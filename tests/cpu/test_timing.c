/* SPDX-License-Identifier: MIT */
#include "isolation_fixture.h"
#include "unity.h"
void setUp(void) {}
void tearDown(void) {}
static void request_rejected(void) {
 machine m;prepare_machine(&m,0);TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&m));
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(m.cpu));
 cpu_run_result r=cpu_run(m.cpu,UINT64_MAX);
 cpu_destroy(m.cpu);
 TEST_ASSERT_EQUAL_MESSAGE(CPU_STATUS_INVALID_ARGUMENT,r.reason,"out-of-range request must reject");
}
int main(void) {UNITY_BEGIN();RUN_TEST(request_rejected);return UNITY_END();}
