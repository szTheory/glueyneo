#!/usr/bin/env python3
"""Bounded source and compile-closure audit for the owned MC68000 experiment.

This checker is intentionally mechanical. It checks named source facts and known
fixture boundaries; it does not replace an independent code review.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = Path("experiments/owned_cpu/state-inventory.json")
RUNTIME_PATH = Path("experiments/owned_cpu/cpu.c")
HEADER_PATH = Path("experiments/owned_cpu/cpu.h")
FIXTURE_PATH = Path("tests/owned_cpu/isolation_fixture.h")
EXPECTED_COMPILED_SOURCES = {
    "experiments/owned_cpu/cpu.c",
    "third_party/unity/src/unity.c",
    "tests/owned_cpu/test_diagnostic.c",
    "tests/owned_cpu/test_semantics.c",
    "tests/owned_cpu/test_timing.c",
    "tests/owned_cpu/test_isolation.c",
    "tests/owned_cpu/test_cold.c",
    "tests/owned_cpu/test_faults.c",
    "tests/owned_cpu/test_state.c",
    "tests/cpu/guest_fixture.c",
}
HASHED_SOURCES = {
    "experiments/owned_cpu/CMakeLists.txt",
    "experiments/owned_cpu/cpu.c",
    "experiments/owned_cpu/cpu.h",
    "third_party/unity/src/unity.c",
    "third_party/unity/src/unity.h",
    "third_party/unity/src/unity_internals.h",
    "tests/owned_cpu/isolation_fixture.h",
    "tests/owned_cpu/test_diagnostic.c",
    "tests/owned_cpu/test_semantics.c",
    "tests/owned_cpu/test_timing.c",
    "tests/owned_cpu/test_isolation.c",
    "tests/owned_cpu/test_cold.c",
    "tests/owned_cpu/test_faults.c",
    "tests/owned_cpu/test_state.c",
    "tests/owned_cpu/cold.py",
    "tests/owned_cpu/negative.py",
    "tests/owned_cpu/test_inventory.py",
    "tests/cpu/guest_fixture.c",
    "tests/cpu/guest_fixture.h",
    "tools/owned_cpu/inventory.py",
}
EXECUTABLE_TARGETS = {
    "owned_cpu_diagnostic",
    "owned_cpu_semantics",
    "owned_cpu_timing",
    "owned_cpu_isolation",
    "owned_cpu_cold",
    "owned_cpu_faults",
    "owned_cpu_state",
}
MANIFEST_PATH = Path("experiments/owned_cpu/source-manifest.json")


def closure_paths(root: Path) -> set[str]:
    """Source distribution scope; derived receipts are deliberately excluded."""
    paths = {"CMakeLists.txt", "LICENSE", "third_party/unity/LICENSE.txt",
             "third_party/unity/PROVENANCE.md", "tests/cpu/guest_fixture.c",
             "tests/cpu/guest_fixture.h", "tests/cpu/ORACLE.md"}
    if (root / "CMakePresets.json").is_file():
        paths.add("CMakePresets.json")
    for directory in ("experiments/owned_cpu", "tests/owned_cpu", "tools/owned_cpu",
                      "third_party/unity/src"):
        for path in (root / directory).iterdir():
            if path.is_file() and path.suffix in (".c", ".h", ".py", ".md", ".txt", ".json"):
                if path.name not in ("source-manifest.json", "acceptance-results.json", "budget-ledger.json", "REVIEW.md"):
                    paths.add(path.relative_to(root).as_posix())
    return paths


def make_manifest(root: Path) -> dict[str, Any]:
    files = []
    for name in sorted(closure_paths(root)):
        copied = name.startswith("third_party/unity/")
        files.append({"path": name, "sha256": sha256(root / name),
                      "origin": "copied" if copied else "authored",
                      "source": "Unity b6763fbd9cedfacaa89e2ad9fd00d615a234e355" if copied else "Glueyneo original; exact bytes identified by SHA-256",
                      "license": "MIT", "notice": "third_party/unity/LICENSE.txt" if copied else "LICENSE",
                      "update_owner": "Glueyneo maintainers; audit upstream pin changes" if copied else "Glueyneo maintainers",
                      "compiled": name in EXPECTED_COMPILED_SOURCES,
                      "distributed": True,
                      "host_calls": "explicit allocator/bus callbacks and C memory functions only" if name == RUNTIME_PATH.as_posix() else "host-side build/test/evidence only; not runtime"})
    return {"schema": 1, "files": files, "generated_runtime": [],
            "runtime_archive_sources": [RUNTIME_PATH.as_posix()],
            "compiled_sources": sorted(EXPECTED_COMPILED_SOURCES),
            "oracle": "tests/owned_cpu/ORACLE.md; tests/cpu/ORACLE.md; manuals primary, emulator agreement is not hardware truth",
            "fixture": {"recipe": "tests/cpu/guest_fixture.c", "sha256": sha256(root / "tests/cpu/guest_fixture.c"),
                        "outputs": {"scenario_a": "0000000a", "scenario_b": "00000010"},
                        "output_sha256": {"scenario_a": hashlib.sha256(bytes.fromhex("0000000a")).hexdigest(),
                                          "scenario_b": hashlib.sha256(bytes.fromhex("00000010")).hexdigest()}}}


def manifest_errors(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors = []
    if manifest.get("schema") != 1:
        errors.append("invalid source manifest schema")
    rows = manifest.get("files", [])
    names = [row.get("path", "") for row in rows]
    if len(names) != len(set(names)):
        errors.append("duplicate source manifest record")
    expected = make_manifest(root)
    wanted = {row["path"]: row for row in expected["files"]}
    for name in sorted(set(wanted) - set(names)):
        errors.append(f"missing source manifest record: {name}")
    for row in rows:
        name = row.get("path", "")
        if name not in wanted:
            errors.append(f"forbidden source manifest record: {name}")
        elif row != wanted[name]:
            errors.append(f"stale source manifest record: {name}")
    for key in ("generated_runtime", "runtime_archive_sources", "compiled_sources", "oracle", "fixture"):
        if manifest.get(key) != expected[key]:
            errors.append(f"source manifest closure mismatch: {key}")
    pins = {
        "src/unity.c": "a6cc4b143075a03317d72c760b5ed67a4a12eeda1242f575464ad23f34042275",
        "src/unity.h": "b30ba4db1e0be1a1f6c862d359d73c91025a114977e41d3dad17103363804334",
        "src/unity_internals.h": "35bffad23ebc533977291e7a848c646027513572268fbfa9bd03d5ec21ee818a",
        "LICENSE.txt": "ec6cf55f05ba2aa538b9677b2481b9ac14a87c63594fce8a0677d4f71c583980"}
    for name, expected_hash in pins.items():
        if sha256(root / "third_party/unity" / name) != expected_hash:
            errors.append(f"Unity immutable pin mismatch: {name}")
    return errors


class InventoryError(Exception):
    """A stable named reason that can be checked without Python assertions."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_cpu_fields(source: str) -> dict[str, str]:
    match = re.search(r"struct\s+owned_cpu\s*\{(?P<body>.*?)\n\};", source, re.S)
    if match is None:
        raise InventoryError("owned_cpu struct not found")
    fields: dict[str, str] = {}
    declaration = re.compile(
        r"^\s*(?P<type>[A-Za-z_][A-Za-z_0-9]*(?:\s+\*+)?)[ \t]+"
        r"(?P<name>[A-Za-z_][A-Za-z_0-9]*)(?P<array>\s*\[[^]]+\])?\s*;\s*$"
    )
    for line in match.group("body").splitlines():
        item = declaration.match(line)
        if item is None:
            if line.strip():
                raise InventoryError(f"unparsed owned_cpu field declaration: {line.strip()}")
            continue
        name = item.group("name")
        fields[name] = " ".join(
            part for part in (item.group("type").strip(), name + (item.group("array") or ""))
            if part
        )
    return fields


def parse_state_record_fields(source: str) -> dict[str, str]:
    match = re.search(
        r"typedef\s+struct\s*\{(?P<body>[^{}]*)\}\s*owned_cpu_state\s*;",
        source,
        re.S,
    )
    if match is None:
        raise InventoryError("owned_cpu_state record not found")
    fields: dict[str, str] = {}
    declaration = re.compile(
        r"^\s*(?P<type>[A-Za-z_][A-Za-z_0-9]*(?:\s+\*+)?)[ \t]+"
        r"(?P<name>[A-Za-z_][A-Za-z_0-9]*)(?P<array>\s*\[[^]]+\])?\s*;\s*$"
    )
    for line in match.group("body").splitlines():
        item = declaration.match(line)
        if item is None:
            if line.strip():
                raise InventoryError(f"unparsed state record field declaration: {line.strip()}")
            continue
        name = item.group("name")
        fields[name] = " ".join(
            part for part in (item.group("type").strip(), name + (item.group("array") or ""))
            if part
        )
    return fields


def field_errors(field_entries: list[dict[str, Any]], source: str) -> list[str]:
    actual = parse_cpu_fields(source)
    entries = {str(item.get("name", "")): item for item in field_entries}
    errors: list[str] = []
    for name in sorted(actual.keys() - entries.keys()):
        errors.append(f"missing field inventory entry: {name}")
    for name in sorted(entries.keys() - actual.keys()):
        errors.append(f"extra field inventory entry: {name}")
    for name in sorted(actual.keys() & entries.keys()):
        if entries[name].get("declaration") != actual[name]:
            errors.append(f"field declaration mismatch: {name}")
    return errors


def state_record_errors(root: Path, inventory: dict[str, Any]) -> list[str]:
    header = (root / HEADER_PATH).read_text(encoding="utf-8")
    runtime_hash = sha256(root / RUNTIME_PATH)
    errors: list[str] = []
    errors.extend(state_identity_errors(header, runtime_hash))

    record = inventory.get("private_state_record", {})
    try:
        actual = parse_state_record_fields(header)
    except InventoryError as error:
        return [str(error)]
    entries = {str(item.get("name", "")): item
               for item in record.get("record_fields", [])}
    if len(entries) != len(record.get("record_fields", [])):
        errors.append("duplicate private state inventory field")
    for name in sorted(actual.keys() - entries.keys()):
        errors.append(f"missing private state inventory entry: {name}")
    for name in sorted(entries.keys() - actual.keys()):
        errors.append(f"extra private state inventory entry: {name}")
    for name in sorted(actual.keys() & entries.keys()):
        if entries[name].get("declaration") != actual[name]:
            errors.append(f"private state field declaration mismatch: {name}")

    for entry in inventory.get("fields", []):
        name = str(entry.get("name", ""))
        disposition = str(entry.get("capture_disposition", "")).strip()
        if not disposition:
            errors.append(f"missing capture disposition: {name}")
        if entry.get("classification") == "host-binding" and "destination" not in disposition:
            errors.append(f"host binding does not name destination ownership: {name}")
    return errors


def state_identity_errors(header: str, runtime_hash: str) -> list[str]:
    if f'"{runtime_hash}"' not in header:
        return ["private state core identity is stale against cpu.c SHA-256"]
    return []


def mutable_file_scope_objects(source: str) -> list[str]:
    """Find conventional unindented C file-scope object declarations.

    This source-shape check is deliberately bounded; it is not a C parser.
    """
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    names: set[str] = set()
    storage = {"static", "extern", "register", "volatile", "restrict", "struct"}
    for line in stripped.splitlines():
        if not line or line[0].isspace() or line.startswith("#"):
            continue
        statement = line.strip()
        if not statement.endswith(";") or "(" in statement or ")" in statement:
            continue
        if statement.startswith("enum ") or statement.startswith("typedef "):
            continue
        if re.match(r"^(?:static\s+)?const\b", statement):
            continue
        statement = statement[:-1].split("=", 1)[0].split("[", 1)[0]
        identifiers = re.findall(r"[A-Za-z_]\w*", statement)
        identifiers = [name for name in identifiers if name not in storage]
        if len(identifiers) >= 2:
            names.add(identifiers[-1])
    return sorted(names)


def runtime_global_errors(source: str) -> list[str]:
    names = mutable_file_scope_objects(source)
    errors = [f"hidden mutable global state: {name}" for name in names]
    forbidden_calls = ("malloc", "calloc", "realloc", "free", "clock", "time",
                       "fopen", "socket", "pthread_create", "getenv", "system",
                       "dlopen", "printf")
    for name in forbidden_calls:
        if re.search(rf"\b{name}\s*\(", source):
            errors.append(f"direct host service call in runtime: {name}")
    return errors


def callback_owner_errors(source: str) -> list[str]:
    errors: list[str] = []
    callback_names = ("iso_read16", "iso_write16")
    assignment = re.compile(
        r"\b(?:machine|userdata)\s*->\s*(?:cpu|owner)\s*(?:=|\+\+|--|\+=|-=)"
    )
    for name in callback_names:
        header = re.search(rf"\b{name}\s*\([^)]*\)\s*\{{", source)
        if header is None:
            errors.append(f"missing ownership callback: {name}")
            continue
        depth = 1
        index = header.end()
        start = index
        while index < len(source) and depth != 0:
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
            index += 1
        body = source[start:index - 1]
        if assignment.search(body):
            errors.append(f"callback mutates owner binding: {name}")
    return errors


def hash_errors(root: Path, hashes: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for name in sorted(HASHED_SOURCES - hashes.keys()):
        errors.append(f"missing source hash: {name}")
    for name in sorted(hashes.keys() - HASHED_SOURCES):
        errors.append(f"extra source hash: {name}")
    for name in sorted(HASHED_SOURCES & hashes.keys()):
        path = root / name
        if not path.is_file():
            errors.append(f"missing source file: {name}")
        else:
            actual = sha256(path)
            if hashes[name] != actual:
                errors.append(f"stale source hash: {name}")
    return errors


def file_scope_errors(root: Path, entries: list[dict[str, str]]) -> list[str]:
    declared = {(entry.get("source", ""), entry.get("name", "")): entry
                for entry in entries}
    actual: set[tuple[str, str]] = set()
    for source in EXPECTED_COMPILED_SOURCES:
        for name in mutable_file_scope_objects((root / source).read_text(encoding="utf-8")):
            actual.add((source, name))
    errors: list[str] = []
    for source, name in sorted(actual - declared.keys()):
        prefix = "hidden mutable global state" if source == RUNTIME_PATH.as_posix() else "unlisted mutable file-scope object"
        errors.append(f"{prefix}: {source}:{name}")
    for source, name in sorted(declared.keys() - actual):
        errors.append(f"stale mutable file-scope inventory entry: {source}:{name}")
    return errors


def normalize_source(root: Path, source: str) -> str:
    path = Path(source)
    if not path.is_absolute():
        path = root / path
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise InventoryError(f"compiled source outside repository: {source}") from error


def load_cache(build_dir: Path) -> dict[str, str]:
    path = build_dir / "CMakeCache.txt"
    if not path.is_file():
        raise InventoryError(f"missing CMake cache: {build_dir}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("//") or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if ":" in key:
            values[key.split(":", 1)[0]] = value
    return values


def command_arguments(row: dict[str, Any]) -> list[str]:
    if isinstance(row.get("arguments"), list):
        return [str(value) for value in row["arguments"]]
    return shlex.split(str(row.get("command", "")))


def compile_errors(root: Path, build_dir: Path, expected: list[str]) -> list[str]:
    path = build_dir / "compile_commands.json"
    if not path.is_file():
        return [f"missing compile database: {build_dir}"]
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"invalid compile database: {error}"]
    errors: list[str] = []
    compiled: set[str] = set()
    cache = load_cache(build_dir)
    for row in rows:
        source = normalize_source(root, str(row.get("file", "")))
        compiled.add(source)
        args = command_arguments(row)
        command = " ".join(args)
        if "-std=c17" not in args:
            errors.append(f"compile command is not strict C17: {source}")
        sanitizer = cache.get("GLUEYNEO_OWNED_CPU_SANITIZER", "NONE")
        if sanitizer == "ADDRESS_UNDEFINED":
            if "-fsanitize=address,undefined" not in args:
                errors.append(f"ASan+UBSan missing from compile command: {source}")
            if "-fno-sanitize-recover=all" not in args:
                errors.append(f"nonrecovering ASan+UBSan missing: {source}")
        elif sanitizer == "THREAD" and "-fsanitize=thread" not in args:
            errors.append(f"ThreadSanitizer missing from compile command: {source}")
        optimization = cache.get("GLUEYNEO_OWNED_CPU_OPTIMIZATION", "NONE")
        required_optimization = "-O2" if optimization == "RELEASE" else "-O0"
        if required_optimization not in args:
            errors.append(f"owned optimization mode missing {required_optimization}: {source}")
        if "-fsanitize=" in command and sanitizer == "NONE":
            errors.append(f"unexpected sanitizer in NONE compile mode: {source}")
    expected_set = set(expected)
    for source in sorted(expected_set - compiled):
        errors.append(f"missing compiled source: {source}")
    for source in sorted(compiled - expected_set):
        errors.append(f"extra compiled source: {source}")

    ninja_path = shutil.which("ninja")
    if ninja_path is None or not (build_dir / "build.ninja").is_file():
        errors.append("runtime archive closure requires Ninja and build.ninja")
    else:
        archive = subprocess.run([ninja_path, "-C", str(build_dir), "-t", "commands", "owned_cpu"],
                                 text=True, capture_output=True, check=False)
        lines = [line for line in archive.stdout.splitlines() if " qc " in line and "libowned_cpu.a" in line]
        if archive.returncode != 0 or len(lines) != 1:
            errors.append("cannot inspect owned runtime archive closure")
        else:
            objects = re.findall(r"\S+\.o(?:\s|$)", lines[0])
            if len(objects) != 1 or "owned_cpu.dir/cpu.c.o" not in objects[0]:
                errors.append("forbidden object in owned runtime archive")

    sanitizer = cache.get("GLUEYNEO_OWNED_CPU_SANITIZER", "NONE")
    if sanitizer != "NONE":
        flag = "-fsanitize=address,undefined" if sanitizer == "ADDRESS_UNDEFINED" else "-fsanitize=thread"
        ninja_path = shutil.which("ninja")
        if ninja_path is None or not (build_dir / "build.ninja").is_file():
            errors.append("sanitizer link closure check requires Ninja and build.ninja")
        else:
            for target in sorted(EXECUTABLE_TARGETS):
                result = subprocess.run(
                    [ninja_path, "-C", str(build_dir), "-t", "commands", target],
                    text=True, capture_output=True, check=False,
                )
                if result.returncode != 0:
                    errors.append(f"cannot inspect sanitizer link command: {target}")
                    continue
                link_pattern = re.compile(
                    rf"-o\s+(?:[^\s]*/)?{re.escape(target)}(?:\s|$)"
                )
                links = [line for line in result.stdout.splitlines() if link_pattern.search(line)]
                if len(links) != 1:
                    errors.append(f"expected one final linker command for owned target: {target}")
                elif flag not in links[0]:
                    errors.append(f"sanitizer linker flag missing from owned target: {target}")
    return errors


def check_inventory(root: Path, build_dir: Path, inventory: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    runtime = (root / RUNTIME_PATH).read_text(encoding="utf-8")
    errors.extend(field_errors(inventory.get("fields", []), runtime))
    errors.extend(state_record_errors(root, inventory))
    errors.extend(runtime_global_errors(runtime))
    manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    errors.extend(manifest_errors(root, manifest))
    # Preserve the earlier state audit; the current distribution manifest owns
    # current hashes for files since changed by inventory/collector work.
    current = {row["path"]: row["sha256"] for row in manifest["files"]}
    errors.extend(hash_errors(root, {name: current.get(name, digest)
                                    for name, digest in inventory.get("source_hashes", {}).items()}))
    errors.extend(file_scope_errors(root, inventory.get("file_scope_objects", [])))
    errors.extend(compile_errors(root, build_dir, inventory.get("compiled_sources", [])))
    fixture = (root / FIXTURE_PATH).read_text(encoding="utf-8")
    errors.extend(callback_owner_errors(fixture))
    expected = sorted(EXPECTED_COMPILED_SOURCES)
    declared = sorted(inventory.get("compiled_sources", []))
    if declared != expected:
        for source in sorted(set(expected) - set(declared)):
            errors.append(f"missing inventory compile source: {source}")
        for source in sorted(set(declared) - set(expected)):
            errors.append(f"extra inventory compile source: {source}")
    return errors


def expect_named(errors: list[str], expected: str) -> None:
    if expected not in errors:
        raise InventoryError(f"self-test control missed named rejection: {expected}")


def run_self_test(root: Path, inventory: dict[str, Any]) -> int:
    runtime = (root / RUNTIME_PATH).read_text(encoding="utf-8")
    actual_fields = parse_cpu_fields(runtime)

    missing = copy.deepcopy(inventory["fields"])
    missing.pop()
    expect_named(field_errors(missing, runtime), "missing field inventory entry: reset_signal_events")

    extra = copy.deepcopy(inventory["fields"])
    extra.append({"name": "invented", "declaration": "uint32_t invented"})
    expect_named(field_errors(extra, runtime), "extra field inventory entry: invented")

    missing_state = copy.deepcopy(inventory)
    missing_state["private_state_record"]["record_fields"].pop()
    expect_named(state_record_errors(root, missing_state),
                 "missing private state inventory entry: reset_signal_events")

    current_header = (root / HEADER_PATH).read_text(encoding="utf-8")
    current_hash = sha256(root / RUNTIME_PATH)
    stale_core = current_header.replace(current_hash, "0" * 64, 1)
    if stale_core == current_header:
        raise InventoryError("self-test could not mutate private state core identity")
    expect_named(state_identity_errors(stale_core, current_hash),
                 "private state core identity is stale against cpu.c SHA-256")

    stale_hashes = dict(inventory["source_hashes"])
    stale_hashes["experiments/owned_cpu/cpu.c"] = "0" * 64
    expect_named(hash_errors(root, stale_hashes), "stale source hash: experiments/owned_cpu/cpu.c")

    injected_global = runtime + "\nstatic uint32_t hidden_cpu_state;\n"
    expect_named(runtime_global_errors(injected_global), "hidden mutable global state: hidden_cpu_state")

    fixture = (root / FIXTURE_PATH).read_text(encoding="utf-8")
    injected_callback = fixture.replace(
        "    iso_probe_reentry(machine);",
        "    machine->cpu = (owned_cpu *)0;\n    iso_probe_reentry(machine);",
        1,
    )
    expect_named(callback_owner_errors(injected_callback),
                 "callback mutates owner binding: iso_read16")

    if len(actual_fields) != len(inventory["fields"]):
        raise InventoryError("self-test baseline field inventory count differs")
    manifest = make_manifest(root)
    for kind in ("missing", "duplicate", "stale", "forbidden"):
        broken = copy.deepcopy(manifest)
        if kind == "missing":
            broken["files"].pop()
        elif kind == "duplicate":
            broken["files"].append(broken["files"][0])
        elif kind == "stale":
            broken["files"][0]["sha256"] = "0" * 64
        else:
            broken["files"].append({"path": "third_party/musashi/m68kcpu.c"})
        if not any(kind in error for error in manifest_errors(root, broken)):
            raise InventoryError(f"manifest control missed {kind}")
    print("PASS: missing/extra fields, stale hashes, hidden globals and callback-owner mutation rejected")
    return 0


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "self-test", "refresh-manifest"))
    parser.add_argument("--build-dir", type=Path, default=Path("build/owned-cpu"))
    options = parser.parse_args(arguments)
    try:
        if options.command == "refresh-manifest":
            (ROOT / MANIFEST_PATH).write_text(json.dumps(make_manifest(ROOT), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return 0
        inventory = json.loads((ROOT / INVENTORY_PATH).read_text(encoding="utf-8"))
        if options.command == "self-test":
            return run_self_test(ROOT, inventory)
        errors = check_inventory(ROOT, (ROOT / options.build_dir).resolve(), inventory)
        if errors:
            for reason in errors:
                print(f"FAIL: {reason}", file=sys.stderr)
            return 1
        print(f"PASS: {len(inventory['fields'])} owned fields; "
              f"{len(inventory['compiled_sources'])} compiled source files; "
              "runtime mutable globals=0; callback owner mutation=0")
        return 0
    except (OSError, json.JSONDecodeError, KeyError, InventoryError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
