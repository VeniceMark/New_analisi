
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

            comuni = df_eff_tot.columns.union(df_budget.columns)
            clienti = df_eff_tot.index.union(df_budget.index)

            eff = df_eff_tot.reindex(index=clienti, columns=comuni).fillna(0)
            budget = df_budget.reindex(index=clienti, columns=comuni).fillna(0)

            diff_percent = pd.DataFrame(index=clienti, columns=comuni, dtype=object)

            for col in comuni:
                for idx in clienti:
                    b = budget.at[idx, col] if pd.notna(budget.at[idx, col]) else 0
                    e = eff.at[idx, col] if pd.notna(eff.at[idx, col]) else 0
                    if b == 0 and e > 0:
                        diff_percent.at[idx, col] = "extrabudget"
                    elif b == 0 and e == 0:
                        diff_percent.at[idx, col] = np.nan
                    elif b > 0:
                        diff = (b - e) / b * 100
                        diff_percent.at[idx, col] = round(diff, 1)
                    else:
                        diff_percent.at[idx, col] = np.nan

            st.subheader("📈 Scostamento percentuale tra Budget e Ore Effettive (inclusi clienti unilaterali)")

            def color_custom(val):
                if isinstance(val, str) and val == "extrabudget":
                    return "background-color: #d5b3ff; color: black"
                elif isinstance(val, (int, float)):
                    if val >= 75:
                        return "background-color: #c7fdb7"
                    elif 0 <= val < 75:
                        return "background-color: #fdf8b7"
                    elif val < 0:
                        return "background-color: #f9c2c2"
                return ""

            styled = diff_percent.style.applymap(color_custom).format(
                lambda v: v if isinstance(v, str) else f"{v:.1f}%"
            )
            st.dataframe(styled, use_container_width=True)

            st.subheader("📊 Grafico a barre: Budget vs Effettivo per clienti")
            opzioni = ["Totale complessivo"] + sorted(comuni)
            mese_selezionato = st.selectbox("Seleziona un mese o il totale", opzioni)

            if mese_selezionato == "Totale complessivo":
                df_plot = pd.DataFrame({
                    "Effettivo": eff.sum(axis=1),
                    "Budget": budget.sum(axis=1)
                })
                titolo = "Confronto Totale Complessivo"
            else:
                df_plot = pd.DataFrame({
                    "Effettivo": eff[mese_selezionato],
                    "Budget": budget[mese_selezionato]
                })
                titolo = f"Confronto Ore - {mese_selezionato}"

            df_plot = df_plot.fillna(0).sort_values("Effettivo", ascending=True)
            fig, ax = plt.subplots(figsize=(10, len(df_plot) * 0.4))
            df_plot.plot(kind="barh", ax=ax)
            ax.set_xlabel("Ore")
            ax.set_ylabel("Cliente")
            ax.set_title(titolo)
            st.pyplot(fig)

            st.subheader("📊 Dashboard riepilogativa per cliente")

            if mese_selezionato == "Totale complessivo":
                totale_eff = eff.sum(axis=1)
                totale_budget = budget.sum(axis=1)
            else:
                totale_eff = eff[mese_selezionato]
                totale_budget = budget[mese_selezionato]

            dashboard = pd.DataFrame({
                "Ore Effettive": totale_eff,
                "Ore a Budget": totale_budget
            })

            dashboard["Differenza (ore)"] = dashboard["Ore a Budget"] - dashboard["Ore Effettive"]
            dashboard["Scostamento %"] = np.where(
                dashboard["Ore a Budget"] == 0,
                np.where(dashboard["Ore Effettive"] > 0, "extrabudget", np.nan),
                (dashboard["Ore a Budget"] - dashboard["Ore Effettive"]) / dashboard["Ore a Budget"] * 100
            )

            def color_dashboard(val):
                if isinstance(val, str) and val == "extrabudget":
                    return "background-color: #d5b3ff; color: black"
                elif isinstance(val, (int, float)):
                    if val >= 75:
                        return "background-color: #c7fdb7"
                    elif 0 <= val < 75:
                        return "background-color: #fdf8b7"
                    elif val < 0:
                        return "background-color: #f9c2c2"
                return ""

            dashboard = dashboard.round(1).sort_values("Scostamento %", ascending=True)

            st.dataframe(
                dashboard.style.format({"Scostamento %": lambda v: v if isinstance(v, str) else f"{v:.1f}%"}).applymap(color_dashboard),
                use_container_width=True
            )

    except Exception as e:
        st.error(f"Errore durante l'elaborazione: {type(e).__name__}: {e}")
