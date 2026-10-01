/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_TEST_BUS_H
#define GLUEYNEO_TEST_BUS_H
#include "cpu_adapter.h"
typedef struct { const uint8_t *rom; size_t rom_size; uint8_t *ram;
 size_t ram_size; uint32_t ram_base; size_t reads, writes; } test_bus;
cpu_bus test_bus_bind(test_bus *bus);
#endif
