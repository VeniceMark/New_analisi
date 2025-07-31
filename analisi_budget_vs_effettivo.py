
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import re

def calcola_scostamento(row):
    if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0:
        return row["Ore Effettive"]
    elif row["Ore a Budget"] > 0:
        return (row["Ore a Budget"] - row["Ore Effettive"]) / row["Ore a Budget"] * 100
    else:
        return np.nan

st.set_page_config(page_title="Analisi Budget vs Effettivo", layout="wide")
st.title("📊 Confronto Ore Lavorate vs Ore a Budget per Cliente")

uploaded_file = st.file_uploader("Carica un file Excel con due fogli (Effettivo e Budget)", type=["xlsx"])

if uploaded_file:
    try:
        df_eff = pd.read_excel(uploaded_file, sheet_name="Effettivo")
        df_budget = pd.read_excel(uploaded_file, sheet_name="Budget")

        df_eff.columns = df_eff.columns.str.strip().str.lower()
        df_budget.columns = df_budget.columns.str.strip()

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

            df_1_15 = df_eff[df_eff['giorno'] <= 15]
            pivot_1_15 = df_1_15.pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_15.columns = [f"{col} (1-15)" for col in pivot_1_15.columns]

            pivot_1_fine = df_eff.pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_fine.columns = [f"{col} (1-fine)" for col in pivot_1_fine.columns]

            df_eff_tot = pd.concat([pivot_1_15, pivot_1_fine], axis=1).fillna(0)
            df_eff_tot = df_eff_tot.reindex(sorted(df_eff_tot.columns), axis=1)
            df_eff_tot.index = df_eff_tot.index.astype(str)

            df_budget = df_budget.set_index('cliente')
            df_budget.index = df_budget.index.astype(str)
            pattern = re.compile(r'\d{4}-\d{2} \((1-15|1-fine)\)')
            valid_cols = [col for col in df_budget.columns if pattern.match(col)]
            df_budget = df_budget[valid_cols]

            all_cols = sorted(set(df_eff_tot.columns).union(set(df_budget.columns)))
            all_idx = sorted(set(df_eff_tot.index).union(set(df_budget.index)))

            eff = df_eff_tot.reindex(index=all_idx, columns=all_cols, fill_value=0)
            budget = df_budget.reindex(index=all_idx, columns=all_cols, fill_value=0)

            # Costruzione tabelle scostamento
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
                        diff_numeric.at[client, period] = 0

            def style_func(val):
                if val == "extrabudget":
                    return "background-color: mediumpurple; color: white"
                return ""

            st.subheader("📈 Scostamento percentuale tra Budget e Ore Effettive")
            styled = diff_numeric.style.background_gradient(
                cmap="RdYlGn", vmin=-50, vmax=100).format(
                lambda x: f"{x:.1f}%" if pd.notnull(x) else "").applymap(style_func, subset=diff_display == "extrabudget")
            st.dataframe(styled, use_container_width=True)

            st.subheader("📋 Dati Dettagliati")
            df_view = pd.concat([eff, budget, diff_display], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
            st.dataframe(df_view, use_container_width=True)

            buffer = io.BytesIO()
            diff_display.to_excel(buffer, index=True, sheet_name='Scostamenti')
            st.download_button("📥 Scarica Scostamenti in Excel", data=buffer.getvalue(), file_name="scostamenti.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.subheader("📊 Dashboard riepilogativa per cliente")
            totale_eff = eff.sum(axis=1)
            totale_budget = budget.sum(axis=1)
            dashboard = pd.DataFrame({
                "Ore Effettive": totale_eff,
                "Ore a Budget": totale_budget
            })
            dashboard["Scostamento %"] = dashboard.apply(calcola_scostamento, axis=1)

            def color_dashboard(row):
                if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0:
                    return ["background-color: mediumpurple; color: white" if col == "Scostamento %" else "" for col in row.index]
                else:
                    return [""] * len(row)

            def format_dashboard(x, row):
                if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0:
                    return f"{x:.1f}"
                elif pd.notnull(x):
                    return f"{x:.1f}%"
                return ""

            styled_dashboard = dashboard.style.apply(color_dashboard, axis=1).format(format_dashboard, axis=1)
            styled_dashboard = styled_dashboard.background_gradient(
                cmap="RdYlGn", subset=["Scostamento %"], vmin=-50, vmax=100)
            st.dataframe(styled_dashboard, use_container_width=True)

    except Exception as e:
        st.error(f"Errore durante l'elaborazione: {type(e).__name__}: {e}")
