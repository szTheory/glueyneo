/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "z80_candidate.h"

#include <stdio.h>
#include <string.h>

#ifndef _WIN32
#include <pthread.h>
#endif

enum {
    TEST_MEMORY_SIZE = 65536,
    TEST_EVENT_CAPACITY = 256,
    TEST_PROGRAM_CYCLES = 96,
    TEST_Z80_STATE_BYTES = 76,
    TEST_Z80_DDFD_M1_T2 = 1685,
    TEST_Z80_DDFD_LDHLN_OVERLAPPED = 1699,
    TEST_Z80_CB_M1_T2 = 1700,
    TEST_Z80_CB_M1_T4 = 1702,
    TEST_Z80_ED_M1_T2 = 1703,
    TEST_Z80_ED_M1_T4 = 1705,
    TEST_Z80_INT_IM1_STEP = 1642
};

typedef struct {
    uint8_t memory[TEST_MEMORY_SIZE];
    z80_candidate_bus_kind kinds[TEST_EVENT_CAPACITY];
    uint16_t addresses[TEST_EVENT_CAPACITY];
    uint8_t values[TEST_EVENT_CAPACITY];
    uint64_t event_cycles[TEST_EVENT_CAPACITY];
    uint64_t current_cycle;
    size_t event_count;
    size_t fail_on_event;
} test_bus;

typedef enum {
    MUTATION_NONE = 0,
    MUTATION_CYCLE,
    MUTATION_BUS,
    MUTATION_IRQ,
    MUTATION_CONTINUATION,
    MUTATION_INSTANCE
} test_mutation;

static test_mutation mutation;

static void configure_im1_irq_program(test_bus *bus);
static size_t find_event(const test_bus *bus, z80_candidate_bus_kind kind);

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
    bus->event_cycles[index] = bus->current_cycle;
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

static int tick_once(test_bus *bus, z80_candidate *candidate, bool irq,
                     z80_candidate_tick_result *tick) {
    bus->current_cycle++;
    return z80_candidate_tick(candidate, irq, false, tick) == Z80_CANDIDATE_OK;
}

static int tick_many(test_bus *bus, z80_candidate *candidate, unsigned cycles,
                     bool irq, z80_candidate_tick_result *tick) {
    for (unsigned index = 0u; index < cycles; ++index) {
        if (!tick_once(bus, candidate, irq, tick)) return 0;
    }
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
        TEST_ASSERT_TRUE(tick_once(&bus, candidate, false, &tick));
        uint64_t observed_cycles = tick.cycles +
            (mutation == MUTATION_CYCLE ? UINT64_C(1) : UINT64_C(0));
        TEST_ASSERT_EQUAL_UINT64(cycle + 1u, observed_cycles);
    }
    TEST_ASSERT_EQUAL_UINT(2u, bus.event_count);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_MEMORY_READ, bus.kinds[0]);
    uint16_t observed_address = (uint16_t)(bus.addresses[0] +
        (mutation == MUTATION_BUS ? 1u : 0u));
    TEST_ASSERT_EQUAL_HEX16(0u, observed_address);
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

static void bus_program_runs_documented_memory_write_cycles(void) {
    test_bus bus = {0};
    z80_candidate *candidate = NULL;
    z80_candidate_snapshot snapshot = {0};
    z80_candidate_tick_result tick = {0};
    bus.memory[0] = 0x3eu; /* LD A,0x5a: 4T fetch + 3T read. */
    bus.memory[1] = 0x5au;
    bus.memory[2] = 0x32u; /* LD (0x4000),A: 4T + 3T + 3T + 3T. */
    bus.memory[3] = 0x00u;
    bus.memory[4] = 0x40u;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &bus, &candidate));
    TEST_ASSERT_TRUE(tick_many(&bus, candidate, 20u, false, &tick));
    TEST_ASSERT_EQUAL_UINT64(20u, tick.cycles);
    TEST_ASSERT_EQUAL_HEX8(0x5au, bus.memory[0x4000u]);
    TEST_ASSERT_EQUAL_UINT(6u, bus.event_count);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_MEMORY_WRITE, bus.kinds[5]);
    TEST_ASSERT_EQUAL_HEX16(0x4000u, bus.addresses[5]);
    TEST_ASSERT_EQUAL_HEX8(0x5au, bus.values[5]);
    TEST_ASSERT_EQUAL_UINT64(19u, bus.event_cycles[5]);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK, z80_candidate_capture(candidate, &snapshot));
    TEST_ASSERT_EQUAL_HEX8(0x5au, snapshot.cpu.a);
    z80_candidate_destroy(candidate);
}

static void reset_reinitializes_candidate_but_preserves_external_memory(void) {
    test_bus bus = {0};
    z80_candidate *candidate = NULL;
    z80_candidate_snapshot snapshot = {0};
    z80_candidate_tick_result tick = {0};
    bus.memory[0] = 0x3eu;
    bus.memory[1] = 0x42u;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &bus, &candidate));
    TEST_ASSERT_TRUE(tick_many(&bus, candidate, 7u, false, &tick));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK, z80_candidate_capture(candidate, &snapshot));
    TEST_ASSERT_EQUAL_HEX8(0x42u, snapshot.cpu.a);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK, z80_candidate_reset(candidate));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK, z80_candidate_capture(candidate, &snapshot));
    TEST_ASSERT_EQUAL_UINT64(0u, snapshot.cycles);
    TEST_ASSERT_EQUAL_HEX16(0u, snapshot.cpu.pc);
    TEST_ASSERT_EQUAL_HEX16(0xffffu, snapshot.cpu.af);
    TEST_ASSERT_EQUAL_HEX8(0x3eu, bus.memory[0]);
    z80_candidate_destroy(candidate);
}

static void cycle_counter_rejects_wrap_before_candidate_tick(void) {
    test_bus bus = {0};
    z80_candidate *candidate = NULL;
    z80_candidate_snapshot before = {0};
    z80_candidate_snapshot after = {0};
    z80_candidate_tick_result tick = {0};
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &bus, &candidate));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(candidate, &before));
    before.cycles = UINT64_MAX;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_restore(candidate, &before));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_CYCLE_LIMIT,
                          z80_candidate_tick(candidate, false, false, &tick));
    TEST_ASSERT_EQUAL_UINT64(UINT64_MAX, tick.cycles);
    TEST_ASSERT_EQUAL_UINT(0u, bus.event_count);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(candidate, &after));
    TEST_ASSERT_EQUAL_INT(0, memcmp(&before, &after, sizeof(before)));
    z80_candidate_destroy(candidate);
}

static void restore_rejects_decoder_steps_outside_the_pinned_switch(void) {
    test_bus bus = {0};
    z80_candidate *candidate = NULL;
    z80_candidate_snapshot before = {0};
    z80_candidate_snapshot invalid = {0};
    z80_candidate_snapshot after = {0};

    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &bus, &candidate));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(candidate, &before));
    invalid = before;
    invalid.cpu.step = UINT16_MAX;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT,
                          z80_candidate_restore(candidate, &invalid));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(candidate, &after));
    TEST_ASSERT_EQUAL_INT(0, memcmp(&before, &after, sizeof(before)));
    TEST_ASSERT_EQUAL_UINT(0u, bus.event_count);
    z80_candidate_destroy(candidate);
}

static int snapshots_equal(const z80_candidate_snapshot *left,
                           const z80_candidate_snapshot *right) {
    return memcmp(left, right, sizeof(*left)) == 0;
}

static int event_traces_equal(const test_bus *left, const test_bus *right) {
    if (left->event_count != right->event_count) return 0;
    for (size_t index = 0u; index < left->event_count; ++index) {
        if (left->kinds[index] != right->kinds[index] ||
            left->addresses[index] != right->addresses[index] ||
            left->values[index] != right->values[index] ||
            left->event_cycles[index] != right->event_cycles[index]) return 0;
    }
    return 1;
}

static void write_test_u64_be(uint8_t *bytes, uint64_t value) {
    for (size_t index = 0u; index < 8u; ++index) {
        bytes[7u - index] = (uint8_t)value;
        value >>= 8;
    }
}

static void write_test_u16_be(uint8_t *bytes, uint16_t value) {
    bytes[0] = (uint8_t)(value >> 8);
    bytes[1] = (uint8_t)value;
}

static uint64_t read_test_u64_be(const uint8_t *bytes) {
    uint64_t value = 0u;
    for (size_t index = 0u; index < 8u; ++index) {
        value = (value << 8) | bytes[index];
    }
    return value;
}

static void load_state_microprogram(test_bus *bus) {
    static const uint8_t program[] = {
        0xedu, 0x56u,             /* IM 1 */
        0xfbu,                    /* EI */
        0x00u,                    /* NOP */
        0xddu, 0x21u, 0x00u, 0x20u, /* LD IX,0x2000 */
        0xddu, 0x36u, 0x01u, 0x5au, /* LD (IX+1),0x5a */
        0xedu, 0x44u,             /* NEG */
        0xcbu, 0x07u,             /* RLC A */
        0xddu, 0xcbu, 0x00u, 0x06u, /* RLC (IX+0) */
        0x76u                     /* HALT */
    };
    memcpy(bus->memory, program, sizeof(program));
    bus->memory[0x38u] = 0xc3u; /* bounded IM 1 handler: JP 0x0038 */
    bus->memory[0x39u] = 0x38u;
    bus->memory[0x3au] = 0x00u;
}

static void canonical_state_rebinds_across_live_decoder_microstates(void) {
    static const unsigned capture_cycles[] = {
        1u, 2u, 3u, 4u, 5u, 6u, 7u, 8u, 9u, 10u, 11u, 12u,
        13u, 14u, 15u, 16u, 17u, 18u, 19u, 20u, 21u, 22u, 23u,
        24u, 25u, 26u, 27u, 28u, 29u, 30u, 31u, 32u, 33u, 34u,
        35u, 36u, 37u, 38u, 39u, 40u, 41u, 42u, 43u, 44u, 45u,
        46u, 47u, 48u, 49u, 50u, 51u, 52u, 53u, 54u, 55u, 56u,
        57u, 58u, 59u, 60u, 61u, 62u, 63u, 64u, 65u, 66u, 67u,
        68u, 69u, 70u, 71u, 72u, 73u, 74u, 75u, 76u, 77u, 78u,
        79u, 80u
    };
    size_t ddfd_states = 0u;
    size_t ddcb_states = 0u;
    size_t ed_states = 0u;
    size_t cb_states = 0u;

    TEST_ASSERT_EQUAL_UINT(TEST_Z80_STATE_BYTES, z80_candidate_state_size());
    for (size_t trial = 0u;
         trial < sizeof(capture_cycles) / sizeof(capture_cycles[0]); ++trial) {
        test_bus source_bus = {0};
        test_bus destination_bus = {0};
        z80_candidate *source = NULL;
        z80_candidate *destination = NULL;
        z80_candidate_state *staged = NULL;
        z80_candidate_tick_result source_tick = {0};
        z80_candidate_tick_result destination_tick = {0};
        z80_candidate_snapshot source_snapshot = {0};
        uint8_t bytes[TEST_Z80_STATE_BYTES] = {0};
        uint8_t rebound_bytes[TEST_Z80_STATE_BYTES] = {0};
        size_t written = 0u;
        unsigned cut = capture_cycles[trial];

        load_state_microprogram(&source_bus);
        load_state_microprogram(&destination_bus);
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_create(test_bus_access, &source_bus,
                                                   &source));
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_create(test_bus_access,
                                                   &destination_bus,
                                                   &destination));
        TEST_ASSERT_TRUE(source_bus.memory != destination_bus.memory);
        TEST_ASSERT_TRUE(tick_many(&source_bus, source, cut, false, &source_tick));
        memcpy(destination_bus.memory, source_bus.memory,
               sizeof(destination_bus.memory));
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_capture(source, &source_snapshot));
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_state_capture(source, bytes,
                                                          sizeof(bytes), &written));
        TEST_ASSERT_EQUAL_UINT(TEST_Z80_STATE_BYTES, written);
        TEST_ASSERT_EQUAL_HEX8('G', bytes[0]);
        TEST_ASSERT_EQUAL_HEX8('Z', bytes[1]);
        TEST_ASSERT_EQUAL_HEX8('8', bytes[2]);
        TEST_ASSERT_EQUAL_HEX8('0', bytes[3]);
        TEST_ASSERT_EQUAL_HEX8(1u, bytes[4]);
        TEST_ASSERT_EQUAL_HEX8((source_snapshot.cpu.step >> 8) & 0xffu,
                               bytes[5]);
        TEST_ASSERT_EQUAL_HEX8(source_snapshot.cpu.step & 0xffu, bytes[6]);
        TEST_ASSERT_EQUAL_HEX8((source_snapshot.cpu.pc >> 8) & 0xffu,
                               bytes[29]);
        TEST_ASSERT_EQUAL_HEX8(source_snapshot.cpu.pc & 0xffu, bytes[30]);
        TEST_ASSERT_EQUAL_UINT64(source_snapshot.pins,
                                 read_test_u64_be(&bytes[60]));
        TEST_ASSERT_EQUAL_UINT64(source_snapshot.cycles,
                                 read_test_u64_be(&bytes[68]));
        if (source_snapshot.cpu.step >= TEST_Z80_DDFD_M1_T2 &&
            source_snapshot.cpu.step <= TEST_Z80_DDFD_LDHLN_OVERLAPPED) ++ddfd_states;
        if (source_snapshot.cpu.step >= 1621u && source_snapshot.cpu.step <= 1635u) {
            ++ddcb_states;
        }
        if ((source_snapshot.cpu.step >= TEST_Z80_ED_M1_T2 &&
             source_snapshot.cpu.step <= TEST_Z80_ED_M1_T4) ||
            (source_snapshot.cpu.step >= 256u && source_snapshot.cpu.step <= 511u)) {
            ++ed_states;
        }
        if ((source_snapshot.cpu.step >= TEST_Z80_CB_M1_T2 &&
             source_snapshot.cpu.step <= TEST_Z80_CB_M1_T4) ||
            (source_snapshot.cpu.step >= 1612u && source_snapshot.cpu.step <= 1620u)) {
            ++cb_states;
        }
        size_t event_count_before_stage = source_bus.event_count;
        size_t destination_event_count_before_stage = destination_bus.event_count;
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_state_stage(bytes, sizeof(bytes),
                                                        &staged));
        TEST_ASSERT_NOT_NULL(staged);
        TEST_ASSERT_EQUAL_UINT(event_count_before_stage, source_bus.event_count);
        TEST_ASSERT_EQUAL_UINT(destination_event_count_before_stage,
                               destination_bus.event_count);
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_state_rebind(staged, destination));
        TEST_ASSERT_EQUAL_UINT(event_count_before_stage, source_bus.event_count);
        TEST_ASSERT_EQUAL_UINT(destination_event_count_before_stage,
                               destination_bus.event_count);
        z80_candidate_state_apply(destination, staged);
        z80_candidate_state_discard(staged);
        staged = NULL;
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_state_capture(destination,
                                                          rebound_bytes,
                                                          sizeof(rebound_bytes),
                                                          &written));
        TEST_ASSERT_EQUAL_MEMORY(bytes, rebound_bytes, sizeof(bytes));

        source_bus.event_count = 0u;
        destination_bus.event_count = 0u;
        source_bus.current_cycle = cut;
        destination_bus.current_cycle = cut;
        memset(source_bus.kinds, 0, sizeof(source_bus.kinds));
        memset(destination_bus.kinds, 0, sizeof(destination_bus.kinds));
        memset(source_bus.addresses, 0, sizeof(source_bus.addresses));
        memset(destination_bus.addresses, 0, sizeof(destination_bus.addresses));
        memset(source_bus.values, 0, sizeof(source_bus.values));
        memset(destination_bus.values, 0, sizeof(destination_bus.values));
        memset(source_bus.event_cycles, 0, sizeof(source_bus.event_cycles));
        memset(destination_bus.event_cycles, 0, sizeof(destination_bus.event_cycles));
        for (unsigned cycle = 0u; cycle < 40u; ++cycle) {
            bool irq = cycle < 4u;
            bool nmi = cycle == 12u;
            source_bus.current_cycle++;
            destination_bus.current_cycle++;
            TEST_ASSERT_EQUAL_INT(z80_candidate_tick(source, irq, nmi,
                                                     &source_tick),
                                  z80_candidate_tick(destination, irq, nmi,
                                                     &destination_tick));
            TEST_ASSERT_EQUAL_UINT64(source_tick.cycles, destination_tick.cycles);
            TEST_ASSERT_EQUAL_UINT64(source_tick.pins, destination_tick.pins);
            TEST_ASSERT_EQUAL_INT(source_tick.instruction_complete,
                                  destination_tick.instruction_complete);
        }
        TEST_ASSERT_TRUE(event_traces_equal(&source_bus, &destination_bus));
        TEST_ASSERT_EQUAL_MEMORY(source_bus.memory, destination_bus.memory,
                                 sizeof(source_bus.memory));
        z80_candidate_destroy(destination);
        z80_candidate_destroy(source);
    }
    TEST_ASSERT_TRUE(ddfd_states > 0u);
    TEST_ASSERT_TRUE(ddcb_states > 0u);
    TEST_ASSERT_TRUE(ed_states > 0u);
    TEST_ASSERT_TRUE(cb_states > 0u);
    printf("z80_canonical_continuations=%zu ddfd=%zu ddcb=%zu ed=%zu cb=%zu bytes=%u\n",
           sizeof(capture_cycles) / sizeof(capture_cycles[0]), ddfd_states,
           ddcb_states, ed_states, cb_states, TEST_Z80_STATE_BYTES);
}

static void canonical_state_rejects_bad_lengths_bools_and_decoder_relations(void) {
    enum {
        STATE_STEP_OFFSET = 5,
        STATE_HLX_INDEX_OFFSET = 11,
        STATE_PREFIX_OFFSET = 12,
        STATE_INT_BITS_OFFSET = 21,
        STATE_IM_OFFSET = 57,
        STATE_IFF1_OFFSET = 58,
        STATE_IFF2_OFFSET = 59,
        STATE_PINS_OFFSET = 60
    };
    test_bus bus = {0};
    z80_candidate *candidate = NULL;
    z80_candidate_state *staged = NULL;
    uint8_t valid[TEST_Z80_STATE_BYTES] = {0};
    uint8_t short_buffer[TEST_Z80_STATE_BYTES - 1u] = {0};
    uint8_t invalid[TEST_Z80_STATE_BYTES];
    size_t written = 0u;
    size_t rejected = 0u;

    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &bus, &candidate));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_capture(candidate, valid,
                                                      sizeof(valid), &written));
    TEST_ASSERT_EQUAL_UINT(TEST_Z80_STATE_BYTES, written);
    written = 1u;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_ARGUMENT,
                          z80_candidate_state_capture(candidate, short_buffer,
                                                      sizeof(short_buffer), &written));
    TEST_ASSERT_EQUAL_UINT(0u, written);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT,
                          z80_candidate_state_stage(valid, sizeof(valid) - 1u,
                                                   &staged));
    TEST_ASSERT_NULL(staged);
    ++rejected;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT,
                          z80_candidate_state_stage(valid, sizeof(valid) + 1u,
                                                   &staged));
    TEST_ASSERT_NULL(staged);
    ++rejected;

#define ASSERT_INVALID_BYTE(field_offset, field_value) do { \
        memcpy(invalid, valid, sizeof(invalid)); \
        invalid[(field_offset)] = (uint8_t)(field_value); \
        staged = NULL; \
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT, \
                              z80_candidate_state_stage(invalid, sizeof(invalid), \
                                                       &staged)); \
        TEST_ASSERT_NULL(staged); \
        ++rejected; \
    } while (0)
    memcpy(invalid, valid, sizeof(invalid));
    invalid[STATE_STEP_OFFSET] = 0xffu;
    invalid[STATE_STEP_OFFSET + 1u] = 0xffu;
    staged = NULL;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT,
                          z80_candidate_state_stage(invalid, sizeof(invalid),
                                                   &staged));
    TEST_ASSERT_NULL(staged);
    ++rejected;

    ASSERT_INVALID_BYTE(0u, 'X');
    ASSERT_INVALID_BYTE(4u, 0u);
    ASSERT_INVALID_BYTE(STATE_PREFIX_OFFSET, 2u);
    ASSERT_INVALID_BYTE(STATE_IFF1_OFFSET, 2u);
    ASSERT_INVALID_BYTE(STATE_IFF2_OFFSET, 2u);
    ASSERT_INVALID_BYTE(STATE_HLX_INDEX_OFFSET, 1u);
    memcpy(invalid, valid, sizeof(invalid));
    invalid[STATE_HLX_INDEX_OFFSET] = 1u;
    invalid[STATE_PREFIX_OFFSET] = 0u;
    staged = NULL;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT,
                          z80_candidate_state_stage(invalid, sizeof(invalid),
                                                   &staged));
    TEST_ASSERT_NULL(staged);
    ++rejected;

    memcpy(invalid, valid, sizeof(invalid));
    invalid[STATE_STEP_OFFSET] = (uint8_t)(TEST_Z80_INT_IM1_STEP >> 8);
    invalid[STATE_STEP_OFFSET + 1u] = (uint8_t)TEST_Z80_INT_IM1_STEP;
    invalid[STATE_IM_OFFSET] = 0u;
    staged = NULL;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT,
                          z80_candidate_state_stage(invalid, sizeof(invalid),
                                                   &staged));
    TEST_ASSERT_NULL(staged);
    ++rejected;

    memcpy(invalid, valid, sizeof(invalid));
    invalid[STATE_INT_BITS_OFFSET] = 1u;
    staged = NULL;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT,
                          z80_candidate_state_stage(invalid, sizeof(invalid),
                                                   &staged));
    TEST_ASSERT_NULL(staged);
    ++rejected;

    memcpy(invalid, valid, sizeof(invalid));
    uint64_t pins = Z80_INT;
    write_test_u64_be(&invalid[STATE_PINS_OFFSET], pins);
    staged = NULL;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT,
                          z80_candidate_state_stage(invalid, sizeof(invalid),
                                                   &staged));
    TEST_ASSERT_NULL(staged);
    ++rejected;
    TEST_ASSERT_EQUAL_UINT(0u, bus.event_count);
    printf("z80_invalid_state_cases=%zu source_callbacks=0\n", rejected);
#undef ASSERT_INVALID_BYTE
    z80_candidate_destroy(candidate);
}

static void canonical_state_rejects_mismatched_prefix_entry_opcodes(void) {
    test_bus bus = {0};
    z80_candidate *candidate = NULL;
    z80_candidate_state *staged = NULL;
    z80_candidate_snapshot initial = {0};
    uint8_t bytes[TEST_Z80_STATE_BYTES] = {0};
    uint8_t invalid[TEST_Z80_STATE_BYTES];
    size_t written = 0u;
    z80_candidate_status status;

    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &bus, &candidate));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(candidate, &initial));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_capture(candidate, bytes,
                                                      sizeof(bytes), &written));

    /* _z80_fetch_dd/fd retains the prefix byte at decoder step 1685. */
    memcpy(invalid, bytes, sizeof(invalid));
    write_test_u16_be(&invalid[5], TEST_Z80_DDFD_M1_T2);
    invalid[10] = 0x3eu;
    invalid[11] = 1u;
    invalid[12] = 1u;
    status = z80_candidate_state_stage(invalid, sizeof(invalid), &staged);
    z80_candidate_state_discard(staged);
    staged = NULL;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT, status);

    memcpy(invalid, bytes, sizeof(invalid));
    write_test_u16_be(&invalid[5], TEST_Z80_DDFD_M1_T2);
    invalid[10] = 0xfdu; /* FD cannot select IX. */
    invalid[11] = 1u;
    invalid[12] = 1u;
    status = z80_candidate_state_stage(invalid, sizeof(invalid), &staged);
    z80_candidate_state_discard(staged);
    staged = NULL;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT, status);

    memcpy(invalid, bytes, sizeof(invalid));
    write_test_u16_be(&invalid[5], TEST_Z80_CB_M1_T2);
    invalid[10] = 0x00u;
    invalid[12] = 1u;
    status = z80_candidate_state_stage(invalid, sizeof(invalid), &staged);
    z80_candidate_state_discard(staged);
    staged = NULL;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT, status);

    memcpy(invalid, bytes, sizeof(invalid));
    write_test_u16_be(&invalid[5], TEST_Z80_ED_M1_T2);
    invalid[10] = 0x00u;
    invalid[12] = 1u;
    status = z80_candidate_state_stage(invalid, sizeof(invalid), &staged);
    z80_candidate_state_discard(staged);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_INVALID_SNAPSHOT, status);
    z80_candidate_destroy(candidate);
    printf("z80_prefix_opcode_invalid_cases=4\n");
}

static void canonical_state_resumes_a_pending_im1_acknowledgement(void) {
    test_bus source_bus = {0};
    test_bus destination_bus = {0};
    z80_candidate *source = NULL;
    z80_candidate *destination = NULL;
    z80_candidate_state *staged = NULL;
    z80_candidate_snapshot checkpoint = {0};
    z80_candidate_tick_result source_tick = {0};
    z80_candidate_tick_result destination_tick = {0};
    uint8_t bytes[TEST_Z80_STATE_BYTES] = {0};
    size_t written = 0u;
    bool found_interrupt_step = false;

    configure_im1_irq_program(&source_bus);
    configure_im1_irq_program(&destination_bus);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &source_bus,
                                               &source));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access,
                                               &destination_bus, &destination));
    for (unsigned cycle = 1u; cycle <= 40u; ++cycle) {
        TEST_ASSERT_TRUE(tick_once(&source_bus, source, cycle >= 16u,
                                   &source_tick));
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_capture(source, &checkpoint));
        if (checkpoint.cpu.step >= TEST_Z80_INT_IM1_STEP &&
            checkpoint.cpu.step <= 1654u) {
            found_interrupt_step = true;
            break;
        }
    }
    TEST_ASSERT_TRUE(found_interrupt_step);
    TEST_ASSERT_TRUE(checkpoint.cpu.iff1);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_capture(source, bytes,
                                                      sizeof(bytes), &written));
    memcpy(destination_bus.memory, source_bus.memory,
           sizeof(destination_bus.memory));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_stage(bytes, sizeof(bytes),
                                                    &staged));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_rebind(staged, destination));
    z80_candidate_state_apply(destination, staged);
    z80_candidate_state_discard(staged);
    source_bus.event_count = 0u;
    destination_bus.event_count = 0u;
    source_bus.current_cycle = checkpoint.cycles;
    destination_bus.current_cycle = checkpoint.cycles;
    for (unsigned cycle = 0u; cycle < 24u; ++cycle) {
        source_bus.current_cycle++;
        destination_bus.current_cycle++;
        TEST_ASSERT_EQUAL_INT(z80_candidate_tick(source, true, false,
                                                 &source_tick),
                              z80_candidate_tick(destination, true, false,
                                                 &destination_tick));
        TEST_ASSERT_EQUAL_UINT64(source_tick.cycles, destination_tick.cycles);
        TEST_ASSERT_EQUAL_UINT64(source_tick.pins, destination_tick.pins);
    }
    TEST_ASSERT_TRUE(event_traces_equal(&source_bus, &destination_bus));
    TEST_ASSERT_TRUE(find_event(&source_bus, Z80_CANDIDATE_BUS_INTERRUPT_ACK) <
                     source_bus.event_count);
    TEST_ASSERT_EQUAL_MEMORY(source_bus.memory, destination_bus.memory,
                             sizeof(source_bus.memory));
    printf("z80_irq_microstate_step=%u irq_cycles=%llu ack_events=%zu\n",
           (unsigned)checkpoint.cpu.step,
           (unsigned long long)checkpoint.cycles,
           source_bus.event_count);
    z80_candidate_destroy(destination);
    z80_candidate_destroy(source);
}

static void canonical_state_resumes_inside_nmi_entry(void) {
    test_bus source_bus = {0};
    test_bus destination_bus = {0};
    z80_candidate *source = NULL;
    z80_candidate *destination = NULL;
    z80_candidate_state *staged = NULL;
    z80_candidate_snapshot checkpoint = {0};
    z80_candidate_tick_result source_tick = {0};
    z80_candidate_tick_result destination_tick = {0};
    uint8_t bytes[TEST_Z80_STATE_BYTES] = {0};
    size_t written = 0u;
    bool found_nmi_step = false;

    source_bus.memory[0x66u] = 0xc3u; /* bounded NMI handler: JP 0x0066 */
    source_bus.memory[0x67u] = 0x66u;
    source_bus.memory[0x68u] = 0x00u;
    memcpy(destination_bus.memory, source_bus.memory,
           sizeof(destination_bus.memory));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &source_bus,
                                               &source));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access,
                                               &destination_bus, &destination));
    TEST_ASSERT_TRUE(tick_once(&source_bus, source, false, &source_tick));
    /* Re-arm with a low-to-high edge, then let the edge latch while the pin falls. */
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_tick(source, false, true, &source_tick));
    source_bus.current_cycle++;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_tick(source, false, false, &source_tick));
    source_bus.current_cycle++;
    for (unsigned cycle = 0u; cycle < 32u; ++cycle) {
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_capture(source, &checkpoint));
        if (checkpoint.cpu.step >= 1674u && checkpoint.cpu.step <= 1684u) {
            found_nmi_step = true;
            break;
        }
        TEST_ASSERT_TRUE(tick_once(&source_bus, source, false, &source_tick));
    }
    TEST_ASSERT_TRUE(found_nmi_step);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_capture(source, bytes,
                                                      sizeof(bytes), &written));
    memcpy(destination_bus.memory, source_bus.memory,
           sizeof(destination_bus.memory));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_stage(bytes, sizeof(bytes),
                                                    &staged));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_rebind(staged, destination));
    z80_candidate_state_apply(destination, staged);
    z80_candidate_state_discard(staged);
    source_bus.event_count = 0u;
    destination_bus.event_count = 0u;
    source_bus.current_cycle = checkpoint.cycles;
    destination_bus.current_cycle = checkpoint.cycles;
    for (unsigned cycle = 0u; cycle < 32u; ++cycle) {
        source_bus.current_cycle++;
        destination_bus.current_cycle++;
        TEST_ASSERT_EQUAL_INT(z80_candidate_tick(source, false, false,
                                                 &source_tick),
                              z80_candidate_tick(destination, false, false,
                                                 &destination_tick));
        TEST_ASSERT_EQUAL_UINT64(source_tick.cycles, destination_tick.cycles);
        TEST_ASSERT_EQUAL_UINT64(source_tick.pins, destination_tick.pins);
    }
    TEST_ASSERT_TRUE(event_traces_equal(&source_bus, &destination_bus));
    TEST_ASSERT_TRUE(find_event(&source_bus, Z80_CANDIDATE_BUS_MEMORY_WRITE) <
                     source_bus.event_count);
    TEST_ASSERT_EQUAL_MEMORY(source_bus.memory, destination_bus.memory,
                             sizeof(source_bus.memory));
    printf("z80_nmi_microstate_step=%u cycles=%llu bus_events=%zu\n",
           (unsigned)checkpoint.cpu.step,
           (unsigned long long)checkpoint.cycles,
           source_bus.event_count);
    z80_candidate_destroy(destination);
    z80_candidate_destroy(source);
}

static void canonical_staging_allocation_failures_preserve_destination_and_peer(void) {
    test_bus source_bus = {0};
    test_bus target_bus = {0};
    test_bus peer_bus = {0};
    test_bus create_failure_bus = {0};
    test_bus success_bus = {0};
    z80_candidate *source = NULL;
    z80_candidate *target = NULL;
    z80_candidate *peer = NULL;
    z80_candidate *success = NULL;
    z80_candidate_state *staged = NULL;
    z80_candidate_snapshot before_target = {0};
    z80_candidate_snapshot before_peer = {0};
    z80_candidate_snapshot after_target = {0};
    z80_candidate_snapshot after_peer = {0};
    z80_candidate_tick_result source_tick = {0};
    z80_candidate_tick_result target_tick = {0};
    z80_candidate_tick_result peer_tick = {0};
    uint8_t bytes[TEST_Z80_STATE_BYTES] = {0};
    size_t written = 0u;
    z80_candidate_test_failpoint create_failure = {.fail_at = 1u};
    z80_candidate_test_failpoint stage_failure = {.fail_at = 2u};
    z80_candidate_test_failpoint success_allocator = {0};
    size_t target_events_before_stage;
    size_t peer_events_before_stage;

    load_state_microprogram(&source_bus);
    load_state_microprogram(&target_bus);
    load_state_microprogram(&peer_bus);
    load_state_microprogram(&create_failure_bus);
    load_state_microprogram(&success_bus);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &source_bus,
                                               &source));
    TEST_ASSERT_TRUE(tick_many(&source_bus, source, 18u, false, &source_tick));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_capture(source, bytes,
                                                      sizeof(bytes), &written));

    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OUT_OF_MEMORY,
                          z80_candidate_test_create(test_bus_access,
                                                    &create_failure_bus,
                                                    &create_failure, &target));
    TEST_ASSERT_NULL(target);
    TEST_ASSERT_EQUAL_UINT(1u, create_failure.attempts);
    TEST_ASSERT_EQUAL_UINT(0u, create_failure.allocations);
    TEST_ASSERT_EQUAL_UINT(0u, create_failure.frees);
    TEST_ASSERT_EQUAL_UINT(0u, create_failure_bus.event_count);

    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_test_create(test_bus_access, &target_bus,
                                                    &stage_failure, &target));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &peer_bus, &peer));
    TEST_ASSERT_TRUE(tick_many(&target_bus, target, 10u, false, &target_tick));
    TEST_ASSERT_TRUE(tick_many(&peer_bus, peer, 10u, false, &peer_tick));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(target, &before_target));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(peer, &before_peer));
    TEST_ASSERT_EQUAL_INT(1, snapshots_equal(&before_target, &before_peer));
    target_events_before_stage = target_bus.event_count;
    peer_events_before_stage = peer_bus.event_count;

    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OUT_OF_MEMORY,
                          z80_candidate_state_test_stage(bytes, sizeof(bytes),
                                                        &stage_failure, &staged));
    TEST_ASSERT_NULL(staged);
    TEST_ASSERT_EQUAL_UINT(2u, stage_failure.attempts);
    TEST_ASSERT_EQUAL_UINT(1u, stage_failure.allocations);
    TEST_ASSERT_EQUAL_UINT(0u, stage_failure.frees);
    TEST_ASSERT_EQUAL_UINT(target_events_before_stage, target_bus.event_count);
    TEST_ASSERT_EQUAL_UINT(peer_events_before_stage, peer_bus.event_count);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(target, &after_target));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(peer, &after_peer));
    TEST_ASSERT_EQUAL_INT(1, snapshots_equal(&before_target, &after_target));
    TEST_ASSERT_EQUAL_INT(1, snapshots_equal(&before_peer, &after_peer));

    target_bus.event_count = 0u;
    peer_bus.event_count = 0u;
    target_bus.current_cycle = before_target.cycles;
    peer_bus.current_cycle = before_peer.cycles;
    TEST_ASSERT_TRUE(tick_many(&target_bus, target, 24u, true, &target_tick));
    TEST_ASSERT_TRUE(tick_many(&peer_bus, peer, 24u, true, &peer_tick));
    TEST_ASSERT_EQUAL_UINT64(target_tick.cycles, peer_tick.cycles);
    TEST_ASSERT_TRUE(event_traces_equal(&target_bus, &peer_bus));
    TEST_ASSERT_EQUAL_MEMORY(target_bus.memory, peer_bus.memory,
                             sizeof(target_bus.memory));
    z80_candidate_destroy(target);
    target = NULL;
    z80_candidate_destroy(peer);
    peer = NULL;
    TEST_ASSERT_EQUAL_UINT(1u, stage_failure.allocations);
    TEST_ASSERT_EQUAL_UINT(1u, stage_failure.frees);

    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_test_create(test_bus_access, &success_bus,
                                                    &success_allocator, &success));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_test_stage(bytes, sizeof(bytes),
                                                        &success_allocator, &staged));
    TEST_ASSERT_EQUAL_UINT(2u, success_allocator.attempts);
    TEST_ASSERT_EQUAL_UINT(2u, success_allocator.allocations);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_rebind(staged, success));
    z80_candidate_state_apply(success, staged);
    z80_candidate_state_discard(staged);
    staged = NULL;
    z80_candidate_destroy(success);
    success = NULL;
    TEST_ASSERT_EQUAL_UINT(2u, success_allocator.frees);
    printf("z80_allocation_sites=2 create_failures=1 stage_failures=1 "
           "successful_allocations_after_sweep=2 leaks=0 unchanged_peer=1\n");
    z80_candidate_destroy(source);
}

static void canonical_capture_and_rebind_reject_faulted_candidates(void) {
    test_bus source_bus = {0};
    test_bus target_bus = {0};
    z80_candidate *source = NULL;
    z80_candidate *faulted_source = NULL;
    z80_candidate *faulted_target = NULL;
    z80_candidate_state *staged = NULL;
    z80_candidate_tick_result tick = {0};
    uint8_t valid[TEST_Z80_STATE_BYTES] = {0};
    uint8_t rejected[TEST_Z80_STATE_BYTES];
    uint8_t before[TEST_Z80_STATE_BYTES];
    size_t written = 0u;
    size_t rejected_written = 1u;

    memset(rejected, 0xa5, sizeof(rejected));
    memcpy(before, rejected, sizeof(before));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &source_bus,
                                               &source));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_capture(source, valid,
                                                      sizeof(valid), &written));

    source_bus.fail_on_event = 1u;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &source_bus,
                                               &faulted_source));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_FAILURE,
                          z80_candidate_tick(faulted_source, false, false, &tick));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_FAILURE,
                          z80_candidate_state_capture(faulted_source, rejected,
                                                      sizeof(rejected),
                                                      &rejected_written));
    TEST_ASSERT_EQUAL_UINT(0u, rejected_written);
    TEST_ASSERT_EQUAL_MEMORY(before, rejected, sizeof(before));

    target_bus.fail_on_event = 1u;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &target_bus,
                                               &faulted_target));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_FAILURE,
                          z80_candidate_tick(faulted_target, false, false, &tick));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_state_stage(valid, sizeof(valid), &staged));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_FAILURE,
                          z80_candidate_state_rebind(staged, faulted_target));
    TEST_ASSERT_EQUAL_UINT(1u, target_bus.event_count);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_FAILURE,
                          z80_candidate_tick(faulted_target, false, false, &tick));
    TEST_ASSERT_EQUAL_UINT(1u, target_bus.event_count);
    z80_candidate_state_discard(staged);
    printf("z80_faulted_state_cases=2 source_capture_rejected=1 target_rebind_rejected=1 callbacks_after_failure=0\n");
    z80_candidate_destroy(faulted_target);
    z80_candidate_destroy(faulted_source);
    z80_candidate_destroy(source);
}

static void continuation_replays_from_supported_instruction_boundary(void) {
    test_bus bus = {0};
    test_bus first_trace = {0};
    uint8_t checkpoint_memory[TEST_MEMORY_SIZE];
    z80_candidate *candidate = NULL;
    z80_candidate_snapshot checkpoint = {0};
    z80_candidate_snapshot first_result = {0};
    z80_candidate_snapshot replay_result = {0};
    z80_candidate_tick_result tick = {0};
    bus.memory[0] = 0x3eu;
    bus.memory[1] = 0x5au;
    bus.memory[2] = 0x32u;
    bus.memory[3] = 0x00u;
    bus.memory[4] = 0x40u;
    bus.memory[5] = 0x76u;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &bus, &candidate));
    TEST_ASSERT_TRUE(tick_many(&bus, candidate, 8u, false, &tick));
    TEST_ASSERT_TRUE(tick.instruction_complete);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(candidate, &checkpoint));
    memcpy(checkpoint_memory, bus.memory, sizeof(checkpoint_memory));
    bus.event_count = 0u;

    TEST_ASSERT_TRUE(tick_many(&bus, candidate, 13u, false, &tick));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(candidate, &first_result));
    first_trace = bus;

    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_restore(candidate, &checkpoint));
    memcpy(bus.memory, checkpoint_memory, sizeof(bus.memory));
    bus.current_cycle = checkpoint.cycles;
    bus.event_count = 0u;
    memset(bus.kinds, 0, sizeof(bus.kinds));
    memset(bus.addresses, 0, sizeof(bus.addresses));
    memset(bus.values, 0, sizeof(bus.values));
    memset(bus.event_cycles, 0, sizeof(bus.event_cycles));
    TEST_ASSERT_TRUE(tick_many(&bus, candidate, 13u, false, &tick));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(candidate, &replay_result));
    if (mutation == MUTATION_CONTINUATION) replay_result.cpu.a ^= 1u;
    TEST_ASSERT_EQUAL_INT(1, snapshots_equal(&first_result, &replay_result));
    TEST_ASSERT_TRUE(event_traces_equal(&first_trace, &bus));
    TEST_ASSERT_EQUAL_HEX8(0x5au, bus.memory[0x4000u]);
    z80_candidate_destroy(candidate);
}

static void configure_im1_irq_program(test_bus *bus) {
    bus->memory[0] = 0xedu; /* IM 1: 8T. */
    bus->memory[1] = 0x56u;
    bus->memory[2] = 0xfbu; /* EI: 4T, then one following instruction. */
    bus->memory[3] = 0x00u; /* NOP: 4T. */
    bus->memory[4] = 0x76u; /* HALT if the request is missed. */
    bus->memory[0x38u] = 0xc3u; /* JP 0x0038 keeps the handler bounded. */
    bus->memory[0x39u] = 0x38u;
    bus->memory[0x3au] = 0x00u;
}

static size_t find_event(const test_bus *bus, z80_candidate_bus_kind kind) {
    for (size_t index = 0u; index < bus->event_count; ++index) {
        if (bus->kinds[index] == kind) return index;
    }
    return bus->event_count;
}

static void irq_is_accepted_at_the_adjacent_documented_boundary(void) {
    test_bus early_bus = {0};
    z80_candidate *early = NULL;
    z80_candidate_tick_result tick = {0};
    configure_im1_irq_program(&early_bus);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &early_bus, &early));
    for (unsigned cycle = 1u; cycle <= 15u; ++cycle) {
        TEST_ASSERT_TRUE(tick_once(&early_bus, early, cycle == 15u, &tick));
    }
    TEST_ASSERT_TRUE(tick_many(&early_bus, early, 18u, false, &tick));
    TEST_ASSERT_EQUAL_UINT(early_bus.event_count,
                           find_event(&early_bus, Z80_CANDIDATE_BUS_INTERRUPT_ACK));
    z80_candidate_destroy(early);

    test_bus boundary_bus = {0};
    z80_candidate *boundary = NULL;
    z80_candidate_snapshot snapshot = {0};
    configure_im1_irq_program(&boundary_bus);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &boundary_bus, &boundary));
    for (unsigned cycle = 1u; cycle <= 16u; ++cycle) {
        TEST_ASSERT_TRUE(tick_once(&boundary_bus, boundary, cycle == 16u, &tick));
    }
    TEST_ASSERT_EQUAL_UINT(boundary_bus.event_count,
                           find_event(&boundary_bus, Z80_CANDIDATE_BUS_INTERRUPT_ACK));
    TEST_ASSERT_TRUE(tick_many(&boundary_bus, boundary, 3u, false, &tick));
    size_t ack_event = find_event(&boundary_bus, Z80_CANDIDATE_BUS_INTERRUPT_ACK);
    TEST_ASSERT_TRUE(ack_event < boundary_bus.event_count);
    uint64_t observed_ack_cycle = boundary_bus.event_cycles[ack_event] +
        (mutation == MUTATION_IRQ ? UINT64_C(1) : UINT64_C(0));
    TEST_ASSERT_EQUAL_UINT64(19u, observed_ack_cycle);
    TEST_ASSERT_TRUE(tick_many(&boundary_bus, boundary, 11u, false, &tick));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(boundary, &snapshot));
    TEST_ASSERT_EQUAL_HEX16(0x0039u, snapshot.cpu.pc);
    TEST_ASSERT_EQUAL_HEX8(0x00u, boundary_bus.memory[0xfffeu]);
    TEST_ASSERT_EQUAL_HEX8(0x04u, boundary_bus.memory[0xfffdu]);
    z80_candidate_destroy(boundary);
}

typedef struct {
    test_bus bus;
    z80_candidate *candidate;
    z80_candidate_snapshot snapshot;
} isolated_result;

#ifndef _WIN32
typedef struct {
    test_bus *bus;
    z80_candidate *candidate;
    int ok;
} thread_run;
#endif

static void configure_distinguishable_program(test_bus *bus, uint8_t value,
                                               uint16_t destination) {
    bus->memory[0] = 0x3eu;
    bus->memory[1] = value;
    bus->memory[2] = 0x32u;
    bus->memory[3] = (uint8_t)destination;
    bus->memory[4] = (uint8_t)(destination >> 8);
    bus->memory[5] = 0x18u;
    bus->memory[6] = 0xfau;
}

#ifndef _WIN32
static void *run_threaded_program(void *userdata) {
    thread_run *run = userdata;
    z80_candidate_tick_result tick = {0};
    run->ok = tick_many(run->bus, run->candidate, TEST_PROGRAM_CYCLES, false, &tick);
    return NULL;
}
#endif

static int run_isolated(uint8_t value, uint16_t destination,
                        isolated_result *result) {
    z80_candidate_tick_result tick = {0};
    memset(result, 0, sizeof(*result));
    configure_distinguishable_program(&result->bus, value, destination);
    if (z80_candidate_create(test_bus_access, &result->bus, &result->candidate) !=
        Z80_CANDIDATE_OK) return 0;
    int okay = tick_many(&result->bus, result->candidate, TEST_PROGRAM_CYCLES,
                         false, &tick) &&
               z80_candidate_capture(result->candidate, &result->snapshot) ==
                   Z80_CANDIDATE_OK;
    z80_candidate_destroy(result->candidate);
    result->candidate = NULL;
    return okay;
}

static int compare_to_baseline(const isolated_result *actual,
                               const isolated_result *expected) {
    return snapshots_equal(&actual->snapshot, &expected->snapshot) &&
           memcmp(actual->bus.memory, expected->bus.memory,
                  sizeof(actual->bus.memory)) == 0 &&
           event_traces_equal(&actual->bus, &expected->bus);
}

static void two_distinguishable_instances_match_isolated_baselines(void) {
    isolated_result baselines[2];
    isolated_result interleaved[2];
    TEST_ASSERT_TRUE(run_isolated(0x11u, 0x4000u, &baselines[0]));
    TEST_ASSERT_TRUE(run_isolated(0x22u, 0x4001u, &baselines[1]));
    TEST_ASSERT_FALSE(snapshots_equal(&baselines[0].snapshot,
                                      &baselines[1].snapshot));

    memset(interleaved, 0, sizeof(interleaved));
    configure_distinguishable_program(&interleaved[0].bus, 0x11u, 0x4000u);
    configure_distinguishable_program(&interleaved[1].bus, 0x22u, 0x4001u);
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_create(test_bus_access,
                                                   &interleaved[owner].bus,
                                                   &interleaved[owner].candidate));
    }
    for (unsigned cycle = 0u; cycle < TEST_PROGRAM_CYCLES; ++cycle) {
        unsigned first = (cycle & 1u) == 0u ? 0u : 1u;
        unsigned order[2] = {first, 1u - first};
        for (unsigned turn = 0u; turn < 2u; ++turn) {
            z80_candidate_tick_result tick = {0};
            unsigned owner = order[turn];
            TEST_ASSERT_TRUE(tick_once(&interleaved[owner].bus,
                                       interleaved[owner].candidate, false, &tick));
        }
    }
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                              z80_candidate_capture(interleaved[owner].candidate,
                                                    &interleaved[owner].snapshot));
        TEST_ASSERT_TRUE(compare_to_baseline(
            mutation == MUTATION_INSTANCE && owner == 0u
                ? &baselines[1]
                : &interleaved[owner],
            &baselines[owner]));
    }
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        z80_candidate_destroy(interleaved[owner].candidate);
    }

#ifndef _WIN32
    for (unsigned iteration = 0u; iteration < 16u; ++iteration) {
        isolated_result concurrent[2];
        thread_run runs[2];
        pthread_t threads[2];
        memset(concurrent, 0, sizeof(concurrent));
        for (unsigned owner = 0u; owner < 2u; ++owner) {
            configure_distinguishable_program(&concurrent[owner].bus,
                                              owner == 0u ? 0x11u : 0x22u,
                                              owner == 0u ? 0x4000u : 0x4001u);
            TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                                  z80_candidate_create(test_bus_access,
                                                       &concurrent[owner].bus,
                                                       &concurrent[owner].candidate));
            runs[owner] = (thread_run){&concurrent[owner].bus,
                                       concurrent[owner].candidate, 0};
            TEST_ASSERT_EQUAL_INT(0, pthread_create(&threads[owner], NULL,
                                                    run_threaded_program,
                                                    &runs[owner]));
        }
        for (unsigned owner = 0u; owner < 2u; ++owner) {
            TEST_ASSERT_EQUAL_INT(0, pthread_join(threads[owner], NULL));
            TEST_ASSERT_TRUE(runs[owner].ok);
            TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                                  z80_candidate_capture(concurrent[owner].candidate,
                                                        &concurrent[owner].snapshot));
            TEST_ASSERT_TRUE(compare_to_baseline(&concurrent[owner],
                                                 &baselines[owner]));
            z80_candidate_destroy(concurrent[owner].candidate);
        }
    }
#endif
    TEST_ASSERT_EQUAL_HEX8(0x11u, baselines[0].bus.memory[0x4000u]);
    TEST_ASSERT_EQUAL_HEX8(0x22u, baselines[1].bus.memory[0x4001u]);
#ifndef _WIN32
    printf("z80_instance_pairs=16 cycles_per_instance=%u interleaved=1 concurrent=1\n",
           TEST_PROGRAM_CYCLES);
#else
    printf("z80_instance_owners=2 cycles_per_instance=%u interleaved=1 concurrent=not-run\n",
           TEST_PROGRAM_CYCLES);
#endif
}

static void failed_bus_latches_until_reset_and_cannot_be_restored_around(void) {
    test_bus bus = {0};
    z80_candidate *candidate = NULL;
    z80_candidate_snapshot checkpoint = {0};
    z80_candidate_tick_result tick = {0};
    bus.memory[0] = 0x00u;
    bus.fail_on_event = 1u;
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_create(test_bus_access, &bus, &candidate));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK,
                          z80_candidate_capture(candidate, &checkpoint));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_FAILURE,
                          z80_candidate_tick(candidate, false, false, &tick));
    TEST_ASSERT_EQUAL_UINT64(1u, tick.cycles);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_FAILURE,
                          z80_candidate_tick(candidate, false, false, &tick));
    TEST_ASSERT_EQUAL_UINT64(1u, tick.cycles);
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_BUS_FAILURE,
                          z80_candidate_restore(candidate, &checkpoint));
    TEST_ASSERT_EQUAL_INT(Z80_CANDIDATE_OK, z80_candidate_reset(candidate));
    TEST_ASSERT_TRUE(tick_once(&bus, candidate, false, &tick));
    TEST_ASSERT_EQUAL_UINT64(1u, tick.cycles);
    TEST_ASSERT_EQUAL_UINT(2u, bus.event_count);
    z80_candidate_destroy(candidate);
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--mutation=cycle") == 0) mutation = MUTATION_CYCLE;
    else if (argc == 2 && strcmp(argv[1], "--mutation=bus") == 0) mutation = MUTATION_BUS;
    else if (argc == 2 && strcmp(argv[1], "--mutation=irq") == 0) mutation = MUTATION_IRQ;
    else if (argc == 2 && strcmp(argv[1], "--mutation=continuation") == 0) mutation = MUTATION_CONTINUATION;
    else if (argc == 2 && strcmp(argv[1], "--mutation=instance") == 0) mutation = MUTATION_INSTANCE;
    else if (argc == 2 && strcmp(argv[1], "--case=failure-latch") == 0) {
        UNITY_BEGIN();
        RUN_TEST(failed_bus_latches_until_reset_and_cannot_be_restored_around);
        return UNITY_END();
    } else if (argc != 1) {
        fputs("unknown z80_admission_test option\n", stderr);
        return 2;
    }
    UNITY_BEGIN();
    RUN_TEST(one_instruction_reads_opcode_and_immediate);
    RUN_TEST(bus_program_runs_documented_memory_write_cycles);
    RUN_TEST(reset_reinitializes_candidate_but_preserves_external_memory);
    RUN_TEST(cycle_counter_rejects_wrap_before_candidate_tick);
    RUN_TEST(restore_rejects_decoder_steps_outside_the_pinned_switch);
    RUN_TEST(canonical_state_rebinds_across_live_decoder_microstates);
    RUN_TEST(canonical_state_rejects_bad_lengths_bools_and_decoder_relations);
    RUN_TEST(canonical_state_rejects_mismatched_prefix_entry_opcodes);
    RUN_TEST(canonical_state_resumes_a_pending_im1_acknowledgement);
    RUN_TEST(canonical_state_resumes_inside_nmi_entry);
    RUN_TEST(canonical_staging_allocation_failures_preserve_destination_and_peer);
    RUN_TEST(canonical_capture_and_rebind_reject_faulted_candidates);
    RUN_TEST(continuation_replays_from_supported_instruction_boundary);
    RUN_TEST(irq_is_accepted_at_the_adjacent_documented_boundary);
    RUN_TEST(two_distinguishable_instances_match_isolated_baselines);
    RUN_TEST(failed_bus_latches_until_reset_and_cannot_be_restored_around);
    return UNITY_END();
}
