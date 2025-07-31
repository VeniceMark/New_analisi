
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
        df_eff = pd.read_excel(uploaded_file, sheet_name="Effettivo")
        df_budget = pd.read_excel(uploaded_file, sheet_name="Budget")

        df_eff.columns = df_eff.columns.str.strip().str.lower()
        df_budget.columns = df_budget.columns.str.strip()

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

        df_budget = df_budget.set_index('cliente').fillna(0)
        comuni = df_eff_tot.columns.intersection(df_budget.columns)
        
        eff = df_eff_tot[comuni].fillna(0)
        budget = df_budget[comuni].fillna(0)

        diff_percent = pd.DataFrame(index=budget.index, columns=budget.columns, dtype=object)

        for col in comuni:
            diff_percent[col] = np.where(
                budget[col] > 0,
                ((budget[col] - eff[col]) / budget[col] * 100).round(1).astype(str) + "%",
                np.where(eff[col] > 0, "Extrabudget", "0%")
            )

        def colori_scostamenti(val):
            if val == "Extrabudget":
                return 'background-color: violet; color: white;'
            elif val == "0%":
                return 'background-color: black; color: white;'
            else:
                val_float = float(val.strip('%'))
                norm = (val_float + 50) / 150
                color = plt.cm.RdYlGn(norm)
                return f'background-color: {matplotlib.colors.rgb2hex(color)}'

        st.subheader("📈 Scostamento percentuale tra Budget e Ore Effettive")
        st.dataframe(diff_percent.style.applymap(colori_scostamenti), use_container_width=True)

        df_view = pd.concat([eff, budget, diff_percent], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
        st.subheader("📋 Dati Dettagliati")
        st.dataframe(df_view, use_container_width=True)

        dashboard = pd.DataFrame({
            "Ore Effettive": eff.sum(axis=1),
            "Ore a Budget": budget.sum(axis=1)
        })

        dashboard["Scostamento Valore (ore)"] = dashboard["Ore a Budget"] - dashboard["Ore Effettive"]
        dashboard["Scostamento %"] = np.where(
            dashboard["Ore a Budget"] > 0,
            ((dashboard["Ore a Budget"] - dashboard["Ore Effettive"]) / dashboard["Ore a Budget"] * 100).round(1).astype(str) + "%",
            np.where(dashboard["Ore Effettive"] > 0, "Extrabudget", "0%")
        )

        dashboard = dashboard[~((dashboard["Ore Effettive"] == 0) & (dashboard["Ore a Budget"] == 0))]

        st.subheader("📊 Dashboard riepilogativa per cliente")
        st.dataframe(dashboard.style.applymap(colori_scostamenti, subset=["Scostamento %"]), use_container_width=True)

        st.subheader("📉 Grafico a barre Budget vs Effettivo")
        clienti = dashboard.index
        x = np.arange(len(clienti))
        width = 0.3

        fig, ax = plt.subplots(figsize=(12, max(6, len(clienti)*0.5)))
        ax.barh(x - width, dashboard["Ore a Budget"], width, label='Budget')
        ax.barh(x, dashboard["Ore Effettive"], width, label='Effettivo')
        ax.barh(x + width, np.where(dashboard["Scostamento %"]=="Extrabudget", dashboard["Ore Effettive"], 0), width, label='Extrabudget', color='purple')

        ax.set(yticks=x, yticklabels=clienti, xlabel='Ore')
        ax.legend()
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Errore: {e}")
