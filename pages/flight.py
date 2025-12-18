# crowley/flight.py

# ==============================================================================
# 1. IMPORTAÇÕES E CONFIGURAÇÕES INICIAIS
# ==============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import io
import math
import json
from datetime import datetime
import calendar
import xlsxwriter

# Configuração global do pandas para styler
pd.set_option("styler.render.max_elements", 5_000_000)

# ==============================================================================
# 2. CONFIGURAÇÃO VISUAL (CSS)
# ==============================================================================
def apply_custom_css(hide_tipo_col=False):
    """
    Aplica estilos CSS.
    Col 1 (Anunciante): Alinhada à esquerda, negrito.
    Col 2 (Tipo de Veiculação): Centralizada (se visível).
    """
    idx_anunciante = 1 if hide_tipo_col else 2 
    
    css = f"""
        <style>
        /* Tabela Compacta: Geral */
        [data-testid="stDataFrame"] th, [data-testid="stDataFrame"] td {{
            text-align: center !important;
            vertical-align: middle !important;
            font-size: 0.75rem !important;
            padding: 4px !important;
            white-space: nowrap !important;
        }}
        
        /* 1ª COLUNA VISUAL: ANUNCIANTE (Alinhada à esquerda) */
        [data-testid="stDataFrame"] td:nth-child({idx_anunciante}) {{
            text-align: left !important;
            font-weight: bold;
            min-width: 200px !important;
            max-width: 300px !important;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        /* 2ª COLUNA VISUAL: TIPO DE VEICULAÇÃO (Apenas se visível) */
        {"" if hide_tipo_col else """
        [data-testid="stDataFrame"] td:nth-child(2) {
            text-align: center !important;
            font-weight: normal;
            color: #444;
            min-width: 140px !important;
        }
        """}
        
        .page-title-centered {{
            text-align: center;
            font-size: 2em;
            font-weight: bold;
            color: #003366;
            margin-bottom: 20px;
        }}
        </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ==============================================================================
# 3. FUNÇÃO PRINCIPAL `render`
# ==============================================================================
def render(df_crowley, cookies, data_atualizacao):
    
    mes_map = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
               7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}
    
    # --- Header e Navegação ---
    if st.button("Voltar", key="btn_voltar_flight"):
        st.query_params["view"] = "menu"
        keys_to_clear = ["flight_search_trigger", "flight_page_idx", "flight_praca_key", "flight_tipo_key"]
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown('<div class="page-title-centered">Relatório Flight (Mapa de Inserções)</div>', unsafe_allow_html=True)

    # --- Validação da Base ---
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
    
    df_crowley_copy["Ano"] = df_crowley_copy["Data_Dt"].dt.year
    df_crowley_copy["Mes"] = df_crowley_copy["Data_Dt"].dt.month
    df_crowley_copy["Dia"] = df_crowley_copy["Data_Dt"].dt.day

    # --- Cookies ---
    saved_filters = {}
    if cookie_val := cookies.get("crowley_filters_flight"):
        try: saved_filters = json.loads(cookie_val)
        except: pass

    def get_cookie_val(key, default=None):
        return saved_filters.get(key, default)

    # --- Controle de Paginação ---
    if "flight_page_idx" not in st.session_state:
        st.session_state.flight_page_idx = 0

    def reset_pagination():
        st.session_state.flight_page_idx = 0

    # --- UI DE FILTROS ---
    st.markdown("##### Configuração do Mapa")
    
    # Listas Globais Iniciais
    lista_pracas_base = sorted(df_crowley_copy["Praca"].dropna().unique())
    
    # Recuperação de Defaults
    default_praca_val = get_cookie_val("praca")
    if default_praca_val not in lista_pracas_base: default_praca_val = lista_pracas_base[0] if lista_pracas_base else None
    
    # Inicialização Session State (Praça)
    if "flight_praca_key" not in st.session_state:
        st.session_state.flight_praca_key = default_praca_val

    with st.container(border=True):
        # LINHA 1: Ano (1), Mês (1), Dia (1), Praça (2)
        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
        
        lista_anos = sorted(df_crowley_copy["Ano"].dropna().unique(), reverse=True)
        default_ano = get_cookie_val("ano")
        idx_ano = lista_anos.index(default_ano) if default_ano in lista_anos else 0
        with c1:
            sel_ano = st.selectbox("1. Ano (*)", options=lista_anos, index=idx_ano, key="flight_ano", on_change=reset_pagination)
        
        df_ano = df_crowley_copy[df_crowley_copy["Ano"] == sel_ano]
        lista_meses_num = sorted(df_ano["Mes"].dropna().unique())
        lista_meses_fmt = [(m, mes_map.get(m, str(m))) for m in lista_meses_num]
        saved_mes = get_cookie_val("mes")
        idx_mes = next((i for i, (m_num, _) in enumerate(lista_meses_fmt) if m_num == saved_mes), 0)
        
        with c2:
            sel_mes_tuple = st.selectbox("2. Mês (*)", options=lista_meses_fmt, index=idx_mes, format_func=lambda x: x[1], key="flight_mes", on_change=reset_pagination)
            sel_mes = sel_mes_tuple[0] if sel_mes_tuple else None

        lista_dias = []
        if sel_ano and sel_mes:
            try:
                _, last_day = calendar.monthrange(int(sel_ano), int(sel_mes))
                lista_dias = list(range(1, last_day + 1))
            except: pass
        saved_dias = get_cookie_val("dias", [])
        valid_dias = [d for d in saved_dias if d in lista_dias]
        
        with c3:
            sel_dias = st.multiselect("3. Dias (Opc.)", options=lista_dias, default=valid_dias, placeholder="Todo o mês", key="flight_dias", on_change=reset_pagination)

        with c4:
            sel_praca = st.selectbox("4. Praça (*)", options=lista_pracas_base, key="flight_praca_key", on_change=reset_pagination)

        st.divider()
        
        # --- FILTRO EM CASCATA ---
        # 1. Filtra base por Tempo e Praça para obter veículos
        df_context_nv1 = df_crowley_copy[
            (df_crowley_copy["Ano"] == sel_ano) & 
            (df_crowley_copy["Mes"] == sel_mes) & 
            (df_crowley_copy["Praca"] == sel_praca)
        ] if sel_ano and sel_mes and sel_praca else pd.DataFrame()
        
        # LINHA 2: Veículo, Anunciante, Tipo
        c5, c6, c7 = st.columns(3)
        
        # 5. Veículo
        lista_veiculos = sorted(df_context_nv1["Emissora"].dropna().unique())
        saved_veiculo = get_cookie_val("veiculo")
        idx_veiculo = lista_veiculos.index(saved_veiculo) if saved_veiculo in lista_veiculos else 0
        
        with c5:
            sel_veiculo = st.selectbox("5. Veículo (*)", options=lista_veiculos, index=idx_veiculo, key="flight_veiculo", on_change=reset_pagination)
            
        # 2. Filtra base por Veículo para obter Anunciantes e TIPOS ESPECÍFICOS DESTE VEÍCULO/PERÍODO
        df_context_nv2 = df_context_nv1[df_context_nv1["Emissora"] == sel_veiculo] if not df_context_nv1.empty else pd.DataFrame()
        
        # 6. Anunciante
        lista_anunciantes = sorted(df_context_nv2["Anunciante"].dropna().unique())
        saved_anunciantes = get_cookie_val("anunciantes", [])
        valid_anunciantes = [a for a in saved_anunciantes if a in lista_anunciantes]
        
        with c6:
            sel_anunciantes = st.multiselect("6. Anunciantes (Opc.)", options=lista_anunciantes, default=valid_anunciantes, placeholder="Todos", key="flight_anunciantes", on_change=reset_pagination)

        # 7. Tipo de Veiculação (AGORA SIM, FILTRO EM CASCATA COMPLETO)
        # As opções vêm do contexto filtrado por Ano + Mês + Praça + Veículo
        tipos_disponiveis = sorted(df_context_nv2["Tipo"].dropna().unique().tolist())
        
        # Lógica de persistência e limpeza do Session State para Tipos
        saved_tipos = get_cookie_val("tipo_veiculacao", [])
        if "Consolidado" in saved_tipos: saved_tipos = []
        
        if "flight_tipo_key" not in st.session_state:
            # Inicialização
            valid_tipos_init = [t for t in saved_tipos if t in tipos_disponiveis]
            st.session_state.flight_tipo_key = valid_tipos_init
        else:
            # Manutenção: Remove tipos selecionados que não existem no novo contexto (ex: mudou de praça/mês)
            current_selection = st.session_state.flight_tipo_key
            valid_selection = [t for t in current_selection if t in tipos_disponiveis]
            st.session_state.flight_tipo_key = valid_selection

        with c7:
            sel_tipos = st.multiselect(
                "7. Tipo de Veiculação (Opc.)", 
                options=tipos_disponiveis, 
                key="flight_tipo_key",     
                placeholder="Todos",
                on_change=reset_pagination
            )

        st.markdown("<br>", unsafe_allow_html=True)
        
        c_spacer_L, c_btn, c_spacer_R = st.columns([2, 1, 2])
        with c_btn:
            btn_gerar = st.button("Gerar Mapa Flight", type="primary", use_container_width=True)

    if btn_gerar:
        st.session_state["flight_search_trigger"] = True
        reset_pagination()
        
        tipos_cookie = sel_tipos if sel_tipos else ["Consolidado"]
        new_cookie = {
            "ano": int(sel_ano) if sel_ano else None,
            "mes": int(sel_mes) if sel_mes else None,
            "dias": sel_dias,
            "praca": sel_praca,
            "veiculo": sel_veiculo,
            "anunciantes": sel_anunciantes,
            "tipo_veiculacao": tipos_cookie
        }
        cookies["crowley_filters_flight"] = json.dumps(new_cookie)
        cookies.save()

    # --- PROCESSAMENTO E TABELA ---
    if st.session_state.get("flight_search_trigger") and sel_ano and sel_mes and sel_praca and sel_veiculo:
        
        nome_mes_display = mes_map.get(sel_mes, str(sel_mes))
        
        # 1. Filtros (Reutilizando a lógica, pois o contexto já filtrou tudo, mas por segurança aplicamos na base full)
        mask = (
            (df_crowley_copy["Ano"] == sel_ano) &
            (df_crowley_copy["Mes"] == sel_mes) &
            (df_crowley_copy["Praca"] == sel_praca) &
            (df_crowley_copy["Emissora"] == sel_veiculo)
        )
        if sel_anunciantes: mask = mask & (df_crowley_copy["Anunciante"].isin(sel_anunciantes))
        if sel_dias: mask = mask & (df_crowley_copy["Dia"].isin(sel_dias))
        if sel_tipos: mask = mask & (df_crowley_copy["Tipo"].isin(sel_tipos))
        
        df_final = df_crowley_copy[mask].copy()
        
        if df_final.empty:
            st.warning("Nenhuma inserção encontrada com os filtros selecionados.")
            return

        val_col = "Volume de Insercoes" if "Volume de Insercoes" in df_final.columns else "Contagem"
        if val_col == "Contagem": df_final["Contagem"] = 1

        # 2. PIVOT
        pivot = pd.pivot_table(
            df_final,
            index=["Anunciante", "Tipo"], 
            columns="Dia",
            values=val_col,
            aggfunc="sum",
            fill_value=0,
            observed=True
        )

        if sel_dias: days_range = sorted(sel_dias)
        else:
            _, last_day = calendar.monthrange(int(sel_ano), int(sel_mes))
            days_range = list(range(1, last_day + 1))
        
        pivot = pivot.reindex(columns=days_range, fill_value=0)
        
        pivot["TOTAL"] = pivot.sum(axis=1)
        pivot = pivot[pivot["TOTAL"] > 0]
        pivot = pivot.sort_values("TOTAL", ascending=False)
        
        if pivot.empty:
            st.warning("Nenhum dado para exibir.")
            return

        daily_totals = pivot.sum(numeric_only=True)
        total_row = pd.DataFrame(daily_totals).T
        total_row.index = ["TOTAL DIÁRIO"] 
        pivot.columns = [f"{c:02d}" if isinstance(c, int) else c for c in pivot.columns]
        total_row.columns = pivot.columns

        # --- FLATTENING ---
        df_display_flat = pivot.reset_index() 
        df_display_flat = df_display_flat.rename(columns={'Tipo': 'Tipo de Veiculação'})
        
        # Paginação
        ROWS_PER_PAGE = 20
        total_rows = len(df_display_flat)
        total_pages = math.ceil(total_rows / ROWS_PER_PAGE)
        
        current_page = st.session_state.flight_page_idx
        if current_page >= total_pages: 
            current_page = 0
            st.session_state.flight_page_idx = 0
            
        start_idx = current_page * ROWS_PER_PAGE
        end_idx = start_idx + ROWS_PER_PAGE
        
        df_page = df_display_flat.iloc[start_idx:end_idx].copy()
        
        row_total_dict = total_row.iloc[0].to_dict()
        row_total_dict['Anunciante'] = "TOTAL DIÁRIO"
        row_total_dict['Tipo de Veiculação'] = "" 
        
        df_page = pd.concat([df_page, pd.DataFrame([row_total_dict])], ignore_index=True)
        
        # Visibilidade da Coluna
        should_hide_tipo = (len(sel_tipos) == 1)
        
        cols_days = [c for c in pivot.columns if c != "TOTAL"]
        
        if should_hide_tipo:
            cols_final = ["Anunciante"] + cols_days + ["TOTAL"]
        else:
            cols_final = ["Anunciante", "Tipo de Veiculação"] + cols_days + ["TOTAL"]

        df_page_view = df_page[cols_final]

        st.subheader(f"Mapa: **{sel_veiculo}** - {nome_mes_display}/{sel_ano}")
        
        apply_custom_css(hide_tipo_col=should_hide_tipo)
        
        col_config = {}
        col_config["TOTAL"] = st.column_config.TextColumn("Total", width="small")
        col_config["Anunciante"] = st.column_config.TextColumn("Anunciante", width="large")
        if not should_hide_tipo:
            col_config["Tipo de Veiculação"] = st.column_config.TextColumn("Tipo", width="medium")
            
        for c in cols_days: col_config[c] = st.column_config.TextColumn(c, width="small")

        # --- DEFINIÇÃO DE MAX_VAL (Correção Pylance) ---
        max_val = pivot[cols_days].max().max() if not pivot[cols_days].empty else 1

        styler = df_page_view.style\
            .background_gradient(cmap="YlOrRd", subset=cols_days, vmin=0, vmax=max_val)\
            .format({c: "{:.0f}" for c in cols_days + ["TOTAL"]})\
            .map(lambda x: "color: transparent" if (isinstance(x, (int, float)) and x == 0) else "color: black; font-weight: bold", subset=cols_days)\
            .map(lambda x: "background-color: #e6f3ff; font-weight: bold; border-left: 2px solid #ccc", subset=["TOTAL"])\
            .apply(lambda x: ["background-color: #d1e7dd; font-weight: bold" if x['Anunciante'] == "TOTAL DIÁRIO" else "" for i in x], axis=1)
        
        styler = styler.set_properties(**{'text-align': 'center'})

        st.dataframe(
            styler,
            height=(len(df_page_view) * 35) + 38,
            width="stretch",
            column_config=col_config,
            hide_index=True
        )

        # UI Paginação
        if total_pages > 1:
            st.markdown("<br>", unsafe_allow_html=True)
            c_prev, c_msg, c_next = st.columns([1, 2, 1])
            with c_prev:
                if st.button("Anterior", disabled=(current_page == 0), use_container_width=True):
                    st.session_state.flight_page_idx -= 1
                    st.rerun()
            with c_msg:
                st.markdown(f"<div style='text-align:center;font-weight:bold;color:#003366;padding-top:5px'>Página {current_page + 1} de {total_pages} • {total_rows} registros</div>", unsafe_allow_html=True)
            with c_next:
                if st.button("Próximo", disabled=(current_page == total_pages - 1), use_container_width=True):
                    st.session_state.flight_page_idx += 1
                    st.rerun()
        else:
            st.caption(f"Mostrando {total_rows} registros.")

        st.markdown("---")

        # --- Detalhamento ---
        with st.expander("Fonte de Dados Completa (Detalhamento)", expanded=False):
            rename_map = {
                "Praca": "Praça", "Anuncio": "Anúncio", "Duracao": "Duração",
                "Emissora": "Veículo", "Volume de Insercoes": "Inserções", 
                "Tipo": "Tipo de Veiculação", "DayPart": "DayPart"
            }
            df_detalhe = df_final.copy()
            if "Data_Dt" in df_detalhe.columns:
                df_detalhe["Data"] = df_detalhe["Data_Dt"].dt.strftime("%d/%m/%Y")
            
            cols_originais = ["Data", "Anunciante", "Anuncio", "Duracao", "Praca", "Emissora", "Tipo", "DayPart", "Volume de Insercoes"]
            cols_existentes = [c for c in cols_originais if c in df_detalhe.columns]
            
            df_exib_detalhe = df_detalhe[cols_existentes].rename(columns=rename_map)
            df_exib_detalhe.sort_values(by=["Anunciante", "Data"], inplace=True)
            st.dataframe(df_exib_detalhe, width="stretch", hide_index=True)

        # --- Exportação ---
        st.markdown("<br>", unsafe_allow_html=True)
        with st.spinner("Gerando Excel..."):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                workbook = writer.book
                fmt_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
                fmt_left = workbook.add_format({'align': 'left', 'valign': 'vcenter'})
                
                # CORREÇÃO: Formatação correta para listas vazias na exportação
                tipos_str = ", ".join(sel_tipos) if sel_tipos else "Todos"
                dias_str = ", ".join(map(str, sel_dias)) if sel_dias else "Todo o mês"
                anunciantes_str = ", ".join(sel_anunciantes) if sel_anunciantes else "Todos"
                
                f_data = {
                    "Parâmetro": ["Ano", "Mês", "Dias", "Praça", "Veículo", "Anunciantes", "Tipos"],
                    "Valor": [sel_ano, nome_mes_display, dias_str, sel_praca, sel_veiculo, anunciantes_str, tipos_str]
                }
                pd.DataFrame(f_data).to_excel(writer, sheet_name='Filtros', index=False)
                
                # Mapa Flight
                df_export = df_display_flat.copy()
                row_total_export = row_total_dict.copy()
                df_export = pd.concat([df_export, pd.DataFrame([row_total_export])], ignore_index=True)
                
                if should_hide_tipo:
                    cols_final_exp = ["Anunciante"] + cols_days + ["TOTAL"]
                else:
                    cols_final_exp = ["Anunciante", "Tipo de Veiculação"] + cols_days + ["TOTAL"]
                
                df_export = df_export[cols_final_exp]
                    
                df_export.to_excel(writer, sheet_name='Mapa Flight', index=False)
                ws_mapa = writer.sheets['Mapa Flight']
                
                if should_hide_tipo:
                    ws_mapa.set_column('A:A', 40, fmt_left)
                    ws_mapa.set_column('B:Z', 8, fmt_center)
                else:
                    ws_mapa.set_column('A:A', 40, fmt_left)   
                    ws_mapa.set_column('B:B', 20, fmt_center) 
                    ws_mapa.set_column('C:Z', 8, fmt_center)

                # Detalhamento
                if not df_exib_detalhe.empty:
                    df_exib_detalhe.to_excel(writer, sheet_name='Detalhamento', index=False)
                    ws_det = writer.sheets['Detalhamento']
                    for idx, col in enumerate(df_exib_detalhe.columns):
                        width = 35 if col in ["Anunciante", "Anúncio", "Tipo de Veiculação"] else 15
                        align = fmt_left if col in ["Anunciante", "Anúncio"] else fmt_center
                        ws_det.set_column(idx, idx, width, align)

            c_L, c_btn_exp, c_R = st.columns([2, 1, 2])
            with c_btn_exp:
                st.download_button(
                    "Exportar Excel", 
                    data=buffer, 
                    file_name=f"Mapa_Flight_{sel_veiculo}_{nome_mes_display}_{sel_ano}.xlsx", 
                    mime="application/vnd.ms-excel", 
                    type="secondary", 
                    use_container_width=True
                )