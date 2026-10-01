/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "cpu_adapter.h"
#include "guest_fixture.h"
#include <stdlib.h>
#include <string.h>
static void *allocate(void *p,size_t n) {(void)p; return malloc(n);}
static void release(void *p,void *v) {(void)p; free(v);}
static int read_bus(void *p,uint32_t a,unsigned w,uint32_t *v) {
 uint8_t *rom=p; if(a>512 || w>512-a) return 0;
 *v=0; for(unsigned i=0;i<w;i++) *v=(*v<<8)|rom[a+i]; return 1;
}
static int write_bus(void *p,uint32_t a,unsigned w,uint32_t v) {(void)p;(void)a;(void)w;(void)v;return 0;}
void setUp(void) {}
void tearDown(void) {}
static void reset_registers_are_observable(void) {
 uint8_t rom[512]; guest_fixture(rom,0,0); cpu_instance *c=NULL;
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_create(68000,(cpu_bus){rom,read_bus,write_bus},(cpu_allocator){NULL,allocate,release},&c));
 TEST_ASSERT_EQUAL(CPU_STATUS_OK,cpu_reset(c));
 cpu_observation o={0}; cpu_status result=cpu_inspect(c,&o); cpu_destroy(c);
 TEST_ASSERT_EQUAL_MESSAGE(CPU_STATUS_OK,result,"instance register observation available");
 TEST_ASSERT_EQUAL_HEX32(0x100,o.pc); TEST_ASSERT_EQUAL_HEX32(0x2000,o.registers[15]);
}
int main(void) {UNITY_BEGIN(); RUN_TEST(reset_registers_are_observable); return UNITY_END();}
