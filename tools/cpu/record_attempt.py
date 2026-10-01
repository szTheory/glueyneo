"""MIT: preserve source-budget and failed-build evidence; not an acceptance audit.

Usage: python3 tools/cpu/record_attempt.py PRISTINE_DIRECTORY
The six pristine files must be acquired explicitly from the documented pin.
No network access or source mutation occurs here. Existing historical receipts
must not be overwritten; use a new --output directory to reproduce them.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("pristine", type=Path)
parser.add_argument("--output", type=Path, default=Path("experiments/cpu/evidence/attempt-1"))
args = parser.parse_args()
root = Path.cwd()
inputs = {
    "m68k.h": "7fb10f51ee36d45f6e2be38d72aa0c57853810a816f1cf19e0f0c600bd1afa4a",
    "m68k_in.c": "7a5836fa60ac5c59f77adbcfe086a288d5356c3d373ab15d337986a4e51e0132",
    "m68kconf.h": "8193cf670f6bfe61ad373055e7f44039427174195109bee78167ff3e0630dca4",
    "m68kcpu.c": "0d98c1bfd104929ca393ab6020c05adaa3de5433961cbf924d0ab78a82778405",
    "m68kcpu.h": "372d2086a9c39aadf87d9e0fa42104c5849bd4972ce74b191c0d458208193635",
    "m68kmake.c": "c6da040b9f9b4a2a30aabc7b26f7228796ef6090934002d9c8a788d754904788",
}
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

if args.output.exists():
    raise SystemExit("Refusing to overwrite historical evidence")
rows, patches = [], []
for name, expected in inputs.items():
    pristine, current = args.pristine / name, Path("third_party/musashi") / name
    if digest(pristine) != expected:
        raise SystemExit("Pristine hash mismatch: " + name)
    diff = subprocess.run(["git", "diff", "--no-index", "--numstat", str(pristine), str(current)], capture_output=True, text=True)
    if diff.returncode not in (0, 1):
        raise SystemExit("Diff failed")
    added, deleted = map(int, diff.stdout.split()[:2])
    patch = subprocess.run(["git", "diff", "--no-index", "--", str(pristine), str(current)], capture_output=True, text=True, check=False)
    if patch.returncode not in (0, 1):
        raise SystemExit("Patch failed")
    normalized = patch.stdout.replace("a" + str(pristine), "a/" + name).replace("b/" + str(current), "b/" + name)
    patches.append(normalized)
    rows.append(dict(file=str(current), pristine_sha256=expected, adapted_sha256=digest(current), added=added, deleted=deleted))
support = ["tools/cpu/adapt.py", "experiments/cpu/cpu_adapter.c", "experiments/cpu/cpu_adapter.h", "experiments/cpu/test_bus.c", "experiments/cpu/test_bus.h"]
support_rows = [dict(file=p, lines=len(Path(p).read_text().splitlines()), sha256=digest(Path(p))) for p in support]
generated = [dict(file=str(p), lines=len(p.read_text().splitlines()), bytes=p.stat().st_size, sha256=digest(p)) for p in sorted(Path("third_party/musashi").glob("m68kops.*"))]
build = subprocess.run(["cmake", "--build", "build/cpu"], text=True, capture_output=True, timeout=30)
build_output = (build.stdout + build.stderr).replace(str(root) + "/", "")
start = datetime.datetime.fromisoformat("2026-10-01T16:19:53+00:00")
now = datetime.datetime.now(datetime.timezone.utc)
record = dict(status="halted", outcome="deferred", attempt=1, candidate="313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd",
    freeze_commit="f9e7dda6ce3593dc176ebfc99f9a6c504bf423f8", starting_revision="3977c3bfbfdc752e1b43443aa3911c7012678177",
    interval=dict(start=start.isoformat(), end=now.isoformat(), charged_seconds=int((now-start).total_seconds()), accounting="conservative full wall interval, including preparation/tool wait"),
    inputs=rows, adaptation_support=support_rows, generated=generated,
    upstream_added_deleted=sum(r["added"]+r["deleted"] for r in rows),
    support_current_lines=sum(r["lines"] for r in support_rows),
    discarded_red_scaffold_lines=15,
    semantic_classification="unreviewed; no acceptance claim",
    commands=[dict(command="cmake --build build/cpu", exit_code=build.returncode)],
    reason="Three inline correction attempts exhausted; initial build still fails. Numeric admission caps have not been shown exceeded.")
args.output.mkdir(parents=True)
(args.output / "source.patch").write_text("".join(patches))
(args.output / "build-failure.txt").write_text(build_output)
(args.output / "receipt.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"outcome":record["outcome"], "build_exit":build.returncode, "upstream_churn":record["upstream_added_deleted"], "support":record["support_current_lines"], "charged_seconds":record["interval"]["charged_seconds"]}))
