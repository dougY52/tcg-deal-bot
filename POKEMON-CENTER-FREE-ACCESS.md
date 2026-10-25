# Pokémon Center Deutschland: kostenloser Cloud-Zugriff

Stand: 25.10.2026. **Zugang zu Homepage und deutschem Katalog bestätigt; noch keine bestätigte Live-Bestandsabdeckung.** Der bestehende Bot läuft weiterhin ohne Nutzer-PC auf GitHub Actions. Das GitHub-Secret `SCRAPINGANT_API_KEY` funktioniert. Kein weiterer Zugang ist für diesen Test erforderlich.

## Weitere kostenlose Queue-Recherche vom 25.10.2026

**Noch kein nachgewiesener zuverlässiger Live-Zugang zu deutschen Restocks oder einer aktiven Warteschlange.** Der kostenlose Cloud-Betrieb des Bots allein beweist diese Abdeckung nicht.

- Der öffentliche Quellcode der [PC-Queue-Erweiterung](https://github.com/imjoshin/pc-queue/blob/main/content.js) liest die Wartezeit `ttw` aus einem eingebetteten `/_Incapsula_Resource`-Rahmen. Das war ein konkreter fehlender Lesepfad unseres Browsers: `page.content()` enthält nur das äußere Dokument.
- Der Browser prüft jetzt zusätzlich bereits geladene, sichtbare, gleichnamige Rahmen auf der deutschen Homepage (`/de-de/`, `/en-de`). Er akzeptiert nur HTTP 200, gleiche HTTPS-Origin, erlaubten Robots-Pfad und eindeutigen sichtbaren Warteschlangentext. Er ruft keinen geratenen Backend-Pfad auf und führt keine CAPTCHA-/Queue-Aktion aus. Produktseiten werden niemals durch Rahmeninhalt ersetzt. Keine zusätzlichen Provider-Requests oder ScrapingAnt-Credits.
- Live-Beobachtung: Die deutsche Homepage lieferte HTTP 200 mit einem solchen Rahmen. Der tatsächlich verlinkte Rahmen lieferte **„Additional security check is required“**, keine Queue. Das bleibt `blocked_or_unreadable`; kein Discord-Alert und kein vermeintliches Ende einer zuvor offenen Queue. Temporäre Rahmenparameter, Cookies und rohe Schutzseiten werden nicht ins Repository geschrieben.
- Tests simulieren eine echte Queue-Seite im Rahmen, Fehlerseite, fremde Origin, falsche Länderregion, Produktseite, unsichtbaren Rahmen, Nicht-200-Status, Robots-Sperre, abgelösten Rahmen und vorhandene Discord-Deduplizierung. Der Browser-Smoke-Test nutzt vollständig lokal abgefangene Antworten; er ist ausdrücklich keine Live-Zugangsbestätigung.
- [pokemon-restock-monitor](https://github.com/cjudge129/pokemon-restock-monitor) und [cardalert](https://github.com/rgreen1207/cardalert) liefern keinen verifizierten kostenlosen Deutschland-Datenfeed. Geratene Queue-URLs oder beliebige Nicht-404-Antworten werden nicht als Beweis übernommen.
- [TCGCompare](https://www.tcgcompare.com/pokemon-tcg) bietet Queue-Benachrichtigungen an; eine frei dokumentierte, nachweisbar Deutschland-bezogene Discord-/Server-Schnittstelle konnte in dieser Prüfung nicht bestätigt werden. [CardScout](https://cardscout.co/) erhält Crowd-Meldungen aus Browser-Erweiterungen. Deren Einsende-Endpunkt ist kein bestätigter lesbarer Bestandsfeed. Der Bot sendet dort keine erfundenen Queue-Meldungen. [QueueDex](https://queuedex.com/) ist eine historische Drop-Quelle, keine bestätigte Live-Bestandsquelle.

Eine bestätigte Queue nutzt weiterhin den bestehenden Cloud-Scan und persistenten Episoden-State. Bei unverändertem Warteraum gibt es keine Wiederholung; eine zwischengeschaltete Schutzseite zählt nicht als Schließung. Eine Warteschlange wird nur als Hinweis auf den deutschen Seitenzugang gemeldet, **nicht** als bestätigter deutscher Karten-Drop. [Pokémon Center erklärt ausdrücklich](https://support.pokemoncenter.com/hc/en-us/articles/37286495522452-Pok%C3%A9mon-Center-Virtual-Queue), dass eine Queue weder Produktstart noch Verfügbarkeit garantiert.

Der Workflow bleibt im Fünf-Minuten-Zeitplan. GitHub-Verzögerungen, abgewiesene Zugriffe und kürzere Drop-Fenster können Meldungen weiterhin verhindern. Eine garantierte Sofort-Erkennung ist damit noch nicht erreicht. Der begrenzte externe Gratis-Anbieter bleibt ausschließlich manuelle Diagnose.

Zusätzlicher Betriebsfehler behoben: Eine direkte Browser-403-Sperre wird separat vom Cloud-Reader gespeichert. Dadurch sperrt ein abgewiesener MediaMarkt-/Saturn-Homepage-Queue-Check nicht mehr automatisch deren funktionierende Produktabfragen über den Worker. HTTP 429/503 bleiben weiterhin für den ganzen Host wirksam; bestehende unklassifizierte Sperrzeiten laufen regulär aus. Doppelt gestartete Workflows nennen im Bericht jetzt den Mindestabstand und erhalten die sichtbare Anzahl gespeicherter Ziele, statt einen scheinbar leeren Scanner anzuzeigen.

## Tatsächlich geprüft

- Direkte GitHub-/Cloudflare-Abrufe liefern weiterhin Schutzseiten, teilweise mit HTTP 200.
- ScrapingAnt im verifizierten Gratis-Tarif konnte mit einem Residential-Browser die deutsche Homepage und `/de-de/category/trading-card-game` laden. Ein unmittelbar wiederholter Homepage-Test lieferte jedoch erneut eine Schutzseite: Der Zugriff ist bislang nicht zuverlässig.
- Der Katalog enthielt unter anderem Dunkelnacht-Boosterbundles (27,99 EUR), Dunkelnacht-Displays (165,99 EUR) und Delta-Herrschaft-Displays (165,99 EUR). Das sind **beobachtete Katalogpreise vom Testzeitpunkt, keine bestätigten lieferbaren Angebote**.
- Die eingebetteten JSON-LD-Angebote behaupteten dagegen USD und `OutOfStock`. Diese Metadaten werden deshalb ausdrücklich nicht als Preis-/Bestandsnachweis übernommen.
- Der erste Versuch, das konkret verlinkte Boosterbundle aufzurufen, endete mit Anbieter-HTTP 423. Auch der gezielte Folgetest der direkt aus dem Katalog übernommenen Display-URLs scheiterte: Dunkelnacht HTTP 423, Delta-Herrschaft eine Schutzseite. Es wurde kein Produktbestand bestätigt. Ergebnis: `research/pokemon-center-products-2026-10-25.json`.
- Öffentliche Testdaten: `research/pokemon-center-scrapingant-2026-10-25.json`. Keine API-Keys, Cookies oder vollständigen Netzwerkantworten. Der Bericht kennzeichnet sämtliche Katalogdaten als `inventory_confirmed: false`.

## Umsetzung und Kostenbegrenzung

- `tcg_bot/pokemon_center_access.py`: ausschließlich öffentliche Deutschland-URLs; Robots-Prüfung; Gratis-Tarif und Restkontingent vor jeder Anfrage; feste Zeitlimits; keine automatischen Wiederholungen; keine Tarifänderung. Bei unerwartetem Credit-Verbrauch wird abgebrochen.
- `scripts/check_pokemon_center.py`: gezielter Test von zwei beobachteten Display-Seiten, maximal **250 reservierte Gratis-Credits**. Deutscher Browserstandort, Warten auf Produktüberschrift und kurze zusätzliche Ladezeit. Keine Warenkorbänderungen und keine Discord-Nachrichten.
- `cloud-watch.yml`: Der externe Anbietertest läuft nur bei explizitem manuellem Workflow-Start mit `pc_access_test=true`. Standard ist `false`. Reguläre Fünf-Minuten-Läufe und Code-Pushes verbrauchen keine ScrapingAnt-Credits. Für einen vollständig nachrichtenfreien Test zusätzlich `dry_run=true` belassen.
- Das Diagnoseartefakt `pokemon-center-access` bleibt drei Tage verfügbar. Ein grüner Workflow bedeutet nur, dass die Diagnose ausgeführt wurde; der konkrete Zugriffsstatus steht im Bericht.
- Der bestehende Drop-Watch berücksichtigt `/de-de/` und `/en-de` unter demselben persistenten Dedupe-Schlüssel. Die bisherigen Scanner, Discord-Secrets und der normale Bot-State bleiben erhalten.

Die [Anbieterseite](https://scrapingant.com/) nennt 10.000 kostenlose Credits pro Monat ohne Kreditkarte. Der bisher erfolgreiche Browsermodus benötigt **125 Credits pro Abruf**, im Test über den Kostenheader bestätigt. Damit sind theoretisch höchstens 80 solcher Abrufe pro Monat möglich. Ein Fünf-Minuten-Scan schon einer einzelnen Seite benötigt dagegen 8.640 Abrufe in 30 Tagen. Diese Methode liefert deshalb **keine kostenlose flächendeckende Fünf-Minuten-Abdeckung**.

[Dokumentierte Kosten](https://docs.scrapingant.com/credits-cost): Standard HTTP 1, Standard Browser 10, Residential HTTP 25, Residential Browser mit JavaScript 125 Credits. Die günstigeren getesteten Modi lieferten keine verwertbare deutsche Produktseite.

## Grenze vor Discord-Aktivierung

Ein lesbarer Katalog genügt nicht. Vor einer Aktivierung müssen konkrete deutsche Karten, EUR-Preis, Produktvariante, aktuelle Bestellmöglichkeit und Lieferung nach Deutschland auf der Produktseite bestätigt werden. Auch eine deutsche Shop-Oberfläche allein beweist nicht die Kartensprache. Zubehör wie Ordner, Deckboxen oder Spielunterlagen wird aus sealed Produktkandidaten entfernt.

Bis diese Prüfung erfolgreich ist, gibt es **keine Bestands-/Deal-Alerts aus diesem Anbieterzugriff**. Der vorhandene Drop-Watch kann weiterhin separat bestätigte Warteschlangen oder datierte offizielle Verkaufsankündigungen melden. Keine Testnachrichten oder „keine Treffer“-Meldungen.

## Öffentliche Quellen

- [Deutsche Pokémon-Center-Presse](https://pokemon.gamespress.com/de/MEDIENMITTEILUNG-Pokemon-Center-veroffentlicht-die-Feiertagskollektion) verlinkt `/de-de/`; [Länderauswahl im Support](https://support.pokemoncenter.com/hc/en-us/articles/360051729272-How-do-I-select-a-different-country-on-Pok%C3%A9mon-Center) nennt `/en-de`.
- [robots.txt](https://www.pokemoncenter.com/robots.txt) schließt unter anderem `/cortex`, `/availabilities`, `/offers` und `/prices` aus. Diese Endpunkte werden nicht gescannt.
- [ScrapingAnt: Browserstandort](https://docs.scrapingant.com/proxy-settings), [Warten auf Seitenelemente](https://docs.scrapingant.com/wait-for-selector), [zusätzliche Ladezeit](https://docs.scrapingant.com/javascript-execution).
