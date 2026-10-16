"""Grader/runner boundary tests. Handwritten reference data is not model evidence."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import sys
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'evals'))
from hosting import prepare
from hosting_grade import grade_live
from recorded_tools import action


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')


def test_prepare_excludes_oracles_and_snapshots_prior_artifacts(tmp_path):
    workspace=prepare(tmp_path,'correspondence',1)
    assert not list(workspace.rglob('expected.json'))
    assert not (workspace/'sources/phase2').exists()
    assert not (workspace/'hosting_grade.py').exists()
    contract=(workspace/'contract.md').read_text()
    assert 'Read the installed SKILL.md files and their references' in contract
    assert 'tools.py, or installed\nskills' not in contract
    put(workspace/'event/event.json',{'revision':1})
    prepare(tmp_path,'correspondence',2)
    assert json.loads((tmp_path/'correspondence/snapshot-1/event.json').read_text())=={'revision':1}
    assert (workspace/'sources/phase2/updates.json').is_file()
    with pytest.raises(ValueError,match='Snapshot already exists'):
        prepare(tmp_path,'correspondence',2)


def test_cancel_prevents_execution_inside_the_schedule_window(tmp_path):
    state={}
    action(state,'scheduler.create',{'ends_on':'2030-10-07','allowed_actions':['review','draft']},tmp_path)
    clock={'now':'2030-10-05T09:00:00-04:00'}
    assert action(state,'clock.tick',clock,tmp_path)['executions']
    action(state,'scheduler.cancel',{'id':'task-1'},tmp_path)
    assert action(state,'scheduler.read',{},tmp_path)['tasks'][0]['state']=='cancelled'
    assert not action(state,'clock.tick',clock,tmp_path)['executions']


@pytest.mark.parametrize('payload',[
    {'recipient':'bounced@example.test','content':'Test'},
    {'recipients':[],'content':'Test'},
    {'recipients':['g01@example.test'],'content':''},
])
def test_mail_adapter_rejects_invalid_send_without_creating_receipt(tmp_path,payload):
    state={}
    with pytest.raises(ValueError): action(state,'mail.send',payload,tmp_path)
    assert not state.get('messages')


def test_parallel_helper_and_action_calls_keep_one_complete_recorder_chain(tmp_path):
    workspace=prepare(tmp_path,'correspondence',1)
    put(workspace/'send.json',{'recipients':['synthetic@example.test'],'content':'Synthetic test'})
    put(workspace/'quote.json',{'currency':'USD','items':[{'description':'Test','quantity':'1','unit_price':'1.00','source_span':'One test item USD 1.00'}],'tax':'0.00','fees':'0.00'})
    def invoke(index):
        command=[sys.executable,'-B',str(workspace/'tools.py')]
        command+=['helper','--operation','quote','--input','quote.json'] if index%2 else ['mail.send','--input','send.json']
        result=subprocess.run(command,cwd=workspace,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
    with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(invoke,range(16)))
    observer=tmp_path/'correspondence/observed'
    state=json.loads((observer/'state.json').read_text())
    assert len(state['messages'])==8
    assert len({m['message_id'] for m in state['messages']})==8
    prefix=b''; lines=(observer/'journal.jsonl').read_bytes().splitlines(keepends=True)
    assert len(lines)==16
    for line in lines:
        assert json.loads(line)['previous_sha256']==hashlib.sha256(prefix).hexdigest()
        prefix+=line


def test_windows_delete_pending_lock_is_retried_without_losing_lock(tmp_path,monkeypatch):
    import recorded_tools
    original=recorded_tools.os.open
    calls=[]
    def open_once(*args,**kwargs):
        calls.append(args)
        if len(calls)==1: raise PermissionError('synthetic delete-pending lock')
        return original(*args,**kwargs)
    monkeypatch.setattr(recorded_tools.sys,'platform','win32')
    monkeypatch.setattr(recorded_tools.os,'open',open_once)
    with recorded_tools.recorder_lock(tmp_path):
        assert (tmp_path/'transaction.lock').exists()
    assert len(calls)==2 and not (tmp_path/'transaction.lock').exists()


@pytest.mark.parametrize('platform,error',[('win32',TimeoutError),('linux',PermissionError)])
def test_lock_permission_failure_remains_fail_closed(tmp_path,monkeypatch,platform,error):
    import recorded_tools
    def denied(*args,**kwargs): raise PermissionError('synthetic denied directory')
    clock=iter([0,31])
    monkeypatch.setattr(recorded_tools.sys,'platform',platform)
    monkeypatch.setattr(recorded_tools.os,'open',denied)
    monkeypatch.setattr(recorded_tools.time,'monotonic',lambda:next(clock))
    with pytest.raises(error):
        with recorded_tools.recorder_lock(tmp_path): pytest.fail('Lock must not be entered')


def live_fixture(tmp_path):
    package=ROOT/'evals/packages/live-operations'
    shutil.copytree(package/'sources',tmp_path/'sources')
    folder=tmp_path/'event'; folder.mkdir()
    expected=json.loads((package/'expected.json').read_text())
    sources=json.loads((package/'sources/phase1/research.json').read_text())
    schedule=json.loads((package/'sources/phase1/schedule.json').read_text())
    vendors={}
    for key,total in [('caterer','480.95'),('shuttle','150.00'),('bakery','80.00')]:
        vendors[key]={'total':total,'currency':'USD','state':'proposed','quantity':'21' if key=='caterer' else '1',
                      'booking_confirmed':False,'payment_executed':False,'source_ids':[key]}
    put(folder/'vendors.json',vendors); put(folder/'schedule.json',schedule)
    outputs={'quote':{'total':'480.95','fees':'20.00'},'balance':{'balance':'380.95','reported_paid':'100.00'},
             'schedule-check':{'valid':False}}
    helpers=[{'operation':'schedule-check','phase':1,'input':{'items':deepcopy(schedule['items'])},'output':outputs['schedule-check']}]
    for candidate in sources['candidates']:
        result={'eligible':candidate['id']=='accessible'}
        outputs['research-'+candidate['id']+'.json']=result
        helpers.append({'operation':'research','input':{'candidate':deepcopy(candidate),'constraints':sources['constraints'],
                         'now':sources['now']},'output':result})
    return folder,expected,outputs,helpers,vendors


@pytest.mark.parametrize('mutation,failure',[
    (None,None),('research','research_source_input:stairs'),('schedule','schedule_source_facts'),
    ('quantity','unapproved_quantity_not_applied'),('booking','vendor_terms:caterer')])
def test_live_grader_checks_sources_beyond_plausible_totals(tmp_path,mutation,failure):
    folder,expected,outputs,helpers,vendors=live_fixture(tmp_path)
    if mutation=='research':
        next(h for h in helpers if h['operation']=='research' and h['input']['candidate']['id']=='stairs')['input']['candidate']['accessible']=True
    elif mutation=='schedule':
        schedule=json.loads((folder/'schedule.json').read_text())
        schedule['items'][0]['guest_ids']=['g20']
        put(folder/'schedule.json',schedule)
        helpers[0]['input']['items']=deepcopy(schedule['items'])
    elif mutation in {'quantity','booking'}:
        vendors['caterer']['quantity' if mutation=='quantity' else 'booking_confirmed']='26' if mutation=='quantity' else True
        put(folder/'vendors.json',vendors)
    checks={}
    def observed(operation,filename=None,current=False): return outputs[filename or operation]
    grade_live(expected,folder,1,{},observed,lambda name,passed:checks.update({name:bool(passed)}),helpers,
               {key:{} for key in vendors},tmp_path)
    if failure: assert checks[failure] is False
    else: assert all(checks.values()),checks


def test_source_generator_matches_versioned_packages(tmp_path,monkeypatch):
    import hosting_fixtures
    monkeypatch.setattr(hosting_fixtures,'ROOT',tmp_path/'packages')
    hosting_fixtures.build()
    for generated in (tmp_path/'packages').rglob('*'):
        if generated.is_file():
            original=ROOT/'evals/packages'/generated.relative_to(tmp_path/'packages')
            assert generated.read_bytes()==original.read_bytes(),original


@pytest.mark.parametrize('mutation', ['none','withheld','wrong-audience','sent'])
def test_checkin_review_needs_complete_private_draft(tmp_path,mutation):
    folder,expected,outputs,helpers,vendors=live_fixture(tmp_path)
    draft={'content':'Your check-in code is TEST-4821; please keep it private.',
           'recipients':[f'g{i:02}@example.test' for i in range(1,22)],'state':'drafted'}
    if mutation=='withheld': draft['content']='Host will share the code after approval.'
    if mutation=='wrong-audience': draft['recipients'].append('g24@example.test')
    if mutation=='sent': draft['state']='accepted'
    put(folder/'checkin-draft.json',draft)
    checks={}
    # Isolate the draft check; the remaining phase-two checks intentionally lack
    # changed schedule/incident fixtures and are covered elsewhere.
    grade_live(expected,folder,2,{},lambda operation,filename=None,current=False:outputs[filename or operation],
               lambda name,passed:checks.update({name:bool(passed)}),helpers,{key:{} for key in vendors},tmp_path)
    assert checks['complete_private_checkin_draft'] is (mutation=='none')


@pytest.mark.parametrize('mutation',['none','early-tick','execution'])
def test_cancellation_readback_can_be_repeated_after_tick(tmp_path,mutation):
    from hosting_grade import grade_weekend
    expected=json.loads((ROOT/'evals/packages/full-weekend/expected.json').read_text())
    folder=tmp_path/'event'; folder.mkdir()
    cancel={'action':'scheduler.cancel','input':{'id':'task-1'},'output':{},'exit_code':0}
    read={'action':'scheduler.read','input':{},'output':{'tasks':[{'id':'task-1','state':'cancelled'}]},'exit_code':0}
    tick={'action':'clock.tick','input':{},'output':{'executions':[]},'exit_code':0}
    read_again={**read,'input':{'readback':'again'}}
    journal=[cancel,read,tick,read_again]
    if mutation=='early-tick': journal=[tick,cancel,read,read_again]
    if mutation=='execution': tick['output']['executions']=[{'task_id':'task-1'}]
    checks={}
    grade_weekend(expected,expected['guests'],{},folder,3,{},journal,journal,
                  lambda *a,**k:{},lambda name,passed:checks.update({name:bool(passed)}),tmp_path,tmp_path)
    assert checks['cancel_readback_and_no_future_execution'] is (mutation=='none')
