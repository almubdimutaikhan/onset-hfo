"""The figures' shared style. No Qt."""

from __future__ import annotations

from pathlib import Path

from onset_review import studycharts


def test_the_series_hues_are_the_validated_pair():
    assert studycharts.SERIES == ("#4F46E5", "#C2410C")
    assert studycharts.SERIES[0].lower() in open(
        Path(__file__).resolve().parents[1] / "onset_review" / "theme.py").read().lower(), \
        "the first hue is the window's accent"
