# Weryfikacja aplikacji GUS BDL — 2026-10-02

## Wykonane

- `bash scripts/project-ci.sh`: kontrola składni Pythona/JavaScript i 97 testów Python (54 aplikacji BDL + 43 dotychczasowe testy kontrolera/demonstracji), wszystkie przeszły.
- Testy aplikacji: zgodność katalogu z 36 metodami oficjalnego OpenAPI; wymagane/nieznane parametry; integer/enum/tablice; zachowanie zer wiodących; kodowanie parametrów i obrona przed zmianą docelowego URL; paginacja i ograniczenia rozmiaru.
- Prawdziwy lokalny serwer HTTP z atrapą GUS: kompletne odpowiedzi i wszystkie pola, statyczne pliki, nagłówki bezpieczeństwa, 400/404/414/429/502, health/meta, brak logowania wyszukiwanej treści.
- Transport: timeout, ucięta odpowiedź, nieprawidłowy JSON i Unicode, NaN/Infinity/przepełnienie liczby, limit odpowiedzi, odrzucanie przekierowań, cache/TTL/limit/współbieżność. CI nie kontaktuje się z GUS.
- Rzeczywisty lokalny serwer z docelowymi plikami: `/`, `/static/app.js`, `/static/style.css`, `/api/catalog`, `/healthz` zwróciły HTTP 200 z właściwym typem treści.
- Live GUS poprzez aplikację: zmienne `samochody`, rozmiar strony 2 → HTTP 200, 106 wyników, pierwszy „samochody osobowe”. Dane zmiennej 3643 za 2024 r. na poziomie 2 → HTTP 200, 16 jednostek, poprawnie zachowane zagnieżdżone wartości i atrybuty.
- Dodatkowy smoke oficjalnego API: tematy, zmienne/szczegóły, jednostki Warszawa, dane według jednostki, słowniki atrybutów i poziomów, metadane oraz wersja.
- Przegląd kodu: poprawiono domyślną wielkość strony przy pominiętym filtrze; zweryfikowano renderowanie tekstowe bez interpretacji HTML, zachowanie pól i odrzucanie nieaktualnych odpowiedzi.

- `node tests/test_gus_ui.cjs`: deterministyczny test kontrolera UI na lekkiej atrapie DOM, bez zależności. Sprawdzono parametry/listy, pola nested/unknown/null/false/zero, XSS, bezpieczny link źródła, paginację przy domyślnym rozmiarze 10, stare odpowiedzi, powtarzane kliknięcia, 429 i ponowienie, puste wyniki, anulowanie/czyszczenie i zera w identyfikatorach. To nie jest test renderowania przeglądarki.

## Granice weryfikacji

Kontrola wizualna w przeglądarce nie została wykonana: przeglądarka chmurowa odrzuciła lokalny adres aplikacji (`net::ERR_BLOCKED_BY_CLIENT`). Nie obchodzono tej blokady. Należy jeszcze sprawdzić wygląd desktop/mobile, obsługę klawiaturą i Back/Forward w docelowej przeglądarce.

Nie wykonano wdrożenia, budowy kontenera, testu self-hosted runnera ani testów obciążeniowych. Wynik CI GitHub dotyczy konkretnego SHA i jest raportowany w PR; powyższe punkty opisują lokalne testy. Domyślny nasłuch aplikacji jest lokalny, a publiczne udostępnienie wymaga osobnego przygotowania operacyjnego.
