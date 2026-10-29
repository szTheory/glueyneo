#!/usr/bin/env python3
"""Compare the opt-in frontend observer window with a fresh native process."""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import tempfile
from pathlib import Path

import retroarch_smoke as smoke


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run(harness: Path, production: Path, witness: Path, bundle: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="glueyneo-observer-test-") as temporary:
        work = Path(temporary)
        state_path = work / "checkpoint.gnst"
        inputs_path = work / "inputs.gnfi"
        trace_path = work / "witness.gnfo"
        observed_process = subprocess.run(
            [str(harness), "--continuation-observations", str(bundle), str(state_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=90,
        )
        require(observed_process.returncode == 0,
                "instrumented adapter or independent in-process checks failed")
        observations = smoke.parse_continuation_observations(observed_process.stdout)
        state = state_path.read_bytes()
        require(72 <= len(state) <= 1024 * 1024 and state.startswith(b"GNST"),
                "instrumented adapter did not write a bounded GNST checkpoint")
        require(len(state) == observations["capture"]["state_bytes"] ==
                observations["restore"]["state_bytes"],
                "observed capture and restore sizes do not match the checkpoint")
        require(observations["restore"].get("state") == state,
                "observer restore bytes do not equal the saved GNST checkpoint")

        frames = observations["frames"]
        input_data = bytearray(b"GNFI" + struct.pack(">II", 1, len(frames)))
        for frame in frames:
            input_data.extend(struct.pack(">IQ", frame["input_mask"], frame["cycle_delta"]))
        inputs_path.write_bytes(input_data)
        witness_process = subprocess.run(
            [str(witness), "frontend-import", str(bundle), str(state_path),
             str(inputs_path), str(trace_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=90,
        )
        require(witness_process.returncode == 0,
                "fresh native process rejected the observed GNST continuation")
        result_lines = [line for line in witness_process.stdout.splitlines()
                        if line.startswith(b"STATE_FRONTEND_RESULT ")]
        require(len(result_lines) == 1, "native witness result record is missing or duplicated")
        result = json.loads(result_lines[0].split(b" ", 1)[1])
        require(result.get("outcome") == "pass" and result.get("frames") == 4,
                "fresh native process did not complete its four-frame continuation")
        require(result.get("state_bytes") == len(state) and
                result.get("nonzero_audio_samples", 0) > 0 and
                result.get("nonzero_video_bytes", 0) > 0,
                "native witness did not validate the exact payload and known signal")

        trace = trace_path.read_bytes()
        require(12 <= len(trace) <= 8 * 1024 * 1024 and
                trace[:12] == b"GNFO" + struct.pack(">II", 1, 4),
                "native witness trace is malformed or outside its bound")
        cursor = 12
        prior_cycles = 0
        nonzero_audio_samples = 0
        nonzero_video_bytes = 0
        for expected, frame in enumerate(frames):
            require(len(trace) - cursor >= 24, "native witness trace frame is truncated")
            input_mask, = struct.unpack_from(">I", trace, cursor)
            elapsed_cycles, = struct.unpack_from(">Q", trace, cursor + 4)
            audio_frames, video_bytes, audio_bytes = struct.unpack_from(
                ">III", trace, cursor + 12)
            cursor += 24
            require(input_mask == frame["input_mask"] and
                    elapsed_cycles == frame["cycle_delta"] - prior_cycles and
                    audio_frames == frame["audio_frames"] and
                    video_bytes == smoke.CONTINUATION_VIDEO_BYTES and
                    audio_bytes == audio_frames * 4,
                    "native witness input, cycles, or callback extents differ")
            require(video_bytes + audio_bytes <= len(trace) - cursor,
                    "native witness callback bytes are truncated")
            native_video = trace[cursor:cursor + video_bytes]
            cursor += video_bytes
            native_audio = trace[cursor:cursor + audio_bytes]
            cursor += audio_bytes
            require(native_video == frame["video"] and native_audio == frame["audio"],
                    "raw callback video or PCM differs from the fresh native witness")
            nonzero_video_bytes += sum(value != 0 for value in native_video)
            nonzero_audio_samples += sum(
                sample != 0 for sample, in struct.iter_unpack("<h", native_audio))
            prior_cycles = frame["cycle_delta"]
        require(cursor == len(trace) and nonzero_video_bytes > 0 and
                nonzero_audio_samples > 0,
                "native witness trace has trailing bytes or lacks the known sound signal")

        # Corrupt one byte inside the extracted GNST header length. The fresh
        # native process must reject the changed MEM at the state-restore
        # assertion, before it can produce a continuation trace.
        mutated_state_path = work / "mutated-mem.gnst"
        mutated_state = bytearray(state)
        mutated_state[12] ^= 0x01
        mutated_state_path.write_bytes(mutated_state)
        rejected_state = subprocess.run(
            [str(witness), "frontend-import", str(bundle), str(mutated_state_path),
             str(inputs_path), str(work / "mutated-mem.gnfo")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=90,
        )
        require(rejected_state.returncode != 0 and
                b"STATE_ASSERT sdk.state.frontend.accepts-actual-frontend-mem-payload" in
                rejected_state.stderr,
                "mutated extracted MEM did not fail at the native restore assertion")

        production_trace_path = work / "production.gnfo"
        production_process = subprocess.run(
            [str(production), "--continuation-production", str(bundle),
             str(state_path), str(production_trace_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=90,
        )
        require(production_process.returncode == 0,
                "default production adapter could not replay the same checkpoint")
        production_trace = production_trace_path.read_bytes()
        require(production_trace == trace,
                "observer-enabled callback output or guest cycles differ from production")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.harness.resolve(), args.production.resolve(),
            args.witness.resolve(), args.bundle.resolve())
    except (OSError, RuntimeError, ValueError, smoke.SmokeBlocked,
            subprocess.SubprocessError) as error:
        print(f"continuation observer verification failed: {type(error).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
