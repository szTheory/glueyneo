/* SPDX-License-Identifier: MIT */
#include "state_fixture.h"
#include "chips/ym2610_candidate.h"
#include "chips/z80_candidate.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

void state_oom_case_counts(uint64_t *out_cases, uint64_t *out_assertions) {
    (void)sdk_test_result;
    (void)state_fixture_write_u32be;
    (void)state_fixture_guard_valid;
    if (out_cases != NULL) *out_cases = sdk_cases;
    if (out_assertions != NULL) *out_assertions = sdk_assertions;
}

typedef struct {
    gn_instance *instance;
    const uint8_t *state;
    size_t state_size;
    gn_state_detail_v1 detail;
} restore_operation;

static int invoke_restore(void *raw) {
    restore_operation *operation = (restore_operation *)raw;
    memset(&operation->detail, 0, sizeof(operation->detail));
    const gn_status status = gn_state_restore_v1(
        operation->instance, operation->state, operation->state_size,
        &operation->detail, sizeof(operation->detail));
    STATE_RESOURCE_CHECK(operation->instance);
    return (int)status;
}

static void state_mutation_fault_recovery_test(void) {
    SDK_CASE("sdk.state.oom.faulted-sound-capture-and-recovery");
    gn_instance *target = NULL;
    gn_instance *witness = NULL;
    uint8_t *baseline = NULL;
    uint8_t *blocked_output = NULL;
    uint8_t *malformed = NULL;
    size_t capacity = 0u;
    uintptr_t target_owner = 0u;
    uintptr_t witness_owner = 0u;
    gn_run_result raw;
    gn_state_detail_v1 detail;
    size_t written = 0u;
    gn_status faulted_capture = GN_STATUS_OK;

    SDK_CHECK_TRUE("sdk.state.oom.fault-target-load",
                   state_fixture_load(&target, 0u));
    SDK_CHECK_TRUE("sdk.state.oom.fault-independent-witness-load",
                   state_fixture_load(&witness, 0u));
    if (target == NULL || witness == NULL) goto cleanup;
    SDK_CHECK_TRUE("sdk.state.oom.fault-baseline-capture",
                   state_fixture_capture(target, &baseline, &capacity));
    if (baseline == NULL) goto cleanup;
    SDK_CHECK_TRUE("sdk.state.oom.fault-witness-baseline",
                   state_fixture_restore(witness, baseline, capacity));
    target_owner = gn_test_mvs_save_ram_address(target);
    witness_owner = gn_test_mvs_save_ram_address(witness);
    SDK_CHECK_STATUS("sdk.state.oom.inject-known-sound-fault", GN_STATUS_OK,
        gn_test_mvs_set_failure(target, GN_TEST_MVS_FAILURE_SOUND_TICK_LIMIT));
    SDK_CHECK_STATUS("sdk.state.oom.known-sound-fault-status",
                     GN_STATUS_CPU_FAILURE, gn_run(target, 64u, &raw));

    blocked_output = (uint8_t *)malloc(capacity);
    malformed = (uint8_t *)malloc(capacity);
    SDK_CHECK_TRUE("sdk.state.oom.fault-rejection-buffers",
                   blocked_output != NULL && malformed != NULL);
    if (blocked_output == NULL || malformed == NULL) goto cleanup;
    memset(blocked_output, 0x6du, capacity);
    written = 77u;
    faulted_capture = gn_state_capture_v1(target, blocked_output, capacity,
                                          &written, &detail, sizeof(detail));
    SDK_CHECK_STATUS("sdk.state.oom.faulted-capture-ineligible",
                     GN_STATUS_INVALID_STATE, faulted_capture);
    SDK_CHECK_U64("sdk.state.oom.faulted-capture-reason",
                  GN_STATE_REASON_GUEST_FAULT, detail.reason);
    SDK_CHECK_U64("sdk.state.oom.faulted-capture-count-zero", 0u, written);
    SDK_CHECK_U64("sdk.state.oom.faulted-capture-does-not-write", 0x6du,
                  blocked_output[0]);

    memcpy(malformed, baseline, capacity);
    malformed[68] = 1u;
    SDK_CHECK_STATUS("sdk.state.oom.malformed-restore-while-faulted",
                     GN_STATUS_INVALID_MEDIA,
        gn_state_restore_v1(target, malformed, capacity, &detail,
                            sizeof(detail)));
    SDK_CHECK_U64("sdk.state.oom.malformed-rejection-reason",
                  GN_STATE_REASON_RESERVED, detail.reason);
    memset(blocked_output, 0x6du, capacity);
    written = 77u;
    SDK_CHECK_STATUS("sdk.state.oom.rejection-keeps-fault-latched",
                     GN_STATUS_INVALID_STATE,
        gn_state_capture_v1(target, blocked_output, capacity, &written,
                            &detail, sizeof(detail)));
    SDK_CHECK_U64("sdk.state.oom.rejected-restore-keeps-fault-reason",
                  GN_STATE_REASON_GUEST_FAULT, detail.reason);
    SDK_CHECK_U64("sdk.state.oom.rejected-restore-keeps-output-untouched",
                  0x6du, blocked_output[0]);

    SDK_CHECK_TRUE("sdk.state.oom.healthy-restore-recovers-known-fault",
                   state_fixture_restore(target, baseline, capacity));
    state_fixture_observation expected;
    state_fixture_observation actual;
    SDK_CHECK_TRUE("sdk.state.oom.fault-recovery-witness-advance",
        state_fixture_advance(witness, GN_MVS_INPUT_P1_A, &expected));
    SDK_CHECK_TRUE("sdk.state.oom.fault-recovery-target-advance",
        state_fixture_advance(target, GN_MVS_INPUT_P1_A, &actual));
    SDK_CHECK_TRUE("sdk.state.oom.fault-recovery-continuation-equal",
        state_fixture_observation_equal(&expected, &actual));
    SDK_CHECK_TRUE("sdk.state.oom.fault-recovery-owner-retained",
                  target_owner == gn_test_mvs_save_ram_address(target));
    SDK_CHECK_TRUE("sdk.state.oom.fault-recovery-peer-owner-retained",
                  witness_owner == gn_test_mvs_save_ram_address(witness));

cleanup:
    free(malformed);
    free(blocked_output);
    free(baseline);
    gn_destroy(witness);
    gn_destroy(target);
}

void state_mutation_oom_red_test(void) {
    SDK_CASE("sdk.state.oom.aggregate-restore-allocation-sweep");
    gn_instance *target = NULL;
    gn_instance *witness = NULL;
    uint8_t *state = NULL;
    size_t state_size = 0u;
    gn_test_state_failpoint_info allocations;
    restore_operation operation;
    size_t ym_points = 0u;
    size_t ym_bytes = 0u;
    size_t ym_high_water = 0u;
    int64_t ym_lifetime = 0;
    uint32_t ym_failed_site = 0u;
    int operation_result = -99;
    size_t z80_attempts = 0u;
    size_t z80_high_water = 0u;
    gn_test_state_resources resources = {0};
    size_t measured_aggregate = 0u;
    size_t ym_site_failures[8] = {0u};
    uintptr_t target_owner = 0u;
    uintptr_t peer_owner = 0u;
    clock_t latency_start = (clock_t)-1;
    clock_t latency_end = (clock_t)-1;

    SDK_CHECK_TRUE("sdk.state.oom.target-load", state_fixture_load(&target, 0u));
    SDK_CHECK_TRUE("sdk.state.oom.independent-witness-load",
                   state_fixture_load(&witness, 0u));
    if (target == NULL || witness == NULL) goto cleanup;
    SDK_CHECK_TRUE("sdk.state.oom.capture", state_fixture_capture(
        target, &state, &state_size));
    if (state == NULL) goto cleanup;
    target_owner = gn_test_mvs_save_ram_address(target);
    peer_owner = gn_test_mvs_save_ram_address(witness);
    SDK_CHECK_TRUE("sdk.state.oom.distinct-live-owner-witnesses",
        target_owner != (uintptr_t)0 && peer_owner != (uintptr_t)0 &&
        target_owner != peer_owner);
    SDK_CHECK_TRUE("sdk.state.oom.witness-baseline-restore",
                   state_fixture_restore(witness, state, state_size));

    /* Measure the public import first to enumerate the real C and C++ sites. */
    operation = (restore_operation){target, state, state_size, {0}};
    SDK_CHECK_STATUS("sdk.state.oom.arm-c-measurement", GN_STATUS_OK,
                     gn_test_state_failpoint_arm(target, 0u));
    latency_start = clock();
    SDK_CHECK_STATUS("sdk.state.oom.run-through-real-import", YM2610_CANDIDATE_OK,
        ym2610_candidate_test_invoke_with_failpoint(
            invoke_restore, &operation, SIZE_MAX, &operation_result,
            &ym_points, &ym_lifetime, &ym_bytes, &ym_high_water,
            &ym_failed_site));
    latency_end = clock();
    SDK_CHECK_STATUS("sdk.state.oom.import-succeeds-without-failure", GN_STATUS_OK,
                     (gn_status)operation_result);
    SDK_CHECK_STATUS("sdk.state.oom.disarm-c-measurement", GN_STATUS_OK,
                     gn_test_state_failpoint_disarm(target));
    SDK_CHECK_STATUS("sdk.state.oom.read-c-allocation-ownership", GN_STATUS_OK,
                     gn_test_state_failpoint_read(target, &allocations));
    z80_attempts = allocations.attempts;
    z80_high_water = allocations.high_water_bytes;
    SDK_CHECK_U64("sdk.state.oom.two-real-z80-allocation-sites", 2u,
                  z80_attempts);
    SDK_CHECK_TRUE("sdk.state.oom.c-success-keeps-one-replacement-owner",
                   allocations.allocations == allocations.frees + 1u);
    SDK_CHECK_TRUE("sdk.state.oom.c-success-live-bytes-bounded",
                   allocations.live_bytes > 0u &&
                   allocations.live_bytes <= allocations.high_water_bytes);
    SDK_CHECK_TRUE("sdk.state.oom.ym-construction-sites-reached",
                   ym_points > 0u && ym_high_water > 0u && ym_bytes > 0u);
    SDK_CHECK_STATUS("sdk.state.resources.derived-profile-bound", GN_STATUS_OK,
                     gn_test_state_resources_read(target, &resources));
    SDK_CHECK_U64("sdk.state.resources.trusted-input-size", state_size,
                  resources.input_bytes);
    SDK_CHECK_U64("sdk.state.resources.full-success-byte-charge",
                  resources.byte_work_limit, resources.byte_work);
    SDK_CHECK_U64("sdk.state.resources.full-success-fixed-phases", 9u,
                  resources.phases);
    SDK_CHECK_U64("sdk.state.resources.derived-z80-requested-peak",
                  z80_candidate_state_heap_bound(), z80_high_water);
    SDK_CHECK_U64("sdk.state.resources.derived-ym-requested-peak",
                  ym2610_candidate_state_heap_bound(), ym_high_water);
    SDK_CHECK_U64("sdk.state.resources.derived-ym-construction-count",
                  ym2610_candidate_state_allocation_bound(), ym_points);
    measured_aggregate = resources.stack_staging_bytes + z80_high_water +
                         ym_high_water;
    SDK_CHECK_TRUE("sdk.state.resources.aggregate-requested-peak-bounded",
                   measured_aggregate <= resources.staging_bytes);
    SDK_CHECK_U64("sdk.state.oom.no-c-failed-site-on-success", 0u,
                  allocations.failed_site);
    SDK_CHECK_U64("sdk.state.oom.no-ym-failed-site-on-success", 0u,
                  ym_failed_site);

    state_fixture_observation expected;
    state_fixture_observation actual;
    SDK_CHECK_TRUE("sdk.state.oom.success-witness-advance",
                   state_fixture_advance(witness, GN_MVS_INPUT_P1_A,
                                         &expected));
    SDK_CHECK_TRUE("sdk.state.oom.success-target-advance",
                   state_fixture_advance(target, GN_MVS_INPUT_P1_A, &actual));
    SDK_CHECK_TRUE("sdk.state.oom.success-continuation-equal",
                   state_fixture_observation_equal(&expected, &actual));
    SDK_CHECK_TRUE("sdk.state.oom.success-target-owner-retained",
                  target_owner == gn_test_mvs_save_ram_address(target));
    SDK_CHECK_TRUE("sdk.state.oom.success-peer-owner-retained",
                  peer_owner == gn_test_mvs_save_ram_address(witness));

    /* Fail each actual C allocation: stage-state then replacement CPU. */
    for (size_t fail_at = 1u; fail_at <= z80_attempts; ++fail_at) {
        SDK_CASE(fail_at == 1u ? "sdk.state.oom.z80-stage-state"
                               : "sdk.state.oom.z80-create-replacement");
        SDK_CHECK_TRUE("sdk.state.oom.c-target-baseline-before-failure",
                       state_fixture_restore(target, state, state_size));
        SDK_CHECK_TRUE("sdk.state.oom.c-witness-baseline-before-failure",
                       state_fixture_restore(witness, state, state_size));
        SDK_CHECK_STATUS("sdk.state.oom.arm-c-site", GN_STATUS_OK,
                         gn_test_state_failpoint_arm(target, fail_at));
        ym_points = 0u; ym_lifetime = 0; ym_bytes = 0u;
        ym_high_water = 0u; ym_failed_site = 0u; operation_result = -99;
        SDK_CHECK_STATUS("sdk.state.oom.scope-real-c-import", YM2610_CANDIDATE_OK,
            ym2610_candidate_test_invoke_with_failpoint(
                invoke_restore, &operation, SIZE_MAX, &operation_result,
                &ym_points, &ym_lifetime, &ym_bytes, &ym_high_water,
                &ym_failed_site));
        SDK_CHECK_STATUS("sdk.state.oom.c-injected-site-returns-oom",
                         GN_STATUS_OUT_OF_MEMORY,
                         (gn_status)operation_result);
        SDK_CHECK_STATUS("sdk.state.oom.disarm-c-site", GN_STATUS_OK,
                         gn_test_state_failpoint_disarm(target));
        SDK_CHECK_STATUS("sdk.state.oom.read-c-failure-ownership", GN_STATUS_OK,
                         gn_test_state_failpoint_read(target, &allocations));
        SDK_CHECK_U64("sdk.state.oom.c-attempt-index", fail_at,
                      allocations.attempts);
        SDK_CHECK_U64("sdk.state.oom.c-exact-failed-site", fail_at,
                      allocations.failed_site);
        SDK_CHECK_TRUE("sdk.state.resources.c-oom-aggregate-bounded",
            resources.stack_staging_bytes + allocations.high_water_bytes +
                ym_high_water <= resources.staging_bytes);
        SDK_CHECK_U64("sdk.state.oom.c-failure-unwinds-count", 0u,
                      allocations.allocations - allocations.frees);
        SDK_CHECK_U64("sdk.state.oom.c-failure-unwinds-live-bytes", 0u,
                      allocations.live_bytes);
        if (fail_at == 1u)
            SDK_CHECK_U64("sdk.state.oom.first-site-fails-before-allocation",
                          0u, allocations.high_water_bytes);
        else
            SDK_CHECK_TRUE("sdk.state.oom.c-failure-high-water-bounded",
                           allocations.high_water_bytes > 0u &&
                           allocations.high_water_bytes <= z80_high_water);
        SDK_CHECK_U64("sdk.state.oom.ym-partial-construction-unwinds", 0u,
                      (uint64_t)(ym_lifetime < 0 ? -ym_lifetime : ym_lifetime));
        if (fail_at == 1u)
            SDK_CHECK_U64("sdk.state.oom.stage-does-not-reach-ym", 0u,
                          ym_points);
        else
            SDK_CHECK_TRUE("sdk.state.oom.reconstruction-reaches-ym",
                           ym_points > 0u && ym_bytes > 0u);
        SDK_CHECK_TRUE("sdk.state.oom.c-failure-witness-equal",
            state_fixture_advance(witness, GN_MVS_INPUT_P1_A, &expected) &&
            state_fixture_advance(target, GN_MVS_INPUT_P1_A, &actual) &&
            state_fixture_observation_equal(&expected, &actual));
        SDK_CHECK_TRUE("sdk.state.oom.c-failure-target-owner",
                      target_owner == gn_test_mvs_save_ram_address(target));
        SDK_CHECK_TRUE("sdk.state.oom.c-failure-peer-owner",
                      peer_owner == gn_test_mvs_save_ram_address(witness));
    }

    /* Restore uses real YM candidate/channel/operator allocations. Vector
     * growth is capture-only and must not be reported as an import allocation. */
    SDK_CHECK_TRUE("sdk.state.oom.ym-target-baseline-before-measurement",
                   state_fixture_restore(target, state, state_size));
    SDK_CHECK_TRUE("sdk.state.oom.ym-witness-baseline-before-measurement",
                   state_fixture_restore(witness, state, state_size));
    operation = (restore_operation){target, state, state_size, {0}};
    SDK_CHECK_STATUS("sdk.state.oom.measure-ym-import", YM2610_CANDIDATE_OK,
        ym2610_candidate_test_invoke_with_failpoint(
            invoke_restore, &operation, SIZE_MAX, &operation_result,
            &ym_points, &ym_lifetime, &ym_bytes, &ym_high_water,
            &ym_failed_site));
    SDK_CHECK_STATUS("sdk.state.oom.ym-measure-import-succeeds", GN_STATUS_OK,
                     (gn_status)operation_result);
    const size_t measured_ym_points = ym_points;
    SDK_CHECK_TRUE("sdk.state.oom.ym-point-count-bounded",
                   measured_ym_points > 0u && measured_ym_points < 1024u);
    SDK_CHECK_U64("sdk.state.oom.ym-success-failure-site-none", 0u,
                  ym_failed_site);
    SDK_CHECK_TRUE("sdk.state.oom.ym-success-high-water-recorded",
                   ym_high_water > 0u && ym_bytes > 0u);
    SDK_CHECK_U64("sdk.state.oom.ym-success-net-owned-objects", 0u,
                  (uint64_t)(ym_lifetime < 0 ? -ym_lifetime : ym_lifetime));
    for (size_t fail_at = 0u; fail_at < measured_ym_points; ++fail_at) {
        SDK_CASE("sdk.state.oom.ym-construction-site");
        SDK_CHECK_TRUE("sdk.state.oom.ym-target-baseline-before-failure",
                       state_fixture_restore(target, state, state_size));
        SDK_CHECK_TRUE("sdk.state.oom.ym-witness-baseline-before-failure",
                       state_fixture_restore(witness, state, state_size));
        SDK_CHECK_STATUS("sdk.state.oom.ym-disable-c-failpoint", GN_STATUS_OK,
                         gn_test_state_failpoint_disarm(target));
        ym_points = 0u; ym_lifetime = 0; ym_bytes = 0u;
        ym_high_water = 0u; ym_failed_site = 0u; operation_result = -99;
        SDK_CHECK_STATUS("sdk.state.oom.scope-ym-allocation-failure",
                         YM2610_CANDIDATE_OK,
            ym2610_candidate_test_invoke_with_failpoint(
                invoke_restore, &operation, fail_at, &operation_result,
                &ym_points, &ym_lifetime, &ym_bytes, &ym_high_water,
                &ym_failed_site));
        SDK_CHECK_STATUS("sdk.state.oom.ym-injected-site-returns-oom",
                         GN_STATUS_OUT_OF_MEMORY,
                         (gn_status)operation_result);
        SDK_CHECK_U64("sdk.state.oom.ym-failure-at-index", fail_at + 1u,
                      ym_points);
        SDK_CHECK_TRUE("sdk.state.oom.ym-failure-site-is-real-constructor",
                       ym_failed_site >= 1u && ym_failed_site <= 7u &&
                       ym_failed_site != 5u && ym_failed_site != 6u);
        ++ym_site_failures[ym_failed_site];
        SDK_CHECK_TRUE("sdk.state.resources.ym-oom-requested-peak-bounded",
            ym_high_water <= ym2610_candidate_state_heap_bound());
        SDK_CHECK_TRUE("sdk.state.resources.ym-oom-aggregate-bounded",
            resources.stack_staging_bytes + z80_high_water + ym_high_water <=
                resources.staging_bytes);
        SDK_CHECK_U64("sdk.state.oom.ym-partial-construction-unwinds", 0u,
                      (uint64_t)(ym_lifetime < 0 ? -ym_lifetime : ym_lifetime));
        SDK_CHECK_TRUE("sdk.state.oom.ym-failure-high-water-bounded",
                       ym_high_water <= ym_bytes);
        SDK_CHECK_TRUE("sdk.state.oom.ym-failure-witness-equal",
            state_fixture_advance(witness, GN_MVS_INPUT_P1_A, &expected) &&
            state_fixture_advance(target, GN_MVS_INPUT_P1_A, &actual) &&
            state_fixture_observation_equal(&expected, &actual));
        SDK_CHECK_TRUE("sdk.state.oom.ym-failure-target-owner",
                      target_owner == gn_test_mvs_save_ram_address(target));
        SDK_CHECK_TRUE("sdk.state.oom.ym-failure-peer-owner",
                      peer_owner == gn_test_mvs_save_ram_address(witness));
    }

    state_mutation_fault_recovery_test();

    SDK_CHECK_TRUE("sdk.state.oom.final-target-baseline",
                   state_fixture_restore(target, state, state_size));
    SDK_CHECK_TRUE("sdk.state.oom.final-witness-baseline",
                   state_fixture_restore(witness, state, state_size));
    SDK_CHECK_STATUS("sdk.state.oom.final-c-measurement", GN_STATUS_OK,
                     gn_test_state_failpoint_arm(target, 0u));
    operation = (restore_operation){target, state, state_size, {0}};
    SDK_CHECK_STATUS("sdk.state.oom.final-clean-ym-scope", YM2610_CANDIDATE_OK,
        ym2610_candidate_test_invoke_with_failpoint(
            invoke_restore, &operation, SIZE_MAX, &operation_result,
            &ym_points, &ym_lifetime, &ym_bytes, &ym_high_water,
            &ym_failed_site));
    SDK_CHECK_STATUS("sdk.state.oom.success-after-full-sweep", GN_STATUS_OK,
                     (gn_status)operation_result);
    SDK_CHECK_STATUS("sdk.state.oom.disarm-final-c-measurement", GN_STATUS_OK,
                     gn_test_state_failpoint_disarm(target));
    SDK_CHECK_STATUS("sdk.state.oom.read-final-c-ownership", GN_STATUS_OK,
                     gn_test_state_failpoint_read(target, &allocations));
    SDK_CHECK_U64("sdk.state.oom.final-c-sites-repeat-measurement",
                  z80_attempts, allocations.attempts);
    SDK_CHECK_TRUE("sdk.state.oom.final-live-replacement-observed",
                   allocations.live_bytes > 0u && allocations.live_bytes <=
                       allocations.high_water_bytes);
    SDK_CHECK_TRUE("sdk.state.oom.final-continuation-equal",
        state_fixture_advance(witness, GN_MVS_INPUT_P1_A, &expected) &&
        state_fixture_advance(target, GN_MVS_INPUT_P1_A, &actual) &&
        state_fixture_observation_equal(&expected, &actual));
    SDK_CHECK_STATUS("sdk.state.oom.unload-successful-replacement", GN_STATUS_OK,
                     gn_unload(target));
    SDK_CHECK_STATUS("sdk.state.oom.read-post-unload-c-ownership", GN_STATUS_OK,
                     gn_test_state_failpoint_read(target, &allocations));
    SDK_CHECK_U64("sdk.state.oom.successful-replacement-eventually-freed", 0u,
                  allocations.allocations - allocations.frees);
    SDK_CHECK_U64("sdk.state.oom.successful-replacement-live-bytes-cleared", 0u,
                  allocations.live_bytes);

    const double host_latency_ns = latency_start != (clock_t)-1 &&
            latency_end != (clock_t)-1 && latency_end >= latency_start
        ? ((double)(latency_end - latency_start) * 1000000000.0) /
              (double)CLOCKS_PER_SEC
        : 0.0;
    (void)printf("SDK_STATE_RESOURCE_BOUND input_bytes=%zu stack_staging_bytes=%zu "
                 "heap_staging_bytes=%zu aggregate_staging_bytes=%zu "
                 "measured_aggregate_upper_bytes=%zu byte_work_limit=%zu "
                 "fixed_phase_limit=%zu\n", resources.input_bytes,
        resources.stack_staging_bytes, resources.heap_staging_bytes,
        resources.staging_bytes, measured_aggregate, resources.byte_work_limit,
        resources.phase_limit);
    (void)printf("SDK_STATE_RESTORE_METRICS source=%s config=%s compiler=%s-%s "
                 "fixture=public_sound_guest-v1 payload_bytes=%zu "
                 "outer_parser_alloc_sites=0 cpu_state_alloc_sites=0 "
                 "z80_sites=%zu z80_high_water_bytes=%zu "
                 "ym_points=%zu ym_requested_bytes=%zu ym_high_water_bytes=%zu "
                 "ym_sites=%zu,%zu,%zu,%zu,%zu,%zu,%zu "
                 "host_cpu_latency_ns=%.0f emulated_time_unit=guest_cycles\n",
        GLUEYNEO_SOURCE_REVISION, GLUEYNEO_CONFIGURATION,
        GLUEYNEO_COMPILER_ID, GLUEYNEO_COMPILER_VERSION,
        state_size, z80_attempts, z80_high_water, measured_ym_points,
        ym_bytes, ym_high_water, ym_site_failures[1], ym_site_failures[2],
        ym_site_failures[3], ym_site_failures[4], ym_site_failures[5],
        ym_site_failures[6], ym_site_failures[7], host_latency_ns);

cleanup:
    free(state);
    gn_destroy(witness);
    gn_destroy(target);
}
