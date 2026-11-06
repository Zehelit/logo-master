from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
try:import check as checker
except ImportError:checker=None

class CheckTests(unittest.TestCase):
 def api(self):self.assertIsNotNone(checker,'Test runner missing');return checker
 def result(self,skips=()):return {'discovered':50,'passed':50-len(skips),'skipped':list(skips),'failures':[],'errors':[],'import_errors':[]}
 def test_zero_discovered_tests_fails(self):
  r=self.result();r['discovered']=0
  self.assertFalse(self.api().evaluate_suite(r,'portable',False))
 def test_full_profile_rejects_any_skip(self):
  self.assertFalse(self.api().evaluate_suite(self.result(['x']),'full',False))
 def test_portable_profile_reports_skip_names(self):
  c=self.api();r=self.result(c.ALLOWED_SKIPS)
  self.assertTrue(c.evaluate_suite(r,'portable',True));self.assertEqual(set(r['skipped']),set(c.ALLOWED_SKIPS))
 def test_unexpected_skip_fails(self):
  c=self.api();self.assertFalse(c.evaluate_suite(self.result([*c.ALLOWED_SKIPS,'unexpected']),'portable',True))
 def test_managed_tools_tests_included(self):
  self.assertEqual(self.api().SUITES,('tests','skills/logo-master/tests'))
 def test_checks_import_checkout_not_installed_skill(self):
  with self.assertRaises(ValueError):self.api().validate_origins({'logo_core.model':str(Path.home()/'.codex/skills/logo-master/scripts/logo_core/model.py')},ROOT)
  self.api().validate_origins({'logo_core.model':str(ROOT/'skills/logo-master/scripts/logo_core/model.py')},ROOT)
 def test_portable_environment_clears_external_configuration(self):
  c=self.api();e=c.subprocess_environment('portable',{},base={'LOGO_INKSCAPE':'wrong','LOGO_FONT_PYTHON':'wrong','PYTHONPATH':'wrong','PATH':'normal'})
  self.assertNotIn('LOGO_INKSCAPE',e);self.assertNotIn('LOGO_FONT_PYTHON',e);self.assertNotIn('PYTHONPATH',e);self.assertEqual(e['PATH'],'normal')
 def test_failed_or_missing_skill_tests_cannot_pass(self):
  c=self.api();r=self.result(c.ALLOWED_SKIPS);r['failures']=['failure'];self.assertFalse(c.evaluate_suite(r,'portable',True))
  r=self.result(c.ALLOWED_SKIPS);r['discovered']=49;self.assertFalse(c.evaluate_suite(r,'portable',True))

if __name__=='__main__':unittest.main()
