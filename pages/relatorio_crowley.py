# pages/relatorio_crowley.py
import importlib
import traceback
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from utils.loaders import load_crowley_base


VIEW_CONFIG = {
    "menu": {
        "title": "Crowley Intelligence",
        "subtitle": "Selecione o módulo de análise desejado:",
    },
    "opportunity": {
        "label": "Opportunity Radar",
        "desc": "Quem está entrando?<br>Onde estão as oportunidades?",
        "module": "opportunity_radar",
    },
    "campaign": {
        "label": "Campaign Flow",
        "desc": "Como o mercado se<br>movimenta no tempo?",
        "module": "campaign_flow",
    },
    "presence": {
        "label": "Presence Map",
        "desc": "Onde cada marca ocupa<br>(ou não) o território?",
        "module": "presence_map",
    },
    "performance": {
        "label": "Performance Index",
        "desc": "Quem é mais forte<br>e consistente?",
        "module": "performance_index",
    },
    "custom": {
        "label": "Relatório Personalizado",
        "desc": "Crie sua própria visão<br>dinâmica dos dados",
        "module": "relatorio_personalizado",
    },
}


def _apply_page_css() -> None:
    st.markdown(
        """
        <style>
        .nb-container {
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            width: 100%;
            margin-top: 2rem;
        }

        .nb-grid {
            display: grid;
            grid-template-columns: repeat(3, 280px);
            grid-template-rows: auto;
            gap: 1.5rem;
            justify-content: center;
        }

        .nb-card {
            background-color: #007dc3;
            border: 2px solid white;
            border-radius: 15px;
            color: white !important;
            text-decoration: none !important;
            font-size: 1.1rem;
            font-weight: 700;
            min-height: 150px;
            width: 280px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
            transition: all 0.25s ease-in-out;
            text-align: center;
            padding: 10px;
            box-sizing: border-box;
        }

        .nb-card span {
            font-size: 0.8rem;
            font-weight: 400;
            margin-top: 8px;
            color: #e0f7fa;
            line-height: 1.2;
        }

        .nb-card:hover {
            background-color: #00a8e0;
            transform: scale(1.03);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.25);
            text-decoration: none !important;
        }

        .nb-card:active {
            transform: scale(0.98);
            background-color: #004b8d;
        }

        .footer-date {
            margin-top: 50px;
            text-align: center;
            font-size: 0.85rem;
            color: #666;
            border-top: 1px solid #eee;
            padding-top: 10px;
            width: 100%;
        }

        @media only screen and (max-width: 900px) {
            .nb-grid { grid-template-columns: repeat(2, minmax(240px, 1fr)); }
            .nb-card { width: 100%; }
        }

        @media only screen and (max-width: 600px) {
            .nb-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _get_current_view() -> str:
    raw_view = st.query_params.get("view", "menu")

    if isinstance(raw_view, list):
        view = raw_view[0] if raw_view else "menu"
    else:
        view = raw_view

    if not isinstance(view, str) or not view.strip():
        return "menu"

    view = view.strip().lower()
    return view if view in VIEW_CONFIG else "menu"


def _go_to_view(view: str) -> None:
    st.query_params["view"] = view
    st.rerun()


def _safe_format_update_date(value) -> str:
    if value is None:
        return "Não disponível"

    try:
        if isinstance(value, (pd.Timestamp,)):
            return value.strftime("%d/%m/%Y")
        return str(value)
    except Exception:
        return "Não disponível"


def _safe_load_base() -> Tuple[Optional[pd.DataFrame], str]:
    try:
        with st.spinner("Carregando base Crowley..."):
            result = load_crowley_base()
    except MemoryError:
        st.error("A aplicação ficou sem memória ao carregar a base. Tente novamente ou reduza o volume de dados carregado.")
        return None, "Não disponível"
    except Exception as exc:
        st.error(f"Erro ao carregar a base Crowley: {exc}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())
        return None, "Não disponível"

    if not isinstance(result, tuple) or len(result) != 2:
        st.error("O carregamento da base retornou um formato inesperado.")
        return None, "Não disponível"

    df_crowley, data_atualizacao = result

    if df_crowley is None:
        st.warning("A base Crowley não retornou dados.")
        return None, _safe_format_update_date(data_atualizacao)

    if not isinstance(df_crowley, pd.DataFrame):
        st.error("A base Crowley retornou um objeto inválido.")
        return None, _safe_format_update_date(data_atualizacao)

    if df_crowley.empty:
        st.warning("A base Crowley foi carregada, mas está vazia.")
        return df_crowley, _safe_format_update_date(data_atualizacao)

    return df_crowley, _safe_format_update_date(data_atualizacao)


def _render_menu(data_atualizacao: str) -> None:
    st.markdown(
        "<h1 style='text-align: center; color: #003366; margin-bottom: 0.5rem;'>Crowley Intelligence</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='text-align:center; color: #555; margin-bottom: 1rem;'>Selecione o módulo de análise desejado:</div>",
        unsafe_allow_html=True,
    )

    cards_html = []
    for view_key in ["opportunity", "campaign", "presence", "performance", "custom"]:
        cfg = VIEW_CONFIG[view_key]
        cards_html.append(
            f'''
            <a href="?view={view_key}" target="_self" class="nb-card">
                {cfg["label"]}
                <span>{cfg["desc"]}</span>
            </a>
            '''
        )

    st.markdown(
        f"""
        <div class="nb-container">
          <div class="nb-grid">
            {''.join(cards_html)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="footer-date">
            <b>Última atualização da base de dados:</b> {data_atualizacao}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _import_page_module(module_name: str):
    try:
        return importlib.import_module(f"pages.{module_name}")
    except Exception as exc:
        st.error(f"Não foi possível carregar o módulo '{module_name}': {exc}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())
        return None


def _render_module_page(view: str, df_crowley: pd.DataFrame, cookies, data_atualizacao: str) -> None:
    cfg = VIEW_CONFIG.get(view)
    if not cfg or "module" not in cfg:
        st.error("Página não encontrada.")
        if st.button("Ir para o Menu"):
            _go_to_view("menu")
        return

    module = _import_page_module(cfg["module"])
    if module is None:
        if st.button("Voltar ao Menu"):
            _go_to_view("menu")
        return

    if not hasattr(module, "render"):
        st.error(f"O módulo '{cfg['module']}' não possui a função render().")
        if st.button("Voltar ao Menu"):
            _go_to_view("menu")
        return

    try:
        module.render(df_crowley, cookies, data_atualizacao)
    except MemoryError:
        st.error(
            f"A página '{cfg['label']}' excedeu o limite de memória. Tente reduzir os filtros ou voltar ao menu."
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Recarregar página"):
                st.rerun()
        with col2:
            if st.button("Voltar ao Menu"):
                _go_to_view("menu")
    except Exception as exc:
        st.error(f"Ocorreu um erro ao abrir '{cfg['label']}': {exc}")
        with st.expander("Detalhes técnicos"):
            st.code(traceback.format_exc())
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Tentar novamente"):
                st.rerun()
        with col2:
            if st.button("Voltar ao Menu"):
                _go_to_view("menu")


def render(cookies):
    _apply_page_css()

    current_view = _get_current_view()
    df_crowley, data_atualizacao = _safe_load_base()

    if current_view == "menu":
        _render_menu(data_atualizacao)
        return

    if df_crowley is None:
        st.warning("A base não pôde ser carregada. Retorne ao menu ou tente novamente.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Tentar novamente"):
                st.rerun()
        with col2:
            if st.button("Ir para o Menu"):
                _go_to_view("menu")
        return

    if df_crowley.empty:
        st.warning("A base está vazia no momento. Não há dados para exibir nesta página.")
        if st.button("Ir para o Menu"):
            _go_to_view("menu")
        return

    _render_module_page(current_view, df_crowley, cookies, data_atualizacao)
