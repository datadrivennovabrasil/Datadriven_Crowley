# pages/relatorio_personalizado.py
import streamlit as st
import pandas as pd
import numpy as np
import io
import gc
import time
import warnings
from datetime import datetime, date, timedelta
from utils.export_crowley import generate_custom_report_excel

# Suprime avisos futuros do Pandas
warnings.simplefilter(action='ignore', category=FutureWarning)

# ==============================================================================
# FUNÇÃO DE CACHE OTIMIZADA
# ==============================================================================
@st.cache_data(show_spinner="Indexando dados para o relatório...", ttl=3600)
def prepare_custom_data(df_raw):
    # Cria cópia leve
    df = df_raw.copy()
    
    # Garante Data
    if "Data_Dt" not in df.columns and "Data" in df.columns:
        df["Data_Dt"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    
    # Mapeamento de Nomes
    dim_map = {
        "Ano": "Ano", "Mes": "Mês", "Dia": "Dia", "Praca": "Praça", 
        "Emissora": "Veículo", "Anunciante": "Anunciante", "Anuncio": "Anúncio",
        "Tipo": "Tipo de Veiculação", "DayPart": "Faixa Horária", 
        "Produto": "Produto", "Programa": "Programa"
    }
    
    # Identifica colunas válidas
    raw_dims = [c for c in dim_map.keys() if c in df.columns]
    
    # ORDENAÇÃO ALFABÉTICA (A-Z)
    valid_dims = sorted(raw_dims, key=lambda x: dim_map.get(x, x))
    
    # Gera opções de filtros usando categorias (Performance)
    filters_options = {}
    for col in valid_dims:
        if isinstance(df[col].dtype, pd.CategoricalDtype):
            opts = df[col].cat.categories.tolist()
        else:
            opts = df[col].dropna().unique().tolist()
            
        opts_str = sorted([str(x) for x in opts if x is not None and str(x).strip() != "" and str(x) != "nan"])
        filters_options[col] = opts_str

    return df, filters_options, valid_dims, dim_map

# ==============================================================================
# RENDERIZAÇÃO
# ==============================================================================
def render(df_crowley, cookies, data_atualizacao):
    pd.set_option("styler.render.max_elements", 5_000_000)

    st.markdown("""
        <style>
        .page-title-centered { text-align: center; font-size: 2.5rem; font-weight: 700; color: #003366; margin-top: 1rem; }
        .page-subtitle-centered { text-align: center; color: #666; font-size: 1rem; margin-bottom: 2rem; }
        [data-testid="stDataFrame"] { width: 100%; }
        [data-testid="stCheckbox"] label { font-size: 0.85rem !important; }
        .preview-warning {
            padding: 0.8rem; background-color: #fff3cd; border-left: 5px solid #ffc107;
            border-radius: 4px; color: #856404; font-size: 0.9rem; margin-bottom: 1rem;
            display: flex; align-items: center; gap: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

    if st.button("Voltar", key="btn_voltar_custom"):
        st.query_params["view"] = "menu"
        keys_to_clear = ["custom_step", "custom_pivot_cache", "custom_filters_info", "show_custom_export", "cust_rows", "cust_cols", "cust_metrics", "pivot_too_big", "pivot_is_preview"]
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown('<div class="page-title-centered">Relatório Personalizado</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle-centered">Crie sua própria visão dinâmica cruzando os dados disponíveis</div>', unsafe_allow_html=True)

    if df_crowley is None or df_crowley.empty:
        st.error("Base de dados não carregada.")
        st.stop()

    df, cached_filters_options, valid_dims, dim_map = prepare_custom_data(df_crowley)

    metrics_map = {"Volume de Insercoes": "Inserções", "Duracao": "Duração"}
    valid_metrics = [c for c in metrics_map.keys() if c in df.columns]

    if "custom_step" not in st.session_state:
        st.session_state.custom_step = 1

    # =========================================================
    # ETAPA 1: ESTRUTURA (FORM)
    # =========================================================
    st.markdown("#### 1. Estrutura do Relatório")
    
    default_rows = st.session_state.get("cust_rows", [])
    default_cols = st.session_state.get("cust_cols", [])
    default_metrics = st.session_state.get("cust_metrics", ["Volume de Insercoes"] if "Volume de Insercoes" in valid_metrics else [])
    
    with st.form("form_structure"):
        c1, c2, c3 = st.columns(3)
        with c1:
            sel_rows = st.multiselect(
                "Linhas (Índice)", 
                options=valid_dims, 
                default=default_rows, 
                format_func=lambda x: dim_map.get(x, x), 
                key="input_rows",
                placeholder="Escolha uma opção"  # Tradução
            )
            add_total_rows = st.checkbox("Adicionar Total (Linhas)", key="input_chk_rows")
        with c2:
            sel_cols = st.multiselect(
                "Colunas", 
                options=valid_dims, 
                default=default_cols, 
                format_func=lambda x: dim_map.get(x, x), 
                key="input_cols",
                placeholder="Escolha uma opção"  # Tradução
            )
            add_total_cols = st.checkbox("Adicionar Total (Colunas)", key="input_chk_cols")
        with c3:
            sel_metrics = st.multiselect(
                "Métricas (Valores)", 
                options=valid_metrics, 
                default=default_metrics, 
                format_func=lambda x: metrics_map.get(x, x), 
                key="input_metrics",
                placeholder="Escolha uma opção"  # Tradução
            )
            st.caption("Selecione os valores a calcular")

        st.markdown("<br>", unsafe_allow_html=True)
        cb1, cb2, cb3 = st.columns([1, 1, 1])
        with cb2:
            label_btn_struct = "Atualizar Estrutura" if st.session_state.custom_step >= 2 else "Continuar para Filtros"
            submitted_struct = st.form_submit_button(label_btn_struct, type="primary", use_container_width=True)

    if submitted_struct:
        intersection = set(sel_rows) & set(sel_cols)
        if not sel_rows and not sel_cols:
            st.error("Selecione pelo menos uma Linha ou Coluna.")
        elif not sel_metrics:
            st.error("Selecione pelo menos uma Métrica.")
        elif intersection:
            st.error(f"Erro: O campo '{dim_map.get(list(intersection)[0])}' não pode estar em Linhas e Colunas ao mesmo tempo.")
        else:
            st.session_state.cust_rows = sel_rows
            st.session_state.cust_cols = sel_cols
            st.session_state.cust_metrics = sel_metrics
            st.session_state.add_total_rows = add_total_rows
            st.session_state.add_total_cols = add_total_cols
            
            current_struct = (sel_rows, sel_cols, sel_metrics, add_total_rows, add_total_cols)
            if st.session_state.get("last_struct") != current_struct:
                st.session_state.pop("custom_pivot_cache", None)
                st.session_state.pop("pivot_is_preview", None)
                st.session_state["last_struct"] = current_struct
            
            st.session_state.custom_step = 2
            st.rerun()

    # =========================================================
    # ETAPA 2: FILTROS (FORM)
    # =========================================================
    if st.session_state.custom_step >= 2:
        st.markdown("---")
        
        s_rows = st.session_state.cust_rows
        s_cols = st.session_state.cust_cols
        s_metrics = st.session_state.cust_metrics
        
        with st.form("form_filters"):
            # Período
            st.markdown("##### Período") 
            
            min_date = date(2024, 1, 1)
            try: max_date = datetime.strptime(data_atualizacao, "%d/%m/%Y").date()
            except: max_date = datetime.now().date()
            default_ini = max(min_date, max_date - timedelta(days=30))
            
            d1, d2, _ = st.columns([1, 1, 2])
            with d1:
                # Alteração: Formato DD/MM/YYYY
                dt_ini = st.date_input("Início", value=default_ini, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
            with d2:
                # Alteração: Formato DD/MM/YYYY
                dt_fim = st.date_input("Fim", value=max_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

            # Construção Dinâmica dos Filtros (Respeitando Ordem)
            fields_ordered = []
            seen = set()
            
            for c in s_rows + s_cols:
                if c not in seen:
                    fields_ordered.append(c)
                    seen.add(c)
            
            if "Praca" not in seen:
                fields_ordered.insert(0, "Praca")
                seen.add("Praca")
            
            fields_to_filter = [f for f in fields_ordered if f not in ["Data", "Data_Dt"]]
            
            filters_selected_ui = {}
            if fields_to_filter:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("##### Filtros")
                with st.container(border=True):
                    cols_ui = st.columns(3)
                    
                    for idx, col_name in enumerate(fields_to_filter):
                        with cols_ui[idx % 3]:
                            display_name = dim_map.get(col_name, col_name)
                            options_list = cached_filters_options.get(col_name, [])
                            
                            filters_selected_ui[col_name] = st.multiselect(
                                f"{display_name}", 
                                options=options_list,
                                placeholder="Todos", # Garante placeholder em filtros também
                                key=f"filter_{col_name}"
                            )

            st.markdown("<br>", unsafe_allow_html=True)
            gen1, gen2, gen3 = st.columns([1, 1, 1])
            with gen2:
                submitted_report = st.form_submit_button("Gerar Relatório", type="primary", use_container_width=True)

        if submitted_report:
            with st.spinner("Processando dados..."):
                time.sleep(0.1)
                
                ts_ini = pd.Timestamp(dt_ini)
                ts_fim = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                
                # 1. Filtro Data
                mask = (df["Data_Dt"] >= ts_ini) & (df["Data_Dt"] <= ts_fim)
                
                # 2. Filtros Dinâmicos
                real_filters_selected = {}
                for col, vals in filters_selected_ui.items():
                    if vals:
                        mask = mask & (df[col].isin(vals))
                        real_filters_selected[col] = vals
                
                df_filtered = df[mask]
                
                if df_filtered.empty:
                    st.warning("Nenhum dado encontrado para o período/filtros.")
                    st.session_state.pop("custom_pivot_cache", None)
                else:
                    try:
                        est_rows = df_filtered[s_rows].drop_duplicates().shape[0] if s_rows else 1
                        est_cols = df_filtered[s_cols].drop_duplicates().shape[0] if s_cols else 1
                        total_cells = est_rows * est_cols * len(s_metrics)
                        
                        if total_cells > 6_000_000:
                            st.error(f"Relatório muito grande (~{total_cells:,.0f} células). Filtre mais.")
                            st.session_state.pop("custom_pivot_cache", None)
                        else:
                            use_margins = st.session_state.add_total_rows or st.session_state.add_total_cols
                            pivot = pd.pivot_table(
                                df_filtered,
                                index=s_rows if s_rows else None,
                                columns=s_cols if s_cols else None,
                                values=s_metrics,
                                aggfunc="sum",
                                fill_value=0,
                                margins=use_margins,
                                margins_name="TOTAL",
                                observed=True 
                            )

                            if use_margins:
                                if not st.session_state.add_total_rows:
                                    if "TOTAL" in pivot.index: pivot = pivot.drop("TOTAL", axis=0)
                                if not st.session_state.add_total_cols:
                                    if isinstance(pivot.columns, pd.MultiIndex):
                                        try: pivot = pivot.drop("TOTAL", axis=1, level=0)
                                        except: pass 
                                    else:
                                        if "TOTAL" in pivot.columns: pivot = pivot.drop("TOTAL", axis=1)

                            # --- BLINDAGEM CONTRA ARROWINVALID (ÍNDICES) ---
                            if isinstance(pivot.index, pd.MultiIndex):
                                new_levels = [lvl.astype(str) for lvl in pivot.index.levels]
                                pivot.index = pivot.index.set_levels(new_levels, level=range(len(new_levels)))
                            else:
                                pivot.index = pivot.index.astype(str)
                            
                            # --- RENOMEAÇÃO DE ÍNDICES ---
                            new_idx_names = [dim_map.get(n, n) for n in pivot.index.names]
                            pivot.index.names = new_idx_names
                            
                            # --- RENOMEAÇÃO E CORREÇÃO DE COLUNAS (MIXED TYPES) ---
                            if pivot.columns.names:
                                pivot.columns.names = [dim_map.get(n, n) for n in pivot.columns.names]

                            if isinstance(pivot.columns, pd.MultiIndex):
                                new_levels = []
                                for level_vals in pivot.columns.levels:
                                    # Força string para evitar Warning do PyArrow em colunas mistas
                                    new_vals = [str(metrics_map.get(x, dim_map.get(x, x))) for x in level_vals]
                                    new_levels.append(new_vals)
                                pivot.columns = pivot.columns.set_levels(new_levels, level=range(len(new_levels)))
                            else:
                                # Força string aqui também
                                new_cols = [str(metrics_map.get(x, x)) for x in pivot.columns]
                                pivot.columns = new_cols
                            # ----------------------------------------------------

                            # --- TRAVA DE VISUALIZAÇÃO ---
                            MAX_COLS_DISPLAY = 50
                            st.session_state.pivot_is_preview = (pivot.size > 100_000) or (pivot.shape[1] > MAX_COLS_DISPLAY)
                            st.session_state.custom_pivot_cache = pivot
                            
                            st.session_state.custom_filters_info = {
                                "Período": f"{dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}",
                                "Linhas": ", ".join([dim_map.get(x,x) for x in s_rows]),
                                "Colunas": ", ".join([dim_map.get(x,x) for x in s_cols]),
                                "Filtros Aplicados": str(real_filters_selected) if real_filters_selected else "Nenhum"
                            }
                            
                            del df_filtered
                            gc.collect()
                            st.rerun()

                    except Exception as e:
                        st.error(f"Erro no processamento: {e}")

    # =========================================================
    # 3. EXIBIÇÃO
    # =========================================================
    if "custom_pivot_cache" in st.session_state:
        full_pivot = st.session_state.custom_pivot_cache
        is_preview = st.session_state.get("pivot_is_preview", False)
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        if is_preview:
            preview_rows = 500
            preview_cols = 50
            
            pivot_display = full_pivot.iloc[:preview_rows, :preview_cols]
            
            warning_msg = f"<strong>Prévia de Exibição</strong><br>O relatório completo possui <strong>{len(full_pivot):,.0f} linhas</strong> e <strong>{full_pivot.shape[1]} colunas</strong>."
            
            reasons = []
            if full_pivot.shape[0] > preview_rows:
                reasons.append(f"apenas as primeiras {preview_rows} linhas")
            if full_pivot.shape[1] > preview_cols:
                reasons.append(f"apenas as primeiras {preview_cols} colunas")
            
            if reasons:
                warning_msg += f"<br>Exibindo {' e '.join(reasons)}. Baixe o Excel para ver tudo."

            st.markdown(f"""
                <div class="preview-warning">
                    <span>⚠️</span>
                    <div>{warning_msg}</div>
                </div>
            """, unsafe_allow_html=True)
            st.dataframe(pivot_display, height=500, width="stretch")
        else:
            st.success("Relatório gerado com sucesso!")
            st.dataframe(full_pivot, height=600, width="stretch")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        c_exp1, c_exp_btn, c_exp2 = st.columns([1, 1, 1])
        with c_exp_btn:
            if st.button("Exportar Excel", type="secondary", use_container_width=True):
                st.session_state.show_custom_export = True
                st.rerun()

    if st.session_state.get("show_custom_export", False):
        @st.dialog("Exportação Personalizada")
        def export_dialog_custom():
            st.write("Preparando arquivo Excel...")
            df_to_export = st.session_state.get("custom_pivot_cache")
            filters_info = st.session_state.get("custom_filters_info", {})
            
            # --- VERIFICAÇÃO DE LIMITE DE COLUNAS DO EXCEL ---
            if df_to_export is not None and df_to_export.shape[1] > 16384:
                st.error(f"Não foi possível concluir o relatório devido ao relatório possuir {df_to_export.shape[1]} colunas (o limite do Excel é 16384). Por favor, ajuste os filtros para gerar um relatório menor.")
                if st.button("Fechar", key="btn_close_export_error"):
                    st.session_state.show_custom_export = False
                    st.rerun()
                return
            # -------------------------------------------------

            if df_to_export is not None and df_to_export.size > 500_000:
                st.info("O arquivo é grande, isso pode levar alguns segundos...")
            
            with st.spinner("Gerando arquivo..."):
                if isinstance(df_to_export.index, pd.MultiIndex):
                    pass 
                else:
                    if isinstance(df_to_export.index.dtype, pd.CategoricalDtype):
                        df_to_export.index = df_to_export.index.astype(str)

                excel_buffer = generate_custom_report_excel(df_to_export, filters_info)
            
            st.success("Pronto!")
            
            st.markdown("""
                <style>
                div[data-testid="stDialog"] button[kind="primary"] {
                    background-color: #007bff !important; 
                    border-color: #007bff !important; 
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
                file_name=f"Relatorio_Personalizado_{datetime.now().strftime('%d%m_%H%M')}.xlsx",
                mime="application/vnd.ms-excel",
                type="primary", 
                use_container_width=True,
                on_click=lambda: st.session_state.update(show_custom_export=False)
            )
        export_dialog_custom()
