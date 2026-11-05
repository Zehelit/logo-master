"""Deterministic edits of selected sources; no generative redraw or in-place writes."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from .model import read_svg, sha256, safe_path, find_variant
from .audit import audit_svg, compare_operation, canonical, style_dict, audit_png
from .render import render_svg, _executable

SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)

def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def write_svg(root, path):
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)

def target(root, ident):
    nodes = [n for n in root.iter() if n.get('id') == ident]
    if len(nodes) != 1:
        raise ValueError('Tekil SVG bileşeni bulunamadı: '+str(ident))
    return nodes[0]

def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(name+' pozitif ve sonlu olmalı.')
    return value

def drawing_bbox(source, env, ident=None):
    exe = _executable(env, 'LOGO_INKSCAPE', ['inkscape.com', 'inkscape'])
    args = [exe, str(source)] + ([f'--query-id={ident}'] if ident else [])
    result = subprocess.run(args+['--query-x', '--query-y', '--query-width', '--query-height'], env=dict(env), capture_output=True, text=True, timeout=60, check=True)
    values = [float(v) for v in result.stdout.split()]
    if len(values) != 4 or not all(math.isfinite(v) for v in values) or min(values[2:]) <= 0:
        raise ValueError('Görünür çizim sınırı çözümlenemedi.')
    return values

def apply_edit(project: dict, operation: dict, output_dir: Path) -> dict:
    root = Path(project['_root']); _, variant = find_variant(project, operation['variant_id'])
    selection = variant.get('selection', {})
    if selection.get('status') not in ['selected', 'approved'] or not selection.get('evidence'):
        raise ValueError('Teknik üretim için kullanıcı seçimi veya açık revizyon kanıtı gerekli.')
    source = safe_path(root, variant['source']['path'])
    if sha256(source) != variant['source']['sha256']:
        raise ValueError('Kaynak hash uyuşmazlığı.')
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError('İşlem çıktısı yeni bir dizin olmalı.')
    tree = read_svg(source); kind = operation['kind']; params = operation.get('parameters', {})
    component = next((c for c in variant['components'] if c['id'] == operation.get('target_component')), None)
    if kind != 'canvas' and component is None:
        raise ValueError('Bileşen modelde bulunamadı.')
    node = target(tree, component['svg_id']) if component else None
    contract = {'kind': kind, 'target_component': component['svg_id'] if component else None}
    if kind == 'recolor':
        replacements = params.get('replacements')
        if not isinstance(replacements, dict) or not replacements:
            raise ValueError('Açık eski→yeni renk eşlemesi gerekli.')
        replacements = {k.casefold(): v for k, v in replacements.items()}
        if any(not isinstance(v, str) or any(c in v for c in [';', '(', ')', '<', '>']) for v in replacements.values()):
            raise ValueError('Yalnız düz renk değeri kullanılabilir.')
        changed = 0
        for child in node.iter():
            for key in ['fill', 'stroke']:
                old = child.get(key)
                if old and old.casefold() in replacements:
                    child.set(key, replacements[old.casefold()]); changed += 1
            if child.get('style'):
                styles = {k.strip(): v.strip() for k, v in style_dict(child.get('style')).items()}
                for key in ['fill', 'stroke']:
                    if styles.get(key, '').casefold() in replacements:
                        styles[key] = replacements[styles[key].casefold()]; changed += 1
                child.set('style', ';'.join(k+':'+v for k, v in styles.items()))
        if not changed:
            raise ValueError('Hedef bileşende eşleşen açık renk bulunamadı; kalıtımlı/CSS renk otomatik tahmin edilmez.')
    elif kind in ['scale', 'layout']:
        if kind == 'scale':
            factor = positive(params['factor'], 'Ölçek'); cx, cy = params.get('center', [0, 0])
            transform = f'translate({cx} {cy}) scale({factor}) translate({-cx} {-cy})'
        else:
            x, y = params['translate']
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in [x, y]):
                raise ValueError('Sonlu konum gerekli.')
            transform = f'translate({x} {y})'
        transform += (' '+node.get('transform')) if node.get('transform') else ''
        node.set('transform', transform); contract['expected_transform'] = transform
    elif kind == 'canvas':
        if any('%' in value for element in tree.iter() for value in element.attrib.values()):
            raise ValueError('Yüzdeye bağlı SVG geometri/stili tuval değişiminden önce mutlak koordinata çözülmeli.')
        width = positive(params['width'], 'Tuval genişliği'); height = positive(params['height'], 'Tuval yüksekliği')
        margin = params.get('margin', .08)
        if not isinstance(margin, (int, float)) or not 0 <= margin < .5:
            raise ValueError('Kenar payı 0≤m<0.5 olmalı.')
        # Query is in document user coordinates. Unit-bearing roots require an explicit conversion.
        if any(tree.get(k, '').strip().endswith(u) for k in ['width', 'height'] for u in ['mm', 'cm', 'in', 'pt', '%']):
            raise ValueError('Tuval işlemi önce birim dönüşümü gerektiriyor; sessiz piksel varsayımı yok.')
        x, y, w, h = drawing_bbox(source, dict(os.environ))
        viewbox = tree.get('viewBox')
        if viewbox:
            import re
            vx,vy,vw,vh=map(float,re.split(r'[\s,]+',viewbox.strip()))
            rw,rh=float(tree.get('width',vw)),float(tree.get('height',vh))
            sx,sy=rw/vw,rh/vh
            aspect=tree.get('preserveAspectRatio','xMidYMid meet').strip()
            if aspect=='none': x,y,w,h=vx+x/sx,vy+y/sy,w/sx,h/sy
            elif aspect in ['xMidYMid','xMidYMid meet']:
                ratio=min(sx,sy);ox=(rw-vw*ratio)/2;oy=(rh-vh*ratio)/2
                x,y,w,h=vx+(x-ox)/ratio,vy+(y-oy)/ratio,w/ratio,h/ratio
            else: raise ValueError('Bu preserveAspectRatio için otomatik tuval dönüşümü desteklenmiyor.')
        scale = min(width*(1-2*margin)/w, height*(1-2*margin)/h)
        tx, ty = (width-scale*w)/2-scale*x, (height-scale*h)/2-scale*y
        wrapper = ET.Element('{'+SVG+'}g', {'transform': f'translate({tx} {ty}) scale({scale})'})
        if any(n.tag.split('}')[-1] == 'style' for n in tree.iter()):
            raise ValueError('CSS içeren tuvalde otomatik sarmalama desteklenmiyor.')
        for child in list(tree):
            if child.tag.split('}')[-1] not in ['defs', 'metadata', 'title', 'desc']:
                tree.remove(child); wrapper.append(child)
        tree.append(wrapper); tree.set('width', str(width)); tree.set('height', str(height)); tree.set('viewBox', f'0 0 {width} {height}')
        contract.update(expected_transform=wrapper.get('transform'), bbox=[x, y, w, h])
    else:
        raise ValueError('Desteklenmeyen işlem: '+str(kind))
    with tempfile.TemporaryDirectory(prefix='logo-edit-') as folder:
        staged = Path(folder)/'source.svg'; write_svg(tree, staged)
        if kind == 'canvas':
            # Exact tree contract: only a single wrapper and root canvas attrs were changed.
            restored = copy.deepcopy(tree); wrap = restored[-1]; restored.remove(wrap)
            for child in wrap: restored.append(child)
            original = read_svg(source)
            for key in ['width', 'height', 'viewBox']:
                restored.attrib.pop(key, None)
                if original.get(key) is not None: restored.set(key, original.get(key))
            protected = canonical(restored) == canonical(original)
            check = {'status': 'passed' if protected else 'failed', 'protected_structure_equal': protected, 'contract': contract}
        else:
            check = compare_operation(source, staged, contract)
        if check['status'] == 'failed': raise ValueError('Korunan yapı değişti: '+str(check))
        output_dir.mkdir(parents=True)
        destination = output_dir/'source.svg'; destination.write_bytes(staged.read_bytes())
    result = {'status': check['status'], 'parent_id': variant['id'], 'design_id': next(d['id'] for d in project['designs'] if variant in d['variants']), 'operation': operation, 'source': {'path': str(destination.resolve()), 'sha256': sha256(destination), 'kind': audit_svg(destination)['source_kind']}, 'audit': check, 'original_sha256': sha256(source)}
    write_json(output_dir/'edit-receipt.json', result)
    return result

def _node_path(root, wanted):
    def walk(node, route):
        if node is wanted: return route
        for i, child in enumerate(node):
            result = walk(child, route+[i])
            if result is not None: return result
    return walk(root, [])

def split_svg(source: Path, component_ids: list, output_dir: Path) -> dict:
    root = read_svg(source); output_dir = Path(output_dir)
    if output_dir.exists(): raise ValueError('Ayırma çıktısı yeni dizin olmalı.')
    if len(component_ids) != len(set(component_ids)): raise ValueError('Yinelenen bileşen.')
    routes = {ident: _node_path(root, target(root, ident)) for ident in component_ids}
    if any(a != b and routes[b][:len(routes[a])] == routes[a] for a in routes for b in routes):
        raise ValueError('İç içe hedefler bağımsız parçalara ayrılamaz.')
    output_dir.mkdir(parents=True); skeleton = output_dir/'skeleton.svg'; write_svg(root, skeleton)
    parts = []
    for index, ident in enumerate(component_ids):
        part = copy.deepcopy(root); wanted = target(part, ident)
        ancestors = set()
        def mark(node):
            found = node is wanted
            for child in node: found = mark(child) or found
            if found: ancestors.add(node)
            return found
        mark(part)
        def prune(node):
            if node is wanted or node.tag.split('}')[-1] in ['defs', 'style']: return
            for child in list(node):
                if child in ancestors or child.tag.split('}')[-1] in ['defs', 'style']: prune(child)
                else: node.remove(child)
        prune(part); path = output_dir/f'component-{index+1}.svg'; write_svg(part, path)
        check=audit_svg(path)
        if check['errors'] or any(r['kind']=='external' for r in check['references']):
            raise ValueError('Bağımsız parça bağımlılığı korunamadı; kaynağı self-contained defs ile düzenle: '+str(check['errors']))
        # Store exact context excluding the editable node; prevents silently dropping ancestor edits.
        context = copy.deepcopy(part); editable = target(context,ident); tail=editable.tail; editable.clear(); editable.tag='{'+SVG+'}g'; editable.set('id',ident);editable.tail=tail
        parts.append({'svg_id': ident, 'route': routes[ident], 'path': str(path.resolve()), 'context': canonical(context)})
    manifest = {'status': 'passed', 'skeleton': str(skeleton.resolve()), 'skeleton_sha256': sha256(skeleton), 'parts': parts, 'limitations': 'Parça içi düzenleme desteklenir; ortak defs/ata düzenlemesi yeniden eşleme gerektirir.'}
    write_json(output_dir/'split.json', manifest); return manifest

def assemble_svg(parts, target_path: Path) -> dict:
    if isinstance(parts, (str, Path)): parts = json.loads(Path(parts).read_text(encoding='utf-8'))
    target_path = Path(target_path)
    if target_path.exists(): raise ValueError('Birleştirme çıktısı mevcut olamaz.')
    skeleton = Path(parts['skeleton'])
    if sha256(skeleton) != parts['skeleton_sha256']: raise ValueError('İskelet hash uyuşmazlığı.')
    tree = read_svg(skeleton)
    defs = [canonical(n) for n in tree if n.tag.split('}')[-1] in ['defs', 'style']]
    for item in parts['parts']:
        part = read_svg(Path(item['path']))
        context = copy.deepcopy(part); editable = target(context,item['svg_id']);tail=editable.tail; editable.clear(); editable.tag='{'+SVG+'}g'; editable.set('id',item['svg_id']);editable.tail=tail
        if canonical(context) != item['context']: raise ValueError('Parçanın ata/tuval/bağımlılık bağlamı değişmiş; yeniden eşleme gerekli.')
        if [canonical(n) for n in part if n.tag.split('}')[-1] in ['defs', 'style']] != defs:
            raise ValueError('Ortak bağımlılık değişmiş; sessiz birleştirme yok.')
        parent = tree
        for pos in item['route'][:-1]: parent = parent[pos]
        if not item['route']: raise ValueError('Kök bileşen ayrılamaz.')
        pos = item['route'][-1]; parent.remove(parent[pos]); parent.insert(pos, copy.deepcopy(target(part, item['svg_id'])))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='logo-assemble-') as folder:
        staged = Path(folder)/'source.svg'; write_svg(tree, staged); audit = audit_svg(staged)
        if audit['errors']: raise ValueError('Birleştirmede bozuk referans/id: '+str(audit['errors']))
        target_path.write_bytes(staged.read_bytes())
    return {'status': 'passed', 'path': str(target_path.resolve()), 'sha256': sha256(target_path), 'audit': audit}

def export_png(source: Path, target: Path, width: int, height: int, dpi: int, env: dict, allow_raster_resize=False) -> dict:
    from PIL import Image
    source, target = Path(source), Path(target)
    if target.exists() or source.resolve() == target.resolve(): raise ValueError('Yeni çıktı yolu gerekli.')
    if any(type(v) is not int or v <= 0 for v in [width, height, dpi]): raise ValueError('Pozitif piksel/DPI gerekli.')
    with tempfile.TemporaryDirectory(prefix='logo-export-') as folder:
        if source.suffix.lower() == '.svg':
            rendered = Path(folder)/'render.png'; proof = render_svg(source, rendered, width, height, env); image = Image.open(rendered).convert('RGBA'); kind = 'vector_render'
        else:
            with Image.open(source) as original: image = original.convert('RGBA')
            kind = 'raster_metadata'
            proof = {'source_sha256': sha256(source)}
            if image.size != (width, height):
                if not allow_raster_resize: raise ValueError('Raster boyut değişimi için açık allow_raster_resize gerekli.')
                image = image.resize((width, height), Image.Resampling.LANCZOS); kind = 'raster_resize'
        staged = Path(folder)/'out.png'; image.save(staged, dpi=(dpi, dpi)); image.close()
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(staged.read_bytes())
    return {'status': 'passed', 'path': str(target.resolve()), 'sha256': sha256(target), 'operation': kind, 'audit': audit_png(target), 'render': proof}
