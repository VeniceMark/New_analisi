import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Budget vs Effettivo", layout="wide")
st.title("📊 Analisi Budget vs Effettivo")

# ------------------------------
# FUNZIONI DI SUPPORTO
# ------------------------------

def get_time_block(date):
    """Restituisce il blocco temporale corrispondente alla data"""
    date = pd.to_datetime(date)
    month = date.strftime('%B').lower()
    if date.day <= 15:
        return f"budget 1-15 {month}"
    else:
        return f"budget 1-fine mese {month}"

# ------------------------------
# FORM A - BUDGET
# ------------------------------
st.header("📁 Form A: Caricamento Budget")

budget_file = st.file_uploader("Carica il file Excel del budget", type=["xlsx"], key="budget")

if budget_file:
    budget_df = pd.read_excel(budget_file)
    st.success("✅ Budget caricato correttamente")
    st.dataframe(budget_df, use_container_width=True)

# ------------------------------
# FORM B - EFFETTIVO
# ------------------------------
st.header("📁 Form B: Caricamento Effettivo")

effettivo_file = st.file_uploader("Carica il file Excel dell'effettivo", type=["xlsx"], key="effettivo")

if effettivo_file:
    effettivo_df = pd.read_excel(effettivo_file)
    
    # Controllo e parsing date
    effettivo_df['data'] = pd.to_datetime(effettivo_df['data'], errors='coerce')
    effettivo_df = effettivo_df.dropna(subset=['data'])

    effettivo_df['time_block'] = effettivo_df['data'].apply(get_time_block)
    
    st.success("✅ Dati effettivi caricati e processati")
    st.dataframe(effettivo_df, use_container_width=True)

    # --------------------------
    # PIVOT: Effettivo aggregato per cliente e blocco temporale
    # --------------------------
    pivot_eff = effettivo_df.pivot_table(
        index='nome cliente',
        columns='time_block',
        values='ore lavorate',
        aggfunc='sum',
        fill_value=0
    )

    st.subheader("🧮 Ore Effettive Aggregate")
    st.dataframe(pivot_eff, use_container_width=True)

    # --------------------------
    # CONFRONTO BUDGET vs EFFETTIVO
    # --------------------------
    if budget_file:
        st.subheader("📌 Confronto Budget vs Effettivo")

        # Estrazione delle colonne budget temporali
        time_block_cols = [col for col in budget_df.columns if col.startswith("budget ")]

        # Preparazione dati budget (melt)
        budget_melt = budget_df.melt(
            id_vars=["nome cliente"],
            value_vars=time_block_cols,
            var_name="time_block",
            value_name="ore_budget"
        )

        # Preparazione effettivo (melt)
        effettivo_melt = pivot_eff.reset_index().melt(
            id_vars=["nome cliente"],
            var_name="time_block",
            value_name="ore_effettive"
        )

        # Merge e calcolo scostamento
        confronto_df = pd.merge(budget_melt, effettivo_melt, on=["nome cliente", "time_block"], how="outer")
        confronto_df.fillna(0, inplace=True)

        confronto_df["scostamento_percentuale"] = np.where(
            confronto_df["ore_budget"] == 0,
            np.where(confronto_df["ore_effettive"] == 0, 0, 100),
            (confronto_df["ore_effettive"] - confronto_df["ore_budget"]) / confronto_df["ore_budget"] * 100
        )

        # Visualizzazione risultato
        st.dataframe(confronto_df, use_container_width=True)

        # Download confronto
        output = BytesIO()
        confronto_df.to_excel(output, index=False)
        st.download_button(
            label="📥 Scarica il confronto in Excel",
            data=output.getvalue(),
            file_name="confronto_budget_vs_effettivo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
``
