"""Allowlisted API operations derived from the checked-in official OpenAPI snapshot."""
import html
import json
from pathlib import Path
import re
from urllib.parse import quote, urlencode

BASE_URL = "https://bdl.stat.gov.pl/api/v1"
SPEC = json.loads((Path(__file__).resolve().parents[1] / "docs/bdl-openapi.json").read_text())
GROUPS = {"aggregates": "Agregaty", "attributes": "Atrybuty danych", "data": "Dane statystyczne",
          "levels": "Poziomy terytorialne", "measures": "Jednostki miary", "subjects": "Tematy",
          "units": "Jednostki terytorialne", "variables": "Zmienne", "version": "Wersja API", "years": "Lata"}


def plain(value):
    return html.unescape(re.sub(r"<[^>]*>", " ", value or "")).strip()


def title(path):
    group = GROUPS[path.split('/')[1]]
    if path.endswith('/metadata'):
        return f"{group}: opis pól"
    if '/by-variable/' in path:
        return 'Dane według zmiennej' + (' — miejscowości' if '/localities/' in path else '')
    if '/by-unit/' in path:
        return 'Dane według jednostki' + (' — miejscowości' if '/localities/' in path else '')
    if '/localities' in path:
        group = 'Miejscowości statystyczne'
    return group + (': wyszukiwanie' if path.endswith('/search') else ': szczegóły' if '{' in path else ': lista')


def make_catalog():
    endpoints = []
    for path, methods in SPEC['paths'].items():
        operation = methods['get']
        parameters = []
        for parameter in operation.get('parameters', []):
            if parameter['in'] not in ('path', 'query') or parameter['name'] in ('lang', 'format'):
                continue
            field = {**parameter['schema'], 'name': parameter['name'], 'in': parameter['in'],
                     'required': parameter.get('required', False), 'description': plain(parameter.get('description'))}
            if field['type'] == 'enum':
                field['type'] = 'string'
            if field['name'] == 'page':
                field['minimum'] = 0
            if field['name'] == 'page-size':
                field.update(minimum=1, maximum=100)
                field['description'] += ' W aplikacji maksymalnie 100 rekordów na stronę; kolejne strony są dostępne osobno.'
            parameters.append(field)
        endpoints.append({'id': path, 'path': path, 'title': title(path),
                          'description': plain(operation.get('summary')), 'parameters': parameters})
    return {'endpoints': endpoints}


CATALOG = make_catalog()
ENDPOINTS = {item['id']: item for item in CATALOG['endpoints']}


def validate_value(field, value):
    name = field['name']
    if not value or len(value) > 500 or any(ord(c) < 32 for c in value):
        raise ValueError(f'Nieprawidłowa wartość pola {name}.')
    schema = field.get('items', {}) if field['type'] == 'array' else field
    if 'enum' in schema and value not in [str(v) for v in schema['enum']]:
        raise ValueError(f'Wybierz jedną z dostępnych wartości pola {name}.')
    if schema.get('type') == 'integer':
        if not re.fullmatch(r'[0-9]+', value) or int(value) > 2147483647:
            raise ValueError(f'Pole {name} wymaga nieujemnej liczby całkowitej.')
        number = int(value)
        if number < field.get('minimum', 0) or number > field.get('maximum', 2147483647):
            raise ValueError(f'Pole {name} jest poza dozwolonym zakresem.')
    if field['in'] == 'path' and not re.fullmatch(r'[A-Za-z0-9-]+', value):
        raise ValueError(f'Nieprawidłowy identyfikator {name}.')
    return value


def query_url(params):
    endpoint_ids = params.get('endpoint', [])
    if len(endpoint_ids) != 1 or endpoint_ids[0] not in ENDPOINTS:
        raise ValueError('Wybierz obsługiwaną metodę API BDL.')
    endpoint = ENDPOINTS[endpoint_ids[0]]
    fields = {p['name']: p for p in endpoint['parameters']}
    if set(params) - set(fields) - {'endpoint'}:
        raise ValueError('Zapytanie zawiera nieobsługiwane pola.')
    path = endpoint['path']
    query = [('format', 'json'), ('lang', 'pl')]
    for name, field in fields.items():
        values = [v.strip() for v in params.get(name, []) if v.strip()]
        if field['type'] == 'array':
            values = [part.strip() for value in values for part in value.split(',') if part.strip()]
        elif len(values) > 1:
            raise ValueError(f'Podaj tylko jedną wartość pola {name}.')
        if field['required'] and not values:
            raise ValueError(f'Uzupełnij wymagane pole {name}.')
        if len(values) > 100:
            raise ValueError(f'Pole {name} może zawierać maksymalnie 100 wartości.')
        for value in values:
            validate_value(field, value)
            if field['in'] == 'path':
                path = path.replace('{' + name + '}', quote(value, safe=''))
            else:
                query.append((name, value))
    return BASE_URL + path + '?' + urlencode(query)
