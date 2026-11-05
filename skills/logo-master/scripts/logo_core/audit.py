"""Structural checks are evidence, not aesthetic or renderer equivalence certificates."""
import copy
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from .model import read_svg, sha256

GEOMETRY = {'d','points','x','y','x1','y1','x2','y2','cx','cy','r','rx','ry','width','height','viewBox','transform','stroke-width','stroke-linecap','stroke-linejoin','stroke-miterlimit','stroke-dasharray','stroke-dashoffset','fill-rule','clip-rule','font-family','font-size','font-weight','letter-spacing','word-spacing','text-anchor','vector-effect'}

def signature(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def style_dict(value):
    return dict(s.split(':',1) for s in [p.strip() for p in value.split(';')] if ':' in s)

def canonical(node, geometry=False):
    attrs = dict(node.attrib)
    style = style_dict(attrs.pop('style',''))
    attrs.update({k.strip():v.strip() for k,v in style.items()})
    if geometry:attrs={k:v for k,v in attrs.items() if k in GEOMETRY}
    return {'tag':node.tag,'attrs':attrs,'text':node.text or '', 'tail':node.tail or '', 'children':[canonical(c,geometry) for c in node]}

def audit_svg(path: Path) -> dict:
    root=read_svg(path);counts={};refs=[];warnings=[];errors=[];transform_chains=[]
    def chains(node, inherited):
        current=inherited+([node.get('transform')] if node.get('transform') else [])
        if node.get('id'):
            transform_chains.append({'svg_id':node.get('id'),'ordered_ancestor_and_local_transforms':current,'coordinate_note':'Dıştan içe bileşim; iç SVG viewBox ve CSS bu listeyle sayısal çözülmez.'})
        for child in node: chains(child,current)
    chains(root,[])
    ids=[n.get('id') for n in root.iter() if n.get('id')];idset=set(ids)
    if len(ids)!=len(idset):errors.append({'code':'duplicate_id','message':'SVG id çakışması.'})
    for n in root.iter():
        tag=n.tag.split('}')[-1];counts[tag]=counts.get(tag,0)+1
        if tag=='style' or n.get('class'):
            warnings.append({'code':'stylesheet_requires_render','message':'CSS seçicileri için gerçek render gerekli.'})
        if tag=='style':
            stylesheet=''.join(n.itertext())
            if re.search(r'@import\b',stylesheet,re.I) or any(not value.startswith('#') for value in re.findall(r'url\(\s*[\'"]?([^\)\'"\s]+)',stylesheet)):
                refs.append({'tag':tag,'kind':'external','target':'stylesheet-external-dependency'})
                warnings.append({'code':'external_reference','message':'Stil sayfası dış bağımlılık içeriyor.'})
        if tag in ['filter','mask','clipPath','foreignObject','script']:
            warnings.append({'code':'effect_requires_render','message':tag+' görünüm için render incelemesi gerektirir.'})
        if tag in ['script','foreignObject']:
            errors.append({'code':'active_content','message':'Düz logo kaynağında aktif içerik desteklenmiyor.'})
        for key,value in n.attrib.items():
            if key.startswith('on'):errors.append({'code':'active_content','message':'SVG olay kodu desteklenmiyor.'})
            if key.split('}')[-1]=='href':
                kind='internal' if value.startswith('#') else 'embedded' if value.startswith('data:') else 'external'
                refs.append({'tag':tag,'kind':kind,'target':value if kind!='embedded' else 'sha256:'+hashlib.sha256(value.encode()).hexdigest()})
                if kind=='internal' and value[1:] not in idset:errors.append({'code':'missing_reference','target':value})
                if kind=='external':warnings.append({'code':'external_reference','message':'Dış varlık çözülmeden görünüm eşdeğerliği kanıtlanmaz.'})
            for target in re.findall(r'url\(\s*[\'"]?([^\)\'"\s]+)',value):
                if target.startswith('#') and target[1:] not in idset:errors.append({'code':'missing_reference','target':target})
                if not target.startswith('#'):
                    refs.append({'tag':tag,'kind':'external','target':target})
                    warnings.append({'code':'external_reference','message':'Harici url() varlığı var.'})
    raster=counts.get('image',0)>0
    return {'file':str(Path(path).resolve()),'sha256':sha256(path),'status':'failed' if errors else 'needs_render' if warnings else 'passed','counts':counts,'transform_chains':transform_chains,'references':refs,'errors':errors,'warnings':warnings,'source_kind':'hybrid' if raster else 'vector','geometry_signature':signature(canonical(root,True)),'appearance_signature':signature(canonical(root)),'limitations':'Yapısal eşitlik estetik onay veya renderer eşdeğerliği değildir; CSS, efekt ve font çözümlemesini ayrıca doğrula.'}

def _target(root, ident):
    found=[n for n in root.iter() if n.get('id')==ident]
    if len(found)!=1:raise ValueError('Hedef SVG id tekil olmalı: '+str(ident))
    return found[0]

def compare_operation(before: Path, after: Path, contract: dict) -> dict:
    a,b=read_svg(before),read_svg(after);aa,bb=audit_svg(before),audit_svg(after)
    if aa['errors'] or bb['errors']:return {'status':'failed','reason':'invalid_svg','before':aa,'after':bb}
    kind=contract.get('kind');allowed=contract.get('target_component')
    try:
        if kind=='recolor':
            for root in [a,b]:
                for n in _target(root,allowed).iter():
                    for key in ['fill','stroke']:
                        if n.get(key) and n.get(key).lower() not in ['none','transparent']:n.set(key,'__allowed_color__')
                    if n.get('style'):
                        st=style_dict(n.get('style'));st={k.strip():v.strip() for k,v in st.items()}
                        for key in ['fill','stroke']:
                            if st.get(key) and st[key].lower() not in ['none','transparent']:st[key]='__allowed_color__'
                        n.set('style',';'.join(k+':'+v for k,v in sorted(st.items())))
        elif kind in ['scale','layout']:
            na,nb=_target(a,allowed),_target(b,allowed)
            if nb.get('transform','')!=contract.get('expected_transform'):
                return {'status':'failed','reason':'unexpected_transform'}
            nb.attrib.pop('transform',None)
            if na.get('transform') is not None:nb.set('transform',na.get('transform'))
        elif kind=='identical':pass
        else:return {'status':'needs_render','reason':'operation_requires_specific_or_render_contract'}
        same=canonical(a)==canonical(b)
        result={'status':'passed' if same else 'failed','protected_structure_equal':same,'before_sha256':aa['sha256'],'after_sha256':bb['sha256']}
        if same and (aa['warnings'] or bb['warnings']):result.update(status='needs_render',reason='structural_match_with_unresolved_appearance')
        return result
    except ValueError as exc:return {'status':'failed','reason':str(exc)}

def audit_png(path):
    from PIL import Image
    import numpy as np
    with Image.open(path) as source:
        im=source.convert('RGBA');arr=np.array(im);alpha=arr[:,:,3];ys,xs=np.nonzero(alpha)
        return {'status':'passed','size':list(im.size),'mode':source.mode,'dpi':list(source.info.get('dpi',[])),'transparent_pixels':int((alpha==0).sum()),'opaque_pixels':int((alpha==255).sum()),'partial_alpha_pixels':int(((alpha>0)&(alpha<255)).sum()),'all_corners_transparent':all(alpha[y,x]==0 for y,x in [(0,0),(0,-1),(-1,0),(-1,-1)]),'visible_bbox':None if not len(xs) else [int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]}

def compare_renders(before,after):
    from PIL import Image
    import numpy as np
    with Image.open(before) as first,Image.open(after) as second:
        a=np.array(first.convert('RGBA'));b=np.array(second.convert('RGBA'))
    if a.shape!=b.shape:return {'status':'failed','reason':'dimensions_differ'}
    changed=np.any(a!=b,axis=2);visible=np.zeros(changed.shape,dtype=bool)
    for bg in [0.,255.]:
        af=a[:,:,:3].astype(float)*(a[:,:,3:4]/255.)+bg*(1-a[:,:,3:4]/255.)
        bf=b[:,:,:3].astype(float)*(b[:,:,3:4]/255.)+bg*(1-b[:,:,3:4]/255.)
        visible|=np.any(np.rint(af)!=np.rint(bf),axis=2)
    return {'status':'equal' if not changed.any() else 'different','rgba_changed_pixels':int(changed.sum()),'visible_changed_pixels':int(visible.sum()),'max_channel_difference':int(np.abs(a.astype(int)-b.astype(int)).max()),'limitations':'Fark sayısı tek başına kusur kararı değildir; görsel ve işlem sözleşmesiyle değerlendir.'}
