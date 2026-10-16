"""Validate public package metadata, resource resolution and accidental sensitive content."""
import json
from pathlib import Path
import re
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT):
    failures = []
    manifests = [root / p for p in ('plugin.json', '.codex-plugin/plugin.json', '.claude-plugin/plugin.json')]
    data = [json.loads(p.read_text(encoding='utf-8')) for p in manifests]
    if len({(d['name'], d['version']) for d in data}) != 1:
        failures.append('Plugin identities or versions diverge')
    skills = list((root / 'skills').glob('*/SKILL.md'))
    if len(skills) != 12:
        failures.append('Expected all twelve skills')
    for skill in skills:
        text = skill.read_text(encoding='utf-8')
        try:
            metadata = yaml.safe_load(text.split('---', 2)[1])
            if metadata['name'] != skill.parent.name or not re.fullmatch('[a-z0-9-]{1,64}', metadata['name']):
                failures.append(f'Invalid skill identity: {skill.parent.name}')
            if not 20 <= len(metadata['description']) <= 1024:
                failures.append(f'Invalid description: {skill.parent.name}')
            ui = yaml.safe_load((skill.parent / 'agents/openai.yaml').read_text())['interface']
            if not 25 <= len(ui['short_description']) <= 64:
                failures.append(f'Invalid UI description: {skill.parent.name}')
        except (KeyError, IndexError, yaml.YAMLError) as exc:
            failures.append(f'Invalid metadata: {skill.parent.name}: {type(exc).__name__}')
    for file in (root / 'skills').rglob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)', file.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):
                continue
            path = (file.parent / target.split('#')[0]).resolve()
            if not path.is_relative_to((root / 'skills').resolve()) or not path.exists():
                failures.append(f'Missing or escaping skill resource: {file.relative_to(root)} -> {target}')
    forbidden = [r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}', r'gh[pousr]_[A-Za-z0-9]{20,}', r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
    for file in root.rglob('*'):
        if any(part in {'.git', '.eval-runs', '.pytest_cache', '__pycache__', 'dist', '.venv'} for part in file.relative_to(root).parts) or not file.is_file():
            continue
        if file.name.startswith('.env'):
            failures.append(f'Environment file in package: {file.relative_to(root)}')
        if file.suffix in {'.md', '.py', '.json', '.yaml', '.yml', '.txt'}:
            text = file.read_text(encoding='utf-8')
            if any(re.search(pattern, text) for pattern in forbidden):
                failures.append(f'Potential secret in {file.relative_to(root)}')
    return failures


if __name__ == '__main__':
    failures = validate()
    print(json.dumps({'passed': not failures, 'skills': 12, 'failures': failures}, indent=2))
    sys.exit(bool(failures))
