import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app/src/main/assets/nx2a/payload/porter_sync.py"


def load_porter_sync():
    spec = importlib.util.spec_from_file_location("ngr_porter_sync_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PorterSyncTests(unittest.TestCase):
    def test_invalid_current_main_falls_back_to_pinned_porter(self):
        module = load_porter_sync()
        with tempfile.TemporaryDirectory() as tmp:
            module.REPO = Path(tmp) / "nx2android"
            module.REPO.mkdir()
            (module.REPO / ".nx2a_sha").write_text("mainsha", encoding="utf-8")
            module._payload = lambda: {
                "porter_sha": "oldsha",
                "porter_good": "goodsha",
                "porter_track": "main",
            }
            module.mode = lambda: "newest"
            module.upstream_head = lambda: "mainsha"
            module.complete = lambda: True

            calls = []
            def patch():
                calls.append("patch")
                if calls.count("patch") == 1:
                    raise RuntimeError("main patch mismatch")
                return "verified"

            def install(sha, log, must_patch):
                calls.append(("install", sha, must_patch))
                (module.REPO / ".nx2a_sha").write_text(sha, encoding="utf-8")

            module.patch = patch
            module._install = install
            ok, message = module.sync(log=lambda _: None)

            self.assertTrue(ok, message)
            self.assertIn(("install", "goodsha", False), calls)
            self.assertEqual((module.REPO / ".nx2a_sha").read_text(), "goodsha")
            self.assertIn("installed and patched", message)

    def test_good_mode_fails_closed_when_pinned_patches_do_not_apply(self):
        module = load_porter_sync()
        with tempfile.TemporaryDirectory() as tmp:
            module.REPO = Path(tmp) / "nx2android"
            module.REPO.mkdir()
            (module.REPO / ".nx2a_sha").write_text("goodsha", encoding="utf-8")
            module._payload = lambda: {
                "porter_sha": "oldsha",
                "porter_good": "goodsha",
                "porter_track": "main",
            }
            module.mode = lambda: "good"
            module.complete = lambda: True
            module.patch = lambda: (_ for _ in ()).throw(RuntimeError("patch mismatch"))

            ok, message = module.sync(log=lambda _: None)
            self.assertFalse(ok)
            self.assertIn("patch validation failed", message)


if __name__ == "__main__":
    unittest.main()
