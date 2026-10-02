/* SPDX-License-Identifier: MIT */
#include "cpu.h"

#include <limits.h>
#include <string.h>

_Static_assert(CHAR_BIT == 8, "owned CPU requires 8-bit bytes");
_Static_assert(UINT8_MAX == 0xffu, "owned CPU requires exact uint8_t");
_Static_assert(UINT16_MAX == 0xffffu, "owned CPU requires exact uint16_t");
_Static_assert(UINT32_MAX == 0xffffffffu, "owned CPU requires exact uint32_t");
_Static_assert(UINT64_MAX == UINT64_C(0xffffffffffffffff), "owned CPU requires exact uint64_t");

struct owned_cpu {
    owned_cpu_bus bus;
    owned_cpu_allocator allocator;
    owned_cpu_observation state;
    uint8_t ready;
    uint8_t faulted;
};

owned_cpu_status owned_cpu_create(uint32_t model, owned_cpu_bus bus,
                                  owned_cpu_allocator allocator, owned_cpu **out_cpu) {
    if (out_cpu == NULL) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    *out_cpu = NULL;
    if (model != OWNED_CPU_MODEL_MC68000) {
        return OWNED_CPU_UNSUPPORTED_MODEL;
    }
    if (bus.read16 == NULL || bus.write16 == NULL || allocator.allocate == NULL ||
        allocator.release == NULL) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    owned_cpu *cpu = allocator.allocate(allocator.userdata, sizeof(*cpu));
    if (cpu == NULL) {
        return OWNED_CPU_ALLOCATION_FAILURE;
    }
    memset(cpu, 0, sizeof(*cpu));
    cpu->bus = bus;
    cpu->allocator = allocator;
    *out_cpu = cpu;
    return OWNED_CPU_OK;
}

void owned_cpu_destroy(owned_cpu *cpu) {
    if (cpu != NULL) {
        owned_cpu_allocator allocator = cpu->allocator;
        allocator.release(allocator.userdata, cpu);
    }
}

owned_cpu_status owned_cpu_reset(owned_cpu *cpu) {
    if (cpu == NULL) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    cpu->ready = 0u;
    cpu->faulted = 0u;
    memset(&cpu->state, 0, sizeof(cpu->state));
    uint16_t words[4];
    for (unsigned index = 0u; index < 4u; ++index) {
        if (!cpu->bus.read16(cpu->bus.userdata, index * 2u, &words[index])) {
            cpu->faulted = 1u;
            return OWNED_CPU_HOST_FAULT;
        }
    }
    cpu->state.ssp = ((uint32_t)words[0] << 16) | words[1];
    cpu->state.address_registers[7] = cpu->state.ssp;
    cpu->state.pc = ((uint32_t)words[2] << 16) | words[3];
    cpu->state.sr = UINT16_C(0x2700);
    cpu->state.reset_cycles = 40u;
    if ((cpu->state.ssp & 1u) != 0u || (cpu->state.pc & 1u) != 0u) {
        return OWNED_CPU_ADDRESS_ERROR;
    }
    cpu->ready = 1u;
    return OWNED_CPU_OK;
}

owned_cpu_run_result owned_cpu_run(owned_cpu *cpu, uint64_t cycle_budget) {
    owned_cpu_run_result result;
    memset(&result, 0, sizeof(result));
    result.requested_cycles = cycle_budget;
    result.reason = OWNED_CPU_INVALID_ARGUMENT;
    if (cpu == NULL || cycle_budget > OWNED_CPU_MAX_CYCLE_BUDGET || cpu->ready == 0u) {
        return result;
    }
    result.pc = cpu->state.pc;
    if (cpu->faulted != 0u) {
        result.reason = OWNED_CPU_HOST_FAULT;
        return result;
    }
    if (cycle_budget == 0u) {
        result.reason = OWNED_CPU_BUDGET;
        return result;
    }
    uint16_t instruction = 0u;
    if (!cpu->bus.read16(cpu->bus.userdata, cpu->state.pc & UINT32_C(0x00ffffff), &instruction)) {
        cpu->faulted = 1u;
        result.reason = OWNED_CPU_HOST_FAULT;
        return result;
    }
    result.instruction_register = instruction;
    result.fault_pc = cpu->state.pc;
    result.reason = OWNED_CPU_UNSUPPORTED_OPCODE;
    return result;
}

owned_cpu_status owned_cpu_set_irq(owned_cpu *cpu, unsigned level) {
    if (cpu == NULL || level > 7u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    cpu->state.irq_level = (uint8_t)level;
    return OWNED_CPU_OK;
}

owned_cpu_status owned_cpu_observe(const owned_cpu *cpu, owned_cpu_observation *out) {
    if (cpu == NULL || out == NULL) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    *out = cpu->state;
    return OWNED_CPU_OK;
}
