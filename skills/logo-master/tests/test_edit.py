import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    from logo_core.edit import apply_edit, split_svg, assemble_svg, export_png
except ImportError:
    def apply_edit(*args):return {'status':'missing'}
    def split_svg(*args):return {'status':'missing'}
    def assemble_svg(*args):return {'status':'missing'}
    def export_png(*args):return {'status':'missing'}

class EditTests(unittest.TestCase):
    def test_changed_part_ancestor_is_not_silently_discarded(self):
        pieces=split_svg(self.source,['mark','word'],self.root/'pieces')
        p=Path(pieces['parts'][0]['path']);p.write_text(p.read_text().replace('translate(5 10)','translate(50 100)'),encoding='utf-8')
        with self.assertRaises(ValueError):assemble_svg(pieces,self.root/'assembled.svg')
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'source.svg';self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><defs><clipPath id="cp"><rect width="100" height="100"/></clipPath></defs><g transform="translate(5 10)"><g id="mark" clip-path="url(#cp)"><rect width="20" height="20" fill="#2584c9"/><circle cx="5" cy="5" r="2" fill="white"/></g><path id="word" d="M30 0H60V10H30Z" fill="#2584c9"/></g></svg>',encoding='utf-8')
        self.digest=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.project={'_root':str(self.root),'designs':[{'id':'d1','variants':[{'id':'v1','number':1,'selection':{'status':'selected','evidence':'user'},'source':{'path':'source.svg','sha256':self.digest,'kind':'vector'},'components':[{'id':'emblem','svg_id':'mark','kind':'vector'}]}]}]}
    def op(self,kind,parameters=None):return {'kind':kind,'variant_id':'v1','target_component':'emblem','parameters':parameters or {}}
    def test_recolor_preserves_white_and_source(self):
        r=apply_edit(self.project,self.op('recolor',{'replacements':{'#2584c9':'#ea414c'}}),self.root/'color')
        self.assertEqual(r['status'],'needs_render');self.assertTrue(r['audit']['protected_structure_equal']);self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.digest)
        out=Path(r['source']['path']).read_text();self.assertIn('fill="white"',out);self.assertIn('fill="#ea414c"',out)
        self.assertEqual(out.count('fill="#2584c9"'),1)
    def test_uniform_scale_keeps_path_data(self):
        r=apply_edit(self.project,self.op('scale',{'factor':.75,'center':[10,10]}),self.root/'scale')
        self.assertEqual(r['status'],'needs_render');self.assertTrue(r['audit']['protected_structure_equal']);tree=E.parse(r['source']['path']);self.assertIn('scale(0.75)',tree.find(".//*[@id='mark']").get('transform'))
    def test_candidate_cannot_enter_production(self):
        self.project['designs'][0]['variants'][0]['selection']={'status':'candidate'}
        with self.assertRaises(ValueError):apply_edit(self.project,self.op('scale',{'factor':.75}),self.root/'out')
    def test_existing_output_not_overwritten(self):
        (self.root/'out').mkdir();(self.root/'out/source.svg').write_text('protected')
        with self.assertRaises(ValueError):apply_edit(self.project,self.op('scale',{'factor':.75}),self.root/'out')
        self.assertEqual((self.root/'out/source.svg').read_text(),'protected')
    def test_reassembly_preserves_nested_ancestor_and_dependencies(self):
        pieces=split_svg(self.source,['mark','word'],self.root/'pieces')
        r=assemble_svg(pieces,self.root/'assembled.svg')
        self.assertEqual(r['status'],'passed')
        if os.environ.get('LOGO_INKSCAPE'):
            from logo_core.render import render_svg
            from logo_core.audit import compare_renders
            render_svg(self.source,self.root/'before.png',100,100,dict(os.environ));render_svg(self.root/'assembled.svg',self.root/'after.png',100,100,dict(os.environ))
            self.assertEqual(compare_renders(self.root/'before.png',self.root/'after.png')['visible_changed_pixels'],0)
    def test_export_dpi_changes_no_pixels(self):
        from PIL import Image
        source=self.root/'old.png';Image.new('RGBA',(20,20),(37,132,201,128)).save(source,dpi=(96,96))
        r=export_png(source,self.root/'new.png',20,20,300,dict(os.environ))
        self.assertEqual(r['status'],'passed')
        with Image.open(source) as a,Image.open(self.root/'new.png') as b:
            self.assertEqual(a.convert('RGBA').tobytes(),b.convert('RGBA').tobytes());self.assertAlmostEqual(b.info['dpi'][0],300,places=2)
    def test_no_implicit_raster_upscale(self):
        from PIL import Image
        source=self.root/'raster.png';Image.new('RGBA',(20,20)).save(source)
        with self.assertRaises(ValueError):export_png(source,self.root/'larger.png',40,40,300,dict(os.environ))

if __name__=='__main__':unittest.main()
