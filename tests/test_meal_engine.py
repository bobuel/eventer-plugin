# Adapted original assertions; service-bound cases excluded in evals/traceability.json.
from datetime import datetime
from time import perf_counter
from uuid import uuid4
import pytest
from engines.errors import DomainError
from engines.meal_engine import attendance, calculate

def meal(start='2026-10-02T18:00:00-04:00', end='2026-10-02T20:00:00-04:00', **extra):
    return {'service_start': start, 'service_end': end, 'timezone': 'America/New_York', 'status': 'planning', 'serving_categories': ['adult', 'child'], **extra}

def guest(identity='g1', **extra):
    return {'id': identity, 'name': 'Synthetic Guest', 'rsvp_status': 'confirmed', 'precision': 'exact_time', 'arrival': '2026-10-02T12:00:00-04:00', 'departure': '2026-10-04T10:00:00-04:00', 'truth_state': 'confirmed', **extra}

def report(guests=None, **extra):
    args = {'meal': meal(), 'guests': guests or [guest()], 'overrides': [], 'profiles': [], 'needs': [], 'accommodations': [], 'requirements': []}
    args.update(extra)
    return calculate(**args)

def test_arrival_and_departure_boundaries_use_declared_window():
    breakfast = meal('2026-10-02T08:00:00-04:00', '2026-10-02T09:30:00-04:00')
    assert attendance(breakfast, guest(), None)['state'] == 'absent'
    assert attendance(meal(), guest(), None)['state'] == 'confirmed'
    assert attendance(meal(), guest(arrival='2026-10-02T20:00:00-04:00'), None)['state'] == 'absent'
    assert attendance(meal(), guest(departure='2026-10-02T18:00:00-04:00'), None)['state'] == 'absent'
    assert attendance(meal(), guest(departure='2026-10-02T18:01:00-04:00'), None)['state'] == 'confirmed'

def test_dst_offset_conversion_and_uncertain_dates():
    dst_meal = meal('2026-11-01T01:15:00-05:00', '2026-11-01T01:45:00-05:00')
    visiting = guest(arrival='2026-11-01T05:30:00+00:00', departure='2026-11-01T06:30:00+00:00')
    assert attendance(dst_meal, visiting, None)['state'] == 'confirmed'
    assert attendance(meal(), guest(precision='date'), None)['state'] == 'possible'
    assert attendance(meal(), guest(arrival='2026-10-01T12:00:00-04:00', precision='date'), None)['state'] == 'confirmed'

def test_explicit_responses_override_and_preserve_evidence():
    for response, state in (('in', 'confirmed'), ('out', 'absent'), ('uncertain', 'possible')):
        value = attendance(meal(), guest(rsvp_status='unknown', arrival=None), {'response': response, 'evidence_id': 'evidence'})
        assert value == {'state': state, 'reason': 'explicit_' + response, 'evidence_id': 'evidence'}

def test_unknowns_never_covered_and_serving_category_never_inferred():
    value = report([guest(rsvp_status='unknown', arrival=None, name='Baby Child')])
    assert value['counts']['unknown'] == 1
    assert value['serving_counts']['unknown']['unknown'] == 1
    assert value['coverage'] == [{'category': 'unknown', 'need_type': 'unknown', 'state': 'unknown', 'count': 1}]
    assert value['unknown_dietary_count'] == 1

def test_coverage_states_and_allergy_is_not_a_preference():
    needs = [{'guest_id': 'g1', 'category': 'peanut_free', 'need_type': 'allergy', 'requirement_id': 'r1', 'evidence_id': 'e1', 'restricted_note': 'Private synthetic context'}]
    profile = [{'guest_id': 'g1', 'dietary_status': 'has_needs', 'serving_category': 'child'}]
    value = report(needs=needs, profiles=profile, accommodations=[{'category': 'peanut_free', 'need_type': 'preference', 'state': 'covered', 'evidence_id': 'menu'}])
    assert value['coverage'][0]['state'] == 'uncovered'
    for state in ('covered', 'provisional', 'confirm', 'uncovered'):
        menu = [{'category': 'peanut_free', 'need_type': 'allergy', 'state': state, 'evidence_id': 'menu'}]
        value = report(needs=needs, profiles=profile, accommodations=menu)
        assert value['coverage'][0]['state'] == state
        assert value['serving_counts']['child']['confirmed'] == 1
    value = report([guest(rsvp_status='possible')], needs=needs, profiles=profile, accommodations=menu[:0] + [{'category': 'peanut_free', 'need_type': 'allergy', 'state': 'covered', 'evidence_id': 'menu'}])
    assert value['coverage'][0]['state'] == 'provisional'

def test_unmapped_gate_a_requirement_is_visible_even_if_no_needs_answer():
    value = report(profiles=[{'guest_id': 'g1', 'dietary_status': 'no_needs'}], requirements=[{'id': 'r1', 'guest_id': 'g1', 'kind': 'allergy', 'description': 'Sensitive source', 'evidence_id': 'e1'}])
    assert value['unmapped_requirement_count'] == 1
    assert value['coverage'] == [{'category': 'unmapped', 'need_type': 'allergy', 'state': 'confirm', 'count': 1}]

def test_repeated_requirement_category_counts_each_guest_once():
    needs = [{'guest_id': 'g1', 'category': 'peanut_free', 'need_type': 'allergy', 'requirement_id': str(index), 'evidence_id': 'e1'} for index in range(2)]
    value = report(needs=needs, profiles=[{'guest_id': 'g1', 'dietary_status': 'has_needs'}])
    assert value['coverage'][0]['count'] == 1
    assert len(value['details']) == 2

def test_cancelled_meal_does_not_count_explicit_optin():
    value = report(meal=meal(status='cancelled'), overrides=[{'guest_id': 'g1', 'response': 'in', 'evidence_id': 'e1'}])
    assert value['counts']['absent'] == 1
    assert value['coverage'] == []

def test_count_is_stable_under_permutation_and_100_guest_benchmark():
    guests = [guest(str(index)) for index in range(100)]
    start = perf_counter()
    value = report(guests)
    duration = perf_counter() - start
    assert value == report(list(reversed(guests)))
    assert value['counts']['confirmed'] == 100
    assert duration < 1.0

def test_naive_timestamp_rejected():
    with pytest.raises(ValueError, match='offset'):
        attendance(meal(service_start=datetime(2026, 10, 2, 18)), guest(), None)
