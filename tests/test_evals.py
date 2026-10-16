from copy import deepcopy
from cases import cases
from grade import grade_behavior, grade_rsvp
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
