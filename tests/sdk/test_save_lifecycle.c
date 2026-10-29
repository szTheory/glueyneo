/* SPDX-License-Identifier: MIT */
#include "save_fixture.h"
#include "test_support.h"
#include "chips/ym2610_candidate.h"

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

static int invalid_suite;
static const uint8_t saved_a[SAVE_FIXTURE_OUTPUT_COUNT] = {
    0x12u, 0x34u, 0x56u, 0x78u, 0x9au, 0xbcu
};
static const uint8_t saved_b[SAVE_FIXTURE_OUTPUT_COUNT] = {
    0xa1u, 0xb2u, 0xc3u, 0xd4u, 0xe5u, 0xf6u
};

void setUp(void) {}
void tearDown(void) {}

static int lifecycle_state_equal(gn_instance *instance,
                                const uint8_t *expected,
                                size_t expected_size) {
    uint8_t *actual = NULL;
    size_t actual_size = 0u;
    const int captured = save_fixture_capture(instance, &actual, &actual_size);
    const int equal = captured != 0 && actual_size == expected_size &&
        memcmp(actual, expected, expected_size) == 0;
    free(actual);
    return equal;
}

typedef struct {
    gn_instance *instance;
    const uint8_t *state;
    size_t state_size;
} lifecycle_restore_operation;

static int lifecycle_invoke_restore(void *raw) {
    lifecycle_restore_operation *operation =
        (lifecycle_restore_operation *)raw;
    gn_state_detail_v1 detail;
    return (int)gn_state_restore_v1(
        operation->instance, operation->state, operation->state_size,
        &detail, sizeof(detail));
}

static gn_status lifecycle_export(gn_instance *instance,
                                  gn_mvs_save_receipt_v1 *out_receipt) {
    uint8_t *envelope = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    if (envelope == NULL) return GN_STATUS_OUT_OF_MEMORY;
    size_t written = 0u;
    gn_mvs_save_detail_v1 detail;
    const gn_status status = save_fixture_export(
        instance, envelope, GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written,
        out_receipt, &detail);
    if (status != GN_STATUS_OK) {
        (void)fprintf(stderr, "lifecycle export failed status=%u reason=%u\n",
                      (unsigned)status, (unsigned)detail.reason);
    }
    free(envelope);
    return status;
}

static gn_status lifecycle_ack(gn_instance *instance,
                               const gn_mvs_save_receipt_v1 *receipt) {
    gn_mvs_save_detail_v1 detail;
    return gn_mvs_save_ack_v1(instance, receipt, sizeof(*receipt), &detail,
                              sizeof(detail));
}

static int lifecycle_pending(const gn_instance *instance) {
    gn_mvs_save_info_v1 info;
    gn_mvs_save_detail_v1 detail;
    return save_fixture_query(instance, &info, &detail) == GN_STATUS_OK &&
        info.dirty != 0u;
}

static void lifecycle_repeated_baseline_import_before_guest(void) {
    SDK_CASE("save.lifecycle.repeated-baseline-import-before-guest");
    gn_instance *target = NULL;
    gn_instance *producer = NULL;
    uint8_t *envelope_a = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    uint8_t *envelope_b = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    size_t written = 0u;
    uint8_t sram[SAVE_FIXTURE_OUTPUT_COUNT];
    gn_mvs_save_receipt_v1 receipt;
    gn_mvs_save_detail_v1 detail;
    gn_mvs_save_info_v1 info;

    SDK_CHECK_TRUE("save.lifecycle.target-load", save_fixture_load(&target));
    SDK_CHECK_TRUE("save.lifecycle.producer-load",
                   save_fixture_load(&producer));
    SDK_CHECK_TRUE("save.lifecycle.envelopes-allocated",
                   envelope_a != NULL && envelope_b != NULL);
    if (target == NULL || producer == NULL || envelope_a == NULL ||
        envelope_b == NULL) goto cleanup;

    SDK_CHECK_STATUS("save.lifecycle.target-scope", GN_STATUS_OK,
                     save_fixture_scope(target, 61u, &detail));
    SDK_CHECK_STATUS("save.lifecycle.producer-scope", GN_STATUS_OK,
                     save_fixture_scope(producer, 62u, &detail));
    SDK_CHECK_TRUE("save.lifecycle.producer-a-run",
                   save_fixture_run_guest(producer, GN_MVS_INPUT_P1_A));
    SDK_CHECK_TRUE("save.lifecycle.producer-a-readback",
                   save_fixture_read_sram(producer, sram) &&
                   memcmp(sram, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.lifecycle.export-a", GN_STATUS_OK,
                     save_fixture_export(producer, envelope_a,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         &detail));
    SDK_CHECK_U64("save.lifecycle.export-a-size",
                  GN_MVS_SAVE_ENVELOPE_V1_BYTES, written);

    SDK_CHECK_TRUE("save.lifecycle.producer-reload",
                   save_fixture_reload(producer));
    SDK_CHECK_TRUE("save.lifecycle.producer-b-run",
                   save_fixture_run_guest(producer, GN_MVS_INPUT_P1_B));
    SDK_CHECK_TRUE("save.lifecycle.producer-b-readback",
                   save_fixture_read_sram(producer, sram) &&
                   memcmp(sram, saved_b, sizeof(saved_b)) == 0);
    SDK_CHECK_STATUS("save.lifecycle.export-b", GN_STATUS_OK,
                     save_fixture_export(producer, envelope_b,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         &detail));
    SDK_CHECK_U64("save.lifecycle.export-b-size",
                  GN_MVS_SAVE_ENVELOPE_V1_BYTES, written);

    SDK_CHECK_STATUS("save.lifecycle.first-pre-execution-import",
                     GN_STATUS_OK,
                     gn_mvs_save_import_baseline_v1(target, envelope_a,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &detail,
                         sizeof(detail)));
    SDK_CHECK_TRUE("save.lifecycle.first-import-a-bytes",
                   save_fixture_read_sram(target, sram) &&
                   memcmp(sram, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.lifecycle.repeated-pre-execution-import",
                     GN_STATUS_OK,
                     gn_mvs_save_import_baseline_v1(target, envelope_b,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &detail,
                         sizeof(detail)));
    SDK_CHECK_TRUE("save.lifecycle-repeated-import-b-bytes",
                   save_fixture_read_sram(target, sram) &&
                   memcmp(sram, saved_b, sizeof(saved_b)) == 0);
    SDK_CHECK_STATUS("save.lifecycle.query-after-repeated-import",
                     GN_STATUS_OK,
                     save_fixture_query(target, &info, &detail));
    SDK_CHECK_U64("save.lifecycle-repeated-import-keeps-startup-open", 1u,
                  info.startup_import_allowed);
    SDK_CHECK_U64("save.lifecycle-repeated-import-baseline-known", 1u,
                  info.baseline_known);

    SDK_CHECK_TRUE("save.lifecycle.target-first-guest-run",
                   save_fixture_run_guest(target, GN_MVS_INPUT_P1_A));
    SDK_CHECK_TRUE("save.lifecycle.target-guest-replaces-sram",
                   save_fixture_read_sram(target, sram) &&
                   memcmp(sram, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.lifecycle.query-after-first-guest", GN_STATUS_OK,
                     save_fixture_query(target, &info, &detail));
    SDK_CHECK_U64("save.lifecycle-first-guest-closes-startup", 0u,
                  info.startup_import_allowed);
    SDK_CHECK_STATUS("save.lifecycle.reset-after-first-guest", GN_STATUS_OK,
                     gn_reset(target));
    SDK_CHECK_STATUS("save.lifecycle.query-after-reset", GN_STATUS_OK,
                     save_fixture_query(target, &info, &detail));
    SDK_CHECK_U64("save.lifecycle-reset-does-not-reopen-startup", 0u,
                  info.startup_import_allowed);
    SDK_CHECK_STATUS("save.lifecycle.import-after-guest-closed",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_import_baseline_v1(target, envelope_a,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &detail,
                         sizeof(detail)));
    SDK_CHECK_U64("save.lifecycle.import-after-guest-reason",
                  GN_MVS_SAVE_REASON_STARTUP_CLOSED, detail.reason);

cleanup:
    free(envelope_a);
    free(envelope_b);
    gn_destroy(target);
    gn_destroy(producer);
}

static void lifecycle_reset_watchdog_and_fault_retain_pending_save(void) {
    SDK_CASE("save.lifecycle.reset-watchdog-fault-retain-pending");
    gn_instance *instance = NULL;
    gn_mvs_save_receipt_v1 receipt;
    gn_mvs_save_detail_v1 detail;
    gn_mvs_save_info_v1 info;
    gn_test_mvs_machine_state machine_before;
    gn_test_mvs_machine_state machine_after;
    gn_test_save_observation save_before_watchdog;
    gn_test_save_observation save_after_watchdog;
    uint8_t sram[SAVE_FIXTURE_OUTPUT_COUNT];
    uint8_t *envelope = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    size_t envelope_written = 0u;
    gn_run_result run;

    SDK_CHECK_TRUE("save.lifecycle-retain.load", save_fixture_load(&instance));
    if (instance == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.lifecycle-retain.scope", GN_STATUS_OK,
                     save_fixture_scope(instance, 71u, &detail));
    SDK_CHECK_TRUE("save.lifecycle-retain.guest-a",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_TRUE("save.lifecycle-retain.envelope-allocation",
                   envelope != NULL);
    if (envelope == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.lifecycle-retain.export-a", GN_STATUS_OK,
                     save_fixture_export(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &envelope_written,
                         &receipt, &detail));
    SDK_CHECK_STATUS("save.lifecycle-retain.reset", GN_STATUS_OK,
                     gn_reset(instance));
    SDK_CHECK_TRUE("save.lifecycle-retain.reset-bytes",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_TRUE("save.lifecycle-retain.reset-pending",
                   lifecycle_pending(instance));
    SDK_CHECK_STATUS("save.lifecycle-retain.reset-query", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.lifecycle-retain.reset-startup-stays-closed", 0u,
                  info.startup_import_allowed);
    SDK_CHECK_STATUS("save.lifecycle-retain.reset-import-stays-closed",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_import_baseline_v1(instance, envelope,
                         envelope_written, &detail, sizeof(detail)));
    SDK_CHECK_U64("save.lifecycle-retain.reset-import-reason",
                  GN_MVS_SAVE_REASON_STARTUP_CLOSED, detail.reason);
    SDK_CHECK_STATUS("save.lifecycle-retain.reset-receipt-still-eligible",
                     GN_STATUS_OK, lifecycle_ack(instance, &receipt));
    SDK_CHECK_STATUS("save.lifecycle-retain.clean-after-ack-query", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.lifecycle-retain.ack-clears-dirty", 0u, info.dirty);
    SDK_CHECK_STATUS("save.lifecycle-retain.clean-after-ack-import-stays-closed",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_import_baseline_v1(instance, envelope,
                         envelope_written, &detail, sizeof(detail)));
    SDK_CHECK_U64("save.lifecycle-retain.clean-after-ack-startup-reason",
                  GN_MVS_SAVE_REASON_STARTUP_CLOSED, detail.reason);

    SDK_CHECK_TRUE("save.lifecycle-retain.guest-b",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_B));
    SDK_CHECK_STATUS("save.lifecycle-retain.export-b", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));
    SDK_CHECK_STATUS("save.lifecycle-retain.save-lineage-before-watchdog",
                     GN_STATUS_OK,
                     gn_test_save_observe(instance, &save_before_watchdog));
    SDK_CHECK_TRUE("save.lifecycle-retain.machine-before-watchdog",
                   gn_test_mvs_machine_state_read(instance, &machine_before) ==
                       GN_STATUS_OK &&
                   machine_before.watchdog_remaining_cycles > 0u);
    memset(&run, 0, sizeof(run));
    gn_status watchdog_status = GN_STATUS_OK;
    unsigned watchdog_calls = 0u;
    do {
        SDK_CHECK_TRUE("save.lifecycle-retain.watchdog-budget-state",
                       gn_test_mvs_machine_state_read(instance,
                           &machine_after) == GN_STATUS_OK);
        const uint64_t watchdog_budget =
            machine_after.watchdog_remaining_cycles < GN_MAX_CYCLE_BUDGET
                ? machine_after.watchdog_remaining_cycles
                : GN_MAX_CYCLE_BUDGET;
        watchdog_status = gn_run_mvs(instance, watchdog_budget, &run);
        ++watchdog_calls;
        if (gn_test_mvs_machine_state_read(instance, &machine_after) !=
                GN_STATUS_OK ||
            machine_after.watchdog_reset_count >
                machine_before.watchdog_reset_count)
            break;
    } while (watchdog_calls < 4u);
    SDK_CHECK_STATUS("save.lifecycle-retain.actual-watchdog", GN_STATUS_OK,
                     watchdog_status);
    SDK_CHECK_TRUE("save.lifecycle-retain.watchdog-call-count",
                   watchdog_calls >= 2u && watchdog_calls <= 4u);
    SDK_CHECK_TRUE("save.lifecycle-retain.watchdog-reset-observed",
                   gn_test_mvs_machine_state_read(instance, &machine_after) ==
                       GN_STATUS_OK &&
                   machine_after.watchdog_reset_count >
                       machine_before.watchdog_reset_count);
    SDK_CHECK_TRUE("save.lifecycle-retain.watchdog-keeps-b",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, saved_b, sizeof(saved_b)) == 0);
    SDK_CHECK_TRUE("save.lifecycle-retain.watchdog-keeps-pending",
                   lifecycle_pending(instance));
    SDK_CHECK_STATUS("save.lifecycle-retain.watchdog-query", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.lifecycle-retain.watchdog-keeps-startup-closed", 0u,
                  info.startup_import_allowed);
    SDK_CHECK_STATUS("save.lifecycle-retain.save-lineage-after-watchdog",
                     GN_STATUS_OK,
                     gn_test_save_observe(instance, &save_after_watchdog));
    SDK_CHECK_U64("save.lifecycle-retain.watchdog-mutation-sequence-stable",
                  save_before_watchdog.mutation_sequence,
                  save_after_watchdog.mutation_sequence);
    SDK_CHECK_STATUS("save.lifecycle-retain.watchdog-receipt-eligible",
                     GN_STATUS_OK, lifecycle_ack(instance, &receipt));

    SDK_CHECK_STATUS("save.lifecycle-retain.reset-before-faulted-a",
                     GN_STATUS_OK, gn_reset(instance));
    SDK_CHECK_TRUE("save.lifecycle-retain.guest-a-for-fault",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_STATUS("save.lifecycle-retain.export-before-fault", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));
    SDK_CHECK_STATUS("save.lifecycle-retain.arm-main-fault", GN_STATUS_OK,
                     gn_test_mvs_set_failure(instance,
                         GN_TEST_MVS_FAILURE_MAIN_AFTER_INSTRUCTION));
    memset(&run, 0, sizeof(run));
    SDK_CHECK_STATUS("save.lifecycle-retain.inject-main-fault",
                     GN_STATUS_CPU_FAILURE,
                     gn_run_mvs(instance, UINT64_C(5000), &run));
    SDK_CHECK_TRUE("save.lifecycle-retain.faulted-machine-pending",
                   lifecycle_pending(instance));
    SDK_CHECK_STATUS("save.lifecycle-retain.faulted-machine-export-recovery",
                     GN_STATUS_OK, lifecycle_export(instance, &receipt));
    SDK_CHECK_TRUE("save.lifecycle-retain.faulted-machine-keeps-a",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.lifecycle-retain.faulted-receipt-eligible",
                     GN_STATUS_OK, lifecycle_ack(instance, &receipt));

cleanup:
    free(envelope);
    gn_destroy(instance);
}

static void lifecycle_checked_discard_and_teardown(void) {
    SDK_CASE("save.lifecycle.checked-discard-and-teardown");
    gn_instance *instance = NULL;
    gn_mvs_save_lifecycle_result_v1 result;
    gn_mvs_save_detail_v1 detail;
    gn_mvs_save_info_v1 info;
    gn_mvs_save_receipt_v1 receipt;
    uint8_t sram[SAVE_FIXTURE_OUTPUT_COUNT];

    SDK_CHECK_TRUE("save.lifecycle-checked.load", save_fixture_load(&instance));
    if (instance == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.lifecycle-checked.scope", GN_STATUS_OK,
                     save_fixture_scope(instance, 72u, &detail));
    SDK_CHECK_TRUE("save.lifecycle-checked.guest-a",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_STATUS("save.lifecycle-checked.export-a", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));
    SDK_CHECK_STATUS("save.lifecycle-checked.require-unload-refuses-pending",
                     GN_STATUS_INVALID_STATE,
                     gn_unload_checked_v1(instance,
                         GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED, 1u,
                         &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.lifecycle-checked.require-unload-reason",
                  GN_MVS_SAVE_REASON_HOST_WORK_PENDING, detail.reason);
    SDK_CHECK_TRUE("save.lifecycle-checked.require-unload-preserves-owner",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, saved_a, sizeof(saved_a)) == 0 &&
                   lifecycle_pending(instance));
    SDK_CHECK_STATUS("save.lifecycle-checked.require-destroy-refuses-pending",
                     GN_STATUS_INVALID_STATE,
                     gn_destroy_checked_v1(&instance,
                         GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED, 1u,
                         &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_TRUE("save.lifecycle-checked.refused-destroy-keeps-pointer",
                   instance != NULL);
    SDK_CHECK_STATUS("save.lifecycle-checked.refused-destroy-receipt-eligible",
                     GN_STATUS_OK, lifecycle_ack(instance, &receipt));

    SDK_CHECK_STATUS("save.lifecycle-checked.reset-before-b", GN_STATUS_OK,
                     gn_reset(instance));
    SDK_CHECK_TRUE("save.lifecycle-checked.guest-b",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_B));
    SDK_CHECK_STATUS("save.lifecycle-checked.require-host-attestation",
                     GN_STATUS_INVALID_STATE,
                     gn_unload_checked_v1(instance,
                         GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED, 0u,
                         &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.lifecycle-checked.export-b", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));
    SDK_CHECK_STATUS("save.lifecycle-checked.allow-unload", GN_STATUS_OK,
                     gn_unload_checked_v1(instance,
                         GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                         &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.lifecycle-checked.unload-reports-discard", 1u,
                  result.discarded_pending);
    SDK_CHECK_STATUS("save.lifecycle-checked.unload-has-no-media",
                     GN_STATUS_INVALID_STATE, gn_reset(instance));

    SDK_CHECK_TRUE("save.lifecycle-checked.reload-after-unload",
                   save_fixture_reload_checked(instance,
                       GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                       &result, &detail) == GN_STATUS_OK);
    SDK_CHECK_U64("save.lifecycle-checked.clean-load-reports-no-discard", 0u,
                  result.discarded_pending);
    SDK_CHECK_STATUS("save.lifecycle-checked.query-clean-new-medium",
                     GN_STATUS_OK, save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.lifecycle-checked.new-medium-no-baseline", 0u,
                  info.baseline_known);
    SDK_CHECK_U64("save.lifecycle-checked.new-medium-startup-open", 1u,
                  info.startup_import_allowed);
    SDK_CHECK_TRUE("save.lifecycle-checked.guest-a-again",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_STATUS("save.lifecycle-checked.export-a-again", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));

    SDK_CHECK_STATUS("save.lifecycle-checked.allow-destroy", GN_STATUS_OK,
                     gn_destroy_checked_v1(&instance,
                         GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                         &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.lifecycle-checked.destroy-reports-discard", 1u,
                  result.discarded_pending);
    SDK_CHECK_TRUE("save.lifecycle-checked.destroy-clears-pointer",
                   instance == NULL);

    SDK_CHECK_TRUE("save.lifecycle-checked.reload-final", save_fixture_load(&instance));
    if (instance == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.lifecycle-checked.final-scope", GN_STATUS_OK,
                     save_fixture_scope(instance, 76u, &detail));
    SDK_CHECK_STATUS("save.lifecycle-checked.final-query", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.lifecycle-checked.final-scope-valid", 1u,
                  info.scope_valid);
    SDK_CHECK_TRUE("save.lifecycle-checked.final-guest-b",
                   gn_reset(instance) == GN_STATUS_OK &&
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_B));
    SDK_CHECK_STATUS("save.lifecycle-checked.final-export", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));
    SDK_CHECK_STATUS("save.lifecycle-checked.require-destroy-clean",
                     GN_STATUS_OK,
                     lifecycle_ack(instance, &receipt));
    SDK_CHECK_STATUS("save.lifecycle-checked.clean-destroy", GN_STATUS_OK,
                     gn_destroy_checked_v1(&instance,
                         GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED, 1u,
                         &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.lifecycle-checked.clean-destroy-no-discard", 0u,
                  result.discarded_pending);
    SDK_CHECK_TRUE("save.lifecycle-checked.clean-destroy-clears-pointer",
                   instance == NULL);

cleanup:
    gn_destroy(instance);
}

static void lifecycle_checked_candidate_oom_is_atomic(void) {
    SDK_CASE("save.lifecycle.checked-candidate-oom-atomic");
    gn_instance *instance = NULL;
    gn_test_allocator allocator;
    gn_test_allocator_init(&allocator);
    gn_mvs_save_lifecycle_result_v1 result;
    gn_mvs_save_detail_v1 detail;
    gn_mvs_save_info_v1 info;
    gn_mvs_save_receipt_v1 receipt;
    uint8_t sram[SAVE_FIXTURE_OUTPUT_COUNT];
    uint8_t *expected_state = NULL;
    size_t expected_state_size = 0u;
    size_t candidate_sites = 0u;
    gn_mvs_manifest_v3 invalid_manifest;

    SDK_CHECK_TRUE("save.lifecycle-candidate.load-with-allocator",
                   save_fixture_load_with_allocator(&allocator, &instance));
    if (instance == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.lifecycle-candidate.scope", GN_STATUS_OK,
                     save_fixture_scope(instance, 73u, &detail));
    SDK_CHECK_TRUE("save.lifecycle-candidate.guest-b",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_B));
    SDK_CHECK_STATUS("save.lifecycle-candidate.export-b", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));
    const uintptr_t owner = gn_test_mvs_save_ram_address(instance);

    SDK_CHECK_STATUS("save.lifecycle-candidate.require-pending-refused",
                     GN_STATUS_INVALID_STATE,
                     save_fixture_reload_checked(instance,
                         GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED, 1u,
                         &result, &detail));
    SDK_CHECK_U64("save.lifecycle-candidate.require-pending-reason",
                  GN_MVS_SAVE_REASON_HOST_WORK_PENDING, detail.reason);
    memset(&invalid_manifest, 0, sizeof(invalid_manifest));
    invalid_manifest.version = UINT32_MAX;
    SDK_CHECK_STATUS("save.lifecycle-candidate.invalid-allow-candidate",
                     GN_STATUS_UNSUPPORTED_PROFILE,
                     gn_load_mvs_v3_checked_v1(instance, &invalid_manifest,
                         GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                         &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.lifecycle-candidate.invalid-reports-no-discard", 0u,
                  result.discarded_pending);
    SDK_CHECK_TRUE("save.lifecycle-candidate.invalid-keeps-old-sram",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, saved_b, sizeof(saved_b)) == 0 &&
                   owner == gn_test_mvs_save_ram_address(instance));

    gn_test_allocator_arm(&allocator, 0u);
    SDK_CHECK_STATUS("save.lifecycle-candidate.measure-success", GN_STATUS_OK,
                     save_fixture_reload_checked(instance,
                         GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                         &result, &detail));
    candidate_sites = allocator.attempts;
    SDK_CHECK_TRUE("save.lifecycle-candidate.nonzero-failpoint-denominator",
                   candidate_sites > 0u);
    SDK_CHECK_U64("save.lifecycle-candidate.measure-reports-discard", 1u,
                  result.discarded_pending);
    gn_test_allocator_disarm(&allocator);

    SDK_CHECK_TRUE("save.lifecycle-candidate.rearm-pending-guest",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_B));
    SDK_CHECK_STATUS("save.lifecycle-candidate.rearm-pending-export", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));
    SDK_CHECK_TRUE("save.lifecycle-candidate.capture-oom-baseline",
                   save_fixture_capture(instance, &expected_state,
                                        &expected_state_size));
    const uintptr_t pending_owner = gn_test_mvs_save_ram_address(instance);
    gn_test_allocator_arm(&allocator, 0u);
    const size_t allocations_before = allocator.live_allocations;
    const size_t bytes_before = allocator.live_bytes;
    gn_test_allocator_disarm(&allocator);

    for (size_t fail_at = 1u; fail_at <= candidate_sites; ++fail_at) {
        gn_test_allocator_arm(&allocator, fail_at);
        const gn_status status = save_fixture_reload_checked(instance,
            GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u, &result, &detail);
        SDK_CHECK_TRUE("save.lifecycle-candidate.failpoint-is-oom",
                       status == GN_STATUS_OUT_OF_MEMORY);
        gn_test_allocator_disarm(&allocator);
        SDK_CHECK_U64("save.lifecycle-candidate.failpoint-no-discard", 0u,
                      result.discarded_pending);
        SDK_CHECK_TRUE("save.lifecycle-candidate.failpoint-state-preserved",
                       lifecycle_state_equal(instance, expected_state,
                                             expected_state_size));
        SDK_CHECK_TRUE("save.lifecycle-candidate.failpoint-sram-preserved",
                       save_fixture_read_sram(instance, sram) &&
                       memcmp(sram, saved_b, sizeof(saved_b)) == 0);
        SDK_CHECK_TRUE("save.lifecycle-candidate.failpoint-owner-preserved",
                       pending_owner == gn_test_mvs_save_ram_address(instance));
        SDK_CHECK_TRUE("save.lifecycle-candidate.failpoint-pending-preserved",
                       lifecycle_pending(instance));
        SDK_CHECK_U64("save.lifecycle-candidate.failpoint-allocation-balance",
                      allocations_before, allocator.live_allocations);
        SDK_CHECK_U64("save.lifecycle-candidate.failpoint-byte-balance",
                      bytes_before, allocator.live_bytes);
    }
    (void)fprintf(stdout,
                  "LIFECYCLE_CANDIDATE_OOM failed_allocations=%zu successful_index=%zu\n",
                  candidate_sites, candidate_sites + 1u);
    SDK_CHECK_STATUS("save.lifecycle-candidate.receipt-eligible-after-sweep",
                     GN_STATUS_OK, lifecycle_ack(instance, &receipt));

    SDK_CHECK_STATUS("save.lifecycle-candidate.reset-before-a", GN_STATUS_OK,
                     gn_reset(instance));
    SDK_CHECK_TRUE("save.lifecycle-candidate.guest-a-after-ack",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_STATUS("save.lifecycle-candidate.export-a-after-ack", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));
    SDK_CHECK_STATUS("save.lifecycle-candidate.discard-commits-after-stage",
                     GN_STATUS_OK,
                     save_fixture_reload_checked(instance,
                         GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                         &result, &detail));
    SDK_CHECK_U64("save.lifecycle-candidate.success-reports-discard", 1u,
                  result.discarded_pending);
    SDK_CHECK_TRUE("save.lifecycle-candidate.success-clears-sram",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, (uint8_t[sizeof(sram)]){0}, sizeof(sram)) == 0);
    SDK_CHECK_STATUS("save.lifecycle-candidate.success-query-new-baseline",
                     GN_STATUS_OK, save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.lifecycle-candidate.success-no-false-baseline", 0u,
                  info.baseline_known);
    SDK_CHECK_U64("save.lifecycle-candidate.success-startup-open", 1u,
                  info.startup_import_allowed);

cleanup:
    free(expected_state);
    gn_destroy(instance);
}

static void lifecycle_restore_rollback_and_staging_oom(void) {
    SDK_CASE("save.lifecycle.restore-rollback-staging-oom");
    gn_instance *instance = NULL;
    gn_instance *probe = NULL;
    gn_mvs_save_detail_v1 save_detail;
    gn_state_detail_v1 state_detail;
    gn_mvs_save_info_v1 info;
    gn_test_save_observation save_observation;
    gn_mvs_save_receipt_v1 receipt_b;
    gn_mvs_save_receipt_v1 receipt_a;
    uint8_t sram[SAVE_FIXTURE_OUTPUT_COUNT];
    uint8_t *state_a = NULL;
    size_t state_a_size = 0u;
    size_t c_points = 0u;
    size_t ym_points = 0u;
    int operation_result = -1;
    int64_t lifetime_balance = 0;
    size_t requested_bytes = 0u;
    size_t high_water_bytes = 0u;
    uint32_t failed_site = 0u;
    gn_test_state_failpoint_info failpoint_info;
    uint8_t *expected_b = NULL;
    size_t expected_b_size = 0u;
    uint8_t *exhausted_envelope = NULL;

    SDK_CHECK_TRUE("save.lifecycle-restore.load", save_fixture_load(&instance));
    if (instance == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.lifecycle-restore.scope", GN_STATUS_OK,
                     save_fixture_scope(instance, 74u, &save_detail));
    SDK_CHECK_TRUE("save.lifecycle-restore.guest-a",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_TRUE("save.lifecycle-restore.capture-a",
                   save_fixture_capture(instance, &state_a, &state_a_size));
    SDK_CHECK_STATUS("save.lifecycle-restore.reset-before-b",
                     GN_STATUS_OK, gn_reset(instance));
    SDK_CHECK_TRUE("save.lifecycle-restore.guest-b",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_B));
    SDK_CHECK_STATUS("save.lifecycle-restore.export-b", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt_b));

    uint8_t *malformed = (uint8_t *)malloc(state_a_size);
    SDK_CHECK_TRUE("save.lifecycle-restore.malformed-buffer", malformed != NULL);
    if (malformed != NULL) {
        memcpy(malformed, state_a, state_a_size);
        malformed[68u] = 1u;
        const uintptr_t owner_before = gn_test_mvs_save_ram_address(instance);
        SDK_CHECK_STATUS("save.lifecycle-restore.reject-malformed",
                         GN_STATUS_INVALID_MEDIA,
                         gn_state_restore_v1(instance, malformed, state_a_size,
                             &state_detail, sizeof(state_detail)));
        SDK_CHECK_TRUE("save.lifecycle-restore.malformed-preserves-b",
                       save_fixture_read_sram(instance, sram) &&
                       memcmp(sram, saved_b, sizeof(saved_b)) == 0 &&
                       lifecycle_pending(instance) &&
                       owner_before == gn_test_mvs_save_ram_address(instance));
        free(malformed);
    }

    SDK_CHECK_TRUE("save.lifecycle-restore.probe-load", save_fixture_load(&probe));
    if (probe == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.lifecycle-restore.probe-c-arm", GN_STATUS_OK,
                     gn_test_state_failpoint_arm(probe, 0u));
    SDK_CHECK_TRUE("save.lifecycle-restore.probe-ym-measure",
                   ym2610_candidate_test_invoke_with_failpoint(
                       lifecycle_invoke_restore,
                       &(lifecycle_restore_operation){probe, state_a,
                                                      state_a_size},
                       SIZE_MAX, &operation_result, &ym_points,
                       &lifetime_balance, &requested_bytes, &high_water_bytes,
                       &failed_site) == YM2610_CANDIDATE_OK &&
                   operation_result == GN_STATUS_OK);
    SDK_CHECK_STATUS("save.lifecycle-restore.probe-c-count", GN_STATUS_OK,
                     gn_test_state_failpoint_read(probe, &failpoint_info));
    c_points = failpoint_info.attempts;
    SDK_CHECK_TRUE("save.lifecycle-restore.c-failpoint-denominator",
                   c_points > 0u);
    SDK_CHECK_TRUE("save.lifecycle-restore.ym-failpoint-denominator",
                   ym_points > 0u);
    SDK_CHECK_STATUS("save.lifecycle-restore.probe-c-disarm", GN_STATUS_OK,
                     gn_test_state_failpoint_disarm(probe));

    const uintptr_t owner_before_sweep = gn_test_mvs_save_ram_address(instance);
    SDK_CHECK_TRUE("save.lifecycle-restore.capture-b-before-sweep",
                   save_fixture_capture(instance, &expected_b,
                                        &expected_b_size));
    for (size_t fail_at = 1u; fail_at <= c_points; ++fail_at) {
        SDK_CHECK_STATUS("save.lifecycle-restore.c-arm", GN_STATUS_OK,
                         gn_test_state_failpoint_arm(instance, fail_at));
        const int invoke_status = (int)ym2610_candidate_test_invoke_with_failpoint(
            lifecycle_invoke_restore,
            &(lifecycle_restore_operation){instance, state_a, state_a_size},
            SIZE_MAX, &operation_result, &ym_points, &lifetime_balance,
            &requested_bytes, &high_water_bytes, &failed_site);
        SDK_CHECK_TRUE("save.lifecycle-restore.c-invoke-wrapper",
                       invoke_status == YM2610_CANDIDATE_OK);
        SDK_CHECK_STATUS("save.lifecycle-restore.c-disarm", GN_STATUS_OK,
                         gn_test_state_failpoint_disarm(instance));
        SDK_CHECK_TRUE("save.lifecycle-restore.c-site-is-oom",
                       operation_result == GN_STATUS_OUT_OF_MEMORY);
        SDK_CHECK_TRUE("save.lifecycle-restore.c-state-preserved",
                       lifecycle_state_equal(instance, expected_b,
                                             expected_b_size));
        SDK_CHECK_TRUE("save.lifecycle-restore.c-sram-preserved",
                       save_fixture_read_sram(instance, sram) &&
                       memcmp(sram, saved_b, sizeof(saved_b)) == 0);
        SDK_CHECK_TRUE("save.lifecycle-restore.c-owner-preserved",
                       owner_before_sweep ==
                           gn_test_mvs_save_ram_address(instance));
        SDK_CHECK_TRUE("save.lifecycle-restore.c-pending-preserved",
                       lifecycle_pending(instance));
    }
    SDK_CHECK_STATUS("save.lifecycle-restore.ym-c-arm", GN_STATUS_OK,
                     gn_test_state_failpoint_arm(instance, 0u));
    for (size_t fail_at = 0u; fail_at < ym_points; ++fail_at) {
        const int invoke_status = (int)ym2610_candidate_test_invoke_with_failpoint(
            lifecycle_invoke_restore,
            &(lifecycle_restore_operation){instance, state_a, state_a_size},
            fail_at, &operation_result, &ym_points, &lifetime_balance,
            &requested_bytes, &high_water_bytes, &failed_site);
        SDK_CHECK_TRUE("save.lifecycle-restore.ym-invoke-wrapper",
                       invoke_status == YM2610_CANDIDATE_OK);
        SDK_CHECK_TRUE("save.lifecycle-restore.ym-site-is-oom",
                       operation_result == GN_STATUS_OUT_OF_MEMORY);
        SDK_CHECK_TRUE("save.lifecycle-restore.ym-state-preserved",
                       lifecycle_state_equal(instance, expected_b,
                                             expected_b_size));
        SDK_CHECK_TRUE("save.lifecycle-restore.ym-sram-preserved",
                       save_fixture_read_sram(instance, sram) &&
                       memcmp(sram, saved_b, sizeof(saved_b)) == 0);
        SDK_CHECK_TRUE("save.lifecycle-restore.ym-owner-preserved",
                       owner_before_sweep ==
                           gn_test_mvs_save_ram_address(instance));
        SDK_CHECK_TRUE("save.lifecycle-restore.ym-pending-preserved",
                       lifecycle_pending(instance));
    }
    SDK_CHECK_STATUS("save.lifecycle-restore.ym-c-disarm", GN_STATUS_OK,
                     gn_test_state_failpoint_disarm(instance));
    (void)fprintf(stdout,
                  "LIFECYCLE_RESTORE_OOM c_allocation_sites=%zu ym_allocation_sites=%zu injected_failures=%zu\n",
                  c_points, ym_points, c_points + ym_points);
    SDK_CHECK_STATUS("save.lifecycle-restore.failed-staging-keeps-receipt",
                     GN_STATUS_OK, lifecycle_ack(instance, &receipt_b));

    SDK_CHECK_STATUS("save.lifecycle-restore.accept-a-rollback", GN_STATUS_OK,
                     gn_state_restore_v1(instance, state_a, state_a_size,
                         &state_detail, sizeof(state_detail)));
    SDK_CHECK_STATUS("save.lifecycle-restore.old-b-receipt-rejected",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(instance, &receipt_b,
                         sizeof(receipt_b), &save_detail, sizeof(save_detail)));
    SDK_CHECK_U64("save.lifecycle-restore.old-b-reason",
                  GN_MVS_SAVE_REASON_STALE_RECEIPT, save_detail.reason);
    SDK_CHECK_TRUE("save.lifecycle-restore.rollback-a-bytes",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.lifecycle-restore.rollback-pending-query",
                     GN_STATUS_OK, save_fixture_query(instance, &info,
                                                       &save_detail));
    SDK_CHECK_U64("save.lifecycle-restore.rollback-remains-pending", 1u,
                  info.dirty);
    SDK_CHECK_STATUS("save.lifecycle-restore.export-a-rollback", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt_a));
    SDK_CHECK_STATUS("save.lifecycle-restore.ack-a-rollback", GN_STATUS_OK,
                     lifecycle_ack(instance, &receipt_a));

    uint8_t *equal_state = NULL;
    size_t equal_state_size = 0u;
    SDK_CHECK_TRUE("save.lifecycle-restore.capture-equal-a",
                   save_fixture_capture(instance, &equal_state,
                                        &equal_state_size));
    SDK_CHECK_STATUS("save.lifecycle-restore.equal-byte-reset-before-b",
                     GN_STATUS_OK, gn_reset(instance));
    SDK_CHECK_TRUE("save.lifecycle-restore.equal-byte-guest-b",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_B));
    SDK_CHECK_STATUS("save.lifecycle-restore.equal-byte-export-b", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt_b));
    SDK_CHECK_STATUS("save.lifecycle-restore.equal-byte-restore", GN_STATUS_OK,
                     gn_state_restore_v1(instance, equal_state,
                         equal_state_size, &state_detail, sizeof(state_detail)));
    SDK_CHECK_STATUS("save.lifecycle-restore.equal-byte-old-receipt-stale",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(instance, &receipt_b,
                         sizeof(receipt_b), &save_detail, sizeof(save_detail)));
    SDK_CHECK_U64("save.lifecycle-restore.equal-byte-stale-reason",
                  GN_MVS_SAVE_REASON_STALE_RECEIPT, save_detail.reason);
    SDK_CHECK_TRUE("save.lifecycle-restore.equal-byte-still-pending",
                   lifecycle_pending(instance));
    SDK_CHECK_STATUS("save.lifecycle-restore.equal-byte-export-a", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt_a));
    SDK_CHECK_STATUS("save.lifecycle-restore.equal-byte-ack", GN_STATUS_OK,
                     lifecycle_ack(instance, &receipt_a));
    free(equal_state);

    SDK_CHECK_STATUS("save.lifecycle-restore.reload-after-restore", GN_STATUS_OK,
                     save_fixture_reload_checked(instance,
                         GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                         &(gn_mvs_save_lifecycle_result_v1){0}, &save_detail));
    SDK_CHECK_STATUS("save.lifecycle-restore.post-reload-scope", GN_STATUS_OK,
                     save_fixture_scope(instance, 75u, &save_detail));
    SDK_CHECK_TRUE("save.lifecycle-restore.post-reload-guest-a",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_STATUS("save.lifecycle-restore.post-reload-export-ack",
                     GN_STATUS_OK, lifecycle_export(instance, &receipt_a));
    SDK_CHECK_STATUS("save.lifecycle-restore.post-reload-ack", GN_STATUS_OK,
                     lifecycle_ack(instance, &receipt_a));

    SDK_CHECK_STATUS("save.lifecycle-restore.seed-exhausted-branch",
                     GN_STATUS_OK,
                     gn_test_save_seed_lineage(instance, 1u,
                         UINT64_MAX - 1u, 0u, 0u));
    SDK_CHECK_STATUS("save.lifecycle-restore.branch-reaches-maximum",
                     GN_STATUS_OK,
                     gn_state_restore_v1(instance, state_a, state_a_size,
                         &state_detail, sizeof(state_detail)));
    SDK_CHECK_STATUS("save.lifecycle-restore.branch-exhausts",
                     GN_STATUS_OK,
                     gn_state_restore_v1(instance, state_a, state_a_size,
                         &state_detail, sizeof(state_detail)));
    SDK_CHECK_STATUS("save.lifecycle-restore.observe-exhausted", GN_STATUS_OK,
                     gn_test_save_observe(instance, &save_observation));
    SDK_CHECK_U64("save.lifecycle-restore.branch-does-not-wrap", UINT64_MAX,
                  save_observation.restore_branch);
    SDK_CHECK_U64("save.lifecycle-restore.branch-exhausted", 1u,
                  save_observation.exhausted);

    SDK_CHECK_STATUS("save.lifecycle-restore.reset-with-exhaustion",
                     GN_STATUS_OK, gn_reset(instance));
    SDK_CHECK_TRUE("save.lifecycle-restore.guest-write-allowed-exhausted",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_B));
    SDK_CHECK_TRUE("save.lifecycle-restore.exhausted-guest-write-b",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, saved_b, sizeof(saved_b)) == 0);
    SDK_CHECK_STATUS("save.lifecycle-restore.restore-applies-when-exhausted",
                     GN_STATUS_OK,
                     gn_state_restore_v1(instance, state_a, state_a_size,
                         &state_detail, sizeof(state_detail)));
    SDK_CHECK_TRUE("save.lifecycle-restore.exhausted-restore-continuation",
                   lifecycle_state_equal(instance, state_a, state_a_size));
    SDK_CHECK_TRUE("save.lifecycle-restore.exhausted-restore-sram-a",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.lifecycle-restore.exhausted-restore-observation",
                     GN_STATUS_OK,
                     gn_test_save_observe(instance, &save_observation));
    SDK_CHECK_U64("save.lifecycle-restore.exhaustion-retained", 1u,
                  save_observation.exhausted);
    SDK_CHECK_U64("save.lifecycle-restore.exhausted-restore-pending", 1u,
                  save_observation.dirty);
    exhausted_envelope = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    SDK_CHECK_TRUE("save.lifecycle-restore.exhausted-export-buffer",
                   exhausted_envelope != NULL);
    if (exhausted_envelope != NULL) {
        size_t written = 0u;
        gn_mvs_save_detail_v1 exhausted_detail;
        SDK_CHECK_STATUS("save.lifecycle-restore.exhausted-export-refused",
                         GN_STATUS_INVALID_STATE,
                         gn_mvs_save_export_v1(instance, exhausted_envelope,
                             GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written,
                             &receipt_a, sizeof(receipt_a), &exhausted_detail,
                             sizeof(exhausted_detail)));
        SDK_CHECK_U64("save.lifecycle-restore.exhausted-export-reason",
                      GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED,
                      exhausted_detail.reason);
        SDK_CHECK_U64("save.lifecycle-restore.exhausted-export-no-length", 0u,
                      written);
    }
    SDK_CHECK_STATUS("save.lifecycle-restore.renew-after-exhaustion",
                     GN_STATUS_OK, save_fixture_scope(instance, 77u,
                                                       &save_detail));
    SDK_CHECK_TRUE("save.lifecycle-restore.renew-keeps-a",
                   save_fixture_read_sram(instance, sram) &&
                   memcmp(sram, saved_a, sizeof(saved_a)) == 0);

cleanup:
    free(exhausted_envelope);
    free(expected_b);
    free(state_a);
    gn_destroy(probe);
    gn_destroy(instance);
}

static void lifecycle_checked_barriers_and_input_aliases(void) {
    SDK_CASE("save.lifecycle.checked-barriers-and-input-aliases");
    gn_instance *instance = NULL;
    gn_mvs_save_lifecycle_result_v1 result;
    gn_mvs_save_detail_v1 detail;
    gn_mvs_save_receipt_v1 receipt;
    gn_mvs_manifest_v3 manifest;
    uint8_t *bundle = NULL;
    uint8_t *expected_state = NULL;
    size_t expected_size = 0u;
    const size_t bundle_size = public_save_guest_size();
    SDK_CHECK_TRUE("save.checked-boundary.load", save_fixture_load(&instance));
    if (instance == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.checked-boundary.scope", GN_STATUS_OK,
                     save_fixture_scope(instance, 81u, &detail));
    SDK_CHECK_TRUE("save.checked-boundary.guest-a",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_STATUS("save.checked-boundary.export", GN_STATUS_OK,
                     lifecycle_export(instance, &receipt));
    SDK_CHECK_TRUE("save.checked-boundary.capture",
                   save_fixture_capture(instance, &expected_state, &expected_size));
    const uintptr_t backing = gn_test_mvs_save_ram_address(instance);
    gn_instance *const original = instance;
    bundle = (uint8_t *)malloc(bundle_size);
    SDK_CHECK_TRUE("save.checked-boundary.bundle", bundle != NULL &&
                   public_save_guest_build(bundle, bundle_size) &&
                   save_fixture_manifest_from_bundle(bundle, bundle_size, &manifest));
    if (bundle == NULL || expected_state == NULL) goto cleanup;

    SDK_CHECK_STATUS("save.checked-boundary.unresolved-unload", GN_STATUS_INVALID_STATE,
        gn_unload_checked_v1(instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 0u,
                            &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.checked-boundary.unresolved-unload-reason",
                  GN_MVS_SAVE_REASON_HOST_WORK_PENDING, detail.reason);
    SDK_CHECK_STATUS("save.checked-boundary.unresolved-replace", GN_STATUS_INVALID_STATE,
        gn_load_mvs_v3_checked_v1(instance, &manifest,
            GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 0u,
            &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.checked-boundary.unresolved-destroy", GN_STATUS_INVALID_STATE,
        gn_destroy_checked_v1(&instance, GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 0u,
                             &result, sizeof(result), &detail, sizeof(detail)));
    SDK_CHECK_TRUE("save.checked-boundary.unresolved-preserves-handle", instance == original);
    /* Stop safely on the old implementation after a destructive failure. */
    if (instance != original || gn_test_mvs_save_ram_address(instance) != backing)
        goto cleanup;

    for (uint32_t version = GN_MVS_MANIFEST_VERSION_LEGACY;
         version <= GN_MVS_MANIFEST_VERSION; ++version) {
        gn_mvs_manifest_v3 older = manifest;
        older.version = version;
        older.region_count = version == GN_MVS_MANIFEST_VERSION_LEGACY
            ? GN_MVS_LEGACY_REGIONS : GN_MVS_MAX_REGIONS;
        SDK_CHECK_STATUS("save.checked-boundary.v3-rejects-old-version",
            GN_STATUS_UNSUPPORTED_PROFILE,
            gn_load_mvs_v3_checked_v1(instance, &older,
                GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                &result, sizeof(result), &detail, sizeof(detail)));
    }
    for (unsigned output_kind = 0u; output_kind < 2u; ++output_kind) {
        gn_mvs_manifest_v3 alias = manifest;
        gn_mvs_save_lifecycle_result_v1 *result_out = output_kind == 0u
            ? (gn_mvs_save_lifecycle_result_v1 *)(void *)&alias : &result;
        gn_mvs_save_detail_v1 *detail_out = output_kind == 1u
            ? (gn_mvs_save_detail_v1 *)(void *)&alias : &detail;
        SDK_CHECK_STATUS("save.checked-boundary.manifest-overlap-rejected",
            GN_STATUS_INVALID_ARGUMENT,
            gn_load_mvs_v3_checked_v1(instance, &alias,
                GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                result_out, sizeof(result), detail_out, sizeof(detail)));
        SDK_CHECK_TRUE("save.checked-boundary.manifest-preserved",
                       memcmp(&alias, &manifest, sizeof(alias)) == 0);
    }
    for (size_t index = 0u; index < manifest.region_count; ++index) {
        for (unsigned output_kind = 0u; output_kind < 2u; ++output_kind) {
            uint8_t before[sizeof(gn_mvs_save_detail_v1)];
            uint8_t *source = (uint8_t *)(uintptr_t)manifest.regions[index].source;
            memcpy(before, source, sizeof(before));
            gn_mvs_save_lifecycle_result_v1 *result_out = output_kind == 0u
                ? (gn_mvs_save_lifecycle_result_v1 *)(void *)source : &result;
            gn_mvs_save_detail_v1 *detail_out = output_kind == 1u
                ? (gn_mvs_save_detail_v1 *)(void *)source : &detail;
            const size_t counts[] = {manifest.region_count,
                                     GN_MVS_V3_MAX_REGIONS + 1u, SIZE_MAX};
            for (size_t count_index = 0u; count_index < 3u; ++count_index) {
                gn_mvs_manifest_v3 input = manifest;
                input.region_count = counts[count_index];
                SDK_CHECK_STATUS("save.checked-boundary.media-overlap-rejected",
                    GN_STATUS_INVALID_ARGUMENT,
                    gn_load_mvs_v3_checked_v1(instance, &input,
                        GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD, 1u,
                        result_out, sizeof(result), detail_out, sizeof(detail)));
                SDK_CHECK_TRUE("save.checked-boundary.media-preserved",
                               memcmp(before, source, sizeof(before)) == 0);
            }
        }
    }
    SDK_CHECK_TRUE("save.checked-boundary.all-rejections-preserve-state",
                   lifecycle_state_equal(instance, expected_state, expected_size));
    SDK_CHECK_TRUE("save.checked-boundary.all-rejections-preserve-backing",
                   gn_test_mvs_save_ram_address(instance) == backing);
    SDK_CHECK_STATUS("save.checked-boundary.all-rejections-preserve-receipt",
                     GN_STATUS_OK, lifecycle_ack(instance, &receipt));
cleanup:
    free(bundle);
    free(expected_state);
    gn_destroy(instance);
}

static void run_suite(const char *suite) {
    UnityBegin("tests/sdk/test_save_lifecycle.c");
    if (strcmp(suite, "repeat-import") == 0 ||
        strcmp(suite, "lifecycle") == 0) {
        RUN_TEST(lifecycle_repeated_baseline_import_before_guest);
        if (strcmp(suite, "lifecycle") == 0) {
            RUN_TEST(lifecycle_reset_watchdog_and_fault_retain_pending_save);
            RUN_TEST(lifecycle_checked_discard_and_teardown);
            RUN_TEST(lifecycle_checked_candidate_oom_is_atomic);
            RUN_TEST(lifecycle_restore_rollback_and_staging_oom);
            RUN_TEST(lifecycle_checked_barriers_and_input_aliases);
        }
    } else {
        (void)fprintf(stderr, "unknown sdk save lifecycle suite: %s\n", suite);
        invalid_suite = 1;
        (void)UnityEnd();
        return;
    }
    const int failures = UnityEnd();
    sdk_test_result("sdk-save-lifecycle", failures, GLUEYNEO_SOURCE_REVISION,
                    GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
                    GLUEYNEO_COMPILER_VERSION);
}

int main(int argc, char **argv) {
    if (argc != 2) {
        (void)fprintf(stderr,
                      "usage: sdk_save_lifecycle_test <repeat-import|lifecycle>\n");
        return 2;
    }
    run_suite(argv[1]);
    if (invalid_suite != 0) return 2;
    return Unity.TestFailures == 0 ? 0 : 1;
}
