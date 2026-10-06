/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"

#include "cpu.h"

#include <stdlib.h>
#include <string.h>

#define GN_ROM_BASE UINT32_C(0)
#define GN_ROM_SIZE UINT32_C(512)
#define GN_RAM_BASE UINT32_C(0x1000)
#define GN_RAM_SIZE UINT32_C(0x1000)
#define GN_RAM_INIT_SIZE ((size_t)10)
#define GN_STACK_TOP UINT32_C(0x2000)

typedef struct {
    uint8_t *bytes;
    uint32_t base;
    uint32_t size;
} gn_memory_region;

typedef struct {
    gn_memory_region rom;
    gn_memory_region ram;
    uint8_t *ram_seed;
    size_t ram_seed_size;
    owned_cpu *cpu;
} gn_image;

struct gn_instance {
    gn_image *image;
};

static void *gn_cpu_allocate(void *userdata, size_t bytes) {
    (void)userdata;
    return malloc(bytes);
}

static void gn_cpu_release(void *userdata, void *allocation) {
    (void)userdata;
    free(allocation);
}

static int gn_read16(void *userdata, uint32_t address, uint16_t *value) {
    const gn_image *image = (const gn_image *)userdata;
    if (image == NULL || value == NULL || (address & UINT32_C(1)) != 0u) {
        return 0;
    }
    if (address >= image->rom.base &&
        address - image->rom.base <= image->rom.size - UINT32_C(2)) {
        const size_t offset = (size_t)(address - image->rom.base);
        *value = (uint16_t)(((uint16_t)image->rom.bytes[offset] << 8) |
                            (uint16_t)image->rom.bytes[offset + 1u]);
        return 1;
    }
    if (address >= image->ram.base &&
        address - image->ram.base <= image->ram.size - UINT32_C(2)) {
        const size_t offset = (size_t)(address - image->ram.base);
        *value = (uint16_t)(((uint16_t)image->ram.bytes[offset] << 8) |
                            (uint16_t)image->ram.bytes[offset + 1u]);
        return 1;
    }
    return 0;
}

static int gn_write16(void *userdata, uint32_t address, uint16_t value) {
    gn_image *image = (gn_image *)userdata;
    if (image == NULL || (address & UINT32_C(1)) != 0u ||
        address < image->ram.base ||
        address - image->ram.base > image->ram.size - UINT32_C(2)) {
        return 0;
    }
    const size_t offset = (size_t)(address - image->ram.base);
    image->ram.bytes[offset] = (uint8_t)(value >> 8);
    image->ram.bytes[offset + 1u] = (uint8_t)value;
    return 1;
}

static uint32_t gn_read32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static gn_status gn_validate_manifest(const gn_manifest *manifest,
                                      const gn_region **rom_out,
                                      const gn_region **ram_out) {
    if (manifest == NULL || rom_out == NULL || ram_out == NULL) {
        return GN_STATUS_INVALID_ARGUMENT;
    }
    *rom_out = NULL;
    *ram_out = NULL;
    if (manifest->profile != GN_PROFILE_DIAGNOSTIC) {
        return GN_STATUS_UNSUPPORTED_PROFILE;
    }
    if (manifest->version != GN_MANIFEST_VERSION ||
        manifest->region_count != GN_MAX_REGIONS) {
        return GN_STATUS_INVALID_MEDIA;
    }

    size_t total_bytes = 0u;
    for (size_t index = 0u; index < manifest->region_count; ++index) {
        const gn_region *region = &manifest->regions[index];
        if (region->source == NULL || region->source_size == 0u ||
            region->mapped_size == 0u ||
            region->guest_base > UINT32_MAX - region->mapped_size ||
            region->source_size > (size_t)region->mapped_size) {
            return GN_STATUS_INVALID_MEDIA;
        }
        if (region->source_size > GN_MAX_MEDIA_BYTES - total_bytes ||
            (size_t)region->mapped_size > GN_MAX_MEDIA_BYTES - total_bytes -
                                               region->source_size) {
            return GN_STATUS_INVALID_MEDIA;
        }
        total_bytes += region->source_size + (size_t)region->mapped_size;
        if (region->kind == GN_REGION_ROM) {
            if (*rom_out != NULL) return GN_STATUS_INVALID_MEDIA;
            *rom_out = region;
        } else if (region->kind == GN_REGION_RAM) {
            if (*ram_out != NULL) return GN_STATUS_INVALID_MEDIA;
            *ram_out = region;
        } else {
            return GN_STATUS_INVALID_MEDIA;
        }
    }

    const gn_region *rom = *rom_out;
    const gn_region *ram = *ram_out;
    if (rom == NULL || ram == NULL || rom->guest_base != GN_ROM_BASE ||
        rom->mapped_size != GN_ROM_SIZE || rom->source_size != GN_ROM_SIZE ||
        ram->guest_base != GN_RAM_BASE || ram->mapped_size != GN_RAM_SIZE ||
        ram->source_size != GN_RAM_INIT_SIZE) {
        return GN_STATUS_INVALID_MEDIA;
    }
    const uint32_t initial_ssp = gn_read32_be(rom->source);
    const uint32_t initial_pc = gn_read32_be(rom->source + 4u);
    if (initial_ssp != GN_STACK_TOP || (initial_pc & UINT32_C(1)) != 0u ||
        initial_pc >= GN_ROM_SIZE) {
        return GN_STATUS_INVALID_MEDIA;
    }
    return GN_STATUS_OK;
}

static void gn_free_image(gn_image *image) {
    if (image == NULL) return;
    owned_cpu_destroy(image->cpu);
    free(image->ram.bytes);
    free(image->ram_seed);
    free(image->rom.bytes);
    free(image);
}

static gn_status gn_initialize_candidate(gn_image *image) {
    memset(image->ram.bytes, 0, (size_t)image->ram.size);
    memcpy(image->ram.bytes, image->ram_seed, image->ram_seed_size);
    const owned_cpu_status status = owned_cpu_reset(image->cpu);
    return status == OWNED_CPU_OK ? GN_STATUS_OK : GN_STATUS_CPU_FAILURE;
}

GN_API gn_status gn_create(gn_instance **out_instance) {
    if (out_instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    *out_instance = NULL;
    gn_instance *instance = (gn_instance *)calloc(1u, sizeof(*instance));
    if (instance == NULL) return GN_STATUS_OUT_OF_MEMORY;
    *out_instance = instance;
    return GN_STATUS_OK;
}

GN_API gn_status gn_load(gn_instance *instance, const gn_manifest *manifest) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;

    const gn_region *rom = NULL;
    const gn_region *ram = NULL;
    gn_status status = gn_validate_manifest(manifest, &rom, &ram);
    if (status != GN_STATUS_OK) return status;

    gn_image *candidate = (gn_image *)calloc(1u, sizeof(*candidate));
    if (candidate == NULL) return GN_STATUS_OUT_OF_MEMORY;
    candidate->rom.base = rom->guest_base;
    candidate->rom.size = rom->mapped_size;
    candidate->ram.base = ram->guest_base;
    candidate->ram.size = ram->mapped_size;
    candidate->ram_seed_size = ram->source_size;
    candidate->rom.bytes = (uint8_t *)malloc(rom->source_size);
    candidate->ram_seed = (uint8_t *)malloc(ram->source_size);
    candidate->ram.bytes = (uint8_t *)malloc((size_t)ram->mapped_size);
    if (candidate->rom.bytes == NULL || candidate->ram_seed == NULL ||
        candidate->ram.bytes == NULL) {
        gn_free_image(candidate);
        return GN_STATUS_OUT_OF_MEMORY;
    }
    memcpy(candidate->rom.bytes, rom->source, rom->source_size);
    memcpy(candidate->ram_seed, ram->source, ram->source_size);
    memset(candidate->ram.bytes, 0, (size_t)candidate->ram.size);
    memcpy(candidate->ram.bytes, candidate->ram_seed, candidate->ram_seed_size);

    const owned_cpu_bus bus = {candidate, gn_read16, gn_write16};
    const owned_cpu_allocator allocator = {NULL, gn_cpu_allocate, gn_cpu_release};
    const owned_cpu_status cpu_status = owned_cpu_create(
        OWNED_CPU_MODEL_MC68000, bus, allocator, &candidate->cpu);
    if (cpu_status != OWNED_CPU_OK) {
        gn_free_image(candidate);
        return cpu_status == OWNED_CPU_ALLOCATION_FAILURE ? GN_STATUS_OUT_OF_MEMORY
                                                          : GN_STATUS_CPU_FAILURE;
    }
    status = gn_initialize_candidate(candidate);
    if (status != GN_STATUS_OK) {
        gn_free_image(candidate);
        return status;
    }

    gn_image *previous = instance->image;
    instance->image = candidate;
    gn_free_image(previous);
    return GN_STATUS_OK;
}

GN_API gn_status gn_reset(gn_instance *instance) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    return gn_initialize_candidate(instance->image);
}

GN_API gn_status gn_run(gn_instance *instance, uint64_t cycle_budget,
                        gn_run_result *out_result) {
    if (out_result == NULL) return GN_STATUS_INVALID_ARGUMENT;
    memset(out_result, 0, sizeof(*out_result));
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    if (cycle_budget > GN_MAX_CYCLE_BUDGET) return GN_STATUS_INVALID_ARGUMENT;

    const owned_cpu_run_result cpu_result =
        owned_cpu_run(instance->image->cpu, cycle_budget);
    out_result->requested_cycles = cpu_result.requested_cycles;
    out_result->elapsed_cycles = cpu_result.elapsed_cycles;
    out_result->overshoot_cycles = cpu_result.overshoot_cycles;
    out_result->instructions = cpu_result.instructions;
    out_result->boundary_pc = cpu_result.pc;
    out_result->fault_pc = cpu_result.fault_pc;
    out_result->instruction_register = cpu_result.instruction_register;
    if (cpu_result.reason == OWNED_CPU_STOPPED) {
        out_result->reason = GN_RUN_STOPPED;
        return GN_STATUS_OK;
    }
    if (cpu_result.reason == OWNED_CPU_BUDGET) {
        out_result->reason = GN_RUN_BUDGET;
        return GN_STATUS_OK;
    }
    if (cpu_result.reason == OWNED_CPU_HOST_FAULT ||
        cpu_result.reason == OWNED_CPU_ADDRESS_ERROR ||
        cpu_result.reason == OWNED_CPU_UNSUPPORTED_OPCODE ||
        cpu_result.reason == OWNED_CPU_PRIVILEGE_VIOLATION) {
        out_result->reason = GN_RUN_FAULT;
        return GN_STATUS_OK;
    }
    out_result->reason = GN_RUN_ERROR;
    return GN_STATUS_CPU_FAILURE;
}

GN_API gn_status gn_observe(const gn_instance *instance,
                            gn_observations *out_observations) {
    if (out_observations == NULL) return GN_STATUS_INVALID_ARGUMENT;
    memset(out_observations, 0, sizeof(*out_observations));
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;

    owned_cpu_observation cpu_observation;
    memset(&cpu_observation, 0, sizeof(cpu_observation));
    if (owned_cpu_observe(instance->image->cpu, &cpu_observation) != OWNED_CPU_OK) {
        return GN_STATUS_CPU_FAILURE;
    }
    const uint8_t *ram = instance->image->ram.bytes;
    out_observations->arithmetic_result = gn_read32_be(ram);
    out_observations->initialized_result = gn_read32_be(ram + 4u);
    out_observations->bss_result = gn_read32_be(ram + 16u);
    out_observations->ready = cpu_observation.stopped != 0u ? UINT8_C(1) : UINT8_C(0);
    return GN_STATUS_OK;
}

GN_API gn_status gn_unload(gn_instance *instance) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    gn_free_image(instance->image);
    instance->image = NULL;
    return GN_STATUS_OK;
}

GN_API void gn_destroy(gn_instance *instance) {
    if (instance == NULL) return;
    gn_free_image(instance->image);
    free(instance);
}

GN_API const char *gn_status_string(gn_status status) {
    switch (status) {
        case GN_STATUS_OK: return "ok";
        case GN_STATUS_INVALID_ARGUMENT: return "invalid argument";
        case GN_STATUS_INVALID_STATE: return "instance has no loaded media";
        case GN_STATUS_INVALID_MEDIA: return "invalid diagnostic media";
        case GN_STATUS_UNSUPPORTED_PROFILE: return "unsupported diagnostic profile";
        case GN_STATUS_OUT_OF_MEMORY: return "out of memory";
        case GN_STATUS_CPU_FAILURE: return "CPU backend failure";
        default: return "unknown status";
    }
}
