#!/usr/bin/env python3
"""Validate an NGR game payload in place; never duplicate the game data into Android/data."""
import argparse
import json
import re
import sys
from pathlib import Path

APP_PACKAGE = "unknown.none.nx2android"


def validate_game_id(game_id):
    return len(game_id) == 20 and all(c in "0123456789abcdef" for c in game_id)


def validate_payload(source, game_id):
    """Validate the existing payload in its current NGR-owned storage location."""
    if not validate_game_id(game_id):
        raise ValueError("invalid NGR game ID")
    source = Path(source).resolve(strict=True)
    if not source.is_dir() or not (source / "nx2a-data.json").is_file():
        raise ValueError(f"not a completed nx2android data pack: {source}")
    manifest = json.loads((source / "nx2a-data.json").read_text(encoding="utf-8"))
    packed_game_id = manifest.get("game_id")
    if packed_game_id and packed_game_id != game_id:
        raise ValueError(f"data pack belongs to game {packed_game_id}, not selected library entry {game_id}")
    runtime = source / "libdmhost.so"
    if not runtime.is_file() or runtime.stat().st_size < 64:
        raise ValueError("libdmhost.so is missing or empty; recompile this game with the NGR runtime build")

    files = []
    size = 0
    for path in source.rglob("*"):
        if path.is_symlink():
            target = path.resolve(strict=True)
            if not target.is_relative_to(source):
                raise ValueError(f"game data pack contains a symbolic link outside its root: {path}")
            continue
        if path.is_file():
            files.append(path)
            size += path.stat().st_size
    result = {"files": len(files), "bytes": size, "path": str(source)}
    print(f"[NGR runtime] verified {result['files']} files ({size / (1024 ** 3):.2f} GiB) in place", flush=True)
    print(f"[NGR runtime] game data remains at: {source}", flush=True)
    print("[NGR runtime] no game data was copied to Android/data", flush=True)
    print("[NGR runtime] only executable native libraries are staged privately by the native host", flush=True)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--game-id", required=True)
    ap.add_argument("--package", default=APP_PACKAGE)  # retained for old callers
    a = ap.parse_args()
    if len(a.package) > 255 or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+", a.package):
        raise SystemExit("invalid Android package name")
    validate_payload(a.data, a.game_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[NGR runtime] ERROR: {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
