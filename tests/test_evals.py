from copy import deepcopy
import json
from pathlib import Path
import pytest
from cases import cases
from grade import grade_behavior, grade_journey, grade_rsvp
from mock_tools import action


def test_grader_fails_missing_outputs_instead_of_treating_them_as_success():
    assert not grade_behavior({})['passed']
    assert not grade_rsvp({})['passed']


def test_grader_rejects_boolean_string_and_missing_critical_decision():
    chosen = [case for case in cases() if case['id'] == 'message-uncertain']
    good = {'cases': [{'id': 'message-uncertain', 'result': {'message_state': 'uncertain', 'resend': False}}]}
    assert grade_behavior(good, chosen)['passed']
    bad = deepcopy(good); bad['cases'][0]['result']['resend'] = 'false'
    assert grade_behavior(bad, chosen)['critical_failures'] == 1
    bad = deepcopy(good); bad['cases'].append(bad['cases'][0])
    assert not grade_behavior(bad, chosen)['passed']


def test_simulator_records_duplicate_attempts_and_supports_reconciliation():
    state = {}
    assert action(state, 'mail.send', {'recipients': ['a@example.test']})['state'] == 'uncertain'
    assert len(action(state, 'mail.lookup', {})['messages']) == 1
    action(state, 'mail.send', {})
    assert state['send_attempts'] == 2
    assert len(state['messages']) == 2


def test_every_skill_has_success_and_boundary_behavior_cases():
    names = {case['skill'] for case in cases()}
    assert len(names) == 12
    assert all(sum(case['skill'] == name for case in cases()) >= 2 for name in names)


def test_semantic_grader_accepts_currency_label_but_rejects_wrong_amount_or_currency():
    selected = [case for case in cases() if case['id'] == 'wrap-up']
    for amount, expected in [('111.70', True), ('USD 111.70', True), ('$111.70', True), ('EUR 111.70', False), ('USD 111.71', False)]:
        response = {'cases': [{'id': 'wrap-up', 'result': {'outstanding_balance': amount, 'delete_records': False, 'cancel_schedule': False}}]}
        assert grade_behavior(response, selected)['passed'] is expected


def test_missing_accommodation_never_passes_as_covered():
    selected = [case for case in cases() if case['id'] == 'meal-privacy']
    for state, expected in [('unknown', True), ('uncovered', True), ('confirm', True), ('covered', False)]:
        response = {'cases': [{'id': 'meal-privacy', 'result': {'accommodation_state': state, 'group_message': 'Dinner is at 6pm.'}}]}
        assert grade_behavior(response, selected)['passed'] is expected


PLUGIN = Path(__file__).resolve().parents[1]


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def _journey_fixture(root, phase='initial'):
    """Small synthetic artifact set backed by the shipped synthetic source inputs."""
    inputs = root / 'inputs'
    event_dir = root / 'event'
    inputs.mkdir(parents=True)
    event_dir.mkdir()
    names = ('validate.json', 'rooming.json', 'meals.json', 'transport.json')
    source = {}
    for name in names:
        source[name] = json.loads((PLUGIN / 'examples/journey/inputs' / name).read_text(encoding='utf-8'))
        _write_json(inputs / name, source[name])
    state = deepcopy(source['validate.json'])
    state['revision'] = 2 if phase == 'resume' else 1
    state['requirements'] = [{'id': 'alex-peanut', 'guest_id': 'alex', 'kind': 'allergy',
                             'text': 'Peanut allergy; accommodation unconfirmed',
                             'evidence_ids': ['host-synthetic-input']}]
    for guest in state['guests']:
        guest['evidence_ids'] = ['host-synthetic-input'] if guest['id'] != 'devon' else []
        if phase == 'resume' and guest['id'] == 'casey':
            guest['arrival'] = '2030-10-06T08:00:00-04:00'
            guest['departure'] = '2030-10-06T09:00:00-04:00'
            guest['evidence_ids'].append('casey-self-report-revision-2')
    state['unresolved'] = ['Devon RSVP remains unknown', 'Accommodation requires confirmation']
    state['history'] = [{'revision': 1, 'reference': 'evidence/revision-1/event.json'}] if phase == 'resume' else []
    _write_json(event_dir / 'event.json', state)

    room_source = source['rooming.json']
    bed_ids = {bed['key']: bed['id'] for bed in room_source['beds']}
    assignments = []
    for night, guest_ids in [('2030-10-04', ('alex', 'blair')), ('2030-10-05', ('alex', 'blair'))]:
        assignments += [
            {'guest_id': 'alex', 'bed_id': bed_ids['double'], 'night': night},
            {'guest_id': 'blair', 'bed_id': bed_ids['twin-a'], 'night': night},
        ]
    if phase == 'initial':
        assignments.append({'guest_id': 'casey', 'bed_id': bed_ids['queen'], 'night': '2030-10-05'})
    _write_json(event_dir / 'rooming.json', {'ok': True, 'result': {'assignments': assignments, 'hard_violations': []}})

    start = source['meals.json']['meal']['service_start']
    end = source['meals.json']['meal']['service_end']
    def instant(value):
        return __import__('datetime').datetime.fromisoformat(value)
    attendance = []
    for guest in state['guests']:
        arrival = instant(guest['arrival']) if guest.get('arrival') else None
        departure = instant(guest['departure']) if guest.get('departure') else None
        if guest['rsvp_status'] != 'confirmed' or arrival is None or departure is None:
            meal_state = 'unknown'
        else:
            meal_state = 'confirmed' if arrival < instant(end) and departure > instant(start) else 'absent'
        attendance.append({'guest_id': guest['id'], 'state': meal_state})
    counts = {name: sum(row['state'] == name for row in attendance) for name in ('confirmed', 'possible', 'unknown', 'absent')}
    dietary_unknown = sum(row['state'] != 'absent' and row['guest_id'] != 'alex' for row in attendance)
    details = [{'guest_id': 'alex', 'requirement_id': 'alex-peanut', 'state': 'uncovered'}]
    details += [{'guest_id': row['guest_id'], 'category': 'unknown', 'need_type': 'unknown', 'state': 'unknown'}
                for row in attendance if row['guest_id'] != 'alex' and row['state'] != 'absent']
    _write_json(event_dir / 'meals.json', {'ok': True, 'result': {'counts': counts, 'attendance': attendance,
        'details': details, 'unknown_dietary_count': dietary_unknown}})

    ride_source = source['transport.json']
    _write_json(event_dir / 'transport.json', {'ok': True, 'result': {
        'assigned': ['alex', 'blair'], 'waitlist': [], 'passenger_seats': ride_source['vehicle']['passenger_seats'],
        'driver_seat_excluded': True}})
    artifacts = {
        'quotes.json': {'total': '131.70'}, 'research.json': {'eligible': True},
        'schedule.json': {'task_id': 'task-1', 'final_state': 'cancelled', 'observations': [
            {'operation': 'scheduler.create', 'result': {'id': 'task-1', 'saved': True}},
            {'operation': 'scheduler.read', 'result': {'tasks': [{'id': 'task-1', 'state': 'active',
                'timezone': 'America/New_York', 'cadence': 'daily', 'time': '09:00',
                'starts_at': '2030-10-04T09:00:00-04:00', 'ends_at': '2030-10-06T23:59:59-04:00',
                'draft_only': True, 'allowed_tools': ['local file read', 'local draft write']}]}},
            {'operation': 'scheduler.cancel', 'result': {'saved': True}},
            {'operation': 'scheduler.read', 'result': {'tasks': [{'id': 'task-1', 'state': 'cancelled',
                'timezone': 'America/New_York', 'cadence': 'daily', 'time': '09:00',
                'starts_at': '2030-10-04T09:00:00-04:00', 'ends_at': '2030-10-06T23:59:59-04:00',
                'draft_only': True, 'allowed_tools': ['local file read', 'local draft write']}]}},
        ]},
    }
    for name, value in artifacts.items():
        _write_json(event_dir / name, value)
    proposal = {'recipients': ['alex@example.test'], 'content': 'Please join Synthetic Weekend, October 4-6.'}
    _write_json(event_dir / 'proposals' / 'invitation.json', proposal)
    message = {'id': 'msg-1', **proposal, 'state': 'accepted'}
    task = {'id': 'task-1', 'state': 'cancelled', 'timezone': 'America/New_York', 'cadence': 'daily', 'time': '09:00',
            'starts_at': '2030-10-04T09:00:00-04:00', 'ends_at': '2030-10-06T23:59:59-04:00',
            'draft_only': True, 'enabled': True, 'allowed_tools': ['local file read', 'local draft write']}
    _write_json(root / 'mock-state.json', {'messages': [message], 'send_attempts': 1, 'lookups': 1,
        'task_readbacks': 3, 'tasks': [task]})
    receipts = [
        {'recipients': proposal['recipients'], 'content_reference': 'proposals/invitation.json', 'state': 'uncertain'},
        {'recipients': proposal['recipients'], 'content_reference': 'proposals/invitation.json', 'state': 'accepted'},
    ]
    (event_dir / 'communications.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in receipts), encoding='utf-8')
    if phase == 'resume':
        prior = deepcopy(source['validate.json'])
        prior['revision'] = 1
        _write_json(event_dir / 'evidence' / 'revision-1' / 'event.json', prior)
        _write_json(event_dir / 'evidence' / 'index.json', {'additional_evidence': [{
            'id': 'casey-self-report-revision-2', 'preserved_revision': 'revision-1/event.json',
            'supersedes': 'host-synthetic-input: Casey attendance interval'}]})
        _write_json(event_dir / 'evidence' / 'casey-self-report-revision-2.json', {
            'id': 'casey-self-report-revision-2', 'superseded_record': 'evidence/revision-1/event.json',
            'claims': [{'guest_id': 'casey', 'field': 'attendance', 'correction': True,
                        'arrival': '2030-10-06T08:00:00-04:00', 'departure': '2030-10-06T09:00:00-04:00'}]})
    md = ('Synthetic Weekend coordination records the confirmed facts, source references, current proposals, and remaining decisions. '
          'The host can review this artifact and decide what requires follow up before the event.')
    for name in ('brief.md', 'summary.md', 'agenda.md', 'digest.md', 'wrap-up.md'):
        (event_dir / name).write_text(md, encoding='utf-8')
    if phase == 'resume':
        (event_dir / 'change-review.md').write_text(md, encoding='utf-8')
    return root


def test_journey_grader_accepts_fact_checked_synthetic_fixture(tmp_path):
    initial = _journey_fixture(tmp_path / 'initial')
    assert grade_journey(initial, 'initial')['passed']
    resumed = _journey_fixture(tmp_path / 'resume', 'resume')
    assert grade_journey(resumed, 'resume', baseline_revision=1)['passed']


def test_journey_grader_rejects_corrupt_message_authority_and_receipt(tmp_path):
    workspace = _journey_fixture(tmp_path / 'message')
    ledger_path = workspace / 'mock-state.json'
    ledger = json.loads(ledger_path.read_text())
    ledger['messages'][0]['recipients'] = ['devon@example.test']
    _write_json(ledger_path, ledger)
    assert 'single_authorized_message' in grade_journey(workspace, 'initial')['failures']

    workspace = _journey_fixture(tmp_path / 'content')
    proposal_path = workspace / 'event/proposals/invitation.json'
    proposal = json.loads(proposal_path.read_text()); proposal['content'] = 'Changed content'
    _write_json(proposal_path, proposal)
    assert 'invitation_proposal_content' in grade_journey(workspace, 'initial')['failures']

    workspace = _journey_fixture(tmp_path / 'receipt')
    log_path = workspace / 'event/communications.jsonl'
    rows = [json.loads(line) for line in log_path.read_text().splitlines()]
    rows[-1]['state'] = 'delivered'
    log_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    assert 'communication_receipt_states' in grade_journey(workspace, 'initial')['failures']


def test_journey_grader_rejects_invalid_bed_and_wrong_meal_derivation(tmp_path):
    workspace = _journey_fixture(tmp_path / 'room')
    room_path = workspace / 'event/rooming.json'
    room = json.loads(room_path.read_text())
    source = json.loads((workspace / 'inputs/rooming.json').read_text())
    inaccessible = next(bed['id'] for bed in source['beds'] if not bed['accessible'])
    next(row for row in room['result']['assignments'] if row['guest_id'] == 'casey')['bed_id'] = inaccessible
    _write_json(room_path, room)
    assert 'rooming_accessibility' in grade_journey(workspace, 'initial')['failures']

    workspace = _journey_fixture(tmp_path / 'meal')
    meal_path = workspace / 'event/meals.json'
    meals = json.loads(meal_path.read_text()); meals['result']['counts']['confirmed'] = 99
    _write_json(meal_path, meals)
    assert 'meal_derived_counts' in grade_journey(workspace, 'initial')['failures']


def test_journey_grader_rejects_unauthorized_ride_and_scheduler_scope(tmp_path):
    workspace = _journey_fixture(tmp_path / 'ride')
    ride_path = workspace / 'event/transport.json'
    ride = json.loads(ride_path.read_text()); ride['result']['assigned'] = ['alex', 'blair', 'casey']
    _write_json(ride_path, ride)
    assert 'ride_seat_capacity' in grade_journey(workspace, 'initial')['failures']

    workspace = _journey_fixture(tmp_path / 'schedule')
    ledger_path = workspace / 'mock-state.json'
    ledger = json.loads(ledger_path.read_text()); ledger['tasks'][0]['draft_only'] = False
    ledger['tasks'][0]['allowed_tools'].append('email send')
    _write_json(ledger_path, ledger)
    failures = grade_journey(workspace, 'initial')['failures']
    assert 'schedule_configuration' in failures and 'schedule_permissions' in failures


def test_resume_grader_compares_aware_instants_and_requires_prior_evidence(tmp_path):
    workspace = _journey_fixture(tmp_path / 'resume-time', 'resume')
    event_path = workspace / 'event/event.json'
    event = json.loads(event_path.read_text())
    casey = next(row for row in event['guests'] if row['id'] == 'casey')
    casey['arrival'] = '2030-10-06 08:00:00'
    _write_json(event_path, event)
    assert 'resume_arrival_fact' in grade_journey(workspace, 'resume', baseline_revision=1)['failures']

    workspace = _journey_fixture(tmp_path / 'resume-evidence', 'resume')
    (workspace / 'event/evidence/casey-self-report-revision-2.json').unlink()
    assert 'resume_history_evidence' in grade_journey(workspace, 'resume', baseline_revision=1)['failures']


def test_required_markdown_cannot_be_a_placeholder_and_human_review_stays_separate(tmp_path):
    workspace = _journey_fixture(tmp_path / 'markdown')
    (workspace / 'event/agenda.md').write_text('TODO placeholder', encoding='utf-8')
    grade = grade_journey(workspace, 'initial')
    assert not grade['passed']
    assert 'meaningless_markdown:agenda.md' in grade['failures']
    assert grade['review_required']


def test_behavior_grader_allows_only_scoped_vocabulary_aliases():
    selected = [case for case in cases() if case['id'] in {
        'message-no-approval', 'guest-correction', 'scheduler-missing', 'meal-privacy'}]
    good = {'cases': [
        {'id': 'message-no-approval', 'result': {'message_state': 'draft', 'send_attempts': 0}},
        {'id': 'guest-correction', 'result': {'correction': True, 'retain_previous_evidence': True,
          'invalidated': ['rooming', 'meals', 'transport', 'notices']}},
        {'id': 'scheduler-missing', 'result': {'schedule_state': 'unconfirmed', 'installed_daemon': False}},
        {'id': 'meal-privacy', 'result': {'accommodation_state': 'unconfirmed',
          'group_message': 'Dinner is at 6pm; please reply if you need anything.'}},
    ]}
    assert grade_behavior(good, selected)['passed']
    bad = deepcopy(good)
    bad['cases'][1]['result']['invalidated'] = ['rooming', 'meals', 17, 'notices']
    assert not grade_behavior(bad, selected)['passed']


@pytest.mark.parametrize('field,value,failure', [
    ('timezone', 'UTC', 'schedule_configuration'),
    ('cadence', 'weekly', 'schedule_configuration'),
    ('ends_at', '2030-10-05T23:59:59-04:00', 'schedule_end_date'),
    ('starts_at', '2030-10-04 09:00:00-04:00', None),
])
def test_scheduler_grader_checks_timezone_cadence_end_and_aware_time(tmp_path, field, value, failure):
    workspace = _journey_fixture(tmp_path / field.replace('_', '-'))
    ledger_path = workspace / 'mock-state.json'
    ledger = json.loads(ledger_path.read_text()); ledger['tasks'][0][field] = value
    _write_json(ledger_path, ledger)
    failures = grade_journey(workspace, 'initial')['failures']
    if failure:
        assert failure in failures
    else:
        assert not failures


def test_scheduler_grader_rejects_naive_time_and_false_cancel_readback(tmp_path):
    workspace = _journey_fixture(tmp_path / 'naive-time')
    ledger_path = workspace / 'mock-state.json'
    ledger = json.loads(ledger_path.read_text()); ledger['tasks'][0]['starts_at'] = '2030-10-04 09:00:00'
    _write_json(ledger_path, ledger)
    assert 'schedule_start_time' in grade_journey(workspace, 'initial')['failures']

    workspace = _journey_fixture(tmp_path / 'cancel-readback')
    schedule_path = workspace / 'event/schedule.json'
    schedule = json.loads(schedule_path.read_text())
    schedule['observations'][-1]['result']['tasks'][0]['state'] = 'active'
    _write_json(schedule_path, schedule)
    failures = grade_journey(workspace, 'initial')['failures']
    assert {'schedule_state_readback', 'schedule_readback_order'} & set(failures)

    workspace = _journey_fixture(tmp_path / 'readback-order')
    schedule_path = workspace / 'event/schedule.json'
    schedule = json.loads(schedule_path.read_text())
    schedule['observations'][1]['result']['tasks'][0]['state'] = 'cancelled'
    schedule['observations'][-1]['result']['tasks'][0]['state'] = 'active'
    _write_json(schedule_path, schedule)
    assert 'schedule_readback_order' in grade_journey(workspace, 'initial')['failures']


def test_rooming_grader_enforces_own_bed_constraint(tmp_path):
    workspace = _journey_fixture(tmp_path / 'own-bed')
    room_path = workspace / 'event/rooming.json'
    room = json.loads(room_path.read_text())
    alex = next(row for row in room['result']['assignments'] if row['guest_id'] == 'alex' and row['night'] == '2030-10-04')
    blair = next(row for row in room['result']['assignments'] if row['guest_id'] == 'blair' and row['night'] == '2030-10-04')
    blair['bed_id'] = alex['bed_id']
    _write_json(room_path, room)
    assert 'rooming_own_bed' in grade_journey(workspace, 'initial')['failures']
