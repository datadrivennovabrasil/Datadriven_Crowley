# pages/relatorio_crowley.py
import streamlit as st
import pandas as pd
from utils.loaders import load_crowley_base

# ==================== IMPORTAÇÃO DOS MÓDULOS (NOVOS NOMES) ====================
from pages import opportunity_radar, campaign_flow, presence_map, performance_index, relatorio_personalizado

def render(cookies):
    
    # --- 1. Carrega dados e data (Cache) ---
    df_crowley, data_atualizacao = load_crowley_base()

    # --- 2. Gerenciamento de Navegação ---
    query_params = st.query_params
    current_view = query_params.get("view", "menu")
    if isinstance(current_view, list):
        current_view = current_view[0]

    # ==================== CSS CROWLEY ====================
    st.markdown("""
        <style>
        .nb-container { display: flex; justify-content: center; align-items: center; flex-direction: column; width: 100%; margin-top: 2rem; }
        
        /* Ajuste do Grid para acomodar descrições e novos cards */
        .nb-grid { 
            display: grid; 
            grid-template-columns: repeat(3, 280px); /* 3 colunas para acomodar os cards */
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
            height: 150px; 
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
        }
        
        .nb-card span {
            font-size: 0.8rem;
            font-weight: 400;
            margin-top: 8px;
            color: #e0f7fa;
            line-height: 1.2;
        }

        .nb-card:hover { background-color: #00a8e0; transform: scale(1.05); box-shadow: 0 6px 12px rgba(0, 0, 0, 0.25); text-decoration: none !important; }
        .nb-card:active { transform: scale(0.97); background-color: #004b8d; }
        
        .footer-date { margin-top: 50px; text-align: center; font-size: 0.85rem; color: #666; border-top: 1px solid #eee; padding-top: 10px; width: 100%; }
        
        /* Responsividade para mobile */
        @media only screen and (max-width: 900px) {
            .nb-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        @media only screen and (max-width: 600px) {
            .nb-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    # ==================== ROTEAMENTO ====================
    
    # --- 1. MENU PRINCIPAL ---
    if current_view == "menu":
        st.markdown("<h1 style='text-align: center; color: #003366; margin-bottom: 0.5rem;'>Crowley Intelligence</h1>", unsafe_allow_html=True)
        st.markdown("<div style='text-align:center; color: #555; margin-bottom: 1rem;'>Selecione o módulo de análise desejado:</div>", unsafe_allow_html=True)

        st.markdown("""
        <div class="nb-container">
          <div class="nb-grid">
            <a href="?view=opportunity" target="_self" class="nb-card">
                Opportunity Radar
                <span>Quem está entrando?<br>Onde estão as oportunidades?</span>
            </a>
            <a href="?view=campaign" target="_self" class="nb-card">
                Campaign Flow
                <span>Como o mercado se<br>movimenta no tempo?</span>
            </a>
            <a href="?view=presence" target="_self" class="nb-card">
                Presence Map
                <span>Onde cada marca ocupa<br>(ou não) o território?</span>
            </a>
            <a href="?view=performance" target="_self" class="nb-card">
                Performance Index
                <span>Quem é mais forte<br>e consistente?</span>
            </a>
            <a href="?view=custom" target="_self" class="nb-card">
                Relatório Personalizado
                <span>Crie sua própria visão<br>dinâmica dos dados</span>
            </a>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class="footer-date">
                <b>Última atualização da base de dados:</b> {data_atualizacao}
            </div>
        """, unsafe_allow_html=True)

    # --- 2. ROTEAMENTO PARA OS MÓDULOS ---
    elif current_view == "opportunity":
        opportunity_radar.render(df_crowley, cookies, data_atualizacao)

    elif current_view == "campaign":
        campaign_flow.render(df_crowley, cookies, data_atualizacao)
    
    elif current_view == "performance":
        performance_index.render(df_crowley, cookies, data_atualizacao)
    
    elif current_view == "presence":
        presence_map.render(df_crowley, cookies, data_atualizacao)
        
    elif current_view == "custom":
        relatorio_personalizado.render(df_crowley, cookies, data_atualizacao)
    
    else:
        st.error("Página não encontrada.")
        if st.button("Ir para o Menu"):
            st.query_params["view"] = "menu"
            st.rerun()