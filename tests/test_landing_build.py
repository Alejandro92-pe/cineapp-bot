"""The published HTML must invalidate year-long image caches on asset changes."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def test_build_versions_background_and_preserves_existing_seo(tmp_path):
    source=tmp_path/'landing'
    shutil.copytree(ROOT/'landing',source)
    output=tmp_path/'public'
    output.mkdir()
    (output/'sitemap.xml').write_text('existing sitemap')
    legacy=output/'old-title.html'
    legacy.write_text('existing title')

    def build():
        subprocess.run([sys.executable,str(source/'build.py'),'--out',str(output)],check=True,capture_output=True)
        return (output/'index.html').read_text(encoding='utf8')

    first=build()
    for filename in ('cover.webp','cover-mobile.webp','selection.js'):
        asset=source/'assets'/filename
        digest=hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
        version=f'{asset.stem}.{digest}{asset.suffix}'
        assert f'assets/{version}' in first
        assert (output/'assets'/version).read_bytes()==asset.read_bytes()
    assert 'https://app.quehay.live' in first
    assert (output/'sitemap.xml').read_text()=='existing sitemap'
    assert legacy.read_text()=='existing title'
    assert build()==first

    background=source/'assets/cover.webp'
    background.write_bytes(background.read_bytes()+b'changed asset')
    assert build()!=first
