#!/usr/bin/env python3
from pathlib import Path
import argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm


def normalize_rw(v: str) -> str:
    v = str(v).strip().lower()
    if v in ("read", "seq_read", "seqread"):
        return "seq_read"
    if v in ("randread", "rand_read", "random_read"):
        return "rand_read"
    return v


def infer_engine(df: pd.DataFrame, cli_engine: str | None) -> str:
    if cli_engine:
        return cli_engine
    if "ioengine" in df.columns and df["ioengine"].notna().any():
        vals = df["ioengine"].dropna().astype(str).unique().tolist()
        if len(vals) == 1:
            return vals[0]
        if len(vals) > 1:
            return "_mixed"
    return "unknown"


def prepare_df(csv_path: Path) -> tuple[pd.DataFrame, str]:
    df = pd.read_csv(csv_path)

    required = {"job_name", "rw", "numjobs", "iodepth", "bw_MBps", "lat_avg_us"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV 缺少必要列: {sorted(missing)}")

    df = df.copy()
    df["rw_norm"] = df["rw"].apply(normalize_rw)
    df["numjobs"] = pd.to_numeric(df["numjobs"], errors="coerce")
    df["iodepth"] = pd.to_numeric(df["iodepth"], errors="coerce")
    df["bw_MBps"] = pd.to_numeric(df["bw_MBps"], errors="coerce")
    df["lat_avg_us"] = pd.to_numeric(df["lat_avg_us"], errors="coerce")

    df = df.dropna(subset=["rw_norm", "numjobs", "iodepth", "bw_MBps", "lat_avg_us"])

    engine = infer_engine(df, None)
    return df, engine


def base_style():
    plt.style.use("default")
    plt.rcParams.update({
        "figure.figsize": (7.2, 4.8),
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "legend.fontsize": 10,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def save_line_bw_vs_numjobs(df: pd.DataFrame, engine: str, outdir: Path):
    d = df[df["iodepth"] == 1].copy()
    d = d[d["rw_norm"].isin(["seq_read", "rand_read"])]

    if d.empty:
        print("[WARN] 没有 iodepth=1 的数据，跳过图1")
        return

    fig, ax = plt.subplots()

    for rw, label, marker in [
        ("seq_read", "Sequential Read", "o"),
        ("rand_read", "Random Read", "s"),
    ]:
        sub = d[d["rw_norm"] == rw].sort_values("numjobs")
        if sub.empty:
            continue
        ax.plot(
            sub["numjobs"],
            sub["bw_MBps"],
            marker=marker,
            linewidth=2.0,
            markersize=6,
            label=label,
        )

    ax.set_xlabel("numjobs")
    ax.set_ylabel("Bandwidth (MB/s)")
    ax.set_title(f"BW vs numjobs (iodepth=1, engine={engine})")
    ax.legend(frameon=False)
    fig.tight_layout()

    out = outdir / f"qd_jobs_{engine}_bw_vs_numjobs_iodepth1.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out}")


def save_line_lat_vs_numjobs(df: pd.DataFrame, engine: str, outdir: Path):
    d = df[df["iodepth"] == 1].copy()
    d = d[d["rw_norm"].isin(["seq_read", "rand_read"])]

    if d.empty:
        print("[WARN] 没有 iodepth=1 的数据，跳过图2")
        return

    fig, ax = plt.subplots()

    for rw, label, marker in [
        ("seq_read", "Sequential Read", "o"),
        ("rand_read", "Random Read", "s"),
    ]:
        sub = d[d["rw_norm"] == rw].sort_values("numjobs")
        if sub.empty:
            continue
        ax.plot(
            sub["numjobs"],
            sub["lat_avg_us"],
            marker=marker,
            linewidth=2.0,
            markersize=6,
            label=label,
        )

    ax.set_xlabel("numjobs")
    ax.set_ylabel("Average Latency (us)")
    ax.set_title(f"Latency vs numjobs (iodepth=1, engine={engine})")
    ax.legend(frameon=False)
    fig.tight_layout()

    out = outdir / f"qd_jobs_{engine}_latency_vs_numjobs_iodepth1.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out}")


def build_heatmap_matrix(df: pd.DataFrame, rw_norm: str, value_col: str) -> pd.DataFrame:
    sub = df[df["rw_norm"] == rw_norm].copy()
    if sub.empty:
        return pd.DataFrame()

    pivot = sub.pivot_table(
        index="numjobs",
        columns="iodepth",
        values=value_col,
        aggfunc="mean"
    )
    pivot = pivot.sort_index().sort_index(axis=1)
    return pivot


def compute_shared_range(*mats: pd.DataFrame) -> tuple[float | None, float | None]:
    vals = []
    for mat in mats:
        if mat is None or mat.empty:
            continue
        arr = mat.to_numpy(dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        if arr.size:
            vals.append(arr)

    if not vals:
        return None, None

    all_vals = np.concatenate(vals)
    return float(np.min(all_vals)), float(np.max(all_vals))


def build_shared_norm(*mats: pd.DataFrame, log_scale: bool = False):
    if not log_scale:
        return None

    vals = []
    for mat in mats:
        if mat is None or mat.empty:
            continue
        arr = mat.to_numpy(dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        arr = arr[arr > 0]
        if arr.size:
            vals.append(arr)

    if not vals:
        return None

    all_vals = np.concatenate(vals)
    vmin = float(np.min(all_vals))
    vmax = float(np.max(all_vals))
    if vmin <= 0 or vmax <= 0 or vmin == vmax:
        return None
    return LogNorm(vmin=vmin, vmax=vmax)


def draw_heatmap(ax, mat, title, cmap="OrRd", value_fmt=None, reverse_y=True, vmin=None, vmax=None, norm=None):
    if mat.empty:
        ax.set_title(title)
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_axis_off()
        return None

    # 如果要求纵轴从下到上增大，就把行顺序翻转
    plot_mat = mat.sort_index(ascending=not reverse_y)

    imshow_kwargs = {"aspect": "auto", "cmap": cmap, "origin": "upper"}
    if norm is not None:
        imshow_kwargs["norm"] = norm
    else:
        imshow_kwargs["vmin"] = vmin
        imshow_kwargs["vmax"] = vmax
    im = ax.imshow(plot_mat.values, **imshow_kwargs)

    ax.set_title(title)
    ax.set_xticks(range(len(plot_mat.columns)))
    ax.set_xticklabels([str(int(x)) if float(x).is_integer() else str(x) for x in plot_mat.columns])

    ax.set_yticks(range(len(plot_mat.index)))
    ax.set_yticklabels([str(int(x)) if float(x).is_integer() else str(x) for x in plot_mat.index])

    ax.set_xlabel("iodepth")
    ax.set_ylabel("numjobs")

    # 在格子里标数值
    val_min = np.nanmin(plot_mat.values)
    val_max = np.nanmax(plot_mat.values)
    tmin = vmin if vmin is not None else val_min
    tmax = vmax if vmax is not None else val_max
    if norm is not None and hasattr(norm, "vmin") and hasattr(norm, "vmax"):
        tmin = norm.vmin
        tmax = norm.vmax
    threshold = (tmin + tmax) / 2.0 if np.isfinite(tmin) and np.isfinite(tmax) else 0

    if norm is not None and tmin is not None and tmax is not None and tmin > 0 and tmax > 0:
        threshold = float(np.sqrt(tmin * tmax))

    for i in range(plot_mat.shape[0]):
        for j in range(plot_mat.shape[1]):
            val = plot_mat.iloc[i, j]
            if pd.notna(val):
                if value_fmt is None:
                    text = f"{val:.1f}" if val >= 10 else f"{val:.2f}"
                else:
                    text = value_fmt(val)

                # 深色格子用白字，浅色格子用黑字
                color = "white" if val > threshold else "black"
                ax.text(j, i, text, ha="center", va="center", fontsize=8, color=color)

    return im


def save_heatmap_bw(df, engine, outdir, log_scale=False):
    seq_mat = build_heatmap_matrix(df, "seq_read", "bw_MBps")
    rand_mat = build_heatmap_matrix(df, "rand_read", "bw_MBps")
    shared_min, shared_max = compute_shared_range(seq_mat, rand_mat)
    shared_norm = build_shared_norm(seq_mat, rand_mat, log_scale=log_scale)
    if log_scale and shared_norm is None:
        print("[WARN] BW 热力图对数色阶需要正数数据，已回退为线性色阶")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=False)

    # BW 用暖色系
    im1 = draw_heatmap(
        axes[0], seq_mat,
        title="Sequential Read",
        cmap="OrRd",
        reverse_y=True,
        vmin=shared_min if shared_norm is None else None,
        vmax=shared_max if shared_norm is None else None,
        norm=shared_norm,
    )
    im2 = draw_heatmap(
        axes[1], rand_mat,
        title="Random Read",
        cmap="OrRd",
        reverse_y=True,
        vmin=shared_min if shared_norm is None else None,
        vmax=shared_max if shared_norm is None else None,
        norm=shared_norm,
    )

    fig.suptitle(f"BW Heatmap (engine={engine})", y=0.98)

    # 给右边留出 colorbar 空间
    fig.subplots_adjust(right=0.88, wspace=0.25, top=0.88)

    # 把色条放到最右边图外
    target_im = im2 if im2 is not None else im1
    if target_im is not None:
        cax = fig.add_axes([0.90, 0.18, 0.02, 0.62])  # [left, bottom, width, height]
        cbar = fig.colorbar(target_im, cax=cax)
        cbar.set_label("Bandwidth (MB/s, log scale)" if shared_norm is not None else "Bandwidth (MB/s)")

    out = outdir / f"qd_jobs_{engine}_bw_heatmap.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out}")


def save_heatmap_lat(df, engine, outdir, log_scale=False):
    seq_mat = build_heatmap_matrix(df, "seq_read", "lat_avg_us")
    rand_mat = build_heatmap_matrix(df, "rand_read", "lat_avg_us")
    shared_min, shared_max = compute_shared_range(seq_mat, rand_mat)
    shared_norm = build_shared_norm(seq_mat, rand_mat, log_scale=log_scale)
    if log_scale and shared_norm is None:
        print("[WARN] 延迟热力图对数色阶需要正数数据，已回退为线性色阶")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=False)

    # Latency 用蓝色系
    im1 = draw_heatmap(
        axes[0], seq_mat,
        title="Sequential Read",
        cmap="Blues",
        reverse_y=True,
        vmin=shared_min if shared_norm is None else None,
        vmax=shared_max if shared_norm is None else None,
        norm=shared_norm,
    )
    im2 = draw_heatmap(
        axes[1], rand_mat,
        title="Random Read",
        cmap="Blues",
        reverse_y=True,
        vmin=shared_min if shared_norm is None else None,
        vmax=shared_max if shared_norm is None else None,
        norm=shared_norm,
    )

    fig.suptitle(f"Latency Heatmap (engine={engine})", y=0.98)

    fig.subplots_adjust(right=0.88, wspace=0.25, top=0.88)

    target_im = im2 if im2 is not None else im1
    if target_im is not None:
        cax = fig.add_axes([0.90, 0.18, 0.02, 0.62])
        cbar = fig.colorbar(target_im, cax=cax)
        cbar.set_label("Average Latency (us, log scale)" if shared_norm is not None else "Average Latency (us)")

    out = outdir / f"qd_jobs_{engine}_latency_heatmap.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out}")


def main():
    parser = argparse.ArgumentParser(description="Plot qd_jobs fio CSV results.")
    parser.add_argument("csv", help="Path to qd_jobs csv")
    parser.add_argument("-o", "--outdir", default=".", help="Output directory")
    parser.add_argument("-e", "--engine", default=None, help="Override engine name in title/file")
    parser.add_argument("--heatmap-log-scale", action="store_true", help="Use logarithmic color scale for heatmaps")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base_style()
    df, auto_engine = prepare_df(csv_path)
    engine = args.engine if args.engine else auto_engine

    save_line_bw_vs_numjobs(df, engine, outdir)
    save_line_lat_vs_numjobs(df, engine, outdir)
    save_heatmap_bw(df, engine, outdir, log_scale=args.heatmap_log_scale)
    save_heatmap_lat(df, engine, outdir, log_scale=args.heatmap_log_scale)


if __name__ == "__main__":
    main()
