
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import calendar
import re

st.set_page_config(page_title="Analisi Budget vs Effettivo", layout="wide")

st.sidebar.title("⚙️ Caricamento Dati")
budget_file = st.sidebar.file_uploader("📊 Carica il file Budget (.xlsx)", type="xlsx")
effettive_file = st.sidebar.file_uploader("⏱️ Carica il file Ore Effettive (.xlsx)", type="xlsx")

def get_period(data, tipo):
    giorno = data.day
    if tipo == "1-15":
        return giorno <= 15
    elif tipo == "1-fine":
        return giorno >= 1
    else:
        return True

def extract_budget_structure(columns):
    pattern = r"(\d{4}-\d{2})_(coeff|budget_mensile|xselling)|(\d{4}-\d{2}) \((1-15|1-fine)\)"
    struttura = {}
    for col in columns:
        match = re.match(pattern, col)
        if match:
            if match.group(1):
                mese = match.group(1)
                campo = match.group(2)
                struttura.setdefault(mese, {})[campo] = col
            elif match.group(3):
                mese = match.group(3)
                tipo = match.group(4)
                key = f"slot_{tipo}"
                struttura.setdefault(mese, {})[key] = col
    return struttura

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

if budget_file and effettive_file:
    df_budget = pd.read_excel(budget_file)
    df_effettive = pd.read_excel(effettive_file)
    df_effettive['data'] = pd.to_datetime(df_effettive['data'])

    struttura_colonne = extract_budget_structure(df_budget.columns.tolist())
    if not struttura_colonne:
        st.error("❌ Il file budget non ha una struttura valida.")
        st.stop()

    cliente_selezionato = st.sidebar.selectbox("🧾 Seleziona Cliente", ["Tutti"] + sorted(df_effettive['cliente'].unique()))
    periodo = st.sidebar.radio("📅 Seleziona Periodo", ["1-15", "1-fine", "Tutti i giorni"])

    if cliente_selezionato != "Tutti":
        df_effettive = df_effettive[df_effettive['cliente'] == cliente_selezionato]
    if periodo != "Tutti i giorni":
        df_effettive = df_effettive[df_effettive['data'].apply(lambda d: get_period(d, periodo))]

    df_effettive['mese_anno'] = df_effettive['data'].dt.to_period('M').astype(str)
    df_agg_eff = df_effettive.groupby(['cliente', 'mese_anno'])['ore'].sum().reset_index()
    df_agg_eff.rename(columns={'ore': 'ore_lavorate'}, inplace=True)

    records = []
    for i, row in df_budget.iterrows():
        cliente = row['cliente']
        for mese, campi in struttura_colonne.items():
            coeff = row.get(campi.get('coeff'), 0)
            budget = row.get(campi.get('budget_mensile'), 0)
            xsel = row.get(campi.get('xselling'), 0)
            slot_col = campi.get(f"slot_{periodo}") if periodo != "Tutti i giorni" else None
            slot = row.get(slot_col, 0) if slot_col else 0
            records.append({
                'cliente': cliente,
                'mese_anno': mese,
                'coefficiente': coeff,
                'budget': budget,
                'xselling': xsel,
                'slot': slot
            })

    df_budget_expanded = pd.DataFrame(records)
    df_merge = pd.merge(df_budget_expanded, df_agg_eff, on=['cliente', 'mese_anno'], how='outer').fillna(0)
    df_merge['scostamento_ore'] = df_merge['slot'] - df_merge['ore_lavorate']
    df_merge['%_scostamento'] = np.where(
        df_merge['slot'] == 0,
        np.where(df_merge['ore_lavorate'] == 0, 0, -999),
        ((df_merge['slot'] - df_merge['ore_lavorate']) / df_merge['slot']) * 100
    )

    df_tot = df_merge.groupby('cliente').agg({'slot':'sum','ore_lavorate':'sum'}).reset_index()
    df_tot['scostamento_totale'] = df_tot['slot'] - df_tot['ore_lavorate']
    df_tot['%_totale'] = np.where(
        df_tot['slot'] == 0,
        np.where(df_tot['ore_lavorate'] == 0, 0, -999),
        ((df_tot['slot'] - df_tot['ore_lavorate']) / df_tot['slot']) * 100
    )

    styled_tot = df_tot.style.apply(
        lambda row: [color_percent(row['%_totale'], row['slot'], row['ore_lavorate']) if c=='%_totale' else '' for c in df_tot.columns],
        axis=1
    ).format({'slot':'{:.2f}','ore_lavorate':'{:.2f}','scostamento_totale':'{:+.2f}','%_totale':'{:+.1f}%'})

    styled_det = df_merge.style.apply(
        lambda row: [color_percent(row['%_scostamento'], row['slot'], row['ore_lavorate']) if c=='%_scostamento' else '' for c in df_merge.columns],
        axis=1
    ).format({'budget':'{:.2f}','xselling':'{:.2f}','slot':'{:.2f}','ore_lavorate':'{:.2f}','scostamento_ore':'{:+.2f}','%_scostamento':'{:+.1f}%'})

    st.markdown("## 📈 Riepilogo per Cliente")
    st.dataframe(styled_tot, use_container_width=True)

    st.markdown("## 📊 Dettaglio Mensile")
    st.dataframe(styled_det, use_container_width=True)

else:
    st.warning("📂 Carica entrambi i file per iniziare.")
