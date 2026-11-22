#!/usr/bin/env python3
"""Export the exact compiled game/Android profiles as a versioned NGR runtime document.

The JSON is an intermediate ABI artifact. It does not replace the current profile
headers yet; profile_h is checked so a derived/provisional build cannot silently
receive the wrong profile document.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def profile_candidates(repo, source_folder, game_id):
    dm = Path(repo) / "nxnative" / "dm"
    roots = [dm / "games"]
    if source_folder:
        work = Path(source_folder).expanduser() / (game_id + "_build")
        roots.extend(work / name for name in ("profile", "profile-derived", "profile-mem"))
    for value in os.environ.get("DM_GAMES_DIR", "").split(os.pathsep):
        if value:
            roots.append(Path(value))
    seen = set()
    for root in roots:
        candidate = (root / game_id).resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "game.tsv").is_file():
            yield candidate


def export_profile(repo, game_id, data_dir, source_folder=""):
    repo = Path(repo).resolve()
    data_dir = Path(data_dir).resolve()
    manifest_path = data_dir / "nx2a-data.json"
    if not manifest_path.is_file():
        raise ValueError(f"game data manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if str(manifest.get("title_id", "")).lower() != game_id.lower():
        raise ValueError("selected profile ID does not match the game data manifest")
    expected_hash = manifest.get("profile_h")
    if not expected_hash:
        raise ValueError("nx2a-data.json has no profile_h; this build cannot be mapped safely to a runtime profile")

    dm = repo / "nxnative" / "dm"
    sys.path.insert(0, str(dm / "games"))
    sys.path.insert(0, str(dm / "android" / "tools"))
    import game
    import android_profile

    selected = None
    game_header = android_header = None
    for candidate in profile_candidates(repo, source_folder, game_id):
        try:
            g = game.load(str(candidate))
            header = game.header(g).encode("utf-8")
            if hashlib.sha256(header).hexdigest() != expected_hash:
                continue
            apath = candidate / "android.tsv"
            ap = android_profile.AndroidProfile(g) if apath.is_file() else None
            aheader = android_profile.header(ap).encode("utf-8")
            selected, game_header, android_header = (g, ap), header, aheader
            break
        except Exception:
            continue
    if selected is None:
        raise ValueError(f"no profile candidate matched compiled profile_h {expected_hash[:12]} for {game_id}")

    g, ap = selected
    tables = {}
    if hasattr(game, "BUILD_TABLES") and hasattr(game, "build_table"):
        for filename in game.BUILD_TABLES:
            tables[filename] = game.build_table(g, filename)

    android = None
    if ap is not None:
        android = {
            "rows": [{"key": k, "value": v} for k, v in ap.rows],
            "status": ap.status,
            "tested": ap.tested,
            "package": ap.package,
            "landscape": ap.landscape,
            "requires": ap.requires,
            "sysdata": ap.sysdata,
            "romfs_zstd": bool(getattr(ap, "romfs_zstd", False)),
            "vulkan_driver": getattr(ap, "vulkan_driver", "system"),
            "pacing": getattr(ap, "pacing", "adaptive"),
            "env": ap.env,
            "settings": ap.settings,
            "overlay": ap.overlay_table(),
        }

    payload = {
        "schema_version": 1,
        "identity": {
            "game_id": g.id,
            "name": g.get("name", g.id),
            "title_id": f"{g.title_id:016X}",
            "program_id": f"{int(g.get('program_id'), 16):016X}",
            "package": manifest.get("package", ""),
            "version": manifest.get("version", ""),
            "display": manifest.get("display", ""),
            "language": manifest.get("language", ""),
        },
        "source": {
            "profile_directory": str(g.dir),
            "porter_commit": (repo / ".nx2a_sha").read_text().strip() if (repo / ".nx2a_sha").is_file() else "",
            "game_profile_sha256": hashlib.sha256(game_header).hexdigest(),
            "android_profile_sha256": hashlib.sha256(android_header).hexdigest(),
        },
        "game": {
            "rows": [{"key": k, "values": values} for k, values in g.rows],
            "modules": g.words("modules"),
            "builds": g.builds(),
            "tables": tables,
        },
        "android": android,
    }
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > 4 * 1024 * 1024:
        raise ValueError(f"runtime profile JSON exceeds 4 MiB ({len(encoded)} bytes)")
    target = data_dir / "profile.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_bytes(encoded)
    temporary.replace(target)
    return target, len(encoded), payload["source"]["game_profile_sha256"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--game-id", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--source-folder", default="")
    args = ap.parse_args()
    target, size, digest = export_profile(args.repo, args.game_id, args.data, args.source_folder)
    print(f"[NGR profile] exported schema v1: {target} ({size} bytes)", flush=True)
    print(f"[NGR profile] compiled game_profile.h SHA-256 matched: {digest}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[NGR profile] ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
