# GitHub + Codex: wydania na jednym hoście, pod różnymi portami
## Playbook operacyjny dla menedżera i agenta

**Wersja 1.0 | 2 października 2026 | Model referencyjny: GitHub.com, Linux, Docker, jeden serwis HTTP na slot.**

**Decyzja architektoniczna:** port należy do stałej gałęzi slotu, np. `deploy/p4101`. Zadania powstają na osobnych, krótkotrwałych gałęziach. Scalenie PR-a aktualizuje planowany kod; dopiero jawne uruchomienie workflow zmienia działającą aplikację.

To jest propozycja zasad dla Waszego projektu, nie opis standardu wymaganego przez GitHub. Nazwy, numery portów i role slotów są przykładowe. Zachowanie platform opisane jako fakt opiera się na oficjalnych źródłach [S1-S19]. Szczegóły dostępności funkcji zależą od planu GitHub.

**Granica gotowości:** dołączono referencyjny workflow, kontroler hosta, testy, demonstracyjny serwis i instrukcje agenta. Nie skonfigurowano Waszego repozytorium ani serwera. Nie znamy stosu aplikacji, modelu danych ani wymagań dostępu. Domyślna konfiguracja celowo blokuje wdrożenia do czasu adaptacji; testy Waszej aplikacji trzeba dopisać. Szczegóły w rozdziałach 24-26.

### Jak korzystać z dokumentu

Menedżer zaczyna od rozdziałów 1-6, następnie wykonuje scenariusz z rozdziałów 7-13. Przy awarii przechodzi do rozdziałów 14 i 21. Administrator uruchamiający mechanizm czyta dodatkowo rozdziały 17-20 oraz 24-26. Agent otrzymuje `AGENTS.md` i skill, a nie polecenie zapamiętania całego podręcznika.

### Spis treści

1. Najkrótsza instrukcja i warunki startu
2. Model: zadanie, kod, artefakt, slot i akceptacja
3. Nazwy gałęzi, portów, PR-ów i wydań
4. Role, uprawnienia i granice autonomii agenta
5. Konfiguracja GitHuba i zabezpieczenia
6. Tablica pracy, issue i karta wydania
7. Zlecenie zadania Codexowi
8. Przegląd i scalenie zmiany
9. Przygotowanie gałęzi slotu
10. Ręczne wdrożenie w Actions
11. Promocja tego samego artefaktu
12. Testowanie i akceptacja biznesowa
13. Równoległe wersje i eksperymenty
14. Rollback i zatrzymanie slotu
15. Hotfix bez przypadkowego wydania innych funkcji
16. Zmiana wymagań i usunięcie funkcji
17. Dane, migracje i integracje zewnętrzne
18. Ten sam host i inne porty: pułapki
19. Jak działa dostarczony workflow
20. Bezpieczeństwo self-hosted runnera
21. Katalog nietypowych i awaryjnych operacji
22. Diagnostyka komunikatów i stanów
23. Codzienna i okresowa kontrola
24. Instalacja przez administratora
25. Kontrakt aplikacji i test odbioru infrastruktury
26. Zakres testów dostarczonego pakietu
27. Skill, AGENTS.md i gotowe polecenia
28. Przejście do docelowego środowiska
29. Listy kontrolne i definicja zakończenia
30. Źródła

# 1. Najkrótsza instrukcja i warunki startu

## 1.1. Zasada, którą trzeba zapamiętać

**Issue opisuje zamiar. PR opisuje proponowaną zmianę. Gałąź slotu opisuje wybraną zawartość. Digest identyfikuje obraz. Status hosta pokazuje, co rzeczywiście działa.**

Nie traktuj tych obiektów jako zamienników. Zielony wynik testów nie oznacza wdrożenia. Scalenie do `deploy/p4101` nie oznacza, że port 4101 już serwuje nową wersję. Zamknięcie issue nie zatrzymuje procesu. Rollback działającego obrazu nie cofa danych ani nie przesuwa gałęzi.

## 1.2. Standardowy przebieg

1. Utwórz issue z celem i sprawdzalnym wynikiem. Zleć Codexowi zmianę na `feat/123-krotki-opis`.
2. Obejrzyj PR, wyniki testów i instrukcję odbioru. Scal do `main` po spełnieniu kryteriów.
3. Przygotuj PR z zatwierdzonym zestawem zmian do `deploy/p4101`. Sprawdź cały zakres, nie tylko ostatnie zadanie.
4. W Actions uruchom `status` dla p4101. Odczytaj numer `generation`. Skopiuj pełny SHA aktualnego końca gałęzi slotu.
5. Uruchom `deploy` z tym SHA, generacją i potwierdzeniem `deploy/p4101`. Workflow uruchamiaj **z `main`**.
6. Sprawdź wynik operacji, `/_meta` i scenariusze biznesowe. Zapisz wynik w karcie wydania. Dopiero potem udostępnij adres odbiorcom lub promuj obraz na kolejny slot.

## 1.3. Minimum pozwalające zacząć teraz

Zacznij od **jednego slotu p4101, danych demonstracyjnych i dostępu prywatnego**. p4102 i p4103 są gotowymi rezerwacjami; nie musisz ich od razu uruchamiać. Nazwa `pilot` nie zamienia tymczasowego serwera w bezpieczną produkcję.

Przed pierwszym uruchomieniem musi istnieć osoba techniczna odpowiedzialna za runner, host, firewall, dane i odtworzenie usługi. Menedżer może samodzielnie podejmować decyzje produktowe i uruchamiać zatwierdzony proces. Nie powinien samodzielnie rozstrzygać, czy nieznana migracja SQL jest odwracalna albo czy publiczny port jest bezpieczny.

Wymagane minimum: zidentyfikowane repozytorium; konto operatora; prywatna ścieżka dostępu do aplikacji; zatwierdzony zakres portów; oddzielne dane testowe; działające testy aplikacji; sprawdzony rollback; brak niekontrolowanych zadań i prawdziwych płatności.

**Nie uruchamiaj** tego wzorca jako publicznego serwera wykonującego dowolny kod z PR-ów osób trzecich. GitHub ostrzega, że self-hosted runner może zostać trwale przejęty przez niezaufany kod [S4].

# 2. Model: zadanie, kod, artefakt, slot i akceptacja

## 2.1. Słownik roboczy

| Pojęcie | Znaczenie w tym procesie |
| --- | --- |
| Issue | Opis problemu, wymagania albo decyzji. Może prowadzić do wielu PR-ów. |
| Branch / gałąź | Nazwany, przesuwający się wskaźnik historii kodu. Nie jest środowiskiem sam w sobie. |
| Commit / SHA | Konkretny zapis kodu i historii. W tym adapterze używamy pełnego 40-znakowego SHA. |
| Git tree | Zawartość plików danego commita. Różne commity mogą mieć ten sam tree. |
| PR | Propozycja połączenia zmian z gałęzi źródłowej do docelowej. |
| Build / budowa | Wytworzenie obrazu aplikacji z konkretnego kodu i zależności. |
| Obraz i digest | Gotowy artefakt; digest `sha256:...` identyfikuje jego zawartość. |
| Slot | Zarejestrowane miejsce uruchomienia: host, port, konfiguracja i dane. |
| Deployment | Konkretna operacja uruchomienia obrazu w slocie. |
| Generation | Rosnący licznik operacji zmieniających stan slotu. Chroni przed starym poleceniem. |
| Rollback | Uruchomienie wcześniejszego obrazu; bez automatycznego cofania bazy. |
| Akceptacja | Potwierdzenie przez człowieka, że wersja spełnia potrzeby biznesowe. |

Digest należy odróżnić od tagu obrazu, takiego jak `latest`. Registry pozwala pobierać obraz po konkretnym digest, co ogranicza ryzyko przypadkowej podmiany wersji pod stałą nazwą [S8].

## 2.2. Cztery niezależne identyfikatory

W karcie operacji występują:

- `controller_sha`: wersja instrukcji wdrożeniowych na `main`, z których uruchomiono workflow.
- `target_sha`: commit zaakceptowany na gałęzi docelowego slotu.
- `build_sha`: commit, z którego zbudowano obraz.
- `deployment_id`: konkretne uruchomienie obrazu, np. `gh-123456-1-p4101-g7`.

Przy zwykłym `deploy` target i build SHA są równe. Przy `promote` mogą być różne: scalenie na drugą gałąź tworzy nowy commit, ale nie musi zmienić plików. Kontroler wymaga wtedy równego `tree_sha` i przenosi **ten sam digest obrazu**, bez ponownej budowy.

To kontrola ściślejsza niż stwierdzenie „ta sama funkcja”: porównuje całe drzewo repozytorium. Sama różnica dokumentacji może zablokować promocję. Nie wyłączaj tego warunku ad hoc; albo uzgodnij zawartość, albo wykonaj nowe `deploy` i testy.

## 2.3. Źródła prawdy

Wymagania i decyzje zapisuj w issue. Kod sprawdzaj w repozytorium. Zawartość planowaną odczytuj z gałęzi slotu. Informację o działającej wersji weryfikuj przez wynik `status`, metadane aplikacji i rejestr deploymentów. Informację o akceptacji zapisuj w komentarzu menedżera odnoszącym się do konkretnego deployment ID.

Gdy te źródła się nie zgadzają, nie wybieraj najwygodniejszego. Oznacz rozbieżność i wyjaśnij ją. Host mógł zostać zmieniony ręcznie, workflow mógł przerwać pracę, a przeglądarka może pokazywać zapisany wcześniej interfejs.

# 3. Nazwy gałęzi, portów, PR-ów i wydań

## 3.1. Dozwolone rodziny nazw

| Rodzaj | Przykład | Przeznaczenie |
| --- | --- | --- |
| Główna integracja | `main` | Zatwierdzony wspólny kod. Nie wdraża się automatycznie. |
| Funkcja | `feat/123-eksport-klientow` | Praca nad funkcją z issue #123. |
| Poprawka | `fix/147-daty-w-eksporcie` | Naprawa potwierdzonego problemu. |
| Eksperyment | `exp/156-nowy-formularz` | Zmiana, która może zostać odrzucona. |
| Dokumentacja | `docs/160-instrukcja` | Dokumentacja bez prawa zmiany hosta. |
| Infrastruktura | `ops/170-kontrola-portow` | Workflow, runner, polityki; wymaga przeglądu technicznego. |
| Zestaw wydania | `release/2026-10-02-r1` | Krótkotrwałe złożenie kilku zmian do PR-a. |
| Pilna poprawka | `hotfix/181-logowanie` | Minimalna poprawka wyprowadzona z aktywnej wersji. |
| Stały slot | `deploy/p4101` | Docelowa zawartość dla portu 4101. |

W nazwach stosuj małe litery ASCII, cyfry i myślniki. Bez spacji, polskich znaków, danych klienta, adresów e-mail i sekretów. Numer issue zapewnia powiązanie z celem. Gdy narzędzie tworzy prefiks `codex/`, możesz zachować `codex/feat/123-eksport-klientow`; to nadal gałąź pracy, nigdy automatyczny cel wdrożenia.

## 3.2. Port wyłącznie w nazwie stałego slotu

Przyjmujemy dokładny format `deploy/p<port>`, bez opisowego sufiksu. Parser akceptuje wyłącznie nazwy z zatwierdzonej listy. `deploy/p4101-demo`, `deploy/p04101`, `Deploy/p4101` i `feat/123-port4101` nie są celami wdrożenia. Port nie jest pobierany z tytułu PR-a, etykiety ani dowolnej liczby znalezionej w nazwie.

Docelowe porty 4101-4103 trzeba najpierw zarezerwować na rzeczywistym hoście. Nie są gwarantowanie wolne. Ten sam fizyczny port nie może należeć do dwóch niezależnych mechanizmów wdrożeniowych. Rejestr wszystkich aplikacji na hoście prowadzi administrator.

Nazwa zawiera adresowanie, a rola jest w rejestrze: p4101 = demo, p4102 = odbiór, p4103 = pilotaż. Zmiana roli slotu nie wymaga zmiany nazwy gałęzi. Gałęzi slotu nie usuwaj automatycznie po scaleniu.

## 3.3. Dlaczego nie `feat/123-p4101`

Takie nazewnictwo łączy dwa niezależne zagadnienia: pracę nad zmianą i wykorzystanie portu. Dwie funkcje mogą potrzebować tego samego demo. Jedna funkcja może wymagać kilku poprawek i kilku portów. Zamknięta gałąź nie powinna przypadkiem usuwać czyjegoś środowiska odbioru. Stały slot rozwiązuje te niejednoznaczności.

## 3.4. Tytuły i identyfikatory wydań

Tytuł PR-a: `feat: eksport klientow do CSV (#123)` albo `release: demo 2026-10-02-r1 -> p4101`. Opis PR-a ma być po polsku i wyjaśniać skutek dla użytkownika. Nie wymuszamy angielskich opisów tylko dlatego, że GitHub ma angielskie przyciski.

Uzgodnione wydanie biznesowe może mieć tag `v0.3.0` lub identyfikator `2026-10-02-r1`. Nie umieszczaj portu w identyfikatorze produktu: ten sam artefakt ma nadawać się na kilka slotów. Tag utwórz na **build SHA**, a w opisie wydania podaj digest. Nie przesuwaj opublikowanego tagu na inny commit; nadaj nowy identyfikator. Samo utworzenie tagu nie uruchamia dostarczonego workflow.

# 4. Role, uprawnienia i granice autonomii agenta

## 4.1. Podział odpowiedzialności

| Czynność | Menedżer | Agent | Administrator / reviewer techniczny |
| --- | --- | --- | --- |
| Cel, priorytet, kryteria odbioru | Decyduje | Pomaga doprecyzować | Konsultuje ryzyka |
| Kod i testy na gałęzi roboczej | Zleca | Wykonuje | Recenzuje, gdy potrzebne |
| Zakres wydania i wybór slotu | Zatwierdza | Pokazuje skutki | Sprawdza zależności |
| Scalenie do chronionej gałęzi | Osobna decyzja | Domyślnie tylko przygotowuje | Weryfikuje zmiany infrastruktury |
| Deploy, promote, rollback, stop | Osobna jawna decyzja | Bez samodzielnego wykonania | Utrzymuje mechanizm |
| Firewall, runner, sekrety, migracje | Akceptuje ryzyko biznesowe | Przygotowuje propozycję | Zatwierdza i wdraża technicznie |
| Akceptacja biznesowa | Wykonuje lub deleguje | Nie akceptuje własnej pracy | Nie zastępuje odbiorcy |

Agent nie uzyskuje zgody na wdrożenie tylko dlatego, że dostał zadanie „zrób funkcję”. Domyślny wynik jego pracy to gałąź, PR, testy i raport. W tym playbooku menedżer sam uruchamia mutujące operacje w Actions. Wyjątkowo można jawnie upoważnić agenta do jednej konkretnej operacji, zapisując jej cel, SHA, generację i ryzyko w karcie wydania. Nie wynika to automatycznie ze zlecenia kodowania; przy stałej delegacji trzeba osobno określić uprawnienia i kontrolę.

## 4.2. Jedna osoba nie tworzy rozdzielenia obowiązków

Gdy agent i menedżer działają tym samym kontem lub tokenem, GitHub nie rozpoznaje, kto faktycznie podjął decyzję. Instrukcja agenta jest pomocna, ale nie jest granicą uprawnień. Przy realnych klientach lub danych potrzebne są oddzielne role, reviewer infrastruktury i odpowiednie ograniczenia runnera.

Nie przyznawaj agentowi `admin`, prawa zmiany rulesetów, sekretów i rejestracji runnerów jako skrótu do „odblokowania pracy”. Zmiana zasad kontroli nie jest zwykłą poprawką aplikacji.

# 5. Konfiguracja GitHuba i zabezpieczenia

## 5.1. Ustawienia na początek

Administrator ustawia `main` jako domyślną gałąź. Tworzy chronione gałęzie `deploy/p4101`, `deploy/p4102`, `deploy/p4103` z zatwierdzonego punktu startowego. Na pierwsze dni wystarczy p4101; pozostałe można zostawić nieuruchomione.

Dla `main` oraz `deploy/**` wymagaj PR-a i zielonych kontroli `policy` oraz `application`. Nazwy wymaganych kontroli wybierz po ich pierwszym rzeczywistym uruchomieniu. Wyłącz force push i usuwanie chronionych gałęzi. Ogranicz obejścia reguł; reguła, którą wszyscy stale omijają, nie daje oczekiwanej ochrony [S2].

Przy większym zespole wymagaj przeglądu osoby innej niż autor i ponownego zatwierdzenia po nowych commitach. Dla jednoosobowej pracy demonstracyjnej nie ustawiaj wymogu niezależnego review, którego nie ma kto spełnić. To jawnie słabszy wariant: menedżer robi odbiór, a zmiany infrastruktury nadal konsultuje z osobą techniczną.

## 5.2. Metody scalania

Proponujemy **Squash and merge do `main`**: jedno typowe zadanie daje jeden wygodny do wskazania commit. Do długowiecznych gałęzi `deploy/p...` używaj **Create a merge commit**: zachowuje historię powiązań między kolejnymi promocjami. Nie wymagaj na tych gałęziach historii liniowej, bo byłoby to sprzeczne z merge commitami.

GitHub pozwala skonfigurować dostępne metody scalania na poziomie repozytorium [S13]. To nie znaczy, że samo ustawienie przypilnuje naszej zasady „squash tylko do main”. Menedżer sprawdza metodę przy przycisku; agent wpisuje ją do karty PR-a. Automatyczne wymuszenie per rodzaj gałęzi można dodać później.

Nie włączaj auto-merge dla PR-ów do slotów na starcie. Automatyczne usuwanie gałęzi można stosować do zakończonych gałęzi roboczych, po sprawdzeniu, że chronione gałęzie slotów są wyłączone z tego procesu [S14].

## 5.3. Pliki szczególnej kontroli

`.github/workflows/`, `ops/`, `scripts/project-ci.sh`, `AGENTS.md`, `.agents/`, pliki zależności, Dockerfile i migracje powinny mieć podwyższony poziom review. Wzór `CODEOWNERS.example` należy uzupełnić prawdziwym kontem lub zespołem i dopiero wtedy nazwać `CODEOWNERS`. Sam plik bez odpowiedniej reguły wymagania review nie stanowi pełnego zabezpieczenia [S2, S4].

Workflow przypina użytą akcję checkout do pełnego SHA. Aktualizacje przygotowuje Dependabot; również one przechodzą review. Nie zastępuj SHA przypadkowym forkiem akcji znalezionym w komentarzu [S4].

## 5.4. Ograniczenia planu i bramki zatwierdzania

Dostarczony wariant bazowy używa ręcznego `workflow_dispatch` i listy operatorów. Nie zakłada dostępności płatnej bramki reviewers. W szczególności prywatne repozytorium w Pro lub Team nie gwarantuje dostępności wymaganych reviewerów dla environment; sprawdź plan przed projektowaniem tego zabezpieczenia [S3].

Jeżeli bramka jest dostępna, administrator może dodać do zadania `operate` environment o nazwie `approval-p4101` albo analogicznej. Ogranicza ją do kontrolującego `main`. To osobne środowisko **zgody**, nie dowód uruchomienia kodu z main. Właściwy rekord deployment dla `p4101` tworzy kontroler, wskazując `target_sha` i digest.

Environment approval nie zamienia współdzielonego runnera w izolowaną maszynę. Jeszcze ważniejsze jest ograniczenie, **które workflow w ogóle mogą dostać dostęp do runnera**; opis w rozdziale 20 [S4-S5].

# 6. Tablica pracy, issue i karta wydania

## 6.1. Tablica menedżera

W GitHub Projects albo prostym rejestrze issue utrzymuj etapy: `Do doprecyzowania`, `Gotowe do pracy`, `W toku`, `Do przegladu`, `Zintegrowane`, `W odbiorze`, `Zakonczone` oraz `Wstrzymane`. Nie musisz od razu automatyzować wszystkich przejść.

Dodatkowe pola: właściciel, priorytet, ryzyko, zależności, wymagane sloty, link do PR-a i link do karty wydania. Status slotu nie jest statusem zadania. Jedno zadanie może być zaakceptowane na demo, a nadal niewydane na pilotażu.

## 6.2. Minimalna treść issue

Opisz: kto ma problem; jaki wynik ma otrzymać; czego nie zmieniamy; 3-7 konkretnych kroków sprawdzenia; przykładowe dane bez informacji wrażliwych; wymagane integracje; ryzyko migracji lub utraty danych. Jeżeli wymaganie zmienia się w dyskusji, dopisz decyzję z datą i aktualizuj kryteria. Nie pozostawiaj sprzecznych warunków rozsianych po komentarzach.

Domyślnie w PR-ach używaj `Refs #123`, a nie `Closes #123`. Chcemy zamykać wymaganie po odbiorze, nie jedynie po integracji kodu. GitHub ma własne reguły automatycznego zamykania powiązanych issue, szczególnie dla gałęzi domyślnej [S15]. Alternatywą jest osobne issue implementacji zamykane automatycznie i osobna karta odbioru.

## 6.3. Karta wydania poza gałęzią aplikacji

Utwórz issue typu wydanie: `Wydanie 2026-10-02-r1`. Wpisz listę funkcji i napraw, znane ograniczenia, wykluczone zadania, kolejność slotów, scenariusze odbioru, plan danych i decyzję o rollbacku. Po operacji dopisz target SHA, build SHA, digest, deployment ID, generation, konfigurację i wynik.

**Nie dopisuj różnych plików karty wydania do każdej gałęzi slotu.** Zmienisz tree i zablokujesz promocję tego samego obrazu. Decyzje o konkretnym uruchomieniu są w issue, metadanych deployment i stanie hosta. W repozytorium pozostaje wspólny szablon oraz opis procesu.

# 7. Zlecenie zadania Codexowi

## 7.1. Polecenie startowe

Użyj jednoznacznego polecenia, np.:

> Pracuj w repozytorium OWNER/REPO. Przeczytaj AGENTS.md i użyj skillu github-port-releases. Zrealizuj issue #123 na nowej gałęzi feat/123-eksport-klientow utworzonej z aktualnego origin/main. Najpierw sprawdź aktualne kryteria i zależności. Przygotuj PR do main, wyniki testów i instrukcję odbioru po polsku. Nie scalaj, nie wdrażaj i nie zmieniaj konfiguracji slotów.

Dołącz konkretny cel i ograniczenia zamiast instrukcji „zrób, żeby było dobrze”. W szczególności określ, czy funkcja może zmienić format danych, uprawnienia, integracje lub zależności. Agent powinien wskazać niepewności przed kosztowną zmianą.

## 7.2. Co agent ustala przed edycją

Agent potwierdza repozytorium, domyślną gałąź, bieżący branch, niezapisane zmiany, aktualny stan issue i otwarte powiązane PR-y. Nie tworzy kolejnej implementacji tylko dlatego, że nie zauważył gotowego PR-a. Nie nadpisuje pracy w nieczystym katalogu.

W pracy lokalnej Codex może używać osobnego worktree dla każdego zadania. W innym interfejsie agenta odpowiednikiem jest oddzielna przestrzeń zadania. Nie zakładamy, że każdy interfejs ma identyczne menu. Ważny jest rezultat: dwa zadania nie modyfikują tej samej gałęzi i tego samego katalogu bez koordynacji.

Agent nie podłącza produkcyjnej bazy ani nie pobiera sekretów z hosta do testów. Gdy brakuje narzędzia lub uprawnień, opisuje ograniczenie. Nie twierdzi, że utworzył PR, uruchomił testy albo wdrożył aplikację, jeśli ma tylko gotowy kod lub plan.

## 7.3. Wymagany rezultat zadania

W raporcie ma być: co zmieniono dla użytkownika; link do PR-a; gałąź i commit; wykonane testy i ich wynik; niewykonane testy; zależności; wpływ na dane; instrukcja sprawdzenia; ryzyka; operacje wymagające osobnej zgody. Sam komunikat „gotowe” nie wystarcza.

# 8. Przegląd i scalenie zmiany

## 8.1. Odbiór PR-a przez menedżera

Otwórz PR i sprawdź pole **base**. Dla zwykłej funkcji ma to być `main`, a nie przypadkowo `deploy/p4103`. Przeczytaj opis zmiany i listę plików. Nie musisz rozumieć każdej linii, ale musisz zauważyć, że przy zadaniu „kolor przycisku” zmieniono także workflow, autoryzację albo migracje.

W zakładce **Checks** sprawdź, czy testy zakończyły się sukcesem, a nie zostały pominięte. Poproś agenta o wskazanie konkretnego testu, który potwierdza wymaganie. Dla zmiany interfejsu obejrzyj zrzut lub demonstrację, ale nie traktuj obrazu jako dowodu, że działa zapis i autoryzacja.

Przeczytaj komentarze review i pytania bez odpowiedzi. Zweryfikuj przypadek negatywny: pusty plik, nieprawidłowe dane, brak uprawnień lub ponowienie operacji. Jeżeli zakres się rozrósł, podziel zadanie albo jawnie zatwierdź szerszy zakres w issue.

## 8.2. Scalenie nie jest wdrożeniem

Po spełnieniu warunków wybierz **Squash and merge** do `main`. Zapisz link do wynikowego commita. Przy squash jest on innym identyfikatorem niż ostatni commit na gałęzi agenta [S13]. Używaj commita rzeczywiście znajdującego się na gałęzi docelowej.

Oznacz zadanie jako `Zintegrowane`. To nadal nie oznacza `Zakonczone`, jeżeli wymagany jest odbiór wdrożenia. Gałąź roboczą można usunąć po upewnieniu się, że nic od niej nie zależy. Pozostają issue, PR i historia integracji.

## 8.3. Zmiana po przeglądzie

Nowe commity do PR-a mogą zmienić to, co zostało sprawdzone. Powtórz wymagane kontrole. Dla przyjętej wersji nie akceptuj argumentu „to tylko mała poprawka” bez ustalenia nowego SHA. Wydanie oparte na ruchomej gałęzi bez przypiętej rewizji nie daje powtarzalnego punktu odniesienia.

# 9. Przygotowanie gałęzi slotu

## 9.1. Zwykłe wydanie skumulowane

Po zintegrowaniu wybranych zadań menedżer zleca agentowi utworzenie `release/2026-10-02-r1` z konkretnego SHA na `main` i otwarcie PR-a do `deploy/p4101`. Gałąź wydania zamraża kandydaturę; nie jest gałęzią portu i nie uruchamia wdrożenia.

Agent porównuje **całą wynikową zawartość** z obecną gałęzią slotu i z aktywnym deploymentem. Pokazuje funkcje dodawane, zmieniane i wycofywane oraz wszystkie migracje. Jeżeli ostatnie wdrożenie było rollbackiem, gałąź slotu może być dalej niż aktywna aplikacja; trzeba to pokazać osobno.

Scal PR przez **Create a merge commit**. Dopiero commit powstały na `deploy/p4101` jest `target_sha` do operacji `deploy`. W Actions nie podawaj SHA z main ani SHA sprzed scalenia tylko dlatego, że dotyczył tej samej funkcji.

## 9.2. Sam merge nie zastępuje zawartości gałęzi

Jeżeli slot ma własne poprawki albo reverts, scalenie `main` może je zachować zamiast zastąpić. Agent ma sprawdzić wynikowe drzewo plików. Nie wolno obiecać „teraz jest identycznie jak main” na podstawie samego faktu merge.

Gdy celem jest dokładne wyrównanie plików do określonego commita, agent przygotowuje jawną zmianę odtwarzającą tę zawartość na gałęzi roboczej, z listą usuwanych różnic. Przechodzi ona PR i testy. Nie rozwiązujemy tego force pushem na `deploy/p...`.

## 9.3. Selektywny zestaw zmian

Domyślnie wydawaj kolejne zatwierdzone stany main. Jeżeli trzeba wybrać tylko część zmian, przygotuj osobny zestaw wydania z bazy odpowiadającej docelowemu slotowi. Agent analizuje zależności, a nie wybiera PR-ów wyłącznie po tytułach. Wybranie A bez B może wymagać adaptacji kodu, schematu bazy i testów.

W karcie zapisz pierwotne PR-y, commity przeniesione do zestawu oraz różnice względem main. Selektywny zestaw jest nową kombinacją, którą należy przetestować. Nie dziedziczy automatycznie akceptacji poszczególnych składników.

# 10. Ręczne wdrożenie w Actions

## 10.1. Odczyt stanu

Wejdź do repozytorium, następnie **Actions -> Port release (manual) -> Run workflow**. W selektorze gałęzi workflow wybierz **main**. W polu `operation` wybierz `status`, w `slot_branch` wybierz `deploy/p4101`. Pozostałe pola pozostaw puste lub z domyślnym `none`.

Po zakończeniu otwórz podsumowanie. Odczytaj `generation`, `observed`, `active` i `pending_transaction`. Gdy `pending_transaction` jest prawdą albo stan to `DRIFT_OR_ENGINE_UNAVAILABLE`, nie rozpoczynaj kolejnego wdrożenia. Zleć uzgodnienie stanu administratorowi.

Zielony wynik operacji `status` oznacza, że raport został pobrany. Sam raport może zawierać `UNHEALTHY`. Nie utożsamiaj koloru wykonania workflow ze zdrowiem aplikacji.

## 10.2. Formularz zwykłego deploy

| Pole | Co wpisać |
| --- | --- |
| Branch wyboru workflow | `main`, zawsze. To wersja mechanizmu sterującego. |
| `operation` | `deploy` |
| `slot_branch` | Np. `deploy/p4101`. Z tej nazwy wynika port. |
| `target_sha` | Pełny 40-znakowy SHA aktualnego końca tej gałęzi po scaleniu. |
| `expected_generation` | Licznik z przed chwilą pobranego statusu; `0` tylko dla pustego slotu. |
| `promote_from` | `none` |
| `source_deployment_id` | Puste. |
| `confirm` | Ponownie dokładnie `deploy/p4101`. |
| `reason` | Np. `Wydanie #200, odbior eksportu i poprawki dat`. Bez sekretów. |

Pełny SHA można skopiować ze strony commita wskazywanego przez koniec gałęzi. Agent może przygotować wartość oraz link, ale przed kliknięciem porównaj nazwę gałęzi i zakres wydania.

Mechanizm `workflow_dispatch` musi znajdować się na gałęzi domyślnej, aby dało się go uruchamiać standardowo. GitHub pozwala wybrać ref uruchomienia; dlatego nasz workflow dodatkowo odmawia operacji sterowanej z innej gałęzi niż main [S1].

## 10.3. Co zrobi workflow

Najpierw sprawdzi operatora, nazwę slotu, potwierdzenie i SHA. Na runnerze GitHub uruchomi testy aplikacji dla dokładnie tego SHA, następnie zbuduje obraz i opublikuje go w GHCR. Na hoście kontroler ponownie sprawdzi koniec gałęzi, generację slotu i obraz, a potem uruchomi nową wersję.

Zwykłe `deploy` buduje nowy artefakt. Ponowne zbudowanie tego samego commita może dać inny digest, np. przy nieprzypiętych zależnościach. Do przesunięcia już przetestowanego obrazu używaj `promote`, nie kolejnego builda.

Jeżeli ktoś zmieni gałąź w trakcie budowy, operacja odmówi użycia nieaktualnej kandydatury. Jeżeli ktoś w międzyczasie zmieni działający slot, odmówi z powodu nieaktualnej generacji. To ochrona przed nadpisaniem czyjejś decyzji, nie błąd wymagający obejścia.

## 10.4. Zapis po wdrożeniu

W karcie wydania wklej link do uruchomienia Actions, deployment ID, oba SHA, digest i nową generację. Wpisz `wdrozone technicznie, oczekuje na odbior`. Nie używaj jeszcze `zaakceptowane`.

Adres podany przez kontroler pochodzi z konfiguracji hosta. W przykładzie jest to localhost, czyli adres dostępny na serwerze. Administrator musi zorganizować dostęp przez VPN albo tunel i podać użytkownikowi właściwy adres. Nie naprawiaj braku dostępu, otwierając port na cały Internet.

# 11. Promocja tego samego artefaktu

## 11.1. Kiedy użyć promote

Po odbiorze demo chcesz uruchomić dokładnie ten sam obraz na p4102, ale z konfiguracją i danymi p4102. To jest promocja. Nie kompilujesz ponownie kodu i nie kopiujesz bazy danych z demo.

Najpierw przygotuj i scal PR do `deploy/p4102`, którego wynikowa zawartość plików odpowiada testowanemu obrazowi. Agent ma potwierdzić równość tree. Następnie pobierz `status` p4101 i p4102.

W formularzu wybierz `promote`; destination = `deploy/p4102`; `target_sha` = aktualny HEAD p4102; `expected_generation` = generacja p4102; `promote_from` = `deploy/p4101`; `source_deployment_id` = aktywne ID z p4101; `confirm` = `deploy/p4102`; podaj decyzję w `reason`.

Kontroler blokuje oba sloty na czas odczytu i operacji, sprawdza, czy źródło nadal ma wskazane ID i jest zdrowe, porównuje drzewa, a następnie pobiera dokładnie ten sam digest. Nowy deployment otrzymuje własne ID i generację na p4102. Stan p4101 nie zmienia się.

## 11.2. Co promocja potwierdza, a czego nie

Potwierdza tożsamość artefaktu. Nie potwierdza zgodności obu baz danych, konfiguracji OAuth, kont pocztowych, flag funkcji i danych odbiorców. Na nowym slocie wykonaj jego testy integracyjne i odbiorcze.

Jeżeli p4101 zmieni się po testach, stare ID nie przejdzie kontroli. Nie wpisuj bez zastanowienia nowego ID: dotyczy ono potencjalnie nieodebranej wersji. Albo odbierz nową wersję, albo przywróć w kontrolowany sposób wcześniejszy obraz i dopiero wtedy promuj.

## 11.3. Ograniczenie wzorca

Promocja w tej implementacji działa pomiędzy slotami zarządzanymi przez ten sam kontroler hosta. Nie jest gotowym mechanizmem promocji między wieloma serwerami. Do przyszłej migracji zachowujemy identyfikację digestem i rejestr decyzji; sposób transportu oraz blokowania będzie trzeba rozszerzyć.

# 12. Testowanie i akceptacja biznesowa

Testuj konkretny deployment ID, nie ogólnie „wersję na demo”. Przed testem sprawdź `/_meta`, adres i rolę użytkownika. Po zmianie portu sprawdź, czy nie korzystasz z nieprawidłowej sesji. Gdy dane lub interfejs wyglądają na stare, zbadaj cache i service worker; sam refresh nie zawsze wyjaśnia problem.

Wykonaj kryteria z issue, scenariusz podstawowy, przypadki błędne, kontrolę uprawnień i przynajmniej jeden proces niezwiązany ze zmienianą funkcją. Przy eksportach sprawdź faktyczny plik i zawartość, a nie tylko pojawienie się przycisku. Przy formularzu sprawdź odczyt danych po ponownym wejściu.

W karcie wpisz wynik każdego istotnego scenariusza oraz autora odbioru. Użyj formuły: „Akceptuję deployment X na p4102 w zakresie zadań #123 i #147. Znane ograniczenie: Y. Nie obejmuje pilotażu ani migracji danych”. To ogranicza przypadkowe rozszerzanie zgody.

Gdy pojawia się problem, zapisz issue z adresem, portem, deployment ID, godziną UTC, krokami, oczekiwanym i obserwowanym wynikiem. Nie wklejaj tokenów z adresu ani danych klientów. Podaj, czy problem występuje również na innym slocie; różnica jest wskazówką, nie automatycznym dowodem winy ostatniego PR-a.

# 13. Równoległe wersje i eksperymenty

## 13.1. Przykładowy stan trzech slotów

**Poniższy scenariusz jest fikcyjny i służy objaśnieniu proponowanego procesu.**

| Slot | Działająca wersja | Priorytet | Następna decyzja |
| --- | --- | --- | --- |
| p4101 demo | Nowy formularz + eksport + eksperyment walidacji | Szybka informacja zwrotna | Odrzucić lub zaakceptować eksperyment |
| p4102 odbiór | Eksport bez eksperymentu | Powtarzalny odbiór | Nie zmieniać podczas testu klienta |
| p4103 pilotaż | Poprzedni formularz + pilny hotfix logowania | Stabilność | Wydać tylko poprawkę krytyczną |

Nie ma tu jednego sensownego rankingu „najnowsza wersja”. p4103 może mieć ważniejszą poprawkę, a p4101 więcej nowych funkcji. Do oceny potrzebna jest macierz zawartości, konfiguracji i akceptacji, nie tylko numer PR-a.

## 13.2. Test zmiany przed przyjęciem do main

Możesz przetestować eksperyment na demo przed jego przyjęciem do main. Agent tworzy kontrolowany zestaw zawierający bazę i eksperyment, otwiera PR do p4101, a menedżer zatwierdza test i ręcznie wdraża. Pierwotny PR do main może pozostać otwarty.

W tym wzorcu nie istnieje specjalny magiczny status „test merged”. Jest konkretny merge do gałęzi slotu i konkretny deployment. Menedżer musi odróżnić „scalone do demo” od „przyjęte do wspólnego produktu”.

Nie promuj gałęzi eksperymentalnego demo do pilotażu tylko dlatego, że zawiera jedną potrzebną poprawkę. Przygotuj minimalny hotfix albo nowy czysty zestaw. Inaczej wydasz również eksperyment.

## 13.3. Zakończenie eksperymentu

Jeżeli eksperyment zostaje odrzucony, zamknij jego propozycję z uzasadnieniem. Usuń go z planowanej zawartości slotu przez PR i wdrożenie poprawionego zestawu, albo wykonaj runtime rollback i potem uzgodnij branch. Samo zamknięcie PR-a do main nie usunie eksperymentu z działającej aplikacji.

# 14. Rollback i zatrzymanie slotu

## 14.1. Pierwsza decyzja w incydencie

Ustal, czy problem dotyczy dostępności, błędnych wyników, danych czy podejrzenia naruszenia bezpieczeństwa. Przy ryzyku wycieku lub destrukcyjnych zapisów priorytetem może być zatrzymanie dostępu lub procesu, a nie uruchamianie starszego kodu. Przy migracji bazy decyzję o bezpiecznym rollbacku podejmuje osoba techniczna.

Wstrzymaj nowe operacje na dotkniętym slocie. Pobierz `status`, zapisz aktywne i poprzednie ID, generację, moment i objawy. Nie anuluj bezmyślnie workflow w trakcie zmiany procesów; rozdział 21 opisuje przerwane transakcje.

## 14.2. Ręczny rollback

Użyj `operation=rollback`, wybierz slot, wpisz jego bieżącą generację, powtórz nazwę w `confirm` i podaj incydent w `reason`. `target_sha` pozostaw puste. Kontroler wybiera zapisany **poprzedni obraz**, a nie dowolny tag ani starszy koniec gałęzi.

Rollback ponownie uruchamia poprzedni digest z tym samym wymaganym odciskiem konfiguracji i oznaczeniem epoki danych. Nie wykonuje builda. Nadaje nowe deployment ID i zwiększa generację. Sprawdź `/_meta`, objawy i kluczowe procesy biznesowe.

Wzorzec przechowuje jeden poprzedni aktywny rekord. Następny rollback może oznaczać powrót do wersji, którą właśnie wycofano. Dlatego każda operacja wymaga świeżego statusu; nie naciskaj wielokrotnie „ponów”.

## 14.3. Automatyczne przywrócenie po błędzie nowego kontenera

Jeżeli nowa wersja nie przejdzie kontroli `/healthz` i `/_meta`, kontroler próbuje uruchomić poprzedni zatrzymany kontener. Workflow pozostaje nieudany, nawet gdy poprzednia usługa znowu działa. To prawidłowy komunikat: próba nowego wdrożenia się nie powiodła.

To odzyskiwanie **procesu**, nie transakcja bazy danych. Nowy proces nie może samoczynnie uruchamiać migracji ani nieodwracalnych zadań startowych. W przeciwnym razie automatyczny powrót do starego procesu może być niebezpieczny.

Przerwanie zasilania, `SIGKILL`, awaria demona Docker albo brak miejsca na dysku może uniemożliwić ten powrót. Kontroler pozostawia dziennik `pending`; kolejne zmiany są blokowane do czasu uzgodnienia stanu przez administratora. Nie obiecujemy atomowego ani bezprzerwowego wdrożenia.

## 14.4. Gałąź po rollbacku

Rollback **nie przesuwa `deploy/p4101`**. Nadal może ona wskazywać wadliwy kod. Po opanowaniu incydentu przygotuj PR odwracający wadliwą zmianę albo poprawiający ją do przodu, a następnie nowy plan wydania. Nie uruchamiaj kolejnego deploy starego head tylko dlatego, że branch nazywa się „deploy”.

## 14.5. Stop i ponowne uruchomienie

`stop` zatrzymuje i usuwa zarządzany kontener wybranego slotu, zapisując poprzedni obraz w rejestrze. Nie usuwa branch, issue, obrazu w registry ani zewnętrznych danych. Wymaga generacji, potwierdzenia celu i przyczyny.

Po stop możesz użyć rollback, aby ponownie uruchomić ostatni zapisany obraz, jeżeli nadal zgodna jest konfiguracja i epoka danych. Nowe zwykłe wydanie wymaga `deploy`. Zatrzymanie usługi nie zwalnia automatycznie rezerwacji portu.

# 15. Hotfix bez przypadkowego wydania innych funkcji

Nie zaczynaj pilnej poprawki automatycznie od najnowszego main. Najpierw odczytaj aktywny rekord slotu i ustal, który kod rzeczywiście tam działa. W przypadku promocji build SHA i target SHA mogą się różnić, choć zawartość plików jest równa.

Agent tworzy `hotfix/181-logowanie` z uzgodnionej aktywnej wersji. Naprawia tylko przyczynę incydentu, dodaje test regresji i opisuje ryzyka. Otwiera PR do dotkniętego slotu oraz osobno przenosi poprawkę do main. Może to być ten sam commit albo adaptacja, ale powiązanie musi zostać zapisane.

Jeżeli gałąź slotu zawiera niewdrożony lub wycofany kod, PR hotfix nie może go przypadkiem ponownie wydać. Agent przygotowuje wynikową zawartość tak, aby była to aktywna wersja plus poprawka; menedżer sprawdza listę wszystkich zmian. To częsta przyczyna pozornie „małych” wydań z dużym zakresem.

Po scaleniu wykonaj deploy, sprawdź naprawę, odnotuj nowy digest i ustal, na które pozostałe sloty poprawka ma trafić. Incydent nie jest zakończony, jeśli hotfix istnieje tylko w jednej izolowanej wersji i zniknie przy następnym standardowym wydaniu.

# 16. Zmiana wymagań i usunięcie funkcji

Nowe informacje mogą uzasadniać zmianę lub usunięcie funkcji. Zapisz decyzję produktową: co przestało być potrzebne, jakie dane pozostają, kto korzysta z dotychczasowego zachowania i które sloty mają zachować starszą wersję.

Jeżeli wycofujesz cały izolowany PR, rozważ revert. Jeżeli część zmiany jest dobra albo inne funkcje już od niej zależą, przygotuj selektywną poprawkę lub nowe usunięcie funkcji. Nie wybieraj pełnego revert tylko dlatego, że jest przycisk [S10].

Sprawdź zależne raporty, eksporty, dane, uprawnienia, integracje i dokumentację. Nie kasuj bazy lub kolumny w tym samym kroku, w którym wyłączasz interfejs, jeżeli którykolwiek działający slot jeszcze ich potrzebuje. Zakres wycofania zapisuje się osobno od statusu pierwotnego PR-a.

Issue zamknięte jako „nieaktualne po usunięciu funkcji” nie oznacza naprawy zgłoszonego zachowania. Taki powód jest poprawny, o ile został jawnie zapisany. Nie mierz liczby napraw wyłącznie liczbą zamkniętych zgłoszeń.

# 17. Dane, migracje i integracje zewnętrzne

## 17.1. Porty nie rozdzielają danych

Dla każdego slotu utwórz osobne konto i bazę lub schemat, osobny prefiks plików, grupę konsumentów kolejki oraz konfigurację integracji. Konto demo nie może mieć uprawnień do danych pilota. Współdzielenie serwera bazy jest możliwe, ale wymaga rzeczywistego rozdzielenia uprawnień, nie tylko innej nazwy w interfejsie.

W tym pakiecie dane trwałe są poza kontenerem aplikacji i poza zarządzaniem kontrolera. Wbudowany adapter odrzuca obrazy deklarujące Docker VOLUME i nie montuje katalogów hosta. Aplikacja zapisująca pliki lokalnie, SQLite lub wymagająca zestawu usług potrzebuje osobnego, ocenionego adaptera. Nie usuwaj ograniczenia tylko po to, aby pierwszy deploy przeszedł.

## 17.2. Migracja jest osobną decyzją

Referencyjny workflow nie uruchamia migracji bazy. Nie ukrywaj nieodwracalnej migracji w starcie kontenera: zastąpienie procesu może nastąpić automatycznie podczas odtwarzania po błędzie. Przed migracją zapisz w karcie wydania wersję schematu, backup, próbę odtworzenia, zgodność ze starym obrazem i osobę odpowiedzialną.

Preferowany wzorzec organizacyjny: najpierw dodaj zgodną wstecz strukturę, następnie przełącz aplikacje, a dopiero po wycofaniu wszystkich starych wersji usuń nieużywane struktury. Nie oznacza to, że każda migracja może być bezpiecznie wykonana tą metodą. Administrator musi sprawdzić konkretny schemat i operacje.

`data_epoch` w konfiguracji hosta jest ręcznie zarządzanym znacznikiem zgodności danych. Zmień go, gdy stary obraz nie jest już bezpiecznym kandydatem do rollback. Kontroler porównuje znacznik; nie analizuje schematu i nie wykryje pominiętej aktualizacji. To blokada oparta na deklaracji administratora, a nie automatyczny dowód kompatybilności.

### Zmiana konfiguracji w oknie serwisowym

Referencyjny kontroler odrzuca deploy/promote do aktywnego slotu, gdy zmienił się odcisk konfiguracji, sekretów lub data_epoch. Zaplanuj: stop starej usługi, backup i zatwierdzoną zmianę konfiguracji/danych, następnie nowy deploy do pustego slotu i odbiór. Po takiej zmianie nie obiecuj automatycznego rollback do starej epoki. To celowo konserwatywne ograniczenie wersji referencyjnej.

Nie edytuj konfiguracji hosta ani danych równolegle do deployment. Kontroler nie jest transakcyjnym menedżerem bazy. Przy zmianie pliku env w trakcie podmiany zatrzyma automatyczne odtworzenie starego procesu i pozostawi stan do uzgodnienia, zamiast zakładać zgodność.

## 17.3. Funkcje działające bez kliknięcia użytkownika

Przed uruchomieniem drugiej kopii sprawdź harmonogramy, importy, subskrypcje kolejki, webhooki i płatności. Dwie instancje mogą wykonywać ten sam proces biznesowy dwa razy. Demo powinno mieć wyłączone wysyłki do realnych klientów oraz rozliczenia, nawet jeśli nikt nie otwiera strony.

Kopiowanie konfiguracji pilota do demo nie jest promocją. Promujemy obraz, a nie sekrety i dane. Tokeny, adresy callback, dozwolone pochodzenia CORS oraz klucze sesji należą do konkretnego slotu. Do demo używaj danych syntetycznych lub osobno zaakceptowanej anonimizacji.

# 18. Ten sam host i inne porty: pułapki

## 18.1. Cookies i logowanie

Cookies HTTP nie są izolowane numerem portu: standard wskazuje współdzielenie ich między portami tego samego hosta [S16]. Sesja na `host:4101` może więc kolidować z sesją na `host:4102`, jeśli aplikacje używają tych samych nazw i zakresów cookies.

Na czas przejściowy stosuj osobne nazwy cookies sesyjnych i CSRF, osobne klucze podpisu, osobne callback OAuth i jawne testy wylogowania. Różne nazwy ograniczają przypadkowe kolizje, ale nie są granicą bezpieczeństwa wobec złośliwej aplikacji na sąsiednim porcie. Nie umieszczaj nieufnego kodu obok wrażliwej aplikacji. Docelowo rozdziel hostnames i politykę cookies, a dla różnych poziomów zaufania także odpowiednie zasoby i uprawnienia.

## 18.2. Dostęp sieciowy i URL

Domyślny hostowy adapter wiąże port z `127.0.0.1`. Nie jest on wtedy adresem dostępnym bezpośrednio z komputera menedżera. Administrator przygotowuje tunel lub prywatny adres VPN oraz poprawny URL widoczny w rejestrze. Przestawienie na VPN wymaga zgodnego `bind_address`, `health_address` i adresu dla odbiorcy. Sposób publikowania portów ma znaczenie dla dostępu z sieci [S9].

Kontroler odrzuca `0.0.0.0`. To celowe zabezpieczenie przed przypadkowym wystawieniem wszystkich slotów publicznie, nie kompletny firewall. Administrator weryfikuje reguły sieci, wersję silnika Docker, uwierzytelnianie i TLS. HTTP z przykładu nadaje się do lokalnego testu przez kontrolowany kanał, nie do przesyłania haseł przez publiczny Internet.

Udany healthcheck z hosta nie dowodzi, że menedżer może wejść z VPN. Osobno testuj dostęp z docelowego komputera, przekierowania, linki generowane przez aplikację, callback logowania i brak mieszania ruchu między portami.

## 18.3. Wspólny limit awarii

Awaria hosta, pełny dysk, błąd administratora lub podatność jądra może objąć wszystkie sloty. Limity CPU, RAM, procesów i logów zmniejszają część ryzyka, lecz nie dają niezależnej dostępności. Kontenery są mechanizmem izolacji procesów o określonych ograniczeniach, a uprawnienia do silnika Docker wymagają szczególnego zaufania [S7].

Przykładowo trzy sloty po 512 MB nie oznaczają, że host z 1,5 GB RAM wystarczy: system, Docker, runner i usługi zewnętrzne także potrzebują zasobów. Administrator wyznacza budżet po pomiarach. Na tym hoście nie uruchamiamy kompilacji kodu aplikacji.

# 19. Jak działa dostarczony workflow

Plik `.github/workflows/port-release.yml` jest ręcznym kontrolerem procesu. Wszystkie uruchomienia wybierają workflow z `main`, a docelowa gałąź i SHA są wejściami. To zapobiega myleniu rewizji automatyzacji z rewizją aplikacji. Sam fakt istnienia workflow w repozytorium nie instaluje narzędzi na hoście [S1].

| Etap | Gdzie | Co robi |
| --- | --- | --- |
| Plan | Runner GitHub-hosted | Czyta zaufaną konfigurację z main, sprawdza operatora, nazwę slotu, potwierdzenie, generację i SHA. |
| Testy aplikacji | Osobny runner GitHub-hosted | Dla deploy pobiera dokładny target SHA i uruchamia `scripts/project-ci.sh`. |
| Budowa | Osobny runner GitHub-hosted | Dla deploy buduje obraz i publikuje go do GHCR. Zwraca digest, nie tylko tag. |
| Operacja | Self-hosted runner | Nie pobiera repozytorium. Uruchamia preinstalowany, kontrolowany przez administratora `portctl.py`. |
| Potwierdzenie | Host i GitHub | Weryfikuje health i tożsamość, zapisuje stan oraz rekord deployment dla kodu aplikacji. |

Promote, rollback, status i stop pomijają testy oraz nową budowę w tym przebiegu. Promote używa sprawdzonego aktywnego obrazu z innego slotu; rollback używa poprzedniego zapisanego obrazu. Obie operacje ponownie sprawdzają obraz i stan usługi, lecz nie stanowią nowego odbioru biznesowego.

## 19.1. Co faktycznie chroni przed pomyłką

Nazwę `deploy/p4101` kontroler rozkłada na port 4101, ale dodatkowo wymaga jej obecności w rejestrze i zgodności numeru w konfiguracji. Samo utworzenie dowolnej gałęzi z portem nie rezerwuje portu i nie daje dostępu do hosta.

`expected_generation` jest mechanizmem porównaj-i-zmień. Jeśli po twoim status inna operacja zmieniła stan, stara decyzja jest odrzucana. Generacja rośnie także po nieudanej podmianie z odtworzeniem starego procesu. Nie jest numerem wersji biznesowej i nie wolno jej zerować, aby obejść odmowę.

Blokada na hoście obejmuje fizyczny port. Promocja blokuje źródło i cel w ustalonej kolejności. Przed podmianą kontroler ponownie sprawdza HEAD gałęzi: długie oczekiwanie na runner lub pobranie obrazu nie uprawnia do wydania już nieaktualnego polecenia.

GitHub `concurrency` z `cancel-in-progress: false` nie jest trwałą kolejką wszystkich zamówionych wydań. W konfiguracji bazowej nowszy przebieg może zastąpić starszy oczekujący; to nie sygnał, że wdrożenie się odbyło. Dokumentacja opisuje również rozszerzoną koleję, ale ten pakiet nie polega na niej [S6]. Nie klikaj wielokrotnie: jedno polecenie, odczyt wyniku, nowa decyzja.

## 19.2. Co znaczy „podmiana”

Kontroler pobiera i weryfikuje obraz przed zatrzymaniem starego procesu. Następnie zapisuje dziennik transakcji, zatrzymuje stary kontener, uruchamia nowy na tym samym porcie, sprawdza health oraz `/_meta`, po czym atomowo zapisuje plik stanu. Jest krótka przerwa: to nie wdrożenie bez przestoju.

Awaria nowej aplikacji powoduje próbę przywrócenia poprzedniego procesu. Twarde przerwanie runnera lub zasilania może uniemożliwić odtworzenie. Plik `.pending.json` zostaje wtedy jako sygnał nierozliczonej operacji; kolejne mutacje są blokowane. Nie obiecujemy transakcyjności obejmującej GitHub, Docker i bazę danych.

## 19.3. Dwa rodzaje informacji o wdrożeniu

Workflow uruchomiony z main ma własny SHA. Nie wolno przedstawiać go jako kodu wdrożonej aplikacji. Dlatego host tworzy przez API osobny rekord deployment przypisany do `target_sha`, z digestem i `build_sha` w danych dodatkowych. Wyłącza automatyczne scalanie API; kontrole dopuszczenia wykonał wcześniej workflow [S18].

Opcjonalne GitHub Environment `approval-p4101` służy wyłącznie do dopuszczenia zadania. Faktyczny rekord działającej aplikacji jest przypisany do `p4101`. Nie mieszaj obu historii. Rekord przez API nie jest sam w sobie bramką zatwierdzającą wykonanie powłoki na runnerze.

Rejestr hosta i odczyt `/_meta` dają informację operacyjną. GitHub to widoczna kopia historii. Gdy zapis statusu GitHub nie powiedzie się po poprawnym wdrożeniu, zadanie zgłosi ostrzeżenie/błąd, ale nie wycofa zdrowej aplikacji tylko dla uzyskania zielonego znacznika.

# 20. Bezpieczeństwo self-hosted runnera

To obszar odpowiedzialności administratora. Self-hosted runner wykonuje polecenia workflow na twojej maszynie; kod uruchomiony w jobie może trwale wpłynąć na host [S4]. Nie jest to „po prostu serwer wykonujący YAML” bez dodatkowego ryzyka.

## 20.1. Minimalna granica zaufania

Nie kieruj testów otwartych PR-ów na host wdrożeniowy. Nie stosuj `pull_request_target` połączonego z pobraniem i wykonaniem nieufnego kodu. Buduj na GitHub-hosted runnerach, a na hoście uruchamiaj zatwierdzone obrazy ze stałego pakietu registry. Sekrety runtime pozostają na hoście, nie trafiają do kontekstu budowy.

Bardzo ważne: warunek `if`, sprawdzenie `GITHUB_REF`, lista operatorów w Pythonie i etykieta runnera nie są granicą ochrony przed osobą mogącą dodać inne zadanie z dowolnym skryptem na ten sam runner. Taki job może ominąć kontroler. Nie myl zabezpieczenia przed pomyłką z izolacją przed napastnikiem.

W miarę możliwości ogranicz grupę runnerów do dokładnego workflow `OWNER/REPO/.github/workflows/port-release.yml@refs/heads/main`, a nie całego repozytorium. Dostępność i konfigurację tych polityk administrator sprawdza w organizacji [S5].

Jeśli nie można wymusić takiego ograniczenia, mocniejszy wariant to osobne repozytorium operacyjne, do którego agent aplikacyjny nie ma prawa zapisu. Wymaga to adaptacji dostarczonych skryptów do osobnego repozytorium źródłowego i uwierzytelnienia. Pakiet bazowy tego wariantu nie implementuje. Bez tej izolacji traktuj wszystkich autorów workflow jako administratorów hosta i ogranicz start do zaufanego zespołu, syntetycznych danych i niewrażliwego demo.

## 20.2. Konfiguracja hosta

Uruchamiaj runner jako dedykowanego użytkownika, nie konto codzienne administratora. Kod kontrolera i konfiguracja polityki należą do administratora; dane runtime są prywatne. Dostęp do Docker nadal daje bardzo szerokie możliwości, więc konto w grupie docker nie jest niskouprzywilejowanym sandboxem [S7].

Nie montuj Docker socket do aplikacji, nie używaj `--privileged`, sieci hosta ani dowolnych mountów dostarczonych przez agenta. Ograniczenia w adapterze są stałe i nie wynikają z pliku Compose zmienianego przez kandydacki PR. Zatwierdzony obraz nadal może być złośliwy lub mieć podatność; zatwierdzenie i analiza aplikacji pozostają konieczne.

Token build ma `packages: write` tylko w swoim jobie. Job hosta ma krótkotrwały token do odczytu kodu i zapisania deployment, bez uprawnień do push. Osobne konto hosta ma minimalne uprawnienia odczytu prywatnego pakietu GHCR, skonfigurowane przez administratora [S8]. Nie przekazuj PAT-a do polecenia agenta, issue ani pliku env w repo.

Akcje zewnętrzne przypinamy do pełnego SHA i aktualizujemy przez oceniony PR. Dołączony checkout ma przypiętą, sprawdzoną rewizję v6.1.0 [S17]; to konkretna wersja referencyjna, nie deklaracja „zawsze najnowsza”. Włącz aktualizacje Dependabot i okresowy przegląd zależności.

# 21. Katalog nietypowych i awaryjnych operacji

Poniższe procedury są instrukcjami decyzyjnymi. Menedżer ustala cel i akceptuje ryzyko; operacje oznaczone jako administracyjne wykonuje osoba z odpowiednimi kompetencjami.

## 21.1. PR powstał do złej gałęzi

Przed merge zmień base w PR lub poproś agenta o odtworzenie gałęzi z poprawnej podstawy. Obejrzyj cały nowy diff i ponów testy. Zmiana base nie jest kosmetyką: może zmienić listę commitów i wynik integracji.

## 21.2. PR scalono do złego slotu

Nie cofaj historii force pushem. Zablokuj wydanie tego slotu, sprawdź, czy zmiana rzeczywiście została wdrożona. Przygotuj PR korygujący do złego celu i osobny do dobrego. Jeśli runtime już się zmienił, oddzielnie rozważ rollback.

## 21.3. PR zamknięto bez merge, ale jego funkcja nadal działa

Sprawdź rekord aktywnego artefaktu. Kod mógł zostać wcześniej włączony do gałęzi slotu innym PR-em albo jako selektywnie przeniesiony commit. Zamknięcie propozycji nie zatrzymuje kontenera. Usuń zachowanie z docelowego kodu przez zatwierdzony PR albo zmień wdrożenie.

## 21.4. Chcesz cofnąć tylko jedną część PR-a

Agent przygotowuje selektywną poprawkę i test zachowania, które ma zostać. Nie cofaj całego pliku ze starego commita bez porównania późniejszych zmian. Pełny revert, przywrócenie pliku i naprawa do przodu mają inne skutki [S10].

## 21.5. Chcesz przywrócić wcześniej wycofaną funkcję

Nie zakładaj, że ponowne merge tej samej gałęzi ją przywróci. Revert odwraca zawartość, ale historia pamięta pierwotne scalenie. Agent ocenia revert rewertu albo nową implementację na aktualnej podstawie, z testem zależności [S10].

## 21.6. Potrzebujesz tylko wybranych zmian z main

Utwórz kandydacką gałąź z uzgodnionej podstawy slotu. Agent może selektywnie przenieść commity, zapisując źródła i adaptacje. Sprawdź wymagane biblioteki, schematy i poprawki pomocnicze. Nowe SHA po przeniesieniu są normalne; nie są dowodem tożsamości artefaktu.

## 21.7. Promocja jest blokowana przez TREE_MISMATCH

Porównaj zawartość obu targetów, także dokumentację i workflow. Nie usuwaj porównania tree. Albo uzgodnij tę samą zawartość poprzez nowy PR i dopiero promuj, albo uznaj cel za inne wydanie i wykonaj deploy z nowym odbiorem.

## 21.8. Dwie osoby zleciły operacje na tym samym porcie

Jedna otrzyma wynik, druga może zobaczyć anulowany oczekujący job albo STALE_GENERATION. Nie kopiuj nowego numeru w ciemno. Odczytaj status, porównaj aktywne wydanie z własną intencją i złóż nowe polecenie tylko jeśli nadal jest potrzebne.

## 21.9. Workflow utknął w kolejce

Sprawdź dostępność runnera, jego etykiety, ograniczenia grupy oraz oczekujące zatwierdzenie. Nie wysyłaj kolejnych deploymentów jako „odświeżenie”. Po długiej przerwie odczytaj aktualny status i SHA: stara decyzja mogła stracić ważność.

## 21.10. Ktoś nacisnął Cancel lub host zgasł podczas podmiany

Uruchom tylko status. Jeśli jest pending albo drift, administrator porównuje dziennik, kontenery, image digest, plik aktywnego stanu i GitHub. Przywraca spójny stan lub kończy operację, zachowując kopie diagnostyczne i zwiększając generację. Nie kasuj pending, dopóki nie ustalono wyniku. Pakiet nie ma automatycznego polecenia „napraw wszystko”.

## 21.11. Obcy proces zajmuje port albo kontener ma nieznaną tożsamość

Nie uruchamiaj automatycznego kill procesu na podstawie numeru portu. Administrator ustala właściciela. Adapter ma odmawiać przejęcia nieznanego kontenera; konflikt bind podczas startu uruchamia ścieżkę błędu. Zajęty numer może należeć do innej usługi.

## 21.12. Potrzebny jest starszy obraz niż zapisany jako previous

Zwykły rollback obsługuje jeden poprzedni wpis. Starszy artefakt wymaga administracyjnego przywrócenia na podstawie historii, weryfikacji digesta, kompatybilności konfiguracji i danych oraz nowego rekordu. Nie dopisuj dowolnego digesta do inputs ani nie edytuj stanu ręcznie jako menedżer. To świadome ograniczenie powierzchni pomyłek.

## 21.13. Registry utraciło stary obraz

Nie da się obiecać rollback do nieistniejącego artefaktu. Ponowna budowa starego kodu może dać inny obraz, szczególnie przy nieprzypiętych zależnościach. Administrator ocenia lokalnie zachowaną kopię i retencję; nowa budowa to nowe wydanie, nie odtworzenie tożsamego artefaktu.

## 21.14. Zmieniono sekret, konfigurację albo schemat po poprzednim wydaniu

Kontroler blokuje automatyczny rollback, gdy odcisk runtime lub data_epoch nie pasuje. Nie przywracaj skompromitowanego sekretu, aby kontrola przeszła. Administrator planuje kompatybilny rollback/forward fix w aktualnej konfiguracji. Wycofanie aplikacji nie cofa automatycznie zewnętrznych skutków.

## 21.15. Usunięto gałąź deploy lub zmieniono jej nazwę

Runtime nadal może działać. Odczytaj jego rekord; administrator odtwarza referencję z uzgodnionego target SHA i przywraca ochronę. Port nie jest automatycznie zwalniany. Gałęzi `deploy/p4101` nie zmieniaj na `deploy/p4201` jako metody przeniesienia serwisu.

## 21.16. Przenosisz aplikację na inny port

Administrator rezerwuje nowy slot, aktualizuje allowlisty, inputs, sieć, env i polityki dostępu. Zatwierdzony obraz trafia na nowy cel, przechodzi testy URL/logowania/integracji, a odbiorcy dostają nowy adres. Dopiero potem stop starego slotu. Dane i callbacki wymagają osobnej decyzji.

## 21.17. Wycofujesz slot na stałe

Najpierw odłącz odbiorców i harmonogramy, potem stop, potem archiwizacja danych i historii, a na końcu usunięcie uprawnień i rezerwacji. Zachowaj zapis ostatniego obrazu i decyzji. Automatyczne usunięcie gałęzi po PR nie zastępuje tej procedury.

## 21.18. Sekret trafił do commita, logu lub rozmowy

Zatrzymaj dystrybucję, unieważnij/obróć sekret, sprawdź użycie i dopiero planuj oczyszczenie historii i logów. Revert pozostawia starą treść w historii. Specjalistyczne przepisywanie historii może być uzasadnione w incydencie, ale wymaga koordynacji, nie zwykłego force push agenta [S19].

## 21.19. Agent prosi o force push albo reset gałęzi wdrożeniowej

Domyślna odpowiedź brzmi: przygotuj korektę jako nowy PR. Porządkowanie lokalnej, nieopublikowanej gałęzi roboczej jest czymś innym niż usuwanie historii wspólnego slotu. Wyjątki zatwierdza administrator w konkretnym incydencie.

## 21.20. Revert merge ma konflikt albo nie wiadomo, który parent wybrać

Agent analizuje rodziców merge i wpływ późniejszych zmian. Nie wybiera automatycznie `ours`, `theirs` ani `-m 1` bez sprawdzenia celu. Menedżer ocenia rezultat funkcjonalny, nie proponuje numeru parent z pamięci. Testy obejmują funkcję usuwaną i funkcje mające pozostać [S10].

## 21.21. Dwa wydania uruchamiają ten sam cron lub wysyłają dwa maile

To incydent integracji, nie tylko błąd kodu. Zatrzymaj niepożądane wykonanie zgodnie z ustalonym zakresem, zachowaj dowody i przeanalizuj skutki. Nie kasuj już przetworzonych danych bez planu. Napraw konfigurację zadań oraz test izolacji przed ponownym startem.

## 21.22. Dysk pełny albo wszystkie sloty zwolniły

Administrator identyfikuje logi, obrazy, procesy i zasoby. Nie uruchamiaj ogólnego `docker system prune -a --volumes`: może usunąć elementy potrzebne innym usługom lub rollback. Retencja jest jawna: aktywne i poprzednie artefakty każdego slotu muszą zostać zachowane.

## 21.23. Po restarcie hosta aplikacja jest „zielona” tylko w starym Actions

Stary sukces dotyczy dawnej chwili. Wykonaj świeży status i test dostępu. Docker restart policy nie zastępuje monitoringu. Kontroler wykrywa część drift przez nazwę, etykiety, obraz i stan procesu; nie audytuje każdego ustawienia sieci i jądra.

## 21.24. Agent otworzył kilka zależnych PR-ów

Opisz kolejność i warunki scalenia. Po zmianie podstawy ponów przegląd wynikowej zawartości. Do wydania potrzebna jest sprawdzona kombinacja, nie suma indywidualnie zielonych ekranów. Nie kończ zadania produktu, gdy scalono wyłącznie warstwę pomocniczą.

## 21.25. Ten sam host ma obsłużywać drugie repozytorium

Nie kopiuj kontrolera z niezależnym katalogiem blokad i tą samą pulą portów. Administrator musi wprowadzić wspólny przydział portów i blokady zasobów. Ten pakiet zakłada jedną aplikację/repozytorium zarządzane przez jedną instalację kontrolera.

## 21.26. Chcesz uruchomić obraz zewnętrznego autora

Nie wklejaj dowolnego image digest do stanu. Najpierw włącz i oceń kod w zatwierdzonym procesie, zbuduj go przez zaufany workflow albo zaprojektuj osobny przepływ dostawcy. Etykiety OCI są metadanymi, nie podpisem kryptograficznym producenta. Bezpieczeństwo pochodzenia opiera się tu na zaufanym buildzie, registry i uprawnieniach do uruchomienia workflow.

# 22. Diagnostyka komunikatów i stanów

Najpierw sprawdź, czy odmowa nastąpiła przed dotknięciem runtime, czy w czasie podmiany. Wynik `status` może być technicznie udanym uruchomieniem joba, a jednocześnie zgłaszać niezdrową aplikację. Czytaj `observed`, `pending_transaction`, `active`, `previous` i `last_result`, nie tylko ikonę Actions.

| Sygnał | Znaczenie i następny krok |
| --- | --- |
| UNKNOWN_SLOT / INVALID_PORT | Nazwa nie należy do rejestru albo port nie pasuje. Nie obchodź kontroli; administrator sprawdza konfigurację. |
| TRUSTED_WORKFLOW_REQUIRED / PLAN_REFUSED | Niepoprawny workflow/ref, operator lub niegotowa konfiguracja. Wybierz main, następnie zweryfikuj ustawienia. |
| BRANCH_MOVED | HEAD celu zmienił się od zatwierdzenia. Przejrzyj nowy zakres; nie podmieniaj SHA bez decyzji. |
| STALE_GENERATION | Runtime został zmieniony przez inną operację. Odczytaj status i ponownie oceń zamiar. |
| TREE_MISMATCH | Promowany obraz ma inną zawartość niż gałąź celu. Uzgodnij kod lub potraktuj jako nowe wydanie. |
| PROMOTION_SOURCE_CHANGED | W slocie źródłowym nie działa już zaakceptowany deployment_id. Ponownie wskaż i zaakceptuj źródło. |
| NO_PREVIOUS_RELEASE | Brak wpisu do standardowego rollback. Potrzebny inny plan odtworzenia. |
| RUNTIME_CONFIG_CHANGED | Dla aktywnego slotu zmieniono konfigurację. Zaplanuj stop, zmianę serwisową i nowy deploy do pustego slotu. |
| CONFIG_OR_DATA_EPOCH_CHANGED | Automatyczny rollback nie potwierdza zgodności. Decyzja administratora, nie zmniejszanie znacznika. |
| DRIFT / UNMANAGED_CONTAINER | Rzeczywistość nie zgadza się z rejestrem. Bez kolejnego deploy; administrator uzgadnia stan. |
| FAILED_RESTORED | Nowy deploy się nie udał, poprzednia usługa została odtworzona. Zapisz incydent i nową generację. |
| FAILED_EMPTY | Pierwszy deploy nie powiódł się; slot wrócił do pustego stanu. To nie udane uruchomienie. |
| INCOMPLETE_TRANSACTION / RECOVERY_REQUIRED | Jest niedokończona podmiana. Tylko status i administracyjne uzgodnienie. |
| DEPLOYED_RECORDING_INCOMPLETE | Zdrowa aplikacja mogła już zostać zapisana jako aktywna; niepełny audyt wymaga naprawy. |
| observed: UNHEALTHY | Proces istnieje, ale nie przeszedł health/tożsamości. To nie pełna diagnoza przyczyny. |
| observed: DRIFT_OR_ENGINE_UNAVAILABLE | Kontener/rejestr się różni albo silnik nie odpowiada. Administrator odróżnia te przypadki. |
| warning po DEPLOYED | Runtime zmienił się, lecz status GitHub lub sprzątanie wymaga uwagi. Nie uruchamiaj kolejnej zmiany w ciemno. |

Brak tokena registry, problemy DNS i limit zasobów nie są automatycznie błędami aplikacji. Agent może pomóc zinterpretować oczyszczony log, ale nie powinien prosić o pełny plik sekretów. Kontroler celowo nie wypisuje surowych błędów silnika, które mogłyby zawierać wrażliwe dane.

# 23. Codzienna i okresowa kontrola

Przed pierwszym wydaniem danego dnia operator sprawdza status dotkniętych slotów, nierozliczone incydenty oraz to, czy ktoś nie oczekuje na odbiór konkretnego deployment_id. Działającego demo nie nadpisuje się tylko dlatego, że jest najnowszy main.

Po każdej zmianie zapisz kartę wydania, wynik smoke testu, URL i tożsamość runtime. Informuj odbiorców o utracie ważności starych wyników testów. Gdy zmienia się konfiguracja lub dane, nawet ten sam digest wymaga adekwatnego powtórzenia testów.

Co tydzień menedżer z administratorem przeglądają różnice między slotami i main, hotfixy nieprzeniesione do wspólnej linii, eksperymenty bez decyzji końcowej, ważność tokenów, obrazy do zachowania, zasoby hosta i aktualizacje zabezpieczeń. To proponowana kadencja, nie wymóg platformy.

Przed zmianą kontrolera, Docker, systemu lub modelu danych przeprowadź próbę odtworzenia na niewrażliwym slocie. Kontroler nie implementuje ciągłego monitoringu, alarmów dyżurowych ani okresowych backupów. Te obowiązki pozostają osobnym zadaniem operacyjnym.

# 24. Instalacja przez administratora

## 24.1. Decyzje przed instalacją

Ustal: prywatne repozytorium GitHub.com, pełne nazwy operatorów, pojedynczy host Linux x86-64, pulę portów, sposób dostępu VPN/tunel, ograniczenia runnera, budżet zasobów, registry, kontrakt aplikacji i właściciela danych. Ten zestaw nie jest automatycznym instalatorem GitHuba ani systemu operacyjnego.

Wybór Docker jest założeniem referencyjnym, bo stos aplikacji nie został podany. Jeśli macie już niezawodny mechanizm systemd lub inny hosting, zachowajcie model identyfikacji i politykę, a wymieńcie adapter po testach. Nie należy uruchamiać dostarczonego skryptu niezmienionego w nieobsługiwanym środowisku.

## 24.2. Pliki repozytorium

Przenieś pliki przez PR infrastrukturalny. Nie nadpisuj istniejących workflow, AGENTS.md i reguł CODEOWNERS bez połączenia zasad. W `ops/slots.json` ustaw repozytorium, listę operatorów i używane sloty. Zgodnie zmień listy choices w workflow oraz konfigurację hosta.

`application_ready` pozostaje false do czasu dopasowania Dockerfile, rzeczywistych testów w `scripts/project-ci.sh`, endpointów i odbioru infrastruktury. Skrypt testów aplikacji domyślnie kończy się błędem: to bezpieczne przypomnienie o brakującym kontrakcie, nie usterka do naprawienia przez wpisanie `exit 0`.

Skopiuj `.github/CODEOWNERS.example` do `.github/CODEOWNERS` po zastąpieniu przykładowego zespołu. Skonfiguruj rulesets z rozdziału 5. W prywatnym repo sprawdź uprawnienia GITHUB_TOKEN do GHCR i to, czy pakiet jest powiązany z repozytorium [S8].

## 24.3. Host i kontroler

Zainstaluj wspieraną wersję Docker Engine oraz Python 3.10+ i dedykowanego self-hosted runnera. Wymagany jest Linux, ponieważ kontroler używa blokad `fcntl`. Runner dostaje etykietę `port-deploy`; etykieta kieruje job, ale nie stanowi uprawnienia. Ograniczenie grupy i zaufanie do repo sprawdź osobno.

Poniższe polecenia to fragment konfiguracji dla administratora. Zakładają już istniejącego użytkownika runnera `ghdeploy`; jego utworzenie, runner i polityka Docker są zależne od hosta. Uruchamiaj z ocenionej kopii pakietu, nie z niezatwierdzonej gałęzi agenta.

```bash
sudo install -d -m 0755 /opt/port-releases
sudo install -m 0755 ops/host/portctl.py /opt/port-releases/portctl.py
sudo install -d -m 0750 -o root -g ghdeploy /etc/port-releases
sudo install -m 0640 -o root -g ghdeploy \
  ops/host/host.example.json /etc/port-releases/host.json
sudo install -d -m 0700 -o ghdeploy -g ghdeploy /srv/port-releases/state
```

Administrator edytuje host.json: prawdziwe repo, operatorzy, zatwierdzone porty, adresy, sieci, konfiguracje i epoki danych. `configured` pozostaje false do odbioru. Pliki env tworzy bezpiecznym kanałem, z właścicielem runnera i trybem 0600. Nie mogą być symlinkami; ich zawartości nie umieszcza w repo ani w logach.

Dla każdego używanego slotu administrator tworzy osobną sieć, np.:

```bash
sudo docker network create portapp-p4101
sudo docker network create portapp-p4102
sudo docker network create portapp-p4103
```

Domyślne sieci nie gwarantują zakazu wszelkiego ruchu do pozostałych adresów hosta lub Internetu. Wymagania egress/ingress wdraża administrator w warstwie sieciowej. Oddzielna nazwa sieci nie zastępuje kontroli dostępu do bazy.

Zaloguj dedykowanego użytkownika do GHCR z minimalnym tokenem odczytu przez `docker login --password-stdin`, korzystając z bezpiecznie dostarczonego sekretu. Nie dodawaj sekretu do argumentu komendy, przykładowego pliku lub historii powłoki. Uprawnienia do prywatnego pakietu muszą być potwierdzone próbnym pull [S8].

## 24.4. Uruchomienie kontrolowane

Najpierw włącz odczyt status na pustym p4101. Oczekiwany wynik: generation 0, active null, pending false i STOPPED_OR_EMPTY. Brak usługi jest wtedy prawidłowy, a nie awarią.

Do testu infrastruktury możesz użyć wyłącznie demonstracyjnej aplikacji z pakietu. W osobnym testowym repo kopiujesz `example-app/Dockerfile` do głównego `Dockerfile` i `example-app/project-ci.sh` do `scripts/project-ci.sh`; pozostawiasz folder example-app. To nie konfiguracja testów Waszego produktu.

Po odbiorze kontraktu aplikacji administrator zatwierdza `application_ready: true` w repo i `configured: true` na hoście. Zmiana pierwszej flagi jest PR-em. Zmiana drugiej należy do kontrolowanej konfiguracji hosta. Zapisz wersję oraz sumę pliku kontrolera; aktualizacja `ops/host/portctl.py` w repo nie podmienia automatycznie kopii `/opt/...`.

Utwórz pierwszą gałąź `deploy/p4101` z uzgodnionego commita main. Dla inicjalizacji trzeba bezpiecznie dopuścić utworzenie referencji w ruleset; po utworzeniu przywrócić komplet ochrony. Nie twórz osobnej gałęzi o nazwie `deploy`, która może kolidować ze strukturą referencji `deploy/...`.

Przeprowadź pierwszy deploy, drugi deploy i rollback na danych demonstracyjnych. Sprawdź dostęp menedżera z jego komputera. Dopiero potem dopuszczaj kolejne sloty i scenariusze biznesowe.

# 25. Kontrakt aplikacji i test odbioru infrastruktury

## 25.1. Kontrakt referencyjnego adaptera

| Element | Wymaganie |
| --- | --- |
| Platforma | Jeden obraz Linux/amd64, GitHub.com, Python 3.10+ na hoście. |
| Serwis | Jeden kontener, HTTP na 0.0.0.0:8080 wewnątrz kontenera. Port hosta określa slot. |
| Uruchomienie | UID/GID 10001, read-only root filesystem, zapis tymczasowy tylko /tmp. |
| Dane | Brak wbudowanych volumes; baza i trwałe pliki zarządzane zewnętrznie. |
| Health | GET /healthz zwraca 2xx dopiero po gotowości do obsługi. |
| Tożsamość | GET /_meta zwraca JSON z build_sha i deployment_id zgodnymi z env. |
| Skutki uboczne | Brak nieodwracalnych migracji i niekontrolowanych realnych wysyłek w starcie. |
| CI | scripts/project-ci.sh instaluje wymagane narzędzia bez sekretów i sprawdza faktyczne kryteria. |
| Budowa | Dockerfile w root, poprawny .dockerignore, przypięte zależności i ograniczony kontekst. |

Zmienne dostarczane przez host: `APP_GIT_SHA`, `DEPLOY_TARGET_SHA`, `DEPLOYMENT_ID`, `DEPLOY_SLOT`. Endpoint `/_meta` nie zwraca sekretów, surowego env ani odcisku konfiguracji. Przykładowy wynik (wartości skrócone wyłącznie na potrzeby prezentacji):

```json
{
  "build_sha": "pelny-40-znakowy-sha-w-rzeczywistym-wyniku",
  "deployment_id": "gh-123456-1-p4101-g7",
  "target_sha": "pelny-sha-galezi-docelowej",
  "slot": "p4101"
}
```

Submoduły, Git LFS, wiele kontenerów, prywatne zależności builda, architektura ARM, Windows i repo Git z innym formatem identyfikatorów wymagają adaptacji. Nie twierdzimy, że jedno YAML obsługuje każdy stos.

## 25.2. Lista testów na prawdziwym hoście

Te testy wykonuje administrator przed dopuszczeniem użytkowników. Nie zostały wykonane w ramach przygotowania pakietu.

1. Status pustego slotu jest prawidłowy; błędny operator, port i workflow/ref są odrzucane.
2. Poprawny obraz startuje, /_meta zgadza się z rejestrem, link działa z komputera odbiorcy.
3. Obraz z uszkodzonym health lub złym deployment_id nie zostaje zaakceptowany; poprzedni proces zostaje odtworzony.
4. Zmiana HEAD w trakcie oczekiwania oraz dwie operacje z tą samą generacją nie powodują cichego nadpisania.
5. Promocja przenosi dokładnie ten sam digest; inny tree oraz zmienione źródło są odrzucane.
6. Rollback przywraca poprzedni obraz bez budowy; zmiana konfiguracji/data_epoch blokuje go zgodnie z projektem.
7. Cancel/twarde przerwanie na testowym slocie zostawia rozpoznawalny stan; administrator potrafi go uzgodnić bez usuwania cudzych kontenerów.
8. Brak GHCR, niedostępny Docker i awaria zapisu statusu GitHub są rozróżnialne od błędu aplikacji.
9. Sloty nie współdzielą sesji przypadkiem, danych, prawdziwych kolejek, callbacków ani skutków wysyłki.
10. Reguły runnera rzeczywiście odrzucają nieuprawniony workflow. Testuj to tylko kontrolowanym, nieszkodliwym jobem.
11. Reboot hosta i zapełnienie kontrolowanego limitu logów nie gubią rejestru; jest backup stanu i przećwiczony plan odtworzenia.
12. Zmierz przestój i dopuszczalne obciążenie; zaakceptuj je jawnie przed pilotem.

# 26. Zakres testów dostarczonego pakietu

W trakcie przygotowania uruchomiono testy Python obejmujące walidację wejść i stanów kontrolera oraz lokalny serwer demonstracyjny. Wynik i liczba testów znajdują się w dołączonym `TEST_REPORT_PL.md`. Polecenie odtworzenia:

```bash
python3 -m unittest discover -s tests -v
```

Testy kontrolera podstawiają atrapę Docker i GitHub API. Sprawdzają m.in. konflikt generacji, odmowę nieznanego celu, promocję po równym tree, rollback, zmianę konfiguracji i nieudany health z odtworzeniem. Test endpointów uruchamia rzeczywisty lokalny serwer HTTP demonstracji.

Nie wykonano prawdziwego docker build/run, uruchomienia GitHub Actions w Waszej organizacji, logowania GHCR, testu firewall/TLS ani testów Waszej aplikacji. Sprawdzenie pliku YAML i testy z atrapami nie zastępują punktów z rozdziału 25. Paczka jest sprawdzoną referencją do adaptacji, nie odebranym środowiskiem produkcyjnym.

Rejestr operacyjny to prywatne pliki JSON/JSONL z blokadą i zapisem atomowym, nie odporny na administratora system audytu. Nie ma automatycznego zarządzania kopiami danych, klastra, dynamicznej rezerwacji portów, gwarancji zero downtime ani podpisów artefaktów. Zmiany tych założeń wymagają osobnego projektu.

# 27. Skill, AGENTS.md i gotowe polecenia

## 27.1. Dlaczego nie wystarczy wiedza modelu

Agent może znać standardowe operacje Git, lecz nie można zakładać, że zna Wasz przydział portów, granice autonomii, zasady promocji i procedury awaryjne. Nie ma podstaw, aby z domniemanych danych treningowych wyprowadzić znajomość tej polityki.

Dlatego krótkie, stale obowiązujące reguły znajdują się w `AGENTS.md`, a procedura wydania w `.agents/skills/github-port-releases/SKILL.md`. Codex obsługuje te mechanizmy konfiguracji; dokładna dostępność i instalacja zależy od klienta [S11, S12]. Dla innego klienta agenta zachowaj treść polityki, ale sprawdź jego metodę ładowania, zamiast zakładać identyczne zachowanie.

Nie powielamy w skillu podręcznika Git. Są tam niestandardowe nazwy, wymagane odczyty, rozdzielenie identyfikatorów, warunki zgody i format raportu. To instrukcje zachowania, nie granica uprawnień: agent z administracyjnym tokenem nadal ma administracyjne możliwości.

## 27.2. Instalacja i sprawdzenie

Połącz AGENTS.md z istnieącym plikiem projektu. Zainstaluj katalog skill w `.agents/skills/github-port-releases/`. Archiwum `skill.zip` zawiera ten sam pojedynczy skill do klientów obsługujących import. Nie kopiuj sekretów ani pełnego playbooka do stałego promptu.

W nowej sesji poproś agenta: „Przeczytaj AGENTS.md i github-port-releases. Wyjaśnij, jak wybierzesz port, ską pobierzesz aktualny stan i czego nie zrobisz bez zgody. Niczego nie zmieniaj”. Zweryfikuj odpowiedź; samo istnienie pliku nie potwierdza jego zastosowania.

## 27.3. Gotowe zlecenia

**Nowa funkcja:** „Zrealizuj issue #123 na osobnej gałęzi od main. Najpierw potwierdź zakres i kryteria. Dodaj testy i otwórz PR. Nie scalaj ani nie wdrażaj. W raporcie podaj faktycznie uruchomione testy i ryzyka.”

**Przygotowanie wydania:** „Przygotuj kandydaturę #181 dla deploy/p4101 z ustalonego main SHA. Porównaj ją z kodem aktualnie działającym na slocie i wypisz wszystkie zmiany, także te spoza mojego ostatniego zadania. Otwórz PR do slotu. Niczego nie scalaj.”

**Promocja:** „Przygotuj promocję zaakceptowanego deployment_id ze slotu p4101 do p4102. Sprawdź drzewo Git, generację celu, konfigurację i plan danych. Przygotuj dokładne wartości formularza; nie uruchamiaj go. Nie buduj nowego obrazu.”

**Podejrzenie awarii:** „Wykonaj wyłącznie odczyt statusu p4102 i analizę oczyszczonych logów. Ustal, czy aktywny obraz odpowiada karcie wydania. Zaproponuj rollback lub forward fix wraz z ryzykiem danych. Nie zatrzymuj procesu, nie edytuj stanu i nie obracaj sekretów bez osobnej zgody.”

**Usunięcie funkcji:** „Przygotuj plan wycofania funkcji X. Sprawdź wszystkie sloty, zależne funkcje i dane. Odróżnij usunięcie interfejsu od migracji danych. Zaproponuj PR-y i kryteria odbioru; zachowaj historię.”

# 28. Przejście do docelowego środowiska

Nie trzeba dziś wybierać nieznanej przyszłej platformy. Trzeba zachować obiekty, które ułatwią przejście: identyfikator artefaktu, logiczny slot, konfigurację poza obrazem, rekord deployment, decyzję i kryteria akceptacji.

Gdy pojawi się docelowy hosting, dodaj nowe logiczne cele, np. staging i production. Wymień mapowanie branch-slot-host oraz adapter wykonujący operację. Nie zakodowuj portów hosta w logice produktu. Nazwy `deploy/p4101` można zachować w historii, ale nie muszą stać się trwałą terminologią firmy.

Migracja obejmuje test obrazu na nowej platformie, dane, integracje, dostęp, konfigurację i plan powrotu. Ten sam digest upraszcza kontrolę pochodzenia; nie gwarantuje zgodnego zachowania w nowym otoczeniu. Przez okres przejściowy nowy i stary cel mogą współistnieć, ale należy wyraźnie wskazać właściciela realnych skutków biznesowych.

Po migracji zamknij tymczasowe sloty według procedury wycofania. Nie zostawiaj publicznego portu i starego tokena „na wszelki wypadek”. Zachowaj historyczne karty wydań jako powiązanie dawnego hosta z nową platformą.

# 29. Listy kontrolne i definicja zakończenia

## 29.1. Przed poleceniem zmiany runtime

- [ ] Znam docelowy slot, jego odbiorców i pełny zakres zmiany.
- [ ] Mam świeży status i generację, nie ma pending ani drift.
- [ ] Dla deploy/promote mam zatwierdzony target SHA; dla promocji również source deployment_id.
- [ ] Znam skutki dla danych i integracji; istnieje realny plan powrotu.
- [ ] Mam kartę wydania/incydentu oraz jednoznaczną zgodę na tę operację.

## 29.2. Po poleceniu

- [ ] Odczytałem wynik runtime, nie tylko zielony job.
- [ ] Digest, build SHA i deployment_id odpowiadają zatwierdzonej operacji.
- [ ] Zweryfikowałem URL z komputera odbiorcy i wykonałem smoke test.
- [ ] Zaktualizowałem kartę i powiadomiłem odbiorców.
- [ ] Gdy zadanie się nie udało, zapisałem, co faktycznie nadal działa.

## 29.3. Kiedy zadanie jest zakończone

„Kod scalony”, „artefakt zbudowany”, „uruchomiony na p4101” i „zaakceptowany przez odbiorcę na p4102” to osobne stany. Definition of Done dla issue wymienia wymagane cele i testy. Nie zamykamy produktu przez sam fakt zakończenia pracy agenta.

Dla poprawki awaryjnej dodatkowym warunkiem jest przeniesienie naprawy do uzgodnionej wspólnej linii albo jawna decyzja, dlaczego ma pozostać lokalna. Dla eksperymentu warunkiem jest decyzja: przyjąć, zmienić, odrzucić lub przedłużyć, wraz z terminem ponownej oceny.

Najważniejsze pytanie operacyjne brzmi: **jaki artefakt działa, w którym slocie, z jaką konfiguracją, na podstawie czyjej decyzji i jakim dowodem potwierdzono wynik?**

# 30. Źródła

Sprawdzono 2 października 2026. Dokumentacja produktów może się zmieniać. Reguły naszego procesu są propozycją projektową; źródła uzasadniają opisane mechanizmy i ograniczenia platform, a nie poświadczają gotowości tej implementacji.

- [S1: GitHub, ręczne uruchamianie workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [S2: GitHub, ochrona gałęzi](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [S3: GitHub, Environments i ograniczenia planów](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
- [S4: GitHub, bezpieczne użycie Actions](https://docs.github.com/en/actions/reference/security/secure-use)
- [S5: GitHub, polityki grup runnerów i selected workflows](https://docs.github.com/en/rest/actions/self-hosted-runner-groups)
- [S6: GitHub, współbieżność workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
- [S7: Docker, granice bezpieczeństwa silnika i kontenerów](https://docs.docker.com/engine/security/)
- [S8: GitHub, Container Registry i digest](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [S9: Docker, publikowanie portów](https://docs.docker.com/engine/network/port-publishing/)
- [S10: Git, git revert i konsekwencje rewertu merge](https://git-scm.com/docs/git-revert)
- [S11: OpenAI, agent skills](https://developers.openai.com/codex/skills/)
- [S12: OpenAI, instrukcje AGENTS.md](https://developers.openai.com/codex/guides/agents-md/)
- [S13: GitHub, metody scalania](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github)
- [S14: GitHub, automatyczne usuwanie gałęzi](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-the-automatic-deletion-of-branches)
- [S15: GitHub, linkowanie PR i automatyczne zamykanie issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)
- [S16: RFC 6265, cookies współdzielone pomiędzy portami](https://www.rfc-editor.org/rfc/rfc6265.html)
- [S17: actions/checkout, przypięty commit v6.1.0](https://github.com/actions/checkout/commit/d23441a48e516b6c34aea4fa41551a30e30af803)
- [S18a: GitHub REST API, deployments](https://docs.github.com/en/rest/deployments/deployments)
- [S18b: GitHub REST API, deployment statuses](https://docs.github.com/en/rest/deployments/statuses)
- [S19: GitHub, usuwanie wrażliwych danych z historii](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)

