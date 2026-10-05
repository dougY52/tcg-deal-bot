# Tägliche Live-Preise

Seit 05.10.2026 gibt es neben den deduplizierten Sofortmeldungen tägliche Preisinfos.

- Ein konkretes Produkt je Händler/Variante erscheint einmal pro Kalendertag (Europe/Berlin), auch bei unverändertem Preis.
- Die Übersicht wird über die regulären Scans in kompakten Blöcken ergänzt. Sie ist keine garantierte Vollerhebung aller Shops zu einem festen Zeitpunkt.
- Ausschließlich in diesem Lauf live bestätigte, direkt bestellbare Angebote oder Preorders. Kataloge und Such-Snippets reichen nicht aus.
- Pokémon DE, Dragon Ball EN, One Piece EN und Naruto DE/EN; bestehende Produkt- und Händlerprüfungen gelten.
- Maximal 200 Euro Produktpreis. Versand wird separat angegeben; unbekannter Versand bleibt offen.
- Fehlende Retail-/UVP-Referenzen verhindern die Preisinfo nicht. Kennzeichnung: „Preisvergleich offen; kein bestätigter UVP-Deal“. Ein solcher Preis ist keine Deal-Empfehlung.
- Wachsendes Chaos und Optimale Ordnung bleiben bei normalen Preisen gemäß der ausdrücklichen Ausnahme ausgeschlossen.
- Maximal vier Angebote pro Nachricht und zwei Preisnachrichten pro Lauf, innerhalb des bestehenden Gesamtsendelimits. Weitere Angebote können bei ihrer nächsten Live-Prüfung folgen.
- Verschiedene Händler werden getrennt gezeigt. Die Tageshistorie ist unabhängig von Preissturz-/Restock-Alerts.
- Bereits heute als Sofortmeldung gesendete Produkte werden nicht zusätzlich als Preisinfo wiederholt.
- Erfolg wird erst nach erfolgreicher Discord-Antwort gespeichert; nach Versandfehlern bleibt der Eintrag für einen späteren Live-Check offen. Wie bisher ist bei einem Prozessabbruch zwischen Discord-Antwort und State-Persistenz eine Wiederholung möglich.
- Trockenläufe markieren nichts als versendet. Keine Nachrichten für leere Ergebnisse.
- Keine neuen Services, Secrets oder Requests: die bestehende Live-Prüfung und der bot-state-Branch werden genutzt.

Konfiguration: `daily_prices` in `config/config.json`.
Tests: `python -m unittest discover -s tests -v`.
