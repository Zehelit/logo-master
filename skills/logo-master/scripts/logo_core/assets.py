"""Read visual metadata from file contents independently of project declarations."""
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def read_svg(path):
    raw = Path(path).read_bytes()
    markers = raw.upper().replace(b'\x00', b'')
    if b'<!DOCTYPE' in markers or b'<!ENTITY' in markers:
        raise ValueError('SVG içinde DTD/entity desteklenmiyor.')
    tree = ET.fromstring(raw)
    if tree.tag.split('}')[-1] != 'svg':
        raise ValueError('SVG kökü bulunamadı.')
    return tree


def raster_observation(image):
    dpi = image.info.get('dpi')
    dpi = list(dpi) if isinstance(dpi, (tuple, list)) and len(dpi) == 2 and all(
        type(value) in {float, int} and math.isfinite(value) and value > 0 for value in dpi
    ) else None
    alpha = 'A' in image.getbands() or 'transparency' in image.info
    bounds = image.convert('RGBA').getchannel('A').getbbox() if alpha else (0, 0, *image.size)
    return {'status':'measured', 'format':image.format.lower(), 'kind':'raster', 'size':list(image.size),
            'size_unit':'px', 'mode':image.mode, 'dpi':dpi, 'has_alpha':alpha,
            'visible_bbox':list(bounds) if bounds else None}


def _svg_observation(tree):
    factors = {'':1, 'px':1, 'in':96, 'cm':96/2.54, 'mm':96/25.4, 'pt':96/72, 'pc':16, 'q':96/101.6}
    def pixels(name):
        match = re.fullmatch(r'\s*(\d+(?:\.\d*)?|\.\d+)([a-z]*)\s*', tree.get(name, ''))
        if match and match[2] in factors:
            value = float(match[1]) * factors[match[2]]
            if math.isfinite(value) and value > 0:
                return value

    tags = [node.tag.split('}')[-1] for node in tree.iter()]
    width, height = pixels('width'), pixels('height')
    return {'status':'measured', 'format':'svg', 'kind':'hybrid' if 'image' in tags or 'foreignObject' in tags else 'vector',
            'size':[width, height] if width and height else None, 'size_unit':'css_px', 'dpi':None,
            'view_box':tree.get('viewBox'), 'live_text':tags.count('text'), 'image_elements':tags.count('image')}


def _pdf_observation(path):
    result = {'status':'unknown', 'format':'pdf', 'kind':None, 'size':None, 'size_unit':'pt', 'dpi':None}
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError:
        return dict(result, reason='pdf_parser_unavailable')
    try:
        with path.open('rb') as stream:
            reader = PdfReader(stream)
            pages = []
            for page in reader.pages:
                box = page.mediabox
                size = [float(box.width) * float(page.user_unit), float(box.height) * float(page.user_unit)]
                if any(not math.isfinite(value) or value <= 0 for value in size):
                    raise ValueError('PDF sayfa ölçüsü geçersiz.')
                resources = page.get('/Resources', {})
                resources = resources.get_object() if resources else {}
                fonts = resources.get('/Font', {}) if resources else {}
                fonts = fonts.get_object() if fonts else {}
                content = page.get_contents()
                path_ops = sum(operator in {b'm',b'l',b'c',b'v',b'y',b'h',b're'} for _,operator in content.operations) if content else 0
                pages.append({'size':size, 'size_unit':'pt', 'rotation':page.rotation, 'image_objects':len(page.images),
                              'font_resource_names':[str(name) for name in fonts], 'path_construction_operators':path_ops})
    except (OSError, ValueError, TypeError, KeyError, PyPdfError) as exc:
        return dict(result, reason='pdf_unreadable', error=type(exc).__name__)
    return dict(result, status='measured', pages=pages, size=pages[0]['size'] if len(pages) == 1 else None)


def inspect_asset(path):
    path = Path(path)
    with path.open('rb') as stream:
        header = stream.read(1024)
    if header.startswith(b'%PDF-'):
        return _pdf_observation(path)
    if header.replace(b'\x00', b'').lstrip(b'\xef\xbb\xbf\xff\xfe \t\r\n').startswith(b'<'):
        try:
            return _svg_observation(read_svg(path))
        except (ET.ParseError, ValueError) as exc:
            return {'status':'unknown', 'format':None, 'kind':None, 'reason':'xml_not_readable_as_svg', 'detail':str(exc)}
    from PIL import Image
    try:
        with Image.open(path) as image:
            image.load()
            return raster_observation(image)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        return {'status':'unknown', 'format':None, 'kind':None, 'reason':'visual_format_unknown', 'detail':type(exc).__name__}


def declaration_conflicts(record, observed):
    comparisons = {'format':observed.get('format'), 'size_unit':observed.get('size_unit'), 'dpi':observed.get('dpi')}
    size = observed.get('size') or (None, None)
    comparisons.update(width=size[0], height=size[1])
    conflicts = []
    for key, measured in comparisons.items():
        declared = record.get(key)
        if declared is None or declared == 'unknown':
            continue
        if key == 'format':
            expected = str(declared).lower()
            if expected == 'jpg':
                expected = 'jpeg'
            matches = expected == measured
        elif key == 'dpi':
            axes = declared if isinstance(declared, (list, tuple)) else (declared, declared)
            tolerance = 0.0127 if observed.get('format') == 'png' else 0.001
            matches = measured is not None and len(axes) == 2 and all(
                type(a) in {float, int} and math.isclose(a, b, rel_tol=0, abs_tol=tolerance)
                for a, b in zip(axes, measured)
            )
        elif key in {'width', 'height'}:
            matches = type(declared) in {float, int} and measured is not None and math.isclose(declared, measured, rel_tol=0, abs_tol=1e-6)
        else:
            matches = declared == measured
        if not matches:
            conflicts.append({'field':key, 'declared':declared, 'observed':measured})
    return conflicts
