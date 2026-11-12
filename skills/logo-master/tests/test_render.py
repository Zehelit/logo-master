from pathlib import Path
from contextlib import redirect_stderr
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    from logo_core.render import resolve_font, render_svg, outline_svg
except ImportError:
    def resolve_font(*args):return {'status':'missing','resolved_family':None,'unknown_glyphs':None}
    def render_svg(*args):return {'status':'missing'}
    def outline_svg(*args):return {'status':'missing'}

class RenderTests(unittest.TestCase):
    def test_receipt_preflight_leaves_export_unwritten(self):
        from PIL import Image
        from logo import main
        source = self.root/'original.png'
        Image.new('RGBA', (16, 16)).save(source)
        target = self.root/'export.png'
        existing = self.root/'receipt.json'
        existing.write_text('prior receipt', encoding='utf-8')
        for receipt in (existing, target):
            with self.subTest(receipt=receipt), redirect_stderr(io.StringIO()) as errors:
                code = main(['--receipt', str(receipt), 'export', str(source), str(target), '--width', '16', '--height', '16'])
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(errors.getvalue())['side_effects'], 'none')
                self.assertFalse(target.exists())
                self.assertEqual(existing.read_text(encoding='utf-8'), 'prior receipt')

    def test_renderer_refuses_bad_output_and_reports_tool_failures(self):
        from logo import main
        source = self.root/'logo.svg'
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="10" height="10"/></svg>', encoding='utf-8')
        target = self.root/'logo.png'
        environment = self.root/'tools.json'
        environment.write_text(json.dumps({'LOGO_INKSCAPE': sys.executable}), encoding='utf-8')

        def broken_output(args, **_):
            Path(args[-1].split('=', 1)[1]).write_bytes(b'broken renderer result')
            return subprocess.CompletedProcess(args, 0, '', '')

        for stage, cause, outcome in [('renderer_execution', 'timeout', subprocess.TimeoutExpired('renderer', 90)),
                                      ('renderer_execution', 'exit_code', subprocess.CalledProcessError(7, 'renderer')),
                                      ('renderer_output', 'invalid_output', broken_output)]:
            with self.subTest(cause=cause), patch('logo_core.render.subprocess.run', side_effect=outcome), redirect_stderr(io.StringIO()) as errors:
                code = main(['--environment', str(environment), 'render', str(source), str(target), '--width', '16', '--height', '16'])
                self.assertEqual(code, 1)
                report = json.loads(errors.getvalue())
                self.assertEqual((report['stage'], report['cause'], report['side_effects']), (stage, cause, 'output_not_published'))
                self.assertFalse(target.exists())

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

    def test_real_renderer_binds_font_file_hash(self):
        if not os.environ.get('LOGO_FONT_PYTHON') or not os.environ.get('LOGO_INKSCAPE'):
            self.skipTest('Gerçek font ve renderer motoru konfigüre değil; sınanmadı.')
        env = dict(os.environ)
        actual = resolve_font({'family':'Exo 2','weight':700}, 'EMESİS ŞİĞ', env)
        self.assertEqual(actual['status'], 'passed', actual)
        self.assertTrue(actual.get('font_file_sha256'), actual)
        source = self.root/'text.svg'
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><text id="name" x="10" y="40" font-family="Exo 2" font-weight="700">EMESİS ŞİĞ</text></svg>', encoding='utf-8')
        expected = {'name':{'path':actual['font_file'], 'sha256':actual['font_file_sha256'], 'family':'Exo 2', 'weight':700}}
        result = render_svg(source, self.root/'good.png', 200, 100, env, font_specs=expected)
        self.assertEqual(result['font_checks'][0]['font_file_sha256'], expected['name']['sha256'])
        expected['name']['sha256'] = '0' * 64
        target = self.root/'bad.png'
        with self.assertRaises(ValueError):
            render_svg(source, target, 200, 100, env, font_specs=expected)
        self.assertFalse(target.exists())
    def test_real_renderer_preserves_dimensions(self):
        if not os.environ.get('LOGO_INKSCAPE'):self.skipTest('Gerçek renderer konfigüre değil; sınanmadı.')
        a=self.root/'a.svg';a.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect x="10" y="10" width="80" height="80" fill="#2584c9"/></svg>')
        p=self.root/'a.png';r=render_svg(a,p,200,200,dict(os.environ))
        self.assertEqual(r['status'],'passed');from PIL import Image
        with Image.open(p) as im:self.assertEqual(im.size,(200,200))
        from logo_core.acceptance import accept_asset
        bounded = self.root/'bounded.svg'
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="-50 -50 100 100"><g transform="translate(3 0)"><path d="M-48 -20H20" stroke="red" stroke-width="6"/></g></svg>'
        bounded.write_text(svg, encoding='utf-8')
        result = accept_asset(bounded, 'vector-delivery', {}, dict(os.environ))
        self.assertEqual(result['status'], 'passed', result)
        bounded.write_text(svg.replace('translate(3 0)','translate(-3 0)'), encoding='utf-8')
        result = accept_asset(bounded, 'vector-delivery', {}, dict(os.environ))
        self.assertEqual(result['status'], 'failed', result)
        self.assertTrue(next(item for item in result['checks'] if item['name']=='svg_bounds')['observed']['overflow'])
    def test_missing_font_blocks_outline(self):
        a=self.root/'a.svg';a.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text id="t" style="font-family:Absolutely Missing Font Family 938;font-size:20px">İŞĞ</text></svg>',encoding='utf-8')
        with self.assertRaises(ValueError):outline_svg(a,self.root/'out.svg',dict(os.environ))
    def test_missing_font_blocks_raster_render_too(self):
        if not os.environ.get('LOGO_INKSCAPE'):self.skipTest('Gerçek renderer konfigüre değil; sınanmadı.')
        a=self.root/'bad-font.svg';a.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><text style="font-family:Absolutely Missing Font Family 938;font-size:20px">İŞĞ</text></svg>',encoding='utf-8')
        with self.assertRaises(ValueError):render_svg(a,self.root/'bad-font.png',100,100,dict(os.environ))

if __name__=='__main__':unittest.main()
