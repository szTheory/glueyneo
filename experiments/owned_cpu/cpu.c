/* SPDX-License-Identifier: MIT */
#include "cpu.h"

#include <limits.h>
#include <string.h>

#define CPU_ADDRESS_MASK UINT32_C(0x00ffffff)
#define SR_C UINT16_C(0x0001)
#define SR_V UINT16_C(0x0002)
#define SR_Z UINT16_C(0x0004)
#define SR_N UINT16_C(0x0008)
#define SR_X UINT16_C(0x0010)
#define SR_S UINT16_C(0x2000)
#define SR_ARITHMETIC_FLAGS (SR_X | SR_N | SR_Z | SR_V | SR_C)
#define SR_MOVE_FLAGS (SR_N | SR_Z | SR_V | SR_C)

_Static_assert(CHAR_BIT == 8, "owned CPU requires 8-bit bytes");
_Static_assert(UINT8_MAX == 0xffu, "owned CPU requires exact uint8_t");
_Static_assert(UINT16_MAX == 0xffffu, "owned CPU requires exact uint16_t");
_Static_assert(UINT32_MAX == 0xffffffffu, "owned CPU requires exact uint32_t");
_Static_assert(UINT64_MAX == UINT64_C(0xffffffffffffffff), "owned CPU requires exact uint64_t");

struct owned_cpu {
    owned_cpu_bus bus;
    owned_cpu_allocator allocator;
    uint32_t data_registers[8];
    uint32_t address_registers[8];
    uint32_t pc;
    uint32_t previous_pc;
    uint32_t usp;
    uint32_t ssp;
    uint32_t fault_pc;
    uint16_t sr;
    uint16_t instruction_register;
    uint8_t stopped;
    uint8_t irq_level;
    uint8_t irq7_pending;
    uint8_t ready;
    uint8_t faulted;
    uint8_t active;
    uint64_t instructions;
    uint64_t instruction_cycles;
    uint64_t reset_cycles;
};

static uint32_t bus_address(uint32_t address) {
    return address & CPU_ADDRESS_MASK;
}

static owned_cpu_status read_word(owned_cpu *cpu, uint32_t address, uint16_t *value) {
    if ((address & 1u) != 0u) {
        return OWNED_CPU_ADDRESS_ERROR;
    }
    if (cpu->bus.read16(cpu->bus.userdata, bus_address(address), value) == 0) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static owned_cpu_status write_word(owned_cpu *cpu, uint32_t address, uint16_t value) {
    if ((address & 1u) != 0u) {
        return OWNED_CPU_ADDRESS_ERROR;
    }
    if (cpu->bus.write16(cpu->bus.userdata, bus_address(address), value) == 0) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static owned_cpu_status fetch_word(owned_cpu *cpu, uint32_t *cursor, uint16_t *word) {
    owned_cpu_status status = read_word(cpu, *cursor, word);
    if (status == OWNED_CPU_OK) {
        /* Keep the 32-bit guest PC; mask only the physical bus transfer. */
        *cursor += UINT32_C(2);
    }
    return status;
}

static void set_supervisor_status(owned_cpu *cpu, uint16_t value) {
    int old_supervisor = (cpu->sr & SR_S) != 0u;
    int new_supervisor = (value & SR_S) != 0u;
    if (old_supervisor != new_supervisor) {
        if (old_supervisor != 0) {
            cpu->ssp = cpu->address_registers[7];
            cpu->address_registers[7] = cpu->usp;
        } else {
            cpu->usp = cpu->address_registers[7];
            cpu->address_registers[7] = cpu->ssp;
        }
    }
    cpu->sr = value;
}

static void set_move_flags(owned_cpu *cpu, uint32_t result) {
    cpu->sr = (uint16_t)(cpu->sr & (uint16_t)~SR_MOVE_FLAGS);
    if (result == 0u) {
        cpu->sr = (uint16_t)(cpu->sr | SR_Z);
    }
    if ((result & UINT32_C(0x80000000)) != 0u) {
        cpu->sr = (uint16_t)(cpu->sr | SR_N);
    }
}

static void add_quick_long(owned_cpu *cpu, unsigned reg, unsigned quick) {
    uint32_t before = cpu->data_registers[reg];
    uint64_t full_sum = (uint64_t)before + (uint64_t)quick;
    uint32_t after = (uint32_t)full_sum;
    uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (after == 0u) {
        flags = (uint16_t)(flags | SR_Z);
    }
    if ((after & UINT32_C(0x80000000)) != 0u) {
        flags = (uint16_t)(flags | SR_N);
    }
    if (((~(before ^ (uint32_t)quick) & (before ^ after)) & UINT32_C(0x80000000)) != 0u) {
        flags = (uint16_t)(flags | SR_V);
    }
    if (full_sum > UINT32_MAX) {
        flags = (uint16_t)(flags | SR_C | SR_X);
    }
    cpu->data_registers[reg] = after;
    cpu->sr = flags;
}

static owned_cpu_status execute_one(owned_cpu *cpu, uint32_t *next_pc, uint16_t *opcode,
                                    uint64_t *cycles) {
    const uint32_t instruction_pc = cpu->pc;
    uint32_t cursor = instruction_pc;
    owned_cpu_status status = fetch_word(cpu, &cursor, opcode);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = 0u;
        return status;
    }

    if ((*opcode & UINT16_C(0xf100)) == UINT16_C(0x7000)) {
        unsigned reg = (unsigned)((*opcode >> 9) & 7u);
        uint32_t immediate = (uint32_t)(*opcode & UINT16_C(0x00ff));
        if ((immediate & UINT32_C(0x80)) != 0u) {
            immediate |= UINT32_C(0xffffff00);
        }
        cpu->data_registers[reg] = immediate;
        set_move_flags(cpu, immediate);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x5080)) {
        unsigned quick = (unsigned)((*opcode >> 9) & 7u);
        unsigned reg = (unsigned)(*opcode & 7u);
        if (quick == 0u) {
            quick = 8u;
        }
        add_quick_long(cpu, reg, quick);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x23c0)) {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) {
            status = fetch_word(cpu, &cursor, &low);
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t destination = ((uint32_t)high << 16) | (uint32_t)low;
        if ((destination & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_ADDRESS_ERROR;
        }
        unsigned reg = (unsigned)(*opcode & 7u);
        uint32_t value = cpu->data_registers[reg];
        status = write_word(cpu, destination, (uint16_t)(value >> 16));
        if (status == OWNED_CPU_OK) {
            status = write_word(cpu, destination + UINT32_C(2), (uint16_t)value);
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, value);
        *cycles = UINT64_C(20);
    } else if (*opcode == UINT16_C(0x4e72)) {
        if ((cpu->sr & SR_S) == 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_PRIVILEGE_VIOLATION;
        }
        uint16_t immediate_sr = 0u;
        status = fetch_word(cpu, &cursor, &immediate_sr);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_supervisor_status(cpu, immediate_sr);
        cpu->stopped = 1u;
        *cycles = UINT64_C(4);
    } else {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = *opcode;
        return OWNED_CPU_UNSUPPORTED_OPCODE;
    }

    *next_pc = cursor;
    cpu->fault_pc = 0u;
    cpu->instruction_register = *opcode;
    return OWNED_CPU_OK;
}

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
    if (cpu != NULL && cpu->active == 0u) {
        owned_cpu_allocator allocator = cpu->allocator;
        allocator.release(allocator.userdata, cpu);
    }
}

owned_cpu_status owned_cpu_reset(owned_cpu *cpu) {
    if (cpu == NULL || cpu->active != 0u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    cpu->ready = 0u;
    cpu->faulted = 0u;
    memset(cpu->data_registers, 0, sizeof(cpu->data_registers));
    memset(cpu->address_registers, 0, sizeof(cpu->address_registers));
    cpu->pc = 0u;
    cpu->previous_pc = 0u;
    cpu->usp = 0u;
    cpu->ssp = 0u;
    cpu->fault_pc = 0u;
    cpu->sr = 0u;
    cpu->instruction_register = 0u;
    cpu->stopped = 0u;
    cpu->irq_level = 0u;
    cpu->irq7_pending = 0u;
    cpu->instructions = 0u;
    cpu->instruction_cycles = 0u;
    cpu->reset_cycles = 0u;

    uint16_t vectors[4] = {0u, 0u, 0u, 0u};
    cpu->active = 1u;
    owned_cpu_status status = OWNED_CPU_OK;
    for (unsigned index = 0u; index < 4u; ++index) {
        status = read_word(cpu, index * UINT32_C(2), &vectors[index]);
        if (status != OWNED_CPU_OK) {
            break;
        }
    }
    cpu->active = 0u;
    if (status != OWNED_CPU_OK) {
        return status;
    }

    cpu->ssp = ((uint32_t)vectors[0] << 16) | (uint32_t)vectors[1];
    cpu->address_registers[7] = cpu->ssp;
    cpu->pc = ((uint32_t)vectors[2] << 16) | (uint32_t)vectors[3];
    cpu->previous_pc = cpu->pc;
    cpu->sr = UINT16_C(0x2700);
    cpu->reset_cycles = UINT64_C(40);
    if ((cpu->ssp & 1u) != 0u || (cpu->pc & 1u) != 0u) {
        return OWNED_CPU_ADDRESS_ERROR;
    }
    cpu->ready = 1u;
    return OWNED_CPU_OK;
}

owned_cpu_run_result owned_cpu_run(owned_cpu *cpu, uint64_t cycle_budget) {
    owned_cpu_run_result result;
    memset(&result, 0, sizeof(result));
    result.reason = OWNED_CPU_INVALID_ARGUMENT;
    result.requested_cycles = cycle_budget;
    if (cpu == NULL || cpu->active != 0u || cycle_budget > OWNED_CPU_MAX_CYCLE_BUDGET) {
        return result;
    }
    result.pc = cpu->pc;
    if (cpu->faulted != 0u) {
        result.reason = OWNED_CPU_HOST_FAULT;
        return result;
    }
    if (cpu->ready == 0u) {
        return result;
    }
    if (cycle_budget == 0u) {
        result.reason = OWNED_CPU_BUDGET;
        return result;
    }
    if (cpu->stopped != 0u) {
        result.reason = OWNED_CPU_STOPPED;
        return result;
    }

    result.reason = OWNED_CPU_BUDGET;
    cpu->active = 1u;
    while (result.elapsed_cycles < cycle_budget && cpu->stopped == 0u) {
        /* All currently supported operations cost at most 20 cycles. Guard the
         * cumulative counters before allowing an instruction to change state. */
        if (cpu->instructions == UINT64_MAX ||
            cpu->instruction_cycles > UINT64_MAX - UINT64_C(20)) {
            result.reason = OWNED_CPU_INVALID_ARGUMENT;
            break;
        }
        uint64_t step_cycles = 0u;
        uint32_t next_pc = cpu->pc;
        uint16_t opcode = 0u;
        owned_cpu_status status = execute_one(cpu, &next_pc, &opcode, &step_cycles);
        if (status != OWNED_CPU_OK) {
            result.reason = status;
            result.fault_pc = cpu->fault_pc;
            result.instruction_register = cpu->instruction_register;
            break;
        }
        cpu->previous_pc = cpu->pc;
        cpu->pc = next_pc;
        cpu->instructions++;
        cpu->instruction_cycles += step_cycles;
        result.instructions++;
        result.elapsed_cycles += step_cycles;
        result.pc = cpu->pc;
        result.instruction_register = opcode;
        result.reason = cpu->stopped != 0u ? OWNED_CPU_STOPPED : OWNED_CPU_BUDGET;
    }
    cpu->active = 0u;
    result.pc = cpu->pc;
    if (result.elapsed_cycles > cycle_budget) {
        result.overshoot_cycles = result.elapsed_cycles - cycle_budget;
    }
    return result;
}

owned_cpu_status owned_cpu_set_irq(owned_cpu *cpu, unsigned level) {
    if (cpu == NULL || cpu->active != 0u || level > 7u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    if (cpu->faulted != 0u) {
        return OWNED_CPU_HOST_FAULT;
    }
    if (cpu->ready == 0u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    if (cpu->irq_level < 7u && level == 7u) {
        cpu->irq7_pending = 1u;
    }
    cpu->irq_level = (uint8_t)level;
    return OWNED_CPU_OK;
}

owned_cpu_status owned_cpu_observe(const owned_cpu *cpu, owned_cpu_observation *out) {
    if (cpu == NULL || out == NULL || cpu->active != 0u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    if (cpu->faulted != 0u) {
        return OWNED_CPU_HOST_FAULT;
    }
    if (cpu->ready == 0u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));
    memcpy(out->data_registers, cpu->data_registers, sizeof(out->data_registers));
    memcpy(out->address_registers, cpu->address_registers, sizeof(out->address_registers));
    out->pc = cpu->pc;
    out->previous_pc = cpu->previous_pc;
    out->usp = cpu->usp;
    out->ssp = cpu->ssp;
    out->sr = cpu->sr;
    out->stopped = cpu->stopped;
    out->irq_level = cpu->irq_level;
    out->irq7_pending = cpu->irq7_pending;
    out->instructions = cpu->instructions;
    out->instruction_cycles = cpu->instruction_cycles;
    out->reset_cycles = cpu->reset_cycles;
    return OWNED_CPU_OK;
}

#ifdef OWNED_CPU_TEST_HOOKS
owned_cpu_status owned_cpu_test_seed_data_register(owned_cpu *cpu, unsigned reg,
                                                    uint32_t value) {
    if (cpu == NULL || cpu->active != 0u || cpu->ready == 0u || reg > 7u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    if (cpu->faulted != 0u) {
        return OWNED_CPU_HOST_FAULT;
    }
    cpu->data_registers[reg] = value;
    return OWNED_CPU_OK;
}
#endif
