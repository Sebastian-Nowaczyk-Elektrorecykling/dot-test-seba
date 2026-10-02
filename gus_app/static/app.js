/* BDL Explorer: dependency-free, data-driven forms and lossless presentation. */
'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const state = { endpoints: [], selected: null, controller: null, sequence: 0, lastAttempt: null, lastResult: null, pagination: null, dirty: false, retry: null };
  const resourceLabels = { variables: 'Zmienne i wskaźniki', units: 'Jednostki terytorialne i miejscowości', data: 'Dane statystyczne', subjects: 'Dziedziny i tematy', attributes: 'Atrybuty danych', measures: 'Jednostki miary', aggregates: 'Poziomy agregacji', levels: 'Poziomy dostępności', years: 'Lata', version: 'Informacje o API' };
  const labels = {
    id: 'Identyfikator', name: 'Nazwa', n1: 'Nazwa — poziom 1', n2: 'Nazwa — poziom 2', n3: 'Nazwa — poziom 3', n4: 'Nazwa — poziom 4', n5: 'Nazwa — poziom 5',
    subjectId: 'Identyfikator tematu', subjectName: 'Temat', level: 'Poziom terytorialny', parentId: 'Jednostka nadrzędna', kind: 'Rodzaj jednostki',
    year: 'Rok', years: 'Dostępne lata', value: 'Wartość', val: 'Wartość', values: 'Wartości w latach', attrId: 'Atrybut danych', attributeId: 'Atrybut danych',
    variableId: 'Identyfikator zmiennej', variableName: 'Zmienna', varId: 'Identyfikator zmiennej', unitId: 'Identyfikator jednostki', unitName: 'Nazwa jednostki',
    measureUnitId: 'Identyfikator jednostki miary', measureUnitName: 'Jednostka miary', measureUnit: 'Jednostka miary', aggregateId: 'Poziom agregacji',
    totalRecords: 'Łączna liczba wyników', page: 'Indeks strony', pageSize: 'Wyników na stronę', results: 'Wyniki', resultsOrdered: 'Wyniki uporządkowane',
    links: 'Odnośniki API', metadata: 'Metadane', version: 'Wersja API', description: 'Opis', notes: 'Uwagi', lastUpdate: 'Ostatnia aktualizacja',
    first: 'Pierwsza strona', firstPage: 'Pierwsza strona', prev: 'Poprzednia strona', previous: 'Poprzednia strona', prevPage: 'Poprzednia strona',
    self: 'Bieżąca strona', next: 'Następna strona', nextPage: 'Następna strona', last: 'Ostatnia strona', lastPage: 'Ostatnia strona',
    'subject-id': 'Identyfikator tematu', 'var-id': 'Identyfikator zmiennej', 'unit-id': 'Identyfikator jednostki', 'unit-parent-id': 'Jednostka nadrzędna',
    'parent-id': 'Identyfikator nadrzędny', 'unit-level': 'Poziom jednostek', 'aggregate-id': 'Poziom agregacji', 'page-size': 'Wyników na stronę', sort: 'Sortowanie',
    symbol: 'Symbol', hasChildren: 'Ma elementy podrzędne', children: 'Elementy podrzędne', lang: 'Język', title: 'Tytuł', url: 'Adres', href: 'Adres', rel: 'Relacja'
  };
  const hints = {
    name: 'Wpisz fragment nazwy. Nie musisz znać jej w całości.', year: 'Jeden rok lub kilka lat, np. 2022, 2023.',
    page: 'API liczy strony od zera: 0 to pierwsza strona.', 'page-size': 'Mniejsza liczba wyników przyspiesza odpowiedź.',
    'var-id': 'Identyfikator znajdziesz w wynikach wyszukiwania zmiennych.', 'unit-id': 'Użyj identyfikatora BDL, zachowując zera na początku.',
    'unit-parent-id': 'Identyfikator BDL obszaru, do którego zawęzisz dane.', 'parent-id': 'Identyfikator elementu, którego podziały chcesz zobaczyć.',
    'subject-id': 'Identyfikator znajdziesz w zasobach „Dziedziny i tematy”.', level: 'Poziom podziału opisany w dokumentacji tego parametru.',
    'unit-level': 'Poziom jednostek terytorialnych opisany w dokumentacji parametru.', 'aggregate-id': 'Identyfikator ze słownika „Poziomy agregacji”.'
  };
  const friendly = (key) => Object.hasOwn(labels, key) ? labels[key] : key.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[-_]/g, ' ').replace(/^./, (v) => v.toLocaleUpperCase('pl'));
  const node = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = String(text); return el; };
  const isRecord = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
  const isComposite = (v) => v !== null && typeof v === 'object';
  const countFormat = (v) => new Intl.NumberFormat('pl-PL').format(v);
  const resource = (endpoint) => endpoint?.path.split('/').filter(Boolean)[0] || '';
  const parameters = () => state.selected?.parameters || [];
  const control = (name) => Array.from($('parameters').querySelectorAll('input, select')).find((el) => el.name === name);
  const endpointByPath = (path) => state.endpoints.find((ep) => ep.path === path);
  const titleOf = (endpoint) => endpoint?.title || endpoint?.path || 'Dane BDL';
  const officialUrl = (value) => {
    try { const u = new URL(value); return (u.protocol === 'https:' || u.protocol === 'http:') && !u.username && !u.password && (u.hostname === 'stat.gov.pl' || u.hostname.endsWith('.stat.gov.pl')) ? u.href : null; }
    catch { return null; }
  };
  const announce = (text) => { $('live-status').textContent = text; };
  function resetRequest() {
    state.sequence += 1;
    state.controller?.abort();
    state.controller = null;
    setLoading(false);
  }
  function setLoading(loading) {
    $('results-panel').setAttribute('aria-busy', String(loading));
    $('loading-state').hidden = !loading;
    $('search-button').disabled = loading || !state.selected;
    $('search-button').replaceChildren(node('span', '', loading ? '◌' : '⌕'), document.createTextNode(loading ? 'Pobieranie…' : 'Pobierz dane'));
    $('search-button').firstElementChild.setAttribute('aria-hidden', 'true');
    for (const id of ['previous-page', 'next-page']) $(id).disabled = loading || state.dirty || !state.pagination?.[id === 'previous-page' ? 'previous' : 'next'];
  }
  function clearPresentation() {
    $('results-content').replaceChildren();
    for (const id of ['error-box', 'no-results', 'pagination', 'source-footer', 'request-note']) $(id).hidden = true;
    $('empty-state').hidden = false;
    $('result-badge').textContent = 'Gotowe na pytanie';
    state.lastResult = null;
    state.pagination = null;
    state.lastAttempt = null;
    state.dirty = false;
  }
  function showError(message, catalog = false) {
    $('empty-state').hidden = true;
    $('error-box').hidden = false;
    $('error-title').textContent = catalog ? 'Katalog zasobów jest niedostępny' : 'Nie udało się pobrać danych';
    $('error-message').textContent = message;
    $('result-badge').textContent = 'Spróbuj ponownie';
    state.retry = catalog ? loadCatalog : () => state.lastAttempt && runQuery(new URLSearchParams(state.lastAttempt));
    announce(message);
  }
  function defaultValue(parameter) {
    if (parameter.name === 'page') return '0';
    if (parameter.name === 'page-size') return String(Math.min(20, parameter.maximum ?? 20));
    return '';
  }
  function fieldLabel(parameter) {
    if (parameter.name === 'name') return resource(state.selected) === 'variables' ? 'Czego szukasz?' : resource(state.selected) === 'subjects' ? 'Nazwa tematu' : 'Nazwa miejsca';
    if (parameter.name === 'year') return 'Rok lub lata';
    if (parameter.name === 'id') return `Identyfikator (${resourceLabels[resource(state.selected)] || 'zasób'})`;
    if (parameter.name === 'var-id' && parameter.type === 'array') return 'Identyfikatory zmiennych';
    if (parameter.name === 'page') return 'Strona API (od 0)';
    return friendly(parameter.name);
  }
  function makeField(parameter, index) {
    const wrap = node('div', 'field');
    const label = node('label', '', fieldLabel(parameter));
    const id = `parameter-${index}`;
    label.htmlFor = id;
    if (parameter.required) { const star = node('span', 'required-star', '*'); star.setAttribute('aria-hidden', 'true'); label.append(star); }
    let input;
    if (parameter.type === 'boolean' || (Array.isArray(parameter.enum) && parameter.type !== 'array')) {
      input = node('select'); input.append(new Option('Domyślnie (bez filtra)', ''));
      const values = parameter.type === 'boolean' ? [true, false] : parameter.enum;
      values.forEach((value) => input.append(new Option(value === true ? 'Tak' : value === false ? 'Nie' : String(value), String(value))));
    } else {
      input = node('input'); input.type = parameter.type === 'integer' ? 'number' : 'text';
      if (parameter.type === 'integer') { input.step = '1'; if (parameter.minimum !== undefined) input.min = String(parameter.minimum); if (parameter.maximum !== undefined) input.max = String(parameter.maximum); }
      if (parameter.name === 'page') input.min = String(Math.max(0, parameter.minimum ?? 0));
      if (parameter.name === 'page-size') input.min = String(Math.max(1, parameter.minimum ?? 1));
      if (parameter.name === 'name') input.placeholder = resource(state.selected) === 'variables' ? 'np. samochody…' : resource(state.selected) === 'subjects' ? 'np. ludność…' : 'np. Warszawa, Kraków…';
      else if (parameter.name === 'year') input.placeholder = 'np. 2022, 2023';
      else if (parameter.type === 'array') input.placeholder = 'Wartości oddziel przecinkami';
      else input.placeholder = parameter.required ? 'Wymagane' : 'Opcjonalnie';
      input.autocomplete = 'off';
    }
    input.id = id; input.name = parameter.name; input.required = Boolean(parameter.required); input.value = defaultValue(parameter);
    wrap.append(label, input);
    let hintText = hints[parameter.name] || (parameter.description ? parameter.description.split(/\s\/\s/)[0] : 'Opcjonalny filtr opisany w dokumentacji BDL.');
    if (parameter.type === 'array' && parameter.name !== 'year') hintText += ' Kilka wartości oddziel przecinkami.';
    const hint = node('p', 'field-hint', hintText); hint.id = `${id}-hint`; input.setAttribute('aria-describedby', hint.id); wrap.append(hint);
    const detail = node('details', 'parameter-detail'); detail.append(node('summary', '', 'Opis parametru w API'));
    const description = node('p', '', parameter.description || 'Opis tego parametru nie został podany w katalogu API.');
    description.append(node('br'), node('code', '', `${parameter.name} · ${parameter.type} · ${parameter.in === 'path' ? 'ścieżka' : 'filtr'}`));
    if (parameter.minimum !== undefined || parameter.maximum !== undefined) description.append(node('br'), document.createTextNode(`Zakres: ${parameter.minimum ?? 'bez minimum'} – ${parameter.maximum ?? 'bez maksimum'}.`));
    if (parameter.type === 'array' && parameter.items?.enum) description.append(node('br'), document.createTextNode(`Dozwolone wartości: ${parameter.items.enum.join(', ')}.`));
    detail.append(description); wrap.append(detail);
    input.addEventListener('input', markDirty); input.addEventListener('change', markDirty);
    return wrap;
  }
  function markDirty() {
    if (state.controller) { resetRequest(); announce('Zapytanie anulowane po zmianie filtrów.'); }
    state.dirty = true;
    if (state.lastAttempt) { $('request-note').hidden = false; $('request-note').textContent = 'Filtry zostały zmienione. Wybierz „Pobierz dane”, aby zobaczyć aktualne wyniki.'; }
    $('error-box').hidden = true;
    $('result-badge').textContent = 'Zmieniono filtry';
    setLoading(false);
  }
  function selectEndpoint(endpoint, values = {}, focus = false) {
    if (!endpoint) return;
    resetRequest(); clearPresentation();
    state.selected = endpoint; $('endpoint').value = endpoint.id;
    $('endpoint-description').textContent = endpoint.description || titleOf(endpoint);
    $('endpoint-path').textContent = endpoint.path; $('endpoint-path').hidden = false;
    $('parameters').replaceChildren();
    const list = endpoint.parameters || [];
    $('parameter-count').textContent = `${list.length} ${list.length === 1 ? 'parametr' : 'parametrów'}`;
    const primary = node('div');
    const advanced = node('details', 'advanced-filters');
    const advancedFields = node('div'); let advancedCount = 0;
    list.forEach((parameter, index) => {
      const field = makeField(parameter, index);
      const isAdvanced = !parameter.required && parameter.in !== 'path' && !['name', 'search', 'year', 'var-id', 'unit-id'].includes(parameter.name);
      if (isAdvanced) { advancedFields.append(field); advancedCount += 1; } else primary.append(field);
    });
    $('parameters').append(primary);
    if (advancedCount) { advanced.append(node('summary', '', `Więcej filtrów i stronicowanie (${advancedCount})`), advancedFields); $('parameters').append(advanced); }
    if (!list.length) $('parameters').append(node('p', 'no-parameters', 'Ten zasób nie wymaga filtrów. Wybierz „Pobierz dane”, aby go odczytać.'));
    Object.entries(values).forEach(([key, value]) => { const input = control(key); if (input) { input.value = String(value); if (input.closest('.advanced-filters')) input.closest('.advanced-filters').open = true; } });
    document.querySelectorAll('[data-mode]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.mode === resource(endpoint))));
    $('search-button').disabled = false; $('clear-button').disabled = false;
    if (focus) { $('explorer').scrollIntoView({ behavior: 'smooth', block: 'start' }); ($('parameters').querySelector('input, select') || $('search-button')).focus({ preventScroll: true }); }
  }
  function formQuery() {
    const query = new URLSearchParams({ endpoint: state.selected.id });
    for (const parameter of parameters()) {
      const input = control(parameter.name); const value = input?.value.trim();
      if (!value) continue;
      if (parameter.type === 'array') value.split(/[,;\n]+/).map((v) => v.trim()).filter(Boolean).forEach((v) => query.append(parameter.name, v));
      else query.set(parameter.name, value);
    }
    return query;
  }
  function valueNode(value, depth = 0, context = {}) {
    if (value === null) return node('span', 'value-empty', 'Brak wartości (null)');
    if (value === undefined) return node('span', 'value-empty', 'Pole nieobecne');
    if (typeof value === 'boolean') return node('span', 'value-boolean', value ? 'Tak (true)' : 'Nie (false)');
    if (typeof value === 'number') return node('span', 'numeric', String(value));
    if (typeof value === 'string') return value === '' ? node('span', 'value-empty', 'Pusty tekst') : node('span', 'value-text', value);
    if (Array.isArray(value)) return arrayNode(value, depth, context);
    return objectNode(value, depth, context);
  }
  function nestedValue(value, depth) {
    if (!isComposite(value)) return valueNode(value, depth);
    const detail = node('details', 'nested-data');
    const length = Array.isArray(value) ? value.length : Object.keys(value).length;
    detail.append(node('summary', '', Array.isArray(value) ? `Pokaż elementy (${length})` : `Pokaż pola (${length})`), valueNode(value, depth + 1));
    return detail;
  }
  function fieldName(key) {
    const label = node('span', '', friendly(key));
    if (friendly(key) !== key) label.append(node('span', 'field-key', key));
    return label;
  }
  function actionButtons(record, endpoint) {
    const id = record.id ?? record.variableId ?? record.unitId;
    if (id === undefined || id === null || isComposite(id)) return null;
    const kind = resource(endpoint); const actions = node('div', 'row-actions');
    const add = (text, path, params, secondary = false) => {
      const target = endpointByPath(path); if (!target) return;
      const button = node('button', `row-action${secondary ? ' secondary' : ''}`, text); button.type = 'button';
      button.addEventListener('click', () => {
        selectEndpoint(target, params, true);
        announce(`Wybrano ${titleOf(target)}. Sprawdź filtry i pobierz dane.`);
      }); actions.append(button);
    };
    if (kind === 'variables') { add('Zobacz dane →', '/data/by-variable/{var-id}', { 'var-id': id }); if (endpoint.path !== '/variables/{id}') add('Szczegóły zmiennej', '/variables/{id}', { id }, true); }
    if (kind === 'units') {
      const locality = endpoint.path.includes('/localities');
      add('Zobacz dane →', locality ? '/data/localities/by-unit/{unit-id}' : '/data/by-unit/{unit-id}', { 'unit-id': id });
      const detailPath = locality ? '/units/localities/{id}' : '/units/{id}';
      if (endpoint.path !== detailPath) add('Szczegóły miejsca', detailPath, { id }, true);
    }
    if (kind === 'subjects') add('Zmienne tematu →', '/variables', { 'subject-id': id });
    return actions.childElementCount ? actions : null;
  }
  function arrayNode(array, depth, context) {
    if (!array.length) return node('span', 'value-empty', 'Brak elementów (pusta lista)');
    if (array.every((v) => !isComposite(v))) {
      const list = node('ul', 'scalar-list'); array.forEach((value) => { const item = node('li'); item.append(valueNode(value, depth + 1)); list.append(item); }); return list;
    }
    if (array.every(isRecord)) {
      const keys = Array.from(new Set(array.flatMap((record) => Object.keys(record))));
      const actions = context.records ? array.map((record) => actionButtons(record, state.selected)) : [];
      const haveActions = actions.some(Boolean);
      if (!keys.length && !haveActions) { const list = node('ul', 'scalar-list'); array.forEach(() => list.append(node('li', 'value-empty', 'Pusty obiekt'))); return list; }
      const scroll = node('div', 'table-scroll'); scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Tabela danych. W razie potrzeby przewiń ją poziomo.');
      const table = node('table', 'data-table'); const caption = node('caption', 'sr-only', `Dane BDL: ${array.length} rekordów. Wszystkie pola odpowiedzi.`); table.append(caption);
      const head = node('thead'); const headRow = node('tr');
      if (haveActions) { const th = node('th', '', 'Odkrywaj dalej'); th.scope = 'col'; headRow.append(th); }
      keys.forEach((key) => { const th = node('th'); th.scope = 'col'; th.append(fieldName(key)); headRow.append(th); }); head.append(headRow); table.append(head);
      const body = node('tbody');
      array.forEach((record, index) => {
        const row = node('tr');
        if (haveActions) { const cell = node('td'); cell.append(actions[index] || node('span', 'value-empty', '—')); row.append(cell); }
        keys.forEach((key) => {
          const cell = node('td', ['name', 'n1', 'unitName', 'variableName'].includes(key) ? 'primary-value' : '');
          cell.append(nestedValue(Object.hasOwn(record, key) ? record[key] : undefined, depth + 1)); row.append(cell);
        }); body.append(row);
      }); table.append(body); scroll.append(table); return scroll;
    }
    const list = node('ol', 'mixed-list');
    array.forEach((value, index) => { const item = node('li'); item.append(node('span', 'item-index', `Element ${index + 1}`), valueNode(value, depth + 1)); list.append(item); }); return list;
  }
  function objectNode(object, depth, context) {
    const entries = Object.entries(object);
    if (!entries.length) return node('span', 'value-empty', 'Pusty obiekt');
    const dl = node('dl', 'object-properties');
    entries.forEach(([key, value]) => { const dt = node('dt'); dt.append(fieldName(key)); const dd = node('dd'); dd.append(nestedValue(value, depth + 1)); dl.append(dt, dd); });
    if (context.records) { const wrapper = node('div'); wrapper.append(dl); const actions = actionButtons(object, state.selected); if (actions) { const actionsWrap = node('div', 'record-actions'); actionsWrap.append(actions); wrapper.append(actionsWrap); } return wrapper; }
    return dl;
  }
  function renderData(data) {
    const root = $('results-content'); root.replaceChildren();
    if (isRecord(data) && Object.hasOwn(data, 'results')) {
      const section = node('section', 'data-section'); const heading = node('h3', 'data-section-heading', 'Wyniki');
      if (Array.isArray(data.results)) heading.append(node('span', 'count', `${countFormat(data.results.length)} na tej stronie`));
      section.append(heading, valueNode(data.results, 0, { records: true })); root.append(section);
      // Every field is preserved, including alternative result arrays and unfamiliar metadata.
      Object.entries(data).filter(([key]) => key !== 'results').forEach(([key, value]) => {
        const section = node('details', 'data-section metadata-section');
        const summary = node('summary'); summary.append(fieldName(key)); if (Array.isArray(value)) summary.append(document.createTextNode(` (${value.length})`));
        section.append(summary, valueNode(value, 0)); root.append(section);
      });
    } else { const section = node('section', 'data-section'); section.append(valueNode(data, 0, { records: true })); root.append(section); }
    if (resource(state.selected) === 'data') {
      const note = node('p', 'data-section field-hint', 'Wartości interpretuj łącznie z atrybutem danych (attrId): zero może oznaczać brak danych lub tajemnicę statystyczną. Znaczenie kodów sprawdzisz w zasobie „Atrybuty danych”.'); root.prepend(note);
    }
  }
  function hasPageLink(links, direction) {
    const keys = direction === 'next' ? ['next', 'nextPage'] : ['prev', 'previous', 'prevPage', 'previousPage'];
    if (isRecord(links)) return keys.some((key) => Boolean(links[key]));
    if (Array.isArray(links)) return links.some((link) => isRecord(link) && keys.includes(link.rel) && Boolean(link.href || link.url));
    return false;
  }
  function renderPagination(data, query) {
    if (!parameters().some((parameter) => parameter.name === 'page')) { $('pagination').hidden = true; state.pagination = null; return; }
    const page = Number(query.get('page') || '0');
    const defaultSize = parameters().find((parameter) => parameter.name === 'page-size')?.default || 10;
    const size = isRecord(data) && Number(data.pageSize) > 0 ? Number(data.pageSize) : Number(query.get('page-size') || defaultSize);
    const total = isRecord(data) && typeof data.totalRecords === 'number' && data.totalRecords >= 0 ? data.totalRecords : null;
    const next = hasPageLink(data?.links, 'next') || (total !== null && (page + 1) * size < total);
    const previous = page > 0;
    state.pagination = { previous, next, page, query: query.toString() };
    $('pagination').hidden = !previous && !next;
    $('previous-page').disabled = !previous; $('next-page').disabled = !next;
    const pages = total !== null ? Math.max(1, Math.ceil(total / size)) : null;
    $('page-label').textContent = `Strona ${page + 1}${pages !== null ? ` z ${countFormat(pages)}` : ''}`;
  }
  async function runQuery(query) {
    resetRequest(); const sequence = state.sequence;
    state.controller = new AbortController(); state.lastAttempt = query.toString(); state.lastResult = null; state.pagination = null; state.dirty = false;
    $('results-content').replaceChildren();
    for (const id of ['empty-state', 'error-box', 'no-results', 'pagination', 'source-footer']) $(id).hidden = true;
    $('request-note').hidden = false; $('request-note').replaceChildren(node('strong', '', titleOf(state.selected)), document.createTextNode(' · '), node('span', '', state.selected.path));
    $('result-badge').textContent = 'Pobieranie'; setLoading(true); announce('Pobieranie danych z BDL.');
    try {
      const response = await fetch(`/api/query?${query}`, { signal: state.controller.signal, headers: { Accept: 'application/json' } });
      let payload; try { payload = await response.json(); } catch { throw new Error('Serwer zwrócił nieczytelną odpowiedź. Spróbuj ponownie za chwilę.'); }
      if (sequence !== state.sequence) return;
      if (!response.ok) throw new Error(payload.error || (response.status === 429 ? 'Limit zapytań został wyczerpany. Odczekaj chwilę i spróbuj ponownie.' : 'BDL jest chwilowo niedostępny. Spróbuj ponownie.'));
      if (!Object.hasOwn(payload, 'data')) throw new Error('Odpowiedź nie zawiera danych BDL. Spróbuj ponownie.');
      state.lastResult = payload; renderData(payload.data); renderPagination(payload.data, query);
      const records = Array.isArray(payload.data) ? payload.data : payload.data?.results;
      const total = typeof payload.data?.totalRecords === 'number' ? payload.data.totalRecords : null;
      const empty = Array.isArray(records) && records.length === 0;
      $('no-results').hidden = !empty;
      $('result-badge').textContent = total !== null ? `${countFormat(total)} wyników` : Array.isArray(records) ? `${countFormat(records.length)} wyników` : 'Odpowiedź odebrana';
      const source = officialUrl(payload.source);
      $('source-footer').hidden = false; $('source-link').hidden = !source;
      if (source) $('source-link').href = source; else $('source-link').removeAttribute('href');
      announce(empty ? 'Brak wyników dla wybranych filtrów.' : `Dane zostały pobrane. ${$('result-badge').textContent}.`);
    } catch (error) {
      if (sequence !== state.sequence || error.name === 'AbortError') return;
      showError(error instanceof TypeError ? 'Nie można połączyć się z serwerem. Sprawdź połączenie i spróbuj ponownie.' : error.message);
    } finally {
      if (sequence === state.sequence) { state.controller = null; setLoading(false); }
    }
  }
  async function loadCatalog() {
    resetRequest(); const sequence = state.sequence; state.controller = new AbortController();
    $('error-box').hidden = true; $('result-badge').textContent = 'Wczytywanie katalogu';
    $('retry-button').disabled = true;
    try {
      const response = await fetch('/api/catalog', { signal: state.controller.signal, headers: { Accept: 'application/json' } });
      const payload = await response.json();
      if (sequence !== state.sequence) return;
      if (!response.ok || !Array.isArray(payload.endpoints) || !payload.endpoints.length) throw new Error(payload.error || 'Nie udało się wczytać listy zasobów BDL. Spróbuj ponownie.');
      state.endpoints = payload.endpoints; $('endpoint').replaceChildren();
      const groups = new Map();
      payload.endpoints.forEach((endpoint) => {
        const key = resource(endpoint); if (!groups.has(key)) { const group = node('optgroup'); group.label = resourceLabels[key] || friendly(key); groups.set(key, group); }
        groups.get(key).append(new Option(titleOf(endpoint), endpoint.id));
      }); groups.forEach((group) => $('endpoint').append(group));
      $('endpoint').disabled = false;
      document.querySelectorAll('[data-mode], [data-example]').forEach((button) => { button.disabled = false; });
      selectEndpoint(endpointByPath('/variables/search') || endpointByPath('/variables') || payload.endpoints[0]);
      announce('Katalog wczytany. Wybierz filtry i pobierz dane.');
    } catch (error) { if (sequence === state.sequence && error.name !== 'AbortError') showError('Nie można pobrać katalogu zasobów. Sprawdź połączenie i spróbuj ponownie.', true); }
    finally { $('retry-button').disabled = false; if (sequence === state.sequence) state.controller = null; }
  }
  $('query-form').addEventListener('invalid', (event) => { const group = event.target.closest('details'); if (group) group.open = true; }, true);
  $('query-form').addEventListener('submit', (event) => { event.preventDefault(); if (state.selected && !state.controller && $('query-form').reportValidity()) runQuery(formQuery()); });
  $('endpoint').addEventListener('change', () => selectEndpoint(state.endpoints.find((ep) => ep.id === $('endpoint').value)));
  $('clear-button').addEventListener('click', () => { if (state.selected) selectEndpoint(state.selected); announce('Filtry wyczyszczone.'); });
  $('cancel-button').addEventListener('click', () => { resetRequest(); $('result-badge').textContent = 'Anulowano'; $('empty-state').hidden = false; $('request-note').textContent = 'Zapytanie anulowane. Możesz zmienić filtry i spróbować ponownie.'; announce('Zapytanie anulowane.'); });
  $('retry-button').addEventListener('click', () => { if (!state.controller) state.retry?.(); });
  document.querySelectorAll('[data-mode]').forEach((button) => button.addEventListener('click', () => {
    const modes = { variables: ['/variables/search', '/variables'], units: ['/units/search', '/units'], data: ['/data/by-variable/{var-id}', '/data/by-unit/{unit-id}'] };
    const endpoint = modes[button.dataset.mode].map(endpointByPath).find(Boolean); if (endpoint) selectEndpoint(endpoint);
  }));
  document.querySelectorAll('[data-example]').forEach((button) => button.addEventListener('click', () => {
    const examples = { population: ['/subjects/search', 'ludność'], unemployment: ['/variables/search', 'bezrobocie'], warsaw: ['/units/search', 'Warszawa'] };
    const [path, name] = examples[button.dataset.example]; const endpoint = endpointByPath(path); if (!endpoint) return;
    selectEndpoint(endpoint, { name }, true); if ($('query-form').reportValidity()) runQuery(formQuery());
  }));
  [['previous-page', -1], ['next-page', 1]].forEach(([id, delta]) => $(id).addEventListener('click', () => {
    if (state.controller || state.dirty || !state.pagination || $(id).disabled) return;
    const query = new URLSearchParams(state.pagination.query); const page = Math.max(0, state.pagination.page + delta); query.set('page', String(page));
    const pageInput = control('page'); if (pageInput) pageInput.value = String(page);
    runQuery(query); $('results-title').focus({ preventScroll: true }); $('results-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
  loadCatalog();
})();
