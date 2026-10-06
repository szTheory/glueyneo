#!/usr/bin/env python3
"""Build and verify Glueyneo's offline installed package consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "build" / "consumers"
EXPECTED_FIXTURE_SHA256 = (
    "495eb195089d0ee7e73f4090514980b47a5fd4a55869d9e7f46376bce1646948"
)
MAX_WORKERS = 2
COMMAND_TIMEOUT_SECONDS = 300
FILTERED_ENVIRONMENT = {
    "CFLAGS",
    "CXXFLAGS",
    "CPPFLAGS",
    "LDFLAGS",
    "CMAKE_PREFIX_PATH",
    "CMAKE_MODULE_PATH",
    "CMAKE_TOOLCHAIN_FILE",
    "CMAKE_PROJECT_INCLUDE",
    "CMAKE_PROJECT_INCLUDE_BEFORE",
    "CMAKE_GENERATOR",
}


class CheckError(RuntimeError):
    def __init__(self, message: str, *, code: str = "check-failed") -> None:
        super().__init__(message)
        self.code = code


def clean_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if source is None else source)
    for name in FILTERED_ENVIRONMENT:
        env.pop(name, None)
    return env


def run(
    argv: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
    expected_returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=clean_environment(env),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        raise CheckError(
            f"Timed out after {timeout}s: {' '.join(argv)}\n{output[-12000:]}"
        ) from error
    if result.returncode != expected_returncode:
        raise CheckError(
            f"Command exited {result.returncode}, expected {expected_returncode}: {' '.join(argv)}\n"
            f"{result.stdout[-16000:]}"
        )
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_no_download_mechanisms() -> None:
    cmake_paths = [ROOT / "CMakeLists.txt"]
    cmake_dir = ROOT / "cmake"
    if cmake_dir.exists():
        cmake_paths.extend(sorted(cmake_dir.rglob("*.cmake")))
        cmake_paths.extend(sorted(cmake_dir.rglob("CMakeLists.txt")))
    forbidden = re.compile(
        r"FetchContent_Declare|ExternalProject_Add|CPMAddPackage|"
        r"file\s*\(\s*DOWNLOAD|conan_cmake|vcpkg_install|"
        r"COMMAND\s+(?:curl|wget)\b",
        re.IGNORECASE,
    )
    for path in cmake_paths:
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            raise CheckError(f"Configure-time dependency download mechanism in {path}")


def installed_layout(prefix: Path, variant: str) -> dict[str, Path]:
    configs = list(prefix.rglob("GlueyneoConfig.cmake"))
    if len(configs) != 1:
        raise CheckError(f"Expected one installed package config; found {configs}", code="missing-config")
    config_dir = configs[0].parent
    version_file = config_dir / "GlueyneoConfigVersion.cmake"
    targets_file = config_dir / "GlueyneoTargets.cmake"
    header = prefix / "include" / "glueyneo" / "glueyneo.h"
    license_file = prefix / "share" / "licenses" / "Glueyneo" / "LICENSE"
    fixture = prefix / "share" / "glueyneo" / "diagnostic-original-a.bin"
    runner_candidates = list((prefix / "bin").glob("glueyneo-diagnostic*"))
    for path in (version_file, targets_file, header, license_file, fixture):
        if not path.is_file():
            code = "missing-header" if path == header else "missing-fixture" if path == fixture else "missing-package-metadata"
            raise CheckError(f"Missing installed package artifact: {path.relative_to(prefix)}", code=code)
    if len(runner_candidates) != 1:
        raise CheckError(f"Expected one installed diagnostic runner; found {runner_candidates}")

    if variant == "static":
        names = {"libglueyneo.a", "glueyneo.lib"}
    else:
        names = {"libglueyneo.dylib", "libglueyneo.so", "glueyneo.dll"}
    libraries = [path for path in prefix.rglob("*") if path.is_file() and path.name in names]
    if len(libraries) != 1:
        raise CheckError(f"Expected one installed {variant} runtime; found {libraries}", code="missing-library")
    return {
        "config": configs[0],
        "version": version_file,
        "targets": targets_file,
        "header": header,
        "license": license_file,
        "fixture": fixture,
        "runner": runner_candidates[0],
        "library": libraries[0],
    }


def require_component(layout: dict[str, Path], component: str) -> None:
    path = layout.get(component)
    if path is None or not path.is_file():
        raise CheckError(
            f"Installed package is missing {component}: {path}",
            code=f"missing-{component}",
        )


def verify_fixture_digest(path: Path, expected: str = EXPECTED_FIXTURE_SHA256) -> None:
    observed = sha256(path)
    if observed != expected:
        raise CheckError(
            f"Fixture digest mismatch: expected {expected}, observed {observed}",
            code="fixture-digest-mismatch",
        )


def inspect_exports(
    prefix: Path,
    build_dir: Path,
    layout: dict[str, Path],
    variant: str,
    extra_forbidden: tuple[str, ...] = (),
) -> None:
    metadata_paths = sorted(layout["config"].parent.glob("*.cmake"))
    if not metadata_paths:
        raise CheckError("Installed package contains no CMake export metadata")
    metadata = "\n".join(path.read_text(encoding="utf-8") for path in metadata_paths)
    forbidden_text = (str(ROOT), str(build_dir), *extra_forbidden, "owned_cpu", "gn_test_", "unity")
    for forbidden in forbidden_text:
        if forbidden in metadata:
            raise CheckError(f"Private or absolute build detail leaked into package metadata: {forbidden}")
    targets = layout["targets"].read_text(encoding="utf-8")
    if "Glueyneo::glueyneo" not in targets and "glueyneo" not in targets:
        raise CheckError("Installed target export does not define Glueyneo::glueyneo")
    if "INTERFACE_INCLUDE_DIRECTORIES" not in targets or "_IMPORT_PREFIX" not in targets:
        raise CheckError("Installed include path is not expressed relative to the moved prefix")
    for forbidden in ("INTERFACE_COMPILE_OPTIONS", "third_party/unity", "experiments/owned_cpu"):
        if forbidden in targets:
            raise CheckError(f"Developer-only usage requirement leaked into export: {forbidden}")
    if variant == "shared" and "GLUEYNEO_SHARED" not in targets:
        raise CheckError("Shared package does not export the public DLL import definition")

    verify_fixture_digest(layout["fixture"])
    if sha256(layout["header"]) != sha256(ROOT / "include" / "glueyneo" / "glueyneo.h"):
        raise CheckError("Installed public header differs from the producer header")


EXPECTED_SHARED_EXPORTS = {
    "gn_create",
    "gn_load",
    "gn_reset",
    "gn_run",
    "gn_observe",
    "gn_unload",
    "gn_destroy",
    "gn_status_string",
}


def check_export_contract(names: set[str] | list[str]) -> list[str]:
    observed = set(names)
    public = {name for name in observed if name.startswith("gn_") and not name.startswith("gn_test_")}
    missing = EXPECTED_SHARED_EXPORTS - public
    extra = public - EXPECTED_SHARED_EXPORTS
    private = sorted(name for name in observed if name.startswith(("owned_cpu_", "gn_test_")))
    if missing or extra or private:
        raise CheckError(
            f"Shared export contract differs: missing={sorted(missing)}, "
            f"extra={sorted(extra)}, private={private}"
        )
    return sorted(public)


def parse_windows_exports(output: str) -> set[str]:
    if re.search(r"^\s*File Type:\s*DLL\s*$", output, re.IGNORECASE | re.MULTILINE) is None:
        raise CheckError("DUMPBIN output does not identify a DLL")
    lines = output.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines)
         if re.search(r"^\s*ordinal\s+hint\s+RVA\s+name\s*$", line, re.IGNORECASE)),
        None,
    )
    if header_index is None:
        raise CheckError("DUMPBIN output has no recognizable /EXPORTS table header")
    row = re.compile(
        r"^\s*[0-9]+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+([^\s=]+)(?:\s*=\s*\S.*)?\s*$"
    )
    names: set[str] = set()
    saw_row = False
    for line in lines[header_index + 1:]:
        if not line.strip():
            if saw_row:
                break
            continue
        match = row.fullmatch(line)
        if match is not None:
            name = match.group(1)
            if name in names:
                raise CheckError(f"DUMPBIN output repeats export name: {name}")
            names.add(name)
            saw_row = True
            continue
        if re.match(r"^\s*[0-9]+\s+", line):
            raise CheckError(f"DUMPBIN output contains an unparseable export row: {line.strip()}")
        if saw_row:
            break
    if not names:
        raise CheckError("DUMPBIN output contains no named DLL exports")
    # DUMPBIN /EXPORTS table: https://learn.microsoft.com/en-us/cpp/build/reference/dash-exports
    # x64 C-linkage exports have no __cdecl name decoration:
    # https://learn.microsoft.com/en-us/cpp/build/reference/decorated-names
    # Both Microsoft docs were checked 2026-10-06. Preserve names exactly here.
    return names


def export_inspector() -> tuple[str, str]:
    if sys.platform == "win32":
        name = "dumpbin"
    elif sys.platform == "darwin" or sys.platform.startswith("linux"):
        name = "nm"
    else:
        raise CheckError(f"Shared export inspection is not implemented for {sys.platform}")
    executable = shutil.which(name)
    if executable is None:
        raise CheckError(f"{name} is required to inspect the tested shared-library exports")
    return name, executable


def export_inspector_identity() -> dict[str, str]:
    name, executable = export_inspector()
    output = run([executable, "/?"] if name == "dumpbin" else [executable, "--version"]).stdout
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if name == "dumpbin" and re.search(r"Dumper Version\s+[0-9.]+", first_line, re.IGNORECASE) is None:
        raise CheckError("DUMPBIN /? returned an unsupported version identity")
    if name == "nm" and not re.search(r"\b(nm|llvm-nm|Apple LLVM)\b", first_line, re.IGNORECASE):
        raise CheckError("nm --version returned an unsupported tool identity")
    return {"name": name, "executable": Path(executable).name, "version": first_line}


def shared_exports(library: Path) -> list[str]:
    name, executable = export_inspector()
    if name == "dumpbin":
        output = run([executable, "/EXPORTS", str(library)]).stdout
        return check_export_contract(parse_windows_exports(output))
    if sys.platform == "darwin":
        output = run([executable, "-gU", str(library)]).stdout
    else:
        output = run([executable, "-D", "--defined-only", str(library)]).stdout
    names: list[str] = []
    for line in output.splitlines():
        fields = line.split()
        if fields:
            name = fields[-1].lstrip("_")
            if name.startswith("gn_") or name.startswith("owned_cpu_") or name.startswith("gn_test_"):
                names.append(name)
    return check_export_contract(names)


def compiler_identity(build_dir: Path) -> dict[str, str]:
    cache = (build_dir / "CMakeCache.txt").read_text(encoding="utf-8")
    compiler_files = sorted((build_dir / "CMakeFiles").glob("*/CMakeCCompiler.cmake"))
    if len(compiler_files) != 1:
        raise CheckError(f"Expected one generated C compiler identity file: {compiler_files}")
    compiler_data = compiler_files[0].read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for key in ("CMAKE_C_COMPILER", "CMAKE_BUILD_TYPE"):
        match = re.search(rf"^{re.escape(key)}(?::[^=]+)?=(.*)$", cache, re.MULTILINE)
        if match is None:
            raise CheckError(f"CMake cache is missing toolchain identity {key}")
        values[key] = match.group(1)
    for key in ("CMAKE_C_COMPILER_ID", "CMAKE_C_COMPILER_VERSION"):
        match = re.search(rf'set\({key} "([^"]*)"\)', compiler_data)
        if match is None:
            raise CheckError(f"Generated compiler metadata is missing {key}")
        values[key] = match.group(1)
    if "GLUEYNEO_INHERITED_" in cache:
        raise CheckError("Inherited compiler flags reached the fresh SDK build")
    return values


def consumer_compiler_identity(build_dir: Path) -> dict[str, str]:
    identity = compiler_identity(build_dir)
    cache = (build_dir / "CMakeCache.txt").read_text(encoding="utf-8")
    compiler_files = sorted((build_dir / "CMakeFiles").glob("*/CMakeCXXCompiler.cmake"))
    if len(compiler_files) != 1:
        raise CheckError(f"Expected one generated C++ compiler identity file: {compiler_files}")
    compiler_data = compiler_files[0].read_text(encoding="utf-8")
    for key in ("CMAKE_CXX_COMPILER",):
        match = re.search(rf"^{re.escape(key)}(?::[^=]+)?=(.*)$", cache, re.MULTILINE)
        if match is None:
            raise CheckError(f"CMake cache is missing toolchain identity {key}")
        identity[key] = match.group(1)
    for key in ("CMAKE_CXX_COMPILER_ID", "CMAKE_CXX_COMPILER_VERSION"):
        match = re.search(rf'set\({key} "([^"]*)"\)', compiler_data)
        if match is None:
            raise CheckError(f"Generated compiler metadata is missing {key}")
        identity[key] = match.group(1)
    return identity


def new_work_dir(label: str) -> Path:
    work_parent = Path(tempfile.gettempdir()) / "glueyneo-sdk-checks"
    work_parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{label}-", dir=work_parent))


def build_package(variant: str, work: Path) -> dict[str, object]:
    assert_no_download_mechanisms()
    build_dir = work / "producer"
    prefix = work / "install"
    inherited = dict(os.environ)
    inherited["CFLAGS"] = "-DGLUEYNEO_INHERITED_CFLAGS_SENTINEL=1"
    inherited["CXXFLAGS"] = "-DGLUEYNEO_INHERITED_CXXFLAGS_SENTINEL=1"
    shared = "ON" if variant == "shared" else "OFF"
    run(
        [
            shutil.which("cmake") or "cmake",
            "-S",
            str(ROOT),
            "-B",
            str(build_dir),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            "-DBUILD_TESTING=OFF",
            "-DGLUEYNEO_BUILD_TESTS=OFF",
            "-DGLUEYNEO_CPU_EXPERIMENT=OFF",
            "-DGLUEYNEO_OWNED_CPU_EXPERIMENT=OFF",
            f"-DBUILD_SHARED_LIBS={shared}",
            f"-DCMAKE_INSTALL_PREFIX={prefix}",
        ],
        env=inherited,
    )
    run(
        [shutil.which("cmake") or "cmake", "--build", str(build_dir), "--parallel", str(MAX_WORKERS)],
        env=inherited,
    )
    run([shutil.which("cmake") or "cmake", "--install", str(build_dir)], env=inherited)
    identity = compiler_identity(build_dir)
    layout = installed_layout(prefix, variant)
    inspect_exports(prefix, build_dir, layout, variant)
    exports = shared_exports(layout["library"]) if variant == "shared" else []
    export_tool = export_inspector_identity() if variant == "shared" else None

    generated = work / "installed-runner-fixture.bin"
    clean = clean_environment(inherited)
    for name in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        clean.pop(name, None)
    run([str(layout["runner"]), "--write-fixture", str(generated)], env=clean)
    if sha256(generated) != EXPECTED_FIXTURE_SHA256:
        raise CheckError("Installed runner did not reproduce the original diagnostic fixture")

    return {
        "work": work,
        "build_dir": build_dir,
        "prefix": prefix,
        "layout": layout,
        "identity": identity,
        "exports": exports,
        "export_inspector": export_tool,
    }


def case_build(variant: str) -> None:
    package = build_package(variant, new_work_dir(f"build-{variant}"))
    layout = package["layout"]
    result = {
        "schema_version": 1,
        "case_id": f"sdk.package.build-{variant}",
        "outcome": "pass",
        "assertions": 8 if variant == "shared" else 7,
        "variant": variant,
        "host": f"{platform.system()} {platform.machine()}",
        "compiler": package["identity"],
        "cmake": run([shutil.which("cmake") or "cmake", "--version"]).stdout.splitlines()[0],
        "project_version": "0.1.0",
        "configuration": "Release",
        "library_sha256": sha256(layout["library"]),
        "header_sha256": sha256(layout["header"]),
        "fixture_sha256": sha256(layout["fixture"]),
        "shared_public_exports": package["exports"],
        "shared_export_inspector": package["export_inspector"],
        "offline_configure": "pass; no fetch/download hooks; tests disabled; vendored dependencies not required",
        "install_prefix_relocation_ready": "pass; metadata contains no source/build path",
        "inherited_flags": "pass; controlled CFLAGS/CXXFLAGS sentinels were stripped",
    }
    print("SDK_PACKAGE " + json.dumps(result, sort_keys=True))


def stage_consumer_project(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tests" / "consumers" / "CMakeLists.txt", destination / "CMakeLists.txt")
    shutil.copy2(ROOT / "tests" / "consumers" / "header.cpp", destination / "header.cpp")
    shutil.copy2(ROOT / "examples" / "diagnostic.c", destination / "diagnostic.c")


def parse_consumer_record(output: str, marker: str) -> dict[str, object]:
    records = [line[len(marker) :] for line in output.splitlines() if line.startswith(marker)]
    if len(records) != 1:
        raise CheckError(f"Expected one {marker.strip()} result record; got {len(records)}")
    result = json.loads(records[0])
    if result.get("outcome") != "pass":
        raise CheckError(f"Consumer reported failure: {result}")
    return result


def require_public_cli_output(output: str, local_paths: tuple[Path, ...]) -> None:
    if any(str(path) in output for path in local_paths if str(path)):
        raise CheckError("CLI output exposed a local filesystem path")
    host_path_patterns = (
        r"/(?:Users|home)/[^/\s\"]+",
        r"/(?:private/tmp|tmp|var/folders|private/var/folders)/[^/\s\"]+",
        r"[A-Za-z]:\\(?:Users\\|Temp\\)[^\s\"]+",
    )
    if any(re.search(pattern, output, re.IGNORECASE) for pattern in host_path_patterns):
        raise CheckError("CLI output exposed a host-user path")


def parse_diagnostic_record(output: str, local_paths: tuple[Path, ...]) -> dict[str, object]:
    require_public_cli_output(output, local_paths)
    marker = "SDK_DIAGNOSTIC "
    lines = [line[len(marker):] for line in output.splitlines() if line.startswith(marker)]
    if len(lines) != 1:
        raise CheckError(f"Expected one {marker.strip()} result record; got {len(lines)}")
    assertion_count = 0
    for line in output.splitlines():
        if not line:
            continue
        if line.startswith("# ASSERT "):
            if re.fullmatch(r"# ASSERT sdk\.[A-Za-z0-9_.-]+ expected=\d+ observed=\d+", line) is None:
                raise CheckError("Installed runner emitted an unclear assertion line")
            assertion_count += 1
        elif not line.startswith(marker):
            raise CheckError("Installed runner emitted unexpected user-facing output")
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise CheckError(f"Installed runner emitted malformed JSON: {error}") from error
    if not isinstance(result, dict):
        raise CheckError("Installed runner result must be a JSON object")

    expected = {
        "arithmetic": 10,
        "initialized": 0x1237,
        "bss": 1,
        "cycles": 172,
        "instructions": 12,
        "pc": 0x12E,
    }
    observed = result.get("observed")
    identity = result.get("identity")
    if (result.get("schema_version") != 1 or
            result.get("case_id") != "sdk.diagnostic.original-a" or
            result.get("outcome") != "pass" or
            not isinstance(result.get("assertions"), int) or
            result["assertions"] != assertion_count or assertion_count < 14 or
            set(result) != {"schema_version", "case_id", "outcome", "assertions",
                            "expected", "observed", "identity"} or
            result.get("expected") != expected or
            not isinstance(observed, dict) or
            set(observed) != {*expected, "reason"} or
            any(observed.get(name) != value for name, value in expected.items()) or
            observed.get("reason") != 1 or not isinstance(identity, dict) or
            set(identity) != {"source_revision", "configuration", "compiler"} or
            not all(
                isinstance(identity.get(name), str) and identity[name]
                for name in ("source_revision", "configuration", "compiler")
            ) or
            identity.get("configuration") != "Release" or
            (identity.get("source_revision") != "unknown" and
             re.fullmatch(r"[0-9a-f]{7,40}", identity["source_revision"]) is None) or
            any("/" in identity[name] or "\\" in identity[name]
                for name in ("source_revision", "configuration", "compiler"))):
        raise CheckError("Installed runner result omits named diagnostic, boundary, or build identity fields")
    return result


def check_ownership_error_guide() -> int:
    guide = (ROOT / "docs" / "ownership-and-errors.md").read_text(encoding="utf-8")
    required = (
        "`GN_STATUS_INVALID_MEDIA` | `invalid diagnostic media`",
        "`gn_status_string`",
        "failed replacements retain the previously loaded image",
        "These strings contain no host pointers or private paths.",
    )
    for phrase in required:
        if phrase not in guide:
            raise CheckError(f"Ownership and error guide is missing recovery contract: {phrase}")
    return len(required)


def run_with_loader_trace(
    executable: Path,
    args: list[str],
    layout: dict[str, Path],
    *,
    expected_returncode: int = 0,
) -> str:
    env = clean_environment()
    for name in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        env.pop(name, None)
    library = layout["library"].resolve()
    if sys.platform == "win32":
        # Windows searches the executable directory first, then PATH. The
        # consumer build directory does not contain Glueyneo.dll, so put only
        # the relocated package's runtime directory first in the search path.
        env["PATH"] = str(library.parent) + os.pathsep + env.get("PATH", "")
        return run(
            [str(executable), *args], env=env,
            expected_returncode=expected_returncode,
        ).stdout
    if sys.platform == "darwin":
        env["DYLD_PRINT_LIBRARIES"] = "1"
    elif sys.platform.startswith("linux"):
        env["LD_DEBUG"] = "libs"
    else:
        raise CheckError(f"Relocated shared loader identity is not implemented for {sys.platform}")
    output = run(
        [str(executable), *args], env=env,
        expected_returncode=expected_returncode,
    ).stdout
    # glibc's LD_DEBUG preserves a loader path such as bin/../lib. Inspect
    # successful initialization, rather than a candidate search, and compare
    # resolved paths so a relocatable $ORIGIN path keeps its actual identity.
    # https://man7.org/linux/man-pages/man8/ld.so.8.html (checked 2026-10-06)
    loaded = linux_trace_loaded_library(output, library) if sys.platform.startswith("linux") else str(library) in output
    if not loaded:
        raise CheckError(f"Loader trace did not resolve the shared runtime from the moved prefix: {library}")
    return output


def linux_trace_loaded_library(output: str, library: Path) -> bool:
    expected = library.resolve()
    for match in re.finditer(r"(?m)^\s*\d+:\s*calling init:\s*(.+?)\s*$", output):
        path = Path(match.group(1))
        if path.is_absolute() and path.resolve() == expected:
            return True
    return False


def expect_failure(code: str, action) -> None:
    try:
        action()
    except CheckError as error:
        if error.code != code:
            raise CheckError(
                f"Negative control expected {code}, but hit {error.code}: {error}"
            ) from error
        return
    raise CheckError(f"Negative control did not fail at expected check {code}")


def verify_missing_component_control(layout: dict[str, Path], component: str) -> None:
    path = layout[component]
    backup = path.with_name(path.name + ".negative-control")
    if backup.exists():
        raise CheckError(f"Stale negative-control backup exists: {backup}")
    path.rename(backup)
    try:
        expect_failure(f"missing-{component}", lambda: require_component(layout, component))
    finally:
        backup.rename(path)


def case_consumers(variant: str) -> None:
    work = new_work_dir(f"consumers-{variant}")
    package = build_package(variant, work)
    old_prefix = package["prefix"]
    relocated_prefix = work / "relocated" / "sdk-prefix"
    relocated_prefix.parent.mkdir(parents=True)
    shutil.move(str(old_prefix), str(relocated_prefix))
    if old_prefix.exists():
        raise CheckError("Original install prefix still exists after relocation")

    build_dir = package["build_dir"]
    layout = installed_layout(relocated_prefix, variant)
    inspect_exports(
        relocated_prefix,
        build_dir,
        layout,
        variant,
        extra_forbidden=(str(old_prefix),),
    )
    staged_source = work / "consumer-source"
    stage_consumer_project(staged_source)
    consumer_build = work / "consumer-build"
    cmake = shutil.which("cmake") or "cmake"
    ctest_identity = compiler_identity(build_dir)
    run(
        [
            cmake,
            "-S",
            str(staged_source),
            "-B",
            str(consumer_build),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            f"-DGlueyneo_DIR={layout['config'].parent}",
            "-DGLUEYNEO_CONSUMER_C_SOURCE=diagnostic.c",
        ]
    )
    run([cmake, "--build", str(consumer_build), "--parallel", str(MAX_WORKERS)])

    compile_commands_path = consumer_build / "compile_commands.json"
    compile_commands = json.loads(compile_commands_path.read_text(encoding="utf-8"))
    command_text = "\n".join(item.get("command", "") for item in compile_commands)
    compile_source_text = "\n".join(item.get("file", "") for item in compile_commands)
    cache = (consumer_build / "CMakeCache.txt").read_text(encoding="utf-8")
    for forbidden in (str(ROOT), str(build_dir), str(old_prefix), "experiments/owned_cpu", "third_party/unity"):
        if forbidden in command_text or forbidden in compile_source_text or forbidden in cache:
            raise CheckError(f"Out-of-tree consumer retained producer/private path: {forbidden}")
    if str(relocated_prefix) not in command_text:
        raise CheckError("Consumer compile commands do not use the moved installed header")
    if str(layout["config"].parent) not in cache:
        raise CheckError("Consumer did not resolve find_package from the moved Glueyneo_DIR")

    fixture = work / "moved-prefix-fixture.bin"
    runner_env = clean_environment()
    for name in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        runner_env.pop(name, None)
    if variant == "shared":
        runner_output = run_with_loader_trace(
            layout["runner"], ["--write-fixture", str(fixture)], layout
        )
    else:
        runner_output = run(
            [str(layout["runner"]), "--write-fixture", str(fixture)], env=runner_env
        ).stdout
    verify_fixture_digest(fixture)

    runner_diagnostic_output = run([str(layout["runner"])], env=runner_env).stdout
    runner_record = parse_diagnostic_record(
        runner_diagnostic_output,
        (ROOT, work, relocated_prefix, Path.home(), Path(tempfile.gettempdir())),
    )

    c_executable = consumer_build / "glueyneo-installed-c"
    cxx_executable = consumer_build / "glueyneo-installed-cxx"
    if sys.platform == "win32":
        c_executable = c_executable.with_suffix(".exe")
        cxx_executable = cxx_executable.with_suffix(".exe")
    if variant == "shared":
        c_output = run_with_loader_trace(c_executable, [str(fixture)], layout)
        cxx_output = run_with_loader_trace(cxx_executable, [], layout)
    else:
        c_output = run([str(c_executable), str(fixture)]).stdout
        cxx_output = run([str(cxx_executable)]).stdout
    c_record = parse_consumer_record(c_output, "SDK_CONSUMER ")
    cxx_record = parse_consumer_record(cxx_output, "SDK_CONSUMER_CPP ")

    wrong_expected_output = [str(c_executable), str(fixture), "--expect-arithmetic", "11"]
    if variant == "shared" and sys.platform == "win32":
        wrong_expected_env = clean_environment()
        wrong_expected_env["PATH"] = (
            str(layout["library"].resolve().parent)
            + os.pathsep
            + wrong_expected_env.get("PATH", "")
        )
        wrong_expected_stdout = run(
            wrong_expected_output, env=wrong_expected_env, expected_returncode=1
        ).stdout
    else:
        wrong_expected_stdout = run(
            wrong_expected_output, env=clean_environment(), expected_returncode=1
        ).stdout
    intended_failures = (
        "CONSUMER_ASSERT sdk.observe.arithmetic expected=11 observed=10",
        "CONSUMER_ASSERT sdk.reset-observe.arithmetic expected=11 observed=10",
    )
    if wrong_expected_stdout.count("CONSUMER_ASSERT") != len(intended_failures) or any(
        marker not in wrong_expected_stdout for marker in intended_failures
    ):
        raise CheckError("Wrong-output control failed for a reason other than the arithmetic result")
    require_public_cli_output(
        wrong_expected_stdout,
        (ROOT, work, relocated_prefix, Path.home(), Path(tempfile.gettempdir())),
    )

    control_results: list[str] = []
    for component in ("library", "config", "header"):
        verify_missing_component_control(layout, component)
        control_results.append(f"missing-{component}")
    expect_failure(
        "fixture-digest-mismatch",
        lambda: verify_fixture_digest(fixture, expected="0" * 64),
    )
    control_results.append("wrong-fixture-digest")
    control_results.append("wrong-expected-output")

    result = {
        "schema_version": 1,
        "case_id": f"sdk.package.consumers-{variant}",
        "outcome": "pass",
        "variant": variant,
        "host": f"{platform.system()} {platform.machine()}",
        "producer_compiler": ctest_identity,
        "consumer_compilers": consumer_compiler_identity(consumer_build),
        "cmake": run([cmake, "--version"]).stdout.splitlines()[0],
        "fixture_sha256": sha256(fixture),
        "relocation": "pass; installed runner and C/C++ consumers used moved prefix; no producer include/build paths",
        "loader_resolution": "moved prefix" if variant == "shared" else "static archive",
        "lanes": {"C": c_record, "C++": cxx_record},
        "runner_diagnostic": runner_record,
        "negative_controls": {"outcome": "pass", "checks": control_results},
        "assertions": (
            int(runner_record["assertions"])
            + int(c_record["assertions"])
            + int(cxx_record["assertions"])
            + len(control_results)
        ),
        "runner_fixture_output": runner_output.splitlines()[-1] if runner_output.splitlines() else "pass",
    }
    print("SDK_PACKAGE " + json.dumps(result, sort_keys=True))


def README_commands() -> list[str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start = "<!-- docs:installed-commands:start -->"
    end = "<!-- docs:installed-commands:end -->"
    if readme.count(start) != 1 or readme.count(end) != 1:
        raise CheckError("README must contain one marked installed-command block")
    section = readme.split(start, 1)[1].split(end, 1)[0]
    fenced = re.search(r"```sh\s*\n(.*?)\n```", section, re.DOTALL)
    if fenced is None:
        raise CheckError("README installed commands are not in one shell code block")
    commands: list[str] = []
    pending = ""
    for line in fenced.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1].rstrip() + " "
            continue
        commands.append(pending + line)
        pending = ""
    if pending:
        raise CheckError("README installed-command block ends with an incomplete continuation")
    return commands


def stage_documentation_project(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for file in ("CMakeLists.txt", "LICENSE", ".release-please-manifest.json"):
        shutil.copy2(ROOT / file, destination / file)
    for directory in ("cmake", "include", "src", "experiments/owned_cpu"):
        shutil.copytree(ROOT / directory, destination / directory)
    for relative in (
        "tools/diagnostic/main.c",
        "tests/sdk/guest_fixture.c",
        "tests/sdk/guest_fixture.h",
        "tests/consumers/CMakeLists.txt",
        "tests/consumers/header.cpp",
        "examples/diagnostic.c",
    ):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def command_argv(command: str, cwd: Path) -> list[str]:
    expanded = command.replace('"$PWD"', str(cwd)).replace("$PWD", str(cwd))
    return shlex.split(expanded)


def check_readme_links_and_contracts() -> int:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    local_links = 0
    for target in link_pattern.findall(readme):
        target = target.strip().split()[0]
        if target.startswith(("https://", "http://", "mailto:")) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        if path and not (ROOT / path).is_file() and not (ROOT / path).is_dir():
            raise CheckError(f"README link points to a missing local path: {target}")
        local_links += 1
    if local_links < 9:
        raise CheckError(f"README local-link verification found too few links: {local_links}")

    required_contracts = (
        "find_package(Glueyneo 0.1.0 EXACT CONFIG REQUIRED)",
        "callbacks receive the low 24 address bits",
        "GN_STATUS_INVALID_MEDIA",
        "invalid diagnostic media",
        "GN_RUN_STOPPED",
        "overshoot",
        "stopped-idle",
        "0x4AFC",
        "saved-PC behavior remains unknown",
        "phase_admitted: false",
        "WR-01",
        "without reading `0x106`",
        "do not qualify a platform support matrix",
    )
    for phrase in required_contracts:
        if phrase not in readme:
            raise CheckError(f"README is missing required current contract text: {phrase}")
    stale_phrases = (
        "There is no public SDK yet",
        "no public SDK qualification is established",
        "$gsd-execute-phase 01",
    )
    for phrase in stale_phrases:
        if phrase in readme:
            raise CheckError(f"README retains stale scope text: {phrase}")
    return local_links + len(required_contracts) + len(stale_phrases) + check_ownership_error_guide()


def check_capability_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    subset = (ROOT / "experiments" / "owned_cpu" / "SUBSET.md").read_text(encoding="utf-8")
    contract_rows = (
        ("MOVEQ #imm8,Dn", "MOVEQ #imm8,Dn"),
        ("ADDQ.L #1..8,Dn", "ADDQ.L #1..8,Dn"),
        ("MOVE.L Dn,(abs.L)", "MOVE.L Dn,(abs.L)"),
        ("NOP", "0x4e71"),
        ("RESET", "0x4e70"),
        ("RTE", "0x4e73"),
        ("TRAP #0", "0x4e40"),
        ("MOVE.W #imm16,SR", "0x46fc"),
        ("MOVE.W (abs.L),Dn", "MOVE.W (abs.L),Dn"),
        ("STOP #imm16", "0x4e72"),
    )
    for public_phrase, subset_phrase in contract_rows:
        if public_phrase not in readme or subset_phrase not in subset:
            raise CheckError(f"README and candidate subset disagree or omit {public_phrase}")
    exclusions = (
        "physical pin",
        "board behavior",
        "commercial game or BIOS compatibility",
        "video",
        "audio",
        "public\nsnapshots",
        "replay",
        "durable saves",
        "CPU plugins",
        "gameplay performance",
    )
    for phrase in exclusions:
        if phrase not in readme:
            raise CheckError(f"README omits a required excluded capability: {phrase}")
    if "phase_admitted: true" in readme or "original-silicon saved PC is known" in readme:
        raise CheckError("README overstates candidate admission or hardware saved-PC evidence")


def case_docs_readme() -> None:
    assertion_count = check_readme_links_and_contracts()
    commands = README_commands()
    if len(commands) != 16:
        raise CheckError(f"Expected 16 executable static/shared README commands; found {len(commands)}")
    print(
        "SDK_DOCS "
        + json.dumps(
            {
                "schema_version": 1,
                "case_id": "sdk.docs.readme-links-and-commands",
                "outcome": "pass",
                "assertions": assertion_count + 3 + len(commands),
                "commands_found": len(commands),
                "local_links": "pass",
            },
            sort_keys=True,
        )
    )


def case_capabilities() -> None:
    check_capability_contract()
    readme_assertions = check_readme_links_and_contracts()
    print(
        "SDK_CAPABILITIES "
        + json.dumps(
            {
                "schema_version": 1,
                "case_id": "sdk.capabilities.alpha-scope",
                "outcome": "pass",
                "assertions": 31 + readme_assertions,
                "scope": "bounded candidate and fixed diagnostic profile",
                "unknowns": ["original-silicon saved PC", "CMake 3.20 floor", "other platforms"],
            },
            sort_keys=True,
        )
    )


def case_docs_variant(variant: str) -> None:
    commands = README_commands()
    work = new_work_dir(f"docs-{variant}")
    source = work / "project"
    stage_documentation_project(source)
    selected: list[list[str]] = []
    tags = (f"sdk-{variant}", f"install-{variant}", f"consumer-{variant}")
    for command in commands:
        if any(tag in command for tag in tags):
            argv = command_argv(command, source)
            selected.append(argv)
    if len(selected) != 8:
        raise CheckError(f"Expected eight README commands for {variant}, found {len(selected)}")

    outcomes: list[dict[str, object]] = []
    for argv in selected:
        result = run(argv, cwd=source, timeout=COMMAND_TIMEOUT_SECONDS)
        if argv[0].startswith("./") and "glueyneo-installed-cxx" in argv[0]:
            outcomes.append(parse_consumer_record(result.stdout, "SDK_CONSUMER_CPP "))
        elif argv[0].startswith("./") and "glueyneo-installed-c" in argv[0]:
            require_public_cli_output(
                result.stdout,
                (ROOT, work, source, Path.home(), Path(tempfile.gettempdir())),
            )
            if "--recovery" in argv:
                recovery = parse_consumer_record(result.stdout, "SDK_RECOVERY ")
                if recovery.get("expected_status") != "invalid diagnostic media" or recovery.get(
                    "observed_status"
                ) != "invalid diagnostic media":
                    raise CheckError("README recovery command did not produce the documented invalid-media status")
                outcomes.append(recovery)
            outcomes.append(parse_consumer_record(result.stdout, "SDK_CONSUMER "))

    install_name = f"install-{variant}"
    fixture = source / "build" / install_name / "share" / "glueyneo" / "diagnostic-original-a.bin"
    verify_fixture_digest(fixture)

    if len(outcomes) != 4:
        raise CheckError(f"Expected C/C++ plus recovery outcomes for {variant}; found {len(outcomes)}")
    c_records = [record for record in outcomes if record.get("case_id") == "sdk.consumer.c"]
    cxx_records = [record for record in outcomes if record.get("case_id") == "sdk.consumer.cpp"]
    recovery_records = [record for record in outcomes if record.get("case_id") == "sdk.recovery.malformed-manifest"]
    if len(c_records) != 2 or len(cxx_records) != 1 or len(recovery_records) != 1:
        raise CheckError(f"README lane outcomes are incomplete for {variant}: {outcomes}")
    for c_record in c_records:
        if (c_record.get("arithmetic"), c_record.get("initialized"), c_record.get("bss")) != (10, 0x1237, 1):
            raise CheckError(f"README C example returned unexpected named results: {c_record}")
    print(
        "SDK_DOCS "
        + json.dumps(
            {
                "schema_version": 1,
                "case_id": f"sdk.docs.installed-example-{variant}",
                "outcome": "pass",
                "variant": variant,
                "assertions": sum(int(record.get("assertions", 0)) for record in outcomes),
                "compiled_commands_executed": len(selected),
                "c_lanes": len(c_records),
                "cpp_lanes": len(cxx_records),
                "malformed_manifest_recovery": "pass; GN_STATUS_INVALID_MEDIA then original loaded results pass",
            },
            sort_keys=True,
        )
    )


def suite(suite_name: str) -> None:
    labels = {
        "build": "sdk-package-build",
        "consumers": "sdk-package-consumers",
        "docs": "sdk-package-docs",
        "capabilities": "sdk-package-capabilities",
    }
    if suite_name not in labels:
        raise CheckError(f"Suite is not implemented yet: {suite_name}")
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    build_dir = BUILD_ROOT / "root-suite-build"
    cmake = shutil.which("cmake") or "cmake"
    ctest = shutil.which("ctest") or "ctest"
    run(
        [
            cmake,
            "-S",
            str(ROOT),
            "-B",
            str(build_dir),
            "-DCMAKE_BUILD_TYPE=Debug",
            "-DGLUEYNEO_BUILD_TESTS=ON",
            "-DBUILD_TESTING=ON",
            "-DGLUEYNEO_CPU_EXPERIMENT=OFF",
            "-DGLUEYNEO_OWNED_CPU_EXPERIMENT=OFF",
        ]
    )
    run([cmake, "--build", str(build_dir), "--parallel", str(MAX_WORKERS)])
    result = run(
        [
            ctest,
            "--test-dir",
            str(build_dir),
            "--verbose",
            "--output-on-failure",
            "--no-tests=error",
            "--parallel",
            str(MAX_WORKERS),
            "-L",
            labels[suite_name],
        ]
    )
    print(result.stdout, end="")
    print(
        "SDK_PACKAGE_SUITE "
        + json.dumps(
            {"schema_version": 1, "suite": suite_name, "outcome": "pass", "label": labels[suite_name]},
            sort_keys=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--suite", help="Configure/build and run one named CTest suite")
    choice.add_argument("--case", help="Run one CTest child case without suite dispatch")
    args = parser.parse_args()
    try:
        if args.suite:
            suite(args.suite)
        elif args.case in {"build-static", "build-shared"}:
            case_build(args.case.removeprefix("build-"))
        elif args.case in {"consumers-static", "consumers-shared"}:
            case_consumers(args.case.removeprefix("consumers-"))
        elif args.case in {"docs-static", "docs-shared"}:
            case_docs_variant(args.case.removeprefix("docs-"))
        elif args.case == "docs-readme":
            case_docs_readme()
        elif args.case == "capabilities":
            case_capabilities()
        else:
            raise CheckError(f"Unknown case: {args.case}")
    except (CheckError, OSError, ValueError) as error:
        print(f"SDK_PACKAGE {{\"schema_version\":1,\"outcome\":\"fail\",\"error\":{json.dumps(str(error))}}}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
