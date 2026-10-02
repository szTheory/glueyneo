/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_OWNED_CPU_ISOLATION_FIXTURE_H
#define GLUEYNEO_OWNED_CPU_ISOLATION_FIXTURE_H

#include "cpu.h"
#include "guest_fixture.h"

#include <pthread.h>
#include <stdint.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum {
    ISO_ROM_SIZE = 512,
    ISO_RAM_BASE = 0x1000,
    ISO_RAM_SIZE = 0x4000,
    ISO_TRACE_CAPACITY = 128,
    ISO_BOUNDARIES = 6
};

typedef struct {
    uint32_t address;
    uint16_t value;
    uint8_t write;
    uint8_t succeeded;
} iso_bus_event;

typedef struct {
    uint8_t rom[ISO_ROM_SIZE];
    uint8_t ram[ISO_RAM_SIZE];
    owned_cpu *cpu;
    unsigned owner;
    iso_bus_event events[ISO_TRACE_CAPACITY];
    size_t event_count;
    size_t allocation_attempts;
    size_t live_allocations;
    size_t live_bytes;
    size_t fail_allocate_at;
    int fail_read;
    uint32_t fail_read_address;
    int fail_write;
    uint32_t fail_write_address;
    int reentry_probe;
    owned_cpu_status reentry_run;
    owned_cpu_status reentry_reset;
    owned_cpu_status reentry_observe;
    owned_cpu_status reentry_irq;
    size_t reentry_live_allocations;
} iso_machine;

typedef struct {
    owned_cpu_observation cpu;
    owned_cpu_run_result run;
    uint8_t ram[ISO_RAM_SIZE];
    iso_bus_event events[ISO_TRACE_CAPACITY];
    size_t event_count;
} iso_snapshot;

typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    unsigned ready;
    int released;
} iso_start_gate;

typedef struct {
    iso_start_gate *gate;
    unsigned owner;
    iso_machine machine;
    iso_snapshot snapshots[ISO_BOUNDARIES];
    int succeeded;
} iso_thread_case;

typedef union {
    struct { size_t bytes; } metadata;
    max_align_t alignment;
} iso_allocation_header;

static inline void *iso_allocate(void *userdata, size_t bytes) {
    iso_machine *machine = userdata;
    if (machine == NULL) return NULL;
    machine->allocation_attempts++;
    if (machine->fail_allocate_at == machine->allocation_attempts) return NULL;
    if (bytes > SIZE_MAX - sizeof(iso_allocation_header)) return NULL;
    iso_allocation_header *header = malloc(sizeof(*header) + bytes);
    if (header != NULL) {
        header->metadata.bytes = bytes;
        machine->live_allocations++;
        machine->live_bytes += bytes;
        return header + 1;
    }
    return NULL;
}

static inline void iso_release(void *userdata, void *allocation) {
    iso_machine *machine = userdata;
    if (machine == NULL || allocation == NULL) return;
    iso_allocation_header *header = (iso_allocation_header *)allocation - 1;
    if (machine->live_allocations != 0u) machine->live_allocations--;
    if (machine->live_bytes >= header->metadata.bytes) {
        machine->live_bytes -= header->metadata.bytes;
    } else {
        machine->live_bytes = 0u;
    }
    free(header);
}

static inline void iso_record(iso_machine *machine, uint32_t address,
                              uint16_t value, int write, int succeeded) {
    if (machine->event_count < ISO_TRACE_CAPACITY) {
        machine->events[machine->event_count++] = (iso_bus_event){
            address, value, (uint8_t)(write != 0), (uint8_t)(succeeded != 0)};
    }
}

static inline void iso_probe_reentry(iso_machine *machine) {
    if (machine->reentry_probe == 0 || machine->cpu == NULL) return;
    machine->reentry_probe = 0;
    owned_cpu_observation observation;
    machine->reentry_run = owned_cpu_run(machine->cpu, 1u).reason;
    machine->reentry_reset = owned_cpu_reset(machine->cpu);
    machine->reentry_observe = owned_cpu_observe(machine->cpu, &observation);
    machine->reentry_irq = owned_cpu_set_irq(machine->cpu, 1u);
    owned_cpu_destroy(machine->cpu);
    machine->reentry_live_allocations = machine->live_allocations;
}

static inline int iso_read16(void *userdata, uint32_t address, uint16_t *value) {
    iso_machine *machine = userdata;
    if (machine == NULL || value == NULL || (address & 1u) != 0u) return 0;
    iso_probe_reentry(machine);
    if (machine->fail_read != 0 && address == machine->fail_read_address) {
        machine->fail_read = 0;
        iso_record(machine, address, 0u, 0, 0);
        return 0;
    }
    if (address < ISO_ROM_SIZE && address + 1u < ISO_ROM_SIZE) {
        *value = (uint16_t)(((uint16_t)machine->rom[address] << 8) |
                            machine->rom[address + 1u]);
    } else if (address >= ISO_RAM_BASE &&
               address - ISO_RAM_BASE + 1u < ISO_RAM_SIZE) {
        size_t offset = (size_t)(address - ISO_RAM_BASE);
        *value = (uint16_t)(((uint16_t)machine->ram[offset] << 8) |
                            machine->ram[offset + 1u]);
    } else {
        iso_record(machine, address, 0u, 0, 0);
        return 0;
    }
    iso_record(machine, address, *value, 0, 1);
    return 1;
}

static inline int iso_write16(void *userdata, uint32_t address, uint16_t value) {
    iso_machine *machine = userdata;
    if (machine == NULL || (address & 1u) != 0u) return 0;
    iso_probe_reentry(machine);
    if ((machine->fail_write != 0 && address == machine->fail_write_address) ||
        address < ISO_RAM_BASE || address - ISO_RAM_BASE + 1u >= ISO_RAM_SIZE) {
        if (machine->fail_write != 0 && address == machine->fail_write_address) {
            machine->fail_write = 0;
        }
        iso_record(machine, address, value, 1, 0);
        return 0;
    }
    size_t offset = (size_t)(address - ISO_RAM_BASE);
    machine->ram[offset] = (uint8_t)(value >> 8);
    machine->ram[offset + 1u] = (uint8_t)value;
    iso_record(machine, address, value, 1, 1);
    return 1;
}

static inline int iso_machine_create_with_failure(iso_machine *machine, unsigned owner,
                                                  size_t fail_allocate_at) {
    if (machine == NULL || owner > 1u) return 0;
    memset(machine, 0, sizeof(*machine));
    machine->owner = owner;
    machine->fail_allocate_at = fail_allocate_at;
    guest_fixture(machine->rom, owner, 0);
    owned_cpu_bus bus = {machine, iso_read16, iso_write16};
    owned_cpu_allocator allocator = {machine, iso_allocate, iso_release};
    return owned_cpu_create(OWNED_CPU_MODEL_MC68000, bus, allocator,
                            &machine->cpu) == OWNED_CPU_OK;
}

static inline int iso_machine_create(iso_machine *machine, unsigned owner) {
    return iso_machine_create_with_failure(machine, owner, 0u);
}

static inline int iso_machine_reset(iso_machine *machine) {
    if (machine == NULL || machine->cpu == NULL) return 0;
    if (owned_cpu_reset(machine->cpu) != OWNED_CPU_OK) return 0;
    return owned_cpu_set_irq(machine->cpu, machine->owner + 1u) == OWNED_CPU_OK;
}

static inline void iso_machine_destroy(iso_machine *machine) {
    if (machine == NULL) return;
    owned_cpu_destroy(machine->cpu);
    machine->cpu = NULL;
}

static inline int iso_capture(iso_machine *machine, uint64_t budget,
                              iso_snapshot *snapshot) {
    if (machine == NULL || machine->cpu == NULL || snapshot == NULL) return 0;
    memset(snapshot, 0, sizeof(*snapshot));
    snapshot->run = owned_cpu_run(machine->cpu, budget);
    if (owned_cpu_observe(machine->cpu, &snapshot->cpu) != OWNED_CPU_OK) return 0;
    memcpy(snapshot->ram, machine->ram, sizeof(snapshot->ram));
    snapshot->event_count = machine->event_count;
    memcpy(snapshot->events, machine->events,
           snapshot->event_count * sizeof(snapshot->events[0]));
    return 1;
}

static inline int iso_boundary(iso_machine *machine, unsigned boundary,
                               iso_snapshot *snapshot) {
    if (boundary >= ISO_BOUNDARIES) return 0;
    uint64_t budget = boundary == 0u ? 0u : 1u;
    return iso_capture(machine, budget, snapshot);
}

static inline int iso_run_all(iso_machine *machine,
                              iso_snapshot snapshots[ISO_BOUNDARIES]) {
    if (!iso_machine_reset(machine)) return 0;
    for (unsigned boundary = 0u; boundary < ISO_BOUNDARIES; ++boundary) {
        if (!iso_boundary(machine, boundary, &snapshots[boundary])) return 0;
    }
    return 1;
}

static inline int iso_events_equal(const iso_snapshot *left,
                                   const iso_snapshot *right) {
    if (left->event_count != right->event_count) return 0;
    for (size_t index = 0u; index < left->event_count; ++index) {
        const iso_bus_event *a = &left->events[index];
        const iso_bus_event *b = &right->events[index];
        if (a->address != b->address || a->value != b->value ||
            a->write != b->write || a->succeeded != b->succeeded) return 0;
    }
    return 1;
}

static inline int iso_snapshots_equal(const iso_snapshot *left,
                                      const iso_snapshot *right) {
    return memcmp(&left->cpu, &right->cpu, sizeof(left->cpu)) == 0 &&
           memcmp(&left->run, &right->run, sizeof(left->run)) == 0 &&
           memcmp(left->ram, right->ram, sizeof(left->ram)) == 0 &&
           iso_events_equal(left, right);
}

static inline int iso_wait_at_cold_gate(iso_start_gate *gate) {
    if (pthread_mutex_lock(&gate->mutex) != 0) return 0;
    gate->ready++;
    (void)pthread_cond_broadcast(&gate->condition);
    while (gate->released == 0) {
        if (pthread_cond_wait(&gate->condition, &gate->mutex) != 0) {
            (void)pthread_mutex_unlock(&gate->mutex);
            return 0;
        }
    }
    (void)pthread_mutex_unlock(&gate->mutex);
    return 1;
}

static inline void *iso_thread_run(void *userdata) {
    iso_thread_case *test_case = userdata;
    if (test_case == NULL || test_case->gate == NULL ||
        !iso_wait_at_cold_gate(test_case->gate)) return NULL;
    if (!iso_machine_create(&test_case->machine, test_case->owner)) return NULL;
    test_case->succeeded = iso_run_all(&test_case->machine, test_case->snapshots);
    iso_machine_destroy(&test_case->machine);
    return NULL;
}

static inline int iso_run_cold_pair(iso_snapshot output[2][ISO_BOUNDARIES]) {
    iso_start_gate gate;
    memset(&gate, 0, sizeof(gate));
    iso_thread_case cases[2];
    pthread_t threads[2];
    memset(cases, 0, sizeof(cases));
    int created[2] = {0, 0};
    int mutex_initialized = 0;
    int condition_initialized = 0;
    if (pthread_mutex_init(&gate.mutex, NULL) != 0) goto cleanup;
    mutex_initialized = 1;
    if (pthread_cond_init(&gate.condition, NULL) != 0) goto cleanup;
    condition_initialized = 1;
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        cases[owner].gate = &gate;
        cases[owner].owner = owner;
        if (pthread_create(&threads[owner], NULL, iso_thread_run, &cases[owner]) != 0) {
            goto cleanup;
        }
        created[owner] = 1;
    }
    if (pthread_mutex_lock(&gate.mutex) != 0) goto cleanup;
    while (gate.ready < 2u) {
        if (pthread_cond_wait(&gate.condition, &gate.mutex) != 0) {
            (void)pthread_mutex_unlock(&gate.mutex);
            goto cleanup;
        }
    }
    gate.released = 1;
    (void)pthread_cond_broadcast(&gate.condition);
    (void)pthread_mutex_unlock(&gate.mutex);
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        if (pthread_join(threads[owner], NULL) != 0) goto cleanup;
        created[owner] = 0;
        if (!cases[owner].succeeded) goto cleanup;
        memcpy(output[owner], cases[owner].snapshots, sizeof(cases[owner].snapshots));
        if (cases[owner].machine.live_allocations != 0u) goto cleanup;
    }
    (void)pthread_cond_destroy(&gate.condition);
    (void)pthread_mutex_destroy(&gate.mutex);
    return 1;

cleanup:
    if (mutex_initialized != 0) {
        if (pthread_mutex_lock(&gate.mutex) == 0) {
            gate.released = 1;
            if (condition_initialized != 0) {
                (void)pthread_cond_broadcast(&gate.condition);
            }
            (void)pthread_mutex_unlock(&gate.mutex);
        }
    }
    for (unsigned owner = 0u; owner < 2u; ++owner) {
        if (created[owner] != 0) (void)pthread_join(threads[owner], NULL);
        iso_machine_destroy(&cases[owner].machine);
    }
    if (condition_initialized != 0) (void)pthread_cond_destroy(&gate.condition);
    if (mutex_initialized != 0) (void)pthread_mutex_destroy(&gate.mutex);
    return 0;
}

#endif
