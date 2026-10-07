/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_Z80_CANDIDATE_H
#define GLUEYNEO_Z80_CANDIDATE_H

#include "z80.h"

#include <stdbool.h>
#include <stdint.h>

typedef struct z80_candidate z80_candidate;

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

z80_candidate_status z80_candidate_create(z80_candidate_bus_fn bus, void *userdata,
                                          z80_candidate **out_candidate);
void z80_candidate_destroy(z80_candidate *candidate);
z80_candidate_status z80_candidate_reset(z80_candidate *candidate);
z80_candidate_status z80_candidate_tick(z80_candidate *candidate, bool irq,
                                        bool nmi, z80_candidate_tick_result *result);
z80_candidate_status z80_candidate_capture(const z80_candidate *candidate,
                                           z80_candidate_snapshot *snapshot);
z80_candidate_status z80_candidate_restore(z80_candidate *candidate,
                                           const z80_candidate_snapshot *snapshot);

#endif
