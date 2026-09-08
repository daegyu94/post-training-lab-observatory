import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from telemetry.history import archive


class HistoryTest(unittest.TestCase):
    def report(self, run_id='one'):
        return dict(synthetic=True, run=dict(run_id=run_id, name='Test run', status='completed',
                    started_at='2026-09-01T00:00:00Z', ended_at='2026-09-01T01:00:00Z', framework='Test', workload='SFT'),
                    summary=dict(run_id=run_id, configuration={'model':'test'}, metrics={'training_loss':1.2}),
                    history={'samples':[{'timestamp':'2026-09-01T00:30:00Z','metrics':{'training_loss':1.2}}], 'events':[]})

    def test_append_and_reopen_preserves_previous_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=archive(self.report(),tmp)
            first_bytes=(Path(tmp)/'one.json').read_bytes()
            archive(self.report('two'),tmp)
            self.assertEqual(len(json.loads((Path(tmp)/'index.json').read_text())['runs']),2)
            self.assertEqual((Path(tmp)/'one.json').read_bytes(),first_bytes)
            self.assertEqual(json.loads((Path(tmp)/'one.json').read_text()),first)
            self.assertEqual(first['metadata']['duration_seconds'],3600)
            with self.assertRaises(ValueError): archive(self.report(),tmp)
            self.assertEqual((Path(tmp)/'one.json').read_bytes(),first_bytes)

    def test_invalid_records_do_not_modify_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive(self.report(),tmp)
            before=(Path(tmp)/'index.json').read_bytes()
            for changes in [dict(archive_id='../escape'),dict(archive_id='index'),dict(started_at='2026-09-02T00:00:00Z'),dict(ended_at='2026-09-01T00:20:00Z'),dict(started_at='2026-09-01T00:00:00'),dict(status='failed'),dict(status='running')]:
                with self.assertRaises(ValueError): archive(self.report('two'),tmp,**changes)
            bad=self.report('two');bad['synthetic']='false'
            with self.assertRaises(ValueError): archive(bad,tmp)
            bad=self.report('two');bad['summary']['metrics']['training_loss']=float('nan')
            with self.assertRaises(ValueError): archive(bad,tmp)
            self.assertEqual((Path(tmp)/'index.json').read_bytes(),before)
            self.assertFalse((Path(tmp)/'two.json').exists())

    def test_failed_run_and_missing_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=self.report();report.pop('history')
            record=archive(report,tmp,status='failed',failure_reason='Worker failed')
            self.assertEqual(record['metadata']['failure_reason'],'Worker failed')
            self.assertEqual(record['report']['run']['status'],'failed')
            self.assertEqual(record['metadata']['sample_count'],0)
            self.assertNotIn('samples',record['history'])
            restored=archive(record,tmp,archive_id='restored')
            self.assertEqual(restored['metadata']['failure_reason'],'Worker failed')
            self.assertEqual(restored['report'],record['report'])

    def test_host_capture_keeps_scope_and_all_samples(self):
        doc=json.loads(Path('api/telemetry.json').read_text())
        original=copy.deepcopy(doc)
        with tempfile.TemporaryDirectory() as tmp:
            record=archive(doc,tmp)
            self.assertEqual(record['metadata']['kind'],'host')
            self.assertEqual(record['metadata']['status'],'captured')
            self.assertFalse(record['metadata']['synthetic'])
            self.assertIsNone(record['metadata']['gpus'])
            self.assertEqual(len(record['history']['samples']),len(doc['samples']))
            self.assertEqual(doc,original)
            with self.assertRaises(ValueError):archive(doc,tmp,archive_id='invalid',status='completed')

    def test_published_registry_references_complete_archives(self):
        root=Path('api/history');index=json.loads((root/'index.json').read_text())
        ids=[row['archive_id'] for row in index['runs']]
        self.assertEqual(len(ids),len(set(ids)))
        for row in index['runs']:
            doc=json.loads((root/(row['archive_id']+'.json')).read_text())
            self.assertEqual(doc['metadata'],row)
            self.assertEqual(len(doc['history'].get('samples',[])),row['sample_count'])

    def test_concurrent_archives_keep_every_index_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda i: archive(self.report('run-'+str(i)),tmp),range(8)))
            rows=json.loads((Path(tmp)/'index.json').read_text())['runs']
            self.assertEqual(len(rows),8)
            self.assertEqual(len({r['archive_id'] for r in rows}),8)
