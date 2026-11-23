#!/usr/bin/env python3
"""Patches a nx2android checkout for an aarch64 phone. Idempotent; each patch reports ok / already / FAILED (upstream text changed)."""
import sys
from pathlib import Path

repo = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
failed = 0


def patch(name, rel, marker, edits):
    global failed
    f = repo / rel
    try: s = f.read_text()
    except OSError as e: print(f'{name}: FAILED (cannot read {rel}: {e})'); failed += 1; return
    if marker in s: print(f'{name}: already'); return
    for old, new in edits:
        if s.count(old) != 1: print(f'{name}: FAILED (upstream changed: {old[:50]!r})'); failed += 1; return
        s = s.replace(old, new)
    f.write_text(s); print(f'{name}: ok')


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
("""        man = datapack.build(dst, profile=self.ap, version=self.pkg_ver, display=self.display, patched=self.patched, romfs=romfs, shaders=self.dmsv,
""", """        pack_files = {**self.fps_files, **font_files, **self.ngr_runtime_files()}
        man = datapack.build(dst, profile=self.ap, version=self.pkg_ver, display=self.display, patched=self.patched, romfs=romfs, shaders=self.dmsv,
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
("static const char *const OVM_LABELS[OVM_N] = {\"Show gamepad\", \"Opacity\", \"Edit layout\", \"Rumble\", \"Show FPS\", \"Mode\", \"Export save\", \"Import save\", \"Resume\", \"\"};",
 "static const char *const OVM_LABELS[OVM_N] = {\"Show gamepad\", \"Opacity\", \"Edit layout\", \"Rumble\", \"Show FPS\", \"Mode\", \"Export save\", \"Import save\", \"Resume\", \"Exit game\", \"\"};"),
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
("""    if profile_h: man['profile_h'] = profile_h
""", """    if profile_h: man['profile_h'] = profile_h
    if os.environ.get('NX2A_GAME_ID'): man['game_id'] = os.environ['NX2A_GAME_ID']
"""),
])

# 11. Keep the exact profile header hash in the data-pack manifest. The NGR exporter
# uses it to select the same game / Android profile that produced libdmhost.so.
patch('NGR profile hash manifest', 'porter/datapack.py', 'NX2A_PROFILE_HASH', [
("""def build(dst, *, profile, version, display, patched, romfs, shaders, aoc=None, sysdata=None, language='en-US', package=None, env=(), settings=None, files=None, progress=None):
""", """def build(dst, *, profile, version, display, patched, romfs, shaders, aoc=None, sysdata=None, language='en-US', package=None, env=(), settings=None, files=None, profile_h=None, progress=None):  # NX2A_PROFILE_HASH
"""),
("""    man = dict(title_id=profile.id, name=profile.name, package=package, version=version, display=display, language=language, requires=profile.requires,
""", """    man = dict(title_id=profile.id, name=profile.name, package=package, version=version, display=display, language=language, requires=profile.requires, profile_h=profile_h,
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

# All patch groups must run before reporting failures.
sys.exit(1 if failed else 0)
