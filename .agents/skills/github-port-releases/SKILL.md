---
name: github-port-releases
description: Prowadzenie zmian i wydań w repozytorium z portowymi gałęziami deploy/pNNNN i kontrolerem port-release na self-hosted runnerze. Stosuj przy przygotowaniu PR wydania, wyborze slotu, promocji obrazu, rollback, hotfix, diagnozie rozbieżności runtime, zmianie konfiguracji wdrożenia lub usuwaniu funkcji w takim projekcie. Uwzględniaj zatwierdzenie menedżera, pełne SHA, generację stanu, identyfikator wdrożenia i zakaz samowolnych mutacji.
---

# Wydania GitHub na slotach portowych

## Odczytaj kontekst, nie odtwarzaj go z pamięci

1. Odczytaj lokalne `AGENTS.md`, `ops/slots.json` i zlecenie/issue. Sprawdź repozytorium, branch, base SHA oraz zmiany robocze. Nie nadpisuj cudzej pracy.
2. Ustal rodzaj zadania: kod/PR, przygotowanie wydania, odczyt status, dozwolona mutacja albo incydent. Nie interpretuj samego „napraw” jako zgody na wydanie.
3. Odczytaj aktualne dane przez dostępne Git/gh, API GitHub lub połączony konektor. Nie deklaruj odczytu ani operacji, której narzędzie nie potwierdziło. Gdy brak dostępu, przygotuj instrukcję z jawnymi brakami, bez wymyślonych SHA i statusów.
4. Wczytaj [kontrakt operacji](references/contract.md) przy doborze branch/inputs i [obsługę wyjątków](references/exceptions.md) przy rollback, incydencie lub nietypowej integracji. Szczegóły repozytorium znajdują się w `docs/PLAYBOOK_PL.md`; czytaj tylko potrzebne rozdziały.

## Utrzymuj lokalne konwencje

- Używaj krótkich gałęzi `feat|fix|exp|docs|ops|hotfix/ISSUE-opis`. Dopuszczaj prefiks `codex/` na gałęzi roboczej, jeśli narzędzie go narzuca.
- Używaj `main` jako wspólnej zaakceptowanej integracji. Zestaw wydania może powstać na `release/YYYY-MM-DD-rN`.
- Traktuj tylko dokładne, zarejestrowane `deploy/p<port>` jako gałęzie slotów. Nie dopisuj slugów i nie wybieraj wolnego portu samodzielnie. Nazwa oraz allowlista muszą się zgadzać.
- Proponuj squash do main dla krótkiego zadania i merge commit przy integracji do długotrwałego deploy. Nie stosuj wymagania linear history do deploy, które blokowałoby ten model.
- Linkuj domyślnie `Refs #...`. Rozdziel ukończenie kodu od odbioru produktu; nie zamykaj issue automatycznie przez `Closes`, gdy jeszcze wymagane są wdrożenie i akceptacja.
- Przechowuj karty wydań jako issue/rekordy, nie pliki różniące tree między slotami.

## Przygotuj zmianę lub wydanie

Potwierdź cel, kryteria, granice, dane i zależności. Przygotuj najmniejszy spójny zakres oraz test regresji. Używaj faktycznych testów projektu; nie wyłączaj kontroli, nie ustawiaj `application_ready=true` i nie podmieniaj testów na sukces, aby przejść CI.

Dla wydania porównaj całą kandydacką zawartość z aktywnym wydaniem, nie tylko ostatni PR. Ustal, czy branch deploy zawiera niewydane zmiany albo zmiany wcześniej wycofane w runtime. Utwórz PR do poprawnego slotu; nie wykonuj bezpośredniego push do main/deploy.

Dla hotfix zacznij od uzgodnionej aktywnej wersji. Zaplanuj osobno przeniesienie poprawki do main i innych celów, aby nie zniknęła w następnym wydaniu. Nie dołączaj automatycznie wszystkich nowszych funkcji z main.

## Oddziel identyfikatory i dowody

Zapisuj osobno:

- `controller_sha`: rewizja workflow z main.
- `target_sha`: pełny SHA wybranego HEAD gałęzi docelowej.
- `build_sha`: kod, z którego wytworzono obraz.
- `tree_sha`: zawartość Git; służy do porównania przy promocji.
- `image`: niemutowalny digest obrazu w zatwierdzonym GHCR.
- `deployment_id` i `generation`: konkretne uruchomienie i wersja stanu slotu.

Nie przedstawiaj `github.sha` joba kontrolnego jako kodu aplikacji. Nie przedstawiaj zbudowania obrazu jako wdrożenia. Nie przedstawiaj udanego healthcheck jako akceptacji biznesowej.

## Respektuj granice zgody

Zlecenie implementacji obejmuje przygotowanie kodu, testów i PR-a, nie jego merge ani zmianę runtime. Dopuszczaj mutację wyłącznie po jednoznacznej zgodzie człowieka obejmującej operację, cel, zakres i ryzyko danych.

Dla deploy/promote zgodę wiąż z pełnym target SHA i aktualną generacją. Dla promote wymagaj również konkretnego source_deployment_id. Dla rollback potwierdź identyfikator poprzedniego obrazu i zgodność danych. Dla stop jawnie nazwij odbiorców dotkniętego slotu.

Nie pytaj ponownie o zgodę już otrzymaną dla dokładnie tego zakresu. Gdy odczyt ujawni nowy SHA, generację lub ryzyko, zatrzymaj mutację i przedstaw zmianę sytuacji. Nie odświeżaj parametrów po odmowie tylko po to, aby kontroler wykonał operację.

Nigdy nie wykonuj samowolnie force push, reset wspólnej historii, usuwania branch deploy, migracji, kasowania danych, zmiany sekretów, wyłączenia zabezpieczeń runnera lub edycji plików stanu hosta.

## Uruchom tylko zatwierdzoną operację

1. Wykonaj lub odczytaj świeży status, gdy upoważnienie pozwala na odczyt. Zatrzymaj się przy pending, drift albo nieznanym stanie.
2. Przygotuj formularz `port-release.yml` z `--ref main` / wyborem main. Nie dispatchuj workflow ze źródłowej gałęzi kandydata.
3. Wymagaj pełnych inputs z kontraktu. Nie wpisuj dowolnego obrazu, polecenia powłoki ani portu spoza rejestru.
4. Dla promote zachowaj ten sam digest. Zgodne tree przy różnych merge SHA jest dozwolone; różne tree wymaga uzgodnienia kodu lub nowego deploy.
5. Po dozwolonym wykonaniu odczytaj wynik Actions, status runtime i `/_meta`. Zaktualizuj kartę z dowodami. W razie braku dostępu oznacz wynik jako niezweryfikowany.

Nie uruchamiaj kodu/testów kandydata na hoście wdrożeniowym. Korzystaj z preinstalowanego kontrolera przez zatwierdzony workflow. Różne porty nie zapewniają izolacji cookies, danych, zadań w tle ani uprawnień.

## Raportuj dla menedżera

Kończ pracę krótkim raportem po polsku:

**Cel / stan:** co miało powstać i co faktycznie ukończono.
**Zmiana:** repo, branch, PR i uzgodniony zakres.
**Dowody:** testy wykonane, testy niewykonane, linki; przy runtime identyfikatory i observed.
**Ryzyko:** dane, konfiguracja, zależności oraz możliwość powrotu.
**Decyzja:** jedyna następna potrzebna decyzja lub brak decyzji.

Przygotowanie planu nie jest wykonaniem. Brak błędu w narzędziu nie jest dowodem, że użytkownik widzi poprawny produkt.

