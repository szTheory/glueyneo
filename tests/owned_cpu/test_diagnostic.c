/* SPDX-License-Identifier: MIT */
#include "cpu.h"
#include "guest_fixture.h"
#include "unity.h"

#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(CHAR_BIT == 8, "owned CPU tests require 8-bit bytes");
_Static_assert(UINT8_MAX == 0xffu, "uint8_t must be exactly 8 bits");
_Static_assert(UINT16_MAX == 0xffffu, "uint16_t must be exactly 16 bits");
_Static_assert(UINT32_MAX == 0xffffffffu, "uint32_t must be exactly 32 bits");
_Static_assert(UINT64_MAX == UINT64_C(0xffffffffffffffff), "uint64_t must be exactly 64 bits");

enum { TEST_ROM_SIZE = 512, TEST_RAM_BASE = 0x1000, TEST_RAM_SIZE = 4096, TEST_EVENTS = 64 };

typedef struct {
    char operation;
    uint32_t address;
    uint16_t value;
} bus_event;

typedef struct {
    uint8_t rom[TEST_ROM_SIZE];
    uint8_t ram[TEST_RAM_SIZE];
    bus_event events[TEST_EVENTS];
    size_t event_count;
    size_t reads;
    size_t writes;
    int fail_next_read;
    int fail_next_write;
} test_bus;

static test_bus memory;
static owned_cpu *cpu;
static int mutate_original_guest;

static void *test_allocate(void *userdata, size_t bytes) {
    (void)userdata;
    return malloc(bytes);
}

static void test_release(void *userdata, void *allocation) {
    (void)userdata;
    free(allocation);
}

static void record_event(char operation, uint32_t address, uint16_t value) {
    if (memory.event_count < TEST_EVENTS) {
        memory.events[memory.event_count] = (bus_event){operation, address, value};
        memory.event_count++;
    }
}

static int test_read16(void *userdata, uint32_t address, uint16_t *value) {
    test_bus *bus = userdata;
    if (bus == NULL || value == NULL || (address & 1u) != 0u) {
        return 0;
    }
    bus->reads++;
    if (bus->fail_next_read != 0) {
        bus->fail_next_read = 0;
        return 0;
    }
    if (address < TEST_ROM_SIZE && address + 1u < TEST_ROM_SIZE) {
        *value = (uint16_t)(((uint16_t)bus->rom[address] << 8) | bus->rom[address + 1u]);
    } else if (address >= TEST_RAM_BASE && address - TEST_RAM_BASE + 1u < TEST_RAM_SIZE) {
        size_t offset = (size_t)(address - TEST_RAM_BASE);
        *value = (uint16_t)(((uint16_t)bus->ram[offset] << 8) | bus->ram[offset + 1u]);
    } else {
        return 0;
    }
    record_event('R', address, *value);
    return 1;
}

static int test_write16(void *userdata, uint32_t address, uint16_t value) {
    test_bus *bus = userdata;
    if (bus == NULL || (address & 1u) != 0u) {
        return 0;
    }
    bus->writes++;
    if (bus->fail_next_write != 0) {
        bus->fail_next_write = 0;
        return 0;
    }
    if (address < TEST_RAM_BASE || address - TEST_RAM_BASE + 1u >= TEST_RAM_SIZE) {
        return 0;
    }
    size_t offset = (size_t)(address - TEST_RAM_BASE);
    bus->ram[offset] = (uint8_t)(value >> 8);
    bus->ram[offset + 1u] = (uint8_t)value;
    record_event('W', address, value);
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

static void start_fixture(unsigned scenario) {
    guest_fixture(memory.rom, scenario, mutate_original_guest);
    owned_cpu_bus bus = {&memory, test_read16, test_write16};
    owned_cpu_allocator allocator = {NULL, test_allocate, test_release};
    TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                      owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, allocator, &cpu));
    TEST_ASSERT_NOT_NULL(cpu);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_reset(cpu));
}

static uint32_t ram_long(size_t offset) {
    return ((uint32_t)memory.ram[offset] << 24) |
           ((uint32_t)memory.ram[offset + 1u] << 16) |
           ((uint32_t)memory.ram[offset + 2u] << 8) |
           (uint32_t)memory.ram[offset + 3u];
}

static void assert_scenario(unsigned scenario, uint32_t expected, uint32_t destination) {
    start_fixture(scenario);
    owned_cpu_observation before;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &before));
    TEST_ASSERT_EQUAL_HEX32(0x100u, before.pc);
    TEST_ASSERT_EQUAL_HEX32(0x2000u, before.ssp);
    TEST_ASSERT_EQUAL_HEX16(0x2700u, before.sr);
    TEST_ASSERT_EQUAL_UINT64(40u, before.reset_cycles);

    size_t reads_before_zero = memory.reads;
    size_t writes_before_zero = memory.writes;
    size_t events_before_zero = memory.event_count;
    owned_cpu_run_result zero = owned_cpu_run(cpu, UINT64_C(0));
    owned_cpu_observation after_zero;
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, zero.reason);
    TEST_ASSERT_EQUAL_UINT64(0u, zero.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(0u, zero.instructions);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &after_zero));
    TEST_ASSERT_EQUAL_UINT(reads_before_zero, memory.reads);
    TEST_ASSERT_EQUAL_UINT(writes_before_zero, memory.writes);
    TEST_ASSERT_EQUAL_UINT(events_before_zero, memory.event_count);
    TEST_ASSERT_EQUAL_INT(0, memcmp(&before, &after_zero, sizeof(before)));

    owned_cpu_run_result result = owned_cpu_run(cpu, UINT64_C(200));
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(
        expected, ram_long((size_t)(destination - TEST_RAM_BASE)),
        "guest arithmetic/store result");
    TEST_ASSERT_EQUAL(OWNED_CPU_STOPPED, result.reason);
    TEST_ASSERT_EQUAL_UINT64(36u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL_UINT64(4u, result.instructions);
    TEST_ASSERT_EQUAL_HEX32(0x10eu, result.pc);
    TEST_ASSERT_EQUAL_UINT64(2u, memory.writes);
    size_t observed_writes = 0u;
    for (size_t index = events_before_zero; index < memory.event_count; ++index) {
        if (memory.events[index].operation == 'W') {
            uint32_t expected_address = destination + (uint32_t)(observed_writes * 2u);
            uint16_t expected_word = observed_writes == 0u ? (uint16_t)(expected >> 16)
                                                           : (uint16_t)expected;
            TEST_ASSERT_EQUAL_HEX32(expected_address, memory.events[index].address);
            TEST_ASSERT_EQUAL_UINT16(expected_word, memory.events[index].value);
            observed_writes++;
        }
    }
    TEST_ASSERT_EQUAL_UINT(2u, observed_writes);

    owned_cpu_observation after_run;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(cpu, &after_run));
    TEST_ASSERT_EQUAL_HEX32(0x10eu, after_run.pc);
    TEST_ASSERT_EQUAL_HEX32(expected, after_run.data_registers[0]);
    TEST_ASSERT_EQUAL_UINT8(1u, after_run.stopped);
    TEST_ASSERT_EQUAL_UINT64(4u, after_run.instructions);
    TEST_ASSERT_EQUAL_UINT64(36u, after_run.instruction_cycles);
}

static void original_scenario_a_computes_and_stores_ten(void) {
    assert_scenario(0u, 10u, 0x1000u);
}

static void original_scenario_b_computes_and_stores_sixteen(void) {
    assert_scenario(1u, 16u, 0x1004u);
}

int main(int argc, char **argv) {
    if (argc > 2 || (argc == 2 && strcmp(argv[1], "--mutate") != 0)) {
        (void)fprintf(stderr, "usage: owned_cpu_diagnostic [--mutate]\n");
        return EXIT_FAILURE;
    }
    mutate_original_guest = argc == 2;
    UNITY_BEGIN();
    RUN_TEST(original_scenario_a_computes_and_stores_ten);
    if (argc == 1) {
        RUN_TEST(original_scenario_b_computes_and_stores_sixteen);
    }
    unsigned expected_cases = argc == 1 ? 2u : 1u;
    int failures = UNITY_END();
    if ((unsigned)Unity.NumberOfTests != expected_cases) {
        (void)fprintf(stderr, "Unity denominator mismatch: expected=%u observed=%u\n",
                      expected_cases, (unsigned)Unity.NumberOfTests);
        return EXIT_FAILURE;
    }
    (void)printf("Unity denominator: expected=%u observed=%u\n",
                 expected_cases, (unsigned)Unity.NumberOfTests);
    return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
