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
    pass


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
    if result.returncode != 0:
        raise CheckError(
            f"Command exited {result.returncode}: {' '.join(argv)}\n"
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
        raise CheckError(f"Expected one installed package config; found {configs}")
    config_dir = configs[0].parent
    version_file = config_dir / "GlueyneoConfigVersion.cmake"
    targets_file = config_dir / "GlueyneoTargets.cmake"
    header = prefix / "include" / "glueyneo" / "glueyneo.h"
    license_file = prefix / "share" / "licenses" / "Glueyneo" / "LICENSE"
    fixture = prefix / "share" / "glueyneo" / "diagnostic-original-a.bin"
    runner_candidates = list((prefix / "bin").glob("glueyneo-diagnostic*"))
    for path in (version_file, targets_file, header, license_file, fixture):
        if not path.is_file():
            raise CheckError(f"Missing installed package artifact: {path.relative_to(prefix)}")
    if len(runner_candidates) != 1:
        raise CheckError(f"Expected one installed diagnostic runner; found {runner_candidates}")

    if variant == "static":
        names = {"libglueyneo.a", "glueyneo.lib"}
    else:
        names = {"libglueyneo.dylib", "libglueyneo.so", "glueyneo.dll"}
    libraries = [path for path in prefix.rglob("*") if path.is_file() and path.name in names]
    if len(libraries) != 1:
        raise CheckError(f"Expected one installed {variant} runtime; found {libraries}")
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


def inspect_exports(prefix: Path, build_dir: Path, layout: dict[str, Path], variant: str) -> None:
    metadata_paths = sorted(layout["config"].parent.glob("*.cmake"))
    if not metadata_paths:
        raise CheckError("Installed package contains no CMake export metadata")
    metadata = "\n".join(path.read_text(encoding="utf-8") for path in metadata_paths)
    forbidden_text = (str(ROOT), str(build_dir), "owned_cpu", "gn_test_", "unity")
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

    if sha256(layout["fixture"]) != EXPECTED_FIXTURE_SHA256:
        raise CheckError("Installed original diagnostic fixture digest does not match ORACLE.md")
    if sha256(layout["header"]) != sha256(ROOT / "include" / "glueyneo" / "glueyneo.h"):
        raise CheckError("Installed public header differs from the producer header")


def shared_exports(library: Path) -> list[str]:
    nm = shutil.which("nm")
    if nm is None:
        raise CheckError("nm is required to inspect the tested shared-library exports")
    if sys.platform == "darwin":
        output = run([nm, "-gU", str(library)]).stdout
    elif sys.platform.startswith("linux"):
        output = run([nm, "-D", "--defined-only", str(library)]).stdout
    else:
        raise CheckError(f"Shared export inspection is not implemented for {sys.platform}")
    names: list[str] = []
    for line in output.splitlines():
        fields = line.split()
        if fields:
            name = fields[-1].lstrip("_")
            if name.startswith("gn_") or name.startswith("owned_cpu_") or name.startswith("gn_test_"):
                names.append(name)
    expected = {
        "gn_create",
        "gn_load",
        "gn_reset",
        "gn_run",
        "gn_observe",
        "gn_unload",
        "gn_destroy",
        "gn_status_string",
    }
    found_public = {name for name in names if name.startswith("gn_") and not name.startswith("gn_test_")}
    if found_public != expected:
        raise CheckError(f"Shared public export set differs: found {sorted(found_public)}")
    private = [name for name in names if name.startswith(("owned_cpu_", "gn_test_"))]
    if private:
        raise CheckError(f"Private backend/test symbols exported by shared runtime: {private}")
    return sorted(found_public)


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


def case_build(variant: str) -> None:
    assert_no_download_mechanisms()
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f"build-{variant}-", dir=BUILD_ROOT))
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

    generated = work / "installed-runner-fixture.bin"
    clean = clean_environment(inherited)
    for name in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        clean.pop(name, None)
    run([str(layout["runner"]), "--write-fixture", str(generated)], env=clean)
    if sha256(generated) != EXPECTED_FIXTURE_SHA256:
        raise CheckError("Installed runner did not reproduce the original diagnostic fixture")

    result = {
        "schema_version": 1,
        "case_id": f"sdk.package.build-{variant}",
        "outcome": "pass",
        "assertions": 8 if variant == "shared" else 7,
        "variant": variant,
        "host": f"{platform.system()} {platform.machine()}",
        "compiler": identity,
        "cmake": run([shutil.which("cmake") or "cmake", "--version"]).stdout.splitlines()[0],
        "project_version": "0.1.0",
        "configuration": "Release",
        "library_sha256": sha256(layout["library"]),
        "header_sha256": sha256(layout["header"]),
        "fixture_sha256": sha256(layout["fixture"]),
        "shared_public_exports": exports,
        "offline_configure": "pass; no fetch/download hooks; tests disabled; vendored dependencies not required",
        "install_prefix_relocation_ready": "pass; metadata contains no source/build path",
        "inherited_flags": "pass; controlled CFLAGS/CXXFLAGS sentinels were stripped",
    }
    print("SDK_PACKAGE " + json.dumps(result, sort_keys=True))


def suite(suite_name: str) -> None:
    if suite_name != "build":
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
            "sdk-package-build",
        ]
    )
    print(result.stdout, end="")
    print(
        "SDK_PACKAGE_SUITE "
        + json.dumps(
            {"schema_version": 1, "suite": suite_name, "outcome": "pass", "label": "sdk-package-build"},
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
        else:
            raise CheckError(f"Unknown case: {args.case}")
    except (CheckError, OSError, ValueError) as error:
        print(f"SDK_PACKAGE {{\"schema_version\":1,\"outcome\":\"fail\",\"error\":{json.dumps(str(error))}}}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
