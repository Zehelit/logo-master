import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
try:
 import skill_release as release
except ImportError:
 release=None

class ReleaseTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
  self.skill=self.repo/'skills/logo-master';self.skill.mkdir(parents=True)
  (self.skill/'VERSION').write_bytes(b'1.0.0\n')
  (self.skill/'SKILL.md').write_bytes(b'name: logo-master\n')
  self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid');self.git('config','core.autocrlf','false')
  self.git('add','.');self.git('commit','-qm','fixture');self.commit=self.git('rev-parse','HEAD')
 def git(self,*args):return subprocess.check_output(['git',*args],cwd=self.repo,text=True).strip()
 def api(self):
  self.assertIsNotNone(release,'Release implementation missing')
  return release
 def pack(self):return self.api().build_release(self.repo,self.commit,self.root/'out')
 def test_cli_version_without_subcommand(self):
  p=subprocess.run([sys.executable,str(ROOT/'skills/logo-master/scripts/logo.py'),'--version'],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout.strip(),'1.0.0')
 def test_existing_help_unchanged(self):
  p=subprocess.run([sys.executable,str(ROOT/'skills/logo-master/scripts/logo.py'),'--help'],capture_output=True,text=True)
  self.assertEqual(p.returncode,0)
  for command in ['validate','audit','render','edit','outline','split','assemble','export','stage','commit','artifact','outputs','package']:self.assertIn(command,p.stdout)
 def test_invalid_version_rejected(self):
  for value in ['v1.0.0','01.0.0','1.0','../bad','1.0.0\n2.0.0']:
   (self.skill/'VERSION').write_text(value,encoding='utf-8')
   with self.assertRaises(ValueError):self.api().read_version(self.skill)
 def test_tag_version_mismatch(self):
  with self.assertRaises(ValueError):self.api().validate_tag('v2.0.0','1.0.0')
 def test_pack_uses_committed_tree_not_dirty_files(self):
  (self.skill/'SKILL.md').write_text('uncommitted',encoding='utf-8')
  result=self.pack()
  with zipfile.ZipFile(result['package']) as z:self.assertEqual(z.read('skills/logo-master/SKILL.md'),b'name: logo-master\n')
  self.assertEqual(self.api().verify_release(Path(result['package']),self.commit)['version'],'1.0.0')
 def test_tampered_bytes_rejected(self):
  result=self.pack();p=self.root/'bad.zip'
  with zipfile.ZipFile(result['package']) as src,zipfile.ZipFile(p,'w') as z:
   for name in src.namelist():z.writestr(name,b'bad' if name.endswith('SKILL.md') else src.read(name))
  with self.assertRaises(ValueError):self.api().verify_release(p,self.commit)
 def test_archive_escape_and_case_collision_rejected(self):
  result=self.pack()
  for extra in ['../escape','C:/escape','skills/logo-master/skill.md']:
   p=self.root/(hashlib.sha256(extra.encode()).hexdigest()+'.zip')
   with zipfile.ZipFile(result['package']) as src,zipfile.ZipFile(p,'w') as z:
    for name in src.namelist():z.writestr(name,src.read(name))
    z.writestr(extra,b'bad')
   with self.assertRaises(ValueError):self.api().verify_release(p,self.commit)
 def test_manifest_has_no_self_hash(self):
  result=self.pack()
  with zipfile.ZipFile(result['package']) as z:
   m=json.loads(z.read('manifest.json'));self.assertEqual(m['source_commit'],self.commit)
   self.assertNotIn('manifest.json',m['files']);self.assertEqual(set(z.namelist()),{'manifest.json'}|{'skills/logo-master/'+n for n in m['files']})
 def test_wrong_commit_and_extra_payload_rejected(self):
  result=self.pack()
  with self.assertRaises(ValueError):self.api().verify_release(Path(result['package']),'0'*40)
 def test_repeat_pack_is_byte_identical(self):
  a=self.pack();b=self.api().build_release(self.repo,self.commit,self.root/'second')
  self.assertEqual(Path(a['package']).read_bytes(),Path(b['package']).read_bytes())
 def test_tracked_cache_or_link_refused(self):
  (self.skill/'bad.pyc').write_bytes(b'cache');self.git('add','.');self.git('commit','-qm','bad')
  with self.assertRaises(ValueError):self.api().build_release(self.repo,self.git('rev-parse','HEAD'),self.root/'badout')
 def test_non_object_manifest_is_reported_as_invalid_package(self):
  p=self.root/'list-manifest.zip'
  with zipfile.ZipFile(p,'w') as z:z.writestr('manifest.json',b'[]')
  with self.assertRaises(ValueError):self.api().verify_release(p,self.commit)

if __name__=='__main__':unittest.main()
