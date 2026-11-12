"""Local checks for Canva transfers and controlled PDF imports."""
from collections import Counter
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .assets import inspect_asset, read_svg
from .audit import audit_svg, compare_renders
from .edit import write_svg
from .model import sha256
from .render import RendererError, _executable, render_svg


def preflight_canva(path, expected_sha256=None):
    path = Path(path).resolve()
    digest = sha256(path)
    observed = inspect_asset(path)
    errors = []
    if expected_sha256 is not None and digest != expected_sha256:
        errors.append({'code':'source_hash_changed','expected':expected_sha256,'observed':digest})
    if observed.get('format') != 'svg':
        errors.append({'code':'not_svg','observed':observed})
        audit = None
    else:
        audit = audit_svg(path)
        errors.extend(audit['errors'])
        errors.extend({'code':'external_reference','reference':ref} for ref in audit['references'] if ref['kind']=='external')
    if sha256(path) != digest:
        errors.append({'code':'source_changed_during_preflight'})
    return {'status':'failed' if errors else 'passed', 'path':str(path), 'sha256':digest, 'errors':errors,
            'audit':audit, 'canva_acceptance':'not_run'}


def remove_unreferenced_duplicate_ids(root):
    nodes = [node for node in root.iter() if node.get('id')]
    duplicates = {ident for ident,number in Counter(node.get('id') for node in nodes).items() if number>1}
    if not duplicates:
        return []
    for node in root.iter():
        if node.tag.split('}')[-1] == 'style':
            raise ValueError('CSS içeren SVG’de yinelenen kimlikler otomatik kaldırılmaz.')
        for key,value in node.attrib.items():
            if key == 'id':
                continue
            tokens = set(re.findall(r'[-\w:.]+',value))
            if tokens & duplicates:
                raise ValueError('Yinelenen SVG kimliğinin referansı belirsiz; otomatik düzeltme durdu.')
    seen, removed = set(), []
    for node in nodes:
        ident = node.get('id')
        if ident in seen:
            removed.append(node.attrib.pop('id'))
        seen.add(ident)
    return removed


def _remove_white_page_rect(root, ident):
    if any(node.tag.split('}')[-1] == 'style' or node.get('class') for node in root.iter()) or any(
            root.get(key) for key in ('style','opacity','clip-path','mask','filter')):
        raise ValueError('Sayfa arka planının görünümü CSS veya kök etkileriyle değişebilir.')
    candidates = [node for node in root if node.tag.split('}')[-1] not in {'defs','metadata','title','desc'}]
    if len(candidates) < 2 or candidates[0].get('id') != ident:
        raise ValueError('Arka plan kimliği, ilk bağımsız çizim katmanı olarak bulunamadı.')
    node = candidates[0]
    attrs = node.attrib
    if (node.tag.split('}')[-1] != 'rect' or set(attrs)-{'id','x','y','width','height','fill','stroke'}
            or attrs.get('stroke','none') != 'none' or attrs.get('fill','').lower() not in {'white','#fff','#ffffff'}):
        raise ValueError('Arka plan öğesi etkisiz, opak beyaz bir dikdörtgen olarak doğrulanamadı.')
    try:
        viewport = ([float(value) for value in re.split(r'[,\s]+',root.get('viewBox').strip())] if root.get('viewBox') else
                    [0,0,float(root.get('width','').removesuffix('px')),float(root.get('height','').removesuffix('px'))])
        bounds = [float(node.get(key,'0').removesuffix('px')) for key in ['x','y','width','height']]
    except ValueError as exc:
        raise ValueError('Arka plan ve sayfa koordinatları doğrudan karşılaştırılamadı.') from exc
    if len(viewport)!=4 or min(viewport[2:])<=0 or bounds != viewport:
        raise ValueError('Beyaz dikdörtgenin tam sayfayı kapladığı doğrulanamadı.')
    root.remove(node)
    return {'svg_id':ident, 'bounds':bounds, 'reason':'first opaque white page-sized rect'}


def convert_pdf(source, target, page, env, *, repair_unreferenced_ids=False, background_id=None):
    source,target = Path(source).resolve(),Path(target).resolve()
    if source==target or target.exists() or target.suffix.lower()!='.svg':
        raise ValueError('PDF dönüşümü için yeni bir SVG çıktı yolu gerekli.')
    observed = inspect_asset(source)
    pages = observed.get('pages', [])
    if observed.get('format') != 'pdf' or type(page) is not int or not 1 <= page <= len(pages):
        raise ValueError('PDF sayfası ölçülemedi veya sayfa numarası geçersiz.')
    source_digest = sha256(source)
    exe = _executable(env,'LOGO_INKSCAPE',['inkscape.com','inkscape'])
    page_observed = pages[page-1]
    size = page_observed['size'][::-1] if page_observed['rotation'] % 180 else page_observed['size']
    scale = 768 / max(size)
    dimensions = [max(1,round(value*scale)) for value in size]
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.logo-pdf-',dir=target.parent) as folder:
        stage = Path(folder)
        svg, before, after = (stage/name for name in ('converted.svg','before.png','after.png'))
        common = [exe,str(source),'--pdf-poppler',f'--pages={page}']
        dimensions_args = [f'--export-width={dimensions[0]}',f'--export-height={dimensions[1]}']
        try:
            for args,path in [(['--export-plain-svg'],svg),(dimensions_args,before)]:
                subprocess.run([*common,*args,f'--export-filename={path}'],capture_output=True,text=True,env=env,check=True,timeout=90)
            version = subprocess.run([exe,'--version'],capture_output=True,text=True,env=env,check=True,timeout=15).stdout.strip()
        except (OSError,subprocess.SubprocessError) as exc:
            raise RendererError('pdf_import',str(exc),cause=type(exc).__name__) from exc
        tree = read_svg(svg)
        removed_ids = remove_unreferenced_duplicate_ids(tree) if repair_unreferenced_ids else []
        removed_background = _remove_white_page_rect(tree,background_id) if background_id else None
        if removed_ids or removed_background:
            write_svg(tree,svg)
        preflight = preflight_canva(svg)
        if preflight['status'] != 'passed':
            return {'status':'failed','source_sha256':source_digest,'pdf_page':page_observed,'preflight':preflight}
        render_svg(svg,after,*dimensions,env)
        comparison = compare_renders(before,after,renderer={'path':exe,'version':version,'pdf_importer':'poppler'})
        if comparison['status'] == 'failed' or sha256(source) != source_digest:
            return {'status':'failed','reason':'render_comparison_or_source_integrity','source_sha256':source_digest,'comparison':comparison}
        if removed_background and comparison['visible_changes_by_background']['light']:
            return {'status':'failed','reason':'white_background_removal_changed_visible_artwork','source_sha256':source_digest,'comparison':comparison}
        os.link(svg,target)
    preflight['audit']['file'] = str(target)
    return {'status':'passed','path':str(target),'sha256':sha256(target),'source_sha256':source_digest,'pdf_page':page_observed,
            'pdf_page_number':page,'converted_svg':inspect_asset(target),'audit':preflight['audit'],'render_comparison':comparison,
            'comparison_acceptance':'passed' if comparison['visible_changed_pixels'] == 0 else 'needs_review',
            'removed_unreferenced_duplicate_ids':removed_ids,'removed_background':removed_background,'canva_acceptance':'not_run'}
