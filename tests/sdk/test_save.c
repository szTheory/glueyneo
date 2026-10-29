/* SPDX-License-Identifier: MIT */
#include "save_fixture.h"

#if defined(__has_feature)
#if __has_feature(address_sanitizer)
#define GLUEYNEO_SAVE_ADDRESS_REUSE_UNSUPPORTED 1
#endif
#endif
#if defined(__SANITIZE_ADDRESS__)
#define GLUEYNEO_SAVE_ADDRESS_REUSE_UNSUPPORTED 1
#endif
#include "test_support.h"

#include <inttypes.h>
#include <stddef.h>
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

static const uint8_t saved_a[SAVE_FIXTURE_OUTPUT_COUNT] = {
    0x12u, 0x34u, 0x56u, 0x78u, 0x9au, 0xbcu
};
static const uint8_t saved_b[SAVE_FIXTURE_OUTPUT_COUNT] = {
    0xa1u, 0xb2u, 0xc3u, 0xd4u, 0xe5u, 0xf6u
};
static int stale_clean_negative_control;
static int invalid_suite;

typedef struct {
    gn_instance *instance;
    gn_instance *peer;
    uint8_t *buffer;
    uint8_t *state_a;
    uint8_t *state_b;
} save_receipt_test_resources;

static save_receipt_test_resources active_save_receipt_resources;

static void release_save_receipt_test_resources(void) {
    free(active_save_receipt_resources.state_a);
    free(active_save_receipt_resources.state_b);
    free(active_save_receipt_resources.buffer);
    gn_destroy(active_save_receipt_resources.peer);
    gn_destroy(active_save_receipt_resources.instance);
    memset(&active_save_receipt_resources, 0,
           sizeof(active_save_receipt_resources));
}

void setUp(void) {}
void tearDown(void) {
    /* Unity calls tearDown even after an assertion returns early. */
    release_save_receipt_test_resources();
}

static int save_state_equal(gn_instance *instance, const uint8_t *expected,
                            size_t expected_size) {
    uint8_t *actual = NULL;
    size_t actual_size = 0u;
    const int captured = save_fixture_capture(instance, &actual, &actual_size);
    const int equal = captured != 0 && actual_size == expected_size &&
        memcmp(actual, expected, expected_size) == 0;
    free(actual);
    return equal;
}

static int save_rehash_envelope(uint8_t *envelope) {
    static const uint8_t domain[] = "Glueyneo MVS save v1";
    const size_t covered = sizeof(domain) - 1u + 64u +
        GN_MVS_SAVE_PAYLOAD_V1_BYTES;
    uint8_t *input = (uint8_t *)malloc(covered);
    if (input == NULL) return 0;
    memcpy(input, domain, sizeof(domain) - 1u);
    memcpy(input + sizeof(domain) - 1u, envelope, 64u);
    memcpy(input + sizeof(domain) - 1u + 64u,
           envelope + GN_MVS_SAVE_HEADER_V1_BYTES,
           GN_MVS_SAVE_PAYLOAD_V1_BYTES);
    uint8_t digest[32];
    const gn_status status = gn_test_sha256(input, covered, digest);
    free(input);
    if (status != GN_STATUS_OK) return 0;
    memcpy(envelope + 64u, digest, sizeof(digest));
    return 1;
}

static void save_api_query_export_bounds_and_atomic_outputs(void) {
    SDK_CASE("save.api.query-export-bounds-atomic-outputs");
    gn_instance *instance = NULL;
    uint8_t *envelope = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    uint8_t *before_state = NULL;
    uint8_t *after_state = NULL;
    size_t before_state_size = 0u, after_state_size = 0u;
    gn_mvs_save_receipt_v1 receipt;
    gn_mvs_save_receipt_v1 prior_receipt;
    gn_mvs_save_detail_v1 detail;
    gn_mvs_save_info_v1 info;
    size_t written = 777u;
    SDK_CHECK_TRUE("save.fixture.load", save_fixture_load(&instance));
    SDK_CHECK_TRUE("save.fixture.envelope-allocation", envelope != NULL);
    if (instance == NULL || envelope == NULL) goto cleanup;
    memset(&detail, 0, sizeof(detail));
    SDK_CHECK_STATUS("save.api.scope", GN_STATUS_OK,
                     save_fixture_scope(instance, 1u, &detail));
    SDK_CHECK_STATUS("save.api.query", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.api.supported", 1u, info.supported);
    SDK_CHECK_U64("save.api.save-id", GN_MVS_SAVE_ID_V1, info.save_id);
    SDK_CHECK_U64("save.api.payload-bound",
                  GN_MVS_SAVE_ENVELOPE_V1_BYTES, info.envelope_bytes);
    SDK_CHECK_U64("save.api.initial-clean", 0u, info.dirty);
    SDK_CHECK_U64("save.api.initial-baseline-unknown", 0u,
                  info.baseline_known);
    SDK_CHECK_TRUE("save.api.capture-before-export",
                   save_fixture_capture(instance, &before_state,
                                        &before_state_size));
    memset(&receipt, 0xa7, sizeof(receipt));
    SDK_CHECK_STATUS("save.api.export", GN_STATUS_OK,
                     save_fixture_export(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         &detail));
    SDK_CHECK_U64("save.api.export-length",
                  GN_MVS_SAVE_ENVELOPE_V1_BYTES, written);
    SDK_CHECK_TRUE("save.api.gnsv-magic", memcmp(envelope, "GNSV", 4u) == 0);
    SDK_CHECK_U64("save.api.export-receipt-size", sizeof(receipt), receipt.size);
    SDK_CHECK_TRUE("save.api.capture-after-export",
                   save_fixture_capture(instance, &after_state,
                                        &after_state_size));
    SDK_CHECK_TRUE("save.api.export-does-not-run-guest",
                   before_state_size == after_state_size &&
                   memcmp(before_state, after_state, before_state_size) == 0);
    SDK_CHECK_STATUS("save.api.query-after-export", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.api.export-keeps-clean-state", 0u, info.dirty);
    SDK_CHECK_U64("save.api.export-does-not-affirm-baseline", 0u,
                  info.baseline_known);

    memcpy(&prior_receipt, &receipt, sizeof(receipt));
    memset(envelope, 0x91, GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    written = 99u;
    SDK_CHECK_STATUS("save.api.short-export-rejected", GN_STATUS_INVALID_ARGUMENT,
                     save_fixture_export(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES - 1u, &written, &receipt,
                         &detail));
    SDK_CHECK_U64("save.api.short-export-reason", GN_MVS_SAVE_REASON_CAPACITY,
                  detail.reason);
    SDK_CHECK_U64("save.api.failed-export-written-zero", 0u, written);
    SDK_CHECK_TRUE("save.api.failed-export-preserves-receipt",
                   memcmp(&receipt, &prior_receipt, sizeof(receipt)) == 0);
    SDK_CHECK_TRUE("save.api.failed-export-preserves-payload",
                   envelope[0] == 0x91u &&
                   envelope[GN_MVS_SAVE_ENVELOPE_V1_BYTES - 2u] == 0x91u);
    SDK_CHECK_STATUS("save.api-old-receipt-still-eligible", GN_STATUS_OK,
                     gn_mvs_save_ack_v1(instance, &prior_receipt,
                         sizeof(prior_receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.ack-detail", GN_MVS_SAVE_REASON_NONE,
                     detail.reason);

    memset(&info, 0x4c, sizeof(info));
    SDK_CHECK_STATUS("save.api.query-null-instance", GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_query_v1(NULL, &info, sizeof(info), &detail,
                                          sizeof(detail)));
    SDK_CHECK_U64("save.api.query-null-reason",
                  GN_MVS_SAVE_REASON_INVALID_ARGUMENT, detail.reason);
    SDK_CHECK_U64("save.api.query-null-zero-output", 0u, info.supported);
    SDK_CHECK_STATUS("save.api.query-null-output", GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_query_v1(instance, NULL, sizeof(info), &detail,
                                          sizeof(detail)));
    SDK_CHECK_STATUS("save.api.query-wrong-size", GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_query_v1(instance, &info, sizeof(info) - 1u,
                                          &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.query-null-detail-nonzero-size",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_query_v1(instance, &info, sizeof(info), NULL,
                                          sizeof(detail)));

    _Alignas(max_align_t) uint8_t overlap[sizeof(info) + sizeof(detail) + 16u];
    SDK_CHECK_STATUS("save.api.query-info-detail-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_query_v1(instance,
                         (gn_mvs_save_info_v1 *)overlap, sizeof(info),
                         (gn_mvs_save_detail_v1 *)(overlap + 8u),
                         sizeof(detail)));
    const uintptr_t owned = gn_test_mvs_save_ram_address(instance);
    SDK_CHECK_TRUE("save.api.owner-address-nonzero", owned != (uintptr_t)0);
    SDK_CHECK_STATUS("save.api.query-live-owned-output-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_query_v1(instance,
                         (gn_mvs_save_info_v1 *)owned, sizeof(info), NULL, 0u));

    memset(&receipt, 0x5e, sizeof(receipt));
    memcpy(&prior_receipt, &receipt, sizeof(receipt));
    memset(envelope, 0x39, GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    written = 99u;
    SDK_CHECK_STATUS("save.api.zero-capacity-rejected", GN_STATUS_INVALID_ARGUMENT,
                     save_fixture_export(instance, envelope, 0u, &written,
                                         &receipt, &detail));
    SDK_CHECK_U64("save.api.zero-capacity-reason", GN_MVS_SAVE_REASON_CAPACITY,
                  detail.reason);
    SDK_CHECK_U64("save.api.zero-capacity-written-zero", 0u, written);
    SDK_CHECK_TRUE("save.api.zero-capacity-preserves-receipt",
                   memcmp(&receipt, &prior_receipt, sizeof(receipt)) == 0);
    SDK_CHECK_TRUE("save.api.zero-capacity-preserves-buffer",
                   envelope[0] == 0x39u && envelope[GN_MVS_SAVE_ENVELOPE_V1_BYTES - 1u] == 0x39u);

    written = 123u;
    memset(&receipt, 0x62, sizeof(receipt));
    memcpy(&prior_receipt, &receipt, sizeof(receipt));
    SDK_CHECK_STATUS("save.api.null-buffer-rejected", GN_STATUS_INVALID_ARGUMENT,
                     save_fixture_export(instance, NULL,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         &detail));
    SDK_CHECK_U64("save.api.null-buffer-written-zero", 0u, written);
    SDK_CHECK_TRUE("save.api.null-buffer-preserves-receipt",
                   memcmp(&receipt, &prior_receipt, sizeof(receipt)) == 0);

    SDK_CHECK_STATUS("save.api.null-written-rejected", GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, NULL, &receipt,
                         sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.null-receipt-rejected", GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, NULL,
                         sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.wrong-receipt-size", GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         sizeof(receipt) - 1u, &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.output-written-receipt-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, (size_t *)&receipt,
                         &receipt, sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.output-buffer-written-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, (void *)&written,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.output-buffer-receipt-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, &receipt,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.output-live-owned-buffer-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, (void *)owned,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.buffer-range-overflow",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance,
                         (void *)(uintptr_t)(UINTPTR_MAX - 7u), 16u, &written,
                         &receipt, sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.written-range-overflow",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES,
                         (size_t *)(uintptr_t)(UINTPTR_MAX - 3u), &receipt,
                         sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.api.scope-renew-detail-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_scope_renew_v1(instance,
                         (const gn_mvs_save_scope_v1 *)&detail,
                         sizeof(gn_mvs_save_scope_v1), &detail, sizeof(detail)));
cleanup:
    free(before_state);
    free(after_state);
    free(envelope);
    gn_destroy(instance);
}

static void save_api_entrypoint_arguments_and_aliases(void) {
    SDK_CASE("save.api-entrypoint-arguments-aliases");
    gn_instance *instance = NULL;
    uint8_t *envelope = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    gn_mvs_save_scope_v1 scope;
    gn_mvs_save_receipt_v1 receipt;
    gn_mvs_save_info_v1 info;
    gn_mvs_save_detail_v1 detail;
    size_t written = 0u;
    _Alignas(max_align_t) uint8_t scratch[256];
    _Alignas(max_align_t) uint8_t pair_storage[
        sizeof(gn_mvs_save_receipt_v1) + sizeof(gn_mvs_save_detail_v1) + 16u];
    SDK_CHECK_TRUE("save.args.load", save_fixture_load(&instance));
    SDK_CHECK_TRUE("save.args-envelope-allocation", envelope != NULL);
    if (instance == NULL || envelope == NULL) goto cleanup;
    save_fixture_set_scope(&scope, 51u);
    memset(&detail, 0, sizeof(detail));
    SDK_CHECK_STATUS("save.args.scope-ready", GN_STATUS_OK,
                     save_fixture_scope(instance, 52u, &detail));
    SDK_CHECK_STATUS("save.args.export-ready", GN_STATUS_OK,
                     save_fixture_export(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         &detail));
    const uintptr_t owned = gn_test_mvs_save_ram_address(instance);

    SDK_CHECK_STATUS("save.args.query-misaligned-info",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_query_v1(instance,
                         (gn_mvs_save_info_v1 *)(void *)(scratch + 1u),
                         sizeof(info), NULL, 0u));
    SDK_CHECK_STATUS("save.args.query-detail-misaligned",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_query_v1(instance, &info, sizeof(info),
                         (gn_mvs_save_detail_v1 *)(void *)(scratch + 1u),
                         sizeof(detail)));
    SDK_CHECK_STATUS("save.args.query-detail-owned-alias",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_query_v1(instance, &info, sizeof(info),
                         (gn_mvs_save_detail_v1 *)(uintptr_t)owned,
                         sizeof(detail)));

    SDK_CHECK_STATUS("save.args.scope-null-instance",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_scope_renew_v1(NULL, &scope, sizeof(scope),
                                                &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.args.scope-null-record",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_scope_renew_v1(instance, NULL, sizeof(scope),
                                                &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.args.scope-wrong-size",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_scope_renew_v1(instance, &scope,
                         sizeof(scope) - 1u, &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.args.scope-misaligned-record",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_scope_renew_v1(instance,
                         (const gn_mvs_save_scope_v1 *)(void *)(scratch + 1u),
                         sizeof(scope), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.args.scope-detail-misaligned",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_scope_renew_v1(instance, &scope, sizeof(scope),
                         (gn_mvs_save_detail_v1 *)(void *)(scratch + 1u),
                         sizeof(detail)));
    SDK_CHECK_STATUS("save.args.scope-live-owned-alias",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_scope_renew_v1(instance,
                         (const gn_mvs_save_scope_v1 *)(uintptr_t)owned,
                         sizeof(scope), NULL, 0u));
    SDK_CHECK_STATUS("save.args.scope-pointer-overflow",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_scope_renew_v1(instance,
                         (const gn_mvs_save_scope_v1 *)(uintptr_t)(UINTPTR_MAX - 7u),
                         sizeof(scope), NULL, 0u));

    SDK_CHECK_STATUS("save.args.export-null-instance",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(NULL, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.args.export-written-misaligned",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES,
                         (size_t *)(void *)(scratch + 1u), &receipt,
                         sizeof(receipt), NULL, 0u));
    SDK_CHECK_STATUS("save.args.export-receipt-misaligned",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written,
                         (gn_mvs_save_receipt_v1 *)(void *)(scratch + 1u),
                         sizeof(receipt), NULL, 0u));
    SDK_CHECK_STATUS("save.args.export-detail-misaligned",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         sizeof(receipt),
                         (gn_mvs_save_detail_v1 *)(void *)(scratch + 1u),
                         sizeof(detail)));
    SDK_CHECK_STATUS("save.args.export-buffer-detail-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, &detail,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.args.export-written-detail-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, (size_t *)&detail,
                         &receipt, sizeof(receipt), &detail, sizeof(detail)));
    gn_mvs_save_receipt_v1 *receipt_alias =
        (gn_mvs_save_receipt_v1 *)(void *)pair_storage;
    gn_mvs_save_detail_v1 *detail_alias =
        (gn_mvs_save_detail_v1 *)(void *)(pair_storage + 8u);
    SDK_CHECK_STATUS("save.args.export-receipt-detail-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written,
                         receipt_alias, sizeof(*receipt_alias), detail_alias,
                         sizeof(*detail_alias)));
    SDK_CHECK_STATUS("save.args.export-null-detail-nonzero-size",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_export_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         sizeof(receipt), NULL, sizeof(detail)));

    SDK_CHECK_STATUS("save.args.import-null-instance",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_import_baseline_v1(NULL, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &detail,
                         sizeof(detail)));
    SDK_CHECK_STATUS("save.args.import-detail-misaligned",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_import_baseline_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES,
                         (gn_mvs_save_detail_v1 *)(void *)(scratch + 1u),
                         sizeof(detail)));
    SDK_CHECK_STATUS("save.args.import-null-detail-nonzero-size",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_import_baseline_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, NULL, sizeof(detail)));

    SDK_CHECK_STATUS("save.args.ack-null-instance",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_ack_v1(NULL, &receipt, sizeof(receipt),
                                        &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.args.ack-null-receipt",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_ack_v1(instance, NULL, sizeof(receipt),
                                        &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.args.ack-wrong-size",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_ack_v1(instance, &receipt,
                                        sizeof(receipt) - 1u, &detail,
                                        sizeof(detail)));
    SDK_CHECK_STATUS("save.args.ack-receipt-misaligned",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_ack_v1(instance,
                         (const gn_mvs_save_receipt_v1 *)(void *)(scratch + 1u),
                         sizeof(receipt), &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.args.ack-detail-misaligned",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_ack_v1(instance, &receipt, sizeof(receipt),
                         (gn_mvs_save_detail_v1 *)(void *)(scratch + 1u),
                         sizeof(detail)));
    SDK_CHECK_STATUS("save.args.ack-receipt-detail-overlap",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_ack_v1(instance,
                         (const gn_mvs_save_receipt_v1 *)(void *)pair_storage,
                         sizeof(receipt),
                         (gn_mvs_save_detail_v1 *)(void *)(pair_storage + 8u),
                         sizeof(detail)));
cleanup:
    free(envelope);
    gn_destroy(instance);
}

typedef struct {
    size_t offset;
    uint8_t value;
    int rehash;
    gn_status status;
    gn_mvs_save_reason reason;
    const char *id;
} save_corruption;

static void save_api_import_rejects_envelopes_atomically(void) {
    SDK_CASE("save.api.import-envelope-matrix-atomic");
    gn_instance *instance = NULL;
    gn_instance *source = NULL;
    uint8_t *envelope = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES + 1u);
    uint8_t *bad = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES + 1u);
    uint8_t *state = NULL;
    size_t state_size = 0u;
    uint8_t sram_before[SAVE_FIXTURE_OUTPUT_COUNT];
    uint8_t sram_after[SAVE_FIXTURE_OUTPUT_COUNT];
    gn_mvs_save_receipt_v1 source_receipt;
    gn_mvs_save_info_v1 before_info;
    gn_mvs_save_info_v1 after_info;
    gn_mvs_save_detail_v1 detail;
    size_t written = 0u;
    SDK_CHECK_TRUE("save.fixture.load", save_fixture_load(&instance));
    SDK_CHECK_TRUE("save.api.import-source-load", save_fixture_load(&source));
    SDK_CHECK_TRUE("save.api.import-envelope-allocation",
                   envelope != NULL && bad != NULL);
    if (instance == NULL || source == NULL || envelope == NULL || bad == NULL)
        goto cleanup;
    SDK_CHECK_STATUS("save.api.import-source-scope", GN_STATUS_OK,
                     save_fixture_scope(source, 12u, &detail));
    SDK_CHECK_TRUE("save.api.import-source-guest-a",
                   save_fixture_run_guest(source, GN_MVS_INPUT_P1_A));
    SDK_CHECK_TRUE("save.api.import-source-a-readback",
                   save_fixture_read_sram(source, sram_after));
    SDK_CHECK_TRUE("save.api.import-source-asymmetric-bytes",
                   memcmp(sram_after, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.api.import-source-export", GN_STATUS_OK,
                     save_fixture_export(source, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written,
                         &source_receipt,
                         &detail));
    SDK_CHECK_U64("save.api.import-source-export-length",
                  GN_MVS_SAVE_ENVELOPE_V1_BYTES, written);
    SDK_CHECK_STATUS("save.api.import-scope", GN_STATUS_OK,
                     save_fixture_scope(instance, 11u, &detail));
    SDK_CHECK_TRUE("save.api.import-a-readback", save_fixture_read_sram(
                       instance, sram_before));
    SDK_CHECK_TRUE("save.api.import-target-starts-zero",
                   memcmp(sram_before, (uint8_t[6]){0}, sizeof(sram_before)) ==
                       0);
    SDK_CHECK_STATUS("save.api.import-query-before", GN_STATUS_OK,
                     save_fixture_query(instance, &before_info, &detail));
    SDK_CHECK_TRUE("save.api.import-capture-before",
                   save_fixture_capture(instance, &state, &state_size));
    const uintptr_t owner = gn_test_mvs_save_ram_address(instance);
    const save_corruption corruptions[] = {
        {0u, (uint8_t)'X', 0, GN_STATUS_INVALID_MEDIA,
         GN_MVS_SAVE_REASON_FORMAT,
         "save.import.magic-reason"},
        {7u, 2u, 1, GN_STATUS_UNSUPPORTED_PROFILE,
         GN_MVS_SAVE_REASON_VERSION,
         "save.import.version-reason"},
        {11u, 1u, 1, GN_STATUS_INVALID_MEDIA, GN_MVS_SAVE_REASON_CAPACITY,
         "save.import.header-length-reason"},
        {15u, 0u, 1, GN_STATUS_INVALID_MEDIA, GN_MVS_SAVE_REASON_CAPACITY,
         "save.import.total-length-reason"},
        {17u, (uint8_t)(envelope[17] ^ 1u), 1, GN_STATUS_INVALID_MEDIA,
         GN_MVS_SAVE_REASON_CAPACITY,
         "save.import.payload-length-reason"},
        {23u, 2u, 1, GN_STATUS_UNSUPPORTED_PROFILE,
         GN_MVS_SAVE_REASON_DURABLE_ID,
         "save.import.save-id-reason"},
        {27u, (uint8_t)(envelope[27] ^ 1u), 1,
         GN_STATUS_UNSUPPORTED_PROFILE,
         GN_MVS_SAVE_REASON_PROFILE,
         "save.import.profile-reason"},
        {31u, 1u, 1, GN_STATUS_INVALID_MEDIA, GN_MVS_SAVE_REASON_RESERVED,
         "save.import.reserved-reason"},
        {32u, (uint8_t)(envelope[32] ^ 0x40u), 1, GN_STATUS_INVALID_MEDIA,
         GN_MVS_SAVE_REASON_MEDIA_IDENTITY, "save.import.media-reason"},
        {64u, (uint8_t)(envelope[64] ^ 1u), 0, GN_STATUS_INVALID_MEDIA,
         GN_MVS_SAVE_REASON_INTEGRITY, "save.import.digest-reason"},
        {GN_MVS_SAVE_HEADER_V1_BYTES + GN_MVS_SAVE_PAYLOAD_V1_BYTES - 1u,
         (uint8_t)(envelope[GN_MVS_SAVE_ENVELOPE_V1_BYTES - 1u] ^ 1u), 0,
         GN_STATUS_INVALID_MEDIA,
         GN_MVS_SAVE_REASON_INTEGRITY, "save.import.payload-digest-reason"}
    };
    for (size_t index = 0u;
         index < sizeof(corruptions) / sizeof(corruptions[0]); ++index) {
        memcpy(bad, envelope, GN_MVS_SAVE_ENVELOPE_V1_BYTES);
        bad[corruptions[index].offset] = corruptions[index].value;
        if (corruptions[index].rehash != 0)
            SDK_CHECK_TRUE("save.import.rehash-metadata-mutation",
                           save_rehash_envelope(bad));
        SDK_CHECK_STATUS(corruptions[index].id, corruptions[index].status,
                         gn_mvs_save_import_baseline_v1(instance, bad,
                             GN_MVS_SAVE_ENVELOPE_V1_BYTES, &detail,
                             sizeof(detail)));
        SDK_CHECK_U64("save.import.numeric-reason",
                      corruptions[index].reason, detail.reason);
        SDK_CHECK_TRUE("save.import.continuation-unchanged",
                       save_state_equal(instance, state, state_size));
        SDK_CHECK_TRUE("save.import.backing-address-unchanged",
                       owner == gn_test_mvs_save_ram_address(instance));
        SDK_CHECK_TRUE("save.import-sram-unchanged",
                       save_fixture_read_sram(instance, sram_after) &&
                       memcmp(sram_before, sram_after, sizeof(sram_before)) == 0);
    }
    memcpy(bad, envelope, GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    bad[GN_MVS_SAVE_ENVELOPE_V1_BYTES] = 0x7fu;
    SDK_CHECK_STATUS("save.import.trailing-byte-rejected", GN_STATUS_INVALID_MEDIA,
                     gn_mvs_save_import_baseline_v1(instance, bad,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES + 1u, &detail,
                         sizeof(detail)));
    SDK_CHECK_U64("save.import.trailing-byte-reason",
                  GN_MVS_SAVE_REASON_CAPACITY, detail.reason);
    SDK_CHECK_STATUS("save.import.truncated-rejected", GN_STATUS_INVALID_MEDIA,
                     gn_mvs_save_import_baseline_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES - 1u, &detail,
                         sizeof(detail)));
    SDK_CHECK_U64("save.import.truncated-reason",
                  GN_MVS_SAVE_REASON_CAPACITY, detail.reason);
    SDK_CHECK_STATUS("save.import.null-rejected", GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_import_baseline_v1(instance, NULL,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.import.zero-length-rejected", GN_STATUS_INVALID_MEDIA,
                     gn_mvs_save_import_baseline_v1(instance, envelope, 0u,
                         &detail, sizeof(detail)));
    SDK_CHECK_U64("save.import.zero-length-reason",
                  GN_MVS_SAVE_REASON_CAPACITY, detail.reason);
    SDK_CHECK_STATUS("save.import.pointer-overflow-rejected",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_import_baseline_v1(instance,
                         (const void *)(uintptr_t)(UINTPTR_MAX - 7u), 16u,
                         &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.import.live-owned-alias-rejected",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_import_baseline_v1(instance,
                         (const void *)owner, GN_MVS_SAVE_ENVELOPE_V1_BYTES,
                         &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.import.input-detail-alias-rejected",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_import_baseline_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES,
                         (gn_mvs_save_detail_v1 *)envelope,
                         sizeof(detail)));
    SDK_CHECK_STATUS("save.import.null-detail-nonzero-size",
                     GN_STATUS_INVALID_ARGUMENT,
                     gn_mvs_save_import_baseline_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, NULL, sizeof(detail)));
    SDK_CHECK_STATUS("save.import.query-after-rejections", GN_STATUS_OK,
                     save_fixture_query(instance, &after_info, &detail));
    SDK_CHECK_TRUE("save.import.ownership-unchanged",
                   before_info.dirty == after_info.dirty &&
                   before_info.baseline_known == after_info.baseline_known &&
                   before_info.startup_import_allowed ==
                       after_info.startup_import_allowed &&
                   before_info.exhausted == after_info.exhausted);
    SDK_CHECK_STATUS("save.import-after-rejections-still-valid",
                     GN_STATUS_OK,
                     gn_mvs_save_import_baseline_v1(instance, envelope,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &detail,
                         sizeof(detail)));
    SDK_CHECK_TRUE("save.import-valid-payload-applied",
                   save_fixture_read_sram(instance, sram_after) &&
                   memcmp(sram_after, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.import-query-after-valid-import", GN_STATUS_OK,
                     save_fixture_query(instance, &after_info, &detail));
    SDK_CHECK_U64("save.import-valid-is-clean", 0u, after_info.dirty);
    SDK_CHECK_U64("save.import-valid-establishes-baseline", 1u,
                  after_info.baseline_known);
cleanup:
    free(state);
    free(envelope);
    free(bad);
    gn_destroy(instance);
    gn_destroy(source);
}

static void save_receipts_reject_stale_and_preserve_pending(void) {
    SDK_CASE("save.receipts.latest-current-nonrewinding");
    gn_instance *instance = NULL;
    gn_instance *peer = NULL;
    uint8_t *buffer = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    uint8_t *state_a = NULL;
    uint8_t *state_b = NULL;
    size_t state_a_size = 0u, state_b_size = 0u;
    size_t written = 0u;
    gn_mvs_save_receipt_v1 initial_receipt, first, latest, branch_receipt;
    gn_mvs_save_receipt_v1 peer_receipt;
    gn_mvs_save_detail_v1 detail;
    gn_mvs_save_info_v1 info, peer_info;
    uint8_t output[SAVE_FIXTURE_OUTPUT_COUNT];
    uint8_t readback[SAVE_FIXTURE_OUTPUT_COUNT];
    active_save_receipt_resources.buffer = buffer;
    const int instance_loaded = save_fixture_load(&instance);
    active_save_receipt_resources.instance = instance;
    SDK_CHECK_TRUE("save.receipts.load-instance", instance_loaded);
    const int peer_loaded = save_fixture_load(&peer);
    active_save_receipt_resources.peer = peer;
    SDK_CHECK_TRUE("save.receipts.load-peer", peer_loaded);
    SDK_CHECK_TRUE("save.receipts.transfer-allocation", buffer != NULL);
    if (instance == NULL || peer == NULL || buffer == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.receipts.scope-instance", GN_STATUS_OK,
                     save_fixture_scope(instance, 21u, &detail));
    SDK_CHECK_STATUS("save.receipts.scope-peer", GN_STATUS_OK,
                     save_fixture_scope(peer, 22u, &detail));
    SDK_CHECK_STATUS("save.receipts.query-peer", GN_STATUS_OK,
                     save_fixture_query(peer, &peer_info, &detail));
    SDK_CHECK_STATUS("save.receipts.query-instance", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_TRUE("save.receipts.same-media-peer",
                   memcmp(info.media_identity_sha256,
                          peer_info.media_identity_sha256, 32u) == 0);

    SDK_CHECK_STATUS("save.receipts.initial-export", GN_STATUS_OK,
                     save_fixture_export(instance, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written,
                         &initial_receipt, &detail));
    SDK_CHECK_TRUE("save.receipts.guest-a-run",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_TRUE("save.receipts-first-guest-reads-zero",
                   save_fixture_read_guest_output(instance, output) &&
                   memcmp(output, (uint8_t[6]){0}, sizeof(output)) == 0);
    SDK_CHECK_TRUE("save.receipts-a-byte-word-readback",
                   save_fixture_read_sram(instance, readback) &&
                   memcmp(readback, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.receipts.query-after-guest", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.receipts-guest-dirty", 1u, info.dirty);
    SDK_CHECK_U64("save.receipts-first-execution-closes-startup", 0u,
                  info.startup_import_allowed);
    SDK_CHECK_STATUS("save.receipts-write-after-export-stale",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(instance, &initial_receipt,
                         sizeof(initial_receipt), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.receipts-write-after-export-reason",
                  GN_MVS_SAVE_REASON_STALE_RECEIPT, detail.reason);
    SDK_CHECK_STATUS("save.receipts-first-export", GN_STATUS_OK,
                     save_fixture_export(instance, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &first,
                         &detail));
    SDK_CHECK_STATUS("save.receipts-reexport-same-bytes", GN_STATUS_OK,
                     save_fixture_export(instance, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &latest,
                         &detail));
    SDK_CHECK_TRUE("save.receipts-reexport-supersedes",
                   first.export_sequence != latest.export_sequence &&
                   memcmp(first.scope, latest.scope, sizeof(first.scope)) == 0);
    if (stale_clean_negative_control != 0)
        SDK_CHECK_STATUS("save.receipts.arm-stale-clean-bypass", GN_STATUS_OK,
                         gn_test_save_stale_clean_bypass_arm(instance));
    SDK_CHECK_STATUS("save.receipts-reordered-ack-rejected",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(instance, &first, sizeof(first),
                                        &detail, sizeof(detail)));
    SDK_CHECK_U64("save.receipts-reordered-ack-reason",
                  GN_MVS_SAVE_REASON_STALE_RECEIPT, detail.reason);
    SDK_CHECK_STATUS("save.pending-newer-query", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_TRUE("save.pending-newer",
                   info.dirty != 0u && info.baseline_known == 0u);
    SDK_CHECK_STATUS("save.receipts-latest-ack", GN_STATUS_OK,
                     gn_mvs_save_ack_v1(instance, &latest, sizeof(latest),
                                        &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.receipts-duplicate-ack-rejected",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(instance, &latest, sizeof(latest),
                                        &detail, sizeof(detail)));
    SDK_CHECK_U64("save.receipts-duplicate-ack-reason",
                  GN_MVS_SAVE_REASON_RECEIPT_CONSUMED, detail.reason);
    SDK_CHECK_STATUS("save.receipts-clean-query", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.receipts-latest-ack-clears", 0u, info.dirty);
    SDK_CHECK_U64("save.receipts-latest-ack-baseline", 1u,
                  info.baseline_known);

    const int state_a_captured = save_fixture_capture(
        instance, &state_a, &state_a_size);
    active_save_receipt_resources.state_a = state_a;
    SDK_CHECK_TRUE("save.receipts-capture-a", state_a_captured);
    SDK_CHECK_TRUE("save.receipts-peer-b-run",
                   save_fixture_run_guest(peer, GN_MVS_INPUT_P1_B));
    SDK_CHECK_TRUE("save.receipts-peer-b-readback",
                   save_fixture_read_sram(peer, readback) &&
                   memcmp(readback, saved_b, sizeof(saved_b)) == 0);
    const int state_b_captured = save_fixture_capture(
        peer, &state_b, &state_b_size);
    active_save_receipt_resources.state_b = state_b;
    SDK_CHECK_TRUE("save.receipts-capture-b", state_b_captured);
    SDK_CHECK_STATUS("save.receipts-peer-export", GN_STATUS_OK,
                     save_fixture_export(peer, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written,
                         &peer_receipt, &detail));
    SDK_CHECK_STATUS("save.receipts-restore-b", GN_STATUS_OK,
                     save_fixture_restore(instance, state_b, state_b_size)
                         ? GN_STATUS_OK : GN_STATUS_INVALID_MEDIA);
    SDK_CHECK_TRUE("save.receipts-b-current-bytes",
                   save_fixture_read_sram(instance, readback) &&
                   memcmp(readback, saved_b, sizeof(saved_b)) == 0);
    SDK_CHECK_STATUS("save.receipts-export-b-branch", GN_STATUS_OK,
                     save_fixture_export(instance, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written,
                         &branch_receipt, &detail));
    SDK_CHECK_STATUS("save.receipts-restore-a-after-b", GN_STATUS_OK,
                     save_fixture_restore(instance, state_a, state_a_size)
                         ? GN_STATUS_OK : GN_STATUS_INVALID_MEDIA);
    SDK_CHECK_TRUE("save.receipts-a-b-a-byte-restoration",
                   save_fixture_read_sram(instance, readback) &&
                   memcmp(readback, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.receipts-a-b-a-old-ack-rejected",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(instance, &branch_receipt,
                         sizeof(branch_receipt), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.receipts-a-b-a-old-ack-reason",
                  GN_MVS_SAVE_REASON_STALE_RECEIPT, detail.reason);
    SDK_CHECK_STATUS("save.receipts-a-b-a-pending-query", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.receipts-a-b-a-keeps-pending", 1u, info.dirty);
    SDK_CHECK_STATUS("save.receipts-a-b-a-export", GN_STATUS_OK,
                     save_fixture_export(instance, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &latest,
                         &detail));
    SDK_CHECK_STATUS("save.receipts-foreign-peer-ack-rejected",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(instance, &peer_receipt,
                         sizeof(peer_receipt), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.receipts-foreign-peer-reason",
                  GN_MVS_SAVE_REASON_STALE_RECEIPT, detail.reason);
    SDK_CHECK_STATUS("save.receipts-a-b-a-current-ack", GN_STATUS_OK,
                     gn_mvs_save_ack_v1(instance, &latest, sizeof(latest),
                                        &detail, sizeof(detail)));
    SDK_CHECK_TRUE("save.receipts-reload-old-receipt-export",
                   save_fixture_export(instance, buffer,
                       GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written,
                       &branch_receipt, &detail) == GN_STATUS_OK);
    SDK_CHECK_TRUE("save.receipts-successful-reload",
                   save_fixture_reload(instance));
    SDK_CHECK_STATUS("save.receipts-reload-old-receipt-rejected",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(instance, &branch_receipt,
                         sizeof(branch_receipt), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.receipts-reload-old-receipt-reason",
                  GN_MVS_SAVE_REASON_STALE_RECEIPT, detail.reason);
    SDK_CHECK_TRUE("save.receipts-reload-fresh-scope",
                   save_fixture_scope(instance, 23u, &detail) == GN_STATUS_OK);

cleanup:
    release_save_receipt_test_resources();
}

static void save_receipt_scope_survives_allocator_address_reuse(void) {
    SDK_CASE("save.receipts-recreated-address-foreign-scope");
    gn_test_allocator allocator;
    gn_test_allocator_init(&allocator);
    gn_instance *first = NULL;
    gn_instance *second = NULL;
    uint8_t *buffer = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    gn_mvs_save_receipt_v1 old_receipt;
    gn_mvs_save_detail_v1 detail;
    gn_mvs_save_info_v1 info;
    size_t written = 0u;
    SDK_CHECK_TRUE("save.receipts-address.load-first",
                   save_fixture_load_with_allocator(&allocator, &first));
    SDK_CHECK_TRUE("save.receipts-address.buffer", buffer != NULL);
    if (first == NULL || buffer == NULL) goto cleanup;
#if !defined(GLUEYNEO_SAVE_ADDRESS_REUSE_UNSUPPORTED)
    const uintptr_t old_address = (uintptr_t)first;
#endif
    SDK_CHECK_STATUS("save.receipts-address.old-scope", GN_STATUS_OK,
                     save_fixture_scope(first, 31u, &detail));
    SDK_CHECK_TRUE("save.receipts-address.old-guest-a",
                   save_fixture_run_guest(first, GN_MVS_INPUT_P1_A));
    SDK_CHECK_STATUS("save.receipts-address.old-export", GN_STATUS_OK,
                     save_fixture_export(first, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &old_receipt,
                         &detail));
    gn_destroy(first);
    first = NULL;
    SDK_CHECK_TRUE("save.receipts-address.load-second",
                   save_fixture_load_with_allocator(&allocator, &second));
    if (second == NULL) goto cleanup;
#if !defined(GLUEYNEO_SAVE_ADDRESS_REUSE_UNSUPPORTED)
    SDK_CHECK_TRUE("save.receipts-address-instance-memory-reused",
                   (uintptr_t)second == old_address);
#endif
    SDK_CHECK_STATUS("save.receipts-address.new-scope", GN_STATUS_OK,
                     save_fixture_scope(second, 32u, &detail));
    SDK_CHECK_TRUE("save.receipts-address.new-guest-a",
                   save_fixture_run_guest(second, GN_MVS_INPUT_P1_A));
    SDK_CHECK_STATUS("save.receipts-address-old-ack-rejected",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(second, &old_receipt,
                         sizeof(old_receipt), &detail, sizeof(detail)));
    SDK_CHECK_U64("save.receipts-address-old-ack-reason",
                  GN_MVS_SAVE_REASON_STALE_RECEIPT, detail.reason);
    SDK_CHECK_STATUS("save.receipts-address-pending-query", GN_STATUS_OK,
                     save_fixture_query(second, &info, &detail));
    SDK_CHECK_U64("save.receipts-address-new-pending", 1u, info.dirty);
cleanup:
    free(buffer);
    gn_destroy(first);
    gn_destroy(second);
}

static void save_lineage_counters_do_not_wrap_or_block_guest(void) {
    SDK_CASE("save.receipts.lineage-counter-exhaustion");
    gn_instance *instance = NULL;
    uint8_t *buffer = (uint8_t *)malloc(GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    uint8_t *state = NULL;
    size_t state_size = 0u;
    size_t written = 0u;
    gn_mvs_save_receipt_v1 receipt;
    gn_mvs_save_info_v1 info;
    gn_test_save_observation observed;
    gn_mvs_save_detail_v1 detail;
    uint8_t saved[SAVE_FIXTURE_OUTPUT_COUNT];
    SDK_CHECK_TRUE("save.counter.load", save_fixture_load(&instance));
    SDK_CHECK_TRUE("save.counter.buffer", buffer != NULL);
    if (instance == NULL || buffer == NULL) goto cleanup;
    SDK_CHECK_STATUS("save.counter.scope-1", GN_STATUS_OK,
                     save_fixture_scope(instance, 41u, &detail));
    SDK_CHECK_STATUS("save.counter.seed-mutation", GN_STATUS_OK,
                     gn_test_save_seed_lineage(instance, 1u, 0u,
                                               UINT64_MAX - 1u, 0u));
    SDK_CHECK_TRUE("save.counter.guest-store-at-boundary",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_TRUE("save.counter-byte-word-stores-complete",
                   save_fixture_read_sram(instance, saved) &&
                   memcmp(saved, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.counter.query-mutation-exhausted", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.counter-mutation-pending", 1u, info.dirty);
    SDK_CHECK_U64("save.counter-mutation-latched", 1u, info.exhausted);
    SDK_CHECK_STATUS("save.counter.observe-mutation", GN_STATUS_OK,
                     gn_test_save_observe(instance, &observed));
    SDK_CHECK_U64("save.counter-mutation-does-not-wrap", UINT64_MAX,
                  observed.mutation_sequence);
    SDK_CHECK_STATUS("save.counter.export-refuses-exhaustion",
                     GN_STATUS_INVALID_STATE,
                     save_fixture_export(instance, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         &detail));
    SDK_CHECK_U64("save.counter.export-reason",
                  GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED, detail.reason);
    SDK_CHECK_STATUS("save.counter.scope-renew-mutation", GN_STATUS_OK,
                     save_fixture_scope(instance, 42u, &detail));
    SDK_CHECK_TRUE("save.counter-renew-preserves-sram",
                   save_fixture_read_sram(instance, saved) &&
                   memcmp(saved, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.counter.query-after-renew", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.counter-renew-keeps-pending", 1u, info.dirty);
    SDK_CHECK_U64("save.counter-renew-clears-exhaustion", 0u, info.exhausted);
    SDK_CHECK_STATUS("save.counter.seed-export", GN_STATUS_OK,
                     gn_test_save_seed_lineage(instance, 1u, 0u, 0u,
                                               UINT64_MAX - 1u));
    SDK_CHECK_STATUS("save.counter-export-last-sequence", GN_STATUS_OK,
                     save_fixture_export(instance, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         &detail));
    SDK_CHECK_U64("save.counter-export-at-maximum", UINT64_MAX,
                  receipt.export_sequence);
    written = 99u;
    SDK_CHECK_STATUS("save.counter-export-does-not-wrap",
                     GN_STATUS_INVALID_STATE,
                     save_fixture_export(instance, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         &detail));
    SDK_CHECK_U64("save.counter-export-overflow-reason",
                  GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED, detail.reason);
    SDK_CHECK_U64("save.counter-export-failure-length-zero", 0u, written);
    SDK_CHECK_STATUS("save.counter-overflow-preserves-latest-ack",
                     GN_STATUS_OK,
                     gn_mvs_save_ack_v1(instance, &receipt, sizeof(receipt),
                                        &detail, sizeof(detail)));
    SDK_CHECK_STATUS("save.counter-overflow-ack-query", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.counter-overflow-ack-clears-pending", 0u, info.dirty);
    SDK_CHECK_STATUS("save.counter.scope-renew-export", GN_STATUS_OK,
                     save_fixture_scope(instance, 43u, &detail));
    SDK_CHECK_TRUE("save.counter-export-renew-preserves-sram",
                   save_fixture_read_sram(instance, saved) &&
                   memcmp(saved, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.counter.seed-mutation-overflow-with-receipt",
                     GN_STATUS_OK,
                     gn_test_save_seed_lineage(instance, 1u, 0u, UINT64_MAX,
                                               0u));
    SDK_CHECK_STATUS("save.counter.export-at-mutation-maximum", GN_STATUS_OK,
                     save_fixture_export(instance, buffer,
                         GN_MVS_SAVE_ENVELOPE_V1_BYTES, &written, &receipt,
                         &detail));
    SDK_CHECK_STATUS("save.counter.mutation-overflow-write",
                     GN_STATUS_OK,
                     gn_test_mvs_write_bus8(instance, UINT32_C(0xd00000),
                                            UINT8_C(0x77)));
    SDK_CHECK_STATUS("save.counter.observe-mutation-overflow-with-receipt",
                     GN_STATUS_OK, gn_test_save_observe(instance, &observed));
    SDK_CHECK_U64("save.counter.mutation-overflow-invalidates-receipt", 0u,
                  observed.receipt_valid);
    SDK_CHECK_STATUS("save.counter.mutation-overflow-old-ack-rejected",
                     GN_STATUS_INVALID_STATE,
                     gn_mvs_save_ack_v1(instance, &receipt, sizeof(receipt),
                                        &detail, sizeof(detail)));
    SDK_CHECK_U64("save.counter.mutation-overflow-old-ack-reason",
                  GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED, detail.reason);
    SDK_CHECK_STATUS("save.counter.mutation-overflow-remains-dirty", GN_STATUS_OK,
                     save_fixture_query(instance, &info, &detail));
    SDK_CHECK_U64("save.counter.mutation-overflow-keeps-pending", 1u, info.dirty);
    SDK_CHECK_STATUS("save.counter.scope-renew-mutation-overflow", GN_STATUS_OK,
                     save_fixture_scope(instance, 46u, &detail));
    SDK_CHECK_STATUS("save.counter.restore-a-byte-for-next-boundary",
                     GN_STATUS_OK,
                     gn_test_mvs_write_bus8(instance, UINT32_C(0xd00000),
                                            saved_a[0]));

    SDK_CHECK_TRUE("save.counter-capture-for-restore",
                   save_fixture_capture(instance, &state, &state_size));
    SDK_CHECK_STATUS("save.counter.seed-restore", GN_STATUS_OK,
                     gn_test_save_seed_lineage(instance, 1u, UINT64_MAX - 1u,
                                               0u, 0u));
    SDK_CHECK_TRUE("save.counter-restore-at-maximum",
                   save_fixture_restore(instance, state, state_size));
    SDK_CHECK_STATUS("save.counter.observe-restore-at-maximum", GN_STATUS_OK,
                     gn_test_save_observe(instance, &observed));
    SDK_CHECK_U64("save.counter-restore-does-not-wrap", UINT64_MAX,
                  observed.restore_branch);
    SDK_CHECK_TRUE("save.counter-restore-still-pends", observed.dirty != 0u);
    SDK_CHECK_TRUE("save.counter-second-restore-still-succeeds",
                   save_fixture_restore(instance, state, state_size));
    SDK_CHECK_STATUS("save.counter.observe-restore-exhaustion", GN_STATUS_OK,
                     gn_test_save_observe(instance, &observed));
    SDK_CHECK_U64("save.counter-restore-exhausted", 1u, observed.exhausted);
    SDK_CHECK_U64("save.counter-restore-keeps-maximum", UINT64_MAX,
                  observed.restore_branch);
    SDK_CHECK_STATUS("save.counter.scope-renew-restore", GN_STATUS_OK,
                     save_fixture_scope(instance, 44u, &detail));
    SDK_CHECK_TRUE("save.counter-restore-renew-keeps-sram",
                   save_fixture_read_sram(instance, saved) &&
                   memcmp(saved, saved_a, sizeof(saved_a)) == 0);

    SDK_CHECK_STATUS("save.counter.seed-load", GN_STATUS_OK,
                     gn_test_save_seed_lineage(instance, UINT64_MAX - 1u,
                                               0u, 0u, 0u));
    SDK_CHECK_TRUE("save.counter-load-to-maximum", save_fixture_reload(instance));
    SDK_CHECK_STATUS("save.counter.observe-load-maximum", GN_STATUS_OK,
                     gn_test_save_observe(instance, &observed));
    SDK_CHECK_U64("save.counter-load-does-not-wrap", UINT64_MAX,
                  observed.load_generation);
    SDK_CHECK_TRUE("save.counter-load-overflow-reload", save_fixture_reload(instance));
    SDK_CHECK_STATUS("save.counter.observe-load-exhaustion", GN_STATUS_OK,
                     gn_test_save_observe(instance, &observed));
    SDK_CHECK_U64("save.counter-load-keeps-maximum", UINT64_MAX,
                  observed.load_generation);
    SDK_CHECK_U64("save.counter-load-exhausted", 1u, observed.exhausted);
    SDK_CHECK_TRUE("save.counter-guest-store-after-load-exhaustion",
                   save_fixture_run_guest(instance, GN_MVS_INPUT_P1_A));
    SDK_CHECK_TRUE("save.counter-guest-store-survives-exhaustion",
                   save_fixture_read_sram(instance, saved) &&
                   memcmp(saved, saved_a, sizeof(saved_a)) == 0);
    SDK_CHECK_STATUS("save.counter.scope-renew-load", GN_STATUS_OK,
                     save_fixture_scope(instance, 45u, &detail));
    SDK_CHECK_TRUE("save.counter-load-renew-preserves-sram",
                   save_fixture_read_sram(instance, saved) &&
                   memcmp(saved, saved_a, sizeof(saved_a)) == 0);
cleanup:
    free(state);
    free(buffer);
    gn_destroy(instance);
}

static void run_suite(const char *suite) {
    UnityBegin("tests/sdk/test_save.c");
    if (strcmp(suite, "api") == 0) {
        RUN_TEST(save_api_query_export_bounds_and_atomic_outputs);
        RUN_TEST(save_api_entrypoint_arguments_and_aliases);
        RUN_TEST(save_api_import_rejects_envelopes_atomically);
    } else if (strcmp(suite, "receipts") == 0) {
        RUN_TEST(save_receipts_reject_stale_and_preserve_pending);
        RUN_TEST(save_receipt_scope_survives_allocator_address_reuse);
        RUN_TEST(save_lineage_counters_do_not_wrap_or_block_guest);
    } else if (strcmp(suite, "stale-clean") == 0) {
        stale_clean_negative_control = 1;
        RUN_TEST(save_receipts_reject_stale_and_preserve_pending);
    } else {
        (void)fprintf(stderr, "unknown sdk save suite: %s\n", suite);
        invalid_suite = 1;
        (void)UnityEnd();
        return;
    }
    const int failures = UnityEnd();
    sdk_test_result("sdk-save", failures, GLUEYNEO_SOURCE_REVISION,
                    GLUEYNEO_CONFIGURATION, GLUEYNEO_COMPILER_ID,
                    GLUEYNEO_COMPILER_VERSION);
}

int main(int argc, char **argv) {
    if (argc != 2) {
        (void)fprintf(stderr, "usage: sdk_save_test <api|receipts|stale-clean>\n");
        return 2;
    }
    run_suite(argv[1]);
    if (invalid_suite != 0) return 2;
    return Unity.TestFailures == 0 ? 0 : 1;
}
