
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

if sezione == "📈 Analisi Scostamenti":
    st.header("📈 Analisi Scostamenti Budget vs Effettivo")

    uploaded_eff = st.file_uploader("📥 Carica file 'Effettivo'", type=["xlsx"])
    uploaded_budget = st.file_uploader("📥 Carica file 'Budget'", type=["xlsx"])
    if uploaded_eff and uploaded_budget:
        try:
            df_eff = pd.read_excel(uploaded_eff, sheet_name='Effettivo')
            df_eff.columns = df_eff.columns.str.lower().str.strip()
            df_eff["data"] = pd.to_datetime(df_eff["data"], dayfirst=True)
            df_eff["mese"] = df_eff["data"].dt.to_period("M").astype(str)
            df_eff["giorno"] = df_eff["data"].dt.day

            df_budget = pd.read_excel(uploaded_budget)
            df_budget = df_budget.set_index("cliente")

            pivot_1_15 = df_eff[df_eff["giorno"] <= 15].pivot_table(index="cliente", columns="mese", values="ore", aggfunc="sum", fill_value=0)
            pivot_1_15.columns = [f"{col} (1-15)" for col in pivot_1_15.columns]

            pivot_1_fine = df_eff.pivot_table(index="cliente", columns="mese", values="ore", aggfunc="sum", fill_value=0)
            pivot_1_fine.columns = [f"{col} (1-fine)" for col in pivot_1_fine.columns]

            df_eff_tot = pd.concat([pivot_1_15, pivot_1_fine], axis=1).fillna(0)
            df_eff_tot = df_eff_tot.reindex(sorted(df_eff_tot.columns), axis=1)

            colonne_comuni = df_eff_tot.columns.intersection(df_budget.columns)
            clienti_comuni = df_eff_tot.index.union(df_budget.index)

            eff = df_eff_tot.reindex(index=clienti_comuni, columns=colonne_comuni, fill_value=0)
            budget = df_budget.reindex(index=clienti_comuni, columns=colonne_comuni, fill_value=0)

            diff_numeric = pd.DataFrame(index=budget.index, columns=budget.columns, dtype=float)
            for col in colonne_comuni:
                diff_numeric[col] = np.where(
                    (budget[col] == 0) & (eff[col] > 0), -9999,
                    np.where((budget[col] == 0) & (eff[col] == 0), -8888,
                    ((budget[col] - eff[col]) / budget[col] * 100).round(1))
                )

            tabella_unificata = pd.DataFrame(index=eff.index)
            for col in colonne_comuni:
                tabella_unificata[(col, "Effettivo")] = eff[col]
                tabella_unificata[(col, "Budget")] = budget[col]
                tabella_unificata[(col, "Scostamento %")] = diff_numeric[col]

            tot_eff = eff.sum(axis=1)
            tot_budget = budget.sum(axis=1)

            scostamento_str = []
            for idx in eff.index:
                beff = tot_eff.loc[idx]
                bbud = tot_budget.loc[idx]
                if bbud == 0 and beff == 0:
                    scostamento_str.append("None")
                elif bbud == 0 and beff > 0:
                    scostamento_str.append("Extrabudget")
                else:
                    perc = ((bbud - beff) / bbud * 100).round(1)
                    scostamento_str.append(f"{perc:.1f}%")

            tabella_unificata[("Totale", "Diff Ore")] = tot_budget - tot_eff
            tabella_unificata[("Totale", "% Totale")] = scostamento_str
            tabella_unificata.columns = pd.MultiIndex.from_tuples(tabella_unificata.columns)
            tabella_unificata = tabella_unificata.sort_index(axis=1, level=0)

            def colori_scostamenti(val):
                if val == "Extrabudget":
                    return "background-color: violet; color: white;"
                elif val == "None":
                    return "background-color: black; color: white;"
                try:
                    v = float(val.replace('%', ''))
                    norm = (v + 50) / 150
                    color = plt.cm.RdYlGn(norm)
                    return f"background-color: {matplotlib.colors.rgb2hex(color)}"
                except:
                    return ""

            styled = tabella_unificata.style.applymap(colori_scostamenti, subset=pd.IndexSlice[:, pd.IndexSlice[:, "Scostamento %"]])
            styled = styled.applymap(colori_scostamenti, subset=pd.IndexSlice[:, pd.IndexSlice["Totale", "% Totale"]])
            st.dataframe(styled, use_container_width=True)

        except Exception as e:
            st.error(f"Errore: {e}")
