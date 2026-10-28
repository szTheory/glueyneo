"""Independent design calculations for the owned MVS PCM converter.

The frequency-response calculation is a direct analytic sum over each FIR
phase. It does not execute the C polyphase accumulator or its ring-buffer code.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path

PHASES = 12
TAPS = 80
SOURCE_RATE_HZ = 500_000
OUTPUT_RATE_HZ = 48_000
SOURCE_NYQUIST_HZ = SOURCE_RATE_HZ // 2
CUTOFF_HZ = 20_000
KAISER_BETA = 5.0
Q30_SCALE = 1 << 30
PASSBAND_EDGE_HZ = 12_000
STOPBAND_CHECK_HZ = 30_000
MAX_PASSBAND_DEVIATION_DB = 1.0
MIN_STOPBAND_REJECTION_DB = 40.0
CANDIDATE_TAPS = (48, 64, 72, 80, 96, 224)
YMFM_FM_ABS_PEAK = 32_768
YMFM_SSG_CHANNEL_PEAK = 16_382
MIXED_SAMPLE_ABS_PEAK = 28_671


def _bessel_i0(value: float) -> float:
    """Modified Bessel I0, using its convergent power series."""
    quarter_square = value * value * 0.25
    total = 1.0
    term = 1.0
    for order in range(1, 80):
        term *= quarter_square / (order * order)
        total += term
        if term <= total * 1e-16:
            break
    return total


def _sinc(value: float) -> float:
    if value == 0.0:
        return 1.0
    argument = math.pi * value
    return math.sin(argument) / argument


def _round_away_from_zero(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if numerator < 0:
        return -((-numerator + denominator // 2) // denominator)
    return (numerator + denominator // 2) // denominator


def _round_float_away_from_zero(value: float) -> int:
    if value < 0.0:
        return -math.floor(-value + 0.5)
    return math.floor(value + 0.5)


def derive_float_bank(taps: int = TAPS, phases: int = PHASES) -> tuple[tuple[float, ...], ...]:
    """Derive normalized Kaiser-windowed fractional-delay sinc phases.

    The cutoff is 20 kHz on a 500 kHz source, giving a normalized Nyquist
    cutoff of 0.08. The midpoint is (taps-1)/2; the half-sample term and phase
    fraction select the causal fractional-delay position used by the design.
    """
    if taps < 2 or taps % 2 != 0 or phases < 1:
        raise ValueError("taps must be positive even and phases must be positive")
    cutoff = CUTOFF_HZ / SOURCE_NYQUIST_HZ
    midpoint = (taps - 1) / 2.0
    window_denominator = _bessel_i0(KAISER_BETA)
    window: list[float] = []
    for tap in range(taps):
        position = 2.0 * tap / (taps - 1) - 1.0
        window.append(
            _bessel_i0(KAISER_BETA * math.sqrt(max(0.0, 1.0 - position * position)))
            / window_denominator
        )

    rows: list[tuple[float, ...]] = []
    for phase in range(phases):
        raw = tuple(
            cutoff
            * _sinc(cutoff * (tap - midpoint + 0.5 - phase / phases))
            * window[tap]
            for tap in range(taps)
        )
        normalization = math.fsum(raw)
        rows.append(tuple(coefficient / normalization for coefficient in raw))
    return tuple(rows)


def derive_q30_bank(taps: int = TAPS, phases: int = PHASES) -> tuple[tuple[int, ...], ...]:
    """Quantize the independent design to signed Q1.30, ties away from zero."""
    floating = derive_float_bank(taps, phases)
    quantized: list[tuple[int, ...]] = []
    for phase, row in enumerate(floating):
        if phases == PHASES and phase >= 7:
            quantized.append(tuple(reversed(quantized[PHASES - phase])))
        else:
            quantized.append(
                tuple(_round_float_away_from_zero(value * Q30_SCALE) for value in row)
            )
    return tuple(quantized)


def read_runtime_q30_bank(source: Path | None = None) -> tuple[tuple[int, ...], ...]:
    """Read the compact owned table and expand its reversed complementary phases."""
    if source is None:
        source = Path(__file__).resolve().parents[2] / "src/mvs/mvs_bus.c"
    text = source.read_text(encoding="utf-8")
    match = re.search(
        r"gn_mvs_pcm_q30_coefficients\[7\]\[80\]\s*=\s*\{(.*?)\n\};",
        text,
        re.DOTALL,
    )
    if match is None:
        raise ValueError("owned Q1.30 table was not found")
    values = [int(value) for value in re.findall(r"-?\d+", match.group(1))]
    if len(values) != 7 * TAPS:
        raise ValueError(f"expected {7 * TAPS} stored coefficients, found {len(values)}")
    stored = tuple(
        tuple(values[row * TAPS : (row + 1) * TAPS]) for row in range(7)
    )
    return tuple(
        stored[phase]
        if phase < 7
        else tuple(reversed(stored[PHASES - phase]))
        for phase in range(PHASES)
    )


@lru_cache(maxsize=64)
def _oscillator(frequency_hz: int, taps: int) -> tuple[tuple[float, float], ...]:
    angular_rate = 2.0 * math.pi * frequency_hz / SOURCE_RATE_HZ
    return tuple(
        (math.cos(angular_rate * tap), math.sin(angular_rate * tap))
        for tap in range(taps)
    )


def _magnitude(coefficients: tuple[float, ...], frequency_hz: int) -> float:
    oscillator = _oscillator(frequency_hz, len(coefficients))
    real = math.fsum(coefficient * oscillator[tap][0]
                     for tap, coefficient in enumerate(coefficients))
    imaginary = -math.fsum(coefficient * oscillator[tap][1]
                           for tap, coefficient in enumerate(coefficients))
    return math.hypot(real, imaginary)


@lru_cache(maxsize=8)
def evaluate_candidate(taps: int) -> dict[str, float | int]:
    """Measure every phase against the frozen analytic response contract.

    Passband samples span DC..12 kHz in 50 Hz steps. Each phase is measured
    against the mean magnitude across phases at 1 kHz. The stopband result is
    the worst phase at 30 kHz relative to that same in-band reference.
    """
    floating_bank = derive_float_bank(taps, PHASES)
    q30_bank = derive_q30_bank(taps, PHASES)
    reference = math.fsum(
        _magnitude(row, 1_000) for row in floating_bank
    ) / PHASES
    worst_deviation = 0.0
    for frequency in range(0, PASSBAND_EDGE_HZ + 1, 50):
        for row in floating_bank:
            magnitude = _magnitude(row, frequency)
            deviation = abs(20.0 * math.log10(magnitude / reference))
            worst_deviation = max(worst_deviation, deviation)
    worst_stop_magnitude = max(
        _magnitude(row, STOPBAND_CHECK_HZ) for row in floating_bank
    )
    rejection = -20.0 * math.log10(worst_stop_magnitude / reference)
    phase_l1 = max(math.fsum(abs(value) for value in row) / Q30_SCALE
                   for row in q30_bank)
    quantization_error = max(
        MIXED_SAMPLE_ABS_PEAK
        * math.fsum(
            abs(q30_bank[phase][tap] / Q30_SCALE - floating_bank[phase][tap])
            for tap in range(taps)
        )
        for phase in range(PHASES)
    )
    return {
        "taps": taps,
        "passband_deviation_db": worst_deviation,
        "stopband_rejection_db": rejection,
        "macs_per_stereo_frame": 2 * taps,
        "max_phase_l1": phase_l1,
        "quantization_error_s16": quantization_error,
    }


def candidate_passes(metrics: dict[str, float | int]) -> bool:
    return (
        metrics["passband_deviation_db"] <= MAX_PASSBAND_DEVIATION_DB
        and metrics["stopband_rejection_db"] >= MIN_STOPBAND_REJECTION_DB
    )


def select_shortest_candidate(candidates: tuple[int, ...] = CANDIDATE_TAPS) -> int:
    passing = [taps for taps in candidates if candidate_passes(evaluate_candidate(taps))]
    if not passing:
        raise ValueError("no evaluated FIR candidate passes the frozen criteria")
    return min(passing)


def output_frame_count(source_frames: int) -> int:
    """Count outputs for a zero-origin, causal 12/125 converter stream."""
    if source_frames < 0:
        raise ValueError("source frame count must not be negative")
    return source_frames * 12 // 125


def mix_channels(fm_left: int, fm_right: int, ssg_mono: int) -> tuple[int, int]:
    """Preserve FM stereo and add mono SSG at the frozen 1/2 FM, 1/4 total mix."""
    return (
        _round_away_from_zero(2 * fm_left + ssg_mono, 4),
        _round_away_from_zero(2 * fm_right + ssg_mono, 4),
    )


def alias_frequency(source_hz: int, output_rate_hz: int = OUTPUT_RATE_HZ) -> int:
    """Return the folded output-band frequency of an unfiltered sampled tone."""
    if source_hz < 0 or output_rate_hz <= 0:
        raise ValueError("frequencies and output rate must be nonnegative/positive")
    folded = source_hz % output_rate_hz
    if folded > output_rate_hz // 2:
        folded = output_rate_hz - folded
    return folded


def headroom_bounds() -> dict[str, int | float]:
    """Return the source-derived conservative mixer and Q1.30 bounds."""
    ssg_peak = 3 * YMFM_SSG_CHANNEL_PEAK
    numerator_peak = 2 * YMFM_FM_ABS_PEAK + ssg_peak
    mixed_peak = _round_away_from_zero(numerator_peak, 4)
    return {
        "fm_abs_peak": YMFM_FM_ABS_PEAK,
        "ssg_mono_peak": ssg_peak,
        "mixer_numerator_peak": numerator_peak,
        "mixed_abs_peak": mixed_peak,
        "generic_l1_bound": 2,
        "int64_accumulator_bound": mixed_peak * 2 * Q30_SCALE,
    }


def group_delay(taps: int = TAPS) -> dict[str, float]:
    midpoint = (taps - 1) / 2.0
    return {
        "source_samples": midpoint,
        "microseconds": midpoint * 1_000_000.0 / SOURCE_RATE_HZ,
        "output_frames": midpoint * OUTPUT_RATE_HZ / SOURCE_RATE_HZ,
    }


def main() -> None:
    print("taps passband_dev_db stop_rejection_db stereo_MAC/frame")
    for taps in CANDIDATE_TAPS:
        metrics = evaluate_candidate(taps)
        print(
            f"{taps:4d} {metrics['passband_deviation_db']:14.6f} "
            f"{metrics['stopband_rejection_db']:18.6f} "
            f"{metrics['macs_per_stereo_frame']:18d}"
        )
    print(f"selected taps: {select_shortest_candidate()}")
    print(f"500000 source frames: {output_frame_count(500_000)} output frames")


if __name__ == "__main__":
    main()
