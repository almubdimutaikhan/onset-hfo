"""Review, answer first: the headline, its channels, and review mode.

The redesign's second step. What has to hold:

* the headline says the answer in the ranking's own whole numbers, and
  counts the channels tied with the busiest one without counting the busiest
  itself; the case's interictal sentence does the same;
* the busiest channel and those tied with it are chips that take the
  ranking, and with it the trace, to that channel; the trend strip is folded
  until asked for, and the choice is remembered;
* MNE's "Loading…" bar goes once the trace has loaded;
* review mode shows the events list's event full screen, records A / D / U
  through the list (under the reader's name, advancing), counts what is
  judged over the list as filtered, and lets go of the list when it closes.
"""

from __future__ import annotations

import os
import re

import pytest

from onset_review.session import ReviewRequest, session_from_recording

pytest.importorskip("qtpy.QtWidgets", reason="the review extra is not installed")


@pytest.fixture(scope="module")
def qapp():
    from qtpy import QtWidgets

    pytest.importorskip("mne_qt_browser", reason="the review extra is not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("MNE_BROWSER_BACKEND", "qt")
    yield QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("ONSET_REVIEW_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ONSET_REVIEW_READS", str(tmp_path / "reads"))
    return tmp_path


def _settle(app, n=10):
    from qtpy.QtCore import QThread

    for _ in range(n):
        app.processEvents()
        QThread.msleep(15)


def _request(recording):
    return ReviewRequest(dataset="", subject="synthetic", t_start=0.0,
                         t_stop=float(recording.duration), detectors=("rms",))


@pytest.fixture
def opened(qapp, recording, config, monkeypatch):
    """The application with the synthetic recording open in the page window."""
    from onset_review import launcher
    from onset_review.app import _Review, build_parser

    monkeypatch.setattr(launcher, "load_with_progress",
                        lambda request, cache_dir=None, parent=None:
                        session_from_recording(recording, request))
    review = _Review(qapp, None, False, build_parser().parse_args([]))
    review._open_request(_request(recording))
    _settle(qapp)
    yield review
    mode = getattr(review.parts.pages, "review_mode", None)
    if mode is not None:
        try:
            mode.close()
        except RuntimeError:
            pass
    review.parts.panels["console"].clear_user_variables()
    review.parts.host.close()
    _settle(qapp)


# -- the sentence ----------------------------------------------------------------------------
def test_the_headline_uses_whole_numbers_and_does_not_count_the_leader(recording):
    session = session_from_recording(recording, _request(recording))
    caveat = session.caveat()
    leader = session.leader
    if not leader.get("distinguishable"):
        pytest.skip("the synthetic window has no leader that stands out")
    assert caveat.startswith(f"{leader['leader']} stands out: ")
    assert not re.search(r"\d\.\d", caveat), "no decimals the ranking does not print"
    low, high = leader["leader_ci"]
    assert f"(interval {low:.0f}–{high:.0f})" in caveat
    others = session.tied_with_leader()
    assert leader["leader"] not in others
    assert others == [c for c in session.candidates if c != leader["leader"]]
    if others:
        assert f"{len(others)} other channel" in caveat
    else:
        assert "No other channel's interval overlaps it." in caveat


def test_the_case_sentence_does_not_count_the_busiest_among_its_ties():
    import pandas as pd

    from onset_review.caseinterictal import InterictalResult

    fields = InterictalResult.__dataclass_fields__
    values = {name: None for name in fields}
    values.update(
        table=pd.DataFrame({"channel": ["LA1", "LA2", "LB1"], "tied": [True, True, False]}),
        leader={"available": True, "distinguishable": True, "leader": "LA1",
                "leader_rate_per_min": 12.0, "leader_ci": (9.0, 15.0)},
        n_segments=2, minutes=4.0, settings={})
    statement = InterictalResult(**values).statement()
    assert "1 other channel cannot be told apart from it: LA2." in statement
    assert "LA1, LA2" not in statement


# -- the headline on the page --------------------------------------------------------------
def test_the_answer_comes_first_with_its_channels_as_chips(qapp, opened):
    pages = opened.parts.pages
    session = opened.parts.session
    pages.show_page("recording")
    assert pages.leader.text() == session.caveat()
    leader = session.leader.get("leader")
    assert list(pages.leader_chips) == [leader] + session.tied_with_leader()
    other = session.findings["channel"].iloc[-1]
    opened.parts.panels["findings"].select_channel(other)
    pages.side.setCurrentIndex(1)
    pages.leader_chips[leader].click()
    assert opened.parts.panels["findings"].selected_channel() == leader
    assert pages.side.currentWidget() is opened.parts.panels["findings"]


def test_the_trend_is_folded_until_asked_for_and_remembered(qapp, opened, recording):
    pages = opened.parts.pages
    assert not pages.trend_toggle.isChecked()
    assert opened.parts.panels["trends"].isHidden()
    pages.trend_toggle.setChecked(True)
    assert not opened.parts.panels["trends"].isHidden()
    opened._rerun(threshold_sd=5.0)
    _settle(qapp)
    assert opened.parts.pages.trend_toggle.isChecked(), "remembered across a rebuild"


def test_the_loading_bar_goes_once_the_trace_has_loaded(qapp):
    from qtpy.QtWidgets import QLabel, QMainWindow, QProgressBar

    from onset_review.window import hide_load_bar_when_done

    class Browser(QMainWindow):
        pass

    figure = Browser()
    figure.mne = type("State", (), {})()
    figure.mne.load_progressbar, figure.mne.load_prog_label = QProgressBar(), QLabel()
    figure.mne.data_precomputed = False
    figure.statusBar().addWidget(figure.mne.load_progressbar)
    figure.show()
    assert hide_load_bar_when_done(figure) is False
    assert not figure.mne.load_progressbar.isHidden(), "still loading"
    figure.mne.data_precomputed = True
    figure.statusBar().showMessage("Loading Finished", 5)
    assert figure.mne.load_progressbar.isHidden() and figure.mne.load_prog_label.isHidden()
    figure.close()


# -- review mode ---------------------------------------------------------------------------
def test_review_mode_judges_through_the_events_list_and_moves_on(qapp, opened):
    pages = opened.parts.pages
    events = opened.parts.panels["events"]
    session = opened.parts.session
    session.read.reader = "dr test"
    judged = []
    events.judged.connect(lambda key, verdict: judged.append((key, verdict)))

    mode = pages.open_review_mode(full_screen=False)
    _settle(qapp)
    at, total = mode.position()
    assert at == 1 and total == events.model.rowCount() > 1
    first = events.selected_key()
    assert mode.where.text().startswith(f"Event 1 of {total}")
    assert mode.count.text().startswith(f"0 of {total} judged")
    assert mode.verdict.text() == "Not judged yet"

    mode.judge("agree")
    assert judged[-1] == (first, "agree"), "recorded through the list, so it is saved"
    assert session.read.verdict_of(first) == "agree"
    assert session.read.events[first].reader == "dr test"
    assert mode.position()[0] == 2, "the next event follows"
    assert mode.count.text().startswith(f"1 of {total} judged")

    mode.step(-1)
    assert mode.verdict.text() == "Your read: real"
    assert mode.buttons["agree"].isChecked()
    mode.judge("")
    assert session.read.verdict_of(first) == ""

    mode.judge("disagree")
    assert mode.next_unjudged()
    assert not session.read.verdict_of(events.selected_key())


def test_review_mode_follows_the_list_s_filters_and_lets_go_when_closed(qapp, opened):
    pages = opened.parts.pages
    events = opened.parts.panels["events"]
    leader = opened.parts.session.leader.get("leader")
    events.channel.setCurrentText(leader)
    mode = pages.open_review_mode(full_screen=False)
    _settle(qapp)
    assert mode.position()[1] == events.model.rowCount()
    assert leader in mode.scope.text()
    assert all(events.model.row_value(row, "channel") == leader
               for row in range(events.model.rowCount()))
    mode.close()
    _settle(qapp)
    events.step(+1)            # the list goes on without review mode
    again = pages.open_review_mode(full_screen=False)
    assert again is not mode and again.position()[0] >= 1
    again.close()


def test_review_mode_goes_through_the_channels_a_reader_chooses(qapp, opened):
    from onset_review.reviewmode import ChannelPicker, channel_phrase

    events = opened.parts.panels["events"]
    session = opened.parts.session
    mode = opened.parts.pages.open_review_mode(full_screen=False)
    _settle(qapp)
    counts = events.channel_counts()
    with_events = [name for name, n in counts.items() if n]
    assert len(with_events) >= 3, "the fixture's recording has events on several channels"
    total = mode.position()[1]
    two = with_events[1:3]
    try:
        assert mode.choose_channels(two) == tuple(two)
        at, shown = mode.position()
        assert at == 1 and shown == counts[two[0]] + counts[two[1]] < total
        assert {events.model.row_value(row, "channel")
                for row in range(events.model.rowCount())} == set(two)
        assert channel_phrase(two) in mode.scope.text()
        assert events.channel.currentText() == "2 chosen channels", "the list narrows too"
        times = [events.model.row_value(row, "t_local") for row in range(shown)]
        assert times == sorted(times), "still in time order"
        # One channel is that channel's own entry; every channel is no filter.
        assert mode.choose_channels(two[:1]) == tuple(two[:1])
        assert events.channel.currentText() == two[0]
        assert mode.choose_channels(list(counts)) == ()
        assert mode.position()[1] == total
        assert events.channel.findText("2 chosen channels") < 0, "the old entry is gone"
        # The picker: a tick per channel with its count, and the quick choices.
        picker = ChannelPicker(counts, two, session.candidates)
        assert picker.list.count() == len(counts)
        assert picker.chosen() == two
        picker.quick["all"].click()
        assert picker.chosen() == list(counts)
        picker.quick["none"].click()
        assert picker.chosen() == []
        if "busiest" in picker.quick:
            picker.quick["busiest"].click()
            assert picker.chosen() == [c for c in counts if c in session.candidates]
        picker.quick["with"].click()
        assert picker.chosen() == with_events
        assert f"{counts[two[0]]} event" in picker.list.item(1).text()
    finally:
        mode.close()


def test_review_mode_goes_channel_by_channel_and_keeps_the_event_shown(qapp, opened):
    events = opened.parts.panels["events"]
    pages = opened.parts.pages
    mode = pages.open_review_mode(full_screen=False)
    _settle(qapp)
    try:
        mode.step(+3)
        shown = events.selected_key()
        assert mode.toggle_order() == "channel"
        assert events.selected_key() == shown, "the event on screen stays on screen"
        assert "channel by channel" in mode.scope.text()
        assert mode.buttons["Order: by time"].text() == "Order: by channel"
        rows = [(events.model.row_value(r, "channel"), events.model.row_value(r, "t_local"))
                for r in range(events.model.rowCount())]
        names = events.channel_names()
        assert [names.index(c) for c, _ in rows] == sorted(names.index(c) for c, _ in rows), \
            "channels in the ranking's order"
        for channel in {c for c, _ in rows}:
            times = [t for c, t in rows if c == channel]
            assert times == sorted(times), channel
    finally:
        mode.close()
    _settle(qapp)
    again = pages.open_review_mode(full_screen=False)
    try:
        assert events.order() == "channel", "the order is remembered"
        assert again.set_order("time") == "time"
        times = [events.model.row_value(r, "t_local") for r in range(events.model.rowCount())]
        assert times == sorted(times)
        assert again.scope.text().endswith("in time order")
    finally:
        again.close()


def test_the_channels_chosen_come_back_for_the_same_recording(qapp, opened):
    events = opened.parts.panels["events"]
    pages = opened.parts.pages
    mode = pages.open_review_mode(full_screen=False)
    _settle(qapp)
    with_events = [n for n, c in events.channel_counts().items() if c]
    two = with_events[:2]
    mode.choose_channels(two)
    mode.close()
    _settle(qapp)
    events.set_channels(())                      # the list let go in between
    again = pages.open_review_mode(full_screen=False)
    try:
        assert events.chosen_channels() == tuple(two)
        assert "(as chosen last time)" in again.scope.text()
    finally:
        again.close()
    _settle(qapp)
    # A list narrowed by hand is the reader's choice, not last time's.
    events.set_channels(())
    events.channel.setCurrentText(with_events[2])
    third = pages.open_review_mode(full_screen=False)
    try:
        assert events.chosen_channels() == (with_events[2],)
        assert "last time" not in third.scope.text()
        third.choose_channels(list(events.channel_counts()))      # every channel: forgotten
    finally:
        third.close()
    _settle(qapp)
    events.set_channels(())
    fourth = pages.open_review_mode(full_screen=False)
    try:
        assert events.chosen_channels() == ()
    finally:
        fourth.close()


def test_review_mode_is_reached_by_space_the_toolbar_and_the_menu(qapp, opened):
    from qtpy.QtWidgets import QShortcut

    pages = opened.parts.pages
    spaces = [s for owner in (pages.figure, pages.side)
              for s in owner.findChildren(QShortcut) if s.key().toString() == "Space"]
    assert len(spaces) == 2, "on the trace and the side column, not window-wide"
    assert pages.review_button.text() == "Review events"
    navigate = next(a.menu() for a in opened.parts.host.menuBar().actions()
                    if a.text().replace("&", "") == "Navigate")
    entry = next(a for a in navigate.actions()
                 if a.text().replace("&", "").startswith("Review events one at a time"))
    entry.trigger()
    _settle(qapp)
    assert pages.review_mode.isVisible()
    pages.review_mode.close()


# -- when one event is not enough ------------------------------------------------------------
def _mode(qapp, opened):
    pages = opened.parts.pages
    pages.show_page("recording")
    mode = pages.open_review_mode()
    _settle(qapp)
    return pages, mode


def test_review_mode_opens_as_a_window_that_can_be_moved_and_goes_full_screen_on_f11(
        qapp, opened):
    _pages, mode = _mode(qapp, opened)
    try:
        assert not mode.isFullScreen(), "an ordinary window: moved, resized, minimised"
        mode.toggle_full_screen()
        _settle(qapp, 3)
        assert mode.isFullScreen()
        mode.toggle_full_screen()
        _settle(qapp, 3)
        assert not mode.isFullScreen()
        keys = {s.key().toString() for s in mode.shortcuts}
        assert {"F11", "Home", "End", "+", "-", "Up", "Down", "R", "C", "K", "T"} <= keys
    finally:
        mode.close()


def test_plus_and_minus_change_the_seconds_shown_and_the_arrows_the_gain(qapp, opened):
    from onset_review.reviewmode import PADS

    _pages, mode = _mode(qapp, opened)
    try:
        start = mode.detail.pad_s
        before = mode.detail._snapshot.times
        wider = mode.widen(+1)
        assert wider > start
        after = mode.detail._snapshot.times
        # Wider on the right at least; on the left the recording may begin first.
        assert after[-1] - after[0] > before[-1] - before[0]
        assert after[-1] >= before[-1] + (wider - start) - 0.01
        assert mode.widen(-10) == PADS[0]
        assert mode.widen(+10) == PADS[-1]
        flat = mode.detail.axes[0].get_ylim()
        mode.set_gain(4.0)
        tall = mode.detail.axes[0].get_ylim()
        assert (tall[1] - tall[0]) == pytest.approx((flat[1] - flat[0]) / 4.0, rel=0.05)
        assert "gain ×4" in mode.zoom.text()
        mode.reset_zoom()
        assert mode.detail.gain == 1.0 and mode.detail.pad_s == PADS[2]
        assert f"{PADS[2]:g} s either side" in mode.detail.caption.text()
    finally:
        mode.close()


def test_home_and_end_go_to_the_first_and_last_event(qapp, opened):
    _pages, mode = _mode(qapp, opened)
    try:
        mode.step(-10**9)
        assert mode.position()[0] == 1
        mode.step(+10**9)
        at, total = mode.position()
        assert at == total
    finally:
        mode.close()


def test_the_context_view_shows_the_neighbours_and_stays_open_from_event_to_event(
        qapp, opened):
    from onset_review import eventcontext

    _pages, mode = _mode(qapp, opened)
    try:
        assert mode.context.isHidden()
        assert mode.toggle_context()
        _settle(qapp, 3)
        event = mode._event()
        shown = mode.context.shown
        assert shown.channels == eventcontext.neighbours(
            opened.parts.session.raw.ch_names, event.channel, 2)
        assert event.channel in mode.context.title.text()
        assert "same moment" in mode.context.note.text()
        mode.step(+1)
        _settle(qapp, 3)
        assert mode.context.isVisible()
        assert mode.context.shown.event_channel == mode._event().channel
        mode.context.contacts.setChecked(True)
        _settle(qapp, 3)
        first, second = mode._event().channel.split("-")
        assert mode.context.shown.channels[:2] == [first, second]
    finally:
        mode.close()


def test_t_takes_the_full_trace_to_the_event_with_review_mode_left_open(qapp, opened,
                                                                        monkeypatch):
    from onset_review import window

    pages, mode = _mode(qapp, opened)
    calls = []
    monkeypatch.setattr(window, "goto", lambda figure, t, channel=None, session=None:
                        calls.append((figure, t, channel)))
    try:
        event = mode._event()
        assert mode.show_in_trace()
        figure, t, channel = calls[-1]
        assert figure is pages.figure and channel == event.channel
        assert t == pytest.approx(event.start - opened.parts.session.t_offset)
        assert mode.isVisible()
    finally:
        mode.close()


def test_review_mode_remembers_its_zoom_and_context_view(qapp, opened):
    from onset_review import reviewmode

    _pages, mode = _mode(qapp, opened)
    mode.widen(+1)
    mode.toggle_context()
    pad = mode.detail.pad_s
    mode.close()
    _settle(qapp, 3)
    prefs = reviewmode.load_prefs()
    assert prefs["pad_s"] == pad and prefs["context"] is True and prefs["geometry"]
    _pages, again = _mode(qapp, opened)
    try:
        assert again.detail.pad_s == pad
        assert again.context.isVisible()
    finally:
        again.close()
