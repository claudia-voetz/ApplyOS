import os
import csv
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

PROFIL_PFAD     = Path("profil.txt")
BEWERBUNGEN_DIR = Path("output/bewerbungen")
UEBERSICHT_HTML = Path("output/bewertungen/uebersicht.html")
UEBERSICHT_CSV  = Path("output/bewertungen/uebersicht.csv")
LOGO_DIR        = Path(__file__).parent / "logo"
SCORE_SCHWELLE  = 6

_suchlauf_proc:    subprocess.Popen | None = None
_suchlauf_start:   float = 0.0
_suchlauf_csv_vor: int   = 0


@app.route("/")
def index():
    html = UEBERSICHT_HTML.read_text(encoding="utf-8")
    # Relative Dateipfade → absolute Server-Pfade umschreiben
    html = html.replace("../bewerbungen/", "/bewerbungen/")
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/bewerbungen/<path:filename>")
def bewerbungen(filename):
    return send_from_directory(BEWERBUNGEN_DIR.resolve(), filename)


@app.route("/Logo/<path:filename>")
def logo(filename):
    return send_from_directory(LOGO_DIR.resolve(), filename)


@app.route("/stelle-hinzufuegen", methods=["POST"])
def stelle_hinzufuegen():
    data        = request.get_json(force=True) or {}
    firma       = str(data.get("firma", "")).strip()
    titel       = str(data.get("titel", "")).strip()
    url         = str(data.get("url", "")).strip()
    stellentext = str(data.get("stellentext", "")).strip()

    if not firma or not titel:
        return jsonify({"fehler": "Firma und Titel sind Pflichtfelder."}), 400

    from agents import orchestrator
    ctx = orchestrator.run(
        stellentext=stellentext,
        firmenname=firma,
        stellentitel=titel,
        url=url,
    )

    result = {
        "score":      ctx.score,
        "empfehlung": ctx.empfehlung,
        "branche":    ctx.branche,
    }
    if ctx.bewerbung_link:
        anschreiben = ctx.bewerbung_link.replace("../bewerbungen/", "/bewerbungen/")
        result["anschreiben_link"] = anschreiben
        cv_name = Path(ctx.bewerbung_link).name.replace("_anschreiben.html", "_cv.html")
        if (BEWERBUNGEN_DIR / cv_name).exists():
            result["cv_link"] = f"/bewerbungen/{cv_name}"
    return jsonify(result)


@app.route("/generieren", methods=["POST"])
def generieren():
    data       = request.get_json(force=True) or {}
    stelle_key = str(data.get("stelle_key", ""))

    if "|" not in stelle_key:
        return jsonify({"fehler": "Ungültiger stelle_key."}), 400

    stelle_name, firma_name = stelle_key.split("|", 1)

    if not UEBERSICHT_CSV.exists():
        return jsonify({"fehler": "Keine Übersicht (CSV) gefunden."}), 404

    zeile = None
    with UEBERSICHT_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("Stelle") == stelle_name and row.get("Unternehmen") == firma_name:
                zeile = row
                break

    if not zeile:
        return jsonify({"fehler": "Stelle nicht in der Übersicht gefunden."}), 404

    try:
        score = int(zeile.get("Score", "0"))
    except ValueError:
        score = 0

    from agents.context import JobContext
    from agents import writer_agent, output_agent

    profil_text = PROFIL_PFAD.read_text(encoding="utf-8")
    pro_1 = zeile.get("Pro1", "") or ""
    pro_2 = zeile.get("Pro2", "") or ""
    pro_3 = zeile.get("Pro3", "") or ""
    con_1 = zeile.get("Con1", "") or ""
    con_2 = zeile.get("Con2", "") or ""
    con_3 = zeile.get("Con3", "") or ""

    ctx = JobContext(
        stellentitel = stelle_name,
        firmenname   = firma_name,
        url          = zeile.get("Link",      "") or "",
        score        = score,
        fahrtzeit    = int(zeile.get("Fahrtzeit", "0") or "0"),
        branche      = zeile.get("Branche",   "") or "",
        empfehlung   = zeile.get("Empfehlung","") or "",
        status       = zeile.get("Status",    "Offen") or "Offen",
        pro_1=pro_1, pro_2=pro_2, pro_3=pro_3,
        con_1=con_1, con_2=con_2, con_3=con_3,
        staerken=[s for s in [pro_1, pro_2, pro_3] if s],
        cons    =[s for s in [con_1, con_2, con_3] if s],
        profil_text=profil_text,
        stellentext="",
    )

    ctx = writer_agent.run(ctx)
    ctx = output_agent.run(ctx)

    result = {}
    if ctx.bewerbung_link:
        anschreiben = ctx.bewerbung_link.replace("../bewerbungen/", "/bewerbungen/")
        result["anschreiben_link"] = anschreiben
        cv_name = Path(ctx.bewerbung_link).name.replace("_anschreiben.html", "_cv.html")
        if (BEWERBUNGEN_DIR / cv_name).exists():
            result["cv_link"] = f"/bewerbungen/{cv_name}"
    return jsonify(result)


@app.route("/suchlauf-starten", methods=["POST"])
def suchlauf_starten():
    global _suchlauf_proc, _suchlauf_start, _suchlauf_csv_vor
    if os.getenv("DEMO_MODE") == "true":
        return jsonify({
            "status": "demo_modus",
            "nachricht": "Liebe Firma – Ihr Interesse freut uns! 🎉 Dieses Feature konnten wir leider nicht live schalten, da Claudia ihre Tokens zum Lernen und Coden braucht."
        })
    if _suchlauf_proc is not None and _suchlauf_proc.poll() is None:
        return jsonify({"status": "laeuft_bereits", "laufzeit_sek": int(time.time() - _suchlauf_start)})
    _suchlauf_csv_vor = 0
    if UEBERSICHT_CSV.exists():
        with UEBERSICHT_CSV.open(newline="", encoding="utf-8") as f:
            _suchlauf_csv_vor = sum(1 for _ in csv.DictReader(f))
    _suchlauf_proc = subprocess.Popen(
        [sys.executable, "main.py", "--suche", "--max-stellen", "15"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _suchlauf_start = time.time()
    return jsonify({"status": "gestartet"})


@app.route("/suchlauf-status")
def suchlauf_status():
    global _suchlauf_proc, _suchlauf_start, _suchlauf_csv_vor
    if _suchlauf_proc is None:
        return jsonify({"laeuft": False, "laufzeit_sek": 0, "neue_stellen": 0, "dauer": "0:00"})
    laeuft   = _suchlauf_proc.poll() is None
    laufzeit = int(time.time() - _suchlauf_start) if _suchlauf_start else 0
    dauer    = f"{laufzeit // 60}:{laufzeit % 60:02d}"
    neue_stellen = 0
    if not laeuft and UEBERSICHT_CSV.exists():
        with UEBERSICHT_CSV.open(newline="", encoding="utf-8") as f:
            neue_stellen = max(0, sum(1 for _ in csv.DictReader(f)) - _suchlauf_csv_vor)
    return jsonify({"laeuft": laeuft, "laufzeit_sek": laufzeit, "neue_stellen": neue_stellen, "dauer": dauer})


if __name__ == "__main__":
    print("Starte Server → http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
