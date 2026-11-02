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
