# Zusätzliche deutsche Händler – 6. Oktober 2026

Die Kartenwacht-Händlerliste dient als Recherchequelle. Der Bot prüft direkt beim Händler; Kartenwacht-Meldungen werden weder kopiert noch ungeprüft weitergeleitet.

## Angebundene Kataloge

Zehn neue Einträge im bestehenden Scanner: TobisToys, Kroko Games, Animeboy, Mulligan TCG, Feenturm, Card Club, Nerdbank, CardCatcher, KEEPSEVEN und Freispiel Freiburg.

- Shopify: rotierende gezielte TCG-Kategorie plus allgemeiner Katalog. Produkt-JSON und konkrete Variante/Formular werden vor einem Alert neu gelesen. Ausgewählte `select name=id`-Varianten (TobisToys) und „Zum Warenkorb“ (Nerdbank) werden unterstützt.
- CardCatcher/JTL: eigene Produktseite, übereinstimmende Überschrift/SKU, EUR-Angebot, eindeutiges `buy_form`, Artikel-ID und dazugehöriges Mengenfeld. Variantenwahlen und fremde Warenkorbformulare werden abgelehnt.
- WooCommerce: zusätzlich zu bestehenden konkreten Variationen auch einfache Produkte mit passendem Bestellformular. Artikel ohne Formular bleiben unbestätigt; explizit ausverkaufte Produkte bleiben ausverkauft.
- HTML-Kategorien und Produktlinks rotieren mit persistenten Cursorn. Boxen, Bundles und Kollektionen werden ebenfalls entdeckt. Fehlende Katalogsprache darf eine Live-Prüfung auslösen, aber niemals die Sprachregel für einen Alert ersetzen.
- Feenturm: Mitglieder-/Zirkelangebote werden ausgeschlossen. Die öffentlich als Mitglieder-Drops beschriebenen 30-Jahre-Produkte sind vorsorglich separat gesperrt.
- Händlernachweise sind je Shop unter `trust_evidence` hinterlegt. Die Basisprüfung behauptet keine unabhängig verifizierten Kundenbewertungen. Nerdbank: öffentlicher Inhaber, Anschrift/Kontakt und Zahlungsangebot geprüft; Impressum ist automatisiert gesperrt, entsprechend anderer Hinweis.

## Tatsächlich beobachtete Grenzen

Ein konfigurierter Katalog ist keine Garantie, dass jeder Artikel live verifizierbar ist.

| Quelle | Befund aus GitHub-Runner |
| --- | --- |
| TobisToys | FB03 und FB04 EN zu je 89,99 € mit passender Variante und aktivem Formular bestätigt. Preisqualifikation erfolgt separat. |
| Animeboy | Naruto Mythos Konoha Shidō, 2nd Edition EN, 69,90 € bestellbar bestätigt; Preisprüfung im Audit positiv. |
| Mulligan TCG | Direkte Varianten/Formulare bestätigt; Katalog enthält auch viele fremdsprachige bzw. unpassende Produkte. |
| Feenturm | Offene Produkte bestätigt; FB11 EN zu 99,99 € beim Audit ausverkauft. Kein Alert für diesen ausverkauften Treffer. |
| CardCatcher | One Piece Premium Card Collection Vol. 6 EN, 54,99 € mit Produktformular bestätigt. |
| Freispiel Freiburg | OP-Displays erfasst; geprüfte Beispiele ausverkauft, korrekt kein Alert. Positiver Checkout zusätzlich per Regressionstest abgedeckt. |
| Kroko Games | Katalog erreichbar; viele Angaben ohne explizite Kartensprache. Live-Prüfung muss die Sprache bestätigen. |
| Nerdbank | Katalog erreichbar; Crawl-/Zeitbudget begrenzt einzelne Läufe. Gezielte Kategorien rotieren, bekannte Naruto-Seite wird zusätzlich geprüft. |
| Card Club | Katalog erreichbar; deaktivierte Varianten-ID im HTML verhindert derzeit die Checkout-Freigabe bei geprüften Produkten. Kein blindes Annehmen einer JavaScript-Freischaltung. |
| KEEPSEVEN | Adapter vorbereitet und regelmäßig im Scan, derzeit HTTP 403 bei Kategorieseiten. |
| Collect-it / Comicplanet | HTTP 503 beim automatisierten Zugriff; weiterhin Erreichbarkeits-/Discovery-Quellen, keine freigegebenen Alerts. |
| BB-Spiele | robots.txt untersagt den geprüften Zugriff. Keine Umgehung. |
| Games Island | Produktabruf liefert keine verifizierbaren Produkt-/Formulardaten; weiterhin Discovery, keine behauptete Live-Anbindung. Deutscher Händler trotz .eu-Domain. |
| Hiveworld | Erreichbar; geprüfte Shopware-Seite benötigt einen eigenen verifizierten Checkout-Adapter. Weiterhin Discovery. |

Preise sind Audit-Beobachtungen vom 06.10.2026, keine Zusage aktueller Verfügbarkeit.

## Betrieb und Tests

Bestehender Fast Watch, Versandregeln, Preisobergrenze, Webhook-Secret und persistenter `bot-state` bleiben erhalten. Es gibt keinen zweiten Discord-Bot und keine neuen kostenpflichtigen Dienste. Breitere Katalogsuche läuft nach der schnellen Prüfung bekannter Produkte; neue Händler vergrößern den Suchumfang, ohne die festen Laufbudgets zu erhöhen.

`tests/test_new_retailers.py` prüft reale Formularstrukturen sowie falsche Variante, deaktivierte Felder, fremde Formulare, Waitlist, Sold-out, Sprache, Livepreis, Duplikate, Preisfall, Restock und Waitlist → Preorder. Ein neuer Test entdeckte zunächst einen Fehler: Waitlist wurde bei einfachen Produkten als unbekannter Checkout gespeichert. Die Statusübernahme wurde korrigiert, damit echte Wiederöffnungen erkennbar bleiben.

`scripts/audit_new_retailers.py` nutzt dieselben produktiven Adapter und die Laufbudgets. Der PR-Workflow speichert `new-retailer-audit.json` als Artefakt. Er sendet keine Discord-Nachrichten und schreibt keinen produktiven State.
