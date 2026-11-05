"""Single CLI for the logo-master local helpers."""
import argparse
import json
import os
from pathlib import Path
import sys
from logo_core.model import load_project, validate_project
from logo_core.audit import audit_svg, audit_png, compare_operation, compare_renders
from logo_core.render import render_svg, outline_svg
from logo_core.edit import apply_edit, split_svg, assemble_svg, export_png
from logo_core.outputs import stage_variant, commit_variant, build_outputs, register_artifact

def parser():
    p = argparse.ArgumentParser(description='Logo-master: seçilmiş kaynakta kontrollü yerel üretim; yayın işlemi yok.')
    p.add_argument('--environment', type=Path, help='Yalnız bu süreç için ortam değişkenleri JSON dosyası')
    p.add_argument('--receipt', type=Path, help='Makinece okunabilir yeni makbuz dosyası')
    sub = p.add_subparsers(dest='command', required=True)
    a=sub.add_parser('validate'); a.add_argument('project',type=Path)
    a=sub.add_parser('audit'); a.add_argument('source',type=Path); a.add_argument('--compare',type=Path); a.add_argument('--contract',type=Path)
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

def main(argv=None):
    args=parser().parse_args(argv)
    try:
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
            if hasattr(args,'project'):
                project=load_project(args.project); project['_root']=str(args.project.parent.resolve())
            c=args.command
            if c=='validate': result=validate_project(project,Path(project['_root']))
            elif c=='audit':
                if args.compare:
                    result=compare_operation(args.source,args.compare,load_project(args.contract)) if args.source.suffix.lower()=='.svg' and args.contract else compare_renders(args.source,args.compare)
                else: result=audit_svg(args.source) if args.source.suffix.lower()=='.svg' else audit_png(args.source)
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
        if args.receipt:
            if args.receipt.exists(): raise ValueError('Makbuz dosyası mevcut; yeni yol kullan.')
            args.receipt.parent.mkdir(parents=True,exist_ok=True)
            args.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get('status')=='failed' else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)},ensure_ascii=False),file=sys.stderr); return 1

if __name__=='__main__':sys.exit(main())
