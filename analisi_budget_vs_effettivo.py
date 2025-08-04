
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re

st.set_page_config(page_title="Analisi Budget vs Effettivo", layout="wide")

st.sidebar.title("⚙️ Caricamento Dati")
budget_file = st.sidebar.file_uploader("📊 Carica il file Budget (.xlsx)", type="xlsx")
effettive_file = st.sidebar.file_uploader("⏱️ Carica il file Ore Effettive (.xlsx)", type="xlsx")

def color_percent(val, budget, effettive):
    if budget == 0 and effettive == 0:
        return 'background-color: black; color: white'
    elif budget == 0 and effettive > 0:
        return 'background-color: purple; color: white'
    else:
        val = max(-100, min(100, val))
        red = int(255 - (val + 100) * 255 / 200)
        green = int((val + 100) * 255 / 200)
        return f'background-color: rgb({red},{green},0); color: white'

def build_periodo_options(columns):
    pattern = r"(\d{4}-\d{2}) \((1-15|1-fine)\)"
    periodi = []
    for col in columns:
        match = re.match(pattern, col)
        if match:
            mese = match.group(1)
            tipo = match.group(2)
            mese_nome = pd.to_datetime(mese).strftime('%B')
            periodi.append((f"{mese_nome.capitalize()} {tipo}", col))
    periodi.sort(key=lambda x: (
        datetime.strptime(x[0].split()[0], "%B").month,
        0 if "1-15" in x[0] else 1
    ))
    periodi.append(("Tutti i mesi", "Tutti i mesi"))
    return periodi

if budget_file and effettive_file:
    df_budget = pd.read_excel(budget_file)
    df_effettive = pd.read_excel(effettive_file)
    df_effettive['data'] = pd.to_datetime(df_effettive['data'])

    # Costruzione filtri
    clienti = sorted(df_budget['cliente'].dropna().unique().tolist())
    cliente_sel = st.sidebar.selectbox("🎯 Cliente", ["Tutti"] + clienti)

    periodi_options = build_periodo_options(df_budget.columns)
    periodo_labels = [x[0] for x in periodi_options]
    periodo_dict = dict(periodi_options)
    periodo_sel = st.sidebar.selectbox("🗓️ Periodo", periodo_labels)
    col_budget_sel = periodo_dict[periodo_sel]

    df_effettive['mese_anno'] = df_effettive['data'].dt.to_period('M').astype(str)
    df_effettive['giorno'] = df_effettive['data'].dt.day

    # Aggregazione effettive per periodo
    if col_budget_sel != "Tutti i mesi":
        mese_match = re.match(r"(\d{4}-\d{2})", col_budget_sel).group(1)
        tipo = "1-15" if "1-15" in col_budget_sel else "1-fine"
        df_eff_sub = df_effettive[df_effettive['mese_anno'] == pd.to_datetime(mese_match).to_period('M').strftime('%Y-%m')]
        if tipo == "1-15":
            df_eff_sub = df_eff_sub[df_eff_sub['giorno'] <= 15]
    else:
        df_eff_sub = df_effettive.copy()

    df_agg_eff = df_eff_sub.groupby(['cliente', 'mese_anno'])['ore'].sum().reset_index()
    df_agg_eff.rename(columns={'ore': 'ore_lavorate'}, inplace=True)

    # Parsing file budget per estrarre colonna selezionata
    records = []
    for _, row in df_budget.iterrows():
        for col in df_budget.columns:
            match = re.match(r"(\d{4}-\d{2})_(coeff|budget_mensile|xselling)", col)
            if match:
                continue
            match = re.match(r"(\d{4}-\d{2}) \((1-15|1-fine)\)", col)
            if match:
                mese = match.group(1)
                tipo = match.group(2)
                if col_budget_sel != "Tutti i mesi" and col != col_budget_sel:
                    continue
                ore_budget = row.get(col, 0)
                records.append({
                    'cliente': row['cliente'],
                    'mese_anno': pd.to_datetime(mese).to_period('M').strftime('%Y-%m'),
                    'ore_budget': ore_budget
                })

    df_budget_expanded = pd.DataFrame(records)

    # Merge
    df_merge = pd.merge(df_budget_expanded, df_agg_eff, how='outer', on=['cliente', 'mese_anno']).fillna(0)
    if cliente_sel != "Tutti":
        df_merge = df_merge[df_merge['cliente'] == cliente_sel]

    df_merge['scostamento_ore'] = df_merge['ore_budget'] - df_merge['ore_lavorate']
    df_merge['%_scostamento'] = np.where(
        df_merge['ore_budget'] == 0,
        np.where(df_merge['ore_lavorate'] == 0, 0, -999),
        ((df_merge['ore_budget'] - df_merge['ore_lavorate']) / df_merge['ore_budget']) * 100
    )

    # Styling
    styled_det = df_merge.style.apply(
        lambda row: [color_percent(row['%_scostamento'], row['ore_budget'], row['ore_lavorate']) if c=='%_scostamento' else '' for c in df_merge.columns],
        axis=1
    ).format({
        'ore_budget': '{:.2f}',
        'ore_lavorate': '{:.2f}',
        'scostamento_ore': '{:+.2f}',
        '%_scostamento': '{:+.1f}%'
    })

    st.markdown("## 📊 Analisi Comparativa Budget vs Effettivo")
    st.dataframe(styled_det, use_container_width=True)

else:
    st.warning("📂 Carica entrambi i file per iniziare.")
