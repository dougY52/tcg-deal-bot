# Händlerabdeckung · Version 2 · 18.09.2026

„Angeschlossen“ bedeutet nicht „jedes Produkt wird gemeldet“. Angebote benötigen weiterhin eine bestätigte Identität, passende Sprache, feste Preisreferenz, einen zugelassenen Verkäufer und bestätigten Onlinebestand. Es gibt keine vollständige Internet- oder Deutschland-Filialabdeckung.

## Angeschlossene Quellen

| Quelle | Tatsächlich implementiert | Automatische Deal-Meldungen |
|---|---|---|
| KartenZeche | Shopify-Katalog und genaue Produktseiten | Bei passender Preisreferenz |
| CardBuddys | Shopify-Katalog und genaue Produktseiten | Bei passender Preisreferenz |
| CardCosmos | Begrenzter Shopify-Katalog und genaue Produktseiten | Bei passender Preisreferenz |
| Skash Cards | Shopify-Katalog und genaue Produktseiten | Bei passender Preisreferenz |
| CrispyCards | Begrenzter Shopify-Katalog und genaue Produktseiten | Bei passender Preisreferenz |
| **MediaMarkt** | Pokémon-Kategorie plus Neuheiten, ETBs, Tins, Geschenkideen; bis 16 rotierende Produktseiten je Stunde plus genaue Beobachtungen | Eigenverkauf mit bestätigtem Onlinebestand; fremde Verkäufer erst nach ausdrücklicher Aufnahme in die Händlerliste |
| **Saturn** | Pokémon-Neuheiten, ETBs, Tins, Geschenkideen; bis 16 rotierende Produktseiten je Stunde plus genaue Beobachtungen | Wie MediaMarkt |
| **Otto** | Öffentliche Pokémon-Angebotsliste; genaue Variantenpreise ohne Ab-Preise und ohne Verwechslung mit Monatsraten | **Nur Prüfkandidaten.** Verkäuferdaten fehlen in der geprüften Listenantwort; getestete Produktseiten antworten mit HTTP 400 |
| **Gate to the Games** | Fünf Kategorien für Pokémon, Digimon, Naruto, One Piece und Weiß Schwarz; strukturierte Preise; explizite Produktseiten liefern Bestand | Bestätigte Einzelproduktangebote mit passender Referenz; Kategoriepreise ohne Bestand bleiben Kandidaten |
| **Ultra Comix** | Konkrete Fairy-Tail-100-Years-Quest-Display-Seite | Als Restock-Ziel; kein vollständiger Shopkatalog |

Die Großhandelsketten werden zunächst für ihre verifizierten Pokémon-Seiten abgefragt. Weitere Anime-Reihen werden bei den entsprechenden Fachhändlern entdeckt; es gibt keine Behauptung, jede Reihe in jeder Großhandelskette vollständig durchsuchen zu können.

Zehn feste Produkt-/Sprachregeln mit 16 konkreten Händlerbindungen sind vorbereitet. Neu: Pokémon Reisegefährten Top-Trainer-Box DE bei MediaMarkt/Saturn und Fairy Tail 100 Years Quest 12er-Display EN bei Gate to the Games/Ultra Comix. Die exakten Referenzen und URLs stehen in `config/config.json`.

Zusätzlich können freigegebene Referenzen mit geprüften GTIN/EAN-Codes händlerübergreifend zugeordnet werden. Die Prüfziffer wird validiert; vorangestellte Nullen werden normalisiert. Titel, Sprache, Zustand, Verkäufer und Preis bleiben zusätzliche Sperren. Ein gleicher Serienname allein genügt nicht. Mehrdeutige Zuordnungen werden verworfen. Vorbestellungen und unbekannte Bestände lösen keinen Dealalarm aus.

## Geprüft, aber nicht automatisch angebunden

| Quelle | Tatsächliches Ergebnis |
|---|---|
| **Cardmarket** | Direkter Abruf HTTP 403; laut offizieller Hilfe werden derzeit keine neuen API-Anträge angenommen. Keine aktive Verkäufer-, Preis- oder Bestandsüberwachung. Marktpreise wären außerdem keine Hersteller-UVP. |
| **Müller** | Bereits der direkte robots.txt-Abruf antwortet mit HTTP 403. Keine aktive Online- oder Filialüberwachung. |
| **Smyths Toys** | Öffentliche Kategorie ist per Websuche sichtbar; einfacher Abruf und separater Chromium-Test antworten mit HTTP 403. Keine aktive Überwachung. |
| **Kaufland Marketplace** | Direkter Abruf HTTP 403. Keine aktive Überwachung. |
| **Rossmann** | Einfacher Abruf: Client Challenge. Browserprüfung: Amigo-Katalog lesbar, gefundene Pokémon-Kalender online nicht verfügbar. Frühere Bisaflor-Produktseite nicht gefunden. Noch kein geprüfter Filialbestandsadapter. |
| FantasyWelt | Kategorie HTTP 403. |
| Games Island | Hauptseite liefert keine Produktangebote; separat verlinkter maschineller Feed sperrt Crawler in robots.txt. |
| Galaxus | Suchseite wird durch robots.txt gesperrt; kein geprüfter alternativer TCG-Katalogadapter. |
| ROFU | Getesteter Pokémon-Kategoriepfad nicht vorhanden; kein verifizierter Adapter. |
| idee+spiel | Getesteter Suchpfad HTTP 404; kein verifizierter Adapter. |

Diese Quellen stehen sichtbar unter `unavailable_sources` und im Laufbericht. Sie werden **nicht** nur zum Erhöhen einer Händlerzahl als aktiv gezählt. Die Ergebnisse gelten für diese Testumgebung; GitHub kann ebenfalls blockiert werden oder andere Ergebnisse liefern. Es gibt keine CAPTCHA-Umgehung, Browser-Tarnung, Proxy-Rotation oder versteckte kostenpflichtige API. Andere Händler lassen sich später über zusätzliche Adapter ergänzen; „alle Onlineshops“ ist technisch kein endlich abgrenzbarer Katalog.

Cardmarket: [offizieller API-Zugangsstatus](https://help.cardmarket.com/de/cardmarket-api).

## Filialbestände: noch offen

**Der Bot meldet momentan keine automatischen Filialbestände.** Die vom Nutzer bestätigte Suchregion ist **65934 mit 50 km Umkreis**. Eine erfolgreich geprüfte Quelle für konkrete Marktbestände fehlt weiterhin. Als Umkreis ist zunächst Luftlinie vorgesehen; die tatsächliche Entfernungsfilterung ist noch nicht implementiert.

MediaMarkt/Saturn stellen auf ihren Seiten allgemeine Abholinformationen bereit. Ein Test mit einer echten Markt-ID im Produktlink lieferte trotzdem `storeId: null`. Daher bleibt der Bestand „Filiale nicht ausgewählt/ungeprüft“, auch wenn `isProductPickable` wahr ist. Das ist keine Bestätigung, dass der Artikel in Essen oder irgendeiner anderen konkreten Filiale liegt. Die genutzte Testfiliale war lediglich ein technischer Test und wurde nicht als Standortpräferenz gespeichert.

Die Konfiguration enthält `local_stores` mit `enabled: false`, `postal_code: "65934"`, `radius_km: 50` und noch leeren Filialen. Das ist eine sichtbare offene Anforderung, **kein bereits funktionsfähiger Adapter**, den man einfach einschalten könnte. Die Region ist festgelegt; für den nächsten Schritt bleibt eine nachvollziehbare, lesbare Filialbestandsquelle erforderlich. Müller/Smyths/Rossmann bleiben zusätzlich durch die oben beschriebenen Zugriffsprobleme begrenzt.

## Erweiterung

- `shopify`: öffentlicher Shopify-Katalog, genaue Varianten.
- `mms`: öffentliche Seiten von MediaMarkt/Saturn, deren eingebettete Daten Produkt, Händler, Preis und Onlinebestand getrennt ausweisen.
- `otto`: konkrete Varianten aus öffentlicher Angebotsliste, derzeit bewusst nur Kandidaten.
- `html_catalog`: JSON-LD und schema.org-Microdata aus Kategorien/Produktseiten; fehlende Bestandsdaten bleiben unbekannt.

Für Nicht-Shopify-Quellen verwenden Referenzbindungen zusätzlich `url`. `handle` ist die stabile URL-Kennung aus dem Laufbericht; `variant_id` darf auch alphanumerisch sein. Mit `product_kind` können exakt geprüfte ETBs, Bundles, Tins, Kollektionen oder Booster freigegeben werden. Ungeprüfte andere Produkttypen erzeugen weiterhin keinen Dealalarm. Echte neue Filialadapter müssen Onlinebestand und Filialbestand getrennt führen und eine konkrete Filial-ID in der Antwort bestätigen.

## Regionale Anlaufstellen für die weitere Anbindung

Die offiziellen Filialseiten bestätigen folgende Standorte im Frankfurter Stadtgebiet. Das sind Rechercheziele, keine bestätigten TCG-Bestände und keine vollständige Liste aller Märkte im 50-km-Radius.

- [MediaMarkt Frankfurt-Nordwestzentrum](https://www.mediamarkt.de/de/store/frankfurt-nordwestzentrum-447)
- [Smyths Toys Frankfurt am Main, Nordwestzentrum](https://www.smythstoys.com/de/de-de/storefinder/storedetails/frankfurt-am-main)
- [MediaMarkt-Standortübersicht Frankfurt mit Main-Taunus-Zentrum](https://www.mediamarkt.de/de/store/region-frankfurt-main)

## Browserprüfung am 18.09.2026

MediaMarkt und Saturn: echte Produktseiten und Kataloge im isolierten Chromium ohne Anmeldung lesbar. Die geprüfte KP09-Box wurde jeweils mit 59,99 EUR, Eigenverkauf und **nicht lieferbar** ausgelesen. Browseradapter implementiert; GitHub-Prüfung separat im Workflow.

LimitedMarket: konkrete Jubiläums-ETB-Seite zeigt auch im Browser eine Cloudflare-Sicherheitsprüfung (HTTP 403). Nicht aktiviert. Rossmann: lesbarer Katalog ist noch keine verifizierte lokale Bestandsabfrage. Der bisherige Umkreis 65934 / 50 km bleibt unverändert und noch ohne funktionierenden Filialadapter.

Seit Version 2.3 gibt es zusätzlich einmalige Meldungen für neue bestellbare DE/EN-Displays ohne Preisreferenz, einschließlich markierter Vorbestellungen. Diese sind ausdrücklich keine Deal-Empfehlungen.

### Ergebnis des GitHub-Browsertests

[Browser source check](https://github.com/dougY52/tcg-deal-bot/actions/runs/35339357663): Installation und 60 Tests erfolgreich; MediaMarkt und Saturn jeweils **Browser HTTP 403**. Deshalb wird Browserbetrieb im regulären Workflow nur nach ausdrücklicher Aktivierung über die Repository-Variable TCG_BROWSER=1 installiert/benutzt. Kein Erfolg der Cloud-Anbindung behauptet; lokale Probe erfolgreich. Die bereits funktionierenden Quellen behalten ihren bisherigen Betrieb.
