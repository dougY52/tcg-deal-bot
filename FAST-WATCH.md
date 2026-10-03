# Fast Watch

Der vorhandene Cloud-Workflow hat `*/5 * * * *` und weiterhin `workflow_dispatch`.
GitHub kann Starts verzögern. Der vorhandene externe Timer ergänzt den Zeitplan.
Die gemeinsame Concurrency-Gruppe verhindert gleichzeitige State-Schreibzugriffe;
ein persistenter Mindestabstand von 240 Sekunden vermeidet doppelte Scans durch beide Trigger.

## Ablauf

1. Persistente `fast_targets` aus vorhandenen Preorder-/Markt-URLs initialisieren.
2. Fusion World zuerst: bis zu 48 Varianten aller erkannten `FB`-Setnummern, einschließlich zukünftiger Sets. Vier FB11-Plätze werden bevorzugt, weitere Ziele rotieren nach letzter Prüfung.
3. Reservierte Plätze: wichtige Preorders 8, Pokémon DE 8, One Piece EN 8, Naruto 6, Masters 4. Ältere, nicht verfügbare Produkte bleiben in der Rotation.
4. Live-Abfragen parallel bei höchstens vier unterschiedlichen Hosts; Varianten eines Hosts nacheinander. Gemeinsames Live-Budget 140 Sekunden, zusätzliche Phasenbudgets verhindern Verdrängung der übrigen TCGs.
5. Qualifizierte Treffer senden und State speichern, bevor langsame Discovery beginnt.
6. Je Lauf bis zu zwölf länger nicht gescannte Händlerkataloge prüfen, frühestens nach 30 Minuten erneut. Bei 58 Händlern wird die gesamte Liste bei regelmäßigen Starts ungefähr alle 25–30 Minuten durchlaufen. Discovery-Budget 80 Sekunden. Neue Produkte kommen in die nächste Live-Prüfung.
7. Alle drei Stunden vier bisher am längsten nicht geprüfte Händlerverzeichniseinträge auf neue Shops prüfen; separate Kandidatenliste `retailer_candidates`. Impressum, Zahlverfahren und Reputation müssen geprüft werden, bevor ein neuer Shop aktiviert wird. Ein Verzeichniseintrag ist keine Vertrauensbestätigung.

**Das ist kein Versprechen, alle Produkte alle fünf Minuten zu prüfen.** Die aktuell bekannten Fusion-World-Ziele passen in das Kontingent; bei mehr als 48, Rate-Limits, langsamen Antworten oder GitHub-Verzögerungen wird verschoben. Die übrigen Watchlists rotieren. Zähler `selected`, `checked`, `deferred` und Ablehnungsgründe stehen im Report.

## Live-Prüfung und Preis

Shopify: frisches Produkt-JSON, exakte verfügbare Variant-ID, aktuelle Währung und passendes aktives Warenkorbformular. WooCommerce: konkrete verfügbare Variation und zugehöriges Formular. Kein Kauf, keine Warenkorbmutation. Nicht unterstützte Checkout-Verfahren werden zurückgehalten; allgemeine HTML-/Marketplace-Scanner bleiben zur Discovery erhalten.

Such-/Katalogpreise sind keine Versandgrundlage. Live-Preis ersetzt alten Preis; Sprach-, Set-, Editions- oder Produkttypkonflikte verhindern den Alert. Waitlist, Notify, Sold-out und nicht verbindliche Backorders qualifizieren nicht.

Nur belegte Retail-/UVP-Referenzen oder ausdrücklich beschriftete Nutzer-Preisorientierungen qualifizieren. Drei aktuell teure Händler allein rechtfertigen keine neue Retailbasis. Vorhandene geprüfte Preisreferenzen werden weiterverwendet. FB02 95 €, FB04 85 €, FB11 120 € sind befristete Nutzerorientierungen, keine erfundene UVP. Höhere Preise benötigen andere geeignete Belege. Maximal 200 € Produktpreis bleiben erhalten.

Pokémon nur DE, Dragon Ball/One Piece EN, Naruto DE/EN. Relevante versiegelte Bundles und Tins sind im Fast Watch wieder zugelassen; keine selbst zusammengestellten Stapel, Displaybreaks, Grading-Einzelkarten oder Repack-Angebote. Wachsendes Chaos / Optimale Ordnung: mindestens 20 % unter bestätigter Vergleichsbasis, sonst still.

Nicht bestätigter Versand wird als unbekannt ausgewiesen, niemals als kostenlos erfunden. Ein Gesamtpreis erscheint nur bei bekanntem Versand. Automatischer Vergleich von vollständigen Lieferpreisen ist damit noch nicht für jeden Shop möglich.

## State und Discord

Bestehender Branch `bot-state`, bestehendes Secret und bestehende `preorder_products` weiterverwendet. Statusverlauf wird auf 100 Änderungen begrenzt. Erst bestätigte Nichtbestellbarkeit und anschließendes In-stock/Preorder erhöhen die Verfügbarkeitsepisode; Netzwerkfehler zählen nicht als Ausverkauft. Gleiche Episode/gleicher Preis schweigt, ab 5 % Preisrückgang darf erneut gemeldet werden. Bereits im alten Deal-Watch gesendete Angebote werden bei der Migration berücksichtigt. Unterschiedliche Händler bleiben getrennt. Fehlgeschlagener Discord-Versand wird nicht als zugestellt markiert.

Keine Fundmeldung bedeutet keine Discord-Nachricht. Logs und Reports enthalten Betriebshinweise, nie der Deal-Channel.

## Offene Grenzen

Cardmarket wurde direkt geprüft und antwortet HTTP 403. Ein schonender periodischer Zugriffsversuch bleibt enthalten; es gibt **keine aktive Cardmarket-Seller-/Bestandsvalidierung** und keine Alerts aus dessen Suchmaschinen-Snippets. Keine Schutzumgehung. Auch neue Händler werden nicht ungeprüft automatisch freigeschaltet.

Unbestätigte Sprachen, Herstellerlizenzen neuer Naruto-Produkte, UVPs, Varianten und Versandkosten bleiben offen statt geschätzt. Nicht alle HTML-Shops haben einen unterstützten Live-Checkout-Parser. Die bestehenden Parser werden nicht entfernt.

## Tests

`python -m unittest discover -s tests -v`

Zusätzlich zu den vorhandenen Tests: echter beobachteter OOS→In-stock-Zyklus, Notify→Preorder, gleicher Treffer erneut, Preisrückgang, falscher Indexpreis vs. Live-Preis, Live-Ausverkauft, Sprach-/Setkonflikt, fehlender Preisanker, Pokémon-Ausnahme, fehlgeschlagener Discord-Versand, doppelte Trigger, zukünftige FB-Nummern und reservierte Plätze für andere Franchises. Versandtests benutzen einen Fake-Sender und erzeugen keine Testnachrichten im Discord.
