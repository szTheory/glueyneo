"""Bounded live gameplay lane. No launch without an explicit readiness flag.

This does not run the scripted acceptance campaign or manufacture human feedback.
All paths/output are private. Existing strict qualification remains the default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid
import subprocess

from tools.mvs import hybrid_acceptance as h
from tools.mvs import qualify_local_boot as q

ACTIVE_FRAMES = 1800
CAPTURES = [450, 900, 1500]
MAX_CHANGES = 32


def budget(prefix=47, changes=MAX_CHANGES):
    # Each change emits S + pending V + context V at ages4/8. Periodic
    # callbacks can overlap those; counting them again is conservative.
    # The prefix includes boot/R/P; future input-change costs are conservative.
    return prefix + (ACTIVE_FRAMES + 128 + 31) // 32 + 4 * changes


def instructions(configuration):
    """Read the actual prepared config; never guess a host keyboard mapping."""
    import re
    settings = dict(re.findall(r'^([a-z0-9_]+) = "([^"\n]*)"$', configuration, re.M))
    return {"move_left": settings["input_player1_left"],
            "move_right": settings["input_player1_right"],
            "fire": settings["input_player1_b"],
            "coin": settings["input_player1_select"], "start": settings["input_player1_start"],
            "actions": ["Press 1 for coin, then 2 to start.", "Move using the left/right keys.",
                        "While moving, hold the fire key briefly.",
                        "Release all keys and wait for automatic closure."],
            "feedback": ["Did movement and firing work together? pass / fail / unknown",
                         "If not, briefly describe what happened."],
            "session_seconds_ceiling": 120,
            "active_frames": ACTIVE_FRAMES,
            "note": "Frame horizon is not a measured duration or promised play time."}


def prepare(machine, output):
    output = output.resolve()
    smoke = q._load_retroarch_smoke()
    if output.exists() or not q.ignored(output):
        raise ValueError("fresh ignored output required")
    output.mkdir(parents=True)
    captures = output / "captures"; captures.mkdir()
    config = smoke.write_frontend_config(output, captures, direct_log=True)
    with config.open("a") as stream:
        stream.write('config_save_on_exit = "false"\nquit_press_twice = "false"\n'
                     'threaded_data_runloop_enable = "false"\ninput_exit_emulator = "escape"\n')
    plan = {"policy": h.POLICY, "stage": "gameplay_preparation",
            "machine_identity": machine.get("machine_identity"),
            "machine_status": machine.get("machine_status", "unknown"),
            "status": "pending_machine_validation", "launch_authorized": False,
            "instructions": instructions(config.read_text()),
            "budget": {"source_records": budget(), "source_cap": 255,
                       "collector_cap": 256, "changes": MAX_CHANGES,
                       "safety_frames": 8192, "wall_seconds": 120},
            "configuration_sha256": hashlib.sha256(config.read_bytes()).hexdigest()}
    plan["human_participation_history"] = "Prior attempts are history, not a lifetime limit."
    if budget() > 255:
        raise ValueError("manual record budget does not fit")
    (output / "gameplay-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


def run(args, machine):
    """Run only after fresh machine validation AND actual user readiness.

    Callers must refresh the machine receipt before this function; a JSON pass
    string alone is deliberately insufficient to launch from this CLI.
    """
    args.output = args.output.resolve()
    diagnostic = getattr(args, "automated_diagnostic", False)
    if not args.ready and not diagnostic:
        raise ValueError("actual user readiness required")
    sealed = machine.get('machine_identity') == h.identity({k:v for k,v in machine.items() if k!='machine_identity'})
    certificate = None
    compatible = False
    if getattr(args,'revalidation',None) is not None:
        from tools.mvs.hybrid_revalidation import validated_bridge
        certificate = json.loads(Path(args.revalidation).read_text())
        compatible = validated_bridge(machine,certificate)
    if not h.machine_is_current(machine) and not compatible and not (diagnostic and sealed and machine.get('machine_status')=='pass'):
        raise ValueError("fresh hybrid machine acquisition required before live launch")
    smoke = q._load_retroarch_smoke()
    iid = args.output.name.removeprefix("run-")
    import re
    if (re.fullmatch(r"[0-9a-f]{32}", iid) is None or
        args.output.parent.resolve() != (q.PROJECT_ROOT / q.PHASE06_RUN_ROOT).resolve()):
        raise ValueError("manual output must be a fresh canonical run directory")
    if not all((args.core, args.content, args.retroarch)):
        raise ValueError("explicit owned frontend/core/content required")
    args.timeout = 120
    args.capture_dir = args.output / "captures"
    args.child_pid_file = args.output / "owned-child.pid"
    executable, core, content, app = smoke.validate_inputs(args)
    if app != machine["expected_app_identity"]:
        raise ValueError("current frontend/core identity differs from machine acquisition")
    if (hashlib.sha256(content.read_bytes()).hexdigest() != machine.get("expected_bundle_sha256")):
        raise ValueError("manual media differs from machine acquisition")
    plan = prepare(machine, args.output)
    manual_cfg = q._frontend_configuration_identity((args.output / "retroarch.cfg").read_text(),
        work_directory=args.output, capture_directory=args.capture_dir.resolve())
    if manual_cfg != machine["expected_manual_configuration_identity"]:
        raise ValueError("manual configuration was not bound before machine acquisition")
    print(json.dumps(plan["instructions"]), flush=True)
    assertion = None
    retained = {"policy": h.POLICY, "status": "incomplete", "machine_identity": machine["machine_identity"],
                "session_kind": "automated_diagnostic" if diagnostic else "human_gameplay"}
    if certificate is not None:
        retained['machine_revalidation'] = certificate
    session_record = args.output / "human-participation.json"
    try:
        assertion = subprocess.Popen(["/usr/bin/caffeinate", "-d", "-i", "-t", "120"])
        def handoff(origin):
            if not diagnostic:
                with session_record.open("x") as stream:
                    json.dump({"status": "handed_off", "history_only": True,
                    "invocation_id": iid, "machine_identity": machine["machine_identity"]}, stream)
            print("FROM BOOT: 1 coin, 2 start; move with " + plan["instructions"]["move_left"] + "/" + plan["instructions"]["move_right"] + "; " + plan["instructions"]["fire"] + " fires.", flush=True)
        actual = smoke._run_mvs_active_scene_impl(args,
            {"events": [], "capture_frames": CAPTURES, "active_frames": ACTIVE_FRAMES},
            invocation_id=iid, manual_handoff=handoff)
        actual["owned_child_reaped"] = True
        actual.update(hybrid_policy=h.POLICY, hybrid_machine_identity=machine["machine_identity"])
        actual["replay"] = q._load_frontend_replay().run_replay(
            {"path": str(core), "sha256": hashlib.sha256(core.read_bytes()).hexdigest()},
            content, actual, manual_cfg)
        retained.update(status="complete", clean_exit=True, invocation=actual,
                        sources=q._active_frontend_sources({'sha256':hashlib.sha256(core.read_bytes()).hexdigest()}), configuration_identity=manual_cfg,
                        active_frames=ACTIVE_FRAMES)
        retained["artifact_sha256"] = h.identity({"invocation": actual,
            "sources": retained["sources"], "configuration_identity": manual_cfg,
            "machine_identity": machine["machine_identity"]})
        if not h.gameplay_session_valid(retained, machine, allow_diagnostic=diagnostic):
            retained["status"] = "incomplete"
        return retained
    except BaseException as error:
        retained["failure_type"] = type(error).__name__
        retained["private_diagnostic"] = getattr(error, "diagnostic", {})
        raise
    finally:
        if assertion is not None:
            assertion.terminate(); assertion.wait(timeout=5)
        (args.output / "manual-session.json").write_text(json.dumps(retained, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ready", action="store_true")
    parser.add_argument("--automated-diagnostic", action="store_true")
    parser.add_argument("--revalidation",type=Path)
    parser.add_argument("--retroarch", type=Path)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--content", type=Path)
    args = parser.parse_args()
    machine = json.loads(args.machine.read_text())
    if args.ready or args.automated_diagnostic:
        run(args, machine)
    else:
        plan = prepare(machine, args.output)
        print(json.dumps({"stage": plan["stage"], "status": plan["status"],
                          "launch_authorized": False, "records_bound": budget()}))


if __name__ == "__main__":
    main()
