/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"

#include "cpu.h"
#include "chips/ym2610_candidate.h"
#include "chips/z80_candidate.h"
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
/* Raster timing in 68000 clock periods (master clock / 2). Pinned MAME
 * 31e52312: neogeo_spr.h lines 10-15 give 0x180 pixels per line and 0x108
 * lines per frame with VBSTART 0xf0; neogeo.h lines 32-36 give a 24 MHz master
 * clock and a master/4 pixel clock; one line is therefore 384 * 4 = 1536 master
 * clocks = 768 CPU clocks. Evidence class: MAME-differential. */
#define GN_MVS_LINE_CYCLES UINT64_C(768)
#define GN_MVS_FRAME_LINES UINT64_C(264)
#define GN_MVS_FRAME_CYCLES (GN_MVS_LINE_CYCLES * GN_MVS_FRAME_LINES)
_Static_assert(GN_MVS_FRAME_CYCLES == GN_MVS_FRAME_BUDGET_CYCLES,
               "logical MVS frame budget must match raster constants");
#define GN_MVS_VBLANK_LINE UINT64_C(240)
/* Pinned MAME neogeo_spr.h defines VSSTART as 0x100; the sprite generator's
 * auto-animation timer runs once at that scanline each frame. */
#define GN_MVS_VIDEO_AUTO_ANIMATION_LINE UINT64_C(0x100)
#define GN_MVS_VIDEO_AUTO_ANIMATION_CYCLE \
    (GN_MVS_VIDEO_AUTO_ANIMATION_LINE * GN_MVS_LINE_CYCLES)
/* neogeo.h lines 38-40: /VBLANK falls 56 mclk after HSYNC on the VBSTART line
 * and the IRQ1 flip-flop sets 2 mclk later (58 mclk = 29 CPU clocks);
 * neogeo.cpp lines 851-860 and 871-875 schedule it at that point each frame. */
#define GN_MVS_VBLANK_IRQ_CYCLE \
    (GN_MVS_VBLANK_LINE * GN_MVS_LINE_CYCLES + UINT64_C(29))
/* neogeo.cpp lines 797-803 and 1555-1556: IRQ3 asserts line 3, the display
 * position interrupt asserts line 2 (m_raster_level) and VBlank line 1
 * (m_vblank_level). The pending-mask bits follow the $3C000C acknowledge
 * layout of neogeo.cpp lines 805-815: bit 0 IRQ3, bit 1 raster, bit 2 VBlank. */
#define GN_MVS_IRQ_BIT_IRQ3 UINT8_C(1)
#define GN_MVS_IRQ_BIT_RASTER UINT8_C(2)
#define GN_MVS_IRQ_BIT_VBLANK UINT8_C(4)
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

typedef struct {
    uint8_t scope[16];
    uint64_t load_generation;
    uint64_t restore_branch;
    uint64_t mutation_sequence;
    uint64_t export_sequence;
    gn_mvs_save_receipt_v1 latest_receipt;
    uint8_t scope_valid;
    uint8_t dirty;
    uint8_t baseline_known;
    uint8_t startup_import_allowed;
    uint8_t exhausted;
    uint8_t receipt_valid;
    uint8_t receipt_consumed;
} gn_mvs_save_ownership;

int gn_mvs_bus_read8(const gn_mvs_owned_region *regions, size_t count,
                     uint8_t *work_ram, size_t work_ram_size,
                     uint8_t *save_ram, size_t save_ram_size,
                     uint8_t program_bank,
                     uint32_t address, uint8_t *value);
int gn_mvs_bus_read16(const gn_mvs_owned_region *regions, size_t count,
                      uint8_t *work_ram, size_t work_ram_size,
                      uint8_t *save_ram, size_t save_ram_size,
                      uint8_t program_bank,
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
    uint8_t diagnostic_media_identity[32];
    uint8_t diagnostic_media_identity_valid;
    uint8_t mvs_media_identity[32];
    uint8_t mvs_media_identity_valid;
    size_t mvs_state_capacity;
    gn_instance *save_owner;
    uint8_t diagnostic_guest_faulted;
    uint16_t frame_input;
    uint32_t mvs_inputs;
    uint8_t marker_tile[GN_FIXTURE_TILE_SIZE];
    gn_mvs_owned_region mvs_regions[GN_MVS_V3_MAX_REGIONS];
    size_t mvs_region_count;
    uint8_t *mvs_work_ram;
    size_t mvs_work_ram_size;
    uint8_t *mvs_save_ram;
    size_t mvs_save_ram_size;
    uint8_t *mvs_palette_ram;
    size_t mvs_palette_ram_size;
    uint16_t *mvs_video_ram;
    size_t mvs_video_ram_words;
    uint16_t mvs_mslugx_command;
    uint16_t mvs_mslugx_counter;
    uint32_t mvs_bus_fault_address;
    gn_mvs_bus_access mvs_bus_fault_access;
    uint8_t mvs_bus_fault_width;
    uint8_t mvs_bus_fault_valid;
    uint8_t mvs_program_bank;
    uint32_t mvs_mame_unmapped_write_count;
    uint32_t mvs_watchdog_pet_count;
    uint32_t mvs_watchdog_reset_count;
    uint16_t mvs_video_ram_offset;
    uint16_t mvs_video_ram_modulo;
    uint16_t mvs_video_ram_read_buffer;
    uint8_t mvs_video_auto_animation_speed;
    uint8_t mvs_video_auto_animation_disabled;
    uint8_t mvs_video_auto_animation_counter;
    uint8_t mvs_video_auto_animation_frame_counter;
    uint8_t mvs_display_position_interrupt_control;
    uint8_t mvs_irq_pending_mask;
    /* Emulated position inside the current frame in CPU clocks, and the number
     * of VBlank interrupts raised; both are derived only from executed cycles. */
    uint32_t mvs_frame_cycle;
    uint64_t mvs_frame_cycle_carry;
    uint32_t mvs_frame_count;
    uint8_t mvs_output_data;
    uint8_t mvs_output_latch;
    uint8_t mvs_use_cart_vectors;
    uint8_t mvs_cart_audio_selected;
    uint8_t mvs_memcard_lock1;
    uint8_t mvs_memcard_unlock2;
    uint8_t mvs_coin_lockout_mask;
    uint8_t mvs_save_ram_unlocked;
    uint8_t mvs_palette_bank_selected;
    uint8_t mvs_screen_shadow;
    uint32_t mvs_watchdog_pet_generation;
    uint64_t mvs_watchdog_remaining_cycles;
    gn_mvs_calendar mvs_calendar;
    gn_mvs_sound mvs_sound;
    uint64_t mvs_sound_step_cycles;
    gn_mvs_failure mvs_failure;
    uint64_t mvs_completed_main_instructions;
    gn_mvs_protocol mvs_protocol;
    owned_cpu *cpu;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    size_t test_fail_bus_callbacks;
    size_t test_trace_count;
    size_t test_trace_dropped;
    gn_test_mutation test_mutation;
    gn_test_mvs_failure test_mvs_failure;
    gn_test_bus_event test_trace[GN_TEST_TRACE_CAPACITY];
#endif
} gn_image;

struct gn_instance {
    gn_allocator allocator;
    gn_image *image;
    gn_mvs_save_ownership mvs_save;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    gn_test_state_resources state_resources;
    uint8_t state_bypass_ym_irq_relation;
    uint8_t state_bypass_save_stale_clean;
#endif
#if defined(GLUEYNEO_SDK_TEST_HOOKS) && defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate_test_failpoint state_failpoint;
    uint8_t state_failpoint_active;
#endif
};

static void gn_mvs_save_load_committed(gn_instance *instance) {
    if (instance == NULL) return;
    gn_mvs_save_ownership *save = &instance->mvs_save;
    memset(&save->latest_receipt, 0, sizeof(save->latest_receipt));
    save->receipt_valid = 0u;
    save->receipt_consumed = 0u;
    save->dirty = 0u;
    save->baseline_known = 0u;
    save->startup_import_allowed = 1u;
    save->restore_branch = 0u;
    save->mutation_sequence = 0u;
    save->export_sequence = 0u;
    if (save->scope_valid != 0u) {
        if (save->load_generation == UINT64_MAX) {
            save->exhausted = 1u;
        } else {
            ++save->load_generation;
        }
    } else {
        save->load_generation = 0u;
        save->exhausted = 0u;
    }
}

static void gn_mvs_save_guest_mutation(gn_image *image) {
    if (image == NULL || image->save_owner == NULL) return;
    gn_mvs_save_ownership *save = &image->save_owner->mvs_save;
    save->dirty = 1u;
    if (save->mutation_sequence == UINT64_MAX) {
        save->exhausted = 1u;
        save->receipt_valid = 0u;
        save->receipt_consumed = 0u;
        memset(&save->latest_receipt, 0, sizeof(save->latest_receipt));
        return;
    }
    ++save->mutation_sequence;
}

static void gn_mvs_save_restore_committed(gn_image *image) {
    if (image == NULL || image->save_owner == NULL) return;
    gn_mvs_save_ownership *save = &image->save_owner->mvs_save;
    save->dirty = 1u;
    save->receipt_valid = 0u;
    save->receipt_consumed = 0u;
    memset(&save->latest_receipt, 0, sizeof(save->latest_receipt));
    if (save->restore_branch == UINT64_MAX) {
        save->exhausted = 1u;
        return;
    }
    ++save->restore_branch;
}

static void gn_mvs_save_close_startup(gn_image *image) {
    if (image != NULL && image->save_owner != NULL)
        image->save_owner->mvs_save.startup_import_allowed = 0u;
}

static gn_status gn_mvs_native_state_capacity(gn_image *image,
                                               size_t *out_capacity);

void gn_mvs_failure_clear(gn_mvs_failure *failure) {
    if (failure != NULL) memset(failure, 0, sizeof(*failure));
}

void gn_mvs_failure_record(gn_mvs_failure *failure,
                           gn_mvs_failure_component component,
                           gn_mvs_failure_stage stage,
                           gn_mvs_failure_reason reason) {
    if (failure == NULL || failure->valid != 0u ||
        component == GN_MVS_FAILURE_COMPONENT_NONE ||
        stage == GN_MVS_FAILURE_STAGE_NONE ||
        reason == GN_MVS_FAILURE_REASON_NONE) return;
    failure->component = component;
    failure->stage = stage;
    failure->reason = reason;
    failure->valid = 1u;
}

static gn_mvs_failure_site gn_mvs_failure_site_for(
    gn_mvs_failure_component component, gn_mvs_failure_stage stage) {
    if (component == GN_MVS_FAILURE_COMPONENT_MAIN_CPU) {
        if (stage == GN_MVS_FAILURE_STAGE_OBSERVE)
            return GN_MVS_FAILURE_SITE_MAIN_OBSERVE;
        if (stage == GN_MVS_FAILURE_STAGE_IRQ_UPDATE)
            return GN_MVS_FAILURE_SITE_MAIN_IRQ_UPDATE;
        if (stage == GN_MVS_FAILURE_STAGE_EXECUTE)
            return GN_MVS_FAILURE_SITE_MAIN_EXECUTION;
    }
    if (component == GN_MVS_FAILURE_COMPONENT_SOUND_CPU) {
        if (stage == GN_MVS_FAILURE_STAGE_SOUND_CATCHUP)
            return GN_MVS_FAILURE_SITE_SOUND_TICK;
    }
    if (component == GN_MVS_FAILURE_COMPONENT_BOARD &&
        stage == GN_MVS_FAILURE_STAGE_WATCHDOG_RESET)
        return GN_MVS_FAILURE_SITE_BOARD_WATCHDOG_RESET;
    if (component == GN_MVS_FAILURE_COMPONENT_INTERNAL &&
        stage == GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING)
        return GN_MVS_FAILURE_SITE_INTERNAL_TIMING;
    return GN_MVS_FAILURE_SITE_UNKNOWN;
}

static gn_mvs_failure_cause gn_mvs_failure_cause_for(
    gn_mvs_failure_component component, gn_mvs_failure_stage stage) {
    if (component == GN_MVS_FAILURE_COMPONENT_MAIN_CPU)
        return stage == GN_MVS_FAILURE_STAGE_BUS_ACCESS
            ? GN_MVS_FAILURE_CAUSE_MAIN_BUS_CALLBACK
            : GN_MVS_FAILURE_CAUSE_OWNED_CPU;
    if (component == GN_MVS_FAILURE_COMPONENT_SOUND_CPU)
        return stage == GN_MVS_FAILURE_STAGE_BUS_ACCESS
            ? GN_MVS_FAILURE_CAUSE_SOUND_BUS_CALLBACK
            : GN_MVS_FAILURE_CAUSE_Z80_TICK;
    if (component == GN_MVS_FAILURE_COMPONENT_BOARD)
        return GN_MVS_FAILURE_CAUSE_BOARD_RESET;
    if (component == GN_MVS_FAILURE_COMPONENT_INTERNAL)
        return GN_MVS_FAILURE_CAUSE_TIMING_ACCOUNTING;
    return GN_MVS_FAILURE_CAUSE_UNKNOWN;
}

static void gn_mvs_failure_record_image(gn_image *image,
                                        gn_mvs_failure_component component,
                                        gn_mvs_failure_stage stage,
                                        gn_mvs_failure_reason reason) {
    if (image == NULL || image->mvs_failure.valid != 0u) return;
    gn_mvs_failure_record(&image->mvs_failure, component, stage, reason);
    gn_mvs_failure *failure = &image->mvs_failure;
    if (failure->valid == 0u) return;
    failure->site = gn_mvs_failure_site_for(component, stage);
    failure->site_valid = (uint8_t)(failure->site != GN_MVS_FAILURE_SITE_UNKNOWN);
    failure->device_cause = gn_mvs_failure_cause_for(component, stage);
    failure->device_cause_valid = (uint8_t)(
        failure->device_cause != GN_MVS_FAILURE_CAUSE_UNKNOWN);
    failure->completed_main_instructions =
        image->mvs_completed_main_instructions;
    failure->instruction_boundary_valid = 1u;
    failure->capture_pending = image->mvs_protocol.guest_active;
    failure->guest_executed = (uint8_t)(
        image->mvs_completed_main_instructions != 0u);
    if (image->mvs_protocol.guest_active != 0u && image->cpu != NULL) {
        failure->pc = owned_cpu_current_instruction_pc(image->cpu);
        failure->pc_valid = 1u;
        return;
    }
    if (image->cpu != NULL) {
        owned_cpu_observation observation;
        if (owned_cpu_observe(image->cpu, &observation) == OWNED_CPU_OK) {
            failure->emulated_cycle = observation.total_cycles;
            failure->emulated_cycle_valid = 1u;
            failure->pc = observation.pc;
            failure->pc_valid = 1u;
        }
    }
}

static void gn_mvs_failure_capture_step(gn_image *image,
                                        const gn_run_result *step,
                                        uint32_t instruction_pc) {
    if (image == NULL || step == NULL || image->mvs_failure.valid == 0u ||
        image->mvs_failure.capture_pending == 0u) return;
    gn_mvs_failure *failure = &image->mvs_failure;
    failure->capture_pending = 0u;
    failure->completed_main_instructions = image->mvs_completed_main_instructions;
    failure->instruction_boundary_valid = 1u;
    failure->guest_executed = (uint8_t)(
        image->mvs_completed_main_instructions != 0u);
    owned_cpu_observation observation;
    if (image->cpu != NULL &&
        owned_cpu_observe(image->cpu, &observation) == OWNED_CPU_OK) {
        failure->emulated_cycle = observation.total_cycles;
        failure->emulated_cycle_valid = 1u;
    }
    if (failure->component == GN_MVS_FAILURE_COMPONENT_MAIN_CPU &&
        failure->stage == GN_MVS_FAILURE_STAGE_EXECUTE &&
        step->instructions != 0u) {
        failure->pc = instruction_pc;
        failure->pc_valid = 1u;
    }
    if (failure->opcode_valid == 0u && step->instructions != 0u) {
        failure->opcode = step->instruction_register;
        failure->opcode_valid = 1u;
    }
}

static gn_mvs_failure_status gn_mvs_failure_status_for_owned_cpu(
    owned_cpu_status status) {
    switch (status) {
        case OWNED_CPU_INVALID_ARGUMENT:
            return GN_MVS_FAILURE_STATUS_OWNED_CPU_INVALID_ARGUMENT;
        case OWNED_CPU_ALLOCATION_FAILURE:
            return GN_MVS_FAILURE_STATUS_OWNED_CPU_ALLOCATION_FAILURE;
        case OWNED_CPU_ADDRESS_ERROR:
            return GN_MVS_FAILURE_STATUS_OWNED_CPU_ADDRESS_ERROR;
        case OWNED_CPU_PRIVILEGE_VIOLATION:
            return GN_MVS_FAILURE_STATUS_OWNED_CPU_PRIVILEGE_VIOLATION;
        case OWNED_CPU_UNSUPPORTED_OPCODE:
            return GN_MVS_FAILURE_STATUS_OWNED_CPU_UNSUPPORTED_OPCODE;
        case OWNED_CPU_HOST_FAULT:
            return GN_MVS_FAILURE_STATUS_OWNED_CPU_HOST_FAULT;
        case OWNED_CPU_COUNTER_OVERFLOW:
            return GN_MVS_FAILURE_STATUS_OWNED_CPU_COUNTER_OVERFLOW;
        default:
            return GN_MVS_FAILURE_STATUS_UNKNOWN;
    }
}

static void gn_mvs_failure_set_owned_cpu_status(
    gn_image *image, owned_cpu_status status) {
    if (image == NULL || image->mvs_failure.valid == 0u) return;
    gn_mvs_failure *failure = &image->mvs_failure;
    if (failure->component != GN_MVS_FAILURE_COMPONENT_MAIN_CPU ||
        failure->stage != GN_MVS_FAILURE_STAGE_EXECUTE ||
        failure->device_cause != GN_MVS_FAILURE_CAUSE_OWNED_CPU ||
        failure->bus_access_valid != 0u)
        return;
    failure->underlying_status = gn_mvs_failure_status_for_owned_cpu(status);
    failure->underlying_status_valid = (uint8_t)(
        failure->underlying_status != GN_MVS_FAILURE_STATUS_UNKNOWN);
}

gn_status gn_private_mvs_fetch_trace(
    const gn_instance *instance, owned_cpu_fetch_trace_event *events,
    size_t capacity, size_t *out_count) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u) return GN_STATUS_INVALID_ARGUMENT;
    const owned_cpu_status status = owned_cpu_copy_fetch_trace(
        instance->image->cpu, events, capacity, out_count);
    return status == OWNED_CPU_OK ? GN_STATUS_OK : GN_STATUS_INVALID_ARGUMENT;
}

gn_status gn_private_mvs_protocol_trace(
    const gn_instance *instance, gn_mvs_protocol_event *events,
    size_t capacity, size_t *out_count, uint32_t *out_dropped) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u || out_count == NULL ||
        (events == NULL && capacity != 0u)) return GN_STATUS_INVALID_ARGUMENT;
    const gn_mvs_protocol *protocol = &instance->image->mvs_protocol;
    const size_t count = protocol->count < capacity ? protocol->count : capacity;
    if (count != 0u) memcpy(events, protocol->events, count * sizeof(*events));
    *out_count = count;
    if (out_dropped != NULL) *out_dropped = protocol->dropped;
    return GN_STATUS_OK;
}

gn_status gn_private_mvs_attract_verdict(const gn_instance *instance,
                                         gn_mvs_attract_verdict *out) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u || out == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    *out = gn_mvs_protocol_verdict(&instance->image->mvs_protocol);
    return GN_STATUS_OK;
}

gn_status gn_private_mvs_stall_diagnosis(const gn_instance *instance,
                                         gn_mvs_stall_diagnosis *out) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u || out == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    const gn_image *image = instance->image;
    gn_mvs_protocol_diagnose(&image->mvs_protocol, out);
    /* The last published BIOS variable values come from work RAM; they are
     * public protocol values, not program bytes. */
    const uint32_t variables[] = {GN_MVS_BIOS_SYSTEM_MODE, GN_MVS_BIOS_USER_REQUEST,
                                  GN_MVS_BIOS_USER_MODE};
    uint8_t values[3] = {0u, 0u, 0u};
    for (size_t index = 0u; index < 3u; ++index) {
        const size_t offset = (size_t)(variables[index] - UINT32_C(0x100000));
        if (image->mvs_work_ram != NULL && offset < image->mvs_work_ram_size)
            values[index] = image->mvs_work_ram[offset];
    }
    out->bios_system_mode = values[0];
    out->bios_user_request = values[1];
    out->bios_user_mode = values[2];
    return GN_STATUS_OK;
}

gn_status gn_private_mvs_failure(const gn_instance *instance,
                                 gn_mvs_failure *out) {
    if (out == NULL) return GN_STATUS_INVALID_ARGUMENT;
    gn_mvs_failure_clear(out);
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    const gn_image *image = instance->image;
    *out = image->mvs_failure;
    if (out->valid == 0u) {
        out->completed_main_instructions = image->mvs_completed_main_instructions;
        out->instruction_boundary_valid = 1u;
        out->guest_executed = (uint8_t)(
            image->mvs_completed_main_instructions != 0u);
    }
    return GN_STATUS_OK;
}

gn_status gn_private_mvs_sound_diagnostics_clear(gn_instance *instance) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u ||
        instance->image->mvs_sound.ym == NULL)
        return GN_STATUS_INVALID_STATE;
    return ym2610_candidate_diagnostics_clear(instance->image->mvs_sound.ym) ==
        YM2610_CANDIDATE_OK ? GN_STATUS_OK : GN_STATUS_INVALID_STATE;
}

gn_status gn_private_mvs_sound_observe(
    const gn_instance *instance, gn_mvs_sound_observation *out_observation) {
    if (out_observation == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u ||
        instance->image->mvs_sound.ym == NULL)
        return GN_STATUS_INVALID_STATE;
    ym2610_candidate_observation chip;
    if (ym2610_candidate_observe(instance->image->mvs_sound.ym, &chip) !=
        YM2610_CANDIDATE_OK)
        return GN_STATUS_INVALID_STATE;
    memset(out_observation, 0, sizeof(*out_observation));
    gn_mvs_sound_chip_observation *out = &out_observation->chip;
    out->version = chip.version;
    out->event_count = chip.event_count;
    out->event_dropped = chip.event_dropped;
    out->clocks = chip.clocks;
    out->register_writes = chip.register_writes;
    out->ssg_register_writes = chip.ssg_register_writes;
    out->ssg_volume_writes = chip.ssg_volume_writes;
    out->control_register_writes = chip.control_register_writes;
    out->fm_register_writes = chip.fm_register_writes;
    out->fm_key_on_writes = chip.fm_key_on_writes;
    out->fm_key_off_writes = chip.fm_key_off_writes;
    out->fm_frequency_writes = chip.fm_frequency_writes;
    out->fm_level_writes = chip.fm_level_writes;
    out->fm_pan_writes = chip.fm_pan_writes;
    out->adpcm_a_register_writes = chip.adpcm_a_register_writes;
    out->adpcm_a_control_writes = chip.adpcm_a_control_writes;
    out->adpcm_b_register_writes = chip.adpcm_b_register_writes;
    out->adpcm_b_control_writes = chip.adpcm_b_control_writes;
    out->adpcm_a_sample_reads = chip.adpcm_a_sample_reads;
    out->adpcm_b_sample_reads = chip.adpcm_b_sample_reads;
    out->timer_programs = chip.timer_programs;
    out->timer_expirations = chip.timer_expirations;
    out->irq_assertions = chip.irq_assertions;
    out->irq_deassertions = chip.irq_deassertions;
    out->native_frames = chip.native_frames;
    out->native_nonzero_frames = chip.native_nonzero_frames;
    out->native_stereo_nonzero_frames = chip.native_stereo_nonzero_frames;
    out->native_ssg_nonzero_frames = chip.native_ssg_nonzero_frames;
    out->native_peak = chip.native_peak;
    for (uint32_t index = 0u; index < chip.event_count; ++index) {
        out->events[index].clock = chip.events[index].clock;
        out->events[index].port = chip.events[index].port;
        out->events[index].bank = chip.events[index].bank;
        out->events[index].reg = chip.events[index].reg;
        out->events[index].value = chip.events[index].value;
        out->events[index].family = chip.events[index].family;
    }
    const gn_mvs_sound *sound = &instance->image->mvs_sound;
    gn_mvs_sound_board_observation *board = &out_observation->board;
    board->cart_selected = sound->cart_selected;
    board->command = sound->command;
    board->reply = sound->reply;
    board->command_pending = sound->command_pending;
    board->nmi_enabled = sound->nmi_enabled;
    board->ym_irq = sound->ym_irq;
    memcpy(board->banks, sound->banks, sizeof(board->banks));
    z80_candidate_snapshot sound_cpu;
    if (sound->cpu == NULL ||
        z80_candidate_capture(sound->cpu, &sound_cpu) != Z80_CANDIDATE_OK)
        return GN_STATUS_INVALID_STATE;
    board->sound_cpu_pc = sound_cpu.cpu.pc;
    board->sound_cpu_cycles = sound_cpu.cycles;
    return GN_STATUS_OK;
}

static void gn_mvs_failure_record_sound(gn_image *image,
                                        gn_mvs_failure_stage fallback_stage,
                                        gn_mvs_failure_reason fallback_reason) {
    const gn_mvs_failure_stage stage = image->mvs_sound.failure_stage != 0u
        ? (gn_mvs_failure_stage)image->mvs_sound.failure_stage : fallback_stage;
    const gn_mvs_failure_reason reason = image->mvs_sound.failure_reason != 0u
        ? (gn_mvs_failure_reason)image->mvs_sound.failure_reason : fallback_reason;
    const int is_first = image->mvs_failure.valid == 0u;
    gn_mvs_failure_record_image(image,
                                GN_MVS_FAILURE_COMPONENT_SOUND_CPU,
                                stage, reason);
    if (!is_first || image->mvs_failure.valid == 0u) return;
    gn_mvs_failure *failure = &image->mvs_failure;
    const uint8_t site = image->mvs_sound.failure_site;
    const uint8_t cause = image->mvs_sound.failure_cause;
    if (site > GN_MVS_FAILURE_SITE_UNKNOWN &&
        site <= GN_MVS_FAILURE_SITE_INTERNAL_TIMING) {
        failure->site = (gn_mvs_failure_site)site;
        failure->site_valid = 1u;
    }
    if (cause > GN_MVS_FAILURE_CAUSE_UNKNOWN &&
        cause <= GN_MVS_FAILURE_CAUSE_TIMING_ACCOUNTING) {
        failure->device_cause = (gn_mvs_failure_cause)cause;
        failure->device_cause_valid = 1u;
    }
    failure->underlying_status = image->mvs_sound.failure_status;
    failure->underlying_status_valid = (uint8_t)(
        failure->underlying_status > GN_MVS_FAILURE_STATUS_UNKNOWN &&
        failure->underlying_status <=
            GN_MVS_FAILURE_STATUS_OWNED_CPU_PRIVILEGE_VIOLATION);
    if (image->mvs_sound.failure_bus_valid != 0u &&
        image->mvs_sound.failure_operation <= GN_MVS_FAILURE_BUS_INTERRUPT_ACK &&
        image->mvs_sound.failure_width != 0u) {
        failure->operation = (gn_mvs_failure_bus_operation)
            image->mvs_sound.failure_operation;
        failure->bus_address = image->mvs_sound.failure_address;
        failure->bus_width = image->mvs_sound.failure_width;
        failure->bus_access_valid = 1u;
    }
}

static void gn_mvs_failure_record_main(gn_image *image,
                                       gn_mvs_failure_stage stage) {
    if (image->mvs_bus_fault_valid != 0u) {
        const int is_first = image->mvs_failure.valid == 0u;
        gn_mvs_failure_record_image(image,
                                    GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
                                    GN_MVS_FAILURE_STAGE_BUS_ACCESS,
                                    GN_MVS_FAILURE_REASON_BUS_FAILURE);
        if (is_first && image->mvs_failure.valid != 0u) {
            gn_mvs_failure *failure = &image->mvs_failure;
            failure->site = image->mvs_bus_fault_access == GN_MVS_BUS_ACCESS_READ
                ? GN_MVS_FAILURE_SITE_MAIN_BUS_READ
                : GN_MVS_FAILURE_SITE_MAIN_BUS_WRITE;
            failure->site_valid = 1u;
            failure->device_cause = GN_MVS_FAILURE_CAUSE_MAIN_BUS_CALLBACK;
            failure->device_cause_valid = 1u;
            failure->operation = image->mvs_bus_fault_access ==
                GN_MVS_BUS_ACCESS_READ ? GN_MVS_FAILURE_BUS_READ
                                       : GN_MVS_FAILURE_BUS_WRITE;
            failure->bus_address = image->mvs_bus_fault_address;
            failure->bus_width = image->mvs_bus_fault_width;
            failure->bus_access_valid = 1u;
        }
    } else {
        gn_mvs_failure_record_image(image,
                                    GN_MVS_FAILURE_COMPONENT_MAIN_CPU, stage,
                                    GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
    }
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
    if (access == GN_MVS_BUS_ACCESS_READ)
        gn_mvs_protocol_note_read_fault(&image->mvs_protocol);
    if (image->mvs_bus_fault_valid == 0u) {
        image->mvs_bus_fault_address = address;
        image->mvs_bus_fault_access = access;
        image->mvs_bus_fault_width = width;
        image->mvs_bus_fault_valid = 1u;
        const int is_first = image->mvs_failure.valid == 0u;
        gn_mvs_failure_record_image(image,
                                    GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
                                    GN_MVS_FAILURE_STAGE_BUS_ACCESS,
                                    GN_MVS_FAILURE_REASON_BUS_FAILURE);
        if (is_first && image->mvs_failure.valid != 0u) {
            gn_mvs_failure *failure = &image->mvs_failure;
            failure->site = access == GN_MVS_BUS_ACCESS_READ
                ? GN_MVS_FAILURE_SITE_MAIN_BUS_READ
                : GN_MVS_FAILURE_SITE_MAIN_BUS_WRITE;
            failure->site_valid = 1u;
            failure->device_cause = GN_MVS_FAILURE_CAUSE_MAIN_BUS_CALLBACK;
            failure->device_cause_valid = 1u;
            failure->operation = access == GN_MVS_BUS_ACCESS_READ
                ? GN_MVS_FAILURE_BUS_READ : GN_MVS_FAILURE_BUS_WRITE;
            failure->bus_address = address;
            failure->bus_width = width;
            failure->bus_access_valid = 1u;
        }
    }
}

/* Record a guest write that overlaps a documented BIOS RAM variable. The
 * executing instruction's PC (owned_cpu_current_instruction_pc, valid inside a
 * bus callback) classifies the writer. Host-side test hooks run outside
 * gn_run_mvs, where guest_active is clear, so they never record. */
static void gn_mvs_note_guest_write(gn_image *image, uint32_t address,
                                    unsigned width_bytes, uint16_t value) {
    if (image->mvs_protocol.guest_active == 0u ||
        address < GN_MVS_BIOS_SYSTEM_MODE || address > GN_MVS_BIOS_START_FLAG) return;
    gn_mvs_protocol_note_write(
        &image->mvs_protocol, address, width_bytes, value,
        gn_mvs_classify_pc(owned_cpu_current_instruction_pc(image->cpu)));
}

/* Hardware DIP switch register (plan 05-12). Address and the 0x01ff7e mirror
 * mask are in gn_read8 below; the default byte is the all-switches-off DSW. */
#define GN_MVS_REG_DIPSW_ADDRESS UINT32_C(0x300001)
#define GN_MVS_REG_DIPSW_DECODE_MASK UINT32_C(0x01ff7e)
#define GN_MVS_REG_DIPSW_DEFAULT UINT8_C(0xff)

/* Separate TEST input decode (sources S20c-S20d). The selected bounded
 * profile has no host input, so the service/test line is released. The
 * active-high unused bits and callback-free JAMMA sense line contribute zero;
 * the active-low released service bit contributes 0x80. This is the pinned
 * MAME input-port default, not a physical-board measurement. */
#define GN_MVS_REG_TEST_ADDRESS UINT32_C(0x300081)
#define GN_MVS_REG_TEST_DECODE_MASK UINT32_C(0x01ff7e)
#define GN_MVS_REG_TEST_IDLE UINT8_C(0x80)

/* MVS P1 controls occupy the high byte of the 0x300000 word; the low byte
 * remains REG_DIPSW. The upper word-address bits mirror A1-A16. */
#define GN_MVS_REG_P1_CONTROL_ADDRESS UINT32_C(0x300000)
#define GN_MVS_REG_P1_CONTROL_DECODE_MASK UINT32_C(0x01ff7e)
#define GN_MVS_REG_P1_CONTROL_IDLE UINT8_C(0xff)

/* MVS P2 controller input latch (MAME 31e52312 neogeo.cpp machine_start and
 * in1_edge_joy_r, plus joystick.cpp): the byte port is mirrored by A1-A16.
 * The empty host-input state returns 0xff on both byte lanes. */
#define GN_MVS_REG_P2_CONTROL_ADDRESS UINT32_C(0x340000)
#define GN_MVS_REG_P2_CONTROL_DECODE_MASK UINT32_C(0x01fffe)
#define GN_MVS_REG_P2_CONTROL_IDLE UINT8_C(0xff)

/* REG_STATUS_A (plan 05-22 rerun 13, docs/mvs-media.md "Input, status and
 * calendar", sources S22-S22j): low byte of AUDIO_COIN at $320000-$320001,
 * mirrored by 0x01fffe. The high byte is the source-mapped audio reply latch
 * (S25k-S25l). */
#define GN_MVS_REG_STATUS_A_ADDRESS UINT32_C(0x320001)
#define GN_MVS_REG_STATUS_A_DECODE_MASK UINT32_C(0x01fffe)
#define GN_MVS_REG_STATUS_A_IDLE UINT8_C(0x1f)
#define GN_MVS_REG_STATUS_A_TP_SHIFT 6u
#define GN_MVS_REG_STATUS_A_DATA_OUT_SHIFT 7u

/* REG_STATUS_B high byte (05-25, S23-S23i): the SYSTEM port mirrored by
 * 0x01fffe. Released start/select lines are high (low nibble 0x0f), absent
 * memory card returns 7 (bits 4-6), and the pinned MVS hardware-type bit is
 * 1 (bit 7). No input is pressed and no memory card is supplied in this
 * bounded profile. Low-byte and word reads remain unsupported. */
#define GN_MVS_REG_STATUS_B_ADDRESS UINT32_C(0x380000)
#define GN_MVS_REG_STATUS_B_DECODE_MASK UINT32_C(0x01fffe)
#define GN_MVS_REG_STATUS_B_IDLE UINT8_C(0xff)

static uint8_t gn_mvs_status_a_value(const gn_image *image) {
    uint8_t status = (uint8_t)(GN_MVS_REG_STATUS_A_IDLE |
        ((unsigned)(image->mvs_calendar.tp & 1u) << GN_MVS_REG_STATUS_A_TP_SHIFT) |
        ((unsigned)(image->mvs_calendar.data_out & 1u) <<
         GN_MVS_REG_STATUS_A_DATA_OUT_SHIFT));
    if ((image->mvs_inputs & GN_MVS_INPUT_COIN1) != 0u)
        status = (uint8_t)(status & (uint8_t)~GN_MVS_INPUT_COIN1);
    return status;
}

static uint8_t gn_mvs_status_b_value(const gn_image *image) {
    uint8_t status = GN_MVS_REG_STATUS_B_IDLE;
    if ((image->mvs_inputs & GN_MVS_INPUT_P1_START) != 0u)
        status = (uint8_t)(status & (uint8_t)~UINT8_C(0x01));
    return status;
}

/* ---- uPD4990A calendar (plan 05-21, docs/mvs-media.md "Input, status and
 * calendar", sources S21-S21k) ----------------------------------------------
 * The MVS io_control_w handler drives the chip's data_in (bit 0), clk (bit 1)
 * and stb (bit 2) lines from a byte write at $380051 (offset 0x28); cs, oe and
 * c0-c2 are held high at machine start, which selects the serial mode. The
 * chip's 32,768 Hz crystal is converted from executed 68000 clocks (12 MHz) as
 * 128/46875 chip ticks per clock with the integer remainder carried per
 * instance, so no host clock is read. Reference-emulator derived (pinned MAME
 * upd1990a.cpp); the physical phase of the sub-second divider is unverified.
 * The output pins are read through REG_STATUS_A at $320001 (plan 05-22
 * rerun 13). */
#define GN_MVS_CAL_TICK_NUMERATOR UINT64_C(128)
#define GN_MVS_CAL_TICK_DENOMINATOR UINT64_C(46875)
#define GN_MVS_CAL_SECOND_TICKS UINT32_C(32768)
#define GN_MVS_CAL_HALF_SECOND_TICKS UINT32_C(16384)
#define GN_MVS_CAL_DIVIDER_TICKS UINT32_C(64)
#define GN_MVS_CAL_WRITE_OFFSET UINT32_C(0x28)

enum {
    GN_CAL_REGISTER_HOLD = 0,
    GN_CAL_SHIFT = 1,
    GN_CAL_TIME_SET = 2,
    GN_CAL_TIME_READ = 3,
    GN_CAL_TP_64HZ = 4,
    GN_CAL_TP_60S_INT = 11,
    GN_CAL_INT_STOP_CLOCK = 14,
    GN_CAL_TEST = 15
};

static void gn_mvs_calendar_reset(gn_mvs_calendar *calendar) {
    static const uint8_t seed[sizeof(calendar->time_counter)] = GN_MVS_CALENDAR_EPOCH;
    memset(calendar, 0, sizeof(*calendar));
    memcpy(calendar->time_counter, seed, sizeof(seed));
    /* device_start arms the one-second time counter; the pulse timers stay
     * idle until a command selects them. */
    calendar->clock_running = 1u;
    calendar->clock_remaining = GN_MVS_CAL_SECOND_TICKS;
}

static unsigned gn_cal_bcd_value(uint8_t value) {
    return (unsigned)(value >> 4) * 10u + (unsigned)(value & 15u);
}

static uint8_t gn_cal_bcd_pack(unsigned value) {
    return (uint8_t)(((value / 10u) << 4) | (value % 10u));
}

/* dirtc.cpp advance_days with the uPD4990A features: no leap year, two-digit
 * year. The weekday nibble counts 0..6 here. */
static void gn_cal_advance_days(gn_mvs_calendar *calendar) {
    static const unsigned days_per_month[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    unsigned day = gn_cal_bcd_value(calendar->time_counter[3]) + 1u;
    unsigned month = (unsigned)(calendar->time_counter[4] >> 4);
    unsigned weekday = ((unsigned)(calendar->time_counter[4] & 15u) + 1u) % 7u;
    unsigned year = gn_cal_bcd_value(calendar->time_counter[5]);
    if (month > 0u && month <= 12u && day > days_per_month[month - 1u]) {
        day = 1u;
        ++month;
    }
    if (month == 13u) {
        month = 1u;
        year = (year + 1u) % 100u;
    }
    calendar->time_counter[3] = gn_cal_bcd_pack(day);
    calendar->time_counter[4] = (uint8_t)((month << 4) | weekday);
    calendar->time_counter[5] = gn_cal_bcd_pack(year);
}

/* dirtc.cpp advance_seconds, advance_minutes. */
static void gn_cal_advance_second(gn_mvs_calendar *calendar) {
    unsigned second = gn_cal_bcd_value(calendar->time_counter[0]) + 1u;
    if (second != 60u) {
        calendar->time_counter[0] = gn_cal_bcd_pack(second);
        return;
    }
    calendar->time_counter[0] = 0u;
    unsigned minute = gn_cal_bcd_value(calendar->time_counter[1]) + 1u;
    unsigned hour = gn_cal_bcd_value(calendar->time_counter[2]);
    if (minute == 60u) {
        minute = 0u;
        ++hour;
    }
    calendar->time_counter[1] = gn_cal_bcd_pack(minute);
    if (hour == 24u) {
        calendar->time_counter[2] = 0u;
        gn_cal_advance_days(calendar);
    } else {
        calendar->time_counter[2] = gn_cal_bcd_pack(hour);
    }
}

/* Timers armed with a zero delay fire before any more time passes. */
static void gn_cal_fire_due(gn_mvs_calendar *calendar) {
    for (;;) {
        int fired = 0;
        if (calendar->clock_running != 0u && calendar->clock_remaining == 0u) {
            gn_cal_advance_second(calendar);
            calendar->clock_remaining = GN_MVS_CAL_SECOND_TICKS;
            fired = 1;
        }
        if (calendar->data_out_running != 0u && calendar->data_out_remaining == 0u) {
            calendar->data_out = (uint8_t)(calendar->data_out ^ 1u);
            calendar->data_out_remaining = calendar->data_out_period;
            fired = 1;
        }
        if (calendar->tp_running != 0u && calendar->tp_remaining == 0u) {
            calendar->tp = (uint8_t)(calendar->tp ^ 1u);
            calendar->tp_remaining = calendar->tp_period;
            fired = 1;
        }
        if (fired == 0) return;
    }
}

static void gn_mvs_calendar_advance(gn_mvs_calendar *calendar, uint64_t cycles) {
    const uint64_t scaled = (uint64_t)calendar->tick_remainder +
                            cycles * GN_MVS_CAL_TICK_NUMERATOR;
    uint64_t ticks = scaled / GN_MVS_CAL_TICK_DENOMINATOR;
    calendar->tick_remainder = (uint32_t)(scaled % GN_MVS_CAL_TICK_DENOMINATOR);
    for (;;) {
        gn_cal_fire_due(calendar);
        if (ticks == 0u) return;
        if (calendar->clock_running == 0u && calendar->data_out_running == 0u &&
            calendar->tp_running == 0u) return;
        uint64_t step = ticks;
        if (calendar->clock_running != 0u && calendar->clock_remaining < step)
            step = calendar->clock_remaining;
        if (calendar->data_out_running != 0u && calendar->data_out_remaining < step)
            step = calendar->data_out_remaining;
        if (calendar->tp_running != 0u && calendar->tp_remaining < step)
            step = calendar->tp_remaining;
        if (calendar->clock_running != 0u) calendar->clock_remaining -= (uint32_t)step;
        if (calendar->data_out_running != 0u) calendar->data_out_remaining -= (uint32_t)step;
        if (calendar->tp_running != 0u) calendar->tp_remaining -= (uint32_t)step;
        ticks -= step;
    }
}

static void gn_cal_start_data_out(gn_mvs_calendar *calendar) {
    /* upd1990a.cpp: 2 x (clock / 32768) Hz toggling, first toggle at once. */
    calendar->data_out_period = GN_MVS_CAL_HALF_SECOND_TICKS;
    calendar->data_out_remaining = 0u;
    calendar->data_out_running = 1u;
}

static void gn_cal_start_tp(gn_mvs_calendar *calendar, uint32_t half_period_ticks) {
    calendar->tp_period = half_period_ticks;
    calendar->tp_remaining = 0u;
    calendar->tp_running = 1u;
}

/* upd1990a.cpp stb_w rising edge in serial mode: the command is the 4-bit
 * serial command register. Returns 0 for the TEST command, which is not
 * modeled, so the guest access is a recorded bus fault rather than a sink.
 * Commands 12-14 (interrupt output control) have no effect in the pinned
 * source either (marked TODO there). */
static int gn_cal_execute_command(gn_mvs_calendar *calendar) {
    const unsigned command = calendar->shift_reg[6];
    calendar->command = (uint8_t)command;
    if (command == GN_CAL_TEST) return 0;
    if (command == GN_CAL_REGISTER_HOLD ||
        (command >= GN_CAL_TP_64HZ && command <= GN_CAL_TP_60S_INT))
        calendar->clock_running = 1u;
    switch (command) {
    case GN_CAL_REGISTER_HOLD:
        gn_cal_start_data_out(calendar);
        gn_cal_start_tp(calendar, 256u);
        break;
    case GN_CAL_SHIFT:
        calendar->clock_running = 1u;
        calendar->data_out_running = 0u;
        calendar->data_out = (uint8_t)(calendar->shift_reg[0] & 1u);
        break;
    case GN_CAL_TIME_SET:
        calendar->clock_running = 0u;
        calendar->data_out_running = 0u;
        calendar->data_out = (uint8_t)(calendar->shift_reg[0] & 1u);
        memcpy(calendar->time_counter, calendar->shift_reg,
               sizeof(calendar->time_counter));
        /* The pinned source resets divider stages 10-15 here; keep only the
         * sub-64-tick phase. Unverified against hardware. */
        calendar->clock_remaining %= GN_MVS_CAL_DIVIDER_TICKS;
        break;
    case GN_CAL_TIME_READ:
        calendar->clock_running = 1u;
        memcpy(calendar->shift_reg, calendar->time_counter,
               sizeof(calendar->time_counter));
        gn_cal_start_data_out(calendar);
        break;
    case 4u: gn_cal_start_tp(calendar, 256u); break;   /* 64 Hz */
    case 5u: gn_cal_start_tp(calendar, 64u); break;    /* 256 Hz */
    case 6u: gn_cal_start_tp(calendar, 8u); break;     /* 2048 Hz */
    case 7u: gn_cal_start_tp(calendar, 4u); break;     /* 4096 Hz */
    case 8u: gn_cal_start_tp(calendar, GN_MVS_CAL_HALF_SECOND_TICKS); break;
    case 9u: gn_cal_start_tp(calendar, GN_MVS_CAL_HALF_SECOND_TICKS * 10u); break;
    case 10u: gn_cal_start_tp(calendar, GN_MVS_CAL_HALF_SECOND_TICKS * 30u); break;
    case 11u: gn_cal_start_tp(calendar, GN_MVS_CAL_HALF_SECOND_TICKS * 60u); break;
    default: break;
    }
    gn_cal_fire_due(calendar);
    return 1;
}

/* One byte written at $380051: data_in, clk, stb in that order. Returns 0 when
 * the strobe selects an unmodeled command. */
static int gn_mvs_calendar_write_lines(gn_mvs_calendar *calendar, uint8_t value) {
    const uint8_t clk = (uint8_t)((value >> 1) & 1u);
    const uint8_t stb = (uint8_t)((value >> 2) & 1u);
    int ok = 1;
    calendar->data_in = (uint8_t)(value & 1u);
    if (calendar->clk == 0u && clk != 0u) {
        const uint8_t shifted_out = (uint8_t)(calendar->shift_reg[6] & 1u);
        calendar->shift_reg[6] = (uint8_t)((calendar->shift_reg[6] >> 1) |
                                           (calendar->data_in << 3));
        if (calendar->command == GN_CAL_SHIFT) {
            for (unsigned index = 0u; index < 6u; ++index) {
                calendar->shift_reg[index] = (uint8_t)(calendar->shift_reg[index] >> 1);
                if (index == 5u)
                    calendar->shift_reg[index] |= (uint8_t)(shifted_out << 7);
                else
                    calendar->shift_reg[index] |=
                        (uint8_t)((calendar->shift_reg[index + 1u] << 7) & 0x80u);
            }
            calendar->data_out = (uint8_t)(calendar->shift_reg[0] & 1u);
        }
    }
    calendar->clk = clk;
    if (calendar->stb == 0u && stb != 0u) ok = gn_cal_execute_command(calendar);
    calendar->stb = stb;
    return ok;
}
/* ---- end uPD4990A calendar ---------------------------------------------- */

static int gn_mvs_sound_catch_up(gn_image *image) {
    if (image->mvs_protocol.guest_active == 0u) return 1;
    const uint64_t position = owned_cpu_current_bus_cycles(image->cpu);
    if (position < image->mvs_sound_step_cycles) {
        gn_mvs_failure_record_image(image,
                              GN_MVS_FAILURE_COMPONENT_INTERNAL,
                              GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING,
                              GN_MVS_FAILURE_REASON_ACCOUNTING_MISMATCH);
        return 0;
    }
    const gn_status status = gn_mvs_sound_advance(
        &image->mvs_sound, position - image->mvs_sound_step_cycles);
    image->mvs_sound_step_cycles = position;
    if (status != GN_STATUS_OK) {
        gn_mvs_failure_record_sound(image, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                                    GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
    }
    return status == GN_STATUS_OK;
}

static int gn_mvs_p2_control_decode(uint32_t address) {
    /* Drop the decoded mirror bits and the byte-lane bit. */
    return ((address & ~GN_MVS_REG_P2_CONTROL_DECODE_MASK) &
            ~UINT32_C(1)) == GN_MVS_REG_P2_CONTROL_ADDRESS;
}

static int gn_mvs_p1_control_decode(uint32_t address) {
    /* A0 selects P1's high byte versus the DIP low byte. */
    return (address & ~GN_MVS_REG_P1_CONTROL_DECODE_MASK) ==
           GN_MVS_REG_P1_CONTROL_ADDRESS;
}

static uint8_t gn_mvs_p1_control_value(const gn_image *image) {
    uint8_t value = GN_MVS_REG_P1_CONTROL_IDLE;
    if ((image->mvs_inputs & GN_MVS_INPUT_P1_UP) != 0u)
        value = (uint8_t)(value & (uint8_t)~UINT8_C(0x01));
    if ((image->mvs_inputs & GN_MVS_INPUT_P1_DOWN) != 0u)
        value = (uint8_t)(value & (uint8_t)~UINT8_C(0x02));
    if ((image->mvs_inputs & GN_MVS_INPUT_P1_LEFT) != 0u)
        value = (uint8_t)(value & (uint8_t)~UINT8_C(0x04));
    if ((image->mvs_inputs & GN_MVS_INPUT_P1_RIGHT) != 0u)
        value = (uint8_t)(value & (uint8_t)~UINT8_C(0x08));
    if ((image->mvs_inputs & GN_MVS_INPUT_P1_A) != 0u)
        value = (uint8_t)(value & (uint8_t)~UINT8_C(0x10));
    if ((image->mvs_inputs & GN_MVS_INPUT_P1_B) != 0u)
        value = (uint8_t)(value & (uint8_t)~UINT8_C(0x20));
    if ((image->mvs_inputs & GN_MVS_INPUT_P1_C) != 0u)
        value = (uint8_t)(value & (uint8_t)~UINT8_C(0x40));
    if ((image->mvs_inputs & GN_MVS_INPUT_P1_D) != 0u)
        value = (uint8_t)(value & (uint8_t)~UINT8_C(0x80));
    return value;
}

static int gn_mvs_mslugx_protection_decode(uint32_t address) {
    return address >= UINT32_C(0x2fffe0) &&
           address <= UINT32_C(0x2fffef);
}

static int gn_mvs_mslugx_table_bit(gn_image *image, uint16_t select,
                                   uint8_t *bit) {
    const uint32_t table_address = UINT32_C(0x0dedd2) +
        (uint32_t)((select >> 3) & UINT16_C(0x0fff));
    uint8_t table_byte = 0u;
    if (!gn_mvs_bus_read8(image->mvs_regions, image->mvs_region_count,
                          image->mvs_work_ram, image->mvs_work_ram_size,
                          image->mvs_save_ram, image->mvs_save_ram_size,
                          image->mvs_program_bank, table_address, &table_byte)) {
        return 0;
    }
    *bit = (uint8_t)((table_byte >> ((uint16_t)~select & UINT16_C(7))) & 1u);
    return 1;
}

static int gn_mvs_mslugx_protection_read(gn_image *image, uint32_t address,
                                         uint16_t *value) {
    (void)address;
    if (image->mvs_mslugx_command == UINT16_C(1)) {
        uint8_t bit = 0u;
        if (!gn_mvs_mslugx_table_bit(image, image->mvs_mslugx_counter, &bit)) {
            return 0;
        }
        ++image->mvs_mslugx_counter;
        *value = bit;
        return 1;
    }
    if (image->mvs_mslugx_command == UINT16_C(0x0fff)) {
        uint16_t selected_word = 0u;
        if (!gn_mvs_bus_read16(image->mvs_regions, image->mvs_region_count,
                               image->mvs_work_ram, image->mvs_work_ram_size,
                               image->mvs_save_ram, image->mvs_save_ram_size,
                               image->mvs_program_bank, UINT32_C(0x10f00a),
                               &selected_word)) {
            return 0;
        }
        /* MAME subtracts one into int32_t then right-shifts. Truncating the
         * subtraction to 16 bits reproduces the mapped low 16-bit index,
         * including select=0 -> 0xffff, without signed-shift behavior. */
        const uint16_t select = (uint16_t)(selected_word - UINT16_C(1));
        uint8_t bit = 0u;
        if (!gn_mvs_mslugx_table_bit(image, select, &bit)) return 0;
        *value = bit;
        return 1;
    }
    *value = 0u;
    return 1;
}

static int gn_mvs_mslugx_protection_write(gn_image *image, uint32_t address,
                                          uint16_t value) {
    switch (address - UINT32_C(0x2fffe0)) {
    case UINT32_C(0x0):
        image->mvs_mslugx_command = 0u;
        break;
    case UINT32_C(0x2):
    case UINT32_C(0x4):
        image->mvs_mslugx_command |= value;
        break;
    case UINT32_C(0xa):
        image->mvs_mslugx_command = 0u;
        image->mvs_mslugx_counter = 0u;
        break;
    default:
        /* The pinned MAME handler ignores offsets 0x6 and other writes. */
        break;
    }
    return 1;
}

static int gn_read16(void *userdata, uint32_t address, uint16_t *value) {
    gn_image *image = (gn_image *)userdata;
    if (image == NULL || value == NULL || (address & UINT32_C(1)) != 0u) {
        return 0;
    }
    if (image->mvs_region_count != 0u) {
        gn_mvs_protocol_note_read(&image->mvs_protocol, address);
        if (gn_mvs_mslugx_protection_decode(address)) {
            if (!gn_mvs_mslugx_protection_read(image, address, value)) {
                gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_READ, 2u);
                return 0;
            }
            return 1;
        }
        if (gn_mvs_p1_control_decode(address)) {
            /* MAME ngarcade_base_state::in0_edge_joy_r combines P1's
             * active-low control byte with REG_DIPSW in the low byte. */
            *value = (uint16_t)(((uint16_t)gn_mvs_p1_control_value(image) << 8) |
                                GN_MVS_REG_DIPSW_DEFAULT);
            return 1;
        }
        if (gn_mvs_p2_control_decode(address)) {
            /* MAME ngarcade_base_state::in1_edge_joy_r returns the P2
             * joystick in the high byte and 0xff in the low byte. The
             * bounded native profile has no P2 host input; all controls are
             * released, so the complete word is 0xffff. */
            *value = UINT16_C(0xffff);
            return 1;
        }
        if ((address & ~GN_MVS_REG_STATUS_A_DECODE_MASK) ==
            GN_MVS_REG_STATUS_A_ADDRESS - UINT32_C(1)) {
            uint8_t reply = 0u;
            if (!gn_mvs_sound_catch_up(image)) return 0;
            if (!gn_mvs_sound_read_reply(&image->mvs_sound, address, &reply)) {
                gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_READ, 2u);
                return 0;
            }
            const uint8_t status = gn_mvs_status_a_value(image);
            *value = (uint16_t)(((uint16_t)reply << 8) | status);
            return 1;
        }
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
            /* The read-side map is only four words wide and is mirrored
             * across 0x20000 bytes. Writes have a separate, wider decode. */
            const uint32_t index = (address & UINT32_C(0x00000006)) >> 1;
            if (index <= 1u) {
                *value = image->mvs_video_ram_read_buffer;
                return 1;
            }
            if (index == 2u) {
                *value = image->mvs_video_ram_modulo;
                return 1;
            }
            if (index == 3u) {
                uint32_t v_counter =
                    (uint32_t)(image->mvs_frame_cycle / GN_MVS_LINE_CYCLES) +
                    UINT32_C(0x100);
                if (v_counter >= UINT32_C(0x200))
                    v_counter -= (uint32_t)GN_MVS_FRAME_LINES;
                *value = (uint16_t)((v_counter << 7) |
                    (uint32_t)(image->mvs_video_auto_animation_counter & 7u));
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
            image->mvs_save_ram, image->mvs_save_ram_size,
            image->mvs_program_bank, address, value);
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
        gn_mvs_protocol_note_read(&image->mvs_protocol, address);
        if (gn_mvs_p1_control_decode(address)) {
            *value = (address & UINT32_C(1)) == 0u
                ? gn_mvs_p1_control_value(image)
                : GN_MVS_REG_DIPSW_DEFAULT;
            return 1;
        }
        if (gn_mvs_p2_control_decode(address)) {
            *value = GN_MVS_REG_P2_CONTROL_IDLE;
            return 1;
        }
        if ((address & UINT32_C(0x00fe0000)) == UINT32_C(0x003c0000) &&
            (address & UINT32_C(1)) == 0u) {
            const uint32_t index = (address & UINT32_C(0x00000006)) >> 1;
            uint16_t register_value;
            if (index <= 1u) {
                register_value = image->mvs_video_ram_read_buffer;
            } else if (index == 2u) {
                register_value = image->mvs_video_ram_modulo;
            } else {
                uint32_t v_counter =
                    (uint32_t)(image->mvs_frame_cycle / GN_MVS_LINE_CYCLES) +
                    UINT32_C(0x100);
                if (v_counter >= UINT32_C(0x200))
                    v_counter -= (uint32_t)GN_MVS_FRAME_LINES;
                register_value = (uint16_t)((v_counter << 7) |
                    (uint32_t)(image->mvs_video_auto_animation_counter & 7u));
            }
            *value = (uint8_t)(register_value >> 8);
            return 1;
        }
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
        if ((address & ~GN_MVS_REG_DIPSW_DECODE_MASK) == GN_MVS_REG_DIPSW_ADDRESS) {
            /* REG_DIPSW. The DSW port defaults every switch to its Off/Normal
             * position, which MAME reads as 0xff (neogeo.cpp 31e52312 lines
             * 1814-1836); in0_edge_r returns it as the low byte of the word at
             * $300000 (lines 899-902), mirrored by 0x01ff7e (lines 1581-1583).
             * The NeoGeo Development Wiki "Memory mapped registers" oldid 9288
             * lists REG_DIPSW at $300001, decode mask $FE0081, active low. */
            *value = GN_MVS_REG_DIPSW_DEFAULT;
            return 1;
        }
        if ((address & ~GN_MVS_REG_TEST_DECODE_MASK) == GN_MVS_REG_TEST_ADDRESS) {
            *value = GN_MVS_REG_TEST_IDLE;
            return 1;
        }
        if ((address & ~UINT32_C(0x01fffe)) == UINT32_C(0x320000)) {
            if (!gn_mvs_sound_catch_up(image)) return 0;
            return gn_mvs_sound_read_reply(&image->mvs_sound, address, value);
        }
        if ((address & ~GN_MVS_REG_STATUS_A_DECODE_MASK) == GN_MVS_REG_STATUS_A_ADDRESS) {
            /* Pinned MAME neogeo.cpp 31e52312 lines 1731 and 1845-1853: the
             * AUDIO_COIN port low byte with the calendar pins read live. Data
             * out is returned as the pin level because output enable is held
             * high at machine start (upd1990a.cpp get_data_out). */
            *value = gn_mvs_status_a_value(image);
            return 1;
        }
        if ((address & ~GN_MVS_REG_STATUS_B_DECODE_MASK) == GN_MVS_REG_STATUS_B_ADDRESS) {
            *value = gn_mvs_status_b_value(image);
            return 1;
        }
        const int success = gn_mvs_bus_read8(
            image->mvs_regions, image->mvs_region_count,
            image->mvs_work_ram, image->mvs_work_ram_size,
            image->mvs_save_ram, image->mvs_save_ram_size,
            image->mvs_program_bank, address, value);
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

static int gn_mvs_write_program_bank(gn_image *image, uint32_t address,
                                     uint16_t value) {
    if (image == NULL || address < UINT32_C(0x2ffff0) ||
        address > UINT32_C(0x2ffffe) || (address & UINT32_C(1)) != 0u) {
        return 0;
    }
    /* Pinned MAME 31e52312 neogeo.cpp write_banksel installs eight
     * word registers across $2ffff0-$2fffff. The data's low three
     * bits select a 1 MiB page at (bank + 1) MiB; a page whose base
     * is beyond the loaded program falls back to bank zero. This is
     * emulator-differential behavior, not physical-board evidence. */
    size_t program_size = 0u;
    for (size_t index = 0u; index < image->mvs_region_count; ++index) {
        if (image->mvs_regions[index].role == GN_MVS_REGION_PROGRAM) {
            program_size = image->mvs_regions[index].size;
            break;
        }
    }
    uint8_t selected_bank = (uint8_t)(value & UINT16_C(7));
    const size_t bank_base = ((size_t)selected_bank + 1u) * 0x100000u;
    if (bank_base >= program_size) selected_bank = 0u;
    image->mvs_program_bank = selected_bank;
    return 1;
}

/* Pinned MAME neogeo_v.cpp video_register_w and neogeo_spr.cpp VRAM
 * callbacks, revision 31e52312, supply the modeled register effects. */
static int gn_mvs_write_video_register(gn_image *image, uint32_t address,
                                       uint16_t value, uint8_t access_width) {
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
        /* MAME set_video_control: high byte controls animation speed, bit 3
         * disables auto animation, bits 4-7 set IRQ2 control. */
        image->mvs_video_auto_animation_speed = (uint8_t)(value >> 8);
        image->mvs_video_auto_animation_disabled =
            (uint8_t)((value >> 3) & 1u);
        image->mvs_display_position_interrupt_control =
            (uint8_t)(value & UINT16_C(0x00f0));
        return 1;
    }
    if (index == 6u) {
        gn_mvs_protocol_note_irq_ack(&image->mvs_protocol);
        /* Pinned MAME 31e52312 neogeo.cpp lines 805-815
         * (acknowledge_interrupt): bit 0 clears IRQ3, bit 1 the display
         * position interrupt and bit 2 VBlank, then update_interrupts
         * (lines 797-803) recomputes the lines. The owned CPU's line setter is
         * rejected while an instruction executes, so gn_run_mvs applies the
         * recomputed highest pending level at the next instruction boundary,
         * where a 68000 samples its interrupt lines. */
        image->mvs_irq_pending_mask =
            (uint8_t)(image->mvs_irq_pending_mask & (uint8_t)~(value & 7u));
        return 1;
    }
    gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_WRITE,
                            access_width);
    return 0;
}

static int gn_write16(void *userdata, uint32_t address, uint16_t value) {
    gn_image *image = (gn_image *)userdata;
    if (image == NULL || (address & UINT32_C(1)) != 0u) {
        return 0;
    }
    if (image->mvs_region_count != 0u) {
        if (gn_mvs_mslugx_protection_decode(address)) {
            return gn_mvs_mslugx_protection_write(image, address, value);
        }
        if (address >= UINT32_C(0x2ffff0) &&
            address <= UINT32_C(0x2ffffe)) {
            return gn_mvs_write_program_bank(image, address, value);
        }
        if ((address & UINT32_C(0x00fe0000)) == UINT32_C(0x003c0000)) {
            /* Pinned MAME's video_register_w handles the shared register
             * semantics; only the supported subset is modeled here. */
            return gn_mvs_write_video_register(image, address, value, 2u);
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
                const uint8_t high = (uint8_t)(value >> 8);
                const uint8_t low = (uint8_t)value;
                const int changed = image->mvs_save_ram[offset] != high ||
                    image->mvs_save_ram[offset + 1u] != low;
                image->mvs_save_ram[offset] = high;
                image->mvs_save_ram[offset + 1u] = low;
                if (changed) gn_mvs_save_guest_mutation(image);
            }
            return 1;
        }
        const int success = gn_mvs_bus_write16(
            image->mvs_work_ram, image->mvs_work_ram_size, address, value);
        if (!success) gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_WRITE, 2u);
        else gn_mvs_note_guest_write(image, address, 2u, value);
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
        if (address >= UINT32_C(0x2ffff0) &&
            address <= UINT32_C(0x2fffff)) {
            /* MAME's big-endian memory layer packs byte writes into the
             * selected word lane before calling write16smo_delegate. */
            const uint32_t word_address = address & ~UINT32_C(1);
            const uint16_t word_value = (address & UINT32_C(1)) != 0u
                ? (uint16_t)value : (uint16_t)((uint16_t)value << 8);
            return gn_mvs_write_program_bank(image, word_address, word_value);
        }
        if ((address & UINT32_C(0x00fe0000)) == UINT32_C(0x003c0000) &&
            (address & UINT32_C(1)) == 0u) {
            /* MAME's big-endian byte adapter places an even-address byte in
             * the high lane. video_register_w duplicates that byte into both
             * lanes before applying its register semantics. Low-byte-only
             * writes stay unmapped. */
            const uint16_t packed = (uint16_t)(((uint16_t)value << 8) | value);
            return gn_mvs_write_video_register(image, address, packed, 1u);
        }
        if ((address & ~UINT32_C(0x01fffe)) == UINT32_C(0x320000)) {
            if (!gn_mvs_sound_catch_up(image)) return 0;
            return gn_mvs_sound_write_command(&image->mvs_sound, address, value);
        }
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
                 * Version 2 supplies the separate BIOS source; legacy v1
                 * selection fails on its first absent-source fetch. */
                if (!gn_mvs_sound_catch_up(image)) return 0;
                image->mvs_cart_audio_selected =
                    (uint8_t)((word_offset >> 3) & 1u);
                image->mvs_sound.cart_selected = image->mvs_cart_audio_selected;
                return 1;
            }
        }
        if ((address & UINT32_C(0x00fe0000)) == UINT32_C(0x00380000) &&
            (address & UINT32_C(1)) != 0u) {
            const uint32_t io_word_offset = (address & UINT32_C(0xff)) >> 1;
            switch (io_word_offset & UINT32_C(0x78)) {
            case UINT32_C(0x00):
                /* Pinned MAME neogeo_base_state::io_control_w forwards this
                 * output to optional controller devices. The selected native
                 * profile has no host input device, so accept the mapped
                 * output without inventing controller state. */
                return 1;
            case UINT32_C(0x10):
                /* MAME mvs_state::io_control_w selects an existing slot.
                 * The admitted profile owns only slot zero, so empty slots
                 * leave its current cartridge mapping unchanged. */
                if (value < 6u) return 1;
                break;
            case UINT32_C(0x18):
                /* MAME mvs_state updates the latch; its base output_strobe and
                 * set_outputs virtuals are empty, so external outputs stay out. */
                image->mvs_output_latch = value;
                return 1;
            case UINT32_C(0x20):
                image->mvs_output_data = value;
                return 1;
            case GN_MVS_CAL_WRITE_OFFSET:
                /* ngarcade_base_state::io_control_w offset 0x28 (S21b). */
                if (gn_mvs_calendar_write_lines(&image->mvs_calendar, value) == 0) {
                    gn_record_mvs_bus_fault(image, address, GN_MVS_BUS_ACCESS_WRITE, 1u);
                    return 0;
                }
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
                /* MAME routes offsets 0x30/0x70 with bit 1 clear to its
                 * bookkeeping coin counters. These outputs are not guest-
                 * visible and this core does not model physical counters. */
                return 1;
            default:
                break;
            }
        }
        if ((address & UINT32_C(1)) != 0u &&
            (latch_address & ~UINT32_C(0x1f)) == UINT32_C(0x3a0000)) {
            const uint32_t word_offset = (latch_address - UINT32_C(0x3a0000)) >> 1;
            if ((word_offset & UINT32_C(7)) == 0u) {
                /* The system-latch Q0 output selects MAME's shadow pen bank. */
                image->mvs_screen_shadow = (uint8_t)((word_offset >> 3) & 1u);
                return 1;
            }
            if ((word_offset & UINT32_C(7)) == 2u) {
                /* S24f maps HC259 output 2 to the memory card's lock1 input. */
                image->mvs_memcard_lock1 = (uint8_t)((word_offset >> 3) & 1u);
                return 1;
            }
            if ((word_offset & UINT32_C(7)) == 3u) {
                /* S24b maps HC259 output 3 to the memory card's unlock2 input. */
                image->mvs_memcard_unlock2 = (uint8_t)((word_offset >> 3) & 1u);
                return 1;
            }
            if ((word_offset & UINT32_C(7)) == 6u) {
                /* Pinned MAME ngarcade_base_state::set_save_ram_unlock sets
                 * this gate; save_ram_w accepts writes only while enabled. */
                image->mvs_save_ram_unlocked = (uint8_t)((word_offset >> 3) & 1u);
                return 1;
            }
            if ((word_offset & UINT32_C(7)) == 7u) {
                /* Pinned MAME neogeo_base_state::set_palette_bank selects
                 * the palette bank and refreshes pens. */
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
                const size_t offset = (size_t)(address & UINT32_C(0xffff));
                if (image->mvs_save_ram[offset] != value) {
                    image->mvs_save_ram[offset] = value;
                    gn_mvs_save_guest_mutation(image);
                }
            }
            return 1;
        }
        if (address < UINT32_C(0x100000)) {
            /* MAME 31e52312 neogeo_main_map has only a vector read handler at
             * 0x000000-0x00007f, and 0x000080-0x0fffff is the read-only
             * cartridge P1 window (docs/mvs-media.md S7, read by
             * gn_mvs_bus_read*). Writes anywhere below work RAM reach MAME's
             * default dropped-write handler: they log and are not stored. This
             * is a differential emulator behavior, not verified board behavior. */
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
        else gn_mvs_note_guest_write(image, address, 1u, value);
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

/* SHA-256 follows RFC 6234 section 6.1 (2011-05),
 * https://www.rfc-editor.org/rfc/rfc6234.html. This is an independent
 * implementation of the algorithm; no RFC sample implementation is copied. */
typedef struct {
    uint32_t words[8];
    uint64_t total_bytes;
    uint8_t block[64];
    size_t used;
} gn_sha256;

static uint32_t gn_sha256_rotr(uint32_t value, unsigned count) {
    return (value >> count) | (value << (32u - count));
}

static void gn_sha256_process(gn_sha256 *sha, const uint8_t block[64]) {
    static const uint32_t constants[64] = {
        UINT32_C(0x428a2f98), UINT32_C(0x71374491), UINT32_C(0xb5c0fbcf), UINT32_C(0xe9b5dba5),
        UINT32_C(0x3956c25b), UINT32_C(0x59f111f1), UINT32_C(0x923f82a4), UINT32_C(0xab1c5ed5),
        UINT32_C(0xd807aa98), UINT32_C(0x12835b01), UINT32_C(0x243185be), UINT32_C(0x550c7dc3),
        UINT32_C(0x72be5d74), UINT32_C(0x80deb1fe), UINT32_C(0x9bdc06a7), UINT32_C(0xc19bf174),
        UINT32_C(0xe49b69c1), UINT32_C(0xefbe4786), UINT32_C(0x0fc19dc6), UINT32_C(0x240ca1cc),
        UINT32_C(0x2de92c6f), UINT32_C(0x4a7484aa), UINT32_C(0x5cb0a9dc), UINT32_C(0x76f988da),
        UINT32_C(0x983e5152), UINT32_C(0xa831c66d), UINT32_C(0xb00327c8), UINT32_C(0xbf597fc7),
        UINT32_C(0xc6e00bf3), UINT32_C(0xd5a79147), UINT32_C(0x06ca6351), UINT32_C(0x14292967),
        UINT32_C(0x27b70a85), UINT32_C(0x2e1b2138), UINT32_C(0x4d2c6dfc), UINT32_C(0x53380d13),
        UINT32_C(0x650a7354), UINT32_C(0x766a0abb), UINT32_C(0x81c2c92e), UINT32_C(0x92722c85),
        UINT32_C(0xa2bfe8a1), UINT32_C(0xa81a664b), UINT32_C(0xc24b8b70), UINT32_C(0xc76c51a3),
        UINT32_C(0xd192e819), UINT32_C(0xd6990624), UINT32_C(0xf40e3585), UINT32_C(0x106aa070),
        UINT32_C(0x19a4c116), UINT32_C(0x1e376c08), UINT32_C(0x2748774c), UINT32_C(0x34b0bcb5),
        UINT32_C(0x391c0cb3), UINT32_C(0x4ed8aa4a), UINT32_C(0x5b9cca4f), UINT32_C(0x682e6ff3),
        UINT32_C(0x748f82ee), UINT32_C(0x78a5636f), UINT32_C(0x84c87814), UINT32_C(0x8cc70208),
        UINT32_C(0x90befffa), UINT32_C(0xa4506ceb), UINT32_C(0xbef9a3f7), UINT32_C(0xc67178f2)
    };
    uint32_t schedule[64];
    for (size_t index = 0u; index < 16u; ++index) {
        const size_t at = index * 4u;
        schedule[index] = ((uint32_t)block[at] << 24) |
            ((uint32_t)block[at + 1u] << 16) |
            ((uint32_t)block[at + 2u] << 8) | (uint32_t)block[at + 3u];
    }
    for (size_t index = 16u; index < 64u; ++index) {
        const uint32_t x = schedule[index - 15u];
        const uint32_t y = schedule[index - 2u];
        const uint32_t small0 = gn_sha256_rotr(x, 7u) ^
            gn_sha256_rotr(x, 18u) ^ (x >> 3);
        const uint32_t small1 = gn_sha256_rotr(y, 17u) ^
            gn_sha256_rotr(y, 19u) ^ (y >> 10);
        schedule[index] = schedule[index - 16u] + small0 +
            schedule[index - 7u] + small1;
    }
    uint32_t a = sha->words[0];
    uint32_t b = sha->words[1];
    uint32_t c = sha->words[2];
    uint32_t d = sha->words[3];
    uint32_t e = sha->words[4];
    uint32_t f = sha->words[5];
    uint32_t g = sha->words[6];
    uint32_t h = sha->words[7];
    for (size_t index = 0u; index < 64u; ++index) {
        const uint32_t big1 = gn_sha256_rotr(e, 6u) ^
            gn_sha256_rotr(e, 11u) ^ gn_sha256_rotr(e, 25u);
        const uint32_t choose = (e & f) ^ (~e & g);
        const uint32_t first = h + big1 + choose + constants[index] + schedule[index];
        const uint32_t big0 = gn_sha256_rotr(a, 2u) ^
            gn_sha256_rotr(a, 13u) ^ gn_sha256_rotr(a, 22u);
        const uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        const uint32_t second = big0 + majority;
        h = g; g = f; f = e; e = d + first;
        d = c; c = b; b = a; a = first + second;
    }
    sha->words[0] += a; sha->words[1] += b;
    sha->words[2] += c; sha->words[3] += d;
    sha->words[4] += e; sha->words[5] += f;
    sha->words[6] += g; sha->words[7] += h;
}

static void gn_sha256_init(gn_sha256 *sha) {
    static const uint32_t initial[8] = {
        UINT32_C(0x6a09e667), UINT32_C(0xbb67ae85), UINT32_C(0x3c6ef372), UINT32_C(0xa54ff53a),
        UINT32_C(0x510e527f), UINT32_C(0x9b05688c), UINT32_C(0x1f83d9ab), UINT32_C(0x5be0cd19)
    };
    memcpy(sha->words, initial, sizeof(initial));
    sha->total_bytes = 0u;
    sha->used = 0u;
}

static void gn_sha256_update(gn_sha256 *sha, const uint8_t *bytes, size_t length) {
    sha->total_bytes += (uint64_t)length;
    while (length != 0u) {
        size_t amount = sizeof(sha->block) - sha->used;
        if (amount > length) amount = length;
        memcpy(sha->block + sha->used, bytes, amount);
        sha->used += amount;
        bytes += amount;
        length -= amount;
        if (sha->used == sizeof(sha->block)) {
            gn_sha256_process(sha, sha->block);
            sha->used = 0u;
        }
    }
}

static void gn_sha256_finish(gn_sha256 *sha, uint8_t digest[32]) {
    const uint64_t bit_length = sha->total_bytes * UINT64_C(8);
    sha->block[sha->used++] = UINT8_C(0x80);
    if (sha->used > 56u) {
        memset(sha->block + sha->used, 0, sizeof(sha->block) - sha->used);
        gn_sha256_process(sha, sha->block);
        sha->used = 0u;
    }
    memset(sha->block + sha->used, 0, 56u - sha->used);
    for (unsigned index = 0u; index < 8u; ++index) {
        sha->block[63u - index] = (uint8_t)(bit_length >> (index * 8u));
    }
    gn_sha256_process(sha, sha->block);
    for (size_t word = 0u; word < 8u; ++word) {
        for (unsigned byte = 0u; byte < 4u; ++byte) {
            digest[word * 4u + byte] =
                (uint8_t)(sha->words[word] >> (24u - byte * 8u));
        }
    }
}

static void gn_sha256_u32(gn_sha256 *sha, uint32_t value) {
    const uint8_t bytes[4] = {(uint8_t)(value >> 24), (uint8_t)(value >> 16),
                              (uint8_t)(value >> 8), (uint8_t)value};
    gn_sha256_update(sha, bytes, sizeof(bytes));
}

static void gn_sha256_u64(gn_sha256 *sha, uint64_t value) {
    gn_sha256_u32(sha, (uint32_t)(value >> 32));
    gn_sha256_u32(sha, (uint32_t)value);
}

static void gn_diagnostic_media_identity(const gn_image *image,
                                         uint8_t out_digest[32]) {
    static const uint8_t domain[] = "Glueyneo diagnostic media identity v1";
    gn_sha256 sha;
    gn_sha256_init(&sha);
    gn_sha256_update(&sha, domain, sizeof(domain) - 1u);
    gn_sha256_u32(&sha, GN_PROFILE_DIAGNOSTIC);
    gn_sha256_u32(&sha, GN_STATE_CONFIGURATION_DIAGNOSTIC_V1);
    gn_sha256_u32(&sha, (uint32_t)GN_REGION_ROM);
    gn_sha256_u32(&sha, image->rom.base);
    gn_sha256_u32(&sha, image->rom.size);
    gn_sha256_u64(&sha, image->rom.size);
    gn_sha256_update(&sha, image->rom.bytes, image->rom.size);
    gn_sha256_u32(&sha, (uint32_t)GN_REGION_RAM);
    gn_sha256_u32(&sha, image->ram.base);
    gn_sha256_u32(&sha, image->ram.size);
    gn_sha256_u64(&sha, (uint64_t)image->ram_seed_size);
    gn_sha256_u64(&sha, image->ram.size);
    gn_sha256_update(&sha, image->ram.bytes, image->ram.size);
    gn_sha256_finish(&sha, out_digest);
}

static void gn_mvs_media_identity(const gn_image *image,
                                  uint8_t out_digest[32]) {
    static const uint8_t domain[] = "Glueyneo MVS native state media v1";
    gn_sha256 sha;
    gn_sha256_init(&sha);
    gn_sha256_update(&sha, domain, sizeof(domain) - 1u);
    gn_sha256_u32(&sha, GN_MVS_PROFILE_MSX);
    gn_sha256_u32(&sha, UINT32_C(2)); /* MVS native-state configuration v1. */
    for (unsigned role = GN_MVS_REGION_BIOS;
         role <= GN_MVS_REGION_Y_ZOOM; ++role) {
        const gn_mvs_owned_region *found = NULL;
        for (size_t index = 0u; index < image->mvs_region_count; ++index) {
            if ((unsigned)image->mvs_regions[index].role == role) {
                found = &image->mvs_regions[index];
                break;
            }
        }
        gn_sha256_u32(&sha, (uint32_t)role);
        gn_sha256_u32(&sha, found != NULL ? UINT32_C(1) : UINT32_C(0));
        if (found != NULL) {
            gn_sha256_u64(&sha, (uint64_t)found->size);
            gn_sha256_update(&sha, found->bytes, found->size);
        }
    }
    gn_sha256_finish(&sha, out_digest);
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

gn_status gn_test_sha256(const uint8_t *bytes, size_t length,
                         uint8_t out_digest[32]) {
    if (out_digest == NULL || (bytes == NULL && length != 0u))
        return GN_STATUS_INVALID_ARGUMENT;
    gn_sha256 sha;
    gn_sha256_init(&sha);
    if (length != 0u) gn_sha256_update(&sha, bytes, length);
    gn_sha256_finish(&sha, out_digest);
    return GN_STATUS_OK;
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
    gn_mvs_sound_destroy(&image->mvs_sound);
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
        gn_mvs_failure_clear(&image->mvs_failure);
        image->mvs_completed_main_instructions = 0u;
        image->mvs_sound_step_cycles = 0u;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
        image->test_mvs_failure = GN_TEST_MVS_FAILURE_NONE;
#endif
        memset(image->mvs_work_ram, 0, image->mvs_work_ram_size);
        image->mvs_bus_fault_address = 0u;
        image->mvs_bus_fault_access = (gn_mvs_bus_access)0;
        image->mvs_bus_fault_width = 0u;
        image->mvs_bus_fault_valid = 0u;
        image->mvs_program_bank = 0u;
        image->mvs_mame_unmapped_write_count = 0u;
        image->mvs_watchdog_pet_count = 0u;
        image->mvs_watchdog_reset_count = 0u;
        image->mvs_video_auto_animation_speed = 0u;
        image->mvs_video_auto_animation_disabled = 0u;
        image->mvs_video_auto_animation_counter = 0u;
        image->mvs_video_auto_animation_frame_counter = 0u;
        image->mvs_display_position_interrupt_control = 0u;
        image->mvs_irq_pending_mask = 0u;
        image->mvs_inputs = 0u;
        image->mvs_frame_cycle = 0u;
        image->mvs_frame_cycle_carry = 0u;
        image->mvs_frame_count = 0u;
        image->mvs_output_data = 0u;
        image->mvs_output_latch = 0u;
        image->mvs_use_cart_vectors = 0u;
        image->mvs_cart_audio_selected = 0u;
        image->mvs_memcard_lock1 = 0u;
        image->mvs_memcard_unlock2 = 0u;
        image->mvs_coin_lockout_mask = 0u;
        image->mvs_save_ram_unlocked = 0u;
        image->mvs_palette_bank_selected = 0u;
        image->mvs_screen_shadow = 0u;
        image->mvs_watchdog_pet_generation = 0u;
        image->mvs_watchdog_remaining_cycles = GN_MVS_WATCHDOG_MAIN_CYCLES;
        gn_mvs_calendar_reset(&image->mvs_calendar);
        gn_mvs_protocol_reset(&image->mvs_protocol);
        const owned_cpu_status mvs_status = owned_cpu_reset(image->cpu);
        if (mvs_status != OWNED_CPU_OK) {
            gn_mvs_failure_record_image(image,
                                  GN_MVS_FAILURE_COMPONENT_BOARD,
                                  GN_MVS_FAILURE_STAGE_WATCHDOG_RESET,
                                  GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
            return GN_STATUS_CPU_FAILURE;
        }
        const gn_status sound_status = gn_mvs_sound_reset(&image->mvs_sound);
        if (sound_status != GN_STATUS_OK) {
            gn_mvs_failure_record_sound(image,
                                        GN_MVS_FAILURE_STAGE_WATCHDOG_RESET,
                                        GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
        }
        return sound_status;
    }
    memset(image->ram.bytes, 0, (size_t)image->ram.size);
    memcpy(image->ram.bytes, image->ram_seed, image->ram_seed_size);
    const owned_cpu_status status = owned_cpu_reset(image->cpu);
    if (status != OWNED_CPU_OK) return GN_STATUS_CPU_FAILURE;
    image->diagnostic_guest_faulted = 0u;
    return GN_STATUS_OK;
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

#if defined(Z80_CANDIDATE_TEST_HOOKS)
gn_status gn_test_state_failpoint_arm(gn_instance *instance, size_t fail_at) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    memset(&instance->state_failpoint, 0, sizeof(instance->state_failpoint));
    instance->state_failpoint.fail_at = fail_at;
    instance->state_failpoint_active = 1u;
    return GN_STATUS_OK;
}

gn_status gn_test_state_validation_bypass_arm(gn_instance *instance,
                                               uint32_t validator) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_ARGUMENT;
    if (validator == GN_TEST_STATE_BYPASS_YM_IRQ_RELATION) {
        instance->state_bypass_ym_irq_relation = 1u;
        return GN_STATUS_OK;
    }
    if (validator != GN_TEST_STATE_BYPASS_Z80_VALIDATOR)
        return GN_STATUS_INVALID_ARGUMENT;
    memset(&instance->state_failpoint, 0, sizeof(instance->state_failpoint));
    instance->state_failpoint.bypass_validation = 1u;
    instance->state_failpoint_active = 1u;
    return GN_STATUS_OK;
}

gn_status gn_test_state_failpoint_disarm(gn_instance *instance) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    instance->state_failpoint_active = 0u;
    return GN_STATUS_OK;
}

gn_status gn_test_state_failpoint_read(
    const gn_instance *instance, gn_test_state_failpoint_info *out_failpoint) {
    if (instance == NULL || out_failpoint == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    out_failpoint->fail_at = instance->state_failpoint.fail_at;
    out_failpoint->attempts = instance->state_failpoint.attempts;
    out_failpoint->allocations = instance->state_failpoint.allocations;
    out_failpoint->frees = instance->state_failpoint.frees;
    out_failpoint->live_bytes = instance->state_failpoint.live_bytes;
    out_failpoint->high_water_bytes =
        instance->state_failpoint.high_water_bytes;
    out_failpoint->failed_site = instance->state_failpoint.failed_site;
    return GN_STATUS_OK;
}
#endif

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

gn_status gn_test_mvs_set_failure(gn_instance *instance,
                                  gn_test_mvs_failure failure) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    if (failure < GN_TEST_MVS_FAILURE_NONE ||
        failure > GN_TEST_MVS_FAILURE_FIRST_ERROR_PRECEDENCE)
        return GN_STATUS_INVALID_ARGUMENT;
    gn_image *image = instance->image;
    image->test_mvs_failure = failure;
    switch (failure) {
        case GN_TEST_MVS_FAILURE_SOUND_BUS:
        case GN_TEST_MVS_FAILURE_SOUND_BEFORE_MAIN_PROGRESS:
        case GN_TEST_MVS_FAILURE_FIRST_ERROR_PRECEDENCE:
            image->mvs_sound.test_fail_bus = 1u;
            break;
        case GN_TEST_MVS_FAILURE_SOUND_TICK_LIMIT:
            image->mvs_sound.test_fail_tick_limit = 1u;
            break;
        default:
            break;
    }
    return GN_STATUS_OK;
}

gn_status gn_test_mvs_run_with_pcm_capture(
    gn_instance *instance, uint64_t cycle_budget, int16_t *audio,
    size_t audio_capacity_frames, gn_run_result *out_result,
    size_t *out_delivered_frames) {
    if (out_result == NULL || out_delivered_frames == NULL ||
        (audio == NULL && audio_capacity_frames != 0u) ||
        audio_capacity_frames > GN_MVS_PCM_MAX_OUTPUT_FRAMES)
        return GN_STATUS_INVALID_ARGUMENT;
    *out_delivered_frames = 0u;
    memset(out_result, 0, sizeof(*out_result));
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    gn_mvs_sound *sound = &instance->image->mvs_sound;
    if (sound->pcm_capture_active != 0u) return GN_STATUS_INVALID_STATE;
    sound->pcm_active_sink = audio;
    sound->pcm_active_capacity_frames = audio_capacity_frames;
    sound->pcm_call_generated_frames = 0u;
    sound->pcm_call_delivered_frames = 0u;
    sound->pcm_capture_active = 1u;
    const gn_status status = gn_run_mvs(instance, cycle_budget, out_result);
    *out_delivered_frames = sound->pcm_call_delivered_frames;
    sound->pcm_active_sink = NULL;
    sound->pcm_active_capacity_frames = 0u;
    sound->pcm_call_generated_frames = 0u;
    sound->pcm_call_delivered_frames = 0u;
    sound->pcm_capture_active = 0u;
    return status;
}

static uint64_t gn_test_mvs_history_digest(uint64_t digest, uint32_t sample) {
    digest = (digest ^ (uint8_t)(sample >> 24)) * UINT64_C(1099511628211);
    digest = (digest ^ (uint8_t)(sample >> 16)) * UINT64_C(1099511628211);
    digest = (digest ^ (uint8_t)(sample >> 8)) * UINT64_C(1099511628211);
    return (digest ^ (uint8_t)sample) * UINT64_C(1099511628211);
}

gn_status gn_test_mvs_sound_state_read(
    const gn_instance *instance, gn_test_mvs_sound_state *out_state) {
    if (instance == NULL || out_state == NULL) return GN_STATUS_INVALID_ARGUMENT;
    memset(out_state, 0, sizeof(*out_state));
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    const gn_mvs_sound *sound = &instance->image->mvs_sound;
    out_state->main_cycles_advanced = sound->test_main_cycles_advanced;
    out_state->ym_input_clocks = sound->test_ym_input_clocks;
    out_state->native_samples = sound->test_native_samples;
    out_state->irq_assertions = sound->test_irq_assertions;
    out_state->irq_deassertions = sound->test_irq_deassertions;
    out_state->bank_changes = sound->test_bank_changes;
    memcpy(out_state->timer_register_writes, sound->test_timer_register_writes,
           sizeof(out_state->timer_register_writes));
    out_state->pcm_output_phase = sound->pcm_output_phase;
    out_state->filter_history_next = (uint16_t)sound->pcm_history_next;
    out_state->main_clock_remainder = sound->main_clock_remainder;
    out_state->ym_clock_remainder =
        (uint8_t)(sound->test_ym_input_clocks % UINT64_C(16));
    out_state->ym_irq = sound->ym_irq;
    memcpy(out_state->banks, sound->banks, sizeof(out_state->banks));
    out_state->failed = sound->failed;
    uint64_t digest = UINT64_C(14695981039346656037);
    for (size_t index = 0u; index < GN_MVS_PCM_FILTER_TAPS; ++index) {
        digest = gn_test_mvs_history_digest(
            digest, (uint32_t)sound->pcm_history[index]);
        digest = gn_test_mvs_history_digest(
            digest, (uint32_t)sound->pcm_right_history[index]);
    }
    out_state->filter_history_digest = digest;
    return GN_STATUS_OK;
}

gn_status gn_test_mvs_machine_state_read(
    const gn_instance *instance, gn_test_mvs_machine_state *out_state) {
    if (instance == NULL || out_state == NULL) return GN_STATUS_INVALID_ARGUMENT;
    memset(out_state, 0, sizeof(*out_state));
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    const gn_image *image = instance->image;
    out_state->frame_count = image->mvs_frame_count;
    out_state->frame_cycle = image->mvs_frame_cycle;
    out_state->frame_cycle_carry = image->mvs_frame_cycle_carry;
    out_state->watchdog_pet_count = image->mvs_watchdog_pet_count;
    out_state->watchdog_reset_count = image->mvs_watchdog_reset_count;
    out_state->watchdog_remaining_cycles = image->mvs_watchdog_remaining_cycles;
    out_state->irq_pending_mask = image->mvs_irq_pending_mask;
    out_state->animation_counter = image->mvs_video_auto_animation_counter;
    out_state->animation_frame_counter =
        image->mvs_video_auto_animation_frame_counter;
    out_state->animation_speed = image->mvs_video_auto_animation_speed;
    out_state->animation_disabled = image->mvs_video_auto_animation_disabled;
    return GN_STATUS_OK;
}

uintptr_t gn_test_mvs_save_ram_address(const gn_instance *instance) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u) return (uintptr_t)0;
    return (uintptr_t)instance->image->mvs_save_ram;
}

gn_status gn_test_save_seed_lineage(
    gn_instance *instance, uint64_t load_generation, uint64_t restore_branch,
    uint64_t mutation_sequence, uint64_t export_sequence) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    gn_mvs_save_ownership *save = &instance->mvs_save;
    save->load_generation = load_generation;
    save->restore_branch = restore_branch;
    save->mutation_sequence = mutation_sequence;
    save->export_sequence = export_sequence;
    save->exhausted = 0u;
    return GN_STATUS_OK;
}

gn_status gn_test_save_observe(
    const gn_instance *instance, gn_test_save_observation *out_observation) {
    if (instance == NULL || out_observation == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    memset(out_observation, 0, sizeof(*out_observation));
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    const gn_mvs_save_ownership *save = &instance->mvs_save;
    out_observation->load_generation = save->load_generation;
    out_observation->restore_branch = save->restore_branch;
    out_observation->mutation_sequence = save->mutation_sequence;
    out_observation->export_sequence = save->export_sequence;
    out_observation->scope_valid = save->scope_valid;
    out_observation->dirty = save->dirty;
    out_observation->baseline_known = save->baseline_known;
    out_observation->startup_import_allowed = save->startup_import_allowed;
    out_observation->exhausted = save->exhausted;
    out_observation->receipt_valid = save->receipt_valid;
    out_observation->receipt_consumed = save->receipt_consumed;
    return GN_STATUS_OK;
}

gn_status gn_test_save_stale_clean_bypass_arm(gn_instance *instance) {
    if (instance == NULL || instance->image == NULL ||
        instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    instance->state_bypass_save_stale_clean = 1u;
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

gn_status gn_test_mvs_read_bus8(const gn_instance *instance,
                                uint32_t address, uint8_t *out_value) {
    if (instance == NULL || out_value == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    return gn_read8(instance->image, address, out_value)
        ? GN_STATUS_OK : GN_STATUS_INVALID_MEDIA;
}

gn_status gn_test_mvs_write_bus8(gn_instance *instance, uint32_t address,
                                 uint8_t value) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    return gn_write8(instance->image, address, value)
        ? GN_STATUS_OK : GN_STATUS_INVALID_MEDIA;
}

gn_status gn_test_mvs_calendar(const gn_instance *instance, gn_mvs_calendar *out) {
    if (instance == NULL || out == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    *out = instance->image->mvs_calendar;
    return GN_STATUS_OK;
}

gn_status gn_test_mvs_system_latch_output3(const gn_instance *instance,
                                           uint8_t *out_value) {
    if (instance == NULL || out_value == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    *out_value = instance->image->mvs_memcard_unlock2;
    return GN_STATUS_OK;
}

gn_status gn_test_mvs_system_latch_output2(const gn_instance *instance,
                                           uint8_t *out_value) {
    if (instance == NULL || out_value == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    *out_value = instance->image->mvs_memcard_lock1;
    return GN_STATUS_OK;
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
    if (candidate->profile == GN_PROFILE_DIAGNOSTIC) {
        gn_diagnostic_media_identity(candidate,
                                     candidate->diagnostic_media_identity);
        candidate->diagnostic_media_identity_valid = 1u;
    }

    gn_image *previous = instance->image;
    instance->image = candidate;
    gn_mvs_save_load_committed(instance);
    gn_free_image(previous);
    return GN_STATUS_OK;
}

static gn_status gn_build_mvs_candidate(
    const gn_allocator *allocator, uint32_t version, uint32_t profile,
    size_t region_count, const gn_mvs_region *regions, size_t region_capacity,
    gn_image **out_candidate) {
    if (out_candidate == NULL) return GN_STATUS_INVALID_ARGUMENT;
    *out_candidate = NULL;
    if (allocator == NULL || regions == NULL) return GN_STATUS_INVALID_ARGUMENT;
    const int is_v3 = version == GN_MVS_MANIFEST_VERSION_ZOOM &&
                      region_capacity == GN_MVS_V3_MAX_REGIONS;
    if ((!is_v3 && version != GN_MVS_MANIFEST_VERSION &&
         version != GN_MVS_MANIFEST_VERSION_LEGACY) ||
        profile != GN_MVS_PROFILE_MSX) {
        return GN_STATUS_UNSUPPORTED_PROFILE;
    }
    const size_t required_regions = version == GN_MVS_MANIFEST_VERSION_LEGACY
        ? GN_MVS_LEGACY_REGIONS : GN_MVS_MAX_REGIONS;
    if ((is_v3 && region_count != GN_MVS_V3_MAX_REGIONS - 1u &&
         region_count != GN_MVS_V3_MAX_REGIONS) ||
        (!is_v3 && region_count != required_regions) ||
        region_count > region_capacity) return GN_STATUS_INVALID_MEDIA;
    uint32_t roles = 0u;
    size_t total = 0u;
    static const size_t expected_sizes[GN_MVS_V3_MAX_REGIONS] = {
        GN_MVS_BIOS_BYTES, GN_MVS_PROGRAM_BYTES, GN_MVS_FIXED_BYTES,
        GN_MVS_AUDIO_PROGRAM_BYTES, GN_MVS_SAMPLES_BYTES,
        GN_MVS_SPRITES_BYTES, GN_MVS_AUDIO_BIOS_BYTES,
        GN_MVS_Y_ZOOM_BYTES};
    const unsigned max_role = is_v3 ? GN_MVS_V3_MAX_REGIONS :
        (unsigned)required_regions;
    for (size_t index = 0u; index < region_count; ++index) {
        const gn_mvs_region *region = &regions[index];
        if (region->role < GN_MVS_REGION_BIOS ||
            (unsigned)region->role > max_role ||
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
    if (is_v3) {
        for (unsigned role = GN_MVS_REGION_BIOS;
             role <= GN_MVS_REGION_SPRITES; ++role)
            expected_roles |= UINT32_C(1) << role;
        expected_roles |= UINT32_C(1) << GN_MVS_REGION_Y_ZOOM;
        const uint32_t optional_audio_bios =
            UINT32_C(1) << GN_MVS_REGION_AUDIO_BIOS;
        if (roles != expected_roles &&
            roles != (expected_roles | optional_audio_bios))
            return GN_STATUS_INVALID_MEDIA;
    } else {
        for (unsigned role = GN_MVS_REGION_BIOS;
             role <= required_regions; ++role) {
            expected_roles |= UINT32_C(1) << role;
        }
        if (roles != expected_roles) return GN_STATUS_INVALID_MEDIA;
    }

    const gn_allocator candidate_allocator = *allocator;
    gn_image *candidate = (gn_image *)gn_allocate(&candidate_allocator,
                                                   sizeof(*candidate));
    if (candidate == NULL) return GN_STATUS_OUT_OF_MEMORY;
    memset(candidate, 0, sizeof(*candidate));
    candidate->allocator = candidate_allocator;
    candidate->profile = GN_MVS_PROFILE_MSX;
    candidate->mvs_region_count = region_count;
    candidate->mvs_work_ram_size = (size_t)0x10000u;
    candidate->mvs_work_ram = (uint8_t *)gn_allocate(
        &candidate_allocator, candidate->mvs_work_ram_size);
    candidate->mvs_save_ram_size = GN_MVS_SAVE_RAM_BYTES;
    candidate->mvs_save_ram = (uint8_t *)gn_allocate(
        &candidate_allocator, candidate->mvs_save_ram_size);
    candidate->mvs_palette_ram_size = GN_MVS_PALETTE_RAM_BYTES;
    candidate->mvs_palette_ram = (uint8_t *)gn_allocate(
        &candidate_allocator, candidate->mvs_palette_ram_size);
    candidate->mvs_video_ram_words = GN_MVS_VIDEO_RAM_WORDS;
    candidate->mvs_video_ram = (uint16_t *)gn_allocate(
        &candidate_allocator, candidate->mvs_video_ram_words *
                                  sizeof(*candidate->mvs_video_ram));
    if (candidate->mvs_work_ram == NULL || candidate->mvs_save_ram == NULL ||
        candidate->mvs_palette_ram == NULL || candidate->mvs_video_ram == NULL) {
        gn_free_image(candidate);
        return GN_STATUS_OUT_OF_MEMORY;
    }
    memset(candidate->mvs_save_ram, 0, candidate->mvs_save_ram_size);
    memset(candidate->mvs_video_ram, 0,
           candidate->mvs_video_ram_words * sizeof(*candidate->mvs_video_ram));
    memset(candidate->mvs_palette_ram, 0, candidate->mvs_palette_ram_size);
    for (size_t index = 0u; index < region_count; ++index) {
        const gn_mvs_region *source = &regions[index];
        gn_mvs_owned_region *destination = &candidate->mvs_regions[index];
        destination->bytes = (uint8_t *)gn_allocate(&candidate_allocator,
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
    const gn_mvs_owned_region *audio_program = NULL;
    for (size_t index = 0u; index < candidate->mvs_region_count; ++index) {
        if (candidate->mvs_regions[index].role == GN_MVS_REGION_AUDIO_PROGRAM) {
            audio_program = &candidate->mvs_regions[index];
            break;
        }
    }
    if (audio_program == NULL) {
        gn_free_image(candidate);
        return GN_STATUS_INVALID_MEDIA;
    }
    const gn_status sound_status = gn_mvs_sound_create(
        &candidate->mvs_sound, audio_program->bytes, audio_program->size);
    if (sound_status != GN_STATUS_OK) {
        gn_free_image(candidate);
        return sound_status;
    }
    for (size_t index = 0u; index < candidate->mvs_region_count; ++index) {
        if (candidate->mvs_regions[index].role == GN_MVS_REGION_AUDIO_BIOS) {
            candidate->mvs_sound.bios_program = candidate->mvs_regions[index].bytes;
            candidate->mvs_sound.bios_program_size = candidate->mvs_regions[index].size;
        }
        if (candidate->mvs_regions[index].role == GN_MVS_REGION_SAMPLES) {
            candidate->mvs_sound.samples = candidate->mvs_regions[index].bytes;
            candidate->mvs_sound.samples_size = candidate->mvs_regions[index].size;
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
    const gn_status state_status = gn_mvs_native_state_capacity(
        candidate, &candidate->mvs_state_capacity);
    if (state_status != GN_STATUS_OK) {
        gn_free_image(candidate);
        return state_status;
    }
    gn_mvs_media_identity(candidate, candidate->mvs_media_identity);
    candidate->mvs_media_identity_valid = 1u;
    *out_candidate = candidate;
    return GN_STATUS_OK;
}

static void gn_mvs_candidate_commit(gn_instance *instance,
                                   gn_image *candidate) {
    gn_image *previous = instance->image;
    candidate->save_owner = instance;
    instance->image = candidate;
    gn_mvs_save_load_committed(instance);
    gn_free_image(previous);
}

static gn_status gn_load_mvs_regions(gn_instance *instance, uint32_t version,
                                     uint32_t profile, size_t region_count,
                                     const gn_mvs_region *regions,
                                     size_t region_capacity) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    gn_image *candidate = NULL;
    const gn_status status = gn_build_mvs_candidate(
        &instance->allocator, version, profile, region_count, regions,
        region_capacity, &candidate);
    if (status != GN_STATUS_OK) return status;
    gn_mvs_candidate_commit(instance, candidate);
    return GN_STATUS_OK;
}

GN_API gn_status gn_load_mvs(gn_instance *instance,
                             const gn_mvs_manifest *manifest) {
    if (manifest == NULL) return GN_STATUS_INVALID_ARGUMENT;
    return gn_load_mvs_regions(instance, manifest->version, manifest->profile,
                               manifest->region_count, manifest->regions,
                               GN_MVS_MAX_REGIONS);
}

GN_API gn_status gn_load_mvs_v3(gn_instance *instance,
                                const gn_mvs_manifest_v3 *manifest) {
    if (manifest == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (manifest->version != GN_MVS_MANIFEST_VERSION_ZOOM)
        return GN_STATUS_UNSUPPORTED_PROFILE;
    return gn_load_mvs_regions(instance, manifest->version, manifest->profile,
                               manifest->region_count, manifest->regions,
                               GN_MVS_V3_MAX_REGIONS);
}

GN_API gn_status gn_reset(gn_instance *instance) {
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    return gn_initialize_candidate(instance->image);
}

#define GN_STATE_SECTION_CPU UINT32_C(1)
#define GN_STATE_SECTION_RAM UINT32_C(2)
#define GN_STATE_SECTION_MVS_MEMORY UINT32_C(2)
#define GN_STATE_SECTION_MVS_BOARD UINT32_C(3)
#define GN_STATE_SECTION_MVS_SOUND UINT32_C(4)
#define GN_STATE_SECTION_MVS_YM2610 UINT32_C(5)
#define GN_STATE_CPU_BYTES ((size_t)152u)
#define GN_STATE_RAM_BYTES ((size_t)GN_RAM_SIZE)
#define GN_STATE_MVS_CONFIGURATION_V1 UINT32_C(2)
#define GN_STATE_MVS_SECTION_COUNT UINT32_C(5)
#define GN_STATE_MVS_CALENDAR_BYTES ((size_t)46u)
#define GN_STATE_MVS_PROTOCOL_EVENT_BYTES ((size_t)32u)
#define GN_STATE_MVS_POLLED_BYTES ((size_t)12u)
#define GN_STATE_MVS_PROTOCOL_BYTES \
    ((size_t)GN_MVS_PROTOCOL_TRACE_CAPACITY * GN_STATE_MVS_PROTOCOL_EVENT_BYTES + \
     (size_t)8u + (size_t)64u + (size_t)7u + \
     (size_t)GN_MVS_POLLED_TABLE_CAPACITY * GN_STATE_MVS_POLLED_BYTES + \
     (size_t)4u + (size_t)24u + (size_t)64u + (size_t)40u + (size_t)16u)
#define GN_STATE_MVS_BOARD_BYTES \
    ((size_t)135u + GN_STATE_MVS_PROTOCOL_BYTES)
#define GN_STATE_MVS_SOUND_FIXED_BYTES \
    ((size_t)7u + GN_MVS_SOUND_RAM_BYTES + (size_t)4u + \
     (size_t)2u * GN_MVS_PCM_FILTER_TAPS * (size_t)4u + (size_t)4u + \
     (size_t)2u)

_Static_assert(sizeof(gn_state_reason) == 4u,
               "native state reasons use a fixed 32-bit representation");
_Static_assert(sizeof(gn_state_detail_v1) == 20u,
               "native state detail v1 layout must stay fixed width");
_Static_assert(sizeof(gn_state_compatibility_info_v1) == 60u,
               "native state compatibility v1 layout must stay fixed width");
_Static_assert(sizeof(gn_mvs_save_scope_v1) == 24u,
               "MVS save scope v1 layout must stay fixed");
_Static_assert(sizeof(gn_mvs_save_receipt_v1) == 56u,
               "MVS save receipt v1 layout must stay fixed");
_Static_assert(sizeof(gn_mvs_save_info_v1) == 60u,
               "MVS save info v1 layout must stay fixed");
_Static_assert(sizeof(gn_mvs_save_detail_v1) == 16u,
               "MVS save detail v1 layout must stay fixed");
_Static_assert(sizeof(gn_mvs_save_lifecycle_result_v1) == 8u,
               "MVS save lifecycle result v1 layout must stay fixed");
_Static_assert(GN_MVS_SAVE_ENVELOPE_V1_BYTES == 65632u,
               "MVS save envelope v1 must remain bounded");
_Static_assert(GN_STATE_MAX_SIZE_V1 == 4336u,
               "diagnostic native state v1 maximum must be stable");

static int gn_state_size_add(size_t *total, size_t amount) {
    if (total == NULL || amount > SIZE_MAX - *total) return 0;
    *total += amount;
    return 1;
}

static gn_status gn_mvs_native_state_capacity(gn_image *image,
                                               size_t *out_capacity) {
    if (image == NULL || out_capacity == NULL ||
        image->mvs_region_count == 0u || image->mvs_sound.ym == NULL ||
        image->mvs_work_ram == NULL || image->mvs_save_ram == NULL ||
        image->mvs_palette_ram == NULL || image->mvs_video_ram == NULL)
        return GN_STATUS_INVALID_STATE;
    size_t ym_bytes = 0u;
    const ym2610_candidate_status ym_status =
        ym2610_candidate_state_size(image->mvs_sound.ym, &ym_bytes);
    if (ym_status != YM2610_CANDIDATE_OK || ym_bytes == 0u ||
        ym_bytes > UINT32_MAX)
        return ym_status == YM2610_CANDIDATE_NO_MEMORY
            ? GN_STATUS_OUT_OF_MEMORY : GN_STATUS_CPU_FAILURE;
    size_t memory_bytes = image->mvs_work_ram_size;
    if (!gn_state_size_add(&memory_bytes, image->mvs_save_ram_size) ||
        !gn_state_size_add(&memory_bytes, image->mvs_palette_ram_size) ||
        image->mvs_video_ram_words > SIZE_MAX / sizeof(uint16_t) ||
        !gn_state_size_add(&memory_bytes,
            image->mvs_video_ram_words * sizeof(uint16_t)))
        return GN_STATUS_INVALID_MEDIA;
    size_t capacity = GN_STATE_HEADER_V1_SIZE;
    const size_t section_headers = (size_t)GN_STATE_MVS_SECTION_COUNT * 8u;
    const size_t payloads[] = {
        GN_STATE_CPU_BYTES, memory_bytes, GN_STATE_MVS_BOARD_BYTES,
        GN_STATE_MVS_SOUND_FIXED_BYTES + z80_candidate_state_size(), ym_bytes
    };
    if (!gn_state_size_add(&capacity, section_headers))
        return GN_STATUS_INVALID_MEDIA;
    for (size_t index = 0u; index < sizeof(payloads) / sizeof(payloads[0]);
         ++index) {
        if (payloads[index] > UINT32_MAX ||
            !gn_state_size_add(&capacity, payloads[index]))
            return GN_STATUS_INVALID_MEDIA;
    }
    if (capacity > UINT32_MAX) return GN_STATUS_INVALID_MEDIA;
    *out_capacity = capacity;
    return GN_STATUS_OK;
}

static int gn_state_range_valid(const void *pointer, size_t length) {
    if (length == 0u) return 1;
    if (pointer == NULL) return 0;
    const uintptr_t start = (uintptr_t)pointer;
    return (uintmax_t)length <= (uintmax_t)(UINTPTR_MAX - start);
}

static int gn_state_ranges_overlap(const void *left, size_t left_size,
                                   const void *right, size_t right_size) {
    if (left_size == 0u || right_size == 0u) return 0;
    if (!gn_state_range_valid(left, left_size) ||
        !gn_state_range_valid(right, right_size)) return 1;
    const uintptr_t left_start = (uintptr_t)left;
    const uintptr_t right_start = (uintptr_t)right;
    const uintptr_t left_end = left_start + (uintptr_t)left_size;
    const uintptr_t right_end = right_start + (uintptr_t)right_size;
    return left_start < right_end && right_start < left_end;
}

static int gn_state_overlaps_owned(const gn_instance *instance,
                                   const void *buffer, size_t length) {
    if (instance == NULL || buffer == NULL || length == 0u) return 0;
    if (gn_state_ranges_overlap(buffer, length, instance, sizeof(*instance))) return 1;
    const gn_image *image = instance->image;
    if (image == NULL) return 0;
    if (gn_state_ranges_overlap(buffer, length, image, sizeof(*image)) ||
        gn_state_ranges_overlap(buffer, length, image->rom.bytes, image->rom.size) ||
        gn_state_ranges_overlap(buffer, length, image->ram.bytes, image->ram.size) ||
        gn_state_ranges_overlap(buffer, length, image->ram_seed,
                                image->ram_seed_size) ||
        owned_cpu_buffer_overlaps(image->cpu, buffer, length)) return 1;
    for (size_t index = 0u; index < image->mvs_region_count; ++index) {
        if (gn_state_ranges_overlap(buffer, length,
                image->mvs_regions[index].bytes,
                image->mvs_regions[index].size)) return 1;
    }
    if (gn_state_ranges_overlap(buffer, length, image->mvs_work_ram,
                                image->mvs_work_ram_size) ||
        gn_state_ranges_overlap(buffer, length, image->mvs_save_ram,
                                image->mvs_save_ram_size) ||
        gn_state_ranges_overlap(buffer, length, image->mvs_palette_ram,
                                image->mvs_palette_ram_size)) return 1;
    if (image->mvs_video_ram_words != 0u &&
        gn_state_ranges_overlap(buffer, length, image->mvs_video_ram,
                                image->mvs_video_ram_words * sizeof(uint16_t))) return 1;
    return 0;
}

static int gn_state_detail_args_valid(const gn_state_detail_v1 *detail,
                                      size_t detail_size) {
    if (detail == NULL) return detail_size == 0u;
    return detail_size == sizeof(*detail) &&
        ((uintptr_t)detail % _Alignof(gn_state_detail_v1)) == 0u;
}

static void gn_state_set_detail(gn_state_detail_v1 *detail,
                                gn_state_reason reason, uint32_t section,
                                uint32_t field, uint32_t offset) {
    if (detail == NULL) return;
    detail->size = (uint32_t)sizeof(*detail);
    detail->reason = reason;
    detail->section = section;
    detail->field = field;
    detail->offset = offset;
}

static gn_status gn_state_fail(gn_state_detail_v1 *detail,
                               gn_state_reason reason, uint32_t section,
                               uint32_t field, uint32_t offset,
                               gn_status status) {
    gn_state_set_detail(detail, reason, section, field, offset);
    return status;
}

static void gn_state_write_u16(uint8_t **cursor, uint16_t value) {
    *(*cursor)++ = (uint8_t)(value >> 8);
    *(*cursor)++ = (uint8_t)value;
}

static void gn_state_write_u32(uint8_t **cursor, uint32_t value) {
    *(*cursor)++ = (uint8_t)(value >> 24);
    *(*cursor)++ = (uint8_t)(value >> 16);
    *(*cursor)++ = (uint8_t)(value >> 8);
    *(*cursor)++ = (uint8_t)value;
}

static void gn_state_write_u64(uint8_t **cursor, uint64_t value) {
    gn_state_write_u32(cursor, (uint32_t)(value >> 32));
    gn_state_write_u32(cursor, (uint32_t)value);
}

static uint16_t gn_state_read_u16(const uint8_t **cursor) {
    const uint16_t value = (uint16_t)(((uint16_t)(*cursor)[0] << 8) |
                                      (uint16_t)(*cursor)[1]);
    *cursor += 2u;
    return value;
}

static uint32_t gn_state_read_u32(const uint8_t **cursor) {
    const uint32_t value = gn_read32_be(*cursor);
    *cursor += 4u;
    return value;
}

static uint64_t gn_state_read_u64(const uint8_t **cursor) {
    const uint64_t high = gn_state_read_u32(cursor);
    const uint64_t low = gn_state_read_u32(cursor);
    return (high << 32) | low;
}

typedef struct {
    uint16_t frame_input;
    uint32_t inputs;
    uint16_t mslugx_command;
    uint16_t mslugx_counter;
    uint8_t program_bank;
    uint32_t unmapped_write_count;
    uint32_t watchdog_pet_count;
    uint32_t watchdog_reset_count;
    uint16_t video_offset;
    uint16_t video_modulo;
    uint16_t video_read_buffer;
    uint8_t animation_speed;
    uint8_t animation_disabled;
    uint8_t animation_counter;
    uint8_t animation_frame_counter;
    uint8_t display_interrupt_control;
    uint8_t irq_pending_mask;
    uint32_t frame_cycle;
    uint64_t frame_cycle_carry;
    uint32_t frame_count;
    uint8_t output_data;
    uint8_t output_latch;
    uint8_t use_cart_vectors;
    uint8_t cart_audio_selected;
    uint8_t memcard_lock1;
    uint8_t memcard_unlock2;
    uint8_t coin_lockout_mask;
    uint8_t save_ram_unlocked;
    uint8_t palette_bank_selected;
    uint8_t screen_shadow;
    uint32_t watchdog_pet_generation;
    uint64_t watchdog_remaining_cycles;
    uint64_t sound_step_cycles;
    uint64_t completed_main_instructions;
    gn_mvs_calendar calendar;
    gn_mvs_protocol protocol;
} gn_state_mvs_board;

typedef struct {
    uint8_t cart_selected;
    uint8_t ym_irq;
    uint8_t command;
    uint8_t reply;
    uint8_t command_pending;
    uint8_t nmi_enabled;
    uint8_t main_clock_remainder;
    uint8_t ram[GN_MVS_SOUND_RAM_BYTES];
    uint8_t banks[4];
    int32_t pcm_history[GN_MVS_PCM_FILTER_TAPS];
    int32_t pcm_right_history[GN_MVS_PCM_FILTER_TAPS];
    uint32_t pcm_history_next;
    uint16_t pcm_output_phase;
} gn_state_mvs_sound;

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
static void gn_state_resource_charge(gn_instance *instance, unsigned phase,
                                      size_t bytes) {
    gn_test_state_resources *r = &instance->state_resources;
    const uint32_t bit = UINT32_C(1) << phase;
    if ((r->phase_mask & bit) != 0u) r->repeated_phase = 1u;
    r->phase_mask |= bit;
    ++r->phases;
    r->byte_work += bytes;
}

gn_status gn_test_state_resources_read(const gn_instance *instance,
                                       gn_test_state_resources *out) {
    if (instance == NULL || out == NULL || instance->image == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    const gn_image *image = instance->image;
    *out = instance->state_resources;
    const size_t cpu = sizeof(owned_cpu_state);
    if (image->mvs_region_count == 0u) {
        out->input_bytes = GN_STATE_MAX_SIZE_V1;
        out->stack_staging_bytes = 2u * cpu + GN_RAM_SIZE;
        out->heap_staging_bytes = 0u;
        out->phase_limit = 4u;
        out->byte_work_limit = GN_STATE_HEADER_V1_SIZE + 16u +
            GN_STATE_CPU_BYTES + 3u * cpu + 2u * GN_RAM_SIZE;
    } else {
        const size_t z80_heap = z80_candidate_state_heap_bound();
        const size_t ym_heap = ym2610_candidate_state_heap_bound();
        const size_t memory = image->mvs_work_ram_size +
            image->mvs_save_ram_size + image->mvs_palette_ram_size +
            image->mvs_video_ram_words * sizeof(uint16_t);
        const size_t fixed = GN_STATE_HEADER_V1_SIZE + 40u +
            GN_STATE_CPU_BYTES + memory + GN_STATE_MVS_BOARD_BYTES +
            GN_STATE_MVS_SOUND_FIXED_BYTES + z80_candidate_state_size();
        const size_t ym_wire = image->mvs_state_capacity - fixed;
        out->ym_bytes_limit = ym_wire;
        out->input_bytes = image->mvs_state_capacity;
        out->stack_staging_bytes = 2u * cpu + sizeof(gn_state_mvs_board) +
            sizeof(gn_state_mvs_sound) + z80_candidate_state_stack_bound() +
            ym2610_candidate_state_stack_bound();
        out->heap_staging_bytes = z80_heap + ym_heap;
        out->phase_limit = 9u;
        out->byte_work_limit = GN_STATE_HEADER_V1_SIZE + 40u +
            GN_STATE_CPU_BYTES + 2u * GN_STATE_MVS_BOARD_BYTES +
            2u * sizeof(gn_state_mvs_board) + GN_STATE_MVS_SOUND_FIXED_BYTES +
            2u * sizeof(gn_state_mvs_sound) + z80_candidate_state_size() +
            4u * z80_heap + z80_candidate_state_stack_bound() +
            ym_wire + 2u * ym_heap + 3u * cpu + memory;
    }
    out->staging_bytes = out->stack_staging_bytes + out->heap_staging_bytes;
    return GN_STATUS_OK;
}
#define GN_STATE_CHARGE(i, p, b) gn_state_resource_charge((i), (p), (b))
#else
#define GN_STATE_CHARGE(i, p, b) ((void)0)
#endif

static void gn_state_encode_calendar(const gn_mvs_calendar *calendar,
                                     uint8_t **cursor) {
    memcpy(*cursor, calendar->time_counter, sizeof(calendar->time_counter));
    *cursor += sizeof(calendar->time_counter);
    memcpy(*cursor, calendar->shift_reg, sizeof(calendar->shift_reg));
    *cursor += sizeof(calendar->shift_reg);
    *(*cursor)++ = calendar->data_in;
    *(*cursor)++ = calendar->clk;
    *(*cursor)++ = calendar->stb;
    *(*cursor)++ = calendar->command;
    *(*cursor)++ = calendar->data_out;
    *(*cursor)++ = calendar->tp;
    *(*cursor)++ = calendar->clock_running;
    *(*cursor)++ = calendar->data_out_running;
    *(*cursor)++ = calendar->tp_running;
    gn_state_write_u32(cursor, calendar->tick_remainder);
    gn_state_write_u32(cursor, calendar->clock_remaining);
    gn_state_write_u32(cursor, calendar->data_out_remaining);
    gn_state_write_u32(cursor, calendar->data_out_period);
    gn_state_write_u32(cursor, calendar->tp_remaining);
    gn_state_write_u32(cursor, calendar->tp_period);
}

static void gn_state_decode_calendar(const uint8_t **cursor,
                                     gn_mvs_calendar *calendar) {
    memset(calendar, 0, sizeof(*calendar));
    memcpy(calendar->time_counter, *cursor, sizeof(calendar->time_counter));
    *cursor += sizeof(calendar->time_counter);
    memcpy(calendar->shift_reg, *cursor, sizeof(calendar->shift_reg));
    *cursor += sizeof(calendar->shift_reg);
    calendar->data_in = *(*cursor)++;
    calendar->clk = *(*cursor)++;
    calendar->stb = *(*cursor)++;
    calendar->command = *(*cursor)++;
    calendar->data_out = *(*cursor)++;
    calendar->tp = *(*cursor)++;
    calendar->clock_running = *(*cursor)++;
    calendar->data_out_running = *(*cursor)++;
    calendar->tp_running = *(*cursor)++;
    calendar->tick_remainder = gn_state_read_u32(cursor);
    calendar->clock_remaining = gn_state_read_u32(cursor);
    calendar->data_out_remaining = gn_state_read_u32(cursor);
    calendar->data_out_period = gn_state_read_u32(cursor);
    calendar->tp_remaining = gn_state_read_u32(cursor);
    calendar->tp_period = gn_state_read_u32(cursor);
}

static void gn_state_encode_protocol(const gn_mvs_protocol *protocol,
                                     uint8_t **cursor) {
    for (size_t index = 0u; index < GN_MVS_PROTOCOL_TRACE_CAPACITY; ++index) {
        const gn_mvs_protocol_event *event = &protocol->events[index];
        gn_state_write_u32(cursor, event->address);
        *(*cursor)++ = event->kind;
        *(*cursor)++ = event->value;
        *(*cursor)++ = event->writer_pc_region;
        *(*cursor)++ = 0u;
        gn_state_write_u64(cursor, event->total_cycles);
        gn_state_write_u64(cursor, event->sequence);
        gn_state_write_u64(cursor, event->input_sequence);
    }
    gn_state_write_u32(cursor, protocol->count);
    gn_state_write_u32(cursor, protocol->dropped);
    gn_state_write_u64(cursor, protocol->sequence);
    gn_state_write_u64(cursor, protocol->cycle_base);
    gn_state_write_u64(cursor, protocol->input_sequence);
    gn_state_write_u64(cursor, protocol->attract_input_sequence);
    gn_state_write_u64(cursor, protocol->coin_input_sequence);
    gn_state_write_u64(cursor, protocol->start_input_sequence);
    gn_state_write_u64(cursor, protocol->player_start_input_sequence);
    gn_state_write_u64(cursor, protocol->bios_p1_start_input_sequence);
    *(*cursor)++ = 0u; /* guest_active is a transient host call guard. */
    *(*cursor)++ = protocol->decided;
    *(*cursor)++ = protocol->corroborated;
    *(*cursor)++ = protocol->attract_start_reached;
    *(*cursor)++ = protocol->user_request;
    *(*cursor)++ = protocol->player_start_entered;
    *(*cursor)++ = protocol->player_start_with_p1_indication;
    for (size_t index = 0u; index < GN_MVS_POLLED_TABLE_CAPACITY; ++index) {
        gn_state_write_u32(cursor, protocol->polled[index].address);
        gn_state_write_u64(cursor, protocol->polled[index].reads);
    }
    gn_state_write_u32(cursor, protocol->polled_count);
    gn_state_write_u64(cursor, protocol->polled_untracked_reads);
    gn_state_write_u64(cursor, protocol->interrupts_taken);
    gn_state_write_u64(cursor, protocol->irq_ack_writes);
    for (size_t index = 0u; index < GN_MVS_SR_MASK_BUCKETS; ++index)
        gn_state_write_u64(cursor, protocol->sr_mask_histogram[index]);
    for (size_t index = 0u; index < GN_MVS_PC_REGION_BUCKETS; ++index)
        gn_state_write_u64(cursor, protocol->pc_region_histogram[index]);
    gn_state_write_u64(cursor, protocol->low_program_window_reads);
    gn_state_write_u64(cursor, protocol->unmapped_read_count);
}

static void gn_state_decode_protocol(const uint8_t **cursor,
                                     gn_mvs_protocol *protocol) {
    memset(protocol, 0, sizeof(*protocol));
    for (size_t index = 0u; index < GN_MVS_PROTOCOL_TRACE_CAPACITY; ++index) {
        gn_mvs_protocol_event *event = &protocol->events[index];
        event->address = gn_state_read_u32(cursor);
        event->kind = *(*cursor)++;
        event->value = *(*cursor)++;
        event->writer_pc_region = *(*cursor)++;
        (void)*(*cursor)++; /* checked as zero by section validation */
        event->total_cycles = gn_state_read_u64(cursor);
        event->sequence = gn_state_read_u64(cursor);
        event->input_sequence = gn_state_read_u64(cursor);
    }
    protocol->count = gn_state_read_u32(cursor);
    protocol->dropped = gn_state_read_u32(cursor);
    protocol->sequence = gn_state_read_u64(cursor);
    protocol->cycle_base = gn_state_read_u64(cursor);
    protocol->input_sequence = gn_state_read_u64(cursor);
    protocol->attract_input_sequence = gn_state_read_u64(cursor);
    protocol->coin_input_sequence = gn_state_read_u64(cursor);
    protocol->start_input_sequence = gn_state_read_u64(cursor);
    protocol->player_start_input_sequence = gn_state_read_u64(cursor);
    protocol->bios_p1_start_input_sequence = gn_state_read_u64(cursor);
    (void)*(*cursor)++; /* guest_active is never persisted. */
    protocol->guest_active = 0u;
    protocol->decided = *(*cursor)++;
    protocol->corroborated = *(*cursor)++;
    protocol->attract_start_reached = *(*cursor)++;
    protocol->user_request = *(*cursor)++;
    protocol->player_start_entered = *(*cursor)++;
    protocol->player_start_with_p1_indication = *(*cursor)++;
    for (size_t index = 0u; index < GN_MVS_POLLED_TABLE_CAPACITY; ++index) {
        protocol->polled[index].address = gn_state_read_u32(cursor);
        protocol->polled[index].reads = gn_state_read_u64(cursor);
    }
    protocol->polled_count = gn_state_read_u32(cursor);
    protocol->polled_untracked_reads = gn_state_read_u64(cursor);
    protocol->interrupts_taken = gn_state_read_u64(cursor);
    protocol->irq_ack_writes = gn_state_read_u64(cursor);
    for (size_t index = 0u; index < GN_MVS_SR_MASK_BUCKETS; ++index)
        protocol->sr_mask_histogram[index] = gn_state_read_u64(cursor);
    for (size_t index = 0u; index < GN_MVS_PC_REGION_BUCKETS; ++index)
        protocol->pc_region_histogram[index] = gn_state_read_u64(cursor);
    protocol->low_program_window_reads = gn_state_read_u64(cursor);
    protocol->unmapped_read_count = gn_state_read_u64(cursor);
}

static int gn_state_valid_bcd(uint8_t value, unsigned maximum,
                              unsigned minimum) {
    const unsigned tens = (unsigned)(value >> 4);
    const unsigned ones = (unsigned)(value & 15u);
    if (tens > 9u || ones > 9u) return 0;
    const unsigned decoded = tens * 10u + ones;
    return decoded >= minimum && decoded <= maximum;
}

static int gn_state_calendar_valid(const gn_mvs_calendar *calendar) {
    const unsigned month = (unsigned)(calendar->time_counter[4] >> 4);
    const unsigned weekday = (unsigned)(calendar->time_counter[4] & 15u);
    if (!gn_state_valid_bcd(calendar->time_counter[0], 59u, 0u) ||
        !gn_state_valid_bcd(calendar->time_counter[1], 59u, 0u) ||
        !gn_state_valid_bcd(calendar->time_counter[2], 23u, 0u) ||
        !gn_state_valid_bcd(calendar->time_counter[3], 31u, 1u) ||
        !gn_state_valid_bcd(calendar->time_counter[5], 99u, 0u) ||
        month == 0u || month > 12u || weekday > 6u ||
        calendar->data_in > 1u || calendar->clk > 1u ||
        calendar->stb > 1u || calendar->command > 15u ||
        calendar->data_out > 1u || calendar->tp > 1u ||
        calendar->clock_running > 1u || calendar->data_out_running > 1u ||
        calendar->tp_running > 1u ||
        calendar->tick_remainder >= GN_MVS_CAL_TICK_DENOMINATOR ||
        calendar->clock_remaining > GN_MVS_CAL_SECOND_TICKS ||
        calendar->data_out_period > GN_MVS_CAL_HALF_SECOND_TICKS ||
        calendar->data_out_remaining > calendar->data_out_period ||
        calendar->tp_remaining > calendar->tp_period)
        return 0;
    if (calendar->data_out_running != 0u &&
        calendar->data_out_period != GN_MVS_CAL_HALF_SECOND_TICKS)
        return 0;
    if (calendar->tp_running != 0u) {
        const uint32_t period = calendar->tp_period;
        if (period != 4u && period != 8u && period != 64u &&
            period != 256u && period != GN_MVS_CAL_HALF_SECOND_TICKS &&
            period != GN_MVS_CAL_HALF_SECOND_TICKS * 10u &&
            period != GN_MVS_CAL_HALF_SECOND_TICKS * 30u &&
            period != GN_MVS_CAL_HALF_SECOND_TICKS * 60u)
            return 0;
    }
    return 1;
}

static int gn_state_protocol_valid(const gn_mvs_protocol *protocol,
                                  const uint8_t *section) {
    const size_t flags_offset =
        (size_t)GN_MVS_PROTOCOL_TRACE_CAPACITY *
            GN_STATE_MVS_PROTOCOL_EVENT_BYTES +
        (size_t)8u + (size_t)64u;
    if (protocol->count > GN_MVS_PROTOCOL_TRACE_CAPACITY ||
        protocol->polled_count > GN_MVS_POLLED_TABLE_CAPACITY ||
        section[flags_offset] != 0u ||
        protocol->decided > 1u || protocol->corroborated > 1u ||
        protocol->attract_start_reached > 1u ||
        protocol->player_start_entered > 1u ||
        protocol->player_start_with_p1_indication > 1u ||
        (protocol->user_request != 0u && protocol->user_request != 2u &&
         protocol->user_request != 3u)) return 0;
    const uint8_t *cursor = section;
    for (size_t index = 0u; index < GN_MVS_PROTOCOL_TRACE_CAPACITY; ++index) {
        const uint32_t address = gn_state_read_u32(&cursor);
        const uint8_t kind = *cursor++;
        (void)*cursor++;
        const uint8_t region = *cursor++;
        const uint8_t reserved = *cursor++;
        cursor += 24u;
        if (reserved != 0u || region > GN_MVS_PC_OTHER ||
            (index < protocol->count &&
             (kind < GN_MVS_PROTOCOL_BIOS_VAR_WRITE ||
              kind > GN_MVS_PROTOCOL_PLAYER_START_FETCH)) ||
            (index >= protocol->count && kind != 0u &&
             (kind < GN_MVS_PROTOCOL_BIOS_VAR_WRITE ||
              kind > GN_MVS_PROTOCOL_PLAYER_START_FETCH))) return 0;
        if (index < protocol->count && address > UINT32_C(0x00ffffff))
            return 0;
    }
    for (size_t index = 0u; index < protocol->polled_count; ++index) {
        const uint32_t address = protocol->polled[index].address;
        const int public_window =
            (address >= UINT32_C(0x300000) && address <= UINT32_C(0x3fffff)) ||
            (address >= UINT32_C(0x2fffe0) && address <= UINT32_C(0x2fffff));
        if (!public_window || protocol->polled[index].reads == 0u) return 0;
    }
    return 1;
}

static void gn_state_encode_board(const gn_image *image,
                                  uint8_t *destination) {
    const uint8_t *start = destination;
    uint8_t *cursor = destination;
    gn_state_write_u16(&cursor, image->frame_input);
    gn_state_write_u32(&cursor, image->mvs_inputs);
    gn_state_write_u16(&cursor, image->mvs_mslugx_command);
    gn_state_write_u16(&cursor, image->mvs_mslugx_counter);
    *cursor++ = image->mvs_program_bank;
    gn_state_write_u32(&cursor, image->mvs_mame_unmapped_write_count);
    gn_state_write_u32(&cursor, image->mvs_watchdog_pet_count);
    gn_state_write_u32(&cursor, image->mvs_watchdog_reset_count);
    gn_state_write_u16(&cursor, image->mvs_video_ram_offset);
    gn_state_write_u16(&cursor, image->mvs_video_ram_modulo);
    gn_state_write_u16(&cursor, image->mvs_video_ram_read_buffer);
    *cursor++ = image->mvs_video_auto_animation_speed;
    *cursor++ = image->mvs_video_auto_animation_disabled;
    *cursor++ = image->mvs_video_auto_animation_counter;
    *cursor++ = image->mvs_video_auto_animation_frame_counter;
    *cursor++ = image->mvs_display_position_interrupt_control;
    *cursor++ = image->mvs_irq_pending_mask;
    gn_state_write_u32(&cursor, image->mvs_frame_cycle);
    gn_state_write_u64(&cursor, image->mvs_frame_cycle_carry);
    gn_state_write_u32(&cursor, image->mvs_frame_count);
    *cursor++ = image->mvs_output_data;
    *cursor++ = image->mvs_output_latch;
    *cursor++ = image->mvs_use_cart_vectors;
    *cursor++ = image->mvs_cart_audio_selected;
    *cursor++ = image->mvs_memcard_lock1;
    *cursor++ = image->mvs_memcard_unlock2;
    *cursor++ = image->mvs_coin_lockout_mask;
    *cursor++ = image->mvs_save_ram_unlocked;
    *cursor++ = image->mvs_palette_bank_selected;
    *cursor++ = image->mvs_screen_shadow;
    gn_state_write_u32(&cursor, image->mvs_watchdog_pet_generation);
    gn_state_write_u64(&cursor, image->mvs_watchdog_remaining_cycles);
    gn_state_write_u64(&cursor, image->mvs_sound_step_cycles);
    gn_state_write_u64(&cursor, image->mvs_completed_main_instructions);
    gn_state_encode_calendar(&image->mvs_calendar, &cursor);
    gn_state_encode_protocol(&image->mvs_protocol, &cursor);
    (void)start;
}

static int gn_state_decode_board(const uint8_t *bytes,
                                 gn_state_mvs_board *board) {
    memset(board, 0, sizeof(*board));
    const uint8_t *cursor = bytes;
    board->frame_input = gn_state_read_u16(&cursor);
    board->inputs = gn_state_read_u32(&cursor);
    board->mslugx_command = gn_state_read_u16(&cursor);
    board->mslugx_counter = gn_state_read_u16(&cursor);
    board->program_bank = *cursor++;
    board->unmapped_write_count = gn_state_read_u32(&cursor);
    board->watchdog_pet_count = gn_state_read_u32(&cursor);
    board->watchdog_reset_count = gn_state_read_u32(&cursor);
    board->video_offset = gn_state_read_u16(&cursor);
    board->video_modulo = gn_state_read_u16(&cursor);
    board->video_read_buffer = gn_state_read_u16(&cursor);
    board->animation_speed = *cursor++;
    board->animation_disabled = *cursor++;
    board->animation_counter = *cursor++;
    board->animation_frame_counter = *cursor++;
    board->display_interrupt_control = *cursor++;
    board->irq_pending_mask = *cursor++;
    board->frame_cycle = gn_state_read_u32(&cursor);
    board->frame_cycle_carry = gn_state_read_u64(&cursor);
    board->frame_count = gn_state_read_u32(&cursor);
    board->output_data = *cursor++;
    board->output_latch = *cursor++;
    board->use_cart_vectors = *cursor++;
    board->cart_audio_selected = *cursor++;
    board->memcard_lock1 = *cursor++;
    board->memcard_unlock2 = *cursor++;
    board->coin_lockout_mask = *cursor++;
    board->save_ram_unlocked = *cursor++;
    board->palette_bank_selected = *cursor++;
    board->screen_shadow = *cursor++;
    board->watchdog_pet_generation = gn_state_read_u32(&cursor);
    board->watchdog_remaining_cycles = gn_state_read_u64(&cursor);
    board->sound_step_cycles = gn_state_read_u64(&cursor);
    board->completed_main_instructions = gn_state_read_u64(&cursor);
    gn_state_decode_calendar(&cursor, &board->calendar);
    gn_state_decode_protocol(&cursor, &board->protocol);
    if ((size_t)(cursor - bytes) != GN_STATE_MVS_BOARD_BYTES) return 0;
    if ((board->inputs & ~GN_MVS_INPUT_SUPPORTED_MASK) != 0u ||
        board->program_bank > 3u ||
        board->video_offset >= GN_MVS_VIDEO_RAM_WORDS ||
        board->animation_disabled > 1u ||
        board->display_interrupt_control > 0xf0u ||
        (board->display_interrupt_control & 0x0fu) != 0u ||
        (board->irq_pending_mask & (uint8_t)~7u) != 0u ||
        board->frame_cycle >= GN_MVS_FRAME_CYCLES ||
        board->frame_cycle_carry >= GN_MVS_FRAME_BUDGET_CYCLES ||
        board->use_cart_vectors > 1u || board->cart_audio_selected > 1u ||
        board->memcard_lock1 > 1u || board->memcard_unlock2 > 1u ||
        board->coin_lockout_mask > 7u || board->save_ram_unlocked > 1u ||
        board->palette_bank_selected > 1u || board->screen_shadow > 1u ||
        board->watchdog_remaining_cycles > GN_MVS_WATCHDOG_MAIN_CYCLES ||
        !gn_state_calendar_valid(&board->calendar) ||
        !gn_state_protocol_valid(&board->protocol, bytes + 135u))
        return 0;
    return 1;
}

static void gn_state_encode_mvs_sound(const gn_mvs_sound *sound,
                                      uint8_t *destination) {
    uint8_t *cursor = destination;
    *cursor++ = sound->cart_selected;
    *cursor++ = sound->ym_irq;
    *cursor++ = sound->command;
    *cursor++ = sound->reply;
    *cursor++ = sound->command_pending;
    *cursor++ = sound->nmi_enabled;
    *cursor++ = sound->main_clock_remainder;
    memcpy(cursor, sound->ram, sizeof(sound->ram));
    cursor += sizeof(sound->ram);
    memcpy(cursor, sound->banks, sizeof(sound->banks));
    cursor += sizeof(sound->banks);
    for (size_t index = 0u; index < GN_MVS_PCM_FILTER_TAPS; ++index) {
        uint32_t bits = 0u;
        memcpy(&bits, &sound->pcm_history[index], sizeof(bits));
        gn_state_write_u32(&cursor, bits);
    }
    for (size_t index = 0u; index < GN_MVS_PCM_FILTER_TAPS; ++index) {
        uint32_t bits = 0u;
        memcpy(&bits, &sound->pcm_right_history[index], sizeof(bits));
        gn_state_write_u32(&cursor, bits);
    }
    gn_state_write_u32(&cursor, (uint32_t)sound->pcm_history_next);
    gn_state_write_u16(&cursor, sound->pcm_output_phase);
}

static int gn_state_decode_mvs_sound(const uint8_t *bytes,
                                     gn_state_mvs_sound *sound) {
    memset(sound, 0, sizeof(*sound));
    const uint8_t *cursor = bytes;
    sound->cart_selected = *cursor++;
    sound->ym_irq = *cursor++;
    sound->command = *cursor++;
    sound->reply = *cursor++;
    sound->command_pending = *cursor++;
    sound->nmi_enabled = *cursor++;
    sound->main_clock_remainder = *cursor++;
    memcpy(sound->ram, cursor, sizeof(sound->ram));
    cursor += sizeof(sound->ram);
    memcpy(sound->banks, cursor, sizeof(sound->banks));
    cursor += sizeof(sound->banks);
    for (size_t index = 0u; index < GN_MVS_PCM_FILTER_TAPS; ++index) {
        const uint32_t bits = gn_state_read_u32(&cursor);
        memcpy(&sound->pcm_history[index], &bits, sizeof(bits));
    }
    for (size_t index = 0u; index < GN_MVS_PCM_FILTER_TAPS; ++index) {
        const uint32_t bits = gn_state_read_u32(&cursor);
        memcpy(&sound->pcm_right_history[index], &bits, sizeof(bits));
    }
    sound->pcm_history_next = gn_state_read_u32(&cursor);
    sound->pcm_output_phase = gn_state_read_u16(&cursor);
    return (size_t)(cursor - bytes) == GN_STATE_MVS_SOUND_FIXED_BYTES &&
        sound->cart_selected <= 1u && sound->ym_irq <= 1u &&
        sound->command_pending <= 1u && sound->nmi_enabled <= 1u &&
        sound->main_clock_remainder < 3u &&
        sound->pcm_history_next < GN_MVS_PCM_FILTER_TAPS &&
        sound->pcm_output_phase < 125u;
}

static int gn_state_mvs_ym_irq_relation_valid(
    const gn_state_mvs_sound *sound, const ym2610_candidate *candidate) {
    uint8_t chip_irq = 0u;
    return sound != NULL && candidate != NULL &&
        ym2610_candidate_state_irq_line(candidate, &chip_irq) ==
            YM2610_CANDIDATE_OK &&
        sound->ym_irq == chip_irq;
}

static void gn_state_encode_cpu(const owned_cpu_state *state, uint8_t *bytes) {
    uint8_t *cursor = bytes;
    for (unsigned index = 0u; index < 8u; ++index)
        gn_state_write_u32(&cursor, state->data_registers[index]);
    for (unsigned index = 0u; index < 8u; ++index)
        gn_state_write_u32(&cursor, state->address_registers[index]);
    gn_state_write_u32(&cursor, state->pc);
    gn_state_write_u32(&cursor, state->previous_pc);
    gn_state_write_u32(&cursor, state->usp);
    gn_state_write_u32(&cursor, state->ssp);
    gn_state_write_u32(&cursor, state->fault_pc);
    gn_state_write_u16(&cursor, state->sr);
    gn_state_write_u16(&cursor, state->instruction_register);
    *cursor++ = state->stopped;
    *cursor++ = state->irq_level;
    *cursor++ = state->irq7_pending;
    *cursor++ = state->reset_pending;
    *cursor++ = state->last_exception_vector;
    memset(cursor, 0, 3u);
    cursor += 3u;
    gn_state_write_u64(&cursor, state->instructions);
    gn_state_write_u64(&cursor, state->instruction_cycles);
    gn_state_write_u64(&cursor, state->reset_cycles);
    gn_state_write_u64(&cursor, state->exception_cycles);
    gn_state_write_u64(&cursor, state->idle_cycles);
    gn_state_write_u64(&cursor, state->total_cycles);
    gn_state_write_u64(&cursor, state->reset_signal_events);
}

static int gn_state_decode_cpu(const uint8_t *bytes, owned_cpu_state *state,
                               uint32_t *bad_field) {
    memset(state, 0, sizeof(*state));
    state->size = (uint32_t)sizeof(*state);
    state->version = OWNED_CPU_STATE_VERSION;
    memcpy(state->core_identity, OWNED_CPU_STATE_CORE_IDENTITY_SHA256,
           sizeof(state->core_identity));
    state->present_fields = OWNED_CPU_STATE_REQUIRED_FIELDS;
    const uint8_t *cursor = bytes;
    for (unsigned index = 0u; index < 8u; ++index)
        state->data_registers[index] = gn_state_read_u32(&cursor);
    for (unsigned index = 0u; index < 8u; ++index)
        state->address_registers[index] = gn_state_read_u32(&cursor);
    state->pc = gn_state_read_u32(&cursor);
    state->previous_pc = gn_state_read_u32(&cursor);
    state->usp = gn_state_read_u32(&cursor);
    state->ssp = gn_state_read_u32(&cursor);
    state->fault_pc = gn_state_read_u32(&cursor);
    state->sr = gn_state_read_u16(&cursor);
    state->instruction_register = gn_state_read_u16(&cursor);
    state->stopped = *cursor++;
    state->irq_level = *cursor++;
    state->irq7_pending = *cursor++;
    state->reset_pending = *cursor++;
    state->last_exception_vector = *cursor++;
    if (cursor[0] != 0u || cursor[1] != 0u || cursor[2] != 0u) {
        *bad_field = UINT32_C(1);
        return 0;
    }
    cursor += 3u;
    state->instructions = gn_state_read_u64(&cursor);
    state->instruction_cycles = gn_state_read_u64(&cursor);
    state->reset_cycles = gn_state_read_u64(&cursor);
    state->exception_cycles = gn_state_read_u64(&cursor);
    state->idle_cycles = gn_state_read_u64(&cursor);
    state->total_cycles = gn_state_read_u64(&cursor);
    state->reset_signal_events = gn_state_read_u64(&cursor);
    return (size_t)(cursor - bytes) == GN_STATE_CPU_BYTES;
}

static gn_status gn_state_loaded_diagnostic(const gn_instance *instance,
                                             gn_state_detail_v1 *detail) {
    if (instance == NULL)
        return gn_state_fail(detail, GN_STATE_REASON_INVALID_ARGUMENT, 0u, 0u,
                             0u, GN_STATUS_INVALID_ARGUMENT);
    if (instance->image == NULL)
        return gn_state_fail(detail, GN_STATE_REASON_INVALID_STATE, 0u, 0u,
                             0u, GN_STATUS_INVALID_STATE);
    const gn_image *image = instance->image;
    if (image->profile == GN_PROFILE_DIAGNOSTIC &&
        image->mvs_region_count == 0u &&
        image->diagnostic_media_identity_valid != 0u)
        return GN_STATUS_OK;
    if (image->profile == GN_MVS_PROFILE_MSX &&
        image->mvs_region_count != 0u &&
        image->mvs_media_identity_valid != 0u &&
        image->mvs_state_capacity != 0u)
        return GN_STATUS_OK;
    if (image->profile != GN_PROFILE_DIAGNOSTIC &&
        image->profile != GN_MVS_PROFILE_MSX)
        return gn_state_fail(detail, GN_STATE_REASON_UNSUPPORTED_PROFILE, 0u, 0u,
                             0u, GN_STATUS_UNSUPPORTED_PROFILE);
    if ((image->profile == GN_PROFILE_DIAGNOSTIC &&
         image->diagnostic_media_identity_valid == 0u) ||
        (image->profile == GN_MVS_PROFILE_MSX &&
         image->mvs_media_identity_valid == 0u))
        return gn_state_fail(detail, GN_STATE_REASON_INVALID_STATE, 0u, 0u,
                             0u, GN_STATUS_INVALID_STATE);
    return gn_state_fail(detail, GN_STATE_REASON_INVALID_STATE, 0u, 0u,
                         0u, GN_STATUS_INVALID_STATE);
}

static void gn_state_encode_image(const gn_image *image,
                                  const owned_cpu_state *cpu_state,
                                  uint8_t output[GN_STATE_MAX_SIZE_V1]) {
    memset(output, 0, GN_STATE_MAX_SIZE_V1);
    memcpy(output, "GNST", 4u);
    uint8_t *cursor = output + 4u;
    gn_state_write_u32(&cursor, GN_STATE_FORMAT_V1_VERSION);
    gn_state_write_u32(&cursor, (uint32_t)GN_STATE_HEADER_V1_SIZE);
    gn_state_write_u32(&cursor, (uint32_t)GN_STATE_MAX_SIZE_V1);
    gn_state_write_u32(&cursor, GN_STATE_FORMAT_V1_ID);
    gn_state_write_u32(&cursor, GN_STATE_REPLAY_V1_ID);
    gn_state_write_u32(&cursor, GN_PROFILE_DIAGNOSTIC);
    gn_state_write_u32(&cursor, GN_STATE_CONFIGURATION_DIAGNOSTIC_V1);
    memcpy(cursor, image->diagnostic_media_identity, 32u);
    cursor += 32u;
    gn_state_write_u32(&cursor, UINT32_C(2));
    gn_state_write_u32(&cursor, 0u);
    gn_state_write_u32(&cursor, GN_STATE_SECTION_CPU);
    gn_state_write_u32(&cursor, (uint32_t)GN_STATE_CPU_BYTES);
    gn_state_encode_cpu(cpu_state, cursor);
    cursor += GN_STATE_CPU_BYTES;
    gn_state_write_u32(&cursor, GN_STATE_SECTION_RAM);
    gn_state_write_u32(&cursor, (uint32_t)GN_STATE_RAM_BYTES);
    memcpy(cursor, image->ram.bytes, GN_STATE_RAM_BYTES);
}

static gn_status gn_state_encode_mvs_image(const gn_image *image,
                                           const owned_cpu_state *cpu_state,
                                           uint8_t *output) {
    if (image == NULL || cpu_state == NULL || output == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    const size_t capacity = image->mvs_state_capacity;
    memset(output, 0, capacity);
    memcpy(output, "GNST", 4u);
    uint8_t *cursor = output + 4u;
    gn_state_write_u32(&cursor, GN_STATE_FORMAT_V1_VERSION);
    gn_state_write_u32(&cursor, (uint32_t)GN_STATE_HEADER_V1_SIZE);
    gn_state_write_u32(&cursor, (uint32_t)capacity);
    gn_state_write_u32(&cursor, GN_STATE_FORMAT_V1_ID);
    gn_state_write_u32(&cursor, GN_STATE_REPLAY_V1_ID);
    gn_state_write_u32(&cursor, GN_MVS_PROFILE_MSX);
    gn_state_write_u32(&cursor, GN_STATE_MVS_CONFIGURATION_V1);
    memcpy(cursor, image->mvs_media_identity, 32u);
    cursor += 32u;
    gn_state_write_u32(&cursor, GN_STATE_MVS_SECTION_COUNT);
    gn_state_write_u32(&cursor, 0u);

    gn_state_write_u32(&cursor, GN_STATE_SECTION_CPU);
    gn_state_write_u32(&cursor, (uint32_t)GN_STATE_CPU_BYTES);
    gn_state_encode_cpu(cpu_state, cursor);
    cursor += GN_STATE_CPU_BYTES;

    const size_t memory_bytes = image->mvs_work_ram_size +
        image->mvs_save_ram_size + image->mvs_palette_ram_size +
        image->mvs_video_ram_words * sizeof(uint16_t);
    gn_state_write_u32(&cursor, GN_STATE_SECTION_MVS_MEMORY);
    gn_state_write_u32(&cursor, (uint32_t)memory_bytes);
    memcpy(cursor, image->mvs_work_ram, image->mvs_work_ram_size);
    cursor += image->mvs_work_ram_size;
    memcpy(cursor, image->mvs_save_ram, image->mvs_save_ram_size);
    cursor += image->mvs_save_ram_size;
    memcpy(cursor, image->mvs_palette_ram, image->mvs_palette_ram_size);
    cursor += image->mvs_palette_ram_size;
    for (size_t index = 0u; index < image->mvs_video_ram_words; ++index)
        gn_state_write_u16(&cursor, image->mvs_video_ram[index]);

    gn_state_write_u32(&cursor, GN_STATE_SECTION_MVS_BOARD);
    gn_state_write_u32(&cursor, (uint32_t)GN_STATE_MVS_BOARD_BYTES);
    gn_state_encode_board(image, cursor);
    cursor += GN_STATE_MVS_BOARD_BYTES;

    const size_t z80_bytes = z80_candidate_state_size();
    const size_t sound_bytes = z80_bytes + GN_STATE_MVS_SOUND_FIXED_BYTES;
    gn_state_write_u32(&cursor, GN_STATE_SECTION_MVS_SOUND);
    gn_state_write_u32(&cursor, (uint32_t)sound_bytes);
    size_t z80_written = 0u;
    if (z80_candidate_state_capture(image->mvs_sound.cpu, cursor, z80_bytes,
                                    &z80_written) != Z80_CANDIDATE_OK ||
        z80_written != z80_bytes) return GN_STATUS_CPU_FAILURE;
    cursor += z80_bytes;
    gn_state_encode_mvs_sound(&image->mvs_sound, cursor);
    cursor += GN_STATE_MVS_SOUND_FIXED_BYTES;

    size_t ym_written = 0u;
    size_t ym_bytes = 0u;
    const ym2610_candidate_status ym_size_status =
        ym2610_candidate_state_size(image->mvs_sound.ym, &ym_bytes);
    if (ym_size_status != YM2610_CANDIDATE_OK)
        return ym_size_status == YM2610_CANDIDATE_NO_MEMORY
            ? GN_STATUS_OUT_OF_MEMORY : GN_STATUS_CPU_FAILURE;
    size_t expected_capacity = GN_STATE_HEADER_V1_SIZE;
    if (!gn_state_size_add(&expected_capacity, 40u) ||
        !gn_state_size_add(&expected_capacity, GN_STATE_CPU_BYTES) ||
        !gn_state_size_add(&expected_capacity, memory_bytes) ||
        !gn_state_size_add(&expected_capacity, GN_STATE_MVS_BOARD_BYTES) ||
        !gn_state_size_add(&expected_capacity, sound_bytes) ||
        !gn_state_size_add(&expected_capacity, ym_bytes) ||
        expected_capacity != capacity)
        return GN_STATUS_INVALID_STATE;
    gn_state_write_u32(&cursor, GN_STATE_SECTION_MVS_YM2610);
    gn_state_write_u32(&cursor, (uint32_t)ym_bytes);
    const ym2610_candidate_status ym_capture_status =
        ym2610_candidate_state_capture(image->mvs_sound.ym, cursor, ym_bytes,
                                        &ym_written);
    if (ym_capture_status != YM2610_CANDIDATE_OK || ym_written != ym_bytes)
        return ym_capture_status == YM2610_CANDIDATE_NO_MEMORY
            ? GN_STATUS_OUT_OF_MEMORY : GN_STATUS_CPU_FAILURE;
    cursor += ym_bytes;
    return (size_t)(cursor - output) == capacity
        ? GN_STATUS_OK : GN_STATUS_INVALID_STATE;
}

static int gn_state_pointer_aligned(const void *pointer, size_t alignment) {
    return pointer != NULL && ((uintptr_t)pointer % alignment) == 0u;
}

GN_API gn_status gn_state_capacity_v1(const gn_instance *instance,
                                      size_t *out_capacity) {
    if (out_capacity == NULL ||
        !gn_state_pointer_aligned(out_capacity, _Alignof(size_t)) ||
        gn_state_overlaps_owned(instance, out_capacity, sizeof(*out_capacity)))
        return GN_STATUS_INVALID_ARGUMENT;
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    const gn_image *image = instance->image;
    if (image->profile == GN_PROFILE_DIAGNOSTIC &&
        image->mvs_region_count == 0u &&
        image->diagnostic_media_identity_valid != 0u) {
        *out_capacity = GN_STATE_MAX_SIZE_V1;
        return GN_STATUS_OK;
    }
    if (image->profile == GN_MVS_PROFILE_MSX &&
        image->mvs_region_count != 0u &&
        image->mvs_media_identity_valid != 0u &&
        image->mvs_state_capacity != 0u) {
        *out_capacity = image->mvs_state_capacity;
        return GN_STATUS_OK;
    }
    if (image->profile != GN_PROFILE_DIAGNOSTIC &&
        image->profile != GN_MVS_PROFILE_MSX)
        return GN_STATUS_UNSUPPORTED_PROFILE;
    return GN_STATUS_INVALID_STATE;
}

GN_API gn_status gn_state_capture_v1(gn_instance *instance, void *buffer,
                                     size_t capacity, size_t *out_written,
                                     gn_state_detail_v1 *detail,
                                     size_t detail_size) {
    if (out_written == NULL ||
        !gn_state_pointer_aligned(out_written, _Alignof(size_t)) ||
        !gn_state_range_valid(out_written, sizeof(*out_written)) ||
        gn_state_overlaps_owned(instance, out_written, sizeof(*out_written)))
        return GN_STATUS_INVALID_ARGUMENT;
    if ((buffer != NULL && capacity != 0u &&
         !gn_state_range_valid(buffer, capacity)) ||
        (detail != NULL && detail_size != 0u &&
         !gn_state_range_valid(detail, detail_size)))
        return GN_STATUS_INVALID_ARGUMENT;
    const size_t buffer_range = buffer == NULL ? 0u : capacity;
    const size_t detail_range = detail == NULL ? 0u : detail_size;
    if (gn_state_ranges_overlap(out_written, sizeof(*out_written),
                                buffer, buffer_range) ||
        gn_state_ranges_overlap(out_written, sizeof(*out_written), detail,
                                detail_range) ||
        gn_state_ranges_overlap(buffer, buffer_range, detail,
                                detail_range))
        return GN_STATUS_INVALID_ARGUMENT;
    *out_written = 0u;
    if (!gn_state_detail_args_valid(detail, detail_size))
        return GN_STATUS_INVALID_ARGUMENT;
    if (detail != NULL && gn_state_overlaps_owned(instance, detail,
                                                   sizeof(*detail)))
        return GN_STATUS_INVALID_ARGUMENT;
    gn_state_set_detail(detail, GN_STATE_REASON_NONE, 0u, 0u, 0u);
    if (buffer == NULL)
        return gn_state_fail(detail, GN_STATE_REASON_INVALID_ARGUMENT, 0u, 0u,
                             0u, GN_STATUS_INVALID_ARGUMENT);
    if (gn_state_overlaps_owned(instance, buffer, capacity))
        return gn_state_fail(detail, GN_STATE_REASON_ALIAS, 0u, 0u, 0u,
                             GN_STATUS_INVALID_ARGUMENT);
    gn_status status = gn_state_loaded_diagnostic(instance, detail);
    if (status != GN_STATUS_OK) return status;
    gn_image *image = instance->image;
    if (owned_cpu_is_active(image->cpu))
        return gn_state_fail(detail, GN_STATE_REASON_ACTIVE_CALL, 0u, 0u,
                             0u, GN_STATUS_INVALID_STATE);
    const int is_mvs = image->mvs_region_count != 0u;
    if ((!is_mvs && image->diagnostic_guest_faulted != 0u) ||
        (is_mvs && (image->mvs_failure.valid != 0u ||
                    image->mvs_bus_fault_valid != 0u ||
                    image->mvs_sound.failed != 0u ||
                    image->mvs_sound.pcm_capture_active != 0u ||
                    image->mvs_sound.pcm_active_sink != NULL)))
        return gn_state_fail(detail, GN_STATE_REASON_GUEST_FAULT, 0u, 0u,
                             0u, GN_STATUS_INVALID_STATE);
    const size_t required_capacity = is_mvs
        ? image->mvs_state_capacity : GN_STATE_MAX_SIZE_V1;
    if (capacity < required_capacity)
        return gn_state_fail(detail, GN_STATE_REASON_CAPACITY, 0u, 0u,
                             (uint32_t)capacity, GN_STATUS_INVALID_ARGUMENT);
    owned_cpu_state cpu_state;
    memset(&cpu_state, 0, sizeof(cpu_state));
    if (owned_cpu_capture_state(image->cpu, &cpu_state) != OWNED_CPU_OK)
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE, GN_STATE_SECTION_CPU,
                             0u, 0u, GN_STATUS_CPU_FAILURE);
    if (is_mvs != 0) {
        uint8_t *encoded = (uint8_t *)gn_allocate(
            &image->allocator, required_capacity);
        if (encoded == NULL)
            return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                                 GN_STATE_SECTION_MVS_SOUND, 0u, 0u,
                                 GN_STATUS_OUT_OF_MEMORY);
        status = gn_state_encode_mvs_image(image, &cpu_state, encoded);
        if (status == GN_STATUS_OK) {
            memcpy(buffer, encoded, required_capacity);
            *out_written = required_capacity;
        }
        gn_release(&image->allocator, encoded);
        if (status != GN_STATUS_OK)
            return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                                 GN_STATE_SECTION_MVS_SOUND, 0u, 0u, status);
    } else {
        uint8_t encoded[GN_STATE_MAX_SIZE_V1];
        gn_state_encode_image(image, &cpu_state, encoded);
        memcpy(buffer, encoded, sizeof(encoded));
        *out_written = sizeof(encoded);
    }
    gn_state_set_detail(detail, GN_STATE_REASON_NONE, 0u, 0u, 0u);
    return GN_STATUS_OK;
}

static gn_status gn_state_restore_mvs(gn_instance *instance,
                                      const uint8_t *input, size_t length,
                                      gn_state_detail_v1 *detail,
                                      int bypass_ym_irq_relation) {
    gn_image *image = instance->image;
#if defined(GLUEYNEO_SDK_TEST_HOOKS) && defined(Z80_CANDIDATE_TEST_HOOKS)
    z80_candidate_test_failpoint *failpoint =
        instance->state_failpoint_active != 0u
            ? &instance->state_failpoint : NULL;
#endif
    const size_t capacity = image->mvs_state_capacity;
    if (owned_cpu_is_active(image->cpu))
        return gn_state_fail(detail, GN_STATE_REASON_ACTIVE_CALL, 0u, 0u,
                             0u, GN_STATUS_INVALID_STATE);
    if (image->mvs_sound.pcm_capture_active != 0u ||
        image->mvs_sound.pcm_active_sink != NULL)
        return gn_state_fail(detail, GN_STATE_REASON_ACTIVE_CALL,
                             GN_STATE_SECTION_MVS_SOUND, 0u, 0u,
                             GN_STATUS_INVALID_STATE);
    if (length < capacity)
        return gn_state_fail(detail, GN_STATE_REASON_TRUNCATED, 0u, 0u,
                             (uint32_t)length, GN_STATUS_INVALID_ARGUMENT);
    if (length > capacity)
        return gn_state_fail(detail, GN_STATE_REASON_TRAILING_BYTES, 0u, 0u,
                             (uint32_t)capacity, GN_STATUS_INVALID_ARGUMENT);
    GN_STATE_CHARGE(instance, 0u, GN_STATE_HEADER_V1_SIZE + 40u);
    if (memcmp(input, "GNST", 4u) != 0 ||
        gn_read32_be(input + 4u) != GN_STATE_FORMAT_V1_VERSION ||
        gn_read32_be(input + 8u) != (uint32_t)GN_STATE_HEADER_V1_SIZE ||
        gn_read32_be(input + 12u) != (uint32_t)capacity ||
        gn_read32_be(input + 16u) != GN_STATE_FORMAT_V1_ID)
        return gn_state_fail(detail, GN_STATE_REASON_FORMAT, 0u, 0u, 4u,
                             GN_STATUS_INVALID_ARGUMENT);
    if (gn_read32_be(input + 20u) != GN_STATE_REPLAY_V1_ID)
        return gn_state_fail(detail, GN_STATE_REASON_REPLAY_IDENTITY, 0u, 0u,
                             20u, GN_STATUS_UNSUPPORTED_PROFILE);
    if (gn_read32_be(input + 24u) != GN_MVS_PROFILE_MSX)
        return gn_state_fail(detail, GN_STATE_REASON_PROFILE_IDENTITY, 0u, 0u,
                             24u, GN_STATUS_UNSUPPORTED_PROFILE);
    if (gn_read32_be(input + 28u) != GN_STATE_MVS_CONFIGURATION_V1)
        return gn_state_fail(detail, GN_STATE_REASON_CONFIGURATION_IDENTITY,
                             0u, 0u, 28u, GN_STATUS_UNSUPPORTED_PROFILE);
    if (memcmp(input + 32u, image->mvs_media_identity, 32u) != 0)
        return gn_state_fail(detail, GN_STATE_REASON_MEDIA_IDENTITY, 0u, 0u,
                             32u, GN_STATUS_INVALID_MEDIA);
    if (gn_read32_be(input + 64u) != GN_STATE_MVS_SECTION_COUNT)
        return gn_state_fail(detail, GN_STATE_REASON_SECTION, 0u, 0u, 64u,
                             GN_STATUS_INVALID_MEDIA);
    if (gn_read32_be(input + 68u) != 0u)
        return gn_state_fail(detail, GN_STATE_REASON_RESERVED, 0u, 0u, 68u,
                             GN_STATUS_INVALID_MEDIA);

    const size_t memory_bytes = image->mvs_work_ram_size +
        image->mvs_save_ram_size + image->mvs_palette_ram_size +
        image->mvs_video_ram_words * sizeof(uint16_t);
    const size_t sound_bytes = z80_candidate_state_size() +
        GN_STATE_MVS_SOUND_FIXED_BYTES;
    size_t ym_base = GN_STATE_HEADER_V1_SIZE;
    if (!gn_state_size_add(&ym_base, 40u) ||
        !gn_state_size_add(&ym_base, GN_STATE_CPU_BYTES) ||
        !gn_state_size_add(&ym_base, memory_bytes) ||
        !gn_state_size_add(&ym_base, GN_STATE_MVS_BOARD_BYTES) ||
        !gn_state_size_add(&ym_base, sound_bytes) || capacity < ym_base)
        return gn_state_fail(detail, GN_STATE_REASON_SECTION, 0u, 0u, 12u,
                             GN_STATUS_INVALID_STATE);
    const size_t ym_bytes = capacity - ym_base;
    const uint32_t expected_ids[5] = {
        GN_STATE_SECTION_CPU, GN_STATE_SECTION_MVS_MEMORY,
        GN_STATE_SECTION_MVS_BOARD, GN_STATE_SECTION_MVS_SOUND,
        GN_STATE_SECTION_MVS_YM2610
    };
    const size_t expected_lengths[5] = {
        GN_STATE_CPU_BYTES, memory_bytes, GN_STATE_MVS_BOARD_BYTES,
        sound_bytes, ym_bytes
    };
    const uint8_t *sections[5] = {0};
    const uint8_t *cursor = input + GN_STATE_HEADER_V1_SIZE;
    for (size_t index = 0u; index < 5u; ++index) {
        const size_t section_header_offset =
            (size_t)(cursor - input);
        const uint32_t section_id = gn_state_read_u32(&cursor);
        const uint32_t section_size = gn_state_read_u32(&cursor);
        if (section_id != expected_ids[index] ||
            (size_t)section_size != expected_lengths[index])
            return gn_state_fail(detail, GN_STATE_REASON_SECTION,
                                 expected_ids[index], (uint32_t)index,
                                 (uint32_t)section_header_offset,
                                 GN_STATUS_INVALID_MEDIA);
        sections[index] = cursor;
        cursor += section_size;
    }
    if ((size_t)(cursor - input) != capacity)
        return gn_state_fail(detail, GN_STATE_REASON_SECTION, 0u, 0u,
                             (uint32_t)(cursor - input),
                             GN_STATUS_INVALID_MEDIA);

    owned_cpu_state cpu_state;
    uint32_t bad_field = 0u;
    GN_STATE_CHARGE(instance, 1u, GN_STATE_CPU_BYTES);
    if (!gn_state_decode_cpu(sections[0], &cpu_state, &bad_field) ||
        owned_cpu_validate_state(&cpu_state) != OWNED_CPU_OK)
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                             GN_STATE_SECTION_CPU, bad_field,
                             (uint32_t)(sections[0] - input),
                             GN_STATUS_INVALID_MEDIA);
    gn_state_mvs_board board;
    GN_STATE_CHARGE(instance, 2u, 2u * GN_STATE_MVS_BOARD_BYTES +
                                  2u * sizeof(board));
    if (!gn_state_decode_board(sections[2], &board))
        return gn_state_fail(detail, GN_STATE_REASON_RESERVED,
                             GN_STATE_SECTION_MVS_BOARD, 0u,
                             (uint32_t)(sections[2] - input),
                             GN_STATUS_INVALID_MEDIA);
    const size_t z80_bytes = z80_candidate_state_size();
    gn_state_mvs_sound sound_state;
    GN_STATE_CHARGE(instance, 3u, GN_STATE_MVS_SOUND_FIXED_BYTES +
                                  2u * sizeof(sound_state));
    if (!gn_state_decode_mvs_sound(sections[3] + z80_bytes, &sound_state))
        return gn_state_fail(detail, GN_STATE_REASON_RESERVED,
                             GN_STATE_SECTION_MVS_SOUND, 0u,
                             (uint32_t)(sections[3] - input + z80_bytes),
                             GN_STATUS_INVALID_MEDIA);

    z80_candidate_state *staged_z80 = NULL;
    GN_STATE_CHARGE(instance, 4u, z80_bytes +
        3u * z80_candidate_state_heap_bound() +
        z80_candidate_state_stack_bound());
    const z80_candidate_status z80_status =
#if defined(GLUEYNEO_SDK_TEST_HOOKS) && defined(Z80_CANDIDATE_TEST_HOOKS)
        failpoint != NULL
            ? z80_candidate_state_test_stage(sections[3], z80_bytes,
                                             failpoint, &staged_z80)
            :
#endif
              z80_candidate_state_stage(sections[3], z80_bytes, &staged_z80);
    if (z80_status != Z80_CANDIDATE_OK)
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                             GN_STATE_SECTION_MVS_SOUND, 0u,
                             (uint32_t)(sections[3] - input),
                             z80_status == Z80_CANDIDATE_OUT_OF_MEMORY
                                 ? GN_STATUS_OUT_OF_MEMORY
                                 : GN_STATUS_INVALID_MEDIA);
    ym2610_candidate *staged_ym = NULL;
    ym2610_candidate_state_detail ym_detail;
    GN_STATE_CHARGE(instance, 5u, ym_bytes +
                                  2u * ym2610_candidate_state_heap_bound());
    const ym2610_candidate_status ym_status =
        ym2610_candidate_state_stage(sections[4], ym_bytes, &staged_ym,
                                     &ym_detail);
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    instance->state_resources.ym_bytes_read = ym_detail.consumed;
#endif
    if (ym_status != YM2610_CANDIDATE_OK) {
        z80_candidate_state_discard(staged_z80);
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                             GN_STATE_SECTION_MVS_YM2610,
                             (uint32_t)ym_detail.reason,
                             (uint32_t)(sections[4] - input + ym_detail.offset),
                             ym_status == YM2610_CANDIDATE_NO_MEMORY
                                 ? GN_STATUS_OUT_OF_MEMORY
                                 : GN_STATUS_INVALID_MEDIA);
    }
    if (!bypass_ym_irq_relation &&
        !gn_state_mvs_ym_irq_relation_valid(&sound_state, staged_ym)) {
        z80_candidate_state_discard(staged_z80);
        ym2610_candidate_destroy(staged_ym);
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                             GN_STATE_SECTION_MVS_SOUND, 0u,
                             (uint32_t)(sections[3] - input + z80_bytes + 1u),
                             GN_STATUS_INVALID_MEDIA);
    }
    z80_candidate *replacement_z80 = NULL;
    GN_STATE_CHARGE(instance, 6u, z80_candidate_state_heap_bound());
    gn_status status = gn_mvs_sound_prepare_state_rebind(
        &image->mvs_sound, staged_ym,
#if defined(Z80_CANDIDATE_TEST_HOOKS)
        failpoint,
#endif
        &replacement_z80);
    if (status != GN_STATUS_OK) {
        z80_candidate_state_discard(staged_z80);
        ym2610_candidate_destroy(staged_ym);
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                             GN_STATE_SECTION_MVS_SOUND, 0u, 0u, status);
    }
    const z80_candidate_status z80_rebind_status =
        z80_candidate_state_rebind(staged_z80, replacement_z80);
    if (z80_rebind_status != Z80_CANDIDATE_OK) {
        z80_candidate_destroy(replacement_z80);
        z80_candidate_state_discard(staged_z80);
        ym2610_candidate_destroy(staged_ym);
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                             GN_STATE_SECTION_MVS_SOUND, 0u,
                             (uint32_t)(sections[3] - input),
                             GN_STATUS_INVALID_MEDIA);
    }
    z80_candidate_state_apply(replacement_z80, staged_z80);
    z80_candidate_state_discard(staged_z80);

    /* All parsing, validation, allocations, and callback rebinds are complete.
     * The CPU apply validates before its first write; after it succeeds the
     * remainder is bounded copies and pointer swaps with no failure path. */
    GN_STATE_CHARGE(instance, 7u, 3u * sizeof(cpu_state));
    if (owned_cpu_apply_state(image->cpu, &cpu_state) != OWNED_CPU_OK) {
        z80_candidate_destroy(replacement_z80);
        ym2610_candidate_destroy(staged_ym);
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                             GN_STATE_SECTION_CPU, 0u,
                             (uint32_t)(sections[0] - input),
                             GN_STATUS_CPU_FAILURE);
    }
    const uint8_t *memory = sections[1];
    GN_STATE_CHARGE(instance, 8u, memory_bytes);
    memcpy(image->mvs_work_ram, memory, image->mvs_work_ram_size);
    memory += image->mvs_work_ram_size;
    memcpy(image->mvs_save_ram, memory, image->mvs_save_ram_size);
    memory += image->mvs_save_ram_size;
    memcpy(image->mvs_palette_ram, memory, image->mvs_palette_ram_size);
    memory += image->mvs_palette_ram_size;
    for (size_t index = 0u; index < image->mvs_video_ram_words; ++index)
        image->mvs_video_ram[index] = gn_state_read_u16(&memory);

    image->frame_input = board.frame_input;
    image->mvs_inputs = board.inputs;
    image->mvs_mslugx_command = board.mslugx_command;
    image->mvs_mslugx_counter = board.mslugx_counter;
    image->mvs_program_bank = board.program_bank;
    image->mvs_mame_unmapped_write_count = board.unmapped_write_count;
    image->mvs_watchdog_pet_count = board.watchdog_pet_count;
    image->mvs_watchdog_reset_count = board.watchdog_reset_count;
    image->mvs_video_ram_offset = board.video_offset;
    image->mvs_video_ram_modulo = board.video_modulo;
    image->mvs_video_ram_read_buffer = board.video_read_buffer;
    image->mvs_video_auto_animation_speed = board.animation_speed;
    image->mvs_video_auto_animation_disabled = board.animation_disabled;
    image->mvs_video_auto_animation_counter = board.animation_counter;
    image->mvs_video_auto_animation_frame_counter = board.animation_frame_counter;
    image->mvs_display_position_interrupt_control =
        board.display_interrupt_control;
    image->mvs_irq_pending_mask = board.irq_pending_mask;
    image->mvs_frame_cycle = board.frame_cycle;
    image->mvs_frame_cycle_carry = board.frame_cycle_carry;
    image->mvs_frame_count = board.frame_count;
    image->mvs_output_data = board.output_data;
    image->mvs_output_latch = board.output_latch;
    image->mvs_use_cart_vectors = board.use_cart_vectors;
    image->mvs_cart_audio_selected = board.cart_audio_selected;
    image->mvs_memcard_lock1 = board.memcard_lock1;
    image->mvs_memcard_unlock2 = board.memcard_unlock2;
    image->mvs_coin_lockout_mask = board.coin_lockout_mask;
    image->mvs_save_ram_unlocked = board.save_ram_unlocked;
    image->mvs_palette_bank_selected = board.palette_bank_selected;
    image->mvs_screen_shadow = board.screen_shadow;
    image->mvs_watchdog_pet_generation = board.watchdog_pet_generation;
    image->mvs_watchdog_remaining_cycles = board.watchdog_remaining_cycles;
    image->mvs_sound_step_cycles = board.sound_step_cycles;
    image->mvs_completed_main_instructions =
        board.completed_main_instructions;
    image->mvs_calendar = board.calendar;
    image->mvs_protocol = board.protocol;

    gn_mvs_sound *sound = &image->mvs_sound;
    z80_candidate *old_z80 = sound->cpu;
    ym2610_candidate *old_ym = sound->ym;
    sound->cart_selected = sound_state.cart_selected;
    sound->ym_irq = sound_state.ym_irq;
    sound->command = sound_state.command;
    sound->reply = sound_state.reply;
    sound->command_pending = sound_state.command_pending;
    sound->nmi_enabled = sound_state.nmi_enabled;
    sound->main_clock_remainder = sound_state.main_clock_remainder;
    memcpy(sound->ram, sound_state.ram, sizeof(sound->ram));
    memcpy(sound->banks, sound_state.banks, sizeof(sound->banks));
    memcpy(sound->pcm_history, sound_state.pcm_history,
           sizeof(sound->pcm_history));
    memcpy(sound->pcm_right_history, sound_state.pcm_right_history,
           sizeof(sound->pcm_right_history));
    sound->pcm_history_next = sound_state.pcm_history_next;
    sound->pcm_output_phase = sound_state.pcm_output_phase;
    sound->cpu = replacement_z80;
    sound->ym = staged_ym;
    sound->failed = 0u;
    sound->failure_stage = 0u;
    sound->failure_reason = 0u;
    sound->failure_status = GN_MVS_FAILURE_STATUS_UNKNOWN;
    sound->failure_site = 0u;
    sound->failure_cause = 0u;
    sound->failure_bus_valid = 0u;
    sound->failure_operation = 0u;
    sound->failure_width = 0u;
    sound->failure_address = 0u;
    gn_mvs_failure_clear(&image->mvs_failure);
    image->mvs_bus_fault_address = 0u;
    image->mvs_bus_fault_access = (gn_mvs_bus_access)0;
    image->mvs_bus_fault_width = 0u;
    image->mvs_bus_fault_valid = 0u;
    z80_candidate_destroy(old_z80);
    ym2610_candidate_destroy(old_ym);
    gn_mvs_save_restore_committed(image);
    gn_state_set_detail(detail, GN_STATE_REASON_NONE, 0u, 0u, 0u);
    return GN_STATUS_OK;
}

GN_API gn_status gn_state_restore_v1(gn_instance *instance, const void *bytes,
                                     size_t length,
                                     gn_state_detail_v1 *detail,
                                     size_t detail_size) {
    int bypass_ym_irq_relation = 0;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (instance != NULL) {
        memset(&instance->state_resources, 0, sizeof(instance->state_resources));
        bypass_ym_irq_relation =
            instance->state_bypass_ym_irq_relation != 0u;
        instance->state_bypass_ym_irq_relation = 0u;
    }
#endif
    if (!gn_state_detail_args_valid(detail, detail_size) ||
        (detail != NULL && (!gn_state_range_valid(detail, sizeof(*detail)) ||
            gn_state_overlaps_owned(instance, detail, sizeof(*detail)))))
        return GN_STATUS_INVALID_ARGUMENT;
    /* Input/detail aliasing must be rejected before the first detail write. */
    if (bytes != NULL && gn_state_range_valid(bytes, length) &&
        gn_state_ranges_overlap(bytes, length, detail,
                                detail == NULL ? 0u : sizeof(*detail)))
        return GN_STATUS_INVALID_ARGUMENT;
    gn_state_set_detail(detail, GN_STATE_REASON_NONE, 0u, 0u, 0u);
    if (bytes == NULL || !gn_state_range_valid(bytes, length))
        return gn_state_fail(detail, GN_STATE_REASON_INVALID_ARGUMENT, 0u, 0u,
                             0u, GN_STATUS_INVALID_ARGUMENT);
    if (gn_state_overlaps_owned(instance, bytes, length))
        return gn_state_fail(detail, GN_STATE_REASON_ALIAS, 0u, 0u, 0u,
                             GN_STATUS_INVALID_ARGUMENT);
    gn_status status = gn_state_loaded_diagnostic(instance, detail);
    if (status != GN_STATUS_OK) return status;
    gn_image *image = instance->image;
    if (image->mvs_region_count != 0u)
        return gn_state_restore_mvs(instance, (const uint8_t *)bytes, length,
                                    detail, bypass_ym_irq_relation);
    if (owned_cpu_is_active(image->cpu))
        return gn_state_fail(detail, GN_STATE_REASON_ACTIVE_CALL, 0u, 0u,
                             0u, GN_STATUS_INVALID_STATE);
    if (length < GN_STATE_MAX_SIZE_V1)
        return gn_state_fail(detail, GN_STATE_REASON_TRUNCATED, 0u, 0u,
                             (uint32_t)length, GN_STATUS_INVALID_ARGUMENT);
    if (length > GN_STATE_MAX_SIZE_V1)
        return gn_state_fail(detail, GN_STATE_REASON_TRAILING_BYTES, 0u, 0u,
                             (uint32_t)GN_STATE_MAX_SIZE_V1,
                             GN_STATUS_INVALID_ARGUMENT);

    GN_STATE_CHARGE(instance, 0u, GN_STATE_HEADER_V1_SIZE + 16u);
    const uint8_t *input = (const uint8_t *)bytes;
    if (memcmp(input, "GNST", 4u) != 0 ||
        gn_read32_be(input + 4u) != GN_STATE_FORMAT_V1_VERSION ||
        gn_read32_be(input + 8u) != (uint32_t)GN_STATE_HEADER_V1_SIZE ||
        gn_read32_be(input + 12u) != (uint32_t)GN_STATE_MAX_SIZE_V1 ||
        gn_read32_be(input + 16u) != GN_STATE_FORMAT_V1_ID)
        return gn_state_fail(detail, GN_STATE_REASON_FORMAT, 0u, 0u, 4u,
                             GN_STATUS_INVALID_ARGUMENT);
    if (gn_read32_be(input + 20u) != GN_STATE_REPLAY_V1_ID)
        return gn_state_fail(detail, GN_STATE_REASON_REPLAY_IDENTITY, 0u, 0u,
                             20u, GN_STATUS_UNSUPPORTED_PROFILE);
    if (gn_read32_be(input + 24u) != GN_PROFILE_DIAGNOSTIC)
        return gn_state_fail(detail, GN_STATE_REASON_PROFILE_IDENTITY, 0u, 0u,
                             24u, GN_STATUS_UNSUPPORTED_PROFILE);
    if (gn_read32_be(input + 28u) != GN_STATE_CONFIGURATION_DIAGNOSTIC_V1)
        return gn_state_fail(detail, GN_STATE_REASON_CONFIGURATION_IDENTITY,
                             0u, 0u, 28u, GN_STATUS_UNSUPPORTED_PROFILE);
    if (memcmp(input + 32u, image->diagnostic_media_identity, 32u) != 0)
        return gn_state_fail(detail, GN_STATE_REASON_MEDIA_IDENTITY, 0u, 0u,
                             32u, GN_STATUS_INVALID_MEDIA);
    if (gn_read32_be(input + 64u) != UINT32_C(2))
        return gn_state_fail(detail, GN_STATE_REASON_SECTION, 0u, 0u, 64u,
                             GN_STATUS_INVALID_MEDIA);
    if (gn_read32_be(input + 68u) != 0u)
        return gn_state_fail(detail, GN_STATE_REASON_RESERVED, 0u, 0u, 68u,
                             GN_STATUS_INVALID_MEDIA);
    const size_t cpu_header = GN_STATE_HEADER_V1_SIZE;
    const size_t cpu_data = cpu_header + 8u;
    const size_t ram_header = cpu_data + GN_STATE_CPU_BYTES;
    const size_t ram_data = ram_header + 8u;
    if (gn_read32_be(input + cpu_header) != GN_STATE_SECTION_CPU ||
        gn_read32_be(input + cpu_header + 4u) != (uint32_t)GN_STATE_CPU_BYTES ||
        gn_read32_be(input + ram_header) != GN_STATE_SECTION_RAM ||
        gn_read32_be(input + ram_header + 4u) != (uint32_t)GN_STATE_RAM_BYTES)
        return gn_state_fail(detail, GN_STATE_REASON_SECTION, 0u, 0u,
                             (uint32_t)cpu_header, GN_STATUS_INVALID_MEDIA);

    owned_cpu_state cpu_state;
    uint32_t bad_field = 0u;
    GN_STATE_CHARGE(instance, 1u, GN_STATE_CPU_BYTES);
    if (!gn_state_decode_cpu(input + cpu_data, &cpu_state, &bad_field))
        return gn_state_fail(detail, GN_STATE_REASON_RESERVED, GN_STATE_SECTION_CPU,
                             bad_field, (uint32_t)(cpu_data + 93u),
                             GN_STATUS_INVALID_MEDIA);
    if (owned_cpu_validate_state(&cpu_state) != OWNED_CPU_OK)
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                             GN_STATE_SECTION_CPU, 0u, (uint32_t)cpu_data,
                             GN_STATUS_INVALID_MEDIA);
    uint8_t staged_ram[GN_RAM_SIZE];
    GN_STATE_CHARGE(instance, 8u, 2u * sizeof(staged_ram));
    memcpy(staged_ram, input + ram_data, sizeof(staged_ram));

    /* Every operation that can reject has completed. CPU apply is named,
     * allocation-free and callback-free; the following RAM copy cannot fail. */
    GN_STATE_CHARGE(instance, 7u, 3u * sizeof(cpu_state));
    if (owned_cpu_apply_state(image->cpu, &cpu_state) != OWNED_CPU_OK)
        return gn_state_fail(detail, GN_STATE_REASON_CPU_STATE,
                             GN_STATE_SECTION_CPU, 0u, (uint32_t)cpu_data,
                             GN_STATUS_CPU_FAILURE);
    memcpy(image->ram.bytes, staged_ram, sizeof(staged_ram));
    image->diagnostic_guest_faulted = 0u;
    gn_state_set_detail(detail, GN_STATE_REASON_NONE, 0u, 0u, 0u);
    return GN_STATUS_OK;
}

GN_API gn_status gn_state_compatibility_v1(
    const gn_instance *instance, gn_state_compatibility_info_v1 *out_info,
    size_t info_size) {
    if (out_info == NULL || info_size != sizeof(*out_info) ||
        !gn_state_pointer_aligned(out_info, _Alignof(gn_state_compatibility_info_v1)) ||
        !gn_state_range_valid(out_info, sizeof(*out_info)) ||
        gn_state_overlaps_owned(instance, out_info, sizeof(*out_info)))
        return GN_STATUS_INVALID_ARGUMENT;
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    const gn_image *image = instance->image;
    if (image->profile != GN_PROFILE_DIAGNOSTIC &&
        image->profile != GN_MVS_PROFILE_MSX)
        return GN_STATUS_UNSUPPORTED_PROFILE;
    if ((image->profile == GN_PROFILE_DIAGNOSTIC &&
         image->diagnostic_media_identity_valid == 0u) ||
        (image->profile == GN_MVS_PROFILE_MSX &&
         (image->mvs_media_identity_valid == 0u ||
          image->mvs_state_capacity == 0u)))
        return GN_STATUS_INVALID_STATE;
    gn_state_compatibility_info_v1 info;
    memset(&info, 0, sizeof(info));
    info.size = (uint32_t)sizeof(info);
    info.format_id = GN_STATE_FORMAT_V1_ID;
    info.replay_id = GN_STATE_REPLAY_V1_ID;
    info.durable_save_id = image->profile == GN_MVS_PROFILE_MSX
        ? GN_MVS_SAVE_ID_V1 : 0u;
    info.public_abi_id = GN_STATE_PUBLIC_ABI_V1_ID;
    if (image->profile == GN_PROFILE_DIAGNOSTIC) {
        info.profile_id = GN_PROFILE_DIAGNOSTIC;
        info.configuration_id = GN_STATE_CONFIGURATION_DIAGNOSTIC_V1;
        memcpy(info.media_identity_sha256, image->diagnostic_media_identity,
               sizeof(info.media_identity_sha256));
    } else {
        info.profile_id = GN_MVS_PROFILE_MSX;
        info.configuration_id = GN_STATE_MVS_CONFIGURATION_V1;
        memcpy(info.media_identity_sha256, image->mvs_media_identity,
               sizeof(info.media_identity_sha256));
    }
    memcpy(out_info, &info, sizeof(info));
    return GN_STATUS_OK;
}

enum {
    GN_SAVE_FIELD_HEADER = 1u,
    GN_SAVE_FIELD_VERSION = 2u,
    GN_SAVE_FIELD_LENGTH = 3u,
    GN_SAVE_FIELD_IDENTITY = 4u,
    GN_SAVE_FIELD_DIGEST = 5u,
    GN_SAVE_FIELD_SCOPE = 6u,
    GN_SAVE_FIELD_RECEIPT = 7u,
    GN_SAVE_FIELD_LIFECYCLE = 8u
};

static int gn_mvs_save_detail_args_valid(
    const gn_instance *instance, const gn_mvs_save_detail_v1 *detail,
    size_t detail_size) {
    if (detail == NULL) return detail_size == 0u;
    return detail_size == sizeof(*detail) &&
        gn_state_pointer_aligned(detail, _Alignof(gn_mvs_save_detail_v1)) &&
        gn_state_range_valid(detail, sizeof(*detail)) &&
        !gn_state_overlaps_owned(instance, detail, sizeof(*detail));
}

static void gn_mvs_save_set_detail(gn_mvs_save_detail_v1 *detail,
                                   gn_mvs_save_reason reason,
                                   uint32_t field, uint32_t offset) {
    if (detail == NULL) return;
    detail->size = (uint32_t)sizeof(*detail);
    detail->reason = reason;
    detail->field = field;
    detail->offset = offset;
}

static gn_status gn_mvs_save_fail(gn_mvs_save_detail_v1 *detail,
                                  gn_mvs_save_reason reason,
                                  uint32_t field, uint32_t offset,
                                  gn_status status) {
    gn_mvs_save_set_detail(detail, reason, field, offset);
    return status;
}

static int gn_mvs_save_nonzero_scope(const uint8_t scope[16]) {
    uint8_t combined = 0u;
    for (size_t index = 0u; index < 16u; ++index) combined |= scope[index];
    return combined != 0u;
}

static int gn_mvs_save_supported(const gn_instance *instance) {
    return instance != NULL && instance->image != NULL &&
        instance->image->profile == GN_MVS_PROFILE_MSX &&
        instance->image->mvs_media_identity_valid != 0u &&
        instance->image->mvs_save_ram != NULL &&
        instance->image->mvs_save_ram_size == GN_MVS_SAVE_PAYLOAD_V1_BYTES;
}

static void gn_mvs_save_digest(const uint8_t *envelope, uint8_t out_digest[32]) {
    static const uint8_t domain[] = "Glueyneo MVS save v1";
    gn_sha256 sha;
    gn_sha256_init(&sha);
    gn_sha256_update(&sha, domain, sizeof(domain) - 1u);
    gn_sha256_update(&sha, envelope, 64u);
    gn_sha256_update(&sha, envelope + GN_MVS_SAVE_HEADER_V1_BYTES,
                     GN_MVS_SAVE_PAYLOAD_V1_BYTES);
    gn_sha256_finish(&sha, out_digest);
}

static void gn_mvs_save_write_u32(uint8_t *out, uint32_t value) {
    out[0] = (uint8_t)(value >> 24);
    out[1] = (uint8_t)(value >> 16);
    out[2] = (uint8_t)(value >> 8);
    out[3] = (uint8_t)value;
}

static gn_status gn_mvs_save_check_envelope(
    const gn_instance *instance, const uint8_t *bytes, size_t length,
    gn_mvs_save_detail_v1 *detail) {
    if (length != GN_MVS_SAVE_ENVELOPE_V1_BYTES)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_CAPACITY,
                                GN_SAVE_FIELD_LENGTH, (uint32_t)length,
                                GN_STATUS_INVALID_MEDIA);
    if (memcmp(bytes, "GNSV", 4u) != 0)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_FORMAT,
                                GN_SAVE_FIELD_HEADER, 0u,
                                GN_STATUS_INVALID_MEDIA);
    if (gn_read32_be(bytes + 4u) != GN_MVS_SAVE_FORMAT_V1_VERSION)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_VERSION,
                                GN_SAVE_FIELD_VERSION, 4u,
                                GN_STATUS_UNSUPPORTED_PROFILE);
    if (gn_read32_be(bytes + 8u) != GN_MVS_SAVE_HEADER_V1_BYTES ||
        gn_read32_be(bytes + 12u) != GN_MVS_SAVE_ENVELOPE_V1_BYTES ||
        gn_read32_be(bytes + 16u) != GN_MVS_SAVE_PAYLOAD_V1_BYTES)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_CAPACITY,
                                GN_SAVE_FIELD_LENGTH, 8u,
                                GN_STATUS_INVALID_MEDIA);
    if (gn_read32_be(bytes + 20u) != GN_MVS_SAVE_ID_V1)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_DURABLE_ID,
                                GN_SAVE_FIELD_IDENTITY, 20u,
                                GN_STATUS_UNSUPPORTED_PROFILE);
    if (gn_read32_be(bytes + 24u) != instance->image->profile)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_PROFILE,
                                GN_SAVE_FIELD_IDENTITY, 24u,
                                GN_STATUS_UNSUPPORTED_PROFILE);
    if (gn_read32_be(bytes + 28u) != 0u)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_RESERVED,
                                GN_SAVE_FIELD_HEADER, 28u,
                                GN_STATUS_INVALID_MEDIA);
    if (memcmp(bytes + 32u, instance->image->mvs_media_identity, 32u) != 0)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_MEDIA_IDENTITY,
                                GN_SAVE_FIELD_IDENTITY, 32u,
                                GN_STATUS_INVALID_MEDIA);
    uint8_t digest[32];
    gn_mvs_save_digest(bytes, digest);
    if (memcmp(bytes + 64u, digest, sizeof(digest)) != 0)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INTEGRITY,
                                GN_SAVE_FIELD_DIGEST, 64u,
                                GN_STATUS_INVALID_MEDIA);
    return GN_STATUS_OK;
}

GN_API gn_status gn_mvs_save_query_v1(
    const gn_instance *instance, gn_mvs_save_info_v1 *out_info,
    size_t info_size, gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (out_info == NULL || info_size != sizeof(*out_info) ||
        !gn_state_pointer_aligned(out_info, _Alignof(gn_mvs_save_info_v1)) ||
        !gn_state_range_valid(out_info, sizeof(*out_info)) ||
        gn_state_overlaps_owned(instance, out_info, sizeof(*out_info)) ||
        !gn_mvs_save_detail_args_valid(instance, detail, detail_size) ||
        (detail != NULL && gn_state_ranges_overlap(out_info, sizeof(*out_info),
                                                    detail, sizeof(*detail))))
        return GN_STATUS_INVALID_ARGUMENT;
    memset(out_info, 0, sizeof(*out_info));
    if (instance == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_ARGUMENT,
                                0u, 0u, GN_STATUS_INVALID_ARGUMENT);
    if (instance->image == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_STATE,
                                0u, 0u, GN_STATUS_INVALID_STATE);
    out_info->size = (uint32_t)sizeof(*out_info);
    out_info->profile_id = instance->image->profile;
    if (!gn_mvs_save_supported(instance)) {
        gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
        return GN_STATUS_OK;
    }
    const gn_mvs_save_ownership *save = &instance->mvs_save;
    out_info->supported = 1u;
    out_info->save_id = GN_MVS_SAVE_ID_V1;
    memcpy(out_info->media_identity_sha256,
           instance->image->mvs_media_identity,
           sizeof(out_info->media_identity_sha256));
    out_info->envelope_bytes = (uint32_t)GN_MVS_SAVE_ENVELOPE_V1_BYTES;
    out_info->dirty = save->dirty;
    out_info->baseline_known = save->baseline_known;
    out_info->scope_valid = save->scope_valid;
    out_info->exhausted = save->exhausted;
    out_info->startup_import_allowed = save->startup_import_allowed;
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    return GN_STATUS_OK;
}

GN_API gn_status gn_mvs_save_scope_renew_v1(
    gn_instance *instance, const gn_mvs_save_scope_v1 *scope,
    size_t scope_size, gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (!gn_mvs_save_detail_args_valid(instance, detail, detail_size) ||
        scope == NULL || scope_size != sizeof(*scope) ||
        !gn_state_pointer_aligned(scope, _Alignof(gn_mvs_save_scope_v1)) ||
        !gn_state_range_valid(scope, sizeof(*scope)) ||
        gn_state_overlaps_owned(instance, scope, sizeof(*scope)) ||
        (detail != NULL && gn_state_ranges_overlap(scope, sizeof(*scope),
                                                    detail, sizeof(*detail))))
        return GN_STATUS_INVALID_ARGUMENT;
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    if (instance == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_ARGUMENT,
                                0u, 0u, GN_STATUS_INVALID_ARGUMENT);
    if (instance->image == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_STATE,
                                0u, 0u, GN_STATUS_INVALID_STATE);
    if (!gn_mvs_save_supported(instance))
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_UNSUPPORTED_PROFILE,
                                0u, 0u, GN_STATUS_UNSUPPORTED_PROFILE);
    if (scope->size != sizeof(*scope) || scope->reserved != 0u ||
        !gn_mvs_save_nonzero_scope(scope->scope))
        return gn_mvs_save_fail(detail,
            scope->reserved != 0u ? GN_MVS_SAVE_REASON_RESERVED
                                  : GN_MVS_SAVE_REASON_SCOPE,
            GN_SAVE_FIELD_SCOPE, 0u, GN_STATUS_INVALID_ARGUMENT);
    gn_mvs_save_ownership *save = &instance->mvs_save;
    if (save->scope_valid != 0u &&
        memcmp(save->scope, scope->scope, sizeof(save->scope)) == 0)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_SCOPE_REUSED,
                                GN_SAVE_FIELD_SCOPE, 0u,
                                GN_STATUS_INVALID_ARGUMENT);
    memcpy(save->scope, scope->scope, sizeof(save->scope));
    save->scope_valid = 1u;
    save->load_generation = 1u;
    save->restore_branch = 0u;
    save->mutation_sequence = 0u;
    save->export_sequence = 0u;
    save->exhausted = 0u;
    save->receipt_valid = 0u;
    save->receipt_consumed = 0u;
    memset(&save->latest_receipt, 0, sizeof(save->latest_receipt));
    return GN_STATUS_OK;
}

GN_API gn_status gn_mvs_save_export_v1(
    gn_instance *instance, void *buffer, size_t capacity, size_t *out_written,
    gn_mvs_save_receipt_v1 *out_receipt, size_t receipt_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (out_written == NULL ||
        !gn_state_pointer_aligned(out_written, _Alignof(size_t)) ||
        !gn_state_range_valid(out_written, sizeof(*out_written)) ||
        gn_state_overlaps_owned(instance, out_written, sizeof(*out_written)) ||
        out_receipt == NULL || receipt_size != sizeof(*out_receipt) ||
        !gn_state_pointer_aligned(out_receipt,
                                  _Alignof(gn_mvs_save_receipt_v1)) ||
        !gn_state_range_valid(out_receipt, sizeof(*out_receipt)) ||
        gn_state_overlaps_owned(instance, out_receipt, sizeof(*out_receipt)) ||
        !gn_mvs_save_detail_args_valid(instance, detail, detail_size))
        return GN_STATUS_INVALID_ARGUMENT;
    if (gn_state_ranges_overlap(out_written, sizeof(*out_written),
                                out_receipt, sizeof(*out_receipt)) ||
        (detail != NULL &&
         (gn_state_ranges_overlap(out_written, sizeof(*out_written),
                                  detail, sizeof(*detail)) ||
          gn_state_ranges_overlap(out_receipt, sizeof(*out_receipt),
                                  detail, sizeof(*detail)))) ||
        (buffer != NULL && capacity != 0u &&
         gn_state_range_valid(buffer, capacity) &&
         (gn_state_overlaps_owned(instance, buffer, capacity) ||
          gn_state_ranges_overlap(buffer, capacity, out_written,
                                  sizeof(*out_written)) ||
          gn_state_ranges_overlap(buffer, capacity, out_receipt,
                                  sizeof(*out_receipt)) ||
          (detail != NULL && gn_state_ranges_overlap(
              buffer, capacity, detail, sizeof(*detail))))))
        return GN_STATUS_INVALID_ARGUMENT;
    *out_written = 0u;
    if (buffer == NULL || capacity < GN_MVS_SAVE_ENVELOPE_V1_BYTES ||
        !gn_state_range_valid(buffer, capacity))
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_CAPACITY,
                                GN_SAVE_FIELD_LENGTH, 0u,
                                GN_STATUS_INVALID_ARGUMENT);
    if (instance == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_ARGUMENT,
                                0u, 0u, GN_STATUS_INVALID_ARGUMENT);
    if (instance->image == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_STATE,
                                0u, 0u, GN_STATUS_INVALID_STATE);
    if (!gn_mvs_save_supported(instance))
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_UNSUPPORTED_PROFILE,
                                0u, 0u, GN_STATUS_UNSUPPORTED_PROFILE);
    gn_mvs_save_ownership *save = &instance->mvs_save;
    if (save->scope_valid == 0u)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_SCOPE,
                                GN_SAVE_FIELD_SCOPE, 0u,
                                GN_STATUS_INVALID_STATE);
    if (save->exhausted != 0u)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED,
                                GN_SAVE_FIELD_RECEIPT, 0u,
                                GN_STATUS_INVALID_STATE);
    if (save->export_sequence == UINT64_MAX) {
        save->exhausted = 1u;
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED,
                                GN_SAVE_FIELD_RECEIPT, 0u,
                                GN_STATUS_INVALID_STATE);
    }

    uint8_t *encoded = (uint8_t *)buffer;
    memset(encoded, 0, GN_MVS_SAVE_HEADER_V1_BYTES);
    memcpy(encoded, "GNSV", 4u);
    gn_mvs_save_write_u32(encoded + 4u, GN_MVS_SAVE_FORMAT_V1_VERSION);
    gn_mvs_save_write_u32(encoded + 8u,
                          (uint32_t)GN_MVS_SAVE_HEADER_V1_BYTES);
    gn_mvs_save_write_u32(encoded + 12u,
                          (uint32_t)GN_MVS_SAVE_ENVELOPE_V1_BYTES);
    gn_mvs_save_write_u32(encoded + 16u,
                          (uint32_t)GN_MVS_SAVE_PAYLOAD_V1_BYTES);
    gn_mvs_save_write_u32(encoded + 20u, GN_MVS_SAVE_ID_V1);
    gn_mvs_save_write_u32(encoded + 24u, instance->image->profile);
    memcpy(encoded + 32u, instance->image->mvs_media_identity, 32u);
    memcpy(encoded + GN_MVS_SAVE_HEADER_V1_BYTES,
           instance->image->mvs_save_ram, GN_MVS_SAVE_PAYLOAD_V1_BYTES);
    uint8_t digest[32];
    gn_mvs_save_digest(encoded, digest);
    memcpy(encoded + 64u, digest, sizeof(digest));

    gn_mvs_save_receipt_v1 receipt;
    memset(&receipt, 0, sizeof(receipt));
    receipt.size = (uint32_t)sizeof(receipt);
    memcpy(receipt.scope, save->scope, sizeof(receipt.scope));
    receipt.load_generation = save->load_generation;
    receipt.restore_branch = save->restore_branch;
    receipt.mutation_sequence = save->mutation_sequence;
    receipt.export_sequence = save->export_sequence + 1u;
    save->export_sequence = receipt.export_sequence;
    save->latest_receipt = receipt;
    save->receipt_valid = 1u;
    save->receipt_consumed = 0u;
    memcpy(out_receipt, &receipt, sizeof(receipt));
    *out_written = GN_MVS_SAVE_ENVELOPE_V1_BYTES;
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    return GN_STATUS_OK;
}

GN_API gn_status gn_mvs_save_import_baseline_v1(
    gn_instance *instance, const void *bytes, size_t length,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (!gn_mvs_save_detail_args_valid(instance, detail, detail_size) ||
        (bytes != NULL && gn_state_range_valid(bytes, length) &&
         (gn_state_overlaps_owned(instance, bytes, length) ||
          (detail != NULL && gn_state_ranges_overlap(
              bytes, length, detail, sizeof(*detail))))))
        return GN_STATUS_INVALID_ARGUMENT;
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    if (bytes == NULL || !gn_state_range_valid(bytes, length))
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_ARGUMENT,
                                0u, 0u, GN_STATUS_INVALID_ARGUMENT);
    if (instance == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_ARGUMENT,
                                0u, 0u, GN_STATUS_INVALID_ARGUMENT);
    if (instance->image == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_STATE,
                                0u, 0u, GN_STATUS_INVALID_STATE);
    if (!gn_mvs_save_supported(instance))
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_UNSUPPORTED_PROFILE,
                                0u, 0u, GN_STATUS_UNSUPPORTED_PROFILE);
    gn_status status = gn_mvs_save_check_envelope(
        instance, (const uint8_t *)bytes, length, detail);
    if (status != GN_STATUS_OK) return status;
    gn_mvs_save_ownership *save = &instance->mvs_save;
    if (save->exhausted != 0u)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED,
                                GN_SAVE_FIELD_RECEIPT, 0u,
                                GN_STATUS_INVALID_STATE);
    if (save->scope_valid == 0u)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_SCOPE,
                                GN_SAVE_FIELD_SCOPE, 0u,
                                GN_STATUS_INVALID_STATE);
    if (save->startup_import_allowed == 0u)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_STARTUP_CLOSED,
                                GN_SAVE_FIELD_LIFECYCLE, 0u,
                                GN_STATUS_INVALID_STATE);
    if (save->dirty != 0u || save->export_sequence != 0u ||
        save->receipt_valid != 0u)
        return gn_mvs_save_fail(detail,
            GN_MVS_SAVE_REASON_HOST_WORK_PENDING, GN_SAVE_FIELD_LIFECYCLE,
            0u, GN_STATUS_INVALID_STATE);
    if (save->restore_branch == UINT64_MAX)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED,
                                GN_SAVE_FIELD_RECEIPT, 0u,
                                GN_STATUS_INVALID_STATE);

    memcpy(instance->image->mvs_save_ram,
           (const uint8_t *)bytes + GN_MVS_SAVE_HEADER_V1_BYTES,
           GN_MVS_SAVE_PAYLOAD_V1_BYTES);
    save->baseline_known = 1u;
    save->dirty = 0u;
    ++save->restore_branch;
    save->receipt_valid = 0u;
    save->receipt_consumed = 0u;
    memset(&save->latest_receipt, 0, sizeof(save->latest_receipt));
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    return GN_STATUS_OK;
}

GN_API gn_status gn_mvs_save_ack_v1(
    gn_instance *instance, const gn_mvs_save_receipt_v1 *receipt,
    size_t receipt_size, gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    int bypass_stale_clean = 0;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
    if (instance != NULL && instance->state_bypass_save_stale_clean != 0u) {
        instance->state_bypass_save_stale_clean = 0u;
        bypass_stale_clean = 1;
    }
#endif
    if (!gn_mvs_save_detail_args_valid(instance, detail, detail_size) ||
        receipt == NULL || receipt_size != sizeof(*receipt) ||
        !gn_state_pointer_aligned(receipt,
                                  _Alignof(gn_mvs_save_receipt_v1)) ||
        !gn_state_range_valid(receipt, sizeof(*receipt)) ||
        gn_state_overlaps_owned(instance, receipt, sizeof(*receipt)) ||
        (detail != NULL && gn_state_ranges_overlap(receipt, sizeof(*receipt),
                                                    detail, sizeof(*detail))))
        return GN_STATUS_INVALID_ARGUMENT;
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    if (instance == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_ARGUMENT,
                                0u, 0u, GN_STATUS_INVALID_ARGUMENT);
    if (instance->image == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_STATE,
                                0u, 0u, GN_STATUS_INVALID_STATE);
    if (!gn_mvs_save_supported(instance))
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_UNSUPPORTED_PROFILE,
                                0u, 0u, GN_STATUS_UNSUPPORTED_PROFILE);
    if (receipt->size != sizeof(*receipt) || receipt->reserved != 0u)
        return gn_mvs_save_fail(detail,
            receipt->reserved != 0u ? GN_MVS_SAVE_REASON_RESERVED
                                    : GN_MVS_SAVE_REASON_INVALID_ARGUMENT,
            GN_SAVE_FIELD_RECEIPT, 0u, GN_STATUS_INVALID_ARGUMENT);
    gn_mvs_save_ownership *save = &instance->mvs_save;
    if (save->exhausted != 0u &&
        !(save->export_sequence == UINT64_MAX && save->receipt_valid != 0u))
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED,
                                GN_SAVE_FIELD_RECEIPT, 0u,
                                GN_STATUS_INVALID_STATE);
    if (save->receipt_valid != 0u && save->receipt_consumed != 0u &&
        receipt->export_sequence == save->latest_receipt.export_sequence &&
        memcmp(receipt->scope, save->latest_receipt.scope,
               sizeof(receipt->scope)) == 0)
        return gn_mvs_save_fail(detail,
            GN_MVS_SAVE_REASON_RECEIPT_CONSUMED, GN_SAVE_FIELD_RECEIPT, 0u,
            GN_STATUS_INVALID_STATE);
    const gn_mvs_save_receipt_v1 *latest = &save->latest_receipt;
    if (save->receipt_valid == 0u || save->receipt_consumed != 0u ||
        memcmp(receipt->scope, save->scope, sizeof(receipt->scope)) != 0 ||
        memcmp(receipt->scope, latest->scope, sizeof(receipt->scope)) != 0 ||
        receipt->load_generation != save->load_generation ||
        receipt->load_generation != latest->load_generation ||
        receipt->restore_branch != save->restore_branch ||
        receipt->restore_branch != latest->restore_branch ||
        receipt->mutation_sequence != save->mutation_sequence ||
        receipt->mutation_sequence != latest->mutation_sequence ||
        receipt->export_sequence != save->export_sequence ||
        receipt->export_sequence != latest->export_sequence) {
        if (bypass_stale_clean != 0) save->dirty = 0u;
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_STALE_RECEIPT,
                                GN_SAVE_FIELD_RECEIPT, 0u,
                                GN_STATUS_INVALID_STATE);
    }
    save->receipt_consumed = 1u;
    save->dirty = 0u;
    save->baseline_known = 1u;
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    return GN_STATUS_OK;
}

GN_API const char *gn_state_reason_string(gn_state_reason reason) {
    switch (reason) {
        case GN_STATE_REASON_NONE: return "ok";
        case GN_STATE_REASON_INVALID_ARGUMENT: return "invalid argument";
        case GN_STATE_REASON_INVALID_STATE: return "invalid state";
        case GN_STATE_REASON_UNSUPPORTED_PROFILE: return "unsupported profile";
        case GN_STATE_REASON_ACTIVE_CALL: return "active guest call";
        case GN_STATE_REASON_GUEST_FAULT: return "guest fault latched";
        case GN_STATE_REASON_CPU_STATE: return "invalid CPU state";
        case GN_STATE_REASON_CAPACITY: return "insufficient capacity";
        case GN_STATE_REASON_TRUNCATED: return "truncated state";
        case GN_STATE_REASON_TRAILING_BYTES: return "trailing state bytes";
        case GN_STATE_REASON_FORMAT: return "unsupported state format";
        case GN_STATE_REASON_SECTION: return "invalid state section";
        case GN_STATE_REASON_RESERVED: return "nonzero reserved field";
        case GN_STATE_REASON_REPLAY_IDENTITY: return "incompatible replay identity";
        case GN_STATE_REASON_PROFILE_IDENTITY: return "incompatible profile identity";
        case GN_STATE_REASON_CONFIGURATION_IDENTITY: return "incompatible configuration identity";
        case GN_STATE_REASON_MEDIA_IDENTITY: return "incompatible media identity";
        case GN_STATE_REASON_ALIAS: return "overlapping buffers";
        default: return "unknown state reason";
    }
}

GN_API const char *gn_mvs_save_reason_string(gn_mvs_save_reason reason) {
    switch (reason) {
        case GN_MVS_SAVE_REASON_NONE: return "ok";
        case GN_MVS_SAVE_REASON_INVALID_ARGUMENT: return "invalid argument";
        case GN_MVS_SAVE_REASON_INVALID_STATE: return "invalid state";
        case GN_MVS_SAVE_REASON_UNSUPPORTED_PROFILE: return "unsupported profile";
        case GN_MVS_SAVE_REASON_CAPACITY: return "invalid save length";
        case GN_MVS_SAVE_REASON_FORMAT: return "invalid save format";
        case GN_MVS_SAVE_REASON_VERSION: return "unsupported save version";
        case GN_MVS_SAVE_REASON_RESERVED: return "nonzero reserved field";
        case GN_MVS_SAVE_REASON_DURABLE_ID: return "unsupported save identity";
        case GN_MVS_SAVE_REASON_PROFILE: return "incompatible save profile";
        case GN_MVS_SAVE_REASON_MEDIA_IDENTITY: return "incompatible save media";
        case GN_MVS_SAVE_REASON_INTEGRITY: return "save digest mismatch";
        case GN_MVS_SAVE_REASON_SCOPE: return "save scope required";
        case GN_MVS_SAVE_REASON_STALE_RECEIPT: return "stale save receipt";
        case GN_MVS_SAVE_REASON_RECEIPT_CONSUMED: return "save receipt already consumed";
        case GN_MVS_SAVE_REASON_STARTUP_CLOSED: return "startup import is closed";
        case GN_MVS_SAVE_REASON_HOST_WORK_PENDING: return "host work is pending";
        case GN_MVS_SAVE_REASON_COUNTER_EXHAUSTED: return "save lineage exhausted";
        case GN_MVS_SAVE_REASON_SCOPE_REUSED: return "save scope was reused";
        default: return "unknown save reason";
    }
}

static int gn_mvs_lifecycle_result_args_valid(
    const gn_instance *instance, gn_mvs_save_lifecycle_result_v1 *result,
    size_t result_size, gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    return result != NULL && result_size == sizeof(*result) &&
        gn_state_pointer_aligned(result,
            _Alignof(gn_mvs_save_lifecycle_result_v1)) &&
        gn_state_range_valid(result, sizeof(*result)) &&
        !gn_state_overlaps_owned(instance, result, sizeof(*result)) &&
        gn_mvs_save_detail_args_valid(instance, detail, detail_size) &&
        (detail == NULL || !gn_state_ranges_overlap(
            result, sizeof(*result), detail, sizeof(*detail)));
}

static int gn_mvs_lifecycle_policy_valid(
    gn_mvs_save_lifecycle_policy_v1 policy, uint32_t host_work_resolved) {
    return (policy == GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED ||
            policy == GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD) &&
        host_work_resolved <= 1u;
}

static gn_status gn_mvs_lifecycle_policy_check(
    const gn_instance *instance, gn_mvs_save_lifecycle_policy_v1 policy,
    uint32_t host_work_resolved, gn_mvs_save_detail_v1 *detail) {
    if (!gn_mvs_lifecycle_policy_valid(policy, host_work_resolved))
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_ARGUMENT,
                                GN_SAVE_FIELD_LIFECYCLE, 0u,
                                GN_STATUS_INVALID_ARGUMENT);
    if (host_work_resolved == 0u ||
        (policy == GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED &&
         instance != NULL && instance->mvs_save.dirty != 0u))
        return gn_mvs_save_fail(detail,
            GN_MVS_SAVE_REASON_HOST_WORK_PENDING, GN_SAVE_FIELD_LIFECYCLE,
            0u, GN_STATUS_INVALID_STATE);
    return GN_STATUS_OK;
}

GN_API gn_status gn_load_mvs_v3_checked_v1(
    gn_instance *instance, const gn_mvs_manifest_v3 *manifest,
    gn_mvs_save_lifecycle_policy_v1 policy, uint32_t host_work_resolved,
    gn_mvs_save_lifecycle_result_v1 *out_result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    /* Reject every input/output alias before writing even diagnostic outputs.
     * Region data remains caller-owned until candidate copying completes. */
    if (!gn_mvs_lifecycle_result_args_valid(instance, out_result, result_size,
                                             detail, detail_size) ||
        instance == NULL || manifest == NULL ||
        !gn_state_pointer_aligned(manifest, _Alignof(gn_mvs_manifest_v3)) ||
        !gn_state_range_valid(manifest, sizeof(*manifest)) ||
        gn_state_overlaps_owned(instance, manifest, sizeof(*manifest)) ||
        gn_state_ranges_overlap(out_result, sizeof(*out_result), manifest,
                                sizeof(*manifest)) ||
        (detail != NULL && gn_state_ranges_overlap(
            detail, sizeof(*detail), manifest, sizeof(*manifest))))
        return GN_STATUS_INVALID_ARGUMENT;
    for (size_t index = 0u; index < manifest->region_count &&
                            index < GN_MVS_V3_MAX_REGIONS; ++index) {
        const gn_mvs_region *region = &manifest->regions[index];
        if (gn_state_ranges_overlap(out_result, sizeof(*out_result),
                                    region->source, region->source_size) ||
            (detail != NULL && gn_state_ranges_overlap(
                detail, sizeof(*detail), region->source,
                region->source_size)))
            return GN_STATUS_INVALID_ARGUMENT;
    }
    memset(out_result, 0, sizeof(*out_result));
    out_result->size = (uint32_t)sizeof(*out_result);
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    if (manifest->version != GN_MVS_MANIFEST_VERSION_ZOOM)
        return GN_STATUS_UNSUPPORTED_PROFILE;
    const gn_status policy_status = gn_mvs_lifecycle_policy_check(
        instance, policy, host_work_resolved, detail);
    if (policy_status != GN_STATUS_OK) return policy_status;

    const uint32_t discarded_pending = instance->mvs_save.dirty != 0u ? 1u : 0u;
    gn_image *candidate = NULL;
    const gn_status status = gn_build_mvs_candidate(
        &instance->allocator, manifest->version, manifest->profile,
        manifest->region_count, manifest->regions, GN_MVS_V3_MAX_REGIONS,
        &candidate);
    if (status != GN_STATUS_OK) return status;

    gn_mvs_candidate_commit(instance, candidate);
    out_result->discarded_pending = discarded_pending;
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    return GN_STATUS_OK;
}

GN_API gn_status gn_unload_checked_v1(
    gn_instance *instance, gn_mvs_save_lifecycle_policy_v1 policy,
    uint32_t host_work_resolved,
    gn_mvs_save_lifecycle_result_v1 *out_result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (!gn_mvs_lifecycle_result_args_valid(instance, out_result, result_size,
                                             detail, detail_size))
        return GN_STATUS_INVALID_ARGUMENT;
    memset(out_result, 0, sizeof(*out_result));
    out_result->size = (uint32_t)sizeof(*out_result);
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    if (instance == NULL)
        return gn_mvs_save_fail(detail, GN_MVS_SAVE_REASON_INVALID_ARGUMENT,
                                0u, 0u, GN_STATUS_INVALID_ARGUMENT);
    const gn_status policy_status = gn_mvs_lifecycle_policy_check(
        instance, policy, host_work_resolved, detail);
    if (policy_status != GN_STATUS_OK) return policy_status;

    const uint32_t discarded_pending = instance->mvs_save.dirty != 0u ? 1u : 0u;
    if (instance->image != NULL) {
        gn_mvs_save_load_committed(instance);
        gn_free_image(instance->image);
        instance->image = NULL;
    }
    out_result->discarded_pending = discarded_pending;
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    return GN_STATUS_OK;
}

GN_API gn_status gn_destroy_checked_v1(
    gn_instance **inout_instance, gn_mvs_save_lifecycle_policy_v1 policy,
    uint32_t host_work_resolved,
    gn_mvs_save_lifecycle_result_v1 *out_result, size_t result_size,
    gn_mvs_save_detail_v1 *detail, size_t detail_size) {
    if (inout_instance == NULL ||
        !gn_state_pointer_aligned(inout_instance, _Alignof(gn_instance *)) ||
        !gn_state_range_valid(inout_instance, sizeof(*inout_instance)))
        return GN_STATUS_INVALID_ARGUMENT;
    gn_instance *instance = *inout_instance;
    if (!gn_mvs_lifecycle_result_args_valid(instance, out_result, result_size,
                                             detail, detail_size) ||
        gn_state_ranges_overlap(inout_instance, sizeof(*inout_instance),
                                out_result, sizeof(*out_result)) ||
        (detail != NULL && gn_state_ranges_overlap(
            inout_instance, sizeof(*inout_instance), detail, sizeof(*detail))) ||
        gn_state_overlaps_owned(instance, inout_instance,
                                sizeof(*inout_instance)))
        return GN_STATUS_INVALID_ARGUMENT;
    memset(out_result, 0, sizeof(*out_result));
    out_result->size = (uint32_t)sizeof(*out_result);
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    const gn_status policy_status = gn_mvs_lifecycle_policy_check(
        instance, policy, host_work_resolved, detail);
    if (policy_status != GN_STATUS_OK) return policy_status;

    const uint32_t discarded_pending = instance != NULL &&
        instance->mvs_save.dirty != 0u ? 1u : 0u;
    gn_destroy(instance);
    *inout_instance = NULL;
    out_result->discarded_pending = discarded_pending;
    gn_mvs_save_set_detail(detail, GN_MVS_SAVE_REASON_NONE, 0u, 0u);
    return GN_STATUS_OK;
}

GN_API gn_status gn_set_mvs_inputs(gn_instance *instance, uint32_t input_mask) {
    if ((input_mask & ~GN_MVS_INPUT_SUPPORTED_MASK) != 0u)
        return GN_STATUS_INVALID_ARGUMENT;
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    gn_image *image = instance->image;
    if (image->mvs_region_count == 0u) return GN_STATUS_UNSUPPORTED_PROFILE;
    if (image->mvs_inputs != input_mask) {
        gn_mvs_protocol_note_input_change(&image->mvs_protocol,
                                           image->mvs_inputs, input_mask);
        image->mvs_inputs = input_mask;
    }
    return GN_STATUS_OK;
}

static gn_status gn_run_cpu(gn_instance *instance, uint64_t cycle_budget,
                            gn_run_result *out_result,
                            owned_cpu_status *out_cpu_status) {
    if (out_result == NULL) return GN_STATUS_INVALID_ARGUMENT;
    memset(out_result, 0, sizeof(*out_result));
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    if (cycle_budget > GN_MAX_CYCLE_BUDGET) return GN_STATUS_INVALID_ARGUMENT;

    const owned_cpu_run_result cpu_result =
        owned_cpu_run(instance->image->cpu, cycle_budget);
    if (out_cpu_status != NULL) *out_cpu_status = cpu_result.reason;
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
    if (mapped_status == GN_STATUS_OK &&
        out_result->reason == GN_RUN_FAULT &&
        instance->image->profile == GN_PROFILE_DIAGNOSTIC) {
        instance->image->diagnostic_guest_faulted = 1u;
    }
    return mapped_status;
}

static gn_status gn_mvs_watchdog_soft_reset(gn_image *image) {
    const owned_cpu_status cpu_status = owned_cpu_reset(image->cpu);
    if (cpu_status != OWNED_CPU_OK) {
        gn_mvs_failure_record_image(image,
                              GN_MVS_FAILURE_COMPONENT_BOARD,
                              GN_MVS_FAILURE_STAGE_WATCHDOG_RESET,
                              GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
        return GN_STATUS_CPU_FAILURE;
    }
    const gn_status sound_status = gn_mvs_sound_reset(&image->mvs_sound);
    if (sound_status != GN_STATUS_OK) {
        gn_mvs_failure_record_sound(image,
                                    GN_MVS_FAILURE_STAGE_WATCHDOG_RESET,
                                    GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
        return sound_status;
    }
    image->mvs_cart_audio_selected = 0u;
    image->mvs_bus_fault_address = 0u;
    image->mvs_bus_fault_access = (gn_mvs_bus_access)0;
    image->mvs_bus_fault_width = 0u;
    image->mvs_bus_fault_valid = 0u;
    image->mvs_watchdog_remaining_cycles = GN_MVS_WATCHDOG_MAIN_CYCLES;
    if (image->mvs_watchdog_reset_count != UINT32_MAX)
        ++image->mvs_watchdog_reset_count;
    return GN_STATUS_OK;
}

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
static int gn_test_mvs_consume_failure(gn_image *image,
                                      gn_test_mvs_failure failure) {
    if (image->test_mvs_failure != failure) return 0;
    image->test_mvs_failure = GN_TEST_MVS_FAILURE_NONE;
    return 1;
}
#endif

/* Highest pending source level, as update_interrupts drives the three CPU
 * lines and the 68000 services the highest unmasked one (neogeo.cpp 797-803). */
static unsigned gn_mvs_pending_irq_level(uint8_t pending) {
    if ((pending & GN_MVS_IRQ_BIT_IRQ3) != 0u) return 3u;
    if ((pending & GN_MVS_IRQ_BIT_RASTER) != 0u) return 2u;
    if ((pending & GN_MVS_IRQ_BIT_VBLANK) != 0u) return 1u;
    return 0u;
}

/* Clocks from the current frame position until the next VBlank flip-flop set;
 * always at least one, so a fast-forwarded idle step makes progress. */
static uint64_t gn_mvs_cycles_to_vblank_irq(const gn_image *image) {
    const uint64_t position = image->mvs_frame_cycle;
    return position < GN_MVS_VBLANK_IRQ_CYCLE
        ? GN_MVS_VBLANK_IRQ_CYCLE - position
        : GN_MVS_FRAME_CYCLES - position + GN_MVS_VBLANK_IRQ_CYCLE;
}

/* Clocks until MAME's sprite auto-animation timer reaches VSSTART. */
static uint64_t gn_mvs_cycles_to_video_animation_tick(const gn_image *image) {
    const uint64_t position = image->mvs_frame_cycle;
    return position < GN_MVS_VIDEO_AUTO_ANIMATION_CYCLE
        ? GN_MVS_VIDEO_AUTO_ANIMATION_CYCLE - position
        : GN_MVS_FRAME_CYCLES - position + GN_MVS_VIDEO_AUTO_ANIMATION_CYCLE;
}

static void gn_mvs_video_animation_tick(gn_image *image) {
    if (image->mvs_video_auto_animation_frame_counter == 0u) {
        image->mvs_video_auto_animation_frame_counter =
            image->mvs_video_auto_animation_speed;
        ++image->mvs_video_auto_animation_counter;
    } else {
        --image->mvs_video_auto_animation_frame_counter;
    }
}

/* Advance the per-instance raster by executed CPU clocks and process each
 * VBlank and auto-animation boundary crossed. Host time never enters. */
static void gn_mvs_advance_raster(gn_image *image, uint64_t cycles) {
    uint64_t remaining = cycles;
    uint64_t position = image->mvs_frame_cycle;
    while (remaining != 0u) {
        const uint64_t to_vblank = position < GN_MVS_VBLANK_IRQ_CYCLE
            ? GN_MVS_VBLANK_IRQ_CYCLE - position
            : GN_MVS_FRAME_CYCLES - position + GN_MVS_VBLANK_IRQ_CYCLE;
        const uint64_t to_animation =
            position < GN_MVS_VIDEO_AUTO_ANIMATION_CYCLE
                ? GN_MVS_VIDEO_AUTO_ANIMATION_CYCLE - position
                : GN_MVS_FRAME_CYCLES - position +
                      GN_MVS_VIDEO_AUTO_ANIMATION_CYCLE;
        const uint64_t to_event = to_vblank < to_animation
            ? to_vblank : to_animation;
        if (remaining < to_event) {
            position = (position + remaining) % GN_MVS_FRAME_CYCLES;
            break;
        }
        remaining -= to_event;
        position = (position + to_event) % GN_MVS_FRAME_CYCLES;
        if (to_event == to_vblank) {
            image->mvs_irq_pending_mask =
                (uint8_t)(image->mvs_irq_pending_mask | GN_MVS_IRQ_BIT_VBLANK);
            if (image->mvs_frame_count != UINT32_MAX) ++image->mvs_frame_count;
        }
        if (to_event == to_animation) gn_mvs_video_animation_tick(image);
    }
    image->mvs_frame_cycle = (uint32_t)position;
}

/* Every return after execution starts must expose the same actual-clock
 * prefix, including failures before the next instruction can begin. */
static gn_status gn_mvs_finish_run(gn_run_result *result, uint64_t budget,
                                   uint64_t elapsed, uint64_t instructions,
                                   gn_run_reason reason, gn_status status) {
    result->elapsed_cycles = elapsed;
    result->overshoot_cycles = elapsed > budget ? elapsed - budget : 0u;
    result->instructions = instructions;
    result->reason = reason;
    return status;
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
    if (cycle_budget == 0u) return gn_run_cpu(instance, 0u, out_result, NULL);

    uint64_t elapsed = 0u;
    uint64_t instructions = 0u;
    gn_run_reason final_reason = GN_RUN_BUDGET;
    while (elapsed < cycle_budget) {
        gn_image *image = instance->image;
        if (image->mvs_watchdog_remaining_cycles == 0u) {
            const gn_status reset_status = gn_mvs_watchdog_soft_reset(image);
            if (reset_status != GN_STATUS_OK) {
                gn_mvs_failure_record_image(image,
                                      GN_MVS_FAILURE_COMPONENT_BOARD,
                                      GN_MVS_FAILURE_STAGE_WATCHDOG_RESET,
                                      GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
                return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, GN_RUN_ERROR, reset_status);
            }
        }

        owned_cpu_observation cpu_observation;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
        if (gn_test_mvs_consume_failure(image, GN_TEST_MVS_FAILURE_MAIN_OBSERVE)) {
            gn_mvs_failure_record_image(image,
                                  GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
                                  GN_MVS_FAILURE_STAGE_OBSERVE,
                                  GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
            return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, GN_RUN_ERROR, GN_STATUS_CPU_FAILURE);
        }
#endif
        if (owned_cpu_observe(image->cpu, &cpu_observation) != OWNED_CPU_OK) {
            gn_mvs_failure_record_image(image,
                                  GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
                                  GN_MVS_FAILURE_STAGE_OBSERVE,
                                  GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
            return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, GN_RUN_ERROR, GN_STATUS_CPU_FAILURE);
        }
        /* Apply the highest pending source level at the instruction boundary.
         * The line is level-sensitive: it stays asserted until the guest
         * acknowledges through $3C000C, so a handler that never acknowledges
         * is entered again as soon as its mask is lowered. */
        const unsigned wanted_level =
            gn_mvs_pending_irq_level(image->mvs_irq_pending_mask);
        if (wanted_level != cpu_observation.irq_level) {
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
            if (gn_test_mvs_consume_failure(
                    image, GN_TEST_MVS_FAILURE_MAIN_IRQ_UPDATE)) {
                gn_mvs_failure_record_image(image,
                                      GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
                                      GN_MVS_FAILURE_STAGE_IRQ_UPDATE,
                                      GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
                return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, GN_RUN_ERROR, GN_STATUS_CPU_FAILURE);
            }
#endif
            if (owned_cpu_set_irq(image->cpu, wanted_level) != OWNED_CPU_OK ||
                owned_cpu_observe(image->cpu, &cpu_observation) != OWNED_CPU_OK) {
                gn_mvs_failure_record_image(image,
                                      GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
                                      GN_MVS_FAILURE_STAGE_IRQ_UPDATE,
                                      GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
                return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, GN_RUN_ERROR, GN_STATUS_CPU_FAILURE);
            }
        }
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
        const int sound_before_progress =
            gn_test_mvs_consume_failure(
                image, GN_TEST_MVS_FAILURE_SOUND_BEFORE_MAIN_PROGRESS);
        const int first_error_precedence = sound_before_progress == 0
            ? gn_test_mvs_consume_failure(
                  image, GN_TEST_MVS_FAILURE_FIRST_ERROR_PRECEDENCE)
            : 0;
        if (sound_before_progress != 0 || first_error_precedence != 0) {
            const gn_status sound_status =
                gn_mvs_sound_advance(&image->mvs_sound, UINT64_C(128));
            if (sound_status != GN_STATUS_OK) {
                gn_mvs_failure_record_sound(
                    image, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                    GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
                if (first_error_precedence != 0) {
                    gn_mvs_failure_record_image(image,
                                          GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
                                          GN_MVS_FAILURE_STAGE_EXECUTE,
                                          GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
                }
                return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, GN_RUN_ERROR, GN_STATUS_CPU_FAILURE);
            }
        }
#endif
        uint64_t step_budget = 1u;
        const unsigned mask = (unsigned)((cpu_observation.sr >> 8) & 7u);
        const unsigned level = cpu_observation.irq_level;
        const int irq_acceptable = cpu_observation.irq7_pending != 0u ||
            (level == 7u && mask < 7u) ||
            (level >= 1u && level <= 6u && level > mask);
        if (cpu_observation.stopped != 0u && !irq_acceptable) {
            /* Nothing can wake the CPU before the watchdog period ends, the
             * budget ends or the next VBlank flip-flop sets, so idle in one
             * step instead of one clock at a time. */
            const uint64_t budget_left = cycle_budget - elapsed;
            step_budget = image->mvs_watchdog_remaining_cycles < budget_left
                ? image->mvs_watchdog_remaining_cycles : budget_left;
            const uint64_t to_vblank = gn_mvs_cycles_to_vblank_irq(image);
            if (to_vblank < step_budget) step_budget = to_vblank;
            const uint64_t to_animation =
                gn_mvs_cycles_to_video_animation_tick(image);
            if (to_animation < step_budget) step_budget = to_animation;
        }

        /* An instruction is about to start at the documented USER entry. IRQ
         * and reset events are not instruction starts. When an acceptable
         * interrupt is pending the boundary PC is a handler-entry preamble, not
         * an instruction start, so it is skipped below. */
        if (cpu_observation.stopped == 0u && !irq_acceptable &&
            cpu_observation.pc == GN_MVS_USER_ENTRY) {
            gn_mvs_protocol_note_user_entry(&image->mvs_protocol);
        }
        if (cpu_observation.stopped == 0u && !irq_acceptable &&
            cpu_observation.pc == GN_MVS_PLAYER_START_ENTRY) {
            gn_mvs_protocol_note_player_start(&image->mvs_protocol);
        }

        const uint32_t pet_generation = image->mvs_watchdog_pet_generation;
        gn_run_result step;
        image->mvs_sound_step_cycles = 0u;
        image->mvs_protocol.guest_active = 1u;
        gn_status run_status;
        owned_cpu_status cpu_status = OWNED_CPU_OK;
        int cpu_status_valid = 0;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
        if (gn_test_mvs_consume_failure(image, GN_TEST_MVS_FAILURE_MAIN_EXECUTE)) {
            memset(&step, 0, sizeof(step));
            step.reason = GN_RUN_ERROR;
            gn_mvs_failure_record_image(image,
                                  GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
                                  GN_MVS_FAILURE_STAGE_EXECUTE,
                                  GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
            run_status = GN_STATUS_CPU_FAILURE;
        } else
#endif
        {
            gn_mvs_save_close_startup(image);
            run_status = gn_run_cpu(instance, step_budget, &step, &cpu_status);
            cpu_status_valid = 1;
        }
        image->mvs_protocol.guest_active = 0u;
#if defined(GLUEYNEO_SDK_TEST_HOOKS)
        const int fail_after_instruction = run_status == GN_STATUS_OK &&
            step.instructions != 0u &&
            gn_test_mvs_consume_failure(
                image, GN_TEST_MVS_FAILURE_MAIN_AFTER_INSTRUCTION);
        const int fail_main_then_sound = run_status == GN_STATUS_OK &&
            step.instructions != 0u && !fail_after_instruction &&
            gn_test_mvs_consume_failure(image,
                GN_TEST_MVS_FAILURE_MAIN_AFTER_INSTRUCTION_THEN_SOUND_TICK_LIMIT);
        if (fail_after_instruction || fail_main_then_sound) {
            gn_mvs_failure_record_image(image,
                                  GN_MVS_FAILURE_COMPONENT_MAIN_CPU,
                                  GN_MVS_FAILURE_STAGE_EXECUTE,
                                  GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
            image->mvs_failure.capture_pending = 1u;
            if (fail_main_then_sound)
                image->mvs_sound.test_fail_tick_limit = 1u;
            run_status = GN_STATUS_CPU_FAILURE;
            step.reason = GN_RUN_ERROR;
        }
#endif
        if (run_status != GN_STATUS_OK && image->mvs_failure.valid == 0u)
            gn_mvs_failure_record_main(image, GN_MVS_FAILURE_STAGE_EXECUTE);
        image->mvs_protocol.cycle_base += step.elapsed_cycles;
        /* Stall diagnosis sampling (observation only). The instruction is
         * bucketed by the SR interrupt mask and PC region it started with; an
         * interrupt is an exception-only step that leaves a level 1-7
         * autovector (vectors 25-31). */
        int interrupt_taken = 0;
        owned_cpu_observation after_step;
        if (owned_cpu_observe(image->cpu, &after_step) == OWNED_CPU_OK) {
            /* An autovector entry is the only event that charges exception
             * clocks with no completed instruction and leaves vector 25-31. The
             * clock charge itself is the owned CPU's business (plan 05-10
             * finding: it charges 72, not the 44 this check once assumed). */
            interrupt_taken =
                after_step.exception_cycles > cpu_observation.exception_cycles &&
                step.instructions == 0u &&
                after_step.last_exception_vector >= 25u &&
                after_step.last_exception_vector <= 31u;
        }
        gn_mvs_protocol_note_step(&image->mvs_protocol,
                                  (unsigned)((cpu_observation.sr >> 8) & 7u),
                                  gn_mvs_classify_pc(cpu_observation.pc),
                                  step.instructions, interrupt_taken);
        elapsed += step.elapsed_cycles;
        instructions += step.instructions;
        if (step.instructions > UINT64_MAX - image->mvs_completed_main_instructions) {
            image->mvs_completed_main_instructions = UINT64_MAX;
            gn_mvs_failure_record_image(image,
                                  GN_MVS_FAILURE_COMPONENT_INTERNAL,
                                  GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING,
                                  GN_MVS_FAILURE_REASON_ACCOUNTING_MISMATCH);
        } else {
            image->mvs_completed_main_instructions += step.instructions;
        }
        gn_mvs_advance_raster(image, step.elapsed_cycles);
        gn_mvs_calendar_advance(&image->mvs_calendar, step.elapsed_cycles);
        gn_status sound_status;
        if (step.elapsed_cycles < image->mvs_sound_step_cycles) {
            gn_mvs_failure_record_image(image,
                                  GN_MVS_FAILURE_COMPONENT_INTERNAL,
                                  GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING,
                                  GN_MVS_FAILURE_REASON_ACCOUNTING_MISMATCH);
            sound_status = run_status == GN_STATUS_OK
                ? GN_STATUS_CPU_FAILURE : run_status;
        } else {
            sound_status = gn_mvs_sound_advance(
                &image->mvs_sound,
                step.elapsed_cycles - image->mvs_sound_step_cycles);
            if (sound_status != GN_STATUS_OK) {
                gn_mvs_failure_record_sound(
                    image, GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                    GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
            }
        }
        out_result->boundary_pc = step.boundary_pc;
        out_result->fault_pc = step.fault_pc;
        out_result->instruction_register = step.instruction_register;
        /* A bounded unsupported/privileged guest instruction is returned as
         * GN_RUN_FAULT with GN_STATUS_OK by gn_run_cpu. Preserve it as the
         * first native execution failure too; otherwise the local qualifier
         * has a run fault but no structured component/site/cause tuple. */
        if (image->mvs_failure.valid == 0u && step.reason == GN_RUN_FAULT) {
            gn_mvs_failure_record_main(image, GN_MVS_FAILURE_STAGE_EXECUTE);
            if (image->mvs_failure.valid != 0u &&
                image->mvs_failure.component == GN_MVS_FAILURE_COMPONENT_MAIN_CPU &&
                image->mvs_failure.stage == GN_MVS_FAILURE_STAGE_EXECUTE) {
                image->mvs_failure.pc = step.fault_pc;
                image->mvs_failure.pc_valid = 1u;
                image->mvs_failure.opcode = step.instruction_register;
                image->mvs_failure.opcode_valid = 1u;
            }
        }
        if (cpu_status_valid != 0)
            gn_mvs_failure_set_owned_cpu_status(image, cpu_status);
        gn_mvs_failure_capture_step(image, &step, cpu_observation.pc);
        if (run_status != GN_STATUS_OK) {
            if (image->mvs_failure.valid == 0u)
                gn_mvs_failure_record_main(image, GN_MVS_FAILURE_STAGE_EXECUTE);
            return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, step.reason, run_status);
        }
        if (sound_status != GN_STATUS_OK) {
            gn_mvs_failure_record_sound(image,
                                        GN_MVS_FAILURE_STAGE_SOUND_CATCHUP,
                                        GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
            return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, GN_RUN_ERROR, sound_status);
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
                gn_mvs_failure_record_image(image,
                                      GN_MVS_FAILURE_COMPONENT_BOARD,
                                      GN_MVS_FAILURE_STAGE_WATCHDOG_RESET,
                                      GN_MVS_FAILURE_REASON_INTERNAL_FAILURE);
                return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, GN_RUN_ERROR, reset_status);
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
    return gn_mvs_finish_run(out_result, cycle_budget, elapsed,
                    instructions, final_reason, GN_STATUS_OK);
}

/* Logical frame consumers repay previously executed instruction excess.
 * Raw budget calls retain their public minimum-budget/actual-clock contract.
 * Raster, sound, calendar and interrupt state advance inside gn_run_mvs using
 * actual executed clocks; carrying excess never advances or replays an event. */
gn_status gn_mvs_run_frame_budget(gn_instance *instance, gn_run_result *out_result) {
    if (instance == NULL || instance->image == NULL || out_result == NULL ||
        instance->image->mvs_region_count == 0u)
        return gn_run_mvs(instance, GN_MVS_FRAME_BUDGET_CYCLES, out_result);
    gn_image *image = instance->image;
    const uint64_t carry = image->mvs_frame_cycle_carry;
    if (carry >= GN_MVS_FRAME_BUDGET_CYCLES) {
        memset(out_result, 0, sizeof(*out_result));
        out_result->reason = GN_RUN_ERROR;
        gn_mvs_failure_record_image(image, GN_MVS_FAILURE_COMPONENT_BOARD,
            GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING,
            GN_MVS_FAILURE_REASON_INVALID_STATE);
        return GN_STATUS_CPU_FAILURE;
    }
    const gn_status status = gn_run_mvs(instance,
        GN_MVS_FRAME_BUDGET_CYCLES - carry, out_result);
    if (out_result->elapsed_cycles > UINT64_MAX - carry) {
        gn_mvs_failure_record_image(image, GN_MVS_FAILURE_COMPONENT_BOARD,
            GN_MVS_FAILURE_STAGE_TIMING_ACCOUNTING,
            GN_MVS_FAILURE_REASON_CLOCK_OVERFLOW);
        out_result->reason = GN_RUN_ERROR;
        return status == GN_STATUS_OK ? GN_STATUS_CPU_FAILURE : status;
    }
    /* A short failed call retains its reported partial frame prefix; failure
     * status stays authoritative. Reset/load clear the prefix and overshoot. */
    image->mvs_frame_cycle_carry =
        (carry + out_result->elapsed_cycles) % GN_MVS_FRAME_BUDGET_CYCLES;
    return status;
}

GN_API gn_status gn_run(gn_instance *instance, uint64_t cycle_budget,
                        gn_run_result *out_result) {
    if (instance != NULL && instance->image != NULL &&
        instance->image->mvs_region_count != 0u) {
        return gn_run_mvs(instance, cycle_budget, out_result);
    }
    return gn_run_cpu(instance, cycle_budget, out_result, NULL);
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

GN_API gn_status gn_observe_mvs_progress(
    const gn_instance *instance, gn_mvs_progress_observation *out_observation,
    size_t out_observation_size) {
    if (out_observation == NULL) return GN_STATUS_INVALID_ARGUMENT;
    const size_t minimum_size =
        offsetof(gn_mvs_progress_observation, player_start_with_p1_indication) +
        sizeof(out_observation->player_start_with_p1_indication);
    if (out_observation_size < minimum_size) return GN_STATUS_INVALID_ARGUMENT;
    gn_mvs_progress_observation current;
    memset(&current, 0, sizeof(current));
    current.size = sizeof(current);
    current.version = GN_MVS_PROGRESS_OBSERVATION_VERSION;
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
    const gn_mvs_protocol *protocol = &instance->image->mvs_protocol;
    current.attract_start_reached = protocol->attract_start_reached;
    current.user_request = protocol->user_request;
    current.player_start_entered = protocol->player_start_entered;
    current.player_start_with_p1_indication = protocol->player_start_with_p1_indication;
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

static uint8_t gn_mvs_expand_palette_component(uint8_t value,
                                               uint32_t resistor_scale) {
    const uint32_t expanded =
        ((uint32_t)value * UINT32_C(255) + UINT32_C(15)) / UINT32_C(31);
    return (uint8_t)((expanded * resistor_scale + UINT32_C(32767)) /
                     UINT32_C(65535));
}

static uint32_t gn_mvs_palette_xrgb(const gn_image *image,
                                    size_t palette_index) {
    const size_t bank_offset = image->mvs_palette_bank_selected != 0u
        ? (size_t)0x2000u : 0u;
    const size_t offset = bank_offset + palette_index * (size_t)2u;
    const uint16_t word = (uint16_t)(((uint16_t)image->mvs_palette_ram[offset]
                                      << 8) |
                                     image->mvs_palette_ram[offset + 1u]);
    /* MAME computes four palette lookup sets from the cited 3900/2200/1000/
     * 470/220-ohm network with 8200-ohm dark and 150-ohm shadow pull-downs.
     * Keep the linear XRGB host representation and apply the corresponding
     * normalized resistor ratios; this is not an analog-output claim. */
    static const uint32_t resistor_scale[4] = {
        UINT32_C(65535), UINT32_C(64595), UINT32_C(36507), UINT32_C(36213)};
    const size_t lookup = (size_t)((word >> 15) & UINT16_C(1)) |
        ((size_t)image->mvs_screen_shadow << 1);
    const uint8_t red5 = (uint8_t)(((word >> 14) & 1u) |
                                   ((word >> 7) & 0x1eu));
    const uint8_t green5 = (uint8_t)(((word >> 13) & 1u) |
                                     ((word >> 3) & 0x1eu));
    const uint8_t blue5 = (uint8_t)(((word >> 12) & 1u) |
                                    ((word << 1) & 0x1eu));
    const uint32_t red = gn_mvs_expand_palette_component(
        red5, resistor_scale[lookup]);
    const uint32_t green = gn_mvs_expand_palette_component(
        green5, resistor_scale[lookup]);
    const uint32_t blue = gn_mvs_expand_palette_component(
        blue5, resistor_scale[lookup]);
    return (red << 16) | (green << 8) | blue;
}

static const uint16_t gn_mvs_sprite_zoom_x[16] = {
    UINT16_C(0x0080), UINT16_C(0x0880), UINT16_C(0x0888), UINT16_C(0x2888),
    UINT16_C(0x288a), UINT16_C(0x2a8a), UINT16_C(0x2aaa), UINT16_C(0xaaaa),
    UINT16_C(0xaaea), UINT16_C(0xbaea), UINT16_C(0xbaeb), UINT16_C(0xbbeb),
    UINT16_C(0xbbef), UINT16_C(0xfbef), UINT16_C(0xfbff), UINT16_C(0xffff)};

static size_t gn_mvs_collect_sprite_line(const gn_image *image,
                                         uint32_t scanline,
                                         uint16_t active[96]) {
    uint32_t y = 0u;
    uint32_t rows = 0u;
    size_t count = 0u;
    for (uint32_t sprite = 0u; sprite < 381u; ++sprite) {
        const uint16_t y_control =
            image->mvs_video_ram[0x8200u | (size_t)sprite];
        if ((y_control & UINT16_C(0x0040)) == 0u) {
            y = UINT32_C(0x200) - ((uint32_t)y_control >> 7);
            rows = y_control & UINT16_C(0x003f);
        }
        if (rows == 0u) continue;
        const uint32_t sprite_line = (scanline - y) & UINT32_C(0x1ff);
        if (rows < UINT32_C(0x20) && sprite_line >= rows * UINT32_C(16))
            continue;
        active[count++] = (uint16_t)sprite;
        if (count == 96u) break;
    }
    return count;
}

static const gn_mvs_owned_region *gn_mvs_y_zoom_region(
    const gn_image *image) {
    for (size_t index = 0u;
         index < image->mvs_region_count &&
         index < GN_MVS_V3_MAX_REGIONS; ++index) {
        if (image->mvs_regions[index].role == GN_MVS_REGION_Y_ZOOM)
            return &image->mvs_regions[index];
    }
    return NULL;
}

static int gn_mvs_sprite_zoom_supported(
    const gn_image *image, const gn_mvs_owned_region *y_zoom) {
    if (y_zoom != NULL && (y_zoom->bytes == NULL ||
                           y_zoom->size != GN_MVS_Y_ZOOM_BYTES)) return 0;
    uint16_t active[96];
    for (uint32_t y = 0u; y < UINT32_C(224); ++y) {
        const uint32_t scanline = UINT32_C(0x10) + y;
        const size_t count =
            gn_mvs_collect_sprite_line(image, scanline, active);
        uint32_t x = 0u;
        uint32_t zoom_x = 0u;
        uint32_t zoom_y = 0u;
        for (size_t index = 0u; index < count; ++index) {
            const uint32_t sprite = active[index];
            const uint16_t y_control =
                image->mvs_video_ram[0x8200u | (size_t)sprite];
            const uint16_t zoom_control =
                image->mvs_video_ram[0x8000u | (size_t)sprite];
            if ((y_control & UINT16_C(0x0040)) != 0u) {
                x = (x + zoom_x + 1u) & UINT32_C(0x1ff);
                zoom_x = (zoom_control >> 8) & UINT16_C(0x000f);
            } else {
                x = image->mvs_video_ram[0x8400u | (size_t)sprite] >> 7;
                zoom_y = zoom_control & UINT16_C(0x00ff);
                zoom_x = (zoom_control >> 8) & UINT16_C(0x000f);
            }
            if (x >= UINT32_C(0x140) && x <= UINT32_C(0x1f0)) continue;
            if (zoom_y != UINT32_C(0xff) &&
                (y_zoom == NULL || y_zoom->bytes == NULL ||
                 y_zoom->size != GN_MVS_Y_ZOOM_BYTES)) return 0;
        }
    }
    return 1;
}

gn_status gn_private_mvs_video_activity(
    const gn_instance *instance,
    gn_mvs_private_video_activity *out_activity) {
    if (out_activity == NULL) return GN_STATUS_INVALID_ARGUMENT;
    memset(out_activity, 0, sizeof(*out_activity));
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    const gn_image *image = instance->image;
    if (image->mvs_region_count == 0u || image->mvs_video_ram == NULL ||
        image->mvs_video_ram_words < (size_t)0x8800u ||
        image->mvs_palette_ram == NULL ||
        image->mvs_palette_ram_size < (size_t)0x4000u) {
        return GN_STATUS_UNSUPPORTED_PROFILE;
    }

    gn_mvs_private_video_activity activity;
    memset(&activity, 0, sizeof(activity));
    for (size_t index = 0u; index < image->mvs_video_ram_words; ++index) {
        if (image->mvs_video_ram[index] != 0u)
            ++activity.nonzero_vram_words;
    }
    for (size_t index = (size_t)0x7000u; index < (size_t)0x8000u; ++index) {
        if (image->mvs_video_ram[index] != 0u)
            ++activity.nonzero_fixed_tilemap_words;
    }
    for (size_t index = (size_t)0x8000u; index < (size_t)0x8800u; ++index) {
        if (image->mvs_video_ram[index] != 0u)
            ++activity.nonzero_sprite_words;
    }
    for (size_t index = 0u; index + 1u < image->mvs_palette_ram_size;
         index += 2u) {
        if (image->mvs_palette_ram[index] != 0u ||
            image->mvs_palette_ram[index + 1u] != 0u) {
            ++activity.nonzero_palette_entries;
        }
    }

    uint8_t visible[381] = {0u};
    uint16_t active[96];
    for (uint32_t line = 0u; line < UINT32_C(224); ++line) {
        const uint32_t scanline = UINT32_C(0x10) + line;
        const size_t count = gn_mvs_collect_sprite_line(image, scanline, active);
        uint32_t x = 0u;
        uint32_t zoom_x = 0u;
        uint32_t zoom_y = 0u;
        for (size_t index = 0u; index < count; ++index) {
            const uint32_t sprite = active[index];
            const uint16_t y_control =
                image->mvs_video_ram[0x8200u | (size_t)sprite];
            const uint16_t zoom_control =
                image->mvs_video_ram[0x8000u | (size_t)sprite];
            if ((y_control & UINT16_C(0x0040)) != 0u) {
                x = (x + zoom_x + 1u) & UINT32_C(0x1ff);
                zoom_x = (zoom_control >> 8) & UINT16_C(0x000f);
            } else {
                x = image->mvs_video_ram[0x8400u | (size_t)sprite] >> 7;
                zoom_y = zoom_control & UINT16_C(0x00ff);
                zoom_x = (zoom_control >> 8) & UINT16_C(0x000f);
            }
            if (x >= UINT32_C(0x140) && x <= UINT32_C(0x1f0)) continue;
            visible[sprite] = 1u;
            if (zoom_y != UINT32_C(0x00ff))
                ++activity.visible_nonfull_y_zoom_samples;
        }
    }
    for (size_t sprite = 0u; sprite < sizeof(visible); ++sprite)
        activity.visible_sprites += visible[sprite];

    const size_t backdrop_offset =
        (image->mvs_palette_bank_selected != 0u ? (size_t)0x2000u : 0u) +
        (size_t)0x0fffu * (size_t)2u;
    activity.backdrop_palette_nonzero =
        (image->mvs_palette_ram[backdrop_offset] != 0u ||
         image->mvs_palette_ram[backdrop_offset + 1u] != 0u) ? 1u : 0u;
    activity.video_ram_offset = image->mvs_video_ram_offset;
    activity.video_ram_modulo = image->mvs_video_ram_modulo;
    activity.frame_count = image->mvs_frame_count;
    activity.frame_cycle = image->mvs_frame_cycle;
    activity.frame_cycle_carry = image->mvs_frame_cycle_carry;
    activity.auto_animation_counter = image->mvs_video_auto_animation_counter;
    activity.palette_bank_selected = image->mvs_palette_bank_selected;
    activity.screen_shadow = image->mvs_screen_shadow;
    activity.video_auto_animation_speed = image->mvs_video_auto_animation_speed;
    activity.video_auto_animation_disabled = image->mvs_video_auto_animation_disabled;
    activity.display_position_interrupt_control =
        image->mvs_display_position_interrupt_control;
    *out_activity = activity;
    return GN_STATUS_OK;
}

static uint8_t gn_mvs_sprite_pen(const gn_mvs_owned_region *sprites,
                                 size_t decoded_size,
                                 size_t decoded_offset) {
    if (decoded_offset >= decoded_size) return 0u;
    const size_t tile = decoded_offset / (size_t)0x100u;
    const size_t in_tile = decoded_offset & (size_t)0xffu;
    const size_t row = in_tile / (size_t)16u;
    const size_t x = in_tile & (size_t)15u;
    const size_t half_base = x < (size_t)8u ? (size_t)0x40u : 0u;
    const size_t bit = x & (size_t)7u;
    const size_t raw_base = tile * (size_t)0x80u;
    if (raw_base > sprites->size || sprites->size - raw_base < (size_t)0x80u)
        return 0u;
    const size_t line_base = raw_base + half_base + row * (size_t)4u;
    const size_t plane_offsets[4] = {
        (size_t)0u, (size_t)2u, (size_t)1u, (size_t)3u};
    uint8_t pen = 0u;
    for (size_t plane = 0u; plane < 4u; ++plane) {
        const uint8_t source = sprites->bytes[line_base + plane_offsets[plane]];
        pen = (uint8_t)(pen | (uint8_t)(((source >> bit) & 1u) << plane));
    }
    return pen;
}

static void gn_mvs_draw_sprite_line(const gn_image *image,
                                    const gn_mvs_owned_region *sprites,
                                    const gn_mvs_owned_region *y_zoom,
                                    size_t decoded_size, size_t address_mask,
                                    uint32_t scanline, uint8_t *row) {
    uint16_t active[96];
    const size_t count =
        gn_mvs_collect_sprite_line(image, scanline, active);
    uint32_t x = 0u;
    uint32_t y = 0u;
    uint32_t rows = 0u;
    uint32_t zoom_x = 0u;
    uint32_t zoom_y = 0u;
    for (size_t index = 0u; index < count; ++index) {
        const uint32_t sprite = active[index];
        const uint16_t y_control =
            image->mvs_video_ram[0x8200u | (size_t)sprite];
        const uint16_t zoom_control =
            image->mvs_video_ram[0x8000u | (size_t)sprite];
        if ((y_control & UINT16_C(0x0040)) != 0u) {
            x = (x + zoom_x + 1u) & UINT32_C(0x1ff);
            zoom_x = (zoom_control >> 8) & UINT16_C(0x000f);
        } else {
            y = UINT32_C(0x200) - ((uint32_t)y_control >> 7);
            rows = y_control & UINT16_C(0x003f);
            x = image->mvs_video_ram[0x8400u | (size_t)sprite] >> 7;
            zoom_y = zoom_control & UINT16_C(0x00ff);
            zoom_x = (zoom_control >> 8) & UINT16_C(0x000f);
        }
        if (x >= UINT32_C(0x140) && x <= UINT32_C(0x1f0)) continue;

        const uint32_t sprite_line = (scanline - y) & UINT32_C(0x1ff);
        uint32_t zoom_line = sprite_line & UINT32_C(0xff);
        int invert = (sprite_line & UINT32_C(0x100)) != 0u;
        if (invert != 0) zoom_line ^= UINT32_C(0xff);
        if (rows > UINT32_C(0x20)) {
            const uint32_t period = (zoom_y + 1u) << 1;
            zoom_line %= period;
            if (zoom_line > zoom_y) {
                zoom_line = period - 1u - zoom_line;
                invert = !invert;
            }
        }
        const uint32_t sprite_x = x;
        uint32_t tile;
        uint32_t sprite_y;
        if (y_zoom != NULL) {
            const size_t lookup_index =
                ((size_t)zoom_y << 8) | (size_t)zoom_line;
            if (lookup_index >= y_zoom->size) continue;
            const uint8_t row_and_tile = y_zoom->bytes[lookup_index];
            tile = (uint32_t)row_and_tile >> 4;
            sprite_y = (uint32_t)row_and_tile & UINT32_C(0x0f);
            if (invert != 0) {
                sprite_y ^= UINT32_C(0x0f);
                tile ^= UINT32_C(0x1f);
            }
        } else {
            uint32_t source_y = zoom_line;
            if (invert != 0) source_y = UINT32_C(0x1ff) - source_y;
            tile = source_y >> 4;
            sprite_y = source_y & UINT32_C(0x0f);
        }
        const size_t attr_offset =
            ((size_t)sprite << 6) | ((size_t)tile << 1);
        const uint16_t attr = image->mvs_video_ram[attr_offset + 1u];
        if ((attr & UINT16_C(0x0002)) != 0u)
            sprite_y ^= UINT32_C(0x0f);
        uint32_t code =
            (((uint32_t)attr << 12) & UINT32_C(0x000f0000)) |
            image->mvs_video_ram[attr_offset];
        if (image->mvs_video_auto_animation_disabled == 0u) {
            if ((attr & UINT16_C(0x0008)) != 0u) {
                code = (code & ~UINT32_C(7)) |
                       (image->mvs_video_auto_animation_counter & 7u);
            } else if ((attr & UINT16_C(0x0004)) != 0u) {
                code = (code & ~UINT32_C(3)) |
                       (image->mvs_video_auto_animation_counter & 3u);
            }
        }
        const int flipped = (attr & UINT16_C(0x0001)) != 0u;
        size_t gfx_base = (((size_t)code << 8) |
                           ((size_t)sprite_y << 4)) & address_mask;
        if (flipped != 0) gfx_base = (gfx_base + (size_t)15u) & address_mask;
        uint32_t output_pixels = 0u;
        uint32_t wrapped_x = 0u;
        uint32_t wrapped_cursor = sprite_x;
        uint16_t zoom_pattern = gn_mvs_sprite_zoom_x[zoom_x];
        for (uint32_t pixel = 0u; pixel < UINT32_C(16); ++pixel) {
            if ((zoom_pattern & UINT16_C(0x8000)) != 0u) {
                const uint8_t pen =
                    gn_mvs_sprite_pen(sprites, decoded_size, gfx_base);
                if (pen != 0u) {
                    const size_t palette_base =
                        (size_t)(attr >> 8) * (size_t)16u;
                    const uint32_t color = gn_mvs_palette_xrgb(
                        image, palette_base + pen);
                    if (sprite_x <= UINT32_C(0x1f0)) {
                        if (sprite_x + output_pixels < UINT32_C(320)) {
                            memcpy(row + ((size_t)sprite_x + output_pixels) * sizeof(color),
                                   &color, sizeof(color));
                        }
                    } else if (wrapped_cursor >= UINT32_C(0x200)) {
                        if (wrapped_x < UINT32_C(320)) {
                            memcpy(row + (size_t)wrapped_x * sizeof(color), &color,
                                   sizeof(color));
                        }
                    }
                }
                if (sprite_x > UINT32_C(0x1f0)) {
                    if (wrapped_cursor >= UINT32_C(0x200)) ++wrapped_x;
                    ++wrapped_cursor;
                } else {
                    ++output_pixels;
                }
            }
            zoom_pattern = (uint16_t)(zoom_pattern << 1);
            if (zoom_pattern == 0u) break;
            gfx_base = flipped != 0
                ? (gfx_base - 1u) & address_mask
                : (gfx_base + 1u) & address_mask;
        }
    }
}

static gn_status gn_private_mvs_render_frame_preflight(
    const gn_instance *instance, uint32_t width, uint32_t height,
    size_t pitch_bytes, const uint8_t *pixels, size_t pixel_capacity_bytes) {
    if (instance == NULL || pixels == NULL || width != UINT32_C(320) ||
        height != UINT32_C(224)) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    const gn_image *image = instance->image;
    if (image->mvs_region_count == 0u) return GN_STATUS_UNSUPPORTED_PROFILE;

    const size_t row_bytes = (size_t)width * sizeof(uint32_t);
    if (pitch_bytes < row_bytes ||
        pitch_bytes > (SIZE_MAX - row_bytes) / (size_t)(height - 1u))
        return GN_STATUS_INVALID_ARGUMENT;
    const size_t required = pitch_bytes * (size_t)(height - 1u) + row_bytes;
    if (pixel_capacity_bytes < required) return GN_STATUS_INVALID_ARGUMENT;

    const gn_mvs_owned_region *fixed = NULL;
    const gn_mvs_owned_region *sprites = NULL;
    const gn_mvs_owned_region *y_zoom = gn_mvs_y_zoom_region(image);
    for (size_t index = 0u;
         index < image->mvs_region_count && index < GN_MVS_V3_MAX_REGIONS;
         ++index) {
        if (image->mvs_regions[index].role == GN_MVS_REGION_FIXED)
            fixed = &image->mvs_regions[index];
        else if (image->mvs_regions[index].role == GN_MVS_REGION_SPRITES)
            sprites = &image->mvs_regions[index];
    }
    if (fixed == NULL || fixed->bytes == NULL ||
        fixed->size != GN_MVS_FIXED_BYTES || sprites == NULL ||
        sprites->bytes == NULL || sprites->size < 0x80u ||
        sprites->size > SIZE_MAX / (size_t)2u ||
        sprites->size % (size_t)0x80u != 0u ||
        image->mvs_palette_ram == NULL ||
        image->mvs_palette_ram_size < (size_t)0x4000u ||
        image->mvs_video_ram == NULL ||
        image->mvs_video_ram_words < (size_t)0x8800u)
        return GN_STATUS_UNSUPPORTED_PROFILE;

    const uint32_t last_scanline = UINT32_C(0x10) + height - 1u;
    const size_t last_fixed_word =
        (size_t)(UINT32_C(0x7000) | (last_scanline >> 3)) +
        (size_t)39u * (size_t)0x20u;
    if (last_fixed_word >= image->mvs_video_ram_words)
        return GN_STATUS_UNSUPPORTED_PROFILE;
    const size_t decoded_size = sprites->size * (size_t)2u;
    size_t decoded_capacity = (size_t)1u;
    while (decoded_capacity < decoded_size) {
        if (decoded_capacity > SIZE_MAX / (size_t)2u)
            return GN_STATUS_UNSUPPORTED_PROFILE;
        decoded_capacity *= (size_t)2u;
    }
    if (decoded_capacity == 0u ||
        !gn_mvs_sprite_zoom_supported(image, y_zoom))
        return GN_STATUS_UNSUPPORTED_PROFILE;
    return GN_STATUS_OK;
}

gn_status gn_private_mvs_render_frame(const gn_instance *instance,
                                      uint32_t width, uint32_t height,
                                      size_t pitch_bytes, uint8_t *pixels,
                                      size_t pixel_capacity_bytes,
                                      size_t *out_pixels_produced) {
    if (out_pixels_produced == NULL) return GN_STATUS_INVALID_ARGUMENT;
    *out_pixels_produced = 0u;
    if (instance == NULL || pixels == NULL || width != UINT32_C(320) ||
        height != UINT32_C(224)) {
        return GN_STATUS_INVALID_ARGUMENT;
    }
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    const gn_image *image = instance->image;
    if (image->mvs_region_count == 0u)
        return GN_STATUS_UNSUPPORTED_PROFILE;

    const size_t row_bytes = (size_t)width * sizeof(uint32_t);
    if (pitch_bytes < row_bytes ||
        pitch_bytes > (SIZE_MAX - row_bytes) / (size_t)(height - 1u)) {
        return GN_STATUS_INVALID_ARGUMENT;
    }
    const size_t required = pitch_bytes * (size_t)(height - 1u) + row_bytes;
    if (pixel_capacity_bytes < required) return GN_STATUS_INVALID_ARGUMENT;

    const gn_mvs_owned_region *fixed = NULL;
    const gn_mvs_owned_region *sprites = NULL;
    const gn_mvs_owned_region *y_zoom = gn_mvs_y_zoom_region(image);
    for (size_t index = 0u;
         index < image->mvs_region_count &&
         index < GN_MVS_V3_MAX_REGIONS;
         ++index) {
        if (image->mvs_regions[index].role == GN_MVS_REGION_FIXED) {
            fixed = &image->mvs_regions[index];
        } else if (image->mvs_regions[index].role == GN_MVS_REGION_SPRITES) {
            sprites = &image->mvs_regions[index];
        }
    }
    if (fixed == NULL || fixed->bytes == NULL ||
        fixed->size != GN_MVS_FIXED_BYTES ||
        sprites == NULL || sprites->bytes == NULL || sprites->size < 0x80u ||
        sprites->size > SIZE_MAX / (size_t)2u ||
        sprites->size % (size_t)0x80u != 0u ||
        image->mvs_palette_ram == NULL ||
        image->mvs_palette_ram_size < (size_t)0x4000u ||
        image->mvs_video_ram == NULL ||
        image->mvs_video_ram_words < (size_t)0x8800u) {
        return GN_STATUS_UNSUPPORTED_PROFILE;
    }

    /* MAME's raw active area starts at horizontal pixel 0x01c and scanline
     * 0x010. The public native frame is the cropped 320x224 visible area. */
    const uint32_t first_scanline = UINT32_C(0x10);
    const uint32_t last_scanline = first_scanline + height - 1u;
    const size_t last_fixed_word =
        (size_t)(UINT32_C(0x7000) | (last_scanline >> 3)) +
        (size_t)39u * (size_t)0x20u;
    if (last_fixed_word >= image->mvs_video_ram_words) {
        return GN_STATUS_UNSUPPORTED_PROFILE;
    }
    const size_t decoded_size = sprites->size * (size_t)2u;
    size_t decoded_capacity = (size_t)1u;
    while (decoded_capacity < decoded_size) {
        if (decoded_capacity > SIZE_MAX / (size_t)2u)
            return GN_STATUS_UNSUPPORTED_PROFILE;
        decoded_capacity *= (size_t)2u;
    }
    const size_t sprite_address_mask = decoded_capacity - 1u;
    if (decoded_capacity == 0u ||
        !gn_mvs_sprite_zoom_supported(image, y_zoom))
        return GN_STATUS_UNSUPPORTED_PROFILE;

    static const uint8_t fixed_pixel_offsets[4] = {
        UINT8_C(0x10), UINT8_C(0x18), UINT8_C(0x00), UINT8_C(0x08)};
    const size_t fixed_mask = fixed->size - 1u;
    const uint32_t backdrop = gn_mvs_palette_xrgb(image, (size_t)0x0fffu);
    for (uint32_t y = 0u; y < height; ++y) {
        const uint32_t scanline = first_scanline + y;
        uint8_t *row = pixels + (size_t)y * pitch_bytes;
        for (uint32_t x = 0u; x < width; ++x) {
            memcpy(row + (size_t)x * sizeof(backdrop), &backdrop,
                   sizeof(backdrop));
        }

        gn_mvs_draw_sprite_line(image, sprites, y_zoom, decoded_size,
                                sprite_address_mask, scanline, row);

        const size_t map_row = (size_t)(UINT32_C(0x7000) |
                                        (scanline >> 3));
        for (size_t column = 0u; column < (size_t)40u; ++column) {
            const size_t map_index = map_row + column * (size_t)0x20u;
            const uint16_t code_and_palette = image->mvs_video_ram[map_index];
            const uint16_t code = code_and_palette & UINT16_C(0x0fff);
            const size_t palette_base =
                (size_t)(code_and_palette >> 12) * (size_t)16u;
            const uint32_t gfx_row = (uint32_t)code << 5 |
                                     (scanline & UINT32_C(7));
            for (size_t group = 0u; group < 4u; ++group) {
                const size_t fixed_offset =
                    ((size_t)gfx_row + fixed_pixel_offsets[group]) & fixed_mask;
                const uint8_t packed = fixed->bytes[fixed_offset];
                const uint8_t pens[2] = {packed & UINT8_C(0x0f),
                                         (uint8_t)(packed >> 4)};
                for (size_t pixel = 0u; pixel < 2u; ++pixel) {
                    if (pens[pixel] == 0u) continue;
                    const size_t x = column * (size_t)8u + group * (size_t)2u + pixel;
                    const uint32_t color = gn_mvs_palette_xrgb(
                        image, palette_base + pens[pixel]);
                    memcpy(row + x * sizeof(color), &color, sizeof(color));
                }
            }
        }
    }
    *out_pixels_produced = (size_t)width * (size_t)height;
    return GN_STATUS_OK;
}

gn_status gn_private_mvs_save_ram_view(gn_instance *instance,
                                       uint8_t **out_bytes,
                                       size_t *out_size) {
    if (out_bytes != NULL) *out_bytes = NULL;
    if (out_size != NULL) *out_size = 0u;
    if (out_bytes == NULL || out_size == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    if (instance == NULL) return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;

    gn_image *const image = instance->image;
    if (image->profile != GN_MVS_PROFILE_MSX ||
        image->mvs_region_count == 0u)
        return GN_STATUS_UNSUPPORTED_PROFILE;
    if (image->mvs_save_ram == NULL || image->mvs_save_ram_size == 0u)
        return GN_STATUS_INVALID_STATE;

    *out_bytes = image->mvs_save_ram;
    *out_size = image->mvs_save_ram_size;
    return GN_STATUS_OK;
}

static int gn_mvs_buffer_range(const void *buffer, size_t bytes,
                               uintptr_t *out_begin, uintptr_t *out_end) {
    if (buffer == NULL || bytes == 0u || out_begin == NULL || out_end == NULL)
        return 0;
    const uintptr_t begin = (uintptr_t)buffer;
    if (bytes > UINTPTR_MAX - begin) return 0;
    *out_begin = begin;
    *out_end = begin + (uintptr_t)bytes;
    return 1;
}

static int gn_mvs_ranges_overlap(uintptr_t first_begin, uintptr_t first_end,
                                 uintptr_t second_begin, uintptr_t second_end) {
    return first_begin < second_end && second_begin < first_end;
}

GN_API gn_status gn_mvs_audio_capacity_v1(const gn_instance *instance,
                                           size_t *out_capacity_frames) {
    if (instance == NULL || out_capacity_frames == NULL)
        return GN_STATUS_INVALID_ARGUMENT;
    if (instance->image == NULL || instance->image->mvs_region_count == 0u)
        return GN_STATUS_INVALID_STATE;
    if (instance->image->profile != GN_MVS_PROFILE_MSX)
        return GN_STATUS_UNSUPPORTED_PROFILE;
    *out_capacity_frames = GN_MVS_AUDIO_CAPACITY_FRAMES_V1;
    return GN_STATUS_OK;
}

GN_API gn_status gn_mvs_advance_frame_v1(
    gn_instance *instance, const gn_mvs_frame_request_v1 *request,
    size_t request_size, gn_mvs_frame_result_v1 *out_result,
    size_t result_size) {
    if (instance == NULL || request == NULL || out_result == NULL ||
        request_size != sizeof(*request) || result_size != sizeof(*out_result))
        return GN_STATUS_INVALID_ARGUMENT;

    const gn_mvs_frame_request_v1 frame = *request;
    uintptr_t request_begin = 0u, request_end = 0u;
    uintptr_t result_begin = 0u, result_end = 0u;
    if (!gn_mvs_buffer_range(request, sizeof(*request), &request_begin,
                             &request_end) ||
        !gn_mvs_buffer_range(out_result, sizeof(*out_result), &result_begin,
                             &result_end) ||
        gn_mvs_ranges_overlap(request_begin, request_end,
                              result_begin, result_end))
        return GN_STATUS_INVALID_ARGUMENT;

    if (frame.version != GN_MVS_FRAME_REQUEST_V1_VERSION ||
        (frame.input_mask & ~GN_MVS_INPUT_SUPPORTED_MASK) != 0u ||
        frame.pixel_format != GN_PIXEL_XRGB8888 || frame.width != 320u ||
        frame.height != 224u || frame.pixels == NULL ||
        (frame.audio == NULL && frame.audio_capacity_frames != 0u) ||
        (frame.audio != NULL &&
         (uintptr_t)frame.audio % (uintptr_t)_Alignof(int16_t) != 0u) ||
        (frame.audio != NULL && frame.audio_capacity_frames <
                                    GN_MVS_PCM_MAX_OUTPUT_FRAMES) ||
        frame.audio_capacity_frames > SIZE_MAX /
            (sizeof(int16_t) * (size_t)2u))
        return GN_STATUS_INVALID_ARGUMENT;

    const size_t row_bytes = (size_t)frame.width * sizeof(uint32_t);
    if (frame.pitch_bytes < row_bytes ||
        frame.pitch_bytes >
            (SIZE_MAX - row_bytes) / (size_t)(frame.height - 1u))
        return GN_STATUS_INVALID_ARGUMENT;
    const size_t required_pixels = frame.pitch_bytes *
        (size_t)(frame.height - 1u) + row_bytes;
    if (frame.pixel_capacity_bytes < required_pixels)
        return GN_STATUS_INVALID_ARGUMENT;

    size_t audio_capacity_bytes = 0u;
    if (frame.audio != NULL)
        audio_capacity_bytes = frame.audio_capacity_frames * sizeof(int16_t) *
                               (size_t)2u;
    uintptr_t pixels_begin = 0u, pixels_end = 0u;
    uintptr_t audio_begin = 0u, audio_end = 0u;
    if (!gn_mvs_buffer_range(frame.pixels, frame.pixel_capacity_bytes,
                             &pixels_begin, &pixels_end))
        return GN_STATUS_INVALID_ARGUMENT;
    if (frame.audio != NULL &&
        !gn_mvs_buffer_range(frame.audio, audio_capacity_bytes,
                             &audio_begin, &audio_end))
        return GN_STATUS_INVALID_ARGUMENT;
    if (gn_mvs_ranges_overlap(request_begin, request_end,
                              pixels_begin, pixels_end) ||
        gn_mvs_ranges_overlap(result_begin, result_end,
                              pixels_begin, pixels_end) ||
        (frame.audio != NULL &&
         (gn_mvs_ranges_overlap(request_begin, request_end,
                                audio_begin, audio_end) ||
          gn_mvs_ranges_overlap(result_begin, result_end,
                                audio_begin, audio_end) ||
          gn_mvs_ranges_overlap(pixels_begin, pixels_end,
                                audio_begin, audio_end))))
        return GN_STATUS_INVALID_ARGUMENT;

    if (instance->image == NULL) return GN_STATUS_INVALID_STATE;
    if (instance->image->mvs_region_count == 0u ||
        instance->image->profile != GN_MVS_PROFILE_MSX)
        return GN_STATUS_UNSUPPORTED_PROFILE;
    const gn_status video_status = gn_private_mvs_render_frame_preflight(
        instance, frame.width, frame.height, frame.pitch_bytes, frame.pixels,
        frame.pixel_capacity_bytes);
    if (video_status != GN_STATUS_OK) return video_status;

    memset(out_result, 0, sizeof(*out_result));
    out_result->version = GN_MVS_FRAME_RESULT_V1_VERSION;
    out_result->reason = GN_RUN_ERROR;
    out_result->audio_format = GN_AUDIO_S16_INTERLEAVED_STEREO;
    out_result->audio_sample_rate = UINT32_C(48000);
    out_result->audio_channels = 2u;
    out_result->frame_time_denominator = UINT64_C(12000000);
    out_result->machine_clock_hz_numerator = UINT32_C(12000000);
    out_result->machine_clock_hz_denominator = 1u;

    const gn_status input_status =
        gn_set_mvs_inputs(instance, frame.input_mask);
    if (input_status != GN_STATUS_OK) return input_status;

    gn_mvs_sound *sound = &instance->image->mvs_sound;
    sound->pcm_active_sink = frame.audio;
    sound->pcm_active_capacity_frames = frame.audio_capacity_frames;
    sound->pcm_call_generated_frames = 0u;
    sound->pcm_call_delivered_frames = 0u;
    sound->pcm_capture_active = 1u;
    gn_run_result run;
    const gn_status run_status = gn_mvs_run_frame_budget(instance, &run);
    const size_t generated = sound->pcm_call_generated_frames;
    const size_t delivered = sound->pcm_call_delivered_frames;
    sound->pcm_active_sink = NULL;
    sound->pcm_active_capacity_frames = 0u;
    sound->pcm_capture_active = 0u;
    sound->pcm_call_generated_frames = 0u;
    sound->pcm_call_delivered_frames = 0u;

    out_result->requested_cycles = run.requested_cycles;
    out_result->elapsed_cycles = run.elapsed_cycles;
    out_result->instructions = run.instructions;
    out_result->frame_time_numerator = run.elapsed_cycles;
    out_result->reason = run.reason;
    out_result->audio_frames_generated = generated;
    out_result->audio_frames_delivered = delivered;
    out_result->audio_frames_discarded = generated - delivered;
    if (run_status != GN_STATUS_OK) return run_status;
    if (run.reason == GN_RUN_FAULT || run.reason == GN_RUN_ERROR)
        return GN_STATUS_CPU_FAILURE;

    size_t pixels_produced = 0u;
    const gn_status render_status = gn_private_mvs_render_frame(
        instance, frame.width, frame.height, frame.pitch_bytes, frame.pixels,
        frame.pixel_capacity_bytes, &pixels_produced);
    if (render_status != GN_STATUS_OK) return render_status;
    out_result->video_pixels_produced = pixels_produced;
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
    if (instance->image != NULL) gn_mvs_save_load_committed(instance);
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
