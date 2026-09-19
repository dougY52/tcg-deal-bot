# Anime TCG Deal Watch – Version 3

Kostenloser Python-Bot für deutsche Händler: breite Katalog-Discovery, genaue Produktzuordnung, unabhängiger Marktvergleich und konservative Discord-Meldungen. Python 3.12+, Standardbibliothek, keine bezahlte API.

## Wichtigste Regel: keine Scalperpreise

**Eine Ersparnis gegenüber überhöhten Angeboten ist kein Deal.** Jede Meldung braucht eine geprüfte, höchstens 30 Tage alte Hersteller-UVP in EUR oder einen ausdrücklich belegten regulären Händlerpreis. Der gewünschte Preisrahmen liegt jetzt bei **bis zu 30 € über dem belegten Normalpreis/der belegten UVP**. Verifizierte neue Angebote innerhalb dieses Rahmens werden auch ohne Restock gemeldet. Die Bewertung bleibt streng: ein Aufpreis wird ausdrücklich genannt und ist kein Schnäppchen. Hohe aktuelle Marktpreise erhöhen die Grenze niemals. Ein Händlerpreis ist keine UVP; die Nachricht benennt den Unterschied.

Zusätzlich sind mindestens **zwei andere unabhängige Händler** (drei Händler insgesamt), identisches Produktformat, ein konsistenter Vergleichsmarkt und Confidence ≥90 % erforderlich. Confidence ist ein nachvollziehbarer Regelwert, keine statistische Wahrscheinlichkeit.

- Preisdeal: mindestens 15 % und 8 € unter dem bereinigten Median; außerdem nicht teurer als der günstigste Vergleichshändler.
- Neue verifizierte Angebote bis Normalpreis + 30 €: Meldung mit Bewertung; pro Produkt nur das günstigste qualifizierte Angebot. Bereits gemeldete Preise werden nicht wiederholt.
- Restock: bestätigter Ausverkauf mindestens sechs Stunden, letzte Bestandsbeobachtung höchstens zwei Stunden alt, Rückkehr innerhalb des Preisrahmens (höchstens 30 € Aufpreis), höchstens zwei aktuell verfügbare Händler und kein günstigerer aktuell verfügbarer Vergleichshändler. Fehlende Seiten/Fehler sind niemals ein Ausverkauf.
- Fehlende UVP/Normalpreisreferenz, uneindeutige Variante, Sprache oder Packzahl, Vorbestellung, beschädigte Verpackung: **nur Prüfbericht, niemals Discord**.
- Beispiel B15: 83,99 € ist bei einem belegten Normalpreis von 79,99 € kein starker Preisdeal. Innerhalb des neuen Preisrahmens darf es mit ehrlicher Bewertung gemeldet werden; die Marktprüfung bleibt erforderlich. Die Beispielpreise 60–80 € in den Tests sind Regressionstestdaten, keine Live-Angebotsliste.

Es gibt bewusst keine Zusage, den gesamten deutschen Markt oder jedes Anime-Set zu finden. Strenge Prüfungen führen insbesondere anfangs zu wenigen oder keinen Meldungen. Das ist besser als ein ungesicherter „Deal“.

## Preisbewertung pro Angebot

- 🔥 **Sehr guter Preis:** mindestens 15 % und 8 € unter der Vergleichsbasis.
- 🟢 **Guter / fairer Preis:** auf oder unter der Vergleichsbasis.
- 🟡 **Noch okay:** maximal 15 % über der Vergleichsbasis, zusätzlich innerhalb der 30-€-Grenze; kein Schnäppchen.
- 🟠 **Erhöhter Preis:** mehr als 15 % Aufpreis, aber höchstens 30 € über dem geprüften Normalpreis; Meldung mit ausdrücklichem Hinweis „kein Schnäppchen“.
- 🔴 **Über deinem Preisrahmen:** mehr als 30 € über dem geprüften Normalpreis; keine Meldung.
- ⚪ **Nicht sicher bewertbar:** fehlende Referenz oder unzureichende Vergleichsdaten; keine Meldung.

Die Vergleichsbasis ist der kleinere Wert aus geprüftem Normalpreis (gegebenenfalls historisch abgesenkt) und bereinigtem Marktmedian. Bewertungen werden erst nach bestandener Identitäts-, Referenz- und Confidence-Prüfung vergeben. Es sind automatische Regelbewertungen, keine persönliche KI-Liveprüfung.

Beispiel: Normalpreis und Marktmedian 70 €, Angebot 80 € → **🟡 Noch okay**, 14,3 % Aufschlag. Verifizierte Angebote innerhalb des 30-€-Rahmens dürfen jetzt auch ohne Preisvorteil oder Restock gemeldet werden. Fehlende Referenzen/Marktdaten bleiben ausgeschlossen. Jede Kandidatenbewertung steht im JSON-Prüfbericht; Discord nennt Bewertung, Begründung und Vergleichspreise.

## Ausgeschlossene Spiele

Auf Nutzerwunsch werden **Digimon und Yu-Gi-Oh!** nicht mehr überwacht oder gemeldet. Gemischte Händlerkataloge können die Artikel weiterhin enthalten; der Bot verwirft sie als irrelevant.

## Pipeline

1. `sources.py` liest paginierte öffentliche Shopify-Kataloge und gezielte Collections. `web_sources.py` liest Such-/Kategorieseiten, strukturierte Angebote und begrenzt verlinkte Produktseiten. Bestehende Spezialadapter bleiben verfügbar.
2. `market.py` normalisiert Franchise, Spielsystem, Setcode/Setname, Edition, Sprache und Boosterzahl. Masters/Fusion World, 1st/2nd Edition, DE/EN und Displaygrößen bleiben getrennt. Namens-Fallback ist konservativ exakt, kein unsicheres Fuzzy Matching. Unbekannte Editionen werden nicht mit ausdrücklich benannten Editionen gemischt.
3. Eine Händlergruppe zählt einmal; der Kandidat wird nicht in seinen eigenen Vergleich einbezogen. Ausverkaufspreise gelangen nur über zuvor beobachtete verfügbare Angebote und maximal 24 Stunden in den Vergleich. Fehlende, veraltete und extreme Vergleichswerte scheiden aus.
4. Fester UVP/Normalpreis-Anker + Median + Mindestvorteil + Bestandswechsel bestimmen die Qualifikation. Historische Preise können die Obergrenze zusätzlich senken, aber nie alleine eine UVP begründen.
5. DE wird bei qualifizierten Treffern desselben Sets/Formats bevorzugt, sonst EN. Pro Identität nur das günstigste qualifizierte Angebot.
6. JSON speichert 90 Tage Preis-/Bestandsänderungen, maximal 180 Stichproben je Angebot, Restock-Episoden und bestätigte Meldungen. Erneute Meldung erst nach 24 Stunden und deutlicher weiterer Preissenkung oder neuer Restock-Episode. Alte Versandhistorie wird beim Upgrade übernommen.
7. Discord enthält Produkt, Sprache, Händler, Preis, Normalpreis/UVP-Beleg, Marktmedian, Vergleichslinks, Grund und Confidence. Nur Produktpreise inkl. MwSt. werden verglichen; Versand wird ausdrücklich als zusätzlich gekennzeichnet. Keine Garantie für günstigsten gelieferten Endpreis.

## Lokal prüfen

```sh
python -m unittest discover -s tests -v
python -m tcg_bot --check-config
python -m tcg_bot --report report.json
```

Der letzte Befehl ist ein **Dry-run**: keine Discord-Nachrichten, keine Änderungen an der gespeicherten Historie. `--send` aktiviert Versand und atomare Zustandsspeicherung; der Webhook kommt ausschließlich aus `DISCORD_WEBHOOK_URL`. Niemals Webhook oder private PC-Laufzeitdateien ins Repo aufnehmen.

`report.json` enthält Gründe für ausgeschlossene Produkte, Quellfehler und Teilabdeckung. Ein unvollständiger Lauf liefert Exitcode 1; gültige Treffer anderer Quellen werden trotzdem bewertet. Exitcode 2 bedeutet Abbruch. Die Diagnose-Workflows haben keine Versandfreigabe.

## GitHub Actions: stündlich, ohne Doppelbetrieb

Der Workflow enthält `17 * * * *`. **Automatische Cloud-Läufe sind zusätzlich durch `TCG_RUNNER=github` gesperrt**, solange der vorhandene PC-Betrieb zuständig ist. Nicht PC und Cloud gleichzeitig aktivieren: ihre getrennten Historien könnten Doppelmeldungen erzeugen.

Zum Wechsel auf GitHub:

1. Den PC-Zeitplan „TCG Deal Watch PC“ pausieren. Aktuellen privaten `state.json`-Meldungsstand ohne Zugangsdaten auf den Branch `bot-state` übernehmen, falls dort ein älterer Stand liegt.
2. Projekt einschließlich `.github` im bestehenden **öffentlichen** Repository aktualisieren. Secret `DISCORD_WEBHOOK_URL` setzen/weiterverwenden; Actions muss Repository-Inhalte schreiben dürfen.
3. Unter Actions Variables `TCG_RUNNER=github` setzen. Zunächst manuell mit `dry_run=true` prüfen; danach übernimmt der Stundenplan.

Der Workflow verweigert private Repositories, damit keine kostenpflichtigen Laufminuten entstehen. Standard-Runner öffentlicher Repositories sind laut [GitHub-Abrechnung](https://docs.github.com/en/actions/concepts/billing-and-usage) kostenlos. Zeitpläne können verspätet starten und nach 60 Tagen Repository-Inaktivität deaktiviert werden: [GitHub-Dokumentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows). Kein Echtzeit-SLA und keine absolute Betriebszusage.

Der Branch `bot-state` wird nach Versand sowie bei Teilfehlern gesichert; keine flüchtige Cache-Abhängigkeit. Läufe überschneiden sich nicht. Zwischen bestätigtem Discord-Versand und dauerhaftem Git-Push bleibt eine kleine Absturzlücke: exakt-einmalige Zustellung lässt sich über diese beiden Systeme nicht garantieren.

## Quellen und neue Shops

Die aktuelle Liste steht in [QUELLEN-V3.md](QUELLEN-V3.md), alle Einstellungen in `config/config.json`. EU-/Importquellen aus Version 2 sind erhalten, aber im Deutschland-Modus deaktiviert. Frühere Prüfberichte dokumentieren Version 2 und sind kein aktueller Betriebsnachweis.

Neuen Shopify-Shop als Objekt in `shops` ergänzen:

```json
{
  "id": "neuer-shop", "name": "Neuer Shop",
  "base_url": "https://shop.example", "adapter": "shopify",
  "currency": "EUR", "max_pages": 8,
  "catalog_collections": ["booster-displays"],
  "retailer_group": "eindeutiger-betreiber"
}
```

Nur zuvor geprüfte seriöse Direktverkäufer aufnehmen. Unterschiedliche Domains desselben Betreibers bekommen dieselbe `retailer_group`. Für HTML-Shops `adapter: html_catalog`, geprüfte `catalog_urls`, optional `product_urls`, `max_detail_pages` und `product_link_pattern` verwenden. Der Bot verwendet nur strukturierte exakte Angebotspreise, keine durchgestrichenen Preise oder „ab“-Preise. Die URL im Beispiel ist ein Platzhalter.

Für jede neue Quelle einen Dry-run und Parser-Test ergänzen. Bei fehlender Sprache/Packgröße zuerst Quellenadapter verbessern; nicht die Sicherheitsfilter lockern. Neue Anime-Franchises sind Regexeinträge in `franchises`; Set-Aliase stehen unter `market.set_aliases`. Dubiose nicht lizenzierte Produkte erhalten keine Preisreferenz.

## Preisreferenz ergänzen

Die Kandidatenliste liefert die exakte `identity`. Nach Prüfung von Hersteller oder seriösem Normalpreis-Beleg unter `market.price_references` ergänzen:

```json
{
  "identity": "masters|BT15|unspecified|24|standard|EN",
  "kind": "observed_retail",
  "price_eur": "79.99",
  "verified_on": "2026-09-18",
  "valid_until": "2026-10-18",
  "evidence_url": "https://comic-attack.de/produkt/dragon-ball-super-card-game-b15-saiyan-showdown-booster-box/"
}
```

`msrp` ausschließlich für belegte Hersteller-UVP desselben Produkts und Markts. Amerikanische Einzelpack-UVP wird nicht als deutsche Display-UVP umgerechnet. `market_reference` ist nur als Datenkategorie erlaubt und kann keine Normalpreisfreigabe erzeugen. Cardmarket wird nicht aggressiv gescrapt; ein Marktplatz-Tiefstpreis oder Suchsnippet reicht nicht als Retailfreigabe. Ein Prüfer muss veraltete Anker erneuern; das System erhöht sie nicht selbst.

## Rücksicht auf Quellen

robots.txt wird pro Herkunft geladen; 404 wird als fehlende robots-Datei behandelt, andere Fehler sperren die Abfrage. Wildcards, Allow/Disallow, Crawl-delay und Request-rate werden berücksichtigt. Mindestens eine Sekunde Abstand je Host, keine Redirect-Umgehung. HTTP 429/503 beendet weitere Anfragen an den Host im Lauf; Retry-After wird im Versandbetrieb über Läufe hinweg gespeichert. Kein Captcha-/Bot-Schutz-Bypass, keine bezahlte Such-API.

Seiten-/Detailgrenzen sind explizit und erzeugen Warnungen. Sehr große Kataloge müssen über gezielte Collections oder passende Grenzen abgedeckt werden. HTML-Seiten ohne strukturierte Bestandsdaten bleiben Kandidaten oder liefern eine Quellwarnung.

## Reparatur der Produktzuordnung

Am 18.09.2026: geprüfte Set-Aliase verbinden Naruto Konoha Shido/First Set sowie Shinobi Shiren und unterschiedliche Schreibweisen der Edition. Editionsnummern bleiben getrennt, zählen aber nicht doppelt zum Setnamen. Explizite 18er-/36er-Displaygrößen werden erkannt. Drei unabhängige Händler insgesamt genügen nur zusammen mit gültigem geprüftem Normalpreisanker und unverändert mindestens 90 % Confidence. Alte Versandhistorie für umbenannte Identitäten wird übernommen.
