import csv
import json
import re
from datetime import date
from pathlib import Path

from agents.context import JobContext

BEWERTUNGEN_DIR = Path("output/bewertungen")
BEWERBUNGEN_DIR = Path("output/bewerbungen")
UEBERSICHT_CSV  = BEWERTUNGEN_DIR / "uebersicht.csv"
UEBERSICHT_HTML = BEWERTUNGEN_DIR / "uebersicht.html"

CSV_FELDER = [
    "Datum", "Stelle", "Link", "Unternehmen",
    "Score", "Fahrtzeit", "Branche",
    "Pro1", "Pro2", "Pro3",
    "Con1", "Con2", "Con3",
    "Empfehlung", "Status", "StatusDatum", "Bewerbung", "ScoreDetails",
]

# (Kurzname, Schlüsselwort im ScoreDetails-String)
SCORE_KRITERIEN = [
    ("E2E",         "End-to-End"),
    ("Roadmap",     "Roadmap"),
    ("Auto",        "Automation"),
    ("AgentAI",     "Agentic"),
    ("Stakeholder", "Stakeholder"),
    ("Cross",       "Cross"),
    ("Engineering", "Engineering"),
    ("Agile",       "Agile"),
    ("B2B",         "B2B SaaS"),
    ("Behörden",    "Behörden"),
    ("Sozial",      "Soziales"),
    ("Standort",    "Standort"),
    ("Gehalt",      "Gehalt"),
]


def run(ctx: JobContext) -> JobContext:
    slug = _slug(ctx)
    if ctx.anschreiben_html or ctx.cv_html:
        _speichere_bewerbungsunterlagen(ctx, slug)
        ctx.bewerbung_link = f"../bewerbungen/{slug}_anschreiben.html"
    _aktualisiere_uebersicht(ctx, slug)
    ctx.gespeichert = True
    return ctx


def _slug(ctx: JobContext) -> str:
    teile = [date.today().isoformat()]
    if ctx.firmenname:
        teile.append(_bereinigen(ctx.firmenname))
    if ctx.stellentitel:
        teile.append(_bereinigen(ctx.stellentitel))
    return "_".join(teile)


def _bereinigen(text: str) -> str:
    # Em-Dash, En-Dash und URL-problematische Zeichen entfernen
    text = re.sub(r'[\u2013\u2014\u2012<>:"/\\|?*&()\[\]{}]', '', text)
    text = re.sub(r'\s+', '_', text.strip())
    text = re.sub(r'_+', '_', text)   # mehrfache _ zusammenführen
    return text[:40]


def _aktualisiere_uebersicht(ctx: JobContext, slug: str) -> None:
    zeilen_dicts: list[dict] = []
    if UEBERSICHT_CSV.exists():
        with UEBERSICHT_CSV.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            alte_felder = set(reader.fieldnames or [])
            zeilen_dicts = list(reader)
        if alte_felder - set(CSV_FELDER):
            backup = UEBERSICHT_CSV.with_name(
                f"uebersicht_{date.today().isoformat()}_alt.csv"
            )
            UEBERSICHT_CSV.rename(backup)
            zeilen_dicts = []

    neue_zeile = {
        "Datum":        date.today().isoformat(),
        "Stelle":       ctx.stellentitel or "–",
        "Link":         ctx.url or "–",
        "Unternehmen":  ctx.firmenname or "–",
        "Score":        ctx.score if ctx.score is not None else "–",
        "Fahrtzeit":    ctx.fahrtzeit,
        "Branche":      ctx.branche or "–",
        "Pro1":         ctx.pro_1 or "–",
        "Pro2":         ctx.pro_2 or "–",
        "Pro3":         ctx.pro_3 or "–",
        "Con1":         ctx.con_1 or "–",
        "Con2":         ctx.con_2 or "–",
        "Con3":         ctx.con_3 or "–",
        "Empfehlung":   ctx.empfehlung or "–",
        "Status":       ctx.status or "Offen",
        "StatusDatum":  "",
        "Bewerbung":    ctx.bewerbung_link or "",
        "ScoreDetails": "|".join(ctx.score_details) if ctx.score_details else "",
    }

    key = (ctx.stellentitel or "–", ctx.firmenname or "–")
    ersetzt = False
    for i, zeile in enumerate(zeilen_dicts):
        if (zeile.get("Stelle"), zeile.get("Unternehmen")) == key:
            # Nutzerstatus und -datum aus dem Browser/CSV bewahren
            alt_status = zeile.get("Status", "")
            if alt_status and alt_status != "Offen":
                neue_zeile["Status"]      = alt_status
                neue_zeile["StatusDatum"] = zeile.get("StatusDatum", "")
            # Vorhandener Bewerbungslink bleibt erhalten wenn kein neuer gesetzt
            if not neue_zeile["Bewerbung"] and zeile.get("Bewerbung"):
                neue_zeile["Bewerbung"] = zeile["Bewerbung"]
            # ScoreDetails bewahren wenn keine neuen vorhanden (z.B. beim Generieren)
            if not neue_zeile["ScoreDetails"] and zeile.get("ScoreDetails"):
                neue_zeile["ScoreDetails"] = zeile["ScoreDetails"]
            zeilen_dicts[i] = neue_zeile
            ersetzt = True
            break

    if not ersetzt:
        zeilen_dicts.append(neue_zeile)

    with UEBERSICHT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FELDER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(zeilen_dicts)

    _erstelle_html()


# ---------------------------------------------------------------------------
# Hilfsfunktionen HTML
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    t = str(text or "")
    return (t.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _fmt(v: float) -> str:
    return str(int(v)) if v == int(v) else str(v)


def _parse_score_details(raw: str) -> dict:
    """'Kriterium: val/max|...' → {kurzname: (val, max)}"""
    result: dict[str, tuple[float, float]] = {}
    if not raw:
        return result
    for part in raw.split("|"):
        part = part.strip()
        if ":" not in part:
            continue
        key, rest = part.split(":", 1)
        key = key.strip().lower()
        m = re.match(r"([\d.]+)/([\d.]+)", rest.strip())
        if not m:
            continue
        val  = float(m.group(1))
        maxv = float(m.group(2))
        for short, keyword in SCORE_KRITERIEN:
            if keyword.lower() in key:
                result[short] = (val, maxv)
                break
    return result


def _krit_cell(details: dict, short: str) -> str:
    if short not in details:
        return '<td class="c-krit c-krit-na">–</td>'
    val, maxv = details[short]
    label = f"{_fmt(val)}/{_fmt(maxv)}"
    if val == 0:
        cls = "c-krit-zero"
    elif val >= maxv:
        cls = "c-krit-full"
    else:
        cls = "c-krit-half"
    return f'<td class="c-krit {cls}" title="{short}: {label}">{label}</td>'


# ---------------------------------------------------------------------------
# HTML-Generierung
# ---------------------------------------------------------------------------

def _erstelle_html() -> None:
    if not UEBERSICHT_CSV.exists():
        return

    with UEBERSICHT_CSV.open(newline="", encoding="utf-8") as f:
        zeilen = list(csv.DictReader(f))

    zeilen_sortiert = sorted(
        zeilen,
        key=lambda r: int(r.get("Score") or 0) if str(r.get("Score", "")).isdigit() else 0,
        reverse=True,
    )

    modal_data: dict[str, dict] = {}
    zeilen_html = ""

    for idx, z in enumerate(zeilen_sortiert):
        score_str = z.get("Score", "?")
        try:
            score_int = int(score_str)
            score_kls = "score-high" if score_int >= 7 else ("score-mid" if score_int >= 5 else "score-low")
        except (ValueError, TypeError):
            score_int = -1
            score_kls = ""

        link  = z.get("Link", "") or ""
        stelle = z.get("Stelle", "–")
        stelle_html = (
            f'<a href="{_esc(link)}" target="_blank">{_esc(stelle)}</a>'
            if link and link != "–" else _esc(stelle)
        )
        firma_html = _esc(z.get("Unternehmen", "–"))

        fahrtzeit   = z.get("Fahrtzeit", "")
        fz_html     = "Remote" if str(fahrtzeit) in ("0", "") else f"{fahrtzeit} Min"

        # Bewerbungsunterlagen
        anschreiben_link = z.get("Bewerbung", "") or ""
        bew_html = ""
        if anschreiben_link and "_anschreiben.html" in anschreiben_link:
            slug_file = anschreiben_link.replace("../bewerbungen/", "")
            cv_slug   = slug_file.replace("_anschreiben.html", "_cv.html")
            cv_link   = f"../bewerbungen/{cv_slug}"
            anschreiben_exists = (BEWERBUNGEN_DIR / slug_file).exists()
            cv_exists = (BEWERBUNGEN_DIR / cv_slug).exists()
            if anschreiben_exists:
                bew_html = f'<a href="{_esc(anschreiben_link)}" target="_blank" class="bew-link">📄 Anschreiben</a>'
                if cv_exists:
                    bew_html += f'<a href="{_esc(cv_link)}" target="_blank" class="bew-link">📋 CV</a>'
            else:
                # Datei existiert nicht (z.B. nach Render-Deploy) → Generieren-Button zeigen
                stelle_key_esc = _esc(f"{stelle}|{z.get('Unternehmen', '–')}")
                bew_html = (
                    f'<button class="btn-gen" data-key="{stelle_key_esc}"'
                    f' onclick="generiereUnterlagen(this.dataset.key, this)">⚡ Generieren</button>'
                )
        elif score_int >= 6:
            stelle_key_esc = _esc(f"{stelle}|{z.get('Unternehmen', '–')}")
            bew_html = (
                f'<button class="btn-gen" data-key="{stelle_key_esc}"'
                f' onclick="generiereUnterlagen(this.dataset.key, this)">⚡ Generieren</button>'
            )
        elif score_int >= 0:
            stelle_key_esc = _esc(f"{stelle}|{z.get('Unternehmen', '–')}")
            bew_html = (
                f'<button class="btn-trotzdem" data-key="{stelle_key_esc}" data-score="{score_int}"'
                f' onclick="trotzdemBewerben(this.dataset.key, this.dataset.score, this)">'
                f'📄 Generieren</button>'
            )

        # localStorage-Schlüssel (stabil über HTML-Regenerierungen)
        ls_key_raw  = f"{z.get('Datum','')}_{z.get('Unternehmen','')}_{stelle[:30]}"
        ls_key_attr = _esc(ls_key_raw)

        status_val   = z.get("Status",      "Offen") or "Offen"
        status_datum = z.get("StatusDatum", "") or ""

        # Status-Dropdown (inkl. neuer Option "Absage")
        opts = ["Offen", "Interessant", "Beworben", "Absage", "Überspringen"]
        opt_html = "".join(
            f'<option{"  selected" if status_val == o else ""}>{_esc(o)}</option>'
            for o in opts
        )
        status_html = (
            f'<select class="status-sel" '
            f'data-key="{ls_key_attr}" data-status="{_esc(status_val)}" '
            f'onchange="saveStatus(this)">{opt_html}</select>'
        )

        # Score-Kriterien
        details    = _parse_score_details(z.get("ScoreDetails", "") or "")
        krit_cells = "".join(_krit_cell(details, short) for short, _ in SCORE_KRITERIEN)

        # Modal-Daten (plain text, kein HTML-Escaping – JSON-Escaping via json.dumps)
        modal_data[str(idx)] = {
            "stelle": stelle,
            "firma":  z.get("Unternehmen", "–"),
            "fz":     fz_html,
            "pro1":   z.get("Pro1", "") or "",
            "pro2":   z.get("Pro2", "") or "",
            "pro3":   z.get("Pro3", "") or "",
            "con1":   z.get("Con1", "") or "",
            "con2":   z.get("Con2", "") or "",
            "con3":   z.get("Con3", "") or "",
        }

        # Zeile
        zeilen_html += (
            f'      <tr data-status="{_esc(status_val)}">\n'
            f'        <td class="c-sm">{_esc(z.get("Datum",""))}</td>\n'
            f'        <td class="c-stelle">'
            f'{stelle_html}'
            f'<small class="c-firma">{firma_html} · {fz_html}</small>'
            f'</td>\n'
            f'        <td class="c-sc"><span class="score {score_kls}">{_esc(score_str)}/10</span></td>\n'
            f'{krit_cells}\n'
            f'        <td class="c-modal"><button class="btn-modal" data-idx="{idx}" onclick="openModal(this.dataset.idx)">💬</button></td>\n'
            f'        <td class="c-status">{status_html}</td>\n'
            f'        <td class="c-datum"><span class="status-datum" id="datum_{ls_key_attr}">{_esc(status_datum)}</span></td>\n'
            f'        <td class="c-bew">{bew_html}</td>\n'
            f'      </tr>\n'
        )

    modal_data_js = json.dumps(modal_data, ensure_ascii=False, indent=2)
    krit_headers  = "".join(
        f'<th class="c-krit-h" title="{short}">{short}</th>'
        for short, _ in SCORE_KRITERIEN
    )

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bewerbungsübersicht – Claudia</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f0f2f5; color: #222; padding: 1.5rem;
    }}
    h1 {{ color: #1a1a2e; margin-bottom: 0.2rem; font-size: 1.3rem; }}
    .subtitle {{ color: #888; font-size: 0.8rem; margin-bottom: 1.2rem; }}

    .table-wrap {{
      overflow-x: auto;
      overflow-y: auto;
      max-height: calc(100vh - 80px);
      border-radius: 10px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.09);
    }}
    table {{
      border-collapse: collapse;
      background: white;
      font-size: 0.77rem;
      white-space: nowrap;
    }}
    th {{
      background: #1a1a2e; color: white;
      padding: 8px 7px;
      text-align: left;
      font-size: 0.73rem; font-weight: 600;
      position: sticky; top: 0; z-index: 10;
    }}
    td {{
      padding: 7px 7px;
      border-bottom: 1px solid #f0f0f0;
      vertical-align: middle; color: #333;
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #f7f9ff; }}
    tr[data-status="Überspringen"] {{ opacity: 0.5; }}
    tr[data-status="Absage"]      {{ opacity: 0.42; }}

    /* ── Sticky Stelle-Spalte ── */
    .c-stelle {{
      position: sticky; left: 0; z-index: 5;
      background: white;
      min-width: 190px; max-width: 230px;
      white-space: normal; word-break: break-word;
      box-shadow: 2px 0 5px rgba(0,0,0,0.07);
    }}
    thead .c-stelle {{ z-index: 20; background: #1a1a2e; }}
    tr:hover .c-stelle {{ background: #f7f9ff; }}
    tr[data-status="Überspringen"] .c-stelle,
    tr[data-status="Absage"]       .c-stelle {{ background: white; }}
    tr[data-status="Überspringen"]:hover .c-stelle,
    tr[data-status="Absage"]:hover       .c-stelle {{ background: #f7f9ff; }}

    .c-firma {{
      display: block; font-size: 0.69rem;
      color: #999; margin-top: 2px;
      white-space: normal;
    }}

    /* Spaltenbreiten */
    .c-sm     {{ min-width: 62px; max-width: 80px; }}
    .c-sc     {{ min-width: 52px; max-width: 68px; text-align: center; }}
    .c-modal  {{ width: 26px; text-align: center; padding: 4px 2px; }}
    .c-status {{ min-width: 115px; max-width: 130px; }}
    .c-datum  {{ min-width: 72px; max-width: 82px; color: #999; font-size: 0.70rem; }}
    .c-bew    {{ min-width: 120px; }}

    /* Score-Kriterium-Spalten */
    .c-krit-h {{
      min-width: 36px; max-width: 50px;
      text-align: center; font-size: 0.66rem;
      padding: 8px 2px;
    }}
    .c-krit {{
      min-width: 36px; max-width: 50px;
      text-align: center;
      font-size: 0.70rem; font-weight: 600;
      padding: 5px 2px;
    }}
    .c-krit-na   {{ background: #f2f2f2; color: #ccc; }}
    .c-krit-zero {{ background: #ebebeb; color: #aaa; }}
    .c-krit-half {{ background: #fff3cd; color: #856404; }}
    .c-krit-full {{ background: #d4edda; color: #155724; }}

    /* Score-Badge */
    .score {{
      font-weight: 700; border-radius: 4px;
      padding: 2px 6px; display: inline-block;
    }}
    .score-high {{ background: #d4edda; color: #155724; }}
    .score-mid  {{ background: #fff3cd; color: #856404; }}
    .score-low  {{ background: #f8d7da; color: #721c24; }}

    a {{ color: #0055cc; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    .bew-link {{
      display: inline-block; font-size: 0.73rem;
      margin-right: 5px; white-space: nowrap;
    }}

    /* Status-Dropdown */
    select.status-sel {{
      font-size: 0.73rem; padding: 3px 4px;
      border: 1px solid #ccc; border-radius: 4px;
      background: white; cursor: pointer; width: 100%;
    }}
    select.status-sel[data-status="Interessant"] {{ border-color: #f0a500; background: #fffbf0; }}
    select.status-sel[data-status="Beworben"]    {{ border-color: #28a745; background: #f0faf4; }}
    select.status-sel[data-status="Absage"]      {{ border-color: #dc3545; background: #fff0f0; color: #721c24; }}
    select.status-sel[data-status="Überspringen"]{{ border-color: #bbb;    background: #f5f5f5; color: #999; }}

    /* Buttons */
    .btn-modal {{
      background: none; border: none; cursor: pointer;
      font-size: 0.95rem; padding: 0; opacity: 0.65;
    }}
    .btn-modal:hover {{ opacity: 1; }}

    /* ── Modal ── */
    #modal-overlay {{
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.42); z-index: 1000;
    }}
    #modal-box {{
      display: none; position: fixed;
      top: 50%; left: 50%; transform: translate(-50%, -50%);
      background: white; border-radius: 12px;
      padding: 1.5rem 1.8rem 1.2rem;
      min-width: 380px; max-width: min(92vw, 680px);
      max-height: 85vh; overflow-y: auto;
      z-index: 1001;
      box-shadow: 0 10px 36px rgba(0,0,0,0.22);
    }}
    #modal-title {{
      font-size: 0.98rem; font-weight: 700;
      color: #1a1a2e; margin-bottom: 0.15rem;
      white-space: normal;
    }}
    #modal-meta {{
      font-size: 0.75rem; color: #aaa;
      margin-bottom: 1rem;
    }}
    .modal-grid {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem;
    }}
    .modal-pro h4 {{ color: #155724; font-size: 0.80rem; margin-bottom: 0.4rem; }}
    .modal-con h4 {{ color: #721c24; font-size: 0.80rem; margin-bottom: 0.4rem; }}
    .modal-pro ul, .modal-con ul {{
      padding-left: 1.1rem; margin: 0;
      font-size: 0.76rem; color: #333; line-height: 1.45;
    }}
    .modal-pro li, .modal-con li {{ margin-bottom: 0.45rem; white-space: normal; }}
    #modal-close {{
      margin-top: 1.1rem; padding: 0.35rem 1.2rem;
      border: none; background: #1a1a2e; color: white;
      border-radius: 6px; cursor: pointer; font-size: 0.78rem;
    }}
    #modal-close:hover {{ background: #2d2d5e; }}

    /* ── Header Bar ── */
    .header-bar {{
      display: flex; align-items: flex-start;
      justify-content: space-between; margin-bottom: 1.2rem;
    }}
    .header-bar .subtitle {{ margin-bottom: 0; }}
    .btn-add-stelle {{
      background: #1a1a2e; color: white; border: none;
      border-radius: 6px; padding: 0.4rem 0.9rem;
      font-size: 0.80rem; cursor: pointer; white-space: nowrap;
      flex-shrink: 0; margin-top: 0.15rem;
    }}
    .btn-add-stelle:hover {{ background: #2d2d5e; }}

    /* ── ⚡ Generieren Button ── */
    .btn-gen {{
      background: none; border: 1px solid #ccc; border-radius: 4px;
      cursor: pointer; font-size: 0.73rem; padding: 2px 8px;
      color: #555; white-space: nowrap;
    }}
    .btn-gen:hover {{ background: #f0f0f0; border-color: #999; }}
    .btn-gen:disabled {{ opacity: 0.5; cursor: default; }}

    /* ── Add-Stelle Modal ── */
    #add-modal-overlay {{
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.42); z-index: 1000;
    }}
    #add-modal-box {{
      display: none; position: fixed;
      top: 50%; left: 50%; transform: translate(-50%, -50%);
      background: white; border-radius: 12px;
      padding: 1.5rem 1.8rem 1.2rem;
      width: min(92vw, 560px); max-height: 90vh; overflow-y: auto;
      z-index: 1001; box-shadow: 0 10px 36px rgba(0,0,0,0.22);
    }}
    #add-modal-box h2 {{ font-size: 1rem; color: #1a1a2e; margin-bottom: 1rem; font-weight: 700; }}
    .add-form label {{
      display: block; font-size: 0.78rem; font-weight: 600;
      margin-bottom: 0.2rem; color: #444;
    }}
    .add-form input, .add-form textarea {{
      width: 100%; border: 1px solid #ccc; border-radius: 5px;
      padding: 0.4rem 0.6rem; font-size: 0.78rem;
      margin-bottom: 0.8rem; font-family: inherit; box-sizing: border-box;
    }}
    .add-form textarea {{ resize: vertical; }}
    .add-form input:focus, .add-form textarea:focus {{ outline: none; border-color: #1a1a2e; }}
    .add-form-actions {{ display: flex; gap: 0.6rem; margin-top: 0.4rem; }}
    .btn-primary {{
      background: #1a1a2e; color: white; border: none;
      border-radius: 6px; padding: 0.4rem 1.1rem;
      font-size: 0.80rem; cursor: pointer;
    }}
    .btn-primary:hover {{ background: #2d2d5e; }}
    .btn-primary:disabled {{ opacity: 0.5; cursor: default; }}
    .btn-secondary {{
      background: #f0f0f0; color: #444; border: none;
      border-radius: 6px; padding: 0.4rem 1.1rem;
      font-size: 0.80rem; cursor: pointer;
    }}
    .btn-secondary:hover {{ background: #e0e0e0; }}
    #add-result {{ margin-top: 0.8rem; font-size: 0.80rem; }}
    .add-loading {{ color: #666; }}
    .add-error {{ color: #c00; }}
    .add-result-box {{
      background: #f8fff8; border: 1px solid #c3e6cb;
      border-radius: 6px; padding: 0.8rem;
    }}
    .add-result-box p {{ margin-bottom: 0.35rem; }}

    /* ── Filter-Bar ── */
    .filter-bar {{
      display: flex; gap: 0.6rem; flex-wrap: wrap;
      margin-bottom: 0.8rem; align-items: center;
    }}
    .filter-bar input {{
      flex: 1; min-width: 200px; max-width: 340px;
      padding: 6px 10px; border: 1px solid #ccc;
      border-radius: 6px; font-size: 0.82rem;
    }}
    .filter-bar select {{
      padding: 6px 8px; border: 1px solid #ccc;
      border-radius: 6px; font-size: 0.82rem;
      background: white; cursor: pointer;
    }}

    /* ── Suchlauf ── */
    .header-actions {{
      display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;
      justify-content: flex-end;
    }}
    #btn-suchlauf:disabled {{ opacity: 0.7; cursor: default; }}
    #suchlauf-banner {{
      display: none; background: #f0f7ff;
      border: 1px solid #b8d8f8; border-radius: 6px;
      padding: 0.5rem 1rem; font-size: 0.80rem; color: #1a1a2e;
      margin-bottom: 0.8rem;
    }}
    #suchlauf-banner.fertig {{ background: #f0fff4; border-color: #b0e0c0; color: #155724; }}

    /* ── Trotzdem bewerben ── */
    .btn-trotzdem {{
      background: none; border: 1px solid #f0a500; border-radius: 4px;
      cursor: pointer; font-size: 0.73rem; padding: 2px 8px;
      color: #856404; white-space: nowrap;
    }}
    .btn-trotzdem:hover {{ background: #fffbf0; }}
    .btn-trotzdem:disabled {{ opacity: 0.5; cursor: default; }}

    /* ── Bestätigungs-Popup ── */
    #confirm-overlay {{
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.42); z-index: 2000;
    }}
    #confirm-box {{
      display: none; position: fixed;
      top: 50%; left: 50%; transform: translate(-50%,-50%);
      background: white; border-radius: 12px;
      padding: 1.5rem 1.8rem 1.2rem;
      width: min(92vw, 400px);
      z-index: 2001; box-shadow: 0 10px 36px rgba(0,0,0,0.22);
    }}
    #confirm-box p {{ font-size: 0.90rem; color: #333; margin-bottom: 1.2rem; white-space: normal; }}
    .confirm-actions {{ display: flex; gap: 0.6rem; justify-content: flex-end; }}
  </style>
</head>
<body>
  <div class="header-bar">
    <div>
      <h1>Bewerbungsübersicht</h1>
      <p class="subtitle">Stand: {date.today().strftime("%d.%m.%Y")} &nbsp;&middot;&nbsp; {len(zeilen)} Stelle(n)</p>
    </div>
    <div class="header-actions">
      <button id="btn-suchlauf" class="btn-add-stelle" onclick="startSuchlauf()">🔍 Suchlauf starten</button>
      <button class="btn-add-stelle" onclick="openAddModal()">➕ Stelle hinzufügen</button>
    </div>
  </div>
  <div class="filter-bar">
    <input type="text" id="suche" placeholder="🔍 Stelle oder Firma suchen …" oninput="filterTabelle()" />
    <select id="filter-status" onchange="filterTabelle()">
      <option value="">Alle Status</option>
      <option value="Offen">Offen</option>
      <option value="Interessant">Interessant</option>
      <option value="Beworben">Beworben</option>
      <option value="Absage">Absage</option>
      <option value="Überspringen">Überspringen</option>
    </select>
    <select id="filter-score" onchange="filterTabelle()">
      <option value="">Alle Scores</option>
      <option value="8">Score ≥ 8</option>
      <option value="7">Score ≥ 7</option>
      <option value="6">Score ≥ 6</option>
    </select>
  </div>
  <div id="suchlauf-banner"><span id="suchlauf-banner-text"></span></div>

  <!-- Modal -->
  <div id="modal-overlay" onclick="closeModal()"></div>
  <div id="modal-box">
    <div id="modal-title"></div>
    <div id="modal-meta"></div>
    <div class="modal-grid">
      <div class="modal-pro"><h4>✅ Pro</h4><ul id="modal-pros"></ul></div>
      <div class="modal-con"><h4>❌ Con</h4><ul id="modal-cons"></ul></div>
    </div>
    <button id="modal-close" onclick="closeModal()">Schließen</button>
  </div>

  <!-- Bestätigungs-Popup -->
  <div id="confirm-overlay" onclick="closeConfirm()"></div>
  <div id="confirm-box">
    <p id="confirm-text"></p>
    <div class="confirm-actions">
      <button class="btn-secondary" onclick="closeConfirm()">Abbrechen</button>
      <button class="btn-primary" onclick="confirmBewerben()">Ja, erstellen</button>
    </div>
  </div>

  <!-- Add-Stelle Modal -->
  <div id="add-modal-overlay" onclick="closeAddModal()"></div>
  <div id="add-modal-box">
    <h2>➕ Stelle hinzufügen</h2>
    <form id="add-form" class="add-form" onsubmit="event.preventDefault(); stelleHinzufuegen();">
      <label for="add-firma">Firmenname *</label>
      <input id="add-firma" type="text" placeholder="z. B. Siemens AG" required>
      <label for="add-titel">Stellentitel *</label>
      <input id="add-titel" type="text" placeholder="z. B. Senior Product Owner (m/w/d)" required>
      <label for="add-url">URL (optional)</label>
      <input id="add-url" type="text" placeholder="https://...">
      <label for="add-text">Stellentext</label>
      <textarea id="add-text" rows="10" placeholder="Anzeigentext hier reinkopieren …"></textarea>
      <div class="add-form-actions">
        <button id="add-submit" type="submit" class="btn-primary">Analysieren &amp; Anschreiben erstellen</button>
        <button type="button" class="btn-secondary" onclick="closeAddModal()">Abbrechen</button>
      </div>
    </form>
    <div id="add-result"></div>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="c-sm">Datum</th>
          <th class="c-stelle">Stelle / Unternehmen</th>
          <th class="c-sc">Score</th>
          {krit_headers}
          <th class="c-modal" title="Pro &amp; Con">💬</th>
          <th class="c-status">Status</th>
          <th class="c-datum">Geändert</th>
          <th class="c-bew">Bewerbung</th>
        </tr>
      </thead>
      <tbody>
{zeilen_html}      </tbody>
    </table>
  </div>

  <script>
    var MD = {modal_data_js};

    function openModal(idx) {{
      var d = MD[idx];
      if (!d) return;
      document.getElementById('modal-title').textContent = d.stelle;
      document.getElementById('modal-meta').textContent  = d.firma + ' · ' + d.fz;
      var pros = document.getElementById('modal-pros');
      var cons = document.getElementById('modal-cons');
      pros.innerHTML = ''; cons.innerHTML = '';
      [d.pro1, d.pro2, d.pro3].forEach(function(t) {{
        if (t && t !== '–') {{ var li = document.createElement('li'); li.textContent = t; pros.appendChild(li); }}
      }});
      [d.con1, d.con2, d.con3].forEach(function(t) {{
        if (t && t !== '–') {{ var li = document.createElement('li'); li.textContent = t; cons.appendChild(li); }}
      }});
      document.getElementById('modal-overlay').style.display = 'block';
      document.getElementById('modal-box').style.display    = 'flex';
    }}

    function closeModal() {{
      document.getElementById('modal-overlay').style.display = 'none';
      document.getElementById('modal-box').style.display    = 'none';
    }}
    document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') {{ closeModal(); closeAddModal(); closeConfirm(); }} }});

    function pad(n) {{ return n < 10 ? '0' + n : '' + n; }}
    function heuteDatum() {{
      var d = new Date();
      return pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + '.' + d.getFullYear();
    }}

    function saveStatus(sel) {{
      var key    = sel.dataset.key;
      var status = sel.value;
      var datum  = heuteDatum();
      sel.dataset.status = status;
      var row = sel.closest('tr');
      if (row) row.dataset.status = status;
      var datumEl = document.getElementById('datum_' + key);
      if (datumEl) datumEl.textContent = datum;
      localStorage.setItem('bew_' + key, JSON.stringify({{ status: status, datum: datum }}));
    }}

    document.addEventListener('DOMContentLoaded', function() {{
      document.querySelectorAll('.status-sel').forEach(function(sel) {{
        var key   = sel.dataset.key;
        var saved = localStorage.getItem('bew_' + key);
        if (saved) {{
          try {{
            var data = JSON.parse(saved);
            if (data.status) sel.value = data.status;
            var el = document.getElementById('datum_' + key);
            if (el && data.datum) el.textContent = data.datum;
          }} catch (e) {{ sel.value = saved; }}
        }}
        sel.dataset.status = sel.value;
        var row = sel.closest('tr');
        if (row) row.dataset.status = sel.value;
      }});
    }});

    // ── Add-Stelle Modal ──
    function openAddModal() {{
      document.getElementById('add-modal-overlay').style.display = 'block';
      document.getElementById('add-modal-box').style.display     = 'block';
      document.getElementById('add-firma').focus();
    }}
    function closeAddModal() {{
      document.getElementById('add-modal-overlay').style.display = 'none';
      document.getElementById('add-modal-box').style.display     = 'none';
      document.getElementById('add-result').innerHTML = '';
      document.getElementById('add-form').reset();
    }}

    function stelleHinzufuegen() {{
      var firma = document.getElementById('add-firma').value.trim();
      var titel = document.getElementById('add-titel').value.trim();
      var url   = document.getElementById('add-url').value.trim();
      var text  = document.getElementById('add-text').value.trim();
      if (!firma || !titel) {{
        document.getElementById('add-result').innerHTML = '<p class="add-error">Bitte Firma und Titel ausfüllen.</p>';
        return;
      }}
      var btn = document.getElementById('add-submit');
      btn.disabled = true;
      document.getElementById('add-result').innerHTML = '<p class="add-loading">⏳ Analyse läuft … ca. 30 Sekunden</p>';
      fetch('/stelle-hinzufuegen', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{firma: firma, titel: titel, url: url, stellentext: text}})
      }})
      .then(function(r) {{ return r.json(); }})
      .then(function(data) {{
        btn.disabled = false;
        if (data.fehler) {{
          document.getElementById('add-result').innerHTML = '<p class="add-error">❌ ' + data.fehler + '</p>';
          return;
        }}
        var scoreKls = data.score >= 7 ? 'score-high' : (data.score >= 5 ? 'score-mid' : 'score-low');
        var html = '<div class="add-result-box">';
        html += '<p><span class="score ' + scoreKls + '">' + data.score + '/10</span>&nbsp; <strong>' + data.empfehlung + '</strong></p>';
        if (data.anschreiben_link) {{
          html += '<a href="' + data.anschreiben_link + '" target="_blank" class="bew-link">📄 Anschreiben</a> ';
        }}
        if (data.cv_link) {{
          html += '<a href="' + data.cv_link + '" target="_blank" class="bew-link">📋 CV</a>';
        }}
        html += '<p style="margin-top:0.6rem;color:#666;font-size:0.74rem;">✅ Gespeichert – Seite wird in 3 s neu geladen …</p>';
        html += '</div>';
        document.getElementById('add-result').innerHTML = html;
        setTimeout(function() {{ location.reload(); }}, 3000);
      }})
      .catch(function(err) {{
        btn.disabled = false;
        document.getElementById('add-result').innerHTML = '<p class="add-error">❌ Verbindungsfehler: ' + err.message + '</p>';
      }});
    }}

    // ── ⚡ Generieren ──
    function generiereUnterlagen(stelleKey, btn, fehlerLabel) {{
      var restoreText = fehlerLabel || '⚡ Generieren';
      btn.disabled = true;
      btn.textContent = '⏳ Erstelle Docs...';
      var existErr = btn.parentNode ? btn.parentNode.querySelector('.gen-error') : null;
      if (existErr) existErr.remove();
      fetch('/generieren', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{stelle_key: stelleKey}})
      }})
      .then(function(r) {{ return r.json(); }})
      .then(function(data) {{
        if (data.fehler) {{
          btn.disabled = false;
          btn.textContent = restoreText;
          var errEl = document.createElement('span');
          errEl.className = 'gen-error';
          errEl.style.cssText = 'display:block;color:#c00;font-size:0.70rem;margin-top:2px;white-space:normal;';
          errEl.textContent = '❌ ' + data.fehler;
          if (btn.parentNode) btn.parentNode.insertBefore(errEl, btn.nextSibling);
          return;
        }}
        var cell = btn.closest('td');
        var html = '';
        if (data.anschreiben_link) {{
          html += '<a href="' + data.anschreiben_link + '" target="_blank" class="bew-link">📄 Anschreiben</a>';
        }}
        if (data.cv_link) {{
          html += '<a href="' + data.cv_link + '" target="_blank" class="bew-link">📋 CV</a>';
        }}
        if (html) {{ cell.innerHTML = html; }}
        else {{ btn.disabled = false; btn.textContent = restoreText; }}
      }})
      .catch(function(err) {{
        btn.disabled = false;
        btn.textContent = restoreText;
        var errEl = document.createElement('span');
        errEl.className = 'gen-error';
        errEl.style.cssText = 'display:block;color:#c00;font-size:0.70rem;margin-top:2px;';
        errEl.textContent = '❌ Verbindungsfehler: ' + err.message;
        if (btn.parentNode) btn.parentNode.insertBefore(errEl, btn.nextSibling);
      }});
    }}

    // ── 🔍 Suchlauf starten ──
    var _suchlaufPollTimer  = null;
    var _suchlaufClockTimer = null;
    var _suchlaufStartMs    = null;

    function startSuchlauf() {{
      var btn = document.getElementById('btn-suchlauf');
      btn.disabled = true;
      _suchlaufStartMs = Date.now();
      fetch('/suchlauf-starten', {{ method: 'POST' }})
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
          if (data.fehler) {{
            btn.disabled = false;
            btn.textContent = '🔍 Suchlauf starten';
            return;
          }}
          _suchlaufClockTimer = setInterval(_updateSuchlauf, 1000);
          _suchlaufPollTimer  = setInterval(_pollSuchlauf,   5000);
          _updateSuchlauf();
        }})
        .catch(function() {{
          btn.disabled = false;
          btn.textContent = '🔍 Suchlauf starten';
        }});
    }}

    function _updateSuchlauf() {{
      if (!_suchlaufStartMs) return;
      var sek = Math.floor((Date.now() - _suchlaufStartMs) / 1000);
      var min = Math.floor(sek / 60);
      var s   = sek % 60;
      var zeit = min + ':' + (s < 10 ? '0' + s : s);
      document.getElementById('btn-suchlauf').textContent = '⏳ Läuft... (' + zeit + ')';
      var banner = document.getElementById('suchlauf-banner');
      if (banner) {{
        banner.style.display = 'block';
        banner.className = '';
        document.getElementById('suchlauf-banner-text').textContent =
          '🔍 Suchlauf läuft – Stellen werden gesucht und bewertet... (' + zeit + ')';
      }}
    }}

    function _pollSuchlauf() {{
      fetch('/suchlauf-status')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
          if (!data.laeuft) {{
            clearInterval(_suchlaufPollTimer);
            clearInterval(_suchlaufClockTimer);
            _suchlaufPollTimer = _suchlaufClockTimer = null;
            var btn = document.getElementById('btn-suchlauf');
            btn.disabled = false;
            btn.textContent = '🔍 Suchlauf starten';
            var banner = document.getElementById('suchlauf-banner');
            if (banner) {{
              banner.className = 'fertig';
              banner.style.display = 'block';
              var neu = data.neue_stellen !== undefined ? data.neue_stellen : 0;
              var dauer = data.dauer || '';
              document.getElementById('suchlauf-banner-text').innerHTML =
                '✅ Suchlauf abgeschlossen (' + dauer + ') — <strong>' + neu +
                ' neue Stelle(n)</strong> gefunden. ' +
                '<button class="btn-secondary" onclick="location.reload()" ' +
                'style="margin-left:0.5rem;padding:2px 10px;font-size:0.76rem;">🔄 Seite neu laden</button>';
            }}
          }}
        }});
    }}

    // ── 📄 Generieren (Low-Score) ──
    var _confirmKey = null;
    var _confirmBtn = null;

    function trotzdemBewerben(stelleKey, score, btn) {{
      _confirmKey = stelleKey;
      _confirmBtn = btn;
      document.getElementById('confirm-text').textContent =
        'Score ist ' + score + '/10 — Anschreiben + CV erstellen?';
      document.getElementById('confirm-overlay').style.display = 'block';
      document.getElementById('confirm-box').style.display     = 'block';
    }}

    function closeConfirm() {{
      document.getElementById('confirm-overlay').style.display = 'none';
      document.getElementById('confirm-box').style.display     = 'none';
      _confirmKey = null;
      _confirmBtn = null;
    }}

    function confirmBewerben() {{
      var key = _confirmKey;
      var btn = _confirmBtn;
      closeConfirm();
      if (key && btn) {{
        generiereUnterlagen(key, btn, '📄 Generieren');
      }}
    }}
    // ── 🔍 Filter ──
    function filterTabelle() {{
      var suche    = document.getElementById('suche').value.toLowerCase();
      var status   = document.getElementById('filter-status').value;
      var minScore = parseInt(document.getElementById('filter-score').value) || 0;
      document.querySelectorAll('tbody tr').forEach(function(row) {{
        var text      = row.textContent.toLowerCase();
        var rowStatus = row.dataset.status || '';
        var scoreEl   = row.querySelector('.score');
        var rowScore  = scoreEl ? parseInt(scoreEl.textContent) : 0;
        var ok = (!suche || text.includes(suche))
              && (!status || rowStatus === status)
              && (rowScore >= minScore);
        row.style.display = ok ? '' : 'none';
      }});
    }}

  </script>
</body>
</html>"""

    UEBERSICHT_HTML.write_text(html, encoding="utf-8")


def _speichere_bewerbungsunterlagen(ctx: JobContext, slug: str) -> None:
    BEWERBUNGEN_DIR.mkdir(parents=True, exist_ok=True)
    if ctx.anschreiben_html:
        pfad = BEWERBUNGEN_DIR / f"{slug}_anschreiben.html"
        pfad.write_text(ctx.anschreiben_html, encoding="utf-8")
        print(f"[DEBUG output] Geschrieben: {pfad.resolve()} ({pfad.stat().st_size} bytes)")
    if ctx.cv_html:
        pfad = BEWERBUNGEN_DIR / f"{slug}_cv.html"
        pfad.write_text(ctx.cv_html, encoding="utf-8")
        print(f"[DEBUG output] Geschrieben: {pfad.resolve()} ({pfad.stat().st_size} bytes)")
