# Schnellere Erkennung und Zugriffssperren

Stand: 04.10.2026.

## Erkennung im bestehenden Bot

Der Fast Watch prüft bekannte konkrete Varianten zuerst. Neue oder geänderte Katalogeinträge werden anschließend noch im selben Lauf live validiert. Dafür sind zusätzlich maximal 18 Varianten und 25 Sekunden reserviert; nicht abgeschlossene Prüfungen bleiben in der vorhandenen Watchlist.

Die Prüfung verteilt Plätze eines Franchises über verschiedene Händler. Eine große Variantenzahl eines einzelnen Shops kann nicht mehr alle Plätze vorab belegen. FB11 bleibt bevorzugt. Live-Produkt-JSON wird innerhalb eines Händler-Batches geteilt; der Warenkorb-/Varianten-HTML-Abruf bleibt pro konkreter Variante frisch. Zwischen Läufen gibt es keinen Verfügbarkeitscache.

Katalogprüfung: maximal 16 Händler pro Lauf, 80 Sekunden Budget, frühestens nach 15 Minuten erneut. Das ist eine Rotation und keine Zusage, dass jeder Händler exakt alle 15 Minuten komplett geprüft wird. GitHub kann Starts verzögern.

Beide Prüfphasen teilen sich das bestehende Discord-Limit von 20 Meldungen. Nur bestätigte, qualifizierende Angebote werden gesendet. Dedupe-State und Statuswechsel bleiben persistent. Warte-/Benachrichtigungslisten, falsche Sprache und veraltete Suchpreise qualifizieren nicht.

## Neue Quellen

- ANI KUNI: deutsches Impressum mit Kontakt/USt-ID; Zahlungen mit Käuferschutz in Versandbedingungen genannt; Cardmarket-Profil mit externer Bewertungshistorie. https://www.ani-kuni.de/policies/legal-notice / https://www.ani-kuni.de/policies/shipping-policy / https://www.cardmarket.com/de/DragonBallSuper/Users/ani-kuni
- DAESU CARDS: deutsches Impressum mit Kontakt/USt-ID; AGB nennen PayPal, Kreditkarte und Klarna. Keine unabhängig bestätigte Bewertungshistorie hinterlegt. https://daesu-cards.de/policies/legal-notice / https://daesu-cards.de/policies/terms-of-service

Diese Angaben sind eine dokumentierte Händler-Basisprüfung, keine Garantie. Produktangebote durchlaufen die gleichen Live-/Preisregeln wie alle anderen Shops.

## Warum ein Händler blockiert

HTTP 403 heißt zunächst nur, dass der Server den Abruf abweist. Möglich sind Bot-Schutz, IP-/Rechenzentrum-Regeln, Sitzungsanforderungen oder eine gesperrte/veraltete Adresse. HTTP 429 ist ein Ratenlimit; Challenge-HTML ist kein Produktbestand. Die bisherigen GitHub-Tests beweisen für Smyths/Kaufland/MMS eine Ablehnung der getesteten Adressen, nicht die genaue Ursache.

Cardmarket beschreibt den Schutz gegen Bots und Crawler ausdrücklich: https://news.cardmarket.com/en/Magic/Cloudflare-Authentication-Request-On-Cardmarket
Neue API-Anträge sind laut Hilfe derzeit geschlossen: https://help.cardmarket.com/en/cardmarket-api

Preisvergleich, Suchindex und Shopverzeichnisse können neue Produkte/Händler entdecken. Sie beweisen keine aktuelle Bestellbarkeit. Ein öffentliches, erlaubtes Feed/API kann nur nach tatsächlichem Zugriff und Varianten-/Verfügbarkeitsprüfung aktiviert werden. Keine Zugriffssperre wird durch CAPTCHA-Umgehung oder IP-Rotation ignoriert.

Für Filialbestände rund um 65934/50 km fehlt weiterhin eine bestätigte Bestandsquelle. Prospektangebote sind keine Regalbestände.

## Nachweis

Der PR-Test liest den Produktions-State und Workflow-Metadaten sowie neue Shopkataloge/konkrete Produktseiten. Er besitzt kein Discord-Secret und schreibt keine Produktionsdaten. Dabei protokolliert er den letzten Lauf, Anzahl der Watch-Ziele, letzte bestätigte Zustellung und tatsächliche Validatorergebnisse.
