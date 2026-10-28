// SPDX-License-Identifier: MIT; original public-fixture installed C++ consumer.
#include "glueyneo/glueyneo.h"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <memory>
#include <string>
#include <vector>

namespace {

constexpr size_t kWidth = 320;
constexpr size_t kHeight = 224;
constexpr size_t kRegionCount = 8;
constexpr size_t kHeaderBytes = 16;
constexpr size_t kDescriptorBytes = 12;
constexpr size_t kPixelCount = kWidth * kHeight;
constexpr size_t kPixelBytes = kPixelCount * sizeof(uint32_t);
constexpr size_t kBundleLimit = GN_MVS_MAX_MEDIA_BYTES + kHeaderBytes +
                                kRegionCount * kDescriptorBytes;

#define CHECK(condition)                                                     \
    do {                                                                      \
        ++assertions;                                                         \
        if (!(condition)) {                                                   \
            std::fprintf(stderr, "C++ runtime consumer assertion failed: %s\n", \
                         #condition);                                         \
            return false;                                                     \
        }                                                                     \
    } while (false)

uint32_t read_be32(const uint8_t *bytes) {
    return (static_cast<uint32_t>(bytes[0]) << 24) |
           (static_cast<uint32_t>(bytes[1]) << 16) |
           (static_cast<uint32_t>(bytes[2]) << 8) |
           static_cast<uint32_t>(bytes[3]);
}

bool write_le(std::ofstream &stream, uint64_t value, size_t width) {
    for (size_t i = 0; i < width; ++i) {
        stream.put(static_cast<char>(value & UINT64_C(0xff)));
        if (!stream) return false;
        value >>= 8;
    }
    return true;
}

bool write_frame(std::ofstream &stream,
                 const gn_mvs_frame_result_v1 &result,
                 const std::vector<uint32_t> &pixels,
                 const std::vector<int16_t> &audio) {
    if (!write_le(stream, result.audio_frames_delivered, 4) ||
        !write_le(stream, result.elapsed_cycles, 8)) return false;
    for (uint32_t pixel : pixels)
        if (!write_le(stream, pixel, 4)) return false;
    const size_t samples = result.audio_frames_delivered * 2;
    if (samples > audio.size()) return false;
    for (size_t i = 0; i < samples; ++i)
        if (!write_le(stream, static_cast<uint16_t>(audio[i]), 2)) return false;
    return true;
}

struct InstanceDeleter {
    void operator()(gn_instance *instance) const { gn_destroy(instance); }
};

bool tone_present(const std::vector<int16_t> &audio, size_t frames) {
    if (frames < 800 || frames * 2 > audio.size()) return false;
    int64_t best = 0;
    for (size_t phase = 0; phase < 48; ++phase) {
        int64_t correlation = 0;
        for (size_t i = 32; i < 800; ++i) {
            if (audio[2 * i] != audio[2 * i + 1]) return false;
            correlation += static_cast<int64_t>(audio[2 * i]) *
                (((i + phase) % 48 < 24) ? 1 : -1);
        }
        if (correlation < 0) correlation = -correlation;
        best = std::max(best, correlation);
    }
    return best / 768 >= 256;
}

bool run_consumer(const char *bundle_path, const char *trace_path,
                  int &assertions, size_t &generated_samples) {
    std::ifstream input(bundle_path, std::ios::binary);
    CHECK(input.good());
    input.seekg(0, std::ios::end);
    const std::streamoff file_size = input.tellg();
    CHECK(file_size >= static_cast<std::streamoff>(kHeaderBytes));
    CHECK(static_cast<uint64_t>(file_size) <= kBundleLimit);
    input.seekg(0, std::ios::beg);
    std::vector<uint8_t> bundle(static_cast<size_t>(file_size));
    input.read(reinterpret_cast<char *>(bundle.data()), file_size);
    CHECK(input.good() || input.eof());
    CHECK(static_cast<size_t>(input.gcount()) == bundle.size());
    CHECK(std::memcmp(bundle.data(), "GNMV", 4) == 0);
    CHECK(read_be32(bundle.data() + 4) == GN_MVS_MANIFEST_VERSION_ZOOM);
    CHECK(read_be32(bundle.data() + 8) == GN_MVS_PROFILE_MSX);
    CHECK(read_be32(bundle.data() + 12) == kRegionCount);

    gn_mvs_manifest_v3 manifest{};
    manifest.version = GN_MVS_MANIFEST_VERSION_ZOOM;
    manifest.profile = GN_MVS_PROFILE_MSX;
    manifest.region_count = kRegionCount;
    size_t at = kHeaderBytes;
    for (size_t i = 0; i < kRegionCount; ++i) {
        CHECK(at <= bundle.size());
        CHECK(bundle.size() - at >= kDescriptorBytes);
        const uint32_t role = read_be32(bundle.data() + at);
        const uint32_t high = read_be32(bundle.data() + at + 4);
        const uint32_t size = read_be32(bundle.data() + at + 8);
        at += kDescriptorBytes;
        CHECK(role == i + 1);
        CHECK(high == 0);
        CHECK(size != 0);
        CHECK(size <= bundle.size() - at);
        manifest.regions[i] = gn_mvs_region{
            static_cast<gn_mvs_region_role>(role), bundle.data() + at,
            size, size, GN_MVS_LAYOUT_LINEAR};
        at += size;
    }
    CHECK(at == bundle.size());

    gn_instance *created = nullptr;
    CHECK(gn_create(&created) == GN_STATUS_OK);
    CHECK(created != nullptr);
    std::unique_ptr<gn_instance, InstanceDeleter> instance(created);
    const gn_status load_status = gn_load_mvs_v3(instance.get(), &manifest);
    CHECK(load_status == GN_STATUS_OK);

    size_t capacity = 0;
    CHECK(gn_mvs_audio_capacity_v1(instance.get(), &capacity) == GN_STATUS_OK);
    CHECK(capacity == GN_MVS_AUDIO_CAPACITY_FRAMES_V1);
    std::vector<uint32_t> pixels(kPixelCount);
    std::vector<int16_t> audio(capacity * 2);
    std::vector<int16_t> neutral;
    std::vector<int16_t> fired;
    std::ofstream trace(trace_path, std::ios::binary | std::ios::trunc);
    CHECK(trace.good());

    const uint32_t masks[] = {0, 0, GN_MVS_INPUT_P1_A, 0};
    size_t neutral_frames = 0;
    size_t fired_frames = 0;
    for (size_t frame = 0; frame < 4; ++frame) {
        gn_mvs_frame_request_v1 request{
            GN_MVS_FRAME_REQUEST_V1_VERSION, masks[frame],
            GN_PIXEL_XRGB8888, kWidth, kHeight,
            kWidth * sizeof(uint32_t), reinterpret_cast<uint8_t *>(pixels.data()),
            kPixelBytes, audio.data(), capacity};
        gn_mvs_frame_result_v1 result{};
        CHECK(gn_mvs_advance_frame_v1(instance.get(), &request, sizeof(request),
                                      &result, sizeof(result)) == GN_STATUS_OK);
        CHECK(result.version == GN_MVS_FRAME_RESULT_V1_VERSION);
        CHECK(result.elapsed_cycles > 0);
        CHECK(result.audio_sample_rate == 48000);
        CHECK(result.audio_channels == 2);
        CHECK(result.audio_frames_generated >= 800);
        CHECK(result.audio_frames_generated <= capacity);
        CHECK(result.audio_frames_delivered == result.audio_frames_generated);
        CHECK(result.audio_frames_discarded == 0);
        CHECK(result.video_pixels_produced == kPixelCount);
        CHECK(pixels[0] == 0);
        CHECK(pixels[1] == UINT32_C(0x00ffffff));
        CHECK(write_frame(trace, result, pixels, audio));
        generated_samples += result.audio_frames_delivered;
        if (frame == 1) {
            CHECK(tone_present(audio, result.audio_frames_delivered));
            neutral_frames = result.audio_frames_delivered;
            neutral.assign(audio.begin(), audio.begin() + neutral_frames * 2);
        } else if (frame == 2) {
            CHECK(result.audio_frames_delivered == neutral_frames);
            CHECK(!std::equal(neutral.begin(), neutral.end(), audio.begin()));
            fired_frames = result.audio_frames_delivered;
            fired.assign(audio.begin(), audio.begin() + fired_frames * 2);
        } else if (frame == 3) {
            CHECK(result.audio_frames_delivered == fired_frames);
            CHECK(tone_present(audio, result.audio_frames_delivered));
            CHECK(!std::equal(fired.begin(), fired.end(), audio.begin()));
        }
    }
    trace.close();
    CHECK(trace.good());

    CHECK(gn_reset(instance.get()) == GN_STATUS_OK);
    for (size_t frame = 0; frame < 3; ++frame) {
        gn_mvs_frame_request_v1 request{
            GN_MVS_FRAME_REQUEST_V1_VERSION, 0, GN_PIXEL_XRGB8888,
            kWidth, kHeight, kWidth * sizeof(uint32_t),
            reinterpret_cast<uint8_t *>(pixels.data()), kPixelBytes,
            audio.data(), capacity};
        gn_mvs_frame_result_v1 result{};
        CHECK(gn_mvs_advance_frame_v1(instance.get(), &request, sizeof(request),
                                      &result, sizeof(result)) == GN_STATUS_OK);
        CHECK(result.audio_frames_delivered == neutral_frames);
        if (frame == 1)
            CHECK(std::equal(neutral.begin(), neutral.end(), audio.begin()));
        if (frame == 2)
            CHECK(!std::equal(fired.begin(), fired.end(), audio.begin()));
    }
    return true;
}

} // namespace

int main(int argc, char **argv) {
    if (argc != 4 || std::strcmp(argv[2], "--trace") != 0) {
        std::fprintf(stderr, "usage: %s PUBLIC_FIXTURE --trace TRACE\n", argv[0]);
        return 2;
    }
    int assertions = 0;
    size_t generated_samples = 0;
    if (!run_consumer(argv[1], argv[3], assertions, generated_samples))
        return 1;
    std::printf(
        "SDK_SANITIZER_CONSUMER {\"language\":\"C++17\",\"outcome\":\"pass\","
        "\"cases\":1,\"assertions\":%d,\"frames\":4,\"sample_frames\":%zu}\n",
        assertions, generated_samples);
    return 0;
}
