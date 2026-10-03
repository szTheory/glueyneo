/* SPDX-License-Identifier: MIT */
#include "cpu.h"
#include "unity.h"

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum { MEMORY_SIZE = 0x4000, ACCESS_CAPACITY = 512 };

typedef struct {
    uint32_t address;
    uint16_t value;
    uint8_t write;
    uint8_t success;
} bus_access;

typedef struct {
    uint8_t bytes[MEMORY_SIZE];
    bus_access events[ACCESS_CAPACITY];
    size_t accesses;
    int fail_read;
    int fail_write;
    uint32_t fail_read_address;
    uint32_t fail_write_address;
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

static int read_word(void *userdata, uint32_t address, uint16_t *value) {
    memory_bus *bus = userdata;
    if (bus == NULL || value == NULL || (address & 1u) != 0u || address >= MEMORY_SIZE - 1u) {
        return 0;
    }
    int success = !(bus->fail_read && address == bus->fail_read_address);
    if (bus->accesses < ACCESS_CAPACITY) {
        bus->events[bus->accesses] = (bus_access){address, 0u, 0u, (uint8_t)success};
    }
    bus->accesses++;
    if (!success) {
        return 0;
    }
    *value = (uint16_t)(((uint16_t)bus->bytes[address] << 8) | bus->bytes[address + 1u]);
    if (bus->accesses <= ACCESS_CAPACITY) {
        bus->events[bus->accesses - 1u].value = *value;
    }
    return 1;
}

static int write_word(void *userdata, uint32_t address, uint16_t value) {
    memory_bus *bus = userdata;
    if (bus == NULL || (address & 1u) != 0u || address >= MEMORY_SIZE - 1u) {
        return 0;
    }
    int success = !(bus->fail_write && address == bus->fail_write_address);
    if (bus->accesses < ACCESS_CAPACITY) {
        bus->events[bus->accesses] = (bus_access){address, value, 1u, (uint8_t)success};
    }
    bus->accesses++;
    if (!success) {
        return 0;
    }
    bus->bytes[address] = (uint8_t)(value >> 8);
    bus->bytes[address + 1u] = (uint8_t)value;
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

static void put_word(uint32_t address, uint16_t value) {
    memory.bytes[address] = (uint8_t)(value >> 8);
    memory.bytes[address + 1u] = (uint8_t)value;
}

static void put_long(uint32_t address, uint32_t value) {
    put_word(address, (uint16_t)(value >> 16));
    put_word(address + 2u, (uint16_t)value);
}

static uint16_t get_word(uint32_t address) {
    return (uint16_t)(((uint16_t)memory.bytes[address] << 8) | memory.bytes[address + 1u]);
}

static uint32_t get_long(uint32_t address) {
    return ((uint32_t)get_word(address) << 16) | (uint32_t)get_word(address + 2u);
}

static void put_vector(unsigned vector, uint32_t address) {
    put_long((uint32_t)vector * UINT32_C(4), address);
}

static void clear_trace(void) {
    memory.accesses = 0u;
    memset(memory.events, 0, sizeof(memory.events));
}

static void create_machine(void) {
    put_long(0u, UINT32_C(0x3000));
    put_long(4u, UINT32_C(0x100));
    owned_cpu_bus bus = {&memory, read_word, write_word};
    owned_cpu_allocator allocator = {NULL, allocate_memory, release_memory};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, allocator, &cpu));
    TEST_ASSERT_NOT_NULL(cpu);
}

static void install_program(const uint8_t *program, size_t length) {
    TEST_ASSERT_NOT_NULL(program);
    TEST_ASSERT_TRUE(length <= MEMORY_SIZE - 0x100u);
    memcpy(memory.bytes + 0x100u, program, length);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_reset(cpu));
    memory.accesses = 0u;
}

static void run_reset_event(void) {
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(40u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.pc);
    clear_trace();
}

static void observe(owned_cpu_observation *out) {
    TEST_ASSERT_NOT_NULL(out);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, out));
}

static void reset_debt_is_consumed_once_and_nop_executes(void) {
    create_machine();
    const uint8_t program[] = {0x4e, 0x71, 0x4e, 0x71};
    install_program(program, sizeof(program));

    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(0));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(0u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT(0u, memory.accesses);
    owned_cpu_observation initial_observation;
    observe(&initial_observation);
    TEST_ASSERT_EQUAL_UINT8(1u, initial_observation.reset_pending);
    TEST_ASSERT_EQUAL_UINT64(0u, initial_observation.total_cycles);

    result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL_UINT64(40u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(39u, result.overshoot_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.pc);
    TEST_ASSERT_EQUAL_UINT(0u, memory.accesses);

    result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(3u, result.overshoot_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x102u, result.pc);
    TEST_ASSERT_EQUAL_UINT(1u, memory.accesses);
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_HEX16(0x2700u, observation.sr);
    TEST_ASSERT_EQUAL_HEX32(0u, observation.data_registers[0]);
    TEST_ASSERT_EQUAL_HEX32(0u, observation.address_registers[0]);
}

static void reset_instruction_is_distinct_and_observable(void) {
    create_machine();
    const uint8_t program[] = {0x4e, 0x70};
    install_program(program, sizeof(program));
    run_reset_event();

    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(132u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x102u, result.pc);
    TEST_ASSERT_EQUAL_UINT(1u, memory.accesses);
    TEST_ASSERT_EQUAL_UINT8(0u, memory.events[0].write);
    TEST_ASSERT_EQUAL_HEX32(0x100u, memory.events[0].address);

    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT64(1u, observation.reset_signal_events);
    TEST_ASSERT_EQUAL_UINT64(132u, observation.instruction_cycles);
    TEST_ASSERT_EQUAL_HEX16(0x2700u, observation.sr);
}

static void trap_stacks_next_pc_then_addq_rte_resumes_stop(void) {
    create_machine();
    put_vector(32u, UINT32_C(0x180));
    const uint8_t program[] = {0x4e, 0x40, 0x4e, 0x72, 0x27, 0x00};
    const uint8_t handler[] = {0x52, 0x81, 0x4e, 0x73};
    install_program(program, sizeof(program));
    memcpy(memory.bytes + 0x180u, handler, sizeof(handler));
    run_reset_event();

    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(34u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x180u, result.pc);
    TEST_ASSERT_EQUAL_UINT(6u, memory.accesses);
    TEST_ASSERT_EQUAL_UINT8(0u, memory.events[0].write);
    TEST_ASSERT_EQUAL_HEX32(0x100u, memory.events[0].address);
    TEST_ASSERT_EQUAL_UINT8(1u, memory.events[1].write);
    TEST_ASSERT_EQUAL_HEX32(0x2ffcu, memory.events[1].address);
    TEST_ASSERT_EQUAL_UINT8(1u, memory.events[2].write);
    TEST_ASSERT_EQUAL_HEX32(0x2ffeu, memory.events[2].address);
    TEST_ASSERT_EQUAL_UINT8(1u, memory.events[3].write);
    TEST_ASSERT_EQUAL_HEX32(0x2ffau, memory.events[3].address);
    TEST_ASSERT_EQUAL_UINT8(0u, memory.events[4].write);
    TEST_ASSERT_EQUAL_HEX32(0x80u, memory.events[4].address);
    TEST_ASSERT_EQUAL_UINT8(0u, memory.events[5].write);
    TEST_ASSERT_EQUAL_HEX32(0x82u, memory.events[5].address);
    TEST_ASSERT_EQUAL_HEX16(0x2700u, get_word(0x2ffau));
    TEST_ASSERT_EQUAL_HEX32(0x102u, get_long(0x2ffcu));

    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_HEX32(0x2ffau, observation.address_registers[7]);
    TEST_ASSERT_EQUAL_UINT8(32u, observation.last_exception_vector);
    TEST_ASSERT_EQUAL_UINT64(34u, observation.exception_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, observation.instructions);

    result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT32(1u, observation.data_registers[1]);

    result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL_UINT64(20u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    observe(&observation);
    TEST_ASSERT_EQUAL_HEX32(0x102u, observation.pc);
    TEST_ASSERT_EQUAL_HEX32(0x3000u, observation.address_registers[7]);
    TEST_ASSERT_EQUAL_HEX16(0x2700u, observation.sr);

    result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL(OWNED_CPU_STOPPED, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
}

static void canonical_unsupported_has_only_opcode_fetch(void) {
    create_machine();
    put_vector(4u, UINT32_C(0x180));
    const uint8_t program[] = {0x4a, 0xfc};
    install_program(program, sizeof(program));
    run_reset_event();

    for (unsigned reg = 0u; reg < 8u; ++reg) {
        TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                          owned_cpu_test_seed_data_register(cpu, reg, 0x12345678u + reg));
    }
    /* Neither vector 4 nor an inaccessible/odd exception stack may be used. */
    memory.fail_read = 1;
    memory.fail_read_address = 0x10u;
    memory.fail_write = 1;
    memory.fail_write_address = 0x2ffcu;
    for (unsigned odd_stack = 0u; odd_stack < 2u; ++odd_stack) {
        TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_test_seed_execution_state(
            cpu, 0x2700u, 0x3800u, 0x3000u + odd_stack, 0x100u));
        owned_cpu_observation before, after;
        observe(&before);
        uint8_t bytes_before[MEMORY_SIZE];
        memcpy(bytes_before, memory.bytes, sizeof(bytes_before));
        for (unsigned repeat = 0u; repeat < 2u; ++repeat) {
            clear_trace();
            owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(1));
            TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
            TEST_ASSERT_EQUAL_HEX32(0x100u, result.pc);
            TEST_ASSERT_EQUAL_HEX32(0x100u, result.fault_pc);
            TEST_ASSERT_EQUAL_HEX16(0x4afcu, result.instruction_register);
            TEST_ASSERT_EQUAL_UINT64(0u, result.elapsed_cycles);
            TEST_ASSERT_EQUAL_UINT64(0u, result.overshoot_cycles);
            TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
            TEST_ASSERT_EQUAL_UINT(1u, memory.accesses);
            TEST_ASSERT_EQUAL_HEX32(0x100u, memory.events[0].address);
            TEST_ASSERT_EQUAL_HEX16(0x4afcu, memory.events[0].value);
            TEST_ASSERT_EQUAL_UINT8(0u, memory.events[0].write);
            TEST_ASSERT_EQUAL_UINT8(1u, memory.events[0].success);
            observe(&after);
            TEST_ASSERT_EQUAL_MEMORY(&before, &after, sizeof(before));
            TEST_ASSERT_EQUAL_MEMORY(bytes_before, memory.bytes, sizeof(bytes_before));
        }
    }
}

static void canonical_rejection_retains_prior_reset_irq_and_instruction_charges(void) {
    create_machine();
    const uint8_t program[] = {0x4a, 0xfc};
    install_program(program, sizeof(program));
    owned_cpu_run_result result = owned_cpu_run(cpu, 41u);
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_UINT64(40u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_UINT64(0u, result.overshoot_cycles);
    put_vector(31u, 0x180u);
    put_word(0x180u, 0x4afcu);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 7u));
    clear_trace();
    result = owned_cpu_run(cpu, 45u);
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_UINT64(44u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x180u, result.pc);
    TEST_ASSERT_EQUAL_HEX32(0x180u, result.fault_pc);
    TEST_ASSERT_EQUAL_UINT(6u, memory.accesses);
    TEST_ASSERT_EQUAL_HEX32(0x180u, memory.events[5].address);
    owned_cpu_observation after_irq;
    observe(&after_irq);
    TEST_ASSERT_EQUAL_UINT64(44u, after_irq.exception_cycles);
    TEST_ASSERT_EQUAL_UINT64(84u, after_irq.total_cycles);
    TEST_ASSERT_EQUAL_UINT8(31u, after_irq.last_exception_vector);
    put_word(0x180u, 0x4e71u);
    put_word(0x182u, 0x4afcu);
    result = owned_cpu_run(cpu, 5u);
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x182u, result.fault_pc);
    observe(&after_irq);
    TEST_ASSERT_EQUAL_UINT64(88u, after_irq.total_cycles);
    TEST_ASSERT_EQUAL_UINT64(4u, after_irq.instruction_cycles);
    TEST_ASSERT_EQUAL_UINT64(44u, after_irq.exception_cycles);
}

static void canonical_failed_opcode_fetch_remains_a_host_fault(void) {
    create_machine();
    const uint8_t program[] = {0x4a, 0xfc};
    install_program(program, sizeof(program));
    run_reset_event();
    memory.fail_read = 1;
    memory.fail_read_address = 0x100u;
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT64(0u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT(1u, memory.accesses);
    TEST_ASSERT_EQUAL_UINT8(0u, memory.events[0].success);
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(1u, memory.accesses);
}

static void canonical_unsupported_wrong_status_expectation(void) {
    create_machine();
    const uint8_t program[] = {0x4a, 0xfc};
    install_program(program, sizeof(program));
    run_reset_event();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_MESSAGE(OWNED_CPU_BUDGET, result.reason,
                              "canonical unsupported result-status assertion");
}

static void move_word_absolute_long_loads_every_data_register(void) {
    for (unsigned reg = 0u; reg < 8u; ++reg) {
        if (cpu != NULL) owned_cpu_destroy(cpu);
        cpu = NULL;
        memset(&memory, 0, sizeof(memory));
        create_machine();
        put_word(0x200u, 0x8001u);
        uint16_t opcode = (uint16_t)(0x3039u | (uint16_t)(reg << 9));
        const uint8_t program[] = {(uint8_t)(opcode >> 8), (uint8_t)opcode,
                                   0x00, 0x00, 0x02, 0x00};
        install_program(program, sizeof(program));
        run_reset_event();
        TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                          owned_cpu_test_seed_data_register(cpu, reg, 0x12345678u));
        clear_trace();
        owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
        TEST_ASSERT_EQUAL_UINT64(16u, result.elapsed_cycles);
        TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
        TEST_ASSERT_EQUAL_UINT(4u, memory.accesses);
        TEST_ASSERT_EQUAL_HEX32(0x100u, memory.events[0].address);
        TEST_ASSERT_EQUAL_HEX32(0x102u, memory.events[1].address);
        TEST_ASSERT_EQUAL_HEX32(0x104u, memory.events[2].address);
        TEST_ASSERT_EQUAL_HEX32(0x200u, memory.events[3].address);
        owned_cpu_observation observation;
        observe(&observation);
        TEST_ASSERT_EQUAL_HEX32(0x12348001u, observation.data_registers[reg]);
        TEST_ASSERT_EQUAL_HEX16(0x2708u, observation.sr);
    }
}

static void odd_word_source_stacks_manual_derived_address_error_frame(void) {
    create_machine();
    put_vector(3u, 0x180u);
    const uint8_t program[] = {0x30, 0x39, 0x00, 0x00, 0x02, 0x01};
    install_program(program, sizeof(program));
    run_reset_event();
    clear_trace();

    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(50u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x180u, result.pc);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.fault_pc);
    TEST_ASSERT_EQUAL_HEX16(0x3039u, result.instruction_register);
    TEST_ASSERT_EQUAL_UINT(12u, memory.accesses);
    TEST_ASSERT_EQUAL_UINT8(0u, memory.events[0].write);
    TEST_ASSERT_EQUAL_HEX32(0x100u, memory.events[0].address);
    TEST_ASSERT_EQUAL_HEX32(0x102u, memory.events[1].address);
    TEST_ASSERT_EQUAL_HEX32(0x104u, memory.events[2].address);
    TEST_ASSERT_EQUAL_UINT8(1u, memory.events[3].write);
    TEST_ASSERT_EQUAL_HEX32(0x2ffcu, memory.events[3].address);
    TEST_ASSERT_EQUAL_HEX32(0x2ffeu, memory.events[4].address);
    TEST_ASSERT_EQUAL_HEX32(0x2ffau, memory.events[5].address);
    TEST_ASSERT_EQUAL_HEX32(0x2ff8u, memory.events[6].address);
    TEST_ASSERT_EQUAL_HEX32(0x2ff4u, memory.events[7].address);
    TEST_ASSERT_EQUAL_HEX32(0x2ff6u, memory.events[8].address);
    TEST_ASSERT_EQUAL_HEX32(0x2ff2u, memory.events[9].address);
    TEST_ASSERT_EQUAL_UINT8(0u, memory.events[10].write);
    TEST_ASSERT_EQUAL_HEX32(0x0cu, memory.events[10].address);
    TEST_ASSERT_EQUAL_HEX32(0x0eu, memory.events[11].address);
    TEST_ASSERT_EQUAL_HEX16(0x001du, get_word(0x2ff2u));
    TEST_ASSERT_EQUAL_HEX32(0x00000201u, get_long(0x2ff4u));
    TEST_ASSERT_EQUAL_HEX16(0x3039u, get_word(0x2ff8u));
    TEST_ASSERT_EQUAL_HEX16(0x2700u, get_word(0x2ffau));
    TEST_ASSERT_EQUAL_HEX32(0x100u, get_long(0x2ffcu));
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT8(3u, observation.last_exception_vector);
    TEST_ASSERT_EQUAL_UINT64(50u, observation.exception_cycles);
}

static void odd_long_destination_stacks_a_write_address_error(void) {
    create_machine();
    put_vector(3u, 0x180u);
    const uint8_t program[] = {0x23, 0xc0, 0x00, 0x00, 0x02, 0x01};
    install_program(program, sizeof(program));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      owned_cpu_test_seed_data_register(cpu, 0u, 0xaabbccddu));
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(50u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(12u, memory.accesses);
    TEST_ASSERT_EQUAL_HEX16(0x000du, get_word(0x2ff2u));
    TEST_ASSERT_EQUAL_HEX32(0x00000201u, get_long(0x2ff4u));
    TEST_ASSERT_EQUAL_HEX16(0x23c0u, get_word(0x2ff8u));
    TEST_ASSERT_EQUAL_HEX32(0x100u, get_long(0x2ffcu));
    TEST_ASSERT_EQUAL_HEX32(0u, get_long(0x200u));
}

static void odd_instruction_fetch_enters_group_zero_without_an_odd_bus_read(void) {
    create_machine();
    put_vector(3u, 0x180u);
    const uint8_t aligned[] = {0x4e, 0x71};
    install_program(aligned, sizeof(aligned));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_test_seed_execution_state(
                                        cpu, 0x2700u, 0u, 0x3000u, 0x101u));
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(50u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(9u, memory.accesses);
    TEST_ASSERT_EQUAL_HEX32(0x2ffcu, memory.events[0].address);
    for (size_t index = 0u; index < memory.accesses; ++index) {
        TEST_ASSERT_EQUAL_UINT32(0u, memory.events[index].address & 1u);
    }
    TEST_ASSERT_EQUAL_HEX16(0x0016u, get_word(0x2ff2u));
    TEST_ASSERT_EQUAL_HEX32(0x00000101u, get_long(0x2ff4u));
    TEST_ASSERT_EQUAL_HEX16(0u, get_word(0x2ff8u));
    TEST_ASSERT_EQUAL_HEX32(0x101u, get_long(0x2ffcu));
}

static void twenty_four_bit_bus_address_wrap_is_explicit(void) {
    create_machine();
    const uint8_t program[] = {0x23, 0xc0, 0x01, 0x00, 0x00, 0x00};
    install_program(program, sizeof(program));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      owned_cpu_test_seed_data_register(cpu, 0u, 0xaabbccddu));
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(20u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT(5u, memory.accesses);
    TEST_ASSERT_EQUAL_HEX32(0u, memory.events[3].address);
    TEST_ASSERT_EQUAL_HEX16(0xaabbu, get_word(0u));
    TEST_ASSERT_EQUAL_HEX32(2u, memory.events[4].address);
    TEST_ASSERT_EQUAL_HEX16(0xccddu, get_word(2u));
}

static void failed_second_word_write_keeps_first_word_and_becomes_terminal(void) {
    create_machine();
    const uint8_t program[] = {0x23, 0xc0, 0x00, 0x00, 0x02, 0x00};
    install_program(program, sizeof(program));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      owned_cpu_test_seed_data_register(cpu, 0u, 0xaabbccddu));
    memory.fail_write = 1;
    memory.fail_write_address = 0x202u;
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(5u, memory.accesses);
    TEST_ASSERT_EQUAL_HEX16(0xaabbu, get_word(0x200u));
    TEST_ASSERT_EQUAL_HEX16(0u, get_word(0x202u));
    size_t accesses = memory.accesses;
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(accesses, memory.accesses);
}

static void irq3_stays_masked_until_move_to_sr_then_enters_as_its_own_event(void) {
    create_machine();
    put_vector(27u, 0x180u);
    const uint8_t program[] = {0x4e, 0x71, 0x46, 0xfc, 0x20, 0x00,
                               0x4e, 0x72, 0x27, 0x00};
    const uint8_t handler[] = {0x52, 0x81, 0x4e, 0x73};
    install_program(program, sizeof(program));
    memcpy(memory.bytes + 0x180u, handler, sizeof(handler));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 3u));

    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x102u, result.pc);
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(12u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x106u, result.pc);
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(44u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x180u, result.pc);
    TEST_ASSERT_EQUAL_HEX16(0x2000u, get_word(0x2ffau));
    TEST_ASSERT_EQUAL_HEX32(0x106u, get_long(0x2ffcu));
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_HEX16(0x2300u, observation.sr);
    TEST_ASSERT_EQUAL_UINT8(27u, observation.last_exception_vector);
    TEST_ASSERT_EQUAL_UINT64(44u, observation.exception_cycles);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 0u));
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT32(1u, observation.data_registers[1]);
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(20u, result.elapsed_cycles);
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
}

static void irq7_edge_is_unmasked_and_held_level_waits_for_mask_change(void) {
    create_machine();
    put_vector(31u, 0x180u);
    const uint8_t program[] = {0x4e, 0x71, 0x4e, 0x71};
    const uint8_t handler[] = {0x4e, 0x71, 0x46, 0xfc, 0x20, 0x00};
    install_program(program, sizeof(program));
    memcpy(memory.bytes + 0x180u, handler, sizeof(handler));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 7u));

    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(44u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x180u, result.pc);
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT8(0u, observation.irq7_pending);
    TEST_ASSERT_EQUAL_UINT8(31u, observation.last_exception_vector);
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT8(31u, observation.last_exception_vector);
    TEST_ASSERT_EQUAL_HEX16(0x2700u, observation.sr);
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(12u, result.elapsed_cycles);
    observe(&observation);
    TEST_ASSERT_EQUAL_HEX16(0x2000u, observation.sr);
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(44u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT8(31u, observation.last_exception_vector);
    TEST_ASSERT_EQUAL_HEX32(0x180u, observation.pc);

    /* A second rising edge is remembered even when the pin is deasserted
     * before the next instruction boundary samples it. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 0u));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 7u));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(cpu, 0u));
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(44u, result.elapsed_cycles);
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT8(31u, observation.last_exception_vector);
    TEST_ASSERT_EQUAL_HEX32(0x180u, observation.pc);
}

static void user_mode_privileged_instructions_raise_vector_eight(void) {
    const uint16_t opcodes[] = {0x4e72u, 0x4e70u, 0x4e73u, 0x46fcu};
    const uint8_t extensions[][2] = {{0x27u, 0x00u}, {0u, 0u}, {0u, 0u}, {0u, 0u}};
    for (size_t index = 0u; index < sizeof(opcodes) / sizeof(opcodes[0]); ++index) {
        if (cpu != NULL) owned_cpu_destroy(cpu);
        cpu = NULL;
        memset(&memory, 0, sizeof(memory));
        create_machine();
        put_vector(8u, 0x180u);
        uint16_t opcode = opcodes[index];
        const uint8_t program[] = {(uint8_t)(opcode >> 8), (uint8_t)opcode,
                                   extensions[index][0], extensions[index][1]};
        install_program(program, sizeof(program));
        run_reset_event();
        TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_test_seed_execution_state(
                                            cpu, 0u, 0x3800u, 0x3000u, 0x100u));
        clear_trace();
        owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
        TEST_ASSERT_EQUAL_UINT64(34u, result.elapsed_cycles);
        TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
        TEST_ASSERT_EQUAL_HEX32(0x180u, result.pc);
        TEST_ASSERT_EQUAL_HEX16(0u, get_word(0x2ffau));
        TEST_ASSERT_EQUAL_HEX32(0x100u, get_long(0x2ffcu));
        owned_cpu_observation observation;
        observe(&observation);
        TEST_ASSERT_EQUAL_UINT8(8u, observation.last_exception_vector);
        TEST_ASSERT_EQUAL_HEX16(0x2000u, observation.sr);
        TEST_ASSERT_EQUAL_HEX32(0x2ffau, observation.address_registers[7]);
        TEST_ASSERT_EQUAL_HEX32(0x3800u, observation.usp);
    }
}

static void stopped_cpu_idles_to_the_exact_request_without_bus_access(void) {
    create_machine();
    const uint8_t stop[] = {0x4e, 0x72, 0x27, 0x00};
    install_program(stop, sizeof(stop));
    run_reset_event();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_STOPPED, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    size_t accesses = memory.accesses;
    result = owned_cpu_run(cpu, 9u);
    TEST_ASSERT_EQUAL(OWNED_CPU_STOPPED, result.reason);
    TEST_ASSERT_EQUAL_UINT64(9u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT(accesses, memory.accesses);
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT64(9u, observation.idle_cycles);
    TEST_ASSERT_EQUAL_UINT64(53u, observation.total_cycles);
    TEST_ASSERT_EQUAL_UINT64(4u, observation.instruction_cycles);
}

static void event_limits_and_counter_overflow_are_explicit(void) {
    create_machine();
    const uint8_t stop[] = {0x4e, 0x72, 0x27, 0x00};
    install_program(stop, sizeof(stop));
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, 0u);
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    result = owned_cpu_run(cpu, OWNED_CPU_MAX_CYCLE_BUDGET + 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, result.reason);
    result = owned_cpu_run(cpu, UINT64_MAX);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, result.reason);
    TEST_ASSERT_EQUAL_UINT(0u, memory.accesses);
    result = owned_cpu_run(cpu, OWNED_CPU_MAX_CYCLE_BUDGET);
    TEST_ASSERT_EQUAL(OWNED_CPU_STOPPED, result.reason);
    TEST_ASSERT_EQUAL_UINT64(OWNED_CPU_MAX_CYCLE_BUDGET, result.elapsed_cycles);
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT64(OWNED_CPU_MAX_CYCLE_BUDGET, observation.total_cycles);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_reset(cpu));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_test_seed_counters(
                                        cpu, UINT64_MAX, 0u, 0u, 0u, 0u));
    clear_trace();
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_COUNTER_OVERFLOW, result.reason);
    TEST_ASSERT_EQUAL_UINT(1u, memory.accesses);
    TEST_ASSERT_EQUAL_HEX32(0x100u, memory.events[0].address);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.pc);
}

static void reset_request_boundaries_never_split_the_reset_event(void) {
    const uint64_t requests[] = {39u, 40u, 41u};
    const uint64_t expected[] = {40u, 40u, 44u};
    const uint64_t overshoot[] = {1u, 0u, 3u};
    for (size_t index = 0u; index < sizeof(requests) / sizeof(requests[0]); ++index) {
        if (cpu != NULL) owned_cpu_destroy(cpu);
        cpu = NULL;
        memset(&memory, 0, sizeof(memory));
        create_machine();
        const uint8_t nop[] = {0x4e, 0x71};
        install_program(nop, sizeof(nop));
        owned_cpu_run_result result = owned_cpu_run(cpu, requests[index]);
        TEST_ASSERT_EQUAL_UINT64(expected[index], result.elapsed_cycles);
        TEST_ASSERT_EQUAL_UINT64(overshoot[index], result.overshoot_cycles);
        TEST_ASSERT_EQUAL_UINT64(index == 2u ? 1u : 0u, result.instructions);
        TEST_ASSERT_EQUAL_HEX32(index == 2u ? 0x102u : 0x100u, result.pc);
    }
}

static void reset_and_four_named_guest_instructions_total_seventy_six_cycles(void) {
    create_machine();
    const uint8_t program[] = {0x70, 0x0a, 0x5c, 0x80, 0x23, 0xc0,
                               0x00, 0x00, 0x10, 0x00, 0x4e, 0x72, 0x27, 0x00};
    install_program(program, sizeof(program));
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(40u, result.elapsed_cycles);
    result = owned_cpu_run(cpu, 36u);
    TEST_ASSERT_EQUAL_UINT64(36u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(4u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x10eu, result.pc);
    TEST_ASSERT_EQUAL_HEX32(16u, get_long(0x1000u));
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT64(76u, observation.total_cycles);
    TEST_ASSERT_EQUAL_UINT64(36u, observation.instruction_cycles);
}

static void nested_vector_callback_failure_is_terminal_without_recursion(void) {
    create_machine();
    put_vector(32u, 0x180u);
    const uint8_t trap[] = {0x4e, 0x40};
    install_program(trap, sizeof(trap));
    run_reset_event();
    memory.fail_read = 1;
    memory.fail_read_address = 0x80u;
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(5u, memory.accesses);
    size_t accesses = memory.accesses;
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(accesses, memory.accesses);
}

static void odd_exception_stack_fault_is_terminal_without_recursive_entry(void) {
    create_machine();
    put_vector(32u, 0x180u);
    const uint8_t trap[] = {0x4e, 0x40};
    install_program(trap, sizeof(trap));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_test_seed_execution_state(
                                        cpu, 0x2700u, 0u, 0x3001u, 0x100u));
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(1u, memory.accesses);
    size_t accesses = memory.accesses;
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(accesses, memory.accesses);
}

static void address_error_wrong_cycle_expectation(void) {
    create_machine();
    put_vector(3u, 0x180u);
    const uint8_t program[] = {0x30, 0x39, 0x00, 0x00, 0x02, 0x01};
    install_program(program, sizeof(program));
    run_reset_event();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL_UINT64(49u, result.elapsed_cycles);
}

static void move_to_sr_switches_to_user_stack(void) {
    create_machine();
    const uint8_t program[] = {0x46, 0xfc, 0x00, 0x00};
    install_program(program, sizeof(program));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_test_seed_execution_state(
                                        cpu, 0x2700u, 0x3800u, 0x3000u, 0x100u));

    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL_UINT64(12u, result.elapsed_cycles);
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_HEX16(0x0000u, observation.sr);
    TEST_ASSERT_EQUAL_HEX32(0x3800u, observation.address_registers[7]);
    TEST_ASSERT_EQUAL_HEX32(0x3800u, observation.usp);
    TEST_ASSERT_EQUAL_HEX32(0x3000u, observation.ssp);
}

static void rte_restores_user_stack_bank_from_short_frame(void) {
    create_machine();
    const uint8_t rte[] = {0x4e, 0x73};
    install_program(rte, sizeof(rte));
    put_word(0x3000u, 0x0000u);
    put_long(0x3002u, 0x0200u);
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_test_seed_execution_state(
                                        cpu, 0x2700u, 0x3800u, 0x3000u, 0x100u));
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(1));
    TEST_ASSERT_EQUAL_UINT64(20u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT(4u, memory.accesses);
    TEST_ASSERT_EQUAL_HEX32(0x100u, memory.events[0].address);
    TEST_ASSERT_EQUAL_HEX32(0x3000u, memory.events[1].address);
    TEST_ASSERT_EQUAL_HEX32(0x3002u, memory.events[2].address);
    TEST_ASSERT_EQUAL_HEX32(0x3004u, memory.events[3].address);
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_HEX32(0x200u, observation.pc);
    TEST_ASSERT_EQUAL_HEX16(0x0000u, observation.sr);
    TEST_ASSERT_EQUAL_HEX32(0x3800u, observation.address_registers[7]);
    TEST_ASSERT_EQUAL_HEX32(0x3006u, observation.ssp);
    TEST_ASSERT_EQUAL_HEX32(0x3800u, observation.usp);
}

static void inaccessible_rte_frame_read_is_terminal_without_return_commit(void) {
    create_machine();
    const uint8_t rte[] = {0x4e, 0x73};
    install_program(rte, sizeof(rte));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_test_seed_execution_state(
                                        cpu, 0x2700u, 0u, 0x3000u, 0x100u));
    memory.fail_read = 1;
    memory.fail_read_address = 0x3002u;
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.pc);
    TEST_ASSERT_EQUAL_UINT(3u, memory.accesses);
    TEST_ASSERT_EQUAL_HEX32(0x100u, memory.events[0].address);
    TEST_ASSERT_EQUAL_HEX32(0x3000u, memory.events[1].address);
    TEST_ASSERT_EQUAL_HEX32(0x3002u, memory.events[2].address);
    size_t accesses = memory.accesses;
    result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, result.reason);
    TEST_ASSERT_EQUAL_UINT(accesses, memory.accesses);
}

static void independent_counter_boundaries_do_not_block_other_event_kinds(void) {
    create_machine();
    const uint8_t nop[] = {0x4e, 0x71};
    install_program(nop, sizeof(nop));
    run_reset_event();
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_test_seed_counters(
                                        cpu, 0u, UINT64_MAX - 4u, UINT64_MAX, 0u, 40u));
    clear_trace();
    owned_cpu_run_result result = owned_cpu_run(cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    owned_cpu_observation observation;
    observe(&observation);
    TEST_ASSERT_EQUAL_UINT64(UINT64_MAX, observation.instruction_cycles);
    TEST_ASSERT_EQUAL_UINT64(UINT64_MAX, observation.exception_cycles);
    TEST_ASSERT_EQUAL_UINT64(44u, observation.total_cycles);
}

int main(int argc, char **argv) {
    UNITY_BEGIN();
    if (argc == 2 && strcmp(argv[1], "--mutate-unsupported") == 0) {
        RUN_TEST(canonical_unsupported_wrong_status_expectation);
        int failures = UNITY_END();
        puts("Unity denominator: expected=1 observed=1");
        return failures;
    }
    if (argc == 2 && strcmp(argv[1], "--mutate-cycle") == 0) {
        RUN_TEST(address_error_wrong_cycle_expectation);
        int failures = UNITY_END();
        puts("Unity denominator: expected=1 observed=1");
        return failures;
    }
    RUN_TEST(reset_debt_is_consumed_once_and_nop_executes);
    RUN_TEST(reset_instruction_is_distinct_and_observable);
    RUN_TEST(trap_stacks_next_pc_then_addq_rte_resumes_stop);
    RUN_TEST(canonical_unsupported_has_only_opcode_fetch);
    RUN_TEST(canonical_rejection_retains_prior_reset_irq_and_instruction_charges);
    RUN_TEST(canonical_failed_opcode_fetch_remains_a_host_fault);
    RUN_TEST(move_word_absolute_long_loads_every_data_register);
    RUN_TEST(odd_word_source_stacks_manual_derived_address_error_frame);
    RUN_TEST(odd_long_destination_stacks_a_write_address_error);
    RUN_TEST(odd_instruction_fetch_enters_group_zero_without_an_odd_bus_read);
    RUN_TEST(twenty_four_bit_bus_address_wrap_is_explicit);
    RUN_TEST(failed_second_word_write_keeps_first_word_and_becomes_terminal);
    RUN_TEST(irq3_stays_masked_until_move_to_sr_then_enters_as_its_own_event);
    RUN_TEST(irq7_edge_is_unmasked_and_held_level_waits_for_mask_change);
    RUN_TEST(user_mode_privileged_instructions_raise_vector_eight);
    RUN_TEST(stopped_cpu_idles_to_the_exact_request_without_bus_access);
    RUN_TEST(event_limits_and_counter_overflow_are_explicit);
    RUN_TEST(reset_request_boundaries_never_split_the_reset_event);
    RUN_TEST(reset_and_four_named_guest_instructions_total_seventy_six_cycles);
    RUN_TEST(nested_vector_callback_failure_is_terminal_without_recursion);
    RUN_TEST(odd_exception_stack_fault_is_terminal_without_recursive_entry);
    RUN_TEST(move_to_sr_switches_to_user_stack);
    RUN_TEST(rte_restores_user_stack_bank_from_short_frame);
    RUN_TEST(inaccessible_rte_frame_read_is_terminal_without_return_commit);
    RUN_TEST(independent_counter_boundaries_do_not_block_other_event_kinds);
    return UNITY_END();
}
