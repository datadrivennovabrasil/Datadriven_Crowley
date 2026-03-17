import gc
import time
import warnings
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from utils.export_crowley import generate_custom_report_excel

warnings.simplefilter(action="ignore", category=FutureWarning)

# Limites defensivos para evitar travamentos por volume
MAX_ESTIMATED_CELLS = 4_000_000
MAX_PREVIEW_ROWS = 500
MAX_PREVIEW_COLS = 50
MAX_PREVIEW_SIZE = 100_000
MAX_EXCEL_CELLS = 500_000
MAX_EXCEL_COLUMNS = 16_384
FILTER_HELP_TEXT = (
    "Os filtros abaixo respeitam primeiro o período selecionado e depois funcionam em cascata: "
    "Praça → Veículo → Anunciante → Anúncio."
)


@st.cache_data(show_spinner="Indexando dados para o relatório...", ttl=3600)
def prepare_custom_data(df_raw: pd.DataFrame):
    """Pré-processa a base uma única vez para a página customizada."""
    df = df_raw.copy()

    if "Data_Dt" in df.columns:
        df["Data_Dt"] = pd.to_datetime(df["Data_Dt"], errors="coerce")
    elif "Data" in df.columns:
        df["Data_Dt"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    else:
        df["Data_Dt"] = pd.NaT

    if "Data_Dt" in df.columns:
        df["Ano"] = df["Data_Dt"].dt.year.astype("Int32")
        df["Mes"] = df["Data_Dt"].dt.month.astype("Int16")
        df["Dia"] = df["Data_Dt"].dt.day.astype("Int16")

    for metric_col in ["Volume de Insercoes", "Duracao"]:
        if metric_col in df.columns:
            df[metric_col] = pd.to_numeric(df[metric_col], errors="coerce").fillna(0)

    dim_map = {
        "Ano": "Ano",
        "Mes": "Mês",
        "Dia": "Dia",
        "Praca": "Praça",
        "Emissora": "Veículo",
        "Anunciante": "Anunciante",
        "Anuncio": "Anúncio",
        "Tipo": "Tipo de Veiculação",
        "DayPart": "Faixa Horária",
        "Produto": "Produto",
        "Programa": "Programa",
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


def _build_display_mapping(series: pd.Series) -> dict:
    mapping = {}
    for value in pd.unique(series.dropna()):
        display = _clean_option_value(value)
        if display is not None and display not in mapping:
            mapping[display] = value
    return dict(sorted(mapping.items(), key=lambda item: item[0]))


def _coerce_selection_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _clear_custom_filters():
    for key in list(st.session_state.keys()):
        if key.startswith("custom_filter_"):
            st.session_state.pop(key, None)


def _reset_custom_outputs():
    st.session_state.pop("custom_pivot_cache", None)
    st.session_state.pop("pivot_is_preview", None)
    st.session_state.pop("custom_filters_info", None)
    st.session_state.pop("show_custom_export", None)


def _format_selected_filters(real_filters_selected: dict) -> str:
    if not real_filters_selected:
        return "Nenhum"
    parts = []
    for label, values in real_filters_selected.items():
        if values:
            parts.append(f"{label}: {', '.join(map(str, values))}")
    return " | ".join(parts) if parts else "Nenhum"


def render(df_crowley, cookies, data_atualizacao):
    pd.set_option("styler.render.max_elements", 5_000_000)

    st.markdown(
        """
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
        """,
        unsafe_allow_html=True,
    )

    if st.button("Voltar", key="btn_voltar_custom"):
        st.query_params["view"] = "menu"
        keys_to_clear = [
            "custom_step",
            "custom_filters_info",
            "cust_rows",
            "cust_cols",
            "cust_metrics",
            "last_struct",
            "custom_period_signature",
            "add_total_rows",
            "add_total_cols",
        ]
        _clear_custom_filters()
        for key in keys_to_clear:
            st.session_state.pop(key, None)
        _reset_custom_outputs()
        st.rerun()

    st.markdown('<div class="page-title-centered">Relatório Personalizado</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle-centered">Crie sua própria visão dinâmica cruzando os dados disponíveis</div>',
        unsafe_allow_html=True,
    )

    if df_crowley is None or df_crowley.empty:
        st.error("Base de dados não carregada.")
        st.stop()

    df, valid_dims, dim_map = prepare_custom_data(df_crowley)

    metrics_map = {"Volume de Insercoes": "Inserções", "Duracao": "Duração"}
    valid_metrics = [c for c in metrics_map.keys() if c in df.columns]

    if not valid_dims:
        st.error("A base não possui dimensões suficientes para montar o relatório.")
        st.stop()
    if not valid_metrics:
        st.error("A base não possui métricas válidas para o relatório personalizado.")
        st.stop()

    if "custom_step" not in st.session_state:
        st.session_state.custom_step = 1

    st.markdown("#### 1. Estrutura do Relatório")

    default_rows = st.session_state.get("cust_rows", [])
    default_cols = st.session_state.get("cust_cols", [])
    default_metrics = st.session_state.get(
        "cust_metrics",
        ["Volume de Insercoes"] if "Volume de Insercoes" in valid_metrics else valid_metrics[:1],
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
                placeholder="Escolha uma opção",
            )
            add_total_rows = st.checkbox(
                "Adicionar Total (Linhas)",
                value=st.session_state.get("add_total_rows", False),
                key="input_chk_rows",
            )
        with c2:
            sel_cols = st.multiselect(
                "Colunas",
                options=valid_dims,
                default=default_cols,
                format_func=lambda x: dim_map.get(x, x),
                key="input_cols",
                placeholder="Escolha uma opção",
            )
            add_total_cols = st.checkbox(
                "Adicionar Total (Colunas)",
                value=st.session_state.get("add_total_cols", False),
                key="input_chk_cols",
            )
        with c3:
            sel_metrics = st.multiselect(
                "Métricas (Valores)",
                options=valid_metrics,
                default=default_metrics,
                format_func=lambda x: metrics_map.get(x, x),
                key="input_metrics",
                placeholder="Escolha uma opção",
            )
            st.caption("Selecione os valores a calcular")

        st.markdown("<br>", unsafe_allow_html=True)
        _, center_col, _ = st.columns([1, 1, 1])
        with center_col:
            label_btn_struct = (
                "Atualizar Estrutura" if st.session_state.custom_step >= 2 else "Continuar para Filtros"
            )
            submitted_struct = st.form_submit_button(
                label_btn_struct,
                type="primary",
                use_container_width=True,
            )

    if submitted_struct:
        intersection = set(sel_rows) & set(sel_cols)
        if not sel_rows and not sel_cols:
            st.error("Selecione pelo menos uma Linha ou Coluna.")
        elif not sel_metrics:
            st.error("Selecione pelo menos uma Métrica.")
        elif intersection:
            duplicated = dim_map.get(list(intersection)[0], list(intersection)[0])
            st.error(f"Erro: o campo '{duplicated}' não pode estar em Linhas e Colunas ao mesmo tempo.")
        else:
            st.session_state.cust_rows = sel_rows
            st.session_state.cust_cols = sel_cols
            st.session_state.cust_metrics = sel_metrics
            st.session_state.add_total_rows = add_total_rows
            st.session_state.add_total_cols = add_total_cols

            current_struct = (tuple(sel_rows), tuple(sel_cols), tuple(sel_metrics), add_total_rows, add_total_cols)
            if st.session_state.get("last_struct") != current_struct:
                _clear_custom_filters()
                _reset_custom_outputs()
                st.session_state.pop("custom_period_signature", None)
                st.session_state["last_struct"] = current_struct

            st.session_state.custom_step = 2
            st.rerun()

    if st.session_state.custom_step >= 2:
        st.markdown("---")

        s_rows = st.session_state.get("cust_rows", [])
        s_cols = st.session_state.get("cust_cols", [])
        s_metrics = st.session_state.get("cust_metrics", [])

        st.markdown("##### Período")
        if "Data_Dt" not in df.columns or df["Data_Dt"].dropna().empty:
            st.error("A base não possui datas válidas para o filtro de período.")
            st.stop()

        data_series = df["Data_Dt"].dropna()
        data_min_base = data_series.min().date()
        data_max_base = data_series.max().date()

        min_date = data_min_base
        try:
            max_date_cfg = datetime.strptime(data_atualizacao, "%d/%m/%Y").date()
            max_date = min(max_date_cfg, data_max_base)
        except Exception:
            max_date = data_max_base

        default_ini = st.session_state.get("custom_dt_ini", max(min_date, max_date - timedelta(days=30)))
        default_fim = st.session_state.get("custom_dt_fim", max_date)

        d1, d2, d3 = st.columns([1, 1, 1])
        with d1:
            dt_ini = st.date_input(
                "Início",
                value=default_ini,
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY",
                key="custom_dt_ini",
            )
        with d2:
            dt_fim = st.date_input(
                "Fim",
                value=default_fim,
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY",
                key="custom_dt_fim",
            )
        with d3:
            clear_filters_clicked = st.button(
                "Limpar Filtros",
                use_container_width=True,
                key="btn_custom_clear_filters",
            )

        if clear_filters_clicked:
            _clear_custom_filters()
            _reset_custom_outputs()
            st.rerun()

        if dt_ini > dt_fim:
            st.warning("A data inicial não pode ser maior que a final.")
            st.stop()

        period_signature = f"{dt_ini.isoformat()}__{dt_fim.isoformat()}"
        if st.session_state.get("custom_period_signature") != period_signature:
            _clear_custom_filters()
            _reset_custom_outputs()
            st.session_state["custom_period_signature"] = period_signature

        ts_ini = pd.Timestamp(dt_ini)
        ts_fim = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        mask_period = df["Data_Dt"].between(ts_ini, ts_fim, inclusive="both")

        priority_filters = ["Praca", "Emissora", "Anunciante", "Anuncio"]
        fields_ordered = []
        seen = set()
        for col in priority_filters + s_rows + s_cols + ["Tipo", "Produto", "Programa", "DayPart", "Ano", "Mes", "Dia"]:
            if col in df.columns and col not in seen and col not in ["Data", "Data_Dt"]:
                fields_ordered.append(col)
                seen.add(col)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Filtros")
        st.caption(FILTER_HELP_TEXT)

        if not bool(mask_period.any()):
            _reset_custom_outputs()
            st.info("Não há dados no período selecionado. Ajuste as datas para carregar as opções de filtro.")
            st.stop()

        records_in_period = int(mask_period.sum())
        st.caption(f"Registros disponíveis no período: {records_in_period:,}".replace(",", "."))

        available_mappings = {}
        mask_context = mask_period.copy()

        if fields_ordered:
            with st.container(border=True):
                cols_ui = st.columns(3)
                for idx, col_name in enumerate(fields_ordered):
                    display_name = dim_map.get(col_name, col_name)
                    state_key = f"custom_filter_{col_name}"
                    current_selected = _coerce_selection_list(st.session_state.get(state_key, []))

                    options_map = _build_display_mapping(df.loc[mask_context, col_name])
                    options_list = list(options_map.keys())
                    valid_selected = [x for x in current_selected if x in options_list]
                    if current_selected != valid_selected:
                        st.session_state[state_key] = valid_selected

                    with cols_ui[idx % 3]:
                        selected_display = st.multiselect(
                            display_name,
                            options=options_list,
                            default=st.session_state.get(state_key, []),
                            key=state_key,
                            placeholder="Todos",
                        )

                    available_mappings[col_name] = options_map
                    selected_actual = [options_map[val] for val in selected_display if val in options_map]
                    if selected_actual:
                        mask_context &= df[col_name].isin(selected_actual)

        st.markdown("<br>", unsafe_allow_html=True)
        _, center_btn, _ = st.columns([1, 1, 1])
        with center_btn:
            submitted_report = st.button(
                "Gerar Relatório",
                type="primary",
                use_container_width=True,
                key="custom_generate_report",
            )

        if submitted_report:
            with st.spinner("Processando dados..."):
                time.sleep(0.1)
                real_filters_selected = {}
                mask_filtered = mask_period.copy()

                for col in fields_ordered:
                    state_key = f"custom_filter_{col}"
                    selected_display = _coerce_selection_list(st.session_state.get(state_key, []))
                    options_map = available_mappings.get(col, {})
                    selected_actual = [options_map[val] for val in selected_display if val in options_map]
                    if selected_actual:
                        mask_filtered &= df[col].isin(selected_actual)
                        real_filters_selected[dim_map.get(col, col)] = selected_display

                if not bool(mask_filtered.any()):
                    _reset_custom_outputs()
                    st.warning("Nenhum dado encontrado para o período/filtros.")
                else:
                    try:
                        needed_columns = list(dict.fromkeys(s_rows + s_cols + s_metrics))
                        df_filtered = df.loc[mask_filtered, needed_columns]

                        est_rows = df_filtered[s_rows].drop_duplicates().shape[0] if s_rows else 1
                        est_cols = df_filtered[s_cols].drop_duplicates().shape[0] if s_cols else 1
                        total_cells = est_rows * est_cols * max(len(s_metrics), 1)

                        if total_cells > MAX_ESTIMATED_CELLS:
                            _reset_custom_outputs()
                            st.error(
                                f"Relatório muito grande (~{total_cells:,.0f} células). "
                                "Aplique mais filtros antes de gerar."
                            )
                        else:
                            use_margins = bool(
                                st.session_state.get("add_total_rows", False)
                                or st.session_state.get("add_total_cols", False)
                            )

                            pivot = pd.pivot_table(
                                df_filtered,
                                index=s_rows or None,
                                columns=s_cols or None,
                                values=s_metrics,
                                aggfunc="sum",
                                fill_value=0,
                                margins=use_margins,
                                margins_name="TOTAL",
                                observed=True,
                                sort=False,
                            )

                            if use_margins:
                                if not st.session_state.get("add_total_rows", False) and "TOTAL" in pivot.index:
                                    pivot = pivot.drop("TOTAL", axis=0)
                                if not st.session_state.get("add_total_cols", False):
                                    if isinstance(pivot.columns, pd.MultiIndex):
                                        for level in range(pivot.columns.nlevels):
                                            try:
                                                pivot = pivot.drop("TOTAL", axis=1, level=level)
                                            except Exception:
                                                continue
                                    elif "TOTAL" in pivot.columns:
                                        pivot = pivot.drop("TOTAL", axis=1)

                            if isinstance(pivot.index, pd.MultiIndex):
                                new_levels = [lvl.astype(str) for lvl in pivot.index.levels]
                                pivot.index = pivot.index.set_levels(new_levels, level=range(len(new_levels)))
                            else:
                                pivot.index = pivot.index.astype(str)

                            pivot.index.names = [dim_map.get(name, name) for name in pivot.index.names]
                            if pivot.columns.names:
                                pivot.columns.names = [dim_map.get(name, name) for name in pivot.columns.names]

                            if isinstance(pivot.columns, pd.MultiIndex):
                                new_levels = []
                                for level_vals in pivot.columns.levels:
                                    new_vals = [str(metrics_map.get(val, dim_map.get(val, val))) for val in level_vals]
                                    new_levels.append(new_vals)
                                pivot.columns = pivot.columns.set_levels(new_levels, level=range(len(new_levels)))
                            else:
                                pivot.columns = [str(metrics_map.get(val, val)) for val in pivot.columns]

                            st.session_state.pivot_is_preview = (
                                pivot.size > MAX_PREVIEW_SIZE or pivot.shape[1] > MAX_PREVIEW_COLS
                            )
                            st.session_state.custom_pivot_cache = pivot
                            st.session_state.custom_filters_info = {
                                "Período": f"{dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}",
                                "Linhas": ", ".join([dim_map.get(x, x) for x in s_rows]) or "Nenhuma",
                                "Colunas": ", ".join([dim_map.get(x, x) for x in s_cols]) or "Nenhuma",
                                "Filtros Aplicados": _format_selected_filters(real_filters_selected),
                            }

                            del df_filtered
                            gc.collect()
                            st.rerun()

                    except MemoryError:
                        _reset_custom_outputs()
                        st.error(
                            "O relatório excedeu a memória disponível. Aplique mais filtros ou reduza a estrutura."
                        )
                    except Exception as exc:
                        _reset_custom_outputs()
                        st.error(f"Erro no processamento: {exc}")

    if "custom_pivot_cache" in st.session_state:
        full_pivot = st.session_state.get("custom_pivot_cache")
        is_preview = st.session_state.get("pivot_is_preview", False)

        if full_pivot is None or full_pivot.empty:
            _reset_custom_outputs()
            st.warning("O relatório gerado ficou vazio após o processamento.")
            st.stop()

        st.markdown("<hr>", unsafe_allow_html=True)

        if is_preview:
            pivot_display = full_pivot.iloc[:MAX_PREVIEW_ROWS, :MAX_PREVIEW_COLS]
            warning_msg = (
                f"<strong>Prévia de Exibição</strong><br>"
                f"O relatório completo possui <strong>{len(full_pivot):,.0f} linhas</strong> e "
                f"<strong>{full_pivot.shape[1]} colunas</strong>."
            )
            reasons = []
            if full_pivot.shape[0] > MAX_PREVIEW_ROWS:
                reasons.append(f"apenas as primeiras {MAX_PREVIEW_ROWS} linhas")
            if full_pivot.shape[1] > MAX_PREVIEW_COLS:
                reasons.append(f"apenas as primeiras {MAX_PREVIEW_COLS} colunas")
            if reasons:
                warning_msg += f"<br>Exibindo {' e '.join(reasons)}. Baixe o Excel para ver tudo."

            st.markdown(
                f'''
                <div class="preview-warning">
                    <span>⚠️</span>
                    <div>{warning_msg}</div>
                </div>
                ''',
                unsafe_allow_html=True,
            )
            st.dataframe(pivot_display, height=500, width="stretch")
        else:
            st.success("Relatório gerado com sucesso!")
            st.dataframe(full_pivot, height=600, width="stretch")

        st.markdown("<br>", unsafe_allow_html=True)
        _, export_col, _ = st.columns([1, 1, 1])
        with export_col:
            if st.button("Exportar Excel", type="secondary", use_container_width=True):
                st.session_state.show_custom_export = True
                st.rerun()

    if st.session_state.get("show_custom_export", False):

        @st.dialog("Exportação Personalizada")
        def export_dialog_custom():
            st.write("Preparando arquivo Excel...")
            df_to_export = st.session_state.get("custom_pivot_cache")
            filters_info = st.session_state.get("custom_filters_info", {})

            if df_to_export is None or df_to_export.empty:
                st.error("Não há relatório válido para exportar.")
                if st.button("Fechar", key="btn_close_export_empty"):
                    st.session_state.show_custom_export = False
                    st.rerun()
                return

            if df_to_export.shape[1] > MAX_EXCEL_COLUMNS:
                st.error(
                    f"Não foi possível exportar porque o relatório possui {df_to_export.shape[1]} colunas "
                    f"(o limite do Excel é {MAX_EXCEL_COLUMNS}). Ajuste os filtros para gerar um relatório menor."
                )
                if st.button("Fechar", key="btn_close_export_error"):
                    st.session_state.show_custom_export = False
                    st.rerun()
                return

            if df_to_export.size > MAX_EXCEL_CELLS:
                st.info("O arquivo é grande, isso pode levar alguns segundos...")

            try:
                with st.spinner("Gerando arquivo..."):
                    export_df = df_to_export.copy()
                    if (
                        not isinstance(export_df.index, pd.MultiIndex)
                        and isinstance(export_df.index.dtype, pd.CategoricalDtype)
                    ):
                        export_df.index = export_df.index.astype(str)
                    excel_buffer = generate_custom_report_excel(export_df, filters_info)
            except MemoryError:
                st.error("A exportação excedeu a memória disponível. Reduza o tamanho do relatório.")
                if st.button("Fechar", key="btn_close_export_memory"):
                    st.session_state.show_custom_export = False
                    st.rerun()
                return
            except Exception as exc:
                st.error(f"Falha ao gerar o Excel: {exc}")
                if st.button("Fechar", key="btn_close_export_exception"):
                    st.session_state.show_custom_export = False
                    st.rerun()
                return

            st.success("Pronto!")
            st.markdown(
                """
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
                """,
                unsafe_allow_html=True,
            )

            st.download_button(
                label="Baixar Arquivo",
                data=excel_buffer,
                file_name=f"Relatorio_Personalizado_{datetime.now().strftime('%d%m_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
                on_click=lambda: st.session_state.update(show_custom_export=False),
            )

        export_dialog_custom()
