# HFO / epileptiform evidence report -- sub-17 (None, run 01)

*Report v1, pipeline 0.1.0, generated 2026-10-12T03:41:04+00:00.*

> Decision support for research use. This report presents detector output and the
> signal windows behind it. It contains no diagnosis and no treatment recommendation.

## Summary

2 detectors ran on sub-17 (None, run 01), 60 s of recording, 42 channels. Highest event rate: FPR1-FPR2 (rms 81.0/min, line_length 62.0/min). 3 of the leading channels are ranked very differently by the two detectors. This report presents evidence windows and rates; it contains no diagnosis and no recommendation.

## Recording

- source: `openneuro:ds003498`
- 42 channels analysed, 2000.0 Hz, 0.0-60.0 s of the original recording

## Findings

### FPR1-FPR2
- **rms**: 81.0 events/min (95% CI 64.3-99.6, n=81), rank 1
- **line_length**: 62.0 events/min (95% CI 47.5-78.4, n=62), rank 1
- interictal discharges: 2.0/min; 2% of its HFOs coincide with one
- evidence windows: FPR1-FPR2 0.000-0.043 s [sub-17|FPR1-FPR2|line_length|0.000]; FPR1-FPR2 2.327-2.426 s [sub-17|FPR1-FPR2|rms|2.327]; FPR1-FPR2 29.124-29.312 s [sub-17|FPR1-FPR2|line_length|29.124]; FPR1-FPR2 29.126-29.310 s [sub-17|FPR1-FPR2|rms|29.125]; FPR1-FPR2 47.828-47.967 s [sub-17|FPR1-FPR2|line_length|47.828]; FPR1-FPR2 47.840-47.968 s [sub-17|FPR1-FPR2|rms|47.840]

### FPR8-FPR9
- **rms**: 66.0 events/min (95% CI 51.0-82.9, n=66), rank 2
- **line_length**: 50.0 events/min (95% CI 37.1-64.9, n=50), rank 4
- interictal discharges: 14.0/min; 15% of its HFOs coincide with one
- evidence windows: FPR8-FPR9 0.000-0.035 s [sub-17|FPR8-FPR9|rms|0.000]; FPR8-FPR9 2.310-2.492 s [sub-17|FPR8-FPR9|rms|2.311]; FPR8-FPR9 21.608-21.760 s [sub-17|FPR8-FPR9|line_length|21.608]; FPR8-FPR9 43.249-43.405 s [sub-17|FPR8-FPR9|line_length|43.249]; FPR8-FPR9 45.110-45.206 s [sub-17|FPR8-FPR9|line_length|45.110]; FPR8-FPR9 45.112-45.284 s [sub-17|FPR8-FPR9|rms|45.111]

### FPR10-FPR11
- **rms**: 64.0 events/min (95% CI 49.3-80.7, n=64), rank 3
- **line_length**: 58.0 events/min (95% CI 44.0-73.9, n=58), rank 2
- interictal discharges: 21.0/min; 29% of its HFOs coincide with one
- evidence windows: FPR10-FPR11 33.794-33.871 s [sub-17|FPR10-FPR11|rms|33.794]; FPR10-FPR11 33.801-33.859 s [sub-17|FPR10-FPR11|line_length|33.801]; FPR10-FPR11 43.226-43.408 s [sub-17|FPR10-FPR11|rms|43.227]; FPR10-FPR11 43.226-43.406 s [sub-17|FPR10-FPR11|line_length|43.226]; FPR10-FPR11 49.079-49.276 s [sub-17|FPR10-FPR11|line_length|49.079]; FPR10-FPR11 49.080-49.274 s [sub-17|FPR10-FPR11|rms|49.080]

### FPR9-FPR10
- **rms**: 60.0 events/min (95% CI 45.7-76.2, n=60), rank 5
- **line_length**: 48.0 events/min (95% CI 35.3-62.6, n=48), rank 8
- interictal discharges: 17.0/min; 23% of its HFOs coincide with one
- evidence windows: FPR9-FPR10 21.622-21.812 s [sub-17|FPR9-FPR10|rms|21.622]; FPR9-FPR10 21.622-21.810 s [sub-17|FPR9-FPR10|line_length|21.622]; FPR9-FPR10 33.794-33.874 s [sub-17|FPR9-FPR10|line_length|33.794]; FPR9-FPR10 39.133-39.234 s [sub-17|FPR9-FPR10|line_length|39.133]; FPR9-FPR10 39.134-39.232 s [sub-17|FPR9-FPR10|rms|39.135]; FPR9-FPR10 49.071-49.270 s [sub-17|FPR9-FPR10|rms|49.071]

## Where the detectors disagree

- **FAR8-FAR9** -- rms: 4, line_length: 24. the two detectors' ranks differ by 18 places; the report states both and resolves neither
  - evidence: FAR8-FAR9 12.798-12.971 s [sub-17|FAR8-FAR9|rms|12.799]; FAR8-FAR9 19.471-19.666 s [sub-17|FAR8-FAR9|line_length|19.471]
- **FPR5-FPR6** -- rms: 22, line_length: 3. the two detectors' ranks differ by 19 places; the report states both and resolves neither
  - evidence: FPR5-FPR6 1.663-1.846 s [sub-17|FPR5-FPR6|line_length|1.663]; FPR5-FPR6 12.185-12.244 s [sub-17|FPR5-FPR6|rms|12.185]
- **FPR13-FPR14** -- rms: 10, line_length: 5. the two detectors' ranks differ by 6 places; the report states both and resolves neither
  - evidence: FPR13-FPR14 21.584-21.706 s [sub-17|FPR13-FPR14|rms|21.584]; FPR13-FPR14 21.598-21.761 s [sub-17|FPR13-FPR14|line_length|21.599]

## Data quality

- slice 0-60 s of the original recording; all times reported by this pipeline are in original-recording seconds
- 0 channels flagged bad in channels.tsv (white matter, CSF, outside brain, or noisy) and excluded
- mains frequency 50 Hz (ds003498)
- expert HFO markings: 2861 events on 37 reviewed channels (FAR1-FAR2, FAR10-FAR11, FAR11-FAR12, FAR12-FAR13, FAR13-FAR14, FAR14-FAR15, ...)
- only those channels were annotated, so a detection elsewhere is unjudged rather than wrong; evaluation is restricted to them
- rms: 241 of 1922 accepted events (13%) coincide with an interictal discharge on the same channel — 241.0/min against 1681.0/min for the rest, summed over all channels. The two are reported separately because nothing here can tell a physiological ripple from an epileptic one, and merging them hides that.
- line_length: 230 of 1528 accepted events (15%) coincide with an interictal discharge on the same channel — 230.0/min against 1298.0/min for the rest, summed over all channels. The two are reported separately because nothing here can tell a physiological ripple from an epileptic one, and merging them hides that.
- Discharge co-occurrence is a proxy for the physiological/epileptic distinction, not a label for it: no public archive marks which ripples were physiological, so neither sub-population should be read as one or the other.
- All 39 contacts passed the quality checks.
- rms: 1961 candidate events, 39 rejected by artifact validation (in-band spectral peak only 4.0 dB above the 1/f background (< 4 dB): 3, in-band spectral peak only 1.6 dB above the 1/f background (< 4 dB): 3, in-band spectral peak only 2.9 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 3.4 dB above the 1/f background (< 4 dB): 2, only 2.0 cycles (< 2): 2, in-band spectral peak only 3.9 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 3.3 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 3.5 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 1.1 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 3.7 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 1.3 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 3.0 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 3.1 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only -0.7 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.3 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 3.2 dB above the 1/f background (< 4 dB): 1, only 1.6 cycles (< 2): 1, in-band spectral peak only 2.5 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only -0.0 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 1.8 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.6 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 3.6 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only -0.8 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.0 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 1.9 dB above the 1/f background (< 4 dB): 1)
- line_length: 1549 candidate events, 21 rejected by artifact validation (in-band spectral peak only 3.7 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 3.0 dB above the 1/f background (< 4 dB): 3, in-band spectral peak only 3.9 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 3.1 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 4.0 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 1.3 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 1.7 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 3.3 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.7 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 1.0 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.9 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only -0.7 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 3.8 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.1 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.8 dB above the 1/f background (< 4 dB): 1)
- rates are events per minute over the analysed window; confidence intervals assume a Poisson process

## Method

- kept 42 intracranial channels; dropped 0 non-brain channels (DC/trigger/ECG/misc)
- high-pass 1 Hz (windowed FIR of 6601 taps (3.30 s), zero phase, MNE's automatic transition band)
- notch 50 Hz (from the dataset) + harmonics (50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850 Hz, 2 Hz wide)
- bipolar montage: 39 pairs of neighbouring contacts
- detectors: rms, line_length (see docs/METHODS.md)
- configuration: {"preprocess": {"line_freq": null, "notch": true, "bipolar": true, "highpass": 1.0, "lowpass": null, "notch_width": 2.0, "notch_harmonics": true, "average_reference": false, "resample": null, "drop_bads": true, "exclude": [], "filter_method": "fir", "iir_order": 4, "filter_phase": "zero", "transition_bandwidth": null, "reference": null, "modality": "auto", "grid_columns": [], "annotate_muscle": false, "muscle_z": 4.0, "regress_channels": [], "ica": false, "ica_n_components": null, "ica_method": "fastica", "ica_exclude": [], "ica_seed": 97, "annotate_amplitude": false, "amplitude_ptp_uv": null}, "rms": {"band": [80.0, 250.0], "rms_window_ms": 3.0, "threshold_sd": 2.0, "extend_sd": 2.0, "peak_threshold_sd": 2.0, "min_peaks": 6, "min_duration_ms": 6.0, "max_duration_ms": 200.0, "merge_gap_ms": 10.0, "baseline": "robust"}, "line_length": {"band": [80.0, 250.0], "rms_window_ms": 3.0, "threshold_sd": 2.0, "extend_sd": 2.0, "peak_threshold_sd": 2.0, "min_peaks": 6, "min_duration_ms": 6.0, "max_duration_ms": 200.0, "merge_gap_ms": 10.0, "baseline": "robust"}, "hilbert": {"band": [80.0, 250.0], "rms_window_ms": 3.0, "threshold_sd": 5.0, "extend_sd": 2.0, "peak_threshold_sd": 2.0, "min_peaks": 6, "min_duration_ms": 6.0, "max_duration_ms": 200.0, "merge_gap_ms": 10.0, "baseline": "robust"}, "short_time_energy": {"band": [80.0, 250.0], "rms_window_ms": 3.0, "threshold_sd": 5.0, "extend_sd": 2.0, "peak_threshold_sd": 2.0, "min_peaks": 6, "min_duration_ms": 6.0, "max_duration_ms": 200.0, "merge_gap_ms": 10.0, "baseline": "robust"}, "spikes": {"band": [5.0, 60.0], "threshold_sd": 6.0, "slope_sd": 5.0, "min_duration_ms": 10.0, "max_duration_ms": 200.0, "refractory_ms": 200.0, "max_raw_jump_sd": 10.0}, "validation": {"min_peak_prominence_db": 4.0, "max_low_band_sd": 8.0, "min_cycles": 2.0, "scalp_max_concurrent_fraction": 0.0}, "quality": {"flat_uv": 0.5, "max_clipped_fraction": 0.01, "max_line_fraction": 0.3, "max_hf_ratio_sd": 6.0, "bursty_ratio": 1.2, "max_amplitude_sd": 6.0, "amplitude_outlier_ratio": 3.0, "segment_s": 1.0, "segment_jump_sd": 100.0, "segment_ceiling_uv": 5000.0, "max_bad_segment_fraction": 0.5}, "check_quality": true, "rate_window_s": 60.0, "top_k": 5, "disagreement_ranks": 5}

## Limitations

- prototype: thresholds come from the literature, checked on synthetic data and against expert markings on 20 subjects of ds003498; not validated on a clinical cohort
- this recording carries expert HFO markings, so the detectors can be scored on it (python -m onset_hfo.cli benchmark); agreement with those markings is not accuracy, because the reference is another detector's validated output
- event rate is not a diagnosis: physiological ripples occur in healthy tissue, particularly in mesial temporal and occipital regions
- a single short window of a single patient; nothing here generalises
- bipolar pairs are formed from consecutive contact numbers, which on a grid is not always spatial adjacency

## Data citation

Fedele T, Burnos S, Boran E, Krayenbuehl N, Hilfiker P, Grunwald T, Sarnthein J. Resection of high frequency oscillations predicts seizure outcome in the individual patient. Scientific Reports 7:13836 (2017). doi:10.1038/s41598-017-13064-1 -- BIDS conversion by A. Zhang (mne-hfo), OpenNeuro ds003498, CC0.
