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
/* Signed requests 0..1000000. INT_MAX headroom exceeds the qualified maximum
 * combined reset40 + IRQ44 + instruction132 debit; zero never consumes debt. */
#define CPU_MAX_CYCLE_REQUEST INT64_C(1000000)
cpu_run_result cpu_run(cpu_instance *cpu, int64_t cycles);
cpu_status cpu_set_irq(cpu_instance *cpu, unsigned level);
/* Private observation only, not a serialized state or public ABI. */
typedef struct { uint32_t registers[16], pc, previous_pc, sr, stopped, irq, nmi;
 uint64_t instructions; } cpu_observation;
cpu_status cpu_inspect(cpu_instance *cpu, cpu_observation *out);
/* Private same-build record, no durable or public ABI promise. Every field is
 * required; size/version reject missing or incompatible records. Host memory
 * is copied separately. Capture/restore reject active or terminal instances. */
#define CPU_GUEST_STATE_VERSION 1
#define CPU_GUEST_SCALARS(F) \
 F(ppc) F(pc) F(vbr) F(ir) F(t1_flag) F(t0_flag) F(s_flag) F(m_flag) \
 F(x_flag) F(n_flag) F(not_z_flag) F(v_flag) F(c_flag) F(int_mask) F(int_level) \
 F(stopped) F(pref_addr) F(pref_data) F(instr_mode) F(run_mode) \
 F(reset_cycles) F(virq_state) F(nmi_pending)
typedef struct {
 uint32_t version, size, model, dar[16], dar_save[16], sp[7];
#define CPU_STATE_DECLARE(name) uint32_t name;
 CPU_GUEST_SCALARS(CPU_STATE_DECLARE)
#undef CPU_STATE_DECLARE
 uint32_t tracing, address_space, aerr_address, aerr_write_mode, aerr_fc;
 uint64_t instructions;
} cpu_guest_state;
cpu_status cpu_capture(cpu_instance *cpu, cpu_guest_state *out);
cpu_status cpu_restore(cpu_instance *cpu, const cpu_guest_state *state);
#endif
