"""MIT: supervised consequential guest mutation, crash/timeout do not qualify."""
import subprocess
import sys
r = subprocess.run([sys.argv[1], "--mutate"], capture_output=True, text=True, timeout=10)
expected = "guest_adds_and_stores:FAIL: Expected 10 Was 11:guest arithmetic/store result"
if r.returncode != 1 or expected not in r.stdout or "1 Tests 1 Failures 0 Ignored" not in r.stdout:
    print(r.stdout, r.stderr)
    raise SystemExit("negative control did not fail the intended arithmetic assertion")
print("PASS: executed operand mutation failed the arithmetic/store assertion")
