# app.py

import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# Configurazione della pagina
st.set_page_config(page_title="Analisi Budget vs Effettivo", layout="wide")

# Titolo dell'applicazione
st.title("Analisi Ore Budget vs Effettivo")

# --- Caricamento File ---
st.header("1. Caricamento Dati")

uploaded_budget_file = st.file_uploader("Carica il file Excel del Budget", type=["xlsx"])
uploaded_effettivo_file = st.file_uploader("Carica il file Excel dell'Effettivo", type=["xlsx"])

if uploaded_budget_file is not None and uploaded_effettivo_file is not None:
    try:
        with st.spinner("Elaborazione dei dati..."):
            # --- 1. CARICAMENTO E PRE-PROCESSING DEI DATI ---

            # Caricamento Budget (primo foglio disponibile)
            df_budget_raw = pd.read_excel(uploaded_budget_file, sheet_name=0)
            st.success(f"File Budget caricato: {uploaded_budget_file.name}")

            # Caricamento Effettivo (primo foglio disponibile)
            df_effettivo_raw = pd.read_excel(uploaded_effettivo_file, sheet_name=0)
            st.success(f"File Effettivo caricato: {uploaded_effettivo_file.name}")

            # --- Pre-processing Effettivo ---
            # Normalizzazione colonne
            df_effettivo_raw.columns = df_effettivo_raw.columns.str.strip().str.lower()

            # Pulizia iniziale: rimuovi righe dove cliente o data o ore sono NaN
            df_effettivo_clean = df_effettivo_raw.dropna(subset=['cliente', 'data', 'ore']).copy()
            
            # Rimuovi righe di intestazione spurie (es. cliente='cliente')
            # Assicurati che 'cliente' sia una stringa e 'ore' sia numerico
            df_effettivo_clean = df_effettivo_clean[
                (df_effettivo_clean['cliente'].astype(str).str.strip().str.lower() != 'cliente')
            ]
            
            # Converti la colonna 'ore' in numerico, forzando errori a NaN
            df_effettivo_clean['ore'] = pd.to_numeric(df_effettivo_clean['ore'], errors='coerce')
            # Rimuovi eventuali righe dove 'ore' è diventato NaN dopo la conversione
            df_effettivo_clean = df_effettivo_clean.dropna(subset=['ore'])

            # Gestione del formato data GG/MM/AA
            def parse_custom_date(date_str):
                try:
                    date_str = str(date_str).strip()
                    parts = date_str.split('/')
                    if len(parts) != 3:
                        return pd.NaT
                    day, month, year = map(int, parts)
                    if year < 100:
                        # Assumendo che gli anni 25-39 siano 2025-2039
                        # e 00-24 siano 2000-2024
                        if 25 <= year <= 99:
                            year += 1900 # Copre fino al 1999 se necessario, altrimenti modifica
                        else: # 00-24
                            year += 2000
                    return pd.Timestamp(year=year, month=month, day=day)
                except Exception:
                    return pd.NaT

            df_effettivo_clean['data'] = df_effettivo_clean['data'].apply(parse_custom_date)
            df_effettivo_clean = df_effettivo_clean.dropna(subset=['data'])

            df_effettivo_clean['mese_anno'] = df_effettivo_clean['data'].dt.to_period('M').astype(str)
            df_effettivo_clean['giorno'] = df_effettivo_clean['data'].dt.day

            # --- Creazione Pivot per Effettivo ---
            df_eff_1_15 = df_effettivo_clean[df_effettivo_clean['giorno'].between(1, 15)]
            df_eff_1_fine = df_effettivo_clean.copy() # Tutti i giorni del mese

            pivot_eff_1_15 = df_eff_1_15.groupby(['cliente', 'mese_anno'])['ore'].sum().reset_index()
            pivot_eff_1_fine = df_eff_1_fine.groupby(['cliente', 'mese_anno'])['ore'].sum().reset_index()

            # Rinomina colonne pivot per chiarezza
            pivot_eff_1_15.rename(columns={'ore': 'ore_eff_1_15'}, inplace=True)
            pivot_eff_1_fine.rename(columns={'ore': 'ore_eff_1_fine'}, inplace=True)

            # --- Pre-processing Budget ---
            df_budget_clean = df_budget_raw.copy()
            df_budget_clean.columns = df_budget_clean.columns.astype(str)
            # La prima colonna è il cliente
            cliente_col_name = df_budget_clean.columns[0]
            df_budget_clean.rename(columns={cliente_col_name: 'cliente'}, inplace=True)

            # Identificazione colonne di budget ore (formato 'YYYY-MM (1-15)' o 'YYYY-MM (1-fine)')
            ore_columns = [col for col in df_budget_clean.columns if re.match(r"^\d{4}-\d{2} \(1-(15|fine)\)$", col)]
            if not ore_columns:
                st.warning("Nessuna colonna di budget ore trovata nel formato 'YYYY-MM (1-15)' o 'YYYY-MM (1-fine)'. Verifica il file.")
                st.stop()

            # Creazione DataFrame con cliente e colonne ore
            df_budget_ore = df_budget_clean[['cliente'] + ore_columns].copy()
            
            # --- 2. LOGICHE DI ANALISI E CREAZIONE TABELLE ---

            # Creazione di un elenco unico di clienti e periodi
            clienti_budget = set(df_budget_ore['cliente'].dropna().unique())
            clienti_eff_1_15 = set(pivot_eff_1_15['cliente'].unique()) if not pivot_eff_1_15.empty else set()
            clienti_eff_1_fine = set(pivot_eff_1_fine['cliente'].unique()) if not pivot_eff_1_fine.empty else set()
            tutti_clienti = sorted(list(clienti_budget | clienti_eff_1_15 | clienti_eff_1_fine))

            periodi = sorted(list(set(col for col in ore_columns)))

            # Creazione dizionari per accesso rapido ai dati
            budget_dict = df_budget_ore.set_index('cliente').to_dict('index')
            
            # Gestisci il caso in cui i pivot siano vuoti
            eff_1_15_dict = {}
            eff_1_fine_dict = {}
            if not pivot_eff_1_15.empty:
                 eff_1_15_dict = pivot_eff_1_15.set_index(['cliente', 'mese_anno']).to_dict()['ore_eff_1_15']
            if not pivot_eff_1_fine.empty:
                 eff_1_fine_dict = pivot_eff_1_fine.set_index(['cliente', 'mese_anno']).to_dict()['ore_eff_1_fine']

            # --- Creazione Tabella A (Dettaglio Mensile) ---
            st.header("2. Tabella A: Dettaglio Mensile")

            table_a_data = []
            for cliente in tutti_clienti:
                row = {'cliente': cliente}
                for periodo in periodi:
                    # Recupero Budget
                    budget_val = budget_dict.get(cliente, {}).get(periodo, 0)

                    # Determina se il periodo è 1-15 o 1-fine per recuperare l'effettivo corretto
                    chiave_mese = periodo.split(' (')[0] # "2025-01 (1-15)" -> "2025-01"
                    
                    if "(1-15)" in periodo:
                        effettivo_val = eff_1_15_dict.get((cliente, chiave_mese), 0)
                    elif "(1-fine)" in periodo:
                        effettivo_val = eff_1_fine_dict.get((cliente, chiave_mese), 0)
                    else:
                        effettivo_val = 0

                    # Applicazione delle Regole
                    if budget_val == 0 and effettivo_val > 0:
                        valore_cella = "extrabudget"
                    elif budget_val == 0 and effettivo_val == 0:
                        valore_cella = "None"
                    elif budget_val > 0: # Effettivo >= 0 implicito
                        # Calcolo percentuale di scostamento
                        scostamento = ((budget_val - effettivo_val) / budget_val) * 100
                        valore_cella = scostamento
                    else:
                        valore_cella = "None" # Fallback

                    row[periodo] = valore_cella
                table_a_data.append(row)

            df_table_a = pd.DataFrame(table_a_data)

            # --- Creazione Tabella B (Riepilogo Totale) ---
            st.header("3. Tabella B: Riepilogo Totale")

            table_b_data = []
            for cliente in tutti_clienti:
                budget_cliente_dict = budget_dict.get(cliente, {})
                
                # Somma totale Budget
                tot_budget = sum(budget_cliente_dict.get(p, 0) for p in periodi)
                
                # Somma totale Effettivo
                # Sommiamo tutti gli effettivi totali mensili (1-fine) per il cliente
                tot_effettivo = pivot_eff_1_fine[pivot_eff_1_fine['cliente'] == cliente]['ore_eff_1_fine'].sum() if not pivot_eff_1_fine.empty else 0
                
                # Calcolo dello scostamento totale
                diff_budget_eff = tot_budget - tot_effettivo
                if tot_budget == 0:
                    if tot_effettivo > 0:
                        scostamento_tot_testo = "extrabudget"
                    else:
                        scostamento_tot_testo = "None"
                else:
                    scostamento_tot_percentuale = (diff_budget_eff / tot_budget) * 100
                    scostamento_tot_testo = scostamento_tot_percentuale

                table_b_data.append({
                    'cliente': cliente,
                    'Budget Totale': tot_budget,
                    'Effettivo Totale': tot_effettivo,
                    'Differenza (Bud - Eff)': diff_budget_eff,
                    'Scostamento %': scostamento_tot_testo
                })

            df_table_b = pd.DataFrame(table_b_data)

            # --- 3. VISUALIZZAZIONE CON FILTRI ---
            
            # --- Funzioni di Supporto per Colori ---
            def highlight_cells_table_a(val):
                """Applica colori alle celle della Tabella A."""
                style = ''
                if isinstance(val, str):
                    if val == "extrabudget":
                        style = 'background-color: #9370DB; color: white;'
                    elif val == "None":
                        style = 'background-color: black; color: white;'
                elif isinstance(val, (int, float)):
                    perc = np.clip(val, -100, 100)
                    norm = (perc + 100) / 200
                    red = int(255 * (1 - norm))
                    green = int(255 * norm)
                    blue = 0
                    style = f'background-color: rgb({red}, {green}, {blue}); color: black;'
                return style

            def highlight_cells_table_b(val, col_name):
                """Applica colori alle celle della Tabella B."""
                style = ''
                if col_name == 'Scostamento %':
                    if isinstance(val, str):
                        if val == "extrabudget":
                            style = 'background-color: #9370DB; color: white;'
                        elif val == "None":
                            style = 'background-color: black; color: white;'
                    elif isinstance(val, (int, float)):
                        perc = np.clip(val, -100, 100)
                        norm = (perc + 100) / 200
                        red = int(255 * (1 - norm))
                        green = int(255 * norm)
                        blue = 0
                        style = f'background-color: rgb({red}, {green}, {blue}); color: black;'
                return style

            # --- Filtri ---
            st.sidebar.header("Filtri")
            
            cliente_options = ["Tutti"] + list(tutti_clienti)
            selected_cliente = st.sidebar.selectbox("Seleziona un Cliente:", cliente_options)

            periodo_options = ["Tutti"] + periodi
            selected_periodo = st.sidebar.selectbox("Seleziona un Periodo:", periodo_options)

            # --- Applicazione Filtri e Visualizzazione ---
            
            # Tabella A con Filtri
            df_table_a_filtered = df_table_a.copy()
            if selected_cliente != "Tutti":
                df_table_a_filtered = df_table_a_filtered[df_table_a_filtered['cliente'] == selected_cliente]
            
            if selected_periodo != "Tutti":
                 # Seleziona solo la colonna del periodo scelto + cliente
                 df_table_a_filtered = df_table_a_filtered[['cliente', selected_periodo]]

            # Visualizzazione Tabella A con colori
            st.subheader("Tabella A - Dettaglio Mensile (con filtri)")
            st.dataframe(
                df_table_a_filtered.style.map(highlight_cells_table_a),
                height=600,
                use_container_width=True
            )

            # Tabella B con Filtro Cliente
            df_table_b_filtered = df_table_b.copy()
            if selected_cliente != "Tutti":
                df_table_b_filtered = df_table_b_filtered[df_table_b_filtered['cliente'] == selected_cliente]
                
            def _apply_styling_table_b(row):
                styles = []
                for col in row.index:
                    styles.append(highlight_cells_table_b(row[col], col))
                return pd.Series(styles, index=row.index)

            # Visualizzazione Tabella B con colori
            st.subheader("Tabella B - Riepilogo Totale (con filtro cliente)")
            st.dataframe(
                df_table_b_filtered.style.apply(_apply_styling_table_b, axis=1),
                height=400,
                use_container_width=True
            )

            # --- Download DataFrames ---
            st.sidebar.header("Download Dati")
            st.sidebar.download_button(
                label="Scarica Tabella A (CSV)",
                data=df_table_a.to_csv(index=False),
                file_name="tabella_a_budget_effettivo.csv",
                mime="text/csv",
            )

            st.sidebar.download_button(
                label="Scarica Tabella B (CSV)",
                data=df_table_b.to_csv(index=False),
                file_name="tabella_b_budget_effettivo.csv",
                mime="text/csv",
            )

    except Exception as e:
        st.error(f"Si è verificato un errore durante l'elaborazione: {e}")
        st.exception(e) # Per debugging
else:
    st.info("Per favore, carica entrambi i file Excel: Budget e Effettivo.")
