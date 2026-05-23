import os
import re
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agents.context import JobContext

load_dotenv()

MODEL = "claude-sonnet-4-6"
KRITERIEN_PFAD = Path("scoring_kriterien.md")

SYSTEM_PROMPT = """\
Du bist ein erfahrener Karriere-Scout. Du bekommst drei Dokumente:
1. SCORING-KRITERIEN — Claudias persönliche Regeln für die Stellenbewertung
2. BEWERBERPROFIL — Claudias Hintergrund, Skills und Erfahrung
3. STELLENANZEIGE — die zu bewertende Stelle

Befolge die SCORING-KRITERIEN in der dort angegebenen Reihenfolge:
- Standort immer zuerst prüfen (Abschnitt 1)
- Ausschlusskriterien prüfen (Abschnitt 2)
- Dann vollständige inhaltliche Bewertung

Antworte EXAKT in diesem Format — keine Abweichungen, keine Einleitung:

SCORE: [Zahl 1–10]
BRANCHE: [z. B. "B2B SaaS", "HealthTech" – max. 3 Wörter]
FAHRTZEIT: [geschätzte Minuten von München Laim per MVV – bei Remote: 0]
PRO_1: [stärkster Pluspunkt, eine Zeile]
PRO_2: [zweiter Pluspunkt, eine Zeile]
PRO_3: [dritter Pluspunkt, eine Zeile]
CON_1: [größter Minuspunkt, eine Zeile]
CON_2: [zweiter Minuspunkt, eine Zeile]
CON_3: [dritter Minuspunkt, eine Zeile]
EMPFEHLUNG: [genau eines: Bewerben / Überspringen / Nicht passend]
SCORE_DETAILS:
- [Kriteriumsname]: [erreichte Punkte]/[maximale Punkte]
(einen Eintrag pro aktivem Kriterium aus scoring_kriterien.md)\
"""


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _kriterien_laden() -> str:
    if KRITERIEN_PFAD.exists():
        return KRITERIEN_PFAD.read_text(encoding="utf-8")
    return "(Keine scoring_kriterien.md gefunden — nur Profil verwenden)"


def run(ctx: JobContext) -> JobContext:
    kriterien = _kriterien_laden()
    kwargs = dict(
        model=MODEL,
        max_tokens=1024,
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
                        "text": f"SCORING-KRITERIEN:\n{kriterien}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": f"\nBEWERBERPROFIL:\n{ctx.profil_text}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": f"\nSTELLENANZEIGE:\n{ctx.stellentext}",
                    },
                ],
            }
        ],
    )
    for versuch in range(3):
        try:
            response = _get_client().messages.create(**kwargs)
            break
        except anthropic.RateLimitError:
            if versuch == 2:
                raise
            print("  [Analyst] Rate-Limit — warte 65 Sekunden ...")
            time.sleep(65)
        except anthropic.APIConnectionError:
            if versuch == 2:
                raise
            print("  [Analyst] Verbindungsfehler — warte 15 Sekunden ...")
            time.sleep(15)

    return _parse(ctx, response.content[0].text)


def _parse(ctx: JobContext, antwort: str) -> JobContext:
    # Zeilenweise parsen — robust gegen leere Felder und Mehrzeiligkeit
    sections: dict[str, str] = {}
    current_label: str | None = None
    current_lines: list[str] = []

    for line in antwort.split("\n"):
        # Labels dürfen Großbuchstaben, Unterstriche und Ziffern enthalten (z. B. PRO_1)
        m = re.match(r"^([A-Z][A-Z_0-9]+):\s*(.*)$", line)
        if m:
            if current_label is not None:
                sections[current_label] = "\n".join(current_lines).strip()
            current_label = m.group(1)
            rest = m.group(2).strip()
            current_lines = [rest] if rest else []
        elif current_label is not None:
            current_lines.append(line)

    if current_label is not None:
        sections[current_label] = "\n".join(current_lines).strip()

    def get(key: str) -> str:
        return sections.get(key, "")

    score_match = re.search(r"\d+", get("SCORE"))
    ctx.score = int(score_match.group()) if score_match else None

    ctx.branche   = get("BRANCHE")

    fahrtzeit_match = re.search(r"\d+", get("FAHRTZEIT"))
    ctx.fahrtzeit = int(fahrtzeit_match.group()) if fahrtzeit_match else 0

    ctx.pro_1 = get("PRO_1")
    ctx.pro_2 = get("PRO_2")
    ctx.pro_3 = get("PRO_3")
    ctx.con_1 = get("CON_1")
    ctx.con_2 = get("CON_2")
    ctx.con_3 = get("CON_3")
    ctx.empfehlung = get("EMPFEHLUNG")

    ctx.score_details = [
        line.lstrip("- ").strip()
        for line in get("SCORE_DETAILS").splitlines()
        if line.strip().startswith("-")
    ]

    # Rückwärtskompatibilität: Writer Agent nutzt staerken/cons
    ctx.staerken = [s for s in [ctx.pro_1, ctx.pro_2, ctx.pro_3] if s]
    ctx.cons     = [s for s in [ctx.con_1, ctx.con_2, ctx.con_3] if s]

    return ctx
