# Anime TCG Retail Watch · Discord · 0 €

Ein kleiner Python-Bot prüft bekannte Produktziele nach einem Fünf-Minuten-Zeitplan und durchsucht stündlich die Händlerkataloge und meldet passende Display-Angebote in deinen Discord-Kanal. Kein bezahlter Suchdienst, keine KI-API, kein n8n-Abo, kein laufender PC. Python benötigt keine Zusatzpakete.

**Fertig vorbereitet, noch nicht auf deinem GitHub-Konto aktiviert.** Der Bot sendet erst, wenn du ihn mit deinem Discord-Secret startest. Das kostenlose Setup verwendet ein **öffentliches** GitHub-Repository und den normalen Linux-Runner. Für private Repositories startet der mitgelieferte Workflow absichtlich nicht.

## Einrichtung in drei Schritten

### 1. Discord-Webhook erstellen

Öffne deinen Discord-Server → **Servereinstellungen → Integrationen → Webhooks → Neuer Webhook**. Wähle einen normalen Textkanal, z. B. `#tcg-deals`, und kopiere die Webhook-URL. Dafür brauchst du „Webhooks verwalten“. Eine eigene Bot-Anwendung ist nicht erforderlich. Die URL gehört ausschließlich ins GitHub-Secret aus Schritt 3, nicht in Dateien oder einen Chat.

### 2. Das Projekt auf GitHub hochladen

- ZIP entpacken, bei GitHub anmelden und über **New repository** ein **öffentliches** Repository `tcg-deal-bot` anlegen. Der kostenlose GitHub-Tarif reicht.
- Über **uploading an existing file** / **Add file → Upload files** den **Inhalt** des entpackten Ordners hochladen. Wichtig: auch den Ordner `.github` mitnehmen! Keinen zusätzlichen äußeren `tcg-deal-bot`-Ordner im Repository erzeugen.
- Mit **Commit changes** speichern. Im Repository müssen `README.md`, `config/`, `tcg_bot/`, `tests/` und `.github/workflows/watch.yml` direkt an der richtigen Stelle liegen. `main` bleibt der Standardbranch.

### 3. Secret setzen und ersten Lauf starten

- Repository → **Settings → Secrets and variables → Actions → New repository secret**.
- Name exakt **`DISCORD_WEBHOOK_URL`**, als Wert die kopierte Discord-URL einfügen, speichern.
- **Actions → TCG Deal Watch → Run workflow**. Für den tatsächlichen Start das Häkchen bei **„Nur prüfen, keine Discord-Nachrichten senden“ entfernen** und starten. Mit Häkchen gibt es ausschließlich eine Vorschau im Laufbericht.
- Bekannte Produkte werden anschließend alle **fünf Minuten** eingeplant (xx:02, :07, :12 usw.). Um **xx:17** erfolgt zusätzlich die Katalogsuche. GitHub kann Starts verzögern oder auslassen; dazu kommt die Abrufdauer. Das ist keine garantierte Echtzeitüberwachung. Wenn Actions einen Aktivieren-Button zeigt, einmal aktivieren. Unter dem ersten Lauf findest du erfolgreiche Quellen, Filter und eventuelle Probleme. Ohne passende Angebote bleibt Discord still; es wird keine künstliche Testnachricht gesendet.

Der Workflow besitzt die nötige `contents: write`-Berechtigung bereits. Verhindert eine Organisationsrichtlinie das Schreiben, muss diese Richtlinie bzw. die Freigabe für Actions angepasst werden; bei einem normalen persönlichen Repository ist keine zusätzliche Einstellung vorgesehen.

## Händlerabdeckung der erweiterten Version

**Zehn angeschlossene Quellen:** die bisherigen fünf Shops sowie MediaMarkt, Saturn, Otto, Gate to the Games und Ultra Comix. Otto liefert momentan ausschließlich Prüfkandidaten, keine automatisch freigegebenen Angebote. Großhändlerabfragen sind zunächst auf verifizierte Pokémon-Kategorien begrenzt. Fachhändler erkennen zusätzlich die gewünschten Anime-Reihen.

Die detaillierte, ehrliche Trennung zwischen **automatischer Überwachung**, **Kandidatenerkennung** und **nicht angebundenen Quellen** steht in [QUELLEN.md](QUELLEN.md). Insbesondere Cardmarket, Müller, Smyths und Kaufland sind nach dem aktuellen Zugriffstest nicht aktiv angebunden. Die Filial-Suchregion ist **65934 mit 50 km Umkreis**. Ein verlässlicher Filialadapter ist noch nicht vorhanden; die Standortkonfiguration aktiviert daher noch keine Bestandsmeldungen.

Zehn Produkt-/Sprachregeln mit 16 konkreten Händlerbindungen sind vorbereitet. Neu sind Reisegefährten Top-Trainer-Boxen DE bei MediaMarkt/Saturn und Fairy Tail 100 Years Quest 12er-Displays EN bei Gate to the Games/Ultra Comix. Die vollständigen Preise, Belege und Bindungen stehen in `config/config.json`. Referenzen mit gültiger EAN können auch händlerübergreifend greifen, wenn Titel, Sprache, Preis und Verkäufer ebenfalls passen. Es wird keine automatische Hersteller-UVP aus Marktpreisen abgeleitet.

Alle ursprünglichen Reihen bleiben als Suchregeln eingerichtet: Pokémon, Dragon Ball, JoJo, Fairy Tail, Bleach, One Piece, My Hero Academia, Naruto, Digimon und weitere Anime-TCGs. Für JoJo, Bleach und My Hero Academia fehlen weiterhin konkrete freigegebene Preisreferenzen. Neue bestellbare Displays können jetzt trotzdem als ungeprüfte Entdeckung gemeldet werden.

Keine freie Vollwebsuche, keine Garantie aller Händler oder aller Produkte. Händler-Referenzpreise sind keine bestätigten Hersteller-UVPs und kein bundesweiter Bestpreis einschließlich Versand. Katalogabfragen sind begrenzt; explizit beobachtete Produktseiten werden zusätzlich geprüft. Die bestehenden Referenzen laufen am 17.12.2026 ab und müssen anhand aktueller Belege erneuert werden.

## Regeln gegen Fehlalarme

- Exakte Zuordnung über Händler, Produktpfad und Varianten-ID oder freigegebene gültige GTIN; zusätzlich Prüfung von Titel, Variantenbezeichnung, Sprache und Format.
- Keine Ableitung eines Displaypreises aus dem billigsten Einzelbooster einer Produktseite.
- Fehlende/ungültige Preise, andere Währungen, Japanisch/Chinesisch/Koreanisch, Einzelkarten, Hüllen, Cases, B-Ware und nicht freigegebene Produktarten werden verworfen.
- Händlerverfügbarkeit muss explizit `true` sein. Vorbestellhinweise im Titel oder der Beschreibung sperren die Einstufung als sofort lieferbarer Retail-Treffer auch dann. Die separate Entdeckungsmeldung erlaubt bestellbare Vorbestellungen und kennzeichnet sie. Alte Vorbestellhinweise können deshalb einen eigentlich lieferbaren Artikel vorsorglich unterdrücken.
- Referenzen laufen am **17.12.2026** ab. Danach keine Meldungen für diese Regeln, bis die Belege neu geprüft und Daten verlängert wurden. Der Actions-Lauf weist schon 14 Tage vorher darauf hin und wird als prüfbedürftig markiert.
- Deutsch wird gegenüber Englisch **für dasselbe Set, dieselbe Edition und Packgröße** bevorzugt, solange ein passendes deutsches Angebot den Preisfilter besteht. Englische Angebote anderer Sets bleiben sichtbar.
- Produktpreise sind Händler-Endkundenpreise; **Versand kommt dazu und wird nicht automatisch ermittelt**. Die Nachricht benennt das ausdrücklich. Der Bot verspricht keinen günstigsten Gesamtpreis einschließlich Versand.
- Keine künstliche Obergrenze für passende Meldungen pro Lauf. Discord-Ratelimits werden weiterhin berücksichtigt.
- Unveränderte Angebote werden nicht wiederholt. Erneute Meldung erst bei beobachtetem Wechsel „ausverkauft → verfügbar“ oder mindestens **5 € und 5 %** Preisrückgang, ohne zusätzliche Wartezeit. Die frühere Sechs-Stunden-Sperre ist deaktiviert; unveränderte verfügbare Angebote bleiben trotzdem still.
- Ausfall eines Shops oder verschwundene Produkte gelten **nicht** als „ausverkauft“. Ein Restock kann nur erkannt werden, wenn der Bot zuvor ausdrücklich „nicht verfügbar“ gesehen hat.

## Speicherung und Fehler

Der Bot speichert zuletzt beobachtete Bestände und bestätigte Meldungen dauerhaft im separaten Git-Branch **`bot-state`**. Kein flüchtiger Actions-Cache und keine kostenpflichtige Datenbank. Der Branch enthält öffentliche Händler-/Variantenkennungen, Bestandsflags und Discord-Nachrichten-IDs, **keine Webhook-URL**. Er wird nur bei tatsächlichen Änderungen aktualisiert. Nicht löschen, sonst werden bekannte Angebote wieder als neu angesehen.

Parallel laufende Bot-Workflows werden verhindert. Der Versand wartet auf Discord-Bestätigung; erst danach wird ein Angebot als gemeldet gespeichert. Auch nach einem Teilfehler sichert der Workflow bereits bestätigte Meldungen. Bei einem harten Abbruch genau zwischen Discord-Versand und Git-Sicherung oder bei verlorener Versandantwort kann trotzdem eine doppelte Nachricht entstehen. Eine mathematische Exactly-once-Garantie ist mit Webhook und Git nicht möglich.

Ein Shopfehler blockiert die anderen Shops nicht, führt aber zu einem fehlgeschlagenen Actions-Status mit Hinweis im Bericht. Bei vollständigem Ausfall wird nichts gemeldet und kein künstlicher Bestandswechsel erzeugt. 403/429/CAPTCHA oder robots.txt-Sperren werden nicht umgangen. Discord-429 wird begrenzt wiederholt; unsichere Timeouts werden nicht unmittelbar erneut gesendet. Geheimnisse und rohe Fehlermeldungen mit URLs werden nicht ausgegeben.

**GitHub-Grenzen:** Zeitpläne sind Best Effort; Starts können verspätet oder ausgelassen werden. Bei öffentlichen Repositories können geplante Workflows nach 60 Tagen ohne Repository-Aktivität deaktiviert werden. Gelegentlich im Actions-Tab prüfen und nötigenfalls wieder aktivieren. Der Bot erstellt keine künstlichen Keep-alive-Commits. Kostenfreiheit gilt für die mitgelieferte öffentliche Standardrunner-Architektur nach dem unten verlinkten GitHub-Preismodell; es werden weder größere Runner noch bezahlte APIs oder Artefaktarchive angefordert.

## Regeln und Händler erweitern

1. Im Actions-Lauf die Kandidaten ansehen; lokal enthält `report.json` zusätzlich Links, Produktpfade und Varianten-IDs.
2. Genaues Set, Edition, Sprache, Packzahl und versiegelten Zustand auf der Produktseite prüfen. Eine Hersteller-/Distributoren-UVP in EUR oder einen plausiblen belegten regulären Händlerpreis eintragen. Ein durchgestrichener „Compare-at“-Preis wird nicht als UVP akzeptiert. Keine aktuellen Scalperpreise zur Referenz machen.
3. `config/reference-template.json` kopieren und ausgefüllt in die Liste `references` von `config/config.json` aufnehmen. Das Template ist absichtlich ungültig, bis Preis, Datum, Identität und Belege ersetzt wurden. `variant_id` bleibt eine Zeichenkette. `variant_pattern` muss genau die verifizierte Variante erlauben.
4. `group` ist nur bei identischem Set/Edition/Packformat sprachübergreifend gleich. `kind: "msrp"` nur mit echtem Herstellerbeleg; sonst `observed_retail`. Toleranz standardmäßig 0 %, technisch höchstens 5 %.
5. Für einen weiteren Shopify-Shop einen Eintrag unter `shops` ergänzen. `currency: "EUR"` nur nach Prüfung des Shop-Endpunkts und der deutschen Endkundenpreise eintragen. Das öffentliche Shopify-JSON liefert selbst keine Währungskennung. Händler müssen nach Deutschland liefern. HTML-/Marktplatzadapter stehen in `tcg_bot/web_sources.py`; ihre Grenzen und Konfigurationsfelder sind in `QUELLEN.md` dokumentiert.
6. Danach den Workflow mit Vorschau-Häkchen ausführen und den Bericht prüfen.

Die Händlerdaten stammen aus öffentlichen JSON-Endpunkten und HTML-Seiten, aber nicht aus garantierten Langzeit-APIs. Anpassungen bei Shop-Umbauten bleiben gelegentlich nötig.

## Lokal testen (optional)

Python 3.12 oder neuer verwenden, im Projektordner:

```bash
python -m unittest discover -s tests -v
python -m tcg_bot --check-config
python -m tcg_bot
```

Der Standardaufruf ist immer **Dry Run**: kein Secret notwendig, keine Nachrichten, kein Schreiben der Statusdatei. `report.json` enthält den Bericht. Nur `python -m tcg_bot --send` sendet; dafür muss `DISCORD_WEBHOOK_URL` als Umgebungsvariable gesetzt sein. `.env.example` erklärt den Namen, echte `.env`-Dateien werden nicht automatisch geladen und dürfen nicht hochgeladen werden.

## Prüfstand und Quellen

Offline-Tests decken Preisfilter, Varianten, Sprache, Vorbestellungen, Zubehör, Wiederholungen, Restocks, Teilausfälle, Discord-Rate-Limits und Statusdateien ab. Live-Händlerprüfung erfolgte ohne Discord-Versand. Ein echter GitHub-Actions-Lauf und die Zustellung in deinen Discord-Kanal sind erst nach deiner Einrichtung prüfbar. Details stehen in `PRUEFBERICHT.md`.

- [GitHub: kostenlose Actions für öffentliche Repositories mit Standardrunnern](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [GitHub: Zeitpläne, Verzögerungen und 60-Tage-Regel](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [Discord: Webhooks, Versandbestätigung und erlaubte Erwähnungen](https://docs.discord.com/developers/resources/webhook#execute-webhook)
- Händlerbelege pro Produkt: `config/config.json`.

## Geschwindigkeit

Explizit konfigurierte Produktbindungen werden alle fünf Minuten eingeplant. Der Schnelllauf überspringt die Katalogsuche und prüft die bekannten Produktseiten direkt. Nach Abschluss der Prüfung werden passende neue Treffer und Restocks ohne zusätzliche Sammelwartezeit an Discord geschickt. Deutsch-Präferenz wird über die Ergebnisse des Laufs ausgewertet.

Nur über Kataloge/EAN neu entdeckte Angebote werden weiterhin stündlich geprüft, bis ihre konkrete Produktseite als Bindung aufgenommen wurde. Es gibt keinen Push-Zugang der Händler. Kurzzeitige Bestände zwischen zwei Abfragen können verpasst werden. Fehlende Filialadapter und blockierte Quellen werden durch den schnelleren Zeitplan nicht verfügbar. GitHub-Konfiguration und Discord-Secret müssen weiterhin eingerichtet sein; dieses ZIP startet allein noch keinen Dienst.

## Neue Produkte automatisch melden

Aktiv unter `discoveries` in `config/config.json`: Neue Displays/Booster-Boxen der konfigurierten Reihen werden auch ohne Preisreferenz gemeldet, mit **„Neu entdeckt – Preis noch ungeprüft“**. Beispiel: Dragon Ball FB10 EN. Voraussetzung: Händler meldet ausdrücklich bestellbar (`available: true`), DE/EN ist erkennbar, EUR-Preis vorhanden und Verkäufer verifiziert. Bestellbare Vorbestellungen sind erlaubt und werden als Vorbestellung gekennzeichnet. Ausverkaufte Artikel und unbekannter Bestand werden nicht gemeldet. Zubehör, Cases, fremde Sprachen und ungeprüfte Marketplace-Verkäufer bleiben ausgeschlossen.

Das ist eine Produktentdeckung, keine Preisempfehlung: Ohne Vergleichspreis lässt sich ein hoher Preis nicht zuverlässig als Scalperpreis erkennen. Bereits referenzierte zu teure Produkte werden nicht über diese Meldungsart durchgelassen. Geprüfte Retail-Angebote und Restocks behalten ihre bisherigen Regeln.

Einmal pro Händler und Variante; derselbe Artikel bei einem anderen Händler kann eine weitere Meldung auslösen. DE-Meldungen werden zuerst versendet; ohne sicher bekannte Set-Identität werden EN-Varianten nicht automatisch unterdrückt. Bis zu zehn neue Produktmeldungen pro Lauf, weitere werden bei späteren Katalogabfragen erneut berücksichtigt. Nur erfolgreich gesendete Meldungen werden in `discovery_seen` auf dem vorhandenen `bot-state`-Branch bestätigt. Der beim Update bereits bekannte verfügbare Bestand dient als Ausgangsstand, ohne alte Produkte nachträglich zu fluten. Eine später hinzugefügte Preisreferenz kann weiterhin eine geprüfte Deal-Meldung auslösen.

Entdeckungen entstehen bei der **stündlichen, begrenzten Katalogsuche**, nicht durch eine Vollwebsuche. Neue ungeprüfte Produkte werden dadurch nicht automatisch in die Fünf-Minuten-Prüfung aufgenommen. Otto bleibt reine Kandidatenquelle. X ist nicht angebunden. Händlerfehler und fehlende Filialadapter bleiben sichtbar.
