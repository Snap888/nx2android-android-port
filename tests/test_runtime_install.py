import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "app/src/main/assets/nx2a/payload/runtime_install.py"
SPEC = importlib.util.spec_from_file_location("ngr_runtime_install", MODULE)
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class RuntimeInstallTests(unittest.TestCase):
    def make_payload(self, root, marker=True, library=True, extra="v1"):
        source = root / "source"
        source.mkdir()
        if marker:
            (source / "nx2a-data.json").write_text('{"schema":1}')
        if library:
            (source / "libdmhost.so").write_bytes(b"ELF-runtime-" + extra.encode())
        (source / "RomFS").mkdir()
        (source / "RomFS" / "game.bin").write_text(extra)
        return source

    def test_installs_payload_into_single_app_game_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_payload(root)
            games = root / "Android/data/unknown.none.nx2android/files/games"
            result = RUNTIME.install_payload(source, games, "0123456789abcdefabcd")
            installed = games / "0123456789abcdefabcd"
            self.assertTrue((installed / "nx2a-data.json").is_file())
            self.assertTrue((installed / "libdmhost.so").is_file())
            self.assertEqual((installed / "RomFS/game.bin").read_text(), "v1")
            self.assertEqual(result["path"], str(installed))
            self.assertFalse((games / "0123456789abcdefabcd.staging").exists())
            self.assertFalse((games / "0123456789abcdefabcd.previous").exists())

    def test_replaces_existing_payload_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            games = root / "games"
            source = self.make_payload(root)
            game_id = "0123456789abcdefabcd"
            RUNTIME.install_payload(source, games, game_id)
            (source / "RomFS/game.bin").write_text("v2")
            RUNTIME.install_payload(source, games, game_id)
            self.assertEqual((games / game_id / "RomFS/game.bin").read_text(), "v2")
            self.assertFalse((games / (game_id + ".previous")).exists())

    def test_recovers_backup_left_by_interrupted_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            games = root / "games"
            game_id = "0123456789abcdefabcd"
            backup = games / (game_id + ".previous")
            backup.mkdir(parents=True)
            (backup / "old.txt").write_text("recoverable")
            source = self.make_payload(root)
            RUNTIME.install_payload(source, games, game_id)
            self.assertTrue((games / game_id / "libdmhost.so").is_file())
            self.assertFalse(backup.exists())

    def test_rejects_incomplete_data_pack_before_creating_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_payload(root, library=False)
            games = root / "games"
            with self.assertRaisesRegex(ValueError, "libdmhost.so"):
                RUNTIME.install_payload(source, games, "0123456789abcdefabcd")
            self.assertFalse(games.exists())

    def test_rejects_invalid_game_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_payload(root)
            with self.assertRaisesRegex(ValueError, "game ID"):
                RUNTIME.install_payload(source, root / "games", "../bad")


if __name__ == "__main__":
    unittest.main()
