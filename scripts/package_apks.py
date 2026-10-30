"""Validate two already-built APKs and prepare a static SiteGround upload locally.

No uploads, credentials, keystores, signing, deletion or production connections.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

CERT = '8b9eb1ea50e568ea54ba1dd1859fcef647edd3f78a4dd88abc0928508decf681'
PACKAGES = {'android': 'live.quehay.app.preview', 'tv': 'live.quehay.tv'}
HTACCESS = '''Options -Indexes
AddType application/vnd.android.package-archive .apk
<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
<FilesMatch "\\.apk$">
Header always set Content-Disposition "attachment"
Header always set Cache-Control "public, max-age=31536000, immutable"
</FilesMatch>
<Files "releases.json">
Header always set Cache-Control "no-store"
</Files>
</IfModule>
'''

def run_tool(tool, *args):
    result = subprocess.run([str(tool), *map(str, args)], capture_output=True, text=True, check=True)
    return result.stdout

def inspect_apk(path, kind, tools):
    signature = run_tool(tools/'apksigner.bat', 'verify', '--print-certs', path)
    certificates = re.findall(r'certificate SHA-256 digest: ([a-f0-9]{64})', signature)
    if certificates != [CERT]:
        raise ValueError(f'{kind}: la firma no coincide con la instalación existente')
    badging = run_tool(tools/'aapt.exe', 'dump', 'badging', path)
    manifest = run_tool(tools/'aapt.exe', 'dump', 'xmltree', path, 'AndroidManifest.xml')
    package = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging)
    if not package or package[1] != PACKAGES[kind]:
        raise ValueError(f'{kind}: paquete incorrecto o variante local de prueba')
    if not re.fullmatch(r'\d+\.\d+\.\d+', package[3]):
        raise ValueError(f'{kind}: versión inválida')
    if 'application-debuggable' in badging:
        raise ValueError(f'{kind}: no se admite una APK depurable')
    permissions = re.findall(r"uses-permission: name='([^']+)'", badging)
    if permissions != ['android.permission.INTERNET']:
        raise ValueError(f'{kind}: permisos inesperados')
    if not re.search(r'usesCleartextTraffic[^\n]*0x0\s*$', manifest, re.M):
        raise ValueError(f'{kind}: requiere tráfico cifrado')
    if "sdkVersion:'26'" not in badging:
        raise ValueError(f'{kind}: revisar compatibilidad mínima')
    # BuildConfig holds the launch origin. Reject local builds even if repackaged.
    with zipfile.ZipFile(path) as apk:
        dex = b''.join(apk.read(n) for n in apk.namelist() if re.fullmatch(r'classes\d*\.dex', n))
        if b'https://app.quehay.live' not in dex or b'http://127.0.0.1:' in dex or b'http://192.168.' in dex:
            raise ValueError(f'{kind}: origen de compilación no apto para distribuir')
        if any('startup_check_network' in n for n in apk.namelist()):
            raise ValueError(f'{kind}: contiene configuración de prueba')
    data = path.read_bytes()
    filename = f"QueHay-{'Android' if kind == 'android' else 'TV'}-{package[3]}.apk"
    return {'version': package[3], 'versionCode': int(package[2]), 'package': package[1],
            'filename': filename, 'url': f'https://quehay.live/apps/{filename}',
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'signerSha256': CERT, 'minAndroid': 8}

def package_apks(android, tv, tools, out):
    sources = {'android': android.resolve(), 'tv': tv.resolve()}
    releases = {kind: inspect_apk(path, kind, tools) for kind, path in sources.items()}
    # Immutable filenames: never silently replace an existing binary.
    apps = out/'siteground/apps'
    for item in releases.values():
        target = apps/item['filename']
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('El archivo publicado con esa versión ya contiene otros bytes; incrementa la versión')
    apps.mkdir(parents=True, exist_ok=True)
    for kind, item in releases.items():
        shutil.copyfile(sources[kind], apps/item['filename'])
    (apps/'.htaccess').write_text(HTACCESS, encoding='utf-8')
    data = {'schema': 1, 'published': True, 'releases': releases}
    (apps/'releases.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    (apps/'SHA256SUMS.txt').write_text(''.join(f"{r['sha256']}  {r['filename']}\n" for r in releases.values()), encoding='ascii')
    activation = out/'activation'; activation.mkdir(exist_ok=True)
    (activation/'apk-releases.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    archive = out/'quehay-apps-siteground.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in ['.htaccess', 'releases.json', 'SHA256SUMS.txt'] + [r['filename'] for r in releases.values()]:
            bundle.write(apps/name, 'apps/'+name)
    return data

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--android', type=Path, required=True)
    parser.add_argument('--tv', type=Path, required=True)
    parser.add_argument('--build-tools', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    data = package_apks(args.android, args.tv, args.build_tools, args.out)
    print(json.dumps(data, indent=2))
