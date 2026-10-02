# Przygotowanie wyszukiwarki GUS do portu 4103

Refs #2, PR #3. Żądanie właściciela: komentarz
https://github.com/Sebastian-Nowaczyk-Elektrorecykling/dot-test-seba/pull/3#issuecomment-5950827213.

## Stan: przygotowanie aplikacji, wdrożenie zablokowane

Dodano główny `Dockerfile` i allowlistę `.dockerignore`. Obraz uruchamia wyłącznie `gus_app` na `0.0.0.0:8080`, jako UID/GID 10001, bez instalacji dodatkowych zależności, zapisu bytecode, wolumenów i migracji. Port hosta 4103 ustala kontroler slotu, nie Dockerfile. `/healthz` i `/_meta` są już częścią aplikacji.

Baza: oficjalny `python:3.12-slim-bookworm`, manifest Linux/amd64 `sha256:9901e0a8d75037d8242ed43155cbcb2d1f61be1356383d8054afb59fd50e39c4`, odczytany z Docker Hub Registry 2026-10-02. Digest indeksu w chwili odczytu: `sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3`. Przypięcie zapewnia powtarzalną bazę, nie zastępuje przeglądu podatności i aktualizacji.

## Zweryfikowane przeszkody

Odczyt GitHub 2026-10-02:
- `main:ops/slots.json` nadal ma `repository=CHANGE_ME/CHANGE_ME`, `operators=[CHANGE_ME]` i `application_ready=false`. Slot `deploy/p4103` jest na allowliście.
- Wyszukanie gałęzi `deploy/p4103` nie zwróciło wyniku. PR #3 pozostaje draftem do `main`.
- Repo zawiera tylko przykładową konfigurację hosta: `configured=false`, URL loopback. Nie ustalono rzeczywistego hosta, adresu dostępu, bieżącej generacji ani stanu runtime. Nie odczytano stanu self-hosted runnera; nie można stwierdzić, czy istnieje.
- Walidator `ops/plan.py` odrzuci nawet `status` przy niedopasowanej nazwie repozytorium/operatora. Nie uruchamiano przewidywalnie odrzucanego workflow.

Nie zmieniono `ops/`, `.github/`, `AGENTS.md`, `.agents/`, ochrony gałęzi, sekretów ani konfiguracji hosta. Nie utworzono gałęzi slotu i nie scalono PR-a. Nie ma dowodu wystawienia usługi na porcie 4103.

## Kolejność i odpowiedzialność

1. Właściciel/administrator wskazuje rzeczywisty host Linux/amd64 i sposób prywatnego dostępu odbiorcy. Nie przesyła haseł ani tokenów w komentarzu.
2. Administrator przygotowuje i odbiera kontroler, runner z rzeczywistym ograniczeniem dostępu, GHCR, sieć i prywatną konfigurację slotu według rozdziałów 20, 24–25 `PLAYBOOK_PL.md`. Zmiany dostępu, tokenów i sieci wymagają osobnej zgody; samo żądanie wystawienia aplikacji ich nie autoryzuje.
3. Oceniany PR infrastrukturalny dostosowuje repozytorium/operatorów. `application_ready=true` dopiero po rzeczywistej budowie, testach kontraktu i odbiorze infrastruktury; administrator odrębnie zatwierdza `configured` na hoście. Nie używać flag jako obejścia.
4. Właściciel zatwierdza/scalając ustala zawartość aplikacji i slotu przez właściwe PR-y. Inicjalizację chronionej gałęzi `deploy/p4103` wykonuje administrator według playbooka. Brak automatycznego merge/pusha na gałąź slotu.
5. Operator uruchamia `port-release.yml` z **main**, najpierw `operation=status`, `slot_branch=deploy/p4103`. Zatrzymuje się przy pending, drift lub nieznanym stanie.
6. Właściciel potwierdza `deploy` dla pełnego 40-znakowego HEAD **gałęzi slotu** oraz świeżej generacji. SHA gałęzi aplikacji nie zastępuje SHA celu. Inputs: `target_sha`, `expected_generation`, `confirm=deploy/p4103`, `reason` z decyzją/kartą wydania. Nie zmieniać automatycznie SHA ani generacji po odmowie.
7. Po wykonaniu sprawdzić Actions, runtime `observed`, digest, `deployment_id`, `/_meta` i adres widoczny dla odbiorcy. Sam zielony CI nie potwierdza wdrożenia ani odbioru biznesowego.

## Weryfikacja

`bash scripts/project-ci.sh` zawiera dodatkowe statyczne testy deklaracji kontenera; dotychczasowe testy HTTP sprawdzają health i dokładne identyfikatory z env.

W środowisku przygotowującym zmianę nie ma polecenia Docker. **Budowa obrazu, start jako UID 10001 z read-only filesystem, test sieci z kontenera, publikacja GHCR i test prawdziwego portu 4103 nie zostały wykonane.** Statyczne testy Dockerfile nie dowodzą, że obraz się zbuduje. Właściwy build/test obrazu należy wykonać na zatwierdzonym środowisku, nigdy z kodu PR-a na hoście wdrożeniowym.

Nie ma bazy danych, migracji ani sekretów aplikacji; zapytania przekazywane są do publicznego API GUS. Dostęp odbiorców i limity ruchu wymagają odbioru infrastruktury. Różne porty nie są granicą bezpieczeństwa.
