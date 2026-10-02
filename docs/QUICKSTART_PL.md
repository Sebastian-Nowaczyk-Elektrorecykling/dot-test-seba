# Pierwszy dzień i standardowe wydanie

## Najpierw administrator

Przed pracą menedżera administrator musi potwierdzić: kontrolowany runner, rejestr portów, prywatny dostęp, dane demo, rzeczywiste CI, kontrakt obrazu, health i sprawdzony rollback. Nie włączamy p4103 z realnymi danymi jako drogi na skróty. Procedura: rozdziały 20 i 24-25 w PLAYBOOK_PL.md.

## Co robi menedżer

1. **Issue.** Zapisz cel, przykład oczekiwanego wyniku, testy i czego nie zmieniamy.
2. **Codex.** Zleć pracę od main na feat/NUMER-opis. Pozwól przygotować PR, nie merge/deploy.
3. **PR do main.** Przejrzyj zakres, instrukcję odbioru i wyniki faktycznych testów. Scal zatwierdzoną zmianę.
4. **PR do slotu.** Przygotuj wydanie z uzgodnionego zestawu do deploy/p4101. Sprawdź cały wynikowy diff. Użyj merge commit, nie squash, dla tej długotrwałej gałęzi.
5. **Actions.** Uruchom Port release (manual) z main. Najpierw operation=status, slot_branch=deploy/p4101. Zapisz generation i aktualny stan.
6. **Deploy.** W nowym przebiegu podaj operation=deploy, ten sam slot, pełny target SHA z HEAD gałęzi, expected_generation, confirm=deploy/p4101 i reason z numerem karty wydania.
7. **Odbiór.** Sprawdź observed, digest i deployment_id; otwórz URL oraz /_meta. Wykonaj testy biznesowe i zapisz rezultat w karcie wydania.

Nie używaj pola „Use workflow from” do wyboru aplikacji: w nim zawsze main. Cel określa slot_branch, a kod -- target_sha.

## Po akceptacji

Promocja na p4102 wymaga nowego PR-a uzgadniającego zawartość gałęzi celu z zaakceptowaną zawartością. Różne SHA są dopuszczalne, różne Git tree -- nie. Zleć prepare agentowi. W Actions użyj promote ze świeżą generacją celu, pełnym target SHA, promote_from i dokładnym source_deployment_id. Nie buduj ponownie obrazu tylko po to, aby nazwa SHA pasowała.

## Gdy coś nie działa

Uruchom status, zapisz tożsamość oraz objaw. Pending/drift oznacza administracyjne uzgodnienie, nie kolejne kliknięcie deploy. Rollback przywraca jeden poprzedni obraz, nie dane ani gałąź. Stop dotyczy jednego slotu i nie usuwa danych. Pełne procedury: rozdziały 14, 21-22.

## Zasada końcowa

Nie utożsamiaj: issue zamknięte, PR scalony, obraz zbudowany, kod uruchomiony, wynik zaakceptowany. Każdy etap ma osobny dowód.

