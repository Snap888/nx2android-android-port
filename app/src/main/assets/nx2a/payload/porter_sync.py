#!/usr/bin/env python3
"""Keeps /root/nx2android complete, at the pinned commit and patched. Safe to call often: it only downloads when files are missing or the pinned commit changed.
The old tree is renamed aside before the new one goes in, so a failed step can never leave a half-deleted porter behind."""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

REPO = Path(os.environ.get('NX2A_REPO', Path.home() / 'nx2android'))
HERE = Path(__file__).resolve().parent
STATUS = Path(os.environ.get('NX2A_STATUS', '/root/patch_status.txt'))
REQUIRED = ['porter/cli.py', 'porter/pipeline.py', 'porter/upstream.py', 'nxnative/dm/android/tools/android_profile.py', 'nxnative/dm/android/build.py',
            'nxnative/dm/android/gfx_vk_core.c', 'nxnative/dm/games/game.py', 'nxnative/dm/tools/nacp.py']


def missing(root=None):
    root = Path(root or REPO)
    return [f for f in REQUIRED if not (root / f).is_file()]


def complete(): return not missing()


def state():
    m = missing()
    return 'ok' if not m else 'incomplete: missing ' + ', '.join(m[:3]) + (' ...' if len(m) > 3 else '')


MODE = Path(os.environ.get('NX2A_PORTER_MODE', Path.home() / '.config/nx2android/porter_mode'))


def mode():
    """'good' when the person chose the porter version known to work (payload.json porter_good) instead of upstream's newest; otherwise 'newest'."""
    try: return 'good' if MODE.read_text().strip() == 'good' else 'newest'
    except OSError: return 'newest'


def set_mode(m):
    MODE.parent.mkdir(parents=True, exist_ok=True)
    if m == 'good': MODE.write_text('good\n')
    else:
        try: MODE.unlink()
        except OSError: pass


def _payload():
    return json.loads((HERE / 'payload.json').read_text())


def _want():
    return _payload().get('porter_sha')


def commit():
    try: return (REPO / '.nx2a_sha').read_text().strip()[:9]
    except OSError: return ''


def local_ready():
    """Fast offline validation used on every GUI boot; no GitHub request or patch run."""
    try:
        have = (REPO / '.nx2a_sha').read_text().strip()
        patch_hash = hashlib.sha256((HERE / 'apply_patches.py').read_bytes()).hexdigest()
        stamp = (REPO / '.nx2a_patched').read_text().strip().splitlines()
        return complete() and len(have) == 40 and stamp == [have, patch_hash], have
    except OSError:
        return False, ''


def upstream_head():
    """Newest commit of upstream's main branch (the GitHub 'sha' media type returns just the id)."""
    if os.environ.get('NX2A_UPSTREAM_SHA'): return os.environ['NX2A_UPSTREAM_SHA']
    req = urllib.request.Request('https://api.github.com/repos/shirai91/nx2android/commits/main', headers={'Accept': 'application/vnd.github.sha', 'User-Agent': 'nx2android-app'})
    sha = urllib.request.urlopen(req, timeout=15).read().decode().strip()
    if len(sha) != 40: raise ValueError('unexpected answer: ' + sha[:60])
    return sha


def _download(url):
    last = None
    for _ in range(3):
        try: return urllib.request.urlopen(url, timeout=60).read()
        except Exception as e: last = e; time.sleep(2)
    raise last


def patch():
    r = subprocess.run([sys.executable, str(HERE / 'apply_patches.py'), str(REPO)], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    try: STATUS.write_text(out + f'\nexit {r.returncode}\n')
    except OSError: pass
    if r.returncode != 0:
        detail = out.replace(chr(10), ' | ')[:1800] or f'exit {r.returncode}'
        raise RuntimeError('NGR porter patch validation failed: ' + detail)
    try:
        have = (REPO / '.nx2a_sha').read_text().strip()
        patch_hash = hashlib.sha256((HERE / 'apply_patches.py').read_bytes()).hexdigest()
        (REPO / '.nx2a_patched').write_text(have + '\n' + patch_hash + '\n')
    except OSError: pass
    return out


def _install(sha, log, must_patch):
    """Downloads sha, checks it is complete and that our patches still fit, then swaps it in. Raises on any problem and leaves the current tree untouched."""
    tmp = REPO.with_name(REPO.name + '.new')
    try:
        url = (os.environ.get('NX2A_PORTER_URL') or 'https://codeload.github.com/shirai91/nx2android/tar.gz/{sha}').format(sha=sha)
        data = _download(url)
        shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as t:
            t.extractall(tmp, filter='data') if hasattr(tarfile, 'data_filter') else t.extractall(tmp)
        kids = list(tmp.iterdir())
        src = kids[0] if len(kids) == 1 and kids[0].is_dir() else tmp
        bad = missing(src)
        if bad: raise RuntimeError('the download is incomplete, missing ' + ', '.join(bad[:3]))
        r = subprocess.run([sys.executable, str(HERE / 'apply_patches.py'), str(src)], capture_output=True, text=True)
        if r.returncode != 0: raise RuntimeError('our patches no longer fit this commit: ' + (r.stdout + r.stderr).strip().replace(chr(10), ' | ')[:1200])
        (src / '.nx2a_sha').write_text(sha)
        old = None
        if REPO.exists():
            old = REPO.with_name(f'{REPO.name}.old{int(time.time())}'); REPO.rename(old)
        try: src.rename(REPO)
        except OSError:
            if old is not None: old.rename(REPO)
            raise
        if old is not None: shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sync(force=False, log=print):
    """Validate the active porter first; if newest no longer accepts our patches, fall back to the pinned known-good checkout."""
    pl = _payload(); pinned = pl.get('porter_good') or pl.get('porter_sha'); track = pl.get('porter_track') == 'main'
    if mode() == 'good' and pl.get('porter_good'):
        pinned = pl['porter_good']; track = False
    try: have = (REPO / '.nx2a_sha').read_text().strip()
    except OSError: have = ''
    target = pinned
    if track:
        try: target = upstream_head()
        except Exception as e: log(f'cannot ask GitHub for the newest porter ({e}); keeping {have[:9] or pinned[:9]}'); target = have or pinned

    msgs = []
    for sha, must in ((target, True), (pinned, False)):
        if not sha or (sha == pinned and sha == target and msgs):
            break
        if not force and complete() and have == sha:
            try:
                patch()
                return True, ' ; '.join(msgs + ['porter ready (' + have[:9] + ')'])
            except Exception as e:
                m = f'porter {sha[:9]} is present but its NGR patches are invalid: {e}'
                log(m); msgs.append(m)
                # Do not compile from a complete-but-unpatched tree. If this is
                # the moving upstream branch, try the pinned known-good source.
                if sha == target and track and pinned != target:
                    continue
                try: STATUS.write_text(' ; '.join(msgs) + '\n')
                except OSError: pass
                return False, ' ; '.join(msgs)

        log(f'downloading the porter ({sha[:9]})')
        try:
            _install(sha, log, must_patch=must)
            patch()
            return True, ' ; '.join(msgs + [f'porter {sha[:9]} installed and patched'])
        except Exception as e:
            m = f'porter {sha[:9]} not installed: {e}'
            log(m); msgs.append(m)
            if complete() and sha == target and track:
                # The previous checkout may still be usable. Validate it before
                # keeping it; otherwise continue to the pinned fallback.
                try:
                    patch()
                    return True, ' ; '.join(msgs + [f'keeping {have[:9] or "the current porter"}'])
                except Exception as previous_error:
                    m = f'current porter patch validation also failed: {previous_error}'
                    log(m); msgs.append(m)

    try: STATUS.write_text(' ; '.join(msgs) + '\n')
    except OSError: pass
    return False, ' ; '.join(msgs) or 'porter unavailable or patch validation failed'


if __name__ == '__main__':
    if '--local-check' in sys.argv:
        ok, have = local_ready()
        print('cached porter ' + have[:9] + ' is complete and patched' if ok else 'porter cache is incomplete or needs patch validation')
        sys.exit(0 if ok else 1)
    ok, msg = sync(force='--force' in sys.argv); print(msg); sys.exit(0 if ok else 1)
