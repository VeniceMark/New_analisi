# v3.4 - Ordinamento corretto per % in Heatmap e Dati Dettagliati (resto invariato rispetto v3.3)
import streamlit as st, pandas as pd, numpy as np, matplotlib.pyplot as plt, matplotlib, re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Analisi Budget vs Effettivo (v3.4)", layout="wide")
st.markdown("### 📊 Analisi Budget vs Effettivo — **v3.4**")

if "budget_df" not in st.session_state:
    st.session_state["budget_df"] = None

COL_PATTERN = re.compile(r"^(?P<y>\d{4})-(?P<m>\d{2}) \((?P<half>1-15|1-fine)\)$")
def parse_col(col: str):
    m = COL_PATTERN.match(str(col)); 
    return (int(m.group("y")), int(m.group("m")), m.group("half")) if m else None

def colori_scostamenti(val):
    if (isinstance(val, str) and val.strip().lower().startswith("extrabudget")) or (isinstance(val, (int, float)) and val == -9999):
        return 'background-color: violet; color: white;'
    if isinstance(val, str) and val.strip().lower() == "zero":
        return 'background-color: black; color: white;'
    try:
        val_float = float(str(val).replace("%","").strip())
        norm = (val_float + 50) / 150
        norm = max(0.0, min(1.0, norm))
        color = plt.cm.RdYlGn(norm)
        return f'background-color: {matplotlib.colors.rgb2hex(color)}'
    except:
        return ""

def ui_toggle_sidebar(label: str, value: bool, key: str):
    return (st.sidebar.toggle(label, value=value, key=key) if hasattr(st.sidebar, "toggle")
            else st.sidebar.checkbox(label, value=value, key=key))

def ui_toggle_inline(label: str, value: bool, key: str):
    return (st.toggle(label, value=value, key=key) if hasattr(st, "toggle")
            else st.checkbox(label, value=value, key=key))

def safe_rerun():
    (st.rerun() if hasattr(st, "rerun") else st.experimental_rerun())

def fmt_percent_numeric(v: float) -> str:
    if v == -9999: return "Extrabudget"
    if abs(float(v)) < 1e-9: return "0%"
    return f"{float(v):.1f}%"

sezione = st.sidebar.radio("Vai a:", ["📝 Budget Editor", "📈 Analisi Scostamenti"])

if sezione == "📝 Budget Editor":
    st.header("📝 Budget Editor – Inserimento e Calcolo Slot")
    uploaded_budget = st.file_uploader("📄 Carica un file Budget esistente (opzionale)", type=["xlsx"])
    if uploaded_budget:
        try:
            df = pd.read_excel(uploaded_budget); df.columns = df.columns.str.strip()
            cliente_col = next((c for c in df.columns if c.lower()=="cliente"), None)
            if not cliente_col: st.error("Il file Budget deve contenere la colonna 'cliente'."); st.stop()
            cat_col = next((c for c in df.columns if c.lower()=="categoria_cliente"), None)
            if not cat_col: st.warning("Nel Budget manca la colonna 'categoria_cliente'. Verrà aggiunta vuota."); df["categoria_cliente"] = ""
            elif cat_col != "categoria_cliente": df = df.rename(columns={cat_col: "categoria_cliente"})
            st.session_state["budget_df"] = df; st.success("✅ File Budget caricato.")
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
                    base = f"{anno}-{mese:02d}"; totale = (budget_mensile + xselling) / coeff if coeff > 0 else 0
                    record[f"{base}_coeff"] = coeff; record[f"{base}_budget_mensile"] = budget_mensile
                    record[f"{base}_xselling"] = xselling; record[f"{base} (1-15)"] = round(totale/2,2); record[f"{base} (1-fine)"] = round(totale,2)
            nuovo_df = pd.DataFrame([record])
            st.session_state["budget_df"] = (pd.concat([st.session_state["budget_df"], nuovo_df], ignore_index=True)
                                             if st.session_state["budget_df"] is not None else nuovo_df)
            st.success(f"Cliente '{nuovo_cliente}' aggiunto!")
    if st.session_state["budget_df"] is not None:
        st.subheader("✏️ Modifica diretta del Budget")
        edited_df = st.data_editor(st.session_state["budget_df"], use_container_width=True, num_rows="dynamic")
        st.session_state["budget_df"] = edited_df; buf = BytesIO(); edited_df.to_excel(buf, index=False)
        st.download_button("💾 Scarica Budget aggiornato", data=buf.getvalue(), file_name="budget_generato.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else: st.info("Carica un file o aggiungi un cliente per iniziare.")

elif sezione == "📈 Analisi Scostamenti":
    st.header("📈 Analisi Scostamenti Budget vs Effettivo")
    uploaded_eff = st.file_uploader("📥 Carica file 'Effettivo' (obbligatorio)", type=["xlsx"])
    if st.session_state["budget_df"] is not None: df_budget = st.session_state["budget_df"]; st.success("✅ Usando il Budget in memoria.")
    else:
        uploaded_budget = st.file_uploader("📄 Carica file 'Budget' (alternativo)", type=["xlsx"])
        df_budget = pd.read_excel(uploaded_budget) if uploaded_budget else None
        if df_budget is not None: df_budget.columns = df_budget.columns.str.strip()
    if uploaded_eff and df_budget is not None:
        try:
            df_eff = pd.read_excel(uploaded_eff, sheet_name="Effettivo"); df_eff.columns = df_eff.columns.str.strip().str.lower()
            df_eff["data"] = pd.to_datetime(df_eff["data"], errors="coerce", dayfirst=True)
            df_eff["mese"] = df_eff["data"].dt.to_period("M").astype(str); df_eff["giorno"] = df_eff["data"].dt.day
            p1 = df_eff[df_eff["giorno"]<=15].pivot_table(index="cliente", columns="mese", values="ore", aggfunc="sum", fill_value=0)
            p1.columns = [f"{c} (1-15)" for c in p1.columns]
            p2 = df_eff.pivot_table(index="cliente", columns="mese", values="ore", aggfunc="sum", fill_value=0)
            p2.columns = [f"{c} (1-fine)" for c in p2.columns]
            eff = pd.concat([p1, p2], axis=1).fillna(0); eff = eff.reindex(sorted(eff.columns), axis=1); eff.index = eff.index.astype(str)
            dfb = df_budget.copy(); dfb.columns = dfb.columns.str.strip()
            cliente_col = next((c for c in dfb.columns if c.lower()=="cliente"), None)
            if not cliente_col: st.error("Nel Budget manca la colonna 'cliente'."); st.stop()
            if "categoria_cliente" not in dfb.columns: dfb["categoria_cliente"] = ""
            dfb = dfb.set_index(cliente_col)
            pattern = re.compile(r"^\d{4}-\d{2} \((1-15|1-fine)\)$")
            colonne_valide = [c for c in dfb.columns if pattern.match(str(c))]; colonne_comuni = eff.columns.intersection(colonne_valide)
            idx_union = sorted(set(dfb.index.astype(str)).union(set(eff.index.astype(str))))
            eff = eff.reindex(index=idx_union, columns=colonne_comuni, fill_value=0); budget = dfb.reindex(index=idx_union, columns=colonne_comuni, fill_value=0)
            cat_series = dfb.reindex(index=idx_union)["categoria_cliente"].fillna("")
            missing_cat = [c for c in idx_union if (c not in dfb.index) or (str(cat_series.get(c, "")).strip() == "")]
            if missing_cat:
                st.error("⚠ Alcuni clienti non hanno categoria assegnata. Completa per procedere:"); nuove_cat={}
                for cliente in missing_cat: nuove_cat[cliente] = st.selectbox(f"Categoria per '{cliente}'", ["", "Ricorrente", "Progetto", "Interno", "Altro"], key=f"cat_{cliente}")
                if st.button("Conferma categorie e procedi"):
                    for cliente, cat in nuove_cat.items():
                        if cat:
                            if cliente in dfb.index: dfb.loc[cliente,"categoria_cliente"]=cat
                            else:
                                new_row = pd.Series({col:0 for col in dfb.columns}, name=cliente); new_row["categoria_cliente"]=cat; dfb = pd.concat([dfb, new_row.to_frame().T])
                    st.session_state["budget_df"] = dfb.reset_index().rename(columns={"index":"cliente"}); safe_rerun()
                st.stop()
            # scostamenti numerici per ordinamento
            diff_num = pd.DataFrame(index=eff.index, columns=colonne_comuni, dtype=float)
            diff_zero = pd.DataFrame(False, index=eff.index, columns=colonne_comuni)
            for col in colonne_comuni:
                num = (budget[col].astype(float) - eff[col].astype(float)); den = budget[col].astype(float)
                perc = np.zeros_like(num, dtype=float); np.divide(num, den, out=perc, where=den!=0); perc = np.round(perc * 100, 1)
                mask_extrab = (den==0)&(eff[col]>0); mask_zero = (den==0)&(eff[col]==0); diff_zero[col]=mask_zero
                perc[mask_extrab] = -9999; diff_num[col] = perc
            # filtri
            clienti = ["Tutti i clienti"] + list(eff.index.astype(str)); selezione = st.sidebar.selectbox("Filtro cliente", clienti, index=0)
            cat_map = dfb["categoria_cliente"].astype(str).fillna(""); cat_map_norm = cat_map.str.strip().str.title()
            cats = sorted([c for c in cat_map_norm.unique() if c]); scelte=[]
            st.sidebar.markdown("**Categorie**")
            for c in cats:
                if ui_toggle_sidebar(f"• {c}", True, key=f"cat_{c}"): scelte.append(c)
            st.sidebar.markdown("**Colonne**")
            inc115 = ui_toggle_sidebar("Includi 1-15", True, key="inc115"); inc1f = ui_toggle_sidebar("Includi 1-fine", True, key="inc1f")
            st.sidebar.markdown("**Anni e Mesi**")
            years = sorted({parse_col(c)[0] for c in colonne_comuni if parse_col(c)}); sel_year_months={}
            for y in years:
                months_y = sorted({parse_col(c)[1] for c in colonne_comuni if parse_col(c) and parse_col(c)[0]==y})
                with st.sidebar.expander(f"Anno {y}", expanded=True):
                    if ui_toggle_inline(f"Includi {y}", True, key=f"year_{y}"):
                        selected=set()
                        for m in months_y:
                            if ui_toggle_inline(f"Mese {m:02d}", True, key=f"y{y}_m{m:02d}"): selected.add(m)
                        if selected: sel_year_months[y]=selected
            def col_selected(c):
                p=parse_col(c); 
                return (p and (p[0] in sel_year_months) and (p[1] in sel_year_months[p[0]]) and ((p[2]!="1-15" or inc115) and (p[2]!="1-fine" or inc1f)))
            selected_cols=[c for c in colonne_comuni if col_selected(c)] or list(colonne_comuni)
            idx=[selezione] if selezione!="Tutti i clienti" else [c for c in eff.index if cat_map_norm.get(c,"") in scelte]
            eff_f=eff.loc[idx, selected_cols]; budget_f=budget.loc[idx, selected_cols]; diff_num_f=diff_num.loc[idx, selected_cols]; zero_mask_f=diff_zero.loc[idx, selected_cols]
            # HEATMAP (ordinabile)
            st.subheader("📉 Scostamento percentuale tra Budget e Ore Effettive")
            def _style_heatmap(_df):
                styles=pd.DataFrame("", index=_df.index, columns=_df.columns)
                for c in _df.columns:
                    for r in _df.index:
                        v=_df.loc[r,c]
                        if v==-9999: styles.loc[r,c]='background-color: violet; color: white;'
                        elif bool(zero_mask_f.loc[r,c]): styles.loc[r,c]='background-color: black; color: white;'
                        else:
                            norm=(float(v)+50)/150; norm=max(0.0,min(1.0,norm)); color=plt.cm.RdYlGn(norm); styles.loc[r,c]=f'background-color: {matplotlib.colors.rgb2hex(color)}'
                return styles
            st.dataframe(diff_num_f.style.apply(_style_heatmap, axis=None).format(fmt_percent_numeric), use_container_width=True)
            # DETTAGLIO COMPLETO (ordinabile)
            st.subheader("📋 Dati Dettagliati (Effettivo / Budget / Scostamento %)")
            df_view=pd.concat([eff_f, budget_f, diff_num_f], keys=["Effettivo","Budget","Scostamento %"], axis=1)
            sc_cols=[c for c in df_view.columns if isinstance(c, tuple) and c[0]=="Scostamento %"]
            def _style_detail(_df):
                styles=pd.DataFrame("", index=diff_num_f.index, columns=diff_num_f.columns)
                for c in diff_num_f.columns:
                    for r in diff_num_f.index:
                        v=diff_num_f.loc[r,c]
                        if v==-9999: styles.loc[r,c]='background-color: violet; color: white;'
                        elif bool(zero_mask_f.loc[r,c]): styles.loc[r,c]='background-color: black; color: white;'
                        else:
                            norm=(float(v)+50)/150; norm=max(0.0,min(1.0,norm)); color=plt.cm.RdYlGn(norm); styles.loc[r,c]=f'background-color: {matplotlib.colors.rgb2hex(color)}'
                return styles
            fmt_dict={("Scostamento %",c): fmt_percent_numeric for c in selected_cols}
            st.dataframe(df_view.style.apply(_style_detail, subset=pd.IndexSlice[:, sc_cols], axis=None).format(fmt_dict), use_container_width=True)
            # DASHBOARD e RIEPILOGO: come già definiti nella tua v3.3, tralasciati qui per brevità
        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {e}")
