"""MIT: offline, host-only source, generation and cumulative-budget audit.

No result admits a backend. Receipts are published only after every check;
scratch is unique per invocation and never replaces admitted source outputs.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ["m68k.h", "m68kcpu.h", "m68kcpu.c", "m68kconf.h", "m68k_in.c", "m68kmake.c"]
UPSTREAM = ["third_party/musashi/" + name for name in INPUTS]
HELPERS = ["tools/cpu/adapt.py", "experiments/cpu/cpu_adapter.c", "experiments/cpu/cpu_adapter.h",
           "experiments/cpu/test_bus.c", "experiments/cpu/test_bus.h", "CMakeLists.txt", "experiments/cpu/CMakeLists.txt"]
OUTPUTS = ["third_party/musashi/m68kops.c", "third_party/musashi/m68kops.h"]
MUSASHI_PIN = "313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd"
UNITY_PIN = "b6763fbd9cedfacaa89e2ad9fd00d615a234e355"
HISTORICAL_BASE = "f4eb1afe8b20299619abd93c48ed564e1780e617"
RUNTIME_FILES = set(UPSTREAM + OUTPUTS + HELPERS[1:3]) - {"third_party/musashi/m68kmake.c", "third_party/musashi/m68k_in.c"}
CAPS = dict(attempts=2, total_seconds=57600, attempt_seconds=28800, upstream_files=6,
            handwritten=5000, semantic=500, helpers=600, generated_files=2,
            generated_lines=50000, generated_bytes=2097152)
HOST_CALLS = {
    "memcpy": "explicit buffer copy", "memset": "instance initialization",
    "__memset_chk": "compiler-generated bounds-checked instance initialization",
    "bzero": "compiler-selected zero fill", "memset_pattern16": "compiler-selected repeated-pattern memory fill",
    "setjmp": "current call fault frame", "longjmp": "bounded return to current call",
    "sigsetjmp": "backend address-error frame", "siglongjmp": "backend address-error return",
    "__stack_chk_fail": "compiler stack-integrity support", "__stack_chk_guard": "compiler stack-integrity support",
}
FORBIDDEN = {"exit", "_Exit", "abort", "getenv", "system", "fopen", "fread", "fwrite", "fprintf",
             "printf", "puts", "open", "read", "write", "socket", "connect", "time", "clock", "gettimeofday"}

class AuditError(Exception):
    pass

def require(ok, message):
    if not ok:
        raise AuditError(message)

def run(args, cwd=ROOT, timeout=60):
    result = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True, text=True, timeout=timeout)
    require(result.returncode == 0, "command failed: " + str(args[0]) + "\n" + result.stdout + result.stderr)
    return result.stdout

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def validate_budget(values):
    if not isinstance(values, dict) or set(values) != set(CAPS):
        return False
    if any(type(values[k]) is not int or not 0 <= values[k] <= cap for k, cap in CAPS.items()):
        return False
    return (values["attempts"] > 0 and values["generated_files"] == 2
            and values["semantic"] <= values["handwritten"] and values["helpers"] <= values["handwritten"])

def load_ledger(root):
    path = root / "experiments/cpu/budget-ledger.json"
    require(path.is_file(), "missing budget ledger")
    ledger = json.loads(path.read_text())
    required = {"freeze_commit", "historical_base", "historical_accounting", "historical_semantic_refinement", "historical_handwritten", "historical_helpers",
                "historical_semantic_upper_bound", "semantic_review", "attempts", "preparation_intervals",
                "recovery_executor_charge_start", "upstream_paths", "helper_paths", "generated_paths",
                "recovery_semantic_lines", "recovery_semantic_review", "additional_review_seconds", "reviewed_source_hashes"}
    require(isinstance(ledger, dict) and required <= ledger.keys(), "incomplete budget ledger")
    for key in required - {"recovery_semantic_lines", "additional_review_seconds"}:
        require(ledger[key] is not None and ledger[key] != "" and ledger[key] != [], "empty ledger field: " + key)
    for key, expected in (("upstream_paths", UPSTREAM), ("helper_paths", HELPERS), ("generated_paths", OUTPUTS)):
        require(sorted(ledger[key]) == sorted(expected), "changed or duplicate budget paths: " + key)
    require(ledger["historical_base"] == HISTORICAL_BASE, "historical base changed")
    return ledger

def check_reviewed_sources(root, ledger):
    reviewed = ledger["reviewed_source_hashes"]
    require(isinstance(reviewed, dict) and set(reviewed) == set(UPSTREAM + HELPERS), "incomplete reviewed source identities")
    for path, expected in reviewed.items():
        require(sha(root / path) == expected, "stale semantic/source review: " + path)

def verify_recipe(root, history_repo):
    receipt = json.loads(run(["git", "show", HISTORICAL_BASE + ":experiments/cpu/evidence/attempt-1/receipt.json"], history_repo))
    with tempfile.TemporaryDirectory(prefix="cpu-recipe-") as temporary:
        scratch = Path(temporary)
        pristine = scratch / "pristine"
        pristine.mkdir()
        for row in receipt["inputs"]:
            (pristine / Path(row["file"]).name).write_text(run(["git", "show", HISTORICAL_BASE + ":" + row["file"]], history_repo))
        patch = scratch / "historical.patch"
        patch.write_text(run(["git", "show", HISTORICAL_BASE + ":experiments/cpu/evidence/attempt-1/source.patch"], history_repo))
        run(["git", "apply", "--reverse", patch], pristine)
        for row in receipt["inputs"]:
            require(sha(pristine / Path(row["file"]).name) == row["pristine_sha256"], "pristine source identity mismatch")
        adapted = scratch / "adapted"
        run([sys.executable, root / "tools/cpu/adapt.py", pristine, adapted], root)
        require(all((adapted / name).read_bytes() == (root / "third_party/musashi" / name).read_bytes() for name in INPUTS), "current adaptation recipe mismatch")

def diff_count(root, before, after, paths):
    args = ["git", "diff", "--numstat", before]
    if after:
        args.append(after)
    output = run(args + ["--", *paths], root)
    rows = [line.split("\t") for line in output.splitlines()]
    require(all(len(row) == 3 and row[0].isdigit() and row[1].isdigit() for row in rows), "binary or malformed source diff")
    return sum(int(row[0]) + int(row[1]) for row in rows)

def budget(root=ROOT):
    ledger = load_ledger(root)
    check_reviewed_sources(root, ledger)
    verify_recipe(root, root)
    history_path = root / ledger["historical_accounting"]
    history = json.loads(history_path.read_text())
    require(history["handwritten_cumulative_conservative"] == ledger["historical_handwritten"] == 2073, "historical total mismatch")
    require(history["helper_cumulative_conservative"] == ledger["historical_helpers"] == 302, "historical helper mismatch")
    refinement = json.loads((root / ledger["historical_semantic_refinement"]).read_text())
    require(refinement["revised_attempt1_semantic_upper_bound"] == ledger["historical_semantic_upper_bound"] == 327, "semantic review mismatch")
    require(len(refinement["pairs"]) * 2 + len(refinement["charged_residual"]) == 188, "incomplete semantic review")
    run([sys.executable, root / "experiments/cpu/evidence/recovery-accounting/replay.py", root], root)
    frozen = lambda text: text.split("<!-- freeze:start -->", 1)[1].split("<!-- freeze:end -->", 1)[0]
    original = run(["git", "show", ledger["freeze_commit"] + ":experiments/cpu/ACCEPTANCE.md"], root)
    require(frozen(original) == frozen((root / "experiments/cpu/ACCEPTANCE.md").read_text()), "frozen contract changed")
    run(["git", "merge-base", "--is-ancestor", ledger["freeze_commit"], ledger["historical_base"]], root)
    commits = run(["git", "rev-list", "--reverse", ledger["historical_base"] + "..HEAD"], root).splitlines()
    upstream = helpers = 0
    for commit in commits:
        upstream += diff_count(root, commit + "^", commit, UPSTREAM)
        helpers += diff_count(root, commit + "^", commit, HELPERS)
    upstream += diff_count(root, "HEAD", None, UPSTREAM)
    helpers += diff_count(root, "HEAD", None, HELPERS)
    discarded = ledger.get("discarded_helper_lines", 0)
    require(type(discarded) is int and discarded >= 0, "invalid discarded helper charge")
    helpers += discarded
    attempts = ledger["attempts"]
    require([a["number"] for a in attempts] == list(range(1, len(attempts) + 1)), "duplicate or missing attempt")
    seconds = []
    now = dt.datetime.now(dt.timezone.utc)
    parse = lambda value: dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    for attempt in attempts:
        start = parse(attempt["start"] if attempt["number"] == 1 else ledger["recovery_executor_charge_start"])
        end = parse(attempt["end"]) if attempt["end"] else now
        elapsed = int((end - start).total_seconds())
        require(elapsed >= 0, "negative effort interval")
        if attempt["end"]:
            require(attempt["charged_seconds"] == elapsed, "effort receipt mismatch")
        seconds.append(elapsed)
    review = ledger["additional_review_seconds"]
    require(type(review) is int and review >= 0, "invalid review effort")
    for interval in ledger["preparation_intervals"]:
        elapsed = int((parse(interval["end"]) - parse(interval["start"])).total_seconds())
        require(elapsed == interval["charged_seconds"] and elapsed >= 0, "invalid preparation interval")
        review += elapsed
    metrics = dict(attempts=len(attempts), total_seconds=sum(seconds) + review, attempt_seconds=max(seconds[0], seconds[-1] + review),
                   upstream_files=len(UPSTREAM), handwritten=2073 + upstream + helpers,
                   semantic=327 + ledger["recovery_semantic_lines"], helpers=302 + helpers,
                   generated_files=len(OUTPUTS), generated_lines=sum(len((root / p).read_bytes().splitlines()) for p in OUTPUTS),
                   generated_bytes=sum((root / p).stat().st_size for p in OUTPUTS))
    require(validate_budget(metrics), "budget cap exceeded or incomplete: " + json.dumps(metrics))
    return {"status": "pass", "metrics": metrics, "caps": CAPS, "historical_replay": str(history_path.relative_to(root)),
            "cumulative_method": "Historical edit replay plus every subsequent committed transition and current working diff; no net-diff reset."}

def inventory(root=ROOT):
    path = root / "tools/cpu/source-manifest.json"
    require(path.is_file(), "missing source manifest")
    manifest = json.loads(path.read_text())
    require(manifest.get("candidate") == MUSASHI_PIN and manifest.get("unity_revision") == UNITY_PIN, "incorrect source pin")
    require(manifest.get("adaptation_recipe") == {"path": "tools/cpu/adapt.py", "sha256": sha(root / "tools/cpu/adapt.py")}, "stale adaptation recipe identity")
    rows = manifest.get("files")
    require(isinstance(rows, list) and rows, "empty source manifest")
    names = [row.get("path") for row in rows]
    require(all(isinstance(name, str) and not Path(name).is_absolute() and ".." not in Path(name).parts for name in names), "invalid inventory path")
    require(len(names) == len(set(names)), "duplicate source entry")
    actual = set()
    for directory in ("third_party", "experiments/cpu", "tests/cpu", "tools/cpu"):
        for file in (root / directory).rglob("*"):
            rel = file.relative_to(root).as_posix()
            if file.is_file() and "__pycache__" not in file.parts and "/evidence/" not in rel and file.suffix in {".c", ".h", ".py"}:
                actual.add(rel)
    actual.update({"CMakeLists.txt", "experiments/cpu/CMakeLists.txt", "LICENSE", "third_party/unity/LICENSE.txt",
                   "third_party/unity/PROVENANCE.md", "third_party/musashi/PROVENANCE.md"})
    require(set(names) == actual, "unknown or missing source inventory entry: " + str(sorted(set(names) ^ actual)))
    for row in rows:
        require(all(key in row for key in ("sha256", "origin", "revision", "license", "notice", "copied", "generated", "compiled", "distributed", "host_calls")), "incomplete source disposition")
        file = root / row["path"]
        require(file.resolve().is_relative_to(root.resolve()), "source escapes admitted tree")
        require(file.is_file() and sha(file) == row["sha256"], "source hash mismatch: " + row["path"])
        musashi = row["path"] in UPSTREAM + OUTPUTS
        unity = row["path"].startswith("third_party/unity/") and not row["path"].endswith(".md")
        origin = "Musashi" if musashi else "Unity" if unity else "Glueyneo"
        revision = MUSASHI_PIN if musashi else UNITY_PIN if unity else "sha256:" + row["sha256"]
        expected_compiled = ([] if row["path"] == "third_party/musashi/m68k_in.c" else ["runtime"] if row["path"] in RUNTIME_FILES else ["host-generator"] if row["path"].endswith("m68kmake.c")
                             else ["test"] if file.suffix in {".c", ".h"} else [])
        require(row["origin"] == origin and row["revision"] == revision, "incorrect origin/revision: " + row["path"])
        require(row["generated"] is (row["path"] in OUTPUTS) and row["copied"] is ((musashi or unity) and row["path"] not in OUTPUTS), "incorrect copied/generated classification")
        require(row["compiled"] == expected_compiled, "unclassified runtime/adaptation source: " + row["path"])
        require(row["distributed"] is True and row["license"] and row["notice"] and row["host_calls"], "missing rights/host disposition")
        notice = (root / row["notice"]).read_text()
        require("Permission is hereby granted" in notice and "THE SOFTWARE IS PROVIDED" in notice, "missing license notice: " + row["path"])
        if row["copied"] or row["generated"]:
            text = file.read_text()
            if file.suffix in {".c", ".h"}:
                require("Copyright" in text, "removed file copyright: " + row["path"])
    require(manifest["host_call_dispositions"] == HOST_CALLS, "host call disposition mismatch")
    return manifest

def regenerate(root=ROOT, receipt=None, interrupt=False):
    manifest = inventory(root)
    with tempfile.TemporaryDirectory(prefix="cpu-generation-") as temporary:
        scratch = Path(temporary)
        generator = scratch / "generator"
        compiler = os.environ.get("CC", "cc")
        run([compiler, "-std=c17", root / "third_party/musashi/m68kmake.c", "-o", generator], root)
        def generate(number):
            target = scratch / str(number)
            target.mkdir()
            run([generator, target, root / "third_party/musashi/m68k_in.c"], root)
            return {name: (target / name).read_bytes() for name in ("m68kops.c", "m68kops.h")}
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(generate, (1, 2)))
        require(first == second, "parallel regeneration mismatch")
        require(all(data == (root / "third_party/musashi" / name).read_bytes() for name, data in first.items()), "regenerated bytes differ")
        if interrupt:
            raise AuditError("injected interruption before receipt publication")
        result = {"status": "pass", "manifest_sha256": sha(root / "tools/cpu/source-manifest.json"),
                  "generator_sha256": sha(root / "third_party/musashi/m68kmake.c"),
                  "compiler": run([compiler, "--version"], root).splitlines()[0],
                  "independent_parallel_directories": 2,
                  "outputs": {name: hashlib.sha256(data).hexdigest() for name, data in first.items()}}
        if receipt:
            atomic_json(receipt, result)
        return result

def symbols(output):
    defined, undefined = set(), set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[-2]) == 1:
            symbol = parts[-1]
            if sys.platform == "darwin" and symbol.startswith("_"):
                symbol = symbol[1:]
            (undefined if parts[-2] == "U" else defined).add(symbol)
    return defined, undefined

def check_imports(imports):
    require(not (set(imports) - HOST_CALLS.keys()), "forbidden runtime import: " + str(sorted(set(imports) - HOST_CALLS.keys())))

def closure(root=ROOT):
    root = root.resolve()
    manifest = inventory(root)
    require(not any((root / "third_party/musashi" / name).exists() for name in ("softfloat", "m68kfpu.c", "m68kmmu.h", "m68kmame.h")), "excluded dependency present")
    lanes = []
    with tempfile.TemporaryDirectory(prefix="cpu-closure-") as temporary:
        for optimization in ("NONE", "RELEASE"):
            build = Path(temporary) / optimization
            run(["cmake", "-S", root, "-B", build, "-G", "Ninja", "-DGLUEYNEO_CPU_EXPERIMENT=ON",
                 "-DGLUEYNEO_CPU_OPTIMIZATION=" + optimization, "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"], root)
            run(["cmake", "--build", build, "--target", "cpu_runtime", "--parallel", "2"], root, 120)
            commands = [row for row in json.loads((build / "compile_commands.json").read_text()) if "cpu_runtime.dir" in row["command"]]
            expected = {"experiments/cpu/cpu_adapter.c", "third_party/musashi/m68kcpu.c", "third_party/musashi/m68kops.c"}
            require({str(Path(row["file"]).relative_to(root)) for row in commands} == expected, "runtime compile closure mismatch")
            includes = run(["ninja", "-C", build, "-t", "deps"], root)
            require(not re.search(r"softfloat|m68kfpu|m68kmmu|m68kmame", includes, re.I), "excluded compiled include")
            project_dependencies = set()
            for line in includes.splitlines():
                name = line.strip()
                if not line.startswith("    ") or not Path(name).is_absolute():
                    continue
                dependency = Path(name)
                if dependency.is_relative_to(root):
                    require(dependency.resolve().is_relative_to(root), "runtime dependency escapes source tree")
                    project_dependencies.add(dependency.resolve().relative_to(root).as_posix())
            require(project_dependencies and project_dependencies <= RUNTIME_FILES, "unclassified runtime dependency: " + str(sorted(project_dependencies - RUNTIME_FILES)))
            translation_units = []
            compiler = None
            for row in commands:
                args = shlex.split(row["command"])
                compiler = args[0]
                args = args[:args.index("-o")] + ["-E", row["file"]]
                preprocessed = run(args, row["directory"])
                require(not re.search(r'^#.*(?:softfloat/|m68kfpu|m68kmmu|m68kmame)', preprocessed, re.M | re.I), "excluded preprocessed include")
                ast = run(args[:-2] + ["-Xclang", "-ast-dump", "-fsyntax-only", row["file"]], row["directory"])
                refs = set(re.findall(r"DeclRefExpr[^\n]*Function[^\n]* '([^']+)' '", ast))
                require(refs, "zero AST function references; unsupported compiler audit")
                require(not (refs & FORBIDDEN), "forbidden runtime AST reference: " + str(sorted(refs & FORBIDDEN)))
                require(not any(re.search(r"softfloat|m68040_fpu|pmmu_translate|m68881_mmu", ref) for ref in refs), "FPU/MMU compiled reference")
                translation_units.append({"source": str(Path(row["file"]).relative_to(root)),
                                          "preprocessed_sha256": hashlib.sha256(preprocessed.replace(str(root), "<source>").encode()).hexdigest(),
                                          "function_references": sorted(refs)})
            archive = build / "experiments/cpu/libcpu_runtime.a"
            members = run(["ar", "-t", archive], root).splitlines()
            require({name for name in members if not name.startswith("__.SYMDEF")} == {"cpu_adapter.c.o", "m68kcpu.c.o", "m68kops.c.o"}, "host/test object in runtime")
            defined, undefined = symbols(run(["nm", "-g", archive], root))
            imports = undefined - defined
            check_imports(imports)
            consumer = build / "closure_consumer.c"
            consumer.write_text('#include "cpu_adapter.h"\nint main(void) { cpu_instance *p=0; cpu_bus b={0}; cpu_allocator a={0}; (void)cpu_create(68000,b,a,&p); (void)cpu_reset(p); (void)cpu_run(p,0); cpu_destroy(p); return 0; }\n')
            link_map = build / "runtime.map"
            map_flag = "-Wl,-map," if sys.platform == "darwin" else "-Wl,-Map,"
            run([compiler, "-std=c17", "-I" + str(root / "experiments/cpu"), consumer, archive, map_flag + str(link_map), "-o", build / "consumer"], root)
            map_text = link_map.read_text()
            require("cpu_adapter.c.o" in map_text and "m68kcpu.c.o" in map_text and "m68kops.c.o" in map_text, "incomplete runtime link map")
            require(not re.search(r"unity\.c\.o|m68kmake\.c\.o", map_text), "test/generator object linked into consumer")
            lanes.append({"optimization": optimization, "compiler": run([compiler, "--version"], root).splitlines()[0],
                          "archive_members": members, "host_imports": sorted(imports), "translation_units": translation_units,
                          "project_dependencies": sorted(project_dependencies),
                          "compile_dependencies_sha256": hashlib.sha256(includes.replace(str(root), "<source>").replace(str(build), "<build>").encode()).hexdigest(),
                          "link_map_sha256": hashlib.sha256(map_text.replace(str(root), "<source>").replace(str(build), "<build>").encode()).hexdigest()})
    return {"status": "pass", "manifest_sha256": sha(root / "tools/cpu/source-manifest.json"), "lanes": lanes,
            "scope": "native compiler closure only; no platform matrix or backend admission"}

def state_inventory(root=ROOT):
    from state_inventory import verify
    return verify(root)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("budget", "closure", "regenerate", "self-test", "state_inventory"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--interrupt", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    try:
        root = args.root.resolve()
        if args.command == "self-test":
            checked = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests/cpu", "-p", "test_audit.py"], cwd=root, capture_output=True, text=True, timeout=180)
            output = checked.stdout + checked.stderr
            count = re.search(r"Ran ([1-9][0-9]*) tests?", output)
            require(checked.returncode == 0 and count, "audit controls failed or zero tests:\n" + output)
            result = {"status": "pass", "controls": "tests/cpu/test_audit.py", "tests": int(count[1])}
        elif args.command == "regenerate":
            result = regenerate(root, interrupt=args.interrupt)
        else:
            result = globals()[args.command](root)
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        if args.receipt:
            atomic_json(args.receipt, result)
        print(json.dumps(result, indent=2))
    except (AuditError, KeyError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print("FAIL: " + str(error).replace(str(ROOT), "<source>"), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
