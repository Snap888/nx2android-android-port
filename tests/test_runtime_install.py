import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "app/src/main/assets/nx2a/payload/runtime_install.py"
SPEC = importlib.util.spec_from_file_location("ngr_runtime_install", MODULE)
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class RuntimeInstallTests(unittest.TestCase):
    def make_payload(self, root, marker=True, library=True, game_id="0123456789abcdefabcd"):
        source = root / "source"
        source.mkdir()
        if marker:
            (source / "nx2a-data.json").write_text(
                '{"schema":1,"game_id":"' + game_id + '"}', encoding="utf-8")
        if library:
            (source / "libdmhost.so").write_bytes(b"ELF-runtime-test".ljust(128, b"\\0"))
        (source / "RomFS").mkdir()
        (source / "RomFS" / "game.bin").write_text("game-data", encoding="utf-8")
        return source

    def test_validates_payload_in_place_without_creating_android_data_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_payload(root)
            result = RUNTIME.validate_payload(source, "0123456789abcdefabcd")
            self.assertEqual(result["path"], str(source.resolve()))
            self.assertTrue((source / "libdmhost.so").is_file())
            self.assertTrue((source / "RomFS/game.bin").is_file())
            self.assertFalse((root / "Android/data/unknown.none.nx2android/files/games").exists())

    def test_reuses_existing_payload_and_reports_current_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_payload(root)
            result1 = RUNTIME.validate_payload(source, "0123456789abcdefabcd")
            (source / "RomFS/game.bin").write_text("updated", encoding="utf-8")
            result2 = RUNTIME.validate_payload(source, "0123456789abcdefabcd")
            self.assertEqual(result1["path"], result2["path"])
            self.assertGreater(result2["bytes"], result1["bytes"])

    def test_rejects_incomplete_data_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_payload(root, library=False)
            with self.assertRaisesRegex(ValueError, "libdmhost.so"):
                RUNTIME.validate_payload(source, "0123456789abcdefabcd")

    def test_rejects_wrong_game_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_payload(root, game_id="aaaaaaaaaaaaaaaaaaaa")
            with self.assertRaisesRegex(ValueError, "belongs to game"):
                RUNTIME.validate_payload(source, "0123456789abcdefabcd")

    def test_rejects_invalid_game_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_payload(root)
            with self.assertRaisesRegex(ValueError, "game ID"):
                RUNTIME.validate_payload(source, "../bad")

    def test_rejects_symbolic_links_in_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_payload(root)
            outside = root / "outside.bin"
            outside.write_text("outside", encoding="utf-8")
            target = source / "RomFS" / "link.bin"
            target.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                RUNTIME.validate_payload(source, "0123456789abcdefabcd")


if __name__ == "__main__":
    unittest.main()
