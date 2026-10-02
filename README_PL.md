# GitHub + Codex: wydania na portach

Referencyjny proces dla jednego prywatnego repozytorium, hosta Linux x86-64 i pojedynczej aplikacji HTTP w kontenerze. **Nie jest to gotowe wdrożenie dowolnej aplikacji.** Flagi gotowości są wyłączone, a testy aplikacji celowo wymagają konfiguracji.

## Zacznij tutaj

- [Pełny playbook po polsku](docs/PLAYBOOK_PL.md) -- 30 rozdziałów, procedury menedżera i administratora.
- [Pierwszy dzień i standardowe wydanie](docs/QUICKSTART_PL.md).
- [Raport wykonanych testów](TEST_REPORT_PL.md).
- [Szablon karty wydania](docs/RELEASE_CARD_TEMPLATE.md).

## Zawartość

`.github/workflows/port-release.yml` obsługuje ręczne status/deploy/promote/rollback/stop. Nazwa gałęzi `deploy/p4101` wskazuje port 4101, lecz tylko sloty z allowlisty są dopuszczone. Workflow wybierasz z main; SHA aplikacji podajesz osobno.

`ops/plan.py` sprawdza wejścia na runnerze GitHub-hosted. `ops/host/portctl.py` jest instalowany przez administratora poza checkoutem repozytorium. Na self-hosted runnerze nie wykonujemy skryptu kandydata, nie budujemy obrazu i nie pobieramy kodu przez checkout.

`ops/slots.json` i `ops/host/host.example.json` są konfiguracjami do dopasowania. Kontroler wymaga stanu na dysku, registry GHCR, prywatnych plików env i przygotowanej sieci. Port hosta jest konfigurowany przez slot; aplikacja słucha na 8080 wewnątrz kontenera.

`AGENTS.md` zawiera stałe zasady. `.agents/skills/github-port-releases/` zawiera skill dla agenta. Szablony issue/PR są w `.github/`. Pliki z końcówką `.example` trzeba przejrzeć, dopasować i dopiero aktywować.

## Uruchomienie testów pakietu

```bash
python3 -m unittest discover -s tests -v
```

To testy kontrolera z atrapami i demonstracji, nie Waszej aplikacji. `scripts/project-ci.sh` należy zastąpić rzeczywistymi testami projektu, nie `exit 0`.

## Granice bezpieczeństwa

Różne porty nie izolują cookies. Wspólny host nie daje niezależnej dostępności. Autor dowolnego workflow mogący uruchamiać powłokę na runnerze może ominąć kontrole tego skryptu. Ogranicz runner do zatwierdzonego workflow albo zastosuj osobną granicę administracyjną. Etykieta runnera nie jest ACL. Szczegóły: rozdziały 18 i 20 playbooka.

Nie wykonano wdrożenia na prawdziwym hoście, logowania GHCR ani testu GitHub Actions. Przed użyciem wymagane są adaptacja i odbiór z rozdziałów 24-26.

