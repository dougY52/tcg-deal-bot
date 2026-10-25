# VEDES, Faix und duo: aktive Scanner

Stand: 25.10.2026. Läuft im bestehenden öffentlichen GitHub-Workflow `TCG Cloud Watch`
und dem kostenlosen Cloudflare-Worker `tcg-mms-reader`. Kein eingeschalteter PC,
keine neue kostenpflichtige API und keine Änderung der Discord-Secrets erforderlich.

## Tatsächliche Abdeckung

| Quelle | Was live geprüft wird | Takt / Begrenzung |
|---|---|---|
| VEDES Marktplatz | Konkreter Händler, Produkt-ID, Produktpreis, Artikelbestand, Versand/Reservierung und Händlerimpressum | Bekannte Produkte rotierend im 5-Minuten-Workflow, maximal ein gezielter Check je Lauf; Kataloge separat rotierend |
| Faix | Versandangebot und separat auswählbare Filialbestände in Darmstadt und Riedstadt | Gleiches Verfahren; nur passende Produktarten/Sprachen und qualifizierte Preise werden gemeldet |
| duo | Tatsächlich an den Warenkorb gebundene Händlerofferte, Produkt-ID, Stückzahl, aktueller Preis und Versand nach Deutschland | Ein rotierendes Produkt frühestens alle 90 Minuten; Katalog alle 6 Stunden |

Ein Workflow-Start bedeutet nicht, dass jedes Produkt alle fünf Minuten geprüft wird.
GitHub kann Starts verzögern; Kataloge werden über den vorhandenen Shop-Rotator verteilt.
Weitere Händlerangebote/Produkte werden aus den Katalogen als Kandidaten aufgenommen,
aber erst nach erfolgreicher Live-Prüfung alarmiert. duo ist ausdrücklich kein
vollständiger Fünf-Minuten-Scanner: Cloudflare Free stellt zehn Browser-Minuten pro Tag
bereit und begrenzt Quick Actions auf einen Aufruf pro zehn Sekunden.
Quellen: https://developers.cloudflare.com/browser-run/limits/

## Filialradius und Bedeutung des Bestands

- Mittelpunkt PLZ 65934: 50.1038972 / 8.5756857; 50 km **Luftlinie**, keine Fahrstrecke.
- VEDES erhält die öffentliche Standortauswahl für 65934. Eine Entfernung wird nur
  verwendet, wenn die Produktseite genau diesen Standort bestätigt.
- Faix gibt teilweise Entfernungen zum eigenen Standort zurück. Diese werden ignoriert.
  Für die bestätigten Filialen wird die Entfernung aus überprüften Adresskoordinaten berechnet.
- Live geprüft: Riedstadt (28,5 km) und Darmstadt (26,5 km). Der technische Testartikel
  war ein 2er-Blister; er ist kein automatisch qualifizierendes Angebot.
- MTZ Sulzbach und LOOP5 existieren, ihre Bestandsanbindung ist hier noch nicht bestätigt.
  Weder diese noch sämtliche deutschen Filialen werden als bereits vollständig überwacht ausgegeben.
- Reservierung ist kein abgeschlossener Kauf und keine garantierte Abholbereitschaft.
  Discord nennt die Filiale; der Nutzer muss sie im Shop wählen und deren Bestätigung abwarten.
- Eine zukünftige Warenanlieferung wird nicht aus allgemeinen Öffnungszeiten, Prospekten
  oder einer Abholoption ohne positiven Artikelbestand erfunden.

Filial-/Verfahrensquellen:
https://www.faix.de/faix-online-shop-darmstadt/h/unsere-filialen
https://www.faix.de/faix-online-shop-darmstadt/c/reservieren-und-abholen
Koordinaten: OpenStreetMap / Nominatim, einmalig anhand der öffentlichen Adressen ermittelt
(© OpenStreetMap-Mitwirkende, ODbL; konkrete Objektlinks stehen in `config/config.json`).

## Validierung und Alerts

VEDES/Faix: das einzelne Produktformular muss SKU, Händler-ID, Produkt-UUID und
Bestands-Endpunkt konsistent binden. Der JSON-Status muss dieselbe Variante bestätigen.
Nur positiver Bestand plus die konkrete aktiv angebotene Versand-/Reservierungsoption
und aktiver Warenkorb qualifiziert. Ein `AggregateOffer.lowPrice` wird nie als Kaufpreis verwendet.
Keine Warenkorbbefüllung, Reservierung oder Bestellung wird ausgeführt.

Bei duo wird ausschließlich serialisierter Qwik-Zustand gelesen, kein fremder Code
interpretiert. Nur die zum tatsächlichen Button gehörende `selectedOffer` gilt.
Preis, Produkt-ID und Sprache müssen passen. Eine sichtbare weitere Händlerzeile ist
kein Bestellnachweis. Aktuell ist Carl Otto als Händler geprüft; weitere Händler
bleiben bis zur Prüfung ihrer Daten unbestätigt. Sprache folgt expliziten Produktdaten
oder hinterlegten exakten Produktbelegen, niemals der Sprache der Webseite.

Bestehende Preisregeln, Franchise-/Sprachfilter und Budget bleiben erhalten.
Reale Filialbestände erhalten einen eigenen Alert mit Adresse/Entfernung/Reservierungshinweis.
Versand und Abholung sowie unterschiedliche Filialen besitzen verschiedene Variantenschlüssel.
Der vorhandene persistente State verhindert Doppelmeldungen, erkennt beobachtete Ausverkäufe
und erneute Verfügbarkeit. Ein HTTP-Fehler zählt nicht als Ausverkauf.

## Betrieb und Prüfungen

- `python -m unittest discover -s tests -v`
- `node cloudflare/mms-reader/test.mjs`
- `python -m tcg_bot --check-config`
- `python -m scripts.check_local_retail` mit dem vorhandenen Reader/OIDC: echte
  Händler-/Filialantworten, **niemals Discord-Versand**. Läuft beim Code-Push im
  bestehenden Diagnosejob vor dem normalen Scanner.
- `tests/test_local_retail.py`: falsche Variante, Aggregatpreis, falscher Standort,
  Radiusgrenze, Bestand null, deaktivierter Button, exakte duo-Offerte, Verkäuferprüfung,
  Gratis-Kontingent-Takt, Duplikate, Preiswechsel und echter beobachteter Restock.

Der Worker akzeptiert nur feste öffentliche Lesepfade. Browser-Produktseiten werden
nicht gecacht. Nur robots.txt darf sechs Stunden gecacht werden; Region-Cookies sind
anonyme feste Ortspräferenzen, kurzzeitig pro Worker-Isolat gehalten. Authentifizierung
bleibt auf das vorhandene GitHub-Repository und dessen Main-Workflow beschränkt.
HTTP 429/403 oder Quotenende verursachen interne Fehler/Backoff, keine erfundenen Alerts.
