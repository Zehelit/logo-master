"""Run repository tests and skill tests with explicit portable/full evidence."""
import argparse
from datetime import datetime,timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
SUITES=('tests','skills/logo-master/tests')
ENV_KEYS=('LOGO_INKSCAPE','LOGO_FONT_PYTHON','FONTCONFIG_FILE','PANGOCAIRO_BACKEND','INKSCAPE_PROFILE_DIR')
ALLOWED_SKIPS=frozenset({
 'test_render.RenderTests.test_real_exo_2_family_and_turkish',
 'test_render.RenderTests.test_real_renderer_preserves_dimensions',
 'test_render.RenderTests.test_missing_font_blocks_raster_render_too',
 'test_review_regressions.ReviewRegressions.test_missing_parent_font_in_tail_is_rejected',
 'test_review_regressions.ReviewRegressions.test_upright_face_cannot_pass_as_requested_italic'})

def subprocess_environment(profile,overrides,base=None):
 env=dict(os.environ if base is None else base)
 for name in (*ENV_KEYS,'PYTHONPATH'):env.pop(name,None)
 env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
 if profile=='full':
  if set(overrides)-set(ENV_KEYS) or not all(isinstance(v,str) for v in overrides.values()):raise ValueError('Bilinmeyen veya metin olmayan ortam değeri.')
  env.update(overrides)
 return env
def validate_origins(paths,repo):
 expected=(Path(repo)/'skills/logo-master/scripts').resolve()
 for name,path in paths.items():
  if not Path(path).resolve().is_relative_to(expected):raise ValueError('Checkout dışında import: '+name+' '+path)
def evaluate_suite(result,profile,is_skill):
 if result['discovered']<1 or result['failures'] or result['errors'] or result.get('import_errors'):return False
 if is_skill and result['discovered']<50:return False
 skips=set(result['skipped'])
 return skips==ALLOWED_SKIPS if profile=='portable' and is_skill else not skips
def child(suite):
 if suite not in SUITES:raise ValueError('Bilinmeyen suite.')
 sys.path.insert(0,str(ROOT/'skills/logo-master/scripts'))
 suite_obj=unittest.defaultTestLoader.discover(str(ROOT/suite))
 stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite_obj)
 origins={name:str(Path(module.__file__).resolve()) for name,module in sys.modules.items() if name.startswith('logo_core') and getattr(module,'__file__',None)}
 problems=[]
 try:validate_origins(origins,ROOT)
 except ValueError as exc:problems.append(str(exc))
 if suite==SUITES[1] and not origins:problems.append('Skill modülleri checkout üzerinden yüklenmedi.')
 report={'suite':suite,'discovered':result.testsRun,'passed':result.testsRun-len(result.skipped)-len(result.failures)-len(result.errors),
 'skipped':[t.id() for t,_ in result.skipped],'skip_reasons':{t.id():reason for t,reason in result.skipped},
 'failures':[{'test':t.id(),'traceback':trace} for t,trace in result.failures],
 'errors':[{'test':t.id(),'traceback':trace} for t,trace in result.errors],
 'module_origins':origins,'import_errors':problems,'log':stream.getvalue()}
 print(json.dumps(report,ensure_ascii=False));return 0
def git_text(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True,encoding='utf-8').strip()
def run(profile,environment,report_path):
 import yaml
 from skill_source import read_version
 env=subprocess_environment(profile,environment)
 engine={'status':'not_run','reason':'portable profile, no font/renderer acceptance'}
 if profile=='full':
  for name in ('LOGO_INKSCAPE','LOGO_FONT_PYTHON','FONTCONFIG_FILE'):
   if not Path(env.get(name,'')).is_file():raise ValueError('Gerçek ortam yolu eksik: '+name)
  inkscape=subprocess.run([env['LOGO_INKSCAPE'],'--version'],capture_output=True,text=True,encoding='utf-8',env=env,check=True)
  pango=subprocess.run([env['LOGO_FONT_PYTHON'],'-c',"import gi;gi.require_version('Pango','1.0');from gi.repository import Pango;print(Pango.version_string())"],capture_output=True,text=True,encoding='utf-8',env=env,check=True)
  engine={'status':'passed','inkscape':inkscape.stdout.strip(),'pango':pango.stdout.strip()}
 skill=ROOT/'skills/logo-master'
 front=(skill/'SKILL.md').read_text(encoding='utf-8').split('---',2)
 metadata=yaml.safe_load(front[1]) if len(front)==3 else {}
 policy=yaml.safe_load((skill/'agents/openai.yaml').read_text(encoding='utf-8'))
 if metadata.get('name')!='logo-master' or not metadata.get('description') or policy.get('policy',{}).get('allow_implicit_invocation') is not False:raise ValueError('Skill metadata/açık çağrı politikası geçersiz.')
 reports=[]
 for suite in SUITES:
  proc=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--child','--suite',suite],capture_output=True,text=True,encoding='utf-8',env=env,cwd=ROOT)
  if proc.returncode:raise ValueError('Test alt süreci başlatılamadı: '+proc.stderr[-1000:])
  item=json.loads(proc.stdout);item['accepted']=evaluate_suite(item,profile,suite==SUITES[1]);reports.append(item)
 data={'schema_version':1,'date':datetime.now(timezone.utc).isoformat(),'profile':profile,'version':read_version(skill),
 'source_commit':git_text('rev-parse','HEAD'),'source_dirty':bool(git_text('status','--porcelain','--untracked-files=normal')),
 'metadata':'passed','engine':engine,'suites':reports,'status':'passed' if all(r['accepted'] for r in reports) else 'failed'}
 if report_path:
  report_path=Path(report_path)
  if report_path.exists():raise ValueError('Yeni test makbuzu yolu gerekli.')
  report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in data.items() if k!='suites'}|{'suites':[{k:r[k] for k in ('suite','discovered','passed','skipped','accepted')} for r in reports]},ensure_ascii=False))
 return 0 if data['status']=='passed' else 1
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=('portable','full'),default='portable');p.add_argument('--environment',type=Path);p.add_argument('--report',type=Path);p.add_argument('--child',action='store_true');p.add_argument('--suite',choices=SUITES)
 args=p.parse_args()
 try:
  if args.child:return child(args.suite)
  environment=json.loads(args.environment.read_text(encoding='utf-8')) if args.environment else {}
  return run(args.profile,environment,args.report)
 except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as exc:print(json.dumps({'status':'failed','error':str(exc)},ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
