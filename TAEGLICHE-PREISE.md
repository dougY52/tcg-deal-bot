# Tägliche Preisübersicht

Die gemeinsame Auswahl und die Kanalregeln stehen in [TCG-WATCH.md](TCG-WATCH.md).

Die regulären Live-Scans sammeln am selben Tag geprüfte Angebote in `state.daily_price_overview`. Preis, Händler, Produktvariante, Sprache und Prüfzeitpunkt bleiben erhalten. Fehlende Retailreferenzen verhindern die Aufnahme nicht; sie werden gekennzeichnet. Verfügbarkeit, Sprache, Händlerprüfung und 200-Euro-Grenze bleiben erforderlich. Bestätigte Ausverkäufe bzw. Preisänderungen entfernen alte Einträge.

Dieser gespeicherte Überblick ist keine Echtzeitgarantie. Die zentrale Chat-Recherche muss Prüfzeitpunkte nennen und vor Kaufhinweisen oder neuen Discord-Alerts nochmals aktuell validieren. Die Sammlung allein erzeugt noch keinen ChatGPT-Zeitplan.

Discord bleibt selektiv: `daily_prices.discord_enabled` ist **false**. Es werden keine täglichen Preisblöcke an Discord gesendet. Die optionalen Tages-Dedupe-/Blockfunktionen bleiben getestet, aber deaktiviert.

Bestehende Sofortmeldungen verwenden weiterhin ihren eigenen persistenten Dedupe-State. Keine neuen Secrets oder Infrastruktur, keine zusätzlichen Produktrequests.

Tests: `python -m unittest discover -s tests -v`.
