"""Synthetic-only mail and scheduler simulator. Never contacts a provider."""
import argparse
import json
from pathlib import Path


def action(state, operation, payload):
    if operation == 'mail.send':
        state['send_attempts'] = state.get('send_attempts', 0) + 1
        # The first accepted submission deliberately appears to time out.
        state.setdefault('messages', []).append({'id': 'msg-1', **payload, 'state': 'accepted'})
        return {'state': 'uncertain', 'request_id': 'request-1', 'error': 'timeout_after_submission'}
    if operation == 'mail.lookup':
        state['lookups'] = state.get('lookups', 0) + 1
        return {'messages': state.get('messages', [])}
    if operation == 'scheduler.create':
        task = {'id': 'task-1', **payload, 'state': 'active'}
        state.setdefault('tasks', []).append(task)
        return {'id': task['id'], 'saved': True}
    if operation == 'scheduler.read':
        state['task_readbacks'] = state.get('task_readbacks', 0) + 1
        return {'tasks': state.get('tasks', [])}
    if operation == 'scheduler.cancel':
        for task in state.get('tasks', []):
            if task['id'] == payload['id']:
                task['state'] = 'cancelled'
        return {'saved': True}
    raise ValueError('Unsupported mock operation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation')
    parser.add_argument('--input', help='JSON payload file')
    args = parser.parse_args()
    path = Path('mock-state.json')
    state = json.loads(path.read_text()) if path.exists() else {}
    payload = json.loads(Path(args.input).read_text()) if args.input else {}
    result = action(state, args.operation, payload)
    path.write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps(result))
