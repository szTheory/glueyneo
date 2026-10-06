/* SPDX-License-Identifier: MIT */
#include "unity.h"
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

static gn_instance *instance;
static uint64_t sdk_assertions;
static uint64_t sdk_cases;

#define SDK_CHECK_STATUS(id, expected, actual)                                     \
    do {                                                                           \
        const int sdk_expected_value = (int)(expected);                            \
        const int sdk_actual_value = (int)(actual);                                \
        ++sdk_assertions;                                                          \
        (void)printf("# ASSERT %s expected=%d observed=%d\n", (id),              \
                     sdk_expected_value, sdk_actual_value);                       \
        TEST_ASSERT_EQUAL_INT_MESSAGE(sdk_expected_value, sdk_actual_value, (id)); \
    } while (0)

#define SDK_CHECK_U64(id, expected, actual)                                          \
    do {                                                                             \
        const uint64_t sdk_expected_value = (uint64_t)(expected);                    \
        const uint64_t sdk_actual_value = (uint64_t)(actual);                        \
        ++sdk_assertions;                                                            \
        (void)printf("# ASSERT %s expected=%" PRIu64 " observed=%" PRIu64 "\n", \
                     (id), sdk_expected_value, sdk_actual_value);                    \
        TEST_ASSERT_EQUAL_UINT64_MESSAGE(sdk_expected_value, sdk_actual_value, (id));\
    } while (0)

#define SDK_CASE(id)             \
    do {                         \
        ++sdk_cases;             \
        (void)printf("# CASE %s\n", (id)); \
    } while (0)

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

static gn_status load_scenario(gn_instance *target, unsigned scenario) {
    uint8_t *rom = (uint8_t *)malloc(512u);
    uint8_t *ram_seed = (uint8_t *)malloc(10u);
    if (rom == NULL || ram_seed == NULL) {
        free(rom);
        free(ram_seed);
        return GN_STATUS_OUT_OF_MEMORY;
    }
    build_guest(rom, ram_seed, scenario);
    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_DIAGNOSTIC;
    manifest.region_count = GN_MAX_REGIONS;
    manifest.regions[0] = (gn_region){0u, 512u, rom, 512u, GN_REGION_ROM};
    manifest.regions[1] = (gn_region){0x1000u, 4096u, ram_seed, 10u, GN_REGION_RAM};
    const gn_status status = gn_load(target, &manifest);
    memset(rom, 0xa5, 512u);
    memset(ram_seed, 0x5a, 10u);
    free(rom);
    free(ram_seed);
    return status;
}

void setUp(void) {
    instance = NULL;
    SDK_CHECK_STATUS("sdk.instance.create", GN_STATUS_OK, gn_create(&instance));
    if (instance != NULL) {
        SDK_CHECK_STATUS("sdk.media.load.original-a", GN_STATUS_OK,
                         load_scenario(instance, 0u));
    }
}

void tearDown(void) {
    gn_destroy(instance);
    instance = NULL;
}

static void original_guest_computes_named_results(void) {
    SDK_CASE("sdk.diagnostic.original-a");
    gn_run_result run;
    memset(&run, 0xa5, sizeof(run));
    SDK_CHECK_STATUS("sdk.run.status", GN_STATUS_OK, gn_run(instance, 172u, &run));
    SDK_CHECK_U64("sdk.run.requested-cycles", 172u, run.requested_cycles);
    SDK_CHECK_U64("sdk.run.elapsed-cycles", 172u, run.elapsed_cycles);
    SDK_CHECK_U64("sdk.run.overshoot-cycles", 0u, run.overshoot_cycles);
    SDK_CHECK_U64("sdk.run.instructions", 12u, run.instructions);
    SDK_CHECK_STATUS("sdk.run.reason-stopped", GN_RUN_STOPPED, run.reason);
    SDK_CHECK_U64("sdk.run.boundary-pc", 0x12eu, run.boundary_pc);

    gn_observations observations;
    memset(&observations, 0xa5, sizeof(observations));
    SDK_CHECK_STATUS("sdk.observe.status", GN_STATUS_OK,
                     gn_observe(instance, &observations));
    SDK_CHECK_U64("sdk.observe.arithmetic", 10u, observations.arithmetic_result);
    SDK_CHECK_U64("sdk.observe.initialized", 0x1237u, observations.initialized_result);
    SDK_CHECK_U64("sdk.observe.bss", 1u, observations.bss_result);
    SDK_CHECK_U64("sdk.observe.ready", 1u, observations.ready);
}

static void failed_replacement_and_reset_preserve_owned_media(void) {
    SDK_CASE("sdk.media.failed-replacement-preserves-live");
    gn_manifest invalid;
    memset(&invalid, 0, sizeof(invalid));
    invalid.version = GN_MANIFEST_VERSION;
    invalid.profile = GN_PROFILE_DIAGNOSTIC;
    SDK_CHECK_STATUS("sdk.media.reject-empty-manifest", GN_STATUS_INVALID_MEDIA,
                     gn_load(instance, &invalid));
    SDK_CHECK_STATUS("sdk.reset.owned-seed", GN_STATUS_OK, gn_reset(instance));

    gn_observations before_run;
    memset(&before_run, 0xa5, sizeof(before_run));
    SDK_CHECK_STATUS("sdk.observe.reset", GN_STATUS_OK,
                     gn_observe(instance, &before_run));
    SDK_CHECK_U64("sdk.reset.arithmetic-zero", 0u, before_run.arithmetic_result);
    SDK_CHECK_U64("sdk.reset.initialized-zero", 0u, before_run.initialized_result);
    SDK_CHECK_U64("sdk.reset.bss-zero", 0u, before_run.bss_result);

    gn_run_result run;
    SDK_CHECK_STATUS("sdk.run.after-reset", GN_STATUS_OK, gn_run(instance, 172u, &run));
    gn_observations after_run;
    SDK_CHECK_STATUS("sdk.observe.after-reset-run", GN_STATUS_OK,
                     gn_observe(instance, &after_run));
    SDK_CHECK_U64("sdk.reset.restored-arithmetic", 10u, after_run.arithmetic_result);
    SDK_CHECK_U64("sdk.reset.restored-initialized", 0x1237u,
                  after_run.initialized_result);
    SDK_CHECK_U64("sdk.reset.restored-bss", 1u, after_run.bss_result);
    SDK_CHECK_U64("sdk.reset.restored-stop", GN_RUN_STOPPED, run.reason);
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sdk_assertions = 0u;
    sdk_cases = 0u;
    UNITY_BEGIN();
    RUN_TEST(original_guest_computes_named_results);
    RUN_TEST(failed_replacement_and_reset_preserve_owned_media);
    const int failures = UNITY_END();
    (void)printf(
        "SDK_RESULT {\"schema_version\":1,\"suite\":\"sdk_diagnostic\","
        "\"outcome\":\"%s\",\"outcomes\":[\"pass\",\"fail\","
        "\"skipped\",\"unsupported\",\"unknown\"],\"cases\":%" PRIu64
        ",\"assertions\":%" PRIu64 ",\"identity\":{\"source_revision\":\"%s\","
        "\"configuration\":\"%s\",\"compiler\":\"%s %s\"}}\n",
        failures == 0 ? "pass" : "fail", sdk_cases, sdk_assertions,
        GLUEYNEO_SOURCE_REVISION, GLUEYNEO_CONFIGURATION,
        GLUEYNEO_COMPILER_ID, GLUEYNEO_COMPILER_VERSION);
    return failures;
}
