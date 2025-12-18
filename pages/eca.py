# crowley/eca.py
import streamlit as st
import pandas as pd
import json
import io
import numpy as np
from datetime import datetime, timedelta, date

def render(df_crowley, cookies, data_atualizacao):
    # Aumenta limite de renderização
    pd.set_option("styler.render.max_elements", 5_000_000)

    # --- CSS GLOBAL ---
    st.markdown("""
        <style>
        [data-testid="stDataFrame"] th {
            text-align: center !important;
            vertical-align: middle !important;
        }
        [data-testid="stDataFrame"] td {
            text-align: center !important;
            vertical-align: middle !important;
        }
        [data-testid="stDataFrame"] th[data-testid="stColumnHeader"]:first-child,
        [data-testid="stDataFrame"] td:first-child {
            text-align: left !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- Header e Voltar ---
    if st.button("Voltar", key="btn_voltar_eca"):
        st.query_params["view"] = "menu"
        keys_to_clear = ["eca_search_trigger", "eca_praca_key", "eca_veiculo_key", "eca_concorrentes_key", "eca_tipo_key", "eca_share_toggle"]
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown('<div class="page-title-centered">Relatório ECA</div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">Exclusivos • Compartilhados • Ausentes</p>', unsafe_allow_html=True)
    
    # --- Validação da Base ---
    if df_crowley is None or df_crowley.empty:
        st.error("Base de dados não carregada.")
        st.stop()

    df_crowley_copy = df_crowley.copy()

    if "Data_Dt" not in df_crowley_copy.columns:
        if "Data" in df_crowley_copy.columns:
            df_crowley_copy["Data_Dt"] = pd.to_datetime(df_crowley_copy["Data"], dayfirst=True, errors="coerce")
        else:
            st.error("Coluna de Data não encontrada na base.")
            st.stop()

    # --- CONFIGURAÇÃO ---
    min_date_allowed = date(2024, 1, 1)
    try: max_date_allowed = datetime.strptime(data_atualizacao, "%d/%m/%Y").date()
    except: max_date_allowed = datetime.now().date()
        
    tooltip_dates = f"Dados disponíveis para pesquisa:\nDe 01/01/2024 até {data_atualizacao}"

    # --- COOKIES ---
    saved_filters = {}
    cookie_val = cookies.get("crowley_filters_eca")
    if cookie_val:
        try: saved_filters = json.loads(cookie_val)
        except: pass

    def get_date_from_cookie(key, default_date):
        val = saved_filters.get(key)
        if val:
            try:
                d = datetime.strptime(val, "%Y-%m-%d").date()
                if d < min_date_allowed: return min_date_allowed
                if d > max_date_allowed: return max_date_allowed
                return d
            except: return default_date
        return default_date
    
    def get_cookie_val(key, default=None):
        return saved_filters.get(key, default)

    # Defaults
    default_ini = max(min_date_allowed, max_date_allowed - timedelta(days=30))
    val_dt_ini = get_date_from_cookie("dt_ini", default_ini)
    val_dt_fim = get_date_from_cookie("dt_fim", max_date_allowed)
    
    saved_praca = get_cookie_val("praca", None)
    saved_veiculo = get_cookie_val("veiculo", None)
    saved_concorrentes = get_cookie_val("concorrentes", [])
    
    # --- FILTROS ---
    st.markdown("##### Configuração da Análise")
    
    lista_pracas = sorted(df_crowley_copy["Praca"].dropna().unique())
    
    if saved_praca not in lista_pracas: saved_praca = lista_pracas[0] if lista_pracas else None
    if "eca_praca_key" not in st.session_state:
        st.session_state.eca_praca_key = saved_praca
    
    def on_change_reset():
        st.session_state["eca_search_trigger"] = False
    
    with st.container(border=True):
        # LINHA 1: Datas e Praça
        c1, c2, c3 = st.columns([1, 1, 1.5])
        with c1: dt_ini = st.date_input("Início", value=val_dt_ini, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY", help=tooltip_dates)
        with c2: dt_fim = st.date_input("Fim", value=val_dt_fim, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY")
        with c3: sel_praca = st.selectbox("Praça", options=lista_pracas, key="eca_praca_key", on_change=on_change_reset)

        st.divider()
        
        # --- CÁLCULO DO CONTEXTO (CASCATA) ---
        ts_ini_ctx = pd.Timestamp(dt_ini)
        ts_fim_ctx = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        mask_context = (
            (df_crowley_copy["Data_Dt"] >= ts_ini_ctx) &
            (df_crowley_copy["Data_Dt"] <= ts_fim_ctx) &
            (df_crowley_copy["Praca"] == sel_praca)
        )
        df_context = df_crowley_copy[mask_context]
        
        lista_veiculos_local = sorted(df_context["Emissora"].dropna().unique())
        lista_concorrentes_completa = [v for v in lista_veiculos_local]
        tipos_disponiveis = sorted(df_context["Tipo"].dropna().unique().tolist())
        
        # LINHA 2: Veículo, Concorrência, Tipo E TOGGLE (Matriz)
        # Ajuste de proporções para o botão ficar harmônico
        c4, c5, c6, c7 = st.columns([1.3, 1.3, 1.1, 0.8])
        
        # 1. Veículo Alvo
        if "eca_veiculo_key" not in st.session_state:
            v_init = saved_veiculo if saved_veiculo in lista_veiculos_local else (lista_veiculos_local[0] if lista_veiculos_local else None)
            st.session_state.eca_veiculo_key = v_init
        else:
            if st.session_state.eca_veiculo_key not in lista_veiculos_local and lista_veiculos_local:
                 st.session_state.eca_veiculo_key = lista_veiculos_local[0]

        with c4: 
            sel_veiculo = st.selectbox("Veículo Alvo (Protagonista)", options=lista_veiculos_local, key="eca_veiculo_key", on_change=on_change_reset)

        # 2. Concorrência
        lista_concorrentes = [v for v in lista_concorrentes_completa if v != sel_veiculo]
        
        if "eca_concorrentes_key" not in st.session_state:
            v_conc = [c for c in saved_concorrentes if c in lista_concorrentes]
            st.session_state.eca_concorrentes_key = v_conc
        else:
            curr = st.session_state.eca_concorrentes_key
            st.session_state.eca_concorrentes_key = [c for c in curr if c in lista_concorrentes]

        with c5: 
            sel_concorrentes = st.multiselect(
                "Comparar com (Concorrência)", 
                options=lista_concorrentes, 
                key="eca_concorrentes_key", 
                placeholder="Se vazio, compara com TODOS da praça",
                on_change=on_change_reset
            )

        # 3. Tipo de Veiculação
        saved_tipos = get_cookie_val("tipo_veiculacao", [])
        if "Consolidado" in saved_tipos: saved_tipos = []
        
        if "eca_tipo_key" not in st.session_state:
            valid_tipos_init = [t for t in saved_tipos if t in tipos_disponiveis]
            st.session_state.eca_tipo_key = valid_tipos_init
        else:
            curr_tipos = st.session_state.eca_tipo_key
            st.session_state.eca_tipo_key = [t for t in curr_tipos if t in tipos_disponiveis]

        with c6:
            sel_tipos = st.multiselect(
                "Tipo de Veiculação (Opc.)", 
                options=tipos_disponiveis,
                key="eca_tipo_key",          
                placeholder="Todos",         
                on_change=on_change_reset
            )

        # 4. Botão Toggle Share (Estilo Botão)
        if "eca_share_toggle" not in st.session_state:
            st.session_state.eca_share_toggle = True

        with c7:
            # Spacer para alinhar com os inputs que possuem label (~28px)
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            
            is_active_share = st.session_state.eca_share_toggle
            if is_active_share:
                btn_type = "primary"
                btn_text = "Share %: Ativo"
            else:
                btn_type = "secondary"
                btn_text = "Share %: Inativo"
            
            # Botão que funciona como Toggle
            if st.button(btn_text, type=btn_type, key="btn_share_toggle", help="Ativar/Desativar coluna de Share %", use_container_width=True):
                st.session_state.eca_share_toggle = not is_active_share
                st.rerun()
            
            # Variável final para uso no código
            show_share = st.session_state.eca_share_toggle

        st.markdown("<br>", unsafe_allow_html=True)
        
        c_btn_vazio1, c_btn, c_btn_vazio2 = st.columns([1, 1, 1])
        with c_btn:
            submitted = st.button("Gerar Relatório ECA", type="primary", use_container_width=True)


    if submitted:
        st.session_state["eca_search_trigger"] = True
        
        tipos_para_cookie = sel_tipos if sel_tipos else ["Consolidado"]

        new_filters = {
            "dt_ini": str(dt_ini), 
            "dt_fim": str(dt_fim), 
            "praca": sel_praca, 
            "veiculo": sel_veiculo, 
            "concorrentes": sel_concorrentes,
            "tipo_veiculacao": tipos_para_cookie
        }
        cookies["crowley_filters_eca"] = json.dumps(new_filters)
        cookies.save()

    if st.session_state.get("eca_search_trigger"):
        
        df_base = df_context.copy()
        
        if sel_tipos:
            df_base = df_base[df_base["Tipo"].isin(sel_tipos)]

        df_target = df_base[df_base["Emissora"] == sel_veiculo]
        
        if sel_concorrentes: df_comp = df_base[df_base["Emissora"].isin(sel_concorrentes)]
        else: df_comp = df_base[df_base["Emissora"] != sel_veiculo]

        if df_target.empty and df_comp.empty:
             st.warning("Nenhum dado encontrado com os filtros selecionados.")
             return
        
        anunciantes_target = set(df_target["Anunciante"].unique()) if not df_target.empty else set()
        anunciantes_comp = set(df_comp["Anunciante"].unique()) if not df_comp.empty else set()

        exclusivos = anunciantes_target - anunciantes_comp
        compartilhados = anunciantes_target & anunciantes_comp
        ausentes = anunciantes_comp - anunciantes_target

        # --- HELPER DE TABELA ---
        def criar_tabela_resumo(df_src, lista_anunciantes, is_exclusive=False, show_share=True):
            if not lista_anunciantes: return pd.DataFrame()
            
            df_final = df_src[df_src["Anunciante"].isin(lista_anunciantes)].copy()
            col_val = "Volume de Insercoes" if "Volume de Insercoes" in df_final.columns else "Contagem"
            if col_val == "Contagem": df_final["Contagem"] = 1
            
            pivot_qty = pd.pivot_table(
                df_final, index="Anunciante", columns="Emissora", values=col_val, 
                aggfunc="sum", fill_value=0, observed=True
            )
            
            total_por_anunciante = pivot_qty.sum(axis=1)
            pivot_qty = pivot_qty.loc[total_por_anunciante.sort_values(ascending=False).index]
            
            if is_exclusive:
                total_row = pivot_qty.sum(numeric_only=True)
                pivot_qty.loc["TOTAL GERAL"] = total_row
                return pivot_qty
            
            if not show_share:
                pivot_simple = pivot_qty.copy()
                pivot_simple["TOTAL"] = total_por_anunciante
                
                total_row = pivot_simple.sum(numeric_only=True)
                pivot_simple.loc["TOTAL GERAL"] = total_row
                return pivot_simple

            # Com Share
            pivot_share = pivot_qty.div(total_por_anunciante.replace(0, 1), axis=0) * 100
            
            cols = []
            for col in pivot_qty.columns:
                cols.append((col, "Share %"))
                cols.append((col, "Inserções"))
            cols.append(("TOTAL", "Inserções"))
            
            df_multi = pd.DataFrame(index=pivot_qty.index, columns=pd.MultiIndex.from_tuples(cols))
            
            for col in pivot_qty.columns:
                df_multi[(col, "Inserções")] = pivot_qty[col]
                df_multi[(col, "Share %")] = pivot_share[col]
            
            df_multi[("TOTAL", "Inserções")] = total_por_anunciante
            
            # Linha de Total Geral
            totals_qty = pivot_qty.sum(numeric_only=True)
            grand_total = totals_qty.sum()
            
            total_geral_row = []
            
            for col_tuple in df_multi.columns:
                emissora, tipo = col_tuple
                if tipo == "Inserções":
                    if emissora == "TOTAL": val = grand_total
                    else: val = totals_qty.get(emissora, 0)
                    total_geral_row.append(val)
                else:
                    # SHARE % NA LINHA DE TOTAL GERAL DEVE SER VAZIO
                    total_geral_row.append(np.nan)
            
            df_multi.loc["TOTAL GERAL"] = total_geral_row
            return df_multi

        # --- HELPERS DE ESTILO ---
        def safe_fmt_int(x):
            try:
                if pd.isnull(x) or x == "": return ""
                return f"{int(x)}"
            except: return str(x)

        def safe_fmt_pct(x):
            try:
                if pd.isnull(x) or x == "": return "" 
                return f"{float(x):.1f}%"
            except: return str(x)

        def style_df(df, is_exclusive=False, show_share=True):
            if df.empty: return df
            
            header_styles = [
                {'selector': 'th', 'props': [('text-align', 'center'), ('vertical-align', 'middle')]},
                {'selector': 'th.row_heading', 'props': [('text-align', 'left')]},
                {'selector': 'td', 'props': [('text-align', 'center')]}
            ]
            
            if is_exclusive or not show_share:
                s = df.style.format(safe_fmt_int)
            else:
                format_dict = {}
                for col in df.columns:
                    if col[1] == "Share %": format_dict[col] = safe_fmt_pct
                    else: format_dict[col] = safe_fmt_int
                
                # AQUI: na_rep=" " garante que o np.nan apareça como espaço em branco na tela
                s = df.style.format(format_dict, na_rep=" ")

            s = s.set_properties(**{'text-align': 'center'})
            s = s.set_table_styles(header_styles)
            s = s.apply(lambda x: ["background-color: #f0f2f6; font-weight: bold" if (hasattr(x, 'name') and x.name == "TOTAL GERAL") else "" for i in x], axis=1)
            return s

        t1, t2, t3 = st.tabs([f"Exclusivos ({len(exclusivos)})", f"Compartilhados ({len(compartilhados)})", f"Ausentes ({len(ausentes)})"])

        with t1:
            df1 = criar_tabela_resumo(df_target, exclusivos, is_exclusive=True)
            if not df1.empty: 
                st.dataframe(style_df(df1, is_exclusive=True), width="stretch", height=500)
            else: st.info("Nenhum registro.")

        with t2:
            df_full_shared = pd.concat([df_target[df_target["Anunciante"].isin(compartilhados)], df_comp[df_comp["Anunciante"].isin(compartilhados)]])
            df2 = criar_tabela_resumo(df_full_shared, compartilhados, is_exclusive=False, show_share=show_share)
            if not df2.empty: 
                st.dataframe(style_df(df2, is_exclusive=False, show_share=show_share), width="stretch", height=500)
            else: st.info("Nenhum registro.")

        with t3:
            df3 = criar_tabela_resumo(df_comp, ausentes, is_exclusive=False, show_share=show_share)
            if not df3.empty: 
                st.dataframe(style_df(df3, is_exclusive=False, show_share=show_share), width="stretch", height=500)
            else: st.info("Nenhum registro.")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- DETALHAMENTO ---
        with st.expander("Fonte de Dados Completa (Detalhamento)", expanded=False):
            df_global_view = pd.concat([df_target, df_comp])
            
            rename_map = {
                "Praca": "Praça", "Anuncio": "Anúncio", "Duracao": "Duração",
                "Emissora": "Veículo", "Volume de Insercoes": "Inserções", 
                "Tipo": "Tipo de Veiculação", "DayPart": "DayPart"
            }
            
            df_detalhe = df_global_view.copy()
            if "Data_Dt" in df_detalhe.columns:
                df_detalhe["Data"] = df_detalhe["Data_Dt"].dt.strftime("%d/%m/%Y")
            
            cols_originais = ["Data", "Anunciante", "Anuncio", "Duracao", "Praca", "Emissora", "Tipo", "DayPart", "Volume de Insercoes"]
            cols_existentes = [c for c in cols_originais if c in df_detalhe.columns]
            
            df_exib = df_detalhe[cols_existentes].rename(columns=rename_map)
            df_exib.sort_values(by=["Anunciante", "Data"], inplace=True)
            
            st.dataframe(df_exib, width="stretch", hide_index=True)

        st.markdown("---")
        
        # --- EXPORTAÇÃO ---
        with st.spinner("Gerando Excel..."):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                fmt_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
                fmt_left = workbook.add_format({'align': 'left', 'valign': 'vcenter'})
                
                tipos_export = ", ".join(sel_tipos) if sel_tipos else "Todos"

                f_data = {
                    "Parâmetro": ["Início", "Fim", "Praça", "Veículo", "Concorrentes", "Tipo de Veiculação"], 
                    "Valor": [
                        dt_ini.strftime("%d/%m/%Y"), 
                        dt_fim.strftime("%d/%m/%Y"), 
                        sel_praca, 
                        sel_veiculo, 
                        ", ".join(sel_concorrentes) if sel_concorrentes else "Todos",
                        tipos_export
                    ]
                }
                pd.DataFrame(f_data).to_excel(writer, sheet_name='Filtros', index=False)
                writer.sheets['Filtros'].set_column('A:B', 40)

                def save_tab(df, name, include_index=True):
                    if not df.empty:
                        # O Pandas exporta np.nan como célula vazia automaticamente
                        df.to_excel(writer, sheet_name=name, index=include_index)
                        worksheet = writer.sheets[name]
                        worksheet.set_column('A:A', 40, fmt_left)
                        worksheet.set_column('B:Z', 15, fmt_center)
                
                save_tab(df1, 'Exclusivos')
                save_tab(df2, 'Compartilhados')
                save_tab(df3, 'Ausentes')
                
                if not df_exib.empty:
                    df_exib.to_excel(writer, sheet_name='Detalhamento', index=False)
                    worksheet = writer.sheets['Detalhamento']
                    
                    for idx, col_name in enumerate(df_exib.columns):
                        if col_name in ["Anunciante", "Anúncio", "Tipo de Veiculação"]:
                            worksheet.set_column(idx, idx, 35, fmt_left)
                        else:
                            worksheet.set_column(idx, idx, 15, fmt_center)

        c_vazio1_exp, c_vazio2_exp, c_btn_exp, c_vazio3_exp, c_vazio4_exp = st.columns([1, 1, 1, 1, 1])
        with c_btn_exp:
            st.download_button("Exportar Excel", data=buf, file_name=f"ECA_{sel_veiculo}_{datetime.now().strftime('%d%m')}.xlsx", mime="application/vnd.ms-excel", type="secondary", use_container_width=True)
        
        st.markdown(f"<div style='text-align:center;color:#666;font-size:0.8rem;margin-top:5px;'>Última atualização da base de dados: {data_atualizacao}</div>", unsafe_allow_html=True)