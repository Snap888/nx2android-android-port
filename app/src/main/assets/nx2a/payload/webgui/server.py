#!/usr/bin/env python3
"""nx2android phone GUI: a local web app (stdlib only) that drives `python -m porter`. Only the app itself can use it: a random token, a Host check and a same-site cookie guard every request."""
import contextlib, glob, hashlib, hmac, http.cookies, io, json, mimetypes, os, re, signal, subprocess, sys, threading, time, zipfile, shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen

HERE = Path(__file__).parent


def reset_signals():
    """Android's Java process leaves some signals blocked or ignored, and children inherit that. Termux clears them before starting a shell; programs such as
    the .NET runtime assume a normal Unix process. Everything started from here (including every job) inherits the clean state."""
    try:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, signal.valid_signals())
        for s in signal.valid_signals():
            if s in (signal.SIGKILL, signal.SIGSTOP, signal.SIGPIPE): continue
            try:
                if signal.getsignal(s) == signal.SIG_IGN: signal.signal(s, signal.SIG_DFL)
            except (OSError, ValueError, RuntimeError): pass
    except Exception: pass


def sig_state():
    try: return {k: v for k, v in (l.split(':\t', 1) for l in Path('/proc/self/status').read_text().splitlines() if ':\t' in l) if k in ('SigBlk', 'SigIgn', 'SigCgt', 'Seccomp', 'NoNewPrivs')}
    except OSError: return {}


SIG_BEFORE = sig_state()
reset_signals()
os.umask(0o022)
sys.path.insert(0, str(HERE.parent))
import porter_sync   # noqa: E402
import dotnet_probe   # noqa: E402
import prebuilt   # noqa: E402
import adb_auto   # noqa: E402
import server_state   # noqa: E402
server_state.set_before(SIG_BEFORE)
REPO = Path(os.environ.get('NX2A_REPO', Path.home() / 'nx2android'))
PORT = int(os.environ.get('NX2A_PORT', '7331'))
TOKEN = os.environ.get('NX2A_TOKEN', '')
VERSION = os.environ.get('NX2A_VERSION', '0')
HOSTS = {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
ENV = {k: v for k, v in os.environ.items() if k != 'NX2A_TOKEN'}
ENV.update(PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', DOTNET_EnableWriteXorExecute='0', DOTNET_SYSTEM_GLOBALIZATION_INVARIANT='1')
CFG = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'nx2android' / 'config.json'
LIBRARY = CFG.parent / 'library.json'
GAMES = Path(os.environ.get('NX2A_GAMES', '/root/games'))
OTA = Path(os.environ.get('NX2A_OTA', '/root/ota'))
STATUS = Path(os.environ.get('NX2A_STATUS', '/root/patch_status.txt'))
DEFAULT_OUT = '/sdcard/Switch/Ports'
GAME_EXT = ('.nsp', '.xci', '.nsz', '.xcz')
JOB = {'p': None, 'lines': [], 'done': True, 'code': None, 'kind': '', 'stage': '', 'frac': None, 'seq': 0}
LOCK = threading.Lock()


def cfg():
    try: return json.loads(CFG.read_text())
    except (OSError, ValueError): return {}


def library_read():
    try:
        value = json.loads(LIBRARY.read_text())
        if value.get('schema_version') == 1 and isinstance(value.get('games'), list):
            return value
    except (OSError, ValueError, AttributeError):
        pass
    return {'schema_version': 1, 'games': []}


def library_write(value):
    LIBRARY.parent.mkdir(parents=True, exist_ok=True)
    tmp = LIBRARY.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, LIBRARY)


def library_update(game_id, mutate):
    catalog = library_read()
    for game in catalog['games']:
        if game.get('id') == game_id:
            mutate(game)
            library_write(catalog)
            return game
    return None

# Switch icons are fetched lazily from the public Nlib catalogue. Downloads are
# cached locally; a user's manually selected cover always takes precedence.
COVER_CACHE = CFG.parent / 'covers'
COVER_JOB = {'running': False, 'done': True, 'found': 0, 'checked': 0, 'error': ''}
COVER_LOCK = threading.Lock()


def _cover_cache_path(game_id):
    return COVER_CACHE / (game_id + '.jpg')


def _cover_is_readable(game):
    try:
        p = Path(game.get('cover_path') or '').resolve(strict=True)
        return p.is_file() and p.stat().st_size > 0
    except (OSError, RuntimeError):
        return False


def _fetch_switch_icon(game):
    game_id = str(game.get('id') or '')
    title_id = str(game.get('title_id') or '').upper()
    if not re.fullmatch(r'[0-9a-f]{20}', game_id) or not re.fullmatch(r'[0-9A-F]{16}', title_id):
        return False
    if _cover_is_readable(game):
        return False
    api_url = 'https://api.nlib.cc/nx/' + title_id + '?fields=name,icon'
    req = Request(api_url, headers={'User-Agent': 'NGR-Launcher/1.0', 'Accept': 'application/json'})
    with urlopen(req, timeout=10) as response:
        meta = json.loads(response.read(256 * 1024).decode('utf-8'))
    icon_url = meta.get('icon') if isinstance(meta, dict) else None
    if not isinstance(icon_url, str) or not icon_url.startswith('https://api.nlib.cc/nx/'):
        return False
    image_req = Request(icon_url, headers={'User-Agent': 'NGR-Launcher/1.0'})
    with urlopen(image_req, timeout=15) as response:
        content_type = (response.headers.get('Content-Type') or '').lower()
        data = response.read(8 * 1024 * 1024 + 1)
    if not content_type.startswith('image/') or not data or len(data) > 8 * 1024 * 1024:
        return False
    COVER_CACHE.mkdir(parents=True, exist_ok=True)
    target = _cover_cache_path(game_id)
    temp = target.with_suffix('.jpg.tmp')
    temp.write_bytes(data)
    temp.replace(target)
    library_update(game_id, lambda g: g.update(
        cover_path=str(target.resolve()), cover_source='nlib-icon',
        title=(g.get('title') or meta.get('name') or 'Nintendo Switch game'),
        updated_at=int(time.time())))
    return True


def _run_cover_refresh():
    with COVER_LOCK:
        COVER_JOB.update(running=True, done=False, found=0, checked=0, error='')
    try:
        games = library_read().get('games', [])
        for game in games:
            if game.get('cover_source') != 'nlib-icon' and _cover_is_readable(game):
                continue
            try:
                if _fetch_switch_icon(game):
                    COVER_JOB['found'] += 1
            except Exception as error:
                COVER_JOB['error'] = str(error)[:240]
            COVER_JOB['checked'] += 1
    finally:
        with COVER_LOCK:
            COVER_JOB['running'] = False
            COVER_JOB['done'] = True


def start_cover_refresh():
    with COVER_LOCK:
        if COVER_JOB['running']:
            return False
        COVER_JOB.update(running=True, done=False, found=0, checked=0, error='')
    def worker():
        try:
            _run_cover_refresh()
        except Exception as error:
            with COVER_LOCK:
                COVER_JOB.update(running=False, done=True, error=str(error)[:240])
    threading.Thread(target=worker, name='NGR-CoverArt', daemon=True).start()
    return True


def extract_runtime_libraries(apk_path, data_dir):
    """Extract the native runtime from the porter's build output; the game APK is never installed or retained."""
    apk = Path(apk_path)
    data = Path(data_dir)
    if not apk.is_file() or not data.is_dir():
        raise FileNotFoundError(f'game build output missing: APK={apk}, data={data}')
    names = []
    with zipfile.ZipFile(apk) as z:
        libs = [n for n in z.namelist() if n.startswith('lib/arm64-v8a/') and n.endswith('.so') and Path(n).name.startswith('lib')]
        if not any(Path(n).name == 'libdmhost.so' for n in libs):
            raise ValueError('built APK has no lib/arm64-v8a/libdmhost.so')
        for name in libs:
            base = Path(name).name
            if base in ('.', '..') or '/' in base or '\\\\' in base:
                raise ValueError(f'unsafe native library name: {name}')
            target = data / base
            tmp = target.with_suffix(target.suffix + '.tmp')
            with z.open(name) as src, tmp.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            tmp.replace(target)
            names.append(base)
        # The touch-gamepad theme is an APK asset, not a shared host resource. Move it into the game payload
        # because NGR's shell APK has a different AssetManager from the old per-game APK.
        for name in z.namelist():
            if not name.startswith('assets/') or name.endswith('/'):
                continue
            rel = Path(name[len('assets/'):])
            if not rel.parts or any(part in ('', '.', '..') for part in rel.parts):
                raise ValueError(f'unsafe APK asset path: {name}')
            target = data / 'assets' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + '.tmp')
            with z.open(name) as src, tmp.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            tmp.replace(target)
    # This APK was only a build container for the native library. NGR owns the sole installable APK.
    apk.unlink()
    return sorted(names)


def register_port_result(lines):
    """Register a port as a game payload in NGR; extract its native library and discard the per-game APK."""
    result = None
    for line in reversed(lines):
        if line.startswith('{'):
            try:
                event = json.loads(line)
                if event.get('ev') == 'result':
                    result = event
                    break
            except ValueError:
                pass
    if not result or not result.get('data'):
        return
    package = str(result.get('package') or 'unknown.none.nx2android')
    data_path = str(result['data'])
    title_id = str(result.get('title_id') or '')
    identity = 'switch:' + title_id.upper() if re.fullmatch(r'[0-9A-Fa-f]{16}', title_id) else (package + ':' + data_path)
    game_id = hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]
    catalog = library_read()
    source_folder = str(JOB.get('source_folder') or '')
    existing = next((g for g in catalog['games'] if g.get('id') == game_id), None)
    if not existing and title_id:
        existing = next((g for g in catalog['games'] if
                         g.get('title_id', '').upper() == title_id.upper() or
                         (source_folder and g.get('source_folder') == source_folder)), None)
    if existing and existing.get('id') != game_id:
        # Migrate an earlier package-hash shortcut to the stable title-ID shortcut.
        catalog['games'] = [g for g in catalog['games'] if g.get('id') != existing.get('id')]
    title = str(result.get('name') or result.get('app_name') or Path(data_path).name.removesuffix('-data'))
    runtime_libs = []
    runtime_error = ''
    try:
        data_dir = Path(data_path)
        if result.get('runtime') and (data_dir / 'libdmhost.so').is_file():
            runtime_libs = sorted(p.name for p in data_dir.glob('*.so') if p.is_file())
        elif result.get('apk'):
            # Backward compatibility for a port built by an older, already-synced porter.
            runtime_libs = extract_runtime_libraries(result['apk'], data_path)
        else:
            raise ValueError('porter did not emit libdmhost.so directly into the game data pack')
        if 'libdmhost.so' not in runtime_libs:
            raise ValueError('libdmhost.so is missing from the game data pack')
    except Exception as e:
        runtime_error = str(e)
        JOB['lines'].append(f'[NGR runtime] native runtime missing: {runtime_error}')

    # Export the exact profile header used by the native build. This is the first
    # versioned JSON ABI artifact; the current host still uses its compiled macros.
    profile_ready = False
    profile_error = ''
    if re.fullmatch(r'[0-9A-Fa-f]{16}', title_id):
        exporter = HERE.parent / 'profile_export.py'
        try:
            exported = subprocess.run(
                [sys.executable, str(exporter), '--repo', str(REPO), '--game-id', title_id,
                 '--data', data_path, '--source-folder', str(JOB.get('source_folder') or '')],
                capture_output=True, text=True, timeout=90, env=ENV
            )
            profile_ready = exported.returncode == 0
            detail = (exported.stdout + exported.stderr).strip()
            if detail:
                JOB['lines'].extend(detail.splitlines()[-12:])
            if not profile_ready:
                profile_error = detail[-1200:] or f'profile exporter exited {exported.returncode}'
        except Exception as e:
            profile_error = str(e)
        if not profile_ready:
            JOB['lines'].append(f'[NGR profile] export unavailable (legacy compiled host remains usable): {profile_error}')
    else:
        profile_error = 'porter result has no valid 16-digit title_id'
        JOB['lines'].append(f'[NGR profile] {profile_error}')

    ready = not runtime_error
    item = {
        'id': game_id, 'title': title, 'platform': 'switch', 'title_id': title_id,
        'package': package, 'apk_path': '', 'data_path': data_path,
        'runtime_so_path': str(Path(data_path) / 'libdmhost.so') if ready else '',
        'runtime_libs': runtime_libs, 'runtime_ready': ready, 'runtime_installed': False,
        'profile_path': str(Path(data_path) / 'profile.json') if profile_ready else '',
        'runtime_profile_ready': profile_ready, 'runtime_profile_error': profile_error,
        'source_folder': source_folder,
        'status': 'runtime_ready' if ready else 'runtime_extract_failed',
        'runtime_error': runtime_error,
        'settings': (existing or {}).get('settings', {
            'touch': bool(JOB.get('port_options', {}).get('touch')),
            'fps60': bool(JOB.get('port_options', {}).get('fps60')),
            'vulkan_driver': str(JOB.get('port_options', {}).get('vulkan_driver') or '')
        }),
        'cover_path': (existing or {}).get('cover_path', ''),
        'created_at': (existing or {}).get('created_at', int(time.time())),
        'updated_at': int(time.time())
    }
    if existing:
        catalog['games'] = [item if g.get('id') == game_id else g for g in catalog['games']]
    else:
        catalog['games'].append(item)
    library_write(catalog)
    if ready:
        JOB['lines'].append(f'[NGR runtime] {len(runtime_libs)} native libraries are already in the game data pack; no per-game APK was generated.')


def job_env():
    """The base environment plus the .NET workaround the probe found, if any."""
    e = dict(ENV)
    e.update(prebuilt.env())   # the CI-built .NET tools, when they are installed and start
    e['NX2A_NGR'] = '1'        # the porter emits a native runtime + data pack, never a per-game APK
    return e


UPD = {'t': 0, 'msg': 'not checked yet'}


def check_update():
    """Same download-and-verify as the launcher's, so the banner appears without restarting the app."""
    try:
        sys.path.insert(0, os.environ.get('NX2A_DIR', '/nx2a'))
        import launcher
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): got = launcher.update()
        UPD.update(t=time.time(), msg=(buf.getvalue().strip().splitlines() or ['up to date'])[-1])
        return got
    except Exception as e:
        UPD.update(t=time.time(), msg=f'update check failed: {e}'); return False


def auto_porter():
    """Follows upstream's newest commit, but never swaps the porter while a job is running."""
    time.sleep(60)
    while True:
        try:
            if JOB['done']: porter_sync.sync()
        except Exception as e: print('porter follow failed:', e, flush=True)
        time.sleep(6 * 3600)


def auto_update():
    time.sleep(20)
    while True:
        check_update(); time.sleep(300)


def need_prebuilt():
    """The .NET tools built in the cloud with runtimes that start on this phone. Returns True when they are active."""
    try:
        if prebuilt.active(): return True
        prebuilt.install()
        return bool(prebuilt.active())
    except Exception as e: print('prebuilt tools failed:', e, flush=True); return False


def need_dotnet():
    need_prebuilt()   # the standard .NET runtime does not start under proot on these phones; only the ready-made tools are used


def need_porter():
    # Always verify the selected upstream checkout and every NGR patch before a
    # build. A complete directory is not proof that it contains our patches.
    ok, message = porter_sync.sync()
    if not ok: raise RuntimeError('NGR porter is unavailable: ' + message)
    porter_sync.patch()


def porter(*args, timeout=120):
    need_porter()
    r = subprocess.run([sys.executable, '-m', 'porter', *args], cwd=REPO, env=job_env(), capture_output=True, text=True, timeout=timeout)
    return r.stdout, r.stderr, r.returncode


def norm_path(p):
    """/storage/emulated/0/x and /storage/self/primary/x are /sdcard/x here: the Android file picker and file managers show the first, but only /sdcard is visible inside the app's Ubuntu."""
    if isinstance(p, str):
        for pre in ('/storage/emulated/0', '/storage/self/primary', '/mnt/sdcard', '/sdcard0'):
            if p == pre or p.startswith(pre + '/'): return '/sdcard' + p[len(pre):]
    return p


def adb_ready():
    """True when adb lists a device that is ready (wireless debugging to this phone is connected)."""
    try:
        out, _, _ = porter('devices', '--json', timeout=40)
        return any(d.get('state') == 'device' for d in json.loads(out))
    except (ValueError, OSError, subprocess.TimeoutExpired, AttributeError): return False


def start_job(argv, kind=''):
    """Returns at once: the preparation (porter sources, ready-made .NET tools: downloads that can take minutes) runs in the job's own thread, so the screen never waits on it."""
    with LOCK:
        if (JOB['p'] and JOB['p'].poll() is None) or JOB.get('starting'): return False
        JOB.update(lines=[], done=False, code=None, kind=kind, stage='preparing', frac=None, seq=JOB['seq'] + 1, starting=True)

    def run():
        try:
            if kind in ('port', 'tools', 'install'):
                JOB['lines'].append('preparing: the porter...'); need_porter()
            if kind in ('port', 'tools'):
                JOB['lines'].append('preparing: the .NET tools...'); need_dotnet()   # the ready-made tools first: with them active the porter does not download the 1.5 GB .NET SDK
            p = subprocess.Popen(argv, cwd=REPO, env=job_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', start_new_session=True)
        except Exception as e:
            JOB['lines'].append(f'could not start: {e}'); JOB['code'] = 1; JOB['starting'] = False; JOB['done'] = True; return
        JOB['p'] = p; JOB['starting'] = False
        pump(p)

    def pump(p):
        for ln in p.stdout:
            ln = ln.rstrip('\n'); JOB['lines'].append(ln)
            try:
                if ln.startswith('{'):
                    ev = json.loads(ln)
                    if ev.get('ev') == 'stage': JOB['stage'] = f"{ev.get('k')}/{ev.get('n')} {ev.get('name')}"; JOB['frac'] = None
                    elif ev.get('ev') == 'progress' and ev.get('frac') is not None: JOB['frac'] = ev['frac']
                elif ln.strip(): JOB['stage'] = ln.strip()[:70]
            except ValueError: pass
        JOB['code'] = p.wait()
        if JOB['kind'] == 'runtime_install' and JOB['code'] == 0:
            gid = JOB.get('runtime_game_id', '')
            library_update(gid, lambda g: g.update(runtime_installed=True, runtime_installed_at=int(time.time()), updated_at=int(time.time())))
            JOB['lines'].append('[NGR runtime] installed and verified; launch is now available from Library.')
        if JOB['kind'] == 'tools' and JOB['code'] == 0:     # check right away that .NET starts on this phone
            try:
                JOB['lines'].append('ready-made .NET tools:'); JOB['lines'].extend('  ' + l for l in prebuilt.install())
            except Exception as e: JOB['lines'].append(f'.NET check failed: {e}')
        if JOB['kind'] == 'port':
            try:
                txt = '\n'.join(l for l in JOB['lines'] if l.startswith('{"ev": "say"'))
                if JOB.get('fps60') and JOB['code'] == 0 and ('keeps its own frame rate' in txt or 'cannot be applied' in txt):
                    JOB['lines'].append('NOTE: 60 fps was NOT applied to this port: there is no community 60 fps config (FPSLocker-Warehouse) for this exact game version, or it could not be used. The game keeps its own frame rate (see the "60 fps" line above).')
                red = ([l for l in txt.splitlines() if '[RED]' in l] or [''])[-1]   # the failure itself: only a failed on-device step is an adb matter (a host build or a shader error is not)
                devfail = any(k in red for k in ('Oodle decoder', 'on the device', 'captured only', 'GLSLC capture', 'adb'))
                if devfail and JOB['code'] != 0 and ('to push' in txt or 'exit 139' in '\n'.join(JOB['lines'])):
                    JOB['lines'].append('HINT: adb is connected (the game was sent to the phone) but the game crashed there. Send the last lines above. If a line says "[RED] main build ... is not the tested ..." the port used a game version the profile has no fixes for: put the game\'s update NSP (the version named after "tested on") in the same folder as the base game and port again.')
                elif devfail and JOB['code'] != 0:
                    JOB['lines'].append('HINT: this game\'s shaders need a device connected over adb. Device tab: pair (Settings > Developer options > Wireless debugging > Pair with code), connect, List devices; then port again.')
            except Exception: pass
        if JOB['kind'] == 'port' and JOB['code'] == 0:
            try: register_port_result(JOB['lines'])
            except Exception as e: JOB['lines'].append(f'Could not add game to library: {e}')
        if JOB['kind'] == 'port' and JOB['code'] == 0 and not JOB.get('keep'):
            try:
                res = next((json.loads(l) for l in reversed(JOB['lines']) if l.startswith('{"ev": "result"')), {})
                freed = clean_work((res.get('apk'), res.get('data')))
                JOB['lines'].append(f'Deleted the working files: {freed / 1e9:.1f} GB of the phone storage used by the app is free again. The APK and data are in the output folder.')
            except Exception as e: JOB['lines'].append(f'Could not delete the working files: {e}')
        JOB['done'] = True
    threading.Thread(target=run, daemon=True).start()
    return True


def rm_tree(p):
    """rmtree that also removes read-only files and folders (game extractions often are): the owner may delete them once it makes them writable. Returns the first error or ''."""
    import shutil, stat
    errs = []
    def fix(func, path, exc_info):
        try:
            os.chmod(os.path.dirname(path) or '.', 0o700); os.chmod(path, 0o700) if not os.path.islink(path) else None
            func(path)
        except OSError as e: errs.append(f'{path}: {e}')
    shutil.rmtree(p, onerror=fix)
    return errs[0] if errs else ''


def build_dirs():
    return [d for d in GAMES.glob('*/*_build') if d.is_dir() and not d.is_symlink()]


def dir_size(d):
    n = 0
    for root, _, files in os.walk(d):
        for f in files:
            try: n += os.lstat(os.path.join(root, f)).st_size
            except OSError: pass
    return n


def clean_work(keep_paths=()):
    """Delete the porter's working folders (extracted game, shader work, the copy the APK is built from). The finished APK and data are in the output folder; these only
    take space, and only this app can delete them (they sit in its private storage). Returns the bytes freed."""
    import shutil
    freed = 0
    for d in build_dirs():
        if any(str(k).startswith(str(d) + os.sep) for k in keep_paths if k): continue   # the output sits inside it: leave it alone
        freed += dir_size(d); rm_tree(d)
    return freed


PROTECTED = None


def remove_paths(paths):
    """Delete files and folders chosen in the file manager. Only under the private storage (/root), the internal storage (/sdcard) and SD cards (/storage/<id>); never the
    storage roots, the porter, the tools or the app's own settings. A symlink is removed itself, never what it points to. Returns [(path, 'ok' | error)]."""
    import shutil
    global PROTECTED
    if PROTECTED is None:
        PROTECTED = {Path(x) for x in ('/', '/root', '/sdcard', '/storage', '/root/.config', '/root/games', '/root/prebuilt', '/root/.config/nx2android', '/nx2a')} | {REPO, REPO.parent}
    out = []
    for raw in paths:
        p = Path(os.path.abspath(str(raw)))   # tidies .. and double slashes, does not follow a final symlink
        s = str(p)
        if not s.startswith(('/root/', '/sdcard/', '/storage/')) or p in PROTECTED or (s.startswith('/storage/') and (len(p.parts) < 4 or s.startswith(('/storage/emulated/0/Android', '/storage/self')) and len(p.parts) < 5)) or s in ('/storage/emulated/0', '/storage/emulated/legacy'):
            out.append((s, 'not allowed')); continue
        if any(p == q or q in p.parents for q in (REPO, Path('/root/prebuilt'), Path('/root/.config/nx2android'))):
            out.append((s, 'part of the app: use Update / repair instead')); continue
        try:
            if p.is_symlink() or p.is_file(): p.unlink()
            elif p.is_dir():
                err = rm_tree(p)
                if err: out.append((s, err)); continue
            else: out.append((s, 'not found')); continue
            out.append((s, 'ok'))
        except OSError as e: out.append((s, str(e)))
    return out


def stage_folder(folder):
    """The porter builds next to the game folder and /sdcard cannot run programs: link the game files into internal storage."""
    p = Path(folder)
    if not str(p).startswith(('/sdcard', '/storage')): return str(p)
    slug = re.sub(r'[^A-Za-z0-9._-]+', '_', p.name) or 'game'
    d = GAMES / slug; d.mkdir(parents=True, exist_ok=True)
    for old in d.iterdir():   # links left by an earlier port of this folder: the game files may have been moved or deleted since, and a dangling link crashes the porter
        if old.is_symlink() and old.suffix.lower() in GAME_EXT: old.unlink()
    for f in p.iterdir():
        if f.suffix.lower() in GAME_EXT:
            t = d / f.name
            if t.is_symlink() or t.exists(): t.unlink()
            t.symlink_to(f)
    return str(d)


def stage_driver(path):
    """A custom Vulkan driver (Turnip and the like) for --vulkan-driver: a .so, or a .zip that holds one. Copied to internal storage; checked to be an arm64 ELF library."""
    import shutil, zipfile
    p = Path(path.strip()).expanduser()
    if not p.is_file(): raise ValueError(f'driver not found: {p}')
    d = GAMES / '_drivers'; d.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == '.zip':
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if n.lower().endswith('.so') and not n.endswith('/')]
            if not names: raise ValueError(f'{p.name}: no .so library inside the zip')
            if len(names) > 1: raise ValueError(f'{p.name}: more than one .so inside ({", ".join(Path(n).name for n in names[:4])}); extract the driver and pick the .so')
            out = d / Path(names[0]).name
            with z.open(names[0]) as r, open(out, 'wb') as f: shutil.copyfileobj(r, f)
    elif p.suffix.lower() == '.so':
        out = d / p.name; shutil.copyfile(p, out)
    else: raise ValueError('the driver must be a .so file (or a .zip that holds one)')
    h = out.read_bytes()[:20]
    if h[:4] != b'\x7fELF' or h[4] != 2 or int.from_bytes(h[18:20], 'little') != 183:
        out.unlink(); raise ValueError(f'{out.name} is not an arm64 (64-bit ARM) library')
    return str(out)


def check_game_folder(folder):
    folder = (folder or '').strip()
    if not folder: raise ValueError('Choose the game folder first (Port tab, Browse).')
    p = Path(folder)
    if not p.is_dir():
        hint = ' The SD card needs the newest APK (Releases, latest) so the app can see it.' if folder.startswith('/storage/') and not folder.startswith('/storage/emulated') else ''
        raise ValueError(f'Folder not found: {folder}.{hint}')
    if not any(f.suffix.lower() in GAME_EXT for f in p.iterdir() if f.is_file() or f.is_symlink()):
        raise ValueError(f'No game files (.nsp .xci .nsz .xcz) directly inside {folder}. Pick the folder that holds them, not a folder above it.')
    return folder


def build_port_args(o):
    o = dict(o, folder=check_game_folder(o.get('folder')))
    a = ['port', stage_folder(o['folder']), '--progress', 'json']
    out = o.get('out') or ('' if cfg().get('out') else DEFAULT_OUT)
    if out: a += ['-o', out]
    if o.get('app_name'): a += ['--app-name', o['app_name']]
    if o.get('language'): a += ['-l', o['language']]
    if o.get('package'): a += ['--package', o['package']]
    for flag in ('touch', 'fps60', 'experimental', 'install', 'replace_signer'):
        if o.get(flag): a.append('--' + flag.replace('_', '-'))
    if o.get('jobs'): a += ['--jobs', str(max(1, int(o['jobs'])))]
    if (o.get('vulkan_driver') or '').strip(): a += ['--vulkan-driver', stage_driver(o['vulkan_driver'])]
    return a


def last_build_log():
    """The newest build log of a port that just ran: what failed is in there, the job output only says which stage."""
    best = None
    for pat in (str(GAMES / '*' / '*_build' / 'logs' / '*.log'), '/sdcard/Switch/**/*_build/logs/*.log'):
        for f in glob.glob(pat, recursive=True):
            try: m = os.path.getmtime(f)
            except OSError: continue
            if not best or m > best[0]: best = (m, f)
    if not best or time.time() - best[0] > 900: return {}
    lines = Path(best[1]).read_text(errors='replace').splitlines()[-60:]
    return {'file': best[1], 'tail': '\n'.join(l[:300] for l in lines)}


def ver(d):
    try: return int(json.loads((d / 'payload.json').read_text())['version'])
    except Exception: return -1


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, body, ctype='application/json', code=200, headers=None):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header('Content-Type', ctype + '; charset=utf-8'); self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)

    def j(self, obj, code=200): self.send(json.dumps(obj), code=code)

    def gate(self, path, q, post=False):
        if self.headers.get('Host', '') not in HOSTS: self.send('bad host', 'text/plain', 403); return False
        origin = self.headers.get('Origin')
        if post and origin and urlparse(origin).netloc not in HOSTS: self.send('bad origin', 'text/plain', 403); return False
        if not TOKEN: return True
        try:
            ck = http.cookies.SimpleCookie(self.headers.get('Cookie', ''))
            if 'nx2a' in ck and hmac.compare_digest(ck['nx2a'].value, TOKEN): return True
            if path == '/' and hmac.compare_digest(q.get('t', [''])[0], TOKEN): self.set_cookie = True; return True
        except (TypeError, http.cookies.CookieError): pass
        self.send('forbidden', 'text/plain', 403); return False

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        self.set_cookie = False
        if not self.gate(u.path, q): return
        if u.path == '/':
            return self.send((HERE / 'index.html').read_bytes(), 'text/html', headers={'Set-Cookie': f'nx2a={TOKEN}; Path=/; HttpOnly; SameSite=Strict'} if self.set_cookie else None)
        if u.path == '/api/status':
            try: pat = STATUS.read_text()[-400:]
            except OSError: pat = ''
            return self.j({'version': VERSION, 'ota': ver(OTA), 'update_ready': ver(OTA) > int(VERSION or 0), 'patches': pat, 'porter': porter_sync.state(), 'porter_commit': porter_sync.commit(), 'porter_mode': porter_sync.mode(), 'porter_good': str(porter_sync._payload().get('porter_good') or '')[:9], 'update_msg': UPD['msg']})
        if u.path == '/api/doctor':
            out, err, code = porter('doctor', '--json')
            try: return self.j({'checks': json.loads(out)})
            except ValueError: return self.j({'error': (err or out)[-600:]})
        if u.path == '/api/config': return self.j(cfg())
        if u.path == '/api/library':
            start_cover_refresh()
            return self.j(library_read())
        if u.path == '/api/library/covers/status':
            return self.j(dict(COVER_JOB))
        if u.path == '/api/cover':
            game = next((g for g in library_read()['games'] if g.get('id') == q.get('id', [''])[0]), None)
            path = Path(game.get('cover_path', '')) if game else Path('/')
            try:
                resolved = path.resolve(strict=True)
                cache_root = COVER_CACHE.resolve()
                in_cache = os.path.commonpath((str(cache_root), str(resolved))) == str(cache_root)
                in_shared = str(resolved).startswith(('/sdcard/', '/storage/'))
                if not (in_cache or in_shared) or not resolved.is_file() or resolved.stat().st_size > 8 * 1024 * 1024:
                    raise OSError('invalid cover')
                return self.send(resolved.read_bytes(), mimetypes.guess_type(str(resolved))[0] or 'application/octet-stream')
            except (OSError, ValueError):
                return self.send(b'', 'application/octet-stream', 404)
        if u.path == '/api/lastlog': return self.j(last_build_log())
        if u.path == '/api/work': return self.j({'bytes': sum(dir_size(d) for d in build_dirs()), 'dirs': [d.name for d in build_dirs()]})
        if u.path == '/api/summary': return self.j({'running': not JOB['done'], 'kind': JOB['kind'], 'stage': JOB['stage'], 'frac': JOB['frac'], 'code': JOB['code'], 'seq': JOB['seq']})
        if u.path == '/api/job':
            since = int(q.get('since', ['0'])[0])
            return self.j({'lines': JOB['lines'][since:], 'next': len(JOB['lines']), 'done': JOB['done'], 'code': JOB['code']})
        if u.path == '/api/ls':
            p = Path(norm_path(q.get('path', ['/sdcard'])[0]))
            try:
                items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                return self.j({'path': str(p), 'parent': str(p.parent), 'items': [{'n': x.name, 'd': x.is_dir(), 's': (x.lstat().st_size if x.is_file() and not x.is_symlink() else None), 'l': x.is_symlink()} for x in items if not x.name.startswith('.') or q.get('hidden')][:1000]})
            except OSError as e: return self.j({'path': str(p), 'parent': str(p.parent), 'items': [], 'error': str(e)})
        if u.path == '/api/devices':
            out, err, _ = porter('devices', '--json')
            try: devs = json.loads(out); return self.j({'devices': devs, 'ready': any(d.get('state') == 'device' for d in devs), 'paired': bool(adb_auto.load().get('paired')), 'note': adb_auto.load().get('last', '')})
            except ValueError: return self.j({'devices': [], 'error': (err or out)[-300:]})
        self.send('not found', 'text/plain', 404)

    def do_POST(self):
        u = urlparse(self.path); q = {}
        if not self.gate(u.path, q, post=True): return
        n = int(self.headers.get('Content-Length') or 0)
        try: o = json.loads(self.rfile.read(n) or b'{}')
        except ValueError: return self.j({'error': 'bad json'}, 400)
        for k in ('data', 'apk', 'folder', 'vulkan_driver', 'out', 'path'):
            if k in o: o[k] = norm_path(o[k])
        if isinstance(o.get('paths'), list): o['paths'] = [norm_path(x) for x in o['paths']]
        if u.path == '/api/config':
            if o.get('key') not in ('keys', 'out'): return self.j({'ok': False, 'msg': 'unknown setting'})
            out, err, c = porter('config', o['key'], o['value']); return self.j({'ok': c == 0, 'msg': (err or out)[-300:]})
        if u.path == '/api/library/settings':
            settings = o.get('settings')
            if not isinstance(settings, dict): return self.j({'ok': False, 'error': 'settings must be an object'}, 400)
            allowed = {'resolution', 'graphics', 'fps', 'controller', 'vulkan_driver', 'touch', 'fps60', 'log_runtime', 'log_slowframe', 'log_nvn', 'log_watchdog', 'log_fs'}
            clean = {k: v for k, v in settings.items() if k in allowed and isinstance(v, (str, int, bool))}
            game = library_update(str(o.get('id', '')), lambda g: g.update(settings=clean, updated_at=int(time.time())))
            return self.j({'ok': game is not None, 'game': game})
        if u.path == '/api/library/covers/refresh':
            return self.j({'started': start_cover_refresh()})
        if u.path == '/api/library/cover':
            path = Path(norm_path(str(o.get('path', ''))))
            try:
                resolved = path.resolve(strict=True)
                if not (str(resolved).startswith('/sdcard/') or str(resolved).startswith('/storage/')) or not resolved.is_file() or resolved.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
                    raise ValueError('Choose a PNG, JPG or WebP image in shared storage.')
                if resolved.stat().st_size > 8 * 1024 * 1024: raise ValueError('Cover image must be 8 MB or smaller.')
                game = library_update(str(o.get('id', '')), lambda g: g.update(cover_path=str(resolved), updated_at=int(time.time())))
                return self.j({'ok': game is not None, 'error': None if game else 'Game not found'})
            except (OSError, ValueError) as e:
                return self.j({'ok': False, 'error': str(e)})
        if u.path == '/api/library/remove':
            catalog = library_read()
            before = len(catalog['games'])
            catalog['games'] = [g for g in catalog['games'] if g.get('id') != str(o.get('id', ''))]
            library_write(catalog)
            return self.j({'ok': len(catalog['games']) != before, 'files_deleted': False})
        if u.path == '/api/tools': return self.j({'started': start_job([sys.executable, str(HERE.parent / 'fast_tools.py')], 'tools')})
        if u.path == '/api/inspect':
            out, err, c = porter('inspect', stage_folder(o['folder']), '--json')
            try: return self.j(json.loads(out))
            except ValueError: return self.j({'error': (err or out)[-600:]})
        if u.path == '/api/port':
            try: args = build_port_args(o)
            except (ValueError, OSError, Exception) as e: return self.j({'started': False, 'error': str(e)})
            if (not JOB['done']) or JOB.get('starting'): return self.j({'started': False, 'error': 'A job is already running.'})
            JOB['keep'] = bool(o.get('keep_work')); JOB['fps60'] = bool(o.get('fps60'))
            JOB['source_folder'] = norm_path(str(o.get('folder') or ''))
            JOB['port_options'] = {k: o.get(k) for k in ('touch', 'fps60', 'vulkan_driver')}
            return self.j({'started': start_job([sys.executable, '-m', 'porter', *args], 'port')})
        if u.path == '/api/runtime/install':
            game_id = str(o.get('id') or '')
            if not re.fullmatch(r'[0-9a-f]{20}', game_id): return self.j({'started': False, 'error': 'Invalid game ID.'}, 400)
            game = next((g for g in library_read()['games'] if g.get('id') == game_id), None)
            if not game: return self.j({'started': False, 'error': 'Game not found in the library.'}, 404)
            data = Path(game.get('data_path') or '')
            if not game.get('runtime_ready') or not (data / 'libdmhost.so').is_file():
                return self.j({'started': False, 'error': game.get('runtime_error') or 'This game has no extracted NGR runtime. Recompile it with the latest NGR build.'})
            if (not data.is_dir()) or not (data / 'nx2a-data.json').is_file():
                return self.j({'started': False, 'error': 'The completed game data pack is missing. Recompile/update this game.'})
            argv = [sys.executable, str(HERE.parent / 'runtime_install.py'), '--data', str(data), '--game-id', game_id, '--package', 'unknown.none.nx2android']
            JOB['runtime_game_id'] = game_id
            started = start_job(argv, 'runtime_install')
            return self.j({'started': started, 'error': None if started else 'Another job is already running.'})
        if u.path == '/api/install':   # the game data (and the APK, if it is not on the phone yet) over adb: the one way Android lets this app put files into Android/data
            if not adb_ready(): return self.j({'started': False, 'error': 'No adb device is connected. Open the Device tab: pair, connect, List devices, then try again.'})
            d = Path(o.get('data') or '')
            if not d.is_dir(): return self.j({'started': False, 'error': f'The data folder does not exist: {d}. Port the game first, or fix the path (it must be a folder like /sdcard/Switch/Ports/Game-data).'})
            if not (d / 'nx2a-data.json').is_file(): return self.j({'started': False, 'error': f'{d} is not a finished data pack (nx2a-data.json is missing). Choose the folder that ends in -data next to the APK.'})
            a = ['install', o['data']] + (['--apk', o['apk']] if o.get('apk') else []) + ['--progress', 'json'] + (['--replace-signer'] if o.get('replace_signer') else [])
            return self.j({'started': start_job([sys.executable, '-m', 'porter', *a], 'install')})
        if u.path == '/api/adb':   # wireless debugging to this same phone (optional): pair once, the app reconnects by itself afterwards (adb_auto.py)
            op = o.get('op')
            if op == 'auto':
                ok, msg = adb_auto.auto(ENV); return self.j({'out': msg, 'ok': ok})
            if op == 'forget':
                adb_auto.save(paired=False, connect='')
                try: subprocess.run(['adb', 'disconnect'], capture_output=True, text=True, timeout=15, env=ENV)
                except (OSError, subprocess.TimeoutExpired): pass
                return self.j({'out': 'Forgotten: the app will not reconnect by itself until you pair again.'})
            if op not in ('pair', 'connect', 'disconnect'): return self.j({'out': 'bad operation'})
            cmd = ['adb', op, str(o['host'])] + ([str(o['code'])] if op == 'pair' and o.get('code') else [])
            try: r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=ENV)
            except (OSError, subprocess.TimeoutExpired) as e: return self.j({'out': str(e)})
            out = (r.stdout + r.stderr).strip(); low = out.lower()
            if op == 'pair' and 'successfully paired' in low: adb_auto.save(paired=True)
            if op == 'connect' and 'connected to' in low and 'failed' not in low: adb_auto.save(connect=str(o['host']), paired=True)
            return self.j({'out': out})
        if u.path == '/api/cancel':
            p = JOB['p']
            if p and p.poll() is None: os.killpg(p.pid, signal.SIGKILL)
            return self.j({'ok': True})
        if u.path == '/api/checkupdate':
            got = check_update(); return self.j({'ready': got or ver(OTA) > int(VERSION or 0), 'msg': UPD['msg']})
        if u.path == '/api/expfile':
            t = Path('/sdcard/Switch/nx2android-proot-experiments.txt')
            try: return self.j({'path': str(t), 'age': int(time.time() - t.stat().st_mtime), 'text': t.read_text(errors='replace')})
            except OSError: return self.j({})
        if u.path == '/api/tracefile':
            t = Path('/sdcard/Switch/nx2android-proot-trace.txt')
            try: return self.j({'path': str(t), 'age': int(time.time() - t.stat().st_mtime), 'tail': '\n'.join(t.read_text(errors='replace').splitlines()[-90:])})
            except OSError: return self.j({})
        if u.path == '/api/dotnet':
            rep = dotnet_probe.full_report()
            try: Path('/sdcard/Switch').mkdir(parents=True, exist_ok=True); Path('/sdcard/Switch/nx2android-dotnet-report.txt').write_text('\n'.join(rep))
            except OSError: pass
            return self.j({'report': rep, 'saved': dotnet_probe.saved()})
        if u.path == '/api/rm':
            if (JOB['p'] and JOB['p'].poll() is None) or JOB.get('starting'): return self.j({'error': 'a job is running: wait for it to finish'})
            return self.j({'results': remove_paths(o.get('paths') or [])})
        if u.path == '/api/clean':
            if (JOB['p'] and JOB['p'].poll() is None) or JOB.get('starting'): return self.j({'error': 'a job is running'})
            return self.j({'freed': clean_work()})
        if u.path == '/api/prebuilt':
            need_porter(); rep = prebuilt.install()
            try: Path('/sdcard/Switch').mkdir(parents=True, exist_ok=True); Path('/sdcard/Switch/nx2android-prebuilt-report.txt').write_text('\n'.join(rep))
            except OSError: pass
            return self.j({'report': rep, 'state': prebuilt.state()})
        if u.path == '/api/porter_mode':   # off (default): the porter follows upstream's newest commit; on: the version known to work (payload.json porter_good). A switch for one port, never a change for everyone
            porter_sync.set_mode('good' if o.get('mode') == 'good' else 'newest')
            ok, msg = porter_sync.sync(); return self.j({'ok': ok, 'msg': msg, 'mode': porter_sync.mode(), 'porter': porter_sync.state(), 'porter_commit': porter_sync.commit()})
        if u.path == '/api/repair':
            ok, msg = porter_sync.sync(force=True); return self.j({'ok': ok, 'msg': msg, 'porter': porter_sync.state()})
        if u.path == '/api/restart':
            threading.Timer(0.5, lambda: os._exit(75)).start(); return self.j({'ok': True})
        self.send('not found', 'text/plain', 404)


if __name__ == '__main__':
    # Do not make GUI availability depend on a network download or porter patch
    # validation. The launcher has already attempted the pinned checkout; the
    # GUI must come up even when that checkout needs repair. Port operations
    # call need_porter() and report a precise error in the job log.
    print('NGR GUI boot: deferring porter validation until a port operation', flush=True)
    threading.Thread(target=auto_update, daemon=True).start()
    threading.Thread(target=auto_porter, daemon=True).start()
    threading.Thread(target=adb_auto.loop, args=(ENV, lambda: not JOB['done']), daemon=True).start()
    print(f'nx2android GUI {VERSION} on 127.0.0.1:{PORT} (porter: {REPO})', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
