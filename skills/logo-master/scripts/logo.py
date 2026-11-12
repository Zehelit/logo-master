"""Single CLI for the logo-master local helpers."""
import argparse
import json
import os
from pathlib import Path
import sys
import subprocess
import xml.etree.ElementTree as ET
from logo_core.model import find_variant, load_project, safe_path, sha256, validate_project
from logo_core.assets import inspect_asset
from logo_core.acceptance import TARGETS, accept_asset
from logo_core.canva import preflight_canva, convert_pdf
from logo_core.canva_records import sync_state
from logo_core.audit import audit_svg, audit_png, compare_operation, compare_renders
from logo_core.render import RendererError, render_svg, outline_svg
from logo_core.edit import apply_edit, split_svg, assemble_svg, export_png
from logo_core.outputs import atomic_json, stage_variant, commit_variant, build_outputs, register_artifact

def parser():
    p = argparse.ArgumentParser(description='Logo-master: seçilmiş kaynakta kontrollü yerel üretim; yayın işlemi yok.')
    p.add_argument('--version', action='version', version=(Path(__file__).resolve().parents[1]/'VERSION').read_text(encoding='utf-8').strip())
    p.add_argument('--environment', type=Path, help='Yalnız bu süreç için ortam değişkenleri JSON dosyası')
    p.add_argument('--receipt', type=Path, help='Makinece okunabilir yeni makbuz dosyası')
    sub = p.add_subparsers(dest='command', required=True)
    a=sub.add_parser('validate'); a.add_argument('project',type=Path)
    a=sub.add_parser('audit'); a.add_argument('source',type=Path); a.add_argument('--compare',type=Path); a.add_argument('--contract',type=Path)
    a=sub.add_parser('accept'); a.add_argument('source',type=Path); a.add_argument('--target',choices=TARGETS,required=True); a.add_argument('--contract',type=Path); a.add_argument('--project',type=Path); a.add_argument('--variant-id'); a.add_argument('--evidence-dir',type=Path)
    a=sub.add_parser('canva-preflight'); a.add_argument('source',type=Path); a.add_argument('--expect-sha256')
    a=sub.add_parser('canva-state'); a.add_argument('project',type=Path); a.add_argument('variant_id'); a.add_argument('--observation',type=Path)
    a=sub.add_parser('pdf-to-svg'); a.add_argument('source',type=Path); a.add_argument('target',type=Path); a.add_argument('--page',type=int,default=1); a.add_argument('--repair-unreferenced-ids',action='store_true'); a.add_argument('--background-id')
    a=sub.add_parser('render'); a.add_argument('source',type=Path); a.add_argument('target',type=Path); a.add_argument('--width',type=int,required=True); a.add_argument('--height',type=int,required=True)
    a=sub.add_parser('edit'); a.add_argument('project',type=Path); a.add_argument('operation',type=Path); a.add_argument('output_dir',type=Path)
    a=sub.add_parser('outline'); a.add_argument('source',type=Path); a.add_argument('target',type=Path)
    a=sub.add_parser('split'); a.add_argument('source',type=Path); a.add_argument('output_dir',type=Path); a.add_argument('--ids',nargs='+',required=True)
    a=sub.add_parser('assemble'); a.add_argument('manifest',type=Path); a.add_argument('target',type=Path)
    a=sub.add_parser('export'); a.add_argument('source',type=Path); a.add_argument('target',type=Path); a.add_argument('--width',type=int,required=True); a.add_argument('--height',type=int,required=True); a.add_argument('--dpi',type=int,default=300); a.add_argument('--allow-raster-resize',action='store_true')
    a=sub.add_parser('stage'); a.add_argument('project',type=Path); a.add_argument('edit_receipt',type=Path); a.add_argument('output_dir',type=Path)
    a=sub.add_parser('commit'); a.add_argument('project',type=Path); a.add_argument('staged',type=Path)
    a=sub.add_parser('artifact'); a.add_argument('project',type=Path); a.add_argument('variant_id'); a.add_argument('record',type=Path)
    for name in ['outputs','package']:
        a=sub.add_parser(name); a.add_argument('project',type=Path); a.add_argument('output_dir',type=Path)
        if name=='outputs': a.add_argument('--kinds',nargs='+',choices=['inventory','panel','package'],default=['inventory','panel'])
    return p

def reserve_receipt(args):
    path = args.receipt.resolve()
    for key, value in vars(args).items():
        if key == 'receipt' or not isinstance(value, Path):
            continue
        other = value.resolve()
        if (other == path or (key in {'output_dir', 'evidence_dir', 'target'} and other.is_relative_to(path))
                or (key in {'output_dir', 'evidence_dir'} and path.is_relative_to(other))):
            raise ValueError('Makbuz yolu komutun girdi veya çıktı yoluyla çakışıyor.')
    if os.path.lexists(args.receipt) or path.exists():
        raise ValueError('Makbuz dosyası mevcut; yeni yol kullan.')
    path.parent.mkdir(parents=True, exist_ok=True)
    reservation = path.with_name(f'.{path.name}.logo-receipt-lock')
    with reservation.open('xb'):
        pass
    if path.exists():
        reservation.unlink()
        raise ValueError('Makbuz dosyası mevcut; yeni yol kullan.')
    return path, reservation


def main(argv=None):
    args=parser().parse_args(argv)
    stage = 'preflight'
    receipt = reservation = result = None
    try:
        if args.receipt:
            receipt, reservation = reserve_receipt(args)
        env=dict(os.environ)
        if args.environment:
            overrides=load_project(args.environment)
            if not all(isinstance(v,str) for v in overrides.values()): raise ValueError('Ortam değerleri metin olmalı.')
            env.update(overrides)
        # edit canvas uses the same subprocess-only configuration.
        previous={key:os.environ.get(key) for key in env if os.environ.get(key)!=env[key]}
        os.environ.update(env)
        try:
            project=None
            if getattr(args,'project',None) is not None:
                project=load_project(args.project); project['_root']=str(args.project.parent.resolve())
            c=args.command
            stage = 'command'
            if c=='validate': result=validate_project(project,Path(project['_root']))
            elif c=='audit':
                observed = inspect_asset(args.source)
                if args.compare:
                    result=compare_operation(args.source,args.compare,load_project(args.contract)) if observed.get('format')=='svg' and args.contract else compare_renders(args.source,args.compare)
                elif observed.get('format') == 'svg': result=audit_svg(args.source)
                elif observed.get('kind') == 'raster': result=audit_png(args.source)
                else: result=observed
            elif c=='accept':
                contract = load_project(args.contract) if args.contract else {}
                if args.contract:
                    contract['_root'] = str(args.contract.parent.resolve())
                result = accept_asset(args.source,args.target,contract,env,project,args.variant_id,args.evidence_dir)
            elif c=='canva-preflight': result=preflight_canva(args.source,args.expect_sha256)
            elif c=='canva-state':
                _, variant = find_variant(project,args.variant_id)
                local = sha256(safe_path(project['_root'],variant['source']['path']))
                result = sync_state(variant.get('canva') or {}, local, load_project(args.observation) if args.observation else {})
            elif c=='pdf-to-svg': result=convert_pdf(args.source,args.target,args.page,env,repair_unreferenced_ids=args.repair_unreferenced_ids,background_id=args.background_id)
            elif c=='render': result=render_svg(args.source,args.target,args.width,args.height,env)
            elif c=='edit': result=apply_edit(project,load_project(args.operation),args.output_dir)
            elif c=='outline': result=outline_svg(args.source,args.target,env)
            elif c=='split': result=split_svg(args.source,args.ids,args.output_dir)
            elif c=='assemble': result=assemble_svg(args.manifest,args.target)
            elif c=='export': result=export_png(args.source,args.target,args.width,args.height,args.dpi,env,args.allow_raster_resize)
            elif c=='stage': result=stage_variant(project,load_project(args.edit_receipt),args.output_dir)
            elif c=='commit': result=commit_variant(args.project,load_project(args.staged))
            elif c=='artifact': result=register_artifact(args.project,args.variant_id,load_project(args.record))
            elif c in ['outputs','package']: result=build_outputs(project,args.output_dir,['inventory','panel','package'] if c=='package' else args.kinds)
        finally:
            for key,value in previous.items():
                if value is None: os.environ.pop(key,None)
                else: os.environ[key]=value
        if receipt:
            stage = 'receipt'
            atomic_json(receipt, result, exclusive=True)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get('status') in {'failed', 'unknown'} or (c == 'accept' and result['status'] != 'passed') else 0
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError, subprocess.SubprocessError) as exc:
        failure = {'status':'failed', 'error':str(exc), 'stage':stage, 'error_type':type(exc).__name__}
        if stage == 'receipt':
            failure.update(side_effects='command_returned', result=result,
                           retry='Komut sonucunu doğrula. Makbuz hatası tek başına işlemi yeniden çalıştırma gerekçesi değildir.')
        elif isinstance(exc, RendererError):
            failure.update(stage=exc.stage, cause=exc.cause, side_effects='output_not_published')
        else:
            failure['side_effects'] = 'none' if stage == 'preflight' else 'unverified'
        print(json.dumps(failure,ensure_ascii=False),file=sys.stderr)
        return 1
    finally:
        if reservation:
            reservation.unlink(missing_ok=True)

if __name__=='__main__':sys.exit(main())
