/* SPDX-License-Identifier: MIT */
#include "save_fixture.h"

#include <stdlib.h>
#include <string.h>

static const uint32_t save_offsets[SAVE_FIXTURE_OUTPUT_COUNT] = {
    0u, 1u, 0x1234u, 0x1235u, 0xfffeu, 0xffffu
};

static uint32_t read_u32be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

int save_fixture_manifest_from_bundle(
    const uint8_t *bundle, size_t bundle_size,
    gn_mvs_manifest_v3 *out_manifest) {
    if (bundle == NULL || out_manifest == NULL ||
        bundle_size < 16u + GN_MVS_V3_MAX_REGIONS * 12u ||
        memcmp(bundle, "GNMV", 4u) != 0 ||
        read_u32be(bundle + 4u) != GN_MVS_MANIFEST_VERSION_ZOOM ||
        read_u32be(bundle + 8u) != GN_MVS_PROFILE_MSX ||
        read_u32be(bundle + 12u) != GN_MVS_V3_MAX_REGIONS)
        return 0;
    gn_mvs_manifest_v3 manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    manifest.region_count = GN_MVS_V3_MAX_REGIONS;
    size_t cursor = 16u;
    for (size_t index = 0u; index < GN_MVS_V3_MAX_REGIONS; ++index) {
        if (cursor > bundle_size || bundle_size - cursor < 12u) return 0;
        const uint32_t role = read_u32be(bundle + cursor);
        const uint32_t reserved = read_u32be(bundle + cursor + 4u);
        const uint32_t extent = read_u32be(bundle + cursor + 8u);
        cursor += 12u;
        if (role != index + 1u || reserved != 0u || extent == 0u ||
            (size_t)extent > bundle_size - cursor)
            return 0;
        manifest.regions[index] = (gn_mvs_region){
            (gn_mvs_region_role)role, bundle + cursor, (size_t)extent,
            (size_t)extent, GN_MVS_LAYOUT_LINEAR
        };
        cursor += (size_t)extent;
    }
    if (cursor != bundle_size) return 0;
    *out_manifest = manifest;
    return 1;
}

static uint8_t *save_fixture_bundle(size_t *out_bundle_size) {
    if (out_bundle_size == NULL) return NULL;
    *out_bundle_size = 0u;
    const size_t bundle_size = public_save_guest_size();
    if (bundle_size == 0u || bundle_size > SAVE_FIXTURE_BUNDLE_BYTES)
        return NULL;
    uint8_t *bundle = (uint8_t *)malloc(bundle_size);
    if (bundle == NULL || !public_save_guest_build(bundle, bundle_size)) {
        free(bundle);
        return NULL;
    }
    *out_bundle_size = bundle_size;
    return bundle;
}

int save_fixture_reload(gn_instance *instance) {
    if (instance == NULL) return 0;
    size_t bundle_size = 0u;
    uint8_t *bundle = save_fixture_bundle(&bundle_size);
    if (bundle == NULL) return 0;
    gn_mvs_manifest_v3 manifest;
    if (!save_fixture_manifest_from_bundle(bundle, bundle_size, &manifest)) {
        free(bundle);
        return 0;
    }
    const gn_status status = gn_load_mvs_v3(instance, &manifest);
    free(bundle);
    return status == GN_STATUS_OK;
}

gn_status save_fixture_reload_checked(
    gn_instance *instance, gn_mvs_save_lifecycle_policy_v1 policy,
    uint32_t host_work_resolved, gn_mvs_save_lifecycle_result_v1 *out_result,
    gn_mvs_save_detail_v1 *detail) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    size_t bundle_size = 0u;
    uint8_t *bundle = save_fixture_bundle(&bundle_size);
    if (bundle == NULL) return GN_STATUS_OUT_OF_MEMORY;
    gn_mvs_manifest_v3 manifest;
    if (!save_fixture_manifest_from_bundle(bundle, bundle_size, &manifest)) {
        free(bundle);
        return GN_STATUS_INVALID_MEDIA;
    }
    const gn_status status = gn_load_mvs_v3_checked_v1(
        instance, &manifest, policy, host_work_resolved, out_result,
        out_result == NULL ? 0u : sizeof(*out_result), detail,
        detail == NULL ? 0u : sizeof(*detail));
    free(bundle);
    return status;
}

int save_fixture_load_with_allocator(gn_test_allocator *allocator,
                                     gn_instance **out_instance) {
    if (out_instance == NULL) return 0;
    *out_instance = NULL;
    const gn_status status = allocator == NULL
        ? gn_create(out_instance) : gn_test_create(allocator, out_instance);
    if (status != GN_STATUS_OK || *out_instance == NULL) {
        gn_destroy(*out_instance);
        *out_instance = NULL;
        return 0;
    }
    if (!save_fixture_reload(*out_instance)) {
        gn_destroy(*out_instance);
        *out_instance = NULL;
        return 0;
    }
    return 1;
}

int save_fixture_load(gn_instance **out_instance) {
    return save_fixture_load_with_allocator(NULL, out_instance);
}

int save_fixture_run_guest(gn_instance *instance, uint32_t input_mask) {
    if (instance == NULL ||
        gn_set_mvs_inputs(instance, input_mask) != GN_STATUS_OK)
        return 0;
    gn_run_result result;
    memset(&result, 0, sizeof(result));
    const gn_status status = gn_run_mvs(instance, UINT64_C(5000), &result);
    return status == GN_STATUS_OK && result.reason != GN_RUN_ERROR &&
        result.reason != GN_RUN_FAULT && result.reason != GN_RUN_STOPPED;
}

int save_fixture_read_guest_output(
    const gn_instance *instance, uint8_t output[SAVE_FIXTURE_OUTPUT_COUNT]) {
    if (instance == NULL || output == NULL) return 0;
    for (size_t index = 0u; index < SAVE_FIXTURE_OUTPUT_COUNT; ++index) {
        if (gn_test_mvs_read_bus8(instance, UINT32_C(0x100000) +
                                  (uint32_t)index, &output[index]) != GN_STATUS_OK)
            return 0;
    }
    return 1;
}

int save_fixture_read_sram(
    const gn_instance *instance, uint8_t output[SAVE_FIXTURE_OUTPUT_COUNT]) {
    if (instance == NULL || output == NULL) return 0;
    for (size_t index = 0u; index < SAVE_FIXTURE_OUTPUT_COUNT; ++index) {
        if (gn_test_mvs_read_bus8(instance, UINT32_C(0xd00000) +
                                  save_offsets[index], &output[index]) != GN_STATUS_OK)
            return 0;
    }
    return 1;
}

int save_fixture_capture(gn_instance *instance, uint8_t **out_state,
                         size_t *out_size) {
    if (out_state == NULL || out_size == NULL) return 0;
    *out_state = NULL;
    *out_size = 0u;
    size_t capacity = 0u;
    if (gn_state_capacity_v1(instance, &capacity) != GN_STATUS_OK ||
        capacity == 0u) return 0;
    uint8_t *state = (uint8_t *)malloc(capacity);
    if (state == NULL) return 0;
    size_t written = 0u;
    gn_state_detail_v1 detail;
    const gn_status status = gn_state_capture_v1(
        instance, state, capacity, &written, &detail, sizeof(detail));
    if (status != GN_STATUS_OK || written != capacity) {
        free(state);
        return 0;
    }
    *out_state = state;
    *out_size = written;
    return 1;
}

int save_fixture_restore(gn_instance *instance, const uint8_t *state,
                         size_t size) {
    gn_state_detail_v1 detail;
    return gn_state_restore_v1(instance, state, size, &detail,
                               sizeof(detail)) == GN_STATUS_OK;
}

void save_fixture_set_scope(gn_mvs_save_scope_v1 *scope,
                            uint8_t discriminator) {
    memset(scope, 0, sizeof(*scope));
    scope->size = (uint32_t)sizeof(*scope);
    scope->scope[0] = discriminator;
    scope->scope[15] = (uint8_t)(discriminator ^ 0xa5u);
}

gn_status save_fixture_scope(gn_instance *instance, uint8_t discriminator,
                             gn_mvs_save_detail_v1 *detail) {
    gn_mvs_save_scope_v1 scope;
    save_fixture_set_scope(&scope, discriminator);
    return gn_mvs_save_scope_renew_v1(instance, &scope, sizeof(scope), detail,
                                      detail == NULL ? 0u : sizeof(*detail));
}

gn_status save_fixture_export(gn_instance *instance, uint8_t *buffer,
                              size_t capacity, size_t *out_written,
                              gn_mvs_save_receipt_v1 *receipt,
                              gn_mvs_save_detail_v1 *detail) {
    return gn_mvs_save_export_v1(instance, buffer, capacity, out_written,
                                 receipt, sizeof(*receipt), detail,
                                 detail == NULL ? 0u : sizeof(*detail));
}

gn_status save_fixture_query(const gn_instance *instance,
                             gn_mvs_save_info_v1 *out_info,
                             gn_mvs_save_detail_v1 *detail) {
    return gn_mvs_save_query_v1(instance, out_info, sizeof(*out_info), detail,
                                detail == NULL ? 0u : sizeof(*detail));
}
