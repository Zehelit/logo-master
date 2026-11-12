"""Target-specific technical acceptance. Aesthetic selection stays in the model."""
import math
import os
from pathlib import Path
import subprocess
import tempfile

from .assets import declaration_conflicts, inspect_asset
from .audit import audit_svg, audit_png, compare_renders
from .edit import drawing_bbox
from .model import find_variant, safe_path, sha256, validate_project
from .render import font_environment, render_svg, validate_live_fonts
from .trace_quality import trace_quality
from .provenance import is_technical_pilot


TARGETS = ('preview', 'selected-source', 'vector-delivery', 'raster-delivery')


def accept_asset(source, target, contract, env, project=None, variant_id=None, evidence_dir=None):
    if target not in TARGETS:
        raise ValueError('Teknik kabul hedefi tanınmıyor.')
    source = Path(source).resolve()
    observed = inspect_asset(source)
    digest = sha256(source)
    checks = []
    def check(name, status, method, expected, actual, *, required=True, evidence=None):
        checks.append({'name':name,'status':status,'required':required,'method':method,
                       'expected':expected,'observed':actual,'evidence':evidence or str(source),'sha256':digest})

    kind = observed.get('kind')
    format_name = observed.get('format')
    acceptable = {'preview':{'svg','png','jpeg','webp'}, 'selected-source':{'svg','png','jpeg','webp'},
                  'vector-delivery':{'svg'}, 'raster-delivery':{'png'}}[target]
    check('format', 'passed' if format_name in acceptable else 'failed', 'file_contents', sorted(acceptable), format_name)
    specs = {}
    if project is not None or target == 'selected-source':
        if project is None or not variant_id:
            check('source_binding','not_run','variant_and_sha256','project and variant ID',None)
        else:
            root = Path(project['_root'])
            _, variant = find_variant(project, variant_id)
            selection = variant['selection']
            model = validate_project(project, root)
            chosen = not is_technical_pilot(project) and selection['status'] in {'selected','approved'} and bool(selection.get('evidence'))
            assets = [variant['source']]
            if target in {'vector-delivery','raster-delivery','preview'}:
                assets.extend(variant.get('artifacts', []))
            bound = any(safe_path(root, record['path']) == source and record['sha256'] == digest for record in assets)
            model_errors = [item for item in model['errors'] if item.get('context','').split('/')[0] == variant_id or not item.get('context')]
            status = 'passed' if bound and chosen and not model_errors else 'failed'
            check('source_binding',status,'variant_and_sha256','selected source and matching model',
                  {'selected':chosen,'matched_source':bound,'model_errors':model_errors})
            for component in variant.get('components', []):
                spec = component.get('font')
                if component.get('kind') == 'live_text' and spec and component.get('svg_id'):
                    specs[component['svg_id']] = {**spec, **({'path':safe_path(root,spec['path'])} if spec.get('path') else {})}

    structure = audit_svg(source) if format_name == 'svg' else None
    unsafe = False
    if structure:
        external = [ref for ref in structure['references'] if ref['kind'] == 'external']
        unsafe = bool(structure['errors'] or external)
        check('svg_structure','failed' if unsafe else 'passed','svg_audit','valid IDs and self-contained content',
              {'errors':structure['errors'],'external_references':external})
    comparison_status = _check_reference(source, observed, contract, env, specs, check) if not unsafe else None
    if structure:
        if target == 'vector-delivery':
            clean = kind == 'vector' and not observed['live_text']
            check('portable_vector','passed' if clean else 'failed','svg_tree','vector without live text or images',
                  {'kind':kind,'live_text':observed['live_text'],'images':observed['image_elements']})
        with font_environment(env, specs.values()) as scoped:
            if observed['live_text']:
                if unsafe:
                    check('fonts','not_run','pango','resolvable text fonts',None)
                else:
                    try:
                        proofs = validate_live_fonts(source,scoped,font_specs=specs,shared_config=True)
                        pinned = all(proof.get('requested_font_sha256') for proof in proofs)
                        check('fonts','passed' if pinned else 'needs_review','pango','each live font bound to a file hash',proofs)
                    except (ValueError, OSError) as exc:
                        check('fonts','needs_review','pango','resolvable text fonts',str(exc))
            _check_svg_bounds(source, observed, structure, contract, scoped, check, unsafe, comparison_status)
        if not unsafe:
            _check_svg_visibility(source, observed, env, specs, check)
    elif kind == 'raster':
        check('visible_artwork','passed' if observed['visible_bbox'] else 'failed','alpha_bounds','nonempty visible region',observed['visible_bbox'])
    if target == 'raster-delivery':
        declared = {key:contract.get(key) for key in ('width','height','dpi')}
        conflicts = declaration_conflicts(declared, observed)
        metadata_status = 'failed' if conflicts else 'not_run' if any(value is None or value == 'unknown' for value in declared.values()) else 'passed'
        check('raster_metadata',metadata_status,'file_contents','explicit width, height and DPI',
              {'expected':declared,'observed':observed,'conflicts':conflicts})
        if contract.get('transparent') is True:
            png = audit_png(source) if format_name == 'png' else {}
            transparent = bool(png.get('all_corners_transparent') and png.get('visible_bbox'))
            check('transparent_background','passed' if transparent else 'failed','png_alpha','visible content and transparent corners',png.get('transparent_pixels'))
    if contract.get('physical') or evidence_dir:
        _check_production_views(source, observed, contract, env, specs, check, unsafe, evidence_dir)

    required = {item['status'] for item in checks if item['required']}
    status = 'failed' if 'failed' in required else 'needs_review' if required & {'needs_review','not_run'} else 'passed'
    return {'status':status,'target':target,'path':str(source),'sha256':digest,'observed':observed,'checks':checks}


def _check_svg_bounds(source, observed, structure, contract, env, check, unsafe, comparison_status):
    size = observed.get('size')
    if not size or unsafe:
        check('svg_bounds','not_run','inkscape_query','measurable, safe absolute SVG viewport',size)
        return
    try:
        x, y, width, height = drawing_bbox(source, env)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        check('svg_bounds','needs_review','inkscape_query','measurable visible bounds',str(exc))
        return
    bounds = [x,y,x+width,y+height]
    viewport = [0,0,*size]
    outside = x < -1e-6 or y < -1e-6 or bounds[2] > size[0]+1e-6 or bounds[3] > size[1]+1e-6
    clip = any(structure['counts'].get(tag,0) for tag in ('clipPath','mask','filter'))
    intentional = contract.get('intentional_clipping')
    purpose_recorded = isinstance(intentional,dict) and isinstance(intentional.get('reason'),str) and intentional['reason'].strip()
    if outside and not purpose_recorded:
        status = 'failed'
    elif outside or clip:
        status = 'passed' if purpose_recorded and comparison_status == 'passed' else 'needs_review'
    else:
        status = 'passed'
    check('svg_bounds',status,'inkscape_query_css_px',viewport,
          {'bounds':bounds,'overflow':outside,'has_clip_mask_or_filter':clip,'intent':intentional})


def _check_svg_visibility(source, observed, env, specs, check):
    size = observed.get('size')
    if not size:
        check('visible_artwork','not_run','inkscape_render_alpha','measurable viewport',None)
        return
    scale = 384 / max(size)
    with tempfile.TemporaryDirectory(prefix='logo-accept-') as folder:
        png = Path(folder)/'preview.png'
        try:
            render_svg(source, png, *(max(1,round(value*scale)) for value in size), env, font_specs=specs)
            measured = audit_png(png)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            check('visible_artwork','needs_review','inkscape_render_alpha','visible preview at fitted size',str(exc))
            return
    check('visible_artwork','passed' if measured['visible_bbox'] else 'failed','inkscape_render_alpha','nonempty visible region',
          {'bounds':measured['visible_bbox'],'size':measured['size']})


def _check_reference(source, observed, contract, env, specs, check):
    comparison = contract.get('comparison')
    trace = contract.get('trace')
    comparison_status = None
    for name, options in [('render_comparison',comparison),('trace_quality',trace)]:
        if options is None:
            continue
        if not isinstance(options,dict) or not options.get('reference'):
            raise ValueError('Karşılaştırma için raster referans yolu gerekli.')
        root = Path(contract.get('_root',source.parent))
        reference = safe_path(root, options['reference'])
        reference_asset = inspect_asset(reference)
        if reference_asset.get('kind') != 'raster':
            check(name,'failed','raster_reference','measured raster reference',reference_asset,evidence=str(reference))
            continue
        reference_hash = sha256(reference)
        if options.get('reference_sha256') and options['reference_sha256'] != reference_hash:
            check(name,'failed','reference_hash',options['reference_sha256'],reference_hash,evidence=str(reference))
            continue
        with tempfile.TemporaryDirectory(prefix='logo-compare-') as folder:
            output = source
            renderer = None
            if observed.get('format') == 'svg':
                output = Path(folder)/'candidate.png'
                try:
                    rendered = render_svg(source, output, *reference_asset['size'], env, font_specs=specs)
                    exe = rendered['renderer']
                    version = subprocess.run([exe,'--version'], capture_output=True, text=True, env=env, check=True, timeout=15)
                    renderer = {'path':exe,'version':version.stdout.strip(),'source_sha256':rendered['source_sha256']}
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    check(name,'needs_review','inkscape_render','rendered comparison at reference size',str(exc),evidence=str(reference))
                    continue
            if name == 'trace_quality':
                result = trace_quality(reference, output, options)
                check(name,result['status'],'trace_against_reference',options,{**result,'reference_sha256':reference_hash,
                      'result_raster_sha256':sha256(output),'renderer':renderer},evidence=str(reference))
            else:
                mask = safe_path(root,options['mask']) if options.get('mask') else None
                result = compare_renders(reference, output, mask=mask, renderer=renderer)
                metrics = {'max_visible_changed_pixels':'visible_changed_pixels','max_interior_changed_pixels':'visible_interior_changed_pixels'}
                limits = {key:options[key] for key in metrics if key in options}
                if any(type(value) is not int or value < 0 for value in limits.values()):
                    raise ValueError('Karşılaştırma piksel sınırı negatif olmayan tamsayı olmalı.')
                if result['status'] == 'failed' or any(result[metrics[key]] > value for key,value in limits.items()):
                    comparison_status = 'failed'
                else:
                    comparison_status = 'passed' if limits else 'needs_review'
                check(name,comparison_status,'rgba_and_background_composites',limits,result,evidence=str(reference))
    return comparison_status


def _check_production_views(source, observed, contract, env, specs, check, unsafe, evidence_dir):
    from PIL import Image
    physical = contract.get('physical')
    with tempfile.TemporaryDirectory(prefix='logo-production-review-') as folder:
        raster = source
        if observed.get('format') == 'svg' and not unsafe:
            size = observed.get('size')
            if not size:
                check('production_views','not_run','inkscape_render','measurable SVG viewport',None)
                return
            scale = 1000 / max(size)
            raster_size = (physical or {}).get('raster_size', [max(1, round(value*scale)) for value in size])
            if len(raster_size) != 2 or any(type(value) is not int or value <= 0 for value in raster_size):
                raise ValueError('Fiziksel render boyutu iki pozitif piksel ölçüsü olmalı.')
            if abs(raster_size[0] - raster_size[1]*size[0]/size[1]) > 1:
                raise ValueError('Fiziksel render boyutu SVG oranını korumalı.')
            raster = Path(folder)/'physical-view.png'
            try:
                render_svg(source,raster,*raster_size,env,font_specs=specs)
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                check('production_views','needs_review','inkscape_render','measurable RGBA proof',str(exc))
                return
        elif observed.get('kind') != 'raster':
            check('production_views','not_run','rgba_composites','measurable RGBA proof',None)
            return
        with Image.open(raster) as original:
            rgba = original.convert('RGBA')
        with rgba:
            if physical:
                _measure_physical(rgba, physical, sha256(source), check)
            if evidence_dir:
                directory = Path(evidence_dir).resolve()
                if directory.exists():
                    raise ValueError('Teknik kanıt dizini yeni olmalı.')
                directory.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.TemporaryDirectory(prefix='.logo-views-',dir=directory.parent) as temporary:
                    staged = Path(temporary)/'views'
                    staged.mkdir()
                    small = rgba.copy()
                    small.thumbnail((128,128), Image.Resampling.LANCZOS)
                    try:
                        for name, color in [('acik',255),('gri',128),('koyu',0)]:
                            for kind, image in [('tam',rgba),('kucuk',small)]:
                                background = Image.new('RGBA',image.size,(color,color,color,255))
                                background.alpha_composite(image)
                                background.save(staged/f'{name}-{kind}.png')
                                background.close()
                    finally:
                        small.close()
                    evidence = {path.name:sha256(path) for path in staged.iterdir()}
                    os.rename(staged, directory)
                check('production_views','passed','same_rgba_composites','light, gray, and dark at full and small size',
                      {'rgba_raster_sha256':sha256(raster),'files':evidence},evidence=str(directory))


def _measure_physical(image, physical, digest, check):
    mm = physical.get('size_mm')
    if not isinstance(mm,list) or len(mm)!=2 or any(type(value) not in {int,float} or not math.isfinite(value) or value <= 0 for value in mm):
        check('physical_dimensions','not_run','declared_use_size','positive width and height in mm',mm)
        return
    px_to_mm = [measure / pixels for measure,pixels in zip(mm,image.size)]
    same_scale = math.isclose(*px_to_mm, rel_tol=.005)
    check('physical_dimensions','passed' if same_scale else 'failed','declared_use_size','uniform physical scale',
          {'size_mm':mm,'pixels':list(image.size),'mm_per_pixel':px_to_mm})
    alpha = image.getchannel('A')
    for name, ink in [('stroke',True),('gap',False)]:
        samples = physical.get(name+'_segments', [])
        minimum = physical.get('minimum_'+name+'_mm')
        lengths = []
        unresolved = 0
        for start, end in samples:
            if not all(isinstance(point,list) and len(point)==2 and all(type(value) is int and 0 <= value < extent
                       for value,extent in zip(point,image.size)) for point in (start,end)) or sum(a != b for a,b in zip(start,end)) != 1:
                raise ValueError('Fiziksel örnek kesiti raster içinde yatay veya dikey olmalı.')
            axis = 0 if start[0]!=end[0] else 1
            low, high = sorted((start[axis],end[axis]))
            matches = []
            for value in range(low,high+1):
                point = (value,start[1]) if axis==0 else (start[0],value)
                matches.append((alpha.getpixel(point) >= 128) == ink)
            runs = sum(current and not previous for previous,current in zip(matches,matches[1:]))
            if matches[0] or matches[-1] or runs != 1:
                unresolved += 1
            else:
                lengths.append(sum(matches)*px_to_mm[axis])
        valid_minimum = type(minimum) in {int,float} and math.isfinite(minimum) and minimum > 0
        if not samples or not valid_minimum:
            status = 'not_run'
        elif any(length < minimum for length in lengths):
            status = 'failed'
        else:
            status = 'needs_review' if unresolved else 'passed'
        check('physical_'+name,status,'raster_cross_sections_mm',minimum,{'lengths_mm':lengths,'unresolved_segments':unresolved})
    readability = physical.get('readability', {})
    status = 'needs_review'
    if (readability.get('sha256') == digest and readability.get('size_mm') == mm and readability.get('evidence')
            and readability.get('status') in {'passed','failed'}):
        status = readability['status']
    check('physical_readability',status,'recorded_inspection_at_use_size',{'size_mm':mm,'sha256':digest},readability)
