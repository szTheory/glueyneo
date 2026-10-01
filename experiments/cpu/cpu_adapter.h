/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_CPU_ADAPTER_H
#define GLUEYNEO_CPU_ADAPTER_H
#include <stddef.h>
#include <stdint.h>
typedef struct cpu_instance cpu_instance;
typedef enum { CPU_OK, CPU_INVALID_ARGUMENT, CPU_ALLOCATION_FAILURE,
 CPU_UNSUPPORTED_MODEL, CPU_STOPPED, CPU_BUDGET, CPU_HOST_FAULT } cpu_status;
typedef struct { void *userdata; void *(*allocate)(void *, size_t);
 void (*release)(void *, void *); } cpu_allocator;
typedef struct { void *userdata; int (*read)(void *, uint32_t, unsigned, uint32_t *);
 int (*write)(void *, uint32_t, unsigned, uint32_t); } cpu_bus;
typedef struct { uint64_t requested, elapsed, instructions, overshoot;
 cpu_status reason; } cpu_run_result;
cpu_status cpu_create(unsigned model, cpu_bus bus, cpu_allocator allocator, cpu_instance **out);
void cpu_destroy(cpu_instance *cpu);
cpu_status cpu_reset(cpu_instance *cpu);
cpu_run_result cpu_run(cpu_instance *cpu, uint64_t cycles);
cpu_status cpu_set_irq(cpu_instance *cpu, unsigned level);
#endif
