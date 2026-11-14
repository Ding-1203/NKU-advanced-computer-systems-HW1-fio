#!/usr/bin/env python3
from pathlib import Path
import argparse
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


def normalize_label(job_name: str, rw: str) -> str:
    """
    优先根据 job_name 判断，其次根据 rw 判断。
    输出统一用于图表展示。
    """
    name = str(job_name).strip().lower()
    rw = str(rw).strip().lower()

    if "seq_read" in name or rw == "read":
        if "rand" not in name:
            return "Sequential Read"
    if "seq_write" in name or rw == "write":
        if "rand" not in name:
            return "Sequential Write"
    if "rand_read" in name or rw == "randread":
        return "Random Read"
    if "rand_write" in name or rw == "randwrite":
        return "Random Write"

    return str(job_name)


def infer_engine(df: pd.DataFrame, cli_engine: str | None) -> str:
    if cli_engine:
        return cli_engine
    if "ioengine" in df.columns and df["ioengine"].notna().any():
        vals = df["ioengine"].dropna().astype(str).unique().tolist()
        if len(vals) == 1:
            return vals[0]
        if len(vals) > 1:
            return "mixed"
    return "unknown"


def base_style():
    plt.style.use("default")
    plt.rcParams.update({
        "figure.figsize": (8.2, 4.8),
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "axes.facecolor": "#fbfcfe",
        "figure.facecolor": "#ffffff",
        "axes.grid": True,
        "grid.alpha": 0.18,
        "grid.linestyle": "-",
        "grid.color": "#6b7280",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#d7dde8",
    })


def main():
    parser = argparse.ArgumentParser(description="Plot basic fio results.")
    parser.add_argument("csv", help="Path to basic_test.csv")
    parser.add_argument("-o", "--outdir", default=".", help="Output directory")
    parser.add_argument("-e", "--engine", default=None, help="Override engine label")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)

    required = {"job_name", "rw", "bw_MBps", "lat_avg_us"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV 缺少必要列: {sorted(missing)}")

    df = df.copy()
    df["bw_MBps"] = pd.to_numeric(df["bw_MBps"], errors="coerce")
    df["lat_avg_us"] = pd.to_numeric(df["lat_avg_us"], errors="coerce")
    df["label"] = df.apply(lambda r: normalize_label(r["job_name"], r["rw"]), axis=1)

    # 只保留基础测试常见四类
    order = ["Sequential Read", "Sequential Write", "Random Read", "Random Write"]
    df = df[df["label"].isin(order)].copy()
    df["label"] = pd.Categorical(df["label"], categories=order, ordered=True)
    df = df.sort_values("label")

    engine = infer_engine(df, args.engine)

    base_style()

    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()

    labels = df["label"].astype(str).tolist()
    x = list(range(len(df)))

    palette = {
        "Sequential Read": "#4C78A8",
        "Sequential Write": "#F58518",
        "Random Read": "#54A24B",
        "Random Write": "#E45756",
    }
    bar_colors = [palette.get(label, "#8093b0") for label in labels]

    # 柱状图：BW
    bars = ax1.bar(
        x,
        df["bw_MBps"],
        width=0.62,
        color=bar_colors,
        edgecolor="#f8fafc",
        linewidth=1.0,
        alpha=0.94,
        label="Bandwidth",
    )

    # 折线图：Latency
    ax2.plot(
        x,
        df["lat_avg_us"],
        marker="o",
        linewidth=2.2,
        markersize=6,
        color="#2F3E46",
        markerfacecolor="#ffffff",
        markeredgewidth=1.5,
        label="Average Latency",
    )

    # x轴
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels)
    for tick, c in zip(ax1.get_xticklabels(), bar_colors):
        tick.set_color(c)
        tick.set_fontweight("semibold")

    # 轴标签
    ax1.set_ylabel("Bandwidth (MB/s)")
    ax2.set_ylabel("Average Latency (us)")
    ax1.set_xlabel("Access Pattern")

    # 两侧比例尺留白，避免数据贴到图顶
    bw_max = float(df["bw_MBps"].max())
    lat_max = float(df["lat_avg_us"].max())
    ax1.set_ylim(0, bw_max * 1.18 if bw_max > 0 else 1)
    ax2.set_ylim(0, lat_max * 1.20 if lat_max > 0 else 1)

    # 统一网格：仅保留左轴水平主网格，右轴不单独画网格
    ax1.grid(axis="x", visible=False)
    ax1.grid(axis="y", which="major", color="#6b7280", alpha=0.20, linewidth=0.8)
    ax2.grid(False)

    ax1.tick_params(axis="y", colors="#334155")
    ax2.tick_params(axis="y", colors="#2F3E46")
    ax2.spines["right"].set_color("#d7dde8")

    # 标题
    ax1.set_title(f"Basic fio Performance (engine={engine})")

    # 给柱子标数值
    for rect, val in zip(bars, df["bw_MBps"]):
        ax1.text(
            rect.get_x() + rect.get_width() / 2,
            rect.get_height() + (bw_max * 0.01 if bw_max > 0 else 0.1),
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#0f172a"
        )

    # 给折线点标数值
    for xi, val in zip(x, df["lat_avg_us"]):
        ax2.annotate(
            f"{val:.1f}",
            (xi, val),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=9,
            color="#2F3E46",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": "#ffffff", "edgecolor": "none", "alpha": 0.85}
        )

    # 图例合并：用代理对象展示系列含义，避免多色柱子导致图例混乱
    legend_handles = [
        Patch(facecolor="#4C78A8", edgecolor="none", label="Bandwidth by Pattern"),
        Line2D([0], [0], color="#2F3E46", marker="o", markerfacecolor="#ffffff", lw=2.2, label="Average Latency"),
    ]
    ax1.legend(handles=legend_handles, frameon=False, loc="upper left")

    fig.tight_layout()

    out = outdir / f"basic_{engine}_bw_latency_combo.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)

    print(f"[OK] {out}")


if __name__ == "__main__":
    main()
