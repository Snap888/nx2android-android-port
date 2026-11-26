import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "app/src/main/assets/nx2a/payload/apply_patches.py"


class ApplyPatchesTests(unittest.TestCase):
    def test_two_signature_yield_wait_patch_is_applied_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "nxnative/dm/host/hle_thread.c"
            source.parent.mkdir(parents=True)
            source.write_text(
                "uint64_t yrun_svc, yrun_t0, yrun_sig;     // Current run of yields: nsvc of the last yield, when the run began, and the caller's x19–x28 at the last yield (a run lasts while no other SVC comes between two yields and those registers stay the same, thr_yield)\\n"
                "static void thr_yield(thr_t *me, const uint64_t *regs) {\\n"
                "    int moved = me->yrun_svc + 1 == me->nsvc && me->yrun_sig != sig;   // the loop moved on since its last yield\\n"
                "    me->yrun_svc = me->nsvc; me->yrun_sig = sig;\\n"
                "}\\n",
                encoding="utf-8",
            )
            env = dict(os.environ, NX2A_PATCH_ONLY="NGR two-signature yield wait detection")
            first = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            patched = source.read_text(encoding="utf-8")
            self.assertIn("NX2A_YIELD_TWO_SIG", patched)
            self.assertIn("me->yrun_sig2 != sig", patched)
            self.assertIn("me->yrun_sig2 = me->yrun_sig", patched)

            second = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("already", second.stdout)

    def test_condition_variable_trace_patch_is_applied_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "nxnative/dm/host/hle_thread.c"
            source.parent.mkdir(parents=True)
            source.write_text(
                "static void wake(thr_t *t, int64_t res) {\n"
                "    wait_unlink(t);\n"
                "}\n"
                "static int64_t block(thr_t *t, int kind, int64_t ns) {\n"
                "    t->wkind = kind;\n"
                "}\n"
                "void signal_waiters(uint64_t key, int cnt, int n) {\n"
                "        for (thr_t *w; (cnt <= 0 || n < cnt) && (w = pick(2, key)); n++) lock_acquire_for(w, w->waddr, w->wtag);   // In kernel order; once turned into a lock wait or woken it is no longer kind 2\n"
                "}\n",
                encoding="utf-8",
            )
            env = dict(os.environ, NX2A_PATCH_ONLY="NGR condition-variable wait/wake trace")
            first = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            patched = source.read_text(encoding="utf-8")
            for marker in (
                "NX2A_SYNC_WAIT_TRACE",
                "[NGR_SYNC_WAIT] register",
                "[NGR_SYNC_WAIT] delivered",
                "[NGR_SYNC_WAIT] signal-target",
            ):
                self.assertIn(marker, patched)

            second = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("already", second.stdout)


    def test_twelve_minutes_offline_presence_patch_and_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "nxnative/dm/host/hle_friends.c"
            source.parent.mkdir(parents=True)
            source.write_text(
                "// Presence\n"
                "HLE_FORCE(\"_ZN2nn7friends12UserPresence10InitializeERKNS_7account3UidE\", \"presence unavailable (cut)\", Result, h_fr_UpInit, void *self, const void *uid) { (void)self; (void)uid; return RES_FAIL; }\n"
                "HLE_FORCE(\"_ZN2nn7friends12UserPresence14SetDescriptionEPKc\", \"presence unavailable (cut)\", Result, h_fr_UpDesc, void *self, const char *s) { (void)self; (void)s; return RES_FAIL; }\n"
                "HLE_FORCE(\"_ZN2nn7friends12UserPresence6CommitEv\", \"presence unavailable (cut)\", Result, h_fr_UpCommit, void *self) { (void)self; return RES_FAIL; }\n",
                encoding="utf-8",
            )
            env = dict(
                os.environ,
                NX2A_PATCH_ONLY="NGR offline UserPresence;NGR Twelve Minutes profile",
            )
            first = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

            patched = source.read_text(encoding="utf-8")
            self.assertIn("NX2A_FRIENDS_OFFLINE_PRESENCE", patched)
            self.assertIn("UserPresence10InitializeEv", patched)
            self.assertEqual(patched.count("return RES_OK;"), 4)
            self.assertNotIn("presence unavailable (cut)", patched)

            profile = Path(tmp) / "nxnative/dm/games/0100CD701434C000"
            game = (profile / "game.tsv").read_text(encoding="utf-8")
            self.assertIn("main=e93717eabaa393489060fcbf8f086ca3", game)
            self.assertIn("sdk=56ec24747ec9e7f19b3efb062483a19d", game)
            self.assertIn("mem_reserve\t0x160000000", game)
            self.assertIn("mem_alias\t0x138000000", game)
            self.assertIn("app_pool\t0xCD500000", game)
            self.assertIn("shader_groups\t/Data/=data", game)
            self.assertIn("depth_mode\tzero", game)
            android = (profile / "android.tsv").read_text(encoding="utf-8")
            self.assertIn("status\texperimental", android)
            self.assertIn("package\tunknown.none.nx2android", android)
            self.assertIn("orientation\tlandscape", android)

            second = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("NGR Twelve Minutes profile: already", second.stdout)



    def test_legacy_porter_ui_font_helper_is_added_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = Path(tmp) / "porter/pipeline.py"
            pipeline.parent.mkdir(parents=True)
            pipeline.write_text(
                "from pathlib import Path\n"
                "from porter.paths import DM, NXNATIVE\n",
                encoding="utf-8",
            )
            env = dict(os.environ, NX2A_PATCH_ONLY="NGR UI font assets")
            first = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            patched = pipeline.read_text(encoding="utf-8")
            self.assertIn("NX2A_UI_FONT_ASSETS", patched)
            self.assertIn("def ui_font_assets():", patched)
            compile(patched, str(pipeline), "exec")

            second = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("implementation present", second.stdout)

    def test_newer_upstream_ui_font_helper_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = Path(tmp) / "porter/pipeline.py"
            pipeline.parent.mkdir(parents=True)
            original = (
                "from pathlib import Path\n"
                "from porter.paths import DM, NXNATIVE\n"
                "UI_FONT = DM / 'font.nxpf'\n"
                "def ui_font_assets():\n"
                "    return {'font/ui.bin': UI_FONT}\n"
            )
            pipeline.write_text(original, encoding="utf-8")
            env = dict(os.environ, NX2A_PATCH_ONLY="NGR UI font assets")
            result = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(pipeline.read_text(encoding="utf-8"), original)



    def test_cpu_decoded_bc_first_use_upload_patch_is_applied_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "nxnative/dm/android/gfx_vk_tex.c"
            source.parent.mkdir(parents=True)
            source.write_text(
                "static int cpu_content_tex(const tex_t *t, const vkfmt_t *f) {\\n"
                "    static int on = -1; if (on < 0) { const char *e = getenv(\\\"DM_NVN_STORAGE_FIRST_USE\\\"); on = !e || atoi(e) != 0; }\\n"
                "    if (!on || !t->pool || t->has_layout || !(f->compressed || t->d.target == 2) || t->d.samples > 1) return 0;\\n"
                "    if (t->pool->flags & NVN_MEMORY_POOL_FLAGS_VIRTUAL) return 0;\\n"
                "    if (t->d.flags & (NVN_TEXTURE_FLAGS_IMAGE | NVN_TEXTURE_FLAGS_COMPRESSIBLE | NVN_TEXTURE_FLAGS_LINEAR | NVN_TEXTURE_FLAGS_LINEAR_RENDER_TARGET | NVN_TEXTURE_FLAGS_SPARSE)) return 0;\\n"
                "}\\n",
                encoding="utf-8",
            )
            env = dict(os.environ, NX2A_PATCH_ONLY="NGR CPU-decoded BC texture first-use upload")
            first = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            patched = source.read_text(encoding="utf-8")
            self.assertIn("NX2A_CPU_DECODED_BC_FIRST_USE", patched)
            self.assertIn("int guest_comp = f->compressed || f->dec;", patched)
            self.assertIn("!(guest_comp || t->d.target == 2)", patched)
            self.assertIn("(guest_comp ? 0 : (NVN_TEXTURE_FLAGS_IMAGE | NVN_TEXTURE_FLAGS_COMPRESSIBLE))", patched)

            second = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("already", second.stdout)

if __name__ == "__main__":
    unittest.main()
