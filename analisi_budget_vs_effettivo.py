# File aggiornato: aggiunta tendina di filtro cliente nella sidebar per la dashboard
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Gestione Budget e Analisi", layout="wide")
st.title("\U0001F4CA Sistema Integrato: Budget Editor + Analisi Scostamenti")

if "budget_df" not in st.session_state:
    st.session_state["budget_df"] = None

sezione = st.sidebar.radio("Vai a:", ["\U0001F4DD Budget Editor", "\U0001F4C8 Analisi Scostamenti"])

if sezione == "\U0001F4DD Budget Editor":
    st.header("\U0001F4DD Budget Editor – Inserimento e Calcolo Slot")

    uploaded_budget = st.file_uploader("\U0001F4C4 Carica un file Budget esistente (opzionale)", type=["xlsx"])
    if uploaded_budget:
        try:
            df = pd.read_excel(uploaded_budget)
            st.session_state["budget_df"] = df
            st.success("✅ File budget caricato correttamente.")
        except Exception as e:
            st.error(f"Errore nel caricamento: {e}")

    st.subheader("➕ Nuovo Cliente")

    with st.form("aggiungi_cliente"):
        nuovo_cliente = st.text_input("Nome Cliente").strip()
        anni = st.multiselect("Anni da includere", options=list(range(2024, 2036)), default=[datetime.now().year])
        mesi = st.multiselect("Mesi da includere", options=list(range(1, 13)), default=list(range(1, 13)))

        coeff = st.number_input("Coefficiente", min_value=1, max_value=100, value=50)
        try:
            budget_mensile = float(st.text_input("Budget mensile (numero)", value="0"))
        except:
            budget_mensile = 0.0
        try:
            xselling = float(st.text_input("Beget Xselling (numero)", value="0"))
        except:
            xselling = 0.0

        submitted = st.form_submit_button("Aggiungi Cliente")

        if submitted and nuovo_cliente and anni and mesi:
            record = {"cliente": nuovo_cliente}
            for anno in anni:
                for mese in mesi:
                    base = f"{anno}-{mese:02d}"
                    totale = (budget_mensile + xselling) / coeff if coeff > 0 else 0
                    slot_1_fine = round(totale, 2)
                    slot_1_15 = round(totale / 2, 2)

                    record[f"{base}_coeff"] = coeff
                    record[f"{base}_budget_mensile"] = budget_mensile
                    record[f"{base}_xselling"] = xselling
                    record[f"{base} (1-15)"] = slot_1_15
                    record[f"{base} (1-fine)"] = slot_1_fine

            nuovo_df = pd.DataFrame([record])

            if st.session_state["budget_df"] is not None:
                st.session_state["budget_df"] = pd.concat([st.session_state["budget_df"], nuovo_df], ignore_index=True)
            else:
                st.session_state["budget_df"] = nuovo_df
            st.success(f"Cliente '{nuovo_cliente}' aggiunto!")

    if st.session_state["budget_df"] is not None:
        st.subheader("✏️ Modifica diretta del Budget")
        edited_df = st.data_editor(st.session_state["budget_df"], use_container_width=True, num_rows="dynamic")
        st.session_state["budget_df"] = edited_df

        buffer = BytesIO()
        edited_df.to_excel(buffer, index=False)
        st.download_button(
            label="\U0001F4C5 Scarica file Budget aggiornato",
            data=buffer.getvalue(),
            file_name="budget_generato.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Carica un file o aggiungi un cliente per iniziare.")

elif sezione == "\U0001F4C8 Analisi Scostamenti":
    st.header("\U0001F4C8 Analisi Scostamenti Budget vs Effettivo")

    uploaded_eff = st.file_uploader("\U0001F4C5 Carica file 'Effettivo' (obbligatorio)", type=["xlsx"])
    if st.session_state["budget_df"] is not None:
        df_budget = st.session_state["budget_df"]
        st.success("✅ Usando il file Budget generato nella sessione.")
    else:
        uploaded_budget = st.file_uploader("\U0001F4C5 Carica file 'Budget' (alternativo)", type=["xlsx"])
        if uploaded_budget:
            df_budget = pd.read_excel(uploaded_budget)
        else:
            df_budget = None

    if uploaded_eff and df_budget is not None:
        try:
            df_eff = pd.read_excel(uploaded_eff, sheet_name="Effettivo")
            df_eff.columns = df_eff.columns.str.strip().str.lower()
            df_eff['data'] = pd.to_datetime(df_eff['data'], format='%d-%m-%Y', errors='coerce')
            df_eff['mese'] = df_eff['data'].dt.to_period('M').astype(str)
            df_eff['giorno'] = df_eff['data'].dt.day

            pivot_1_15 = df_eff[df_eff['giorno'] <= 15].pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_15.columns = [f"{col} (1-15)" for col in pivot_1_15.columns]

            pivot_1_fine = df_eff.pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_fine.columns = [f"{col} (1-fine)" for col in pivot_1_fine.columns]

            df_eff_tot = pd.concat([pivot_1_15, pivot_1_fine], axis=1).fillna(0)
            df_eff_tot = df_eff_tot.reindex(sorted(df_eff_tot.columns), axis=1)
            df_eff_tot.index = df_eff_tot.index.astype(str)

            df_budget = df_budget.set_index("cliente").fillna(0)
            pattern = re.compile(r"^\d{4}-\d{2} \(1-(15|fine)\)$")
            colonne_valide = [col for col in df_budget.columns if pattern.match(col)]
            colonne_comuni = df_eff_tot.columns.intersection(colonne_valide)

            eff = df_eff_tot.reindex(index=df_budget.index, columns=colonne_comuni, fill_value=0)
            budget = df_budget.reindex(index=df_budget.index, columns=colonne_comuni, fill_value=0)

            diff_percent = pd.DataFrame(index=budget.index, columns=budget.columns, dtype=object)

            for col in colonne_comuni:
                diff_percent[col] = np.where(
                    (budget[col] == 0) & (eff[col] > 0), "Extrabudget",
                    np.where((budget[col] == 0) & (eff[col] == 0), "Zero",
                    ((budget[col] - eff[col]) / budget[col] * 100).round(1).astype(str) + "%")
                )

            # Mappa colori con gradiente -50% -> +100% (in linea con specifiche)
            def colori_scostamenti(val):
                if val == "Extrabudget":
                    return 'background-color: violet; color: white;'
                elif val == "Zero":
                    return 'background-color: black; color: white;'
                else:
                    try:
                        val_float = float(val.strip('%'))
                        # normalizzazione: -50% => 0.0, +100% => 1.0
                        norm = (val_float + 50) / 150
                        norm = max(0.0, min(1.0, norm))
                        color = plt.cm.RdYlGn(norm)
                        return f'background-color: {matplotlib.colors.rgb2hex(color)}'
                    except:
                        return ""

            # ----- DASHBOARD riepilogativa (solo colonne "(1-fine)") -----
            colonne_budget_fine = [col for col in budget.columns if "(1-fine)" in col]
            colonne_effettivo_fine = [col for col in eff.columns if "(1-fine)" in col]

            dashboard = pd.DataFrame({
                "Ore Effettive": eff[colonne_effettivo_fine].sum(axis=1),
                "Ore a Budget": budget[colonne_budget_fine].sum(axis=1)
            })

            dashboard["Scostamento Valore (ore)"] = dashboard["Ore a Budget"] - dashboard["Ore Effettive"]
            dashboard["Scostamento %"] = np.where(
                dashboard["Ore a Budget"] > 0,
                ((dashboard["Ore a Budget"] - dashboard["Ore Effettive"]) / dashboard["Ore a Budget"] * 100).round(1),
                np.where(dashboard["Ore Effettive"] > 0, -9999, 0)
            )
            # rimuovi righe completamente a zero
            dashboard = dashboard[~((dashboard["Ore Effettive"] == 0) & (dashboard["Ore a Budget"] == 0))]

            # === 🔽 NUOVO: filtro cliente nella SIDEBAR ===
            clienti_opzioni = ["Tutti i clienti"] + list(dashboard.index.astype(str))
            selezione_cliente = st.sidebar.selectbox("Filtro cliente (dashboard)", clienti_opzioni, index=0)

            if selezione_cliente != "Tutti i clienti":
                idx = [selezione_cliente]
            else:
                idx = list(dashboard.index.astype(str))

            # Applica filtro a tutte le viste
            eff_f = eff.loc[eff.index.isin(idx)]
            budget_f = budget.loc[budget.index.isin(idx)]
            diff_percent_f = diff_percent.loc[diff_percent.index.isin(idx)]
            dashboard_f = dashboard.loc[dashboard.index.isin(idx)]

            # Ordinamento dashboard dopo filtro
            dashboard_f = dashboard_f.sort_values(by="Scostamento %", ascending=True)

            # Formatter per Scostamento % (stringhe con colori)
            def format_scostamento(val):
                if val == -9999:
                    return "Extrabudget"
                elif val == 0:
                    return "0%"
                else:
                    return f"{val:.1f}%"

            # ----- TABELLE -----
            st.subheader("\U0001F4C8 Scostamento percentuale tra Budget e Ore Effettive")
            styled_diff = diff_percent_f.style.applymap(colori_scostamenti)
            styled_diff = styled_diff.format(lambda v: "0%" if v == "Zero" else v)
            st.dataframe(styled_diff, use_container_width=True)

            st.subheader("\U0001F4CB Dati Dettagliati")
            df_view = pd.concat([eff_f, budget_f, diff_percent_f], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
            scostamento_cols = [col for col in df_view.columns if isinstance(col, tuple) and col[0] == "Scostamento %"]
            styled_view = df_view.style.applymap(colori_scostamenti, subset=pd.IndexSlice[:, scostamento_cols])
            styled_view = styled_view.format(lambda v: "0%" if v == "Zero" else v, subset=pd.IndexSlice[:, scostamento_cols])
            st.dataframe(styled_view, use_container_width=True)

            st.subheader("\U0001F4CA Dashboard riepilogativa per cliente")
            dashboard_f["Scostamento % (str)"] = dashboard_f["Scostamento %"].apply(format_scostamento)
            styled_dashboard = dashboard_f.style.applymap(colori_scostamenti, subset=["Scostamento % (str)"])
            st.dataframe(styled_dashboard, use_container_width=True)

        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {e}")
