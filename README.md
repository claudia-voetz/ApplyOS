# Bewerbungsagent – Claudia

Multi-Agent-System: automatische Jobsuche, Bewertung gegen Claudias Profil und Erstellung individueller Bewerbungsunterlagen.

## Installation

```bash
pip install anthropic python-dotenv flask
```

API-Key in `.env`:
```
ANTHROPIC_API_KEY=sk-...
```

## Starten

### Web-Oberfläche (empfohlen)

```bash
python server.py
```

→ Öffne http://localhost:5000

Features:
- **➕ Stelle hinzufügen** — Firma, Titel, URL und Stellentext eingeben → Analyse + Anschreiben in ~30 s
- **⚡ Generieren** — Anschreiben/CV für bereits bewertete Stellen (Score ≥ 6) nachholen

### Automatischer Suchlauf (CLI)

```bash
python main.py --suche --max-stellen 25
```

### Einzelne Stelle analysieren

`stelle.txt` mit dem Anzeigentext befüllen, dann:

```bash
python main.py
```

### Anschreiben für vorhandene Stellen neu erstellen

```bash
python main.py --rewrite
```

## Struktur

```
output/
  bewertungen/uebersicht.csv   — alle bewerteten Stellen
  bewertungen/uebersicht.html  — Übersicht (auch direkt öffnbar)
  bewerbungen/                 — Anschreiben + CV als HTML
```
