# streamlit_app.py

import os
import streamlit as st
from PIL import Image
import pandas as pd
from datetime import datetime, timedelta
import streamlit_cookies_manager 
import json 
import locale
import warnings

# ==================== FILTRO DE AVISOS E LOCALE ====================
warnings.filterwarnings("ignore", message=".*st.cache is deprecated.*")

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')
    except locale.Error:
        pass 

# Importações dos módulos Crowley
from pages import relatorio_crowley 

# ==================== CONFIGURAÇÕES GERAIS ====================
icon_path = os.path.join("assets", "icone.png") 
favicon = None
if os.path.exists(icon_path):
    try: favicon = Image.open(icon_path)
    except: pass

st.set_page_config(
    page_title="Relatório Crowley - Novabrasil",
    page_icon=favicon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== AUTENTICAÇÃO E COOKIES ====================
cookies = streamlit_cookies_manager.CookieManager()
if not cookies.ready():
    st.spinner("Carregando...")
    st.stop()

if not st.session_state.get("authenticated", False):
    auth_cookie = cookies.get("auth_token_crowley")
    if auth_cookie == "user_is_logged_in_crowley":
        st.session_state.authenticated = True
    else:
        st.session_state.authenticated = False

# Tela de Login
if not st.session_state.authenticated:
    hide_elements_style = """
        <style>
            [data-testid="stSidebar"] {display: none;}
            [data-testid="stHeader"] {display: none;}
            [data-testid="stToolbar"] {display: none;}
            .main {padding-top: 2rem;}
        </style>
    """
    st.markdown(hide_elements_style, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        logo_path = os.path.join("assets", "NOVABRASIL_TH+_LOGOS_VETORIAIS-07.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=200)
        
        st.markdown("#### 🔒 Acesso Crowley")
        
        with st.form(key="login_form"):
            password = st.text_input("Insira a senha:", type="password")
            submitted = st.form_submit_button("Entrar")

        if submitted:
            try:
                senha_correta = st.secrets["senha_app"]
            except Exception:
                st.error("Erro: Senha não configurada no secrets.")
                st.stop()

            if password.strip() == senha_correta:
                st.session_state.authenticated = True
                cookies["auth_token_crowley"] = "user_is_logged_in_crowley"
                cookies.save() 
                st.rerun() 
            else:
                st.error("Senha incorreta.")
                st.session_state.authenticated = False
    st.stop()

# ==================== ESTILOS E CSS ====================
def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css("utils/style.css")

# Esconde navegação padrão do Streamlit
st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    </style>
""", unsafe_allow_html=True)

# ==================== BARRA LATERAL (SIDEBAR) ====================

# 1. LOGO DA NOVABRASIL
logo_path = os.path.join("assets", "NOVABRASIL_TH+_LOGOS_VETORIAIS-07.png")
if os.path.exists(logo_path):
    logo = Image.open(logo_path)
    st.sidebar.image(logo, width=160) 

# 2. MENU DE NAVEGAÇÃO
query_params = st.query_params
current_view = query_params.get("view", ["menu"])[0]

st.sidebar.markdown('<p style="font-size:0.85rem; font-weight:600; margin-bottom: 0.5rem; margin-left: 10px;">Selecione a página:</p>', unsafe_allow_html=True)

# --- ATUALIZAÇÃO DOS NOMES NO MENU ---
menu_options = [
    {"label": "Início", "view": "menu"},
    {"label": "Opportunity Radar", "view": "opportunity"},
    {"label": "Campaign Flow", "view": "campaign"},
    {"label": "Presence Map", "view": "presence"},
    {"label": "Performance Index", "view": "performance"},
]

html_menu = []
for option in menu_options:
    label = option["label"]
    view_key = option["view"]
    is_active = "active" if view_key == current_view else ""
    html_menu.append(
        f'<a class="sidebar-nav-btn {is_active}" href="?view={view_key}" target="_self">{label}</a>'
    )

# Link Voltar para o app principal
link_faturamento = "https://novabrasil-datadriven.streamlit.app" 
html_menu.append(
    f'<a class="sidebar-nav-btn" href="{link_faturamento}" target="_blank">Voltar p/ Faturamento</a>'
)

st.sidebar.markdown(f'<div class="sidebar-nav-container">{"".join(html_menu)}</div>', unsafe_allow_html=True)
st.sidebar.divider()

# ==================== POP-UP DE BOAS-VINDAS ====================

@st.dialog("Banner de Boas-vindas", width="medium")
def modal_boas_vindas():
    st.markdown("""
        <div class="popup-title-styled">Intelligence Crowley</div>
        <div class="popup-subtitle">Novos Módulos Data Driven</div>
    """, unsafe_allow_html=True)

    with st.container(height=320, border=True):
        st.markdown("""
        ### O que há de novo?
        * **Opportunity Radar:** Quem está entrando? Onde estão as oportunidades? (Antigo Busca de Novos).
        * **Campaign Flow:** Como o mercado se movimenta no tempo? (Antigo ECA).
        * **Presence Map:** Onde cada marca ocupa o território? (Antigo Flight).
        * **Performance Index:** Quem é mais forte e consistente? (Antigo Ranking).
        ---
        """)
        st.markdown("**Dúvidas:** (31) 9.9274-4574 - Silvia Freitas")

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True) 
    
    if st.button("Entendido", type="secondary"): 
        cookies["last_popup_view_crowley"] = datetime.now().isoformat()
        cookies.save()
        st.rerun()

# Lógica do Pop-up
if st.session_state.authenticated:
    show_welcome = False
    last_view_str = cookies.get("last_popup_view_crowley")
    
    if not last_view_str:
        show_welcome = True
    else:
        try:
            last_view = datetime.fromisoformat(last_view_str)
            if datetime.now() - last_view > timedelta(hours=24):
                show_welcome = True
        except ValueError:
            show_welcome = True

    if show_welcome:
        modal_boas_vindas()

# ==================== RENDERIZAÇÃO DA PÁGINA ====================
relatorio_crowley.render(cookies)

# ==================== RODAPÉ (FOOTER) ====================
footer_html = """
<div class="footer-container">
    <p class="footer-text">Powered by Python | Interface Streamlit | Data Driven Novabrasil</p>
    <p class="footer-text">Conteúdo Confidencial. A distribuição a terceiros não autorizados é estritamente proibida.</p>
</div>
"""
st.markdown(footer_html, unsafe_allow_html=True)