/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef GLUEYNEO_SOURCE_REVISION
#define GLUEYNEO_SOURCE_REVISION "unknown"
#endif
#ifndef GLUEYNEO_CONFIGURATION
#define GLUEYNEO_CONFIGURATION "unspecified"
#endif
#ifndef GLUEYNEO_COMPILER_ID
#define GLUEYNEO_COMPILER_ID "unknown"
#endif
#ifndef GLUEYNEO_COMPILER_VERSION
#define GLUEYNEO_COMPILER_VERSION "unknown"
#endif

static void build_guest(uint8_t rom[512], uint8_t ram_seed[10], unsigned scenario) {
    static const uint16_t words[] = {
        0x7007u, 0x5680u, 0x23c0u, 0x0000u, 0x1000u,
        0x7200u, 0x3239u, 0x0000u, 0x1008u, 0x5681u, 0x23c1u, 0x0000u, 0x1004u,
        0x7400u, 0x3439u, 0x0000u, 0x100au, 0x5282u, 0x23c2u, 0x0000u, 0x1010u,
        0x4e72u, 0x2700u
    };
    memset(rom, 0, 512u);
    memset(ram_seed, 0, 10u);
    rom[2] = 0x20u;
    rom[6] = 0x01u;
    for (size_t index = 0u; index < sizeof(words) / sizeof(words[0]); ++index) {
        const size_t offset = 0x100u + index * 2u;
        rom[offset] = (uint8_t)(words[index] >> 8);
        rom[offset + 1u] = (uint8_t)words[index];
    }
    ram_seed[8] = scenario == 0u ? 0x12u : 0x23u;
    ram_seed[9] = scenario == 0u ? 0x34u : 0x45u;
    if (scenario != 0u) {
        rom[0x101u] = 0x0bu;
        rom[0x102u] = 0x5au;
    }
}

static int run_scenario(unsigned scenario) {
    uint8_t rom[512];
    uint8_t ram_seed[10];
    build_guest(rom, ram_seed, scenario);
    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_DIAGNOSTIC;
    manifest.region_count = GN_MAX_REGIONS;
    manifest.regions[0] = (gn_region){0u, 512u, rom, sizeof(rom), GN_REGION_ROM};
    manifest.regions[1] =
        (gn_region){0x1000u, 4096u, ram_seed, sizeof(ram_seed), GN_REGION_RAM};

    gn_instance *instance = NULL;
    gn_status status = gn_create(&instance);
    if (status == GN_STATUS_OK) status = gn_load(instance, &manifest);
    memset(rom, 0xa5, sizeof(rom));
    memset(ram_seed, 0x5a, sizeof(ram_seed));

    gn_run_result run;
    memset(&run, 0, sizeof(run));
    if (status == GN_STATUS_OK) status = gn_run(instance, 172u, &run);
    gn_observations observations;
    memset(&observations, 0, sizeof(observations));
    if (status == GN_STATUS_OK) status = gn_observe(instance, &observations);

    const uint32_t expected_arithmetic = scenario == 0u ? 10u : 16u;
    const uint32_t expected_initialized = scenario == 0u ? 0x1237u : 0x2348u;
    const int passes = status == GN_STATUS_OK && run.reason == GN_RUN_STOPPED &&
                       run.requested_cycles == 172u && run.elapsed_cycles == 172u &&
                       run.overshoot_cycles == 0u && run.instructions == 12u &&
                       run.boundary_pc == 0x12eu && observations.ready == 1u &&
                       observations.arithmetic_result == expected_arithmetic &&
                       observations.initialized_result == expected_initialized &&
                       observations.bss_result == 1u;
    (void)printf(
        "SDK_DIAGNOSTIC {\"schema_version\":1,\"case_id\":\"sdk.diagnostic.original-%c\","
        "\"outcome\":\"%s\",\"assertions\":10,\"expected\":{"
        "\"arithmetic\":%" PRIu32 ",\"initialized\":%" PRIu32
        ",\"bss\":1,\"cycles\":172,\"instructions\":12,\"pc\":302},"
        "\"observed\":{\"arithmetic\":%" PRIu32 ",\"initialized\":%" PRIu32
        ",\"bss\":%" PRIu32 ",\"cycles\":%" PRIu64 ",\"instructions\":%" PRIu64
        ",\"pc\":%" PRIu32 ",\"reason\":%d},\"identity\":{"
        "\"source_revision\":\"%s\",\"configuration\":\"%s\","
        "\"compiler\":\"%s %s\"}}\n",
        scenario == 0u ? 'a' : 'b', passes ? "pass" : "fail", expected_arithmetic,
        expected_initialized, observations.arithmetic_result,
        observations.initialized_result, observations.bss_result, run.elapsed_cycles,
        run.instructions, run.boundary_pc, (int)run.reason, GLUEYNEO_SOURCE_REVISION,
        GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID, GLUEYNEO_COMPILER_VERSION);
    if (!passes) {
        (void)fprintf(stderr, "diagnostic failed: %s\n", gn_status_string(status));
    }
    gn_destroy(instance);
    return passes ? EXIT_SUCCESS : EXIT_FAILURE;
}

int main(int argc, char **argv) {
    unsigned scenario = 0u;
    if (argc == 2 && strcmp(argv[1], "--scenario-b") == 0) {
        scenario = 1u;
    } else if (argc != 1) {
        (void)fprintf(stderr, "usage: glueyneo-diagnostic [--scenario-b]\n");
        return EXIT_FAILURE;
    }
    return run_scenario(scenario);
}
