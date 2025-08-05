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

            clienti = sorted(df_budget.index.unique())
            periodi
