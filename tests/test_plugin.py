from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
import eventer
import install
import package
import validate

ROOT = Path(__file__).resolve().parents[1]


def example(operation):
    return json.loads((ROOT / 'examples/inputs' / (operation + '.json')).read_text())


@pytest.mark.parametrize('operation', eventer.OPERATIONS)
def test_every_documented_helper_accepts_its_working_example(operation):
    assert eventer.run(operation, example(operation)) is not None


def test_event_evidence_and_identity_validation():
    data = example('validate')
    data['guests'] = [{'id': 'g1', 'rsvp_status': 'confirmed', 'truth_state': 'confirmed', 'evidence_ids': []}]
    with pytest.raises(ValueError, match='evidence'):
        eventer.run('validate', data)
    data['guests'][0]['evidence_ids'] = ['e1']
    assert eventer.run('validate', data)['valid']
    data['guests'] *= 2
    with pytest.raises(ValueError, match='Duplicate|duplicate'):
        eventer.run('validate', data)


def test_fingerprint_changes_with_action_and_does_not_authorize():
    data = example('fingerprint')
    first = eventer.run('fingerprint', data)
    assert first['authorized'] is False
    for field, value in [('event_id', 'other'), ('revision', 2), ('recipients', ['other@example.test']), ('content', 'Changed')]:
        assert eventer.run('fingerprint', {**data, field: value})['fingerprint'] != first['fingerprint']


def test_payment_identity_and_currency_are_not_silently_merged():
    data = example('balance')
    assert eventer.run('balance', data)['balance'] == '111.70'
    data['payments'] *= 2
    with pytest.raises(ValueError, match='duplicate'):
        eventer.run('balance', data)
    data = example('balance'); data['payments'][0]['currency'] = 'EUR'
    with pytest.raises(ValueError, match='currency'):
        eventer.run('balance', data)


@pytest.mark.parametrize('field,value', [('passenger_seats', -1), ('passenger_seats', True), ('driver_authorized', 'false'), ('child_seats', 99)])
def test_transport_invalid_types_cannot_supply_permission(field, value):
    data = example('transport'); data['vehicle'][field] = value
    with pytest.raises(ValueError):
        eventer.run('transport', data)


def test_cli_errors_and_never_overwrites_output(tmp_path):
    command = [sys.executable, '-B', str(ROOT / 'skills/eventer/scripts/eventer.py'), 'balance']
    invalid = subprocess.run(command, input='{}', text=True, capture_output=True)
    assert invalid.returncode == 2 and json.loads(invalid.stderr)['ok'] is False
    output = tmp_path / 'output.json'; output.write_text('preserve')
    second = subprocess.run(command + ['--output', str(output)], input=json.dumps(example('balance')), text=True, capture_output=True)
    assert second.returncode == 2 and output.read_text() == 'preserve'


def test_portable_install_preview_update_remove_preserve_unrelated(tmp_path):
    destination = tmp_path / 'skills'
    assert not install.install(destination)['applied'] and not destination.exists()
    install.install(destination, apply=True)
    unrelated = destination / 'other-skill'; unrelated.mkdir(); (unrelated / 'SKILL.md').write_text('unrelated')
    install.install(destination, apply=True)
    assert (destination / 'eventer/scripts/engines/rooming_engine.py').exists()
    install.install(destination, apply=True, uninstall=True)
    assert (unrelated / 'SKILL.md').read_text() == 'unrelated'
    assert not (destination / 'eventer').exists()


def test_install_refuses_changed_or_unowned_files(tmp_path):
    install.install(tmp_path, apply=True)
    skill = tmp_path / 'eventer/SKILL.md'; skill.write_text('local customization')
    with pytest.raises(ValueError, match='Locally modified'):
        install.install(tmp_path, apply=True)
    with pytest.raises(ValueError, match='Locally modified'):
        install.install(tmp_path, apply=True, uninstall=True)
    assert skill.read_text() == 'local customization'


def test_install_refuses_path_traversal_and_existing_unowned_skill(tmp_path):
    with pytest.raises(ValueError):
        install.safe_path(tmp_path, '../outside')
    folder = tmp_path / 'eventer'; folder.mkdir(); (folder / 'mine.md').write_text('preserve')
    with pytest.raises(ValueError, match='Unowned'):
        install.install(tmp_path, apply=True)


def test_installed_helpers_work_without_source_checkout(tmp_path):
    install.install(tmp_path, apply=True)
    command = [sys.executable, '-B', str(tmp_path / 'eventer/scripts/eventer.py'), 'quote-diff']
    result = subprocess.run(command, input=json.dumps(example('quote-diff')), cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert 'total' in {d['field'] for d in json.loads(result.stdout)['result']['differences']}


def test_package_is_reproducible_and_excludes_generated_private_directories():
    first, digest = package.build()
    _, again = package.build()
    assert digest == again
    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        assert 'eventer/skills/eventer/SKILL.md' in names
        assert not any('/.git/' in p or '/.eval-runs/' in p or '__pycache__' in p for p in names)


def test_public_package_validation():
    assert validate.validate() == []
