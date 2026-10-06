/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_SDK_PRIVATE_H
#define GLUEYNEO_SDK_PRIVATE_H

#include "glueyneo/glueyneo.h"

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
typedef struct {
    size_t fail_at;
    size_t attempts;
    size_t total_attempts;
    size_t live_allocations;
    size_t live_bytes;
} gn_test_allocator;

void gn_test_allocator_init(gn_test_allocator *allocator);
void gn_test_allocator_arm(gn_test_allocator *allocator, size_t fail_at);
void gn_test_allocator_disarm(gn_test_allocator *allocator);
gn_status gn_test_create(gn_test_allocator *allocator,
                         gn_instance **out_instance);
gn_status gn_test_validate_region_layout(const gn_manifest *manifest);
gn_status gn_test_image_digest(const gn_instance *instance, uint64_t *out_digest);
gn_status gn_test_seed_counters(gn_instance *instance, uint64_t instructions,
                                uint64_t instruction_cycles,
                                uint64_t exception_cycles,
                                uint64_t idle_cycles, uint64_t total_cycles);
gn_status gn_test_fail_next_bus_callback(gn_instance *instance);
#endif

#endif
