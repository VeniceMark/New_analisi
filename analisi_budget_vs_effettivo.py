# Versione aggiornata: categorizzazione clienti obbligatoria per clienti solo-effettivo
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Gestione Budget e Analisi", layout="wide")
st.title("\U0001F4CA Sistema Integrato: Budget Editor + Analisi Scostamenti")

if "budget_df" not in st.session_state:
    st.session_state["budget_df"] = None

sezione = st.sidebar.radio("Vai a:", ["\U0001F4DD Budget Editor", "\U0001F4C8 Analisi Scostamenti"])

if sezione == "\U0001F4DD Budget Editor":
    st.header("\U0001F4DD Budget Editor – Inserimento e Calcolo Slot")

    uploaded_budget = st.file_uploader("\U0001F4C4 Carica un file Budget esistente (opzionale)", type=["xlsx"])
    if uploaded_budget:
        try:
            df = pd.read_excel(uploaded_budget)
            df.columns = df.columns.str.strip()
            if "cliente" not in [c.lower() for c in df.columns]:
                st.error("Il file Budget deve contenere la colonna 'cliente'.")
                st.stop()
            if "categoria_cliente" not in [c.lower() for c in df.columns]:
                st.warning("Il file Budget non contiene la colonna 'categoria_cliente'. Verrà aggiunta vuota.")
                df["categoria_cliente"] = ""
            st.session_state["budget_df"] = df
            st.success("✅ File budget caricato correttamente.")
        except Exception as e:
            st.error(f"Errore nel caricamento: {e}")

    st.subheader("➕ Nuovo Cliente")
    with st.form("aggiungi_cliente"):
        nuovo_cliente = st.text_input("Nome Cliente").strip()
        categoria_cliente = st.selectbox("Categoria Cliente", ["", "Ricorrente", "Progetto", "Interno", "Altro"])
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
        if submitted and nuovo_cliente and categoria_cliente and anni and mesi:
            record = {"cliente": nuovo_cliente, "categoria_cliente": categoria_cliente}
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
            label="\U0001F4C5 Scarica file Budget aggiornato",
            data=buffer.getvalue(),
            file_name="budget_generato.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Carica un file o aggiungi un cliente per iniziare.")

elif sezione == "\U0001F4C8 Analisi Scostamenti":
    st.header("\U0001F4C8 Analisi Scostamenti Budget vs Effettivo")
    uploaded_eff = st.file_uploader("\U0001F4C5 Carica file 'Effettivo' (obbligatorio)", type=["xlsx"])
    if st.session_state["budget_df"] is not None:
        df_budget = st.session_state["budget_df"]
        st.success("✅ Usando il file Budget generato nella sessione.")
    else:
        uploaded_budget = st.file_uploader("\U0001F4C5 Carica file 'Budget' (alternativo)", type=["xlsx"])
        if uploaded_budget:
            df_budget = pd.read_excel(uploaded_budget)
            if "categoria_cliente" not in [c.lower() for c in df_budget.columns]:
                df_budget["categoria_cliente"] = ""
        else:
            df_budget = None

    if uploaded_eff and df_budget is not None:
        try:
            df_eff = pd.read_excel(uploaded_eff, sheet_name="Effettivo")
            df_eff.columns = df_eff.columns.str.strip().str.lower()
            df_eff['data'] = pd.to_datetime(df_eff['data'], errors='coerce', dayfirst=True)
            df_eff['mese'] = df_eff['data'].dt.to_period('M').astype(str)
            df_eff['giorno'] = df_eff['data'].dt.day
            pivot_1_15 = df_eff[df_eff['giorno'] <= 15].pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_15.columns = [f"{col} (1-15)" for col in pivot_1_15.columns]
            pivot_1_fine = df_eff.pivot_table(index='cliente', columns='mese', values='ore', aggfunc='sum', fill_value=0)
            pivot_1_fine.columns = [f"{col} (1-fine)" for col in pivot_1_fine.columns]
            df_eff_tot = pd.concat([pivot_1_15, pivot_1_fine], axis=1).fillna(0)
            df_eff_tot = df_eff_tot.reindex(sorted(df_eff_tot.columns), axis=1)
            df_eff_tot.index = df_eff_tot.index.astype(str)

            cliente_col = next((c for c in df_budget.columns if c.lower()=="cliente"), None)
            df_budget = df_budget.set_index(cliente_col).fillna(0)
            pattern = re.compile(r"^\d{4}-\d{2} \(1-(15|fine)\)$")
            colonne_valide = [col for col in df_budget.columns if pattern.match(col)]
            colonne_comuni = df_eff_tot.columns.intersection(colonne_valide)

            idx_union = sorted(set(df_budget.index.astype(str)).union(set(df_eff_tot.index.astype(str))))
            eff = df_eff_tot.reindex(index=idx_union, columns=colonne_comuni, fill_value=0)
            budget = df_budget.reindex(index=idx_union, columns=colonne_comuni, fill_value=0)

            # Controllo clienti senza categoria
            if "categoria_cliente" not in [c.lower() for c in df_budget.columns]:
                df_budget["categoria_cliente"] = ""
            clienti_senza_cat = [c for c in idx_union if (c not in df_budget.index) or (df_budget.loc[c, "categoria_cliente"] == "")]
            if clienti_senza_cat:
                st.error("⚠ Alcuni clienti non hanno categoria assegnata. Devi completare prima di procedere:")
                nuove_cat = {}
                for cliente in clienti_senza_cat:
                    nuove_cat[cliente] = st.selectbox(f"Categoria per '{cliente}'", ["", "Ricorrente", "Progetto", "Interno", "Altro"], key=f"cat_{cliente}")
                if st.button("Conferma categorie e procedi"):
                    for cliente, cat in nuove_cat.items():
                        if cat:
                            if cliente in df_budget.index:
                                df_budget.loc[cliente, "categoria_cliente"] = cat
                            else:
                                new_row = pd.Series({col: 0 for col in df_budget.columns}, name=cliente)
                                new_row["categoria_cliente"] = cat
                                df_budget = pd.concat([df_budget, new_row.to_frame().T])
                    st.session_state["budget_df"] = df_budget.reset_index().rename(columns={"index": "cliente"})
                    (
                        st.rerun() if hasattr(st, 'rerun') else st.experimental_rerun()
                    )
                st.stop()

            diff_percent = pd.DataFrame(index=eff.index, columns=colonne_comuni, dtype=object)
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
                        norm = max(0.0, min(1.0, norm))
                        color = plt.cm.RdYlGn(norm)
                        return f'background-color: {matplotlib.colors.rgb2hex(color)}'
                    except:
                        return ""

            colonne_budget_fine = [col for col in budget.columns if "(1-fine)" in col]
            colonne_effettivo_fine = [col for col in eff.columns if "(1-fine)" in col]

            dashboard = pd.DataFrame({
                "Ore Effettive": eff[colonne_effettivo_fine].sum(axis=1),
                "Ore a Budget": budget[colonne_budget_fine].sum(axis=1),
                "Categoria": [df_budget.loc[c, "categoria_cliente"] if c in df_budget.index else "" for c in eff.index]
            })
            dashboard["Scostamento %"] = np.where(
                dashboard["Ore a Budget"] > 0,
                ((dashboard["Ore a Budget"] - dashboard["Ore Effettive"]) / dashboard["Ore a Budget"] * 100).round(1),
                np.where(dashboard["Ore Effettive"] > 0, -9999, 0)
            )
            dashboard = dashboard[~((dashboard["Ore Effettive"] == 0) & (dashboard["Ore a Budget"] == 0))]

            clienti_opzioni = ["Tutti i clienti"] + list(dashboard.index.astype(str))
            selezione_cliente = st.sidebar.selectbox("Filtro cliente (dashboard)", clienti_opzioni, index=0)

            if selezione_cliente != "Tutti i clienti":
                idx = [selezione_cliente]
            else:
                idx = list(dashboard.index.astype(str))

            eff_f = eff.loc[eff.index.isin(idx)]
            budget_f = budget.loc[budget.index.isin(idx)]
            diff_percent_f = diff_percent.loc[diff_percent.index.isin(idx)]
            dashboard_f = dashboard.loc[dashboard.index.isin(idx)]

            def format_scostamento(val):
                if val == -9999:
                    return "Extrabudget"
                elif val == 0:
                    return "0%"
                else:
                    return f"{val:.1f}%"

            st.subheader("\U0001F4C8 Scostamento percentuale tra Budget e Ore Effettive")
            styled_diff = diff_percent_f.style.applymap(colori_scostamenti)
            styled_diff = styled_diff.format(lambda v: "0%" if v == "Zero" else v)
            st.dataframe(styled_diff, use_container_width=True)

            st.subheader("\U0001F4CB Dashboard riepilogativa per cliente")
            dashboard_f["Scostamento % (str)"] = dashboard_f["Scostamento %"].apply(format_scostamento)
            styled_dashboard = dashboard_f.style.applymap(colori_scostamenti, subset=["Scostamento % (str)"])
            st.dataframe(styled_dashboard, use_container_width=True)

        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {e}")
