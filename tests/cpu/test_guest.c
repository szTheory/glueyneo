/* SPDX-License-Identifier: MIT */
#include "unity.h"
#include "cpu_adapter.h"
#include "test_bus.h"
#include "guest_fixture.h"
#include <stdlib.h>
#include <string.h>
static uint8_t rom[512], ram[4096];
static cpu_instance *cpu;
static test_bus bus;
static int mutate;
static void *allocate(void *data,size_t n) {(void)data; return malloc(n);}
static void release(void *data,void *p) {(void)data; free(p);}
void setUp(void) {
 memset(ram,0,sizeof(ram)); guest_fixture(rom,0,mutate);
 bus=(test_bus){.rom=rom,.rom_size=sizeof(rom),.ram=ram,.ram_size=sizeof(ram),.ram_base=0x1000};
 TEST_ASSERT_EQUAL(CPU_OK,cpu_create(68000,test_bus_bind(&bus),(cpu_allocator){NULL,allocate,release},&cpu));
 TEST_ASSERT_EQUAL(CPU_OK,cpu_reset(cpu));
}
void tearDown(void) {cpu_destroy(cpu); cpu=NULL;}
static void guest_adds_and_stores(void) {
 cpu_run_result r=cpu_run(cpu,200);
 TEST_ASSERT_EQUAL_UINT32_MESSAGE(10,((uint32_t)ram[0]<<24)|((uint32_t)ram[1]<<16)|((uint32_t)ram[2]<<8)|ram[3],"guest arithmetic/store result");
 TEST_ASSERT_EQUAL(CPU_STOPPED,r.reason);
 TEST_ASSERT_EQUAL_UINT64(4,r.instructions);
}
static void zero_is_noop(void) {
 size_t reads=bus.reads,writes=bus.writes;
 cpu_run_result r=cpu_run(cpu,0);
 TEST_ASSERT_EQUAL_UINT64(0,r.elapsed); TEST_ASSERT_EQUAL_UINT64(0,r.instructions);
 TEST_ASSERT_EQUAL(reads,bus.reads); TEST_ASSERT_EQUAL(writes,bus.writes);
 (void)cpu_run(cpu,200); TEST_ASSERT_EQUAL_UINT8(10,ram[3]);
}
static void bad_address_survives(void) {
 rom[0x108]=0x30;
 cpu_run_result r=cpu_run(cpu,200);
 TEST_ASSERT_EQUAL(CPU_HOST_FAULT,r.reason);
 TEST_ASSERT_EQUAL(CPU_HOST_FAULT,cpu_run(cpu,200).reason);
}
int main(int argc,char **argv) {
 mutate=argc==2 && strcmp(argv[1],"--mutate")==0;
 UNITY_BEGIN(); RUN_TEST(guest_adds_and_stores);
 if(argc==1) {RUN_TEST(zero_is_noop); RUN_TEST(bad_address_survives);}
 return UNITY_END();
}
