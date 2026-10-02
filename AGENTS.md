# Zasady repozytorium: GitHub i sloty portowe

Stosuj te reguły przy pracy nad kodem i wydaniami. Przed zmianami wydania odczytaj skill `.agents/skills/github-port-releases/SKILL.md`, konfigurację `ops/slots.json` i odpowiedni fragment `docs/PLAYBOOK_PL.md`.

## Rozdziel obiekty

- Issue to problem/decyzja; PR to proponowana zmiana; branch to historia, nie runtime.
- `main` przechowuje zaakceptowany kod. Krótkie gałęzie: `feat/123-opis`, `fix/123-opis`, `exp/123-opis`, `docs/123-opis`, `ops/123-opis`, `hotfix/123-opis`. Dopuszczalny prefiks narzędzia `codex/` dla gałęzi roboczej.
- Slot ma dokładną nazwę `deploy/p<port>`, np. `deploy/p4101`, bez sufiksu. Wymagaj obecności w allowliście; nie przydzielaj samodzielnie portu.
- Odróżniaj controller_sha, target_sha, build_sha, image digest i deployment_id. Wyniki odbioru przypisuj do konkretnego deployment_id.

## Granice autonomii

- Standardowe zlecenie kodowania pozwala przygotować zmianę, testy i PR. Nie uprawnia do merge, deploy, promote, rollback, stop, zmiany sekretów, migracji ani usunięcia danych.
- Wykonuj mutację operacyjną wyłącznie po jednoznacznym upoważnieniu do konkretnej operacji i celu. Nie powtarzaj zgody, która już obejmuje dokładnie ten zakres; zmieniony SHA/stan wymaga ponownej decyzji.
- Nie pushuj bezpośrednio, nie force-pushuj i nie usuwaj main ani deploy/**. Nie obchodź reguł repozytorium.
- Nie zmieniaj zabezpieczeń, CI lub flag gotowości tylko po to, aby zadanie przeszło. Zmiany ops/.github/AGENTS/.agents wymagają jawnego wyróżnienia i oceny infrastrukturalnej.

## Praca i raport

Przed edycją sprawdź repozytorium, branch, base SHA i czystość working tree. Nie nadpisuj cudzych niezacommitowanych zmian. Przy wielu agentach używaj osobnych gałęzi/worktree. Nie przypisuj zlecenia do przypadkowej bieżącej gałęzi deploy.

Domyślnie linkuj `Refs #123`, nie `Closes #123`. Nie zamykaj zadania produktu jako ukończonego tylko dlatego, że kod jest scalony.

Raportuj po polsku: zamiar; faktycznie zmienione pliki; testy wykonane i niewykonane; ryzyka danych i konfiguracji; link do PR; decyzja potrzebna od człowieka. Nie deklaruj wdrożenia bez odczytanego dowodu runtime.

## Wydania

Workflow `port-release.yml` uruchamiaj zawsze z main. Dla deploy/promote wymagaj pełnego zatwierdzonego target SHA, świeżej generacji celu i dokładnego potwierdzenia slotu. Nie podstawiaj nowego SHA/generacji automatycznie po odmowie.

Promote oznacza ten sam digest i zgodny Git tree; nie nowy build. Rollback dotyczy obrazu, nie danych lub gałęzi. Pending/drift wymaga administracyjnego uzgodnienia; nie kasuj dzienników i nie zabijaj obcego procesu.

Nie wykonuj kodu z PR-a na self-hosted runnerze. Nie pobieraj sekretów do rozmowy. Nie traktuj różnych portów jako izolacji cookies, danych lub uprawnień.

