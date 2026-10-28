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
#define SR_IMPLEMENTED_MASK UINT16_C(0xa71f)
#define SR_ARITHMETIC_FLAGS (SR_X | SR_N | SR_Z | SR_V | SR_C)
#define SR_MOVE_FLAGS (SR_N | SR_Z | SR_V | SR_C)
/* MC68000 (16-bit bus) reset recovery: M68000 User's Manual Rev. 9.1 Section 8,
 * Table 8-14, printed p. 8-11, RESET 40(6/0). Table 7-15 (64) is the 8-bit-bus
 * (MC68008) table and does not describe the selected processor. */
#define RESET_EVENT_CYCLES UINT64_C(40)
/* MC68000 exception processing, UM Rev. 9.1 Section 8, Table 8-14, printed
 * p. 8-11 (Table 7-15 72/94/62 is the 8-bit-bus table). Only clocks are
 * modeled; the table's read/write bus-cycle counts are not core counters.
 * Table 8-14 interrupt 44(5/3) assumes a 4-clock interrupt acknowledge. */
#define EXCEPTION_IRQ_CYCLES UINT64_C(44)
/* Table 8-14: address error and bus error 50(4/7). */
#define EXCEPTION_ADDRESS_ERROR_CYCLES UINT64_C(50)
/* Table 8-14: illegal instruction, privilege violation, TRAP 34(4/3). */
#define EXCEPTION_INSTRUCTION_CYCLES UINT64_C(34)
#define MINIMUM_COUNTED_INSTRUCTION_CYCLES UINT64_C(4)

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
    uint64_t bus_cycles;
    uint8_t reset_pending;
    uint8_t last_exception_vector;
    uint64_t instructions;
    uint64_t instruction_cycles;
    uint64_t reset_cycles;
    uint64_t exception_cycles;
    uint64_t idle_cycles;
    uint64_t total_cycles;
    uint64_t reset_signal_events;
    uint64_t fetch_trace_run_sequence;
    size_t fetch_trace_count;
    size_t fetch_trace_next;
    owned_cpu_fetch_trace_event fetch_trace[OWNED_CPU_FETCH_TRACE_CAPACITY];
};

#ifdef OWNED_CPU_TEST_HOOKS
_Static_assert(_Alignof(owned_cpu) <=
                   _Alignof(owned_cpu_test_allocation_alignment),
               "test allocator alignment must cover the complete owned CPU");
#endif

static uint32_t bus_address(uint32_t address) {
    return address & CPU_ADDRESS_MASK;
}

/* Sign-extend encoded 68000 displacement/index fields using only defined
 * unsigned arithmetic. Converting an out-of-range unsigned value directly to
 * int8_t/int16_t is implementation-defined in C17. */
static uint32_t sign_extend_byte(uint8_t value) {
    return (value & UINT8_C(0x80)) != 0u
        ? UINT32_C(0xffffff00) | (uint32_t)value : (uint32_t)value;
}

static uint32_t sign_extend_word(uint16_t value) {
    return (value & UINT16_C(0x8000)) != 0u
        ? UINT32_C(0xffff0000) | (uint32_t)value : (uint32_t)value;
}

static int32_t sign_extend_word_signed(uint16_t value) {
    return (value & UINT16_C(0x8000)) != 0u
        ? (int32_t)value - INT32_C(0x10000) : (int32_t)value;
}

static int64_t sign_extend_long_signed(uint32_t value) {
    return (value & UINT32_C(0x80000000)) != 0u
        ? (int64_t)value - INT64_C(0x100000000) : (int64_t)value;
}

static owned_cpu_status read_word(owned_cpu *cpu, uint32_t address, uint16_t *value) {
    if ((address & 1u) != 0u) {
        return OWNED_CPU_ADDRESS_ERROR;
    }
    cpu->bus_cycles += UINT64_C(4);
    if (cpu->bus.read16(cpu->bus.userdata, bus_address(address), value) == 0) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static owned_cpu_status read_byte(owned_cpu *cpu, uint32_t address, uint8_t *value) {
    cpu->bus_cycles += UINT64_C(4);
    if (cpu->bus.read8 == NULL ||
        cpu->bus.read8(cpu->bus.userdata, bus_address(address), value) == 0) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static owned_cpu_status write_word(owned_cpu *cpu, uint32_t address, uint16_t value) {
    if ((address & 1u) != 0u) {
        return OWNED_CPU_ADDRESS_ERROR;
    }
    cpu->bus_cycles += UINT64_C(4);
    if (cpu->bus.write16(cpu->bus.userdata, bus_address(address), value) == 0) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static owned_cpu_status write_byte(owned_cpu *cpu, uint32_t address, uint8_t value) {
    cpu->bus_cycles += UINT64_C(4);
    if (cpu->bus.write8 == NULL ||
        cpu->bus.write8(cpu->bus.userdata, bus_address(address), value) == 0) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static void set_move_byte_flags(owned_cpu *cpu, uint8_t result) {
    cpu->sr = (uint16_t)(cpu->sr & (uint16_t)~SR_MOVE_FLAGS);
    if (result == 0u) cpu->sr = (uint16_t)(cpu->sr | SR_Z);
    if ((result & UINT8_C(0x80)) != 0u) cpu->sr = (uint16_t)(cpu->sr | SR_N);
}

/* CMP, CMPA and CMPI use destination-minus-source arithmetic flags and
 * preserve X. The width-limited helper is shared across their supported
 * register and memory forms. */
static void set_compare_flags(owned_cpu *cpu, uint32_t destination,
                              uint32_t source, unsigned width) {
    const uint32_t mask = width == 1u ? UINT32_C(0xff) :
        width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
    const uint32_t sign_bit = width == 1u ? UINT32_C(0x80) :
        width == 2u ? UINT32_C(0x8000) : UINT32_C(0x80000000);
    destination &= mask;
    source &= mask;
    const uint32_t difference = (destination - source) & mask;
    uint16_t flags = (uint16_t)(cpu->sr &
                                (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
    if (difference == 0u) flags = (uint16_t)(flags | SR_Z);
    if ((difference & sign_bit) != 0u)
        flags = (uint16_t)(flags | SR_N);
    if (((destination ^ source) & (destination ^ difference) & sign_bit) != 0u)
        flags = (uint16_t)(flags | SR_V);
    if (destination < source) flags = (uint16_t)(flags | SR_C);
    cpu->sr = flags;
}

/* CMPA compares a sign-extended word or full long source against An; N/Z/V/C
 * change while X and both operand registers remain unchanged (68000 PRM). */
static void set_cmpa_flags(owned_cpu *cpu, unsigned destination_register,
                           uint32_t source) {
    set_compare_flags(cpu, cpu->address_registers[destination_register],
                      source, 4u);
}

/* Width-limited ADD/SUB arithmetic shared by immediate and quick memory forms.
 * The caller commits `*sr_out` only after its register or memory write succeeds. */
static uint8_t addsubq_byte(uint16_t sr, uint8_t before, unsigned quick,
                            int subtract, uint16_t *sr_out) {
    const uint16_t full_result = subtract
        ? (uint16_t)((uint16_t)before - (uint16_t)quick)
        : (uint16_t)((uint16_t)before + (uint16_t)quick);
    const uint8_t after = (uint8_t)full_result;
    uint16_t flags = (uint16_t)(sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (after == 0u) flags = (uint16_t)(flags | SR_Z);
    if ((after & UINT8_C(0x80)) != 0u) flags = (uint16_t)(flags | SR_N);
    const uint8_t quick_byte = (uint8_t)quick;
    const uint8_t overflow_bits = subtract
        ? (uint8_t)((before ^ quick_byte) & (before ^ after))
        : (uint8_t)(~(before ^ quick_byte) & (before ^ after));
    if ((overflow_bits & UINT8_C(0x80)) != 0u) flags = (uint16_t)(flags | SR_V);
    if ((subtract && before < quick_byte) || (!subtract && full_result > UINT8_MAX))
        flags = (uint16_t)(flags | SR_C | SR_X);
    *sr_out = flags;
    return after;
}

/* SUBQ.W for the guest-observed data-register form. */
static uint16_t subtract_quick_word(uint16_t sr, uint16_t before,
                                    unsigned quick, uint16_t *sr_out) {
    const uint32_t full_result = (uint32_t)before - (uint32_t)quick;
    const uint16_t after = (uint16_t)full_result;
    uint16_t flags = (uint16_t)(sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (after == 0u) flags = (uint16_t)(flags | SR_Z);
    if ((after & UINT16_C(0x8000)) != 0u) flags = (uint16_t)(flags | SR_N);
    if ((((before ^ (uint16_t)quick) & (before ^ after)) &
         UINT16_C(0x8000)) != 0u) flags = (uint16_t)(flags | SR_V);
    if (before < (uint16_t)quick) flags = (uint16_t)(flags | SR_C | SR_X);
    *sr_out = flags;
    return after;
}

/* SUBX's register-direct byte/word/long operation. The incoming X bit may
 * increase the subtrahend past the operand mask, so retain it in uint64_t
 * until after both borrow detection and the width-limited result are known. */
static void subtract_extend_data_register(owned_cpu *cpu,
                                          unsigned source_register,
                                          unsigned destination_register,
                                          unsigned width) {
    const unsigned width_bits = width * 8u;
    const uint32_t mask = width == 4u
        ? UINT32_MAX : (UINT32_C(1) << width_bits) - UINT32_C(1);
    const uint32_t sign_bit = UINT32_C(1) << (width_bits - 1u);
    const uint32_t source = cpu->data_registers[source_register] & mask;
    const uint32_t destination_before =
        cpu->data_registers[destination_register];
    const uint32_t destination = destination_before & mask;
    const uint64_t extend = (cpu->sr & SR_X) != 0u ? UINT64_C(1) : UINT64_C(0);
    const uint64_t subtrahend = (uint64_t)source + extend;
    const uint64_t wide_difference = (uint64_t)destination - subtrahend;
    const uint32_t result = (uint32_t)(wide_difference & (uint64_t)mask);
    const int borrow = (uint64_t)destination < subtrahend;

    uint16_t flags =
        (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (result == 0u && (cpu->sr & SR_Z) != 0u)
        flags = (uint16_t)(flags | SR_Z);
    if ((result & sign_bit) != 0u)
        flags = (uint16_t)(flags | SR_N);
    if (((destination ^ source) & (destination ^ result) & sign_bit) != 0u)
        flags = (uint16_t)(flags | SR_V);
    if (borrow != 0)
        flags = (uint16_t)(flags | SR_C | SR_X);

    cpu->data_registers[destination_register] =
        (destination_before & ~mask) | result;
    cpu->sr = flags;
}

/* ADDX's register-direct byte/word/long operation. Keep the carry-in in the
 * wide sum until carry-out is known, while flags and the destination result
 * remain limited to the selected operand width. */
static void add_extend_data_register(owned_cpu *cpu,
                                     unsigned source_register,
                                     unsigned destination_register,
                                     unsigned width) {
    const unsigned width_bits = width * 8u;
    const uint32_t mask = width == 4u
        ? UINT32_MAX : (UINT32_C(1) << width_bits) - UINT32_C(1);
    const uint32_t sign_bit = UINT32_C(1) << (width_bits - 1u);
    const uint32_t source = cpu->data_registers[source_register] & mask;
    const uint32_t destination_before =
        cpu->data_registers[destination_register];
    const uint32_t destination = destination_before & mask;
    const uint64_t extend = (cpu->sr & SR_X) != 0u ? UINT64_C(1) : UINT64_C(0);
    const uint64_t full_sum = (uint64_t)destination + (uint64_t)source + extend;
    const uint32_t result = (uint32_t)(full_sum & (uint64_t)mask);

    uint16_t flags =
        (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (result == 0u && (cpu->sr & SR_Z) != 0u)
        flags = (uint16_t)(flags | SR_Z);
    if ((result & sign_bit) != 0u)
        flags = (uint16_t)(flags | SR_N);
    if (((~(destination ^ source)) & (destination ^ result) & sign_bit) != 0u)
        flags = (uint16_t)(flags | SR_V);
    if (full_sum > (uint64_t)mask)
        flags = (uint16_t)(flags | SR_C | SR_X);

    cpu->data_registers[destination_register] =
        (destination_before & ~mask) | result;
    cpu->sr = flags;
}

static owned_cpu_status fetch_word(owned_cpu *cpu, uint32_t *cursor, uint16_t *word) {
    const uint32_t prefetch_pc = *cursor;
    owned_cpu_status status = read_word(cpu, *cursor, word);
    if (status == OWNED_CPU_OK) {
        /* Keep the 32-bit guest PC; mask only the physical bus transfer. */
        *cursor += UINT32_C(2);
        const size_t slot = cpu->fetch_trace_next;
        cpu->fetch_trace[slot] = (owned_cpu_fetch_trace_event){
            prefetch_pc, *cursor, *word, cpu->fetch_trace_run_sequence,
            cpu->total_cycles};
        cpu->fetch_trace_next = (slot + 1u) % OWNED_CPU_FETCH_TRACE_CAPACITY;
        if (cpu->fetch_trace_count < OWNED_CPU_FETCH_TRACE_CAPACITY)
            ++cpu->fetch_trace_count;
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

/* Every guest-visible write to an address register goes through here. A7 is
 * the active stack pointer (M68000 PRM section 2: SR.S selects the supervisor
 * or user stack pointer as A7), so a write to A7 also updates the banked
 * pointer of the active mode; the inactive bank is untouched and A0-A6 never
 * change either bank. State restore requires address_registers[7] to equal
 * the active bank, so the two must not drift apart. */
static void write_address_register(owned_cpu *cpu, unsigned index, uint32_t value) {
    cpu->address_registers[index] = value;
    if (index == 7u) {
        if ((cpu->sr & SR_S) != 0u) cpu->ssp = value;
        else cpu->usp = value;
    }
}

typedef struct {
    uint32_t address;
    uint32_t updated_base;
    uint64_t address_cycles;
    unsigned base_register;
    unsigned update_after_access;
    unsigned has_base_update;
} data_alterable_memory_ea;

/* MC68000 data-alterable memory modes are (An), (An)+, -(An), d16(An),
 * brief d8(An,Xn), absolute short, and absolute long. This resolver keeps
 * address-register changes deferred so operations can commit them at the
 * correct predecrement/postincrement access boundary. */
static int is_data_alterable_memory_ea(uint16_t opcode) {
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    return mode >= 2u &&
        (mode < 7u || (mode == 7u && reg <= 1u));
}

static int is_word_memory_shift_destination(uint16_t opcode) {
    /* The size field 3 selects the one-bit word memory form. The EA must be
     * memory-alterable; register-result shifts use a separate encoding. */
    const uint16_t family = (uint16_t)(opcode & UINT16_C(0xffc0));
    return (family == UINT16_C(0xe0c0) || family == UINT16_C(0xe2c0)) &&
        is_data_alterable_memory_ea(opcode) != 0;
}

static int is_move_long_address_register_to_memory(uint16_t opcode) {
    const uint16_t destination_ea = (uint16_t)(
        (((opcode >> 6) & UINT16_C(0x0007)) << 3) |
        ((opcode >> 9) & UINT16_C(0x0007)));
    return (opcode & UINT16_C(0xf038)) == UINT16_C(0x2008) &&
        is_data_alterable_memory_ea(destination_ea) != 0;
}

static int is_movem_register_to_memory_ea(uint16_t ea_encoding) {
    const unsigned mode = (unsigned)((ea_encoding >> 3) & 7u);
    const unsigned reg = (unsigned)(ea_encoding & 7u);
    /* MC68000 MOVEM register-to-memory admits (An), -(An), d16(An), brief
     * indexed, and absolute short/long. In particular, (An)+ is not a store
     * destination even though it is a data-alterable EA for other opcodes. */
    return mode == 2u || mode == 4u || mode == 5u || mode == 6u ||
        (mode == 7u && reg <= 1u);
}

static int is_movem_memory_to_register_ea(uint16_t ea_encoding) {
    const unsigned mode = (unsigned)((ea_encoding >> 3) & 7u);
    const unsigned reg = (unsigned)(ea_encoding & 7u);
    /* PRM §4 MOVEM, pp. 4-127–4-130: loads admit (An), (An)+, displacement,
     * brief indexed, absolute, and PC-relative sources. Unlike the store
     * direction, PC-relative sources are legal; predecrement is not. */
    return mode == 2u || mode == 3u || mode == 5u || mode == 6u ||
        (mode == 7u && reg <= 3u);
}

static int is_move_word_immediate_to_data_alterable_memory(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf03f)) != UINT16_C(0x303c)) return 0;
    const unsigned destination_mode = (unsigned)((opcode >> 6) & 7u);
    const unsigned destination_register = (unsigned)((opcode >> 9) & 7u);
    const uint16_t destination_ea = (uint16_t)((destination_mode << 3) |
                                                destination_register);
    return is_data_alterable_memory_ea(destination_ea);
}

static int is_move_byte_immediate_to_data_alterable_memory(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf03f)) != UINT16_C(0x103c)) return 0;
    const unsigned destination_mode = (unsigned)((opcode >> 6) & 7u);
    const unsigned destination_register = (unsigned)((opcode >> 9) & 7u);
    const uint16_t destination_ea = (uint16_t)((destination_mode << 3) |
                                                destination_register);
    return is_data_alterable_memory_ea(destination_ea);
}

static int is_static_bit_modify_data_alterable_memory(uint16_t opcode) {
    if ((opcode & UINT16_C(0xff00)) != UINT16_C(0x0800)) return 0;
    const unsigned operation = (unsigned)((opcode >> 6) & 3u);
    if (operation != 1u && operation != 2u && operation != 3u)
        return 0; /* BCHG/BCLR/BSET; BTST has its own read-only path. */
    return is_data_alterable_memory_ea(opcode);
}

static unsigned negx_data_alterable_memory_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xff00)) != UINT16_C(0x4000) ||
        is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    const unsigned size = (unsigned)((opcode >> 6) & 3u);
    if (size > 2u) return 0u;
    return size == 0u ? 1u : size == 1u ? 2u : 4u;
}

static unsigned neg_data_alterable_memory_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xff00)) != UINT16_C(0x4400) ||
        is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    const unsigned size = (unsigned)((opcode >> 6) & 3u);
    if (size > 2u) return 0u;
    return size == 0u ? 1u : size == 1u ? 2u : 4u;
}

static int dynamic_bit_operation_data_alterable_memory(uint16_t opcode) {
    /* Dynamic BTST/BCHG/BCLR/BSET share the 0000 DDD 1 OO EA format. The
     * data-alterable memory predicate excludes mode-001 MOVEP and PC-relative
     * destinations; the operation field is returned for the shared executor. */
    if ((opcode & UINT16_C(0xf100)) != UINT16_C(0x0100) ||
        is_data_alterable_memory_ea(opcode) == 0) return -1;
    return (int)((opcode >> 6) & UINT16_C(3));
}

static unsigned static_bit_modify_data_register_operation(uint16_t opcode) {
    if ((opcode & UINT16_C(0xfff8)) == UINT16_C(0x0880)) return 2u;
    if ((opcode & UINT16_C(0xfff8)) == UINT16_C(0x08c0)) return 3u;
    return 0u;
}

static unsigned cmp_data_alterable_memory_source_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0xb000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode > 2u || is_data_alterable_memory_ea(opcode) == 0) return 0u;
    return opmode == 0u ? 1u : opmode == 1u ? 2u : 4u;
}

static unsigned cmpa_data_alterable_memory_source_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0xb000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if ((opmode != 3u && opmode != 7u) ||
        is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    return opmode == 3u ? 2u : 4u;
}

static unsigned adda_data_alterable_memory_source_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0xd000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if ((opmode != 3u && opmode != 7u) ||
        is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    return opmode == 3u ? 2u : 4u;
}

static unsigned adda_register_direct_source_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0xd000)) return 0u;
    const unsigned source_mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (source_mode > 1u || (opmode != 3u && opmode != 7u)) return 0u;
    return opmode == 3u ? 2u : 4u;
}

static unsigned clr_data_register_direct_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xfff8)) == UINT16_C(0x4200)) return 1u;
    if ((opcode & UINT16_C(0xfff8)) == UINT16_C(0x4240)) return 2u;
    if ((opcode & UINT16_C(0xfff8)) == UINT16_C(0x4280)) return 4u;
    return 0u;
}

static unsigned count_set_bits_word(uint16_t value) {
    unsigned count = 0u;
    while (value != 0u) {
        count += (unsigned)(value & UINT16_C(1));
        value = (uint16_t)(value >> 1);
    }
    return count;
}

static int is_multiply_word_source_to_data_register(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf0c0)) != UINT16_C(0xc0c0)) return 0;
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    if (mode == 0u || is_data_alterable_memory_ea(opcode) != 0) return 1;
    /* MULS/MULU word sources permit the two PC-relative forms and immediate,
     * but not An-direct or reserved mode-7 EAs (PRM §4 MULS/MULU). */
    return mode == 7u && reg >= 2u && reg <= 4u;
}

static unsigned muls_word_transition_count(uint16_t source) {
    /* UM Rev. 9.1 Chapter 8 Table 8-4 p. 8-4 counts adjacent 10/01 pairs
     * after appending a zero LSB to the 16-bit multiplier. XOR with the
     * one-bit shift marks each transition, including source bit zero vs 0. */
    const uint16_t transitions = (uint16_t)(source ^
        (uint16_t)(source << 1));
    return count_set_bits_word(transitions);
}

static int is_divu_word_source_to_data_register(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf1c0)) != UINT16_C(0x80c0)) return 0;
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    if (mode == 0u || is_data_alterable_memory_ea(opcode) != 0) return 1;
    /* DIVU's readable source EAs also include PC-relative and immediate.
     * Address-register direct and reserved mode-7 encodings are excluded. */
    return mode == 7u && reg >= 2u && reg <= 4u;
}

static int is_divs_word_source_to_data_register(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf1c0)) != UINT16_C(0x81c0)) return 0;
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    /* Admit Dn and the immediate data-word source observed in the selected
     * guest. Keep An-direct, memory and PC-relative forms explicitly closed. */
    return mode == 0u || (mode == 7u && reg == 4u);
}

static uint64_t divs_word_register_cycles(int64_t dividend,
                                          int32_t divisor) {
    /* The MC68000's signed divide timing is operand-dependent. This
     * independently written recurrence follows the published report's
     * register-form observations (best 120/122, worst 156 clocks), which are
     * only partially hardware-tested and conflict with the UM's 158-clock
     * maximum/less-than-10%-spread note. No GPL implementation text is used.
     * Caller excludes divide-by-zero. */
    uint64_t magnitude = dividend < 0
        ? (uint64_t)(-dividend) : (uint64_t)dividend;
    const uint32_t divisor_magnitude = divisor < 0
        ? (uint32_t)(-(int64_t)divisor) : (uint32_t)divisor;
    uint64_t machine_cycles = UINT64_C(6);
    if (dividend < 0) ++machine_cycles;

    /* This early absolute-overflow condition is distinct from the signed
     * quotient overflow discovered after division. */
    if ((magnitude >> 16) >= (uint64_t)divisor_magnitude)
        return (machine_cycles + UINT64_C(2)) * UINT64_C(2);

    uint64_t absolute_quotient = magnitude / divisor_magnitude;
    machine_cycles += UINT64_C(55);
    if (divisor >= 0) {
        if (dividend < 0) ++machine_cycles;
        else --machine_cycles;
    }

    /* The published model counts the quotient's 15 leading bits after each
     * shift. Test the sign bit explicitly instead of an out-of-range
     * uint16_t-to-int16_t conversion. */
    for (unsigned stage = 0u; stage < 15u; ++stage) {
        if ((absolute_quotient & UINT64_C(0x8000)) == 0u)
            ++machine_cycles;
        absolute_quotient <<= 1;
    }
    return machine_cycles * UINT64_C(2);
}

static uint64_t divu_word_register_cycles(uint32_t dividend,
                                          uint16_t divisor) {
    /* The MC68000's restoring divide works through 15 quotient stages for
     * the register-operand portion of DIVU.W. This explicit partial-remainder
     * model follows the published 76..136-clock MC68000 timing behavior: a
     * stage that needs a trial subtraction costs two clocks, one that rejects
     * it costs four, and a 17th-bit remainder correction costs none. The
     * timing report is differential evidence with partial hardware testing,
     * not a hardware qualification for this core. It is expressed here as a
     * fresh remainder recurrence; no GPL implementation text is reused.
     * Caller excludes zero divisor and quotient overflow. */
    uint32_t partial_remainder = dividend >> 16;
    uint64_t clocks = UINT64_C(76);
    for (unsigned bit = 15u; bit > 0u; --bit) {
        partial_remainder = (partial_remainder << 1) |
            ((dividend >> bit) & UINT32_C(1));
        if ((partial_remainder & UINT32_C(0x10000)) != 0u) {
            partial_remainder -= (uint32_t)divisor;
        } else if (partial_remainder >= (uint32_t)divisor) {
            partial_remainder -= (uint32_t)divisor;
            clocks += UINT64_C(2);
        } else {
            clocks += UINT64_C(4);
        }
    }
    return clocks;
}

static unsigned or_data_alterable_memory_source_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0x8000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode > 2u || is_data_alterable_memory_ea(opcode) == 0) return 0u;
    return opmode == 0u ? 1u : opmode == 1u ? 2u : 4u;
}

static unsigned and_data_alterable_memory_source_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0xc000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode > 2u || is_data_alterable_memory_ea(opcode) == 0) return 0u;
    return opmode == 0u ? 1u : opmode == 1u ? 2u : 4u;
}

static unsigned and_data_register_memory_destination_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0xc000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode < 4u || opmode > 6u ||
        is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    return opmode == 4u ? 1u : opmode == 5u ? 2u : 4u;
}

static unsigned or_data_register_width(uint16_t opcode) {
    /* This is OR <Dn>,Dn: direction=EA-to-Dn, source mode=Dn direct. The
     * opmode selects byte/word/long; opmode 011 remains DIVU.W. */
    if ((opcode & UINT16_C(0xf138)) != UINT16_C(0x8000)) return 0u;
    switch ((opcode >> 6) & 3u) {
        case 0u: return 1u;
        case 1u: return 2u;
        case 2u: return 4u;
        default: return 0u;
    }
}

static unsigned add_data_alterable_memory_source_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0xd000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode > 2u || is_data_alterable_memory_ea(opcode) == 0) return 0u;
    return opmode == 0u ? 1u : opmode == 1u ? 2u : 4u;
}

static unsigned add_data_register_direct_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0xd000) ||
        ((opcode >> 3) & 7u) != 0u)
        return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode > 2u) return 0u;
    return opmode == 0u ? 1u : opmode == 1u ? 2u : 4u;
}

static unsigned sub_data_register_source_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0x9000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode > 2u) return 0u; /* SUBA and SUBX remain separate. */
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    if (mode == 0u || (mode == 1u && opmode != 0u) ||
        is_data_alterable_memory_ea(opcode) != 0 ||
        (mode == 7u && reg >= 2u && reg <= 4u))
        return opmode == 0u ? 1u : opmode == 1u ? 2u : 4u;
    return 0u;
}

static unsigned add_data_register_memory_destination_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0xd000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode < 4u || opmode > 6u ||
        is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    return opmode == 4u ? 1u : opmode == 5u ? 2u : 4u;
}

static unsigned sub_data_register_memory_destination_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0x9000)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode < 4u || opmode > 6u ||
        is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    return opmode == 4u ? 1u : opmode == 5u ? 2u : 4u;
}

static unsigned eor_data_register_memory_destination_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf100)) != UINT16_C(0xb100)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode < 4u || opmode > 6u ||
        is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    return opmode == 4u ? 1u : opmode == 5u ? 2u : 4u;
}

static unsigned or_data_register_memory_destination_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf100)) != UINT16_C(0x8100)) return 0u;
    const unsigned opmode = (unsigned)((opcode >> 6) & 7u);
    if (opmode < 4u || opmode > 6u ||
        is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    return opmode == 4u ? 1u : opmode == 5u ? 2u : 4u;
}

static unsigned immediate_arithmetic_memory_width(uint16_t opcode) {
    const uint16_t operation = (uint16_t)(opcode & UINT16_C(0xff00));
    if (operation != UINT16_C(0x0400) &&
        operation != UINT16_C(0x0600))
        return 0u;
    const unsigned size_code = (unsigned)((opcode >> 6) & 3u);
    if (size_code == 3u || is_data_alterable_memory_ea(opcode) == 0)
        return 0u;
    return size_code == 0u ? 1u : size_code == 1u ? 2u : 4u;
}

static unsigned subi_immediate_data_register_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xff00)) != UINT16_C(0x0400) ||
        ((opcode >> 3) & 7u) != 0u)
        return 0u;
    const unsigned size_code = (unsigned)((opcode >> 6) & 3u);
    return size_code == 0u ? 1u : size_code == 1u ? 2u :
           size_code == 2u ? 4u : 0u;
}

static unsigned addi_immediate_data_register_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xff00)) != UINT16_C(0x0600) ||
        ((opcode >> 3) & 7u) != 0u)
        return 0u;
    const unsigned size_code = (unsigned)((opcode >> 6) & 3u);
    return size_code == 0u ? 1u : size_code == 1u ? 2u :
           size_code == 2u ? 4u : 0u;
}

static unsigned rotate_immediate_data_register_width(uint16_t opcode) {
    switch (opcode & UINT16_C(0xf1f8)) {
        case UINT16_C(0xe018):
        case UINT16_C(0xe118):
            return 1u;
        case UINT16_C(0xe058):
        case UINT16_C(0xe158):
            return 2u;
        case UINT16_C(0xe098):
        case UINT16_C(0xe198):
            return 4u;
        default:
            return 0u;
    }
}

static uint64_t move_immediate_data_alterable_memory_cycles(
    uint16_t destination_ea) {
    const unsigned mode = (unsigned)((destination_ea >> 3) & 7u);
    const unsigned reg = (unsigned)(destination_ea & 7u);
    /* UM Rev. 9.1 Table 8-2 p. 8-2 lists MOVE immediate-to-memory totals
     * directly. In particular, -(An) is 12 clocks, not the generic EA's
     * 8-clock surcharge plus Table 8-1's six predecrement clocks. */
    switch (mode) {
        case 2u:
        case 3u:
        case 4u:
            return UINT64_C(12);
        case 5u:
            return UINT64_C(16);
        case 6u:
            return UINT64_C(18);
        case 7u:
            if (reg == 0u) return UINT64_C(16);
            if (reg == 1u) return UINT64_C(20);
            return 0u;
        default:
            return 0u;
    }
}

static owned_cpu_status resolve_data_alterable_memory_ea(
    owned_cpu *cpu, uint16_t opcode, uint32_t *cursor, unsigned width,
    data_alterable_memory_ea *ea) {
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    const unsigned base_step = width == 1u && reg == 7u ? 2u : width;
    const unsigned long_operand = width == 4u;
    memset(ea, 0, sizeof(*ea));

    switch (mode) {
        case 2u:
            ea->address = cpu->address_registers[reg];
            ea->address_cycles = long_operand != 0u ? UINT64_C(8) : UINT64_C(4);
            return OWNED_CPU_OK;
        case 3u:
            ea->address = cpu->address_registers[reg];
            ea->updated_base = ea->address + (uint32_t)base_step;
            ea->base_register = reg;
            ea->has_base_update = 1u;
            ea->update_after_access = 1u;
            ea->address_cycles = long_operand != 0u ? UINT64_C(8) : UINT64_C(4);
            return OWNED_CPU_OK;
        case 4u:
            ea->updated_base = cpu->address_registers[reg] - (uint32_t)base_step;
            ea->address = ea->updated_base;
            ea->base_register = reg;
            ea->has_base_update = 1u;
            ea->address_cycles = long_operand != 0u ? UINT64_C(10) : UINT64_C(6);
            return OWNED_CPU_OK;
        case 5u: {
            uint16_t displacement = 0u;
            owned_cpu_status status = fetch_word(cpu, cursor, &displacement);
            if (status != OWNED_CPU_OK) return status;
            ea->address = cpu->address_registers[reg] + sign_extend_word(displacement);
            ea->address_cycles = long_operand != 0u ? UINT64_C(12) : UINT64_C(8);
            return OWNED_CPU_OK;
        }
        case 6u: {
            uint16_t extension = 0u;
            owned_cpu_status status = fetch_word(cpu, cursor, &extension);
            if (status != OWNED_CPU_OK) return status;
            /* The MC68000 brief extension reserves bits 10..8. Full-format
             * 68020 extensions are outside this CPU subset. */
            if ((extension & UINT16_C(0x0700)) != 0u)
                return OWNED_CPU_UNSUPPORTED_OPCODE;
            const unsigned index_register = (unsigned)((extension >> 12) & 7u);
            uint32_t index = (extension & UINT16_C(0x8000)) != 0u
                ? cpu->address_registers[index_register]
                : cpu->data_registers[index_register];
            if ((extension & UINT16_C(0x0800)) == 0u)
                index = sign_extend_word((uint16_t)index);
            ea->address = cpu->address_registers[reg] + index +
                          sign_extend_byte((uint8_t)extension);
            ea->address_cycles = long_operand != 0u ? UINT64_C(14) : UINT64_C(10);
            return OWNED_CPU_OK;
        }
        case 7u:
            if (reg == 0u) {
                uint16_t absolute = 0u;
                owned_cpu_status status = fetch_word(cpu, cursor, &absolute);
                if (status != OWNED_CPU_OK) return status;
                ea->address = sign_extend_word(absolute);
                ea->address_cycles = long_operand != 0u ? UINT64_C(12) : UINT64_C(8);
                return OWNED_CPU_OK;
            }
            if (reg == 1u) {
                uint16_t high = 0u;
                uint16_t low = 0u;
                owned_cpu_status status = fetch_word(cpu, cursor, &high);
                if (status == OWNED_CPU_OK) status = fetch_word(cpu, cursor, &low);
                if (status != OWNED_CPU_OK) return status;
                ea->address = ((uint32_t)high << 16) | (uint32_t)low;
                ea->address_cycles = long_operand != 0u ? UINT64_C(16) : UINT64_C(12);
                return OWNED_CPU_OK;
            }
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        default:
            return OWNED_CPU_UNSUPPORTED_OPCODE;
    }
}

static owned_cpu_status resolve_memory_to_register_source_ea(
    owned_cpu *cpu, uint16_t opcode, uint32_t *cursor, unsigned width,
    data_alterable_memory_ea *ea) {
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    if (mode != 7u || reg < 2u)
        return resolve_data_alterable_memory_ea(cpu, opcode, cursor, width, ea);

    /* Read-only memory sources can additionally admit d16(PC) and brief
     * d8(PC,Xn). The PC base is the extension-word address, per PRM §2.2.11. */
    memset(ea, 0, sizeof(*ea));
    const uint32_t extension_address = *cursor;
    uint16_t extension = 0u;
    owned_cpu_status status = fetch_word(cpu, cursor, &extension);
    if (status != OWNED_CPU_OK) return status;
    if (reg == 2u) {
        ea->address = extension_address + sign_extend_word(extension);
        ea->address_cycles = width == 4u ? UINT64_C(12) : UINT64_C(8);
        return OWNED_CPU_OK;
    }

    /* Only the MC68000 brief index extension is in this owned subset. */
    if ((extension & UINT16_C(0x0700)) != 0u)
        return OWNED_CPU_UNSUPPORTED_OPCODE;
    const unsigned index_register = (unsigned)((extension >> 12) & 7u);
    uint32_t index = (extension & UINT16_C(0x8000)) != 0u
        ? cpu->address_registers[index_register]
        : cpu->data_registers[index_register];
    if ((extension & UINT16_C(0x0800)) == 0u)
        index = sign_extend_word((uint16_t)index);
    ea->address = extension_address + index +
                  sign_extend_byte((uint8_t)extension);
    ea->address_cycles = width == 4u ? UINT64_C(14) : UINT64_C(10);
    return OWNED_CPU_OK;
}

static unsigned data_alterable_memory_ea_slot(uint16_t opcode) {
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    if (mode >= 2u && mode <= 6u) return mode - 2u;
    if (mode == 7u && reg <= 1u) return reg == 0u ? 5u : 6u;
    return 7u;
}

static unsigned logical_immediate_data_alterable_memory_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xf000)) != 0u) return 0u;
    const uint16_t operation = (uint16_t)(opcode & UINT16_C(0x0f00));
    if (operation != UINT16_C(0x0000) && operation != UINT16_C(0x0200) &&
        operation != UINT16_C(0x0a00))
        return 0u;
    const unsigned size = (unsigned)((opcode >> 6) & 3u);
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    const unsigned width = size == 0u ? 1u : size == 1u ? 2u :
                           size == 2u ? 4u : 0u;
    if (width == 0u) return 0u;
    if ((mode >= 2u && mode <= 6u) || (mode == 7u && reg <= 1u))
        return width;
    return 0u;
}

static unsigned andi_immediate_data_register_width(uint16_t opcode) {
    if ((opcode & UINT16_C(0xfff8)) == UINT16_C(0x0200)) return 1u;
    if ((opcode & UINT16_C(0xfff8)) == UINT16_C(0x0240)) return 2u;
    if ((opcode & UINT16_C(0xfff8)) == UINT16_C(0x0280)) return 4u;
    return 0u;
}

static unsigned immediate_logic_ccr_operation(uint16_t opcode) {
    /* The MC68000 CCR forms are the size-byte special encodings with EA
     * 111100; full-SR word encodings and all other immediate EAs stay apart. */
    switch (opcode) {
        case UINT16_C(0x003c): return 1u; /* ORI.B #<data>,CCR */
        case UINT16_C(0x023c): return 2u; /* ANDI.B #<data>,CCR */
        case UINT16_C(0x0a3c): return 3u; /* EORI.B #<data>,CCR */
        default: return 0u;
    }
}

static uint64_t move_byte_word_memory_to_data_alterable_memory_cycles(
    uint16_t opcode) {
    static const uint8_t cycles[7][7] = {
        {12u, 12u, 12u, 16u, 18u, 16u, 20u},
        {12u, 12u, 12u, 16u, 18u, 16u, 20u},
        {14u, 14u, 14u, 18u, 20u, 18u, 22u},
        {16u, 16u, 16u, 20u, 22u, 20u, 24u},
        {18u, 18u, 18u, 22u, 24u, 22u, 26u},
        {16u, 16u, 16u, 20u, 22u, 20u, 24u},
        {20u, 20u, 20u, 24u, 26u, 24u, 28u},
    };
    const uint16_t operation = (uint16_t)(opcode & UINT16_C(0xf000));
    if (operation != UINT16_C(0x1000) &&
        operation != UINT16_C(0x3000)) return 0u;
    const uint16_t source_ea = (uint16_t)(opcode & UINT16_C(0x003f));
    const uint16_t destination_ea = (uint16_t)(
        (((opcode >> 6) & 7u) << 3) | ((opcode >> 9) & 7u));
    if (is_data_alterable_memory_ea(source_ea) == 0 ||
        is_data_alterable_memory_ea(destination_ea) == 0)
        return 0u;
    const unsigned source_slot = data_alterable_memory_ea_slot(source_ea);
    const unsigned destination_slot =
        data_alterable_memory_ea_slot(destination_ea);
    if (source_slot >= 7u || destination_slot >= 7u) return 0u;
    return cycles[source_slot][destination_slot];
}

static uint64_t move_long_memory_to_memory_cycles(uint16_t opcode) {
    /* MC68000 UM Rev. 9.1 Chapter 8 Table 8-3, printed p. 8-3, lists the
     * complete MOVE.L data-alterable memory-to-memory timing matrix. */
    static const uint8_t cycles[7][7] = {
        {20u, 20u, 20u, 24u, 26u, 24u, 28u},
        {20u, 20u, 20u, 24u, 26u, 24u, 28u},
        {22u, 22u, 22u, 26u, 28u, 26u, 30u},
        {24u, 24u, 24u, 28u, 30u, 28u, 32u},
        {26u, 26u, 26u, 30u, 32u, 30u, 34u},
        {24u, 24u, 24u, 28u, 30u, 28u, 32u},
        {28u, 28u, 28u, 32u, 34u, 32u, 36u},
    };
    if ((opcode & UINT16_C(0xf000)) != UINT16_C(0x2000)) return 0u;
    const uint16_t source_ea = (uint16_t)(opcode & UINT16_C(0x003f));
    const uint16_t destination_ea = (uint16_t)(
        (((opcode >> 6) & 7u) << 3) | ((opcode >> 9) & 7u));
    if (is_data_alterable_memory_ea(source_ea) == 0 ||
        is_data_alterable_memory_ea(destination_ea) == 0)
        return 0u;
    const unsigned source_slot = data_alterable_memory_ea_slot(source_ea);
    const unsigned destination_slot =
        data_alterable_memory_ea_slot(destination_ea);
    if (source_slot >= 7u || destination_slot >= 7u) return 0u;
    return cycles[source_slot][destination_slot];
}

static uint32_t addsub_value(uint16_t sr, uint32_t before, uint32_t operand,
                              unsigned width, int subtract, uint16_t *sr_out) {
    const uint64_t mask = width == 1u ? UINT64_C(0xff) :
                          width == 2u ? UINT64_C(0xffff) : UINT64_C(0xffffffff);
    const uint32_t sign_bit = width == 1u ? UINT32_C(0x80) :
                              width == 2u ? UINT32_C(0x8000) : UINT32_C(0x80000000);
    before &= (uint32_t)mask;
    operand &= (uint32_t)mask;
    const uint64_t sum = (uint64_t)before + (uint64_t)operand;
    const uint32_t after = (uint32_t)((subtract
        ? (uint64_t)((uint32_t)(before - operand)) : sum) & mask);
    uint16_t flags = (uint16_t)(sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (after == 0u) flags = (uint16_t)(flags | SR_Z);
    if ((after & sign_bit) != 0u) flags = (uint16_t)(flags | SR_N);
    const uint32_t overflow = subtract
        ? ((before ^ operand) & (before ^ after))
        : (~(before ^ operand) & (before ^ after));
    if ((overflow & sign_bit) != 0u) flags = (uint16_t)(flags | SR_V);
    if ((subtract != 0 && before < operand) ||
        (subtract == 0 && sum > mask))
        flags = (uint16_t)(flags | SR_C | SR_X);
    *sr_out = flags;
    return after;
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
    write_address_register(cpu, 7u, stack_pointer);
    owned_cpu_status status = write_word(cpu, stack_pointer, value);
    if (status != OWNED_CPU_OK) {
        cpu->faulted = 1u;
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static owned_cpu_status push_long(owned_cpu *cpu, uint32_t value) {
    uint32_t stack_pointer = cpu->address_registers[7] - UINT32_C(4);
    write_address_register(cpu, 7u, stack_pointer);
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

static int condition_true(uint16_t sr, unsigned condition) {
    const int c = (sr & SR_C) != 0u;
    const int v = (sr & SR_V) != 0u;
    const int z = (sr & SR_Z) != 0u;
    const int n = (sr & SR_N) != 0u;
    switch (condition) {
        case 0u: return 1;               /* T */
        case 1u: return 0;               /* F */
        case 2u: return !c && !z;       /* HI */
        case 3u: return c || z;         /* LS */
        case 4u: return !c;             /* CC */
        case 5u: return c;              /* CS */
        case 6u: return !z;             /* NE */
        case 7u: return z;              /* EQ */
        case 8u: return !v;             /* VC */
        case 9u: return v;              /* VS */
        case 10u: return !n;            /* PL */
        case 11u: return n;             /* MI */
        case 12u: return n == v;         /* GE */
        case 13u: return n != v;         /* LT */
        case 14u: return !z && n == v;   /* GT */
        case 15u: return z || n != v;    /* LE */
        default: return 0;
    }
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

static void set_move_word_flags(owned_cpu *cpu, uint16_t result) {
    cpu->sr = (uint16_t)(cpu->sr & (uint16_t)~SR_MOVE_FLAGS);
    if (result == 0u) cpu->sr = (uint16_t)(cpu->sr | SR_Z);
    if ((result & UINT16_C(0x8000)) != 0u) cpu->sr = (uint16_t)(cpu->sr | SR_N);
}

static owned_cpu_status execute_eor_data_register_to_memory(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const unsigned width = eor_data_register_memory_destination_width(opcode);
    data_alterable_memory_ea ea;
    owned_cpu_status status = resolve_data_alterable_memory_ea(
        cpu, opcode, cursor, width, &ea);
    if (status != OWNED_CPU_OK) {
        if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = opcode;
        }
        return status;
    }

    /* MC68000 UM Rev. 9.1 Table 8-4 gives EOR Dn,<M> 8(1/1)+ for byte/word
     * and 12(1/2)+ for long. Table 8-1 contributes this destination EA's
     * address calculation. */
    const uint64_t instruction_cycles =
        (width == 4u ? UINT64_C(12) : UINT64_C(8)) + ea.address_cycles;
    if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        /* The pinned generated EOR handlers use the EA PI/PD helpers before
         * the aligned RMW read. This partial vector-3 state is differential
         * behavior only; primary manuals do not specify this chronology. */
        if (ea.has_base_update != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         ea.address, 0, 1);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
    if (status != OWNED_CPU_OK) return status;
    /* Predecrement precedes the RMW read. Postincrement is committed after
     * the entire operand read, before its write callback. */
    if (ea.has_base_update != 0u && ea.update_after_access == 0u)
        write_address_register(cpu, ea.base_register, ea.updated_base);

    uint32_t operand = 0u;
    if (width == 1u) {
        uint8_t byte = 0u;
        status = read_byte(cpu, ea.address, &byte);
        operand = byte;
    } else if (width == 2u) {
        uint16_t word = 0u;
        status = read_word(cpu, ea.address, &word);
        operand = word;
    } else {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = read_word(cpu, ea.address, &high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, ea.address + UINT32_C(2), &low);
        operand = ((uint32_t)high << 16) | (uint32_t)low;
    }
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (ea.has_base_update != 0u && ea.update_after_access != 0u)
        write_address_register(cpu, ea.base_register, ea.updated_base);

    const unsigned source_register = (unsigned)((opcode >> 9) & 7u);
    const uint32_t mask = width == 1u ? UINT32_C(0xff) :
                          width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
    const uint32_t result = (operand ^ cpu->data_registers[source_register]) & mask;
    if (width == 1u) {
        status = write_byte(cpu, ea.address, (uint8_t)result);
    } else if (width == 2u) {
        status = write_word(cpu, ea.address, (uint16_t)result);
    } else {
        status = write_word(cpu, ea.address, (uint16_t)(result >> 16));
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, ea.address + UINT32_C(2),
                                (uint16_t)result);
    }
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (width == 1u) set_move_byte_flags(cpu, (uint8_t)result);
    else if (width == 2u) set_move_word_flags(cpu, (uint16_t)result);
    else set_move_flags(cpu, result);
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static owned_cpu_status execute_and_data_register_to_memory(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const unsigned width = and_data_register_memory_destination_width(opcode);
    data_alterable_memory_ea ea;
    owned_cpu_status status = resolve_data_alterable_memory_ea(
        cpu, opcode, cursor, width, &ea);
    if (status != OWNED_CPU_OK) {
        if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = opcode;
        }
        return status;
    }

    /* NXP MC68000 UM Rev. 9.1 Table 8-4 p. 8-4 gives AND Dn,<M> 8(1/1)+
     * for byte/word and 12(1/2)+ for long. Table 8-1 p. 8-2 adds the
     * destination effective-address cost. PRM §4 AND pp. 4-15 to 4-17
     * defines source AND destination -> destination, N/Z from the result,
     * cleared V/C and preserved X. These are MC68000 model timings; the
     * owned bus callback order is not an independent silicon trace. */
    const uint64_t instruction_cycles =
        (width == 4u ? UINT64_C(12) : UINT64_C(8)) + ea.address_cycles;
    if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        /* The manual establishes vector 3 for the odd access, not this
         * partial auto-update chronology. Preserve the existing AND.W
         * (An)+ boundary and keep the detail as owned-core behavior. */
        if (ea.has_base_update != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         ea.address, 0, 1);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
    if (status != OWNED_CPU_OK) return status;
    if (ea.has_base_update != 0u && ea.update_after_access == 0u)
        write_address_register(cpu, ea.base_register, ea.updated_base);

    uint32_t operand = 0u;
    if (width == 1u) {
        uint8_t byte = 0u;
        status = read_byte(cpu, ea.address, &byte);
        operand = byte;
    } else if (width == 2u) {
        uint16_t word = 0u;
        status = read_word(cpu, ea.address, &word);
        operand = word;
    } else {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = read_word(cpu, ea.address, &high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, ea.address + UINT32_C(2), &low);
        operand = ((uint32_t)high << 16) | (uint32_t)low;
    }
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (ea.has_base_update != 0u && ea.update_after_access != 0u)
        write_address_register(cpu, ea.base_register, ea.updated_base);

    const unsigned source_register = (unsigned)((opcode >> 9) & 7u);
    const uint32_t mask = width == 1u ? UINT32_C(0xff) :
                          width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
    const uint32_t result =
        (operand & cpu->data_registers[source_register]) & mask;
    if (width == 1u) {
        status = write_byte(cpu, ea.address, (uint8_t)result);
    } else if (width == 2u) {
        status = write_word(cpu, ea.address, (uint16_t)result);
    } else {
        status = write_word(cpu, ea.address, (uint16_t)(result >> 16));
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, ea.address + UINT32_C(2),
                                (uint16_t)result);
    }
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (width == 1u) set_move_byte_flags(cpu, (uint8_t)result);
    else if (width == 2u) set_move_word_flags(cpu, (uint16_t)result);
    else set_move_flags(cpu, result);
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static owned_cpu_status execute_or_data_register_to_memory(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const unsigned width = or_data_register_memory_destination_width(opcode);
    data_alterable_memory_ea ea;
    owned_cpu_status status = resolve_data_alterable_memory_ea(
        cpu, opcode, cursor, width, &ea);
    if (status != OWNED_CPU_OK) {
        if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = opcode;
        }
        return status;
    }

    /* NXP MC68000 UM Rev. 9.1 Table 8-4 gives OR Dn,<M> 8(1/1)+ for
     * byte/word and 12(1/2)+ for long. Table 8-1 adds destination-EA cost. */
    const uint64_t instruction_cycles =
        (width == 4u ? UINT64_C(12) : UINT64_C(8)) + ea.address_cycles;
    if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        /* The manuals establish vector 3 for an odd word/long access but do
         * not specify auto-update chronology. Match the shared data-alterable
         * resolver's already-qualified EOR RMW exception boundary. */
        if (ea.has_base_update != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         ea.address, 0, 1);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
    if (status != OWNED_CPU_OK) return status;
    if (ea.has_base_update != 0u && ea.update_after_access == 0u)
        write_address_register(cpu, ea.base_register, ea.updated_base);

    uint32_t operand = 0u;
    if (width == 1u) {
        uint8_t byte = 0u;
        status = read_byte(cpu, ea.address, &byte);
        operand = byte;
    } else if (width == 2u) {
        uint16_t word = 0u;
        status = read_word(cpu, ea.address, &word);
        operand = word;
    } else {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = read_word(cpu, ea.address, &high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, ea.address + UINT32_C(2), &low);
        operand = ((uint32_t)high << 16) | (uint32_t)low;
    }
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (ea.has_base_update != 0u && ea.update_after_access != 0u)
        write_address_register(cpu, ea.base_register, ea.updated_base);

    const unsigned source_register = (unsigned)((opcode >> 9) & 7u);
    const uint32_t mask = width == 1u ? UINT32_C(0xff) :
                          width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
    const uint32_t result =
        (operand | cpu->data_registers[source_register]) & mask;
    if (width == 1u) {
        status = write_byte(cpu, ea.address, (uint8_t)result);
    } else if (width == 2u) {
        status = write_word(cpu, ea.address, (uint16_t)result);
    } else {
        status = write_word(cpu, ea.address, (uint16_t)(result >> 16));
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, ea.address + UINT32_C(2),
                                (uint16_t)result);
    }
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (width == 1u) set_move_byte_flags(cpu, (uint8_t)result);
    else if (width == 2u) set_move_word_flags(cpu, (uint16_t)result);
    else set_move_flags(cpu, result);
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static owned_cpu_status execute_word_memory_shift(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    data_alterable_memory_ea ea;
    owned_cpu_status status = resolve_data_alterable_memory_ea(
        cpu, opcode, cursor, 2u, &ea);
    if (status != OWNED_CPU_OK) {
        if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = opcode;
        }
        return status;
    }

    const int arithmetic_right = (opcode & UINT16_C(0x0200)) == 0u;
    /* MC68000 UM Rev. 9.1 Table 8-7 p. 8-6 gives word-memory ASR/LSR
     * 8(1/1)+; Table 8-1 p. 8-2 supplies the destination EA time. */
    const uint64_t instruction_cycles = UINT64_C(8) + ea.address_cycles;
    if ((ea.address & UINT32_C(1)) != 0u) {
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        /* The manual establishes vector 3 for an odd word access, but not
         * this partial base-update chronology. Match the existing owned RMW
         * contract and keep it distinct from a hardware claim. */
        if (ea.has_base_update != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         ea.address, 0, 1);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
    if (status != OWNED_CPU_OK) return status;
    if (ea.has_base_update != 0u && ea.update_after_access == 0u)
        write_address_register(cpu, ea.base_register, ea.updated_base);

    uint16_t operand = 0u;
    status = read_word(cpu, ea.address, &operand);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (ea.has_base_update != 0u && ea.update_after_access != 0u)
        write_address_register(cpu, ea.base_register, ea.updated_base);

    uint16_t result = (uint16_t)(operand >> 1);
    if (arithmetic_right != 0 && (operand & UINT16_C(0x8000)) != 0u)
        result = (uint16_t)(result | UINT16_C(0x8000));
    uint16_t flags = (uint16_t)(cpu->sr &
        (uint16_t)~(SR_X | SR_N | SR_Z | SR_V | SR_C));
    if (arithmetic_right != 0 && (result & UINT16_C(0x8000)) != 0u)
        flags = (uint16_t)(flags | SR_N);
    if (result == 0u) flags = (uint16_t)(flags | SR_Z);
    if ((operand & UINT16_C(1)) != 0u)
        flags = (uint16_t)(flags | SR_X | SR_C);

    status = write_word(cpu, ea.address, result);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    cpu->sr = flags;
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static owned_cpu_status execute_move_byte_word_memory_to_memory(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const unsigned width = (opcode & UINT16_C(0xf000)) == UINT16_C(0x1000)
                               ? 1u : 2u;
    const uint64_t instruction_cycles =
        move_byte_word_memory_to_data_alterable_memory_cycles(opcode);
    const uint16_t source_ea = (uint16_t)(opcode & UINT16_C(0x003f));
    const uint16_t destination_ea = (uint16_t)(
        (((opcode >> 6) & 7u) << 3) | ((opcode >> 9) & 7u));
    data_alterable_memory_ea source;
    data_alterable_memory_ea destination;
    owned_cpu_status status = preflight_event(
        cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
    if (status != OWNED_CPU_OK) return status;

    status = resolve_data_alterable_memory_ea(cpu, source_ea, cursor, width,
                                               &source);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (width == 2u && (source.address & UINT32_C(1)) != 0u) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (source.has_base_update != 0u)
            write_address_register(cpu, source.base_register,
                                   source.updated_base);
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         source.address, 0, 1);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    if (source.has_base_update != 0u && source.update_after_access == 0u)
        write_address_register(cpu, source.base_register, source.updated_base);
    uint16_t word_value = 0u;
    uint8_t byte_value = 0u;
    status = width == 1u
        ? read_byte(cpu, source.address, &byte_value)
        : read_word(cpu, source.address, &word_value);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (source.has_base_update != 0u && source.update_after_access != 0u)
        write_address_register(cpu, source.base_register, source.updated_base);

    /* Source postincrement is visible while destination extensions and its
     * effective address are resolved, including when both EAs alias. */
    status = resolve_data_alterable_memory_ea(cpu, destination_ea, cursor,
                                               width, &destination);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (width == 2u && (destination.address & UINT32_C(1)) != 0u) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (destination.has_base_update != 0u)
            write_address_register(cpu, destination.base_register,
                                   destination.updated_base);
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         destination.address, 0, 0);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }
    if (destination.has_base_update != 0u &&
        destination.update_after_access == 0u)
        write_address_register(cpu, destination.base_register,
                               destination.updated_base);
    status = width == 1u
        ? write_byte(cpu, destination.address, byte_value)
        : write_word(cpu, destination.address, word_value);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (destination.has_base_update != 0u &&
        destination.update_after_access != 0u)
        write_address_register(cpu, destination.base_register,
                               destination.updated_base);
    if (width == 1u) set_move_byte_flags(cpu, byte_value);
    else set_move_word_flags(cpu, word_value);
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static owned_cpu_status execute_move_long_memory_to_memory(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const uint64_t instruction_cycles =
        move_long_memory_to_memory_cycles(opcode);
    const uint16_t source_ea = (uint16_t)(opcode & UINT16_C(0x003f));
    const uint16_t destination_ea = (uint16_t)(
        (((opcode >> 6) & 7u) << 3) | ((opcode >> 9) & 7u));
    data_alterable_memory_ea source;
    data_alterable_memory_ea destination;
    owned_cpu_status status = preflight_event(
        cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
    if (status != OWNED_CPU_OK) return status;

    status = resolve_data_alterable_memory_ea(cpu, source_ea, cursor, 4u,
                                               &source);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if ((source.address & UINT32_C(1)) != 0u) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (source.has_base_update != 0u)
            write_address_register(cpu, source.base_register,
                                   source.updated_base);
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         source.address, 0, 1);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    if (source.has_base_update != 0u && source.update_after_access == 0u)
        write_address_register(cpu, source.base_register, source.updated_base);
    uint16_t value_high = 0u;
    uint16_t value_low = 0u;
    status = read_word(cpu, source.address, &value_high);
    if (status == OWNED_CPU_OK)
        status = read_word(cpu, source.address + UINT32_C(2), &value_low);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (source.has_base_update != 0u && source.update_after_access != 0u)
        write_address_register(cpu, source.base_register, source.updated_base);

    /* Resolve the destination only after the source has been acquired and
     * its postincrement committed. This keeps same-An transfers source-first. */
    status = resolve_data_alterable_memory_ea(cpu, destination_ea, cursor,
                                               4u, &destination);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if ((destination.address & UINT32_C(1)) != 0u) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (destination.has_base_update != 0u)
            write_address_register(cpu, destination.base_register,
                                   destination.updated_base);
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         destination.address, 0, 0);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }
    if (destination.has_base_update != 0u &&
        destination.update_after_access == 0u)
        write_address_register(cpu, destination.base_register,
                               destination.updated_base);
    status = write_word(cpu, destination.address, value_high);
    if (status == OWNED_CPU_OK)
        status = write_word(cpu, destination.address + UINT32_C(2), value_low);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (destination.has_base_update != 0u &&
        destination.update_after_access != 0u)
        write_address_register(cpu, destination.base_register,
                               destination.updated_base);
    set_move_flags(cpu, ((uint32_t)value_high << 16) | value_low);
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static uint64_t move_byte_memory_source_to_data_register_cycles(
    uint16_t opcode) {
    /* MOVE.B <data-alterable memory>,Dn. The destination mode is Dn direct;
     * source modes are the seven data-alterable memory EAs only. */
    if ((opcode & UINT16_C(0xf1c0)) != UINT16_C(0x1000)) return 0u;
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    switch (mode) {
        case 2u:
        case 3u:
            return UINT64_C(8);
        case 4u:
            return UINT64_C(10);
        case 5u:
            return UINT64_C(12);
        case 6u:
            return UINT64_C(14);
        case 7u:
            if (reg == 0u) return UINT64_C(12);
            if (reg == 1u) return UINT64_C(16);
            return 0u;
        default:
            return 0u;
    }
}

static owned_cpu_status execute_move_byte_memory_source_to_data_register(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint64_t *cycles) {
    const uint64_t instruction_cycles =
        move_byte_memory_source_to_data_register_cycles(opcode);
    data_alterable_memory_ea source;
    owned_cpu_status status = resolve_data_alterable_memory_ea(
        cpu, opcode, cursor, 1u, &source);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    /* The formerly separate displacement, indexed, and absolute source paths
     * fetched/validated their EA extensions before counter preflight. Keep
     * that extension-fault precedence while still blocking base updates,
     * operand access, and architectural state changes on counter overflow. */
    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
    if (status != OWNED_CPU_OK) return status;

    /* Preserve the shared EA update boundary: predecrement is visible before
     * operand access; postincrement follows a successful byte read. Byte EAs
     * permit odd effective addresses, so no vector-3 path applies here. */
    if (source.has_base_update != 0u && source.update_after_access == 0u)
        write_address_register(cpu, source.base_register, source.updated_base);
    uint8_t value = 0u;
    status = read_byte(cpu, source.address, &value);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (source.has_base_update != 0u && source.update_after_access != 0u)
        write_address_register(cpu, source.base_register, source.updated_base);

    const unsigned destination_register = (unsigned)((opcode >> 9) & 7u);
    cpu->data_registers[destination_register] =
        (cpu->data_registers[destination_register] & UINT32_C(0xffffff00)) |
        (uint32_t)value;
    set_move_byte_flags(cpu, value);
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static uint64_t move_word_memory_source_to_data_register_cycles(
    uint16_t opcode) {
    /* MOVE.W <readable memory>,Dn. Table 8-2 gives the complete instruction
     * totals; source EAs include the seven data-alterable forms plus the two
     * legal PC-relative forms. Dn/An-direct and immediate sources stay on
     * their separate handlers. */
    if ((opcode & UINT16_C(0xf1c0)) != UINT16_C(0x3000)) return 0u;
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    switch (mode) {
        case 2u: return UINT64_C(8);  /* (An) */
        case 3u: return UINT64_C(8);  /* (An)+ */
        case 4u: return UINT64_C(10); /* -(An) */
        case 5u: return UINT64_C(12); /* d16(An) */
        case 6u: return UINT64_C(14); /* brief d8(An,Xn) */
        case 7u:
            if (reg == 0u || reg == 2u) return UINT64_C(12);
            if (reg == 1u) return UINT64_C(16);
            if (reg == 3u) return UINT64_C(14);
            return 0u;
        default: return 0u;
    }
}

static owned_cpu_status execute_move_word_memory_source_to_data_register(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const uint64_t instruction_cycles =
        move_word_memory_source_to_data_register_cycles(opcode);
    if (instruction_cycles == 0u) return OWNED_CPU_UNSUPPORTED_OPCODE;

    data_alterable_memory_ea source;
    owned_cpu_status status = resolve_memory_to_register_source_ea(
        cpu, opcode, cursor, 2u, &source);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }

    if ((source.address & UINT32_C(1)) != 0u) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        /* The pinned MOVE.W PI/PD handlers use EA_AY_PI_16 / EA_AY_PD_16,
         * which update An before the attempted word read detects odd address.
         * Keep that vector-3 partial update as emulator-differential evidence;
         * normal host callback failures have separate owned-core boundaries. */
        if (source.has_base_update != 0u)
            write_address_register(cpu, source.base_register,
                                   source.updated_base);
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         source.address, 0, 1);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    /* Extensions are resolved before the fixed instruction-counter preflight.
     * No base update or operand read is committed when that preflight fails. */
    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
    if (status != OWNED_CPU_OK) return status;
    if (source.has_base_update != 0u && source.update_after_access == 0u)
        write_address_register(cpu, source.base_register,
                               source.updated_base);

    uint16_t value = 0u;
    status = read_word(cpu, source.address, &value);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (source.has_base_update != 0u && source.update_after_access != 0u)
        write_address_register(cpu, source.base_register,
                               source.updated_base);

    const unsigned destination_register = (unsigned)((opcode >> 9) & 7u);
    cpu->data_registers[destination_register] =
        (cpu->data_registers[destination_register] & UINT32_C(0xffff0000)) |
        (uint32_t)value;
    set_move_word_flags(cpu, value);
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static uint64_t move_long_memory_source_to_data_register_cycles(
    uint16_t opcode) {
    /* MOVE.L readable memory source to Dn. Table 8-3 gives full instruction
     * totals; adding generic EA costs here would double-count predecrement. */
    if ((opcode & UINT16_C(0xf1c0)) != UINT16_C(0x2000)) return 0u;
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    switch (mode) {
        case 2u:
        case 3u: return UINT64_C(12);
        case 4u: return UINT64_C(14);
        case 5u: return UINT64_C(16);
        case 6u: return UINT64_C(18);
        case 7u:
            if (reg == 0u || reg == 2u) return UINT64_C(16);
            if (reg == 1u) return UINT64_C(20);
            if (reg == 3u) return UINT64_C(18);
            return 0u;
        default: return 0u;
    }
}

static owned_cpu_status execute_move_long_memory_source_to_data_register(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const uint64_t instruction_cycles =
        move_long_memory_source_to_data_register_cycles(opcode);
    data_alterable_memory_ea source;
    owned_cpu_status status = resolve_memory_to_register_source_ea(
        cpu, opcode, cursor, 4u, &source);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }

    if ((source.address & UINT32_C(1)) != 0u) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        /* Pinned MAME's EA_AY_PI_32 / EA_AY_PD_32 updates An before its
         * attempted long read detects an odd address. The PRM specifies the
         * address exception but not this partial-update chronology. */
        if (source.has_base_update != 0u)
            write_address_register(cpu, source.base_register,
                                   source.updated_base);
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         source.address, 0, 1);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    /* Resolve extensions before exact counter preflight, matching the prior
     * individually admitted MOVE.L source forms. Do not commit PI/PD or read
     * operand data until that preflight succeeds. */
    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                             1u, 0u);
    if (status != OWNED_CPU_OK) return status;
    if (source.has_base_update != 0u && source.update_after_access == 0u)
        write_address_register(cpu, source.base_register,
                               source.updated_base);

    uint16_t high = 0u;
    uint16_t low = 0u;
    status = read_word(cpu, source.address, &high);
    if (status == OWNED_CPU_OK)
        status = read_word(cpu, source.address + UINT32_C(2), &low);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }

    if (source.has_base_update != 0u && source.update_after_access != 0u)
        write_address_register(cpu, source.base_register,
                               source.updated_base);
    const uint32_t value = ((uint32_t)high << 16) | (uint32_t)low;
    const unsigned destination_register = (unsigned)((opcode >> 9) & 7u);
    cpu->data_registers[destination_register] = value;
    set_move_flags(cpu, value);
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static uint64_t move_long_address_register_to_memory_cycles(
    uint16_t destination_ea) {
    const unsigned mode = (unsigned)((destination_ea >> 3) & 7u);
    const unsigned reg = (unsigned)(destination_ea & 7u);
    /* UM Rev. 9.1 Table 8-3 p. 8-3 lists full MOVE.L totals. In particular,
     * destination -(An) costs 12 clocks; do not add Table 8-1's generic EA
     * predecrement surcharge to that instruction-specific total. */
    switch (mode) {
        case 2u:
        case 3u:
        case 4u:
            return UINT64_C(12);
        case 5u:
            return UINT64_C(16);
        case 6u:
            return UINT64_C(18);
        case 7u:
            if (reg == 0u) return UINT64_C(16);
            if (reg == 1u) return UINT64_C(20);
            return 0u;
        default:
            return 0u;
    }
}

static owned_cpu_status execute_move_long_address_register_to_memory(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const unsigned source_register = (unsigned)(opcode & UINT16_C(0x0007));
    const uint16_t destination_ea = (uint16_t)(
        (((opcode >> 6) & UINT16_C(0x0007)) << 3) |
        ((opcode >> 9) & UINT16_C(0x0007)));
    /* The generated MOVE handlers sample An before resolving the destination
     * EA. This is observable when the source aliases a postincrement or
     * predecrement destination base. */
    const uint32_t value = cpu->address_registers[source_register];
    data_alterable_memory_ea destination;
    owned_cpu_status status = resolve_data_alterable_memory_ea(
        cpu, destination_ea, cursor, 4u, &destination);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    const uint64_t instruction_cycles =
        move_long_address_register_to_memory_cycles(destination_ea);
    if (instruction_cycles == 0u) return OWNED_CPU_UNSUPPORTED_OPCODE;

    if ((destination.address & UINT32_C(1)) != 0u) {
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        /* Pinned MAME's EA_AX_PI_32 and EA_AX_PD_32 update the base while
         * calculating the destination, before its aligned long write. Keep
         * this partial state on vector 3 as differential behavior only; the
         * manuals do not specify instruction-specific fault chronology. */
        if (destination.has_base_update != 0u)
            write_address_register(cpu, destination.base_register,
                                   destination.updated_base);
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         destination.address, 0, 0);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
    if (status != OWNED_CPU_OK) return status;
    /* Predecrement is committed before transfer. Postincrement is deferred
     * until both word callbacks succeed, the owned-core host-fault contract. */
    if (destination.has_base_update != 0u &&
        destination.update_after_access == 0u)
        write_address_register(cpu, destination.base_register,
                               destination.updated_base);

    if (((destination_ea >> 3) & 7u) == 4u) {
        /* PRM/UM define the final big-endian longword but not subcycle order.
         * Match the exact pinned MAME generated MOVE.L predecrement handlers:
         * low word at EA+2, then high word at EA. */
        status = write_word(cpu, destination.address + UINT32_C(2),
                            (uint16_t)value);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination.address,
                                (uint16_t)(value >> 16));
    } else {
        status = write_word(cpu, destination.address,
                            (uint16_t)(value >> 16));
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination.address + UINT32_C(2),
                                (uint16_t)value);
    }
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    if (destination.has_base_update != 0u &&
        destination.update_after_access != 0u)
        write_address_register(cpu, destination.base_register,
                               destination.updated_base);
    set_move_flags(cpu, value);
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

/* Logical shift left for immediate-count, data-register forms. Width is in
 * bytes (1, 2 or 4); the decoder preflights timing before this commits the
 * result and condition codes. */
static void logical_shift_left_data_register(owned_cpu *cpu, unsigned reg,
                                             unsigned width, unsigned count) {
    const unsigned bits = width * 8u;
    const uint32_t mask = width == 4u
        ? UINT32_MAX : (UINT32_C(1) << bits) - UINT32_C(1);
    const uint32_t before = cpu->data_registers[reg];
    const uint32_t operand = before & mask;
    const uint32_t result = (operand << count) & mask;
    const unsigned last_out = (unsigned)((operand >> (bits - count)) & 1u);
    uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (last_out != 0u) flags = (uint16_t)(flags | SR_C | SR_X);
    if ((result & (UINT32_C(1) << (bits - 1u))) != 0u)
        flags = (uint16_t)(flags | SR_N);
    if (result == 0u) flags = (uint16_t)(flags | SR_Z);
    cpu->data_registers[reg] = (before & ~mask) | result;
    cpu->sr = flags;
}

/* Logical shift right for immediate-count, data-register forms. Width is in
 * bytes (1, 2 or 4); the decoder preflights timing before committing state. */
static void logical_shift_right_data_register(owned_cpu *cpu, unsigned reg,
                                              unsigned width, unsigned count) {
    const unsigned bits = width * 8u;
    const uint32_t mask = width == 4u
        ? UINT32_MAX : (UINT32_C(1) << bits) - UINT32_C(1);
    const uint32_t before = cpu->data_registers[reg];
    const uint32_t operand = before & mask;
    const uint32_t result = operand >> count;
    const unsigned last_out = (unsigned)((operand >> (count - 1u)) & 1u);
    uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (last_out != 0u) flags = (uint16_t)(flags | SR_C | SR_X);
    if (result == 0u) flags = (uint16_t)(flags | SR_Z);
    cpu->data_registers[reg] = (before & ~mask) | result;
    cpu->sr = flags;
}

/* Arithmetic shift right for immediate or register counts. The bounded
 * unsigned loop supplies sign fill explicitly, so no implementation-defined
 * signed right shift is involved. The decoder preflights the selected timing
 * before this helper commits the destination and condition codes. */
static void arithmetic_shift_right_data_register(owned_cpu *cpu, unsigned reg,
                                                 unsigned width,
                                                 unsigned count) {
    const unsigned bits = width * 8u;
    const uint32_t mask = width == 4u
        ? UINT32_MAX : (UINT32_C(1) << bits) - UINT32_C(1);
    const uint32_t sign_bit = UINT32_C(1) << (bits - 1u);
    const uint32_t before = cpu->data_registers[reg];
    uint32_t result = before & mask;
    unsigned last_out = 0u;
    for (unsigned step = 0u; step < count; ++step) {
        const uint32_t sign_fill = result & sign_bit;
        last_out = result & UINT32_C(1);
        result >>= 1;
        if (sign_fill != 0u) result |= sign_bit;
    }
    result &= mask;

    uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (count == 0u) flags = (uint16_t)(flags | (cpu->sr & SR_X));
    else if (last_out != 0u) flags = (uint16_t)(flags | SR_C | SR_X);
    if ((result & sign_bit) != 0u) flags = (uint16_t)(flags | SR_N);
    if (result == 0u) flags = (uint16_t)(flags | SR_Z);
    cpu->data_registers[reg] = (before & ~mask) | result;
    cpu->sr = flags;
}

/* Rotate a data register without extend at byte, word or long width. The
 * decoder preflights the instruction timing before committing either result
 * or condition codes. */
static void rotate_data_register(owned_cpu *cpu, unsigned reg,
                                 unsigned width, unsigned count,
                                 int rotate_left) {
    const unsigned bits = width * 8u;
    const uint32_t mask = width == 4u
        ? UINT32_MAX : (UINT32_C(1) << bits) - UINT32_C(1);
    const uint32_t before = cpu->data_registers[reg];
    const uint32_t operand = before & mask;
    const uint32_t result = rotate_left != 0
        ? ((operand << count) | (operand >> (bits - count))) & mask
        : ((operand >> count) | (operand << (bits - count))) & mask;
    const unsigned last_out = rotate_left != 0
        ? (unsigned)((operand >> (bits - count)) & UINT32_C(1))
        : (unsigned)((operand >> (count - 1u)) & UINT32_C(1));
    uint16_t flags = (uint16_t)(cpu->sr &
        (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
    if ((result & (UINT32_C(1) << (bits - 1u))) != 0u)
        flags = (uint16_t)(flags | SR_N);
    if (result == 0u) flags = (uint16_t)(flags | SR_Z);
    if (last_out != 0u) flags = (uint16_t)(flags | SR_C);
    cpu->data_registers[reg] = (before & ~mask) | result;
    cpu->sr = flags;
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

static void subtract_quick_long(owned_cpu *cpu, unsigned reg, unsigned quick) {
    const uint32_t before = cpu->data_registers[reg];
    const uint32_t after = before - (uint32_t)quick;
    uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (after == 0u) flags = (uint16_t)(flags | SR_Z);
    if ((after & UINT32_C(0x80000000)) != 0u) flags = (uint16_t)(flags | SR_N);
    if ((((before ^ (uint32_t)quick) & (before ^ after)) &
         UINT32_C(0x80000000)) != 0u) flags = (uint16_t)(flags | SR_V);
    if (before < (uint32_t)quick) flags = (uint16_t)(flags | SR_C | SR_X);
    cpu->data_registers[reg] = after;
    cpu->sr = flags;
}

static void add_quick_word(owned_cpu *cpu, unsigned reg, unsigned quick) {
    const uint16_t before = (uint16_t)cpu->data_registers[reg];
    const uint32_t full_sum = (uint32_t)before + (uint32_t)quick;
    const uint16_t after = (uint16_t)full_sum;
    uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (after == 0u) flags = (uint16_t)(flags | SR_Z);
    if ((after & UINT16_C(0x8000)) != 0u) flags = (uint16_t)(flags | SR_N);
    if (((uint16_t)(~(before ^ (uint16_t)quick) & (before ^ after)) &
         UINT16_C(0x8000)) != 0u) flags = (uint16_t)(flags | SR_V);
    if (full_sum > UINT16_MAX) flags = (uint16_t)(flags | SR_C | SR_X);
    cpu->data_registers[reg] =
        (cpu->data_registers[reg] & UINT32_C(0xffff0000)) | after;
    cpu->sr = flags;
}

static void add_quick_byte(owned_cpu *cpu, unsigned reg, unsigned quick) {
    const uint8_t before = (uint8_t)cpu->data_registers[reg];
    const uint16_t full_sum = (uint16_t)before + (uint16_t)quick;
    const uint8_t after = (uint8_t)full_sum;
    uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (after == 0u) flags = (uint16_t)(flags | SR_Z);
    if ((after & UINT8_C(0x80)) != 0u) flags = (uint16_t)(flags | SR_N);
    if (((uint8_t)(~(before ^ (uint8_t)quick) & (before ^ after)) & UINT8_C(0x80)) != 0u)
        flags = (uint16_t)(flags | SR_V);
    if (full_sum > UINT8_MAX) flags = (uint16_t)(flags | SR_C | SR_X);
    cpu->data_registers[reg] = (cpu->data_registers[reg] & UINT32_C(0xffffff00)) | after;
    cpu->sr = flags;
}

static void add_data_register_direct(owned_cpu *cpu, unsigned source_reg,
                                     unsigned destination_reg, unsigned width) {
    const uint32_t mask = width == 1u ? UINT32_C(0x000000ff) :
                          width == 2u ? UINT32_C(0x0000ffff) : UINT32_MAX;
    const uint32_t sign_bit = width == 1u ? UINT32_C(0x00000080) :
                              width == 2u ? UINT32_C(0x00008000) :
                                            UINT32_C(0x80000000);
    const uint32_t source = cpu->data_registers[source_reg] & mask;
    const uint32_t destination = cpu->data_registers[destination_reg] & mask;
    const uint64_t full_sum = (uint64_t)source + (uint64_t)destination;
    const uint32_t result = (uint32_t)(full_sum & mask);
    uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
    if (result == 0u) flags = (uint16_t)(flags | SR_Z);
    if ((result & sign_bit) != 0u) flags = (uint16_t)(flags | SR_N);
    if (((~(source ^ destination) & (destination ^ result)) & sign_bit) != 0u) {
        flags = (uint16_t)(flags | SR_V);
    }
    if (full_sum > mask) flags = (uint16_t)(flags | SR_C | SR_X);
    cpu->data_registers[destination_reg] =
        (cpu->data_registers[destination_reg] & ~mask) | result;
    cpu->sr = flags;
}

static uint64_t pea_control_ea_cycles(uint16_t opcode) {
    if ((opcode & UINT16_C(0xffc0)) != UINT16_C(0x4840)) return 0u;
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    switch (mode) {
        case 2u: return UINT64_C(12);
        case 5u: return UINT64_C(16);
        case 6u: return UINT64_C(20);
        case 7u:
            if (reg == 0u || reg == 2u) return UINT64_C(16);
            if (reg == 1u || reg == 3u) return UINT64_C(20);
            return 0u;
        default: return 0u;
    }
}

static owned_cpu_status resolve_control_ea(
    owned_cpu *cpu, uint16_t opcode, uint32_t *cursor,
    uint32_t *effective_address) {
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    if (mode == 2u || mode == 5u || mode == 6u ||
        (mode == 7u && reg < 2u)) {
        data_alterable_memory_ea ea;
        owned_cpu_status status = resolve_data_alterable_memory_ea(
            cpu, (uint16_t)(opcode & UINT16_C(0x003f)), cursor, 4u, &ea);
        if (status == OWNED_CPU_OK) *effective_address = ea.address;
        return status;
    }
    if (mode != 7u || (reg != 2u && reg != 3u))
        return OWNED_CPU_UNSUPPORTED_OPCODE;

    const uint32_t extension_address = *cursor;
    uint16_t extension = 0u;
    owned_cpu_status status = fetch_word(cpu, cursor, &extension);
    if (status != OWNED_CPU_OK) return status;
    if (reg == 2u) {
        *effective_address = extension_address + sign_extend_word(extension);
        return OWNED_CPU_OK;
    }

    /* Control-EA PC-index admits only the MC68000 brief extension.
     * Full-format extensions stay outside this CPU subset. */
    if ((extension & UINT16_C(0x0700)) != 0u)
        return OWNED_CPU_UNSUPPORTED_OPCODE;
    const unsigned index_register = (unsigned)((extension >> 12) & 7u);
    const uint32_t full_index = (extension & UINT16_C(0x8000)) != 0u
        ? cpu->address_registers[index_register]
        : cpu->data_registers[index_register];
    const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
        ? full_index
        : sign_extend_word((uint16_t)full_index);
    *effective_address = extension_address + index +
                         sign_extend_byte((uint8_t)extension);
    return OWNED_CPU_OK;
}

static uint64_t jsr_control_ea_cycles(uint16_t opcode) {
    if ((opcode & UINT16_C(0xffc0)) != UINT16_C(0x4e80)) return 0u;
    const unsigned mode = (unsigned)((opcode >> 3) & 7u);
    const unsigned reg = (unsigned)(opcode & 7u);
    switch (mode) {
        case 2u: return UINT64_C(16);
        case 5u: return UINT64_C(18);
        case 6u: return UINT64_C(22);
        case 7u:
            if (reg == 0u || reg == 2u) return UINT64_C(18);
            if (reg == 1u) return UINT64_C(20);
            if (reg == 3u) return UINT64_C(22);
            return 0u;
        default: return 0u;
    }
}

static owned_cpu_status execute_pea_control_ea(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const uint64_t instruction_cycles = pea_control_ea_cycles(opcode);
    uint32_t effective_address = 0u;
    owned_cpu_status status = resolve_control_ea(
        cpu, opcode, cursor, &effective_address);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }

    const uint32_t stack_destination =
        cpu->address_registers[7] - UINT32_C(4);
    if ((stack_destination & UINT32_C(1)) != 0u) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         stack_destination, 0, 0);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    /* Table 8-10 gives complete PEA instruction totals. Extensions are
     * resolved first; no source operand is read and the stack is untouched
     * until exact timing and counter preflight succeeds. */
    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                             1u, 0u);
    if (status != OWNED_CPU_OK) return status;
    status = push_long(cpu, effective_address);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
}

static owned_cpu_status execute_jsr_control_ea(
    owned_cpu *cpu, uint32_t instruction_pc, uint16_t opcode,
    uint32_t *cursor, uint32_t *next_pc, uint64_t *cycles,
    step_kind *kind) {
    const uint64_t instruction_cycles = jsr_control_ea_cycles(opcode);
    uint32_t target = 0u;
    owned_cpu_status status = resolve_control_ea(
        cpu, opcode, cursor, &target);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }

    const uint32_t stack_destination =
        cpu->address_registers[7] - UINT32_C(4);
    if ((stack_destination & UINT32_C(1)) != 0u) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                 EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = enter_address_exception(cpu, instruction_pc, opcode,
                                         stack_destination, 0, 0);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }

    /* PRM §4 JSR pushes the continuation after the EA extensions. Resolve
     * extensions before exact-cycle counter preflight, then write the return
     * address and transfer control without fetching the target in this step. */
    status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                             1u, 0u);
    if (status != OWNED_CPU_OK) return status;
    status = push_long(cpu, *cursor);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = opcode;
        return status;
    }
    *cursor = target;
    *cycles = instruction_cycles;
    return OWNED_CPU_OK;
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
                                                    EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
        if (overflow != OWNED_CPU_OK) return overflow;
        owned_cpu_status address_status = enter_address_exception(
            cpu, instruction_pc, 0u, instruction_pc, 1, 1);
        if (address_status != OWNED_CPU_OK) return address_status;
        *next_pc = cpu->pc;
        *kind = STEP_ADDRESS_EXCEPTION;
        *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
        return OWNED_CPU_OK;
    }
    owned_cpu_status status = fetch_word(cpu, &cursor, opcode);
    if (status != OWNED_CPU_OK) {
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = 0u;
        return status;
    }
    cpu->instruction_register = *opcode;

    if (move_word_memory_source_to_data_register_cycles(*opcode) != 0u) {
        status = execute_move_word_memory_source_to_data_register(
            cpu, instruction_pc, *opcode, &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if (is_multiply_word_source_to_data_register(*opcode) != 0) {
        /* MC68000 MULS.W/MULU.W admit data-register, data-alterable memory,
         * PC-relative and immediate word sources (PRM §4 MULS pp. 4-135–4-136,
         * MULU pp. 4-138–4-139). Address-register direct is not a legal source.
         * The destination's low word is sampled before any result write so
         * source/destination Dn aliases use the original operands. */
        const unsigned source_mode = (unsigned)((*opcode >> 3) & 7u);
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const int signed_operation = (*opcode & UINT16_C(0x0100)) != 0u;
        uint16_t source = 0u;
        uint64_t source_ea_cycles = 0u;
        int memory_source = 0;
        data_alterable_memory_ea source_ea = {0};

        if (source_mode == 0u) {
            source = (uint16_t)cpu->data_registers[source_register];
        } else if (source_mode == 7u && source_register == 4u) {
            status = fetch_word(cpu, &cursor, &source);
            source_ea_cycles = UINT64_C(4);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
        } else {
            status = resolve_memory_to_register_source_ea(
                cpu, *opcode, &cursor, 2u, &source_ea);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            memory_source = 1;
            source_ea_cycles = source_ea.address_cycles;
            if ((source_ea.address & UINT32_C(1)) != 0u) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                         EXCEPTION_ADDRESS_ERROR_CYCLES,
                                         0u, 0u);
                if (status != OWNED_CPU_OK) return status;
                if (source_ea.has_base_update != 0u)
                    write_address_register(cpu, source_ea.base_register,
                                           source_ea.updated_base);
                status = enter_address_exception(cpu, instruction_pc, *opcode,
                                                 source_ea.address, 0, 1);
                if (status != OWNED_CPU_OK) return status;
                *next_pc = cpu->pc;
                *kind = STEP_ADDRESS_EXCEPTION;
                *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
                return OWNED_CPU_OK;
            }

            status = read_word(cpu, source_ea.address, &source);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
        }

        const uint16_t destination =
            (uint16_t)cpu->data_registers[destination_register];
        uint32_t product = 0u;
        unsigned iterations = 0u;
        if (signed_operation != 0) {
            /* Both signed 16-bit operands convert into int32_t by explicit
             * subtraction, avoiding implementation-defined uint16_t-to-int16_t
             * conversion. Their product always fits signed 32-bit. */
            const int32_t signed_source = (source & UINT16_C(0x8000)) != 0u
                ? (int32_t)source - INT32_C(0x10000) : (int32_t)source;
            const int32_t signed_destination =
                (destination & UINT16_C(0x8000)) != 0u
                    ? (int32_t)destination - INT32_C(0x10000)
                    : (int32_t)destination;
            product = (uint32_t)(signed_source * signed_destination);
            iterations = muls_word_transition_count(source);
        } else {
            product = (uint32_t)source * (uint32_t)destination;
            iterations = count_set_bits_word(source);
        }

        /* UM Rev. 9.1 MC68000 Chapter 8 Table 8-4 p. 8-4 specifies 38+2n
         * multiply clocks: MULU n is source popcount; MULS n counts adjacent
         * transitions in the source with a zero LSB. Table 8-1 p. 8-2 adds
         * the selected word source EA clocks. Acquire the dynamic source
         * before exact counter preflight; no result/flags or successful EA
         * update commits unless the complete timing fits the counters. */
        const uint64_t instruction_cycles = UINT64_C(38) +
            UINT64_C(2) * (uint64_t)iterations + source_ea_cycles;
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (memory_source != 0 && source_ea.has_base_update != 0u)
            write_address_register(cpu, source_ea.base_register,
                                   source_ea.updated_base);

        cpu->data_registers[destination_register] = product;
        /* PRM specifies X unchanged and C clear for both word multiply forms;
         * N/Z follow the full 32-bit result and V is clear for word products. */
        cpu->sr = (uint16_t)(cpu->sr & (uint16_t)~SR_MOVE_FLAGS);
        if (product == 0u) cpu->sr = (uint16_t)(cpu->sr | SR_Z);
        if ((product & UINT32_C(0x80000000)) != 0u)
            cpu->sr = (uint16_t)(cpu->sr | SR_N);
        *cycles = instruction_cycles;
    } else if (is_divs_word_source_to_data_register(*opcode) != 0) {
        /* The diagnosed slice accepts Dn and immediate word sources. PRM §4
         * DIVS pp. 4-92–4-95 defines signed 32/16 division, packed signed
         * remainder/quotient, flags and overflow behavior. */
        const unsigned source_mode = (unsigned)((*opcode >> 3) & 7u);
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        uint16_t source_word = 0u;
        uint64_t source_ea_cycles = 0u;
        if (source_mode == 0u) {
            source_word = (uint16_t)cpu->data_registers[source_register];
        } else {
            /* Immediate DIVS.W consumes one extension word and adds the
             * four-clock immediate EA cost from UM Table 8-1. */
            status = fetch_word(cpu, &cursor, &source_word);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            source_ea_cycles = UINT64_C(4);
        }
        const int64_t dividend = sign_extend_long_signed(
            cpu->data_registers[destination_register]);
        const int32_t divisor = sign_extend_word_signed(
            source_word);

        if (divisor == 0) {
            /* UM Rev. 9.1 Table 8-14 p. 8-11 specifies 38 clocks for the
             * divide-by-zero exception, plus source EA time. The frame saves
             * PC after acquired extensions; undefined flags stay deterministic. */
            const uint64_t exception_cycles =
                UINT64_C(38) + source_ea_cycles;
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION,
                                     exception_cycles, 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            cpu->sr = (uint16_t)(cpu->sr & (uint16_t)~SR_C);
            status = enter_short_exception(cpu, 5u, cpu->sr, cursor, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = exception_cycles;
            return OWNED_CPU_OK;
        }

        const uint64_t instruction_cycles =
            divs_word_register_cycles(dividend, divisor) + source_ea_cycles;
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;

        const int64_t quotient = dividend / (int64_t)divisor;
        const int64_t remainder = dividend % (int64_t)divisor;
        if (quotient < -INT64_C(32768) || quotient > INT64_C(32767)) {
            /* The PRM leaves N/Z undefined on overflow; preserve them as the
             * core's deterministic choice, set V, clear C, and keep X. */
            cpu->sr = (uint16_t)((cpu->sr &
                (uint16_t)~(SR_V | SR_C)) | SR_V);
        } else {
            const uint32_t result =
                ((uint32_t)(uint16_t)remainder << 16) |
                (uint32_t)(uint16_t)quotient;
            cpu->data_registers[destination_register] = result;
            cpu->sr = (uint16_t)(cpu->sr &
                (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
            if (quotient < 0)
                cpu->sr = (uint16_t)(cpu->sr | SR_N);
            if (quotient == 0)
                cpu->sr = (uint16_t)(cpu->sr | SR_Z);
        }
        *cycles = instruction_cycles;
    } else if (is_divu_word_source_to_data_register(*opcode) != 0) {
        /* DIVU.W admits readable data EAs: Dn, the seven data-alterable
         * memory modes, PC-relative displacement/index, and immediate.
         * PRM §4 DIVU pp. 4-96–4-97 defines the unsigned 32/16 result, X
         * preservation, and quotient-overflow result/flag behavior. */
        const unsigned source_mode = (unsigned)((*opcode >> 3) & 7u);
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        uint16_t divisor = 0u;
        uint64_t source_ea_cycles = 0u;
        int memory_source = 0;
        data_alterable_memory_ea source_ea = {0};

        if (source_mode == 0u) {
            /* Sample the low word before reading/writing the destination so
             * DIVU.W Dn,Dn uses the original value for both operands. */
            divisor = (uint16_t)cpu->data_registers[source_register];
        } else if (source_mode == 7u && source_register == 4u) {
            /* Immediate is a fetched data word with a four-clock EA cost. */
            status = fetch_word(cpu, &cursor, &divisor);
            source_ea_cycles = UINT64_C(4);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
        } else {
            /* The shared memory resolver covers data-alterable EAs and the
             * read-source resolver adds PC-relative forms. */
            status = resolve_memory_to_register_source_ea(
                cpu, *opcode, &cursor, 2u, &source_ea);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            memory_source = 1;
            source_ea_cycles = source_ea.address_cycles;
            if ((source_ea.address & UINT32_C(1)) != 0u) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                         EXCEPTION_ADDRESS_ERROR_CYCLES,
                                         0u, 0u);
                if (status != OWNED_CPU_OK) return status;
                if (source_ea.has_base_update != 0u)
                    write_address_register(cpu, source_ea.base_register,
                                           source_ea.updated_base);
                status = enter_address_exception(cpu, instruction_pc, *opcode,
                                                 source_ea.address, 0, 1);
                if (status != OWNED_CPU_OK) return status;
                *next_pc = cpu->pc;
                *kind = STEP_ADDRESS_EXCEPTION;
                *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
                return OWNED_CPU_OK;
            }

            status = read_word(cpu, source_ea.address, &divisor);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
        }

        const uint32_t dividend = cpu->data_registers[destination_register];
        if (divisor == 0u) {
            /* UM Table 8-14 p. 8-11 specifies 38 clocks plus the source EA
             * calculation for divide-by-zero. The frame saves the next PC
             * after all acquired EA extensions. N/Z/V are undefined for zero;
             * retain them deterministically while clearing defined C and
             * preserving X. */
            const uint64_t exception_cycles = UINT64_C(38) + source_ea_cycles;
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION,
                                     exception_cycles, 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (memory_source != 0 && source_ea.has_base_update != 0u)
                write_address_register(cpu, source_ea.base_register,
                                       source_ea.updated_base);
            cpu->sr = (uint16_t)(cpu->sr & (uint16_t)~SR_C);
            status = enter_short_exception(cpu, 5u, cpu->sr, cursor, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = exception_cycles;
            return OWNED_CPU_OK;
        }

        const int quotient_overflow = (dividend >> 16) >= (uint32_t)divisor;
        const uint64_t register_cycles = quotient_overflow != 0
            ? UINT64_C(10) : divu_word_register_cycles(dividend, divisor);
        const uint64_t instruction_cycles = register_cycles +
                                             source_ea_cycles;
        /* Memory data must be acquired before exact cycle-counter preflight
         * because its divisor determines restoring timing. All address-
         * register updates and result/flag writes wait until preflight passes;
         * the vector-3 path follows the owned-core address-error update
         * contract before exception entry (manuals do not define that partial
         * state), while host read faults leave the source register unchanged. */
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (memory_source != 0 && source_ea.has_base_update != 0u)
            write_address_register(cpu, source_ea.base_register,
                                   source_ea.updated_base);

        if (quotient_overflow != 0) {
            /* The PRM describes N/Z as undefined on overflow (and contains a
             * signed-width phrase inconsistent with unsigned DIVU). The
             * result remains unchanged; keep N/Z stable as this core's
             * deterministic choice, set V, clear C, and preserve X. Timing
             * follows the separately sourced MC68000 overflow observation
             * plus this EA calculation; it is differential, not hardware
             * proof. */
            cpu->sr = (uint16_t)((cpu->sr &
                (uint16_t)~(SR_V | SR_C)) | SR_V);
        } else {
            const uint32_t quotient = dividend / (uint32_t)divisor;
            const uint32_t remainder = dividend % (uint32_t)divisor;
            const uint32_t result = (remainder << 16) | quotient;
            cpu->data_registers[destination_register] = result;
            cpu->sr = (uint16_t)(cpu->sr &
                (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
            if ((quotient & UINT32_C(0x8000)) != 0u)
                cpu->sr = (uint16_t)(cpu->sr | SR_N);
            if (quotient == 0u) cpu->sr = (uint16_t)(cpu->sr | SR_Z);
        }
        *cycles = instruction_cycles;
    } else if (move_byte_memory_source_to_data_register_cycles(*opcode) != 0u) {
        status = execute_move_byte_memory_source_to_data_register(
            cpu, instruction_pc, *opcode, &cursor, cycles);
        if (status != OWNED_CPU_OK) return status;
    } else if (is_move_long_address_register_to_memory(*opcode) != 0) {
        status = execute_move_long_address_register_to_memory(
            cpu, instruction_pc, *opcode, &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if (*opcode == UINT16_C(0x4e75)) {
        uint16_t return_high = 0u;
        uint16_t return_low = 0u;
        const uint32_t stack = cpu->address_registers[7];
        status = read_word(cpu, stack, &return_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, stack + UINT32_C(2), &return_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* M68000 PRM §4 RTS (p. 4-169): (SP)->PC and SP+4->SP.
         * User's Manual Table 8-12: 16 clocks, 4 reads, 0 writes. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, 7u, stack + UINT32_C(4));
        cursor = ((uint32_t)return_high << 16) | (uint32_t)return_low;
        *cycles = UINT64_C(16);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4ed0)) {
        /* JMP (An). MC68000 User's Manual Rev. 9.1, Table 8-10
         * (printed p. 8-8): 8(2/0). The target is selected without fetching
         * the instruction at that target. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cursor = cpu->address_registers[(unsigned)(*opcode & 7u)];
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4ee8)) {
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* JMP (d16,An): PRM §2.2.6 defines the signed displacement and §4
         * JMP pp. 4-108 to 4-109 admits this control EA and changes PC without
         * changing condition codes. UM Rev. 9.1 Table 8-10 (printed p. 8-8)
         * gives 10(2/0); the no-prefetch core reads opcode and displacement,
         * leaving the target fetch to the next CPU step. An odd target thus
         * raises its address error on that later instruction fetch. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(10), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned base_register = (unsigned)(*opcode & 7u);
        cursor = cpu->address_registers[base_register] +
            sign_extend_word(encoded_displacement);
        *cycles = UINT64_C(10);
    } else if (*opcode == UINT16_C(0x4efa)) {
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* JMP (d16,PC): the signed displacement is added to the address of
         * its extension word (PRM §§2.2.11 and 4 JMP, pp. 2-13 and 4-108).
         * The MC68000 User's Manual Rev. 9.1 Table 8-10 (printed p. 8-8)
         * specifies 10(2/0). The no-prefetch core reads the opcode and
         * extension word; the target instruction is not fetched here. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(10), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t displacement = (encoded_displacement & UINT16_C(0x8000)) != 0u
            ? (UINT32_C(0xffff0000) | (uint32_t)encoded_displacement)
            : (uint32_t)encoded_displacement;
        cursor = (instruction_pc + UINT32_C(2)) + displacement;
        *cycles = UINT64_C(10);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4ef0) ||
               *opcode == UINT16_C(0x4efb)) {
        const uint32_t extension_address = cursor;
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* JMP (d8,An,Xn)/(d8,PC,Xn) admits only the MC68000 brief index
         * extension. PRM §2.2.7/§2.2.12 defines a signed d8 plus a signed
         * word or full-long index; §4 JMP pp. 4-108 to 4-109 restricts the
         * destination to control EAs and preserves condition codes. The
         * MC68000 UM Rev. 9.1 Table 8-10 (printed p. 8-8) gives 14(3/0).
         * This no-prefetch core reads the opcode and extension only and does
         * not fetch the target; the third table read is not a callback. */
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const uint32_t full_index = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? full_index
            : sign_extend_word((uint16_t)full_index);
        const uint32_t base = *opcode == UINT16_C(0x4efb)
            ? extension_address
            : cpu->address_registers[(unsigned)(*opcode & 7u)];
        const uint32_t target = base + sign_extend_byte((uint8_t)extension) + index;
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(14), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cursor = target;
        *cycles = UINT64_C(14);
    } else if (*opcode == UINT16_C(0x4ef8)) {
        uint16_t encoded_address = 0u;
        status = fetch_word(cpu, &cursor, &encoded_address);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* JMP (xxx).W: the MC68000 absolute-short EA is sign-extended to the
         * full logical address. UM Rev. 9.1 Table 8-10 (printed p. 8-8) gives
         * 10(2/0); PRM §2.2.10 defines sign extension and §4 JMP p. 4-108
         * changes PC without changing condition codes. This no-prefetch core
         * reads the opcode and address extension only; it does not fetch the
         * jump target. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(10), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cursor = (encoded_address & UINT16_C(0x8000)) != 0u
            ? UINT32_C(0xffff0000) | (uint32_t)encoded_address
            : (uint32_t)encoded_address;
        *cycles = UINT64_C(10);
    } else if (*opcode == UINT16_C(0x4ef9)) {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* PRM §4 JMP p. 4-108 defines destination address -> PC. MC68000 UM
         * Rev. 9.1 Table 8-10 (printed p. 8-8) gives absolute-long JMP as
         * 12(3/0). This no-prefetch core reads the opcode and two address
         * extension words; target refill is not a callback. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cursor = ((uint32_t)high << 16) | (uint32_t)low;
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf0f8)) == UINT16_C(0x50c8)) {
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned reg = (unsigned)(*opcode & 7u);
        const unsigned condition = (unsigned)((*opcode >> 8) & 15u);
        const int condition_holds = condition_true(cpu->sr, condition);
        const uint16_t count = (uint16_t)cpu->data_registers[reg];
        const uint16_t decremented = (uint16_t)(count - UINT16_C(1));
        const int expired = condition_holds == 0 && decremented == UINT16_MAX;
        const uint64_t instruction_cycles = condition_holds != 0
            ? UINT64_C(12) : expired ? UINT64_C(14) : UINT64_C(10);
        /* Motorola M68000 Family PRM §4 DBcc, pp. 4-90–4-91: a true
         * condition leaves Dn untouched; otherwise Dn[15:0] decrements and
         * branches from opcode address+2 unless the result is -1. The upper
         * word and condition codes never change. User's Manual Rev. 9.1
         * Table 8-9, p. 8-7: cc true 12(2/0), cc false/count-not-expired
         * 10(2/0), and cc false/counter-expired 14(3/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (condition_holds == 0) {
            cpu->data_registers[reg] =
                (cpu->data_registers[reg] & UINT32_C(0xffff0000)) |
                (uint32_t)decremented;
        }
        if (condition_holds == 0 && !expired) {
            uint32_t displacement = (uint32_t)encoded_displacement;
            if ((displacement & UINT32_C(0x8000)) != 0u)
                displacement |= UINT32_C(0xffff0000);
            cursor = instruction_pc + UINT32_C(2) + displacement;
        }
        *cycles = instruction_cycles;
    } else if (*opcode == UINT16_C(0x6000)) {
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* BRA.W uses the word after the opcode and keeps all condition codes
         * unchanged (PRM section 4 BRA, pp. 4-55 to 4-56). The displacement
         * is relative to opcode+2. MC68000 UM Rev. 9.1 Table 8-9 (printed
         * p. 8-7) specifies 10(2/0); no target fetch is modeled. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(10), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t displacement = (encoded_displacement & UINT16_C(0x8000)) != 0u
            ? (UINT32_C(0xffff0000) | (uint32_t)encoded_displacement)
            : (uint32_t)encoded_displacement;
        cursor = (instruction_pc + UINT32_C(2)) + displacement;
        *cycles = UINT64_C(10);
    } else if ((*opcode & UINT16_C(0xff00)) == UINT16_C(0x6000) &&
               (*opcode & UINT16_C(0x00ff)) != 0u) {
        /* BRA byte (plan 05-20, guest-observed): PC + 2 + sign-extended 8-bit
         * displacement, condition codes unaffected (PRM section 4 BRA,
         * p. 4-55). Displacement byte 0 is the word form (BRA.W); condition
         * 1 is handled by the BSR branch below. User's Manual Rev. 9.1
         * Table 8-9 (p. 8-7): BRA byte 10(2/0), the second read being the
         * target refill. */
        const uint64_t instruction_cycles = UINT64_C(10);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint32_t displacement = (uint32_t)(*opcode & UINT16_C(0x00ff));
        if ((displacement & UINT32_C(0x80)) != 0u)
            displacement |= UINT32_C(0xffffff00);
        cursor = instruction_pc + UINT32_C(2) + displacement;
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xf000)) == UINT16_C(0x6000) &&
               ((*opcode >> 8) & 15u) >= 2u && (*opcode & UINT16_C(0x00ff)) != 0u) {
        const unsigned condition = (unsigned)((*opcode >> 8) & 15u);
        const int taken = condition_true(cpu->sr, condition);
        const uint64_t instruction_cycles = taken ? UINT64_C(10) : UINT64_C(8);
        /* Bcc byte: MC68000 User's Manual Rev. 9.1 Table 8-9 (p. 8-7):
         * 10(2/0) taken, 8(1/0) not taken. */
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (taken) {
            uint32_t displacement = (uint32_t)(*opcode & UINT16_C(0x00ff));
            if ((displacement & UINT32_C(0x80)) != 0u)
                displacement |= UINT32_C(0xffffff00);
            cursor = instruction_pc + UINT32_C(2) + displacement;
        }
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xf0ff)) == UINT16_C(0x6000) &&
               ((*opcode >> 8) & 15u) >= 2u) {
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* Bcc word: MC68000 User's Manual Rev. 9.1, Table 8-9 (printed
         * p. 8-7): 10(2/0) taken, 12(2/0) not taken. Displacement is
         * relative to the extension-word address. */
        const unsigned condition = (unsigned)((*opcode >> 8) & 15u);
        const int taken = condition_true(cpu->sr, condition);
        const uint64_t instruction_cycles = taken ? UINT64_C(10) : UINT64_C(12);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (taken) {
            uint32_t displacement = (uint32_t)encoded_displacement;
            if ((displacement & UINT32_C(0x8000)) != 0u)
                displacement |= UINT32_C(0xffff0000);
            cursor = instruction_pc + UINT32_C(2) + displacement;
        }
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xff00)) == UINT16_C(0x6100) &&
               (*opcode & UINT16_C(0x00ff)) != 0u) {
        /* BSR byte: PC+2 is both the displacement base and pushed return PC.
         * PRM §4 BSR, pp. 4-59–4-60. UM Rev. 9.1 Table 8-9 p. 8-7 gives
         * 18 clocks (2 reads, 2 writes). A word push to an odd active SP is
         * an address error before any stack transfer (UM §6.3.10). */
        const uint32_t destination = cpu->address_registers[7] - UINT32_C(4);
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(18), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = push_long(cpu, cursor);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t displacement = (uint32_t)(*opcode & UINT16_C(0x00ff));
        if ((displacement & UINT32_C(0x80)) != 0u)
            displacement |= UINT32_C(0xffffff00);
        cursor = instruction_pc + UINT32_C(2) + displacement;
        *cycles = UINT64_C(18);
    } else if (*opcode == UINT16_C(0x6100)) {
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t displacement = (uint32_t)encoded_displacement;
        if ((displacement & UINT32_C(0x8000)) != 0u)
            displacement |= UINT32_C(0xffff0000);
        const uint32_t destination = cpu->address_registers[7] - UINT32_C(4);
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        /* M68000 PRM §4 BSR: push return PC and branch relative to the
         * extension-word address. User's Manual Table 8-9, p. 8-7: word BSR
         * takes 18 clocks (2 reads, 2 writes). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(18), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = push_long(cpu, cursor);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        cursor = (instruction_pc + UINT32_C(2)) + displacement;
        *cycles = UINT64_C(18);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x213c)) {
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = fetch_word(cpu, &cursor, &value_high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint16_t destination_ea = (uint16_t)(
            (((*opcode >> 6) & UINT16_C(0x0007)) << 3) |
            ((*opcode >> 9) & UINT16_C(0x0007)));
        data_alterable_memory_ea destination;
        status = resolve_data_alterable_memory_ea(
            cpu, destination_ea, &cursor, 4u, &destination);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t value = ((uint32_t)value_high << 16) | value_low;
        /* MOVE.L #<data>,-(An): UM Rev. 9.1 Table 8-3 p. 8-3 gives 20(3/2).
         * PRM §4 MOVE pp. 4-116–4-118 defines the final longword and flags;
         * the manuals do not specify split-write chronology. Match this core's
         * existing predecrement long-store callback order (low word at EA+2,
         * then high word at EA), which is different-model differential
         * evidence only, not a silicon bus-order claim. */
        if ((destination.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (destination.has_base_update != 0u)
                write_address_register(cpu, destination.base_register,
                                       destination.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination.address, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (destination.has_base_update != 0u &&
            destination.update_after_access == 0u)
            write_address_register(cpu, destination.base_register,
                                   destination.updated_base);
        status = write_word(cpu, destination.address + UINT32_C(2),
                            (uint16_t)value);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination.address,
                                (uint16_t)(value >> 16));
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, value);
        *cycles = UINT64_C(20);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x20bc)) {
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = fetch_word(cpu, &cursor, &value_high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination = cpu->address_registers[address_register];
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        const uint32_t value = ((uint32_t)value_high << 16) | value_low;
        /* MOVE.L #<data>,(An) (plan 05-20, guest-observed). Other sizes and
         * destination modes stay unsupported. PRM section 4 MOVE, pp. 4-116 to
         * 4-118: high word then low word, N/Z from the long value, V/C
         * cleared, X unchanged, An not modified. User's Manual Rev. 9.1
         * Table 8-3 (printed p. 8-3): immediate to (An) 20(3/2). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination + UINT32_C(2), value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, value);
        *cycles = UINT64_C(20);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x20fc)) {
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = fetch_word(cpu, &cursor, &value_high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination = cpu->address_registers[address_register];
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        const uint32_t value = ((uint32_t)value_high << 16) | value_low;
        /* MOVE.L #<data>,(An)+: MC68000 User's Manual Rev. 9.1 Table 8-3
         * (printed p. 8-3): 20(3/2). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination + UINT32_C(2), value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, address_register, destination + UINT32_C(4));
        set_move_flags(cpu, value);
        *cycles = UINT64_C(20);
    } else if (*opcode == UINT16_C(0x23fc)) {
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        uint16_t address_high = 0u;
        uint16_t address_low = 0u;
        status = fetch_word(cpu, &cursor, &value_high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &value_low);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &address_high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &address_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t destination = ((uint32_t)address_high << 16) | address_low;
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        const uint32_t value = ((uint32_t)value_high << 16) | value_low;
        /* MOVE.L #<data>,(xxx).L: MC68000 User's Manual Rev. 9.1 Table 8-3
         * (printed p. 8-3): 28(5/2). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(28), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination + UINT32_C(2), value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, value);
        *cycles = UINT64_C(28);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x217c)) {
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &value_high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &value_low);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t displacement = (uint32_t)encoded_displacement;
        if ((displacement & UINT32_C(0x8000)) != 0u)
            displacement |= UINT32_C(0xffff0000);
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination = cpu->address_registers[address_register] + displacement;
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        const uint32_t value = ((uint32_t)value_high << 16) | (uint32_t)value_low;
        /* MOVE.L #<data>,(d16,An): MC68000 User's Manual Rev. 9.1 Table 8-3
         * (printed p. 8-3): 24(4/2). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(24), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination + UINT32_C(2), value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, value);
        *cycles = UINT64_C(24);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x203c)) {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t value = ((uint32_t)high << 16) | (uint32_t)low;
        /* MOVE.L #<data>,Dn sets N/Z/V/C and preserves X. Motorola/NXP
         * MC68000 User's Manual Rev. 9.1 Table 8-3 (printed p. 8-3):
         * 12(3/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cpu->data_registers[(*opcode >> 9) & 7u] = value;
        set_move_flags(cpu, value);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x307c)) {
        uint16_t immediate = 0u;
        status = fetch_word(cpu, &cursor, &immediate);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* MOVEA.W #<data>,An sign-extends the immediate into the full
         * address register and leaves CCR unchanged. PRM §4 MOVEA,
         * pp. 4-119–4-120; UM Rev. 9.1 Table 8-3 p. 8-3: 8(2/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, (unsigned)((*opcode >> 9) & 7u),
                               sign_extend_word(immediate));
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x207c)) {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t value = ((uint32_t)high << 16) | (uint32_t)low;
        /* MOVEA.L #<data>,An loads all 32 bits without changing flags.
         * Motorola PRM §4 MOVEA, pp. 4-119–4-120; UM Rev. 9.1 Table 8-3,
         * p. 8-3: immediate long takes 12(3/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, (unsigned)((*opcode >> 9) & 7u), value);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2040)) {
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        /* MOVEA.L Dn,An copies the full data register without changing flags.
         * Motorola M68000 Family PRM §4 MOVEA, pp. 4-119–4-120; User's Manual
         * Table 8-3, p. 8-3: Dn to An costs 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, destination_register,
                               cpu->data_registers[source_register]);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2048)) {
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t value = cpu->address_registers[source_register];
        /* Motorola M68000 User's Manual Table 8-3, p. 8-3: MOVE.L An,An
         * takes 4 clocks (1 read, 0 writes). The address-register destination
         * selects MOVEA semantics, so the full value moves without flag changes. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, destination_register, value);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2140)) {
        /* MOVE.L Dn,(d16,An): admit only data-register source mode 000 and
         * displacement destination mode 101 (guest demanded, plan 05-27). */
        uint16_t displacement = 0u;
        status = fetch_word(cpu, &cursor, &displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned base_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t value = cpu->data_registers[source_register];
        const uint32_t destination = cpu->address_registers[base_register] +
                                     sign_extend_word(displacement);
        if ((destination & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        /* MOVE sets N/Z from the longword, clears V/C, and preserves X:
         * Motorola M68000 Family PRM MOVE, pp. 4-116 to 4-118. User's Manual
         * Rev. 9.1 Table 8-3 (printed p. 8-3): Dn to (d16,An) is 16(2/2).
         * The source and extension are two word reads; the longword stores
         * high word first, then low word. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, (uint16_t)(value >> 16));
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination + UINT32_C(2), (uint16_t)value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, value);
        *cycles = UINT64_C(16);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2180)) {
        /* MOVE.L Dn,(d8,An,Xn) (guest demanded, plan 05-27). Admit only the
         * MC68000 brief index extension; bits 10-8 are reserved and remain
         * unsupported. PRM §2.2.7, p. 2-9: An + sign-extended d8 + the
         * word/long index. PRM MOVE, pp. 4-116 to 4-118: N/Z from the
         * longword, V/C cleared, X preserved. User's Manual Rev. 9.1
         * Table 8-3 (p. 8-3): Dn to indexed destination is 18(2/2). */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const unsigned base_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t destination = cpu->address_registers[base_register] +
                                     sign_extend_byte((uint8_t)extension) +
                                     index;
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        const uint32_t value = cpu->data_registers[source_register];
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(18), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, (uint16_t)(value >> 16));
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination + UINT32_C(2), (uint16_t)value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, value);
        *cycles = UINT64_C(18);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2198)) {
        /* MOVE.L (An)+,(d8,An,Xn) is the next guest-observed transfer. The
         * PRM §2.2.4 p. 2-6 defines the four-byte source postincrement and
         * §2.2.7/§2.4 the MC68000 brief-index destination. The manual does not
         * specify source/destination alias order; matching pinned MAME
         * 31e52312's x2198_move_l_pi_071234fc is differential evidence only.
         * Table 8-3 p. 8-3 gives 26(4/2): opcode, brief extension and two
         * source reads, then two destination writes. UM Figure 2-6 p. 2-7
         * documents generic longword word layout/access order; no instruction-
         * specific partial-store chronology is asserted. */
        uint16_t destination_extension = 0u;
        status = fetch_word(cpu, &cursor, &destination_extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((destination_extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned source_base_register = (unsigned)(*opcode & 7u);
        const unsigned destination_base_register =
            (unsigned)((*opcode >> 9) & 7u);
        const uint32_t source_address = cpu->address_registers[source_base_register];
        if ((source_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source_address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(26), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, source_address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source_address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, source_base_register,
                               source_address + UINT32_C(4));
        const unsigned index_register =
            (unsigned)((destination_extension >> 12) & 7u);
        const uint32_t index_full =
            (destination_extension & UINT16_C(0x8000)) != 0u
                ? cpu->address_registers[index_register]
                : cpu->data_registers[index_register];
        const uint32_t index =
            (destination_extension & UINT16_C(0x0800)) != 0u
                ? index_full
                : sign_extend_word((uint16_t)index_full);
        const uint32_t destination_address =
            cpu->address_registers[destination_base_register] +
            sign_extend_byte((uint8_t)destination_extension) + index;
        if ((destination_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination_address, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = write_word(cpu, destination_address, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination_address + UINT32_C(2), value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t value = ((uint32_t)value_high << 16) | value_low;
        set_move_flags(cpu, value);
        *cycles = UINT64_C(26);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x21b0)) {
        /* MOVE.L (d8,An,Xn),(d8,An,Xn) is one of the bounded guest-observed
         * memory-to-memory forms. Fetch source then destination brief
         * extensions; reject full-format/scaled extensions before data access.
         * PRM §2.2.7 defines signed d8 and word/long indexes. PRM MOVE,
         * pp. 4-116 to 4-118, defines flags and preserved registers. User's
         * Manual Rev. 9.1 Table 8-3 (printed p. 8-3) gives 32(5/2): opcode,
         * two extensions and two source words, followed by two destination
         * word writes. */
        uint16_t source_extension = 0u;
        uint16_t destination_extension = 0u;
        status = fetch_word(cpu, &cursor, &source_extension);
        if (status == OWNED_CPU_OK)
            status = fetch_word(cpu, &cursor, &destination_extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((source_extension & UINT16_C(0x0700)) != 0u ||
            (destination_extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned source_base_register = (unsigned)(*opcode & 7u);
        const unsigned destination_base_register =
            (unsigned)((*opcode >> 9) & 7u);
        const unsigned source_index_register =
            (unsigned)((source_extension >> 12) & 7u);
        const unsigned destination_index_register =
            (unsigned)((destination_extension >> 12) & 7u);
        const uint32_t source_index_full =
            (source_extension & UINT16_C(0x8000)) != 0u
                ? cpu->address_registers[source_index_register]
                : cpu->data_registers[source_index_register];
        const uint32_t destination_index_full =
            (destination_extension & UINT16_C(0x8000)) != 0u
                ? cpu->address_registers[destination_index_register]
                : cpu->data_registers[destination_index_register];
        const uint32_t source_index =
            (source_extension & UINT16_C(0x0800)) != 0u
                ? source_index_full
                : sign_extend_word((uint16_t)source_index_full);
        const uint32_t destination_index =
            (destination_extension & UINT16_C(0x0800)) != 0u
                ? destination_index_full
                : sign_extend_word((uint16_t)destination_index_full);
        const uint32_t source_address =
            cpu->address_registers[source_base_register] +
            sign_extend_byte((uint8_t)source_extension) + source_index;
        const uint32_t destination_address =
            cpu->address_registers[destination_base_register] +
            sign_extend_byte((uint8_t)destination_extension) +
            destination_index;
        if ((source_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source_address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(32), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, source_address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source_address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((destination_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination_address, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = write_word(cpu, destination_address, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination_address + UINT32_C(2), value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t value = ((uint32_t)value_high << 16) | value_low;
        set_move_flags(cpu, value);
        *cycles = UINT64_C(32);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x21a8)) {
        /* MOVE.L (d16,An),(d8,An,Xn): consume source displacement then the
         * destination's MC68000 brief index extension. Bits 10-8 are
         * reserved and remain unsupported. PRM §2.2.7 p. 2-9 defines the
         * signed displacement and index. PRM MOVE, pp. 4-116 to 4-118:
         * N/Z reflect the longword, V/C clear and X is preserved. User's
         * Manual Rev. 9.1 Table 8-3 (printed p. 8-3):
         * (d16,An) to (d8,An,Xn) is 30(5/2). */
        uint16_t source_displacement = 0u;
        uint16_t destination_extension = 0u;
        status = fetch_word(cpu, &cursor, &source_displacement);
        if (status == OWNED_CPU_OK)
            status = fetch_word(cpu, &cursor, &destination_extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((destination_extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned source_base_register = (unsigned)(*opcode & 7u);
        const unsigned destination_base_register =
            (unsigned)((*opcode >> 9) & 7u);
        const unsigned index_register =
            (unsigned)((destination_extension >> 12) & 7u);
        const uint32_t index_full =
            (destination_extension & UINT16_C(0x8000)) != 0u
                ? cpu->address_registers[index_register]
                : cpu->data_registers[index_register];
        const uint32_t index =
            (destination_extension & UINT16_C(0x0800)) != 0u
                ? index_full
                : sign_extend_word((uint16_t)index_full);
        const uint32_t source_address =
            cpu->address_registers[source_base_register] +
            sign_extend_word(source_displacement);
        const uint32_t destination_address =
            cpu->address_registers[destination_base_register] +
            sign_extend_byte((uint8_t)destination_extension) + index;
        if ((source_address & UINT32_C(1)) != 0u ||
            (destination_address & UINT32_C(1)) != 0u) {
            const uint32_t fault_address =
                (source_address & UINT32_C(1)) != 0u
                    ? source_address
                    : destination_address;
            const int read_access = (source_address & UINT32_C(1)) != 0u;
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             fault_address, 0, read_access);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(30), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, source_address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source_address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = write_word(cpu, destination_address, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination_address + UINT32_C(2),
                                value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t value = ((uint32_t)value_high << 16) | value_low;
        set_move_flags(cpu, value);
        *cycles = UINT64_C(30);
    } else if (move_byte_word_memory_to_data_alterable_memory_cycles(*opcode) != 0u) {
        status = execute_move_byte_word_memory_to_memory(
            cpu, instruction_pc, *opcode, &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2168)) {
        /* MOVE.L (d16,An),(d16,An): source and destination extension words
         * are fetched in that order. Other memory-to-memory EA combinations
         * remain unsupported. */
        uint16_t source_displacement = 0u;
        uint16_t destination_displacement = 0u;
        status = fetch_word(cpu, &cursor, &source_displacement);
        if (status == OWNED_CPU_OK)
            status = fetch_word(cpu, &cursor, &destination_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned source_base_register = (unsigned)(*opcode & 7u);
        const unsigned destination_base_register =
            (unsigned)((*opcode >> 9) & 7u);
        const uint32_t source_address =
            cpu->address_registers[source_base_register] +
            sign_extend_word(source_displacement);
        const uint32_t destination_address =
            cpu->address_registers[destination_base_register] +
            sign_extend_word(destination_displacement);
        if ((source_address & 1u) != 0u ||
            (destination_address & 1u) != 0u) {
            const uint32_t fault_address = (source_address & 1u) != 0u
                                               ? source_address
                                               : destination_address;
            const int read_access = (source_address & 1u) != 0u;
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             fault_address, 0, read_access);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        /* MOVE sets N/Z from the longword, clears V/C, and preserves X:
         * M68000 Family PRM §4 MOVE, pp. 4-116 to 4-118. User's Manual
         * Rev. 9.1 Table 8-3 (printed p. 8-3): (d16,An) to (d16,An) is
         * 28(5/2): opcode, two extensions and two operand reads, then two
         * ordered word writes. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(28), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, source_address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source_address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = write_word(cpu, destination_address, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination_address + UINT32_C(2),
                                value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t value = ((uint32_t)value_high << 16) | value_low;
        set_move_flags(cpu, value);
        *cycles = UINT64_C(28);
    } else if (clr_data_register_direct_width(*opcode) != 0u) {
        /* CLR.{B,W,L} Dn (selected guest demand). The low operand width is
         * zeroed while unaffected upper Dn bits remain intact. CLR sets Z,
         * clears N/V/C and preserves X. MC68000 PRM §4 CLR pp. 4-73 to 4-74;
         * UM Rev. 9.1 Chapter 8 Table 8-6 p. 8-6 gives register byte/word
         * 4(1/0), long 6(1/0). This direct-register form has no operand bus
         * access; overflow preflight follows the opcode fetch but precedes
         * register or flag mutation. */
        const unsigned width = clr_data_register_direct_width(*opcode);
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint64_t instruction_cycles = width == 4u
            ? UINT64_C(6) : UINT64_C(4);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t preserved_mask = width == 1u
            ? UINT32_C(0xffffff00)
            : width == 2u ? UINT32_C(0xffff0000) : UINT32_C(0);
        cpu->data_registers[destination_register] &= preserved_mask;
        cpu->sr = (uint16_t)((cpu->sr & (uint16_t)~SR_MOVE_FLAGS) | SR_Z);
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4210)) {
        /* CLR.B (An), observed on the ordinary selected-guest path in 06-02.
         * PRM §4 CLR pp. 4-73 to 4-74 requires the destination read before the
         * byte write, N/V/C clear, Z set and X preserved. UM Rev. 9.1 Table
         * 8-6 p. 8-6 gives byte-memory base 8(1/1); Table 8-1 p. 8-2 adds
         * 4(1/0) for (An), totaling 12 clocks. Byte addressing permits an odd
         * address, and this mode leaves its address register unchanged. */
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const uint32_t destination = cpu->address_registers[base_register];
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t discarded = 0u;
        status = read_byte(cpu, destination, &discarded);
        if (status == OWNED_CPU_OK) status = write_byte(cpu, destination, 0u);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, 0u);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4228)) {
        /* CLR.B (d16,An): size byte, mode 101 (guest demanded, plan 05-11).
         * Word size and every other mode stay unsupported. */
        uint16_t displacement = 0u;
        status = fetch_word(cpu, &cursor, &displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t destination = cpu->address_registers[*opcode & 7u] +
                                     sign_extend_word(displacement);
        /* Operation and condition codes: M68000 Family PRM section 4, CLR,
         * pp. 4-73 to 4-74 (N=0, Z=1, V=0, C=0, X unchanged). The same page
         * notes that the MC68000 reads the location before clearing it, so a
         * byte read precedes the byte write. Timing: User's Manual Rev. 9.1
         * Table 8-6 (printed p. 8-6) CLR byte memory 8(1/1) plus Table 8-1
         * (printed p. 8-2) (d16,An) byte 8(2/0) = 16 clocks. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t discarded = 0u;
        status = read_byte(cpu, destination, &discarded);
        if (status == OWNED_CPU_OK) status = write_byte(cpu, destination, 0u);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, 0u);
        *cycles = UINT64_C(16);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4230)) {
        /* CLR.B (d8,An,Xn) (guest demanded, plan 05-02). Admit only the
         * MC68000 brief extension form; bits 10-8 remain unsupported. PRM
         * §2.2.7 defines the signed displacement and word/long index; §4 CLR
         * pp. 4-73 to 4-74 requires the MC68000 pre-clear read and clears
         * N/V/C, sets Z, and preserves X. Byte EAs need not be aligned. UM
         * Rev. 9.1 Table 8-6 p. 8-6 gives CLR byte memory 8(1/1); Table 8-1
         * p. 8-2 indexed byte EA adds 10(2/0), totaling 18(3/1). */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t destination = cpu->address_registers[base_register] +
            sign_extend_byte((uint8_t)extension) + index;
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(18), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t discarded = 0u;
        status = read_byte(cpu, destination, &discarded);
        if (status == OWNED_CPU_OK) status = write_byte(cpu, destination, 0u);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, 0u);
        *cycles = UINT64_C(18);
    } else if ((*opcode & UINT16_C(0xffc0)) == UINT16_C(0x4240)) {
        /* CLR.W memory, data-alterable EA only. The MC68000 CLR entry says
         * memory is read before it is cleared (PRM §4 CLR, pp. 4-73–4-74),
         * and X is preserved while N/V/C clear and Z sets. Keep all admitted
         * word-memory destinations in one path so EA decoding, alignment,
         * read-before-write and flags cannot drift between forms. The PRM does
         * not specify partial address-register state after a failed bus cycle;
         * this core commits predecrement after EA calculation and accounting
         * preflight, before operand access or address-error entry. Postincrement
         * normally follows a successful operand read; an odd address-error
         * commits it before vector 3 per the pinned MAME differential. Table
         * 8-6 p. 8-6 gives 8(1/1)+;
         * Table 8-1 p. 8-2 adds (An)/(An)+ 4, -(An) 6, d16/abs.w 8,
         * brief-index 10, or abs.l 12 clocks. */
        const unsigned mode = (unsigned)((*opcode >> 3) & 7u);
        const unsigned ea_register = (unsigned)(*opcode & 7u);
        uint32_t destination = 0u;
        uint64_t instruction_cycles = 0u;
        int postincrement = 0;
        int predecrement = 0;
        switch (mode) {
        case 2u:
            destination = cpu->address_registers[ea_register];
            instruction_cycles = UINT64_C(12);
            break;
        case 3u:
            destination = cpu->address_registers[ea_register];
            postincrement = 1;
            instruction_cycles = UINT64_C(12);
            break;
        case 4u:
            destination = cpu->address_registers[ea_register] - UINT32_C(2);
            predecrement = 1;
            instruction_cycles = UINT64_C(14);
            break;
        case 5u: {
            uint16_t displacement = 0u;
            status = fetch_word(cpu, &cursor, &displacement);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            destination = cpu->address_registers[ea_register] +
                          sign_extend_word(displacement);
            instruction_cycles = UINT64_C(16);
            break;
        }
        case 6u: {
            uint16_t extension = 0u;
            status = fetch_word(cpu, &cursor, &extension);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            if ((extension & UINT16_C(0x0700)) != 0u) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return OWNED_CPU_UNSUPPORTED_OPCODE;
            }
            const unsigned index_register = (unsigned)((extension >> 12) & 7u);
            const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
                ? cpu->address_registers[index_register]
                : cpu->data_registers[index_register];
            const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
                ? index_full : sign_extend_word((uint16_t)index_full);
            destination = cpu->address_registers[ea_register] +
                          sign_extend_byte((uint8_t)extension) + index;
            instruction_cycles = UINT64_C(18);
            break;
        }
        case 7u:
            if (ea_register == 0u) {
                uint16_t absolute_short = 0u;
                status = fetch_word(cpu, &cursor, &absolute_short);
                if (status != OWNED_CPU_OK) {
                    cpu->fault_pc = instruction_pc;
                    cpu->instruction_register = *opcode;
                    return status;
                }
                destination = sign_extend_word(absolute_short);
                instruction_cycles = UINT64_C(16);
            } else if (ea_register == 1u) {
                uint16_t high = 0u;
                uint16_t low = 0u;
                status = fetch_word(cpu, &cursor, &high);
                if (status == OWNED_CPU_OK)
                    status = fetch_word(cpu, &cursor, &low);
                if (status != OWNED_CPU_OK) {
                    cpu->fault_pc = instruction_pc;
                    cpu->instruction_register = *opcode;
                    return status;
                }
                destination = ((uint32_t)high << 16) | (uint32_t)low;
                instruction_cycles = UINT64_C(20);
            } else {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return OWNED_CPU_UNSUPPORTED_OPCODE;
            }
            break;
        default:
            /* Dn and An-direct are intentionally outside this memory-EA
             * extension; CLR.W PC-relative and immediate forms are invalid. */
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (predecrement != 0)
                write_address_register(cpu, ea_register, destination);
            else if (postincrement != 0)
                write_address_register(cpu, ea_register,
                                       destination + UINT32_C(2));
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (predecrement != 0)
            write_address_register(cpu, ea_register, destination);
        uint16_t discarded = 0u;
        status = read_word(cpu, destination, &discarded);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (postincrement != 0)
            write_address_register(cpu, ea_register,
                                   destination + UINT32_C(2));
        status = write_word(cpu, destination, 0u);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_word_flags(cpu, 0u);
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xffc0)) == UINT16_C(0x4280) &&
               is_data_alterable_memory_ea(*opcode) != 0) {
        /* CLR.L memory, data-alterable EA only. PRM §4 CLR, pp. 4-73 to 4-74,
         * defines N/V/C clear, Z set and X preserved, and says the MC68000
         * reads a memory location before clearing it. Keep all seven legal
         * memory EAs in this shared resolver path. UM Rev. 9.1 Table 8-6
         * (printed p. 8-6) gives long CLR memory as 12(1/2)+; Table 8-1
         * (printed p. 8-2) supplies long EA time, for totals 20/20/22/24/26/
         * 24/28 clocks in indirect, postincrement, predecrement, displacement,
         * brief-index, absolute-short, and absolute-long order. The read pair
         * precedes either clear write; postincrement commits after both reads
         * on success, and before vector 3 for an odd EA per the pinned MAME
         * differential. Predecrement commits after timing preflight and before
         * access. */
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   4u, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t total_cycles = UINT64_C(12) + ea.address_cycles;
        if ((ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, ea.address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, ea.address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        status = write_word(cpu, ea.address, 0u);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, ea.address + UINT32_C(2), 0u);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, 0u);
        *cycles = total_cycles;
    } else if (*opcode == UINT16_C(0x4239)) {
        /* CLR.B (xxx).L (plan 05-20, guest-observed). CLR.W (xxx).L is
         * separately admitted above; long and other byte modes stay unsupported
         * except the already admitted displacement form. */
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t destination = ((uint32_t)high << 16) | (uint32_t)low;
        /* PRM section 4 CLR, pp. 4-73 to 4-74: N=0, Z=1, V=0, C=0, X
         * unchanged; the MC68000 reads the location before clearing it.
         * User's Manual Rev. 9.1 Table 8-6 (printed p. 8-6) CLR byte memory
         * 8(1/1) plus Table 8-1 (printed p. 8-2) (xxx).L byte 12(3/0) =
         * 20(4/1). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t discarded = 0u;
        status = read_byte(cpu, destination, &discarded);
        if (status == OWNED_CPU_OK) status = write_byte(cpu, destination, 0u);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, 0u);
        *cycles = UINT64_C(20);
    } else if (negx_data_alterable_memory_width(*opcode) != 0u) {
        /* NEGX.B/W/L to data-alterable memory. PRM §4 NEGX defines
         * 0-destination-X, X=C, N from the width-limited result, V on signed
         * overflow and sticky Z. UM Rev. 9.1 Table 8-6 p. 8-6 gives byte/word
         * memory 8(1/1)+ and long memory 12(1/2)+; Table 8-1 p. 8-2 adds EA
         * time. RMW update/fault chronology below is the owned-core contract. */
        const unsigned width = negx_data_alterable_memory_width(*opcode);
        const unsigned bits = width * 8u;
        const uint32_t mask = width == 1u ? UINT32_C(0xff) :
            width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
        const uint32_t sign_bit = UINT32_C(1) << (bits - 1u);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
            }
            return status;
        }
        const uint64_t instruction_cycles =
            (width == 4u ? UINT64_C(12) : UINT64_C(8)) + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t operand = 0u;
        if (width == 1u) {
            uint8_t byte = 0u;
            status = read_byte(cpu, ea.address, &byte);
            operand = byte;
        } else if (width == 2u) {
            uint16_t word = 0u;
            status = read_word(cpu, ea.address, &word);
            operand = word;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            operand = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        const unsigned extend = (cpu->sr & SR_X) != 0u ? 1u : 0u;
        const int64_t modulus = INT64_C(1) << bits;
        const int64_t signed_operand = (operand & sign_bit) != 0u
            ? (int64_t)operand - modulus : (int64_t)operand;
        const int64_t signed_result = -signed_operand - (int64_t)extend;
        const int64_t signed_min = -(INT64_C(1) << (bits - 1u));
        const int64_t signed_max = -signed_min - INT64_C(1);
        const uint32_t result = (UINT32_C(0) - operand - extend) & mask;
        uint16_t flags = (uint16_t)(cpu->sr &
            (uint16_t)~(SR_X | SR_N | SR_V | SR_C));
        if (result != 0u) flags = (uint16_t)(flags & (uint16_t)~SR_Z);
        if ((result & sign_bit) != 0u) flags = (uint16_t)(flags | SR_N);
        if (signed_result < signed_min || signed_result > signed_max)
            flags = (uint16_t)(flags | SR_V);
        if (operand != 0u || extend != 0u)
            flags = (uint16_t)(flags | SR_X | SR_C);

        if (width == 1u) {
            status = write_byte(cpu, ea.address, (uint8_t)result);
        } else if (width == 2u) {
            status = write_word(cpu, ea.address, (uint16_t)result);
        } else {
            status = write_word(cpu, ea.address, (uint16_t)(result >> 16));
            if (status == OWNED_CPU_OK)
                status = write_word(cpu, ea.address + UINT32_C(2),
                                    (uint16_t)result);
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        cpu->sr = flags;
        *cycles = instruction_cycles;
    } else if (neg_data_alterable_memory_width(*opcode) != 0u) {
        /* NEG.B/W/L to data-alterable memory. PRM §4 NEG, pp. 4-143–4-144,
         * defines 0-destination with X=C, N/Z from the result and V on signed
         * overflow. UM Rev. 9.1 Table 8-6 p. 8-6 gives memory bases 8(1/1)
         * for byte/word and 12(1/2) for long; Table 8-1 p. 8-2 adds EA time. */
        const unsigned width = neg_data_alterable_memory_width(*opcode);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
            }
            return status;
        }
        const uint64_t instruction_cycles =
            (width == 4u ? UINT64_C(12) : UINT64_C(8)) + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t operand = 0u;
        if (width == 1u) {
            uint8_t byte = 0u;
            status = read_byte(cpu, ea.address, &byte);
            operand = byte;
        } else if (width == 2u) {
            uint16_t word = 0u;
            status = read_word(cpu, ea.address, &word);
            operand = word;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            operand = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint16_t flags = cpu->sr;
        const uint32_t result = addsub_value(cpu->sr, 0u, operand, width, 1,
                                             &flags);
        if (width == 1u) {
            status = write_byte(cpu, ea.address, (uint8_t)result);
        } else if (width == 2u) {
            status = write_word(cpu, ea.address, (uint16_t)result);
        } else {
            status = write_word(cpu, ea.address, (uint16_t)(result >> 16));
            if (status == OWNED_CPU_OK)
                status = write_word(cpu, ea.address + UINT32_C(2),
                                    (uint16_t)result);
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        cpu->sr = flags;
        *cycles = instruction_cycles;
    } else if (((*opcode & UINT16_C(0xff00)) == UINT16_C(0x4400)) &&
               (((*opcode >> 6) & 3u) < 3u) &&
               (((*opcode >> 3) & 7u) == 0u)) {
        /* NEG.B/W/L Dn. PRM §4 NEG, pp. 4-142–4-144, defines 0-Dn with X=C,
         * N/Z from the width-limited result and V on signed overflow. UM Rev.
         * 9.1 Table 8-6 (printed p. 8-6) gives byte/word register forms 4(1/0)
         * and long 6(1/0). Keep memory destinations and invalid sizes outside
         * this register-direct slice. */
        const unsigned size_code = (unsigned)((*opcode >> 6) & 3u);
        const unsigned width = size_code == 0u ? 1u :
            size_code == 1u ? 2u : 4u;
        const unsigned reg = (unsigned)(*opcode & 7u);
        const uint32_t mask = width == 1u ? UINT32_C(0xff) :
            width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
        const uint64_t instruction_cycles = width == 4u
            ? UINT64_C(6) : UINT64_C(4);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t before = cpu->data_registers[reg];
        uint16_t flags = cpu->sr;
        const uint32_t result = addsub_value(cpu->sr, 0u, before & mask,
                                             width, 1, &flags);
        cpu->data_registers[reg] = (before & ~mask) | result;
        cpu->sr = flags;
        *cycles = instruction_cycles;
    } else if (((*opcode & UINT16_C(0xff00)) == UINT16_C(0x4600)) &&
               (((*opcode >> 6) & 3u) < 3u) &&
               (((*opcode >> 3) & 7u) == 0u ||
                is_data_alterable_memory_ea(*opcode) != 0)) {
        /* NOT has one operation for byte/word/long data registers and all
         * seven data-alterable memory EAs. PRM §4 NOT, pp. 4-148 to 4-149,
         * defines ones complement, N/Z from the result, V/C clear and X
         * preserved. UM Rev. 9.1 Table 8-6 p. 8-6 gives register 4/4/6 and
         * memory 8/8/12 clocks before adding the Table 8-1 EA time. */
        const unsigned size_code = (unsigned)((*opcode >> 6) & 3u);
        const unsigned width = size_code == 0u ? 1u :
            size_code == 1u ? 2u : 4u;
        const unsigned mode = (unsigned)((*opcode >> 3) & 7u);
        if (mode == 0u) {
            const uint64_t instruction_cycles = width == 4u
                ? UINT64_C(6) : UINT64_C(4);
            status = preflight_event(cpu, STEP_INSTRUCTION,
                                     instruction_cycles, 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            const unsigned reg = (unsigned)(*opcode & 7u);
            const uint32_t mask = width == 4u ? UINT32_MAX :
                (UINT32_C(1) << (width * 8u)) - UINT32_C(1);
            const uint32_t result = ~cpu->data_registers[reg] & mask;
            cpu->data_registers[reg] =
                (cpu->data_registers[reg] & ~mask) | result;
            if (width == 1u) set_move_byte_flags(cpu, (uint8_t)result);
            else if (width == 2u) set_move_word_flags(cpu, (uint16_t)result);
            else set_move_flags(cpu, result);
            *cycles = instruction_cycles;
        } else {
            data_alterable_memory_ea ea;
            status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                       width, &ea);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            const uint64_t instruction_cycles =
                (width == 4u ? UINT64_C(12) : UINT64_C(8)) +
                ea.address_cycles;
            if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
                status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                         EXCEPTION_ADDRESS_ERROR_CYCLES,
                                         0u, 0u);
                if (status != OWNED_CPU_OK) return status;
                /* At pinned MAME 31e52312, x4658_not_w_pi_071234fc and
                 * x4698_not_l_pi_071234fc call EA_AY_PI_16/32 before the
                 * operand read; an odd word/long read retains the update in
                 * that differential. The manuals specify vector 3 but not
                 * this partial state. */
                if (ea.has_base_update != 0u)
                    write_address_register(cpu, ea.base_register,
                                           ea.updated_base);
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                status = enter_address_exception(cpu, instruction_pc, *opcode,
                                                 ea.address, 0, 1);
                if (status != OWNED_CPU_OK) return status;
                *next_pc = cpu->pc;
                *kind = STEP_ADDRESS_EXCEPTION;
                *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
                return OWNED_CPU_OK;
            }
            status = preflight_event(cpu, STEP_INSTRUCTION,
                                     instruction_cycles, 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);

            uint32_t operand = 0u;
            if (width == 1u) {
                uint8_t byte = 0u;
                status = read_byte(cpu, ea.address, &byte);
                operand = byte;
            } else if (width == 2u) {
                uint16_t word = 0u;
                status = read_word(cpu, ea.address, &word);
                operand = word;
            } else {
                uint16_t high = 0u;
                uint16_t low = 0u;
                status = read_word(cpu, ea.address, &high);
                if (status == OWNED_CPU_OK)
                    status = read_word(cpu, ea.address + UINT32_C(2), &low);
                operand = ((uint32_t)high << 16) | (uint32_t)low;
            }
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            if (ea.has_base_update != 0u && ea.update_after_access != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);

            const uint32_t mask = width == 4u ? UINT32_MAX :
                (UINT32_C(1) << (width * 8u)) - UINT32_C(1);
            const uint32_t result = ~operand & mask;
            if (width == 1u)
                status = write_byte(cpu, ea.address, (uint8_t)result);
            else if (width == 2u)
                status = write_word(cpu, ea.address, (uint16_t)result);
            else {
                status = write_word(cpu, ea.address, (uint16_t)(result >> 16));
                if (status == OWNED_CPU_OK)
                    status = write_word(cpu, ea.address + UINT32_C(2),
                                        (uint16_t)result);
            }
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            if (width == 1u) set_move_byte_flags(cpu, (uint8_t)result);
            else if (width == 2u) set_move_word_flags(cpu, (uint16_t)result);
            else set_move_flags(cpu, result);
            *cycles = instruction_cycles;
        }
    } else if ((*opcode & UINT16_C(0xff38)) == UINT16_C(0x4a00) &&
               (((*opcode >> 6) & 3u) < 3u)) {
        /* TST.B/W/L Dn shares the register-only path. PRM §4 TST,
         * pp. 4-192 to 4-193, specifies N/Z from the selected width, clears
         * V/C and preserves X. UM Rev. 9.1 Table 8-6 p. 8-6 gives 4(1/0)
         * for each register size. Memory TST forms retain their separate
         * width- and EA-specific paths below. */
        const unsigned size_code = (unsigned)((*opcode >> 6) & 3u);
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned reg = (unsigned)(*opcode & 7u);
        if (size_code == 0u) {
            set_move_byte_flags(cpu, (uint8_t)cpu->data_registers[reg]);
        } else if (size_code == 1u) {
            set_move_word_flags(cpu, (uint16_t)cpu->data_registers[reg]);
        } else {
            set_move_flags(cpu, cpu->data_registers[reg]);
        }
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4aa8)) {
        /* TST.L d16(An), reached by the bounded ordinary guest path. PRM §4
         * TST pp. 4-192 to 4-193 defines N/Z from the operand, clears V/C and
         * preserves X. UM Rev. 9.1 Table 8-6 p. 8-6 gives a four-cycle base;
         * Table 8-1 p. 8-2 adds 12(3/0) for long d16(An), totaling 16 clocks. */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const uint32_t source = cpu->address_registers[base_register] +
                                sign_extend_word(extension);
        if ((source & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = read_word(cpu, source, &high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source + UINT32_C(2), &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, ((uint32_t)high << 16) | (uint32_t)low);
        *cycles = UINT64_C(16);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4ab0)) {
        /* TST.L (d8,An,Xn), reached by the bounded ordinary guest path. Only
         * MC68000 brief indexed extensions are admitted; bits 10-8 remain
         * unsupported. PRM §2.2.7 defines signed d8 plus a signed word or full
         * long index. PRM §4 TST pp. 4-192 to 4-193 defines N/Z from the
         * long operand, cleared V/C and preserved X. UM Rev. 9.1 Table 8-6
         * p. 8-6 gives a 4(1/0) base; Table 8-1 p. 8-2 adds 14(3/0) for the
         * long indexed EA, totaling 18 clocks and four word reads. */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t source = cpu->address_registers[base_register] +
            sign_extend_byte((uint8_t)extension) + index;
        if ((source & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(18), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = read_word(cpu, source, &high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source + UINT32_C(2), &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, ((uint32_t)high << 16) | (uint32_t)low);
        *cycles = UINT64_C(18);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4a10)) {
        /* TST.B (An) (guest-observed during plan 05-02 continuation). Byte
         * addressing permits an odd An value. PRM §4 TST pp. 4-192 to 4-193
         * sets N/Z from the byte, clears V/C, and preserves X. UM Rev. 9.1
         * Table 8-6 p. 8-6 gives 4(1/0); Table 8-1 p. 8-2 adds 4(1/0) for
         * (An), totaling 8 clocks. This mode does not update An or memory.
         */
        const unsigned address_register = (unsigned)(*opcode & 7u);
        const uint32_t address = cpu->address_registers[address_register];
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t value = 0u;
        status = read_byte(cpu, address, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4a50)) {
        /* TST.W (An) (selected guest continuation, plan 05-02 task 2). This
         * admits only the word address-indirect form. PRM section 4 TST,
         * pp. 4-192 to 4-193: N/Z come from the operand, V/C clear and X is
         * unchanged. UM Rev. 9.1 Table 8-6 p. 8-6 gives 4(1/0); Table 8-1
         * p. 8-2 adds 4(1/0) for (An), totaling 8 clocks (two reads, no write). */
        const unsigned address_register = (unsigned)(*opcode & 7u);
        const uint32_t address = cpu->address_registers[address_register];
        if ((address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value = 0u;
        status = read_word(cpu, address, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4a28)) {
        /* TST.B (d16,An) (guest demanded, plan 05-02). Byte accesses permit
         * odd addresses. PRM TST pp. 4-192 to 4-193 defines N/Z from the byte,
         * clears V/C, and preserves X. UM Rev. 9.1 Table 8-6 p. 8-6 gives
         * 4(1/0); Table 8-1 p. 8-2 adds 8(2/0) for byte (d16,An), totaling
         * 12 clocks and two word fetches plus one byte operand read. */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const uint32_t address = cpu->address_registers[base_register] +
            sign_extend_word(extension);
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t value = 0u;
        status = read_byte(cpu, address, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4a30)) {
        /* TST.B (d8,An,Xn) (guest-demanded, plan 05-02 task 2). Only the
         * MC68000 brief indexed extension is accepted; bits 10-8 remain
         * unsupported. PRM §2.2.7 defines signed d8 plus a signed word or full
         * long index. TST sets N/Z from the byte, clears V/C, and preserves X
         * (PRM §4 TST, pp. 4-192 to 4-193). Byte operands permit odd addresses.
         * UM Rev. 9.1 Table 8-6 p. 8-6 gives 4(1/0); Table 8-1 p. 8-2 gives
         * indexed EA 10(2/0), totaling 14 clocks. */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t source = cpu->address_registers[base_register] +
            sign_extend_byte((uint8_t)extension) + index;
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(14), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t value = 0u;
        status = read_byte(cpu, source, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(14);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4a70)) {
        /* TST.W (d8,An,Xn) (guest demanded, plan 05-02). Only the MC68000
         * brief indexed extension is implemented; bits 10-8 remain reserved
         * and unsupported. PRM section 2.2.7 defines signed d8 plus a signed
         * word or full long index. TST sets N/Z from the operand, clears V/C,
         * and preserves X (PRM section 4 TST, pp. 4-192 to 4-193). UM Rev.
         * 9.1 Table 8-6 p. 8-6 gives TST word memory 4(1/0); Table 8-1 p. 8-2
         * gives indexed word EA 10(2/0), totaling 14 clocks (3 word reads,
         * no writes). */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t source = cpu->address_registers[base_register] +
            sign_extend_byte((uint8_t)extension) + index;
        if ((source & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(14), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value = 0u;
        status = read_word(cpu, source, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(14);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4a68)) {
        /* TST.W (d16,An) (guest demanded, plan 05-02). The displacement is
         * signed and the operand is read without changing An. PRM TST pp.
         * 4-192 to 4-193 defines N/Z from the word, clears V/C, and preserves
         * X. UM Rev. 9.1 Table 8-6's 4(1/0) plus Table 8-1's d16,An word
         * 8(2/0) gives 12 clocks. */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const uint32_t source = cpu->address_registers[base_register] +
                                sign_extend_word(extension);
        if ((source & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value = 0u;
        status = read_word(cpu, source, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(12);
    } else if (*opcode == UINT16_C(0x4a38)) {
        /* TST.B (xxx).W (guest demanded, plan 05-02). The absolute-short
         * extension is sign extended and byte accesses permit odd addresses.
         * PRM TST pp. 4-192 to 4-193 defines N/Z from the byte, clears V/C,
         * and preserves X. UM Rev. 9.1 Table 8-6's 4(1/0) plus Table 8-1's
         * absolute-short byte 8(2/0) gives 12 clocks. */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t source = sign_extend_word(extension);
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t value = 0u;
        status = read_byte(cpu, source, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(12);
    } else if (*opcode == UINT16_C(0x4a79)) {
        /* TST.W (xxx).L is the observed absolute-long word probe. Both
         * address words are fetched before the aligned operand read. An odd
         * address raises vector 3 without an operand transfer. PRM section 4
         * TST sets N/Z from the word, clears V/C and preserves X; UM Rev. 9.1
         * Table 8-6 (printed p. 8-6) gives 4(1/0), plus the Table 8-1
         * absolute-long word EA 12(3/0), for 16(4/0). */
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t source = ((uint32_t)high << 16) | (uint32_t)low;
        if ((source & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
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
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(16);
    } else if (*opcode == UINT16_C(0x4a39)) {
        /* TST.B (xxx).L (guest demanded, plan 05-11). Word and long sizes and
         * every other unimplemented mode stay unsupported. */
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t source = ((uint32_t)high << 16) | (uint32_t)low;
        /* Operation and condition codes: M68000 Family PRM section 4, TST,
         * pp. 4-192 to 4-193 (N and Z from the operand, V and C cleared, X
         * unchanged). Timing: User's Manual Rev. 9.1 Table 8-6 (printed p.
         * 8-6) TST byte memory 4(1/0) plus Table 8-1 (printed p. 8-2)
         * (xxx).L byte 12(3/0) = 16 clocks. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t value = 0u;
        status = read_byte(cpu, source, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(16);
    } else if ((*opcode & UINT16_C(0xf000)) == UINT16_C(0x5000) &&
               ((*opcode >> 6) & 3u) != 3u &&
               is_data_alterable_memory_ea(*opcode) != 0) {
        /* ADDQ/SUBQ memory destinations share the MC68000 data-alterable EA
         * forms. UM Rev. 9.1 Table 8-5 p. 8-5 gives 8(1/1)+ for byte/word
         * and 12(1/2)+ for long; Table 8-1 p. 8-2 supplies EA time. */
        const unsigned size_code = (unsigned)((*opcode >> 6) & 3u);
        const unsigned width = size_code == 0u ? 1u : size_code == 1u ? 2u : 4u;
        const unsigned subtract = (*opcode & UINT16_C(0x0100)) != 0u;
        unsigned quick = (unsigned)((*opcode >> 9) & 7u);
        if (quick == 0u) quick = 8u;
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
            }
            return status;
        }
        const uint64_t total_cycles =
            (width == 4u ? UINT64_C(12) : UINT64_C(8)) + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t before = 0u;
        if (width == 1u) {
            uint8_t value = 0u;
            status = read_byte(cpu, ea.address, &value);
            before = value;
        } else if (width == 2u) {
            uint16_t value = 0u;
            status = read_word(cpu, ea.address, &value);
            before = value;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            before = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint16_t flags = 0u;
        const uint32_t after = addsub_value(cpu->sr, before, quick, width,
                                             (int)subtract, &flags);
        if (width == 1u) {
            status = write_byte(cpu, ea.address, (uint8_t)after);
        } else if (width == 2u) {
            status = write_word(cpu, ea.address, (uint16_t)after);
        } else {
            status = write_word(cpu, ea.address, (uint16_t)(after >> 16));
            if (status == OWNED_CPU_OK)
                status = write_word(cpu, ea.address + UINT32_C(2), (uint16_t)after);
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        cpu->sr = flags;
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xff00)) == UINT16_C(0x0c00) &&
               ((*opcode >> 6) & 3u) < 3u &&
               is_data_alterable_memory_ea(*opcode) != 0) {
        /* CMPI.B/W/L #imm,<data-alterable memory EA>. Fetch the immediate
         * words before EA extensions, then read (never write) the operand.
         * PRM §4 CMPI pp. 4-79 to 4-80 defines destination-minus-immediate
         * N/Z/V/C, preserved X and unchanged memory. UM Rev. 9.1 Table 8-5
         * p. 8-5 gives byte/word 8(2/0)+ and long 12(3/0)+; Table 8-1 p. 8-2
         * supplies the width-specific EA timing. The odd PI/PD vector-3 base
         * updates follow pinned generated MAME CMPI.W/L PI/PD handlers as
         * emulator-differential evidence only; terminal host read failures
         * retain the owned-core contract of updating PI only after a complete
         * operand read and PD before access.
         */
        const unsigned size_code = (unsigned)((*opcode >> 6) & 3u);
        const unsigned width = size_code == 0u ? 1u :
            size_code == 1u ? 2u : 4u;
        uint32_t source = 0u;
        uint16_t immediate_high = 0u;
        uint16_t immediate_low = 0u;
        status = fetch_word(cpu, &cursor, &immediate_high);
        if (status == OWNED_CPU_OK && width == 4u)
            status = fetch_word(cpu, &cursor, &immediate_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        source = width == 4u
            ? ((uint32_t)immediate_high << 16) | (uint32_t)immediate_low
            : width == 1u ? (uint32_t)(uint8_t)immediate_high
                          : (uint32_t)immediate_high;

        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t base_cycles = width == 4u ? UINT64_C(12) : UINT64_C(8);
        const uint64_t total_cycles = base_cycles + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t destination = 0u;
        if (width == 1u) {
            uint8_t value = 0u;
            status = read_byte(cpu, ea.address, &value);
            destination = value;
        } else if (width == 2u) {
            uint16_t value = 0u;
            status = read_word(cpu, ea.address, &value);
            destination = value;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            destination = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        set_compare_flags(cpu, destination, source, width);
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb010)) {
        /* CMP.B (An),Dn (05-27 rerun 38). PRM CMP pp. 4-75 to 4-76:
         * byte subtraction updates N/Z/V/C while preserving X and operands.
         * UM Rev. 9.1 Table 8-4 p. 8-4 4(1/0)+ and Table 8-1 p. 8-2
         * (An) byte 4(1/0) = 8(2/0). One opcode-word and one byte read. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t address = cpu->address_registers[*opcode & UINT16_C(7)];
        uint8_t source = 0u;
        status = read_byte(cpu, address, &source);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned data_register = (*opcode >> 9) & 7u;
        const uint8_t destination = (uint8_t)cpu->data_registers[data_register];
        const uint8_t difference = (uint8_t)(destination - source);
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if (difference == 0u) flags = (uint16_t)(flags | SR_Z);
        if ((difference & UINT8_C(0x80)) != 0u) flags = (uint16_t)(flags | SR_N);
        if (((destination ^ source) & (destination ^ difference) & UINT8_C(0x80)) != 0u)
            flags = (uint16_t)(flags | SR_V);
        if (destination < source) flags = (uint16_t)(flags | SR_C);
        cpu->sr = flags;
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0xb039)) {
        /* CMP.B (xxx).L,Dn (05-25). PRM CMP pp. 4-75 to 4-76:
         * byte subtraction for N/Z/V/C; X and both operands unchanged.
         * UM Rev. 9.1 Table 8-4 p. 8-4 4(1/0)+ plus Table 8-1 p. 8-2
         * absolute-long byte 12(3/0) = 16(4/0). This retained exact absolute-
         * long byte case precedes the shared CMP.B/W/L data-alterable memory
         * source resolver below, which handles the other admitted EAs. */
        uint16_t address_high = 0u;
        uint16_t address_low = 0u;
        status = fetch_word(cpu, &cursor, &address_high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &address_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t address = ((uint32_t)address_high << 16) | address_low;
        uint8_t source = 0u;
        status = read_byte(cpu, address, &source);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint8_t destination = (uint8_t)cpu->data_registers[(*opcode >> 9) & 7u];
        const uint8_t difference = (uint8_t)(destination - source);
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if (difference == 0u) flags = (uint16_t)(flags | SR_Z);
        if ((difference & UINT8_C(0x80)) != 0u) flags = (uint16_t)(flags | SR_N);
        if (((destination ^ source) & (destination ^ difference) & UINT8_C(0x80)) != 0u)
            flags = (uint16_t)(flags | SR_V);
        if (destination < source) flags = (uint16_t)(flags | SR_C);
        cpu->sr = flags;
        *cycles = UINT64_C(16);
    } else if (cmp_data_alterable_memory_source_width(*opcode) != 0u) {
        /* CMP byte/word/long memory source to Dn shares the selected CPU's
         * seven data-alterable EAs. UM Rev. 9.1 Table 8-4 p. 8-4 gives base
         * times 4(1/0)+ for byte/word and 6(1/0)+ for long; Table 8-1 p. 8-2
         * supplies the width-specific EA cost. PRM §4 CMP pp. 4-75 to 4-76
         * defines low-width destination-minus-source flags, preserves X, and
         * leaves Dn unchanged. Odd word/long addresses take vector 3 before
         * the operand read; address-register partial-fault ordering follows
         * the owned-core EA policy, not a hardware bus-chronology claim. */
        const unsigned width = cmp_data_alterable_memory_source_width(*opcode);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t base_cycles = width == 4u ? UINT64_C(6) : UINT64_C(4);
        const uint64_t total_cycles = base_cycles + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        uint32_t source = 0u;
        if (width == 1u) {
            uint8_t value = 0u;
            status = read_byte(cpu, ea.address, &value);
            source = value;
        } else if (width == 2u) {
            uint16_t value = 0u;
            status = read_word(cpu, ea.address, &value);
            source = value;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            source = ((uint32_t)high << 16) | low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        const unsigned destination_register =
            (unsigned)((*opcode >> 9) & UINT16_C(7));
        set_compare_flags(cpu, cpu->data_registers[destination_register],
                          source, width);
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb1c8)) {
        /* CMPA.L Ay,Ax (guest demanded). Compare the full address-register
         * values for flags only; X and both registers are preserved. Other
         * effective-address modes remain outside this admitted form. The
         * MC68000 Family PRM CMPA operation and condition codes are at
         * pp. 4-77 to 4-78; User's Manual Rev. 9.1 Table 8-4 lists 6(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(6), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t source = cpu->address_registers[source_register];
        set_cmpa_flags(cpu, destination_register, source);
        *cycles = UINT64_C(6);
    } else if ((*opcode & UINT16_C(0xf0ff)) == UINT16_C(0xb0fc)) {
        /* CMPA.W/L #imm,An shares one immediate path. The word source is
         * sign-extended; long uses all 32 immediate bits. Table 8-4 gives
         * CMPA 6(1/0)+; Table 8-1 adds 4(1/0) for word or 8(2/0) for long,
         * totaling 10 or 14 clocks (UM Rev. 9.1, printed pp. 8-2, 8-4). */
        const int long_immediate = (*opcode & UINT16_C(0x0100)) != 0u;
        const uint64_t instruction_cycles = long_immediate != 0
            ? UINT64_C(14) : UINT64_C(10);
        /* The preflight count is completed instructions; extension fetches are
         * bus reads and must not inflate this counter. */
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t immediate_high = 0u;
        uint16_t immediate_low = 0u;
        if (long_immediate != 0)
            status = fetch_word(cpu, &cursor, &immediate_high);
        if (status == OWNED_CPU_OK)
            status = fetch_word(cpu, &cursor, &immediate_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t source = long_immediate != 0
            ? ((uint32_t)immediate_high << 16) | (uint32_t)immediate_low
            : sign_extend_word(immediate_low);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        set_cmpa_flags(cpu, destination_register, source);
        *cycles = instruction_cycles;
    } else if (cmpa_data_alterable_memory_source_width(*opcode) != 0u) {
        /* CMPA.W/L admits the seven MC68000 data-alterable memory source EAs.
         * The word is sign-extended before the 32-bit An comparison; flags
         * follow PRM §4 CMPA (pp. 4-77–4-78), preserving X and not writing the
         * destination register except when it aliases an EA auto-update base.
         * UM Rev. 9.1 Table 8-4 (printed p. 8-4) gives 6(1/0)+; Table 8-1
         * (p. 8-2) supplies the EA cost, including long bus-transfer counts.
         * Odd word/long addresses enter vector 3 before operand access. The
         * partial base update at that exception boundary follows the shared
         * EA policy and pinned generated-handler differential, not a manual
         * bus-chronology claim. */
        const unsigned width = cmpa_data_alterable_memory_source_width(*opcode);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t total_cycles = UINT64_C(6) + ea.address_cycles;
        if ((ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t source = 0u;
        if (width == 2u) {
            uint16_t word = 0u;
            status = read_word(cpu, ea.address, &word);
            source = sign_extend_word(word);
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            source = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        set_cmpa_flags(cpu, (unsigned)((*opcode >> 9) & UINT16_C(7)), source);
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2008)) {
        /* MOVE.L An,Dn (guest demanded, plan 05-11). Byte-sized An-direct is
         * invalid; memory byte sources and other address-register source
         * sizes are handled separately. Operation and condition codes:
         * PRM section 4 MOVE, pp. 4-116 to 4-118 (N/Z from the long, V/C
         * cleared, X unchanged). Timing: User's Manual Rev. 9.1 Table 8-3
         * (printed p. 8-3), An source to Dn destination: 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t value = cpu->address_registers[*opcode & 7u];
        cpu->data_registers[(*opcode >> 9) & 7u] = value;
        set_move_flags(cpu, value);
        *cycles = UINT64_C(4);
    } else if (add_data_alterable_memory_source_width(*opcode) != 0u) {
        /* ADD byte/word/long data-alterable memory source to Dn. PRM §4 ADD,
         * pp. 4-3 to 4-5, defines width-limited addition, X/C/N/Z/V, and
         * preservation of the unaffected upper Dn bits for byte/word. UM
         * Rev. 9.1 Table 8-4 p. 8-4 gives base 4(1/0)+ for byte/word and
         * 6(1/0)+ for long; Table 8-1 p. 8-2 supplies each EA cost. Odd
         * word/long addresses take vector 3 before the operand access. The
         * partial address-register update on that exception follows the pinned
         * MAME ADD EA-handler differential (not manual hardware chronology);
         * host read-callback failure remains a distinct terminal path. */
        const unsigned width = add_data_alterable_memory_source_width(*opcode);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
            }
            return status;
        }
        const uint64_t base_cycles = width == 4u ? UINT64_C(6) : UINT64_C(4);
        const uint64_t total_cycles = base_cycles + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t source = 0u;
        if (width == 1u) {
            uint8_t value = 0u;
            status = read_byte(cpu, ea.address, &value);
            source = value;
        } else if (width == 2u) {
            uint16_t value = 0u;
            status = read_word(cpu, ea.address, &value);
            source = value;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            source = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        const unsigned destination_register =
            (unsigned)((*opcode >> 9) & UINT16_C(7));
        const uint32_t mask = width == 1u ? UINT32_C(0xff) :
            width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
        uint16_t flags = 0u;
        const uint32_t result = addsub_value(cpu->sr,
            cpu->data_registers[destination_register], source, width, 0, &flags);
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & ~mask) | (result & mask);
        cpu->sr = flags;
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xc140) ||
               (*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xc148) ||
               (*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xc188)) {
        /* EXG exchanges full-width register values for Dn,Dm; An,Am; and
         * Dn,Am. It leaves every condition code unchanged. Address-register
         * writes pass through write_address_register so an active A7 exchange
         * stays synchronized with SSP or USP. PRM §4 EXG pp. 4-104 to 4-105;
         * UM Rev. 9.1 Table 8-12 p. 8-10 gives 6(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(6), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned first = (unsigned)((*opcode >> 9) & 7u);
        const unsigned second = (unsigned)(*opcode & 7u);
        const uint16_t form = (uint16_t)(*opcode & UINT16_C(0xf1f8));
        if (form == UINT16_C(0xc140)) {
            const uint32_t first_value = cpu->data_registers[first];
            const uint32_t second_value = cpu->data_registers[second];
            cpu->data_registers[first] = second_value;
            cpu->data_registers[second] = first_value;
        } else if (form == UINT16_C(0xc148)) {
            const uint32_t first_value = cpu->address_registers[first];
            const uint32_t second_value = cpu->address_registers[second];
            write_address_register(cpu, first, second_value);
            write_address_register(cpu, second, first_value);
        } else {
            const uint32_t data_value = cpu->data_registers[first];
            const uint32_t address_value = cpu->address_registers[second];
            cpu->data_registers[first] = address_value;
            write_address_register(cpu, second, data_value);
        }
        *cycles = UINT64_C(6);
    } else if (and_data_alterable_memory_source_width(*opcode) != 0u) {
        /* AND byte/word/long data-alterable memory source to Dn. PRM §4 AND,
         * pp. 4-15 to 4-17, defines width-limited results, N/Z, cleared V/C
         * and preserved X. UM Rev. 9.1 Table 8-4 p. 8-4 gives base 4(1/0)+
         * for byte/word and 6(1/0)+ for long; Table 8-1 p. 8-2 supplies the
         * EA cost. PC-relative and immediate sources remain outside this
         * memory-subset handler. Odd word/long addresses take vector 3 before
         * operand access; pre/post update chronology follows the common EA
         * contract, and host read faults remain terminal without false flags.
         */
        const unsigned width = and_data_alterable_memory_source_width(*opcode);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
            }
            return status;
        }
        const uint64_t base_cycles = width == 4u ? UINT64_C(6) : UINT64_C(4);
        const uint64_t total_cycles = base_cycles + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t source = 0u;
        if (width == 1u) {
            uint8_t value = 0u;
            status = read_byte(cpu, ea.address, &value);
            source = value;
        } else if (width == 2u) {
            uint16_t value = 0u;
            status = read_word(cpu, ea.address, &value);
            source = value;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            source = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        const unsigned destination_register =
            (unsigned)((*opcode >> 9) & UINT16_C(7));
        if (width == 1u) {
            const uint8_t result = (uint8_t)cpu->data_registers[destination_register] &
                                   (uint8_t)source;
            cpu->data_registers[destination_register] =
                (cpu->data_registers[destination_register] & UINT32_C(0xffffff00)) |
                (uint32_t)result;
            set_move_byte_flags(cpu, result);
        } else if (width == 2u) {
            const uint16_t result =
                (uint16_t)cpu->data_registers[destination_register] &
                (uint16_t)source;
            cpu->data_registers[destination_register] =
                (cpu->data_registers[destination_register] & UINT32_C(0xffff0000)) |
                (uint32_t)result;
            set_move_word_flags(cpu, result);
        } else {
            const uint32_t result = cpu->data_registers[destination_register] & source;
            cpu->data_registers[destination_register] = result;
            set_move_flags(cpu, result);
        }
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xc000) ||
               (*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xc040) ||
               (*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xc080)) {
        /* AND.{B,W,L} Dm,Dn: the register-direct source and destination
         * opmodes use one width-aware path. Byte/word take four clocks; the
         * long direct-source form is eight because UM Table 8-4's 6-clock
         * base has footnote **'s two-clock register-direct adjustment. PRM
         * §4 AND pp. 4-15 to 4-17 defines width-specific results, N/Z, cleared
         * V/C and preserved X. The separate Dn-to-memory word form below
         * remains distinct; other memory sources stay unsupported. */
        const unsigned size = (unsigned)((*opcode >> 6) & 3u);
        const uint64_t instruction_cycles = size == 2u
            ? UINT64_C(8) : UINT64_C(4);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t source = cpu->data_registers[source_register];
        const uint32_t destination = cpu->data_registers[destination_register];
        if (size == 0u) {
            const uint8_t result = (uint8_t)((uint8_t)destination & (uint8_t)source);
            cpu->data_registers[destination_register] =
                (destination & UINT32_C(0xffffff00)) | (uint32_t)result;
            set_move_byte_flags(cpu, result);
        } else if (size == 1u) {
            const uint16_t result = (uint16_t)((uint16_t)destination & (uint16_t)source);
            cpu->data_registers[destination_register] =
                (destination & UINT32_C(0xffff0000)) | (uint32_t)result;
            set_move_word_flags(cpu, result);
        } else {
            const uint32_t result = destination & source;
            cpu->data_registers[destination_register] = result;
            set_move_flags(cpu, result);
        }
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xc158)) {
        /* AND.W Dn,(An)+ is the exact memory-destination form reached by the
         * bounded no-input continuation. PRM §4 AND defines N/Z from the word,
         * clears V/C and preserves X. UM Rev. 9.1 Table 8-4 p. 8-4 gives
         * Dn-to-memory 8(1/1)+; Table 8-1 p. 8-2 adds word (An)+ 4(1/0), for
         * 12(2/1) in this no-prefetch bus model. The pinned MAME differential
         * uses EA_AY_PI_16 before m68ki_read_16, so An advances by two before
         * an odd-address read error. */
        const unsigned source_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned address_register = (unsigned)(*opcode & 7u);
        const uint32_t address = cpu->address_registers[address_register];
        if ((address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            write_address_register(cpu, address_register,
                                   address + UINT32_C(2));
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 2u, 1u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, address_register,
                               address + UINT32_C(2));
        uint16_t destination = 0u;
        status = read_word(cpu, address, &destination);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint16_t result = (uint16_t)(
            (uint16_t)cpu->data_registers[source_register] & destination);
        status = write_word(cpu, address, result);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint16_t flags = (uint16_t)(cpu->sr &
            (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if ((result & UINT16_C(0x8000)) != 0u)
            flags = (uint16_t)(flags | SR_N);
        if (result == 0u) flags = (uint16_t)(flags | SR_Z);
        cpu->sr = flags;
        *cycles = UINT64_C(12);
    } else if (and_data_register_memory_destination_width(*opcode) != 0u) {
        status = execute_and_data_register_to_memory(
            cpu, instruction_pc, *opcode, &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if (or_data_register_memory_destination_width(*opcode) != 0u) {
        status = execute_or_data_register_to_memory(
            cpu, instruction_pc, *opcode, &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if (eor_data_register_memory_destination_width(*opcode) != 0u) {
        status = execute_eor_data_register_to_memory(
            cpu, instruction_pc, *opcode, &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb180)) {
        /* EOR.L Dm,Dn (guest-observed register-direct continuation). PRM §4
         * EOR, pp. 4-99 to 4-101, defines full-width XOR, N/Z, cleared V/C
         * and preserved X. UM Rev. 9.1 Table 8-4 p. 8-4 gives 8(1/0) for
         * long EOR to Dn; footnote *** limits that row to Dn direct. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint32_t result = cpu->data_registers[source_register] ^
                                cpu->data_registers[destination_register];
        cpu->data_registers[destination_register] = result;
        uint16_t flags = (uint16_t)(cpu->sr &
            (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if ((result & UINT32_C(0x80000000)) != 0u)
            flags = (uint16_t)(flags | SR_N);
        if (result == 0u) flags = (uint16_t)(flags | SR_Z);
        cpu->sr = flags;
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb100)) {
        /* EOR.B Dm,Dn (guest demanded, plan 05-22). Word register-direct
         * size is handled below; long is above. Data-alterable memory
         * destinations are handled by the separate family. PRM §4 EOR,
         * pp. 4-99 to 4-100: the low byte of the destination Dn (mode 000) is
         * exclusive-ORed with the low byte of Dm (bits 11-9), Dn[31:8]
         * preserved, N/Z from the byte, V/C cleared, X unchanged. User's
         * Manual Rev. 9.1 Table 8-4 (p. 8-4): EOR byte Dn,<ea> to a data
         * register 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint8_t result = (uint8_t)((uint8_t)cpu->data_registers[destination_register] ^
                                         (uint8_t)cpu->data_registers[source_register]);
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & UINT32_C(0xffffff00)) | result;
        set_move_byte_flags(cpu, result);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb140)) {
        /* EOR.W Dm,Dn is the guest-observed word register-direct form. The
         * destination's high word is preserved, X is unchanged, N/Z follow
         * the result, and V/C clear (PRM section 4 EOR, pp. 4-99 to 4-100).
         * MC68000 UM Rev. 9.1 Table 8-4 (printed p. 8-4) gives 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint16_t source =
            (uint16_t)cpu->data_registers[source_register];
        const uint16_t destination =
            (uint16_t)cpu->data_registers[destination_register];
        const uint16_t result = (uint16_t)(source ^ destination);
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & UINT32_C(0xffff0000)) |
            (uint32_t)result;
        uint16_t flags = (uint16_t)(cpu->sr &
            (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if ((result & UINT16_C(0x8000)) != 0u)
            flags = (uint16_t)(flags | SR_N);
        if (result == 0u) flags = (uint16_t)(flags | SR_Z);
        cpu->sr = flags;
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb148)) {
        /* CMPM.W (Ay)+,(Ax)+ (guest demanded). The MC68000 PRM defines
         * destination minus source, updates N/Z/V/C and preserves X; neither
         * operand is written. Source precedes destination, including the
         * same-register case. The UM Rev. 9.1 Table 8-11 lists 12(3/0).
         * Long size and all other direction/mode forms stay unsupported. */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t source_address = cpu->address_registers[source_register];
        if ((source_address & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source_address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t source_next = source_address + UINT32_C(2);
        const uint32_t destination_address =
            destination_register == source_register
                ? source_next : cpu->address_registers[destination_register];
        uint16_t source = 0u;
        uint16_t destination = 0u;
        status = read_word(cpu, source_address, &source);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* The source access completed, so its postincrement is committed
         * before attempting the destination access. This also keeps the
         * source-before-destination order when the address registers match. */
        write_address_register(cpu, source_register, source_next);
        if ((destination_address & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status == OWNED_CPU_OK)
                status = enter_address_exception(cpu, instruction_pc, *opcode,
                                                 destination_address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = read_word(cpu, destination_address, &destination);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, destination_register,
                               destination_address + UINT32_C(2));
        const uint16_t difference = (uint16_t)(destination - source);
        uint16_t flags = (uint16_t)(cpu->sr &
                                    (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if (difference == 0u) flags = (uint16_t)(flags | SR_Z);
        if ((difference & UINT16_C(0x8000)) != 0u)
            flags = (uint16_t)(flags | SR_N);
        if (((destination ^ source) & (destination ^ difference) &
             UINT16_C(0x8000)) != 0u)
            flags = (uint16_t)(flags | SR_V);
        if (destination < source) flags = (uint16_t)(flags | SR_C);
        cpu->sr = flags;
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb108)) {
        /* CMPM.B (Ay)+,(Ax)+ (guest demanded, plan 05-21). Word and long
         * sizes stay unsupported. M68000 Family PRM CMPM, pp. 4-80 to 4-81:
         * destination minus source sets N, Z, V and C (C is the borrow); X is
         * unaffected and neither operand is written. The source is read and Ay
         * postincremented before the destination read, so Ax == Ay reads
         * consecutive bytes; byte postincrement is two for A7 (PRM section 2).
         * User's Manual Rev. 9.1 Table 8-11 (printed p. 8-9): CMPM byte is
         * 12(3/0). */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t source_address = cpu->address_registers[source_register];
        const uint32_t source_next =
            source_address + (source_register == 7u ? UINT32_C(2) : UINT32_C(1));
        const uint32_t destination_address =
            destination_register == source_register
                ? source_next : cpu->address_registers[destination_register];
        uint8_t source = 0u;
        uint8_t destination = 0u;
        status = read_byte(cpu, source_address, &source);
        if (status == OWNED_CPU_OK)
            status = read_byte(cpu, destination_address, &destination);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, source_register, source_next);
        write_address_register(
            cpu, destination_register,
            destination_address + (destination_register == 7u ? UINT32_C(2) : UINT32_C(1)));
        const uint8_t difference = (uint8_t)(destination - source);
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if (difference == 0u) flags = (uint16_t)(flags | SR_Z);
        if ((difference & UINT8_C(0x80)) != 0u) flags = (uint16_t)(flags | SR_N);
        if (((destination ^ source) & (destination ^ difference) & UINT8_C(0x80)) != 0u)
            flags = (uint16_t)(flags | SR_V);
        if (destination < source) flags = (uint16_t)(flags | SR_C);
        cpu->sr = flags;
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2090)) {
        /* MOVE.L (Ay),(Ax) is the guest-observed memory-to-memory form. The
         * source longword is read before the destination is checked/written,
         * so an odd destination retains both successful source reads. No
         * address register changes. PRM section 4 MOVE sets N/Z from the
         * longword, clears V/C and preserves X; UM Rev. 9.1 Table 8-3,
         * printed p. 8-3, gives 20(3/2). */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t source_address = cpu->address_registers[source_register];
        if ((source_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source_address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, source_address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source_address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t destination_address =
            cpu->address_registers[destination_register];
        if ((destination_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination_address, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = write_word(cpu, destination_address, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination_address + UINT32_C(2), value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, ((uint32_t)value_high << 16) | (uint32_t)value_low);
        *cycles = UINT64_C(20);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2098)) {
        /* MOVE.L (Ay)+,(Ax), reached by the selected guest. PRM §4 MOVE,
         * pp. 4-116–4-118, defines the long transfer and its N/Z, V/C and X
         * behavior; §2.2.4 p. 2-6 defines four-byte postincrement. UM Rev.
         * 9.1 Table 8-3 p. 8-3 gives 20(3/2). The manual does not state the
         * same-An alias or odd-read partial-update sequence. Match those
         * corners to pinned MAME 31e52312's x2098_move_l_pi_071234fc
         * (source postincrement before destination EA and attempted source
         * read); this is differential evidence, not a hardware bus-order
         * claim. Normal host read errors still defer the update until both
         * source words have been read. */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t source_address = cpu->address_registers[source_register];
        if ((source_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            write_address_register(cpu, source_register,
                                   source_address + UINT32_C(4));
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source_address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, source_address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source_address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, source_register,
                               source_address + UINT32_C(4));
        const uint32_t destination_address =
            cpu->address_registers[destination_register];
        if ((destination_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination_address, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = write_word(cpu, destination_address, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination_address + UINT32_C(2), value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, ((uint32_t)value_high << 16) | (uint32_t)value_low);
        *cycles = UINT64_C(20);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x20d8)) {
        /* MOVE.L (Ay)+,(Ax)+ (guest demanded, plan 05-02). Read and commit
         * the source postincrement before forming the destination address, so
         * Ax == Ay transfers to the next longword. A failed destination write
         * retains the completed source read/increment; destination increment
         * follows both successful word writes. PRM §2.2.4 defines the long
         * postincrement. UM Rev. 9.1 Table 8-3 p. 8-3 gives 20(3/2). */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t source_address = cpu->address_registers[source_register];
        if ((source_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source_address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, source_address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source_address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, source_register,
                               source_address + UINT32_C(4));
        const uint32_t destination_address =
            cpu->address_registers[destination_register];
        if ((destination_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination_address, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = write_word(cpu, destination_address, value_high);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination_address + UINT32_C(2), value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, destination_register,
                               destination_address + UINT32_C(4));
        set_move_flags(cpu, ((uint32_t)value_high << 16) | (uint32_t)value_low);
        *cycles = UINT64_C(20);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x10c0)) {
        /* MOVE.B Dn,(An)+: keep this observed data-register source and
         * postincrement destination form narrow (plan 05-27). */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination = cpu->address_registers[address_register];
        const uint8_t value = (uint8_t)cpu->data_registers[source_register];
        /* MOVE.B takes 8(1/1): opcode read and one byte write. The PRM MOVE
         * operation sets N/Z, clears V/C, and preserves X; §2.2.4 increments
         * A7 by two for byte postincrement to preserve stack alignment. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_byte(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(
            cpu, address_register,
            destination + (address_register == 7u ? UINT32_C(2) : UINT32_C(1)));
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x1100)) {
        /* MOVE.B Dn,-(An): UM Rev. 9.1 Table 8-2 p. 8-2 gives 8(1/1);
         * PRM §4 MOVE defines N/Z from the byte, V/C clear, X preserved.
         * Predecrement A7 by two for stack alignment (§2.2.4). */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t decrement = address_register == 7u
            ? UINT32_C(2) : UINT32_C(1);
        const uint32_t destination =
            cpu->address_registers[address_register] - decrement;
        const uint8_t value = (uint8_t)cpu->data_registers[source_register];
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, address_register, destination);
        status = write_byte(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2080)) {
        /* MOVE.L Dn,(An) is the selected guest's long store through an
         * address register. PRM MOVE pp. 4-116 to 4-118 sets N/Z from the
         * long, clears V/C and preserves X. MC68000 UM Rev. 9.1 Table 8-3
         * p. 8-3 gives Dn to (An) 12(1/2): one opcode read and two writes. */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination = cpu->address_registers[address_register];
        const uint32_t value = cpu->data_registers[source_register];
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, (uint16_t)(value >> 16));
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination + UINT32_C(2),
                                (uint16_t)value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, value);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2100)) {
        /* MOVE.L Dn,-(An). UM Rev. 9.1 Table 8-3 (printed p. 8-3) gives
         * 12(1/2); PRM §4 MOVE defines the operation/flags but not split-word
         * bus order. Match the selected pinned MAME differential handler
         * x2100_move_l_071234fc (commit 31e5231, m68kops.cpp:18866-18878):
         * low word to destination+2 first, then high word to destination.
         * Update An before writes; keep X, set N/Z, clear V/C. The pinned
         * differential evaluates the predecrement EA before the aligned-write
         * check, so an odd-address exception retains An-4. */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination =
            cpu->address_registers[address_register] - UINT32_C(4);
        const uint32_t value = cpu->data_registers[source_register];
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            write_address_register(cpu, address_register, destination);
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, address_register, destination);
        status = write_word(cpu, destination + UINT32_C(2),
                            (uint16_t)value);
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination,
                                (uint16_t)(value >> 16));
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_flags(cpu, value);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x20c0)) {
        /* MOVE.L Dn,(An)+ (plan 05-21, guest-observed). Other sources and
         * destination modes stay unsupported. M68000 Family PRM MOVE, pp.
         * 4-116 to 4-118: high word then low word, N/Z from the long, V/C
         * clear, X unaffected; the long postincrement is four, also for A7.
         * An odd destination takes the address-error exception with no write,
         * like MOVE.W Dn,(An)+. User's Manual Rev. 9.1 Table 8-3 (printed p.
         * 8-3): Dn to (An)+ long 12(1/2). */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination = cpu->address_registers[address_register];
        const uint32_t value = cpu->data_registers[source_register];
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, (uint16_t)(value >> 16));
        if (status == OWNED_CPU_OK)
            status = write_word(cpu, destination + UINT32_C(2), (uint16_t)value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, address_register, destination + UINT32_C(4));
        set_move_flags(cpu, value);
        *cycles = UINT64_C(12);
    } else if (subi_immediate_data_register_width(*opcode) != 0u) {
        /* SUBI.B/W/L #<data>,Dn. PRM section 4 SUBI, pp. 4-179 to 4-180,
         * defines subtraction flags and preserves the unselected upper Dn
         * bits for byte/word sizes. UM Rev. 9.1 Table 8-5 p. 8-5 gives
         * immediate-to-Dn timing as 8(2/0) for byte/word and 16(3/0) for
         * long. Acquire every extension word before preflight or mutation. */
        const unsigned width = subi_immediate_data_register_width(*opcode);
        uint32_t immediate = 0u;
        if (width == 4u) {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = fetch_word(cpu, &cursor, &high);
            if (status == OWNED_CPU_OK)
                status = fetch_word(cpu, &cursor, &low);
            immediate = ((uint32_t)high << 16) | (uint32_t)low;
        } else {
            uint16_t extension = 0u;
            status = fetch_word(cpu, &cursor, &extension);
            immediate = width == 1u
                ? (uint32_t)(extension & UINT16_C(0x00ff))
                : (uint32_t)extension;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t instruction_cycles =
            width == 4u ? UINT64_C(16) : UINT64_C(8);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;

        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint32_t destination_full =
            cpu->data_registers[destination_register];
        const uint32_t width_mask = width == 1u ? UINT32_C(0xff) :
                                    width == 2u ? UINT32_C(0xffff) :
                                                  UINT32_C(0xffffffff);
        uint16_t flags = 0u;
        const uint32_t result = addsub_value(
            cpu->sr, destination_full & width_mask, immediate, width, 1,
            &flags);
        cpu->data_registers[destination_register] =
            (destination_full & ~width_mask) | result;
        cpu->sr = flags;
        *cycles = instruction_cycles;
    } else if (addi_immediate_data_register_width(*opcode) != 0u) {
        /* ADDI.B/W/L #<data>,Dn. PRM §4 ADDI pp. 4-9 to 4-10 defines the
         * width-limited sum and X/N/Z/V/C; byte/word preserve the unselected
         * Dn upper bits. UM Rev. 9.1 Table 8-5 p. 8-5 gives 8(2/0) for
         * byte/word and 16(3/0) for long. Fetch every extension before
         * preflight or register/flag mutation. */
        const unsigned width = addi_immediate_data_register_width(*opcode);
        uint32_t immediate = 0u;
        if (width == 4u) {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = fetch_word(cpu, &cursor, &high);
            if (status == OWNED_CPU_OK)
                status = fetch_word(cpu, &cursor, &low);
            immediate = ((uint32_t)high << 16) | (uint32_t)low;
        } else {
            uint16_t extension = 0u;
            status = fetch_word(cpu, &cursor, &extension);
            immediate = width == 1u
                ? (uint32_t)(extension & UINT16_C(0x00ff))
                : (uint32_t)extension;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t instruction_cycles = width == 4u
            ? UINT64_C(16) : UINT64_C(8);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint32_t destination_full =
            cpu->data_registers[destination_register];
        const uint32_t width_mask = width == 1u ? UINT32_C(0xff) :
                                    width == 2u ? UINT32_C(0xffff) :
                                                  UINT32_MAX;
        uint16_t flags = 0u;
        const uint32_t result = addsub_value(
            cpu->sr, destination_full & width_mask, immediate, width, 0,
            &flags);
        cpu->data_registers[destination_register] =
            (destination_full & ~width_mask) | result;
        cpu->sr = flags;
        *cycles = instruction_cycles;
    } else if (immediate_arithmetic_memory_width(*opcode) != 0u) {
        /* ADDI/SUBI #imm,<data-alterable memory EA>. Share the concrete
         * byte/word/long destination sequence and the width-limited arithmetic
         * helper while retaining each operation's own opcode family. PRM §4
         * ADDI pp. 4-9 to 4-10 and SUBI pp. 4-179 to 4-180 define X/N/Z/V/C.
         * UM Rev. 9.1 Table 8-5 p. 8-5 gives byte/word 12(2/1)+ and long
         * 20(3/2)+; Table 8-1 p. 8-2 supplies EA clocks. Both fetch the
         * immediate before destination EA extensions. For odd word/long
         * auto-update vector-3 state, the generated pinned MAME SUBI word/long
         * PI/PD handlers evaluate EA updates before operand access; manuals do
         * not define that partial fault chronology. Terminal host callback
         * failures remain this core's separate read/write contract. */
        const unsigned width = immediate_arithmetic_memory_width(*opcode);
        const int subtract = (*opcode & UINT16_C(0xff00)) == UINT16_C(0x0400);
        uint32_t immediate = 0u;
        if (width == 4u) {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = fetch_word(cpu, &cursor, &high);
            if (status == OWNED_CPU_OK)
                status = fetch_word(cpu, &cursor, &low);
            immediate = ((uint32_t)high << 16) | (uint32_t)low;
        } else {
            uint16_t extension = 0u;
            status = fetch_word(cpu, &cursor, &extension);
            immediate = width == 1u ? (uint32_t)(extension & UINT16_C(0x00ff))
                                    : (uint32_t)extension;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t total_cycles =
            (width == 4u ? UINT64_C(20) : UINT64_C(12)) + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            /* Pinned MAME differential: the generated ADDI and SUBI handlers
             * resolve PI/PD EA macros before the operand read, so those
             * updates survive a guest vector-3 read fault. Manual sources
             * define the address error but not this partial-update chronology. */
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t before = 0u;
        if (width == 1u) {
            uint8_t value = 0u;
            status = read_byte(cpu, ea.address, &value);
            before = value;
        } else if (width == 2u) {
            uint16_t value = 0u;
            status = read_word(cpu, ea.address, &value);
            before = value;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            before = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint16_t flags = 0u;
        const uint32_t after = addsub_value(cpu->sr, before, immediate, width,
                                             subtract, &flags);
        if (width == 1u) {
            status = write_byte(cpu, ea.address, (uint8_t)after);
        } else if (width == 2u) {
            status = write_word(cpu, ea.address, (uint16_t)after);
        } else {
            status = write_word(cpu, ea.address, (uint16_t)(after >> 16));
            if (status == OWNED_CPU_OK)
                status = write_word(cpu, ea.address + UINT32_C(2), (uint16_t)after);
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        cpu->sr = flags;
        *cycles = total_cycles;
    } else if (immediate_logic_ccr_operation(*opcode) != 0u) {
        /* ORI/ANDI/EORI.B #<data>,CCR are special MC68000 immediate forms,
         * separate from general effective-address operations. The PRM's
         * instruction descriptions specify the operation on implemented CCR
         * bits only; preserve every upper SR bit. UM Rev. 9.1 Table 8-12,
         * printed p. 8-10, gives each form 20 clocks. This no-prefetch core
         * performs only the opcode and immediate-word callbacks. */
        uint16_t immediate = 0u;
        status = fetch_word(cpu, &cursor, &immediate);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;

        const uint16_t operation = (uint16_t)immediate_logic_ccr_operation(*opcode);
        const uint16_t current_flags =
            (uint16_t)(cpu->sr & SR_ARITHMETIC_FLAGS);
        const uint16_t source_flags =
            (uint16_t)(immediate & SR_ARITHMETIC_FLAGS);
        uint16_t updated_flags = 0u;
        if (operation == 1u) {
            updated_flags = (uint16_t)(current_flags | source_flags);
        } else if (operation == 2u) {
            updated_flags = (uint16_t)(current_flags & source_flags);
        } else {
            updated_flags = (uint16_t)(current_flags ^ source_flags);
        }
        cpu->sr = (uint16_t)((cpu->sr &
                              (uint16_t)~SR_ARITHMETIC_FLAGS) |
                             updated_flags);
        *cycles = UINT64_C(20);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x0040)) {
        /* ORI.W #<data>,Dn. PRM §4 ORI pp. 4-153 to 4-154 defines the
         * word-width inclusive OR and N/Z/V/C result; X is unaffected. UM
         * Rev. 9.1 Table 8-5 p. 8-5 specifies 8 clocks, 2 reads, no writes. */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint16_t result =
            (uint16_t)((uint16_t)cpu->data_registers[destination_register] | extension);
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & UINT32_C(0xffff0000)) |
            (uint32_t)result;
        set_move_word_flags(cpu, result);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x0000)) {
        /* ORI.B #<data>,Dn (plan 05-21, guest-observed). Memory and CCR
         * destinations (except the separate CCR special form) and the long
         * size stay unsupported; ORI.W Dn is decoded separately. PRM
         * section 4 ORI, pp. 4-152 to 4-153: the low byte of Dn is ORed with
         * the low byte of the extension word, Dn[31:8] preserved, N/Z from
         * the byte, V/C cleared, X unchanged. User's Manual Rev. 9.1 Table 8-5
         * (p. 8-5): ORI byte to Dn 8(2/0). */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint8_t result =
            (uint8_t)((uint8_t)cpu->data_registers[destination_register] | (uint8_t)extension);
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & UINT32_C(0xffffff00)) | result;
        set_move_byte_flags(cpu, result);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x0a00)) {
        /* EORI.B #<data>,Dn (plan 05-22, guest-observed). Memory and CCR
         * destinations and the word and long sizes stay unsupported. PRM
         * section 4 EORI, pp. 4-101 to 4-102: the low byte of Dn is
         * exclusive-ORed with the low byte of the extension word, Dn[31:8]
         * preserved, N/Z from the byte, V/C cleared, X unchanged. User's
         * Manual Rev. 9.1 Table 8-5 (p. 8-5): EORI byte to Dn 8(2/0). */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint8_t result =
            (uint8_t)((uint8_t)cpu->data_registers[destination_register] ^ (uint8_t)extension);
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & UINT32_C(0xffffff00)) | result;
        set_move_byte_flags(cpu, result);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x0100)) {
        /* BTST Dn,Dn is the observed dynamic, long-register form. The bit
         * number is modulo 32 and only Z changes; the destination is not
         * modified. PRM §4 BTST, pp. 4-60 to 4-63; MC68000 User's Manual
         * Rev. 9.1 Table 8-8 (printed p. 8-7): dynamic long BTST to Dn is
         * 6(1/0). Dynamic data-alterable memory bit operations are handled
         * below; unlisted addressing forms stay unsupported. */
        const unsigned bit_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const unsigned bit_number =
            (unsigned)(cpu->data_registers[bit_register] & UINT32_C(0x1f));
        const uint32_t bit_mask = UINT32_C(1) << bit_number;
        const uint32_t destination = cpu->data_registers[destination_register];
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(6), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_Z);
        if ((destination & bit_mask) == 0u) flags = (uint16_t)(flags | SR_Z);
        cpu->sr = flags;
        *cycles = UINT64_C(6);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x01c0)) {
        /* BSET Dm,Dn uses a long data-register destination and modulo-32 bit
         * numbering. Z reflects the old selected bit; X/N/V/C are preserved.
         * PRM §4 BSET, pp. 4-56 to 4-57, defines the operation and flags;
         * MC68000 UM Rev. 9.1 Table 8-8, printed p. 8-7, gives 8(1/0)* as a
         * maximum. This owned model charges that fixed eight-cycle bound. */
        const unsigned bit_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint32_t source = cpu->data_registers[bit_register];
        const uint32_t destination = cpu->data_registers[destination_register];
        const unsigned bit_number = (unsigned)(source & UINT32_C(0x1f));
        const uint32_t bit_mask = UINT32_C(1) << bit_number;
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cpu->data_registers[destination_register] = destination | bit_mask;
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_Z);
        if ((destination & bit_mask) == 0u) flags = (uint16_t)(flags | SR_Z);
        cpu->sr = flags;
        *cycles = UINT64_C(8);
    } else if (dynamic_bit_operation_data_alterable_memory(*opcode) >= 0) {
        /* Dynamic BTST/BCHG/BCLR/BSET to a data-alterable memory byte use the
         * same EA and RMW path. PRM §4 defines the register bit number modulo
         * eight and Z from the original bit; UM Rev. 9.1 Table 8-8 p. 8-7
         * gives BTST 4(1/0)+ and each modifying form 8(1/1)+. Table 8-1
         * p. 8-2 supplies the byte EA surcharge. Capture Dn before resolving
         * a possible indexed EA, then read the byte before any modifying write. */
        const unsigned operation = (unsigned)
            dynamic_bit_operation_data_alterable_memory(*opcode);
        const unsigned bit_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned bit_number =
            (unsigned)(cpu->data_registers[bit_register] & UINT32_C(7));
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor, 1u,
                                                   &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t base_cycles = operation == 0u
            ? UINT64_C(4) : UINT64_C(8);
        const uint64_t total_cycles = base_cycles + ea.address_cycles;
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        uint8_t destination = 0u;
        status = read_byte(cpu, ea.address, &destination);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        const uint8_t bit_mask = (uint8_t)(UINT8_C(1) << bit_number);
        uint8_t result = destination;
        if (operation == 1u) result = (uint8_t)(destination ^ bit_mask);
        else if (operation == 2u)
            result = (uint8_t)(destination & (uint8_t)~bit_mask);
        else if (operation == 3u)
            result = (uint8_t)(destination | bit_mask);
        if (operation != 0u) {
            status = write_byte(cpu, ea.address, result);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
        }
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_Z);
        if ((destination & bit_mask) == 0u)
            flags = (uint16_t)(flags | SR_Z);
        cpu->sr = flags;
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x0800)) {
        /* BTST #<data>,Dn (guest demanded, plan 05-27). This admits the
         * static-bit, data-register destination form; dynamic BTST data-
         * alterable memory is handled separately, while unlisted destinations
         * and dynamic register-destination modifies remain unsupported. PRM BTST
         * p. 4-60: Dn is long, the immediate bit number is modulo 32, and only
         * Z changes. User's Manual Rev. 9.1 Table 8-4 (p. 8-4): static BTST
         * long to Dn is 10(2/0). The core fetches opcode plus extension word. */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(10), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const unsigned bit_number = (unsigned)(extension & UINT16_C(0x001f));
        const uint32_t mask = UINT32_C(1) << bit_number;
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_Z);
        if ((cpu->data_registers[destination_register] & mask) == 0u) {
            flags = (uint16_t)(flags | SR_Z);
        }
        cpu->sr = flags;
        *cycles = UINT64_C(10);
    } else if (static_bit_modify_data_register_operation(*opcode) != 0u) {
        /* Static BCLR/BSET to Dn use a long register operand; bit numbers wrap
         * modulo 32, Z reflects the old bit, and X/N/V/C are preserved (PRM
         * §4 BCLR pp. 4-30 to 4-33 and BSET pp. 4-55 to 4-56). UM Rev. 9.1
         * Table 8-8 p. 8-7 gives 14(2/0) for BCLR and 12(2/0) for BSET. */
        uint16_t bit_extension = 0u;
        status = fetch_word(cpu, &cursor, &bit_extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned operation =
            static_bit_modify_data_register_operation(*opcode);
        const uint64_t instruction_cycles = operation == 3u
            ? UINT64_C(12) : UINT64_C(14);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const unsigned bit_number = (unsigned)(bit_extension & UINT16_C(0x001f));
        const uint32_t mask = UINT32_C(1) << bit_number;
        const uint32_t before = cpu->data_registers[destination_register];
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_Z);
        if ((before & mask) == 0u) flags = (uint16_t)(flags | SR_Z);
        cpu->data_registers[destination_register] = operation == 3u
            ? before | mask : before & ~mask;
        cpu->sr = flags;
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x0828)) {
        /* BTST #<data>,(d16,An) is the observed static byte-memory form.
         * Motorola PRM §4 BTST, pp. 4-61–4-63: memory bit numbers wrap
         * modulo eight and only Z changes according to the old bit. UM Rev.
         * 9.1 Table 8-8 p. 8-7 gives 8(2/0)+; Table 8-1 p. 8-2 adds
         * 8(2/0) for (d16,An), totaling 16 clocks. */
        uint16_t bit_extension = 0u;
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &bit_extension);
        if (status == OWNED_CPU_OK)
            status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const uint32_t address = cpu->address_registers[base_register] +
            sign_extend_word(encoded_displacement);
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t operand = 0u;
        status = read_byte(cpu, address, &operand);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint8_t bit_mask = (uint8_t)(UINT8_C(1) <<
            (unsigned)(bit_extension & UINT16_C(7)));
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_Z);
        if ((operand & bit_mask) == 0u) flags = (uint16_t)(flags | SR_Z);
        cpu->sr = flags;
        *cycles = UINT64_C(16);
    } else if (*opcode == UINT16_C(0x0839)) {
        /* BTST #<data>,(xxx).L (guest demanded, plan 05-02). This admits only
         * the static bit-test absolute-long byte source. PRM section 4 BTST,
         * pp. 4-61 to 4-63, defines modulo-eight memory bit numbers and says
         * only Z changes. UM Rev. 9.1 Table 8-8 p. 8-7 gives static BTST
         * memory 8(2/0)+; Table 8-1 p. 8-2 adds 12(3/0) for (xxx).L, totaling
         * 20(5/0). Byte access allows odd addresses. */
        uint16_t bit_extension = 0u;
        uint16_t address_high = 0u;
        uint16_t address_low = 0u;
        status = fetch_word(cpu, &cursor, &bit_extension);
        if (status == OWNED_CPU_OK)
            status = fetch_word(cpu, &cursor, &address_high);
        if (status == OWNED_CPU_OK)
            status = fetch_word(cpu, &cursor, &address_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t address = ((uint32_t)address_high << 16) | address_low;
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t operand = 0u;
        status = read_byte(cpu, address, &operand);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint8_t bit_mask = (uint8_t)(UINT8_C(1) <<
            (unsigned)(bit_extension & UINT16_C(7)));
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_Z);
        if ((operand & bit_mask) == 0u)
            flags = (uint16_t)(flags | SR_Z);
        cpu->sr = flags;
        *cycles = UINT64_C(20);
    } else if (is_static_bit_modify_data_alterable_memory(*opcode) != 0) {
        /* Static BCHG/BCLR/BSET to a data-alterable memory byte. NXP/Motorola
         * PRM §4 defines modulo-eight bit selection, Z from the old bit and
         * the old bit, and preserve X/N/V/C; bit number and EA extensions are
         * fetched in that order. UM Rev. 9.1 Table 8-8 p. 8-7 gives a static
         * memory base of 12(2/1)+; Table 8-1 p. 8-2 supplies byte EA timing.
         * Thus the admitted forms cost 16/16/18/20/22/20/24 clocks. The
         * shared resolver commits predecrement before the operand read and
         * postincrement after a successful read, matching other core RMW EAs;
         * fault chronology is an owned-core policy, not a hardware claim. */
        uint16_t bit_extension = 0u;
        const uint16_t destination_ea =
            (uint16_t)(*opcode & UINT16_C(0x003f));
        status = fetch_word(cpu, &cursor, &bit_extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, destination_ea,
                                                   &cursor, 1u, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t total_cycles = UINT64_C(12) + ea.address_cycles;
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        uint8_t before = 0u;
        status = read_byte(cpu, ea.address, &before);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        const uint8_t bit_mask =
            (uint8_t)(UINT8_C(1) << (unsigned)(bit_extension & UINT16_C(7)));
        const unsigned operation = (unsigned)((*opcode >> 6) & 3u);
        const uint8_t after = operation == 1u
            ? (uint8_t)(before ^ bit_mask)
            : operation == 2u
                ? (uint8_t)(before & (uint8_t)~bit_mask)
                : (uint8_t)(before | bit_mask);
        status = write_byte(cpu, ea.address, after);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_Z);
        if ((before & bit_mask) == 0u) flags = (uint16_t)(flags | SR_Z);
        cpu->sr = flags;
        *cycles = total_cycles;
    } else if (logical_immediate_data_alterable_memory_width(*opcode) != 0u) {
        /* ORI/ANDI/EORI immediate operations share the seven documented
         * data-alterable memory EAs. The immediate extension precedes EA
         * extensions. UM Rev. 9.1 Table 8-5 p. 8-5 supplies the 12-cycle
         * byte/word and 20-cycle long bases; Table 8-1 p. 8-2 supplies the
         * width-specific EA time. CCR/SR special encodings, Dn, PC-relative,
         * immediate and address-register forms stay outside this decoder. */
        const unsigned width =
            logical_immediate_data_alterable_memory_width(*opcode);
        uint16_t immediate_high = 0u;
        uint16_t immediate_low = 0u;
        status = fetch_word(cpu, &cursor, &immediate_high);
        if (status == OWNED_CPU_OK && width == 4u)
            status = fetch_word(cpu, &cursor, &immediate_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t immediate = width == 4u
            ? ((uint32_t)immediate_high << 16) | (uint32_t)immediate_low
            : (uint32_t)immediate_high;
        const uint16_t destination_ea =
            (uint16_t)(*opcode & UINT16_C(0x003f));
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, destination_ea,
                                                   &cursor, width, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t total_cycles =
            (width == 4u ? UINT64_C(20) : UINT64_C(12)) + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            /* Pinned MAME revision 31e52312 calls EA_AY_PI/PD_16/32 before
             * the operand read in x0258_andi_w_pi_071234fc,
             * x0260_andi_w_pd_071234fc, x0298_andi_l_pi_071234fc, and
             * x02a0_andi_l_pd_071234fc; those macros update An before vector
             * 3. This is emulator-differential evidence only; manuals specify
             * the exception but not this partial-update chronology. */
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t before = 0u;
        if (width == 1u) {
            uint8_t value = 0u;
            status = read_byte(cpu, ea.address, &value);
            before = value;
        } else if (width == 2u) {
            uint16_t value = 0u;
            status = read_word(cpu, ea.address, &value);
            before = value;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            before = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        const uint32_t mask = width == 4u ? UINT32_MAX :
            (UINT32_C(1) << (width * 8u)) - UINT32_C(1);
        const uint16_t operation = (uint16_t)(*opcode & UINT16_C(0x0f00));
        const uint32_t logical_result = operation == UINT16_C(0x0000)
            ? before | immediate
            : operation == UINT16_C(0x0200) ? before & immediate
            : before ^ immediate;
        const uint32_t result = logical_result & mask;
        if (width == 1u) {
            status = write_byte(cpu, ea.address, (uint8_t)result);
        } else if (width == 2u) {
            status = write_word(cpu, ea.address, (uint16_t)result);
        } else {
            status = write_word(cpu, ea.address, (uint16_t)(result >> 16));
            if (status == OWNED_CPU_OK)
                status = write_word(cpu, ea.address + UINT32_C(2),
                                    (uint16_t)result);
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (width == 1u) set_move_byte_flags(cpu, (uint8_t)result);
        else if (width == 2u) set_move_word_flags(cpu, (uint16_t)result);
        else set_move_flags(cpu, result);
        *cycles = total_cycles;
    } else if (andi_immediate_data_register_width(*opcode) != 0u) {
        /* ANDI.B/W/L #<data>,Dn share width-limited operand, upper-bit and
         * flag handling. Acquire both long immediate words before timing
         * preflight, then commit the destination and CCR atomically. PRM §4
         * ANDI pp. 4-18–4-19 defines the operation; UM Rev. 9.1 Table 8-5
         * p. 8-5 gives byte/word 8(2/0) and long 14(3/0). */
        const unsigned width = andi_immediate_data_register_width(*opcode);
        uint16_t immediate_high = 0u;
        uint16_t immediate_low = 0u;
        status = fetch_word(cpu, &cursor, &immediate_high);
        if (status == OWNED_CPU_OK && width == 4u)
            status = fetch_word(cpu, &cursor, &immediate_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t immediate = width == 4u
            ? ((uint32_t)immediate_high << 16) | (uint32_t)immediate_low
            : (uint32_t)immediate_high;
        const uint64_t instruction_cycles = width == 4u
            ? UINT64_C(14) : UINT64_C(8);
        status = preflight_event(cpu, STEP_INSTRUCTION,
                                 instruction_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint32_t before = cpu->data_registers[destination_register];
        const uint32_t mask = width == 1u ? UINT32_C(0xff) :
            width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
        const uint32_t result = before & immediate & mask;
        cpu->data_registers[destination_register] =
            (before & ~mask) | result;
        if (width == 1u) set_move_byte_flags(cpu, (uint8_t)result);
        else if (width == 2u) set_move_word_flags(cpu, (uint16_t)result);
        else set_move_flags(cpu, result);
        *cycles = instruction_cycles;
    } else if (or_data_alterable_memory_source_width(*opcode) != 0u) {
        /* OR byte/word/long data-alterable memory source to Dn shares the
         * seven legal source EAs. UM Rev. 9.1 Table 8-4 p. 8-4 gives base
         * 4(1/0)+ for byte/word and 6(1/0)+ for long; Table 8-1 p. 8-2
         * supplies width-specific EA cost. PRM §4 OR pp. 4-150 to 4-151
         * defines low-width Dn updates, N/Z, cleared V/C, and preserved X.
         */
        const unsigned width = or_data_alterable_memory_source_width(*opcode);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t base_cycles = width == 4u ? UINT64_C(6) : UINT64_C(4);
        const uint64_t total_cycles = base_cycles + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t source = 0u;
        if (width == 1u) {
            uint8_t value = 0u;
            status = read_byte(cpu, ea.address, &value);
            source = value;
        } else if (width == 2u) {
            uint16_t value = 0u;
            status = read_word(cpu, ea.address, &value);
            source = value;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            source = ((uint32_t)high << 16) | low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        const unsigned destination_register =
            (unsigned)((*opcode >> 9) & UINT16_C(7));
        if (width == 1u) {
            const uint8_t result = (uint8_t)cpu->data_registers[destination_register] |
                                   (uint8_t)source;
            cpu->data_registers[destination_register] =
                (cpu->data_registers[destination_register] & UINT32_C(0xffffff00)) |
                (uint32_t)result;
            set_move_byte_flags(cpu, result);
        } else if (width == 2u) {
            const uint16_t result = (uint16_t)cpu->data_registers[destination_register] |
                                    (uint16_t)source;
            cpu->data_registers[destination_register] =
                (cpu->data_registers[destination_register] & UINT32_C(0xffff0000)) |
                (uint32_t)result;
            set_move_word_flags(cpu, result);
        } else {
            const uint32_t result = cpu->data_registers[destination_register] | source;
            cpu->data_registers[destination_register] = result;
            set_move_flags(cpu, result);
        }
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xc100)) {
        /* ABCD.B Dm,Dn (guest observed, plan 06-02). The exact register-direct
         * mask leaves the overlapping predecrement-memory form unsupported.
         * The M68000 Family PRM §4 ABCD, pp. 4-2 to 4-3, defines packed-BCD
         * destination + source + X, decimal C/X carry and sticky Z; N/V are
         * undefined. This deterministic subset preserves those undefined
         * incoming bits without claiming their hardware values, and qualifies
         * only valid packed-BCD digits. MC68000 UM Rev. 9.1 §8.10 Table 8-11
         * (printed p. 8-9) gives the register form as 6(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(6), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)(*opcode & UINT16_C(7));
        const unsigned destination_register = (unsigned)((*opcode >> 9) & UINT16_C(7));
        const uint8_t source = (uint8_t)cpu->data_registers[source_register];
        const uint32_t original_destination =
            cpu->data_registers[destination_register];
        const uint8_t destination = (uint8_t)original_destination;
        const int extend_in = (cpu->sr & SR_X) != 0u ? 1 : 0;
        const int low_sum = (int)(destination & UINT8_C(0x0f)) +
            (int)(source & UINT8_C(0x0f)) + extend_in;
        const int low_carry = low_sum > 9 ? 1 : 0;
        const int corrected_low = low_sum + (low_carry != 0 ? 6 : 0);
        const int high_sum = (int)(destination >> 4) + (int)(source >> 4) +
            low_carry;
        const int decimal_carry = high_sum > 9 ? 1 : 0;
        const int corrected_high = high_sum + (decimal_carry != 0 ? 6 : 0);
        const uint8_t result = (uint8_t)(
            ((unsigned)corrected_high & 15u) << 4 |
            ((unsigned)corrected_low & 15u));
        cpu->data_registers[destination_register] =
            (original_destination & UINT32_C(0xffffff00)) | (uint32_t)result;
        uint16_t new_sr = (uint16_t)(cpu->sr &
            (uint16_t)~(SR_X | SR_Z | SR_C));
        if (decimal_carry != 0) new_sr = (uint16_t)(new_sr | SR_X | SR_C);
        if ((cpu->sr & SR_Z) != 0u && result == 0u)
            new_sr = (uint16_t)(new_sr | SR_Z);
        cpu->sr = new_sr;
        *cycles = UINT64_C(6);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x8100)) {
        /* SBCD.B Dm,Dn (guest demanded, bounded register form). The exact
         * mask excludes the overlapping -(Ay),-(Ax) form (bit 3 set), which
         * remains unsupported. PRM section 4 SBCD, pp. 4-169 to 4-170,
         * defines packed-decimal destination-source-X, C/X borrow and sticky
         * Z; N and V are undefined. We leave those two undefined bits
         * unchanged as a deterministic owned-core choice, not a hardware
         * claim. Valid packed-decimal digits are required by this contract.
         * UM Rev. 9.1 Chapter 8 Table 8-11 (printed p. 8-9) gives register
         * SBCD 6(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(6), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)(*opcode & UINT16_C(7));
        const unsigned destination_register = (unsigned)((*opcode >> 9) & UINT16_C(7));
        const uint8_t source = (uint8_t)cpu->data_registers[source_register];
        const uint32_t original_destination =
            cpu->data_registers[destination_register];
        const uint8_t destination = (uint8_t)original_destination;
        const int extend_in = (cpu->sr & SR_X) != 0u ? 1 : 0;
        const int low_difference = (int)(destination & UINT8_C(0x0f)) -
            (int)(source & UINT8_C(0x0f)) - extend_in;
        const int low_borrow = low_difference < 0 ? 1 : 0;
        const int corrected_low = low_difference - (low_borrow != 0 ? 6 : 0);
        const unsigned low_digit = (unsigned)(corrected_low + 16) & 15u;
        const int high_difference = (int)(destination >> 4) -
            (int)(source >> 4) - low_borrow;
        const int decimal_borrow = high_difference < 0 ? 1 : 0;
        const int corrected_high = high_difference -
            (decimal_borrow != 0 ? 6 : 0);
        const unsigned high_digit = (unsigned)(corrected_high + 16) & 15u;
        const uint8_t result = (uint8_t)((high_digit << 4) | low_digit);
        cpu->data_registers[destination_register] =
            (original_destination & UINT32_C(0xffffff00)) | (uint32_t)result;
        uint16_t new_sr = (uint16_t)(cpu->sr &
            (uint16_t)~(SR_X | SR_Z | SR_C));
        if (decimal_borrow != 0) new_sr = (uint16_t)(new_sr | SR_X | SR_C);
        if ((cpu->sr & SR_Z) != 0u && result == 0u)
            new_sr = (uint16_t)(new_sr | SR_Z);
        cpu->sr = new_sr;
        *cycles = UINT64_C(6);
    } else if (or_data_register_width(*opcode) != 0u) {
        /* OR.B/W/L Dm,Dn (guest demanded/observed, plans 05-27/05-20). The
         * MC68000 PRM §4 OR, pp. 4-150–4-151, defines source OR destination,
         * N/Z from the selected-width result, V/C clear and X unchanged.
         * UM Rev. 9.1 Table 8-4 (p. 8-4) gives 4 clocks for byte/word
         * op<ea>,Dn and 6+ for long; its register-direct long footnote raises
         * that form to 8. Memory sources use the shared EA resolver above.
         * The width helper admits only Dn-direct sources, direction 0, and
         * opmodes 000/001/010; DIVU and SBCD are decoded separately. */
        const unsigned width = or_data_register_width(*opcode);
        const uint64_t total_cycles = width == 4u ? UINT64_C(8) : UINT64_C(4);
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t original_destination =
            cpu->data_registers[destination_register];
        if (width == 1u) {
            const uint8_t result =
                (uint8_t)original_destination |
                (uint8_t)cpu->data_registers[source_register];
            cpu->data_registers[destination_register] =
                (original_destination & UINT32_C(0xffffff00)) | (uint32_t)result;
            set_move_byte_flags(cpu, result);
        } else if (width == 2u) {
            const uint16_t result = (uint16_t)(original_destination |
                cpu->data_registers[source_register]);
            cpu->data_registers[destination_register] =
                (original_destination & UINT32_C(0xffff0000)) | (uint32_t)result;
            set_move_word_flags(cpu, result);
        } else {
            const uint32_t result = original_destination |
                cpu->data_registers[source_register];
            cpu->data_registers[destination_register] = result;
            set_move_flags(cpu, result);
        }
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x0c40)) {
        /* CMPI.W #<data>,Dn (guest demanded, plan 05-02). Long size and
         * memory destinations remain unsupported. PRM §4 CMPI pp. 4-79 to
         * 4-80 specifies low-word Dn minus immediate data, N/Z/V/C updates,
         * X unchanged and Dn not written. UM Rev. 9.1 Table 8-5 p. 8-5 gives
         * 8(2/0): opcode plus immediate extension, with no operand bus access. */
        uint16_t source = 0u;
        status = fetch_word(cpu, &cursor, &source);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint16_t destination =
            (uint16_t)cpu->data_registers[destination_register];
        const uint16_t difference = (uint16_t)(destination - source);
        uint16_t flags = (uint16_t)(cpu->sr &
            (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if (difference == 0u) flags = (uint16_t)(flags | SR_Z);
        if ((difference & UINT16_C(0x8000)) != 0u)
            flags = (uint16_t)(flags | SR_N);
        if (((destination ^ source) & (destination ^ difference) &
             UINT16_C(0x8000)) != 0u) flags = (uint16_t)(flags | SR_V);
        if (destination < source) flags = (uint16_t)(flags | SR_C);
        cpu->sr = flags;
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x0c80)) {
        /* CMPI.L #<data>,Dn (guest-observed). PRM §4 CMPI, pp. 4-79 to
         * 4-80, defines destination minus immediate, N/Z/V/C from the long
         * result, X unchanged, and no destination write. MC68000 UM Rev. 9.1
         * Chapter 8 Table 8-5 p. 8-5 gives 14(3/0): opcode and two immediate
         * word reads. */
        uint16_t immediate_high = 0u;
        uint16_t immediate_low = 0u;
        status = fetch_word(cpu, &cursor, &immediate_high);
        if (status == OWNED_CPU_OK)
            status = fetch_word(cpu, &cursor, &immediate_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(14), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)(*opcode & 7u);
        const uint32_t source = ((uint32_t)immediate_high << 16) |
                                (uint32_t)immediate_low;
        const uint32_t destination =
            cpu->data_registers[destination_register];
        const uint32_t difference = destination - source;
        uint16_t flags = (uint16_t)(cpu->sr &
            (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if (difference == 0u) flags = (uint16_t)(flags | SR_Z);
        if ((difference & UINT32_C(0x80000000)) != 0u)
            flags = (uint16_t)(flags | SR_N);
        if (((destination ^ source) & (destination ^ difference) &
             UINT32_C(0x80000000)) != 0u)
            flags = (uint16_t)(flags | SR_V);
        if (destination < source) flags = (uint16_t)(flags | SR_C);
        cpu->sr = flags;
        *cycles = UINT64_C(14);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x0c00)) {
        /* CMPI.B #<data>,Dn (guest demanded, plan 05-11). Word and long sizes
         * and every memory destination stay unsupported. The immediate byte is
         * the low byte of the extension word. Operation and condition codes:
         * PRM section 4 CMPI, pp. 4-79 to 4-80 (Dn byte minus data; X
         * unchanged; Dn not written). Timing: User's Manual Rev. 9.1 Table
         * 8-5 (printed p. 8-5) CMPI byte to Dn: 8(2/0). */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint8_t source = (uint8_t)extension;
        const uint8_t destination = (uint8_t)cpu->data_registers[*opcode & 7u];
        const uint8_t difference = (uint8_t)(destination - source);
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if (difference == 0u) flags = (uint16_t)(flags | SR_Z);
        if ((difference & UINT8_C(0x80)) != 0u) flags = (uint16_t)(flags | SR_N);
        if (((destination ^ source) & (destination ^ difference) & UINT8_C(0x80)) != 0u)
            flags = (uint16_t)(flags | SR_V);
        if (destination < source) flags = (uint16_t)(flags | SR_C);
        cpu->sr = flags;
        *cycles = UINT64_C(8);
    } else if (is_word_memory_shift_destination(*opcode) != 0) {
        /* ASR.W and LSR.W <data-alterable memory> shift one bit. Other memory
         * shifts/rotates stay unsupported; register results use separate
         * width/count decoders below. */
        status = execute_word_memory_shift(cpu, instruction_pc, *opcode,
                                           &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if ((*opcode & UINT16_C(0xf138)) == UINT16_C(0xe000) ||
               (*opcode & UINT16_C(0xf138)) == UINT16_C(0xe020)) {
        /* ASR.{B,W,L} #<1..8>/Dn,Dn. Register results admit immediate-count
         * (field zero means eight) and Dn-count forms (low six count bits).
         * ASR sign-fills from the operand MSB; C/X take the last bit shifted
         * out for nonzero counts, X is unchanged and C clears at count zero,
         * V clears, and N/Z follow the result. PRM §4 ASL/ASR pp. 4-20–4-22;
         * MC68000 UM Rev. 9.1 Table 8-7 p. 8-6 gives 6+2n byte/word and
         * 8+2n long clocks. Word memory shifts and non-data-register EAs
         * remain outside this register-result path. */
        const unsigned size = (unsigned)((*opcode >> 6) & 3u);
        if (size == 3u) return OWNED_CPU_UNSUPPORTED_OPCODE;
        const unsigned width = size == 0u ? 1u : size == 1u ? 2u : 4u;
        unsigned count;
        if ((*opcode & UINT16_C(0x0020)) != 0u) {
            count = (unsigned)(cpu->data_registers[(*opcode >> 9) & 7u] &
                               UINT32_C(0x3f));
        } else {
            count = (unsigned)((*opcode >> 9) & 7u);
            if (count == 0u) count = 8u;
        }
        const uint64_t base_cycles = width == 4u ? UINT64_C(8) : UINT64_C(6);
        const uint64_t shift_cycles = base_cycles + (uint64_t)(2u * count);
        status = preflight_event(cpu, STEP_INSTRUCTION, shift_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        arithmetic_shift_right_data_register(cpu, (unsigned)(*opcode & 7u),
                                             width, count);
        *cycles = shift_cycles;
    } else if ((*opcode & UINT16_C(0xf138)) == UINT16_C(0xe008)) {
        /* LSR.{B,W,L} #<1..8>,Dn. The MC68000 immediate-count form supports
         * byte, word and long data-register operands; dynamic counts, memory
         * forms and other shift/rotate operations remain outside this decoder.
         * PRM §4 LSL/LSR pp. 4-113 to 4-115 defines zero fill, X/C from the
         * last shifted bit, N clear, Z from the result, and V clear. UM Rev.
         * 9.1 Table 8-7 p. 8-6 gives 6+2n clocks for byte/word and 8+2n long. */
        const unsigned size = (unsigned)((*opcode >> 6) & 3u);
        if (size == 3u) return OWNED_CPU_UNSUPPORTED_OPCODE;
        const unsigned width = size == 0u ? 1u : size == 1u ? 2u : 4u;
        unsigned count = (unsigned)((*opcode >> 9) & 7u);
        if (count == 0u) count = 8u;
        const uint64_t base_cycles = width == 4u ? UINT64_C(8) : UINT64_C(6);
        const uint64_t shift_cycles = base_cycles + (uint64_t)(2u * count);
        status = preflight_event(cpu, STEP_INSTRUCTION, shift_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        logical_shift_right_data_register(cpu, (unsigned)(*opcode & 7u),
                                          width, count);
        *cycles = shift_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xe108) ||
               (*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xe148) ||
               (*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xe188)) {
        /* LSL.{B,W,L} #<1..8>,Dn. The family shares zero-fill and condition
         * code behavior: X/C receive the last bit shifted out, N/Z reflect
         * the selected width, V clears, and the count field zero means eight.
         * PRM §4 LSL pp. 4-113 to 4-115 defines operation/flags; UM Rev. 9.1
         * Table 8-7 p. 8-6 gives byte/word 6+2n and long 8+2n (1/0). */
        const unsigned size = (unsigned)((*opcode >> 6) & 3u);
        const unsigned width = size == 0u ? 1u : size == 1u ? 2u : 4u;
        unsigned count = (unsigned)((*opcode >> 9) & 7u);
        if (count == 0u) count = 8u;
        const uint64_t base_cycles = width == 4u ? UINT64_C(8) : UINT64_C(6);
        const uint64_t shift_cycles = base_cycles + (uint64_t)(2u * count);
        status = preflight_event(cpu, STEP_INSTRUCTION, shift_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        logical_shift_left_data_register(cpu, (unsigned)(*opcode & 7u),
                                         width, count);
        *cycles = shift_cycles;
    } else if (rotate_immediate_data_register_width(*opcode) != 0u) {
        /* ROL/ROR.{B,W,L} #<1..8>,Dn. Rotates do not include X: N/Z follow
         * the selected width, V clears, C receives the last bit rotated out,
         * and X is unchanged. PRM §4 ROL/ROR pp. 4-160 to 4-162 defines the
         * operation and count-field zero as eight; UM Rev. 9.1 Table 8-7 p.
         * 8-6 gives 6+2n clocks for byte/word and 8+2n for long. */
        const unsigned width = rotate_immediate_data_register_width(*opcode);
        unsigned count = (unsigned)((*opcode >> 9) & 7u);
        if (count == 0u) count = 8u;
        const uint64_t base_cycles = width == 4u ? UINT64_C(8) : UINT64_C(6);
        const uint64_t rotate_cycles = base_cycles + (uint64_t)(2u * count);
        status = preflight_event(cpu, STEP_INSTRUCTION, rotate_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned reg = (unsigned)(*opcode & 7u);
        rotate_data_register(cpu, reg, width, count,
                             (*opcode & UINT16_C(0x0100)) != 0u);
        *cycles = rotate_cycles;
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x103b)) {
        /* MOVE.B (d8,PC,Xn),Dn (05-27 rerun 39). PRM §2.2.12 p. 2-14:
         * PC is the extension-word address; the brief displacement and word
         * index are sign extended. PRM MOVE pp. 4-116 to 4-118 sets N/Z from
         * the byte, clears V/C, and preserves X. UM Rev. 9.1 Table 8-2
         * (printed p. 8-2): (d8,PC,Xn) source to Dn is 14(3/0). */
        const uint32_t extension_address = cursor;
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t address = extension_address +
                                 sign_extend_byte((uint8_t)extension) + index;
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(14), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint8_t value = 0u;
        status = read_byte(cpu, address, &value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned data_register = (unsigned)((*opcode >> 9) & 7u);
        cpu->data_registers[data_register] =
            (cpu->data_registers[data_register] & UINT32_C(0xffffff00)) | (uint32_t)value;
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~(SR_N | SR_Z | SR_V | SR_C));
        if (value == 0u) flags = (uint16_t)(flags | SR_Z);
        if ((value & UINT8_C(0x80)) != 0u) flags = (uint16_t)(flags | SR_N);
        cpu->sr = flags;
        *cycles = UINT64_C(14);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2068)) {
        /* MOVEA.L (d16,An),An (guest demanded, plan 05-02). The PRM §2.2.5
         * address displacement is signed and added to the old base value;
         * MOVEA §4 loads the full longword without changing condition codes.
         * UM Rev. 9.1 Table 8-3 p. 8-3 gives 16(4/0). */
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t address = cpu->address_registers[source_register] +
            sign_extend_word(encoded_displacement);
        if ((address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = read_word(cpu, address, &high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, address + UINT32_C(2), &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, destination_register,
                               ((uint32_t)high << 16) | (uint32_t)low);
        *cycles = UINT64_C(16);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2060)) {
        /* MOVEA.L -(An),An: the PRM defines long predecrement as An-4 before
         * the operand EA is used and MOVEA as a full-width load that preserves
         * condition codes (§2.2.5 and §4, pp. 2-7 and 4-119–4-120). UM Rev. 9.1
         * Table 8-3 p. 8-3 gives 14(3/0). Compute from the original base so
         * source/destination aliasing reads the predecremented memory value;
         * commit the source update before operand access, including an odd-EA
         * vector-3 path, while counter preflight remains atomic. */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t address =
            cpu->address_registers[source_register] - UINT32_C(4);
        if ((address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            write_address_register(cpu, source_register, address);
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(14), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, source_register, address);
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, destination_register,
                               ((uint32_t)value_high << 16) | value_low);
        *cycles = UINT64_C(14);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2050)) {
        /* MOVEA.L (An),An (guest demanded, plan 05-02). PRM §4 MOVEA,
         * pp. 4-119 to 4-120 loads the full longword without changing flags.
         * UM Rev. 9.1 Table 8-3 p. 8-3 gives (An) long source to An 12(3/0).
         * Compute the source before writing An so source/destination aliasing
         * reads the old address register. */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const uint32_t address = cpu->address_registers[source_register];
        if ((address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, (unsigned)((*opcode >> 9) & 7u),
                               ((uint32_t)value_high << 16) | (uint32_t)value_low);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x2078)) {
        /* MOVEA.L (xxx).W,An (guest demanded). Only the absolute-short source
         * is admitted here; the longword address is sign-extended, odd source
         * addresses take the MC68000 address-error path, and flags are intact.
         * PRM §2.2.10 absolute short and §4 MOVEA, pp. 4-119–4-120; UM Rev. 9.1
         * Table 8-3 (printed p. 8-3) supplies the MOVE.L absolute-short timing. */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t address = sign_extend_word(extension);
        if ((address & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, (*opcode >> 9) & 7u,
                               ((uint32_t)value_high << 16) | (uint32_t)value_low);
        *cycles = UINT64_C(16);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x2079)) {
        /* MOVEA.L (xxx).L,An: fetch the full absolute-long source address,
         * then load the full operand into An without changing condition codes.
         * PRM §2.2.17 p. 2-18 and §4 MOVEA, pp. 4-119–4-120; UM Rev. 9.1
         * Table 8-3 p. 8-3 gives 20(3/2) for absolute-long source to An. */
        uint16_t address_high = 0u;
        uint16_t address_low = 0u;
        status = fetch_word(cpu, &cursor, &address_high);
        if (status == OWNED_CPU_OK)
            status = fetch_word(cpu, &cursor, &address_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t address = ((uint32_t)address_high << 16) |
                                 (uint32_t)address_low;
        if ((address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(20), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, (*opcode >> 9) & 7u,
                               ((uint32_t)value_high << 16) | (uint32_t)value_low);
        *cycles = UINT64_C(20);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2070)) {
        /* MOVEA.L (d8,An,Xn),An (guest demanded, plan 05-02). The PRM
         * §2.2.7 EA is An + sign-extended d8 + the sized, sign-extended
         * index. Only the MC68000 brief extension is admitted; bits 10-8
         * reject scale/full-format variants. MOVEA loads the full longword
         * and leaves flags unchanged (PRM §4 MOVEA, pp. 4-119 to 4-120).
         * UM Rev. 9.1 Table 8-3 p. 8-3 gives indexed-long source to An
         * 18(4/0). */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t address = cpu->address_registers[base_register] +
                                 sign_extend_byte((uint8_t)extension) +
                                 index;
        if ((address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(18), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, (*opcode >> 9) & 7u,
                               ((uint32_t)value_high << 16) | (uint32_t)value_low);
        *cycles = UINT64_C(18);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x207b)) {
        /* MOVEA.L (d8,PC,Xn),An (guest demanded, plan 05-11). MOVEA.W, other
         * source modes and non-MC68000 extension words stay unsupported.
         * Effective address: PRM section 2.2.12, p. 2-14 (the PC value is the
         * address of the extension word; displacement and index are sign
         * extended). Only the MC68000 brief extension format is admitted:
         * extension bits 10-8 must be zero, so scale and full-format words
         * fail closed. Operation and condition codes: PRM section 4 MOVEA,
         * pp. 4-119 to 4-120 (full longword to An, flags unchanged). Timing:
         * User's Manual Rev. 9.1 Table 8-3 (printed p. 8-3), (d8,PC,Xn)
         * source to An: 18(4/0). */
        const uint32_t extension_address = cursor;
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t address = extension_address +
                                 sign_extend_byte((uint8_t)extension) + index;
        if ((address & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode, address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(18), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t value_high = 0u;
        uint16_t value_low = 0u;
        status = read_word(cpu, address, &value_high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, address + UINT32_C(2), &value_low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, (*opcode >> 9) & 7u,
                               ((uint32_t)value_high << 16) | (uint32_t)value_low);
        *cycles = UINT64_C(18);
    } else if (move_long_memory_source_to_data_register_cycles(*opcode) != 0u) {
        status = execute_move_long_memory_source_to_data_register(
            cpu, instruction_pc, *opcode, &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2058)) {
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t source = cpu->address_registers[source_register];
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = read_word(cpu, source, &high);
        if (status == OWNED_CPU_OK)
            status = read_word(cpu, source + UINT32_C(2), &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t value = ((uint32_t)high << 16) | (uint32_t)low;
        write_address_register(cpu, source_register, source + UINT32_C(4));
        write_address_register(cpu, destination_register, value);
        /* Motorola M68000 Family PRM §4 MOVEA, pp. 4-119–4-120:
         * full longword to An, condition codes unchanged. User's Manual
         * Table 8-3, p. 8-3: MOVE.L (An)+,An is 12(3/0). */
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x40e0)) {
        /* MOVE SR,-(An), MC68000 only, guest demanded. Only the predecrement
         * word destination is admitted. The 68000 does not privilege MOVE
         * from SR (the UM marks it privileged only for the 68010); reserved
         * SR bits read as zero. PRM §4 MOVE from SR, pp. 4-125–4-126; UM
         * Rev. 9.1 Table 8-12 (printed p. 8-10) gives 8(1/1)+, and Table 8-1
         * (printed p. 8-2) adds 6(1/0) for predecrement, totaling 14 clocks.
         * The bounded core has one opcode read and one word write; it omits
         * the next-instruction prefetch represented in the manual's read count. */
        const unsigned address_register = (unsigned)(*opcode & 7u);
        const uint32_t destination =
            cpu->address_registers[address_register] - UINT32_C(2);
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(14), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, address_register, destination);
        status = write_word(cpu, destination,
                            (uint16_t)(cpu->sr & SR_IMPLEMENTED_MASK));
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        *cycles = UINT64_C(14);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4840)) {
        const unsigned reg = (unsigned)(*opcode & 7u);
        const uint32_t before = cpu->data_registers[reg];
        const uint32_t result = (before << 16) | (before >> 16);
        /* SWAP Dn exchanges the data-register words. PRM §4 SWAP,
         * pp. 4-185 to 4-186: N/Z from the full 32-bit result, V/C clear,
         * X unchanged. User's Manual Rev. 9.1 Table 8-12, p. 8-10: 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cpu->data_registers[reg] = result;
        set_move_flags(cpu, result);
        *cycles = UINT64_C(4);
    } else if (pea_control_ea_cycles(*opcode) != 0u) {
        /* PEA's control-EA set is distinct from SWAP's overlapping mode 000.
         * PRM §4 PEA, p. 4-159; UM Rev. 9.1 Table 8-10, p. 8-8. */
        status = execute_pea_control_ea(cpu, instruction_pc, *opcode,
                                        &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if (jsr_control_ea_cycles(*opcode) != 0u) {
        /* JSR control EAs are distinct from SWAP and PEA. PRM §4 JSR p. 4-109
         * and UM Rev. 9.1 Table 8-10 p. 8-8 define its operation and complete
         * timing by EA. */
        status = execute_jsr_control_ea(cpu, instruction_pc, *opcode,
                                        &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
    } else if ((*opcode & UINT16_C(0xff80)) == UINT16_C(0x4880) &&
               is_movem_register_to_memory_ea(
                   (uint16_t)(*opcode & UINT16_C(0x003f))) != 0) {
        uint16_t register_mask = 0u;
        status = fetch_word(cpu, &cursor, &register_mask);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        unsigned register_count = 0u;
        for (unsigned bit = 0u; bit < 16u; ++bit)
            if ((register_mask & (uint16_t)(UINT16_C(1) << bit)) != 0u)
                ++register_count;
        const unsigned width = (*opcode & UINT16_C(0x0040)) != 0u ? 4u : 2u;
        const unsigned predecrement =
            ((*opcode >> 3) & UINT16_C(7)) == UINT16_C(4);
        const unsigned address_register = (unsigned)(*opcode & UINT16_C(7));
        const uint32_t initial_base = cpu->address_registers[address_register];
        const uint16_t destination_ea = (uint16_t)(*opcode & UINT16_C(0x003f));
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, destination_ea, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (register_count != 0u && (ea.address & UINT32_C(1)) != 0u) {
            /* MC68000 User's Manual Rev. 9.1 §6.3.9.1/6.3.10, Fig. 6-7,
             * Table 8-14 p. 8-11: address error, extended frame, 50 clocks.
             * Pinned MAME's generated x48e0 handler attempts the low word at
             * EA+2 before the high word at EA for a predecrement long store;
             * the manuals do not establish split-word chronology. */
            const uint32_t fault_address = ea.address +
                (predecrement != 0u && width == 4u ? UINT32_C(2) : UINT32_C(0));
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             fault_address, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        /* MOVEM register-to-memory W/L. PRM §4 MOVEM pp. 4-127–4-130 defines
         * normal mask order D0..D7,A0..A7, reversed predecrement mask order
         * A7..A0,D7..D0, word truncation, initial-An transfer for a listed
         * predecrement base, and unchanged condition codes. UM Rev. 9.1
         * Table 8-10 p. 8-8 gives direct R->M totals; the split longword order
         * below is a local word-bus contract except for predecrement, which
         * follows the pinned generated x48e0 MAME differential only. */
        const unsigned mode = (unsigned)((destination_ea >> 3) & 7u);
        unsigned base_cycles = 0u;
        if (mode == 2u || mode == 4u) base_cycles = 8u;
        else if (mode == 5u) base_cycles = 12u;
        else if (mode == 6u) base_cycles = 14u;
        else if (mode == 7u)
            base_cycles = (destination_ea & 7u) == 0u ? 12u : 16u;
        const uint64_t instruction_cycles = (uint64_t)base_cycles +
            (uint64_t)register_count * (width == 4u ? UINT64_C(8) : UINT64_C(4));
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint32_t address = predecrement != 0u ? initial_base : ea.address;
        for (unsigned bit = 0u; bit < 16u; ++bit) {
            if ((register_mask & (uint16_t)(UINT16_C(1) << bit)) == 0u) continue;
            if (predecrement != 0u) address -= (uint32_t)width;
            unsigned register_index = 0u;
            unsigned address_source = 0u;
            if (predecrement != 0u) {
                if (bit < 8u) {
                    address_source = 1u;
                    register_index = 7u - bit;
                } else {
                    register_index = 15u - bit;
                }
            } else if (bit < 8u) {
                register_index = bit;
            } else {
                address_source = 1u;
                register_index = bit - 8u;
            }
            const uint32_t value = address_source != 0u
                ? (predecrement != 0u && register_index == address_register
                       ? initial_base : cpu->address_registers[register_index])
                : cpu->data_registers[register_index];
            if (width == 2u) {
                status = write_word(cpu, address, (uint16_t)value);
            } else if (predecrement != 0u) {
                /* Pinned MAME x48e0_movem_l_071234fc emits the low half at
                 * address+2 first, then the high half at address. */
                status = write_word(cpu, address + UINT32_C(2), (uint16_t)value);
                if (status == OWNED_CPU_OK)
                    status = write_word(cpu, address, (uint16_t)(value >> 16));
            } else {
                /* The manual specifies the final long value, not callback
                 * chronology; retain the core's conventional high/low word
                 * decomposition without assigning it to hardware. */
                status = write_word(cpu, address, (uint16_t)(value >> 16));
                if (status == OWNED_CPU_OK)
                    status = write_word(cpu, address + UINT32_C(2), (uint16_t)value);
            }
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            if (predecrement == 0u) address += (uint32_t)width;
        }
        if (predecrement != 0u && register_count != 0u)
            write_address_register(cpu, address_register, address);
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xff80)) == UINT16_C(0x4c80) &&
               is_movem_memory_to_register_ea(
                   (uint16_t)(*opcode & UINT16_C(0x003f))) != 0) {
        uint16_t register_mask = 0u;
        status = fetch_word(cpu, &cursor, &register_mask);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        unsigned register_count = 0u;
        for (unsigned bit = 0u; bit < 16u; ++bit)
            if ((register_mask & (uint16_t)(UINT16_C(1) << bit)) != 0u)
                ++register_count;
        const unsigned width = (*opcode & UINT16_C(0x0040)) != 0u ? 4u : 2u;
        const uint16_t source_ea = (uint16_t)(*opcode & UINT16_C(0x003f));
        const unsigned source_mode = (unsigned)((source_ea >> 3) & 7u);
        const unsigned source_reg = (unsigned)(source_ea & 7u);
        data_alterable_memory_ea ea;
        status = resolve_memory_to_register_source_ea(cpu, source_ea, &cursor,
                                                      width, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (register_count != 0u && (ea.address & UINT32_C(1)) != 0u) {
            /* MC68000 User's Manual Rev. 9.1 §6.3.9.1/6.3.10, Fig. 6-7,
             * Table 8-14 p. 8-11: address error, extended frame, 50 clocks. */
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }

        /* UM Rev. 9.1 Table 8-10 p. 8-8 gives M->R W/L base terms of 12
         * clocks for (An)/(An)+, 16 for displacement/absolute-short/PC-displacement,
         * 18 for brief index/PC-index, and 20 for absolute-long. Each selected
         * register adds four clocks for W or eight for L. */
        unsigned base_cycles = 0u;
        if (source_mode == 2u || source_mode == 3u) base_cycles = 12u;
        else if (source_mode == 5u ||
                 (source_mode == 7u && (source_reg == 0u || source_reg == 2u)))
            base_cycles = 16u;
        else if (source_mode == 6u ||
                 (source_mode == 7u && source_reg == 3u))
            base_cycles = 18u;
        else if (source_mode == 7u && source_reg == 1u)
            base_cycles = 20u;
        const uint64_t instruction_cycles = (uint64_t)base_cycles +
            (uint64_t)register_count * (width == 4u ? UINT64_C(8) : UINT64_C(4));
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint32_t address = ea.address;
        for (unsigned bit = 0u; bit < 16u; ++bit) {
            if ((register_mask & (uint16_t)(UINT16_C(1) << bit)) == 0u) continue;
            uint16_t high = 0u;
            uint16_t low = 0u;
            uint32_t value = 0u;
            if (width == 2u) {
                status = read_word(cpu, address, &high);
                if (status == OWNED_CPU_OK)
                    value = sign_extend_word(high);
            } else {
                status = read_word(cpu, address, &high);
                if (status == OWNED_CPU_OK)
                    status = read_word(cpu, address + UINT32_C(2), &low);
                if (status == OWNED_CPU_OK)
                    value = ((uint32_t)high << 16) | (uint32_t)low;
            }
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            if (bit < 8u) {
                cpu->data_registers[bit] = value;
            } else {
                write_address_register(cpu, bit - 8u, value);
            }
            address += (uint32_t)width;
        }
        if (source_mode == 3u)
            write_address_register(cpu, source_reg, address);
        /* PRM §4 MOVEM pp. 4-128–4-129: the final postincremented An value
         * overwrites a loaded register-list value for that same base. */
        *cycles = instruction_cycles;
    } else if (is_move_byte_immediate_to_data_alterable_memory(*opcode) != 0) {
        uint16_t immediate = 0u;
        status = fetch_word(cpu, &cursor, &immediate);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned destination_mode = (unsigned)((*opcode >> 6) & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint16_t destination_ea = (uint16_t)((destination_mode << 3) |
                                                    destination_register);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, destination_ea, &cursor,
                                                   1u, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t total_cycles =
            move_immediate_data_alterable_memory_cycles(destination_ea);
        if (total_cycles == 0u) return OWNED_CPU_UNSUPPORTED_OPCODE;
        const uint8_t value = (uint8_t)immediate;
        /* The MC68000 User's Manual Rev. 9.1 Table 8-2 p. 8-2 gives 12/12/12/
         * 16/18/16/20 clocks for immediate byte to the seven data-alterable
         * memory EAs. PRM §4 MOVE, pp. 4-116 to 4-118, defines the byte value
         * and flags. The immediate extension is fetched before destination EA
         * extensions; postincrement commits after the successful write. */
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        status = write_byte(cpu, ea.address, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        set_move_byte_flags(cpu, value);
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x41d0)) {
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t effective_address = cpu->address_registers[base_register];
        /* LEA (An),An transfers the address-register value without reading
         * memory or changing condition codes. User's Manual Rev. 9.1
         * Table 8-10 (printed p. 8-8) gives 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, destination_register, effective_address);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x41e8)) {
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t displacement = (uint32_t)encoded_displacement;
        if ((displacement & UINT32_C(0x8000)) != 0u)
            displacement |= UINT32_C(0xffff0000);
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        /* LEA (d16,An),An does not touch condition codes. User's Manual
         * Rev. 9.1 Table 8-10 (printed p. 8-8): LEA (d16,An) is 8(2/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, destination_register,
                               cpu->address_registers[base_register] + displacement);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x41f0)) {
        uint16_t index_extension = 0u;
        status = fetch_word(cpu, &cursor, &index_extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((index_extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned base_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned index_register = (unsigned)((index_extension >> 12) & 7u);
        const uint32_t index_full =
            (index_extension & UINT16_C(0x8000)) != 0u
                ? cpu->address_registers[index_register]
                : cpu->data_registers[index_register];
        const uint32_t index =
            (index_extension & UINT16_C(0x0800)) != 0u
                ? index_full
                : sign_extend_word((uint16_t)index_full);
        const uint32_t displacement =
            sign_extend_byte((uint8_t)index_extension);
        const uint32_t effective_address =
            cpu->address_registers[base_register] + displacement + index;
        /* LEA (d8,An,Xn),An: PRM §4 LEA p. 4-110 loads the 32-bit effective
         * address into An without changing condition codes; §2.2.7 p. 2-9
         * defines the brief indexed extension. MC68000 User's Manual Rev. 9.1
         * Table 8-10 (printed p. 8-8): LEA indexed is 12(2/0). Reject the
         * later-family full extension; the owned MC68000 subset reads only
         * the opcode and one brief extension word, with no operand access. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, destination_register, effective_address);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x41fa)) {
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t displacement = (uint32_t)encoded_displacement;
        if ((displacement & UINT32_C(0x8000)) != 0u)
            displacement |= UINT32_C(0xffff0000);
        /* LEA (d16,PC),An (guest demanded, plan 05-21). M68000 Family PRM
         * LEA, p. 4-110: the effective address is loaded into all 32 bits of
         * An and condition codes are unaffected. The PC-relative base is the
         * extension-word address (PRM section 2, same rule as JSR (d16,PC)
         * above). User's Manual Rev. 9.1 Table 8-10 (printed p. 8-8): LEA
         * (d16 PC) is 8(2/0). Destination A0-A7 only; (d8,PC,Xn) stays
         * unsupported. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, (unsigned)((*opcode >> 9) & 7u),
                               (instruction_pc + UINT32_C(2)) + displacement);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x41f8)) {
        uint16_t encoded_address = 0u;
        status = fetch_word(cpu, &cursor, &encoded_address);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t absolute = (uint32_t)encoded_address;
        if ((absolute & UINT32_C(0x8000)) != 0u) absolute |= UINT32_C(0xffff0000);
        /* LEA (xxx).W,An (guest demanded, plan 05-22). M68000 Family PRM LEA,
         * p. 4-110: the effective address, the sign-extended absolute short
         * address (PRM section 2), is loaded into all 32 bits of An and
         * condition codes are unaffected. User's Manual Rev. 9.1 Table 8-10
         * (printed p. 8-8): LEA (xxx).W is 8(2/0). PEA, JMP and indexed LEA
         * stay unsupported. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, (unsigned)((*opcode >> 9) & 7u), absolute);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x41f9)) {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* M68000 PRM §4 LEA: effective address -> An. User's Manual
         * Table 8-10, p. 8-8: LEA absolute-long is 12 clocks on the 16-bit bus. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, (*opcode >> 9) & 7u,
                               ((uint32_t)high << 16) | (uint32_t)low);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x1180)) {
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* MOVE.B Dn,(d8,An,Xn) (guest demanded by the bounded continuation).
         * Admit the MC68000 brief extension only; bits 10-8 are reserved and
         * remain unsupported. The index is signed word or full long plus the
         * signed d8 and An, with no scale. Byte EAs permit odd addresses.
         * PRM §2.2.7 and §4 MOVE define the address and N/Z/V/C/X behavior;
         * MC68000 UM Rev. 9.1 Table 8-2, p. 8-2 gives 14(2/1). */
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const unsigned base_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t destination = cpu->address_registers[base_register] +
            sign_extend_byte((uint8_t)extension) + index;
        const uint8_t value = (uint8_t)cpu->data_registers[source_register];
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(14), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_byte(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(14);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x1140)) {
        uint16_t encoded_displacement = 0u;
        status = fetch_word(cpu, &cursor, &encoded_displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        uint32_t displacement = encoded_displacement;
        if ((displacement & UINT32_C(0x8000)) != 0u)
            displacement |= UINT32_C(0xffff0000);
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned base_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination = cpu->address_registers[base_register] + displacement;
        const uint8_t value = (uint8_t)cpu->data_registers[source_register];
        /* MOVE.B Dn,(d16,An) (guest demanded, plan 05-27). Only this
         * register-to-displacement byte store is admitted. PRM section 4 MOVE,
         * pp. 4-116 to 4-118: move the low byte, set N/Z, clear V/C, preserve
         * X. User's Manual Rev. 9.1 Table 8-2 (printed p. 8-2): 12(2/1).
         */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_byte(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x1080)) {
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination = cpu->address_registers[address_register];
        const uint8_t value = (uint8_t)cpu->data_registers[source_register];
        /* Motorola M68000 PRM §4 MOVE and MC68000 User's Manual Table 8-2,
         * p. 8-2: Dn to (An) byte store is 8(1/1). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_byte(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x13c0)) {
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t destination = ((uint32_t)high << 16) | (uint32_t)low;
        const unsigned reg = (unsigned)(*opcode & 7u);
        const uint8_t value = (uint8_t)cpu->data_registers[reg];
        /* M68000 PRM §4 MOVE and MC68000 User's Manual Table 8-2, p. 8-2:
         * Dn to (xxx).L byte move is 16(3/1). Data-register upper bits are
         * unaffected; board timing remains subject to hardware validation. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_byte(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(16);
    } else if ((*opcode & UINT16_C(0xf100)) == UINT16_C(0x7000)) {
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
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x5040)) {
        /* ADDQ.W #<quick>,Dn. MC68000 User's Manual Rev. 9.1 Table 8-5
         * (p. 8-5): 4(1/0); update the low word and preserve the upper word. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        unsigned quick = (unsigned)((*opcode >> 9) & 7u);
        if (quick == 0u) quick = 8u;
        add_quick_word(cpu, (unsigned)(*opcode & 7u), quick);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x5100)) {
        /* SUBQ.B #<1..8>,Dn. PRM SUBQ pp. 4-181 to 4-182: subtraction
         * updates X/N/Z/V/C, with X receiving the borrow. UM Rev. 9.1
         * Table 8-5 p. 8-5 gives byte/word Dn quick arithmetic 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        unsigned quick = (unsigned)((*opcode >> 9) & 7u);
        const unsigned reg = (unsigned)(*opcode & 7u);
        if (quick == 0u) quick = 8u;
        uint16_t flags = 0u;
        const uint8_t before = (uint8_t)cpu->data_registers[reg];
        const uint8_t after = addsubq_byte(cpu->sr, before, quick, 1, &flags);
        cpu->data_registers[reg] =
            (cpu->data_registers[reg] & UINT32_C(0xffffff00)) | (uint32_t)after;
        cpu->sr = flags;
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x5140)) {
        /* SUBQ.W #<1..8>,Dn (guest demanded, plan 05-02). Preserve the high
         * word and update X/N/Z/V/C from the low-word subtraction. UM Rev. 9.1
         * Table 8-5 p. 8-5 gives register-direct word quick arithmetic 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        unsigned quick = (unsigned)((*opcode >> 9) & 7u);
        if (quick == 0u) quick = 8u;
        const unsigned reg = (unsigned)(*opcode & 7u);
        uint16_t flags = 0u;
        const uint16_t before = (uint16_t)cpu->data_registers[reg];
        const uint16_t after = subtract_quick_word(cpu->sr, before, quick,
                                                   &flags);
        cpu->data_registers[reg] =
            (cpu->data_registers[reg] & UINT32_C(0xffff0000)) | after;
        cpu->sr = flags;
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x4880)) {
        /* EXT.W Dn. PRM §4 EXT, printed p. 4-106: sign-extend Dn's low byte
         * into its low word; N/Z follow that word, V/C clear, X unchanged.
         * MC68000 UM Rev. 9.1 Table 8-12, printed p. 8-10, gives 4(1/0). */
        const unsigned reg = (unsigned)(*opcode & UINT16_C(0x0007));
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint16_t result = (uint16_t)sign_extend_byte(
            (uint8_t)cpu->data_registers[reg]);
        cpu->data_registers[reg] =
            (cpu->data_registers[reg] & UINT32_C(0xffff0000)) | result;
        set_move_word_flags(cpu, result);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x48c0)) {
        /* EXT.L Dn. PRM §4 EXT, printed p. 4-106: sign-extend Dn's low word
         * into the full register; N/Z follow the long result, V/C clear and X
         * is unchanged. MC68000 UM Rev. 9.1 Table 8-12, printed p. 8-10,
         * gives 4(1/0). */
        const unsigned reg = (unsigned)(*opcode & UINT16_C(0x0007));
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint32_t result = sign_extend_word(
            (uint16_t)cpu->data_registers[reg]);
        cpu->data_registers[reg] = result;
        set_move_flags(cpu, result);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf0f8)) == UINT16_C(0x50c0)) {
        /* Scc.B Dn for all 16 conditions. PRM section 4 Scc, pp. 4-172 to
         * 4-173: write $ff when the encoded condition is true and $00
         * otherwise; condition codes are not affected. UM Rev. 9.1 Table
         * 8-6 (p. 8-6) gives register-direct Scc 4(1/0) when false and
         * 6(1/0) when true. Keep the data-register-direct EA exact. */
        const unsigned reg = (unsigned)(*opcode & UINT16_C(0x0007));
        const unsigned condition = (unsigned)((*opcode >> 8) & 15u);
        const int condition_holds = condition_true(cpu->sr, condition);
        const uint64_t instruction_cycles = condition_holds != 0
            ? UINT64_C(6) : UINT64_C(4);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cpu->data_registers[reg] =
            (cpu->data_registers[reg] & UINT32_C(0xffffff00)) |
            (condition_holds != 0 ? UINT32_C(0xff) : UINT32_C(0x00));
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xf0c0)) == UINT16_C(0x50c0) &&
               is_data_alterable_memory_ea(*opcode) != 0) {
        /* Scc.B to the seven data-alterable memory EAs. PRM §4 Scc,
         * pp. 4-172–4-173 says MC68000/68008 memory destinations are read
         * before the condition byte is written; follow that primary-source
         * contract. The pinned MAME differential handler for SNE.B absolute
         * long omits the read (recorded as a discrepancy in ORACLE.md).
         * UM Rev. 9.1 Table 8-6 p. 8-6 gives the memory base 8(1/1), and
         * Table 8-1 p. 8-2 supplies the byte EA surcharge. Preserve the
         * resolver's predecrement-before-read and postincrement-after-read
         * partial-update behavior on host callback failures. */
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor, 1u,
                                                   &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t total_cycles = UINT64_C(8) + ea.address_cycles;
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        uint8_t discarded = 0u;
        status = read_byte(cpu, ea.address, &discarded);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        const unsigned condition = (unsigned)((*opcode >> 8) & 15u);
        status = write_byte(cpu, ea.address,
                            condition_true(cpu->sr, condition) != 0
                                ? UINT8_C(0xff) : UINT8_C(0x00));
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x5000)) {
        /* ADDQ.B #<quick>,Dn. MC68000 User's Manual Rev. 9.1 Table 8-5
         * (p. 8-5): 4(1/0); only the low byte is modified. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        unsigned quick = (unsigned)((*opcode >> 9) & 7u);
        if (quick == 0u) quick = 8u;
        add_quick_byte(cpu, (unsigned)(*opcode & 7u), quick);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x5180)) {
        /* SUBQ.L #<quick>,Dn. PRM SUBQ, pp. 4-181 to 4-182; MC68000
         * User's Manual Rev. 9.1 Table 8-5 (p. 8-5): 8(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        unsigned quick = (unsigned)((*opcode >> 9) & 7u);
        unsigned reg = (unsigned)(*opcode & 7u);
        if (quick == 0u) quick = 8u;
        subtract_quick_long(cpu, reg, quick);
        *cycles = UINT64_C(8);
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
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x30c0)) {
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination = cpu->address_registers[address_register];
        const uint16_t value = (uint16_t)cpu->data_registers[source_register];
        if ((destination & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        /* Motorola M68000 PRM §4 MOVE: word postincrement advances An by two.
         * MC68000 User's Manual Table 8-2, p. 8-2: Dn to (An)+ is 8(1/1). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, address_register, destination + UINT32_C(2));
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x3100)) {
        /* MOVE.W Dn,-(An). The MC68000 User's Manual Rev. 9.1 Table 8-2
         * (printed p. 8-2) gives 8(1/1), matching the indirect and
         * postincrement word stores above. The PRM MOVE operation writes Dn's
         * low word, sets N/Z, clears V/C and preserves X. Resolve and commit
         * predecrement before the write; odd-address update ordering follows
         * the pinned MAME 68000 handler as a differential, not a hardware
         * bus-timing claim. A7 goes through write_address_register so the
         * active supervisor/user stack bank stays synchronized. */
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t destination =
            cpu->address_registers[address_register] - UINT32_C(2);
        const uint16_t value = (uint16_t)cpu->data_registers[source_register];
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            write_address_register(cpu, address_register, destination);
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, address_register, destination);
        status = write_word(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x3080)) {
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned data_register = (unsigned)(*opcode & 7u);
        const uint32_t destination = cpu->address_registers[address_register];
        if ((destination & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        /* MOVE.W Dn,(An). MC68000 User's Manual Rev. 9.1 Table 8-2 (p. 8-2):
         * 8(1/1). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint16_t value = (uint16_t)cpu->data_registers[data_register];
        status = write_word(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x3140)) {
        uint16_t displacement = 0u;
        status = fetch_word(cpu, &cursor, &displacement);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned address_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned data_register = (unsigned)(*opcode & 7u);
        const uint32_t destination = cpu->address_registers[address_register] +
                                     sign_extend_word(displacement);
        if ((destination & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        /* MOVE.W Dn,(d16,An). MC68000 User's Manual Rev. 9.1 Table 8-2
         * (p. 8-2): 12(2/1). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint16_t value = (uint16_t)cpu->data_registers[data_register];
        status = write_word(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x3180)) {
        /* MOVE.W Dn,(d8,An,Xn) (guest demanded, plan 05-02). Admit the
         * MC68000 brief extension only; its reserved bits 10-8 must be zero.
         * PRM §2.2.7 defines signed d8 plus the signed word or full long index.
         * A word write to an odd EA enters vector 3 before operand access.
         * The value comes from Dn's low word, N/Z follow that word, V/C clear,
         * and X is preserved (PRM §4 MOVE, pp. 4-116 to 4-118). UM Rev. 9.1
         * Table 8-2, p. 8-2: Dn to indexed destination is 14(2/1). */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if ((extension & UINT16_C(0x0700)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return OWNED_CPU_UNSUPPORTED_OPCODE;
        }
        const unsigned index_register = (unsigned)((extension >> 12) & 7u);
        const unsigned base_register = (unsigned)((*opcode >> 9) & 7u);
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const uint32_t index_full = (extension & UINT16_C(0x8000)) != 0u
            ? cpu->address_registers[index_register]
            : cpu->data_registers[index_register];
        const uint32_t index = (extension & UINT16_C(0x0800)) != 0u
            ? index_full
            : sign_extend_word((uint16_t)index_full);
        const uint32_t destination = cpu->address_registers[base_register] +
            sign_extend_byte((uint8_t)extension) + index;
        if ((destination & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(14), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const uint16_t value = (uint16_t)cpu->data_registers[source_register];
        status = write_word(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(14);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x3008)) {
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint16_t value = (uint16_t)cpu->address_registers[source_register];
        /* MOVE.W An,Dn. MC68000 User's Manual Rev. 9.1 Table 8-2 (p. 8-2):
         * 4(1/0); only Dn's low word is replaced. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & UINT32_C(0xffff0000)) |
            (uint32_t)value;
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x2000)) {
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint32_t value = cpu->data_registers[source_register];
        /* MOVE.L Dm,Dn (plan 05-21, guest-observed). PRM section 4 MOVE,
         * pp. 4-116 to 4-118: all 32 bits are copied, N/Z from the long, V/C
         * clear, X preserved. User's Manual Rev. 9.1 Table 8-3 (p. 8-3): Dn to
         * Dn long 4(1/0). Other sources and destinations stay unsupported. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cpu->data_registers[destination_register] = value;
        set_move_flags(cpu, value);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x103c)) {
        /* MOVE.B #<data>,Dn (guest demanded, plan 05-22). Other immediate
         * destinations stay unsupported; other byte source forms are handled
         * separately. PRM section 4 MOVE,
         * pp. 4-116 to 4-118: the low byte of Dn is replaced by the low byte
         * of the extension word, Dn[31:8] preserved, N/Z from the byte, V/C
         * cleared, X unchanged. User's Manual Rev. 9.1 Table 8-2 (p. 8-2):
         * immediate to Dn byte 8(2/0). */
        uint16_t extension = 0u;
        status = fetch_word(cpu, &cursor, &extension);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint8_t value = (uint8_t)extension;
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & UINT32_C(0xffffff00)) |
            (uint32_t)value;
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x1000)) {
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint8_t value = (uint8_t)cpu->data_registers[source_register];
        /* MOVE.B Dn,Dn (plan 05-20, guest-observed). Other Dn-direct sizes
         * and unlisted source/destination forms stay unsupported. PRM section 4 MOVE,
         * pp. 4-116 to 4-118: byte write keeps Dn[31:8], N/Z from the byte,
         * V/C clear, X preserved. User's Manual Rev. 9.1 Table 8-2 (p. 8-2):
         * Dn to Dn byte 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & UINT32_C(0xffffff00)) |
            (uint32_t)value;
        set_move_byte_flags(cpu, value);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0x3000)) {
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint16_t value = (uint16_t)cpu->data_registers[source_register];
        /* Motorola M68000 PRM §4 MOVE: word writes preserve Dn[31:16], update
         * N/Z/V/C, and preserve X. MC68000 User's Manual Table 8-2, p. 8-2:
         * Dn to Dn word is 4(1/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        cpu->data_registers[destination_register] =
            (cpu->data_registers[destination_register] & UINT32_C(0xffff0000)) |
            (uint32_t)value;
        set_move_word_flags(cpu, value);
        *cycles = UINT64_C(4);
    } else if (is_move_word_immediate_to_data_alterable_memory(*opcode) != 0) {
        uint16_t immediate = 0u;
        status = fetch_word(cpu, &cursor, &immediate);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const unsigned destination_mode = (unsigned)((*opcode >> 6) & 7u);
        const unsigned destination_register = (unsigned)((*opcode >> 9) & 7u);
        const uint16_t destination_ea = (uint16_t)((destination_mode << 3) |
                                                    destination_register);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, destination_ea, &cursor,
                                                   2u, &ea);
        if (status != OWNED_CPU_OK) {
            if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
            }
            return status;
        }
        const uint64_t total_cycles =
            move_immediate_data_alterable_memory_cycles(destination_ea);
        if (total_cycles == 0u) return OWNED_CPU_UNSUPPORTED_OPCODE;
        if ((ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        status = write_word(cpu, ea.address, immediate);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        set_move_word_flags(cpu, immediate);
        *cycles = total_cycles;
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x303c)) {
        uint16_t immediate = 0u;
        status = fetch_word(cpu, &cursor, &immediate);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        /* M68000 PRM §4 MOVE: word immediate to Dn replaces only its low
         * word. MC68000 User's Manual Table 8-2, p. 8-2: 8(2/0). */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned reg = (unsigned)((*opcode >> 9) & 7u);
        cpu->data_registers[reg] =
            (cpu->data_registers[reg] & UINT32_C(0xffff0000)) | immediate;
        set_move_word_flags(cpu, immediate);
        *cycles = UINT64_C(8);
    /* MOVE.L Dn,(xxx).L; address-register sources are handled by the shared
     * data-alterable destination path above. UM Rev. 9.1 Table 8-3 gives
     * 20(3/2) for Dn and an absolute-long destination. */
    } else if ((*opcode & UINT16_C(0xfff0)) == UINT16_C(0x23c0)) {
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
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode, destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        const unsigned reg = (unsigned)(*opcode & 7u);
        const uint32_t value = cpu->data_registers[reg];
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
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, EXCEPTION_INSTRUCTION_CYCLES, 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_short_exception(cpu, 8u, cpu->sr, instruction_pc, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = EXCEPTION_INSTRUCTION_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(132), 1u, 1u);
        if (status != OWNED_CPU_OK) return status;
        cpu->reset_signal_events++;
        *cycles = UINT64_C(132);
    } else if (*opcode == UINT16_C(0x4e73)) {
        if ((cpu->sr & SR_S) == 0u) {
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, EXCEPTION_INSTRUCTION_CYCLES, 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_short_exception(cpu, 8u, cpu->sr, instruction_pc, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = EXCEPTION_INSTRUCTION_CYCLES;
            return OWNED_CPU_OK;
        }
        if ((cpu->address_registers[7] & 1u) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             cpu->address_registers[7], 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
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
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x33c0)) {
        /* MOVE.W Dn,(xxx).L (guest demanded by bounded continuation). The
         * low word is written once; N/Z come from it, V/C clear and X stays.
         * UM Rev. 9.1 Table 8-2 p. 8-2 gives Dn to absolute-long 16(3/1). */
        uint16_t high = 0u;
        uint16_t low = 0u;
        status = fetch_word(cpu, &cursor, &high);
        if (status == OWNED_CPU_OK) status = fetch_word(cpu, &cursor, &low);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t destination = ((uint32_t)high << 16) | (uint32_t)low;
        if ((destination & 1u) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION, EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode, destination, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const uint16_t value =
            (uint16_t)cpu->data_registers[source_register];
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = write_word(cpu, destination, value);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        cpu->sr = (uint16_t)(cpu->sr & (uint16_t)~SR_MOVE_FLAGS);
        if (value == 0u) cpu->sr = (uint16_t)(cpu->sr | SR_Z);
        if ((value & UINT16_C(0x8000)) != 0u) cpu->sr = (uint16_t)(cpu->sr | SR_N);
        *cycles = UINT64_C(16);
    } else if ((*opcode & UINT16_C(0xf038)) == UINT16_C(0x5008) &&
               (((*opcode >> 6) & 3u) == 1u ||
                ((*opcode >> 6) & 3u) == 2u)) {
        /* ADDQ/SUBQ.W/L #<quick>,An (mode 001). PRM §4 ADDQ pp. 4-11–4-12
         * and SUBQ pp. 4-181–4-182 allow word/long only, operate on the full
         * 32-bit An, and leave all condition codes unchanged. UM Rev. 9.1
         * Table 8-5 p. 8-5 lists ADDQ.W An as 4 clocks; Rockwell's 1985 R68000
         * Data Book Table 27 p. 1-47 lists 8 clocks for word-only An, and the
         * pinned MAME cycle table also uses 4. Keep that documented conflict
         * explicit and select 8 from the independent Rockwell primary table;
         * the guest does not qualify hardware cycle accuracy for this form. */
        const uint64_t instruction_cycles = UINT64_C(8);
        status = preflight_event(cpu, STEP_INSTRUCTION, instruction_cycles,
                                 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        unsigned quick = (unsigned)((*opcode >> 9) & 7u);
        if (quick == 0u) quick = 8u;
        const unsigned reg = (unsigned)(*opcode & 7u);
        const unsigned subtract = (unsigned)((*opcode >> 8) & 1u);
        const uint32_t before = cpu->address_registers[reg];
        const uint32_t after = subtract != 0u
            ? before - (uint32_t)quick
            : before + (uint32_t)quick;
        write_address_register(cpu, reg, after);
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb000)) {
        /* CMP.B Dm,Dn (guest demanded). The direct-register encoding is
         * restricted to this byte opmode; compare Dn's low byte minus Dm's,
         * update N/Z/V/C, and preserve X and both registers. PRM CMP pp. 4-75
         * to 4-76 defines the compare flags; UM Rev. 9.1 Table 8-4 (printed
         * p. 8-4) gives 4(1/0) for byte op<ea>,Dn plus zero Dn EA clocks. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_reg = (unsigned)(*opcode & 7u);
        const unsigned destination_reg = (unsigned)((*opcode >> 9) & 7u);
        const uint8_t source = (uint8_t)cpu->data_registers[source_reg];
        const uint8_t destination = (uint8_t)cpu->data_registers[destination_reg];
        set_compare_flags(cpu, destination, source, 1u);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb040)) {
        /* CMP.W Dn,Dn: Motorola/NXP M68000 User's Manual Rev. 9.1,
         * Table 8-4 (printed p. 8-4), CMP word op<ea>,Dn with Dn direct: 4(1/0).
         * CMP subtracts for flags and never writes the destination. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(4), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_reg = (unsigned)(*opcode & 7u);
        const unsigned destination_reg = (unsigned)((*opcode >> 9) & 7u);
        const uint16_t source = (uint16_t)cpu->data_registers[source_reg];
        const uint16_t destination = (uint16_t)cpu->data_registers[destination_reg];
        set_compare_flags(cpu, destination, source, 2u);
        *cycles = UINT64_C(4);
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xb080)) {
        /* CMP.L Dm,Dn compares the complete longword without writing either
         * operand. The shared compare helper updates N/Z/V/C and preserves X.
         * UM Rev. 9.1 Table 8-4 p. 8-4 gives long CMP op<ea>,Dn 6(1/0); Dn
         * direct adds no EA clocks. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(6), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_reg = (unsigned)(*opcode & 7u);
        const unsigned destination_reg = (unsigned)((*opcode >> 9) & 7u);
        set_compare_flags(cpu, cpu->data_registers[destination_reg],
                          cpu->data_registers[source_reg], 4u);
        *cycles = UINT64_C(6);
    } else if (((*opcode & UINT16_C(0xf130)) == UINT16_C(0x9100)) &&
               ((*opcode & UINT16_C(0x0008)) == 0u) &&
               (((*opcode >> 6) & UINT16_C(3)) < 3u)) {
        /* SUBX Dm,Dn register-direct byte/word/long forms. The PRM SUBX
         * entry (pp. 4-182 to 4-184) specifies X as borrow-in, C/X as
         * borrow-out, sticky Z, and N/V from the width-limited result. UM
         * Rev. 9.1 Table 8-11 (printed p. 8-9) gives 4(1/0) for byte/word
         * and 8(1/0) for long. Bit 3 selects predecrement-memory SUBX, which
         * remains unsupported here. */
        const unsigned size_code = (unsigned)((*opcode >> 6) & 3u);
        const unsigned width = size_code == 0u ? 1u :
            size_code == 1u ? 2u : 4u;
        const uint64_t instruction_cycles = width == 4u
            ? UINT64_C(8) : UINT64_C(4);
        status = preflight_event(cpu, STEP_INSTRUCTION,
                                 instruction_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register =
            (unsigned)((*opcode >> 9) & 7u);
        subtract_extend_data_register(cpu, source_register,
                                      destination_register, width);
        *cycles = instruction_cycles;
    } else if (((*opcode & UINT16_C(0xf130)) == UINT16_C(0xd100)) &&
               ((*opcode & UINT16_C(0x0008)) == 0u) &&
               (((*opcode >> 6) & UINT16_C(3)) < 3u)) {
        /* ADDX Dm,Dn register-direct byte/word/long forms. The PRM ADDX
         * entry (pp. 4-13 to 4-15) specifies X as carry-in, C/X as carry-out,
         * sticky Z, and N/V from the width-limited result. UM Rev. 9.1
         * Table 8-11 (printed p. 8-9) gives 4(1/0) for byte/word and 8(1/0)
         * for long. Bit 3 selects predecrement-memory ADDX, kept separate. */
        const unsigned size_code = (unsigned)((*opcode >> 6) & UINT16_C(3));
        const unsigned width = size_code == 0u ? 1u :
            size_code == 1u ? 2u : 4u;
        const uint64_t instruction_cycles = width == 4u
            ? UINT64_C(8) : UINT64_C(4);
        status = preflight_event(cpu, STEP_INSTRUCTION,
                                 instruction_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const unsigned destination_register =
            (unsigned)((*opcode >> 9) & 7u);
        add_extend_data_register(cpu, source_register,
                                 destination_register, width);
        *cycles = instruction_cycles;
    } else if ((*opcode & UINT16_C(0xf1f8)) == UINT16_C(0xd148)) {
        /* ADDX.W -(Ay),-(Ax) is a guest-observed memory-to-memory form. The
         * MC68000 PRM ADDX operation uses X as carry-in and makes Z sticky;
         * UM Rev. 9.1 Table 8-11 (printed p. 8-9) specifies 18(3/1). Keep
         * byte/long predecrement forms separate from the register-direct
         * family handled above. */
        const unsigned source_register = (unsigned)(*opcode & UINT16_C(7));
        const unsigned destination_register =
            (unsigned)((*opcode >> 9) & UINT16_C(7));
        const uint32_t source_address =
            cpu->address_registers[source_register] - UINT32_C(2);
        if ((source_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             source_address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(18), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        write_address_register(cpu, source_register, source_address);
        uint16_t source = 0u;
        status = read_word(cpu, source_address, &source);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t destination_address =
            cpu->address_registers[destination_register] - UINT32_C(2);
        if ((destination_address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             destination_address, 0, 0);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        write_address_register(cpu, destination_register, destination_address);
        uint16_t destination = 0u;
        status = read_word(cpu, destination_address, &destination);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint32_t full_sum = (uint32_t)source + (uint32_t)destination +
            ((cpu->sr & SR_X) != 0u ? UINT32_C(1) : UINT32_C(0));
        const uint16_t result = (uint16_t)full_sum;
        uint16_t flags = (uint16_t)(cpu->sr & (uint16_t)~SR_ARITHMETIC_FLAGS);
        if (result == 0u && (cpu->sr & SR_Z) != 0u)
            flags = (uint16_t)(flags | SR_Z);
        if ((result & UINT16_C(0x8000)) != 0u)
            flags = (uint16_t)(flags | SR_N);
        if (((~(source ^ destination) & (destination ^ result)) &
             UINT16_C(0x8000)) != 0u)
            flags = (uint16_t)(flags | SR_V);
        if (full_sum > UINT16_MAX)
            flags = (uint16_t)(flags | SR_C | SR_X);
        status = write_word(cpu, destination_address, result);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        cpu->sr = flags;
        *cycles = UINT64_C(18);
    } else if (add_data_register_memory_destination_width(*opcode) != 0u ||
               sub_data_register_memory_destination_width(*opcode) != 0u) {
        /* ADD/SUB.B/W/L Dn,<data-alterable memory> use the same read-modify-
         * write transfer. UM Rev. 9.1 Table 8-4 p. 8-4 gives 8(1/1)+ for
         * byte/word and 12(1/2)+ for long; Table 8-1 p. 8-2 supplies the
         * selected EA cost. Resolve extension words before the transfer,
         * commit predecrement before operand access, and postincrement after a
         * successful read. For odd word/long vector-3 faults, the ADD/SUB
         * auto-update ordering follows pinned MAME handlers as differential
         * evidence only; host callback errors remain distinct terminal faults. */
        const int subtract =
            (*opcode & UINT16_C(0xf000)) == UINT16_C(0x9000);
        const unsigned width = subtract != 0
            ? sub_data_register_memory_destination_width(*opcode)
            : add_data_register_memory_destination_width(*opcode);
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
            }
            return status;
        }
        const uint64_t base_cycles = width == 4u ? UINT64_C(12) : UINT64_C(8);
        const uint64_t total_cycles = base_cycles + ea.address_cycles;
        if (width != 1u && (ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t destination = 0u;
        if (width == 1u) {
            uint8_t value = 0u;
            status = read_byte(cpu, ea.address, &value);
            destination = value;
        } else if (width == 2u) {
            uint16_t value = 0u;
            status = read_word(cpu, ea.address, &value);
            destination = value;
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            destination = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        const unsigned source_register = (unsigned)((*opcode >> 9) & UINT16_C(7));
        const uint32_t source_mask = width == 1u ? UINT32_C(0xff) :
            width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
        const uint32_t source =
            cpu->data_registers[source_register] & source_mask;
        uint16_t flags = 0u;
        const uint32_t result = addsub_value(cpu->sr, destination, source,
                                              width, subtract, &flags);
        if (width == 1u) {
            status = write_byte(cpu, ea.address, (uint8_t)result);
        } else if (width == 2u) {
            status = write_word(cpu, ea.address, (uint16_t)result);
        } else {
            status = write_word(cpu, ea.address, (uint16_t)(result >> 16));
            if (status == OWNED_CPU_OK)
                status = write_word(cpu, ea.address + UINT32_C(2),
                                    (uint16_t)result);
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        cpu->sr = flags;
        *cycles = total_cycles;
    } else if (sub_data_register_source_width(*opcode) != 0u) {
        /* SUB.{B,W,L} <ea>,Dn uses one shared source path. The PRM §4 SUB
         * source-EA table (pp. 4-174 to 4-175) admits Dn, An for word/long,
         * data-alterable memory, PC-relative and immediate, but explicitly
         * excludes An-direct for byte. UM Rev. 9.1 Table 8-4 p. 8-4 gives
         * byte/word base 4(1/0)+ and long 6(1/0)+; its ** adjustment raises
         * long Dn/An-direct and immediate to eight before adding any immediate
         * EA time. Table 8-1 p. 8-2 supplies memory/PC/immediate EA costs. */
        const unsigned width = sub_data_register_source_width(*opcode);
        const unsigned source_mode = (unsigned)((*opcode >> 3) & 7u);
        const unsigned source_register = (unsigned)(*opcode & UINT16_C(7));
        const unsigned destination_register =
            (unsigned)((*opcode >> 9) & UINT16_C(7));
        const uint32_t mask = width == 1u ? UINT32_C(0xff) :
            width == 2u ? UINT32_C(0xffff) : UINT32_MAX;
        uint32_t source = 0u;
        uint64_t source_ea_cycles = 0u;
        int memory_source = 0;
        data_alterable_memory_ea source_ea = {0};

        if (source_mode == 0u) {
            source = cpu->data_registers[source_register] & mask;
        } else if (source_mode == 1u) {
            source = cpu->address_registers[source_register] & mask;
        } else if (source_mode == 7u && source_register == 4u) {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = fetch_word(cpu, &cursor, &high);
            if (status == OWNED_CPU_OK && width == 4u)
                status = fetch_word(cpu, &cursor, &low);
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            source = width == 4u
                ? ((uint32_t)high << 16) | (uint32_t)low
                : (uint32_t)high;
            source_ea_cycles = width == 4u ? UINT64_C(8) : UINT64_C(4);
        } else {
            status = resolve_memory_to_register_source_ea(
                cpu, *opcode, &cursor, width, &source_ea);
            if (status != OWNED_CPU_OK) {
                if (status != OWNED_CPU_UNSUPPORTED_OPCODE) {
                    cpu->fault_pc = instruction_pc;
                    cpu->instruction_register = *opcode;
                }
                return status;
            }
            memory_source = 1;
            source_ea_cycles = source_ea.address_cycles;
            if (width != 1u && (source_ea.address & UINT32_C(1)) != 0u) {
                status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                         EXCEPTION_ADDRESS_ERROR_CYCLES,
                                         0u, 0u);
                if (status != OWNED_CPU_OK) return status;
                if (source_ea.has_base_update != 0u)
                    write_address_register(cpu, source_ea.base_register,
                                           source_ea.updated_base);
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                status = enter_address_exception(cpu, instruction_pc, *opcode,
                                                 source_ea.address, 0, 1);
                if (status != OWNED_CPU_OK) return status;
                *next_pc = cpu->pc;
                *kind = STEP_ADDRESS_EXCEPTION;
                *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
                return OWNED_CPU_OK;
            }
        }

        uint64_t base_cycles = width == 4u ? UINT64_C(6) : UINT64_C(4);
        if (width == 4u &&
            (source_mode <= 1u ||
             (source_mode == 7u && source_register == 4u)))
            base_cycles = UINT64_C(8);
        const uint64_t total_cycles = base_cycles + source_ea_cycles;
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;

        if (memory_source != 0) {
            if (source_ea.has_base_update != 0u &&
                source_ea.update_after_access == 0u)
                write_address_register(cpu, source_ea.base_register,
                                       source_ea.updated_base);
            if (width == 1u) {
                uint8_t value = 0u;
                status = read_byte(cpu, source_ea.address, &value);
                source = value;
            } else if (width == 2u) {
                uint16_t value = 0u;
                status = read_word(cpu, source_ea.address, &value);
                source = value;
            } else {
                uint16_t high = 0u;
                uint16_t low = 0u;
                status = read_word(cpu, source_ea.address, &high);
                if (status == OWNED_CPU_OK)
                    status = read_word(cpu, source_ea.address + UINT32_C(2),
                                       &low);
                source = ((uint32_t)high << 16) | (uint32_t)low;
            }
            if (status != OWNED_CPU_OK) {
                cpu->fault_pc = instruction_pc;
                cpu->instruction_register = *opcode;
                return status;
            }
            if (source_ea.has_base_update != 0u &&
                source_ea.update_after_access != 0u)
                write_address_register(cpu, source_ea.base_register,
                                       source_ea.updated_base);
        }

        const uint32_t destination_full =
            cpu->data_registers[destination_register];
        uint16_t flags = 0u;
        const uint32_t result = addsub_value(cpu->sr, destination_full,
            source, width, 1, &flags);
        cpu->data_registers[destination_register] =
            (destination_full & ~mask) | (result & mask);
        cpu->sr = flags;
        *cycles = total_cycles;
    } else if (add_data_register_direct_width(*opcode) != 0u) {
        /* ADD.{B,W,L} Dm,Dn (guest demanded): opmodes 000/001/010 admit
         * only data-register direct source and destination. The shared
         * width-aware operation preserves unaffected Dn bits for byte/word,
         * updates X/N/Z/V/C from the selected result width, and handles
         * source/destination aliasing. PRM §4 ADD, pp. 4-4 to 4-6, defines
         * the operation and flags. MC68000 UM Rev. 9.1 Table 8-4 (printed
         * p. 8-4) gives byte/word 4(1/0); long is 6(1/0)+ with footnote **
         * adding two clocks for register direct, totaling 8(1/0). */
        const unsigned width = add_data_register_direct_width(*opcode);
        const uint64_t total_cycles = width == 4u ? UINT64_C(8) : UINT64_C(4);
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_reg = (unsigned)(*opcode & 7u);
        const unsigned destination_reg = (unsigned)((*opcode >> 9) & 7u);
        add_data_register_direct(cpu, source_reg, destination_reg, width);
        *cycles = total_cycles;
    } else if (adda_data_alterable_memory_source_width(*opcode) != 0u) {
        /* ADDA.W/L reads one of the seven data-alterable memory EAs, adds the
         * sign-extended word or full long source to An, and leaves SR
         * unchanged. MC68000 UM Rev. 9.1 Table 8-4 p. 8-4 gives the word
         * op<ea>,An base as 8(1/0)+ and the long base as 6(1/0)+; Table 8-1
         * p. 8-2 supplies the width-specific memory EA cost. The long `**`
         * adjustment is only for register-direct or immediate EAs, which
         * this admission excludes. The source EA update is applied before
         * the sum, including when source base and destination An alias; this
         * ordering follows the pinned generated ADDA handlers as differential
         * evidence. Odd word/long auto-update at vector 3 follows that same
         * differential; host callback failures remain a separate owned-core
         * contract. */
        const unsigned width =
            adda_data_alterable_memory_source_width(*opcode);
        const unsigned destination_register =
            (unsigned)((*opcode >> 9) & UINT16_C(7));
        data_alterable_memory_ea ea;
        status = resolve_data_alterable_memory_ea(cpu, *opcode, &cursor,
                                                   width, &ea);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        const uint64_t base_cycles = width == 2u
            ? UINT64_C(8) : UINT64_C(6);
        const uint64_t total_cycles = base_cycles + ea.address_cycles;
        if ((ea.address & UINT32_C(1)) != 0u) {
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            if (ea.has_base_update != 0u)
                write_address_register(cpu, ea.base_register, ea.updated_base);
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             ea.address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, total_cycles, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        if (ea.has_base_update != 0u && ea.update_after_access == 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);

        uint32_t source = 0u;
        if (width == 2u) {
            uint16_t word = 0u;
            status = read_word(cpu, ea.address, &word);
            source = sign_extend_word(word);
        } else {
            uint16_t high = 0u;
            uint16_t low = 0u;
            status = read_word(cpu, ea.address, &high);
            if (status == OWNED_CPU_OK)
                status = read_word(cpu, ea.address + UINT32_C(2), &low);
            source = ((uint32_t)high << 16) | (uint32_t)low;
        }
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        if (ea.has_base_update != 0u && ea.update_after_access != 0u)
            write_address_register(cpu, ea.base_register, ea.updated_base);
        write_address_register(cpu, destination_register,
            cpu->address_registers[destination_register] + source);
        *cycles = total_cycles;
    } else if (adda_register_direct_source_width(*opcode) != 0u) {
        /* ADDA.{W,L} Dm/Am,An (selected-guest demand): opmodes 011/111 and
         * direct Dn/An source only. Word sources sign-extend before the
         * full-width sum; long sources use all bits. Sample the source before
         * writing An so source/destination aliases use the original value.
         * SR is unchanged. PRM §4 ADDA, pp. 4-7 to 4-8. UM Rev. 9.1
         * Table 8-4 p. 8-4 gives the word row 8(1/0)+ and long row 6(1/0)+**;
         * the register-direct footnote raises long to 8(1/0), so all direct
         * source forms here take eight clocks. */
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(8), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned source_reg = (unsigned)(*opcode & 7u);
        const unsigned destination_reg = (unsigned)((*opcode >> 9) & 7u);
        const unsigned source_mode = (unsigned)((*opcode >> 3) & 7u);
        const unsigned width = adda_register_direct_source_width(*opcode);
        uint32_t source = source_mode == 0u
            ? cpu->data_registers[source_reg]
            : cpu->address_registers[source_reg];
        if (width == 2u) source = sign_extend_word((uint16_t)source);
        write_address_register(cpu, destination_reg,
            cpu->address_registers[destination_reg] + source);
        *cycles = UINT64_C(8);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0xd0fc)) {
        /* ADDA.W #<data>,An for the word-immediate source only. The source
         * word is sign-extended before addition to all 32 bits of An; ADDA
         * leaves SR unchanged. PRM §4 ADDA pp. 4-7 to 4-8 specifies the
         * operation and immediate EA. UM Rev. 9.1 Table 8-4 p. 8-4 gives
         * word op<ea>,An as 8(1/0)+; Table 8-1 p. 8-2 adds 4(1/0) for the
         * immediate word, totaling 12(2/0). The ** adjustment is not marked
         * on this row. */
        uint16_t immediate = 0u;
        status = fetch_word(cpu, &cursor, &immediate);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_reg = (unsigned)((*opcode >> 9) & 7u);
        write_address_register(cpu, destination_reg,
            cpu->address_registers[destination_reg] +
            sign_extend_word(immediate));
        *cycles = UINT64_C(12);
    } else if ((*opcode & UINT16_C(0xf1ff)) == UINT16_C(0x90fc)) {
        /* SUBA.W #<data>,An for the word-immediate source only. The source
         * word is sign-extended before subtraction from all 32 bits of An;
         * SUBA leaves SR unchanged. PRM §4 SUBA pp. 4-177 to 4-178 specifies
         * the operation and immediate EA. UM Rev. 9.1 Table 8-4 p. 8-4 gives
         * the SUB byte/word op<ea>,An base as 8(1/0)+; Table 8-1 p. 8-2 adds
         * 4(1/0) for the immediate word, totaling 12(2/0). No ** adjustment
         * is marked on this byte/word row. */
        uint16_t immediate = 0u;
        status = fetch_word(cpu, &cursor, &immediate);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(12), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        const unsigned destination_reg = (unsigned)((*opcode >> 9) & 7u);
        write_address_register(cpu, destination_reg,
            cpu->address_registers[destination_reg] -
            sign_extend_word(immediate));
        *cycles = UINT64_C(12);
    } else if (*opcode == UINT16_C(0x4afc)) {
        /* P01-C-14: candidate capability boundary, not silicon behavior.
         * Successful fetch rejects before exception preflight or bus effects. */
        cpu->fault_pc = instruction_pc;
        cpu->instruction_register = *opcode;
        return OWNED_CPU_UNSUPPORTED_OPCODE;
    } else if (*opcode == UINT16_C(0x4e40)) {
        status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, EXCEPTION_INSTRUCTION_CYCLES, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = enter_short_exception(cpu, 32u, cpu->sr, cursor, 0u);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_INSTRUCTION_EXCEPTION;
        *cycles = EXCEPTION_INSTRUCTION_CYCLES;
        return OWNED_CPU_OK;
    } else if ((*opcode & UINT16_C(0xfff8)) == UINT16_C(0x46d8)) {
        /* MOVE.W (An)+,SR (guest-observed, plan 05-02 task 2). On MC68000
         * this operation is privileged; user mode takes vector 8 before EA
         * access or postincrement. In supervisor mode the word is read before
         * An advances by two, then its implemented SR bits take effect (PRM
         * MOVE to SR, section 6, p. 6-19; section 2.2.4, p. 2-6). UM Rev. 9.1
         * Table 8-12 p. 8-10 gives 12(2/0)+, and Table 8-1 p. 8-2 adds 4
         * clocks for postincrement. The core omits the manual's prefetch read,
         * so its bus count is opcode plus operand word. */
        if ((cpu->sr & SR_S) == 0u) {
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION,
                                     EXCEPTION_INSTRUCTION_CYCLES, 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_short_exception(cpu, 8u, cpu->sr,
                                           instruction_pc, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = EXCEPTION_INSTRUCTION_CYCLES;
            return OWNED_CPU_OK;
        }
        const unsigned source_register = (unsigned)(*opcode & 7u);
        const uint32_t address = cpu->address_registers[source_register];
        if ((address & UINT32_C(1)) != 0u) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            status = preflight_event(cpu, STEP_ADDRESS_EXCEPTION,
                                     EXCEPTION_ADDRESS_ERROR_CYCLES, 0u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_address_exception(cpu, instruction_pc, *opcode,
                                             address, 0, 1);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_ADDRESS_EXCEPTION;
            *cycles = EXCEPTION_ADDRESS_ERROR_CYCLES;
            return OWNED_CPU_OK;
        }
        status = preflight_event(cpu, STEP_INSTRUCTION, UINT64_C(16), 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        uint16_t source_status = 0u;
        status = read_word(cpu, address, &source_status);
        if (status != OWNED_CPU_OK) {
            cpu->fault_pc = instruction_pc;
            cpu->instruction_register = *opcode;
            return status;
        }
        write_address_register(cpu, source_register, address + UINT32_C(2));
        set_supervisor_status(cpu,
                              (uint16_t)(source_status & SR_IMPLEMENTED_MASK));
        *cycles = UINT64_C(16);
    } else if (*opcode == UINT16_C(0x46fc)) {
        if ((cpu->sr & SR_S) == 0u) {
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, EXCEPTION_INSTRUCTION_CYCLES, 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_short_exception(cpu, 8u, cpu->sr, instruction_pc, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = EXCEPTION_INSTRUCTION_CYCLES;
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
            status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, EXCEPTION_INSTRUCTION_CYCLES, 1u, 0u);
            if (status != OWNED_CPU_OK) return status;
            status = enter_short_exception(cpu, 8u, cpu->sr, instruction_pc, 0u);
            if (status != OWNED_CPU_OK) return status;
            *next_pc = cpu->pc;
            *kind = STEP_INSTRUCTION_EXCEPTION;
            *cycles = EXCEPTION_INSTRUCTION_CYCLES;
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
    } else if (((*opcode & UINT16_C(0xffc0)) == UINT16_C(0x0a00) ||
                (*opcode & UINT16_C(0xffc0)) == UINT16_C(0x0a80)) &&
               ((*opcode >> 3) & 7u) == 7u && (*opcode & 7u) >= 5u) {
        /* These observed EORI.B/EORI.L destination encodings are invalid on MC68000:
         * User's Manual Rev. 9.1 §6.3.6 selects illegal-instruction vector 4;
         * Table 6-2 (p. 6-7) places it at offset 0x10. The group-1 short frame
         * stores the unexecuted instruction PC and old SR on SSP (§§6.2.4-5).
         * Table 8-14 (p. 8-11) gives 34(4/3). Other
         * unsupported encodings remain fail-closed until classified. */
        status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION, EXCEPTION_INSTRUCTION_CYCLES, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = enter_short_exception(cpu, 4u, cpu->sr, instruction_pc, 0u);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_INSTRUCTION_EXCEPTION;
        *cycles = EXCEPTION_INSTRUCTION_CYCLES;
        return OWNED_CPU_OK;
    } else if ((*opcode & UINT16_C(0xf000)) == UINT16_C(0xa000)) {
        /* The MC68000 reserves the A-line range for unimplemented instructions
         * and enters the distinct Line 1010 Emulator vector. NXP PRM Table B-1
         * p. B-2 assigns vector 10 / offset $28; UM Rev. 9.1 §6.3.6 p. 6-15
         * describes the range and separate vector. The group-1 short frame
         * and 34-clock timing follow the illegal-instruction exception path
         * (UM §§6.2.4–6.2.5 and Table 8-14 p. 8-11); the manual does not list
         * Line-A timing separately, so this timing is an explicit inference. */
        status = preflight_event(cpu, STEP_INSTRUCTION_EXCEPTION,
                                 EXCEPTION_INSTRUCTION_CYCLES, 1u, 0u);
        if (status != OWNED_CPU_OK) return status;
        status = enter_short_exception(cpu, 10u, cpu->sr,
                                       instruction_pc, 0u);
        if (status != OWNED_CPU_OK) return status;
        *next_pc = cpu->pc;
        *kind = STEP_INSTRUCTION_EXCEPTION;
        *cycles = EXCEPTION_INSTRUCTION_CYCLES;
        return OWNED_CPU_OK;
    } else if (move_long_memory_to_memory_cycles(*opcode) != 0u) {
        status = execute_move_long_memory_to_memory(
            cpu, instruction_pc, *opcode, &cursor, next_pc, cycles, kind);
        if (status != OWNED_CPU_OK) return status;
        if (*kind == STEP_ADDRESS_EXCEPTION) return OWNED_CPU_OK;
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
    cpu->reset_cycles = RESET_EVENT_CYCLES;
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
    if (cpu->fetch_trace_run_sequence != UINT64_MAX)
        ++cpu->fetch_trace_run_sequence;
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
        result.elapsed_cycles = RESET_EVENT_CYCLES;
        cpu->total_cycles += RESET_EVENT_CYCLES;
    }
    while (result.elapsed_cycles < cycle_budget) {
        cpu->bus_cycles = 0u;
        unsigned level = cpu->irq_level;
        unsigned mask = (unsigned)((cpu->sr & SR_INTERRUPT_MASK) >> 8);
        int irq7 = cpu->irq7_pending != 0u || (level == 7u && mask < 7u);
        if (irq7 != 0 || (level >= 1u && level <= 6u && level > mask)) {
            unsigned accepted_level = irq7 != 0 ? 7u : level;
            uint64_t irq_cycles = EXCEPTION_IRQ_CYCLES;
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

uint64_t owned_cpu_current_bus_cycles(const owned_cpu *cpu) {
    return cpu != NULL && cpu->active != 0u ? cpu->bus_cycles : 0u;
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

uint32_t owned_cpu_current_instruction_pc(const owned_cpu *cpu) {
    if (cpu == NULL || cpu->ready == 0u) {
        return 0u;
    }
    /* While executing, cpu->pc still holds the instruction start: the run loop
     * assigns next_pc only after execute_one returns and moves the old value to
     * previous_pc. */
    return cpu->active != 0u ? cpu->pc : cpu->previous_pc;
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

owned_cpu_status owned_cpu_copy_fetch_trace(
    const owned_cpu *cpu, owned_cpu_fetch_trace_event *events,
    size_t capacity, size_t *out_count) {
    if (cpu == NULL || out_count == NULL || (capacity != 0u && events == NULL) ||
        cpu->active != 0u || capacity < cpu->fetch_trace_count) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    const size_t oldest = (cpu->fetch_trace_next + OWNED_CPU_FETCH_TRACE_CAPACITY -
                           cpu->fetch_trace_count) % OWNED_CPU_FETCH_TRACE_CAPACITY;
    for (size_t index = 0u; index < cpu->fetch_trace_count; ++index) {
        events[index] = cpu->fetch_trace[(oldest + index) %
                                         OWNED_CPU_FETCH_TRACE_CAPACITY];
    }
    *out_count = cpu->fetch_trace_count;
    return OWNED_CPU_OK;
}

_Static_assert(sizeof(owned_cpu_state) <= UINT32_MAX,
               "private state record size must fit its fixed header");
_Static_assert(sizeof(OWNED_CPU_STATE_CORE_IDENTITY_SHA256) == 65u,
               "private state identity must be one full SHA-256 hex digest");

static void state_from_cpu(const owned_cpu *cpu, owned_cpu_state *state) {
    state->size = (uint32_t)sizeof(*state);
    state->version = OWNED_CPU_STATE_VERSION;
    memcpy(state->core_identity, OWNED_CPU_STATE_CORE_IDENTITY_SHA256,
           sizeof(state->core_identity));
    state->present_fields = OWNED_CPU_STATE_REQUIRED_FIELDS;
    for (unsigned index = 0u; index < 8u; ++index) {
        state->data_registers[index] = cpu->data_registers[index];
        state->address_registers[index] = cpu->address_registers[index];
    }
    state->pc = cpu->pc;
    state->previous_pc = cpu->previous_pc;
    state->usp = cpu->usp;
    state->ssp = cpu->ssp;
    state->fault_pc = cpu->fault_pc;
    state->sr = cpu->sr;
    state->instruction_register = cpu->instruction_register;
    state->stopped = cpu->stopped;
    state->irq_level = cpu->irq_level;
    state->irq7_pending = cpu->irq7_pending;
    state->reset_pending = cpu->reset_pending;
    state->last_exception_vector = cpu->last_exception_vector;
    state->instructions = cpu->instructions;
    state->instruction_cycles = cpu->instruction_cycles;
    state->reset_cycles = cpu->reset_cycles;
    state->exception_cycles = cpu->exception_cycles;
    state->idle_cycles = cpu->idle_cycles;
    state->total_cycles = cpu->total_cycles;
    state->reset_signal_events = cpu->reset_signal_events;
}

static void state_copy_named(const owned_cpu_state *source, owned_cpu_state *target) {
    target->size = source->size;
    target->version = source->version;
    memcpy(target->core_identity, source->core_identity, sizeof(target->core_identity));
    target->present_fields = source->present_fields;
    for (unsigned index = 0u; index < 8u; ++index) {
        target->data_registers[index] = source->data_registers[index];
        target->address_registers[index] = source->address_registers[index];
    }
    target->pc = source->pc;
    target->previous_pc = source->previous_pc;
    target->usp = source->usp;
    target->ssp = source->ssp;
    target->fault_pc = source->fault_pc;
    target->sr = source->sr;
    target->instruction_register = source->instruction_register;
    target->stopped = source->stopped;
    target->irq_level = source->irq_level;
    target->irq7_pending = source->irq7_pending;
    target->reset_pending = source->reset_pending;
    target->last_exception_vector = source->last_exception_vector;
    target->instructions = source->instructions;
    target->instruction_cycles = source->instruction_cycles;
    target->reset_cycles = source->reset_cycles;
    target->exception_cycles = source->exception_cycles;
    target->idle_cycles = source->idle_cycles;
    target->total_cycles = source->total_cycles;
    target->reset_signal_events = source->reset_signal_events;
}

static int state_counter_sum(const owned_cpu_state *state, uint64_t *sum) {
    uint64_t value = state->reset_pending != 0u ? 0u : RESET_EVENT_CYCLES;
    const uint64_t counters[] = {
        state->instruction_cycles, state->exception_cycles, state->idle_cycles};
    for (size_t index = 0u; index < sizeof(counters) / sizeof(counters[0]); ++index) {
        if (value > UINT64_MAX - counters[index]) return 0;
        value += counters[index];
    }
    *sum = value;
    return 1;
}

static int state_instruction_count_valid(const owned_cpu_state *state) {
    if (state->instruction_cycles != 0u && state->instructions == 0u) return 0;
    if (state->instruction_cycles > UINT64_MAX - state->exception_cycles) return 0;
    uint64_t counted_instruction_cycles =
        state->instruction_cycles + state->exception_cycles;
    return state->instructions <=
           counted_instruction_cycles / MINIMUM_COUNTED_INSTRUCTION_CYCLES;
}

static int state_valid(const owned_cpu_state *state) {
    if (state->size != (uint32_t)sizeof(*state) ||
        state->version != OWNED_CPU_STATE_VERSION ||
        memcmp(state->core_identity, OWNED_CPU_STATE_CORE_IDENTITY_SHA256,
               sizeof(state->core_identity)) != 0 ||
        state->present_fields != OWNED_CPU_STATE_REQUIRED_FIELDS) {
        return 0;
    }
    if (state->stopped > 1u || state->irq7_pending > 1u ||
        state->reset_pending > 1u || state->irq_level > 7u ||
        state->reset_cycles != RESET_EVENT_CYCLES) {
        return 0;
    }
    uint32_t active_stack = (state->sr & SR_S) != 0u ? state->ssp : state->usp;
    /* Preserve guest-reachable odd addresses; execution reports deferred faults. */
    if (state->address_registers[7] != active_stack) {
        return 0;
    }
    uint64_t expected_total = 0u;
    if (!state_counter_sum(state, &expected_total) ||
        state->total_cycles != expected_total) {
        return 0;
    }
    if (!state_instruction_count_valid(state)) return 0;
    if (state->reset_pending != 0u &&
        (state->instructions != 0u || state->instruction_cycles != 0u ||
         state->exception_cycles != 0u || state->idle_cycles != 0u ||
         state->total_cycles != 0u || state->reset_signal_events != 0u)) {
        return 0;
    }
    return 1;
}

owned_cpu_status owned_cpu_validate_state(const owned_cpu_state *state) {
    return state != NULL && state_valid(state)
        ? OWNED_CPU_OK : OWNED_CPU_INVALID_ARGUMENT;
}

int owned_cpu_is_active(const owned_cpu *cpu) {
    return cpu != NULL && cpu->active != 0u;
}

static int cpu_address_ranges_overlap(const void *left, size_t left_size,
                                      const void *right, size_t right_size) {
    if (left_size == 0u || right_size == 0u) return 0;
    const uintptr_t left_start = (uintptr_t)left;
    const uintptr_t right_start = (uintptr_t)right;
    if (left_size > (size_t)(UINTPTR_MAX - left_start) ||
        right_size > (size_t)(UINTPTR_MAX - right_start)) return 1;
    const uintptr_t left_end = left_start + (uintptr_t)left_size;
    const uintptr_t right_end = right_start + (uintptr_t)right_size;
    return left_start < right_end && right_start < left_end;
}

int owned_cpu_buffer_overlaps(const owned_cpu *cpu, const void *buffer,
                              size_t length) {
    if (cpu == NULL || buffer == NULL || length == 0u) return 0;
    return cpu_address_ranges_overlap(buffer, length, cpu, sizeof(*cpu));
}

owned_cpu_status owned_cpu_capture_state(const owned_cpu *cpu, owned_cpu_state *out_state) {
    if (cpu == NULL || out_state == NULL || cpu->active != 0u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    if (cpu->faulted != 0u) return OWNED_CPU_HOST_FAULT;
    if (cpu->ready == 0u) return OWNED_CPU_INVALID_ARGUMENT;
    owned_cpu_state candidate;
    state_from_cpu(cpu, &candidate);
    if (!state_valid(&candidate)) return OWNED_CPU_INVALID_ARGUMENT;
    state_copy_named(&candidate, out_state);
    return OWNED_CPU_OK;
}

owned_cpu_status owned_cpu_apply_state(owned_cpu *cpu, const owned_cpu_state *state) {
    if (cpu == NULL || state == NULL || cpu->active != 0u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    if (state->size != (uint32_t)sizeof(*state)) return OWNED_CPU_INVALID_ARGUMENT;
    owned_cpu_state candidate;
    state_copy_named(state, &candidate);
    if (!state_valid(&candidate)) return OWNED_CPU_INVALID_ARGUMENT;

    for (unsigned index = 0u; index < 8u; ++index) {
        cpu->data_registers[index] = candidate.data_registers[index];
        cpu->address_registers[index] = candidate.address_registers[index];
    }
    cpu->pc = candidate.pc;
    cpu->previous_pc = candidate.previous_pc;
    cpu->usp = candidate.usp;
    cpu->ssp = candidate.ssp;
    cpu->fault_pc = candidate.fault_pc;
    cpu->sr = candidate.sr;
    cpu->instruction_register = candidate.instruction_register;
    cpu->stopped = candidate.stopped;
    cpu->irq_level = candidate.irq_level;
    cpu->irq7_pending = candidate.irq7_pending;
    cpu->reset_pending = candidate.reset_pending;
    cpu->last_exception_vector = candidate.last_exception_vector;
    cpu->instructions = candidate.instructions;
    cpu->instruction_cycles = candidate.instruction_cycles;
    cpu->reset_cycles = candidate.reset_cycles;
    cpu->exception_cycles = candidate.exception_cycles;
    cpu->idle_cycles = candidate.idle_cycles;
    cpu->total_cycles = candidate.total_cycles;
    cpu->reset_signal_events = candidate.reset_signal_events;
    cpu->bus_cycles = 0u;
    cpu->ready = 1u;
    cpu->faulted = 0u;
    cpu->fetch_trace_run_sequence = 0u;
    cpu->fetch_trace_count = 0u;
    cpu->fetch_trace_next = 0u;
    memset(cpu->fetch_trace, 0, sizeof(cpu->fetch_trace));
    return OWNED_CPU_OK;
}

owned_cpu_status owned_cpu_restore_state(owned_cpu *cpu, const owned_cpu_state *state) {
    if (cpu == NULL || state == NULL || cpu->active != 0u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    if (cpu->faulted != 0u) return OWNED_CPU_HOST_FAULT;
    return owned_cpu_apply_state(cpu, state);
}

#ifdef OWNED_CPU_TEST_HOOKS
owned_cpu_status owned_cpu_test_capture_faulted_state(
    const owned_cpu *cpu, owned_cpu_state *out_state) {
    if (cpu == NULL || out_state == NULL || cpu->active != 0u ||
        cpu->faulted == 0u || cpu->ready == 0u)
        return OWNED_CPU_INVALID_ARGUMENT;
    state_from_cpu(cpu, out_state);
    return OWNED_CPU_OK;
}

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
