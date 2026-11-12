from pathlib import Path
from contextlib import redirect_stdout
import io
import json
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

    def test_exact_recolor_checks_other_colors_styles_and_no_op(self):
        source = self.base.replace('<path id="mark"', '<g id="emblem"><path id="mark"').replace(
            '</svg>', '<path id="accent" fill="red" d="M2 2H3V3Z" style="fill: blue ; opacity: 0.9;"/></g></svg>')
        before = self.put('before.svg', source)
        valid = source.replace('fill="blue"', 'fill="navy"').replace('fill: blue', 'fill: navy')
        contract = {'kind':'recolor','target_component':'emblem','replacements':{'blue':'navy'},'attributes':['fill']}
        report = compare_operation(before, self.put('after.svg', valid), contract)
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['color_mapping_verified'])
        self.assertEqual(len(report['authorized_changes']), 2)
        for bad in (source, valid.replace('fill="red"','fill="orange"'), valid.replace('stroke="black"','stroke="navy"'),
                    valid.replace('opacity: 0.9','opacity: 0.5'), valid.replace('M2 2','M4 4')):
            with self.subTest(svg=bad):
                self.assertEqual(compare_operation(before, self.put('bad.svg',bad), contract)['status'], 'failed')
        no_effect = compare_operation(before, before, dict(contract, replacements={'blue':'blue'}))
        self.assertEqual(no_effect['reason'], 'expected_recolor_no_effect')
        self.assertFalse(compare_operation(before, self.put('old.svg',valid), {'kind':'recolor','target_component':'emblem'})['color_mapping_verified'])

    def test_comparison_ignores_container_indentation_preserves_text_and_xml_space(self):
        source = '<svg xmlns="http://www.w3.org/2000/svg"><g><text>A<tspan>B</tspan> C</text><g xml:space="preserve"><path/></g></g></svg>'
        before = self.put('before.svg',source)
        indented = source.replace('<g><text>', '\n  <g>\n    <text>').replace('</text><g', '</text>\n    <g').replace('</g></g></svg>','</g>\n  </g>\n</svg>')
        contract = {'kind':'identical'}
        self.assertEqual(compare_operation(before, self.put('indented.svg', indented), contract)['status'], 'passed')
        for modified in (indented.replace('> C</text>', '>C</text>'), indented.replace('preserve"><path', 'preserve">\n <path')):
            self.assertEqual(compare_operation(before, self.put('modified.svg', modified), contract)['status'], 'failed')
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
        self.assertEqual(result['visible_changes_by_background'], {'light':0,'gray':0,'dark':0})

    def test_raster_acceptance_requires_visible_content_and_measured_metadata(self):
        from PIL import Image
        from logo import main
        source = self.root/'delivery.png'
        contract = self.root/'contract.json'
        contract.write_text(json.dumps({'width':32,'height':32,'dpi':300,'transparent':True}), encoding='utf-8')
        with Image.new('RGBA', (32,32)) as image:
            image.save(source, dpi=(300,300))
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(['accept',str(source),'--target','raster-delivery','--contract',str(contract)]), 1)
            report = json.loads(stdout.getvalue())
            self.assertEqual({item['name']:item['status'] for item in report['checks']}['visible_artwork'], 'failed')
            image.paste('red', (5, 5, 20, 20))
            image.save(source, dpi=(300,300))
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(['accept',str(source),'--target','raster-delivery','--contract',str(contract)]), 0)
        self.assertEqual(json.loads(stdout.getvalue())['status'], 'passed')
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(['accept',str(source),'--target','raster-delivery']), 1)
        self.assertEqual(json.loads(stdout.getvalue())['status'], 'needs_review')

    def test_trace_independently_detects_small_accent_and_closed_hole(self):
        from PIL import Image
        from logo_core.trace_quality import trace_quality
        ref, after = self.root/'reference.png', self.root/'after.png'
        with Image.new('RGBA',(64,64)) as image:
            image.paste('navy',(1,1,63,63))
            image.paste((0,0,0,0),(20,20,24,24))
            image.paste('red',(26,26,29,29))
            image.save(ref)
            image.paste('navy',(20,20,24,24))
            image.paste('navy',(26,26,29,29))
            image.save(after)
        contract = {'min_silhouette_iou':.99,'min_hole_retention':1,'palette':[{'name':'accent','rgb':[255,0,0],'min_retention':1}]}
        self.assertEqual(trace_quality(ref,ref,contract)['status'],'passed')
        result = trace_quality(ref,after,contract)
        self.assertEqual({check['name']:check['status'] for check in result['checks']},
                         {'silhouette_iou':'passed','hole_retention':'failed','accent':'failed'})

    def test_masked_render_comparison_and_physical_views(self):
        from PIL import Image
        from logo_core.acceptance import accept_asset
        from logo_core.model import sha256
        before, after, mask = [self.root/name for name in ('before.png','after.png','mask.png')]
        with Image.new('RGBA',(32,32)) as image:
            image.paste('red',(2,8,9,16))
            image.paste('red',(12,8,19,16))
            image.save(before,dpi=(300,300))
            image.paste('navy',(22,22,26,26))
            image.save(after,dpi=(300,300))
        with Image.new('L',(32,32)) as region:
            region.paste(255,(0,0,20,20))
            region.save(mask)
        self.assertEqual(compare_renders(before,after,mask=mask)['status'],'equal')
        physical={'size_mm':[32,32],'minimum_stroke_mm':5,'stroke_segments':[[[0,10],[10,10]]],
                  'minimum_gap_mm':2,'gap_segments':[[[4,10],[15,10]]],
                  'readability':{'status':'passed','sha256':sha256(before),'size_mm':[32,32],'evidence':'test fixture'}}
        evidence = self.root/'views'
        result = accept_asset(before,'raster-delivery',{'width':32,'height':32,'dpi':300,'physical':physical},{},evidence_dir=evidence)
        self.assertEqual(result['status'],'passed',result)
        self.assertEqual(len(list(evidence.glob('*.png'))),6)

    def test_final_canva_hash_and_conservative_svg_cleanup(self):
        from logo_core.canva import preflight_canva, remove_unreferenced_duplicate_ids, _remove_white_page_rect
        from logo_core.model import read_svg
        from logo_core.edit import write_svg
        raw = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><clipPath id="bounds"><rect width="75" height="75"/></clipPath></defs><rect id="paper" width="100" height="100" fill="white"/><g clip-path="url(#bounds)"><path id="duplicate" d="M2 2H20V20Z"/><path id="duplicate" d="M3 3H5V5Z" fill="white"/></g></svg>'
        path = self.put('canvas.svg',raw)
        self.assertEqual(preflight_canva(path)['errors'][0]['code'],'duplicate_id')
        root = read_svg(path)
        self.assertEqual(remove_unreferenced_duplicate_ids(root),['duplicate'])
        self.assertEqual(_remove_white_page_rect(root,'paper')['svg_id'],'paper')
        write_svg(root,path)
        report = preflight_canva(path)
        self.assertEqual(report['status'],'passed')
        self.assertEqual(report['audit']['counts']['clipPath'],1)
        self.assertEqual(report['audit']['counts']['path'],2)
        self.assertIn('fill="white"',path.read_text(encoding='utf-8'))
        path.write_text(raw.replace('</g>', '<use href="#duplicate"/></g>'),encoding='utf-8')
        self.assertIn('source_hash_changed',{item['code'] for item in preflight_canva(path,report['sha256'])['errors']})
        with self.assertRaises(ValueError):
            remove_unreferenced_duplicate_ids(read_svg(path))

if __name__=='__main__':unittest.main()
