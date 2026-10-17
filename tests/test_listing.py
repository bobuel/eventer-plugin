"""Local directory-package checks, not a substitute for portal review."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import zipfile

import pytest
import validate
import package

ROOT=Path(__file__).resolve().parents[1]


def candidate(tmp_path):
    shutil.copytree(ROOT/'assets',tmp_path/'assets')
    shutil.copyfile(ROOT/'PRIVACY.md',tmp_path/'PRIVACY.md')
    return [json.loads((ROOT/p).read_text()) for p in ['plugin.json','.codex-plugin/plugin.json']]


@pytest.mark.parametrize('field',['displayName','shortDescription','longDescription','developerName','category','logo','composerIcon','privacyPolicyURL'])
def test_missing_required_listing_value_is_rejected(tmp_path,field):
    portable,codex=candidate(tmp_path)
    portable['extensions']['com.openai']['interface'].pop(field)
    codex['interface']=deepcopy(portable['extensions']['com.openai']['interface'])
    assert validate.validate_listing(tmp_path,portable,codex)


def test_inline_and_overlay_must_agree(tmp_path):
    portable,codex=candidate(tmp_path)
    assert not validate.validate_listing(tmp_path,portable,codex)
    codex['interface']['shortDescription']='Different listing'
    assert 'Portable and Codex listing metadata diverge' in validate.validate_listing(tmp_path,portable,codex)


@pytest.mark.parametrize('format',['portable','codex'])
def test_local_helper_execution_is_declared(tmp_path,format):
    portable,codex=candidate(tmp_path)
    target=portable['extensions']['com.openai'] if format=='portable' else codex
    target.pop('requires_local_executor')
    assert validate.validate_listing(tmp_path,portable,codex)


@pytest.mark.parametrize('mutation',['long_subtitle','secret_url','traversal','nonsquare','active_svg'])
def test_bad_listing_asset_or_text_is_rejected(tmp_path,mutation):
    portable,codex=candidate(tmp_path)
    interface=portable['extensions']['com.openai']['interface']
    if mutation=='long_subtitle': interface['shortDescription']='x'*31
    elif mutation=='secret_url': interface['supportURL']='https://user:password@example.test/support'
    elif mutation=='traversal': interface['logo']='./../private.svg'
    else:
        svg=tmp_path/'assets/icon.svg'
        text=svg.read_text()
        svg.write_text(text.replace('height="96"','height="48"') if mutation=='nonsquare' else text.replace('</svg>','<script>alert(1)</script></svg>'))
    codex['interface']=deepcopy(interface)
    assert validate.validate_listing(tmp_path,portable,codex)


def test_release_contains_directory_assets_and_policy():
    archive,_=package.build()
    with zipfile.ZipFile(archive) as package_zip:
        assert {'eventer/assets/icon.svg','eventer/PRIVACY.md'}<=set(package_zip.namelist())


@pytest.mark.parametrize('content',[
    '<style>@import url("https://example.test/external.css");</style>',
    '<rect width="96" height="96" fill="url(https://example.test/external.svg#paint)"/>',
    '<rect width="96" height="96" style="fill: url(https://example.test/external.svg#paint)"/>',
])
def test_remote_svg_resources_are_rejected(tmp_path,content):
    portable,codex=candidate(tmp_path)
    (tmp_path/'assets/icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96">'+content+'</svg>')
    assert validate.validate_listing(tmp_path,portable,codex)


def test_local_svg_paint_reference_remains_valid(tmp_path):
    portable,codex=candidate(tmp_path)
    (tmp_path/'assets/icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><defs><linearGradient id="paint"><stop stop-color="#145C54"/></linearGradient></defs><rect width="96" height="96" fill="url(#paint)"/></svg>')
    assert not validate.validate_listing(tmp_path,portable,codex)
