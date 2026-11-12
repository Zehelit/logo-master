"""Structural checks are evidence, not aesthetic or renderer equivalence certificates."""
import copy
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from .model import read_svg, sha256
from .typography import style_dict

GEOMETRY = {'d','points','x','y','x1','y1','x2','y2','cx','cy','r','rx','ry','width','height','viewBox','transform','stroke-width','stroke-linecap','stroke-linejoin','stroke-miterlimit','stroke-dasharray','stroke-dashoffset','fill-rule','clip-rule','font-family','font-size','font-weight','letter-spacing','word-spacing','text-anchor','vector-effect'}

def signature(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def canonical(node, geometry=False):
    attrs = dict(node.attrib)
    style = style_dict(attrs.pop('style',''))
    attrs.update({k.strip():v.strip() for k,v in style.items()})
    if geometry:attrs={k:v for k,v in attrs.items() if k in GEOMETRY}
    return {'tag':node.tag,'attrs':attrs,'text':node.text or '', 'tail':node.tail or '', 'children':[canonical(c,geometry) for c in node]}


def comparison_tree(node, inherited_preserve=False, ignore_tail=False):
    """Keep explicit attributes and all text except formatting in graphic containers."""
    namespace, _, name = node.tag.rpartition('}')
    preserve = inherited_preserve or node.get('{http://www.w3.org/XML/1998/namespace}space') == 'preserve'
    graphic_container = namespace in {'', '{http://www.w3.org/2000/svg'} and name in {
        'svg', 'g', 'defs', 'symbol', 'marker', 'clipPath', 'mask', 'pattern',
    }
    normalize = graphic_container and not preserve and len(node) > 0
    text, tail = node.text or '', node.tail or ''
    return {'tag':node.tag, 'attrs':dict(node.attrib),
            'text':'' if normalize and not text.strip() else text,
            'tail':'' if ignore_tail and not tail.strip() else tail,
            'children':[comparison_tree(child, preserve, normalize) for child in node]}


def recolor_component(node, replacements, attributes):
    if not isinstance(replacements, dict) or not replacements:
        raise ValueError('Açık eski→yeni renk eşlemesi gerekli.')
    if not isinstance(attributes, (list, tuple)) or not attributes or any(key not in ('fill','stroke') for key in attributes) or len(attributes) != len(set(attributes)):
        raise ValueError('Renk niteliği listesi fill/stroke değerlerinden oluşmalı.')
    colors = {}
    for old, new in replacements.items():
        if any(not isinstance(value, str) or not re.fullmatch(r'#[0-9A-Fa-f]{3,8}|[a-zA-Z]+', value.strip()) for value in (old, new)):
            raise ValueError('Yalnız açık düz renk değerleri kullanılabilir.')
        key = old.strip().casefold()
        if key in colors:
            raise ValueError('Aynı kaynak renk birden fazla eşlemede kullanılmış.')
        colors[key] = new.strip()

    changes = []
    def replacement(value, element, attribute, location):
        key = value.strip().casefold()
        new = colors.get(key)
        if new is None or new.casefold() == key:
            return value
        changes.append({'svg_id':element.get('id'), 'attribute':attribute, 'location':location, 'from':value, 'to':new})
        return new

    pattern = re.compile(r'(^|;)(\s*)(' + '|'.join(attributes) + r')(\s*:\s*)([^;]*?)(\s*)(?=;|$)', re.I)
    for element in node.iter():
        for key in attributes:
            if key in element.attrib:
                old = element.get(key)
                new = replacement(old, element, key, 'attribute')
                if old != new:
                    element.set(key, new)
        style = element.get('style')
        if style and pattern.search(style):
            if any(token in style for token in ('/*', '\\', '"', "'", 'data:')):
                raise ValueError('Karmaşık inline CSS için güvenli renk değişimi doğrulanamadı.')
            def substitute(match):
                separator, leading, key, colon, value, trailing = match.groups()
                updated = replacement(value, element, key.lower(), 'style')
                return separator + leading + key + colon + updated + trailing
            element.set('style', pattern.sub(substitute, style))
    return changes

def audit_svg(path: Path) -> dict:
    root=read_svg(path);counts={};refs=[];warnings=[];errors=[];transform_chains=[]
    def chains(node, inherited):
        current=inherited+([node.get('transform')] if node.get('transform') else [])
        if node.get('id'):
            transform_chains.append({'svg_id':node.get('id'),'ordered_ancestor_and_local_transforms':current,'coordinate_note':'Dıştan içe bileşim; iç SVG viewBox ve CSS bu listeyle sayısal çözülmez.'})
        for child in node: chains(child,current)
    chains(root,[])
    ids=[n.get('id') for n in root.iter() if n.get('id')];idset=set(ids)
    if len(ids)!=len(idset):errors.append({'code':'duplicate_id','message':'SVG id çakışması.'})
    for n in root.iter():
        tag=n.tag.split('}')[-1];counts[tag]=counts.get(tag,0)+1
        if tag=='style' or n.get('class'):
            warnings.append({'code':'stylesheet_requires_render','message':'CSS seçicileri için gerçek render gerekli.'})
        if tag=='style':
            stylesheet=''.join(n.itertext())
            if re.search(r'@import\b',stylesheet,re.I) or any(not value.startswith('#') for value in re.findall(r'url\(\s*[\'"]?([^\)\'"\s]+)',stylesheet)):
                refs.append({'tag':tag,'kind':'external','target':'stylesheet-external-dependency'})
                warnings.append({'code':'external_reference','message':'Stil sayfası dış bağımlılık içeriyor.'})
        if tag in ['filter','mask','clipPath','foreignObject','script']:
            warnings.append({'code':'effect_requires_render','message':tag+' görünüm için render incelemesi gerektirir.'})
        if tag in ['script','foreignObject']:
            errors.append({'code':'active_content','message':'Düz logo kaynağında aktif içerik desteklenmiyor.'})
        for key,value in n.attrib.items():
            if key.startswith('on'):errors.append({'code':'active_content','message':'SVG olay kodu desteklenmiyor.'})
            if key.split('}')[-1]=='href':
                kind='internal' if value.startswith('#') else 'embedded' if value.startswith('data:') else 'external'
                refs.append({'tag':tag,'kind':kind,'target':value if kind!='embedded' else 'sha256:'+hashlib.sha256(value.encode()).hexdigest()})
                if kind=='internal' and value[1:] not in idset:errors.append({'code':'missing_reference','target':value})
                if kind=='external':warnings.append({'code':'external_reference','message':'Dış varlık çözülmeden görünüm eşdeğerliği kanıtlanmaz.'})
            for target in re.findall(r'url\(\s*[\'"]?([^\)\'"\s]+)',value):
                if target.startswith('#') and target[1:] not in idset:errors.append({'code':'missing_reference','target':target})
                if not target.startswith('#'):
                    refs.append({'tag':tag,'kind':'external','target':target})
                    warnings.append({'code':'external_reference','message':'Harici url() varlığı var.'})
    raster=counts.get('image',0)>0
    return {'file':str(Path(path).resolve()),'sha256':sha256(path),'status':'failed' if errors else 'needs_render' if warnings else 'passed','counts':counts,'transform_chains':transform_chains,'references':refs,'errors':errors,'warnings':warnings,'source_kind':'hybrid' if raster else 'vector','geometry_signature':signature(canonical(root,True)),'appearance_signature':signature(canonical(root)),'limitations':'Yapısal eşitlik estetik onay veya renderer eşdeğerliği değildir; CSS, efekt ve font çözümlemesini ayrıca doğrula.'}

def _target(root, ident):
    found=[n for n in root.iter() if n.get('id')==ident]
    if len(found)!=1:raise ValueError('Hedef SVG id tekil olmalı: '+str(ident))
    return found[0]

def compare_operation(before: Path, after: Path, contract: dict) -> dict:
    a,b=read_svg(before),read_svg(after);aa,bb=audit_svg(before),audit_svg(after)
    if aa['errors'] or bb['errors']:return {'status':'failed','reason':'invalid_svg','before':aa,'after':bb}
    kind=contract.get('kind');allowed=contract.get('target_component')
    try:
        evidence = {}
        parameters = contract.get('parameters') or {}
        if kind=='recolor' and ('replacements' in contract or 'replacements' in parameters):
            changes = recolor_component(_target(a,allowed), contract.get('replacements',parameters.get('replacements')),
                                        contract.get('attributes',parameters.get('attributes',['fill','stroke'])))
            if not changes:
                return {'status':'failed','reason':'expected_recolor_no_effect','color_mapping_verified':False}
            evidence = {'authorized_changes':changes, 'comparison_scope':'exact_color_mapping'}
        elif kind=='recolor':
            evidence = {'color_mapping_verified':False, 'comparison_scope':'legacy_structural_only'}
            for root in [a,b]:
                for n in _target(root,allowed).iter():
                    for key in ['fill','stroke']:
                        if n.get(key) and n.get(key).lower() not in ['none','transparent']:n.set(key,'__allowed_color__')
                    if n.get('style'):
                        st=style_dict(n.get('style'));st={k.strip():v.strip() for k,v in st.items()}
                        for key in ['fill','stroke']:
                            if st.get(key) and st[key].lower() not in ['none','transparent']:st[key]='__allowed_color__'
                        n.set('style',';'.join(k+':'+v for k,v in sorted(st.items())))
        elif kind in ['scale','layout']:
            na,nb=_target(a,allowed),_target(b,allowed)
            if nb.get('transform','')!=contract.get('expected_transform'):
                return {'status':'failed','reason':'unexpected_transform'}
            nb.attrib.pop('transform',None)
            if na.get('transform') is not None:nb.set('transform',na.get('transform'))
        elif kind=='identical':pass
        else:return {'status':'needs_render','reason':'operation_requires_specific_or_render_contract'}
        if evidence.get('comparison_scope') == 'legacy_structural_only':
            same = canonical(a) == canonical(b)
        else:
            same = comparison_tree(a) == comparison_tree(b)
        result={'status':'passed' if same else 'failed','protected_structure_equal':same,'before_sha256':aa['sha256'],'after_sha256':bb['sha256'],**evidence}
        if evidence.get('comparison_scope') == 'exact_color_mapping':
            result['color_mapping_verified'] = same
        if same and (aa['warnings'] or bb['warnings']):result.update(status='needs_render',reason='structural_match_with_unresolved_appearance')
        return result
    except ValueError as exc:return {'status':'failed','reason':str(exc)}

def audit_png(path):
    from PIL import Image
    import numpy as np
    from .assets import raster_observation
    with Image.open(path) as source:
        observed = raster_observation(source)
        alpha = np.array(source.convert('RGBA').getchannel('A'))
        return {**observed, 'status':'passed', 'dpi':observed['dpi'] or [],
                'transparent_pixels':int((alpha==0).sum()),'opaque_pixels':int((alpha==255).sum()),
                'partial_alpha_pixels':int(((alpha>0)&(alpha<255)).sum()),
                'all_corners_transparent':all(alpha[y,x]==0 for y,x in [(0,0),(0,-1),(-1,0),(-1,-1)])}

def compare_renders(before, after, *, mask=None, renderer=None):
    from PIL import Image
    import numpy as np
    with Image.open(before) as first,Image.open(after) as second:
        a=np.array(first.convert('RGBA'));b=np.array(second.convert('RGBA'))
    evidence = {'before_sha256':sha256(before), 'after_sha256':sha256(after), 'renderer':renderer,
                'before_size':[a.shape[1],a.shape[0]], 'after_size':[b.shape[1],b.shape[0]]}
    if a.shape!=b.shape:
        return {'status':'failed','reason':'dimensions_differ',**evidence}
    if mask:
        with Image.open(mask) as region:
            selected = np.array(region.convert('L')) != 0
        evidence['mask_sha256'] = sha256(mask)
        if selected.shape != a.shape[:2] or not selected.any():
            return {'status':'failed','reason':'mask_dimension_or_visibility_invalid',**evidence}
    else:
        selected = np.ones(a.shape[:2],dtype=bool)
        evidence['mask_sha256'] = None
    changed = np.any(a!=b,axis=2) & selected
    visible = np.zeros(changed.shape,dtype=bool)
    backgrounds = {}
    first_alpha, second_alpha = a[:,:,3:4]/255., b[:,:,3:4]/255.
    for name,bg in [('light',255.),('gray',128.),('dark',0.)]:
        af = a[:,:,:3]*first_alpha+bg*(1-first_alpha)
        bf = b[:,:,:3]*second_alpha+bg*(1-second_alpha)
        difference = np.any(np.rint(af)!=np.rint(bf),axis=2) & selected
        visible |= difference
        backgrounds[name] = int(difference.sum())
    def edge_pixels(image):
        alpha = image[:,:,3]
        solid = alpha != 0
        padded = np.pad(solid, 1, constant_values=False)
        neighbors = [padded[:-2,1:-1], padded[2:,1:-1], padded[1:-1,:-2], padded[1:-1,2:]]
        return np.logical_or.reduce([solid != neighbor for neighbor in neighbors]) | ((alpha != 0) & (alpha != 255))
    edges = edge_pixels(a) | edge_pixels(b)
    return {'status':'equal' if not changed.any() else 'different',**evidence,'rgba_changed_pixels':int(changed.sum()),
            'visible_changed_pixels':int(visible.sum()),'visible_edge_changed_pixels':int((visible & edges).sum()),
            'visible_interior_changed_pixels':int((visible & ~edges).sum()),'visible_changes_by_background':backgrounds,
            'max_channel_difference':int(np.abs(a[selected].astype(int)-b[selected].astype(int)).max()),
            'limitations':'Fark sayısı tek başına kusur kararı değildir; görsel ve işlem sözleşmesiyle değerlendir.'}
