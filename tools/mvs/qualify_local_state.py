#!/usr/bin/env python3
"""Run bounded local native-state continuation checks for the selected MVS scene."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import uuid


ROOT = Path(__file__).resolve().parents[2]
PUBLIC_BUILD = ROOT / "build" / "sdk-debug"
DEBUG_RUNNER = PUBLIC_BUILD / ("sdk_state_process.exe" if os.name == "nt"
                               else "sdk_state_process")
PUBLIC_BUNDLE = PUBLIC_BUILD / "public-sound-mvs.bin"
MAX_ACTIVE_FRAMES = 3600
MAX_FUTURE_FRAMES = 8
MAX_INPUT_MASK = 0x3FF
LOCAL_REPORT_LIMIT = 1024 * 1024


class QualificationError(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def encode_schedule(*, capture_frame: int, future_inputs: list[int],
                    private_scene: bool) -> bytes:
    """Encode all frame masks through the requested future continuation."""
    if (type(capture_frame) is not int or capture_frame < 0 or
            not isinstance(future_inputs, list) or
            type(private_scene) is not bool or
            len(future_inputs) <= capture_frame + 1 or
            len(future_inputs) > MAX_ACTIVE_FRAMES):
        raise ValueError("invalid local state schedule bounds")
    future_frames = len(future_inputs) - capture_frame - 1
    if future_frames > MAX_FUTURE_FRAMES:
        raise ValueError("local future frame count exceeds bound")
    if any(type(mask) is not int or not 0 <= mask <= MAX_INPUT_MASK
           for mask in future_inputs):
        raise ValueError("invalid local input mask")
    flags = 0 if private_scene else 1
    header = b"GNSL" + struct.pack(
        ">5I", 1, capture_frame, future_frames, flags, len(future_inputs))
    return header + b"".join(struct.pack(">I", mask) for mask in future_inputs)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise QualificationError("local-tooling-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_quiet(command: list[str], *, timeout: int,
              cwd: Path = ROOT) -> bool:
    try:
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, timeout=timeout,
                                 check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def build_public_driver() -> bool:
    return (run_quiet(["cmake", "--preset", "sdk-debug"], timeout=180) and
            run_quiet(["cmake", "--build", "--preset", "sdk-debug",
                       "--target", "sdk_state_process",
                       "glueyneo-public-sound-fixture", "--parallel", "2"],
                      timeout=300))


def run_public_self_test() -> int:
    if not build_public_driver() or not DEBUG_RUNNER.is_file() or not PUBLIC_BUNDLE.is_file():
        print('STATE_LOCAL_SELF_TEST {"outcome":"blocked",'
              '"reason":"public-driver-or-fixture-unavailable"}')
        return 1
    # Public fixture startup is deliberately one raw cycle; future masks are
    # arbitrary public test inputs and never read from a private scene contract.
    masks = [0, 0x40, 0, 0]
    try:
        with tempfile.TemporaryDirectory(prefix="state-local-public-",
                                         dir=PUBLIC_BUILD) as temporary:
            directory = Path(temporary)
            schedule = directory / "schedule.bin"
            schedule.write_bytes(encode_schedule(
                capture_frame=1, future_inputs=masks, private_scene=False))
            output = directory / "output"
            output.mkdir()
            command = [sys.executable, str(ROOT / "tests/sdk/test_state_exchange.py"),
                       "--mode", "local", "--runner", str(DEBUG_RUNNER),
                       "--bundle", str(PUBLIC_BUNDLE), "--schedule", str(schedule),
                       "--output-dir", str(output)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True,
                                    text=True, timeout=MAX_LOCAL_RUN_SECONDS,
                                    check=False)
            metadata = parse_supervisor_result(result.stdout)
            if result.returncode != 0 or metadata is None:
                assertion = next((line.removeprefix("ASSERTION FAILED ")
                                  for line in result.stderr.splitlines()
                                  if line.startswith("ASSERTION FAILED sdk.state.local.")),
                                 None)
                child_assertion = next((line.removeprefix("LOCAL CHILD ASSERTION ")
                                         for line in result.stderr.splitlines()
                                         if line.startswith("LOCAL CHILD ASSERTION sdk.state.local.")),
                                        None)
                print('STATE_LOCAL_SELF_TEST {"outcome":"fail",'
                      '"reason":"public-process-comparison-failed",'
                      '"assertion":' + json.dumps(assertion) + ","
                      '"child_assertion":' + json.dumps(child_assertion) + "}")
                return 1
            print("STATE_LOCAL_SELF_TEST " + json.dumps({
                "outcome": "pass", "cases": metadata["cases"],
                "assertions": metadata["assertions"],
                "future_frames": metadata["future_frames"],
                "state_bytes": metadata["state_bytes"],
                "trace_bytes": metadata["trace_bytes"],
                "independent_processes": metadata["independent_processes"],
                "invalid_import_atomic": metadata["invalid_import_atomic"],
                "historical_sram_restored": metadata["historical_sram_restored"],
                "full_trace_equal": metadata["full_trace_equal"],
            }, sort_keys=True))
            return 0
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        print('STATE_LOCAL_SELF_TEST {"outcome":"fail",'
              '"reason":"public-process-comparison-failed"}')
        return 1


MAX_LOCAL_RUN_SECONDS = 180


def parse_supervisor_result(output: str) -> dict[str, object] | None:
    for line in output.splitlines():
        if not line.startswith("STATE_LOCAL_RESULT "):
            continue
        try:
            result = json.loads(line[len("STATE_LOCAL_RESULT "):])
        except json.JSONDecodeError:
            return None
        if (not isinstance(result, dict) or result.get("outcome") != "pass" or
                result.get("cases") != 1 or
                not isinstance(result.get("assertions"), int) or
                result.get("assertions", 0) <= 0 or
                result.get("independent_processes") is not True or
                result.get("invalid_import_atomic") is not True or
                result.get("historical_sram_restored") is not True or
                result.get("full_trace_equal") is not True):
            return None
        return result
    return None


def require_ignored_directory(path: Path) -> None:
    if any(parent.is_symlink() for parent in (
            ROOT / "local", ROOT / "local/qualification", path.parent, path)):
        raise QualificationError("private-output-path-rejected")
    result = subprocess.run(["git", "check-ignore", "-q", str(path)],
                            cwd=ROOT, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, check=False)
    if result.returncode != 0:
        raise QualificationError("private-output-not-ignored")
    if path.exists():
        if not path.is_dir():
            raise QualificationError("private-output-path-rejected")
    else:
        path.mkdir(parents=True)
    if path.is_symlink():
        raise QualificationError("private-output-path-rejected")


def build_private_importer(boot) -> Path:
    if not (run_quiet(["cmake", "--preset", boot.QUALIFIER_PRESET], timeout=180) and
            run_quiet(["cmake", "--build", "--preset", boot.QUALIFIER_PRESET,
                       "--target", "mvs_importer", "--parallel", "2"], timeout=300)):
        raise QualificationError("selected-importer-build-failed")
    importer = boot.CONFIGURED_IMPORTER_PATH
    if not importer.is_file() or not os.access(importer, os.X_OK):
        raise QualificationError("selected-importer-unavailable")
    return importer


def read_scene(config_path: Path, boot):
    canonical_path = boot.PHASE06_CONTRACT_PATH
    expected = (ROOT / canonical_path).resolve(strict=True)
    if (config_path.is_symlink() or not config_path.is_file() or
            config_path.resolve(strict=True) != expected or
            not boot.ignored(config_path)):
        raise QualificationError("explicit-scene-configuration-rejected")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch",
                              config_path.relative_to(ROOT).as_posix()],
                             cwd=ROOT, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, check=False)
    if tracked.returncode == 0:
        raise QualificationError("scene-configuration-is-tracked")
    input_root = ROOT / "local/roms"
    status, scene = boot.validate_scene_contract(
        canonical_path, Path("local/roms"), check_current_identity=False)
    if status != "active_scene_contract_valid" or not isinstance(scene, dict):
        raise QualificationError("selected-scene-contract-invalid")
    sound_path = ROOT / boot.PHASE07_SOUND_CONTRACT_PATH
    sound = boot._read_phase07_sound_contract(
        Path(boot.PHASE07_SOUND_CONTRACT_PATH), require_frozen=True)
    scene_digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
    if (not isinstance(sound, dict) or
            not boot._phase07_sound_contract_scene_binding_valid(
                sound, scene, Path(boot.PHASE06_CONTRACT_PATH),
                scene_digest=scene_digest)):
        raise QualificationError("selected-sound-contract-invalid")
    pairs = boot.find_pairs(input_root)
    if len(pairs) != 1:
        raise QualificationError("selected-media-pair-count-invalid")
    identities = [boot._file_identity(path) for path in pairs[0]]
    if identities != scene.get("media_identity"):
        raise QualificationError("selected-media-identity-mismatch")
    return scene, sound, pairs[0], scene_digest


def selected_schedule(scene: dict[str, object], sound: dict[str, object]
                      ) -> tuple[int, list[int], str]:
    schedule = scene.get("schedule")
    recordings = sound.get("recordings")
    action = recordings.get("action") if isinstance(recordings, dict) else None
    windows = action.get("windows") if isinstance(action, dict) else None
    fire = windows.get("fire") if isinstance(windows, dict) else None
    capture = fire.get("last_frame") if isinstance(fire, dict) else None
    if (type(capture) is not int or capture < 0 or capture + 4 >= MAX_ACTIVE_FRAMES or
            not isinstance(schedule, dict) or
            type(schedule.get("active_frames")) is not int or
            capture + 4 >= schedule["active_frames"]):
        raise QualificationError("selected-fire-window-boundary-invalid")
    # The scene's approved action schedule is the source of every active input.
    # Import the established parser from the same source module used to validate it.
    module = load_module("_glueyneo_qualify_local_boot_schedule", ROOT /
                         "tools/mvs/qualify_local_boot.py")
    events = module._active_scene_input_events(schedule, "fire", "action")
    if not isinstance(events, list) or not events:
        raise QualificationError("selected-input-schedule-invalid")
    future_end = capture + 4
    masks = [0] * (future_end + 1)
    current = 0
    event_index = 0
    for frame in range(future_end + 1):
        while event_index < len(events) and events[event_index][0] == frame:
            current = events[event_index][1]
            event_index += 1
        masks[frame] = current
    if event_index != len(events):
        # Later scheduled inputs are irrelevant to this local continuation.
        if any(frame <= future_end for frame, _mask in events[event_index:]):
            raise QualificationError("selected-input-schedule-order-invalid")
    identity = module.active_scene_configuration_identity(schedule)
    return capture, masks, identity


def run_local(config_path: Path) -> int:
    private_root = ROOT / "local/qualification/native-state"
    run_directory = private_root / ("run-" + uuid.uuid4().hex)
    report_path = private_root / ("report-" + uuid.uuid4().hex + ".json")
    started = time.monotonic()
    report: dict[str, object] = {
        "schema_version": 1, "outcome": "blocked",
        "reason": "qualification-not-complete",
    }
    preserve = True
    try:
        require_ignored_directory(private_root)
        run_directory.mkdir()
        if (subprocess.run(["git", "check-ignore", "-q", str(run_directory)],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False).returncode != 0):
            raise QualificationError("private-output-not-ignored")
        boot = load_module("_glueyneo_qualify_local_boot", ROOT /
                           "tools/mvs/qualify_local_boot.py")
        scene, sound, selected_pair, config_digest = read_scene(config_path, boot)
        capture_frame, masks, schedule_identity = selected_schedule(scene, sound)
        if not build_public_driver():
            raise QualificationError("debug-state-runner-build-failed")
        importer = build_private_importer(boot)
        bundle = run_directory / "selected.gnmv"
        imported = subprocess.run(
            [str(importer), "--selected", str(selected_pair[0]),
             str(selected_pair[1]), str(bundle)], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30, check=False)
        if imported.returncode != 0 or not bundle.is_file():
            raise QualificationError("selected-media-import-failed")
        schedule_path = run_directory / "schedule.bin"
        schedule_path.write_bytes(encode_schedule(
            capture_frame=capture_frame, future_inputs=masks, private_scene=True))
        output = run_directory / "process-output"
        output.mkdir()
        command = [sys.executable, str(ROOT / "tests/sdk/test_state_exchange.py"),
                   "--mode", "local", "--runner", str(DEBUG_RUNNER),
                   "--bundle", str(bundle), "--schedule", str(schedule_path),
                   "--output-dir", str(output)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True,
                                text=True, timeout=MAX_LOCAL_RUN_SECONDS,
                                check=False)
        metadata = parse_supervisor_result(result.stdout)
        if result.returncode != 0 or metadata is None:
            assertion = None
            for line in result.stderr.splitlines():
                for prefix in ("ASSERTION FAILED sdk.state.local.",
                               "LOCAL CHILD ASSERTION sdk.state.local."):
                    if line.startswith(prefix):
                        suffix = line.removeprefix(prefix)
                        if suffix and all(char.isalnum() or char in "_.-"
                                          for char in suffix):
                            assertion = prefix.removeprefix(
                                "ASSERTION FAILED ").removeprefix(
                                    "LOCAL CHILD ASSERTION ") + suffix
                            break
                if assertion is not None:
                    break
            reason = "selected-scene-continuation-failed"
            if assertion is not None:
                reason += ":" + assertion
            raise QualificationError(reason)
        source_revision = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=10, check=True).stdout.strip()
        report.update({
            "outcome": "pass", "reason": "selected-scene-continuation-passed",
            "code_revision": source_revision,
            "source_content_sha256": metadata.get("source_content_sha256"),
            "configuration_sha256_private": config_digest,
            "media_identity_private": [
                {"size": item["size"], "sha256": item["sha256"]}
                for item in scene["media_identity"]
            ],
            "schedule_identity_private": schedule_identity,
            "future_frames": metadata["future_frames"],
            "state_bytes": metadata["state_bytes"],
            "trace_bytes": metadata["trace_bytes"],
            "assertions": metadata["assertions"],
            "independent_processes": metadata["independent_processes"],
            "invalid_import_atomic": metadata["invalid_import_atomic"],
            "historical_sram_restored": metadata["historical_sram_restored"],
            "full_trace_equal": metadata["full_trace_equal"],
        })
        preserve = False
        print("PRIVATE_STATE_RESULT " + json.dumps({
            "outcome": "pass", "code_revision": source_revision,
            "future_frames": metadata["future_frames"],
            "state_bytes": metadata["state_bytes"],
            "trace_bytes": metadata["trace_bytes"],
            "assertions": metadata["assertions"],
            "independent_processes": metadata["independent_processes"],
            "invalid_import_atomic": metadata["invalid_import_atomic"],
            "historical_sram_restored": metadata["historical_sram_restored"],
            "full_trace_equal": metadata["full_trace_equal"],
        }, sort_keys=True))
        return 0
    except QualificationError as error:
        report.update(outcome="blocked", reason=error.reason)
        print("PRIVATE_STATE_RESULT " + json.dumps({
            "outcome": "blocked", "reason": error.reason}, sort_keys=True))
        return 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            subprocess.SubprocessError):
        report.update(outcome="blocked", reason="local-qualification-error")
        print('PRIVATE_STATE_RESULT {"outcome":"blocked",'
              '"reason":"local-qualification-error"}')
        return 1
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        try:
            if (run_directory.parent.is_dir() and not report_path.is_symlink() and
                    report_path.parent.resolve() == run_directory.parent.resolve()):
                report_path.write_text(json.dumps(report, sort_keys=True) + "\n",
                                       encoding="utf-8")
            if not preserve and run_directory.is_dir():
                shutil.rmtree(run_directory)
        except OSError:
            # No private path or low-level OS diagnostic enters stdout/stderr.
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--run-local", action="store_true")
    parser.add_argument("--config", type=Path,
                        help="explicit canonical local scene configuration")
    args = parser.parse_args()
    if args.self_test:
        if args.config is not None:
            parser.error("--config is available only with --run-local")
        return run_public_self_test()
    if args.config is None:
        parser.error("--run-local requires an explicit --config")
    return run_local(args.config if args.config.is_absolute()
                     else ROOT / args.config)


if __name__ == "__main__":
    raise SystemExit(main())
