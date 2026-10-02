/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_OWNED_CPU_H
#define GLUEYNEO_OWNED_CPU_H

#include <stddef.h>
#include <stdint.h>

#define OWNED_CPU_MODEL_MC68000 UINT32_C(68000)
#define OWNED_CPU_MAX_CYCLE_BUDGET UINT64_C(1000000)

typedef struct owned_cpu owned_cpu;

typedef enum {
    OWNED_CPU_OK = 0,
    OWNED_CPU_INVALID_ARGUMENT,
    OWNED_CPU_ALLOCATION_FAILURE,
    OWNED_CPU_UNSUPPORTED_MODEL,
    OWNED_CPU_ADDRESS_ERROR,
    OWNED_CPU_PRIVILEGE_VIOLATION,
    OWNED_CPU_UNSUPPORTED_OPCODE,
    OWNED_CPU_HOST_FAULT,
    OWNED_CPU_BUDGET,
    OWNED_CPU_STOPPED
} owned_cpu_status;

typedef struct {
    void *userdata;
    int (*read16)(void *userdata, uint32_t address, uint16_t *value);
    int (*write16)(void *userdata, uint32_t address, uint16_t value);
} owned_cpu_bus;

typedef struct {
    void *userdata;
    void *(*allocate)(void *userdata, size_t bytes);
    void (*release)(void *userdata, void *allocation);
} owned_cpu_allocator;

typedef struct {
    owned_cpu_status reason;
    uint64_t requested_cycles;
    uint64_t elapsed_cycles;
    uint64_t overshoot_cycles;
    uint64_t instructions;
    uint32_t pc;
    uint32_t fault_pc;
    uint16_t instruction_register;
} owned_cpu_run_result;

typedef struct {
    uint32_t data_registers[8];
    uint32_t address_registers[8];
    uint32_t pc;
    uint32_t previous_pc;
    uint32_t usp;
    uint32_t ssp;
    uint16_t sr;
    uint8_t stopped;
    uint8_t irq_level;
    uint8_t irq7_pending;
    uint64_t instructions;
    uint64_t instruction_cycles;
    uint64_t reset_cycles;
} owned_cpu_observation;

/* All callback and allocator bindings must remain live for the instance.
 * Calls on one instance must not overlap or reenter. A host callback failure
 * is terminal until reset or destruction; completed bus writes are retained. */
owned_cpu_status owned_cpu_create(uint32_t model, owned_cpu_bus bus,
                                  owned_cpu_allocator allocator, owned_cpu **out_cpu);
void owned_cpu_destroy(owned_cpu *cpu);
owned_cpu_status owned_cpu_reset(owned_cpu *cpu);
owned_cpu_run_result owned_cpu_run(owned_cpu *cpu, uint64_t cycle_budget);
owned_cpu_status owned_cpu_set_irq(owned_cpu *cpu, unsigned level);
owned_cpu_status owned_cpu_observe(const owned_cpu *cpu, owned_cpu_observation *out);

#ifdef OWNED_CPU_TEST_HOOKS
/* Test-only seed for arithmetic flag boundaries that the first guest subset
 * cannot construct in a bounded number of instructions. */
owned_cpu_status owned_cpu_test_seed_data_register(owned_cpu *cpu, unsigned reg,
                                                    uint32_t value);
#endif

#endif
