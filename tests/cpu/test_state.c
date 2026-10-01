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
static int mutation;
static void put_word(machine *m,unsigned a,uint16_t v) {m->rom[a]=(uint8_t)(v>>8);m->rom[a+1]=(uint8_t)v;}
static cpu_guest_state capture(machine *m) {cpu_guest_state s;TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_capture(m->cpu,&s));return s;}
static void boot(machine *m) {TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(m));TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(m->cpu));}
static void same_state(machine *a,machine *b) {
 cpu_guest_state x=capture(a),y=capture(b);
 TEST_ASSERT_EQUAL_MEMORY(&x,&y,sizeof(x));TEST_ASSERT_EQUAL_MEMORY(a->ram,b->ram,sizeof(a->ram));
 TEST_ASSERT_EQUAL(a->count,b->count);TEST_ASSERT_FALSE(a->overflow);TEST_ASSERT_FALSE(b->overflow);
 for(size_t i=0;i<a->count;i++) {
  TEST_ASSERT_EQUAL(a->owner,a->trace[i].owner);TEST_ASSERT_EQUAL(b->owner,b->trace[i].owner);
  TEST_ASSERT_EQUAL(a->trace[i].address,b->trace[i].address);TEST_ASSERT_EQUAL(a->trace[i].value,b->trace[i].value);
  TEST_ASSERT_EQUAL(a->trace[i].width,b->trace[i].width);TEST_ASSERT_EQUAL(a->trace[i].write,b->trace[i].write);
 }
}
static void same_run(machine *a,machine *b,int64_t n) {
 cpu_run_result x=cpu_run(a->cpu,n),y=cpu_run(b->cpu,n);
 TEST_ASSERT_EQUAL(x.reason,y.reason);TEST_ASSERT_NOT_EQUAL(CPU_STATUS_HOST_FAULT,x.reason);
 TEST_ASSERT_EQUAL_UINT64(x.elapsed,y.elapsed);TEST_ASSERT_EQUAL_UINT64(x.instructions,y.instructions);
 TEST_ASSERT_EQUAL_UINT64(x.overshoot,y.overshoot);same_state(a,b);
}
static void setup_checkpoint(machine *m,unsigned kind) {
 prepare_machine(m,0);
 if(kind==3) { /* masked IRQ, then unmask and STOP */
  put_word(m,27*4+2,0x180);put_word(m,0x100,0x46fc);put_word(m,0x102,0x2000);
  put_word(m,0x104,0x4e72);put_word(m,0x106,0x2700);
 }
 if(kind==5 || kind==7) {put_word(m,4*4+2,0x180);put_word(m,0x100,0x4afc);}
 if(kind==6) { /* address exception leaves run/instruction and fault metadata */
  put_word(m,3*4+2,0x180);put_word(m,0x100,0x3039);put_word(m,0x102,0);put_word(m,0x104,0x1001);
  put_word(m,0x180,0x4e72);put_word(m,0x182,0x2700);
 }
 boot(m);
 if(kind==0) return; /* reset debt */
 cpu_run(m->cpu,40);
 if(kind==1) cpu_run(m->cpu,4); /* populated prefetch */
 if(kind==2) cpu_run(m->cpu,36); /* STOP */
 if(kind==3) cpu_set_irq(m->cpu,3);
 if(kind==4) {cpu_set_irq(m->cpu,7);cpu_set_irq(m->cpu,0);} /* latched edge, pins low */
 if(kind==5 || kind==6 || kind==7) cpu_run(m->cpu,1);
 if(kind==7) {cpu_run(m->cpu,1);cpu_run(m->cpu,1);} /* RTE restores normal modes. */
}
static void fresh_destination_continuation(void) {
 for(unsigned kind=0;kind<8;kind++) {
  machine source,baseline,destination;setup_checkpoint(&source,kind);setup_checkpoint(&baseline,kind);
  cpu_guest_state s=capture(&source);
  if(kind==0) TEST_ASSERT_EQUAL(40,s.reset_cycles);
  if(kind==1) {TEST_ASSERT_EQUAL_HEX32(0x102,s.pref_addr);TEST_ASSERT_EQUAL_HEX32(0x5680,s.pref_data);}
  if(kind==2) TEST_ASSERT_EQUAL(1,s.stopped);
  if(kind==3) TEST_ASSERT_EQUAL_HEX32(0x300,s.int_level);
  if(kind==4) {TEST_ASSERT_EQUAL(1,s.nmi_pending);TEST_ASSERT_EQUAL(0,s.int_level);}
  if(kind==5) TEST_ASSERT_EQUAL(8,s.instr_mode);
  if(kind==7) {TEST_ASSERT_EQUAL(0,s.instr_mode);TEST_ASSERT_EQUAL(0,s.run_mode);}
  if(kind==6) TEST_ASSERT_EQUAL(2,s.run_mode);
  prepare_machine(&destination,0);destination.owner=73;baseline.owner=91;
  memcpy(destination.rom,source.rom,sizeof(source.rom));memcpy(destination.ram,source.ram,sizeof(source.ram));
  TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&destination));
  TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_restore(destination.cpu,&s));
  cpu_destroy(source.cpu);TEST_ASSERT_EQUAL(0,source.live);memset(&source,0xa5,sizeof(source));
  baseline.count=destination.count=0;same_state(&baseline,&destination);
  if(kind==2) {cpu_set_irq(baseline.cpu,7);cpu_set_irq(destination.cpu,7);}
  for(unsigned step=0;step<6;step++) {
   same_run(&baseline,&destination,1);
   if(kind==3 && step==0) {cpu_set_irq(baseline.cpu,0);cpu_set_irq(destination.cpu,0);}
  }
  cpu_destroy(baseline.cpu);cpu_destroy(destination.cpu);TEST_ASSERT_EQUAL(0,destination.live);
 }
}
static void malformed_atomicity(void) {
 for(unsigned kind=0;kind<25;kind++) {
  machine a,b;setup_checkpoint(&a,1);setup_checkpoint(&b,1);cpu_guest_state invalid=capture(&a);
  switch(kind) {
   case 0:invalid.version++;break;case 1:invalid.size--;break;case 2:invalid.model=68010;break;
   case 3:invalid.s_flag=2;break;case 4:invalid.int_mask=1;break;case 5:invalid.int_level=8;break;
   case 6:invalid.stopped=2;break;case 7:invalid.ir=0x10000;break;case 8:invalid.pref_data=0x10000;break;
   case 9:invalid.pref_addr|=1;break;case 10:invalid.instr_mode=1;break;case 11:invalid.run_mode=1;break;
   case 12:invalid.reset_cycles=39;break;case 13:invalid.nmi_pending=2;break;case 14:invalid.virq_state=1;break;
   case 15:invalid.t0_flag=1;break;case 16:invalid.m_flag=2;break;case 17:invalid.aerr_fc=8;break;
   case 18:invalid.aerr_write_mode=1;break;case 19:invalid.instructions=UINT64_MAX;break;
   case 20:invalid.reset_cycles=40;invalid.stopped=1;break;case 21:invalid.address_space=1;break;
   case 22:invalid.reset_cycles=40;invalid.instructions=0;invalid.s_flag=0;break;
   case 23:invalid.reset_cycles=40;invalid.instructions=0;invalid.t1_flag=0x8000;break;
   case 24:invalid.reset_cycles=40;invalid.instructions=0;invalid.int_mask=0;break;
  }
  TEST_ASSERT_EQUAL(CPU_STATUS_INVALID_ARGUMENT,cpu_restore(a.cpu,&invalid));
  TEST_ASSERT_EQUAL(CPU_STATUS_INVALID_ARGUMENT,cpu_restore(a.cpu,NULL));
  a.count=b.count=0;same_run(&a,&b,28);cpu_destroy(a.cpu);cpu_destroy(b.cpu);
 }
}
static void zero_near_counter_limit(void) {
 machine m;setup_checkpoint(&m,1);cpu_guest_state s=capture(&m);
 s.instructions=UINT64_MAX-CPU_MAX_CYCLE_REQUEST-2;
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_restore(m.cpu,&s));
 TEST_ASSERT_EQUAL(CPU_STATUS_BUDGET,cpu_run(m.cpu,1).reason);
 cpu_run_result r=cpu_run(m.cpu,0);cpu_destroy(m.cpu);
 TEST_ASSERT_EQUAL_MESSAGE(CPU_STATUS_BUDGET,r.reason,"zero remains no-op near counter limit");
 TEST_ASSERT_EQUAL_UINT64(0,r.elapsed);
}
static void consequential_mutation(void) {
 machine source,destination;setup_checkpoint(&source,mutation==1?4:1);
 cpu_guest_state s=capture(&source);prepare_machine(&destination,0);
 memcpy(destination.rom,source.rom,sizeof(source.rom));memcpy(destination.ram,source.ram,sizeof(source.ram));
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,create_machine(&destination));
 if(mutation==1) s.nmi_pending=0;
 if(mutation==2) s.pref_data=0x5a80; /* ADDQ #5 instead of #3 */
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_restore(destination.cpu,&s));
 cpu_run(source.cpu,1);cpu_run(destination.cpu,1);
 cpu_guest_state a=capture(&source),b=capture(&destination);
 cpu_destroy(source.cpu);cpu_destroy(destination.cpu);
 TEST_ASSERT_EQUAL_MESSAGE(mutation==1?a.dar[1]:a.dar[0],mutation==1?b.dar[1]:b.dar[0],"consequential saved-field comparison");
}
typedef struct {machine m;cpu_guest_state state;unsigned attempts;} reentry_case;
static int guarded_read(void *p,uint32_t a,unsigned w,uint32_t *v) {
 reentry_case *c=p;
 if(c->m.cpu) {
  cpu_guest_state out;
  if(cpu_capture(c->m.cpu,&out)!=CPU_STATUS_INVALID_ARGUMENT ||
     cpu_restore(c->m.cpu,&c->state)!=CPU_STATUS_INVALID_ARGUMENT) return 0;
  c->attempts++;
 }
 return trace_read(&c->m,a,w,v);
}
static void lifecycle(void) {
 reentry_case c={0};prepare_machine(&c.m,0);
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_create(68000,(cpu_bus){&c,guarded_read,trace_write},
  (cpu_allocator){&c.m,count_allocate,count_release},&c.m.cpu));
 TEST_ASSERT_EQUAL(CPU_STATUS_INVALID_ARGUMENT,cpu_capture(c.m.cpu,&c.state));
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(c.m.cpu));c.state=capture(&c.m);
 TEST_ASSERT_NOT_EQUAL(CPU_STATUS_HOST_FAULT,cpu_run(c.m.cpu,44).reason);TEST_ASSERT_TRUE(c.attempts>2);
 c.m.fail_read=1;c.m.fail_address=0x108;
 TEST_ASSERT_EQUAL(CPU_STATUS_HOST_FAULT,cpu_run(c.m.cpu,100).reason);
 TEST_ASSERT_EQUAL(CPU_STATUS_HOST_FAULT,cpu_capture(c.m.cpu,&c.state));
 TEST_ASSERT_EQUAL(CPU_STATUS_HOST_FAULT,cpu_restore(c.m.cpu,&c.state));cpu_destroy(c.m.cpu);
}
int main(int argc,char **argv) {
 if(argc==2) mutation=strcmp(argv[1],"--mutate-pending")==0?1:2;
 UNITY_BEGIN();
 if(mutation) RUN_TEST(consequential_mutation);
 else {RUN_TEST(complete_state_available);RUN_TEST(fresh_destination_continuation);
  RUN_TEST(malformed_atomicity);RUN_TEST(consequential_mutation);RUN_TEST(lifecycle);RUN_TEST(zero_near_counter_limit);}
 return UNITY_END();
}
