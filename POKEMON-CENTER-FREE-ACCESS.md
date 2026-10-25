# Pokémon Center Deutschland: kostenloser Cloud-Zugriff

Stand: 25.10.2026. **Noch keine bestätigte Live-Bestandsabdeckung.** Der Bot läuft weiterhin ohne Nutzer-PC auf GitHub Actions. Diese Ergänzung prüft weitere Zugriffswege, ohne ungeprüfte Bestände an Discord zu melden.

## Was umgesetzt ist

- Der vorhandene Drop-Watch prüft die offiziell verlinkte deutsche Adresse `/de-de/`, mit `/en-de` als zweitem öffentlichen Deutschland-Pfad. Beide teilen denselben persistenten Dedupe-State. Keine zweite Aufgabe und keine doppelten Queue-Alerts.
- Der bestehende GitHub-Workflow führt bei Push und manuellem Dry Run `python -m scripts.check_pokemon_center` aus. Reguläre Fünf-Minuten-Läufe verbrauchen **keine** externen Scraping-Credits.
- Der Bericht `pokemon-center-access-report.json` wird drei Tage als GitHub-Artefakt bereitgestellt. Er enthält Zugriffsstatus, öffentliche Überschriften und Kandidatenlinks, keine API-Keys, Cookies oder vollständigen Netzwerkantworten.
- Mit dem optionalen Secret `SCRAPINGANT_API_KEY` kann derselbe Test vier Abrufverfahren prüfen. Vor jedem Abruf muss die Nutzungs-API ausdrücklich `Free` oder `Free Plan` und ausreichende Gratis-Credits bestätigen. Bezahlte, Trial- und unbekannte Tarife werden abgelehnt. Kein Upgrade, keine Zahlung, keine automatischen Wiederholungen.
- Tests prüfen unter anderem HTTP-200-Schutzseiten, fremde Länder/URLs, Gratis-Tarif, Credit-Limit, Geheimnisschutz und fehlende Schlüssel. Lesbare Produktdaten werden ausdrücklich **nicht** automatisch zu bestätigten Angeboten.

## Neuer kostenloser Kandidat: ScrapingAnt

Die [Anbieterseite](https://scrapingant.com/) nennt 10.000 Credits **monatlich**, ohne Kreditkarte. Das ist eine überprüfbare Tarifangabe, keine Zusage, dass Pokémon Center erreichbar ist.

Laut [Credit-Dokumentation](https://docs.scrapingant.com/credits-cost):

| Abruf | Credits pro Versuch laut Dokumentation | Theoretische Abrufe aus 10.000 Credits |
|---|---:|---:|
| Standard HTTP | 1 | 10.000 |
| Standard Browser mit JavaScript | 10 | 1.000 |
| Residential HTTP | 25 | 400 |
| Residential Browser mit JavaScript | 125 | 80 |

Der Diagnoseversuch reserviert höchstens **161 Credits** nach diesen dokumentierten Preisen (1+10+25+125), beendet sich beim ersten lesbaren Ergebnis und stoppt bei unerwarteten Kosten. Das Gratis-Konto ist die eigentliche Kostengrenze; der Bot nimmt keine Tarifänderung vor. Keine Zusage für Fünf-Minuten-Bestandschecks: Bereits eine einzelne Seite benötigt dafür 8.640 Abrufe in 30 Tagen, mehrere Produkte entsprechend mehr.

## Einmalig fehlender Zugang

1. Kostenloses Konto unter [ScrapingAnt](https://app.scrapingant.com) anlegen, keine Zahlungsdaten hinterlegen.
2. Den API-Key ausschließlich als Repository-Secret `SCRAPINGANT_API_KEY` unter [GitHub Actions Secrets](https://github.com/dougY52/tcg-deal-bot/settings/secrets/actions) speichern. Nicht in Chat, Code oder Konfiguration posten.
3. Bestehenden **TCG Cloud Watch** manuell mit **dry_run=true** starten, oder nach dem Speichern im Chat Bescheid geben, damit der Test gestartet werden kann.

Ohne Secret wird der Anbieter übersprungen. Das ist im Bericht `not_configured`, kein erfolgreicher Anbieter-Test.

## Abnahmekriterien vor Aktivierung von Bestandsmeldungen

Ein erfolgreicher Homepage-Abruf reicht nicht. Zuerst müssen eine konkrete deutsche TCG-Produktseite, EUR-Preis, richtige Variante, aktuelle Bestellmöglichkeit und Versand nach Deutschland unabhängig validiert werden. Öffentliche Hersteller-Metadaten, Suchindexpreise, eine Queue oder ein lesbares Shop-Menü sind kein Bestandsbeweis. Erst nach einem echten erfolgreichen Produkt-Test wird ein dauerhafter Abfrageplan innerhalb der kostenlosen Limits aktiviert.

Der bestehende Drop-Watch kann weiterhin ausdrücklich gekennzeichnete, bestätigte Warteschlangen oder datierte Verkaufsankündigungen melden. Keine Testnachrichten und keine „keine Treffer“-Meldungen.

## Weitere Rechercheergebnisse

- [Offizielle deutsche Presse](https://pokemon.gamespress.com/de/MEDIENMITTEILUNG-Pokemon-Center-veroffentlicht-die-Feiertagskollektion) verlinkt `/de-de/`; [Pokémon Center Support](https://support.pokemoncenter.com/hc/en-us/articles/360051729272-How-do-I-select-a-different-country-on-Pok%C3%A9mon-Center) nennt `/en-de`. Deshalb werden beide berücksichtigt.
- Direkte Produkt-/Katalogseiten, Sitemap und gewöhnlicher Cloudflare-Browser blieben bei den bisherigen Tests Schutzseiten. Aktuelle zusätzliche Cloud-Ergebnisse: `research/pokemon-center-access-followup-2026-10-25.json`.
- [robots.txt](https://www.pokemoncenter.com/robots.txt) schließt unter anderem `/cortex`, `/availabilities`, `/offers` und `/prices` aus. Diese Endpunkte werden nicht gescannt.
- Gefundene Open-Source-Projekte mit aus dem Nutzerbrowser kopierten Cookies benötigen regelmäßige Erneuerung und sind keine wartungsfreie Lösung ohne PC. Ein generischer Queue-it-HTTP-200-Status belegt weder eine Deutschland-Queue noch einen Drop; eine solche Heuristik wurde nicht übernommen.
- [ScraperAPI](https://www.scraperapi.com/pricing/) nennt ebenfalls einen kostenlosen Tarif, aber mit 1.000 Credits deutlich weniger Spielraum. Kein zusätzlicher Dienst angemeldet.
