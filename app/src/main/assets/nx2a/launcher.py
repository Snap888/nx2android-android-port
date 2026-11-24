#!/usr/bin/env python3
"""Stable boot script (changes rarely). Runs the newest valid payload, keeps it updated from GitHub, rolls back a bad update, and keeps the pinned porter patched."""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, threading, time, urllib.request
from pathlib import Path

D = Path(os.environ.get('NX2A_DIR', '/nx2a'))
OTA = Path(os.environ.get('NX2A_OTA', '/root/ota'))
REPO = Path(os.environ.get('NX2A_REPO', '/root/nx2android'))
MARK = Path(os.environ.get('NX2A_SETUP_MARK', '/root/.nx2a_setup'))
STATUS = Path(os.environ.get('NX2A_STATUS', '/root/patch_status.txt'))
BUNDLED = D / 'payload'


def log(*a): print('[launcher]', *a, flush=True)
def sha(b): return hashlib.sha256(b).hexdigest()
def run(cmd, **kw): return subprocess.run(cmd, text=True, capture_output=True, **kw)


def manifest(d):
    try: return json.loads((d / 'payload.json').read_text())
    except Exception: return None


def valid(d):
    m = manifest(d)
    try: return bool(m) and all(sha((d / rel).read_bytes()) == h for rel, h in m['files'].items())
    except Exception: return False


def pick():
    b, o = manifest(BUNDLED), manifest(OTA)
    if o and b and int(o['version']) > int(b['version']) and valid(OTA): return OTA
    return BUNDLED


def setup_if_needed(P, m):
    want = int(m.get('setup', 1))
    try: have = int(MARK.read_text().strip())
    except Exception: have = 0
    if have < want:
        log('running setup', want)
        r = subprocess.run(['bash', str(P / 'inner_setup.sh')])
        log('setup exit', r.returncode)


def sync_porter(P, m):
    # Use the same selector as the GUI/build path. The old launcher pinned
    # porter_sha while porter_sync followed upstream (or porter_good), causing
    # the two processes to replace each other's checkout on every app start.
    script = P / 'porter_sync.py'
    if not script.is_file():
        log('porter sync script is missing:', script)
        return
    r = run([sys.executable, str(script)])
    detail = (r.stdout + r.stderr).strip()
    try: STATUS.write_text(detail + f'\nexit {r.returncode}\n')
    except OSError: pass
    log('porter sync: exit', r.returncode)
    for line in detail.splitlines():
        log('porter:', line)
    if r.returncode != 0:
        log('WARNING: porter is not ready; GUI startup will continue and port operations will report the error')

def fetch(url):
    last = None
    for _ in range(3):
        try: return urllib.request.urlopen(url, timeout=12).read()
        except Exception as e: last = e; time.sleep(2)
    raise last


def update():
    try:
        cfg = json.loads((D / 'update.json').read_text())
        base = os.environ.get('NX2A_UPDATE_BASE') or f"https://raw.githubusercontent.com/{cfg['repo']}/{cfg.get('branch', 'main')}/{cfg['path']}"
        man = json.loads(fetch(base + '/payload.json'))
        cur = max(int(manifest(BUNDLED)['version']), int((manifest(OTA) or {'version': -1})['version']))
        if int(man['version']) <= cur: return False
        new = OTA.with_name(OTA.name + '.new'); shutil.rmtree(new, ignore_errors=True)
        for rel, h in man['files'].items():
            if rel.startswith('/') or '..' in rel.split('/'): raise ValueError('bad path ' + rel)
            data = fetch(base + '/' + rel)
            if sha(data) != h: raise ValueError('hash mismatch ' + rel)
            (new / rel).parent.mkdir(parents=True, exist_ok=True); (new / rel).write_bytes(data)
        (new / 'payload.json').write_text(json.dumps(man))
        shutil.rmtree(OTA, ignore_errors=True); new.rename(OTA)
        log('update downloaded: version', man['version']); return True
    except Exception as e:
        log('update check failed:', e); return False


def updater():
    time.sleep(5)
    while True:
        update(); time.sleep(300)


def main():
    threading.Thread(target=updater, daemon=True).start()
    crashes = 0
    while True:
        P = pick(); m = manifest(P)
        setup_if_needed(P, m); sync_porter(P, m)
        env = dict(os.environ, NX2A_VERSION=str(m['version']))
        log('starting payload version', m['version'], 'from', P)
        t0 = time.time()
        rc = subprocess.run([sys.executable, str(P / 'webgui/server.py')], env=env).returncode
        if rc == 75: crashes = 0; continue          # the GUI asked for a restart (to apply an update)
        log('server exited with', rc)
        if P == OTA and time.time() - t0 < 20:
            crashes += 1
            if crashes >= 2: log('downloaded payload keeps failing, rolling back'); shutil.rmtree(OTA, ignore_errors=True); crashes = 0
        time.sleep(3)


if __name__ == '__main__': main()
