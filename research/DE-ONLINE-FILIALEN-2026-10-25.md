# Deutschland: kostenlose Online- und Filialquellen für den TCG-Watch
Stand: 25.10.2026. Fokus Pokémon DE, Dragon Ball EN, One Piece EN; Naruto bleibt pausiert. Filialsuche: 65934 + 50 km. Recherche und technische Stichproben, keine vollständige Bestandsabdeckung aller deutschen Händler.

## Ergebnis und tatsächlicher Betriebsstand

Der vorhandene GitHub-Watch und der produktive MediaMarkt-/Saturn-Worker laufen ohne den Nutzer-PC. Für die neue Recherche wurde ein separater, authentifizierter Cloudflare-Worker mit einem echten Browser-Run verwendet. **Pokémon Center bleibt auch dort gesperrt.** HTTP 200 enthielt lediglich Challenge-HTML (888 Bytes nach Browserdarstellung), keine Produkt-/Bestandsdaten. Es wurde keine funktionierende kostenlose öffentliche PC-Bestands-API gefunden.

[Realer GitHub-Testlauf](https://github.com/dougY52/tcg-deal-bot/actions/runs/40177137230): 43 feste öffentliche URLs, davon 22 lesbar, 2 Challenge-Seiten, 5 nicht erfolgreich abrufbar (einschließlich eines Redirects), 12 mit nicht geklärter Robots-Erlaubnis und 2 laut Robots ausgeschlossen. Die Kategorien beschreiben diesen Zugriff zu diesem Zeitpunkt, keine dauerhafte Sperre und keinen Lagerstatus. MediaMarkt/Saturn wurden im separaten bestehenden Cloud-Check geprüft.

[Maschinenlesbarer Befund](free-cloud-results-2026-10-25.json) enthält alle 43 Einzelresultate. Keine Testnachricht an Discord. Keine Checkout-/Warenkorbänderungen. Kein kostenpflichtiger Tarif.

**Neu in der vorhandenen Quellenrotation:** Hugendubel, Akihabara Kelkheim, VEDES, duo, Faix-Filialverzeichnis, ROFU-Filialseite, RestockRadar, HoloHeaven und REWE-Sammelkarten. Damit 42 registrierte Recherchequellen statt 33; das ist nicht die Zahl funktionierender Deal-Scanner. Die Rotation bleibt bei höchstens vier Prüfungen/15 Sekunden je Lauf und sechs Stunden Wiederholabstand pro Quelle. Gefundene Produktlinks bleiben Kandidaten bis zur unabhängigen Liveprüfung. Die Teststrecke über Cloudflare wird dadurch nicht automatisch für diese neun Händler zur produktiven Anbindung.

## Pokémon Center: geprüfte Wege und kostenlose Alternative

| Weg | Ergebnis / Eignung |
|---|---|
| Direkter öffentlicher HTTP-Abruf, GitHub-Browser | Schutzseite; frühere Tests im Hauptbericht |
| Kostenloser Cloudflare-HTTP-Zugriff | Ebenfalls Schutzseite |
| Echter Cloudflare Browser Run | Ebenfalls Schutzseite; tatsächlich getestet, kein bloßer Architekturvorschlag |
| Produktseiten, öffentliche Varianten-/Bestandsantworten | Noch keine erfolgreich gelesene konkrete DE-Variante; daher keine PC-Live-Alerts |
| Offizielle Presse und datierte Verkaufsankündigungen | Öffentlich lesbar; bestehender Drop-Watch nutzt diese bereits |
| Newsletter | Kostenloser zusätzlicher Hinweisweg; Weiterleitung erfordert ein eingerichtetes, autorisiertes Postfach und wurde nicht eingerichtet |
| Suchindex, Vergleichsseiten, Community | Neue URLs/Drop-Hinweise entdecken; nie Preis/Bestand damit bestätigen |
| Lieferanten-/interne Shop-APIs | Kein allgemeiner öffentlicher Zugang festgestellt; Pfadnamen in robots.txt sind kein zugänglicher Bestandsfeed |
| Kostenpflichtige Browser, Proxys, kostenlose Testabos | Keine dauerhaft kostenlose Lösung; nicht gebucht |

[Cloudflare Browser Run](https://developers.cloudflare.com/browser-run/faq/) bietet im kostenlosen Tarif zehn Browser-Minuten täglich. Das ist für gezielte Tests brauchbar, kein unbegrenztes Fünf-Minuten-Browsen vieler Shops. Ein Browser garantiert keinen Zugriff auf geschützte Seiten. [Die öffentliche Content-Funktion](https://developers.cloudflare.com/browser-run/quick-actions/content-endpoint/) wurde über die Browser-Bindung des Workers getestet.

[Pokémon Center nennt selbst keine verlässlichen künftigen Restocktermine](https://support.pokemoncenter.com/hc/en-us/articles/23363169957012-How-often-does-Pok%C3%A9mon-Center-restock-items). Sinnvoll verfügbar bleiben [offizielle Presse](https://pokemon.gamespress.com/de), veröffentlichte Verkaufsankündigungen und optional [Newsletter](https://support.pokemon.com/hc/de/articles/20573695697428-Newsletter-FAQ). Diese sind Frühhinweise, kein Ersatz für eine konkrete bestellbare Variante. Ein Queue-Start allein ist ebenfalls kein Bestandsbeweis.

## Online-Händler: breit suchen, konkrete Angebote einzeln bestätigen

| Gruppe | Quellen / Untersuchung | Nächster technisch sinnvoller Schritt |
|---|---|---|
| Große Elektronikhändler | MediaMarkt, Saturn: produktiver öffentlicher Reader funktioniert | Produkt-/Verkäuferprüfung beibehalten; Filialbestand separat erschließen |
| Drogerien / Spielwaren | Müller-Katalog im Cloudtest lesbar; Produkt mit Filialbutton gefunden. Smyths 403. Rossmann Zugriff noch nicht bestätigt | Müller-Filialantwort mit ausgewählter Filiale nachweisen; Smyths/Rossmann zunächst offizielle Verfügbarkeitsdienste |
| Marktplätze | OTTO-Katalog mit Produktdaten lesbar; Kaufland Marketplace und Cardmarket hier bereits bei Robots 403 | Exakte Sprache, gewerblicher Verkäufer, Versand und Checkout validieren; kein Alert aus niedrigstem Listenpreis |
| Lokale Spielwarenverbünde | VEDES, duo, idee+spiel | Besonders wertvoll für kleinere Händler; Verkäufer- und Filial-ID je Angebot erforderlich |
| Buch-/Kaufhäuser | Hugendubel lesbar, Thalia/Galeria Zugriff nicht bestätigt; JPC-Homepage lesbar | Produktseiten/Filialfunktionen prüfen, Homepage ist keine TCG-Inventur |
| TCG-Fachhandel | Games Island, Comicplanet, Kartenmeier, Tabletop Dragon, BreakTheCase, Akihabara im Cloudtest lesbar; weitere bestehende Scanner bleiben | Konkrete Kataloge statt Startseiten und vorhandene Plattformparser nutzen |
| Weitere Fachhändler | Hiveworld-Homepage lesbar; FantasyWelt 403, Collect-it Robots 403, BB-Spiele Robots-Verbot | Ergebnis protokollieren; gesperrte Seite nicht als leer oder ausverkauft speichern |
| Generalisten | Amazon-Homepage lesbar; Galaxus geprüfte Suchroute laut Robots ausgeschlossen | Keine Händlerabdeckung aus Homepage-Erfolg ableiten |
| Lebensmittel/Discounter | Kaufland-Filialangebote, Lidl, ALDI Nord lesbar; REWE/EDEKA/ALDI Süd/Netto uneinheitlich oder nicht abrufbar | Ortsbezogene Angebote und vorhandene Filialfunktionen statt bundesweitem Lagerbestand |

Marktplätze verlangen zusätzlich die Identität des tatsächlichen Verkäufers: Ein Artikel auf Kaufland oder OTTO muss nicht von Kaufland bzw. OTTO stammen. Für Cardmarket bleibt der gewünschte Filter professionelle DE-Verkäufer mit belastbarer Historie; dieser Test konnte deren konkrete Angebote nicht auslesen.

## Filialbestand und bevorstehende Lieferungen

| Quelle | Öffentlich dokumentiertes Signal | Aussagegrenze |
|---|---|---|
| [Smyths](https://www.smythstoys.com/de/de-de/verfuegbarkeit) | Online- und gewählte Filialverfügbarkeit, Click & Collect, ausgewählte Vorbestellungen | Cloudzugriff aktuell fehlgeschlagen; spätere Abholung ist nicht zwingend heutiger Regalbestand |
| [MediaMarkt](https://www.mediamarkt.de/de/service/lieferung/abholung-markt) / Saturn | Abholung im ausgewählten Markt, teils Expressabholung | Produkt + Markt + Abholzeit prüfen; Versand in den Markt getrennt behandeln |
| [Müller](https://www.mueller.de/service/haeufige-fragen/) | Filialprüfung am Produkt, Lieferung in Filiale, teils Verfügbarkeits-E-Mail | Unser normales Browser-Klicken scheiterte an einer Verifizierung; keine konkrete Filialmenge bestätigt |
| [Rossmann](https://unternehmen.rossmann.de/presse/pressemeldung/app-relaunch-inklusive-onlineshopping.html) | App nennt Bestand bevorzugter Filiale und Lieferoptionen | Dokumentierte Nutzerfunktion; kein von uns bestätigter Cloud-Bestandszugriff |
| [Thalia](https://www.thalia.de/vorteile/filialabholung) | Filialverfügbarkeit und Abholung, alternativ Bestellung in Filiale | Nicht jede Abholoption bedeutet bereits dort vorhandene Ware |
| [Hugendubel](https://www.hugendubel.de/de/category/101686/neue_booster.html) | Liste konkreter Filialen mit Booster-Sortiment | Sortiment bestätigt keine Stückzahl, Sprache oder Display-Verfügbarkeit |
| [VEDES](https://www.vedes.com/c/hilfe-und-infos) | Händlerauswahl nach Standort, Angebote verschiedener lokaler Händler, Versand/Reservierung | Produktbezogenen Händler und tatsächliche Lieferanzeige auswählen; keine pauschale UVP-Garantie |
| [duo](https://www.duo-shop.de/l/bestellablauf/) | Händlerangebote; je Händler Selbstabholung/Drive-in | Abholbarkeit und Termin am konkreten Angebot bestätigen |
| [idee+spiel](https://www.ideeundspiel.com/produkte/spielzeug/sammelkarten/) | Angebote einzelner Fachhändler | Eigener Verkäufer-/Variantenvalidator fehlt; Zugriff kann nach Umgebung variieren |
| [Lidl](https://kundenservice.lidl.de/SelfServiceDE/s/article/Wo-finde-ich-Informationen-zur-Verf%C3%BCgbarkeit-der-Werbeartikel-in-den-Filialen) | Verfügbarkeitsanzeige für bestimmte aktuelle Nonfood-Werbeartikel | Nur für erfasste Aktionen; keine vollständige TCG-Bestandsliste oder künftige Lieferwagenplanung |
| [Kaufland Filiale](https://filiale.kaufland.de/service/haeufige-fragen.html) | Ortsbezogene aktuelle/nächste Angebote, Aktionszeitraum | Prospekt ist keine bestätigte Restmenge; getrennt vom Marketplace |
| [EDEKA](https://www.edeka.de/services/fragen-und-antworten/) | Marktbezogene Sortimente und Angebote; eigenständige Kaufleute | Keine bundesweit einheitliche Bestandsanzeige ableitbar |
| REWE, ALDI, Netto, Globus | Standortbezogene Sortimente, Prospekte und Aktionsankündigungen | Kein allgemeiner öffentlicher SKU-Wareneingangsfeed nachgewiesen |
| [ROFU](https://www.rofu.de/filialen/) | Filialsuche und aktuelle Servicehinweise | Aktuelle Seite sagt, Online-Bestellungen seien nicht möglich. Ältere Click-&-Collect-Artikel reichen nicht als heutiger Funktionsnachweis |

**Müller konkret:** SKU 3179589 zeigte 6,39 € und „Aktuell nicht lieferbar“ sowie „Filialverfügbarkeit prüfen“. Der Filialbutton beweist keinen Bestand. Eine Browser-Verifizierung verhinderte die Auswahl; kein Alert. Dies war ein einzelner Booster als Schnittstellenprobe, kein Display-Angebot.

Für „vor Ort Lieferungen“ gibt es drei verschiedene nützliche Signale:

1. **Heute in Filiale verfügbar:** konkrete SKU + Filial-ID + aktueller Status/Abholzeitpunkt.
2. **Ware kommt voraussichtlich:** Händler nennt für genau dieses Produkt und diese Filiale ein Datum. Als Lieferankündigung kennzeichnen; keine Bestandsmeldung vor Ankunft.
3. **Community meldet neue Ware:** Foto/Beitrag mit Filiale, Datum und Produkt. Als unbestätigten Hinweis behandeln, besonders bei älteren oder weiterverbreiteten Beiträgen.

Ein zentraler frei zugänglicher deutscher Feed mit allen LKW-Lieferungen oder Händler-Zuteilungen wurde nicht gefunden. Wiederkehrende Liefertage sind ohne konkrete Bestätigung nur ein Muster, kein verlässlicher Droptermin.

## Konkrete regionale Ansatzpunkte für 65934 + 50 km

Die folgende Auswahl sind Rechercheziele im Rhein-Main-Gebiet, keine Meldung vorhandener Ware. Für automatische Radiusfilter fehlen noch geocodierte Filial-IDs und deren artikelbezogene Bestandsantworten.

- [BreakTheCase Frankfurt](https://www.breakthecase.de/): Peter-Bied-Straße 47, 65929 Frankfurt; vorhandener Online-Shop und Abholoption. Bereits bestehender Scanner; Abholung je Variante separat bestätigen.
- [Akihabara Kelkheim](https://akihabara-tcg.de/impressum/): Frankenallee 14, 65779 Kelkheim. Öffentliches Impressum und Online-Katalog vorhanden; Händlerprüfung vor Alerts nicht allein mit der Adresse abschließen.
- [Faix](https://www.faix.de/faix-online-shop-darmstadt/h/unsere-filialen): Main-Taunus-Zentrum Sulzbach, Darmstadt Innenstadt, Loop5 Weiterstadt und Riedstadt. Filialverzeichnis vorhanden; noch kein bestätigter TCG-Filialbestand.
- [Hugendubel](https://www.hugendubel.de/de/category/101686/neue_booster.html): unter anderem Frankfurt Steinweg/Hessencenter, Bad Homburg, Neu-Isenburg, Mainz Brand/Römerpassage und Wiesbaden. Die Liste nennt Booster-Sortiment, keine aktuell verfügbaren Displays.
- [Smyths Frankfurt](https://www.smythstoys.com/de/de-de/storefinder/storedetails/frankfurt-am-main): Nordwestzentrum; Filial-/Abholfunktion dokumentiert, unser Cloudzugriff noch gesperrt.
- Collect-it Dreieich, weitere örtliche Spielwarenläden und offizielle TCG-Spielstätten bleiben zusätzliche Kandidaten. Bei widersprüchlichen Verzeichnisadressen erst die aktuelle Verkaufsstelle prüfen.

[Pokémons offizielle Händlersuche-Hilfe](https://support.pokemon.com/hc/de/articles/360000634514-Wie-finde-ich-heraus-wo-Pok%C3%A9mon-Produkte-verkauft-werden), Event-Locator und [Bandais deutsche Händlerliste](https://www.dbs-cardgame.com/europe-en/shop-locator/list_germany.php) helfen, weitere kleine Shops zu finden. Ältere Turnier-/Demolisten sind keine aktuellen Inventarlisten.

## Weitere kostenlose Hinweiswege

- Händler-Produktseiten, öffentliche Produkt-JSON/JSON-LD, Kategorien, Sitemaps: neue Seiten und Varianten entdecken. Neue URL oder Bilddatei allein bedeutet keinen bevorstehenden Drop.
- [Kartenwacht](https://kartenwacht.de/so-funktionierts): Preis-/Community-Hinweise; Veröffentlichungsverzögerungen beachten. Keine Live-Bestandsgarantie übernehmen.
- Cardwatch-Händlerverzeichnis: öffentlich für Discovery brauchbar. Ein zeitlich begrenzter kostenloser Test des eigentlichen Monitors ist keine dauerhaft kostenlose Bot-Architektur.
- [RestockRadar](https://restockradar.de/de/haendler/kaufland) und [HoloHeaven](https://www.holoheaven.de/karten-radar): Filialfunde bzw. Aktionsübersichten. Quelle und Alter mitführen, keine automatische Checkout-Bestätigung.
- [Mydealz-Alarme](https://help.mydealz.de/help/wie-werde-ich-informiert-wenn-deals-die-mich-interessieren-veroffentlicht-werden), Händlernewsletter und [Preisalarme](https://www.billiger.de/info/faq/preisalarm): zusätzliche Discovery nach Einrichtung eines eigenen Kontos/Postfachs. Hier keine Anmeldung oder Weiterleitung vorgenommen.
- Öffentliche Händlerposts auf X, Instagram, Facebook, Telegram/Discord-Ankündigungen: Produkt, Filiale, Datum und ursprünglichen Verfasser prüfen. Kein verlässlicher kostenloser vollständiger X-Datenstrom für Deutschland nachgewiesen. Geschlossene Gruppen oder fremde private Feeds wurden nicht verwendet.
- Öffentlich angekündigte Hersteller-Releases und Händler-Vorbestellungswellen: Startsignal für häufigere Prüfungen; Release-Datum ist nicht gleich Wareneingang eines bestimmten Händlers.

## Sinnvolle Umsetzung im bestehenden kostenlosen System

1. Bestehende schnelle Produktprüfungen und validierte Discord-Alerts beibehalten.
2. Neue Händler-/Produktkandidaten langsam rotierend sammeln, dann gezielt die reichhaltigsten Quellen VEDES/duo und konkrete regionale Angebote validieren.
3. Filialdaten mit eigener Identität speichern: Händler, Filial-ID, PLZ/Ort, SKU/EAN, Sprache, Status, Abhol-/Liefertermin, Prüfzeitpunkt, Beleg-URL. Fehlende oder gesperrte Daten als unbekannt behandeln, nicht als ausverkauft.
4. Hinweise und Kaufmeldungen getrennt halten. Erst bestätigter Bestand/Checkout plus passende Sprache und Preis qualifiziert für Discord. Keine Prospekt-, Suchindex- oder Community-Sichtung als „sofort lieferbar“ ausgeben.
5. Unbekannte Händler vor Alerts prüfen; niedriger Preis allein genügt nicht. Höchstens 200 € betrachten, bestehende Sprach-/Themen-/Produktregeln gelten weiter.
6. GitHub-Zeitplan bleibt fünf Minuten; tatsächliche Starts können verzögert sein. Keine ständigen Browser-Runs für alle Händler, keine neuen bezahlten Dienste, keine Abhängigkeit vom eingeschalteten Nutzer-PC.

Die neun hinzugefügten Rechercheeinträge liefern noch keine vollautomatischen Filialalerts. Dafür sind die konkreten Verkäufer-/Filial- und Variantenprüfungen der nächste Implementierungsschritt. Pokémon-Center-Livebestand bleibt eine offene Lücke, ausdrücklich nicht als gelöst markiert.


## Prüfung und Reproduktion

- Konfiguration validiert; 372 Python-Tests bestanden. Bestehende Worker- und GitHub-OIDC-Tests bestanden.
- Auditquellen: `free-cloud-targets-2026-10-25.json`; Auswertung: `../scripts/audit_free_cloud.py`; temporärer Worker: `../cloudflare/mms-reader/research-worker.mjs`.
- Der einmalige Audit-Schritt wurde wieder aus dem regulären Workflow entfernt. Kein zusätzlicher periodischer Browserverbrauch. Der separate Recherche-Worker wurde nach dem Test gelöscht; `tcg-mms-reader` bleibt produktiv.
- Zur bewussten Wiederholung muss der separate Worker mit neuer, kurzer Ablaufzeit erneut bereitgestellt und der Audit im autorisierten GitHub-Kontext gestartet werden. Der archivierte Endpunkt ist keine produktive Bot-Abhängigkeit.
