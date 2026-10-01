"""MIT: bind completed plan-02 CTest runs to exact source and runtime identities."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PLAN = "03" if "--plan03" in sys.argv else "02"
OUT = ROOT / ("experiments/cpu/evidence/plan-01-" + PLAN)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

lanes = []
for directory, expected, sanitizer in (("cpu", 28 if PLAN=="03" else 25, None), ("cpu-asan", 8 if PLAN=="03" else 5, "address,undefined"), ("cpu-tsan", 18, "thread")):
    build = ROOT / "build" / directory
    log = (build / "Testing/Temporary/LastTest.log").read_text()
    if log.count("Test Passed.") != expected or "Test Failed." in log or re.search(r"runtime error:|ERROR: AddressSanitizer|WARNING: ThreadSanitizer|SUMMARY: .*Sanitizer", log):
        raise SystemExit("failed, incomplete or diagnostic-bearing lane: " + directory)
    ninja = (build / "build.ninja").read_text()
    # A reused build directory can retain obsolete objects. Bind the actual
    # archive inputs from Ninja, not every historical file in its object folder.
    archive = re.search(r"^build experiments/cpu/libcpu_runtime.a: C_STATIC_LIBRARY_LINKER[^\n]*", ninja, re.M)
    if not archive:
        raise SystemExit("missing runtime archive linkage")
    objects = [build / p for p in archive[0].split() if p.endswith(".o")]
    if len(objects) != 3:
        raise SystemExit("incomplete actual runtime objects")
    for object in objects:
        relative = object.relative_to(build).as_posix()
        block = re.search(r"^build " + re.escape(relative) + r":.*?(?=\n\n)", ninja, re.M | re.S)
        if not block or (sanitizer and "-fsanitize=" + sanitizer not in block[0]):
            raise SystemExit("runtime object lacks requested instrumentation: " + relative)
        if sanitizer == "address,undefined" and "-fno-sanitize-recover=all" not in block[0]:
            raise SystemExit("recoverable sanitizer diagnostics are not admitted")
    sanitized = log.replace(str(ROOT), "<source>").replace(sys.executable, "<python>")
    sanitized = re.sub(r'"/[^"\n]*python[0-9.]*"', '"<python>"', sanitized)
    log_path = OUT / (directory + ".log")
    log_path.write_text(sanitized)
    lanes.append(dict(build="build/"+directory, status="pass", tests=expected,
                      sanitizer=sanitizer or "none", optimization="O0", diagnostics=0,
                      log=log_path.relative_to(ROOT).as_posix(), log_sha256=sha(log_path),
                      runtime_objects={o.relative_to(ROOT).as_posix():sha(o) for o in objects},
                      runtime_archive_sha256=sha(build / "experiments/cpu/libcpu_runtime.a"),
                      measurements=re.findall(r"(?:cold_)?instance=\d allocations=\d+ bytes=\d+ create_ns=\d+(?: boundaries=\d+)?",log)))
manifest = ROOT / "tools/cpu/source-manifest.json"
result = dict(schema=1,status="plan-01-"+PLAN+"-evidence-not-admission",source_manifest_sha256=sha(manifest),
              state_inventory_sha256=sha(ROOT/'experiments/cpu/state-inventory.json'),
              budget_ledger_sha256=sha(ROOT/'experiments/cpu/budget-ledger.json'),
              source_hashes={r['path']:r['sha256'] for r in json.loads(manifest.read_text())['files']},
              compiler=subprocess.check_output(['cc','--version'],text=True).splitlines()[0],
              platform=subprocess.check_output(['uname','-srm'],text=True).strip(),
              sdk=subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip(),
              lanes=lanes,distinct_compiler=dict(status='unsupported',reason='gcc-14, gcc-15, gcc-16, clang-19 and clang-20 not found; gcc is Apple Clang'),
              limitations=['Native test lane only, no release platform matrix','Timing and fresh-instance continuation remain plan 01-03','No backend admission'],
              counterexamples=['irq-fault-counterexample.json','sanitizer-counterexample.json'])
if PLAN=="03":
    result['limitations']=['Native instruction-boundary timing and private same-build continuation only', 'No bus-cycle, guest bus-error, board, BIOS, public state compatibility or backend admission claim']
    result['counterexamples']=['timing-red.json','reset-counterexamples.md','state-red.json']
(OUT/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(status=result['status'],lanes=[dict(build=x['build'],tests=x['tests'],status=x['status']) for x in lanes])))
