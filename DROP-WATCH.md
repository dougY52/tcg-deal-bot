# Drop-Watch und Betriebsdiagnose

Stand: 24.10.2026. Der normale Deal-/Preorder-Watch bleibt aktiv. Zusätzlich kann derselbe Lauf öffentliche Händler-Ankündigungen und sichtbare Warteschlangen melden. Keine zusätzlichen Secrets, kein bezahlter Dienst.

## Tatsächlich festgestellte Störungen

* Externer Zeitgeber `cron-job.org`, Job `8473281`: deaktiviert. Der lokal gespeicherte GitHub-Dispatch-Token liefert **HTTP 401**. Die letzten acht GitHub-Starts waren ausschließlich `schedule`; am 24.10. lagen ungefähr 2–4,5 Stunden dazwischen. Ein erfolgreiches Scan-Ergebnis bestätigt keinen Fünf-Minuten-Takt.
* AdventureCardz, GemCards und Card Club schalten die konkrete Shopify-Varianten-ID erst durch JavaScript frei. Statisches HTML enthält ein deaktiviertes Feld im Kauf-Formular und ein anderes, aktives Feld im Ratenzahlungsformular. Diese Formulare dürfen nicht zusammengeführt werden. `browser_checkout: true` lädt bei diesen drei Shops die Produktseite in einem normalen, isolierten Browser. Erst das aktivierte Formular für genau die ID zählt. Kein Warenkorb wird verändert.
* FantasiaCards verwendet „In den Einkaufswagen legen“. Dieses Label wird jetzt erkannt. Externe Buttons mit explizitem `form="..."` werden nur dem eindeutig passenden Formular zugeordnet.
* FB03- und Naruto-Konoha-Shido-2nd-Edition-Preisreferenzen waren abgelaufen. Beide wurden am 24.10. anhand direkter Bestellvalidierung bei Card Collector (85 EUR) bzw. Animeboy (69,90 EUR) erneut bestätigt, ohne die Preisgrenze anzuheben. Andere abgelaufene Referenzen bleiben gesperrt und stehen jetzt im Bericht.
* Der State-Abruf lud mehrere Minuten lang die Historie des `bot-state`-Branches. Er lädt jetzt nur den jüngsten Commit; der bestehende State und die Versandhistorie bleiben erhalten.

## Zusätzlicher Signal-Kanal innerhalb des Bots

`tcg_bot/drop_watch.py` läuft vor den Produktprüfungen, mit maximal 18 Sekunden und fünf Quellseiten je Scan. Pokémon Center Deutschland (`https://www.pokemoncenter.com/en-de`) hat Vorrang und ist bei jedem Lauf nach mindestens fünf Minuten fällig. Die Startseiten aktivierter, vertrauenswürdiger deutscher Händler rotieren dahinter. Sie werden frühestens nach 30 Minuten erneut gelesen; die tatsächliche Zeit hängt von Anzahl und Laufhäufigkeit ab. **Nicht jeder Händler wird alle fünf Minuten auf Ankündigungen geprüft.** Weitere konkrete offizielle Ankündigungsseiten können unter `drop_watch.sources` ergänzt werden.

Zwei klar getrennte Nachrichtentypen:

* **WARTESCHLANGE SICHTBAR:** Die tatsächlich geladene Seite enthält eine passende Hauptüberschrift und operative Warteinformationen. Ein eingebundenes Queue-Script, eine FAQ oder ein einzelnes Wort „Waitlist“ genügt nicht. Die Meldung bestätigt ausdrücklich keinen Drop, Bestand, Preis oder Kaufzugang. Bei einer allgemeinen Händlerwarteschlange ist die Kartensprache noch unbekannt.
* **DROP ANGEKÜNDIGT:** Ein kurzer öffentlicher Händlertext nennt eines der vier TCGs, ein sealed Produkt, einen ausdrücklichen Verkaufs-/Vorbestellstart sowie Datum und Uhrzeit. Nur kommende sieben Tage bzw. höchstens fünf Minuten zurückliegende Starts; Europe/Berlin. Pokémon muss ausdrücklich DE, Dragon Ball/One Piece EN, Naruto DE/EN sein. Ein reines Erscheinungsdatum oder eine undatierte „Coming soon“-Seite genügt nicht. Eine Warteliste wird dadurch niemals zum bestellbaren Preorder-Angebot.

Die neue Erkennung ist absichtlich textbasiert und begrenzt: bildbasierte Instagram-Posts, private Discords, Logins, Captchas, unklare Datumsangaben und unbekannte Backend-Daten werden nicht ausgewertet. Hersteller können einen Drop unangekündigt starten. Eine Queue allein ist laut [Pokémon Center](https://support.pokemoncenter.com/hc/en-us/articles/37286495522452-Pok%C3%A9mon-Center-Virtual-Queue) kein Beweis für einen Produktstart.

Pokémon Center Deutschland lieferte am 24.10. beim direkten Abruf **HTTP 200 mit Incapsula-Schutzseite**. Der Bericht zeigt `blocked_or_unreadable`, nicht „keine Queue“ oder „verfügbar“. Seine robots.txt sperrt unter anderem `/availabilities`, `/cortex`, `/prices` und `/carts`. Diese Endpunkte werden nicht abgefragt. Das Hinzufügen der Quelle bedeutet deshalb derzeit **keine bestätigte aktive Pokémon-Center-Drop-Abdeckung**.

## State und Versand

`drop_watch_sources` wird im vorhandenen `state.json` / Branch `bot-state` gespeichert. Ankündigungen werden pro Quelle, TCG und Startzeit einmal gesendet; Änderungen an Countdown oder Fließtext erzeugen keine Wiederholung. Eine Queue wird einmal je Öffnungsphase gemeldet. Erst zwei lesbare normale Seiten schließen die Phase; Fehler/Schutzseiten tun das nicht. Discord muss eine Message-ID bestätigen, bevor `delivered` gesetzt wird. Ein fehlgeschlagener Versand bleibt erneut zustellbar. Dry-runs schreiben weder Produktions-State noch Discord.

Die bisherigen Preis-, Sprach-, Händler-, Varianten- und Deal-Dublettenregeln gelten weiterhin. Ein Queue-/Ankündigungssignal ist ausdrücklich kein qualifizierter Retail-Deal. Quellenfehler bleiben im Scanbericht und erzeugen keine leeren Discord-Statusposts.

## Zeitgeber wiederherstellen

1. Bei GitHub den bestehenden eingeschränkten Token für `dougY52/tcg-deal-bot` erneuern: nur dieses Repository, **Actions: Read and write**, mit bewusst gewählter Gültigkeit. Nicht in Chats posten.
2. Im vorhandenen cron-job.org-Job `8473281` den Header `Authorization: Bearer …` ersetzen, Job aktivieren, fünf Minuten und POST-Body `{"ref":"main","inputs":{"dry_run":false}}` beibehalten. Ziel: `https://api.github.com/repos/dougY52/tcg-deal-bot/actions/workflows/cloud-watch.yml/dispatches`.
3. Testlauf muss HTTP **204** ergeben; anschließend in GitHub mindestens zwei tatsächliche `workflow_dispatch`-Starts mit dem erwarteten Abstand und erfolgreiche Scans prüfen. Der Browser muss danach nicht geöffnet bleiben.

GitHub-Schedule bleibt ein zusätzlicher Auslöser. Starts bei Codeänderungen auf `main` prüfen eine neue Version sofort. Der State verhindert eng aufeinanderfolgende Doppel-Scans. Diese Mechanismen ersetzen keinen funktionierenden externen Zeitgeber.

## Prüfung

`python -m unittest discover -s tests -q` und `python -m tcg_bot --check-config`.
Live-Browser benötigt die bereits vorhandene `requirements-browser.txt` sowie `python -m playwright install --with-deps chromium`. Der Cloud-Workflow installiert sie jetzt für die konfigurierten Checkout-Prüfungen mit aktivierter Browser-Anbindung (`TCG_BROWSER=1`).

Neue Tests prüfen unter anderem externe Formularzuordnung, falsche/deaktivierte Varianten, „Einkaufswagen“, Browserfehler, Queue-Dedupe/Wiederöffnung, Sendefehler, abgelaufene/falschsprachige Ankündigungen und Schutzseiten. Kein Test sendet einen erfundenen Deal an Discord.


## Browser-Abdeckung – geprüft am 25.10.2026 (Europe/Berlin)

Der Cloud Watch aktiviert den normalen Chromium-Browser für Müller, MediaMarkt/Saturn und die öffentliche Pokémon-Center-DE-Seite. Parallele Händlerprüfungen behalten jetzt diesen Transport; jeder Worker schließt seinen eigenen Browser. Zeitbudgets, robots.txt, Crawl-Abstände und Backoff bleiben aktiv. Es gibt keine Proxies, Stealth-Fingerprints, Login-Übernahme oder Warenkorb-Klicks.

* **Müller:** Kataloge auf Linux- und Windows-GitHub-Runnern erreichbar. Die beobachteten Folgeseiten werden pro Katalog persistent rotiert; Zubehör wird vor Detailabfragen aussortiert. Mehrere responsive Warenkorbbuttons derselben bestätigten Produkt-ID gelten als dieselbe Kaufoption. Sprache, aktueller Preis, Verkäufer, echte Verfügbarkeit und Lieferung nach Hause müssen weiterhin passen. Filialbestände ohne gewählte Filiale bleiben unbestätigt.
* **MediaMarkt/Saturn:** Lokal erreichbar; beide GitHub-Runner liefern weiterhin HTTP 403. Der Adapter ist eingebunden, aber das ist **keine funktionierende Cloud-Bestandsabdeckung**. Sperren stehen im Bericht und lösen 30 Minuten Backoff aus. Ein Wechsel von Linux zu Windows löst diese Sperre nach dem Test nicht.
* **Pokémon Center:** Shop und öffentliche Sitemap liefern weiterhin Schutzseiten bzw. leere Inhalte. Keine bestätigte Live-Stock-Abdeckung. Als zusätzliche offizielle Quelle wird `https://pokemon.gamespress.com/de` stündlich geprüft: maximal zwei Artikel zu Pokémon Center pro Besuch; Artikel ohne qualifiziertes Signal höchstens täglich erneut, nur dortige deutsche Artikel. Nur ein konkreter, datierter Verkaufsstart für passende Karten besteht die vorhandenen Ankündigungsregeln. Plüsch, Kleidung, allgemeine News und reine Erscheinungsdaten bleiben still. Der Direktlink führt zur Pressemitteilung, niemals zu einer behaupteten Kaufbestätigung.

`scripts/check_browser.py` prüft die Zugriffswege ohne Secrets und ohne Discord. Ein nicht erreichbarer Shop macht den Probe-Lauf bewusst rot; der JSON-Bericht unterscheidet erreichbare Kataloge, echte Produktvalidierung und einen ausdrücklich als Nicht-TCG markierten positiven Parser-Kontrollartikel. Dieser Kontrollartikel gelangt nie in die Alert-Pipeline. Die bestehenden Bot-Tests und Live-Zugriffstests sind getrennt zu beurteilen.

Der Bot läuft auf GitHub auch bei ausgeschaltetem PC. Die Pünktlichkeit des externen Fünf-Minuten-Auslösers bleibt davon unabhängig: seine zuvor ungültige GitHub-Freigabe muss wie oben beschrieben erneuert werden. Ein öffentlich zugänglicher, kostenloser und garantiert funktionierender Cloud-Zugriff auf alle drei Händler wurde nicht gefunden.
