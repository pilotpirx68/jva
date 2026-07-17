#!/usr/bin/env python3
"""
app.py – Web-Oberfläche (Streamlit) für den Gerichts- und JVA-Finder M-V.

Start lokal:   streamlit run app.py
Deployment:    GitHub-Repo + share.streamlit.io  (siehe requirements.txt)
"""

import streamlit as st

from logik import (
    gerichte_suchen, lg_ag_aus_ergebnis, auswahl_zu_lg_ag,
    ermittle_jva, dauer_in_monate, pruefe_dauer_plausibel, Fall,
    LG_BEZIRKE_MV, LG_AUSWAHL, HAFTARTEN, ANSTALTEN, STAND, QUELLE,
)

st.set_page_config(page_title="Gerichts- und JVA-Finder (M-V)", page_icon="⚖️")
st.title("⚖️ Gerichts- und JVA-Finder (M-V)")
st.caption("Vollstreckungsplan Mecklenburg-Vorpommern")

# --- Sitzungszustand ---
st.session_state.setdefault("lg", "")
st.session_state.setdefault("ag", "")
st.session_state.setdefault("quelle", "")
st.session_state.setdefault("lg_auswahl", "")

# ============ Schritt 1: Online-Suche ============
st.header("Schritt 1 – Zuständiges Gericht online suchen")
c1, c2 = st.columns(2)
plz = c1.text_input("Postleitzahl")
ort = c2.text_input("Ort (optional)")

if st.button("Gericht suchen"):
    if not plz.strip().isdigit() or len(plz.strip()) != 5:
        st.error("Bitte eine fünfstellige Postleitzahl angeben.")
    else:
        try:
            with st.spinner("Onlineabfrage läuft …"):
                relevant = gerichte_suchen(plz.strip(), ort.strip())
            if not relevant:
                st.warning("Keine Ergebnisse. Bitte Ort ergänzen oder "
                           "in Schritt 1b manuell eingeben.")
            else:
                lg, ag = lg_ag_aus_ergebnis(relevant)
                st.session_state.update(lg=lg, ag=ag, quelle="online")

                # Online-Ergebnis in die manuelle Auswahl spiegeln – Wismar-sicher
                if lg == "Schwerin":
                    if "wismar" in (ag or "").lower():
                        st.session_state["lg_auswahl"] = (
                            "Schwerin – AG-Bezirk Wismar "
                            "(Einzugsbereich Rostock / JVA Waldeck)")
                    else:
                        st.session_state["lg_auswahl"] = \
                            "Schwerin (AG-Bezirke Schwerin/Ludwigslust)"
                        st.warning(
                            "⚠ Landgericht Schwerin erkannt. Falls der Ort im "
                            "AG-Bezirk Wismar liegt (z. B. Wismar, Grevesmühlen, "
                            "Nordwestmecklenburg), bitte in Schritt 1b die "
                            "Wismar-Option wählen – dann ist die JVA Waldeck "
                            "(statt Bützow) zuständig.")
                elif lg in ("Stralsund", "Rostock", "Neubrandenburg"):
                    st.session_state["lg_auswahl"] = lg

                for e in relevant:
                    st.markdown(f"**{e['name']}**")
                    st.text("\n".join(e["adresse"]))
        except Exception as exc:
            st.error(f"Suche fehlgeschlagen: {exc}\n\n"
                     "Bitte in Schritt 1b manuell eingeben.")

# ============ Schritt 1b: Manuell ============
st.header("Schritt 1b – Manuelle Eingabe (offline / falls Gericht bekannt)")
st.info("Besonderheit: Der AG-Bezirk **Wismar** gehört zum LG Schwerin, wird "
        "für den Vollzug aber dem Bereich Rostock (**JVA Waldeck**) zugeordnet "
        "– bitte gesondert auswählen.")

optionen = [""] + LG_AUSWAHL
vorauswahl = st.session_state.get("lg_auswahl", "")
index = optionen.index(vorauswahl) if vorauswahl in optionen else 0
auswahl = st.selectbox("Landgerichtsbezirk", optionen, index=index)

if st.button("Manuell übernehmen"):
    if not auswahl:
        st.error("Bitte einen Landgerichtsbezirk aus der Liste wählen.")
    else:
        lg, ag = auswahl_zu_lg_ag(auswahl)
        st.session_state.update(lg=lg, ag=ag, quelle="manuell", lg_auswahl=auswahl)

# --- aktives Gericht anzeigen ---
if st.session_state["lg"]:
    txt = f"**Aktives Gericht:** Landgericht {st.session_state['lg']}"
    if st.session_state["ag"]:
        txt += f" / Amtsgericht {st.session_state['ag']}"
    txt += f"  (Quelle: {st.session_state['quelle']})"
    st.success(txt)

# ============ Schritt 2: Haftangaben ============
st.header("Schritt 2 – Angaben zur Haft")
c5, c6 = st.columns(2)
haftart = c5.selectbox("Haftart", HAFTARTEN, index=1)
geschlecht = c6.selectbox("Geschlecht", ["m", "w", "d"])
c7, c8 = st.columns(2)
alter = c7.number_input("Alter (bei Inhaftierung)", min_value=0, max_value=120, value=30)
tatzeit = c8.number_input("Alter zur Tatzeit (nur U-Haft, 0 = k. A.)",
                          min_value=0, max_value=120, value=0)

st.markdown("**Vollzugsdauer**")
d1, d2, d3 = st.columns(3)
jahre = d1.number_input("Jahre", min_value=0, max_value=99, value=0)
monate = d2.number_input("Monate", min_value=0, max_value=11, value=0)
tage = d3.number_input("Tage", min_value=0, max_value=30, value=0)

c9, c10 = st.columns(2)
lebenslang = c9.checkbox("lebenslang")
offen = c9.checkbox("offener Vollzug")
freier_fuss = c10.checkbox("auf freiem Fuß (Ladung, EFS/Männer)")

if st.button("Zuständige JVA ermitteln", type="primary"):
    lg = st.session_state["lg"]
    ag = st.session_state["ag"]
    if not lg:
        st.warning("Bitte zuerst ein Gericht ermitteln (Schritt 1) oder "
                   "manuell eingeben (Schritt 1b).")
    elif lg not in LG_BEZIRKE_MV:
        st.error(f"Landgericht '{lg}' liegt nicht in M-V. Dieser "
                 f"Vollstreckungsplan gilt nur für {', '.join(LG_BEZIRKE_MV)}.")
    else:
        # Plausibilitätswarnung (blockiert nicht, weist aber hin)
        warnungen = pruefe_dauer_plausibel(int(jahre), int(monate), int(tage),
                                           bool(lebenslang))
        for w in warnungen:
            st.warning("Plausibilität: " + w)

        # Wismar-Sicherheitshinweis
        if lg == "Schwerin" and "wismar" not in (ag or "").lower():
            st.info("Hinweis: Landgerichtsbezirk Schwerin **ohne** AG-Bezirk "
                    "Wismar → JVA Bützow. Liegt der Fall im AG-Bezirk Wismar, "
                    "bitte in Schritt 1b die Wismar-Option wählen (→ JVA Waldeck).")

        dauer_monate = dauer_in_monate(int(jahre), int(monate), int(tage))
        fall = Fall(
            haftart=haftart, geschlecht=geschlecht, alter=int(alter),
            tatzeit_alter=int(tatzeit) or None,
            dauer_monate=dauer_monate,
            lebenslang=lebenslang, offen=offen, auf_freiem_fuss=freier_fuss,
        )
        anstalt, regel, hinweise = ermittle_jva(fall, lg, ag)

        st.subheader("Ergebnis – Zuständige JVA")
        if dauer_monate is not None:
            st.caption(f"Vollzugsdauer: {int(jahre)} J. {int(monate)} M. "
                       f"{int(tage)} T. (≈ {dauer_monate:.2f} Monate)")
        elif lebenslang:
            st.caption("Vollzugsdauer: lebenslang")

        if anstalt is None:
            st.warning(f"Keine eindeutige Zuordnung möglich ({regel}).")
        else:
            st.success(f"**Zuständig: {anstalt}**")
            st.caption(f"Regel: {regel}")
            st.text("\n".join(ANSTALTEN.get(anstalt.split(" (")[0], [])))

        for h in hinweise:
            st.info(h)
        st.caption(f"Stand des Regelwerks: {STAND}")
        st.caption(f"Amtliche Quelle: {QUELLE}")
        st.caption("Bitte vor verbindlicher Verwendung prüfen, ob eine neuere "
                   "Fassung des Vollstreckungsplans gilt.")
