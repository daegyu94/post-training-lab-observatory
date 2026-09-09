import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from telemetry.server import make_server, validate_framework
from telemetry.agent import framework_samples, metrics
from telemetry.export import export

class TelemetryTest(unittest.TestCase):
    def test_math(self):
        m = metrics((1,100,50,{}, {'eth0':(10,20)}), (3,200,75,{'MemTotal':2097152,'MemAvailable':1048576,'SwapTotal':1048576,'SwapFree':524288},{'eth0':(250000010,500000020)}))
        self.assertEqual(m['cpu_utilization_percent'],75)
        self.assertEqual(m['memory_used_gib'],1)
        self.assertEqual(m['swap_used_gib'],0.5)
        self.assertEqual(m['nic_receive_gbps'],1)
        self.assertEqual(m['nic_transmit_gbps'],2)

    def test_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            database=str(Path(tmp)/'db')
            server=make_server(('127.0.0.1',0),database,'x'*32)
            thread=threading.Thread(target=server.serve_forever);thread.start()
            endpoint='http://127.0.0.1:'+str(server.server_port)+'/api/telemetry'
            sample=dict(run_id='test',node='spark1',metrics=dict(cpu_utilization_percent=25,memory_used_gib=1,memory_total_gib=2,memory_available_gib=1,swap_used_gib=0,swap_total_gib=1,nic_receive_gbps=0,nic_transmit_gbps=0,interval_seconds=2))
            def request(data=None,token='x'*32):
                return urlopen(Request(endpoint,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+token}),timeout=2)
            try:
                base = endpoint.removesuffix('/api/telemetry')
                for asset, mime in [('theme.js', 'text/javascript'), ('theme.css', 'text/css')]:
                    with urlopen(base + '/assets/' + asset, timeout=2) as r:
                        self.assertEqual(r.status, 200)
                        self.assertEqual(r.headers.get_content_type(), mime)
                        self.assertTrue(r.read())
                with self.assertRaises(HTTPError) as missing:
                    urlopen(base + '/assets/../telemetry/server.py', timeout=2)
                self.assertEqual(missing.exception.code, 404)
                with self.assertRaises(HTTPError) as e: request(sample,'wrong')
                self.assertEqual(e.exception.code,401)
                with request(sample) as r: self.assertEqual(r.status,201)
                sample['metrics']['cpu_utilization_percent']=float('nan')
                with self.assertRaises(HTTPError) as e: request(sample)
                self.assertEqual(e.exception.code,400)
                with request() as r: self.assertEqual(len(json.load(r)['samples']),1)
                framework=dict(schema_version=1,run_id='test',framework='megatron',node='spark1',rank=0,local_rank=0,step=1,observed_at=1.0,metrics={'training_loss':1.25,'training_tokens_per_second':10.0},timers={'forward-backward':0.5})
                framework_endpoint=base+'/api/framework-metrics'
                with urlopen(Request(framework_endpoint,data=json.dumps(framework).encode(),headers={'Authorization':'Bearer '+'x'*32}),timeout=2) as r:self.assertEqual(r.status,201)
                with urlopen(Request(framework_endpoint,headers={'Authorization':'Bearer '+'x'*32}),timeout=2) as r:
                    body=json.load(r);self.assertEqual(body['source'],'framework-adapter');self.assertEqual(body['samples'][0]['metrics']['training_loss'],1.25)
                output=Path(tmp)/'snapshot.json'
                archive_dir=Path(tmp)/'history'
                export(database,'test',output,archive_dir)
                self.assertEqual(json.loads((archive_dir/'index.json').read_text())['runs'][0]['status'],'captured')
                self.assertFalse(json.loads(output.read_text())['synthetic'])
                with self.assertRaises(ValueError): export(database,'missing',output)
            finally:
                server.shutdown();server.server_close();thread.join()
            restarted=make_server(('127.0.0.1',0),database,'x'*32);restarted.server_close()
            export(database,'test',output)
            self.assertEqual(len(json.loads(output.read_text())['samples']),1)

    def test_framework_validation_and_spool_deduplication(self):
        sample=dict(schema_version=1,run_id='test',framework='trl',node='spark1',rank=0,local_rank=0,step=1,observed_at=1.0,metrics={'training_loss':1.0},timers={})
        self.assertEqual(validate_framework(sample),sample)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trl-rank-0.json';path.write_text(json.dumps(sample));seen={}
            self.assertEqual(framework_samples(Path(tmp),seen),[sample])
            self.assertEqual(framework_samples(Path(tmp),seen),[])
        for change in [
            {'framework':'unknown'}, {'rank':-1}, {'metrics':{'unknown':1}},
            {'metrics':{'training_loss':float('nan')}}, {'timers':{'bad timer':1}},
        ]:
            invalid=dict(sample);invalid.update(change)
            with self.assertRaises(ValueError):validate_framework(invalid)
