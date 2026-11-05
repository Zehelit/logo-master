import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from logo_core.model import sha256
try:
    from logo_core.outputs import stage_variant, commit_variant, build_outputs, register_artifact
except ImportError:
    def stage_variant(*a, **k): return {'status':'missing'}
    def commit_variant(*a, **k): return {'status':'missing'}
    def build_outputs(*a, **k): return {'status':'missing'}
    def register_artifact(*a, **k): return {'status':'missing'}

class OutputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)
        self.svg=self.root/'source.svg'; self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path id="mark" d="M0 0H10V10Z" fill="red"/></svg>')
        self.p={'schema_version':1,'project_id':'other-brand','brand':{'name':'Diğer'},'designs':[{'id':'d','name':'Deneme','approach':4,'case':22,'variants':[{'id':'v1','number':1,'active':True,'parent_id':None,'selection':{'status':'selected','evidence':'user'},'source':{'path':'source.svg','sha256':sha256(self.svg),'kind':'vector'},'canvas':{'width':100,'height':100},'components':[{'id':'emblem','svg_id':'mark','kind':'vector'}],'artifacts':[]}]}]}
        self.path=self.root/'project.json'; self.path.write_text(json.dumps(self.p),encoding='utf-8'); self.p['_root']=str(self.root)
        self.changed=self.root/'changed.svg';self.changed.write_text(self.svg.read_text().replace('red','blue'))
        self.edit={'status':'passed','parent_id':'v1','design_id':'d','original_sha256':sha256(self.svg),'operation':{'kind':'recolor','operation_id':'test-1'},'source':{'path':str(self.changed),'sha256':sha256(self.changed),'kind':'vector'}}
    def test_commit_and_idempotent_retry(self):
        staged=stage_variant(self.p,self.edit,self.root/'staging');r=commit_variant(self.path,staged)
        self.assertEqual(r['status'],'passed');self.assertEqual(commit_variant(self.path,staged)['variant_id'],r['variant_id'])
        rows=json.loads(self.path.read_text())['designs'][0]['variants'];self.assertEqual(len(rows),2);self.assertEqual(rows[-1]['parent_id'],'v1');self.assertEqual(rows[-1]['number'],2)
    def test_tampered_stage_rejected(self):
        staged=stage_variant(self.p,self.edit,self.root/'staging');self.changed.write_text('bad')
        # Tampering with the actual staged bytes must be detected, regardless of original edit file.
        if 'asset_path' in staged: Path(staged['asset_path']).write_text('bad')
        with self.assertRaises(ValueError): commit_variant(self.path,staged)
    def test_failure_after_asset_move_is_recoverable(self):
        staged=stage_variant(self.p,self.edit,self.root/'staging')
        with self.assertRaises(RuntimeError):commit_variant(self.path,staged,_fail_after_move=True)
        self.assertEqual(len(json.loads(self.path.read_text())['designs'][0]['variants']),1)
        self.assertEqual(commit_variant(self.path,staged)['status'],'passed')
        self.assertEqual(len(json.loads(self.path.read_text())['designs'][0]['variants']),2)
    def test_stale_parent_prevents_commit(self):
        staged=stage_variant(self.p,self.edit,self.root/'staging');self.svg.write_text('stale')
        with self.assertRaises(ValueError):commit_variant(self.path,staged)
    def test_outputs_exclude_inactive_and_have_no_selection_controls(self):
        inactive=copy.deepcopy(self.p['designs'][0]['variants'][0]);inactive.update(id='v0',number=3,active=False)
        self.p['designs'][0]['variants'].append(inactive)
        r=build_outputs(self.p,self.root/'delivery',['inventory','panel','package']);self.assertEqual(r['status'],'passed')
        html=(self.root/'delivery/index.html').read_text(encoding='utf-8');self.assertNotIn('v0',html);self.assertNotIn('<input',html);self.assertNotIn('<button',html)
        self.assertTrue((self.root/'delivery/package.zip').is_file());self.assertEqual(r['zip_crc'],'passed')
    def test_missing_asset_stops_package(self):
        self.svg.unlink()
        with self.assertRaises(ValueError):build_outputs(self.p,self.root/'delivery',['package'])
    def test_export_registration_does_not_add_variant(self):
        from PIL import Image
        path=self.root/'out.png';Image.new('RGBA',(10,10)).save(path)
        register_artifact(self.path,'v1',{'path':'out.png','sha256':sha256(path),'format':'png','dpi':300})
        p=json.loads(self.path.read_text());self.assertEqual(len(p['designs'][0]['variants']),1);self.assertEqual(len(p['designs'][0]['variants'][0]['artifacts']),1)

if __name__=='__main__':unittest.main()
