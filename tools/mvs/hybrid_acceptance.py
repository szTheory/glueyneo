"""Prospective hybrid policy. Strict evaluator/receipts remain unchanged.

Machine calibration is never aggregate acceptance. Human feedback cannot turn
a failed machine gate into a pass, or establish hardware/player-coordinate truth.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
from pathlib import Path

from tools.mvs import qualify_local_boot as q

POLICY = "frontend_joint_delivery_human_semantics_v1"
RETAINED = ("scene", "composition", "right", "left", "projectile", "release", "scroll")


def joint_mask():
    header = (q.PROJECT_ROOT / "include/glueyneo/glueyneo.h").read_text()
    def bit(name):
        return int(re.search(r"#define " + name + r" UINT32_C\((0x[0-9a-fA-F]+)\)", header)[1], 16)
    return bit("GN_MVS_INPUT_P1_RIGHT") | bit("GN_MVS_INPUT_P1_A")


def source_identity():
    return {str(p.relative_to(q.PROJECT_ROOT)): q._sha256_path(p) for p in (
        Path(__file__), Path(q.__file__), q.PROJECT_ROOT / "tests/libretro/retroarch_smoke.py",
        q.PROJECT_ROOT / "tools/mvs/frontend_replay.py",
        q.PROJECT_ROOT / "tools/mvs/hybrid_gameplay.py",
        q.PROJECT_ROOT / "tools/mvs/hybrid_qualification.py",
        q.PROJECT_ROOT / "include/glueyneo/glueyneo.h")}


def prepare_acquisition(contract, sources, configuration_identity, app_identity,
                        manual_configuration_identity=None):
    """Write this intent before acquisition; legacy reports have no such binding."""
    return {"policy": POLICY, "policy_contract_identity": identity(derive_contract(contract)),
            "acquisition_id": secrets.token_hex(16), "sources": copy.deepcopy(sources),
            "configuration_identity": configuration_identity,
            "manual_configuration_identity": manual_configuration_identity or configuration_identity,
            "app_identity": copy.deepcopy(app_identity), "implementation": source_identity()}


def frame_set_identity(runs):
    def encode(value):
        if isinstance(value, bytes):
            return {"rgb_sha256": hashlib.sha256(value).hexdigest()}
        if isinstance(value, dict):
            return {key: encode(item) for key, item in value.items()}
        if isinstance(value, list):
            return [encode(item) for item in value]
        return value
    return identity(encode(runs))


def _owned_capture(capture, iid):
    if not isinstance(iid, str) or re.fullmatch(r"[0-9a-f]{32}", iid) is None:
        return False
    path = Path(capture["path"])
    owner = q.PROJECT_ROOT / q.PHASE06_RUN_ROOT / ("run-" + iid) / "captures"
    return (not path.is_symlink() and path.is_file() and q.ignored(path) and
            path.resolve().is_relative_to(owner.resolve()) and
            q._sha256_path(path) == capture["sha256"])


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def derive_contract(strict_contract):
    """Create a distinct policy identity without modifying the frozen contract."""
    return {"schema_version": 1, "policy": POLICY,
            "strict_contract_identity": identity(strict_contract),
            "retained_frontend_predicates": list(RETAINED),
            "combined_projectile_required": True,
            "human_question": "Did the character visibly move while firing, with both actions working together?",
            "human_outcomes": ["pass", "fail", "unknown"],
            "implementation": source_identity(),
            "human_seconds_ceiling": 120}


def _projectile(contract, runs):
    try:
        schedule = contract["schedule"]
        parsed = q._active_scene_schedule_masks(schedule)
        samples = runs["combined"]
        if not q._scene_complete_samples(samples, ("action", "control")):
            return False
        start = parsed["combined"]["action"][0][0]
        release = parsed["combined"]["action"][-1][0]
        held = [i for i, f in enumerate(schedule["pairs"]["combined"]["capture_frames"])
                if start <= f < release]
        return q._scene_projectile_track(contract, samples["action"], samples["control"], held,
            minimum_pixels=contract["predicates"]["combined"]["min_projectile_pixels"]) is not None
    except (KeyError, TypeError, ValueError):
        return False


def machine_calibration(contract, runs, invocations, sources, configuration_identity,
                        expected_app_identity, native_contract, native_runs, *,
                        acquisition=None, native_evidence=None):
    """Evaluate raw evidence, not caller-supplied frontend pass booleans.

    Caller supplies current identities exactly as the maintained qualification
    runner does. All captures are rehashed/decoded here; replay ancestry is
    validated against those same owned screenshot bytes and input observations.
    """
    frontend_contract = {**contract, "schedule": contract.get("frontend", {}).get("schedule", contract.get("schedule"))}
    strict = q._evaluate_active_frontend_pairs(frontend_contract, runs, invocations,
                                              sources, configuration_identity)
    gates = {name: strict.get(name, "unknown") for name in RETAINED}
    gates["combined_projectile"] = "pass" if _projectile(frontend_contract, runs) else "fail"
    native_predicates = q.evaluate_active_scene_pairs(native_contract, native_runs)
    native_bound = (isinstance(native_evidence, dict) and
        native_evidence.get("status") == "complete" and native_evidence.get("guest_executed") is True and
        native_evidence.get("contract_identity") == identity(native_contract) and
        native_evidence.get("runs_identity") == frame_set_identity(native_runs) and
        native_evidence.get("code_identity") == native_contract.get("code_identity") and
        native_evidence.get("media_identity") == native_contract.get("media_identity") and
        native_evidence.get("evaluator_identity") == q._production_evaluator_identity() == native_contract.get("evaluator_identity"))
    gates["native_combined"] = ("pass" if native_bound and
        q.active_scene_contract_is_valid(native_contract) and native_contract.get("frozen") is True and
        q._active_frontend_native_identity(native_contract) == q._active_frontend_native_identity(contract) and
        native_predicates.get("combined") == "pass" and native_predicates.get("overall") == "pass" else "unknown")
    valid = (q.active_scene_contract_is_valid(contract) and contract.get("frozen") is True and
             isinstance(invocations, list) and len(invocations) == 10 and
             isinstance(acquisition, dict) and acquisition.get("policy") == POLICY and
             acquisition.get("policy_contract_identity") == identity(derive_contract(contract)) and
             isinstance(acquisition.get("acquisition_id"), str) and
             re.fullmatch(r"[0-9a-f]{32}", acquisition["acquisition_id"]) is not None and
             acquisition.get("sources") == sources and acquisition.get("configuration_identity") == configuration_identity and
             acquisition.get("app_identity") == expected_app_identity and acquisition.get("implementation") == source_identity())
    seen, identifiers = set(), set()
    try:
        for row in invocations:
            pair, role, iid = row["pair"], row["role"], row["invocation_id"]
            valid = valid and ((pair, role) not in seen and iid not in identifiers and
                isinstance(iid, str) and re.fullmatch(r"[0-9a-f]{32}", iid) is not None and
                row.get("hybrid_acquisition_identity") == identity(acquisition) and
                row.get("owned_child_reaped") is True and len(row["observations"]) <= 255)
            seen.add((pair, role)); identifiers.add(iid)
            events = q._active_scene_input_events(frontend_contract["schedule"], pair, role)
            valid = valid and (row.get("status") == "complete" and
                type(row.get("frontend_exit_code")) is int and row["frontend_exit_code"] == 0 and
                row.get("identity") == expected_app_identity and
                q._active_frontend_events_valid(row, events, iid) and
                q._active_frontend_transfer_valid(row, sources, configuration_identity))
            targets = frontend_contract["schedule"]["pairs"][pair]["capture_frames"]
            valid = valid and len(row["captures"]) == len(targets)
            for index, (target, capture) in enumerate(zip(targets, row["captures"])):
                mask = next((m for f, m in reversed(events) if f <= target), 0)
                valid = valid and q.active_scene_frontend_capture_is_valid(capture,
                    row["observations"], invocation_id=iid, expected_mask=mask,
                    origin=row["active_origin_video_sequence"], target_frame=target)
                path = Path(capture["path"])
                valid = valid and _owned_capture(capture, iid)
                width, height, channels, pixels = q._load_retroarch_smoke().decode_png(path)
                if channels == 4:
                    pixels = b"".join(pixels[i:i+3] for i in range(0, len(pixels), 4))
                valid = valid and (width, height) == (320, 224) and pixels == runs[pair][role][index]
        valid = valid and q._active_frontend_temporal_bounds_valid(frontend_contract["schedule"], invocations)
        valid = valid and seen == {(p, r) for p in q._ACTIVE_SCENE_PAIR_NAMES for r in ("action", "control")}
        valid = valid and len({r["selected_bundle_sha256"] for r in invocations}) == 1
    except (KeyError, TypeError, ValueError, OSError, RuntimeError, StopIteration):
        valid = False
    gates["joint_input_transfer_lifecycle"] = "pass" if valid else "fail"
    policy_contract = derive_contract(contract)
    result = {"schema_version": 1, "policy": POLICY,
        "policy_contract_identity": identity(policy_contract),
        "strict_predicates": copy.deepcopy(strict), "machine_gates": gates,
        "evidence_identity": identity({"invocations": invocations, "sources": sources,
            "configuration": configuration_identity, "app": expected_app_identity,
            "native": native_predicates}),
        "expected_sources": copy.deepcopy(sources),
        "expected_app_identity": copy.deepcopy(expected_app_identity),
        "expected_bundle_sha256": invocations[0].get("selected_bundle_sha256") if invocations and isinstance(invocations[0], dict) else None,
        "expected_manual_configuration_identity": acquisition.get("manual_configuration_identity") if isinstance(acquisition, dict) else None,
        "acquisition": copy.deepcopy(acquisition),
        "implementation": source_identity(),
        "capture_artifacts": [{"capture": copy.deepcopy(c), "invocation_id": row["invocation_id"]}
            for row in invocations for c in row.get("captures", [])] if isinstance(invocations, list) else [],
        "stage": "machine_calibration", "human_semantics": "pending", "overall": "pending"}
    result["machine_status"] = "pass" if all(v == "pass" for v in gates.values()) else "fail"
    if result["machine_status"] != "pass":
        result["overall"] = "fail"
    result["machine_identity"] = identity(result)
    return result


def machine_is_current(machine):
    """Check the sealed, complete machine stage and its still-owned artifacts."""
    try:
        required = set(RETAINED) | {"combined_projectile", "native_combined", "joint_input_transfer_lifecycle"}
        return (machine.get("policy") == POLICY and machine.get("machine_status") == "pass" and
            machine.get("stage") == "machine_calibration" and machine.get("human_semantics") == "pending" and
            machine.get("overall") == "pending" and
            set(machine.get("machine_gates", {})) == required and
            all(v == "pass" for v in machine["machine_gates"].values()) and
            machine.get("implementation") == source_identity() and
            machine.get("machine_identity") == identity({k:v for k,v in machine.items() if k != "machine_identity"}) and
            len(machine.get("capture_artifacts", [])) == 60 and
            all(_owned_capture(a["capture"], a["invocation_id"]) for a in machine["capture_artifacts"]))
    except (KeyError, TypeError, ValueError, OSError):
        return False


def review_feedback(machine, session, feedback):
    """No cached feedback, generic yes or human override of machine failure."""
    result = copy.deepcopy(machine)
    result["stage"] = "human_semantic_review"
    result["human_semantics"] = "unknown"
    result["overall"] = "fail" if machine.get("machine_status") != "pass" else "pending"
    if machine.get("policy") != POLICY or machine.get("machine_status") != "pass":
        return result
    compatible = False
    if isinstance(session, dict) and isinstance(session.get('machine_revalidation'), dict):
        from tools.mvs.hybrid_revalidation import validated_bridge
        compatible = validated_bridge(machine, session['machine_revalidation'])
    if not machine_is_current(machine) and not compatible:
        result["overall"] = "fail"
        return result
    unsealed = {k: v for k, v in machine.items() if k != "machine_identity"}
    if machine.get("machine_identity") != identity(unsealed):
        result["overall"] = "fail"
        return result
    if not isinstance(session, dict) or not isinstance(feedback, dict):
        return result
    if (session.get("policy") != POLICY or session.get("machine_identity") != machine["machine_identity"] or
        session.get("status") != "complete" or session.get("clean_exit") is not True or
        not isinstance(session.get("artifact_sha256"), str) or
        re.fullmatch(r"[0-9a-f]{64}", session["artifact_sha256"]) is None):
        return result
    if not gameplay_session_valid(session, machine):
        return result
    if (feedback.get("policy") != POLICY or feedback.get("machine_identity") != machine["machine_identity"] or
        feedback.get("session_identity") != identity(session) or
        feedback.get("outcome") not in ("pass", "fail", "unknown") or
        type(feedback.get("viewing_seconds")) not in (int, float) or
        not 0 < feedback["viewing_seconds"] <= 120):
        return result
    result["human_semantics"] = feedback["outcome"]
    result["overall"] = {"pass": "pass", "fail": "fail", "unknown": "pending"}[feedback["outcome"]]
    return result


def gameplay_session_valid(session, machine, *, allow_diagnostic=False):
    """Validate live-session history separately from frozen scripted controls."""
    try:
        row = session["invocation"]
        sources = session["sources"]
        configuration = session["configuration_identity"]
        expected_sources = machine.get('expected_sources', {})
        if session.get('session_kind') not in ({'human_gameplay','automated_diagnostic'} if allow_diagnostic else {'human_gameplay'}):
            return False
        if (sources != q._active_frontend_sources({'sha256':expected_sources.get('core_sha256')}) or
            row.get("hybrid_policy") != POLICY or
            row.get("hybrid_machine_identity") != machine.get("machine_identity") or
            configuration != machine.get("expected_manual_configuration_identity") or
            row.get("selected_bundle_sha256") != machine.get("expected_bundle_sha256") or
            row.get("identity") != machine.get("expected_app_identity") or
            row.get("status") != "complete" or type(row.get("frontend_exit_code")) is not int or
            row["frontend_exit_code"] != 0 or row.get("owned_child_reaped") is not True or
            not q._active_frontend_transfer_valid(row, sources, configuration)):
            return False
        records = q._load_retroarch_smoke()._validated_observation_records(
            row["observations"], row["invocation_id"])
        if not records or len(records) > 255:
            return False
        begin, end = row["handoff_record_count"], row["close_record_count"]
        if type(begin) is not int or type(end) is not int or begin != 1 or not begin < end <= len(records):
            return False
        window = records[begin:end]
        changes = [r for r in window if r["event_kind"] == "S"]
        videos = [r for r in window if r["event_kind"] == "V"]
        ready = [r for r in records if r["event_kind"] == "R"]
        started = [r for r in records if r["event_kind"] == "P"]
        # The user, never automated HeldMVSKeys transitions, owns these masks.
        if (row.get("input_mode") != "manual" or row.get("manual_boot_policy") != "human_coin_start_from_boot_v1" or
            len(changes) > 32 or not videos or len(ready) != 1 or len(started) != 1 or
            ready[0]["successful_video_sequence"] > started[0]["successful_video_sequence"]):
            return False
        horizon, origin = session["active_frames"], row["active_origin_video_sequence"]
        if (type(horizon) is not int or not 1 <= horizon <= 1800 or
            type(origin) is not int or origin < 1 or
            videos[-1]["successful_video_sequence"] < origin + horizon):
            return False
        if origin != started[0]["successful_video_sequence"] or not any(
            r["event_kind"] == "S" and r["sampled_mask"] & 2 and r["sample_sequence"] <= started[0]["sample_sequence"] for r in records):
            return False
        if not any(r["successful_video_sequence"] >= origin and r["sampled_mask"] & joint_mask() == joint_mask() for r in videos):
            return False
        if len(row["captures"]) != 3:
            return False
        for capture in row["captures"]:
            path = Path(capture["path"])
            if not _owned_capture(capture, row["invocation_id"]):
                return False
            interval = capture["successful_video_interval"]
            first, last = capture["before_record_count"], capture["after_record_count"]
            if (type(first) is not int or type(last) is not int or
                not begin <= first < last <= end or
                not isinstance(interval, list) or len(interval) != 2 or
                not origin + capture["target_frame"] <= interval[0] < interval[1] <= videos[-1]["successful_video_sequence"] or
                interval[1] > origin + capture["target_frame"] + 128):
                return False
            binding = q._load_retroarch_smoke().bind_manual_gameplay_capture(
                records[:first], records[:last], invocation_id=row["invocation_id"], capture_sha256=capture["sha256"])
            if any(capture.get(key) != value for key, value in binding.items()):
                return False
            width, height, channels, pixels = q._load_retroarch_smoke().decode_png(path)
            if (width, height) != (320, 224) or channels not in (3, 4):
                return False
        bound = {"invocation": row, "sources": sources, "configuration_identity": configuration,
                 "machine_identity": machine["machine_identity"]}
        return session["artifact_sha256"] == identity(bound)
    except (KeyError, TypeError, ValueError, OSError, RuntimeError):
        return False
