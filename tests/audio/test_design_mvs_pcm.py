#!/usr/bin/env python3
"""Independent mathematical checks for the native MVS PCM design."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools/audio"))

import design_mvs_pcm as design


class MvsPcmDesignTests(unittest.TestCase):
    def test_derived_filter_bank_matches_owned_q30_coefficients(self) -> None:
        expected = design.derive_q30_bank()
        actual = design.read_runtime_q30_bank()
        self.assertEqual(len(expected), 12)
        self.assertTrue(all(len(phase) == 80 for phase in expected))
        self.assertEqual(expected, actual)

    def test_selected_80_tap_candidate_meets_frozen_response_contract(self) -> None:
        selected = design.evaluate_candidate(80)
        self.assertLessEqual(selected["passband_deviation_db"], 1.0)
        self.assertGreaterEqual(selected["stopband_rejection_db"], 40.0)
        self.assertAlmostEqual(selected["passband_deviation_db"], 0.248329, delta=0.002)
        self.assertAlmostEqual(selected["stopband_rejection_db"], 51.349654, delta=0.02)
        self.assertEqual(selected["macs_per_stereo_frame"], 160)
        reference = design.evaluate_candidate(224)
        self.assertEqual(reference["macs_per_stereo_frame"], 448)
        shorter = design.evaluate_candidate(48)
        self.assertFalse(
            shorter["passband_deviation_db"] <= 1.0
            and shorter["stopband_rejection_db"] >= 40.0
        )
        self.assertEqual(design.select_shortest_candidate(), 80)

    def test_rational_count_and_ties_away_channel_mix(self) -> None:
        self.assertEqual(design.output_frame_count(500_000), 48_000)
        self.assertEqual(design.output_frame_count(125), 12)
        self.assertEqual(design.mix_channels(10_000, -10_000, 4_000), (6_000, -4_000))
        self.assertEqual(design.mix_channels(1, -1, 0), (1, -1))
        self.assertEqual(design.alias_frequency(30_000), 18_000)

    def test_filter_delay_and_integer_headroom(self) -> None:
        delay = design.group_delay()
        self.assertEqual(delay["source_samples"], 39.5)
        self.assertAlmostEqual(delay["microseconds"], 79.0)
        self.assertAlmostEqual(delay["output_frames"], 3.792)
        bounds = design.headroom_bounds()
        self.assertEqual(bounds["ssg_mono_peak"], 49_146)
        self.assertEqual(bounds["mixer_numerator_peak"], 114_682)
        self.assertEqual(bounds["mixed_abs_peak"], 28_671)
        self.assertLess(bounds["int64_accumulator_bound"], 1 << 63)
        selected = design.evaluate_candidate(80)
        self.assertLess(selected["max_phase_l1"], 2.0)
        self.assertLess(selected["quantization_error_s16"], 0.002)


if __name__ == "__main__":
    unittest.main(verbosity=2)
