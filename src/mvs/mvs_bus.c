/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint8_t *bytes;
    size_t size;
    gn_mvs_region_role role;
} gn_mvs_owned_region;

static const gn_mvs_owned_region *find_region(
    const gn_mvs_owned_region *regions, size_t count, gn_mvs_region_role role) {
    for (size_t index = 0u; index < count; ++index) {
        if (regions[index].role == role) return &regions[index];
    }
    return NULL;
}

int gn_mvs_bus_read16(const gn_mvs_owned_region *regions, size_t count,
                      uint8_t *work_ram, size_t work_ram_size,
                      uint32_t address, uint16_t *value) {
    if (regions == NULL || value == NULL || (address & UINT32_C(1)) != 0u) {
        return 0;
    }
    const gn_mvs_owned_region *bios = find_region(regions, count,
                                                  GN_MVS_REGION_BIOS);
    if (bios != NULL && address <= bios->size && bios->size - address >= 2u) {
        *value = (uint16_t)(((uint16_t)bios->bytes[address] << 8) |
                            bios->bytes[address + 1u]);
        return 1;
    }
    if (work_ram_size >= 2u && address >= UINT32_C(0x100000) &&
        (uint64_t)address - UINT32_C(0x100000) <= work_ram_size - 2u) {
        const size_t offset = (size_t)(address - UINT32_C(0x100000));
        *value = (uint16_t)(((uint16_t)work_ram[offset] << 8) |
                            work_ram[offset + 1u]);
        return 1;
    }
    const gn_mvs_owned_region *program = find_region(regions, count,
                                                     GN_MVS_REGION_PROGRAM);
    if (program != NULL && program->size >= 2u &&
        address >= UINT32_C(0x200000) &&
        (uint64_t)address - UINT32_C(0x200000) <= program->size - 2u) {
        const size_t offset = (size_t)(address - UINT32_C(0x200000));
        *value = (uint16_t)(((uint16_t)program->bytes[offset] << 8) |
                            program->bytes[offset + 1u]);
        return 1;
    }
    return 0;
}

int gn_mvs_bus_write16(uint8_t *work_ram, size_t work_ram_size,
                       uint32_t address, uint16_t value) {
    if (work_ram == NULL || (address & UINT32_C(1)) != 0u ||
        address < UINT32_C(0x100000) || work_ram_size < 2u ||
        (uint64_t)address - UINT32_C(0x100000) > work_ram_size - 2u) {
        return 0;
    }
    const size_t offset = (size_t)(address - UINT32_C(0x100000));
    work_ram[offset] = (uint8_t)(value >> 8);
    work_ram[offset + 1u] = (uint8_t)value;
    return 1;
}
