# Öffentliche Händler-Schnittstellen und frühe Drops

Stand: 25.10.2026, circa 01:08–01:15 Uhr Europe/Berlin. 38 Quellen geprüft: große Händler, lokale Angebotsportale, Hersteller und Händlerverzeichnisse. Dies ist keine Behauptung, dass 38 neue Händler bereits bestellbare Angebote liefern. Die beiden JSON-Protokolle enthalten Einzelbefunde und Zeitstempel. Naruto ist separat pausiert; aktiv bleiben Pokémon DE, Dragon Ball EN und One Piece EN.

## Konkretes Ergebnis

**Saturn liefert über die beobachtete öffentliche `SearchV4`-Abfrage auch vom GitHub-Runner Produktdaten.** Im Cloud-Test: HTTP 200, 12 Katalogprodukte. Die öffentliche Katalogsuche ist jetzt zusätzlich zum vorhandenen Seitenparser eingebunden. Pro Katalogdurchlauf rotiert eine Abfrage zwischen Pokémon-Sammelkarten, Dragon-Ball-Displays und One-Piece-Displays sowie bis zu fünf Ergebnisseiten. Es werden ausschließlich passende Produkt-URLs übernommen; Sprache, Preis, Verkäufer, Variante und Bestellbarkeit müssen weiterhin auf der konkreten Produktseite validiert werden. Ein API-Preis oder `isAvailableAndBuyable` aus einer Suchliste erzeugt allein keinen Alert.

**MediaMarkt:** Dieselbe technische Familie ist vorhanden. Lokal funktionieren `CategoryV4` und die Produktseiten. Der direkte öffentliche API-Test auf GitHub lieferte HTTP 403, ebenso die Katalogseite. Deshalb ist dieser zusätzliche API-Weg dort nicht als funktionierende Cloud-Quelle aktiviert. Bestehende Scanner bleiben erhalten und dokumentieren Fehler.

**Müller:** Katalog und normale Browserdarstellung sind lokal und auf GitHub lesbar. Beobachtet wurde `GET /api/navigation/?buildId=…`; das ist Navigation, kein Bestandsfeed. Produktdaten und Warenkorbzustand kommen weiter aus der tatsächlichen Produktseite. Der vorhandene Parser prüft konkrete SKU, Preis/Währung, Verkäufer, passenden aktiven Warenkorbbutton und Lieferung nach Hause. „Nur Filiale“ bleibt unbestätigter lokaler Bestand. Es wurde kein allgemeiner öffentlicher Feed mit zukünftigen Nachlieferungen gefunden.

**Pokémon Center Deutschland:** `/en-de` bleibt bei beiden Testumgebungen eine Schutzseite. Auch ein HTTP 200 kann hier nur Challenge-HTML enthalten. Die Robots-Datei listet unter anderem `/availabilities`, `/items`, `/offers`, `/prices`, `/cortex` und `/site/*/resourceapi/` als ausgeschlossen. Diese Pfade wurden nicht als Ersatz gescannt. Die deutsche offizielle Presseseite ist erreichbar und bereits im Drop-Watch angebunden. Eine öffentliche, exakt datierte Verkaufsankündigung kann einen separaten Hinweis auslösen; eine bloße Veröffentlichung, ein Bild oder eine Release-Angabe nicht. Eine Warteschlange garantiert laut [Pokémon Center](https://support.pokemoncenter.com/hc/en-us/sections/37286442436372-Waiting-to-enter-Pok%C3%A9mon-Center) weder einen Drop noch Bestand.

## Weitere Händler und Quellen

- **OTTO:** Katalog und Browser lesbar. Beobachtete öffentliche Fragmente unter anderem `/leafcutter/filtersection` und `/san-squirrel-suggest-api/completion`. Sie eignen sich zur Suche, nicht allein zur Verkäufer-/Checkout-Bestätigung. Die vorhandene OTTO-Anbindung bleibt Discovery. Die dokumentierte [OTTO Market API](https://api.otto.market/docs/sellers-integration/) ist für authentifizierte Händler und deren eigene Produkte; sie ist kein freier Gesamtbestandsfeed für uns.
- **Smyths:** Die deutsche TCG-Kategorie existiert; in unseren Abrufen lokal und auf GitHub HTTP 403. [Smyths erklärt](https://www.smythstoys.com/de/de-de/verfuegbarkeit) ausdrücklich die Trennung von Onlinebestand, gewählter Filiale und Vorbestellung. Eine funktionierende automatische Filialprüfung wurde hier nicht bestätigt.
- **Kaufland:** Der Marketplace-Abruf scheitert in dieser Umgebung bereits an HTTP 403. Die separate [Filial-Angebotsseite](https://filiale.kaufland.de/angebote/uebersicht.html) ist in beiden Umgebungen lesbar und nun als eigene Discovery-Quelle registriert. Aktionszeitraum und Filialauswahl müssen geprüft werden; ein Prospekt beweist keinen Livebestand und ist kein Online-Verkäuferangebot.
- **idee+spiel:** Die alte indexierte Kategorie gibt 404 zurück. Die aktuelle [Sammelkarten-Kategorie](https://www.ideeundspiel.com/produkte/spielzeug/sammelkarten/) ist lokal und in GitHub lesbar und ersetzt die bisherige Homepage. Produktangebote nennen einzelne Verkäufer, Versand und teils Stückzahlen. Für verlässliche Alerts fehlt noch ein eigener Verkäufer-/Variantenvalidator. Hohe Altset-Preise werden durch die bloße Aufnahme nicht freigegeben.
- **Netto:** Die [Sammelkarten-Kategorie](https://www.netto-online.de/sammelkarten/c-N06081404) ist lesbar und ersetzt die ungezielte Homepage. Viele Angebote sind Englisch, Japanisch, Koreanisch oder Chinesisch; das macht sie für Pokémon DE nicht passend. Discovery ersetzt die Sprachregeln nicht.
- **Rossmann:** Produktseite liefert Challenge-HTML, auch im normalen Browser. **Galeria, Thalia, Cardmarket, REWE:** hier keine belastbar lesbare Angebotsquelle (Details in der Tabelle). Cardmarket-Verkäufer und einzelne Sprachen konnten daher nicht live bestätigt werden.
- **EDEKA, Lidl, ALDI, Globus:** Angebots-/Startseiten sind je nach Umgebung lesbar. Daraus ergibt sich keine vollständige SKU-Verfügbarkeit aller Märkte. Eine funktionierende Bestandsprüfung für **65934 + 50 km** ist mit diesen Ergebnissen noch nicht erreicht.
- **ROFU, Games Island, Hiveworld, Collect-it, Comicplanet, BB-Spiele, FantasyWelt, JPC:** in die technische Bestandsaufnahme aufgenommen. Erreichbarkeit, Zeitbudgets und Cloud-Unterschiede stehen unten. Eine Homepage ohne passende Produktlinks ist keine nachgewiesene TCG-Abdeckung.
- **Kartenmeier und Tabletop Dragon:** zusätzliche öffentlich lesbare Katalog-/Preorderquellen registriert. Neue Shops bleiben vor Alerts auf konkrete Checkout- und Händlerprüfung angewiesen.
- **OpasLaden:** der bisherige Shopify-Katalog liefert 404. Die [eigene Seite](https://opasladen.de/collections/pokemon) kündigt den Umzug von Einzelkarten/Slabs zu TCG Elite an. Der defekte Katalogscanner wurde pausiert, seine Historie bleibt erhalten; die Umzugsseite wird separat beobachtet. Kein funktionierender Sealed-Scanner wurde entfernt.

## Woher andere Monitore ihre Hinweise haben können

Öffentliche Produktkataloge, neue Produkt-URLs, Varianten-JSON, Händlerankündigungen, öffentliche Filialangebote und Community-Sichtungen reichen oft schon aus. Das ist eine plausible technische Erklärung, kein Nachweis für die Methode der erwähnten Person. Ohne deren Quelle lässt sich nicht behaupten, sie habe internen Lagerzugang.

[Kartenwacht beschreibt selbst](https://kartenwacht.de/so-funktionierts) Händler-Preisprüfungen, Restock-Vergleiche und Community-Funde. Öffentliche und Discord-/Telegram-Funde erscheinen dort nach eigener Aussage teilweise verzögert. Als alleinige Sofortquelle wäre das ungeeignet. Die öffentliche One-Piece-Seite ist jetzt eine zusätzliche Discovery-Quelle, kein Bestandssiegel. Cardwatch bleibt Händlerverzeichnis; Kartodex bezeichnet Sichtungen selbst als ungeprüft.

Shopify hat eine dokumentierte öffentliche [Produkt-JSON-Schnittstelle](https://shopify.dev/docs/api/ajax/reference/product), die unser bestehender Bot bereits nutzt. Warenwirtschaft, Lieferantenportale und authentifizierte Verkäufer-APIs sind davon getrennt. Öffentliche Daten enthalten oft noch keinen künftigen Wareneingang; eine Vorhersage vor jeder Freischaltung ist damit nicht möglich.

## Was im Bot geändert wurde

- Naruto reversibel pausiert, einschließlich alter Fast-Watch-Ziele, Preorders, Tagespreise und themenbezogener Drop-Hinweise; Historie nicht gelöscht.
- Saturns bestätigte öffentliche Katalog-API als zusätzliche URL-Discovery eingebunden, mit rotierenden Suchbegriffen/Seiten, bestehendem Zeitbudget, Rate-Limit-Behandlung und unveränderter Produktseiten-Validierung.
- Händler-Discovery erkennt jetzt auch normale relative Produktlinks, nicht ausschließlich strukturierte JSON-LD-Produkte. Offsite-Links, pausierte Themen und offensichtliches Zubehör werden verworfen. Kandidaten werden mit Quelle, erstem und letztem Sichtungszeitpunkt gespeichert, höchstens 500 Einträge für 30 Tage; **keine automatische Angebotsmeldung daraus**.
- Gezielt bessere Kategorie-URLs sowie getrennte Filial-/Vergleichsquellen registriert. Es bleibt bei den bestehenden kurzen, rotierenden Prüfungen; kein Vollcrawl von 38 Quellen alle fünf Minuten.
- Wiederholbarer öffentlicher Netzwerk-/Schnittstellen-Audit im bestehenden GitHub-Prüfworkflow. Keine neuen Dienste, Abos oder Secrets. Frische Browserkontexte, keine Anmeldung, kein HAR, keine Cookie-/Tokenaufzeichnung, keine Warenkorbänderung. POSTs blockiert. Normale Bot-Schutzseiten bleiben als Hindernis sichtbar.

## Zugangsmatrix

„Lesbar“ bezeichnet die geprüfte Seite, ausdrücklich keine bestätigte Bestellbarkeit. `unavailable` ist kein „ausverkauft“. Unterschiede zwischen lokal und Cloud sowie zeitliche Änderungen sind real; insbesondere Saturn war in früheren Cloud-Tests gesperrt, bei diesem Test jedoch erreichbar.

| Quelle | Lokal | GitHub Linux |
|---|---|---|
| [pokemoncenter-de](https://www.pokemoncenter.com/en-de) | challenge; Browser 200 | challenge; Browser 200 |
| [pokemon-press-de](https://pokemon.gamespress.com/de) | lesbar | lesbar |
| [pokemon-official-retailers](https://tcg.pokemon.com/de-de/where-to-buy/) | challenge | challenge |
| [pokemon-event-locator](https://events.pokemon.com/de-de/locations) | Unexpected robots redirect | Unexpected robots redirect |
| [kaufland-filiale](https://filiale.kaufland.de/angebote/uebersicht.html) | lesbar; Browser lesbar | lesbar; Browser lesbar |
| [cardwatch-directory](https://cardwatch.eu/de/stores/germany) | lesbar | lesbar |
| [kartenwacht](https://kartenwacht.de/) | lesbar | lesbar |
| [kartodex](https://www.kartodex.de/restock-radar) | Network or encoding error | Network or encoding error |
| [tabletop-dragon](https://www.tabletop-dragon.de/shop_de/trading-card-games/pokemon/vorbestellung.html) | lesbar | lesbar |
| [kartenmeier](https://kartenmeier.de/collections/pokemon-deutsch-top-trainer-box) | lesbar | lesbar |
| [cardmarket](https://www.cardmarket.com/de/Pokemon/Products/Booster-Boxes) | HTTP 403 | HTTP 403 |
| [mueller](https://www.mueller.de/c/spielwaren/spiele-puzzles/sammelkarten/) | lesbar; Browser lesbar | lesbar; Browser lesbar |
| [smyths](https://www.smythstoys.com/de/de-de/spielzeug/action-spielzeug/pokemon/pokemon-karten/c/SM1001012002) | HTTP 403; Browser 403 | HTTP 403; Browser 403 |
| [fantasywelt](https://www.fantasywelt.de/Pokemon) | Run request budget exhausted | HTTP 403 |
| [gamesisland](https://games-island.eu/) | lesbar | lesbar |
| [galaxus](https://www.galaxus.de/search?q=pokemon%20display) | robots.txt disallows this endpoint | robots.txt disallows this endpoint |
| [rofu](https://www.rofu.de/) | lesbar | lesbar |
| [ideeundspiel](https://www.ideeundspiel.com/produkte/spielzeug/sammelkarten/) | lesbar; Browser lesbar | lesbar; Browser lesbar |
| [kaufland](https://www.kaufland.de/product/564681995/) | HTTP 403; Browser not_attempted_policy_unconfirmed | HTTP 403; Browser not_attempted_policy_unconfirmed |
| [rossmann](https://www.rossmann.de/de/ideenwelt-amigo-pokemon-tcg-wachsendes-chaos-3-booster-blister/p/0196214140189) | challenge; Browser 200 | challenge; Browser 200 |
| [mediamarkt](https://www.mediamarkt.de/de/category/pokemon-karten-8444.html) | lesbar; Browser lesbar | HTTP 403; Browser 403 |
| [saturn](https://www.saturn.de/de/brand/pokemon-sammelkartenspiel/neuheiten) | lesbar; Browser lesbar | lesbar; Browser lesbar |
| [otto](https://www.otto.de/spielzeug/spiele/sammelkarten/?marke=pokemon) | lesbar; Browser lesbar | lesbar; Browser lesbar |
| [edeka](https://www.edeka.de/angebote/) | HTTP 500; Browser 403 | lesbar; Browser 403 |
| [galeria](https://www.galeria.de/kinder/spielzeug/spiele-und-puzzles/gesellschaftsspiele-und-co/pokemon-karten) | HTTP 403; Browser not_attempted_policy_unconfirmed | HTTP 403; Browser not_attempted_policy_unconfirmed |
| [rewe](https://www.rewe.de/angebote/nationale-angebote/) | HTTP 403 | HTTP 403 |
| [lidl](https://www.lidl.de/) | lesbar | lesbar |
| [aldi-sued](https://www.aldi-sued.de/) | lesbar | lesbar |
| [aldi-nord](https://www.aldi-nord.de/) | lesbar | lesbar |
| [netto](https://www.netto-online.de/sammelkarten/c-N06081404) | lesbar | lesbar |
| [globus](https://www.globus.de/) | lesbar | lesbar |
| [thalia](https://www.thalia.de/kategorie/sammelkartenspiele-8205/) | HTTP 403 | HTTP 403 |
| [amazon-de](https://www.amazon.de/) | lesbar | lesbar |
| [jpc](https://www.jpc.de/) | lesbar | lesbar |
| [hiveworld](https://www.hiveworld.de/) | lesbar | lesbar |
| [collect-it](https://www.collect-it.de/) | lesbar | HTTP 403 |
| [comicplanet](https://www.comicplanet.de/) | lesbar | HTTP 503 |
| [bb-spiele](https://www.bb-spiele.de/) | lesbar | robots.txt disallows this endpoint |

## Belege und Reproduktion

- [Cloud-Audit, Lauf 40141874669](https://github.com/dougY52/tcg-deal-bot/actions/runs/40141874669), Job `public-interfaces`: öffentliche 38-Quellen-Prüfung, Saturn JSON erfolgreich, MediaMarkt 403.
- `research/public-interfaces-cloud-2026-10-25.json`: aus genau diesem Job extrahierte Befunde.
- `research/public-interfaces-local-2026-10-25.json`: lokale Gegenprobe und anonymisierte Endpunktmetadaten.
- `research/public-mms-local-2026-10-25.json`: beide API-Katalogabrufe lokal erfolgreich.
- `python -m scripts.audit_public_interfaces` und `python -m scripts.audit_mms_queries` reproduzieren die begrenzten Zugangsprüfungen. Optional `--ids mediamarkt,saturn,mueller` oder `--http-only` beim ersten Skript.
- Der Audit-Job selbst ist erfolgreich, wenn der Bericht erstellt wurde. Einzelne HTTP-403-/Challenge-Befunde bleiben im Bericht Fehler und werden nicht zu „funktioniert“ umgedeutet.

Öffentlich beobachtete GraphQL-Abfragehashes können sich mit der Shopversion ändern. Die gespeicherten Werte sind keine Zugangsschlüssel. Bei geändertem Schema oder GraphQL-Fehler wird die Abfrage verworfen; der normale Seitenweg bleibt erhalten. Der aktuelle Stand verspricht weder Sekundenstarts von GitHub Actions noch eine garantierte Drop-Vorwarnung für alle Händler.
