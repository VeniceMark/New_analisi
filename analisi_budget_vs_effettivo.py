
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import io

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

        clienti_comuni = df_eff_tot.index.union(df_budget.index)
        colonne_comuni = df_eff_tot.columns.intersection(df_budget.columns)

        eff = df_eff_tot.reindex(index=clienti_comuni, columns=colonne_comuni, fill_value=0)
        budget = df_budget.reindex(index=clienti_comuni, columns=colonne_comuni, fill_value=0)

        periodo_scelto = st.selectbox("🎯 Seleziona periodo da visualizzare:", ["Tutto"] + list(colonne_comuni))

        if periodo_scelto == "Tutto":
            dati_effettivi = eff.sum(axis=1)
            dati_budget = budget.sum(axis=1)
        else:
            dati_effettivi = eff[periodo_scelto]
            dati_budget = budget[periodo_scelto]

        dashboard = pd.DataFrame({
            "Ore Effettive": dati_effettivi,
            "Ore a Budget": dati_budget
        })

        dashboard["Scostamento Valore (ore)"] = dashboard["Ore a Budget"] - dashboard["Ore Effettive"]
        dashboard["Scostamento %"] = np.where(
            dashboard["Ore a Budget"] > 0,
            ((dashboard["Ore a Budget"] - dashboard["Ore Effettive"]) / dashboard["Ore a Budget"] * 100).round(1),
            np.where(dashboard["Ore Effettive"] > 0, -9999, 0)
        )

        dashboard = dashboard[~((dashboard["Ore Effettive"] == 0) & (dashboard["Ore a Budget"] == 0))]
        dashboard = dashboard.sort_values(by="Scostamento %", ascending=True)

        def colori_scostamenti(val):
            if val == -9999:
                return 'background-color: violet; color: white;'
            elif val == 0:
                return 'background-color: black; color: white;'
            else:
                norm = (val + 50) / 150
                color = plt.cm.RdYlGn(norm)
                return f'background-color: {matplotlib.colors.rgb2hex(color)}'

        def format_scostamento(val):
            if val == -9999:
                return "Extrabudget"
            elif val == 0:
                return "0%"
            else:
                return f"{val:.1f}%"

        st.subheader("📊 Dashboard riepilogativa per cliente")
        styled_dashboard = dashboard.style.format({"Scostamento %": format_scostamento})
        styled_dashboard = styled_dashboard.applymap(colori_scostamenti, subset=["Scostamento %"])
        st.dataframe(styled_dashboard, use_container_width=True)

        st.subheader("📉 Grafico a barre Budget vs Effettivo")
        clienti = dashboard.index
        x = np.arange(len(clienti))
        width = 0.3

        fig, ax = plt.subplots(figsize=(12, max(6, len(clienti)*0.5)))
        ax.barh(x - width, dashboard["Ore a Budget"], width, label='Budget')
        ax.barh(x, dashboard["Ore Effettive"], width, label='Effettivo')
        ax.barh(x + width, np.where(dashboard["Scostamento %"]==-9999, dashboard["Ore Effettive"], 0), width, label='Extrabudget', color='purple')

        ax.set(yticks=x, yticklabels=clienti, xlabel='Ore')
        ax.legend()
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Errore: {e}")
