import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from telemetry.server import make_server
from telemetry.agent import metrics
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
                output=Path(tmp)/'snapshot.json'
                export(database,'test',output)
                self.assertFalse(json.loads(output.read_text())['synthetic'])
                with self.assertRaises(ValueError): export(database,'missing',output)
            finally:
                server.shutdown();server.server_close();thread.join()
            restarted=make_server(('127.0.0.1',0),database,'x'*32);restarted.server_close()
            export(database,'test',output)
            self.assertEqual(len(json.loads(output.read_text())['samples']),1)
