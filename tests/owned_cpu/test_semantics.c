/* SPDX-License-Identifier: MIT */
#include "cpu.h"
#include "unity.h"

#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(CHAR_BIT == 8, "owned CPU tests require 8-bit bytes");
_Static_assert(UINT8_MAX == 0xffu, "uint8_t must be exactly 8 bits");
_Static_assert(UINT16_MAX == 0xffffu, "uint16_t must be exactly 16 bits");
_Static_assert(UINT32_MAX == 0xffffffffu, "uint32_t must be exactly 32 bits");
_Static_assert(UINT64_MAX == UINT64_C(0xffffffffffffffff), "uint64_t must be exactly 64 bits");

enum { ROM_SIZE = 512, MAX_WRITES = 32 };

typedef struct {
    uint8_t rom[ROM_SIZE];
    uint32_t write_addresses[MAX_WRITES];
    uint16_t write_values[MAX_WRITES];
    size_t write_attempts;
    size_t successful_writes;
    size_t reads;
    size_t fail_read_on;
    size_t fail_write_on;
} memory_bus;

static memory_bus memory;
static owned_cpu *cpu;

static void *allocate_memory(void *userdata, size_t bytes) {
    (void)userdata;
    return malloc(bytes);
}

static void release_memory(void *userdata, void *allocation) {
    (void)userdata;
    free(allocation);
}

static void *fail_allocate(void *userdata, size_t bytes) {
    (void)userdata;
    (void)bytes;
    return NULL;
}

static int read_guest_word(void *userdata, uint32_t address, uint16_t *value) {
    memory_bus *bus = userdata;
    if (bus == NULL || value == NULL || (address & 1u) != 0u) {
        return 0;
    }
    bus->reads++;
    if (bus->fail_read_on != 0u && bus->reads == bus->fail_read_on) {
        return 0;
    }
    if (address >= ROM_SIZE || address + 1u >= ROM_SIZE) {
        return 0;
    }
    *value = (uint16_t)(((uint16_t)bus->rom[address] << 8) | bus->rom[address + 1u]);
    return 1;
}

static int write_guest_word(void *userdata, uint32_t address, uint16_t value) {
    memory_bus *bus = userdata;
    if (bus == NULL || (address & 1u) != 0u) {
        return 0;
    }
    size_t attempt = bus->write_attempts++;
    if (attempt < MAX_WRITES) {
        bus->write_addresses[attempt] = address;
        bus->write_values[attempt] = value;
    }
    if (bus->fail_write_on != 0u && bus->write_attempts == bus->fail_write_on) {
        return 0;
    }
    bus->successful_writes++;
    return 1;
}

void setUp(void) {
    memset(&memory, 0, sizeof(memory));
    cpu = NULL;
}

void tearDown(void) {
    owned_cpu_destroy(cpu);
    cpu = NULL;
}

static void set_vector(uint32_t address, uint32_t value) {
    memory.rom[address] = (uint8_t)(value >> 24);
    memory.rom[address + 1u] = (uint8_t)(value >> 16);
    memory.rom[address + 2u] = (uint8_t)(value >> 8);
    memory.rom[address + 3u] = (uint8_t)value;
}

static void create_cpu(void) {
    set_vector(0u, UINT32_C(0x2000));
    set_vector(4u, UINT32_C(0x100));
    owned_cpu_bus bus = {&memory, read_guest_word, write_guest_word};
    owned_cpu_allocator allocator = {NULL, allocate_memory, release_memory};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, allocator, &cpu));
    TEST_ASSERT_NOT_NULL(cpu);
}

static owned_cpu_status reset_with_program(const uint8_t *program, size_t length) {
    if (program == NULL || length > ROM_SIZE - 0x100u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    memcpy(memory.rom + 0x100u, program, length);
    owned_cpu_status status = owned_cpu_reset(cpu);
    if (status != OWNED_CPU_OK) return status;
    owned_cpu_run_result reset_event = owned_cpu_run(cpu, UINT64_C(1));
    if (reset_event.reason != OWNED_CPU_BUDGET || reset_event.elapsed_cycles != 40u ||
        reset_event.instructions != 0u) {
        return OWNED_CPU_HOST_FAULT;
    }
    return OWNED_CPU_OK;
}

static void emit_word(uint8_t *program, size_t *length, uint16_t word) {
    program[*length] = (uint8_t)(word >> 8);
    program[*length + 1u] = (uint8_t)word;
    *length += 2u;
}

static void reset_host_fault_stays_terminal_until_reset(void) {
    create_cpu();
    memory.fail_read_on = 1u;
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, owned_cpu_reset(cpu));

    size_t reads_after_fault = memory.reads;
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(reads_after_fault, memory.reads);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, owned_cpu_observe(cpu, &observation));

    memory.fail_read_on = 0u;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_reset(cpu));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(0x100u, observation.pc);
}

static void cycle_budgets_and_opcode_errors_are_explicit(void) {
    create_cpu();
    const uint8_t program[] = {0xff, 0xff}; /* Reserved encoding remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, OWNED_CPU_MAX_CYCLE_BUDGET + UINT64_C(1));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, result.reason);
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.pc);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.fault_pc);
    TEST_ASSERT_EQUAL_HEX16(0xffffu, result.instruction_register);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_UINT64(0u, result.elapsed_cycles);
}

static void sub_instruction_budget_makes_bounded_progress_and_reports_overshoot(void) {
    create_cpu();
    const uint8_t program[] = {0x70, 0x01, 0x72, 0x02};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(1u, result.requested_cycles);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(3u, result.overshoot_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x102u, result.pc);
}

static void moveq_selects_all_registers_and_sign_extends(void) {
    create_cpu();
    const uint8_t program[] = {
        0x70, 0x01, 0x72, 0x02, 0x74, 0x03, 0x76, 0x04,
        0x78, 0x05, 0x7a, 0x06, 0x7c, 0x07, 0x7e, 0x08,
    };
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(32));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(8u, result.instructions);
    TEST_ASSERT_EQUAL_UINT64(32u, result.elapsed_cycles);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    for (unsigned reg = 0u; reg < 8u; ++reg) {
        TEST_ASSERT_EQUAL_UINT32(reg + 1u, observation.data_registers[reg]);
    }

    const uint8_t signed_program[] = {0x70, 0x80, 0x72, 0x00};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(signed_program, sizeof(signed_program)));
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xffffff80), observation.data_registers[0]);
    TEST_ASSERT_BITS_HIGH(0x0008u, observation.sr);
    TEST_ASSERT_BITS_LOW(0x0007u, observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(0u, observation.data_registers[1]);
    TEST_ASSERT_BITS_HIGH(0x0004u, observation.sr);
    TEST_ASSERT_BITS_LOW(0x000au, observation.sr);
}

static void addq_long_uses_eight_for_zero_and_sets_extend_flags(void) {
    create_cpu();
    const uint8_t program[] = {
        0x70, 0xff, /* MOVEQ #-1,D0 */
        0x52, 0x80, /* ADDQ.L #1,D0 */
        0x72, 0x00, /* MOVEQ #0,D1 preserves X and clears C/V */
        0x50, 0x82, /* ADDQ.L #8,D2: encoded quick value zero */
    };
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(12));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(12u, result.elapsed_cycles);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(0u, observation.data_registers[0]);
    TEST_ASSERT_BITS_HIGH(0x0015u, observation.sr);
    TEST_ASSERT_BITS_LOW(0x000au, observation.sr);

    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(0u, observation.data_registers[1]);
    TEST_ASSERT_BITS_HIGH(0x0014u, observation.sr);
    TEST_ASSERT_BITS_LOW(0x0003u, observation.sr);

    result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(8u, observation.data_registers[2]);
    TEST_ASSERT_BITS_LOW(0x001fu, observation.sr);
}

static void addq_long_selects_each_data_register(void) {
    create_cpu();
    uint8_t program[8u * 4u];
    size_t length = 0u;
    for (unsigned reg = 0u; reg < 8u; ++reg) {
        emit_word(program, &length, (uint16_t)(UINT16_C(0x7000) | (uint16_t)(reg << 9)));
    }
    for (unsigned reg = 0u; reg < 8u; ++reg) {
        emit_word(program, &length, (uint16_t)(UINT16_C(0x5280) | (uint16_t)reg));
    }
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, length));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(96));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(16u, result.instructions);
    TEST_ASSERT_EQUAL_UINT64(96u, result.elapsed_cycles);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    for (unsigned reg = 0u; reg < 8u; ++reg) {
        TEST_ASSERT_EQUAL_UINT32(1u, observation.data_registers[reg]);
    }
}

static void addq_long_reports_signed_positive_overflow(void) {
    create_cpu();
    const uint8_t program[] = {0x52, 0x80}; /* ADDQ.L #1,D0 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      owned_cpu_test_seed_data_register(cpu, 0u, UINT32_C(0x7fffffff)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x80000000), observation.data_registers[0]);
    TEST_ASSERT_BITS_HIGH(0x000au, observation.sr);
    TEST_ASSERT_BITS_LOW(0x0015u, observation.sr);
}

static void move_long_uses_each_data_register_and_ordered_words(void) {
    create_cpu();
    uint8_t program[8u * 2u + 8u * 6u];
    size_t length = 0u;
    for (unsigned reg = 0u; reg < 8u; ++reg) {
        emit_word(program, &length, (uint16_t)(UINT16_C(0x7000) | (uint16_t)(reg << 9) |
                                               (uint16_t)(reg + 1u)));
    }
    for (unsigned reg = 0u; reg < 8u; ++reg) {
        emit_word(program, &length, (uint16_t)(UINT16_C(0x23c0) | (uint16_t)reg));
        uint32_t destination = UINT32_C(0x1000) + (uint32_t)(reg * 4u);
        emit_word(program, &length, (uint16_t)(destination >> 16));
        emit_word(program, &length, (uint16_t)destination);
    }
    TEST_ASSERT_EQUAL_UINT(sizeof(program), length);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, length));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(192));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(16u, result.instructions);
    TEST_ASSERT_EQUAL_UINT64(192u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT(16u, memory.successful_writes);
    for (unsigned reg = 0u; reg < 8u; ++reg) {
        uint32_t destination = UINT32_C(0x1000) + (uint32_t)(reg * 4u);
        size_t event = (size_t)(reg * 2u);
        TEST_ASSERT_EQUAL_HEX32(destination, memory.write_addresses[event]);
        TEST_ASSERT_EQUAL_UINT16(0u, memory.write_values[event]);
        TEST_ASSERT_EQUAL_HEX32(destination + 2u, memory.write_addresses[event + 1u]);
        TEST_ASSERT_EQUAL_UINT16((uint16_t)(reg + 1u), memory.write_values[event + 1u]);
    }
}

static void move_long_clears_nzvc_and_preserves_x(void) {
    create_cpu();
    const uint8_t program[] = {
        0x70, 0xff,             /* MOVEQ #-1,D0 sets N. */
        0x52, 0x80,             /* ADDQ.L #1,D0 sets X, C and Z. */
        0x23, 0xc0, 0x00, 0x00, 0x10, 0x00,
    };
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(32));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(3u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(0u, observation.data_registers[0]);
    TEST_ASSERT_BITS_HIGH(0x0014u, observation.sr);
    TEST_ASSERT_BITS_LOW(0x000bu, observation.sr);
    TEST_ASSERT_EQUAL_UINT(2u, memory.successful_writes);
}

static void stop_loads_sr_and_switches_to_the_selected_stack_bank(void) {
    create_cpu();
    const uint8_t program[] = {0x4e, 0x72, 0x00, 0x00};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_STOPPED, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x104u, result.pc);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX16(0u, observation.sr);
    TEST_ASSERT_EQUAL_HEX32(0x2000u, observation.ssp);
    TEST_ASSERT_EQUAL_HEX32(0u, observation.address_registers[7]);
    TEST_ASSERT_EQUAL_UINT8(1u, observation.stopped);
}

static void unsupported_modes_and_illegal_word_report_pc_and_ir(void) {
    create_cpu();
    const uint8_t unsupported_move[] = {0x21, 0x80};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(unsupported_move, sizeof(unsupported_move)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.fault_pc);
    TEST_ASSERT_EQUAL_HEX16(0x2180u, result.instruction_register);

    const uint8_t guest_illegal[] = {0x4a, 0xfc};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(guest_illegal, sizeof(guest_illegal)));
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(34u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0u, result.pc);

    const uint8_t unsupported_moveq[] = {0x71, 0x00};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(unsupported_moveq, sizeof(unsupported_moveq)));
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.fault_pc);
    TEST_ASSERT_EQUAL_HEX16(0x7100u, result.instruction_register);
}

static void odd_reset_vectors_and_odd_store_are_explicit(void) {
    create_cpu();
    set_vector(4u, UINT32_C(0x101));
    TEST_ASSERT_EQUAL(OWNED_CPU_ADDRESS_ERROR, owned_cpu_reset(cpu));
    set_vector(4u, UINT32_C(0x100));
    set_vector(0u, UINT32_C(0x2001));
    TEST_ASSERT_EQUAL(OWNED_CPU_ADDRESS_ERROR, owned_cpu_reset(cpu));

    set_vector(0u, UINT32_C(0x2000));
    const uint8_t odd_store[] = {0x70, 0x01, 0x23, 0xc0, 0x00, 0x00, 0x10, 0x01};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(odd_store, sizeof(odd_store)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(54));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(54u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x102u, result.fault_pc);
    TEST_ASSERT_EQUAL_HEX16(0x23c0u, result.instruction_register);
    TEST_ASSERT_EQUAL_UINT(7u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(0x1ffcu, memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX32(0x1ffeu, memory.write_addresses[1]);
    TEST_ASSERT_EQUAL_HEX32(0x1ffau, memory.write_addresses[2]);
    TEST_ASSERT_EQUAL_HEX32(0x1ff8u, memory.write_addresses[3]);
    TEST_ASSERT_EQUAL_HEX32(0x1ff4u, memory.write_addresses[4]);
    TEST_ASSERT_EQUAL_HEX32(0x1ff6u, memory.write_addresses[5]);
    TEST_ASSERT_EQUAL_HEX32(0x1ff2u, memory.write_addresses[6]);
}

static void incomplete_extension_fetch_becomes_terminal_host_fault(void) {
    create_cpu();
    set_vector(4u, UINT32_C(0x1fc));
    memory.rom[0x1fcu] = 0x23;
    memory.rom[0x1fdu] = 0xc0;
    memory.rom[0x1feu] = 0x00;
    memory.rom[0x1ffu] = 0x00;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_reset(cpu));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(100));
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_HEX32(0x1fcu, result.fault_pc);
    TEST_ASSERT_EQUAL_HEX16(0x23c0u, result.instruction_register);
    size_t reads_after_fault = memory.reads;
    result = owned_cpu_run(cpu, UINT64_C(100));
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(reads_after_fault, memory.reads);
}

static void write_fault_keeps_the_successful_first_word(void) {
    create_cpu();
    const uint8_t program[] = {0x70, 0x01, 0x23, 0xc0, 0x00, 0x00, 0x10, 0x00};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    memory.fail_write_on = 2u;
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(100));
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT(2u, memory.write_attempts);
    TEST_ASSERT_EQUAL_UINT(1u, memory.successful_writes);
    TEST_ASSERT_EQUAL_HEX32(0x1000u, memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX32(0x1002u, memory.write_addresses[1]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, owned_cpu_observe(cpu, &observation));
}

static void absolute_long_second_word_wraps_in_defined_unsigned_space(void) {
    create_cpu();
    const uint8_t program[] = {
        0x70, 0x01,
        0x23, 0xc0, 0xff, 0xff, 0xff, 0xfe,
    };
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(24));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(2u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(2u, memory.successful_writes);
    TEST_ASSERT_EQUAL_HEX32(0x00fffffeu, memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX32(0u, memory.write_addresses[1]);
    TEST_ASSERT_EQUAL_UINT16(0u, memory.write_values[0]);
    TEST_ASSERT_EQUAL_UINT16(1u, memory.write_values[1]);
}

static void program_counter_keeps_logical_high_byte_while_bus_masks_to_24_bits(void) {
    create_cpu();
    const uint8_t program[] = {0x70, 0x01};
    set_vector(4u, UINT32_C(0x12000100));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(0x12000100u, observation.pc);
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_HEX32(0x12000102u, result.pc);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_UINT32(1u, observation.data_registers[0]);
}

static void model_allocator_irq_and_invalid_budget_reject_without_side_effects(void) {
    create_cpu();
    const uint8_t program[] = {0x70, 0x01};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_observation before;
    owned_cpu_observation after;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &before));
    size_t reads_before = memory.reads;
    size_t writes_before = memory.write_attempts;
    owned_cpu_run_result result = owned_cpu_run(cpu, OWNED_CPU_MAX_CYCLE_BUDGET + UINT64_C(1));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, result.reason);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, owned_cpu_set_irq(cpu, 8u));
    TEST_ASSERT_EQUAL_UINT(reads_before, memory.reads);
    TEST_ASSERT_EQUAL_UINT(writes_before, memory.write_attempts);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &after));
    TEST_ASSERT_EQUAL_INT(0, memcmp(&before, &after, sizeof(before)));

    owned_cpu *rejected = cpu;
    owned_cpu_bus bus = {&memory, read_guest_word, write_guest_word};
    owned_cpu_allocator allocator = {NULL, allocate_memory, release_memory};
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_MODEL,
                      owned_cpu_create(UINT32_C(68010), bus, allocator, &rejected));
    TEST_ASSERT_NULL(rejected);
    rejected = cpu;
    allocator.allocate = fail_allocate;
    TEST_ASSERT_EQUAL(OWNED_CPU_ALLOCATION_FAILURE,
                      owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, allocator, &rejected));
    TEST_ASSERT_NULL(rejected);
    rejected = cpu;
    bus.write16 = NULL;
    allocator.allocate = allocate_memory;
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, allocator, &rejected));
    TEST_ASSERT_NULL(rejected);

    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 3u));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &after));
    TEST_ASSERT_EQUAL_UINT8(3u, after.irq_level);
    TEST_ASSERT_EQUAL_UINT8(0u, after.irq7_pending);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 7u));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &after));
    TEST_ASSERT_EQUAL_UINT8(1u, after.irq7_pending);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 7u));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 0u));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &after));
    TEST_ASSERT_EQUAL_UINT8(1u, after.irq7_pending);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(reset_host_fault_stays_terminal_until_reset);
    RUN_TEST(cycle_budgets_and_opcode_errors_are_explicit);
    RUN_TEST(sub_instruction_budget_makes_bounded_progress_and_reports_overshoot);
    RUN_TEST(moveq_selects_all_registers_and_sign_extends);
    RUN_TEST(addq_long_uses_eight_for_zero_and_sets_extend_flags);
    RUN_TEST(addq_long_selects_each_data_register);
    RUN_TEST(addq_long_reports_signed_positive_overflow);
    RUN_TEST(move_long_uses_each_data_register_and_ordered_words);
    RUN_TEST(move_long_clears_nzvc_and_preserves_x);
    RUN_TEST(stop_loads_sr_and_switches_to_the_selected_stack_bank);
    RUN_TEST(unsupported_modes_and_illegal_word_report_pc_and_ir);
    RUN_TEST(odd_reset_vectors_and_odd_store_are_explicit);
    RUN_TEST(incomplete_extension_fetch_becomes_terminal_host_fault);
    RUN_TEST(write_fault_keeps_the_successful_first_word);
    RUN_TEST(absolute_long_second_word_wraps_in_defined_unsigned_space);
    RUN_TEST(program_counter_keeps_logical_high_byte_while_bus_masks_to_24_bits);
    RUN_TEST(model_allocator_irq_and_invalid_budget_reject_without_side_effects);
    return UNITY_END();
}
