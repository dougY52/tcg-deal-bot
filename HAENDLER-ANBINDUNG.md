# Zusätzliche Händler: Implementierung und Grenzen

Stand: 03.10.2026. Die Quellennamen allein bedeuten keine bestätigte Bestandsüberwachung.

## Neu im laufenden Bot

- 24 größere Händler/Quellen werden regelmäßig auf Erreichbarkeit und Produktlinks geprüft. Maximal vier pro Lauf, insgesamt 15 Sekunden Zusatzbudget. Derselbe Zugang wird frühestens nach sechs Stunden erneut geprüft. Fortschritt und Fehler stehen im Report und persistent unter `retailer_coverage` im bestehenden State.
- Registriert: Cardmarket, Müller, Smyths Toys, FantasyWelt, Games Island, Galaxus, ROFU, idee+spiel, Kaufland, Rossmann, MediaMarkt, Saturn, Otto, Edeka, Galeria, REWE, Lidl, Aldi Süd, Aldi Nord, Netto, Globus, Thalia, Amazon DE und JPC.
- Startseiten bei Discountern/Buchhändlern sind zunächst Zugangsprüfungen. Sie sind weder vollständige Katalogsuche noch Filialbestand. Produktlinks aus strukturierten Daten bleiben Recherchekandidaten; sie lösen keine Nachrichten aus.
- Müller-Katalog und Pokémon-Markenseite sind als Discovery-Quelle ergänzt. Exakte Produkt-ID, Angebot-ID `itemId`, Händler, aktueller Preis und zugehöriger aktiver Warenkorbbutton werden vor einem Alert separat geprüft. Ein Hinweis auf ausschließliche Filiallieferung zählt nicht als bestätigter Onlinebestand.
- MediaMarkt/Saturn: eigener Live-Prüfpfad statt pauschaler Ablehnung des Adapters. Er verlangt die exakte Produkt-ID, denselben Verkäufer, einen positiven Lieferstatus und explizit `isAvailableAndBuyable=true`. Sprache, Preisanker und Deduplication bleiben Pflicht. Erreichbarkeit vom GitHub Runner ist damit noch nicht hergestellt.
- HTTP-Weiterleitungen innerhalb derselben HTTPS-Domain werden bis maximal drei Schritte unterstützt. Zielpfade unterliegen erneut robots.txt; fremde Domains, Downgrades und Zugangsdaten in URLs werden abgewiesen. Für Discord bleibt die bisherige Weiterleitungssperre erhalten.
- Otto und MediaMarkt/Saturn behalten konkrete Zugangs-/Parserdiagnosen statt eines allgemeinen ValueError ohne Ursache.
- Bestehende Suche, Webhook, Secrets, Statusverlauf, Preisgrenzen und 5-Minuten-Workflow bleiben erhalten. Tests und Cloud-Audit laufen ohne Discord-Nachrichten.

## Tatsächlich beobachtet

Die Prüfungen liefen direkt auf GitHub Actions, nicht nur über eine Suchmaschine.

- MediaMarkt-/Saturn-Produktseiten, Smyths, Kaufland und Cardmarket: bei den getesteten Abrufen HTTP 403.
- Saturn-Neuheitenkatalog: in einem späteren Abruf lesbar, darunter zahlreiche fremdsprachige Marketplace-Produkte. Kein Beleg für bestellbare deutsche Produkte.
- Otto: Produktabruf HTTP 400; der Katalog war teilweise erreichbar. Ein funktionierender Otto-Detail-/Checkout-Adapter ist weiterhin offen.
- Müller: Kataloge und eine konkrete Sammelkarten-Produktseite waren lesbar, weitere Abrufe antworteten 403. Der geprüfte Beispielartikel war nur zur Filiallieferung vorgesehen; JSON-LD meldete trotzdem InStock und ein aktiver Warenkorbbutton war vorhanden. Der neue Validator hält genau diesen Fall zurück. Der Beispielartikel war Topps, kein qualifizierendes Angebot für die vier überwachten TCGs.
- Rossmann: Weiterleitung der robots.txt funktioniert nach der Korrektur; der konkrete ältere Produktlink lieferte anschließend Challenge-/Nicht-gefunden-Seiten.
- Edeka: Angebotsseite lesbar. Keine bestätigte Filialbestandsquelle. PLZ 65934 / 50 km bleibt die Zielregion, es wird kein Regalbestand oder Radiusnachweis erfunden.
- Weitere erreichbare Startseiten bedeuten nicht, dass deren vollständige TCG-Sortimente verfügbar sind.

## Was noch nicht gelöst ist

Es gibt keine Garantie für alle Händler oder alle Produkte. Insbesondere sind Smyths, Kaufland, Cardmarket, Rossmann und Otto noch keine zusätzlichen verifizierten Alert-Quellen. Kein Proxy-Wechsel, CAPTCHA-Umgehen oder Ausgeben von Such-Snippets als Lagerbestand. Keine kostenpflichtigen APIs.

Der neue Workflow `Retailer integration checks` dient Tests und manuellen Zugangsprüfungen. Er hat keine Discord-Secrets und schreibt nicht in bot-state. Der normale Fast Watch übernimmt die kleinen regelmäßigen Zugangsprüfungen.

## Tests

Neue Tests prüfen sichere Weiterleitungen, robots-Verweigerung, Redirect-Schleifen, exakte MediaMarkt-/Saturn-Varianten, Verkäuferwechsel, fehlende Bestellbarkeit, Müller-ID-/Preis-/Buttonbindung, Filiallieferung sowie die Trennung zwischen erreichbarer Webseite und bestätigtem Bestand.
