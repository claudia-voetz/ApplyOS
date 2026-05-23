import os
import re
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agents.context import JobContext

load_dotenv()

MODEL = "claude-sonnet-4-6"

VORLAGEN_DIR = Path("output/vorlagen")

MONATE_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
MONTHS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

SYSTEM_PROMPT = """\
Du bist ein erfahrener HR-Berater und Bewerbungsexperte.
Du schreibst individuelle Bewerbungsunterlagen für Claudia Voetz.
Du bekommst ihr vollständiges Profil, die Stellenanzeige und eine Analyst-Bewertung.

────────────────────────────────────────────────────────────
GOLDENE REGEL: JEDER SATZ BRAUCHT EINEN FAKT ODER EINE ZAHL.
Kein Satz ohne konkreten Inhalt. Kein Satz der nur Haltung beschreibt.
────────────────────────────────────────────────────────────

GUTES BEISPIEL (genau so soll es klingen):
  "Produktprofi mit Fokus auf End-to-End-Entwicklung digitaler Produkte –
   von Discovery bis Launch – in internationalen, cross-funktionalen Teams.
   Mitentwicklung eines HSMAI-ausgezeichneten SaaS-Tools.
   Mein erstes Multi-Agent-System automatisiert bereits täglich operative Prozesse."

SCHLECHTES BEISPIEL (genau so NICHT):
  "Ich bringe etwas mit, das viele klassische POs nicht haben:
   einen operationalen Hintergrund, der mir zeigt, wo Automatisierung
   wirklich Schmerz lindert."
  → WARUM SCHLECHT: Kein einziger Fakt. Nur Behauptungen über sich selbst.

────────────────────────────────────────────────────────────
STIL-REGELN – NICHT OPTIONAL
────────────────────────────────────────────────────────────
✅ MACHEN:
- Jeder Satz = ein Fakt, eine Zahl, ein konkretes Ergebnis
- Zahlen aus dem Profil nutzen: 21 Länder, 3 Mio. Euro, 130+ Hotels, 1.500+ Hotels
- Kurze Sätze. Punkt. Nächster Gedanke.
- <strong> genau 1x pro Absatz – für den härtesten Fakt
- Anschreiben ergänzt den CV – neue Perspektive, keine Wiederholung

❌ VERBOTEN:
- "Ich bringe umfangreiche Erfahrung mit..."
- "Ich bin überzeugt, dass ich..."
- "Was mich auszeichnet ist..."
- "Ich habe ein tiefes Verständnis für..."
- Jede Aussage die ohne konkreten Beleg steht
- "kommunikationsstark", "teamorientiert", "motiviert"

────────────────────────────────────────────────────────────
AUFBAU ANSCHREIBEN – 6 SEKTIONEN:
────────────────────────────────────────────────────────────
EINSTIEG (EXAKT 2 Sätze – nicht mehr, nicht weniger):
  → Satz 1: "Produktprofi für End-to-End-Entwicklung..." ODER starker Einstieg mit Firmenbezug
  → Satz 2: Eine konkrete Zahl oder Tatsache. Dann STOP.
  → ❌ VERBOTEN: Multi-Agent-System, Zertifizierungen, "X Jahre Erfahrung", "Ich bewerbe mich"
  → ❌ KEIN dritter Satz – egal was
  → ✅ GUT: "Produktprofi für End-to-End-Entwicklung digitaler B2B-Produkte – von Discovery bis Launch. Gift-Card-Plattform über 21 Länder skaliert, Transaktionsvolumen von 1 Mio. auf 3 Mio. €."

KEINE WIEDERHOLUNGEN – STRIKTE REGEL:
  Jeder Inhalt darf NUR EINMAL im gesamten Anschreiben vorkommen.
  - Multi-Agent-System → NUR in FOKUS_ENTWICKLUNG
  - Zertifizierungen → NUR in FOKUS_ENTWICKLUNG
  - Gift-Card-Zahlen (21 Länder, 3 Mio. €) → NUR im EINSTIEG oder ERFAHRUNG_STAERKE, nicht beide
  - HSMAI Award → NUR in ERFAHRUNG_STAERKE
  - Stakeholder-Management → NUR in ARBEITSWEISE_TEAM

FOKUS_ENTWICKLUNG (2–3 Bullet Points als HTML-Liste):
  → Aktuelle Weiterbildung, AI-Praxis, Multi-Agent-System
  → REGEL: max. 10 Wörter pro Bullet. Kein Verb nötig. Keine Nebensätze.
  → ❌ SCHLECHT: "Hands-on-Aufbau eines eigenen Multi-Agent-Systems mit Agentic AI und Vibe Coding – täglicher Einsatz zur Automatisierung operativer Prozesse"
  → ✅ GUT: "Multi-Agent-System im Einsatz – automatisiert täglich operative Prozesse"
  → ✅ GUT: "Advanced Product Ownership, UX, KI-getriebene Entwicklung"
  → Format: <ul><li>...</li><li>...</li></ul>

ERFAHRUNG_STAERKE (2–3 Bullet Points als HTML-Liste):
  → Revenue Management, BI, B2B SaaS, Systemintegration – mit Zahlen
  → REGEL: max. 10 Wörter pro Bullet. Zahlen ja, Erklärungen nein.
  → ❌ SCHLECHT: "Business-Intelligence-Fundament: Aufbau interaktiver Google-Analytics-Dashboards und KPI-Frameworks für 500 Hotels im DACH-Hub – datengetriebene Entscheidungen als Arbeitsgrundlage"
  → ✅ GUT: "Hintergrund in Revenue Management & Business Intelligence"
  → ✅ GUT: "B2B SaaS, Plattformen, Systemintegration – 10+ Jahre Praxis"
  → Format: <ul><li>...</li><li>...</li></ul>

ARBEITSWEISE_TEAM (2–3 Bullet Points als HTML-Liste):
  → Pragmatisch, serviceorientiert, Produktfokus statt Hierarchie
  → REGEL: max. 10 Wörter pro Bullet. Adjektive und kurze Aussagen.
  → ❌ SCHLECHT: "Serviceorientierter Blick auf Automatisierung: Hintergrund in Revenue Management und operativem Hotelbetrieb schärft den Blick dafür, wo manuelle Prozesse echten Aufwand erzeugen"
  → ✅ GUT: "Pragmatisch, serviceorientiert, energiegebend"
  → ✅ GUT: "Klare Ziele, Transparenz, Produktfokus statt Hierarchie"
  → Format: <ul><li>...</li><li>...</li></ul>

FIT_ROLLE (1–2 Sätze):
  → Konkreter Bezug zur Stelle – was passt, was bringe ich ein
  → Stellenspezifisch – nicht generisch
  → Keine Wiederholung von Inhalten aus anderen Sektionen

SCHLUSS (1 Satz):
  → Kurz, direkt. Z.B. "Ich freue mich auf ein erstes Gespräch."

────────────────────────────────────────────────────────────
SPRACHE-REGEL:
  Stellenanzeige auf Englisch → SPRACHE: en, alle Felder auf Englisch
  Sonst → SPRACHE: de, alle Felder auf Deutsch

────────────────────────────────────────────────────────────
ANTWORT-FORMAT (exakt so, kein Text davor, keine Abweichungen):
────────────────────────────────────────────────────────────

SPRACHE: de

JOBTITEL_HEADER:
[Rollenbezeichnung für Header, max. 60 Zeichen, z. B. "Senior Product Owner · HealthTech"]

CV_TAGLINE:
[2–3 Sätze, stellenspezifisch, authentisch – Ausgangspunkt ist der Standard-Text aus dem Profil, leicht angepasst an die Stelle]

CV_HIGHLIGHT_1:
[Wichtigster Erfolg für diese Stelle – eine Zeile mit Zahlen, max. 120 Zeichen]

CV_HIGHLIGHT_2:
[Zweiter Erfolg – eine Zeile mit Zahlen, max. 120 Zeichen]

ANSPRECHPERSON:
[Ansprechperson aus der Anzeige, z. B. "z. Hd. Frau Müller" – leer lassen wenn unbekannt]

ANSCHREIBEN_EINSTIEG:
[2–3 Sätze Profil-Intro mit Zahlen – kein "Ich bewerbe mich"]

ANSCHREIBEN_FOKUS:
<ul><li>[Weiterbildung / AI-Praxis Punkt 1]</li><li>[Punkt 2]</li><li>[Punkt 3]</li></ul>

ANSCHREIBEN_ERFAHRUNG:
<ul><li>[Erfahrung/Stärke mit Zahlen Punkt 1]</li><li>[Punkt 2]</li><li>[Punkt 3]</li></ul>

ANSCHREIBEN_ARBEITSWEISE:
<ul><li>[Arbeitsweise/Team Punkt 1]</li><li>[Punkt 2]</li><li>[Punkt 3]</li></ul>

ANSCHREIBEN_FIT:
[1–2 Sätze konkreter Fit zur Stelle]

ANSCHREIBEN_SCHLUSS:
[1 Satz kurzer Abschluss]

CV_ANPASSUNGEN:
- [Interner Hinweis 1 für Claudia]
- [Interner Hinweis 2 für Claudia]\
"""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def run(ctx: JobContext) -> JobContext:
    staerken = "\n".join(f"- {s}" for s in ctx.staerken)
    cons = "\n".join(f"- {l}" for l in ctx.cons)

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"BEWERBERPROFIL:\n{ctx.profil_text}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"\nSTELLENANZEIGE:\n{ctx.stellentext}"
                            f"\n\nANALYST-BEWERTUNG:\n"
                            f"Score: {ctx.score}/10 – {ctx.empfehlung}\n"
                            f"Begründung: {ctx.begruendung}\n"
                            f"Stärken:\n{staerken}\n"
                            f"Lücken:\n{cons}"
                        ),
                    },
                ],
            }
        ],
    )

    ctx = _parse(ctx, response.content[0].text)
    ctx = _befuelle_vorlagen(ctx)
    return ctx


def _parse(ctx: JobContext, antwort: str) -> JobContext:
    # Zeilenweise parsen – robust, kein Regex-Bleeding bei leeren Feldern
    sections: dict[str, str] = {}
    current_label: str | None = None
    current_lines: list[str] = []

    for line in antwort.split("\n"):
        label_match = re.match(r"^([A-ZÄÖÜ][A-ZÄÖÜ_0-9]{1,}):\s*(.*)$", line)
        if label_match:
            if current_label is not None:
                sections[current_label] = "\n".join(current_lines).strip()
            current_label = label_match.group(1)
            rest = label_match.group(2).strip()
            current_lines = [rest] if rest else []
        elif current_label is not None:
            current_lines.append(line)

    if current_label is not None:
        sections[current_label] = "\n".join(current_lines).strip()

    def get(key: str) -> str:
        return sections.get(key, "")

    ctx.sprache           = get("SPRACHE") or "de"
    ctx.jobtitel_header   = get("JOBTITEL_HEADER")
    ctx.tagline           = get("CV_TAGLINE")
    ctx.highlight_1       = get("CV_HIGHLIGHT_1")
    ctx.highlight_2       = get("CV_HIGHLIGHT_2")
    ctx.ansprechperson    = get("ANSPRECHPERSON")
    ctx.einstieg          = get("ANSCHREIBEN_EINSTIEG")
    ctx.fokus_entwicklung = get("ANSCHREIBEN_FOKUS")
    ctx.erfahrung_staerke = get("ANSCHREIBEN_ERFAHRUNG")
    ctx.arbeitsweise_team = get("ANSCHREIBEN_ARBEITSWEISE")
    ctx.fit_rolle         = get("ANSCHREIBEN_FIT")
    ctx.schluss_absatz    = get("ANSCHREIBEN_SCHLUSS")
    ctx.cv_anpassungen    = get("CV_ANPASSUNGEN")

    return ctx


def _datum(sprache: str) -> str:
    heute = date.today()
    if sprache == "en":
        return f"Munich, {MONTHS_EN[heute.month - 1]} {heute.year}"
    return f"München, {MONATE_DE[heute.month - 1]} {heute.year}"


def _befuelle_vorlagen(ctx: JobContext) -> JobContext:
    sprache = ctx.sprache.lower().strip()

    if sprache == "en":
        # ── Englische Vorlagen ──────────────────────────────────────
        anschreiben_pfad = VORLAGEN_DIR / "Cover_Letter_Vorlage_EN.html"
        cv_pfad          = VORLAGEN_DIR / "CV_Vorlage_EN.html"

        anschreiben_werte = {
            "JOBTITLE_HEADER":    ctx.jobtitel_header,
            "RECIPIENT_COMPANY":  ctx.firmenname or "[Company]",
            "RECIPIENT_PERSON":   ctx.ansprechperson or "",
            "RECIPIENT_EMAIL":    "",
            "DATE":               _datum("en"),
            "JOB_TITLE":          ctx.stellentitel or ctx.jobtitel_header,
            "EINSTIEG":           ctx.einstieg,
            "FOKUS_ENTWICKLUNG":  ctx.fokus_entwicklung,
            "ERFAHRUNG_STAERKE":  ctx.erfahrung_staerke,
            "ARBEITSWEISE_TEAM":  ctx.arbeitsweise_team,
            "FIT_ROLLE":          ctx.fit_rolle,
            "SCHLUSS":            ctx.schluss_absatz,
        }

        cv_werte = {
            "JOBTITLE_HEADER": ctx.jobtitel_header,
            "TAGLINE":         ctx.tagline,
            "CV_HIGHLIGHT_1":  ctx.highlight_1,
            "CV_HIGHLIGHT_2":  ctx.highlight_2,
        }

    else:
        # ── Deutsche Vorlagen ───────────────────────────────────────
        anschreiben_pfad = VORLAGEN_DIR / "Anschreiben_Vorlage_DE.html"
        cv_pfad          = VORLAGEN_DIR / "CV_Vorlage_DE.html"

        anschreiben_werte = {
            "JOBTITEL_HEADER":    ctx.jobtitel_header,
            "EMPFAENGER_FIRMA":   ctx.firmenname or "[Unternehmen]",
            "EMPFAENGER_PERSON":  ctx.ansprechperson or "",
            "EMPFAENGER_EMAIL":   "",
            "DATUM":              _datum("de"),
            "STELLENTITEL":       ctx.stellentitel or ctx.jobtitel_header,
            "EINSTIEG":           ctx.einstieg,
            "FOKUS_ENTWICKLUNG":  ctx.fokus_entwicklung,
            "ERFAHRUNG_STAERKE":  ctx.erfahrung_staerke,
            "ARBEITSWEISE_TEAM":  ctx.arbeitsweise_team,
            "FIT_ROLLE":          ctx.fit_rolle,
            "SCHLUSS":            ctx.schluss_absatz,
        }

        cv_werte = {
            "JOBTITEL_HEADER": ctx.jobtitel_header,
            "TAGLINE":         ctx.tagline,
            "CV_HIGHLIGHT_1":  ctx.highlight_1,
            "CV_HIGHLIGHT_2":  ctx.highlight_2,
        }

    ctx.anschreiben_html = _ersetze_platzhalter(anschreiben_pfad, anschreiben_werte)
    ctx.cv_html          = _ersetze_platzhalter(cv_pfad, cv_werte)

    return ctx


def _ersetze_platzhalter(pfad: Path, werte: dict[str, str]) -> str:
    if not pfad.exists():
        print(f"[Writer] Warnung: Vorlage nicht gefunden: {pfad}")
        return ""
    html = pfad.read_text(encoding="utf-8")
    for platzhalter, wert in werte.items():
        html = html.replace(f"{{{{{platzhalter}}}}}", wert or "")
    return html
