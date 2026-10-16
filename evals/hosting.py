"""Stage, snapshot and independently grade phased hosting evaluations. No model calls in CI."""
import argparse
from datetime import datetime, UTC
import hashlib
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from install import install
from hosting_grade import grade

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,indent=2)+'\n').encode())

def hashes(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

def prepare(run,package,phase):
    source=ROOT/'evals/packages'/package
    workspace=run/package/'workspace'; observer=run/package/'observed'
    if phase==1:
        workspace.mkdir(parents=True,exist_ok=False)
        install(workspace/'.agents/skills',apply=True)
        shutil.copytree(source/'sources/common',workspace/'sources/common')
        shutil.copytree(source/'protected',workspace/'protected')
        shutil.copyfile(source/'contract.md',workspace/'contract.md')
        shutil.copyfile(ROOT/'evals/recorded_tools.py',workspace/'tools.py')
        write(run/package/'baseline.json',{'protected':hashes(workspace/'protected'),'skills':hashes(workspace/'.agents/skills'),
            'plumbing':{name:hashlib.sha256((workspace/name).read_bytes()).hexdigest() for name in ('tools.py','contract.md')}})
        (workspace/'AGENTS.md').write_text('Synthetic Eventer test. Read contract.md and task.md. Work only in this workspace, using tools.py for observed helpers and simulated external actions. Never inspect parent directories, graders, expected.json, other runs or real accounts. No network or real effects.\n',encoding='utf-8')
    else:
        prior=run/package/f'snapshot-{phase-1}'
        if prior.exists(): raise ValueError('Snapshot already exists; choose a new run rather than overwrite evidence')
        shutil.copytree(workspace/'event',prior)
        if (observer/'journal.jsonl').exists(): shutil.copyfile(observer/'journal.jsonl',run/package/f'journal-before-{phase}.jsonl')
    shutil.copytree(source/f'sources/phase{phase}',workspace/f'sources/phase{phase}')
    shutil.copyfile(source/f'phase{phase}.md',workspace/'task.md')
    write(workspace/'_adapter.json',{'observer':str(observer.resolve()),'phase':phase})
    prompt=f'''Use the installed Eventer skills in {workspace.resolve().as_posix()} to fulfill task.md and contract.md. This is phase {phase}; use saved event records when present. Read the relevant installed SKILL.md files and references. Do not read outside this workspace, except invoking the configured Python and the adapter's recorder automatically. Set this absolute workdir on every command. Use {Path(sys.executable).as_posix()} -B tools.py for helpers and simulated connected tools. Do not inspect source repo, graders, expected answers or other run directories. No real external effects. Complete actual artifacts; report failures honestly. Do not spawn agents.'''
    (run/package/f'prompt-{phase}.txt').write_text(prompt,encoding='utf-8')
    write(run/package/'current.json',{'package':package,'phase':phase,'started_at':datetime.now(UTC).isoformat(),'skill_hashes':hashes(workspace/'.agents/skills'),'python':sys.version.split()[0]})
    print(prompt)
    return workspace

def evaluate(run,package,phase):
    folder=run/package
    current=json.loads((folder/'current.json').read_text())['phase']
    if phase>current: raise ValueError('Phase has not been prepared')
    # Regrade historical output, never the artifacts changed by a later agent.
    if phase<current:
        scratch_root=ROOT/'.eval-runs'; scratch_root.mkdir(exist_ok=True)
        # Deep caller paths can exceed Windows path limits when skills are copied.
        with TemporaryDirectory(prefix='snapshot-grade-',dir=scratch_root) as scratch:
            target=Path(scratch); workspace=target/'workspace'
            workspace.mkdir()
            for name in ['.agents','protected']:
                shutil.copytree(folder/'workspace'/name,workspace/name)
            for name in ['tools.py','contract.md']:
                shutil.copyfile(folder/'workspace'/name,workspace/name)
            for group in ['common',*[f'phase{i}' for i in range(1,phase+1)]]:
                shutil.copytree(folder/'workspace/sources'/group,workspace/'sources'/group)
            shutil.copytree(folder/f'snapshot-{phase}',workspace/'event')
            shutil.copyfile(folder/'baseline.json',target/'baseline.json')
            (target/'observed').mkdir()
            shutil.copyfile(folder/f'journal-before-{phase+1}.jsonl',target/'observed/journal.jsonl')
            if phase>1:
                shutil.copytree(folder/f'snapshot-{phase-1}',target/f'snapshot-{phase-1}')
                shutil.copyfile(folder/f'journal-before-{phase}.jsonl',target/f'journal-before-{phase}.jsonl')
            result=grade(ROOT/'evals/packages'/package,target,phase)
        result['artifact_source']=f'snapshot-{phase}'
    else:
        result=grade(ROOT/'evals/packages'/package,folder,phase)
        result['artifact_source']='current-workspace'
    result.update(package=package,phase=phase,evaluated_at=datetime.now(UTC).isoformat())
    result['provenance']={'inputs':hashes(ROOT/'evals/packages'/package),
        'skills':load_current_skills(run/package),
        'staged_plumbing':json.loads((run/package/'baseline.json').read_text()).get('plumbing',{}),
        'grader_sha256':hashlib.sha256((ROOT/'evals/hosting_grade.py').read_bytes()).hexdigest()}
    previous=folder/f'grade-{phase}.json'
    if previous.exists() and not (folder/f'grade-{phase}.original.json').exists():
        shutil.copyfile(previous,folder/f'grade-{phase}.original.json')
    write(previous,result)
    print(json.dumps(result,indent=2))
    return result

def load_current_skills(folder):
    return json.loads((folder/'current.json').read_text())['skill_hashes']

def harness_run(args,phases):
    from run import invoke
    executable=args.executable or shutil.which(args.harness)
    if not executable: raise ValueError('Harness executable not found')
    results=[]
    for phase in range(1,phases+1):
        workspace=prepare(args.run.resolve(),args.package,phase)
        folder=args.run.resolve()/args.package
        observer=folder/'observed'; observer.mkdir(exist_ok=True)
        prompt=(folder/f'prompt-{phase}.txt').read_text()
        prompt+=' Finish your response with only JSON containing completed and issues; also save completion.json.'
        response,metadata=invoke(args.harness,executable,workspace,prompt,folder/f'response-{phase}.json',args.timeout,(observer,))
        write(folder/f'harness-{phase}.json',metadata)
        result=evaluate(args.run.resolve(),args.package,phase)
        results.append({'phase':phase,'automated_passed':result['automated_passed'],'harness_returned':response is not None})
        if response is None or not result['automated_passed']: break
    passed=len(results)==phases and all(r['automated_passed'] and r['harness_returned'] for r in results)
    write(args.run.resolve()/args.package/'report.json',{'harness':args.harness,'results':results,
        'automated_passed':passed,'overall_passed':False,'independent_review_required':True})
    return int(not passed)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','grade','harness'])
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--package',choices=['full-weekend','correspondence','live-operations'],required=True)
    parser.add_argument('--phase',type=int)
    parser.add_argument('--harness',choices=['codex','claude'])
    parser.add_argument('--executable')
    parser.add_argument('--timeout',type=int,default=900)
    args=parser.parse_args()
    expected=json.loads((ROOT/'evals/packages'/args.package/'expected.json').read_text())
    if args.mode=='harness':
        if not args.harness or not 1<=args.timeout<=3600: parser.error('Provide --harness and timeout 1-3600 seconds')
        return harness_run(args,expected['phases'])
    if args.phase is None or not 1<=args.phase<=expected['phases']: parser.error('Invalid phase')
    if args.mode=='prepare': prepare(args.run.resolve(),args.package,args.phase); return 0
    return int(not evaluate(args.run.resolve(),args.package,args.phase)['automated_passed'])

if __name__=='__main__': raise SystemExit(main())
