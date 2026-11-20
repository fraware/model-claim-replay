"""Exercise the real HTTP adapter against a deterministic local server."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from model_claim_replay.cli import api_completion
from model_claim_replay.core import ReplayError


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        size=int(self.headers['Content-Length'])
        data=json.loads(self.rfile.read(size))
        assert self.path == '/v1/chat/completions'
        assert data['messages'][-1]['content'] == 'Reply alpha'
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'choices':[{'message':{'content':'alpha'}}], 'usage':{'total_tokens':12}}).encode())

    def log_message(self, *args):
        pass


class EndpointTests(unittest.TestCase):
    def test_local_endpoint(self):
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            output,usage=api_completion(base_url=f'http://127.0.0.1:{server.server_port}/v1',api_key=None,
                model='local-test',messages=[{'role':'user','content':'Reply alpha'}],temperature=0,max_tokens=12,timeout=2)
            self.assertEqual(output,'alpha')
            self.assertEqual(usage['total_tokens'],12)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_remote_cleartext_refused(self):
        with self.assertRaisesRegex(ReplayError,'HTTPS'):
            api_completion(base_url='http://example.com/v1',api_key='secret',model='x',
                messages=[],temperature=0,max_tokens=12,timeout=1)

    def test_url_userinfo_refused(self):
        with self.assertRaises(ReplayError):
            api_completion(base_url='https://user:pass@example.com/v1',api_key='secret',model='x',
                messages=[],temperature=0,max_tokens=12,timeout=1)


if __name__ == '__main__':
    unittest.main()
