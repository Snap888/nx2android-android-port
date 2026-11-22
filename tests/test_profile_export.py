import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "app/src/main/assets/nx2a/payload/profile_export.py"
SPEC = importlib.util.spec_from_file_location("ngr_profile_export", MODULE)
EXPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORTER)


class ProfileExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.dm = self.repo / "nxnative/dm"
        self.game_id = "0100000000001000"
        self.profile = self.dm / "games" / self.game_id
        self.profile.mkdir(parents=True)
        (self.profile / "game.tsv").write_text("name\\tTest Game\\n")
        (self.profile / "android.tsv").write_text("status\\tplayable\\n")
        (self.data = self.root / "game-data").mkdir()
        self.header = b"// deterministic generated game profile header\\n"
        self.android_header = b"// deterministic generated android profile header\\n"
        self.modules = self.root / "modules"
        self.modules.mkdir()
        (self.dm / "games").mkdir(parents=True, exist_ok=True)
        (self.dm / "android/tools").mkdir(parents=True)
        (self.dm / "games/game.py").write_text(
            "class FakeGame:\\n"
            "    def __init__(self, path):\\n"
            "        from pathlib import Path\\n"
            "        self.dir=Path(path); self.id=self.dir.name; self.rows=[('name',['Test Game']),('modules',['main','sdk'])]; self.title_id=int(self.id,16)\\n"
            "    def get(self,k,d=None): return {'name':'Test Game','program_id':'0100000000001000'}.get(k,d)\\n"
            "    def words(self,k,d=None): return ['main','sdk'] if k=='modules' else (d or '').split()\\n"
            "    def builds(self): return {'v1':{'main':'0123456789abcdef0123456789abcdef','display':'1.0'}}\\n"
            "def load(path): return FakeGame(path)\\n"
            f"def header(g): return {self.header!r}\\n"
            "BUILD_TABLES={'fps_locks.tsv':None}\\n"
            "def build_table(g,n): return [['0123456789abcdef0123456789abcdef','main','0x10']]\\n"
        )
        (self.dm / "android/tools/android_profile.py").write_text(
            "class FakeAndroid:\\n"
            "    def __init__(self,g):\\n"
            "        self.rows=[('status','playable')]; self.status='playable'; self.tested='device'; self.package='org.test.game'; self.landscape=True; self.requires=[]; self.sysdata=[]; self.romfs_zstd=False; self.vulkan_driver='system'; self.pacing='adaptive'; self.env=[]; self.settings={'overlay':'1'}\\n"
            "    def overlay_table(self): return [{'layout':'tablet','name':'menu','kind':'menu','x':'0.5','y':'0.5'}]\\n"
            "def AndroidProfile(g): return FakeAndroid(g)\\n"
            f"def header(p): return {self.android_header!r}\\n"
        )
        (self.data / "nx2a-data.json").write_text(json.dumps({
            "title_id": self.game_id,
            "package": "org.test.game",
            "version": "v1",
            "display": "1.0",
            "language": "en-US",
            "profile_h": hashlib.sha256(self.header).hexdigest()
        }))
        sys.modules.pop("game", None)
        sys.modules.pop("android_profile", None)

    def tearDown(self):
        sys.modules.pop("game", None)
        sys.modules.pop("android_profile", None)
        self.tmp.cleanup()

    def test_exports_exact_compiled_profile_and_android_layout(self):
        target, size, digest = EXPORTER.export_profile(self.repo, self.game_id, self.data)
        payload = json.loads(target.read_text())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["identity"]["package"], "org.test.game")
        self.assertEqual(payload["game"]["modules"], ["main", "sdk"])
        self.assertEqual(payload["game"]["tables"]["fps_locks.tsv"][0][1], "main")
        self.assertEqual(payload["android"]["overlay"][0]["name"], "menu")
        self.assertEqual(payload["source"]["game_profile_sha256"], hashlib.sha256(self.header).hexdigest())
        self.assertEqual(digest, payload["source"]["game_profile_sha256"])
        self.assertEqual(size, target.stat().st_size)

    def test_rejects_profile_that_does_not_match_compiled_header_hash(self):
        manifest = json.loads((self.data / "nx2a-data.json").read_text())
        manifest["profile_h"] = "0" * 64
        (self.data / "nx2a-data.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "no profile candidate matched"):
            EXPORTER.export_profile(self.repo, self.game_id, self.data)

    def test_rejects_data_pack_without_profile_hash(self):
        manifest = json.loads((self.data / "nx2a-data.json").read_text())
        manifest.pop("profile_h")
        (self.data / "nx2a-data.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "no profile_h"):
            EXPORTER.export_profile(self.repo, self.game_id, self.data)


if __name__ == "__main__":
    unittest.main()
