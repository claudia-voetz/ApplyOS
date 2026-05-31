import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import anthropic
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Selenium für JavaScript-lastige Seiten (Playwright benötigt greenlet-DLL,
# die für Python 3.14 noch nicht verfügbar ist)
try:
    from selenium import webdriver as _selenium_webdriver
    from selenium.webdriver.chrome.options import Options as _ChromeOptions
    from selenium.webdriver.chrome.service import Service as _ChromeService
    from webdriver_manager.chrome import ChromeDriverManager as _ChromeDriverManager
    _JS_BROWSER_OK = True
except ImportError:
    _JS_BROWSER_OK = False

load_dotenv()

MODEL                 = "claude-sonnet-4-6"
MAX_TEXT_ZEICHEN      = 3000
MAX_LINKS_PRO_SEITE   = 20
GESEHENE_STELLEN_JSON = Path("output/gesehene_stellen.json")

ERLAUBTE_DOMAINS = {
    "www.stepstone.de",
    "de.indeed.com",
    "www.xing.com",
    "jobboerse.arbeitsagentur.de",
    "www.linkedin.com",
    "www.glassdoor.de",
    "www.experteer.de",
    "jobs.personio.de",
    "jobs.personio.com",
    "join.com",
    "www.join.com",
    "www.monster.de",
}

PORTAL_NAMEN = {
    "stepstone.de":      "StepStone",
    "indeed.com":        "Indeed",
    "xing.com":          "Xing",
    "arbeitsagentur.de": "Arbeitsagentur",
    "linkedin.com":      "LinkedIn",
    "glassdoor.de":      "Glassdoor",
    "experteer.de":      "Experteer",
    "personio.de":       "Personio",
    "join.com":          "Join",
    "monster.de":        "Monster",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
}

JOB_LINK_MUSTER = {
    "stepstone.de":      ["/stellenangebote--"],
    "indeed.com":        ["/viewjob", "/rc/clk", "/pagead/clk"],
    "xing.com":          ["/jobs/muenchen-", "/jobs/deutschland-", "/jobs/remote-"],
    "arbeitsagentur.de": ["angebotsnummer=", "/vamJB/stelle/"],
    "linkedin.com":      ["/jobs/view/"],
    "glassdoor.de":      ["/job-listing/", "/Job/"],
    "experteer.de":      ["/job-", "/stellenangebot-"],
    "personio.de":       ["/job/"],
    "personio.com":      ["/job/"],
    "join.com":          ["/jobs/", "/o/", "/companies/"],
    "monster.de":        ["/job-opening/", "/stellenangebot/"],
}

# Pfadmuster in Firmen-URLs, die auf eine individuelle Stellenseite hinweisen
JOB_PFAD_MUSTER = frozenset({
    "/offer/", "/offer-redirect/", "/vacancy/", "/lavoro/", "/position/", "/stellen/",
    "/karriere/jobs/",
})

BLACKLIST_FIRMEN: frozenset[str] = frozenset({
    "jobriver", "instaffo", "hubside", "hays", "michael page",
    "robert half", "adecco", "manpower", "randstad", "gulp",
    "trenkwalder", "avantgarde", "orizon", "akka", "brunel",
    "amadeus fire",
})

# Domains, die JavaScript-Rendering für vollständige Inhalte benötigen
JS_DOMAINS = frozenset({
    "linkedin.com", "join.com", "careers.epam.com",
    "karriere.doctarigroup.com",  # offer-redirect Links nur per JS sichtbar
    "jobs.ashbyhq.com",           # Ashby-Job-Board (iFrame-Quelle von munichelectrification)
})

KARRIERE_SUFFIXE = [
    "/jobs",
    "/karriere",
    "/careers",
    "/stellenangebote",
    "/de/karriere",
    "/de/jobs",
    "/en/careers",
]

# ── Such-URLs (Portale) ────────────────────────────────────────────────────
SUCH_URLS = [
    # StepStone München
    "https://www.stepstone.de/jobs/product-owner/in-muenchen.html",
    "https://www.stepstone.de/jobs/product-manager/in-muenchen.html",
    "https://www.stepstone.de/jobs/ai-product-owner/in-muenchen.html",
    "https://www.stepstone.de/jobs/head-of-product/in-muenchen.html",
    "https://www.stepstone.de/jobs/digitalisierung-behoerden/in-muenchen.html",
    "https://www.stepstone.de/jobs/e-government/in-muenchen.html",
    # Indeed München
    "https://de.indeed.com/jobs?q=product+owner&l=M%C3%BCnchen%2C+Bayern",
    "https://de.indeed.com/jobs?q=product+manager&l=M%C3%BCnchen%2C+Bayern",
    "https://de.indeed.com/jobs?q=ai+product+owner&l=M%C3%BCnchen%2C+Bayern",
    "https://de.indeed.com/jobs?q=head+of+product&l=M%C3%BCnchen%2C+Bayern",
    "https://de.indeed.com/jobs?q=digitalisierung+%C3%B6ffentliche+verwaltung&l=M%C3%BCnchen%2C+Bayern",
    "https://de.indeed.com/jobs?q=e-government+product+owner&l=M%C3%BCnchen%2C+Bayern",
    # Personio
    "https://jobs.personio.de/search?query=product+owner&location=M%C3%BCnchen",
    "https://jobs.personio.de/search?query=product+manager&location=M%C3%BCnchen",
    # Glassdoor
    "https://www.glassdoor.de/Job/munchen-product-owner-jobs-SRCH_IL.0,7_IC2640729_KO8,21.htm",
    "https://www.glassdoor.de/Job/munchen-product-manager-jobs-SRCH_IL.0,7_IC2640729_KO8,23.htm",
    # Arbeitsagentur
    "https://jobboerse.arbeitsagentur.de/vamJB/stellenangebote.html?what=Product+Owner&where=M%C3%BCnchen&umkreis=25",
    "https://jobboerse.arbeitsagentur.de/vamJB/stellenangebote.html?what=Product+Manager&where=M%C3%BCnchen&umkreis=25",
    "https://jobboerse.arbeitsagentur.de/vamJB/stellenangebote.html?what=E-Government+Product+Owner&umkreis=25",
]

# ── Direkte Firmen-Karriereseiten ──────────────────────────────────────────
FIRMEN_KARRIERE_URLS = [
    "https://www.diva-e.com/karriere/",
    "https://gofore.com/de/",
    "https://www.cgi.com/de/de/karriere",
    "https://www.allianz.com/de/karriere.html",
    "https://www.mach.de/karriere/",
    "https://www.vispiron.de/karriere/",
    "https://careers.epam.com",
    "https://www.bikeleasing.de/karriere",
    "https://jobs.ashbyhq.com/munich-electrification",  # Ashby-Board (iFrame-Quelle der career-Seite)
    "https://www.bluemetering.de/karriere/",  # /jobs gibt 403; /karriere/ listet alle Stellen
    "https://www.planerio.de/jobs",
    "https://www.fabasoft.com/de/karriere/jobs",
    "https://www.vectornator.io/careers",
    "https://enopai.com/jobs",
    "https://karriere.doctarigroup.com",
    "https://job.teoresigroup.com",
    "https://join.com/companies/vispiron-gmbh",
    "https://join.com/companies/vispiron-gmbh/16073933-product-owner-m-w-d-fleet-tech-plattform",
    "https://enopai.jobs.personio.com",
    "https://careers.epam.com/en/vacancy/senior-product-manager-m-f-d-digital-data-ai-solutions",
    "https://job.teoresigroup.com/lavoro/product-owner-m-w-d-digitale-b2b-cloud-services/",
    "https://jobs.ashbyhq.com/munich-electrification/7a10f170-0636-4601-af80-1923a9af588c",
    "https://www.bluemetering.de/karriere/jobs/senior-solution-owner-m-w-d.php",
    "https://jobportal.brunata-muenchen.de/senior-solution-owner-mwd-de-f1026.html",
    # Public Sector & Verwaltungsdigitalisierung (München)
    "https://karriere.digitalfabrix.de/",
    "https://karriere.digitalfabrix.de/jobposting/296ef31f793caf3d8189b1c4a9514b149a1d715e",
    "https://www.akdb.de/karriere/",
    "https://www.adesso.de/de/jobs/",
    "https://www.sopra-steria.de/karriere/",
    "https://www.mach.de/karriere/",
]

# ── LinkedIn (Firmennamen-Extraktion, nicht Job-Links) ────────────────────
LINKEDIN_SUCH_URLS = [
    "https://www.linkedin.com/jobs/search/?keywords=product+owner&location=M%C3%BCnchen",
    "https://www.linkedin.com/jobs/search/?keywords=ai+product+owner&location=M%C3%BCnchen",
    "https://www.linkedin.com/jobs/search/?keywords=head+of+product&location=M%C3%BCnchen",
    "https://www.linkedin.com/jobs/search/?keywords=e-government+product+owner",
    "https://www.linkedin.com/jobs/search/?keywords=digitalisierung+beh%C3%B6rden+product+owner",
]

SYSTEM_PROMPT = """\
Du bist ein Search Agent. Du erhältst den HTML-Text von {anzahl_portale} Seiten
(Job-Portale + Firmenwebsites) sowie Listen mit gefundenen Job-Links.

Deine Aufgabe: Extrahiere bis zu {max_stellen} passende Stellenanzeigen.

Gesuchte Stellen:
- Jobtitel: Product Owner, Product Manager, AI Product Owner,
  Automation Product Manager, Head of Product,
  Agentic AI Product Manager, Digital Product Owner,
  Solution Owner, Solution Manager,
  E-Government Product Owner, Digitalisierungsmanager,
  Product Owner Verwaltung, Product Owner öffentlicher Dienst
- Standort: München ODER Remote (Deutschland, 100%)
- Bevorzugte Branchen: B2B SaaS, Plattformen, Tools, HealthTech, InsurTech,
  Travel, Mobility, Consulting mit digitalem Produktfokus,
  Öffentliche Verwaltung / Behörden / E-Government / GovTech,
  Soziales / Non-Profit / NGO,
  AI Solutions, Automatisierung, Digitalisierung
- Ausschluss: reine PM-Rollen ohne Produktverantwortung,
  vollständig On-Site, Associate/Junior-Level

Regeln:
- Nutze BEVORZUGT die URLs aus den "Gefundene Job-Links"-Abschnitten — das sind echte Links
- Nutze NUR Jobtitel und Firmen die du tatsächlich im Text siehst
- Wenn du keine passenden Stellen findest, gib [] zurück

Antworte NUR mit einem JSON-Array, keine Einleitung, kein Kommentar:
[
  {{
    "portal": "StepStone",
    "url": "https://...",
    "titel": "Jobtitel",
    "firma": "Firmenname",
    "stellentext": "Beschreibung oder Zusammenfassung der Stelle"
  }}
]\
"""


# ── Hilfsfunktionen ────────────────────────────────────────────────────────

def _portal_name(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    for key, name in PORTAL_NAMEN.items():
        if key in netloc:
            return name
    return urlparse(url).netloc.replace("www.", "") or "Firma"


def _ist_portal(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return any(p in domain for p in PORTAL_NAMEN)


def _domain_erlaubt(url: str, streng: bool = True) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        if not streng:
            return bool(domain) and "." in domain
        if "personio.com" in domain:
            return True
        return domain in ERLAUBTE_DOMAINS
    except Exception:
        return False


def _ist_blacklist_firma(firma: str) -> bool:
    firma_lower = firma.lower()
    return any(b in firma_lower for b in BLACKLIST_FIRMEN)


def _seite_laden(url: str, besuchte_urls: list[str], streng: bool = True) -> tuple[str, str]:
    """Gibt (text_oder_fehler, raw_html) zurück."""
    if not _domain_erlaubt(url, streng=streng):
        domain = urlparse(url).netloc
        return f"FEHLER: Domain '{domain}' nicht erlaubt.", ""
    besuchte_urls.append(url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if "text/html" not in resp.headers.get("Content-Type", ""):
            return f"FEHLER: Kein HTML", ""
        return resp.text, resp.text
    except requests.RequestException as e:
        return f"FEHLER: {e}", ""


def _html_zu_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > MAX_TEXT_ZEICHEN:
        text = text[:MAX_TEXT_ZEICHEN] + "\n[... gekürzt ...]"
    return text


def _job_links_extrahieren(html: str, base_url: str) -> list[str]:
    """Extrahiert bekannte Job-Link-Muster von Portal-Seiten."""
    if not html:
        return []
    soup  = BeautifulSoup(html, "html.parser")
    domain = urlparse(base_url).netloc.lower()
    muster = next(
        (patterns for key, patterns in JOB_LINK_MUSTER.items() if key in domain),
        [],
    )
    links: list[str] = []
    seen:  set[str]  = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        if not _domain_erlaubt(href) or href in seen or href == base_url:
            continue
        if any(p in href for p in muster):
            seen.add(href)
            links.append(href)
        if len(links) >= MAX_LINKS_PRO_SEITE:
            break
    return links


def _produkt_links_extrahieren(html: str, base_url: str) -> list[str]:
    """Extrahiert Links mit 'product' im Pfad oder Linktext (Firmen-Karriereseiten)."""
    if not html:
        return []
    soup  = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen:  set[str]  = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text().strip().lower()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        if href in seen:
            continue
        href_l = href.lower()
        if (
            "product" in href_l or "owner" in href_l or "solution" in href_l
            or "product" in text or "owner" in text or "solution" in text
            or any(m in href_l for m in JOB_PFAD_MUSTER)
        ):
            seen.add(href)
            links.append(href)
        if len(links) >= MAX_LINKS_PRO_SEITE:
            break
    return links


def _extrahiere_firmennamen_aus_linkedin(html: str) -> list[str]:
    """Versucht Firmennamen aus LinkedIn-Job-Suchergebnissen zu extrahieren (Best-Effort)."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    firmennamen: list[str] = []
    seen: set[str] = set()
    klassen = [
        "base-search-card__subtitle",
        "job-search-card__company-name",
        "job-card-container__company-name",
        "artdeco-entity-lockup__subtitle",
    ]
    for cls in klassen:
        for el in soup.find_all(class_=re.compile(cls)):
            name = el.get_text().strip()
            key  = name.lower()
            if name and key not in seen and len(name) > 2:
                seen.add(key)
                firmennamen.append(name)
    return firmennamen[:15]


def _karriere_url_finden(firma_name: str) -> str | None:
    """Slug-basierte Suche nach einer Karriereseite für einen Firmennamen."""
    firma = firma_name.strip()
    if not firma:
        return None
    slug = re.sub(r"[^a-zA-Z0-9]", "", re.split(r"\s+", firma)[0].lower())
    if len(slug) < 2:
        return None
    varianten = [
        f"https://www.{slug}.de{suffix}"
        for suffix in KARRIERE_SUFFIXE
    ] + [
        f"https://www.{slug}.com{suffix}"
        for suffix in KARRIERE_SUFFIXE
    ]
    for url in varianten:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
            if resp.status_code < 400:
                print(f"    >> Karriereseite gefunden: {url}")
                return url
        except requests.RequestException:
            continue
    return None


def _firmen_url_finden(stelle: dict) -> str | None:
    """Firmenwebsite aus Stellentext extrahieren oder per Slug suchen."""
    text = stelle.get("stellentext", "") + " " + stelle.get("firma", "")
    # Schritt 1: Explizite URL im Text
    for url in re.findall(r'https?://[^\s\'"<>]+', text):
        if not _ist_portal(url) and urlparse(url).netloc:
            return url.rstrip(".,)")
    # Schritt 2: Slug-basierte Suche
    return _karriere_url_finden(stelle.get("firma", ""))


def _braucht_js_browser(url: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    return any(d in netloc for d in JS_DOMAINS)


def _playwright_laden(url: str, besuchte_urls: list[str], streng: bool = False) -> tuple[str, str]:
    """Lädt JavaScript-lastige Seiten via Headless Chrome (Selenium).

    Gleiche Rückgabe wie _seite_laden: (text_oder_fehler, raw_html).
    Implementiert mit Selenium statt Playwright, da greenlet für Python 3.14
    noch kein kompiliertes Binary hat.
    """
    if not _domain_erlaubt(url, streng=streng):
        domain = urlparse(url).netloc
        return f"FEHLER: Domain '{domain}' nicht erlaubt.", ""
    besuchte_urls.append(url)

    if not _JS_BROWSER_OK:
        print("  [JS-Browser] Selenium nicht verfügbar — falle zurück auf requests.")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
            if "text/html" not in resp.headers.get("Content-Type", ""):
                return "FEHLER: Kein HTML", ""
            return resp.text, resp.text
        except requests.RequestException as e:
            return f"FEHLER: {e}", ""

    try:
        os.environ.setdefault("WDM_LOG", "0")  # webdriver-manager-Logs unterdrücken
        opts = _ChromeOptions()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument(f"--user-agent={HEADERS['User-Agent']}")
        opts.add_argument("--lang=de-DE")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("prefs", {"intl.accept_languages": "de,de_DE"})
        drv = _selenium_webdriver.Chrome(
            service=_ChromeService(_ChromeDriverManager().install()),
            options=opts,
        )
        drv.set_page_load_timeout(25)
        drv.get(url)
        time.sleep(3)  # JS-Rendering abwarten
        html = drv.page_source
        drv.quit()
        return html, html
    except Exception as e:
        return f"FEHLER (JS-Browser): {e}", ""


def _api_call_mit_retry(client: anthropic.Anthropic, **kwargs) -> anthropic.types.Message:
    for versuch in range(3):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            if versuch == 2:
                raise
            print("  [Search] Rate-Limit — warte 65 Sekunden ...")
            time.sleep(65)
        except anthropic.APIConnectionError:
            if versuch == 2:
                raise
            print("  [Search] Verbindungsfehler — warte 15 Sekunden ...")
            time.sleep(15)
    raise RuntimeError("Unerreichbar")


def _gesehene_laden() -> set[str]:
    if GESEHENE_STELLEN_JSON.exists():
        try:
            return set(json.loads(GESEHENE_STELLEN_JSON.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return set()


def _gesehene_speichern(urls: set[str]) -> None:
    GESEHENE_STELLEN_JSON.parent.mkdir(parents=True, exist_ok=True)
    GESEHENE_STELLEN_JSON.write_text(
        json.dumps(sorted(urls), ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Hauptfunktion ──────────────────────────────────────────────────────────

def run(max_stellen: int = 10) -> list[dict]:
    client        = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    besuchte_urls: list[str] = []
    gesehene_urls = _gesehene_laden()

    print(f"[Search] Suche gestartet (max. {max_stellen} Stellen) ...")
    if gesehene_urls:
        print(f"[Search] {len(gesehene_urls)} bereits bekannte URL(s) werden übersprungen.")

    seiten_abschnitte: list[str] = []

    # ── 1. Portale ─────────────────────────────────────────────────────────
    print("\n[Search] === Job-Portale ===")
    for url in SUCH_URLS:
        portal = _portal_name(url)
        print(f"  [{portal}] {url}")
        raw, html = _seite_laden(url, besuchte_urls)
        text      = _html_zu_text(html) if html else raw
        job_links = _job_links_extrahieren(html, url)

        abschnitt = f"=== {portal.upper()} ===\nURL: {url}\n\n{text}"
        if job_links:
            abschnitt += "\n\nGefundene Job-Links:\n" + "\n".join(f"- {l}" for l in job_links)
            print(f"    >> {len(job_links)} Job-Link(s)")
        seiten_abschnitte.append(abschnitt)

    # ── 2. Direkte Firmen-Karriereseiten ───────────────────────────────────
    print("\n[Search] === Firmen-Karriereseiten ===")
    for url in FIRMEN_KARRIERE_URLS:
        firma = urlparse(url).netloc.replace("www.", "")
        js = _braucht_js_browser(url)
        print(f"  [{'JS' if js else 'req'}][{firma}] {url}")
        if js:
            raw, html = _playwright_laden(url, besuchte_urls, streng=False)
        else:
            raw, html = _seite_laden(url, besuchte_urls, streng=False)
        if not html:
            print(f"    >> Nicht erreichbar: {raw[:80]}")
            continue
        text          = _html_zu_text(html)
        produkt_links = _produkt_links_extrahieren(html, url)

        abschnitt = f"=== FIRMA: {firma.upper()} ===\nURL: {url}\n\n{text}"
        if produkt_links:
            abschnitt += "\n\nGefundene Product-Job-Links:\n" + "\n".join(f"- {l}" for l in produkt_links)
            print(f"    >> {len(produkt_links)} Product-Link(s)")
        seiten_abschnitte.append(abschnitt)

        # Gefundene Job-Seiten direkt laden — Claude bekommt den echten Stellentext
        for job_link in produkt_links[:2]:
            if job_link in besuchte_urls:
                continue
            js_j = _braucht_js_browser(job_link)
            if js_j:
                raw_j, html_j = _playwright_laden(job_link, besuchte_urls, streng=False)
            else:
                raw_j, html_j = _seite_laden(job_link, besuchte_urls, streng=False)
            if not html_j:
                continue
            text_j = _html_zu_text(html_j)
            if len(text_j) < 100:
                continue
            seiten_abschnitte.append(
                f"=== JOB (via {firma.upper()}): {job_link} ===\n\n{text_j}"
            )
            print(f"    >> Job-Seite geladen: {job_link}")

    # ── 3. LinkedIn → Firmennamen → Karriereseiten ─────────────────────────
    print("\n[Search] === LinkedIn-Firmen-Extraktion (JS-Browser) ===")
    for li_url in LINKEDIN_SUCH_URLS:
        print(f"  [JS][LinkedIn] {li_url}")
        raw, html = _playwright_laden(li_url, besuchte_urls, streng=True)
        if not html:
            print("    >> Nicht erreichbar oder blockiert.")
            continue
        firmennamen = _extrahiere_firmennamen_aus_linkedin(html)
        if not firmennamen:
            print("    >> Keine Firmennamen extrahiert (LinkedIn blockiert möglicherweise).")
            continue
        print(f"    >> {len(firmennamen)} Firma(en): {', '.join(firmennamen[:5])}")
        for firma in firmennamen[:5]:
            karriere_url = _karriere_url_finden(firma)
            if not karriere_url:
                continue
            raw2, html2 = _seite_laden(karriere_url, besuchte_urls, streng=False)
            if not html2:
                continue
            text2  = _html_zu_text(html2)
            links2 = _produkt_links_extrahieren(html2, karriere_url)
            abschnitt = f"=== FIRMA (via LinkedIn): {firma.upper()} ===\nURL: {karriere_url}\n\n{text2}"
            if links2:
                abschnitt += "\n\nGefundene Product-Job-Links:\n" + "\n".join(f"- {l}" for l in links2)
            seiten_abschnitte.append(abschnitt)

            for job_link in links2[:2]:
                if job_link in besuchte_urls:
                    continue
                raw_j, html_j = _seite_laden(job_link, besuchte_urls, streng=False)
                if not html_j:
                    continue
                text_j = _html_zu_text(html_j)
                if len(text_j) < 100:
                    continue
                seiten_abschnitte.append(
                    f"=== JOB (via {firma.upper()}): {job_link} ===\n\n{text_j}"
                )

    print(f"\n[Search] {len(seiten_abschnitte)} Seiten geladen. Analysiere mit Claude ...")

    # ── 4. Claude extrahiert Jobs ──────────────────────────────────────────
    user_content = (
        f"Hier sind die Inhalte von {len(seiten_abschnitte)} Seiten:\n\n"
        + "\n\n---\n\n".join(seiten_abschnitte)
        + f"\n\nBitte extrahiere bis zu {max_stellen} passende Stellen als JSON."
    )

    response = _api_call_mit_retry(
        client,
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT.format(
            anzahl_portale=len(seiten_abschnitte),
            max_stellen=max_stellen,
        ),
        messages=[{"role": "user", "content": user_content}],
    )

    stellen: list[dict] = []
    for block in response.content:
        if hasattr(block, "text"):
            match = re.search(r"\[.*\]", block.text, re.DOTALL)
            if match:
                try:
                    alle = json.loads(match.group())
                    gesehen_dieser_lauf: set[str] = set()
                    uebersprungen = 0
                    for s in alle:
                        url = s.get("url", "")
                        if not url:
                            continue
                        if url in gesehene_urls or url in gesehen_dieser_lauf:
                            uebersprungen += 1
                            continue
                        gesehen_dieser_lauf.add(url)
                        stellen.append(s)
                        if len(stellen) >= max_stellen:
                            break
                    if uebersprungen:
                        print(f"[Search] {uebersprungen} bereits bekannte Stelle(n) übersprungen.")
                    print(f"[Search] {len(stellen)} Stelle(n) extrahiert (dedupliziert).")
                except json.JSONDecodeError as e:
                    print(f"[Search] JSON-Fehler: {e}")
            break

    # ── 5. Blacklist-Filter ────────────────────────────────────────────────
    if stellen:
        gefiltert: list[dict] = []
        for s in stellen:
            firma = s.get("firma", "")
            if _ist_blacklist_firma(firma):
                print(f"  [Blacklist] '{firma}' gefiltert.")
            else:
                gefiltert.append(s)
        entfernt = len(stellen) - len(gefiltert)
        if entfernt:
            print(f"[Search] {entfernt} Stelle(n) durch Blacklist entfernt.")
        stellen = gefiltert

    # ── 6. Volltexte nachladen ─────────────────────────────────────────────
    if stellen:
        print("[Search] Lade Volltexte ...")
        for stelle in stellen:
            url = stelle.get("url", "")
            if not url or url in besuchte_urls:
                continue
            ist_portal = _ist_portal(url)
            # Portale: nur erlaubte Domains; Firmen-URLs: immer zulassen
            if ist_portal and not _domain_erlaubt(url, streng=True):
                continue
            portal = _portal_name(url)
            js = _braucht_js_browser(url)
            print(f"  [{'JS' if js else 'req'}][{portal}] {url}")
            if js:
                raw, html = _playwright_laden(url, besuchte_urls, streng=ist_portal)
            else:
                raw, html = _seite_laden(url, besuchte_urls, streng=ist_portal)
            volltext  = _html_zu_text(html) if html else raw

            if not volltext or volltext.startswith("FEHLER") or len(volltext) < 200:
                firmen_url = _firmen_url_finden(stelle)
                if firmen_url:
                    print(f"    >> Portal geblockt – versuche Firmenwebsite: {firmen_url}")
                    raw2, html2 = _seite_laden(firmen_url, besuchte_urls, streng=False)
                    volltext2   = _html_zu_text(html2) if html2 else raw2
                    if volltext2 and not volltext2.startswith("FEHLER") and len(volltext2) > 200:
                        stelle["stellentext"] = volltext2
                        stelle["quelle"]      = firmen_url
                        print("    >> Firmenwebsite erfolgreich geladen ✓")
                    else:
                        print("    >> Firmenwebsite auch nicht erreichbar.")
            else:
                stelle["stellentext"] = volltext

    print(f"\n[Search] Besuchte Seiten: {len(besuchte_urls)}")

    neue_urls = {s.get("url", "") for s in stellen if s.get("url")}
    if neue_urls:
        gesehene_urls.update(neue_urls)
        _gesehene_speichern(gesehene_urls)
        print(f"[Search] {len(neue_urls)} neue URL(s) gespeichert.")

    if stellen:
        print(f"[Search] {len(stellen)} Stelle(n) bereit.\n")
        return stellen

    print("[Search] Keine Stellen gefunden.")
    return []
