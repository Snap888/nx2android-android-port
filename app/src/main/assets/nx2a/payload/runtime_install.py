#!/usr/bin/env python3
"""Copy a game payload into NGR's own app-specific external files directory (no ADB or per-game APK)."""
import argparse
import shutil
import sys
from pathlib import Path

APP_PACKAGE = "unknown.none.nx2android"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--game-id", required=True)
    ap.add_argument("--package", default=APP_PACKAGE)
    a = ap.parse_args()
    if len(a.game_id) != 20 or any(c not in "0123456789abcdef" for c in a.game_id):
        raise SystemExit("invalid NGR game ID")
    source = Path(a.data).resolve()
    if not source.is_dir() or not (source / "nx2a-data.json").is_file():
        raise SystemExit(f"not a completed nx2android data pack: {source}")
    if not (source / "libdmhost.so").is_file():
        raise SystemExit("libdmhost.so is missing; recompile this game with the NGR runtime build")

    # Proot runs under the NGR app UID. Android permits it to write its own
    # Android/data/<package>/files directory, so no wireless debugging is needed.
    root = Path("/sdcard/Android/data") / a.package / "files" / "games"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / a.game_id
    staging = root / (a.game_id + ".staging")
    backup = root / (a.game_id + ".previous")
    for stale in (staging, backup):
        if stale.exists():
            shutil.rmtree(stale)
    print(f"[NGR runtime] copying game payload from {source}", flush=True)
    shutil.copytree(source, staging, copy_function=shutil.copy2, symlinks=False)
    if not (staging / "libdmhost.so").is_file() or not (staging / "nx2a-data.json").is_file():
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError("staged payload verification failed")
    count = sum(1 for p in staging.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in staging.rglob("*") if p.is_file())
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
    print(f"[NGR runtime] installed {count} files ({size / (1024 ** 3):.2f} GiB)", flush=True)
    print(f"[NGR runtime] game directory: {destination}", flush=True)
    print("[NGR runtime] native libraries will be copied to private executable storage when launched", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[NGR runtime] ERROR: {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
