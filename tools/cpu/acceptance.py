"""MIT: host-only, fail-closed CPU acceptance evidence and actual-run collector.

Evidence is an auditable local receipt, not a cryptographic attestation against
a malicious author who can replace both source and receipts. Independent review
is a separate required trust boundary. No runtime behavior is implemented here.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/cpu"))
import audit

CAPS = audit.CAPS
FREEZE = "f9e7dda6ce3593dc176ebfc99f9a6c504bf423f8"
CANDIDATE = audit.MUSASHI_PIN
CONFIG = {"native": "NONE", "asan-ubsan": "ADDRESS_UNDEFINED", "tsan": "THREAD"}
RUNTIME = dict(cpu_guest=4, cpu_guest_negative=1, cpu_isolation=4,
               cpu_isolation_negative=1, cpu_faults=4, cpu_timing=8,
               cpu_state=6, cpu_state_negative=2)
COLD = {"cpu_cold_" + str(i): 1 for i in range(1, 17)}
SOURCE = dict(cpu_closure=1, cpu_budget=1, cpu_audit_controls=13, cpu_inventory=3,
              regeneration=2, acceptance_controls=10)
REQUIRED = {"native": dict(RUNTIME, **COLD, **SOURCE), "asan-ubsan": RUNTIME,
            "tsan": dict(cpu_isolation=4, cpu_isolation_negative=1, **COLD)}
REVIEW_SCOPE = ("rights-oracles", "closure-generation", "explicit-call-graph", "all-state-fields",
                "cold-init-cleanup", "fault-frames", "cycles-exceptions", "fresh-bindings",
                "consequential-controls", "budgets-effort", "admission-tooling", "public-hygiene")
UNSUPPORTED = [dict(case=name, status="unsupported", reason=reason) for name, reason in (
    ("distinct-compiler", "Queried GCC 14/15/16 and Clang 19/20 unavailable; gcc aliases Apple Clang"),
    ("guest-bus-error", "Host memory faults are terminal; true 68000 bus-error frames unqualified"),
    ("bus-cycle-suspension", "Selected instruction and exception boundaries only"),
    ("board-bios-game", "Original CPU fixtures establish no board, BIOS or game compatibility"),
    ("public-state-compatibility", "Private same-build typed record, separate host memory required"),
    ("release-platforms", "Native experiment only; no release platform matrix"))]
OUT = ROOT / "experiments/cpu/acceptance-results.json"
EVIDENCE = ROOT / "experiments/cpu/evidence/plan-01-04"
HEX = re.compile(r"^[0-9a-f]{64}$")
DIAGNOSTIC = re.compile(r"runtime error:|ERROR: AddressSanitizer|WARNING: ThreadSanitizer|SUMMARY: .*Sanitizer")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def kind(case):
    return "source" if case in SOURCE else "runtime"


def sorted_records(records):
    return sorted(records, key=lambda r: (r["case"], r["lane"], r["configuration"], r["input_digest"]))


def evidence_digest(report):
    payload = {k: v for k, v in report.items() if k not in ("review", "result", "captured_at")}
    if isinstance(payload.get("records"), list):
        payload["records"] = sorted(payload["records"], key=canonical)
    if isinstance(payload.get("unsupported"), list):
        payload["unsupported"] = sorted(payload["unsupported"], key=canonical)
    return digest(payload)


def decide(report, identity):
    """Pure reducer: malformed, missing, contradictory or stale facts reject."""
    errors = []
    records = []
    def check(ok, reason):
        if not ok:
            errors.append(reason)
    try:
        check(report["schema"] == 1, "schema")
        check(report["identity"] == identity and bool(identity["input_hashes"]), "current source identity")
        check(bool(re.fullmatch(r"[0-9a-f]{40}", identity["source_revision"]))
              and bool(HEX.fullmatch(identity["content_digest"])), "identity format")
        check(report["caps"] == CAPS and report["freeze_commit"] == FREEZE, "frozen caps/contract")
        check(report["candidate"] == CANDIDATE and report["attempts"] == [1, 2], "candidate/attempt history")
        check(bool(HEX.fullmatch(report["ledger_sha256"])), "ledger identity")
        check(audit.validate_budget(report["budget"]), "budget limits")
        for key, floor in dict(handwritten=2611, helpers=520, semantic=483,
                               total_seconds=15065, attempt_seconds=13919).items():
            check(report["budget"][key] >= floor, "reset accounting: " + key)
        check(report["candidate_disposition"] == "eligible", "candidate rejected/deferred")
        check(sorted(report["unsupported"], key=canonical) == sorted(UNSUPPORTED, key=canonical), "unsupported denominator")
        expected = {(lane, name): count for lane, cases in REQUIRED.items() for name, count in cases.items()}
        seen = set()
        for row in report["records"]:
            key = (row["lane"], row["case"])
            check(key not in seen, "duplicate case: " + str(key))
            seen.add(key)
            check(key in expected, "unknown case: " + str(key))
            check(type(row["observed"]) is int and type(row["expected"]) is int
                  and row["observed"] == row["expected"] == expected.get(key, -1), "case count: " + str(key))
            check(row["status"] == "pass" and row["kind"] == kind(row["case"]), "case outcome: " + str(key))
            check(row["configuration"] == CONFIG[row["lane"]]
                  and row["input_digest"] == identity["content_digest"], "case identity: " + str(key))
            check(bool(HEX.fullmatch(row["output_sha256"])) and bool(row["command"]), "case receipt: " + str(key))
            records.append(row)
        check(seen == set(expected), "missing required cases")
        check(set(report["lanes"]) == set(CONFIG), "instrumentation denominator")
        for lane, config in CONFIG.items():
            row = report["lanes"][lane]
            check(row["status"] == "pass" and row["diagnostics"] == 0 and row["executed"] is True,
                  "actual execution: " + lane)
            check(row["instrumentation"] == config and len(row["runtime_objects"]) == 3
                  and all(HEX.fullmatch(h) for h in row["runtime_objects"]), "instrumented runtime: " + lane)
            check(all(row.get(k) for k in ("compiler", "sdk", "platform")), "toolchain identity: " + lane)
    except (KeyError, TypeError, ValueError, AttributeError):
        errors.append("malformed or incomplete evidence")
    review = report.get("review") if isinstance(report, dict) else None
    if review is not None:
        try:
            check(review["independent"] is True and bool(review["reviewer"])
                  and review["reviewer"] != "execute_01_04", "independent reviewer")
            check(review["content_digest"] == identity["content_digest"]
                  and review["source_revision"] == identity["source_revision"]
                  and review["evidence_digest"] == evidence_digest(report), "current review identity")
            check(sorted(review["inspected"]) == sorted(REVIEW_SCOPE), "actual source review scope")
            check(isinstance(review["findings"], list), "findings ledger")
            for finding in review["findings"]:
                check(finding["severity"] in ("low", "medium", "high", "critical")
                      and finding["status"] in ("open", "resolved") and bool(finding["id"]), "finding schema")
                check(finding["severity"] not in ("high", "critical") or finding["status"] == "resolved", "blocking review finding")
        except (KeyError, TypeError, ValueError):
            errors.append("malformed review")
    decision = "rejected" if errors else "ready-for-review" if review is None else "accepted"
    return dict(decision=decision, phase_status="ACCEPTED" if decision == "accepted" else "GAPS_FOUND",
                reasons=sorted(set(errors)), records=sorted_records(records),
                missing_review=review is None)


def inputs():
    # Include every source/build/test/tool/fixture input; exclude produced
    # evidence, ledger and review to avoid recursive hashes. Recovery files are
    # immutable audit inputs, so are explicitly included despite their location.
    files = {ROOT / "CMakeLists.txt", ROOT / "LICENSE"}
    for directory in ("third_party", "tools/cpu", "tests/cpu", "experiments/cpu"):
        for path in (ROOT / directory).rglob("*"):
            if (path.is_file() and "__pycache__" not in path.parts
                    and "/evidence/" not in path.as_posix()
                    and (path.suffix in (".c", ".h", ".py") or path.name in
                         ("CMakeLists.txt", "ORACLE.md", "PROVENANCE.md", "LICENSE.txt",
                          "source-manifest.json", "state-inventory.json", "fixture-manifest.json"))):
                files.add(path)
    files.update(p for p in (ROOT / "experiments/cpu/evidence/recovery-accounting").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts)
    return {p.relative_to(ROOT).as_posix(): audit.sha(p) for p in sorted(files)}


def identity(revision=None):
    hashes = inputs()
    return dict(source_revision=revision or audit.run(["git", "rev-parse", "HEAD"]).strip(),
                content_digest=digest(hashes), input_hashes=hashes)


def budget_history():
    return digest(audit.run(["git", "log", "--format=%H", "--numstat", audit.HISTORICAL_BASE + "..HEAD",
                            "--", *audit.UPSTREAM, *audit.HELPERS]))


def sanitize(text, build):
    text = text.replace(str(build), "<build>").replace(str(ROOT), "<source>")
    text = re.sub(r"/(?:Users|home)/[^\s\"']+", "<private-path>", text)
    text = re.sub(r"/(?:private/)?(?:var/folders|tmp)/[^\s\"']+", "<temporary>", text)
    return text


def command(args, build, name, timeout=240):
    started = time.monotonic()
    result = subprocess.run([str(x) for x in args], cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    output = sanitize(result.stdout, build)
    log = EVIDENCE / (name + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(output)
    audit.require(result.returncode == 0 and not DIAGNOSTIC.search(output), "failed command; retained " + str(log.relative_to(ROOT)))
    return output, round(time.monotonic() - started, 3), log


def observe(name, output):
    audit.require("[This part of the test output was removed" not in output, "truncated CTest output: " + name)
    if name in RUNTIME and not name.endswith("negative") or name in COLD:
        matches = re.findall(r"(\d+) Tests (\d+) Failures (\d+) Ignored", output)
        audit.require(len(matches) == 1 and matches[0][1:] == ("0", "0"), "invalid Unity execution: " + name)
        return int(matches[0][0])
    needles = {"cpu_guest_negative": "PASS: executed operand mutation", "cpu_isolation_negative": "PASS: swapped baseline",
               "cpu_state_negative": "intended consequential assertion failed",
               "cpu_inventory": "controls=3"}
    if name in needles:
        count = output.count(needles[name])
        audit.require(count == (2 if name == "cpu_state_negative" else 1), "missing control assertions: " + name)
        return SOURCE.get(name, RUNTIME.get(name))
    if name in ("cpu_closure", "cpu_budget", "cpu_audit_controls"):
        result = json.loads(output)
        audit.require(result["status"] == "pass", "failed source evidence: " + name)
        return result["tests"] if name == "cpu_audit_controls" else 1
    raise audit.AuditError("unclassified result " + name)


def collect(build):
    build = build.resolve()
    audit.require(build.is_relative_to(ROOT / "build"), "build directory must be below build/")
    initial = identity()
    # The named checkout revision must contain exactly the inputs being tested.
    for path, expected in initial["input_hashes"].items():
        raw = subprocess.check_output(["git", "show", initial["source_revision"] + ":" + path], cwd=ROOT)
        audit.require(hashlib.sha256(raw).hexdigest() == expected, "commit inputs before collection: " + path)
    audit.inventory()
    budget = audit.budget()
    ledger = audit.load_ledger(ROOT)
    report = dict(schema=1, identity=initial, freeze_commit=FREEZE, candidate=CANDIDATE,
                  budget=budget["metrics"], caps=CAPS, ledger_sha256=audit.sha(ROOT / "experiments/cpu/budget-ledger.json"),
                  attempts=[a["number"] for a in ledger["attempts"]], candidate_disposition="eligible",
                  budget_history_digest=budget_history(),
                  records=[], lanes={}, unsupported=copy.deepcopy(UNSUPPORTED), review=None)
    available = [name for name in ("gcc-14", "gcc-15", "gcc-16", "clang-19", "clang-20") if shutil.which(name)]
    audit.require(not available, "distinct compiler now available; qualify and reconcile lane contract: " + str(available))
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="qualification-", dir=build) as temporary:
        fresh = Path(temporary)
        for lane, config in CONFIG.items():
            directory = fresh / lane
            args = ["cmake", "-S", ".", "-B", directory, "-G", "Ninja", "-DGLUEYNEO_CPU_EXPERIMENT=ON", "-DGLUEYNEO_CPU_SANITIZER=" + config]
            _, configure_seconds, _ = command(args, fresh, lane + "-configure")
            _, build_seconds, _ = command(["cmake", "--build", directory, "--parallel", "2"], fresh, lane + "-build")
            cases = [name for name in REQUIRED[lane] if name not in ("regeneration", "acceptance_controls")]
            selection = "^(" + "|".join(sorted(cases)) + ")$"
            args = ["ctest", "--test-dir", directory, "-R", selection, "-E", "^cpu_acceptance", "--output-on-failure", "--no-tests=error", "--test-output-size-passed", "10485760", "--test-output-size-failed", "10485760", "--output-junit", directory / "results.xml"]
            _, test_seconds, _ = command(args, fresh, lane + "-ctest", timeout=600)
            xml = ET.parse(directory / "results.xml").getroot()
            actual = xml.findall("testcase")
            audit.require(sorted(t.attrib["name"] for t in actual) == sorted(cases), "incomplete CTest denominator: " + lane)
            for test in actual:
                name = test.attrib["name"]
                output = sanitize(test.findtext("system-out", ""), fresh)
                audit.require(test.attrib.get("status") == "run" and test.find("failure") is None
                              and test.find("skipped") is None and not DIAGNOSTIC.search(output), "failed case " + name)
                record = dict(lane=lane, case=name, kind=kind(name), configuration=config,
                              expected=REQUIRED[lane][name], observed=observe(name, output), status="pass",
                              input_digest=initial["content_digest"], output_sha256=hashlib.sha256(output.encode()).hexdigest(),
                              command=["ctest", "--test-dir", "<build>/" + lane, "-R", "^" + name + "$"])
                record["output"] = output
                report["records"].append(record)
            ninja = (directory / "build.ninja").read_text()
            link = re.search(r"^build experiments/cpu/libcpu_runtime.a: C_STATIC_LIBRARY_LINKER[^\n]*", ninja, re.M)
            audit.require(link is not None, "missing runtime linkage")
            objects = [p for p in link[0].split() if p.endswith(".o")]
            audit.require(len(objects) == 3, "runtime object denominator")
            flag = {"NONE": "-O0", "ADDRESS_UNDEFINED": "-fsanitize=address,undefined", "THREAD": "-fsanitize=thread"}[config]
            object_blocks = []
            for obj in objects:
                block = re.search(r"^build " + re.escape(obj) + r":.*?(?=\n\n)", ninja, re.M | re.S)
                audit.require(block is not None and flag in block[0], "runtime instrumentation missing")
                audit.require(config != "ADDRESS_UNDEFINED" or "-fno-sanitize-recover=all" in block[0], "recoverable sanitizer")
                object_blocks.append(sanitize(block[0], fresh))
            cache = (directory / "CMakeCache.txt").read_text()
            compiler = re.search(r"^CMAKE_C_COMPILER:FILEPATH=(.+)$", cache, re.M)[1]
            report["lanes"][lane] = dict(status="pass", diagnostics=0, executed=True, instrumentation=config,
                runtime_objects=[audit.sha(directory / obj) for obj in objects], runtime_object_paths=objects,
                object_commands=object_blocks, runtime_archive_sha256=audit.sha(directory / "experiments/cpu/libcpu_runtime.a"),
                compiler=audit.run([compiler, "--version"]).splitlines()[0],
                sdk=audit.run(["xcrun", "--show-sdk-version"]).strip(), platform=audit.run(["uname", "-srm"]).strip(),
                configure_seconds=configure_seconds, build_seconds=build_seconds, test_seconds=test_seconds)
        regeneration = audit.regenerate()
        control_output, _, _ = command([sys.executable, ROOT / "tests/cpu/test_acceptance.py"], fresh, "acceptance-controls")
        audit.require("Ran 10 tests" in control_output and "\nOK" in control_output, "nonempty acceptance controls")
        for name, output in (("regeneration", canonical(regeneration)), ("acceptance_controls", control_output)):
            report["records"].append(dict(lane="native", case=name, kind="source", configuration="NONE",
                expected=SOURCE[name], observed=SOURCE[name], status="pass", input_digest=initial["content_digest"],
                output_sha256=hashlib.sha256(output.encode()).hexdigest(), output=output,
                command=["python3", "tools/cpu/audit.py", "regenerate"] if name == "regeneration"
                else ["python3", "tools/cpu/acceptance.py", "self-test"]))
    audit.require(identity() == initial, "inputs changed during collection")
    report["records"] = sorted_records(report["records"])
    report["result"] = decide(report, initial)
    audit.atomic_json(OUT, report)
    audit.require(report["result"]["decision"] == "ready-for-review", canonical(report["result"]["reasons"]))
    print(canonical(dict(decision="ready-for-review", content_digest=initial["content_digest"], evidence_digest=evidence_digest(report))))


def verify(require_accepted=False, seal=False):
    report = json.loads(OUT.read_text())
    current = identity(report["identity"]["source_revision"])
    audit.run(["git", "merge-base", "--is-ancestor", current["source_revision"], "HEAD"])
    for path, expected in current["input_hashes"].items():
        raw = subprocess.check_output(["git", "show", current["source_revision"] + ":" + path], cwd=ROOT)
        audit.require(hashlib.sha256(raw).hexdigest() == expected, "evaluated revision differs: " + path)
    audit.require(report["ledger_sha256"] == audit.sha(ROOT / "experiments/cpu/budget-ledger.json"), "stale ledger")
    audit.require(report["budget_history_digest"] == budget_history(), "changed cumulative source history")
    ledger = audit.load_ledger(ROOT)
    audit.require(report["attempts"] == [a["number"] for a in ledger["attempts"]], "attempt ledger mismatch")
    frozen = lambda s: s.split("<!-- freeze:start -->", 1)[1].split("<!-- freeze:end -->", 1)[0]
    audit.require(frozen((ROOT / "experiments/cpu/ACCEPTANCE.md").read_text()) ==
                  frozen(audit.run(["git", "show", FREEZE + ":experiments/cpu/ACCEPTANCE.md"])), "freeze changed")
    for row in report["records"]:
        audit.require(hashlib.sha256(row["output"].encode()).hexdigest() == row["output_sha256"], "output identity mismatch")
        if row["case"] not in ("regeneration", "acceptance_controls"):
            audit.require(observe(row["case"], row["output"]) == row["observed"], "output count mismatch")
        if row["case"] == "cpu_budget":
            budget = json.loads(row["output"])
            audit.require(budget["metrics"] == report["budget"] and budget["caps"] == CAPS, "budget receipt mismatch")
        if row["case"] == "regeneration":
            generated = json.loads(row["output"])
            audit.require(generated["status"] == "pass" and generated["independent_parallel_directories"] == 2
                          and all(audit.sha(ROOT / "third_party/musashi" / name) == value
                                  for name, value in generated["outputs"].items())
                          and set(generated["outputs"]) == {"m68kops.c", "m68kops.h"}, "regeneration receipt")
        if row["case"] == "acceptance_controls":
            audit.require("Ran 10 tests" in row["output"] and "\nOK" in row["output"], "acceptance controls receipt")
    review_path = ROOT / "experiments/cpu/REVIEW.md"
    if review_path.exists():
        text = review_path.read_text()
        match = re.search(r"```json\n(.*?)\n```", text, re.S)
        audit.require(match is not None, "review metadata missing")
        review = json.loads(match[1])
        review["receipt_sha256"] = audit.sha(review_path)
        if seal:
            report["review"] = review
        else:
            audit.require(report["review"] == review, "review receipt changed or not sealed")
    elif report.get("review") is not None:
        raise audit.AuditError("review receipt absent")
    result = decide(report, current)
    if seal:
        report["result"] = result
        audit.atomic_json(OUT, report)
    else:
        audit.require(result == report["result"], "stored decision differs from recomputed decision")
    print(canonical(dict(decision=result["decision"], phase_status=result["phase_status"], reasons=result["reasons"])))
    return 0 if result["decision"] == "accepted" or not require_accepted and result["decision"] == "ready-for-review" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("collect", "self-test", "verify", "seal"))
    parser.add_argument("--build-dir", default="build/cpu-final")
    parser.add_argument("--require-accepted", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "self-test":
            return subprocess.run([sys.executable, ROOT / "tests/cpu/test_acceptance.py"], timeout=60).returncode
        if args.action == "collect":
            collect(ROOT / args.build_dir)
            return 0
        return verify(args.require_accepted, args.action == "seal")
    except (audit.AuditError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        reason = sanitize(str(error), ROOT / "build")
        if args.action == "collect":
            audit.atomic_json(OUT, dict(schema=1, identity=identity(), candidate_disposition="rejected",
                                       result=dict(decision="rejected", phase_status="GAPS_FOUND", reasons=[reason]),
                                       missing_evidence="Collection did not complete; retained command logs are not admission"))
        print("GAPS_FOUND: " + reason, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
