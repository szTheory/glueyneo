/* SPDX-License-Identifier: MIT */
#include "test_bus.h"
static int read_bus(void *data, uint32_t address, unsigned width, uint32_t *value) {
 test_bus *b=data; const uint8_t *p;
 if (width!=1 && width!=2 && width!=4) return 0;
 if (address <= b->rom_size && width <= b->rom_size-address) p=b->rom+address;
 else if (address>=b->ram_base && address-b->ram_base<=b->ram_size && width<=b->ram_size-(address-b->ram_base)) p=b->ram+(address-b->ram_base);
 else return 0;
 *value=0; for(unsigned i=0;i<width;i++) *value=(*value<<8)|p[i]; b->reads++; return 1;
}
static int write_bus(void *data, uint32_t address, unsigned width, uint32_t value) {
 test_bus *b=data;
 if ((width!=1 && width!=2 && width!=4) || address<b->ram_base || address-b->ram_base>b->ram_size || width>b->ram_size-(address-b->ram_base)) return 0;
 uint8_t *p=b->ram+(address-b->ram_base);
 for(unsigned i=0;i<width;i++) p[i]=(uint8_t)(value>>(8*(width-i-1)));
 b->writes++; return 1;
}
cpu_bus test_bus_bind(test_bus *b) { return (cpu_bus){b,read_bus,write_bus}; }
