#!/usr/bin/env python3
import re
import csv
import argparse
from pathlib import Path
from collections import defaultdict


HEADER_RE = re.compile(
    r'^(?P<name>[^:]+): \(g=\d+\): rw=(?P<rw>[^,]+), .*?ioengine=(?P<ioengine>[^,]+), iodepth=(?P<iodepth>\d+)'
)

JOB_START_RE = re.compile(
    r'^(?P<name>[^:]+): \(groupid=(?P<groupid>\d+), jobs=(?P<jobs>\d+)\):'
)

BS_RE = re.compile(
    r'bs=\(R\)\s*(?P<rbs>[^-]+)-'
)

IOPS_BW_RE = re.compile(
    r'^\s*(read|write): IOPS=(?P<iops>[0-9.]+)(?P<iops_unit>[kKmM]?)[, ]+BW=(?P<bw>[0-9.]+)(?P<bw_unit>[KMG]i?B/s|\w+B/s)'
)

CLAT_NS_RE = re.compile(
    r'^\s*clat \((?P<unit>nsec|usec|msec)\): .*?avg=(?P<avg>[0-9.]+)'
)

LAT_NS_RE = re.compile(
    r'^\s*lat \((?P<unit>nsec|usec|msec)\): .*?avg=(?P<avg>[0-9.]+)'
)

# 兼容 clat (usec): min=2, max=..., avg= 4.34, stdev=...
CLAT_SIMPLE_RE = re.compile(
    r'^\s*clat \((?P<unit>nsec|usec|msec)\): .*?avg=\s*(?P<avg>[0-9.]+)'
)

LAT_SIMPLE_RE = re.compile(
    r'^\s*lat \((?P<unit>nsec|usec|msec)\): .*?avg=\s*(?P<avg>[0-9.]+)'
)


def iops_to_number(val: str, unit: str) -> float:
    x = float(val)
    unit = unit.lower()
    if unit == 'k':
        return x * 1_000
    if unit == 'm':
        return x * 1_000_000
    return x


def bw_to_mbps(val: str, unit: str) -> float:
    """
    统一转成 MB/s（十进制），便于画图和表格比较
    支持 KiB/s, MiB/s, GiB/s, KB/s, MB/s, GB/s
    """
    x = float(val)
    unit = unit.strip()

    mapping = {
        'KiB/s': 1024 / 1_000_000,
        'MiB/s': 1024 * 1024 / 1_000_000,
        'GiB/s': 1024 * 1024 * 1024 / 1_000_000,
        'KB/s': 1 / 1000,
        'MB/s': 1,
        'GB/s': 1000,
    }
    if unit not in mapping:
        raise ValueError(f'Unsupported BW unit: {unit}')
    return x * mapping[unit]


def latency_to_us(avg: str, unit: str) -> float:
    x = float(avg)
    if unit == 'nsec':
        return x / 1000.0
    if unit == 'usec':
        return x
    if unit == 'msec':
        return x * 1000.0
    raise ValueError(f'Unsupported latency unit: {unit}')


def parse_header_blocks(lines):
    """
    先解析顶部声明块，获取每个 job 的静态信息：
    name, rw, bs, ioengine, iodepth
    """
    meta = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        m = HEADER_RE.match(line)
        if m:
            name = m.group('name').strip()
            rw = m.group('rw').strip()
            ioengine = m.group('ioengine').strip()
            iodepth = int(m.group('iodepth'))
            bs_match = BS_RE.search(line)
            bs = bs_match.group('rbs').strip() if bs_match else ''

            meta[name] = {
                'job_name': name,
                'rw': rw,
                'bs': bs,
                'ioengine': ioengine,
                'iodepth': iodepth,
            }
        i += 1
    return meta


def parse_results(lines, meta):
    """
    解析每个 groupid/job 的运行结果
    """
    rows = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = JOB_START_RE.match(line)
        if not m:
            i += 1
            continue

        name = m.group('name').strip()
        groupid = int(m.group('groupid'))
        jobs = int(m.group('jobs'))

        row = {
            'job_name': name,
            'groupid': groupid,
            'jobs': jobs,
            'rw': meta.get(name, {}).get('rw', ''),
            'bs': meta.get(name, {}).get('bs', ''),
            'ioengine': meta.get(name, {}).get('ioengine', ''),
            'iodepth': meta.get(name, {}).get('iodepth', ''),
            'iops': None,
            'bw_MBps': None,
            'lat_avg_us': None,
            'clat_avg_us': None,
        }

        j = i + 1
        while j < len(lines):
            next_line = lines[j]

            # 下一个 job 开始，停止
            if JOB_START_RE.match(next_line):
                break

            m_iops = IOPS_BW_RE.match(next_line)
            if m_iops:
                row['iops'] = iops_to_number(m_iops.group('iops'), m_iops.group('iops_unit'))
                row['bw_MBps'] = bw_to_mbps(m_iops.group('bw'), m_iops.group('bw_unit'))

            m_clat = CLAT_SIMPLE_RE.match(next_line) or CLAT_NS_RE.match(next_line)
            if m_clat:
                row['clat_avg_us'] = latency_to_us(m_clat.group('avg'), m_clat.group('unit'))

            m_lat = LAT_SIMPLE_RE.match(next_line) or LAT_NS_RE.match(next_line)
            if m_lat:
                row['lat_avg_us'] = latency_to_us(m_lat.group('avg'), m_lat.group('unit'))

            j += 1

        # 如果没有 lat，就退回用 clat
        if row['lat_avg_us'] is None and row['clat_avg_us'] is not None:
            row['lat_avg_us'] = row['clat_avg_us']

        rows.append(row)
        i = j

    return rows


def aggregate_rows(rows):
    """
    对 numjobs>1 的情况，同名 job 会有多个子进程结果。
    这里按 job_name 聚合：
    - iops 求和
    - bw 求和
    - latency 取平均
    """
    grouped = defaultdict(list)
    for r in rows:
        grouped[r['job_name']].append(r)

    agg_rows = []
    for job_name, items in grouped.items():
        first = items[0]
        agg = dict(first)
        agg['subjobs'] = len(items)

        def vals(key):
            return [x[key] for x in items if x[key] is not None]

        iops_vals = vals('iops')
        bw_vals = vals('bw_MBps')
        lat_vals = vals('lat_avg_us')
        clat_vals = vals('clat_avg_us')

        agg['iops'] = sum(iops_vals) if iops_vals else None
        agg['bw_MBps'] = sum(bw_vals) if bw_vals else None
        agg['lat_avg_us'] = sum(lat_vals) / len(lat_vals) if lat_vals else None
        agg['clat_avg_us'] = sum(clat_vals) / len(clat_vals) if clat_vals else None

        # 从 job 名中尽量提取 numjobs / iodepth
        # 例如 seq_read_n4_d16
        m = re.search(r'_n(?P<numjobs>\d+)_d(?P<iodepth>\d+)$', job_name)
        if m:
            agg['numjobs'] = int(m.group('numjobs'))
            agg['iodepth'] = int(m.group('iodepth'))
        else:
            agg['numjobs'] = first.get('jobs', 1)

        agg_rows.append(agg)

    return agg_rows


def write_csv(rows, out_path):
    fields = [
        'job_name',
        'groupid',
        'jobs',
        'subjobs',
        'rw',
        'bs',
        'numjobs',
        'iodepth',
        'ioengine',
        'iops',
        'bw_MBps',
        'lat_avg_us',
        'clat_avg_us',
    ]
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main():
    parser = argparse.ArgumentParser(description='Convert fio txt output to CSV.')
    parser.add_argument('input', help='Path to fio txt output')
    parser.add_argument('-o', '--output', help='Output CSV path')
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path.with_suffix('.csv')

    text = in_path.read_text(encoding='utf-8', errors='ignore')
    lines = text.splitlines()

    meta = parse_header_blocks(lines)
    raw_rows = parse_results(lines, meta)
    agg_rows = aggregate_rows(raw_rows)

    # 按 groupid 排序，更符合原输出顺序
    agg_rows.sort(key=lambda x: (x.get('groupid', 0), x.get('job_name', '')))

    write_csv(agg_rows, out_path)
    print(f'Wrote CSV: {out_path}')


if __name__ == '__main__':
    main()
