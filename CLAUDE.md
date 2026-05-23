# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projekt

**Bewerbungsagent von Claudia** — ein Multi-Agent-System, das automatisch Stellen sucht, gegen Claudias Profil bewertet und passende Bewerbungsunterlagen erstellt.

**Arbeitssprache:** Deutsch (Code-Kommentare, Ausgaben, Dateinamen)

---

## Über Claudia

- **Rolle:** Senior Product Owner / Project Manager (20+ Jahre Erfahrung)
- **Status:** Freigestellt bei Accor, verfügbar ab sofort
- **Letzter Job:** Director Digital Products ENA bei Accor (Europa & Nordafrika, 3.100 Hotels)
- **Weitere Erfahrung:** eCommerce Manager Northern Europe, Project Manager Revenue Management, Revenue Manager (Accor / FTI / Starwood)
- **Auszeichnung:** HSMAI European Gold Award 2016 (MiceTracker)
- **Zertifizierungen:** CSPO, CPUX-F (Jul 2026), AI Powered PO (Mai 2026), A-CSPO (laufend)
- **Standort:** München Laim — bevorzugt Hybrid (2–3 Tage Office) oder Remote
- **Pendelbereitschaft:** max. 30 Minuten mit Fahrrad / MVV
- **Gehalt:** 80.000–95.000 € brutto/Jahr
- **Branchen-Präferenz:** HealthTech, InsurTech, FinTech, Travel/Mobility, regulated industries
- **Ausschlusskriterien:** reine PM-Rollen ohne Produktverantwortung, vollständig On-Site, Standorte außerhalb Münchens ohne Remote, Startups ohne gesicherte Finanzierung, unter Senior-Level

Das vollständige Profil liegt in `profil.txt`.

---

## Agent-Architektur (Zielzustand)

```
Orchestrator
├── Search Agent       — sucht Stellenanzeigen und Firmeninfos im Web
├── Analyst Agent      — scored Stellen gegen Claudias Profil (1–10)
├── Writer Agent       — erstellt Anschreiben, passt CV an
└── Output Agent       — speichert Ergebnisse strukturiert (Tabelle, Dateien)
```

### Orchestrator
Koordiniert den Gesamtablauf: nimmt einen Job-Suchauftrag entgegen, delegiert an die Unteragenten in der richtigen Reihenfolge und gibt das Endergebnis aus.

### Search Agent
Wiederverwendbar für verschiedene Suchen: Stellenanzeigen, Firmen-Research, Branchen-Infos. Gibt strukturierte Rohdaten zurück.

### Analyst Agent
Bewertet eine Stelle gegen `profil.txt`. Output-Format:
- `SCORE` (1–10)
- `BEGRUENDUNG` (2–3 Sätze)
- `STAERKEN` (was passt)
- `LUECKEN` (was fehlt)
- `EMPFEHLUNG` (Bewerben / Überspringen)

### Writer Agent
Erstellt auf Basis von Profil + Stellenanzeige ein individuelles Anschreiben und schlägt CV-Anpassungen vor.

### Output Agent
Speichert Ergebnisse strukturiert: Bewertungstabelle (CSV oder Markdown), Anschreiben als `.txt` oder `.docx`, Statustracking der Bewerbungen.

---

## Aktueller Stand

`hallo_agent.py` ist ein einfacher Proof-of-Concept: lädt `profil.txt` + `stelle.txt`, ruft Claude direkt auf und gibt die Analyst-Ausgabe aus. Noch kein Orchestrator, kein Search Agent, kein Writer Agent.

### Ausführen (aktueller PoC)

```bash
pip install anthropic python-dotenv
python hallo_agent.py
```

Neue Stelle testen: `stelle.txt` mit dem Anzeigentext überschreiben, dann Script neu starten.

### Umgebung

API-Key in `.env` als `ANTHROPIC_API_KEY`. Modell aktuell: `claude-haiku-4-5-20251001` — für höhere Qualität auf `claude-sonnet-4-6` wechseln.

---

## Sicherheitsregeln (höchste Priorität)

- **Keine Downloads** von unbekannten Quellen — weder Code noch Dateien
- **Erklären vor Ausführen** — jede Aktion wird beschrieben, bevor sie ausgeführt wird
- **Keine externen Abhängigkeiten** ohne explizite Zustimmung von Claudia
- **Keine API-Calls** an Dienste außer Anthropic ohne vorherige Absprache
- **Profil- und Bewerbungsdaten** (profil.txt, Anschreiben) verlassen das lokale System nicht — sie werden nicht in Logs, Git-Commits oder externe Services übertragen
