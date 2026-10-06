# Übernahme: Erweitere Anime-TCG-Deal-Bot

Stand: 06.10.2026. Quellchat: `01a0b489-9b2e-74f3-ad72-05ec903387cc`, Titel **Erweitere Anime-TCG-Deal-Bot**. Zentrale Regeln: [TCG-WATCH.md](TCG-WATCH.md).

## Umfang und Nachweisgrenze

Beide verfügbaren Verlaufsseiten bis `hasMore=false` gelesen: **11 Gesprächsrunden, 12 Nutzernachrichten, 83 Shell-Ausführungen** im bereitgestellten Verlauf. Die enthaltenen Gesprächsrunden stammen vom 18.09.2026. Anforderungen, spätere Korrekturen, Quellen, Codearbeiten, Tests, Laufbelege und offene Grenzen sind hier zusammengeführt. Technische Ausgaben wurden nach Themen ausgewertet; dies ist keine wortgetreue Rohkopie.

Eine umfangreiche Kandidatenausgabe (`exec-ea81e44e-ff21-4336-9c55-9414e8d4e62c`) ist vom Lesewerkzeug auf 20.000 Zeichen gekürzt. Die damaligen lokalen Dateien/ZIPs konnten heute wegen nicht startbarer lokaler Shell nicht erneut geöffnet werden. Daher keine Behauptung einer vollständigen Datei-/Log-Sicherung. Der Quellchat bleibt als Nachweis erhalten. Zugangsdaten und private Laufzeitdateien werden nicht übernommen.

Abgleich mit dem tatsächlichen GitHub-Stand `44989188d7f5b3571a9b984e5c578808ad0cfd9a`: `config/config.json`, `tcg_bot/market.py`, `tcg_bot/preorders.py` und bisherigem zentralen Regelblatt. Die Übernahme ändert nur Dokumentation, keine Versand- oder Preislogik und keinen Zeitplan.

## Wesentliche zusätzliche Nutzerentscheidungen

Die Reihenfolge im alten Chat ist entscheidend:

1. Ausgangspunkt: keine offensichtlichen Scalperpreise, möglichst nahe belegter UVP bzw. regulärem Handelspreis. Ein Rabatt gegen künstlich überhöhte Preise reicht nicht.
2. Zunächst wurde eine starre Normalpreisgrenze umgesetzt; danach 5 % UVP-Aufschlag vorgeschlagen.
3. Der Nutzer präzisierte: **80 Euro statt normalerweise 70 Euro sind akzeptabel.** Darauf folgte eine Zustimmung zu Bewertungen und zunächst 15 % Toleranz.
4. **Spätere ausdrückliche Präzisierung:** „20–30€ mehr als uvp sollten trotzdem angezeigt werden, aber mit bewertung“. Umgesetzt wurde damals **Normalpreis/UVP + maximal 30 Euro**, auch ohne Restock.
5. Ein höherer Preis muss als erhöht bzw. „kein Schnäppchen“ benannt werden. Niemals durch einen hohen Marktmedian schönrechnen.
6. Digimon und Yu-Gi-Oh ausdrücklich ausschließen.
7. Damals: alle zehn Minuten Angebote, Bestandswechsel und neue Produkte prüfen; nicht nur alte Produkt-URLs.
8. Wiederholte Beschwerden über Stille sind Teil des Ziels: Ablehnungsgründe untersuchen und Identitäts-/Referenzfehler beheben; eine hohe Zahl gelesener Varianten ist kein Nachweis sinnvoller Treffer.

**Einordnung in den neueren Gesamtauftrag:** Der +30-Euro-Wunsch erklärt die gewünschte Preisorientierung; er ist keine universelle neue Discord-Freigabe. Tagesübersicht zeigt auch normale/erhöhte bestätigte Preise mit Einordnung. Discord bleibt nach der jüngeren Zusammenführung auf ausgewählte interessante, live geprüfte Treffer beschränkt. 200-Euro-Artikelgrenze, aktuelle Sprach-/Sortimentsregeln und gesonderte Preorder-Regeln gelten weiter. Die frühere 5-Prozent-Empfehlung und „nur bei Restock“-Beschränkung sind nicht die letzte Entscheidung dieses Quellchats.

## Preisbewertungen und aktuelle Umsetzung

| Bewertung | Historische Regel und beabsichtigte Aussage |
|---|---|
| 🔥 Sehr guter Preis | Mindestens 15 % und 8 Euro unter konservativer Vergleichsbasis |
| 🟢 Guter / fairer Preis | Auf oder unter Vergleichsbasis |
| 🟡 Noch okay | Höchstens 15 % über Basis und innerhalb absoluter Preisgrenze; kein Schnäppchen |
| 🟠 Erhöhter Preis – kein Schnäppchen | Mehr als 15 % Aufschlag, höchstens 30 Euro über belegtem Normalpreis/UVP |
| 🔴 Über deinem Preisrahmen | Mehr als 30 Euro über belegtem Normalpreis; damaliger Discord-Ausschluss |
| ⚪ Nicht sicher bewertbar | Referenz/Marktdaten fehlen; inzwischen in Tagesübersicht zulässig, keine erfundene UVP |

Die Basis für Bewertungen war der kleinere Wert aus geprüftem Normalpreis und bereinigtem Marktmedian. Die absolute +30-Euro-Grenze bezieht sich auf den belegten Normalpreis. Beispiel: Normalpreis 70 Euro, Angebot 90 oder 100 Euro = orange; 100,01 Euro außerhalb dieses Rahmens. Hoher Marktmedian macht daraus keinen grünen Deal. Es handelt sich um nachvollziehbare Regeln, keine persönliche KI-Liveprüfung jedes Angebots.

**Heute im Repository bereits vorhanden:** `market.near_retail_tolerance_pct=15`, `max_premium_eur=30`, `notify_within_price_range=true`, Bewertungsfunktion/Labels in `market.py`. Auch `notify_all_shops=true`, `allow_verified_without_comparisons=true` und Preis-Kontext-Funktionen sind neuere Erweiterungen. Sie dürfen nicht durch alte Dateien überschrieben werden.

**Wichtige offene Differenz:** Der schnelle Prüfpfad verwendet `preorders.price_check`. Dort gelten eigene Referenz-, MSRP- und Medianbedingungen; `market.max_premium_eur` wird dort nicht pauschal angewandt. Ein gespeicherter +30-Euro-Konfigurationswert beweist deshalb nicht, dass der Fast Watch solche Preise meldet. Bei weiterer Fehlersuche den tatsächlich verwendeten Pfad und dessen Ablehnungsgrund betrachten. Eine eventuelle Vereinheitlichung muss Tagespreisinfo, gutes Angebot und erhöhte Preise bewusst unterscheiden und Regressionstests erhalten.

## Produktidentität: entscheidende damalige Reparatur

Der Bot hatte dasselbe Naruto-Produkt wegen verschiedener Namen getrennt. Dadurch fehlten Vergleichshändler und gute Angebote blieben unsichtbar.

- `Konoha Shido`, `Konoha Shidō`, `First Set`, `1st Set` können nach geprüftem Alias dasselbe **Naruto Mythos Set** sein.
- **Set 1 ist nicht automatisch First Edition.** Beispielsweise „First Set 2nd Edition“ gehört zur zweiten Edition des ersten Sets.
- Setname, Spielsystem, Edition, Sprache, Packmenge und Sonderausführung sind separate Identitätsmerkmale.
- First und Second Edition sowie Mythos/Weiss Schwarz/andere Systeme niemals vermischen.
- Akzente normalisieren; Editionswörter nicht zusätzlich in den Setnamen aufnehmen.
- Explizite „18er Display“-/„36er Display“-Formate erkennen; Setcodes wie BT-015/B15/BT15 korrekt kanonisieren, ohne Setnummer als Boosterzahl zu lesen.
- Shinobi Shiren erhielt einen eigenen Alias. Chaos Rising und Pitch Black waren historische Pokemon-Aliase, keine Freigabe englischer Pokemon-Produkte.
- Produktseiten-/Variantendaten schlagen irreführende URL-Slugs. Historisches Beispiel: CardBuddys-Naruto-Produkt unter einem „mega-evolution-pitch-black…kopie“-Slug.
- `migrate_alias_identities` übernimmt alte `market_history`- und `market_sent`-Identitäten auf den geprüften Alias und bewahrt die jüngste Versandhistorie, statt durch Umbenennung Doppelmeldungen zu erzeugen.
- Mindestanzahl damals von **drei anderen Händlern** auf **zwei andere Händler** gesenkt: drei unabhängige Händler einschließlich Kandidat. Geprüfter Preisanker und Confidence mindestens 0,90 blieben damalige Voraussetzungen. Neuere gültige Referenzwege ohne Vergleichshändler nicht zurückbauen.

Aliasnormalisierung, Migration, Packzahlerkennung und `min_comparisons=2` sind heute vorhanden. Der Fast-Watch-Vergleich besitzt daneben eigene Produktschlüssel/Referenzbindungen; bei Problemen beide Identitätswege prüfen.

Herstellerhinweis als historischer Editionsbeleg:
https://www.narutomythos.com/en/community/updates-about-1st-set-2nd-edition-af7d468c

## Historische konkrete Funde und Referenzen

Alle folgenden Werte stammen aus dem alten Verlauf vom **18.09.2026**, nicht aus einer heutigen Shopabfrage.

| Produkt / Quelle | Damaliger Befund | Verwendung heute |
|---|---|---|
| Masters B15 Saiyan Showdown, Play-Maniac, EN 24 Booster | 83,99 Euro, ausverkauft, Verpackungsunperfektionen möglich | Kein damaliger verfügbarer Deal; Zustand und Checkout neu prüfen |
| B15, Comic Attack | 79,99 Euro, im Quellverlauf neu/OVP und verfügbar | Beobachteter Händlerpreis, keine Hersteller-UVP |
| B15, Cardmarket | Ab 59,99 Euro, 30-Tage-Wert 60,82, Trend 67,19 | Historischer Kontext, niemals aktueller Retail-/Bestandsbeweis |
| Naruto First Set/Konoha Shido, 2nd Edition EN 24 | CardCosmos 69,90 Euro | Datierter Normalpreisanker, keine UVP |
| Dasselbe Naruto-Display, CardLegends | 54,99 Euro; Vergleich AdventureCardz 79,99 / CardBuddys 79,95 / CardCosmos 69,90 / Play-Maniac 84,99 | Historisch tatsächlich gemeldet, etwa 21,3 % unter damaliger Basis |
| Fusion World FB03 EN 24, Play-Maniac | 83,99 Euro, als orange/elevated bewertet; Vergleich AdventureCardz 99,99 / CrispyCards 89,99 | Historisch tatsächlich gemeldet; alte 59,99-Euro-Basis ist inzwischen im zentralen Bot korrigiert |
| Naruto Shinobi Shiren Set 2 First EN 24 | KartenZeche/Skash/CrispyCards; Referenz 89,99 Euro | Konkrete Variantenbindung erhalten; damaligen generellen Preorder-Ausschluss nicht übernehmen |
| Digimon BT04 Great Legend | Damaliger Test-/Laufkandidat 44,90 Euro | Ausschließlich Historie, ausdrücklich nicht mehr im Sortiment |

Quellen zur erneuten Prüfung:
- https://www.play-maniac.de/products/dragon-ball-super-card-game-saiyan-showdown-b15-booster-display-24-packs-englisch?variant=42059417387232
- https://comic-attack.de/produkt/dragon-ball-super-card-game-b15-saiyan-showdown-booster-box/
- https://cardcosmos.de/products/naruto-mythos-tcg-konoha-shido-booster-display-2-edition-englisch?variant=52855856791895
- https://cardlegends.de/products/naruto-mythos-tcg-first-set-2nd-edition-display-en?variant=54159545303373
- https://adventurecardz.de/products/naruto-mythos-tcg-first-set-2nd-edition-display-en?variant=53148061270283
- https://cardbuddys.de/products/mega-evolution-pitch-black-booster-display-en-kopie?variant=57912723669323
- https://www.play-maniac.de/products/naruto-mythos-tcg-first-set-2nd-edition-display-24-booster-englisch?variant=57948731801864
- https://www.play-maniac.de/products/dragon-ball-super-card-game-fusion-world-fb03-raging-roar-booster-display-24-packs-englisch?variant=45109502738696
- https://adventurecardz.de/products/dragon-ball-super-card-game-fusion-world-raging-roar-en?variant=45711719858443
- https://crispycards.de/products/dragonball-super-fb03-fusion-world-raging-roar-display-eng?variant=61016967184714

## Vollständiger Händlerbestand dieser lokalen Entwicklungsstufe

Diese 33 Einträge sind historisch dokumentiert und wurden mit der heutigen Konfiguration abgeglichen. CardsRfun, CardLegends und Comic Attack waren damalige Ergänzungen. „Konfiguriert“ bestätigt weder einen erfolgreichen heutigen Abruf noch vollständige Abdeckung.

| Händler | ID | Basis-URL | Heutiger Konfigurationsstatus |
|---|---|---|---|
| KartenZeche | kartenzeche | https://kartenzeche.de | konfiguriert, Erreichbarkeit separat prüfen |
| CardBuddys | cardbuddys | https://cardbuddys.de | konfiguriert, Erreichbarkeit separat prüfen |
| CardCosmos | cardcosmos | https://cardcosmos.de | konfiguriert, Erreichbarkeit separat prüfen |
| Skash Cards | skashcards | https://skashcards.com | konfiguriert, Erreichbarkeit separat prüfen |
| CrispyCards | crispycards | https://crispycards.de | konfiguriert, Erreichbarkeit separat prüfen |
| MediaMarkt | mediamarkt | https://www.mediamarkt.de | konfiguriert, Erreichbarkeit separat prüfen |
| Saturn | saturn | https://www.saturn.de | konfiguriert, Erreichbarkeit separat prüfen |
| OTTO | otto | https://www.otto.de | konfiguriert, Erreichbarkeit separat prüfen |
| Gate to the Games | gate | https://www.gate-to-the-games.de | konfiguriert, Erreichbarkeit separat prüfen |
| Ultra Comix | ultracomix | https://shop.ultracomix.de | deaktiviert |
| TCGViert | tcgviert | https://tcgviert.com | konfiguriert, Erreichbarkeit separat prüfen |
| Webbas-Kartenecke | webbas-kartenecke | https://webbas-kartenecke.de | konfiguriert, Erreichbarkeit separat prüfen |
| Celestial-Gameshop | celestial-gameshop | https://www.celestial-gameshop.de | konfiguriert, Erreichbarkeit separat prüfen |
| Pokeminati | pokeminati | https://pokeminati.de | konfiguriert, Erreichbarkeit separat prüfen |
| GeeksHeaven | geeksheaven | https://geeksheaven.de | konfiguriert, Erreichbarkeit separat prüfen |
| Card-Collector | card-collector | https://card-collector.net | konfiguriert, Erreichbarkeit separat prüfen |
| PushDich | pushdich | https://www.pushdich-tcg.de | konfiguriert, Erreichbarkeit separat prüfen |
| VanessasTCG-Shop | vanessastcg-shop | https://vanessastcg-shop.myshopify.com | konfiguriert, Erreichbarkeit separat prüfen |
| MoCards | mocards | https://mocards.de | konfiguriert, Erreichbarkeit separat prüfen |
| Crocus-Cards | crocus-cards | https://crocus-cards.de | konfiguriert, Erreichbarkeit separat prüfen |
| Play-Maniac | play-maniac | https://www.play-maniac.de | konfiguriert, Erreichbarkeit separat prüfen |
| Kartenschatz | kartenschatz | https://kartenschatz.de | konfiguriert, Erreichbarkeit separat prüfen |
| Cards-Uniques | cards-uniques | https://www.cards-uniques.de | konfiguriert, Erreichbarkeit separat prüfen |
| AdventureCardz | adventurecardz | https://adventurecardz.de | konfiguriert, Erreichbarkeit separat prüfen |
| Tenkaichi | tenkaichi | https://tenkaichi.de | konfiguriert, Erreichbarkeit separat prüfen |
| Card-Centre | card-centre | https://card-centre.de | konfiguriert, Erreichbarkeit separat prüfen |
| Toy-Treasure | toy-treasure | https://toy-treasure.com | konfiguriert, Erreichbarkeit separat prüfen |
| Battle-Bear | battle-bear | https://www.battle-bear.de | konfiguriert, Erreichbarkeit separat prüfen |
| Variety Cards | variety-cards | https://variety-cards.de | konfiguriert, Erreichbarkeit separat prüfen |
| OpasLaden | opasladen | https://opasladen.de | konfiguriert, Erreichbarkeit separat prüfen |
| CardsRfun | cardsrfun | https://cardsrfun.de | konfiguriert, Erreichbarkeit separat prüfen |
| CardLegends | cardlegends | https://cardlegends.de | konfiguriert, Erreichbarkeit separat prüfen |
| Comic Attack | comic-attack | https://comic-attack.de | konfiguriert, Erreichbarkeit separat prüfen |

MediaMarkt und Saturn zählen bei unabhängigen Vergleichspreisen als gemeinsame Betreibergruppe, nicht als zwei unabhängige Preisbelege. Otto lieferte damals teils exakte Variantenpreise ohne Verkäufernachweis und deshalb nur Discovery-Kandidaten. Gate-Kategoriepreise brauchten Produktbestätigung. Ultracomix war eine einzelne Fairy-Tail-Seite, kein Gesamtkatalog; heute deaktiviert und außerhalb des gewünschten Sortiments.

Weitere **14 schon damals vorhandene Auslands-Einträge** wurden in der deutschen v3-Stufe deaktiviert. Sie stehen auch im am 06.10. geprüften GitHub-Stand noch auf `enabled=false`:

| Händler | URL | Status |
|---|---|---|
| Geekie (BE) | https://geekie.be | deaktiviert |
| OutpostBrussels (BE) | https://outpostbrussels.be | deaktiviert |
| Bescards (NL) | https://www.bescards.com | deaktiviert |
| CardStore (NL) | https://cardstore.nl | deaktiviert |
| Lairos.Shop (AT) | https://lairos.shop | deaktiviert |
| CardStore (AT) | https://cardstore.at | deaktiviert |
| S-Games (AT) | https://s-games.at | deaktiviert |
| PrimeProtector (AT) | https://primeprotector.at | deaktiviert |
| Merchfox (AT) | https://www.merchfox.at | deaktiviert |
| Coso5 (AT) | https://www.coso5.at | deaktiviert |
| Japan2UK (GB) | https://www.japan2uk.com | deaktiviert |
| Poke Swiss (CH) | https://poke-swiss.ch | deaktiviert |
| Pokeflip (BE) | https://pokeflip.com | deaktiviert |
| Universe TCG (ES) | https://www.universetcg.com | deaktiviert |

Dies sind gespeicherte Quellenkandidaten, keine aktive EU-Vollabdeckung. Der neuere Auftrag erlaubt EU-Lieferungen nach Deutschland sowie ausdrücklich bewertete UK-/CH-Ausnahmen. Vor einer Aktivierung sind Lieferung, Sprache, Verkäufer, Währung/Importkosten und die tatsächlich geeigneten Adapter zu prüfen. Fehlende EU-Abdeckung bleibt ein offener Punkt.

## Weitere technische Erkenntnisse aus dem Verlauf

- Ursprüngliche Pipeline: Discovery, exakte Normalisierung, unabhängiger Preisvergleich, historischer/UVP-Anker, Bewertung, persistente Historie, Deduplizierung, Discord.
- Shopify-Kataloge damals auf bis zu acht Seiten à 250 Produkte erweitert; zusätzliche Collections und Referenzprodukte. Seitenlimitwarnung zwingend. Gezählt wurden Varianten, nicht 30.000 passende Deals.
- HTML-Katalogadapter ergänzt: Same-Site-Produktlinks, strukturierte Angebote, begrenzte Pagination/Detailseiten; finale Produktdetails ersetzen Katalogdaten.
- Preisvergleich zählt pro Betreiber höchstens einmal, Kandidat zählt nicht als eigener unabhängiger Vergleich. Ausreißer/inkonsistente Märkte werden verworfen; hohe Marktpreise erzeugen keine UVP.
- Alter Marktpfad: Vergleichspreise höchstens 24 Stunden alt; Historie 90 Tage, höchstens 180 Samples pro Angebot, Änderungs-/Tagesstichproben. Diese Werte sind historische/teilweise weiter bestehende Implementierung, keine Vorgabe für frische Checkout-Validierung.
- Fehlende Seiten, Timeouts, unbekannter Bestand und Shopausfall bedeuten **nicht ausverkauft**. Status nicht künstlich umschalten; sonst falsche Restocks.
- Versandstatus erst nach erfolgreicher Discord-Bestätigung setzen. Fehlgeschlagene Sends dürfen keine Treffer verschlucken. Atomare State-Sicherung und Migration alter Versandstände erhalten.
- Historisch pro Produkt nur günstigster Anbieter; dies wurde später ausdrücklich durch separate Händlerangebote ersetzt.
- Früher 24-Stunden-Cooldown und sechs Stunden Mindest-Ausverkauf. Neuere schnelle echte Restocks/Preorder-Öffnungen nicht wieder auf diese Wartezeiten zurücksetzen.
- robots.txt, Allow/Disallow, Crawl-delay/Request-rate, Hostabstand, Timeouts und Gesamtzeitbudget beachten. HTTP 429/503 und Retry-After über Läufe im State berücksichtigen. Kein Schutz-/Captcha-Bypass.
- Historische Diagnose-Workflows hatten keine Versandfreigabe. Discord-Payload unterdrückt automatische Mentions.
- Historisch reine Artikelpreise inklusive Steuer verglichen; Versand extra. Kein Beweis günstigster Gesamtkosten. Aktueller Auftrag verlangt Versand-/Importtransparenz.
- „Confidence 90 %“ ist ein regelbasierter Score, keine statistisch gemessene Zuverlässigkeit.
- Zwischen Discord-Bestätigung und dauerhaftem Git-State-Push bleibt ohne Transaktion ein Absturzfenster; keine absolute Exactly-once-Garantie behaupten.

## Damalige Tests, Betrieb und Artefakte

Nachweise aus den gespeicherten damaligen Ausgaben, **keine heute neu ausgeführten Tests**:
- Grundpipeline: 85 Tests und Konfigurationsprüfung; Dry-run 32 Quellen, 30.302 Varianten, ein qualifizierter Kandidat, kein Versand.
- Preisbewertungen: 92 Tests, darunter 80 statt 70 Euro, exakte 15-%-Grenze, künstlich hoher Median, fehlende Referenz und günstigere verfügbare Alternative.
- +30-Euro-Erweiterung: 98 Tests; 90/100 bei Basis 70 zulässig/orange, 100,01 unzulässig, Deduplizierung/fehlender Anker geprüft.
- Identitätsreparatur: 105 Tests; Alias/Edition/Spielsystem/18er-Format, Mindestvergleiche und Migration des Meldungsstands.
- Neuerfassungsprüfung: 33 Quellen, 30.339 Varianten; zwei verbleibende Meldungen nach Deduplizierung.
- Lokaler Lauf 18.09., 20:47:41–20:51:46 Europe/Berlin: `sent=2`, `errors=[]`, beide Versandstände mit bestätigter Message-ID. Naruto 54,99 Euro und FB03 83,99 Euro. Exitcode 1 wegen damaliger Warnungslogik bedeutete hier nicht fehlgeschlagenen Discord-Versand.
- Kataloglücken damals besonders CardCosmos, Celestial Gameshop, Geeksheaven, Battle Bear, Variety Cards und Opasladen; einzelne MediaMarkt-Seite nicht erreichbar.

Lokaler Betrieb hieß **TCG Deal Watch PC**. Intervall von PT5M auf PT10M geändert, zusätzlich Anmeldungstrigger, IgnoreNew und Prozess-Mutex gegen Überschneidungen. Wach/online/angemeldet erforderlich, Bildschirmsperre möglich. Keine Energieeinstellungen geändert. Ein fehlerhafter `Set-ScheduledTask -InputObject`-Aufruf wurde damals durch gezieltes Aktualisieren der Trigger behoben. Webhook lag privat per Windows-DPAPI verschlüsselt, zur Laufzeit als Umgebungsvariable. GitHub war damals über `TCG_RUNNER` gegen Doppelbetrieb abgesichert. Diese Einrichtung ist **historisch**; der heutige PC-unabhängige Cloudbetrieb wird nicht darauf zurückgestellt. Heutiger Zustand der alten Windows-Aufgabe wurde nicht beobachtet.

Artefaktregister, relativ zum damaligen zweiten Projektordner `referenced-chatgpt-conversation-this-is-an-2`:
- `outputs/tcg-deal-bot-v3/`, `outputs/tcg-deal-bot-v3.zip`, `outputs/tcg-deal-bot-v3.patch`
- `outputs/Aenderungen.json`, `outputs/Pruefbericht.md`, `outputs/live-probelauf.json`
- `outputs/Reparatur-Bericht.md`, `outputs/Reparatur-Pruefung.json`, `outputs/Versandbestaetigung.json`
- Im Paket: `PREISBEWERTUNG.md`, `PRUEFBERICHT-V3.md`, `QUELLEN-V3.md`, README
- Entwicklungskopien: `work/bot`, `work/rating-bot`, `work/premium-bot`, `work/repair-bot`
- Erfassungen: `work/captured-offers.json`, `work/capture-status.json`, `work/repair-comparison.json`
- Damals aktualisierte Laufkopie im ersten Projekt: `outputs/tcg-deal-bot`; privater Zustand unter `work/tcg-pc-runtime` mit `last-run.json`, `last-run.log`, `report.json`, `state.json`, privaten Einstellungen und DPAPI-Datei. Private Dateien niemals veröffentlichen.

Im Quellchat wurde ausdrücklich **kein GitHub-Publish** dieser damaligen Pakete behauptet. Heute sind relevante Funktionen im echten Repository nachgewiesen; alte ZIPs nicht über neueren Cloudcode kopieren.

## Überholte Regeln und verbleibende Aufgaben

Nicht reaktivieren: zusätzliche Franchises, englische Pokemon-Produkte, pauschaler Preorder-Ausschluss, Displays-only, ausschließlich Deutschland, nur ein Händler pro Produkt, PC-Pflicht, alter Stunden-/Zehn-Minuten-Cloudplan, starre sechs Stunden OOS, fehlende UVP als Ausschluss aus jeder Chat-Preisübersicht.

Bewahren/weiter bearbeiten:
1. +30-Euro-Präferenz und ehrliche Farbbewertung bei künftigen Filterentscheidungen berücksichtigen; Fast-Watch-/Marktpfad-Differenz sichtbar lassen.
2. EU-Einträge sind noch deaktiviert. Tatsächliche Coverage statt Listenlänge prüfen.
3. Händler-/Set-Aliase verbessern, ohne Edition/Packung/Sprache zu vermischen; Migration gegen Doppelmeldungen testen.
4. Abgelehnte Kandidaten mit konkretem Grund prüfen; alte Referenzen nicht mit OOS-Schnäppchen als dauerhafte Obergrenze verwechseln.
5. Cloud-Chat-Funde gelangen noch nicht automatisch in den Python-Bot; diese bereits zentral dokumentierte Lücke bleibt bestehen.
6. Historische lokale Artefakte und ein gekürzter Logrest sind keine vollständige Dateisicherung. Bei späterem Shellzugriff bei Bedarf sichern; keine jetzige Laufzusage für die alte Windows-Aufgabe.

## Vollständiger Gesprächsrunden-Index

| Reihenfolge | Turn-ID | Nutzeranlass |
|---|---|---|
| 1 | `01a0b489-9d72-7ed3-9f71-593826ce8e01` | Mehrstufige breite Discovery und Marktvergleich; ausdrückliche Ergänzung: keine Scalperpreise, sehr nahe UVP |
| 2 | `01a0b4b9-37b4-7553-a29d-b1445835c6d6` | Ja vielleicht sollte man etwas über uvp noch als obergrenze setzen?  |
| 3 | `01a0b4ba-1e58-72a2-a43a-31ffaa6f60ed` | wenn jetzt was normalerweise 70 kostet und ich 80  bezahlen muss ist das doch auch okay  |
| 4 | `01a0b506-5a04-75e3-bffb-cfb745ee1510` | oder mit bewertung von dir guter preis, kein guter preis etc  |
| 5 | `01a0b506-e043-7090-8223-f01564fa8b71` | ja  |
| 6 | `01a0b509-35bc-7011-8664-2cc68c185350` | und dann auch bitte laufen lassen, alle 10 minuten oder so abchecken obs was gibt oder was neues gibt  |
| 7 | `01a0b534-fbdf-71d2-9ddc-ba4ea7c5696e` | da kam nichts bisher  |
| 8 | `01a0b53c-9e65-7d10-a263-2e9430c50c35` | okay, also 20-30€ mehr als uvp sollten trotzdem angezeigt werden, aber mit bewertung  |
| 9 | `01a0b53f-f8e7-7010-a9b3-c322f1916634` | sicher dass es wirklich läuft?  |
| 10 | `01a0b540-b38b-7243-a153-181c5bafe60a` | kein digimon und yugioh mehr nehmen  |
| 11 | `01a0b5d2-f378-7ce2-bdd3-03ae4b365123` | kann doch nicht sein dass nichts mehr reinkommt??  |
