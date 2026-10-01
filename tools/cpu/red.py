"""MIT: translate actual Unity RED results into the installed TAP evidence schema."""
import json
from pathlib import Path
import re
import subprocess
import sys

r = subprocess.run([sys.argv[1], "--red"], text=True, capture_output=True, timeout=10)
raw = r.stdout.replace(str(Path.cwd()) + "/", "")
failures = re.findall(r"^[^\n]+:\d+:([^:\n]+):FAIL:([^\n]+)$", raw, re.M)
summary = re.search(r"(\d+) Tests (\d+) Failures (\d+) Ignored", raw)
if r.returncode != 1 or not summary or tuple(map(int, summary.groups())) != (1, 1, 0) or len(failures) != 1:
    raise SystemExit("No single intentional Unity assertion failure: " + raw)
name, detail = failures[0]
if name != "guest_adds_and_stores" or detail.strip() != "Expected 10 Was 0:guest arithmetic/store result":
    raise SystemExit("Unexpected RED assertion: " + raw)
tap = f"TAP version 13\nnot ok 1 - {name}\n1..1\n# tests 1\n# pass 0\n# fail 1\n"
record = dict(command="python3 tools/cpu/red.py build/cpu/experiments/cpu/cpu_guest", exitCode=r.returncode,
              output=tap, raw_output=raw, targetTest=name, targetFile="tests/cpu/test_guest.c",
              expected="guest stores computed value 10", actual="guest store is 0 before backend implementation")
Path("tests/cpu/red-evidence.json").write_text(json.dumps(record, indent=2) + "\n")
print(tap)
