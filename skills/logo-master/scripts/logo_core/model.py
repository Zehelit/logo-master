"""Versioned, read-only project and asset validation."""
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import xml.etree.ElementTree as ET


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_project(path: Path) -> dict:
    project = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(project, dict):
        raise ValueError('Proje JSON kökü nesne olmalı.')
    return project


def safe_path(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or PureWindowsPath(relative).drive:
        raise ValueError('Varlık yolu proje köküne göre olmalı.')
    target = (Path(root) / relative).resolve()
    if not target.is_relative_to(Path(root).resolve()):
        raise ValueError('Varlık yolu proje kökü dışına çıkıyor.')
    return target


def read_svg(path):
    raw = Path(path).read_bytes()
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('SVG içinde DTD/entity desteklenmiyor.')
    tree = ET.fromstring(raw)
    if tree.tag.split('}')[-1] != 'svg':
        raise ValueError('SVG kökü bulunamadı.')
    return tree


def variants(project):
    for design in project.get('designs', []):
        for variant in design.get('variants', []):
            yield design, variant


def find_variant(project, variant_id):
    rows = [(d, v) for d, v in variants(project) if v['id'] == variant_id]
    if len(rows) != 1:
        raise ValueError('Varyant kimliği tekil olarak bulunamadı: ' + str(variant_id))
    return rows[0]


def validate_project(project: dict, root: Path) -> dict:
    errors, warnings, assets = [], [], []
    def add(code, message, context=''):
        errors.append({'code': code, 'message': message, 'context': context})
    def asset(spec, context):
        if not isinstance(spec, dict):
            add('asset_invalid', 'Varlık kaydı nesne olmalı.', context); return None
        try: path = safe_path(root, spec.get('path'))
        except ValueError as exc:
            add('unsafe_path', str(exc), context); return None
        if not path.is_file():
            add('asset_missing', 'Varlık dosyası bulunamadı.', context); return None
        digest = sha256(path)
        if digest != spec.get('sha256'):
            add('hash_mismatch', 'Varlık hash kaydı gerçek dosyayla uyuşmuyor.', context)
        assets.append({'path': str(path), 'sha256': digest, 'context': context})
        return path
    if not isinstance(project, dict):
        return {'status':'failed','errors':[{'code':'project_invalid','message':'Proje nesne olmalı.'}],'warnings':[],'assets':[]}
    # Reject malformed nested shapes before identity, path, and graph traversal.
    malformed = []
    for design in project.get('designs', []) if isinstance(project.get('designs'),list) else []:
        if not isinstance(design,dict): continue
        for key in ['approach','case']:
            if type(design.get(key)) is not int: malformed.append('design.'+key)
        rows=design.get('variants',[])
        if not isinstance(rows,list): continue
        for row in rows:
            if not isinstance(row,dict): continue
            for key in ['selection','source','canvas']:
                if not isinstance(row.get(key),dict): malformed.append('variant.'+key)
            if row.get('parent_id') is not None and not isinstance(row['parent_id'],str): malformed.append('variant.parent_id')
            if not isinstance(row.get('components',[]),list) or not isinstance(row.get('artifacts',[]),list): malformed.append('variant.lists'); continue
            if row.get('canva') is not None and not isinstance(row['canva'],dict): malformed.append('variant.canva')
            for comp in row.get('components',[]):
                if not isinstance(comp,dict) or not isinstance(comp.get('id'),str) or (comp.get('font') is not None and not isinstance(comp['font'],dict)): malformed.append('component')
    if malformed:
        return {'status':'failed','errors':[{'code':'record_type_invalid','message':'Geçersiz kayıt türü: '+s} for s in malformed],'warnings':[],'assets':[]}
    if project.get('schema_version') != 1:
        add('schema_version', 'Desteklenen şema sürümü 1.')
    if not project.get('project_id') or not isinstance(project.get('brand'), dict):
        add('project_identity', 'Proje kimliği ve marka kaydı gerekli.')
    if not isinstance(project.get('designs'), list):
        add('designs_invalid', 'designs liste olmalı.')
        return {'status': 'failed', 'errors': errors, 'warnings': warnings, 'assets': assets}
    seen_designs, seen_variants, seen_cases = set(), set(), set()
    for design in project['designs']:
        if not isinstance(design, dict):
            add('design_invalid', 'Tasarım kaydı nesne olmalı.'); continue
        did = design.get('id')
        if not isinstance(did, str) or not did or did in seen_designs:
            add('duplicate_design', 'Tasarım kimliği boş veya yinelenmiş.', str(did))
        seen_designs.add(str(did))
        case_key = (design.get('approach'), design.get('case'))
        if any(type(n) is not int or n <= 0 for n in case_key) or case_key in seen_cases:
            add('case_identity', 'Yaklaşım/case pozitif ve tekil olmalı.', str(did))
        seen_cases.add(case_key)
        rows = design.get('variants')
        if not isinstance(rows, list):
            add('variants_invalid', 'variants liste olmalı.', str(did)); continue
        parent_map, numbers = {}, set()
        for variant in rows:
            if not isinstance(variant, dict):
                add('variant_invalid', 'Varyant kaydı nesne olmalı.', str(did)); continue
            vid = variant.get('id'); context = str(vid)
            if not isinstance(vid, str) or not vid or vid in seen_variants:
                add('duplicate_variant', 'Varyant kimliği boş veya yinelenmiş.', context)
            seen_variants.add(str(vid)); parent_map[str(vid)] = variant.get('parent_id')
            number = variant.get('number')
            if type(number) is not int or number <= 0 or number in numbers:
                add('variant_number', 'Varyant numarası case içinde pozitif ve tekil olmalı.', context)
            numbers.add(str(number)) if not isinstance(number, int) else numbers.add(number)
            if type(variant.get('active')) is not bool:
                add('active_invalid', 'active boolean olmalı.', context)
            selection = variant.get('selection', {})
            if selection.get('status') not in ['candidate', 'selected', 'approved', 'rejected']:
                add('selection_invalid', 'Seçim durumu tanınmıyor.', context)
            if selection.get('status') in ['selected', 'approved'] and not selection.get('evidence'):
                add('selection_evidence_missing', 'Seçim/onay kanıtı gerekli.', context)
            canvas = variant.get('canvas', {})
            if any(type(canvas.get(k)) not in [int, float] or not math.isfinite(canvas[k]) or canvas[k] <= 0 for k in ['width', 'height']):
                add('canvas_invalid', 'Tuval ölçüleri pozitif sonlu sayı olmalı.', context)
            source = variant.get('source', {})
            if source.get('kind') not in ['vector', 'hybrid', 'raster']:
                add('source_kind', 'Kaynak türü vector/hybrid/raster olmalı.', context)
            source_path = asset(source, context)
            node_ids = None
            if source_path and source_path.suffix.lower() == '.svg':
                try:
                    tree = read_svg(source_path)
                    ids = [n.get('id') for n in tree.iter() if n.get('id')]
                    if len(ids) != len(set(ids)): add('svg_duplicate_id', 'SVG id çakışması var.', context)
                    node_ids = set(ids)
                except (ValueError, ET.ParseError) as exc:
                    add('svg_invalid', str(exc), context)
            component_ids = set()
            for comp in variant.get('components', []):
                cid = comp.get('id')
                if not cid or cid in component_ids:
                    add('component_identity', 'Bileşen kimliği boş veya yinelenmiş.', context)
                component_ids.add(cid)
                if node_ids is not None and comp.get('svg_id') not in node_ids:
                    add('component_missing', 'Kaynak SVG bileşen düğümünü içermiyor.', context + '/' + str(cid))
                kind = comp.get('kind')
                if kind not in ['vector', 'raster', 'live_text', 'outlined']:
                    add('component_kind', 'Bileşen türü tanınmıyor.', context)
                font = comp.get('font') or {}
                if kind == 'live_text':
                    if not font.get('family') or font.get('status') == 'unknown':
                        add('live_font_unknown', 'Canlı metnin gerçek font ailesi bilinmeli.', context)
                    if not comp.get('text'):
                        add('live_text_missing', 'Canlı metin içeriği gerekli.', context)
                    if font.get('path'):
                        asset(font, context + '/font')
                        if font.get('license_file'): asset(font['license_file'],context+'/font_license')
                        else: warnings.append({'code':'font_license_file_unverified','context':context,'message':'Font dağıtımından önce lisans dosyasını ekle/doğrula.'})
                    elif font.get('family'):
                        warnings.append({'code': 'font_file_unverified', 'context': context, 'message': 'Font dosyası ve renderer çözümlemesi ayrıca doğrulanmalı.'})
                if kind == 'outlined' and not font.get('family'):
                    warnings.append({'code': 'font_unknown_outlined', 'context': context, 'message': 'Konturlar korunabilir; canlı font ailesi değiştirme kanıtı yok.'})
            for output in variant.get('artifacts', []): asset(output, context + '/artifact')
            canva = variant.get('canva') or {}
            if canva.get('source_sha256') and canva['source_sha256'] != source.get('sha256'):
                add('canva_source_mismatch', 'Canva eşlemesi başka kaynak sürümüne bağlı; sessiz aktarım yapılamaz.', context)
        for child, parent in parent_map.items():
            if parent is not None and parent not in parent_map:
                add('parent_missing', 'Ebeveyn aynı tasarım içinde bulunamadı.', child); continue
            chain, cursor = set(), child
            while cursor is not None and cursor in parent_map:
                if cursor in chain:
                    add('parent_cycle', 'Ebeveyn zinciri döngülü.', child); break
                chain.add(cursor); cursor = parent_map[cursor]
    return {'status': 'failed' if errors else 'passed', 'errors': errors, 'warnings': warnings, 'assets': assets}
