/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "glueyneo/glueyneo.h"
#include "guest_fixture.h"

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

static gn_status load_scenario(gn_instance *target, unsigned scenario) {
    guest_fixture_image *fixture =
        (guest_fixture_image *)malloc(sizeof(*fixture));
    if (fixture == NULL) return GN_STATUS_OUT_OF_MEMORY;
    guest_fixture_build(fixture, (guest_fixture_scenario)scenario);
    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_DIAGNOSTIC;
    manifest.region_count = GN_MAX_REGIONS;
    manifest.regions[0] = (gn_region){0u, GUEST_FIXTURE_ROM_SIZE, fixture->rom,
                                      GUEST_FIXTURE_ROM_SIZE, GN_REGION_ROM};
    manifest.regions[1] = (gn_region){0x1000u, 4096u, fixture->ram_seed,
                                      GUEST_FIXTURE_RAM_INIT_SIZE, GN_REGION_RAM};
    const gn_status status = gn_load(target, &manifest);
    memset(fixture, 0xa5, sizeof(*fixture));
    free(fixture);
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

static void scenario_b_has_distinguishable_named_results(void) {
    SDK_CASE("sdk.diagnostic.original-b");
    SDK_CHECK_STATUS("sdk.media.load.original-b", GN_STATUS_OK,
                     load_scenario(instance, GUEST_FIXTURE_SCENARIO_B));
    gn_run_result run;
    SDK_CHECK_STATUS("sdk.run.scenario-b", GN_STATUS_OK, gn_run(instance, 172u, &run));
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.observe.scenario-b", GN_STATUS_OK,
                     gn_observe(instance, &observations));
    SDK_CHECK_U64("sdk.scenario-b.arithmetic", 16u,
                  observations.arithmetic_result);
    SDK_CHECK_U64("sdk.scenario-b.initialized", 0x2348u,
                  observations.initialized_result);
    SDK_CHECK_U64("sdk.scenario-b.bss", 1u, observations.bss_result);
    SDK_CHECK_U64("sdk.scenario-b.cycles", 172u, run.elapsed_cycles);
    SDK_CHECK_U64("sdk.scenario-b.instructions", 12u, run.instructions);
    SDK_CHECK_STATUS("sdk.scenario-b.stopped", GN_RUN_STOPPED, run.reason);
}

static void original_instruction_boundaries_match_manual_recipe(void) {
    static const uint64_t requests[] = {
        40u, 4u, 8u, 20u, 4u, 16u, 8u, 20u, 4u, 16u, 8u, 20u, 4u
    };
    static const uint64_t cumulative_cycles[] = {
        40u, 44u, 52u, 72u, 76u, 92u, 100u, 120u, 124u, 140u, 148u, 168u, 172u
    };
    static const uint32_t boundary_pcs[] = {
        0x100u, 0x102u, 0x104u, 0x10au, 0x10cu, 0x112u, 0x114u,
        0x11au, 0x11cu, 0x122u, 0x124u, 0x12au, 0x12eu
    };
    SDK_CASE("sdk.diagnostic.original-a-instruction-boundaries");
    uint64_t total_elapsed = 0u;
    uint64_t total_instructions = 0u;
    for (size_t index = 0u; index < sizeof(requests) / sizeof(requests[0]); ++index) {
        gn_run_result run;
        memset(&run, 0, sizeof(run));
        SDK_CHECK_STATUS("sdk.boundary.run", GN_STATUS_OK,
                         gn_run(instance, requests[index], &run));
        total_elapsed += run.elapsed_cycles;
        total_instructions += run.instructions;
        SDK_CHECK_U64("sdk.boundary.elapsed-this-call", requests[index],
                      run.elapsed_cycles);
        SDK_CHECK_U64("sdk.boundary.elapsed-total", cumulative_cycles[index],
                      total_elapsed);
        SDK_CHECK_U64("sdk.boundary.instructions-total", (uint64_t)index,
                      total_instructions);
        SDK_CHECK_U64("sdk.boundary.pc", boundary_pcs[index], run.boundary_pc);
        const gn_run_reason expected_reason =
            index + 1u == sizeof(requests) / sizeof(requests[0])
                ? GN_RUN_STOPPED
                : GN_RUN_BUDGET;
        SDK_CHECK_STATUS("sdk.boundary.reason", expected_reason, run.reason);
    }
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sdk_assertions = 0u;
    sdk_cases = 0u;
    UNITY_BEGIN();
    RUN_TEST(original_guest_computes_named_results);
    RUN_TEST(failed_replacement_and_reset_preserve_owned_media);
    RUN_TEST(scenario_b_has_distinguishable_named_results);
    RUN_TEST(original_instruction_boundaries_match_manual_recipe);
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
