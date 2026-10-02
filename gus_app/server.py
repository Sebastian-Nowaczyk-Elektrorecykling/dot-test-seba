"""Local HTTP app, with a bounded, fixed-destination BDL proxy (no credentials)."""
import json
import math
import os
from pathlib import Path
import socket
import threading
import time
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from gus_app.catalog import CATALOG, query_url

STATIC = Path(__file__).parent / 'static'
MAX_RESPONSE = 5 * 1024 * 1024
TIMEOUT = 20


class GusError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite JSON number")
    return result


def reject_constant(value):
    raise ValueError("Non-finite JSON number: " + value)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GusClient:
    """Small bounded cache and global pacing; GUS still enforces its own quotas."""
    def __init__(self):
        self.opener = build_opener(NoRedirect())
        self.lock = threading.Lock()
        self.cache = {}
        self.last_request = 0.0

    def fetch(self, url):
        with self.lock:
            now = time.monotonic()
            cached = self.cache.get(url)
            if cached and now - cached[0] < 60:
                return cached[1]
            delay = 0.25 - (now - self.last_request)
            if delay > 0:
                time.sleep(delay)
            self.last_request = time.monotonic()
            try:
                request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'GUS-BDL-Explorer/1.0'})
                with self.opener.open(request, timeout=TIMEOUT) as response:
                    raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise GusError('Odpowiedź GUS jest zbyt duża. Zawęź filtry lub zmniejsz liczbę rekordów.')
                data = json.loads(raw, parse_constant=reject_constant, parse_float=finite_float)
            except HTTPError as error:
                if error.code == 429:
                    raise GusError('Przekroczono limit zapytań GUS. Odczekaj i spróbuj ponownie.', 429) from error
                if error.code in (400, 404, 412, 422):
                    raise GusError('GUS nie znalazł zasobu lub odrzucił parametry. Sprawdź identyfikatory i filtry.', 400) from error
                raise GusError('Usługa GUS jest chwilowo niedostępna. Spróbuj ponownie później.') from error
            except (URLError, TimeoutError, socket.timeout, OSError, HTTPException) as error:
                raise GusError('Nie udało się połączyć z GUS w wymaganym czasie. Spróbuj ponownie.') from error
            except (ValueError, UnicodeError, RecursionError) as error:
                raise GusError('GUS zwrócił nieprawidłową odpowiedź. Spróbuj ponownie później.') from error
            if len(self.cache) >= 16:
                self.cache.pop(next(iter(self.cache)))
            self.cache[url] = (time.monotonic(), data)
            return data


class Handler(BaseHTTPRequestHandler):
    client = GusClient()

    def send_payload(self, status, payload, content_type='application/json; charset=utf-8'):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=True, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Browser canceled an obsolete query.

    def do_GET(self):
        if len(self.path) > 12000:
            return self.send_payload(414, {'error': 'Zapytanie jest zbyt długie.'})
        parsed = urlsplit(self.path)
        if parsed.path == '/api/catalog':
            return self.send_payload(200, CATALOG)
        if parsed.path == '/api/query':
            try:
                params = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=250)
                url = query_url(params)
                data = self.client.fetch(url)
                return self.send_payload(200, {'data': data, 'source': url})
            except ValueError as error:
                return self.send_payload(400, {'error': str(error)})
            except GusError as error:
                return self.send_payload(error.status, {'error': str(error)})
        if parsed.path == '/healthz':
            return self.send_payload(200, {'ready': True})
        if parsed.path == '/_meta':
            return self.send_payload(200, {key: os.environ.get(env, 'local') for key, env in (
                ('build_sha', 'APP_GIT_SHA'), ('deployment_id', 'DEPLOYMENT_ID'),
                ('target_sha', 'DEPLOY_TARGET_SHA'), ('slot', 'DEPLOY_SLOT'))})
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        files.update({'/static/app.js': files['/app.js'], '/static/style.css': files['/style.css']})
        if parsed.path not in files:
            return self.send_payload(404, {'error': 'Nie znaleziono strony.'})
        name, content_type = files[parsed.path]
        return self.send_payload(200, (STATIC / name).read_bytes(), content_type)

    def log_message(self, format, *args):
        pass  # Do not retain search terms or query parameters in access logs.


def main():
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '8080'))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f'GUS BDL: http://{host}:{port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
