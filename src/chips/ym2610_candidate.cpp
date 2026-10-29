#include "ym2610_candidate.h"

#include "ymfm_opn.h"

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <limits>
#include <new>
#include <utility>
#include <vector>

namespace {

constexpr uint32_t kMaxClocksPerCall = 1000000u;
constexpr uint32_t kClocksPerSample = 16u;
constexpr uint64_t kYmTimerMaxDuration[2] = {
    UINT64_C(1024) * ymfm::ym2610::fm_engine::OPERATORS * UINT64_C(6),
    UINT64_C(4096) * ymfm::ym2610::fm_engine::OPERATORS * UINT64_C(6)
};
constexpr uint64_t kYmBusyMaxDuration = UINT64_C(32) * UINT64_C(6);
static_assert(ymfm::ym2610::fm_engine::OPERATORS == 24u,
              "YM2610 timer bounds require the six-channel, 24-operator OPN-A engine");

#if defined(GLUEYNEO_YM2610_TEST_HOOKS) || defined(GLUEYNEO_SDK_TEST_HOOKS)
struct allocation_control {
    size_t fail_at;
    size_t allocation_points = 0u;
    int64_t lifetime_balance = 0;
    size_t requested_bytes = 0u;
    size_t high_water_bytes = 0u;
    uint32_t failed_site = 0u;
};

thread_local allocation_control *active_allocation_control = nullptr;
thread_local bool bypass_next_state_validation = false;
thread_local bool bypass_next_state_relation = false;

class allocation_scope {
public:
    explicit allocation_scope(size_t fail_at) : previous_(active_allocation_control) {
        control_.fail_at = fail_at;
        active_allocation_control = &control_;
    }
    ~allocation_scope() { active_allocation_control = previous_; }
    allocation_scope(const allocation_scope &) = delete;
    allocation_scope &operator=(const allocation_scope &) = delete;

    size_t points() const noexcept { return control_.allocation_points; }
    int64_t lifetime_balance() const noexcept { return control_.lifetime_balance; }
    size_t requested_bytes() const noexcept { return control_.requested_bytes; }
    size_t high_water_bytes() const noexcept { return control_.high_water_bytes; }
    uint32_t failed_site() const noexcept { return control_.failed_site; }

private:
    allocation_control control_{};
    allocation_control *previous_;
};

void allocation_point(size_t bytes = 0u, uint32_t site = 0u) {
    if (active_allocation_control == nullptr) return;
    const size_t current = active_allocation_control->allocation_points++;
    if (current == active_allocation_control->fail_at) {
        active_allocation_control->failed_site = site;
        throw std::bad_alloc();
    }
    if (bytes > std::numeric_limits<size_t>::max() -
                    active_allocation_control->requested_bytes)
        throw std::bad_alloc();
    active_allocation_control->requested_bytes += bytes;
    if (active_allocation_control->requested_bytes >
        active_allocation_control->high_water_bytes)
        active_allocation_control->high_water_bytes =
            active_allocation_control->requested_bytes;
}

void lifetime_delta(int64_t delta) noexcept {
    if (active_allocation_control != nullptr)
        active_allocation_control->lifetime_balance += delta;
}
#else
void allocation_point(size_t = 0u, uint32_t = 0u) {}
void lifetime_delta(int64_t) noexcept {}
#endif

void increment(uint64_t &value) noexcept {
    if (value != std::numeric_limits<uint64_t>::max()) ++value;
}

uint32_t magnitude(int32_t value) noexcept {
    return value < 0 ? static_cast<uint32_t>(-(static_cast<int64_t>(value)))
                     : static_cast<uint32_t>(value);
}

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
        clear_diagnostics();
    }

    void clear_diagnostics() noexcept {
        timer_programs_ = 0u;
        timer_expirations_ = 0u;
        adpcm_a_sample_reads_ = 0u;
        adpcm_b_sample_reads_ = 0u;
        irq_assertions_ = 0u;
        irq_deassertions_ = 0u;
    }

    void copy_diagnostics(ym2610_candidate_observation *out) const noexcept {
        out->timer_programs = timer_programs_;
        out->timer_expirations = timer_expirations_;
        out->adpcm_a_sample_reads = adpcm_a_sample_reads_;
        out->adpcm_b_sample_reads = adpcm_b_sample_reads_;
        out->irq_assertions = irq_assertions_;
        out->irq_deassertions = irq_deassertions_;
    }

    ym2610_candidate_status failure() const noexcept { return failure_; }
    bool callback_active() const noexcept { return callback_active_; }
    void state_clock(uint64_t &now, uint64_t &busy_end,
                     uint64_t (&timer_due)[2], bool (&timer_active)[2]) const noexcept {
        now = now_;
        busy_end = busy_end_;
        for (uint32_t timer = 0u; timer < 2u; ++timer) {
            timer_due[timer] = timer_due_[timer];
            timer_active[timer] = timer_active_[timer];
        }
    }
    void restore_clock(uint64_t now, uint64_t busy_end,
                       const uint64_t (&timer_due)[2],
                       const bool (&timer_active)[2]) noexcept {
        now_ = now;
        busy_end_ = busy_end;
        for (uint32_t timer = 0u; timer < 2u; ++timer) {
            timer_due_[timer] = timer_due[timer];
            timer_active_[timer] = timer_active[timer];
        }
        failure_ = YM2610_CANDIDATE_OK;
        callback_active_ = false;
    }
    void rebind(const ym2610_candidate_callbacks &callbacks,
                void *userdata) noexcept {
        callbacks_ = callbacks;
        userdata_ = userdata;
        failure_ = YM2610_CANDIDATE_OK;
        callback_active_ = false;
    }
    void fail(ym2610_candidate_status status) noexcept {
        if (failure_ == YM2610_CANDIDATE_OK) failure_ = status;
    }

    void advance_one_clock() {
        ++now_;
        for (uint32_t timer = 0u; timer < 2u; ++timer) {
            if (timer_active_[timer] && timer_due_[timer] <= now_) {
                timer_active_[timer] = false;
                increment(timer_expirations_);
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
        increment(timer_programs_);
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
        increment(asserted ? irq_assertions_ : irq_deassertions_);
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
        if (access == ymfm::ACCESS_ADPCM_A) increment(adpcm_a_sample_reads_);
        else if (access == ymfm::ACCESS_ADPCM_B) increment(adpcm_b_sample_reads_);
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
    uint64_t timer_programs_ = 0u;
    uint64_t timer_expirations_ = 0u;
    uint64_t adpcm_a_sample_reads_ = 0u;
    uint64_t adpcm_b_sample_reads_ = 0u;
    uint64_t irq_assertions_ = 0u;
    uint64_t irq_deassertions_ = 0u;
};

} // namespace

#if defined(GLUEYNEO_YM2610_TEST_HOOKS) || defined(GLUEYNEO_SDK_TEST_HOOKS)
namespace ymfm {
void ymfm_test_allocation_point(size_t bytes, uint32_t site) {
    ::allocation_point(bytes, site);
}
void ymfm_test_lifetime_delta(int64_t delta) noexcept { ::lifetime_delta(delta); }
} // namespace ymfm
#endif

struct ym2610_candidate {
    ym2610_candidate(const ym2610_candidate_callbacks *callbacks,
                     void *userdata)
        : interface(callbacks, userdata), chip(interface, 0x36u) {
        lifetime_delta(1);
    }
    ~ym2610_candidate() { lifetime_delta(-1); }

    candidate_interface interface;
    ymfm::ym2610 chip;
    uint8_t clock_remainder = 0u;
    uint64_t total_clocks = 0u;
    uint64_t diagnostic_clocks = 0u;
    uint8_t selected_register[2] = {0u, 0u};
    uint32_t event_count = 0u;
    uint32_t event_dropped = 0u;
    uint64_t register_writes = 0u;
    uint64_t ssg_register_writes = 0u;
    uint64_t ssg_volume_writes = 0u;
    uint64_t control_register_writes = 0u;
    uint64_t fm_register_writes = 0u;
    uint64_t fm_key_on_writes = 0u;
    uint64_t fm_key_off_writes = 0u;
    uint64_t fm_frequency_writes = 0u;
    uint64_t fm_level_writes = 0u;
    uint64_t fm_pan_writes = 0u;
    uint64_t adpcm_a_register_writes = 0u;
    uint64_t adpcm_a_control_writes = 0u;
    uint64_t adpcm_b_register_writes = 0u;
    uint64_t adpcm_b_control_writes = 0u;
    uint64_t native_frames = 0u;
    uint64_t native_nonzero_frames = 0u;
    uint64_t native_stereo_nonzero_frames = 0u;
    uint64_t native_ssg_nonzero_frames = 0u;
    uint32_t native_peak = 0u;
    ym2610_candidate_register_event events[
        YM2610_CANDIDATE_DIAGNOSTIC_EVENT_CAPACITY] = {};
};

extern "C" size_t ym2610_candidate_state_heap_bound(void) {
    using registers = ymfm::opna_registers;
    return sizeof(ym2610_candidate) +
        registers::CHANNELS * sizeof(ymfm::fm_channel<registers>) +
        registers::OPERATORS * sizeof(ymfm::fm_operator<registers>) +
        ymfm::adpcm_a_engine::CHANNELS * sizeof(ymfm::adpcm_a_channel) +
        sizeof(ymfm::adpcm_b_channel);
}

extern "C" size_t ym2610_candidate_state_allocation_bound(void) {
    return 1u + ymfm::opna_registers::CHANNELS +
        ymfm::opna_registers::OPERATORS + ymfm::adpcm_a_engine::CHANNELS + 1u;
}

extern "C" size_t ym2610_candidate_state_stack_bound(void) {
    /* traverse_state's guest clock/latch copies plus the span visitor.
     * This is object storage, not compiler-generated stack-frame usage. */
    return sizeof(ymfm::ymfm_saved_state) + 2u * sizeof(uint32_t) +
        5u * sizeof(uint64_t) + 2u * sizeof(bool) + 3u * sizeof(uint8_t);
}

namespace {

void clear_candidate_diagnostics(ym2610_candidate *candidate) noexcept {
    candidate->diagnostic_clocks = 0u;
    candidate->event_count = 0u;
    candidate->event_dropped = 0u;
    candidate->register_writes = 0u;
    candidate->ssg_register_writes = 0u;
    candidate->ssg_volume_writes = 0u;
    candidate->control_register_writes = 0u;
    candidate->fm_register_writes = 0u;
    candidate->fm_key_on_writes = 0u;
    candidate->fm_key_off_writes = 0u;
    candidate->fm_frequency_writes = 0u;
    candidate->fm_level_writes = 0u;
    candidate->fm_pan_writes = 0u;
    candidate->adpcm_a_register_writes = 0u;
    candidate->adpcm_a_control_writes = 0u;
    candidate->adpcm_b_register_writes = 0u;
    candidate->adpcm_b_control_writes = 0u;
    candidate->native_frames = 0u;
    candidate->native_nonzero_frames = 0u;
    candidate->native_stereo_nonzero_frames = 0u;
    candidate->native_ssg_nonzero_frames = 0u;
    candidate->native_peak = 0u;
    candidate->interface.clear_diagnostics();
}

uint8_t register_family(uint8_t bank, uint8_t reg) noexcept {
    /* Port/bank ranges follow the Yamaha YM2610 Application Manual's register
     * allocation and the pinned ymfm_opn.cpp write_data/write_data_hi decoder.
     * Counters classify guest writes; they do not prove audible output. */
    if (bank == 0u && reg <= 0x0du) return YM2610_CANDIDATE_FAMILY_SSG;
    if (bank == 0u && reg >= 0x10u && reg <= 0x1bu)
        return YM2610_CANDIDATE_FAMILY_ADPCM_B;
    if (bank == 1u && reg <= 0x2fu)
        return YM2610_CANDIDATE_FAMILY_ADPCM_A;
    if (bank == 0u &&
        ((reg >= 0x0eu && reg <= 0x0fu) ||
         (reg >= 0x1cu && reg <= 0x1fu) ||
         (reg >= 0x20u && reg <= 0x2fu)))
        return YM2610_CANDIDATE_FAMILY_CONTROL;
    return YM2610_CANDIDATE_FAMILY_FM;
}

void record_register_write(ym2610_candidate *candidate, uint32_t port,
                           uint8_t value) noexcept {
    const uint32_t bank = port >= 2u ? 1u : 0u;
    if ((port & 1u) == 0u) {
        candidate->selected_register[bank] = value;
        return;
    }
    const uint8_t reg = candidate->selected_register[bank];
    const uint8_t family = register_family(static_cast<uint8_t>(bank), reg);
    increment(candidate->register_writes);
    if (bank == 0u && reg == 0x28u) {
        increment((value & 0xf0u) != 0u
            ? candidate->fm_key_on_writes
            : candidate->fm_key_off_writes);
    }
    switch (family) {
        case YM2610_CANDIDATE_FAMILY_SSG:
            increment(candidate->ssg_register_writes);
            if (reg >= 0x08u && reg <= 0x0au)
                increment(candidate->ssg_volume_writes);
            break;
        case YM2610_CANDIDATE_FAMILY_FM:
            increment(candidate->fm_register_writes);
            if ((reg >= 0xa0u && reg <= 0xa2u) ||
                (reg >= 0xa4u && reg <= 0xa6u))
                increment(candidate->fm_frequency_writes);
            if (reg >= 0x40u && reg <= 0x4fu)
                increment(candidate->fm_level_writes);
            if (reg >= 0xb4u && reg <= 0xb6u)
                increment(candidate->fm_pan_writes);
            break;
        case YM2610_CANDIDATE_FAMILY_ADPCM_A:
            increment(candidate->adpcm_a_register_writes);
            if (reg == 0x00u) increment(candidate->adpcm_a_control_writes);
            break;
        case YM2610_CANDIDATE_FAMILY_ADPCM_B:
            increment(candidate->adpcm_b_register_writes);
            if (reg == 0x10u) increment(candidate->adpcm_b_control_writes);
            break;
        case YM2610_CANDIDATE_FAMILY_CONTROL:
            increment(candidate->control_register_writes);
            break;
        default:
            break;
    }
    if (candidate->event_count < YM2610_CANDIDATE_DIAGNOSTIC_EVENT_CAPACITY) {
        ym2610_candidate_register_event &event =
            candidate->events[candidate->event_count++];
        event.clock = candidate->diagnostic_clocks;
        event.port = static_cast<uint8_t>(port);
        event.bank = static_cast<uint8_t>(bank);
        event.reg = reg;
        event.value = value;
        event.family = family;
    } else {
        if (candidate->event_dropped != UINT32_MAX) ++candidate->event_dropped;
    }
}

void record_native_frame(ym2610_candidate *candidate,
                         const ymfm::ym2610::output_data &output) noexcept {
    increment(candidate->native_frames);
    const uint32_t left = magnitude(output.data[0]);
    const uint32_t right = magnitude(output.data[1]);
    const uint32_t ssg = magnitude(output.data[2]);
    if (left != 0u || right != 0u || ssg != 0u)
        increment(candidate->native_nonzero_frames);
    if (left != 0u || right != 0u)
        increment(candidate->native_stereo_nonzero_frames);
    if (ssg != 0u) increment(candidate->native_ssg_nonzero_frames);
    candidate->native_peak = std::max(candidate->native_peak,
                                      std::max(left, std::max(right, ssg)));
}

constexpr uint32_t kStateMagic = UINT32_C(0x47594d31); /* GYM1 */
constexpr uint32_t kStateVersion = 1u;

int stage_read(void *, uint32_t, uint32_t, uint8_t *value) {
    if (value == nullptr) return -1;
    *value = 0u;
    return 0;
}

int stage_write(void *, uint32_t, uint32_t, uint8_t) { return 0; }
void stage_irq(void *, int) {}

const ym2610_candidate_callbacks kStageCallbacks = {
    stage_read, stage_write, stage_irq, 0u, 0u, 0u
};

#if defined(GLUEYNEO_YM2610_TEST_HOOKS) || defined(GLUEYNEO_SDK_TEST_HOOKS)
void state_vector_growth(void *) { allocation_point(0u, 5u); }
void state_vector_growth_observe(void *, size_t capacity) {
    if (active_allocation_control != nullptr &&
        capacity > active_allocation_control->high_water_bytes)
        active_allocation_control->high_water_bytes = capacity;
}
#endif

ym2610_candidate_state_reason state_reason(ymfm::ymfm_saved_state::error error) {
    using saved_error = ymfm::ymfm_saved_state::error;
    switch (error) {
        case saved_error::underflow:
            return YM2610_CANDIDATE_STATE_REASON_TRUNCATED;
        case saved_error::trailing_data:
            return YM2610_CANDIDATE_STATE_REASON_TRAILING;
        case saved_error::invalid_boolean:
            return YM2610_CANDIDATE_STATE_REASON_BOOLEAN;
        case saved_error::invalid_enum:
            return YM2610_CANDIDATE_STATE_REASON_ENUM;
        case saved_error::invalid_range:
        case saved_error::too_large:
            return YM2610_CANDIDATE_STATE_REASON_RANGE;
        case saved_error::none:
        default:
            return YM2610_CANDIDATE_STATE_REASON_NONE;
    }
}

ym2610_candidate_status state_status(ym2610_candidate_state_reason reason) {
    return reason == YM2610_CANDIDATE_STATE_REASON_NONE
        ? YM2610_CANDIDATE_OK : YM2610_CANDIDATE_INVALID_ARGUMENT;
}

void set_state_detail(ym2610_candidate_state_detail *detail,
                      ym2610_candidate_state_reason reason,
                      size_t offset, size_t consumed) {
    if (detail == nullptr) return;
    detail->reason = reason;
    detail->offset = offset;
    detail->consumed = consumed;
}

ym2610_candidate_state_reason traverse_state(
    ym2610_candidate *candidate, ymfm::ymfm_saved_state &state) {
    uint32_t magic = kStateMagic;
    uint32_t version = kStateVersion;
    uint64_t now = 0u;
    uint64_t busy_end = 0u;
    uint64_t timer_due[2] = {0u, 0u};
    bool timer_active[2] = {false, false};
    uint8_t clock_remainder = 0u;
    uint64_t total_clocks = 0u;
    uint8_t selected_register[2] = {0u, 0u};

    if (state.saving()) {
        candidate->interface.state_clock(now, busy_end, timer_due, timer_active);
        clock_remainder = candidate->clock_remainder;
        total_clocks = candidate->total_clocks;
        selected_register[0] = candidate->selected_register[0];
        selected_register[1] = candidate->selected_register[1];
    }

    state.save_restore(magic);
    state.save_restore(version);
    if (!state.saving() && state.failed())
        return state_reason(state.failure());
    if (!state.saving() && magic != kStateMagic) {
        state.reject(ymfm::ymfm_saved_state::error::invalid_range);
        return YM2610_CANDIDATE_STATE_REASON_MAGIC;
    }
    if (!state.saving() && version != kStateVersion) {
        state.reject(ymfm::ymfm_saved_state::error::invalid_range);
        return YM2610_CANDIDATE_STATE_REASON_VERSION;
    }

    state.save_restore(now);
    state.save_restore(busy_end);
    state.save_restore(timer_due);
    state.save_restore(timer_active);
    state.save_restore(clock_remainder);
    state.save_restore(total_clocks);
    state.save_restore(selected_register);

    if (!state.saving()) {
        state.require(total_clocks == now);
        state.require(clock_remainder < kClocksPerSample);
        state.require(clock_remainder == total_clocks % kClocksPerSample);
        for (uint32_t timer = 0u; timer < 2u; ++timer) {
            if (timer_active[timer]) state.require(timer_due[timer] > now);
        }
    }

    if (!state.saving()) {
        candidate->interface.restore_clock(now, busy_end, timer_due, timer_active);
        candidate->clock_remainder = clock_remainder;
        candidate->total_clocks = total_clocks;
        candidate->selected_register[0] = selected_register[0];
        candidate->selected_register[1] = selected_register[1];
    }

    candidate->chip.save_restore(state);
    candidate->chip.save_restore_held_output(state);
    state.finish();
    return state_reason(state.failure());
}

ym2610_candidate_state_reason check_wrapper_chip_relation(
    const ym2610_candidate *candidate, size_t *field_offset) {
    if (field_offset != nullptr) *field_offset = 0u;
    if (candidate == nullptr || field_offset == nullptr)
        return YM2610_CANDIDATE_STATE_REASON_ARGUMENT;

    uint64_t now = 0u;
    uint64_t busy_end = 0u;
    uint64_t timer_due[2] = {0u, 0u};
    bool timer_active[2] = {false, false};
    candidate->interface.state_clock(now, busy_end, timer_due, timer_active);
    if (!(busy_end <= now || busy_end - now <= kYmBusyMaxDuration)) {
        *field_offset = 16u;
        return YM2610_CANDIDATE_STATE_REASON_INVARIANT;
    }

    for (uint32_t timer = 0u; timer < 2u; ++timer) {
        const bool chip_running =
            candidate->chip.fm_engine_state().timer_running(timer) != 0u;
        if (timer_active[timer] != chip_running) {
            *field_offset = 40u + timer;
            return YM2610_CANDIDATE_STATE_REASON_INVARIANT;
        }
    }
    for (uint32_t timer = 0u; timer < 2u; ++timer) {
        if (timer_active[timer] && timer_due[timer] > now &&
            timer_due[timer] - now > kYmTimerMaxDuration[timer]) {
            *field_offset = 24u + 8u * timer;
            return YM2610_CANDIDATE_STATE_REASON_INVARIANT;
        }
    }
    return YM2610_CANDIDATE_STATE_REASON_NONE;
}

ym2610_candidate_state_reason measure_state(const ym2610_candidate *candidate,
                                             size_t *size) {
    ymfm::ymfm_saved_state state(size);
    ym2610_candidate *mutable_candidate = const_cast<ym2610_candidate *>(candidate);
    const ym2610_candidate_state_reason reason = traverse_state(mutable_candidate, state);
    if (reason != YM2610_CANDIDATE_STATE_REASON_NONE) return reason;
    return state.failed() ? state_reason(state.failure())
                         : YM2610_CANDIDATE_STATE_REASON_NONE;
}

} // namespace

namespace {

template <typename Factory>
ym2610_candidate_status create_guarded(ym2610_candidate **out_candidate,
                                       Factory &&factory) noexcept {
    *out_candidate = nullptr;
    try {
        *out_candidate = factory();
    } catch (const std::bad_alloc &) {
        return YM2610_CANDIDATE_NO_MEMORY;
    } catch (...) {
        return YM2610_CANDIDATE_EXCEPTION;
    }
    return *out_candidate == nullptr ? YM2610_CANDIDATE_NO_MEMORY
                                     : YM2610_CANDIDATE_OK;
}

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
    return create_guarded(out_candidate, [callbacks, userdata] {
        allocation_point(sizeof(ym2610_candidate), 6u);
        return new (std::nothrow) ym2610_candidate(callbacks, userdata);
    });
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
        candidate->selected_register[0] = 0u;
        candidate->selected_register[1] = 0u;
        clear_candidate_diagnostics(candidate);
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
        record_register_write(candidate, port, value);
        candidate->chip.write(port, value);
        return candidate->interface.failure();
    });
}

extern "C" ym2610_candidate_status ym2610_candidate_diagnostics_clear(
    ym2610_candidate *candidate) {
    if (candidate == nullptr) return YM2610_CANDIDATE_INVALID_ARGUMENT;
    if (candidate->interface.callback_active()) {
        candidate->interface.fail(YM2610_CANDIDATE_CALLBACK_FAILURE);
        return YM2610_CANDIDATE_CALLBACK_FAILURE;
    }
    clear_candidate_diagnostics(candidate);
    return candidate->interface.failure();
}

extern "C" ym2610_candidate_status ym2610_candidate_observe(
    const ym2610_candidate *candidate, ym2610_candidate_observation *out) {
    if (candidate == nullptr || out == nullptr)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    if (candidate->interface.callback_active())
        return YM2610_CANDIDATE_CALLBACK_FAILURE;
    *out = {};
    out->version = 1u;
    out->event_count = candidate->event_count;
    out->event_dropped = candidate->event_dropped;
    out->clocks = candidate->diagnostic_clocks;
    out->register_writes = candidate->register_writes;
    out->ssg_register_writes = candidate->ssg_register_writes;
    out->ssg_volume_writes = candidate->ssg_volume_writes;
    out->control_register_writes = candidate->control_register_writes;
    out->fm_register_writes = candidate->fm_register_writes;
    out->fm_key_on_writes = candidate->fm_key_on_writes;
    out->fm_key_off_writes = candidate->fm_key_off_writes;
    out->fm_frequency_writes = candidate->fm_frequency_writes;
    out->fm_level_writes = candidate->fm_level_writes;
    out->fm_pan_writes = candidate->fm_pan_writes;
    out->adpcm_a_register_writes = candidate->adpcm_a_register_writes;
    out->adpcm_a_control_writes = candidate->adpcm_a_control_writes;
    out->adpcm_b_register_writes = candidate->adpcm_b_register_writes;
    out->adpcm_b_control_writes = candidate->adpcm_b_control_writes;
    out->native_frames = candidate->native_frames;
    out->native_nonzero_frames = candidate->native_nonzero_frames;
    out->native_stereo_nonzero_frames = candidate->native_stereo_nonzero_frames;
    out->native_ssg_nonzero_frames = candidate->native_ssg_nonzero_frames;
    out->native_peak = candidate->native_peak;
    candidate->interface.copy_diagnostics(out);
    for (uint32_t index = 0u; index < candidate->event_count; ++index)
        out->events[index] = candidate->events[index];
    return YM2610_CANDIDATE_OK;
}

extern "C" ym2610_candidate_status ym2610_candidate_read(
    ym2610_candidate *candidate, uint32_t port, uint8_t *value) {
    if (candidate == nullptr || port > 3u || value == nullptr) {
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    }
    return guarded(candidate, [candidate, port, value] {
        const uint8_t result = candidate->chip.read(port);
        const ym2610_candidate_status status = candidate->interface.failure();
        if (status == YM2610_CANDIDATE_OK) *value = result;
        return status;
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
            increment(candidate->diagnostic_clocks);
            ++candidate->clock_remainder;
            if (candidate->clock_remainder == kClocksPerSample) {
                candidate->clock_remainder = 0u;
                ymfm::ym2610::output_data output = {};
                candidate->chip.generate(&output, 1u);
                record_native_frame(candidate, output);
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

#if defined(GLUEYNEO_YM2610_CANDIDATE_INTERNAL) || \
    defined(GLUEYNEO_YM2610_TEST_HOOKS) || \
    defined(GLUEYNEO_SDK_TEST_HOOKS)
extern "C" ym2610_candidate_status ym2610_candidate_state_size(
    const ym2610_candidate *candidate, size_t *size) {
    if (size != nullptr) *size = 0u;
    if (candidate == nullptr || size == nullptr)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    if (candidate->interface.callback_active())
        return YM2610_CANDIDATE_CALLBACK_FAILURE;
    if (candidate->interface.failure() != YM2610_CANDIDATE_OK)
        return candidate->interface.failure();
    try {
        const ym2610_candidate_state_reason reason = measure_state(candidate, size);
        return state_status(reason);
    } catch (const std::bad_alloc &) {
        *size = 0u;
        return YM2610_CANDIDATE_NO_MEMORY;
    } catch (...) {
        *size = 0u;
        return YM2610_CANDIDATE_EXCEPTION;
    }
}

extern "C" ym2610_candidate_status ym2610_candidate_state_timer_bound(
    uint32_t timer, uint64_t *out_bound) {
    if (out_bound != nullptr) *out_bound = 0u;
    if (out_bound == nullptr || timer >= 2u)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    *out_bound = kYmTimerMaxDuration[timer];
    return YM2610_CANDIDATE_OK;
}

extern "C" ym2610_candidate_status ym2610_candidate_state_busy_bound(
    uint64_t *out_bound) {
    if (out_bound == nullptr) return YM2610_CANDIDATE_INVALID_ARGUMENT;
    *out_bound = kYmBusyMaxDuration;
    return YM2610_CANDIDATE_OK;
}

extern "C" ym2610_candidate_status ym2610_candidate_state_capture(
    const ym2610_candidate *candidate, uint8_t *destination, size_t capacity,
    size_t *written) {
    if (written == nullptr) return YM2610_CANDIDATE_INVALID_ARGUMENT;
    *written = 0u;
    if (candidate == nullptr) return YM2610_CANDIDATE_INVALID_ARGUMENT;
    if (candidate->interface.callback_active())
        return YM2610_CANDIDATE_CALLBACK_FAILURE;
    if (candidate->interface.failure() != YM2610_CANDIDATE_OK)
        return candidate->interface.failure();

    size_t required = 0u;
    ym2610_candidate_status status = ym2610_candidate_state_size(candidate, &required);
    if (status != YM2610_CANDIDATE_OK) return status;
    if (capacity < required) return YM2610_CANDIDATE_CAPACITY;
    if (destination == nullptr) return YM2610_CANDIDATE_INVALID_ARGUMENT;

    try {
        std::vector<uint8_t> bytes;
#if defined(GLUEYNEO_YM2610_TEST_HOOKS) || defined(GLUEYNEO_SDK_TEST_HOOKS)
        ymfm::ymfm_saved_state state(bytes, true,
            ymfm::ymfm_saved_state::format::canonical_big_endian, required,
            state_vector_growth, nullptr,
            state_vector_growth_observe, nullptr);
#else
        ymfm::ymfm_saved_state state(bytes, true,
            ymfm::ymfm_saved_state::format::canonical_big_endian, required);
#endif
        const ym2610_candidate_state_reason reason =
            traverse_state(const_cast<ym2610_candidate *>(candidate), state);
        if (reason != YM2610_CANDIDATE_STATE_REASON_NONE)
            return state_status(reason);
        if (state.failed() || bytes.size() != required)
            return YM2610_CANDIDATE_EXCEPTION;
        std::memcpy(destination, bytes.data(), bytes.size());
        *written = bytes.size();
        return YM2610_CANDIDATE_OK;
    } catch (const std::bad_alloc &) {
        return YM2610_CANDIDATE_NO_MEMORY;
    } catch (...) {
        return YM2610_CANDIDATE_EXCEPTION;
    }
}

extern "C" ym2610_candidate_status ym2610_candidate_state_stage(
    const uint8_t *bytes, size_t length, ym2610_candidate **staged,
    ym2610_candidate_state_detail *detail) {
#if defined(GLUEYNEO_YM2610_TEST_HOOKS) || defined(GLUEYNEO_SDK_TEST_HOOKS)
    const bool bypass_validation =
        std::exchange(bypass_next_state_validation, false);
    const bool bypass_relation =
        std::exchange(bypass_next_state_relation, false);
#else
    constexpr bool bypass_relation = false;
#endif
    if (staged != nullptr) *staged = nullptr;
    set_state_detail(detail, YM2610_CANDIDATE_STATE_REASON_NONE, 0u, 0u);
    if (staged == nullptr || (bytes == nullptr && length != 0u)) {
        set_state_detail(detail, YM2610_CANDIDATE_STATE_REASON_ARGUMENT, 0u, 0u);
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    }

    ym2610_candidate *candidate = nullptr;
    try {
        allocation_point(sizeof(ym2610_candidate), 7u);
        candidate = new (std::nothrow) ym2610_candidate(&kStageCallbacks, nullptr);
        if (candidate == nullptr) return YM2610_CANDIDATE_NO_MEMORY;
#if defined(GLUEYNEO_YM2610_TEST_HOOKS) || defined(GLUEYNEO_SDK_TEST_HOOKS)
        if (bypass_validation) {
            *staged = candidate;
            return YM2610_CANDIDATE_OK;
        }
#endif
        ymfm::ymfm_saved_state state(bytes, length,
            ymfm::ymfm_saved_state::format::canonical_big_endian);
        const ym2610_candidate_state_reason reason = traverse_state(candidate, state);
        set_state_detail(detail, reason, state.error_offset(), state.consumed());
        if (reason != YM2610_CANDIDATE_STATE_REASON_NONE) {
            delete candidate;
            return state_status(reason);
        }
        if (!bypass_relation) {
            size_t field_offset = 0u;
            const ym2610_candidate_state_reason relation_reason =
                check_wrapper_chip_relation(candidate, &field_offset);
            if (relation_reason != YM2610_CANDIDATE_STATE_REASON_NONE) {
                set_state_detail(detail, relation_reason, field_offset,
                                 state.consumed());
                delete candidate;
                return state_status(relation_reason);
            }
        }
        *staged = candidate;
        return YM2610_CANDIDATE_OK;
    } catch (const std::bad_alloc &) {
        delete candidate;
        return YM2610_CANDIDATE_NO_MEMORY;
    } catch (...) {
        delete candidate;
        return YM2610_CANDIDATE_EXCEPTION;
    }
}

extern "C" ym2610_candidate_status ym2610_candidate_state_validate(
    const uint8_t *bytes, size_t length,
    ym2610_candidate_state_detail *detail) {
    ym2610_candidate *staged = nullptr;
    const ym2610_candidate_status status =
        ym2610_candidate_state_stage(bytes, length, &staged, detail);
    ym2610_candidate_destroy(staged);
    return status;
}

extern "C" ym2610_candidate_status
ym2610_candidate_state_irq_line(const ym2610_candidate *candidate,
                                uint8_t *out_asserted) {
    if (candidate == nullptr || out_asserted == nullptr)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    *out_asserted = candidate->chip.fm_engine_state().irq_state() != 0u;
    return YM2610_CANDIDATE_OK;
}

extern "C" ym2610_candidate_status ym2610_candidate_state_rebind(
    ym2610_candidate *staged,
    const ym2610_candidate_callbacks *callbacks, void *userdata) {
    if (staged == nullptr || callbacks == nullptr)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    if (staged->interface.callback_active())
        return YM2610_CANDIDATE_CALLBACK_FAILURE;
    if (staged->interface.failure() != YM2610_CANDIDATE_OK)
        return staged->interface.failure();
    staged->interface.rebind(*callbacks, userdata);
    return YM2610_CANDIDATE_OK;
}
#endif

#if defined(GLUEYNEO_YM2610_TEST_HOOKS) || defined(GLUEYNEO_SDK_TEST_HOOKS)
extern "C" void ym2610_candidate_test_bypass_next_state_validation(void) {
    bypass_next_state_validation = true;
}

extern "C" void ym2610_candidate_test_bypass_next_state_relation(void) {
    bypass_next_state_relation = true;
}

extern "C" ym2610_candidate_status ym2610_candidate_test_create_oom(void) {
    ym2610_candidate *candidate = nullptr;
    return create_guarded(&candidate, []() -> ym2610_candidate * {
        throw std::bad_alloc();
    });
}

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

extern "C" ym2610_candidate_status
ym2610_candidate_test_state_create_failpoint(size_t fail_at,
                                              size_t *allocation_points,
                                              int64_t *lifetime_balance) {
    if (allocation_points == nullptr || lifetime_balance == nullptr)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    allocation_scope scope(fail_at);
    ym2610_candidate *candidate = nullptr;
    const ym2610_candidate_status status =
        ym2610_candidate_create(&kStageCallbacks, nullptr, &candidate);
    ym2610_candidate_destroy(candidate);
    *allocation_points = scope.points();
    *lifetime_balance = scope.lifetime_balance();
    return status;
}

extern "C" ym2610_candidate_status
ym2610_candidate_test_state_stage_failpoint(const uint8_t *bytes, size_t length,
                                             size_t fail_at,
                                             size_t *allocation_points,
                                             int64_t *lifetime_balance) {
    if (allocation_points == nullptr || lifetime_balance == nullptr)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    allocation_scope scope(fail_at);
    ym2610_candidate *staged = nullptr;
    ym2610_candidate_state_detail detail{};
    const ym2610_candidate_status status =
        ym2610_candidate_state_stage(bytes, length, &staged, &detail);
    ym2610_candidate_destroy(staged);
    *allocation_points = scope.points();
    *lifetime_balance = scope.lifetime_balance();
    return status;
}

extern "C" ym2610_candidate_status
ym2610_candidate_test_state_capture_failpoint(
    const ym2610_candidate *candidate, uint8_t *destination, size_t capacity,
    size_t *written, size_t fail_at, size_t *allocation_points,
    int64_t *lifetime_balance) {
    if (allocation_points == nullptr || lifetime_balance == nullptr)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    allocation_scope scope(fail_at);
    const ym2610_candidate_status status =
        ym2610_candidate_state_capture(candidate, destination, capacity, written);
    *allocation_points = scope.points();
    *lifetime_balance = scope.lifetime_balance();
    return status;
}

extern "C" ym2610_candidate_status
ym2610_candidate_test_state_rebind_failpoint(
    ym2610_candidate *staged, const ym2610_candidate_callbacks *callbacks,
    void *userdata, size_t fail_at, size_t *allocation_points,
    int64_t *lifetime_balance) {
    if (allocation_points == nullptr || lifetime_balance == nullptr)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    allocation_scope scope(fail_at);
    ym2610_candidate_status status = YM2610_CANDIDATE_EXCEPTION;
    try {
        status = ym2610_candidate_state_rebind(staged, callbacks, userdata);
    } catch (const std::bad_alloc &) {
        status = YM2610_CANDIDATE_NO_MEMORY;
    } catch (...) {
        status = YM2610_CANDIDATE_EXCEPTION;
    }
    *allocation_points = scope.points();
    *lifetime_balance = scope.lifetime_balance();
    return status;
}

extern "C" ym2610_candidate_status
ym2610_candidate_test_invoke_with_failpoint(
    ym2610_candidate_test_operation operation, void *userdata,
    size_t fail_at, int *operation_result, size_t *allocation_points,
    int64_t *lifetime_balance, size_t *requested_bytes,
    size_t *high_water_bytes, uint32_t *failed_site) {
    if (operation == nullptr || operation_result == nullptr ||
        allocation_points == nullptr || lifetime_balance == nullptr ||
        requested_bytes == nullptr || high_water_bytes == nullptr ||
        failed_site == nullptr)
        return YM2610_CANDIDATE_INVALID_ARGUMENT;
    allocation_scope scope(fail_at);
    try {
        *operation_result = operation(userdata);
    } catch (const std::bad_alloc &) {
        *operation_result = -1;
    } catch (...) {
        *operation_result = -2;
    }
    *allocation_points = scope.points();
    *lifetime_balance = scope.lifetime_balance();
    *requested_bytes = scope.requested_bytes();
    *high_water_bytes = scope.high_water_bytes();
    *failed_site = scope.failed_site();
    return YM2610_CANDIDATE_OK;
}
#endif
