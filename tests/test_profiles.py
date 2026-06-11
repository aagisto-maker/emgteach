"""Tests for :mod:`emgteach.profiles`.

The most important property is that ``EMG_PROFILE`` reproduces *exactly*
the values that were previously hardcoded across the workers and the
acquisition tab, so that wiring the package to it changes no behaviour.
These tests pin those values and the derived channel schema.
"""

from __future__ import annotations

import pytest

from emgteach import EMG_PROFILE, ChannelInfo, SignalProfile


class TestEmgProfileValues:
    """EMG_PROFILE must equal the pre-refactor hardcoded defaults."""

    def test_filter_and_analysis_defaults(self) -> None:
        p = EMG_PROFILE
        assert p.name == "EMG"
        assert p.sample_frequency == 1000
        assert (p.f_low, p.f_high, p.f_notch, p.f_env) == (20.0, 450.0, 50.0, 5.0)
        assert p.rms_window_ms == 50.0
        assert p.seg_len_s == 1.0
        assert p.overlap == 0.5
        assert p.mvc_percentile == 95.0

    def test_channel_labels_and_dimension(self) -> None:
        p = EMG_PROFILE
        assert p.raw_label == "EMG"
        assert p.filtered_label == "EMG_Filtered"
        assert p.envelope_label == "EMG_Envelope"
        assert p.dimension == "mV"

    def test_display_ranges(self) -> None:
        p = EMG_PROFILE
        assert p.ylim_raw == (-3.3, 3.3)
        assert p.ylim_filtered == (-0.8, 0.8)
        assert p.ylim_envelope == (0.0, 0.5)

    def test_marker_presets(self) -> None:
        # The acquisition tab historically offered exactly these labels.
        assert EMG_PROFILE.marker_presets == (
            "Inicio contracción",
            "Fin contracción",
            "Fatiga",
            "Reposo",
            "Otro…",
        )


class TestFilterKwargs:
    def test_filter_kwargs_matches_fields(self) -> None:
        assert EMG_PROFILE.filter_kwargs() == {
            "f_low": 20.0,
            "f_high": 450.0,
            "f_notch": 50.0,
            "f_env": 5.0,
        }


class TestBuildChannels:
    """build_channels() must reproduce the acquisition worker's schema."""

    def test_reproduces_legacy_channel_list(self) -> None:
        # This is exactly the list the acquisition worker built by hand
        # before the refactor.
        expected = [
            ChannelInfo("EMG", sample_frequency=1000),
            ChannelInfo("EMG_Filtered", sample_frequency=1000),
            ChannelInfo("EMG_Envelope", physical_min=0.0, sample_frequency=1000),
        ]
        assert EMG_PROFILE.build_channels(fs=1000) == expected

    def test_defaults_to_profile_sample_frequency(self) -> None:
        channels = EMG_PROFILE.build_channels()
        assert [c.sample_frequency for c in channels] == [1000, 1000, 1000]

    def test_fs_override_propagates_to_every_channel(self) -> None:
        channels = EMG_PROFILE.build_channels(fs=500)
        assert [c.sample_frequency for c in channels] == [500, 500, 500]

    def test_only_envelope_channel_is_non_negative(self) -> None:
        raw, filtered, envelope = EMG_PROFILE.build_channels()
        assert raw.physical_min == -3.3
        assert filtered.physical_min == -3.3
        assert envelope.physical_min == 0.0


class TestImmutabilityAndValidation:
    def test_profile_is_frozen(self) -> None:
        with pytest.raises(Exception):  # noqa: B017 — FrozenInstanceError
            EMG_PROFILE.f_low = 10.0  # type: ignore[misc]

    def test_inverted_band_raises(self) -> None:
        with pytest.raises(ValueError, match="f_low < f_high"):
            SignalProfile(name="bad", f_low=450.0, f_high=20.0)

    def test_non_positive_sample_frequency_raises(self) -> None:
        with pytest.raises(ValueError, match="sample_frequency"):
            SignalProfile(name="bad", sample_frequency=0)

    def test_non_positive_envelope_cutoff_raises(self) -> None:
        with pytest.raises(ValueError, match="f_env"):
            SignalProfile(name="bad", f_env=0.0)

    def test_overlap_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="overlap"):
            SignalProfile(name="bad", overlap=1.0)

    def test_custom_profile_for_a_new_modality(self) -> None:
        # A hypothetical ECG profile: the whole point of the extension
        # point is that this requires no change anywhere else.
        ecg = SignalProfile(
            name="ECG",
            f_low=0.5,
            f_high=100.0,
            f_notch=50.0,
            f_env=10.0,
            raw_label="ECG",
            filtered_label="ECG_Filtered",
            envelope_label="ECG_Envelope",
        )
        assert ecg.name == "ECG"
        assert ecg.build_channels()[0].label == "ECG"
        assert ecg.filter_kwargs()["f_high"] == 100.0
