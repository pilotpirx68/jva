"""
app.py
======
Streamlit-Frontend für den Gerichts- und JVA-Finder.

Bundeslandunabhängig: Die eigentliche Zuständigkeitslogik liegt in den
Plugins unter laender/ (z. B. laender/mv.py) und wird über die Registry
in core.py angesprochen.

Neu in dieser Fassung:
  * korrigierte Gerichtssuche (richtiger Endpoint + ang-Code + Regex-Parsing)
  * zusätzliche Staatsanwaltschafts-Abfrage
  * optionales Debug-Panel mit Roh-Trefferliste

Start:  streamlit run app.py
"""

import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import streamlit as st

import laender                      # registriert alle Bundesland-Plugins
from core import alle_laender, Falldaten


# ===================================================================== #
#  Label -> Code-Mappings (Frontend -> Plugin)                          #
# ===================================================================== #
HAFTART_LABELS = {
    "Untersuchungshaft": "u-haft",
    "Freiheitsstrafe": "freiheitsstrafe",
    "Ersatzfreiheitsstrafe": "ersatzfreiheitsstrafe",
    "Jugendstrafe": "jugendstrafe",
    "Jugendarrest": "jugendarrest",
    "Sicherungsverwahrung": "sicherungsverwahrung",
    "Ordnungshaft": "ordnungshaft",
    "Auslieferungs-/Durchlieferungshaft": "auslieferungshaft",
}

GESCHLECHT_LABELS = {
    "männlich": "m",
    "weiblich": "w",
    "divers / ohne Angabe / abweichend": "d",
}


# ===================================================================== #
#  Gerichtssuche über justizadressen.nrw.de                            #
# ===================================================================== #
BASE_URL = "https://www.justizadressen.nrw.de"
SEARCH_PAGE = f"{BASE_URL}/de/justiz/suche"
RESULT_PAGE = f"{BASE_URL}/de/justiz/gericht"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (JVA-Finder; nicht-kommerziell)",
    "Accept-Language": "de-DE,de;q=0.9",
}


def _lade_ang_code(session: requests.Session) -> str | None:
    """Liest den Code der Angelegenheit 'Allgemeiner Gerichtsstand' aus dem
    <select name='ang'> der Suchseite (liefert AG/LG/OLG)."""
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
        return None

    for opt in select.find_all("option"):
        label = " ".join(opt.get_text().split())
        value = opt.get("value")
        if value and "gerichtsstand" in label.lower():
            return value
    return None


def _parse_ergebnis(html: str) -> list[dict]:
    """Extrahiert Behördenblöcke (Name + Adresszeilen) aus der Ergebnisseite."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find(id="main") or soup.body or soup
    zeilen = [" ".join(z.split()) for z in main.get_text("\n").split("\n")]
    zeilen = [z for z in zeilen if z]

    behoerden_re = re.compile(
        r"^(Amtsgericht|Landgericht|Oberlandesgericht|Kammergericht|"
        r"Staatsanwaltschaft|Generalstaatsanwaltschaft)\b")
    stopp_re = re.compile(
        r"^(Hilfe|Kontakt|Übersicht|Suche zuständiges|Anschriften der|"
        r"Copyright|Datenschutz|Impressum|Springe direkt)")

    eintraege, aktuell = [], None
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

    gesehen, eindeutig = set(), []
    for e in eintraege:
        if e["name"] not in gesehen:
            gesehen.add(e["name"])
            eindeutig.append(e)
    return eindeutig


@st.cache_data(show_spinner=False)
def suche_gericht(plz_oder_ort: str) -> dict:
    """Ermittelt zuständiges Amts-, Land- und Oberlandesgericht sowie die
    Staatsanwaltschaft über justizadressen.nrw.de.
    Nimmt 'PLZ', 'PLZ Ort' oder nur 'Ort' entgegen.
    Rückgabe: {'ag','lg','olg','sta','quelle','roh'} oder {'fehler': ...}."""
    eingabe = plz_oder_ort.strip()
    m = re.search(r"\b(\d{5})\b", eingabe)
    plz = m.group(1) if m else ""
    ort = eingabe.replace(plz, "").strip() if plz else eingabe
    if not plz and not ort:
        return {"fehler": "Bitte PLZ oder Ort eingeben."}

    session = requests.Session()
    session.headers.update(_HEADERS)

    try:
        ang_code = _lade_ang_code(session)
        if ang_code is None:
            return {"fehler": "Suchseite hat sich geändert – 'Angelegenheit' "
                              "nicht gefunden. Bitte manuellen Override nutzen."}
        params = {"ang": ang_code, "plz": plz, "ort": ort}
        r = session.get(RESULT_PAGE, params=params, timeout=20)
        r.raise_for_status()
    except requests.RequestException as exc:
        return {"fehler": f"Abfrage nicht möglich ({exc}). "
                          "Bitte manuellen Override nutzen."}

    if "nicht eindeutig" in r.text or "mehrere Orte" in r.text:
        return {"fehler": "PLZ nicht eindeutig – bitte zusätzlich den "
                          "Ortsnamen angeben (z. B. '18055 Rostock')."}

    eintraege = _parse_ergebnis(r.text)

    def _finde(prefix: str) -> str:
        return next((e["name"].replace(prefix, "").strip()
                     for e in eintraege if e["name"].startswith(prefix)), "")

    ag = _finde("Amtsgericht")
    lg = _finde("Landgericht")
    olg = _finde("Oberlandesgericht") or _finde("Kammergericht")
    sta = _finde("Staatsanwaltschaft")

    if not ag and not lg and not sta:
        return {"fehler": "Kein Gericht gefunden. Bitte PLZ prüfen, Ortsnamen "
                          "ergänzen oder manuellen Override nutzen."}

    quelle = f"justizadressen.nrw.de ({plz or ort})"
    return {"ag": ag, "lg": lg, "olg": olg, "sta": sta,
            "quelle": quelle, "roh": eintraege}


# ===================================================================== #
#  Seiten-Grundgerüst                                                   #
# ===================================================================== #
st.set_page_config(page_title="Gerichts- und JVA-Finder", page_icon="⚖️")
st.title("⚖️ Gerichts- und JVA-Finder")

# Bundesland-Auswahl aus der Registry
laender_liste = alle_laender()
if not laender_liste:
    st.error("Es sind keine Bundesland-Plugins registriert. "
             "Bitte laender/__init__.py prüfen.")
    st.stop()

bl = st.selectbox("Bundesland", laender_liste, format_func=lambda b: b.name)
st.caption(f"Vollstreckungsplan {bl.name} · Stand: {bl.stand}")

# Debug-Modus (Seitenleiste)
debug = st.sidebar.checkbox("🐞 Debug-Panel anzeigen")


# ===================================================================== #
#  Datenschutzhinweis                                                   #
# ===================================================================== #
with st.expander("🔒 Datenschutzhinweis (bitte lesen)"):
    st.markdown(
        """
**Verarbeitung Ihrer Eingaben**

- Diese Anwendung verarbeitet die von Ihnen eingegebenen Daten
  (PLZ/Ort sowie die Haftangaben) **ausschließlich flüchtig im
  Arbeitsspeicher**, um das Ergebnis zu berechnen. Es findet **keine
  dauerhafte Speicherung** und **kein Logging** dieser Eingaben statt.
- Für die Gerichtssuche wird die eingegebene **PLZ/der Ort** an den
  externen Dienst *justizadressen.nrw.de* übertragen. Für diese
  Abfrage gelten die dortigen Datenschutzbestimmungen.
- Haftbezogene Angaben (Alter, Haftart usw.) können **besonders
  sensible personenbezogene Daten** darstellen. Geben Sie daher nur
  die für die Berechnung nötigen Angaben ein und **verzichten Sie auf
  Namen oder andere direkt identifizierende Daten**.
- Das Ergebnis dient der **Orientierung** und ersetzt keine
  verbindliche behördliche oder rechtliche Prüfung.

Mit der Nutzung bestätigen Sie, diese Hinweise zur Kenntnis genommen
zu haben.
        """
    )

datenschutz_ok = st.checkbox(
    "Ich habe den Datenschutzhinweis gelesen und stimme der beschriebenen "
    "Verarbeitung zu.")


# ===================================================================== #
#  Schritt 1 – Gericht ermitteln (Suche + manueller Override)          #
# ===================================================================== #
st.header("1 · Zuständiges Gericht")

tab_suche, tab_manuell = st.tabs(["🔎 Automatische Suche", "✍️ Manueller Override"])

with tab_suche:
    plz_ort = st.text_input("PLZ oder Ort", placeholder="z. B. 18055 oder Rostock")
    if st.button("Gericht suchen"):
        if not plz_ort.strip():
            st.warning("Bitte PLZ oder Ort eingeben.")
        else:
            with st.spinner("Suche läuft …"):
                res = suche_gericht(plz_ort.strip())
            if "fehler" in res:
                st.error(res["fehler"])
                # Rohdaten für Debug auch im Fehlerfall verwerfen
                st.session_state.pop("gericht_roh", None)
            else:
                st.session_state["lg"] = res["lg"]
                st.session_state["ag"] = res["ag"]
                st.session_state["olg"] = res.get("olg", "")
                st.session_state["sta"] = res.get("sta", "")
                st.session_state["quelle"] = res["quelle"]
                st.session_state["gericht_roh"] = res.get("roh", [])
                st.success(f"Gefunden: LG {res['lg'] or '—'}, "
                           f"AG {res['ag'] or '—'}")
                if res.get("sta"):
                    st.caption(f"Staatsanwaltschaft: {res['sta']}")
                if res.get("olg"):
                    st.caption(f"Oberlandesgericht: {res['olg']}")

with tab_manuell:
    st.caption("Nutzbar offline oder wenn das Gericht bereits bekannt ist.")
    lg_manuell = st.selectbox(
        "Landgerichtsbezirk", [""] + list(bl.landgerichte),
        format_func=lambda x: x or "— bitte wählen —")
    ag_manuell = st.text_input("Amtsgerichtsbezirk (optional)",
                               placeholder="z. B. Wismar")
    sta_manuell = st.text_input("Staatsanwaltschaft (optional)",
                                placeholder="z. B. Rostock")
    if st.button("Override übernehmen"):
        st.session_state["lg"] = lg_manuell
        st.session_state["ag"] = ag_manuell
        st.session_state["sta"] = sta_manuell
        st.session_state["olg"] = ""
        st.session_state["quelle"] = "manueller Override"
        st.session_state.pop("gericht_roh", None)
        st.success(f"Übernommen: LG {lg_manuell or '—'}, "
                   f"AG {ag_manuell or '—'}")

# Aktuellen Gerichtsstand anzeigen
lg = st.session_state.get("lg", "")
ag = st.session_state.get("ag", "")
sta = st.session_state.get("sta", "")
olg = st.session_state.get("olg", "")
if lg or ag or sta:
    zeile = f"Aktuell gesetzt: **LG {lg or '—'}**, **AG {ag or '—'}**"
    if sta:
        zeile += f", **StA {sta}**"
    zeile += f" · Quelle: {st.session_state.get('quelle', '—')}"
    st.info(zeile)

# ---- Debug-Panel: Roh-Trefferliste ----
if debug:
    with st.expander("🐞 Debug – Roh-Trefferliste der Gerichtssuche", expanded=True):
        roh = st.session_state.get("gericht_roh")
        if not roh:
            st.write("Noch keine Trefferdaten vorhanden (oder letzter Aufruf "
                     "war ein manueller Override / Fehler).")
        else:
            st.write(f"**{len(roh)} Behördenblock/-blöcke gefunden:**")
            for i, e in enumerate(roh, 1):
                st.markdown(f"**{i}. {e['name']}**")
                if e["details"]:
                    st.code("\n".join(e["details"]))
                else:
                    st.caption("— keine Detailzeilen —")
            st.markdown("**Extrahierte Felder**")
            st.json({"ag": ag, "lg": lg, "olg": olg, "sta": sta})


# ===================================================================== #
#  Schritt 2 – Haftangaben                                              #
# ===================================================================== #
st.header("2 · Haftangaben")

haftart_label = st.selectbox(
    "Haftart", list(HAFTART_LABELS.keys()), index=1)
haftart_code = HAFTART_LABELS[haftart_label]

geschlecht_label = st.selectbox(
    "Geschlechtseintrag", list(GESCHLECHT_LABELS.keys()), index=0)
geschlecht_code = GESCHLECHT_LABELS[geschlecht_label]

col1, col2 = st.columns(2)
alter = col1.number_input("Alter bei Inhaftierung", min_value=14,
                          max_value=120, value=30, step=1)
tatzeit = col2.number_input("Alter zur Tatzeit (0 = keine Angabe)",
                            min_value=0, max_value=120, value=0, step=1)

st.markdown("**Vollzugsdauer**")
d1, d2, d3 = st.columns(3)
jahre = d1.number_input("Jahre", min_value=0, max_value=99, value=0, step=1)
monate = d2.number_input("Monate", min_value=0, max_value=11, value=0, step=1)
tage = d3.number_input("Tage", min_value=0, max_value=30, value=0, step=1)

lebenslang = st.checkbox("Lebenslange Freiheitsstrafe")
offen = st.checkbox("Offener Vollzug")
freier_fuss = st.checkbox("Verurteilte(r) auf freiem Fuß (für EFS-Ladung)")
sexualdelikt = st.checkbox("Sexualdelikt (zentrale Ladung, z. B. BB → Brandenburg a. d. Havel)")
# ---- Vollzugsdauer in Monate umrechnen ----
if lebenslang or (jahre == 0 and monate == 0 and tage == 0):
    dauer_monate = None
else:
    dauer_monate = jahre * 12 + monate + tage / 30.436875

# ---- Plausibilitätsprüfung ----
if not lebenslang and dauer_monate is not None and dauer_monate <= 0:
    st.warning("Bitte eine Vollzugsdauer größer als 0 angeben "
               "oder 'lebenslang' wählen.")


# ===================================================================== #
#  Schritt 3 – Ermitteln (rechnen + in session_state speichern)        #
# ===================================================================== #
st.header("3 · Ergebnis")

if st.button("Zuständige JVA ermitteln", type="primary",
             disabled=not datenschutz_ok):
    if not datenschutz_ok:
        st.warning("Bitte zuerst den Datenschutzhinweis bestätigen.")
        st.stop()
    if not lg:
        st.warning("Bitte zuerst ein Landgericht ermitteln oder per Override "
                   "setzen (Schritt 1).")
        st.stop()

    fall = Falldaten(
        landgericht=lg,
        amtsgericht=ag,
        haftart=haftart_code,
        geschlecht=geschlecht_code,
        alter=int(alter),
        alter_tatzeit=int(tatzeit),
        dauer_monate=dauer_monate,
        lebenslang=bool(lebenslang),
        offener_vollzug=bool(offen),
        auf_freiem_fuss=bool(freier_fuss),
        sexualdelikt=bool(sexualdelikt),
    )
    erg = bl.ermittle(fall)

    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dauer_text = ("lebenslang" if lebenslang else
                  f"{int(jahre)} J. {int(monate)} M. {int(tage)} T."
                  if dauer_monate is not None else "keine Angabe")

    st.session_state["jva_ergebnis"] = {
        "zeitstempel": zeitstempel,
        "bundesland": bl.name,
        "stand": bl.stand,
        "quelle_regelwerk": bl.quelle,
        "lg": lg,
        "ag": ag,
        "sta": sta,
        "olg": olg,
        "quelle": st.session_state.get("quelle", ""),
        "haftart": haftart_label,
        "geschlecht": geschlecht_label,
        "alter": int(alter),
        "tatzeit": int(tatzeit),
        "jahre": int(jahre),
        "monate": int(monate),
        "tage": int(tage),
        "dauer_monate": round(dauer_monate, 2) if dauer_monate is not None else None,
        "dauer_text": dauer_text,
        "lebenslang": bool(lebenslang),
        "offen": bool(offen),
        "freier_fuss": bool(freier_fuss),
        "sexualdelikt": bool(sexualdelikt),
        "anstalt": erg.anstalt,
        "anstalt_adresse": erg.adresse,
        "regel": erg.regel,
        "hinweise": erg.hinweise,
    }


# ===================================================================== #
#  Anzeige des gespeicherten Ergebnisses (über Reruns hinweg)          #
# ===================================================================== #
if "jva_ergebnis" in st.session_state:
    e = st.session_state["jva_ergebnis"]

    st.divider()
    st.subheader("Ergebnis – Zuständige JVA")
    st.caption(f"Bundesland: {e['bundesland']}")

    if e["dauer_monate"] is not None:
        st.caption(f"Vollzugsdauer: {e['dauer_text']} "
                   f"(≈ {e['dauer_monate']:.2f} Monate)")
    elif e["lebenslang"]:
        st.caption("Vollzugsdauer: lebenslang")

    if e["anstalt"] is None:
        st.warning(f"Keine eindeutige Zuordnung möglich ({e['regel']}).")
    else:
        st.success(f"**Zuständig: {e['anstalt']}**")
        st.caption(f"Regel: {e['regel']}")
        if e["anstalt_adresse"]:
            st.text("\n".join(e["anstalt_adresse"]))

    for h in e["hinweise"]:
        st.info(h)
    st.caption(f"Stand des Regelwerks: {e['stand']}")
    st.caption(f"Amtliche Quelle: {e['quelle_regelwerk']}")
    st.caption("Bitte vor verbindlicher Verwendung prüfen, ob eine neuere "
               "Fassung des Vollstreckungsplans gilt.")

    # ---------------- Export ----------------
    ergebnis_dict = {
        "erstellt_am": e["zeitstempel"],
        "bundesland": e["bundesland"],
        "gericht": {
            "landgericht": e["lg"],
            "amtsgericht": e["ag"],
            "staatsanwaltschaft": e.get("sta", ""),
            "oberlandesgericht": e.get("olg", ""),
            "quelle": e["quelle"],
        },
        "haftangaben": {
            "haftart": e["haftart"],
            "geschlecht": e["geschlecht"],
            "alter_bei_inhaftierung": e["alter"],
            "alter_zur_tatzeit": e["tatzeit"] or None,
            "vollzugsdauer": {
                "jahre": e["jahre"],
                "monate": e["monate"],
                "tage": e["tage"],
                "in_monaten": e["dauer_monate"],
                "lebenslang": e["lebenslang"],
            },
            "offener_vollzug": e["offen"],
            "auf_freiem_fuss": e["freier_fuss"],
            "sexualdelikt": e.get("sexualdelikt", False),
        },
        "ergebnis": {
            "zustaendige_jva": e["anstalt"],
            "regel": e["regel"],
            "anstalt_adresse": e["anstalt_adresse"],
            "hinweise": e["hinweise"],
        },
        "rechtsstand": e["stand"],
        "quelle_regelwerk": e["quelle_regelwerk"],
    }
    json_export = json.dumps(ergebnis_dict, ensure_ascii=False, indent=2)

    text_zeilen = [
        "Gerichts- und JVA-Finder – Ergebnis",
        "=" * 45,
        f"Erstellt am: {e['zeitstempel']}",
        f"Bundesland:  {e['bundesland']}",
        "",
        f"Landgerichtsbezirk:  {e['lg']}",
        f"Amtsgerichtsbezirk:  {e['ag'] or '-'}",
        f"Staatsanwaltschaft:  {e.get('sta') or '-'}",
        f"Oberlandesgericht:   {e.get('olg') or '-'}",
        f"Quelle Gericht: {e['quelle']}",
        "",
        "Haftangaben:",
        f"  Haftart:            {e['haftart']}",
        f"  Geschlecht:         {e['geschlecht']}",
        f"  Alter (Inhaft.):    {e['alter']}",
        f"  Alter zur Tatzeit:  {e['tatzeit'] or '-'}",
        f"  Vollzugsdauer:      {e['dauer_text']}"
        + (f" (≈ {e['dauer_monate']:.2f} Monate)" if e["dauer_monate"] is not None else ""),
        f"  Offener Vollzug:    {'ja' if e['offen'] else 'nein'}",
        f"  Auf freiem Fuß:     {'ja' if e['freier_fuss'] else 'nein'}",
        f"  Sexualdelikt:       {'ja' if e.get('sexualdelikt') else 'nein'}",
        "",
        "Ergebnis:",
        f"  Zuständige JVA: {e['anstalt'] or 'keine eindeutige Zuordnung'}",
        f"  Regel:          {e['regel']}",
    ]
    if e["anstalt_adresse"]:
        text_zeilen.append("  Anschrift:")
        text_zeilen += [f"    {z}" for z in e["anstalt_adresse"]]
    if e["hinweise"]:
        text_zeilen += ["", "Hinweise:"]
        text_zeilen += [f"  - {h}" for h in e["hinweise"]]
    text_zeilen += [
        "",
        f"Stand des Regelwerks: {e['stand']}",
        f"Amtliche Quelle: {e['quelle_regelwerk']}",
        "",
        "Ergebnis dient der Orientierung; keine verbindliche "
        "rechtliche Auskunft.",
    ]
    text_export = "\n".join(text_zeilen)

    dateibasis = ("jva_ergebnis_"
                  + e["zeitstempel"].replace("-", "").replace(":", "").replace(" ", "_"))

    st.markdown("**Ergebnis exportieren**")
    exp1, exp2, exp3 = st.columns(3)
    exp1.download_button(
        "⬇ Als Text (.txt)", data=text_export,
        file_name=f"{dateibasis}.txt", mime="text/plain")
    exp2.download_button(
        "⬇ Als JSON (.json)", data=json_export,
        file_name=f"{dateibasis}.json", mime="application/json")
    if exp3.button("🗑 Ergebnis löschen"):
        del st.session_state["jva_ergebnis"]
        st.rerun()
