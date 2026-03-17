import streamlit as st
import pandas as pd
import io
import gc
import time
import warnings
from datetime import datetime, date, timedelta
from utils.export_crowley import generate_custom_report_excel

warnings.simplefilter(action='ignore', category=FutureWarning)


@st.cache_data(show_spinner="Indexando dados para o relatório...", ttl=3600)
def prepare_custom_data(df_raw):
    df = df_raw.copy()

    if "Data_Dt" in df.columns:
        df["Data_Dt"] = pd.to_datetime(df["Data_Dt"], errors="coerce")
    elif "Data" in df.columns:
        df["Data_Dt"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")

    if "Data_Dt" in df.columns:
        df["Ano"] = df["Data_Dt"].dt.year
        df["Mes"] = df["Data_Dt"].dt.month
        df["Dia"] = df["Data_Dt"].dt.day

    dim_map = {
        "Ano": "Ano", "Mes": "Mês", "Dia": "Dia", "Praca": "Praça",
        "Emissora": "Veículo", "Anunciante": "Anunciante", "Anuncio": "Anúncio",
        "Tipo": "Tipo de Veiculação", "DayPart": "Faixa Horária",
        "Produto": "Produto", "Programa": "Programa"
    }

    raw_dims = [c for c in dim_map.keys() if c in df.columns]
    valid_dims = sorted(raw_dims, key=lambda x: dim_map.get(x, x))

    return df, valid_dims, dim_map


def _clean_option_value(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    return text


def _build_display_mapping(series):
    mapping = {}
    for value in series.dropna().unique().tolist():
        display = _clean_option_value(value)
        if display is not None and display not in mapping:
            mapping[display] = value
    return dict(sorted(mapping.items(), key=lambda item: item[0]))


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
        keys_to_clear = [
            "custom_step", "custom_pivot_cache", "custom_filters_info", "show_custom_export",
            "cust_rows", "cust_cols", "cust_metrics", "pivot_too_big", "pivot_is_preview",
            "last_struct", "custom_period_signature"
        ]
        for k in list(st.session_state.keys()):
            if k.startswith("custom_filter_"):
                st.session_state.pop(k, None)
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown('<div class="page-title-centered">Relatório Personalizado</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle-centered">Crie sua própria visão dinâmica cruzando os dados disponíveis</div>', unsafe_allow_html=True)

    if df_crowley is None or df_crowley.empty:
        st.error("Base de dados não carregada.")
        st.stop()

    df, valid_dims, dim_map = prepare_custom_data(df_crowley)

    metrics_map = {"Volume de Insercoes": "Inserções", "Duracao": "Duração"}
    valid_metrics = [c for c in metrics_map.keys() if c in df.columns]

    if "custom_step" not in st.session_state:
        st.session_state.custom_step = 1

    st.markdown("#### 1. Estrutura do Relatório")

    default_rows = st.session_state.get("cust_rows", [])
    default_cols = st.session_state.get("cust_cols", [])
    default_metrics = st.session_state.get(
        "cust_metrics",
        ["Volume de Insercoes"] if "Volume de Insercoes" in valid_metrics else []
    )

    with st.form("form_structure"):
        c1, c2, c3 = st.columns(3)
        with c1:
            sel_rows = st.multiselect(
                "Linhas (Índice)",
                options=valid_dims,
                default=default_rows,
                format_func=lambda x: dim_map.get(x, x),
                key="input_rows",
                placeholder="Escolha uma opção"
            )
            add_total_rows = st.checkbox("Adicionar Total (Linhas)", key="input_chk_rows")
        with c2:
            sel_cols = st.multiselect(
                "Colunas",
                options=valid_dims,
                default=default_cols,
                format_func=lambda x: dim_map.get(x, x),
                key="input_cols",
                placeholder="Escolha uma opção"
            )
            add_total_cols = st.checkbox("Adicionar Total (Colunas)", key="input_chk_cols")
        with c3:
            sel_metrics = st.multiselect(
                "Métricas (Valores)",
                options=valid_metrics,
                default=default_metrics,
                format_func=lambda x: metrics_map.get(x, x),
                key="input_metrics",
                placeholder="Escolha uma opção"
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
                st.session_state.pop("custom_period_signature", None)
                for k in list(st.session_state.keys()):
                    if k.startswith("custom_filter_"):
                        st.session_state.pop(k, None)
                st.session_state["last_struct"] = current_struct

            st.session_state.custom_step = 2
            st.rerun()

    if st.session_state.custom_step >= 2:
        st.markdown("---")

        s_rows = st.session_state.cust_rows
        s_cols = st.session_state.cust_cols
        s_metrics = st.session_state.cust_metrics

        st.markdown("##### Período")
        if "Data_Dt" not in df.columns or df["Data_Dt"].dropna().empty:
            st.error("A base não possui datas válidas para o filtro de período.")
            st.stop()

        data_min_base = df["Data_Dt"].min().date()
        data_max_base = df["Data_Dt"].max().date()

        min_date = data_min_base
        try:
            max_date_cfg = datetime.strptime(data_atualizacao, "%d/%m/%Y").date()
            max_date = min(max_date_cfg, data_max_base) if pd.notna(data_max_base) else max_date_cfg
        except Exception:
            max_date = data_max_base

        default_ini = max(min_date, max_date - timedelta(days=30))

        d1, d2, _ = st.columns([1, 1, 2])
        with d1:
            dt_ini = st.date_input("Início", value=default_ini, min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key="custom_dt_ini")
        with d2:
            dt_fim = st.date_input("Fim", value=max_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key="custom_dt_fim")

        if dt_ini > dt_fim:
            st.warning("A data inicial não pode ser maior que a final.")
            st.stop()

        period_signature = f"{dt_ini.isoformat()}__{dt_fim.isoformat()}"
        if st.session_state.get("custom_period_signature") != period_signature:
            for k in list(st.session_state.keys()):
                if k.startswith("custom_filter_"):
                    st.session_state.pop(k, None)
            st.session_state["custom_period_signature"] = period_signature
            st.session_state.pop("custom_pivot_cache", None)
            st.session_state.pop("pivot_is_preview", None)

        ts_ini = pd.Timestamp(dt_ini)
        ts_fim = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        df_period = df[(df["Data_Dt"] >= ts_ini) & (df["Data_Dt"] <= ts_fim)].copy()

        priority_filters = ["Praca", "Emissora", "Anunciante", "Anuncio"]
        hidden_period_dims = {"Ano", "Mes", "Dia", "Data", "Data_Dt"}
        extra_filters = ["Tipo", "Produto", "Programa", "DayPart"]

        fields_ordered = []
        seen = set()
        for col in priority_filters + s_rows + s_cols + extra_filters:
            if col in df.columns and col not in seen and col not in hidden_period_dims:
                fields_ordered.append(col)
                seen.add(col)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Filtros")
        st.caption("Os filtros abaixo respeitam primeiro o período selecionado e depois funcionam em cascata: Praça → Veículo → Anunciante → Anúncio. Mês, ano e dia são controlados apenas pelo período acima.")

        if df_period.empty:
            st.info("Não há dados no período selecionado. Ajuste as datas para carregar as opções de filtro.")
            st.session_state.pop("custom_pivot_cache", None)
            st.stop()

        available_mappings = {}
        df_context = df_period.copy()

        if fields_ordered:
            with st.container(border=True):
                cols_ui = st.columns(3)
                for idx, col_name in enumerate(fields_ordered):
                    display_name = dim_map.get(col_name, col_name)
                    options_map = _build_display_mapping(df_context[col_name]) if col_name in df_context.columns else {}
                    options_list = list(options_map.keys())
                    state_key = f"custom_filter_{col_name}"

                    current_selected = st.session_state.get(state_key, [])
                    valid_selected = [x for x in current_selected if x in options_list]
                    if current_selected != valid_selected:
                        st.session_state[state_key] = valid_selected

                    with cols_ui[idx % 3]:
                        selected_display = st.multiselect(
                            display_name,
                            options=options_list,
                            default=st.session_state.get(state_key, []),
                            key=state_key,
                            placeholder="Todos"
                        )

                    available_mappings[col_name] = options_map
                    selected_actual = [options_map[val] for val in selected_display if val in options_map]
                    if selected_actual:
                        df_context = df_context[df_context[col_name].isin(selected_actual)]

        st.markdown("<br>", unsafe_allow_html=True)
        gen1, gen2, gen3 = st.columns([1, 1, 1])
        with gen2:
            submitted_report = st.button("Gerar Relatório", type="primary", use_container_width=True, key="custom_generate_report")

        if submitted_report:
            with st.spinner("Processando dados..."):
                time.sleep(0.1)

                df_filtered = df_period.copy()
                real_filters_selected = {}

                for col in fields_ordered:
                    state_key = f"custom_filter_{col}"
                    selected_display = st.session_state.get(state_key, [])
                    options_map = available_mappings.get(col, {})
                    selected_actual = [options_map[val] for val in selected_display if val in options_map]
                    if selected_actual:
                        df_filtered = df_filtered[df_filtered[col].isin(selected_actual)]
                        real_filters_selected[dim_map.get(col, col)] = selected_display

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
                                if not st.session_state.add_total_rows and "TOTAL" in pivot.index:
                                    pivot = pivot.drop("TOTAL", axis=0)
                                if not st.session_state.add_total_cols:
                                    if isinstance(pivot.columns, pd.MultiIndex):
                                        try:
                                            pivot = pivot.drop("TOTAL", axis=1, level=0)
                                        except Exception:
                                            pass
                                    elif "TOTAL" in pivot.columns:
                                        pivot = pivot.drop("TOTAL", axis=1)

                            if isinstance(pivot.index, pd.MultiIndex):
                                new_levels = [lvl.astype(str) for lvl in pivot.index.levels]
                                pivot.index = pivot.index.set_levels(new_levels, level=range(len(new_levels)))
                            else:
                                pivot.index = pivot.index.astype(str)

                            new_idx_names = [dim_map.get(n, n) for n in pivot.index.names]
                            pivot.index.names = new_idx_names

                            if pivot.columns.names:
                                pivot.columns.names = [dim_map.get(n, n) for n in pivot.columns.names]

                            if isinstance(pivot.columns, pd.MultiIndex):
                                new_levels = []
                                for level_vals in pivot.columns.levels:
                                    new_vals = [str(metrics_map.get(x, dim_map.get(x, x))) for x in level_vals]
                                    new_levels.append(new_vals)
                                pivot.columns = pivot.columns.set_levels(new_levels, level=range(len(new_levels)))
                            else:
                                pivot.columns = [str(metrics_map.get(x, x)) for x in pivot.columns]

                            MAX_COLS_DISPLAY = 50
                            st.session_state.pivot_is_preview = (pivot.size > 100_000) or (pivot.shape[1] > MAX_COLS_DISPLAY)
                            st.session_state.custom_pivot_cache = pivot
                            st.session_state.custom_filters_info = {
                                "Período": f"{dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}",
                                "Linhas": ", ".join([dim_map.get(x, x) for x in s_rows]),
                                "Colunas": ", ".join([dim_map.get(x, x) for x in s_cols]),
                                "Filtros Aplicados": str(real_filters_selected) if real_filters_selected else "Nenhum"
                            }

                            del df_filtered
                            gc.collect()
                            st.rerun()

                    except Exception as e:
                        st.error(f"Erro no processamento: {e}")

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

            st.markdown(f'''
                <div class="preview-warning">
                    <span>⚠️</span>
                    <div>{warning_msg}</div>
                </div>
            ''', unsafe_allow_html=True)
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

            if df_to_export is not None and df_to_export.shape[1] > 16384:
                st.error(
                    f"Não foi possível concluir o relatório devido ao relatório possuir {df_to_export.shape[1]} colunas (o limite do Excel é 16384). Por favor, ajuste os filtros para gerar um relatório menor."
                )
                if st.button("Fechar", key="btn_close_export_error"):
                    st.session_state.show_custom_export = False
                    st.rerun()
                return

            if df_to_export is not None and df_to_export.size > 500_000:
                st.info("O arquivo é grande, isso pode levar alguns segundos...")

            with st.spinner("Gerando arquivo..."):
                if not isinstance(df_to_export.index, pd.MultiIndex) and isinstance(df_to_export.index.dtype, pd.CategoricalDtype):
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
