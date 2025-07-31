
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import re

# ====================== FUNZIONI DI UTILITÀ ======================

def calcola_scostamento_valore(row: pd.Series) -> float:
    if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0:
        return row["Ore Effettive"]
    elif row["Ore a Budget"] > 0:
        return (row["Ore a Budget"] - row["Ore Effettive"]) / row["Ore a Budget"] * 100
    else:
        return 0.0

def calcola_scostamento_testo(row: pd.Series) -> str:
    if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0:
        return f"{row['Ore Effettive']:.1f}"
    elif row["Ore a Budget"] > 0:
        perc = (row["Ore a Budget"] - row["Ore Effettive"]) / row["Ore a Budget"] * 100
        return f"{perc:.1f}%"
    else:
        return "0.0%"

def evidenzia_viola_nera_extrabudget(df_display: pd.DataFrame) -> pd.DataFrame:
    styles = pd.DataFrame("", index=df_display.index, columns=df_display.columns)
    for row in df_display.index:
        for col in df_display.columns:
            val = df_display.at[row, col]
            if val == "extrabudget":
                styles.at[row, col] = "background-color: mediumpurple; color: white"
            elif val == "0.0%" and df_display.columns.isin([col]).any():
                styles.at[row, col] = "background-color: black; color: white"
    return styles

def evidenzia_dashboard_viola(row: pd.Series) -> list[str]:
    if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0:
        return ["", "", "background-color: mediumpurple; color: white"]
    return ["", "", ""]

# ====================== CONFIGURAZIONE STREAMLIT ======================

st.set_page_config(page_title="Analisi Budget vs Effettivo", layout="wide")
st.title("📊 Confronto Ore Lavorate vs Ore a Budget per Cliente")

uploaded_file = st.file_uploader("Carica un file Excel con due fogli (Effettivo e Budget)", type=["xlsx"])

# ====================== LOGICA PRINCIPALE ======================

if uploaded_file:
    try:
        df_eff = pd.read_excel(uploaded_file, sheet_name="Effettivo")
        df_budget = pd.read_excel(uploaded_file, sheet_name="Budget")

        df_eff.columns = df_eff.columns.str.strip().str.lower()
        df_budget.columns = df_budget.columns.str.strip()

        df_eff['data'] = pd.to_datetime(df_eff['data'], format='%d-%m-%Y', errors='coerce')
        df_eff['mese'] = df_eff['data'].dt.to_period('M').astype(str)
        df_eff['giorno'] = df_eff['data'].dt.day

        # Pivot Effettivo: 1-15
        df_1_15 = df_eff[df_eff['giorno'] <= 15]
        pivot_1_15 = df_1_15.pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
        pivot_1_15.columns = [f"{col} (1-15)" for col in pivot_1_15.columns]

        # Pivot Effettivo: 1-fine
        pivot_1_fine = df_eff.pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
        pivot_1_fine.columns = [f"{col} (1-fine)" for col in pivot_1_fine.columns]

        df_eff_tot = pd.concat([pivot_1_15, pivot_1_fine], axis=1).fillna(0)
        df_eff_tot = df_eff_tot.reindex(sorted(df_eff_tot.columns), axis=1)
        df_eff_tot.index = df_eff_tot.index.astype(str)

        # Pulizia Budget
        df_budget = df_budget.set_index('cliente')
        df_budget.index = df_budget.index.astype(str)
        pattern = re.compile(r'\d{4}-\d{2} \((1-15|1-fine)\)')
        valid_cols = [col for col in df_budget.columns if pattern.match(col)]
        df_budget = df_budget[valid_cols]

        # Uniforma indici e colonne
        all_cols = sorted(set(df_eff_tot.columns).union(set(df_budget.columns)))
        all_idx = sorted(set(df_eff_tot.index).union(set(df_budget.index)))

        eff = df_eff_tot.reindex(index=all_idx, columns=all_cols, fill_value=0)
        budget = df_budget.reindex(index=all_idx, columns=all_cols, fill_value=0)

        # ====================== SCOSTAMENTO % ======================

        diff_display = pd.DataFrame(index=all_idx, columns=all_cols, dtype=object)
        diff_numeric = pd.DataFrame(index=all_idx, columns=all_cols, dtype=float)

        for client in all_idx:
            for period in all_cols:
                b = budget.at[client, period]
                e = eff.at[client, period]
                if b > 0:
                    scost = round((b - e) / b * 100, 1)
                    diff_display.at[client, period] = f"{scost:.1f}%"
                    diff_numeric.at[client, period] = scost
                elif b == 0 and e > 0:
                    diff_display.at[client, period] = "extrabudget"
                    diff_numeric.at[client, period] = np.nan
                else:
                    diff_display.at[client, period] = "0.0%"
                    diff_numeric.at[client, period] = 0.0

        # ====================== VISUALIZZAZIONE ======================

        st.subheader("📈 Scostamento percentuale tra Budget e Ore Effettive")
        style_overlay = evidenzia_viola_nera_extrabudget(diff_display)
        styled = diff_numeric.style             .background_gradient(cmap="RdYlGn", vmin=-50, vmax=100)             .format(lambda x: f"{x:.1f}%" if pd.notnull(x) else "")             .apply(lambda _: style_overlay, axis=None)
        st.dataframe(styled, use_container_width=True)

        st.subheader("📋 Dati Dettagliati")
        df_view = pd.concat([eff, budget, diff_display], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
        style_overlay_view = evidenzia_viola_nera_extrabudget(diff_display)
        df_view_numeric = pd.concat([eff, budget, diff_numeric], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
        styled_view = df_view_numeric.style             .background_gradient(cmap="RdYlGn", vmin=-50, vmax=100, subset=pd.IndexSlice["Scostamento %", :])             .format(lambda x: f"{x:.1f}%" if pd.notnull(x) else "", subset=pd.IndexSlice["Scostamento %", :])             .apply(lambda _: style_overlay_view, axis=None)
        st.dataframe(styled_view, use_container_width=True)

        # ====================== DASHBOARD ======================

        st.subheader("📊 Dashboard riepilogativa per cliente")
        totale_eff = eff.sum(axis=1)
        totale_budget = budget.sum(axis=1)

        dashboard = pd.DataFrame({
            "Ore Effettive": totale_eff,
            "Ore a Budget": totale_budget
        })
        dashboard["Scostamento Valore"] = dashboard.apply(calcola_scostamento_valore, axis=1)
        dashboard["Scostamento %"] = dashboard.apply(calcola_scostamento_testo, axis=1)

        styled_dashboard = dashboard[["Ore Effettive", "Ore a Budget", "Scostamento %", "Scostamento Valore"]].style             .apply(evidenzia_dashboard_viola, axis=1)             .background_gradient(subset=["Scostamento Valore"], cmap="RdYlGn", vmin=-50, vmax=100)
        st.dataframe(styled_dashboard, use_container_width=True)

        # ====================== GRAFICO ======================

        st.subheader("📉 Grafico a barre: Budget vs Effettivo per clienti")
        data_for_chart = dashboard.copy()
        extrabudget_mask = (data_for_chart["Ore a Budget"] == 0) & (data_for_chart["Ore Effettive"] > 0)

        fig, ax = plt.subplots(figsize=(12, 6))
        bars1 = ax.bar(data_for_chart.index, data_for_chart["Ore a Budget"], label="Budget")
        bars2 = ax.bar(data_for_chart.index, data_for_chart["Ore Effettive"], label="Effettivo")
        bars3 = ax.bar(data_for_chart[extrabudget_mask].index,
                       data_for_chart[extrabudget_mask]["Ore Effettive"],
                       label="Extrabudget", color='mediumpurple')

        ax.set_ylabel("Ore")
        ax.set_title("Confronto Budget vs Effettivo")
        ax.legend()
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Errore: {type(e).__name__}: {e}")
