
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

            df_budget.columns = df_budget.columns.str.strip()
            df_budget = df_budget.set_index('cliente')
            df_budget.index = df_budget.index.astype(str)

            pattern = re.compile(r'\d{4}-\d{2} \((1-15|1-fine)\)')
            valid_cols = [col for col in df_budget.columns if pattern.match(col)]
            df_budget = df_budget[valid_cols]

            comuni = df_eff_tot.columns.intersection(df_budget.columns)
            if comuni.empty:
                st.error("Nessuna colonna in comune tra fogli Effettivo e Budget. Verifica le intestazioni.")
            else:
                eff = df_eff_tot[comuni].copy().fillna(0)
                budget = df_budget[comuni].copy().fillna(0)

                
                diff_percent = pd.DataFrame(index=budget.index.union(eff.index), columns=budget.columns.union(eff.columns), dtype=object)

                all_clients = diff_percent.index
                all_periods = diff_percent.columns

                for client in all_clients:
                    for period in all_periods:
                        b = budget.at[client, period] if client in budget.index and period in budget.columns else 0
                        e = eff.at[client, period] if client in eff.index and period in eff.columns else 0
                        if b > 0 and e > 0:
                            diff_percent.at[client, period] = round((b - e) / b * 100, 1)
                        elif b == 0 and e > 0:
                            diff_percent.at[client, period] = "extrabudget"
                        elif b > 0 and e == 0:
                            diff_percent.at[client, period] = 100
                        else:
                            diff_percent.at[client, period] = 0


                st.subheader("📈 Scostamento percentuale tra Budget e Ore Effettive (gradiente -50% ➜ +100%)")
                
                def highlight_extrabudget(val):
                    if val == "extrabudget":
                        return "background-color: mediumpurple; color: white"
                    elif isinstance(val, (int, float)):
                        return ""
                    return ""

                styled = diff_percent.style.applymap(highlight_extrabudget).format(
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
                opzioni = ["Totale complessivo"] + list(comuni.unique())
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

                df_plot = df_plot.sort_values("Effettivo", ascending=True)
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
                
                dashboard["Scostamento %"] = dashboard.apply(
                    lambda row: row["Ore Effettive"] if row["Ore a Budget"] == 0 and row["Ore Effettive"] > 0
                    else ((row["Ore a Budget"] - row["Ore Effettive"]) / row["Ore a Budget"] * 100)
                    if row["Ore a Budget"] > 0 else np.nan,
                    axis=1
                )
,
                    (dashboard["Ore a Budget"] - dashboard["Ore Effettive"]) / dashboard["Ore a Budget"] * 100
                )

                dashboard = dashboard.round(1).sort_values("Scostamento %", ascending=True)

                st.dataframe(
                    
                    dashboard.style.applymap(
                        lambda val: "background-color: mediumpurple; color: white" if isinstance(val, (int, float)) and val > 0 and dashboard.loc[dashboard["Scostamento %"] == val, "Ore a Budget"].values[0] == 0 else "",
                        subset=["Scostamento %"]
                    ).format({"Scostamento %": lambda x: f"{x:.1f}%" if isinstance(x, float) else x}).background_gradient(
                        cmap="RdYlGn", subset=["Scostamento %"], vmin=-50, vmax=100
                    )
,
                    use_container_width=True
                )

    except Exception as e:
        st.error(f"Errore durante l'elaborazione: {type(e).__name__}: {e}")
