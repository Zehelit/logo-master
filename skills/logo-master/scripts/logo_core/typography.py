"""Collect live SVG text and font runs with presentation-style inheritance."""


def style_dict(value):
    return dict(part.split(':', 1) for part in (item.strip() for item in value.split(';')) if ':' in part)


def font_description(style):
    if style.get('font'):
        return None
    family = style.get('font-family', '').strip().strip("'\"")
    weight = style.get('font-weight', '400').strip()
    weight = {'normal':'400', 'bold':'700'}.get(weight, weight)
    slant = style.get('font-style', 'normal').strip()
    if not family or ',' in family or not weight.isdecimal() or slant not in {'normal', 'italic', 'oblique'}:
        return None
    return {'family':family, 'weight':int(weight), 'style':slant}


def live_text_runs(tree, component=None):
    result = []
    css = any(node.tag.split('}')[-1] == 'style' or node.get('class') for node in tree.iter())
    def walk(node, inherited, in_text=False, owner=None, selected=False):
        style = dict(inherited)
        style.update({key:value for key,value in node.attrib.items() if key == 'font' or key.startswith('font-')})
        style.update({key.strip():value.strip() for key,value in style_dict(node.get('style', '')).items()})
        tag = node.tag.split('}')[-1]
        if tag == 'text':
            owner = node.get('id')
            in_text = True
        if component is None or node is component:
            selected = True
        if selected and in_text and node.text:
            result.append({'text':node.text, 'font':font_description(style), 'svg_id':owner})
        for child in node:
            walk(child, style, in_text, owner, selected)
            if selected and in_text and child.tail:
                result.append({'text':child.tail, 'font':font_description(style), 'svg_id':owner})
    walk(tree, {})
    return result, css
