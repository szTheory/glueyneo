#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute and validate the public first-run SDK guide."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path, PureWindowsPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_package
from check_package import (
    ROOT,
    COMMAND_TIMEOUT_SECONDS,
    CheckError,
    clean_environment,
    new_work_dir,
    run,
    sha256,
    stage_documentation_project,
    validate_persistence_result_record,
)


GUIDE = ROOT / "docs" / "sdk-examples.md"
REPAIR_FLAG = re.compile(
    r"(?:^|\s)(?:-I|-L|-Wl,|CMAKE_(?:PREFIX_PATH|MODULE_PATH|C_FLAGS|CXX_FLAGS)|"
    r"(?:DYLD|LD)_LIBRARY_PATH)(?:\s|=|$)"
)


def guide_commands(variant: str, guide: Path = GUIDE) -> list[str]:
    section = "static" if variant == "static" else "shared"
    start = f"<!-- sdk-examples:{section}-commands:start -->"
    end = f"<!-- sdk-examples:{section}-commands:end -->"
    text = guide.read_text(encoding="utf-8")
    if text.count(start) != 1 or text.count(end) != 1:
        raise CheckError(f"Guide must contain exactly one {variant} command block")
    body = text.split(start, 1)[1].split(end, 1)[0]
    fenced = re.search(r"```sh\s*\n(.*?)\n```", body, re.DOTALL)
    if fenced is None:
        raise CheckError(f"Guide {variant} commands are not in one shell block")
    commands: list[str] = []
    pending = ""
    for raw_line in fenced.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1].rstrip() + " "
            continue
        commands.append(pending + line)
        pending = ""
    if pending:
        raise CheckError(f"Guide {variant} command block ends with an incomplete line")
    if len(commands) != 14:
        raise CheckError(f"Guide {variant} command block must contain 14 commands, found {len(commands)}")
    for command in commands:
        if REPAIR_FLAG.search(command):
            raise CheckError(f"Guide command contains a manual linker/search-path repair: {command}")
    return commands


def command_argv(
    command: str, cwd: Path, *, cmake_generator: str | None = None,
) -> list[str]:
    # Parse the controlled shell syntax before expanding the host path so a
    # Windows cwd never passes through POSIX shlex as source text. Join the
    # documented POSIX suffix as path components to preserve native separators.
    argv = shlex.split(command)
    expanded: list[str] = []
    for argument in argv:
        count = argument.count("$PWD")
        if count == 0:
            expanded.append(argument)
            continue
        if count != 1:
            raise CheckError("Guide command must expand $PWD at most once per argument")
        prefix, suffix = argument.split("$PWD", 1)
        if suffix and not suffix.startswith("/"):
            raise CheckError("Guide $PWD suffix must use the documented POSIX path separator")
        components = suffix[1:].split("/") if suffix else []
        if any(component in {"", ".", ".."} for component in components):
            raise CheckError("Guide $PWD suffix must use normalized path components")
        path = cwd.joinpath(*components) if components else cwd
        expanded.append(prefix + str(path))
    if cmake_generator and expanded[0] == "cmake" and "-S" in expanded and "-B" in expanded:
        expanded[1:1] = ["-G", cmake_generator]
    if str(ROOT) in " ".join(expanded):
        raise CheckError("Guide command refers to the original source checkout")
    return expanded


def result_record(output: str, prefix: str, role: str) -> dict[str, object]:
    records = [line[len(prefix):] for line in output.splitlines() if line.startswith(prefix)]
    if len(records) != 1:
        raise CheckError(f"Expected one {prefix.strip()} result record, found {len(records)}")
    try:
        record = json.loads(records[0])
    except json.JSONDecodeError as error:
        raise CheckError(f"Malformed {prefix.strip()} result record: {error}") from error
    if record.get("role") != role:
        raise CheckError(f"Expected {role} result from {prefix.strip()}, got {record}")
    return record


def blocked_network_environment() -> dict[str, str]:
    env = clean_environment()
    # The unserved local port makes an accidental network request fail closed.
    blocked_proxy = "http://localhost:9"
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env[name] = blocked_proxy
    env["NO_PROXY"] = ""
    env["no_proxy"] = ""
    return env


OUTCOMES = {"pass", "fail", "unsupported", "skipped", "unknown"}
MATRIX_SPECS = {
    "docs/testing.md": (
        "Package consumption support matrix",
        ["Source/artifact identity", "OS / architecture", "Compiler / SDK",
         "Configuration / linkage", "Outcome", "Result identity"],
    ),
    "docs/native-state.md": (
        "Native state exchange support matrix",
        ["Source/build identity", "Profile/media/semantic identities",
         "Actual build pair", "Outcome", "Scope"],
    ),
    "docs/native-save.md": (
        "Native persistence support matrix",
        ["Source/build identity", "OS / filesystem", "Host and slot ownership",
         "Commit / failure evidence", "Outcome", "Limit"],
    ),
    "docs/frontend-continuation.md": (
        "Frontend operation support matrix",
        ["Frontend/core source identity", "Host / configuration",
         "Allowed operation set", "Outcome", "Claim or limit"],
    ),
}


def read_contract_documents() -> dict[str, str]:
    return {path: (ROOT / path).read_text(encoding="utf-8") for path in MATRIX_SPECS}


def _load_verify_sdk_module():
    path = ROOT / "tools" / "verify_sdk.py"
    spec = importlib.util.spec_from_file_location("example_docs_verify_sdk", path)
    if spec is None or spec.loader is None:
        raise CheckError("could not load the SDK source-identity provider")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_matrix(
    document: str,
    heading: str,
    expected_headers: list[str],
    *,
    require_outcome: bool = True,
) -> list[dict[str, str]]:
    lines = document.splitlines()
    matches = [index for index, line in enumerate(lines)
               if line.lstrip("# ").strip() == heading]
    if len(matches) != 1:
        raise CheckError(f"expected one named matrix {heading!r}; found {len(matches)}")
    table_lines: list[str] = []
    for line in lines[matches[0] + 1:]:
        if line.strip().startswith("|"):
            table_lines.append(line.strip())
        elif table_lines:
            break
    if len(table_lines) < 3:
        raise CheckError(f"matrix {heading!r} has no complete table")

    def cells(line: str) -> list[str]:
        return [" ".join(cell.strip().split())
                for cell in line.strip().strip("|").split("|")]

    headers = cells(table_lines[0])
    separator = cells(table_lines[1])
    if headers != expected_headers or not all(re.fullmatch(r":?-+:?", value) for value in separator):
        raise CheckError(f"matrix {heading!r} has wrong fields or malformed header")
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        values = cells(line)
        if len(values) != len(headers):
            raise CheckError(f"matrix {heading!r} has a row with the wrong number of fields")
        row = dict(zip(headers, values))
        if require_outcome:
            row["Outcome"] = row["Outcome"].strip("`").casefold()
            if row["Outcome"] not in OUTCOMES:
                raise CheckError(f"matrix {heading!r} has an invalid outcome {row['Outcome']!r}")
        if any(not value for value in row.values()):
            raise CheckError(f"matrix {heading!r} has an empty identity or evidence field")
        rows.append(row)
    return rows


def validate_evidence_matrices(documents: dict[str, str]) -> int:
    """Enforce separate matrix ownership, identity fields, and evidence outcomes."""
    if set(documents) != set(MATRIX_SPECS):
        raise CheckError("support matrix document set is incomplete or widened")
    loaded: dict[str, list[dict[str, str]]] = {}
    for path, (heading, headers) in MATRIX_SPECS.items():
        document = documents[path]
        normalized = " ".join(document.casefold().split())
        vocabulary = "`pass`, `fail`, `unsupported`, `skipped`, and `unknown`"
        if vocabulary not in normalized:
            raise CheckError(f"{path} must name all five evidence outcomes")
        for other_path, (other_heading, _headers) in MATRIX_SPECS.items():
            if other_path != path and other_heading.casefold() in normalized:
                raise CheckError(f"{path} contains another owner's matrix {other_heading!r}")
        loaded[path] = parse_matrix(document, heading, headers)

    package_rows = loaded["docs/testing.md"]
    by_artifact = {row["Source/artifact identity"]: row for row in package_rows}
    release_rows = [row for row in package_rows
                    if "glueyneo-sdk-0.2.1-" in row["Source/artifact identity"]]
    required_artifacts = (
        "glueyneo-sdk-0.2.1-linux-x86_64.tar.gz",
        "glueyneo-sdk-0.2.1-macos-arm64.tar.gz",
        "glueyneo-sdk-0.2.1-windows-x86_64.tar.gz",
    )
    for artifact in required_artifacts:
        matches = [row for row in release_rows if artifact in row["Source/artifact identity"]]
        if len(matches) != 1 or matches[0]["Outcome"] != "pass":
            raise CheckError(f"published package row is missing or not a passing exact artifact: {artifact}")
        row = matches[0]
        for field in ("OS / architecture", "Compiler / SDK", "Configuration / linkage", "Result identity"):
            if not row[field]:
                raise CheckError(f"package matrix {artifact} omits {field}")
        if "sha-256" not in row["Source/artifact identity"].casefold():
            raise CheckError(f"package matrix omits the artifact digest: {artifact}")
    local_rows = [row for row in package_rows
                  if "Local source guide at" in row["Source/artifact identity"]]
    linux_pending = [row for row in package_rows
                     if "Current Phase 07 Linux Clang sanitizer" in row["Source/artifact identity"]]
    if (len(local_rows) != 1 or local_rows[0]["Outcome"] != "pass" or
            "28 commands" not in local_rows[0]["Result identity"] or
            len(linux_pending) != 1 or linux_pending[0]["Outcome"] != "unknown" or
            "BUILD-05 remains pending" not in linux_pending[0]["Result identity"]):
        raise CheckError("package matrix must retain the local pass and pending Linux unknown separately")

    state_rows = loaded["docs/native-state.md"]
    state_text = " ".join(documents["docs/native-state.md"].casefold().split())
    if (not any("1aee4c0369f1efb8f7e244eadb8522124c063909" in row["Source/build identity"]
                and row["Outcome"] == "pass" and "Debug" in row["Actual build pair"]
                and "Release" in row["Actual build pair"]
                for row in state_rows) or
            not any("Any other OS" in row["Source/build identity"] and row["Outcome"] == "unknown"
                    for row in state_rows) or
            not any("outside diagnostic and MVS MSX" in row["Source/build identity"]
                    and row["Outcome"] == "unsupported" for row in state_rows)):
        raise CheckError("native state matrix lost its exact pair, unknown boundary, or unsupported profile")
    if "source revision and content hashes identify the tested builds and provenance; they are not import gates" not in state_text:
        raise CheckError("native state source hashes must remain provenance, not import conditions")

    save_source_identity = _load_verify_sdk_module().save_source_identity(ROOT)
    save_rows = loaded["docs/native-save.md"]
    save_text = " ".join(documents["docs/native-save.md"].casefold().split())
    if (not any(save_source_identity in
                row["Source/build identity"] and "Darwin 25.6.0" in row["OS / filesystem"]
                and "APFS" in row["OS / filesystem"] and row["Outcome"] == "pass"
                for row in save_rows) or
            not any("Non-Darwin" in row["Source/build identity"] and row["Outcome"] == "unsupported"
                    for row in save_rows) or
            not any("Physical power-loss" in row["Source/build identity"]
                    and row["Outcome"] == "unknown" for row in save_rows)):
        raise CheckError("native persistence matrix lost its measured host, unsupported, or unknown row")
    for phrase in (
        "one writer per authoritative slot", "successful ack consumes the exact receipt",
        "it does not roll guest sram backward", "full historical sram rollback occurs only",
        "`discard` is an explicit loss choice", "it does not ack, flush",
        "discard never acks",
        "all six restore/scope/slot/replacement/unload/destroy transitions stay blocked",
    ):
        if phrase not in save_text:
            raise CheckError(f"native save ownership/loss boundary is missing: {phrase}")

    frontend_rows = loaded["docs/frontend-continuation.md"]
    frontend_text = " ".join(documents["docs/frontend-continuation.md"].casefold().split())
    false_policy = [row for row in frontend_rows
                    if "block_sram_overwrite=false" in row["Host / configuration"]]
    true_policy = [row for row in frontend_rows
                   if "block_sram_overwrite=true" in row["Host / configuration"]]
    if (len(false_policy) != 1 or false_policy[0]["Outcome"] != "pass" or
            "Exact historical continuation" not in false_policy[0]["Claim or limit"] or
            len(true_policy) != 1 or true_policy[0]["Outcome"] != "pass" or
            "Preserve-current SRAM only" not in true_policy[0]["Claim or limit"] or
            "not exact historical whole-machine continuation" not in true_policy[0]["Claim or limit"] or
            not any("threaded periodic autosave concurrent" in row["Allowed operation set"].casefold()
                    and row["Outcome"] == "unsupported" for row in frontend_rows) or
            not any("Other RetroArch binaries" in row["Frontend/core source identity"]
                    and row["Outcome"] == "unknown" for row in frontend_rows)):
        raise CheckError("frontend matrix overstates historical SRAM or threaded autosave support")
    for phrase in (
        "autosave_interval=0", "autosave_interval=1", "no state load or undo",
        "combined threaded-autosave and state-operation case is unsupported",
    ):
        if phrase not in frontend_text:
            raise CheckError(f"frontend operation limit is missing: {phrase}")

    expected_compatibility = {
        "Package version", "Public ABI ID", "GNST format ID", "Replay behavior ID",
        "Profile/configuration IDs", "Normalized media identity", "durable_save_id",
        "Source revision/content SHA-256",
    }
    _compat_headers = ["Identity", "Current value or source", "Governs", "Does not govern"]
    compatibility_rows = parse_matrix(
        documents["docs/native-state.md"], "Independent distribution and exchange identities",
        _compat_headers,
        require_outcome=False,
    )
    if ({row["Identity"].strip("`") for row in compatibility_rows} != expected_compatibility or
            any("GNST import compatibility" not in row["Does not govern"]
                for row in compatibility_rows if row["Identity"] == "Package version") or
            any("A condition for importing a state" not in row["Does not govern"]
                for row in compatibility_rows if row["Identity"] == "Source revision/content SHA-256")):
        raise CheckError("package, ABI, state, replay, save, and source identities were conflated")

    return sum(len(rows) + 1 for rows in loaded.values()) + len(compatibility_rows)


class ExampleGuideCommandTests(unittest.TestCase):
    assertion_count = 0
    cmake_generator: str | None = None

    def __getattribute__(self, name: str):
        attribute = super().__getattribute__(name)
        if name.startswith("assert") and callable(attribute):
            def count_assertion(*args, **kwargs):
                type(self).assertion_count += 1
                return attribute(*args, **kwargs)
            return count_assertion
        return attribute

    def test_documented_commands(self) -> None:
        type(self).assertion_count = 0
        self.assertTrue(GUIDE.is_file(), "the task-oriented guide must exist at docs/sdk-examples.md")
        network_env = blocked_network_environment()
        executed = 0
        checked_records = 0
        variants: dict[str, dict[str, object]] = {}

        for variant in ("static", "shared"):
            work = new_work_dir(f"example-guide-{variant}")
            source = work / "project"
            stage_documentation_project(source)
            staged_guide = source / "docs" / "sdk-examples.md"
            self.assertEqual(staged_guide.read_bytes(), GUIDE.read_bytes())
            commands = guide_commands(variant, staged_guide)
            last_outputs: list[tuple[list[str], str]] = []
            persistence_executable: Path | None = None
            host_producer: dict[str, object] | None = None
            fixture: Path | None = None
            for command in commands:
                argv = command_argv(command, source, cmake_generator=self.cmake_generator)
                result = run(argv, cwd=source, env=network_env,
                             timeout=COMMAND_TIMEOUT_SECONDS)
                executed += 1
                last_outputs.append((argv, result.stdout))
                executable = argv[0]
                if "glueyneo-installed-sound" in executable:
                    fixture = source / argv[-1]
                    self.assertTrue(fixture.is_file(), "the public fixture command must create its input")
                    self.assertGreater(fixture.stat().st_size, 0)
                elif argv[:2] == ["cmake", "--install"]:
                    installed = source / "build" / f"install-{variant}"
                    package = installed / "lib" / "cmake" / "Glueyneo"
                    self.assertTrue((package / "GlueyneoConfig.cmake").is_file())
                    self.assertTrue((package / "GlueyneoTargets-release.cmake").is_file())
                elif (argv[:2] == ["cmake", "--build"] and
                      argv[2].startswith("build/examples-")):
                    binary_dir = source / argv[2]
                    extension = ".exe" if sys.platform == "win32" else ""
                    self.assertTrue(
                        (binary_dir / f"glueyneo-installed-sound{extension}").is_file(),
                        "documented consumer executables must share the guide's stable build path",
                    )
                elif "glueyneo-installed-continuation" in executable:
                    role = "producer" if "--produce" in argv else "reader"
                    record = result_record(result.stdout, "SDK_CONTINUATION ", role)
                    self.assertEqual(record.get("outcome"), "pass")
                    self.assertGreater(record.get("assertions", 0), 0)
                    checked_records += 1
                elif "glueyneo-installed-persistence" in executable:
                    persistence_executable = source / executable.removeprefix("./")
                    role = argv[argv.index("--role") + 1]
                    record = result_record(result.stdout, "SDK_PERSISTENCE ", role)
                    route = validate_persistence_result_record(record)
                    if route == "portable":
                        self.assertEqual(record.get("outcome"), "pass")
                        self.assertEqual(record.get("host_file_commit"), "not_claimed")
                        self.assertGreaterEqual(record.get("fixture_bytes", 0), 60 * 1024 * 1024)
                        self.assertLess(record.get("fixture_bytes", 0), 65 * 1024 * 1024)
                    else:
                        self.assertIn(record.get("outcome"), {"pass", "unsupported"})
                        if record.get("outcome") == "unsupported":
                            self.assertEqual(record.get("host_file_commit"), "unsupported")
                            self.assertTrue(record.get("reason"))
                        else:
                            self.assertIn(record.get("host_file_commit"),
                                          {"committed_darwin_apfs", "read_only_reopen"})
                        if role == "producer":
                            host_producer = record
                    checked_records += 1

            self.assertEqual(len(last_outputs), 14)
            self.assertEqual(checked_records % 6, 0)
            self.assertIsNotNone(fixture)
            self.assertIsNotNone(persistence_executable)
            compile_db = source / f"build/examples-{variant}" / "compile_commands.json"
            self.assertTrue(compile_db.is_file(), "guide must export consumer compile commands")
            compile_text = compile_db.read_text(encoding="utf-8")
            self.assertNotIn(str(ROOT), compile_text)
            self.assertNotIn(str(source / f"build/sdk-{variant}" / "CMakeFiles"), compile_text)
            self.assertIn(str(source / f"build/install-{variant}"), compile_text)
            self._check_host_failure_outcomes(
                source, variant, persistence_executable, host_producer, network_env,
            )
            self._check_missing_helper_control(
                source, variant, network_env, cmake_generator=self.cmake_generator,
            )
            variants[variant] = {
                "commands": 14,
                "fixture_bytes": fixture.stat().st_size,
                "host_outcome": (host_producer or {}).get("outcome"),
            }

        self.assertEqual(executed, 28)
        self.assertEqual(checked_records, 12)
        self.assertEqual(set(variants), {"static", "shared"})
        print("SDK_EXAMPLE_DOCS " + json.dumps({
            "schema_version": 1,
            "case_id": "sdk.docs.runnable-entry-guide",
            "outcome": "pass",
            "assertions": type(self).assertion_count,
            "commands_executed": executed,
            "result_records_checked": checked_records,
            "missing_helper_controls": 2,
            "variants": variants,
        }, sort_keys=True))

    def _check_host_failure_outcomes(
        self,
        source: Path,
        variant: str,
        executable: Path,
        producer: dict[str, object] | None,
        env: dict[str, str],
    ) -> None:
        if producer is None or producer.get("outcome") == "unsupported":
            return
        slot = source / f"build/sdk-{variant}-host/slot.gnsave"
        before = sha256(slot)
        output = run([
            str(executable), "--mode", "host", "--role", "producer", "--value", "A",
            "--slot", str(slot), "--scratch-dir", str(slot.parent),
            "--scope", "00000000000000000000000000000003",
        ], cwd=source, env=env, expected_returncode=2)
        record = result_record(output.stdout, "SDK_PERSISTENCE ", "producer")
        self.assertEqual(record.get("outcome"), "invalid")
        self.assertEqual(record.get("reason"), "slot_already_exists")
        self.assertEqual(sha256(slot), before, "refusing an existing slot must preserve its bytes")

        missing_dir = source / f"build/sdk-{variant}-failure-missing"
        missing_dir.mkdir()
        missing = missing_dir / "slot.gnsave"
        output = run([
            str(executable), "--mode", "host", "--role", "reader", "--reopen",
            "--slot", str(missing), "--scratch-dir", str(missing_dir),
            "--scope", "00000000000000000000000000000009",
        ], cwd=source, env=env, expected_returncode=2)
        record = result_record(output.stdout, "SDK_PERSISTENCE ", "reader")
        self.assertEqual((record.get("outcome"), record.get("reason")), ("invalid", "slot_missing"))

        invalid_dir = source / f"build/sdk-{variant}-failure-invalid"
        invalid_dir.mkdir()
        invalid = invalid_dir / "slot.gnsave"
        invalid.write_bytes(b"not a GNSV save")
        output = run([
            str(executable), "--mode", "host", "--role", "reader", "--reopen",
            "--slot", str(invalid), "--scratch-dir", str(invalid_dir),
            "--scope", "0000000000000000000000000000000a",
        ], cwd=source, env=env, expected_returncode=2)
        record = result_record(output.stdout, "SDK_PERSISTENCE ", "reader")
        self.assertEqual((record.get("outcome"), record.get("reason")), ("invalid", "slot_invalid"))

        malformed_dir = source / f"build/sdk-{variant}-failure-format"
        malformed_dir.mkdir()
        malformed = malformed_dir / "slot.gnsave"
        malformed.write_bytes(bytes(96 + 65536))
        output = run([
            str(executable), "--mode", "host", "--role", "reader", "--reopen",
            "--slot", str(malformed), "--scratch-dir", str(malformed_dir),
            "--scope", "0000000000000000000000000000000b",
        ], cwd=source, env=env, expected_returncode=2)
        record = result_record(output.stdout, "SDK_PERSISTENCE ", "reader")
        self.assertEqual((record.get("outcome"), record.get("reason")),
                         ("invalid", "slot_format_invalid"))

    def _check_missing_helper_control(
        self, source: Path, variant: str, env: dict[str, str],
        *, cmake_generator: str | None = None,
    ) -> None:
        missing_source = new_work_dir(f"example-guide-missing-{variant}") / "project"
        stage_documentation_project(missing_source)
        withheld = missing_source / "examples" / "persistence_host.c"
        self.assertTrue(withheld.is_file(), "the guide closure must include its host writer helper")
        withheld.unlink()
        installed = source / f"build/install-{variant}"
        shutil.copytree(installed, missing_source / f"build/install-{variant}")
        configure = next(
            command for command in guide_commands(variant, source / "docs" / "sdk-examples.md")
            if "cmake -S tests/consumers" in command
        )
        build = next(
            command for command in guide_commands(variant, source / "docs" / "sdk-examples.md")
            if command.startswith("cmake --build build/examples-")
        )
        run(command_argv(configure, missing_source, cmake_generator=cmake_generator),
            cwd=missing_source, env=env)
        run(command_argv(build, missing_source), cwd=missing_source, env=env)
        target = "glueyneo-installed-persistence"
        missing_target = subprocess.run([
            shutil.which("cmake") or "cmake", "--build", f"build/examples-{variant}",
            "--target", target,
        ], cwd=missing_source, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=COMMAND_TIMEOUT_SECONDS, check=False)
        self.assertNotEqual(missing_target.returncode, 0,
                            "withholding a documented helper must remove its target")
        self.assertRegex(missing_target.stdout.lower(), r"(no rule|unknown target|could not be found)")


class ExampleGuideContractTests(unittest.TestCase):
    assertion_count = 0
    mutation_count = 0

    def __getattribute__(self, name: str):
        attribute = super().__getattribute__(name)
        if name.startswith("assert") and callable(attribute):
            def count_assertion(*args, **kwargs):
                type(self).assertion_count += 1
                return attribute(*args, **kwargs)
            return count_assertion
        return attribute

    @classmethod
    def setUpClass(cls) -> None:
        cls.assertion_count = 0
        cls.mutation_count = 0

    def test_command_argv_preserves_expanded_path_separators(self) -> None:
        windows_root = PureWindowsPath(r"C:\build\guide with spaces\project")
        windows_command = 'cmake -S "$PWD" -DCMAKE_INSTALL_PREFIX="$PWD/build/install-static"'
        windows_argv = command_argv(windows_command, windows_root)
        self.assertEqual(windows_argv, [
            "cmake",
            "-S",
            str(windows_root),
            "-DCMAKE_INSTALL_PREFIX=" + str(windows_root / "build" / "install-static"),
        ])

        posix_root = Path("/tmp/guide\\literal")
        posix_argv = command_argv('cmake -S "$PWD" -DROOT="$PWD/build"', posix_root)
        self.assertEqual(posix_argv, ["cmake", "-S", str(posix_root), "-DROOT=" + str(posix_root) + "/build"])

        self.assertEqual(
            command_argv("cmake --install build/sdk-static", windows_root),
            ["cmake", "--install", "build/sdk-static"],
        )
        for variant in ("static", "shared"):
            commands = guide_commands(variant)
            build_argv = shlex.split(next(command for command in commands if command.startswith("cmake --build")))
            install_argv = shlex.split(next(command for command in commands if command.startswith("cmake --install")))
            self.assertIn("--config", build_argv)
            self.assertEqual(build_argv[build_argv.index("--config") + 1], "Release")
            self.assertIn("--config", install_argv)
            self.assertEqual(install_argv[install_argv.index("--config") + 1], "Release")

    def _load_verify_sdk(self):
        return _load_verify_sdk_module()

    def _assert_matrix_rejects(self, documents: dict[str, str], detail: str) -> None:
        with self.subTest(mutation=detail), self.assertRaises(CheckError):
            validate_evidence_matrices(documents)
        type(self).mutation_count += 1

    def _replace_outcome(
        self, document: str, heading: str, identity_marker: str, replacement: str,
    ) -> str:
        lines = document.splitlines()
        heading_index = next(index for index, line in enumerate(lines)
                             if line.lstrip("# ").strip() == heading)
        header_index = next(index for index in range(heading_index + 1, len(lines))
                            if lines[index].lstrip().startswith("|"))
        headers = [cell.strip() for cell in lines[header_index].strip().strip("|").split("|")]
        outcome_index = headers.index("Outcome")
        row_index = next(index for index in range(header_index + 2, len(lines))
                         if lines[index].lstrip().startswith("|") and identity_marker in lines[index])
        cells = [cell.strip() for cell in lines[row_index].strip().strip("|").split("|")]
        cells[outcome_index] = f"`{replacement}`"
        lines[row_index] = "| " + " | ".join(cells) + " |"
        return "\n".join(lines) + "\n"

    def test_separate_support_matrices(self) -> None:
        documents = read_contract_documents()
        self.assertGreater(validate_evidence_matrices(documents), 0)
        verify = self._load_verify_sdk()
        save_docs_path = ROOT / "tests/sdk/test_save_process.py"
        save_docs_spec = importlib.util.spec_from_file_location(
            "example_docs_save_contract", save_docs_path)
        if save_docs_spec is None or save_docs_spec.loader is None:
            raise CheckError("could not load the native save owner documentation check")
        save_docs = importlib.util.module_from_spec(save_docs_spec)
        sys.modules[save_docs_spec.name] = save_docs
        save_docs_spec.loader.exec_module(save_docs)
        save_documents = {
            path: (ROOT / path).read_text(encoding="utf-8")
            for path in ("docs/native-save.md", "docs/native-state.md",
                         "docs/state-inventory.md", "docs/ownership-and-errors.md")
        }
        manifest = json.loads((ROOT / "tests/fixture/rights-manifest.json").read_text(encoding="utf-8"))
        save_source_identity = verify.save_source_identity(ROOT)
        save_counts = save_docs.check_save_contract_docs(
            save_documents, (ROOT / "include/glueyneo/glueyneo.h").read_text(encoding="utf-8"),
            (ROOT / "src/instance.c").read_text(encoding="utf-8"), manifest,
            save_source_identity)
        self.assertGreater(sum(save_counts.values()), 0)
        self.assertGreater(verify.frontend_docs_checks(ROOT)["assertions"], 0)
        self.assertGreater(check_package.check_readme_links_and_contracts(), 0)

        for path, heading, marker in (
            ("docs/testing.md", MATRIX_SPECS["docs/testing.md"][0],
             "Current Phase 07 Linux Clang sanitizer"),
            ("docs/native-state.md", MATRIX_SPECS["docs/native-state.md"][0],
             "A profile outside diagnostic and MVS MSX"),
            ("docs/native-save.md", MATRIX_SPECS["docs/native-save.md"][0],
             "Non-Darwin host commit protocol"),
            ("docs/frontend-continuation.md", MATRIX_SPECS["docs/frontend-continuation.md"][0],
             "Threaded periodic autosave concurrent"),
        ):
            candidate = dict(documents)
            candidate[path] = self._replace_outcome(candidate[path], heading, marker, "pass")
            self._assert_matrix_rejects(candidate, f"promote unknown/unsupported to pass: {path}")

        conjoined = dict(documents)
        conjoined["docs/native-state.md"] = conjoined["docs/native-state.md"].replace(
            "Native state exchange support matrix", "Package consumption support matrix", 1)
        self._assert_matrix_rejects(conjoined, "conflate package and native state matrices")
        missing_owner_field = dict(documents)
        missing_owner_field["docs/native-save.md"] = missing_owner_field[
            "docs/native-save.md"].replace("Host and slot ownership", "Host", 1)
        self._assert_matrix_rejects(missing_owner_field, "remove native host ownership field")

    def test_independent_compatibility_identities(self) -> None:
        documents = read_contract_documents()
        self.assertGreater(validate_evidence_matrices(documents), 0)
        mutations = (
            ("source SHA used as state import gate",
             "they are not import gates", "they are import gates"),
            ("package version used as GNST import gate",
             "GNST import compatibility", "GNST import gate"),
            ("public ABI conflated with snapshot format",
             "GNST format ID", "Public ABI ID"),
        )
        for label, token, replacement in mutations:
            candidate = dict(documents)
            candidate["docs/native-state.md"] = candidate["docs/native-state.md"].replace(
                token, replacement, 1)
            with self.subTest(mutation=label), self.assertRaises(CheckError):
                validate_evidence_matrices(candidate)
            type(self).mutation_count += 1

    def test_frontend_operation_limits(self) -> None:
        documents = read_contract_documents()
        self.assertGreater(validate_evidence_matrices(documents), 0)
        verify = self._load_verify_sdk()
        frontend_documents = {
            "frontend": documents["docs/frontend-continuation.md"],
            "first_playable": (ROOT / "docs/first-playable-build.md").read_text(encoding="utf-8"),
            "native_state": documents["docs/native-state.md"],
            "native_save": documents["docs/native-save.md"],
            "testing": documents["docs/testing.md"],
        }
        self.assertGreater(verify.validate_frontend_documentation(frontend_documents), 0)
        save_text = " ".join(documents["docs/native-save.md"].casefold().split())
        self.assertIn("a full historical sram rollback occurs only", save_text)
        self.assertIn("it does not ack, flush", save_text)

        mutations = (
            ("frontend", "Preserve-current SRAM only; not exact historical whole-machine continuation",
             "Exact historical whole-machine continuation"),
            ("docs/native-save.md", "Discard never ACKs.", "Discard ACKs the receipt."),
            ("docs/native-save.md", "it does not ack, flush, or silently publish",
             "it does ACK, flush, and publish"),
            ("docs/native-save.md", "all six restore/scope/slot/replacement/unload/destroy transitions stay blocked",
             "No transitions stay blocked"),
        )
        for path, token, replacement in mutations:
            key = "frontend" if path == "frontend" else path
            source_path = "docs/frontend-continuation.md" if key == "frontend" else key
            candidate = dict(documents)
            pattern = re.compile(r"\s+".join(re.escape(part) for part in token.split()), re.IGNORECASE)
            if pattern.search(candidate[source_path]) is None:
                raise CheckError(f"mutation anchor is missing: {token}")
            candidate[source_path] = pattern.sub(replacement, candidate[source_path])
            with self.subTest(mutation=token), self.assertRaises(CheckError):
                validate_evidence_matrices(candidate)
            type(self).mutation_count += 1


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("commands", "contracts"), required=True)
    parser.add_argument("--generator", choices=("Ninja Multi-Config",), default=None,
                        help="execute documented configure commands with this installed generator")
    args = parser.parse_args()
    if args.mode == "commands":
        ExampleGuideCommandTests.cmake_generator = args.generator
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ExampleGuideCommandTests)
    else:
        if args.generator:
            parser.error("--generator is only valid with --mode commands")
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ExampleGuideContractTests)
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
