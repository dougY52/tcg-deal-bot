# Händlerabdeckung – 03.10.2026

Die aktive Liste wurde von 39 auf **58 Händler** erweitert. 19 neue Quellen
sind aktiviert, ihre Kataloge beziehungsweise Produktseiten wurden live gelesen.
Das ist keine Behauptung, alle Artikel dieser Shops oder den ganzen Markt abzudecken.

| Zusätzlicher Händler | Adapter | Varianten im Test | Quelle |
|---|---|---:|---|
| Brofessor Eich | shopify | 1073 | [Shop](https://brofessoreich.de) |
| CardGames24 | shopify | 387 | [Shop](https://cardgames24.de) |
| GemCards | shopify | 452 | [Shop](https://gemcards.de) |
| LionTCG | shopify | 75 | [Shop](https://liontcg.de) |
| MajinCards | shopify | 52 | [Shop](https://majincards.de) |
| New Era TCG | shopify | 178 | [Shop](https://newera-tcg.shop) |
| Nika Cards | shopify | 497 | [Shop](https://nikacards.de) |
| Pirogamma | shopify | 936 | [Shop](https://pirogamma.cards) |
| PoPa TCG | shopify | 713 | [Shop](https://popatcg.de) |
| Card Knights | shopify | 1338 | [Shop](https://www.card-knights.de) |
| Crazy Cards | shopify | 380 | [Shop](https://www.crazycards.eu) |
| MUCollectibles | shopify | 125 | [Shop](https://www.mucollectibles.de) |
| Pokitrio | shopify | 184 | [Shop](https://www.pokitrio.de) |
| RocketCardStore | shopify | 433 | [Shop](https://www.rocketcardstore.de) |
| Team Lunti | shopify | 270 | [Shop](https://www.teamlunti.de) |
| YONKO TCG | shopify | 973 | [Shop](https://yonko-tcg.de) |
| ZenoCards | shopify | 50 | [Shop](https://zenocards.com) |
| YomiruCards | html_catalog | 2 | [Shop](https://www.yomirucards.com) |
| Sapphire-Cards | woocommerce | 5 | [Shop](https://sapphire-cards.de) |

## Was sich technisch geändert hat

- Vier Händlerhosts können parallel abgefragt werden. Pro Host bleiben die
  Abfragen sequenziell; Robots-Regeln, Abstände, Backoff und das globale Zeitbudget
  bleiben bestehen. Pro Händlergruppe gelten maximal 60 Sekunden für Abrufe.
- Shopify-Kataloge der neuen Shops liefern bis zu 1000 Produkte je Lauf. Varianten
  sind separat gezählt. Erreichte Seitengrenzen erscheinen im Scanbericht.
- Sapphire-Cards: eigener WooCommerce-Parser prüft konkrete Variation, ausgewählte
  Sprache, `is_in_stock`, `is_purchasable`, aktive/sichtbare Variation, Bestellformular
  und `max_qty`. Eine sichtbare generische Schaltfläche genügt nicht.
- YomiruCards: Wix-Produktseiten liefern strukturierte Angebote. Der konkrete
  Produktinfo-Abschnitt ergänzt Inhalte/Boosterzahl, ohne Empfehlungen anderer
  Produkte in die Identität zu mischen. FB04 ist zusätzlich fest beobachtet.
- Gemischt angebotene „Display / Booster“-Produkte werden anhand der gewählten
  Variante geprüft. Der echte 6,99-Euro-Einzelbooster darf nicht als Display oder
  als Display-Vergleichspreis durchrutschen. PSA-/BGS-/CGC-Karten sind keine ETBs.
- Vergangene Release-Daten allein erzeugen keine Preorder-Kandidaten mehr.
  Ein ausdrücklich weiter geltender Preorder-Hinweis bleibt prüfpflichtig.
- Preorder-Prüflimit: 96 Kandidaten/120 Sekunden, mit prioritärer Auswahl und
  weiterhin eigenständiger Preisfreigabe. Das ist keine garantierte Prüfung
  aller Kandidaten in jedem Lauf.

## Tatsächlicher Test und Grenzen

Der Live-Test der zunächst 21 hinzugefügten Quellen dauerte 187 Sekunden. Alle
lieferten Daten. Anschließend wurden zwei für die Vorgaben ungeeignete Kataloge
wieder deaktiviert: JohtoMarket (eigener Webshop nur Zubehör) und Kartenkoloss
(geprüftes Sortiment in unpassenden Sprachen). Sie zählen nicht zu den 58 aktiven
Händlern. Ein Cardmarket-Verkäufer kann ein anderes Sortiment haben als sein Shop.

Card-Knights erreichte seine Katalogseitengrenze. Bei YomiruCards konnten einige
weitere Produktseiten nicht abgerufen werden; FB04 wurde separat direkt bestätigt.
Dunpop lieferte dem Bot beim Test eine leere Antwort. Cardmarket besitzt weiterhin
keinen funktionsfähigen Bot-Adapter. Diese Quellen werden nicht als abgedeckt
behauptet. Bestehende MediaMarkt-/Saturn-/Otto-Probleme sind davon unabhängig.

Die neuen Shopify-Händler wurden anhand ihres abrufbaren Impressums, Ansprechpartners
und ihrer deutschen Anschrift grundlegend geprüft. Die URLs stehen jeweils in
`shops[].trust_evidence`. Keine erfundenen Trustpilot-Bewertungen, Verkaufszahlen
oder Käuferschutz-Zusagen. Eine vollständige Bonitäts-/Fakeshop-Prüfung ist das nicht.

Der Vergleich mit „Anime TCG Retail Watch“ und „FB11 Brightness Watch“ ergab auch:
TCG Garden ist bereits enthalten. Beim dort genannten Naruto-Akatsuki-Angebot steht
auf der geprüften Produktseite keine ausdrückliche Kartensprache. Ein Preisvergleich
oder ein anderer Chat allein ersetzt diesen fehlenden Identitätsnachweis nicht.

Keine bezahlte Such-API, kein neues Konto, keine neue Infrastruktur. Websuche und
öffentliche Händlerverzeichnisse wurden bei dieser Erweiterung zur Recherche genutzt;
der laufende Python-Bot prüft weiterhin die eingerichteten Quellen direkt.

Die normalen Produkt-/Sprach-/200-Euro-Regeln und Meldungs-Deduplizierung bleiben
bestehen. Neue Händler werden getrennt gemeldet. Ungeprüfte Preis-Hinweise im
normalen Deal-Pfad bleiben entsprechend bezeichnet; Preorder-Alerts benötigen
weiterhin ihre strengere Preisfreigabe. Das bestehende Meldelimit begrenzt die
Nachrichten pro Lauf, weitere qualifizierte Angebote folgen nach Deduplizierung.
