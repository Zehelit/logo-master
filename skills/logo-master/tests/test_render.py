from pathlib import Path
import os
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    from logo_core.render import resolve_font, render_svg, outline_svg
except ImportError:
    def resolve_font(*args):return {'status':'missing','resolved_family':None,'unknown_glyphs':None}
    def render_svg(*args):return {'status':'missing'}
    def outline_svg(*args):return {'status':'missing'}

class RenderTests(unittest.TestCase):
    def test_tspan_font_override_is_not_ignored(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'tspan.svg'
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text font-family="Exo 2">A<tspan font-family="MissingDefinitelyLogoMaster123">B</tspan></text></svg>',encoding='utf-8')
            from logo_core.render import validate_live_fonts
            with self.assertRaises(ValueError): validate_live_fonts(source,dict(os.environ))
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_absent_font_is_not_success(self):
        r=resolve_font({'family':'Absolutely Missing Font Family 938','weight':700},'İŞĞ',dict(os.environ))
        self.assertEqual(r['status'],'failed')
    def test_real_exo_2_family_and_turkish(self):
        if not os.environ.get('LOGO_FONT_PYTHON'):self.skipTest('Gerçek font motoru konfigüre değil; sınanmadı.')
        r=resolve_font({'family':'Exo 2','weight':700},'EMESİS ÇçĞğİıÖöŞşÜü',dict(os.environ))
        self.assertEqual(r['status'],'passed',r)
        self.assertEqual(r['resolved_family'],'Exo 2');self.assertEqual(r['unknown_glyphs'],0)
    def test_real_renderer_preserves_dimensions(self):
        if not os.environ.get('LOGO_INKSCAPE'):self.skipTest('Gerçek renderer konfigüre değil; sınanmadı.')
        a=self.root/'a.svg';a.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect x="10" y="10" width="80" height="80" fill="#2584c9"/></svg>')
        p=self.root/'a.png';r=render_svg(a,p,200,200,dict(os.environ))
        self.assertEqual(r['status'],'passed');from PIL import Image
        with Image.open(p) as im:self.assertEqual(im.size,(200,200))
    def test_missing_font_blocks_outline(self):
        a=self.root/'a.svg';a.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text id="t" style="font-family:Absolutely Missing Font Family 938;font-size:20px">İŞĞ</text></svg>',encoding='utf-8')
        with self.assertRaises(ValueError):outline_svg(a,self.root/'out.svg',dict(os.environ))
    def test_missing_font_blocks_raster_render_too(self):
        if not os.environ.get('LOGO_INKSCAPE'):self.skipTest('Gerçek renderer konfigüre değil; sınanmadı.')
        a=self.root/'bad-font.svg';a.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><text style="font-family:Absolutely Missing Font Family 938;font-size:20px">İŞĞ</text></svg>',encoding='utf-8')
        with self.assertRaises(ValueError):render_svg(a,self.root/'bad-font.png',100,100,dict(os.environ))

if __name__=='__main__':unittest.main()
