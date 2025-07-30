
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import re

st.set_page_config(page_title="Analisi Budget vs Effettivo", layout="wide")
st.title("📊 Confronto Ore Lavorate vs Ore a Budget per Cliente")

uploaded_file = st.file_uploader("Carica un file Excel con due fogli (Effettivo e Budget)", type=["xlsx"])

if uploaded_file:
    try:
        # Legge i due fogli
        df_eff = pd.read_excel(uploaded_file, sheet_name="Effettivo")
        df_budget = pd.read_excel(uploaded_file, sheet_name="Budget")

        # Pulizia nomi colonne
        df_eff.columns = df_eff.columns.str.strip().str.lower()
        df_budget.columns = df_budget.columns.str.strip()

        # Verifica colonne richieste
        if not {'cliente', 'data', 'ore'}.issubset(df_eff.columns):
            st.error("Il foglio 'Effettivo' deve contenere le colonne: cliente, data, ore")
        elif 'cliente' not in df_budget.columns:
            st.error("Il foglio 'Budget' deve contenere almeno la colonna 'cliente' e colonne mensili tipo '2025-07 (1-15)'")
        else:
            df_eff['data'] = pd.to_datetime(df_eff['data'], format='%d-%m-%Y', errors='coerce')
            if df_eff['data'].isnull().any():
                st.warning("Attenzione: alcune date non sono valide. Devono essere nel formato gg-mm-aaaa.")

            df_eff['mese'] = df_eff['data'].dt.to_period('M').astype(str)
            df_eff['giorno'] = df_eff['data'].dt.day

            # Aggregazione 1-15
            df_1_15 = df_eff[df_eff['giorno'] <= 15]
            pivot_1_15 = df_1_15.pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_15.columns = [f"{col} (1-15)" for col in pivot_1_15.columns]

            # Aggregazione 1-fine
            pivot_1_fine = df_eff.pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_fine.columns = [f"{col} (1-fine)" for col in pivot_1_fine.columns]

            # Unione effettivi
            df_eff_tot = pd.concat([pivot_1_15, pivot_1_fine], axis=1).fillna(0)
            df_eff_tot = df_eff_tot.reindex(sorted(df_eff_tot.columns), axis=1)
            df_eff_tot.index = df_eff_tot.index.astype(str)

            # Prepara budget
            df_budget = df_budget.set_index('cliente')
            df_budget.index = df_budget.index.astype(str)

            # Filtra colonne valide del budget
            pattern = re.compile(r'\d{4}-\d{2} \((1-15|1-fine)\)')
            valid_cols = [col for col in df_budget.columns if pattern.match(col)]
            df_budget = df_budget[valid_cols]

            comuni = df_eff_tot.columns.intersection(df_budget.columns)
            if comuni.empty:
                st.error("Nessuna colonna in comune tra fogli Effettivo e Budget. Verifica le intestazioni.")
            else:
                eff = df_eff_tot[comuni].copy()
                budget = df_budget[comuni].copy()

                diff_percent = (budget - eff) / budget.replace(0, np.nan) * 100
                diff_percent = diff_percent.replace([np.inf, -np.inf], np.nan)

                st.subheader("📈 Scostamento percentuale tra Budget e Ore Effettive")

                def color_map(val):
                    if pd.isna(val):
                        return ''
                    elif val >= 10:
                        return 'background-color: #b6fcb6'
                    elif 0 <= val < 10:
                        return 'background-color: #fff59d'
                    else:
                        return 'background-color: #ff9999'

                styled = diff_percent.style.format("{:.1f}%").applymap(color_map)
                st.dataframe(styled, use_container_width=True)

                # Tabella riepilogativa
                st.subheader("📋 Dati Dettagliati")
                df_view = pd.concat([eff, budget, diff_percent], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
                st.dataframe(df_view.round(1), use_container_width=True)

                # Download Excel
                buffer = io.BytesIO()
                diff_percent.to_excel(buffer, index=True, sheet_name='Scostamenti')
                st.download_button("📥 Scarica Scostamenti in Excel", data=buffer.getvalue(), file_name="scostamenti.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                # Grafico per cliente
                st.subheader("📊 Grafico Confronto per Cliente")
                cliente_selezionato = st.selectbox("Seleziona un cliente", df_eff_tot.index)
                if cliente_selezionato:
                    fig, ax = plt.subplots()
                    eff.loc[cliente_selezionato].plot(kind='bar', ax=ax, label="Effettivo", alpha=0.7)
                    budget.loc[cliente_selezionato].plot(kind='bar', ax=ax, label="Budget", alpha=0.7)
                    ax.set_title(f"Confronto ore - {cliente_selezionato}")
                    ax.set_ylabel("Ore")
                    ax.legend()
                    st.pyplot(fig)

    except Exception as e:
        st.error(f"Errore durante l'elaborazione: {type(e).__name__}: {e}")
