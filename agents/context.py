from dataclasses import dataclass, field
from typing import Optional


@dataclass
class JobContext:
    # Eingabe
    stellentext: str = ""
    firmenname:  str = ""
    stellentitel: str = ""
    url:          str = ""
    profil_text:  str = ""

    # Analyst-Ergebnis
    score:        Optional[int] = None
    empfehlung:   str = ""          # "Bewerben" | "Überspringen" | "Nicht passend"
    branche:      str = ""          # z. B. "B2B SaaS", "HealthTech"
    fahrtzeit:    int = 0           # Minuten von München Laim per MVV; 0 = Remote
    pro_1:        str = ""
    pro_2:        str = ""
    pro_3:        str = ""
    con_1:        str = ""
    con_2:        str = ""
    con_3:        str = ""
    score_details: list[str] = field(default_factory=list)

    # Rückwärtskompatibilität für Writer Agent (aus pro_*/con_* befüllt)
    begruendung: str = ""
    staerken:    list[str] = field(default_factory=list)
    cons:        list[str] = field(default_factory=list)

    # Writer-Ergebnis – Platzhalter für HTML-Vorlagen
    sprache:           str = "de"
    jobtitel_header:   str = ""
    tagline:           str = ""
    highlight_1:       str = ""
    highlight_2:       str = ""
    ansprechperson:    str = ""
    einstieg:          str = ""
    erfolge_absatz:    str = ""
    motivation_absatz: str = ""
    schluss_absatz:    str = ""
    cv_anpassungen:    str = ""
    fokus_entwicklung: str = ""
    erfahrung_staerke: str = ""
    arbeitsweise_team: str = ""
    fit_rolle:         str = ""

    # Fertige HTML-Dokumente
    anschreiben_html: str = ""
    cv_html:          str = ""

    # Tracking
    status:          str = "Offen"   # Offen | Interessant | Beworben | Überspringen
    bewerbung_link:  str = ""        # relativer Pfad zur _anschreiben.html
    gespeichert:     bool = False
