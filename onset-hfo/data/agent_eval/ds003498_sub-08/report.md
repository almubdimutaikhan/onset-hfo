# HFO / epileptiform evidence report -- sub-08 (None, run 01)

*Report v1, pipeline 0.1.0, generated 2026-10-12T03:40:38+00:00.*

> Decision support for research use. This report presents detector output and the
> signal windows behind it. It contains no diagnosis and no treatment recommendation.

## Summary

2 detectors ran on sub-08 (None, run 01), 60 s of recording, 64 channels. Highest event rate: PHR1-PHR2 (rms 100.7/min, line_length 91.5/min). 1 of the leading channels are ranked very differently by the two detectors. This report presents evidence windows and rates; it contains no diagnosis and no recommendation.

## Recording

- source: `openneuro:ds003498`
- 64 channels analysed, 2000.0 Hz, 0.0-60.0 s of the original recording

## Findings

### PHR1-PHR2
- **rms**: 100.7 events/min (95% CI 81.8-121.5, n=99), rank 1
- **line_length**: 91.5 events/min (95% CI 73.6-111.4, n=90), rank 1
- interictal discharges: 0.0/min; 0% of its HFOs coincide with one
- evidence windows: PHR1-PHR2 47.328-47.435 s [sub-08|PHR1-PHR2|rms|47.328]; PHR1-PHR2 47.564-47.609 s [sub-08|PHR1-PHR2|rms|47.565]; PHR1-PHR2 51.766-51.933 s [sub-08|PHR1-PHR2|line_length|51.766]; PHR1-PHR2 53.972-54.143 s [sub-08|PHR1-PHR2|line_length|53.972]; PHR1-PHR2 56.929-57.037 s [sub-08|PHR1-PHR2|rms|56.929]; PHR1-PHR2 56.931-57.020 s [sub-08|PHR1-PHR2|line_length|56.931]

### AR1-AR2
- **rms**: 81.1 events/min (95% CI 63.9-100.2, n=77), rank 2
- **line_length**: 64.2 events/min (95% CI 49.1-81.4, n=61), rank 4
- interictal discharges: 0.0/min; 0% of its HFOs coincide with one
- evidence windows: AR1-AR2 53.403-53.562 s [sub-08|AR1-AR2|rms|53.403]; AR1-AR2 53.404-53.512 s [sub-08|AR1-AR2|line_length|53.404]; AR1-AR2 53.579-53.779 s [sub-08|AR1-AR2|line_length|53.579]; AR1-AR2 53.580-53.752 s [sub-08|AR1-AR2|rms|53.580]; AR1-AR2 57.854-57.938 s [sub-08|AR1-AR2|rms|57.853]; AR1-AR2 57.854-57.938 s [sub-08|AR1-AR2|line_length|57.854]

### ECR2-ECR3
- **rms**: 66.5 events/min (95% CI 50.9-84.3, n=61), rank 3
- **line_length**: 68.7 events/min (95% CI 52.8-86.8, n=63), rank 2
- interictal discharges: 1.1/min; 2% of its HFOs coincide with one
- evidence windows: ECR2-ECR3 42.140-42.195 s [sub-08|ECR2-ECR3|rms|42.139]; ECR2-ECR3 42.142-42.196 s [sub-08|ECR2-ECR3|line_length|42.142]; ECR2-ECR3 42.210-42.287 s [sub-08|ECR2-ECR3|rms|42.209]; ECR2-ECR3 58.512-58.540 s [sub-08|ECR2-ECR3|line_length|58.512]; ECR2-ECR3 58.611-58.646 s [sub-08|ECR2-ECR3|line_length|58.611]; ECR2-ECR3 58.772-58.859 s [sub-08|ECR2-ECR3|rms|58.773]

### ECL6-ECL7
- **rms**: 66.0 events/min (95% CI 51.0-82.9, n=66), rank 4
- **line_length**: 66.0 events/min (95% CI 51.0-82.9, n=66), rank 3
- interictal discharges: 0.0/min; 0% of its HFOs coincide with one
- evidence windows: ECL6-ECL7 48.866-48.998 s [sub-08|ECL6-ECL7|rms|48.867]; ECL6-ECL7 48.866-48.967 s [sub-08|ECL6-ECL7|line_length|48.866]; ECL6-ECL7 52.636-52.708 s [sub-08|ECL6-ECL7|line_length|52.636]; ECL6-ECL7 52.962-53.019 s [sub-08|ECL6-ECL7|rms|52.962]; ECL6-ECL7 56.470-56.582 s [sub-08|ECL6-ECL7|rms|56.469]; ECL6-ECL7 56.470-56.553 s [sub-08|ECL6-ECL7|line_length|56.469]

### AR2-AR3
- **rms**: 63.0 events/min (95% CI 48.4-79.5, n=63), rank 5
- **line_length**: 64.0 events/min (95% CI 49.3-80.7, n=64), rank 6
- interictal discharges: 0.0/min; 0% of its HFOs coincide with one
- evidence windows: AR2-AR3 51.760-51.819 s [sub-08|AR2-AR3|rms|51.760]; AR2-AR3 51.760-51.820 s [sub-08|AR2-AR3|line_length|51.760]; AR2-AR3 53.982-54.034 s [sub-08|AR2-AR3|line_length|53.982]; AR2-AR3 54.199-54.238 s [sub-08|AR2-AR3|rms|54.199]; AR2-AR3 56.956-56.998 s [sub-08|AR2-AR3|line_length|56.956]; AR2-AR3 56.958-56.996 s [sub-08|AR2-AR3|rms|56.958]

## Where the detectors disagree

- **PHL2-PHL3** -- rms: 10, line_length: 5. the two detectors' ranks differ by 5 places; the report states both and resolves neither
  - evidence: PHL2-PHL3 24.693-24.716 s [sub-08|PHL2-PHL3|rms|24.693]; PHL2-PHL3 24.730-24.748 s [sub-08|PHL2-PHL3|rms|24.730]

## Data quality

- slice 0-60 s of the original recording; all times reported by this pipeline are in original-recording seconds
- 0 channels flagged bad in channels.tsv (white matter, CSF, outside brain, or noisy) and excluded
- mains frequency 50 Hz (ds003498)
- expert HFO markings: 724 events on 24 reviewed channels (AL1-AL2, AL2-AL3, AL3-AL4, AR1-AR2, AR2-AR3, AR3-AR4, ...)
- only those channels were annotated, so a detection elsewhere is unjudged rather than wrong; evaluation is restricted to them
- rms: 3 of 1115 accepted events (0%) coincide with an interictal discharge on the same channel — 3.0/min against 1112.0/min for the rest, summed over all channels. The two are reported separately because nothing here can tell a physiological ripple from an epileptic one, and merging them hides that.
- line_length: 4 of 876 accepted events (0%) coincide with an interictal discharge on the same channel — 4.0/min against 872.0/min for the rest, summed over all channels. The two are reported separately because nothing here can tell a physiological ripple from an epileptic one, and merging them hides that.
- Discharge co-occurrence is a proxy for the physiological/epileptic distinction, not a label for it: no public archive marks which ripples were physiological, so neither sub-population should be read as one or the other.
- 3 analysed but flagged (3 hf active): AR1-AR2, PHL1-PHL2, PHL2-PHL3 — look at these on the trace before reading their rank, because this cannot tell a noisy amplifier from a contact full of real ripples. 0.5% of contact-seconds rejected; each contact's rate is over the time that survived.
- rms: 1263 candidate events, 148 rejected by artifact validation (inside a rejected segment (56-57 s): 18, inside a rejected segment (52-53 s): 11, in-band spectral peak only 3.6 dB above the 1/f background (< 4 dB): 10, in-band spectral peak only 3.5 dB above the 1/f background (< 4 dB): 9, inside a rejected segment (51-52 s): 7, in-band spectral peak only 3.8 dB above the 1/f background (< 4 dB): 6, in-band spectral peak only 3.9 dB above the 1/f background (< 4 dB): 6, in-band spectral peak only 3.4 dB above the 1/f background (< 4 dB): 5, in-band spectral peak only 3.3 dB above the 1/f background (< 4 dB): 5, in-band spectral peak only 2.7 dB above the 1/f background (< 4 dB): 5, in-band spectral peak only 3.2 dB above the 1/f background (< 4 dB): 5, in-band spectral peak only 1.9 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 3.7 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 3.0 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 4.0 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 2.6 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 2.9 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 2.5 dB above the 1/f background (< 4 dB): 3, in-band spectral peak only 2.2 dB above the 1/f background (< 4 dB): 3, only 1.9 cycles (< 2): 3, only 2.0 cycles (< 2): 2, in-band spectral peak only 1.6 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only -0.5 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 2.8 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 2.0 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 1.3 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 0.5 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 1.8 dB above the 1/f background (< 4 dB): 1, only 1.6 cycles (< 2): 1, in-band spectral peak only 1.1 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 3.1 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 0.9 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 0.7 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 1.4 dB above the 1/f background (< 4 dB): 1, only 1.8 cycles (< 2): 1, in-band spectral peak only -1.2 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only -1.4 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 0.8 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.1 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.3 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.4 dB above the 1/f background (< 4 dB): 1)
- line_length: 952 candidate events, 76 rejected by artifact validation (inside a rejected segment (56-57 s): 17, inside a rejected segment (52-53 s): 10, inside a rejected segment (51-52 s): 6, in-band spectral peak only 2.6 dB above the 1/f background (< 4 dB): 5, in-band spectral peak only 3.9 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 1.7 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 3.8 dB above the 1/f background (< 4 dB): 4, in-band spectral peak only 3.5 dB above the 1/f background (< 4 dB): 3, in-band spectral peak only 2.0 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 3.7 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 2.4 dB above the 1/f background (< 4 dB): 2, in-band spectral peak only 4.0 dB above the 1/f background (< 4 dB): 2, only 1.7 cycles (< 2): 2, in-band spectral peak only 3.2 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.1 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only -0.5 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 1.6 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.7 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 0.1 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 1.8 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 1.0 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 0.2 dB above the 1/f background (< 4 dB): 1, only 1.6 cycles (< 2): 1, only 1.8 cycles (< 2): 1, in-band spectral peak only 2.3 dB above the 1/f background (< 4 dB): 1, in-band spectral peak only 2.8 dB above the 1/f background (< 4 dB): 1)
- rates are events per minute over the analysed window; confidence intervals assume a Poisson process

## Method

- kept 64 intracranial channels; dropped 0 non-brain channels (DC/trigger/ECG/misc)
- high-pass 1 Hz (windowed FIR of 6601 taps (3.30 s), zero phase, MNE's automatic transition band)
- notch 50 Hz (from the dataset) + harmonics (50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850 Hz, 2 Hz wide)
- bipolar montage: 56 pairs of neighbouring contacts
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
