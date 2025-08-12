# v3.1 - Analisi Budget vs Effettivo (toggle Categoria/Anno/Mese per anno)
# Estende v3.0 con:
# - Toggle per categorie (on/off per ciascuna)
# - Selezione per-anno con toggle e 12 toggle mese (1..12) per ogni anno
# - Mantiene tutte le viste e le protezioni della v3

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Analisi Budget vs Effettivo (v3.1)", layout="wide")
st.markdown("### 📊 Analisi Budget vs Effettivo — **v3.1**")

if "budget_df" not in st.session_state:
    st.session_state["budget_df"] = None

# ------------------------------
# Helper
# ------------------------------
COL_PATTERN = re.compile(r"^(?P<y>\d{4})-(?P<m>\d{2}) \((?P<half>1-15|1-fine)\)$")

def parse_col(col: str):
    m = COL_PATTERN.match(str(col))
    if not m:
        return None
    return int(m.group("y")), int(m.group("m")), m.group("half")

def colori_scostamenti(val):
    if isinstance(val, str) and val.strip().lower().startswith("extrabudget"):
        return 'background-color: violet; color: white;'
    if isinstance(val, str) and val.strip().lower() == "zero":
        return 'background-color: black; color: white;'
    try:
        val_float = float(str(val).replace("%","").strip())
        norm = (val_float + 50) / 150  # -50% => 0.0 ; +100% => 1.0
        norm = max(0.0, min(1.0, norm))
        color = plt.cm.RdYlGn(norm)
        return f'background-color: {matplotlib.colors.rgb2hex(color)}'
    except:
        return ""

def ui_toggle(label: str, value: bool, key: str):
    # Versione sidebar: usa i widget della sidebar
    if hasattr(st.sidebar, "toggle"):
        return st.sidebar.toggle(label, value=value, key=key)
    return st.sidebar.checkbox(label, value=value, key=key)

def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ------------------------------
# Sidebar Nav
# ------------------------------
sezione = st.sidebar.radio("Vai a:", ["📝 Budget Editor", "📈 Analisi Scostamenti"])

# ------------------------------
# BUDGET EDITOR
# ------------------------------
if sezione == "📝 Budget Editor":
    st.header("📝 Budget Editor – Inserimento e Calcolo Slot")

    uploaded_budget = st.file_uploader("📄 Carica un file Budget esistente (opzionale)", type=["xlsx"])
    if uploaded_budget:
        try:
            df = pd.read_excel(uploaded_budget)
            df.columns = df.columns.str.strip()
            cliente_col = next((c for c in df.columns if c.lower()=="cliente"), None)
            if not cliente_col:
                st.error("Il file Budget deve contenere la colonna 'cliente'.")
                st.stop()
            cat_col = next((c for c in df.columns if c.lower()=="categoria_cliente"), None)
            if not cat_col:
                st.warning("Nel Budget manca la colonna 'categoria_cliente'. Verrà aggiunta vuota.")
                df["categoria_cliente"] = ""
            elif cat_col != "categoria_cliente":
                df = df.rename(columns={cat_col: "categoria_cliente"})
            st.session_state["budget_df"] = df
            st.success("✅ File Budget caricato.")
        except Exception as e:
            st.error(f"Errore nel caricamento Budget: {e}")

    st.subheader("➕ Nuovo Cliente")
    with st.form("aggiungi_cliente"):
        nuovo_cliente = st.text_input("Nome Cliente").strip()
        categoria_cliente = st.selectbox("Categoria Cliente", ["", "Ricorrente", "Progetto", "Interno", "Altro"])
        anni = st.multiselect("Anni da includere", options=list(range(2024, 2036)), default=[datetime.now().year])
        mesi = st.multiselect("Mesi da includere", options=list(range(1, 13)), default=list(range(1, 13)))
        coeff = st.number_input("Coefficiente", min_value=1, max_value=100, value=50)
        budget_mensile = st.number_input("Budget mensile (numero)", min_value=0.0, value=0.0, step=1.0)
        xselling = st.number_input("Beget Xselling (numero)", min_value=0.0, value=0.0, step=1.0)
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
            label="💾 Scarica Budget aggiornato",
            data=buffer.getvalue(),
            file_name="budget_generato.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Carica un file o aggiungi un cliente per iniziare.")

# ------------------------------
# ANALISI SCOSTAMENTI
# ------------------------------
elif sezione == "📈 Analisi Scostamenti":
    st.header("📈 Analisi Scostamenti Budget vs Effettivo")

    uploaded_eff = st.file_uploader("📥 Carica file 'Effettivo' (obbligatorio)", type=["xlsx"])
    if st.session_state["budget_df"] is not None:
        df_budget = st.session_state["budget_df"]
        st.success("✅ Usando il Budget in memoria.")
    else:
        uploaded_budget = st.file_uploader("📄 Carica file 'Budget' (alternativo)", type=["xlsx"])
        if uploaded_budget:
            df_budget = pd.read_excel(uploaded_budget)
            df_budget.columns = df_budget.columns.str.strip()
        else:
            df_budget = None

    if uploaded_eff and df_budget is not None:
        try:
            # ---- Effettivo
            df_eff = pd.read_excel(uploaded_eff, sheet_name="Effettivo")
            df_eff.columns = df_eff.columns.str.strip().str.lower()
            df_eff["data"] = pd.to_datetime(df_eff["data"], errors="coerce", dayfirst=True)
            df_eff["mese"] = df_eff["data"].dt.to_period("M").astype(str)
            df_eff["giorno"] = df_eff["data"].dt.day

            pivot_1_15 = df_eff[df_eff["giorno"] <= 15].pivot_table(index="cliente", columns="mese", values="ore", aggfunc="sum", fill_value=0)
            pivot_1_15.columns = [f"{c} (1-15)" for c in pivot_1_15.columns]
            pivot_1_fine = df_eff.pivot_table(index="cliente", columns="mese", values="ore", aggfunc="sum", fill_value=0)
            pivot_1_fine.columns = [f"{c} (1-fine)" for c in pivot_1_fine.columns]

            df_eff_tot = pd.concat([pivot_1_15, pivot_1_fine], axis=1).fillna(0)
            df_eff_tot = df_eff_tot.reindex(sorted(df_eff_tot.columns), axis=1)
            df_eff_tot.index = df_eff_tot.index.astype(str)

            # ---- Budget
            df_budget = df_budget.copy()
            df_budget.columns = df_budget.columns.str.strip()
            cliente_col = next((c for c in df_budget.columns if c.lower()=="cliente"), None)
            if not cliente_col:
                st.error("Nel Budget manca la colonna 'cliente'.")
                st.stop()

            cat_col = next((c for c in df_budget.columns if c.lower()=="categoria_cliente"), None)
            if not cat_col:
                df_budget["categoria_cliente"] = ""
                cat_col = "categoria_cliente"
            elif cat_col != "categoria_cliente":
                df_budget = df_budget.rename(columns={cat_col: "categoria_cliente"})
                cat_col = "categoria_cliente"

            df_budget = df_budget.set_index(cliente_col)

            pattern = re.compile(r"^\d{4}-\d{2} \((1-15|1-fine)\)$")
            colonne_valide = [c for c in df_budget.columns if pattern.match(str(c))]
            colonne_comuni = df_eff_tot.columns.intersection(colonne_valide)

            # indici unione
            idx_union = sorted(set(df_budget.index.astype(str)).union(set(df_eff_tot.index.astype(str))))
            eff = df_eff_tot.reindex(index=idx_union, columns=colonne_comuni, fill_value=0)
            budget = df_budget.reindex(index=idx_union, columns=colonne_comuni, fill_value=0)

            # ---- Gate categorie obbligatorie
            cat_series = df_budget.reindex(index=idx_union)["categoria_cliente"].fillna("")
            missing_cat = [c for c in idx_union if (c not in df_budget.index) or (str(cat_series.get(c, "")).strip() == "")]
            if missing_cat:
                st.error("⚠ Alcuni clienti non hanno categoria assegnata. Completa per procedere:")
                nuove_cat = {}
                for cliente in missing_cat:
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
                    safe_rerun()
                st.stop()

            # ---- Scostamenti % (safe)
            diff_percent = pd.DataFrame(index=eff.index, columns=colonne_comuni, dtype=object)
            for col in colonne_comuni:
                num = (budget[col].astype(float) - eff[col].astype(float))
                den = budget[col].astype(float)
                perc = np.zeros_like(num, dtype=float)
                np.divide(num, den, out=perc, where=den!=0)
                perc = np.round(perc * 100, 1).astype(object)
                perc_str = perc.astype(str) + "%"
                mask_extrabudget = (den == 0) & (eff[col] > 0)
                mask_zero = (den == 0) & (eff[col] == 0)
                perc_str[mask_extrabudget] = "Extrabudget"
                perc_str[mask_zero] = "Zero"
                diff_percent[col] = perc_str

            # ------------------------------
            # FILTRI (toggle)
            # ------------------------------

            # Cliente (unchanged)
            clienti_opzioni = ["Tutti i clienti"] + list(eff.index.astype(str))
            selezione_cliente = st.sidebar.selectbox("Filtro cliente", clienti_opzioni, index=0)

            # Categoria toggles
            st.sidebar.markdown("**Categorie**")
            cat_map = df_budget["categoria_cliente"].astype(str)
            categorie_disponibili = sorted([c for c in cat_map.unique() if c])
            categorie_scelte = []
            for c in categorie_disponibili:
                on = ui_toggle(f"• {c}", True, key=f"cat_{c}")
                if on:
                    categorie_scelte.append(c)

            # Colonne (1-15 / 1-fine)
            st.sidebar.markdown("**Colonne**")
            include_115 = ui_toggle("Includi 1-15", True, key="inc_115")
            include_1fine = ui_toggle("Includi 1-fine", True, key="inc_1fine")

            # Anni & Mesi per anno (toggle)
            st.sidebar.markdown("**Anni e Mesi**")
            years_available = sorted({parse_col(c)[0] for c in colonne_comuni if parse_col(c)})
            selected_year_months = {}
            for y in years_available:
                months_y = sorted({parse_col(c)[1] for c in colonne_comuni if parse_col(c) and parse_col(c)[0]==y})
                with st.sidebar.expander(f"Anno {y}", expanded=True):
                    include_year = ui_toggle(f"Includi {y}", True, key=f"year_{y}")
                    if include_year:
                        # 12 toggle mese in 3 colonne
                        cols = st.columns(3)
                        selected_months = set()
                        for i, m in enumerate(months_y):
                            col_ui = cols[i % 3]
                            with col_ui:
                                on = ui_toggle(f"Mese {m:02d}", True, key=f"y{y}_m{m:02d}")
                                if on:
                                    selected_months.add(m)
                        if selected_months:
                            selected_year_months[y] = selected_months

            # Build selected columns based on toggles
            def col_selected(c):
                p = parse_col(c)
                if not p:
                    return False
                y, m, half = p
                if y not in selected_year_months or m not in selected_year_months[y]:
                    return False
                if half == "1-15" and not include_115:
                    return False
                if half == "1-fine" and not include_1fine:
                    return False
                return True

            selected_cols = [c for c in colonne_comuni if col_selected(c)]
            if not selected_cols:
                selected_cols = list(colonne_comuni)  # fallback

            # Filtra per cliente / categorie
            if selezione_cliente != "Tutti i clienti":
                idx = [selezione_cliente]
            else:
                idx = [c for c in eff.index if cat_map_norm.get(c, "") in categorie_scelte]

            eff_f = eff.loc[idx, selected_cols]
            budget_f = budget.loc[idx, selected_cols]
            diff_percent_f = diff_percent.loc[idx, selected_cols]

            # ---- HEATMAP
            st.subheader("📉 Scostamento percentuale tra Budget e Ore Effettive")
            styled_diff = diff_percent_f.style.applymap(colori_scostamenti).format(lambda v: "0%" if v == "Zero" else v)
            st.dataframe(styled_diff, use_container_width=True)

            # ---- DETTAGLIO COMPLETO
            st.subheader("📋 Dati Dettagliati (Effettivo / Budget / Scostamento %)")
            df_view = pd.concat([eff_f, budget_f, diff_percent_f], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
            scostamento_cols = [col for col in df_view.columns if isinstance(col, tuple) and col[0] == "Scostamento %"]
            styled_view = df_view.style.applymap(colori_scostamenti, subset=pd.IndexSlice[:, scostamento_cols]).format(lambda v: "0%" if v == "Zero" else v, subset=pd.IndexSlice[:, scostamento_cols])
            st.dataframe(styled_view, use_container_width=True)

            # ---- DASHBOARD PER CLIENTE
            st.subheader("📊 Dashboard riepilogativa per cliente")
            cols_fine = [c for c in eff_f.columns if parse_col(c) and parse_col(c)[2] == "1-fine"]
            if not cols_fine:
                cols_fine = [c for c in eff_f.columns if parse_col(c) and parse_col(c)[2] == "1-15"]
            dashboard = pd.DataFrame({
                "Ore Effettive": eff_f[cols_fine].sum(axis=1) if len(cols_fine)>0 else eff_f.sum(axis=1),
                "Ore a Budget": budget_f[cols_fine].sum(axis=1) if len(cols_fine)>0 else budget_f.sum(axis=1),
                "Categoria": [cat_map_norm.get(c, "") for c in eff_f.index]
            }, index=eff_f.index)
            dashboard["Scostamento Valore (ore)"] = dashboard["Ore a Budget"] - dashboard["Ore Effettive"]
            num_dash = (dashboard["Ore a Budget"].astype(float) - dashboard["Ore Effettive"].astype(float))
            den_dash = dashboard["Ore a Budget"].astype(float)
            sc_perc_dash = np.zeros_like(num_dash, dtype=float)
            np.divide(num_dash, den_dash, out=sc_perc_dash, where=den_dash!=0)
            dashboard["Scostamento %"] = np.round(sc_perc_dash * 100, 1)
            mask_den0 = den_dash == 0
            dashboard.loc[mask_den0 & (dashboard["Ore Effettive"] > 0), "Scostamento %"] = -9999
            dashboard.loc[mask_den0 & (dashboard["Ore Effettive"] == 0), "Scostamento %"] = 0

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

            # ---- RIEPILOGO MENSILE
            st.subheader("🗂️ Riepilogo mensile (solo 1-fine)")
            base_months = sorted({(parse_col(c)[0], parse_col(c)[1]) for c in budget_f.columns if parse_col(c) and parse_col(c)[2]=="1-fine"})
            rows = []
            for y,m in base_months:
                col = f"{y}-{m:02d} (1-fine)"
                be = budget_f[col].sum()
                ee = eff_f[col].sum()
                sc_ore = be - ee
                if be > 0:
                    sc_perc = round((sc_ore / be) * 100, 1)
                else:
                    sc_perc = -9999 if ee > 0 else 0
                rows.append({"Anno-Mese": f"{y}-{m:02d}", "Ore a Budget": be, "Ore Effettive": ee, "Scostamento ore": sc_ore, "Scostamento %": sc_perc})
            riepilogo_mensile = pd.DataFrame(rows).set_index("Anno-Mese")
            def fmt_p(v): return "Extrabudget" if v == -9999 else ("0%" if v == 0 else f"{v:.1f}%")
            if not riepilogo_mensile.empty:
                riepilogo_mensile["Scostamento % (str)"] = riepilogo_mensile["Scostamento %"].apply(fmt_p)
                styled_riep = riepilogo_mensile.style.applymap(colori_scostamenti, subset=["Scostamento % (str)"])
                st.dataframe(styled_riep, use_container_width=True)
            else:
                st.info("Nessuna colonna 1-fine selezionata per costruire il riepilogo mensile.")

            # ---- EXPORT BUDGET aggiornato (con categorie)
            st.divider()
            st.caption("Esporta Budget aggiornato (inclusa 'categoria_cliente')")
            buf = BytesIO()
            st.session_state["budget_df"].to_excel(buf, index=False)
            st.download_button("⬇️ Scarica Budget aggiornato", data=buf.getvalue(), file_name="budget_aggiornato_categorie.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {e}")
