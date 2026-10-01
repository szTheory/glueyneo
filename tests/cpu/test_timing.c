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
static void reset_debit(void) {
 machine m;prepare_machine(&m,0);TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&m));
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(m.cpu));
 cpu_run_result r=cpu_run(m.cpu,41);cpu_destroy(m.cpu);
 TEST_ASSERT_EQUAL_MESSAGE(44,r.elapsed,"reset40 plus MOVEQ4");
}
static void reset_clears_pending_nmi(void) {
 machine m;prepare_machine(&m,0);TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&m));
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(m.cpu));cpu_set_irq(m.cpu,7);
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(m.cpu));cpu_observation o;
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_inspect(m.cpu,&o));cpu_destroy(m.cpu);
 TEST_ASSERT_EQUAL_MESSAGE(0,o.nmi,"reset clears stale NMI edge");
}
static void word(machine *m,unsigned a,uint16_t v) {m->rom[a]=(uint8_t)(v>>8);m->rom[a+1]=(uint8_t)v;}
static uint32_t ram_value(machine *m,unsigned a,unsigned n) {
 uint32_t v=0;for(unsigned i=0;i<n;i++) v=(v<<8)|m->ram[a-0x1000+i];return v;
}
static void begin(machine *m) {TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(m));TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(m->cpu));}
static cpu_observation inspect(machine *m) {cpu_observation o;TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_inspect(m->cpu,&o));return o;}
static void budgets_and_partitions(void) {
 const int64_t requests[]={0,1,39,40,41,43,44,45};
 const uint64_t elapsed[]={0,40,40,40,44,44,44,52};
 for(unsigned i=0;i<8;i++) {
  machine m;prepare_machine(&m,0);begin(&m);cpu_run_result r=cpu_run(m.cpu,requests[i]);
  TEST_ASSERT_EQUAL_UINT64(elapsed[i],r.elapsed);TEST_ASSERT_EQUAL_UINT64(elapsed[i]>requests[i]?elapsed[i]-requests[i]:0,r.overshoot);
  TEST_ASSERT_EQUAL_UINT64(i<4?0:i<7?1:2,r.instructions);cpu_destroy(m.cpu);
 }
 machine a,b;prepare_machine(&a,0);prepare_machine(&b,0);begin(&a);begin(&b);
 cpu_run_result x=cpu_run(a.cpu,52),y=cpu_run(b.cpu,40),z=cpu_run(b.cpu,12);
 cpu_observation oa=inspect(&a),ob=inspect(&b);TEST_ASSERT_EQUAL_MEMORY(&oa,&ob,sizeof(oa));
 TEST_ASSERT_EQUAL_UINT64(x.elapsed,y.elapsed+z.elapsed);TEST_ASSERT_EQUAL_UINT64(x.instructions,y.instructions+z.instructions);
 cpu_run(a.cpu,100);oa=inspect(&a);size_t accesses=a.count;
 const int64_t invalid[]={-1,CPU_MAX_CYCLE_REQUEST+1,INT64_MAX,INT64_MIN};
 for(unsigned i=0;i<4;i++) {x=cpu_run(a.cpu,invalid[i]);TEST_ASSERT_EQUAL(CPU_STATUS_INVALID_ARGUMENT,x.reason);}
 ob=inspect(&a);TEST_ASSERT_EQUAL_MEMORY(&oa,&ob,sizeof(oa));TEST_ASSERT_EQUAL(accesses,a.count);
 x=cpu_run(a.cpu,CPU_MAX_CYCLE_REQUEST);TEST_ASSERT_EQUAL(CPU_STATUS_STOPPED,x.reason);
 TEST_ASSERT_EQUAL_UINT64(CPU_MAX_CYCLE_REQUEST,x.elapsed);TEST_ASSERT_EQUAL_UINT64(0,x.instructions);
 TEST_ASSERT_EQUAL_UINT64(0,x.overshoot);cpu_destroy(a.cpu);cpu_destroy(b.cpu);
}
static void instruction_budgets(void) {
 const unsigned q[]={1,3,4,5};const unsigned e[]={4,4,4,12};
 for(unsigned i=0;i<4;i++) {machine m;prepare_machine(&m,0);begin(&m);cpu_run(m.cpu,40);
  cpu_run_result r=cpu_run(m.cpu,q[i]);TEST_ASSERT_EQUAL(e[i],r.elapsed);TEST_ASSERT_EQUAL(i==3?2:1,r.instructions);cpu_destroy(m.cpu);}
 machine m;prepare_machine(&m,0);word(&m,0x100,0x4e70);begin(&m);cpu_run(m.cpu,40);
 cpu_run_result r=cpu_run(m.cpu,1);TEST_ASSERT_EQUAL(132,r.elapsed);TEST_ASSERT_EQUAL(1,r.instructions);
 TEST_ASSERT_EQUAL_HEX32(0x102,inspect(&m).pc);cpu_destroy(m.cpu);
}
static void exceptions(void) {
 /* TRAP #0, ILLEGAL, user-mode STOP: vectors32,4,8. Handler ADDQ/RTE. */
 const unsigned op[]={0x4e40,0x4afc,0x4e72},vec[]={32,4,8};
 for(unsigned i=0;i<3;i++) {
  machine m;prepare_machine(&m,0);word(&m,vec[i]*4+2,0x180);
  unsigned address=0x100;
  if(i==2) {word(&m,address,0x46fc);word(&m,address+2,0);address+=4;}
  word(&m,address,op[i]);word(&m,address+2,0x2700);begin(&m);cpu_run(m.cpu,40);
  if(i==2) {cpu_run_result r=cpu_run(m.cpu,1);TEST_ASSERT_EQUAL(16,r.elapsed);}
  uint32_t saved_sr=inspect(&m).sr;
  cpu_run_result r=cpu_run(m.cpu,1);cpu_observation o=inspect(&m);
  TEST_ASSERT_EQUAL(34,r.elapsed);TEST_ASSERT_EQUAL(1,r.instructions);
  TEST_ASSERT_EQUAL_HEX32(0x180,o.pc);TEST_ASSERT_EQUAL_HEX32(0x1ffa,o.registers[15]);
  TEST_ASSERT_EQUAL_HEX32(saved_sr,ram_value(&m,0x1ffa,2));
  TEST_ASSERT_EQUAL_HEX32(i==0?address+2:address,ram_value(&m,0x1ffc,4));
  r=cpu_run(m.cpu,1);TEST_ASSERT_EQUAL(8,r.elapsed);TEST_ASSERT_EQUAL(1,inspect(&m).registers[1]);
  r=cpu_run(m.cpu,1);TEST_ASSERT_EQUAL(20,r.elapsed);o=inspect(&m);
  TEST_ASSERT_EQUAL_HEX32(i==0?address+2:address,o.pc);TEST_ASSERT_EQUAL_HEX32(saved_sr,o.sr);
  cpu_destroy(m.cpu);
 }
}
static void irq_and_stop(void) {
 machine m;prepare_machine(&m,0);word(&m,27*4+2,0x180);
 word(&m,0x100,0x4e71);word(&m,0x102,0x46fc);word(&m,0x104,0x2000);
 word(&m,0x106,0x4e72);word(&m,0x108,0x2000);begin(&m);cpu_run(m.cpu,40);
 cpu_set_irq(m.cpu,3);cpu_run_result r=cpu_run(m.cpu,1);
 TEST_ASSERT_EQUAL(4,r.elapsed);TEST_ASSERT_EQUAL(0,inspect(&m).registers[1]);
 r=cpu_run(m.cpu,1);TEST_ASSERT_EQUAL(60,r.elapsed); /* MOVE SR16 + entry44 */
 cpu_observation o=inspect(&m);TEST_ASSERT_EQUAL_HEX32(0x180,o.pc);
 TEST_ASSERT_EQUAL_HEX32(0x106,ram_value(&m,0x1ffc,4));TEST_ASSERT_EQUAL_HEX32(0x2000,ram_value(&m,0x1ffa,2));
 cpu_set_irq(m.cpu,0);cpu_run(m.cpu,1);r=cpu_run(m.cpu,1);TEST_ASSERT_EQUAL(20,r.elapsed);
 r=cpu_run(m.cpu,1);TEST_ASSERT_EQUAL(CPU_STATUS_STOPPED,r.reason);TEST_ASSERT_EQUAL(4,r.elapsed);
 r=cpu_run(m.cpu,11);TEST_ASSERT_EQUAL(11,r.elapsed);TEST_ASSERT_EQUAL(0,r.instructions);
 cpu_set_irq(m.cpu,3);r=cpu_run(m.cpu,1);TEST_ASSERT_EQUAL(52,r.elapsed);TEST_ASSERT_EQUAL(1,r.instructions);
 TEST_ASSERT_EQUAL(2,inspect(&m).registers[1]);cpu_set_irq(m.cpu,0);cpu_run(m.cpu,1);
 TEST_ASSERT_EQUAL_HEX32(0x10a,inspect(&m).pc);cpu_destroy(m.cpu);
}
static void address_error(void) {
 machine m;prepare_machine(&m,0);word(&m,14,0x180);
 /* MOVE.W ($1001).L,D0: odd data read, valid exception stack/vector. */
 word(&m,0x100,0x3039);word(&m,0x102,0);word(&m,0x104,0x1001);begin(&m);cpu_run(m.cpu,40);
 cpu_run_result r=cpu_run(m.cpu,1);cpu_observation o=inspect(&m);
 TEST_ASSERT_EQUAL(50,r.elapsed);TEST_ASSERT_EQUAL(0,r.instructions);
 TEST_ASSERT_EQUAL_HEX32(0x180,o.pc);TEST_ASSERT_EQUAL_HEX32(0x1ff2,o.registers[15]);
 TEST_ASSERT_EQUAL_HEX32(0x1001,ram_value(&m,0x1ff4,4));TEST_ASSERT_EQUAL_HEX32(0x3039,ram_value(&m,0x1ff8,2));
 TEST_ASSERT_EQUAL_HEX32(0x2704,ram_value(&m,0x1ffa,2)); /* Backend initial CCR, not hardware reset promise. */
 cpu_destroy(m.cpu);
}
int main(void) {UNITY_BEGIN();RUN_TEST(request_rejected);RUN_TEST(reset_debit);
 RUN_TEST(reset_clears_pending_nmi);RUN_TEST(budgets_and_partitions);RUN_TEST(instruction_budgets);
 RUN_TEST(exceptions);RUN_TEST(irq_and_stop);RUN_TEST(address_error);return UNITY_END();}
