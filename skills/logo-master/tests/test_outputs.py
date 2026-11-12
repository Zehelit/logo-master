import copy
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from logo_core.model import sha256, validate_project
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
        path=self.root/'out.png';Image.new('RGBA',(10,10)).save(path,dpi=(300,300))
        register_artifact(self.path,'v1',{'path':'out.png','sha256':sha256(path),'format':'png','dpi':300})
        p=json.loads(self.path.read_text());self.assertEqual(len(p['designs'][0]['variants']),1);self.assertEqual(len(p['designs'][0]['variants'][0]['artifacts']),1)

    def test_cli_artifact_refuses_false_metadata_without_changing_project(self):
        from PIL import Image
        from logo import main
        path = self.root/'small.dat'
        Image.new('RGBA', (16, 16)).save(path, format='PNG', dpi=(96, 96))
        record = self.root/'record.json'
        record.write_text(json.dumps({'path':path.name,'sha256':sha256(path),'format':'png','width':2000,'height':2000,'dpi':300}), encoding='utf-8')
        initial = sha256(self.path)
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(main(['artifact', str(self.path), 'v1', str(record)]), 1)
        message = json.loads(errors.getvalue())['error']
        self.assertIn('"declared": 2000', message)
        self.assertIn('"observed": 16', message)
        self.assertEqual(sha256(self.path), initial)

    def test_source_kind_comes_from_contents_even_with_misleading_extension(self):
        disguised = self.root/'source.dat'
        disguised.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image id="mark" width="100" height="100"/></svg>', encoding='utf-8')
        source = self.p['designs'][0]['variants'][0]['source']
        source.update(path=disguised.name, sha256=sha256(disguised))
        report = validate_project(self.p, self.root)
        self.assertIn('source_kind_mismatch', {error['code'] for error in report['errors']})
        source['kind'] = 'hybrid'
        self.assertEqual(validate_project(self.p, self.root)['status'], 'passed')

    def test_panel_prefers_measured_visible_resolution_to_preview_role_or_first_png(self):
        from PIL import Image
        artifacts = self.p['designs'][0]['variants'][0]['artifacts']
        for name, size, visible, role in [('small.png',16,16,'preview'),('padded.png',1024,8,'preview'),('large.dat',512,480,'export')]:
            path = self.root/name
            with Image.new('RGBA', (size, size)) as image:
                image.paste('red', (0, 0, visible, visible))
                image.save(path, format='PNG')
            artifacts.append({'path':path.name,'sha256':sha256(path),'format':'png','role':role,'width':2000})
        report = validate_project(self.p, self.root)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(sum(warning['code'] == 'artifact_metadata_mismatch' for warning in report['warnings']), 3)
        delivery = self.root/'delivery'
        result = build_outputs(self.p, delivery, ['panel'])
        self.assertEqual(result['panel_warnings'], [])
        markup = (delivery/'index.html').read_text(encoding='utf-8')
        self.assertIn(f'assets/{artifacts[-1]["sha256"]}.png', markup)
        self.assertNotIn(artifacts[0]['sha256'], markup)
        self.assertNotIn(artifacts[1]['sha256'], markup)

    def test_presentation_uses_explicit_groups_and_omits_archive_only_files(self):
        from PIL import Image
        design = self.p['designs'][0]
        base = design['variants'][0]
        font = self.root/'internal.ttf'
        font.write_bytes(b'private font fixture')
        base['components'].append({'id':'private','kind':'live_text','font':{'path':font.name,'sha256':sha256(font)}})
        base['comparison'] = {'group':'colour','crop':[0.05,0.05,0.9,0.9],'scale':0.9,'note':'Mavi'}
        alternate = copy.deepcopy(base)
        alternate.update(id='v2',number=2,parent_id='v1')
        alternate['comparison']['note'] = 'Kırmızı'
        preview = self.root/'raster.png'
        Image.new('RGBA',(512,512),'red').save(preview)
        alternate['artifacts'] = [{'path':preview.name,'sha256':sha256(preview),'format':'png'}]
        hidden = copy.deepcopy(base)
        hidden.update(id='v3',number=3,active=False)
        hidden['source']['path'] = 'missing-inactive.svg'
        design['variants'].extend([alternate,hidden])
        result = build_outputs(self.p,self.root/'presentation',['panel','package'],scope='presentation')
        self.assertEqual(result['zip_crc'],'passed')
        self.assertEqual(result['active_count'],2)
        self.assertNotIn('project.json',result['files'])
        self.assertFalse(any(path.endswith('.ttf') for path in result['files']))
        panel = (self.root/'presentation/index.html').read_text(encoding='utf-8')
        self.assertEqual(panel.count('data-comparison-group="colour"'),1)
        self.assertEqual(panel.count('--scale:90%'),2)
        self.assertIn('Kırmızı',panel)
        self.assertNotIn('v3',panel)

    def test_delivery_requires_real_technical_receipt_and_final_approval(self):
        from PIL import Image
        from logo_core.acceptance import accept_asset
        row = self.p['designs'][0]['variants'][0]
        raster = self.root/'art.png'
        with Image.new('RGBA',(32,32)) as image:
            image.paste('red',(3,4,20,25))
            image.save(raster,dpi=(300,300))
        accepted = accept_asset(raster,'raster-delivery',{'width':32,'height':32,'dpi':300,'transparent':True},{})
        receipt = self.root/'acceptance.json'
        receipt.write_text(json.dumps(accepted),encoding='utf-8')
        row['artifacts'] = [{'path':raster.name,'sha256':sha256(raster),'format':'png',
                             'acceptance_receipt':{'path':receipt.name,'sha256':sha256(receipt)}}]
        opts = {'scope':'delivery','delivery_target':'raster-delivery'}
        with self.assertRaises(ValueError):
            build_outputs(self.p,self.root/'no-approval',['package'],**opts)
        row['approval'] = {'status':'approved','source_sha256':row['source']['sha256'],'evidence':'fixture'}
        result = build_outputs(self.p,self.root/'delivery',['package'],**opts)
        self.assertEqual(result['zip_crc'],'passed')
        self.assertEqual(set(result['files']),{'delivery.json',f'assets/{sha256(raster)}.png'})
        receipt.write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):
            build_outputs(self.p,self.root/'tampered',['package'],**opts)

if __name__=='__main__':unittest.main()
