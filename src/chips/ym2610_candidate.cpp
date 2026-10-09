#include "ym2610_candidate.h"

#include "ymfm_opn.h"

#include <cstdint>
#include <limits>
#include <new>

namespace {

constexpr uint32_t kMaxClocksPerCall = 1000000u;
constexpr uint32_t kClocksPerSample = 16u;

class candidate_interface final : public ymfm::ymfm_interface {
public:
    candidate_interface(const ym2610_candidate_callbacks *callbacks,
                       void *userdata) noexcept
        : callbacks_(*callbacks), userdata_(userdata) {}

    void reset() noexcept {
        now_ = 0u;
        busy_end_ = 0u;
        timer_due_[0] = timer_due_[1] = 0u;
        timer_active_[0] = timer_active_[1] = false;
        failure_ = YM2610_CANDIDATE_OK;
    }

    ym2610_candidate_status failure() const noexcept { return failure_; }
    bool callback_active() const noexcept { return callback_active_; }
    void fail(ym2610_candidate_status status) noexcept {
        if (failure_ == YM2610_CANDIDATE_OK) failure_ = status;
    }

    void advance_one_clock() {
        ++now_;
        for (uint32_t timer = 0u; timer < 2u; ++timer) {
            if (timer_active_[timer] && timer_due_[timer] <= now_) {
                timer_active_[timer] = false;
                m_engine->engine_timer_expired(timer);
            }
        }
    }

    uint8_t probe_read(uint32_t access, uint32_t address) {
        return ymfm_external_read(access_from_c(access), address);
    }

    void ymfm_set_timer(uint32_t timer, int32_t duration) override {
        if (timer >= 2u) {
            fail(YM2610_CANDIDATE_INVALID_ARGUMENT);
            return;
        }
        if (duration < 0) {
            timer_active_[timer] = false;
            return;
        }
        if (duration == 0 ||
            static_cast<uint64_t>(duration) >
                std::numeric_limits<uint64_t>::max() - now_) {
            timer_active_[timer] = false;
            return;
        }
        timer_due_[timer] = now_ + static_cast<uint64_t>(duration);
        timer_active_[timer] = true;
    }

    void ymfm_set_busy_end(uint32_t clocks) override {
        busy_end_ = clocks > std::numeric_limits<uint64_t>::max() - now_
            ? std::numeric_limits<uint64_t>::max()
            : now_ + clocks;
    }

    bool ymfm_is_busy() override { return now_ < busy_end_; }

    void ymfm_update_irq(bool asserted) override {
        if (callbacks_.irq == nullptr) return;
        if (callback_active_) {
            fail(YM2610_CANDIDATE_CALLBACK_FAILURE);
            return;
        }
        callback_active_ = true;
        try {
            callbacks_.irq(userdata_, asserted ? 1 : 0);
        } catch (...) {
            callback_active_ = false;
            throw;
        }
        callback_active_ = false;
    }

    uint8_t ymfm_external_read(ymfm::access_class access,
                               uint32_t address) override {
        if (failure_ != YM2610_CANDIDATE_OK) return 0u;
        if (!address_allowed(access, address) || callback_active_ ||
            callbacks_.read == nullptr) {
            fail(YM2610_CANDIDATE_CALLBACK_FAILURE);
            return 0u;
        }
        uint8_t value = 0u;
        callback_active_ = true;
        int callback_status = 0;
        try {
            callback_status = callbacks_.read(userdata_, static_cast<uint32_t>(access),
                                              address, &value);
        } catch (...) {
            callback_active_ = false;
            throw;
        }
        callback_active_ = false;
        if (callback_status != 0) {
            fail(YM2610_CANDIDATE_CALLBACK_FAILURE);
        }
        return value;
    }

    void ymfm_external_write(ymfm::access_class access, uint32_t address,
                             uint8_t value) override {
        if (failure_ != YM2610_CANDIDATE_OK) return;
        if (!address_allowed(access, address) || callback_active_ ||
            callbacks_.write == nullptr) {
            fail(YM2610_CANDIDATE_CALLBACK_FAILURE);
            return;
        }
        callback_active_ = true;
        int callback_status = 0;
        try {
            callback_status = callbacks_.write(userdata_, static_cast<uint32_t>(access),
                                               address, value);
        } catch (...) {
            callback_active_ = false;
            throw;
        }
        callback_active_ = false;
        if (callback_status != 0) {
            fail(YM2610_CANDIDATE_CALLBACK_FAILURE);
        }
    }

private:
    bool address_allowed(ymfm::access_class access, uint32_t address) const noexcept {
        uint32_t size = 0u;
        switch (access) {
            case ymfm::ACCESS_IO: size = callbacks_.io_size; break;
            case ymfm::ACCESS_ADPCM_A: size = callbacks_.adpcm_a_size; break;
            case ymfm::ACCESS_ADPCM_B: size = callbacks_.adpcm_b_size; break;
            default: return false;
        }
        return address < size;
    }

    static ymfm::access_class access_from_c(uint32_t access) {
        switch (access) {
            case YM2610_CANDIDATE_ACCESS_ADPCM_A: return ymfm::ACCESS_ADPCM_A;
            case YM2610_CANDIDATE_ACCESS_ADPCM_B: return ymfm::ACCESS_ADPCM_B;
            case YM2610_CANDIDATE_ACCESS_IO: return ymfm::ACCESS_IO;
            default: throw YM2610_CANDIDATE_INVALID_ARGUMENT;
        }
    }

    ym2610_candidate_callbacks callbacks_;
    void *userdata_;
    uint64_t now_ = 0u;
    uint64_t busy_end_ = 0u;
    uint64_t timer_due_[2] = {0u, 0u};
    bool timer_active_[2] = {false, false};
    bool callback_active_ = false;
    ym2610_candidate_status failure_ = YM2610_CANDIDATE_OK;
};

} // namespace

struct ym2610_candidate {
    ym2610_candidate(const ym2610_candidate_callbacks *callbacks,
                     void *userdata)
        : interface(callbacks, userdata), chip(interface, 0x36u) {}

    candidate_interface interface;
    ymfm::ym2610 chip;
    uint8_t clock_remainder = 0u;
    uint64_t total_clocks = 0u;
};

namespace {

template <typename Function>
ym2610_candidate_status guarded(ym2610_candidate *candidate,
                                Function &&function) noexcept {
    if (candidate != nullptr &&
        candidate->interface.failure() != YM2610_CANDIDATE_OK) {
        return candidate->interface.failure();
    }
    if (candidate != nullptr && candidate->interface.callback_active()) {
        candidate->interface.fail(YM2610_CANDIDATE_CALLBACK_FAILURE);
        return YM2610_CANDIDATE_CALLBACK_FAILURE;
    }
    try {
        return function();
    } catch (ym2610_candidate_status status) {
        if (candidate != nullptr) candidate->interface.fail(status);
        return status;
    } catch (...) {
        if (candidate != nullptr) {
            candidate->interface.fail(YM2610_CANDIDATE_EXCEPTION);
        }
        return YM2610_CANDIDATE_EXCEPTION;
    }
}

} // namespace

extern "C" ym2610_candidate_status ym2610_candidate_create(
    const ym2610_candidate_callbacks *callbacks, void *userdata,
    ym2610_candidate **out_candidate) {
    if (out_candidate == nullptr || callbacks == nullptr) {
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    }
    *out_candidate = nullptr;
    try {
        *out_candidate = new (std::nothrow) ym2610_candidate(callbacks, userdata);
    } catch (...) {
        return YM2610_CANDIDATE_EXCEPTION;
    }
    return *out_candidate == nullptr ? YM2610_CANDIDATE_NO_MEMORY
                                     : YM2610_CANDIDATE_OK;
}

extern "C" void ym2610_candidate_destroy(ym2610_candidate *candidate) {
    if (candidate != nullptr && candidate->interface.callback_active()) {
        candidate->interface.fail(YM2610_CANDIDATE_CALLBACK_FAILURE);
        return;
    }
    try {
        delete candidate;
    } catch (...) {
    }
}

extern "C" ym2610_candidate_status ym2610_candidate_reset(
    ym2610_candidate *candidate) {
    if (candidate == nullptr) return YM2610_CANDIDATE_INVALID_ARGUMENT;
    if (candidate->interface.callback_active()) {
        candidate->interface.fail(YM2610_CANDIDATE_CALLBACK_FAILURE);
        return YM2610_CANDIDATE_CALLBACK_FAILURE;
    }
    try {
        candidate->interface.reset();
        candidate->clock_remainder = 0u;
        candidate->total_clocks = 0u;
        candidate->chip.reset();
        return candidate->interface.failure();
    } catch (...) {
        candidate->interface.fail(YM2610_CANDIDATE_EXCEPTION);
        return YM2610_CANDIDATE_EXCEPTION;
    }
}

extern "C" ym2610_candidate_status ym2610_candidate_write(
    ym2610_candidate *candidate, uint32_t port, uint8_t value) {
    if (candidate == nullptr || port > 3u) {
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    }
    return guarded(candidate, [candidate, port, value] {
        candidate->chip.write(port, value);
        return candidate->interface.failure();
    });
}

extern "C" ym2610_candidate_status ym2610_candidate_clock(
    ym2610_candidate *candidate, uint32_t input_clocks, int32_t *samples,
    size_t capacity_frames, size_t *produced_frames) {
    if (produced_frames == nullptr) return YM2610_CANDIDATE_INVALID_ARGUMENT;
    *produced_frames = 0u;
    if (candidate == nullptr) return YM2610_CANDIDATE_INVALID_ARGUMENT;
    if (input_clocks > kMaxClocksPerCall) return YM2610_CANDIDATE_LIMIT;
    if (input_clocks > std::numeric_limits<uint64_t>::max() -
                           candidate->total_clocks) {
        return YM2610_CANDIDATE_LIMIT;
    }
    const uint64_t frame_count =
        (static_cast<uint64_t>(candidate->clock_remainder) + input_clocks) /
        kClocksPerSample;
    if (frame_count > capacity_frames || (frame_count != 0u && samples == nullptr)) {
        return YM2610_CANDIDATE_CAPACITY;
    }
    return guarded(candidate, [candidate, input_clocks, samples, produced_frames] {
        size_t produced = 0u;
        for (uint32_t clock = 0u; clock < input_clocks; ++clock) {
            candidate->interface.advance_one_clock();
            ++candidate->total_clocks;
            ++candidate->clock_remainder;
            if (candidate->clock_remainder == kClocksPerSample) {
                candidate->clock_remainder = 0u;
                ymfm::ym2610::output_data output = {};
                candidate->chip.generate(&output, 1u);
                samples[produced * 3u] = output.data[0];
                samples[produced * 3u + 1u] = output.data[1];
                samples[produced * 3u + 2u] = output.data[2];
                ++produced;
                *produced_frames = produced;
                if (candidate->interface.failure() != YM2610_CANDIDATE_OK) {
                    return candidate->interface.failure();
                }
            }
        }
        *produced_frames = produced;
        return candidate->interface.failure();
    });
}

extern "C" ym2610_candidate_status ym2610_candidate_sample_rate(
    uint32_t input_clock, uint32_t *rate) {
    if (rate == nullptr || input_clock == 0u) {
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    }
    *rate = input_clock / kClocksPerSample;
    return *rate == 0u ? YM2610_CANDIDATE_INVALID_ARGUMENT
                       : YM2610_CANDIDATE_OK;
}

#ifdef GLUEYNEO_YM2610_TEST_HOOKS
extern "C" ym2610_candidate_status ym2610_candidate_test_probe_read(
    ym2610_candidate *candidate, uint32_t access, uint32_t address) {
    if (candidate == nullptr) return YM2610_CANDIDATE_INVALID_ARGUMENT;
    return guarded(candidate, [candidate, access, address] {
        (void)candidate->interface.probe_read(access, address);
        return candidate->interface.failure();
    });
}

extern "C" ym2610_candidate_status ym2610_candidate_test_throw(void) {
    return guarded(nullptr, []() -> ym2610_candidate_status {
        throw std::bad_alloc();
    });
}
#endif
