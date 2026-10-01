/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "isolation_fixture.h"
#include <stdio.h>
void setUp(void) {}
void tearDown(void) {}
static void cold_concurrent_lifecycle(void) {
 start_gate gate={PTHREAD_MUTEX_INITIALIZER,PTHREAD_COND_INITIALIZER,0};
 thread_case c[2];pthread_t threads[2];
 /* No backend has been created before both worker threads cross this gate. */
 for(unsigned k=0;k<2;k++) {memset(&c[k],0,sizeof(c[k]));prepare_machine(&c[k].m,k);c[k].gate=&gate;TEST_ASSERT_EQUAL(0,pthread_create(&threads[k],NULL,thread_run,&c[k]));}
 for(unsigned k=0;k<2;k++) TEST_ASSERT_EQUAL(0,pthread_join(threads[k],NULL));
 for(unsigned k=0;k<2;k++) {
  TEST_ASSERT_TRUE(c[k].ok);machine m;observation isolated[BOUNDARIES];prepare_machine(&m,k);
  TEST_ASSERT_TRUE(run_machine(&m,isolated));
  for(unsigned step=0;step<BOUNDARIES;step++) TEST_ASSERT_TRUE_MESSAGE(observations_equal(&c[k].out[step],&isolated[step]),"cold boundary comparison");
  printf("cold_instance=%u allocations=%zu bytes=%zu create_ns=%llu\n",k,c[k].m.allocations,c[k].m.bytes,(unsigned long long)c[k].m.create_ns);
 }
 pthread_cond_destroy(&gate.cond);pthread_mutex_destroy(&gate.mutex);
 puts("cold_process_cases=1 barrier_started_instances=2 boundaries_per_instance=9");
}
int main(void) {UNITY_BEGIN();RUN_TEST(cold_concurrent_lifecycle);return UNITY_END();}
