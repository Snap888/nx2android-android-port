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



    def test_bounded_texture_first_use_and_descriptor_trace_is_applied_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tex = Path(tmp) / "nxnative/dm/android/gfx_vk_tex.c"
            exe = Path(tmp) / "nxnative/dm/android/gfx_vk_exec.c"
            tex.parent.mkdir(parents=True, exist_ok=True)
            exe.parent.mkdir(parents=True, exist_ok=True)
            tex.write_text(
                "    int nvn_ft_written(const tex_t *);\n"
                "    if (t->mem && lin_copy(im, t, f)) {}\n"
                "    else if (t->mem && (packaged_tex(t) || (first && (nvn_ft_written(t) || cpu_content_tex(t, f))))) {\n",
                encoding="utf-8",
            )
            exe.write_text(
                "    int num = 0;\n"
                "    if (tid && g_var_now != 3 && vk_tex_by_id(tid, &v, &t) && t) {\n"
                "        vkimg_t *im = NULL; ii->imageView = vk_tex_view(t, v, b->dim, b->flags & 1, 0, &im); if (storage && im) im->gpu_w = 1;\n"
                "    }\n"
                "    if (num && !storage) ii->sampler = samp_for(st, b, h, 1);\n"
                "    if (!ii->imageView) {\n",
                encoding="utf-8",
            )
            env = dict(
                os.environ,
                NX2A_PATCH_ONLY="NGR bounded texture first-use trace;NGR bounded texture descriptor trace",
            )
            first = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            patched_tex = tex.read_text(encoding="utf-8")
            patched_exec = exe.read_text(encoding="utf-8")
            self.assertIn("NX2A_TEX_FIRST_TRACE", patched_tex)
            self.assertIn("[tex-first]", patched_tex)
            self.assertIn("source=%s", patched_tex)
            self.assertIn("NX2A_TEX_BIND_TRACE", patched_exec)
            self.assertIn("[tex-bind]", patched_exec)
            self.assertIn("[tex-bind-miss]", patched_exec)
            self.assertIn("DM_VK_TEX_TRACE", patched_exec)

            second = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("already", second.stdout)


    def test_msaa_alias_sync_patch_is_applied_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = Path(tmp) / "nxnative/dm/android/gfx_vk.h"
            tex = Path(tmp) / "nxnative/dm/android/gfx_vk_tex.c"
            header.parent.mkdir(parents=True)
            tex.parent.mkdir(parents=True)
            header.write_text(
                "    uint64_t wseq, rseen;             // when it was last rendered to (gfx_vk_tex.c g_wseq); the newest overlapping write already reported\n",
                encoding="utf-8",
            )
            tex.write_text(
                """static void alias_check(vkimg_t *im) {   // im is about to be sampled
    static int trace = -1, n;
    if (trace < 0) { const char *e = getenv("DM_VK_ALIAS_TRACE"); trace = e && atoi(e) > 0; }
    for (int i = 0; i < im->novl; i++) {
        vkimg_t *o = im->ovl[i]; if (o->wseq <= im->wseq || o->wseq <= im->rseen) continue;
        im->rseen = o->wseq;
        if (trace && n++ < 16) VKLOG("[alias] stale read: %ux%u fmt %#x samples %u target %u flags %#x levels %u at %+lld..%+lld sampled; %ux%u fmt %#x samples %u target %u flags %#x levels %u at %+lld..%+lld rendered later",
            im->w, im->h, im->nvn_format, im->samples, im->target, im->flags, im->levels, (long long)im->off, (long long)(im->off + im->size),
            o->w, o->h, o->nvn_format, o->samples, o->target, o->flags, o->levels, (long long)o->off, (long long)(o->off + o->size));
    }
} // NX2A_ALIAS_TRACE_METADATA
static void img_drop(vkimg_t *im) { vk_lrz_forget(im); if (im->lin_mem) nvn_dirty_release(im->lin_mem, im->lin_len); if (im->packaged && !im->pkg_released && im->pkg_mem) nvn_dirty_release(im->pkg_mem, im->pkg_len); g_img_n--; g_img_bytes -= im->size > 0 ? (uint64_t)im->size : 0; alias_unlink(im); vk_tex_view_drop_all(im); if (im->sub) vk_defer_free_image_sub(im->img, im->sub); else vk_defer_free_image(im->img, im->mem); free(im); }
""",
                encoding="utf-8",
            )
            env = dict(os.environ, NX2A_PATCH_ONLY="NGR resolve 4x MSAA texture aliases before sampling")
            first = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            patched_header = header.read_text(encoding="utf-8")
            patched_tex = tex.read_text(encoding="utf-8")
            for marker in (
                "NX2A_ALIAS_MSAA_RESOLVE",
                "NX2A_ALIAS_TRACE_METADATA",
                "alias_resolve_tmp",
                "alias_sync_msaa_upscale",
                "vkCmdResolveImage",
                "vkCmdBlitImage",
                "VK_FORMAT_R8G8B8A8_SRGB",
                "src->w * 2 != im->w",
            ):
                self.assertIn(marker, patched_header + patched_tex)
            self.assertIn("alias_resolve_tmp_drop(im)", patched_tex)

            second = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("already", second.stdout)

    def test_alias_trace_enables_bounded_texture_binding_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "nxnative/dm/android/gfx_vk_exec.c"
            exe.parent.mkdir(parents=True)
            exe.write_text(
                'static int ngr_tex_trace = -1; /* NX2A_TEX_BIND_TRACE: bounded descriptor trace */ if (ngr_tex_trace < 0) { const char *e = getenv("DM_VK_TEX_TRACE"); ngr_tex_trace = e && atoi(e) != 0; }',
                encoding="utf-8",
            )
            env = dict(os.environ, NX2A_PATCH_ONLY="NGR enable bounded texture trace with alias trace")
            first = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            patched = exe.read_text(encoding="utf-8")
            self.assertIn("DM_VK_ALIAS_TRACE", patched)
            self.assertIn('setenv("DM_VK_TEX_TRACE", "1", 0)', patched)
            self.assertIn("NX2A_ALIAS_AUTO_TEX_TRACE", patched)

            second = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("already", second.stdout)


if __name__ == "__main__":
    unittest.main()
