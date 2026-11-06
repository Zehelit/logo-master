import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import skill_release as release
try:import skillctl as ctl
except ImportError:ctl=None

class InstallTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='logo-İş-');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.target=self.root/'skills/logo-master';self.state=self.root/'state'
  self.target.mkdir(parents=True);(self.target/'SKILL.md').write_bytes(b'legacy')
  self.baseline={'schema_version':1,'repository':release.REPOSITORY,'version':None,'commit':'0'*40,'files':{'SKILL.md':release.digest(b'legacy')},'state':'legacy_baseline'}
  self.a=self.package('1.0.0','1');self.b=self.package('1.1.0','2')
 def api(self):self.assertIsNotNone(ctl,'Installer implementation missing');return ctl
 def package(self,version,key):
  payload={'SKILL.md':('skill '+version).encode(),'VERSION':(version+'\n').encode()};m=release.make_manifest(payload,key*40,version)
  p=self.root/(version+'.zip')
  with zipfile.ZipFile(p,'w') as z:
   z.writestr('manifest.json',release.canonical(m))
   for n,b in payload.items():z.writestr(release.PREFIX+n,b)
  return p
 def adopt(self):return self.api().install_release(self.a,self.target,self.state,adopt_baseline=self.baseline)
 def status(self):return self.api().inspect_install(self.target,self.state)
 def test_unknown_unmanaged_install_refused(self):
  self.assertEqual(self.status()['status'],'unmanaged')
  with self.assertRaises(ValueError):self.api().install_release(self.a,self.target,self.state)
  self.assertEqual((self.target/'SKILL.md').read_bytes(),b'legacy')
 def test_explicit_legacy_adoption_requires_exact_baseline(self):
  (self.target/'extra.py').write_text('extra')
  with self.assertRaises(ValueError):self.adopt()
 def test_install_success_and_same_commit_noop(self):
  self.assertEqual(self.adopt()['status'],'passed');self.assertEqual(self.status()['status'],'clean')
  receipt=(self.state/'receipt.json').read_bytes()
  result=self.api().install_release(self.a,self.target,self.state)
  self.assertTrue(result['noop']);self.assertEqual(receipt,(self.state/'receipt.json').read_bytes())
 def test_modified_missing_and_extra_are_refused(self):
  self.adopt();original=(self.target/'SKILL.md').read_bytes()
  for kind in ['changed','missing','extra']:
   with self.subTest(kind=kind):
    if kind=='changed':(self.target/'SKILL.md').write_bytes(b'user edit')
    if kind=='missing':(self.target/'SKILL.md').unlink()
    if kind=='extra':(self.target/'extra.py').write_bytes(b'user edit')
    self.assertEqual(self.status()['status'],'modified')
    with self.assertRaises(ValueError):self.api().install_release(self.b,self.target,self.state)
    if kind=='extra':(self.target/'extra.py').unlink()
    else:(self.target/'SKILL.md').write_bytes(original)
 def test_cache_is_not_source_modification(self):
  self.adopt();cache=self.target/'__pycache__';cache.mkdir();(cache/'x.pyc').write_bytes(b'cache')
  self.assertEqual(self.status()['status'],'clean')
 def test_one_previous_only(self):
  self.adopt();self.api().install_release(self.b,self.target,self.state)
  self.assertEqual((self.state/'previous/VERSION').read_text().strip(),'1.0.0')
  self.assertFalse((self.state/'retired').exists());self.assertFalse((self.state/'outgoing').exists());self.assertFalse((self.state/'staging').exists())
 def test_dirty_rollback_preserves_changes(self):
  self.adopt();(self.target/'SKILL.md').write_bytes(b'user edit')
  with self.assertRaises(ValueError):self.api().rollback_install(self.target,self.state)
  self.assertEqual((self.target/'SKILL.md').read_bytes(),b'user edit')
 def test_previous_tampering_is_refused(self):
  self.adopt();(self.state/'previous/SKILL.md').write_bytes(b'user edit')
  with self.assertRaises(ValueError):self.api().rollback_install(self.target,self.state)
  self.assertEqual((self.state/'previous/SKILL.md').read_bytes(),b'user edit')
 def test_rollback_and_reinstall_legacy(self):
  self.adopt();self.api().rollback_install(self.target,self.state)
  self.assertEqual((self.target/'SKILL.md').read_bytes(),b'legacy');self.assertIsNone(self.status()['version'])
  self.assertEqual(self.status()['status'],'clean')
  self.api().install_release(self.a,self.target,self.state)
  self.assertEqual(self.status()['version'],'1.0.0')
 def test_interrupted_phases_recover_idempotently(self):
  self.adopt()
  for point in ['after_staging','after_old_move','after_new_move','after_receipt']:
   with self.subTest(point=point):
    def crash(name):
     if name==point:raise RuntimeError('simulated interruption')
    with patch.object(self.api(),'checkpoint',side_effect=crash):
     with self.assertRaises(RuntimeError):self.api().install_release(self.b,self.target,self.state)
    self.assertEqual(self.status()['status'],'recovery_required')
    self.api().recover_install(self.target,self.state);self.assertEqual(self.status()['status'],'clean');self.assertEqual(self.status()['version'],'1.1.0')
    receipt=(self.state/'receipt.json').read_bytes();self.api().recover_install(self.target,self.state)
    self.assertEqual(receipt,(self.state/'receipt.json').read_bytes())
    self.api().rollback_install(self.target,self.state)
 def test_prepare_failure_recovers_without_replacing_live_source(self):
  self.adopt()
  def crash(name):
   if name=='during_staging':raise RuntimeError('simulated interruption')
  with patch.object(self.api(),'checkpoint',side_effect=crash):
   with self.assertRaises(RuntimeError):self.api().install_release(self.b,self.target,self.state)
  self.api().recover_install(self.target,self.state);self.assertEqual(self.status()['version'],'1.0.0')
 def test_second_writer_refused(self):
  self.adopt()
  with self.api().installation_lock(self.state):
   with self.assertRaises(ValueError):self.api().install_release(self.b,self.target,self.state)
 def test_unicode_paths(self):
  self.adopt();self.assertEqual(self.status()['status'],'clean')
 def test_symlink_or_junction_target_refused(self):
  self.adopt();actual=self.root/'actual';self.target.rename(actual)
  p=subprocess.run(['cmd','/c','mklink','/J',str(self.target),str(actual)],capture_output=True)
  self.assertEqual(p.returncode,0,p.stderr)
  try:
   with self.assertRaises(ValueError):self.api().install_release(self.b,self.target,self.state)
  finally:self.target.rmdir();actual.rename(self.target)
 def test_short_status_and_details(self):
  self.adopt();summary=self.status();self.assertLessEqual(len(json.dumps(summary).encode('utf-8')),2048)
  self.assertNotIn('files',summary);self.assertIn('differences',self.api().inspect_install(self.target,self.state,details=True))
 def test_invalid_receipt_is_not_clean(self):
  self.adopt();(self.state/'receipt.json').write_text('{}')
  self.assertEqual(self.status()['status'],'invalid')
  with self.assertRaises(ValueError):self.api().install_release(self.b,self.target,self.state)
 def test_wrong_target_and_state_relationship_refused(self):
  with self.assertRaises(ValueError):self.api().install_release(self.a,self.target,self.target/'state',adopt_baseline=self.baseline)

if __name__=='__main__':unittest.main()
