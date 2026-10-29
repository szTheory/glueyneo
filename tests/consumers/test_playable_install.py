#!/usr/bin/env python3
"""Check installed native and Libretro artifacts from a clean qualification build."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile


SOUND_RECIPE_COMMANDS = (
    "cmake --preset owned-debug",
    "cmake --build --preset owned-debug",
    "cmake --install build/owned-debug --prefix build/sound-prefix",
    'cmake -S tests/consumers -B build/sound-consumer -G Ninja -DGlueyneo_DIR="$PWD/build/sound-prefix/lib/cmake/Glueyneo" -DGLUEYNEO_CONSUMER_C_SOURCE="$PWD/examples/diagnostic.c"',
    "cmake --build build/sound-consumer",
    "build/sound-consumer/glueyneo-installed-sound --write-fixture build/public-sound-mvs.bin",
    "build/sound-consumer/glueyneo-installed-sound build/public-sound-mvs.bin --trace build/installed-sound.trace",
)


def validate_sound_recipe(source_root: Path) -> tuple[list[str], ...]:
    """Bind the prose recipe to the C consumer exercised by real package tests."""
    document = (source_root / "docs/audio-contract.md").read_text(encoding="utf-8")
    begin, end = "<!-- installed-sound:begin -->", "<!-- installed-sound:end -->"
    if document.count(begin) != 1 or document.count(end) != 1:
        raise RuntimeError("sound recipe markers are missing or ambiguous")
    section = document.split(begin, 1)[1].split(end, 1)[0]
    blocks = re.findall(r"```sh\n(.*?)```", section, re.DOTALL)
    if len(blocks) != 1:
        raise RuntimeError("sound recipe needs one executable command block")
    commands = tuple(shlex.split(line.strip()) for line in blocks[0].splitlines() if line.strip())
    if commands != tuple(shlex.split(line) for line in SOUND_RECIPE_COMMANDS):
        raise RuntimeError("sound recipe commands differ from the installed procedure")
    source_argument = next(arg.split("=", 1)[1] for arg in commands[3]
                           if arg.startswith("-DGLUEYNEO_CONSUMER_C_SOURCE="))
    diagnostic = Path(source_argument.replace("$PWD", str(source_root.resolve())))
    if diagnostic != source_root.resolve() / "examples/diagnostic.c" or not diagnostic.is_file():
        raise RuntimeError("sound recipe diagnostic source is missing or outside the source tree")
    source = (source_root / "tests/consumers/sound_consumer.c").read_text(encoding="utf-8")
    names = ("gn_create", "gn_load_mvs_v3", "gn_mvs_audio_capacity_v1",
             "GN_MVS_FRAME_REQUEST_V1_VERSION", "GN_MVS_FRAME_RESULT_V1_VERSION",
             "gn_mvs_advance_frame_v1", "sizeof(request)", "sizeof(result)",
             "gn_reset", "gn_destroy")
    if any(name not in section or name not in source for name in names):
        raise RuntimeError("sound recipe API differs from the compiled C consumer")
    main = source.split("int main(", 1)[-1]
    sequence = ("gn_create(", "load_bundle(", "gn_mvs_audio_capacity_v1(",
                "gn_mvs_advance_frame_v1(", "gn_reset(", "gn_destroy(")
    positions = [main.find(name) for name in sequence]
    if -1 in positions or positions != sorted(positions):
        raise RuntimeError("sound recipe create/load/query/frame/reset/destroy order changed")
    return commands


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--consumer", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--sound-consumer", type=Path, required=True)
    parser.add_argument("--sound-reference-consumer", type=Path, required=True)
    parser.add_argument("--sound-fixture", type=Path, required=True)
    args = parser.parse_args()
    validate_sound_recipe(Path(__file__).resolve().parents[2])
    prefix = args.prefix.resolve()
    consumer = args.consumer.resolve()
    fixture = args.fixture.resolve()
    core = args.core.resolve() if args.core else None
    runner_candidates = sorted((prefix / "bin").glob("glueyneo-diagnostic*"))
    if len(runner_candidates) != 1:
        raise SystemExit("installed diagnostic runner is missing or ambiguous")
    installed_fixture = prefix / "share" / "glueyneo" / "diagnostic-original-a.bin"
    if not installed_fixture.is_file() or not fixture.is_file():
        raise SystemExit("installed or generated diagnostic fixture is missing")
    if sha256(installed_fixture) != sha256(fixture):
        raise SystemExit("installed fixture differs from the clean build fixture")
    check = subprocess.run([str(runner_candidates[0]), "--check-fixture", str(installed_fixture)],
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           check=False, timeout=30)
    if check.returncode:
        raise SystemExit("installed diagnostic runner rejected its fixture")
    run = subprocess.run([str(consumer), str(installed_fixture)], text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         check=False, timeout=30)
    if run.returncode or '"outcome":"pass"' not in run.stdout:
        raise SystemExit("out-of-tree installed C consumer failed its diagnostic")
    with tempfile.TemporaryDirectory(prefix="glueyneo-installed-sound-") as temporary:
        traces = []
        for index, executable in enumerate((args.sound_reference_consumer, args.sound_consumer)):
            trace = Path(temporary) / f"{index}.trace"
            sound = subprocess.run([str(executable), str(args.sound_fixture), "--trace", str(trace)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=30)
            if sound.returncode or not sound.stdout.startswith("SDK_SOUND "):
                raise SystemExit("installed or reference sound consumer failed")
            record = json.loads(sound.stdout.removeprefix("SDK_SOUND "))
            if (record.get("outcome") != "pass" or record.get("frames") != 4 or
                    any(record.get(key) != "pass" for key in ("tone", "fire", "release")) or
                    not 0 < trace.stat().st_size <= 2 * 1024 * 1024):
                raise SystemExit("sound consumer lacks bounded signal/controls evidence")
            traces.append(trace.read_bytes())
        if traces[0] != traces[1]:
            raise SystemExit("installed sound PCM/video differs from in-tree reference")
    result = {
        "schema": "glueyneo.playable-install-consumer/v1",
        "status": "pass",
        "fixture_sha256": sha256(fixture),
        "installed_native_consumer": "pass",
        "installed_sound_consumer": "pass",
        "sound_native_transfer": "exact",
        "installed_libretro_core": "pass" if core and core.is_file() else "unknown",
    }
    if core and core.is_file():
        result["libretro_sha256"] = sha256(core)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["installed_libretro_core"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
