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

Der Direktabruf kann weiterhin an Sicherheitsprüfungen scheitern. Die neue
Frame-Auswertung und die kürzere Wiederholungszeit beseitigen Parser-/Taktlücken,
aber bestätigen keine vollständige oder sekundenschnelle DE-Abdeckung.
Community- und CardPal-Hinweise bleiben zusätzliche Quellen. Ein echter aktueller
DE-Queue-Start samt Discord-Latenz muss erst beobachtet werden.
