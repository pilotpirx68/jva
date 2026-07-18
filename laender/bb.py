"""
laender/bb.py
=============
Bundesland-Plugin: Brandenburg (BB)

Datenbasis: Vollstreckungsplan für das Land Brandenburg vom 20.09.2024
(JMBl/24 Nr. 10, S. 126), in Kraft seit 01.11.2024.
Quelle: https://mdjd.brandenburg.de/sixcms/media.php/9/
        2024-09-20 Vollstreckungsplan_Stand 1. November 2024 .pdf

Aufbau exakt wie laender/mv.py (Codes statt Klartext-Labels!):
  * geschlecht: "w" / "d" / sonst männlich
  * haftart:    "u-haft", "freiheitsstrafe", "ersatzfreiheitsstrafe",
                "jugendstrafe", "jugendarrest", "sicherungsverwahrung",
                "ordnungshaft", "auslieferungshaft"
  * registriert sich am Ende via registriere(Bundesland(code=..., anstalten=...))

Vor produktivem Einsatz die vereinfachten Punkte (Jungtaeter <27
Feinstaffelung, AG Schwedt/Prenzlau offener Jungtaetervollzug) gegen den
amtlichen Volltext pruefen.
"""

from core import Bundesland, Ergebnis, Falldaten, registriere


NAME = "Brandenburg"
CODE = "BB"
STAND = "2024-11-01 (Vollstreckungsplan v. 20.09.2024, JMBl/24 Nr. 10 S. 126)"
QUELLE = ("https://mdjd.brandenburg.de/sixcms/media.php/9/"
          "2024-09-20%20Vollstreckungsplan_Stand%201.%20November%202024%20.pdf")

LG_BEZIRKE_BB = ("Cottbus", "Frankfurt (Oder)", "Neuruppin", "Potsdam")
LANDGERICHTE = ["Cottbus", "Frankfurt (Oder)", "Neuruppin", "Potsdam"]


# ===================================================================== #
#  Anstaltsstammdaten                                                   #
# ===================================================================== #
BRB = {"name": "JVA Brandenburg an der Havel",
       "adresse": ["Justizvollzugsanstalt Brandenburg an der Havel",
                   "Anton-Saefkow-Allee 22", "14772 Brandenburg an der Havel"]}
COT = {"name": "JVA Cottbus-Dissenchen",
       "adresse": ["Justizvollzugsanstalt Cottbus-Dissenchen",
                   "Oststraße 2", "03052 Cottbus"]}
LUD = {"name": "JVA Luckau-Duben",
       "adresse": ["Justizvollzugsanstalt Luckau-Duben",
                   "Lehmkietenweg 1", "15926 Luckau OT Duben"]}
SPR = {"name": "JVA Luckau-Duben, Außenstelle Spremberg",
       "adresse": ["JVA Luckau-Duben – Außenstelle Spremberg",
                   "Neudorfer Weg 1", "03130 Spremberg"]}
WUL = {"name": "JVA Nord-Brandenburg, TA Neuruppin-Wulkow",
       "adresse": ["JVA Nord-Brandenburg – Teilanstalt Neuruppin-Wulkow",
                   "Ausbau 8", "16835 Neuruppin"]}
WRI = {"name": "JVA Nord-Brandenburg, TA Wriezen",
       "adresse": ["JVA Nord-Brandenburg – Teilanstalt Wriezen",
                   "Schulzendorfer Straße 1", "16269 Wriezen"]}
JAA = {"name": "Jugendarrestanstalt Berlin-Brandenburg",
       "adresse": ["Jugendarrestanstalt Berlin-Brandenburg",
                   "Lützowstraße 45", "12307 Berlin"]}

# Bundesland.anstalten erwartet: Name -> Adresszeilen (wie in mv.py)
ANSTALTEN = {a["name"]: a["adresse"]
             for a in (BRB, COT, LUD, SPR, WUL, WRI, JAA)}


# ===================================================================== #
#  Zentrale Sonderzuständigkeiten                                       #
# ===================================================================== #
JVA_FRAUEN = LUD           # Frauenvollzug (geschlossen) zentral
JVA_FRAUEN_EFS = SPR       # EFS-Frauen: unmittelbare Ladung Spremberg
JVA_JUGEND_M = WRI         # männlicher Jugendstrafvollzug zentral
JVA_JUGENDARREST = JAA     # Jugendarrest zentral (Berlin-Brandenburg)
JVA_LEBENSLANG = LUD       # lebenslange Freiheitsstrafe zentral
JVA_SV = BRB               # Sicherungsverwahrung (SVE Brandenburg a. d. Havel)
JVA_SEXUAL = BRB           # Sexualstraftäter zentral (Ladung)


# ===================================================================== #
#  Amtsgerichts-Tabelle: Männer ab 27 Jahre                            #
#  Werte je AG: (uhaft, strafe_bis2, strafe_2bis3, strafe_ueber3,      #
#                freier_fuss/offener_vollzug)                          #
# ===================================================================== #
AG_ERWACHSEN = {
    # --- LG Cottbus ---
    "Bad Liebenwerda":     (COT, COT, COT, LUD, SPR),
    "Cottbus":             (COT, COT, COT, LUD, COT),
    "Lübben":              (COT, COT, COT, LUD, COT),
    "Senftenberg":         (COT, COT, COT, LUD, SPR),
    "Königs Wusterhausen": (COT, COT, COT, LUD, COT),
    # --- LG Frankfurt (Oder) ---
    "Frankfurt (Oder)":    (COT, COT, COT, LUD, SPR),
    "Fürstenwalde":        (COT, COT, COT, LUD, SPR),
    "Bad Freienwalde":     (WUL, COT, COT, LUD, SPR),
    "Bernau":              (WUL, WUL, LUD, LUD, SPR),
    "Eberswalde":          (WUL, COT, COT, LUD, SPR),
    "Eisenhüttenstadt":    (COT, COT, COT, LUD, SPR),
    "Strausberg":          (WUL, WUL, LUD, LUD, SPR),
    # --- LG Neuruppin ---
    "Neuruppin":           (WUL, WUL, WUL, LUD, WUL),
    "Oranienburg":         (WUL, WUL, WUL, LUD, BRB),
    "Perleberg":           (WUL, WUL, WUL, LUD, WUL),
    "Prenzlau":            (WUL, COT, COT, LUD, COT),
    "Zehdenick":           (WUL, WUL, WUL, LUD, WUL),
    "Schwedt":             (WUL, COT, COT, LUD, COT),
    # --- LG Potsdam ---
    "Brandenburg":         (BRB, BRB, BRB, LUD, BRB),
    "Luckenwalde":         (BRB, BRB, LUD, LUD, BRB),
    "Nauen":               (WUL, BRB, BRB, LUD, BRB),
    "Potsdam":             (WUL, BRB, LUD, LUD, BRB),
    "Rathenow":            (WUL, BRB, BRB, LUD, BRB),
    "Zossen":              (COT, COT, COT, LUD, COT),
}

LG_FALLBACK = {
    "Cottbus":          (COT, COT, COT, LUD, COT),
    "Frankfurt (Oder)": (COT, COT, COT, LUD, SPR),
    "Neuruppin":        (WUL, WUL, WUL, LUD, WUL),
    "Potsdam":          (BRB, BRB, BRB, LUD, BRB),
}

GRENZE_JUNGTAETER = 27
GRENZE_UHAFT_JUNG = 25


# ===================================================================== #
#  Hilfsfunktionen (analog mv.py)                                       #
# ===================================================================== #
def _normalisiere_lg(lg: str) -> str:
    """Akzeptiert 'Cottbus', 'LG Cottbus', 'Landgericht Cottbus' -> 'Cottbus'."""
    return (lg or "").replace("Landgericht", "").replace("LG", "").strip()


def _zuordnung_holen(ag: str, lg: str, hinweise: list) -> tuple:
    """Liefert (zuordnung_tuple, quelle_ebene). Erst AG-scharf, sonst
    grobe Näherung anhand des Landgerichts."""
    zuordnung = AG_ERWACHSEN.get(ag)
    if zuordnung is not None:
        return zuordnung, f"Amtsgericht {ag}"
    zuordnung = LG_FALLBACK.get(lg)
    if zuordnung is not None:
        hinweise.append("Kein passender Amtsgerichtsbezirk gefunden – grobe "
                        "Näherung anhand des Landgerichts. Für ein präzises "
                        "Ergebnis bitte den Amtsgerichtsbezirk angeben.")
        return zuordnung, f"Landgericht {lg} (Näherung, AG unbekannt)"
    return None, ""


def _erg(jva: dict, regel: str, hinweise: list) -> Ergebnis:
    return Ergebnis(anstalt=jva["name"], regel=regel,
                    hinweise=hinweise, adresse=jva["adresse"])


# ===================================================================== #
#  Offener Vollzug – eigene Zuständigkeiten (Teil A Ziff. 3 / Teil B)   #
# ===================================================================== #
def _offener_vollzug(fall: Falldaten, lg: str, ag: str,
                     hinweise: list) -> Ergebnis:
    # Frauen (auch weibliche Jugendstrafgefangene): zentral Spremberg
    if fall.geschlecht == "w":
        hinweise.append("Offener Vollzug für weibliche Gefangene wird zentral "
                        "in der JVA Luckau-Duben, Außenstelle Spremberg "
                        "vollzogen.")
        return _erg(SPR, "Offener Vollzug Frauen (zentral Spremberg)", hinweise)

    if fall.geschlecht == "d":
        hinweise.append("Diverser/unbestimmter Geschlechtseintrag: Zuordnung im "
                        "offenen Vollzug nach Einzelfall; hier wie männlich "
                        "behandelt.")

    # Männlicher Jugendstrafvollzug: offene Abteilung Wriezen
    if fall.haftart == "jugendstrafe":
        hinweise.append("Offener männlicher Jugendstrafvollzug: offene Abteilung "
                        "der JVA Nord-Brandenburg, TA Wriezen.")
        return _erg(WRI, "Offener Vollzug Jugendstrafe (m, Wriezen)", hinweise)

    # Männer bis 27 Jahre: offener Vollzug in Wriezen
    if 0 < fall.alter < GRENZE_JUNGTAETER:
        if ag in ("Schwedt", "Prenzlau"):
            hinweise.append("AG Schwedt/Prenzlau sind im offenen Jungtätervollzug "
                            "(<27) gesondert geregelt – bitte Plan (Teil B II) "
                            "prüfen; hier Näherung JVA Cottbus-Dissenchen.")
            return _erg(COT, "Offener Vollzug Jungtäter (<27, Sonderfall AG)",
                        hinweise)
        hinweise.append("Offener Vollzug für männliche Verurteilte bis 27 Jahre "
                        "wird in der JVA Nord-Brandenburg, TA Wriezen vollzogen.")
        return _erg(WRI, "Offener Vollzug Jungtäter (<27, Wriezen)", hinweise)

    # Männer ab 27: nach Amtsgericht (Spalte offener Vollzug)
    zuordnung, quelle_ebene = _zuordnung_holen(ag, lg, hinweise)
    if zuordnung is None:
        return Ergebnis(anstalt=None, regel="Keine Zuordnung (BB, offen)",
                        hinweise=hinweise, adresse=[])
    return _erg(zuordnung[4], f"Offener Vollzug Männer ab 27, {quelle_ebene}",
                hinweise)


# ===================================================================== #
#  Kernlogik                                                            #
# ===================================================================== #
def ermittle(fall: Falldaten) -> Ergebnis:
    hinweise: list = []
    lg = _normalisiere_lg(fall.landgericht)
    ag = (fall.amtsgericht or "").strip()

    # 0) Gültiger Gerichtsbezirk?
    if lg not in LG_BEZIRKE_BB and ag not in AG_ERWACHSEN:
        return Ergebnis(
            anstalt=None, regel="außerhalb BB",
            hinweise=[f"Weder Landgericht '{lg or '—'}' noch Amtsgericht "
                      f"'{ag or '—'}' sind brandenburgische Bezirke. Erwartete "
                      f"LG: {', '.join(LG_BEZIRKE_BB)}."],
            adresse=[])

    monate = fall.dauer_monate

    # 1) Sicherungsverwahrung
    if fall.haftart == "sicherungsverwahrung":
        hinweise.append("Sicherungsverwahrung: SVE Brandenburg a. d. Havel "
                        "(Vollzugsverbund mit Bützow/MV).")
        return _erg(JVA_SV, "Zentralzuständigkeit Sicherungsverwahrung", hinweise)

    # 2) Jugendarrest
    if fall.haftart == "jugendarrest":
        hinweise.append("Jugendarrest wird zentral in der Jugendarrestanstalt "
                        "Berlin-Brandenburg vollzogen.")
        return _erg(JVA_JUGENDARREST, "Zentralzuständigkeit Jugendarrest",
                    hinweise)

    # 3) Offener Vollzug: eigene Anstaltszuordnung
    if fall.offener_vollzug:
        return _offener_vollzug(fall, lg, ag, hinweise)

    # 4) Frauen (geschlossen) – inkl. EFS-Ausnahme (Spremberg)
    if fall.geschlecht == "w":
        if fall.haftart == "ersatzfreiheitsstrafe":
            hinweise.append("Ersatzfreiheitsstrafe bei weiblichen Verurteilten: "
                            "unmittelbare Ladung in die JVA Luckau-Duben, "
                            "Außenstelle Spremberg.")
            return _erg(JVA_FRAUEN_EFS, "EFS Frauen (zentral Spremberg)", hinweise)
        hinweise.append("Frauenvollzug (auch U-Haft und Jugendstrafe) wird "
                        "zentral in der JVA Luckau-Duben vollzogen.")
        return _erg(JVA_FRAUEN, "Zentralzuständigkeit Frauenvollzug", hinweise)

    if fall.geschlecht == "d":
        hinweise.append("Diverser/unbestimmter Geschlechtseintrag: Unterbringung "
                        "nach Einzelfallentscheidung; hier Zuordnung wie Männer.")

    # 5) Männliche Jugendstrafe
    if fall.haftart == "jugendstrafe":
        hinweise.append("Männlicher Jugendstrafvollzug wird zentral in der "
                        "TA Wriezen vollzogen.")
        return _erg(JVA_JUGEND_M, "Zentralzuständigkeit Jugendstrafvollzug (m)",
                    hinweise)

    # 6) Lebenslange Freiheitsstrafe
    if fall.lebenslang:
        hinweise.append("Lebenslange Freiheitsstrafe wird zentral in der "
                        "JVA Luckau-Duben vollzogen.")
        return _erg(JVA_LEBENSLANG, "Zentralzuständigkeit lebenslange FS", hinweise)

    # 7) Sexualstraftäter: zentrale Ladung nach Brandenburg a. d. Havel
    if fall.sexualdelikt and fall.haftart in (
            "freiheitsstrafe", "ersatzfreiheitsstrafe", "u-haft"):
        hinweise.append("Sexualstraftäter werden laut Vollstreckungsplan zentral "
                    "in die JVA Brandenburg an der Havel geladen "
                    "(überschreibt die Regelzuordnung nach Amtsgericht).")
        return _erg(JVA_SEXUAL, "Zentralzuständigkeit Sexualstraftäter (Ladung)",
                hinweise)

    # 8) Jungtäter (Männer bis 27)
    if 0 < fall.alter < GRENZE_JUNGTAETER:
        if fall.haftart == "u-haft":
            jva = WRI if fall.alter < GRENZE_UHAFT_JUNG else COT
            hinweise.append("Jungtäter-U-Haft: bis 24 Jahre TA Wriezen, "
                            "ab 25 Jahre Cottbus-Dissenchen.")
            return _erg(jva, "Jungtätervollzug U-Haft (m, <27)", hinweise)
        hinweise.append("Jungtäter (<27): Freiheitsstrafvollzug i. d. R. in der "
                        "TA Wriezen; Feinstaffelung nach Strafdauer im Plan "
                        "beachten.")
        return _erg(WRI, "Jungtätervollzug Freiheitsstrafe (m, <27)", hinweise)

    # 9) Regelvollzug erwachsene Männer (>=27) nach Amtsgericht
    zuordnung, quelle_ebene = _zuordnung_holen(ag, lg, hinweise)
    if zuordnung is None:
        return Ergebnis(anstalt=None, regel="Keine Zuordnung möglich (BB)",
                        hinweise=hinweise, adresse=[])

    uhaft, s_bis2, s_2bis3, s_ueber3, freier_fuss = zuordnung

    # Reine Ersatzfreiheitsstrafe -> offener Vollzug (auf freiem Fuß)
    if fall.haftart == "ersatzfreiheitsstrafe":
        hinweise.append("Reine Ersatzfreiheitsstrafe: laut Plan ausschließlich "
                        "in den offenen Vollzug zu laden/einzuweisen.")
        return _erg(freier_fuss, f"Ersatzfreiheitsstrafe, {quelle_ebene}", hinweise)

    # U-Haft, Ordnungs-/Auslieferungshaft folgen der U-Haft-Spalte
    if fall.haftart in ("u-haft", "ordnungshaft", "auslieferungshaft"):
        if fall.haftart != "u-haft":
            hinweise.append(f"'{fall.haftart}' im BB-Plan gesondert geregelt; "
                            "hier vereinfacht der U-Haft-Anstalt zugeordnet – "
                            "bitte Plan prüfen.")
        return _erg(uhaft, f"{fall.haftart}, {quelle_ebene}", hinweise)

    # Auf freiem Fuß + bis 3 Jahre -> Ladung in freier-Fuß-Anstalt
    if fall.auf_freiem_fuss and monate is not None and monate <= 36:
        return _erg(freier_fuss,
                    f"Strafhaft (auf freiem Fuß, ≤3 J.), {quelle_ebene}", hinweise)

    # Strafhaft übrige Verurteilte -> Staffelung nach Dauer
    if monate is None:
        hinweise.append("Keine Strafdauer angegeben – Zuordnung nach Stufe "
                        "'bis 2 Jahre' als Annahme.")
        return _erg(s_bis2, f"Strafhaft (Dauer unbekannt), {quelle_ebene}",
                    hinweise)
    if monate <= 24:
        return _erg(s_bis2, f"Strafhaft bis 2 Jahre, {quelle_ebene}", hinweise)
    if monate <= 36:
        return _erg(s_2bis3, f"Strafhaft 2–3 Jahre, {quelle_ebene}", hinweise)
    hinweise.append("Strafen über 3 Jahre werden zentral in Luckau-Duben "
                    "vollzogen.")
    return _erg(s_ueber3, f"Strafhaft über 3 Jahre, {quelle_ebene}", hinweise)


# ===================================================================== #
#  Registrierung (Signatur exakt wie mv.py)                            #
# ===================================================================== #
registriere(Bundesland(
    code=CODE,
    name=NAME,
    stand=STAND,
    quelle=QUELLE,
    ermittle=ermittle,
    landgerichte=LANDGERICHTE,
    anstalten=ANSTALTEN,
))
