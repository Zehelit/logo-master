"""Validate Canva stage receipts and determine drift without changing either side."""
import re


STAGES = {'preflight':None, 'library_upload':'preflight', 'placement':'library_upload',
          'edit':'placement', 'save':'placement', 'download':'save',
          'file_inspection':'download', 'comparison':'file_inspection'}


def _digest(value):
    return isinstance(value,str) and bool(re.fullmatch(r'[a-f0-9]{64}',value))


def stage_errors(mapping, variant_id):
    if 'stage_receipts' not in mapping:
        return []
    receipts = mapping['stage_receipts']
    if not isinstance(receipts,list):
        return ['stage_receipts must be a list']
    previous = {}
    problems = []
    for row in receipts:
        if not isinstance(row,dict) or row.get('stage') not in STAGES:
            problems.append('unknown stage receipt')
            continue
        stage = row['stage']
        if (row.get('variant_id') != variant_id or not _digest(row.get('source_sha256')) or
                row.get('source_sha256') != mapping.get('source_sha256') or
                not isinstance(row.get('observed_at'),str) or not row['observed_at'] or
                not isinstance(row.get('evidence'),str) or not row['evidence'] or
                row.get('status') not in {'passed','failed','needs_review','not_run','not_applicable'}):
            problems.append(stage + ': missing evidence or mismatched variant/source')
            continue
        if row['status'] != 'passed':
            continue
        predecessor = STAGES[stage]
        if predecessor and predecessor not in previous:
            problems.append(stage + ': prior stage evidence missing')
        if stage != 'preflight' and (not row.get('design_id') or row['design_id'] != mapping.get('design_id')):
            problems.append(stage + ': design ID mismatch')
        if stage in {'placement','edit','save','download','file_inspection','comparison'}:
            if not row.get('page_id') or row['page_id'] != mapping.get('page_id'):
                problems.append(stage + ': page ID mismatch')
        if stage == 'library_upload' and row.get('upload_sha256') != mapping.get('source_sha256'):
            problems.append(stage + ': uploaded bytes differ from preflight')
        if stage in {'placement','edit'} and (not isinstance(row.get('element_ids'),list) or not row['element_ids']):
            problems.append(stage + ': observed element IDs missing')
        if stage == 'download' and not _digest(row.get('download_sha256')):
            problems.append(stage + ': actual downloaded file hash missing')
        if stage in {'file_inspection','comparison'} and row.get('download_sha256') != previous.get('download',{}).get('download_sha256'):
            problems.append(stage + ': result is not tied to downloaded file')
        previous[stage] = row
    return problems


def sync_state(mapping, local_sha256, remote_observation):
    base_local = mapping.get('source_sha256')
    base_remote = mapping.get('verified_canva_sha256')
    remote_hash = remote_observation.get('sha256')
    valid_remote = (bool(mapping.get('design_id')) and remote_observation.get('design_id') == mapping.get('design_id')
                    and bool(mapping.get('page_id')) and remote_observation.get('page_id') == mapping.get('page_id')
                    and bool(remote_observation.get('evidence')) and _digest(remote_hash) and _digest(base_remote))
    local_changed = local_sha256 != base_local if _digest(base_local) else None
    remote_changed = remote_hash != base_remote if valid_remote else None
    if remote_changed is None or local_changed is None:
        state = 'pending'
    elif local_changed and remote_changed:
        state = 'conflict'
    elif local_changed:
        state = 'local_changed'
    elif remote_changed:
        state = 'canva_changed'
    else:
        state = 'synced'
    return {'status':state,'local_changed':local_changed,'canva_changed':remote_changed,'local_sha256':local_sha256,
            'canva_sha256':remote_hash if valid_remote else None,'source_choice_required':state=='conflict'}
