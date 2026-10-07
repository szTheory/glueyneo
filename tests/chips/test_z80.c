/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "z80_candidate.h"

#include <string.h>

enum { TEST_MEMORY_SIZE = 65536, TEST_EVENT_CAPACITY = 64 };

typedef struct {
    uint8_t memory[TEST_MEMORY_SIZE];
    z80_candidate_bus_kind kinds[TEST_EVENT_CAPACITY];
    uint16_t addresses[TEST_EVENT_CAPACITY];
    uint8_t values[TEST_EVENT_CAPACITY];
    size_t event_count;
    size_t fail_on_event;
} test_bus;

void setUp(void) {}
void tearDown(void) {}

static int test_bus_access(void *userdata, z80_candidate_bus_kind kind,
                           uint16_t address, uint8_t *data) {
    test_bus *bus = userdata;
    if (bus == NULL || data == NULL || bus->event_count == TEST_EVENT_CAPACITY) return 0;
    bus->event_count++;
    if (bus->fail_on_event != 0u && bus->event_count == bus->fail_on_event) return 0;
    size_t index = bus->event_count - 1u;
    bus->kinds[index] = kind;
    bus->addresses[index] = address;
    if (kind == Z80_CANDIDATE_BUS_MEMORY_READ) {
        *data = bus->memory[address];
    } else if (kind == Z80_CANDIDATE_BUS_MEMORY_WRITE) {
        bus->memory[address] = *data;
    } else if (kind == Z80_CANDIDATE_BUS_INTERRUPT_ACK) {
        *data = 0xffu;
    }
    bus->values[index] = *data;
    return 1;
}

static void one_instruction_reads_opcode_and_immediate(void) {
    test_bus bus = {0};
    z80_candidate *candidate = NULL;
    z80_candidate_tick_result tick = {0};
    z80_candidate_snapshot snapshot = {0};
    bus.memory[0] = 0x3eu; /* LD A,0x42 */
    bus.memory[1] = 0x42u;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &bus, &candidate));
    TEST_ASSERT_NOT_NULL(candidate);
    for (unsigned cycle = 0u; cycle < 7u; ++cycle) {
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_tick(candidate, false, false, &tick));
        TEST_ASSERT_EQUAL_UINT64(cycle + 1u, tick.cycles);
    }
    TEST_ASSERT_EQUAL_HEX8(0x42u, candidate == NULL ? 0u : bus.memory[1]);
    TEST_ASSERT_EQUAL_UINT(2u, bus.event_count);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_MEMORY_READ, bus.kinds[0]);
    TEST_ASSERT_EQUAL_HEX16(0u, bus.addresses[0]);
    TEST_ASSERT_EQUAL_HEX8(0x3eu, bus.values[0]);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_MEMORY_READ, bus.kinds[1]);
    TEST_ASSERT_EQUAL_HEX16(1u, bus.addresses[1]);
    TEST_ASSERT_EQUAL_HEX8(0x42u, bus.values[1]);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK, z80_candidate_capture(candidate, &snapshot));
    TEST_ASSERT_EQUAL_HEX8(0x42u, snapshot.cpu.a);
    TEST_ASSERT_FALSE(tick.instruction_complete);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_tick(candidate, false, false, &tick));
    TEST_ASSERT_TRUE(tick.instruction_complete);
    TEST_ASSERT_EQUAL_UINT64(8u, tick.cycles);
    z80_candidate_destroy(candidate);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(one_instruction_reads_opcode_and_immediate);
    return UNITY_END();
}
