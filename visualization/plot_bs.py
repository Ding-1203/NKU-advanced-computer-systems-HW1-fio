import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# ===== 1. 读取数据 =====
df = pd.read_csv("bs_analysis.csv")

# ===== 2. 处理 bs 为数值（用于对数坐标）=====
def parse_bs(bs):
    bs = bs.lower()
    if 'k' in bs:
        return float(bs.replace('k', '')) * 1024
    elif 'm' in bs:
        return float(bs.replace('m', '')) * 1024 * 1024
    else:
        return float(bs)

df["bs_bytes"] = df["bs"].apply(parse_bs)

# 排序（确保折线顺序正确）
df = df.sort_values(by="bs_bytes")

# 分组
seq = df[df["type"] == "seq_read"]
rand = df[df["type"] == "rand_read"]

# ===== 3. 统一风格 =====
plt.style.use('seaborn-v0_8-whitegrid')
colors = {
    "seq": "#1f77b4",   # 蓝
    "rand": "#d62728"   # 红
}

# ===== 4. 绘图函数 =====
def plot_metric(y_col, ylabel, filename):
    plt.figure(figsize=(6, 4))

    plt.plot(seq["bs_bytes"], seq[y_col],
             marker='o', label='Sequential Read',
             color=colors["seq"], linewidth=2)

    plt.plot(rand["bs_bytes"], rand[y_col],
             marker='s', label='Random Read',
             color=colors["rand"], linewidth=2)

    # 对数横轴
    plt.xscale('log')

    # x轴标签显示为原始 bs
    plt.xticks(seq["bs_bytes"], seq["bs"])

    plt.xlabel("Block Size (bs)")
    plt.ylabel(ylabel)
    plt.title(f"{ylabel} vs Block Size")

    plt.legend()
    plt.tight_layout()

    plt.savefig(f"{filename}.png", dpi=300)
    plt.show()


# ===== 5. 生成三张图 =====
plot_metric("BW_MBps", "Bandwidth (MB/s)", "bs_bw")
plot_metric("IOPS", "IOPS", "bs_iops")
plot_metric("lat_avg_us", "Latency (us)", "bs_latency")
