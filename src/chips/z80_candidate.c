/* SPDX-License-Identifier: MIT */
#if defined(_MSC_VER)
#pragma warning(push)
/* Pinned chips/Z80 narrows its 32-bit flag intermediates by design. */
#pragma warning(disable: 4244)
#endif
#define CHIPS_IMPL
#include "z80_candidate.h"
#if defined(_MSC_VER)
#pragma warning(pop)
#endif

#include <stdlib.h>

enum { Z80_CANDIDATE_SNAPSHOT_VERSION = 1 };

struct z80_candidate {
    z80_t cpu;
    z80_candidate_bus_fn bus;
    void *userdata;
    uint64_t pins;
    uint64_t cycles;
    bool bus_failed;
};

static z80_candidate_status service_bus(z80_candidate *candidate) {
    uint64_t pins = candidate->pins;
    z80_candidate_bus_kind kind;
    uint8_t data;

    if ((pins & Z80_IORQ) != 0u) {
        if ((pins & Z80_M1) != 0u) {
            kind = Z80_CANDIDATE_BUS_INTERRUPT_ACK;
        } else if ((pins & Z80_RD) != 0u) {
            kind = Z80_CANDIDATE_BUS_IO_READ;
        } else if ((pins & Z80_WR) != 0u) {
            kind = Z80_CANDIDATE_BUS_IO_WRITE;
        } else {
            return Z80_CANDIDATE_OK;
        }
    } else if ((pins & Z80_MREQ) != 0u) {
        if ((pins & Z80_RD) != 0u) {
            kind = Z80_CANDIDATE_BUS_MEMORY_READ;
        } else if ((pins & Z80_WR) != 0u) {
            kind = Z80_CANDIDATE_BUS_MEMORY_WRITE;
        } else {
            return Z80_CANDIDATE_OK;
        }
    } else {
        return Z80_CANDIDATE_OK;
    }

    data = Z80_GET_DATA(pins);
    if (candidate->bus(candidate->userdata, kind, Z80_GET_ADDR(pins), &data) == 0) {
        candidate->bus_failed = true;
        return Z80_CANDIDATE_BUS_FAILURE;
    }
    if (kind == Z80_CANDIDATE_BUS_MEMORY_READ ||
        kind == Z80_CANDIDATE_BUS_IO_READ ||
        kind == Z80_CANDIDATE_BUS_INTERRUPT_ACK) {
        Z80_SET_DATA(pins, data);
        candidate->pins = pins;
    }
    return Z80_CANDIDATE_OK;
}

z80_candidate_status z80_candidate_create(z80_candidate_bus_fn bus, void *userdata,
                                          z80_candidate **out_candidate) {
    if (bus == NULL || out_candidate == NULL) return Z80_CANDIDATE_INVALID_ARGUMENT;
    *out_candidate = NULL;
    z80_candidate *candidate = calloc(1u, sizeof(*candidate));
    if (candidate == NULL) return Z80_CANDIDATE_OUT_OF_MEMORY;
    candidate->bus = bus;
    candidate->userdata = userdata;
    candidate->pins = z80_init(&candidate->cpu);
    *out_candidate = candidate;
    return Z80_CANDIDATE_OK;
}

void z80_candidate_destroy(z80_candidate *candidate) {
    free(candidate);
}

z80_candidate_status z80_candidate_reset(z80_candidate *candidate) {
    if (candidate == NULL) return Z80_CANDIDATE_INVALID_ARGUMENT;
    candidate->pins = z80_reset(&candidate->cpu);
    candidate->cycles = 0u;
    candidate->bus_failed = false;
    return Z80_CANDIDATE_OK;
}

z80_candidate_status z80_candidate_tick(z80_candidate *candidate, bool irq,
                                        bool nmi, z80_candidate_tick_result *result) {
    if (candidate == NULL || result == NULL) return Z80_CANDIDATE_INVALID_ARGUMENT;
    *result = (z80_candidate_tick_result){0};
    if (candidate->bus_failed) {
        result->status = Z80_CANDIDATE_BUS_FAILURE;
        result->cycles = candidate->cycles;
        result->pins = candidate->pins;
        return result->status;
    }
    if (candidate->cycles == UINT64_MAX) {
        result->status = Z80_CANDIDATE_CYCLE_LIMIT;
        result->cycles = candidate->cycles;
        result->pins = candidate->pins;
        return result->status;
    }

    candidate->pins &= ~(Z80_INT | Z80_NMI);
    if (irq) candidate->pins |= Z80_INT;
    if (nmi) candidate->pins |= Z80_NMI;
    candidate->pins = z80_tick(&candidate->cpu, candidate->pins);
    candidate->cycles++;
    result->status = service_bus(candidate);
    result->cycles = candidate->cycles;
    result->pins = candidate->pins;
    result->instruction_complete = z80_opdone(&candidate->cpu);
    return result->status;
}

z80_candidate_status z80_candidate_capture(const z80_candidate *candidate,
                                           z80_candidate_snapshot *snapshot) {
    if (candidate == NULL || snapshot == NULL || candidate->bus_failed) {
        return Z80_CANDIDATE_INVALID_ARGUMENT;
    }
    snapshot->version = Z80_CANDIDATE_SNAPSHOT_VERSION;
    snapshot->cpu = candidate->cpu;
    snapshot->pins = candidate->pins;
    snapshot->cycles = candidate->cycles;
    return Z80_CANDIDATE_OK;
}

z80_candidate_status z80_candidate_restore(z80_candidate *candidate,
                                           const z80_candidate_snapshot *snapshot) {
    if (candidate == NULL) return Z80_CANDIDATE_INVALID_ARGUMENT;
    if (candidate->bus_failed) return Z80_CANDIDATE_BUS_FAILURE;
    if (snapshot == NULL ||
        snapshot->version != Z80_CANDIDATE_SNAPSHOT_VERSION ||
        (snapshot->pins & ~Z80_PIN_MASK) != 0u) {
        return Z80_CANDIDATE_INVALID_SNAPSHOT;
    }
    candidate->cpu = snapshot->cpu;
    candidate->pins = snapshot->pins;
    candidate->cycles = snapshot->cycles;
    candidate->bus_failed = false;
    return Z80_CANDIDATE_OK;
}
