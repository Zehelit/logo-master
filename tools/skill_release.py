"""Build and verify byte-preserving skill releases from exact Git commits."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile

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
def make_manifest(payload,commit,version):
 return {'schema_version':1,'name':'logo-master','repository':REPOSITORY,'version':version,'source_commit':commit,'files':{n:digest(b) for n,b in sorted(payload.items())}}
def inspect_package(package,expected_commit):
 if not COMMIT.fullmatch(expected_commit):raise ValueError('Tam commit SHA gerekli.')
 try:
  with zipfile.ZipFile(package) as archive:
   infos=archive.infolist();names=[safe_name(i.filename) for i in infos]
   if len(names)!=len(set(n.casefold() for n in names)):raise ValueError('Yinelenen/arşiv harf çakışması.')
   if sum(i.file_size for i in infos)>20_000_000 or any((i.external_attr>>16)&0o170000==0o120000 for i in infos):raise ValueError('Paket boyutu veya link desteklenmiyor.')
   if 'manifest.json' not in names:raise ValueError('Manifest eksik.')
   manifest=json.loads(archive.read('manifest.json'))
   if not isinstance(manifest,dict) or manifest.get('schema_version')!=1 or manifest.get('name')!='logo-master' or manifest.get('repository')!=REPOSITORY or manifest.get('source_commit')!=expected_commit:raise ValueError('Manifest/commit uyuşmazlığı.')
   version=valid_version(manifest.get('version',''));files=manifest.get('files')
   if not isinstance(files,dict) or not files or len(files)!=len(set(n.casefold() for n in files)):raise ValueError('Manifest dosyaları geçersiz.')
   for name,sha in files.items():
    safe_name(name)
    if ignored(name) or not re.fullmatch('[0-9a-f]{64}',str(sha)):raise ValueError('Manifest dosya/hash geçersiz.')
   if set(names)!={'manifest.json'}|{PREFIX+n for n in files}:raise ValueError('Manifest dışı veya eksik dosya.')
   payload={n:archive.read(PREFIX+n) for n in files}
   if any(digest(payload[n])!=sha for n,sha in files.items()):raise ValueError('Paket hash uyuşmazlığı.')
   if valid_version(payload['VERSION'].decode('utf-8').strip())!=version or 'SKILL.md' not in payload:raise ValueError('Paket VERSION uyuşmazlığı.')
   return manifest,payload
 except (zipfile.BadZipFile,KeyError,UnicodeError,TypeError,json.JSONDecodeError) as exc:raise ValueError('Paket okunamadı: '+str(exc)) from exc
def verify_release(package:Path,expected_commit:str)->dict:
 manifest,_=inspect_package(Path(package),expected_commit)
 return {'status':'passed','version':manifest['version'],'commit':expected_commit,'files_checked':len(manifest['files']),'manifest':manifest}
def build_release(repo:Path,commit:str,out:Path)->dict:
 payload=committed_payload(Path(repo),commit)
 try:version=valid_version(payload['VERSION'].decode('utf-8').strip())
 except KeyError as exc:raise ValueError('VERSION eksik.') from exc
 manifest=make_manifest(payload,commit,version);out=Path(out)
 if out.exists():raise ValueError('Yeni çıktı dizini gerekli.')
 out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.release-',dir=out.parent) as temporary:
  stage=Path(temporary)/'release';stage.mkdir();name='logo-master-'+version+'.zip';package=stage/name
  entries={'manifest.json':canonical(manifest),**{PREFIX+n:b for n,b in payload.items()}}
  with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED) as archive:
   for n,b in sorted(entries.items()):
    info=zipfile.ZipInfo(n,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;archive.writestr(info,b)
  verify_release(package,commit)
  (stage/'SHA256SUMS').write_text(digest(package.read_bytes())+'  '+name+'\n',encoding='ascii')
  os.replace(stage,out)
 return {'status':'passed','version':version,'commit':commit,'files_checked':len(payload),'package':str(out/name),'sums':str(out/'SHA256SUMS')}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--commit',required=True);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();print(json.dumps(build_release(a.repo,a.commit,a.out),ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
