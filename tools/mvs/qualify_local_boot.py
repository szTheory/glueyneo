#!/usr/bin/env python3
"""Run bounded, private MVS import/guest qualification without logging identity."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def ignored(path: Path) -> bool:
    result = subprocess.run(["git", "check-ignore", "-q", str(path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            check=False)
    return result.returncode == 0


def safe_result(report: dict[str, object]) -> dict[str, object]:
    status = report.get("status")
    if not isinstance(status, str):
        return {"status": "qualification_report_invalid"}
    clean: dict[str, object] = {
        "status": status,
        "retroarch_observation": "manual-only-unknown",
        "private_identity_recorded": False,
    }
    if report.get("guest_executed") is True:
        clean["guest_executed"] = True
    event = report.get("first_unsupported_event")
    if isinstance(event, dict):
        pc, opcode = event.get("pc"), event.get("opcode")
        if isinstance(pc, int) and isinstance(opcode, int):
            clean["first_unsupported_event"] = {"pc": pc, "opcode": opcode}
    return clean


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", default="local/roms")
    parser.add_argument("--report", default="local/qualification/phase05.json")
    parser.add_argument("--importer", default="build/sdk-debug/mvs_importer")
    parser.add_argument("--runner", default="build/sdk-debug/mvs_qualify")
    args = parser.parse_args()

    input_root = Path(args.input_root)
    report_path = Path(args.report)
    if input_root.as_posix() != "local/roms" or \
            report_path.as_posix() != "local/qualification/phase05.json":
        parser.error("local qualification accepts only the ignored default paths")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not ignored(input_root) or not ignored(report_path):
        print("local qualification paths must be Git-ignored")
        return 2

    if not input_root.is_dir():
        result = {"status": "private_media_unavailable",
                  "retroarch_observation": "manual-only-unknown",
                  "private_identity_recorded": False}
    else:
        archives = [path for path in input_root.iterdir()
                    if path.is_file() and not path.is_symlink() and
                    path.suffix.lower() == ".zip"]
        imported: list[Path] = []
        runner_report: dict[str, object] | None = None
        with tempfile.TemporaryDirectory(prefix="glueyneo-mvs-") as temporary:
            normalized = Path(temporary) / "normalized.gnmv"
            for archive in archives:
                imported_result = subprocess.run(
                    [args.importer, str(archive), str(normalized)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False,
                )
                if imported_result.returncode == 0:
                    imported.append(archive)
            if len(imported) == 1:
                execution = subprocess.run([args.runner, str(normalized)],
                                           capture_output=True, text=True,
                                           check=False)
                try:
                    decoded = json.loads(execution.stdout)
                    runner_report = safe_result(decoded)
                except (json.JSONDecodeError, TypeError):
                    runner_report = {"status": "native_qualification_failed"}
        if len(imported) == 0:
            result = {"status": "no_supported_role_bundle_archive",
                      "retroarch_observation": "manual-only-unknown",
                      "private_identity_recorded": False,
                      "first_blocking_checkpoint": "archive_to_region_mapping",
                      "next_technical_dependency":
                          "map the supported game and BIOS archives to the normalized MVS region contract"}
        elif len(imported) > 1:
            result = {"status": "ambiguous_private_media_inputs",
                      "retroarch_observation": "manual-only-unknown",
                      "private_identity_recorded": False}
        else:
            result = runner_report or {"status": "native_qualification_failed",
                                       "retroarch_observation": "manual-only-unknown",
                                       "private_identity_recorded": False}

    temporary_report = report_path.with_suffix(".json.tmp")
    temporary_report.write_text(json.dumps(result, sort_keys=True) + "\n",
                                encoding="utf-8")
    os.replace(temporary_report, report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
