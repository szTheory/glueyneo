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
    uint32_t byte_write_addresses[MAX_WRITES];
    uint8_t byte_write_values[MAX_WRITES];
    uint32_t byte_read_addresses[MAX_WRITES];
    size_t byte_reads;
    size_t write_attempts;
    size_t successful_writes;
    size_t reads;
    size_t fail_read_on;
    size_t fail_write_on;
} memory_bus;

static memory_bus memory;
static owned_cpu *cpu;
static owned_cpu_status reset_with_program(const uint8_t *program, size_t length);

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

static int read_guest_byte(void *userdata, uint32_t address, uint8_t *value) {
    memory_bus *bus = userdata;
    if (bus == NULL || value == NULL || address >= ROM_SIZE) return 0;
    size_t attempt = bus->byte_reads++;
    if (attempt < MAX_WRITES) bus->byte_read_addresses[attempt] = address;
    *value = bus->rom[address];
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

static int write_guest_byte(void *userdata, uint32_t address, uint8_t value) {
    memory_bus *bus = userdata;
    if (bus == NULL) return 0;
    size_t attempt = bus->write_attempts++;
    if (attempt < MAX_WRITES) {
        bus->byte_write_addresses[attempt] = address;
        bus->byte_write_values[attempt] = value;
    }
    if (bus->fail_write_on != 0u && bus->write_attempts == bus->fail_write_on) return 0;
    if (address < ROM_SIZE) bus->rom[address] = value;
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
    owned_cpu_bus bus = {&memory, read_guest_word, write_guest_word, write_guest_byte, read_guest_byte};
    owned_cpu_allocator allocator = {NULL, allocate_memory, release_memory};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, allocator, &cpu));
    TEST_ASSERT_NOT_NULL(cpu);
}

static void bsr_word_pushes_return_pc_and_branches_in_18_cycles(void) {
    create_cpu();
    const uint8_t program[] = {0x61u, 0x00u, 0x00u, 0x04u, 0x4eu, 0x71u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(18));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(18u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(2u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1ffc), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(0u, memory.write_values[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1ffe), memory.write_addresses[1]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x0104), memory.write_values[1]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x106), observation.pc);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1ffc), observation.address_registers[7]);
    TEST_ASSERT_EQUAL_HEX16(0u, (uint16_t)(observation.sr & UINT16_C(0x000f)));
}

static void rts_restores_return_pc_and_stack_in_16_cycles(void) {
    create_cpu();
    memory.rom[0] = 0x00u;
    memory.rom[1] = 0x00u;
    memory.rom[2] = 0x01u;
    memory.rom[3] = 0xf0u;
    const uint8_t program[] = {0x4eu, 0x75u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    memory.rom[0x1f0] = 0x00u;
    memory.rom[0x1f1] = 0x00u;
    memory.rom[0x1f2] = 0x01u;
    memory.rom[0x1f3] = 0x20u;
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(16u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x120), observation.pc);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1f4), observation.address_registers[7]);
}

static void jsr_pc_displacement_pushes_return_pc_in_18_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x4eu, 0xbau, 0x00u, 0x10u, /* JSR d16(PC), PC base is extension word */
        0x4eu, 0x71u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(18));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(18u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(2u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1ffc), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(0u, memory.write_values[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1ffe), memory.write_addresses[1]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x0104), memory.write_values[1]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x112), observation.pc);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1ffc), observation.address_registers[7]);

    const uint8_t unsupported_absolute_short[] = {
        0x4eu, 0xb8u, 0x01u, 0x20u}; /* JSR absolute-short remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_absolute_short, sizeof(unsupported_absolute_short)));
    result = owned_cpu_run(cpu, UINT64_C(30));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x4eb8), result.instruction_register);
}

static void addq_byte_displacement_address_updates_one_byte_in_16_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x52, 0x28, 0, 4, /* ADDQ.B #1,(d16,A0) */
        0x52, 0x08}; /* ADDQ.B #1,(A0) remains unsupported. */
    memory.rom[0x184] = 0x7fu;
    memory.rom[0x185] = 0x42u;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x180);
    state.sr = UINT16_C(0x2710);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(16u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.byte_reads);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x184), memory.byte_read_addresses[0]);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_UINT(1u, memory.successful_writes);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x184), memory.byte_write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX8(0x80u, memory.byte_write_values[0]);
    TEST_ASSERT_EQUAL_HEX8(0x80u, memory.rom[0x184]);
    TEST_ASSERT_EQUAL_HEX8(0x42u, memory.rom[0x185]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x270a), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void jsr_absolute_long_pushes_return_pc_in_20_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x4e, 0xb9, 0x00, 0x00, 0x01, 0x20, /* JSR absolute-long */
        0x4e, 0x71};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(20));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(20u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(2u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1ffc), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1ffe), memory.write_addresses[1]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x0106), memory.write_values[1]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x120), observation.pc);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1ffc), observation.address_registers[7]);
}

static void movem_long_postincrement_loads_registers_and_updates_base(void) {
    create_cpu();
    const uint8_t program[] = {
        0x41u, 0xf9u, 0x00u, 0x00u, 0x01u, 0x80u, /* LEA $180,A0 */
        0x4cu, 0xd8u, 0x02u, 0x03u}; /* MOVEM.L (A0)+,D0/D1/A1 */
    const uint32_t values[] = {
        UINT32_C(0x11223344), UINT32_C(0x55667788), UINT32_C(0x99aabbcc)};
    for (size_t i = 0u; i < 3u; ++i) {
        const uint32_t address = UINT32_C(0x180) + (uint32_t)i * UINT32_C(4);
        memory.rom[address] = (uint8_t)(values[i] >> 24);
        memory.rom[address + 1u] = (uint8_t)(values[i] >> 16);
        memory.rom[address + 2u] = (uint8_t)(values[i] >> 8);
        memory.rom[address + 3u] = (uint8_t)values[i];
    }
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(48));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(48u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(2u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(values[0], observation.data_registers[0]);
    TEST_ASSERT_EQUAL_HEX32(values[1], observation.data_registers[1]);
    TEST_ASSERT_EQUAL_HEX32(values[2], observation.address_registers[1]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x18c), observation.address_registers[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x10a), observation.pc);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2700), observation.sr);

    const uint8_t base_register_in_mask[] = {
        0x41u, 0xf9u, 0x00u, 0x00u, 0x01u, 0x80u,
        0x4cu, 0xd8u, 0x01u, 0x01u}; /* MOVEM.L (A0)+,D0/A0 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        base_register_in_mask, sizeof(base_register_in_mask)));
    result = owned_cpu_run(cpu, UINT64_C(40));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(40u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(values[0], observation.data_registers[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x188), observation.address_registers[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2700), observation.sr);

    const uint8_t unsupported_indirect[] = {
        0x4cu, 0xd0u, 0x00u, 0x01u}; /* MOVEM.L (A0),D0 remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_indirect, sizeof(unsupported_indirect)));
    result = owned_cpu_run(cpu, UINT64_C(30));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x4cd0), result.instruction_register);
}

static void movea_long_postincrement_loads_address_register_in_14_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x41u, 0xf9u, 0x00u, 0x00u, 0x01u, 0x80u, /* LEA $180,A0 */
        0x22u, 0x58u}; /* MOVEA.L (A0)+,A1 */
    const uint32_t value = UINT32_C(0x89abcdef);
    memory.rom[0x180] = (uint8_t)(value >> 24);
    memory.rom[0x181] = (uint8_t)(value >> 16);
    memory.rom[0x182] = (uint8_t)(value >> 8);
    memory.rom[0x183] = (uint8_t)value;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(26));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(26u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(2u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(value, observation.address_registers[1]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x184), observation.address_registers[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2700), observation.sr);

    const uint8_t unsupported_indirect[] = {
        0x22u, 0x50u}; /* MOVEA.L (A0),A1 remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_indirect, sizeof(unsupported_indirect)));
    result = owned_cpu_run(cpu, UINT64_C(24));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2250), result.instruction_register);
}

static void movea_long_address_register_to_address_register_uses_4_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x26, 0x4a, /* MOVEA.L A2,A3 */
        0x24, 0x4a}; /* MOVEA.L A2,A2 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[2] = UINT32_C(0x12345678);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(0u, memory.write_attempts);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12345678), observation.address_registers[3]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x271f), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12345678), observation.address_registers[2]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x271f), observation.sr);

    /* A neighboring MOVE.L An,Dn encoding is outside this MOVEA-only slice. */
    const uint8_t wrong_destination[] = {0x24, 0x0a};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      reset_with_program(wrong_destination, sizeof(wrong_destination)));
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_long_immediate_to_data_register_uses_12_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x26, 0x3c, 0x89, 0xab, 0xcd, 0xef, /* MOVE.L #$89abcdef,D3 */
        0x26, 0x12}; /* MOVE.L (A2),D3 remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.data_registers[3] = UINT32_C(0x12345678);
    state.address_registers[2] = UINT32_C(0x2000);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(12));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(12u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(0u, memory.write_attempts);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x89abcdef), observation.data_registers[3]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(12));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void addq_word_to_data_register_updates_word_flags_in_4_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x52, 0x42, /* ADDQ.W #1,D2 */
        0x52, 0x50}; /* ADDQ.W #1,(A0) remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.data_registers[2] = UINT32_C(0x1234ffff);
    state.sr = UINT16_C(0x2710);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12340000), observation.data_registers[2]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2715), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void movea_long_data_register_to_address_register_uses_4_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x26, 0x42, /* MOVEA.L D2,A3 */
        0x26, 0x7c, 0, 0, 0, 1}; /* MOVEA.L #1,A3 remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.data_registers[2] = UINT32_C(0x89abcdef);
    state.address_registers[3] = UINT32_C(0x10203040);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(0u, memory.write_attempts);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x89abcdef), observation.address_registers[3]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x89abcdef), observation.data_registers[2]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x271f), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_word_data_register_to_data_register_uses_4_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x3a, 0x02, /* MOVE.W D2,D5 */
        0x34, 0x02}; /* MOVE.W D2,D2 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.data_registers[2] = UINT32_C(0x12348001);
    state.data_registers[5] = UINT32_C(0xabcd7654);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(0u, memory.write_attempts);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12348001), observation.data_registers[2]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xabcd8001), observation.data_registers[5]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12348001), observation.data_registers[2]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);

    const uint8_t unsupported_byte[] = {0x14, 0x02};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      reset_with_program(unsupported_byte, sizeof(unsupported_byte)));
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_byte_data_register_to_address_indirect_writes_one_byte(void) {
    create_cpu();
    const uint8_t program[] = {0x18, 0x83}; /* MOVE.B D3,(A4) */
    memory.rom[0x180] = 0x5au;
    memory.rom[0x181] = 0x5au;
    memory.rom[0x182] = 0x5au;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[4] = UINT32_C(0x181);
    state.data_registers[3] = UINT32_C(0x12345681);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_UINT(1u, memory.successful_writes);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x181), memory.byte_write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX8(0x81u, memory.byte_write_values[0]);
    TEST_ASSERT_EQUAL_HEX8(0x5au, memory.rom[0x180]);
    TEST_ASSERT_EQUAL_HEX8(0x81u, memory.rom[0x181]);
    TEST_ASSERT_EQUAL_HEX8(0x5au, memory.rom[0x182]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12345681), observation.data_registers[3]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);

    const uint8_t unsupported_postincrement[] = {0x18, 0xc3};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_postincrement, sizeof(unsupported_postincrement)));
    result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_word_data_register_to_postincrement_writes_and_increments(void) {
    create_cpu();
    const uint8_t program[] = {0x38, 0xc3}; /* MOVE.W D3,(A4)+ */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[4] = UINT32_C(0x180);
    state.data_registers[3] = UINT32_C(0x12348001);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x180), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x8001), memory.write_values[0]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x182), observation.address_registers[4]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12348001), observation.data_registers[3]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);

    const uint8_t unsupported_indirect[] = {0x38, 0x93};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_indirect, sizeof(unsupported_indirect)));
    result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);

    set_vector(12u, UINT32_C(0x140));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[4] = UINT32_C(0x181);
    state.data_registers[3] = UINT32_C(0x12348001);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    result = owned_cpu_run(cpu, UINT64_C(94));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(94u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_UINT8(3u, observation.last_exception_vector);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x181), observation.address_registers[4]);
    for (size_t i = 0; i < memory.write_attempts && i < MAX_WRITES; ++i)
        TEST_ASSERT_NOT_EQUAL(UINT32_C(0x181), memory.write_addresses[i]);
}

static void dbf_word_decrements_and_branches_or_expires_with_exact_timing(void) {
    create_cpu();
    const uint8_t program[] = {0x51, 0xcb, 0xff, 0xfc}; /* DBF D3,-4 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.data_registers[3] = UINT32_C(0x12340002);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(10));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(10u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12340001), observation.data_registers[3]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x0fe), observation.pc);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x271f), observation.sr);

    const uint8_t expire[] = {0x51, 0xcb, 0x00, 0x04};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(expire, sizeof(expire)));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.data_registers[3] = UINT32_C(0xabcd0000);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(16u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xabcdffff), observation.data_registers[3]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x104), observation.pc);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x271f), observation.sr);

    const uint8_t unsupported_condition[] = {0x56, 0xcb, 0xff, 0xfc};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_condition, sizeof(unsupported_condition)));
    result = owned_cpu_run(cpu, UINT64_C(10));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_word_address_indirect_to_data_register_uses_8_cycles(void) {
    create_cpu();
    const uint8_t program[] = {0x36, 0x14}; /* MOVE.W (A4),D3 */
    memory.rom[0x180] = 0x80u;
    memory.rom[0x181] = 0x01u;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[4] = UINT32_C(0x180);
    state.data_registers[3] = UINT32_C(0xabcd7654);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    const size_t reads_before = memory.reads;
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(reads_before + 2u, memory.reads);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xabcd8001), observation.data_registers[3]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x180), observation.address_registers[4]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);

    const uint8_t unsupported_postincrement[] = {0x36, 0x1c};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_postincrement, sizeof(unsupported_postincrement)));
    result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);

    set_vector(12u, UINT32_C(0x140));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[4] = UINT32_C(0x181);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    result = owned_cpu_run(cpu, UINT64_C(94));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(94u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_UINT8(3u, observation.last_exception_vector);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x181), observation.address_registers[4]);
}

static void cmp_word_data_registers_sets_flags_without_changing_operands(void) {
    create_cpu();
    const uint8_t program[] = {
        0xba, 0x42, /* CMP.W D2,D5 */
        0xb4, 0x42}; /* CMP.W D2,D2 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.data_registers[2] = UINT32_C(0x12348001);
    state.data_registers[5] = UINT32_C(0xabcd0001);
    state.sr = UINT16_C(0x2710);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12348001), observation.data_registers[2]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xabcd0001), observation.data_registers[5]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x271b), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12348001), observation.data_registers[2]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xabcd0001), observation.data_registers[5]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2714), observation.sr);
    TEST_ASSERT_EQUAL_UINT(0u, memory.write_attempts);

    const uint8_t unsupported_memory[] = {0xba, 0x54};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_memory, sizeof(unsupported_memory)));
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void bcc_word_uses_condition_flags_and_exact_timing(void) {
    create_cpu();
    const uint8_t program[] = {
        0x66u, 0x00u, 0x00u, 0x04u, /* BNE.w +4, taken when Z clear. */
        0x70u, 0x01u,
        0x70u, 0x02u,
        0x70u, 0x03u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.sr = UINT16_C(0x2710); /* X set, Z clear. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(10));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(10u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x106), observation.pc);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2710), observation.sr);

    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.sr = UINT16_C(0x2714); /* Z set: BNE not taken. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    result = owned_cpu_run(cpu, UINT64_C(10));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(10u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x104), observation.pc);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2714), observation.sr);

    const uint8_t unsupported_bsr_byte[] = {0x61u, 0x02u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_bsr_byte, sizeof(unsupported_bsr_byte)));
    result = owned_cpu_run(cpu, UINT64_C(10));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void bcc_byte_uses_taken_and_not_taken_timing(void) {
    create_cpu();
    const uint8_t program[] = {0x66u, 0x04u}; /* BNE.s +4 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.sr = UINT16_C(0x2710);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(10));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(10u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x106), observation.pc);

    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.sr = UINT16_C(0x2714);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    result = owned_cpu_run(cpu, UINT64_C(6));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(6u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x102), observation.pc);
}

static void addq_long_to_address_register_preserves_flags(void) {
    create_cpu();
    const uint8_t program[] = {0x56u, 0x89u}; /* ADDQ.L #3,A1 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[1] = UINT32_C(0xfffffffe);
    state.address_registers[2] = UINT32_C(0x12345678);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000001), observation.address_registers[1]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12345678), observation.address_registers[2]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x271f), observation.sr);

    const uint8_t unsupported_memory[] = {0x56u, 0x90u}; /* ADDQ.L #3,(A0) */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_memory, sizeof(unsupported_memory)));
    result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_word_address_register_to_data_register_preserves_upper_word(void) {
    create_cpu();
    const uint8_t program[] = {0x38u, 0x0bu}; /* MOVE.W A3,D4 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[3] = UINT32_C(0x12348001);
    state.data_registers[4] = UINT32_C(0xabcdffff);
    state.sr = UINT16_C(0x2718);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12348001), observation.address_registers[3]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xabcd8001), observation.data_registers[4]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);

    const uint8_t unsupported_memory_destination[] = {0x30u, 0x88u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_memory_destination, sizeof(unsupported_memory_destination)));
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void jmp_address_indirect_uses_8_cycles_without_target_fetch(void) {
    create_cpu();
    const uint8_t program[] = {0x4eu, 0xd0u}; /* JMP (A0) */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x120);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    const size_t reads_before = memory.reads;
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL(reads_before + 1u, memory.reads);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x120), observation.pc);

    const uint8_t unsupported_register_direct[] = {0x4eu, 0xc0u}; /* JMP D0 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_register_direct, sizeof(unsupported_register_direct)));
    result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void addq_byte_to_data_register_preserves_upper_bits_and_sets_flags(void) {
    create_cpu();
    const uint8_t program[] = {0x52u, 0x04u}; /* ADDQ.B #1,D4 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.data_registers[4] = UINT32_C(0x1234567f);
    state.sr = UINT16_C(0x2714);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(4u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x12345680), observation.data_registers[4]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x270a), observation.sr);

    const uint8_t unsupported_memory[] = {0x52u, 0x10u}; /* ADDQ.B #1,(A0) */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_memory, sizeof(unsupported_memory)));
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_byte_absolute_long_to_data_register_uses_byte_read(void) {
    create_cpu();
    const uint8_t program[] = {0x10u, 0x39u, 0x00u, 0x00u, 0x01u, 0x21u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    memory.rom[0x121u] = 0x80u;
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.data_registers[0] = UINT32_C(0xabcd0011);
    state.sr = UINT16_C(0x2710);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(16u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.byte_reads);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x121), memory.byte_read_addresses[0]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xabcd0080), observation.data_registers[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);
}

static void move_word_immediate_to_data_register_uses_8_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x70u, 0xffu,             /* MOVEQ #-1,D0 */
        0x46u, 0xfcu, 0x27u, 0x10u, /* MOVE #$2710,SR: set X */
        0x30u, 0x3cu, 0x80u, 0x01u}; /* MOVE.W #$8001,D0 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(24));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(24u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(3u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xffff8001), observation.data_registers[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x10a), observation.pc);

    const uint8_t unsupported_absolute_short[] = {
        0x31u, 0xfcu, 0x12u, 0x34u, 0x01u, 0x00u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_absolute_short, sizeof(unsupported_absolute_short)));
    result = owned_cpu_run(cpu, UINT64_C(20));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x31fc), result.instruction_register);

    const uint8_t address_register_control[] = {
        0x30u, 0x7cu, 0x12u, 0x34u}; /* MOVEA.W #$1234,A0 is unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        address_register_control, sizeof(address_register_control)));
    result = owned_cpu_run(cpu, UINT64_C(20));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x307c), result.instruction_register);

    const uint8_t selected_register[] = {
        0x72u, 0xffu,             /* MOVEQ #-1,D1 */
        0x32u, 0x3cu, 0x12u, 0x34u}; /* MOVE.W #$1234,D1 */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        selected_register, sizeof(selected_register)));
    result = owned_cpu_run(cpu, UINT64_C(12));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(12u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(2u, result.instructions);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xffff1234), observation.data_registers[1]);
    TEST_ASSERT_EQUAL_HEX32(0u, observation.data_registers[0]);
}

static void move_word_immediate_to_displacement_memory_uses_16_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x31u, 0x7cu, 0xabu, 0xcdu, 0x00u, 0x04u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_observation before;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &before));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x120);
    state.sr = UINT16_C(0x2710);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(16u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x124), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0xabcd), memory.write_values[0]);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &before));
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), before.sr);

    const uint8_t unsupported_control[] = {
        0x31u, 0xfcu, 0x12u, 0x34u, 0x01u, 0x00u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_control, sizeof(unsupported_control)));
    result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_long_immediate_to_postincrement_memory_uses_20_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x20u, 0xfcu, 0x89u, 0xabu, 0xcdu, 0xefu,
        0x20u, 0x90u}; /* MOVE.L #imm,(A0) remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x180);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(20));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(20u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(2u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x180), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x89ab), memory.write_values[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x182), memory.write_addresses[1]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0xcdef), memory.write_values[1]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x184), observation.address_registers[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(20));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void lea_displacement_address_to_register_uses_8_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x43u, 0xe8u, 0x00u, 0x04u, /* LEA 4(A0),A1 */
        0x43u, 0xf0u, 0x00u, 0x04u}; /* indexed LEA remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x180);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x184), observation.address_registers[1]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x271f), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_long_immediate_to_absolute_long_uses_28_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x23u, 0xfcu, 0x89u, 0xabu, 0xcdu, 0xefu,
        0x00u, 0x00u, 0x01u, 0x80u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(28));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(28u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(2u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x180), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x89ab), memory.write_values[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x182), memory.write_addresses[1]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0xcdef), memory.write_values[1]);

    const uint8_t unsupported_absolute_short[] = {
        0x23u, 0xf8u, 0x01u, 0x80u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_absolute_short, sizeof(unsupported_absolute_short)));
    result = owned_cpu_run(cpu, UINT64_C(28));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void subq_byte_displacement_address_updates_one_byte_in_16_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x53, 0x28, 0, 4, /* SUBQ.B #1,(d16,A0) */
        0x53, 0x08}; /* SUBQ.B #1,(A0) remains unsupported. */
    memory.rom[0x184] = 0x80u;
    memory.rom[0x185] = 0x42u;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x180);
    state.sr = UINT16_C(0x2710);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(16u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.byte_reads);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x184), memory.byte_read_addresses[0]);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX8(0x7fu, memory.byte_write_values[0]);
    TEST_ASSERT_EQUAL_HEX8(0x42u, memory.rom[0x185]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2702), observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_long_immediate_to_displacement_memory_uses_24_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x21u, 0x7cu, 0x89u, 0xabu, 0xcdu, 0xefu, 0x00u, 0x04u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x120);
    state.sr = UINT16_C(0x271f);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(24));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(24u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(2u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x124), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x89ab), memory.write_values[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x126), memory.write_addresses[1]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0xcdef), memory.write_values[1]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);

    const uint8_t unsupported_control[] = {0x20u, 0x90u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_control, sizeof(unsupported_control)));
    result = owned_cpu_run(cpu, UINT64_C(24));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_word_data_register_to_displacement_memory_uses_12_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x31u, 0x40u, 0x00u, 0x04u}; /* MOVE.W D0,4(A0) */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x120);
    state.data_registers[0] = UINT32_C(0x1234abcd);
    state.sr = UINT16_C(0x2710);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(12));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(12u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x124), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0xabcd), memory.write_values[0]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1234abcd), observation.data_registers[0]);

    const uint8_t unsupported_absolute_short[] = {
        0x31u, 0xc0u}; /* MOVE.W D0,(xxx).W remains unsupported. */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_absolute_short, sizeof(unsupported_absolute_short)));
    result = owned_cpu_run(cpu, UINT64_C(12));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_word_data_register_to_address_indirect_uses_8_cycles(void) {
    create_cpu();
    const uint8_t program[] = {0x30u, 0x80u}; /* MOVE.W D0,(A0) */
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_state state;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x120);
    state.data_registers[0] = UINT32_C(0x1234abcd);
    state.sr = UINT16_C(0x2710);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(8u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x120), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0xabcd), memory.write_values[0]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x1234abcd), observation.data_registers[0]);
    TEST_ASSERT_EQUAL_HEX16(UINT16_C(0x2718), observation.sr);

    set_vector(12u, UINT32_C(0x140));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(cpu, &state));
    state.address_registers[0] = UINT32_C(0x121);
    state.data_registers[0] = UINT32_C(0x5678);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(cpu, &state));
    result = owned_cpu_run(cpu, UINT64_C(94));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(94u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_UINT8(3u, observation.last_exception_vector);
    for (size_t index = 0u; index < memory.write_attempts && index < MAX_WRITES; ++index)
        TEST_ASSERT_NOT_EQUAL(UINT32_C(0x121), memory.write_addresses[index]);

    const uint8_t unsupported_absolute_short[] = {0x31u, 0xc0u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_absolute_short, sizeof(unsupported_absolute_short)));
    result = owned_cpu_run(cpu, UINT64_C(8));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
}

static void move_byte_immediate_to_absolute_long_writes_byte_in_20_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x13u, 0xfcu, 0x00u, 0x80u, 0x00u, 0x00u, 0x01u, 0x21u};
    memory.rom[0x120u] = 0xaau;
    memory.rom[0x121u] = 0xbbu;
    memory.rom[0x122u] = 0xccu;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(20));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(20u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x121), memory.byte_write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX8(0x80u, memory.byte_write_values[0]);
    TEST_ASSERT_EQUAL_HEX8(0xaau, memory.rom[0x120u]);
    TEST_ASSERT_EQUAL_HEX8(0x80u, memory.rom[0x121u]);
    TEST_ASSERT_EQUAL_HEX8(0xccu, memory.rom[0x122u]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x108), observation.pc);
    TEST_ASSERT((observation.sr & UINT16_C(0x0008)) != 0u);
    TEST_ASSERT((observation.sr & UINT16_C(0x0004)) == 0u);
}

static void lea_absolute_long_loads_address_register_in_12_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x41u, 0xf9u, 0x00u, 0x00u, 0x01u, 0x24u};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(12));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(12u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x124), observation.address_registers[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x106), observation.pc);
    TEST_ASSERT_EQUAL_HEX16(0u, (uint16_t)(observation.sr & UINT16_C(0x000f)));
}

static void move_word_immediate_to_absolute_long_writes_word_in_20_cycles(void) {
    create_cpu();
    const uint8_t program[] = {
        0x33u, 0xfcu, 0x12u, 0x34u, 0x00u, 0x00u, 0x01u, 0x22u};
    memory.rom[0x122u] = 0xaau;
    memory.rom[0x123u] = 0xbbu;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(20));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(20u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x122), memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX16(0x1234u, memory.write_values[0]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x108), observation.pc);
    TEST_ASSERT_EQUAL_HEX16(0u, (uint16_t)(observation.sr & UINT16_C(0x000f)));
}

static void move_byte_data_register_to_absolute_long_writes_one_byte(void) {
    create_cpu();
    const uint8_t program[] = {
        0x70u, 0x7fu,             /* MOVEQ #127,D0 */
        0x52u, 0x80u,             /* ADDQ.L #1,D0: sets X, result $80 */
        0x13u, 0xc0u, 0x00u, 0x00u, 0x01u, 0x21u}; /* MOVE.B D0,$121 */
    memory.rom[0x120u] = 0xaau;
    memory.rom[0x121u] = 0xbbu;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(24));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(24u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(3u, result.instructions);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x121), memory.byte_write_addresses[0]);
    TEST_ASSERT_EQUAL_HEX8(0x80u, memory.byte_write_values[0]);
    TEST_ASSERT_EQUAL_HEX8(0xaau, memory.rom[0x120u]);
    TEST_ASSERT_EQUAL_HEX8(0x80u, memory.rom[0x121u]);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x00000080), observation.data_registers[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0x10a), observation.pc);
    TEST_ASSERT((observation.sr & UINT16_C(0x0008)) != 0u);
    TEST_ASSERT((observation.sr & UINT16_C(0x0004)) == 0u);
    TEST_ASSERT((observation.sr & UINT16_C(0x0010)) == 0u);
}

static owned_cpu_status reset_with_program(const uint8_t *program, size_t length) {
    if (program == NULL || length > ROM_SIZE - 0x100u) {
        return OWNED_CPU_INVALID_ARGUMENT;
    }
    memcpy(memory.rom + 0x100u, program, length);
    owned_cpu_status status = owned_cpu_reset(cpu);
    if (status != OWNED_CPU_OK) return status;
    owned_cpu_run_result reset_event = owned_cpu_run(cpu, UINT64_C(1));
    if (reset_event.reason != OWNED_CPU_BUDGET || reset_event.elapsed_cycles != 64u ||
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

static void sampled_words_add_into_marker_and_store_with_word_semantics(void) {
    create_cpu();
    memory.rom[0x1f0] = 0xff;
    memory.rom[0x1f1] = 0xf0;
    memory.rom[0x1f2] = 0x00;
    memory.rom[0x1f3] = 0x20;
    const uint8_t program[] = {
        0x70, 0xff,                         /* MOVEQ #-1,D0 */
        0x72, 0xff,                         /* MOVEQ #-1,D1 */
        0x30, 0x39, 0x00, 0x00, 0x01, 0xf0, /* MOVE.W ($1f0).L,D0 */
        0x32, 0x39, 0x00, 0x00, 0x01, 0xf2, /* MOVE.W ($1f2).L,D1 */
        0xd2, 0x40,                         /* ADD.W D0,D1 */
        0x33, 0xc1, 0x00, 0x00, 0x01, 0xf4, /* MOVE.W D1,($1f4).L */
    };
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(44));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(44u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(5u, result.instructions);

    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xffffffF0), observation.data_registers[0]);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xffff0010), observation.data_registers[1]);
    TEST_ASSERT_BITS_HIGH(0x0011u, observation.sr); /* carry also sets extend */
    TEST_ASSERT_BITS_LOW(0x000eu, observation.sr);
    result = owned_cpu_run(cpu, UINT64_C(16));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(16u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &observation));
    TEST_ASSERT_BITS_HIGH(0x0010u, observation.sr); /* MOVE.W preserves X */
    TEST_ASSERT_BITS_LOW(0x000fu, observation.sr);
    TEST_ASSERT_EQUAL_UINT(1u, memory.write_attempts);
    TEST_ASSERT_EQUAL_HEX32(0x1f4u, memory.write_addresses[0]);
    TEST_ASSERT_EQUAL_UINT16(0x0010u, memory.write_values[0]);
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

    const uint8_t unsupported_bsr_byte[] = {0x61, 0x02};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      reset_with_program(unsupported_bsr_byte, sizeof(unsupported_bsr_byte)));
    result = owned_cpu_run(cpu, UINT64_C(18));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX16(0x6102u, result.instruction_register);

    const uint8_t unsupported_rtr[] = {0x4e, 0x77};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      reset_with_program(unsupported_rtr, sizeof(unsupported_rtr)));
    result = owned_cpu_run(cpu, UINT64_C(20));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX16(0x4e77u, result.instruction_register);

    const uint8_t unsupported_lea_mode[] = {0x41, 0xfa, 0x00, 0x04};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      reset_with_program(unsupported_lea_mode, sizeof(unsupported_lea_mode)));
    result = owned_cpu_run(cpu, UINT64_C(12));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX16(0x41fau, result.instruction_register);

    const uint8_t unsupported_move_byte_absolute_word[] = {
        0x13, 0xf8, 0x01, 0x20};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(
        unsupported_move_byte_absolute_word, sizeof(unsupported_move_byte_absolute_word)));
    result = owned_cpu_run(cpu, UINT64_C(20));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_HEX16(0x13f8u, result.instruction_register);

    const uint8_t guest_illegal[] = {0x4a, 0xfc};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(guest_illegal, sizeof(guest_illegal)));
    result = owned_cpu_run(cpu, UINT64_C(4));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_OPCODE, result.reason);
    TEST_ASSERT_EQUAL_UINT64(0u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.pc);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.fault_pc);
    TEST_ASSERT_EQUAL_HEX16(0x4afcu, result.instruction_register);
    TEST_ASSERT_EQUAL_UINT(0u, memory.write_attempts);
    owned_cpu_observation rejected;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &rejected));
    TEST_ASSERT_EQUAL_UINT8(0u, rejected.last_exception_vector);
    TEST_ASSERT_EQUAL_UINT64(0u, rejected.exception_cycles);
    TEST_ASSERT_EQUAL_HEX32(0x2000u, rejected.address_registers[7]);

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
    TEST_ASSERT_EQUAL_UINT64(98u, result.elapsed_cycles);
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

    memory.write_attempts = 0u;
    const uint8_t odd_immediate_store[] = {
        0x33, 0xfc, 0x12, 0x34, 0x00, 0x00, 0x10, 0x01};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      reset_with_program(odd_immediate_store, sizeof(odd_immediate_store)));
    result = owned_cpu_run(cpu, UINT64_C(94));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(94u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x100u, result.fault_pc);
    TEST_ASSERT_EQUAL_HEX16(0x33fcu, result.instruction_register);
    TEST_ASSERT_EQUAL_UINT(7u, memory.write_attempts);
    TEST_ASSERT_NOT_EQUAL(UINT32_C(0x1001), memory.write_addresses[0]);
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

static void jmp_absolute_long_sets_next_pc_without_fetching_target(void) {
    create_cpu();
    const uint8_t program[] = {0x4e, 0xf9, 0x00, 0x00, 0x01, 0x20};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, reset_with_program(program, sizeof(program)));
    const size_t reads_after_reset = memory.reads;
    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(12));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(12u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(1u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x120u, result.pc);
    TEST_ASSERT_EQUAL_UINT(reads_after_reset + 3u, memory.reads);
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
    owned_cpu_bus bus = {&memory, read_guest_word, write_guest_word, write_guest_byte, read_guest_byte};
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
    RUN_TEST(sampled_words_add_into_marker_and_store_with_word_semantics);
    RUN_TEST(addq_long_reports_signed_positive_overflow);
    RUN_TEST(move_long_uses_each_data_register_and_ordered_words);
    RUN_TEST(move_long_clears_nzvc_and_preserves_x);
    RUN_TEST(stop_loads_sr_and_switches_to_the_selected_stack_bank);
    RUN_TEST(unsupported_modes_and_illegal_word_report_pc_and_ir);
    RUN_TEST(odd_reset_vectors_and_odd_store_are_explicit);
    RUN_TEST(incomplete_extension_fetch_becomes_terminal_host_fault);
    RUN_TEST(write_fault_keeps_the_successful_first_word);
    RUN_TEST(absolute_long_second_word_wraps_in_defined_unsigned_space);
    RUN_TEST(jmp_absolute_long_sets_next_pc_without_fetching_target);
    RUN_TEST(bsr_word_pushes_return_pc_and_branches_in_18_cycles);
    RUN_TEST(rts_restores_return_pc_and_stack_in_16_cycles);
    RUN_TEST(jsr_pc_displacement_pushes_return_pc_in_18_cycles);
    RUN_TEST(jsr_absolute_long_pushes_return_pc_in_20_cycles);
    RUN_TEST(addq_byte_displacement_address_updates_one_byte_in_16_cycles);
    RUN_TEST(movem_long_postincrement_loads_registers_and_updates_base);
    RUN_TEST(movea_long_postincrement_loads_address_register_in_14_cycles);
    RUN_TEST(movea_long_address_register_to_address_register_uses_4_cycles);
    RUN_TEST(movea_long_data_register_to_address_register_uses_4_cycles);
    RUN_TEST(move_long_immediate_to_data_register_uses_12_cycles);
    RUN_TEST(addq_word_to_data_register_updates_word_flags_in_4_cycles);
    RUN_TEST(move_word_data_register_to_data_register_uses_4_cycles);
    RUN_TEST(move_byte_data_register_to_address_indirect_writes_one_byte);
    RUN_TEST(move_word_data_register_to_postincrement_writes_and_increments);
    RUN_TEST(dbf_word_decrements_and_branches_or_expires_with_exact_timing);
    RUN_TEST(move_word_address_indirect_to_data_register_uses_8_cycles);
    RUN_TEST(cmp_word_data_registers_sets_flags_without_changing_operands);
    RUN_TEST(bcc_word_uses_condition_flags_and_exact_timing);
    RUN_TEST(addq_long_to_address_register_preserves_flags);
    RUN_TEST(bcc_byte_uses_taken_and_not_taken_timing);
    RUN_TEST(move_word_address_register_to_data_register_preserves_upper_word);
    RUN_TEST(jmp_address_indirect_uses_8_cycles_without_target_fetch);
    RUN_TEST(addq_byte_to_data_register_preserves_upper_bits_and_sets_flags);
    RUN_TEST(move_byte_absolute_long_to_data_register_uses_byte_read);
    RUN_TEST(move_word_immediate_to_data_register_uses_8_cycles);
    RUN_TEST(move_word_immediate_to_displacement_memory_uses_16_cycles);
    RUN_TEST(move_long_immediate_to_displacement_memory_uses_24_cycles);
    RUN_TEST(subq_byte_displacement_address_updates_one_byte_in_16_cycles);
    RUN_TEST(move_long_immediate_to_absolute_long_uses_28_cycles);
    RUN_TEST(lea_displacement_address_to_register_uses_8_cycles);
    RUN_TEST(move_long_immediate_to_postincrement_memory_uses_20_cycles);
    RUN_TEST(move_word_data_register_to_displacement_memory_uses_12_cycles);
    RUN_TEST(move_word_data_register_to_address_indirect_uses_8_cycles);
    RUN_TEST(move_byte_immediate_to_absolute_long_writes_byte_in_20_cycles);
    RUN_TEST(lea_absolute_long_loads_address_register_in_12_cycles);
    RUN_TEST(move_word_immediate_to_absolute_long_writes_word_in_20_cycles);
    RUN_TEST(move_byte_data_register_to_absolute_long_writes_one_byte);
    RUN_TEST(program_counter_keeps_logical_high_byte_while_bus_masks_to_24_bits);
    RUN_TEST(model_allocator_irq_and_invalid_budget_reject_without_side_effects);
    return UNITY_END();
}
