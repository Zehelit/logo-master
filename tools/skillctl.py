"""Explicit Windows skill installation management; no background updates."""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from skill_source import (COMMIT,REPOSITORY,canonical,committed_payload,digest,
                         git,ignored,load_source,safe_name,valid_version,validate_tag)

class RecoveryRequired(RuntimeError):pass
def now():return datetime.now(timezone.utc).isoformat()
def checkpoint(name):pass
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def atomic_json(path,data):
 path=Path(path);temporary=path.with_name(path.name+'.tmp')
 with temporary.open('wb') as f:f.write(canonical(data));f.flush();os.fsync(f.fileno())
 os.replace(temporary,path)
def reject_links(path):
 for p in [Path(path),*Path(path).parents]:
  if p.is_symlink() or p.is_junction():raise ValueError('Link/junction yolu desteklenmiyor: '+str(p))
def locations(target,state):
 target=Path(target).absolute();state=Path(state).absolute()
 reject_links(target);reject_links(state)
 if target.name!='logo-master' or target==state or target in state.parents or state in target.parents or target.anchor.casefold()!=state.anchor.casefold():raise ValueError('Hedef ve state aynı diskte ayrı kökler olmalı.')
 return target,state
def tree(root):
 root=Path(root);reject_links(root)
 if not root.is_dir():raise ValueError('Kurulum klasörü yok: '+str(root))
 result={}
 for p in sorted(root.rglob('*')):
  if p.is_symlink() or p.is_junction():raise ValueError('Kurulumda link/junction var.')
  if p.is_file():
   name=p.relative_to(root).as_posix();safe_name(name)
   if not ignored(name):result[name]=digest(p.read_bytes())
 return result
def record_valid(record):
 if not isinstance(record,dict) or record.get('schema_version')!=1 or record.get('repository')!=REPOSITORY or not COMMIT.fullmatch(str(record.get('commit',''))):raise ValueError('Kurulum makbuzu geçersiz.')
 if record.get('version') is None:
  if record.get('state')!='legacy_baseline':raise ValueError('Bilinmeyen sürüm.')
 else:valid_version(record['version'])
 files=record.get('files')
 if not isinstance(files,dict) or not files or len(files)!=len(set(n.casefold() for n in files)):raise ValueError('Makbuz dosya listesi geçersiz.')
 for name,sha in files.items():
  safe_name(name)
  if ignored(name) or len(str(sha))!=64 or any(c not in '0123456789abcdef' for c in str(sha)):raise ValueError('Makbuz hash/yol geçersiz.')
 if 'SKILL.md' not in files or (record.get('version') is not None and 'VERSION' not in files):raise ValueError('Makbuz kaynakları eksik.')
 return record
def current_record(receipt):return {k:v for k,v in receipt.items() if k!='previous'}
def matches(path,record):return Path(path).is_dir() and tree(path)==record_valid(record)['files']
def assert_matches(path,record):
 if not matches(path,record):raise ValueError('Kaynak dosya kümesi/hash uyuşmazlığı: '+str(path))
def inspect_install(target:Path,state_root:Path,details=False)->dict:
 try:
  target,state=locations(target,state_root)
  if (state/'journal.json').exists() or any((state/n).exists() for n in ('staging','outgoing','retired')):return {'status':'recovery_required','version':None,'commit':None}
  if not (state/'receipt.json').exists():
   if (state/'previous').exists():raise ValueError('Makbuzsuz previous klasörü; korunuyor.')
   return {'status':'unmanaged','version':None,'commit':None,'exists':target.exists()}
  receipt=record_valid(read(state/'receipt.json'));actual=tree(target) if target.exists() else {};expected=receipt['files']
  differences={'added':sorted(actual.keys()-expected.keys()),'missing':sorted(expected.keys()-actual.keys()),'changed':sorted(n for n in actual.keys()&expected.keys() if actual[n]!=expected[n])}
  previous=receipt.get('previous')
  if previous:
   if not matches(state/'previous',previous):raise ValueError('Önceki kurulum değişmiş veya eksik.')
  elif (state/'previous').exists():raise ValueError('Sahipsiz previous klasörü.')
  status='modified' if any(differences.values()) else 'clean'
  if status=='clean' and receipt['version'] is not None and (target/'VERSION').read_text(encoding='utf-8').strip()!=receipt['version']:raise ValueError('Makbuz VERSION ile uyuşmuyor.')
  result={'status':status,'version':receipt['version'],'commit':receipt['commit'],'files_checked':len(actual),'difference_counts':{k:len(v) for k,v in differences.items()}}
  if details:result['differences']=differences
  return result
 except (ValueError,OSError,TypeError,KeyError) as e:return {'status':'invalid','version':None,'commit':None,'error':str(e)[:300]}

@contextmanager
def installation_lock(state):
 state=Path(state);reject_links(state);state.mkdir(parents=True,exist_ok=True)
 import msvcrt
 with (state/'install.lock').open('a+b') as f:
  f.seek(0,os.SEEK_END)
  if not f.tell():f.write(b'0');f.flush()
  f.seek(0)
  try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
  except OSError as e:raise ValueError('Başka kurulum işlemi kilidi tutuyor.') from e
  try:yield
  finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

def remove_owned(path,state,record,partial=False):
 path=Path(path);state=Path(state)
 reject_links(path)
 if path.parent.resolve()!=state.resolve() or path.name not in ('staging','retired'):raise ValueError('Temizlik yolu izinli state sınırı dışında.')
 if not path.exists():return
 actual=tree(path)
 if partial:
  if set(actual)-set(record_valid(record)['files']):raise ValueError('Staging içinde bilinmeyen dosya; korunuyor.')
 else:assert_matches(path,record)
 shutil.rmtree(path)
def candidate_checks(path,record):
 assert_matches(path,record)
 if record['version'] is not None:
  if (path/'VERSION').read_text(encoding='utf-8').strip()!=record['version']:raise ValueError('Kurulum VERSION uyuşmazlığı.')
  if (path/'scripts/logo.py').exists():
   p=subprocess.run([sys.executable,str(path/'scripts/logo.py'),'--version'],capture_output=True,text=True,encoding='utf-8')
   if p.returncode or p.stdout.strip()!=record['version']:raise ValueError('Aday CLI doğrulanamadı: '+p.stderr[-300:])
def finish(target,state,journal):
 new=record_valid(journal['new']);old=journal['old'];prior=old.get('previous') if old else None
 previous=state/'previous';retired=state/'retired';outgoing=state/'outgoing';stage=state/'staging'
 if target.exists() and not matches(target,new):
  if not old or outgoing.exists():raise RecoveryRequired('Canlı hedef beklenmeyen durumda; dosyalar korunuyor.')
  assert_matches(target,old)
  if prior:
   if previous.exists():
    assert_matches(previous,prior)
    if retired.exists():raise RecoveryRequired('Hem previous hem retired mevcut; inceleme gerekli.')
    previous.rename(retired)
   elif not matches(retired,prior):raise RecoveryRequired('Önceki kopya bulunamadı.')
  elif previous.exists() or retired.exists():raise RecoveryRequired('Beklenmeyen önceki kopya.')
  target.rename(outgoing);checkpoint('after_old_move')
 if not target.exists():
  if old:assert_matches(outgoing,old)
  candidate_checks(stage,new);stage.rename(target);checkpoint('after_new_move')
 candidate_checks(target,new)
 if old:
  if outgoing.exists():assert_matches(outgoing,old)
  elif not matches(previous,old):raise RecoveryRequired('Geri dönüş kopyası bulunamadı.')
 new_receipt={**new,'previous':current_record(old) if old else None}
 atomic_json(state/'receipt.json',new_receipt);checkpoint('after_receipt')
 if outgoing.exists():
  if previous.exists():raise RecoveryRequired('Previous hedefi dolu; üzerine yazılmadı.')
  outgoing.rename(previous)
 if retired.exists():
  if not prior:raise RecoveryRequired('Retired sahipliği belirsiz.')
  remove_owned(retired,state,prior)
 (state/'journal.json').unlink()
 return {'status':'passed','version':new['version'],'commit':new['commit'],'files_checked':len(new['files']),'noop':False}
def transaction(payload,new,target,state,old,had_receipt):
 journal={'schema_version':1,'phase':'preparing','new':new,'old':old,'had_receipt':had_receipt}
 atomic_json(state/'journal.json',journal);stage=state/'staging';stage.mkdir()
 for name,data in payload.items():
  p=stage/safe_name(name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);checkpoint('during_staging')
 candidate_checks(stage,new);journal['phase']='ready';atomic_json(state/'journal.json',journal);checkpoint('after_staging')
 return finish(target,state,journal)
def preflight(target,state):
 status=inspect_install(target,state)
 if status['status'] in ('recovery_required','invalid','modified'):raise ValueError('Kurulum önkoşulu sağlanmadı: '+json.dumps(status,ensure_ascii=False))
 return status
def install_source(source:dict,target:Path,state_root:Path,*,adopt_baseline=None)->dict:
 target,state=locations(target,state_root)
 expected=source['commit'];payload=source['payload']
 manifest=record_valid({'schema_version':1,'repository':REPOSITORY,'version':source['version'],'commit':expected,'files':source['files']})
 if not isinstance(payload,dict) or set(payload)!=set(manifest['files']):raise ValueError('Commit dosya listesi uyuşmazlığı.')
 if any(not isinstance(data,bytes) or digest(data)!=manifest['files'][name] for name,data in payload.items()):raise ValueError('Commit dosya hash uyuşmazlığı.')
 if payload['VERSION'].decode('utf-8').strip()!=manifest['version']:raise ValueError('Commit VERSION uyuşmazlığı.')
 with installation_lock(state):
  status=preflight(target,state);had_receipt=(state/'receipt.json').exists();old=read(state/'receipt.json') if had_receipt else None
  if target.exists() and not old:
   if adopt_baseline is None:raise ValueError('Yönetilmeyen kurulum; exact baseline ile açık benimseme gerekli.')
   old={**record_valid(adopt_baseline),'installed_at':now(),'previous':None};assert_matches(target,old)
   if (state/'previous').exists():raise ValueError('Sahipsiz previous korunuyor.')
  if old and old['commit']==expected:
   if old['files']!=manifest['files'] or old['version']!=manifest['version']:raise ValueError('Aynı commit farklı payload taşıyor.')
   return {'status':'passed','version':old['version'],'commit':expected,'files_checked':len(old['files']),'noop':True}
  new={'schema_version':1,'repository':REPOSITORY,'version':manifest['version'],'commit':expected,'files':manifest['files'],'installed_at':now()}
  target.parent.mkdir(parents=True,exist_ok=True)
  return transaction(payload,new,target,state,old,had_receipt)
def rollback_install(target:Path,state_root:Path)->dict:
 target,state=locations(target,state_root)
 with installation_lock(state):
  if preflight(target,state)['status']!='clean':raise ValueError('Temiz yönetilen kurulum gerekli.')
  old=read(state/'receipt.json');previous=old.get('previous')
  if not previous:raise ValueError('Geri dönüş kopyası yok.')
  assert_matches(state/'previous',previous)
  payload={n:(state/'previous'/n).read_bytes() for n in previous['files']}
  new={**current_record(previous),'installed_at':now()}
  return transaction(payload,new,target,state,old,True)
def recover_install(target:Path,state_root:Path)->dict:
 target,state=locations(target,state_root)
 with installation_lock(state):
  if not (state/'journal.json').exists():
   result=inspect_install(target,state)
   if result['status'] in ('invalid','recovery_required'):raise RecoveryRequired('Journal olmadan kalan state; manuel inceleme gerekli.')
   return {**result,'noop':True}
  journal=read(state/'journal.json')
  if journal.get('schema_version')!=1 or journal.get('phase') not in ('preparing','ready'):raise RecoveryRequired('Journal geçersiz; korunuyor.')
  record_valid(journal['new'])
  if journal['phase']=='preparing':
   if journal['old']:assert_matches(target,journal['old'])
   elif target.exists():raise RecoveryRequired('Beklenmeyen canlı hedef.')
   remove_owned(state/'staging',state,journal['new'],partial=True)
   if journal['had_receipt']:atomic_json(state/'receipt.json',journal['old'])
   (state/'journal.json').unlink()
   return {**inspect_install(target,state),'recovered':'old_installation'}
  return finish(target,state,journal)

def install_from_repo(repo:Path,ref:str,target:Path,state_root:Path,*,adopt_baseline=None,tag=None)->dict:
 origin=git(repo,'remote','get-url','origin').decode('utf-8').strip()
 if origin not in ('https://github.com/'+REPOSITORY,'https://github.com/'+REPOSITORY+'.git','git@github.com:'+REPOSITORY+'.git','ssh://git@github.com/'+REPOSITORY+'.git'):raise ValueError('Beklenmeyen origin: '+origin)
 source=load_source(repo,ref)
 if tag is not None:validate_tag(tag,source['version'])
 return install_source(source,target,state_root,adopt_baseline=adopt_baseline)

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 s=sub.add_parser('status');s.add_argument('--details',action='store_true')
 s=sub.add_parser('install');refs=s.add_mutually_exclusive_group();refs.add_argument('--ref',help='Yerel HEAD, tag veya commit (varsayılan: HEAD)');refs.add_argument('--tag',help='Uyumlu eski seçenek; tag VERSION ile eşleşmeli');s.add_argument('--adopt-baseline')
 sub.add_parser('rollback');sub.add_parser('recover');args=p.parse_args(argv)
 home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))).expanduser()
 target=home/'skills/logo-master';state=home/'skill-installations/logo-master';repo=Path(__file__).resolve().parents[1]
 try:
  if not home.is_absolute():raise ValueError('CODEX_HOME mutlak bir klasör yolu olmalı.')
  if args.command=='status':result=inspect_install(target,state,args.details)
  elif args.command=='rollback':result=rollback_install(target,state)
  elif args.command=='recover':result=recover_install(target,state)
  else:
   baseline=None
   if args.adopt_baseline:
    payload=committed_payload(repo,args.adopt_baseline)
    if 'VERSION' in payload:raise ValueError('Legacy baseline sürümlü olamaz.')
    baseline={'schema_version':1,'repository':REPOSITORY,'version':None,'commit':args.adopt_baseline,'files':{n:digest(b) for n,b in payload.items()},'state':'legacy_baseline'}
   result=install_from_repo(repo,args.tag or args.ref or 'HEAD',target,state,adopt_baseline=baseline,tag=args.tag)
  print(json.dumps(result,ensure_ascii=False));return 0
 except (ValueError,OSError,RuntimeError,KeyError,UnicodeError,subprocess.CalledProcessError) as exc:
  pending=(state/'journal.json').exists();print(json.dumps({'status':'recovery_required' if pending else 'failed','error':str(exc)[:1000]},ensure_ascii=False));return 3 if pending else 2
if __name__=='__main__':raise SystemExit(main())
