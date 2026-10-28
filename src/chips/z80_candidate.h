/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_Z80_CANDIDATE_H
#define GLUEYNEO_Z80_CANDIDATE_H

#include "z80.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct z80_candidate z80_candidate;
typedef struct z80_candidate_state z80_candidate_state;

#if defined(Z80_CANDIDATE_TEST_HOOKS)
/* Test-only private allocator accounting; never part of the public SDK ABI. */
typedef struct {
    size_t fail_at;
    size_t attempts;
    size_t allocations;
    size_t frees;
    size_t live_bytes;
    size_t high_water_bytes;
    uint32_t failed_site;
    uint8_t bypass_validation;
} z80_candidate_test_failpoint;

typedef enum {
    Z80_CANDIDATE_TEST_SITE_NONE = 0,
    Z80_CANDIDATE_TEST_SITE_STAGE_STATE = 1,
    Z80_CANDIDATE_TEST_SITE_CREATE_REPLACEMENT = 2
} z80_candidate_test_site;
#endif

typedef enum {
    Z80_CANDIDATE_BUS_MEMORY_READ = 0,
    Z80_CANDIDATE_BUS_MEMORY_WRITE,
    Z80_CANDIDATE_BUS_IO_READ,
    Z80_CANDIDATE_BUS_IO_WRITE,
    Z80_CANDIDATE_BUS_INTERRUPT_ACK
} z80_candidate_bus_kind;

typedef enum {
    Z80_CANDIDATE_OK = 0,
    Z80_CANDIDATE_INVALID_ARGUMENT,
    Z80_CANDIDATE_OUT_OF_MEMORY,
    Z80_CANDIDATE_CYCLE_LIMIT,
    Z80_CANDIDATE_BUS_FAILURE,
    Z80_CANDIDATE_INVALID_SNAPSHOT
} z80_candidate_status;

/* The callback is borrowed and called synchronously by tick on this instance. */
typedef int (*z80_candidate_bus_fn)(void *userdata, z80_candidate_bus_kind kind,
                                    uint16_t address, uint8_t *data);

typedef struct {
    z80_candidate_status status;
    uint64_t cycles;
    uint64_t pins;
    bool instruction_complete;
} z80_candidate_tick_result;

/* Internal continuation record; bus memory and callback ownership stay external. */
typedef struct {
    uint32_t version;
    z80_t cpu;
    uint64_t pins;
    uint64_t cycles;
} z80_candidate_snapshot;

/* Private, pointer-free canonical continuation format. */
size_t z80_candidate_state_size(void);
z80_candidate_status z80_candidate_state_capture(const z80_candidate *candidate,
                                                 void *bytes, size_t capacity,
                                                 size_t *written);
z80_candidate_status z80_candidate_state_stage(const void *bytes, size_t length,
                                               z80_candidate_state **out_state);
#if defined(Z80_CANDIDATE_TEST_HOOKS)
z80_candidate_status z80_candidate_state_test_stage(
    const void *bytes, size_t length,
    z80_candidate_test_failpoint *failpoint, z80_candidate_state **out_state);
#endif
void z80_candidate_state_discard(z80_candidate_state *state);
/* Bind a validated state to a healthy destination before its no-fail apply. */
z80_candidate_status z80_candidate_state_rebind(z80_candidate_state *state,
                                                const z80_candidate *destination);
/* Applies only after rebind succeeded for this exact destination. */
void z80_candidate_state_apply(z80_candidate *destination,
                               const z80_candidate_state *state);
/* Concrete storage for one import, including the decoder's stack guest copy. */
size_t z80_candidate_state_heap_bound(void);
size_t z80_candidate_state_stack_bound(void);

z80_candidate_status z80_candidate_create(z80_candidate_bus_fn bus, void *userdata,
                                          z80_candidate **out_candidate);
#if defined(Z80_CANDIDATE_TEST_HOOKS)
z80_candidate_status z80_candidate_test_create(
    z80_candidate_bus_fn bus, void *userdata,
    z80_candidate_test_failpoint *failpoint, z80_candidate **out_candidate);
#endif
void z80_candidate_destroy(z80_candidate *candidate);
z80_candidate_status z80_candidate_reset(z80_candidate *candidate);
z80_candidate_status z80_candidate_tick(z80_candidate *candidate, bool irq,
                                        bool nmi, z80_candidate_tick_result *result);
z80_candidate_status z80_candidate_capture(const z80_candidate *candidate,
                                           z80_candidate_snapshot *snapshot);
z80_candidate_status z80_candidate_restore(z80_candidate *candidate,
                                           const z80_candidate_snapshot *snapshot);

#endif
