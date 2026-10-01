/* SPDX-License-Identifier: MIT. Host-only observation harness; no backend access. */
#ifndef ISOLATION_FIXTURE_H
#define ISOLATION_FIXTURE_H
#include "cpu_adapter.h"
#include "guest_fixture.h"
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define BOUNDARIES 9
#define TRACE_CAP 128
typedef struct { uint32_t owner,address,value,width,write; } bus_event;
typedef struct {
 uint8_t rom[512],ram[4096]; unsigned owner, overflow;
 bus_event trace[TRACE_CAP]; size_t count, allocations,bytes,live,fail_at;
 uint32_t fail_address; int fail_read,fail_write;
 cpu_instance *cpu; uint64_t create_ns;
} machine;
typedef struct { cpu_observation cpu; cpu_run_result run;
 uint8_t ram[4096]; bus_event trace[TRACE_CAP]; size_t count; unsigned overflow; } observation;
typedef struct { pthread_mutex_t mutex; pthread_cond_t cond; unsigned arrived; } start_gate;
static void gate_wait(start_gate *g) {
 pthread_mutex_lock(&g->mutex); g->arrived++;
 if(g->arrived==2) pthread_cond_broadcast(&g->cond);
 while(g->arrived<2) pthread_cond_wait(&g->cond,&g->mutex);
 pthread_mutex_unlock(&g->mutex);
}
static void *count_allocate(void *data,size_t n) {
 machine *m=data; m->allocations++; m->bytes+=n;
 if(m->fail_at==m->allocations) return NULL;
 void *p=malloc(n); if(p) m->live++; return p;
}
static void count_release(void *data,void *p) {machine *m=data; if(p) {m->live--;free(p);}}
static int access_bus(machine *m,uint32_t a,unsigned w,uint32_t *v,int write) {
 uint8_t *p=NULL;
 if(w!=1 && w!=2 && w!=4) return 0;
 if((write?m->fail_write:m->fail_read) && a==m->fail_address) return 0;
 if(!write && a<=512 && w<=512-a) p=m->rom+a;
 if(a>=0x1000 && a<=0x2000 && w<=0x2000-a) p=m->ram+a-0x1000;
 if(!p) return 0;
 if(write) {for(unsigned i=0;i<w;i++) p[i]=(uint8_t)(*v>>(8*(w-i-1)));}
 else {*v=0;for(unsigned i=0;i<w;i++) *v=(*v<<8)|p[i];}
 if(m->count==TRACE_CAP) {m->overflow=1;return 0;}
 m->trace[m->count++]=(bus_event){m->owner,a,*v,w,(unsigned)write}; return 1;
}
static int trace_read(void *p,uint32_t a,unsigned w,uint32_t *v) {return access_bus(p,a,w,v,0);}
static int trace_write(void *p,uint32_t a,unsigned w,uint32_t v) {return access_bus(p,a,w,&v,1);}
static void prepare_machine(machine *m,unsigned owner) {
 memset(m,0,sizeof(*m));m->owner=owner;guest_fixture(m->rom,owner,0);
 /* Level-7 autovector to ADDQ.L #1,D1 / RTE, then a second STOP. */
 m->rom[31*4+2]=1;m->rom[31*4+3]=0x80;
 const uint8_t handler[]={0x52,0x81,0x4e,0x73};memcpy(m->rom+0x180,handler,4);
 const uint8_t stop[]={0x4e,0x72,0x27,0};memcpy(m->rom+0x10e,stop,4);
}
static cpu_status create_machine(machine *m) {
 struct timespec begin,end;clock_gettime(CLOCK_MONOTONIC,&begin);
 cpu_status result=cpu_create(68000,(cpu_bus){m,trace_read,trace_write},
  (cpu_allocator){m,count_allocate,count_release},&m->cpu);
 clock_gettime(CLOCK_MONOTONIC,&end);
 m->create_ns=(uint64_t)((int64_t)(end.tv_sec-begin.tv_sec)*1000000000+end.tv_nsec-begin.tv_nsec);
 return result;
}
static int boundary(machine *m,unsigned step,observation *o) {
 memset(o,0,sizeof(*o));
 if(step==6 && cpu_set_irq(m->cpu,7)!=CPU_STATUS_OK) return 0;
 o->run=cpu_run(m->cpu,step==0?0:1);
 if(o->run.reason==CPU_STATUS_HOST_FAULT) return 0;
 if(cpu_inspect(m->cpu,&o->cpu)!=CPU_STATUS_OK) return 0;
 memcpy(o->ram,m->ram,sizeof(o->ram));memcpy(o->trace,m->trace,sizeof(o->trace));
 o->count=m->count;o->overflow=m->overflow;return !m->overflow;
}
static int run_machine(machine *m,observation out[BOUNDARIES]) {
 if(create_machine(m)!=CPU_STATUS_OK) return 0;
 if(cpu_reset(m->cpu)!=CPU_STATUS_OK) {cpu_destroy(m->cpu);m->cpu=NULL;return 0;}
 int ok=1;for(unsigned i=0;i<BOUNDARIES && ok;i++) ok=boundary(m,i,&out[i]);
 cpu_destroy(m->cpu);m->cpu=NULL;return ok && !m->live;
}
static int observations_equal(const observation *a,const observation *b) {
 return memcmp(&a->cpu,&b->cpu,sizeof(a->cpu))==0 &&
 a->run.requested==b->run.requested && a->run.elapsed==b->run.elapsed &&
 a->run.instructions==b->run.instructions && a->run.overshoot==b->run.overshoot &&
 a->run.reason==b->run.reason && a->count==b->count && !a->overflow && !b->overflow &&
 memcmp(a->ram,b->ram,sizeof(a->ram))==0 &&
 memcmp(a->trace,b->trace,a->count*sizeof(bus_event))==0;
}
typedef struct {machine m;observation out[BOUNDARIES];start_gate *gate;int ok;} thread_case;
static void *thread_run(void *p) {thread_case *c=p;gate_wait(c->gate);c->ok=run_machine(&c->m,c->out);return NULL;}
#endif
