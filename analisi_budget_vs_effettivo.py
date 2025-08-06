# app.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
from io import BytesIO

# Configurazione della pagina
st.set_page_config(
    page_title="Analisi Budget vs Effettivo",
    page_icon="📊",
    layout="wide"
)

# Titolo dell'applicazione
st.title("📊 Analisi Budget vs Effettivo")
st.markdown("""
Questa applicazione confronta le ore lavorate effettive con le ore previste a budget, 
organizzate per cliente e suddivise per periodi.
""")

# Funzione per caricare i dati
@st.cache_data
def load_data(uploaded_file):
    # Leggi i due fogli Excel
    try:
        df_effettivo = pd.read_excel(uploaded_file, sheet_name='Effettivo')
        # Per il budget prendiamo il primo foglio disponibile (che è "Sheet1" nel tuo file)
        xl_file = pd.ExcelFile(uploaded_file)
        budget_sheet_name = xl_file.sheet_names[0]  # Prendi il primo foglio
        df_budget_raw = pd.read_excel(uploaded_file, sheet_name=budget_sheet_name)
    except Exception as e:
        st.error(f"Errore nel caricamento dei fogli: {e}")
        return None, None
    
    # Normalizzazione nomi colonne (minuscolo e rimozione spazi)
    df_effettivo.columns = df_effettivo.columns.str.lower().str.strip()
    
    # Validazione colonne obbligatorie per effettivo
    required_effettivo = ['cliente', 'data', 'ore']
    
    if not all(col in df_effettivo.columns for col in required_effettivo):
        st.error(f"Il foglio 'Effettivo' deve contenere le colonne: {required_effettivo}")
        st.info(f"Colonne trovate: {list(df_effettivo.columns)}")
        return None, None
    
    # Conversione colonna data in datetime
    try:
        df_effettivo['data'] = pd.to_datetime(df_effettivo['data'])
    except Exception as e:
        st.error(f"Errore nella conversione della colonna 'data': {e}")
        return None, None
    
    # Estrazione mese e giorno
    df_effettivo['mese'] = df_effettivo['data'].dt.to_period('M').astype(str)
    df_effettivo['giorno'] = df_effettivo['data'].dt.day
    
    # Trasformazione del budget dal formato wide a long
    # Identifica le colonne che contengono i periodi
    periodo_cols = [col for col in df_budget_raw.columns if re.match(r'\d{4}-\d{2} \(1-(15|fine)\)', str(col))]
    
    # Crea un dataframe con cliente e colonne periodo
    df_budget = df_budget_raw[['cliente'] + periodo_cols].copy()
    
    # Trasforma da wide a long
    df_budget = df_budget.melt(
        id_vars=['cliente'],
        value_vars=periodo_cols,
        var_name='periodo',
        value_name='ore'
    )
    
    # Rimuovi righe con ore NaN o 0 (opzionale)
    df_budget = df_budget.dropna(subset=['ore'])
    df_budget = df_budget[df_budget['ore'] != 0]
    
    return df_effettivo, df_budget

# Funzione per creare pivot tables
def create_pivot_tables(df_effettivo):
    # Pivot per 1-15 del mese
    df_15 = df_effettivo[df_effettivo['giorno'] <= 15].copy()
    df_15['periodo'] = df_15['mese'] + " (1-15)"
    pivot_15 = df_15.groupby(['cliente', 'periodo'])['ore'].sum().reset_index()
    
    # Pivot per 1-fine mese
    df_31 = df_effettivo.copy()
    df_31['periodo'] = df_31['mese'] + " (1-fine)"
    pivot_31 = df_31.groupby(['cliente', 'periodo'])['ore'].sum().reset_index()
    
    # Unione dei pivot
    df_effettivo_pivot = pd.concat([pivot_15, pivot_31], axis=0)
    df_effettivo_pivot = df_effettivo_pivot.pivot(index='cliente', columns='periodo', values='ore').fillna(0)
    
    return df_effettivo_pivot

# Funzione per calcolare scostamenti percentuali
def calculate_percentage_diff(eff_df, bud_df):
    # Preparazione dati effettivi
    eff_melted = eff_df.melt(var_name='periodo', value_name='ore_effettivo', ignore_index=False).reset_index()
    
    # Unione con budget
    merged = pd.merge(eff_melted, bud_df, on=['cliente', 'periodo'], how='outer').fillna(0)
    
    # Calcolo scostamento percentuale
    def calc_diff(row):
        if row['ore_budget'] > 0:
            return (row['ore_effettivo'] - row['ore_budget']) / row['ore_budget'] * 100
        elif row['ore_budget'] == 0 and row['ore_effettivo'] > 0:
            return 'extrabudget'
        else:
            return '0%'
    
    merged['scostamento_%'] = merged.apply(calc_diff, axis=1)
    
    # Pivot per visualizzazione
    result = merged.pivot(index='cliente', columns='periodo', values='scostamento_%').fillna('0%')
    
    return result

# Funzione per applicare stili condizionali
def color_scostamenti(val):
    if val == 'extrabudget':
        return 'background-color: #8b5cf6; color: white'
    elif val == '0%':
        return 'background-color: #1e293b; color: white'
    elif isinstance(val, (int, float)):
        if val > 0:
            return 'background-color: #dcfce7; color: #166534'
        elif val < 0:
            return 'background-color: #fee2e2; color: #991b1b'
    return ''

# Funzione per creare il grafico
def create_bar_chart(dashboard_data):
    # Preparazione dati per il grafico
    chart_data = dashboard_data.copy()
    chart_data['extrabudget'] = np.where(
        (chart_data['ore_budget'] == 0) & (chart_data['ore_effettivo'] > 0),
        chart_data['ore_effettivo'],
        0
    )
    
    chart_data['effettivo_regolare'] = np.where(
        chart_data['ore_budget'] > 0,
        chart_data['ore_effettivo'],
        0
    )
    
    # Creazione del grafico
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(chart_data['cliente']))
    width = 0.25
    
    bars1 = ax.bar(x - width, chart_data['ore_budget'], width, label='Budget', color='#3b82f6')
    bars2 = ax.bar(x, chart_data['effettivo_regolare'], width, label='Effettivo', color='#10b981')
    bars3 = ax.bar(x + width, chart_data['extrabudget'], width, label='Extrabudget', color='#8b5cf6')
    
    # Aggiunta delle etichette
    ax.set_xlabel('Clienti')
    ax.set_ylabel('Ore')
    ax.set_title('Confronto Ore Budget vs Effettivo per Cliente')
    ax.set_xticks(x)
    ax.set_xticklabels(chart_data['cliente'], rotation=45, ha='right')
    ax.legend()
    
    # Aggiunta dei valori sopra le barre
    def add_value_labels(bars):
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(f'{height:.0f}',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3),
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=8)
    
    add_value_labels(bars1)
    add_value_labels(bars2)
    add_value_labels(bars3)
    
    plt.tight_layout()
    return fig

# Caricamento file
st.markdown("## Caricamento Dati")
st.markdown("Carica il file Excel con i fogli 'Effettivo' e il foglio budget (formato template fornito)")
uploaded_file = st.file_uploader("Seleziona il file Excel", type="xlsx")

if uploaded_file is not None:
    df_effettivo, df_budget = load_data(uploaded_file)
    
    if df_effettivo is not None and df_budget is not None:
        # Rinomina la colonna ore nel budget per coerenza
        df_budget = df_budget.rename(columns={'ore': 'ore_budget'})
        
        # Creazione pivot tables
        df_effettivo_pivot = create_pivot_tables(df_effettivo)
        
        # Sezione 1: Scostamento Percentuale
        st.header("1. Scostamento Percentuale")
        st.markdown("Confronto percentuale tra ore effettive e ore a budget per cliente e periodo.")
        scostamenti = calculate_percentage_diff(df_effettivo_pivot, df_budget)
        st.dataframe(scostamenti.style.applymap(color_scostamenti))
        
        # Sezione 2: Dati Dettagliati
        st.header("2. Dati Dettagliati")
        st.markdown("Visualizzazione combinata di ore effettive, ore a budget e scostamento percentuale.")
        
        # Combinazione dati
        eff_melted = df_effettivo_pivot.melt(var_name='periodo', value_name='ore_effettivo', ignore_index=False).reset_index()
        dettagli = pd.merge(eff_melted, df_budget, on=['cliente', 'periodo'], how='outer').fillna(0)
        
        def calc_diff(row):
            if row['ore_budget'] > 0:
                return (row['ore_effettivo'] - row['ore_budget']) / row['ore_budget'] * 100
            elif row['ore_budget'] == 0 and row['ore_effettivo'] > 0:
                return 'extrabudget'
            else:
                return '0%'
        
        dettagli['scostamento_%'] = dettagli.apply(calc_diff, axis=1)
        
        # Pivoting per visualizzazione
        pivot_dettagli = dettagli.pivot(index='cliente', columns='periodo', values=['ore_effettivo', 'ore_budget', 'scostamento_%'])
        
        # Applica stili solo alla colonna scostamento_%
        styled_dettagli = pivot_dettagli.style.applymap(
            lambda x: 'background-color: #8b5cf6; color: white' if x == 'extrabudget' 
            else ('background-color: #1e293b; color: white' if x == '0%' 
            else ('background-color: #dcfce7; color: #166534' if isinstance(x, (int, float)) and x > 0 
            else ('background-color: #fee2e2; color: #991b1b' if isinstance(x, (int, float)) and x < 0 
            else ''))), subset=(slice(None), slice(None), 'scostamento_%')
        )
        
        st.dataframe(styled_dettagli)
        
        # Sezione 3: Dashboard Riepilogativa
        st.header("3. Dashboard Riepilogativa per Cliente")
        st.markdown("Sommatoria totale delle ore effettive e di budget per cliente.")
        
        # Aggregazione dati per cliente
        dashboard_data = dettagli.groupby('cliente').agg({
            'ore_effettivo': 'sum',
            'ore_budget': 'sum'
        }).reset_index()
        
        def calc_dashboard_diff(row):
            if row['ore_budget'] > 0:
                return (row['ore_effettivo'] - row['ore_budget']) / row['ore_budget'] * 100
            elif row['ore_budget'] == 0 and row['ore_effettivo'] > 0:
                return 'extrabudget'
            else:
                return '0%'
        
        dashboard_data['scostamento_%'] = dashboard_data.apply(calc_dashboard_diff, axis=1)
        dashboard_data['scostamento_valore'] = dashboard_data['ore_effettivo'] - dashboard_data['ore_budget']
        
        # Filtraggio clienti con dati
        dashboard_data = dashboard_data[
            (dashboard_data['ore_effettivo'] > 0) | (dashboard_data['ore_budget'] > 0)
        ]
        
        # Stile per la dashboard
        def color_dashboard(val, col_name):
            if col_name == 'scostamento_%':
                if val == 'extrabudget':
                    return 'background-color: #8b5cf6; color: white'
                elif val == '0%':
                    return 'background-color: #1e293b; color: white'
                elif isinstance(val, (int, float)):
                    if val > 0:
                        return 'background-color: #dcfce7; color: #166534'
                    elif val < 0:
                        return 'background-color: #fee2e2; color: #991b1b'
            elif col_name == 'scostamento_valore':
                if val == 'extrabudget':
                    return 'background-color: #8b5cf6; color: white'
                elif isinstance(val, (int, float)):
                    if val > 0:
                        return 'background-color: #dcfce7; color: #166534'
                    elif val < 0:
                        return 'background-color: #fee2e2; color: #991b1b'
            return ''
        
        styled_dashboard = dashboard_data.style.apply(lambda x: [
            color_dashboard(x[col], col) for col in x.index
        ], axis=1)
        
        st.dataframe(styled_dashboard)
        
        # Sezione 4: Grafico a Barre
        st.header("4. Grafico a Barre")
        st.markdown("Rappresentazione grafica delle ore effettive, budget e extrabudget per cliente.")
        fig = create_bar_chart(dashboard_data)
        st.pyplot(fig)
        
        # Informazioni aggiuntive
        st.sidebar.header("Informazioni")
        st.sidebar.markdown("""
        - **Verde**: Ore effettive superiori al budget
        - **Rosso**: Ore effettive inferiori al budget
        - **Viola**: Ore extrabudget (non previste a budget)
        - **Nero**: Nessuna attività registrata
        """)
        
        st.sidebar.header("Formato File")
        st.sidebar.markdown("""
        Il file deve contenere:
        1. Un foglio chiamato **'Effettivo'** con colonne:
           - `cliente`
           - `data`
           - `ore`
        2. Un foglio con il budget nel formato template fornito
        """)
else:
    st.info("Carica un file Excel per iniziare l'analisi")
    st.markdown("""
    ### Struttura del file Excel richiesta:
    
    **Foglio 'Effettivo':**
    | cliente | data | ore |
    |---------|------|-----|
    | Cliente A | 2025-07-05 | 120 |
    | Cliente B | 2025-07-10 | 70 |
    
    **Foglio Budget (formato template):**
    | cliente | 2025-01 (1-15) | 2025-01 (1-fine) | ... |
    |---------|----------------|------------------|-----|
    | Cliente A | 100 | 200 | ... |
    """)
