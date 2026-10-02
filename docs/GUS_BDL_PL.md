# Wyszukiwarka GUS BDL

## Zakres i decyzja

Realizuje Refs #2: formularze i czytelne wyniki zamiast surowego JSON. GUS ma wiele odrębnych API. Ta wersja obsługuje **Bank Danych Lokalnych (BDL), API v1**, czyli statystyki publiczne. Nie jest wyszukiwarką firm REGON/BIR, TERYT ani pozostałych API GUS. BDL działa anonimowo; integracja REGON wymaga osobnego zakresu i klucza. Aplikacja nie wymaga i nie przyjmuje żadnych sekretów.

36 metod GET ze snapshotu oficjalnego OpenAPI obejmuje:
- tematy: listy, wyszukiwanie po nazwie, szczegóły i metadane;
- zmienne: wyszukiwanie po nazwach wymiarów, temacie, poziomie i latach, listy i szczegóły;
- jednostki i miejscowości: nazwa, poziomy, lata, rodzaj i jednostka nadrzędna zgodnie z wybraną metodą;
- dane według zmiennej albo jednostki (także dla miejscowości), lata, agregacja i poziom tam, gdzie udostępnia je API;
- słowniki agregatów, atrybutów, poziomów, jednostek miary, lat, ich szczegóły i metadane oraz wersję API.

Formularze powstają ze sprawdzonego pliku `docs/bdl-openapi.json`. Wszystkie udokumentowane parametry biznesowe są dostępne. `lang=pl` i `format=json` są stałe; nagłówki transportowe nie są filtrami. To nie jest dowolny klient URL: backend łączy się tylko ze stałym adresem BDL i zatwierdzonymi ścieżkami. Wartości tablic są wysyłane jako powtarzane parametry. Numery jednostek pozostają tekstem z zerami wiodącymi.

## Uruchomienie lokalne

Wymagany Python 3.12 lub nowszy. Aplikacja nie ma zewnętrznych zależności Python ani frontendowych.

```bash
python3 -m gus_app.server
```

Otwórz http://127.0.0.1:8080. Domyślny nasłuch tylko na lokalnym interfejsie. `HOST` i `PORT` konfigurują nasłuch. Uruchomienie na publicznym interfejsie wymaga własnego reverse proxy, TLS, kontroli dostępu i limitów ruchu. Nie jest to zgoda ani przygotowanie operacyjne wdrożenia na slot. Nie dodano obrazu kontenera i nie zmieniono flag gotowości.

## Jak korzystać

1. Wybierz „Zmienne: wyszukiwanie”, wpisz `samochody` w nazwie i uruchom wyszukiwanie.
2. Wybierz interesującą zmienną lub skopiuj jej ID. W „Dane według zmiennej” podaj ID, np. `3643`, rok `2024` i poziom `2` (województwa).
3. Dla konkretnego miejsca wyszukaj jednostkę, np. `Warszawa`, potem pobierz dane według jej ID i wybranych ID zmiennych.
4. Lata i inne listy przyjmują wiele wartości. Strony API są numerowane od 0; wielkość strony to 1–100. Kolejne strony pobierasz osobno, a nie automatycznie całe wielkie zbiory.
5. Rozwiń zagnieżdżone dane i opisy pól. Słowniki „Atrybuty danych”, „Jednostki miary” i „Poziomy terytorialne” wyjaśniają identyfikatory w wynikach. Zachowane są wszystkie zwrócone pola, również nowe/nierozpoznane, wartości 0, false i null. Nie dopisujemy brakujących danych.

Wynik pokazuje źródłowy adres zapytania GUS. Puste wyniki, błędne parametry, brak sieci i limit GUS mają komunikaty po polsku. Backend ogranicza odpowiedź do 5 MiB oraz czas oczekiwania gniazda do 20 sekund. Duże odpowiedzi wymagają zawężenia filtrów. Jedna aplikacja serializuje zapytania do GUS i zachowuje odstęp minimum 250 ms; pamięć podręczna 16 odpowiedzi na 60 sekund zmniejsza powtórzenia. Nie jest to rozproszony limit dla publicznego serwisu. GUS dodatkowo egzekwuje limity dłuższych okresów (anonimowo m.in. 100 żądań / 15 minut); po 429 należy odczekać. Aplikacja nie ponawia automatycznie nieudanych zapytań.

## Prywatność i bezpieczeństwo

Zapytania trafiają z serwera aplikacji do GUS. Brak bazy danych, logowania zapytań i lokalnego zapisu wyników; krótkotrwała pamięć podręczna jest w RAM procesu. Interfejs nie używa zewnętrznych fontów, CDN, skryptów ani analityki. Dane API są wyświetlane jako tekst/elementy DOM, nie jako HTML. Backend odrzuca nieznane metody, parametry i przekierowania; nigdy nie pobiera URL podanego przez użytkownika. Nie wpisuj danych poufnych w filtry nazw statystycznych.

## Testy

```bash
bash scripts/project-ci.sh
```

Wymagany również Node.js (wyłącznie kontrola składni JS). Skrypt sprawdza składnię Pythona i JavaScript oraz uruchamia rzeczywiste testy jednostkowe i HTTP integracyjne aplikacji oraz istniejące testy polityk repozytorium. Uruchamia także deterministyczne testy kontrolera UI na atrapie DOM (`node tests/test_gus_ui.cjs`). Testy CI nie zależą od bieżącej dostępności GUS; transport zewnętrzny jest atrapą. Ręczny smoke test rzeczywistego API i kontrola przeglądarkowa są raportowane osobno w PR; nie zastępują deterministycznych testów. Dotychczasowy placeholder `APPLICATION_NOT_CONFIGURED` został zastąpiony tymi rzeczywistymi kontrolami, bez zmian `.github/`, `ops/`, `AGENTS.md` i `.agents/`.

`/healthz` potwierdza działanie procesu lokalnego, nie dostępność GUS. `/_meta` udostępnia standardowe identyfikatory adaptera; lokalnie mają wartość `local`.

## Źródła i aktualizacja kontraktu

Snapshot OpenAPI pobrano 2026-10-02 z https://bdl.stat.gov.pl/api/v1/swagger/doc/swagger.json (OpenAPI 3.0.1). Aktualizacja wymaga przeglądu różnic i testów, nie następuje automatycznie w uruchomionej aplikacji.

- Dokumentacja interaktywna: https://bdl.stat.gov.pl/api/v1/swagger/index.html
- Zakres, przykłady i limity BDL: https://api.stat.gov.pl/home/bdlapi
- Odrębne API REGON: https://api.stat.gov.pl/Home/RegonApi?lang=pl

Rzeczywiste odpowiedzi różnią się miejscami od schematów odpowiedzi Swagger: `links.next` zamiast `nextPage`, `val` zamiast `value`, `dateModified` zamiast `modificationDate`. Renderer zachowuje payload, a paginacja opiera się na zwróconych linkach/liczbie wyników i faktycznym zapytaniu.
