# Scoring-Kriterien — Claudias Bewerbungsagent

Diese Datei steuert wie der Agent Stellen bewertet.
Einfach bearbeiten, speichern — Änderungen gelten beim nächsten Lauf sofort.

---

## 1. Standort-Regeln

Diese Prüfung läuft immer zuerst.
Bei Verstoß: Score 2, Empfehlung "Nicht passend" — keine weitere Analyse.

**Akzeptiert:**
- München (max. 40 Min. von Laim/Westend per Fahrrad oder MVV)
- Remote (100% oder überwiegend, Deutschland-basiert)
- **100% Remote (Deutschland)** gilt als vollständig akzeptiert, auch ohne Münchner Standort — kein Score-Abzug, kein Hinweis in LUECKEN nötig
- Formulierungen wie "remote", "homeoffice", "deutschlandweit", "von überall" ohne konkrete Ortsangabe → akzeptiert, kein Abzug
- Hybrid mit mindestens 2 Tagen Home Office pro Woche
- "Home Office möglich", "flexibles Arbeiten", "mobiles Arbeiten" — gilt als Hybrid
- Im Zweifel (Arbeitsmodell unklar, Standort München): akzeptiert, Hinweis in LUECKEN

**Nicht akzeptiert — Score 2, Abbruch:**
- Andere Städte mit explizitem On-Site ohne jede Remote-Erwähnung
- Ausland ohne Remote-Möglichkeit

**Wichtig:** Remote-Stellen dürfen NICHT mit Score-Abzug bestraft werden.
Eine Stelle mit 100% Remote erhält denselben Standort-Score (2/2) wie eine Münchner Stelle.

---

## 2. Harte Ausschlusskriterien

Wenn eine dieser Bedingungen zutrifft: Score 2, kein Anschreiben.

- FinTech (Banken, Trading, Brokerage, Krypto)
- Reine Sales-Rolle ohne Produktverantwortung
- Junior / Associate Level (inhaltlich oder Gehalt unter 75.000 €)

---

## 3. Scoring-System

Maximale Punktzahl: **20 Punkte**
Der Agent vergibt Rohpunkte und rechnet diese auf eine Skala von 1–10 um:
**Score = (Rohpunkte / 20) × 10**, gerundet auf ganze Zahlen.

Bewertungsregel:
- Explizit genannt & klar erfüllt → volle Punkte
- Impliziert oder unklar → halbe Punkte
- Nicht erkennbar → 0 Punkte, in LUECKEN vermerken

### Rolle & Mandat

- **End-to-End Verantwortung — von Discovery & Vision bis Launch** → 2 Punkte
- **Roadmap-Ownership & Produktvision** → 2 Punkte
- **Automation / Digitalisierung** → 2 Punkte
- **Agentic AI / KI-Produkte / Multi-Agent** → 2 Punkte
- **Stakeholder-Management auf Senior- oder Executive-Ebene** → 1 Punkt
- **Cross-funktionale Zusammenarbeit (Engineering, Design, Business)** → 1 Punkt

### Arbeitsweise

- **Enge Arbeit mit Engineering-Teams / externe Entwicklungspartner** → 2 Punkte
- **Agile Methoden (Scrum, Kanban, Backlog-Ownership)** → 2 Punkte

### Branche & Unternehmen

- **B2B SaaS / digitale Plattform / Tool** → 1 Punkt
- **Behörden / öffentlicher Sektor / E-Government** → 0.5 Punkte
- **Soziales / NGO / Impact-orientiertes Unternehmen** → 0.5 Punkte

### Standort

- **Standort München / Remote / Hybrid — max. 40 Min. von Laim/Westend** → 2 Punkte

### Gehalt

- **Gehalt ≥ 80.000 € explizit genannt** → 1 Punkt

---

## 4. Score-Bedeutung

| Score (1–10) | Rohpunkte (von 20) | Bedeutung | Was passiert |
|--------------|--------------------|-----------|--------------|
| 9–10 | 18–20 | Sehr gut passend | Bewerben, Anschreiben erstellt |
| 7–8 | 14–17 | Gut passend | Bewerben, Anschreiben erstellt |
| 5–6 | 10–13 | Teilweise passend | Überspringen |
| 3–4 | 6–9 | Wenig passend | Überspringen |
| 1–2 | 0–5 | Nicht passend / Ausschluss | Nicht passend |

**Anschreiben werden ab Score 7 (auf der 1–10 Skala) automatisch erstellt.**
Das entspricht ca. 14 von 20 Rohpunkten.
Schwellenwert ändern in `agents/orchestrator.py` → `SCORE_SCHWELLENWERT = 7`

---

## 5. Hinweise für den Agent

- Die Kriterien müssen NICHT wörtlich in der Anzeige stehen — es reicht wenn sie sinngemäß herauslesbar sind. Beispiel: "Scrum" muss nicht stehen wenn agile Arbeitsweise klar erkennbar ist.
- Fehlende Informationen sind KEINE automatische 0 — prüfe ob das Kriterium impliziert ist
- Gehalt wird nur bewertet wenn explizit genannt — sonst neutral, in CON vermerken
- Consulting-Rollen sind akzeptiert wenn ein eigenes digitales Produkt oder klares PO-Mandat erkennbar ist
- Nicht erfüllte oder unklare Kriterien gehören in CON_1 / CON_2 / CON_3
