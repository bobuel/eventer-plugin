"""Portable local event export; no providers, overwrite, deletion, or secret guarantee.

Only explicitly selected trees are read. Run with one host/writer at a time.
On failure, any created paths are partial artifacts, never verified archives.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys


BLOCKED = {
    '.git', '.svn', '.hg', '.aws', '.ssh', '.codex', '.agents', '.claude',
    '.tools', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
    '.config', '.npmrc', '.netrc', '.pypirc', '.gitconfig',
    'credentials', 'secrets',
    'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'pyproject.toml',
    'dockerfile', 'docker-compose.yml', 'wrangler.toml', 'wrangler.jsonc',
}
LIMITATION = ('Filename checks cannot guarantee secret-free contents. The host must '
              'review selected event and source contents before export or sharing.')


def _safe_name(name):
    lower = name.casefold()
    if (name in {'', '.', '..'} or any(c in name for c in '\\:/*?"<>|')
            or name.endswith((' ', '.')) or any(ord(c) < 32 for c in name)
            or lower in BLOCKED or lower.startswith('.env')
            or re.search(r'(^|[._-])(secret|secrets|credential|credentials|token|tokens)([._-]|$)', lower)
            or lower in {'id_rsa', 'id_ed25519', 'id_ecdsa'}
            or Path(lower).suffix in {'.pem', '.key', '.p12', '.pfx'}
            or re.match(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', lower)):
        raise ValueError(f'Unsafe, secret, configuration, or plumbing path: {name}')


def _no_links(path):
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise ValueError(f'Symlink or junction refused: {item}')


def _path(value):
    path = Path(value).expanduser()
    if '..' in path.parts:
        raise ValueError(f'Path traversal refused: {value}')
    path = Path(os.path.abspath(path))
    _no_links(path)
    _safe_name(path.name)
    return path


def _relative(value):
    if not isinstance(value, str):
        raise ValueError('Manifest paths must be strings')
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or str(path) != value:
        raise ValueError(f'Invalid relative path: {value}')
    for name in path.parts:
        _safe_name(name)
    return path


def _hash(path):
    _no_links(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f'Only regular files can be archived: {path}')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory(root):
    _no_links(root)
    if not root.is_dir():
        raise ValueError(f'Selected root must be a directory: {root}')
    files, directories, names = {}, [], set()
    # os.walk never follows links; reject links explicitly, including empty ones.
    for current, children, entries in os.walk(root, followlinks=False, onerror=lambda exc: (_ for _ in ()).throw(exc)):
        for name in sorted(children + entries):
            _safe_name(name)
            path = Path(current) / name
            _no_links(path)
            relative = path.relative_to(root).as_posix()
            if relative.casefold() in names:
                raise ValueError(f'Nonportable case-colliding path: {relative}')
            names.add(relative.casefold())
            mode = path.stat().st_mode
            if stat.S_ISDIR(mode):
                directories.append(relative)
            elif stat.S_ISREG(mode):
                files[relative] = _hash(path)
            else:
                raise ValueError(f'Unsupported file type: {path}')
    return {'files': dict(sorted(files.items())), 'directories': sorted(directories)}


def verify_export(root, manifest):
    """Recheck a saved manifest against the complete tree, including extra files."""
    root = _path(root)
    if not isinstance(manifest, dict):
        manifest_path = _path(manifest)
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('format_version') != 1 or not isinstance(manifest.get('files'), dict):
        raise ValueError('Unsupported or invalid archive manifest')
    directories = manifest.get('directories')
    if (not isinstance(directories, list) or not all(isinstance(p, str) for p in directories)
            or len(set(directories)) != len(directories)):
        raise ValueError('Invalid manifest directories')
    for relative, digest in manifest['files'].items():
        _relative(relative)
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid SHA-256 digest')
    for relative in directories:
        _relative(relative)
    actual = _inventory(root)
    if actual != {'files': manifest['files'], 'directories': sorted(directories)}:
        raise ValueError(f'Archive verification failed (missing, extra, or changed bytes): {root}')
    return True


def _copy(root, target, inventory):
    _no_links(target)
    target.mkdir(parents=True, exist_ok=False)
    for relative in sorted(inventory['directories'], key=lambda p: (len(PurePosixPath(p).parts), p)):
        destination = target / relative
        _no_links(destination)
        destination.mkdir(exist_ok=False)
    for relative, expected in inventory['files'].items():
        source, destination = root / relative, target / relative
        _no_links(source)
        _no_links(destination)
        if _hash(source) != expected:
            raise ValueError(f'Source changed before copy: {source}')
        with source.open('rb') as src, destination.open('xb') as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b''):
                dst.write(chunk)


def archive_event(*, event, destination, manifest, sources=None, restore_to=None, retention_days=None):
    if retention_days is not None and (type(retention_days) is not int or retention_days < 0):
        raise ValueError('Retention days must be a nonnegative integer or unknown (null)')
    event, destination, manifest = map(_path, (event, destination, manifest))
    sources = _path(sources) if sources is not None else None
    restore_to = _path(restore_to) if restore_to is not None else None
    roots = [event, destination, manifest] + [p for p in (sources, restore_to) if p is not None]
    for index, first in enumerate(roots):
        for second in roots[index + 1:]:
            if first == second or first in second.parents or second in first.parents:
                raise ValueError(f'Overlapping paths refused: {first} and {second}')
    targets = [destination, manifest] + ([restore_to] if restore_to is not None else [])
    for target in targets:
        if target.exists():
            raise ValueError(f'Target already exists; no overwrite: {target}')
        for parent in target.parents:
            if parent.exists() and not parent.is_dir():
                raise ValueError(f'Target parent is not a directory: {parent}')
    event_inventory = _inventory(event)
    source_inventory = _inventory(sources) if sources is not None else None
    if sources is not None and any(p.split('/')[0].casefold() == 'sources' for p in [*event_inventory['files'], *event_inventory['directories']]):
        raise ValueError('External sources conflict with existing event/sources')
    combined = {'files': dict(event_inventory['files']), 'directories': list(event_inventory['directories'])}
    if source_inventory is not None:
        combined['files'].update({'sources/' + p: h for p, h in source_inventory['files'].items()})
        combined['directories'] += ['sources'] + ['sources/' + p for p in source_inventory['directories']]
    combined = {'files': dict(sorted(combined['files'].items())), 'directories': sorted(combined['directories'])}
    record = {'format_version': 1, **combined, 'retention_days': retention_days,
              'exported_at': datetime.now(timezone.utc).isoformat(), 'hash_algorithm': 'sha256',
              'content_review_limitation': LIMITATION}
    # No filesystem mutations occur before the entire selected plan passes above.
    try:
        _copy(event, destination, event_inventory)
        if sources is not None:
            _copy(sources, destination / 'sources', source_inventory)
        verify_export(destination, record)
        if restore_to is not None:
            _copy(destination, restore_to, combined)
            verify_export(restore_to, record)
        if _inventory(event) != event_inventory or (sources is not None and _inventory(sources) != source_inventory):
            raise ValueError('Original source changed during export; archive is not verified')
        verify_export(destination, record)
        if restore_to is not None:
            verify_export(restore_to, record)
        _no_links(manifest)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
            stream.write('\n')
        saved = json.loads(manifest.read_text(encoding='utf-8'))
        if saved != record:
            raise ValueError('Manifest readback mismatch')
        verify_export(destination, saved)
        if restore_to is not None:
            verify_export(restore_to, saved)
    except (OSError, ValueError) as exc:
        partial = [str(p) for p in targets if p.exists()]
        raise ValueError(f'Export failed; outputs are unverified partial artifacts: {partial}. {exc}') from exc
    return {'ok': True, 'verified': True, 'destination': str(destination), 'manifest': str(manifest),
            'restore_to': str(restore_to) if restore_to else None, 'restored_verified': restore_to is not None,
            'file_count': len(combined['files']), 'retention_days': retention_days,
            'content_review_limitation': LIMITATION}


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=LIMITATION)
    parser.add_argument('--event', required=True)
    parser.add_argument('--sources')
    parser.add_argument('--destination', required=True, help='New exported event directory')
    parser.add_argument('--manifest', required=True, help='New manifest outside all selected trees')
    parser.add_argument('--restore-to', help='Optional new directory for verified restore rehearsal')
    parser.add_argument('--retention-days', type=int, help='Omit when the host has not decided; never deletes records')
    try:
        result = archive_event(**vars(parser.parse_args()))
    except (OSError, ValueError) as exc:
        print(json.dumps({'ok': False, 'verified': False, 'error': str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
