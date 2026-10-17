"""Build a reproducible public ZIP using an explicit allowlist, plus SHA-256."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = {'plugin.json', '.codex-plugin', '.claude-plugin', '.agents', 'skills', 'evals', 'tests', 'assets',
           'docs', 'examples', 'scripts', '.github', 'README.md', 'LICENSE', 'CONTRIBUTING.md',
           'SECURITY.md', 'PRIVACY.md', 'CHANGELOG.md', 'AGENTS.md', 'requirements.txt', 'requirements-dev.txt', 'pyproject.toml', '.gitignore', '.gitattributes'}


def build(root=ROOT):
    version = json.loads((root / 'plugin.json').read_text())['version']
    output = root / 'dist' / f'eventer-{version}.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*'), key=lambda p: p.relative_to(root).as_posix()):
            relative = path.relative_to(root)
            if not path.is_file() or relative.parts[0] not in INCLUDE or any(p in {'__pycache__', '.pytest_cache'} for p in relative.parts):
                continue
            if path.suffix == '.pyc' or path.is_symlink():
                continue
            info = zipfile.ZipInfo('eventer/' + relative.as_posix(), (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    (output.parent / 'SHA256SUMS').write_text(f'{checksum}  {output.name}\n', encoding='utf-8')
    return output, checksum


if __name__ == '__main__':
    print(json.dumps(dict(zip(('archive', 'sha256'), map(str, build()))), indent=2))
