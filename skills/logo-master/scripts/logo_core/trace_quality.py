"""Compare a trace with its raster reference at the same pixel geometry."""
import math


def trace_quality(reference, result, contract):
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    import numpy as np

    with Image.open(reference) as first, Image.open(result) as second:
        before = np.array(first.convert('RGBA'))
        after = np.array(second.convert('RGBA'))
    if before.shape != after.shape:
        return {'status':'failed','reason':'trace_canvas_differs'}
    alpha_cutoff = contract.get('alpha_threshold', 128)
    if type(alpha_cutoff) is not int or not 1 <= alpha_cutoff <= 255:
        raise ValueError('Trace alfa eşiği 1–255 arası olmalı.')
    silhouette_before = before[:,:,3] >= alpha_cutoff
    silhouette_after = after[:,:,3] >= alpha_cutoff
    union = silhouette_before | silhouette_after
    intersection = silhouette_before & silhouette_after
    iou = float(intersection.sum() / union.sum()) if union.any() else None

    def holes(silhouette):
        background = Image.fromarray((~silhouette).astype('uint8') * 255)
        padded = ImageOps.expand(background, 1, fill=255)
        ImageDraw.floodfill(padded, (0,0), 128)
        return np.array(padded)[1:-1,1:-1] == 255

    reference_holes = holes(silhouette_before)
    output_holes = holes(silhouette_after)
    hole_pixels = int(reference_holes.sum())
    hole_retention = float((reference_holes & output_holes).sum() / hole_pixels) if hole_pixels else None
    checks = []
    def evaluate(name, actual, expected, *, applicable=True, details=None):
        if expected is not None and (type(expected) not in {int,float} or not math.isfinite(expected) or not 0 <= expected <= 1):
            raise ValueError('Trace eşikleri 0–1 aralığında olmalı.')
        status = ('not_applicable' if not applicable else 'not_run' if expected is None else
                  'failed' if actual is None or actual < expected else 'passed')
        checks.append({'name':name, 'status':status, 'expected_minimum':expected, 'observed':actual, 'details':details})

    evaluate('silhouette_iou', iou, contract.get('min_silhouette_iou'))
    evaluate('hole_retention', hole_retention, contract.get('min_hole_retention'), applicable=bool(hole_pixels),
             details={'reference_hole_pixels':hole_pixels,'result_hole_pixels':int(output_holes.sum())})
    for item in contract.get('palette', []):
        color = item['rgb']
        tolerance = item.get('channel_tolerance', 0)
        if (not isinstance(color,list) or len(color)!=3 or any(type(value) is not int or not 0 <= value <= 255 for value in color)
                or type(tolerance) is not int or not 0 <= tolerance <= 255):
            raise ValueError('Trace paletinde geçerli RGB ve kanal toleransı gerekli.')
        raw = np.all(before[:,:,:3] == color, axis=2) & (before[:,:,3] >= 250)
        interior = np.array(Image.fromarray(raw.astype('uint8') * 255).filter(ImageFilter.MinFilter(3))) != 0
        reference_mask = interior if interior.any() else raw
        reference_pixels = int(reference_mask.sum())
        matches = np.all(np.abs(after[:,:,:3].astype('int16')-color) <= tolerance, axis=2) & silhouette_after
        retained = int((reference_mask & matches).sum())
        evaluate(item.get('name','palette_'+str(color)), retained/reference_pixels if reference_pixels else None,
                 item.get('min_retention'), details={'reference_pixels':reference_pixels,'retained_pixels':retained,
                                                     'reference_method':'solid_interior' if interior.any() else 'solid_pixels'})
    states = {item['status'] for item in checks}
    status = 'failed' if 'failed' in states else 'needs_review' if 'not_run' in states else 'passed'
    return {'status':status, 'checks':checks, 'size':[before.shape[1],before.shape[0]], 'alpha_threshold':alpha_cutoff}
