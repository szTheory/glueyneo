/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_CPU_ADAPTER_H
#define GLUEYNEO_CPU_ADAPTER_H
#include <stddef.h>
#include <stdint.h>
typedef struct cpu_instance cpu_instance;
typedef enum { CPU_STATUS_OK, CPU_STATUS_INVALID_ARGUMENT, CPU_STATUS_ALLOCATION_FAILURE,
 CPU_STATUS_UNSUPPORTED_MODEL, CPU_STATUS_STOPPED, CPU_STATUS_BUDGET, CPU_STATUS_HOST_FAULT } cpu_status;
typedef struct { void *userdata; void *(*allocate)(void *, size_t);
 void (*release)(void *, void *); } cpu_allocator;
typedef struct { void *userdata; int (*read)(void *, uint32_t, unsigned, uint32_t *);
 int (*write)(void *, uint32_t, unsigned, uint32_t); } cpu_bus;
typedef struct { uint64_t requested, elapsed, instructions, overshoot;
 cpu_status reason; } cpu_run_result;
/* Host bindings must remain live; calls on one instance cannot overlap/reenter.
 * A host fault permits reset/destruction only. Reset does not undo bus writes.
 * NULL destruction is safe; destroying an already freed handle is not. */
cpu_status cpu_create(unsigned model, cpu_bus bus, cpu_allocator allocator, cpu_instance **out);
void cpu_destroy(cpu_instance *cpu);
cpu_status cpu_reset(cpu_instance *cpu);
cpu_run_result cpu_run(cpu_instance *cpu, uint64_t cycles);
cpu_status cpu_set_irq(cpu_instance *cpu, unsigned level);
/* Private observation only, not a serialized state or public ABI. */
typedef struct { uint32_t registers[16], pc, previous_pc, sr, stopped, irq, nmi;
 uint64_t instructions; } cpu_observation;
cpu_status cpu_inspect(cpu_instance *cpu, cpu_observation *out);
#endif
