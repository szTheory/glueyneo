/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_SDK_PRIVATE_H
#define GLUEYNEO_SDK_PRIVATE_H

#include "glueyneo/glueyneo.h"
#include "../experiments/owned_cpu/cpu.h"

gn_status gn_private_mvs_fetch_trace(
    const gn_instance *instance, owned_cpu_fetch_trace_event *events,
    size_t capacity, size_t *out_count);

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
typedef struct {
    size_t fail_at;
    size_t attempts;
    size_t total_attempts;
    size_t live_allocations;
    size_t live_bytes;
} gn_test_allocator;

#define GN_TEST_TRACE_CAPACITY 256u

typedef enum {
    GN_TEST_BUS_READ = 0,
    GN_TEST_BUS_WRITE = 1
} gn_test_bus_direction;

typedef struct {
    uint32_t address;
    uint16_t value;
    uint8_t width_bits;
    uint8_t direction;
} gn_test_bus_event;

typedef enum {
    GN_TEST_MUTATION_NONE = 0,
    GN_TEST_MUTATION_BSS_READ,
    GN_TEST_MUTATION_RUN_ELAPSED,
    GN_TEST_MUTATION_RUN_INSTRUCTIONS,
    GN_TEST_MUTATION_RUN_STOP_REASON,
    GN_TEST_MUTATION_OBSERVATION_BYTE_ORDER,
    GN_TEST_MUTATION_TRACE_ORDER
} gn_test_mutation;

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
gn_status gn_test_set_mutation(gn_instance *instance, gn_test_mutation mutation);
gn_status gn_test_trace_clear(gn_instance *instance);
gn_status gn_test_trace_read(const gn_instance *instance,
                             gn_test_bus_event *events, size_t capacity,
                             size_t *out_count, size_t *out_dropped);
gn_status gn_test_mvs_read_work_ram(const gn_instance *instance,
                                   uint32_t address, uint16_t *out_value);
gn_status gn_test_mvs_read_bus(const gn_instance *instance,
                               uint32_t address, uint16_t *out_value);
#endif

#endif
