from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    from logo_core.audit import audit_svg, compare_operation, audit_png, compare_renders
except ImportError:
    def audit_svg(path): return {'status': 'missing', 'geometry_signature': '', 'appearance_signature': '', 'warnings': [], 'references': []}
    def compare_operation(*args): return {'status': 'missing'}
    def audit_png(*args): return {'status': 'missing'}
    def compare_renders(*args): return {'status': 'missing'}

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.base='<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path id="mark" d="M10 10H90V90H10Z" fill="blue" stroke="black" stroke-width="1"/></svg>'
    def put(self,name,xml):
        p=self.root/name;p.write_text(xml);return p
    def test_recolor_permits_only_target_fill(self):
        a=self.put('a.svg',self.base);b=self.put('b.svg',self.base.replace('fill="blue"','fill="red"'))
        self.assertEqual(compare_operation(a,b,{'kind':'recolor','target_component':'mark'})['status'],'passed')
    def test_stroke_width_is_not_a_recolor(self):
        a=self.put('a.svg',self.base);b=self.put('b.svg',self.base.replace('stroke-width="1"','stroke-width="20"'))
        self.assertEqual(compare_operation(a,b,{'kind':'recolor','target_component':'mark'})['status'],'failed')
        self.assertNotEqual(audit_svg(a)['geometry_signature'],audit_svg(b)['geometry_signature'])
    def test_use_target_is_in_appearance_signature(self):
        a=self.put('a.svg',self.base.replace('</svg>','<use href="#mark"/></svg>'));b=self.put('b.svg',a.read_text().replace('href="#mark"','href="#other"'))
        self.assertNotEqual(audit_svg(a)['appearance_signature'],audit_svg(b)['appearance_signature'])
        self.assertEqual(audit_svg(b)['status'],'failed')
    def test_embedded_content_change_detected(self):
        a=self.put('a.svg',self.base.replace('</svg>','<image href="data:image/png;base64,YQ=="/></svg>'));b=self.put('b.svg',a.read_text().replace('YQ==','Yg=='))
        self.assertNotEqual(audit_svg(a)['appearance_signature'],audit_svg(b)['appearance_signature'])
    def test_css_needs_render_instead_of_false_pass(self):
        a=self.put('a.svg',self.base.replace('<path','<style>.x{fill:red}</style><path class="x"'))
        result=audit_svg(a);self.assertEqual(result['status'],'needs_render')
        self.assertIn('stylesheet_requires_render',{w['code'] for w in result['warnings']})
    def test_scale_checks_expected_transform_and_shape(self):
        a=self.put('a.svg',self.base);b=self.put('b.svg',self.base.replace('id="mark"','id="mark" transform="scale(0.75)"'))
        contract={'kind':'scale','target_component':'mark','expected_transform':'scale(0.75)'}
        self.assertEqual(compare_operation(a,b,contract)['status'],'passed')
        self.assertEqual(compare_operation(a,b,dict(contract,expected_transform='scale(0.5)'))['status'],'failed')
    def test_transparency_is_more_than_corner_alpha(self):
        from PIL import Image
        p=self.root/'image.png';im=Image.new('RGBA',(20,20),'white');im.putpixel((0,0),(0,0,0,0));im.save(p,dpi=(300,300))
        result=audit_png(p)
        self.assertEqual(result['opaque_pixels'],399)
        self.assertEqual(result['transparent_pixels'],1)
        self.assertFalse(result['all_corners_transparent'])
    def test_channel_difference_even_with_equal_zero_alpha(self):
        from PIL import Image
        a=self.root/'a.png';b=self.root/'b.png';Image.new('RGBA',(1,1),(255,0,0,0)).save(a);Image.new('RGBA',(1,1),(0,0,255,0)).save(b)
        result=compare_renders(a,b)
        self.assertEqual(result['rgba_changed_pixels'],1)
        self.assertEqual(result['visible_changed_pixels'],0)

if __name__=='__main__':unittest.main()
