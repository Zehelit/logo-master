"""Reproductions from the independent final review."""
import copy,json,os
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from logo_core.render import validate_live_fonts,resolve_font
from logo_core.audit import compare_operation,audit_svg
from logo_core.edit import split_svg,apply_edit
from logo_core.outputs import build_outputs,stage_variant,commit_variant
from logo_core.model import sha256

class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'source.svg';self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect id="mark" width="20" height="20" fill="red"/></svg>')
        self.row={'id':'v1','number':1,'active':True,'parent_id':None,'selection':{'status':'selected','evidence':'user'},'source':{'path':'source.svg','sha256':sha256(self.source),'kind':'vector'},'canvas':{'width':100,'height':100},'components':[{'id':'mark','svg_id':'mark','kind':'vector'}],'artifacts':[]}
        self.p={'schema_version':1,'project_id':'review','brand':{'name':'Review'},'designs':[{'id':'d','approach':1,'case':1,'variants':[self.row]}],'_root':str(self.root)}
    @unittest.skipUnless(os.environ.get('LOGO_FONT_PYTHON'),'Real font engine required')
    def test_missing_parent_font_in_tail_is_rejected(self):
        self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text font-family="Absolutely Missing Font 123"><tspan font-family="Exo 2">A</tspan>B</text></svg>')
        with self.assertRaises(ValueError):validate_live_fonts(self.source,dict(os.environ))
    @unittest.skipUnless(os.environ.get('LOGO_FONT_PYTHON'),'Real font engine required')
    def test_upright_face_cannot_pass_as_requested_italic(self):
        result=resolve_font({'family':'Exo 2','weight':400,'style':'italic'},'ABC',dict(os.environ))
        self.assertEqual(result['status'],'failed');self.assertNotEqual(result.get('resolved_style'),'italic')
    def test_tail_content_and_spacing_are_protected(self):
        first=self.root/'first.svg';second=self.root/'second.svg'
        first.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>A<tspan>B</tspan>C</text></svg>')
        for tail in ['WRONG',' C']:
            second.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>A<tspan>B</tspan>'+tail+'</text></svg>')
            self.assertEqual(compare_operation(first,second,{'kind':'identical'})['status'],'failed')
    def test_percentage_geometry_is_rejected_before_canvas_write(self):
        self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect id="mark" x="25%" y="25%" width="50%" height="50%"/></svg>')
        self.row['source']['sha256']=sha256(self.source)
        with self.assertRaises(ValueError):apply_edit(self.p,{'kind':'canvas','variant_id':'v1','parameters':{'width':200,'height':200}},self.root/'canvas')
        self.assertFalse((self.root/'canvas/source.svg').exists())
    def test_split_missing_reference_closure_fails_before_manifest(self):
        self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect id="shape" width="20" height="20"/><use id="mark" href="#shape" x="30"/></svg>')
        with self.assertRaises(ValueError):split_svg(self.source,['mark'],self.root/'parts')
        self.assertFalse((self.root/'parts/split.json').exists())
    def test_external_bitmap_package_is_rejected(self):
        from PIL import Image
        image=self.root/'bitmap.png';Image.new('RGBA',(5,5),'red').save(image)
        self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image id="mark" href="bitmap.png" width="5" height="5"/></svg>')
        self.row['source'].update(sha256=sha256(self.source),kind='hybrid')
        self.row['artifacts']=[{'path':'bitmap.png','sha256':sha256(image),'format':'png'}]
        with self.assertRaises(ValueError):build_outputs(self.p,self.root/'delivery',['package'])
        self.assertFalse((self.root/'delivery/package.zip').exists())
    def test_font_without_approved_redistribution_never_enters_package(self):
        font=self.root/'font.ttf';font.write_bytes(b'font-payload')
        self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text id="mark" font-family="Private">A</text></svg>')
        self.row['source']['sha256']=sha256(self.source)
        self.row['components']=[{'id':'mark','svg_id':'mark','kind':'live_text','text':'A','font':{'family':'Private','weight':400,'path':'font.ttf','sha256':sha256(font),'license':'no-redistribution'}}]
        with self.assertRaises(ValueError):build_outputs(self.p,self.root/'delivery',['package'])
        self.assertFalse((self.root/'delivery/package.zip').exists())
    def test_interruption_during_asset_write_can_retry(self):
        path=self.root/'project.json';path.write_text(json.dumps({k:v for k,v in self.p.items() if k!='_root'}))
        edited=self.root/'edited.svg';edited.write_text(self.source.read_text().replace('red','blue'))
        edit={'status':'passed','parent_id':'v1','design_id':'d','original_sha256':sha256(self.source),'operation':{'kind':'recolor','operation_id':'midwrite'},'source':{'path':str(edited),'sha256':sha256(edited),'kind':'vector'}}
        staged=stage_variant(self.p,edit,self.root/'staging');original_open=Path.open
        class Interrupted:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):self.stream.__enter__();return self
            def __exit__(self,*args):return self.stream.__exit__(*args)
            def __getattr__(self,name):return getattr(self.stream,name)
            def write(self,data):self.stream.write(data[:12]);self.stream.flush();raise OSError('mid-write interruption')
        def injected(file,*args,**kwargs):
            stream=original_open(file,*args,**kwargs)
            return Interrupted(stream) if args and args[0]=='xb' and 'variants' in file.parts else stream
        with patch.object(Path,'open',injected):
            with self.assertRaises(OSError):commit_variant(path,staged)
        self.assertEqual(len(json.loads(path.read_text())['designs'][0]['variants']),1)
        self.assertEqual(commit_variant(path,staged)['status'],'passed')

if __name__=='__main__':unittest.main()
