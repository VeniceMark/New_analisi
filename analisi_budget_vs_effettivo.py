# Versione aggiornata: categorie obbligatorie + filtri avanzati + tabelle comparative ripristinate
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

# ------------------------------
# Helper
# ------------------------------
COL_PATTERN = re.compile(r"^(?P<y>\d{4})-(?P<m>\d{2}) \((?P<half>1-15|1-fine)\)$")

def parse_col(col: str):
    m = COL_PATTERN.match(col)
    if not m:
        return None
    return int(m.group("y")), int(m.group("m")), m.group("half")

def colori_scostamenti(val):
    if val == "Extrabudget":
        return 'background-color: violet; color: white;'
    elif val == "Zero":
        return 'background-color: black; color: white;'
    else:
        try:
            val_float = float(val.strip('%'))
            norm = (val_float + 50) / 150  # -50% => 0.0 ; +100% => 1.0
            norm = max(0.0, min(1.0, norm))
            color = plt.cm.RdYlGn(norm)
            return f'background-color: {matplotlib.colors.rgb2hex(color)}'
        except:
            return ""

# ------------------------------
# BUDGET EDITOR
# ------------------------------
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

# ------------------------------
# ANALISI SCOSTAMENTI
# ------------------------------
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
            # ---- Effettivo
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

            # ---- Budget
            df_budget = df_budget.copy()
            df_budget.columns = df_budget.columns.str.strip()
            cliente_col = next((c for c in df_budget.columns if c.lower()=="cliente"), None)
            if not cliente_col:
                st.error("Nel file Budget manca la colonna 'cliente'.")
                st.stop()
            if "categoria_cliente" not in [c.lower() for c in df_budget.columns]:
                df_budget["categoria_cliente"] = ""
            df_budget = df_budget.set_index(cliente_col)

            # colonne valide tipo "YYYY-MM (1-15) | (1-fine)"
            pattern = re.compile(r"^\d{4}-\d{2} \(1-(15|fine)\)$")
            colonne_valide = [col for col in df_budget.columns if pattern.match(col)]
            colonne_comuni = df_eff_tot.columns.intersection(colonne_valide)

            # indici: unione
            idx_union = sorted(set(df_budget.index.astype(str)).union(set(df_eff_tot.index.astype(str))))
            eff = df_eff_tot.reindex(index=idx_union, columns=colonne_comuni, fill_value=0)
            budget = df_budget.reindex(index=idx_union, columns=colonne_comuni, fill_value=0)

            # ---- Gate: categorizzazione obbligatoria per clienti senza categoria
            cat_series = df_budget.reindex(index=idx_union)["categoria_cliente"].fillna("")
            missing_cat = [c for c in idx_union if (c not in df_budget.index) or (str(cat_series.get(c, "")).strip() == "")]
            if missing_cat:
                st.error("⚠ Alcuni clienti non hanno categoria assegnata. Devi completare prima di procedere:")
                nuove_cat = {}
                for cliente in missing_cat:
                    nuove_cat[cliente] = st.selectbox(f"Categoria per '{cliente}'", ["", "Ricorrente", "Progetto", "Interno", "Altro"], key=f"cat_{cliente}")
                if st.button("Conferma categorie e procedi"):
                    for cliente, cat in nuove_cat.items():
                        if cat:
                            if cliente in df_budget.index:
                                df_budget.loc[cliente, "categoria_cliente"] = cat
                            else:
                                # crea nuova riga per il cliente solo-effettivo
                                new_row = pd.Series({col: 0 for col in df_budget.columns}, name=cliente)
                                new_row["categoria_cliente"] = cat
                                df_budget = pd.concat([df_budget, new_row.to_frame().T])
                    # persiste in sessione e riavvia
                    st.session_state["budget_df"] = df_budget.reset_index().rename(columns={"index": "cliente"})
                    # rerun compatibile
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
                st.stop()

            # ---- Scostamenti % (stringhe con colori)
            diff_percent = pd.DataFrame(index=eff.index, columns=colonne_comuni, dtype=object)
            for col in colonne_comuni:
                diff_percent[col] = np.where(
                    (budget[col] == 0) & (eff[col] > 0), "Extrabudget",
                    np.where((budget[col] == 0) & (eff[col] == 0), "Zero",
                    ((budget[col] - eff[col]) / budget[col] * 100).round(1).astype(str) + "%")
                )

            # ---- FILTRI AVANZATI (sidebar)
            # Cliente
            clienti_opzioni = ["Tutti i clienti"] + list(eff.index.astype(str))
            selezione_cliente = st.sidebar.selectbox("Filtro cliente", clienti_opzioni, index=0)

            # Categoria
            cat_map = df_budget["categoria_cliente"].astype(str)
            categorie_disponibili = sorted([c for c in cat_map.unique() if c])
            sel_categorie = st.sidebar.multiselect("Filtra per categoria", options=categorie_disponibili, default=categorie_disponibili)

            # Anno & Mese + mezze colonne
            years_available = sorted({parse_col(c)[0] for c in colonne_comuni if parse_col(c)})
            months_available = sorted({parse_col(c)[1] for c in colonne_comuni if parse_col(c)})
            sel_years = st.sidebar.multiselect("Anni", options=years_available, default=years_available)
            sel_months = st.sidebar.multiselect("Mesi", options=months_available, default=months_available)
            include_115 = st.sidebar.checkbox("Includi colonne 1-15", value=True)
            include_1fine = st.sidebar.checkbox("Includi colonne 1-fine", value=True)

            def col_selected(col):
                p = parse_col(col)
                if not p:
                    return False
                y, m, half = p
                if y not in sel_years or m not in sel_months:
                    return False
                if half == "1-15" and not include_115:
                    return False
                if half == "1-fine" and not include_1fine:
                    return False
                return True

            selected_cols = [c for c in colonne_comuni if col_selected(c)]

            # Filtra clientela per cliente o per categorie
            if selezione_cliente != "Tutti i clienti":
                idx = [selezione_cliente]
            else:
                idx = [c for c in eff.index if cat_map.get(c, "") in sel_categorie]

            eff_f = eff.loc[idx, selected_cols] if selected_cols else eff.loc[idx, colonne_comuni]
            budget_f = budget.loc[idx, selected_cols] if selected_cols else budget.loc[idx, colonne_comuni]
            diff_percent_f = diff_percent.loc[idx, selected_cols] if selected_cols else diff_percent.loc[idx, colonne_comuni]

            # ---- SEZIONE: Heatmap scostamenti %
            st.subheader("\U0001F4C8 Scostamento percentuale tra Budget e Ore Effettive")
            styled_diff = diff_percent_f.style.applymap(colori_scostamenti)
            styled_diff = styled_diff.format(lambda v: "0%" if v == "Zero" else v)
            st.dataframe(styled_diff, use_container_width=True)

            # ---- SEZIONE: Dati Dettagliati (comparativa completa ripristinata)
            st.subheader("\U0001F4CB Dati Dettagliati (Effettivo / Budget / Scostamento %)")
            df_view = pd.concat([eff_f, budget_f, diff_percent_f], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
            scostamento_cols = [col for col in df_view.columns if isinstance(col, tuple) and col[0] == "Scostamento %"]
            styled_view = df_view.style.applymap(colori_scostamenti, subset=pd.IndexSlice[:, scostamento_cols])
            styled_view = styled_view.format(lambda v: "0%" if v == "Zero" else v, subset=pd.IndexSlice[:, scostamento_cols])
            st.dataframe(styled_view, use_container_width=True)

            # ---- SEZIONE: Dashboard riepilogativa per cliente
            st.subheader("\U0001F4CA Dashboard riepilogativa per cliente")
            # Considera solo '(1-fine)' per il riepilogo mensile e totale sensato
            cols_fine = [c for c in eff_f.columns if parse_col(c) and parse_col(c)[2] == "1-fine"]
            # Se non selezionato 1-fine ma 1-15 presente, calcolo su 1-15 come fallback
            if not cols_fine:
                cols_fine = [c for c in eff_f.columns if parse_col(c) and parse_col(c)[2] == "1-15"]
            dashboard = pd.DataFrame({
                "Ore Effettive": eff_f[cols_fine].sum(axis=1) if len(cols_fine)>0 else eff_f.sum(axis=1),
                "Ore a Budget": budget_f[cols_fine].sum(axis=1) if len(cols_fine)>0 else budget_f.sum(axis=1),
                "Categoria": [cat_map.get(c, "") for c in eff_f.index]
            }, index=eff_f.index)
            dashboard["Scostamento %"] = np.where(
                dashboard["Ore a Budget"] > 0,
                ((dashboard["Ore a Budget"] - dashboard["Ore Effettive"]) / dashboard["Ore a Budget"] * 100).round(1),
                np.where(dashboard["Ore Effettive"] > 0, -9999, 0)
            )
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

            # ---- SEZIONE: Riepilogo mensile (comparativa complessiva ripristinata)
            st.subheader("\U0001F5C3\uFE0F Riepilogo mensile (solo 1-fine)")
            # raggruppo per mese (base y-m) usando 1-fine come riferimento
            base_months = sorted({(parse_col(c)[0], parse_col(c)[1]) for c in budget_f.columns if parse_col(c) and parse_col(c)[2]=="1-fine"})
            rows = []
            for y,m in base_months:
                col = f"{y}-{m:02d} (1-fine)"
                be = budget_f[col].sum()
                ee = eff_f[col].sum()
                sc_ore = be - ee
                sc_perc = (sc_ore / be * 100).round(1) if be>0 else (-9999 if ee>0 else 0)
                rows.append({"Anno-Mese": f"{y}-{m:02d}", "Ore a Budget": be, "Ore Effettive": ee, "Scostamento ore": sc_ore, "Scostamento %": sc_perc})
            riepilogo_mensile = pd.DataFrame(rows).set_index("Anno-Mese")
            def fmt_p(v):
                return "Extrabudget" if v == -9999 else ("0%" if v == 0 else f"{v:.1f}%")
            if not riepilogo_mensile.empty:
                riepilogo_mensile["Scostamento % (str)"] = riepilogo_mensile["Scostamento %"].apply(fmt_p)
                styled_riep = riepilogo_mensile.style.applymap(colori_scostamenti, subset=["Scostamento % (str)"])
                st.dataframe(styled_riep, use_container_width=True)
            else:
                st.info("Nessuna colonna 1-fine selezionata per costruire il riepilogo mensile. Abilita 'Includi colonne 1-fine' nella sidebar.")

            # ---- Download del Budget aggiornato (con categorie eventualmente assegnate)
            st.divider()
            st.caption("Esporta Budget aggiornato (inclusa 'categoria_cliente')")
            buf = BytesIO()
            st.session_state["budget_df"].to_excel(buf, index=False)
            st.download_button("⬇️ Scarica Budget aggiornato", data=buf.getvalue(), file_name="budget_aggiornato_categorie.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {e}")
