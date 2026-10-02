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
#define SR_T1 UINT16_C(0x8000)
#define SR_INTERRUPT_MASK UINT16_C(0x0700)
#define SR_ARITHMETIC_FLAGS (SR_X | SR_N | SR_Z | SR_V | SR_C)
#define SR_MOVE_FLAGS (SR_N | SR_Z | SR_V | SR_C)
#define RESET_EVENT_CYCLES UINT64_C(40)

typedef enum {
    STEP_INSTRUCTION = 0,
    STEP_INSTRUCTION_EXCEPTION,
    STEP_ADDRESS_EXCEPTION
} step_kind;

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
    uint8_t reset_pending;
    uint8_t last_exception_vector;
    uint64_t instructions;
    uint64_t instruction_cycles;
    uint64_t reset_cycles;
    uint64_t exception_cycles;
    uint64_t idle_cycles;
    uint64_t total_cycles;
    uint64_t reset_signal_events;
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

static int counter_can_add(uint64_t current, uint64_t amount) {
    return current <= UINT64_MAX - amount;
}

static int accounting_can_add(const owned_cpu *cpu, uint64_t instructions,
                              uint64_t instruction_cycles, uint64_t exception_cycles,
                              uint64_t idle_cycles, uint64_t total_cycles,
                              uint64_t reset_signals) {
    return counter_can_add(cpu->instructions, instructions) &&
           counter_can_add(cpu->instruction_cycles, instruction_cycles) &&
           counter_can_add(cpu->exception_cycles, exception_cycles) &&
           counter_can_add(cpu->idle_cycles, idle_cycles) &&
           counter_can_add(cpu->total_cycles, total_cycles) &&
           counter_can_add(cpu->reset_signal_events, reset_signals);
}

static owned_cpu_status preflight_event(const owned_cpu *cpu, step_kind kind,
                                        uint64_t cycles, uint64_t completed_instructions,
                                        uint64_t reset_signals) {
    uint64_t instruction_cycles = kind == STEP_INSTRUCTION ? cycles : 0u;
    uint64_t exception_cycles = kind == STEP_INSTRUCTION ? 0u : cycles;
    return accounting_can_add(cpu, completed_instructions, instruction_cycles,
                              exception_cycles, 0u, cycles, reset_signals)
               ? OWNED_CPU_OK
               : OWNED_CPU_COUNTER_OVERFLOW;
}

static void set_supervisor_stack_pointer(owned_cpu *cpu, uint32_t value) {
    cpu->address_registers[7] = value;
    cpu->ssp = value;
}

static owned_cpu_status push_word(owned_cpu *cpu, uint16_t value) {
    uint32_t stack_pointer = cpu->address_registers[7] - UINT32_C(2);
    set_supervisor_stack_pointer(cpu, stack_pointer);
    owned_cpu_status status = write_word(cpu, stack_pointer, value);
    if (status != OWNED_CPU_OK) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static owned_cpu_status push_long(owned_cpu *cpu, uint32_t value) {
    uint32_t stack_pointer = cpu->address_registers[7] - UINT32_C(4);
    set_supervisor_stack_pointer(cpu, stack_pointer);
    owned_cpu_status status = write_word(cpu, stack_pointer, (uint16_t)(value >> 16));
    if (status == OWNED_CPU_OK) {
        status = write_word(cpu, stack_pointer + UINT32_C(2), (uint16_t)value);
    }
    if (status != OWNED_CPU_OK) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static owned_cpu_status fetch_exception_vector(owned_cpu *cpu, unsigned vector,
                                                uint32_t *handler_pc) {
    uint32_t vector_address = (uint32_t)vector * UINT32_C(4);
    uint16_t high = 0u;
    uint16_t low = 0u;
    owned_cpu_status status = read_word(cpu, vector_address, &high);
    if (status == OWNED_CPU_OK) {
        status = read_word(cpu, vector_address + UINT32_C(2), &low);
    }
    if (status != OWNED_CPU_OK) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    *handler_pc = ((uint32_t)high << 16) | (uint32_t)low;
    return OWNED_CPU_OK;
}

static owned_cpu_status enter_short_exception(owned_cpu *cpu, unsigned vector,
                                               uint16_t old_sr, uint32_t saved_pc,
                                               unsigned interrupt_level) {
    uint16_t new_sr = (uint16_t)((old_sr | SR_S) & (uint16_t)~SR_T1);
    if (interrupt_level != 0u) {
        new_sr = (uint16_t)((new_sr & (uint16_t)~SR_INTERRUPT_MASK) |
                            (uint16_t)(interrupt_level << 8));
    }
    set_supervisor_status(cpu, new_sr);

    owned_cpu_status status = push_long(cpu, saved_pc);
    if (status == OWNED_CPU_OK) {
        status = push_word(cpu, old_sr);
    }
    uint32_t handler_pc = 0u;
    if (status == OWNED_CPU_OK) {
        status = fetch_exception_vector(cpu, vector, &handler_pc);
    }
    if (status != OWNED_CPU_OK) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }

    cpu->pc = handler_pc;
    cpu->previous_pc = saved_pc;
    cpu->last_exception_vector = (uint8_t)vector;
    cpu->stopped = 0u;
    return OWNED_CPU_OK;
}

static owned_cpu_status enter_address_exception(owned_cpu *cpu, uint32_t fault_pc,
                                                  uint16_t instruction_register,
                                                  uint32_t fault_address,
                                                  int instruction_access, int read_access) {
    const uint16_t old_sr = cpu->sr;
    const unsigned function_code = (old_sr & SR_S) != 0u
                                       ? (instruction_access != 0 ? 6u : 5u)
                                       : (instruction_access != 0 ? 2u : 1u);
    const uint16_t status_word = (uint16_t)((read_access != 0 ? UINT16_C(0x0010) : 0u) |
                                            (instruction_access == 0 ? UINT16_C(0x0008) : 0u) |
                                            (uint16_t)function_code);
    const uint16_t new_sr = (uint16_t)((old_sr | SR_S) & (uint16_t)~SR_T1);
    set_supervisor_status(cpu, new_sr);

    owned_cpu_status status = push_long(cpu, fault_pc);
    if (status == OWNED_CPU_OK) {
        status = push_word(cpu, old_sr);
    }
    if (status == OWNED_CPU_OK) {
        status = push_word(cpu, instruction_register);
    }
    if (status == OWNED_CPU_OK) {
        status = push_long(cpu, fault_address);
    }
    if (status == OWNED_CPU_OK) {
        status = push_word(cpu, status_word);
    }
    uint32_t handler_pc = 0u;
    if (status == OWNED_CPU_OK) {
        status = fetch_exception_vector(cpu, 3u, &handler_pc);
    }
    if (status != OWNED_CPU_OK) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }

    cpu->pc = handler_pc;
    cpu->previous_pc = fault_pc;
    cpu->last_exception_vector = 3u;
    cpu->stopped = 0u;
    return OWNED_CPU_OK;
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
                                    uint64_t *cycles, step_kind *kind) {
    const uint32_t instruction_pc = cpu->pc;
    uint32_t cursor = instruction_pc;
    *kind = STEP_INSTRUCTION;
    if ((instruction_pc & 1u) != 0u) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = 0u;
        owned_cpu_status overflow = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                                    UINT64_C(50), 0u, 0u);
        if (overflow != OWNED_CPU_OK) return overflow;
        owned_cpu_status address_status = enter_address_exception(
            cpu, instruction_pc, 0u, instruction_pc, 1, 1);
        if (address_status != OWNED_CPU_OK) return address_status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = UINT64_C(50);
        return OWNED_CPU_OK;
    }
    owned_cpu_status status = fetch_word(cpu, &cursor, opcode);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = 0u;
        return status;
    }
    cpu->instruction_register = *opcode;

    if ((*opcode & UINT16_C(0xf100)) == UINT16_C(0x7000)) {
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        unsigned reg = (unsigned)((*opcode >> 9) & 7u);
        uint32_t immediate = (uint32_t)(*opcode & UINT16_C(0x00ff));
        if ((immediate & UINT32_C(0x80)) != 0u) {
            immediate |= UINT32_C(0xffffff00);
        }
        cpu->data_registers[reg] = immediate;
        set_move_flags(cpu, immediate);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x5080)) {
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
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
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, UINT64_C(50), 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode, destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = UINT64_C(50);
            return OWNED_CPU_OK;
        }
        unsigned reg = (unsigned)(*opcode & 7u);
        uint32_t value = cpu->data_registers[reg];
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
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
    } else if (*opcode == UINT16_C(0x4e71)) {
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        *cycles = UINT64_C(4);
    } else if (*opcode == UINT16_C(0x4e70)) {
        if ((cpu->sr & SR_S) == 0u) {
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, UINT64_C(34), 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_short_exception(cpu, 8u, cpu->sr, instruction_pc, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = UINT64_C(34);
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(132), 1u, 1u);
        if (status != OWNED_CPU_OK) return status;
        cpu->reset_signal_events++;
        *cycles = UINT64_C(132);
    } else if (*opcode == UINT16_C(0x4e73)) {
        if ((cpu->sr & SR_S) == 0u) {
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, UINT64_C(34), 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_short_exception(cpu, 8u, cpu->sr, instruction_pc, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = UINT64_C(34);
            return OWNED_CPU_OK;
        }
        if ((cpu->address_registers[7] & 1u) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, UINT64_C(50), 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             cpu->address_registers[7], 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = UINT64_C(50);
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t restored_sr = 0u;
        uint16_t pc_high = 0u;
        uint16_t pc_low = 0u;
        status = read_word(cpu, cpu->address_registers[7], &restored_sr);
        if (status == OWNED_CPU_OK) status = read_word(cpu, cpu->address_registers[7] + 2u, &pc_high);
        if (status == OWNED_CPU_OK) status = read_word(cpu, cpu->address_registers[7] + 4u, &pc_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t restored_pc = ((uint32_t)pc_high << 16) | (uint32_t)pc_low;
        uint32_t restored_sp = cpu->address_registers[7] + UINT32_C(6);
        set_supervisor_stack_pointer(cpu, restored_sp);
        set_supervisor_status(cpu, restored_sr);
        *next_pc = restored_pc;
        *cycles = UINT64_C(20);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x3039)) {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t source = ((uint32_t)high << 16) | (uint32_t)low;
        if ((source & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, UINT64_C(50), 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode, source, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = UINT64_C(50);
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value = 0u;
        status = read_word(cpu, source, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        unsigned reg = (unsigned)((*opcode >> 9) & 7u);
        cpu->data_registers[reg] = (cpu->data_registers[reg] & UINT32_C(0xffff0000)) | value;
        cpu->sr = (uint16_t)(cpu->sr & (uint16_t)~SR_MOVE_FLAGS);
        if (value == 0u) cpu->sr = (uint16_t)(cpu->sr | SR_Z);
        if ((value & UINT16_C(0x8000)) != 0u) cpu->sr = (uint16_t)(cpu->sr | SR_N);
        *cycles = UINT64_C(16);
    } else if (*opcode == UINT16_C(0x4afc)) {
        status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, UINT64_C(34), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = enter_short_exception(cpu, 4u, cpu->sr, instruction_pc, 0u);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_INSTRUCTION_EXCEPTION;
        *cycles = UINT64_C(34);
        return OWNED_CPU_OK;
    } else if (*opcode == UINT16_C(0x4e40)) {
        status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, UINT64_C(34), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = enter_short_exception(cpu, 32u, cpu->sr, cursor, 0u);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_INSTRUCTION_EXCEPTION;
        *cycles = UINT64_C(34);
        return OWNED_CPU_OK;
    } else if (*opcode == UINT16_C(0x46fc)) {
        if ((cpu->sr & SR_S) == 0u) {
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, UINT64_C(34), 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_short_exception(cpu, 8u, cpu->sr, instruction_pc, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = UINT64_C(34);
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t immediate_sr = 0u;
        status = fetch_word(cpu, &cursor, &immediate_sr);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_supervisor_status(cpu, immediate_sr);
        *cycles = UINT64_C(12);
    } else if (*opcode == UINT16_C(0x4e72)) {
        if ((cpu->sr & SR_S) == 0u) {
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, UINT64_C(34), 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_short_exception(cpu, 8u, cpu->sr, instruction_pc, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = UINT64_C(34);
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
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

    if (*opcode != UINT16_C(0x4e73)) *next_pc = cursor;
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
    cpu->exception_cycles = 0u;
    cpu->idle_cycles = 0u;
    cpu->total_cycles = 0u;
    cpu->reset_signal_events = 0u;
    cpu->last_exception_vector = 0u;
    cpu->reset_pending = 0u;

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
    cpu->reset_pending = 1u;
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
    result.reason = OWNED_CPU_BUDGET;
    cpu->active = 1u;
    if (cpu->reset_pending != 0u) {
        if (!accounting_can_add(cpu, 0u, 0u, 0u, 0u, RESET_EVENT_CYCLES, 0u)) {
            result.reason = OWNED_CPU_COUNTER_OVERFLOW;
            cpu->active = 0u;
            return result;
        }
        cpu->reset_pending = 0u;
        result.elapsed_cycles = UINT64_C(40);
        cpu->total_cycles += RESET_EVENT_CYCLES;
    }
    while (result.elapsed_cycles < cycle_budget) {
        unsigned level = cpu->irq_level;
        unsigned mask = (unsigned)((cpu->sr & SR_INTERRUPT_MASK) >> 8);
        int irq7 = cpu->irq7_pending != 0u || (level == 7u && mask < 7u);
        if (irq7 != 0 || (level >= 1u && level <= 6u && level > mask)) {
            unsigned accepted_level = irq7 != 0 ? 7u : level;
            uint64_t irq_cycles = UINT64_C(44);
            if (!accounting_can_add(cpu, 0u, 0u, irq_cycles, 0u, irq_cycles, 0u)) {
                result.reason = OWNED_CPU_COUNTER_OVERFLOW;
                break;
            }
            uint16_t old_sr = cpu->sr;
            uint32_t saved_pc = cpu->pc;
            owned_cpu_status irq_status = enter_short_exception(
                cpu, 24u + accepted_level, old_sr, saved_pc, accepted_level);
            if (irq_status != OWNED_CPU_OK) {
                result.reason = irq_status;
                break;
            }
            if (accepted_level == 7u) cpu->irq7_pending = 0u;
            cpu->exception_cycles += irq_cycles;
            cpu->total_cycles += irq_cycles;
            result.elapsed_cycles += irq_cycles;
            result.pc = cpu->pc;
            result.reason = OWNED_CPU_BUDGET;
            continue;
        }
        if (cpu->stopped != 0u) {
            uint64_t idle = cycle_budget - result.elapsed_cycles;
            if (!accounting_can_add(cpu, 0u, 0u, 0u, idle, idle, 0u)) {
                result.reason = OWNED_CPU_COUNTER_OVERFLOW;
                break;
            }
            cpu->idle_cycles += idle;
            cpu->total_cycles += idle;
            result.elapsed_cycles += idle;
            result.reason = OWNED_CPU_STOPPED;
            break;
        }
        uint64_t step_cycles = 0u;
        uint32_t next_pc = cpu->pc;
        uint16_t opcode = 0u;
        step_kind kind = STEP_INSTRUCTION;
        owned_cpu_status status = execute_one(cpu, &next_pc, &opcode, &step_cycles, &kind);
        if (status != OWNED_CPU_OK) {
            result.reason = status;
            result.fault_pc = cpu->fault_pc;
            result.instruction_register = cpu->instruction_register;
            break;
        }
        uint32_t old_pc = cpu->pc;
        if (kind == STEP_INSTRUCTION) cpu->previous_pc = old_pc;
        cpu->pc = next_pc;
        if (kind != STEP_ADDRESS_EXCEPTION) {
            cpu->instructions++;
            result.instructions++;
        }
        if (kind == STEP_INSTRUCTION) cpu->instruction_cycles += step_cycles;
        else cpu->exception_cycles += step_cycles;
        cpu->total_cycles += step_cycles;
        result.elapsed_cycles += step_cycles;
        result.pc = cpu->pc;
        result.instruction_register = opcode;
        if (kind == STEP_ADDRESS_EXCEPTION) result.fault_pc = cpu->fault_pc;
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
    out->reset_pending = cpu->reset_pending;
    out->last_exception_vector = cpu->last_exception_vector;
    out->instructions = cpu->instructions;
    out->instruction_cycles = cpu->instruction_cycles;
    out->reset_cycles = cpu->reset_cycles;
    out->exception_cycles = cpu->exception_cycles;
    out->idle_cycles = cpu->idle_cycles;
    out->total_cycles = cpu->total_cycles;
    out->reset_signal_events = cpu->reset_signal_events;
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

owned_cpu_status owned_cpu_test_seed_execution_state(owned_cpu *cpu, uint16_t sr,
                                                      uint32_t usp, uint32_t ssp,
                                                      uint32_t pc) {
    if (cpu == NULL || cpu->active != 0u || cpu->ready == 0u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    if (cpu->faulted != 0u) return OWNED_CPU_HOST_FAULT;
    cpu->sr = sr;
    cpu->usp = usp;
    cpu->ssp = ssp;
    cpu->address_registers[7] = (sr & SR_S) != 0u ? ssp : usp;
    cpu->pc = pc;
    cpu->previous_pc = pc;
    cpu->stopped = 0u;
    return OWNED_CPU_OK;
}

owned_cpu_status owned_cpu_test_seed_counters(owned_cpu *cpu, uint64_t instructions,
                                               uint64_t instruction_cycles,
                                               uint64_t exception_cycles,
                                               uint64_t idle_cycles,
                                               uint64_t total_cycles) {
    if (cpu == NULL || cpu->active != 0u || cpu->ready == 0u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    if (cpu->faulted != 0u) return OWNED_CPU_HOST_FAULT;
    cpu->instructions = instructions;
    cpu->instruction_cycles = instruction_cycles;
    cpu->exception_cycles = exception_cycles;
    cpu->idle_cycles = idle_cycles;
    cpu->total_cycles = total_cycles;
    return OWNED_CPU_OK;
}
#endif
