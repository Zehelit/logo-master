"""Exercise the public installer CLI in an isolated Codex home, without GitHub."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class RepositoryInstallTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='repo-install-');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir();self.home=self.root/'codex'
  (self.repo/'tools').mkdir()
  for name in ('skillctl.py','skill_source.py'):shutil.copyfile(ROOT/'tools'/name,self.repo/'tools'/name)
  self.skill=self.repo/'skills/logo-master';self.skill.mkdir(parents=True)
  (self.skill/'SKILL.md').write_bytes(b'first');(self.skill/'VERSION').write_bytes(b'1.0.0\n')
  self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid');self.git('config','core.autocrlf','false')
  self.git('add','.');self.git('commit','-qm','first');self.first=self.git('rev-parse','HEAD');self.git('tag','v1.0.0')
  # This URL has no remote access in these tests; commands must use local objects only.
  self.git('remote','add','origin','git@github.com:Zehelit/logo-master.git')
  self.env={**os.environ,'CODEX_HOME':str(self.home),'USERPROFILE':str(self.root/'fallback-profile'),'GIT_TERMINAL_PROMPT':'0','PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1','GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'protocol.allow','GIT_CONFIG_VALUE_0':'never'}
 def git(self,*args):return subprocess.check_output(['git',*args],cwd=self.repo,text=True).strip()
 def cli(self,*args,code=0):
  p=subprocess.run([sys.executable,str(self.repo/'tools/skillctl.py'),*args],cwd=self.root,env=self.env,capture_output=True,text=True,encoding='utf-8')
  self.assertEqual(p.returncode,code,p.stdout+p.stderr);return json.loads(p.stdout)
 def upgrade_source(self):
  (self.skill/'SKILL.md').write_bytes(b'second');(self.skill/'VERSION').write_bytes(b'1.1.0\n')
  self.git('add','.');self.git('commit','-qm','second');return self.git('rev-parse','HEAD')
 def test_human_and_agent_commands_install_update_and_rollback_offline(self):
  self.assertEqual(self.cli('status')['status'],'unmanaged')
  self.assertEqual(self.cli('install')['commit'],self.first)
  self.assertTrue(self.cli('install','--ref',self.first)['noop'])
  self.assertTrue(self.cli('install','--tag','v1.0.0')['noop'])
  second=self.upgrade_source();self.assertEqual(self.cli('install')['commit'],second)
  self.assertEqual(self.cli('rollback')['commit'],self.first)
  self.assertEqual(self.cli('install','--ref',second)['commit'],second)
  self.assertEqual(self.cli('status')['status'],'clean')
  self.assertEqual((self.home/'skills/logo-master/SKILL.md').read_bytes(),b'second')
  self.assertFalse((self.home/'skill-installations/logo-master/journal.json').exists())
 def test_dirty_installed_files_refuse_update(self):
  self.cli('install');self.upgrade_source();path=self.home/'skills/logo-master/SKILL.md';path.write_bytes(b'user changes')
  self.assertEqual(self.cli('install',code=2)['status'],'failed');self.assertEqual(path.read_bytes(),b'user changes')
 def test_unknown_origin_fails_before_install(self):
  self.git('remote','set-url','origin','https://example.invalid/other/repo.git')
  self.assertEqual(self.cli('install',code=2)['status'],'failed');self.assertFalse(self.home.exists())
 def test_relative_codex_home_is_rejected(self):
  self.env['CODEX_HOME']='relative-codex-home'
  self.assertEqual(self.cli('install',code=2)['status'],'failed');self.assertFalse((self.root/'relative-codex-home').exists())
 def test_wrong_tag_version_fails_before_install(self):
  self.git('tag','v9.0.0')
  self.assertEqual(self.cli('install','--tag','v9.0.0',code=2)['status'],'failed');self.assertFalse(self.home.exists())

if __name__=='__main__':unittest.main()
