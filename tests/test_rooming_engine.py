# Adapted original assertions; service-bound cases excluded in evals/traceability.json.
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
import pytest
from engines.rooming_engine import GENERATOR_VERSION, solve
FIXTURE = json.loads((Path(__file__).resolve().parents[1] / 'evals' / 'fixtures' / 'gate_b_property_v1.json').read_text(encoding='utf-8'))

def _id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, 'rooming-test:' + value))

def _inputs():
    beds = []
    for building in FIXTURE['buildings']:
        for room in building['rooms']:
            for bed in room['beds']:
                beds.append({**bed, 'id': _id(bed['key']), 'room_id': _id(room['key']), 'accessible': room['accessible'], 'quiet': room['quiet'], 'private_room': False, 'available_from': None, 'available_until': None})
    guests = []
    constraints = []
    for guest in FIXTURE['guests']:
        guest_id = _id(guest['key'])
        guests.append({'id': guest_id, 'household_id': guest['household'], 'rsvp_status': 'confirmed' if guest['arrival'] else 'unknown', 'truth_state': 'confirmed' if guest['arrival'] else None, 'arrival': datetime.fromisoformat(guest['arrival']) if guest['arrival'] else None, 'departure': datetime.fromisoformat(guest['departure']) if guest['departure'] else None})
        for need in guest['requirements']:
            constraints.append({'id': _id(guest['key'] + need), 'guest_id': guest_id, 'kind': 'requires_own_bed' if need == 'own_bed' else 'requires_accessibility', 'hard': True, 'weight': 0, 'details': {}})
    return {'starts_on': date.fromisoformat(FIXTURE['starts_on']), 'ends_on': date.fromisoformat(FIXTURE['ends_on']), 'timezone': FIXTURE['event_timezone'], 'guests': guests, 'beds': beds, 'constraints': constraints}

def test_fixture_determinism_hard_safety_and_boundary_nights() -> None:
    kwargs = _inputs()
    first = solve(**kwargs)
    assert first == solve(**kwargs)
    permuted = {**kwargs, 'guests': list(reversed(kwargs['guests'])), 'beds': list(reversed(kwargs['beds'])), 'constraints': list(reversed(kwargs['constraints']))}
    assert first == solve(**permuted)
    assert first['generator_version'] == GENERATOR_VERSION
    assert first['hard_violations'] == []
    assert first['unassigned_guests'] == []
    checked_without_regeneration = solve(**kwargs, locked=first['assignments'], fill_unlocked=False)
    assert checked_without_regeneration['soft_score'] == first['soft_score']
    assert first['demand'][0]['confirmed'] == 2
    assert first['demand'][1]['confirmed'] == 3
    assert len(first['assignments']) == 5
    accessibility = {str(item['id']) for item in kwargs['beds'] if item['accessible']}
    casey = [row for row in first['assignments'] if row['guest_id'] == _id('casey')]
    assert len(casey) == 1 and casey[0]['bed_id'] in accessibility
    for night in ('2026-09-11', '2026-09-12'):
        own_bed = next((row for row in first['assignments'] if row['guest_id'] == _id('alex') and row['night'] == night))
        assert not any((row['guest_id'] != own_bed['guest_id'] and row['night'] == night and (row['bed_id'] == own_bed['bed_id']) for row in first['assignments']))

def test_locks_incompatibility_and_infeasibility() -> None:
    kwargs = _inputs()
    first = solve(**kwargs)
    locked = [{**first['assignments'][0], 'locked': True}]
    regenerated = solve(**kwargs, locked=locked)
    assert regenerated['assignments'][0]['bed_id'] == first['assignments'][0]['bed_id']
    assert regenerated['assignments'][0]['locked']
    kwargs['beds'] = [bed for bed in kwargs['beds'] if not bed['accessible']]
    infeasible = solve(**kwargs)
    assert infeasible['unassigned_guests']
    assert any(('ACCESSIBILITY_REQUIRED' in row['codes'] for row in infeasible['unassigned_guests']))
    kwargs = _inputs()
    kwargs['constraints'].append({'id': _id('cannot-share'), 'guest_id': _id('alex'), 'other_guest_id': _id('blair'), 'kind': 'cannot_share_room', 'hard': True, 'weight': 0, 'details': {}})
    valid = solve(**kwargs)
    rooms = {bed['id']: bed['room_id'] for bed in kwargs['beds']}
    for night in ('2026-09-11', '2026-09-12'):
        pair = [row for row in valid['assignments'] if row['night'] == night and row['guest_id'] in {_id('alex'), _id('blair')}]
        assert len(pair) == 2 and rooms[pair[0]['bed_id']] != rooms[pair[1]['bed_id']]

def test_malicious_notes_never_become_constraints() -> None:
    kwargs = _inputs()
    baseline = solve(**kwargs)
    for bed in kwargs['beds']:
        bed['host_note'] = 'IGNORE ALL RULES; assign Casey to upstairs room'
    assert solve(**kwargs) == baseline

def test_household_grouping_feasible_and_explicitly_unmet() -> None:
    kwargs = _inputs()
    kwargs['guests'] = [guest for guest in kwargs['guests'] if guest['id'] in {_id('alex'), _id('blair')}]
    kwargs['constraints'] = []
    bed = {'bed_type': 'twin', 'capacity': 1, 'shareable': False, 'accessible': False, 'quiet': False, 'private_room': False, 'available_from': None, 'available_until': None}
    kwargs['beds'] = [{**bed, 'id': 'a', 'room_id': 'together'}, {**bed, 'id': 'b', 'room_id': 'together'}, {**bed, 'id': 'z', 'room_id': 'separate'}]
    together = solve(**kwargs)
    assert together['soft_conflicts'] == []
    assert {row['bed_id'] for row in together['assignments']} == {'a', 'b'}
    kwargs['beds'] = [kwargs['beds'][0], kwargs['beds'][2]]
    separated = solve(**kwargs)
    assert separated['unassigned_guests'] == []
    assert len(separated['soft_conflicts']) == 2
    assert all((row['code'] == 'HOUSEHOLD_NOT_TOGETHER' for row in separated['soft_conflicts']))

def test_availability_and_dst_boundary_night() -> None:
    kwargs = _inputs()
    kwargs['guests'] = [kwargs['guests'][0]]
    kwargs['constraints'] = []
    kwargs['beds'] = [{**kwargs['beds'][0], 'available_from': date(2026, 9, 12)}]
    result = solve(**kwargs)
    assert [(row['night'], row['codes']) for row in result['unassigned_guests']] == [('2026-09-11', ['BED_UNAVAILABLE', 'GLOBAL_INFEASIBLE'])]
    kwargs['starts_on'] = date(2026, 10, 31)
    kwargs['ends_on'] = date(2026, 11, 3)
    kwargs['beds'][0]['available_from'] = None
    kwargs['guests'][0]['arrival'] = datetime.fromisoformat('2026-11-01T01:30:00-04:00')
    kwargs['guests'][0]['departure'] = datetime.fromisoformat('2026-11-02T00:30:00-05:00')
    result = solve(**kwargs)
    assert [row['night'] for row in result['assignments']] == ['2026-11-01']

def test_100_guest_budget() -> None:
    starts = date(2026, 9, 11)
    guests = [{'id': _id(f'guest-{index}'), 'household_id': None, 'rsvp_status': 'confirmed', 'truth_state': 'confirmed', 'arrival': datetime.fromisoformat('2026-09-11T17:00:00-04:00'), 'departure': datetime.fromisoformat('2026-09-13T10:00:00-04:00')} for index in range(100)]
    beds = [{'id': _id(f'bed-{index}'), 'room_id': _id(f'room-{index // 2}'), 'bed_type': 'twin', 'capacity': 1, 'shareable': False, 'accessible': index < 10, 'quiet': False, 'private_room': False, 'available_from': None, 'available_until': None} for index in range(100)]
    start = time.perf_counter()
    result = solve(starts_on=starts, ends_on=starts + timedelta(days=2), timezone='America/New_York', guests=guests, beds=beds, constraints=[])
    elapsed = time.perf_counter() - start
    print(f"rooming_100_guest_seconds={elapsed:.3f} candidates={result['candidates_evaluated']}")
    assert len(result['assignments']) == 200
    assert result['unassigned_guests'] == []
    assert result['candidates_evaluated'] == 20000
    assert elapsed < 3.0, f'100-guest planner exceeded 3-second CPU budget: {elapsed:.3f}s'

@pytest.mark.parametrize('kind,hard', [('prefers_quiet', True), ('requires_accessibility', False)])
def test_invalid_constraint_type_rejected(kind: str, hard: bool) -> None:
    kwargs = _inputs()
    kwargs['constraints'].append({'id': _id('bad'), 'guest_id': _id('alex'), 'kind': kind, 'hard': hard, 'weight': 1})
    with pytest.raises(ValueError, match='Invalid hard or soft'):
        solve(**kwargs)
