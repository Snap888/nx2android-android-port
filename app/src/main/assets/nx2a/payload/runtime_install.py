#!/usr/bin/env python3
"""Install one NGR game payload into the single NGR app's app-specific external files directory."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

APP_PACKAGE = "unknown.none.nx2android"


def run(cmd, label, timeout=1800):
    print(f"[NGR runtime] {label}", flush=True)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       errors="replace", timeout=timeout)
    if p.stdout:
        for line in p.stdout.splitlines():
            print(line, flush=True)
    if p.returncode:
        raise RuntimeError(f"{label} failed (exit {p.returncode})")
    return p.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adb", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--game-id", required=True)
    ap.add_argument("--serial", default="")
    ap.add_argument("--package", default=APP_PACKAGE)
    a = ap.parse_args()
    if len(a.game_id) != 20 or any(c not in "0123456789abcdef" for c in a.game_id):
        raise SystemExit("invalid NGR game ID")
    data = Path(a.data).resolve()
    if not data.is_dir() or not (data / "nx2a-data.json").is_file():
        raise SystemExit(f"not a completed nx2android data pack: {data}")
    if not (data / "libdmhost.so").is_file():
        raise SystemExit("libdmhost.so is missing; recompile this game with the NGR runtime build")
    adb = [a.adb]
    if a.serial:
        adb += ["-s", a.serial]
    devices = run(adb + ["devices"], "checking the connected Android device", timeout=40)
    connected = [line.split()[0] for line in devices.splitlines()[1:] if len(line.split()) >= 2 and line.split()[1] == "device"]
    if a.serial and a.serial not in connected:
        raise SystemExit(f"configured ADB device is not connected: {a.serial}")
    if not a.serial:
        if len(connected) != 1:
            raise SystemExit(f"expected one connected ADB device, found {len(connected)}; select a device in the Device tab")
    remote = f"/sdcard/Android/data/{a.package}/files/games/{a.game_id}"
    run(adb + ["shell", "mkdir", "-p", remote], "preparing the NGR game directory", timeout=60)
    run(adb + ["push", str(data) + "/.", remote + "/"], "copying game data and native runtime to NGR", timeout=3600)
    run(adb + ["shell", "sh", "-c", f"test -s '{remote}/libdmhost.so' && test -f '{remote}/nx2a-data.json'"],
        "verifying the installed game runtime and data", timeout=60)
    print(f"[NGR runtime] installed: {remote}", flush=True)
    print("[NGR runtime] native libraries will be staged into private executable storage at launch", flush=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired as e:
        print(f"[NGR runtime] ADB timed out: {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
    except Exception as e:
        print(f"[NGR runtime] ERROR: {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
