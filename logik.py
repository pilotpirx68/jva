#!/usr/bin/env python3
"""
logik.py
========
Gemeinsame Logik für die Tkinter- und die Streamlit-Version.
Enthält TEIL 1 (Gerichtsfinder) und TEIL 2 (JVA-Zuordnung M-V) – ohne jede
Oberfläche, damit beide Frontends dieselben Funktionen nutzen können.

Benötigt: pip install requests beautifulsoup4
"""

import re
import requests
from bs4 import BeautifulSoup

# ===========================================================================
# TEIL 1 – Gerichtsfinder (Quelle: justizadressen.nrw.de)
# ===========================================================================

BASE_URL = "https://www.justizadressen.nrw.de"
SEARCH_PAGE = f"{BASE_URL}/de/justiz/suche"
RESULT_PAGE = f"{BASE_URL}/de/justiz/gericht"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Gerichtsfinder-Web; nicht-kommerziell)",
    "Accept-Language": "de-DE,de;q=0.9",
}

ANGELEGENHEITEN = {
    "Allgemeiner Gerichtsstand": "gerichte",
    "Angelegenheiten der Staatsanwaltschaften": "sta",
}


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def lade_angelegenheit_codes(session: requests.Session) -> dict:
    r = session.get(SEARCH_PAGE, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    select = soup.find("select", attrs={"name": "ang"})
    if select is None:
        for sel in soup.find_all("select"):
            if any("Gerichtsstand" in (o.get_text() or "")
                   for o in sel.find_all("option")):
                select = sel
                break
    if select is None:
        raise RuntimeError(
            "Konnte das Auswahlfeld 'Angelegenheit' auf der Suchseite nicht "
            "finden – die Webseite hat sich vermutlich geändert.")

    codes = {}
    for opt in select.find_all("option"):
        label = " ".join(opt.get_text().split())
        value = opt.get("value")
        if label and value:
            codes[label] = value
    return codes


def finde_code(codes: dict, label_fragment: str):
    for label, code in codes.items():
        if label_fragment.lower() in label.lower():
            return code
    return None


def parse_ergebnis(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find(id="main") or soup.body or soup

    text = main.get_text("\n")
    zeilen = [" ".join(z.split()) for z in text.split("\n")]
    zeilen = [z for z in zeilen if z]

    behoerden_re = re.compile(
        r"^(Amtsgericht|Landgericht|Oberlandesgericht|Kammergericht|"
        r"Staatsanwaltschaft|Generalstaatsanwaltschaft|"
        r"Arbeitsgericht|Sozialgericht|Verwaltungsgericht|Finanzgericht)\b")
    stopp_re = re.compile(
        r"^(Hilfe|Kontakt|Übersicht|Suche zuständiges|Anschriften der|"
        r"Copyright|Datenschutz|Impressum|Springe direkt)")

    eintraege = []
    aktuell = None
    for zeile in zeilen:
        if behoerden_re.match(zeile):
            if aktuell:
                eintraege.append(aktuell)
            aktuell = {"name": zeile, "details": []}
        elif aktuell is not None:
            if stopp_re.match(zeile):
                eintraege.append(aktuell)
                aktuell = None
            elif len(aktuell["details"]) < 12:
                aktuell["details"].append(zeile)
    if aktuell:
        eintraege.append(aktuell)

    ergebnis = []
    for e in eintraege:
        info = {"name": e["name"], "adresse": [], "telefon": None,
                "fax": None, "email": None, "internet": None}
        for d in e["details"]:
            low = d.lower()
            if low.startswith(("tel", "telefon")):
                info["telefon"] = d.split(":", 1)[-1].strip()
            elif low.startswith("fax"):
                info["fax"] = d.split(":", 1)[-1].strip()
            elif "@" in d:
                info["email"] = d.replace("E-Mail:", "").strip()
            elif low.startswith(("http", "www", "internet")):
                info["internet"] = d.replace("Internet:", "").strip()
            else:
                if len(info["adresse"]) < 4:
                    info["adresse"].append(d)
        ergebnis.append(info)

    gesehen, eindeutig = set(), []
    for e in ergebnis:
        if e["name"] not in gesehen:
            gesehen.add(e["name"])
            eindeutig.append(e)
    return eindeutig


def suche(session: requests.Session, ang_code: str, plz: str, ort: str) -> list:
    params = {"ang": ang_code, "plz": plz, "ort": ort}
    r = session.get(RESULT_PAGE, params=params, timeout=20)
    r.raise_for_status()

    hinweis = None
    if "nicht eindeutig" in r.text or "mehrere Orte" in r.text:
        hinweis = ("Die PLZ ist nicht eindeutig – bitte zusätzlich den "
                   "Ortsnamen angeben.")
    eintraege = parse_ergebnis(r.text)
    if hinweis and not eintraege:
        raise LookupError(hinweis)
    return eintraege


def gerichte_suchen(plz: str, ort: str) -> list:
    """Komplette Gerichtssuche; gibt relevante Behörden (sortiert) zurück."""
    if not re.fullmatch(r"\d{5}", plz):
        raise ValueError("Bitte eine fünfstellige Postleitzahl angeben.")

    session = get_session()
    codes = lade_angelegenheit_codes(session)

    gesamt = {}
    for label_fragment in ANGELEGENHEITEN:
        code = finde_code(codes, label_fragment)
        if code is None:
            continue
        try:
            gesamt[label_fragment] = suche(session, code, plz, ort)
        except LookupError:
            gesamt[label_fragment] = []

    def typ(name: str) -> str:
        for t in ("Amtsgericht", "Landgericht", "Oberlandesgericht",
                  "Kammergericht", "Generalstaatsanwaltschaft",
                  "Staatsanwaltschaft"):
            if name.startswith(t):
                return t
        return "Sonstige"

    flach = [e for liste in gesamt.values() for e in liste]
    relevant = [e for e in flach if typ(e["name"]) in
                ("Amtsgericht", "Landgericht", "Staatsanwaltschaft",
                 "Oberlandesgericht", "Kammergericht",
                 "Generalstaatsanwaltschaft")]

    reihenfolge = ["Amtsgericht", "Landgericht", "Oberlandesgericht",
                   "Kammergericht", "Staatsanwaltschaft",
                   "Generalstaatsanwaltschaft"]
    relevant.sort(key=lambda e: reihenfolge.index(typ(e["name"]))
                  if typ(e["name"]) in reihenfolge else 99)
    return relevant


# ===========================================================================
# TEIL 2 – JVA-Zuordnung nach Vollstreckungsplan M-V
# ===========================================================================

STAND = ("VollstrPl M-V, VV vom 08.12.2025 (AmtsBl. M-V 2025 S. 642), "
         "in Kraft seit 23.12.2025")
QUELLE = ("https://www.regierung-mv.de/static/Regierungsportal/"
          "Justizministerium/Inhalte/Rechtliches/AmtsBl.M-V/"
          "Amtsblatt%20M-V_51_2025.pdf")

LG_BEZIRKE_MV = ("Stralsund", "Rostock", "Schwerin", "Neubrandenburg")

LG_AUSWAHL = [
    "Stralsund",
    "Rostock",
    "Schwerin (AG-Bezirke Schwerin/Ludwigslust)",
    "Schwerin – AG-Bezirk Wismar (Einzugsbereich Rostock / JVA Waldeck)",
    "Neubrandenburg",
]

ANSTALTEN = {
    "JVA Bützow": ["Justizvollzugsanstalt Bützow", "Kühlungsborner Straße 29a",
                   "18246 Bützow", "Tel. (038461) 55-0",
                   "poststelle@jva-buetzow.mv-justiz.de"],
    "JVA Stralsund": ["Justizvollzugsanstalt Stralsund", "Franzenshöhe 12",
                      "18439 Stralsund", "Tel. (03831) 665-0",
                      "poststelle@jva-stralsund.mv-justiz.de"],
    "JVA Waldeck": ["Justizvollzugsanstalt Waldeck", "Zum Fuchsbau 1",
                    "18196 Dummerstorf", "Tel. (038208) 67-0",
                    "poststelle@jva-waldeck.mv-justiz.de"],
    "JVA Neustrelitz": ["Justizvollzugsanstalt Neustrelitz", "Am Kaulksee 3",
                        "17235 Neustrelitz", "Tel. (03981) 2396-0",
                        "poststelle@jva-neustrelitz.mv-justiz.de"],
    "Jugendanstalt Neustrelitz": [
        "Jugendanstalt Neustrelitz (Teilanstalt der JVA Neustrelitz)",
        "Am Kaulksee 3", "17235 Neustrelitz", "Tel. (03981) 2396-0",
        "poststelle@jva-neustrelitz.mv-justiz.de"],
    "Jugendarrestanstalt Neustrelitz": [
        "Jugendarrestanstalt Neustrelitz (Teilanstalt der JVA Neustrelitz)",
        "Am Kaulksee 3", "17235 Neustrelitz", "Tel. (03981) 2396-0",
        "poststelle@jva-neustrelitz.mv-justiz.de"],
}

HAFTARTEN = ["u-haft", "freiheitsstrafe", "ersatzfreiheitsstrafe",
             "jugendstrafe", "jugendarrest", "sicherungsverwahrung",
             "ordnungshaft", "auslieferungshaft"]

JAHRE = 12                      # Monate pro Jahr
TAGE_PRO_MONAT = 30.436875      # mittlere Monatslänge (365,25 / 12)


def dauer_in_monate(jahre: int, monate: int, tage: int):
    """Rechnet Jahre + Monate + Tage in (Bruch-)Monate um.
    Gibt None zurück, wenn keine Dauer angegeben wurde."""
    if not (jahre or monate or tage):
        return None
    return jahre * JAHRE + monate + tage / TAGE_PRO_MONAT


def pruefe_dauer_plausibel(jahre: int, monate: int, tage: int,
                           lebenslang: bool = False) -> list:
    """Gibt eine Liste von Plausibilitätswarnungen zurück (leer = alles ok)."""
    probleme = []
    if monate >= 12:
        probleme.append(
            f"Monate = {monate}: 12 Monate oder mehr bitte als Jahre eintragen "
            "(z. B. 18 Monate → 1 Jahr 6 Monate).")
    if tage >= 31:
        probleme.append(
            f"Tage = {tage}: 31 Tage oder mehr bitte als Monate eintragen "
            "(z. B. 45 Tage → 1 Monat 15 Tage).")
    if lebenslang and (jahre or monate or tage):
        probleme.append(
            "'lebenslang' ist gesetzt und zugleich eine Vollzugsdauer "
            "angegeben – die Dauer wird bei lebenslanger Strafe ignoriert.")
    return probleme


class Fall:
    def __init__(self, haftart, geschlecht, alter, tatzeit_alter=None,
                 dauer_monate=None, lebenslang=False, offen=False,
                 auf_freiem_fuss=False):
        self.haftart = haftart
        self.geschlecht = geschlecht
        self.alter = alter
        self.tatzeit_alter = tatzeit_alter
        self.dauer_monate = dauer_monate
        self.lebenslang = lebenslang
        self.offen = offen
        self.auf_freiem_fuss = auf_freiem_fuss


def bezirksgruppe(lg: str, ag: str) -> str:
    if lg == "Stralsund":
        return "STRALSUND"
    if lg == "Neubrandenburg":
        return "NEUBRANDENBURG"
    if lg == "Rostock":
        return "ROSTOCK+WISMAR"
    if lg == "Schwerin":
        return "ROSTOCK+WISMAR" if "wismar" in ag.lower() else "SCHWERIN+LUDWIGSLUST"
    raise ValueError(f"Kein Landgerichtsbezirk in M-V: {lg!r}")


def uhaft_erwachsene(gruppe: str, geschlecht: str) -> tuple:
    if geschlecht == "w":
        return "JVA Bützow", "Nr. 2.1.1 (weiblich, alle Bezirke)"
    ziel = {"STRALSUND": "JVA Stralsund",
            "ROSTOCK+WISMAR": "JVA Waldeck",
            "SCHWERIN+LUDWIGSLUST": "JVA Bützow",
            "NEUBRANDENBURG": "JVA Neustrelitz"}[gruppe]
    return ziel, "Nr. 2.1.1 (männlich)"


def ist_jugendfall(args) -> bool:
    if args.haftart == "jugendarrest":
        return True
    if args.haftart == "jugendstrafe" and args.alter < 24:
        return True
    if args.haftart == "u-haft":
        tatzeit = args.tatzeit_alter if args.tatzeit_alter is not None else args.alter
        return tatzeit < 21 and args.alter < 24
    if args.haftart in ("ordnungshaft", "auslieferungshaft"):
        return args.alter < 21
    return False


def ermittle_jva(args, lg: str, ag: str) -> tuple:
    hinweise = []
    g = args.geschlecht
    gruppe = bezirksgruppe(lg, ag)
    dauer = args.dauer_monate

    if g == "d":
        if ist_jugendfall(args):
            anstalt = ("Jugendarrestanstalt Neustrelitz"
                       if args.haftart == "jugendarrest"
                       else "Jugendanstalt Neustrelitz")
            return (anstalt, "Nr. 3.4.2 (altersbedingte Zuständigkeit "
                    "Neustrelitz bleibt bestehen)", hinweise)
        hinweise.append("Die konkrete Ausgestaltung der Unterbringung "
                        "entscheidet die Anstaltsleitung im Einzelfall "
                        "(Nr. 3.4.3).")
        return "JVA Bützow", "Nr. 3.4.1 (grundsätzliche Zuständigkeit)", hinweise

    if args.haftart == "u-haft":
        if ist_jugendfall(args):
            return ("Jugendanstalt Neustrelitz",
                    "Nr. 2.1.2 (unter 21 zur Tatzeit, unter 24 bei Inhaftierung)",
                    hinweise)
        hinweise.append("Abweichungen durch richterliche Anordnung bleiben "
                        "unberührt (Nr. 2.2).")
        anstalt, regel = uhaft_erwachsene(gruppe, g)
        return anstalt, regel, hinweise

    if args.haftart == "ordnungshaft":
        if args.alter < 21:
            return ("Jugendanstalt Neustrelitz", "Nr. 2.9.2 (unter 21)", hinweise)
        anstalt, _ = uhaft_erwachsene(gruppe, g)
        return anstalt, "Nr. 2.9.1 i. V. m. Nr. 2.1.1", hinweise

    if args.haftart == "auslieferungshaft":
        if args.alter < 21:
            return ("Jugendanstalt Neustrelitz", "Nr. 2.10.2 (unter 21)", hinweise)
        return "JVA Bützow", "Nr. 2.10.1", hinweise

    if args.haftart == "sicherungsverwahrung":
        hinweise.append("Nach dem Staatsvertrag mit Brandenburg werden "
                        "Verwahrte mit primärer Sexualproblematik i. d. R. in "
                        "der JVA Brandenburg a. d. Havel untergebracht "
                        "(Nr. 2.7.2).")
        return "JVA Bützow", "Nr. 2.7.1", hinweise

    if args.haftart == "jugendarrest":
        return "Jugendarrestanstalt Neustrelitz", "Nr. 2.8", hinweise

    if args.haftart == "jugendstrafe":
        if args.alter < 24:
            if args.offen:
                return ("JVA Neustrelitz (Abt. des offenen Vollzuges)",
                        "Nr. 2.6.1 (Jugendstrafe, offener Vollzug)", hinweise)
            return "Jugendanstalt Neustrelitz", "Nr. 2.5.1", hinweise
        hinweise.append("Ab Vollendung des 24. Lebensjahres vom Jugendstraf"
                        "vollzug ausgenommen (Nr. 2.5.2) – Zuständigkeit wie "
                        "Freiheitsstrafe.")
        args.haftart = "freiheitsstrafe"

    if g == "w":
        if args.haftart == "ersatzfreiheitsstrafe" and args.auf_freiem_fuss:
            hinweise.append("Eine gesonderte Ladungsregel besteht nur für "
                            "männliche Verurteilte (Nr. 2.4.2). Frauen werden "
                            "unmittelbar zur vollzugszuständigen Anstalt geladen.")
        if args.offen:
            return ("JVA Stralsund (Abt. des offenen Vollzuges)",
                    "Nr. 2.6.3 (weiblich, offener Vollzug einschl. EFS, "
                    "alle Bezirke)", hinweise)
        return ("JVA Bützow",
                "Nr. 2.4.3 (weiblich, Freiheits- und Ersatzfreiheitsstrafe, "
                "geschlossener Vollzug, alle Bezirke)", hinweise)

    if args.haftart == "ersatzfreiheitsstrafe" and not args.offen:
        if args.auf_freiem_fuss:
            ziel = {"Rostock": "JVA Waldeck",
                    "Schwerin": "JVA Bützow",
                    "Neubrandenburg": "JVA Neustrelitz",
                    "Stralsund": "JVA Stralsund"}
            if lg == "Schwerin" and gruppe == "ROSTOCK+WISMAR":
                hinweise.append("Achtung: Die Ladung richtet sich nach dem "
                                "LG-Bezirk Schwerin (JVA Bützow), der Vollzug "
                                "nach Nr. 2.4.1 dagegen nach dem Einzugsbereich "
                                "Rostock/Wismar (JVA Waldeck).")
            return (ziel[lg],
                    "Nr. 2.4.2 (Ladung zum Strafantritt, männlich, auf freiem "
                    "Fuß)", hinweise)
        hinweise.append("Ohne Ladung (Verurteilter nicht auf freiem Fuß) "
                        "richtet sich der Vollzug der Ersatzfreiheitsstrafe "
                        "nach Nr. 2.4.1.")
        if dauer is None:
            dauer = 1
            hinweise.append("Vollzugsdauer nicht angegeben – für die Stufen "
                            "der Nr. 2.4.1 wurde die niedrigste Stufe "
                            "angenommen (EFS überschreitet 2 Jahre nicht).")
        ziel_vollzug = {"STRALSUND": "JVA Stralsund",
                        "NEUBRANDENBURG": "JVA Neustrelitz",
                        "ROSTOCK+WISMAR": "JVA Waldeck",
                        "SCHWERIN+LUDWIGSLUST": "JVA Bützow"}
        return ziel_vollzug[gruppe], "Nr. 2.4.1 (Vollzug der EFS)", hinweise

    if args.offen:
        ziel = {"STRALSUND": "JVA Stralsund (Abt. des offenen Vollzuges)",
                "NEUBRANDENBURG": "JVA Neustrelitz (Abt. des offenen Vollzuges)",
                "ROSTOCK+WISMAR": "JVA Waldeck (Abt. des offenen Vollzuges)",
                "SCHWERIN+LUDWIGSLUST": "JVA Waldeck (Abt. des offenen Vollzuges)"}
        if args.haftart == "ersatzfreiheitsstrafe" and lg == "Neubrandenburg":
            return ("JVA Stralsund (Abt. des offenen Vollzuges)",
                    "Nr. 2.6.2 (EFS offener Vollzug, Bezirk Neubrandenburg)",
                    hinweise)
        gruppe_offen = "SCHWERIN+LUDWIGSLUST" if lg == "Schwerin" else gruppe
        return ziel[gruppe_offen], "Nr. 2.6.1 (offener Vollzug)", hinweise

    if dauer is None and not args.lebenslang:
        hinweise.append("Nr. 2.4.1 staffelt nach der Vollzugsdauer – bitte "
                        "Vollzugsdauer (Jahre/Monate/Tage) angeben. Ohne "
                        "Angabe keine sichere Zuordnung.")
        return None, "Nr. 2.4.1", hinweise

    lebenslang = args.lebenslang
    if gruppe == "STRALSUND":
        if not lebenslang and dauer <= 3 * JAHRE:
            return "JVA Stralsund", "Nr. 2.4.1 (bis 3 Jahre)", hinweise
        return "JVA Bützow", "Nr. 2.4.1 (über 3 Jahre / lebenslang)", hinweise
    if gruppe == "NEUBRANDENBURG":
        if not lebenslang and dauer <= 2 * JAHRE:
            return "JVA Neustrelitz", "Nr. 2.4.1 (bis 2 Jahre)", hinweise
        if not lebenslang and dauer <= 3 * JAHRE:
            return "JVA Waldeck", "Nr. 2.4.1 (über 2 bis 3 Jahre)", hinweise
        return "JVA Bützow", "Nr. 2.4.1 (über 3 Jahre / lebenslang)", hinweise
    if gruppe == "ROSTOCK+WISMAR":
        if not lebenslang and dauer <= 5 * JAHRE:
            return "JVA Waldeck", "Nr. 2.4.1 (bis 5 Jahre)", hinweise
        return "JVA Bützow", "Nr. 2.4.1 (über 5 Jahre / lebenslang)", hinweise
    return "JVA Bützow", "Nr. 2.4.1 (Bezirke Schwerin/Ludwigslust: alle Strafen)", hinweise


def lg_ag_aus_ergebnis(relevant: list) -> tuple:
    lg = ag = ""
    for eintrag in relevant:
        name = eintrag.get("name", "")
        if name.startswith("Landgericht") and not lg:
            lg = name.replace("Landgericht", "").strip()
        if name.startswith("Amtsgericht") and not ag:
            ag = name.replace("Amtsgericht", "").strip()
    return lg, ag


def auswahl_zu_lg_ag(auswahl: str) -> tuple:
    """Wandelt eine Dropdown-Auswahl (Schritt 1b) in (Landgericht, Amtsgericht) um."""
    if auswahl.startswith("Stralsund"):
        return "Stralsund", ""
    if auswahl.startswith("Rostock"):
        return "Rostock", ""
    if auswahl.startswith("Neubrandenburg"):
        return "Neubrandenburg", ""
    if "Wismar" in auswahl:
        return "Schwerin", "Wismar"
    return "Schwerin", ""
