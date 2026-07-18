"""
laender/mv.py
=============
Mecklenburg-Vorpommern als Plugin für den Gerichts- und JVA-Finder.

Kapselt die vollständige Logik aus dem ursprünglichen jva_finder_mv.py.
Rechtsstand: Vollstreckungsplan M-V (VollstrPl M-V), VV vom 08.12.2025
(AmtsBl. M-V 2025 S. 642), in Kraft seit 23.12.2025.
"""

from core import Falldaten, Ergebnis, Bundesland, registriere

# ============================================================= Stammdaten =====
STAND = ("VollstrPl M-V, VV vom 08.12.2025 (AmtsBl. M-V 2025 S. 642), "
         "in Kraft seit 23.12.2025")
QUELLE = ("https://www.regierung-mv.de/static/Regierungsportal/"
          "Justizministerium/Inhalte/Rechtliches/AmtsBl.M-V/"
          "Amtsblatt%20M-V_51_2025.pdf")

LG_BEZIRKE_MV = ("Stralsund", "Rostock", "Schwerin", "Neubrandenburg")
# Auswahlliste fürs Frontend (wird als bl.landgerichte angezeigt):
LANDGERICHTE = ["Stralsund", "Rostock", "Schwerin", "Neubrandenburg"]

HAFTARTEN = ["u-haft", "freiheitsstrafe", "ersatzfreiheitsstrafe",
             "jugendstrafe", "jugendarrest", "sicherungsverwahrung",
             "ordnungshaft", "auslieferungshaft"]

JAHRE = 12  # Monate pro Jahr, für Lesbarkeit der Grenzwerte

# Anschriften gemäß Nummer 1.2 VollstrPl M-V
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


# ======================================================== Hilfsfunktionen =====
def bezirksgruppe(lg: str, ag: str) -> str:
    """Der Plan teilt das Land in vier Einzugsbereiche. Besonderheit:
    Der AG-Bezirk Wismar (LG-Bezirk Schwerin) wird dem Bereich des
    LG Rostock zugeschlagen; die übrigen AG-Bezirke des LG Schwerin
    (Schwerin, Ludwigslust) bilden einen eigenen Bereich."""
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
    """Nummer 2.1.1 (gilt über Nr. 2.9.1 auch für Ordnungs-,
    Sicherungs-, Zwangs- und Erzwingungshaft ab 21)."""
    if geschlecht == "w":
        return "JVA Bützow", "Nr. 2.1.1 (weiblich, alle Bezirke)"
    ziel = {"STRALSUND": "JVA Stralsund",
            "ROSTOCK+WISMAR": "JVA Waldeck",
            "SCHWERIN+LUDWIGSLUST": "JVA Bützow",
            "NEUBRANDENBURG": "JVA Neustrelitz"}[gruppe]
    return ziel, "Nr. 2.1.1 (männlich)"


def _tatzeit_alter(f: Falldaten) -> int:
    """0 bedeutet 'nicht angegeben' -> ersatzweise das Inhaftierungsalter."""
    return f.alter_tatzeit if f.alter_tatzeit else f.alter


def ist_jugendfall(f: Falldaten, haftart: str) -> bool:
    """Fälle, in denen altersbedingt die Jugendanstalt/Jugendarrestanstalt
    Neustrelitz zuständig ist (relevant auch für Nr. 3.4.2)."""
    if haftart == "jugendarrest":
        return True
    if haftart == "jugendstrafe" and f.alter < 24:
        return True
    if haftart == "u-haft":
        return _tatzeit_alter(f) < 21 and f.alter < 24
    if haftart in ("ordnungshaft", "auslieferungshaft"):
        return f.alter < 21
    return False


# ============================================================ Kernlogik =======
def ermittle_jva(f: Falldaten, lg: str, ag: str) -> tuple:
    """Gibt (Anstalt, Regel-Nr., Hinweise) zurück – identisch zur
    ursprünglichen Logik, nur auf Basis von Falldaten."""
    hinweise = []
    g = f.geschlecht
    gruppe = bezirksgruppe(lg, ag)
    dauer = f.dauer_monate
    haftart = f.haftart  # lokale Kopie (wird ggf. umgesetzt, s. Jugendstrafe)

    # --- Geschlechtseintrag "divers"/ohne Eintrag/abweichend (Nr. 3.4) ------
    if g == "d":
        if ist_jugendfall(f, haftart):
            anstalt = ("Jugendarrestanstalt Neustrelitz"
                       if haftart == "jugendarrest"
                       else "Jugendanstalt Neustrelitz")
            return (anstalt, "Nr. 3.4.2 (altersbedingte Zuständigkeit "
                    "Neustrelitz bleibt bestehen)", hinweise)
        hinweise.append("Die konkrete Ausgestaltung der Unterbringung "
                        "entscheidet die Anstaltsleitung im Einzelfall "
                        "(Nr. 3.4.3).")
        return "JVA Bützow", "Nr. 3.4.1 (grundsätzliche Zuständigkeit)", hinweise

    # --- Untersuchungshaft --------------------------------------------------
    if haftart == "u-haft":
        if ist_jugendfall(f, haftart):
            return ("Jugendanstalt Neustrelitz",
                    "Nr. 2.1.2 (unter 21 zur Tatzeit, unter 24 bei Inhaftierung)",
                    hinweise)
        hinweise.append("Abweichungen durch richterliche Anordnung bleiben "
                        "unberührt (Nr. 2.2).")
        anstalt, regel = uhaft_erwachsene(gruppe, g)
        return anstalt, regel, hinweise

    # --- Ordnungs-/Sicherungs-/Zwangs-/Erzwingungshaft ----------------------
    if haftart == "ordnungshaft":
        if f.alter < 21:
            return ("Jugendanstalt Neustrelitz", "Nr. 2.9.2 (unter 21)", hinweise)
        anstalt, _ = uhaft_erwachsene(gruppe, g)
        return anstalt, "Nr. 2.9.1 i. V. m. Nr. 2.1.1", hinweise

    # --- Auslieferungs-/Durchlieferungshaft ---------------------------------
    if haftart == "auslieferungshaft":
        if f.alter < 21:
            return ("Jugendanstalt Neustrelitz", "Nr. 2.10.2 (unter 21)", hinweise)
        return "JVA Bützow", "Nr. 2.10.1", hinweise

    # --- Sicherungsverwahrung -----------------------------------------------
    if haftart == "sicherungsverwahrung":
        hinweise.append("Nach dem Staatsvertrag mit Brandenburg werden "
                        "Verwahrte mit primärer Sexualproblematik i. d. R. in "
                        "der JVA Brandenburg a. d. Havel untergebracht "
                        "(Nr. 2.7.2).")
        return "JVA Bützow", "Nr. 2.7.1", hinweise

    # --- Jugendarrest -------------------------------------------------------
    if haftart == "jugendarrest":
        return "Jugendarrestanstalt Neustrelitz", "Nr. 2.8", hinweise

    # --- Jugendstrafe -------------------------------------------------------
    if haftart == "jugendstrafe":
        if f.alter < 24:
            if f.offener_vollzug:
                return ("JVA Neustrelitz (Abt. des offenen Vollzuges)",
                        "Nr. 2.6.1 (Jugendstrafe, offener Vollzug)", hinweise)
            return "Jugendanstalt Neustrelitz", "Nr. 2.5.1", hinweise
        hinweise.append("Ab Vollendung des 24. Lebensjahres vom Jugendstraf"
                        "vollzug ausgenommen (Nr. 2.5.2) – Zuständigkeit wie "
                        "Freiheitsstrafe.")
        haftart = "freiheitsstrafe"  # weiter unten behandeln

    # --- Freiheitsstrafe / Ersatzfreiheitsstrafe ----------------------------
    if g == "w":
        if haftart == "ersatzfreiheitsstrafe" and f.auf_freiem_fuss:
            hinweise.append("Eine gesonderte Ladungsregel besteht nur für "
                            "männliche Verurteilte (Nr. 2.4.2). Frauen werden "
                            "unmittelbar zur vollzugszuständigen Anstalt "
                            "geladen.")
        if f.offener_vollzug:
            return ("JVA Stralsund (Abt. des offenen Vollzuges)",
                    "Nr. 2.6.3 (weiblich, offener Vollzug einschl. EFS, "
                    "alle Bezirke)", hinweise)
        return ("JVA Bützow",
                "Nr. 2.4.3 (weiblich, Freiheits- und Ersatzfreiheitsstrafe, "
                "geschlossener Vollzug, alle Bezirke)", hinweise)

    # männlich
    if haftart == "ersatzfreiheitsstrafe" and not f.offener_vollzug:
        if f.auf_freiem_fuss:
            # Nr. 2.4.2 regelt nur die LADUNG von Verurteilten auf freiem
            # Fuß und knüpft an den LG-Bezirk an (nicht an den AG-Bezirk).
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
        # Bereits inhaftierte Verurteilte werden nicht geladen; der Vollzug
        # der EFS richtet sich nach der allgemeinen Regel Nr. 2.4.1.
        hinweise.append("Ohne Ladung (Verurteilter nicht auf freiem Fuß) "
                        "richtet sich der Vollzug der Ersatzfreiheitsstrafe "
                        "nach Nr. 2.4.1.")
        if dauer is None:
            dauer = 1  # EFS liegt stets deutlich unter den Stufengrenzen
            hinweise.append("Vollzugsdauer nicht angegeben – für die Stufen "
                            "der Nr. 2.4.1 wurde die niedrigste Stufe "
                            "angenommen (EFS überschreitet 2 Jahre nicht).")
        ziel_vollzug = {"STRALSUND": "JVA Stralsund",
                        "NEUBRANDENBURG": "JVA Neustrelitz",
                        "ROSTOCK+WISMAR": "JVA Waldeck",
                        "SCHWERIN+LUDWIGSLUST": "JVA Bützow"}
        return ziel_vollzug[gruppe], "Nr. 2.4.1 (Vollzug der EFS)", hinweise

    if f.offener_vollzug:
        ziel = {"STRALSUND": "JVA Stralsund (Abt. des offenen Vollzuges)",
                "NEUBRANDENBURG": "JVA Neustrelitz (Abt. des offenen Vollzuges)",
                "ROSTOCK+WISMAR": "JVA Waldeck (Abt. des offenen Vollzuges)",
                "SCHWERIN+LUDWIGSLUST": "JVA Waldeck (Abt. des offenen Vollzuges)"}
        if haftart == "ersatzfreiheitsstrafe" and lg == "Neubrandenburg":
            return ("JVA Stralsund (Abt. des offenen Vollzuges)",
                    "Nr. 2.6.2 (EFS offener Vollzug, Bezirk Neubrandenburg)",
                    hinweise)
        # Nr. 2.6.1 knüpft für den offenen Vollzug an den LG-Bezirk an
        gruppe_offen = "SCHWERIN+LUDWIGSLUST" if lg == "Schwerin" else gruppe
        return ziel[gruppe_offen], "Nr. 2.6.1 (offener Vollzug)", hinweise

    # geschlossener Vollzug, männlich, Nr. 2.4.1
    if dauer is None and not f.lebenslang:
        hinweise.append("Nr. 2.4.1 staffelt nach der Vollzugsdauer – bitte "
                        "Vollzugsdauer angeben. Ohne Angabe keine sichere "
                        "Zuordnung.")
        return None, "Nr. 2.4.1", hinweise

    lebenslang = f.lebenslang
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
    return ("JVA Bützow",
            "Nr. 2.4.1 (Bezirke Schwerin/Ludwigslust: alle Strafen)", hinweise)


# ================================================= Plugin-Schnittstelle =======
def _normalisiere_lg(lg: str) -> str:
    """Akzeptiert 'Rostock', 'LG Rostock', 'Landgericht Rostock' -> 'Rostock'."""
    return (lg.replace("Landgericht", "").replace("LG", "").strip())


def ermittle(f: Falldaten) -> Ergebnis:
    """Standard-Schnittstelle für die Registry."""
    lg = _normalisiere_lg(f.landgericht)
    ag = f.amtsgericht or ""

    if lg not in LG_BEZIRKE_MV:
        return Ergebnis(
            anstalt=None,
            regel="außerhalb M-V",
            hinweise=[f"Der Landgerichtsbezirk '{f.landgericht}' liegt nicht in "
                      f"Mecklenburg-Vorpommern. Dieser Vollstreckungsplan gilt "
                      f"nur für die LG-Bezirke {', '.join(LG_BEZIRKE_MV)}."],
            adresse=[],
        )

    anstalt, regel, hinweise = ermittle_jva(f, lg, ag)
    adresse = ANSTALTEN.get(anstalt.split(" (")[0], []) if anstalt else []
    return Ergebnis(anstalt=anstalt, regel=regel,
                    hinweise=hinweise, adresse=adresse)


# =========================================================== Registrierung ====
registriere(Bundesland(
    code="MV",
    name="Mecklenburg-Vorpommern",
    stand=STAND,
    quelle=QUELLE,
    ermittle=ermittle,
    landgerichte=LANDGERICHTE,
    anstalten=ANSTALTEN,
))
