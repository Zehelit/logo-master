"""Read exact committed skill bytes from a local Git checkout; no network access."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

PREFIX='skills/logo-master/'
REPOSITORY='Zehelit/logo-master'
COMMIT=re.compile(r'[0-9a-f]{40}')
VERSION=re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?')

def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
def valid_version(value):
 match=VERSION.fullmatch(value)
 if not match or (match.group(4) and any(x.isdigit() and len(x)>1 and x.startswith('0') for x in match.group(4).split('.'))):raise ValueError('Geçersiz SemVer.')
 return value
def read_version(skill_root:Path)->str:
 return valid_version((Path(skill_root)/'VERSION').read_text(encoding='utf-8').strip())
def validate_tag(tag,version):
 if tag!='v'+valid_version(version):raise ValueError('Tag ve VERSION uyuşmuyor.')
def safe_name(name):
 parts=PurePosixPath(name).parts
 reserved={'CON','PRN','AUX','NUL'}|{f'{x}{i}' for x in ['COM','LPT'] for i in range(1,10)}
 if not name or '\\' in name or ':' in name or '\x00' in name or name.startswith('/') or any(p in ('.','..') or p.endswith((' ','.')) or p.split('.')[0].upper() in reserved for p in parts) or '/'.join(parts)!=name:
  raise ValueError('Güvensiz paket yolu: '+name)
 return name
def ignored(name):
 return '__pycache__' in PurePosixPath(name).parts or name.endswith(('.pyc','.pyo'))
def git(repo,*args):
 p=subprocess.run(['git','-C',str(repo),*args],capture_output=True)
 if p.returncode:raise ValueError(p.stderr.decode('utf-8',errors='replace').strip())
 return p.stdout
def committed_payload(repo,commit):
 if not COMMIT.fullmatch(commit):raise ValueError('Tam commit SHA gerekli.')
 result={};seen=set()
 for row in git(repo,'ls-tree','-rz',commit,'--',PREFIX).split(b'\0'):
  if not row:continue
  meta,raw=row.split(b'\t',1);mode,kind,sha=meta.split();path=raw.decode('utf-8')
  name=safe_name(path[len(PREFIX):])
  if mode not in (b'100644',b'100755') or kind!=b'blob' or ignored(name) or '.git' in PurePosixPath(name).parts or name=='environment.local.json':raise ValueError('Desteklenmeyen paket dosyası: '+name)
  if name.casefold() in seen:raise ValueError('Büyük/küçük harf dosya çakışması.')
  seen.add(name.casefold());result[name]=git(repo,'cat-file','blob',sha.decode('ascii'))
 if not result or 'SKILL.md' not in result:raise ValueError('Skill ağacı eksik.')
 return result
def load_source(repo:Path,ref="HEAD")->dict:
 if not isinstance(ref,str) or not ref or ref.startswith('-'):raise ValueError('Geçersiz yerel Git referansı.')
 commit=git(repo,'rev-parse','--verify','--end-of-options',ref+'^{commit}').decode('ascii').strip()
 payload=committed_payload(repo,commit)
 try:version=valid_version(payload['VERSION'].decode('utf-8').strip())
 except (KeyError,UnicodeError) as exc:raise ValueError('Commit içinde geçerli VERSION gerekli.') from exc
 return {'version':version,'commit':commit,'payload':payload,'files':{n:digest(b) for n,b in sorted(payload.items())}}
