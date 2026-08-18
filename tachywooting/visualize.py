#!/usr/bin/env python3
"""
visualize.py — viewer for Wooting HDF5 logs.

Data layout:
  /trials/<trial4>/keys/<key4>/values   # shape=(N, 3)
Columns: ["position", "time_from_onset", "time_abs"]

Usage:
  wooting-visualize FILE.hdf5 --list
  wooting-visualize FILE.hdf5 --trial 1 --key 29
  wooting-visualize FILE.hdf5 --trial 1 --all-keys
  wooting-visualize FILE.hdf5
"""
import argparse
import logging
import os
import sys
from typing import Optional

import h5py
import numpy as np

FIXED_COLUMNS = ["position", "time_from_onset", "time_abs"]
_COLOR_SINGLE = "#4C72B0"
_COLOR_THRESH = "#C0392B"
_COLOR_TITLE  = "#1C1C2E"
_COLOR_LABEL  = "#3C3C4E"
_COLOR_TICK   = "#7C7C8E"
_COLOR_SPINE  = "#D0D0DD"
_COLOR_GRID   = "#E8E8F0"

_log = logging.getLogger(__name__)

_W = 64  # terminal width for separators


def _sep(char: str = "═") -> None:
    print(char * _W)


def _field(label: str, value: str, indent: int = 4) -> None:
    print(f"{' ' * indent}{label:<30}{value}")


def _pad4(x: int) -> str:
    return f"{int(x):04d}"


def _trials(f: h5py.File) -> list[str]:
    return sorted(f["trials"].keys()) if "trials" in f else []


def _keys_for(f: h5py.File, trial4: str) -> list[str]:
    g = f.get(f"/trials/{trial4}/keys")
    return sorted(g.keys()) if isinstance(g, h5py.Group) else []


def _key_label(key4: str) -> str:
    """Return 'A (4)' style label, or just '4' if no HID mapping exists."""
    try:
        from tachywooting.wooting_utils import convert_char_to_keycode
        names = convert_char_to_keycode([int(key4)])
        if names and names[0]:
            return f"{names[0].upper()}  (keycode {int(key4):04d})"
    except Exception:
        _log.debug("HID name lookup failed for key %s", key4, exc_info=True)
    return f"keycode {int(key4):04d}"


def _key_short(key4: str) -> str:
    """Return 'A (6)' compact form."""
    try:
        from tachywooting.wooting_utils import convert_char_to_keycode
        names = convert_char_to_keycode([int(key4)])
        if names and names[0]:
            return f"{names[0].upper()} ({int(key4)})"
    except Exception:
        _log.debug("HID name lookup failed for key %s", key4, exc_info=True)
    return str(int(key4))


def _load_threshold(f: h5py.File, trial4: str) -> Optional[float]:
    g = f.get(f"/trials/{trial4}")
    if not isinstance(g, h5py.Group):
        return None
    val = g.attrs.get("threshold")
    return float(val) if val is not None else None


def _load_xy(f: h5py.File, trial4: str, key4: str):
    """Return (pos, tth, tabs, cols) for a key."""
    path = f"/trials/{trial4}/keys/{key4}/values"
    if path not in f:
        raise KeyError(f"Missing dataset at {path}")
    ds = f[path]
    if not isinstance(ds, h5py.Dataset):
        raise TypeError(f"{path} is not a dataset")
    arr = np.asarray(ds[()])
    cols_attr = ds.attrs.get("columns")
    cols = (
        [c.decode() if isinstance(c, (bytes, np.bytes_)) else str(c) for c in cols_attr]
        if cols_attr is not None
        else FIXED_COLUMNS
    )
    # Accept the legacy "time_to_threshold" column label from older log files.
    time_col = "time_from_onset" if "time_from_onset" in cols else "time_to_threshold"
    i_pos, i_tth, i_abs = map(cols.index, ("position", time_col, "time_abs"))
    return arr[:, i_pos], arr[:, i_tth], arr[:, i_abs], cols


# ── Statistics ────────────────────────────────────────────────────────────────

def _compute_stats(
    pos: np.ndarray,
    tabs: np.ndarray,
    threshold: Optional[float],
) -> dict:
    N = len(pos)
    s: dict = {"N": N}
    if N == 0:
        return s

    t_start = float(tabs.min())
    t_end   = float(tabs.max())
    duration = t_end - t_start
    fs = N / duration if duration > 1e-9 else float("nan")
    s.update({"duration": duration, "t_start_abs": t_start, "t_end_abs": t_end, "fs": fs})

    # Position percentiles
    s["pos_min"]    = float(pos.min())
    s["pos_max"]    = float(pos.max())
    s["pos_mean"]   = float(pos.mean())
    s["pos_std"]    = float(pos.std())
    s["pos_median"] = float(np.median(pos))

    # Threshold analysis
    s["threshold"] = threshold
    if threshold is not None:
        above_mask = pos >= threshold
        n_above = int(above_mask.sum())
        s["threshold_reached"] = n_above > 0
        s["n_above"]     = n_above
        s["time_above"]  = n_above / fs if not np.isnan(fs) else float("nan")
        s["pct_above"]   = n_above / N * 100.0
        s["margin"]      = float(threshold - s["pos_max"])  # >0 = missed, <0 = exceeded
        s["n_crossings_up"] = int(np.sum(np.diff(above_mask.astype(np.int8)) == 1))

        if s["threshold_reached"]:
            first_idx = int(np.argmax(above_mask))
            s["t_cross_from_start"] = float(tabs[first_idx]) - t_start
            s["t_cross_abs"]        = float(tabs[first_idx])
        else:
            s["t_cross_from_start"] = None
            s["t_cross_abs"]        = None
    else:
        s.update({
            "threshold_reached": False, "n_above": 0,
            "time_above": 0.0, "pct_above": 0.0, "margin": None,
            "n_crossings_up": 0, "t_cross_from_start": None, "t_cross_abs": None,
        })

    # Press onset (first sample above 0.01)
    ONSET = 0.01
    nonzero = np.where(pos > ONSET)[0]
    if len(nonzero) > 0:
        idx = int(nonzero[0])
        s["onset_t"]     = float(tabs[idx]) - t_start
        s["onset_t_abs"] = float(tabs[idx])
        s["rise_duration"] = (
            s["t_cross_from_start"] - s["onset_t"]
            if s["t_cross_from_start"] is not None
            else None
        )
    else:
        s["onset_t"] = s["onset_t_abs"] = s["rise_duration"] = None

    # Peak
    peak_idx = int(np.argmax(pos))
    s["peak_pos"]           = float(pos[peak_idx])
    s["peak_t_from_start"]  = float(tabs[peak_idx]) - t_start
    s["peak_t_abs"]         = float(tabs[peak_idx])
    s["peak_t_after_cross"] = (
        float(tabs[peak_idx]) - s["t_cross_abs"]
        if s["t_cross_abs"] is not None
        else None
    )

    # Hold at peak (≥ 95 % of max)
    hold_mask = pos >= s["peak_pos"] * 0.95
    n_hold = int(hold_mask.sum())
    s["hold_at_peak_n"] = n_hold
    s["hold_at_peak_s"] = n_hold / fs if not np.isnan(fs) else float("nan")

    # Hold at threshold
    if threshold is not None and s["threshold_reached"]:
        s["hold_at_threshold_n"] = s["n_above"]
        s["hold_at_threshold_s"] = s["time_above"]
    else:
        s["hold_at_threshold_n"] = s["hold_at_threshold_s"] = None

    return s


def _print_key_stats(key4: str, pos: np.ndarray,
                     tabs: np.ndarray, threshold: Optional[float]) -> None:
    s = _compute_stats(pos, tabs, threshold)

    print()
    print(f"  {_key_label(key4)}")
    print("  " + "─" * (_W - 2))

    if s["N"] == 0:
        print("    (no data)")
        return

    def f(label: str, value: str) -> None:
        _field(label, value, indent=4)

    # ── General ──────────────────────────────────────────────────────────────
    print("\n    General")
    f("Samples",         f"{s['N']:,}")
    f("Duration",        f"{s['duration']:.3f} s   ({s['t_start_abs']:.3f} → {s['t_end_abs']:.3f} s abs)")
    f("Sampling rate",   f"{s['fs']:,.1f} Hz")

    # ── Threshold ─────────────────────────────────────────────────────────────
    if s["threshold"] is not None:
        print(f"\n    Threshold  ( {s['threshold']:.3f} )")
        if s["threshold_reached"]:
            f("Reached",             f"YES  ·  first crossing at {s['t_cross_from_start']:.3f} s from trial start")
            f("Upward crossings",    str(s["n_crossings_up"]))
            f("Time above threshold",f"{s['time_above']:.3f} s   ({s['pct_above']:.1f} % of trial,"
                                     f"  {s['hold_at_threshold_n']:,} samples)")
            f("Exceeded by",         f"{abs(s['margin']):.4f}  (max {s['pos_max']:.4f})")
        else:
            f("Reached",             f"NO  ·  missed by {s['margin']:.4f}  (max {s['pos_max']:.4f})")
            if s["n_crossings_up"] > 0:
                f("Partial crossings", str(s["n_crossings_up"]))

    # ── Position ─────────────────────────────────────────────────────────────
    print("\n    Position")
    f("Min / Max",       f"{s['pos_min']:.4f}   /   {s['pos_max']:.4f}")
    f("Mean ± SD",       f"{s['pos_mean']:.4f}   ±   {s['pos_std']:.4f}")
    f("Median",          f"{s['pos_median']:.4f}")

    # ── Timing ───────────────────────────────────────────────────────────────
    print("\n    Timing")
    if s["onset_t"] is not None:
        f("Press onset (> 0.01)",  f"{s['onset_t']:.3f} s from trial start")
    else:
        f("Press onset",           "key never pressed")

    if s["rise_duration"] is not None:
        f("Rise to threshold",     f"{s['rise_duration']:.3f} s   (onset → crossing)")

    peak_cross = (
        f"  (+{s['peak_t_after_cross']:.3f} s after crossing)"
        if s["peak_t_after_cross"] is not None
        else ""
    )
    f("Peak position",         f"{s['peak_pos']:.4f}   at {s['peak_t_from_start']:.3f} s{peak_cross}")
    f("Hold at peak (≥ 95%)",  f"{s['hold_at_peak_s']:.3f} s   ({s['hold_at_peak_n']:,} samples)")

    if s["hold_at_threshold_s"] is not None:
        f("Hold at threshold",     f"{s['hold_at_threshold_s']:.3f} s   ({s['hold_at_threshold_n']:,} samples)")

    print()


def _print_trial_header(
    file_path: str,
    trial4: str,
    keys: list[str],
    threshold: Optional[float],
) -> None:
    _sep()
    print(f"  File      : {os.path.basename(file_path)}")
    print(f"  Trial     : {trial4}")
    key_list = "  ".join(_key_short(k) for k in keys)
    print(f"  Keys      : {key_list}")
    if threshold is not None:
        print(f"  Threshold : {threshold:.3f}")
    _sep()
    print("\n  KEY STATISTICS")
    _sep("─")


# ── Plot helpers ──────────────────────────────────────────────────────────────

def _check_matplotlib() -> None:
    try:
        __import__("matplotlib.pyplot")
    except ImportError as exc:
        raise RuntimeError(
            'matplotlib required. Install the package with its base dependencies.'
        ) from exc


def _make_figure(title: str):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_title(title, pad=14, fontsize=13, fontweight="semibold", color=_COLOR_TITLE)
    ax.set_xlabel("time to threshold  (s)", fontsize=10, labelpad=8, color=_COLOR_LABEL)
    ax.set_ylabel("position", fontsize=10, labelpad=8, color=_COLOR_LABEL)
    ax.tick_params(axis="both", labelsize=9, labelcolor=_COLOR_TICK, color=_COLOR_SPINE)
    ax.set_ylim(0, 1)
    ax.grid(True, axis="y", alpha=1.0, linewidth=0.6, color=_COLOR_GRID, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_edgecolor(_COLOR_SPINE)
    return fig, ax


def _finalize(
    fig, ax, all_tth: np.ndarray, all_tabs: np.ndarray, save_path: Optional[str],
    *, threshold: Optional[float] = None, legend: bool = False,
) -> None:
    import matplotlib.pyplot as plt
    if all_tth.size:
        rng = float(all_tth.max() - all_tth.min())
        pad = 0.02 * (rng if rng > 0 else 1.0)
        ax.set_xlim(float(all_tth.min()) - pad, float(all_tth.max()) + pad)

    if threshold is not None:
        ax.axhline(threshold, linestyle="--", color=_COLOR_THRESH,
                   linewidth=1.2, alpha=0.75, zorder=2)
        ax.annotate(
            f"threshold  {threshold:.2f}",
            xy=(1, threshold), xycoords=("axes fraction", "data"),
            xytext=(6, 0), textcoords="offset points",
            va="center", ha="left", clip_on=False,
            color=_COLOR_THRESH, fontsize=8.5, fontstyle="italic",
        )

    offset = float(np.median(all_tabs - all_tth)) if all_tth.size else 0.0
    secax = ax.secondary_xaxis(
        "top", functions=(lambda x: x + offset, lambda x: x - offset)
    )
    secax.set_xlabel("time abs  (s)", labelpad=8, fontsize=10, color=_COLOR_LABEL)
    secax.tick_params(labelsize=9, labelcolor=_COLOR_TICK, color=_COLOR_SPINE)

    if legend:
        ax.legend(
            title="Key", title_fontsize=9,
            framealpha=0.95, fontsize=9,
            markerscale=2, edgecolor=_COLOR_SPINE, fancybox=False,
        )

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150)
        print(f"\n  Plot saved: {save_path}")
    else:
        plt.show()


# ── Public entry points ───────────────────────────────────────────────────────

def visualize(
    f: h5py.File, trial4: str, key4: str,
    file_path: str = "", save_path: Optional[str] = None,
) -> None:
    _check_matplotlib()
    threshold = _load_threshold(f, trial4)
    pos, tth, tabs, _ = _load_xy(f, trial4, key4)

    _print_trial_header(file_path, trial4, [key4], threshold)
    _print_key_stats(key4, pos, tabs, threshold)

    fig, ax = _make_figure(f"Trial {int(trial4)}  ·  Key {_key_label(key4)}")
    ax.scatter(tth, pos, s=8, alpha=0.85, color=_COLOR_SINGLE, zorder=3)
    _finalize(fig, ax, tth, tabs, save_path, threshold=threshold)


def visualize_all_keys(
    f: h5py.File, trial4: str,
    file_path: str = "", save_path: Optional[str] = None,
) -> None:
    _check_matplotlib()
    keys = _keys_for(f, trial4)
    if not keys:
        _log.warning("No keys found for trial %s", trial4)
        return

    threshold = _load_threshold(f, trial4)
    _print_trial_header(file_path, trial4, keys, threshold)

    import matplotlib.pyplot as plt
    colors = plt.cm.tab10.colors
    fig, ax = _make_figure(f"Trial {int(trial4)}  ·  {len(keys)} keys")

    all_tth, all_tabs = [], []
    for i, k4 in enumerate(keys):
        pos, tth, tabs, _ = _load_xy(f, trial4, k4)
        _print_key_stats(k4, pos, tabs, threshold)
        all_tth.append(tth)
        all_tabs.append(tabs)
        ax.scatter(tth, pos, s=8, alpha=0.8,
                   color=colors[i % len(colors)], label=_key_label(k4), zorder=3)

    _finalize(fig, ax, np.concatenate(all_tth), np.concatenate(all_tabs), save_path,
              threshold=threshold, legend=True)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Visualize Wooting HDF5 logs.")
    ap.add_argument("file", help="Path to .h5 / .hdf5")
    ap.add_argument("--list",     action="store_true", help="List trials and keys, then exit")
    ap.add_argument("--trial",    type=int, help="Trial id  (e.g. 1)")
    ap.add_argument("--key",      type=int, help="Key id  (e.g. 29)")
    ap.add_argument("--all-keys", action="store_true", help="Plot all keys of the trial on one figure")
    ap.add_argument("--save",     type=str, help="Save plot to file  (e.g. plot.png)")
    args = ap.parse_args()

    try:
        f = h5py.File(args.file, "r")
    except Exception as e:
        _log.error("Failed to open %s: %s", args.file, e)
        sys.exit(1)

    with f:
        if args.list:
            ts = _trials(f)
            _sep()
            print(f"  File    : {os.path.basename(args.file)}")
            print(f"  Trials  : {len(ts)}")
            _sep()
            if not ts:
                print("  No /trials group found.")
            for t in ts:
                ks = _keys_for(f, t)
                thresh = _load_threshold(f, t)
                thresh_str = f"  threshold={thresh:.3f}" if thresh is not None else ""
                key_str = "  ".join(_key_short(k) for k in ks)
                n_keys = f"{len(ks)} key{'s' if len(ks) != 1 else ''}"
                print(f"  {t}  ·  {n_keys:8s}  ·  [ {key_str} ]{thresh_str}")
            _sep()
            return

        if args.trial is None:
            ts = _trials(f)
            print(f"Available trials: {', '.join(ts)}")
            trial4 = _pad4(int(input("Trial number: ").strip()))
        else:
            trial4 = _pad4(args.trial)

        if args.all_keys:
            visualize_all_keys(f, trial4, file_path=args.file, save_path=args.save)
            return

        if args.key is None:
            ks = _keys_for(f, trial4)
            print(f"Available keys: {', '.join(ks)}  (or 'all')")
            raw = input("Key number: ").strip().lower()
            if raw == "all":
                visualize_all_keys(f, trial4, file_path=args.file, save_path=args.save)
                return
            key4 = _pad4(int(raw))
        else:
            key4 = _pad4(args.key)

        visualize(f, trial4, key4, file_path=args.file, save_path=args.save)


if __name__ == "__main__":
    main()
