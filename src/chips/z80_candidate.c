/* SPDX-License-Identifier: MIT */
#define CHIPS_IMPL
#if defined(_MSC_VER)
/* C4702 (unreachable code in the pinned z80.h decoder) comes from code
   generation, which /external:W0 does not cover. */
#pragma warning(push)
#pragma warning(disable : 4702)
#endif
#include "z80_candidate.h"
#if defined(_MSC_VER)
#pragma warning(pop)
#endif

#include <stdlib.h>

enum { Z80_CANDIDATE_SNAPSHOT_VERSION = 1 };
enum { Z80_CANDIDATE_STATE_VERSION = 1, Z80_CANDIDATE_STATE_BYTES = 76 };

static const uint8_t z80_state_magic[4] = {'G', 'Z', '8', '0'};

struct z80_candidate {
    z80_t cpu;
    z80_candidate_bus_fn bus;
    void *userdata;
    uint64_t pins;
    uint64_t cycles;
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate_test_failpoint *test_failpoint;
#endif
    bool bus_failed;
};

struct z80_candidate_state {
    z80_t cpu;
    z80_candidate_bus_fn bus;
    void *userdata;
    z80_candidate *rebind_target;
    uint64_t pins;
    uint64_t cycles;
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate_test_failpoint *test_failpoint;
#endif
};

size_t z80_candidate_state_heap_bound(void) {
    return sizeof(z80_candidate_state) + sizeof(z80_candidate);
}

size_t z80_candidate_state_stack_bound(void) {
    return sizeof(z80_t) + 2u * sizeof(uint64_t);
}

#if defined(Z80_CANDIDATE_TEST_HOOKS)
static void *candidate_calloc(z80_candidate_test_failpoint *failpoint,
                              size_t count, size_t size, uint32_t site) {
    if (count != 0u && size > SIZE_MAX / count) return NULL;
    const size_t bytes = count * size;
    if (failpoint != NULL) {
        if (failpoint->attempts == SIZE_MAX) return NULL;
        ++failpoint->attempts;
        if (failpoint->fail_at != 0u &&
            failpoint->attempts == failpoint->fail_at) {
            failpoint->failed_site = site;
            return NULL;
        }
    }
    void *allocation = calloc(count, size);
    if (allocation != NULL && failpoint != NULL) {
        ++failpoint->allocations;
        if (bytes > SIZE_MAX - failpoint->live_bytes) {
            free(allocation);
            --failpoint->allocations;
            return NULL;
        }
        failpoint->live_bytes += bytes;
        if (failpoint->live_bytes > failpoint->high_water_bytes)
            failpoint->high_water_bytes = failpoint->live_bytes;
    }
    return allocation;
}

static void candidate_free(z80_candidate_test_failpoint *failpoint,
                           void *allocation, size_t bytes) {
    if (allocation == NULL) return;
    if (failpoint != NULL && failpoint->frees < failpoint->allocations) {
        ++failpoint->frees;
        if (bytes <= failpoint->live_bytes) failpoint->live_bytes -= bytes;
        else failpoint->live_bytes = SIZE_MAX;
    }
    free(allocation);
}
#endif

static uint16_t read_u16_be(const uint8_t *bytes) {
    return (uint16_t)(((uint16_t)bytes[0] << 8) | bytes[1]);
}

static uint64_t read_u64_be(const uint8_t *bytes) {
    uint64_t value = 0u;
    for (size_t index = 0u; index < 8u; ++index) {
        value = (value << 8) | bytes[index];
    }
    return value;
}

static void write_u16_be(uint8_t *bytes, uint16_t value) {
    bytes[0] = (uint8_t)(value >> 8);
    bytes[1] = (uint8_t)value;
}

static void write_u64_be(uint8_t *bytes, uint64_t value) {
    for (size_t index = 0u; index < 8u; ++index) {
        bytes[7u - index] = (uint8_t)value;
        value >>= 8;
    }
}

static bool valid_decoder_state(const z80_t *cpu, uint64_t pins) {
    const uint64_t data_mask = UINT64_C(0xFF) << 16;
    const uint64_t control_mask = ~data_mask;
    const uint64_t interrupt_mask = Z80_INT | Z80_NMI;

    if (cpu->step > Z80_M1_T4 || cpu->hlx_idx > 2u || cpu->im > 2u ||
        (pins & ~Z80_PIN_MASK) != 0u || (cpu->pins & ~Z80_PIN_MASK) != 0u ||
        (cpu->int_bits & ~interrupt_mask) != 0u ||
        ((cpu->pins ^ pins) & control_mask) != 0u ||
        ((cpu->int_bits ^ pins) & Z80_INT) != 0u ||
        (cpu->hlx_idx != 0u && !cpu->prefix_active)) {
        return false;
    }

    /* _z80_fetch_dd/fd, _z80_fetch_cb/ed and _z80_fetch in z80.h:993-1030. */
    if (cpu->step >= Z80_DDFD_M1_T2 && cpu->step <= Z80_DDFD_LDHLN_OVERLAPPED) {
        if (cpu->step == Z80_DDFD_M1_T2 &&
            ((cpu->hlx_idx == 1u && cpu->opcode != 0xDDu) ||
             (cpu->hlx_idx == 2u && cpu->opcode != 0xFDu))) {
            return false;
        }
        return cpu->prefix_active && cpu->hlx_idx != 0u;
    }
    if (cpu->step >= Z80_CB_M1_T2 && cpu->step <= Z80_CB_M1_T4) {
        return cpu->prefix_active && cpu->hlx_idx == 0u &&
               (cpu->step != Z80_CB_M1_T2 || cpu->opcode == 0xCBu);
    }
    if (cpu->step >= Z80_ED_M1_T2 && cpu->step <= Z80_ED_M1_T4) {
        return cpu->prefix_active && cpu->hlx_idx == 0u &&
               (cpu->step != Z80_ED_M1_T2 || cpu->opcode == 0xEDu);
    }
    if (cpu->step >= Z80_M1_T2) {
        return !cpu->prefix_active && cpu->hlx_idx == 0u;
    }
    if (cpu->step >= Z80_INT_IM0_STEP && cpu->step <= 1673u) {
        if (cpu->prefix_active || cpu->hlx_idx != 0u) return false;
        if (cpu->step <= 1641u) return cpu->im == 0u;
        if (cpu->step <= 1654u) return cpu->im == 1u;
        return cpu->im == 2u;
    }
    if (cpu->step >= Z80_NMI_STEP && cpu->step <= 1684u) {
        return !cpu->prefix_active && cpu->hlx_idx == 0u;
    }
    if (cpu->step >= 1612u && cpu->step <= 1620u) {
        return cpu->prefix_active && cpu->hlx_idx == 0u;
    }
    if (cpu->step >= 1621u && cpu->step <= 1635u) {
        return cpu->prefix_active && cpu->hlx_idx != 0u;
    }
    if (cpu->step >= 256u && cpu->step <= 511u) {
        return cpu->prefix_active && cpu->hlx_idx == 0u &&
               cpu->step == (uint16_t)(256u + cpu->opcode);
    }
    if (cpu->step <= 255u) {
        return cpu->step == cpu->opcode &&
               cpu->prefix_active == (cpu->hlx_idx != 0u);
    }
    return cpu->hlx_idx == 0u || cpu->prefix_active;
}

static size_t encode_cpu(uint8_t *bytes, const z80_t *cpu, uint64_t pins,
                         uint64_t cycles) {
    size_t offset = 0u;
    for (size_t index = 0u; index < sizeof(z80_state_magic); ++index) {
        bytes[offset++] = z80_state_magic[index];
    }
    bytes[offset++] = Z80_CANDIDATE_STATE_VERSION;
#define PUT_U16(field) do { write_u16_be(&bytes[offset], cpu->field); offset += 2u; } while (0)
#define PUT_U8(field) do { bytes[offset++] = cpu->field; } while (0)
    PUT_U16(step);
    PUT_U16(addr);
    PUT_U8(dlatch);
    PUT_U8(opcode);
    PUT_U8(hlx_idx);
    bytes[offset++] = cpu->prefix_active ? 1u : 0u;
    write_u64_be(&bytes[offset], cpu->pins); offset += 8u;
    write_u64_be(&bytes[offset], cpu->int_bits); offset += 8u;
    PUT_U16(pc);
    PUT_U16(af);
    PUT_U16(bc);
    PUT_U16(de);
    PUT_U16(hl);
    PUT_U16(ix);
    PUT_U16(iy);
    PUT_U16(wz);
    PUT_U16(sp);
    PUT_U16(ir);
    PUT_U16(af2);
    PUT_U16(bc2);
    PUT_U16(de2);
    PUT_U16(hl2);
    PUT_U8(im);
    bytes[offset++] = cpu->iff1 ? 1u : 0u;
    bytes[offset++] = cpu->iff2 ? 1u : 0u;
    write_u64_be(&bytes[offset], pins); offset += 8u;
    write_u64_be(&bytes[offset], cycles); offset += 8u;
#undef PUT_U16
#undef PUT_U8
    return offset;
}

static bool decode_cpu(const uint8_t *bytes, z80_t *cpu, uint64_t *pins,
                       uint64_t *cycles) {
    size_t offset = 5u;
    uint8_t prefix_active;
    uint8_t iff1;
    uint8_t iff2;
    for (size_t index = 0u; index < sizeof(z80_state_magic); ++index) {
        if (bytes[index] != z80_state_magic[index]) return false;
    }
    if (bytes[4] != Z80_CANDIDATE_STATE_VERSION) return false;
#define GET_U16(field) do { cpu->field = read_u16_be(&bytes[offset]); offset += 2u; } while (0)
#define GET_U8(field) do { cpu->field = bytes[offset++]; } while (0)
    GET_U16(step);
    GET_U16(addr);
    GET_U8(dlatch);
    GET_U8(opcode);
    GET_U8(hlx_idx);
    prefix_active = bytes[offset++];
    cpu->pins = read_u64_be(&bytes[offset]); offset += 8u;
    cpu->int_bits = read_u64_be(&bytes[offset]); offset += 8u;
    GET_U16(pc);
    GET_U16(af);
    GET_U16(bc);
    GET_U16(de);
    GET_U16(hl);
    GET_U16(ix);
    GET_U16(iy);
    GET_U16(wz);
    GET_U16(sp);
    GET_U16(ir);
    GET_U16(af2);
    GET_U16(bc2);
    GET_U16(de2);
    GET_U16(hl2);
    GET_U8(im);
    iff1 = bytes[offset++];
    iff2 = bytes[offset++];
    *pins = read_u64_be(&bytes[offset]); offset += 8u;
    *cycles = read_u64_be(&bytes[offset]); offset += 8u;
#undef GET_U16
#undef GET_U8
    if (offset != Z80_CANDIDATE_STATE_BYTES || prefix_active > 1u ||
        iff1 > 1u || iff2 > 1u) {
        return false;
    }
    cpu->prefix_active = prefix_active != 0u;
    cpu->iff1 = iff1 != 0u;
    cpu->iff2 = iff2 != 0u;
    return valid_decoder_state(cpu, *pins);
}

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

static z80_candidate_status candidate_create(
    z80_candidate_bus_fn bus, void *userdata,
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate_test_failpoint *failpoint,
#endif
    z80_candidate **out_candidate) {
    if (bus == NULL || out_candidate == NULL) return Z80_CANDIDATE_INVALID_ARGUMENT;
    *out_candidate = NULL;
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate *candidate = candidate_calloc(failpoint, 1u,
        sizeof(*candidate), Z80_CANDIDATE_TEST_SITE_CREATE_REPLACEMENT);
#else
    z80_candidate *candidate = calloc(1u, sizeof(*candidate));
#endif
    if (candidate == NULL) return Z80_CANDIDATE_OUT_OF_MEMORY;
    candidate->bus = bus;
    candidate->userdata = userdata;
    candidate->pins = z80_init(&candidate->cpu);
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    candidate->test_failpoint = failpoint;
#endif
    *out_candidate = candidate;
    return Z80_CANDIDATE_OK;
}

z80_candidate_status z80_candidate_create(z80_candidate_bus_fn bus, void *userdata,
                                          z80_candidate **out_candidate) {
    return candidate_create(bus, userdata,
#if defined(Z80_CANDIDATE_TEST_HOOKS)
                            NULL,
#endif
                            out_candidate);
}

#if defined(Z80_CANDIDATE_TEST_HOOKS)
z80_candidate_status z80_candidate_test_create(
    z80_candidate_bus_fn bus, void *userdata,
    z80_candidate_test_failpoint *failpoint, z80_candidate **out_candidate) {
    if (out_candidate != NULL) *out_candidate = NULL;
    if (failpoint == NULL) return Z80_CANDIDATE_INVALID_ARGUMENT;
    return candidate_create(bus, userdata, failpoint, out_candidate);
}
#endif

void z80_candidate_destroy(z80_candidate *candidate) {
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    if (candidate != NULL)
        candidate_free(candidate->test_failpoint, candidate, sizeof(*candidate));
#else
    free(candidate);
#endif
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
    if (!valid_decoder_state(&candidate->cpu, candidate->pins)) {
        return Z80_CANDIDATE_INVALID_SNAPSHOT;
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
        !valid_decoder_state(&snapshot->cpu, snapshot->pins)) {
        return Z80_CANDIDATE_INVALID_SNAPSHOT;
    }
    candidate->cpu = snapshot->cpu;
    candidate->pins = snapshot->pins;
    candidate->cycles = snapshot->cycles;
    candidate->bus_failed = false;
    return Z80_CANDIDATE_OK;
}

size_t z80_candidate_state_size(void) {
    return Z80_CANDIDATE_STATE_BYTES;
}

z80_candidate_status z80_candidate_state_capture(const z80_candidate *candidate,
                                                 void *bytes, size_t capacity,
                                                 size_t *written) {
    if (written != NULL) *written = 0u;
    if (candidate == NULL || bytes == NULL || written == NULL) {
        return Z80_CANDIDATE_INVALID_ARGUMENT;
    }
    if (candidate->bus_failed) return Z80_CANDIDATE_BUS_FAILURE;
    if (capacity < Z80_CANDIDATE_STATE_BYTES ||
        !valid_decoder_state(&candidate->cpu, candidate->pins)) {
        return capacity < Z80_CANDIDATE_STATE_BYTES
                   ? Z80_CANDIDATE_INVALID_ARGUMENT
                   : Z80_CANDIDATE_INVALID_SNAPSHOT;
    }
    *written = encode_cpu((uint8_t *)bytes, &candidate->cpu, candidate->pins,
                          candidate->cycles);
    return *written == Z80_CANDIDATE_STATE_BYTES
               ? Z80_CANDIDATE_OK
               : Z80_CANDIDATE_INVALID_SNAPSHOT;
}

static z80_candidate_status state_stage(
    const void *bytes, size_t length,
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate_test_failpoint *failpoint, z80_candidate_state **out_state) {
#else
    z80_candidate_state **out_state) {
#endif
    z80_t cpu = {0};
    uint64_t pins = 0u;
    uint64_t cycles = 0u;
    if (out_state == NULL) return Z80_CANDIDATE_INVALID_ARGUMENT;
    *out_state = NULL;
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    const int bypass_validation = failpoint != NULL &&
        failpoint->bypass_validation != 0u;
#else
    const int bypass_validation = 0;
#endif
    if (bytes == NULL || length != Z80_CANDIDATE_STATE_BYTES ||
        (!bypass_validation &&
         !decode_cpu((const uint8_t *)bytes, &cpu, &pins, &cycles))) {
        return Z80_CANDIDATE_INVALID_SNAPSHOT;
    }
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate_state *state = candidate_calloc(
        failpoint, 1u, sizeof(*state), Z80_CANDIDATE_TEST_SITE_STAGE_STATE);
#else
    z80_candidate_state *state = calloc(1u, sizeof(*state));
#endif
    if (state == NULL) return Z80_CANDIDATE_OUT_OF_MEMORY;
    state->cpu = cpu;
    state->pins = pins;
    state->cycles = cycles;
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    state->test_failpoint = failpoint;
#endif
    *out_state = state;
    return Z80_CANDIDATE_OK;
}

z80_candidate_status z80_candidate_state_stage(const void *bytes, size_t length,
                                               z80_candidate_state **out_state) {
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    return state_stage(bytes, length, NULL, out_state);
#else
    return state_stage(bytes, length, out_state);
#endif
}

#if defined(Z80_CANDIDATE_TEST_HOOKS)
z80_candidate_status z80_candidate_state_test_stage(
    const void *bytes, size_t length,
    z80_candidate_test_failpoint *failpoint, z80_candidate_state **out_state) {
    if (out_state != NULL) *out_state = NULL;
    if (failpoint == NULL) return Z80_CANDIDATE_INVALID_ARGUMENT;
    return state_stage(bytes, length, failpoint, out_state);
}
#endif

void z80_candidate_state_discard(z80_candidate_state *state) {
#if defined(Z80_CANDIDATE_TEST_HOOKS)
    if (state != NULL)
        candidate_free(state->test_failpoint, state, sizeof(*state));
#else
    free(state);
#endif
}

z80_candidate_status z80_candidate_state_rebind(z80_candidate_state *state,
                                                const z80_candidate *destination) {
    if (state == NULL || destination == NULL) {
        return Z80_CANDIDATE_INVALID_ARGUMENT;
    }
    if (destination->bus_failed) return Z80_CANDIDATE_BUS_FAILURE;
    if (destination->bus == NULL) return Z80_CANDIDATE_INVALID_ARGUMENT;
    state->bus = destination->bus;
    state->userdata = destination->userdata;
    state->rebind_target = (z80_candidate *)destination;
    return Z80_CANDIDATE_OK;
}

void z80_candidate_state_apply(z80_candidate *destination,
                               const z80_candidate_state *state) {
    if (destination == NULL || state == NULL ||
        state->rebind_target != destination || destination->bus_failed ||
        state->bus == NULL) {
        return;
    }
    destination->cpu = state->cpu;
    destination->bus = state->bus;
    destination->userdata = state->userdata;
    destination->pins = state->pins;
    destination->cycles = state->cycles;
    destination->bus_failed = false;
}
