# Eigenständiger Preorder-Watch

Der normale Cloud-Scan enthält seit 03.10.2026 einen separaten Preorder-Prüfpfad.
Der bestehende Workflow, externe Zehn-Minuten-Zeitgeber, Discord-Secret und
`bot-state`-Branch bleiben bestehen. Es entstehen keine zusätzlichen Dienste,
Pakete oder API-Kosten. Ein Scan ist keine Echtzeit-Reservierung.

## Erkennung und Live-Prüfung

Die vorhandenen Händlerkataloge und expliziten Produktziele liefern Kandidaten.
Vorbestellhinweise, Wartelisten und Release-Angaben lösen die Prüfung aus.
Unabhängig davon, ob ein Kandidat akzeptiert wird, kann er den neuen Filter nicht
über die großzügigere normale Preisbewertung umgehen. Nach live bestätigtem
Übergang zu normaler Lagerware gilt wieder der bestehende Deal-Pfad.

Der Shopify-Validator lädt die Produkt-JSON frisch, sucht genau die Variant-ID,
übernimmt deren Preis, Barcode und Verfügbarkeit und liest anschließend die
Produktseite mit ausgewählter Variante und Cache-Buster. Er verlangt einen
POST-Warenkorb-Formularblock mit genau dieser ID und einem aktiven Bestellknopf.
Die aktive Shop-Währung muss auf der Produktseite bestätigt sein. Ein anderer
Sprachbutton, ein Suchsnippet, ein generischer Button oder `available: true`
allein reicht nicht. Warenkörbe werden nicht verändert, Bestellungen nicht ausgelöst.
Technische Grundlage: [Shopify Product API](https://shopify.dev/docs/api/ajax/reference/product)
und [Cart API](https://shopify.dev/docs/api/ajax/reference/cart).

Sapphire-Cards verlangt ausdrücklich konkrete Variante und frische Stock-Prüfung.
Galeria verlangt zusätzlich eine technisch bestätigte Warenkorb-Funktion. Dafür
existiert derzeit **kein Galeria-Adapter**, daher bleibt Galeria geschlossen.
WooCommerce besitzt jetzt einen eigenen Validator für explizite Variation-Daten,
Währung, auswählbare Sprache, Warenkorb-Formular und konkrete Kaufbarkeit.
Sapphire-Cards nutzt diesen Adapter. Andere nicht unterstützte Checkout-Systeme bleiben im
Preorder-Pfad `UNSUPPORTED_LIVE_CHECK`, bis ein überprüfter spezifischer Adapter
existiert. Ihre bestehenden gewöhnlichen Scanner werden nicht entfernt.
Ein beliebiger Shop lässt sich nicht zuverlässig durch einen universellen
Button-Test freischalten. Es gibt keinen CAPTCHA-/Bot-Schutz-Bypass.

## Sortiment

- Pokémon: ausschließlich DE; Displays, Bundles, ETBs, Collections/Boxen und Tins.
- Dragon Ball: ausschließlich EN; Fusion World und Masters, FB11 priorisiert.
  Heroes, Xeno/Xenoverse, Time Patrol und explizites What-if sind ausgeschlossen.
- One Piece: EN; Displays, EB/PRB, Premium-/Special-Produkte und Deck Sets.
  Japanisch bleibt geschlossen: eine fehlende englische Entsprechung und ein
  außergewöhnliches Angebot können momentan nicht automatisch belegt werden.
- Naruto: Mythos, DE/EN; weitere offizielle Linien müssen nach Lizenzprüfung als
  `official_naruto_patterns` freigegeben werden. First Editions erhalten Vorrang.

Der alte Deal-Pfad bleibt auf seine bisherigen Formate beschränkt. Dort werden
Tins weiterhin nicht zugelassen. Die bestehende Preisgrenze von **200 €** gilt
auch für Preorders. Repack-, Mystery-, Zubehör- und ungeöffnete Leerprodukte
werden nicht als relevante sealed Ware behandelt. Inhaltliche Sammlerqualität
wird über erkennbare Produktbegriffe bewertet, nicht anhand erfundener Kartendaten.

## Preise und Händler

Akzeptiert werden exakte, datierte Retail-/MSRP-Referenzen aus der Konfiguration,
passende bisherige Produktbindungen, qualifizierte historische Preise (14 Tage)
oder ein Preis höchstens auf dem Median von mindestens drei Händlern.
Vergleichsangebote müssen dieselbe Identität einschließlich Sprache, Edition,
Format und Barcode beziehungsweise geprüftem Produktmapping haben. Varianten mit
unterschiedlichen Motiven bleiben getrennt. Pro Händlergruppe zählt ein Preis;
Vergleichsangebote werden nach spätestens 30 Minuten verworfen und bei beobachtetem
Ausverkauf sofort entfernt. Ein bekannter Retailanker begrenzt überhöhte Mediane.
Ohne Preisbeleg gibt es keinen bloßen „ungeprüft“-Preorder-Alert.

FB02 95 €, FB04 85 € und FB11 120 € sind **Nutzer-Orientierungswerte, keine UVP**,
zunächst bis 03.11.2026 gültig. Höhere Preise benötigen andere objektive Belege.
FB11 unter 100 € erhält durch Preis- und Produktpriorität Vorrang. Die Liste kann
um `price_references` mit exaktem `comparison_key`, `kind`, `price_eur`,
`verified_on`, `valid_until`, `evidence_url` und `note` ergänzt werden.
Keine automatisierte Google-/X-Suche und keine erfundenen Vergleichspreise.

`trusted_shop_ids` ist die explizite Vertrauensliste bestehender Shopify-Händler,
keine Behauptung über externe Bewertungen oder Zahlungsarten. Neue Shops werden
nicht automatisch aufgenommen. Alternativ akzeptiert das Vertrauensmodell
`seller_evidence[Verkäufername]` mit geprüfter Firma, Käuferschutz,
`review_count >= 20`, `rating >= 4` und einem HTTPS-Nachweis. Das gilt auch für
gewerbliche Marketplace-Verkäufer, sobald ein passender Live-Adapter vorhanden ist.
`serious_scam_signal` sowie ausschließlich Vorkasse/Krypto sperren auch Whitelist-
Händler. Bewertungen werden nicht automatisch extern recherchiert oder erfunden.
Versandkosten und Release werden bei fehlendem Nachweis als unbestätigt angezeigt.

## Zustand und Deduplizierung

- `preorder_tracking`: entdeckte und weiterhin nachzuprüfende konkrete Varianten.
- `preorder_products`: Preis, Status, maximal 100 Status-/Preiswechsel, Episode,
  letzter tatsächlich bestätigter Discord-Versand und qualifizierter Retailpreis.
- `preorder_quotes`: kurzlebige, live validierte Preisvergleichsangebote.

Der stabile Meldeschlüssel enthält Franchise, Format, Sprache, Edition,
Händler/Verkäufer und Variant-ID. Umbenennungen oder geänderte Release-Daten
lösen daher keine Doppelmeldungen aus. Angebote verschiedener Händler bleiben
getrennt. Existierende Meldungen aus dem normalen Deal-State werden übernommen.

Gleicher Treffer bleibt still. Ein Preisrückgang von mindestens 5 % gegenüber dem
letzten Alert oder beobachteter Ausverkauf/Warteliste mit anschließender Öffnung
führt zu einer neuen Meldung. Ein Timeout zählt nicht als Ausverkauf. Neue Händler
und neue erstmals valide Varianten können nach allen Prüfungen melden. Eine nicht
beobachtete kurze Schließung oder nur behauptete neue „Welle“ wird nicht erfunden.
Erst ein erfolgreicher Discord-Versand setzt `last_alert`; Fehler und Dry-Runs
verbrauchen keinen Alert. Der bestehende Checkpoint sichert nach jedem Versand.

Pro Lauf gelten 96 Live-Kandidaten, höchstens 120 zusätzliche Sekunden und das
bestehende gemeinsame Meldelimit. FB11 hat zwei priorisierte Prüfplätze, bis zu vier weitere prüfen die ältesten
Kandidaten unabhängig vom Katalogstatus. Die übrigen bevorzugen laut Katalog
bestellbare Angebote mit passender Sprache und Produktart, besonders bei
Statuswechseln. Innerhalb dieser Gruppen rotiert die älteste Prüfung.
Kataloghinweise bestimmen nur die Reihenfolge, niemals die Alert-Freigabe. Nicht geprüfte Kandidaten bleiben ausstehend.
Bei vielen Kandidaten wird daher **nicht jedes Produkt alle zehn Minuten** geprüft.
Nicht mehr im Katalog sichtbare bekannte Kandidaten werden bis 14 Tage nachgeprüft.

## Betrieb und Diagnose

`python -m unittest discover -s tests -v`

`python -m tcg_bot --check-config`

`python -m tcg_bot` prüft ohne Discord-Versand. `--send` verwendet unverändert
`DISCORD_WEBHOOK_URL`. Keine Secrets in Konfiguration oder Beispiel-Dateien eintragen.
Der bestehende Actions-Workflow führt alle Tests und den Scan automatisch aus.

`report.json.preorder_watch` und die Actions-Zusammenfassung zeigen geprüft,
verschoben, gesendet und Ablehnungsgründe. Einzelne Ablehnungen enthalten den
Kandidatenschlüssel: WAITLIST, OUT_OF_STOCK, WRONG_LANGUAGE, PRICE_TOO_HIGH,
AMBIGUOUS_VARIANT, SELLER_RISK, DUPLICATE sowie technische Gründe.
`PRICE_TOO_HIGH` umfasst auch fehlende belastbare Preisreferenzen.
Keine Treffer erzeugen keine Discord-Statusmeldung.

Beispiel, keine Behauptung eines aktuellen Fundes:

> 🔥 PREORDER LIVE  
> Dragon Ball Fusion World – FB11 Brightness of Hope  
> 🌍 EN · 🏪 Beispielhändler  
> 💶 104,99 € · 📦 Versand: nicht bestätigt  
> 📅 Release: nicht bestätigt · ✅ Direkt vorbestellbar  
> 💡 Innerhalb deiner Preisorientierung: 120,00 €; keine Hersteller-UVP.  
> 🛡️ Händler auf der konfigurierten Vertrauensliste.  
> Produkt-Direktlink im Titel
