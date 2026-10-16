import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import archive


def setup_event(tmp_path):
    event = tmp_path / 'event'
    (event / 'history').mkdir(parents=True)
    (event / 'evidence').mkdir()
    (event / 'empty').mkdir()
    (event / 'event.json').write_text('{"revision": 2}', encoding='utf-8')
    (event / 'history/revision-1.json').write_text('{"revision": 1}', encoding='utf-8')
    (event / 'evidence/receipt.bin').write_bytes(bytes(range(256)))
    sources = tmp_path / 'incoming'
    sources.mkdir()
    (sources / 'reply.txt').write_text('Synthetic guest reply. Confirmed for dinner.', encoding='utf-8')
    return dict(event=event, sources=sources, destination=tmp_path / 'export/event',
                manifest=tmp_path / 'export/manifest.json', restore_to=tmp_path / 'restored')


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_export_restore_exact_bytes_history_evidence_and_unknown_retention(tmp_path):
    args = setup_event(tmp_path)
    before_event, before_sources = snapshot(args['event']), snapshot(args['sources'])
    result = archive.archive_event(**args)
    assert result['verified'] and result['restored_verified']
    assert result['retention_days'] is None
    manifest = json.loads(args['manifest'].read_text())
    expected = {**before_event, **{'sources/' + p: data for p, data in before_sources.items()}}
    assert manifest['files'] == {p: hashlib.sha256(data).hexdigest() for p, data in expected.items()}
    assert manifest['retention_days'] is None
    assert snapshot(args['destination']) == snapshot(args['restore_to']) == expected
    assert (args['restore_to'] / 'empty').is_dir()
    assert snapshot(args['event']) == before_event
    assert snapshot(args['sources']) == before_sources
    assert archive.verify_export(args['destination'], args['manifest'])


def test_cli_uses_explicit_paths_and_retention_without_mutating_inputs(tmp_path):
    args = setup_event(tmp_path)
    cmd = [sys.executable, str(Path(archive.__file__)), '--retention-days', '30']
    for key, value in args.items():
        cmd += ['--' + key.replace('_', '-'), str(value)]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['retention_days'] == 30
    assert json.loads(args['manifest'].read_text())['retention_days'] == 30


def test_optional_sources_and_restore(tmp_path):
    args = setup_event(tmp_path)
    args.pop('sources')
    args.pop('restore_to')
    result = archive.archive_event(**args)
    assert result['verified'] and not result['restored_verified']
    assert snapshot(args['destination']) == snapshot(args['event'])


@pytest.mark.parametrize('change', ['changed', 'missing', 'extra'])
def test_manifest_detects_tampering(tmp_path, change):
    args = setup_event(tmp_path)
    archive.archive_event(**args)
    file = args['destination'] / 'event.json'
    if change == 'changed':
        file.write_text('tampered')
    elif change == 'missing':
        file.unlink()
    else:
        (args['destination'] / 'extra.txt').write_text('unexpected')
    with pytest.raises(ValueError, match='verification failed'):
        archive.verify_export(args['destination'], args['manifest'])


@pytest.mark.parametrize('target', ['destination', 'manifest', 'restore_to'])
def test_existing_targets_fail_before_any_writes(tmp_path, target):
    args = setup_event(tmp_path)
    args[target].parent.mkdir(parents=True, exist_ok=True)
    args[target].write_text('preserve')
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='already exists'):
        archive.archive_event(**args)
    assert snapshot(tmp_path) == before
    for name in ('destination', 'manifest', 'restore_to'):
        if name != target:
            assert not args[name].exists()


@pytest.mark.parametrize('target,base', [('destination', 'event'), ('restore_to', 'sources'),
                                        ('manifest', 'destination'), ('sources', 'event'),
                                        ('restore_to', 'destination')])
def test_overlaps_fail_before_writes(tmp_path, target, base):
    args = setup_event(tmp_path)
    args[target] = args[base] / 'nested'
    with pytest.raises(ValueError, match='Overlapping'):
        archive.archive_event(**args)
    assert not (tmp_path / 'export').exists()


@pytest.mark.parametrize('name', ['.env', '.env.local', 'credentials.json', 'secret.txt',
                                 '.gitconfig', '.git', 'node_modules', 'private.key'])
def test_secrets_and_plumbing_fail_closed_in_selected_tree(tmp_path, name):
    args = setup_event(tmp_path)
    (args['sources'] / name).write_text('synthetic forbidden contents')
    with pytest.raises(ValueError, match='Unsafe'):
        archive.archive_event(**args)
    assert not (tmp_path / 'export').exists()
    assert not args['restore_to'].exists()


def test_traversal_and_source_collision_fail_before_writes(tmp_path):
    args = setup_event(tmp_path)
    args['destination'] = tmp_path / 'unused/../escape'
    with pytest.raises(ValueError, match='traversal'):
        archive.archive_event(**args)
    args['destination'] = tmp_path / 'export/event'
    (args['event'] / 'sources').mkdir()
    with pytest.raises(ValueError, match='conflict'):
        archive.archive_event(**args)
    assert not (tmp_path / 'export').exists()


def test_ordinary_event_configuration_is_preserved(tmp_path):
    args=setup_event(tmp_path)
    (args['event']/'schedule-config.json').write_text('{"timezone":"UTC"}',encoding='utf-8')
    archive.archive_event(**args)
    assert (args['restore_to']/'schedule-config.json').read_text()=='{"timezone":"UTC"}'


def directory_link(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        if os.name != 'nt':
            raise
        # Windows junctions need no symlink privilege and exercise real link refusal.
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True, text=True)
        assert result.returncode == 0, f'{exc}; {result.stderr}'


def test_link_inside_tree_is_refused(tmp_path):
    args = setup_event(tmp_path)
    directory_link(args['event'] / 'linked', args['sources'])
    with pytest.raises(ValueError, match='Symlink'):
        archive.archive_event(**args)
    assert not (tmp_path / 'export').exists()


def test_linked_output_parent_is_refused(tmp_path):
    args = setup_event(tmp_path)
    directory_link(tmp_path / 'alias', args['sources'])
    args['destination'] = tmp_path / 'alias/export'
    with pytest.raises(ValueError, match='Symlink'):
        archive.archive_event(**args)
    assert not (args['sources'] / 'export').exists()


@pytest.mark.parametrize('retention', [-1, True, '30'])
def test_invalid_retention_is_refused(tmp_path, retention):
    args = setup_event(tmp_path)
    with pytest.raises(ValueError, match='Retention'):
        archive.archive_event(**args, retention_days=retention)
    assert not (tmp_path / 'export').exists()


def test_concurrent_change_fails_and_identifies_partial_artifacts(tmp_path, monkeypatch):
    args = setup_event(tmp_path)
    original_copy = archive._copy

    def changing_copy(root, target, inventory):
        original_copy(root, target, inventory)
        if root == args['event']:
            (root / 'event.json').write_text('another host revision')

    monkeypatch.setattr(archive, '_copy', changing_copy)
    with pytest.raises(ValueError, match='unverified partial artifacts.*Original source changed'):
        archive.archive_event(**args)
    assert args['destination'].exists()
    assert not args['manifest'].exists()


def test_midwrite_failure_does_not_claim_verification_or_delete(tmp_path, monkeypatch):
    args = setup_event(tmp_path)
    original_copy = archive._copy

    def failing_copy(root, target, inventory):
        if root == args['sources']:
            raise OSError('synthetic disk failure')
        original_copy(root, target, inventory)

    monkeypatch.setattr(archive, '_copy', failing_copy)
    with pytest.raises(ValueError, match='unverified partial artifacts.*disk failure'):
        archive.archive_event(**args)
    assert (args['destination'] / 'history/revision-1.json').exists()
    assert not args['manifest'].exists()
    assert not args['restore_to'].exists()


def test_manifest_traversal_is_refused(tmp_path):
    args = setup_event(tmp_path)
    archive.archive_event(**args)
    manifest = json.loads(args['manifest'].read_text())
    manifest['files']['../outside.txt'] = '0' * 64
    with pytest.raises(ValueError, match='Unsafe'):
        archive.verify_export(args['destination'], manifest)
