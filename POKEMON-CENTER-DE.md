# Pokémon Center Deutschland: eigener Monitor

Stand: 01.11.2026. Dieser Monitor prüft ausschließlich Pokémon Center Deutschland.
Er startet als eigener Job **Pokémon Center Deutschland** im bestehenden Workflow
**TCG Cloud Watch**, parallel zum bisherigen Händler-Scanner. Dessen fünfminütiger
Zeitplan und bestehender externer Start werden weiterverwendet. Kein PC, kein
Pokémon-Center-Konto, kein neues kostenpflichtiges API-Abo und keine neuen Secrets.
Der bestehende Discord-Webhook bleibt im GitHub Secret `DISCORD_WEBHOOK_URL`.

## Was tatsächlich funktioniert

- Öffentliche Discord-Ankündigungen über CommunityOne, öffentliche X-Posts über
  RSS, Bisafans auf Telegram sowie Reddit und die vorhandene MyDealz-Prüfung.
- Es zählen ausschließlich Aussagen, die Pokémon Center und Deutschland
  ausdrücklich betreffen. Ein britischer Account darf eine deutsche Meldung
  liefern; britische/amerikanische Produkte bleiben ausgeschlossen.
- **Vorwarnung:** Eine Quelle meldet eine neue deutsche Hinterlegung / ein neues
  Produkt. Maximal 48 Stunden alte Originalmeldungen, mit Datum, Quellenlink und
  ausdrücklicher Kennzeichnung als nicht durch den Shop bestätigter Hinweis.
- **Queue-/Bestandsmeldung:** Nur frische ausdrückliche Deutschland-Meldungen,
  höchstens 15 Minuten alt. Eine Community-Meldung wird nicht zu einer angeblich
  selbst bestätigten Kaufmöglichkeit umetikettiert.
- Direkte deutsche Startseite: prüft erreichbare Warteseiten. Eine globale Queue
  am deutschen URL ohne ausdrücklichen Deutschland-Bezug genügt nicht.
- Beim Start können noch aktuelle Vorwarnungen einmal nachgereicht werden.
  Alte Beiträge werden nicht allein durch eine neue Abfrage wieder frisch.

Die öffentlichen Spiegel sind zusätzliche Quellen mit unbekannter und möglicher
Verzögerung. Sie garantieren weder vollständige Discord-Abdeckung noch einen
Vorsprung gegenüber dem Originalpost. Private Kanäle werden nicht gelesen.

## Konkrete Recherche / Grenzen

1. [Galar Alerts, öffentlich veröffentlichte Discord-Ankündigung](https://communityone.io/en/servers/1554874902937346108/galar-alerts-uk-pokemon-restocks/updates/#msg-1566221101376344288):
   Am 31.10.2026 um 22:43 UTC wird behauptet, dass die 30th-Celebration-ETBs für
   Deutschland hinterlegt seien. Der Parser trennt diese deutsche Aussage vom
   britischen Ditto-Produkt im gleichen Beitrag. **Kein offizieller Bestandsbeleg.**
2. [DROP UK](https://teapawt.net/dropalertsuk): Öffentlich dokumentierte deutsche
   Delta-Herrschaft-SKUs am 13.10.2026. Nicht als heutiger Drop versenden.
3. Direkte Startseite, bekannte deutsche Produktseite und Sitemap lieferten beim
   Test am 01.11.2026 HTTP 200, aber nur eine Incapsula-Schutzseite. Das ist kein
   lesbarer Bestand und auch keine offene Warteschlange.
4. Ein in einem öffentlichen GitHub-Monitor behaupteter Algolia-Suchzugang war
   nicht erreichbar; weder als funktionierende API noch als DE-Datenquelle eingebaut.
5. [Offizielle robots.txt](https://www.pokemoncenter.com/robots.txt) sperrt u.a.
   `/cortex`, `/availabilities`, `/prices`, Warenkorb- und Kontopfade für Crawler.
   Der Monitor fragt diese nicht ab. Keine CAPTCHA-Lösung, Sitzungsübernahme,
   internen Zugangsdaten, SKU-Bruteforce-Scans oder automatischen Käufe.
6. [Pokémon Center zur Warteschlange](https://support.pokemoncenter.com/hc/en-us/articles/37286495522452-Pok%C3%A9mon-Center-Virtual-Queue):
   Eine Queue bedeutet nicht automatisch Produktstart oder Verfügbarkeit.

**Nicht erreicht:** ein direkt bestätigter, dauerhaft kostenloser DE-Bestandsfeed
oder eine Garantie, jeden Drop vorab/sekundenschnell zu erkennen. Ein Kundenkonto
ist dafür kein Backend-Zugang; manuell kopierte Browser-Cookies sind keine
nachgewiesene dauerhafte Cloud-Lösung.

## Betrieb und Nachweis

Konfiguration: `config/pokemon-center-de.json`. Programm:

```sh
python -m scripts.watch_pokemon_center_de          # ohne Discord und ohne State-Schreiben
python -m scripts.watch_pokemon_center_de --send   # vorhandenes Webhook-Secret
python -m unittest discover -s tests -p test_pokemon_center_watch.py -v
```

Im Branch `pokemon-center-state` stehen `state.json` und `report.json`; die
GitHub-Job-Zusammenfassung zeigt pro Quelle Zugriff/Fehler und bestätigte
Discord-Zustellungen. Keine ruhigen Statusmeldungen im Discord-Kanal.

Original-IDs werden erst nach bestätigter Discord-Zustellung als gemeldet gespeichert.
Gleiche SKUs bzw. die 30-Jahre-TTB werden auch über verschiedene Quellen sechs
Stunden lang zusammengefasst. Eine Vorwarnung blockiert keine spätere Queue- oder
Bestandsmeldung. Der bisherige MyDealz-State wird bei der Einrichtung übernommen.
Fehler eines Dienstes stoppen die übrigen Quellen nicht. Blockierte Quellen
erhalten Backoff bis maximal eine Stunde und werden nicht als ausverkauft gespeichert.
Zwischen unbekanntem Queue-Zustand und einer bestätigten Wiederöffnung wird unterschieden.

Der Zeitplan ist fünfminütig, jedoch [kann GitHub Starts verzögern](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
Die Laufzeit auf [Standard-Linux-Runnern öffentlicher Repositories ist kostenlos](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
Der Job bleibt für private Repositories ausgeschaltet und legt keine zusätzlichen
Actions-Artefakte/Caches an. Der bisherige Händler-Bot wird weiterbetrieben; seine
alten Pokémon-Center-Community-/Startseitenprüfungen sind an diesen Job übergeben,
um doppelte Pings zu vermeiden.

## CardPal: authentifizierter Verbindungstest

Stand 01.11.2026: CardPal bewirbt kostenlose Deutschland-Drop-Alarme. Sein
öffentliches Web-Frontend nutzt einen authentifizierten Posteingang sowie einen
Ereignis-Stream. Diese Schnittstellen sind keine zugesicherte externe API.
Ein funktionierender Transport und schnelle Erkennung eines Shop-Drops müssen
getrennt nachgewiesen werden. Der Anschluss ist deshalb noch **kein aktiver
Discord-Monitor**.

Der vorhandene Workflow `TCG Cloud Watch` hat dafür die optionale Eingabe
`cardpal_access_test`. Sie startet ausschließlich einen zusätzlichen Lesetest;
die bestehenden Händler- und Pokémon-Center-Jobs bleiben erhalten. Für den Test
`dry_run=true`, `cardpal_access_test=true`, `pc_access_test=false` auswählen.
Der Lesetest läuft getrennt von langen Händlerläufen und überspringt in seinem
Lauf sämtliche Händler-/Discord-Jobs. Ein Maintainer-Push mit `[cardpal-audit]`
im Commit-Titel startet denselben isolierten Test ohne Browser oder lokalen PC.
Benötigte Repository-Secrets:

- `CARDPAL_EMAIL`: E-Mail des eigenen CardPal-Kontos.
- `CARDPAL_PASSWORD`: Passwort dieses CardPal-Kontos, kein Google-/Apple-Passwort.

Der Test meldet sich direkt bei CardPal über HTTPS an, liest Benachrichtigungs-
Einstellungen und höchstens 250 Posteingangseinträge und prüft kurz den Stream.
Er verändert keine Einstellungen, markiert nichts als gelesen und hat keinen
Discord-Webhook. Passwörter, Cookies und Tokens bleiben im Arbeitsspeicher;
es werden keine fremden Nachrichteninhalte ausgegeben. Der Bericht enthält
nur Zähler, boolesche Einstellungen und Zeit-/Regionsnachweise für spezielle
Pokémon-Center-Broadcasts. Das kleine Diagnose-Artefakt bleibt einen Tag erhalten.
Fehlende Anmeldung, unerwartete Daten oder Umleitungen führen zu einem sichtbaren
Fehler statt einer Erfolgsmeldung über vermeintlich verfügbare Ware.

`transport_verified` bedeutet nur: Anmeldung, Posteingang und Stream waren lesbar.
`no_live_drop_sample` bedeutet: keine neue DE-Meldung während der Messung gesehen.
Das Alter alter Posteingangseinträge wird niemals als Zustellverzögerung verwendet.
Eine im Stream neu beobachtete Meldung liefert höchstens eine Stichprobe für
**CardPal-Veröffentlichung → Empfang**, nicht für **Shop-Drop → CardPal**.
Ohne unabhängigen Shop-Zeitstempel bleibt die zweite Verzögerung unbekannt.

Lokale Tests (ohne Zugangsdaten/Netzwerk):

```sh
python -m unittest discover -s tests -p test_cardpal.py -v
```
