import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re

# Configurazione della pagina
st.set_page_config(page_title="Budget vs Effettivo", layout="wide")
st.title("📊 Confronto Budget vs Effettivo - Ore Lavorate")

# --- 1. Caricamento dei file ---
st.header("📥 Caricamento dei file")

uploaded_budget = st.file_uploader("Carica il file Budget (Excel)", type=["xlsx"])
uploaded_effettivo = st.file_uploader("Carica il file Effettivo (Excel)", type=["xlsx"])

if not uploaded_budget or not uploaded_effettivo:
    st.info("Per favore carica entrambi i file Excel per procedere.")
    st.stop()

try:
    # Lettura dei file
    df_budget_raw = pd.read_excel(uploaded_budget)
    df_effettivo_raw = pd.read_excel(uploaded_effettivo)
except Exception as e:
    st.error(f"Errore nella lettura dei file Excel: {e}")
    st.stop()

# --- 2. Preprocessing: Effettivo ---
st.subheader("🔧 Preprocessing - Dati Effettivi")

def preprocess_effettivo(df):
    if df.empty:
        st.error("Il file Effettivo è vuoto.")
        st.stop()

    # Normalizzazione colonne
    df.columns = [str(col).strip().lower() for col in df.columns]
    required_cols = ['cliente', 'data', 'ore']
    if not all(col in df.columns for col in required_cols):
        st.error(f"Colonne richieste mancanti nel file Effettivo: {required_cols}")
        st.stop()

    df = df[required_cols].copy()

    # Pulizia: rimozione righe non valide
    df = df.dropna(subset=['cliente', 'data', 'ore'])
    df = df[df['cliente'].astype(str).str.lower() != 'cliente']  # Rimuovi intestazioni spurie
    df = df[df['cliente'].astype(str).str.strip() != '']  # Clienti vuoti

    # Conversione ore in numerico
    df['ore'] = pd.to_numeric(df['ore'], errors='coerce')
    df = df.dropna(subset=['ore'])

    # Parsing data: formato GG/MM/AA
    def parse_date(date_str):
        try:
            # Se è già datetime
            if isinstance(date_str, pd.Timestamp):
                return date_str
            # Converti a stringa
            date_str = str(date_str).strip()
            day, month, year = map(int, date_str.split('/'))
            # Gestione anno: 25-39 → 2025-2039, 00-24 → 2000-2024
            if 25 <= year <= 39:
                year = 2000 + year
            elif 0 <= year <= 24:
                year = 2000 + year
            else:
                return pd.NaT
            return pd.Timestamp(year=year, month=month, day=day)
        except:
            return pd.NaT

    df['data'] = df['data'].apply(parse_date)
    df = df.dropna(subset=['data'])

    # Estrazione mese e giorno
    df['mese'] = df['data'].dt.strftime('%Y-%m')  # '2025-01'
    df['giorno'] = df['data'].dt.day

    return df

df_effettivo = preprocess_effettivo(df_effettivo_raw)

# --- 3. Preprocessing: Budget ---
st.subheader("🔧 Preprocessing - Dati Budget")

def preprocess_budget(df):
    if df.empty:
        st.error("Il file Budget è vuoto.")
        st.stop()

    # Rinomina prima colonna come 'cliente'
    df.columns = [str(col).strip() for col in df.columns]
    df.rename(columns={df.columns[0]: 'cliente'}, inplace=True)

    # Identifica colonne con pattern YYYY-MM (1-15) o YYYY-MM (1-fine)
    pattern = r'^\d{4}-\d{2} \(1-(15|fine)\)$'
    relevant_cols = ['cliente'] + [col for col in df.columns[1:] if re.match(pattern, col)]

    if len(relevant_cols) <= 1:
        st.warning("Nessuna colonna di budget trovata con il formato corretto (es. 2025-01 (1-15)).")
        st.stop()

    df = df[relevant_cols].copy()

    # Converte le colonne numeriche (escludendo cliente)
    for col in df.columns[1:]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df

df_budget = preprocess_budget(df_budget_raw)

# --- 4. Creazione Pivot Effettivo ---
st.subheader("🔄 Creazione Pivot Effettivo")

def create_effettivo_pivot(df):
    # Filtra per periodo
    period_1_15 = df[df['giorno'] <= 15]
    period_1_fine = df.copy()  # Tutti i giorni

    # Crea pivot per 1-15
    pivot_1_15 = period_1_15.groupby(['cliente', 'mese'])['ore'].sum().reset_index()
    pivot_1_15 = pivot_1_15.pivot(index='cliente', columns='mese', values='ore').fillna(0)
    pivot_1_15 = pivot_1_15.add_suffix(' (1-15)')

    # Crea pivot per 1-fine
    pivot_1_fine = period_1_fine.groupby(['cliente', 'mese'])['ore'].sum().reset_index()
    pivot_1_fine = pivot_1_fine.pivot(index='cliente', columns='mese', values='ore').fillna(0)
    pivot_1_fine = pivot_1_fine.add_suffix(' (1-fine)')

    # Unisci i due pivot
    df_pivot = pd.concat([pivot_1_15, pivot_1_fine], axis=1)

    # Riordina colonne cronologicamente e per tipo
    months = sorted(df['mese'].unique())
    ordered_cols = []
    for month in months:
        if f"{month} (1-15)" in df_pivot.columns:
            ordered_cols.append(f"{month} (1-15)")
        if f"{month} (1-fine)" in df_pivot.columns:
            ordered_cols.append(f"{month} (1-fine)")
    df_pivot = df_pivot[ordered_cols]

    return df_pivot

df_effettivo_pivot = create_effettivo_pivot(df_effettivo)

# --- 5. Allineamento Budget ed Effettivo ---
st.subheader("🔗 Allineamento Budget ed Effettivo")

# Trova colonne comuni
common_cols = df_budget.columns[1:].intersection(df_effettivo_pivot.columns)
if len(common_cols) == 0:
    st.error("Nessuna colonna comune trovata tra Budget ed Effettivo.")
    st.stop()

# Seleziona solo colonne comuni
df_budget_filtered = df_budget[['cliente'] + list(common_cols)].set_index('cliente')
df_effettivo_filtered = df_effettivo_pivot[common_cols]

# Allinea clienti (riempie con 0 dove mancano)
all_clients = df_budget_filtered.index.union(df_effettivo_filtered.index)
df_budget_aligned = df_budget_filtered.reindex(all_clients, fill_value=0)
df_effettivo_aligned = df_effettivo_filtered.reindex(all_clients, fill_value=0)

# Ordina per cliente
df_budget_aligned = df_budget_aligned.sort_index()
df_effettivo_aligned = df_effettivo_aligned.sort_index()

# --- 6. Creazione Tabelle ---

# Tabella A: Dettaglio Mensile
st.subheader("📋 Tabella A: Dettaglio Mensile")

def calculate_scostamento_cell(budget, effettivo):
    if budget == 0 and effettivo > 0:
        return "extrabudget"
    elif budget == 0 and effettivo == 0:
        return "None"
    else:
        if budget == 0:
            return "None"
        scostamento = ((budget - effettivo) / budget) * 100
        return round(scostamento, 1)

# Crea DataFrame per Tabella A
table_a_data = []
for cliente in df_budget_aligned.index:
    row = {'cliente': cliente}
    for col in common_cols:
        budget_val = df_budget_aligned.loc[cliente, col]
        effettivo_val = df_effettivo_aligned.loc[cliente, col]
        row[col] = calculate_scostamento_cell(budget_val, effettivo_val)
    table_a_data.append(row)

df_table_a = pd.DataFrame(table_a_data).set_index('cliente')

# Tabella B: Riepilogo Totale
st.subheader("📋 Tabella B: Riepilogo Totale")

# Solo colonne (1-fine) per il totale
total_cols = [col for col in common_cols if "(1-fine)" in col]
df_budget_total = df_budget_aligned[total_cols].sum(axis=1)
df_effettivo_total = df_effettivo_aligned[total_cols].sum(axis=1)

table_b_data = []
for cliente in df_budget_aligned.index:
    budget_tot = df_budget_total[cliente]
    eff_tot = df_effettivo_total[cliente]

    diff_ore = budget_tot - eff_tot

    if budget_tot > 0:
        scostamento_pct = round(((budget_tot - eff_tot) / budget_tot) * 100, 1)
    elif budget_tot == 0 and eff_tot > 0:
        scostamento_pct = "extrabudget"
    else:
        scostamento_pct = "None"

    table_b_data.append({
        'Cliente': cliente,
        'Budget Totale': round(budget_tot, 2),
        'Effettivo Totale': round(eff_tot, 2),
        'Differenza (ore)': round(diff_ore, 2),
        'Scostamento %': scostamento_pct
    })

df_table_b = pd.DataFrame(table_b_data)

# Ordinamento: numerico discendente, extrabudget in fondo
df_table_b['Scostamento % Sort'] = pd.to_numeric(df_table_b['Scostamento %'], errors='coerce')
df_table_b = df_table_b.sort_values(
    by=['Scostamento % Sort', 'Scostamento %'],
    ascending=[False, True],
    key=lambda x: x.map(lambda v: -np.inf if v == "extrabudget" else v if isinstance(v, (int, float)) else np.inf)
).drop(columns=['Scostamento % Sort'])

# --- 7. Filtri Dinamici ---
st.subheader("🔍 Filtri")

col1, col2 = st.columns(2)

with col1:
    clienti_opzioni = ["Tutti"] + sorted(df_budget_aligned.index.unique().tolist())
    cliente_filtro = st.selectbox("Filtra per Cliente", options=clienti_opzioni)

with col2:
    periodi_opzioni = ["Tutti"] + sorted(common_cols.tolist())
    periodo_filtro = st.selectbox("Filtra per Periodo", options=periodi_opzioni)

# Applica filtri a Tabella A
df_table_a_display = df_table_a.copy().reset_index()

if cliente_filtro != "Tutti":
    df_table_a_display = df_table_a_display[df_table_a_display['cliente'] == cliente_filtro]

if periodo_filtro != "Tutti":
    df_table_a_display = df_table_a_display[['cliente', periodo_filtro]]

# Applica filtro a Tabella B
df_table_b_display = df_table_b.copy()
if cliente_filtro != "Tutti":
    df_table_b_display = df_table_b_display[df_table_b_display['Cliente'] == cliente_filtro]

# --- 8. Formattazione e Visualizzazione ---

# Funzione per colorare Tabella A
def style_table_a(s):
    if isinstance(s.iloc[0], str):
        if s.name == 'cliente':
            return [''] * len(s)
        return [
            'background-color: purple; color: white' if v == "extrabudget"
            else 'background-color: black; color: white' if v == "None"
            else ''
            for v in s
        ]
    else:
        # Gradiente per valori numerici
        return ['background-color: ' + get_gradient_color(v) for v in s]

def get_gradient_color(val):
    if not isinstance(val, (int, float)) or np.isnan(val):
        return ""
    # Normalizza tra -100 e +100 per mappatura rosso-verde
    val = max(min(val, 100), -100)
    norm_val = (val + 100) / 200  # 0 (rosso) -> 1 (verde)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("rg", ["red", "yellow", "green"])
    r, g, b, _ = cmap(norm_val)
    return f"rgb({int(r*255)}, {int(g*255)}, {int(b*255)})"

# Applica stile a Tabella A
styled_table_a = df_table_a_display.style.map(style_table_a)

# Visualizzazione tabelle
st.write("### 📊 Tabella A - Dettaglio Mensile (Scostamento %)")
st.dataframe(styled_table_a, use_container_width=True, height=400)

st.write("### 📊 Tabella B - Riepilogo Totale")
st.dataframe(df_table_b_display, use_container_width=True, height=400)

# --- 9. Download opzionale ---
st.download_button(
    label="📥 Scarica Tabella B come CSV",
    data=df_table_b.to_csv(index=False),
    file_name="riepilogo_totale.csv",
    mime="text/csv"
)