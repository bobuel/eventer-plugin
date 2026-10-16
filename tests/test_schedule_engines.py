# Adapted original assertions; service-bound cases excluded in evals/traceability.json.
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
import pytest
from engines.errors import DomainError
from engines.research import FakeResearchAdapter, evaluate, public_source
from engines.transport_engine import audience, local_instant, plan_ride
FIXTURE = json.loads((Path(__file__).parents[1] / 'evals/fixtures/gate_c_journey_v1.json').read_text())

def test_local_time_dst_fold_roundtrip_and_gap_rejection():
    early = local_instant('2026-11-01T01:30:00-04:00', 'America/New_York')
    late = local_instant('2026-11-01T01:30:00-05:00', 'America/New_York')
    assert late - early == timedelta(hours=1)
    for invalid in ['2026-03-08T02:30:00-05:00', '2026-03-08T02:30:00-04:00', '2026-11-06T18:00:00', '2026-11-06T18:00:00-04:00']:
        with pytest.raises(DomainError):
            local_instant(invalid, 'America/New_York')

def test_audience_requires_full_confirmed_interval_and_honors_optouts():
    item = {**FIXTURE['schedule'], 'audience_rule': 'confirmed_present', 'opt_out_ids': ['out']}
    guests = [{'id': g, 'rsvp_status': 'unknown' if g == 'unknown' else 'confirmed'} for g in ['whole', 'partial', 'out', 'unknown']]
    segments = [{'guest_id': g['id'], 'truth_state': 'confirmed', 'active': True, 'arrival_at': '2026-11-06T18:30:00-05:00' if g['id'] == 'partial' else '2026-11-06T17:00:00-05:00', 'departure_at': '2026-11-06T20:00:00-05:00'} for g in guests]
    result = audience(item, guests, segments)
    assert result['guest_ids'] == ['whole']
    assert {m['reason'] for m in result['members']} == {'confirmed_present', 'outside_attendance_window', 'explicit_opt_out', 'attendance_unconfirmed'}
    assert audience({**item, 'audience_rule': 'selected', 'guest_ids': []}, guests, segments)['guest_ids'] == []

def ride_fixture():
    ride = {'vehicle_id': 'v', 'driver_id': 'd', 'starts_at': '2026-11-06T16:00:00-05:00', 'ends_at': '2026-11-06T17:00:00-05:00', 'origin': 'Station', 'destination': 'Lodge', 'guest_ids': ['a', 'b', 'c'], 'buffer_minutes': 15}
    vehicle = {'id': 'v', 'driver_id': 'd', 'driver_authorized': True, 'passenger_seats': FIXTURE['transport']['passenger_seats'], 'accessible': True, 'child_seats': 1}
    travelers = [{'guest_id': g, 'pickup_permission': True, 'available_from': '2026-11-06T15:00:00-05:00', 'available_until': '2026-11-06T18:00:00-05:00', 'origin': 'Station', 'destination': 'Lodge', 'accessible_required': False, 'child_seat_required': False} for g in ride['guest_ids']]
    return (ride, vehicle, travelers)

def test_ride_capacity_and_deterministic_waitlist():
    ride, vehicle, travelers = ride_fixture()
    result = plan_ride(ride, vehicle, [], travelers)
    assert result['assigned'] == ['a', 'b']
    assert result['waitlist'] == [{'guest_id': 'c', 'reason': 'capacity_waitlist'}]
    assert plan_ride({**ride, 'guest_ids': ['c', 'b', 'a']}, vehicle, [], travelers)['assigned'] == result['assigned']

@pytest.mark.parametrize(('field', 'value', 'reason'), [('pickup_permission', False, 'pickup_permission_missing'), ('available_from', '2026-11-06T16:30:00-05:00', 'outside_travel_window'), ('available_until', '2026-11-06T16:30:00-05:00', 'outside_travel_window'), ('origin', 'Other station', 'pickup_or_destination_mismatch'), ('destination', 'Other lodge', 'pickup_or_destination_mismatch'), ('rsvp_status', 'unknown', 'attendance_unconfirmed')])
def test_ride_rejects_missing_permission_or_unavailable_passenger(field, value, reason):
    ride, vehicle, travelers = ride_fixture()
    travelers[0][field] = value
    result = plan_ride(ride, vehicle, [], travelers)
    assert {'guest_id': 'a', 'reason': reason} in result['waitlist']
    assert 'a' not in result['assigned']

def test_ride_accessibility_and_child_seats_are_hard_constraints():
    ride, vehicle, travelers = ride_fixture()
    vehicle['accessible'] = False
    travelers[0]['accessible_required'] = True
    travelers[1]['child_seat_required'] = travelers[2]['child_seat_required'] = True
    result = plan_ride(ride, vehicle, [], travelers)
    assert result['assigned'] == ['b']
    assert {w['reason'] for w in result['waitlist']} == {'vehicle_inaccessible', 'child_seat_unavailable'}

def test_ride_driver_vehicle_guest_overlaps_and_buffers():
    ride, vehicle, travelers = ride_fixture()
    with pytest.raises(DomainError):
        plan_ride(ride, {**vehicle, 'driver_authorized': False}, [], travelers)
    with pytest.raises(DomainError):
        plan_ride(ride, vehicle, [{**ride, 'starts_at': '2026-11-06T17:10:00-05:00', 'ends_at': '2026-11-06T18:00:00-05:00'}], travelers)
    other = {**ride, 'vehicle_id': 'other', 'driver_id': 'other', 'guest_ids': ['a']}
    assert {'guest_id': 'a', 'reason': 'guest_ride_overlap'} in plan_ride(ride, vehicle, [other], travelers)['waitlist']
    with pytest.raises(DomainError):
        plan_ride(ride, vehicle, [{**other, 'guest_ids': ['d']}], travelers)

def candidate():
    return {'name': 'Synthetic accessible option', 'source_url': FIXTURE['research'][0]['source_url'], 'retrieved_at': datetime.now(UTC), 'accessible': True, 'distance_km': 12, 'travel_minutes': 20, 'max_group_size': 8, 'minimum_age': 0}

def test_research_freshness_and_explicit_disqualifiers():
    c = candidate()
    constraints = {'accessible_required': True, 'max_distance_km': 20, 'max_travel_minutes': 30, 'group_size': 6, 'minimum_age': 2}
    assert evaluate(c, constraints)['eligible']
    result = evaluate({**c, 'accessible': False, 'distance_km': 21, 'retrieved_at': datetime.now(UTC) - timedelta(days=2)}, constraints)
    assert not result['eligible'] and result['stale']
    assert result['disqualified_reasons'] == ['accessibility_not_confirmed', 'exceeds_or_unknown_max_distance_km']
    assert 'require direct confirmation' in result['disclaimer']
    with pytest.raises(DomainError):
        evaluate(c, {'guest_notes': 'Private itinerary'})
    with pytest.raises(DomainError):
        evaluate({**c, 'retrieved_at': datetime.now(UTC) + timedelta(hours=1)}, {})

@pytest.mark.parametrize('url', ['http://example.test', 'https://127.0.0.1/x', 'https://169.254.169.254/latest', 'https://localhost/x', 'https://secrets.internal/x', 'https://user:password@example.test', 'https://example.test/#private', 'file:///tmp/file', 'javascript:alert(1)'])
def test_research_rejects_unsafe_source_urls(url):
    with pytest.raises(DomainError):
        public_source(url)

def test_fake_research_failure_and_no_guest_queries():
    with pytest.raises(DomainError, match='retry'):
        FakeResearchAdapter(fail=True).search({'group_size': 6})
    with pytest.raises(DomainError, match='Raw guest'):
        FakeResearchAdapter().search({'guest_names': ['Synthetic Guest']})
