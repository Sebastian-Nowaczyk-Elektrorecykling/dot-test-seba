import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "example-app" / "server.py"
spec = importlib.util.spec_from_file_location("example_app",path)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class DemoTests(unittest.TestCase):
    def test_metadata_and_health_over_real_local_http(self):
        server = ThreadingHTTPServer(("127.0.0.1",0),app.Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ,{"APP_GIT_SHA":"a"*40,"DEPLOYMENT_ID":"test-123"}):
                base = f"http://127.0.0.1:{server.server_port}"
                with urllib.request.urlopen(base+"/healthz") as response:
                    self.assertTrue(json.load(response)["ready"])
                with urllib.request.urlopen(base+"/_meta") as response:
                    data = json.load(response)
                    self.assertEqual(data["build_sha"],"a"*40)
                    self.assertEqual(data["deployment_id"],"test-123")
        finally:
            server.shutdown(); server.server_close(); thread.join()
