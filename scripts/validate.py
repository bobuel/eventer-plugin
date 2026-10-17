"""Validate public package metadata, resource resolution and accidental sensitive content."""
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate_listing(root, portable, codex):
    """Local checks of our skills-only listing; not OpenAI portal acceptance."""
    failures=[]
    if portable.get('extensions',{}).get('com.openai',{}).get('requires_local_executor') is not True or codex.get('requires_local_executor') is not True:
        failures.append('Eventer local helpers require the desktop execution declaration')
    interface=portable.get('extensions',{}).get('com.openai',{}).get('interface',{})
    if interface!=codex.get('interface'):
        failures.append('Portable and Codex listing metadata diverge')
    for field,limit in [('displayName',30),('shortDescription',30),('longDescription',4000),
                        ('developerName',80),('category',120)]:
        value=interface.get(field)
        if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 for c in value):
            failures.append('Invalid listing field: '+field)
    for manifest in [portable,codex]:
        if not manifest.get('author',{}).get('name'):
            failures.append('Publisher author.name is required')
    capabilities=interface.get('capabilities')
    if not isinstance(capabilities,list) or len(capabilities)>20 or any(not isinstance(c,str) or not c.strip() or len(c)>120 for c in capabilities):
        failures.append('Invalid listing capabilities')
    prompts=interface.get('defaultPrompt',[])
    if not isinstance(prompts,list) or len(prompts)>3 or len(set(prompts))!=len(prompts) or any(not isinstance(p,str) or not p.strip() or len(p)>128 for p in prompts):
        failures.append('Invalid starter prompts')
    for field in ['websiteURL','supportURL','privacyPolicyURL']:
        value=interface.get(field,'')
        try:
            url=urlsplit(value)
            if url.scheme!='https' or not url.hostname or url.username or url.password or len(value)>1024: raise ValueError()
        except (TypeError,ValueError): failures.append('Invalid listing URL: '+field)
    if not (root/'PRIVACY.md').is_file(): failures.append('Published privacy policy source is missing')
    for field in ['logo','composerIcon']:
        value=interface.get(field,'')
        if not isinstance(value,str) or not value.startswith('./'):
            failures.append('Invalid asset path: '+field); continue
        path=(root/value).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.is_symlink():
            failures.append('Missing or escaping listing asset: '+field); continue
        if path.stat().st_size>5*1024*1024:
            failures.append('Oversized listing asset: '+field); continue
        # Eventer deliberately ships one self-contained SVG; reject active or
        # remotely loaded content and verify the official square size boundary.
        try:
            raw=path.read_text(encoding='utf-8')
            if path.suffix!='.svg' or '<!DOCTYPE' in raw or '<!ENTITY' in raw: raise ValueError()
            svg=ET.fromstring(raw)
            width,height=float(svg.get('width','0')),float(svg.get('height','0'))
            if width<48 or width!=height: raise ValueError()
            for element in svg.iter():
                if element.tag.split('}')[-1] in {'script','foreignObject','image','use','style'}: raise ValueError()
                if any(k.split('}')[-1].startswith('on') or k.split('}')[-1] in {'href','style'} for k in element.attrib): raise ValueError()
                for value in element.attrib.values():
                    if re.search(r'url\s*\(',value,re.IGNORECASE) and not re.fullmatch(r'''url\s*\(\s*(['"]?)\#[A-Za-z_][\w:.-]*\1\s*\)''',value,re.IGNORECASE):
                        raise ValueError()
        except (ValueError,ET.ParseError,UnicodeError): failures.append('Invalid self-contained SVG icon: '+field)
    return failures


def validate(root=ROOT):
    failures = []
    manifests = [root / p for p in ('plugin.json', '.codex-plugin/plugin.json', '.claude-plugin/plugin.json')]
    data = [json.loads(p.read_text(encoding='utf-8')) for p in manifests]
    if len({(d['name'], d['version']) for d in data}) != 1:
        failures.append('Plugin identities or versions diverge')
    failures.extend(validate_listing(root,data[0],data[1]))
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
