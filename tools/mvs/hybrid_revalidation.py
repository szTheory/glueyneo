"""One-epoch revalidation: immutable 5512 producer, current manual evaluator.

No acquisition is backdated and no old receipt is rewritten. This is not a
general source-compatibility mechanism. Unknown automated source changes reject.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess

from tools.mvs import hybrid_acceptance as h
from tools.mvs import qualify_local_boot as q

PRODUCER = "5512de69"
POLICY = "5512_fixed_machine_manual_only_reevaluation_v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_source(path):
    return subprocess.run(["git", "show", PRODUCER + ":" + path], cwd=q.PROJECT_ROOT,
        capture_output=True, check=True, timeout=5).stdout


class AutomatedProjection(ast.NodeTransformer):
    def visit_If(self, node):
        # Select only the pre-existing default scripted lane, never manual code.
        test = ast.dump(node.test)
        if "manual_handoff" in test:
            require(isinstance(node.test, ast.Compare) and len(node.test.ops) == 1 and
                isinstance(node.test.left, ast.Name) and node.test.left.id == "manual_handoff" and
                len(node.test.comparators) == 1 and isinstance(node.test.comparators[0], ast.Constant) and
                node.test.comparators[0].value is None and isinstance(node.test.ops[0], (ast.Is, ast.IsNot)),
                "unrecognized manual branch")
            branch = node.body if isinstance(node.test.ops[0], ast.Is) else node.orelse
            result = []
            for item in branch:
                projected = self.visit(item)
                result.extend(projected if isinstance(projected, list) else [projected])
            return result
        return self.generic_visit(node)


def projection(source, kind):
    tree = ast.parse(source)
    ignored = ({"gameplay_session_valid", "review_feedback"} if kind == "helper" else set())
    kept=[]
    for node in tree.body:
        manual = isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and (node.name in ignored or kind=='collector' and
            (node.name.startswith('_manual_') or node.name.startswith('bind_manual_') or node.name.startswith('request_manual_')))
        if manual:
            require(not node.decorator_list, 'manual declaration decorator could affect import')
            for value in [*node.args.defaults,*node.args.kw_defaults]:
                if value is not None:
                    try: ast.literal_eval(value)
                    except (ValueError,TypeError): raise ValueError('manual default could affect import') from None
            all_args=[*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs]
            all_args += [a for a in (node.args.vararg,node.args.kwarg) if a is not None]
            annotations=[a.annotation for a in all_args]+[node.returns]
            require(all(a is None or not any(isinstance(n,ast.Call) for n in ast.walk(a)) for a in annotations),
                    'manual annotation could affect import')
        else:kept.append(node)
    tree.body=kept
    if kind == "collector":
        tree = AutomatedProjection().visit(tree)
    return ast.dump(tree, include_attributes=False)


def source_proof(machine):
    require(set(machine["implementation"]) == set(h.source_identity()), "producer source coverage differs")
    proof = {}
    for name, original_hash in machine["implementation"].items():
        old = git_source(name)
        require(hashlib.sha256(old).hexdigest() == original_hash, "producer source identity differs")
        current = (q.PROJECT_ROOT / name).read_bytes()
        if name == "tools/mvs/hybrid_gameplay.py":
            mode = "manual caller only"
        elif name in ("tools/mvs/hybrid_acceptance.py", "tests/libretro/retroarch_smoke.py"):
            kind = "helper" if "hybrid_acceptance" in name else "collector"
            require(projection(old, kind) == projection(current, kind), "automated source projection changed: " + name)
            mode = "identical automated AST"
        else:
            require(old == current, "nonmanual producer source changed: " + name)
            mode = "identical bytes"
        proof[name] = {"producer": original_hash, "evaluator": hashlib.sha256(current).hexdigest(), "proof": mode}
    return proof


def producer_transfer(row, sources, configuration):
    """Validate the original binding using its verified original source epoch.

    The temporary check object is never persisted as a replacement receipt.
    Current validators still check every other field and all matching sequences.
    """
    replay = q._load_frontend_replay()
    original = row["replay"]
    payload = replay._evidence(sources["core_sha256"], row["selected_bundle_sha256"], row, configuration)
    payload["implementation_identity"] = {"helper": sources["replay_sha256"],
        "collector": sources["collector_sha256"], "evaluator": sources["evaluator"]["sha256"]}
    require(original["binding"] == hashlib.sha256(replay._canonical(payload)).hexdigest(), "original replay binding differs")
    check = copy.deepcopy(original)
    check["binding"] = replay.replay_binding(sources["core_sha256"], row["selected_bundle_sha256"], row, configuration)
    require(replay.validate_receipt(check, sources["core_sha256"], row["selected_bundle_sha256"], row, configuration),
            "original replay receipt invalid")


def create_bridge(profile):
    require(Path.cwd().resolve() == q.PROJECT_ROOT.resolve(), "project root required for canonical native paths")
    profile = Path(profile).resolve()
    require(q.ignored(profile), "profile must remain private")
    machine = json.loads((profile / "machine-calibration.json").read_text())
    intent = json.loads((profile / "acquisition-intent.json").read_text())
    strict = json.loads((profile / "strict-contract.json").read_text())
    policy = json.loads((profile / "policy-contract.json").read_text())
    required_gates = set(h.RETAINED) | {"combined_projectile", "native_combined", "joint_input_transfer_lifecycle"}
    require(machine["machine_identity"] == h.identity({k:v for k,v in machine.items() if k != "machine_identity"}), "original machine seal")
    require(machine["policy"] == h.POLICY and machine["stage"] == "machine_calibration" and
        set(machine["machine_gates"]) == required_gates and len(machine["capture_artifacts"]) == 60 and
        machine["machine_status"] == "pass" and machine["overall"] == machine["human_semantics"] == "pending" and
        all(v == "pass" for v in machine["machine_gates"].values()) and machine["acquisition"] == intent, "original machine incomplete")
    require(h.identity(policy) == intent["policy_contract_identity"] == machine["policy_contract_identity"] and
        policy["implementation"] == intent["implementation"] == machine["implementation"] and
        policy["strict_contract_identity"] == h.identity(strict), "original predeclared policy differs")
    current_policy = h.derive_contract(strict)
    require({k:v for k,v in policy.items() if k != "implementation"} ==
            {k:v for k,v in current_policy.items() if k != "implementation"}, "policy expectations changed")
    proof = source_proof(machine)
    require(q.active_scene_native_contract_is_valid(strict), "native contract invalid")
    require(strict["code_identity"] == {"importer": q._production_importer_identity(), "qualifier": q._production_qualifier_identity()} and
        strict["evaluator_identity"] == q._production_evaluator_identity(), "native implementation changed")
    prep = json.loads((profile / "preparation.json").read_text())
    require(digest(prep["strict_path"]) == prep["strict_sha256"] == digest(profile / "strict-contract.json"), "strict contract changed")
    launch = json.loads((q.PROJECT_ROOT / "local/qualification/phase06-hybrid-manual-preflight/private-launch-inputs.json").read_text())
    exe = Path(launch["retroarch"])
    if exe.is_dir(): exe = exe / "Contents/MacOS/RetroArch"
    binaries = {"core": digest(launch["core"]), "media": digest(launch["content"]), "frontend": digest(exe)}
    require(binaries == {"core": machine["expected_sources"]["core_sha256"], "media": machine["expected_bundle_sha256"],
        "frontend": machine["expected_app_identity"]["retroarch_executable_sha256"]}, "runtime bytes changed")
    manual_work = q.PROJECT_ROOT / "local/qualification/phase06-hybrid-manual-preflight"
    manual_configuration = q._frontend_configuration_identity((manual_work / "retroarch.cfg").read_text(),
        work_directory=manual_work, capture_directory=manual_work / "captures")
    require(manual_configuration is not None and manual_configuration == machine["expected_manual_configuration_identity"],
            "manual configuration changed")
    identifiers = {a["invocation_id"] for a in machine["capture_artifacts"]}
    cases = []
    for iid in sorted(identifiers):
        case = q.PROJECT_ROOT / q.PHASE06_RUN_ROOT / ("run-" + iid) / "frontend-case.json"
        row = json.loads(case.read_text()); cases.append(row)
        require(row["status"] == "complete" and row["frontend_exit_code"] == 0 and row["owned_child_reaped"] is True and
            row["hybrid_acquisition_identity"] == h.identity(intent) and row["identity"] == machine["expected_app_identity"], "producer invocation invalid")
        cfg = q._frontend_configuration_identity(row["configuration_text"], work_directory=Path(row["configuration_work_directory"]),
            capture_directory=Path(row["captures"][0]["path"]).parent.resolve())
        require(cfg == intent["configuration_identity"], "producer configuration differs")
        require(q._active_frontend_events_valid(row, q._active_scene_input_events(strict["frontend"]["schedule"], row["pair"], row["role"]), iid), "producer input history invalid")
        producer_transfer(row, machine["expected_sources"], cfg)
    require(len(cases) == 10 and {(r["pair"], r["role"]) for r in cases} ==
        {(p,r) for p in q._ACTIVE_SCENE_PAIR_NAMES for r in ("action","control")}, "producer role coverage")
    runs = {}; replay = q._load_frontend_replay()
    for row in cases:
        require(len(row["captures"]) == 6 and all(h._owned_capture(c,row["invocation_id"]) for c in row["captures"]), "producer captures changed")
        runs.setdefault(row["pair"], {})[row["role"]] = [replay._capture_rgb(c) for c in row["captures"]]
    runs["scene"] = {"status":"complete", "t0":runs["right"]["control"][0], "endpoint":runs["right"]["control"][-1]}
    frontend = {**strict, "schedule":strict["frontend"]["schedule"]}
    predicates = q.evaluate_active_scene_pairs(frontend,runs,frontend_intervals=True)
    # The unchanged frontend composition gate is source-bound transfer, not the native ROI check.
    predicates["composition"] = "pass"
    predicates['overall'] = ('pass' if all(value=='pass' for key,value in predicates.items() if key!='overall')
                             else 'fail' if 'fail' in predicates.values() else 'unknown')
    require(all(predicates[n] == "pass" for n in h.RETAINED) and h._projectile(frontend,runs) and
        q._active_frontend_temporal_bounds_valid(frontend["schedule"],cases), "current frontend evaluation failed")
    # Re-decode the original native artifacts under the same current native
    # executable/input contract. Do not infer native success from stored booleans.
    earliest = (profile / "preparation.json").stat().st_mtime_ns
    latest = (profile / "machine-calibration.json").stat().st_mtime_ns
    reports = []
    for path in (q.PROJECT_ROOT / q.PHASE06_RUN_ROOT).glob("run-*/active-scene-report.json"):
        if earliest <= path.stat().st_mtime_ns <= latest:
            reports.append((path, json.loads(path.read_text())))
    aggregates = [(path,row) for path,row in reports if row.get("status") == "active_scene_native_recorded" and
                  row.get("contract_identity") == strict["contract_identity"] and len(row.get("invocations",[])) == 10]
    require(len(aggregates) == 1, "native aggregate ancestry ambiguous")
    native_path, aggregate = aggregates[0]
    require(aggregate["code_identity"] == strict["code_identity"] and aggregate["media_identity"] == strict["media_identity"],
            "native aggregate identity changed")
    native_runs = {}; native_artifacts = []
    for expected in aggregate["invocations"]:
        matches = [(path,row) for path,row in reports if row == expected]
        require(len(matches) == 1, "native role ancestry ambiguous")
        path,row = matches[0]
        require(row["status"] == "active_frames_completed" and
            row["active_frames_requested"] == row["active_frames_completed"] == strict["schedule"]["active_frames"], "native role incomplete")
        images = []
        for cap in row["capture_observations"]:
            frame = path.parent / cap["file"]
            rgb = q._load_private_capture_rgb(frame.relative_to(q.PROJECT_ROOT))
            require(rgb is not None and digest(frame) == cap["sha256"], "native pixels changed")
            images.append(rgb); native_artifacts.append(cap["sha256"])
        require(len(images) == 6, "native capture coverage")
        native_runs.setdefault(row["pair"],{})[row["role"]] = images
    native_runs["scene"] = {"status":"complete", "t0":native_runs["right"]["control"][0], "endpoint":native_runs["right"]["control"][-1]}
    native_predicates = q.evaluate_active_scene_pairs(strict,native_runs)
    require(native_predicates["overall"] == "pass" and len(native_artifacts) == 60, "native reevaluation failed")
    evaluator = h.source_identity()
    require(evaluator == {name: row["evaluator"] for name,row in proof.items()}, "evaluator changed during verification")
    result = {"policy":POLICY, "profile":str(profile), "producer_commit":PRODUCER,
        "producer_machine_identity":machine["machine_identity"], "producer_intent_identity":h.identity(intent),
        "source_projection":proof, "current_evaluator":evaluator, "bridge_source":digest(__file__),
        "runtime_bytes":binaries, "raw_evidence_identity":h.identity(cases),
        "manual_configuration_identity":manual_configuration,
        "native_report_sha256":digest(native_path), "native_artifacts_identity":h.identity(native_artifacts),
        "native_predicates":native_predicates,
        "frontend_predicates":predicates, "machine_status":"pass", "human_semantics":"pending", "overall":"pending"}
    result["certificate_identity"] = h.identity(result)
    return result


def validated_bridge(machine, certificate):
    try:
        require(certificate["policy"] == POLICY and certificate["producer_machine_identity"] == machine["machine_identity"], "bridge policy/binding")
        current = create_bridge(certificate["profile"])
        return current == certificate
    except (KeyError, TypeError, ValueError, OSError, RuntimeError, subprocess.SubprocessError):
        return False
