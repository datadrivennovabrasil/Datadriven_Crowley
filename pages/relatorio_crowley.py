# pages/relatorio_crowley.py
import streamlit as st
import pandas as pd
from utils.loaders import load_crowley_base

# ==================== AJUSTE DE IMPORTAÇÃO ====================
# Antes: from crowley import ...
# Agora: importamos diretamente de 'pages' pois os arquivos estão na mesma pasta
from pages import busca_novos, eca, flight, ranking_analitico

# RECEBE cookies COMO ARGUMENTO
def render(cookies):
    
    # --- 1. Carrega dados e data (Cache) ---
    df_crowley, data_atualizacao = load_crowley_base()

    # --- 2. Gerenciamento de Navegação ---
    query_params = st.query_params
    current_view = query_params.get("view", "menu")
    if isinstance(current_view, list):
        current_view = current_view[0]

    # ==================== CSS GLOBAL DO CROWLEY ====================
    st.markdown("""
        <style>
        /* Estilos do Menu Principal */
        .nb-container { display: flex; justify-content: center; align-items: center; flex-direction: column; width: 100%; margin-top: 2rem; }
        .nb-grid { display: grid; grid-template-columns: repeat(2, 240px); grid-template-rows: repeat(2, 130px); gap: 1.5rem; justify-content: center; }
        .nb-card { background-color: #007dc3; border: 2px solid white; border-radius: 15px; color: white !important; text-decoration: none !important; font-size: 1rem; font-weight: 600; height: 120px; width: 240px; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15); transition: all 0.25s ease-in-out; text-align: center; }
        .nb-card:hover { background-color: #00a8e0; transform: scale(1.05); box-shadow: 0 6px 12px rgba(0, 0, 0, 0.25); text-decoration: none !important; }
        .nb-card:active { transform: scale(0.97); background-color: #004b8d; }
        
        /* AJUSTE: Centralização do Rodapé */
        .footer-date { 
            margin-top: 50px; 
            text-align: center; /* Centralizado */
            font-size: 0.85rem; 
            color: #666; 
            border-top: 1px solid #eee; 
            padding-top: 10px; 
            width: 100%; 
        }
        
        /* Estilos Personalizados da Página */
        .filter-container { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e9ecef; margin-bottom: 20px; }
        
        /* Título Centralizado */
        .page-title-centered {
            text-align: center;
            font-size: 2.5rem;
            font-weight: 700;
            color: #003366;
            margin-bottom: 1.5rem;
            margin-top: 0.5rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # ==================== ROTEAMENTO ====================
    
    # --- 1. MENU PRINCIPAL ---
    if current_view == "menu":
        st.title("Relatório Crowley")
        st.markdown("Análise de concorrência e monitoramento de spots.")

        st.markdown("""
        <div class="nb-container">
          <div class="nb-grid">
            <a href="?view=eca" target="_self" class="nb-card">Relatório ECA</a>
            <a href="?view=novos" target="_self" class="nb-card">Busca de Novos</a>
            <a href="?view=ranking" target="_self" class="nb-card">Ranking Analítico</a>
            <a href="?view=flight" target="_self" class="nb-card">Relatório Flight</a>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class="footer-date">
                <b>Última atualização da base de dados:</b> {data_atualizacao}
            </div>
        """, unsafe_allow_html=True)

    # --- 2. MÓDULOS ESPECÍFICOS ---
    elif current_view == "novos":
        busca_novos.render(df_crowley, cookies, data_atualizacao)

    elif current_view == "eca":
        eca.render(df_crowley, cookies, data_atualizacao)
    
    elif current_view == "ranking":
        ranking_analitico.render(df_crowley, cookies, data_atualizacao)
    
    elif current_view == "flight":
        flight.render(df_crowley, cookies, data_atualizacao)
    
    else:
        st.error("Página não encontrada.")
        if st.button("Ir para o Menu"):
            st.query_params["view"] = "menu"
            st.rerun()