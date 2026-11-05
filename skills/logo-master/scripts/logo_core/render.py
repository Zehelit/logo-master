"""Local font proof and Inkscape rendering; environment is subprocess-scoped."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from .model import read_svg, sha256
from .audit import audit_svg, style_dict

_FONT_PROBE = r'''
import ctypes,ctypes.util,json,sys
from pathlib import Path
import gi
gi.require_version('Pango','1.0');gi.require_version('PangoCairo','1.0')
from gi.repository import Pango,PangoCairo
data=json.load(sys.stdin);desc=Pango.FontDescription();desc.set_family(data['family']);desc.set_weight(Pango.Weight(data.get('weight',400)));desc.set_absolute_size(20*Pango.SCALE)
style_map={'normal':Pango.Style.NORMAL,'italic':Pango.Style.ITALIC,'oblique':Pango.Style.OBLIQUE}
desc.set_style(style_map[data.get('style') or 'normal'])
fm=PangoCairo.FontMap.get_default();ctx=fm.create_context();font=fm.load_font(ctx,desc)
layout=Pango.Layout.new(ctx);layout.set_font_description(desc);layout.set_text(data['text'],-1)
actual=font.describe();style_names={int(v):k for k,v in style_map.items()}
result={'resolved_family':actual.get_family(),'resolved_weight':int(actual.get_weight()),'resolved_style':style_names.get(int(actual.get_style()),'unknown'),'resolved_description':actual.to_string(),'unknown_glyphs':layout.get_unknown_glyphs_count(),'font_file':None,'runs':[]}
iterator=layout.get_iter()
while True:
 run=iterator.get_run_readonly()
 if run:
  description=run.item.analysis.font.describe()
  result['runs'].append({'family':description.get_family(),'weight':int(description.get_weight()),'style':style_names.get(int(description.get_style()),'unknown')})
 if not iterator.next_run():break
try:
 candidates=list(Path(sys.executable).parent.glob('*fontconfig*.dll'))
 library=str(candidates[0]) if candidates else ctypes.util.find_library('fontconfig')
 fc=ctypes.CDLL(library);ptr=ctypes.c_void_p
 fc.FcInitLoadConfigAndFonts.restype=ptr;fc.FcPatternCreate.restype=ptr;fc.FcFontMatch.restype=ptr
 fc.FcPatternAddString.argtypes=[ptr,ctypes.c_char_p,ctypes.c_char_p];fc.FcPatternAddInteger.argtypes=[ptr,ctypes.c_char_p,ctypes.c_int]
 fc.FcConfigSubstitute.argtypes=[ptr,ptr,ctypes.c_int];fc.FcDefaultSubstitute.argtypes=[ptr];fc.FcFontMatch.argtypes=[ptr,ptr,ctypes.POINTER(ctypes.c_int)]
 fc.FcPatternGetString.argtypes=[ptr,ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(ctypes.c_char_p)];fc.FcPatternDestroy.argtypes=[ptr];fc.FcConfigDestroy.argtypes=[ptr]
 config=fc.FcInitLoadConfigAndFonts();pattern=fc.FcPatternCreate()
 fc.FcPatternAddString(pattern,b'family',result['resolved_family'].encode());fc.FcPatternAddInteger(pattern,b'weight',{100:0,200:40,300:50,400:80,500:100,600:180,700:200,800:205,900:210}.get(result['resolved_weight'],80))
 fc.FcPatternAddInteger(pattern,b'slant',{'normal':0,'italic':100,'oblique':110}.get(result['resolved_style'],0))
 fc.FcConfigSubstitute(config,pattern,0);fc.FcDefaultSubstitute(pattern);code=ctypes.c_int();match=fc.FcFontMatch(config,pattern,ctypes.byref(code));file=ctypes.c_char_p()
 if match and fc.FcPatternGetString(match,b'file',0,ctypes.byref(file))==0:
  result['font_file']=file.value.decode();result['font_file_evidence']='Fontconfig match for resolved Pango descriptor'
 if match:fc.FcPatternDestroy(match)
 fc.FcPatternDestroy(pattern);fc.FcConfigDestroy(config)
except Exception as exc:result['font_file_probe_warning']=type(exc).__name__+': '+str(exc)
print(json.dumps(result,ensure_ascii=False))
'''

def _executable(env,key,candidates):
    explicit=env.get(key)
    if explicit:
        if not Path(explicit).is_file():raise ValueError(key+' yolu bulunamadı.')
        return explicit
    for name in candidates:
        found=shutil.which(name,path=env.get('PATH'))
        if found:return found
    raise ValueError(key+' yapılandırılmamış; sessiz alternatif kullanılmaz.')

def resolve_font(font_spec: dict, text: str, env: dict) -> dict:
    family=font_spec.get('family');weight=font_spec.get('weight',400);requested_style=font_spec.get('style') or 'normal'
    if not isinstance(family,str) or not family:return {'status':'failed','reason':'font_family_unknown'}
    if requested_style not in ['normal','italic','oblique']:return {'status':'failed','reason':'font_style_unsupported'}
    scoped=dict(env)
    try:python=_executable(scoped,'LOGO_FONT_PYTHON',['python3','python'])
    except ValueError as exc:return {'status':'failed','reason':str(exc)}
    path=font_spec.get('path')
    if path:
        path=Path(path)
        if not path.is_file() or (font_spec.get('sha256') and sha256(path)!=font_spec['sha256']):
            return {'status':'failed','reason':'font_file_or_hash_invalid'}
    with tempfile.TemporaryDirectory(prefix='logo-font-') as folder:
        if path:
            from xml.sax.saxutils import escape
            config=Path(folder)/'fonts.conf';config.write_text('<fontconfig><dir>'+escape(str(path.resolve().parent))+'</dir><cachedir>'+escape(folder)+'</cachedir></fontconfig>',encoding='utf-8')
            scoped['FONTCONFIG_FILE']=str(config);scoped['PANGOCAIRO_BACKEND']='fc'
        try:
            probe=subprocess.run([python,'-c',_FONT_PROBE],input=json.dumps({'family':family,'weight':weight,'style':font_spec.get('style'),'text':text}),capture_output=True,text=True,encoding='utf-8',env=scoped,timeout=45,check=True)
            result=json.loads(probe.stdout)
        except (subprocess.SubprocessError,json.JSONDecodeError) as exc:
            return {'status':'failed','reason':'font_probe_failed','detail':str(exc)}
    matched=result['resolved_family'].casefold()==family.casefold() and result['resolved_weight']==weight and result['resolved_style']==requested_style and result['unknown_glyphs']==0
    matched=matched and all(run['family'].casefold()==family.casefold() and run['weight']==weight and run['style']==requested_style for run in result['runs'])
    if path:
        observed=result.get('font_file')
        matched=matched and bool(observed) and Path(observed).resolve()==path.resolve()
    result.update(status='passed' if matched else 'failed',requested_family=family,requested_weight=weight,requested_style=requested_style)
    if result.get('font_file') and Path(result['font_file']).is_file():result['font_file_sha256']=sha256(result['font_file'])
    return result

def _run_inkscape(source,target,args,env):
    source,target=Path(source),Path(target)
    if source.resolve()==target.resolve() or target.exists():raise ValueError('Yeni, mevcut olmayan çıktı yolu gerekli.')
    audit=audit_svg(source)
    if audit['errors'] or any(r['kind']=='external' for r in audit['references']):raise ValueError('Geçersiz veya dış varlığa bağlı SVG render edilmez.')
    exe=_executable(env,'LOGO_INKSCAPE',['inkscape.com','inkscape'])
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='logo-render-') as folder:
        staged=Path(folder)/target.name
        ret=subprocess.run([exe,str(source),*args,f'--export-filename={staged}'],capture_output=True,text=True,env=dict(env),timeout=90,check=True)
        if not staged.is_file():raise ValueError('Renderer çıktı oluşturmadı.')
        shutil.copyfile(staged,target)
    return {'status':'passed','path':str(target.resolve()),'sha256':sha256(target),'source_sha256':sha256(source),'renderer':exe,'stderr':ret.stderr.strip()}

def render_svg(source: Path, target: Path, width: int, height: int, env: dict) -> dict:
    if type(width) is not int or type(height) is not int or min(width,height)<=0:raise ValueError('Pozitif piksel ölçüleri gerekli.')
    if Path(target).suffix.lower()!='.png':raise ValueError('Render çıktısı PNG olmalı.')
    checks=validate_live_fonts(source,env)
    result=_run_inkscape(source,target,[f'--export-width={width}',f'--export-height={height}'],env)
    result['font_checks']=checks
    return result

def validate_live_fonts(source: Path, env: dict) -> list:
    tree=read_svg(source);checks=[]
    if any(n.tag.split('}')[-1]=='text' for n in tree.iter()) and any(n.tag.split('}')[-1]=='style' or n.get('class') for n in tree.iter()):
        raise ValueError('CSS seçicili canlı metnin fontu bu çözümleyiciyle kanıtlanamaz; açık font özelliklerine dönüştür.')
    def prove(style,text):
        if style.get('font'):raise ValueError('Font shorthand çözümlenmeden font kanıtı üretilemez.')
        family=style.get('font-family','').strip().strip("'\"")
        weight=style.get('font-weight','400');weight={'normal':'400','bold':'700'}.get(weight,weight)
        if not weight.isdigit():raise ValueError('Font ağırlığı çözümlenemedi.')
        proof=resolve_font({'family':family,'weight':int(weight),'style':style.get('font-style')},text,env)
        if proof['status']!='passed':raise ValueError('Font ikamesi/eksik glif: '+json.dumps(proof,ensure_ascii=False))
        checks.append(proof)
    def walk(node,inherited,in_text=False):
        style=dict(inherited);style.update({k:v for k,v in node.attrib.items() if k.startswith('font-')});style.update(style_dict(node.get('style','')))
        in_text=in_text or node.tag.split('}')[-1]=='text'
        if in_text and (node.text or '').strip():prove(style,node.text)
        for child in node:
            walk(child,style,in_text)
            if in_text and (child.tail or '').strip():prove(style,child.tail)
    walk(tree,{})
    return checks

def outline_svg(source: Path, target: Path, env: dict) -> dict:
    checks=validate_live_fonts(source,env)
    result=_run_inkscape(source,target,['--actions=select-all:all;object-to-path','--export-plain-svg'],env)
    if any(n.tag.split('}')[-1]=='text' for n in read_svg(target).iter()):
        Path(target).unlink();raise ValueError('Konturlu çıktıda canlı metin kaldı.')
    result['font_checks']=checks
    return result
