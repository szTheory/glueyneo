/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "isolation_fixture.h"

#include <stdio.h>
#include <string.h>

void setUp(void) {}
void tearDown(void) {}

static void invalid_arguments_and_allocation_failure_are_contained(void) {
    iso_machine machine;
    memset(&machine, 0, sizeof(machine));
    owned_cpu_bus bus = {&machine, iso_read16, iso_write16};
    owned_cpu_allocator allocator = {&machine, iso_allocate, iso_release};
    owned_cpu *cpu = (owned_cpu *)(uintptr_t)1u;
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, allocator, NULL));
    TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_MODEL,
                      owned_cpu_create(UINT32_C(68020), bus, allocator, &cpu));
    TEST_ASSERT_NULL(cpu);
    owned_cpu_bus bad_bus = bus;
    bad_bus.read16 = NULL;
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_create(OWNED_CPU_MODEL_MC68000, bad_bus, allocator, &cpu));
    TEST_ASSERT_NULL(cpu);
    owned_cpu_allocator bad_allocator = allocator;
    bad_allocator.release = NULL;
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, bad_allocator, &cpu));
    TEST_ASSERT_NULL(cpu);
    TEST_ASSERT_EQUAL_UINT(0u, machine.allocation_attempts);

    TEST_ASSERT_FALSE(iso_machine_create_with_failure(&machine, 0u, 1u));
    TEST_ASSERT_NULL(machine.cpu);
    TEST_ASSERT_EQUAL_UINT(1u, machine.allocation_attempts);
    TEST_ASSERT_EQUAL_UINT(0u, machine.live_allocations);
    TEST_ASSERT_EQUAL_UINT(0u, machine.live_bytes);
    owned_cpu_destroy(NULL);

    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, owned_cpu_reset(NULL));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, owned_cpu_set_irq(NULL, 0u));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, owned_cpu_observe(NULL, NULL));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_run(NULL, 1u).reason);
    TEST_ASSERT_FALSE(iso_read16(&machine, 0u, NULL));
    TEST_ASSERT_FALSE(iso_write16(&machine, 1u, 0u));

    iso_machine lifecycle;
    TEST_ASSERT_TRUE(iso_machine_create(&lifecycle, 0u));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_run(lifecycle.cpu, 1u).reason);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_set_irq(lifecycle.cpu, 1u));
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_observe(lifecycle.cpu, &observation));
    TEST_ASSERT_TRUE(iso_machine_reset(&lifecycle));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_observe(lifecycle.cpu, NULL));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_set_irq(lifecycle.cpu, 8u));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT,
                      owned_cpu_run(lifecycle.cpu,
                                    OWNED_CPU_MAX_CYCLE_BUDGET + UINT64_C(1)).reason);
    iso_machine_destroy(&lifecycle);
    TEST_ASSERT_EQUAL_UINT(0u, lifecycle.live_allocations);
    puts("create_rejections=4 null_api_rejections=4 allocation_sites=1 failed_allocations=1 leaked_bytes=0");
}

static void reentry_is_rejected_and_destroy_during_callback_preserves_owner(void) {
    iso_machine machine;
    TEST_ASSERT_TRUE(iso_machine_create(&machine, 0u));
    machine.reentry_probe = 1;
    TEST_ASSERT_TRUE(iso_machine_reset(&machine));
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, machine.reentry_run);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, machine.reentry_reset);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, machine.reentry_observe);
    TEST_ASSERT_EQUAL(OWNED_CPU_INVALID_ARGUMENT, machine.reentry_irq);
    TEST_ASSERT_EQUAL_UINT(1u, machine.reentry_live_allocations);
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(machine.cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(0x100u, observation.pc);
    iso_machine_destroy(&machine);
    TEST_ASSERT_EQUAL_UINT(0u, machine.live_allocations);
    TEST_ASSERT_EQUAL_UINT(0u, machine.live_bytes);
    puts("same_instance_callback_reentry=rejected destroy_reentry=no_op clean_destroy=1");
}

static void reset_host_fault_is_terminal_and_reset_recovers(void) {
    iso_machine machine;
    TEST_ASSERT_TRUE(iso_machine_create(&machine, 0u));
    machine.fail_read = 1;
    machine.fail_read_address = 0u;
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, owned_cpu_reset(machine.cpu));
    size_t events = machine.event_count;
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, owned_cpu_run(machine.cpu, 1u).reason);
    TEST_ASSERT_EQUAL_UINT(events, machine.event_count);
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, owned_cpu_set_irq(machine.cpu, 1u));
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT,
                      owned_cpu_observe(machine.cpu, &observation));
    TEST_ASSERT_TRUE(iso_machine_reset(&machine));
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(machine.cpu, &observation));
    TEST_ASSERT_EQUAL_HEX32(0x100u, observation.pc);
    iso_machine_destroy(&machine);
    TEST_ASSERT_EQUAL_UINT(0u, machine.live_allocations);
    puts("reset_vector_fault=terminal reset_recovery=pass callbacks_after_fault=0");
}

static void install_trap(iso_machine *machine) {
    machine->rom[0x100] = 0x4e;
    machine->rom[0x101] = 0x40;
}

static void host_fault_case(unsigned kind) {
    iso_machine machine;
    TEST_ASSERT_TRUE(iso_machine_create(&machine, 0u));
    TEST_ASSERT_TRUE(iso_machine_reset(&machine));
    /* Drain reset work before installing each execution-boundary failpoint. */
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, owned_cpu_run(machine.cpu, 1u).reason);

    if (kind == 0u) {
        machine.fail_read = 1;
        machine.fail_read_address = 0x100u;
    } else if (kind == 1u) {
        machine.rom[0x100] = 0x30;
        machine.rom[0x101] = 0x39;
        machine.rom[0x102] = 0x00;
        machine.rom[0x103] = 0x00;
        machine.rom[0x104] = 0x02;
        machine.rom[0x105] = 0x00;
        machine.fail_read = 1;
        machine.fail_read_address = 0x200u;
    } else if (kind == 2u || kind == 3u) {
        TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, owned_cpu_run(machine.cpu, 1u).reason);
        TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, owned_cpu_run(machine.cpu, 1u).reason);
        TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                          owned_cpu_test_seed_data_register(machine.cpu, 0u,
                                                            UINT32_C(0x12345678)));
        machine.fail_write = 1;
        machine.fail_write_address = kind == 2u ? 0x1000u : 0x1002u;
    } else if (kind == 4u) {
        install_trap(&machine);
        machine.fail_write = 1;
        machine.fail_write_address = 0x1ffcu;
    } else if (kind == 5u) {
        install_trap(&machine);
        machine.fail_read = 1;
        machine.fail_read_address = 128u;
    } else if (kind == 6u) {
        install_trap(&machine);
        TEST_ASSERT_EQUAL(OWNED_CPU_OK,
                          owned_cpu_test_seed_execution_state(machine.cpu,
                                                              0x2700u, 0u,
                                                              0x2001u, 0x100u));
    }

    owned_cpu_run_result result = owned_cpu_run(machine.cpu, 1u);
    TEST_ASSERT_EQUAL_MESSAGE(OWNED_CPU_HOST_FAULT, result.reason,
                              "bounded callback or exception-stack fault");
    if (kind == 2u) {
        TEST_ASSERT_EQUAL_HEX8(0u, machine.ram[0]);
        TEST_ASSERT_EQUAL_HEX8(0u, machine.ram[1]);
    }
    if (kind == 3u) {
        TEST_ASSERT_EQUAL_HEX8(0x12u, machine.ram[0]);
        TEST_ASSERT_EQUAL_HEX8(0x34u, machine.ram[1]);
        TEST_ASSERT_EQUAL_HEX8(0u, machine.ram[2]);
        TEST_ASSERT_EQUAL_HEX8(0u, machine.ram[3]);
    }
    size_t events_after_fault = machine.event_count;
    TEST_ASSERT_EQUAL(OWNED_CPU_HOST_FAULT, owned_cpu_run(machine.cpu, 4u).reason);
    TEST_ASSERT_EQUAL_UINT(events_after_fault, machine.event_count);
    owned_cpu_destroy(machine.cpu);
    machine.cpu = NULL;
    TEST_ASSERT_EQUAL_UINT(0u, machine.live_allocations);
}

static void bounded_fetch_store_stack_and_vector_faults_are_terminal(void) {
    enum { CALLBACK_FAULT_CASES = 7 };
    for (unsigned kind = 0u; kind < CALLBACK_FAULT_CASES; ++kind) {
        host_fault_case(kind);
    }
    puts("host_fault_cases=7 reset_recovery_case=1 partial_long_write_preserved=1");
}

static void stopped_cpu_wakes_on_a_level_seven_edge(void) {
    iso_machine machine;
    TEST_ASSERT_TRUE(iso_machine_create(&machine, 0u));
    machine.rom[124] = 0x00;
    machine.rom[125] = 0x00;
    machine.rom[126] = 0x01;
    machine.rom[127] = 0x80;
    TEST_ASSERT_TRUE(iso_machine_reset(&machine));
    for (unsigned boundary = 1u; boundary < ISO_BOUNDARIES; ++boundary) {
        (void)owned_cpu_run(machine.cpu, 1u);
    }
    owned_cpu_observation observation;
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(machine.cpu, &observation));
    TEST_ASSERT_EQUAL_UINT8(1u, observation.stopped);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_set_irq(machine.cpu, 7u));
    owned_cpu_run_result result = owned_cpu_run(machine.cpu, 1u);
    TEST_ASSERT_EQUAL(OWNED_CPU_BUDGET, result.reason);
    TEST_ASSERT_EQUAL_UINT64(44u, result.elapsed_cycles);
    TEST_ASSERT_EQUAL(OWNED_CPU_OK, owned_cpu_observe(machine.cpu, &observation));
    TEST_ASSERT_EQUAL_UINT8(0u, observation.stopped);
    TEST_ASSERT_EQUAL_UINT8(31u, observation.last_exception_vector);
    TEST_ASSERT_EQUAL_HEX32(0x180u, observation.pc);
    iso_machine_destroy(&machine);
    TEST_ASSERT_EQUAL_UINT(0u, machine.live_allocations);
    puts("stopped_pending_irq7_edge=wakes vector=31 clocks=44");
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(invalid_arguments_and_allocation_failure_are_contained);
    RUN_TEST(reentry_is_rejected_and_destroy_during_callback_preserves_owner);
    RUN_TEST(reset_host_fault_is_terminal_and_reset_recovers);
    RUN_TEST(bounded_fetch_store_stack_and_vector_faults_are_terminal);
    RUN_TEST(stopped_cpu_wakes_on_a_level_seven_edge);
    return UNITY_END();
}
