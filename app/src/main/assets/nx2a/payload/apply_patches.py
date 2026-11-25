#!/usr/bin/env python3
"""Patches a nx2android checkout for an aarch64 phone. Idempotent; each patch reports ok / already / FAILED (upstream text changed)."""
import os, sys
from pathlib import Path

PATCH_ONLY = {x for x in os.environ.get('NX2A_PATCH_ONLY', '').split(';') if x}
repo = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
failed = 0


def patch(name, rel, marker, edits):
    global failed
    if PATCH_ONLY and name not in PATCH_ONLY: return
    f = repo / rel
    try: s = f.read_text()
    except OSError as e: print(f'{name}: FAILED (cannot read {rel}: {e})'); failed += 1; return
    if marker in s: print(f'{name}: already'); return
    # Older NGR patches sometimes forgot to include their marker in the replacement.
    # Verify every replacement before treating a marker-less patched tree as a conflict.
    if edits and all(new in s for _, new in edits): print(f'{name}: already (replacement verified)'); return
    for old, new in edits:
        if s.count(old) != 1: print(f'{name}: FAILED (upstream changed: {old[:50]!r})'); failed += 1; return
        s = s.replace(old, new)
    f.write_text(s); print(f'{name}: ok')



# 1d. NGR runtime packaging also runs against the pinned older porter. Newer
# upstream revisions define ui_font_assets(); older pinned revisions do not.
# Keep both supported: backport the helper only when upstream has not added it.
_pipeline_file = repo / 'porter/pipeline.py'
try: _pipeline_source = _pipeline_file.read_text()
except OSError: _pipeline_source = ''
if not _pipeline_file.exists():
    print('NGR UI font assets: skipped (porter source not staged in this patch test)')
elif 'def ui_font_assets()' in _pipeline_source:
    print('NGR UI font assets: upstream implementation present')
else:
    # Required dependency of NGR runtime packaging: never skip it in a
    # selective patch run, or the pinned porter fails at the data-pack stage.
    _saved_patch_only = PATCH_ONLY
    PATCH_ONLY = set()
    try:
        patch('NGR UI font assets', 'porter/pipeline.py', 'NX2A_UI_FONT_ASSETS', [
            ("""from porter.paths import DM, NXNATIVE
""", """from porter.paths import DM, NXNATIVE

# NX2A_UI_FONT_ASSETS: compatibility with the pre-font upstream porter.
UI_FONT = DM / 'third_party/fusion-pixel-font/fusion-pixel-12px-proportional-zh_tw.nxpf'
def ui_font_assets():
    d = UI_FONT.parent
    if not UI_FONT.is_file():
        return {}
    return {'font/ui.bin': UI_FONT, **{f'font/{f.relative_to(d).as_posix()}': f for f in sorted(p for p in d.rglob('*.txt'))}}
"""),
        ])
    finally:
        PATCH_ONLY = _saved_patch_only

# 1. the NDK's own tools are x86-64: use the system clang/glslc with the NDK sysroot, the system clang's headers and the NDK's runtime libraries
patch('arm host build', 'nxnative/dm/android/build.py', 'NX2A_ARM_HOST', [
("""host = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64' if sys.platform.startswith('linux') else 'darwin-x86_64'
bin_ = Path(a.ndk) / 'toolchains/llvm/prebuilt' / host / 'bin'
CC = str(bin_ / ('clang.exe' if os.name == 'nt' else 'clang'))
""", """import platform as _pf, shutil as _sh, stat as _st0
NX2A_ARM_HOST = sys.platform.startswith('linux') and _pf.machine().lower() in ('aarch64', 'arm64')
host = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64' if sys.platform.startswith('linux') else 'darwin-x86_64'
bin_ = Path(a.ndk) / 'toolchains/llvm/prebuilt' / host / 'bin'
CC = str(bin_ / ('clang.exe' if os.name == 'nt' else 'clang'))
if NX2A_ARM_HOST:
    _sysroot = next(Path(a.ndk).glob('toolchains/llvm/prebuilt/*/sysroot'), None)
    _ndkres = next(iter(sorted(Path(a.ndk).glob('toolchains/llvm/prebuilt/*/lib/clang/*'))), None)
    _sys_clang = _sh.which('clang')
    if not (_sysroot and _ndkres and _sys_clang): sys.exit('aarch64 host: need the NDK download (its sysroot) and the system clang (apt install clang lld)')
    _sysres = Path(subprocess.check_output([_sys_clang, '-print-resource-dir'], text=True).strip())
    _wd = Path(a.out if a.out else DM / 'android/out'); _wd.mkdir(parents=True, exist_ok=True)
    _rd = _wd / 'resdir'; _rd.mkdir(exist_ok=True)
    for _n, _t in (('include', _sysres / 'include'), ('lib', _ndkres / 'lib')):
        _l = _rd / _n
        if _l.is_symlink() or _l.exists(): _l.unlink()
        _l.symlink_to(_t)
    _wrap = _wd / 'cc-arm'
    _wrap.write_text(f'#!/bin/sh\\nexec {_sys_clang} --sysroot={_sysroot} -resource-dir={_rd} -rtlib=compiler-rt "$@"\\n')
    _wrap.chmod(_wrap.stat().st_mode | _st0.S_IXUSR)
    CC = str(_wrap)
"""),
("GLSLC = Path(a.ndk) / 'shader-tools' / host / ('glslc.exe' if os.name == 'nt' else 'glslc')\n",
 "GLSLC = Path(a.ndk) / 'shader-tools' / host / ('glslc.exe' if os.name == 'nt' else 'glslc')\nif NX2A_ARM_HOST: GLSLC = Path(_sh.which('glslc') or sys.exit('aarch64 host: apt install glslc'))\n"),
("subprocess.run([str(bin_ / ('llvm-strip.exe' if os.name == 'nt' else 'llvm-strip')), '--strip-unneeded', str(out / 'libdmhost.so')], check=True)",
 "subprocess.run([str(_sh.which('llvm-strip') or _sh.which('llvm-strip-18') or 'strip') if NX2A_ARM_HOST else str(bin_ / ('llvm-strip.exe' if os.name == 'nt' else 'llvm-strip')), '--strip-unneeded', str(out / 'libdmhost.so')], check=True)"),
])

# 1a. Keep the Android host's constructor relocations in standard DT_RELA form.
# NDK Clang injects Android RELR packing for API 30+ targets by default. The
# affected game host has a large init_array; a malformed packed table can leave
# constructor pointers unrelocated before bionic calls them.
patch('standard Android host relocations', 'nxnative/dm/android/build.py', 'NX2A_DISABLE_RELR', [
("""LDFLAGS = [TARGET, '-fuse-ld=lld', '-Wl,--error-limit=0', '-Wl,-z,max-page-size=16384', '-Wl,--build-id', '-Wl,-z,nostart-stop-gc']""",
 """LDFLAGS = [TARGET, '-fuse-ld=lld', '-Wl,--pack-dyn-relocs=none', '-Wl,--error-limit=0', '-Wl,-z,max-page-size=16384', '-Wl,--build-id', '-Wl,-z,nostart-stop-gc']  # NX2A_DISABLE_RELR"""),
])

# 1b. the same wrapper for C++ (the custom-driver loader libadrenotools is C++): the trimmed NDK has no clang++, use the system one with the NDK sysroot
patch('arm host c++', 'nxnative/dm/android/build.py', 'cxx-arm', [
("""    CXX = str(bin_ / ('clang++.exe' if os.name == 'nt' else 'clang++'))
""", """    CXX = str(bin_ / ('clang++.exe' if os.name == 'nt' else 'clang++'))
    if NX2A_ARM_HOST:
        _sys_cxx = _sh.which('clang++') or (_sys_clang + '++')
        _wrx = _wd / 'cxx-arm'
        _wrx.write_text(f'#!/bin/sh\\nexec {_sys_cxx} --sysroot={_sysroot} -resource-dir={_rd} -rtlib=compiler-rt "$@"\\n')
        _wrx.chmod(_wrx.stat().st_mode | _st0.S_IXUSR)
        CXX = str(_wrx)
"""),
])

# 1c. hashlib is used by the NGR stable game-ID patch; import it inside inputs as well as at module scope
# so the stage remains safe when the porter is loaded through an alternate module loader.
patch('NGR hashlib local import', 'porter/pipeline.py', 'NX2A_HASHLIB_LOCAL', [
("""    def inputs(self):
        o = self.o
""", """    def inputs(self):
        import hashlib  # NX2A_HASHLIB_LOCAL: keep the NGR game-ID hash available in this stage
        o = self.o
"""),
])

# 2. the single NGR application owns every game's data directory; per-game Android packages are not created in NGR mode
patch('NGR package and stable game ID', 'porter/pipeline.py', 'NX2A_NGR_PACKAGE', [
('self.package = o.package or ap.package',
 """self.package = 'unknown.none.nx2android' if os.environ.get('NX2A_NGR') == '1' else (o.package or 'unknownnone.nx2android.' + (re.sub(r'^[^a-z]+|[^a-z0-9]', '', ap.name.lower()) or 'game'))  # NX2A_NGR_PACKAGE"""),
('        self.g, self.ap = g, ap\n',
 """        self.g, self.ap = g, ap
        if os.environ.get('NX2A_NGR') == '1':
            self.ngr_game_id = hashlib.sha256(('switch:' + self.g.id.upper()).encode('utf-8')).hexdigest()[:20]
            os.environ['NX2A_GAME_ID'] = self.ngr_game_id
            self.env['NX2A_GAME_ID'] = self.ngr_game_id
"""),
])
# 3. prebuilt .NET tools (CI-built, a runtime that starts under proot): used when the app has installed and tested them (NX2A_PREBUILT)
patch('prebuilt extractor', 'nxnative/scripts/build_ipa_from_nsp.py', 'NX2A_PREBUILT', [
("""    nx = work / 'tools/nx_extract' / exe
""", """    nx = work / 'tools/nx_extract' / exe
    if os.environ.get('NX2A_PREBUILT') and (Path(os.environ['NX2A_PREBUILT']) / 'nx_extract' / 'nx_extract').is_file():   # NX2A_PREBUILT: the app's prebuilt tools
        rmtree(nx.parent); shutil.copytree(Path(os.environ['NX2A_PREBUILT']) / 'nx_extract', nx.parent); return nx
"""),
])
patch('prebuilt translator', 'porter/pipeline.py', 'NX2A_PREBUILT', [
("""        src = DM / 'gfx/tools/dmsh_xlate'; ryu = DM / 'third_party/ryujinx'
""", """        if os.environ.get('NX2A_PREBUILT') and (Path(os.environ['NX2A_PREBUILT']) / 'dmsh_xlate' / 'dmsh_xlate').is_file():   # NX2A_PREBUILT: the app's prebuilt tools
            return Path(os.environ['NX2A_PREBUILT']) / 'dmsh_xlate' / 'dmsh_xlate.dll', 'prebuilt'
        src = DM / 'gfx/tools/dmsh_xlate'; ryu = DM / 'third_party/ryujinx'
"""),
])
patch('prebuilt dotnet check', 'porter/toolchain.py', 'NX2A_PREBUILT', [
("""    cfg = cfg if cfg is not None else config.load()
    if cfg.get('dotnet') and Path(cfg['dotnet']).is_file(): return Path(cfg['dotnet'])
""", """    cfg = cfg if cfg is not None else config.load()
    if os.environ.get('NX2A_PREBUILT_DOTNET') and Path(os.environ['NX2A_PREBUILT_DOTNET']).is_file(): return Path(os.environ['NX2A_PREBUILT_DOTNET'])   # NX2A_PREBUILT
    if cfg.get('dotnet') and Path(cfg['dotnet']).is_file(): return Path(cfg['dotnet'])
"""),
("""def dotnet_sdks(dotnet):   # {'10.0.402': '/usr/local/share/dotnet/sdk', ...}
""", """def dotnet_sdks(dotnet):   # {'10.0.402': '/usr/local/share/dotnet/sdk', ...}
    if os.environ.get('NX2A_PREBUILT_DOTNET') and str(dotnet) == os.environ['NX2A_PREBUILT_DOTNET']: return {'10.0.0': '/nx2a-prebuilt/sdk'}   # stands in for the SDK: the tools are prebuilt
"""),
])

# 5. run-time GLSLC shaders (Fire Emblem: Three Houses): upstream captures them by booting the game in the Mac host; here the Android host runs as a program on the connected phone (adb), as it already does for Oodle
patch('device glslc capture', 'porter/pipeline.py', 'NX2A_GLSLC', [
("""        for k in ('glslc_capture', 'ue_legacy') + """, """        self.glslc_why = src['glslc_capture'][1] if src['glslc_capture'][0] else ''   # NX2A_GLSLC
        if self.glslc_why:
            if not self.tools.get('adb'):
                raise BuildError(f"{self.app_name} compiles some shaders at run time with its own GLSLC ({self.glslc_why}): the port captures them by booting the game on the Android device, so it needs adb and the device even without installing. {NO_ADB}; then connect the device (wireless debugging) and port again")
            try: Adb(self.tools['adb'], self.o.device or self.cfg.get('device'), log=say).pick()
            except (AdbError, KeyError) as e: raise BuildError(f"{self.app_name} compiles some shaders at run time with its own GLSLC ({self.glslc_why}): the port captures them by booting the game on the Android device, so connect it (adb) and port again ({e})") from e
        for k in ('ue_legacy',) + """),
("""            if getattr(self, "ue_why", ""): self.device_ue()""", """            if getattr(self, 'glslc_why', ''): self.device_glslc()   # NX2A_GLSLC: the run-time shaders, captured on the device before the split reads them
            if getattr(self, "ue_why", ""): self.device_ue()"""),
("""    # ---- Unreal Engine shader code archives decoded with the game's own Oodle on the device""", r"""    GDEV = '/data/local/tmp/nx2a-glslc'
    def device_glslc(self):
        # the shaders the game compiles at run time with its own GLSLC: the Android host, built as a program without graphics, boots the game on the connected phone with DM_GLSLC_CAPTURE
        # (dm/host/hle_glslc.c) and the outputs come back to <version dir>/glslc_capture, where the split reads them. First with the big RomFS files as empty stand-ins of the right size (the capture
        # happens in the first second of boot), then, if that did not capture everything, with the whole RomFS
        import shlex, time
        want = nsp.glslc_wanted(self.g)
        have = lambda d: (nsp.glslc_done(d / 'glslc_capture') >= want) if want else bool(nsp.glslc_done(d / 'glslc_capture'))
        todo = [v for v in self.versions if not have(self.dirs[v])]
        PROG.add(1); PROG.stage('GLSLC capture')
        if not todo:
            say('reusing the captured run-time shaders'); PROG.end('reused'); return
        if todo != [self.pkg_ver]:
            PROG.end(ok=False)
            raise BuildError(f"the run-time shader capture runs the packed version {self.pkg_ver}'s code; {', '.join(v for v in todo if v != self.pkg_ver)} needs a capture of its own")
        d, G, SECS = self.dirs[self.pkg_ver], self.GDEV, 60
        rom, cap, log = d / 'RomFS', d / 'glslc_capture.partial', self.logs / 'glslc_capture.log'
        adb = Adb(self.tools['adb'], self.o.device or self.cfg.get('device'), log=say); adb.pick()
        host = self.aw / 'host-glslc'
        PROG.set(step='building the host as a tool (no graphics)')
        nsp.run([PY, DM / 'android/build.py', '--game', self.g.id, '--ndk', self.tools['ndk'], '--out', host, '--exe', '--gfx', 'null', '--release', '--jobs', str(self.o.jobs)],
                self.logs / 'android_glslc_host.log', env=self.env)
        big = sorted((p.relative_to(rom).as_posix(), p.stat().st_size) for p in rom.rglob('*') if p.is_file() and p.stat().st_size > (64 << 20))
        rounds = [False, True] if 0 < len(big) <= 200 else [True]
        got, tail = set(), ''
        try:
            for full in rounds:
                PROG.set(step='sending the game to the phone' + ('' if full else ' (big files as empty stand-ins)'))
                adb.shell(f'pkill -f {G}/dmhost; rm -rf {G}/cap {G}/save {G}/temp {G}/mods {G}/dmhost; mkdir -p {G}/mods {G}/RomFS {G}/cap {G}/save {G}/temp', check=False)
                adb.push_file(host / 'dmhost', f'{G}/dmhost')
                adb.push_tree(self.patched, f'{G}/mods')
                adb.push_file(self.g.table('shader_map.tsv'), f'{G}/shader_map.tsv')
                if full:
                    if big: adb.shell('; '.join(f'rm -f {shlex.quote(G + "/RomFS/" + r)}' for r, _ in big), check=False)
                    adb.push_tree(rom, f'{G}/RomFS')
                else:
                    adb.push_tree(rom, f'{G}/RomFS', skip=[r for r, _ in big])
                    adb.shell('; '.join(f'mkdir -p {shlex.quote(os.path.dirname(G + "/RomFS/" + r))}; truncate -s {s} {shlex.quote(G + "/RomFS/" + r)}' for r, s in big))
                PROG.set(step='booting the game on the phone until it has compiled its shaders')
                env = f'DM_ROOT={G} DM_ROMFS={G}/RomFS DM_SAVE={G}/save DM_TEMP={G}/temp DM_GLSLC_CAPTURE={G}/cap DM_NVN_SHMAP={G}/shader_map.tsv'
                adb.shell(f'cd {G} && chmod 755 dmhost && ({env} timeout {SECS} ./dmhost mods > run.log 2>&1 &); sleep 1; echo started')
                t0, last, same = time.time(), -1, 0
                while time.time() - t0 < SECS + 10:
                    time.sleep(2)
                    f = (adb.shell(f'echo $(ls {G}/cap 2>/dev/null | wc -l) $(pidof dmhost | wc -w)', check=False) or '').split()
                    n, alive = (int(f[0]), int(f[1])) if len(f) == 2 and all(x.isdigit() for x in f) else (0, 1)
                    PROG.set(done=n, total=len(want) if want else None, unit='shaders')
                    same = same + 1 if n == last else 0; last = n
                    if (want and n >= len(want)) or not alive or (not want and n and same >= 3): time.sleep(2); break
                adb.shell('pkill -f dmhost', check=False)
                tail = adb.shell(f'tail -n 40 {G}/run.log', check=False) or ''
                log.write_text(tail, encoding='utf-8')
                nsp.rmtree(cap); cap.mkdir(parents=True)
                adb.run('pull', f'{G}/cap/.', str(cap), check=False)
                got = nsp.glslc_done(cap)
                if (got >= want) if want else got: break
                if not full: say(f'[RED] the capture with stand-in files got {len(got)} shaders{f" of {len(want)}" if want else ""}: trying again with the whole RomFS on the phone')
        finally:
            adb.shell(f'pkill -f {G}/dmhost; rm -rf {G}', check=False)
        if not (got >= want if want else got):
            PROG.end(ok=False)
            PROG.say(f'---- the game on the phone, last lines ({log}) ----\n' + tail.rstrip('\n'))
            raise BuildError(f'captured only {len(got)} run-time shaders' + (f', the profile needs {len(want)}' if want else '') + f' (host output: {log})')
        nsp.swap_in(cap, d / 'glslc_capture'); PROG.end(f'{len(got)} shaders captured on the device')

    # ---- Unreal Engine shader code archives decoded with the game's own Oodle on the device"""),
])

# 5b. the null graphics backend does not link as a program: gl_android.c (always compiled) calls two Vulkan present functions that only the Vulkan backend defines
patch('null graphics link', 'nxnative/dm/android/gfx_null.c', 'NX2A_NULLSTUB', [
("""int mtl_has_window(void) { return 0; }
""", """int mtl_has_window(void) { return 0; }
// NX2A_NULLSTUB: gl_android.c's EGL present path names these; a null-graphics program never presents
void *vk_image_from_ahb(void *ahb, uint32_t w, uint32_t h) { (void)ahb; (void)w; (void)h; return 0; }
uint64_t vk_present_vkimg(void *im, double period) { (void)im; (void)period; return 0; }
"""),
])

# 5c. a LINKDATA DATA1.bin with no bytes (Three Houses: one of the DLC / patch folders) made the split's mmap fail ("cannot mmap an empty file") and stopped the whole port: skip it, say which
patch('empty linkdata', 'nxnative/dm/gfx/tools/shader_split.py', 'NX2A_EMPTYDATA', [
("""    if os.path.basename(path) != 'DATA1.bin' or not os.path.exists(idx): return None
""", """    if os.path.basename(path) != 'DATA1.bin' or not os.path.exists(idx): return None
    if os.path.getsize(path) == 0:   # NX2A_EMPTYDATA
        print(f'shader split: {rel} is empty (a LINKDATA archive without data): skipped', file=sys.stderr); return None
"""),
])

# 5d. the survey's instruction census is a report-only step (it feeds survey.md, not the provisional profile) that disassembles every module with Python capstone: minutes to an hour on a phone for a big game
patch('survey census skipped', 'nxnative/scripts/build_ipa_from_nsp.py', 'NX2A_CENSUS', [
("""        run([py, repo / 'dm/tools/insn_census.py', m], logs / f'census_{m.name}.log', env=env)
""", """        (logs / f'census_{m.name}.log').write_text('skipped by the nx2android app: a slow, report-only step (NX2A_CENSUS)\\n')   # NX2A_CENSUS
"""),
])

# 5e. stripping the host library only makes it smaller: the Ubuntu strip could not read the library's architecture for Rune Factory (the build then stopped), so a failed strip is no longer an error
patch('strip optional', 'nxnative/dm/android/build.py', 'NX2A_STRIPOPT', [
("""if NX2A_ARM_HOST else str(bin_ / ('llvm-strip.exe' if os.name == 'nt' else 'llvm-strip')), '--strip-unneeded', str(out / 'libdmhost.so')], check=True)""",
 """if NX2A_ARM_HOST else str(bin_ / ('llvm-strip.exe' if os.name == 'nt' else 'llvm-strip')), '--strip-unneeded', str(out / 'libdmhost.so')], check=False)  # NX2A_STRIPOPT"""),
])

# 5f. this app's own Android keys for an experimental port (profiles/<title id>.android.tsv: env rows and the like), added once to the android.tsv the porter writes; a game upstream has an android.tsv for never gets them
patch('profile overlays', 'porter/pipeline.py', 'NX2A_OVERLAY', [
("""        self.use_profile_dir(pdir, first=True)
        g = game.load(tid)
        return g, android_profile.AndroidProfile(g)""", """        _nm = next((l.split('\\t', 1)[1].strip() for l in (d / 'game.tsv').read_text(encoding='utf-8').splitlines() if l.startswith('name\\t')), '') if (d / 'game.tsv').is_file() else ''
        for _ov in (Path('@@DIR@@') / f'{tid.upper()}.android.tsv', Path('@@DIR@@') / (''.join(c for c in _nm.lower() if c.isalnum()) + '.android.tsv')):   # NX2A_OVERLAY: by title id, or by game name (letters and digits only, lower case)
            if _ov.is_file() and '# nx2android overlay ' + _ov.name not in (d / 'android.tsv').read_text(encoding='utf-8'):
                with open(d / 'android.tsv', 'a', encoding='utf-8') as _f: _f.write('\\n# nx2android overlay ' + _ov.name + '\\n' + _ov.read_text(encoding='utf-8'))
        self.use_profile_dir(pdir, first=True)
        g = game.load(tid)
        return g, android_profile.AndroidProfile(g)""".replace('@@DIR@@', str(Path(__file__).resolve().parent / 'profiles'))),
])

# 6. when the on-device host fails, keep its whole output (the grep for two words left nothing to read for exit 139)
patch('device host log', 'porter/pipeline.py', "tail -n 30 job.log'", [
("""echo "exit $?"; grep -a -e DM_OODLE_JOB -e RED job.log | tail -5'""", """echo "exit $?"; tail -n 30 job.log'"""),
])

# 5g. the host cuts a big memory pool into fixed 256 MB chunks and a buffer that crosses a chunk's end gets no GPU buffer (Three Houses' field model of the lead): the chunk size can be set per game (DM_VK_ZC_CHUNK_MB, a multiple of 64; 256 = upstream's)
patch('zero-copy chunk size', 'nxnative/dm/android/gfx_vk_core.c', 'NX2A_ZCCHUNK', [
("""#define ZC_CHUNK 0x10000000ull
""", """static uint64_t zc_chunk_sz(void) {   // NX2A_ZCCHUNK
    static uint64_t c; if (c) return c;
    const char *e = getenv("DM_VK_ZC_CHUNK_MB"); long m = e ? atol(e) : 0;
    c = m >= 64 && m <= 512 && !(m & 63) ? (uint64_t)m << 20 : 0x10000000ull; return c;
}
#define ZC_CHUNK zc_chunk_sz()
"""),
])

# 5h. a buffer-to-buffer copy whose destination (or source) crosses the end of a zero-copy chunk found no buffer and was dropped ("buffer copy outside the memory pools"): in Three Houses
# that copy is the lead's field model's vertex data, so the model drew garbage. Any chunk size has the same problem (the game packs its buffers back to back), so the copy is split at the chunk ends
patch('copy across chunks', 'nxnative/dm/android/gfx_vk_core.c', 'NX2A_COPYSPLIT', [
("""void mtl_sub_copy(uint64_t src, uint64_t dst, uint64_t n) {
""", """static void mtl_sub_copy_one(uint64_t src, uint64_t dst, uint64_t n) {
"""),
("""void mtl_sub_fill(uint64_t dst, uint64_t n, uint32_t value) {
""", """void mtl_sub_copy(uint64_t src, uint64_t dst, uint64_t n) {   // NX2A_COPYSPLIT: in pieces that each lie in one chunk of the source's pool and of the destination's
    for (uint64_t done = 0; done < n;) {
        uint64_t s = src + done, d = dst + done, m = n - done;
        vkpool_t *ps = vk_pool_of(s, 1), *pd = vk_pool_of(d, 1);
        if (ps && s + m > ps->hi) m = ps->hi - s;
        if (pd && d + m > pd->hi) m = pd->hi - d;
        mtl_sub_copy_one(s, d, m); done += m;
    }
}
void mtl_sub_fill(uint64_t dst, uint64_t n, uint32_t value) {
"""),
])

# 5i. upstream's new shader export (#212) turned every shader whose translator run wrote its SPIR-V but no reflection file into a failure and left it out of the bundle: on Three Houses 323 of 1,380
# (the lead's field model among the draws that then vanish). Until #212 such a shader was kept with an empty reflection, as every earlier port of the game did, and the game ran. Kept that way again,
# and the translator's first error lines go to the log (what throws, for a fifth of the game's shaders, is not known yet)
if (repo / 'nxnative/dm/android/tools/shader_products.py').is_file(): patch('shader without reflection', 'nxnative/dm/android/tools/shader_products.py', 'NX2A_NOREFL', [
("""    if not reflection.is_file(): raise ValueError(f'{key}: translator omitted reflection')
""", """    if not reflection.is_file(): return data, {'_missing': True, 'key': key, 'cbufs': [], 'sbufs': [], 'textures': [], 'images': []}   # NX2A_NOREFL: the SPIR-V is kept, with an empty reflection
"""),
("""def validate_bindings(bindings, resource):
""", """def validate_bindings(bindings, resource):
    if resource.get('_missing'): return   # NX2A_NOREFL
"""),
])
# why a shader gets no reflection (the translator wrote its SPIR-V and then threw): its exception types and messages, and which stages are hit, go to the port log (both porter versions)
_newer = (repo / 'nxnative/dm/android/tools/shader_products.py').is_file()   # upstream's export with products (#212) reports the translator's errors differently
if not _newer: patch('shader translator errors in the log', 'nxnative/dm/android/tools/shader_vk.py', 'NX2A_XLERR', [
("""    entries, fails = [], collections.Counter()
""", """    entries, fails = [], collections.Counter(); nores = []   # NX2A_XLERR
"""),
("""        spv = open(spv_p, 'rb').read(); res = json.load(open(res_p)) if os.path.exists(res_p) else {}
""", """        spv = open(spv_p, 'rb').read(); res = json.load(open(res_p)) if os.path.exists(res_p) else {}
        if not os.path.exists(res_p): nores.append(k)
"""),
("""    for e, n in errs.most_common(8): print(f'  translator: {n:5d}  {e}')
""", """    for e, n in errs.most_common(8): print(f'  translator: {n:5d}  {e}')
    reasons = collections.Counter()
    for e, n in errs.items(): reasons[re.sub(r'^\\[RED\\] [0-9a-fA-F]+: ', '', e)] += n
    for e, n in reasons.most_common(6): print(f'[RED] translator: {n} x {e}', flush=True)
    if nores: print(f'[RED] translator: {len(nores)} shaders without reflection, by stage {dict(collections.Counter(stages[k] for k in nores))}, e.g. {" ".join(nores[:3])}', flush=True)
"""),
])
if _newer: patch('shader translator errors in the log (newer)', 'porter/pipeline.py', 'NX2A_XLERR3', [
("""            elif s.startswith('[RED] '): say(s)
""", """            elif s.startswith('  translator:'): say(s.strip()[:300])   # NX2A_XLERR3
            elif s.startswith('[RED] '): say(s)
"""),
])
if not _newer: patch('shader translator lines in the log', 'porter/pipeline.py', 'NX2A_XLERR2', [
("""            elif s.startswith('[RED] this Python has no zstd'): say(s)""", """            elif s.startswith('[RED] translator:'): say(s)   # NX2A_XLERR2
            elif s.startswith('[RED] this Python has no zstd'): say(s)"""),
])

# 5j. clang / lld crash now and then inside the phone's Ubuntu (ld.lld "Segmentation fault" in realloc while linking the adrenotools libraries, Three Houses): the same command is run again, up to three times
patch('retry crashed tools', 'nxnative/dm/android/build.py', 'NX2A_RETRY', [
("""import argparse, concurrent.futures as cf, os, re, subprocess, sys
""", """import argparse, concurrent.futures as cf, os, re, subprocess, sys
_real_run = subprocess.run   # NX2A_RETRY
def _retry_run(*a, **k):
    for _ in range(3):
        r = _real_run(*a, **k)
        err = getattr(r, 'stderr', None) or ''
        if r.returncode and (r.returncode < 0 or 'Segmentation fault' in err or 'PLEASE submit a bug report' in err): print('a build tool crashed: running it again', file=sys.stderr); continue
        break
    return r
subprocess.run = _retry_run
"""),
])


# 6. NGR shared launcher: keep each game's files in its own directory under the single NGR app.
# The common NativeActivity dispatcher sets DM_GAME_DIR before forwarding ANativeActivity_onCreate.
patch('NGR per-game data root', 'nxnative/dm/android/front_android.c', 'NX2A_GAME_DIR', [
("    snprintf(g_root, sizeof g_root, \"%s\", act->externalDataPath ? act->externalDataPath : act->internalDataPath);",
 "    const char *ngr_game_dir = getenv(\"DM_GAME_DIR\");\n    if (ngr_game_dir && *ngr_game_dir) snprintf(g_root, sizeof g_root, \"%s\", ngr_game_dir);\n    else snprintf(g_root, sizeof g_root, \"%s\", act->externalDataPath ? act->externalDataPath : act->internalDataPath); // NX2A_GAME_DIR"),
])

patch('NGR overlay asset stdio', 'nxnative/dm/android/overlay_theme.c', 'NX2A_ASSET_STDIO', [
("#include <stdlib.h>", "#include <stdio.h> /* NX2A_ASSET_STDIO */\n#include <stdlib.h>"),
])

# 7. NGR NativeActivity uses the one NGR APK's AssetManager. Game-specific overlay themes
# are therefore unpacked beside the game payload and read from DM_GAME_DIR/assets.
patch('NGR per-game overlay assets', 'nxnative/dm/android/overlay_theme.c', 'NX2A_GAME_ASSETS', [
("static uint8_t *asset(const char *name, size_t *n) {   // the whole asset, NUL-terminated (malloc), NULL when the APK has none\n    AAssetManager *am = dm_front_assets(); AAsset *a = am ? AAssetManager_open(am, name, AASSET_MODE_BUFFER) : NULL;",
 "static uint8_t *asset(const char *name, size_t *n) {   // NX2A_GAME_ASSETS: per-game assets take precedence over the NGR shell APK\n    const char *root = getenv(\"DM_GAME_DIR\");\n    if (root && *root) { char path[1200]; snprintf(path, sizeof path, \"%s/assets/%s\", root, name); FILE *f = fopen(path, \"rb\"); if (f) { if (fseek(f, 0, SEEK_END)) { fclose(f); return NULL; } long len = ftell(f); if (len < 0 || fseek(f, 0, SEEK_SET)) { fclose(f); return NULL; } uint8_t *b = malloc((size_t)len + 1); if (!b) { fclose(f); return NULL; } size_t got = fread(b, 1, (size_t)len, f); fclose(f); if (got != (size_t)len) { free(b); return NULL; } b[len] = 0; *n = (size_t)len; return b; } }\n    AAssetManager *am = dm_front_assets(); AAsset *a = am ? AAssetManager_open(am, name, AASSET_MODE_BUFFER) : NULL;"),
])

# 8. Keep game saves and temporary files isolated in NGR's private storage per game.
patch('NGR per-game save roots', 'nxnative/dm/android/front_android.c', 'NX2A_GAME_SAVE_ROOT', [
("    snprintf(p, sizeof p, \"%s/save\", act->internalDataPath); mkdir(p, 0700); setenv(\"DM_SAVE\", p, 0);\n    snprintf(p, sizeof p, \"%s/temp\", act->internalDataPath); mkdir(p, 0700); setenv(\"DM_TEMP\", p, 0);",
 "    const char *ngr_private_root = getenv(\"NGR_PRIVATE_GAME_DIR\"); if (!ngr_private_root || !*ngr_private_root) ngr_private_root = act->internalDataPath;\n    snprintf(p, sizeof p, \"%s/save\", ngr_private_root); mkdir(p, 0700); setenv(\"DM_SAVE\", p, 0);\n    snprintf(p, sizeof p, \"%s/temp\", ngr_private_root); mkdir(p, 0700); setenv(\"DM_TEMP\", p, 0); // NX2A_GAME_SAVE_ROOT"),
])

# 9. NGR writes the compiled native host, optional driver libraries and UI assets directly into the data pack.
patch('NGR no per-game APK', 'porter/pipeline.py', 'NX2A_NGR_NO_APK', [
("""        self.host()
        self.apk()
        self.data()
""", """        self.host()
        if os.environ.get('NX2A_NGR') != '1': self.apk()   # NX2A_NGR_NO_APK
        self.data()
"""),
("""        say(f'done: {self.result["apk"]} and {self.result["data"]}')
""", """        if os.environ.get('NX2A_NGR') == '1':
            say(f'done: NGR native runtime {self.result.get("runtime", "(missing)")} and data pack {self.result["data"]}')
        else:
            say(f'done: {self.result["apk"]} and {self.result["data"]}')
"""),
("""        man = datapack.build(dst, profile=self.ap, version=self.pkg_ver, display=self.display, patched=self.patched, romfs=self.game / 'RomFS', shaders=self.dmsv,
""", """        pack_files = {**self.fps_files, **font_files, **self.ngr_runtime_files()}
        man = datapack.build(dst, profile=self.ap, version=self.pkg_ver, display=self.display, patched=self.patched, romfs=self.game / 'RomFS', shaders=self.dmsv,
"""),
("""                             files={**self.fps_files, **font_files},
""", """                             files=pack_files, profile_h=profile_h,
"""),
("""        self.data_path = dst; self.result['data'] = str(dst)
""", """        self.data_path = dst; self.result['data'] = str(dst)
        if os.environ.get('NX2A_NGR') == '1':
            self.result['runtime'] = str(dst / 'libdmhost.so')
            self.result['runtime_libs'] = sorted(p.name for p in dst.glob('*.so'))
"""),
("""    def data(self):
""", """    def ngr_runtime_files(self):
        if os.environ.get('NX2A_NGR') != '1': return {}
        files = {'libdmhost.so': self.so}
        # NX2A_NGR_GAME_COVER: nx_extract already decrypted the control NACP icon.
        # Keep the original JPEG in the game data pack; the launcher caches it as library art.
        icon = next((d / 'icon.jpg' for d in (self.game, self.base) if d and (d / 'icon.jpg').is_file()), None)
        if icon: files['ngr-cover.jpg'] = icon
        # NGR packages every native library produced by this game's source build.
        # No hand-maintained companion list and no modification of prebuilt binaries.
        for library in sorted(self.so.parent.glob('*.so')):
            if library.is_file():
                files[library.name] = library
        driver = self.o.vulkan_driver
        if driver:
            if driver.name != driver_lib_name(driver):
                packed = self.so.parent / driver_lib_name(driver)
                shutil.copyfile(driver, packed)
                driver = packed
            files[driver.name] = driver
        theme = android_profile.theme(self.g.id)
        for name in ('theme.tsv', 'tablet.png', 'phone.png'):
            asset = theme / name
            if asset.is_file(): files[f'assets/overlay/{name}'] = asset
        for name, asset in ui_font_assets().items():
            if Path(asset).is_file(): files[f'assets/{name}'] = asset
        return files

    def data(self):
"""),
])

# NGR builds AdrenoTools and its hook libraries from source as part of the game's
# runtime build. They are packaged with the game even when the system Vulkan
# driver is selected, so switching drivers later does not require recompilation.
patch('NGR build complete native runtime', 'porter/pipeline.py', 'NX2A_NGR_ADRENOTOOLS', [
("""                + (['--adrenotools'] if self.o.vulkan_driver else []), self.logs / 'android_host.log', env=self.env)
""",
 """                 + (['--adrenotools'] if self.o.vulkan_driver or os.environ.get('NX2A_NGR') == '1' else []), self.logs / 'android_host.log', env=self.env)  # NX2A_NGR_ADRENOTOOLS
"""),
])


# 9b. The in-game pause/settings menu must provide an explicit way back to NGR.
# Back opens this menu; the last row now ends the NativeActivity instead of leaving
# the player trapped with only Resume available.
patch('NGR overlay exit row', 'nxnative/dm/android/overlay_layout.h', 'NX2A_NGR_EXIT_ROW', [
("OVM_RESUME, OVM_TAB, OVM_N", "OVM_RESUME, OVM_EXIT, OVM_TAB, OVM_N"),
("#define OVM_ROWS (OVM_PER_TAB + 2)", "#define OVM_ROWS (OVM_PER_TAB + 3)"),
("static inline int ov_menu_item(int tab, int row) { return row == 0 ? OVM_TAB : row == OVM_ROWS - 1 ? OVM_RESUME : row > 0 && row < OVM_ROWS - 1 ? OVM_TAB_ITEMS[tab & 1][row - 1] : -1; }",
 "static inline int ov_menu_item(int tab, int row) { return row == 0 ? OVM_TAB : row == OVM_ROWS - 2 ? OVM_RESUME : row == OVM_ROWS - 1 ? OVM_EXIT : row > 0 && row < OVM_ROWS - 2 ? OVM_TAB_ITEMS[tab & 1][row - 1] : -1; }"),
])

patch('NGR overlay exit action', 'nxnative/dm/android/front_android.c', 'NX2A_NGR_EXIT_ACTION', [
("static void on_resume(ANativeActivity *a) { if (g_quit) { act_finish(a); return; } go_foreground(); }",
 """static void act_finish_async(void) {   // menu/input thread: NGR's Java shim marshals Activity.finish() onto Android's UI thread
    if (!g_act || !g_act->vm) return;
    JavaVM *vm = g_act->vm; JNIEnv *E = NULL; int attached = 0;
    jint state = (*vm)->GetEnv(vm, (void **)&E, JNI_VERSION_1_6);
    if (state == JNI_EDETACHED) { if ((*vm)->AttachCurrentThread(vm, &E, NULL) != JNI_OK) { LOG("[RED] cannot attach exit request to Java VM"); return; } attached = 1; }
    else if (state != JNI_OK) { LOG("[RED] cannot obtain JNI environment for exit request"); return; }
    jclass cls = (*E)->GetObjectClass(E, g_act->clazz);
    jmethodID method = cls ? (*E)->GetMethodID(E, cls, "finishFromNative", "()V") : NULL;
    if (method) (*E)->CallVoidMethod(E, g_act->clazz, method);
    if ((*E)->ExceptionCheck(E)) { (*E)->ExceptionDescribe(E); (*E)->ExceptionClear(E); }
    if (!method) { LOG("[RED] finishFromNative is unavailable; using ANativeActivity_finish fallback"); ANativeActivity_finish(g_act); }
    if (attached) (*vm)->DetachCurrentThread(vm);
}
static void on_resume(ANativeActivity *a) { if (g_quit) { act_finish(a); return; } go_foreground(); }"""),
("static void menu_do(int item) {\n    if (item == OVM_OVERLAY)",
 "static void menu_do(int item) {\n    if (item == OVM_EXIT) { LOG(\"[menu] Exit game selected\"); g_quit = 1; act_finish_async(); return; }\n    if (item == OVM_OVERLAY)"),
])

patch('NGR overlay exit labels', 'nxnative/dm/android/gfx_vk_present.c', 'NX2A_NGR_EXIT_LABEL', [
("static const char *const OVM_LABELS[OVM_N] = {\"Show gamepad\", \"Opacity\", \"Edit layout\", \"Rumble\", \"Show FPS\", \"Mode\", \"Export save\", \"Import save\", \"Face buttons\", \"Resume\", \"\"};",
 "static const char *const OVM_LABELS[OVM_N] = {\"Show gamepad\", \"Opacity\", \"Edit layout\", \"Rumble\", \"Show FPS\", \"Mode\", \"Export save\", \"Import save\", \"Face buttons\", \"Resume\", \"Exit game\", \"\"};"),
("if (it == OVM_RESUME) { cv_rrect(cv, r[0], r[1], r[0] + rw, r[1] + 1, 0.5f, C_LINE); cv_text(cv, r[0] + (rw - cv_text_w(\"Resume\", is)) / 2, cy, \"Resume\", is, C_ACCENT); continue; }",
 "if (it == OVM_RESUME || it == OVM_EXIT) { const char *word = OVM_LABELS[it]; cv_rrect(cv, r[0], r[1], r[0] + rw, r[1] + 1, 0.5f, C_LINE); cv_text(cv, r[0] + (rw - cv_text_w(word, is)) / 2, cy, word, is, C_ACCENT); continue; }"),
])


# 10. every device path in env.txt (DLC, sysdata, fonts, FPS tables) resolves inside this game's NGR folder.
patch('NGR per-game data-pack paths', 'porter/datapack.py', 'NX2A_GAME_FILES', [
("""def files_folder(package): return f'/sdcard/Android/data/{package}/files'
""", """def files_folder(package):
    root = f'/sdcard/Android/data/{package}/files'
    game_id = os.environ.get('NX2A_GAME_ID', '')
    return f'{root}/games/{game_id}' if game_id else root   # NX2A_GAME_FILES
"""),
("""    for name, src in (files or {}).items(): shutil.copyfile(src, tmp / name); n += 1; b += Path(src).stat().st_size
""", """    for name, src in (files or {}).items():
        target = tmp / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target); n += 1; b += Path(src).stat().st_size
"""),
])

# 11. Keep the exact profile header hash in the data-pack manifest. The NGR exporter
# uses it to select the same game / Android profile that produced libdmhost.so.
patch('NGR profile hash manifest', 'porter/datapack.py', 'NX2A_PROFILE_HASH', [
("""def build(dst, *, profile, version, display, patched, romfs, shaders, aoc=None, sysdata=None, language='en-US', package=None, env=(), settings=None, files=None, progress=None):
""", """def build(dst, *, profile, version, display, patched, romfs, shaders, aoc=None, sysdata=None, language='en-US', package=None, env=(), settings=None, files=None, profile_h=None, progress=None):  # NX2A_PROFILE_HASH
"""),
("""    man = dict(title_id=profile.id, name=profile.name, package=package, version=version, display=display, language=language, requires=profile.requires,
""", """    man = dict(title_id=profile.id, name=profile.name, package=package, version=version, display=display, language=language, requires=profile.requires, profile_h=profile_h, game_id=os.environ.get('NX2A_GAME_ID', ''),
"""),
])

patch('NGR profile hash computation', 'porter/pipeline.py', 'NX2A_PROFILE_HASH', [
("""    def data(self):
        PROG.stage('data pack', step='button-icon font')
""", """    def data(self):
        import hashlib  # NX2A_PROFILE_HASH
        profile_h = hashlib.sha256(game.header(self.g).encode('utf-8')).hexdigest()
        PROG.stage('data pack', step='button-icon font')
"""),
])

# 12. Trace the Android host thread independently of the dispatcher. The game's
# own stderr is redirected to <game_dir>/log.txt; these markers show whether the
# thread starts, enters dm/host/main.c, completes module loading and reaches nnMain.
patch('NGR host boot trace', 'nxnative/dm/android/front_android.c', 'NX2A_NGR_HOST_BOOT_TRACE', [
("""static void *host_thread(void *a) {
    (void)a;
    char mods[600]; snprintf(mods, sizeof mods, "%s/mods", g_root);
    char *argv[] = {"dmhost", mods, NULL};
    atomic_store(&g_running, 1);
    int rc = main(2, argv);
    LOG("host returned %d", rc);
""", """static void *host_thread(void *a) {
    (void)a;
    char mods[600]; snprintf(mods, sizeof mods, "%s/mods", g_root);
    char *argv[] = {"dmhost", mods, NULL};
    LOG("[NGR host] thread entered; root=%s mods=%s", g_root, mods);
    atomic_store(&g_running, 1);
    LOG("[NGR host] entering dm host main");
    int rc = main(2, argv);
    LOG("[NGR host] dm host main returned rc=%d", rc);
    LOG("host returned %d", rc);
"""),
("""    if (pthread_create(&t, &at, host_thread, NULL)) LOG("[RED] cannot start the host thread"); else pthread_detach(t);
""", """    if (pthread_create(&t, &at, host_thread, NULL)) LOG("[RED] cannot start the host thread");
    else { pthread_detach(t); LOG("[NGR host] detached host thread created; stack=%zu MB", ssz >> 20); }
"""),
])

patch('NGR boot profiling', 'nxnative/dm/host/main.c', 'NX2A_NGR_BOOT_PROF', [
("""    load_modules(argv[1], names, n);
    dm_sdk_major();   // logs the SDK version, which SDK-dependent behaviour follows (loader.c)
""", """    LOG("[NGR boot] loading %d guest modules from %s; profile=%s", n, argv[1], DM_GAME_ID);
    load_modules(argv[1], names, n);
    LOG("[NGR boot] guest modules loaded; resolving SDK and entering guest startup");
    dm_sdk_major();   // logs the SDK version, which SDK-dependent behaviour follows (loader.c)
"""),
("""    LOG(">>> nnMain"); ((fn0)req("nnMain"))();
""", """    LOG("[NGR boot] SDK startup and module constructors complete");
    LOG(">>> nnMain"); ((fn0)req("nnMain"))();
"""),
])


# 13. NGR captures a thread-state snapshot when frame progress stops. The upstream
# watchdog already knows how to dump guest thread PCs/backtraces and graphics wait
# points; expose it during normal gameplay, but never terminate the game process.
patch('NGR non-terminating stall snapshots', 'nxnative/dm/host/crash.c', 'NX2A_WATCH_DUMP_ALL', [
("""static unsigned g_watch_stall;
""", """static unsigned g_watch_stall;
static int g_watch_dump_all, g_watch_no_exit;  // NX2A_WATCH_DUMP_ALL
"""),
("""        // Dump only after entering a run; at most 3 dumps per process, at least 10 seconds between two dumps (the loading screen and the pause menu also stop ticks, do not let them flood the log)
        { static int dumps; static uint64_t last_dump, dumped_for;
          if (g_watch_stall && !atomic_load(&g_watch_pregame) && atomic_load(&g_watch_tick) > 0 && now - last >= 1000000000ull && now - last < (uint64_t)g_watch_stall * 1000000000ull
""", """        // NGR can request snapshots during normal gameplay even while the generic pregame flag remains set.
        // Keep the upstream rate limit: at most 3 dumps per process, at least 10 seconds apart.
        { static int dumps; static uint64_t last_dump, dumped_for;
          if (g_watch_stall && (g_watch_dump_all ? atomic_load(&g_watch_count) > 0 : (!atomic_load(&g_watch_pregame) && atomic_load(&g_watch_tick) > 0)) && now - last >= 1000000000ull && now - last < (uint64_t)g_watch_stall * 1000000000ull
"""),
("""        if (g_watch_stall && now - last >= (uint64_t)g_watch_stall * 1000000000ull) {
""", """        if (g_watch_stall && !g_watch_no_exit && now - last >= (uint64_t)g_watch_stall * 1000000000ull) {
"""),
("""    const char *watch = getenv("DM_WATCH"), *stall = getenv("DM_WATCH_STALL");
""", """    const char *watch = getenv("DM_WATCH"), *stall = getenv("DM_WATCH_STALL");
    const char *dump_all = getenv("DM_WATCH_DUMP_ALL"), *no_exit = getenv("DM_WATCH_NO_EXIT");
    g_watch_dump_all = dump_all && atoi(dump_all) != 0;
    g_watch_no_exit = no_exit && atoi(no_exit) != 0;
"""),
]);
# All patch groups must run before reporting failures.

# 14. NGR loading snapshots: the game can keep presenting a static loading frame
# while its guest main thread is blocked on a file, event, mutex or worker. The
# generic watchdog only observes frame progress, so take a small bounded series
# of independent snapshots from its host thread during startup/loading.
patch('NGR timed loading thread snapshots', 'nxnative/dm/host/crash.c', 'NX2A_LOAD_SNAPSHOTS', [
("""static int g_watch_dump_all, g_watch_no_exit;  // NX2A_WATCH_DUMP_ALL
""", """static int g_watch_dump_all, g_watch_no_exit;  // NX2A_WATCH_DUMP_ALL
static unsigned g_watch_load_dumps, g_watch_load_interval = 10;  // NX2A_LOAD_SNAPSHOTS
"""),
("""static void *watchdog_main(void *arg) {
    (void)arg;
    for (;;) {
        usleep(250000);
""", """static void *watchdog_main(void *arg) {
    (void)arg;
    uint64_t watch_started = watch_now_ns();
    unsigned load_dumps = 0;
    for (;;) {
        usleep(250000);
        // Bounded snapshots at 10/20/30 seconds, independent of frame progress.
        if (g_watch_load_dumps && load_dumps < g_watch_load_dumps &&
            watch_now_ns() - watch_started >= (uint64_t)(load_dumps + 1) * g_watch_load_interval * 1000000000ull) {
            load_dumps++;
            crash_dump_now("NGR timed loading snapshot");
        }
"""),
("""    const char *dump_all = getenv("DM_WATCH_DUMP_ALL"), *no_exit = getenv("DM_WATCH_NO_EXIT");
    g_watch_dump_all = dump_all && atoi(dump_all) != 0;
    g_watch_no_exit = no_exit && atoi(no_exit) != 0;
""", """    const char *dump_all = getenv("DM_WATCH_DUMP_ALL"), *no_exit = getenv("DM_WATCH_NO_EXIT");
    const char *load_dumps = getenv("DM_WATCH_LOAD_DUMPS"), *load_interval = getenv("DM_WATCH_LOAD_INTERVAL");
    g_watch_dump_all = dump_all && atoi(dump_all) != 0;
    g_watch_no_exit = no_exit && atoi(no_exit) != 0;
    g_watch_load_dumps = load_dumps ? (unsigned)atoi(load_dumps) : 0;
    if (g_watch_load_dumps > 3) g_watch_load_dumps = 3;
    if (load_interval) { unsigned v = (unsigned)atoi(load_interval); if (v >= 5 && v <= 60) g_watch_load_interval = v; }
"""),
]);


# 16. Trace only Unity loading/synchronization threads; observational, no scheduling changes.
patch('NGR targeted synchronization trace', 'nxnative/dm/host/hle_thread.c', 'NX2A_SYNC_TRACE', [
("""static thr_t *g_wait;          // All waiting threads (lock / condition / address / synchronization)
""", """static thr_t *g_wait;          // All waiting threads (lock / condition / address / synchronization)
// NX2A_SYNC_TRACE: handles observed in Twelve Minutes loading snapshots.
static uint64_t g_ngr_sync_keys[32]; static unsigned g_ngr_sync_key_n, g_ngr_sync_signal_logs;
static int ngr_sync_watch(uint32_t h) {
    return h == 0x1001 || h == 0x1005 || h == 0x1017 || h == 0x101d ||
           h == 0x101f || h == 0x1020 || h == 0x1025 || h == 0x1027;
}
static void ngr_sync_track_key(uint64_t key) {
    for (unsigned i = 0; i < g_ngr_sync_key_n; i++) if (g_ngr_sync_keys[i] == key) return;
    if (g_ngr_sync_key_n < 32) g_ngr_sync_keys[g_ngr_sync_key_n++] = key;
}
static int ngr_sync_key_watched(uint64_t key) {
    for (unsigned i = 0; i < g_ngr_sync_key_n; i++) if (g_ngr_sync_keys[i] == key) return 1;
    return 0;
}
"""),
("""        if (ld32(addr) == ((uint32_t)regs[0] | WAITERS_BIT)) { t->waddr = addr; t->wtag = (uint32_t)regs[2];
""", """        if (ld32(addr) == ((uint32_t)regs[0] | WAITERS_BIT)) {
            if (ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] lock-wait h=%#x owner=%#x addr=%#llx tag=%#x word=%#x", t->handle, (uint32_t)regs[0], (unsigned long long)addr, (uint32_t)regs[2], ld32(addr));
            t->waddr = addr; t->wtag = (uint32_t)regs[2];
"""),
("""            r = block(t, 1, -1);
            if (ov) pthread_override_qos_class_end_np(ov); }
""", """            r = block(t, 1, -1);
            if (ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] lock-wake h=%#x addr=%#llx result=%lld word=%#x", t->handle, (unsigned long long)addr, (long long)r, ld32(addr));
            if (ov) pthread_override_qos_class_end_np(ov); }
"""),
("""    case 0x1B: G_lock(); lock_handoff(regs[0]); pthread_mutex_unlock(&G); regs[0] = 0; return 1;
""", """    case 0x1B: { thr_t *t = cur(); if (ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] unlock h=%#x addr=%#llx word=%#x", t->handle, (unsigned long long)regs[0], ld32(regs[0])); G_lock(); lock_handoff(regs[0]); pthread_mutex_unlock(&G); regs[0] = 0; return 1; }
"""),
("""        G_lock();
        // The order matters: first set the condition key = 1, then release the mutex. The SDK's InternalConditionVariable::Signal first reads the condition key in user mode, and does not issue svc 0x1D if it is 0;
""", """        G_lock();
        if (ngr_sync_watch(t->handle)) {
            ngr_sync_track_key(key);
            LOG("[NGR_SYNC] cv-wait h=%#x lock=%#llx key=%#llx tag=%#x timeout_ns=%lld lockword=%#x keyword=%#x",
                t->handle, (unsigned long long)addr, (unsigned long long)key, (uint32_t)regs[2],
                (long long)regs[3], ld32(addr), ld32(key));
        }
        // The order matters: first set the condition key = 1, then release the mutex. The SDK's InternalConditionVariable::Signal first reads the condition key in user mode, and does not issue svc 0x1D if it is 0;
"""),
("""        int64_t r = block(t, 2, (int64_t)regs[3]);   // Timeout: the lock is not re-acquired (user mode takes it itself)
        pthread_mutex_unlock(&G);
""", """        int64_t r = block(t, 2, (int64_t)regs[3]);   // Timeout: the lock is not re-acquired (user mode takes it itself)
        if (ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] cv-wake h=%#x lock=%#llx key=%#llx result=%lld lockword=%#x keyword=%#x",
            t->handle, (unsigned long long)addr, (unsigned long long)key, (long long)r, ld32(addr), ld32(key));
        pthread_mutex_unlock(&G);
"""),
("""        uint64_t key = regs[0]; int cnt = (int)regs[1], n = 0;
        G_lock();
        for (thr_t *w; (cnt <= 0 || n < cnt) && (w = pick(2, key)); n++) lock_acquire_for(w, w->waddr, w->wtag);   // In kernel order; once turned into a lock wait or woken it is no longer kind 2
""", """        uint64_t key = regs[0]; int cnt = (int)regs[1], n = 0;
        G_lock();
        int ngr_tracked_signal = ngr_sync_key_watched(key);
        if (ngr_tracked_signal && g_ngr_sync_signal_logs < 256)
            LOG("[NGR_SYNC] cv-signal key=%#llx count=%d", (unsigned long long)key, cnt);
        for (thr_t *w; (cnt <= 0 || n < cnt) && (w = pick(2, key)); n++) lock_acquire_for(w, w->waddr, w->wtag);   // In kernel order; once turned into a lock wait or woken it is no longer kind 2
        if (ngr_tracked_signal && g_ngr_sync_signal_logs++ < 256)
            LOG("[NGR_SYNC] cv-signalled key=%#llx woken=%d", (unsigned long long)key, n);
""")
]);

# 17. Trace condition-variable wait registration and actual wake delivery for the
# Unity loading workers. This is observational only: it does not alter queue or
# synchronization semantics. The older syscall trace missed some waits because
# the thread's diagnostic snapshot can be taken after its last SVC.
patch('NGR condition-variable wait/wake trace', 'nxnative/dm/host/hle_thread.c', 'NX2A_SYNC_WAIT_TRACE', [
("""static void wake(thr_t *t, int64_t res) {
    wait_unlink(t);""",
 """static void wake(thr_t *t, int64_t res) {
    if (t->wkind == 2 && ngr_sync_watch(t->handle))
        LOG("[NGR_SYNC_WAIT] delivered h=%#x key=%#llx lock=%#llx result=%lld",
            t->handle, (unsigned long long)t->wkey, (unsigned long long)t->waddr, (long long)res); /* NX2A_SYNC_WAIT_TRACE */
    wait_unlink(t);"""),
("""static int64_t block(thr_t *t, int kind, int64_t ns) {
    t->wkind = kind;""",
 """static int64_t block(thr_t *t, int kind, int64_t ns) {
    if (kind == 2 && ngr_sync_watch(t->handle))
        LOG("[NGR_SYNC_WAIT] register h=%#x key=%#llx lock=%#llx timeout_ns=%lld",
            t->handle, (unsigned long long)t->wkey, (unsigned long long)t->waddr, (long long)ns);
    t->wkind = kind;"""),
("""        for (thr_t *w; (cnt <= 0 || n < cnt) && (w = pick(2, key)); n++) lock_acquire_for(w, w->waddr, w->wtag);   // In kernel order; once turned into a lock wait or woken it is no longer kind 2""",
 """        for (thr_t *w; (cnt <= 0 || n < cnt) && (w = pick(2, key)); n++) {
            if (ngr_sync_watch(w->handle))
                LOG("[NGR_SYNC_WAIT] signal-target h=%#x key=%#llx lock=%#llx tag=%#x",
                    w->handle, (unsigned long long)key, (unsigned long long)w->waddr, w->wtag);
            lock_acquire_for(w, w->waddr, w->wtag);
        }   // In kernel order; once turned into a lock wait or woken it is no longer kind 2"""),
]);


# Twelve Minutes (0100CD701434C000): its local UserPresence object must accept
# offline initialization/updates. The network-facing friends service stays cut.
patch('NGR offline UserPresence', 'nxnative/dm/host/hle_friends.c', 'NX2A_FRIENDS_OFFLINE_PRESENCE', [
("""// Presence
HLE_FORCE("_ZN2nn7friends12UserPresence10InitializeERKNS_7account3UidE", "presence unavailable (cut)", Result, h_fr_UpInit, void *self, const void *uid) { (void)self; (void)uid; return RES_FAIL; }
HLE_FORCE("_ZN2nn7friends12UserPresence14SetDescriptionEPKc", "presence unavailable (cut)", Result, h_fr_UpDesc, void *self, const char *s) { (void)self; (void)s; return RES_FAIL; }
HLE_FORCE("_ZN2nn7friends12UserPresence6CommitEv", "presence unavailable (cut)", Result, h_fr_UpCommit, void *self) { (void)self; return RES_FAIL; }""",
 """// Presence is a local object. Accept its state changes offline; do not publish to the friends service.
HLE_FORCE("_ZN2nn7friends12UserPresence10InitializeERKNS_7account3UidE", "presence accepted, not published (cut)", Result, h_fr_UpInit, void *self, const void *uid) { (void)self; (void)uid; return RES_OK; }
HLE_FORCE("_ZN2nn7friends12UserPresence10InitializeEv", "presence accepted, not published (cut)", Result, h_fr_UpInitNoUid, void *self) { (void)self; return RES_OK; } /* NX2A_FRIENDS_OFFLINE_PRESENCE */
HLE_FORCE("_ZN2nn7friends12UserPresence14SetDescriptionEPKc", "presence accepted, not published (cut)", Result, h_fr_UpDesc, void *self, const char *s) { (void)self; (void)s; return RES_OK; }
HLE_FORCE("_ZN2nn7friends12UserPresence6CommitEv", "presence accepted, not published (cut)", Result, h_fr_UpCommit, void *self) { (void)self; return RES_OK; }""")
]);

def ensure_twelve_minutes_profile():
    if PATCH_ONLY and 'NGR Twelve Minutes profile' not in PATCH_ONLY: return
    d = repo / 'nxnative/dm/games/0100CD701434C000'
    game = d / 'game.tsv'
    if game.exists():
        if 'NX2A_TWELVE_MINUTES_PROFILE' in game.read_text(encoding='utf-8'):
            print('NGR Twelve Minutes profile: already')
        else:
            print('NGR Twelve Minutes profile: upstream profile exists; leaving it unchanged')
        return
    d.mkdir(parents=True, exist_ok=True)
    game.write_text("""# NGR profile based on the measured nxnative Twelve Minutes profile (seedds/nxnative ff b06d6).
title_id\t0100CD701434C000
program_id\t0100CD701434C000
name\tTwelve Minutes
ipa\tTwelveMinutes.ipa
app_category\tpublic.app-category.games
build\tv0\t1.0.1\tmain=e93717eabaa393489060fcbf8f086ca3\tsubsdk0=bffed55ea46c1b48ddeabcacdfbf81bf\tsdk=56ec24747ec9e7f19b3efb062483a19d
package\tv0
shader_versions\tv0
modules\tmain subsdk0 sdk
romfs_marker\tData/resources.assets
zip_store\t.assets:.bank:.dat:.resource:.ress:.metallib
mem_reserve\t0x160000000
mem_alias\t0x138000000
mem_stack\t0x10000000
app_pool\t0xCD500000
sys_resource\t0x1000000
shader_groups\t/Data/=data
shader_note\tTwelve Minutes shaders; NX2A_TWELVE_MINUTES_PROFILE
depth_mode\tzero
""", encoding='utf-8')
    (d / 'android.tsv').write_text(
        "status\texperimental\npackage\tunknown.none.nx2android\norientation\tlandscape\n",
        encoding='utf-8')
    (d / 'README.md').write_text("""# Twelve Minutes (0100CD701434C000)

Profile based on the measured upstream nxnative profile at seedds/nxnative commit
ffb06d603bd9262417d8bcd076c4cf6829ace8f3. The game is Unity 2019.4.31f1 IL2CPP,
FMOD, SDK 12.3.7; modules are main, subsdk0 and sdk.

The 22% loading stall was traced to UserPresence::Initialize failing while the
friends service is unavailable. The NGR HLE patch accepts local UserPresence
initialization, description and commit without enabling online friends features.

The memory profile uses a 5.5 GiB guest layout, a 4.875 GiB alias region and the
3,285 MiB application pool. It also uses /Data/=data shader grouping and zero
depth mode. Android status remains experimental until verified on the target
device.
""", encoding='utf-8')
    print('NGR Twelve Minutes profile: installed (Build IDs, memory layout, shader/depth settings)')

try:
    ensure_twelve_minutes_profile()
except Exception as e:
    failed += 1
    print(f'NGR Twelve Minutes profile: FAILED: {e}')


# 18. A launcher shortcut may select another Vulkan driver without rebuilding the
# game data. The Android front end reads env.txt after the NativeActivity host has
# been entered, so apply the explicit NGR override after env_file() has loaded it.
patch('NGR per-launch Vulkan driver override', 'nxnative/dm/android/front_android.c', 'NX2A_DM_VK_DRIVER_OVERRIDE', [
    ("""    snprintf(p, sizeof p, "%s/env.txt", g_root); env_file(p);\n""",
     """    snprintf(p, sizeof p, "%s/env.txt", g_root); env_file(p);
    const char *ngr_vk_driver_override = getenv("NGR_DM_VK_DRIVER_OVERRIDE");
    if (ngr_vk_driver_override && *ngr_vk_driver_override) {
        setenv("DM_VK_DRIVER", ngr_vk_driver_override, 1);  // NX2A_DM_VK_DRIVER_OVERRIDE
        LOG("[Vulkan] using per-launch driver override: %s", ngr_vk_driver_override);
    }
"""),
])

# 19. The Unity synchronization trace was useful during the initial Twelve Minutes
# investigation, but its per-lock stderr writes must not run in normal gameplay.
# Reuse the existing watchdog/thread-snapshot opt-in via DM_SYNC_TRACE.
patch('NGR synchronization trace default-off gate', 'nxnative/dm/host/hle_thread.c', 'NX2A_SYNC_TRACE_GATED', [
    ("""// NX2A_SYNC_TRACE: handles observed in Twelve Minutes loading snapshots.
static uint64_t g_ngr_sync_keys[32];""",
     """// NX2A_SYNC_TRACE_GATED: diagnostics only; never emit per-lock I/O in normal play.
static int ngr_sync_trace_enabled(void) {
    static int enabled = -1;
    if (enabled < 0) { const char *v = getenv("DM_SYNC_TRACE"); enabled = v && v[0] == '1'; }
    return enabled;
}
static uint64_t g_ngr_sync_keys[32];"""),
    ("""if (ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] lock-wait""",
     """if (ngr_sync_trace_enabled() && ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] lock-wait"""),
    ("""if (ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] lock-wake""",
     """if (ngr_sync_trace_enabled() && ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] lock-wake"""),
    ("""if (ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] unlock""",
     """if (ngr_sync_trace_enabled() && ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] unlock"""),
    ("""if (ngr_sync_watch(t->handle)) {
            ngr_sync_track_key(key);""",
     """if (ngr_sync_trace_enabled() && ngr_sync_watch(t->handle)) {
            ngr_sync_track_key(key);"""),
    ("""if (ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] cv-wake""",
     """if (ngr_sync_trace_enabled() && ngr_sync_watch(t->handle)) LOG("[NGR_SYNC] cv-wake"""),
    ("""int ngr_tracked_signal = ngr_sync_key_watched(key);""",
     """int ngr_tracked_signal = ngr_sync_trace_enabled() && ngr_sync_key_watched(key);"""),
    ("""if (t->wkind == 2 && ngr_sync_watch(t->handle))
        LOG("[NGR_SYNC_WAIT] delivered""",
     """if (ngr_sync_trace_enabled() && t->wkind == 2 && ngr_sync_watch(t->handle))
        LOG("[NGR_SYNC_WAIT] delivered"""),
    ("""if (kind == 2 && ngr_sync_watch(t->handle))
        LOG("[NGR_SYNC_WAIT] register""",
     """if (ngr_sync_trace_enabled() && kind == 2 && ngr_sync_watch(t->handle))
        LOG("[NGR_SYNC_WAIT] register"""),
    ("""if (ngr_sync_watch(w->handle))
                LOG("[NGR_SYNC_WAIT] signal-target""",
     """if (ngr_sync_trace_enabled() && ngr_sync_watch(w->handle))
                LOG("[NGR_SYNC_WAIT] signal-target"""),
])



# 20. Metro 2033 Redux has guest worker threads that issue millions of progressing
# SleepThread(0) calls whose callee-saved registers change are normally treated as
# productive work and returned without a host scheduling point. Metro's PhysX
# simulator and uEngine Secondary issue millions of such calls while contending
# for a shared lock; the audio renderer and main thread then wait behind them.
# Keep the fast path unchanged for other games, but allow a per-game rate cap.
patch('NGR progressing-yield rate limiter', 'nxnative/dm/host/hle_thread.c', 'NX2A_YIELD_PROGRESS_LIMIT', [
    ("""static void thr_yield(thr_t *me, const uint64_t *regs) {
""",
     """// NX2A_YIELD_PROGRESS_LIMIT: cap pathological progressing-yield loops per thread.
static void yield_progress_limit(thr_t *me, uint64_t now) {
    static int limit = -1, handoff_every = 256;
    static _Thread_local uint64_t window_ns;
    static _Thread_local unsigned count, excess;
    if (limit < 0) {
        const char *e = getenv("DM_YIELD_PROGRESS_LIMIT");
        const char *h = getenv("DM_YIELD_PROGRESS_HANDOFF");
        limit = e && *e ? atoi(e) : 0;
        if (limit < 0) limit = 0;
        if (h && *h) handoff_every = atoi(h);
        if (handoff_every < 1) handoff_every = 1;
        if (handoff_every > 65536) handoff_every = 65536;
        if (limit > 0) LOG("DM_YIELD_PROGRESS_LIMIT=%d/s, host scheduler handoff every %d excess yields (no sleep while guest locks may be held)", limit, handoff_every);
    }
    if (limit <= 0) return;
    if (!window_ns || now - window_ns >= 1000000000ull) { window_ns = now; count = 0; excess = 0; }
    if (++count > (unsigned)limit && ++excess >= (unsigned)handoff_every) {
        excess = 0;
        sched_yield();
    }
}
static void thr_yield(thr_t *me, const uint64_t *regs) {
"""),
    ("""    if (!moved) yield_for(me, y0 - me->yrun_t0);
""",
     """    if (!moved) yield_for(me, y0 - me->yrun_t0);
    else yield_progress_limit(me, y0);  // NX2A_YIELD_PROGRESS_LIMIT
"""),
])




# 21. Metro's PhysX / Secondary workers share priority 43 with its audio and main
# threads. Give only these named workers Utility QoS; ArbitrateLock's existing
# priority-inheritance path temporarily boosts a lock owner to a blocked waiter's
# class, so the owner can release the mutex without starving audio or the UI.
patch('NGR name-based Utility QoS for Metro workers', 'nxnative/dm/host/hle_thread.c', 'NX2A_QOS_UTILITY_NAMES', [
    ("""static int g_qos_map, g_qos_e1 = 44, g_qos_e2 = 59;""",
     """static const char *thr_name(thr_t *t, char *buf, size_t n);
static int g_qos_map, g_qos_e1 = 44, g_qos_e2 = 59;"""),
    ("""static void qos_apply(thr_t *t) {   // on the thread itself
    qos_class_t q = prio_qos(t->prio);
    if ((uint32_t)q != t->qos && !pthread_set_qos_class_self_np(q, 0)) t->qos = (uint32_t)q;
}""",
     """static int qos_utility_name(thr_t *t) {
    if (!g_qos_map || !t) return 0;
    const char *list = getenv("DM_QOS_UTILITY_NAMES");
    if (!list || !*list) return 0;
    char name[64];
    const char *n = thr_name(t, name, sizeof name);
    size_t nl = strlen(n);
    for (const char *p = list; *p;) {
        const char *end = strchr(p, ';');
        size_t len = end ? (size_t)(end - p) : strlen(p);
        if (len == nl && nl && !memcmp(p, n, len)) return 1;
        if (!end) break;
        p = end + 1;
    }
    return 0;
}
static qos_class_t thread_qos(thr_t *t) {
    return qos_utility_name(t) ? QOS_CLASS_UTILITY : prio_qos(t->prio);
}
static void qos_apply(thr_t *t) {   // on the thread itself
    qos_class_t q = thread_qos(t);
    if ((uint32_t)q != t->qos && !pthread_set_qos_class_self_np(q, 0)) t->qos = (uint32_t)q;
}"""),
    ("""    pthread_set_qos_class_self_np(prio_qos(t->prio), 0);""",
     """    pthread_set_qos_class_self_np(thread_qos(t), 0);  // NX2A_QOS_UTILITY_NAMES"""),
])

# 22. DM_NVN_LOG is a numeric setting in NGR (0 means off). Upstream used
# getenv()!=NULL, which treats the literal string "0" as enabled and floods
# logcat with per-call DeviceGetInteger messages during gameplay.
patch('NGR numeric DM_NVN_LOG switch', 'nxnative/dm/gfx/nvn/hle_nvn.c', 'NX2A_NVN_LOG_BOOL', [
    ("""    g_log = getenv("DM_NVN_LOG") != NULL;""",
     """    const char *nvn_log_env = getenv("DM_NVN_LOG");
    g_log = nvn_log_env && nvn_log_env[0] && strcmp(nvn_log_env, "0") != 0;  // NX2A_NVN_LOG_BOOL"""),
])

# 23. Apply the Metro scheduling profile after env.txt so a stale per-game
# override cannot silently restore the known CPU-starvation configuration.
patch('NGR Metro scheduler env after env.txt', 'nxnative/dm/android/front_android.c', 'NX2A_METRO_SCHEDULER_ENV', [
    ("""    const char *ngr_vk_driver_override = getenv("NGR_DM_VK_DRIVER_OVERRIDE");
    if (ngr_vk_driver_override && *ngr_vk_driver_override) {
        setenv("DM_VK_DRIVER", ngr_vk_driver_override, 1);  // NX2A_DM_VK_DRIVER_OVERRIDE
        LOG("[Vulkan] using per-launch driver override: %s", ngr_vk_driver_override);
    }
""",
     """    const char *ngr_vk_driver_override = getenv("NGR_DM_VK_DRIVER_OVERRIDE");
    if (ngr_vk_driver_override && *ngr_vk_driver_override) {
        setenv("DM_VK_DRIVER", ngr_vk_driver_override, 1);  // NX2A_DM_VK_DRIVER_OVERRIDE
        LOG("[Vulkan] using per-launch driver override: %s", ngr_vk_driver_override);
    }
    const char *ngr_game_id = getenv("NGR_GAME_ID");
    if (ngr_game_id && !strcmp(ngr_game_id, "9383b4fd4e8540ed5d6e")) {
        setenv("DM_QOS_MAP", "1", 1);
        setenv("DM_QOS_EDGES", "44,58", 1);
        setenv("DM_QOS_UTILITY_NAMES", "uEngine :: PhysX simulator;uEngine :: Secondary", 1);
        setenv("DM_YIELD_PROGRESS_LIMIT", "50000", 1);
        setenv("DM_YIELD_PROGRESS_HANDOFF", "256", 1);
        unsetenv("DM_YIELD_PROGRESS_SLEEP_US");
        LOG("[scheduler] Metro profile: PhysX/Secondary use Utility QoS with priority inheritance; progressing-yield handoff=256/256 after 50k/s");
    }  // NX2A_METRO_SCHEDULER_ENV
"""),
])

sys.exit(1 if failed else 0)


# 24. The AudioOutBuffer is the SDK's 40-byte object, not the host's former
# private 24-byte prefix. Metro 2033 Redux's resampler asks the SDK for the
# capacity; the old layout made it read data_size as capacity, so every fourth
# block could be re-appended with audio from four blocks earlier (~170 ms).
# Keep the descriptor accessors in the SDK and let the host consume its layout.
def _rewrite_audio_file(rel, marker, transform):
    global failed
    f = repo / rel
    try:
        src = f.read_text()
    except OSError as e:
        print(f'NGR AudioOutBuffer ABI: FAILED (cannot read {rel}: {e})')
        failed += 1
        return
    if marker in src or ('gbuf' not in src and 'aout_buf' in src):
        print(f'NGR AudioOutBuffer ABI {rel}: already')
        return
    try:
        dst = transform(src)
    except Exception as e:
        print(f'NGR AudioOutBuffer ABI {rel}: FAILED ({e})')
        failed += 1
        return
    if dst == src or 'gbuf' in dst:
        print(f'NGR AudioOutBuffer ABI {rel}: FAILED (old layout remains)')
        failed += 1
        return
    if marker not in dst:
        print(f'NGR AudioOutBuffer ABI {rel}: FAILED (marker missing)')
        failed += 1
        return
    f.write_text(dst)
    print(f'NGR AudioOutBuffer ABI {rel}: ok')


def _audio_output(src):
    if 'gbuf' not in src and 'aout_buf' in src:
        return src
    src = src.replace('gbuf', 'aout_buf')
    old_typedef = 'typedef struct { void *ptr; uint64_t cap, size; } aout_buf;     // The first 24 bytes written into the guest AudioOutBuffer\n'
    if src.count(old_typedef) != 1:
        raise RuntimeError('hle_audio.c old buffer typedef changed')
    src = src.replace(old_typedef, '', 1)
    old_accessors = '''HLE_FORCE("_ZN2nn5audio21SetAudioOutBufferInfoEPNS0_14AudioOutBufferEPvmm", "buffer description; written into the first 24 bytes of the guest struct", void, h_au_SetBuf, aout_buf *b, void *p, uint64_t cap, uint64_t size) {
    b->ptr = p; b->cap = cap; b->size = size;
}
HLE_FORCE("_ZN2nn5audio28GetAudioOutBufferDataPointerEPKNS0_14AudioOutBufferE", "buffer data pointer", void *, h_au_BufPtr, const aout_buf *b) { return b->ptr; }
HLE_FORCE("_ZN2nn5audio25GetAudioOutBufferDataSizeEPKNS0_14AudioOutBufferE", "buffer data size", uint64_t, h_au_BufSize, const aout_buf *b) { return b->size; }
'''
    if src.count(old_accessors) != 1:
        raise RuntimeError('hle_audio.c descriptor takeover block changed')
    comment = '''// NX2A_AUDIOOUTBUFFER_ABI: SetAudioOutBufferInfo and the AudioOutBuffer getters run in the SDK.
// The host reads the SDK's complete 40-byte aout_buf; never emulate these accessors with a private layout.
'''
    src = src.replace(old_accessors, comment, 1)
    return src.replace('#include "hle.h"', '#include "hle.h"\n// NX2A_AUDIOOUTBUFFER_ABI', 1)


def _audio_renderer(src):
    if 'gbuf' not in src and 'aout_buf' in src:
        return src
    src = src.replace('gbuf', 'aout_buf')
    old_typedef = "typedef struct { void *ptr; uint64_t cap, size; } aout_buf;       // same as the front of hle_audio.c's AudioOutBuffer\n"
    if src.count(old_typedef) != 1:
        raise RuntimeError('hle_audren.c old buffer typedef changed')
    src = src.replace(old_typedef, '', 1)
    old_init = '(aout_buf){data[i], sizeof data[i], 0}'
    if src.count(old_init) != 1:
        raise RuntimeError('hle_audren.c positional AudioOutBuffer initializer changed')
    src = src.replace(old_init, '(aout_buf){.ptr = data[i], .cap = sizeof data[i], .size = 0}', 1)
    return src.replace('#include "hle.h"', '#include "hle.h"\n// NX2A_AUDIOOUTBUFFER_ABI', 1)


def _audio_test(src):
    if 'gbuf' not in src and 'aout_buf' in src:
        return src
    src = src.replace('gbuf', 'aout_buf')
    old = 'aout_buf b[2] = {{in, SPLIT * 12, SPLIT * 12}, {in + SPLIT * 6, (FRAMES - SPLIT) * 12, (FRAMES - SPLIT) * 12}};'
    new = 'aout_buf b[2] = {{.ptr = in, .cap = SPLIT * 12, .size = SPLIT * 12}, {.ptr = in + SPLIT * 6, .cap = (FRAMES - SPLIT) * 12, .size = (FRAMES - SPLIT) * 12}};'
    if src.count(old) != 1:
        raise RuntimeError('t_audio.c positional buffer test initializer changed')
    src = src.replace(old, new, 1)
    src = src.replace('h_au_SetBuf(', 'set_buf(')
    anchor = '// Exercise the actual device callback, not just a mixing helper.'
    helper = '''// NX2A_AUDIOOUTBUFFER_ABI: test helper writes the SDK-defined fields.
static void set_buf(aout_buf *b, void *p, uint64_t cap, uint64_t size) {
    b->next = NULL; b->ptr = p; b->cap = cap; b->size = size; b->offset = 0;
}
'''
    if src.count(anchor) != 1:
        raise RuntimeError('t_audio.c helper insertion anchor changed')
    src = src.replace(anchor, helper + anchor, 1)
    return src


def _audio_spsc_test(src):
    if 'gbuf' not in src and 'aout_buf' in src:
        return src
    return src.replace('gbuf', 'aout_buf').replace('// hle_audio.c lock-free queue stress test', '// NX2A_AUDIOOUTBUFFER_ABI: hle_audio.c lock-free queue stress test', 1)


_saved_patch_only = PATCH_ONLY
PATCH_ONLY = set()
try:
    _header = (repo / 'nxnative/dm/host/hle.h').read_text()
    if 'typedef struct { void *next; void *ptr; uint64_t cap, size, offset; } aout_buf;' not in _header:
        patch('NGR AudioOutBuffer ABI declaration', 'nxnative/dm/host/hle.h', 'NX2A_AUDIOOUTBUFFER_ABI', [
            ('#include "dm.h"\n', '#include "dm.h"\n#include <stddef.h>\n'),
            ('void dm_audio_reset(void);   // iOS media services reset: recreate the AudioUnits (hle_audio.c)\n',
             '''void dm_audio_reset(void);   // iOS media services reset: recreate the AudioUnits (hle_audio.c)
// NX2A_AUDIOOUTBUFFER_ABI: nn::audio::AudioOutBuffer layout used by the SDK (SDK 8 through Switch 2).
typedef struct { void *next; void *ptr; uint64_t cap, size, offset; } aout_buf;   // next, data, buffer_size, data_size, data_offset
_Static_assert(sizeof(aout_buf) == 40 && offsetof(aout_buf, ptr) == 0x08 && offsetof(aout_buf, cap) == 0x10 && offsetof(aout_buf, size) == 0x18 && offsetof(aout_buf, offset) == 0x20,
               "nn::audio::AudioOutBuffer layout");
''')
        ])
    _rewrite_audio_file('nxnative/dm/host/hle_audio.c', 'NX2A_AUDIOOUTBUFFER_ABI', _audio_output)
    _rewrite_audio_file('nxnative/dm/host/hle_audren.c', 'NX2A_AUDIOOUTBUFFER_ABI', _audio_renderer)
    _rewrite_audio_file('nxnative/dm/host/tests/t_audio.c', 'NX2A_AUDIOOUTBUFFER_ABI', _audio_test)
    _rewrite_audio_file('nxnative/dm/host/tests/t_audio_spsc.c', 'NX2A_AUDIOOUTBUFFER_ABI', _audio_spsc_test)
finally:
    PATCH_ONLY = _saved_patch_only

# 25. Metro's PhysX and Secondary workers run a progressing YieldThread loop:
# their register changes bypass the ordinary no-progress backoff. After the
# measured 50k/s budget, sleep only these two named workers briefly; other games
# and other Metro threads retain the scheduler fast path.
patch('NGR named-worker progressing-yield backoff', 'nxnative/dm/host/hle_thread.c', 'NX2A_YIELD_NAMED_SLEEP', [
    ('''    static int limit = -1, handoff_every = 256;
    static _Thread_local uint64_t window_ns;''',
     '''    static int limit = -1, handoff_every = 256, sleep_us = -1;
    static _Thread_local int sleep_target = -1;
    static _Thread_local uint64_t window_ns;'''),
    ('''        const char *h = getenv("DM_YIELD_PROGRESS_HANDOFF");
        limit = e && *e ? atoi(e) : 0;''',
     '''        const char *h = getenv("DM_YIELD_PROGRESS_HANDOFF");
        const char *su = getenv("DM_YIELD_PROGRESS_SLEEP_US");
        sleep_us = su && *su ? atoi(su) : 0;
        if (sleep_us < 0) sleep_us = 0;
        if (sleep_us > 10000) sleep_us = 10000;
        limit = e && *e ? atoi(e) : 0;'''),
    ('''        if (limit > 0) LOG("DM_YIELD_PROGRESS_LIMIT=%d/s, host scheduler handoff every %d excess yields (no sleep while guest locks may be held)", limit, handoff_every);''',
     '''        if (limit > 0) LOG("DM_YIELD_PROGRESS_LIMIT=%d/s, handoff every %d excess yields, named-worker sleep=%d us", limit, handoff_every, sleep_us);'''),
    ('''        excess = 0;
        sched_yield();
    }
}
static void thr_yield(thr_t *me, const uint64_t *regs) {''',
     '''        excess = 0;
        if (sleep_us > 0 && me) {
            if (sleep_target < 0) {
                sleep_target = 0;
                const char *names = getenv("DM_YIELD_PROGRESS_SLEEP_NAMES");
                if (names && *names) {
                    char name[64]; const char *n = thr_name(me, name, sizeof name);
                    size_t nl = strlen(n);
                    for (const char *p = names; *p;) {
                        const char *end = strchr(p, ';');
                        size_t len = end ? (size_t)(end - p) : strlen(p);
                        if (len == nl && nl && !memcmp(p, n, len)) { sleep_target = 1; break; }
                        if (!end) break;
                        p = end + 1;
                    }
                }
            }
            if (sleep_target) {
                struct timespec ts = { sleep_us / 1000000, (long)(sleep_us % 1000000) * 1000L };
                nanosleep(&ts, NULL);
            } else sched_yield();
        } else sched_yield();
    }
}
static void thr_yield(thr_t *me, const uint64_t *regs) {''')
])

# 26. Enable the measured back-off only for Metro's two busy-wait workers.
patch('NGR Metro named-worker yield backoff env', 'nxnative/dm/android/front_android.c', 'NX2A_METRO_YIELD_SLEEP', [
    ('''        unsetenv("DM_YIELD_PROGRESS_SLEEP_US");
        LOG("[scheduler] Metro profile: PhysX/Secondary use Utility QoS with priority inheritance; progressing-yield handoff=256/256 after 50k/s");''',
     '''        setenv("DM_YIELD_PROGRESS_SLEEP_US", "100", 1);
        setenv("DM_YIELD_PROGRESS_SLEEP_NAMES", "uEngine :: PhysX simulator;uEngine :: Secondary", 1);
        LOG("[scheduler] Metro profile: PhysX/Secondary use Utility QoS plus 100us back-off after 50k progressing yields/s");  // NX2A_METRO_YIELD_SLEEP''')
])
