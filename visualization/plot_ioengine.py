#!/usr/bin/env python3
from pathlib import Path
import argparse
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def normalize_rw(v: str) -> str:
    v = str(v).strip().lower()
    if v in ("read", "seq_read", "seqread"):
        return "seq_read"
    if v in ("randread", "rand_read", "random_read"):
        return "rand_read"
    return v


def pretty_rw(v: str) -> str:
    return {
        "seq_read": "Sequential Read",
        "rand_read": "Random Read",
    }.get(v, v)


def base_style():
    plt.style.use("default")
    plt.rcParams.update({
        "figure.figsize": (8.0, 4.8),
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "font.size": 11,
        "axes.titlesize": 14,
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


def prepare_df(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required = {"job_name", "rw", "ioengine", "bw_MBps", "lat_avg_us"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV 缺少必要列: {sorted(missing)}")

    df = df.copy()
    df["rw_norm"] = df["rw"].apply(normalize_rw)
    df["bw_MBps"] = pd.to_numeric(df["bw_MBps"], errors="coerce")
    df["lat_avg_us"] = pd.to_numeric(df["lat_avg_us"], errors="coerce")

    df = df.dropna(subset=["rw_norm", "ioengine", "bw_MBps", "lat_avg_us"])
    df = df[df["rw_norm"].isin(["seq_read", "rand_read"])]

    # 统一引擎顺序
    engine_order = ["psync", "libaio", "io_uring", "mmap"]
    df["ioengine"] = pd.Categorical(df["ioengine"], categories=engine_order, ordered=True)

    # 同一个 engine + rw 如果有重复，取平均
    df = (
        df.groupby(["ioengine", "rw_norm"], as_index=False)[["bw_MBps", "lat_avg_us"]]
        .mean()
        .sort_values(["ioengine", "rw_norm"])
    )
    return df


def grouped_bar_plot(
    df: pd.DataFrame,
    value_col: str,
    ylabel: str,
    title: str,
    outfile: Path,
    y_top_padding_ratio: float = 0.0,
    legend_loc: str = "best",
    legend_bbox_to_anchor=None,
):
    engines = [e for e in ["psync", "libaio", "io_uring", "mmap"] if e in df["ioengine"].astype(str).unique()]
    seq_vals = []
    rand_vals = []

    for eng in engines:
        seq = df[(df["ioengine"].astype(str) == eng) & (df["rw_norm"] == "seq_read")]
        rand = df[(df["ioengine"].astype(str) == eng) & (df["rw_norm"] == "rand_read")]

        seq_vals.append(seq.iloc[0][value_col] if not seq.empty else None)
        rand_vals.append(rand.iloc[0][value_col] if not rand.empty else None)

    x = list(range(len(engines)))
    width = 0.36

    fig, ax = plt.subplots()

    bars1 = ax.bar([i - width/2 for i in x], seq_vals, width=width, label="Sequential Read")
    bars2 = ax.bar([i + width/2 for i in x], rand_vals, width=width, label="Random Read")

    ax.set_xticks(x)
    ax.set_xticklabels(engines)
    ax.set_xlabel("I/O Engine")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if y_top_padding_ratio > 0:
        all_vals = pd.to_numeric(pd.Series(seq_vals + rand_vals), errors="coerce").dropna()
        if not all_vals.empty:
            y_max = float(all_vals.max())
            ax.set_ylim(0, y_max * (1 + y_top_padding_ratio))

    ax.legend(frameon=False, loc=legend_loc, bbox_to_anchor=legend_bbox_to_anchor)

    # 标数值
    for bars in [bars1, bars2]:
        for b in bars:
            h = b.get_height()
            if pd.notna(h):
                ax.text(
                    b.get_x() + b.get_width() / 2,
                    h,
                    f"{h:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=9
                )

    fig.tight_layout()
    fig.savefig(outfile, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {outfile}")


def grouped_bar_plot_bw_broken_axis(
    df: pd.DataFrame,
    outfile: Path,
    lower_ylim=(0, 800),
    upper_ylim=(8000, 9200),
):
    engines = [e for e in ["psync", "libaio", "io_uring", "mmap"] if e in df["ioengine"].astype(str).unique()]
    seq_vals = []
    rand_vals = []

    for eng in engines:
        seq = df[(df["ioengine"].astype(str) == eng) & (df["rw_norm"] == "seq_read")]
        rand = df[(df["ioengine"].astype(str) == eng) & (df["rw_norm"] == "rand_read")]

        seq_vals.append(seq.iloc[0]["bw_MBps"] if not seq.empty else None)
        rand_vals.append(rand.iloc[0]["bw_MBps"] if not rand.empty else None)

    x = list(range(len(engines)))
    width = 0.36

    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        sharex=True,
        gridspec_kw={"height_ratios": [1, 2], "hspace": 0.05},
    )

    bars_top_seq = ax_top.bar([i - width / 2 for i in x], seq_vals, width=width, label="Sequential Read")
    bars_top_rand = ax_top.bar([i + width / 2 for i in x], rand_vals, width=width, label="Random Read")
    bars_bottom_seq = ax_bottom.bar([i - width / 2 for i in x], seq_vals, width=width, label="Sequential Read")
    bars_bottom_rand = ax_bottom.bar([i + width / 2 for i in x], rand_vals, width=width, label="Random Read")

    ax_top.set_ylim(*upper_ylim)
    ax_bottom.set_ylim(*lower_ylim)

    ax_top.spines["bottom"].set_visible(False)
    ax_bottom.spines["top"].set_visible(False)
    ax_top.tick_params(labeltop=False)
    ax_bottom.xaxis.tick_bottom()

    d = 0.5
    kwargs_top = dict(marker=[(-1, -d), (1, d)], markersize=8, linestyle="none", color="k", mec="k", mew=1, clip_on=False)
    kwargs_bottom = dict(marker=[(-1, d), (1, -d)], markersize=8, linestyle="none", color="k", mec="k", mew=1, clip_on=False)
    ax_top.plot([0, 1], [0, 0], transform=ax_top.transAxes, **kwargs_top)
    ax_bottom.plot([0, 1], [1, 1], transform=ax_bottom.transAxes, **kwargs_bottom)

    ax_bottom.set_xticks(x)
    ax_bottom.set_xticklabels(engines)
    ax_bottom.set_xlabel("I/O Engine")
    ax_bottom.set_ylabel("Bandwidth (MB/s)")
    ax_top.set_title("Bandwidth by I/O Engine (Broken Y-Axis)")
    ax_top.legend(frameon=False)

    def annotate_bars(ax, bars):
        y_min, y_max = ax.get_ylim()
        y_span = y_max - y_min
        for b in bars:
            h = b.get_height()
            if pd.notna(h) and y_min <= h <= y_max:
                ax.text(
                    b.get_x() + b.get_width() / 2,
                    h + y_span * 0.02,
                    f"{h:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

    annotate_bars(ax_top, bars_top_seq)
    annotate_bars(ax_top, bars_top_rand)
    annotate_bars(ax_bottom, bars_bottom_seq)
    annotate_bars(ax_bottom, bars_bottom_rand)

    fig.tight_layout()
    fig.savefig(outfile, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {outfile}")


def scatter_bw_latency(df: pd.DataFrame, outfile: Path):
    fig, ax = plt.subplots()

    markers = {
        "seq_read": "o",
        "rand_read": "s",
    }

    for rw in ["seq_read", "rand_read"]:
        sub = df[df["rw_norm"] == rw]
        ax.scatter(
            sub["lat_avg_us"],
            sub["bw_MBps"],
            marker=markers[rw],
            s=80,
            label=pretty_rw(rw),
        )
        for _, row in sub.iterrows():
            ax.annotate(
                str(row["ioengine"]),
                (row["lat_avg_us"], row["bw_MBps"]),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=9
            )

    ax.set_xlabel("Average Latency (us)")
    ax.set_ylabel("Bandwidth (MB/s)")
    ax.set_title("BW vs Latency by I/O Engine")
    ax.legend(frameon=False)

    fig.tight_layout()
    fig.savefig(outfile, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {outfile}")


def main():
    parser = argparse.ArgumentParser(description="Plot fio ioengine comparison results.")
    parser.add_argument("csv", help="Path to ioengine_test.csv")
    parser.add_argument("-o", "--outdir", default=".", help="Output directory")
    parser.add_argument("--with-scatter", action="store_true", help="Also generate BW-latency scatter plot")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base_style()
    df = prepare_df(csv_path)

    grouped_bar_plot_bw_broken_axis(
        df,
        outfile=outdir / "ioengine_bw_bar.png",
        lower_ylim=(0, 800),
        upper_ylim=(8000, 9200),
    )

    grouped_bar_plot(
        df,
        value_col="lat_avg_us",
        ylabel="Average Latency (us)",
        title="Latency by I/O Engine",
        outfile=outdir / "ioengine_latency_bar.png",
        y_top_padding_ratio=0.20,
        legend_loc="upper right",
        legend_bbox_to_anchor=(1.0, 1.16),
    )

    if args.with_scatter:
        scatter_bw_latency(
            df,
            outfile=outdir / "ioengine_bw_latency_scatter.png",
        )


if __name__ == "__main__":
    main()
