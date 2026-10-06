/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "guest_fixture.h"
#include "test_support.h"

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
static const char *selected_suite;

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
    if (instance != NULL && strcmp(selected_suite, "diagnostic") == 0) {
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

static void unloaded_lifecycle_and_null_arguments_are_reported(void) {
    SDK_CASE("sdk.lifecycle.unloaded-and-null-arguments");
    gn_run_result run;
    gn_observations observations;
    memset(&run, 0xa5, sizeof(run));
    memset(&observations, 0xa5, sizeof(observations));

    SDK_CHECK_STATUS("sdk.lifecycle.create-null-output", GN_STATUS_INVALID_ARGUMENT,
                     gn_create(NULL));
    gn_instance *created = (gn_instance *)(uintptr_t)1u;
    SDK_CHECK_STATUS("sdk.lifecycle.create-clears-output", GN_STATUS_OK,
                     gn_create(&created));
    SDK_CHECK_TRUE("sdk.lifecycle.created-handle", created != NULL);
    SDK_CHECK_STATUS("sdk.lifecycle.reset-before-load", GN_STATUS_INVALID_STATE,
                     gn_reset(created));
    SDK_CHECK_STATUS("sdk.lifecycle.run-before-load", GN_STATUS_INVALID_STATE,
                     gn_run(created, 1u, &run));
    SDK_CHECK_U64("sdk.lifecycle.run-output-zero-request", 0u, run.requested_cycles);
    SDK_CHECK_U64("sdk.lifecycle.run-output-zero-reason", GN_RUN_BUDGET, run.reason);
    SDK_CHECK_STATUS("sdk.lifecycle.observe-before-load", GN_STATUS_INVALID_STATE,
                     gn_observe(created, &observations));
    SDK_CHECK_U64("sdk.lifecycle.observe-output-zero", 0u,
                  observations.initialized_result);
    SDK_CHECK_STATUS("sdk.lifecycle.null-run-handle", GN_STATUS_INVALID_ARGUMENT,
                     gn_run(NULL, 1u, &run));
    SDK_CHECK_U64("sdk.lifecycle.null-run-zero-output", 0u, run.elapsed_cycles);
    SDK_CHECK_STATUS("sdk.lifecycle.null-observe-handle", GN_STATUS_INVALID_ARGUMENT,
                     gn_observe(NULL, &observations));
    SDK_CHECK_U64("sdk.lifecycle.null-observe-zero-output", 0u,
                  observations.arithmetic_result);
    SDK_CHECK_STATUS("sdk.lifecycle.null-reset-handle", GN_STATUS_INVALID_ARGUMENT,
                     gn_reset(NULL));
    SDK_CHECK_STATUS("sdk.lifecycle.null-unload-handle", GN_STATUS_INVALID_ARGUMENT,
                     gn_unload(NULL));
    SDK_CHECK_STATUS("sdk.lifecycle.unload-already-unloaded", GN_STATUS_OK,
                     gn_unload(created));
    SDK_CHECK_STATUS("sdk.lifecycle.unload-repeat", GN_STATUS_OK,
                     gn_unload(created));
    SDK_CHECK_STATUS("sdk.lifecycle.run-null-output", GN_STATUS_INVALID_ARGUMENT,
                     gn_run(created, 1u, NULL));
    SDK_CHECK_STATUS("sdk.lifecycle.load-null-manifest", GN_STATUS_INVALID_ARGUMENT,
                     gn_load(created, NULL));
    gn_destroy(NULL);
    gn_destroy(created);
}

static void unload_reload_and_repeated_reset_reproduce_results(void) {
    SDK_CASE("sdk.lifecycle.unload-reload-repeat-reset");
    gn_instance *created = NULL;
    SDK_CHECK_STATUS("sdk.lifecycle.create", GN_STATUS_OK, gn_create(&created));
    SDK_CHECK_STATUS("sdk.lifecycle.load", GN_STATUS_OK, load_scenario(created, 0u));

    for (unsigned reset = 0u; reset < 2u; ++reset) {
        gn_run_result run;
        gn_observations observations;
        SDK_CHECK_STATUS("sdk.lifecycle.reset-loaded", GN_STATUS_OK,
                         gn_reset(created));
        SDK_CHECK_STATUS("sdk.lifecycle.run-after-reset", GN_STATUS_OK,
                         gn_run(created, 172u, &run));
        SDK_CHECK_STATUS("sdk.lifecycle.observe-after-run", GN_STATUS_OK,
                         gn_observe(created, &observations));
        SDK_CHECK_STATUS("sdk.lifecycle.repeat-stop", GN_RUN_STOPPED, run.reason);
        SDK_CHECK_U64("sdk.lifecycle.repeat-result", 10u,
                      observations.arithmetic_result);
        SDK_CHECK_U64("sdk.lifecycle.repeat-initialized", 0x1237u,
                      observations.initialized_result);
    }

    SDK_CHECK_STATUS("sdk.lifecycle.unload", GN_STATUS_OK, gn_unload(created));
    SDK_CHECK_STATUS("sdk.lifecycle.reset-after-unload", GN_STATUS_INVALID_STATE,
                     gn_reset(created));
    SDK_CHECK_STATUS("sdk.lifecycle.reload", GN_STATUS_OK, load_scenario(created, 1u));
    gn_run_result run;
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.lifecycle.run-after-reload", GN_STATUS_OK,
                     gn_run(created, 172u, &run));
    SDK_CHECK_STATUS("sdk.lifecycle.observe-after-reload", GN_STATUS_OK,
                     gn_observe(created, &observations));
    SDK_CHECK_U64("sdk.lifecycle.reloaded-scenario", 16u,
                  observations.arithmetic_result);
    SDK_CHECK_STATUS("sdk.lifecycle.destroy-after-use", GN_STATUS_OK,
                     gn_unload(created));
    gn_destroy(created);
}

static void sdk_lifecycle_suite(void) {
    RUN_TEST(unloaded_lifecycle_and_null_arguments_are_reported);
    RUN_TEST(unload_reload_and_repeated_reset_reproduce_results);
}

static void sdk_diagnostic_suite(void) {
    RUN_TEST(original_guest_computes_named_results);
    RUN_TEST(failed_replacement_and_reset_preserve_owned_media);
    RUN_TEST(scenario_b_has_distinguishable_named_results);
    RUN_TEST(original_instruction_boundaries_match_manual_recipe);
}

int main(int argc, char **argv) {
    if (argc != 2) {
        (void)fprintf(stderr, "usage: %s <diagnostic|lifecycle|media|faults>\n",
                      argv[0]);
        return 2;
    }
    selected_suite = argv[1];
    UNITY_BEGIN();
    if (strcmp(selected_suite, "diagnostic") == 0) {
        sdk_diagnostic_suite();
    } else if (strcmp(selected_suite, "lifecycle") == 0) {
        sdk_lifecycle_suite();
    } else if (strcmp(selected_suite, "media") != 0 &&
               strcmp(selected_suite, "faults") != 0) {
        (void)fprintf(stderr, "unknown suite: %s\n", selected_suite);
        return 2;
    }
    const int failures = UNITY_END();
    sdk_test_result(selected_suite, failures, GLUEYNEO_SOURCE_REVISION,
                    GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
                    GLUEYNEO_COMPILER_VERSION);
    return failures;
}
