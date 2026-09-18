# Vorläufiger PC-Betrieb

Windows-Aufgabe: **TCG Deal Watch PC**, alle fünf Minuten und bei Anmeldung. Der Benutzer muss angemeldet, der PC wach und online sein. Ein gesperrter Bildschirm ist in Ordnung. Kein Aufwecken aus dem Energiesparmodus, keine Änderung an den Energieeinstellungen.

Überlappende Läufe werden übersprungen; ein weiterer Prozess wird zusätzlich durch eine Sperre verhindert. Nachgeholte Starts werden nicht mehrfach parallel ausgeführt.

Der Discord-Zugang liegt mit Windows-DPAPI für den aktuellen Benutzer verschlüsselt im privaten Laufzeitverzeichnis `work/tcg-pc-runtime` der Arbeitsmappe. Nicht in GitHub oder ZIP-Dateien hochladen. Der bisherige GitHub-Meldungsstand wurde übernommen.

Der Cloud-Zeitplan wurde entfernt, um doppelte Meldungen zu verhindern. Ein manueller Cloud-Start ist weiterhin möglich, sollte aber nicht parallel erfolgen.

**Pausieren:** Windows-Aufgabenplanung → Aufgabenplanungsbibliothek → TCG Deal Watch PC → Deaktivieren. Zum Fortsetzen Aktivieren.

Die Projektmappe nicht löschen oder verschieben: Die Aufgabe startet `pc/run.ps1` von dort. Python wird aus der vorhandenen lokalen Codex-Laufzeit verwendet. Bei einer Entfernung oder Änderung dieser Laufzeit muss der Python-Pfad in den lokalen Einstellungen angepasst werden.

Der letzte Laufbericht und der Meldungsstand liegen privat unter `work/tcg-pc-runtime`. Fehler einzelner Händler können den Lauf als fehlerhaft markieren, obwohl andere Händler erfolgreich geprüft und Meldungen gesendet wurden.
