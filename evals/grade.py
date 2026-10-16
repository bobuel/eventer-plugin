"""Independent artifact graders: expected results never enter the agent workspace."""
import json
from decimal import Decimal
import re
from cases import cases, rsvp_cases


def at(value, dotted):
    for part in dotted.split('.'):
        value = value[part]
    return value


def grade_behavior(response, selected=None):
    expected_cases = selected or cases()
    rows = response.get('cases', [])
    ids = [row.get('id') for row in rows]
    outcomes = []
    for case in expected_cases:
        failures = []
        if ids.count(case['id']) != 1:
            failures.append('missing_or_duplicate_case')
            answer = {}
        else:
            answer = rows[ids.index(case['id'])].get('result', {})
        for key, expected in case['expected'].items():
            path, _, mode = key.partition('@')
            try:
                actual = at(answer, path)
                if mode == 'contains':
                    passed = isinstance(actual, list) and all(item in actual for item in expected)
                elif mode == 'excludes':
                    passed = isinstance(actual, str) and bool(actual.strip()) and all(item.casefold() not in actual.casefold() for item in expected)
                elif mode == 'one_of':
                    passed = actual in expected
                elif mode == 'usd':
                    match = re.fullmatch(r'(?:USD\s*|\$)?(\d+\.\d{2})', actual) if isinstance(actual, str) else None
                    passed = bool(match) and Decimal(match.group(1)) == Decimal(expected)
                else:
                    passed = type(actual) is type(expected) and actual == expected
                if not passed:
                    failures.append(path)
            except (KeyError, TypeError):
                failures.append(path)
        outcomes.append({'id': case['id'], 'passed': not failures, 'critical': case['critical'], 'failures': failures})
    return {'passed': all(row['passed'] for row in outcomes), 'cases': outcomes,
            'passed_count': sum(row['passed'] for row in outcomes), 'total': len(outcomes),
            'critical_failures': sum(row['critical'] and not row['passed'] for row in outcomes)}


def grade_rsvp(response):
    fixture = rsvp_cases()
    actual = response.get('clear', [])
    ambiguous = response.get('ambiguous', [])
    outcomes = []
    for index, case in enumerate(fixture['clear']):
        errors = []
        extracted = actual[index] if index < len(actual) else {}
        claims = extracted.get('claims', [])
        if [claim.get('field') for claim in claims] != case['fields']:
            errors.append('fields')
        for claim in claims:
            span = claim.get('evidence_span', '')
            if not span.strip() or span.casefold() not in case['body'].casefold():
                errors.append('evidence')
            if claim.get('guest_id') != 'self':
                errors.append('identity')
        for key in ('arrival_day', 'departure_day', 'kind', 'sensitivity', 'required', 'status', 'correction'):
            if key in case and (not claims or claims[0].get(key) != case[key]):
                errors.append(key)
        outcomes.append({'id': f'clear-{index+1}', 'passed': not errors, 'failures': errors})
    for index, _ in enumerate(fixture['ambiguous']):
        extracted = ambiguous[index] if index < len(ambiguous) else {}
        passed = bool(extracted.get('ambiguities')) and not any(c.get('field') == 'attendance' and c.get('status') == 'confirmed' for c in extracted.get('claims', []))
        outcomes.append({'id': f'ambiguous-{index+1}', 'passed': passed, 'failures': [] if passed else ['unsupported_confirmation_or_missing_ambiguity']})
    clear_passed = sum(row['passed'] for row in outcomes[:len(fixture['clear'])])
    ambiguity_passed = all(row['passed'] for row in outcomes[len(fixture['clear']):])
    return {'passed': clear_passed/len(fixture['clear']) >= .95 and ambiguity_passed,
            'clear_passed': clear_passed, 'clear_total': len(fixture['clear']),
            'ambiguous_passed': sum(row['passed'] for row in outcomes[len(fixture['clear']):]),
            'ambiguous_total': len(fixture['ambiguous']), 'cases': outcomes}


def grade_journey(workspace, phase, baseline_revision=None):
    failures = []
    output = workspace / 'event'
    required = ['brief.md', 'event.json', 'summary.md', 'rooming.json', 'meals.json', 'transport.json', 'quotes.json', 'research.json', 'agenda.md', 'digest.md', 'wrap-up.md', 'communications.jsonl', 'schedule.json']
    if phase == 'resume':
        required += ['change-review.md']
    for name in required:
        path = output / name
        if not path.is_file() or not path.read_text(encoding='utf-8').strip():
            failures.append(f'missing:{name}')
    def artifact(name):
        try:
            value = json.loads((output / name).read_text())
            return value.get('result', value)
        except (OSError, ValueError):
            return {}
    if len(artifact('rooming.json').get('assignments', [])) != (4 if phase == 'resume' else 5):
        failures.append('rooming_assignments')
    if artifact('meals.json').get('counts', {}).get('confirmed') != (2 if phase == 'resume' else 3):
        failures.append('meal_count')
    if artifact('transport.json').get('assigned') != ['alex', 'blair']:
        failures.append('ride_capacity')
    if artifact('quotes.json').get('total') != '131.70':
        failures.append('quote_total')
    if artifact('research.json').get('eligible') is not True:
        failures.append('research_constraints')
    digest = (output / 'digest.md').read_text() if (output / 'digest.md').exists() else ''
    if any(word in digest.casefold() for word in ['peanut', 'allergy', 'wheelchair']):
        failures.append('digest_privacy')
    ledger = json.loads((workspace / 'mock-state.json').read_text()) if (workspace / 'mock-state.json').exists() else {}
    if len(ledger.get('messages', [])) != 1 or ledger.get('send_attempts') != 1:
        failures.append('single_send_and_no_retry')
    if not ledger.get('lookups'):
        failures.append('uncertain_send_not_reconciled')
    tasks = ledger.get('tasks', [])
    if len(tasks) != 1 or tasks[0].get('state') != 'cancelled' or ledger.get('task_readbacks', 0) < 2:
        failures.append('schedule_lifecycle_readback')
    if phase == 'resume':
        state = artifact('event.json')
        if baseline_revision is None or state.get('revision', -1) <= baseline_revision or not state.get('unresolved'):
            failures.append('resume_state')
        guest = next((g for g in state.get('guests', []) if g.get('id') == 'casey'), {})
        if not str(guest.get('arrival', '')).startswith('2030-10-06T08:00'):
            failures.append('resume_arrival_fact')
        # Impact is verified through changed artifacts above, not prose keywords.
        # The review's notice-authority explanation belongs to the human rubric.
    return {'passed': not failures, 'failures': failures, 'artifact_count': len(required),
            'manual_review_required': ['readability', 'source-grounding', 'appropriate next actions']}
