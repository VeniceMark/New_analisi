# app.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Configurazione della pagina
st.set_page_config(
    page_title="Analisi Budget vs Effetivo",
    page_icon="📊",
    layout="wide"
)

# Titolo dell'applicazione
st.title("📊 Analisi Budget vs Effettivo")
st.markdown("""
Questa applicazione confronta le ore lavorate effettive con le ore previste a budget, 
organizzate per cliente e suddivise per periodi.
""")

# Dati di esempio (in una vera applicazione, questi verrebbero caricati da un file Excel)
@st.cache_data
def load_sample_data():
    # Creazione dati di esempio per il foglio Effettivo
    effettivo_data = {
        'cliente': ['Cliente A', 'Cliente A', 'Cliente B', 'Cliente B', 'Cliente C', 'Cliente C'],
        'data': pd.to_datetime(['2025-07-05', '2025-07-20', '2025-07-10', '2025-08-05', '2025-08-15', '2025-08-25']),
        'ore': [120, 85, 70, 0, 0, 95]
    }
    df_effettivo = pd.DataFrame(effettivo_data)
    
    # Creazione dati di esempio per il foglio Budget
    budget_data = {
        'cliente': ['Cliente A', 'Cliente A', 'Cliente B', 'Cliente B', 'Cliente C', 'Cliente C'],
        'periodo': ['2025-07', '2025-08', '2025-07', '2025-08', '2025-07', '2025-08'],
        'ore': [100, 100, 100, 0, 0, 80]
    }
    df_budget = pd.DataFrame(budget_data)
    
    return df_effettivo, df_budget

df_effettivo, df_budget = load_sample_data()

# Pre-processing dei dati
df_effettivo['mese'] = df_effettivo['data'].dt.to_period('M').astype(str)
df_effettivo['giorno'] = df_effettivo['data'].dt.day

# Creazione pivot per 1-15 e 1-fine mese
def create_pivot(df, day_threshold):
    if day_threshold == 15:
        df_filtered = df[df['giorno'] <= 15]
        period_label = "(1-15)"
    else:
        df_filtered = df
        period_label = "(1-31)"
    
    pivot = df_filtered.groupby(['cliente', 'mese'])['ore'].sum().reset_index()
    pivot['periodo'] = pivot['mese'] + f" {period_label}"
    return pivot.pivot(index='cliente', columns='periodo', values='ore').fillna(0)

pivot_15 = create_pivot(df_effettivo, 15)
pivot_31 = create_pivot(df_effettivo, 31)

# Unione dei pivot
df_effettivo_pivot = pd.concat([pivot_15, pivot_31], axis=1).fillna(0)

# Sezione 1: Scostamento Percentuale
st.header("1. Scostamento Percentuale")
st.markdown("Confronto percentuale tra ore effettive e ore a budget per cliente e periodo.")

# Calcolo dello scostamento percentuale
def calculate_percentage_diff(eff_df, bud_df):
    # Uniamo i dati effettivi e budget
    merged = pd.merge(eff_df.reset_index(), bud_df, on=['cliente', 'periodo'], how='outer').fillna(0)
    
    # Calcolo percentuale
    merged['scostamento_%'] = np.where(
        merged['ore_budget'] > 0,
        (merged['ore_effettivo'] - merged['ore_budget']) / merged['ore_budget'] * 100,
        np.where(
            merged['ore_budget'] == 0,
            np.where(merged['ore_effettivo'] > 0, 'Extrabudget', '0%'),
            '0%'
        )
    )
    
    return merged.pivot(index='cliente', columns='periodo', values='scostamento_%').fillna('0%')

# Creazione della tabella di scostamento
scostamenti = calculate_percentage_diff(
    df_effettivo_pivot.melt(var_name='periodo', value_name='ore_effettivo', ignore_index=False).reset_index(),
    df_budget.rename(columns={'ore': 'ore_budget'})
)

# Applicazione di stili condizionali
def color_scostamenti(val):
    if val == 'Extrabudget':
        return 'background-color: #8b5cf6; color: white'
    elif val == '0%':
        return 'background-color: #1e293b; color: white'
    elif isinstance(val, (int, float)):
        if val > 0:
            return 'background-color: #dcfce7; color: #166534'
        elif val < 0:
            return 'background-color: #fee2e2; color: #991b1b'
    return ''

st.dataframe(scostamenti.style.applymap(color_scostamenti))

# Sezione 2: Dati Dettagliati
st.header("2. Dati Dettagliati")
st.markdown("Visualizzazione combinata di ore effettive, ore a budget e scostamento percentuale.")

# Combinazione dei dati
dettagli = pd.merge(
    df_effettivo_pivot.melt(var_name='periodo', value_name='ore_effettivo', ignore_index=False).reset_index(),
    df_budget.rename(columns={'ore': 'ore_budget'}),
    on=['cliente', 'periodo'],
    how='outer'
).fillna(0)

dettagli['scostamento_%'] = np.where(
    dettagli['ore_budget'] > 0,
    (dettagli['ore_effettivo'] - dettagli['ore_budget']) / dettagli['ore_budget'] * 100,
    np.where(
        dettagli['ore_budget'] == 0,
        np.where(dettagli['ore_effettivo'] > 0, 'Extrabudget', '0%'),
        '0%'
    )
)

# Pivoting per visualizzazione
pivot_dettagli = dettagli.pivot(index='cliente', columns='periodo', values=['ore_effettivo', 'ore_budget', 'scostamento_%'])

st.dataframe(pivot_dettagli.style.applymap(
    lambda x: 'background-color: #8b5cf6; color: white' if x == 'Extrabudget' 
    else ('background-color: #1e293b; color: white' if x == '0%' 
    else ('background-color: #dcfce7; color: #166534' if isinstance(x, (int, float)) and x > 0 
    else ('background-color: #fee2e2; color: #991b1b' if isinstance(x, (int, float)) and x < 0 
    else ''))), subset=(slice(None), slice(None), 'scostamento_%')
))

# Sezione 3: Dashboard Riepilogativa
st.header("3. Dashboard Riepilogativa per Cliente")
st.markdown("Sommatoria totale delle ore effettive e di budget per cliente.")

# Aggregazione dati per cliente
dashboard_data = dettagli.groupby('cliente').agg({
    'ore_effettivo': 'sum',
    'ore_budget': 'sum'
}).reset_index()

dashboard_data['scostamento_%'] = np.where(
    dashboard_data['ore_budget'] > 0,
    (dashboard_data['ore_effettivo'] - dashboard_data['ore_budget']) / dashboard_data['ore_budget'] * 100,
    np.where(
        dashboard_data['ore_budget'] == 0,
        np.where(dashboard_data['ore_effettivo'] > 0, 'Extrabudget', '0%'),
        '0%'
    )
)

dashboard_data['scostamento_valore'] = dashboard_data['ore_effettivo'] - dashboard_data['ore_budget']

# Filtraggio clienti con dati
dashboard_data = dashboard_data[
    (dashboard_data['ore_effettivo'] > 0) | (dashboard_data['ore_budget'] > 0)
]

# Stile per la dashboard
def color_dashboard(val, col_name):
    if col_name == 'scostamento_%':
        if val == 'Extrabudget':
            return 'background-color: #8b5cf6; color: white'
        elif val == '0%':
            return 'background-color: #1e293b; color: white'
        elif isinstance(val, (int, float)):
            if val > 0:
                return 'background-color: #dcfce7; color: #166534'
            elif val < 0:
                return 'background-color: #fee2e2; color: #991b1b'
    elif col_name == 'scostamento_valore':
        if isinstance(val, str) and 'Extrabudget' in val:
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
ax.set_xticklabels(chart_data['cliente'])
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
                        ha='center', va='bottom')

add_value_labels(bars1)
add_value_labels(bars2)
add_value_labels(bars3)

plt.tight_layout()
st.pyplot(fig)

# Informazioni aggiuntive
st.sidebar.header("Informazioni")
st.sidebar.markdown("""
- **Verde**: Ore effettive superiori al budget
- **Rosso**: Ore effettive inferiori al budget
- **Viola**: Ore extrabudget (non previste a budget)
- **Nero**: Nessuna attività registrata
""")

st.sidebar.header("Istruzioni")
st.sidebar.markdown("""
1. Carica i tuoi dati Excel usando il file uploader
2. I dati devono contenere due fogli:
   - `Effettivo`: con colonne cliente, data, ore
   - `Budget`: con colonne cliente, periodo, ore
3. L'applicazione calcolerà automaticamente gli scostamenti
""")
