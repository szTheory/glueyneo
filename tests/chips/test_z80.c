/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "z80_candidate.h"

#include <stdio.h>
#include <string.h>

#ifndef _WIN32
#include <pthread.h>
#endif

enum { TEST_MEMORY_SIZE = 65536, TEST_EVENT_CAPACITY = 256, TEST_PROGRAM_CYCLES = 96 };

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
    RUN_TEST(continuation_replays_from_supported_instruction_boundary);
    RUN_TEST(irq_is_accepted_at_the_adjacent_documented_boundary);
    RUN_TEST(two_distinguishable_instances_match_isolated_baselines);
    RUN_TEST(failed_bus_latches_until_reset_and_cannot_be_restored_around);
    return UNITY_END();
}
