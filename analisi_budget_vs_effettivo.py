# Versione corretta per gestione colorazione scostamenti
# Modifica isolata alla sezione "diff_percent" + funzione "colori_scostamenti"

import numpy as np
import matplotlib.pyplot as plt
import matplotlib

# Calcolo dello scostamento percentuale con nuova logica
diff_percent = pd.DataFrame(index=budget.index, columns=budget.columns, dtype=object)

for col in colonne_comuni:
    diff_percent[col] = np.where(
        (budget[col] == 0) & (eff[col] > 0), "Extrabudget",
        np.where((budget[col] == 0) & (eff[col] == 0), "Zero",
        ((budget[col] - eff[col]) / budget[col] * 100).round(1).astype(str) + "%")
    )

# Funzione di colorazione corretta
def colori_scostamenti(val):
    if val == "Extrabudget":
        return 'background-color: violet; color: white;'
    elif val == "Zero":
        return 'background-color: black; color: white;'
    else:
        try:
            val_float = float(val.strip('%'))
            norm = (val_float + 50) / 150
            color = plt.cm.RdYlGn(norm)
            return f'background-color: {matplotlib.colors.rgb2hex(color)}'
        except:
            return ""

# ATTENZIONE: ricordarsi di aggiornare anche l'uso di "0%" nei dataframe
# dove si applica colori_scostamenti: vanno sostituiti i "0%" con "Zero" prima di mostrare
# oppure gestiti in visualizzazione con un mapping: df.replace("Zero", "0%") se necessario
