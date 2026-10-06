# Kartenwacht: Quellen und Nutzen für unseren Bot

Recherche: 06.10.2026. Konfigurationsabgleich mit main, Commit 2638d26fd75a5403eacb446fcfc0fbe292918dac. Keine neuen Scanner oder Preisfreigaben durch dieses Dokument.

## Öffentlich belegte Arbeitsweise

Kartenwacht beschreibt automatische Händlerchecks, eigene Preishistorien und Community-Einreichungen mit Abstimmungen. Öffentliche/Bot-/Discord-Treffer erscheinen gegenüber eingeloggten Mitgliedern verzögert. Die genaue technische Gewinnung je Shop (Parser, Feed, API oder Kooperation) ist in den geprüften Angaben nicht dokumentiert. Eine öffentliche Integrations-API wurde nicht gefunden; daraus folgt kein Beweis, dass es keine gibt. [Funktionsbeschreibung](https://kartenwacht.de/so-funktionierts)

Die aktuelle Startseite nennt 49 deutsche Händler und führt One Piece und Naruto auf; Pokemon und Dragon Ball erscheinen dort nicht als eigene Spielbereiche. Der ältere abrufbare Händlerindex nennt 42. Das sind unterschiedliche Seitenstände, keine belastbare Vollabdeckungszahl. [Startseite](https://kartenwacht.de/)

## Konkrete deutsche Ergänzungskandidaten

Die [Händlerübersicht](https://kartenwacht.de/haendler) nennt für unsere Recherche unter anderem Games Island, Hiveworld, Collect-it, Nerdbank, TobisToys, Comicplanet, Kroko Games, Card Club, CardCatcher, Animeboy, Mulligan TCG, KEEPSEVEN, Feenturm, Freispiel Freiburg und bb-spiele.

Abgleich mit unserem Repository:
- Keiner dieser 15 Namen ist derzeit als eigener Katalogscanner in `shops` hinterlegt.
- Games Island ist bereits unter `retailer_sources` als `online_unvalidated` hinterlegt. Das ist eine vorhandene Quelle zur Erreichbarkeitsprüfung, keine bestätigte vollständige Produkterfassung.
- Andere Kartenwacht-Händler wie CardCosmos, CrispyCards, CardBuddys, Battle Bear, Gate, GeeksHeaven, Fantasia, TCG Garden und Sapphire sind bei uns schon als Shops konfiguriert. Ihre bloße erneute Nennung vergrößert unsere Abdeckung nicht.
- TobisToys/Comicplanet waren bereits Recherchehinweise; der Unterschied zwischen Hinweis und Scanner bleibt ausdrücklich sichtbar.

Collect-it nennt Kartenwacht mit Abholung in Dreieich-Dreieichenhain. Das ist ein sinnvoller lokaler Prüfhinweis, kein geprüfter Filialbestand. [Händlerprofil](https://kartenwacht.de/haendler/collect-it)

Bei Games Island zeigt das Profil viele Einträge ohne numerischen Preis. Auch Kartenwacht liefert dort keinen lückenlosen Preisnachweis. [Händlerprofil](https://kartenwacht.de/haendler/games-island)

## Umsetzungsschlussfolgerung

Die öffentliche Übersicht eignet sich zur Auswahl zusätzlicher Händler und konkreter Produkt-URLs. Für unseren schnellen Watch anschließend direkt beim Händler prüfen: korrekte Variante/Sprache, Preis, Versand, Checkout und Verkäufernachweise. Betreibergruppen und bestehende Quellen deduplizieren.

Keine ungeprüfte Weiterleitung fremder Dealmeldungen; keine Umgehung der Mitglieder-/Veröffentlichungsverzögerung. Eine Händlerliste ersetzt keinen getesteten Adapter. Die tatsächliche Anbindung erfordert pro Shop Produktprüfung, passende Erfassung und Tests und wurde in dieser Recherche noch nicht vorgenommen.

Aktueller Nutzerfokus: Deutschland; keine Erweiterung um ausländische Händler. Bestehende 14 Auslandseinträge bleiben aus.
