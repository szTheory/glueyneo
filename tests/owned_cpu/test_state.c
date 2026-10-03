/* SPDX-License-Identifier: MIT */
#include "cpu.h"
#include "unity.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    STATE_MEMORY_SIZE = 0x4000,
    STATE_TRACE_CAPACITY = 512,
    STATE_CONTINUATION_CALLS = 6,
    STATE_CASE_COUNT = 13
};

typedef struct {
    uint32_t address;
    uint16_t value;
    uint8_t write;
    uint8_t success;
} state_bus_event;

typedef struct {
    uint8_t memory[STATE_MEMORY_SIZE];
    owned_cpu *cpu;
    state_bus_event events[STATE_TRACE_CAPACITY];
    size_t event_count;
    size_t live_allocations;
    int fail_read;
    uint32_t fail_read_address;
    const owned_cpu_state *active_probe_state;
    owned_cpu_status active_capture_status;
    owned_cpu_status active_restore_status;
    size_t active_probe_events_before;
    size_t active_probe_events_after;
    unsigned active_probe_count;
} state_machine;

typedef enum {
    CASE_RESET_DEBT = 0,
    CASE_DIAGNOSTIC_MOVEQ,
    CASE_DIAGNOSTIC_ADDQ,
    CASE_DIAGNOSTIC_STORE,
    CASE_STOP,
    CASE_MASKED_IRQ,
    CASE_PENDING_IRQ7,
    CASE_IRQ_ENTRY,
    CASE_TRAP_ENTRY,
    CASE_ILLEGAL_ENTRY,
    CASE_PRIVILEGE_ENTRY,
    CASE_ADDRESS_ERROR_ENTRY,
    CASE_RTE
} state_case;

typedef enum {
    OMIT_NONE = 0,
    OMIT_IRQ7_PENDING
} omission_kind;

void setUp(void) {}
void tearDown(void) {}

static void put_word(state_machine *machine, uint32_t address, uint16_t value) {
    machine->memory[address] = (uint8_t)(value >> 8);
    machine->memory[address + 1u] = (uint8_t)value;
}

static void put_long(state_machine *machine, uint32_t address, uint32_t value) {
    put_word(machine, address, (uint16_t)(value >> 16));
    put_word(machine, address + 2u, (uint16_t)value);
}

static void record_event(state_machine *machine, uint32_t address, uint16_t value,
                         int write, int success) {
    if (machine->event_count < STATE_TRACE_CAPACITY) {
        machine->events[machine->event_count++] = (state_bus_event){
            address, value, (uint8_t)(write != 0), (uint8_t)(success != 0)};
    }
}

static void probe_active_state(state_machine *machine) {
    if (machine->active_probe_state == NULL || machine->active_probe_count != 0u) return;
    owned_cpu_state scratch;
    machine->active_probe_events_before = machine->event_count;
    machine->active_capture_status = owned_cpu_capture_state(machine->cpu, &scratch);
    machine->active_restore_status = owned_cpu_restore_state(
        machine->cpu, machine->active_probe_state);
    machine->active_probe_events_after = machine->event_count;
    machine->active_probe_count++;
}

static int state_read16(void *userdata, uint32_t address, uint16_t *value) {
    state_machine *machine = userdata;
    if (machine == NULL || value == NULL || (address & 1u) != 0u ||
        address >= STATE_MEMORY_SIZE - 1u) return 0;
    probe_active_state(machine);
    if (machine->fail_read != 0 && address == machine->fail_read_address) {
        machine->fail_read = 0;
        record_event(machine, address, 0u, 0, 0);
        return 0;
    }
    *value = (uint16_t)(((uint16_t)machine->memory[address] << 8) |
                        machine->memory[address + 1u]);
    record_event(machine, address, *value, 0, 1);
    return 1;
}

static int state_write16(void *userdata, uint32_t address, uint16_t value) {
    state_machine *machine = userdata;
    if (machine == NULL || (address & 1u) != 0u ||
        address >= STATE_MEMORY_SIZE - 1u) return 0;
    probe_active_state(machine);
    machine->memory[address] = (uint8_t)(value >> 8);
    machine->memory[address + 1u] = (uint8_t)value;
    record_event(machine, address, value, 1, 1);
    return 1;
}

static void *state_allocate(void *userdata, size_t bytes) {
    state_machine *machine = userdata;
    if (machine == NULL) return NULL;
    void *allocation = malloc(bytes);
    if (allocation != NULL) machine->live_allocations++;
    return allocation;
}

static void state_release(void *userdata, void *allocation) {
    state_machine *machine = userdata;
    if (machine == NULL || allocation == NULL) return;
    if (machine->live_allocations != 0u) machine->live_allocations--;
    free(allocation);
}

static void write_vector(state_machine *machine, unsigned vector, uint32_t target) {
    put_long(machine, (uint32_t)vector * UINT32_C(4), target);
}

static void configure_case(state_machine *machine, state_case which) {
    const uint8_t diagnostic[] = {
        0x70u, 0x07u,             /* MOVEQ #7,D0 */
        0x56u, 0x80u,             /* ADDQ.L #3,D0 */
        0x23u, 0xc0u, 0x00u, 0x00u, 0x10u, 0x00u, /* MOVE.L D0,$1000 */
        0x4eu, 0x72u, 0x27u, 0x00u /* STOP #$2700 */
    };
    const uint8_t nops[] = {0x4eu, 0x71u, 0x4eu, 0x71u, 0x4eu, 0x71u,
                            0x4eu, 0x71u, 0x4eu, 0x71u, 0x4eu, 0x71u};
    put_long(machine, 0u, UINT32_C(0x00003000));
    put_long(machine, 4u, UINT32_C(0x00000100));
    write_vector(machine, 3u, UINT32_C(0x00000180));
    write_vector(machine, 4u, UINT32_C(0x00000180));
    write_vector(machine, 8u, UINT32_C(0x00000180));
    write_vector(machine, 31u, UINT32_C(0x00000180));
    write_vector(machine, 32u, UINT32_C(0x00000180));
    memcpy(machine->memory + 0x180u, nops, sizeof(nops));

    switch (which) {
        case CASE_RESET_DEBT:
        case CASE_DIAGNOSTIC_MOVEQ:
        case CASE_DIAGNOSTIC_ADDQ:
        case CASE_DIAGNOSTIC_STORE:
        case CASE_STOP:
            memcpy(machine->memory + 0x100u, diagnostic, sizeof(diagnostic));
            break;
        case CASE_MASKED_IRQ:
        case CASE_PENDING_IRQ7:
        case CASE_IRQ_ENTRY:
            memcpy(machine->memory + 0x100u, nops, sizeof(nops));
            if (which == CASE_PENDING_IRQ7 || which == CASE_IRQ_ENTRY) {
                const uint8_t irq_handler[] = {0x72u, 0x01u, 0x4eu, 0x71u};
                memcpy(machine->memory + 0x180u, irq_handler, sizeof(irq_handler));
            }
            break;
        case CASE_TRAP_ENTRY:
        case CASE_RTE: {
            const uint8_t trap_program[] = {0x4eu, 0x40u, 0x4eu, 0x71u,
                                            0x4eu, 0x71u, 0x4eu, 0x71u,
                                            0x4eu, 0x71u, 0x4eu, 0x71u};
            memcpy(machine->memory + 0x100u, trap_program, sizeof(trap_program));
            if (which == CASE_RTE) {
                const uint8_t rte_handler[] = {0x4eu, 0x73u};
                memcpy(machine->memory + 0x180u, rte_handler, sizeof(rte_handler));
            }
            break;
        }
        case CASE_ILLEGAL_ENTRY: {
            const uint8_t illegal[] = {0x4au, 0xfcu, 0x4eu, 0x71u,
                                       0x4eu, 0x71u, 0x4eu, 0x71u,
                                       0x4eu, 0x71u, 0x4eu, 0x71u};
            memcpy(machine->memory + 0x100u, illegal, sizeof(illegal));
            break;
        }
        case CASE_PRIVILEGE_ENTRY: {
            const uint8_t stop[] = {0x4eu, 0x72u, 0x27u, 0x00u,
                                    0x4eu, 0x71u, 0x4eu, 0x71u};
            memcpy(machine->memory + 0x100u, stop, sizeof(stop));
            break;
        }
        case CASE_ADDRESS_ERROR_ENTRY: {
            const uint8_t odd_word_read[] = {0x30u, 0x39u, 0x00u, 0x00u,
                                             0x01u, 0x01u, 0x4eu, 0x71u,
                                             0x4eu, 0x71u, 0x4eu, 0x71u};
            memcpy(machine->memory + 0x100u, odd_word_read, sizeof(odd_word_read));
            break;
        }
    }
}

static int machine_create_fresh(state_machine *machine) {
    owned_cpu_bus bus = {machine, state_read16, state_write16};
    owned_cpu_allocator allocator = {machine, state_allocate, state_release};
    return owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, allocator,
                            &machine->cpu) == OWNED_CPU_OK;
}

static int machine_create_and_reset(state_machine *machine, state_case which) {
    memset(machine, 0, sizeof(*machine));
    configure_case(machine, which);
    if (!machine_create_fresh(machine)) return 0;
    if (owned_cpu_reset(machine->cpu) != OWNED_CPU_OK) return 0;
    machine->event_count = 0u;
    return 1;
}

static void clear_events(state_machine *machine) {
    machine->event_count = 0u;
}

static owned_cpu_run_result run_one(state_machine *machine) {
    return owned_cpu_run(machine->cpu, UINT64_C(1));
}

static int prepare_checkpoint(state_machine *machine, state_case which) {
    owned_cpu_run_result result;
    if (which == CASE_RESET_DEBT) return 1;
    result = run_one(machine); /* Consume the 40-cycle reset event. */
    if (result.reason != OWNED_CPU_BUDGET || result.elapsed_cycles != 40u) return 0;
    switch (which) {
        case CASE_DIAGNOSTIC_MOVEQ:
            result = run_one(machine);
            return result.reason == OWNED_CPU_BUDGET && result.instructions == 1u;
        case CASE_DIAGNOSTIC_ADDQ:
            result = run_one(machine);
            if (result.reason != OWNED_CPU_BUDGET || result.instructions != 1u) return 0;
            result = run_one(machine);
            return result.reason == OWNED_CPU_BUDGET && result.instructions == 1u;
        case CASE_DIAGNOSTIC_STORE:
            for (unsigned index = 0u; index < 3u; ++index) {
                result = run_one(machine);
                if (result.reason != OWNED_CPU_BUDGET || result.instructions != 1u) return 0;
            }
            return 1;
        case CASE_STOP:
            for (unsigned index = 0u; index < 4u; ++index) result = run_one(machine);
            return result.reason == OWNED_CPU_STOPPED && result.instructions == 1u;
        case CASE_MASKED_IRQ:
            return owned_cpu_set_irq(machine->cpu, 3u) == OWNED_CPU_OK;
        case CASE_PENDING_IRQ7:
            if (owned_cpu_set_irq(machine->cpu, 7u) != OWNED_CPU_OK) return 0;
            return owned_cpu_set_irq(machine->cpu, 0u) == OWNED_CPU_OK;
        case CASE_IRQ_ENTRY:
            if (owned_cpu_set_irq(machine->cpu, 7u) != OWNED_CPU_OK) return 0;
            result = run_one(machine);
            return result.reason == OWNED_CPU_BUDGET && result.elapsed_cycles == 44u;
        case CASE_TRAP_ENTRY:
        case CASE_ILLEGAL_ENTRY:
        case CASE_ADDRESS_ERROR_ENTRY:
            result = run_one(machine);
            return result.reason == OWNED_CPU_BUDGET && result.pc == UINT32_C(0x180);
        case CASE_PRIVILEGE_ENTRY:
            if (owned_cpu_test_seed_execution_state(machine->cpu, 0u,
                                                      UINT32_C(0x2800),
                                                      UINT32_C(0x3000),
                                                      UINT32_C(0x100)) != OWNED_CPU_OK) {
                return 0;
            }
            result = run_one(machine);
            return result.reason == OWNED_CPU_BUDGET && result.pc == UINT32_C(0x180);
        case CASE_RTE:
            result = run_one(machine);
            if (result.reason != OWNED_CPU_BUDGET || result.pc != UINT32_C(0x180)) return 0;
            result = run_one(machine);
            return result.reason == OWNED_CPU_BUDGET && result.pc == UINT32_C(0x102);
        case CASE_RESET_DEBT:
            break;
    }
    return 0;
}

static int observation_equal(const owned_cpu_observation *a,
                             const owned_cpu_observation *b) {
    for (unsigned index = 0u; index < 8u; ++index) {
        if (a->data_registers[index] != b->data_registers[index] ||
            a->address_registers[index] != b->address_registers[index]) return 0;
    }
    return a->pc == b->pc && a->previous_pc == b->previous_pc &&
           a->usp == b->usp && a->ssp == b->ssp && a->sr == b->sr &&
           a->stopped == b->stopped && a->irq_level == b->irq_level &&
           a->irq7_pending == b->irq7_pending && a->reset_pending == b->reset_pending &&
           a->last_exception_vector == b->last_exception_vector &&
           a->instructions == b->instructions &&
           a->instruction_cycles == b->instruction_cycles &&
           a->reset_cycles == b->reset_cycles &&
           a->exception_cycles == b->exception_cycles &&
           a->idle_cycles == b->idle_cycles && a->total_cycles == b->total_cycles &&
           a->reset_signal_events == b->reset_signal_events;
}

static int run_result_equal(const owned_cpu_run_result *a,
                            const owned_cpu_run_result *b) {
    return a->reason == b->reason && a->requested_cycles == b->requested_cycles &&
           a->elapsed_cycles == b->elapsed_cycles &&
           a->overshoot_cycles == b->overshoot_cycles &&
           a->instructions == b->instructions && a->pc == b->pc &&
           a->fault_pc == b->fault_pc &&
           a->instruction_register == b->instruction_register;
}

static int bus_events_equal(const state_machine *a, const state_machine *b) {
    if (a->event_count != b->event_count) return 0;
    for (size_t index = 0u; index < a->event_count; ++index) {
        const state_bus_event *left = &a->events[index];
        const state_bus_event *right = &b->events[index];
        if (left->address != right->address || left->value != right->value ||
            left->write != right->write || left->success != right->success) return 0;
    }
    return 1;
}

static int state_equal(const owned_cpu_state *a, const owned_cpu_state *b) {
    for (unsigned index = 0u; index < 8u; ++index) {
        if (a->data_registers[index] != b->data_registers[index] ||
            a->address_registers[index] != b->address_registers[index]) return 0;
    }
    return a->size == b->size && a->version == b->version &&
           memcmp(a->core_identity, b->core_identity, sizeof(a->core_identity)) == 0 &&
           a->present_fields == b->present_fields &&
           a->pc == b->pc && a->previous_pc == b->previous_pc && a->usp == b->usp &&
           a->ssp == b->ssp && a->fault_pc == b->fault_pc && a->sr == b->sr &&
           a->instruction_register == b->instruction_register &&
           a->stopped == b->stopped && a->irq_level == b->irq_level &&
           a->irq7_pending == b->irq7_pending && a->reset_pending == b->reset_pending &&
           a->last_exception_vector == b->last_exception_vector &&
           a->instructions == b->instructions &&
           a->instruction_cycles == b->instruction_cycles &&
           a->reset_cycles == b->reset_cycles &&
           a->exception_cycles == b->exception_cycles && a->idle_cycles == b->idle_cycles &&
           a->total_cycles == b->total_cycles &&
           a->reset_signal_events == b->reset_signal_events;
}

static int capture_equal(owned_cpu *left_cpu, owned_cpu *right_cpu) {
    owned_cpu_state left;
    owned_cpu_state right;
    return owned_cpu_capture_state(left_cpu, &left) == OWNED_CPU_OK &&
           owned_cpu_capture_state(right_cpu, &right) == OWNED_CPU_OK &&
           state_equal(&left, &right);
}

static void machine_destroy(state_machine *machine) {
    owned_cpu_destroy(machine->cpu);
    machine->cpu = NULL;
}

static uint32_t machine_data_register(state_machine *machine, unsigned index) {
    owned_cpu_observation observation;
    if (owned_cpu_observe(machine->cpu, &observation) != OWNED_CPU_OK) return UINT32_MAX;
    return observation.data_registers[index];
}

static void state_copy_for_test(const owned_cpu_state *source, owned_cpu_state *target);

static void continue_scenario(state_case which, omission_kind omission) {
    state_machine baseline;
    state_machine source;
    state_machine destination;
    owned_cpu_state captured;
    owned_cpu_state baseline_state;
    memset(&destination, 0, sizeof(destination));
    TEST_ASSERT_TRUE_MESSAGE(machine_create_and_reset(&baseline, which), "baseline create/reset");
    TEST_ASSERT_TRUE_MESSAGE(machine_create_and_reset(&source, which), "source create/reset");
    TEST_ASSERT_TRUE_MESSAGE(prepare_checkpoint(&baseline, which), "baseline checkpoint setup");
    TEST_ASSERT_TRUE_MESSAGE(prepare_checkpoint(&source, which), "source checkpoint setup");
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(baseline.cpu, &baseline_state));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(source.cpu, &captured));
    TEST_ASSERT_TRUE_MESSAGE(state_equal(&baseline_state, &captured),
                             "source and uninterrupted baseline reach same named boundary");
    TEST_ASSERT_EQUAL_UINT8(0u, memcmp(baseline.memory, source.memory,
                                       sizeof(baseline.memory)) == 0 ? 0u : 1u);
    TEST_ASSERT_TRUE(bus_events_equal(&baseline, &source));

    TEST_ASSERT_TRUE(machine_create_fresh(&destination));
    memcpy(destination.memory, source.memory, sizeof(destination.memory));
    TEST_ASSERT_EQUAL_UINT(0u, destination.event_count);
    if (omission == OMIT_IRQ7_PENDING) captured.irq7_pending = 0u;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(destination.cpu, &captured));
    TEST_ASSERT_EQUAL_UINT(0u, destination.event_count);
    if (omission == OMIT_NONE) {
        TEST_ASSERT_TRUE_MESSAGE(capture_equal(source.cpu, destination.cpu),
                                 "restore copied every named guest continuation field");
    }

    machine_destroy(&source);
    memset(&source, 0xa5, sizeof(source));
    for (unsigned call = 0u; call < STATE_CONTINUATION_CALLS; ++call) {
        clear_events(&baseline);
        clear_events(&destination);
        owned_cpu_run_result expected = run_one(&baseline);
        owned_cpu_run_result actual = run_one(&destination);
        if (omission == OMIT_NONE) {
            TEST_ASSERT_TRUE_MESSAGE(run_result_equal(&expected, &actual),
                                     "run result, elapsed, overshoot and stop reason continue identically");
        }
        if (omission == OMIT_NONE) {
            owned_cpu_observation expected_observation;
            owned_cpu_observation actual_observation;
            TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                              owned_cpu_observe(baseline.cpu, &expected_observation));
            TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                              owned_cpu_observe(destination.cpu, &actual_observation));
            TEST_ASSERT_TRUE_MESSAGE(observation_equal(&expected_observation,
                                                        &actual_observation),
                                     "all architectural fields match after continuation call");
            TEST_ASSERT_EQUAL_UINT8(0u, memcmp(baseline.memory, destination.memory,
                                               sizeof(baseline.memory)) == 0 ? 0u : 1u);
            TEST_ASSERT_TRUE_MESSAGE(bus_events_equal(&baseline, &destination),
                                     "ordered bus callback trace matches after continuation call");
            TEST_ASSERT_TRUE_MESSAGE(capture_equal(baseline.cpu, destination.cpu),
                                     "all private guest and diagnostic fields match after continuation call");
        }
    }
    if (omission == OMIT_IRQ7_PENDING) {
        TEST_ASSERT_EQUAL_UINT32_MESSAGE(1u, machine_data_register(&baseline, 1u),
                                         "pending IRQ7 baseline handler result");
        TEST_ASSERT_EQUAL_UINT32_MESSAGE(1u, machine_data_register(&destination, 1u),
                                         "state omission pending level7 changed D1");
    }
    machine_destroy(&baseline);
    machine_destroy(&destination);
    TEST_ASSERT_EQUAL_UINT(0u, baseline.live_allocations);
    TEST_ASSERT_EQUAL_UINT(0u, destination.live_allocations);
}

static void every_named_boundary_restores_and_continues_in_a_fresh_owner(void) {
    static const char *const names[STATE_CASE_COUNT] = {
        "reset_debt", "diagnostic_MOVEQ", "diagnostic_ADDQ", "diagnostic_MOVE_store",
        "STOP", "masked_IRQ", "IRQ7_edge_pending_after_deassertion", "IRQ_entry",
        "TRAP_entry", "ILLEGAL_entry", "privilege_entry", "address_error_entry", "RTE"};
    for (unsigned which = 0u; which < STATE_CASE_COUNT; ++which) {
        continue_scenario((state_case)which, OMIT_NONE);
    }
    printf("state_checkpoints=%u continuation_run_calls=%u source_destroyed_and_overwritten=1\n",
           STATE_CASE_COUNT, STATE_CASE_COUNT * STATE_CONTINUATION_CALLS);
    printf("state_boundary_names=%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n",
           names[0], names[1], names[2], names[3], names[4], names[5], names[6], names[7],
           names[8], names[9], names[10], names[11], names[12]);
}

static void mutate_invalid_state(owned_cpu_state *state, unsigned which) {
    switch (which) {
        case 0u: state->size--; break;
        case 1u: state->size++; break;
        case 2u: state->version++; break;
        case 3u: state->core_identity[0] ^= 1; break;
        case 4u: state->present_fields &= ~OWNED_CPU_STATE_FIELD_DATA_REGISTERS; break;
        case 5u: state->stopped = 2u; break;
        case 6u: state->irq_level = 8u; break;
        case 7u: state->irq7_pending = 2u; break;
        case 8u: state->reset_pending = 2u; break;
        case 9u: state->pc |= 1u; break;
        case 10u: state->sr ^= UINT16_C(0x2000); break; /* Active stack bank mismatch. */
        case 11u: state->reset_cycles--; break;
        case 12u: state->total_cycles = UINT64_MAX; break;
        case 13u:
            state->instruction_cycles = UINT64_MAX;
            state->exception_cycles = 1u;
            break;
        case 14u:
            state->reset_pending = 1u;
            state->total_cycles = 1u;
            break;
        default: break;
    }
}

static void expect_rejected_without_mutation(state_machine *destination,
                                            const owned_cpu_state *candidate,
                                            owned_cpu_status expected_status) {
    owned_cpu_state before;
    owned_cpu_state after;
    uint8_t memory_before[STATE_MEMORY_SIZE];
    size_t events_before = destination->event_count;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(destination->cpu, &before));
    memcpy(memory_before, destination->memory, sizeof(memory_before));
    TEST_ASSERT_EQUAL(expected_status,
                      owned_cpu_restore_state(destination->cpu, candidate));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(destination->cpu, &after));
    TEST_ASSERT_TRUE_MESSAGE(state_equal(&before, &after),
                             "rejected restore leaves every named destination field unchanged");
    TEST_ASSERT_EQUAL_UINT8(0u, memcmp(memory_before, destination->memory,
                                      sizeof(memory_before)) == 0 ? 0u : 1u);
    TEST_ASSERT_EQUAL_UINT(events_before, destination->event_count);
}

static void instruction_counter_mismatch_rejects_atomically(void) {
    state_machine source;
    state_machine destination;
    owned_cpu_state valid;
    owned_cpu_state missing_counter;
    memset(&destination, 0, sizeof(destination));
    TEST_ASSERT_TRUE(machine_create_and_reset(&source, CASE_DIAGNOSTIC_MOVEQ));
    TEST_ASSERT_TRUE(prepare_checkpoint(&source, CASE_DIAGNOSTIC_MOVEQ));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(source.cpu, &valid));
    TEST_ASSERT_EQUAL_UINT64(1u, valid.instructions);
    TEST_ASSERT_EQUAL_UINT64(4u, valid.instruction_cycles);

    TEST_ASSERT_TRUE(machine_create_fresh(&destination));
    memcpy(destination.memory, source.memory, sizeof(destination.memory));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(destination.cpu, &valid));
    state_copy_for_test(&valid, &missing_counter);
    missing_counter.instructions = 0u;
    expect_rejected_without_mutation(&destination, &missing_counter,
                                    OWNED_CPU_INVALID_ARGUMENT);

    machine_destroy(&source);
    machine_destroy(&destination);
    TEST_ASSERT_EQUAL_UINT(0u, source.live_allocations);
    TEST_ASSERT_EQUAL_UINT(0u, destination.live_allocations);
    puts("state_instruction_counter_mismatch_rejected=1 atomic_destination_and_bus=1");
}

static void malformed_and_incompatible_records_reject_atomically(void) {
    state_machine source;
    state_machine destination;
    owned_cpu_state valid;
    memset(&destination, 0, sizeof(destination));
    TEST_ASSERT_TRUE(machine_create_and_reset(&source, CASE_RESET_DEBT));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(source.cpu, &valid));
    TEST_ASSERT_TRUE(machine_create_fresh(&destination));
    memcpy(destination.memory, source.memory, sizeof(destination.memory));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_restore_state(destination.cpu, &valid));
    for (unsigned mutation = 0u; mutation < 15u; ++mutation) {
        owned_cpu_state candidate;
        state_copy_for_test(&valid, &candidate);
        mutate_invalid_state(&candidate, mutation);
        expect_rejected_without_mutation(&destination, &candidate, OWNED_CPU_INVALID_ARGUMENT);
    }
    expect_rejected_without_mutation(&destination, NULL, OWNED_CPU_INVALID_ARGUMENT);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_restore_state(NULL, &valid));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_capture_state(destination.cpu, NULL));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, owned_cpu_capture_state(NULL, &valid));

    machine_destroy(&source);
    machine_destroy(&destination);
    TEST_ASSERT_EQUAL_UINT(0u, source.live_allocations);
    TEST_ASSERT_EQUAL_UINT(0u, destination.live_allocations);
    puts("state_invalid_records=15 null_inputs=4 atomic_destination_and_bus=1");
}

static void state_copy_for_test(const owned_cpu_state *source, owned_cpu_state *target) {
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

static void reentrant_capture_and_restore_reject_while_active(void) {
    state_machine machine;
    state_machine source;
    owned_cpu_state state;
    TEST_ASSERT_TRUE(machine_create_and_reset(&machine, CASE_MASKED_IRQ));
    TEST_ASSERT_TRUE(machine_create_and_reset(&source, CASE_RESET_DEBT));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(source.cpu, &state));
    owned_cpu_run_result reset_event = run_one(&machine);
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, reset_event.reason);
    TEST_ASSERT_EQUAL_UINT64(40u, reset_event.elapsed_cycles);
    machine.active_probe_state = &state;
    (void)run_one(&machine);
    TEST_ASSERT_EQUAL_UINT(1u, machine.active_probe_count);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, machine.active_capture_status);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, machine.active_restore_status);
    TEST_ASSERT_EQUAL_UINT(machine.active_probe_events_before,
                           machine.active_probe_events_after);
    machine_destroy(&source);
    machine_destroy(&machine);
    TEST_ASSERT_EQUAL_UINT(0u, source.live_allocations);
    TEST_ASSERT_EQUAL_UINT(0u, machine.live_allocations);
    puts("active_capture_restore_rejected=1 restore_bus_callbacks=0");
}

static void terminal_instance_rejects_restore_without_bus_activity(void) {
    state_machine source;
    state_machine terminal;
    owned_cpu_state state;
    TEST_ASSERT_TRUE(machine_create_and_reset(&source, CASE_RESET_DEBT));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_capture_state(source.cpu, &state));
    TEST_ASSERT_TRUE(machine_create_and_reset(&terminal, CASE_DIAGNOSTIC_MOVEQ));
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, run_one(&terminal).reason);
    terminal.fail_read = 1;
    terminal.fail_read_address = UINT32_C(0x100);
    owned_cpu_run_result failed = run_one(&terminal);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, failed.reason);
    size_t events_after_fault = terminal.event_count;
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT,
                      owned_cpu_restore_state(terminal.cpu, &state));
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, run_one(&terminal).reason);
    TEST_ASSERT_EQUAL_UINT(events_after_fault, terminal.event_count);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT,
                      owned_cpu_capture_state(terminal.cpu, &state));
    machine_destroy(&source);
    machine_destroy(&terminal);
    TEST_ASSERT_EQUAL_UINT(0u, source.live_allocations);
    TEST_ASSERT_EQUAL_UINT(0u, terminal.live_allocations);
    puts("terminal_capture_restore_rejected=1 additional_bus_callbacks=0");
}

static void pending_irq_omission_control(void) {
    continue_scenario(CASE_PENDING_IRQ7, OMIT_IRQ7_PENDING);
}

static void instruction_counter_omission_control(void) {
    instruction_counter_mismatch_rejects_atomically();
}

int main(int argc, char **argv) {
    int controlled = argc == 2 &&
                    (strcmp(argv[1], "--omit-irq7") == 0 ||
                     strcmp(argv[1], "--omit-instruction-counter") == 0 ||
                     strcmp(argv[1], "--continuation-only") == 0);
    UNITY_BEGIN();
    if (argc == 2 && strcmp(argv[1], "--continuation-only") == 0) {
        RUN_TEST(every_named_boundary_restores_and_continues_in_a_fresh_owner);
    } else if (argc == 2 && strcmp(argv[1], "--omit-irq7") == 0) {
        RUN_TEST(pending_irq_omission_control);
    } else if (argc == 2 && strcmp(argv[1], "--omit-instruction-counter") == 0) {
        RUN_TEST(instruction_counter_omission_control);
    } else {
        RUN_TEST(every_named_boundary_restores_and_continues_in_a_fresh_owner);
        RUN_TEST(malformed_and_incompatible_records_reject_atomically);
        RUN_TEST(instruction_counter_mismatch_rejects_atomically);
        RUN_TEST(reentrant_capture_and_restore_reject_while_active);
        RUN_TEST(terminal_instance_rejects_restore_without_bus_activity);
    }
    int failures = UNITY_END();
    if (controlled != 0) puts("Unity denominator: expected=1 observed=1");
    return failures;
}
