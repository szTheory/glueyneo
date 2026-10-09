/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "isolation_fixture.h"

#include <stdio.h>
#include <string.h>

void setUp(void) {}
void tearDown(void) {}

static void concurrently_create_run_and_destroy_two_fresh_instances(void) {
    iso_snapshot output[2][ISO_BOUNDARIES];
    TEST_ASSERT_TRUE(iso_run_cold_pair(output));
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        const iso_snapshot *final = &output[owner][ISO_BOUNDARIES - 1u];
        TEST_ASSERT_EQUAL_UINT32(owner == 0u ? 10u : 16u,
                                 final->cpu.data_registers[0]);
        TEST_ASSERT_EQUAL_HEX32(0x10eu, final->cpu.pc);
        TEST_ASSERT_EQUAL_UINT64(100u, final->cpu.total_cycles);
        TEST_ASSERT_EQUAL_UINT64(4u, final->cpu.instructions);
        TEST_ASSERT_EQUAL_UINT8(owner + 1u, final->cpu.irq_level);
        size_t offset = owner == 0u ? 0u : 4u;
        TEST_ASSERT_EQUAL_HEX8(owner == 0u ? 10u : 16u, final->ram[offset + 3u]);
    }
    puts("barrier_started_instances=2 construction_pairs=1 boundaries_per_instance=6");
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    UNITY_BEGIN();
    RUN_TEST(concurrently_create_run_and_destroy_two_fresh_instances);
    return UNITY_END();
}
