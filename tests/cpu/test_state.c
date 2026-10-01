/* SPDX-License-Identifier: MIT */
#include "isolation_fixture.h"
#include "unity.h"
void setUp(void) {}
void tearDown(void) {}
static void complete_state_available(void) {
#ifdef CPU_GUEST_STATE_VERSION
 TEST_ASSERT_EQUAL(1,CPU_GUEST_STATE_VERSION);
#else
 TEST_ASSERT_EQUAL_MESSAGE(1,0,"complete guest record available");
#endif
}
int main(void) {UNITY_BEGIN();RUN_TEST(complete_state_available);return UNITY_END();}
