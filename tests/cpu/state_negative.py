"""MIT: require precise consequential state-mutation failures, never a crash."""
import subprocess
import sys
for option, detail in (("--mutate-pending", "Expected 1 Was 0"),
                       ("--mutate-prefetch", "Expected 10 Was 12")):
    r = subprocess.run([sys.argv[1], option], text=True, capture_output=True, timeout=10)
    if (r.returncode != 1 or "1 Tests 1 Failures 0 Ignored" not in r.stdout
            or detail + ":consequential saved-field comparison" not in r.stdout
            or r.stderr):
        raise SystemExit("Wrong mutation failure: " + r.stdout + r.stderr)
    print(option + ": intended consequential assertion failed")
