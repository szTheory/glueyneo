/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"

#include "cpu.h"
#include "sdk_private.h"

#include <stdlib.h>
#include <string.h>

#define GN_ROM_BASE UINT32_C(0)
#define GN_ROM_SIZE UINT32_C(512)
#define GN_RAM_BASE UINT32_C(0x1000)
#define GN_RAM_SIZE UINT32_C(0x1000)
#define GN_RAM_INIT_SIZE ((size_t)10)
#define GN_STACK_TOP UINT32_C(0x2000)
#define GN_FIXTURE_INPUT_PORT UINT32_C(0x00300000)
#define GN_FIXTURE_HEADER_SIZE 16u
#define GN_FIXTURE_ROM_SIZE 512u
#define GN_FIXTURE_RAM_INIT_SIZE 10u
#define GN_FIXTURE_TILE_SIZE 64u
#define GN_FIXTURE_PAYLOAD_SIZE (GN_FIXTURE_ROM_SIZE + GN_FIXTURE_RAM_INIT_SIZE + GN_FIXTURE_TILE_SIZE)
#define GN_FIXTURE_CONTENT_SIZE (GN_FIXTURE_HEADER_SIZE + GN_FIXTURE_PAYLOAD_SIZE)
#define GN_FIXTURE_FRAME_CYCLES UINT64_C(200000)
#define GN_FIXTURE_WIDTH UINT32_C(320)
#define GN_FIXTURE_HEIGHT UINT32_C(224)
#define GN_MVS_WATCHDOG_MAIN_CYCLES UINT64_C(1622015)
#define GN_MVS_SAVE_RAM_BYTES ((size_t)0x10000u)
#define GN_MVS_PALETTE_RAM_BYTES ((size_t)0x4000u)
#define GN_MVS_VIDEO_RAM_WORDS ((size_t)0x8800u)

static const uint8_t gn_fixture_guest_program[] = {
    0x30u, 0x39u, 0x00u, 0x30u, 0x00u, 0x00u,
    0x32u, 0x39u, 0x00u, 0x00u, 0x10u, 0x00u,
    0xd2u, 0x40u,
    0x33u, 0xc1u, 0x00u, 0x00u, 0x10u, 0x00u,
    0x4eu, 0x72u, 0x27u, 0x00u
};

typedef struct {
    void *userdata;
    void *(*allocate)(void *userdata, size_t bytes);
    void (*release)(void *userdata, void *allocation);
} gn_allocator;

typedef struct {
    uint8_t *bytes;
    uint32_t base;
    uint32_t size;
} gn_memory_region;

typedef struct {
    uint8_t *bytes;
    size_t size;
    gn_mvs_region_role role;
} gn_mvs_owned_region;

int gn_mvs_bus_read8(const gn_mvs_owned_region *regions, size_t count,
                     uint8_t *work_ram, size_t work_ram_size,
                     uint8_t *save_ram, size_t save_ram_size,
                     uint32_t address, uint8_t *value);
int gn_mvs_bus_read16(const gn_mvs_owned_region *regions, size_t count,
                      uint8_t *work_ram, size_t work_ram_size,
                      uint8_t *save_ram, size_t save_ram_size,
                      uint32_t address, uint16_t *value);
int gn_mvs_bus_write16(uint8_t *work_ram, size_t work_ram_size,
                       uint32_t address, uint16_t value);
int gn_mvs_bus_write8(uint8_t *work_ram, size_t work_ram_size,
                      uint32_t address, uint8_t value);

typedef struct {
    gn_allocator allocator;
    gn_memory_region rom;
    gn_memory_region ram;
    uint8_t *ram_seed;
    size_t ram_seed_size;
    uint32_t profile;
    uint16_t frame_input;
    uint8_t marker_tile[GN_FIXTURE_TILE_SIZE];
    gn_mvs_owned_region mvs_regions[GN_MVS_MAX_REGIONS];
    size_t mvs_region_count;
    uint8_t *mvs_work_ram;
    size_t mvs_work_ram_size;
    uint8_t *mvs_save_ram;
    size_t mvs_save_ram_size;
    uint8_t *mvs_palette_ram;
    size_t mvs_palette_ram_size;
    uint16_t *mvs_video_ram;
    size_t mvs_video_ram_words;
    uint32_t mvs_bus_fault_address;
    gn_mvs_bus_access mvs_bus_fault_access;
    uint8_t mvs_bus_fault_width;
    uint8_t mvs_bus_fault_valid;
    uint32_t mvs_mame_unmapped_write_count;
    uint32_t mvs_watchdog_pet_count;
    uint32_t mvs_watchdog_reset_count;
    uint16_t mvs_video_ram_offset;
    uint16_t mvs_video_ram_modulo;
    uint16_t mvs_video_ram_read_buffer;
    uint8_t mvs_video_auto_animation_speed;
    uint8_t mvs_video_auto_animation_disabled;
    uint8_t mvs_display_position_interrupt_control;
    uint8_t mvs_irq_pending_mask;
    uint8_t mvs_output_data;
    uint8_t mvs_output_latch;
    uint8_t mvs_use_cart_vectors;
    uint8_t mvs_cart_audio_selected;
    uint8_t mvs_coin_lockout_mask;
    uint8_t mvs_save_ram_unlocked;
    uint8_t mvs_palette_bank_selected;
    uint32_t mvs_watchdog_pet_generation;
    uint64_t mvs_watchdog_remaining_cycles;
    owned_cpu *cpu;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    size_t test_fail_bus_callbacks;
    size_t test_trace_count;
    size_t test_trace_dropped;
    gn_test_mutation test_mutation;
    gn_test_bus_event test_trace[GN_TEST_TRACE_CAPACITY];
#endif
} gn_image;

struct gn_instance {
    gn_allocator allocator;
    gn_image *image;
};

gn_status gn_private_mvs_fetch_trace(
    const gn_instance *instance, owned_cpu_fetch_trace_event *events,
    size_t capacity, size_t *out_count) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u) return GN_STATUS_INVALID_ARGUMENT;
    const owned_cpu_status status = owned_cpu_copy_fetch_trace(
        instance->image->cpu, events, capacity, out_count);
    return status == OWNED_CPU_OK ? GN_STATUS_OK : GN_STATUS_INVALID_ARGUMENT;
}

static void *gn_system_allocate(void *userdata, size_t bytes) {
    (void)userdata;
    return malloc(bytes);
}

static void gn_system_release(void *userdata, void *allocation) {
    (void)userdata;
    free(allocation);
}

static void *gn_allocate(const gn_allocator *allocator, size_t bytes) {
    return allocator->allocate(allocator->userdata, bytes);
}

static void gn_release(const gn_allocator *allocator, void *allocation) {
    if (allocation != NULL) allocator->release(allocator->userdata, allocation);
}

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
static void gn_test_record_bus_event(gn_image *image,
                                     gn_test_bus_direction direction,
                                     uint32_t address, uint16_t value) {
    if (image->test_trace_count == GN_TEST_TRACE_CAPACITY) {
        if (image->test_trace_dropped < SIZE_MAX) {
            ++image->test_trace_dropped;
        }
        return;
    }
    image->test_trace[image->test_trace_count++] = (gn_test_bus_event){
        address, value, UINT8_C(16), (uint8_t)direction};
}
#endif

static void *gn_cpu_allocate(void *userdata, size_t bytes) {
    const gn_image *image = (const gn_image *)userdata;
    return gn_allocate(&image->allocator, bytes);
}

static void gn_cpu_release(void *userdata, void *allocation) {
    const gn_image *image = (const gn_image *)userdata;
    gn_release(&image->allocator, allocation);
}

static void gn_record_mvs_bus_fault(gn_image *image, uint32_t address,
                                    gn_mvs_bus_access access, uint8_t width) {
    if (image->mvs_bus_fault_valid == 0u) {
        image->mvs_bus_fault_address = address;
        image->mvs_bus_fault_access = access;
        image->mvs_bus_fault_width = width;
        image->mvs_bus_fault_valid = 1u;
    }
}

static int gn_read16(void *userdata, uint32_t address, uint16_t *value) {
    gn_image *image = (gn_image *)userdata;
    if (image == NULL || value == NULL || (address & UINT32_C(1)) != 0u) {
        return 0;
    }
    if (image->mvs_region_count != 0u) {
        if (image->mvs_use_cart_vectors != 0u && address <= UINT32_C(0x7e)) {
            for (size_t index = 0u; index < image->mvs_region_count; ++index) {
                if (image->mvs_regions[index].role == GN_MVS_REGION_PROGRAM &&
                    image->mvs_regions[index].size >= UINT32_C(0x80)) {
                    const uint8_t *vectors = image->mvs_regions[index].bytes + address;
                    *value = (uint16_t)(((uint16_t)vectors[0] << 8) | vectors[1]);
                    return 1;
                }
            }
            gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_READ, 2u);
            return 0;
        }
        if ((address & UINT32_C(0x00fe0000)) == UINT32_C(0x003c0000)) {
            const uint32_t index = (address & UINT32_C(0x0000000e)) >> 1;
            if (index <= 1u) {
                *value = image->mvs_video_ram_read_buffer;
                return 1;
            }
            if (index == 2u) {
                *value = image->mvs_video_ram_modulo;
                return 1;
            }
            gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_READ, 2u);
            return 0;
        }
        if (address >= UINT32_C(0x400000) && address <= UINT32_C(0x7ffffe)) {
            const size_t bank_offset = image->mvs_palette_bank_selected != 0u
                ? (size_t)0x2000u : 0u;
            const size_t offset = bank_offset + (size_t)(address & UINT32_C(0x1ffe));
            *value = (uint16_t)(((uint16_t)image->mvs_palette_ram[offset] << 8) |
                                image->mvs_palette_ram[offset + 1u]);
            return 1;
        }
        const int success = gn_mvs_bus_read16(
            image->mvs_regions, image->mvs_region_count,
            image->mvs_work_ram, image->mvs_work_ram_size,
            image->mvs_save_ram, image->mvs_save_ram_size, address, value);
        if (!success) gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_READ, 2u);
        return success;
    }
    if (image->profile == GN_PROFILE_PUBLIC_FIXTURE &&
        address == GN_FIXTURE_INPUT_PORT) {
        *value = image->frame_input;
        return 1;
    }
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (image->test_fail_bus_callbacks != 0u) {
        --image->test_fail_bus_callbacks;
        return 0;
    }
#endif
    uint16_t observed = 0u;
    int found = 0;
    if (address >= image->rom.base &&
        address - image->rom.base <= image->rom.size - UINT32_C(2)) {
        const size_t offset = (size_t)(address - image->rom.base);
        observed = (uint16_t)(((uint16_t)image->rom.bytes[offset] << 8) |
                              (uint16_t)image->rom.bytes[offset + 1u]);
        found = 1;
    } else if (address >= image->ram.base &&
        address - image->ram.base <= image->ram.size - UINT32_C(2)) {
        const size_t offset = (size_t)(address - image->ram.base);
        observed = (uint16_t)(((uint16_t)image->ram.bytes[offset] << 8) |
                              (uint16_t)image->ram.bytes[offset + 1u]);
        found = 1;
    }
    if (found == 0) return 0;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (image->test_mutation == GN_TEST_MUTATION_BSS_READ &&
        address == UINT32_C(0x100a)) {
        observed = UINT16_C(1);
    }
#endif
    *value = observed;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    gn_test_record_bus_event(image, GN_TEST_BUS_READ, address, observed);
#endif
    return 1;
}

static int gn_read8(void *userdata, uint32_t address, uint8_t *value) {
    gn_image *image = (gn_image *)userdata;
    if (image == NULL || value == NULL) return 0;
    if (image->mvs_region_count != 0u) {
        if (address <= UINT32_C(0x7f)) {
            const gn_mvs_region_role role = image->mvs_use_cart_vectors != 0u
                ? GN_MVS_REGION_PROGRAM : GN_MVS_REGION_BIOS;
            for (size_t index = 0u; index < image->mvs_region_count; ++index) {
                if (image->mvs_regions[index].role == role &&
                    image->mvs_regions[index].size >= UINT32_C(0x80)) {
                    *value = image->mvs_regions[index].bytes[address];
                    return 1;
                }
            }
            gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_READ, 1u);
            return 0;
        }
        if (address >= UINT32_C(0x400000) && address <= UINT32_C(0x7fffff)) {
            const size_t bank_offset = image->mvs_palette_bank_selected != 0u
                ? (size_t)0x2000u : 0u;
            const size_t offset = bank_offset + (size_t)(address & UINT32_C(0x1fff));
            *value = image->mvs_palette_ram[offset];
            return 1;
        }
        const int success = gn_mvs_bus_read8(
            image->mvs_regions, image->mvs_region_count,
            image->mvs_work_ram, image->mvs_work_ram_size,
            image->mvs_save_ram, image->mvs_save_ram_size, address, value);
        if (!success) gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_READ, 1u);
        return success;
    }
    if (address >= image->rom.base && address - image->rom.base < image->rom.size) {
        *value = image->rom.bytes[(size_t)(address - image->rom.base)];
        return 1;
    }
    if (address >= image->ram.base && address - image->ram.base < image->ram.size) {
        *value = image->ram.bytes[(size_t)(address - image->ram.base)];
        return 1;
    }
    return 0;
}

static int gn_write16(void *userdata, uint32_t address, uint16_t value) {
    gn_image *image = (gn_image *)userdata;
    if (image == NULL || (address & UINT32_C(1)) != 0u) {
        return 0;
    }
    if (image->mvs_region_count != 0u) {
        /* Pinned MAME's video_register_w dispatches index 0 to VRAM offset,
         * index 1 to data write plus modulo increment, and index 2 to modulo.
         * The sprite generator storage/read-buffer state is local to this image;
         * rendering and physical-board equivalence are outside this model.
         * Source: neogeo_v.cpp, pinned revision 31e52312, lines 228-269;
         * neogeo_spr.cpp lines 78-108. */
        if ((address & UINT32_C(0x00fe0000)) == UINT32_C(0x003c0000)) {
            const uint32_t index = (address & UINT32_C(0x0000000e)) >> 1;
            if (index == 0u) {
                image->mvs_video_ram_offset =
                    (value & UINT16_C(0x8000)) != 0u
                        ? (uint16_t)(value & UINT16_C(0x87ff)) : value;
                image->mvs_video_ram_read_buffer =
                    image->mvs_video_ram[image->mvs_video_ram_offset];
                return 1;
            }
            if (index == 1u) {
                image->mvs_video_ram[image->mvs_video_ram_offset] = value;
                const uint16_t next_offset = (uint16_t)(
                    (image->mvs_video_ram_offset & UINT16_C(0x8000)) |
                    ((image->mvs_video_ram_offset + image->mvs_video_ram_modulo) &
                     UINT16_C(0x7fff)));
                image->mvs_video_ram_offset =
                    (next_offset & UINT16_C(0x8000)) != 0u
                        ? (uint16_t)(next_offset & UINT16_C(0x87ff)) : next_offset;
                image->mvs_video_ram_read_buffer =
                    image->mvs_video_ram[image->mvs_video_ram_offset];
                return 1;
            }
            if (index == 2u) {
                image->mvs_video_ram_modulo = value;
                return 1;
            }
            if (index == 3u) {
                /* MAME set_video_control: high byte controls animation speed,
                 * bit 3 disables auto animation, bits 4-7 set IRQ2 control. */
                image->mvs_video_auto_animation_speed = (uint8_t)(value >> 8);
                image->mvs_video_auto_animation_disabled =
                    (uint8_t)((value >> 3) & 1u);
                image->mvs_display_position_interrupt_control =
                    (uint8_t)(value & UINT16_C(0x00f0));
                return 1;
            }
            if (index == 6u) {
                /* Pinned MAME acknowledge_interrupt clears only these pending
                 * sources. This profile has no MVS IRQ producers, so the
                 * per-instance pending mask remains zero and IRQ recomputes low. */
                image->mvs_irq_pending_mask =
                    (uint8_t)(image->mvs_irq_pending_mask & (uint8_t)~(value & 7u));
                /* No IRQ sources are modeled, so the owned CPU is already at
                 * level zero; do not call its out-of-instruction setter here. */
                return 1;
            }
            gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_WRITE, 2u);
            return 0;
        }
        if (address >= UINT32_C(0x400000) && address <= UINT32_C(0x7ffffe)) {
            const size_t bank_offset = image->mvs_palette_bank_selected != 0u
                ? (size_t)0x2000u : 0u;
            const size_t offset = bank_offset + (size_t)(address & UINT32_C(0x1ffe));
            image->mvs_palette_ram[offset] = (uint8_t)(value >> 8);
            image->mvs_palette_ram[offset + 1u] = (uint8_t)value;
            return 1;
        }
        if (address >= UINT32_C(0xd00000) && address <= UINT32_C(0xd0fffe) +
                UINT32_C(0x0f0000)) {
            if (image->mvs_save_ram_unlocked != 0u) {
                const size_t offset = (size_t)(address & UINT32_C(0xffff));
                image->mvs_save_ram[offset] = (uint8_t)(value >> 8);
                image->mvs_save_ram[offset + 1u] = (uint8_t)value;
            }
            return 1;
        }
        const int success = gn_mvs_bus_write16(
            image->mvs_work_ram, image->mvs_work_ram_size, address, value);
        if (!success) gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_WRITE, 2u);
        return success;
    }
    if (address < image->ram.base ||
        address - image->ram.base > image->ram.size - UINT32_C(2)) return 0;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (image->test_fail_bus_callbacks != 0u) {
        --image->test_fail_bus_callbacks;
        return 0;
    }
#endif
    const size_t offset = (size_t)(address - image->ram.base);
    image->ram.bytes[offset] = (uint8_t)(value >> 8);
    image->ram.bytes[offset + 1u] = (uint8_t)value;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    gn_test_record_bus_event(image, GN_TEST_BUS_WRITE, address, value);
#endif
    return 1;
}

static int gn_write8(void *userdata, uint32_t address, uint8_t value) {
    gn_image *image = (gn_image *)userdata;
    if (image == NULL) return 0;
    if (image->mvs_region_count != 0u) {
        if ((address & ~UINT32_C(0x01fffe)) == UINT32_C(0x300001)) {
            if (image->mvs_watchdog_pet_count != UINT32_MAX)
                ++image->mvs_watchdog_pet_count;
            if (image->mvs_watchdog_pet_generation != UINT32_MAX)
                ++image->mvs_watchdog_pet_generation;
            image->mvs_watchdog_remaining_cycles = GN_MVS_WATCHDOG_MAIN_CYCLES;
            return 1;
        }
        const uint32_t latch_address = address & ~UINT32_C(0x01ffe0);
        if ((address & UINT32_C(1)) != 0u &&
            (latch_address & ~UINT32_C(0x1f)) == UINT32_C(0x3a0000)) {
            const uint32_t word_offset = (latch_address - UINT32_C(0x3a0000)) >> 1;
            if ((word_offset & UINT32_C(7)) == 1u) {
                /* Pinned MAME neogeo.cpp maps this addressable-latch output
                 * to set_use_cart_vectors. HC259 write_a3 takes output index
                 * from offset[2:0] and the data bit from offset[3], so the
                 * address selects state; the byte's data value is ignored. */
                image->mvs_use_cart_vectors = (uint8_t)((word_offset >> 3) & 1u);
                return 1;
            }
            if ((word_offset & UINT32_C(7)) == 5u) {
                /* The selected MAME output calls set_use_cart_audio, which
                 * switches fixed-layer source and the audio program bank.
                 * Only the per-instance select bit is represented here. */
                image->mvs_cart_audio_selected =
                    (uint8_t)((word_offset >> 3) & 1u);
                return 1;
            }
        }
        if ((address & UINT32_C(0x00fe0000)) == UINT32_C(0x00380000) &&
            (address & UINT32_C(1)) != 0u) {
            const uint32_t io_word_offset = (address & UINT32_C(0xff)) >> 1;
            switch (io_word_offset & UINT32_C(0x78)) {
            case UINT32_C(0x18):
                /* MAME mvs_state updates the latch; its base output_strobe and
                 * set_outputs virtuals are empty, so external outputs stay out. */
                image->mvs_output_latch = value;
                return 1;
            case UINT32_C(0x20):
                image->mvs_output_data = value;
                return 1;
            case UINT32_C(0x30):
            case UINT32_C(0x70):
                /* The pinned MVS map delegates these offsets to the arcade
                 * handler. Model only its two per-instance lockout bits, not
                 * physical coin hardware or counter output lines. */
                if ((io_word_offset & UINT32_C(2)) != 0u) {
                    const uint8_t channel_bit =
                        (uint8_t)(1u << (io_word_offset & UINT32_C(1)));
                    if ((io_word_offset & UINT32_C(0x40)) != 0u)
                        image->mvs_coin_lockout_mask =
                            (uint8_t)(image->mvs_coin_lockout_mask | channel_bit);
                    else
                        image->mvs_coin_lockout_mask =
                            (uint8_t)(image->mvs_coin_lockout_mask &
                                      (uint8_t)~channel_bit);
                    return 1;
                }
                break;
            default:
                break;
            }
        }
        if ((address & UINT32_C(1)) != 0u &&
            (latch_address & ~UINT32_C(0x1f)) == UINT32_C(0x3a0000)) {
            const uint32_t word_offset = (latch_address - UINT32_C(0x3a0000)) >> 1;
            if ((word_offset & UINT32_C(7)) == 6u) {
                /* Pinned MAME ngarcade_base_state::set_save_ram_unlock sets
                 * this gate; save_ram_w accepts writes only while enabled. */
                image->mvs_save_ram_unlocked = (uint8_t)((word_offset >> 3) & 1u);
                return 1;
            }
            if ((word_offset & UINT32_C(7)) == 7u) {
                /* Pinned MAME neogeo_base_state::set_palette_bank selects
                 * the palette bank and refreshes pens; rendering is not modeled. */
                image->mvs_palette_bank_selected = (uint8_t)((word_offset >> 3) & 1u);
                return 1;
            }
        }
        if (address >= UINT32_C(0x400000) && address <= UINT32_C(0x7fffff)) {
            const size_t bank_offset = image->mvs_palette_bank_selected != 0u
                ? (size_t)0x2000u : 0u;
            const size_t offset = bank_offset + (size_t)(address & UINT32_C(0x1fff));
            image->mvs_palette_ram[offset] = value;
            return 1;
        }
        if (address >= UINT32_C(0xd00000) && address <= UINT32_C(0xd0ffff) +
                UINT32_C(0x0f0000)) {
            if (image->mvs_save_ram_unlocked != 0u) {
                image->mvs_save_ram[(size_t)(address & UINT32_C(0xffff))] = value;
            }
            return 1;
        }
        if (address < UINT32_C(0x100000)) {
            /* MAME 31e52312 neogeo_main_map leaves this low gap unmapped
             * (only 0x000000-0x00007f has a vector read handler). Its pinned
             * default unmapped-write handler logs and drops writes. This is a
             * differential emulator behavior, not verified board behavior. */
            if (image->mvs_mame_unmapped_write_count != UINT32_MAX)
                ++image->mvs_mame_unmapped_write_count;
            return 1;
        }
        if (address >= UINT32_C(0x3e0000) && address <= UINT32_C(0x3fffff)) {
            /* Pinned MAME neogeo_base_map installs only an unmapped-read
             * handler over this range; byte writes reach MAME's default
             * dropped-write path. Keep this width-specific and differential. */
            if (image->mvs_mame_unmapped_write_count != UINT32_MAX)
                ++image->mvs_mame_unmapped_write_count;
            return 1;
        }
        const int success = gn_mvs_bus_write8(
            image->mvs_work_ram, image->mvs_work_ram_size, address, value);
        if (!success) gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_WRITE, 1u);
        return success;
    }
    if (address < image->ram.base || address - image->ram.base >= image->ram.size) return 0;
    image->ram.bytes[(size_t)(address - image->ram.base)] = value;
    return 1;
}

static uint32_t gn_read32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static uint16_t gn_read16_be(const uint8_t *bytes) {
    return (uint16_t)(((uint16_t)bytes[0] << 8) | (uint16_t)bytes[1]);
}

static gn_status gn_validate_region_layout(const gn_manifest *manifest) {
    if (manifest == NULL) {
        return GN_STATUS_INVALID_ARGUMENT;
    }
    if (manifest->version != GN_MANIFEST_VERSION ||
        manifest->region_count != GN_MAX_REGIONS) {
        return GN_STATUS_INVALID_MEDIA;
    }

    size_t total_bytes = 0u;
    uint64_t region_starts[GN_MAX_REGIONS];
    uint64_t region_ends[GN_MAX_REGIONS];
    int saw_rom = 0;
    int saw_ram = 0;
    for (size_t index = 0u; index < manifest->region_count; ++index) {
        const gn_region *region = &manifest->regions[index];
        if ((region->source == NULL && region->source_size != 0u) ||
            region->mapped_size == 0u ||
            region->source_size > (size_t)region->mapped_size) {
            return GN_STATUS_INVALID_MEDIA;
        }
        const uint64_t start = (uint64_t)region->guest_base;
        const uint64_t end = start + (uint64_t)region->mapped_size;
        if (end > (UINT64_C(1) << 32)) return GN_STATUS_INVALID_MEDIA;
        region_starts[index] = start;
        region_ends[index] = end;
        if (region->source_size > GN_MAX_MEDIA_BYTES - total_bytes) {
            return GN_STATUS_INVALID_MEDIA;
        }
        total_bytes += region->source_size;
        if ((size_t)region->mapped_size > GN_MAX_MEDIA_BYTES - total_bytes) {
            return GN_STATUS_INVALID_MEDIA;
        }
        total_bytes += (size_t)region->mapped_size;
        if (region->kind == GN_REGION_ROM) {
            if (saw_rom != 0) return GN_STATUS_INVALID_MEDIA;
            saw_rom = 1;
        } else if (region->kind == GN_REGION_RAM) {
            if (saw_ram != 0) return GN_STATUS_INVALID_MEDIA;
            saw_ram = 1;
        } else {
            return GN_STATUS_INVALID_MEDIA;
        }
    }
    if (saw_rom == 0 || saw_ram == 0) return GN_STATUS_INVALID_MEDIA;
    for (size_t left = 0u; left < manifest->region_count; ++left) {
        for (size_t right = left + 1u; right < manifest->region_count; ++right) {
            if (region_starts[left] < region_ends[right] &&
                region_starts[right] < region_ends[left]) {
                return GN_STATUS_INVALID_MEDIA;
            }
        }
    }
    return GN_STATUS_OK;
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
    const gn_status layout_status = gn_validate_region_layout(manifest);
    if (layout_status != GN_STATUS_OK) return layout_status;
    for (size_t index = 0u; index < manifest->region_count; ++index) {
        const gn_region *region = &manifest->regions[index];
        if (region->kind == GN_REGION_ROM) {
            *rom_out = region;
        } else {
            *ram_out = region;
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
        initial_pc > GN_ROM_SIZE - UINT32_C(2)) {
        return GN_STATUS_INVALID_MEDIA;
    }
    return GN_STATUS_OK;
}

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
gn_status gn_test_validate_region_layout(const gn_manifest *manifest) {
    return gn_validate_region_layout(manifest);
}

static uint64_t gn_digest_byte(uint64_t digest, uint8_t byte) {
    return (digest ^ byte) * UINT64_C(1099511628211);
}

static uint64_t gn_digest_bytes(uint64_t digest, const uint8_t *bytes,
                                size_t length) {
    for (size_t index = 0u; index < length; ++index) {
        digest = gn_digest_byte(digest, bytes[index]);
    }
    return digest;
}

static uint64_t gn_digest_u16(uint64_t digest, uint16_t value) {
    digest = gn_digest_byte(digest, (uint8_t)(value >> 8));
    return gn_digest_byte(digest, (uint8_t)value);
}

static uint64_t gn_digest_u32(uint64_t digest, uint32_t value) {
    digest = gn_digest_byte(digest, (uint8_t)(value >> 24));
    digest = gn_digest_byte(digest, (uint8_t)(value >> 16));
    digest = gn_digest_byte(digest, (uint8_t)(value >> 8));
    return gn_digest_byte(digest, (uint8_t)value);
}

static uint64_t gn_digest_u64(uint64_t digest, uint64_t value) {
    digest = gn_digest_u32(digest, (uint32_t)(value >> 32));
    return gn_digest_u32(digest, (uint32_t)value);
}

gn_status gn_test_image_digest(const gn_instance *instance, uint64_t *out_digest) {
    if (out_digest == NULL) return GN_STATUS_INVALID_ARGUMENT;
    *out_digest = 0u;
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;

    owned_cpu_state state;
    memset(&state, 0, sizeof(state));
    if (owned_cpu_capture_state(instance->image->cpu, &state) != OWNED_CPU_OK) {
        return GN_STATUS_CPU_FAILURE;
    }
    uint64_t digest = UINT64_C(14695981039346656037);
    const gn_image *image = instance->image;
    digest = gn_digest_u32(digest, image->rom.base);
    digest = gn_digest_u32(digest, image->rom.size);
    digest = gn_digest_bytes(digest, image->rom.bytes, image->rom.size);
    digest = gn_digest_u32(digest, image->ram.base);
    digest = gn_digest_u32(digest, image->ram.size);
    digest = gn_digest_u64(digest, image->ram_seed_size);
    digest = gn_digest_bytes(digest, image->ram_seed, image->ram_seed_size);
    digest = gn_digest_bytes(digest, image->ram.bytes, image->ram.size);
    digest = gn_digest_u32(digest, state.size);
    digest = gn_digest_u32(digest, state.version);
    digest = gn_digest_bytes(digest, (const uint8_t *)state.core_identity,
                             sizeof(state.core_identity));
    digest = gn_digest_u64(digest, state.present_fields);
    for (unsigned index = 0u; index < 8u; ++index) {
        digest = gn_digest_u32(digest, state.data_registers[index]);
    }
    for (unsigned index = 0u; index < 8u; ++index) {
        digest = gn_digest_u32(digest, state.address_registers[index]);
    }
    digest = gn_digest_u32(digest, state.pc);
    digest = gn_digest_u32(digest, state.previous_pc);
    digest = gn_digest_u32(digest, state.usp);
    digest = gn_digest_u32(digest, state.ssp);
    digest = gn_digest_u32(digest, state.fault_pc);
    digest = gn_digest_u16(digest, state.sr);
    digest = gn_digest_u16(digest, state.instruction_register);
    digest = gn_digest_byte(digest, state.stopped);
    digest = gn_digest_byte(digest, state.irq_level);
    digest = gn_digest_byte(digest, state.irq7_pending);
    digest = gn_digest_byte(digest, state.reset_pending);
    digest = gn_digest_byte(digest, state.last_exception_vector);
    digest = gn_digest_u64(digest, state.instructions);
    digest = gn_digest_u64(digest, state.instruction_cycles);
    digest = gn_digest_u64(digest, state.reset_cycles);
    digest = gn_digest_u64(digest, state.exception_cycles);
    digest = gn_digest_u64(digest, state.idle_cycles);
    digest = gn_digest_u64(digest, state.total_cycles);
    digest = gn_digest_u64(digest, state.reset_signal_events);
    *out_digest = digest;
    return GN_STATUS_OK;
}
#endif

static void gn_free_image(gn_image *image) {
    if (image == NULL) return;
    const gn_allocator allocator = image->allocator;
    owned_cpu_destroy(image->cpu);
    for (size_t index = 0u; index < image->mvs_region_count; ++index) {
        gn_release(&allocator, image->mvs_regions[index].bytes);
    }
    gn_release(&allocator, image->mvs_work_ram);
    gn_release(&allocator, image->mvs_save_ram);
    gn_release(&allocator, image->mvs_palette_ram);
    gn_release(&allocator, image->mvs_video_ram);
    gn_release(&allocator, image->ram.bytes);
    gn_release(&allocator, image->ram_seed);
    gn_release(&allocator, image->rom.bytes);
    gn_release(&allocator, image);
}

static gn_status gn_initialize_candidate(gn_image *image) {
    if (image->mvs_region_count != 0u) {
        memset(image->mvs_work_ram, 0, image->mvs_work_ram_size);
        image->mvs_bus_fault_address = 0u;
        image->mvs_bus_fault_access = (gn_mvs_bus_access)0;
        image->mvs_bus_fault_width = 0u;
        image->mvs_bus_fault_valid = 0u;
        image->mvs_mame_unmapped_write_count = 0u;
        image->mvs_watchdog_pet_count = 0u;
        image->mvs_watchdog_reset_count = 0u;
        image->mvs_video_auto_animation_speed = 0u;
        image->mvs_video_auto_animation_disabled = 0u;
        image->mvs_display_position_interrupt_control = 0u;
        image->mvs_irq_pending_mask = 0u;
        image->mvs_output_data = 0u;
        image->mvs_output_latch = 0u;
        image->mvs_use_cart_vectors = 0u;
        image->mvs_cart_audio_selected = 0u;
        image->mvs_coin_lockout_mask = 0u;
        image->mvs_save_ram_unlocked = 0u;
        image->mvs_palette_bank_selected = 0u;
        image->mvs_watchdog_pet_generation = 0u;
        image->mvs_watchdog_remaining_cycles = GN_MVS_WATCHDOG_MAIN_CYCLES;
        const owned_cpu_status mvs_status = owned_cpu_reset(image->cpu);
        return mvs_status == OWNED_CPU_OK ? GN_STATUS_OK : GN_STATUS_CPU_FAILURE;
    }
    memset(image->ram.bytes, 0, (size_t)image->ram.size);
    memcpy(image->ram.bytes, image->ram_seed, image->ram_seed_size);
    const owned_cpu_status status = owned_cpu_reset(image->cpu);
    return status == OWNED_CPU_OK ? GN_STATUS_OK : GN_STATUS_CPU_FAILURE;
}

static gn_status gn_create_with_allocator(gn_allocator allocator,
                                          gn_instance **out_instance) {
    if (out_instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    *out_instance = NULL;
    if (allocator.allocate == NULL || allocator.release == NULL) {
        return GN_STATUS_INVALID_ARGUMENT;
    }
    gn_instance *instance = (gn_instance *)gn_allocate(&allocator,
                                                        sizeof(*instance));
    if (instance == NULL) return GN_STATUS_OUT_OF_MEMORY;
    memset(instance, 0, sizeof(*instance));
    instance->allocator = allocator;
    *out_instance = instance;
    return GN_STATUS_OK;
}

GN_API gn_status gn_create(gn_instance **out_instance) {
    const gn_allocator allocator = {NULL, gn_system_allocate, gn_system_release};
    return gn_create_with_allocator(allocator, out_instance);
}

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
typedef union {
    /* malloc aligns the base; this union's stride preserves alignment for
     * every concrete payload allocated through this private test allocator.
     * The opaque CPU's concrete-member union is checked at its definition. */
    _Alignas(gn_instance) _Alignas(gn_image)
        _Alignas(owned_cpu_test_allocation_alignment) unsigned char alignment;
    size_t bytes;
} gn_test_allocation_header;

_Static_assert(_Alignof(gn_test_allocation_header) >= _Alignof(gn_instance),
               "test allocation header must preserve instance alignment");
_Static_assert(_Alignof(gn_test_allocation_header) >= _Alignof(gn_image),
               "test allocation header must preserve image alignment");
_Static_assert(_Alignof(gn_test_allocation_header) >=
                   _Alignof(owned_cpu_test_allocation_alignment),
               "test allocation header must preserve owned CPU alignment");

void gn_test_allocator_init(gn_test_allocator *allocator) {
    if (allocator == NULL) return;
    memset(allocator, 0, sizeof(*allocator));
}

void gn_test_allocator_arm(gn_test_allocator *allocator, size_t fail_at) {
    if (allocator == NULL) return;
    allocator->fail_at = fail_at;
    allocator->attempts = 0u;
}

void gn_test_allocator_disarm(gn_test_allocator *allocator) {
    if (allocator == NULL) return;
    allocator->fail_at = 0u;
}

static void *gn_test_allocate(void *userdata, size_t bytes) {
    gn_test_allocator *allocator = (gn_test_allocator *)userdata;
    if (allocator == NULL) return NULL;
    ++allocator->attempts;
    ++allocator->total_attempts;
    if (allocator->fail_at != 0u &&
        allocator->attempts == allocator->fail_at) {
        return NULL;
    }
    if (bytes > SIZE_MAX - sizeof(gn_test_allocation_header)) return NULL;
    gn_test_allocation_header *header =
        (gn_test_allocation_header *)malloc(sizeof(*header) + bytes);
    if (header == NULL) return NULL;
    header->bytes = bytes;
    ++allocator->live_allocations;
    allocator->live_bytes += bytes;
    return header + 1;
}

static void gn_test_release(void *userdata, void *allocation) {
    gn_test_allocator *allocator = (gn_test_allocator *)userdata;
    if (allocation == NULL) return;
    gn_test_allocation_header *header =
        ((gn_test_allocation_header *)allocation) - 1;
    if (allocator != NULL) {
        if (allocator->live_allocations > 0u) --allocator->live_allocations;
        if (allocator->live_bytes >= header->bytes) {
            allocator->live_bytes -= header->bytes;
        }
    }
    free(header);
}

gn_status gn_test_create(gn_test_allocator *test_allocator,
                         gn_instance **out_instance) {
    if (test_allocator == NULL) {
        if (out_instance != NULL) *out_instance = NULL;
        return GN_STATUS_INVALID_ARGUMENT;
    }
    const gn_allocator allocator = {test_allocator, gn_test_allocate,
                                    gn_test_release};
    return gn_create_with_allocator(allocator, out_instance);
}

gn_status gn_test_seed_counters(gn_instance *instance, uint64_t instructions,
                                uint64_t instruction_cycles,
                                uint64_t exception_cycles,
                                uint64_t idle_cycles, uint64_t total_cycles) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    const owned_cpu_status status = owned_cpu_test_seed_counters(
        instance->image->cpu, instructions, instruction_cycles,
        exception_cycles, idle_cycles, total_cycles);
    return status == OWNED_CPU_OK ? GN_STATUS_OK : GN_STATUS_CPU_FAILURE;
}

gn_status gn_test_fail_next_bus_callback(gn_instance *instance) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    instance->image->test_fail_bus_callbacks = 1u;
    return GN_STATUS_OK;
}

gn_status gn_test_set_mutation(gn_instance *instance, gn_test_mutation mutation) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    if (mutation < GN_TEST_MUTATION_NONE ||
        mutation > GN_TEST_MUTATION_TRACE_ORDER) {
        return GN_STATUS_INVALID_ARGUMENT;
    }
    instance->image->test_mutation = mutation;
    return GN_STATUS_OK;
}

gn_status gn_test_trace_clear(gn_instance *instance) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    instance->image->test_trace_count = 0u;
    instance->image->test_trace_dropped = 0u;
    return GN_STATUS_OK;
}

gn_status gn_test_trace_read(const gn_instance *instance,
                             gn_test_bus_event *events, size_t capacity,
                             size_t *out_count, size_t *out_dropped) {
    if (out_count == NULL || out_dropped == NULL) {
        return GN_STATUS_INVALID_ARGUMENT;
    }
    *out_count = 0u;
    *out_dropped = 0u;
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    const gn_image *image = instance->image;
    *out_count = image->test_trace_count;
    *out_dropped = image->test_trace_dropped;
    if (capacity < image->test_trace_count ||
        (events == NULL && image->test_trace_count != 0u)) {
        *out_count = 0u;
        *out_dropped = 0u;
        return GN_STATUS_INVALID_ARGUMENT;
    }
    if (image->test_trace_count != 0u) {
        memcpy(events, image->test_trace,
               image->test_trace_count * sizeof(image->test_trace[0]));
    }
    if (image->test_mutation == GN_TEST_MUTATION_TRACE_ORDER &&
        image->test_trace_count > 1u) {
        const gn_test_bus_event first = events[0];
        events[0] = events[1];
        events[1] = first;
    }
    return GN_STATUS_OK;
}

gn_status gn_test_mvs_read_work_ram(const gn_instance *instance,
                                    uint32_t address, uint16_t *out_value) {
    if (instance == NULL || out_value == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    if ((address & 1u) != 0u || address < UINT32_C(0x100000) ||
        (uint64_t)address - UINT32_C(0x100000) >
            instance->image->mvs_work_ram_size - 2u) return GN_STATUS_INVALID_ARGUMENT;
    const size_t offset = (size_t)(address - UINT32_C(0x100000));
    *out_value = (uint16_t)(((uint16_t)instance->image->mvs_work_ram[offset] << 8) |
                            instance->image->mvs_work_ram[offset + 1u]);
    return GN_STATUS_OK;
}

gn_status gn_test_mvs_read_bus(const gn_instance *instance,
                               uint32_t address, uint16_t *out_value) {
    if (instance == NULL || out_value == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    return gn_read16(instance->image, address, out_value)
        ? GN_STATUS_OK : GN_STATUS_INVALID_MEDIA;
}
#endif

GN_API gn_status gn_load(gn_instance *instance, const gn_manifest *manifest) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;

    gn_manifest normalized;
    const uint8_t *fixture_tile = NULL;
    const uint32_t loaded_profile = manifest == NULL ? 0u : manifest->profile;
    if (loaded_profile == GN_PROFILE_PUBLIC_FIXTURE) {
        if (manifest->version != GN_MANIFEST_VERSION || manifest->region_count != 1u) {
            return GN_STATUS_INVALID_MEDIA;
        }
        const gn_region *content = &manifest->regions[0];
        if (content->source == NULL || content->kind != GN_REGION_ROM ||
            content->guest_base != 0u || content->mapped_size != GN_FIXTURE_CONTENT_SIZE ||
            content->source_size != GN_FIXTURE_CONTENT_SIZE) {
            return GN_STATUS_INVALID_MEDIA;
        }
        const uint8_t *bytes = content->source;
        if (memcmp(bytes, "GNFX", 4u) != 0 || gn_read32_be(bytes + 4u) != 1u ||
            gn_read32_be(bytes + 8u) != GN_FIXTURE_PAYLOAD_SIZE ||
            gn_read32_be(bytes + 12u) != GN_FIXTURE_HEADER_SIZE) {
            return GN_STATUS_INVALID_MEDIA;
        }
        if (memcmp(bytes + GN_FIXTURE_HEADER_SIZE + 0x100u,
                   gn_fixture_guest_program, sizeof(gn_fixture_guest_program)) != 0) {
            return GN_STATUS_INVALID_MEDIA;
        }
        normalized.version = GN_MANIFEST_VERSION;
        normalized.profile = GN_PROFILE_DIAGNOSTIC;
        normalized.region_count = GN_MAX_REGIONS;
        normalized.regions[0] = (gn_region){0u, GN_ROM_SIZE,
            bytes + GN_FIXTURE_HEADER_SIZE, GN_FIXTURE_ROM_SIZE, GN_REGION_ROM};
        normalized.regions[1] = (gn_region){GN_RAM_BASE, GN_RAM_SIZE,
            bytes + GN_FIXTURE_HEADER_SIZE + GN_FIXTURE_ROM_SIZE,
            GN_FIXTURE_RAM_INIT_SIZE, GN_REGION_RAM};
        fixture_tile = bytes + GN_FIXTURE_HEADER_SIZE + GN_FIXTURE_ROM_SIZE +
                       GN_FIXTURE_RAM_INIT_SIZE;
        manifest = &normalized;
    }

    const gn_region *rom = NULL;
    const gn_region *ram = NULL;
    gn_status status = gn_validate_manifest(manifest, &rom, &ram);
    if (status != GN_STATUS_OK) return status;

    const gn_allocator allocator = instance->allocator;
    gn_image *candidate = (gn_image *)gn_allocate(&allocator,
                                                   sizeof(*candidate));
    if (candidate == NULL) return GN_STATUS_OUT_OF_MEMORY;
    memset(candidate, 0, sizeof(*candidate));
    candidate->allocator = allocator;
    candidate->profile = loaded_profile;
    candidate->rom.base = rom->guest_base;
    candidate->rom.size = rom->mapped_size;
    candidate->ram.base = ram->guest_base;
    candidate->ram.size = ram->mapped_size;
    candidate->ram_seed_size = ram->source_size;
    candidate->rom.bytes = (uint8_t *)gn_allocate(&allocator, rom->source_size);
    if (candidate->rom.bytes == NULL) {
        gn_free_image(candidate);
        return GN_STATUS_OUT_OF_MEMORY;
    }
    candidate->ram_seed = (uint8_t *)gn_allocate(&allocator, ram->source_size);
    if (candidate->ram_seed == NULL) {
        gn_free_image(candidate);
        return GN_STATUS_OUT_OF_MEMORY;
    }
    candidate->ram.bytes =
        (uint8_t *)gn_allocate(&allocator, (size_t)ram->mapped_size);
    if (candidate->ram.bytes == NULL) {
        gn_free_image(candidate);
        return GN_STATUS_OUT_OF_MEMORY;
    }
    memcpy(candidate->rom.bytes, rom->source, rom->source_size);
    memcpy(candidate->ram_seed, ram->source, ram->source_size);
    if (fixture_tile != NULL) {
        memcpy(candidate->marker_tile, fixture_tile, sizeof(candidate->marker_tile));
    }
    memset(candidate->ram.bytes, 0, (size_t)candidate->ram.size);
    memcpy(candidate->ram.bytes, candidate->ram_seed, candidate->ram_seed_size);

    const owned_cpu_bus bus = {candidate, gn_read16, gn_write16, gn_write8, gn_read8};
    const owned_cpu_allocator cpu_allocator = {candidate, gn_cpu_allocate,
                                                gn_cpu_release};
    const owned_cpu_status cpu_status = owned_cpu_create(
        OWNED_CPU_MODEL_MC68000, bus, cpu_allocator, &candidate->cpu);
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

GN_API gn_status gn_load_mvs(gn_instance *instance,
                             const gn_mvs_manifest *manifest) {
    if (instance == NULL || manifest == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (manifest->version != GN_MVS_MANIFEST_VERSION ||
        manifest->profile != GN_MVS_PROFILE_MSX) {
        return GN_STATUS_UNSUPPORTED_PROFILE;
    }
    if (manifest->region_count != GN_MVS_MAX_REGIONS) return GN_STATUS_INVALID_MEDIA;
    uint32_t roles = 0u;
    size_t total = 0u;
    static const size_t expected_sizes[GN_MVS_MAX_REGIONS] = {
        GN_MVS_BIOS_BYTES, GN_MVS_PROGRAM_BYTES, GN_MVS_FIXED_BYTES,
        GN_MVS_AUDIO_PROGRAM_BYTES, GN_MVS_SAMPLES_BYTES,
        GN_MVS_SPRITES_BYTES};
    for (size_t index = 0u; index < manifest->region_count; ++index) {
        const gn_mvs_region *region = &manifest->regions[index];
        if (region->role < GN_MVS_REGION_BIOS ||
            region->role > GN_MVS_REGION_SPRITES ||
            region->source == NULL || region->source_size == 0u ||
            region->source_size != region->mapped_size ||
            region->source_size != expected_sizes[(unsigned)region->role - 1u] ||
            region->source_size > GN_MVS_MAX_REGION_BYTES ||
            region->source_size > GN_MVS_MAX_MEDIA_BYTES - total ||
            (region->layout != GN_MVS_LAYOUT_LINEAR &&
             region->layout != GN_MVS_LAYOUT_WORD_SWAP) ||
            (region->layout == GN_MVS_LAYOUT_WORD_SWAP &&
             (region->source_size & 1u) != 0u)) {
            return GN_STATUS_INVALID_MEDIA;
        }
        const uint32_t bit = UINT32_C(1) << (unsigned)region->role;
        if ((roles & bit) != 0u) return GN_STATUS_INVALID_MEDIA;
        roles |= bit;
        total += region->source_size;
    }
    uint32_t expected_roles = 0u;
    for (unsigned role = GN_MVS_REGION_BIOS;
         role <= GN_MVS_REGION_SPRITES; ++role) {
        expected_roles |= UINT32_C(1) << role;
    }
    if (roles != expected_roles) return GN_STATUS_INVALID_MEDIA;

    const gn_allocator allocator = instance->allocator;
    gn_image *candidate = (gn_image *)gn_allocate(&allocator, sizeof(*candidate));
    if (candidate == NULL) return GN_STATUS_OUT_OF_MEMORY;
    memset(candidate, 0, sizeof(*candidate));
    candidate->allocator = allocator;
    candidate->profile = GN_MVS_PROFILE_MSX;
    candidate->mvs_region_count = manifest->region_count;
    candidate->mvs_work_ram_size = (size_t)0x10000u;
    candidate->mvs_work_ram = (uint8_t *)gn_allocate(
        &allocator, candidate->mvs_work_ram_size);
    candidate->mvs_save_ram_size = GN_MVS_SAVE_RAM_BYTES;
    candidate->mvs_save_ram = (uint8_t *)gn_allocate(
        &allocator, candidate->mvs_save_ram_size);
    candidate->mvs_palette_ram_size = GN_MVS_PALETTE_RAM_BYTES;
    candidate->mvs_palette_ram = (uint8_t *)gn_allocate(
        &allocator, candidate->mvs_palette_ram_size);
    candidate->mvs_video_ram_words = GN_MVS_VIDEO_RAM_WORDS;
    candidate->mvs_video_ram = (uint16_t *)gn_allocate(
        &allocator, candidate->mvs_video_ram_words * sizeof(*candidate->mvs_video_ram));
    if (candidate->mvs_work_ram == NULL || candidate->mvs_save_ram == NULL ||
        candidate->mvs_palette_ram == NULL || candidate->mvs_video_ram == NULL) {
        gn_free_image(candidate);
        return GN_STATUS_OUT_OF_MEMORY;
    }
    memset(candidate->mvs_save_ram, 0, candidate->mvs_save_ram_size);
    memset(candidate->mvs_video_ram, 0,
           candidate->mvs_video_ram_words * sizeof(*candidate->mvs_video_ram));
    memset(candidate->mvs_palette_ram, 0, candidate->mvs_palette_ram_size);
    for (size_t index = 0u; index < manifest->region_count; ++index) {
        const gn_mvs_region *source = &manifest->regions[index];
        gn_mvs_owned_region *destination = &candidate->mvs_regions[index];
        destination->bytes = (uint8_t *)gn_allocate(&allocator,
                                                    source->source_size);
        if (destination->bytes == NULL) {
            gn_free_image(candidate);
            return GN_STATUS_OUT_OF_MEMORY;
        }
        destination->size = source->source_size;
        destination->role = source->role;
        if (source->layout == GN_MVS_LAYOUT_LINEAR) {
            memcpy(destination->bytes, source->source, source->source_size);
        } else {
            for (size_t byte = 0u; byte < source->source_size; byte += 2u) {
                destination->bytes[byte] = source->source[byte + 1u];
                destination->bytes[byte + 1u] = source->source[byte];
            }
        }
    }
    const owned_cpu_bus bus = {candidate, gn_read16, gn_write16, gn_write8, gn_read8};
    const owned_cpu_allocator cpu_allocator = {candidate, gn_cpu_allocate,
                                                gn_cpu_release};
    const owned_cpu_status cpu_status = owned_cpu_create(
        OWNED_CPU_MODEL_MC68000, bus, cpu_allocator, &candidate->cpu);
    if (cpu_status != OWNED_CPU_OK) {
        gn_free_image(candidate);
        return cpu_status == OWNED_CPU_ALLOCATION_FAILURE ? GN_STATUS_OUT_OF_MEMORY
                                                          : GN_STATUS_CPU_FAILURE;
    }
    const gn_status status = gn_initialize_candidate(candidate);
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

static gn_status gn_run_cpu(gn_instance *instance, uint64_t cycle_budget,
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
    gn_status mapped_status;
    if (cpu_result.reason == OWNED_CPU_STOPPED) {
        out_result->reason = GN_RUN_STOPPED;
        mapped_status = GN_STATUS_OK;
    } else if (cpu_result.reason == OWNED_CPU_BUDGET) {
        out_result->reason = GN_RUN_BUDGET;
        mapped_status = GN_STATUS_OK;
    } else if (cpu_result.reason == OWNED_CPU_ADDRESS_ERROR ||
        cpu_result.reason == OWNED_CPU_UNSUPPORTED_OPCODE ||
        cpu_result.reason == OWNED_CPU_PRIVILEGE_VIOLATION) {
        out_result->reason = GN_RUN_FAULT;
        mapped_status = GN_STATUS_OK;
    } else {
        out_result->reason = GN_RUN_ERROR;
        mapped_status = GN_STATUS_CPU_FAILURE;
    }
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (mapped_status == GN_STATUS_OK) {
        switch (instance->image->test_mutation) {
            case GN_TEST_MUTATION_RUN_ELAPSED:
                ++out_result->elapsed_cycles;
                break;
            case GN_TEST_MUTATION_RUN_INSTRUCTIONS:
                ++out_result->instructions;
                break;
            case GN_TEST_MUTATION_RUN_STOP_REASON:
                if (out_result->reason == GN_RUN_STOPPED) {
                    out_result->reason = GN_RUN_BUDGET;
                }
                break;
            default:
                break;
        }
    }
#endif
    return mapped_status;
}

static gn_status gn_mvs_watchdog_soft_reset(gn_image *image) {
    const owned_cpu_status cpu_status = owned_cpu_reset(image->cpu);
    if (cpu_status != OWNED_CPU_OK) return GN_STATUS_CPU_FAILURE;
    image->mvs_bus_fault_address = 0u;
    image->mvs_bus_fault_access = (gn_mvs_bus_access)0;
    image->mvs_bus_fault_width = 0u;
    image->mvs_bus_fault_valid = 0u;
    image->mvs_watchdog_remaining_cycles = GN_MVS_WATCHDOG_MAIN_CYCLES;
    if (image->mvs_watchdog_reset_count != UINT32_MAX)
        ++image->mvs_watchdog_reset_count;
    return GN_STATUS_OK;
}

GN_API gn_status gn_run_mvs(gn_instance *instance, uint64_t cycle_budget,
                            gn_run_result *out_result) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u) {
        if (out_result != NULL) memset(out_result, 0, sizeof(*out_result));
        return GN_STATUS_INVALID_STATE;
    }
    if (out_result == NULL) return GN_STATUS_INVALID_ARGUMENT;
    memset(out_result, 0, sizeof(*out_result));
    out_result->requested_cycles = cycle_budget;
    if (cycle_budget > GN_MAX_CYCLE_BUDGET) return GN_STATUS_INVALID_ARGUMENT;
    if (cycle_budget == 0u) return gn_run_cpu(instance, 0u, out_result);

    uint64_t elapsed = 0u;
    uint64_t instructions = 0u;
    gn_run_reason final_reason = GN_RUN_BUDGET;
    while (elapsed < cycle_budget) {
        gn_image *image = instance->image;
        if (image->mvs_watchdog_remaining_cycles == 0u) {
            const gn_status reset_status = gn_mvs_watchdog_soft_reset(image);
            if (reset_status != GN_STATUS_OK) {
                out_result->reason = GN_RUN_ERROR;
                return reset_status;
            }
        }

        owned_cpu_observation cpu_observation;
        if (owned_cpu_observe(image->cpu, &cpu_observation) != OWNED_CPU_OK) {
            out_result->reason = GN_RUN_ERROR;
            return GN_STATUS_CPU_FAILURE;
        }
        uint64_t step_budget = 1u;
        if (cpu_observation.stopped != 0u && cpu_observation.irq_level == 0u &&
            cpu_observation.irq7_pending == 0u) {
            const uint64_t budget_left = cycle_budget - elapsed;
            step_budget = image->mvs_watchdog_remaining_cycles < budget_left
                ? image->mvs_watchdog_remaining_cycles : budget_left;
        }

        const uint32_t pet_generation = image->mvs_watchdog_pet_generation;
        gn_run_result step;
        const gn_status run_status = gn_run_cpu(instance, step_budget, &step);
        elapsed += step.elapsed_cycles;
        instructions += step.instructions;
        out_result->boundary_pc = step.boundary_pc;
        out_result->fault_pc = step.fault_pc;
        out_result->instruction_register = step.instruction_register;
        if (run_status != GN_STATUS_OK) {
            out_result->elapsed_cycles = elapsed;
            out_result->overshoot_cycles = elapsed > cycle_budget ? elapsed - cycle_budget : 0u;
            out_result->instructions = instructions;
            out_result->reason = step.reason;
            return run_status;
        }

        const int watchdog_petted =
            image->mvs_watchdog_pet_generation != pet_generation;
        int watchdog_reset = 0;
        if (watchdog_petted != 0) {
            /* The mapped register write is the final bus transfer for the
             * supported byte-store instruction, so the new period starts at
             * this instruction boundary. */
            image->mvs_watchdog_remaining_cycles = GN_MVS_WATCHDOG_MAIN_CYCLES;
        } else if (step.elapsed_cycles >= image->mvs_watchdog_remaining_cycles) {
            image->mvs_watchdog_remaining_cycles = 0u;
            const gn_status reset_status = gn_mvs_watchdog_soft_reset(image);
            if (reset_status != GN_STATUS_OK) {
                out_result->elapsed_cycles = elapsed;
                out_result->overshoot_cycles = elapsed > cycle_budget ? elapsed - cycle_budget : 0u;
                out_result->instructions = instructions;
                out_result->reason = GN_RUN_ERROR;
                return reset_status;
            }
            final_reason = GN_RUN_BUDGET;
            watchdog_reset = 1;
        } else {
            image->mvs_watchdog_remaining_cycles -= step.elapsed_cycles;
        }

        if (step.reason == GN_RUN_FAULT || step.reason == GN_RUN_ERROR) {
            final_reason = step.reason;
            break;
        }
        if (watchdog_reset == 0) final_reason = step.reason;
    }
    out_result->elapsed_cycles = elapsed;
    out_result->overshoot_cycles = elapsed > cycle_budget ? elapsed - cycle_budget : 0u;
    out_result->instructions = instructions;
    out_result->reason = final_reason;
    return GN_STATUS_OK;
}

GN_API gn_status gn_run(gn_instance *instance, uint64_t cycle_budget,
                        gn_run_result *out_result) {
    if (instance != NULL && instance->image != NULL &&
        instance->image->mvs_region_count != 0u) {
        return gn_run_mvs(instance, cycle_budget, out_result);
    }
    return gn_run_cpu(instance, cycle_budget, out_result);
}

GN_API gn_status gn_observe_mvs_bus_fault(
    const gn_instance *instance, gn_mvs_bus_fault_observation *out_observation,
    size_t out_observation_size) {
    if (out_observation == NULL) return GN_STATUS_INVALID_ARGUMENT;
    const size_t minimum_size = offsetof(gn_mvs_bus_fault_observation, valid) +
                                sizeof(out_observation->valid);
    if (out_observation_size < minimum_size) return GN_STATUS_INVALID_ARGUMENT;
    gn_mvs_bus_fault_observation current;
    memset(&current, 0, sizeof(current));
    current.version = GN_MVS_BUS_FAULT_OBSERVATION_VERSION;
    const size_t copy_size = out_observation_size < sizeof(current)
        ? out_observation_size : sizeof(current);
    if (instance == NULL) {
        memcpy(out_observation, &current, copy_size);
        return GN_STATUS_INVALID_ARGUMENT;
    }
    if (instance->image == NULL || instance->image->mvs_region_count == 0u) {
        memcpy(out_observation, &current, copy_size);
        return GN_STATUS_INVALID_STATE;
    }
    const gn_image *image = instance->image;
    current.valid = image->mvs_bus_fault_valid;
    current.address = image->mvs_bus_fault_address;
    current.access = image->mvs_bus_fault_access;
    current.width = image->mvs_bus_fault_width;
    current.mame_unmapped_write_count =
        image->mvs_mame_unmapped_write_count;
    current.mame_watchdog_pet_count = image->mvs_watchdog_pet_count;
    current.mame_watchdog_reset_count = image->mvs_watchdog_reset_count;
    current.video_ram_offset = image->mvs_video_ram_offset;
    current.video_ram_modulo = image->mvs_video_ram_modulo;
    current.video_auto_animation_speed =
        image->mvs_video_auto_animation_speed;
    current.video_auto_animation_disabled =
        image->mvs_video_auto_animation_disabled;
    current.display_position_interrupt_control =
        image->mvs_display_position_interrupt_control;
    current.mvs_output_data = image->mvs_output_data;
    current.mvs_output_latch = image->mvs_output_latch;
    current.mvs_cart_audio_selected = image->mvs_cart_audio_selected;
    current.mvs_coin_lockout_mask = image->mvs_coin_lockout_mask;
    current.mvs_save_ram_unlocked = image->mvs_save_ram_unlocked;
    current.mvs_palette_bank_selected = image->mvs_palette_bank_selected;
    memcpy(out_observation, &current, copy_size);
    return GN_STATUS_OK;
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
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (instance->image->test_mutation ==
        GN_TEST_MUTATION_OBSERVATION_BYTE_ORDER) {
        const uint32_t value = out_observations->arithmetic_result;
        out_observations->arithmetic_result =
            ((value & UINT32_C(0x000000ff)) << 24) |
            ((value & UINT32_C(0x0000ff00)) << 8) |
            ((value & UINT32_C(0x00ff0000)) >> 8) |
            ((value & UINT32_C(0xff000000)) >> 24);
    }
#endif
    return GN_STATUS_OK;
}

GN_API gn_status gn_advance_frame(gn_instance *instance,
                                  const gn_frame_request *request,
                                  gn_frame_result *out_result) {
    if (out_result == NULL || request == NULL) return GN_STATUS_INVALID_ARGUMENT;
    memset(out_result, 0, sizeof(*out_result));
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    gn_image *image = instance->image;
    if (image->profile != GN_PROFILE_PUBLIC_FIXTURE) return GN_STATUS_UNSUPPORTED_PROFILE;
    if ((request->input_mask & ~GN_INPUT_SUPPORTED_MASK) != 0u ||
        request->pixel_format != GN_PIXEL_XRGB8888 ||
        request->width != GN_FIXTURE_WIDTH || request->height != GN_FIXTURE_HEIGHT ||
        request->pixels == NULL ||
        (request->audio == NULL && request->audio_capacity_frames != 0u)) {
        return GN_STATUS_INVALID_ARGUMENT;
    }
    const size_t row_bytes = (size_t)GN_FIXTURE_WIDTH * sizeof(uint32_t);
    if (request->pitch_bytes < row_bytes ||
        request->pitch_bytes > (SIZE_MAX - row_bytes) / (GN_FIXTURE_HEIGHT - 1u)) {
        return GN_STATUS_INVALID_ARGUMENT;
    }
    const size_t required = request->pitch_bytes * (GN_FIXTURE_HEIGHT - 1u) + row_bytes;
    if (request->pixel_capacity_bytes < required) return GN_STATUS_INVALID_ARGUMENT;

    out_result->requested_cycles = GN_FIXTURE_FRAME_CYCLES;
    out_result->frame_time_denominator = UINT64_C(12000000);
    out_result->machine_clock_hz_numerator = UINT32_C(12000000);
    out_result->machine_clock_hz_denominator = 1u;
    out_result->audio_format = GN_AUDIO_S16_INTERLEAVED_STEREO;
    out_result->audio_sample_rate = UINT32_C(48000);
    out_result->audio_channels = 2u;
    out_result->audio_frames_produced = 0u;
    out_result->video_pixels_produced = 0u;

    image->frame_input = (request->input_mask & GN_INPUT_RIGHT) != 0u ? UINT16_C(1) : 0u;
    const owned_cpu_status reset_status = owned_cpu_reset(image->cpu);
    if (reset_status != OWNED_CPU_OK) {
        out_result->reason = GN_RUN_ERROR;
        return GN_STATUS_CPU_FAILURE;
    }
    const owned_cpu_run_result run = owned_cpu_run(image->cpu, GN_FIXTURE_FRAME_CYCLES);
    out_result->requested_cycles = run.requested_cycles;
    out_result->elapsed_cycles = run.elapsed_cycles;
    out_result->frame_time_numerator = run.elapsed_cycles;
    out_result->instructions = run.instructions;
    out_result->reason = run.reason == OWNED_CPU_STOPPED ? GN_RUN_STOPPED
                       : run.reason == OWNED_CPU_BUDGET ? GN_RUN_BUDGET
                       : run.reason == OWNED_CPU_ADDRESS_ERROR ||
                         run.reason == OWNED_CPU_UNSUPPORTED_OPCODE ||
                         run.reason == OWNED_CPU_PRIVILEGE_VIOLATION ? GN_RUN_FAULT
                       : GN_RUN_ERROR;
    if (run.reason != OWNED_CPU_STOPPED) return GN_STATUS_CPU_FAILURE;

    const uint32_t marker_x = gn_read16_be(image->ram.bytes);
    const uint32_t marker_y = gn_read16_be(image->ram.bytes + 2u);
    if (marker_x > GN_FIXTURE_WIDTH - 8u || marker_y > GN_FIXTURE_HEIGHT - 8u) {
        out_result->reason = GN_RUN_FAULT;
        return GN_STATUS_CPU_FAILURE;
    }
    for (uint32_t y = 0u; y < GN_FIXTURE_HEIGHT; ++y) {
        uint8_t *row = request->pixels + (size_t)y * request->pitch_bytes;
        for (uint32_t x = 0u; x < GN_FIXTURE_WIDTH; ++x) {
            uint32_t pixel = UINT32_C(0x00000000);
            if (x >= marker_x && x < marker_x + 8u &&
                y >= marker_y && y < marker_y + 8u &&
                image->marker_tile[(size_t)(y - marker_y) * 8u + (x - marker_x)] != 0u) {
                pixel = UINT32_C(0x00ffffff);
            }
            memcpy(row + (size_t)x * sizeof(pixel), &pixel, sizeof(pixel));
        }
    }
    out_result->video_pixels_produced = (size_t)GN_FIXTURE_WIDTH * GN_FIXTURE_HEIGHT;
    out_result->marker_x = marker_x;
    out_result->marker_y = marker_y;
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
    const gn_allocator allocator = instance->allocator;
    gn_free_image(instance->image);
    gn_release(&allocator, instance);
}

GN_API const char *gn_status_string(gn_status status) {
    switch (status) {
        case GN_STATUS_OK: return "ok";
        case GN_STATUS_INVALID_ARGUMENT: return "invalid argument";
        case GN_STATUS_INVALID_STATE: return "instance has no loaded media";
        case GN_STATUS_INVALID_MEDIA: return "invalid media contract";
        case GN_STATUS_UNSUPPORTED_PROFILE: return "unsupported media profile";
        case GN_STATUS_OUT_OF_MEMORY: return "out of memory";
        case GN_STATUS_CPU_FAILURE: return "CPU backend failure";
        default: return "unknown status";
    }
}
