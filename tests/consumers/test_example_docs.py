#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute and validate the public first-run SDK guide."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import traceback
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

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
    if sys.platform == "win32" and expanded:
        executable = PureWindowsPath(expanded[0])
        if (len(executable.parts) == 3 and executable.parts[0] == "build" and
                executable.parts[1] in {"examples-static", "examples-shared"} and
                executable.name in {"glueyneo-installed-sound",
                                    "glueyneo-installed-continuation",
                                    "glueyneo-installed-persistence"}):
            expanded[0] = str(PureWindowsPath(cwd) / executable.with_suffix(".exe"))
    if cmake_generator and expanded[0] == "cmake" and "-S" in expanded and "-B" in expanded:
        expanded[1:1] = ["-G", cmake_generator]
    if str(ROOT) in " ".join(expanded):
        raise CheckError("Guide command refers to the original source checkout")
    return expanded


def _raise_guide_launch_failure(command_index: int, executable_token: str, cwd: Path) -> None:
    executable = PureWindowsPath(executable_token)
    if executable.drive or executable.root or executable.is_absolute():
        try:
            relative = executable.relative_to(PureWindowsPath(cwd))
        except ValueError:
            relative_executable = "<absolute executable>"
            expected_path = None
            expected_type = "not-inspected"
            windows_exe_type = "not-inspected"
        else:
            relative_executable = relative.as_posix()
            expected_path = cwd.joinpath(*relative.parts)
            expected_type = (
                "file" if expected_path.is_file()
                else "directory" if expected_path.is_dir() else "missing"
            )
            windows_exe_type = (
                "file" if expected_path.suffix.lower() == ".exe" and expected_path.is_file()
                else "missing"
            )
    else:
        relative_executable = executable.as_posix().removeprefix("./")
        expected_path = cwd.joinpath(*executable.parts) if len(executable.parts) > 1 else None
        expected_type = (
            "file" if expected_path is not None and expected_path.is_file()
            else "directory" if expected_path is not None and expected_path.is_dir()
            else "missing" if expected_path is not None
            else "path-search"
        )
        windows_exe_type = "not-applicable"
        if expected_path is not None:
            windows_exe = (expected_path if expected_path.suffix.lower() == ".exe"
                           else expected_path.with_suffix(".exe"))
            windows_exe_type = (
                "file" if windows_exe.is_file()
                else "directory" if windows_exe.is_dir() else "missing"
            )
    raise CheckError(
        f"guide command {command_index}/14 could not start "
        f"{relative_executable}; cwd=guide-root; path={expected_type}; "
        f"windows-exe={windows_exe_type}"
    ) from None


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


GUIDE_CONSUMER_TARGETS = (
    "glueyneo-installed-sound",
    "glueyneo-installed-continuation",
    "glueyneo-installed-persistence",
)

GUIDE_CONSUMER_SOURCES = {
    "glueyneo-installed-sound": {
        "tests/consumers/sound_consumer.c",
        "tests/fixture/public_sound_guest.c",
    },
    "glueyneo-installed-continuation": {"examples/continuation.c"},
    "glueyneo-installed-persistence": {
        "examples/persistence.c",
        "examples/persistence_host.c",
        "tests/fixture/public_persistence_guest.c",
        "tests/fixture/public_sound_guest.c",
    },
}
GUIDE_SDK_HEADER_SOURCES = {
    name: paths - {"examples/persistence_host.c"}
    for name, paths in GUIDE_CONSUMER_SOURCES.items()
}


def _c_standard_options(fragment: str) -> list[str]:
    try:
        tokens = shlex.split(fragment, posix=True)
    except ValueError:
        raise CheckError("guide consumer Release compile flags are malformed") from None
    options: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index].casefold()
        if token in {"-std", "--std"}:
            index += 1
            if index < len(tokens):
                options.append("-std=" + tokens[index].casefold())
            else:
                options.append("-std=")
        elif token.startswith(("-std=", "--std=")):
            options.append("-std=" + token.split("=", 1)[1])
        elif token == "-ansi":
            options.append("-std=ansi")
        elif token.startswith("/std:"):
            options.append(token)
        elif token == "/std":
            options.append("/std=<separated-selector>")
        index += 1
    return options


def _validate_compile_metadata(
    source: Path, variant: str, metadata: list[str], include_paths: list[str] | None = None,
) -> None:
    if (not isinstance(metadata, list) or not metadata or
            any(type(value) is not str for value in metadata)):
        raise CheckError("guide consumer build did not expose compile policy metadata")
    rendered = "\n".join(metadata)
    normalized = rendered.replace("\\", "/").casefold()
    private_checkout = str(ROOT).replace("\\", "/").casefold()
    sdk_build = str(source / f"build/sdk-{variant}")
    if private_checkout in normalized or sdk_build.replace("\\", "/").casefold() in normalized:
        raise CheckError("guide consumer compile metadata refers to a source checkout or producer build")
    if include_paths is not None:
        if (not isinstance(include_paths, list) or not include_paths or
                any(type(value) is not str for value in include_paths)):
            raise CheckError("guide consumer target did not expose SDK include directories")
        install_include = str(source / f"build/install-{variant}" / "include")
        expected = install_include.replace("\\", "/").casefold()
        actual = {path.replace("\\", "/").casefold() for path in include_paths}
        if expected not in actual:
            raise CheckError("guide consumer target does not include the installed SDK headers")


def _path_is_within(root: PurePath, candidate: PurePath) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _visual_studio_release_c17(
    target_build_dir: Path, target_name: str, generator_platform: str,
) -> bool:
    project_path = target_build_dir / f"{target_name}.vcxproj"
    try:
        if not project_path.is_file() or project_path.stat().st_size > 1_048_576:
            return False
        project = ET.parse(project_path).getroot()
    except (ET.ParseError, OSError):
        return False

    namespace = "{http://schemas.microsoft.com/developer/msbuild/2003}"
    if project.tag != namespace + "Project":
        return False

    release_groups: list[tuple[str, str, ET.Element]] = []
    for group in list(project):
        standards = list(group.iter(namespace + "LanguageStandard_C"))
        if group.tag != namespace + "ItemDefinitionGroup":
            if standards:
                return False
            continue
        condition = group.get("Condition", "")
        match = re.fullmatch(
            r"'\$\(Configuration\)\|\$\(Platform\)'=='([^|' ]+)\|([^|' ]+)'",
            condition,
        )
        if match is None:
            # A broad, conditional, or unconditional C standard group might also
            # apply to Release, so it cannot establish the effective dialect.
            if standards:
                return False
            continue
        release_groups.append((match.group(1), match.group(2), group))

    if generator_platform:
        selected_platform = generator_platform
    else:
        platforms = {
            platform for configuration, platform, _ in release_groups
            if configuration == "Release"
        }
        if len(platforms) != 1:
            return False
        selected_platform = next(iter(platforms))

    selected_groups = [
        group for configuration, platform, group in release_groups
        if configuration == "Release" and platform == selected_platform
    ]
    if len(selected_groups) != 1:
        return False
    cl_compile = [child for child in list(selected_groups[0])
                  if child.tag == namespace + "ClCompile"]
    if (len(cl_compile) != 1 or
            any("Condition" in element.attrib for element in cl_compile)):
        return False
    properties = [
        prop for element in cl_compile for prop in list(element)
        if prop.tag == namespace + "LanguageStandard_C"
    ]
    all_properties = list(selected_groups[0].iter(namespace + "LanguageStandard_C"))
    if (len(all_properties) != len(properties) or
            any("Condition" in prop.attrib for prop in properties)):
        return False
    return len(properties) == 1 and (properties[0].text or "").strip() == "stdc17"


def _file_api_release_compile_metadata(source: Path, variant: str) -> dict[str, list[str]]:
    build_dir = source / f"build/examples-{variant}"
    reply_dir = build_dir / ".cmake" / "api" / "v1" / "reply"
    indexes = sorted(reply_dir.glob("index-*.json"))
    if not indexes:
        raise CheckError("guide consumer build did not produce CMake File API metadata")
    try:
        index = json.loads(indexes[-1].read_text(encoding="utf-8"))
        codemodel_entry = next(
            entry for entry in index["reply"].values() if entry.get("kind") == "codemodel"
        )
        codemodel = json.loads((reply_dir / codemodel_entry["jsonFile"]).read_text(encoding="utf-8"))
        staged_root = source.resolve(strict=True)
        expected_source_root = (staged_root / "tests" / "consumers").resolve(strict=True)
        reported_source_root = Path(codemodel["paths"]["source"]).resolve(strict=True)
        if reported_source_root != expected_source_root:
            raise CheckError("guide consumer codemodel is not rooted at the staged consumer source")
        reported_build_root = Path(codemodel["paths"]["build"]).resolve(strict=True)
        if reported_build_root != build_dir.resolve(strict=True):
            raise CheckError("guide consumer codemodel is not rooted at the configured build directory")
        generator = index["cmake"]["generator"]
        if (not isinstance(generator, dict) or type(generator.get("name")) is not str or
                type(generator.get("multiConfig")) is not bool):
            raise CheckError("guide consumer CMake File API generator metadata is malformed")
        generator_name = generator["name"]
        generator_platform = generator.get("platform", "")
        if type(generator_platform) is not str:
            raise CheckError("guide consumer CMake File API generator platform is malformed")
        visual_studio_generator = generator_name.startswith("Visual Studio ")
        configurations = codemodel["configurations"]
        release_configs = [config for config in configurations if config.get("name") == "Release"]
        if len(release_configs) != 1:
            raise CheckError("guide consumer CMake File API must contain exactly one Release configuration")
        target_metadata: dict[str, list[str]] = {}
        for target_ref in release_configs[0]["targets"]:
            name = target_ref.get("name")
            if name not in GUIDE_CONSUMER_TARGETS:
                continue
            if name in target_metadata:
                raise CheckError("guide consumer CMake File API contains a duplicate Release target")
            target = json.loads((reply_dir / target_ref["jsonFile"]).read_text(encoding="utf-8"))
            if (target.get("name") != name or type(target_ref.get("id")) is not str or
                    target.get("id") != target_ref["id"]):
                raise CheckError("guide consumer CMake File API target identity is inconsistent")
            target_paths = target.get("paths")
            if not isinstance(target_paths, dict) or type(target_paths.get("build")) is not str:
                raise CheckError("guide consumer CMake File API target build path is malformed")
            target_build_dir = Path(target_paths["build"])
            if not target_build_dir.is_absolute():
                target_build_dir = build_dir / target_build_dir
            try:
                resolved_target_build_dir = target_build_dir.resolve(strict=True)
            except OSError:
                raise CheckError("guide consumer CMake File API target build path is missing") from None
            if not _path_is_within(build_dir.resolve(strict=True), resolved_target_build_dir):
                raise CheckError("guide consumer CMake File API target build path is outside its build")
            groups = target.get("compileGroups")
            if not isinstance(groups, list) or not groups:
                raise CheckError("guide consumer Release target has no compile groups")
            target_sources = target.get("sources")
            if not isinstance(target_sources, list) or not target_sources:
                raise CheckError("guide consumer Release target has no source-origin metadata")
            metadata: list[str] = []
            include_paths: list[str] = []
            observed_sources: set[str] = set()
            source_paths: list[str] = []
            for source_entry in target_sources:
                source_path = source_entry["path"]
                if type(source_path) is not str or not source_path:
                    raise CheckError("guide consumer Release target has malformed source-origin metadata")
                source_file = Path(source_path)
                if not source_file.is_absolute():
                    source_file = reported_source_root / source_file
                try:
                    resolved_source = source_file.resolve(strict=True)
                except OSError:
                    raise CheckError("guide consumer Release target source is missing or unreadable") from None
                if not _path_is_within(staged_root, resolved_source):
                    raise CheckError("guide consumer Release target source is outside the staged project")
                if not resolved_source.is_file():
                    raise CheckError("guide consumer Release target source is not a file")
                try:
                    relative_source = resolved_source.relative_to(staged_root).as_posix()
                except ValueError:
                    raise CheckError(
                        "guide consumer Release target source is outside the staged project"
                    ) from None
                observed_sources.add(relative_source)
                source_paths.append(relative_source)
                metadata.append(str(resolved_source))
            if observed_sources != GUIDE_CONSUMER_SOURCES[name]:
                raise CheckError(
                    "guide consumer Release target source is not in its documented consumer closure"
                )
            grouped_source_indexes: set[int] = set()
            for group in groups:
                if group.get("language") != "C":
                    raise CheckError("guide consumer Release target must compile as C")
                source_indexes = group.get("sourceIndexes")
                if (not isinstance(source_indexes, list) or not source_indexes or
                        any(type(index) is not int or index < 0 or index >= len(source_paths)
                            for index in source_indexes) or
                        len(set(source_indexes)) != len(source_indexes) or
                        grouped_source_indexes.intersection(source_indexes)):
                    raise CheckError("guide consumer Release compile group has malformed source bindings")
                grouped_source_indexes.update(source_indexes)
                language_standard = group.get("languageStandard")
                if not isinstance(language_standard, dict) or language_standard.get("standard") != "17":
                    raise CheckError("guide consumer Release target must use C17 compile settings")
                fragments = group.get("compileCommandFragments", [])
                if not isinstance(fragments, list):
                    raise CheckError("guide consumer Release compile flags are malformed")
                dialect_flags = []
                group_metadata = [str(staged_root / source_paths[index]) for index in source_indexes]
                group_include_paths: list[str] = []
                for fragment in fragments:
                    fragment_text = fragment["fragment"]
                    metadata.append(fragment_text)
                    group_metadata.append(fragment_text)
                    dialect_flags.extend(_c_standard_options(fragment_text))
                if dialect_flags:
                    has_strict_c17 = dialect_flags[-1] in {"-std=c17", "/std:c17"}
                else:
                    has_strict_c17 = (
                        visual_studio_generator and _visual_studio_release_c17(
                            resolved_target_build_dir, name, generator_platform,
                        )
                    )
                if not has_strict_c17:
                    evidence = (
                        "Visual Studio Release LanguageStandard_C=stdc17"
                        if visual_studio_generator and not dialect_flags
                        else "a strict C17 compiler flag"
                    )
                    raise CheckError(
                        f"guide consumer Release target {name} is missing {evidence}"
                    )
                includes = group.get("includes", [])
                if not isinstance(includes, list):
                    raise CheckError("guide consumer Release include directories are malformed")
                for include in includes:
                    include_path = include["path"]
                    include_paths.append(include_path)
                    group_include_paths.append(include_path)
                    metadata.append(include_path)
                    group_metadata.append(include_path)
                defines = group.get("defines", [])
                if not isinstance(defines, list):
                    raise CheckError("guide consumer Release compile definitions are malformed")
                for define in defines:
                    metadata.append(define["define"])
                    group_metadata.append(define["define"])
                if any(source_paths[index] in GUIDE_SDK_HEADER_SOURCES[name]
                       for index in source_indexes):
                    _validate_compile_metadata(
                        source, variant, group_metadata, group_include_paths,
                    )
            if grouped_source_indexes != set(range(len(source_paths))):
                raise CheckError("guide consumer Release compile groups omit target source files")
            _validate_compile_metadata(source, variant, metadata, include_paths)
            target_metadata[name] = metadata
    except (AttributeError, KeyError, TypeError, ValueError, OSError, StopIteration) as error:
        raise CheckError(
            "guide consumer CMake File API compile metadata is malformed "
            f"({type(error).__name__})"
        ) from None
    if set(target_metadata) != set(GUIDE_CONSUMER_TARGETS):
        raise CheckError("guide consumer Release codemodel omits an executed example target")
    return target_metadata


def _check_guide_compile_metadata(source: Path, variant: str) -> None:
    build_dir = source / f"build/examples-{variant}"
    compile_db = build_dir / "compile_commands.json"
    _file_api_release_compile_metadata(source, variant)
    if compile_db.is_file():
        try:
            rows = json.loads(compile_db.read_text(encoding="utf-8"))
            compile_db_metadata = [
                value for row in rows
                for value in (row.get("command", ""), row.get("directory", ""), row.get("file", ""))
            ]
        except (AttributeError, TypeError, ValueError, OSError) as error:
            raise CheckError("guide consumer compile database is malformed") from error
        _validate_compile_metadata(source, variant, compile_db_metadata)

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

    def test_windows_guide_executable_tokens_include_native_extension(self) -> None:
        source = Path("C:/guide")
        for variant in ("static", "shared"):
            marker = f"./build/examples-{variant}/glueyneo-installed-"
            executable_commands = [command for command in guide_commands(variant)
                                   if marker in command]
            self.assertEqual(len(executable_commands), 7)
            for command in executable_commands:
                with mock.patch.object(sys, "platform", "win32"):
                    argv = command_argv(command, source)
                documented = PureWindowsPath(shlex.split(command)[0]).with_suffix(".exe")
                expected = PureWindowsPath(source) / documented
                self.assertTrue(PureWindowsPath(argv[0]).is_absolute(), argv[0])
                self.assertEqual(PureWindowsPath(argv[0]), expected)
                self.assertEqual(PureWindowsPath(argv[0]).suffix, ".exe",
                                 f"Windows command must name its executable: {argv[0]}")

    def test_launch_failure_diagnostic_suppresses_absolute_paths(self) -> None:
        source = Path("C:/hosted/guide")
        windows_user_path = "\\".join((
            "C:", "Users", "synthetic-user", "AppData", "Local", "Temp", "missing.exe",
        ))
        posix_user_path = "/".join((
            "", "Users", "synthetic-user", "Library", "Caches", "missing.exe",
        ))
        private_paths = (
            windows_user_path,
            posix_user_path,
        )
        for private_path in private_paths:
            with self.subTest(path_kind="absolute executable"):
                try:
                    try:
                        raise FileNotFoundError(2, "missing executable", private_path)
                    except FileNotFoundError:
                        _raise_guide_launch_failure(7, private_path, source)
                except CheckError as error:
                    rendered = "".join(traceback.format_exception(error))
                self.assertIn("<absolute executable>", rendered)
                self.assertNotIn("synthetic-user", rendered)
                self.assertNotIn(private_path, rendered)
        guide_executable = PureWindowsPath(source) / "build" / "examples-static" / "missing.exe"
        try:
            _raise_guide_launch_failure(7, str(guide_executable), source)
        except CheckError as error:
            rendered = "".join(traceback.format_exception(error))
        self.assertIn("build/examples-static/missing.exe", rendered)
        self.assertNotIn(str(PureWindowsPath(source)), rendered)

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
            file_api_query = (
                source / f"build/examples-{variant}" / ".cmake" / "api" / "v1" / "query"
            )
            file_api_query.mkdir(parents=True)
            (file_api_query / "codemodel-v2").write_text("", encoding="utf-8")
            last_outputs: list[tuple[list[str], str]] = []
            persistence_executable: Path | None = None
            host_producer: dict[str, object] | None = None
            fixture: Path | None = None
            for command_index, command in enumerate(commands, start=1):
                argv = command_argv(command, source, cmake_generator=self.cmake_generator)
                if sys.platform == "win32" and "glueyneo-installed-" in argv[0]:
                    selected = PureWindowsPath(argv[0])
                    relative = selected.relative_to(PureWindowsPath(source))
                    selected_file = Path(argv[0])
                    expected_file = source.joinpath(*relative.parts)
                    self.assertEqual(selected_file, expected_file)
                    self.assertTrue(selected_file.is_file(),
                                    "Windows launch must select the built example executable")
                try:
                    result = run(argv, cwd=source, env=network_env,
                                 timeout=COMMAND_TIMEOUT_SECONDS)
                except FileNotFoundError:
                    _raise_guide_launch_failure(command_index, argv[0], source)
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
            _check_guide_compile_metadata(source, variant)
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
            configure_argv = shlex.split(next(
                command for command in commands
                if command.startswith("cmake -S tests/consumers -B build/examples-")
            ))
            build_argv = shlex.split(next(command for command in commands if command.startswith("cmake --build")))
            install_argv = shlex.split(next(command for command in commands if command.startswith("cmake --install")))
            self.assertIn("-DCMAKE_BUILD_TYPE=Release", configure_argv)
            self.assertIn("--config", build_argv)
            self.assertEqual(build_argv[build_argv.index("--config") + 1], "Release")
            self.assertIn("--config", install_argv)
            self.assertEqual(install_argv[install_argv.index("--config") + 1], "Release")

    def test_compile_metadata_requires_installed_include_and_rejects_build_paths(self) -> None:
        source = Path("/tmp/relocated-guide")
        installed_include = str(source / "build/install-static/include")
        _validate_compile_metadata(source, "static", ["/std:c17"], [installed_include])
        for invalid in (
            ([str(ROOT / "src" / "instance.c")], [installed_include]),
            ([str(source / "build/sdk-static/CMakeFiles/Glueyneo.dir")], [installed_include]),
            (["/std:c17"], ["/tmp/other/include"]),
        ):
            with self.subTest(metadata=invalid), self.assertRaises(CheckError):
                _validate_compile_metadata(source, "static", *invalid)

    def test_staged_source_path_boundary_preserves_posix_case(self) -> None:
        self.assertTrue(_path_is_within(
            PurePosixPath("/tmp/guide"), PurePosixPath("/tmp/guide/examples/continuation.c"),
        ))
        self.assertFalse(_path_is_within(
            PurePosixPath("/tmp/guide"), PurePosixPath("/tmp/GUIDE/private-source.c"),
        ))

    def test_release_compile_metadata_cannot_be_masked_by_debug_or_other_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guide-file-api-") as directory:
            source = Path(directory)
            reply = source / "build/examples-static/.cmake/api/v1/reply"
            reply.mkdir(parents=True)
            consumer_source_root = source / "tests/consumers"
            consumer_source_root.mkdir(parents=True)
            required_targets = (
                "glueyneo-installed-sound",
                "glueyneo-installed-continuation",
                "glueyneo-installed-persistence",
            )
            for relative in {
                *GUIDE_CONSUMER_SOURCES[required_targets[0]],
                *GUIDE_CONSUMER_SOURCES[required_targets[1]],
                *GUIDE_CONSUMER_SOURCES[required_targets[2]],
            }:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            installed_include = str(source / "build/install-static/include")

            def write_target(
                name: str,
                include: str,
                standard: str = "17",
                source_paths: list[str] | None = None,
                fragment: str = "/std:c17",
                compile_groups: list[dict[str, object]] | None = None,
            ) -> dict[str, str]:
                if source_paths is None:
                    source_paths = [str(source / relative) for relative in sorted(
                        GUIDE_CONSUMER_SOURCES.get(name, {"tests/consumers/sound_consumer.c"}),
                    )]
                if compile_groups is None:
                    compile_groups = [{
                        "language": "C",
                        "languageStandard": {"standard": standard},
                        "sourceIndexes": list(range(len(source_paths))),
                        "compileCommandFragments": [{"fragment": fragment}],
                        "includes": [{"path": include}],
                    }]
                json_file = f"target-{name}.json"
                (reply / json_file).write_text(json.dumps({
                    "id": f"{name}::consumer-target",
                    "name": name,
                    "paths": {"build": "."},
                    "sources": [{"path": source_path} for source_path in source_paths],
                    "compileGroups": compile_groups,
                }), encoding="utf-8")
                return {"id": f"{name}::consumer-target", "name": name, "jsonFile": json_file}

            def compile_group(
                source_indexes: list[int],
                include_paths: list[str],
                fragment: str = "/std:c17",
                standard: str = "17",
            ) -> dict[str, object]:
                return {
                    "language": "C",
                    "languageStandard": {"standard": standard},
                    "sourceIndexes": source_indexes,
                    "compileCommandFragments": [{"fragment": fragment}],
                    "includes": [{"path": path} for path in include_paths],
                }

            debug_refs = [write_target("debug-only-helper", installed_include)]
            release_refs = [write_target(name, installed_include) for name in required_targets]

            def write_codemodel(
                configurations: list[dict[str, object]],
                source_root: str = str(consumer_source_root),
                generator: dict[str, object] | None = None,
            ) -> None:
                (reply / "codemodel-v2.json").write_text(json.dumps({
                    "paths": {
                        "source": source_root,
                        "build": str(source / "build/examples-static"),
                    },
                    "configurations": configurations,
                }), encoding="utf-8")
                (reply / "index-test.json").write_text(json.dumps({
                    "cmake": {"generator": generator or {
                        "name": "Ninja", "multiConfig": False, "platform": "",
                    }},
                    "reply": {"codemodel": {
                        "kind": "codemodel", "jsonFile": "codemodel-v2.json",
                    }},
                }), encoding="utf-8")

            write_codemodel([
                {"name": "Debug", "targets": debug_refs},
                {"name": "Release", "targets": release_refs},
            ])
            _check_guide_compile_metadata(source, "static")

            write_target(required_targets[0], str(source / "build/sdk-static/include"))
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            for name in required_targets:
                write_target(name, str(source / "build/sdk-static/include"))
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            for name in required_targets:
                write_target(name, installed_include)
            write_target(required_targets[2], installed_include, standard="20")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_target(required_targets[2], installed_include, fragment="-std=gnu17")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_target(required_targets[2], installed_include,
                         fragment="-std=c17 -std=gnu17")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_target(required_targets[2], installed_include,
                         fragment='-std=c17 -std="gnu17"')
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_target(required_targets[2], installed_include,
                         fragment="-std=gnu17 -DFAKE=-std=c17")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            for fragment in (
                "-std=c17 --std=gnu17",
                "-std=c17 --std gnu17",
                "-std=c17 -ansi",
                "/std:c17 /std gnu17",
            ):
                with self.subTest(fragment=fragment):
                    write_target(required_targets[2], installed_include, fragment=fragment)
                    with self.assertRaises(CheckError):
                        _check_guide_compile_metadata(source, "static")

            write_target(required_targets[2], installed_include, fragment='--std "c17"')
            _check_guide_compile_metadata(source, "static")

            visual_studio_generator = {
                "name": "Visual Studio 18 2026",
                "multiConfig": True,
                "platform": "x64",
            }

            def write_visual_studio_target(
                name: str,
                *,
                configuration: str = "Release",
                platform: str = "x64",
                standard: str = "stdc17",
            ) -> None:
                project = source / f"build/examples-static/{name}.vcxproj"
                project.parent.mkdir(parents=True, exist_ok=True)
                project.write_text(
                    "<Project xmlns=\"http://schemas.microsoft.com/developer/msbuild/2003\">"
                    "<ItemDefinitionGroup Condition=\"'$(Configuration)|$(Platform)'=="
                    f"'{configuration}|{platform}'\"><ClCompile><LanguageStandard_C>"
                    f"{standard}</LanguageStandard_C></ClCompile></ItemDefinitionGroup></Project>",
                    encoding="utf-8",
                )

            visual_studio_targets = [
                write_target(name, installed_include, fragment="")
                for name in required_targets
            ]
            release_configuration = {"name": "Release", "targets": visual_studio_targets}
            write_codemodel([release_configuration], generator=visual_studio_generator)
            for name in required_targets:
                write_visual_studio_target(name)
            _check_guide_compile_metadata(source, "static")

            persistence_project = (
                source / f"build/examples-static/{required_targets[2]}.vcxproj"
            )
            conditional_project = persistence_project.read_text(encoding="utf-8").replace(
                "<LanguageStandard_C>",
                '<LanguageStandard_C Condition="false">',
            )
            persistence_project.write_text(conditional_project, encoding="utf-8")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            conditional_project = persistence_project.read_text(encoding="utf-8").replace(
                "<ClCompile>", '<ClCompile Condition="false">',
            )
            persistence_project.write_text(conditional_project, encoding="utf-8")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            conditional_override = persistence_project.read_text(encoding="utf-8").replace(
                "</LanguageStandard_C>",
                "</LanguageStandard_C><LanguageStandard_C Condition=\"'$(Configuration)'=='Release'\">"
                "stdc11</LanguageStandard_C>",
            )
            persistence_project.write_text(conditional_override, encoding="utf-8")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            duplicate_compile = persistence_project.read_text(encoding="utf-8").replace(
                "</ItemDefinitionGroup>",
                "<ClCompile><WarningLevel>Level3</WarningLevel></ClCompile>"
                "</ItemDefinitionGroup>",
            )
            persistence_project.write_text(duplicate_compile, encoding="utf-8")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            duplicate_standard = persistence_project.read_text(encoding="utf-8").replace(
                "</LanguageStandard_C>",
                "</LanguageStandard_C><LanguageStandard_C>stdc17</LanguageStandard_C>",
            )
            persistence_project.write_text(duplicate_standard, encoding="utf-8")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            unconditional_override = persistence_project.read_text(encoding="utf-8").replace(
                "</Project>",
                "<ItemDefinitionGroup><ClCompile><LanguageStandard_C>stdc11</LanguageStandard_C>"
                "</ClCompile></ItemDefinitionGroup></Project>",
            )
            persistence_project.write_text(unconditional_override, encoding="utf-8")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            broad_condition = persistence_project.read_text(encoding="utf-8").replace(
                "</Project>",
                "<ItemDefinitionGroup Condition=\"'$(Configuration)'=='Release'\"><ClCompile>"
                "<LanguageStandard_C>stdc11</LanguageStandard_C></ClCompile>"
                "</ItemDefinitionGroup></Project>",
            )
            persistence_project.write_text(broad_condition, encoding="utf-8")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            other_platform = persistence_project.read_text(encoding="utf-8").replace(
                "</Project>",
                "<ItemDefinitionGroup Condition=\"'$(Configuration)|$(Platform)'=='Release|Win32'\">"
                "<ClCompile><LanguageStandard_C>stdc11</LanguageStandard_C></ClCompile>"
                "</ItemDefinitionGroup></Project>",
            )
            persistence_project.write_text(other_platform, encoding="utf-8")
            _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            wrong_namespace_project = persistence_project.read_text(encoding="utf-8").replace(
                "http://schemas.microsoft.com/developer/msbuild/2003", "urn:other-project",
            )
            persistence_project.write_text(wrong_namespace_project, encoding="utf-8")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])

            write_codemodel([release_configuration], generator={
                "name": "Ninja", "multiConfig": False, "platform": "",
            })
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_codemodel([release_configuration], generator=visual_studio_generator)

            write_visual_studio_target(required_targets[2], configuration="Debug")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2], platform="Win32")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            write_visual_studio_target(required_targets[2], standard="stdc11")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_visual_studio_target(required_targets[2])
            write_target(required_targets[2], installed_include, fragment="/std:gnu17")
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            persistence_sources = sorted(GUIDE_CONSUMER_SOURCES[required_targets[2]])
            persistence_indexes = {
                relative: index for index, relative in enumerate(persistence_sources)
            }
            sdk_indexes = [index for relative, index in persistence_indexes.items()
                           if relative in GUIDE_SDK_HEADER_SOURCES[required_targets[2]]]
            host_index = persistence_indexes["examples/persistence_host.c"]
            write_target(
                required_targets[2], installed_include,
                source_paths=[str(source / relative) for relative in persistence_sources],
                compile_groups=[
                    compile_group(sdk_indexes, [installed_include]),
                    compile_group([host_index], []),
                ],
            )
            _check_guide_compile_metadata(source, "static")

            write_target(
                required_targets[2], installed_include,
                source_paths=[str(source / relative) for relative in persistence_sources],
                compile_groups=[
                    compile_group(sdk_indexes[:-1], [installed_include]),
                    compile_group([sdk_indexes[-1]], []),
                    compile_group([host_index], []),
                ],
            )
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_target(
                required_targets[0], installed_include,
                source_paths=[str(ROOT / "tests/consumers/sound_consumer.c")],
            )
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            for name in required_targets:
                write_target(name, installed_include)
            producer_source = source / "src/instance.c"
            producer_source.parent.mkdir(parents=True, exist_ok=True)
            producer_source.write_text("int producer_source;\n", encoding="utf-8")
            write_target(
                required_targets[0], installed_include,
                source_paths=[str(producer_source),
                              str(source / "tests/fixture/public_sound_guest.c")],
            )
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            for name in required_targets:
                write_target(name, installed_include)
            write_codemodel([
                {"name": "Debug", "targets": debug_refs},
                {"name": "Release", "targets": release_refs},
            ], source_root=str(ROOT / "tests/consumers"))
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            release_refs.pop()
            write_codemodel([
                {"name": "Debug", "targets": debug_refs},
                {"name": "Release", "targets": release_refs},
            ])
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_codemodel([{"name": "Debug", "targets": debug_refs}])
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            write_codemodel([
                {"name": "Debug", "targets": debug_refs},
                {"name": "Release", "targets": [*release_refs, release_refs[0]]},
            ])
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

            release_refs = [write_target(name, installed_include) for name in required_targets]
            write_codemodel([
                {"name": "Debug", "targets": debug_refs},
                {"name": "Release", "targets": release_refs},
                {"name": "Release", "targets": release_refs},
            ])
            with self.assertRaises(CheckError):
                _check_guide_compile_metadata(source, "static")

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
