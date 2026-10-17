"""Mutation tests for the offline, independently graded hosting scenarios.

The fixtures below are deliberately assembled from synthetic package sources.
They are test artifacts, not outputs from an evaluated model. The only
production logic they execute is the installed helper CLI through the recorder.
"""
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
EVALS = PLUGIN / "evals"
sys.path.insert(0, str(EVALS))
from hosting import prepare  # noqa: E402
from hosting_grade import grade  # noqa: E402


PACKAGE = EVALS / "packages" / "full-weekend"


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def record(run, workspace, action, payload=None, operation=None, input_path=None):
    """Record a real helper/synthetic external action through tools.py."""
    args = [sys.executable, "-B", str(workspace / "tools.py"), action]
    if operation:
        args += ["--operation", operation]
    if input_path:
        args += ["--input", input_path]
    elif payload is not None:
        rel = f"inputs/{action.replace('.', '-')}-{len(list((workspace / 'inputs').glob('*.json')))}.json"
        put(workspace / rel, payload)
        args += ["--input", rel]
    result = subprocess.run(args, cwd=workspace, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def build_phase1_baseline(run):
    """Create one fully passing phase-1 fixture using synthetic source facts."""
    workspace = prepare(run, "full-weekend", 1)
    event_dir = workspace / "event"
    expected = read(PACKAGE / "expected.json")
    logistics = read(PACKAGE / "sources/phase1/logistics.json")
    property_data = read(PACKAGE / "sources/phase1/property.json")
    replies = read(PACKAGE / "sources/phase1/replies.json")

    evidence = []
    evidence_by_source = {}
    for message in replies:
        sid = message["source_id"]
        excerpt = message.get("body", message.get("text", json.dumps(message, sort_keys=True)))
        evidence_by_source[sid] = sid
        evidence.append({"id": sid, "event_id": "weekend",
                         "source_reference": "sources/phase1/replies.json#" + sid,
                         "exact_excerpt": excerpt})
    for source_id, source_file in [("property-1", "property.json"), ("logistics-1", "logistics.json")]:
        content = read(PACKAGE / "sources/phase1" / source_file)
        evidence.append({"id": source_id, "event_id": "weekend",
                         "source_reference": f"sources/phase1/{source_file}",
                         "exact_excerpt": content.get("source_id", source_id)})
    approval_data = read(PACKAGE / "sources/phase1/approval.json")
    evidence.append({"id": approval_data["source_id"], "event_id": "weekend",
                     "source_reference": "sources/phase1/approval.json",
                     "exact_excerpt": approval_data["content"]})

    guests = []
    roster = {r['id']: r for r in csv.DictReader((PACKAGE / 'sources/common/guests.csv').read_text().splitlines())}
    for gid, fact in expected["guests"].items():
        guests.append({"id": gid, "name": roster[gid]['name'], "rsvp_status": fact["status"],
                       "truth_state": "confirmed" if fact["status"] == "confirmed" else "proposed",
                       "arrival": fact["arrival"], "departure": fact["departure"],
                       "evidence_ids": [fact["source_id"]] if fact["source_id"] else []})
    requirements = []
    for gid, kind in expected["requirements"].items():
        sid = f"reply-{int(gid[1:]):02}"
        requirements.append({"id": f"need-{gid}", "guest_id": gid, "kind": kind,
                             "evidence_id": sid, "description": f"Synthetic {kind} requirement"})
    event = {"event_id": "weekend", "revision": 1, "timezone": "America/New_York",
             "starts_on": "2030-10-04", "ends_on": "2030-10-07", "guests": guests,
             "requirements": requirements}
    put(event_dir / "event.json", event)
    put(event_dir / "evidence/index.json", evidence)

    room_guests = [{k: g[k] for k in ("id", "arrival", "departure", "rsvp_status", "truth_state")}
                   for g in guests]
    constraints = [
        {"id": "g01-accessible", "guest_id": "g01", "kind": "requires_accessibility", "hard": True, "weight": 1, "details": {}},
        {"id": "g04-own-bed", "guest_id": "g04", "kind": "requires_own_bed", "hard": True, "weight": 1, "details": {}},
    ]
    room_input = {"starts_on": "2030-10-04", "ends_on": "2030-10-07", "timezone": "America/New_York",
                  "guests": room_guests, "beds": property_data["beds"], "constraints": constraints}
    put(workspace / "inputs/rooming.json", room_input)
    put(event_dir / "rooming-input.json", room_input)
    room = record(run, workspace, "helper", operation="rooming", input_path="inputs/rooming.json")
    put(event_dir / "rooming.json", room)

    meal_input = {"meal": logistics["meal"], "guests": [
        {"id": g["id"], "name": g["name"], "rsvp_status": g["rsvp_status"],
         "arrival": g["arrival"], "departure": g["departure"], "truth_state": g["truth_state"],
         "precision": "exact_time", "attendance_evidence_id": (g["evidence_ids"] or [None])[0]}
        for g in guests],
        "overrides": [],
        "profiles": [{"guest_id": g["id"], "serving_category": "unknown", "dietary_status": "unknown"}
                     for g in guests],
        "needs": [{"guest_id": "g02", "requirement_id": "need-g02", "category": "adult",
                   "evidence_id": "reply-02", "need_type": "allergy"}],
        "accommodations": [{"category": "adult", "need_type": "allergy", "state": "unknown",
                             "evidence_id": "logistics-1"}], "requirements": requirements}
    put(workspace / "inputs/meals.json", meal_input)
    put(event_dir / "meals-input.json", meal_input)
    meals = record(run, workspace, "helper", operation="meals", input_path="inputs/meals.json")
    put(event_dir / "meals.json", meals)

    transport_input = {"ride": logistics["ride"], "vehicle": logistics["vehicle"],
                       "travelers": logistics["travelers"], "existing": []}
    put(workspace / "inputs/transport.json", transport_input)
    put(event_dir / "transport-input.json", transport_input)
    transport = record(run, workspace, "helper", operation="transport", input_path="inputs/transport.json")
    put(event_dir / "transport.json", transport)

    quote_input = deepcopy(logistics["quote"])
    for item in quote_input["items"]:
        item["source_span"] = "Synthetic host-entered quote from logistics.json"
    put(event_dir / "quote-input.json", quote_input)
    quote = record(run, workspace, "helper", operation="quote", payload=quote_input)
    balance_input = {"currency": "USD", "total": expected["quote_total"], "payments": logistics["payments"]}
    put(event_dir / "balance-input.json", balance_input)
    balance = record(run, workspace, "helper", operation="balance", payload=balance_input)
    put(event_dir / "quote.json", quote)
    put(event_dir / "balance.json", balance)

    approval = expected["authorization"]
    send = record(run, workspace, "mail.send", {"recipients": approval["recipients"], "content": approval["content"]})
    lookup = record(run, workspace, "mail.lookup", {})
    assert send["state"] == "uncertain" and lookup["messages"]
    (event_dir / "communications.jsonl").write_text(json.dumps({
        "message_id": "msg-1", "recipients": approval["recipients"], "content": approval["content"],
        "state": "accepted", "approval_source_id": approval["source_id"]}) + "\n", encoding="utf-8")

    schedule_payload = {"timezone": "America/New_York", "local_time": "09:00", "cadence": "daily",
                        "ends_on": "2030-10-07", "allowed_actions": ["review", "draft"], "draft_only": True}
    task = record(run, workspace, "scheduler.create", schedule_payload)
    record(run, workspace, "scheduler.read", {})
    put(event_dir / "schedule.json", {"task": task, **schedule_payload})

    blockers = [{"id": "check-in", "owner": "Morgan Host", "next_action": "Confirm the check-in details.",
                 "source_ids": ["property-1"]},
                {"id": "meal-safety", "owner": "Morgan Host", "next_action": "Confirm an allergy-safe meal.",
                 "source_ids": ["reply-02"]}]
    put(event_dir / "assessment.json", {"event_id": "weekend", "revision": 1, "ready": False,
                                         "blockers": blockers})
    for name in ("summary.md", "digest.md", "agenda.md"):
        content = ("Synthetic weekend host record. Confirmed facts come from the supplied replies. "
                   "Morgan Host should resolve the listed open items before publishing the plan.\n")
        (event_dir / name).write_text(content, encoding="utf-8")
    return workspace, run / "full-weekend"


@pytest.fixture(scope="module")
def phase1_baseline(tmp_path_factory):
    base = tmp_path_factory.mktemp("hosting-baseline")
    return build_phase1_baseline(base / "run")


def copy_phase1_baseline(source_run, destination):
    package_run = destination / "full-weekend"
    shutil.copytree(source_run, package_run)
    workspace = package_run / "workspace"
    adapter_path = workspace / "_adapter.json"
    adapter = read(adapter_path)
    adapter["observer"] = str((package_run / "observed").resolve())
    put(adapter_path, adapter)
    return workspace, package_run


def graded(run):
    return grade(PACKAGE, run, 1)


def test_synthetic_phase1_baseline_passes_independent_hosting_grade(phase1_baseline):
    _, run = phase1_baseline
    result = graded(run)
    assert result["automated_passed"], result["failures"]


@pytest.mark.parametrize("mutation,expected_failure", [
    ("extra_send", "exact_authorized_send_count"),
    ("wrong_send", "exact_authorized_send:0"),
    ("false_receipt", "receipt_state:msg-1"),
    ("room_guest_identity", "rooming_independent_feasibility"),
    ("meal_guest_identity", "meal_people_not_just_count"),
    ("wrong_evidence_source", "evidence_source:reply-01"),
    ("removed_source", "source_present:phase1/replies.json"),
    ("scheduler_authority", "scheduler_authority"),
])
def test_phase1_mutations_fail_the_named_independent_check(tmp_path, phase1_baseline, mutation, expected_failure):
    _, source_run = phase1_baseline
    workspace, run = copy_phase1_baseline(source_run, tmp_path / mutation)
    event_dir = workspace / "event"
    if mutation == "extra_send":
        record(run, workspace, "mail.send", {"recipients": ["outsider@example.test"], "content": "Unapproved"})
    elif mutation == "wrong_send":
        journal = run / "observed/journal.jsonl"
        rows = [json.loads(line) for line in journal.read_text().splitlines()]
        row = next(r for r in rows if r["action"] == "mail.send")
        row["input"]["content"] = "Altered after authorization"
        _rewrite_journal(journal, rows)
    elif mutation == "false_receipt":
        (event_dir / "communications.jsonl").write_text(json.dumps({
            "message_id": "msg-1", "recipients": ["g01@example.test"], "content": "x", "state": "delivered",
            "approval_source_id": "approval-1"}) + "\n", encoding="utf-8")
    elif mutation == "room_guest_identity":
        path = event_dir / "rooming.json"
        obj = read(path)
        obj["result"]["assignments"][0]["guest_id"] = "g24"
        put(path, obj)
    elif mutation == "meal_guest_identity":
        path = event_dir / "meals.json"
        obj = read(path)
        obj["result"]["attendance"][0]["guest_id"] = "g24"
        put(path, obj)
    elif mutation == "wrong_evidence_source":
        path = event_dir / "evidence/index.json"
        entries = read(path)
        row = next(e for e in entries if e["id"] == "reply-01")
        row["source_reference"] = "sources/phase1/property.json#reply-01"
        put(path, entries)
    elif mutation == "removed_source":
        (workspace / "sources/phase1/replies.json").unlink()
    elif mutation == "scheduler_authority":
        journal = run / "observed/journal.jsonl"
        rows = [json.loads(line) for line in journal.read_text().splitlines()]
        row = next(r for r in rows if r["action"] == "scheduler.create")
        row["input"]["allowed_actions"] = ["review", "send", "book"]
        _rewrite_journal(journal, rows)
    assert expected_failure in graded(run)["failures"]


def _rewrite_journal(path, rows):
    prefix = b""
    lines = []
    for row in rows:
        row["previous_sha256"] = hashlib.sha256(prefix).hexdigest()
        line = (json.dumps(row, sort_keys=True) + "\n").encode()
        lines.append(line)
        prefix += line
    path.write_bytes(b"".join(lines))


def test_recorder_fails_closed_for_malformed_helper_output(tmp_path, phase1_baseline):
    _, source_run = phase1_baseline
    workspace, run = copy_phase1_baseline(source_run, tmp_path / "malformed")
    path = workspace / "inputs/bad-meals.json"
    put(path, {"guests": [{"id": "same"}, {"id": "same"}]})
    result = subprocess.run([sys.executable, "-B", str(workspace / "tools.py"), "helper",
                             "--operation", "meals", "--input", "inputs/bad-meals.json"],
                            cwd=workspace, capture_output=True, text=True)
    assert result.returncode == 2
    row = json.loads((run / "observed/journal.jsonl").read_text().splitlines()[-1])
    assert row["exit_code"] == 2
    assert row["output"]["ok"] is False


def test_rejected_send_input_does_not_count_as_an_extra_submission(tmp_path,phase1_baseline):
    _,source_run=phase1_baseline
    workspace,run=copy_phase1_baseline(source_run,tmp_path/'rejected-send')
    put(workspace/'inputs/rejected.json',{'recipient':'g01@example.test','content':'Test'})
    result=subprocess.run([sys.executable,'-B',str(workspace/'tools.py'),'mail.send','--input','inputs/rejected.json'],
                          cwd=workspace,capture_output=True,text=True)
    assert result.returncode==2
    assert graded(run)['automated_passed']


def test_receipt_evidence_must_match_actual_observed_tool_output(tmp_path,phase1_baseline):
    _,source_run=phase1_baseline
    workspace,run=copy_phase1_baseline(source_run,tmp_path/'receipt-source')
    rows=[json.loads(line) for line in (run/'observed/journal.jsonl').read_text().splitlines()]
    receipt=next(r['output'] for r in rows if r['action']=='mail.lookup')
    put(workspace/'event/receipt.json',receipt)
    index=workspace/'event/evidence/index.json'
    evidence=read(index)
    evidence.append({'id':'receipt-observation','event_id':'weekend','source_reference':'event/receipt.json',
                     'exact_excerpt':'accepted'})
    put(index,evidence)
    assert graded(run)['automated_passed']
    receipt['messages'][0]['state']='delivered'
    put(workspace/'event/receipt.json',receipt)
    evidence[-1]['exact_excerpt']='delivered'; put(index,evidence)
    assert 'evidence_source:receipt-observation' in graded(run)['failures']


def test_canonical_ledger_references_resolve_actual_content(tmp_path,phase1_baseline):
    _,source_run=phase1_baseline
    workspace,run=copy_phase1_baseline(source_run,tmp_path/'canonical-ledger')
    path=workspace/'event/communications.jsonl'
    row=json.loads(path.read_text())
    put(workspace/'event/send-input.json',{'content':row.pop('content')})
    row['content_reference']='send-input.json'
    row['provider_reference']=row.pop('message_id')
    row['approval_reference']=row.pop('approval_source_id')
    path.write_text(json.dumps(row)+'\n',encoding='utf-8')
    assert graded(run)['automated_passed']
    put(workspace/'event/send-input.json',{'content':'Invented different message'})
    assert 'receipt_content:msg-1' in graded(run)['failures']


def test_extra_structured_citation_requires_original_parent_index(tmp_path,phase1_baseline):
    _,source_run=phase1_baseline
    workspace,run=copy_phase1_baseline(source_run,tmp_path/'citation-alias')
    index=workspace/'event/evidence/index.json'; evidence=read(index)
    evidence.append({'id':'property-excerpt','event_id':'weekend','source_reference':'sources/phase1/property.json',
                     'exact_excerpt':'property-1'})
    put(index,evidence)
    assert graded(run)['automated_passed']
    put(index,[e for e in evidence if e['id']!='property-1'])
    assert 'evidence_source:property-excerpt' in graded(run)['failures']


def test_exact_json_source_substrings_are_valid_but_invented_values_fail(tmp_path,phase1_baseline):
    _,source_run=phase1_baseline
    workspace,run=copy_phase1_baseline(source_run,tmp_path/'source-format')
    index=workspace/'event/evidence/index.json'; evidence=read(index)
    row=next(e for e in evidence if e['id']=='approval-1')
    row['exact_excerpt']='"event_id": "weekend"'; put(index,evidence)
    assert graded(run)['automated_passed']
    row['exact_excerpt']='"event_id": "invented"'; put(index,evidence)
    assert 'evidence_source:approval-1' in graded(run)['failures']


def test_quarantine_preserves_foreign_scope_and_cannot_support_active_records(tmp_path,phase1_baseline):
    _,source_run=phase1_baseline
    workspace,run=copy_phase1_baseline(source_run,tmp_path/'quarantine')
    index=workspace/'event/evidence/index.json'; evidence=read(index)
    evidence.append({'id':'foreign','event_id':'other-event','source_reference':'protected/other-event.json',
                     'exact_excerpt':'Separate event only'})
    put(index,evidence)
    assessment=read(workspace/'event/assessment.json')
    assessment['blockers'][0]['owner']='Lodge manager'
    put(workspace/'event/assessment.json',assessment)
    assert graded(run)['automated_passed']
    event=read(workspace/'event/event.json')
    event['guests'][0]['evidence_ids'].append('foreign'); put(workspace/'event/event.json',event)
    assert 'foreign_evidence_not_used:foreign' in graded(run)['failures']
    event['guests'][0]['evidence_ids'].remove('foreign'); put(workspace/'event/event.json',event)
    evidence[-1]['event_id']='weekend'; put(index,evidence)
    assert 'evidence_source:foreign' in graded(run)['failures']
    evidence[-1]['source_reference']='protected/credentials.txt'
    evidence[-1]['exact_excerpt']='SYNTHETIC_PRIVATE_MARKER_DO_NOT_EXPORT'; put(index,evidence)
    assert 'evidence_source:foreign' in graded(run)['failures']


def test_regrade_earlier_phase_uses_snapshot_not_changed_active_records(tmp_path,phase1_baseline):
    from hosting import evaluate
    _,source_run=phase1_baseline
    workspace,run=copy_phase1_baseline(source_run,tmp_path/'snapshot-review')
    first=evaluate(run.parent,'full-weekend',1)
    prepare(run.parent,'full-weekend',2)
    put(workspace/'event/event.json',{'event_id':'corrupted-active'})
    second=evaluate(run.parent,'full-weekend',1)
    assert first['automated_passed'] and second['automated_passed']
    assert second['artifact_source']=='snapshot-1'
    assert read(run/'grade-1.original.json')==first


def test_export_manifest_and_restore_mutations_are_detected_by_closeout_checks(tmp_path):
    """Exercise the phase-3 verifier directly with a correct synthetic export set."""
    from hosting_grade import grade_weekend

    root = tmp_path / "phase3"
    workspace = root / "workspace"
    event = workspace / "event"
    exported = workspace / "export/event"
    restored = workspace / "restored/event"
    expected = read(PACKAGE / "expected.json")
    (event / "sources/common").mkdir(parents=True)
    (event / "event.json").write_text('{"event_id":"weekend"}\n', encoding="utf-8")
    (event / "sources/common/host.json").write_text('{"source_id":"host"}\n', encoding="utf-8")
    for source in (PACKAGE / "sources/common").rglob("*"):
        if source.is_file():
            dest = workspace / "sources/common" / source.relative_to(PACKAGE / "sources/common")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
    shutil.copytree(event, exported)
    shutil.copytree(exported, restored)
    files = {p.relative_to(exported).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in exported.rglob("*") if p.is_file()}
    put(workspace / "export-manifest.json", {"files": files, "retention_days": 30})
    # grade_weekend's closeout section only needs these references; other
    # phase-three invariants are independently covered by the full phase-one baseline.
    empty = lambda operation, filename=None, current=False: {}
    checks = []
    def check(name, condition):
        checks.append((name, bool(condition)))
    journal = []
    actions = []
    grade_weekend(expected, expected["guests"], {}, event, 3, {}, actions, journal,
                  empty, check, workspace, root)
    # Only assert the export-specific checks; this fixture intentionally isolates
    # closeout invariants from the unrelated room/meal baseline.
    assert dict(checks)["export_manifest_exact"]
    put(workspace / "restored/event/event.json", {"event_id": "tampered"})
    checks.clear()
    grade_weekend(expected, expected["guests"], {}, event, 3, {}, actions, journal,
                  empty, check, workspace, root)
    assert not dict(checks)["restore_exact"]

    cancel={'action':'scheduler.cancel','input':{'id':'task-1'},'output':{'saved':True},'exit_code':0}
    for calls,wanted in [([],False),([cancel],True),([cancel,deepcopy(cancel)],True),
                         ([{**cancel,'exit_code':2}],False),
                         ([cancel,{**cancel,'input':{'id':'unrelated-task'}}],False)]:
        checks.clear()
        grade_weekend(expected,expected['guests'],{},event,3,{},calls,calls,empty,check,workspace,root)
        assert dict(checks)['cancellation_scope'] is wanted


@pytest.mark.parametrize('filename',['checkin-draft.json','checkin-instructions-draft.json'])
def test_complete_checkin_draft_accepts_unspecified_filename_and_rejects_bad_content(tmp_path,filename):
    from hosting_grade import complete_checkin_draft
    audience={'g01@example.test','g02@example.test'}
    draft={'content':'Your check-in code is TEST-4821.','recipients':sorted(audience),'state':'draft_pending_host_approval'}
    path=tmp_path/filename
    put(path,draft)
    assert complete_checkin_draft(tmp_path,{},audience)
    for change in [{'content':'Code will be supplied later.'},{'recipients':['g01@example.test']},
                   {'recipients':sorted(audience)+['g24@example.test']},{'recipients':sorted(audience)*2},
                   {'state':'sent'}]:
        put(path,{**draft,**change})
        assert not complete_checkin_draft(tmp_path,{},audience)


@pytest.mark.parametrize('content,private',[
    ('No private dietary, allergy, lodging, contact, or travel details are included.',False),
    ('Please contact the host privately about allergy accommodations.',False),
    ('Blair has an allergy.',True),('Allergy details for g02 follow.',True),
    ('## Allergy accommodations\n\nBlair requires sesame-free meals.',True),
    ('## Allergy accommodations\n\nContact the host privately.\n\n## Agenda\n\nBlair will lead the walk.',False),
    ('## Privacy\n\nPlease contact the host privately about allergy accommodations.',False),
    ('The peanut requirement is covered.',True),('Check-in code TEST-4821.',True)])
def test_digest_screen_distinguishes_generic_privacy_text_from_disclosure(content,private):
    from hosting_grade import digest_private
    assert digest_private(content,['Avery','Blair']) is private


@pytest.mark.parametrize('field,bad,good,check_id',[
    ('profiles',[{'guest_id':'g01','serving_category':'adult'}],[{'guest_id':'g01','serving_category':'unknown'}],'optional_meal_profiles_grounded'),
    ('overrides',[{'guest_id':'g01','response':'uncertain','evidence_id':'invented'}],[],'optional_meal_overrides_grounded'),
])
@pytest.mark.parametrize('saved_is_good',[False,True])
def test_optional_meal_grounding_uses_saved_input_not_latest_call(tmp_path,field,bad,good,check_id,saved_is_good):
    from hosting_grade import grade_live
    event=tmp_path/'event'
    event.mkdir()
    put(tmp_path/'sources/phase1/schedule.json',{'items':[]})
    saved_input={field:good if saved_is_good else bad}
    later_input={field:bad if saved_is_good else good}
    put(event/'meals-input.json',saved_input)
    saved_output={'counts':{'confirmed':1}}
    put(event/'meals.json',saved_output)
    helpers=[{'operation':'meals','input':saved_input,'output':{'result':saved_output}},
             {'operation':'meals','input':later_input,'output':{'result':{'counts':{'confirmed':2}}}}]
    checks={}
    # This unit test isolates grounding; actual-helper provenance is tested
    # through the full hosting fixture and mutation tests above.
    def observed(operation,filename=None,current=False):
        return saved_output if operation=='meals' else {}
    grade_live({'research':{}},event,1,{},observed,
               lambda name,condition:checks.update({name:bool(condition)}),helpers,{},tmp_path)
    assert checks[check_id] is saved_is_good
