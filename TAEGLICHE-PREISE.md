# Tägliche Preisübersicht

Die gemeinsame Auswahl und die Kanalregeln stehen in [TCG-WATCH.md](TCG-WATCH.md).

Die regulären Live-Scans sammeln am selben Tag geprüfte Angebote in `state.daily_price_overview`. Preis, Händler, Produktvariante, Sprache und Prüfzeitpunkt bleiben erhalten. Fehlende Retailreferenzen verhindern die Aufnahme nicht; sie werden gekennzeichnet. Verfügbarkeit, Sprache, Händlerprüfung und 200-Euro-Grenze bleiben erforderlich. Bestätigte Ausverkäufe bzw. Preisänderungen entfernen alte Einträge.

Dieser gespeicherte Überblick ist keine Echtzeitgarantie. Die zentrale Chat-Recherche muss Prüfzeitpunkte nennen und vor Kaufhinweisen oder neuen Discord-Alerts nochmals aktuell validieren. Die Sammlung allein erzeugt noch keinen ChatGPT-Zeitplan.

Seit 27.10.2026 ist die Discord-Tagesübersicht aktiviert: `discord_enabled=true`, `repeat_daily=true`, `require_good_retail=true`. Jedes passende Angebot darf an jedem Kalendertag in **Europe/Berlin** einmal erscheinen, auch bei unverändertem Preis seit gestern. Es wird erst gepostet, wenn die konkrete Variante im aktuellen Lauf erneut als bestellbar bestätigt wurde. Der Versand verteilt sich auf kurze Blöcke in den normalen Läufen, ohne zusätzliche Infrastruktur oder festen separaten Zeitplan.

Die Tagesübersicht enthält belegte gute Retailpreise und Angebote höchstens 5 % darüber, mit klarer Kennzeichnung. Ein bloßer Cardmarket-Vergleich, eine Nutzerorientierung oder ein Händler-Median ohne Retailbeleg reicht dafür nicht. Fehlende Belege bleiben im internen Überblick sichtbar. Bereits heute als Sofortmeldung gesendete unveränderte Angebote werden nicht zusätzlich im Tagesblock wiederholt. Neue Restocks und relevante Preissenkungen nutzen weiterhin ihren eigenen Sofortmelde-Duplikatschutz. Fehlgeschlagene Discord-Sendungen werden nicht als zugestellt gespeichert.

## Automatische Preisrecherche

`tcg_bot/retail_research.py` läuft vor der Tagesauswahl im normalen Fast Watch. Es verwendet zunächst die bereits frisch validierten Händlerangebote, dann bekannte passende Produktseiten und öffentliche Händler-Suchfunktionen (Comic Planet sowie rotierende Shopify-Shops). Suchpreise und Bestands-Snippets sind nur Hinweise: Die konkrete Produktseite/Varianten-JSON und das Bestellformular müssen den Preis bestätigen. Sprache, Ausgabe, Packungsform, Verkäufervertrauen und die konservative Produktidentität müssen übereinstimmen.

Neue Händler-Retailreferenzen werden nur von den ausdrücklich konfigurierten Vergleichshändlern übernommen: MediaMarkt, Saturn, Müller, FAIX, CardCatcher und Comic Planet. Andere geprüfte Shops dürfen einen bereits belegten Normalpreis nur zum selben oder einem niedrigeren aktuellen Preis erneuern. Abgelaufene Belege werden niemals allein durch Ändern des Datums verlängert. Ein aktueller Händlerpreis ist **keine Hersteller-UVP**; Quelle und Prüfdatum bleiben sichtbar. Cardmarket bleibt ein separater Wiederverkaufsvergleich.

Abweichende Händlertitel dürfen über eine eindeutig passende Produktkatalog-ID zusammengeführt werden, sofern Sprache, Ausgabe, Produkttyp und Packungsgröße übereinstimmen. Dabei dient der Cardmarket-Katalog ausschließlich zur Produktzuordnung; sein Preis wird nicht zum Retailbeleg umgedeutet. Das ermöglicht beispielsweise, einen bereits belegten und frisch bestätigten FB03-Händlerpreis auch einem anders benannten FB03-Angebot zuzuordnen.

Pro Lauf höchstens zwei offene Produktidentitäten, zwölf gezielte Aufrufe und 18 Sekunden Recherche; bereits frisch geprüfte Varianten werden nicht doppelt abgerufen. Offene Kandidaten rotieren, erfolglose Recherchen werden nach sechs Stunden erneut versucht; Budgetabbrüche nach frühestens fünf Minuten. Die Ergebnisse und Gründe stehen unter `retail_research` im Report und State. Erfolgreiche Belege gelten höchstens 24 Stunden, anschließend ist eine neue Prüfung nötig. Neue Belege können noch im selben Lauf die Tagesmeldung ermöglichen. Unzugängliche Quellen oder fehlende genaue Produktzuordnung werden nicht durch erfundene Referenzen ersetzt.

Keine neuen Secrets, kostenpflichtigen Suchdienste oder Änderungen am bestehenden Fünf-Minuten-Zeitplan.

Tests: `python -m unittest discover -s tests -v`.
