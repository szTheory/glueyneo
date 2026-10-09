/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "../../src/sdk_private.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HEADER_BYTES 16u
#define REGION_HEADER_BYTES 12u
#define MAX_BUNDLE_BYTES (GN_MVS_MAX_MEDIA_BYTES + HEADER_BYTES + \
                          GN_MVS_MAX_REGIONS * REGION_HEADER_BYTES)
#define MAX_RUN_CHUNKS 256u

typedef struct {
    uint32_t chunks;
    uint32_t stable_chunks;
    uint32_t output_transition_chunks;
    uint32_t video_transition_chunks;
    uint32_t bank_transition_chunks;
    uint32_t watchdog_pet_count;
    uint32_t watchdog_reset_count;
    uint8_t repeated_boundary_suffix;
} local_profile;

static int same_output_state(const gn_mvs_bus_fault_observation *left,
                             const gn_mvs_bus_fault_observation *right) {
    return left->mvs_output_data == right->mvs_output_data &&
           left->mvs_output_latch == right->mvs_output_latch &&
           left->mvs_cart_audio_selected == right->mvs_cart_audio_selected &&
           left->mvs_coin_lockout_mask == right->mvs_coin_lockout_mask &&
           left->mvs_save_ram_unlocked == right->mvs_save_ram_unlocked;
}

static int same_video_state(const gn_mvs_bus_fault_observation *left,
                            const gn_mvs_bus_fault_observation *right) {
    return left->video_ram_offset == right->video_ram_offset &&
           left->video_ram_modulo == right->video_ram_modulo &&
           left->video_auto_animation_speed == right->video_auto_animation_speed &&
           left->video_auto_animation_disabled == right->video_auto_animation_disabled &&
           left->display_position_interrupt_control ==
               right->display_position_interrupt_control;
}

static int same_bank_state(const gn_mvs_bus_fault_observation *left,
                           const gn_mvs_bus_fault_observation *right) {
    return left->mvs_palette_bank_selected == right->mvs_palette_bank_selected;
}

static void count_state_transition(local_profile *profile,
                                   const gn_mvs_bus_fault_observation *previous,
                                   const gn_mvs_bus_fault_observation *current) {
    int changed = 0;
    if (!same_output_state(previous, current)) {
        ++profile->output_transition_chunks;
        changed = 1;
    }
    if (!same_video_state(previous, current)) {
        ++profile->video_transition_chunks;
        changed = 1;
    }
    if (!same_bank_state(previous, current)) {
        ++profile->bank_transition_chunks;
        changed = 1;
    }
    if (!changed) ++profile->stable_chunks;
}

static int repeated_boundary_suffix(const uint32_t *boundaries, size_t count) {
    const size_t max_period = count / 2u < 8u ? count / 2u : 8u;
    for (size_t period = 1u; period <= max_period; ++period) {
        int matches = 1;
        for (size_t index = 0u; index < period; ++index) {
            if (boundaries[count - period + index] !=
                boundaries[count - 2u * period + index]) {
                matches = 0;
                break;
            }
        }
        if (matches) return 1;
    }
    return 0;
}

static uint32_t read32be(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}
static uint64_t read64be(const uint8_t *p) {
    return ((uint64_t)read32be(p) << 32) | read32be(p + 4u);
}

static int load_bundle(const uint8_t *bytes, size_t size, gn_mvs_manifest *manifest) {
    if (size < HEADER_BYTES || memcmp(bytes, "GNMV", 4u) != 0 ||
        read32be(bytes + 4u) != 1u ||
        read32be(bytes + 8u) != GN_MVS_PROFILE_MSX ||
        read32be(bytes + 12u) != GN_MVS_MAX_REGIONS) return 0;
    memset(manifest, 0, sizeof(*manifest));
    manifest->version = GN_MVS_MANIFEST_VERSION;
    manifest->profile = GN_MVS_PROFILE_MSX;
    manifest->region_count = GN_MVS_MAX_REGIONS;
    size_t cursor = HEADER_BYTES;
    for (size_t i = 0u; i < manifest->region_count; ++i) {
        if (cursor > size || size - cursor < REGION_HEADER_BYTES) return 0;
        const uint32_t role = read32be(bytes + cursor);
        const uint64_t length = read64be(bytes + cursor + 4u);
        cursor += REGION_HEADER_BYTES;
        if (length > SIZE_MAX || length > size - cursor) return 0;
        manifest->regions[i] = (gn_mvs_region){
            (gn_mvs_region_role)role, bytes + cursor, (size_t)length,
            (size_t)length, GN_MVS_LAYOUT_LINEAR};
        cursor += (size_t)length;
    }
    return cursor == size;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *file = fopen(argv[1], "rb");
    if (file == NULL || fseek(file, 0, SEEK_END) != 0) {
        if (file != NULL) fclose(file);
        puts("{\"status\":\"normalized_bundle_unavailable\"}");
        return 1;
    }
    const long length = ftell(file);
    if (length < 0 || (unsigned long)length > MAX_BUNDLE_BYTES ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file); puts("{\"status\":\"normalized_bundle_out_of_bounds\"}"); return 1;
    }
    uint8_t *bytes = (uint8_t *)malloc((size_t)length);
    if (bytes == NULL || fread(bytes, 1u, (size_t)length, file) != (size_t)length) {
        free(bytes); fclose(file);
        puts("{\"status\":\"normalized_bundle_read_failed\"}"); return 1;
    }
    fclose(file);
    gn_mvs_manifest manifest;
    if (!load_bundle(bytes, (size_t)length, &manifest)) {
        free(bytes); puts("{\"status\":\"normalized_bundle_malformed\"}"); return 1;
    }
    gn_instance *instance = NULL;
    if (gn_create(&instance) != GN_STATUS_OK || instance == NULL) {
        free(bytes); puts("{\"status\":\"native_instance_unavailable\"}"); return 1;
    }
    const gn_status load_status = gn_load_mvs(instance, &manifest);
    free(bytes);
    if (load_status != GN_STATUS_OK) {
        gn_destroy(instance); puts("{\"status\":\"normalized_profile_rejected\"}"); return 1;
    }
    uint32_t last_pc = 0u;
    uint16_t last_opcode = 0u;
    uint64_t total_instructions = 0u;
    uint64_t total_cycles = 0u;
    local_profile profile = {0};
    uint32_t chunk_boundaries[MAX_RUN_CHUNKS] = {0};
    gn_mvs_bus_fault_observation previous_observation;
    memset(&previous_observation, 0, sizeof(previous_observation));
    int have_previous_observation =
        gn_observe_mvs_bus_fault(instance, &previous_observation,
                                 sizeof(previous_observation)) == GN_STATUS_OK;
    for (size_t iteration = 0u; iteration < MAX_RUN_CHUNKS; ++iteration) {
        gn_run_result result;
        const gn_status status = gn_run_mvs(instance, GN_MAX_CYCLE_BUDGET, &result);
        if (status != GN_STATUS_OK || result.reason == GN_RUN_ERROR) {
            gn_mvs_bus_fault_observation observation;
            if (status == GN_STATUS_CPU_FAILURE && result.reason == GN_RUN_ERROR &&
                gn_observe_mvs_bus_fault(instance, &observation,
                                         sizeof(observation)) == GN_STATUS_OK &&
                observation.version == GN_MVS_BUS_FAULT_OBSERVATION_VERSION &&
                observation.valid == 1u &&
                (observation.access == GN_MVS_BUS_ACCESS_READ ||
                 observation.access == GN_MVS_BUS_ACCESS_WRITE)) {
                printf("{\"status\":\"mvs_bus_access_fault\",\"guest_executed\":true,"
                       "\"first_unsupported_event\":{\"kind\":\"mvs_bus_access\","
                       "\"address\":%u,\"operation\":\"%s\",\"width\":%u,"
                       "\"mame_unmapped_write_count\":%u}}\n",
                       observation.address,
                       observation.access == GN_MVS_BUS_ACCESS_READ ? "read" : "write",
                       (unsigned)observation.width,
                       observation.mame_unmapped_write_count);
                gn_destroy(instance); return 0;
            }
            gn_destroy(instance); puts("{\"status\":\"native_execution_error\"}"); return 1;
        }
        last_pc = result.boundary_pc;
        last_opcode = result.instruction_register;
        chunk_boundaries[profile.chunks++] = result.boundary_pc;
        total_instructions += result.instructions;
        total_cycles += result.elapsed_cycles;
        gn_mvs_bus_fault_observation current_observation;
        memset(&current_observation, 0, sizeof(current_observation));
        if (gn_observe_mvs_bus_fault(instance, &current_observation,
                                     sizeof(current_observation)) == GN_STATUS_OK) {
            if (have_previous_observation != 0)
                count_state_transition(&profile, &previous_observation,
                                       &current_observation);
            previous_observation = current_observation;
            have_previous_observation = 1;
        }
        if (result.reason == GN_RUN_FAULT) {
            gn_mvs_bus_fault_observation observation;
            memset(&observation, 0, sizeof(observation));
            (void)gn_observe_mvs_bus_fault(instance, &observation,
                                            sizeof(observation));
            printf("{\"status\":\"unsupported_guest_event\",\"guest_executed\":true,"
                   "\"first_unsupported_event\":{\"pc\":%u,\"opcode\":%u,"
                   "\"mame_unmapped_write_count\":%u,"
                   "\"mame_watchdog_pet_count\":%u,"
                   "\"mame_watchdog_reset_count\":%u}}\n",
                   result.fault_pc, (unsigned)result.instruction_register,
                   observation.mame_unmapped_write_count,
                   observation.mame_watchdog_pet_count,
                   observation.mame_watchdog_reset_count);
            gn_destroy(instance); return 0;
        }
        if (result.reason == GN_RUN_STOPPED) {
            gn_destroy(instance);
            puts("{\"status\":\"guest_stopped\",\"guest_executed\":true}");
            return 0;
        }
    }
    gn_mvs_bus_fault_observation observation;
    memset(&observation, 0, sizeof(observation));
    (void)gn_observe_mvs_bus_fault(instance, &observation, sizeof(observation));
    profile.watchdog_pet_count = observation.mame_watchdog_pet_count;
    profile.watchdog_reset_count = observation.mame_watchdog_reset_count;
    profile.repeated_boundary_suffix =
        (uint8_t)repeated_boundary_suffix(chunk_boundaries, profile.chunks);
    owned_cpu_fetch_trace_event fetches[OWNED_CPU_FETCH_TRACE_CAPACITY];
    size_t fetch_count = 0u;
    (void)gn_private_mvs_fetch_trace(instance, fetches,
                                     OWNED_CPU_FETCH_TRACE_CAPACITY, &fetch_count);
    printf("{\"status\":\"guest_instruction_budget_exhausted\",\"guest_executed\":true,"
           "\"profile\":{\"chunks\":%u,\"stable_chunks\":%u,"
           "\"output_transition_chunks\":%u,\"video_transition_chunks\":%u,"
           "\"bank_transition_chunks\":%u,\"watchdog_pet_count\":%u,"
           "\"watchdog_reset_count\":%u,\"repeated_boundary_suffix\":%s},"
           "\"last_execution\":{\"pc\":%u,\"opcode\":%u,\"instructions\":%llu,"
           "\"elapsed_cycles\":%llu,\"mame_watchdog_reset_count\":%u},"
           "\"recent_fetches\":[",
           profile.chunks, profile.stable_chunks,
           profile.output_transition_chunks, profile.video_transition_chunks,
           profile.bank_transition_chunks, profile.watchdog_pet_count,
           profile.watchdog_reset_count,
           profile.repeated_boundary_suffix != 0u ? "true" : "false",
           last_pc, (unsigned)last_opcode, (unsigned long long)total_instructions,
           (unsigned long long)total_cycles,
           observation.mame_watchdog_reset_count);
    for (size_t index = 0u; index < fetch_count; ++index) {
        printf("%s{\"pc\":%u,\"word\":%u,\"cursor\":%u,\"run\":%llu,\"cycles\":%llu}",
               index == 0u ? "" : ",", fetches[index].prefetch_pc,
               (unsigned)fetches[index].fetched_word,
               fetches[index].resulting_cursor,
               (unsigned long long)fetches[index].run_sequence,
               (unsigned long long)fetches[index].total_cycles);
    }
    puts("]}");
    gn_destroy(instance);
    return 0;
}
