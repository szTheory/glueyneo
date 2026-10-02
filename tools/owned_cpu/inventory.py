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
}


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
    errors.extend(runtime_global_errors(runtime))
    errors.extend(hash_errors(root, inventory.get("source_hashes", {})))
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
    print("PASS: missing/extra fields, stale hashes, hidden globals and callback-owner mutation rejected")
    return 0


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "self-test"))
    parser.add_argument("--build-dir", type=Path, default=Path("build/owned-cpu"))
    options = parser.parse_args(arguments)
    try:
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
