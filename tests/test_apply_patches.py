import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "app/src/main/assets/nx2a/payload/apply_patches.py"


class ApplyPatchesTests(unittest.TestCase):
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
            self.assertIn("status\texperimental", (profile / "android.tsv").read_text(encoding="utf-8"))

            second = subprocess.run(
                [sys.executable, str(PATCHER), tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("NGR Twelve Minutes profile: already", second.stdout)


if __name__ == "__main__":
    unittest.main()
