"""Opt-in prospective hybrid prepare/calibrate/freeze. Never rewrites strict contract.

Acquisition uses the maintained qualifier functions through checked source seams;
this avoids duplicating their importer, bounds, input and capture implementation.
No stage in this module produces aggregate acceptance or human feedback.
"""
import argparse
import inspect
import json
from pathlib import Path
import tempfile

from tools.mvs import hybrid_acceptance as h
from tools.mvs import qualify_local_boot as q


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("maintained qualification seam changed")
    return source.replace(old, new)


def derived_sources():
    native = inspect.getsource(q.run_active_scene)
    native = replace_once(native, '    outcomes = evaluate_active_scene_pairs(contract, runs)',
        '    hybrid_native_sink.update(runs=runs, contract=contract)\n    outcomes = evaluate_active_scene_pairs(contract, runs)')
    frontend = inspect.getsource(q.run_active_scene_frontend)
    frontend = replace_once(frontend, 'actual = smoke.run_mvs_active_scene(', 'actual = hybrid_owned_run(')
    start = frontend.index('    if calibrate and written:')
    end = frontend.index('    return {"status":', start)
    frontend = frontend[:start] + frontend[end:]
    frontend = replace_once(frontend, '    written = write_report(report_directory / "frontend-report.json", report)',
        '    hybrid_frontend_sink.update(contract=contract, runs=runs, invocations=invocations, sources=sources, configuration=configuration_identity)\n    written = write_report(report_directory / "frontend-report.json", report)')
    return native, frontend


def prepare(strict_path, output):
    if output.exists() or not q.ignored(output):
        raise ValueError("fresh ignored output required")
    status, contract = q.validate_scene_contract(strict_path)
    if contract is None:
        raise ValueError(status)
    output.mkdir(parents=True)
    native, frontend = derived_sources()
    (output / "strict-contract.json").write_bytes(strict_path.read_bytes())
    (output / "policy-contract.json").write_text(json.dumps(h.derive_contract(contract), indent=2) + "\n")
    (output / "native-driver.py").write_text(native)
    (output / "frontend-driver.py").write_text(frontend)
    plan = {"stage": "prepared", "policy": h.POLICY, "strict_path": str(strict_path),
            "strict_sha256": q._sha256_path(strict_path), "implementation": h.source_identity(),
            "human_semantics": "pending", "overall": "pending"}
    (output / "preparation.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


def preview_configuration(args):
    """Mirror actual smoke path resolution before declaring any acquisition."""
    smoke = q._load_retroarch_smoke()
    captures = Path(args.capture_dir).resolve()
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory).resolve()
        config = smoke.write_frontend_config(work, captures, direct_log=True)
        text = config.read_text() + 'config_save_on_exit = "false"\n'
        cfg = q._frontend_configuration_identity(text, work_directory=work, capture_directory=captures)
        manual = text + 'quit_press_twice = "false"\nthreaded_data_runloop_enable = "false"\ninput_exit_emulator = "escape"\n'
        manual_cfg = q._frontend_configuration_identity(manual, work_directory=work, capture_directory=captures)
    if cfg is None or manual_cfg is None:
        raise ValueError("configuration preview invalid; acquisition/launch prohibited")
    return cfg, manual_cfg


def calibrate(output, importer=None):
    plan = json.loads((output / "preparation.json").read_text())
    strict_path = Path(plan["strict_path"])
    if (plan["implementation"] != h.source_identity() or
        q._sha256_path(strict_path) != plan["strict_sha256"]):
        raise ValueError("stale preparation; no acquisition allowed")
    native_source, frontend_source = derived_sources()
    if (output / "native-driver.py").read_text() != native_source or (output / "frontend-driver.py").read_text() != frontend_source:
        raise ValueError("derived driver changed")
    native_sink, frontend_sink, intent = {}, {}, {}
    smoke = q._load_retroarch_smoke()
    def owned_run(args, schedule, *, invocation_id):
        nonlocal intent
        _exe, core, _content, app = smoke.validate_inputs(args)
        sources = q._active_frontend_sources({"sha256": q._sha256_path(core)})
        cfg, manual_cfg = preview_configuration(args)
        if not intent:
            intent = h.prepare_acquisition(frontend_sink["strict_contract"], sources, cfg, app, manual_cfg)
            (output / "acquisition-intent.json").write_text(json.dumps(intent, indent=2) + "\n")
        if intent["sources"] != sources or intent["configuration_identity"] != cfg or intent["app_identity"] != app:
            raise ValueError("acquisition identities changed")
        result = smoke.run_mvs_active_scene(args, schedule, invocation_id=invocation_id)
        result.update(hybrid_acquisition_identity=h.identity(intent), owned_child_reaped=True)
        return result
    namespace = dict(q.__dict__)
    namespace.update(hybrid_native_sink=native_sink, hybrid_frontend_sink=frontend_sink, hybrid_owned_run=owned_run)
    exec(compile(native_source, "<hybrid maintained native driver>", "exec"), namespace)
    native_result = namespace["run_active_scene"](Path("local/roms"), importer, strict_path)
    if native_result.get("predicate_results", {}).get("overall") != "pass":
        raise ValueError("fresh native qualification failed")
    frontend_sink["strict_contract"] = native_sink["contract"]
    exec(compile(frontend_source, "<hybrid maintained frontend driver>", "exec"), namespace)
    namespace["run_active_scene_frontend"](Path("local/roms"), importer, strict_path, calibrate=True)
    contract = native_sink["contract"]
    proof = dict(status="complete", guest_executed=True, contract_identity=h.identity(contract),
        runs_identity=h.frame_set_identity(native_sink["runs"]), code_identity=contract["code_identity"],
        media_identity=contract["media_identity"], evaluator_identity=q._production_evaluator_identity())
    machine = h.machine_calibration(frontend_sink["contract"], frontend_sink["runs"],
        frontend_sink["invocations"], frontend_sink["sources"], frontend_sink["configuration"],
        intent.get("app_identity"), contract, native_sink["runs"], acquisition=intent, native_evidence=proof)
    (output / "machine-calibration.json").write_text(json.dumps(machine, indent=2) + "\n")
    return machine


def freeze(output):
    machine = json.loads((output / "machine-calibration.json").read_text())
    if not h.machine_is_current(machine):
        raise ValueError("machine calibration not complete/current")
    frozen = {"policy": h.POLICY, "stage": "hybrid_machine_frozen",
              "machine_identity": machine["machine_identity"], "human_semantics": "pending", "overall": "pending"}
    (output / "hybrid-freeze.json").write_text(json.dumps(frozen, indent=2) + "\n")
    return frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "calibrate", "freeze"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict-contract", type=Path, default=q.PHASE06_CONTRACT_PATH)
    parser.add_argument("--importer")
    args = parser.parse_args()
    result = (prepare(args.strict_contract, args.output) if args.stage == "prepare" else
              calibrate(args.output, args.importer) if args.stage == "calibrate" else freeze(args.output))
    print(json.dumps({key: result[key] for key in ("stage", "human_semantics", "overall") if key in result}))
    return 0 if args.stage != "calibrate" or result.get("machine_status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
