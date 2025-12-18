# crowley/busca_novos.py
import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime, timedelta, date

def render(df_crowley, cookies, data_atualizacao):
    # --- CONFIGURAÇÃO DE PERFORMANCE E VISUAL ---
    pd.set_option("styler.render.max_elements", 5_000_000)

    # CSS para centralização
    st.markdown("""
        <style>
        /* Cabeçalhos centralizados */
        [data-testid="stDataFrame"] th {
            text-align: center !important;
            vertical-align: middle !important;
        }
        /* Células centralizadas por padrão */
        [data-testid="stDataFrame"] td {
            text-align: center !important;
            vertical-align: middle !important;
        }
        /* Alinha à esquerda apenas a primeira coluna de dados */
        [data-testid="stDataFrame"] th[data-testid="stColumnHeader"]:first-child,
        [data-testid="stDataFrame"] td:first-child {
            text-align: left !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- Header e Voltar ---
    if st.button("Voltar", key="btn_voltar_novos"):
        st.query_params["view"] = "menu"
        # Limpa estados
        keys_to_clear = ["novos_search_trigger", "novos_praca_key", "novos_veiculo_key", "novos_anunc_key", "novos_tipo_key"]
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown('<div class="page-title-centered">Busca de Novos Anunciantes</div>', unsafe_allow_html=True)
    
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
    cookie_val = cookies.get("crowley_filters_novos")
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
    if "novos_praca_key" not in st.session_state:
        st.session_state.novos_praca_key = saved_praca

    def on_change_reset():
        st.session_state["novos_search_trigger"] = False

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
        # Filtra a base pelo Período de Análise e Praça para definir o que está disponível
        ts_ini_ctx = pd.Timestamp(dt_ini)
        ts_fim_ctx = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        # Recupera a praça do session state (pois o selectbox usa key)
        sel_praca_ctx = st.session_state.novos_praca_key

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
                key="novos_praca_key",
                on_change=on_change_reset
            )

        # Init Session State Veículo
        if "novos_veiculo_key" not in st.session_state:
            val_v = saved_veiculo if saved_veiculo in lista_veiculos_local else opcao_consolidado
            st.session_state.novos_veiculo_key = val_v
        else:
             # Validação dinâmica
             if st.session_state.novos_veiculo_key not in lista_veiculos_local:
                 st.session_state.novos_veiculo_key = opcao_consolidado

        with c4:
            sel_veiculo = st.selectbox(
                "Veículo Base (Protagonista)", 
                options=lista_veiculos_local,
                key="novos_veiculo_key",
                help="Selecione 'Consolidado' para ver novos em qualquer emissora.",
                on_change=on_change_reset
            )
            
        # 3. Filtros Categóricos (Linha 2 - Tipo e Anunciante)
        c5, c6 = st.columns(2)

        # Init Session State Tipo (Cascata)
        if "novos_tipo_key" not in st.session_state:
            valid_tipos_init = [t for t in saved_tipos if t in tipos_disponiveis]
            st.session_state.novos_tipo_key = valid_tipos_init
        else:
            # Manutenção da seleção
            curr = st.session_state.novos_tipo_key
            st.session_state.novos_tipo_key = [t for t in curr if t in tipos_disponiveis]

        with c5:
            sel_tipos = st.multiselect(
                "Tipo de Veiculação (Opc.)",
                options=tipos_disponiveis,
                key="novos_tipo_key",
                placeholder="Todos",
                on_change=on_change_reset
            )
            
        # Init Session State Anunciante
        if "novos_anunc_key" not in st.session_state:
            valid_anunc = [a for a in saved_anunciantes if a in lista_anunciantes_local]
            st.session_state.novos_anunc_key = valid_anunc
        else:
             curr_a = st.session_state.novos_anunc_key
             st.session_state.novos_anunc_key = [a for a in curr_a if a in lista_anunciantes_local]

        with c6:
            sel_anunciante = st.multiselect(
                "Filtrar Anunciante (Opc.)", 
                options=lista_anunciantes_local,
                key="novos_anunc_key",
                placeholder="Todos os anunciantes desta praça",
                on_change=on_change_reset
            )

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Botão centralizado reduzido
        c_v1, c_btn, c_v2 = st.columns([1, 1, 1])
        with c_btn:
            submitted = st.button("Pesquisar Novos Anunciantes", type="primary", use_container_width=True)

    # --- PROCESSAMENTO ---
    
    if submitted:
        st.session_state["novos_search_trigger"] = True
        
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

    if st.session_state.get("novos_search_trigger"):
        
        # 1. Filtro Base (Comum a ambos os períodos: Praça e Anunciante específico e TIPO)
        # Importante: O filtro de Tipo deve ser aplicado TANTO no período atual QUANTO no de referência?
        # Sim. Se estamos buscando novos anunciantes de "Merchandising", devemos ver quem fez Merchan agora mas NÃO fez Merchan antes.
        
        df_base = df_crowley_copy.copy()
        
        # Filtros Globais
        mask_base = (df_base["Praca"] == sel_praca)
        
        if sel_anunciante:
            mask_base = mask_base & (df_base["Anunciante"].isin(sel_anunciante))
            
        if sel_tipos:
            mask_base = mask_base & (df_base["Tipo"].isin(sel_tipos))

        # Filtro de Veículo (Se selecionado específico)
        # Nota: Novos Anunciantes geralmente compara a PRESENÇA na praça/veículo
        if sel_veiculo != opcao_consolidado:
            mask_base = mask_base & (df_base["Emissora"] == sel_veiculo)

        df_base = df_base[mask_base]

        # 2. Divisão Temporal
        ts_ini = pd.Timestamp(dt_ini)
        ts_fim = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        ts_ref_ini = pd.Timestamp(ref_ini)
        ts_ref_fim = pd.Timestamp(ref_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        df_atual = df_base[(df_base["Data_Dt"] >= ts_ini) & (df_base["Data_Dt"] <= ts_fim)]
        df_ref = df_base[(df_base["Data_Dt"] >= ts_ref_ini) & (df_base["Data_Dt"] <= ts_ref_fim)]

        # 3. Identificação dos Novos
        anunciantes_atual = set(df_atual["Anunciante"].unique())
        anunciantes_ref = set(df_ref["Anunciante"].unique())
        
        novos_anunciantes = anunciantes_atual - anunciantes_ref

        if not novos_anunciantes:
            st.warning(f"Nenhum anunciante novo encontrado na **{sel_praca}** neste período comparativo (com os filtros aplicados).")
        else:
            st.success(f"Encontrados **{len(novos_anunciantes)}** novos anunciantes em relação ao período anterior!")
            
            # Filtra os dados atuais para mostrar apenas os novos
            df_resultado = df_atual[df_atual["Anunciante"].isin(novos_anunciantes)].copy()
            
            # --- TABELA RESUMO (PIVOT) ---
            val_col = "Volume de Insercoes" if "Volume de Insercoes" in df_resultado.columns else "Contagem"
            if val_col == "Contagem": df_resultado["Contagem"] = 1
            agg_func = "sum" if val_col == "Volume de Insercoes" else "count"

            pivot_table = pd.DataFrame()
            try:
                pivot_table = pd.pivot_table(
                    df_resultado,
                    index="Anunciante",
                    columns="Emissora",
                    values=val_col,
                    aggfunc=agg_func,
                    fill_value=0,
                    observed=True 
                )
                pivot_table["TOTAL"] = pivot_table.sum(axis=1)
                pivot_table = pivot_table.sort_values(by="TOTAL", ascending=False)
                
                # --- ADICIONA TOTALIZADOR (ROW) ---
                total_row = pivot_table.sum(numeric_only=True)
                pivot_table.loc["TOTAL GERAL"] = total_row
                
                st.markdown("### Visão Geral por Emissora")
                
                # Estilização
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
            
            df_exibicao = df_detalhe[cols_existentes].rename(columns=rename_map)
            df_exibicao.sort_values(by=["Anunciante", "Data"], inplace=True)

            with st.expander("Fonte de Dados (Detalhamento)", expanded=False):
                st.dataframe(df_exibicao, width="stretch", hide_index=True)

            # --- EXPORTAÇÃO EXCEL ---
            st.markdown("---")
            with st.spinner("Gerando Excel..."):
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    workbook = writer.book
                    
                    fmt_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
                    fmt_left = workbook.add_format({'align': 'left', 'valign': 'vcenter'})
                    
                    tipos_str = ", ".join(sel_tipos) if sel_tipos else "Todos"
                    anunciantes_str = ", ".join(sel_anunciante) if sel_anunciante else "Todos"

                    # 1. Filtros
                    filtros_dict = {
                        "Parâmetro": [
                            "Período de Análise (Início)", "Período de Análise (Fim)",
                            "Período de Referência (Início)", "Período de Referência (Fim)",
                            "Praça Selecionada", "Veículo Base", "Filtro Anunciantes", "Tipo de Veiculação"
                        ],
                        "Valor": [
                            dt_ini.strftime("%d/%m/%Y"), dt_fim.strftime("%d/%m/%Y"),
                            ref_ini.strftime("%d/%m/%Y"), ref_fim.strftime("%d/%m/%Y"),
                            sel_praca, sel_veiculo,
                            anunciantes_str, tipos_str
                        ]
                    }
                    pd.DataFrame(filtros_dict).to_excel(writer, sheet_name='Filtros', index=False)
                    writer.sheets['Filtros'].set_column('A:A', 30); writer.sheets['Filtros'].set_column('B:B', 50)
                    
                    # 2. Visão Geral (Pivot)
                    if not pivot_table.empty:
                        pivot_table.to_excel(writer, sheet_name='Visão Geral')
                        worksheet_pivot = writer.sheets['Visão Geral']
                        worksheet_pivot.set_column('A:A', 40, fmt_left) 
                        worksheet_pivot.set_column('B:Z', 15, fmt_center)

                    # 3. Detalhamento
                    if not df_exibicao.empty:
                        col_insercoes = "Inserções" if "Inserções" in df_exibicao.columns else None
                        df_export_det = df_exibicao.copy()
                        
                        # Adiciona total no detalhamento exportado
                        if col_insercoes:
                            total_ins = df_export_det[col_insercoes].sum()
                            new_row_exp = {c: "" for c in df_export_det.columns}
                            new_row_exp["Anunciante"] = "TOTAL GERAL"
                            new_row_exp[col_insercoes] = total_ins
                            if "Duração" in df_export_det.columns: new_row_exp["Duração"] = 0
                            
                            df_export_det = pd.concat([df_export_det, pd.DataFrame([new_row_exp])], ignore_index=True)

                        df_export_det.to_excel(writer, sheet_name='Detalhamento', index=False)
                        worksheet_detalhe = writer.sheets['Detalhamento']
                        
                        for idx, col_name in enumerate(df_export_det.columns):
                            if col_name in ["Anunciante", "Anúncio", "Tipo de Veiculação"]:
                                worksheet_detalhe.set_column(idx, idx, 35, fmt_left)
                            else:
                                worksheet_detalhe.set_column(idx, idx, 15, fmt_center)

            c_vazio1, c_vazio2, c_btn, c_vazio3, c_vazio4 = st.columns([1, 1, 1, 1, 1])
            with c_btn:
                st.download_button(
                    label="Exportar Excel", 
                    data=buffer,
                    file_name=f"Novos_Anunciantes_{sel_praca}_{datetime.now().strftime('%d%m')}.xlsx",
                    mime="application/vnd.ms-excel",
                    type="secondary", 
                    use_container_width=True
                )
            
            st.markdown(f"""
                <div style="text-align: center; color: #666; font-size: 0.8rem; margin-top: 5px;">
                    Última atualização da base de dados: {data_atualizacao}
                </div>
            """, unsafe_allow_html=True)