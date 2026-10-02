# Kontrakt slotów i operacji

Odczytaj aktualny rejestr `ops/slots.json`; poniższe numery są przykładem, nie automatycznym przydziałem.

| Gałąź | Port | Typowa rola |
| --- | --- | --- |
| deploy/p4101 | 4101 | demo |
| deploy/p4102 | 4102 | akceptacja |
| deploy/p4103 | 4103 | pilot |

Wymagaj dokładnej nazwy i zgodności portu w konfiguracji. Stosuj workflow `port-release.yml` z main. Wariant referencyjny uruchamia wszystko ręcznie; push nie wdraża.

| Operacja | Wejścia poza operation i slot_branch |
| --- | --- |
| status | Brak mutacji, pozostałe pola zbędne. |
| deploy | target_sha, expected_generation, confirm=slot_branch, reason. |
| promote | Jak deploy oraz promote_from i source_deployment_id. |
| rollback | expected_generation, confirm=slot_branch, reason; previous pochodzi z rejestru. |
| stop | expected_generation, confirm=slot_branch, reason. |

Nie wpisuj `latest`, skróconego SHA ani samego numeru PR jako target_sha. Pełny SHA musi nadal być HEAD celu w chwili operacji.

Promocja wymaga tego samego Git tree, niekoniecznie tego samego commit SHA. Obraz zachowuje oryginalny build_sha. Konfiguracja i dane celu nie są kopiowane ze źródła.

Status: odczytaj active/previous, generation, pending_transaction, observed. RUNNING jest wynikiem technicznym; biznesowy odbiór dopisz do karty wydania z konkretnym deployment_id. W publicznym raporcie nie umieszczaj runtime_fingerprint, sekretów lub danych osobowych.

Wymagaj chronionych gałęzi oraz rzeczywistej kontroli dostępu do runnera. Sprawdzenia w skrypcie nie chronią przed innym workflow z dowolną powłoką na tym hoście. Gdy żądanie zmienia model bezpieczeństwa, przygotuj oceniany PR, nie doraźne obejście.

