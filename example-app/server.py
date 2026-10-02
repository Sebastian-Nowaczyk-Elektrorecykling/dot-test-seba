"""Demonstration only: no authentication, business functionality or persistent data."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            payload = {"ready": True}
        elif self.path == "/_meta":
            payload = {"build_sha": os.environ.get("APP_GIT_SHA", "local"),
                       "deployment_id": os.environ.get("DEPLOYMENT_ID", "local"),
                       "target_sha": os.environ.get("DEPLOY_TARGET_SHA", "local"),
                       "slot": os.environ.get("DEPLOY_SLOT", "local")}
        else:
            payload = {"message": "DEMO ONLY - port release adapter"}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()
