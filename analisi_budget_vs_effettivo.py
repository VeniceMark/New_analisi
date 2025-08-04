
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re

st.set_page_config(page_title="Analisi Budget vs Effettivo", layout="wide")

st.sidebar.title("⚙️ Caricamento Dati")
budget_file = st.sidebar.file_uploader("📊 Carica il file Budget (.xlsx)", type="xlsx")
effettive_file = st.sidebar.file_uploader("⏱️ Carica il file Ore Effettive (.xlsx)", type="xlsx")

mesi_ita = {
    "01": "Gennaio", "02": "Febbraio", "03": "Marzo",
    "04": "Aprile", "05": "Maggio", "06": "Giugno",
    "07": "Luglio", "08": "Agosto", "09": "Settembre",
    "10": "Ottobre", "11": "Novembre", "12": "Dicembre"
}

def build_periodo_options_it(columns):
    pattern = r"(\d{4})-(\d{2}) \((1-15|1-fine)\)"
    periodi = []
    for col in columns:
        match = re.match(pattern, col)
        if match:
            anno, mese, blocco = match.groups()
            nome_mese = mesi_ita.get(mese, mese)
            etichetta = f"{nome_mese} {blocco}"
            periodi.append((etichetta, col))
    periodi.sort(key=lambda x: (
        list(mesi_ita.values()).index(x[0].split()[0]),
        0 if "1-15" in x[0] else 1
    ))
    periodi.append(("Tutti i mesi", "Tutti i mesi"))
    return periodi

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

    clienti = sorted(df_budget['cliente'].dropna().unique().tolist())
    cliente_sel = st.sidebar.selectbox("🎯 Cliente", ["Tutti"] + clienti)

    periodi_options = build_periodo_options_it(df_budget.columns)
    periodo_labels = [x[0] for x in periodi_options]
    periodo_dict = dict(periodi_options)
    periodo_sel = st.sidebar.selectbox("🗓️ Periodo", periodo_labels)
    col_budget_sel = periodo_dict[periodo_sel]

    df_effettive['mese_anno'] = df_effettive['data'].dt.to_period('M').astype(str)
    df_effettive['giorno'] = df_effettive['data'].dt.day

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

    records = []
    for _, row in df_budget.iterrows():
        for col in df_budget.columns:
            match = re.match(r"(\d{4}-\d{2}) \((1-15|1-fine)\)", col)
            if match:
                mese = match.group(1)
                tipo = match.group(2)
                if col_budget_sel != "Tutti i mesi" and col != col_budget_sel:
                    continue
                if col_budget_sel == "Tutti i mesi" and tipo != "1-fine":
                    continue
                ore_budget = row.get(col, 0)
                records.append({
                    'cliente': row['cliente'],
                    'mese_anno': pd.to_datetime(mese).to_period('M').strftime('%Y-%m'),
                    'ore_budget': ore_budget
                })

    df_budget_expanded = pd.DataFrame(records)
    df_merge = pd.merge(df_budget_expanded, df_agg_eff, how='outer', on=['cliente', 'mese_anno']).fillna(0)

    if cliente_sel != "Tutti":
        df_merge = df_merge[df_merge['cliente'] == cliente_sel]

    df_merge['scostamento_ore'] = df_merge['ore_budget'] - df_merge['ore_lavorate']
    df_merge['%_scostamento'] = np.where(
        df_merge['ore_budget'] == 0,
        np.where(df_merge['ore_lavorate'] == 0, 0, -999),
        ((df_merge['ore_budget'] - df_merge['ore_lavorate']) / df_merge['ore_budget']) * 100
    )

    df_tot = df_merge.groupby('cliente').agg({'ore_budget':'sum','ore_lavorate':'sum'}).reset_index()
    df_tot['scostamento_totale'] = df_tot['ore_budget'] - df_tot['ore_lavorate']
    df_tot['%_totale'] = np.where(
        df_tot['ore_budget'] == 0,
        np.where(df_tot['ore_lavorate'] == 0, 0, -999),
        ((df_tot['ore_budget'] - df_tot['ore_lavorate']) / df_tot['ore_budget']) * 100
    )

    styled_tot = df_tot.style.apply(
        lambda row: [color_percent(row['%_totale'], row['ore_budget'], row['ore_lavorate']) if c=='%_totale' else '' for c in df_tot.columns],
        axis=1
    ).format({'ore_budget':'{:.2f}','ore_lavorate':'{:.2f}','scostamento_totale':'{:+.2f}','%_totale':'{:+.1f}%'})

    styled_det = df_merge.style.apply(
        lambda row: [color_percent(row['%_scostamento'], row['ore_budget'], row['ore_lavorate']) if c=='%_scostamento' else '' for c in df_merge.columns],
        axis=1
    ).format({'ore_budget':'{:.2f}','ore_lavorate':'{:.2f}','scostamento_ore':'{:+.2f}','%_scostamento':'{:+.1f}%'})

    st.markdown("## 📈 Riepilogo per Cliente")
    st.dataframe(styled_tot, use_container_width=True)

    st.markdown("## 📊 Dettaglio Mensile")
    st.dataframe(styled_det, use_container_width=True)

else:
    st.warning("📂 Carica entrambi i file per iniziare.")
# --- COSTRUZIONE DETTAGLIO CLIENTE ---
    colonne_budget = [c for c in df_budget.columns if re.match(r"(\d{4}-\d{2}) \((1-15|1-fine)\)", c)]

    tabella_dettaglio = []

    for cliente in df_budget['cliente'].dropna().unique():
        riga = {'cliente': cliente}
        ore_budget_tot = 0
        ore_effettive_tot = 0
        for col in colonne_budget:
            match = re.match(r"(\d{4})-(\d{2}) \((1-15|1-fine)\)", col)
            if not match:
                continue
            anno, mese, blocco = match.groups()
            mese_nome = mesi_abbr[mese]
            label_col = f"{mese_nome} {blocco}"

            ore_bud = df_budget[df_budget['cliente'] == cliente][col].values[0]
            mese_rif = f"{anno}-{mese}"
            if blocco == "1-15":
                eff_sub = df_effettive[
                    (df_effettive['cliente'] == cliente) &
                    (df_effettive['mese_anno'] == mese_rif) &
                    (df_effettive['giorno'] <= 15)
                ]
            else:
                eff_sub = df_effettive[
                    (df_effettive['cliente'] == cliente) &
                    (df_effettive['mese_anno'] == mese_rif)
                ]
            ore_eff = eff_sub['ore'].sum()

            ore_budget_tot += ore_bud
            ore_effettive_tot += ore_eff

            if ore_bud == 0 and ore_eff == 0:
                val = 0
            elif ore_bud == 0 and ore_eff > 0:
                val = -999
            else:
                val = round((ore_bud - ore_eff) / ore_bud * 100, 1)

            riga[label_col] = val

        if ore_budget_tot == 0 and ore_effettive_tot == 0:
            tot = 0
        elif ore_budget_tot == 0 and ore_effettive_tot > 0:
            tot = -999
        else:
            tot = round((ore_budget_tot - ore_effettive_tot) / ore_budget_tot * 100, 1)

        riga["Totale"] = tot
        tabella_dettaglio.append(riga)

    df_dettaglio_cliente = pd.DataFrame(tabella_dettaglio)
    df_dettaglio_cliente = df_dettaglio_cliente.fillna(0)

    def style_dettaglio(val):
        if val == -999:
            return 'background-color: purple; color: white'
        elif val == 0:
            return 'background-color: black; color: white'
        else:
            val = max(-100, min(100, val))
            red = int(255 - (val + 100) * 255 / 200)
            green = int((val + 100) * 255 / 200)
            return f'background-color: rgb({red},{green},0); color: white'

    styled_cliente = df_dettaglio_cliente.style.applymap(style_dettaglio, subset=df_dettaglio_cliente.columns[1:]).format("{:+.1f}%")

    st.markdown("## 🧾 Dettaglio Cliente per Periodo")
    st.dataframe(styled_cliente, use_container_width=True)
