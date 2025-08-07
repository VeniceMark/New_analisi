import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from datetime import datetime, timedelta
import re
from io import BytesIO

# Configurazione pagina
st.set_page_config(
    page_title="Analisi Budget vs Effettivo", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

def normalize_column_names(df):
    """Normalizza i nomi delle colonne rimuovendo spazi extra e caratteri speciali"""
    df.columns = df.columns.astype(str).str.strip()
    return df

def load_excel_file(uploaded_file, file_type):
    """Carica un file Excel e gestisce errori"""
    try:
        if uploaded_file is not None:
            df = pd.read_excel(uploaded_file, sheet_name=0)  # Primo foglio
            df = normalize_column_names(df)
            
            # Rimuovi righe completamente vuote
            df = df.dropna(how='all')
            
            return df
        else:
            return None
    except Exception as e:
        st.error(f"Errore nel caricamento del file {file_type}: {str(e)}")
        return None

def parse_budget_data(budget_df):
    """Estrae i dati di budget organizzandoli per cliente e periodo"""
    if budget_df is None:
        return None, []
    
    # Debug: mostra la struttura del file
    st.write("**Debug - Struttura Budget File:**")
    st.write("Colonne trovate:", list(budget_df.columns))
    st.write("Prime 3 righe:")
    st.dataframe(budget_df.head(3))
    
    budget_data = {}
    periods = []
    
    # Metodo 1: Trova colonne che contengono "budget ore nel con capo colonna per periodo"
    budget_columns = [col for col in budget_df.columns if 'budget ore nel con capo colonna per periodo' in col.lower()]
    
    # Metodo 2: Se non trova niente, cerca pattern più flessibili
    if not budget_columns:
        # Cerca colonne che contengono pattern data YYYY-MM
        budget_columns = [col for col in budget_df.columns if re.search(r'\d{4}-\d{2}.*\([^)]*\)', str(col))]
    
    # Metodo 3: Se ancora non trova, cerca qualsiasi colonna con date
    if not budget_columns:
        budget_columns = [col for col in budget_df.columns if re.search(r'\d{4}-\d{2}', str(col))]
    
    st.write("**Colonne budget identificate:**", budget_columns)
    
    if not budget_columns:
        st.error("❌ Nessuna colonna budget trovata. Pattern cercati:")
        st.write("1. Colonne contenenti: 'budget ore nel con capo colonna per periodo'")
        st.write("2. Colonne con pattern: 'YYYY-MM (...)'")
        st.write("3. Colonne con pattern: 'YYYY-MM'")
        return None, []
    
    # Estrai i periodi dalle colonne
    for col in budget_columns:
        # Prova diversi pattern
        match = re.search(r'(\d{4}-\d{2})\s*\(([^)]+)\)', str(col))
        if match:
            year_month = match.group(1)
            period_type = match.group(2).strip()
            period_key = f"{year_month} ({period_type})"
            if period_key not in periods:
                periods.append(period_key)
        else:
            # Fallback: usa nome colonna come periodo
            periods.append(str(col))
    
    st.write("**Periodi identificati:**", periods)
    
    # Organizza i dati per cliente
    for _, row in budget_df.iterrows():
        cliente = str(row.iloc[0]).strip()  # Prima colonna è sempre cliente
        if pd.isna(cliente) or cliente == '' or cliente.lower() == 'cliente':
            continue
            
        budget_data[cliente] = {}
        
        for i, col in enumerate(budget_columns):
            # Usa il periodo corrispondente
            if i < len(periods):
                period_key = periods[i]
            else:
                period_key = str(col)
            
            try:
                value = float(row[col]) if pd.notna(row[col]) else 0
                budget_data[cliente][period_key] = value
            except (ValueError, TypeError):
                budget_data[cliente][period_key] = 0
    
    st.write("**Esempio dati budget processati (primo cliente):**")
    if budget_data:
        first_client = list(budget_data.keys())[0]
        st.write(f"Cliente: {first_client}")
        st.write("Dati:", budget_data[first_client])
    
    return budget_data, sorted(periods)

def process_effettive_data(effettive_df):
    """Processa i dati effettivi creando pivot per periodi 1-15 e 1-fine mese"""
    if effettive_df is None:
        return None, None
    
    # Pulisci i dati
    effettive_df = effettive_df.dropna(subset=['cliente', 'data', 'ore'])
    
    # Converti la colonna data (formato GG/MM/AA)
    effettive_df['data'] = pd.to_datetime(effettive_df['data'], format='%d/%m/%y', errors='coerce')
    effettive_df = effettive_df.dropna(subset=['data'])
    
    # Estrai giorno, mese, anno
    effettive_df['giorno'] = effettive_df['data'].dt.day
    effettive_df['anno'] = effettive_df['data'].dt.year
    effettive_df['mese'] = effettive_df['data'].dt.month
    effettive_df['anno_mese'] = effettive_df['data'].dt.strftime('%Y-%m')
    
    # Converti ore a numerico
    effettive_df['ore'] = pd.to_numeric(effettive_df['ore'], errors='coerce').fillna(0)
    
    # Pivot per giorni 1-15
    effettive_1_15 = effettive_df[effettive_df['giorno'] <= 15].groupby(['cliente', 'anno_mese'])['ore'].sum().reset_index()
    effettive_1_15['periodo'] = effettive_1_15['anno_mese'] + ' (1-15)'
    pivot_1_15 = effettive_1_15.pivot(index='cliente', columns='periodo', values='ore').fillna(0)
    
    # Pivot per tutto il mese
    effettive_totale = effettive_df.groupby(['cliente', 'anno_mese'])['ore'].sum().reset_index()
    effettive_totale['periodo'] = effettive_totale['anno_mese'] + ' (1-fine)'
    pivot_totale = effettive_totale.pivot(index='cliente', columns='periodo', values='ore').fillna(0)
    
    return pivot_1_15, pivot_totale

def apply_analysis_rules(budget_val, effettivo_val):
    """Applica le regole di analisi per calcolare scostamenti"""
    if budget_val == 0 and effettivo_val > 0:
        return "extrabudget"
    elif budget_val == 0 and effettivo_val == 0:
        return "None"
    elif budget_val > 0:
        scostamento = ((budget_val - effettivo_val) / budget_val) * 100
        return f"{round(scostamento, 2)}%"
    else:
        return "None"

def create_detailed_table(budget_data, pivot_1_15, pivot_totale, periods):
    """Crea la tabella dettagliata mensile"""
    if not budget_data or pivot_1_15 is None or pivot_totale is None:
        return pd.DataFrame()
    
    # Ottieni tutti i clienti
    all_clients = set(budget_data.keys())
    if pivot_1_15 is not None:
        all_clients.update(pivot_1_15.index.tolist())
    if pivot_totale is not None:
        all_clients.update(pivot_totale.index.tolist())
    
    results = []
    
    for cliente in sorted(all_clients):
        row_data = {'Cliente': cliente}
        
        for period in periods:
            # Ottieni valore budget
            budget_val = budget_data.get(cliente, {}).get(period, 0)
            
            # Ottieni valore effettivo
            if '(1-15)' in period:
                effettivo_val = pivot_1_15.loc[cliente, period] if cliente in pivot_1_15.index and period in pivot_1_15.columns else 0
            else:
                effettivo_val = pivot_totale.loc[cliente, period] if cliente in pivot_totale.index and period in pivot_totale.columns else 0
            
            # Applica regole
            result = apply_analysis_rules(budget_val, effettivo_val)
            row_data[period] = result
        
        results.append(row_data)
    
    return pd.DataFrame(results)

def create_summary_table(budget_data, pivot_1_15, pivot_totale):
    """Crea la tabella di riepilogo totale"""
    if not budget_data:
        return pd.DataFrame()
    
    all_clients = set(budget_data.keys())
    if pivot_1_15 is not None:
        all_clients.update(pivot_1_15.index.tolist())
    if pivot_totale is not None:
        all_clients.update(pivot_totale.index.tolist())
    
    results = []
    
    for cliente in sorted(all_clients):
        # Calcola totale budget - USA SOLO I VALORI (1-fine) per evitare doppi conteggi
        budget_totale = 0
        for period, value in budget_data.get(cliente, {}).items():
            if '(1-fine)' in period:  # Solo i valori che rappresentano il mese completo
                budget_totale += value
        
        # Calcola totale effettivo - USA SOLO pivot_totale (che rappresenta tutto il mese)
        effettivo_totale = 0
        if pivot_totale is not None and cliente in pivot_totale.index:
            effettivo_totale = pivot_totale.loc[cliente].sum()
        
        # Calcola differenza
        differenza = budget_totale - effettivo_totale
        
        # Calcola scostamento percentuale
        scostamento = apply_analysis_rules(budget_totale, effettivo_totale)
        
        results.append({
            'Cliente': cliente,
            'Budget': round(budget_totale, 2),
            'Effettivo': round(effettivo_totale, 2),
            'Differenza': round(differenza, 2),
            'Scostamento %': scostamento
        })
    
    return pd.DataFrame(results)

def get_color_for_value(value):
    """Restituisce il colore per un valore di scostamento"""
    if isinstance(value, str):
        if value == "extrabudget":
            return "background-color: #8B008B; color: white"  # Viola
        elif value == "None":
            return "background-color: #000000; color: white"  # Nero
        elif value.endswith('%'):
            # Estrai il valore numerico dalla stringa percentuale
            try:
                numeric_value = float(value[:-1])  # Rimuovi il simbolo %
                # Gradiente da rosso (-100%) a verde (+100%)
                normalized = max(-100, min(100, numeric_value)) / 100
                if normalized < 0:
                    # Da rosso a giallo
                    red = 1.0
                    green = 1.0 + normalized
                    blue = 0.0
                else:
                    # Da giallo a verde
                    red = 1.0 - normalized
                    green = 1.0
                    blue = 0.0
                
                color = f"background-color: rgb({int(red*255)}, {int(green*255)}, {int(blue*255)})"
                return color
            except:
                return ""
        else:
            return ""
    else:
        # Fallback per valori numerici (dovrebbe essere raro ora)
        normalized = max(-100, min(100, value)) / 100
        if normalized < 0:
            red = 1.0
            green = 1.0 + normalized
            blue = 0.0
        else:
            red = 1.0 - normalized
            green = 1.0
            blue = 0.0
        
        color = f"background-color: rgb({int(red*255)}, {int(green*255)}, {int(blue*255)})"
        return color

def style_dataframe(df, exclude_columns=None):
    """Applica stili alla tabella"""
    def apply_color(val):
        return get_color_for_value(val)
    
    if exclude_columns is None:
        exclude_columns = []
    
    # Applica colori a tutte le colonne tranne Cliente e quelle escluse
    styled = df.style
    for col in df.columns:
        if col not in ['Cliente'] + exclude_columns:
            styled = styled.applymap(apply_color, subset=[col])
    
    return styled

def create_quarterly_analysis(detailed_df):
    """Crea analisi trimestrale"""
    if detailed_df.empty:
        return pd.DataFrame()
    
    quarterly_data = []
    
    for _, row in detailed_df.iterrows():
        cliente = row['Cliente']
        quarters = {'Q1': [], 'Q2': [], 'Q3': [], 'Q4': []}
        
        for col in detailed_df.columns[1:]:  # Escludi Cliente
            if col != 'Cliente':
                # Considera SOLO i periodi (1-fine) per evitare doppi conteggi
                if '(1-fine)' in col:
                    match = re.search(r'(\d{4})-(\d{2})', col)
                    if match:
                        year = int(match.group(1))
                        month = int(match.group(2))
                        
                        value = row[col]
                        
                        # Assegna al trimestre corretto
                        if month in [1, 2, 3]:
                            quarters['Q1'].append(value)
                        elif month in [4, 5, 6]:
                            quarters['Q2'].append(value)
                        elif month in [7, 8, 9]:
                            quarters['Q3'].append(value)
                        elif month in [10, 11, 12]:
                            quarters['Q4'].append(value)
        
        # Determina il valore per ogni trimestre
        quarterly_row = {'Cliente': cliente}
        for quarter, values in quarters.items():
            if not values:
                quarterly_row[quarter] = "N/A"
            else:
                # Filtra valori non-None
                non_none_values = [v for v in values if v != "None"]
                
                if not non_none_values:
                    quarterly_row[quarter] = "N/A"
                elif any(v == "extrabudget" for v in non_none_values):
                    quarterly_row[quarter] = "extrabudget"
                else:
                    # Calcola media dei valori percentuali
                    numeric_values = []
                    for v in non_none_values:
                        if isinstance(v, str) and v.endswith('%'):
                            try:
                                numeric_values.append(float(v[:-1]))
                            except:
                                pass
                    
                    if numeric_values:
                        avg_value = np.mean(numeric_values)
                        quarterly_row[quarter] = f"{round(avg_value, 2)}%"
                    else:
                        quarterly_row[quarter] = "N/A"
        
        quarterly_data.append(quarterly_row)
    
    return pd.DataFrame(quarterly_data)

def sort_mixed_column(series):
    """Funzione per ordinare colonne che contengono sia percentuali che testo"""
    def sort_key(value):
        if isinstance(value, str):
            if value.endswith('%'):
                try:
                    return (0, float(value[:-1]))  # (tipo, valore numerico)
                except:
                    return (2, value)  # Testo non convertibile
            elif value == "extrabudget":
                return (1, 0)  # extrabudget viene dopo le percentuali
            elif value == "None":
                return (3, 0)  # None viene per ultimo
            else:
                return (2, value)  # Altri testi
        else:
            return (0, float(value))  # Numeri puri
    
    return series.iloc[series.map(sort_key).argsort()]
    """Crea proiezioni per quarters successivi"""
    if summary_df.empty:
        return pd.DataFrame()
    
    projections = []
    
    for _, row in summary_df.iterrows():
        scostamento_str = row['Scostamento %']
        
        # Estrai valore numerico dalla stringa percentuale
        if isinstance(scostamento_str, str) and scostamento_str.endswith('%'):
            try:
                scostamento_val = float(scostamento_str[:-1])
                current_performance = 100 - scostamento_val  # Performance percentuale
                
                # Proiezione prossimo trimestre
                next_q_projection = row['Budget'] * (current_performance / 100) * 1.1  # Assumendo miglioramento 10%
                
                # Proiezione anno successivo
                next_year_projection = row['Budget'] * (current_performance / 100) * 4  # Estendi a 4 trimestri
                
                projections.append({
                    'Cliente': row['Cliente'],
                    'Performance Attuale %': f"{round(current_performance, 2)}%",
                    'Proiezione Prossimo Q': round(next_q_projection, 2),
                    'Proiezione Anno Prossimo': round(next_year_projection, 2)
                })
            except:
                projections.append({
                    'Cliente': row['Cliente'],
                    'Performance Attuale %': "N/A",
                    'Proiezione Prossimo Q': "N/A",
                    'Proiezione Anno Prossimo': "N/A"
                })
        else:
            projections.append({
                'Cliente': row['Cliente'],
                'Performance Attuale %': "N/A",
                'Proiezione Prossimo Q': "N/A",
                'Proiezione Anno Prossimo': "N/A"
            })
    
    return pd.DataFrame(projections)

# Interface Streamlit
st.title("📊 Analisi Budget vs Effettivo")
st.markdown("---")

# Sidebar per caricamento file
st.sidebar.header("📁 Caricamento File")

uploaded_budget = st.sidebar.file_uploader(
    "Carica file Budget Excel", 
    type=['xlsx', 'xls'],
    help="File contenente i dati di budget con struttura cliente + gruppi di 5 colonne per mese"
)

uploaded_effettive = st.sidebar.file_uploader(
    "Carica file Effettive Excel", 
    type=['xlsx', 'xls'],
    help="File contenente tre colonne: cliente, data (GG/MM/AA), ore"
)

# Caricamento e processamento dati
if uploaded_budget is not None and uploaded_effettive is not None:
    
    # Carica i file
    budget_df = load_excel_file(uploaded_budget, "Budget")
    effettive_df = load_excel_file(uploaded_effettive, "Effettive")
    
    if budget_df is not None and effettive_df is not None:
        
        # Processa i dati
        budget_data, periods = parse_budget_data(budget_df)
        pivot_1_15, pivot_totale = process_effettive_data(effettive_df)
        
        if budget_data and periods:
            
            # Filtri
            st.sidebar.markdown("---")
            st.sidebar.header("🔍 Filtri")
            
            # Filtro Cliente
            all_clients = list(budget_data.keys())
            if pivot_1_15 is not None:
                all_clients.extend(pivot_1_15.index.tolist())
            if pivot_totale is not None:
                all_clients.extend(pivot_totale.index.tolist())
            
            unique_clients = sorted(list(set(all_clients)))
            selected_clients = st.sidebar.multiselect(
                "Seleziona Clienti",
                options=["Tutti"] + unique_clients,
                default=["Tutti"]
            )
            
            # Filtro Periodo
            selected_periods = st.sidebar.multiselect(
                "Seleziona Periodi",
                options=["Tutti"] + periods,
                default=["Tutti"]
            )
            
            # Applica filtri
            if "Tutti" in selected_clients:
                filtered_clients = unique_clients
            else:
                filtered_clients = selected_clients
            
            if "Tutti" in selected_periods:
                filtered_periods = periods
            else:
                filtered_periods = selected_periods
            
            # Crea le tabelle
            detailed_df = create_detailed_table(budget_data, pivot_1_15, pivot_totale, filtered_periods)
            summary_df = create_summary_table(budget_data, pivot_1_15, pivot_totale)
            
            # Filtra per clienti selezionati
            if not detailed_df.empty:
                detailed_df = detailed_df[detailed_df['Cliente'].isin(filtered_clients)]
            if not summary_df.empty:
                summary_df = summary_df[summary_df['Cliente'].isin(filtered_clients)]
            
            # Tabs per organizzare l'output
            tab1, tab2, tab3, tab4 = st.tabs(["📋 Dettaglio Mensile", "📈 Riepilogo Totale", "📊 Analisi Trimestrale", "🔮 Proiezioni"])
            
            with tab1:
                st.header("Tabella A - Dettaglio Mensile")
                if not detailed_df.empty:
                    # Crea dataframe con funzione di ordinamento personalizzata
                    displayed_df = detailed_df.copy()
                    st.dataframe(style_dataframe(displayed_df), use_container_width=True)
                    
                    st.info("💡 **Ordinamento**: Le colonne con percentuali si ordinano numericamente. L'ordine è: percentuali (dal più negativo al più positivo), poi 'extrabudget', poi altri testi, infine 'None'.")
                    
                    # Download
                    csv = detailed_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Scarica Tabella Dettaglio (CSV)",
                        data=csv,
                        file_name=f"dettaglio_mensile_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("Nessun dato disponibile per i filtri selezionati")
            
            with tab2:
                st.header("Tabella B - Riepilogo Totale")
                if not summary_df.empty:
                    # Escludi Budget e Effettivo dalla colorazione, mantieni Differenza
                    st.dataframe(style_dataframe(summary_df, exclude_columns=['Budget', 'Effettivo']), use_container_width=True)
                    
                    st.info("💡 **Note**: Budget ed Effettivo senza colorazione. Differenza e Scostamento % sono colorati. Il Budget totale usa solo i valori (1-fine) per evitare doppi conteggi.")
                    
                    # Grafico riepilogativo
                    fig, ax = plt.subplots(figsize=(12, 6))
                    x_pos = np.arange(len(summary_df))
                    
                    ax.bar(x_pos - 0.2, summary_df['Budget'], 0.4, label='Budget', alpha=0.7)
                    ax.bar(x_pos + 0.2, summary_df['Effettivo'], 0.4, label='Effettivo', alpha=0.7)
                    
                    ax.set_xlabel('Clienti')
                    ax.set_ylabel('Ore')
                    ax.set_title('Budget vs Effettivo per Cliente')
                    ax.set_xticks(x_pos)
                    ax.set_xticklabels(summary_df['Cliente'], rotation=45, ha='right')
                    ax.legend()
                    
                    st.pyplot(fig)
                    plt.close()
                    
                    # Download
                    csv = summary_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Scarica Riepilogo (CSV)",
                        data=csv,
                        file_name=f"riepilogo_totale_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("Nessun dato disponibile per i filtri selezionati")
            
            with tab3:
                st.header("Analisi per Trimestri")
                quarterly_df = create_quarterly_analysis(detailed_df)
                
                if not quarterly_df.empty:
                    st.dataframe(style_dataframe(quarterly_df), use_container_width=True)
                    
                    st.info("💡 **Logica Trimestri**: Q1=Gen-Mar, Q2=Apr-Giu, Q3=Lug-Set, Q4=Ott-Dic. **IMPORTANTE**: Usa solo i periodi (1-fine) per evitare doppi conteggi - i valori (1-fine) includono già quelli (1-15). Se c'è 'extrabudget' nel trimestre → 'extrabudget'. Altrimenti media delle percentuali (esclusi 'None').")
                    
                    # Grafico trimestrale
                    fig, ax = plt.subplots(figsize=(12, 6))
                    quarters = ['Q1', 'Q2', 'Q3', 'Q4']
                    
                    for i, cliente in enumerate(quarterly_df['Cliente']):
                        values = []
                        for q in quarters:
                            val = quarterly_df.loc[i, q]
                            if isinstance(val, str) and val.endswith('%'):
                                try:
                                    values.append(float(val[:-1]))
                                except:
                                    values.append(0)
                            else:
                                values.append(0)  # Non plottare extrabudget e N/A
                        
                        ax.plot(quarters, values, marker='o', label=cliente)
                    
                    ax.set_xlabel('Trimestre')
                    ax.set_ylabel('Scostamento Medio %')
                    ax.set_title('Trend Trimestrale Scostamenti (Solo Valori Numerici)')
                    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                    ax.grid(True, alpha=0.3)
                    
                    st.pyplot(fig)
                    plt.close()
                    
                    # Download
                    csv = quarterly_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Scarica Analisi Trimestrale (CSV)",
                        data=csv,
                        file_name=f"analisi_trimestrale_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("Nessun dato disponibile per l'analisi trimestrale")
            
            with tab4:
                st.header("Proiezioni Future")
                projections_df = create_projections(summary_df, periods)
                
                if not projections_df.empty:
                    st.dataframe(projections_df, use_container_width=True)
                    
                    st.info("💡 **Logica Proiezioni**: Basate sulla performance attuale (100% - Scostamento%). Prossimo Q = Performance × Budget × 1.1 (miglioramento 10%). Anno Prossimo = Performance × Budget × 4 (4 trimestri).")
                    
                    # Grafico proiezioni
                    fig, ax = plt.subplots(figsize=(12, 6))
                    
                    # Filtra valori numerici per il grafico
                    numeric_proj = projections_df[
                        projections_df['Proiezione Prossimo Q'] != "N/A"
                    ].copy()
                    
                    if not numeric_proj.empty:
                        numeric_proj['Proiezione Prossimo Q'] = pd.to_numeric(numeric_proj['Proiezione Prossimo Q'])
                        numeric_proj['Proiezione Anno Prossimo'] = pd.to_numeric(numeric_proj['Proiezione Anno Prossimo'])
                        
                        x_pos = np.arange(len(numeric_proj))
                        ax.bar(x_pos - 0.2, numeric_proj['Proiezione Prossimo Q'], 0.4, 
                               label='Prossimo Trimestre', alpha=0.7)
                        ax.bar(x_pos + 0.2, numeric_proj['Proiezione Anno Prossimo'], 0.4, 
                               label='Anno Prossimo', alpha=0.7)
                        
                        ax.set_xlabel('Clienti')
                        ax.set_ylabel('Ore Proiettate')
                        ax.set_title('Proiezioni Future')
                        ax.set_xticks(x_pos)
                        ax.set_xticklabels(numeric_proj['Cliente'], rotation=45, ha='right')
                        ax.legend()
                        
                        st.pyplot(fig)
                        plt.close()
                    else:
                        st.info("Nessun dato numerico disponibile per il grafico delle proiezioni")
                    
                    # Download
                    csv = projections_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Scarica Proiezioni (CSV)",
                        data=csv,
                        file_name=f"proiezioni_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("Nessun dato disponibile per le proiezioni")
            
            # Statistiche generali
            st.markdown("---")
            st.subheader("📊 Statistiche Generali")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Clienti Totali", len(filtered_clients))
            
            with col2:
                if not summary_df.empty:
                    total_budget = summary_df['Budget'].sum()
                    st.metric("Budget Totale", f"{total_budget:,.0f} ore")
                else:
                    st.metric("Budget Totale", "N/A")
            
            with col3:
                if not summary_df.empty:
                    total_effettivo = summary_df['Effettivo'].sum()
                    st.metric("Effettivo Totale", f"{total_effettivo:,.0f} ore")
                else:
                    st.metric("Effettivo Totale", "N/A")
            
            with col4:
                if not summary_df.empty and total_budget > 0:
                    scostamento_generale = ((total_budget - total_effettivo) / total_budget) * 100
                    st.metric("Scostamento Generale", f"{scostamento_generale:.2f}%")
                else:
                    st.metric("Scostamento Generale", "N/A")
        
        else:
            st.error("Errore nel processamento dei dati di budget. Verifica la struttura del file.")
    
    else:
        st.error("Errore nel caricamento di uno o entrambi i file.")

else:
    st.info("👆 Carica entrambi i file Excel nella barra laterale per iniziare l'analisi.")
    
    # Mostra informazioni di aiuto
    with st.expander("ℹ️ Informazioni sui formati file richiesti"):
        st.markdown("""
        **File Budget:**
        - Prima colonna: 'cliente'
        - Successive colonne in gruppi di 5 per mese: Costo orario, Budget Economico, Extrabudget, budget ore periodo YYYY-MM (1-15), budget ore periodo YYYY-MM (1-fine)
        
        **File Effettive:**
        - Tre colonne: 'cliente', 'data', 'ore'
        - Formato data: GG/MM/AA
        
        **Regole di Analisi:**
        1. Budget = 0, Effettivo > 0: "extrabudget" (sfondo viola)
        2. Budget = 0, Effettivo = 0: "None" (sfondo nero)
        3. Budget > 0: Percentuale scostamento con gradiente colore (rosso -100% a verde +100%)
        """)

# Footer
st.markdown("---")
st.markdown("*Applicazione sviluppata per l'analisi comparativa Budget vs Effettivo*")
