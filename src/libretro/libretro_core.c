/* SPDX-License-Identifier: MIT */
#include "glueyneo/glueyneo.h"
#include "libretro.h"
#include "../sdk_private.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#define GNFX_HEADER_SIZE 16u
#define GNFX_ROM_SIZE 512u
#define GNFX_RAM_SEED_SIZE 10u
#define GNFX_TILE_SIZE 64u
#define GNFX_PAYLOAD_SIZE (GNFX_ROM_SIZE + GNFX_RAM_SEED_SIZE + GNFX_TILE_SIZE)
#define GNFX_CONTENT_SIZE (GNFX_HEADER_SIZE + GNFX_PAYLOAD_SIZE)
#define GN_FRAME_WIDTH 320u
#define GN_FRAME_HEIGHT 224u
#define GN_FRAME_PITCH (GN_FRAME_WIDTH * sizeof(uint32_t))
#define GN_FRAME_BYTES (GN_FRAME_PITCH * GN_FRAME_HEIGHT)
#define GN_AUDIO_MAX_FRAMES 800u
#define GN_MVS_AUDIO_MAX_FRAMES GN_MVS_AUDIO_CAPACITY_FRAMES_V1

_Static_assert(GN_MVS_AUDIO_CAPACITY_FRAMES_V1 <=
                   SIZE_MAX / (sizeof(int16_t) * (size_t)2u),
               "MVS PCM capacity must fit its interleaved S16 byte buffer");

static retro_environment_t environment_cb;
static retro_log_printf_t log_cb;
static retro_video_refresh_t video_cb;
static retro_audio_sample_t audio_cb;
static retro_audio_sample_batch_t audio_batch_cb;
static retro_input_poll_t input_poll_cb;
static retro_input_state_t input_state_cb;
static gn_instance *instance;
static bool instance_is_mvs;
static bool av_timing_update_pending;
static size_t mvs_state_capacity;
static bool mvs_start_indication_logged;
static bool mvs_runtime_failure_logged;
static unsigned mvs_video_frames;
static uint32_t pixels[GN_FRAME_WIDTH * GN_FRAME_HEIGHT];
static int16_t audio_samples[GN_AUDIO_MAX_FRAMES * 2u];
static int16_t mvs_audio_samples[GN_MVS_AUDIO_MAX_FRAMES * 2u];
static size_t mvs_audio_capacity_frames;
static uint64_t mvs_audio_frames_generated;
static uint64_t mvs_audio_frames_submitted;
static uint64_t mvs_audio_frames_processed;
static uint64_t mvs_audio_frames_discarded;
static uint64_t mvs_audio_overreported_callbacks;
static bool mvs_audio_drop_warning_logged;
static bool mvs_audio_overreport_warning_logged;

#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
#define GN_CONTINUATION_WINDOW_FRAMES 4u
#define GN_CONTINUATION_RAW_CHUNK_BYTES 192u
#define GN_CONTINUATION_LOG_BUDGET ((size_t)8u * 1024u * 1024u)

static struct {
    uint64_t executed_cycles;
    uint64_t restore_cycles;
    uint64_t completed_frames;
    size_t emitted_bytes;
    unsigned frames_in_window;
    bool active;
    bool incomplete_emitted;
} continuation_observation;
static bool continuation_save_ram_data_logged;
static bool continuation_save_ram_size_logged;

static void continuation_log_line(const char *line) {
    const size_t length = strlen(line);
    if (log_cb == NULL) {
        continuation_observation.active = false;
        continuation_observation.incomplete_emitted = true;
        return;
    }
    if (length > GN_CONTINUATION_LOG_BUDGET -
                     continuation_observation.emitted_bytes) {
        if (!continuation_observation.incomplete_emitted) {
            log_cb(RETRO_LOG_ERROR, "glueyneo: continuation X %u\n",
                   continuation_observation.frames_in_window);
            continuation_observation.incomplete_emitted = true;
        }
        continuation_observation.active = false;
        return;
    }
    continuation_observation.emitted_bytes += length;
    log_cb(RETRO_LOG_INFO, "%s", line);
}

static void continuation_incomplete(void) {
    char line[96];
    if (!continuation_observation.active ||
        continuation_observation.incomplete_emitted) return;
    const int length = snprintf(line, sizeof(line),
        "glueyneo: continuation X %u\n",
        continuation_observation.frames_in_window);
    continuation_observation.active = false;
    continuation_observation.incomplete_emitted = true;
    if (length > 0 && (size_t)length < sizeof(line))
        continuation_log_line(line);
}

static void continuation_note_capture(size_t size) {
    char line[128];
    const int length = snprintf(line, sizeof(line),
        "glueyneo: continuation S %zu %" PRIu64 " %" PRIu64 "\n",
        size, continuation_observation.completed_frames,
        continuation_observation.executed_cycles);
    if (length > 0 && (size_t)length < sizeof(line))
        continuation_log_line(line);
}

static void continuation_note_raw(char kind, uint64_t frame,
                                  const uint8_t *bytes, size_t size);

static void continuation_note_restore(size_t size, const uint8_t *state) {
    if (continuation_observation.active) continuation_incomplete();
    continuation_observation.active = false;
    continuation_observation.incomplete_emitted = false;
    continuation_observation.emitted_bytes = 0u;
    continuation_observation.frames_in_window = 0u;
    continuation_observation.restore_cycles =
        continuation_observation.executed_cycles;
    char line[128];
    const int length = snprintf(line, sizeof(line),
        "glueyneo: continuation R %zu %" PRIu64 " %" PRIu64 "\n",
        size, continuation_observation.completed_frames,
        continuation_observation.executed_cycles);
    if (length <= 0 || (size_t)length >= sizeof(line)) return;
    continuation_observation.active = true;
    continuation_log_line(line);
    continuation_note_raw('M', 0u, state, size);
}

static void continuation_note_raw(char kind, uint64_t frame,
                                  const uint8_t *bytes, size_t size) {
    static const char digits[] = "0123456789abcdef";
    for (size_t offset = 0u; continuation_observation.active && offset < size;) {
        const size_t chunk = size - offset < GN_CONTINUATION_RAW_CHUNK_BYTES
            ? size - offset : GN_CONTINUATION_RAW_CHUNK_BYTES;
        char line[600];
        const int prefix = snprintf(line, sizeof(line),
            "glueyneo: continuation %c %" PRIu64 " %zu ",
            kind, frame, offset);
        if (prefix <= 0 || (size_t)prefix + chunk * 2u + 2u > sizeof(line)) {
            continuation_incomplete();
            return;
        }
        size_t cursor = (size_t)prefix;
        for (size_t index = 0u; index < chunk; ++index) {
            const uint8_t value = bytes[offset + index];
            line[cursor++] = digits[value >> 4];
            line[cursor++] = digits[value & 15u];
        }
        line[cursor++] = '\n';
        line[cursor] = '\0';
        continuation_log_line(line);
        offset += chunk;
    }
}

static void continuation_note_frame(uint32_t input_mask,
                                    const uint8_t *pixels,
                                    size_t pixel_bytes,
                                    const int16_t *audio,
                                    size_t audio_frames) {
    if (!continuation_observation.active) return;
    if (continuation_observation.executed_cycles <=
            continuation_observation.restore_cycles ||
        continuation_observation.frames_in_window >=
            GN_CONTINUATION_WINDOW_FRAMES ||
        input_mask > UINT32_C(0x3ff)) {
        continuation_incomplete();
        return;
    }
    const uint64_t frame = continuation_observation.frames_in_window;
    const uint64_t cycle_delta = continuation_observation.executed_cycles -
        continuation_observation.restore_cycles;
    char line[160];
    const int length = snprintf(line, sizeof(line),
        "glueyneo: continuation F %" PRIu64 " %" PRIu32 " %" PRIu64
        " %zu\n", frame, input_mask, cycle_delta, audio_frames);
    if (length <= 0 || (size_t)length >= sizeof(line)) {
        continuation_incomplete();
        return;
    }
    continuation_log_line(line);
    continuation_note_raw('V', frame, pixels, pixel_bytes);
    continuation_note_raw('A', frame, (const uint8_t *)audio,
                          audio_frames * 2u * sizeof(int16_t));
    if (!continuation_observation.active) return;
    ++continuation_observation.frames_in_window;
    if (continuation_observation.frames_in_window ==
            GN_CONTINUATION_WINDOW_FRAMES) {
        const int complete_length = snprintf(line, sizeof(line),
            "glueyneo: continuation E %u\n",
            continuation_observation.frames_in_window);
        if (complete_length > 0 && (size_t)complete_length < sizeof(line))
            continuation_log_line(line);
        continuation_observation.active = false;
    }
}
#endif

#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
/* Local frontend evidence only. The host owns the invocation/log binding.
 * No host clock, guest bytes, paths or addresses enter these fixed records. */
static struct {
    uint64_t sample_sequence;
    uint64_t successful_video_sequence;
    uint64_t executed_cycles;
    uint32_t sampled_mask;
    unsigned records;
    unsigned frames_since_change;
    bool begun;
    bool sampled;
    bool pending_video;
    bool attract_ready;
    bool player_start;
    bool exhausted;
} mvs_observations;

static void reset_mvs_observations(void) {
    memset(&mvs_observations, 0, sizeof(mvs_observations));
}

static void emit_mvs_observation(char kind, uint64_t cycles) {
    if (log_cb == NULL || mvs_observations.exhausted) return;
    /* Reserve the final slot for an explicit incomplete-evidence marker. */
    if (mvs_observations.records == 255u) {
        kind = 'X';
        cycles = mvs_observations.executed_cycles;
        mvs_observations.exhausted = true;
    }
    ++mvs_observations.records;
    log_cb(RETRO_LOG_INFO, "glueyneo: mvs %c %" PRIu64 " %" PRIu32
           " %" PRIu64 " %" PRIu64 "\n", kind,
           mvs_observations.sample_sequence, mvs_observations.sampled_mask,
           mvs_observations.successful_video_sequence, cycles);
}

static void note_mvs_sample(uint32_t mask) {
    if (mvs_observations.sample_sequence != UINT64_MAX)
        ++mvs_observations.sample_sequence;
    if (!mvs_observations.sampled || mask != mvs_observations.sampled_mask) {
        mvs_observations.sampled = true;
        mvs_observations.sampled_mask = mask;
        mvs_observations.pending_video = true;
        mvs_observations.frames_since_change = 0u;
        emit_mvs_observation('S', mvs_observations.executed_cycles);
    }
}

static void note_mvs_successful_video(bool observation_burst_requested) {
    gn_mvs_attract_verdict verdict;
    gn_mvs_progress_observation progress;
    const bool ready = !mvs_observations.attract_ready &&
        gn_private_mvs_attract_verdict(instance, &verdict) == GN_STATUS_OK &&
        verdict.accepted != 0u;
    const bool started = !mvs_observations.player_start &&
        gn_observe_mvs_progress(instance, &progress, sizeof(progress)) == GN_STATUS_OK &&
        progress.player_start_with_p1_indication != 0u;
    if (mvs_observations.successful_video_sequence != UINT64_MAX)
        ++mvs_observations.successful_video_sequence;
    /* Keep ordinary transition context short to reserve the fixed log budget
     * for denser requested capture intervals. Neither changes guest time. */
    if (mvs_observations.frames_since_change < 9u)
        ++mvs_observations.frames_since_change;
    if (mvs_observations.pending_video || ready || started ||
        (observation_burst_requested &&
         mvs_observations.successful_video_sequence % 2u == 0u) ||
        (mvs_observations.frames_since_change <= 8u &&
         mvs_observations.frames_since_change % 4u == 0u) ||
        mvs_observations.successful_video_sequence % 32u == 0u) {
        emit_mvs_observation('V', mvs_observations.executed_cycles);
        mvs_observations.pending_video = false;
    }
    if (ready) {
        emit_mvs_observation('R', mvs_observations.executed_cycles);
        mvs_observations.attract_ready = true;
    }
    if (started) {
        emit_mvs_observation('P', mvs_observations.executed_cycles);
        mvs_observations.player_start = true;
    }
}

#endif

/* RetroPad Classic mapping; descriptions name the emulated Neo Geo lines. */
static const struct retro_input_descriptor mvs_input_descriptors[] = {
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_UP, "P1 Up"},
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_DOWN, "P1 Down"},
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_LEFT, "P1 Left"},
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_RIGHT, "P1 Right"},
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_B, "P1 Button A"},
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_A, "P1 Button B"},
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_Y, "P1 Button C"},
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_X, "P1 Button D"},
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_SELECT, "Coin1"},
    {0u, RETRO_DEVICE_JOYPAD, 0u, RETRO_DEVICE_ID_JOYPAD_START, "P1 Start"},
    {0u, 0u, 0u, 0u, NULL}
};

static bool retro_joypad_pressed(unsigned id) {
    return input_state_cb(0u, RETRO_DEVICE_JOYPAD, 0u, id) != 0;
}

static void submit_blank_video_frame(void) {
    memset(pixels, 0, sizeof(pixels));
    video_cb(pixels, GN_FRAME_WIDTH, GN_FRAME_HEIGHT, GN_FRAME_PITCH);
}

static uint32_t read_u32_be(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

/* One bounded generic line per GNMV load outcome. Messages are fixed strings:
 * no path, region value, size or digest from the supplied content is logged. */
static void log_mvs_outcome(enum retro_log_level level, const char *message) {
    if (log_cb != NULL) log_cb(level, "%s\n", message);
}

static uint64_t add_bounded_audio_count(uint64_t current, size_t amount) {
    const uintmax_t increment = (uintmax_t)amount;
    if (increment > (uintmax_t)(UINT64_MAX - current)) return UINT64_MAX;
    return current + (uint64_t)increment;
}

static void reset_mvs_audio_delivery_state(void) {
    mvs_audio_frames_generated = 0u;
    mvs_audio_frames_submitted = 0u;
    mvs_audio_frames_processed = 0u;
    mvs_audio_frames_discarded = 0u;
    mvs_audio_overreported_callbacks = 0u;
    mvs_audio_drop_warning_logged = false;
    mvs_audio_overreport_warning_logged = false;
}

static void log_mvs_audio_delivery(enum retro_log_level level, const char *message) {
    if (log_cb == NULL) return;
    log_cb(level,
           "glueyneo: %s: generated=%" PRIu64 " submitted=%" PRIu64
           " processed=%" PRIu64 " discarded=%" PRIu64
           " overreports=%" PRIu64 "\n",
           message, mvs_audio_frames_generated, mvs_audio_frames_submitted,
           mvs_audio_frames_processed, mvs_audio_frames_discarded,
           mvs_audio_overreported_callbacks);
}

#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
/* Private local evidence: one row per completed frame, no guest/sample bytes.
 * The normal adapter build has no observer calls or per-frame log cost. */
static void log_mvs_audio_frame(const gn_mvs_frame_result_v1 *result,
                                const gn_mvs_sound_observation *before,
                                uint32_t watchdog_before, bool before_valid) {
    if (log_cb == NULL || mvs_observations.sample_sequence > 8192u) return;
    gn_mvs_sound_observation after;
    gn_mvs_bus_fault_observation bus_after;
    if (!before_valid || gn_private_mvs_sound_observe(instance, &after) != GN_STATUS_OK ||
            gn_observe_mvs_bus_fault(instance, &bus_after, sizeof(bus_after)) != GN_STATUS_OK) {
        log_mvs_outcome(RETRO_LOG_WARN, "glueyneo: MVS audio frame unavailable");
        return;
    }
#define AUDIO_CHIP_VALUES(chip) \
    (chip).clocks, (chip).fm_key_on_writes, (chip).fm_key_off_writes, \
    (chip).fm_register_writes, (chip).ssg_register_writes, (chip).ssg_volume_writes, \
    (chip).adpcm_a_register_writes, (chip).adpcm_a_control_writes, \
    (chip).adpcm_a_sample_reads, (chip).adpcm_b_register_writes, \
    (chip).adpcm_b_control_writes, (chip).adpcm_b_sample_reads, (chip).native_nonzero_frames
    const uint64_t earlier[] = {AUDIO_CHIP_VALUES(before->chip)};
    const uint64_t later[] = {AUDIO_CHIP_VALUES(after.chip)};
#undef AUDIO_CHIP_VALUES
    uint64_t delta[13];
    uint64_t reset = bus_after.mame_watchdog_reset_count != watchdog_before ? 1u : 0u;
    for (size_t index = 0u; index < 13u; ++index) {
        if (later[index] < earlier[index]) {
            reset = 1u;
            delta[index] = 0u;
        } else {
            delta[index] = later[index] - earlier[index];
        }
    }
    log_cb(RETRO_LOG_INFO,
        "glueyneo: MVS audio frame: %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64
        " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64
        " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64
        " %" PRIu64 " %" PRIu64 "\n",
        mvs_observations.sample_sequence, (uint64_t)mvs_observations.sampled_mask,
        result->elapsed_cycles, (uint64_t)result->audio_frames_generated, reset,
        delta[0], delta[1], delta[2], delta[3], delta[4], delta[5], delta[6],
        delta[7], delta[8], delta[9], delta[10], delta[11], delta[12]);
}
#endif

static void account_mvs_audio_batch(size_t submitted, size_t reported) {
    mvs_audio_frames_submitted = add_bounded_audio_count(
        mvs_audio_frames_submitted, submitted);
    const bool overreported = reported > submitted;
    if (overreported) {
        reported = submitted;
        mvs_audio_overreported_callbacks = add_bounded_audio_count(
            mvs_audio_overreported_callbacks, 1u);
    }
    mvs_audio_frames_processed = add_bounded_audio_count(
        mvs_audio_frames_processed, reported);
    const size_t discarded = submitted - reported;
    mvs_audio_frames_discarded = add_bounded_audio_count(
        mvs_audio_frames_discarded, discarded);
    if (overreported && !mvs_audio_overreport_warning_logged) {
        log_mvs_audio_delivery(RETRO_LOG_WARN,
            "MVS audio callback count exceeded submitted frames");
        mvs_audio_overreport_warning_logged = true;
    }
    if (discarded > 0u && !mvs_audio_drop_warning_logged) {
        log_mvs_audio_delivery(RETRO_LOG_WARN, "MVS audio callback left PCM unprocessed");
        mvs_audio_drop_warning_logged = true;
    }
}

static void log_mvs_runtime_failure(const char *message) {
    if (mvs_runtime_failure_logged) return;
    log_mvs_outcome(RETRO_LOG_ERROR, message);
    mvs_runtime_failure_logged = true;
}

static bool reject_mvs(const char *message) {
    log_mvs_outcome(RETRO_LOG_ERROR, message);
    return false;
}

static void unload_instance(void) {
#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
    continuation_incomplete();
    continuation_save_ram_data_logged = false;
    continuation_save_ram_size_logged = false;
#endif
    if (instance != NULL) {
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
        if (instance_is_mvs)
            log_mvs_audio_delivery(RETRO_LOG_INFO, "MVS audio final delivery");
#endif
        (void)gn_unload(instance);
        gn_destroy(instance);
        instance = NULL;
    }
    instance_is_mvs = false;
    av_timing_update_pending = false;
    mvs_start_indication_logged = false;
    mvs_runtime_failure_logged = false;
    mvs_video_frames = 0u;
    mvs_audio_capacity_frames = 0u;
    mvs_state_capacity = 0u;
    reset_mvs_audio_delivery_state();
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
    reset_mvs_observations();
#endif
}

unsigned retro_api_version(void) { return RETRO_API_VERSION; }

void retro_set_environment(retro_environment_t callback) {
    environment_cb = callback;
}

void retro_set_video_refresh(retro_video_refresh_t callback) {
    video_cb = callback;
}

void retro_set_audio_sample(retro_audio_sample_t callback) {
    audio_cb = callback;
}

void retro_set_audio_sample_batch(retro_audio_sample_batch_t callback) {
    audio_batch_cb = callback;
}

void retro_set_input_poll(retro_input_poll_t callback) {
    input_poll_cb = callback;
}

void retro_set_input_state(retro_input_state_t callback) {
    input_state_cb = callback;
}

void retro_init(void) {
    struct retro_log_callback logging;
    log_cb = NULL;
    memset(&logging, 0, sizeof(logging));
    /* Acquire runtime interfaces once per initialization. RetroArch also calls
     * retro_set_environment while probing metadata with requests disabled.
     * Those probes must not discard the live logger. Logging is optional. */
    if (environment_cb != NULL &&
        environment_cb(RETRO_ENVIRONMENT_GET_LOG_INTERFACE, &logging) &&
        logging.log != NULL) {
        log_cb = logging.log;
    }
}

void retro_deinit(void) {
    unload_instance();
    environment_cb = NULL;
    log_cb = NULL;
    video_cb = NULL;
    audio_cb = NULL;
    audio_batch_cb = NULL;
    input_poll_cb = NULL;
    input_state_cb = NULL;
}

void retro_get_system_info(struct retro_system_info *info) {
    if (info == NULL) return;
    info->library_name = "Glueyneo";
    info->library_version = "0.1";
    info->valid_extensions = "bin|gnmv";
    info->need_fullpath = false;
    info->block_extract = false;
}

static double content_frame_rate(void) {
    return instance_is_mvs ? 12000000.0 / (double)GN_MVS_FRAME_BUDGET_CYCLES : 60.0;
}

void retro_get_system_av_info(struct retro_system_av_info *info) {
    if (info == NULL) return;
    info->geometry.base_width = GN_FRAME_WIDTH;
    info->geometry.base_height = GN_FRAME_HEIGHT;
    info->geometry.max_width = GN_FRAME_WIDTH;
    info->geometry.max_height = GN_FRAME_HEIGHT;
    info->geometry.aspect_ratio = (float)GN_FRAME_WIDTH / (float)GN_FRAME_HEIGHT;
    info->timing.fps = content_frame_rate();
    info->timing.sample_rate = 48000.0;
}

void retro_set_controller_port_device(unsigned port, unsigned device) {
    (void)port;
    (void)device;
}

void retro_reset(void) {
    if (instance != NULL && gn_reset(instance) == GN_STATUS_OK) {
#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
        continuation_incomplete();
#endif
        mvs_video_frames = 0u;
        if (instance_is_mvs) reset_mvs_audio_delivery_state();
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
        reset_mvs_observations();
#endif
    }
}

bool retro_load_game(const struct retro_game_info *game) {
    if (instance != NULL || game == NULL || game->data == NULL ||
        environment_cb == NULL) {
        return false;
    }

    const uint8_t *content = (const uint8_t *)game->data;
    if (game->size >= 16u && memcmp(content, "GNMV", 4u) == 0) {
        const uint32_t version = read_u32_be(content + 4u);
        const uint32_t profile = read_u32_be(content + 8u);
        const uint32_t count = read_u32_be(content + 12u);
        const int is_v3 = version == GN_MVS_MANIFEST_VERSION_ZOOM;
        if (profile != GN_MVS_PROFILE_MSX ||
            !((version == GN_MVS_MANIFEST_VERSION_LEGACY &&
               count == GN_MVS_LEGACY_REGIONS) ||
              (version == GN_MVS_MANIFEST_VERSION &&
               count == GN_MVS_MAX_REGIONS) ||
              (is_v3 && (count == GN_MVS_V3_MAX_REGIONS - 1u ||
                         count == GN_MVS_V3_MAX_REGIONS))) ||
            game->size > GN_MVS_MAX_MEDIA_BYTES + 16u +
                         GN_MVS_V3_MAX_REGIONS * 12u)
            return reject_mvs("glueyneo: MVS bundle rejected: unsupported profile");
        gn_mvs_manifest manifest;
        gn_mvs_manifest_v3 manifest_v3;
        memset(&manifest, 0, sizeof(manifest));
        memset(&manifest_v3, 0, sizeof(manifest_v3));
        gn_mvs_region *regions = is_v3 ? manifest_v3.regions : manifest.regions;
        if (is_v3) {
            manifest_v3.version = version;
            manifest_v3.profile = profile;
            manifest_v3.region_count = count;
        } else {
            manifest.version = version;
            manifest.profile = profile;
            manifest.region_count = count;
        }
        size_t cursor = 16u;
        for (size_t index = 0u; index < count; ++index) {
            if (cursor > game->size || game->size - cursor < 12u)
                return reject_mvs("glueyneo: MVS bundle rejected: malformed");
            const uint32_t role = read_u32_be(content + cursor);
            const uint32_t high = read_u32_be(content + cursor + 4u);
            const uint32_t low = read_u32_be(content + cursor + 8u);
            if (high != 0u)
                return reject_mvs("glueyneo: MVS bundle rejected: malformed");
            const size_t region_size = (size_t)low;
            cursor += 12u;
            if (region_size == 0u || region_size > game->size - cursor)
                return reject_mvs("glueyneo: MVS bundle rejected: malformed");
            regions[index] = (gn_mvs_region){
                (gn_mvs_region_role)role, content + cursor, region_size,
                region_size, GN_MVS_LAYOUT_LINEAR};
            cursor += region_size;
        }
        if (cursor != game->size)
            return reject_mvs("glueyneo: MVS bundle rejected: malformed");
        if (version == GN_MVS_MANIFEST_VERSION_LEGACY)
            return reject_mvs("glueyneo: MVS bundle rejected: missing audio BIOS");
        enum retro_pixel_format pixel_format = RETRO_PIXEL_FORMAT_XRGB8888;
        /* A frontend that cannot supply XRGB8888 rejects the load before the
         * native core is touched. */
        if (!environment_cb(RETRO_ENVIRONMENT_SET_PIXEL_FORMAT, &pixel_format))
            return reject_mvs("glueyneo: MVS bundle rejected: native load rejected");
        if (gn_create(&instance) != GN_STATUS_OK) {
            instance = NULL;
            return reject_mvs("glueyneo: MVS bundle rejected: allocation failed");
        }
        const gn_status loaded = is_v3
            ? gn_load_mvs_v3(instance, &manifest_v3)
            : gn_load_mvs(instance, &manifest);
        if (loaded != GN_STATUS_OK) {
            unload_instance();
            return reject_mvs(loaded == GN_STATUS_OUT_OF_MEMORY
                ? "glueyneo: MVS bundle rejected: allocation failed"
                : "glueyneo: MVS bundle rejected: native load rejected");
        }
        size_t audio_capacity_frames = 0u;
        if (gn_mvs_audio_capacity_v1(instance, &audio_capacity_frames) !=
                GN_STATUS_OK ||
            audio_capacity_frames == 0u ||
            audio_capacity_frames > GN_MVS_AUDIO_MAX_FRAMES ||
            audio_capacity_frames >
                SIZE_MAX / (sizeof(int16_t) * (size_t)2u)) {
            unload_instance();
            return reject_mvs(
                "glueyneo: MVS bundle rejected: audio capacity unavailable");
        }
        size_t state_capacity = 0u;
        if (gn_state_capacity_v1(instance, &state_capacity) != GN_STATUS_OK ||
            state_capacity == 0u) {
            unload_instance();
            return reject_mvs(
                "glueyneo: MVS bundle rejected: state capacity unavailable");
        }
        uint8_t *save_ram = NULL;
        size_t save_ram_size = 0u;
        if (gn_private_mvs_save_ram_view(instance, &save_ram, &save_ram_size) !=
                GN_STATUS_OK ||
            save_ram == NULL || save_ram_size == 0u) {
            unload_instance();
            return reject_mvs(
                "glueyneo: MVS bundle rejected: save RAM unavailable");
        }
        mvs_audio_capacity_frames = audio_capacity_frames;
        mvs_state_capacity = state_capacity;
        instance_is_mvs = true;
        av_timing_update_pending = true;
        (void)environment_cb(RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS,
                             (void *)mvs_input_descriptors);
        mvs_start_indication_logged = false;
        mvs_runtime_failure_logged = false;
        log_mvs_outcome(RETRO_LOG_INFO, "glueyneo: MVS bundle loaded");
        return true;
    }
    if (game->size != (size_t)GNFX_CONTENT_SIZE) return false;
    if (memcmp(content, "GNFX", 4u) != 0 || read_u32_be(content + 4u) != 1u ||
        read_u32_be(content + 8u) != GNFX_PAYLOAD_SIZE ||
        read_u32_be(content + 12u) != GNFX_HEADER_SIZE) {
        return false;
    }

    enum retro_pixel_format pixel_format = RETRO_PIXEL_FORMAT_XRGB8888;
    if (!environment_cb(RETRO_ENVIRONMENT_SET_PIXEL_FORMAT, &pixel_format)) {
        return false;
    }

    gn_manifest manifest;
    memset(&manifest, 0, sizeof(manifest));
    manifest.version = GN_MANIFEST_VERSION;
    manifest.profile = GN_PROFILE_PUBLIC_FIXTURE;
    manifest.region_count = 1u;
    manifest.regions[0] = (gn_region){
        0u, GNFX_CONTENT_SIZE, content, game->size, GN_REGION_ROM};

    if (gn_create(&instance) != GN_STATUS_OK) {
        instance = NULL;
        return false;
    }
    if (gn_load(instance, &manifest) != GN_STATUS_OK) {
        unload_instance();
        return false;
    }
    instance_is_mvs = false;
    mvs_state_capacity = 0u;
    av_timing_update_pending = true;
    mvs_start_indication_logged = false;
    mvs_runtime_failure_logged = false;
    return true;
}

bool retro_load_game_special(unsigned game_type,
                             const struct retro_game_info *info,
                             size_t num_info) {
    (void)game_type;
    (void)info;
    (void)num_info;
    return false;
}

void retro_unload_game(void) { unload_instance(); }

void retro_run(void) {
    if (instance == NULL || input_poll_cb == NULL || input_state_cb == NULL ||
        video_cb == NULL) {
        return;
    }

    /* Pinned libretro.h permits AV updates only inside retro_run. The query
     * already reflects loaded content; explicitly announce each load once.
     * Unsupported updates leave metadata queryable and emit one fixed warning. */
    if (av_timing_update_pending) {
        struct retro_system_av_info av;
        retro_get_system_av_info(&av);
        av_timing_update_pending = false;
        if (environment_cb == NULL ||
            !environment_cb(RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO, &av))
            log_mvs_outcome(RETRO_LOG_WARN, "glueyneo: AV timing update unsupported");
    }
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
    if (instance_is_mvs && !mvs_observations.begun) {
        emit_mvs_observation('B', 0u);
        mvs_observations.begun = true;
    }
#endif
    input_poll_cb();
    if (instance_is_mvs) {
        uint32_t input_mask = 0u;
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_SELECT)) {
            input_mask |= GN_MVS_INPUT_COIN1;
        }
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_START)) {
            input_mask |= GN_MVS_INPUT_P1_START;
        }
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_UP))
            input_mask |= GN_MVS_INPUT_P1_UP;
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_DOWN))
            input_mask |= GN_MVS_INPUT_P1_DOWN;
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_LEFT))
            input_mask |= GN_MVS_INPUT_P1_LEFT;
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_RIGHT))
            input_mask |= GN_MVS_INPUT_P1_RIGHT;
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_B))
            input_mask |= GN_MVS_INPUT_P1_A;
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_A))
            input_mask |= GN_MVS_INPUT_P1_B;
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_Y))
            input_mask |= GN_MVS_INPUT_P1_C;
        if (retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_X))
            input_mask |= GN_MVS_INPUT_P1_D;
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
        /* L3 requests denser host observations only in this opt-in build.
         * It never enters the complete emulated Neo Geo input mask. */
        const bool observation_burst_requested =
            retro_joypad_pressed(RETRO_DEVICE_ID_JOYPAD_L3);
        note_mvs_sample(input_mask);
#endif
        const gn_mvs_frame_request_v1 request = {
            GN_MVS_FRAME_REQUEST_V1_VERSION, input_mask, GN_PIXEL_XRGB8888,
            GN_FRAME_WIDTH, GN_FRAME_HEIGHT, GN_FRAME_PITCH,
            (uint8_t *)pixels, sizeof(pixels), mvs_audio_samples,
            mvs_audio_capacity_frames
        };
        gn_mvs_frame_result_v1 result;
        memset(&result, 0, sizeof(result));
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
        gn_mvs_sound_observation audio_chip_before;
        gn_mvs_bus_fault_observation audio_bus_before = {0};
        const bool audio_chip_before_valid =
            gn_private_mvs_sound_observe(instance, &audio_chip_before) == GN_STATUS_OK &&
            gn_observe_mvs_bus_fault(instance, &audio_bus_before, sizeof(audio_bus_before)) == GN_STATUS_OK;
#endif
        const gn_status frame_status = gn_mvs_advance_frame_v1(
            instance, &request, sizeof(request), &result, sizeof(result));
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
        /* Preserve actual executed clocks, including any failed run prefix.
         * Saturation is defined even for a host that runs indefinitely. */
        if (UINT64_MAX - mvs_observations.executed_cycles < result.elapsed_cycles)
            mvs_observations.executed_cycles = UINT64_MAX;
        else
            mvs_observations.executed_cycles += result.elapsed_cycles;
#endif
        if (frame_status != GN_STATUS_OK || result.reason == GN_RUN_ERROR ||
            result.reason == GN_RUN_FAULT ||
            result.audio_frames_delivered > mvs_audio_capacity_frames ||
            result.audio_frames_generated != result.audio_frames_delivered ||
            result.video_pixels_produced != GN_FRAME_WIDTH * GN_FRAME_HEIGHT) {
            const char *failure_message =
                result.reason == GN_RUN_FAULT
                    ? "glueyneo: MVS guest run fault"
                    : frame_status != GN_STATUS_OK &&
                      result.version == GN_MVS_FRAME_RESULT_V1_VERSION &&
                      result.reason == GN_RUN_STOPPED &&
                      result.video_pixels_produced == 0u
                        ? "glueyneo: MVS video rendering failed"
                        : frame_status != GN_STATUS_OK
                            ? "glueyneo: MVS frame advance failed"
                            : "glueyneo: MVS frame result exceeded its capacity";
#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
            continuation_incomplete();
#endif
            log_mvs_runtime_failure(failure_message);
            submit_blank_video_frame();
            return;
        }
#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
        if (UINT64_MAX - continuation_observation.executed_cycles <
                result.elapsed_cycles ||
            continuation_observation.completed_frames == UINT64_MAX) {
            continuation_incomplete();
        } else {
            continuation_observation.executed_cycles += result.elapsed_cycles;
            ++continuation_observation.completed_frames;
        }
#endif
        video_cb(pixels, GN_FRAME_WIDTH, GN_FRAME_HEIGHT, GN_FRAME_PITCH);
        if (result.audio_frames_delivered > 0u) {
            mvs_audio_frames_generated = add_bounded_audio_count(
                mvs_audio_frames_generated, result.audio_frames_generated);
            if (audio_batch_cb != NULL) {
                const size_t reported = audio_batch_cb(
                    mvs_audio_samples, result.audio_frames_delivered);
                account_mvs_audio_batch(result.audio_frames_delivered,
                                        reported);
            } else if (audio_cb != NULL) {
                for (size_t frame = 0u;
                     frame < result.audio_frames_delivered; ++frame) {
                    audio_cb(mvs_audio_samples[frame * 2u],
                             mvs_audio_samples[frame * 2u + 1u]);
                }
                mvs_audio_frames_submitted = add_bounded_audio_count(
                    mvs_audio_frames_submitted,
                    result.audio_frames_delivered);
                mvs_audio_frames_processed = add_bounded_audio_count(
                    mvs_audio_frames_processed,
                    result.audio_frames_delivered);
            } else {
                mvs_audio_frames_discarded = add_bounded_audio_count(
                    mvs_audio_frames_discarded,
                    result.audio_frames_delivered);
            }
        }
#ifdef GLUEYNEO_MVS_INPUT_OBSERVATIONS
        log_mvs_audio_frame(&result, &audio_chip_before,
                            audio_bus_before.mame_watchdog_reset_count, audio_chip_before_valid);
        note_mvs_successful_video(observation_burst_requested);
#endif
#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
        continuation_note_frame(input_mask, (const uint8_t *)pixels,
                                sizeof(pixels), mvs_audio_samples,
                                result.audio_frames_delivered);
#endif
        /* A bounded diagnostic checkpoint, not a title/compatibility claim.
         * The frontend smoke uses this lower bound instead of host sleeps. */
        if (mvs_video_frames < 720u && ++mvs_video_frames % 120u == 0u) {
            static const char *const checkpoints[] = {
                "glueyneo: MVS video checkpoint: 120 frames",
                "glueyneo: MVS video checkpoint: 240 frames",
                "glueyneo: MVS video checkpoint: 360 frames",
                "glueyneo: MVS video checkpoint: 480 frames",
                "glueyneo: MVS video checkpoint: 600 frames",
                "glueyneo: MVS video checkpoint: 720 frames"};
            log_mvs_outcome(RETRO_LOG_INFO,
                checkpoints[mvs_video_frames / 120u - 1u]);
        }
        gn_mvs_progress_observation progress;
        if (gn_observe_mvs_progress(instance, &progress, sizeof(progress)) ==
                GN_STATUS_OK &&
            progress.player_start_with_p1_indication != 0u &&
            !mvs_start_indication_logged) {
            log_mvs_outcome(RETRO_LOG_INFO,
                            "glueyneo: MVS P1 start indication observed");
            mvs_start_indication_logged = true;
        }
        return;
    }

    uint32_t input_mask = 0u;
    if (input_state_cb(0u, RETRO_DEVICE_JOYPAD, 0u,
                       RETRO_DEVICE_ID_JOYPAD_RIGHT) != 0) {
        input_mask |= GN_INPUT_RIGHT;
    }

    const gn_frame_request request = {
        input_mask, GN_PIXEL_XRGB8888, GN_FRAME_WIDTH, GN_FRAME_HEIGHT,
        GN_FRAME_PITCH, (uint8_t *)pixels, GN_FRAME_BYTES, audio_samples,
        GN_AUDIO_MAX_FRAMES};
    gn_frame_result result;
    if (gn_advance_frame(instance, &request, &result) != GN_STATUS_OK ||
        result.reason != GN_RUN_STOPPED ||
        result.video_pixels_produced != GN_FRAME_WIDTH * GN_FRAME_HEIGHT) {
        submit_blank_video_frame();
        return;
    }

    video_cb(pixels, GN_FRAME_WIDTH, GN_FRAME_HEIGHT, GN_FRAME_PITCH);
    if (result.audio_frames_produced > 0u) {
        if (audio_batch_cb != NULL) {
            (void)audio_batch_cb(audio_samples, result.audio_frames_produced);
        } else if (audio_cb != NULL) {
            for (size_t frame = 0u; frame < result.audio_frames_produced; ++frame) {
                audio_cb(audio_samples[frame * 2u], audio_samples[frame * 2u + 1u]);
            }
        }
    }
}

size_t retro_serialize_size(void) {
    return instance != NULL && instance_is_mvs ? mvs_state_capacity : 0u;
}

bool retro_serialize(void *data, size_t len) {
    const size_t capacity = retro_serialize_size();
    if (capacity == 0u || data == NULL || len < capacity) return false;

    size_t written = 0u;
    const bool captured =
        gn_state_capture_v1(instance, data, len, &written, NULL, 0u) ==
            GN_STATUS_OK && written == capacity;
#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
    if (captured) continuation_note_capture(capacity);
#endif
    return captured;
}

bool retro_unserialize(const void *data, size_t len) {
    const size_t capacity = retro_serialize_size();
    if (capacity == 0u || data == NULL || len != capacity) return false;
    const bool restored =
        gn_state_restore_v1(instance, data, len, NULL, 0u) == GN_STATUS_OK;
#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
    if (restored) continuation_note_restore(capacity, (const uint8_t *)data);
#endif
    return restored;
}

unsigned retro_get_region(void) { return RETRO_REGION_NTSC; }

void *retro_get_memory_data(unsigned id) {
    if (id == RETRO_MEMORY_SAVE_RAM && instance != NULL && instance_is_mvs) {
        uint8_t *bytes = NULL;
        size_t size = 0u;
        if (gn_private_mvs_save_ram_view(instance, &bytes, &size) ==
                GN_STATUS_OK &&
            bytes != NULL && size != 0u) {
#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
            if (!continuation_save_ram_data_logged && log_cb != NULL) {
                log_cb(RETRO_LOG_INFO,
                       "glueyneo: frontend queried MVS SAVE_RAM data\n");
                continuation_save_ram_data_logged = true;
            }
#endif
            return bytes;
        }
    }
    return NULL;
}

size_t retro_get_memory_size(unsigned id) {
    if (id == RETRO_MEMORY_SAVE_RAM && instance != NULL && instance_is_mvs) {
        uint8_t *bytes = NULL;
        size_t size = 0u;
        if (gn_private_mvs_save_ram_view(instance, &bytes, &size) ==
                GN_STATUS_OK) {
#ifdef GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
            if (!continuation_save_ram_size_logged && log_cb != NULL) {
                log_cb(RETRO_LOG_INFO,
                       "glueyneo: frontend queried MVS SAVE_RAM size: %zu bytes\n",
                       size);
                continuation_save_ram_size_logged = true;
            }
#endif
            return size;
        }
    }
    return 0u;
}

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
gn_instance *gn_test_libretro_instance(void) {
    return instance_is_mvs ? instance : NULL;
}
#endif

void retro_cheat_reset(void) {}

void retro_cheat_set(unsigned index, bool enabled, const char *code) {
    (void)index;
    (void)enabled;
    (void)code;
}
