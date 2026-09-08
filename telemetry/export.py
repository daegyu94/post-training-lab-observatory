"""Export one selected run, containing only measured host metrics, for Pages."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from telemetry.server import validate


def export(database, run_id, output, archive_dir=None, archive_id=None):
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
    if archive_dir is not None:
        from telemetry.history import archive
        archive(document, archive_dir, archive_id=archive_id)
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
    p.add_argument('--archive-dir', help='also retain an immutable run archive and update its index')
    p.add_argument('--archive-id', help='unique archive ID; defaults to the run ID')
    args = p.parse_args()
    export(args.database, args.run_id, args.output, args.archive_dir, args.archive_id)
