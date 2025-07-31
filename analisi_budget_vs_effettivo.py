
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import re

def calcola_scostamento(row):
    if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0:
        return row["Ore Effettive"]  # Extrabudget: valore assoluto
    elif row["Ore a Budget"] > 0:
        return (row["Ore a Budget"] - row["Ore Effettive"]) / row["Ore a Budget"] * 100
    else:
        return np.nan

def highlight_dashboard(val, row):
    if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0:
        return "background-color: mediumpurple; color: white"
    return ""

def highlight_gradient(val):
    if val == "extrabudget":
        return "background-color: mediumpurple; color: white"
    elif isinstance(val, (int, float)):
        # Gradiente solo per valori numerici
        if val < -50: return "background-color: #ff0000"
        elif val > 100: return "background-color: #00ff00"
        return ""
    return ""

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

            diff_percent = pd.DataFrame(index=all_idx, columns=all_cols, dtype=object)
            extrabudget_flags = pd.DataFrame(False, index=all_idx, columns=all_cols)

            for client in all_idx:
                for period in all_cols:
                    b = budget.at[client, period]
                    e = eff.at[client, period]
                    if b > 0 and e > 0:
                        diff_percent.at[client, period] = round((b - e) / b * 100, 1)
                    elif b == 0 and e > 0:
                        diff_percent.at[client, period] = "extrabudget"
                        extrabudget_flags.at[client, period] = True
                    elif b > 0 and e == 0:
                        diff_percent.at[client, period] = 100
                    else:
                        diff_percent.at[client, period] = 0

            st.subheader("📈 Scostamento percentuale tra Budget e Ore Effettive")
            styled = diff_percent.style.applymap(highlight_gradient).format(
                lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x
            )
            st.dataframe(styled, use_container_width=True)

            st.subheader("📋 Dati Dettagliati")
            df_view = pd.concat([eff, budget, diff_percent], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
            st.dataframe(df_view.round(1), use_container_width=True)

            buffer = io.BytesIO()
            diff_percent.to_excel(buffer, index=True, sheet_name='Scostamenti')
            st.download_button("📥 Scarica Scostamenti in Excel", data=buffer.getvalue(), file_name="scostamenti.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.subheader("📊 Grafico a barre: Budget vs Effettivo per clienti")
            opzioni = ["Totale complessivo"] + all_cols
            mese_selezionato = st.selectbox("Seleziona un mese o il totale", opzioni)

            if mese_selezionato == "Totale complessivo":
                eff_total = eff.sum(axis=1)
                budget_total = budget.sum(axis=1)
                extrabudget_total = eff.where(budget == 0, 0).sum(axis=1)
                eff_inbudget_total = eff_total - extrabudget_total
            else:
                eff_total = eff[mese_selezionato]
                budget_total = budget[mese_selezionato]
                extrabudget_total = eff[mese_selezionato].where(budget[mese_selezionato] == 0, 0)
                eff_inbudget_total = eff_total - extrabudget_total

            df_plot = pd.DataFrame({
                "Effettivo (In Budget)": eff_inbudget_total,
                "Effettivo (Extrabudget)": extrabudget_total,
                "Budget": budget_total
            }).fillna(0).sort_values("Effettivo (In Budget)", ascending=True)

            fig, ax = plt.subplots(figsize=(10, len(df_plot) * 0.4))
            df_plot[["Effettivo (In Budget)", "Effettivo (Extrabudget)"]].plot(
                kind="barh", stacked=True, ax=ax, color=["steelblue", "mediumpurple"], width=0.6
            )
            df_plot["Budget"].plot(kind="barh", ax=ax, color="gray", alpha=0.5, width=0.3, position=1)
            ax.set_xlabel("Ore")
            ax.set_ylabel("Cliente")
            ax.set_title(f"Confronto Ore - {mese_selezionato}")
            st.pyplot(fig)

            st.subheader("📊 Dashboard riepilogativa per cliente")
            dashboard = pd.DataFrame({
                "Ore Effettive": eff_total,
                "Ore a Budget": budget_total
            })
            dashboard["Scostamento %"] = dashboard.apply(calcola_scostamento, axis=1)

            def highlight_row(row):
                if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0:
                    return ["background-color: mediumpurple; color: white" if col == "Scostamento %" else "" for col in row.index]
                else:
                    return [""] * len(row)

            st.dataframe(
                dashboard.style.apply(highlight_row, axis=1).format(
                    {"Scostamento %": lambda x: f"{x:.1f}%" if isinstance(x, float) else x}
                ).background_gradient(
                    cmap="RdYlGn", subset=["Scostamento %"], vmin=-50, vmax=100
                ),
                use_container_width=True
            )

    except Exception as e:
        st.error(f"Errore durante l'elaborazione: {type(e).__name__}: {e}")
