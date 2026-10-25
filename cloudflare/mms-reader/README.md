# Kostenloser MediaMarkt/Saturn-Zugriff

**Vorbereitet, erst nach Einrichtung aktiv.** Der Bot läuft weiterhin in GitHub Actions. Dieser optionale Worker lädt ausschließlich öffentliche MediaMarkt-/Saturn-Produkt-, Kategorie-, Marken- und robots.txt-Seiten. Kein Browser-Abo, keine kostenpflichtige API, kein laufender PC. Der kostenlose Workers-Tarif erlaubt derzeit 100.000 Requests pro Tag; beim Erreichen der Grenze ausfallen lassen, nicht auf einen kostenpflichtigen Tarif wechseln.

Cloud-Probe am 25.10.2026: MediaMarkt zweimal HTTP 200 mit echtem Produktzustand, Saturn einmal ebenso. Bestehender Parser: SKU 2974734, 59,99 EUR, `PERMANENTLY_NOT_AVAILABLE`, Warenkorb false. **Kein Deal und keine Nachricht.** Das ist ein Zugriffsbeleg für diese Seite, keine Garantie für jeden Artikel oder dauerhafte Erreichbarkeit. Pokémon Center blieb eine Challenge und wird ausdrücklich nicht über diesen Worker unterstützt.

## Einmalige Einrichtung im Browser

1. Kostenloses [Cloudflare-Konto](https://dash.cloudflare.com/sign-up) erstellen; keine Domain, Zahlungsdaten oder kostenpflichtigen Workers-Tarife notwendig. Unter **Workers & Pages → Create application → Worker** einen Worker erstellen. `worker.mjs` im Code-Editor einfügen und deployen.
2. Einen zufälligen Schlüssel mit mindestens 32 Zeichen im Passwortmanager erzeugen. Im Worker unter **Settings → Variables and Secrets** als verschlüsseltes Secret `READER_TOKEN` speichern. Nicht in Code, Chat oder Logs einfügen.
3. Im [GitHub-Repository unter Actions-Secrets](https://github.com/dougY52/tcg-deal-bot/settings/secrets/actions) setzen: `TCG_CLOUD_READER_URL` = `https://WORKER.SUBDOMAIN.workers.dev/read`; `TCG_CLOUD_READER_TOKEN` = derselbe Schlüssel. Bestehenden Discord-Webhook beibehalten. Danach **TCG Cloud Watch → Run workflow → dry_run=true** zum Prüfen, im Bericht MediaMarkt/Saturn kontrollieren. Die folgenden Zeitplanläufe nutzen den Zugang automatisch und senden nur qualifizierte Treffer.

Ohne beide Secrets bleibt die bisherige Route erhalten. Unvollständige/ungültige Einrichtung führt bei diesen beiden Händlern zu einem klaren Fehler, nicht zu einem falschen Angebot. Zum Deaktivieren beide optionalen GitHub-Secrets entfernen.

## Grenzen und Prüfungen

- Worker akzeptiert nur authentifizierte GETs und eine feste Host-/Pfadliste. Keine freien Proxy-Ziele, Weiterleitungen, Kundendaten, Warenkörbe, Logins oder GraphQL-Mutationen.
- Der Bot prüft robots.txt über denselben Weg und behält Zeitbudget, Händlerpausen, Rate Limits und Parser bei. Nur der Bot soll diesen Reader aufrufen; er ist kein öffentlicher Proxy.
- Keine Ergebnis-Caches. Antworten älter als 60 Sekunden oder für eine abweichende URL werden verworfen. Upstream-Fehler bleiben Fehler; 429/503 lösen bestehendes Backoff aus.
- Der bestehende Parser bestätigt Produkt-ID, Sprache, Verkäufer, Preis, Bestand und echte Kaufbarkeit. Katalog-/Suchtreffer allein lösen keinen Alert aus. Deduplizierung und Versandlogik bleiben unverändert.
- MediaMarkts Katalog-/API-Suche außerhalb der unterstützten HTML-Pfade bleibt auf der bisherigen Route. Bei Seitenänderungen oder neuem Bot-Schutz kann auch dieser Weg ausfallen.
- Ein Zugriffstest auf Pokémon Center war erfolglos. Offizielle Ankündigungen bleiben separat; kein behaupteter Live-Bestand und keine garantierte Drop-Vorwarnung.

Quellen: [Workers Free Limits](https://developers.cloudflare.com/workers/platform/limits/), [Playground](https://developers.cloudflare.com/workers/playground/).
