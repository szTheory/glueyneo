#!/usr/bin/env python3
"""Collect exact host measurements for the fixed SDK diagnostic workload."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/sdk-release"
HELPER_SOURCE = r'''/* Generated from tools/sdk_baseline.py; local measurement helper only. */
#define _POSIX_C_SOURCE 200809L
#include "glueyneo/glueyneo.h"
#include "sdk_private.h"
#include "guest_fixture.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#define WARMUPS 3u
#define RETAINED 31u
#define EXECUTION_BATCH 32u

static uint64_t now_ns(void) {
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) return 0u;
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
}

static uint64_t duration_ns(uint64_t start, uint64_t end) {
    return end > start ? end - start : 0u;
}

static void make_manifest(guest_fixture_image *fixture, gn_manifest *manifest) {
    guest_fixture_build(fixture, GUEST_FIXTURE_SCENARIO_A);
    memset(manifest, 0, sizeof(*manifest));
    manifest->version = GN_MANIFEST_VERSION;
    manifest->profile = GN_PROFILE_DIAGNOSTIC;
    manifest->region_count = GN_MAX_REGIONS;
    manifest->regions[0] = (gn_region){0u, GUEST_FIXTURE_ROM_SIZE, fixture->rom,
        GUEST_FIXTURE_ROM_SIZE, GN_REGION_ROM};
    manifest->regions[1] = (gn_region){0x1000u, 4096u, fixture->ram_seed,
        GUEST_FIXTURE_RAM_INIT_SIZE, GN_REGION_RAM};
}

static int matching_output(gn_run_result *run, gn_observations *observed) {
    return observed->arithmetic_result == 10u &&
           observed->initialized_result == UINT32_C(0x1237) &&
           observed->bss_result == 1u && observed->ready == 1u &&
           run->requested_cycles == 172u && run->elapsed_cycles == 172u &&
           run->overshoot_cycles == 0u && run->instructions == 12u &&
           run->boundary_pc == UINT32_C(0x12e) && run->reason == GN_RUN_STOPPED;
}

static int load_sample(uint64_t *average_ns, uint64_t *batch_ns,
                       size_t *allocations, size_t *bytes, size_t *attempts,
                       gn_observations *output_observations,
                       gn_run_result *output_run) {
    gn_test_allocator allocators[EXECUTION_BATCH];
    gn_instance *instances[EXECUTION_BATCH] = {NULL};
    gn_status statuses[EXECUTION_BATCH];
    guest_fixture_image fixture;
    gn_manifest manifest;
    make_manifest(&fixture, &manifest);
    size_t created = 0u;
    for (size_t i = 0u; i < EXECUTION_BATCH; ++i) {
        gn_test_allocator_init(&allocators[i]);
        if (gn_test_create(&allocators[i], &instances[i]) != GN_STATUS_OK ||
            instances[i] == NULL) {
            created = i + 1u;
            goto cleanup_failed;
        }
        created = i + 1u;
    }
    {
        const uint64_t start = now_ns();
        if (start == 0u) goto cleanup_failed;
        for (size_t i = 0u; i < EXECUTION_BATCH; ++i) {
            statuses[i] = gn_load(instances[i], &manifest);
        }
        const uint64_t end = now_ns();
        *batch_ns = duration_ns(start, end);
    }
    if (*batch_ns == 0u) goto cleanup_failed;
    *average_ns = *batch_ns / EXECUTION_BATCH;
    if (*average_ns == 0u) goto cleanup_failed;
    for (size_t i = 0u; i < EXECUTION_BATCH; ++i) {
        if (statuses[i] != GN_STATUS_OK || allocators[i].live_allocations == 0u ||
            allocators[i].live_bytes == 0u || allocators[i].total_attempts == 0u ||
            allocators[i].live_allocations != allocators[0].live_allocations ||
            allocators[i].live_bytes != allocators[0].live_bytes ||
            allocators[i].total_attempts != allocators[0].total_attempts) goto cleanup_failed;
    }
    {
        gn_observations observed;
        gn_run_result run;
        memset(&run, 0, sizeof(run));
        memset(&observed, 0, sizeof(observed));
        if (gn_run(instances[0], 172u, &run) != GN_STATUS_OK ||
            gn_observe(instances[0], &observed) != GN_STATUS_OK ||
            !matching_output(&run, &observed)) goto cleanup_failed;
        *allocations = allocators[0].live_allocations;
        *bytes = allocators[0].live_bytes;
        *attempts = allocators[0].total_attempts;
        *output_observations = observed;
        *output_run = run;
    }
    for (size_t i = 0u; i < EXECUTION_BATCH; ++i) {
        gn_destroy(instances[i]);
        if (allocators[i].live_allocations != 0u || allocators[i].live_bytes != 0u) return 0;
    }
    return 1;

cleanup_failed:
    for (size_t i = 0u; i < created; ++i) gn_destroy(instances[i]);
    return 0;
}

static int execution_sample(uint64_t *average_ns, uint64_t *batch_ns,
                            gn_observations *output_observations,
                            gn_run_result *output_run) {
    gn_test_allocator allocators[EXECUTION_BATCH];
    gn_instance *instances[EXECUTION_BATCH] = {NULL};
    gn_run_result runs[EXECUTION_BATCH];
    gn_status statuses[EXECUTION_BATCH];
    size_t before_allocations[EXECUTION_BATCH];
    size_t before_bytes[EXECUTION_BATCH];
    guest_fixture_image fixture;
    gn_manifest manifest;
    make_manifest(&fixture, &manifest);
    size_t created = 0u;
    for (size_t i = 0u; i < EXECUTION_BATCH; ++i) {
        gn_test_allocator_init(&allocators[i]);
        if (gn_test_create(&allocators[i], &instances[i]) != GN_STATUS_OK ||
            instances[i] == NULL || gn_load(instances[i], &manifest) != GN_STATUS_OK) {
            created = i + 1u;
            goto cleanup_failed;
        }
        before_allocations[i] = allocators[i].live_allocations;
        before_bytes[i] = allocators[i].live_bytes;
        created = i + 1u;
    }
    {
        const uint64_t start = now_ns();
        if (start == 0u) goto cleanup_failed;
        for (size_t i = 0u; i < EXECUTION_BATCH; ++i) {
            statuses[i] = gn_run(instances[i], 172u, &runs[i]);
        }
        const uint64_t end = now_ns();
        *batch_ns = duration_ns(start, end);
    }
    if (*batch_ns == 0u) goto cleanup_failed;
    *average_ns = *batch_ns / EXECUTION_BATCH;
    if (*average_ns == 0u) goto cleanup_failed;
    for (size_t i = 0u; i < EXECUTION_BATCH; ++i) {
        gn_observations observed;
        memset(&observed, 0, sizeof(observed));
        if (statuses[i] != GN_STATUS_OK ||
            gn_observe(instances[i], &observed) != GN_STATUS_OK ||
            !matching_output(&runs[i], &observed) ||
            allocators[i].live_allocations != before_allocations[i] ||
            allocators[i].live_bytes != before_bytes[i]) goto cleanup_failed;
        *output_observations = observed;
        *output_run = runs[i];
    }
    for (size_t i = 0u; i < EXECUTION_BATCH; ++i) {
        gn_destroy(instances[i]);
        if (allocators[i].live_allocations != 0u || allocators[i].live_bytes != 0u) return 0;
    }
    return 1;

cleanup_failed:
    for (size_t i = 0u; i < created; ++i) {
        gn_destroy(instances[i]);
    }
    return 0;
}

static void print_values(const uint64_t *values, size_t count) {
    putchar('[');
    for (size_t i = 0u; i < count; ++i) {
        if (i != 0u) putchar(',');
        printf("%" PRIu64, values[i]);
    }
    putchar(']');
}

int main(void) {
    struct timespec resolution;
    if (clock_getres(CLOCK_MONOTONIC, &resolution) != 0 ||
        resolution.tv_sec < 0 || resolution.tv_nsec < 0) return 2;
    const uint64_t resolution_ns = (uint64_t)resolution.tv_sec * UINT64_C(1000000000) +
        (uint64_t)resolution.tv_nsec;
    if (resolution_ns == 0u) return 3;
    for (size_t i = 0u; i < WARMUPS; ++i) {
        uint64_t load = 0u, load_batch = 0u, execution = 0u, execution_batch = 0u;
        size_t allocations = 0u, bytes = 0u, attempts = 0u;
        gn_observations observed;
        gn_run_result run;
        if (!load_sample(&load, &load_batch, &allocations, &bytes,
                         &attempts, &observed, &run) ||
            !execution_sample(&execution, &execution_batch, &observed, &run)) return 4;
    }
    uint64_t loads[RETAINED] = {0u};
    uint64_t load_batches[RETAINED] = {0u};
    uint64_t executions[RETAINED] = {0u};
    uint64_t execution_batches[RETAINED] = {0u};
    size_t counts[RETAINED] = {0u};
    size_t byte_counts[RETAINED] = {0u};
    size_t attempts[RETAINED] = {0u};
    gn_observations observed;
    gn_run_result run;
    for (size_t i = 0u; i < RETAINED; ++i) {
        if (!load_sample(&loads[i], &load_batches[i],
                        &counts[i], &byte_counts[i], &attempts[i],
                        &observed, &run) ||
            !execution_sample(&executions[i], &execution_batches[i],
                              &observed, &run)) return 5;
        if (counts[i] == 0u || byte_counts[i] == 0u || attempts[i] == 0u) return 6;
    }
    printf("SDK_BASELINE_RAW {\"warmup_samples\":%u,\"retained_samples\":%u,"
           "\"load_runs_per_sample\":%u,\"execution_runs_per_sample\":%u,"
           "\"timer_resolution_ns\":%" PRIu64 ",\"load_ns\":",
           WARMUPS, RETAINED, EXECUTION_BATCH, EXECUTION_BATCH, resolution_ns);
    print_values(loads, RETAINED);
    printf(",\"load_batch_ns\":");
    print_values(load_batches, RETAINED);
    printf(",\"execution_ns\":");
    print_values(executions, RETAINED);
    printf(",\"execution_batch_ns\":");
    print_values(execution_batches, RETAINED);
    printf(",\"execution_runs_per_sample\":%u", EXECUTION_BATCH);
    printf(",\"memory_samples\":[");
    for (size_t i = 0u; i < RETAINED; ++i) {
        if (i != 0u) putchar(',');
        printf("{\"allocations\":%zu,\"bytes\":%zu,\"attempts\":%zu}",
               counts[i], byte_counts[i], attempts[i]);
    }
    printf("],\"observed_output\":{\"arithmetic_result\":%" PRIu32
           ",\"initialized_result\":%" PRIu32 ",\"bss_result\":%" PRIu32
           ",\"ready\":%u,\"requested_cycles\":%" PRIu64
           ",\"elapsed_cycles\":%" PRIu64 ",\"overshoot_cycles\":%" PRIu64
           ",\"instructions\":%" PRIu64 ",\"terminal_pc\":%" PRIu32
           ",\"stop_reason\":%u}}\n",
           observed.arithmetic_result, observed.initialized_result, observed.bss_result,
           (unsigned)observed.ready, run.requested_cycles, run.elapsed_cycles,
           run.overshoot_cycles, run.instructions, run.boundary_pc, (unsigned)run.reason);
    return 0;
}
'''


def clean_environment() -> dict[str, str]:
    env = dict(os.environ)
    for name in ("CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "CMAKE_PREFIX_PATH",
                 "CMAKE_MODULE_PATH", "CMAKE_TOOLCHAIN_FILE", "CMAKE_PROJECT_INCLUDE",
                 "CMAKE_PROJECT_INCLUDE_BEFORE", "CMAKE_GENERATOR"):
        env.pop(name, None)
    return env


def run(argv: list[str], *, timeout: int = 600, cwd: Path = ROOT,
        check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, env=clean_environment(), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=timeout, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {Path(argv[0]).name}\n{result.stdout[-8000:]}")
    return result


def cmake_cache_value(name: str, *, empty_is_valid: bool = False) -> str:
    cache = BUILD / "CMakeCache.txt"
    match = re.search(rf"^{re.escape(name)}:[^=]*=(.*)$", cache.read_text(), re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Release CMake cache lacks {name}")
    value = match.group(1).strip()
    if not value and not empty_is_valid:
        raise RuntimeError(f"Release CMake cache has empty {name}")
    return value


def ensure_release_build() -> dict[str, str]:
    BUILD.mkdir(parents=True, exist_ok=True)
    configure = run(["cmake", "-S", ".", "-B", str(BUILD), "-G", "Ninja",
                     "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=ON",
                     "-DGLUEYNEO_BUILD_TESTS=ON", "-DGLUEYNEO_SDK_SANITIZER=NONE",
                     "-DGLUEYNEO_CPU_EXPERIMENT=OFF",
                     "-DGLUEYNEO_OWNED_CPU_EXPERIMENT=OFF"], timeout=180)
    build = run(["cmake", "--build", str(BUILD), "--parallel", "2"], timeout=300)
    return {"configure": configure.stdout, "build": build.stdout,
            "compiler": cmake_cache_value("CMAKE_C_COMPILER")}


def compile_helper(compiler_path: str) -> tuple[Path, str, str]:
    directory = BUILD / "verify-sdk"
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "sdk-baseline-probe.c"
    executable = directory / "sdk-baseline-probe"
    source.write_text(HELPER_SOURCE, encoding="utf-8")
    flags = shlex.split(cmake_cache_value("CMAKE_C_FLAGS", empty_is_valid=True)) + shlex.split(
        cmake_cache_value("CMAKE_C_FLAGS_RELEASE"))
    argv = [compiler_path, "-std=c17", *flags, "-Wall", "-Wextra", "-Wpedantic", "-Werror",
            "-DGLUEYNEO_SDK_TEST_HOOKS", "-Iinclude", "-Isrc", "-Itests/sdk",
            "-Iexperiments/owned_cpu", str(source), "tests/sdk/guest_fixture.c",
            str(BUILD / "libglueyneo_test.a"), "-o", str(executable)]
    result = run(argv, timeout=120)
    command = "cc -std=c17 " + " ".join(flags + ["-Wall -Wextra -Wpedantic -Werror"])
    return executable, result.stdout, command


def collect_raw() -> tuple[dict[str, Any], dict[str, Any], str, str]:
    build_outputs = ensure_release_build()
    compiler_path = build_outputs["compiler"]
    compiler_id = (BUILD / "CMakeFiles").glob("*/CMakeCCompiler.cmake")
    generated = sorted(compiler_id)
    if not generated:
        raise RuntimeError("Release CMake did not generate compiler identity metadata")
    metadata = generated[-1].read_text(encoding="utf-8", errors="replace")
    identity: dict[str, str] = {}
    for key in ("CMAKE_C_COMPILER_ID", "CMAKE_C_COMPILER_VERSION"):
        match = re.search(rf'^set\({key} "([^"]*)"\)$', metadata, re.MULTILINE)
        identity[key] = match.group(1) if match else "unknown"
    if identity["CMAKE_C_COMPILER_ID"] == "unknown" or identity["CMAKE_C_COMPILER_VERSION"] == "unknown":
        raise RuntimeError("Release compiler identity is unknown in generated CMake metadata")

    runner = BUILD / "glueyneo-diagnostic"
    for scenario, extra in (("a", []), ("b", ["--scenario-b"])):
        fixture = BUILD / f"diagnostic-original-{scenario}.bin"
        run([str(runner), "--write-fixture", str(fixture), *extra], timeout=20)
        result = run([str(runner), "--check-fixture", str(fixture), *extra], timeout=20)
        if "\"outcome\":\"pass\"" not in result.stdout:
            raise RuntimeError(f"Release runner did not verify original fixture {scenario}")

    helper, helper_build_log, compile_command = compile_helper(compiler_path)
    probe = run([str(helper)], timeout=120)
    matches = re.findall(r"(?m)^SDK_BASELINE_RAW (\{.*\})$", probe.stdout)
    if len(matches) != 1:
        raise RuntimeError("measurement helper returned no unique raw sample record")
    raw = json.loads(matches[0])
    raw["cold_build_ns"] = []
    cold_ids: list[str] = []
    cold_root = BUILD / "verify-sdk" / "cold-builds"
    cold_root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 4):
        started = time.perf_counter_ns()
        with tempfile.TemporaryDirectory(prefix=f"cold-{index}-", dir=cold_root) as temp_name:
            directory = Path(temp_name)
            cold_ids.append(f"cold-{index}")
            configure = run(["cmake", "-S", ".", "-B", str(directory), "-G", "Ninja",
                 "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=OFF",
                 "-DGLUEYNEO_BUILD_TESTS=OFF", "-DGLUEYNEO_SDK_SANITIZER=NONE",
                 "-DGLUEYNEO_CPU_EXPERIMENT=OFF", "-DGLUEYNEO_OWNED_CPU_EXPERIMENT=OFF"],
                timeout=180)
            build = run(["cmake", "--build", str(directory), "--parallel", "2"], timeout=300)
        elapsed = time.perf_counter_ns() - started
        if elapsed <= 0:
            raise RuntimeError("cold build wall-time sample was not positive")
        raw["cold_build_ns"].append(elapsed)
        (cold_root / f"cold-{index}.log").write_text(
            "CONFIGURE\n" + configure.stdout + "BUILD\n" + build.stdout,
            encoding="utf-8")

    tool = {"source_sha256": hashlib.sha256(HELPER_SOURCE.encode()).hexdigest(),
            "binary_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
            "compiler": {"id": identity["CMAKE_C_COMPILER_ID"],
                         "version": identity["CMAKE_C_COMPILER_VERSION"],
                         "path_basename": Path(compiler_path).name}}
    raw["cold_build_ids"] = cold_ids
    raw["measurement_tool"] = tool
    raw["compile_command"] = compile_command
    raw["helper_build_log"] = helper_build_log
    raw["release_build_outputs"] = build_outputs
    return raw, tool, compile_command, probe.stdout


if __name__ == "__main__":
    collected, _, _, _ = collect_raw()
    print(json.dumps({"outcome": "pass", "retained_samples": collected["retained_samples"],
                      "cold_build_samples": len(collected["cold_build_ns"])}, sort_keys=True))
