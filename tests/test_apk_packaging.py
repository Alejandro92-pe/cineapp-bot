import hashlib
import importlib.util
from pathlib import Path
import zipfile
import pytest

spec=importlib.util.spec_from_file_location('apk_packager',Path(__file__).resolve().parents[1]/'scripts/package_apks.py')
pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)

@pytest.fixture
def candidates(tmp_path,monkeypatch):
    sources={}
    for kind in ('android','tv'):
        path=tmp_path/f'{kind}.apk'
        with zipfile.ZipFile(path,'w') as apk:apk.writestr('classes.dex',b'https://app.quehay.live')
        sources[kind]=path
    state={'cert':pack.CERT,'debug':False,'package':None,'clear':'0x0'}
    def tool(exe,*args):
        if 'verify' in args:return f"Signer #1 certificate SHA-256 digest: {state['cert']}"
        if 'xmltree' in args:return f"A: android:usesCleartextTraffic(0x010104ec)=(type 0x12){state['clear']}\n"
        kind=Path(args[-1]).stem
        return f"package: name='{state['package'] or pack.PACKAGES[kind]}' versionCode='5' versionName='0.5.0'\nsdkVersion:'26'\nuses-permission: name='android.permission.INTERNET'\n"+('application-debuggable' if state['debug'] else '')
    monkeypatch.setattr(pack,'run_tool',tool)
    return sources,state

def test_package_contains_only_allowlisted_public_files(tmp_path,candidates):
    sources,_=candidates;out=tmp_path/'out'
    result=pack.package_apks(sources['android'],sources['tv'],tmp_path,out)
    with zipfile.ZipFile(out/'quehay-apps-siteground.zip') as archive:
        assert set(archive.namelist())=={'apps/.htaccess','apps/releases.json','apps/SHA256SUMS.txt','apps/QueHay-Android-0.5.0.apk','apps/QueHay-TV-0.5.0.apk'}
        for kind,item in result['releases'].items():
            assert hashlib.sha256(archive.read('apps/'+item['filename'])).hexdigest()==item['sha256']
    assert result['published'] is True
    assert (out/'activation/apk-releases.json').exists()

@pytest.mark.parametrize('patch',[{'cert':'b'*64},{'package':'live.quehay.tv.startupcheck'},{'debug':True},{'clear':'0xffffffff'}])
def test_bad_candidates_do_not_produce_a_distribution(tmp_path,candidates,patch):
    sources,state=candidates;state.update(patch);out=tmp_path/'out'
    with pytest.raises(ValueError):pack.package_apks(sources['android'],sources['tv'],tmp_path,out)
    assert not out.exists()

def test_local_origin_is_rejected_even_if_package_and_signature_match(tmp_path,candidates):
    sources,_=candidates
    with zipfile.ZipFile(sources['android'],'w') as apk:apk.writestr('classes.dex',b'https://app.quehay.live http://127.0.0.1:5031')
    with pytest.raises(ValueError,match='origen'):pack.package_apks(sources['android'],sources['tv'],tmp_path,tmp_path/'out')

def test_published_versions_are_immutable(tmp_path,candidates):
    sources,_=candidates;out=tmp_path/'out'
    pack.package_apks(sources['android'],sources['tv'],tmp_path,out)
    file=out/'siteground/apps/QueHay-Android-0.5.0.apk';file.write_bytes(b'previous bytes')
    with pytest.raises(ValueError,match='incrementa la versión'):pack.package_apks(sources['android'],sources['tv'],tmp_path,out)
    assert file.read_bytes()==b'previous bytes'
