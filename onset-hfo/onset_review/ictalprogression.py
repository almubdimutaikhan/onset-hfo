"""How a seizure spread: which channels changed, in what order, and where. Qt-free.

The Epileptogenicity Index is one number per channel. Behind it is a curve per
channel -- the fast-over-slow energy ratio, divided by that channel's own
baseline -- and a moment when each curve rose and stayed risen
(`onset_hfo.ictal.progression`). This module turns those into the three
things a reader looks at to see a seizure start and spread:

* **the recruitment heatmap**: every channel's ratio over time, from before
  the marked onset to after it, the channels in the order they changed, each
  one's change marked;
* **the order**: first channel, second, ..., each with its delay from the first
  change and from the marked onset;
* **the map at a moment**: where the channels are, coloured by their ratio at
  that moment and ringed once they have changed, so a slider or "play" shows
  the seizure spreading across the electrodes. With nilearn installed and the
  contacts placed in MNI space, the map is nilearn's glass brain (seen from the
  left, from above and from the right); otherwise the contacts seen from above.

What it shows is descriptive: when each channel's fast activity rose against
its own baseline. It recommends nothing, and a channel that changed first is
not thereby the onset zone -- the clinician marks that.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["order_table", "heatmap_rows", "state_at", "draw", "glass_caption", "VMAX"]

#: The colour scale's top, in log10 of the ratio to baseline: 1.5 is about 30
#: times the channel's usual fast-over-slow energy. 0 is "as usual".
VMAX = 1.5


def order_table(prog) -> pd.DataFrame:
    """Channels in the order they changed: those that changed first, by
    change time, then those that did not, by index. Delays are seconds from
    the first change and from the marked onset."""
    table = prog.table.copy()
    if table.empty:
        return pd.DataFrame(columns=["order", "channel", "change_s", "delay_s", "ei",
                                     "detected"])
    detected = table[table["detected"].astype(bool)].sort_values(["change_s", "channel"])
    rest = table[~table["detected"].astype(bool)].sort_values(["ei", "channel"],
                                                             ascending=[False, True])
    ordered = pd.concat([detected, rest], ignore_index=True)
    first = float(detected["change_s"].min()) if len(detected) else np.nan
    ordered["delay_s"] = ordered["change_s"] - first
    ordered.insert(0, "order", np.arange(1, len(ordered) + 1))
    ordered.loc[~ordered["detected"].astype(bool), "order"] = 0
    return ordered[["order", "channel", "change_s", "delay_s", "ei", "detected"]]


def heatmap_rows(prog, limit: int = 40) -> tuple[list[str], np.ndarray]:
    """The channels to draw, in recruitment order (at most `limit`), and their
    log10 ratio to baseline over time, rows matching."""
    order = order_table(prog)
    channels = list(order["channel"])[:limit]
    index = {c: i for i, c in enumerate(prog.channels)}
    rows = np.vstack([np.log10(np.maximum(prog.ratio[index[c]], 1e-6)) for c in channels]) \
        if channels else np.empty((0, len(prog.times)))
    return channels, rows


def state_at(prog, t: float) -> pd.DataFrame:
    """Every channel at `t` seconds from the marked onset: its log10 ratio to
    baseline there, and whether it has changed by then."""
    times = np.asarray(prog.times, dtype=float)
    k = int(np.clip(np.searchsorted(times, t), 0, len(times) - 1)) if len(times) else 0
    change = prog.table.set_index("channel")["change_s"] if len(prog.table) else pd.Series()
    rows = []
    for i, channel in enumerate(prog.channels):
        value = float(np.log10(max(float(prog.ratio[i, k]), 1e-6))) if len(times) else np.nan
        when = change.get(channel, np.nan)
        rows.append({"channel": channel, "log_ratio": value,
                     "changed": bool(np.isfinite(when) and when <= t),
                     "change_s": float(when) if np.isfinite(when) else np.nan})
    return pd.DataFrame(rows)


def glass_caption(kind: str = "template") -> str:
    """What the glass brain shows, and where the positions came from
    (`electrodes.positions_kind`)."""
    from onset_hfo.case.electrodes import CAPTIONS

    return (f"glass brain (MNI152, nilearn) · {CAPTIONS.get(kind, CAPTIONS['template'])}\n"
            "shade: fast/slow ×baseline · cyan ring: changed · dashed: marked onset zone")


def _placed(prog, positions) -> pd.DataFrame | None:
    if positions is None or not len(positions) or "placed" not in positions:
        return None
    placed = positions[positions["placed"].astype(bool)]
    return placed[placed["channel"].isin(prog.channels)]


def _can_glass(placed) -> bool:
    from onset_review import templatebrain

    return (placed is not None and len(placed) > 0 and "z" in placed
            and bool(np.isfinite(placed[["x", "y", "z"]].to_numpy(float)).all())
            and templatebrain.available())


def draw(figure, prog, t: float | None = None, positions: pd.DataFrame | None = None,
         zone: set | frozenset = frozenset(), limit: int = 40, glass: bool = True,
         kind: str = "template") -> dict:
    """The heatmap on the left and, on the right, the map at `t` when the
    channels have positions, else the order as a timeline.

    `positions` has `channel`, `x`, `y` and `placed`, and `z` for the glass
    brain, which is drawn when `glass`, nilearn is installed and every placed
    channel has all three; `kind` says where the positions came from, for the
    caption. `zone` holds the channels the clinician marked as the onset zone,
    ringed on the map.
    """
    from onset_review.studycharts import CURSOR, MUTED, _quiet

    figure.clear()
    channels, rows = heatmap_rows(prog, limit)
    times = np.asarray(prog.times, dtype=float)
    t = float(times[0]) if t is None and len(times) else float(t or 0.0)
    placed = _placed(prog, positions)
    use_glass = bool(glass and channels and _can_glass(placed))
    heat = figure.add_axes([0.08, 0.14, 0.38, 0.76] if use_glass else [0.1, 0.12, 0.5, 0.78])
    side = None if use_glass else figure.add_axes([0.66, 0.12, 0.32, 0.78])
    out = {"channels": channels, "t": t, "glass": use_glass}
    if not channels:
        heat.text(0.5, 0.5, "No channel to draw", ha="center", va="center",
                  transform=heat.transAxes, color=MUTED)
        heat.set_axis_off()
        side.set_axis_off()
        return out
    mesh = heat.pcolormesh(times, np.arange(len(channels)), rows, shading="nearest",
                           cmap="magma", vmin=0.0, vmax=VMAX)
    heat.set_yticks(np.arange(len(channels)))
    heat.set_yticklabels(channels, fontsize=7)
    heat.invert_yaxis()
    change = prog.table.set_index("channel")["change_s"]
    for y, channel in enumerate(channels):
        when = change.get(channel, np.nan)
        if np.isfinite(when):
            heat.plot([when], [y], marker="|", color="white", markersize=7, mew=1.6)
    heat.axvline(0.0, color="white", lw=0.8, ls="--", alpha=0.8)
    out["cursor"] = heat.axvline(t, color=CURSOR, lw=1.4)
    heat.set_xlabel("seconds from the marked onset\nwhite tick: when the channel "
                    "changed  ·  dashed: marked onset", fontsize=7, color=MUTED)
    heat.tick_params(labelsize=7)
    colour = figure.colorbar(mesh, ax=heat, fraction=0.03, pad=0.01)
    colour.set_label("fast/slow energy, ×baseline (log10)", fontsize=7)
    colour.ax.tick_params(labelsize=6)

    if use_glass:
        _draw_glass(figure, prog, t, placed, zone, kind)
        out["map"] = True
        return out
    _quiet(side)
    if placed is not None and len(placed):
        state = state_at(prog, t).set_index("channel")
        values = [state.loc[c, "log_ratio"] for c in placed["channel"]]
        changed = [bool(state.loc[c, "changed"]) for c in placed["channel"]]
        side.scatter(placed["x"], placed["y"], c=values, cmap="magma", vmin=0.0,
                     vmax=VMAX, s=[60 if c else 26 for c in changed],
                     edgecolors=[CURSOR if c else "none" for c in changed],
                     linewidths=1.4)
        ringed = placed[placed["channel"].isin(zone)]
        if len(ringed):
            side.scatter(ringed["x"], ringed["y"], s=140, facecolors="none",
                         edgecolors=MUTED, linewidths=0.8, linestyle="--")
        side.set_aspect("equal", adjustable="datalim")
        side.set_xticks([])
        side.set_yticks([])
        n_changed = int(sum(changed))
        side.set_title(f"at {t:+.1f} s: {n_changed} of {len(placed)} placed channels "
                       "changed", fontsize=8)
        side.set_xlabel("seen from above · cyan ring: changed · dashed: marked onset "
                        "zone", fontsize=7, color=MUTED)
        out["map"] = True
    else:
        order = order_table(prog)
        order = order[order["detected"].astype(bool)].head(15)
        y = np.arange(len(order))
        side.barh(y, order["change_s"], color=[CURSOR if v <= t else MUTED
                                                for v in order["change_s"]])
        side.set_yticks(y)
        side.set_yticklabels(list(order["channel"]), fontsize=7)
        side.invert_yaxis()
        side.axvline(0.0, color=MUTED, lw=0.8, ls="--")
        side.set_xlabel("change, s from the marked onset", fontsize=7, color=MUTED)
        side.set_title("Order of change (no positions placed)", fontsize=8)
        out["map"] = False
    return out


def _draw_glass(figure, prog, t: float, placed: pd.DataFrame, zone, kind: str) -> None:
    """The placed channels at `t` on nilearn's glass brain, right of the heatmap."""
    from nilearn import plotting

    from onset_review.studycharts import CURSOR, MUTED

    state = state_at(prog, t).set_index("channel")
    coords = placed[["x", "y", "z"]].to_numpy(float)
    values = np.array([state.loc[c, "log_ratio"] for c in placed["channel"]], dtype=float)
    changed = np.array([bool(state.loc[c, "changed"]) for c in placed["channel"]])
    sizes = np.where(changed, 40.0, 16.0)
    display = plotting.plot_markers(
        np.nan_to_num(values, nan=0.0), coords, node_size=sizes, node_cmap="magma",
        node_vmin=0.0, node_vmax=VMAX, display_mode="lzr", figure=figure,
        axes=[0.535, 0.16, 0.46, 0.68], colorbar=False, alpha=0.9)
    # Rings, not dots: nilearn hands `marker_color` to matplotlib as `c`, so
    # the face is made transparent there, one colour per marker.
    if changed.any():
        display.add_markers(coords[changed], marker_color=[(0.0, 0.0, 0.0, 0.0)]
                            * int(changed.sum()), marker_size=sizes[changed] + 22,
                            edgecolors=CURSOR, linewidths=1.2)
    ringed = placed["channel"].isin(zone).to_numpy()
    if ringed.any():
        display.add_markers(coords[ringed], marker_color=[(0.0, 0.0, 0.0, 0.0)]
                            * int(ringed.sum()), marker_size=sizes[ringed] + 60,
                            edgecolors=MUTED, linewidths=0.8, linestyle="--")
    figure.text(0.765, 0.80, f"at {t:+.1f} s: {int(changed.sum())} of {len(placed)} "
                "placed channels changed", ha="center", va="top", fontsize=8)
    figure.text(0.765, 0.27, glass_caption(kind), ha="center", va="top", fontsize=6.5,
                color=MUTED)
