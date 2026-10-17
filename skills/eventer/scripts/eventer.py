"""Offline JSON helpers. No credentials, external effects, or implicit state writes."""
import argparse
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from engines import meal_engine, research, rooming_engine, transport_engine, vendor_engine


def timestamp(value):
    return meal_engine.instant(value)


def identities(rows, key='id'):
    values = [str(row[key]) for row in rows]
    if any(not value or value == 'None' for value in values) or len(values) != len(set(values)):
        raise ValueError(f'Missing or duplicate {key}')
    return set(values)


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')


def rooming(data):
    args = deepcopy(data)
    args['starts_on'] = date.fromisoformat(args['starts_on'])
    args['ends_on'] = date.fromisoformat(args['ends_on'])
    ZoneInfo(args['timezone'])
    identities(args['guests'])
    identities(args['beds'])
    identities(args['constraints'])
    for guest in args['guests']:
        for key in ('arrival', 'departure'):
            if guest.get(key):
                guest[key] = timestamp(guest[key])
        if guest.get('arrival') and guest.get('departure') and guest['departure'] < guest['arrival']:
            raise ValueError('Departure precedes arrival')
    for bed in args['beds']:
        integer(bed['capacity'], 1, 20, 'Bed capacity')
        for key in ('shareable', 'accessible', 'private_room', 'quiet'):
            if type(bed[key]) is not bool:
                raise ValueError(f'{key} must be a boolean')
        for key in ('available_from', 'available_until'):
            if bed.get(key):
                bed[key] = date.fromisoformat(bed[key])
        if bed.get('available_from') and bed.get('available_until') and bed['available_until'] < bed['available_from']:
            raise ValueError('Bed availability is reversed')
    return rooming_engine.solve(**args)


def validate_event(data):
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported schema_version')
    if not isinstance(data.get('event_id'), str) or not data['event_id'].strip() or data['event_id'] == 'replace-with-event-id':
        raise ValueError('A stable event_id is required')
    integer(data['revision'], 0, 2**53 - 1, 'revision')
    ZoneInfo(data['timezone'])
    start, end = data.get('starts_on'), data.get('ends_on')
    if bool(start) != bool(end):
        raise ValueError('Provide both event dates or leave both unknown')
    if start and date.fromisoformat(end) < date.fromisoformat(start):
        raise ValueError('Event end precedes start')
    identities(data['guests'])
    for guest in data['guests']:
        if guest['rsvp_status'] not in {'unknown', 'possible', 'confirmed', 'declined'}:
            raise ValueError('Invalid RSVP status')
        if guest['truth_state'] not in {'unknown', 'proposed', 'confirmed'}:
            raise ValueError('Invalid truth state')
        if guest['truth_state'] == 'confirmed' and not guest.get('evidence_ids'):
            raise ValueError('Confirmed guest facts require evidence references')
        for key in ('arrival', 'departure'):
            if guest.get(key):
                timestamp(guest[key])
        if guest.get('arrival') and guest.get('departure') and timestamp(guest['departure']) < timestamp(guest['arrival']):
            raise ValueError('Departure precedes arrival')
    return {'valid': True, 'event_id': data['event_id'], 'revision': data['revision'],
            'limitations': 'Structure only; evidence truth, authority and filesystem privacy are not verified.'}


def run(operation, data):
    if not isinstance(data, dict):
        raise ValueError('Input must be a JSON object')
    if operation == 'validate':
        return validate_event(data)
    if operation == 'audit-records':
        from record_audit import audit_records
        return audit_records(**data)
    if operation == 'archive':
        from archive import archive_event
        return archive_event(**data)
    if operation == 'rooming':
        return rooming(data)
    if operation == 'meals':
        ids = identities(data['guests'])
        for guest in data['guests']:
            required={'id','name','rsvp_status','truth_state','arrival','departure','precision'}
            if not required<=guest.keys():
                raise ValueError('Meal guests require saved id, name, rsvp_status, truth_state, arrival, departure and precision; use null for unknown intervals')
            if guest['rsvp_status'] not in {'unknown','possible','confirmed','declined'} or guest['truth_state'] not in {'unknown','proposed','confirmed'}:
                raise ValueError('Invalid meal guest attendance state')
            if guest['precision'] not in {'unknown','date','part_of_day','exact_time'}:
                raise ValueError('Invalid meal guest time precision')
            for key in ['arrival','departure']:
                if guest[key] is not None: timestamp(guest[key])
            if guest['arrival'] and guest['departure'] and timestamp(guest['departure'])<timestamp(guest['arrival']):
                raise ValueError('Meal guest departure precedes arrival')
        for collection in ('overrides', 'profiles'):
            identities(data[collection], 'guest_id')
        for collection in ('overrides', 'profiles', 'needs', 'requirements'):
            if any(str(row['guest_id']) not in ids for row in data[collection]):
                raise ValueError('Meal record refers to an unknown guest')
        if timestamp(data['meal']['service_end']) <= timestamp(data['meal']['service_start']):
            raise ValueError('Meal interval must be positive')
        return meal_engine.calculate(**data)
    if operation == 'quote':
        return vendor_engine.normalize_quote(data)
    if operation == 'quote-extract':
        return vendor_engine.extract_candidate(data['content'])
    if operation == 'quote-diff':
        before, after = (vendor_engine.normalize_quote(data[key]) for key in ('before', 'after'))
        return {'differences': vendor_engine.semantic_diff(before, after),
                'comparison': vendor_engine.compare([before, after])}
    if operation == 'balance':
        total = vendor_engine.money(data['total'])
        payments = data['payments']
        identities(payments)
        if not data.get('currency') or any(p['currency'] != data['currency'] for p in payments):
            raise ValueError('Payments and total require the same explicit currency')
        paid = sum((vendor_engine.money(p['amount']) for p in payments), Decimal(0))
        return {'currency': data['currency'], 'total': f'{total:.2f}', 'reported_paid': f'{paid:.2f}',
                'balance': f'{max(total-paid, Decimal(0)):.2f}', 'overpayment': f'{max(paid-total, Decimal(0)):.2f}',
                'payment_executed': False}
    if operation == 'research':
        return research.evaluate(data['candidate'], data['constraints'], timestamp(data['now']))
    if operation == 'local-time':
        return {'utc': transport_engine.local_instant(data['value'], data['timezone']).isoformat()}
    if operation == 'audience':
        identities(data['guests'])
        return transport_engine.audience(**data)
    if operation == 'transport':
        vehicle, ride = data['vehicle'], data['ride']
        integer(vehicle['passenger_seats'], 0, 100, 'passenger_seats')
        integer(vehicle['child_seats'], 0, vehicle['passenger_seats'], 'child_seats')
        integer(ride.get('buffer_minutes', 0), 0, 1440, 'buffer_minutes')
        for key in ('driver_authorized', 'accessible'):
            if type(vehicle[key]) is not bool:
                raise ValueError(f'{key} must be a boolean')
        for traveler in data['travelers']:
            if type(traveler.get('pickup_permission')) is not bool:
                raise ValueError('pickup_permission must be a boolean')
        identities(data['travelers'], 'guest_id')
        return transport_engine.plan_ride(**data)
    if operation == 'schedule-check':
        items = data['items']
        identities(items)
        for item in items:
            if timestamp(item['ends_at']) <= timestamp(item['starts_at']):
                raise ValueError('Schedule interval must be positive')
        conflicts = []
        for i, first in enumerate(items):
            for second in items[i+1:]:
                shared = sorted(set(first['guest_ids']) & set(second['guest_ids']))
                if shared and transport_engine.overlaps(first['starts_at'], first['ends_at'], second['starts_at'], second['ends_at']):
                    conflicts.append({'item_ids': [first['id'], second['id']], 'guest_ids': shared})
        return {'conflicts': conflicts, 'valid': not conflicts}
    if operation == 'fingerprint':
        required = {'event_id', 'revision', 'recipients', 'content'}
        if set(data) != required or not isinstance(data['recipients'], list) or not data['recipients']:
            raise ValueError('Fingerprint requires event_id, revision, recipients and content only')
        integer(data['revision'], 0, 2**53 - 1, 'revision')
        if not all(isinstance(x, str) and x.strip() for x in [data['event_id'], data['content'], *data['recipients']]):
            raise ValueError('Fingerprint strings must be nonempty')
        canonical = {**data, 'recipients': sorted(set(data['recipients']))}
        encoded = json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        return {'fingerprint': hashlib.sha256(encoded).hexdigest(), 'authorized': False}
    raise ValueError(f'Unknown operation: {operation}')


OPERATIONS = ('validate', 'audit-records', 'archive', 'rooming', 'meals', 'quote', 'quote-extract', 'quote-diff', 'balance',
              'research', 'local-time', 'audience', 'transport', 'schedule-check', 'fingerprint')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=OPERATIONS)
    parser.add_argument('--input', help='JSON file, otherwise stdin')
    parser.add_argument('--output', help='New output file; never overwrites existing files')
    args = parser.parse_args()
    try:
        raw = Path(args.input).read_text(encoding='utf-8-sig') if args.input else sys.stdin.read()
        if len(raw) > 5_000_000:
            raise ValueError('Input exceeds 5 MB')
        result = run(args.operation, json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON number'))))
        output = json.dumps({'ok': True, 'result': result}, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
        if args.output:
            with open(args.output, 'x', encoding='utf-8') as file:
                file.write(output)
        else:
            print(output, end='')
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError, RecursionError) as exc:
        # Do not echo whole private inputs or filesystem paths into public logs.
        print(json.dumps({'ok': False, 'error': type(exc).__name__, 'message':
              str(exc) if isinstance(exc, ValueError) else 'Check required fields, types, timezone data and file permissions.'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
