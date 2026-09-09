"""Small authenticated lab collector; stdlib only. Run from any directory."""
import argparse
import hmac
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('cpu_utilization_percent', 'memory_used_gib', 'memory_total_gib',
          'nic_receive_gbps', 'nic_transmit_gbps', 'interval_seconds',
          'memory_available_gib', 'swap_used_gib', 'swap_total_gib')
FRAMEWORK_FIELDS = {'training_loss', 'training_step_time_seconds',
                    'training_tokens_per_second'}


def validate(data):
    if not isinstance(data, dict) or set(data) != {'run_id', 'node', 'metrics'}:
        raise ValueError('expected run_id, node, metrics')
    for key in ('run_id', 'node'):
        if not isinstance(data[key], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', data[key]):
            raise ValueError('invalid identifier')
    m = data['metrics']
    if not isinstance(m, dict) or set(m) != set(FIELDS):
        raise ValueError('invalid metric fields')
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in m.values()):
        raise ValueError('metrics must be finite nonnegative numbers')
    if m['cpu_utilization_percent'] > 100 or m['interval_seconds'] <= 0 or m['memory_total_gib'] <= 0 or m['memory_used_gib'] > m['memory_total_gib'] or m['memory_available_gib'] > m['memory_total_gib'] or m['swap_used_gib'] > m['swap_total_gib']:
        raise ValueError('invalid metric range')
    return data


def validate_framework(data):
    expected = {'schema_version', 'run_id', 'framework', 'node', 'rank',
                'local_rank', 'step', 'observed_at', 'metrics', 'timers'}
    if not isinstance(data, dict) or set(data) != expected or data['schema_version'] != 1:
        raise ValueError('invalid framework sample fields')
    for key in ('run_id', 'node'):
        if not isinstance(data[key], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', data[key]):
            raise ValueError('invalid identifier')
    if data['framework'] not in {'trl', 'megatron'}:
        raise ValueError('invalid framework')
    if any(type(data[key]) is not int or data[key] < 0 for key in ('rank', 'local_rank', 'step')):
        raise ValueError('invalid rank or step')
    if type(data['observed_at']) not in (int, float) or not math.isfinite(data['observed_at']) or data['observed_at'] < 0:
        raise ValueError('invalid observation time')
    metrics, timers = data['metrics'], data['timers']
    if not isinstance(metrics, dict) or not metrics or set(metrics) - FRAMEWORK_FIELDS:
        raise ValueError('invalid framework metrics')
    if not isinstance(timers, dict) or len(timers) > 32 or any(not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', key) for key in timers):
        raise ValueError('invalid framework timers')
    values = [*metrics.values(), *timers.values()]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values):
        raise ValueError('framework metrics must be finite nonnegative numbers')
    return data


def validate_origin(value):
    if value is None:
        return None
    origin = value.rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or origin != f'{parsed.scheme}://{parsed.netloc}':
        raise ValueError('CORS origin must be one exact HTTP(S) origin')
    return origin


def make_server(address, database, token, cors_origin=None):
    cors_origin = validate_origin(cors_origin)
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY, received_at TEXT, run_id TEXT, node TEXT, metrics TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS framework_samples (id INTEGER PRIMARY KEY, received_at TEXT, run_id TEXT, framework TEXT, node TEXT, rank INTEGER, sample TEXT)')

    class Handler(BaseHTTPRequestHandler):
        def cors_allowed(self):
            origin = self.headers.get('Origin', '')
            return cors_origin is not None and hmac.compare_digest(origin, cors_origin)

        def reply(self, status, body, mime='application/json'):
            payload = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            if self.cors_allowed():
                self.send_header('Access-Control-Allow-Origin', cors_origin)
                self.send_header('Vary', 'Origin')
            self.end_headers()
            self.wfile.write(payload)

        def authorized(self):
            return hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token)

        def do_OPTIONS(self):
            if self.path not in ('/api/telemetry', '/api/framework-metrics') or not self.cors_allowed():
                return self.reply(403, {'error': 'origin not allowed'})
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', cors_origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            self.send_header('Access-Control-Max-Age', '600')
            self.send_header('Vary', 'Origin')
            self.end_headers()

        def do_GET(self):
            if self.path in ('/', '/telemetry.html'):
                return self.reply(200, (ROOT / 'telemetry.html').read_bytes(), 'text/html; charset=utf-8')
            theme_assets = {
                '/assets/theme.js': 'text/javascript; charset=utf-8',
                '/assets/theme.css': 'text/css; charset=utf-8',
            }
            if self.path in theme_assets:
                return self.reply(200, (ROOT / self.path[1:]).read_bytes(), theme_assets[self.path])
            if self.path == '/healthz':
                return self.reply(200, {'status': 'ok'})
            if self.path not in ('/api/telemetry', '/api/framework-metrics'):
                return self.reply(404, {'error': 'not found'})
            if not self.authorized():
                return self.reply(401, {'error': 'unauthorized'})
            with sqlite3.connect(database) as db:
                if self.path == '/api/telemetry':
                    rows = db.execute('SELECT received_at, run_id, node, metrics FROM samples ORDER BY id DESC LIMIT 1000').fetchall()
                    body = {'source': 'linux-procfs', 'synthetic': False, 'samples': [dict(received_at=t, run_id=r, node=n, metrics=json.loads(m)) for t, r, n, m in rows]}
                else:
                    rows = db.execute('SELECT received_at, sample FROM framework_samples ORDER BY id DESC LIMIT 1000').fetchall()
                    body = {'source': 'framework-adapter', 'synthetic': False, 'samples': [dict(json.loads(sample), received_at=stamp) for stamp, sample in rows]}
            self.reply(200, body)

        def do_POST(self):
            if self.path not in ('/api/telemetry', '/api/framework-metrics'):
                return self.reply(404, {'error': 'not found'})
            if not self.authorized():
                return self.reply(401, {'error': 'unauthorized'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    return self.reply(413, {'error': 'body must be 1..16384 bytes'})
                self.connection.settimeout(10)
                raw = json.loads(self.rfile.read(size))
                data = validate(raw) if self.path == '/api/telemetry' else validate_framework(raw)
            except (ValueError, TypeError, OSError):
                return self.reply(400, {'error': 'invalid sample'})
            stamp = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(database) as db:
                if self.path == '/api/telemetry':
                    db.execute('INSERT INTO samples(received_at, run_id, node, metrics) VALUES (?, ?, ?, ?)', (stamp, data['run_id'], data['node'], json.dumps(data['metrics'])))
                    db.execute('DELETE FROM samples WHERE id <= (SELECT COALESCE(MAX(id),0) - 10000 FROM samples)')
                else:
                    db.execute('INSERT INTO framework_samples(received_at, run_id, framework, node, rank, sample) VALUES (?, ?, ?, ?, ?, ?)', (stamp, data['run_id'], data['framework'], data['node'], data['rank'], json.dumps(data)))
                    db.execute('DELETE FROM framework_samples WHERE id <= (SELECT COALESCE(MAX(id),0) - 10000 FROM framework_samples)')
            self.reply(201, {'received_at': stamp})

    return ThreadingHTTPServer(address, Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--database', default='telemetry.sqlite3')
    parser.add_argument('--cors-origin', help='exact browser origin allowed to call the collector')
    args = parser.parse_args()
    token = os.environ.get('OBSERVATORY_TOKEN', '')
    if len(token) < 24 or not token.isascii():
        parser.error('set OBSERVATORY_TOKEN to at least 24 ASCII characters')
    try:
        server = make_server((args.bind, args.port), args.database, token, args.cors_origin)
    except ValueError as error:
        parser.error(str(error))
    server.serve_forever()
