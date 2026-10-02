/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "isolation_fixture.h"

#include <stdio.h>
#include <string.h>

static iso_snapshot baselines[2][ISO_BOUNDARIES];
static int swapped_owner_control;

void setUp(void) {}
void tearDown(void) {}

static void build_isolated_baselines(void) {
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        iso_machine machine;
        TEST_ASSERT_TRUE(iso_machine_create(&machine, owner));
        TEST_ASSERT_TRUE(iso_run_all(&machine, baselines[owner]));
        TEST_ASSERT_EQUAL_UINT32(owner == 0u ? 10u : 16u,
                                 baselines[owner][ISO_BOUNDARIES - 1u].cpu.data_registers[0]);
        size_t offset = owner == 0u ? 0u : 4u;
        TEST_ASSERT_EQUAL_HEX8(owner == 0u ? 10u : 16u,
                               baselines[owner][ISO_BOUNDARIES - 1u].ram[offset + 3u]);
        TEST_ASSERT_EQUAL_UINT8(owner + 1u,
                                baselines[owner][ISO_BOUNDARIES - 1u].cpu.irq_level);
        iso_machine_destroy(&machine);
        TEST_ASSERT_EQUAL_UINT(0u, machine.live_allocations);
        TEST_ASSERT_EQUAL_UINT(0u, machine.live_bytes);
    }
    TEST_ASSERT_FALSE(iso_snapshots_equal(&baselines[0][ISO_BOUNDARIES - 1u],
                                          &baselines[1][ISO_BOUNDARIES - 1u]));
    puts("isolated_baselines=2 boundaries_per_instance=6 guest_owners=2");
}

static void owner_boundary_comparison(void) {
    unsigned selected = swapped_owner_control != 0 ? 1u : 0u;
    const iso_snapshot *expected = &baselines[0][ISO_BOUNDARIES - 1u];
    const iso_snapshot *actual = &baselines[selected][ISO_BOUNDARIES - 1u];
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(expected->cpu.data_registers[0],
                                     actual->cpu.data_registers[0],
                                     "swapped-owner guest D0");
    TEST_ASSERT_TRUE_MESSAGE(iso_snapshots_equal(expected, actual),
                             "swapped-owner complete boundary");
}

static void interleaved_instances_match_every_named_boundary(void) {
    enum { INTERLEAVED_PAIRS = 32 };
    for (unsigned iteration = 0u; iteration < INTERLEAVED_PAIRS; ++iteration) {
        iso_machine machines[2];
        for (unsigned owner = 0u; owner < 2u; ++owner) {
            TEST_ASSERT_TRUE(iso_machine_create(&machines[owner], owner));
            TEST_ASSERT_TRUE(iso_machine_reset(&machines[owner]));
        }
        for (unsigned boundary = 0u; boundary < ISO_BOUNDARIES; ++boundary) {
            for (unsigned turn = 0u; turn < 2u; ++turn) {
                unsigned owner = (turn + boundary + iteration) & 1u;
                iso_snapshot actual;
                TEST_ASSERT_TRUE(iso_boundary(&machines[owner], boundary, &actual));
                TEST_ASSERT_TRUE_MESSAGE(
                    iso_snapshots_equal(&actual, &baselines[owner][boundary]),
                    "interleaved complete observation, RAM and ordered bus trace");
            }
        }
        for (unsigned owner = 0u; owner < 2u; ++owner) {
            iso_machine_destroy(&machines[owner]);
            TEST_ASSERT_EQUAL_UINT(0u, machines[owner].live_allocations);
            TEST_ASSERT_EQUAL_UINT(0u, machines[owner].live_bytes);
        }
    }
    printf("interleaved_pairs=%u boundaries_per_instance=%u bus_trace_overflows=0\n",
           INTERLEAVED_PAIRS, ISO_BOUNDARIES);
}

static void concurrent_cold_instances_match_every_named_boundary(void) {
    enum { CONCURRENT_PAIRS = 32 };
    for (unsigned iteration = 0u; iteration < CONCURRENT_PAIRS; ++iteration) {
        iso_snapshot concurrent[2][ISO_BOUNDARIES];
        TEST_ASSERT_TRUE(iso_run_cold_pair(concurrent));
        for (unsigned owner = 0u; owner < 2u; ++owner) {
            for (unsigned boundary = 0u; boundary < ISO_BOUNDARIES; ++boundary) {
                TEST_ASSERT_TRUE_MESSAGE(
                    iso_snapshots_equal(&concurrent[owner][boundary],
                                        &baselines[owner][boundary]),
                    "concurrent complete observation, RAM and ordered bus trace");
            }
        }
    }
    printf("concurrent_pairs=%u boundaries_per_instance=%u cold_first_use=1\n",
           CONCURRENT_PAIRS, ISO_BOUNDARIES);
}

int main(int argc, char **argv) {
    swapped_owner_control = argc == 2 && strcmp(argv[1], "--swapped-owner") == 0;
    UNITY_BEGIN();
    RUN_TEST(build_isolated_baselines);
    RUN_TEST(owner_boundary_comparison);
    if (swapped_owner_control == 0) {
        RUN_TEST(interleaved_instances_match_every_named_boundary);
        RUN_TEST(concurrent_cold_instances_match_every_named_boundary);
    }
    return UNITY_END();
}
