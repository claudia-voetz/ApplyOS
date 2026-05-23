import argparse
import csv
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from agents import orchestrator
from agents import writer_agent, output_agent
from agents.context import JobContext

STELLEN_PFAD    = Path("stelle.txt")
PROFIL_PFAD     = Path("profil.txt")
BEWERBUNGEN_DIR = Path("output/bewerbungen")
BEWERTUNGEN_DIR = Path("output/bewertungen")


def _lade_csv_jobs(profil_text: str) -> list[JobContext]:
    csv_pfad = BEWERTUNGEN_DIR / "uebersicht.csv"
    if not csv_pfad.exists():
        return []

    with csv_pfad.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        alle_zeilen = list(reader)

    # Duplikate entfernen: letzten Eintrag pro (Stelle, Unternehmen) behalten
    seen: dict[tuple, dict] = {}
    for row in alle_zeilen:
        key = (row.get("Stelle", ""), row.get("Unternehmen", ""))
        seen[key] = row
    unique_zeilen = list(seen.values())

    if len(unique_zeilen) < len(alle_zeilen):
        entfernt = len(alle_zeilen) - len(unique_zeilen)
        print(f"[CSV] {entfernt} Duplikat(e) bereinigt ({len(alle_zeilen)} → {len(unique_zeilen)} Zeilen)")
        with csv_pfad.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(unique_zeilen)

    jobs: list[JobContext] = []
    for row in unique_zeilen:
            try:
                score = int(row.get("Score", "0"))
            except ValueError:
                continue
            pro_1 = row.get("Pro1", "")
            pro_2 = row.get("Pro2", "")
            pro_3 = row.get("Pro3", "")
            con_1 = row.get("Con1", "")
            con_2 = row.get("Con2", "")
            con_3 = row.get("Con3", "")
            jobs.append(JobContext(
                stellentitel = row.get("Stelle", ""),
                firmenname   = row.get("Unternehmen", ""),
                url          = row.get("Link", ""),
                score        = score,
                fahrtzeit    = int(row.get("Fahrtzeit", "0") or "0"),
                branche      = row.get("Branche", ""),
                empfehlung   = row.get("Empfehlung", ""),
                status       = row.get("Status", "Offen"),
                pro_1        = pro_1,
                pro_2        = pro_2,
                pro_3        = pro_3,
                con_1        = con_1,
                con_2        = con_2,
                con_3        = con_3,
                staerken     = [s for s in [pro_1, pro_2, pro_3] if s],
                cons         = [s for s in [con_1, con_2, con_3] if s],
                profil_text  = profil_text,
                stellentext  = "",
            ))
    return jobs


def rewrite():
    profil_text = PROFIL_PFAD.read_text(encoding="utf-8")
    alle_jobs = _lade_csv_jobs(profil_text)

    if not alle_jobs:
        print("[Rewrite] Keine Jobs in output/bewertungen/uebersicht.csv gefunden.")
        return

    print(f"[Rewrite] {len(alle_jobs)} Job(s) in uebersicht.csv gefunden.\n")

    jobs = [j for j in alle_jobs if j.score is not None and j.score >= orchestrator.SCORE_SCHWELLENWERT]
    uebersprungen = len(alle_jobs) - len(jobs)
    if uebersprungen:
        print(f"  {uebersprungen} Job(s) unter Score {orchestrator.SCORE_SCHWELLENWERT} übersprungen.")

    print(f"[Rewrite] {len(jobs)} Job(s) werden neu erstellt – starte Writer Agent ...\n")
    print("=" * 60)

    erstellt = 0
    for i, ctx in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}] {ctx.stellentitel} @ {ctx.firmenname}  (Score {ctx.score}/10)")
        ctx = writer_agent.run(ctx)
        ctx = output_agent.run(ctx)
        print(f"  Gespeichert.")
        erstellt += 1

    print("=" * 60)
    print(f"[Rewrite] Fertig. {erstellt} Anschreiben + CVs neu erstellt.")


def main():
    parser = argparse.ArgumentParser(description="Claudias Bewerbungsagent")
    parser.add_argument("--suche",   action="store_true", help="Automatische Jobsuche")
    parser.add_argument("--rewrite", action="store_true", help="Anschreiben für vorhandene Stellen neu erstellen")
    parser.add_argument("--max-stellen", type=int, default=10, metavar="N")
    args = parser.parse_args()

    if args.suche:
        orchestrator.suche_und_bewerte(max_stellen=args.max_stellen)
        return

    if args.rewrite:
        rewrite()
        return

    if not STELLEN_PFAD.exists():
        print("Fehler: Keine stelle.txt gefunden.")
        print("Tipp: stelle.txt ablegen, --suche für Jobsuche, --rewrite für Neu-Erstellung.")
        return

    stellentext = STELLEN_PFAD.read_text(encoding="utf-8")
    ergebnis = orchestrator.run(stellentext=stellentext)
    print(f"\nFertig. Score: {ergebnis.score}/10 — {ergebnis.empfehlung}")


if __name__ == "__main__":
    main()
