import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/eventer/scripts'))
from record_audit import audit_records
from eventer import run


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


@pytest.fixture
def records(tmp_path):
    source={'source_id':'reply-1','event_id':'picnic','body':'I confirm; I need accessible lodging.'}
    put(tmp_path/'sources/replies.json',[source])
    event={'event_id':'picnic','revision':1,'guests':[{'id':'g1','evidence_ids':['reply-1']}],
           'requirements':[{'id':'need-1','kind':'mobility','sensitivity':'sensitive','evidence_id':'reply-1'}]}
    evidence=[{'id':'reply-1','event_id':'picnic','source_reference':'sources/replies.json',
               'exact_excerpt':source['body'],'sensitivity':'sensitive'}]
    put(tmp_path/'event/event.json',event)
    put(tmp_path/'event/evidence/index.json',evidence)
    put(tmp_path/'event/assessment.json',{'blockers':[{'id':'access','source_ids':['reply-1']}]})
    return tmp_path,event,evidence


def test_valid_saved_records_are_read_only(records):
    root,_,_=records
    before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result=run('audit-records',{'workspace':str(root)})
    assert result['valid'] and result['issues']==[]
    assert before=={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('mutation,code',[
    ('rename','source_identity'),('foreign','foreign_evidence'),('excerpt','excerpt_missing'),
    ('missing','unresolved_evidence'),('sensitivity','evidence_sensitivity'),
    ('outside','source_missing'),('blocker','missing_sources')])
def test_record_faults_cannot_pass(records,mutation,code):
    root,event,evidence=records
    if mutation=='rename': evidence[0]['id']='my-new-name'
    if mutation=='foreign': evidence[0]['event_id']='another-event'
    if mutation=='excerpt': evidence[0]['exact_excerpt']='Invented different attendance'
    if mutation=='missing': event['guests'][0]['evidence_ids']=['absent']
    if mutation=='sensitivity': evidence[0]['sensitivity']='ordinary'
    if mutation=='outside': evidence[0]['source_reference']='../outside.json'
    if mutation=='blocker': put(root/'event/assessment.json',{'blockers':[{'id':'access','source_ids':[]}]})
    put(root/'event/event.json',event); put(root/'event/evidence/index.json',evidence)
    result=audit_records(root)
    assert not result['valid']
    assert code in {i['code'] for i in result['issues']}


def test_structured_parent_and_original_id_support_subcitation(records):
    root,_,evidence=records
    source={'source_id':'property','event_id':'picnic','notes':'Accessible entry confirmed.'}
    put(root/'sources/property.json',source)
    evidence += [{'id':'property','event_id':'picnic','source_reference':'sources/property.json',
                  'exact_excerpt':(root/'sources/property.json').read_text(), 'sensitivity':'ordinary'},
                 {'id':'entry-detail','event_id':'picnic','source_reference':'sources/property.json',
                  'exact_excerpt':source['notes'],'sensitivity':'ordinary'}]
    put(root/'event/evidence/index.json',evidence)
    assert audit_records(root)['valid']
    put(root/'event/evidence/index.json',[e for e in evidence if e['id']!='property'])
    assert not audit_records(root)['valid']


def test_foreign_reply_can_explain_a_rejection_but_not_a_guest_fact(records):
    root,event,evidence=records
    source={'source_id':'foreign','event_id':'other-event','body':'I confirm another event.'}
    put(root/'sources/foreign.json',source)
    evidence.append({'id':'foreign','event_id':'other-event','source_reference':'sources/foreign.json',
                     'exact_excerpt':source['body'],'sensitivity':'ordinary'})
    put(root/'event/evidence/index.json',evidence)
    put(root/'event/assessment.json',{'decisions':[{'id':'reject-foreign','source_ids':['foreign'],'state':'rejected'}]})
    assert audit_records(root)['valid']
    event['guests'][0]['evidence_ids'].append('foreign'); put(root/'event/event.json',event)
    assert not audit_records(root)['valid']
