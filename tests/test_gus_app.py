"""Offline contract, validation, transport and real-local-HTTP tests for GUS BDL.

The checked-in official OpenAPI document is the independent contract fixture.
No test makes a live request to GUS or requires third-party Python packages.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import http.client
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit, urlencode
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gus_app import catalog, server

with (ROOT / 'docs' / 'bdl-openapi.json').open(encoding='utf-8') as source:
    OFFICIAL = json.load(source)

FULL_PAYLOAD = {
    'totalRecords': 2,
    'page': 0,
    'pageSize': 10,
    'links': [{'rel': 'next', 'href': 'https://bdl.stat.gov.pl/api/v1/units?page=1'}],
    'results': [
        {'id': '000000000000', 'name': 'Łódź', 'unknownFutureField': {'nested': [
            {'number': 0, 'available': False, 'value': None, 'empty': ''},
            [], {}, 12.25, 'Żółć <script>alert(1)</script>'
        ]}},
        {'id': '001234567890', 'values': [{'year': 2024, 'val': None, 'attrId': 0}]},
    ],
    'newMetadata': {'enabled': False, 'count': 0, 'description': None},
}


def official_fields(path):
    return [field for field in OFFICIAL['paths'][path]['get'].get('parameters', [])
            if field['in'] in ('path', 'query') and field['name'] not in ('format', 'lang')]


def valid_value(field):
    schema = field['schema']
    item = schema.get('items', schema)
    if 'enum' in item:
        return str(item['enum'][0])
    if item.get('type') == 'integer':
        return '1'
    return '000123456789' if field['in'] == 'path' else 'Ludność'


def valid_params(path, include_optional=False):
    params = {'endpoint': [path]}
    for field in official_fields(path):
        if include_optional or field.get('required', False):
            params[field['name']] = [valid_value(field)]
    return params


class CatalogContractTests(unittest.TestCase):
    def test_exactly_all_36_official_get_operations_are_available(self):
        official_paths = {path for path, methods in OFFICIAL['paths'].items() if 'get' in methods}
        self.assertEqual(len(official_paths), 36)
        self.assertEqual(len(catalog.CATALOG['endpoints']), 36)
        self.assertEqual(set(catalog.ENDPOINTS), official_paths)
        self.assertEqual({item['id'] for item in catalog.CATALOG['endpoints']}, official_paths)

    def test_every_parameter_matches_official_schema_and_required_flag(self):
        for path in OFFICIAL['paths']:
            with self.subTest(path=path):
                endpoint = catalog.ENDPOINTS[path]
                self.assertEqual(endpoint['path'], path)
                self.assertTrue(endpoint['title'])
                self.assertIsInstance(endpoint['description'], str)
                actual = {field['name']: field for field in endpoint['parameters']}
                expected = {field['name']: field for field in official_fields(path)}
                self.assertEqual(set(actual), set(expected))
                for name, official in expected.items():
                    field = actual[name]
                    self.assertEqual(field['in'], official['in'])
                    self.assertEqual(field['required'], official.get('required', False))
                    self.assertIsInstance(field['description'], str)
                    for key, value in official['schema'].items():
                        if key == 'type' and value == 'enum':
                            value = 'string'
                        self.assertEqual(field[key], value, (path, name, key))
                    if name == 'page':
                        self.assertEqual(field['minimum'], 0)
                    if name == 'page-size':
                        self.assertEqual((field['minimum'], field['maximum']), (1, 100))

    def test_every_operation_builds_minimal_and_all_parameter_urls(self):
        for path in OFFICIAL['paths']:
            for include_optional in (False, True):
                with self.subTest(path=path, all_parameters=include_optional):
                    params = valid_params(path, include_optional)
                    original = copy.deepcopy(params)
                    result = urlsplit(catalog.query_url(params))
                    self.assertEqual(params, original, 'Validation must not mutate the caller input')
                    self.assertEqual((result.scheme, result.netloc), ('https', 'bdl.stat.gov.pl'))
                    self.assertFalse(result.fragment)
                    expected_path = '/api/v1' + path
                    expected_query = {'format': ['json'], 'lang': ['pl']}
                    for field in official_fields(path):
                        name = field['name']
                        if name not in params:
                            continue
                        if field['in'] == 'path':
                            expected_path = expected_path.replace('{' + name + '}', params[name][0])
                        else:
                            expected_query[name] = params[name]
                    self.assertEqual(result.path, expected_path)
                    self.assertEqual(parse_qs(result.query), expected_query)
                    self.assertNotIn('{', result.path)

    def test_each_official_required_parameter_is_enforced(self):
        for path in OFFICIAL['paths']:
            for field in official_fields(path):
                if not field.get('required', False):
                    continue
                for absent in (None, [], [''], ['  ']):
                    with self.subTest(path=path, field=field['name'], absent=absent):
                        params = valid_params(path)
                        if absent is None:
                            params.pop(field['name'])
                        else:
                            params[field['name']] = absent
                        with self.assertRaisesRegex(ValueError, field['name']):
                            catalog.query_url(params)

    def test_all_official_enum_values_are_accepted_and_unknown_values_rejected(self):
        for path in OFFICIAL['paths']:
            for field in official_fields(path):
                schema = field['schema'].get('items', field['schema'])
                if 'enum' not in schema:
                    continue
                for value in schema['enum']:
                    with self.subTest(path=path, field=field['name'], value=value):
                        params = valid_params(path)
                        params[field['name']] = [str(value)]
                        query = parse_qs(urlsplit(catalog.query_url(params)).query)
                        self.assertEqual(query[field['name']], [str(value)])
                params[field['name']] = ['not-an-official-choice']
                with self.assertRaises(ValueError):
                    catalog.query_url(params)

    def test_plain_removes_html_and_decodes_entities(self):
        self.assertEqual(catalog.plain('<p>Łódź &amp; Polska</p>'), 'Łódź & Polska')
        self.assertEqual(catalog.plain(None), '')


class QueryValidationTests(unittest.TestCase):
    def test_every_array_accepts_repetition_and_comma_separation(self):
        for path in OFFICIAL['paths']:
            for field in official_fields(path):
                if field['schema']['type'] != 'array':
                    continue
                with self.subTest(path=path, field=field['name']):
                    params = valid_params(path)
                    params[field['name']] = [' 1,2 ', '3', '4, 5', '', '  ']
                    query = parse_qs(urlsplit(catalog.query_url(params)).query)
                    self.assertEqual(query[field['name']], ['1', '2', '3', '4', '5'])

    def test_array_limit_is_applied_after_splitting(self):
        for values in (['1'] * 100, [','.join(['1'] * 100)]):
            params = {'endpoint': ['/units'], 'level': values}
            self.assertEqual(len(parse_qs(urlsplit(catalog.query_url(params)).query)['level']), 100)
        for values in (['1'] * 101, [','.join(['1'] * 101)]):
            with self.assertRaises(ValueError):
                catalog.query_url({'endpoint': ['/units'], 'level': values})

    def test_required_array_cannot_contain_only_delimiters(self):
        params = {'endpoint': ['/data/by-unit/{unit-id}'], 'unit-id': ['000000000000'],
                  'var-id': [', ,', '  ,  ']}
        with self.assertRaises(ValueError):
            catalog.query_url(params)

    def test_scalar_and_path_parameter_repetition_is_rejected(self):
        for path in OFFICIAL['paths']:
            for field in official_fields(path):
                if field['schema']['type'] == 'array':
                    continue
                with self.subTest(path=path, field=field['name']):
                    params = valid_params(path)
                    params[field['name']] = [valid_value(field)] * 2
                    with self.assertRaises(ValueError):
                        catalog.query_url(params)

    def test_unknown_absent_duplicate_or_external_endpoints_are_rejected(self):
        endpoint_values = [[], ['/missing'], ['/units', '/units'],
                           ['https://evil.example/'], ['http://127.0.0.1/'],
                           ['file:///etc/passwd'], ['//evil.example/units'],
                           ['/units/../version'], ['/units%2f..%2fversion']]
        for values in endpoint_values:
            with self.subTest(values=values), self.assertRaises(ValueError):
                catalog.query_url({'endpoint': values})
        with self.assertRaises(ValueError):
            catalog.query_url({})

    def test_unknown_keys_cannot_override_destination_format_or_language(self):
        for name in ('url', 'host', 'scheme', 'path', 'format', 'lang', 'Accept', 'token', 'api-key'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                catalog.query_url({'endpoint': ['/units'], name: ['https://evil.example/']})

    def test_every_path_field_rejects_path_query_fragment_and_host_injection(self):
        attacks = ['..', '../version', '/version', '//evil.example', r'..\version',
                   '%2e%2e', '%2f', 'foo?format=xml', 'foo#fragment', 'a&b=c',
                   'a b', 'user@host', 'x:y', 'x\x00y', 'x\ny', 'x\ry']
        for path in OFFICIAL['paths']:
            for field in official_fields(path):
                if field['in'] != 'path':
                    continue
                for value in attacks:
                    with self.subTest(path=path, field=field['name'], value=value):
                        params = valid_params(path)
                        params[field['name']] = [value]
                        with self.assertRaises(ValueError):
                            catalog.query_url(params)

    def test_query_text_is_encoded_without_changing_request_destination(self):
        text = 'Łódź &lang=en?x=1#frag / .. https://evil.example <script> + %'
        parsed = urlsplit(catalog.query_url({'endpoint': ['/units/search'], 'name': [text]}))
        self.assertEqual(parsed.netloc, 'bdl.stat.gov.pl')
        self.assertEqual(parsed.path, '/api/v1/units/search')
        self.assertEqual(parsed.fragment, '')
        self.assertEqual(parse_qs(parsed.query), {'format': ['json'], 'lang': ['pl'], 'name': [text]})

    def test_leading_zeros_are_preserved_in_path_and_query(self):
        parsed = urlsplit(catalog.query_url({'endpoint': ['/data/by-unit/{unit-id}'],
                                            'unit-id': ['000000000000'],
                                            'var-id': ['00042'], 'year': ['02024']}))
        self.assertTrue(parsed.path.endswith('/000000000000'))
        self.assertEqual(parse_qs(parsed.query)['var-id'], ['00042'])
        self.assertEqual(parse_qs(parsed.query)['year'], ['02024'])
        query = parse_qs(urlsplit(catalog.query_url({'endpoint': ['/units'],
                                                   'parent-id': ['000000000000']})).query)
        self.assertEqual(query['parent-id'], ['000000000000'])

    def test_every_integer_field_rejects_malformed_or_out_of_range_numbers(self):
        invalid = ['-1', '+1', '1.0', '1e3', 'NaN', 'Infinity', '١', '１', '1 2', '0x10', '2147483648']
        for path in OFFICIAL['paths']:
            for field in official_fields(path):
                schema = field['schema'].get('items', field['schema'])
                if schema.get('type') != 'integer':
                    continue
                for value in invalid:
                    with self.subTest(path=path, field=field['name'], value=value):
                        params = valid_params(path)
                        params[field['name']] = [value]
                        with self.assertRaises(ValueError):
                            catalog.query_url(params)

    def test_integer_boundaries_accept_zero_and_max_int32(self):
        for number in ('0', '2147483647'):
            query = parse_qs(urlsplit(catalog.query_url({'endpoint': ['/variables'],
                                                       'level': [number], 'year': [number]})).query)
            self.assertEqual(query['level'], [number])
            self.assertEqual(query['year'], [number])

    def test_every_pagination_field_enforces_zero_based_pages_and_bounded_page_size(self):
        for path in OFFICIAL['paths']:
            names = {field['name'] for field in official_fields(path)}
            if 'page' not in names:
                continue
            for page, size in [('0', '1'), ('1', '100'), ('2147483647', '10')]:
                with self.subTest(path=path, page=page, size=size):
                    params = valid_params(path)
                    params.update(page=[page], **{'page-size': [size]})
                    query = parse_qs(urlsplit(catalog.query_url(params)).query)
                    self.assertEqual((query['page'], query['page-size']), ([page], [size]))
            for name, value in [('page', '-1'), ('page', '2147483648'), ('page-size', '0'),
                                ('page-size', '101'), ('page-size', '-1')]:
                with self.subTest(path=path, name=name, value=value):
                    params = valid_params(path)
                    params[name] = [value]
                    with self.assertRaises(ValueError):
                        catalog.query_url(params)

    def test_string_size_limits_and_embedded_controls(self):
        params = {'endpoint': ['/subjects/search'], 'name': ['x' * 500]}
        self.assertEqual(parse_qs(urlsplit(catalog.query_url(params)).query)['name'], ['x' * 500])
        for value in ['x' * 501, 'x\x00y', 'x\ty', 'x\ny', 'x\ry', 'x\x1fy']:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                catalog.query_url({'endpoint': ['/subjects/search'], 'name': [value]})

    def test_optional_blanks_are_omitted_and_meaningful_values_trimmed(self):
        result = catalog.query_url({'endpoint': ['/units/search'], 'name': [' Łódź '],
                                    'year': [' '], 'page': [''], 'kind': ['\t ']})
        self.assertEqual(parse_qs(urlsplit(result).query),
                         {'format': ['json'], 'lang': ['pl'], 'name': ['Łódź']})


class GusTransportTests(unittest.TestCase):
    def setUp(self):
        self.client = server.GusClient()
        self.client.opener = Mock()
        self.clock = self.enterContext(patch.object(server.time, 'monotonic', return_value=100.0))
        self.sleep = self.enterContext(patch.object(server.time, 'sleep'))
        self.url = catalog.BASE_URL + '/units?format=json&lang=pl'

    def respond_with(self, raw):
        self.client.opener.open.side_effect = lambda *args, **kwargs: io.BytesIO(raw)

    def test_full_response_preserves_unknown_nested_fields_null_false_zero_and_unicode(self):
        self.respond_with(json.dumps(FULL_PAYLOAD, ensure_ascii=False).encode())
        result = self.client.fetch(self.url)
        self.assertEqual(result, FULL_PAYLOAD)
        self.assertIsNone(result['newMetadata']['description'])
        self.assertIs(result['newMetadata']['enabled'], False)
        self.assertEqual(result['newMetadata']['count'], 0)
        request = self.client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, self.url)
        self.assertEqual(request.get_header('Accept'), 'application/json')
        self.assertEqual(request.get_header('User-agent'), 'GUS-BDL-Explorer/1.0')
        self.assertEqual(self.client.opener.open.call_args.kwargs, {'timeout': server.TIMEOUT})

    def test_valid_json_root_shapes_are_preserved(self):
        for payload in ([], {}, None, False, 0, '1.2.3'):
            with self.subTest(payload=payload):
                self.client.cache.clear()
                self.respond_with(json.dumps(payload).encode())
                self.assertEqual(self.client.fetch(self.url), payload)

    def test_cached_response_avoids_network_and_pacing(self):
        self.respond_with(b'{"results":[]}')
        first = self.client.fetch(self.url)
        self.clock.return_value = 159.999
        self.assertEqual(self.client.fetch(self.url), first)
        self.client.opener.open.assert_called_once()
        self.sleep.assert_not_called()

    def test_cache_expires_at_60_seconds_and_fetches_fresh_data(self):
        self.respond_with(b'{"version":1}')
        self.assertEqual(self.client.fetch(self.url), {'version': 1})
        self.clock.return_value = 160.0
        self.respond_with(b'{"version":2}')
        self.assertEqual(self.client.fetch(self.url), {'version': 2})
        self.assertEqual(self.client.opener.open.call_count, 2)

    def test_cache_is_bounded_and_keys_include_query(self):
        self.respond_with(b'{}')
        for index in range(17):
            self.client.fetch(self.url + '&page=' + str(index))
        self.assertEqual(len(self.client.cache), 16)
        self.assertNotIn(self.url + '&page=0', self.client.cache)
        self.assertIn(self.url + '&page=16', self.client.cache)
        self.assertEqual(self.client.opener.open.call_count, 17)

    def test_requests_are_paced_when_cache_cannot_answer(self):
        self.respond_with(b'{}')
        self.client.last_request = 99.9
        self.client.fetch(self.url)
        self.sleep.assert_called_once()
        self.assertAlmostEqual(self.sleep.call_args.args[0], 0.15)

    def test_http_error_statuses_are_mapped_without_leaking_upstream_content(self):
        for code, expected in [(400, 400), (404, 400), (412, 400), (422, 400), (429, 429),
                               (301, 502), (302, 502), (401, 502), (403, 502),
                               (500, 502), (503, 502)]:
            with self.subTest(code=code):
                error = HTTPError(self.url, code, 'SECRET upstream body', {}, io.BytesIO(b'SECRET'))
                self.client.opener.open.side_effect = error
                with self.assertRaises(server.GusError) as caught:
                    self.client.fetch(self.url)
                self.assertEqual(caught.exception.status, expected)
                self.assertNotIn('SECRET', str(caught.exception))
                self.assertEqual(self.client.cache, {})
                error.close()

    def test_network_errors_and_timeouts_are_controlled_and_not_cached(self):
        for error in (URLError('SECRET'), TimeoutError('SECRET'), socket.timeout('SECRET'),
                      OSError('SECRET'), ConnectionResetError('SECRET'),
                      http.client.IncompleteRead(b'SECRET'), http.client.BadStatusLine('SECRET')):
            with self.subTest(error=type(error).__name__):
                self.client.opener.open.side_effect = error
                with self.assertRaises(server.GusError) as caught:
                    self.client.fetch(self.url)
                self.assertEqual(caught.exception.status, 502)
                self.assertNotIn('SECRET', str(caught.exception))
                self.assertEqual(self.client.cache, {})

    def test_concurrent_identical_requests_share_one_upstream_fetch(self):
        self.respond_with(json.dumps(FULL_PAYLOAD).encode())
        gate = threading.Barrier(8)
        def fetch_after_gate(_):
            gate.wait(timeout=5)
            return self.client.fetch(self.url)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch_after_gate, range(8)))
        self.assertEqual(results, [FULL_PAYLOAD] * 8)
        self.client.opener.open.assert_called_once()
        self.assertEqual(len(self.client.cache), 1)

    def test_read_failure_closes_response_and_is_not_cached(self):
        for error in (TimeoutError('SECRET'), http.client.IncompleteRead(b'SECRET')):
            with self.subTest(error=type(error).__name__):
                response = Mock()
                response.__enter__ = Mock(return_value=response)
                response.__exit__ = Mock(return_value=False)
                response.read.side_effect = error
                self.client.opener.open.return_value = response
                with self.assertRaises(server.GusError) as caught:
                    self.client.fetch(self.url)
                self.assertEqual(caught.exception.status, 502)
                self.assertNotIn('SECRET', str(caught.exception))
                self.assertEqual(self.client.cache, {})
                response.__exit__.assert_called_once()

    def test_failed_request_can_be_retried_successfully(self):
        self.client.opener.open.side_effect = URLError('temporarily unavailable')
        with self.assertRaises(server.GusError):
            self.client.fetch(self.url)
        self.respond_with(b'{"recovered":true}')
        self.assertEqual(self.client.fetch(self.url), {'recovered': True})
        self.assertEqual(self.client.opener.open.call_count, 2)

    def test_invalid_json_encoding_and_excessive_nesting_are_controlled(self):
        for raw in (b'', b'<html>bad gateway</html>', b'{"a":', b'\xff',
                    b'[' * 20000 + b'0' + b']' * 20000):
            with self.subTest(raw=raw[:30]):
                self.respond_with(raw)
                with self.assertRaises(server.GusError) as caught:
                    self.client.fetch(self.url)
                self.assertEqual(caught.exception.status, 502)
                self.assertEqual(self.client.cache, {})

    def test_non_finite_json_numbers_are_rejected_before_caching(self):
        for raw in (b'NaN', b'Infinity', b'-Infinity', b'{"nested":[NaN]}', b'{"value":1e9999}'):
            with self.subTest(raw=raw):
                self.respond_with(raw)
                with self.assertRaises(server.GusError) as caught:
                    self.client.fetch(self.url)
                self.assertEqual(caught.exception.status, 502)
                self.assertEqual(self.client.cache, {})

    def test_response_limit_is_enforced_at_boundary(self):
        raw = b'{"ok":true}'
        with patch.object(server, 'MAX_RESPONSE', len(raw)):
            self.respond_with(raw)
            self.assertEqual(self.client.fetch(self.url), {'ok': True})
            self.client.cache.clear()
            self.respond_with(raw + b' ')
            with self.assertRaises(server.GusError) as caught:
                self.client.fetch(self.url)
            self.assertEqual(caught.exception.status, 502)
            self.assertEqual(self.client.cache, {})

    def test_reader_is_bounded_to_one_byte_over_limit(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{}'
        self.client.opener.open.side_effect = None
        self.client.opener.open.return_value = response
        self.client.fetch(self.url)
        response.read.assert_called_once_with(server.MAX_RESPONSE + 1)
        response.__exit__.assert_called_once()

    def test_redirect_handler_refuses_all_destinations(self):
        handler = server.NoRedirect()
        for url in ('https://bdl.stat.gov.pl/api/v1/version', 'https://evil.example/',
                    'http://127.0.0.1/', 'file:///etc/passwd'):
            with self.subTest(url=url):
                self.assertIsNone(handler.redirect_request(Request(self.url), None, 302,
                                                          'Found', {}, url))
        redirects = [handler for handler in server.GusClient().opener.handlers
                     if isinstance(handler, server.HTTPRedirectHandler)]
        self.assertEqual(len(redirects), 1)
        self.assertIsInstance(redirects[0], server.NoRedirect)


class GusHTTPIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The production handler runs over real HTTP; only upstream transport and
        # static bytes are fixtures, avoiding GUS network and frontend coupling.
        cls.fixture_dir = tempfile.TemporaryDirectory()
        cls.static_bytes = {'index.html': b'<!doctype html><html lang="pl">GUS</html>',
                            'app.js': b'"use strict";\n', 'style.css': b'body { color: black; }\n'}
        for name, contents in cls.static_bytes.items():
            (Path(cls.fixture_dir.name) / name).write_bytes(contents)
        cls.static_patch = patch.object(server, 'STATIC', Path(cls.fixture_dir.name))
        cls.static_patch.start()
        cls.client = Mock(spec=server.GusClient)
        class TestHandler(server.Handler):
            client = cls.client
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), TestHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls.static_patch.stop()
        cls.fixture_dir.cleanup()

    def setUp(self):
        self.client.reset_mock(return_value=True, side_effect=True)
        self.client.fetch.return_value = copy.deepcopy(FULL_PAYLOAD)

    def request(self, path, method='GET'):
        connection = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            body = response.read()
            return response.status, dict(response.getheaders()), body
        finally:
            connection.close()

    def query_path(self, params):
        return '/api/query?' + urlencode(params, doseq=True)

    def assert_json_error(self, path, status=400):
        actual_status, headers, body = self.request(path)
        self.assertEqual(actual_status, status)
        self.assertIn('application/json', headers['Content-Type'])
        self.assertIsInstance(json.loads(body)['error'], str)
        self.client.fetch.assert_not_called()
        return json.loads(body)

    def test_catalog_and_all_36_operations_over_real_http(self):
        status, headers, body = self.request('/api/catalog')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), catalog.CATALOG)
        self.assertEqual(len(json.loads(body)['endpoints']), 36)
        self.client.fetch.assert_not_called()
        for path in OFFICIAL['paths']:
            with self.subTest(path=path):
                self.client.fetch.reset_mock()
                params = valid_params(path, include_optional=True)
                status, headers, body = self.request(self.query_path(params))
                self.assertEqual(status, 200)
                result = json.loads(body)
                self.assertEqual(result['data'], FULL_PAYLOAD)
                self.assertEqual(result['source'], catalog.query_url(params))
                self.client.fetch.assert_called_once_with(result['source'])

    def test_unpaired_unicode_does_not_break_json_response(self):
        payload = {"name": "\ud800", "valid": "Łódź"}
        self.client.fetch.return_value = payload
        status, _, body = self.request('/api/query?endpoint=/version')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['data'], payload)

    def test_static_files_are_exact_and_have_correct_mime_types(self):
        for path, name, mime in [('/', 'index.html', 'text/html'),
                                 ('/app.js', 'app.js', 'text/javascript'),
                                 ('/style.css', 'style.css', 'text/css'),
                                 ('/static/app.js', 'app.js', 'text/javascript'),
                                 ('/static/style.css', 'style.css', 'text/css')]:
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertEqual(body, self.static_bytes[name])
                self.assertTrue(headers['Content-Type'].startswith(mime))
                self.assertEqual(int(headers['Content-Length']), len(body))
        self.client.fetch.assert_not_called()

    def test_security_headers_on_success_and_error_responses(self):
        for path in ('/', '/app.js', '/style.css', '/api/catalog', '/healthz', '/_meta',
                     '/api/query', '/missing'):
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
                csp = headers['Content-Security-Policy']
                for directive in ("default-src 'self'", "connect-src 'self'", "base-uri 'none'",
                                  "frame-ancestors 'none'", "script-src 'self'", "form-action 'self'"):
                    self.assertIn(directive, csp)
                self.assertNotIn('unsafe-inline', csp)
                self.assertNotIn('Access-Control-Allow-Origin', headers)
                self.assertEqual(int(headers['Content-Length']), len(body))

    def test_health_is_ready_without_upstream_request(self):
        status, headers, body = self.request('/healthz')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'ready': True})
        self.client.fetch.assert_not_called()

    def test_metadata_reports_exact_deployment_environment_values(self):
        values = {'APP_GIT_SHA': 'a' * 40, 'DEPLOYMENT_ID': 'deployment-123',
                  'DEPLOY_TARGET_SHA': 'b' * 40, 'DEPLOY_SLOT': 'deploy/p4101'}
        with patch.dict(os.environ, values):
            status, headers, body = self.request('/_meta')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'build_sha': 'a' * 40, 'deployment_id': 'deployment-123',
                                           'target_sha': 'b' * 40, 'slot': 'deploy/p4101'})
        self.client.fetch.assert_not_called()

    def test_metadata_local_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            status, headers, body = self.request('/_meta')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'build_sha': 'local', 'deployment_id': 'local',
                                           'target_sha': 'local', 'slot': 'local'})

    def test_required_fields_fail_locally_and_never_contact_gus(self):
        for path in OFFICIAL['paths']:
            if not any(field.get('required') for field in official_fields(path)):
                continue
            with self.subTest(path=path):
                self.assert_json_error(self.query_path({'endpoint': path}))

    def test_unknown_endpoints_keys_and_injection_fail_locally(self):
        requests = [
            {}, {'endpoint': 'https://evil.example/'}, {'endpoint': ['/', '/units']},
            {'endpoint': '/units', 'url': 'http://127.0.0.1/'},
            {'endpoint': '/units', 'lang': 'en'},
            {'endpoint': '/units/{id}', 'id': '../version'},
            {'endpoint': '/units/{id}', 'id': '%2f%2fevil.example'},
            {'endpoint': '/units', 'page': '-1'},
            {'endpoint': '/units', 'page-size': '101'},
            {'endpoint': '/units/search', 'name': 'x\ny'},
            {'endpoint': '/units', 'page': ['1', '2']},
        ]
        for params in requests:
            with self.subTest(params=params):
                self.assert_json_error(self.query_path(params))

    def test_repeated_arrays_and_leading_zero_ids_survive_http(self):
        params = {'endpoint': '/data/by-unit/{unit-id}', 'unit-id': '000000000000',
                  'var-id': ['42,43', '44'], 'year': ['2023', '2024'], 'page': '0', 'page-size': '100'}
        status, headers, body = self.request(self.query_path(params))
        self.assertEqual(status, 200)
        source = urlsplit(json.loads(body)['source'])
        self.assertTrue(source.path.endswith('/000000000000'))
        query = parse_qs(source.query)
        self.assertEqual(query['var-id'], ['42', '43', '44'])
        self.assertEqual(query['year'], ['2023', '2024'])
        self.assertEqual(query['page'], ['0'])
        self.assertEqual(query['page-size'], ['100'])

    def test_upstream_errors_are_returned_with_their_controlled_status(self):
        for error_status in (400, 429, 502):
            with self.subTest(status=error_status):
                self.client.fetch.side_effect = server.GusError('Kontrolowany błąd GUS', error_status)
                status, headers, body = self.request('/api/query?endpoint=%2Funits')
                self.assertEqual(status, error_status)
                self.assertEqual(json.loads(body), {'error': 'Kontrolowany błąd GUS'})

    def test_long_request_target_is_rejected_without_upstream_request(self):
        self.assert_json_error('/api/query?' + 'x' * 12000, status=414)
        # The same bound covers static and diagnostics routes, not only proxy requests.
        self.assert_json_error('/healthz?' + 'x' * 12000, status=414)

    def test_exact_request_target_limit_is_not_rejected_as_too_long(self):
        path = '/healthz?' + 'x' * (12000 - len('/healthz?'))
        self.assertEqual(len(path), 12000)
        self.assertEqual(self.request(path)[0], 200)
        self.client.fetch.assert_not_called()

    def test_excessive_query_field_count_is_rejected_without_upstream_request(self):
        self.assert_json_error('/api/query?' + '&'.join(['endpoint=%2Funits'] + ['level=1'] * 250))

    def test_unknown_paths_and_traversal_cannot_read_local_files(self):
        for path in ('/missing', '/catalog.py', '/server.py', '/docs/bdl-openapi.json',
                     '/../AGENTS.md', '/%2e%2e/AGENTS.md', '/static/../server.py',
                     '/.git/config', '/app.js/../../AGENTS.md'):
            with self.subTest(path=path):
                self.assert_json_error(path, status=404)

    def test_non_get_methods_cannot_proxy_a_request(self):
        for method in ('POST', 'PUT', 'DELETE', 'PATCH', 'HEAD'):
            with self.subTest(method=method):
                status, headers, body = self.request('/api/query?endpoint=%2Funits', method=method)
                self.assertEqual(status, 501)
                self.client.fetch.assert_not_called()

    def test_query_access_log_does_not_emit_sensitive_search_text(self):
        with patch('sys.stderr', new_callable=io.StringIO) as stderr:
            status, headers, body = self.request('/api/query?endpoint=%2Funits%2Fsearch&name=private-search')
        self.assertEqual(status, 200)
        self.assertEqual(stderr.getvalue(), '')

    def test_disconnected_response_writer_is_ignored(self):
        handler = object.__new__(server.Handler)
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = Mock()
        for error in (BrokenPipeError(), ConnectionResetError()):
            with self.subTest(error=type(error).__name__):
                handler.wfile.write.side_effect = error
                handler.send_payload(200, {'data': FULL_PAYLOAD})


if __name__ == '__main__':
    unittest.main()
