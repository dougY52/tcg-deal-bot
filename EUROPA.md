# Europa-Erweiterung und Preisorientierung · 18.09.2026

**14 zusätzliche Quellen aktiviert:** zwölf EU-Shopangebote aus Österreich, Belgien, den Niederlanden und Spanien sowie Japan2UK und Poke Swiss als Importquellen. Insgesamt 44 konfigurierte Quellen. Markt-/Shopregion ist nicht zwingend der juristische Unternehmenssitz; insbesondere die AT-Webseite von CardStore ist keine Zusage eines österreichischen Versandlagers.

Die Recherche prüfte 115 europäische Händleradressen plus Universe TCG und The Dragoncard. 17 der 115 lieferten technisch lesbare Shopify-Kataloge. Universe TCG wurde anschließend ergänzt. Auslesbarkeit allein genügte nicht zur Aktivierung: Versand nach Deutschland musste durch Händlerbedingungen bzw. expliziten Europaversand zusammen mit Deutschland im Ländermenü belegt sein. Keine Checkout-Bestellung wurde ausgelöst. Einzelne Produkte können zusätzliche Versandbeschränkungen haben.

[GitHub-Katalogprüfung einschließlich gezielter englischer Kategorien](https://github.com/dougY52/tcg-deal-bot/actions/runs/35341984209): erfolgreich. Alle 14 neuen Quellen lesbar; zusätzlich die zuvor ergänzten 20. [Vollständiger Scan vor Ergänzung der vier englischen UK-Kategorien](https://github.com/dougY52/tcg-deal-bot/actions/runs/35341782328): 150 Sekunden, bekannte MediaMarkt-/Saturn-Fehler bleiben sichtbar. 65 automatisierte Tests bestanden.

## Neue Quellen und Versandbelege

| Shop/Markt | Währung | Händlerangabe zum Versand nach Deutschland |
|---|---|---|
| [Geekie (BE)](https://geekie.be) | EUR | Versand nach Deutschland laut Händler: 9 EUR. [Beleg](https://geekie.be/policies/shipping-policy) |
| [OutpostBrussels (BE)](https://outpostbrussels.be) | EUR | Deutschland: 10 EUR Versand; ab 190 EUR Warenwert laut Händler kostenlos. [Beleg](https://outpostbrussels.be/policies/shipping-policy) |
| [Bescards (NL)](https://www.bescards.com) | EUR | Versand nach Europa; Deutschland im Ländermenü. Versandkosten im Checkout. [Beleg](https://www.bescards.com/policies/shipping-policy) |
| [CardStore (NL)](https://cardstore.nl) | EUR | Deutschland: 12,99 EUR Standardversand; Versand separater Artikel kann abweichen. [Beleg](https://cardstore.nl/pages/verzenden) |
| [Lairos.Shop (AT)](https://lairos.shop) | EUR | Deutschland: 10,90 EUR Versand; ab 60 EUR Warenwert 6,90 EUR. [Beleg](https://lairos.shop/policies/shipping-policy) |
| [CardStore (AT)](https://cardstore.at) | EUR | Deutschlandversand bestätigt; unterschiedliche Sprachseiten nennen abweichende Kosten. Endpreis im Checkout prüfen. [Beleg](https://cardstore.at/pages/versand-details) |
| [S-Games (AT)](https://s-games.at) | EUR | Deutschland: je nach Warenwert 6,50 / 5,50 / 3,50 EUR; über 250,01 EUR frei. [Beleg](https://s-games.at/policies/shipping-policy) |
| [PrimeProtector (AT)](https://primeprotector.at) | EUR | Deutschland: Standardversand laut Händler 5,90 EUR; Checkout prüfen. [Beleg](https://primeprotector.at/policies/shipping-policy) |
| [Merchfox (AT)](https://www.merchfox.at) | EUR | Versand nach Europa; Deutschland im Ländermenü. Produktabhängige Versandkosten im Checkout. [Beleg](https://www.merchfox.at/policies/shipping-policy) |
| [Coso5 (AT)](https://www.coso5.at) | EUR | Deutschland: 16 EUR Versand bis 510 EUR Warenwert, darüber 25,90 EUR. [Beleg](https://www.coso5.at/policies/shipping-policy) |
| [Japan2UK (GB)](https://www.japan2uk.com) | GBP | Versand aus UK nach Deutschland; laut Händler DDP. Porto im Checkout, ab 500 GBP laut Händler frei. EUR-Endpreis nicht berechnet. [Beleg](https://www.japan2uk.com/policies/shipping-policy) |
| [Poke Swiss (CH)](https://poke-swiss.ch) | CHF | Versand aus Genf nach Europa; Deutschland im Ländermenü. Versand und mögliche Importabgaben zusätzlich. [Beleg](https://poke-swiss.ch/policies/shipping-policy) |
| [Pokeflip (BE)](https://pokeflip.com) | EUR | Deutschland: 6,95 EUR Versand laut Händlertabelle. [Beleg](https://pokeflip.com/policies/shipping-policy) |
| [Universe TCG (ES)](https://www.universetcg.com) | EUR | Versand aus Barcelona in die EU; Versand und endgültige Steuerberechnung im Checkout. [Beleg](https://www.universetcg.com/policies/shipping-policy) |

Alle aktivierten Kataloge laufen im bestehenden Fünf-Minuten-Zeitplan. Die neuen Quellen sind auf die erste Katalogseite (maximal 250 Produkte) begrenzt. Japan2UK erhält zusätzlich vier gezielte Kategorien: Pokémon, One Piece, Dragon Ball und Digimon, jeweils englische Booster-Displays. Die Suche ist damit international erweitert, aber nicht vollständig für alle EU-Länder oder alle Shopprodukte. Blockierte Händler und Filialbestände sind unverändert offen. GitHub kann Starts verzögern.

## Meldungen und Importpreise

- Nur ausdrücklich bestellbare DE-/EN-Produkte; bestellbare Vorbestellungen als solche gekennzeichnet. Französisch, Italienisch, Spanisch usw. bleiben ausgeschlossen. Neue Schutzregeln verhindern, dass das französische Wort „de“ als deutscher Sprachcode erkannt wird. Zubehör wie Acrylcases und Deck-Displays wird ebenfalls verworfen.
- EU-Angebote können einen bestätigten Retail-Alarm auslösen, wenn eine genaue Euro-Preisreferenz passt. Versandkosten werden als Händlerhinweis angezeigt; der Bot summiert sie nicht automatisch zum Warenpreis. Mehrwertsteuer-/Versand-Anpassungen im Checkout sind möglich.
- Japan2UK und Poke Swiss senden nur gekennzeichnete ungeprüfte Entdeckungen. GBP bleibt GBP, CHF bleibt CHF. Keine Gleichsetzung mit Euro, keine automatische Freigabe als EU-Retail-Schnäppchen. Bei Japan2UK behauptet die Versandrichtlinie DDP für Deutschland; der Bot prüft den Endpreis nicht durch eine Bestellung.
- Keine kostenpflichtigen Wechselkurs- oder Suchdienste. Es gibt aktuell keine automatische Wechselkurs-, Zoll- oder Import-Endpreisrechnung.
- Entdeckungsmeldungen bleiben auf zehn je Lauf begrenzt, einmal je Händler/Variante. Neu aufgenommene Shops können auch ältere erstmals beobachtete Produkte melden.

## Konkrete Preisarbeit

Drei zusätzliche feste Euro-Referenzen, insgesamt jetzt **13**:

| Produkt | Sprache / Inhalt | Referenz |
|---|---|---:|
| Digimon Timeless Bonds BT-26 | EN / 24 Booster | 89,95 EUR (CardBuddys; weitere Händlerbindung PrimeProtector) |
| Yu-Gi-Oh! Battles of Legend: Glorious Gallery | DE / 24 Booster | 64,90 EUR (PrimeProtector) |
| Yu-Gi-Oh! Battles of Legend: Glorious Gallery | EN / 24 Booster | 64,90 EUR (PrimeProtector) |

Das sind am 18.09.2026 dokumentierte Händlerpreise, keine behaupteten Original-Releasepreise oder Hersteller-UVPs. Die Referenz steigt nicht automatisch mit höheren Händlerpreisen. Exakte Produkt-/Variantenbindungen und Belege stehen in config.json. Auch ausverkaufte Produkte werden durch eine Referenz niemals bestellbar gerechnet.

Zusätzlich **fünf offizielle Dollar-Orientierungen**, gültig bis 17.12.2026:

- [dbs-fb09-usd](https://www.dbs-cardgame.com/fw/en/products/02_230.html): 4.99 USD je Booster.
- [dbs-fb10-usd](https://www.dbs-cardgame.com/fw/en/products/01_400.html): 4.99 USD je Booster.
- [dbs-fb11-usd](https://www.dbs-cardgame.com/fw/en/products/01_422.html): 4.99 USD je Booster.
- [digimon-bt26-usd](https://world.digimoncard.com/products/pack/ver26/): 4.99 USD je Booster.
- [onepiece-op16-usd](https://en.onepiece-cardgame.com/products/op16.html): 4.99 USD je Booster.

Die Dollarangabe erscheint bei passenden englischen Angeboten als „US-UVP zur Orientierung“, mit Herstellerlink. Für Digimon BT-26 bestätigt der Hersteller 24 Booster je Box: 24 × 4,99 = 119,76 USD wird ausdrücklich als Hochrechnung und nicht als offizielle Display-UVP bezeichnet. Für die anderen vier Quellen wird nur der belegte Boosterpreis angezeigt. US-Angaben werden nicht automatisch in eine Euro-Retailgrenze umgewandelt. Es gibt noch keine Preisreferenz für jedes Produkt oder jede Reihe.

## Weitere geprüfte Kandidaten

Pokecard Store und Pokecard.ch begrenzen den Versand laut veröffentlichten Bedingungen auf Schweiz/Liechtenstein und wurden nicht aktiviert. Double Sleeved und Total Cards haben lesbare Kataloge; ein für dieses Setup hinreichend konkreter Deutschlandversand wurde nicht bestätigt. Torena blieb ohne bestätigte Versandbedingungen. The Dragoncard wurde ergänzend technisch geprüft, aber ebenfalls nicht aktiviert. Nicht angeschlossene französische, polnische, italienische, spanische und nordische Kandidaten stehen mit technischen Abrufstatus in [europe-audit.json](config/europe-audit.json). Ein fehlgeschlagener Abruf bedeutet nicht, dass der Händler geschlossen ist.
