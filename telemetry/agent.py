"""Sample Linux host counters and push actual interval metrics to Observatory."""
import argparse
import json
import os
from pathlib import Path
import socket
import time
from urllib.request import Request, urlopen


def counters():
    # guest counters are already included in user/nice; exclude them from total.
    cpu = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    mem = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
    net = {}
    for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
        name, values = line.split(':')
        name = name.strip()
        if name == 'lo' or name.startswith(('veth', 'docker', 'br-')):
            continue
        values = list(map(int, values.split()))
        net[name] = (values[0], values[8])
    return time.monotonic(), sum(cpu), cpu[3] + cpu[4], mem, net


def metrics(before, after):
    elapsed = after[0] - before[0]
    total = after[1] - before[1]
    if elapsed <= 0 or total <= 0:
        raise ValueError('sampling interval did not advance')
    net = [sum(max(0, after[4][n][i] - before[4][n][i]) for n in before[4].keys() & after[4].keys()) * 8 / elapsed / 1e9 for i in (0, 1)]
    mem = after[3]
    return dict(cpu_utilization_percent=round(100 * (1 - (after[2] - before[2]) / total), 3),
                memory_used_gib=(mem['MemTotal'] - mem['MemAvailable']) / 1024**2,
                memory_total_gib=mem['MemTotal'] / 1024**2,
                memory_available_gib=mem['MemAvailable'] / 1024**2,
                swap_used_gib=(mem['SwapTotal'] - mem['SwapFree']) / 1024**2,
                swap_total_gib=mem['SwapTotal'] / 1024**2,
                nic_receive_gbps=net[0], nic_transmit_gbps=net[1], interval_seconds=elapsed)


def post(endpoint, token, path, data):
    request = Request(endpoint.rstrip('/') + path, data=json.dumps(data).encode(), headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urlopen(request, timeout=10) as response:
        if response.status != 201:
            raise RuntimeError('collector rejected sample')


def framework_samples(directory, seen):
    if directory is None:
        return []
    samples = []
    for path in sorted(directory.glob('*.json')):
        try:
            sample = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        marker = sample.get('observed_at')
        if marker != seen.get(path):
            seen[path] = marker
            samples.append(sample)
    return samples


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--endpoint', required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--node', default=socket.gethostname())
    p.add_argument('--interval', type=float, default=2)
    p.add_argument('--samples', type=int, default=30)
    p.add_argument('--framework-metrics-dir', type=Path)
    args = p.parse_args()
    if args.interval <= 0 or args.samples <= 0:
        p.error('interval and samples must be positive')
    token = os.environ['OBSERVATORY_TOKEN']
    seen = {}
    before = counters()
    for _ in range(args.samples):
        time.sleep(args.interval)
        after = counters()
        data = dict(run_id=args.run_id, node=args.node, metrics=metrics(before, after))
        post(args.endpoint, token, '/api/telemetry', data)
        for sample in framework_samples(args.framework_metrics_dir, seen):
            if sample.get('run_id') != args.run_id:
                raise ValueError('framework metric run_id must match the agent')
            sample = dict(sample, node=args.node)
            post(args.endpoint, token, '/api/framework-metrics', sample)
        print(json.dumps(data), flush=True)
        before = after


if __name__ == '__main__':
    main()
