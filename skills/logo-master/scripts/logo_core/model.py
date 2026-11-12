"""Versioned, read-only project and asset validation."""
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import xml.etree.ElementTree as ET
from .assets import declaration_conflicts, inspect_asset, read_svg
from .canva_records import stage_errors
from .provenance import generation_errors, pilot_allows
from .typography import live_text_runs


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
    observations = {}
    def asset(spec, context, *, visual=False):
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
        record = {'path': str(path), 'sha256': digest, 'context': context}
        if visual:
            if path not in observations:
                observations[path] = inspect_asset(path)
            record['observed'] = observations[path]
        assets.append(record)
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
            source_path = asset(source, context, visual=True)
            nodes = None
            observed = observations.get(source_path, {})
            kind = observed.get('kind')
            if kind and kind != source.get('kind'):
                add('source_kind_mismatch', f"Beyan edilen tür {source.get('kind')}; dosyada ölçülen {kind}.", context)
            elif source_path and not kind:
                if source_path.suffix.lower() == '.svg' or observed.get('reason') == 'xml_not_readable_as_svg':
                    add('svg_invalid', observed.get('detail', 'Dosya SVG olarak okunamadı.'), context)
                else:
                    warnings.append({'code':'source_kind_unmeasured','context':context,'observed':observed})
            if observed.get('format') == 'svg':
                try:
                    tree = read_svg(source_path)
                    ids = [n.get('id') for n in tree.iter() if n.get('id')]
                    if len(ids) != len(set(ids)): add('svg_duplicate_id', 'SVG id çakışması var.', context)
                    nodes = {node.get('id'):node for node in tree.iter() if node.get('id')}
                except (ValueError, ET.ParseError) as exc:
                    add('svg_invalid', str(exc), context)
            component_ids = set()
            for comp in variant.get('components', []):
                cid = comp.get('id')
                if not cid or cid in component_ids:
                    add('component_identity', 'Bileşen kimliği boş veya yinelenmiş.', context)
                component_ids.add(cid)
                if nodes is not None and comp.get('svg_id') not in nodes:
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
                    if nodes is not None and comp.get('svg_id') in nodes:
                        text_context = context + '/' + cid
                        runs, css = live_text_runs(tree, nodes[comp['svg_id']])
                        actual = ''.join(run['text'] for run in runs)
                        if actual != comp.get('text'):
                            add('live_text_mismatch', f"Model metni {comp.get('text')!r}; SVG metni {actual!r}.", text_context)
                        fonts = [run['font'] for run in runs if run['text'].strip()]
                        if fonts and (css or not all(fonts) or any(item != fonts[0] for item in fonts)):
                            warnings.append({'code':'live_font_needs_review','context':text_context,'status':'needs_review','runs':runs})
                        elif fonts and font.get('family'):
                            actual_font = fonts[0]
                            for key, declared in [('family',font['family']),('weight',font.get('weight',400)),('style',font.get('style','normal'))]:
                                observed = actual_font[key]
                                if str(declared).casefold() != str(observed).casefold():
                                    add('live_font_'+key+'_mismatch', f'Model {key}={declared!r}; SVG {key}={observed!r}.', text_context)
                    if font.get('path'):
                        asset(font, context + '/font')
                        if font.get('license_file'): asset(font['license_file'],context+'/font_license')
                        else: warnings.append({'code':'font_license_file_unverified','context':context,'message':'Font dağıtımından önce lisans dosyasını ekle/doğrula.'})
                    elif font.get('family'):
                        warnings.append({'code': 'font_file_unverified', 'context': context, 'message': 'Font dosyası ve renderer çözümlemesi ayrıca doğrulanmalı.'})
                if kind == 'outlined' and not font.get('family'):
                    warnings.append({'code': 'font_unknown_outlined', 'context': context, 'message': 'Konturlar korunabilir; canlı font ailesi değiştirme kanıtı yok.'})
            for output in variant.get('artifacts', []):
                output_path = asset(output, context + '/artifact', visual=True)
                if output_path:
                    measurement = observations[output_path]
                    if measurement['status'] != 'measured':
                        warnings.append({'code':'artifact_unmeasured','context':context,'path':output['path'],'observed':measurement})
                    for conflict in declaration_conflicts(output, measurement):
                        warnings.append({'code':'artifact_metadata_mismatch','context':context,'path':output['path'],**conflict})
            if 'generation' in variant:
                generation = variant['generation']
                problems = generation_errors(generation)
                for problem in problems:
                    add('generation_record_invalid',problem,context)
                if not problems:
                    output = generation['output']
                    path = asset(output,context+'/generation_output',visual=True)
                    if path and (observations[path]['status'] != 'measured' or declaration_conflicts(output,observations[path])):
                        add('generation_output_metadata','Üretilen dosyanın metadata beyanı ölçümle uyuşmuyor.',context)
                    for ref in generation.get('references', []):
                        if ref.get('path'):
                            asset(ref,context+'/generation_reference')
            if 'technical_pilot' in variant:
                pilot = variant['technical_pilot']
                operations = pilot.get('operations',[]) if isinstance(pilot,dict) else []
                if not operations or not all(pilot_allows(project,variant,op) for op in operations):
                    add('technical_pilot_invalid','Teknik deney proje, varyant ve mevcut kaynak hash’ine bağlanmalı.',context)
            protected = selection.get('protected_components',[])
            if not isinstance(protected,list) or any(not isinstance(item,str) or item not in component_ids for item in protected):
                add('protected_component_invalid','Korunacak bileşen kimliği modelde bulunamadı.',context)
            if 'approval' in variant:
                approval = variant['approval']
                if not isinstance(approval,dict) or approval.get('status') != 'approved' or approval.get('source_sha256') != source.get('sha256') or not approval.get('evidence'):
                    add('final_approval_invalid','Nihai onay mevcut kaynak hash’ine ve kullanıcı kanıtına bağlanmalı.',context)
            canva = variant.get('canva') or {}
            if canva.get('source_sha256') and canva['source_sha256'] != source.get('sha256'):
                add('canva_source_mismatch', 'Canva eşlemesi başka kaynak sürümüne bağlı; sessiz aktarım yapılamaz.', context)
            for problem in stage_errors(canva, vid):
                add('canva_stage_evidence_invalid',problem,context)
        for child, parent in parent_map.items():
            if parent is not None and parent not in parent_map:
                add('parent_missing', 'Ebeveyn aynı tasarım içinde bulunamadı.', child); continue
            chain, cursor = set(), child
            while cursor is not None and cursor in parent_map:
                if cursor in chain:
                    add('parent_cycle', 'Ebeveyn zinciri döngülü.', child); break
                chain.add(cursor); cursor = parent_map[cursor]
    return {'status': 'failed' if errors else 'passed', 'errors': errors, 'warnings': warnings, 'assets': assets}
