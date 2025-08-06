# Analisi Budget vs Effettivo

Questa applicazione Streamlit consente di confrontare le ore lavorate effettive con le ore previste a budget, organizzate per cliente e suddivise per periodi.

## Funzionalità

- Caricamento di file Excel con due fogli: "Effettivo" e "Budget"
- Calcolo degli scostamenti percentuali tra budget e consuntivo
- Visualizzazione tabellare con codifica colori
- Dashboard riepilogativa per cliente
- Grafico a barre comparativo

## Struttura del file Excel

Il file Excel deve contenere due fogli:

### Foglio "Effettivo"
| cliente | data       | ore |
|---------|------------|-----|
| Cliente A | 2025-07-05 | 120 |
| Cliente B | 2025-07-10 | 70  |

### Foglio "Budget"
| cliente | periodo  | ore |
|---------|----------|-----|
| Cliente A | 2025-07  | 100 |
| Cliente B | 2025-07  | 100 |

## Come eseguire l'applicazione

1. Clona questa repository
2. Installa le dipendenze: `pip install -r requirements.txt`
3. Esegui l'applicazione: `streamlit run app.py`

## Deploy su Streamlit Cloud

1. Crea un account su [Streamlit Cloud](https://streamlit.io/cloud)
2. Connetti il tuo repository GitHub
3. Configura l'applicazione puntando a `app.py`