import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    from logo_core.model import load_project, validate_project
except ImportError:
    def validate_project(project, root):
        return {'status': 'missing_implementation', 'errors': [], 'warnings': [], 'assets': []}
    def load_project(path):
        return None


class ModelTests(unittest.TestCase):
    def test_malformed_nested_records_return_report_not_crash(self):
        self.project['designs'][0]['approach'] = []
        self.project['designs'][0]['variants'][0]['selection'] = None
        self.assertEqual(validate_project(self.project,self.root)['status'],'failed')
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'logo.svg'
        self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path id="mark" d="M0 0H10V10Z"/></svg>')
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.project = {'schema_version': 1, 'project_id': 'another-brand', 'brand': {'name': 'Başka Marka'}, 'designs': [
            {'id': 'd1', 'approach': 8, 'case': 22, 'variants': [
                {'id': 'v1', 'number': 1, 'parent_id': None, 'active': True,
                 'selection': {'status': 'selected', 'evidence': 'Kullanıcının açık revizyon isteği'},
                 'source': {'path': 'logo.svg', 'sha256': self.digest, 'kind': 'vector'},
                 'canvas': {'width': 100, 'height': 100},
                 'components': [{'id': 'emblem', 'svg_id': 'mark', 'kind': 'vector'}],
                 'colors': {'primary': '#2584c9'}, 'artifacts': []}]}]}

    def codes(self, project=None):
        return {e['code'] for e in validate_project(project or self.project, self.root)['errors']}

    def test_valid_other_brand_and_arbitrary_case(self):
        result = validate_project(self.project, self.root)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['assets'][0]['sha256'], self.digest)

    def test_load_project_preserves_data(self):
        path = self.root / 'project.json'; path.write_text(json.dumps(self.project), encoding='utf-8')
        self.assertEqual(load_project(path), self.project)

    def test_duplicate_variant_identity_rejected(self):
        self.project['designs'][0]['variants'].append(copy.deepcopy(self.project['designs'][0]['variants'][0]))
        self.assertIn('duplicate_variant', self.codes())

    def test_missing_component_node_rejected(self):
        self.project['designs'][0]['variants'][0]['components'][0]['svg_id'] = 'absent'
        self.assertIn('component_missing', self.codes())

    def test_parent_cycle_rejected(self):
        v = self.project['designs'][0]['variants'][0]
        second = copy.deepcopy(v); second.update(id='v2', number=2, parent_id='v1')
        v['parent_id'] = 'v2'; self.project['designs'][0]['variants'].append(second)
        self.assertIn('parent_cycle', self.codes())

    def test_missing_source_rejected(self):
        self.project['designs'][0]['variants'][0]['source']['path'] = 'absent.svg'
        self.assertIn('asset_missing', self.codes())

    def test_mismatched_hash_rejected(self):
        self.project['designs'][0]['variants'][0]['source']['sha256'] = '0' * 64
        self.assertIn('hash_mismatch', self.codes())

    def test_escape_path_rejected(self):
        self.project['designs'][0]['variants'][0]['source']['path'] = '../outside.svg'
        self.assertIn('unsafe_path', self.codes())

    def test_unknown_outlined_font_is_honest_warning(self):
        self.project['designs'][0]['variants'][0]['components'][0].update(kind='outlined', font={'family': None, 'status': 'unknown'})
        result = validate_project(self.project, self.root)
        self.assertEqual(result['status'], 'passed')
        self.assertIn('font_unknown_outlined', {w['code'] for w in result['warnings']})

    def test_unknown_live_font_rejected(self):
        self.project['designs'][0]['variants'][0]['components'][0].update(kind='live_text', text='Başka', font={'family': None, 'status': 'unknown'})
        self.assertIn('live_font_unknown', self.codes())

    def test_stale_canva_mapping_detected(self):
        self.project['designs'][0]['variants'][0]['canva'] = {'design_id': 'external-id', 'source_sha256': '0' * 64, 'sync_status': 'synced'}
        self.assertIn('canva_source_mismatch', self.codes())

    def test_selected_requires_evidence(self):
        self.project['designs'][0]['variants'][0]['selection']['evidence'] = ''
        self.assertIn('selection_evidence_missing', self.codes())


if __name__ == '__main__': unittest.main()
