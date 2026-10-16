"""Read-only checks of saved record links; does not establish evidence truth."""
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def strings(value):
    if isinstance(value,str): return [value]
    if isinstance(value,dict): return [s for v in value.values() for s in strings(v)]
    if isinstance(value,list): return [s for v in value for s in strings(v)]
    return []


def audit_records(workspace, event='event'):
    root=Path(workspace).resolve()
    folder=(root/event).resolve()
    if not folder.is_relative_to(root): raise ValueError('Event directory must be inside workspace')
    canonical=load(folder/'event.json')
    evidence=load(folder/'evidence/index.json')
    if not isinstance(evidence,list): raise ValueError('Evidence index must be an array')
    issues=[]
    def fail(code,record,message): issues.append({'code':code,'record':record,'message':message})
    ids={e.get('id'):e for e in evidence if isinstance(e,dict)}
    if len(ids)!=len(evidence) or None in ids: fail('evidence_ids','index','Use unique, nonempty evidence ids')
    for identity,row in ids.items():
        reference=str(row.get('source_reference','')).split('#')[0]
        path=(root/reference).resolve()
        if not reference or not path.is_relative_to(root) or not path.is_file():
            fail('source_missing',identity,'Source must resolve to a file inside the workspace'); continue
        raw=path.read_text(encoding='utf-8-sig')
        try: parsed=json.loads(raw)
        except ValueError: parsed=raw
        excerpt=row.get('exact_excerpt',row.get('excerpt',''))
        if not isinstance(excerpt,str) or not excerpt.strip() or not (excerpt in raw or any(excerpt in s for s in strings(parsed))):
            fail('excerpt_missing',identity,'Exact excerpt is absent from the referenced source'); continue
        records=parsed if isinstance(parsed,list) else [parsed]
        supplied=[r for r in records if isinstance(r,dict) and r.get('source_id')]
        matching=[r for r in supplied if r['source_id']==identity]
        if matching:
            if not any((excerpt in json.dumps(r,indent=2,ensure_ascii=False) or (r is parsed and excerpt in raw) or any(excerpt in s for s in strings(r)))
                       and r.get('event_id',row.get('event_id'))==row.get('event_id') for r in matching):
                fail('source_mismatch',identity,'Excerpt or event scope does not match this source id')
        elif supplied:
            parent=ids.get(parsed.get('source_id'),{}) if isinstance(parsed,dict) else {}
            if not parent or parent.get('source_reference','').split('#')[0]!=reference or parent.get('event_id')!=row.get('event_id'):
                fail('source_identity',identity,'Preserve the supplied source_id; index the parent source before adding subcitations')

    event_id=canonical.get('event_id')
    def refs(values,record,allow_foreign=False):
        for value in values:
            if value not in ids: fail('unresolved_evidence',record,f'Missing evidence id: {value}')
            elif not allow_foreign and ids[value].get('event_id')!=event_id: fail('foreign_evidence',record,'Evidence belongs to another event')
    for guest in canonical.get('guests',[]): refs(guest.get('evidence_ids',[]),guest.get('id'))
    rank={'ordinary':0,'operational':1,'personal':2,'sensitive':3}
    for requirement in canonical.get('requirements',[]):
        identity=requirement.get('id',requirement.get('guest_id'))
        linked=requirement.get('evidence_ids',[]) or [requirement.get('evidence_id')]
        refs(linked,identity)
        minimum={'allergy':3,'mobility':3,'sleep':2,'dietary':1}.get(requirement.get('kind'),0)
        if rank.get(requirement.get('sensitivity'),0)<minimum:
            fail('requirement_sensitivity',identity,'Preserve the sensitivity of this personal requirement')
        for reference in linked:
            if reference in ids and rank.get(ids[reference].get('sensitivity'),0)<minimum:
                fail('evidence_sensitivity',reference,'Source contains a linked private requirement; retain its sensitivity')

    # Receipt ids can be cited by operational blockers, but a ledger cannot prove
    # provider truth. The calling agent must still reconcile with connected tools.
    receipt_ids=set()
    ledger=folder/'communications.jsonl'
    if ledger.exists():
        for line in ledger.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip(): continue
            row=json.loads(line)
            receipt_ids.add(row.get('message_id',row.get('provider_reference')))
            approval=row.get('approval_source_id',row.get('approval_reference'))
            if approval: refs([approval],row.get('action_id',row.get('message_id')))
    assessment=folder/'assessment.json'
    if assessment.exists():
        data=load(assessment)
        for collection in ['blockers','decisions','incidents']:
            for row in data.get(collection,[]):
                linked=row.get('source_ids',[])
                if not linked: fail('missing_sources',row.get('id'),'Add the actual supporting source id')
                # Decisions may explain why foreign evidence was rejected; it
                # still cannot support this event's guest facts or requirements.
                refs([r for r in linked if r not in receipt_ids],row.get('id'),allow_foreign=collection=='decisions')
    return {'valid':not issues,'issues':issues,'event_id':event_id,'revision':canonical.get('revision'),
            'limitations':'Checks saved links, source identity, excerpts and labels; not semantic truth, authority or provider delivery.'}
