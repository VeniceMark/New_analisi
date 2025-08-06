# app.py

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import re
from datetime import datetime
from io import BytesIO

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

            # Caricamento Effettivo (foglio 'Effettivo')
            df_effettivo_raw = pd.read_excel(uploaded_effettivo_file, sheet_name="Effettivo")
            st.success(f"File Effettivo caricato: {uploaded_effettivo_file.name}")

            # --- Pre-processing Effettivo ---
            # Normalizzazione colonne
            df_effettivo_raw.columns = df_effettivo_raw.columns.str.strip().str.lower()

            # Pulizia iniziale: rimuovi righe dove cliente o data o ore sono NaN
            df_effettivo_clean = df_effettivo_raw.dropna(subset=['cliente', 'data', 'ore']).copy()
            
            # Rimuovi righe di intestazione spurie (es. cliente='cliente')
            df_effettivo_clean = df_effettivo_clean[
                (df_effettivo_clean['cliente'].astype(str).str.strip().str.lower() != 'cliente')
            ]
            
            # Converti la colonna 'ore' in numerico, forzando errori a NaN
            df_effettivo_clean['ore'] = pd.to_numeric(df_effettivo_clean['ore'], errors='coerce')
            # Rimuovi eventuali righe dove 'ore' è diventato NaN dopo la conversione
            df_effettivo_clean = df_effettivo_clean.dropna(subset=['ore'])

            # Gestione del formato data DD/MM/YY
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
                            year += 1900 # Copre fino al 1999 se necessario
                        else: # 00-24
                            year += 2000
                    return pd.Timestamp(year=year, month=month, day=day)
                except Exception:
                    return pd.NaT

            df_effettivo_clean['data'] = df_effettivo_clean['data'].apply(parse_custom_date)
            df_effettivo_clean = df_effettivo_clean.dropna(subset=['data'])

            # Creazione della colonna 'mese' nel formato 'YYYY-MM'
            df_effettivo_clean['mese'] = df_effettivo_clean['data'].dt.to_period('M').astype(str)
            df_effettivo_clean['giorno'] = df_effettivo_clean['data'].dt.day

            # --- Creazione Pivot per Effettivo ---
            # Pivot per periodo 1-15
            df_eff_1_15 = df_effettivo_clean[df_effettivo_clean['giorno'].between(1, 15)]
            pivot_eff_1_15 = df_eff_1_15.pivot_table(
                index='cliente', 
                columns='mese', 
                values='ore', 
                aggfunc='sum', 
                fill_value=0
            )
            # Rinomina le colonne per il periodo 1-15
            pivot_eff_1_15.columns = [f"{col} (1-15)" for col in pivot_eff_1_15.columns]

            # Pivot per periodo 1-fine
            df_eff_1_fine = df_effettivo_clean.copy()
            pivot_eff_1_fine = df_eff_1_fine.pivot_table(
                index='cliente', 
                columns='mese', 
                values='ore', 
                aggfunc='sum', 
                fill_value=0
            )
            # Rinomina le colonne per il periodo 1-fine
            pivot_eff_1_fine.columns = [f"{col} (1-fine)" for col in pivot_eff_1_fine.columns]

            # Concatenazione dei due pivot in un unico DataFrame
            df_effettivo_finale = pd.concat([pivot_eff_1_15, pivot_eff_1_fine], axis=1).fillna(0)
            # Ordina le colonne
            df_effettivo_finale = df_effettivo_finale.reindex(sorted(df_effettivo_finale.columns), axis=1)
            # Assicura che l'indice sia di tipo stringa
            df_effettivo_finale.index = df_effettivo_finale.index.astype(str)

            # --- Pre-processing Budget ---
            df_budget_clean = df_budget_raw.copy()
            df_budget_clean.columns = df_budget_clean.columns.astype(str)
            # La prima colonna è il cliente
            cliente_col_name = df_budget_clean.columns[0]
            df_budget_clean.rename(columns={cliente_col_name: 'cliente'}, inplace=True)
            
            # Imposta 'cliente' come indice
            df_budget_finale = df_budget_clean.set_index("cliente").fillna(0)
            
            # Identificazione colonne di budget ore (formato 'YYYY-MM (1-15)' o 'YYYY-MM (1-fine)')
            pattern = re.compile(r"^\d{4}-\d{2} \(1-(15|fine)\)$")
            colonne_budget_ore = [col for col in df_budget_finale.columns if pattern.match(col)]
            
            if not colonne_budget_ore:
                st.warning("Nessuna colonna di budget ore trovata nel formato 'YYYY-MM (1-15)' o 'YYYY-MM (1-fine)'. Verifica il file.")
                st.stop()

            # --- 2. LOGICHE DI ANALISI E CREAZIONE TABELLE ---
            
            # Trova le colonne comuni tra budget e effettivo
            colonne_comuni = df_effettivo_finale.columns.intersection(colonne_budget_ore)
            
            # Riallinea i DataFrame sulle colonne comuni e sugli stessi clienti
            df_eff_aligned = df_effettivo_finale.reindex(index=df_budget_finale.index, columns=colonne_comuni, fill_value=0)
            df_budget_aligned = df_budget_finale.reindex(index=df_budget_finale.index, columns=colonne_comuni, fill_value=0)

            # --- Creazione Tabella A (Dettaglio Mensile) ---
            st.header("2. Tabella A: Dettaglio Mensile")

            # Creazione del DataFrame per la tabella A con le regole di business
            df_table_a = pd.DataFrame(index=df_budget_aligned.index, columns=df_budget_aligned.columns, dtype=object)

            for col in colonne_comuni:
                df_table_a[col] = np.where(
                    (df_budget_aligned[col] == 0) & (df_eff_aligned[col] > 0), 
                    "extrabudget",
                    np.where(
                        (df_budget_aligned[col] == 0) & (df_eff_aligned[col] == 0), 
                        "None",
                        ((df_budget_aligned[col] - df_eff_aligned[col]) / df_budget_aligned[col] * 100).round(1)
                    )
                )

            # --- Funzioni di Supporto per Colori ---
            def highlight_cells_table_a(val):
                """Applica colori alle celle della Tabella A."""
                style = ''
                if isinstance(val, str):
                    if val == "extrabudget":
                        style = 'background-color: #9370DB; color: white;' # Viola
                    elif val == "None":
                        style = 'background-color: black; color: white;' # Nero
                elif isinstance(val, (int, float)):
                    # Limitiamo il range per il colore tra -100% e 100%
                    # Ma per una visualizzazione più equilibrata, usiamo -50% a +50% come range centrale
                    # e mappiamo -100% a 100% al range 0-1
                    val_clipped = np.clip(val, -100, 100)
                    # Normalizzazione: da -100/100 a 0/1
                    norm = (val_clipped + 100) / 200 
                    # Usa la colormap RdYlGn di matplotlib
                    color = plt.cm.RdYlGn(norm)
                    hex_color = matplotlib.colors.rgb2hex(color)
                    style = f'background-color: {hex_color}; color: black;'
                return style

            # --- Filtri ---
            st.sidebar.header("Filtri")
            
            # Filtro Cliente
            cliente_options = ["Tutti"] + list(df_table_a.index)
            selected_cliente = st.sidebar.selectbox("Seleziona un Cliente:", cliente_options)

            # Filtro Periodo
            periodo_options = ["Tutti"] + list(df_table_a.columns)
            selected_periodo = st.sidebar.selectbox("Seleziona un Periodo:", periodo_options)

            # --- Applicazione Filtri e Visualizzazione Tabella A ---
            df_table_a_filtered = df_table_a.copy()
            
            if selected_cliente != "Tutti":
                df_table_a_filtered = df_table_a_filtered[df_table_a_filtered.index == selected_cliente]
            
            if selected_periodo != "Tutti":
                 # Seleziona solo la colonna del periodo scelto + cliente
                 df_table_a_filtered = df_table_a_filtered[[selected_periodo]]
                 # Aggiungi la colonna cliente per identificazione
                 df_table_a_filtered.insert(0, 'cliente', df_table_a_filtered.index)

            # Visualizzazione Tabella A con colori
            st.subheader("Tabella A - Dettaglio Mensile (con filtri)")
            st.dataframe(
                df_table_a_filtered.style.map(highlight_cells_table_a),
                height=600,
                use_container_width=True
            )

            # --- Creazione Tabella B (Riepilogo Totale) ---
            st.header("3. Tabella B: Riepilogo Totale")

            # Identifica le colonne "(1-fine)" per il calcolo del totale
            colonne_budget_fine = [col for col in df_budget_aligned.columns if "(1-fine)" in col]
            colonne_effettivo_fine = [col for col in df_eff_aligned.columns if "(1-fine)" in col]

            # Creazione del DataFrame per la tabella B
            table_b_data = []
            for cliente in df_table_a.index:
                # Somma totale Budget ed Effettivo (solo periodi 1-fine)
                tot_budget = df_budget_aligned.loc[cliente, colonne_budget_fine].sum() if colonne_budget_fine else 0
                tot_effettivo = df_eff_aligned.loc[cliente, colonne_effettivo_fine].sum() if colonne_effettivo_fine else 0
                
                # Calcolo dello scostamento totale
                diff_budget_eff = tot_budget - tot_effettivo
                
                if tot_budget == 0:
                    if tot_effettivo > 0:
                        scostamento_tot_testo = "extrabudget"
                    else:
                        scostamento_tot_testo = "None"
                    scostamento_tot_num = np.nan # Per il colore, se necessario
                else:
                    scostamento_tot_num = (diff_budget_eff / tot_budget * 100)
                    scostamento_tot_testo = scostamento_tot_num # Per la visualizzazione numerica

                table_b_data.append({
                    'cliente': cliente,
                    'Budget Totale': round(tot_budget, 2),
                    'Effettivo Totale': round(tot_effettivo, 2),
                    'Differenza (Bud - Eff)': round(diff_budget_eff, 2),
                    'Scostamento %': scostamento_tot_testo # Può essere str o float
                })

            df_table_b = pd.DataFrame(table_b_data)
            df_table_b.set_index('cliente', inplace=True)

            def highlight_cells_table_b(val, col_name):
                """Applica colori alle celle della Tabella B."""
                style = ''
                if col_name == 'Scostamento %':
                    if isinstance(val, str): # "extrabudget" o "None"
                        if val == "extrabudget":
                            style = 'background-color: #9370DB; color: white;'
                        elif val == "None":
                            style = 'background-color: black; color: white;'
                    elif isinstance(val, (int, float)): # Percentuale
                        val_clipped = np.clip(val, -100, 100)
                        norm = (val_clipped + 100) / 200
                        color = plt.cm.RdYlGn(norm)
                        hex_color = matplotlib.colors.rgb2hex(color)
                        style = f'background-color: {hex_color}; color: black;'
                return style

            # Applicazione Filtro Cliente per Tabella B
            df_table_b_filtered = df_table_b.copy()
            if selected_cliente != "Tutti":
                df_table_b_filtered = df_table_b_filtered[df_table_b_filtered.index == selected_cliente]
            
            # Funzione di styling per Tabella B
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
            
            # Reset index per il download CSV
            df_download_a = df_table_a.copy()
            df_download_a.reset_index(inplace=True)
            df_download_b = df_table_b.copy()
            df_download_b.reset_index(inplace=True)
            
            st.sidebar.download_button(
                label="Scarica Tabella A (CSV)",
                data=df_download_a.to_csv(index=False),
                file_name="tabella_a_budget_effettivo.csv",
                mime="text/csv",
            )

            st.sidebar.download_button(
                label="Scarica Tabella B (CSV)",
                data=df_download_b.to_csv(index=False),
                file_name="tabella_b_budget_effettivo.csv",
                mime="text/csv",
            )

    except Exception as e:
        st.error(f"Si è verificato un errore durante l'elaborazione: {e}")
        st.exception(e) # Per debugging
else:
    st.info("Per favore, carica entrambi i file Excel: Budget e Effettivo.")
