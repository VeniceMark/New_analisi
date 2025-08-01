
# File aggiornato con la dashboard riepilogativa per cliente
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

sezione = st.sidebar.radio("Vai a:", ["📝 Budget Editor", "📈 Analisi Scostamenti"])

if sezione == "📝 Budget Editor":
    st.header("📝 Budget Editor – Inserimento e Calcolo Slot")

    uploaded_budget = st.file_uploader("📤 Carica un file Budget esistente (opzionale)", type=["xlsx"])
    if uploaded_budget:
        try:
            df = pd.read_excel(uploaded_budget)
            st.session_state["budget_df"] = df
            st.success("✅ File budget caricato correttamente.")
        except Exception as e:
            st.error(f"Errore nel caricamento: {e}")

    st.subheader("➕ Nuovo Cliente")

    with st.form("aggiungi_cliente"):
        nuovo_cliente = st.text_input("Nome Cliente").strip()
        anni = st.multiselect("Anni da includere", options=list(range(2024, 2036)), default=[datetime.now().year])
        mesi = st.multiselect("Mesi da includere", options=list(range(1, 13)), default=list(range(1, 13)))

        coeff = st.number_input("Coefficiente", min_value=1, max_value=100, value=50)
        try:
            budget_mensile = float(st.text_input("Budget mensile (numero)", value="0"))
        except:
            budget_mensile = 0.0
        try:
            xselling = float(st.text_input("Beget Xselling (numero)", value="0"))
        except:
            xselling = 0.0

        submitted = st.form_submit_button("Aggiungi Cliente")

        if submitted and nuovo_cliente and anni and mesi:
            record = {"cliente": nuovo_cliente}
            for anno in anni:
                for mese in mesi:
                    base = f"{anno}-{mese:02d}"
                    totale = (budget_mensile + xselling) / coeff if coeff > 0 else 0
                    slot_1_fine = round(totale, 2)
                    slot_1_15 = round(totale / 2, 2)

                    record[f"{base}_coeff"] = coeff
                    record[f"{base}_budget_mensile"] = budget_mensile
                    record[f"{base}_xselling"] = xselling
                    record[f"{base} (1-15)"] = slot_1_15
                    record[f"{base} (1-fine)"] = slot_1_fine

            nuovo_df = pd.DataFrame([record])

            if st.session_state["budget_df"] is not None:
                st.session_state["budget_df"] = pd.concat([st.session_state["budget_df"], nuovo_df], ignore_index=True)
            else:
                st.session_state["budget_df"] = nuovo_df
            st.success(f"Cliente '{nuovo_cliente}' aggiunto!")

    if st.session_state["budget_df"] is not None:
        st.subheader("✏️ Modifica diretta del Budget")
        edited_df = st.data_editor(st.session_state["budget_df"], use_container_width=True, num_rows="dynamic")
        st.session_state["budget_df"] = edited_df

        buffer = BytesIO()
        edited_df.to_excel(buffer, index=False)
        st.download_button(
            label="📥 Scarica file Budget aggiornato",
            data=buffer.getvalue(),
            file_name="budget_generato.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Carica un file o aggiungi un cliente per iniziare.")

elif sezione == "📈 Analisi Scostamenti":
    st.header("📈 Analisi Scostamenti Budget vs Effettivo")

    uploaded_eff = st.file_uploader("📥 Carica file 'Effettivo' (obbligatorio)", type=["xlsx"])
    if st.session_state["budget_df"] is not None:
        df_budget = st.session_state["budget_df"]
        st.success("✅ Usando il file Budget generato nella sessione.")
    else:
        uploaded_budget = st.file_uploader("📥 Carica file 'Budget' (alternativo)", type=["xlsx"])
        if uploaded_budget:
            df_budget = pd.read_excel(uploaded_budget)
        else:
            df_budget = None

    df_budget = df_budget.set_index("cliente").fillna(0)
    colonne_periodi_valide = [col for col in df_budget.columns if re.match(r"^\d{4}-\d{2} \(1-(15|fine)\)$", col)]
    periodo_scelto = st.sidebar.selectbox("🎯 Seleziona periodo da analizzare", ["Tutto"] + sorted(colonne_periodi_valide))
    clienti_lista = sorted(df_budget.index.astype(str).unique())
    cliente_scelto = st.sidebar.selectbox("👤 Filtra per cliente", ["Tutti"] + clienti_lista)
    if uploaded_eff and df_budget is not None:
        try:
            df_eff = pd.read_excel(uploaded_eff, sheet_name="Effettivo")
            df_eff.columns = df_eff.columns.str.strip().str.lower()
            df_eff['data'] = pd.to_datetime(df_eff['data'], format='%d-%m-%Y', errors='coerce')
            df_eff['mese'] = df_eff['data'].dt.to_period('M').astype(str)
            df_eff['giorno'] = df_eff['data'].dt.day

            pivot_1_15 = df_eff[df_eff['giorno'] <= 15].pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_15.columns = [f"{col} (1-15)" for col in pivot_1_15.columns]

            pivot_1_fine = df_eff.pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_fine.columns = [f"{col} (1-fine)" for col in pivot_1_fine.columns]

            df_eff_tot = pd.concat([pivot_1_15, pivot_1_fine], axis=1).fillna(0)
            df_eff_tot = df_eff_tot.reindex(sorted(df_eff_tot.columns), axis=1)
            df_eff_tot.index = df_eff_tot.index.astype(str)

            if 'cliente' in df_budget.columns:
                df_budget = df_budget.set_index('cliente')
            elif df_budget.index.name != 'cliente':
                st.error("❌ Il foglio 'Budget' deve contenere una colonna chiamata 'cliente'.")
                st.stop()
            df_budget = df_budget.fillna(0)
            pattern = re.compile(r"^\d{4}-\d{2} \(1-(15|fine)\)$")
            colonne_valide = [col for col in df_budget.columns if pattern.match(col)]

            clienti_comuni = df_eff_tot.index.union(df_budget.index)
            colonne_comuni = df_eff_tot.columns.intersection(colonne_valide)
            if periodo_scelto != "Tutto":
                colonne_comuni = [periodo_scelto]
            if periodo_scelto != "Tutto":
                colonne_comuni = [periodo_scelto]

            eff = df_eff_tot.reindex(index=clienti_comuni, columns=colonne_comuni, fill_value=0)
            budget = df_budget.reindex(index=clienti_comuni, columns=colonne_comuni, fill_value=0)
            if cliente_scelto != "Tutti":
                eff = eff.loc[[cliente_scelto]] if cliente_scelto in eff.index else eff.iloc[0:0]
                budget = budget.loc[[cliente_scelto]] if cliente_scelto in budget.index else budget.iloc[0:0]

            diff_percent = pd.DataFrame(index=budget.index, columns=budget.columns, dtype=object)

            for col in colonne_comuni:
                diff_percent[col] = np.where(
                    (budget[col] == 0) & (eff[col] > 0), "Extrabudget",
                    np.where((budget[col] == 0) & (eff[col] == 0), "Zero",
                    ((budget[col] - eff[col]) / budget[col] * 100).round(1).astype(str) + "%")
                )

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

            st.subheader("📈 Scostamento percentuale tra Budget e Ore Effettive")

            # Manteniamo 'Zero' per la colorazione, ma visualizziamo come '0%%'
            styled_diff = diff_percent.style.applymap(colori_scostamenti)
            styled_diff = styled_diff.format(lambda v: "0%" if v == "Zero" else v)
            st.dataframe(styled_diff, use_container_width=True)

            st.subheader("📋 Dati Dettagliati")
            df_view = pd.concat([eff, budget, diff_percent], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)

            styled_view = df_view.style.applymap(colori_scostamenti, subset=pd.IndexSlice[("Scostamento %", *colonne_comuni)])
            styled_view = styled_view.format(lambda v: "0%" if v == "Zero" else v, subset=pd.IndexSlice[("Scostamento %", *colonne_comuni)])
            st.dataframe(styled_view, use_container_width=True)

            # ➕ Nuova sezione: dashboard riepilogativa per cliente
            st.subheader("📊 Dashboard riepilogativa per cliente")
            dashboard = pd.DataFrame({
                "Ore Effettive": eff.sum(axis=1),
                "Ore a Budget": budget.sum(axis=1)
            })
            dashboard["Scostamento Valore (ore)"] = dashboard["Ore a Budget"] - dashboard["Ore Effettive"]
            dashboard["Scostamento %"] = np.where(
                dashboard["Ore a Budget"] > 0,
                ((dashboard["Ore a Budget"] - dashboard["Ore Effettive"]) / dashboard["Ore a Budget"] * 100).round(1),
                np.where(dashboard["Ore Effettive"] > 0, -9999, 0)
            )
            dashboard = dashboard[~((dashboard["Ore Effettive"] == 0) & (dashboard["Ore a Budget"] == 0))]
            dashboard = dashboard.sort_values(by="Scostamento %", ascending=True)

            def format_scostamento(val):
                if val == -9999:
                    return "Extrabudget"
                elif val == 0:
                    return "0%"
                else:
                    return f"{val:.1f}%"

            dashboard["Scostamento % (str)"] = dashboard["Scostamento %"].apply(format_scostamento)
            styled_dashboard = dashboard.style.applymap(colori_scostamenti, subset=["Scostamento % (str)"])
            st.dataframe(styled_dashboard, use_container_width=True)

        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {e}")
