"""MIT: compiled state coverage must reject omissions and new mutable storage."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/cpu"))
import state_inventory as inventory
root = Path(__file__).resolve().parents[2]
print(json.dumps(inventory.verify(root)))
with tempfile.TemporaryDirectory(prefix="cpu-state-control-") as directory:
    subject = Path(directory)
    for name in ("experiments/cpu", "third_party/musashi"):
        shutil.copytree(root / name, subject / name)
    path = subject / "experiments/cpu/state-inventory.json"
    original = json.loads(path.read_text())
    missing = json.loads(path.read_text())
    missing["objects"] = [row for row in missing["objects"] if row["name"] != "m68ki_cpu_core.nmi_pending"]
    path.write_text(json.dumps(missing))
    try:
        inventory.verify(subject)
        raise SystemExit("omitted pending NMI was accepted")
    except ValueError as error:
        assert "unclassified or stale compiled declaration" in str(error), str(error)
    source = subject / "experiments/cpu/cpu_adapter.c"
    source.write_text(source.read_text() + "\nstatic int injected_shared_state;\n")
    original["source_hashes"]["experiments/cpu/cpu_adapter.c"] = inventory.digest(source)
    path.write_text(json.dumps(original))
    try:
        inventory.verify(subject)
        raise SystemExit("new shared mutation was accepted")
    except ValueError as error:
        assert "unclassified or stale compiled declaration" in str(error), str(error)
print("PASS: omission and injected mutable declaration controls=2")
