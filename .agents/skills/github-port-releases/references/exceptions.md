# Wyjątki i sytuacje niebezpieczne

**BRANCH_MOVED / STALE_GENERATION:** odczytaj nowy stan, opisz różnicę i potwierdź aktualny zamiar. Nie retry z automatycznie zmienionymi wejściami.

**Pending / DRIFT / RECOVERY_REQUIRED:** nie deployuj. Zachowaj dowody i przekaż administratorowi uzgodnienie kontenerów, prywatnego dziennika i GitHub. Nie kasuj pending, nie resetuj generacji, nie przejmuj obcego portu.

**Rollback:** przywraca jeden zapisany poprzedni obraz bez budowy. Nie cofa danych i gałęzi. Zmiana konfiguracji lub data_epoch blokuje automat; nie obniżaj znacznika dla obejścia. Starszy artefakt wymaga oddzielnej administracyjnej procedury.

**FAILED_RESTORED:** nowa próba nie została przyjęta, stara usługa wróciła. Raportuj oba fakty i nową generację. Sukces odtworzenia nie oznacza sukcesu wydania.

**DEPLOYED_RECORDING_INCOMPLETE / warning:** aplikacja może już działać. Sprawdź runtime, nie zakładaj rollback na podstawie czerwonego joba.

**Hotfix:** przygotuj od aktywnej wersji; sprawdź niezrealizowane zmiany branch deploy. Zaplanuj synchronizację z main.

**Cofnięcie PR:** zachowaj historię i przygotuj nowy revert/corrective PR. Scalony PR nie staje się niescalony. Przy przywróceniu funkcji oceniaj revert rewertu lub nową implementację, nie automatyczny remerge starej gałęzi.

**Usunięcie branch / tag:** nie oznacza zatrzymania kontenera. Odtwórz powiązania przez ocenianą procedurę, a stop wykonuj tylko jawnie.

**Przeniesienie portu:** traktuj jako provision nowego slotu, test, przełączenie odbiorców i wycofanie starego. Nie rename jako automatyczna migracja.

**Sekret ujawniony:** nie pokazuj go w raporcie. Zgłoś konieczność revocation/rotation i ocenianego oczyszczenia historii. Zwykły revert nie usuwa historycznej treści.

**Nieznana platforma aplikacji:** nie usuwaj ograniczeń adaptera. Zgłoś potrzebę obsługi volumes/migracji/Compose/ARM itp. i pozostaw blokady gotowości do czasu odbioru.


**RUNTIME_CONFIG_CHANGED:** nie obchodź odmowy. Wymagaj zatwierdzonego okna stop/configure/deploy; po zmianie danych poprzedni obraz może nie nadawać się do powrotu. Nie zmieniaj konfiguracji podczas aktywnego workflow.
