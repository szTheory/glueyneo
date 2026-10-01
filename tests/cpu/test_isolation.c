/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "isolation_fixture.h"
#include <stdio.h>
static observation baseline[2][BOUNDARIES];
static int mutate;
void setUp(void) {}
void tearDown(void) {}
static void reset_registers_are_observable(void) {
 machine m;prepare_machine(&m,0);TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&m));
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(m.cpu));cpu_observation o={0};
 cpu_status result=cpu_inspect(m.cpu,&o);cpu_destroy(m.cpu);
 TEST_ASSERT_EQUAL_MESSAGE(CPU_STATUS_OK,result,"instance register observation available");
 TEST_ASSERT_EQUAL_HEX32(0x100,o.pc); TEST_ASSERT_EQUAL_HEX32(0x2000,o.registers[15]);
}
static void distinct_baselines(void) {
 for(unsigned owner=0;owner<2;owner++) {
  machine m;prepare_machine(&m,owner);TEST_ASSERT_TRUE(run_machine(&m,baseline[owner]));
  TEST_ASSERT_EQUAL_UINT32(owner?16:10,baseline[owner][5].cpu.registers[0]);
  TEST_ASSERT_EQUAL_UINT8(owner?16:10,baseline[owner][5].ram[owner?7:3]);
  TEST_ASSERT_EQUAL_UINT32(1,baseline[owner][6].cpu.registers[1]);
  TEST_ASSERT_EQUAL_UINT32(0,baseline[owner][7].cpu.stopped);
  TEST_ASSERT_NOT_EQUAL(0,baseline[owner][8].cpu.stopped);
  printf("instance=%u allocations=%zu bytes=%zu create_ns=%llu boundaries=%u\n",owner,m.allocations,m.bytes,(unsigned long long)m.create_ns,BOUNDARIES);
 }
}
static void owner_comparison(void) {
 TEST_ASSERT_TRUE_MESSAGE(observations_equal(&baseline[0][5],&baseline[mutate?1:0][5]),"boundary ownership comparison");
}
static void interleaved_and_concurrent(void) {
 for(unsigned iteration=0;iteration<64;iteration++) {
  machine m[2];
  for(unsigned k=0;k<2;k++) {prepare_machine(&m[k],k);TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&m[k]));TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(m[k].cpu));}
  for(unsigned step=0;step<BOUNDARIES;step++) for(unsigned turn=0;turn<2;turn++) {
   unsigned k=(turn+iteration+step)%2;observation got;
   TEST_ASSERT_TRUE(boundary(&m[k],step,&got));
   TEST_ASSERT_TRUE_MESSAGE(observations_equal(&got,&baseline[k][step]),"interleaved boundary comparison");
  }
  for(unsigned k=0;k<2;k++) {cpu_destroy(m[k].cpu);TEST_ASSERT_EQUAL(0,m[k].live);}
  start_gate gate={PTHREAD_MUTEX_INITIALIZER,PTHREAD_COND_INITIALIZER,0};
  thread_case c[2];pthread_t threads[2];
  for(unsigned k=0;k<2;k++) {memset(&c[k],0,sizeof(c[k]));prepare_machine(&c[k].m,k);c[k].gate=&gate;TEST_ASSERT_EQUAL(0,pthread_create(&threads[k],NULL,thread_run,&c[k]));}
  for(unsigned k=0;k<2;k++) {TEST_ASSERT_EQUAL(0,pthread_join(threads[k],NULL));TEST_ASSERT_TRUE(c[k].ok);for(unsigned step=0;step<BOUNDARIES;step++) TEST_ASSERT_TRUE_MESSAGE(observations_equal(&c[k].out[step],&baseline[k][step]),"concurrent boundary comparison");}
  pthread_cond_destroy(&gate.cond);pthread_mutex_destroy(&gate.mutex);
 }
 puts("interleavings=64 concurrent_pairs=64 boundaries_per_instance=9 trace_overflows=0");
}
int main(int argc,char **argv) {
 mutate=argc==2 && strcmp(argv[1],"--mutate")==0;
 UNITY_BEGIN();RUN_TEST(reset_registers_are_observable);RUN_TEST(distinct_baselines);RUN_TEST(owner_comparison);
 if(!mutate) RUN_TEST(interleaved_and_concurrent);return UNITY_END();
}
