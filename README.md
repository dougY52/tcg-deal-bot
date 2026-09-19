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

## GitHub Actions: Betrieb ohne eingeschalteten PC

Der öffentliche GitHub-Workflow prüft mit `6,16,26,36,46,56 * * * *` ungefähr alle zehn Minuten. GitHub kann Starts verzögern oder auslassen; dies ist kein garantierter Echtzeitdienst. Ein Update der Workflowdatei startet ebenfalls einen Lauf. Ein manueller Start ist mit oder ohne Versand möglich; standardmäßig ist dabei der Probelauf gewählt.

Der Windows-Zeitplan bleibt deaktiviert. Nicht parallel aktivieren: PC und Cloud würden getrennte Meldungshistorien führen. Die bisherige PC-Historie wurde für den Wechsel in den Branch `bot-state` übertragen. Nur der GitHub-Workflow schreibt danach den Meldungsstand weiter.

Der Discord-Zugang kommt ausschließlich aus dem bestehenden GitHub-Secret `DISCORD_WEBHOOK_URL`. Private Repositories werden vom Workflow ausgeschlossen; Standard-Linux-Runner in öffentlichen Repositories sind kostenlos. Der Prüfbericht wird für drei Tage als Actions-Artefakt gespeichert.

Status: Im Repository unter Actions → TCG Cloud Watch. Händlerfehler oder unvollständige Kataloge können einen Lauf als fehlgeschlagen markieren, auch wenn andere Händler erfolgreich geprüft und Nachrichten gesendet wurden. Details stehen im Laufprotokoll und Prüfbericht.

Quellen: [Kosten](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Zeitplan-Einschränkungen](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).

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

## Erweiterung vom 19.09.2026

Neue Katalogquellen: TCG Garden, Moon-Shadow, Lake Cards, BreakTheCase, FantasiaCards und Spiele-Spezi (jeweils maximal acht Katalogseiten). Lake Cards und BreakTheCase prüfen die konkret gefundenen AoT-/JoJo-Produkte zusätzlich unabhängig von der Katalogreihenfolge. Hobby-Schmidt und Zuris-Shop prüfen zunächst einzelne verlinkte Produktseiten, keine vollständigen Sortimente. Hobby-Schmidt lieferte beim Test keinen eindeutigen Online-Bestand; Zuris-Shop eine abweichende Verkäuferbezeichnung. Diese Angebote bleiben bis zur sicheren Klärung im Bericht.

Ein Preisrückgang von mindestens 3 EUR UND 5 Prozent gegenüber der letzten erfolgreich gesendeten Meldung umgeht die 24-Stunden-Sperre. Nach Versand wird der neue Preis gespeichert; unveränderte Preise werden weiterhin nicht wiederholt. Unabhängiger Marktvergleich, belegter Normalpreis und Verfügbarkeitsprüfung bleiben erforderlich. Einzelbooster-Inhaltsangaben (etwa „1 Boosterpack enthält 10 Karten“) verfälschen nicht länger die Displaygröße.

Validierung: 112 Tests; Live-Abruf der acht zusätzlichen Quellen. Vergleich mit der Cloud-Historie ergab Naruto 2nd Edition für 50 EUR als neuen qualifizierten Preisrückgang. Das ist noch kein Nachweis eines Discord-Versands. Keine vollständige Händler- oder Marktabdeckung.

Bei mindestens fünf Vergleichshändlern wird die Konsistenz an der mittleren Mehrheit der Preise geprüft (je 20 Prozent an den Rändern ausgenommen). Median und geprüfter Normalpreis bleiben die Bewertungsbasis. Ein einzelner teurer Händler blockiert damit nicht mehr einen belegten Preisrückgang. 114 Tests einschließlich des vollständigen Naruto-Preisbilds bestanden.

## Alle qualifizierten Händlerangebote

Seit dem 19.09.2026 wird pro Produkt, Sprache und unabhängigem Händler gemeldet. Ein günstigeres Angebot eines anderen Händlers unterdrückt andere Angebote nicht. Deutsche Angebote stehen zuerst; englische werden ebenfalls berücksichtigt. Preisrahmen unverändert: bis zu 30 EUR über dem belegten Normalpreis, mit Bewertung und Aufpreis. Die Prüfung von Bestand, Identität, Preisbelegen und Marktvergleich bleibt aktiv; damit sind nicht sämtliche online auffindbaren Angebote automatisch freigegeben.

Die Versandhistorie wird pro Händler geführt. Vorhandene bestätigte Meldungen werden ausschließlich dem tatsächlich gemeldeten Händler zugeordnet; andere Shops werden dadurch nicht gesperrt. Unveränderte Angebote bleiben stumm, deutliche Preisverbesserungen umgehen die Wiederholungssperre. Pro Lauf werden bis zu 20 Meldungen versendet; übrige qualifizierte Angebote bleiben für weitere Läufe offen. Tests prüfen mehrere Händler, gemeinsame Händlergruppen, die Übernahme alter Meldungen, Versandfehler und das Fortsetzen nach dem Nachrichtenlimit.

Der eigenständige Workflow `.github/workflows/cloud-watch.yml` besitzt den Cloud-Zeitplan. `watch.yml` ist nur noch manuell startbar. Beide teilen dieselbe Sperre gegen parallele Läufe und dieselbe Versandhistorie. Ein erfolgreicher Start per Commit bestätigt den Zeitplan nicht; dafür muss ein Lauf mit Ereignis `schedule` nachgewiesen werden.
