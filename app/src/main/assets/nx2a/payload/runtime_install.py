#!/usr/bin/env python3
"""Install one port payload into NGR-owned storage. No ADB and no per-game APK."""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

APP_PACKAGE = "unknown.none.nx2android"


def validate_game_id(game_id):
    return len(game_id) == 20 and all(c in "0123456789abcdef" for c in game_id)


def install_payload(source, games_root, game_id):
    """Transactional install; games_root is .../Android/data/<NGR package>/files/games."""
    if not validate_game_id(game_id):
        raise ValueError("invalid NGR game ID")
    source = Path(source).resolve(strict=True)
    games_root = Path(games_root)
    if not source.is_dir() or not (source / "nx2a-data.json").is_file():
        raise ValueError(f"not a completed nx2android data pack: {source}")
    manifest = json.loads((source / "nx2a-data.json").read_text(encoding="utf-8"))
    packed_game_id = manifest.get("game_id")
    if packed_game_id and packed_game_id != game_id:
        raise ValueError(f"data pack belongs to game {packed_game_id}, not selected library entry {game_id}")
    if not (source / "libdmhost.so").is_file():
        raise ValueError("libdmhost.so is missing; recompile this game with the NGR runtime build")

    games_root.mkdir(parents=True, exist_ok=True)
    destination = games_root / game_id
    staging = games_root / (game_id + ".staging")
    backup = games_root / (game_id + ".previous")

    # Recover a previous version if the process was killed between the two renames.
    if backup.exists():
        if not destination.exists():
            backup.rename(destination)
        else:
            shutil.rmtree(backup)
    if staging.exists():
        shutil.rmtree(staging)

    try:
        print(f"[NGR runtime] copying game payload from {source}", flush=True)
        shutil.copytree(source, staging, copy_function=shutil.copy2, symlinks=False)
        if not (staging / "libdmhost.so").is_file() or not (staging / "nx2a-data.json").is_file():
            raise RuntimeError("staged payload verification failed")

        files = [p for p in staging.rglob("*") if p.is_file()]
        size = sum(p.stat().st_size for p in files)
        if destination.exists():
            destination.rename(backup)
        try:
            staging.rename(destination)
        except Exception:
            if backup.exists() and not destination.exists():
                backup.rename(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        result = {"files": len(files), "bytes": size, "path": str(destination)}
        print(f"[NGR runtime] installed {result['files']} files ({size / (1024 ** 3):.2f} GiB)", flush=True)
        print(f"[NGR runtime] game directory: {destination}", flush=True)
        print("[NGR runtime] native libraries will be copied to private executable storage when launched", flush=True)
        return result
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if backup.exists() and not destination.exists():
            backup.rename(destination)
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--game-id", required=True)
    ap.add_argument("--package", default=APP_PACKAGE)
    a = ap.parse_args()
    if len(a.package) > 255 or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+", a.package):
        raise SystemExit("invalid Android package name")
    games_root = Path("/sdcard/Android/data") / a.package / "files" / "games"
    install_payload(a.data, games_root, a.game_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[NGR runtime] ERROR: {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
