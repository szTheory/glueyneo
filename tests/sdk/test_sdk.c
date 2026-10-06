/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "guest_fixture.h"
#include "sdk_private.h"
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
static uint64_t sdk_failpoint_positions;
static uint64_t sdk_failpoint_failures;
static uint64_t sdk_failpoint_success_boundaries;

static void make_manifest(gn_manifest *manifest, guest_fixture_image *fixture,
                          unsigned scenario) {
    guest_fixture_build(fixture, (guest_fixture_scenario)scenario);
    memset(manifest, 0, sizeof(*manifest));
    manifest->version = GN_MANIFEST_VERSION;
    manifest->profile = GN_PROFILE_DIAGNOSTIC;
    manifest->region_count = GN_MAX_REGIONS;
    manifest->regions[0] = (gn_region){0u, GUEST_FIXTURE_ROM_SIZE, fixture->rom,
                                      GUEST_FIXTURE_ROM_SIZE, GN_REGION_ROM};
    manifest->regions[1] = (gn_region){0x1000u, 4096u, fixture->ram_seed,
                                      GUEST_FIXTURE_RAM_INIT_SIZE, GN_REGION_RAM};
}

static gn_status load_scenario(gn_instance *target, unsigned scenario) {
    guest_fixture_image *fixture =
        (guest_fixture_image *)malloc(sizeof(*fixture));
    if (fixture == NULL) return GN_STATUS_OUT_OF_MEMORY;
    gn_manifest manifest;
    make_manifest(&manifest, fixture, scenario);
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

static uint64_t test_image_digest(const char *id, const gn_instance *target) {
    uint64_t digest = 0u;
    SDK_CHECK_STATUS(id, GN_STATUS_OK,
                     gn_test_image_digest(target, &digest));
    return digest;
}

static void rejected_manifest_preserves_digest(const char *id,
                                               gn_instance *target,
                                               const gn_manifest *candidate,
                                               gn_status expected) {
    const uint64_t before = test_image_digest("sdk.media.digest-before-reject",
                                              target);
    SDK_CHECK_STATUS(id, expected, gn_load(target, candidate));
    const uint64_t after = test_image_digest("sdk.media.digest-after-reject",
                                             target);
    SDK_CHECK_U64("sdk.media.rejected-load-keeps-full-image", before, after);
}

static void malformed_manifests_are_rejected_before_touching_live_media(void) {
    SDK_CASE("sdk.media.validation-preserves-live-image");
    guest_fixture_image *fixture =
        (guest_fixture_image *)malloc(sizeof(*fixture));
    TEST_ASSERT_NOT_NULL(fixture);
    gn_manifest valid;
    make_manifest(&valid, fixture, GUEST_FIXTURE_SCENARIO_A);
    SDK_CHECK_STATUS("sdk.media.exact-supported-manifest", GN_STATUS_OK,
                     gn_load(instance, &valid));

    gn_instance *baseline = NULL;
    SDK_CHECK_STATUS("sdk.media.baseline-create", GN_STATUS_OK,
                     gn_create(&baseline));
    SDK_CHECK_STATUS("sdk.media.baseline-load", GN_STATUS_OK,
                     load_scenario(baseline, GUEST_FIXTURE_SCENARIO_A));
    gn_run_result initial_run;
    gn_run_result baseline_run;
    SDK_CHECK_STATUS("sdk.media.initial-progress", GN_STATUS_OK,
                     gn_run(instance, 120u, &initial_run));
    SDK_CHECK_STATUS("sdk.media.baseline-progress", GN_STATUS_OK,
                     gn_run(baseline, 120u, &baseline_run));
    SDK_CHECK_STATUS("sdk.media.initial-budget-result", GN_RUN_BUDGET,
                     initial_run.reason);
    const uint64_t loaded_digest = test_image_digest("sdk.media.initial-digest",
                                                     instance);
    SDK_CHECK_U64("sdk.media.baseline-digest-matches",
                  test_image_digest("sdk.media.baseline-digest", baseline),
                  loaded_digest);

    gn_manifest candidate = valid;
    candidate.version += 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-version",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.region_count = 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-short-count",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.region_count = GN_MAX_REGIONS + 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-long-count",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.profile += 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-unsupported-profile",
                                       instance, &candidate,
                                       GN_STATUS_UNSUPPORTED_PROFILE);
    candidate = valid;
    candidate.regions[1].kind = GN_REGION_ROM;
    rejected_manifest_preserves_digest("sdk.media.reject-duplicate-role",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].kind = (gn_region_kind)0;
    rejected_manifest_preserves_digest("sdk.media.reject-unknown-role",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].source = NULL;
    rejected_manifest_preserves_digest("sdk.media.reject-null-source",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].source = NULL;
    candidate.regions[0].source_size = 0u;
    rejected_manifest_preserves_digest("sdk.media.reject-empty-rom",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].source_size = 0u;
    rejected_manifest_preserves_digest("sdk.media.reject-empty-ram-seed",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].source_size -= 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-short-rom",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].source_size += 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-long-rom",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].source_size -= 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-short-ram-seed",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].source_size += 1u;
    rejected_manifest_preserves_digest("sdk.media.reject-long-ram-seed",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[0].guest_base = 2u;
    rejected_manifest_preserves_digest("sdk.media.reject-rom-base",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    candidate = valid;
    candidate.regions[1].mapped_size -= 2u;
    rejected_manifest_preserves_digest("sdk.media.reject-ram-map-size",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);

    guest_fixture_image invalid_vectors = *fixture;
    invalid_vectors.rom[7] = 1u;
    candidate = valid;
    candidate.regions[0].source = invalid_vectors.rom;
    rejected_manifest_preserves_digest("sdk.media.reject-odd-reset-pc",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    invalid_vectors = *fixture;
    invalid_vectors.rom[4] = 0u;
    invalid_vectors.rom[5] = 0u;
    invalid_vectors.rom[6] = 2u;
    invalid_vectors.rom[7] = 0u;
    candidate = valid;
    candidate.regions[0].source = invalid_vectors.rom;
    rejected_manifest_preserves_digest("sdk.media.reject-pc-at-map-end",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);
    invalid_vectors = *fixture;
    invalid_vectors.rom[3] = 1u;
    candidate = valid;
    candidate.regions[0].source = invalid_vectors.rom;
    rejected_manifest_preserves_digest("sdk.media.reject-initial-ssp",
                                       instance, &candidate,
                                       GN_STATUS_INVALID_MEDIA);

    uint64_t after_digest = test_image_digest("sdk.media.final-digest", instance);
    SDK_CHECK_U64("sdk.media.all-rejections-kept-current-state", loaded_digest,
                  after_digest);
    gn_run_result final_run;
    gn_run_result baseline_final_run;
    SDK_CHECK_STATUS("sdk.media.continued-run", GN_STATUS_OK,
                     gn_run(instance, 52u, &final_run));
    SDK_CHECK_STATUS("sdk.media.baseline-continued-run", GN_STATUS_OK,
                     gn_run(baseline, 52u, &baseline_final_run));
    SDK_CHECK_STATUS("sdk.media.continued-stop", GN_RUN_STOPPED,
                     final_run.reason);
    SDK_CHECK_U64("sdk.media.continued-cycles-match",
                  baseline_final_run.elapsed_cycles, final_run.elapsed_cycles);
    SDK_CHECK_U64("sdk.media.continued-instructions-match",
                  baseline_final_run.instructions, final_run.instructions);
    SDK_CHECK_U64("sdk.media.continued-pc-match",
                  baseline_final_run.boundary_pc, final_run.boundary_pc);
    gn_observations after;
    gn_observations baseline_after;
    SDK_CHECK_STATUS("sdk.media.continued-observe", GN_STATUS_OK,
                     gn_observe(instance, &after));
    SDK_CHECK_STATUS("sdk.media.baseline-observe", GN_STATUS_OK,
                     gn_observe(baseline, &baseline_after));
    SDK_CHECK_U64("sdk.media.continued-result-match",
                  baseline_after.arithmetic_result, after.arithmetic_result);
    SDK_CHECK_U64("sdk.media.continued-initialized-match",
                  baseline_after.initialized_result, after.initialized_result);
    gn_destroy(baseline);
    free(fixture);
}

static void region_range_arithmetic_and_cap_are_checked_without_dereference(void) {
    SDK_CASE("sdk.media.range-overlap-endpoint-and-cap");
    guest_fixture_image fixture;
    gn_manifest manifest;
    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);

    manifest.regions[1].guest_base = GUEST_FIXTURE_ROM_SIZE;
    SDK_CHECK_STATUS("sdk.media.adjacent-spans-layout-valid", GN_STATUS_OK,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media.adjacent-span-profile-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
    manifest.regions[1].guest_base = GUEST_FIXTURE_ROM_SIZE - 1u;
    SDK_CHECK_STATUS("sdk.media.one-byte-overlap-rejected",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media.one-byte-overlap-load-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));

    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);
    manifest.regions[0].mapped_size = UINT32_C(800000);
    manifest.regions[1].guest_base = UINT32_C(0x00100000);
    manifest.regions[1].mapped_size =
        (uint32_t)(GN_MAX_MEDIA_BYTES - 522u - 800000u);
    SDK_CHECK_STATUS("sdk.media-exact-one-mib-accounting",
                     GN_STATUS_OK,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-exact-one-mib-profile-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
    manifest.regions[1].mapped_size += 1u;
    SDK_CHECK_STATUS("sdk.media-over-one-mib-accounting",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-over-one-mib-load-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));

    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);
    manifest.regions[1].source = (const uint8_t *)(uintptr_t)1u;
    manifest.regions[1].source_size = SIZE_MAX;
    manifest.regions[1].mapped_size = UINT32_MAX;
    SDK_CHECK_STATUS("sdk.media-size-max-rejected-before-read",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-size-max-load-rejected-before-read",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
    manifest.regions[1].source_size = 8u;
    manifest.regions[1].mapped_size = 8u;
    manifest.regions[1].guest_base = UINT32_MAX - 3u;
    SDK_CHECK_STATUS("sdk.media-u32-endpoint-overflow-rejected",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-u32-endpoint-load-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
    manifest.regions[1].guest_base = UINT32_C(0x00100000);
    manifest.regions[1].source_size = 1u;
    manifest.regions[1].mapped_size = UINT32_MAX;
    SDK_CHECK_STATUS("sdk.media-u32-map-size-over-cap-rejected",
                     GN_STATUS_INVALID_MEDIA,
                     gn_test_validate_region_layout(&manifest));
    SDK_CHECK_STATUS("sdk.media-u32-map-size-load-rejected",
                     GN_STATUS_INVALID_MEDIA, gn_load(instance, &manifest));
}

static void successful_replacement_owns_source_and_reset_seed(void) {
    SDK_CASE("sdk.media.replacement-copies-and-resets-seed");
    guest_fixture_image *source =
        (guest_fixture_image *)malloc(sizeof(*source));
    TEST_ASSERT_NOT_NULL(source);
    gn_manifest manifest;
    make_manifest(&manifest, source, GUEST_FIXTURE_SCENARIO_B);
    SDK_CHECK_STATUS("sdk.media.load-distinguishable-replacement", GN_STATUS_OK,
                     gn_load(instance, &manifest));
    memset(source, 0xa5, sizeof(*source));
    free(source);

    gn_run_result run;
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.media.reset-after-source-release", GN_STATUS_OK,
                     gn_reset(instance));
    SDK_CHECK_STATUS("sdk.media.run-after-source-release", GN_STATUS_OK,
                     gn_run(instance, 172u, &run));
    SDK_CHECK_STATUS("sdk.media.observe-after-source-release", GN_STATUS_OK,
                     gn_observe(instance, &observations));
    SDK_CHECK_STATUS("sdk.media.replacement-stopped", GN_RUN_STOPPED, run.reason);
    SDK_CHECK_U64("sdk.media.replacement-arithmetic", 16u,
                  observations.arithmetic_result);
    SDK_CHECK_U64("sdk.media.replacement-initialized-seed", 0x2348u,
                  observations.initialized_result);
    SDK_CHECK_U64("sdk.media.replacement-bss-zero-fill", 1u,
                  observations.bss_result);
}

static void peer_start_at_first_instruction(gn_instance *peer,
                                            const char *label) {
    gn_run_result run;
    SDK_CHECK_STATUS(label, GN_STATUS_OK, gn_reset(peer));
    SDK_CHECK_STATUS("sdk.faults.peer-reset-budget", GN_STATUS_OK,
                     gn_run(peer, 40u, &run));
    SDK_CHECK_STATUS("sdk.faults.peer-reset-boundary", GN_RUN_BUDGET,
                     run.reason);
    SDK_CHECK_U64("sdk.faults.peer-reset-pc", 0x100u, run.boundary_pc);
}

static void peer_progress_after_failure(gn_instance *peer,
                                        const char *label) {
    gn_run_result run;
    SDK_CHECK_STATUS(label, GN_STATUS_OK, gn_run(peer, 4u, &run));
    SDK_CHECK_STATUS("sdk.faults.peer-progress-budget", GN_RUN_BUDGET,
                     run.reason);
    SDK_CHECK_U64("sdk.faults.peer-progress-pc", 0x102u, run.boundary_pc);
}

static void assert_test_allocator_counts(const char *label,
                                         const gn_test_allocator *allocator,
                                         size_t attempts,
                                         size_t total_attempts,
                                         size_t live_allocations,
                                         size_t live_bytes) {
    char field[96];
    (void)snprintf(field, sizeof(field), "%s.attempts", label);
    SDK_CHECK_U64(field, attempts, allocator->attempts);
    (void)snprintf(field, sizeof(field), "%s.total-attempts", label);
    SDK_CHECK_U64(field, total_attempts, allocator->total_attempts);
    (void)snprintf(field, sizeof(field), "%s.live-allocations", label);
    SDK_CHECK_U64(field, live_allocations, allocator->live_allocations);
    (void)snprintf(field, sizeof(field), "%s.live-bytes", label);
    SDK_CHECK_U64(field, live_bytes, allocator->live_bytes);
    (void)printf("# ALLOCATION %s attempts=%zu total_attempts=%zu "
                 "live_allocations=%zu live_bytes=%zu\n",
                 label, allocator->attempts, allocator->total_attempts,
                 allocator->live_allocations, allocator->live_bytes);
}

static void assert_named_result(gn_instance *target, uint32_t arithmetic,
                                const char *label) {
    gn_run_result run;
    gn_observations observations;
    SDK_CHECK_STATUS("sdk.faults.recovery-run", GN_STATUS_OK,
                     gn_run(target, 172u, &run));
    SDK_CHECK_STATUS("sdk.faults.recovery-observe", GN_STATUS_OK,
                     gn_observe(target, &observations));
    SDK_CHECK_STATUS(label, GN_RUN_STOPPED, run.reason);
    SDK_CHECK_U64("sdk.faults.recovery-result", arithmetic,
                  observations.arithmetic_result);
}

static void allocation_failures_in_create_and_first_load_are_contained(void) {
    SDK_CASE("sdk.faults.create-and-first-load-allocation-sweep");
    gn_instance *peer = NULL;
    SDK_CHECK_STATUS("sdk.faults.peer-create", GN_STATUS_OK, gn_create(&peer));
    SDK_CHECK_STATUS("sdk.faults.peer-load-b", GN_STATUS_OK,
                     load_scenario(peer, GUEST_FIXTURE_SCENARIO_B));
    peer_start_at_first_instruction(peer, "sdk.faults.peer-before-create-failure");

    gn_test_allocator create_failure;
    gn_test_allocator_init(&create_failure);
    gn_test_allocator_arm(&create_failure, 1u);
    gn_instance *created = (gn_instance *)(uintptr_t)1u;
    ++sdk_failpoint_positions;
    ++sdk_failpoint_failures;
    SDK_CHECK_STATUS("sdk.faults.create-allocation-fails", GN_STATUS_OUT_OF_MEMORY,
                     gn_test_create(&create_failure, &created));
    SDK_CHECK_TRUE("sdk.faults.create-output-cleared", created == NULL);
    assert_test_allocator_counts("create-fail-1", &create_failure, 1u, 1u,
                                 0u, 0u);
    peer_progress_after_failure(peer, "sdk.faults.peer-after-create-failure");

    gn_test_allocator create_success;
    gn_test_allocator_init(&create_success);
    gn_test_allocator_arm(&create_success, 2u);
    ++sdk_failpoint_positions;
    ++sdk_failpoint_success_boundaries;
    SDK_CHECK_STATUS("sdk.faults.create-first-success", GN_STATUS_OK,
                     gn_test_create(&create_success, &created));
    assert_test_allocator_counts("create-success-after-1", &create_success,
                                 1u, 1u, 1u, create_success.live_bytes);
    peer_start_at_first_instruction(peer, "sdk.faults.peer-before-create-success");
    peer_progress_after_failure(peer, "sdk.faults.peer-after-create-success");
    gn_destroy(created);
    assert_test_allocator_counts("create-destroy", &create_success, 1u, 1u,
                                 0u, 0u);

    for (size_t fail_at = 1u; fail_at <= 6u; ++fail_at) {
        gn_test_allocator allocator;
        gn_test_allocator_init(&allocator);
        gn_instance *target = NULL;
        SDK_CHECK_STATUS("sdk.faults.first-load-create", GN_STATUS_OK,
                         gn_test_create(&allocator, &target));
        const size_t baseline_allocations = allocator.live_allocations;
        const size_t baseline_bytes = allocator.live_bytes;
        gn_test_allocator_arm(&allocator, fail_at);
        peer_start_at_first_instruction(peer, "sdk.faults.peer-before-first-load-failure");

        gn_manifest invalid;
        memset(&invalid, 0, sizeof(invalid));
        invalid.version = GN_MANIFEST_VERSION;
        invalid.profile = GN_PROFILE_DIAGNOSTIC;
        SDK_CHECK_STATUS("sdk.faults.invalid-request-before-first-load",
                         GN_STATUS_INVALID_MEDIA, gn_load(target, &invalid));
        SDK_CHECK_U64("sdk.faults.invalid-request-allocation-free", 0u,
                      allocator.attempts);

        const gn_status expected = fail_at <= 5u ? GN_STATUS_OUT_OF_MEMORY
                                                 : GN_STATUS_OK;
        ++sdk_failpoint_positions;
        if (fail_at <= 5u) {
            ++sdk_failpoint_failures;
        } else {
            ++sdk_failpoint_success_boundaries;
        }
        const gn_status actual = load_scenario(target,
                                               GUEST_FIXTURE_SCENARIO_A);
        char label[64];
        (void)snprintf(label, sizeof(label), "first-load-position-%zu", fail_at);
        SDK_CHECK_STATUS(label, expected, actual);
        const size_t expected_attempts = fail_at <= 5u ? fail_at : 5u;
        const size_t expected_total_attempts = 1u + expected_attempts;
        const size_t expected_allocations =
            baseline_allocations + (fail_at <= 5u ? 0u : 5u);
        const size_t expected_bytes = fail_at <= 5u ? baseline_bytes
                                                     : allocator.live_bytes;
        assert_test_allocator_counts(label, &allocator, expected_attempts,
                                     expected_total_attempts,
                                     expected_allocations, expected_bytes);
        peer_progress_after_failure(peer, "sdk.faults.peer-after-first-load-failure");
        gn_test_allocator_disarm(&allocator);

        if (fail_at <= 5u) {
            gn_run_result run;
            gn_observations observations;
            SDK_CHECK_STATUS("sdk.faults.first-load-unloaded-reset",
                             GN_STATUS_INVALID_STATE, gn_reset(target));
            SDK_CHECK_STATUS("sdk.faults.first-load-unloaded-run",
                             GN_STATUS_INVALID_STATE, gn_run(target, 1u, &run));
            SDK_CHECK_U64("sdk.faults.first-load-error-output-cleared", 0u,
                          run.requested_cycles);
            SDK_CHECK_STATUS("sdk.faults.first-load-unloaded-observe",
                             GN_STATUS_INVALID_STATE,
                             gn_observe(target, &observations));
            SDK_CHECK_U64("sdk.faults.first-load-observation-cleared", 0u,
                          observations.arithmetic_result);
            SDK_CHECK_STATUS("sdk.faults.first-load-unload-after-error",
                             GN_STATUS_OK, gn_unload(target));
            SDK_CHECK_STATUS("sdk.faults.first-load-reload", GN_STATUS_OK,
                             load_scenario(target, GUEST_FIXTURE_SCENARIO_B));
        } else {
            SDK_CHECK_STATUS("sdk.faults.first-load-reset", GN_STATUS_OK,
                             gn_reset(target));
            assert_named_result(target, 10u, "sdk.faults.first-load-success-stopped");
            SDK_CHECK_STATUS("sdk.faults.first-load-unload", GN_STATUS_OK,
                             gn_unload(target));
            SDK_CHECK_STATUS("sdk.faults.first-load-reload", GN_STATUS_OK,
                             load_scenario(target, GUEST_FIXTURE_SCENARIO_B));
        }
        SDK_CHECK_STATUS("sdk.faults.first-load-invalid-budget-recovery",
                         GN_STATUS_OK, gn_reset(target));
        assert_named_result(target, 16u, "sdk.faults.first-load-reloaded-b-stopped");
        SDK_CHECK_STATUS("sdk.faults.first-load-final-unload", GN_STATUS_OK,
                         gn_unload(target));
        gn_destroy(target);
        assert_test_allocator_counts("first-load-final-destroy", &allocator,
                                     expected_attempts + 5u,
                                     expected_total_attempts + 5u, 0u, 0u);
    }

    gn_reset(peer);
    assert_named_result(peer, 16u, "sdk.faults.peer-remains-distinct-b");
    gn_destroy(peer);
}

static void allocation_failures_in_replacement_preserve_old_image_and_peer(void) {
    SDK_CASE("sdk.faults.replacement-allocation-sweep");
    gn_instance *peer = NULL;
    SDK_CHECK_STATUS("sdk.faults.replacement-peer-create", GN_STATUS_OK,
                     gn_create(&peer));
    SDK_CHECK_STATUS("sdk.faults.replacement-peer-load-b", GN_STATUS_OK,
                     load_scenario(peer, GUEST_FIXTURE_SCENARIO_B));

    for (size_t fail_at = 1u; fail_at <= 6u; ++fail_at) {
        gn_test_allocator allocator;
        gn_test_allocator_init(&allocator);
        gn_instance *target = NULL;
        SDK_CHECK_STATUS("sdk.faults.replacement-create", GN_STATUS_OK,
                         gn_test_create(&allocator, &target));
        SDK_CHECK_STATUS("sdk.faults.replacement-load-original-a", GN_STATUS_OK,
                         load_scenario(target, GUEST_FIXTURE_SCENARIO_A));
        gn_run_result partial;
        SDK_CHECK_STATUS("sdk.faults.replacement-partial-run", GN_STATUS_OK,
                         gn_run(target, 120u, &partial));
        const uint64_t before = test_image_digest("sdk.faults.replacement-before",
                                                  target);
        const size_t baseline_allocations = allocator.live_allocations;
        const size_t baseline_bytes = allocator.live_bytes;
        gn_test_allocator_arm(&allocator, fail_at);
        peer_start_at_first_instruction(peer,
                                        "sdk.faults.peer-before-replacement-failure");

        gn_manifest invalid;
        memset(&invalid, 0, sizeof(invalid));
        invalid.version = GN_MANIFEST_VERSION;
        invalid.profile = GN_PROFILE_DIAGNOSTIC;
        SDK_CHECK_STATUS("sdk.faults.invalid-request-before-replacement",
                         GN_STATUS_INVALID_MEDIA, gn_load(target, &invalid));
        SDK_CHECK_U64("sdk.faults.replacement-invalid-is-allocation-free", 0u,
                      allocator.attempts);

        const gn_status expected = fail_at <= 5u ? GN_STATUS_OUT_OF_MEMORY
                                                 : GN_STATUS_OK;
        ++sdk_failpoint_positions;
        if (fail_at <= 5u) {
            ++sdk_failpoint_failures;
        } else {
            ++sdk_failpoint_success_boundaries;
        }
        const gn_status actual = load_scenario(target,
                                               GUEST_FIXTURE_SCENARIO_B);
        char label[64];
        (void)snprintf(label, sizeof(label), "replacement-position-%zu", fail_at);
        SDK_CHECK_STATUS(label, expected, actual);
        const size_t expected_attempts = fail_at <= 5u ? fail_at : 5u;
        const size_t expected_total_attempts = 6u + expected_attempts;
        assert_test_allocator_counts(label, &allocator, expected_attempts,
                                     expected_total_attempts,
                                     baseline_allocations, baseline_bytes);
        peer_progress_after_failure(peer,
                                    "sdk.faults.peer-after-replacement-failure");
        gn_test_allocator_disarm(&allocator);

        if (fail_at <= 5u) {
            SDK_CHECK_U64("sdk.faults.failed-replacement-keeps-complete-image",
                          before,
                          test_image_digest("sdk.faults.replacement-after",
                                            target));
            gn_run_result invalid_budget;
            memset(&invalid_budget, 0xa5, sizeof(invalid_budget));
            SDK_CHECK_STATUS("sdk.faults.replacement-invalid-budget",
                             GN_STATUS_INVALID_ARGUMENT,
                             gn_run(target, GN_MAX_CYCLE_BUDGET + 1u,
                                    &invalid_budget));
            SDK_CHECK_U64("sdk.faults.replacement-invalid-budget-zeroed", 0u,
                          invalid_budget.requested_cycles);
            SDK_CHECK_STATUS("sdk.faults.replacement-reset-after-error",
                             GN_STATUS_OK, gn_reset(target));
            assert_named_result(target, 10u,
                                "sdk.faults.replacement-old-a-recovers");
            SDK_CHECK_STATUS("sdk.faults.replacement-unload-after-error",
                             GN_STATUS_OK, gn_unload(target));
            SDK_CHECK_STATUS("sdk.faults.replacement-reload-after-error",
                             GN_STATUS_OK,
                             load_scenario(target, GUEST_FIXTURE_SCENARIO_B));
        } else {
            SDK_CHECK_TRUE("sdk.faults.successful-replacement-changes-image",
                           before != test_image_digest(
                                        "sdk.faults.replacement-success-digest",
                                        target));
            assert_named_result(target, 16u,
                                "sdk.faults.successful-replacement-b");
            SDK_CHECK_STATUS("sdk.faults.successful-replacement-reset",
                             GN_STATUS_OK, gn_reset(target));
        }
        assert_named_result(target, 16u, "sdk.faults.replacement-b-recovery");
        SDK_CHECK_STATUS("sdk.faults.replacement-final-unload", GN_STATUS_OK,
                         gn_unload(target));
        gn_destroy(target);
        assert_test_allocator_counts("replacement-final-destroy", &allocator,
                                     expected_attempts + (fail_at <= 5u ? 5u : 0u),
                                     expected_total_attempts +
                                         (fail_at <= 5u ? 5u : 0u),
                                     0u, 0u);
    }

    gn_reset(peer);
    assert_named_result(peer, 16u, "sdk.faults.replacement-peer-b");
    gn_destroy(peer);
}

static void guest_fault_reset_and_invalid_requests_allow_recovery(void) {
    SDK_CASE("sdk.faults.guest-fault-and-invalid-request-recovery");
    guest_fixture_image fixture;
    gn_manifest manifest;
    make_manifest(&manifest, &fixture, GUEST_FIXTURE_SCENARIO_A);
    fixture.rom[0x100u] = UINT8_C(0x4a);
    fixture.rom[0x101u] = UINT8_C(0xfc);
    SDK_CHECK_STATUS("sdk.faults.load-guest-fault", GN_STATUS_OK,
                     gn_load(instance, &manifest));
    gn_run_result result;
    SDK_CHECK_STATUS("sdk.faults.guest-fault-run-status", GN_STATUS_OK,
                     gn_run(instance, 172u, &result));
    SDK_CHECK_STATUS("sdk.faults.guest-fault-reason", GN_RUN_FAULT,
                     result.reason);
    SDK_CHECK_U64("sdk.faults.guest-fault-pc", 0x100u, result.fault_pc);
    SDK_CHECK_STATUS("sdk.faults.reset-after-guest-fault", GN_STATUS_OK,
                     gn_reset(instance));
    SDK_CHECK_STATUS("sdk.faults.repeat-guest-fault-status", GN_STATUS_OK,
                     gn_run(instance, 172u, &result));
    SDK_CHECK_STATUS("sdk.faults.repeat-guest-fault-reason", GN_RUN_FAULT,
                     result.reason);
    SDK_CHECK_STATUS("sdk.faults.unload-after-guest-fault", GN_STATUS_OK,
                     gn_unload(instance));
    SDK_CHECK_STATUS("sdk.faults.reload-after-guest-fault", GN_STATUS_OK,
                     load_scenario(instance, GUEST_FIXTURE_SCENARIO_B));
    assert_named_result(instance, 16u, "sdk.faults.valid-run-after-fault");
}

static void sdk_lifecycle_suite(void) {
    RUN_TEST(unloaded_lifecycle_and_null_arguments_are_reported);
    RUN_TEST(unload_reload_and_repeated_reset_reproduce_results);
}

static void sdk_media_suite(void) {
    RUN_TEST(malformed_manifests_are_rejected_before_touching_live_media);
    RUN_TEST(region_range_arithmetic_and_cap_are_checked_without_dereference);
    RUN_TEST(successful_replacement_owns_source_and_reset_seed);
}

static void sdk_faults_suite(void) {
    RUN_TEST(allocation_failures_in_create_and_first_load_are_contained);
    RUN_TEST(allocation_failures_in_replacement_preserve_old_image_and_peer);
    RUN_TEST(guest_fault_reset_and_invalid_requests_allow_recovery);
    (void)printf("# FAILPOINT_SWEEP positions=%" PRIu64
                 " injected_failures=%" PRIu64
                 " successful_boundaries=%" PRIu64 "\n",
                 sdk_failpoint_positions, sdk_failpoint_failures,
                 sdk_failpoint_success_boundaries);
    SDK_CHECK_U64("sdk.faults.failpoint-positions", 14u,
                  sdk_failpoint_positions);
    SDK_CHECK_U64("sdk.faults.injected-failure-count", 11u,
                  sdk_failpoint_failures);
    SDK_CHECK_U64("sdk.faults.first-success-boundaries", 3u,
                  sdk_failpoint_success_boundaries);
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
    } else if (strcmp(selected_suite, "media") == 0) {
        sdk_media_suite();
    } else if (strcmp(selected_suite, "faults") == 0) {
        sdk_faults_suite();
    } else {
        (void)fprintf(stderr, "unknown suite: %s\n", selected_suite);
        return 2;
    }
    const int failures = UNITY_END();
    sdk_test_result(selected_suite, failures, GLUEYNEO_SOURCE_REVISION,
                    GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
                    GLUEYNEO_COMPILER_VERSION);
    return failures;
}
