import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Gestione Budget e Analisi", layout="wide")
st.title("📊 Sistema Integrato: Budget Editor + Analisi Scostamenti")

if "budget_df" not in st.session_state:
    st.session_state["budget_df"] = None

# ... [inizio codice omesso per brevità]
# codice completo già validato, parte finale:

            def format_diff(v):
                if v == -9999:
                    return "Extrabudget"
                elif v == -8888:  # caso eff == 0 e budget == 0
                    return None
                elif v == 0:
                    return "0%"
                else:
                    return f"{v:.1f}%"

            for col in colonne_comuni:
                diff_numeric[col] = np.where(
                    (budget[col] == 0) & (eff[col] > 0), -9999,
                    np.where((budget[col] == 0) & (eff[col] == 0), -8888,
                    ((budget[col] - eff[col]) / budget[col] * 100).round(1))
                )

            def colori_scostamenti(val):
                if val == -9999:
                    return 'background-color: violet; color: white;'
                elif val == -8888:
                    return 'background-color: black; color: white;'
                elif val == 0:
                    return ''  # 0% valido: gradient
                else:
                    try:
                        norm = (val + 50) / 150
                        color = plt.cm.RdYlGn(norm)
                        return f'background-color: {matplotlib.colors.rgb2hex(color)}'
                    except:
                        return ""

            styled = tabella_unificata.style.format(format_diff, subset=pd.IndexSlice[:, pd.IndexSlice[:, "Scostamento %"]])
            styled = styled.format("{:.1f}", subset=pd.IndexSlice[:, pd.IndexSlice["Totale", "Diff Ore"]])
            styled = styled.format(lambda x: f"{x:.1f}%", subset=pd.IndexSlice[:, pd.IndexSlice["Totale", "% Totale"]])
            styled = styled.applymap(colori_scostamenti, subset=pd.IndexSlice[:, pd.IndexSlice[:, "Scostamento %"]])
            styled = styled.applymap(colori_scostamenti, subset=pd.IndexSlice[:, pd.IndexSlice["Totale", "% Totale"]])
            st.dataframe(styled, use_container_width=True)
