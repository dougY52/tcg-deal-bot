# Pokémon Center Deutschland: Queue-Prüfung, 02.11.2026

## Ergebnis der öffentlichen Schnittstellen-Recherche

Eine frei erreichbare, regionsspezifische Status-API mit nachgewiesener DE-Drop-Latenz
ist nicht verifiziert. Der aktuell vom deutschen Shop gelieferte
`main-iframe` verweist auf die shop-eigene Route `_Incapsula_Resource`. Ein direkter
Live-Test konnte diesen Frame lesen, fand darin jedoch eine Imperva-Sicherheitsseite,
keine Warteschlange und keine Positions-/Wartezeitdaten. Dieser Befund ist **unbekannt**,
nicht „Queue geschlossen“. Der Prüfzeitpunkt steht jeweils im Cloud-Bericht.

Öffentliches Vergleichsmaterial:

- [Offizielle Queue-Hilfe](https://support.pokemoncenter.com/hc/en-us/articles/37286495522452-Pok%C3%A9mon-Center-Virtual-Queue):
  Eine Warteschlange kann auch ohne Produktstart auftreten und garantiert keinen Bestand.
- [Browser-Erweiterung von j-ding](https://github.com/j-ding/pokemon-ceneter-queue/blob/main/content.js):
  liest bereits empfangene Incapsula-XHR-Antworten mit `pos`/`ttw`. Sie liefert keine
  eigenständige öffentliche DE-Statusquelle. Es wird weder Code übernommen noch
  die Erweiterung installiert.
- [QueueDex](https://queuedex.com/non-uk-drop-queues): beschreibt gemeinsame
  Queue-Aktivierungen und regionale Deutschland-Banner; ein historisches Archiv,
  kein bestätigter eigener Echtzeit-DE-Datenfeed für unseren Bot.
- [cjudge129-Monitor](https://github.com/cjudge129/pokemon-restock-monitor/blob/main/scrapers/pokemoncenter.js):
  probiert Queue-it-Hosts und wertet Nicht-404-Antworten als Queue aus. Das ist kein
  belastbarer DE-Nachweis und wird nicht übernommen. Ein Fehlerstatus oder eine
  generische CDN-Seite darf niemals einen Discord-Alert erzeugen.
- [Cardiyo](https://cardiyo.io/support): nennt 30-Minuten-Prüfungen im kostenlosen
  Tarif; damit keine verifizierte kostenlose Sofortlösung für diesen Auftrag.

## Umgesetzte Verbesserung

### Sichtbaren Deutschland-Hinweis auslesen und sofort weitergeben

Am 02.11. wurde ein historischer [Screenshot der echten gelben Meldung](https://www.reddit.com/r/PokemonTCG/comments/1tvshzm/)
visuell geprüft. Er nennt den deutschen Store und den heutigen Start deutscher
TCG-Produkte. Seine Formulierung wird in Browser-Tests wiedergegeben; die HTML-
Struktur ist eine Testnachbildung, kein gespeicherter aktueller Shop-Abruf.

Der bestehende kostenlose Browser-Aufruf liest nach zwei Sekunden zusätzlich
einen begrenzten DOM-Schnappschuss. Dabei werden berechnete CSS-Sichtbarkeit,
ausgeblendete Vorfahren und die aktuell eingebundene primäre Warteseite geprüft.
Footer, Navigation, Länderauswahl, Scripts und Formularwerte gelangen nicht in die
Auswertung. Ein Hinweis außerhalb des Warteraum-Frames bleibt erhalten, sofern
der Frame selbst eine echte lesbare Queue zeigt. Eine Sicherheitsprüfung plus
Deutschland-Text bestätigt weiterhin nichts. Ohne vollständigen sichtbaren
Schnappschuss darf dieser Provider keinen DE-Alert erzeugen. Keine zusätzlichen
Seitenaufrufe, Klicks, Cookies, CAPTCHAs oder neuen Abhängigkeiten im normalen Bot.

Zwei reproduzierte Zustellprobleme sind korrigiert: Eine frische Bestätigung aus
dem unabhängigen Cloud-Abruf wurde zuvor durch die Fehlersperre des direkten
Abrufs oder dessen Prüfintervall verworfen; außerdem wartete der Sender auf alle
Community-Abfragen. Bestätigte Queue-Daten gehen jetzt zuerst zum vorhandenen
Discord-Sender. Die direkte HTTP-Fehlersperre bleibt für weitere Netzwerkanfragen
erhalten. Veraltete Bestätigungen und doppelte Alerts werden weiterhin verworfen;
ein Sendefehler verbraucht keine Zustellbestätigung.

Die Gratis-Budgets und Zeitpläne bleiben unverändert. Browser-Replay und ein
begrenzter aktueller Cloud-Test prüfen den Code; ein echter deutscher Queue-Start
mit gemessener Discord-Latenz bleibt separat nachzuweisen.

Verifiziert im [Cloud-Test 41515917699](https://github.com/dougY52/tcg-deal-bot/actions/runs/41515917699):
92 Tests inklusive echter Chrome-Ausführung erfolgreich. Um **21:06 Uhr Berlin**
lieferte der vorhandene kostenlose Provider eine sichtbare deutsche Shopseite
(`store_readable`, `rendered_visibility=true`), keine Queue und keinen Alert.
Kosten: 125 Gratis-Credits, Rest danach rechnerisch 8.990 Credits. Die lokale
Gesamtsuite bestand aus 662 Tests, davon 655 erfolgreich und sieben Browser-Tests
lokal übersprungen; diese sieben liefen im Cloud-Test erfolgreich.
Der reguläre [DE-Job](https://github.com/dougY52/tcg-deal-bot/actions/runs/41515917530/job/125519330328)
um 21:05 Uhr war ebenfalls erfolgreich und verbrauchte ohne Queue-Signal null
Provider-Credits. Der direkte Abruf war weiterhin blockiert; der unabhängige
Provider-Abruf ist deshalb entscheidend. Messdaten stehen in
`research/pokemon-center-visible-2026-11-02.json`.

### Kostenlose Queue-Abfrage mit gezielter Deutschland-Prüfung

Der normale DE-Job liest zusätzlich den anonymen, vom
[StockWatch-Frontend](https://stock-watch.co.uk/pokemon/queue-status) verwendeten
öffentlichen `/api/pokemon-queue/status`-Endpunkt. Er ist ausdrücklich in dessen
robots.txt freigegeben. Das ist ein **gemeinsames** Queue-Signal und erzeugt
allein niemals eine Deutschland-Meldung. `open` bedeutet dort normaler Shopzugang,
`live` eine aktive Queue. `opening`, `gated`, veraltete oder unbekannte Antworten
reichen nicht aus. Letzte Prüfung und gemeldetes Datenalter müssen unter zwei
Minuten liegen. Der Abruf nutzt den bestehenden Minuten-/Fünfminutentakt.

Nur bei frischem `live` wird der vorhandene ScrapingAnt-Zugang für einen gezielten
Abruf der deutschen Startseite verwendet. Der Abruf verlangt keinen `main`-
Selektor mehr, weil echte Warteseiten diesen nicht haben müssen. Aus der Extended-
Antwort wird ausschließlich der aktuell auf der Seite eingebundene primäre Frame
ausgewertet. Ein sichtbarer Queue-Text **und** ein ausdrücklicher Deutschland-
Banner sind weiterhin Pflicht. Cookies, XHR-Inhalte und Challenge-URLs werden
nicht gespeichert oder weitergegeben. Ohne Bestätigung bleibt Discord still.

Gratis-Grenzen sind vor jedem Abruf zwingend: bestätigter kostenloser Tarif,
mindestens 1.000 Credits Restreserve nach dem geplanten Abruf, höchstens 3 Versuche
pro Queue-Welle (frühestens nach 2 und danach 5 Minuten erneut), 750 reservierte
Credits pro UTC-Tag und 6.000 pro rollierenden 30 Tagen. Fehler zählen vorsichtig
mit. Die Reservierung wird vor dem Aufruf gespeichert; geänderte Providerkosten
stoppen weitere Abrufe. Es gibt keine automatische Aufbuchung oder Tarifänderung.
Normale Läufe ohne `live` verbrauchen **null** ScrapingAnt-Credits. Dry Runs nutzen
den Provider nicht. Der separate manuelle Diagnosejob ist auf 125 Credits begrenzt.

Bestätigte Daten gehen durch den vorhandenen Discord-Sender und denselben
persistenten State. Eine bestätigte Zustellung beendet die Versuche für die Welle.
Ein Sendefehler kann innerhalb von zwei Minuten dieselbe frische Bestätigung
erneut nutzen. Zwei unterschiedliche, frische `open`-Beobachtungen erlauben eine
neue Welle; dafür ist erneut ein echter DE-Banner nötig. Ein direkt bereits
erkannter deutscher Queue-Start wird nicht nochmals gemeldet.

Live-Beleg vom 02.11.2026 um 20:34 Uhr Berlin:
[GitHub-Lauf 41511105900](https://github.com/dougY52/tcg-deal-bot/actions/runs/41511105900)
erhielt den aktuellen öffentlichen Status und eine 431.647 Byte große Antwort
mit Titel „Pokémon Center Deutschland Official Site“ und `__NEXT_DATA__`.
Das belegt den Shopseiten-Abruf über diesen Weg, keine Kaufbarkeit und noch keinen
aktiven deutschen Queue-Start. Der konservative Queue-Parser klassifizierte die
Homepage als `unknown`, weil sie keine eindeutige Queue-/Normalzustandsbestätigung
lieferte. Ein echter DE-Drop mit gemessener Discord-Latenz steht weiter aus.

### Zeitplan

Täglich 16:00 bis 19:59 Uhr Europe/Berlin startet der externe cron-job.org-Timer
den bestehenden Workflow mit `pc_minute=true` einmal pro Minute. Sommer-/Winterzeit
wird automatisch berücksichtigt. Dieser Modus führt nur den unabhängigen
Pokémon-Center-Job aus; der breite Händler-Scan bleibt bei fünf Minuten.
Ab 20:00 Uhr läuft Pokémon Center wieder mit dem bisherigen Fünf-Minuten-Zeitgeber.
Ein verspäteter Minuten-Trigger außerhalb des Fensters beendet sich ohne Scan.

Die Quellen verwenden innerhalb des Fensters Minuten-Zeitfenster statt eines
starren 240-Sekunden-Abstands. Ein zweiter Start innerhalb derselben Minute
überspringt bereits geprüfte Quellen. Normaler und schneller Job teilen sich
denselben serialisierten State-Zugriff und dieselbe Discord-Deduplizierung.
GitHub-Runner-Startverzögerungen, lange Quellenanfragen und explizites Rate-Limit-
Backoff bleiben möglich; minütlich eingeplant ist keine sekundengenaue Garantie.

Der bestehende unabhängige GitHub-Job prüft die DE-Startseite mit No-Cache-Headern
und liest höchstens einen dort aktuell eingebundenen, sichtbaren primären Frame.
Ziel ist ausschließlich HTTPS, derselbe Host und die genaue öffentliche
Frame-Route. Fremde Regionen, beliebige Ressourcen, Formulare und fremde Frames
werden nicht angefragt; Sicherheitsprüfungen werden nicht gelöst. Frame-URLs mit
Challenge-Parametern werden weder geloggt noch im State gespeichert.

Positive Queue-Texte und ein ausdrücklicher DE-Queue-/Drop-Banner müssen in
derselben aktuellen Warteseite stehen. Ausgeblendete Texte, Footer, Sprachwahl
und Länderwahl liefern keinen Beleg. Eine gemeinsame Queue ohne DE-Banner bleibt
`QUEUE_REGION_UNCONFIRMED`. HTTP-200-Sicherheitsseiten werden im nächsten
regulären Lauf erneut gelesen; HTTP 429/503 und Netzwerkfehler behalten Backoff.

Bestehende Discord-Zustellung und persistente Deduplizierung bleiben bestehen.
Unbekannte Antworten schließen keine Episode. Erst zwei aufeinanderfolgende
lesbare normale Shopseiten erlauben später einen neuen Öffnungsalert. Ein
Queue-Alert behauptet niemals Produktbestand oder Kaufzugang.

Zusätzlich fragt jeder DE-Job den eigenen CardPal-Relay-Status lesend ab. Ein
Stream-Zeitstempel älter als zehn Minuten gilt nicht als frische Verbindung.
Dieses Signal prüft den Transport, **nicht** die Reaktionszeit von CardPals
eigenem Monitor auf einen Shop-Drop. Kein Browser-Kontingent und keine bezahlte
API werden für diese Erweiterung verwendet.

## Grenzen

### Einmaliger Discord-Funktionstest

Der bestehende Workflow `Browser source check` hat den manuellen Schalter
`pc_discord_test`. Er simuliert den deutschen Hinweis in Chrome (alle Shop-
Requests werden lokal beantwortet), nutzt den normalen Parser, Queue-Gate und
Discord-Sender und sendet **genau eine ausdrücklich als TEST markierte Nachricht**.
Ein separat gespeicherter Test-State prüft die Deduplizierung nach dem Neuladen;
der Produktions-State wird nicht geladen oder verändert. Workflow-Wiederholungen
mit `GITHUB_RUN_ATTEMPT > 1` senden nichts. Der Test läuft niemals nach Zeitplan.

Der Bericht misst ab Erzeugung der simulierten Seite bis zur Discord-API-
Bestätigung und zusätzlich die HTTP-Versanddauer. Er misst weder einen echten
Shop-Drop noch die Push-Benachrichtigung auf dem Handy. Er liest den aktuellen
ScrapingAnt-Kontostand über `/v2/usage`, führt aber keinen kostenpflichtigen oder
creditsverbrauchenden Shop-Abruf aus.

### Zusätzlicher Cloud-Zugriffstest am 02.11.2026

Der [Diagnoselauf 41507297267](https://github.com/dougY52/tcg-deal-bot/actions/runs/41507297267)
hat zwei zusätzliche Zugriffsarten unter Linux und Windows geprüft:

- Normaler Chrome mit JavaScript und sichtbarem Browsermodus: auf beiden
  GitHub-Runnern HTTP 403/Sicherheitsseite, auch nach 30 Sekunden Beobachtung.
  Keine eingebetteten Shopdaten, kein verifizierter deutscher Queue-Status.
- `curl_cffi` mit Chrome-kompatiblem HTTP/TLS: auf beiden Runnern kein nutzbares
  Ergebnis. Der Bericht enthält nur den Fehlertyp `ValueError`; daraus wird
  ausdrücklich kein konkreter HTTP-Status abgeleitet.

56 relevante Tests waren auf beiden Runnern erfolgreich. Die Tests belegen die
Parser-/Deduplizierungslogik, nicht den erfolgreichen Shopzugriff. Rohdaten und
Session-Cookies wurden nicht gespeichert, Discord wurde nicht aufgerufen.
Der Vergleich ist im bestehenden Workflow „Browser source check“ über
`pc_transport_test=true` erneut ausführbar. Er läuft nicht im Minutentakt und
verbraucht keine Cloudflare-Browserminuten oder ScrapingAnt-Credits. Seine
zusätzlichen Abhängigkeiten gelten nur für diesen Diagnosejob.

Die frühere lesbare ScrapingAnt-Katalogantwort vom 25.10.2026 war ein einzelner
Erfolg mit Residential-Browser; die anschließenden Produktabrufe waren nicht
verlässlich. Dieser Modus kostet laut [API-Credittabelle](https://docs.scrapingant.com/credits-cost)
125 Credits pro kostenpflichtig gewertetem Abruf. Die derzeit angebotenen
[10.000 kostenlosen Monatscredits](https://scrapingant.com/) ergeben höchstens
80 solche Abrufe, während allein 16–20 Uhr täglich 240 Minutenprüfungen benötigen.
Es ist daher keine tragfähige kostenlose Minutenlösung. Keine automatische
Tariferhöhung, kein neuer Proxy- oder CAPTCHA-Dienst wurde eingerichtet.

Der CardPal-Relay war im Live-Bericht um 18:59 UTC verbunden und frisch, hatte
aber seit seiner Aktivierung noch keinen DE-Drop zugestellt (`sent=0`). Das ist
kein Nachweis über die Vollständigkeit oder Geschwindigkeit von CardPals
Shopmonitor. Die direkte zuverlässige Pokémon-Center-DE-Abdeckung bleibt offen.

Der Direktabruf kann weiterhin an Sicherheitsprüfungen scheitern. Die neue
Frame-Auswertung und die kürzere Wiederholungszeit beseitigen Parser-/Taktlücken,
aber bestätigen keine vollständige oder sekundenschnelle DE-Abdeckung.
Community- und CardPal-Hinweise bleiben zusätzliche Quellen. Ein echter aktueller
DE-Queue-Start samt Discord-Latenz muss erst beobachtet werden.
