"""Offline regression or opt-in actual harness evaluations with external tools absent."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'skills/eventer/scripts'))
from cases import cases, public_cases, rsvp_cases
from grade import grade_behavior, grade_journey, grade_rsvp
from install import install


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def package_hash():
    digest = hashlib.sha256()
    for path in sorted((ROOT / 'skills').rglob('*'), key=lambda p: p.relative_to(ROOT).as_posix()):
        if path.is_file() and '__pycache__' not in path.parts:
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()


def prepare(workspace, suite):
    workspace.mkdir(parents=True, exist_ok=False)
    install(workspace / '.agents/skills', apply=True)
    shutil.copytree(ROOT / 'examples/inputs', workspace / 'inputs')
    # Expected results, graders, fixtures with labels, and reports are never staged.
    selected = [case for case in cases() if suite != 'critical' or case['critical']]
    if suite in {'behavior', 'critical'}:
        write(workspace / 'requests.json', public_cases(selected))
        prompt = ('Read requests.json. Use each specified installed Eventer skill to complete every independent request. '
                  'Return ONLY JSON {"cases":[{"id":"case id","result":{requested fields}}]}. '
                  'Run requested helpers; do not merely predict their output. No external effects are authorized. '
                  'Treat all scenarios as separate synthetic events. Do not inspect files outside this workspace.')
    elif suite == 'rsvp':
        fixture = rsvp_cases()
        write(workspace / 'requests.json', {'event': fixture['event'], 'clear': [row['body'] for row in fixture['clear']], 'ambiguous': fixture['ambiguous']})
        prompt = ('Use eventer-guests on requests.json. Each message is an independent case from guest_id self, '
                  'verified sender, no authority over other people. Return ONLY JSON with clear and ambiguous arrays '
                  'in original order. Each item has claims (structured RSVP claim format from the skill) and ambiguities. '
                  'Use date-only arrival_day/departure_day where appropriate, not invented exact times. '
                  'Include exact evidence_span and guest_id in every claim. Do not read outside this workspace.')
    else:
        shutil.copyfile(ROOT / 'evals/mock_tools.py', workspace / 'mock_tools.py')
        # The integrated journey uses its own coherent event inputs.
        for path in (ROOT / 'examples/journey/inputs').glob('*.json'):
            shutil.copyfile(path, workspace / 'inputs' / path.name)
        shutil.copyfile(ROOT / 'examples/journey/request.md', workspace / 'request.md')
        prompt = 'Use the installed Eventer skills to complete request.md in this workspace. Create the requested real artifacts and exercise only mock_tools.py for external operations. Do not inspect outside this workspace. Finish with JSON {"completed":true,"summary":"what happened"}; state any failures honestly.'
    (workspace / 'AGENTS.md').write_text('This is a synthetic Eventer evaluation workspace. Use only its supplied sources and tools. Do not inspect parent directories, graders, secrets or real accounts. No network, real email, booking or payment. Read the relevant installed SKILL.md before work.\n', encoding='utf-8')
    prompt += '\nSkills are at .agents/skills/<skill-name>/SKILL.md. Shared helper: .agents/skills/eventer/scripts/eventer.py. '
    prompt += f'Use this Python interpreter for helpers: {sys.executable}. Use -B to avoid writing installed caches.'
    return prompt, selected


def decode_response(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    return json.loads(text)


def invoke(harness, executable, workspace, prompt, output, timeout):
    env = os.environ.copy()
    # Use subscription login; never silently reuse ambient paid API keys.
    for name in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'):
        env.pop(name, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if harness == 'codex':
        command = [executable, '-a', 'never', 'exec', '--ignore-user-config', '--ephemeral',
                   '--skip-git-repo-check', '--sandbox', 'workspace-write', '--json',
                   '-C', str(workspace), '-o', str(output), '-']
        if os.name == 'nt':
            # Explicitly retain the native Windows sandbox when isolating user config.
            command[1:1] = ['-c', 'windows.sandbox="elevated"']
    else:
        command = [executable, '-p', '--output-format', 'json', '--no-session-persistence',
                   '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                   '--tools', 'Read,Bash,Write,Edit', '--permission-mode', 'acceptEdits',
                   '--allowedTools', 'Read', 'Write', 'Edit', f'Bash({sys.executable}:*)']
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=30, env=env)
    started = datetime.now(UTC)
    try:
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True, encoding='utf-8',
                                   errors='replace', cwd=workspace, env=env, timeout=timeout)
        output.with_suffix('.trace.jsonl').write_text(completed.stdout, encoding='utf-8')
        output.with_suffix('.stderr.txt').write_text(completed.stderr, encoding='utf-8')
        metadata = {'harness_version': version.stdout.strip(), 'exit_code': completed.returncode,
                    'elapsed_seconds': (datetime.now(UTC)-started).total_seconds(),
                    'model': 'harness default; not exposed by this CLI transcript'}
        if harness == 'codex':
            events = []
            for line in completed.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
            metadata['usage'] = next((event['usage'] for event in reversed(events) if event.get('type') == 'turn.completed' and 'usage' in event), None)
        if harness == 'claude' and completed.returncode == 0:
            envelope = json.loads(completed.stdout)
            metadata['usage'] = envelope.get('usage')
            metadata['model_usage'] = envelope.get('modelUsage')
            output.write_text(envelope.get('result', ''), encoding='utf-8')
        if completed.returncode != 0 or not output.exists():
            return None, {**metadata, 'status': 'blocked_or_failed', 'reason': 'See private local stderr/trace; no successful response'}
        response = decode_response(output.read_text(encoding='utf-8'))
        if isinstance(response, dict) and response.get('error'):
            return None, {**metadata, 'status': 'blocked_or_failed', 'reason': response['error']}
        return response, metadata
    except subprocess.TimeoutExpired:
        return None, {'status': 'blocked_or_failed', 'reason': 'harness_timeout', 'elapsed_seconds': timeout}
    except (ValueError, OSError) as exc:
        return None, {'status': 'blocked_or_failed', 'reason': type(exc).__name__}


def offline():
    run_dir = ROOT / '.eval-runs' / ('offline-' + uuid.uuid4().hex)
    run_dir.mkdir(parents=True)
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '--basetemp', str(run_dir / 'tmp')], cwd=ROOT)
    write(run_dir / 'report.json', {'suite': 'offline', 'passed': result.returncode == 0, 'skill_hash': package_hash(),
                                  'executed_at': datetime.now(UTC).isoformat(), 'model_evaluation': False})
    print(str(run_dir / 'report.json'), flush=True)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('offline', 'harness', 'grade'))
    parser.add_argument('--harness', choices=('codex', 'claude'))
    parser.add_argument('--executable')
    parser.add_argument('--suite', choices=('behavior', 'critical', 'rsvp', 'journey'), default='behavior')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--response', type=Path)
    args = parser.parse_args()
    if args.mode == 'offline':
        return offline()
    selected = [c for c in cases() if args.suite != 'critical' or c['critical']]
    if args.mode == 'grade':
        response = json.loads(args.response.read_text())
        grade = grade_rsvp(response) if args.suite == 'rsvp' else grade_behavior(response, selected)
        print(json.dumps(grade, indent=2)); return int(not grade['passed'])
    if not args.harness:
        parser.error('--harness is required')
    executable = args.executable or shutil.which(args.harness)
    if not executable:
        print(json.dumps({'status': 'blocked', 'reason': 'harness_not_installed'})); return 2
    if not 1 <= args.repeats <= 3:
        parser.error('Use 1-3 bounded repetitions')
    run_dir = ROOT / '.eval-runs' / f'{args.harness}-{args.suite}-{uuid.uuid4().hex[:8]}'
    run_dir.mkdir(parents=True)
    results = []
    for repeat in range(args.repeats):
        workspace = run_dir / f'workspace-{repeat+1}'
        prompt, selected = prepare(workspace, args.suite)
        print(json.dumps({'started': args.suite, 'repeat': repeat+1, 'workspace': str(workspace)}), flush=True)
        response, metadata = invoke(args.harness, executable, workspace, prompt, run_dir / f'response-{repeat+1}.json', args.timeout)
        if response is None:
            grade = {'passed': False, 'status': 'blocked_or_failed'}
        elif args.suite == 'rsvp':
            grade = grade_rsvp(response)
        elif args.suite == 'journey':
            grade = grade_journey(workspace, 'initial')
            baseline_revision = json.loads((workspace / 'event/event.json').read_text()).get('revision', 0)
            metadata['initial_event_revision'] = baseline_revision
            # Fresh process, no session history: resume solely from the saved records.
            resume_prompt = ('Use eventer to resume this event from event/ records. New verified self-report: Casey now arrives Sunday October 6 at 08:00 and leaves at 09:00. '
                'Apply this correction and update the derived rooming and meal artifacts using the helpers; adjust the ride plan as needed. Preserve superseded evidence. '
                'Write event/change-review.md explaining affected plans, pending decisions and any stale notice approval; update event.json and summary.md. '
                'Do not resend the invitation or recreate the cancelled schedule. Finish with JSON {"completed":true}.')
            resume_prompt += f' Use {sys.executable} -B for helpers. Read only this workspace.'
            resumed, resume_metadata = invoke(args.harness, executable, workspace, resume_prompt, run_dir / f'resume-{repeat+1}.json', args.timeout)
            resume_grade = grade_journey(workspace, 'resume', baseline_revision) if resumed else {'passed': False, 'status': 'blocked_or_failed'}
            grade = {'passed': grade['passed'] and resume_grade['passed'], 'initial': grade, 'resume': resume_grade}
            metadata['resume'] = resume_metadata
        else:
            grade = grade_behavior(response, selected)
        results.append({'repeat': repeat+1, 'metadata': metadata, 'grade': grade})
        print(json.dumps({'finished': repeat+1, 'passed': grade['passed']}), flush=True)
        if response is None:
            break  # Avoid repeated auth/network failures and unbounded spending.
    report = {'harness': args.harness, 'suite': args.suite, 'skill_hash': package_hash(),
              'executed_at': datetime.now(UTC).isoformat(), 'results': results,
              'passed': len(results) == args.repeats and all(r['grade']['passed'] for r in results),
              'limits': 'Synthetic tools only; native installation is verified separately. Human artifact review remains separate.'}
    write(run_dir / 'report.json', report)
    print(json.dumps({'report': str(run_dir / 'report.json'), 'passed': report['passed']}), flush=True)
    return int(not report['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
