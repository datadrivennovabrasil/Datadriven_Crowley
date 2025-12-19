# pages/campaign_flow.py
import streamlit as st
import pandas as pd
import json
import numpy as np
from datetime import datetime, timedelta, date

# Importação da função de exportação que criamos anteriormente
from utils.export_crowley import generate_campaign_flow_excel

def render(df_crowley, cookies, data_atualizacao):
    # Aumenta limite de renderização para tabelas grandes
    pd.set_option("styler.render.max_elements", 5_000_000)

    # --- CSS GLOBAL E ESPECÍFICO ---
    st.markdown("""
        <style>
        /* Estilos de Tabela */
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

        /* TÍTULO CORRIGIDO E CENTRALIZADO */
        .page-title-centered {
            text-align: center;
            font-size: 2.5rem;
            font-weight: 700;
            color: #003366; /* Azul Novabrasil */
            margin-bottom: 0.5rem;
            margin-top: 1rem;
        }
        .page-subtitle-centered {
            text-align: center; 
            color: #666;
            font-size: 1rem;
            margin-bottom: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- Botão Voltar ---
    if st.button("Voltar", key="btn_voltar_camp"):
        st.query_params["view"] = "menu"
        keys_to_clear = ["camp_search_trigger", "camp_praca_key", "camp_veiculo_key", "camp_concorrentes_key", "camp_tipo_key", "camp_share_toggle", "show_camp_export"]
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        st.rerun()

    # --- TÍTULOS ---
    st.markdown('<div class="page-title-centered">Campaign Flow</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle-centered">Análise de anunciantes exclusivos, compartilhados e ausentes</div>', unsafe_allow_html=True)
    
    # --- Validação da Base ---
    if df_crowley is None or df_crowley.empty:
        st.error("Base de dados não carregada.")
        st.stop()

    df_crowley_copy = df_crowley.copy()

    # Garante Data
    if "Data_Dt" not in df_crowley_copy.columns:
        if "Data" in df_crowley_copy.columns:
            df_crowley_copy["Data_Dt"] = pd.to_datetime(df_crowley_copy["Data"], dayfirst=True, errors="coerce")
        else:
            st.error("Coluna de Data não encontrada na base.")
            st.stop()

    # --- CONFIGURAÇÃO DE DATAS ---
    min_date_allowed = date(2024, 1, 1)
    try: max_date_allowed = datetime.strptime(data_atualizacao, "%d/%m/%Y").date()
    except: max_date_allowed = datetime.now().date()
        
    tooltip_dates = f"Dados disponíveis para pesquisa:\nDe 01/01/2024 até {data_atualizacao}"

    # --- COOKIES ---
    saved_filters = {}
    cookie_val = cookies.get("crowley_filters_campaign")
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
    
    # --- INTERFACE DE FILTROS ---
    st.markdown("##### Configuração da Análise")
    
    lista_pracas = sorted(df_crowley_copy["Praca"].dropna().unique())
    
    if saved_praca not in lista_pracas: saved_praca = lista_pracas[0] if lista_pracas else None
    if "camp_praca_key" not in st.session_state:
        st.session_state.camp_praca_key = saved_praca
    
    def on_change_reset():
        st.session_state["camp_search_trigger"] = False
    
    with st.container(border=True):
        # LINHA 1: Datas e Praça
        c1, c2, c3 = st.columns([1, 1, 1.5])
        with c1: dt_ini = st.date_input("Início", value=val_dt_ini, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY", help=tooltip_dates)
        with c2: dt_fim = st.date_input("Fim", value=val_dt_fim, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY")
        with c3: sel_praca = st.selectbox("Praça", options=lista_pracas, key="camp_praca_key", on_change=on_change_reset)

        st.divider()
        
        # --- CÁLCULO DO CONTEXTO ---
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
        
        # LINHA 2
        c4, c5, c6, c7 = st.columns([1.3, 1.3, 1.1, 0.8])
        
        # 1. Veículo Alvo
        if "camp_veiculo_key" not in st.session_state:
            v_init = saved_veiculo if saved_veiculo in lista_veiculos_local else (lista_veiculos_local[0] if lista_veiculos_local else None)
            st.session_state.camp_veiculo_key = v_init
        else:
            if st.session_state.camp_veiculo_key not in lista_veiculos_local and lista_veiculos_local:
                 st.session_state.camp_veiculo_key = lista_veiculos_local[0]

        with c4: 
            sel_veiculo = st.selectbox("Veículo Alvo (Protagonista)", options=lista_veiculos_local, key="camp_veiculo_key", on_change=on_change_reset)

        # 2. Concorrência
        lista_concorrentes = [v for v in lista_concorrentes_completa if v != sel_veiculo]
        
        if "camp_concorrentes_key" not in st.session_state:
            v_conc = [c for c in saved_concorrentes if c in lista_concorrentes]
            st.session_state.camp_concorrentes_key = v_conc
        else:
            curr = st.session_state.camp_concorrentes_key
            st.session_state.camp_concorrentes_key = [c for c in curr if c in lista_concorrentes]

        with c5: 
            sel_concorrentes = st.multiselect(
                "Comparar com (Concorrência)", 
                options=lista_concorrentes, 
                key="camp_concorrentes_key", 
                placeholder="Se vazio, compara com TODOS",
                on_change=on_change_reset
            )

        # 3. Tipo
        saved_tipos = get_cookie_val("tipo_veiculacao", [])
        if "Consolidado" in saved_tipos: saved_tipos = []
        
        if "camp_tipo_key" not in st.session_state:
            valid_tipos_init = [t for t in saved_tipos if t in tipos_disponiveis]
            st.session_state.camp_tipo_key = valid_tipos_init
        else:
            curr_tipos = st.session_state.camp_tipo_key
            st.session_state.camp_tipo_key = [t for t in curr_tipos if t in tipos_disponiveis]

        with c6:
            sel_tipos = st.multiselect(
                "Tipo de Veiculação (Opc.)", 
                options=tipos_disponiveis,
                key="camp_tipo_key",          
                placeholder="Todos",         
                on_change=on_change_reset
            )

        # 4. Toggle Share
        if "camp_share_toggle" not in st.session_state:
            st.session_state.camp_share_toggle = True

        with c7:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            
            is_active_share = st.session_state.camp_share_toggle
            btn_type = "primary" if is_active_share else "secondary"
            btn_text = "Share %: Ativo" if is_active_share else "Share %: Inativo"
            
            if st.button(btn_text, type=btn_type, key="btn_share_toggle", use_container_width=True):
                st.session_state.camp_share_toggle = not is_active_share
                st.rerun()
            
            show_share = st.session_state.camp_share_toggle

        st.markdown("<br>", unsafe_allow_html=True)
        
        _, c_btn, _ = st.columns([1, 1, 1])
        with c_btn:
            submitted = st.button("Gerar Campaign Flow", type="primary", use_container_width=True)


    if submitted:
        st.session_state["camp_search_trigger"] = True
        
        tipos_para_cookie = sel_tipos if sel_tipos else ["Consolidado"]

        new_filters = {
            "dt_ini": str(dt_ini), 
            "dt_fim": str(dt_fim), 
            "praca": sel_praca, 
            "veiculo": sel_veiculo, 
            "concorrentes": sel_concorrentes,
            "tipo_veiculacao": tipos_para_cookie
        }
        cookies["crowley_filters_campaign"] = json.dumps(new_filters)
        cookies.save()

    if st.session_state.get("camp_search_trigger"):
        
        # --- PROCESSAMENTO ---
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

        # --- FUNÇÃO GERADORA DE TABELAS ---
        def criar_tabela_resumo(df_src, lista_anunciantes, is_exclusive=False, calc_share=True):
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
            
            # Se for exclusivo, Share é sempre 100%, retorna simples
            if is_exclusive:
                total_row = pivot_qty.sum(numeric_only=True)
                pivot_qty.loc["TOTAL GERAL"] = total_row
                return pivot_qty
            
            # Versão SEM Share
            if not calc_share:
                pivot_simple = pivot_qty.copy()
                pivot_simple["TOTAL"] = total_por_anunciante
                
                total_row = pivot_simple.sum(numeric_only=True)
                pivot_simple.loc["TOTAL GERAL"] = total_row
                return pivot_simple

            # Versão COM Share (Complexa: Coluna Dupla)
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
            
            # Totais
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
                    total_geral_row.append(np.nan)
            
            df_multi.loc["TOTAL GERAL"] = total_geral_row
            return df_multi

        # --- GERAÇÃO (Cache preventivo) ---
        df1 = criar_tabela_resumo(df_target, exclusivos, is_exclusive=True)
        
        df_full_shared = pd.concat([df_target[df_target["Anunciante"].isin(compartilhados)], df_comp[df_comp["Anunciante"].isin(compartilhados)]])
        df2_share = criar_tabela_resumo(df_full_shared, compartilhados, is_exclusive=False, calc_share=True)
        df2_simple = criar_tabela_resumo(df_full_shared, compartilhados, is_exclusive=False, calc_share=False)
        
        df3_share = criar_tabela_resumo(df_comp, ausentes, is_exclusive=False, calc_share=True)
        df3_simple = criar_tabela_resumo(df_comp, ausentes, is_exclusive=False, calc_share=False)

        # --- ESTILIZAÇÃO ---
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

        def style_df(df, is_exclusive=False, is_share_mode=True):
            if df.empty: return df
            
            header_styles = [
                {'selector': 'th', 'props': [('text-align', 'center'), ('vertical-align', 'middle')]},
                {'selector': 'th.row_heading', 'props': [('text-align', 'left')]},
                {'selector': 'td', 'props': [('text-align', 'center')]}
            ]
            
            if is_exclusive or not is_share_mode:
                s = df.style.format(safe_fmt_int)
            else:
                format_dict = {}
                for col in df.columns:
                    if col[1] == "Share %": format_dict[col] = safe_fmt_pct
                    else: format_dict[col] = safe_fmt_int
                s = df.style.format(format_dict, na_rep=" ")

            s = s.set_properties(**{'text-align': 'center'})
            s = s.set_table_styles(header_styles)
            s = s.apply(lambda x: ["background-color: #f0f2f6; font-weight: bold" if (hasattr(x, 'name') and x.name == "TOTAL GERAL") else "" for i in x], axis=1)
            return s

        # --- ABAS ---
        t1, t2, t3 = st.tabs([f"Exclusivos ({len(exclusivos)})", f"Compartilhados ({len(compartilhados)})", f"Ausentes ({len(ausentes)})"])

        with t1:
            if not df1.empty: st.dataframe(style_df(df1, is_exclusive=True), width="stretch", height=500)
            else: st.info("Nenhum registro.")

        with t2:
            df_to_show = df2_share if show_share else df2_simple
            if not df_to_show.empty: st.dataframe(style_df(df_to_show, is_exclusive=False, is_share_mode=show_share), width="stretch", height=500)
            else: st.info("Nenhum registro.")

        with t3:
            df_to_show = df3_share if show_share else df3_simple
            if not df_to_show.empty: st.dataframe(style_df(df_to_show, is_exclusive=False, is_share_mode=show_share), width="stretch", height=500)
            else: st.info("Nenhum registro.")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- DETALHAMENTO COM LINHA DE TOTAL (Visualização) ---
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
        
        # DF para Exportação (Original, Numérico, sem Total)
        df_exib = df_detalhe[cols_existentes].rename(columns=rename_map)
        df_exib.sort_values(by=["Anunciante", "Data"], inplace=True)
        
        # DF para Visualização (Cópia para mexer à vontade)
        df_exib_view = df_exib.copy()
        
        if not df_exib_view.empty and "Inserções" in df_exib_view.columns:
            total_ins = df_exib_view["Inserções"].sum()
            
            # Cria linha de total com espaços vazios (" ")
            row_total = {col: " " for col in df_exib_view.columns}
            row_total["Anunciante"] = "TOTAL GERAL"
            row_total["Inserções"] = total_ins
            
            # Adiciona linha
            df_exib_view = pd.concat([df_exib_view, pd.DataFrame([row_total])], ignore_index=True)
            
            # --- CORREÇÃO DO ERRO PYARROW: CONVERTER TUDO PARA STRING ---
            df_exib_view = df_exib_view.astype(str)
        
        with st.expander("Fonte de Dados Completa (Detalhamento)", expanded=False):
            st.dataframe(df_exib_view, width="stretch", hide_index=True)

        st.markdown("---")
        
        # ==================== EXPORTAÇÃO COM POP-UP ====================
        _, _, c_btn_exp, _, _ = st.columns([1, 1, 1, 1, 1])
        with c_btn_exp:
            if st.button("Exportar Excel", type="secondary", use_container_width=True):
                st.session_state.show_camp_export = True
        
        # --- DEFINIÇÃO DO DIALOG ---
        if st.session_state.get("show_camp_export", False):
            @st.dialog("Exportação")
            def export_dialog_campaign():
                st.write("Gerando arquivo Excel...")
                
                # Prepara os dados para enviar à função de exportação
                tipos_export = ", ".join(sel_tipos) if sel_tipos else "Todos"
                filters_info = {
                    "Início": dt_ini.strftime("%d/%m/%Y"),
                    "Fim": dt_fim.strftime("%d/%m/%Y"),
                    "Praça": sel_praca,
                    "Veículo": sel_veiculo,
                    "Concorrentes": ", ".join(sel_concorrentes) if sel_concorrentes else "Todos",
                    "Tipo de Veiculação": tipos_export
                }

                dfs_dict = {
                    'exclusivos': df1,
                    'comp_vol': df2_simple,
                    'comp_share': df2_share,
                    'ausentes_vol': df3_simple,
                    'ausentes_share': df3_share,
                    'detalhe': df_exib
                }
                
                # Gera o arquivo
                with st.spinner("Processando dados..."):
                    excel_buffer = generate_campaign_flow_excel(dfs_dict, filters_info)
                
                st.success("Arquivo pronto!")
                
                # INJEÇÃO CSS PARA FORÇAR ESTILO DO BOTÃO DE DOWNLOAD
                st.markdown("""
                    <style>
                    div[data-testid="stDialog"] button[kind="primary"] {
                        background-color: #007bff !important;
                        border-color: #007bff !important;
                        color: white !important;
                    }
                    div[data-testid="stDialog"] button[kind="primary"]:hover {
                        background-color: #0056b3 !important;
                        border-color: #0056b3 !important;
                        color: white !important;
                    }
                    /* Força a cor branca em qualquer elemento de texto dentro do botão */
                    div[data-testid="stDialog"] button[kind="primary"] * {
                        color: white !important;
                    }
                    </style>
                """, unsafe_allow_html=True)
                
                # Botão de Download (Fecha o modal ao clicar)
                st.download_button(
                    label="Baixar Arquivo",
                    data=excel_buffer,
                    file_name=f"Campaign_Flow_{sel_veiculo}_{datetime.now().strftime('%d%m')}.xlsx",
                    mime="application/vnd.ms-excel",
                    type="primary",
                    use_container_width=True,
                    on_click=lambda: st.session_state.update(show_camp_export=False)
                )
                
            export_dialog_campaign()
        
        st.markdown(f"<div style='text-align:center;color:#666;font-size:0.8rem;margin-top:5px;'>Última atualização da base de dados: {data_atualizacao}</div>", unsafe_allow_html=True)