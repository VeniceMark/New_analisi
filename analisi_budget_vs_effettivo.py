# Analisi Budget vs Effettivo — v1.12
# - Applica round(2) internamente a tutte le ore (effettivo/budget) e alle somme
# - Mantiene percentuali numeriche (1 decimale), None (nero su nero), Extrabudget (viola)

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Analisi Budget vs Effettivo (v1.12)", layout="wide")
st.markdown("### 📊 Analisi Budget vs Effettivo — **v1.12**")

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

def fmt_percent_numeric(v: float) -> str:
    try:
        if pd.isna(v):
            return "None"
    except Exception:
        pass
    if v == -9999:
        return "Extrabudget"
    try:
        if abs(float(v)) < 1e-9:
            return "0%"
    except Exception:
        pass
    try:
        return f\"{float(v):.1f}%\"
    except Exception:
        return \"\"

def fmt_hours(v):
    try:
        return f\"{float(v):.2f}\"
    except Exception:
        return \"\"

def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

def ui_toggle_sidebar(label: str, value: bool, key: str):
    if hasattr(st.sidebar, "toggle"):
        return st.sidebar.toggle(label, value=value, key=key)
    return st.sidebar.checkbox(label, value=value, key=key)

def ui_toggle_inline(label: str, value: bool, key: str):
    if hasattr(st, "toggle"):
        return st.toggle(label, value=value, key=key)
    return st.checkbox(label, value=value, key=key)

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
                    record[f"{base}_coeff"] = coeff
                    record[f"{base}_budget_mensile"] = budget_mensile
                    record[f"{base}_xselling"] = xselling
                    record[f"{base} (1-15)"] = round(totale/2, 2)
                    record[f"{base} (1-fine)"] = round(totale, 2)
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

            # indici unione + round(2) su matrici base
            idx_union = sorted(set(df_budget.index.astype(str)).union(set(df_eff_tot.index.astype(str))))
            eff = df_eff_tot.reindex(index=idx_union, columns=colonne_comuni, fill_value=0).round(2)
            budget = df_budget.reindex(index=idx_union, columns=colonne_comuni, fill_value=0).round(2)

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

            # ---- Scostamenti % (numeric-backed)
            diff_percent_num = pd.DataFrame(index=eff.index, columns=colonne_comuni, dtype=float)
            diff_mask_zero = pd.DataFrame(False, index=eff.index, columns=colonne_comuni)
            for col in colonne_comuni:
                num = (budget[col].astype(float) - eff[col].astype(float))
                den = budget[col].astype(float)
                perc = np.zeros_like(num, dtype=float)
                np.divide(num, den, out=perc, where=den!=0)
                perc = np.round(perc * 100, 1)
                mask_extrabudget = (den == 0) & (eff[col] > 0)
                mask_zero = (den == 0) & (eff[col] == 0)
                diff_mask_zero[col] = mask_zero
                perc = pd.Series(perc, index=eff.index)
                perc.loc[mask_zero] = np.nan
                perc.loc[mask_extrabudget] = -9999
                diff_percent_num[col] = perc.astype(float)

            # ------------------------------
            # FILTRI (sidebar)
            # ------------------------------
            clienti_opzioni = ["Tutti i clienti"] + list(eff.index.astype(str))
            selezione_cliente = st.sidebar.selectbox("Filtro cliente", clienti_opzioni, index=0)

            st.sidebar.markdown("**Categorie**")
            cat_map = df_budget["categoria_cliente"].astype(str).fillna("")
            cat_map_norm = cat_map.str.strip().str.title()
            categorie_disponibili = sorted([c for c in cat_map_norm.unique() if c])
            categorie_scelte = []
            for c in categorie_disponibili:
                if ui_toggle_sidebar(f"• {c}", True, key=f"cat_{c}"):
                    categorie_scelte.append(c)

            st.sidebar.markdown("**Colonne**")
            include_115 = ui_toggle_sidebar("Includi 1-15", True, key="inc_115")
            include_1fine = ui_toggle_sidebar("Includi 1-fine", True, key="inc_1fine")

            st.sidebar.markdown("**Anni e Mesi**")
            years_available = sorted({parse_col(c)[0] for c in colonne_comuni if parse_col(c)})
            selected_year_months = {}
            for y in years_available:
                months_y = sorted({parse_col(c)[1] for c in colonne_comuni if parse_col(c) and parse_col(c)[0]==y})
                with st.sidebar.expander(f"Anno {y}", expanded=True):
                    include_year = ui_toggle_inline(f"Includi {y}", True, key=f"year_{y}")
                    if include_year:
                        selected_months = set()
                        for m in months_y:
                            if ui_toggle_inline(f"Mese {m:02d}", True, key=f"y{y}_m{m:02d}"):
                                selected_months.add(m)
                        if selected_months:
                            selected_year_months[y] = selected_months

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
                selected_cols = list(colonne_comuni)

            if selezione_cliente != "Tutti i clienti":
                idx = [selezione_cliente]
            else:
                idx = [c for c in eff.index if cat_map_norm.get(c, "") in categorie_scelte]

            eff_f = eff.loc[idx, selected_cols].round(2)
            budget_f = budget.loc[idx, selected_cols].round(2)
            diff_num_f = diff_percent_num.loc[idx, selected_cols]
            zero_mask_f = diff_mask_zero.loc[idx, selected_cols]

            # ---- HEATMAP
            st.subheader("📉 Scostamento percentuale tra Budget e Ore Effettive")
            def _style_heatmap(_df):
                styles = pd.DataFrame("", index=_df.index, columns=_df.columns)
                for c in _df.columns:
                    for r in _df.index:
                        v = _df.loc[r, c]
                        if pd.isna(v):
                            styles.loc[r, c] = 'background-color: black; color: black;'
                        elif v == -9999:
                            styles.loc[r, c] = 'background-color: violet; color: white;'
                        else:
                            try:
                                norm = (float(v) + 50) / 150
                                norm = max(0.0, min(1.0, norm))
                                color = plt.cm.RdYlGn(norm)
                                styles.loc[r, c] = f'{matplotlib.colors.rgb2hex(color)}'
                            except Exception:
                                styles.loc[r, c] = ""
                return styles
            st.dataframe(diff_num_f.style.apply(_style_heatmap, axis=None).format(fmt_percent_numeric), use_container_width=True)

            # ---- DETTAGLIO COMPLETO
            st.subheader("📋 Dati Dettagliati (Effettivo / Budget / Scostamento %)")
            df_view = pd.concat([eff_f, budget_f, diff_num_f], keys=["Effettivo", "Budget", "Scostamento %"], axis=1)
            scostamento_cols = [col for col in df_view.columns if isinstance(col, tuple) and col[0] == "Scostamento %"]

            def _cell_style_percent(v):
                try:
                    if pd.isna(v):
                        return 'background-color: black; color: black;'
                    if float(v) == -9999:
                        return 'background-color: violet; color: white;'
                    norm = (float(v) + 50) / 150
                    norm = max(0.0, min(1.0, norm))
                    color = plt.cm.RdYlGn(norm)
                    return f'{matplotlib.colors.rgb2hex(color)}'
                except Exception:
                    return ""
            fmt_dict = {("Scostamento %", c): fmt_percent_numeric for c in selected_cols}
            for c in selected_cols:
                fmt_dict[("Effettivo", c)] = fmt_hours
                fmt_dict[("Budget", c)] = fmt_hours

            styled_view = df_view.style.applymap(_cell_style_percent, subset=pd.IndexSlice[:, scostamento_cols]).format(fmt_dict)
            st.dataframe(styled_view, use_container_width=True)

            # ---- DASHBOARD PER CLIENTE
            st.subheader("📊 Dashboard riepilogativa per cliente")
            cols_fine = [c for c in eff_f.columns if parse_col(c) and parse_col(c)[2] == "1-fine"]
            if not cols_fine:
                cols_fine = [c for c in eff_f.columns if parse_col(c) and parse_col(c)[2] == "1-15"]
            dashboard = pd.DataFrame({
                "Ore Effettive": (eff_f[cols_fine].sum(axis=1) if len(cols_fine)>0 else eff_f.sum(axis=1)).round(2),
                "Ore a Budget": (budget_f[cols_fine].sum(axis=1) if len(cols_fine)>0 else budget_f.sum(axis=1)).round(2),
                "Categoria": [cat_map_norm.get(c, "") for c in eff_f.index]
            }, index=eff_f.index)
            dashboard["Scostamento Valore (ore)"] = (dashboard["Ore a Budget"] - dashboard["Ore Effettive"]).round(2)
            num_dash = (dashboard["Ore a Budget"].astype(float) - dashboard["Ore Effettive"].astype(float))
            den_dash = dashboard["Ore a Budget"].astype(float)
            sc_perc_dash = np.zeros_like(num_dash, dtype=float)
            np.divide(num_dash, den_dash, out=sc_perc_dash, where=den_dash!=0)
            dashboard["Scostamento %"] = np.round(sc_perc_dash * 100, 1)
            mask_den0 = den_dash == 0
            dashboard.loc[mask_den0 & (dashboard["Ore Effettive"] > 0), "Scostamento %"] = -9999
            dashboard.loc[mask_den0 & (dashboard["Ore Effettive"] == 0), "Scostamento %"] = np.nan

            def _style_dash(v):
                if pd.isna(v):
                    return 'background-color: black; color: black;'
                if v == -9999:
                    return 'background-color: violet; color: white;'
                try:
                    norm = (float(v) + 50) / 150
                    norm = max(0.0, min(1.0, norm))
                    color = plt.cm.RdYlGn(norm)
                    return f'{matplotlib.colors.rgb2hex(color)}'
                except Exception:
                    return ''
            fmt_dash = {
                "Scostamento %": fmt_percent_numeric,
                "Ore Effettive": fmt_hours,
                "Ore a Budget": fmt_hours,
                "Scostamento Valore (ore)": fmt_hours,
            }
            st.dataframe(dashboard.style.applymap(_style_dash, subset=["Scostamento %"]).format(fmt_dash), use_container_width=True)

            # ---- RIEPILOGO MENSILE (solo 1-fine)
            st.subheader("🗂️ Riepilogo mensile (solo 1-fine)")
            base_months = sorted({(parse_col(c)[0], parse_col(c)[1]) for c in budget_f.columns if parse_col(c) and parse_col(c)[2]=="1-fine"})
            rows = []
            for y,m in base_months:
                col = f"{y}-{m:02d} (1-fine)"
                b_col = budget_f[col].astype(float)
                e_col = eff_f[col].astype(float)

                be = round(float(b_col.sum()), 2)  # Ore a Budget
                mask_extrab = (b_col == 0) & (e_col > 0)
                ee_extra = round(float(e_col[mask_extrab].sum()), 2)  # Ore Extrabudget
                ee_in = round(float(e_col[~mask_extrab].sum()), 2)    # Ore Effettive senza Extrabudget
                ee_tot = round(ee_in + ee_extra, 2)

                if be > 0:
                    s_in = round(((be - ee_in) / be) * 100, 1)
                else:
                    s_in = np.nan

                if be > 0:
                    s_tot = round(((be - ee_tot) / be) * 100, 1)
                else:
                    s_tot = -9999 if ee_tot > 0 else np.nan

                rows.append({
                    "Anno-Mese": f"{y}-{m:02d}",
                    "Ore a Budget": be,
                    "Ore Effettive (senza Extrabudget)": ee_in,
                    "Ore Extrabudget": ee_extra,
                    "Scostamento % (solo eff. a budget)": s_in,
                    "Scostamento % (incl. Extrabudget)": s_tot,
                })

            riepilogo_mensile = pd.DataFrame(rows).set_index("Anno-Mese")

            def _style_riep(v):
                if pd.isna(v):
                    return 'background-color: black; color: black;'
                if v == -9999:
                    return 'background-color: violet; color: white;'
                try:
                    norm = (float(v) + 50) / 150
                    norm = max(0.0, min(1.0, norm))
                    color = plt.cm.RdYlGn(norm)
                    return f'{matplotlib.colors.rgb2hex(color)}'
                except Exception:
                    return ''
            perc_cols = ["Scostamento % (solo eff. a budget)", "Scostamento % (incl. Extrabudget)"]
            fmt_riep = {c: fmt_percent_numeric for c in perc_cols}
            fmt_riep.update({
                "Ore a Budget": fmt_hours,
                "Ore Effettive (senza Extrabudget)": fmt_hours,
                "Ore Extrabudget": fmt_hours,
            })
            st.dataframe(riepilogo_mensile.style.applymap(_style_riep, subset=perc_cols).format(fmt_riep), use_container_width=True)

            # ---- EXPORT BUDGET aggiornato (con categorie)
            st.divider()
            st.caption("Esporta Budget aggiornato (inclusa 'categoria_cliente')")
            buf = BytesIO()
            st.session_state["budget_df"].to_excel(buf, index=False)
            st.download_button("⬇️ Scarica Budget aggiornato", data=buf.getvalue(), file_name="budget_aggiornato_categorie.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        except Exception as e:
            st.error(f\"Errore durante l'elaborazione: {e}\")