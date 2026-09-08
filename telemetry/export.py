"""Export one selected run, containing only measured host metrics, for Pages."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from telemetry.server import validate


def export(database, run_id, output):
    with sqlite3.connect(database) as db:
        rows = db.execute('SELECT received_at, node, metrics FROM samples WHERE run_id=? ORDER BY id', (run_id,)).fetchall()
    if not rows:
        raise ValueError('run has no samples')
    samples = []
    for stamp, node, metrics in rows:
        sample = validate(dict(run_id=run_id, node=node, metrics=json.loads(metrics)))
        samples.append(dict(sample, received_at=stamp))
    document = dict(schema_version=1, source='linux-procfs', synthetic=False,
                    mode='published-snapshot', generated_at=datetime.now(timezone.utc).isoformat(),
                    scope='node-wide; not attributable to a training process', samples=samples)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(document, indent=2) + '\n')
    temporary.replace(target)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', default='telemetry.sqlite3')
    p.add_argument('--run-id', required=True)
    p.add_argument('--output', default='api/telemetry.json')
    args = p.parse_args()
    export(args.database, args.run_id, args.output)
