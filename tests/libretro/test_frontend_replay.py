"""Public synthetic regressions for private sampled-input RGB replay."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib

SPEC = importlib.util.spec_from_file_location("frontend_replay", Path(__file__).resolve().parents[2] / "tools/mvs/frontend_replay.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def invocation():
    def record(kind, sample, mask, video, cycles):
        return dict(event_kind=kind, sample_sequence=sample, sampled_mask=mask,
                    successful_video_sequence=video, executed_cycles=cycles, invocation_id="test")
    return dict(invocation_id="test", selected_bundle_sha256="b" * 64,
                configuration_text="config", configuration_sha256=hashlib.sha256(b"config").hexdigest(),
                observations=[record("B", 0, 0, 0, 0), record("S", 1, 0, 0, 0),
                              record("V", 1, 0, 1, 100), record("V", 3, 0, 3, 300)],
                captures=[dict(path="capture.png", sha256="c" * 64, successful_video_interval=[1, 3], target_frame=1)])


def receipt(inv):
    return dict(policy=replay.POLICY, binding=replay.replay_binding("a" * 64, "b" * 64, inv, "configuration"),
                core_sha256="a" * 64, bundle_sha256="b" * 64, status="pass",
                captures=[dict(capture_sha256=inv["captures"][0]["sha256"], successful_video_interval=[1, 3], matching_sequences=[1, 2, 3])])


class ReplayTests(unittest.TestCase):
    def test_manual_interval_policy_does_not_expand_strict_admission(self):
        inv = invocation()
        inv['observations'][-1].update(sample_sequence=33, successful_video_sequence=33, executed_cycles=3300)
        inv['captures'][0]['successful_video_interval'] = [1, 33]
        with self.assertRaises(replay.ReplayError):
            replay.replay_binding('a'*64, 'b'*64, inv, 'configuration')
        inv.update(input_mode='manual', hybrid_policy='frontend_joint_delivery_human_semantics_v1',
                   hybrid_machine_identity='d'*64)
        evidence = replay._evidence('a'*64, 'b'*64, inv, 'configuration')
        self.assertEqual(replay.MANUAL_POLICY, evidence['policy'])
        for key, bad in [('hybrid_policy','strict'), ('hybrid_machine_identity','stale'), ('input_mode','scripted')]:
            broken = copy.deepcopy(inv); broken[key] = bad
            with self.assertRaises(replay.ReplayError):
                replay.replay_binding('a'*64, 'b'*64, broken, 'configuration')
        inv['observations'][-1].update(sample_sequence=66, successful_video_sequence=66, executed_cycles=6600)
        inv['captures'][0]['successful_video_interval'] = [1, 66]
        with self.assertRaises(replay.ReplayError):
            replay.replay_binding('a'*64, 'b'*64, inv, 'configuration')

    def test_receipt_rejects_changed_implementation_sources(self):
        inv = invocation()
        original = receipt(inv)
        self.assertTrue(replay.validate_receipt(original, "a" * 64, "b" * 64, inv, "configuration"))
        identity = replay._implementation_identity()
        self.assertEqual(set(identity), {"helper", "collector", "evaluator"})
        for component in identity:
            changed = dict(identity, **{component: "0" * 64})
            with self.subTest(component=component), mock.patch.object(replay, "_implementation_identity", return_value=changed):
                self.assertFalse(replay.validate_receipt(original, "a" * 64, "b" * 64, inv, "configuration"))

    def test_retained_receipt_checks_original_binding_without_executing_or_refreshing(self):
        inv = invocation()
        original_identity = replay._implementation_identity()
        original = receipt(inv)
        with mock.patch.object(replay, "_implementation_identity", return_value={
                name: "0" * 64 for name in original_identity}), \
                mock.patch.object(replay, "_child", side_effect=AssertionError("no execution")):
            self.assertFalse(replay.validate_receipt(original, "a" * 64, "b" * 64, inv, "configuration"))
            self.assertTrue(replay.validate_retained_receipt(
                original, "a" * 64, "b" * 64, inv, "configuration", original_identity))
            for mutate in (
                    lambda i: i["observations"][-1].update(executed_cycles=301),
                    lambda i: i["captures"][0].update(sha256="d" * 64),
                    lambda i: i.update(configuration_sha256="d" * 64)):
                changed = copy.deepcopy(inv); mutate(changed)
                self.assertFalse(replay.validate_retained_receipt(
                    original, "a" * 64, "b" * 64, changed, "configuration", original_identity))
            for bad in ({}, dict(original_identity, helper="invalid"),
                        dict(original_identity, helper="0" * 64)):
                self.assertFalse(replay.validate_retained_receipt(
                    original, "a" * 64, "b" * 64, inv, "configuration", bad))
        self.assertEqual(original, receipt(inv), "retained evaluation must not rewrite acquisition")

    def test_binding_covers_complete_input_and_configuration_and_capture(self):
        original = invocation()
        binding = receipt(original)["binding"]
        for field, value in (("path", "other.png"), ("sha256", "d" * 64), ("target_frame", 2)):
            changed = copy.deepcopy(original)
            changed["captures"][0][field] = value
            self.assertNotEqual(binding, replay.replay_binding("a" * 64, "b" * 64, changed, "configuration"))
        changed = copy.deepcopy(original)
        changed["observations"][-1]["executed_cycles"] += 1
        self.assertNotEqual(binding, replay.replay_binding("a" * 64, "b" * 64, changed, "configuration"))
        self.assertNotEqual(binding, replay.replay_binding("a" * 64, "b" * 64, original, "other"))

    def test_read_only_receipt_preserves_all_repeated_matches_and_rejects_mutation(self):
        inv = invocation()
        result = receipt(inv)
        with mock.patch.object(replay, "_child", side_effect=AssertionError("must not execute")):
            self.assertTrue(replay.validate_receipt(result, "a" * 64, "b" * 64, inv, "configuration"))
        for matches in ([], [0], [4], [True], [1, 1], [3, 1], "1"):
            bad = copy.deepcopy(result)
            bad["captures"][0]["matching_sequences"] = matches
            self.assertFalse(replay.validate_receipt(bad, "a" * 64, "b" * 64, inv, "configuration"))
        for key in ("binding", "core_sha256", "bundle_sha256", "policy", "status"):
            bad = copy.deepcopy(result)
            bad[key] = "changed"
            self.assertFalse(replay.validate_receipt(bad, "a" * 64, "b" * 64, inv, "configuration"))

    def test_hostile_history_and_intervals_fail_before_execution(self):
        for mutate in (
                lambda i: i["observations"].pop(0),
                lambda i: i["observations"].pop(1),
                lambda i: i["observations"][1].update(sample_sequence=2),
                lambda i: i["observations"][-1].update(sample_sequence=4),
                lambda i: i["observations"][-1].update(sampled_mask=1),
                lambda i: i["observations"][-1].update(invocation_id="stale"),
                lambda i: i["observations"][-1].update(successful_video_sequence=8193, sample_sequence=8193),
                lambda i: i["captures"][0].update(successful_video_interval=[1, 14]),
                lambda i: i["captures"][0].update(successful_video_interval=[2, 3]),
                lambda i: i.update(captures=i["captures"] * 7),
                lambda i: i.update(configuration_text="changed")):
            inv = invocation()
            mutate(inv)
            with self.subTest(inv=inv), mock.patch.object(replay, "_child") as child:
                with self.assertRaises(replay.ReplayError):
                    replay.run_replay(dict(path="core", sha256="a" * 64), Path("bundle"), inv, "configuration")
                child.assert_not_called()

    def test_interval_width_boundary(self):
        inv = invocation()
        inv["observations"][-1].update(sample_sequence=13, successful_video_sequence=13)
        inv["captures"][0]["successful_video_interval"] = [1, 13]
        replay.replay_binding("a" * 64, "b" * 64, inv, "configuration")
        inv["observations"][-1].update(sample_sequence=14, successful_video_sequence=14)
        inv["captures"][0]["successful_video_interval"] = [1, 14]
        with self.assertRaises(replay.ReplayError):
            replay.replay_binding("a" * 64, "b" * 64, inv, "configuration")

    def test_png_complete_rgb_and_rgba_and_bad_crc(self):
        def png(channels):
            def chunk(kind, data):
                return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
            return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 320, 224, 8, 2 if channels == 3 else 6, 0, 0, 0)) +
                    chunk(b"IDAT", zlib.compress((b"\0" + bytes([1, 2, 3] + ([255] if channels == 4 else [])) * 320) * 224)) + chunk(b"IEND", b""))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.png"
            for channels in (3, 4):
                raw = png(channels)
                path.write_bytes(raw)
                capture = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())
                self.assertEqual(replay._capture_rgb(capture), bytes([1, 2, 3]) * (320 * 224))
                with self.assertRaises(replay.ReplayError):
                    replay._capture_rgb(dict(capture, sha256="a" * 64))
                corrupt = raw[:-1] + bytes([raw[-1] ^ 1])
                path.write_bytes(corrupt)
                with self.assertRaises(replay.ReplayError):
                    replay._capture_rgb(dict(capture, sha256=hashlib.sha256(corrupt).hexdigest()))

    def test_worker_matches_every_candidate_and_preserves_all_matches(self):
        inv = invocation()
        core = dict(path="core", sha256="a" * 64)
        request = dict(core=core, bundle="bundle", invocation=inv, configuration_identity="configuration")
        blob = b"bundle"
        inv["selected_bundle_sha256"] = hashlib.sha256(blob).hexdigest()
        with mock.patch.object(replay, "_read", return_value=blob), \
                mock.patch.object(replay.smoke, "sha256", return_value="a" * 64), \
                mock.patch.object(replay.smoke, "is_normalized_mvs_bundle", return_value=True), \
                mock.patch.object(replay, "_capture_rgb", return_value=b"rgb"), \
                mock.patch.object(replay, "_replay_frames", return_value={1: b"rgb", 2: b"rgb", 3: b"rgb"}) as run:
            result = replay._worker(request)
            self.assertEqual(result["captures"][0]["matching_sequences"], [1, 2, 3])
            self.assertEqual(run.call_args.args[2:], ({1: 0}, {1, 2, 3}))
            run.return_value = {1: b"bad", 2: b"bad", 3: b"bad"}
            with self.assertRaises(replay.ReplayError):
                replay._worker(request)

    def test_subprocess_invalid_request_exits_with_finite_failure(self):
        with self.assertRaisesRegex(replay.ReplayError, "replay child failure"):
            replay._child({"private_path": "do-not-emit"})

    def test_native_callback_contract_and_exception_latching(self):
        import ctypes as c
        class Function:
            def __init__(self, action):
                self.action = action
            def __call__(self, *args):
                return self.action(*args)

        def core_for(mode):
            callbacks = {}
            raw = c.create_string_buffer(bytes([3, 2, 1, 0]) * (320 * 224))
            core = type("Core", (), {})()
            for name in ("environment", "video_refresh", "input_poll", "input_state", "audio_sample_batch"):
                setattr(core, "retro_set_" + name, Function(lambda cb, name=name: callbacks.update({name: cb})))
            core.retro_init = Function(lambda: None)
            def load(game):
                pixel_format = c.c_int(0 if mode == "format" else 1)
                callbacks["environment"](10, c.byref(pixel_format))
                return True
            core.retro_load_game = Function(load)
            def run():
                callbacks["input_poll"]()
                if mode == "double_poll":
                    callbacks["input_poll"]()
                callbacks["input_state"](0, 1, 0, 2)
                if mode == "invalid_input":
                    callbacks["input_state"](9, 1, 0, 2)
                if mode == "no_video":
                    return
                callbacks["video_refresh"](None if mode == "null" else c.cast(raw, c.c_void_p),
                                             321 if mode == "geometry" else 320, 224, 1280)
            core.retro_run = Function(run)
            core.retro_unload_game = Function(lambda: None)
            core.retro_deinit = Function(lambda: None)
            return core
        with mock.patch.object(replay.c, "CDLL", return_value=core_for("valid")):
            frames = replay._replay_frames("core", b"bundle", {1: 0}, {1, 2})
            self.assertEqual(frames, {1: bytes([1, 2, 3]) * (320 * 224), 2: bytes([1, 2, 3]) * (320 * 224)})
        for mode in ("format", "double_poll", "invalid_input", "no_video", "null", "geometry"):
            with self.subTest(mode=mode), mock.patch.object(replay.c, "CDLL", return_value=core_for(mode)):
                with self.assertRaises(replay.ReplayError):
                    replay._replay_frames("core", b"bundle", {1: 0}, {1})

    def test_audio_binding_requires_stages_contract_converter_and_complete_receipt(self):
        import wave
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "capture.wav"
            block = struct.pack("<hhhh",17,-19,23,-29)
            with wave.open(str(path), "wb") as stream:
                stream.setparams((2,2,48000,0,"NONE","not compressed")); stream.writeframes(block*3)
            modified = path.stat().st_mtime_ns
            capture = replay.smoke.parse_frontend_audio_capture(
                path, owned_directory=root, started_ns=modified-1, finished_ns=modified+1)
            capture["recording_relative_path"] = "capture.wav"
            log = root / "driver.log"
            log.write_text("[CoreAudio3] Using buffer size of 3840 bytes: (latency = 20 ms).\n"
                           "Started synchronous audio driver\n")
            route = replay.smoke.parse_frontend_audio_route(log,control="normal")
            inv = invocation(); inv["captures"][0]["path"] = str(root / "capture.png")
            inv["audio_evidence"] = dict(capture=capture, route=route, delivery=dict(
                status="pass", stage="adapter_callback_return_totals", generated=6,submitted=6,
                processed=6,discarded=0,overreports=0))
            inv["audio_replay_context"] = dict(scene_contract_sha256="d"*64,
                sound_contract_sha256="e"*64, schedule_identity="f"*64,control="normal",
                converter_identity={"board":"1"*64,"chip":"2"*64})
            self.assertEqual(replay._capture_pcm(inv),block*3)
            result = receipt(inv); result["policy"] = replay.AUDIO_POLICY
            result["audio"] = dict(status="pass",stage=capture["stage"],format=capture["format"],
                sample_rate_hz=48000,sample_frames=6,pcm_sha256=capture["pcm_sha256"],
                completed_sequences=3,frame_sample_counts=[2,2,2])
            self.assertTrue(replay.validate_receipt(result,"a"*64,"b"*64,inv,"configuration"))
            for field, value in (("frame_sample_counts",[2,2]),("frame_sample_counts",[2,2,3]),
                                 ("frame_sample_counts",[True,2,3]),("completed_sequences",2),
                                 ("stage","device"),("pcm_sha256","0"*64)):
                bad=copy.deepcopy(result); bad["audio"][field]=value
                self.assertFalse(replay.validate_receipt(bad,"a"*64,"b"*64,inv,"configuration"))
            for mutate in (
                    lambda i: i["audio_evidence"].pop("delivery"),
                    lambda i: i["audio_evidence"]["capture"].update(stage="device"),
                    lambda i: i["audio_evidence"]["capture"].update(sample_rate_hz=44100),
                    lambda i: i["audio_evidence"]["capture"].update(recording_relative_path="../capture.wav"),
                    lambda i: i["audio_replay_context"].pop("converter_identity"),
                    lambda i: i["audio_replay_context"].update(control="disabled"),
                    lambda i: i["audio_replay_context"].update(sound_contract_sha256="0"*64)):
                bad=copy.deepcopy(inv); mutate(bad)
                self.assertFalse(replay.validate_receipt(result,"a"*64,"b"*64,bad,"configuration"))
            with mock.patch.object(replay,"_child") as child:
                with self.assertRaises(replay.ReplayError):
                    replay.run_replay(dict(path="core",sha256="a"*64),Path("bundle"),
                                      invocation(),"configuration",require_audio=True)
                child.assert_not_called()
            # The pinned WAV recorder can restart under RetroArch's default .mkv
            # filename. Container metadata, not the suffix, determines format.
            restarted=root/"recordings"/"restart.mkv"; restarted.parent.mkdir()
            path.rename(restarted); path=restarted
            capture["recording_relative_path"]="recordings/restart.mkv"
            self.assertEqual(replay._capture_pcm(inv),block*3)
            # A changed recorder with retained metadata must fail before any core load.
            path.write_bytes(path.read_bytes()[:-4])
            with self.assertRaises(replay.ReplayError): replay._capture_pcm(inv)

    def test_audio_replay_matches_complete_callback_bytes_at_an_actual_frame_boundary(self):
        import ctypes as c
        class Function:
            def __init__(self, action): self.action = action
            def __call__(self, *args): return self.action(*args)
        callbacks = {}
        core = type("Core", (), {})()
        pixels = c.create_string_buffer(bytes([3, 2, 1, 0]) * (320 * 224))
        samples = (c.c_int16 * 4)(17, -19, 23, -29)
        block = struct.pack("<hhhh", 17, -19, 23, -29)
        for name in ("environment", "video_refresh", "input_poll", "input_state", "audio_sample_batch"):
            setattr(core, "retro_set_" + name, Function(lambda cb, name=name: callbacks.update({name: cb})))
        core.retro_init = Function(lambda: None)
        def load(game):
            format_ = c.c_int(1)
            callbacks["environment"](10, c.byref(format_)); return True
        core.retro_load_game = Function(load)
        def run():
            callbacks["input_poll"](); callbacks["input_state"](0, 1, 0, 2)
            callbacks["video_refresh"](c.cast(pixels,c.c_void_p),320,224,1280)
            callbacks["audio_sample_batch"](samples,2)
        core.retro_run = Function(run)
        core.retro_unload_game = Function(lambda: None)
        core.retro_deinit = Function(lambda: None)
        with mock.patch.object(replay.c, "CDLL", return_value=core):
            frames, audio = replay._replay_frames(
                "core", b"original", {1:0}, {1}, audio_pcm=block * 3)
            self.assertEqual(audio["completed_sequences"],3)
            self.assertEqual(audio["sample_frames"],6)
            self.assertEqual(audio["pcm_sha256"],hashlib.sha256(block*3).hexdigest())
            self.assertEqual(audio["frame_sample_counts"],[2,2,2])
            self.assertEqual(set(frames),{1})
            for invalid in (block*3+b"xx", block*3+b"\0\0\0\0", b"\0"*24):
                with self.assertRaises(replay.ReplayError):
                    replay._replay_frames("core",b"original",{1:0},{1},audio_pcm=invalid)
            with self.assertRaises(replay.ReplayError):
                replay._replay_frames("core",b"original",{1:0},{4},audio_pcm=block*3)

    def test_child_timeout_output_overflow_and_crash_are_failures(self):
        import subprocess
        original = subprocess.Popen
        for script, settings in (
                ("import time; time.sleep(1)", {"TIMEOUT_SECONDS": 0.01}),
                ("print('x'*10000)", {"MAX_OUTPUT_BYTES": 100}),
                ("import os, signal; os.kill(os.getpid(), signal.SIGKILL)", {"TIMEOUT_SECONDS": 1})):
            def child(*args, **kwargs):
                return original([sys.executable, "-c", script], **kwargs)
            with self.subTest(script=script), mock.patch.object(replay.subprocess, "Popen", side_effect=child), \
                    mock.patch.multiple(replay, **settings):
                with self.assertRaises(replay.ReplayError):
                    replay._child({})

    def test_compiled_original_core_exercises_ctypes_callbacks_in_child(self):
        compiler = shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler unavailable")
        # Original public fixture: no game bytes, dependencies, or host devices.
        source = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
static bool (*env)(unsigned, void*);
static void (*video)(const void*, unsigned, unsigned, size_t);
static void (*poll)(void);
static int16_t (*input)(unsigned, unsigned, unsigned, unsigned);
static size_t (*audio)(const int16_t*, size_t);
static uint32_t pixels[320*224];
void retro_set_environment(bool (*f)(unsigned, void*)) { env=f; }
void retro_set_video_refresh(void (*f)(const void*,unsigned,unsigned,size_t)) { video=f; }
void retro_set_input_poll(void (*f)(void)) { poll=f; }
void retro_set_input_state(int16_t (*f)(unsigned,unsigned,unsigned,unsigned)) { input=f; }
void retro_set_audio_sample_batch(size_t (*f)(const int16_t*,size_t)) { audio=f; }
void retro_init(void) { }
bool retro_load_game(const void *game) { int format=1; (void)game; return env(10,&format); }
void retro_run(void) {
  poll(); uint32_t rgb=input(0,1,0,2) ? 0x00010203 : 0x00040506;
  for(unsigned i=0;i<320*224;i++) pixels[i]=rgb;
  static const int16_t samples[4]={17,-19,23,-29};
  video(pixels,320,224,1280); audio(samples,2);
}
void retro_unload_game(void) { }
void retro_deinit(void) { }
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "core.c").write_text(source)
            library = path / ("core.dylib" if sys.platform == "darwin" else "core.so")
            result = subprocess.run([compiler, "-shared", "-fPIC", str(path / "core.c"), "-o", str(library)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            self.assertEqual(result.returncode, 0, "original C fixture must compile")
            code = ("import sys; sys.path.insert(0,sys.argv[1]); import frontend_replay as r; "
                    "frames=r._replay_frames(sys.argv[2],b'original',{1:0,2:1},{1,2,3}); "
                    "assert frames[1]==bytes([4,5,6])*(320*224); "
                    "assert frames[2]==frames[3]==bytes([1,2,3])*(320*224); "
                    "import struct; pcm=struct.pack('<hhhh',17,-19,23,-29)*3; "
                    "frames,a=r._replay_frames(sys.argv[2],b'original',{1:0,2:1},{1,2,3},audio_pcm=pcm); "
                    "assert a['frame_sample_counts']==[2,2,2] and a['sample_frames']==6")
            result = subprocess.run([sys.executable, "-B", "-c", code, str(replay.ROOT / "tools/mvs"), str(library)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(result.returncode, 0, "isolated original C callback replay must pass")
            # Decode the producer's keyed wire data independently, accounting
            # for the pinned CLI's one neutral guest bootstrap before record1.
            code = ("import sys,struct; sys.path.insert(0,sys.argv[1]); import frontend_replay as r; "
                    "m=[0,1,1,0]; b=r.smoke.mvs_input_replay_bytes(m,dense_from=2,dense_until=3); "
                    "decoded=[0]+[struct.unpack_from('<h',b,40+i*132+3+2*8+6)[0] for i in range(3)]; "
                    "assert decoded==m; changes={i+1:v for i,v in enumerate(decoded)}; "
                    "f=r._replay_frames(sys.argv[2],b'original',changes,{1,2,3,4}); "
                    "assert f[1]==f[4]==bytes([4,5,6])*(320*224); "
                    "assert f[2]==f[3]==bytes([1,2,3])*(320*224)")
            result = subprocess.run([sys.executable, "-B", "-c", code, str(replay.ROOT / "tools/mvs"), str(library)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(result.returncode, 0, "input-only producer must drive multiple actual C callbacks")


class ContinuationReplayAlignmentTests(unittest.TestCase):
    def test_restore_alignment_uses_only_samples_after_the_load_boundary(self):
        align = getattr(replay, "continuation_alignment", None)
        self.assertTrue(callable(align), "saved-state replay needs a distinct post-load alignment check")
        records = [dict(event_kind="B", sample_sequence=0, sampled_mask=0,
                        successful_video_sequence=0, executed_cycles=0,
                        invocation_id="restored")]
        records.append(dict(event_kind="S", sample_sequence=1, sampled_mask=0,
                            successful_video_sequence=0, executed_cycles=0,
                            invocation_id="restored"))
        sample = 1
        for video in range(1, 11):
            sample += 1
            records.append(dict(event_kind="V", sample_sequence=sample, sampled_mask=0,
                                successful_video_sequence=video, executed_cycles=video * 100,
                                invocation_id="restored"))
        masks = [64, 0, 0, 0]
        current_mask = 0
        video = 10
        cycles = 1000
        for mask, next_video in ((64, 11), (0, 14), (0, 16)):
            if mask != current_mask:
                sample += 1
                records.append(dict(event_kind="S", sample_sequence=sample, sampled_mask=mask,
                                    successful_video_sequence=video, executed_cycles=cycles,
                                    invocation_id="restored"))
                current_mask = mask
            else:
                sample += 1
            video = next_video
            cycles = video * 100
            records.append(dict(event_kind="V", sample_sequence=sample, sampled_mask=mask,
                                successful_video_sequence=video, executed_cycles=cycles,
                                invocation_id="restored"))
        frames = [dict(input_mask=mask) for mask in masks]
        evidence = align(records, frames, invocation_id="restored", after_video_sequence=10)
        self.assertEqual(evidence["sampled_masks"], masks)
        self.assertEqual(evidence["video_interval"], [11, 16])
        self.assertEqual(evidence["observed_input_transitions"], [64, 0])
        with self.assertRaises(replay.ReplayError):
            align(records, [dict(input_mask=1), *frames[1:]],
                  invocation_id="restored", after_video_sequence=10)


if __name__ == "__main__":
    unittest.main()
