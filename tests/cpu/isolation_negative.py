"""MIT: an ownership assertion, not a crash, must reject the swapped baseline."""
import subprocess
import sys
r = subprocess.run([sys.argv[1], "--mutate"], capture_output=True, text=True, timeout=30)
if r.returncode != 1 or "owner_comparison:FAIL:" not in r.stdout or "boundary ownership comparison" not in r.stdout or "3 Tests 1 Failures 0 Ignored" not in r.stdout:
    raise SystemExit("ownership control failed: " + r.stdout + r.stderr)
print("PASS: swapped baseline rejected by boundary ownership comparison")
