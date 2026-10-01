/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "isolation_fixture.h"
#include <stdio.h>
void setUp(void) {}
void tearDown(void) {}
static observation baseline[BOUNDARIES];
static void terminal_fault_rejects_inspection(void) {
 machine m;prepare_machine(&m,0);TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&m));
 m.fail_address=4;m.fail_read=1;TEST_ASSERT_EQUAL(CPU_STATUS_HOST_FAULT,cpu_reset(m.cpu));
 cpu_observation o;cpu_status result=cpu_inspect(m.cpu,&o);cpu_destroy(m.cpu);
 TEST_ASSERT_EQUAL_MESSAGE(CPU_STATUS_HOST_FAULT,result,"terminal instance permits reset or destruction only");
}
static void allocations_and_witness(void) {
 machine success;prepare_machine(&success,0);TEST_ASSERT_TRUE(run_machine(&success,baseline));
 for(size_t fail=1;fail<=success.allocations;fail++) {
  machine m,w;prepare_machine(&m,1);prepare_machine(&w,0);m.fail_at=fail;
  TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&w));TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(w.cpu));
  TEST_ASSERT_EQUAL(CPU_STATUS_ALLOCATION_FAILURE,create_machine(&m));TEST_ASSERT_NULL(m.cpu);TEST_ASSERT_EQUAL(0,m.live);cpu_destroy(m.cpu);cpu_destroy(NULL);
  for(unsigned step=0;step<BOUNDARIES;step++) {observation got;TEST_ASSERT_TRUE(boundary(&w,step,&got));TEST_ASSERT_TRUE(observations_equal(&got,&baseline[step]));}
  cpu_destroy(w.cpu);TEST_ASSERT_EQUAL(0,w.live);
 }
 printf("construction_allocations=%zu failed_positions=%zu leaked_allocations=0\n",success.allocations,success.allocations);
}
static void faults_preserve_witness(void) {
 for(unsigned kind=0;kind<7;kind++) {
  machine m,w;prepare_machine(&m,1);prepare_machine(&w,0);
  TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&m));TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&w));
  TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(w.cpu));
  /* Reset, fetch, store, IRQ stack, exception stack, nested address error,
     and internally detected odd IRQ stack (not a failing bus callback). */
  if(kind==0) {m.fail_address=4;m.fail_read=1;}
  if(kind==1) {m.rom[6]=0x30;m.rom[7]=0;}
  if(kind==2) {m.fail_address=0x1004;m.fail_write=1;}
  if(kind==3 || kind==4 || kind==5) {m.fail_address=0x1ffc;m.fail_write=1;}
  if(kind==4) {m.rom[0x100]=0x4a;m.rom[0x101]=0xfc;}
  if(kind==5) {m.rom[7]=1;}
  if(kind==6) m.rom[3]=1; /* odd SSP 0x2001 */
  cpu_status status=cpu_reset(m.cpu);
  if(kind) {
   TEST_ASSERT_EQUAL(CPU_STATUS_OK,status);(void)cpu_run(m.cpu,1); /* consume reset debt */
   if(kind==3 || kind==6) TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_set_irq(m.cpu,7));
   status=cpu_run(m.cpu,200).reason;
  }
  TEST_ASSERT_EQUAL_MESSAGE(CPU_STATUS_HOST_FAULT,status,"bounded terminal guest fault");
  TEST_ASSERT_EQUAL(CPU_STATUS_HOST_FAULT,cpu_run(m.cpu,1).reason);
  TEST_ASSERT_EQUAL(CPU_STATUS_HOST_FAULT,cpu_set_irq(m.cpu,1));
  cpu_destroy(m.cpu);TEST_ASSERT_EQUAL(0,m.live);
  for(unsigned step=0;step<BOUNDARIES;step++) {observation got;TEST_ASSERT_TRUE(boundary(&w,step,&got));TEST_ASSERT_TRUE_MESSAGE(observations_equal(&got,&baseline[step]),"fault witness boundary");}
  cpu_destroy(w.cpu);TEST_ASSERT_EQUAL(0,w.live);
 }
 puts("fault_cases=7 healthy_witnesses=7 terminal_reuse_rejected=7");
}
static void invalid_requests(void) {
 machine m;prepare_machine(&m,0);cpu_bus b={&m,trace_read,trace_write};cpu_allocator a={&m,count_allocate,count_release};
 TEST_ASSERT_EQUAL(CPU_STATUS_UNSUPPORTED_MODEL,cpu_create(68020,b,a,&m.cpu));TEST_ASSERT_NULL(m.cpu);
 b.read=NULL;TEST_ASSERT_EQUAL(CPU_STATUS_INVALID_ARGUMENT,cpu_create(68000,b,a,&m.cpu));TEST_ASSERT_NULL(m.cpu);
 b.read=trace_read;a.allocate=NULL;TEST_ASSERT_EQUAL(CPU_STATUS_INVALID_ARGUMENT,cpu_create(68000,b,a,&m.cpu));
 TEST_ASSERT_EQUAL(CPU_STATUS_INVALID_ARGUMENT,cpu_create(68000,b,a,NULL));TEST_ASSERT_EQUAL(0,m.allocations);
 TEST_ASSERT_EQUAL(CPU_STATUS_INVALID_ARGUMENT,cpu_reset(NULL));cpu_destroy(NULL);
}
int main(int argc,char **argv) {
 UNITY_BEGIN();RUN_TEST(terminal_fault_rejects_inspection);
 if(argc==1) {RUN_TEST(allocations_and_witness);RUN_TEST(faults_preserve_witness);RUN_TEST(invalid_requests);}
 (void)argv;return UNITY_END();
}
