# File aggiornato con filtri singoli a tendina (cliente e periodo completo)
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Gestione Budget e Analisi", layout="wide")
st.title("📊 Sistema Integrato: Budget Editor + Analisi Scostamenti")

if "budget_df" not in st.session_state:
    st.session_state["budget_df"] = None

sezione = st.sidebar.radio("Vai a:", ["📝 Budget Editor", "📈 Analisi Scostamenti"])

if sezione == "📝 Budget Editor":
    ...

elif sezione == "📈 Analisi Scostamenti":
    st.header("📈 Analisi Scostamenti Budget vs Effettivo")

    uploaded_eff = st.file_uploader("📥 Carica file 'Effettivo' (obbligatorio)", type=["xlsx"])
    if st.session_state["budget_df"] is not None:
        df_budget = st.session_state["budget_df"]
        st.success("✅ Usando il file Budget generato nella sessione.")
    else:
        uploaded_budget = st.file_uploader("📥 Carica file 'Budget' (alternativo)", type=["xlsx"])
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

            # 🎯 Filtri a tendina: cliente + periodo completo singolo
            clienti_lista = sorted(df_budget.index.astype(str).unique())
            cliente_scelto = st.sidebar.selectbox("👤 Seleziona cliente", ["Tutti"] + clienti_lista)

            periodi_disponibili = sorted(colonne_valide)
            periodo_scelto = st.sidebar.selectbox("📆 Seleziona periodo", ["Tutto"] + periodi_disponibili)

            if periodo_scelto == "Tutto":
                colonne_filtrate = colonne_valide
            else:
                colonne_filtrate = [periodo_scelto]

            eff = df_eff_tot.reindex(index=df_budget.index, columns=colonne_filtrate, fill_value=0)
            budget = df_budget.reindex(index=df_budget.index, columns=colonne_filtrate, fill_value=0)

            if cliente_scelto != "Tutti":
                eff = eff.loc[[cliente_scelto]] if cliente_scelto in eff.index else eff.iloc[0:0]
                budget = budget.loc[[cliente_scelto]] if cliente_scelto in budget.index else budget.iloc[0:0]

            # (seguono le 3 tabelle già corrette: diff_percent, df_view, dashboard riepilogativa)
            ...

        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {e}")
