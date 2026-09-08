"""Archive profiling reports or host snapshots for the static history viewer."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import tempfile

from telemetry.server import validate

STATUSES = {'running', 'completed', 'failed', 'cancelled', 'captured'}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be an ISO 8601 string')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timestamp must include a timezone')
    return result


def atomic_json(path, value):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.archive-')
    try:
        with os.fdopen(descriptor, 'w') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def archive(document, root, *, archive_id=None, name=None, status=None,
            started_at=None, ended_at=None, failure_reason=None):
    """Append an immutable archive; the registry is replaced atomically last."""
    if 'metadata' in document and 'report' in document:
        metadata = document['metadata']
        archive_id = archive_id or metadata['archive_id']
        status = status or metadata['status']
        started_at = started_at or metadata['started_at']
        ended_at = ended_at or metadata['ended_at']
        failure_reason = failure_reason or metadata.get('failure_reason')
        document = {**document['report'], 'history': document['history']}
    if type(document.get('synthetic')) is not bool:
        raise ValueError('synthetic must explicitly be true or false')
    host = document.get('source') == 'linux-procfs'
    if host:
        if document['synthetic'] is not False or not document.get('samples'):
            raise ValueError('host archive requires measured samples')
        samples = sorted(document['samples'], key=lambda sample: timestamp(sample['received_at']))
        for sample in samples:
            validate({key: sample[key] for key in ('run_id', 'node', 'metrics')})
        ids = {sample['run_id'] for sample in samples}
        if len(ids) != 1:
            raise ValueError('archive one run at a time')
        run_id = ids.pop()
        status = status or 'captured'
        if status != 'captured':
            raise ValueError('node snapshots use captured status, not a training outcome')
        started_at = started_at or samples[0]['received_at']
        ended_at = ended_at or samples[-1]['received_at']
        run = dict(run_id=run_id, name=name or run_id, framework='Linux /proc',
                   workload='Host observation', nodes=len({s['node'] for s in samples}), gpus=None)
        history = dict(samples=samples, events=[], configuration=None)
    else:
        run = dict(document['run'])
        run_id = run['run_id']
        if document['summary']['run_id'] != run_id:
            raise ValueError('summary run_id does not match the report')
        metrics = document['summary']['metrics']
        if not isinstance(metrics, dict) or any(type(v) not in (int, float) or not math.isfinite(v) for v in metrics.values()):
            raise ValueError('summary metrics must be finite numbers')
        for key in ('resources', 'storage', 'interconnect', 'data_movement'):
            if key in document and document[key].get('run_id') != run_id:
                raise ValueError(key + ' run_id does not match the report')
        status = status or run.get('status')
        started_at = started_at or run.get('started_at')
        ended_at = ended_at or run.get('ended_at')
        history = dict(document.get('history') or {})
        history['configuration'] = document['summary'].get('configuration', {})
        run['name'] = name or run.get('name', run_id)
    archive_id = archive_id or run_id
    if not isinstance(archive_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,96}', archive_id):
        raise ValueError('archive_id must use 1..96 letters, digits, underscores or hyphens')
    if archive_id == 'index':
        raise ValueError('index is a reserved archive ID')
    if status not in STATUSES or (not host and status == 'captured'):
        raise ValueError('invalid run status')
    start = timestamp(started_at)
    if status != 'running' and not ended_at:
        raise ValueError('finished runs require ended_at')
    if status == 'running' and ended_at:
        raise ValueError('running snapshots cannot have ended_at')
    end = timestamp(ended_at) if ended_at else None
    if end and end < start:
        raise ValueError('ended_at precedes started_at')
    for item in history.get('samples', []) + history.get('events', []):
        when = timestamp(item.get('timestamp', item.get('received_at')))
        if when < start or (end and when > end):
            raise ValueError('history item falls outside the run interval')
    for sample in history.get('samples', []):
        if not isinstance(sample.get('metrics'), dict) or any(type(v) not in (int, float) or not math.isfinite(v) for v in sample['metrics'].values()):
            raise ValueError('sample metrics must be finite numbers')
    if status == 'failed' and not failure_reason:
        raise ValueError('failed runs require a failure reason')
    archived_at = datetime.now(timezone.utc).isoformat()
    metadata = dict(archive_id=archive_id, run_id=run_id, name=run['name'],
                    kind='host' if host else 'training', synthetic=document['synthetic'],
                    status=status, started_at=started_at, ended_at=ended_at,
                    archived_at=archived_at, duration_seconds=(end-start).total_seconds() if end else None,
                    framework=run.get('framework'), workload=run.get('workload'),
                    nodes=run.get('nodes'), gpus=run.get('gpus'), failure_reason=failure_reason,
                    sample_count=len(history.get('samples', [])))
    if not host:
        document = {**document, 'history': history, 'run': {**run, 'status': status,
                    'started_at': started_at, 'ended_at': ended_at}}
    result = dict(schema_version=1, metadata=metadata, history=history, report=document)
    # Serialize before touching the archive to reject NaN and unsupported values.
    json.dumps(result, allow_nan=False)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = os.open(root, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        index_path = root / 'index.json'
        index = json.loads(index_path.read_text()) if index_path.exists() else dict(schema_version=1, runs=[])
        target = root / (archive_id + '.json')
        if target.exists() or any(r['archive_id'] == archive_id for r in index['runs']):
            raise ValueError('archive already exists; use a new archive_id')
        atomic_json(target, result)
        index['runs'].append(metadata)
        index['runs'].sort(key=lambda row: timestamp(row['started_at']), reverse=True)
        try:
            atomic_json(index_path, index)
        except Exception:
            target.unlink()
            raise
    finally:
        os.close(lock)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output-dir', default='api/history', type=Path)
    parser.add_argument('--archive-id')
    parser.add_argument('--name')
    parser.add_argument('--status', choices=sorted(STATUSES))
    parser.add_argument('--started-at')
    parser.add_argument('--ended-at')
    parser.add_argument('--failure-reason')
    args = parser.parse_args()
    try:
        record = archive(json.loads(args.input.read_text()), args.output_dir,
                         archive_id=args.archive_id, name=args.name, status=args.status,
                         started_at=args.started_at, ended_at=args.ended_at,
                         failure_reason=args.failure_reason)
    except (ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Invalid archive: {error}\n')
    print('Archived ' + record['metadata']['archive_id'])
