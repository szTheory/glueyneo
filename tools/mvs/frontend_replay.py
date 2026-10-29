"""Bounded private sampled-input RGB/PCM replay and retained-evidence evaluation.

This checks transport agreement with this exact core, not renderer correctness,
hardware truth, cycle-counter equality, or a unique animation phase.
"""
from __future__ import annotations

import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time
import io
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "libretro"))
import retroarch_smoke as smoke

POLICY = "sampled_input_rgb_replay_v1"
MANUAL_POLICY = "manual_sampled_input_rgb_replay_v1"
AUDIO_POLICY = "sampled_input_rgb_pcm_replay_v1"
MAX_FRAMES = 8192
MAX_REQUEST_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 256 * 1024
TIMEOUT_SECONDS = 180


class ReplayError(ValueError):
    """Finite failure token; never include private paths or native diagnostics."""


def _require(condition, token="invalid replay evidence"):
    if not condition:
        raise ReplayError(token)


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _implementation_identity():
    """Bind retained receipts to the exact replay, collector and evaluator code."""
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in (
        ("helper", Path(__file__).resolve()),
        ("collector", ROOT / "tests/libretro/retroarch_smoke.py"),
        ("evaluator", ROOT / "tools/mvs/qualify_local_boot.py"))}


def _audio_binding(invocation):
    context = invocation.get("audio_replay_context")
    if context is None:
        return None
    _require(isinstance(context, dict) and set(context) == {
        "scene_contract_sha256", "sound_contract_sha256", "schedule_identity",
        "converter_identity", "control"}, "invalid audio replay context")
    _require(all(_hash(context[key]) for key in
                 ("scene_contract_sha256", "sound_contract_sha256", "schedule_identity")))
    converter = context["converter_identity"]
    _require(isinstance(converter, dict) and set(converter) == {"board", "chip"} and
             all(_hash(value) for value in converter.values()))
    evidence = invocation.get("audio_evidence")
    _require(isinstance(evidence, dict) and smoke.frontend_audio_evidence_is_valid(
        evidence.get("capture"), evidence.get("route"), expected_control=context["control"],
        delivery=evidence.get("delivery")), "invalid audio stages")
    relative = evidence["capture"].get("recording_relative_path")
    _require(isinstance(relative, str) and 0 < len(relative) <= 256)
    path = Path(relative)
    # RetroArch's WAV driver may restart under the default .mkv filename.
    # The checked header and declared PCM format determine the container.
    _require(not path.is_absolute() and "\0" not in relative and
             all(part not in (".", "..") for part in path.parts) and
             1 <= len(path.parts) <= 2 and
             (len(path.parts) == 1 or path.parts[0] == "recordings"), "invalid recording path")
    return dict(context=context, evidence=evidence)


def _evidence(core_sha256, bundle_sha256, invocation, configuration_identity, *,
              _recorded_identity=None):
    _require(_hash(core_sha256) and _hash(bundle_sha256))
    _require(isinstance(configuration_identity, str) and 0 < len(configuration_identity) <= 4096)
    _require(isinstance(invocation, dict))
    manual = (invocation.get("input_mode") == "manual" and
              invocation.get("hybrid_policy") == "frontend_joint_delivery_human_semantics_v1" and
              _hash(invocation.get("hybrid_machine_identity")))
    maximum_interval = 64 if manual else 12
    _require(invocation.get("selected_bundle_sha256") == bundle_sha256)
    text = invocation.get("configuration_text")
    _require(isinstance(text, str) and len(text.encode()) <= 128 * 1024)
    _require(invocation.get("configuration_sha256") == hashlib.sha256(text.encode()).hexdigest())
    invocation_id = invocation.get("invocation_id")
    try:
        records = smoke._validated_observation_records(invocation.get("observations"), invocation_id)
    except (smoke.SmokeBlocked, TypeError, KeyError):
        raise ReplayError("invalid input history") from None
    # A failed run can poll without a successful submission. Such histories must
    # not be silently interpreted as ordinary frame-indexed input schedules.
    for record in records:
        sample, video = record["sample_sequence"], record["successful_video_sequence"]
        _require(sample <= MAX_FRAMES and video <= MAX_FRAMES, "replay frame budget exceeded")
        kind = record["event_kind"]
        _require(sample == video + (kind == "S"), "sample video divergence")
    changes = [record for record in records if record["event_kind"] == "S"]
    _require(changes and changes[0]["sample_sequence"] == 1, "incomplete input history")
    captures = invocation.get("captures")
    _require(isinstance(captures, list) and 1 <= len(captures) <= 6)
    selected = []
    for capture in captures:
        _require(isinstance(capture, dict))
        interval = capture.get("successful_video_interval")
        _require(isinstance(interval, list) and len(interval) == 2 and
                 all(type(n) is int for n in interval))
        lo, hi = interval
        _require(1 <= lo <= hi <= MAX_FRAMES and hi - lo <= maximum_interval, "invalid replay interval")
        _require(any(r["event_kind"] == "V" and r["successful_video_sequence"] == lo for r in records)
                 and any(r["event_kind"] == "V" and r["successful_video_sequence"] == hi for r in records),
                 "unobserved interval endpoint")
        _require(isinstance(capture.get("path"), str) and 0 < len(capture["path"]) <= 4096)
        _require(_hash(capture.get("sha256")))
        _require(type(capture.get("target_frame")) is int and capture["target_frame"] >= 0)
        selected.append({key: capture[key] for key in
                         ("path", "sha256", "successful_video_interval", "target_frame")})
    identity = _implementation_identity() if _recorded_identity is None else _recorded_identity
    _require(isinstance(identity, dict) and set(identity) == {"helper", "collector", "evaluator"}
             and all(_hash(value) for value in identity.values()), "invalid implementation identity")
    result = dict(policy=MANUAL_POLICY if manual else POLICY, core_sha256=core_sha256, bundle_sha256=bundle_sha256,
                implementation_identity=identity,
                invocation_id=invocation_id, observations=records, captures=selected,
                configuration_text=text, configuration_sha256=invocation["configuration_sha256"],
                configuration_identity=configuration_identity)
    if manual:
        result["hybrid_machine_identity"] = invocation["hybrid_machine_identity"]
    audio = _audio_binding(invocation)
    if audio is not None:
        _require(not manual, "manual audio replay is unsupported")
        result.update(policy=AUDIO_POLICY, audio=audio)
    return result


def replay_binding(core_sha256, bundle_sha256, invocation, configuration_identity, *,
                   _recorded_identity=None):
    """Bind all sampled history, captures, and configuration to immutable inputs."""
    return hashlib.sha256(_canonical(_evidence(core_sha256, bundle_sha256, invocation,
                                               configuration_identity,
                                               _recorded_identity=_recorded_identity))).hexdigest()


def _validate_receipt(receipt, core_sha256, bundle_sha256, invocation, configuration_identity, *,
                      _recorded_identity=None):
    """Validate retained evidence without executing native code or reading files."""
    try:
        binding = replay_binding(core_sha256, bundle_sha256, invocation, configuration_identity,
                                 _recorded_identity=_recorded_identity)
        audio = _audio_binding(invocation)
        fields = {"policy", "binding", "core_sha256", "bundle_sha256", "captures", "status"}
        if audio is not None:
            fields.add("audio")
        if not isinstance(receipt, dict) or set(receipt) != fields:
            return False
        policy = _evidence(core_sha256, bundle_sha256, invocation, configuration_identity,
                           _recorded_identity=_recorded_identity)["policy"]
        if any(receipt.get(k) != v for k, v in dict(policy=policy, binding=binding,
                core_sha256=core_sha256, bundle_sha256=bundle_sha256, status="pass").items()):
            return False
        results = receipt["captures"]
        if not isinstance(results, list) or len(results) != len(invocation["captures"]):
            return False
        for result, capture in zip(results, invocation["captures"]):
            if not isinstance(result, dict) or set(result) != {
                    "capture_sha256", "successful_video_interval", "matching_sequences"}:
                return False
            lo, hi = capture["successful_video_interval"]
            matches = result["matching_sequences"]
            if (result["capture_sha256"] != capture["sha256"] or
                    result["successful_video_interval"] != [lo, hi] or
                    not isinstance(matches, list) or not matches or
                    any(type(n) is not int or not lo <= n <= hi for n in matches) or
                    matches != sorted(set(matches))):
                return False
        if audio is not None:
            actual = receipt["audio"]
            capture = audio["evidence"]["capture"]
            expected = dict(status="pass", stage=capture["stage"], format=capture["format"],
                            sample_rate_hz=48000, sample_frames=capture["sample_frames"],
                            pcm_sha256=capture["pcm_sha256"])
            if (not isinstance(actual, dict) or set(actual) != set(expected) | {
                    "completed_sequences", "frame_sample_counts"} or
                    any(actual.get(key) != value for key, value in expected.items())):
                return False
            counts, completed = actual["frame_sample_counts"], actual["completed_sequences"]
            if (type(completed) is not int or not 1 <= completed <= MAX_FRAMES or
                    not isinstance(counts, list) or len(counts) != completed or
                    any(type(n) is not int or not 0 < n <= 812 for n in counts) or
                    sum(counts) != capture["sample_frames"] or
                    max(cap["successful_video_interval"][1] for cap in invocation["captures"]) > completed):
                return False
        return True
    except (ReplayError, OSError, TypeError, ValueError, KeyError):
        return False


def validate_receipt(receipt, core_sha256, bundle_sha256, invocation, configuration_identity):
    """Validate live replay using only the current implementation identity."""
    return _validate_receipt(receipt, core_sha256, bundle_sha256, invocation, configuration_identity)


def validate_retained_receipt(receipt, core_sha256, bundle_sha256, invocation,
                              configuration_identity, recorded_identity):
    """Verify an immutable old binding, never attest execution of current code.

    Live replay always uses validate_receipt's current implementation identity.
    This separate entry point lets offline pixel diagnosis preserve the original
    collector/helper/evaluator provenance rather than rewrite it as a new run.
    """
    if recorded_identity is None:
        return False
    return _validate_receipt(receipt, core_sha256, bundle_sha256, invocation,
                             configuration_identity, _recorded_identity=recorded_identity)


def continuation_alignment(observations, frames, *, invocation_id, after_video_sequence):
    """Bind continuation masks to the first four observed guest videos after load.

    Initial-load replay has its own receipt. This check starts at the measured
    post-load video boundary so pre-state samples cannot satisfy restoration.
    """
    if (not isinstance(invocation_id, str) or not invocation_id or
            type(after_video_sequence) is not int or after_video_sequence < 0 or
            not isinstance(frames, list) or len(frames) != smoke.CONTINUATION_WINDOW_FRAMES):
        raise ReplayError("invalid restored input boundary")
    expected = [frame.get("input_mask") if isinstance(frame, dict) else None
                for frame in frames]
    if any(type(mask) is not int or not 0 <= mask <= 1023 for mask in expected):
        raise ReplayError("invalid restored input masks")
    try:
        records = smoke._validated_observation_records(observations, invocation_id)
    except (smoke.SmokeBlocked, TypeError, KeyError):
        raise ReplayError("invalid restored observation chain") from None
    videos = [record for record in records
              if record["event_kind"] == "V" and
              record["successful_video_sequence"] > after_video_sequence]
    sequences = [record["successful_video_sequence"] for record in videos]
    observed_masks = [record["sampled_mask"] for record in videos]
    expected_changes = [mask for index, mask in enumerate(expected)
                        if index == 0 or mask != expected[index - 1]]
    observed_changes = [mask for index, mask in enumerate(observed_masks)
                        if index == 0 or mask != observed_masks[index - 1]]
    if (not videos or len(sequences) != len(set(sequences)) or
            sequences != sorted(sequences) or observed_changes != expected_changes):
        raise ReplayError("restored inputs diverge from post-load frames")
    return {"policy": "post_restore_sample_alignment_v1",
            "restore_after_video_sequence": after_video_sequence,
            "video_interval": [sequences[0], sequences[-1]],
            "sampled_masks": expected,
            "observed_input_transitions": observed_changes}


def _read(path, limit):
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    _require(0 < len(data) <= limit, "replay file budget exceeded")
    return data


def _capture_rgb(capture):
    path = Path(capture["path"])
    raw = _read(path, smoke.TITLE_CAPTURE_MAX_BYTES)
    _require(hashlib.sha256(raw).hexdigest() == capture["sha256"], "capture identity changed")
    _require(smoke._active_png_framing_is_valid(raw), "invalid capture PNG")
    class Snapshot:
        def read_bytes(self):
            return raw
    # Decode the exact hash-checked snapshot, never a second racing path read.
    image = smoke.decode_png(Snapshot())
    _require(_read(path, smoke.TITLE_CAPTURE_MAX_BYTES) == raw, "capture identity changed")
    width, height, channels, pixels = image
    _require((width, height) == (320, 224) and channels in (3, 4), "invalid capture geometry")
    return pixels if channels == 3 else bytes(v for i in range(0, len(pixels), 4) for v in pixels[i:i + 3])


def _capture_pcm(invocation):
    bound = _audio_binding(invocation)
    _require(bound is not None, "missing audio stages")
    capture = bound["evidence"]["capture"]
    root = Path(invocation["captures"][0]["path"]).parent
    path = root / capture["recording_relative_path"]
    _require(not root.is_symlink() and not path.parent.is_symlink())
    try:
        parsed = smoke.parse_frontend_audio_capture(
            path, owned_directory=root, started_ns=capture["capture_started_ns"],
            finished_ns=capture["capture_finished_ns"])
    except smoke.SmokeBlocked:
        raise ReplayError("invalid recorded PCM") from None
    _require(all(capture.get(key) == value for key, value in parsed.items()), "audio metadata changed")
    encoded = _read(path, smoke.AUDIO_CAPTURE_MAX_BYTES)
    _require(hashlib.sha256(encoded).hexdigest() == capture["recording_sha256"], "audio identity changed")
    if capture["container"] == "retroarch_v1_22_2_wav_padded56":
        pcm = encoded[56:]
    else:
        with wave.open(io.BytesIO(encoded), "rb") as stream:
            pcm = stream.readframes(capture["sample_frames"])
    _require(len(pcm) == capture["sample_frames"] * 4 and
             hashlib.sha256(pcm).hexdigest() == capture["pcm_sha256"], "audio identity changed")
    return pcm


def _replay_frames(core_path, bundle, changes, candidates, *, audio_pcm=None):
    """Only called in the disposable child. Callback failures are latched."""
    env_t = c.CFUNCTYPE(c.c_bool, c.c_uint, c.c_void_p)
    video_t = c.CFUNCTYPE(None, c.c_void_p, c.c_uint, c.c_uint, c.c_size_t)
    poll_t = c.CFUNCTYPE(None)
    input_t = c.CFUNCTYPE(c.c_int16, c.c_uint, c.c_uint, c.c_uint, c.c_uint)
    audio_t = c.CFUNCTYPE(c.c_size_t, c.c_void_p, c.c_size_t)
    log_t = c.CFUNCTYPE(None, c.c_int, c.c_char_p)

    class Game(c.Structure):
        _fields_ = [("path", c.c_char_p), ("data", c.c_void_p), ("size", c.c_size_t), ("meta", c.c_char_p)]

    state = dict(sequence=0, mask=0, polls=0, videos=0, format=False)
    errors, frames = [], {}
    if audio_pcm is not None:
        _require(isinstance(audio_pcm, bytes) and 0 < len(audio_pcm) <= smoke.AUDIO_CAPTURE_MAX_BYTES
                 and len(audio_pcm) % 4 == 0, "invalid replay PCM")
    audio_offset, audio_counts = 0, []

    def audio(data, count):
        nonlocal audio_offset
        if audio_pcm is None:
            return count
        _require(bool(data) and 0 < count <= 812 and len(audio_counts) == state["sequence"] - 1,
                 "invalid audio callback")
        raw = c.string_at(data, count * 4)
        if sys.byteorder != "little":
            raw = b"".join(raw[index:index + 2][::-1] for index in range(0, len(raw), 2))
        _require(audio_pcm[audio_offset:audio_offset + len(raw)] == raw, "complete PCM mismatch")
        audio_offset += len(raw)
        audio_counts.append(count)
        return count

    def guarded(function, fallback=None):
        def call(*args):
            try:
                return function(*args)
            except Exception:
                errors.append("native callback failure")
                return fallback
        return call

    def environment(command, data):
        if command == 10:
            _require(bool(data) and c.cast(data, c.POINTER(c.c_int))[0] == 1)
            state["format"] = True
            return True
        if command == 27:
            _require(bool(data))
            c.cast(data, c.POINTER(c.c_void_p))[0] = c.cast(logger, c.c_void_p).value
            return True
        return command in (18, 32, 37)

    def video(data, width, height, pitch):
        state["videos"] += 1
        _require(bool(data) and state["format"] and (width, height, pitch) == (320, 224, 1280))
        if state["sequence"] in candidates:
            raw = c.string_at(data, height * pitch)
            frames[state["sequence"]] = bytes(v for i in range(0, len(raw), 4)
                                              for v in ((raw[i + 2], raw[i + 1], raw[i])
                                                        if sys.byteorder == "little" else raw[i + 1:i + 4]))

    def poll():
        state["polls"] += 1

    keys = {2: 1, 3: 2, 4: 4, 5: 8, 6: 16, 7: 32, 0: 64, 8: 128, 1: 256, 9: 512}
    def inputs(port, device, index, key):
        _require(state["polls"] == 1 and state["videos"] == 0)
        _require(port == 0 and device == 1 and index == 0 and key in (*keys, 14))
        return int(bool(state["mask"] & keys.get(key, 0)))

    def log(level, message):
        # Ignore variadic payloads: only the fixed ABI prefix is inspected.
        _require(level < 3, "native runtime failure")

    logger = log_t(guarded(log))
    callbacks = [env_t(guarded(environment, False)), video_t(guarded(video)),
                 poll_t(guarded(poll)), input_t(guarded(inputs, 0)),
                 audio_t(guarded(audio, 0))]
    core = c.CDLL(str(Path(core_path).resolve()))
    for name, callback in zip(("environment", "video_refresh", "input_poll", "input_state", "audio_sample_batch"), callbacks):
        setter = getattr(core, "retro_set_" + name)
        setter.argtypes, setter.restype = [type(callback)], None
        setter(callback)
    for name in ("retro_init", "retro_run", "retro_unload_game", "retro_deinit"):
        getattr(core, name).argtypes, getattr(core, name).restype = [], None
    core.retro_load_game.argtypes, core.retro_load_game.restype = [c.POINTER(Game)], c.c_bool
    core.retro_init()
    storage = c.create_string_buffer(bundle)
    game = Game(None, c.cast(storage, c.c_void_p), len(bundle), None)
    loaded = False
    try:
        loaded = bool(core.retro_load_game(c.byref(game)))
        _require(loaded and not errors, "native load failure")
        maximum = max(candidates) if audio_pcm is None else MAX_FRAMES
        for sequence in range(1, maximum + 1):
            state.update(sequence=sequence, mask=changes.get(sequence, state["mask"]), polls=0, videos=0)
            core.retro_run()
            _require(not errors and state["polls"] == state["videos"] == 1, "native replay failure")
            if audio_pcm is not None:
                _require(len(audio_counts) == sequence, "missing audio callback")
                if audio_offset == len(audio_pcm):
                    _require(sequence >= max(candidates), "video outside recorded audio horizon")
                    break
        _require(set(frames) == candidates, "missing replay candidate")
        if audio_pcm is not None:
            _require(audio_offset == len(audio_pcm), "incomplete PCM replay")
    finally:
        if loaded:
            core.retro_unload_game()
        core.retro_deinit()
    _require(not errors, "native cleanup failure")
    if audio_pcm is not None:
        return frames, dict(status="pass", stage="frontend_libretro_audio_callback_pre_flush",
                            format="pcm_s16le_interleaved_stereo", sample_rate_hz=48000,
                            sample_frames=audio_offset // 4,
                            pcm_sha256=hashlib.sha256(audio_pcm).hexdigest(),
                            completed_sequences=len(audio_counts), frame_sample_counts=audio_counts)
    return frames


def _worker(request):
    core, bundle_path, invocation, identity = (request[k] for k in ("core", "bundle", "invocation", "configuration_identity"))
    bundle = _read(bundle_path, smoke.GNMV_MAX_BYTES)
    _require(smoke.is_normalized_mvs_bundle(bundle), "invalid replay bundle")
    bundle_hash = hashlib.sha256(bundle).hexdigest()
    _require(smoke.sha256(Path(core["path"])) == core["sha256"], "core identity changed")
    binding = replay_binding(core["sha256"], bundle_hash, invocation, identity)
    evidence = _evidence(core["sha256"], bundle_hash, invocation, identity)
    wanted = [_capture_rgb(cap) for cap in invocation["captures"]]
    candidates = {n for cap in invocation["captures"] for n in range(cap["successful_video_interval"][0], cap["successful_video_interval"][1] + 1)}
    changes = {r["sample_sequence"]: r["sampled_mask"] for r in invocation["observations"] if r["event_kind"] == "S"}
    pcm = _capture_pcm(invocation) if "audio" in evidence else None
    replayed = (_replay_frames(core["path"], bundle, changes, candidates) if pcm is None else
                _replay_frames(core["path"], bundle, changes, candidates, audio_pcm=pcm))
    frames, audio = (replayed, None) if pcm is None else replayed
    results = []
    for capture, rgb in zip(invocation["captures"], wanted):
        lo, hi = capture["successful_video_interval"]
        matches = [n for n in range(lo, hi + 1) if frames[n] == rgb]
        _require(matches, "complete RGB mismatch")
        _require(_capture_rgb(capture) == rgb, "capture identity changed")
        results.append(dict(capture_sha256=capture["sha256"], successful_video_interval=[lo, hi], matching_sequences=matches))
    _require(smoke.sha256(Path(core["path"])) == core["sha256"] and
             _read(bundle_path, smoke.GNMV_MAX_BYTES) == bundle, "replay identity changed")
    result = dict(policy=evidence["policy"], binding=binding, core_sha256=core["sha256"], bundle_sha256=bundle_hash,
                  captures=results, status="pass")
    if audio is not None:
        _require(_capture_pcm(invocation) == pcm, "audio identity changed")
        result["audio"] = audio
    return result


def _child(request):
    data = _canonical(request)
    _require(len(data) <= MAX_REQUEST_BYTES, "replay request budget exceeded")
    # stdin fits below the bounded request cap; stdout/stderr are drained together
    # so a noisy or crashed native library cannot block or exhaust the parent.
    import tempfile
    with tempfile.TemporaryFile() as source:
        source.write(data)
        source.seek(0)
        process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "--worker"],
                                   stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = bytearray()
        selector = selectors.DefaultSelector()
        for stream in (process.stdout, process.stderr):
            selector.register(stream, selectors.EVENT_READ)
        deadline, count = time.monotonic() + TIMEOUT_SECONDS, 0
        try:
            while selector.get_map():
                _require(time.monotonic() < deadline, "replay timeout")
                for key, _ in selector.select(min(0.1, max(0, deadline - time.monotonic()))):
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    count += len(block)
                    _require(count <= MAX_OUTPUT_BYTES, "replay output budget exceeded")
                    if key.fileobj is process.stdout:
                        output.extend(block)
            _require(process.wait(timeout=max(0.01, deadline - time.monotonic())) == 0, "replay child failure")
            return json.loads(output)
        except (ValueError, subprocess.SubprocessError):
            raise ReplayError("replay child failure") from None
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            selector.close()
            process.stdout.close()
            process.stderr.close()


def run_replay(core, bundle, invocation, configuration_identity, *, require_audio=False):
    """Execute one isolated bounded replay, returning private reviewable evidence."""
    try:
        _require(isinstance(core, dict) and isinstance(core.get("path"), str) and _hash(core.get("sha256")))
        _require(type(require_audio) is bool and
                 (not require_audio or _audio_binding(invocation) is not None), "missing audio stages")
        bundle_hash = invocation.get("selected_bundle_sha256")
        replay_binding(core["sha256"], bundle_hash, invocation, configuration_identity)
        receipt = _child(dict(core=core, bundle=str(bundle), invocation=invocation,
                              configuration_identity=configuration_identity))
        _require(validate_receipt(receipt, core["sha256"], bundle_hash, invocation, configuration_identity),
                 "invalid replay receipt")
        return receipt
    except ReplayError:
        raise
    except (OSError, TypeError, ValueError, KeyError, smoke.SmokeBlocked):
        raise ReplayError("replay unavailable") from None


def evaluate_captures_main(argv):
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate retained frontend captures without a window or native execution")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--evaluate-captures", type=Path,
                        help="explicit ignored frontend-report.json from one acquired campaign")
    modes.add_argument("--evaluate-audio-trace", type=Path,
                       help="explicit retained normal/action frontend-audio-trace.json; no playback")
    parser.add_argument("--scene-contract", required=True, type=Path)
    parser.add_argument("--sound-contract", type=Path)
    args = parser.parse_args(argv)
    if args.evaluate_audio_trace is not None:
        if args.sound_contract is None:
            parser.error("--evaluate-audio-trace requires its frozen --sound-contract")
        from tools.mvs.qualify_local_boot import evaluate_retained_frontend_audio
        result = evaluate_retained_frontend_audio(args.evaluate_audio_trace, args.scene_contract, args.sound_contract)
        print(json.dumps(result, sort_keys=True))
        return 0 if (result.get("status") == "retained_frontend_audio_evaluated" and
                     result.get("window_alignment") == "pass") else 1
    if args.sound_contract is not None:
        parser.error("--sound-contract applies only to --evaluate-audio-trace")
    from tools.mvs.qualify_local_boot import evaluate_retained_frontend_captures
    result = evaluate_retained_frontend_captures(args.evaluate_captures, args.scene_contract)
    print(json.dumps(result, sort_keys=True))
    return 0 if (result.get("status") == "retained_frontend_evaluated" and
                 result.get("predicate_results", {}).get("overall") == "pass") else 1


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        sys.path.insert(0, str(ROOT))
        sys.exit(evaluate_captures_main(sys.argv[1:]))
    try:
        _require(sys.argv[1:] == ["--worker"])
        request = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        _require(len(request) <= MAX_REQUEST_BYTES)
        result = _worker(json.loads(request))
        print(json.dumps(result, sort_keys=True))
    except Exception:
        print('{"status":"fail","error":"replay failed"}')
        sys.exit(1)
