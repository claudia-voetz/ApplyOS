from pathlib import Path

from agents.context import JobContext
from agents import analyst_agent, writer_agent, output_agent

SCORE_SCHWELLENWERT = 6
PROFIL_PFAD = Path("profil.txt")


def suche_und_bewerte(max_stellen: int = 10) -> list[JobContext]:
    from agents import search_agent

    print(f"\n[Orchestrator] Modus: Automatische Suche (max. {max_stellen} Stellen)")
    print("=" * 50)

    stellen = search_agent.run(max_stellen=max_stellen)

    if not stellen:
        print("[Orchestrator] Keine Stellen gefunden.")
        return []

    print(f"[Orchestrator] {len(stellen)} Stelle(n) gefunden — starte Bewertung ...\n")

    ergebnisse = []
    for i, stelle in enumerate(stellen, 1):
        print(f"[Orchestrator] Stelle {i}/{len(stellen)}: {stelle.get('titel', '?')} @ {stelle.get('firma', '?')}")
        ctx = run(
            stellentext=stelle.get("stellentext", ""),
            firmenname=stelle.get("firma", ""),
            stellentitel=stelle.get("titel", ""),
            url=stelle.get("url", ""),
        )
        ergebnisse.append(ctx)

    print("\n" + "=" * 50)
    print(f"[Orchestrator] Suche abgeschlossen. {len(ergebnisse)} Stelle(n) bewertet.")
    _zusammenfassung(ergebnisse)

    return ergebnisse


def _zusammenfassung(ergebnisse: list[JobContext]) -> None:
    print("\nZusammenfassung:")
    print(f"  {'Stelle':<40} {'Score':>6}  {'Empfehlung'}")
    print("  " + "-" * 60)
    for ctx in sorted(ergebnisse, key=lambda c: c.score or 0, reverse=True):
        titel = f"{ctx.stellentitel} @ {ctx.firmenname}"[:40]
        print(f"  {titel:<40} {ctx.score or '?':>5}/10  {ctx.empfehlung}")


def run(stellentext: str, firmenname: str = "", stellentitel: str = "", url: str = "") -> JobContext:
    profil_text = PROFIL_PFAD.read_text(encoding="utf-8")

    ctx = JobContext(
        stellentext=stellentext,
        firmenname=firmenname,
        stellentitel=stellentitel,
        url=url,
        profil_text=profil_text,
    )

    label = f'"{stellentitel}"' if stellentitel else "Neue Stelle"
    print(f"\n[Orchestrator] Starte Bewerbungsprozess: {label}")
    print("-" * 50)

    # Schritt 1: Analyse
    print("[Orchestrator] >> Analyst Agent wird aufgerufen ...")
    ctx = analyst_agent.run(ctx)
    print(f"[Orchestrator] Score: {ctx.score}/10 — {ctx.empfehlung}")

    # Schritt 2: Anschreiben (nur bei ausreichendem Score)
    if ctx.score is not None and ctx.score >= SCORE_SCHWELLENWERT:
        print("[Orchestrator] >> Writer Agent wird aufgerufen ...")
        ctx = writer_agent.run(ctx)
        print("[Orchestrator] Anschreiben erstellt.")
    else:
        print(
            f"[Orchestrator] Score unter {SCORE_SCHWELLENWERT} "
            f"— Writer Agent wird übersprungen."
        )

    # Schritt 3: Speichern
    print("[Orchestrator] >> Output Agent wird aufgerufen ...")
    ctx = output_agent.run(ctx)
    print("[Orchestrator] Ergebnisse gespeichert.")

    print("-" * 50)
    print(f"[Orchestrator] Abgeschlossen. Score: {ctx.score}/10 — {ctx.empfehlung}")

    return ctx
