# pages/opportunity_radar.py
import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime, timedelta, date

# Nova importação
from utils.export_crowley import generate_opportunity_radar_excel

def render(df_crowley, cookies, data_atualizacao):
    # --- CONFIGURAÇÃO DE PERFORMANCE E VISUAL ---
    pd.set_option("styler.render.max_elements", 5_000_000)

    # CSS Global e Específico
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

    # --- Header e Voltar ---
    if st.button("Voltar", key="btn_voltar_opp"):
        st.query_params["view"] = "menu"
        # Limpa estados específicos do Opportunity Radar
        keys_to_clear = ["opp_search_trigger", "opp_praca_key", "opp_veiculo_key", "opp_anunc_key", "opp_tipo_key", "show_opp_export"]
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        st.rerun()

    # --- TÍTULOS ---
    st.markdown('<div class="page-title-centered">Opportunity Radar</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle-centered">Novos anunciantes de um determinado período</div>', unsafe_allow_html=True)
    
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

    # --- CONFIGURAÇÃO DE DATAS LIMITES ---
    min_date_allowed = date(2024, 1, 1)
    try: max_date_allowed = datetime.strptime(data_atualizacao, "%d/%m/%Y").date()
    except: max_date_allowed = datetime.now().date()
        
    tooltip_dates = f"Dados disponíveis para pesquisa:\nDe 01/01/2024 até {data_atualizacao}"

    # --- COOKIES E FILTROS SALVOS ---
    saved_filters = {}
    cookie_val = cookies.get("crowley_filters_novos") # Mantendo nome do cookie compatível ou altere se preferir
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

    # Datas Default
    default_ini = max(min_date_allowed, max_date_allowed - timedelta(days=30))
    default_ref_fim = max(min_date_allowed, default_ini - timedelta(days=1))
    default_ref_ini = max(min_date_allowed, default_ref_fim - timedelta(days=30))

    val_dt_ini = get_date_from_cookie("dt_ini", default_ini)
    val_dt_fim = get_date_from_cookie("dt_fim", max_date_allowed)
    val_ref_ini = get_date_from_cookie("ref_ini", default_ref_ini)
    val_ref_fim = get_date_from_cookie("ref_fim", default_ref_fim)
    
    saved_praca = get_cookie_val("praca", None)
    saved_veiculo = get_cookie_val("veiculo", "Consolidado (Todas as emissoras)")
    saved_anunciantes = get_cookie_val("anunciantes", [])
    saved_tipos = get_cookie_val("tipo_veiculacao", [])
    if "Consolidado" in saved_tipos: saved_tipos = []

    # --- INTERFACE DE FILTROS ---
    st.markdown("##### Configuração da Análise")
    
    lista_pracas = sorted(df_crowley_copy["Praca"].dropna().unique())
    
    # Init Session State Praça
    if saved_praca not in lista_pracas: saved_praca = lista_pracas[0] if lista_pracas else None
    if "opp_praca_key" not in st.session_state:
        st.session_state.opp_praca_key = saved_praca

    def on_change_reset():
        st.session_state["opp_search_trigger"] = False

    with st.container(border=True):
        
        # 1. Datas
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Período de Análise (Atual)**", help=tooltip_dates)
            col_d1, col_d2 = st.columns(2)
            dt_ini = col_d1.date_input("Início", value=val_dt_ini, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY")
            dt_fim = col_d2.date_input("Fim", value=val_dt_fim, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY")
        
        with c2:
            st.markdown("**Período de Referência (Comparação)**", help=tooltip_dates)
            col_d3, col_d4 = st.columns(2)
            ref_ini = col_d3.date_input("Ref. Início", value=val_ref_ini, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY")
            ref_fim = col_d4.date_input("Ref. Fim", value=val_ref_fim, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY")

        st.divider()

        # --- CÁLCULO DO CONTEXTO (CASCATA) ---
        ts_ini_ctx = pd.Timestamp(dt_ini)
        ts_fim_ctx = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        # Recupera a praça do session state
        sel_praca_ctx = st.session_state.opp_praca_key

        mask_context = (
            (df_crowley_copy["Data_Dt"] >= ts_ini_ctx) &
            (df_crowley_copy["Data_Dt"] <= ts_fim_ctx) &
            (df_crowley_copy["Praca"] == sel_praca_ctx)
        )
        df_context = df_crowley_copy[mask_context]
        
        # Listas Disponíveis no Contexto
        lista_veiculos_local = sorted(df_context["Emissora"].dropna().unique())
        tipos_disponiveis = sorted(df_context["Tipo"].dropna().unique().tolist())
        lista_anunciantes_local = sorted(df_context["Anunciante"].dropna().unique())

        opcao_consolidado = "Consolidado (Todas as emissoras)"
        lista_veiculos_local = [opcao_consolidado] + lista_veiculos_local

        # 2. Filtros Categóricos (Linha 1)
        c3, c4 = st.columns(2)

        with c3:
            sel_praca = st.selectbox(
                "Praça", 
                options=lista_pracas, 
                key="opp_praca_key",
                on_change=on_change_reset
            )

        # Init Session State Veículo
        if "opp_veiculo_key" not in st.session_state:
            val_v = saved_veiculo if saved_veiculo in lista_veiculos_local else opcao_consolidado
            st.session_state.opp_veiculo_key = val_v
        else:
             if st.session_state.opp_veiculo_key not in lista_veiculos_local:
                 st.session_state.opp_veiculo_key = opcao_consolidado

        with c4:
            sel_veiculo = st.selectbox(
                "Veículo Base (Protagonista)", 
                options=lista_veiculos_local,
                key="opp_veiculo_key",
                help="Selecione 'Consolidado' para ver novos em qualquer emissora.",
                on_change=on_change_reset
            )
            
        # 3. Filtros Categóricos (Linha 2 - Tipo e Anunciante)
        c5, c6 = st.columns(2)

        # Init Session State Tipo
        if "opp_tipo_key" not in st.session_state:
            valid_tipos_init = [t for t in saved_tipos if t in tipos_disponiveis]
            st.session_state.opp_tipo_key = valid_tipos_init
        else:
            curr = st.session_state.opp_tipo_key
            st.session_state.opp_tipo_key = [t for t in curr if t in tipos_disponiveis]

        with c5:
            sel_tipos = st.multiselect(
                "Tipo de Veiculação (Opc.)",
                options=tipos_disponiveis,
                key="opp_tipo_key",
                placeholder="Todos",
                on_change=on_change_reset
            )
            
        # Init Session State Anunciante
        if "opp_anunc_key" not in st.session_state:
            valid_anunc = [a for a in saved_anunciantes if a in lista_anunciantes_local]
            st.session_state.opp_anunc_key = valid_anunc
        else:
             curr_a = st.session_state.opp_anunc_key
             st.session_state.opp_anunc_key = [a for a in curr_a if a in lista_anunciantes_local]

        with c6:
            sel_anunciante = st.multiselect(
                "Filtrar Anunciante (Opc.)", 
                options=lista_anunciantes_local, 
                key="opp_anunc_key",
                placeholder="Todos os anunciantes desta praça",
                on_change=on_change_reset
            )

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Botão centralizado
        _, c_btn, _ = st.columns([1, 1, 1])
        with c_btn:
            submitted = st.button("Executar Opportunity Radar", type="primary", use_container_width=True)

    # --- PROCESSAMENTO ---
    if submitted:
        st.session_state["opp_search_trigger"] = True
        
        tipos_para_cookie = sel_tipos if sel_tipos else ["Consolidado"]

        new_filters = {
            "dt_ini": str(dt_ini), "dt_fim": str(dt_fim),
            "ref_ini": str(ref_ini), "ref_fim": str(ref_fim),
            "praca": sel_praca, "veiculo": sel_veiculo,
            "anunciantes": sel_anunciante,
            "tipo_veiculacao": tipos_para_cookie
        }
        cookies["crowley_filters_novos"] = json.dumps(new_filters)
        cookies.save()

    if st.session_state.get("opp_search_trigger"):
        
        df_base = df_crowley_copy.copy()
        
        # Filtros Globais
        mask_base = (df_base["Praca"] == sel_praca)
        if sel_anunciante: mask_base = mask_base & (df_base["Anunciante"].isin(sel_anunciante))
        if sel_tipos: mask_base = mask_base & (df_base["Tipo"].isin(sel_tipos))
        if sel_veiculo != opcao_consolidado: mask_base = mask_base & (df_base["Emissora"] == sel_veiculo)

        df_base = df_base[mask_base]

        # Divisão Temporal
        ts_ini = pd.Timestamp(dt_ini)
        ts_fim = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        ts_ref_ini = pd.Timestamp(ref_ini)
        ts_ref_fim = pd.Timestamp(ref_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        df_atual = df_base[(df_base["Data_Dt"] >= ts_ini) & (df_base["Data_Dt"] <= ts_fim)]
        df_ref = df_base[(df_base["Data_Dt"] >= ts_ref_ini) & (df_base["Data_Dt"] <= ts_ref_fim)]

        # Identificação dos Novos
        anunciantes_atual = set(df_atual["Anunciante"].unique())
        anunciantes_ref = set(df_ref["Anunciante"].unique())
        
        novos_anunciantes = anunciantes_atual - anunciantes_ref

        if not novos_anunciantes:
            st.warning(f"Nenhum anunciante novo encontrado na **{sel_praca}** neste período comparativo.")
        else:
            st.success(f"Encontrados **{len(novos_anunciantes)}** novos anunciantes em relação ao período anterior!")
            
            df_resultado = df_atual[df_atual["Anunciante"].isin(novos_anunciantes)].copy()
            
            # --- TABELA RESUMO (PIVOT) ---
            val_col = "Volume de Insercoes" if "Volume de Insercoes" in df_resultado.columns else "Contagem"
            if val_col == "Contagem": df_resultado["Contagem"] = 1
            agg_func = "sum" if val_col == "Volume de Insercoes" else "count"

            pivot_table = pd.DataFrame()
            try:
                pivot_table = pd.pivot_table(
                    df_resultado, index="Anunciante", columns="Emissora",
                    values=val_col, aggfunc=agg_func, fill_value=0, observed=True 
                )
                pivot_table["TOTAL"] = pivot_table.sum(axis=1)
                pivot_table = pivot_table.sort_values(by="TOTAL", ascending=False)
                
                # TOTALIZADOR (ROW)
                total_row = pivot_table.sum(numeric_only=True)
                pivot_table.loc["TOTAL GERAL"] = total_row
                
                st.markdown("### Visão Geral por Emissora")
                
                def style_pivot(df):
                    s = df.style.background_gradient(cmap="Blues", subset=["TOTAL"])
                    s = s.format("{:.0f}")
                    s = s.apply(lambda x: ["background-color: #f0f2f6; font-weight: bold" if x.name == "TOTAL GERAL" else "" for i in x], axis=1)
                    s = s.set_properties(**{'text-align': 'center'})
                    s = s.set_table_styles([
                        {'selector': 'th', 'props': [('text-align', 'center'), ('vertical-align', 'middle')]},
                        {'selector': 'th.row_heading', 'props': [('text-align', 'left')]},
                        {'selector': 'td', 'props': [('text-align', 'center')]}
                    ])
                    return s

                st.dataframe(
                    style_pivot(pivot_table),
                    width="stretch", 
                    height=min(450, len(pivot_table) * 35 + 40)
                )

            except Exception as e:
                st.error(f"Erro ao gerar tabela dinâmica: {e}")

            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- TABELA DETALHADA ---
            rename_map = {
                "Praca": "Praça", "Anuncio": "Anúncio", "Duracao": "Duração",
                "Emissora": "Veículo", "Volume de Insercoes": "Inserções", 
                "Tipo": "Tipo de Veiculação", "DayPart": "DayPart"
            }
            
            df_detalhe = df_resultado.copy()
            if "Data_Dt" in df_detalhe.columns:
                df_detalhe["Data"] = df_detalhe["Data_Dt"].dt.strftime("%d/%m/%Y")
            
            cols_originais = ["Data", "Anunciante", "Anuncio", "Duracao", "Praca", "Emissora", "Tipo", "DayPart", "Volume de Insercoes"]
            cols_existentes = [c for c in cols_originais if c in df_detalhe.columns]
            
            # DF para EXPORTAÇÃO (Original Numérico)
            df_exib = df_detalhe[cols_existentes].rename(columns=rename_map)
            df_exib.sort_values(by=["Anunciante", "Data"], inplace=True)
            
            # DF para VISUALIZAÇÃO (Com Total e String)
            df_exib_view = df_exib.copy()
            
            if not df_exib_view.empty and "Inserções" in df_exib_view.columns:
                total_ins = df_exib_view["Inserções"].sum()
                
                # Cria linha de total com espaço em branco " "
                row_total = {col: " " for col in df_exib_view.columns}
                row_total["Anunciante"] = "TOTAL GERAL"
                row_total["Inserções"] = total_ins
                
                # Adiciona linha
                df_exib_view = pd.concat([df_exib_view, pd.DataFrame([row_total])], ignore_index=True)
                
                # --- CORREÇÃO DE ERRO PYARROW: Converter para STRING ---
                # Isso impede erros de tipos mistos (Número vs Texto " ")
                df_exib_view = df_exib_view.astype(str)

            with st.expander("Fonte de Dados Completa (Detalhamento)", expanded=False):
                st.dataframe(df_exib_view, width="stretch", hide_index=True)

            st.markdown("---")
            
            # ==================== EXPORTAÇÃO COM POP-UP ====================
            _, _, c_btn_exp, _, _ = st.columns([1, 1, 1, 1, 1])
            with c_btn_exp:
                if st.button("Exportar Excel", type="secondary", use_container_width=True):
                    st.session_state.show_opp_export = True

            # --- DEFINIÇÃO DO DIALOG ---
            if st.session_state.get("show_opp_export", False):
                @st.dialog("Exportação")
                def export_dialog_opp():
                    st.write("Gerando arquivo Excel...")
                    
                    # Prepara dados
                    tipos_export = ", ".join(sel_tipos) if sel_tipos else "Todos"
                    filters_info = {
                        "Início Análise": dt_ini.strftime("%d/%m/%Y"),
                        "Fim Análise": dt_fim.strftime("%d/%m/%Y"),
                        "Início Ref.": ref_ini.strftime("%d/%m/%Y"),
                        "Fim Ref.": ref_fim.strftime("%d/%m/%Y"),
                        "Praça": sel_praca,
                        "Veículo": sel_veiculo,
                        "Filtro Anunciantes": ", ".join(sel_anunciante) if sel_anunciante else "Todos",
                        "Tipo": tipos_export
                    }
                    
                    dfs_dict = {
                        'overview': pivot_table,
                        'detail': df_exib
                    }
                    
                    with st.spinner("Processando dados..."):
                        excel_buffer = generate_opportunity_radar_excel(dfs_dict, filters_info)
                    
                    st.success("Arquivo pronto!")
                    
                    # INJEÇÃO CSS PARA BOTÃO
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
                        div[data-testid="stDialog"] button[kind="primary"] * {
                            color: white !important;
                        }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    st.download_button(
                        label="Baixar Arquivo", 
                        data=excel_buffer,
                        file_name=f"Opportunity_Radar_{sel_praca}_{datetime.now().strftime('%d%m')}.xlsx",
                        mime="application/vnd.ms-excel",
                        type="primary", 
                        use_container_width=True,
                        on_click=lambda: st.session_state.update(show_opp_export=False)
                    )
                
                export_dialog_opp()
            
            st.markdown(f"""
                <div style="text-align: center; color: #666; font-size: 0.8rem; margin-top: 5px;">
                    Última atualização da base de dados: {data_atualizacao}
                </div>
            """, unsafe_allow_html=True)