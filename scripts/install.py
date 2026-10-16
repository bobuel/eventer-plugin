"""Preview or install the complete portable skill collection. No global config edits."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
MARKER = '.eventer-install.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files():
    return {str(p.relative_to(ROOT / 'skills')).replace('\\', '/'): p
            for p in (ROOT / 'skills').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def safe_path(root, relative):
    path = root / relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Unsafe installed path')
    for part in [path, *path.parents]:
        if part == root.parent:
            break
        if part.is_symlink():
            raise ValueError('Installation refuses symlinks')
    return path


def install(destination, apply=False, uninstall=False):
    destination = Path(destination).absolute()
    if destination.is_symlink():
        raise ValueError('Destination must not be a symlink')
    marker = safe_path(destination, MARKER)
    old = json.loads(marker.read_text()) if marker.exists() else {'files': {}}
    sources = {} if uninstall else source_files()
    if uninstall and not marker.exists():
        raise ValueError('No Eventer installation record; refusing removal')
    for relative, expected in old['files'].items():
        target = safe_path(destination, relative)
        if target.exists() and (not target.is_file() or digest(target) != expected):
            raise ValueError(f'Locally modified installed file; preserve or resolve first: {relative}')
    # Never merge with an unowned same-name skill, including unexpected extra files.
    owned_names = {Path(name).parts[0] for name in old['files']}
    new_names = {Path(name).parts[0] for name in sources}
    for name in new_names | owned_names:
        directory = safe_path(destination, name)
        if directory.exists():
            for target in directory.rglob('*'):
                relative = target.relative_to(destination).as_posix()
                if target.is_symlink():
                    raise ValueError('Installation refuses symlinks')
                if target.is_file() and relative not in old['files']:
                    # Python caches are user-generated and must not be removed automatically.
                    raise ValueError(f'Unowned file in skill destination: {relative}')
    planned = {'operation': 'uninstall' if uninstall else 'install-or-update',
               'destination': str(destination), 'write': sorted(sources),
               'remove': sorted(set(old['files']) - set(sources)), 'applied': apply}
    if not apply:
        return planned
    destination.mkdir(parents=True, exist_ok=True)
    for relative, source in sources.items():
        target = safe_path(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for relative in planned['remove']:
        target = safe_path(destination, relative)
        if target.exists():
            target.unlink()
    for name in new_names | owned_names:
        directory = safe_path(destination, name)
        if directory.exists():
            for folder in sorted((p for p in directory.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                if not any(folder.iterdir()):
                    folder.rmdir()
            if not any(directory.iterdir()):
                directory.rmdir()
    if uninstall:
        marker.unlink()
    else:
        marker.write_text(json.dumps({'version': json.loads((ROOT / 'plugin.json').read_text())['version'],
                                     'files': {name: digest(path) for name, path in sources.items()}}, indent=2) + '\n')
    return planned


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, help='Harness skills directory')
    parser.add_argument('--apply', action='store_true', help='Default is preview only')
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.destination, args.apply, args.uninstall), indent=2))
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
