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
    OWNED_CPU_STOPPED,
    OWNED_CPU_COUNTER_OVERFLOW
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
    uint8_t reset_pending;
    uint8_t last_exception_vector;
    uint64_t instructions;
    uint64_t instruction_cycles;
    uint64_t reset_cycles;
    uint64_t exception_cycles;
    uint64_t idle_cycles;
    uint64_t total_cycles;
    uint64_t reset_signal_events;
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
/* Private same-build continuation record. This is an in-memory test contract,
 * not a public ABI, wire format, emulator snapshot, replay, or durable save. */
#define OWNED_CPU_STATE_VERSION UINT32_C(1)
#define OWNED_CPU_STATE_CORE_IDENTITY_SHA256 \
    "8ac6ded7859184651f6eb3fff8a87c073f8e24a98d66175b64c3d86f69cbd15f"
#define OWNED_CPU_STATE_FIELD_DATA_REGISTERS (UINT64_C(1) << 0)
#define OWNED_CPU_STATE_FIELD_ADDRESS_REGISTERS (UINT64_C(1) << 1)
#define OWNED_CPU_STATE_FIELD_PC_AND_PREVIOUS_PC (UINT64_C(1) << 2)
#define OWNED_CPU_STATE_FIELD_STACK_BANKS (UINT64_C(1) << 3)
#define OWNED_CPU_STATE_FIELD_DIAGNOSTIC (UINT64_C(1) << 4)
#define OWNED_CPU_STATE_FIELD_SR (UINT64_C(1) << 5)
#define OWNED_CPU_STATE_FIELD_STOPPED (UINT64_C(1) << 6)
#define OWNED_CPU_STATE_FIELD_IRQ_LEVEL (UINT64_C(1) << 7)
#define OWNED_CPU_STATE_FIELD_IRQ7_PENDING (UINT64_C(1) << 8)
#define OWNED_CPU_STATE_FIELD_RESET_PENDING (UINT64_C(1) << 9)
#define OWNED_CPU_STATE_FIELD_EXCEPTION_VECTOR (UINT64_C(1) << 10)
#define OWNED_CPU_STATE_FIELD_INSTRUCTIONS (UINT64_C(1) << 11)
#define OWNED_CPU_STATE_FIELD_INSTRUCTION_CYCLES (UINT64_C(1) << 12)
#define OWNED_CPU_STATE_FIELD_RESET_CYCLES (UINT64_C(1) << 13)
#define OWNED_CPU_STATE_FIELD_EXCEPTION_AND_IDLE_CYCLES (UINT64_C(1) << 14)
#define OWNED_CPU_STATE_FIELD_TOTAL_AND_RESET_SIGNALS (UINT64_C(1) << 15)
#define OWNED_CPU_STATE_REQUIRED_FIELDS UINT64_C(0x000000000000ffff)

typedef struct {
    uint32_t size;
    uint32_t version;
    char core_identity[65];
    uint64_t present_fields;
    uint32_t data_registers[8];
    uint32_t address_registers[8];
    uint32_t pc;
    uint32_t previous_pc;
    uint32_t usp;
    uint32_t ssp;
    uint32_t fault_pc;
    uint16_t sr;
    uint16_t instruction_register;
    uint8_t stopped;
    uint8_t irq_level;
    uint8_t irq7_pending;
    uint8_t reset_pending;
    uint8_t last_exception_vector;
    uint64_t instructions;
    uint64_t instruction_cycles;
    uint64_t reset_cycles;
    uint64_t exception_cycles;
    uint64_t idle_cycles;
    uint64_t total_cycles;
    uint64_t reset_signal_events;
} owned_cpu_state;

owned_cpu_status owned_cpu_capture_state(const owned_cpu *cpu, owned_cpu_state *out_state);
owned_cpu_status owned_cpu_restore_state(owned_cpu *cpu, const owned_cpu_state *state);

/* Private test-only seeds for flag, stack-bank, fault-boundary, and accounting
 * cases. These declarations are absent from consumer builds. */
owned_cpu_status owned_cpu_test_seed_data_register(owned_cpu *cpu, unsigned reg,
                                                    uint32_t value);
owned_cpu_status owned_cpu_test_seed_execution_state(owned_cpu *cpu, uint16_t sr,
                                                      uint32_t usp, uint32_t ssp,
                                                      uint32_t pc);
owned_cpu_status owned_cpu_test_seed_counters(owned_cpu *cpu, uint64_t instructions,
                                               uint64_t instruction_cycles,
                                               uint64_t exception_cycles,
                                               uint64_t idle_cycles,
                                               uint64_t total_cycles);
#endif

#endif
