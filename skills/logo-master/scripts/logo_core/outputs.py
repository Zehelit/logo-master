"""Recoverable variant transactions and local-only inventory/panel/package output."""
from contextlib import contextmanager
import copy
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile
import uuid
from .model import load_project, validate_project, safe_path, sha256, find_variant, variants
from .edit import write_json
from .audit import audit_svg
from .assets import declaration_conflicts, inspect_asset
from .render import render_svg
from .provenance import is_technical_pilot, pilot_allows

def _publish_asset(asset,destination,expected_hash):
    # Only the complete verified inode becomes visible at the final path.
    temporary=destination.parent/('.source-'+uuid.uuid4().hex+'.part')
    try:
        with temporary.open('xb') as stream:
            stream.write(asset.read_bytes());stream.flush();os.fsync(stream.fileno())
        if sha256(temporary)!=expected_hash:raise ValueError('Geçici varlık hash uyuşmazlığı.')
        try:os.link(temporary,destination)
        except FileExistsError:
            if sha256(destination)!=expected_hash:raise ValueError('Varyant yolu başka içerikle dolu.')
    finally:
        if temporary.exists():temporary.unlink()

def atomic_json(path, value, *, exclusive=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.logo-', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        if exclusive:
            os.link(name, path)
        else:
            os.replace(name, path)
    finally:
        if Path(name).exists(): Path(name).unlink()

@contextmanager
def project_lock(project_path):
    """OS lock releases on process termination; persistent file is not a stale lock."""
    lock = Path(str(project_path)+'.lock'); stream = open(lock, 'a+b')
    stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close(); raise ValueError('Başka bir kayıt işlemi sürüyor; daha sonra aynı işlem kimliğiyle tekrarla.')
    try: yield
    finally:
        stream.seek(0)
        if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else: fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()

def stage_variant(project: dict, edit_result: dict, output_dir: Path) -> dict:
    if edit_result.get('status') != 'passed':
        raise ValueError('Varyant kaydından önce işlem/render incelemesini tamamla; needs_render başarı sayılmaz.')
    source = Path(edit_result['source']['path'])
    if not source.is_file() or sha256(source) != edit_result['source']['sha256']:
        raise ValueError('Düzenleme çıktısı/hash uyuşmazlığı.')
    operation_id = edit_result.get('operation', {}).get('operation_id')
    if not isinstance(operation_id, str) or not operation_id: raise ValueError('Yeniden deneme için sabit operation_id gerekli.')
    identity = hashlib.sha256(operation_id.encode()).hexdigest()
    stage = Path(output_dir)/identity; stage.mkdir(parents=True, exist_ok=True)
    asset = stage/('source'+source.suffix.lower()); receipt = stage/'staged.json'
    signature = hashlib.sha256(json.dumps(edit_result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if receipt.exists():
        old = load_project(receipt)
        if old['edit_signature'] != signature: raise ValueError('Aynı işlem kimliği başka içerikle kullanılmış.')
        return old
    if asset.exists():
        if sha256(asset) != sha256(source): raise ValueError('Staging varlığı çakışıyor.')
    else: shutil.copyfile(source, asset)
    result = {'status':'staged', 'operation_id':operation_id, 'transaction_key':identity, 'edit_signature':signature, 'edit':edit_result, 'asset_path':str(asset.resolve()), 'asset_sha256':sha256(asset)}
    atomic_json(receipt, result); return result

def commit_variant(project_path: Path, staged: dict, _fail_after_move=False) -> dict:
    project_path = Path(project_path); root = project_path.parent.resolve()
    with project_lock(project_path):
        project = load_project(project_path)
        journal_dir = root/'.logo-transactions'; journal_dir.mkdir(exist_ok=True)
        key = hashlib.sha256(staged['operation_id'].encode()).hexdigest(); journal_path = journal_dir/(key+'.json')
        journal = load_project(journal_path) if journal_path.exists() else None
        if journal and journal['edit_signature'] != staged['edit_signature']: raise ValueError('İşlem kimliği başka içerikle kaydedilmiş.')
        if journal and journal['state'] == 'committed':
            _, row = find_variant(project, journal['variant']['id'])
            if sha256(safe_path(root, row['source']['path'])) != row['source']['sha256']: raise ValueError('Kaydedilmiş varlık sonradan değişmiş.')
            return {'status':'passed','variant_id':row['id'],'idempotent':True}
        edit = staged['edit']; design, parent = find_variant(project, edit['parent_id'])
        if design['id'] != edit['design_id']: raise ValueError('Ebeveyn tasarım uyuşmazlığı.')
        if parent['source']['sha256'] != edit['original_sha256'] or sha256(safe_path(root,parent['source']['path'])) != edit['original_sha256']:
            raise ValueError('Düzenleme eski ebeveyn kaynağına bağlı.')
        if is_technical_pilot(project) and not pilot_allows(project,parent,edit['operation']['kind']):
            raise ValueError('Teknik deney için işleme ve kaynağa bağlı yetki gerekli.')
        asset = Path(staged['asset_path'])
        if not asset.is_file() or sha256(asset) != staged['asset_sha256']: raise ValueError('Staging varlığı/hash bozuk.')
        if not journal:
            reserved = [v['number'] for v in design['variants']]
            for path in journal_dir.glob('*.json'):
                pending = load_project(path)
                if pending.get('design_id') == design['id']: reserved.append(pending['variant']['number'])
            number = max(reserved, default=0)+1
            row = copy.deepcopy(parent); row.update(id=f"{design['id']}-v{number}", number=number, parent_id=parent['id'], artifacts=[])
            for key in ('canva','approval','generation','technical_pilot'):
                row.pop(key,None)
            if is_technical_pilot(project):
                row['selection'] = {'status':'candidate','note':'İzole teknik deney.'}
            else:
                row['selection'] = {'status':'selected','evidence':parent['selection']['evidence'], 'note':'Yetkili revizyon; nihai estetik onay aktarılmadı.'}
                if parent['selection'].get('protected_components'):
                    row['selection']['protected_components'] = parent['selection']['protected_components']
            relative = f"variants/{hashlib.sha256(design['id'].encode()).hexdigest()[:16]}/v{number}/source{asset.suffix}"
            row['source'] = {'path':relative,'sha256':staged['asset_sha256'],'kind':edit['source']['kind']}
            row['operation'] = edit['operation']
            if edit['operation']['kind'] == 'canvas':
                row['canvas'] = {k:edit['operation']['parameters'][k] for k in ['width','height']}
            if edit['operation'].get('color_roles'): row['colors'].update(edit['operation']['color_roles'])
            journal = {'state':'prepared','edit_signature':staged['edit_signature'],'design_id':design['id'],'variant':row}
            atomic_json(journal_path, journal)
        row = journal['variant']; destination = safe_path(root, row['source']['path'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256(destination) != staged['asset_sha256']: raise ValueError('Varyant yolu başka içerikle dolu.')
        else:_publish_asset(asset,destination,staged['asset_sha256'])
        if _fail_after_move: raise RuntimeError('Test kesintisi: varlık taşındı, kayıt henüz değişmedi.')
        existing = [v for v in design['variants'] if v['id'] == row['id']]
        if not existing: design['variants'].append(row)
        elif existing != [row]: raise ValueError('Varyant kimliği çakışıyor.')
        check = validate_project(project, root)
        if check['errors']: raise ValueError('Yeni kayıt doğrulanamadı: '+str(check['errors']))
        atomic_json(project_path, project)
        journal['state']='committed'; atomic_json(journal_path, journal)
        return {'status':'passed','variant_id':row['id'],'idempotent':False,'source':row['source']}

def register_artifact(project_path, variant_id, artifact):
    project_path = Path(project_path)
    with project_lock(project_path):
        project = load_project(project_path); _, row = find_variant(project, variant_id)
        path = safe_path(project_path.parent, artifact['path'])
        if not path.is_file() or sha256(path) != artifact['sha256']: raise ValueError('Çıktı/hash uyuşmazlığı.')
        for old in row.get('artifacts', []):
            if old['path'] == artifact['path']:
                if old != artifact: raise ValueError('Eski çıktı kaydı üzerine yazılamaz; yeni yol kullan.')
                return {'status':'passed','idempotent':True}
        observed = inspect_asset(path)
        conflicts = declaration_conflicts(artifact, observed)
        if observed['status'] != 'measured' or conflicts:
            raise ValueError('Çıktı metadata doğrulanamadı. '+json.dumps({'conflicts':conflicts,'observed':observed},ensure_ascii=False))
        row.setdefault('artifacts', []).append(artifact); atomic_json(project_path, project)
    return {'status':'passed','variant_id':variant_id,'observed':observed}


def _panel_preview(variant, measurements):
    """Choose a portable image using the desktop tile's fitted display size."""
    rasters, vectors = [], []
    for record in [*variant.get('artifacts', []), variant['source']]:
        path = record['path']
        observed = measurements.get(path, {})
        preview_role = record.get('role') in {'preview', 'panel_preview'}
        if observed.get('format') == 'svg' and observed['kind'] == 'vector' and not observed['live_text']:
            vectors.append((preview_role, path))
        if observed.get('format') not in {'png', 'jpeg', 'webp'} or not observed.get('visible_bbox'):
            continue
        width, height = observed['size']
        x0, y0, x1, y1 = observed['visible_bbox']
        scale = min(560 / width, 360 / height)
        displayed_mark = max(x1 - x0, y1 - y0) * scale
        adequate = scale <= 1 and displayed_mark >= 72
        rasters.append((adequate, preview_role if adequate else False, min(1, 1/scale), displayed_mark, path))
    best = max(rasters, default=None)
    if best and best[0]:
        return best[-1], None
    if vectors:
        return max(vectors)[-1], None
    if best:
        return best[-1], 'Eldeki önizleme, sunum kutusu için düşük çözünürlüklü veya çizim alanı küçük.'
    return None, 'Paylaşılabilir önizleme için görünür bir raster çıktı veya konturlu SVG gerekli.'


def _generate_panel_preview(variant, stage, measurements):
    source = variant['source']['path']
    observed = measurements.get(source, {})
    if variant['selection']['status'] not in {'selected', 'approved'} or observed.get('kind') != 'vector':
        return None, None
    if not (os.environ.get('LOGO_INKSCAPE') or shutil.which('inkscape.com') or shutil.which('inkscape')):
        return None, 'Önizleme render aracı bulunamadı.'
    size = observed.get('size')
    if not size and observed.get('view_box'):
        try:
            size = [float(value) for value in re.split(r'[,\s]+', observed['view_box'].strip())][2:]
        except ValueError:
            size = None
    if not size or len(size) != 2 or not all(0 < value < float('inf') for value in size):
        return None, 'Vektör kaynakta önizleme için tuval oranı çözümlenemedi.'
    width, height = size
    scale = 768 / max(width, height)
    font_specs = {}
    for component in variant.get('components', []):
        spec = component.get('font')
        if component.get('kind') == 'live_text' and spec and component.get('svg_id'):
            font_specs[component['svg_id']] = {**spec, **({'path':stage/spec['path']} if spec.get('path') else {})}
    preview_key = hashlib.sha256((variant['id'] + ':' + sha256(stage/source)).encode()).hexdigest()
    path = stage/'assets'/f'preview-{preview_key}.png'
    try:
        if not path.exists():
            render_svg(stage/source, path, max(1, round(width*scale)), max(1, round(height*scale)), dict(os.environ), font_specs=font_specs)
        if not inspect_asset(path).get('visible_bbox'):
            return None, 'Renderer görünür logo içeren bir önizleme üretmedi.'
    except (OSError, ValueError) as exc:
        return None, 'Kaynak önizlemesi üretilemedi. '+str(exc)
    return path.relative_to(stage).as_posix(), None


def build_outputs(project: dict, output_dir: Path, kinds: list[str]) -> dict:
    if set(kinds)-{'inventory','panel','package'}: raise ValueError('Bilinmeyen çıktı türü.')
    root = Path(project['_root']); report = validate_project(project, root)
    if report['errors']: raise ValueError('Çıktıdan önce proje doğrulanmalı: '+str(report['errors']))
    for _,variant in variants(project):
        for component in variant.get('components',[]):
            font=component.get('font') or {}
            if font.get('path'):
                permission=font.get('redistribution') or {}
                if not isinstance(permission,dict) or permission.get('allowed') is not True or not permission.get('evidence') or not font.get('license_file') or str(font.get('license','')).casefold() in ['no-redistribution','unknown','restricted']:
                    raise ValueError('Font dağıtımı için doğrulanmış license_file ve redistribution:{allowed:true,evidence:...} gerekli; aksi halde konturlu/raster teslim kullan.')
    for asset in report['assets']:
        if asset.get('observed', {}).get('format') == 'svg':
            check=audit_svg(Path(asset['path']))
            if check['errors'] or any(r['kind']=='external' for r in check['references']):
                raise ValueError('Paketlemeden önce SVG dış bağımlılıklarını göm veya bağımsızlaştır; URI otomatik yeniden yazılmaz.')
    output_dir = Path(output_dir)
    if output_dir.exists(): raise ValueError('Çıktı dizini yeni olmalı.')
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.logo-output-', dir=output_dir.parent) as folder:
        stage = Path(folder)/'delivery'; stage.mkdir(); (stage/'assets').mkdir()
        portable = copy.deepcopy({k:v for k,v in project.items() if k != '_root'}); mapping = {}
        measurements = {}
        for asset in report['assets']:
            path = Path(asset['path'])
            observed = asset.get('observed')
            actual_format = (observed or {}).get('format')
            suffix = f'.{actual_format}' if actual_format else path.suffix.lower()
            relative = f"assets/{asset['sha256']}{suffix}"
            if not (stage/relative).exists(): shutil.copyfile(path, stage/relative)
            mapping[str(path.resolve())] = relative
            if observed:
                measurements[relative] = observed
        def rewrite(value):
            if isinstance(value, dict):
                if 'path' in value and 'sha256' in value:
                    value['path'] = mapping[str(safe_path(root,value['path']))]
                for child in value.values(): rewrite(child)
            elif isinstance(value, list):
                for child in value: rewrite(child)
        rewrite(portable); write_json(stage/'project.json', portable)
        if validate_project(portable,stage)['errors']:raise ValueError('Taşınabilir model doğrulanamadı.')
        active = [{'design_id':d['id'],'variant_id':v['id']} for d,v in variants(portable) if not is_technical_pilot(portable) and v['active'] and v['selection']['status'] != 'rejected']
        active_ids = {row['variant_id'] for row in active}
        write_json(stage/'active.json', active)
        panel_warnings = []
        if 'panel' in kinds or 'package' in kinds:
            cards = []
            for d in portable['designs']:
                views = []
                for v in d['variants']:
                    if v['id'] not in active_ids: continue
                    preview, warning = _panel_preview(v, measurements)
                    if warning:
                        generated, detail = _generate_panel_preview(v, stage, measurements)
                        if generated:
                            preview, warning = generated, None
                        elif detail:
                            warning += ' '+detail
                    label = html.escape(f"{v['id']} · varyant {v['number']}")
                    image = f'<img loading="lazy" src="{html.escape(preview,quote=True)}" alt="{label}">' if preview else ''
                    note = f'<p>{html.escape(warning)}</p>' if warning else ''
                    if warning:
                        panel_warnings.append({'variant_id':v['id'], 'message':warning, 'preview':preview})
                    views.append(f'<figure><div class="art">{image}</div><figcaption>{label}{note}</figcaption></figure>')
                if views: cards.append(f'<section><h2>{html.escape(d.get("name",d["id"]))}</h2><div class="views">'+''.join(views)+'</div></section>')
            title = html.escape(portable['brand']['name'])
            css = 'body{margin:0;background:#eef1f5;color:#182739;font:16px system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:40px 24px}h1{font-size:36px;letter-spacing:-1px}header{margin-bottom:36px}section{margin:24px 0;background:white;border:1px solid #dbe2eb;border-radius:18px;padding:24px}h2{font-size:20px;margin:0 0 20px}.views{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}figure{margin:0;min-width:0}.art{height:360px;border:1px solid #e7ebf0;border-radius:12px;background:white}.art img{display:block;width:100%;height:100%;object-fit:contain}figcaption{padding:14px 4px;font-size:14px;color:#4d6075;overflow-wrap:anywhere}@media(max-width:650px){main{padding:24px 12px}section{padding:14px}.views{gap:12px}.art{height:210px}h1{font-size:28px}}@media(max-width:400px){.art{height:170px}}'
            document = f'<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} — karşılaştırma</title><style>{css}</style><main><header><h1>{title}</h1><p>Logo tasarımları · yan yana karşılaştırma</p></header>'+''.join(cards)+'</main></html>'
            (stage/'index.html').write_text(document, encoding='utf-8')
        hashes = {str(p.relative_to(stage)).replace('\\','/'):sha256(p) for p in stage.rglob('*') if p.is_file()}
        write_json(stage/'manifest.json', {'schema_version':1,'project_id':portable['project_id'],'files':hashes})
        crc = None
        if 'package' in kinds:
            with zipfile.ZipFile(stage/'package.zip','w',zipfile.ZIP_DEFLATED) as archive:
                for path in stage.rglob('*'):
                    if path.is_file() and path.name != 'package.zip': archive.write(path,str(path.relative_to(stage)))
            with zipfile.ZipFile(stage/'package.zip') as archive:
                if archive.testzip() is not None: raise ValueError('ZIP CRC doğrulaması başarısız.')
                with tempfile.TemporaryDirectory(prefix='logo-package-verify-') as extracted:
                    archive.extractall(extracted)
                    extracted=Path(extracted)
                    check=validate_project(load_project(extracted/'project.json'),extracted)
                    if check['errors']:raise ValueError('Açılan ZIP model/varlık doğrulaması başarısız.')
                    if any(sha256(extracted/name)!=digest for name,digest in hashes.items()):raise ValueError('Açılan ZIP hash uyuşmazlığı.')
            crc = 'passed'
        os.replace(stage, output_dir)
    return {'status':'passed','path':str(output_dir.resolve()),'active_count':len(active),'files':hashes,'zip_crc':crc,
            'panel_warnings':panel_warnings,'publication':'not_requested_not_performed'}
