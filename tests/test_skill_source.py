import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
try:import skill_source as source
except ImportError:source=None

class SourceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.repo=Path(self.temp.name)/'repo';self.repo.mkdir();self.skill=self.repo/'skills/logo-master';self.skill.mkdir(parents=True)
  (self.skill/'VERSION').write_bytes(b'1.0.0\n');(self.skill/'SKILL.md').write_bytes(b'known source\n')
  self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid');self.git('config','core.autocrlf','false')
  self.git('add','.');self.git('commit','-qm','fixture');self.commit=self.git('rev-parse','HEAD');self.git('tag','v1.0.0')
 def git(self,*args):return subprocess.check_output(['git',*args],cwd=self.repo,text=True).strip()
 def api(self):self.assertIsNotNone(source,'Direct Git source implementation missing');return source
 def test_cli_version_without_subcommand(self):
  p=subprocess.run([sys.executable,str(ROOT/'skills/logo-master/scripts/logo.py'),'--version'],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout.strip(),'1.1.0')
 def test_existing_help_unchanged(self):
  p=subprocess.run([sys.executable,str(ROOT/'skills/logo-master/scripts/logo.py'),'--help'],capture_output=True,text=True)
  self.assertEqual(p.returncode,0)
  for command in ['validate','audit','render','edit','outline','split','assemble','export','stage','commit','artifact','outputs','package']:self.assertIn(command,p.stdout)
 def test_default_source_is_exact_local_head(self):
  s=self.api().load_source(self.repo)
  self.assertEqual(s['commit'],self.commit);self.assertEqual(s['version'],'1.0.0');self.assertEqual(s['payload']['SKILL.md'],b'known source\n')
 def test_tag_and_full_commit_need_no_release(self):
  for ref in ['v1.0.0',self.commit]:self.assertEqual(self.api().load_source(self.repo,ref)['commit'],self.commit)
 def test_install_reads_commit_not_uncommitted_files(self):
  (self.skill/'SKILL.md').write_bytes(b'local edits');(self.skill/'extra.py').write_bytes(b'not committed')
  s=self.api().load_source(self.repo)
  self.assertEqual(s['payload']['SKILL.md'],b'known source\n');self.assertNotIn('extra.py',s['payload'])
 def test_source_read_never_calls_network_or_gh(self):
  api=self.api();original=api.git;calls=[]
  def observe(repo,*args):calls.append(args);return original(repo,*args)
  with patch.object(api,'git',side_effect=observe):api.load_source(self.repo,'v1.0.0')
  self.assertTrue(calls);self.assertFalse(any(a[0] in ('fetch','pull','ls-remote') for a in calls))
 def test_unknown_reference_is_rejected(self):
  with self.assertRaises(ValueError):self.api().load_source(self.repo,'missing-ref')
 def test_tag_version_mismatch(self):
  with self.assertRaises(ValueError):self.api().validate_tag('v2.0.0','1.0.0')
 def test_invalid_version_rejected(self):
  for text in ['v1.0.0','01.0.0','1.0','1.0.0\n2.0.0']:
   (self.skill/'VERSION').write_text(text)
   with self.assertRaises(ValueError):self.api().read_version(self.skill)
 def test_tracked_cache_is_rejected(self):
  (self.skill/'bad.pyc').write_bytes(b'cache');self.git('add','.');self.git('commit','-qm','bad')
  with self.assertRaises(ValueError):self.api().load_source(self.repo)
 def test_git_case_collision_is_rejected(self):
  blob=self.git('rev-parse','HEAD:skills/logo-master/SKILL.md')
  self.git('update-index','--add','--cacheinfo','100644,'+blob+',skills/logo-master/skill.md');self.git('commit','-qm','collision')
  with self.assertRaises(ValueError):self.api().load_source(self.repo)
 def test_git_symlink_is_rejected(self):
  blob=self.git('rev-parse','HEAD:skills/logo-master/SKILL.md')
  self.git('update-index','--add','--cacheinfo','120000,'+blob+',skills/logo-master/link');self.git('commit','-qm','link')
  with self.assertRaises(ValueError):self.api().load_source(self.repo)
 def test_install_help_supports_repository_ref(self):
  p=subprocess.run([sys.executable,str(ROOT/'tools/skillctl.py'),'install','--help'],capture_output=True,text=True)
  self.assertEqual(p.returncode,0);self.assertIn('--ref',p.stdout)

if __name__=='__main__':unittest.main()
