"""Optional generation and isolated technical-test records for schema version one."""
import re


def is_technical_pilot(project):
    return project.get('purpose') == 'technical_pilot'


def pilot_allows(project, variant, operation):
    record = variant.get('technical_pilot')
    return (operation in ('recolor','scale','layout','canvas') and is_technical_pilot(project) and isinstance(record,dict)
            and bool(project.get('project_id')) and record.get('project_id') == project.get('project_id')
            and record.get('variant_id') == variant.get('id') and record.get('source_sha256') == variant['source'].get('sha256')
            and bool(record.get('evidence')) and isinstance(record.get('operations'),list) and operation in record['operations'])


def generation_errors(record):
    if not isinstance(record,dict):
        return ['generation kaydı nesne olmalı.']
    errors = []
    for key in ('tool','observed_at','prompt'):
        if not isinstance(record.get(key),str) or not record[key].strip():
            errors.append(key+' gerekli.')
    for key in ('requested','submitted','returned','output'):
        if not isinstance(record.get(key),dict):
            errors.append(key+' nesne olmalı.')
    references = record.get('references', [])
    if not isinstance(references,list) or any(not isinstance(ref,dict) or not isinstance(ref.get('sha256'),str) or
                                               not re.fullmatch(r'[0-9a-f]{64}',ref['sha256']) for ref in references):
        errors.append('Her üretim referansı geçerli SHA-256 taşımalı.')
    if errors:
        return errors
    capability = record.get('capability')
    if capability is not None:
        if (not isinstance(capability,dict) or not isinstance(capability.get('schema_parameters'),list)
                or any(not isinstance(item,str) for item in capability['schema_parameters']) or not capability.get('schema_evidence')):
            errors.append('Yeteneğin şema kanıtı ve parametre listesi gerekli.')
        elif set(record['submitted']) - set(capability['schema_parameters']):
            errors.append('Gönderilen parametre, gözlenen araç şemasında yok.')
    if not record['output'].get('path') or not record['output'].get('sha256'):
        errors.append('Üretim çıktısının dosya ve hash kaydı gerekli.')
    return errors
