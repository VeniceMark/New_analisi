import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import calendar

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

def parse_budget(df_budget):
    clienti = df_budget.iloc[:, 0]
    mesi = [calendar.month_name[i] for i in range(1, 13)]
    records = []
    for idx, cliente in enumerate(clienti):
        for i, mese in enumerate(mesi):
            base = 1 + i * 5
            coeff = df_budget.iloc[idx, base]
            budget = df_budget.iloc[idx, base+1]
            extra  = df_budget.iloc[idx, base+2]
            records.append({
                "cliente": cliente,
                "mese_anno": f"{mese}-{datetime.today().year}",
                "coefficiente": coeff,
                "budget": budget,
                "extrabudget": extra
            })
    df = pd.DataFrame(records)
    df['mese_anno'] = pd.to_datetime(df['mese_anno'], format='%B-%Y').dt.to_period('M').astype(str)
    return df

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
    df_budget_raw = pd.read_excel(budget_file)
    df_eff = pd.read_excel(effettive_file)
    df_eff['data'] = pd.to_datetime(df_eff['data'])

    cliente_sel = st.sidebar.selectbox("Seleziona Cliente", ["Tutti"] + sorted(df_eff['cliente'].unique()))
    periodo = st.sidebar.radio("Periodo", ["1-15", "1-fine", "Tutti i giorni"])

    if cliente_sel != "Tutti":
        df_eff = df_eff[df_eff['cliente'] == cliente_sel]
    if periodo != "Tutti i giorni":
        df_eff = df_eff[df_eff['data'].apply(lambda d: get_period(d, periodo))]

    df_budget = parse_budget(df_budget_raw)
    df_eff['mese_anno'] = df_eff['data'].dt.to_period('M').astype(str)
    df_agg_eff = df_eff.groupby(['cliente', 'mese_anno'])['ore_lavorate'].sum().reset_index()

    df_merge = pd.merge(df_budget, df_agg_eff, on=['cliente', 'mese_anno'], how='outer').fillna(0)
    df_merge['slot'] = (df_merge['budget'] + df_merge['extrabudget']) / df_merge['coefficiente'].replace(0, np.nan)
    df_merge['scostamento_ore'] = df_merge['slot'] - df_merge['ore_lavorate']
    df_merge['%_scostamento'] = np.where(
        df_merge['slot'] == 0,
        np.where(df_merge['ore_lavorate'] == 0, 0, -999),
        ((df_merge['slot'] - df_merge['ore_lavorate']) / df_merge['slot']) * 100
    )

    df_total = df_merge.groupby('cliente').agg({'slot':'sum','ore_lavorate':'sum'}).reset_index()
    df_total['scostamento_totale'] = df_total['slot'] - df_total['ore_lavorate']
    df_total['%_totale'] = np.where(
        df_total['slot']==0,
        np.where(df_total['ore_lavorate']==0, 0, -999),
        ((df_total['slot'] - df_total['ore_lavorate']) / df_total['slot']) * 100
    )

    styled_tot = df_total.style.apply(
        lambda row: [color_percent(row['%_totale'], row['slot'], row['ore_lavorate']) if c=='%_totale' else '' for c in df_total.columns],
        axis=1
    ).format({'slot':'{:.2f}','ore_lavorate':'{:.2f}','scostamento_totale':'{:+.2f}','%_totale':'{:+.1f}%'})
    styled_det = df_merge.style.apply(
        lambda row: [color_percent(row['%_scostamento'], row['slot'], row['ore_lavorate']) if c=='%_scostamento' else '' for c in df_merge.columns],
        axis=1
    ).format({'budget':'{:.2f}','extrabudget':'{:.2f}','slot':'{:.2f}','ore_lavorate':'{:.2f}','scostamento_ore':'{:+.2f}','%_scostamento':'{:+.1f}%'})

    st.markdown("## Riepilogo per Cliente")
    st.dataframe(styled_tot, use_container_width=True)
    st.markdown("## Dettaglio Mensile")
    st.dataframe(styled_det, use_container_width=True)
else:
    st.warning("Carica entrambi i file per iniziare.")
