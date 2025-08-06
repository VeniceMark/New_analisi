import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(layout="wide")

st.title("📊 Analisi Budget vs Effettivo")

# --- FUNZIONI DI SUPPORTO ---

@st.cache_data
def load_excel(file):
    return pd.read_excel(file, engine="openpyxl")

def normalizza_colonne(df):
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "")
    return df

def pulisci_effettive(df):
    df = normalizza_colonne(df)
    df = df[~df["cliente"].astype(str).str.lower().eq("cliente")]
    df = df.dropna(subset=["cliente", "data", "ore"])
    df["ore"] = pd.to_numeric(df["ore"], errors="coerce").fillna(0)
    df["data"] = df["data"].apply(parse_data_custom)
    df["giorno"] = df["data"].dt.day
    df["mese"] = df["data"].dt.strftime("%Y-%m")
    return df

def parse_data_custom(x):
    try:
        giorno, mese, anno = map(int, str(x).split("/"))
        if anno >= 25 and anno <= 99:
            anno += 1900 if anno > 39 else 2000
        return pd.to_datetime(f"{anno}-{mese:02d}-{giorno:02d}", errors="coerce")
    except:
        return pd.NaT

def crea_pivot_effettive(df_eff):
    df_15 = df_eff[df_eff["giorno"] <= 15].groupby(["cliente", "mese"])["ore"].sum().unstack().fillna(0)
    df_15.columns = [f"{col} (1-15)" for col in df_15.columns]
    df_fine = df_eff.groupby(["cliente", "mese"])["ore"].sum().unstack().fillna(0)
    df_fine.columns = [f"{col} (1-fine)" for col in df_fine.columns]
    df_eff_pivot = pd.concat([df_15, df_fine], axis=1).fillna(0)
    df_eff_pivot = df_eff_pivot.loc[:, sorted(df_eff_pivot.columns)]
    return df_eff_pivot

def pulisci_budget(df):
    df.columns = df.columns.astype(str)
    df = df.rename(columns={df.columns[0]: "cliente"})
    pattern = re.compile(r"^\d{4}-\d{2} \(1-(15|fine)\)$")
    valid_cols = [col for col in df.columns if col == "cliente" or pattern.match(col)]
    invalid_cols = [col for col in df.columns if col not in valid_cols]
    if invalid_cols:
        st.warning(f"⚠️ Colonne ignorate perché non compatibili: {invalid_cols}")
    if len(valid_cols) <= 1:
        st.warning("⚠️ Nessuna colonna valida trovata nel file Budget. Controlla i nomi delle colonne.")
    else:
        st.success(f"✅ Colonne accettate: {valid_cols[1:]}")
    return df[valid_cols]

    df.columns = df.columns.astype(str)
    df = df.rename(columns={df.columns[0]: "cliente"})
    pattern = re.compile(r"^\d{4}-\d{2} \(1-(15|fine)\)$")
    valid_cols = [col for col in df.columns if col == "cliente" or pattern.match(col)]
    return df[valid_cols]

def calcola_scostamenti(budget, effettivo):
    comuni = list(set(budget.columns).intersection(set(effettivo.columns)) - {"cliente"})
    budget_aligned = budget.set_index("cliente").reindex(columns=comuni).fillna(0)
    eff_aligned = effettivo.reindex(columns=comuni).fillna(0)
    clienti_comuni = sorted(set(budget["cliente"]) | set(effettivo.index))
    budget_aligned = budget_aligned.reindex(clienti_comuni, fill_value=0)
    eff_aligned = eff_aligned.reindex(clienti_comuni, fill_value=0)
    df_result = pd.DataFrame(index=clienti_comuni)
    for col in comuni:
        b = budget_aligned[col]
        e = eff_aligned[col]
        res = []
        for bi, ei in zip(b, e):
            if bi == 0 and ei > 0:
                res.append("extrabudget")
            elif bi == 0 and ei == 0:
                res.append("None")
            else:
                scost = round(((bi - ei) / bi) * 100, 1)
                res.append(scost)
        df_result[col] = res
    df_result.insert(0, "cliente", df_result.index)
    # Ordina le colonne per mese e tipo periodo
    col_periods = sorted(
        [col for col in df_result.columns if col != "cliente"],
        key=lambda x: (x.split(" ")[0], x.split(" ")[1])
    )
    df_result = df_result[["cliente"] + col_periods]
    return df_result

def tabella_riepilogo(budget, effettivo):
    # Seleziona solo le colonne (1-fine) che esistono in entrambi
    cols_fine = [col for col in budget.columns if "(1-fine)" in col and col in effettivo.columns]

    if not cols_fine:
        return pd.DataFrame({"Errore": ["Nessuna colonna (1-fine) disponibile per il confronto."]})

    cols_fine = [col for col in budget.columns if "(1-fine)" in col]
    budget_tot = budget.set_index("cliente")[cols_fine].sum(axis=1)
    effettivo_tot = effettivo[cols_fine].sum(axis=1)
    clienti = sorted(set(budget["cliente"]) | set(effettivo.index))
    budget_tot = budget_tot.reindex(clienti, fill_value=0)
    effettivo_tot = effettivo_tot.reindex(clienti, fill_value=0)
    diff = budget_tot - effettivo_tot
    scost = []
    for b, e in zip(budget_tot, effettivo_tot):
        if b == 0 and e > 0:
            scost.append("extrabudget")
        elif b == 0 and e == 0:
            scost.append("None")
        else:
            scost.append(round(((b - e) / b) * 100, 1))
    df_summary = pd.DataFrame({
        "Cliente": clienti,
        "Budget Totale": budget_tot,
        "Effettivo Totale": effettivo_tot,
        "Differenza (ore)": diff,
        "Scostamento %": scost
    })
    df_summary = df_summary.sort_values(by="Scostamento %", ascending=False, key=lambda x: pd.to_numeric(x, errors="coerce"))
    return df_summary

def style_scostamenti(df):
    def color(val):
        if val == "extrabudget":
            return "background-color: purple; color: white"
        elif val == "None":
            return "background-color: black; color: white"
        elif isinstance(val, (int, float, np.float64)):
            cmap = plt.cm.RdYlGn
            norm = plt.Normalize(-50, 100)
            rgba = cmap(norm(val))
            return f"background-color: rgba({int(rgba[0]*255)}, {int(rgba[1]*255)}, {int(rgba[2]*255)}, 0.6)"
        return ""
    return df.style.applymap(color, subset=df.columns[1:])

# --- UPLOAD FILE ---

file_budget = st.file_uploader("📥 Carica il file Budget (Budget_7_mesi.xlsx)", type=["xlsx"])
file_effettive = st.file_uploader("📥 Carica il file Effettive (Effettive_7_mesi.xlsx)", type=["xlsx"])

if file_budget and file_effettive:
    try:
        df_budget_raw = load_excel(file_budget)
        df_effettive_raw = load_excel(file_effettive)

        df_budget = pulisci_budget(df_budget_raw)
        df_effettive = pulisci_effettive(df_effettive_raw)

        # --- DEBUG: File Effettive prima della pivot ---
        st.subheader("📌 Debug: Dati Grezzi Effettive Dopo Pulizia")
        st.write(f"✅ Righe valide lette: {len(df_effettive)}")
        if df_effettive["data"].isna().all():
            st.error("❌ Tutti i valori della colonna 'data' sono NaT (errore nel parsing delle date).")
        else:
            st.success(f"✅ Colonna 'data' convertita con successo. Esempio formato: {df_effettive['data'].dropna().iloc[0]}")
        st.dataframe(df_effettive.head(20), use_container_width=True)

        df_effettivo_pivot = crea_pivot_effettive(df_effettive)

        # --- DEBUG: Visualizza la pivot delle effettive ---
        st.subheader("📌 Debug: Dati Effettivi Aggregati (Pivot)")
        if df_effettivo_pivot.empty:
            st.warning("⚠️ Nessun dato effettivo aggregabile trovato.")
        else:
            st.success(f"✅ Pivot Effettive generata con {df_effettivo_pivot.shape[0]} clienti e {df_effettivo_pivot.shape[1]} colonne.")
            st.dataframe(df_effettivo_pivot, use_container_width=True)

        df_scostamenti = calcola_scostamenti(df_budget, df_effettivo_pivot)
        df_riepilogo = tabella_riepilogo(df_budget, df_effettivo_pivot)

        # --- FILTRI ---
        clienti = ["Tutti"] + sorted(df_scostamenti["cliente"].unique())
        periodi = ["Tutti"] + [col for col in df_scostamenti.columns if col != "cliente"]

        col1, col2 = st.columns(2)
        cliente_sel = col1.selectbox("Filtra per cliente", clienti)
        periodo_sel = col2.selectbox("Filtra per periodo", periodi)

        df_filtered = df_scostamenti.copy()
        if cliente_sel != "Tutti":
            df_filtered = df_filtered[df_filtered["cliente"] == cliente_sel]
        if periodo_sel != "Tutti":
            cols = ["cliente", periodo_sel]
            df_filtered = df_filtered[cols]

        st.subheader("📅 Tabella A – Dettaglio Mensile")
        st.dataframe(style_scostamenti(df_filtered), use_container_width=True)

        st.subheader("🧮 Tabella B – Riepilogo Totale")
        def style_riepilogo(df):
    def highlight(val):
        if val == "extrabudget":
            return "background-color: purple; color: white"
        elif val == "None":
            return "background-color: black; color: white"
        elif isinstance(val, (int, float, np.float64)):
            cmap = plt.cm.RdYlGn
            norm = plt.Normalize(-50, 100)
            rgba = cmap(norm(val))
            return f"background-color: rgba({int(rgba[0]*255)}, {int(rgba[1]*255)}, {int(rgba[2]*255)}, 0.6)"
        return ""
    return df.style.applymap(highlight, subset=["Scostamento %"])

def style_riepilogo(df):
    def highlight(val):
        if val == "extrabudget":
            return "background-color: purple; color: white"
        elif val == "None":
            return "background-color: black; color: white"
        elif isinstance(val, (int, float, np.float64)):
            cmap = plt.cm.RdYlGn
            norm = plt.Normalize(-50, 100)
            rgba = cmap(norm(val))
            return f"background-color: rgba({int(rgba[0]*255)}, {int(rgba[1]*255)}, {int(rgba[2]*255)}, 0.6)"
        return ""
    return df.style.applymap(highlight, subset=["Scostamento %"])

st.dataframe(style_riepilogo(df_riepilogo), use_container_width=True)

    except Exception as e:
        st.error(f"Errore durante l'elaborazione: {str(e)}")
else:
    st.info("⚠️ Carica entrambi i file per avviare l’analisi.")
