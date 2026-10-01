/* SPDX-License-Identifier: MIT */
#include "cpu_adapter.h"
#include "m68kcpu.h"
#include <string.h>
#include <stdint.h>

struct cpu_instance {
 m68ki_context backend;
 cpu_allocator allocator;
 int faulted, ready;
};
cpu_status cpu_inspect(cpu_instance *c,cpu_observation *out) {
 if(!c || !out) return CPU_STATUS_INVALID_ARGUMENT;
 if(c->faulted) return CPU_STATUS_HOST_FAULT;
 memset(out,0,sizeof(*out));
 for(unsigned i=0;i<16;i++) out->registers[i]=c->backend.cpu.dar[i];
 out->pc=c->backend.cpu.pc; out->previous_pc=c->backend.cpu.ppc;
 out->sr=m68k_get_reg(&c->backend,NULL,M68K_REG_SR);
 out->stopped=c->backend.cpu.stopped; out->irq=c->backend.cpu.int_level;
 out->nmi=c->backend.cpu.nmi_pending; out->instructions=c->backend.instructions;
 return CPU_STATUS_OK;
}
/* A host fault always returns to the current reset/run call, never to a
 * previous call's jump frame. The failed guest is terminal until reset. */
static unsigned read_bus(m68ki_context *ctx, unsigned address, unsigned width) {
 unsigned value=0;
 if(!ctx->bus_read(ctx->bus_data,address,width,&value)) longjmp(ctx->host_fault,1);
 return value;
}
static void write_bus(m68ki_context *ctx, unsigned address, unsigned width, unsigned value) {
 if(!ctx->bus_write(ctx->bus_data,address,width,value)) longjmp(ctx->host_fault,1);
}
unsigned m68k_read_memory_8(m68ki_context *ctx,unsigned a) {return read_bus(ctx,a,1);}
unsigned m68k_read_memory_16(m68ki_context *ctx,unsigned a) {return read_bus(ctx,a,2);}
unsigned m68k_read_memory_32(m68ki_context *ctx,unsigned a) {return read_bus(ctx,a,4);}
void m68k_write_memory_8(m68ki_context *ctx,unsigned a,unsigned v) {write_bus(ctx,a,1,v);}
void m68k_write_memory_16(m68ki_context *ctx,unsigned a,unsigned v) {write_bus(ctx,a,2,v);}
void m68k_write_memory_32(m68ki_context *ctx,unsigned a,unsigned v) {write_bus(ctx,a,4,v);}
cpu_status cpu_create(unsigned model,cpu_bus bus,cpu_allocator a,cpu_instance **out) {
 if(!out) return CPU_STATUS_INVALID_ARGUMENT;
 *out=NULL;
 if(model!=68000) return CPU_STATUS_UNSUPPORTED_MODEL;
 if(!bus.read || !bus.write || !a.allocate || !a.release) return CPU_STATUS_INVALID_ARGUMENT;
 cpu_instance *c=a.allocate(a.userdata,sizeof(*c));
 if(!c) return CPU_STATUS_ALLOCATION_FAILURE;
 memset(c,0,sizeof(*c)); c->allocator=a;
 c->backend.bus_data=bus.userdata; c->backend.bus_read=bus.read; c->backend.bus_write=bus.write;
 m68k_init(&c->backend); m68k_set_cpu_type(&c->backend,M68K_CPU_TYPE_68000);
 *out=c; return CPU_STATUS_OK;
}
void cpu_destroy(cpu_instance *c) {
 if(c) {cpu_allocator a=c->allocator; a.release(a.userdata,c);}
}
cpu_status cpu_reset(cpu_instance *c) {
 if(!c) return CPU_STATUS_INVALID_ARGUMENT;
 c->faulted=0; c->ready=0; c->backend.instructions=0;
 if(setjmp(c->backend.host_fault)) {c->faulted=1; return CPU_STATUS_HOST_FAULT;}
 m68k_pulse_reset(&c->backend); c->ready=1; return CPU_STATUS_OK;
}
cpu_run_result cpu_run(cpu_instance *c,int64_t cycles) {
 cpu_run_result r={.requested=cycles<0?0:(uint64_t)cycles,.reason=CPU_STATUS_INVALID_ARGUMENT};
 if(!c || cycles<0 || cycles>CPU_MAX_CYCLE_REQUEST) return r;
 if(c->faulted) {r.reason=CPU_STATUS_HOST_FAULT; return r;}
 if(!c->ready) return r;
 r.reason=CPU_STATUS_BUDGET;
 if(!cycles) return r;
 unsigned request=(unsigned)cycles;
 unsigned long long before=c->backend.instructions;
 if(setjmp(c->backend.host_fault)) {c->faulted=1; r.reason=CPU_STATUS_HOST_FAULT; return r;}
 r.elapsed=(unsigned)m68k_execute(&c->backend,(int)request);
 if(c->backend.cpu.stopped & STOP_LEVEL_HALT) {c->faulted=1; r.reason=CPU_STATUS_HOST_FAULT; return r;}
 r.instructions=c->backend.instructions-before;
 r.overshoot=r.elapsed>request ? r.elapsed-request : 0;
 r.reason=c->backend.cpu.stopped ? CPU_STATUS_STOPPED : CPU_STATUS_BUDGET;
 return r;
}
cpu_status cpu_set_irq(cpu_instance *c,unsigned level) {
 if(!c || level>7) return CPU_STATUS_INVALID_ARGUMENT;
 if(c->faulted) return CPU_STATUS_HOST_FAULT;
 if(!c->ready) return CPU_STATUS_INVALID_ARGUMENT;
 m68k_set_irq(&c->backend,level); return CPU_STATUS_OK;
}
