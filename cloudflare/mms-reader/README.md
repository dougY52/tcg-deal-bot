# Kostenloser MediaMarkt/Saturn-Zugriff

**Worker veröffentlicht und über GitHub Actions live bestätigt.** Der Bot läuft weiterhin in GitHub Actions. Dieser optionale Worker lädt ausschließlich öffentliche MediaMarkt-/Saturn-Produkt-, Kategorie-, Marken- und robots.txt-Seiten. Kein Browser-Abo, keine kostenpflichtige API, kein laufender PC. Der kostenlose Workers-Tarif erlaubt derzeit 100.000 Requests pro Tag; beim Erreichen der Grenze ausfallen lassen, nicht auf einen kostenpflichtigen Tarif wechseln.

Cloud-Probe am 25.10.2026: MediaMarkt zweimal HTTP 200 mit echtem Produktzustand, Saturn einmal ebenso. Bestehender Parser: SKU 2974734, 59,99 EUR, `PERMANENTLY_NOT_AVAILABLE`, Warenkorb false. **Kein Deal und keine Nachricht.** Das ist ein Zugriffsbeleg für diese Seite, keine Garantie für jeden Artikel oder dauerhafte Erreichbarkeit. Pokémon Center blieb eine Challenge und wird ausdrücklich nicht über diesen Worker unterstützt.

Produktiver Zugriffstest: [GitHub-Job 121029899731](https://github.com/dougY52/tcg-deal-bot/actions/runs/40146408536/job/121029899731), 25.10.2026, 00:28 UTC. Beide Händler lieferten SKU 2974734 für 59,99 EUR als nicht bestellbar. OIDC-Anmeldung, robots.txt, Produktabruf und vorhandener Parser funktionieren zusammen. Der Test versendet keine Discord-Nachrichten.

## Einmalige Einrichtung

Der bevorzugte Weg verwendet Cloudflares offizielle CLI (`wrangler deploy`) und die beiliegende `wrangler.jsonc`. Das kostenlose Cloudflare-Konto autorisiert die Einrichtung einmal im Browser. Der Worker prüft danach kurzlebige, kryptografisch signierte GitHub-OIDC-Token statt eines dauerhaft kopierten Schlüssels. Er akzeptiert nur das Repository `dougY52/tcg-deal-bot` mit seiner unveränderlichen Repository-/Owner-ID, Branch `main` und `.github/workflows/cloud-watch.yml` bei schedule/push/workflow_dispatch. Pull Requests und fremde Repositories erhalten keinen Zugang.

Die öffentliche URL `https://tcg-mms-reader.tcg-deal-bot-dougy52.workers.dev/read` ist als `TCG_CLOUD_READER_URL` im bestehenden Cloud-Workflow eingetragen. `id-token: write` ist dort bereits vorbereitet. Kein Cloudflare-API-Token und kein neuer Discord-Webhook werden in GitHub benötigt. Der laufende Bot braucht weder den PC noch die lokale Wrangler-Anmeldung.

Alternative für andere Clients: Im Worker ein zufälliges Secret `READER_TOKEN` mit mindestens 32 Zeichen und denselben Wert als `TCG_CLOUD_READER_TOKEN` im Client setzen. Diese Alternative ist nicht erforderlich und standardmäßig nicht eingerichtet. Geheimnisse niemals in Chat, Code oder Logs eintragen.

Ohne konfigurierte Reader-URL bleibt die bisherige Route erhalten. Ungültige Einrichtung führt für diese beiden Händler zu einem Fehler, nicht zu einem Angebot. Deaktivierung: Reader-URL aus dem Workflow entfernen. Bestehende Discord-Secrets bleiben unverändert.

## Grenzen und Prüfungen

- Worker akzeptiert nur authentifizierte GETs und eine feste Host-/Pfadliste. Keine freien Proxy-Ziele, Weiterleitungen, Kundendaten, Warenkörbe, Logins oder GraphQL-Mutationen.
- Der Bot prüft robots.txt über denselben Weg und behält Zeitbudget, Händlerpausen, Rate Limits und Parser bei. Nur der Bot soll diesen Reader aufrufen; er ist kein öffentlicher Proxy.
- Keine Ergebnis-Caches. Antworten älter als 60 Sekunden oder für eine abweichende URL werden verworfen. Upstream-Fehler bleiben Fehler; 429/503 lösen bestehendes Backoff aus.
- Der bestehende Parser bestätigt Produkt-ID, Sprache, Verkäufer, Preis, Bestand und echte Kaufbarkeit. Katalog-/Suchtreffer allein lösen keinen Alert aus. Deduplizierung und Versandlogik bleiben unverändert.
- MediaMarkts Katalog-/API-Suche außerhalb der unterstützten HTML-Pfade bleibt auf der bisherigen Route. Bei Seitenänderungen oder neuem Bot-Schutz kann auch dieser Weg ausfallen.
- Ein Zugriffstest auf Pokémon Center war erfolglos. Offizielle Ankündigungen bleiben separat; kein behaupteter Live-Bestand und keine garantierte Drop-Vorwarnung.

Quellen: [GitHub OIDC](https://docs.github.com/en/actions/reference/security/oidc), [Workers Free Limits](https://developers.cloudflare.com/workers/platform/limits/), [Playground](https://developers.cloudflare.com/workers/playground/).
