# Prüfbericht · Version 2 · 18.09.2026

## Implementiert und geprüft

- 48 automatisierte Tests bestanden; Konfiguration validiert.
- Neue Adapter für MediaMarkt/Saturn, Otto sowie JSON-LD/schema.org-Microdata.
- Zusätzliche Tests für Drittanbieter-Verkäufer, unbekannte Bestände, Vorbestellungen, physische statt online verfügbare Angebote, OTTO-Raten/Ab-Preise, GTIN-Prüfziffern und händlerübergreifende Identität.
- Vorhandene Tests für Preisfilter, Restocks, Wiederholungssperren, Discord-Fehler und Git-Statusspeicherung weiterhin bestanden.
- Zehn Quellen konfiguriert; zehn Produkt-/Sprachregeln mit 16 konkreten Händlerbindungen. Ultra Comix ist ein einzelnes Produktziel; Otto liefert nur Kandidaten. Nicht mit zehn vollständigen Shopkatalogen verwechseln.

## Live-Vorschau

Ein gemeinsamer Lauf mit neun Quellen las 3.342 Angebotsvarianten:

| Quelle | Varianten |
|---|---:|
| KartenZeche | 38 |
| CardBuddys | 375 |
| CardCosmos | 1.030 |
| Skash Cards | 14 |
| CrispyCards | 1.733 |
| MediaMarkt | 16 |
| Saturn | 16 |
| Otto | 11 |
| Gate to the Games | 109 |

Alle neun Quellen lieferten Daten. Eine zusätzliche MediaMarkt-Produktseite konnte nicht geladen werden; der Lauf wurde deshalb korrekt mit einer Warnung und Exitcode 1 abgeschlossen. Keine Quelle fiel vollständig aus. Sechs Händlerangebote bestanden den Preisfilter, fünf davon blieben nach Deutsch-Präferenz als Meldungen übrig. Es wurden **keine Nachrichten gesendet**.

Ultra Comix wurde anschließend als zehnte Quelle separat mit dem fertigen Adapter live geprüft. Die Seite liefert das englische Fairy-Tail-Display zu 65 Euro und ausdrücklich ausverkauft. Sie ist als Restock-Ziel eingerichtet.

## Nachgewiesene Grenzen

- Ein Test mit `storeId=424` an einer MediaMarkt-Produktseite lieferte weiterhin `storeId: null`. Keine Bestätigung eines konkreten Filialbestands. Keine Standortpräferenz aus diesem Test abgeleitet.
- Cardmarket/Müller/Kaufland: HTTP 403; Smyths/FantasyWelt: Kategorie HTTP 403.
- Rossmann: HTTP 200, aber nur „Client Challenge“, keine Produktdaten.
- OTTO-Katalog lesbar; geprüfte Produktseiten HTTP 400. Händleridentität deshalb nicht ausreichend geprüft, keine automatische Deal-Freigabe.
- Games-Island-Feed und Galaxus-Suche werden durch robots.txt gesperrt.
- ROFU/idee+spiel: getestete Einstiegspfade nicht nutzbar; keine aktive Integration.

Das vollständige Quellenverzeichnis steht in `QUELLEN.md`. Es wurden keine kostenpflichtigen APIs oder CAPTCHA-Umgehungen verwendet.

## Noch nicht getestet

Kein echter GitHub-Actions-Lauf im Konto des Nutzers, keine Zustellung in einen echten Discord-Kanal und keine automatische Filialüberwachung. Die Suchregion wurde anschließend auf Nutzerwunsch auf 65934 mit 50 km Umkreis gesetzt. Dies ist eine Konfigurationsänderung; sie ist kein Nachweis funktionierender Filialabrufe. Die Preisreferenzen sind dokumentierte Händlerpreise, keine bestätigten Hersteller-UVPs. Versandkosten sind nicht Bestandteil der Preisgrenzen.

## Version 2.2: schnellere Meldungen

Fünf-Minuten-Zeitplan für explizite Produktbindungen, stündliche Katalogsuche. Keine Sechs-Stunden-Sperre und keine künstliche Begrenzung auf sechs Meldungen. 51 automatisierte Tests bestanden, Konfiguration und Workflow-Zeitplan geprüft; weiterhin kein echter GitHub-Lauf oder Discord-Versand. Die Live-Prüfergebnisse oben stammen aus Version 2 und stellen keine neue Verfügbarkeitsprüfung dar.

## Erweiterung: Produktentdeckungen

57 lokale Tests bestanden. Neue Tests: FB10 ohne Preisreferenz, Wiederholungsunterdrückung, Zustellfehler/Wiederholung, Vorschau, bestehender Ausgangsstand, Versandlimit, späterer Retail-Treffer, nicht verfügbare/unklare Bestände ausgeschlossen, bestellbare Vorbestellungen erlaubt, Verkäufer-/Sprach-/Zubehörfilter. Kein künstlicher Discovery-Testpost an Discord.

## Browseradapter

60 lokale Tests bestanden. Isolierter Chromium-Livecheck: MediaMarkt und Saturn jeweils 59,99 EUR, verfügbar=false, Verkäufer bestätigt. Katalogseiten ebenfalls lesbar. LimitedMarket: Sicherheitsprüfung/403. Smyths:403. Rossmann: Amigo-Katalog lesbar, frühere Produktseite nicht gefunden. Keine Discord-Testmeldungen. GitHub-Validierung separat, lokaler Test allein ist kein Cloud-Nachweis.

### Ergebnis des GitHub-Browsertests

[Browser source check](https://github.com/dougY52/tcg-deal-bot/actions/runs/35339357663): Installation und 60 Tests erfolgreich; MediaMarkt und Saturn jeweils **Browser HTTP 403**. Deshalb wird Browserbetrieb im regulären Workflow nur nach ausdrücklicher Aktivierung über die Repository-Variable TCG_BROWSER=1 installiert/benutzt. Kein Erfolg der Cloud-Anbindung behauptet; lokale Probe erfolgreich. Die bereits funktionierenden Quellen behalten ihren bisherigen Betrieb.
