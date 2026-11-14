# hw1-fio

本项目是《计算机系统前沿》作业 1 的 fio 实验代码与结果汇总，包含：

- fio 测试脚本（不同参数组合）
- 原始测试输出结果
- 文本转 CSV 与绘图脚本
- 最终实验报告

## 项目结构

```text
hw1-fio/
├── README.md
├── report.md                        # 实验报告（结论分析）
├── fio_test_file                    # 5GB 测试文件（fio 读写对象）
├── scripts/                         # fio 配置脚本
│   ├── basic_test.fio               # 基础四类测试（顺序读/写、随机读/写）
│   ├── bs_test.fio                  # 块大小（bs）对性能影响
│   ├── ioengine_test.fio            # I/O 引擎对比（psync/libaio/io_uring/mmap）
│   ├── qd_jobs_test_psync.fio       # 并发参数测试（psync）
│   ├── qd_jobs_test_libaio.fio      # 并发参数测试（libaio）
│   └── qd_jobs_test_uring.fio       # 并发参数测试（io_uring）
├── results/                         # fio 原始输出（txt）
│   ├── basic_test.txt
│   ├── bs_test.txt
│   ├── ioengine_test.txt
│   ├── qd_jobs_test_psync.txt
│   ├── qd_jobs_test_libaio.txt
│   └── qd_jobs_test_uring.txt
└── visualization/                   # 数据处理与可视化
    ├── fio_txt_to_csv.py            # txt 结果解析为 CSV
    ├── plot_basic.py                # 基础测试图
    ├── plot_bs.py                   # bs 相关图
    ├── plot_ioengine.py             # ioengine 对比图
    ├── plot_qd_jobs.py              # numjobs/iodepth 热力图与曲线图
    ├── *.csv                        # 清洗后的实验数据
    └── *.png                        # 导出的图像
```

## 目录说明（按流程）

1. 在 `scripts/` 中执行 fio 脚本，得到原始输出。  
2. 原始输出保存到 `results/`（`.txt`）。  
3. 使用 `visualization/fio_txt_to_csv.py` 解析文本，生成 `.csv`。  
4. 使用 `visualization/plot_*.py` 生成图表（`.png`）。  
5. 在 `report.md` 中汇总实验现象与结论。

## 快速开始（示例）

在项目根目录执行某个测试脚本：

```bash
fio scripts/basic_test.fio > results/basic_test.txt
```

在 `visualization/` 中进行解析与绘图（示例）：

```bash
cd visualization
python3 fio_txt_to_csv.py ../results/basic_test.txt basic_test.csv
python3 plot_basic.py basic_test.csv -o .
```

> 注：项目中的 CSV 与 PNG 多数已生成，可直接查看与复用。
