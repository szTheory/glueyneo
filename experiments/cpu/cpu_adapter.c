/* SPDX-License-Identifier: MIT
 * RED-stage link scaffold; no backend execution exists yet. */
#include "cpu_adapter.h"
struct cpu_instance { cpu_allocator allocator; };
cpu_status cpu_create(unsigned model, cpu_bus bus, cpu_allocator a, cpu_instance **out) {
 (void)model; (void)bus; *out = a.allocate(a.userdata, sizeof(**out));
 if (!*out) return CPU_ALLOCATION_FAILURE;
 (*out)->allocator = a; return CPU_OK;
}
void cpu_destroy(cpu_instance *c) { c->allocator.release(c->allocator.userdata, c); }
cpu_status cpu_reset(cpu_instance *c) { (void)c; return CPU_OK; }
cpu_run_result cpu_run(cpu_instance *c, uint64_t cycles) {
 (void)c; return (cpu_run_result){ .requested=cycles, .reason=CPU_BUDGET };
}
cpu_status cpu_set_irq(cpu_instance *c, unsigned level) { (void)c; (void)level; return CPU_OK; }
