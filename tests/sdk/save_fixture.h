/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_SDK_SAVE_FIXTURE_H
#define GLUEYNEO_SDK_SAVE_FIXTURE_H

#include "glueyneo/glueyneo.h"
#include "sdk_private.h"

#include <stddef.h>
#include <stdint.h>

#define SAVE_FIXTURE_OUTPUT_COUNT 6u
#define SAVE_FIXTURE_BUNDLE_BYTES ((size_t)67108976u)

extern size_t public_save_guest_size(void);
extern int public_save_guest_build(uint8_t *bundle, size_t capacity);

int save_fixture_manifest_from_bundle(
    const uint8_t *bundle, size_t bundle_size, gn_mvs_manifest_v3 *out_manifest);
int save_fixture_load(gn_instance **out_instance);
int save_fixture_load_with_allocator(gn_test_allocator *allocator,
                                     gn_instance **out_instance);
int save_fixture_reload(gn_instance *instance);
gn_status save_fixture_reload_checked(
    gn_instance *instance, gn_mvs_save_lifecycle_policy_v1 policy,
    uint32_t host_work_resolved, gn_mvs_save_lifecycle_result_v1 *out_result,
    gn_mvs_save_detail_v1 *detail);
int save_fixture_run_guest(gn_instance *instance, uint32_t input_mask);
int save_fixture_read_guest_output(
    const gn_instance *instance, uint8_t output[SAVE_FIXTURE_OUTPUT_COUNT]);
int save_fixture_read_sram(
    const gn_instance *instance, uint8_t output[SAVE_FIXTURE_OUTPUT_COUNT]);
int save_fixture_capture(gn_instance *instance, uint8_t **out_state,
                         size_t *out_size);
int save_fixture_restore(gn_instance *instance, const uint8_t *state,
                         size_t size);
void save_fixture_set_scope(gn_mvs_save_scope_v1 *scope, uint8_t discriminator);
gn_status save_fixture_scope(gn_instance *instance, uint8_t discriminator,
                             gn_mvs_save_detail_v1 *detail);
gn_status save_fixture_export(gn_instance *instance, uint8_t *buffer,
                              size_t capacity, size_t *out_written,
                              gn_mvs_save_receipt_v1 *receipt,
                              gn_mvs_save_detail_v1 *detail);
gn_status save_fixture_query(const gn_instance *instance,
                             gn_mvs_save_info_v1 *out_info,
                             gn_mvs_save_detail_v1 *detail);

#endif
