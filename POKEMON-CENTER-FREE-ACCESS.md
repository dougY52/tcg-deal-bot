# Pokémon Center Deutschland: kostenloser Cloud-Zugriff

Stand: 25.10.2026. **Zugang zu Homepage und deutschem Katalog bestätigt; noch keine bestätigte Live-Bestandsabdeckung.** Der bestehende Bot läuft weiterhin ohne Nutzer-PC auf GitHub Actions. Das GitHub-Secret `SCRAPINGANT_API_KEY` funktioniert. Kein weiterer Zugang ist für diesen Test erforderlich.

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
