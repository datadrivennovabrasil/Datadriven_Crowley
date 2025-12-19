# pages/performance_index.py
import streamlit as st
import pandas as pd
import numpy as np
import json
import io
from datetime import datetime, timedelta, date

# Nova importação
from utils.export_crowley import generate_performance_index_excel

def render(df_crowley, cookies, data_atualizacao):
    # --- CONFIGURAÇÃO DE VISUAL ---
    pd.set_option("styler.render.max_elements", 5_000_000)

    # CSS Global e Específico
    st.markdown("""
        <style>
        /* Cabeçalho centralizado */
        [data-testid="stDataFrame"] th {
            text-align: center !important;
            vertical-align: middle !important;
        }
        /* Células centralizadas */
        [data-testid="stDataFrame"] td {
            text-align: center !important;
            vertical-align: middle !important;
        }
        /* Alinha à esquerda a coluna de Anunciante (3ª coluna visual na tabela principal) */
        [data-testid="stDataFrame"] td:nth-child(3) {
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
    if st.button("Voltar", key="btn_voltar_perf"):
        st.query_params["view"] = "menu"
        # Limpa chaves específicas do Performance Index
        keys_to_clear = ["perf_search_trigger", "perf_praca_key", "perf_veiculo_key", "perf_anunc_key", "perf_tipo_key", "show_perf_export"]
        for k in keys_to_clear:
            st.session_state.pop(k, None)
        st.rerun()

    # --- TÍTULOS ---
    st.markdown('<div class="page-title-centered">Performance Index</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle-centered">Ranking comparativo por anunciante</div>', unsafe_allow_html=True)
    
    # Validação da Base
    if df_crowley is None or df_crowley.empty:
        st.error("Base de dados não carregada.")
        st.stop()

    # Cópia para imutabilidade
    df_crowley_copy = df_crowley.copy()

    # Garante coluna de data
    if "Data_Dt" not in df_crowley_copy.columns:
        if "Data" in df_crowley_copy.columns:
            df_crowley_copy["Data_Dt"] = pd.to_datetime(df_crowley_copy["Data"], dayfirst=True, errors="coerce")
        else:
            st.error("Coluna de Data não encontrada na base.")
            st.stop()

    # --- DATAS LIMITE ---
    min_date_allowed = date(2024, 1, 1)
    try:
        max_date_allowed = datetime.strptime(data_atualizacao, "%d/%m/%Y").date()
    except:
        max_date_allowed = datetime.now().date()
        
    tooltip_dates = f"Dados disponíveis para pesquisa:\nDe 01/01/2024 até {data_atualizacao}"

    # --- COOKIES E PERSISTÊNCIA ---
    saved_filters = {}
    cookie_val = cookies.get("crowley_filters_performance") # Cookie Renomeado
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
    if "perf_praca_key" not in st.session_state:
        st.session_state.perf_praca_key = saved_praca

    def on_change_reset():
        st.session_state["perf_search_trigger"] = False

    with st.container(border=True):
        # 1. Datas
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Período de Análise (Atual)**", help=tooltip_dates)
            col_d1, col_d2 = st.columns(2)
            dt_ini = col_d1.date_input("Início", value=val_dt_ini, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY", key="perf_dt_ini")
            dt_fim = col_d2.date_input("Fim", value=val_dt_fim, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY", key="perf_dt_fim")
        
        with c2:
            st.markdown("**Período de Comparação (Anterior)**", help=tooltip_dates)
            col_d3, col_d4 = st.columns(2)
            ref_ini = col_d3.date_input("Ref. Início", value=val_ref_ini, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY", key="perf_ref_ini")
            ref_fim = col_d4.date_input("Ref. Fim", value=val_ref_fim, min_value=min_date_allowed, max_value=max_date_allowed, format="DD/MM/YYYY", key="perf_ref_fim")

        st.divider()

        # --- CÁLCULO DO CONTEXTO (CASCATA) ---
        ts_ini_ctx = pd.Timestamp(dt_ini)
        ts_fim_ctx = pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        sel_praca_ctx = st.session_state.perf_praca_key

        mask_context = (
            (df_crowley_copy["Data_Dt"] >= ts_ini_ctx) &
            (df_crowley_copy["Data_Dt"] <= ts_fim_ctx) &
            (df_crowley_copy["Praca"] == sel_praca_ctx)
        )
        df_context = df_crowley_copy[mask_context]
        
        # Listas Disponíveis no Contexto
        raw_veiculos_local = sorted(df_context["Emissora"].dropna().unique())
        lista_anunciantes_local = sorted(df_context["Anunciante"].dropna().unique())
        tipos_disponiveis = sorted(df_context["Tipo"].dropna().unique().tolist())
        
        opcao_consolidado = "Consolidado (Todas as emissoras)"
        lista_veiculos_local = [opcao_consolidado] + raw_veiculos_local

        # 2. Filtros Categóricos - Linha 1
        c3, c4 = st.columns(2)

        with c3:
            sel_praca = st.selectbox("Praça", options=lista_pracas, key="perf_praca_key", on_change=on_change_reset)

        # Init Session State Veículo
        if "perf_veiculo_key" not in st.session_state:
            val_v = saved_veiculo if saved_veiculo in lista_veiculos_local else opcao_consolidado
            st.session_state.perf_veiculo_key = val_v
        else:
             if st.session_state.perf_veiculo_key not in lista_veiculos_local:
                 st.session_state.perf_veiculo_key = opcao_consolidado

        with c4:
            sel_veiculo = st.selectbox(
                "Veículo", 
                options=lista_veiculos_local, 
                key="perf_veiculo_key", 
                help="Selecione 'Consolidado' para ver o total do mercado na praça.",
                on_change=on_change_reset
            )

        # 3. Filtros Categóricos - Linha 2
        c5, c6 = st.columns(2)

        # Init Session State Tipo
        if "perf_tipo_key" not in st.session_state:
            valid_tipos_init = [t for t in saved_tipos if t in tipos_disponiveis]
            st.session_state.perf_tipo_key = valid_tipos_init
        else:
            curr = st.session_state.perf_tipo_key
            st.session_state.perf_tipo_key = [t for t in curr if t in tipos_disponiveis]

        with c5:
            sel_tipos = st.multiselect(
                "Tipo de Veiculação (Opc.)",
                options=tipos_disponiveis,
                key="perf_tipo_key",
                placeholder="Todos",
                on_change=on_change_reset
            )

        # Init Session State Anunciante
        if "perf_anunc_key" not in st.session_state:
            valid_anunc = [a for a in saved_anunciantes if a in lista_anunciantes_local]
            st.session_state.perf_anunc_key = valid_anunc
        else:
             curr_a = st.session_state.perf_anunc_key
             st.session_state.perf_anunc_key = [a for a in curr_a if a in lista_anunciantes_local]

        with c6:
            sel_anunciante = st.multiselect(
                "Filtrar Anunciante (Opcional)", 
                options=lista_anunciantes_local, 
                key="perf_anunc_key", 
                placeholder="Todos os anunciantes",
                on_change=on_change_reset
            )

        st.markdown("<br>", unsafe_allow_html=True)
        # Botão reduzido e centralizado
        c_v1, c_btn, c_v2 = st.columns([1, 1, 1])
        with c_btn:
            submitted = st.button("Gerar Performance Index", type="primary", use_container_width=True)

    # --- PROCESSAMENTO ---
    if submitted:
        st.session_state["perf_search_trigger"] = True
        
        tipos_para_cookie = sel_tipos if sel_tipos else ["Consolidado"]

        new_filters = {
            "dt_ini": str(dt_ini), "dt_fim": str(dt_fim),
            "ref_ini": str(ref_ini), "ref_fim": str(ref_fim),
            "praca": sel_praca, "veiculo": sel_veiculo,
            "anunciantes": sel_anunciante,
            "tipo_veiculacao": tipos_para_cookie
        }
        cookies["crowley_filters_performance"] = json.dumps(new_filters)
        cookies.save()

    if st.session_state.get("perf_search_trigger"):
        
        # 1. Filtro Base (Comum)
        mask_base = (df_crowley_copy["Praca"] == sel_praca)
        if sel_anunciante: mask_base = mask_base & (df_crowley_copy["Anunciante"].isin(sel_anunciante))
        if sel_tipos: mask_base = mask_base & (df_crowley_copy["Tipo"].isin(sel_tipos))
        if sel_veiculo != opcao_consolidado: mask_base = mask_base & (df_crowley_copy["Emissora"] == sel_veiculo)
            
        df_base = df_crowley_copy[mask_base]

        # 2. Divisão Temporal
        ts_ini, ts_fim = pd.Timestamp(dt_ini), pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        ts_ref_ini, ts_ref_fim = pd.Timestamp(ref_ini), pd.Timestamp(ref_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        df_atual = df_base[(df_base["Data_Dt"] >= ts_ini) & (df_base["Data_Dt"] <= ts_fim)]
        df_ref = df_base[(df_base["Data_Dt"] >= ts_ref_ini) & (df_base["Data_Dt"] <= ts_ref_fim)]

        if df_atual.empty and df_ref.empty:
            st.warning("Nenhum dado encontrado para os períodos selecionados (com os filtros atuais).")
            return

        # 3. Agregação
        val_col = "Volume de Insercoes" if "Volume de Insercoes" in df_base.columns else "Contagem"
        if val_col == "Contagem": 
            df_atual = df_atual.copy(); df_atual["Contagem"] = 1
            df_ref = df_ref.copy(); df_ref["Contagem"] = 1

        grp_atual = df_atual.groupby("Anunciante", observed=True)[val_col].sum().reset_index().rename(columns={val_col: "Ins_Atual"})
        grp_ref = df_ref.groupby("Anunciante", observed=True)[val_col].sum().reset_index().rename(columns={val_col: "Ins_Ref"})

        grp_atual["Anunciante"] = grp_atual["Anunciante"].astype(str)
        grp_ref["Anunciante"] = grp_ref["Anunciante"].astype(str)

        df_rank = pd.merge(grp_atual, grp_ref, on="Anunciante", how="outer").fillna(0)

        # 4. Cálculos
        df_rank["Rank_Atual"] = df_rank["Ins_Atual"].rank(ascending=False, method='min')
        df_rank["Rank_Anterior"] = df_rank["Ins_Ref"].rank(ascending=False, method='min')

        df_rank["Var %"] = np.where(
            df_rank["Ins_Ref"] > 0,
            (df_rank["Ins_Atual"] - df_rank["Ins_Ref"]) / df_rank["Ins_Ref"],
            np.where(df_rank["Ins_Atual"] > 0, 1.0, 0.0) 
        )

        total_atual = df_rank["Ins_Atual"].sum()
        df_rank["Share %"] = (df_rank["Ins_Atual"] / total_atual) if total_atual > 0 else 0.0

        # Ordenação
        df_rank = df_rank.sort_values(by=["Ins_Atual", "Ins_Ref"], ascending=[False, False]).reset_index(drop=True)
        df_rank["Posição"] = range(1, len(df_rank) + 1)

        # --- PREPARAÇÃO PARA EXIBIÇÃO ---
        df_rank = df_rank.rename(columns={
            "Posição": "Ranking",
            "Rank_Anterior": "Posição Anterior",
            "Ins_Atual": "Inserções (Atual)",
            "Ins_Ref": "Inserções (Anterior)"
        })

        total_ins_atual = df_rank["Inserções (Atual)"].sum()
        total_ins_ref = df_rank["Inserções (Anterior)"].sum()
        var_total = (total_ins_atual - total_ins_ref) / total_ins_ref if total_ins_ref > 0 else 0.0
        
        row_total = {
            "Ranking": "",           
            "Posição Anterior": "",  
            "Anunciante": "TOTAL GERAL",
            "Inserções (Atual)": total_ins_atual,
            "Share %": "",           
            "Var %": var_total,
            "Inserções (Anterior)": total_ins_ref
        }
        
        cols_show = ["Ranking", "Posição Anterior", "Anunciante", "Inserções (Atual)", "Share %", "Var %", "Inserções (Anterior)"]
        df_final_data = df_rank[cols_show].copy()
        
        # DF Numérico (com total row) para Styler e Exportação (Ranking)
        df_export_rank = pd.concat([df_final_data, pd.DataFrame([row_total])], ignore_index=True)

        # DF Texto para Tela (Styler)
        df_screen = df_export_rank.copy()
        df_screen["Ranking"] = df_screen["Ranking"].astype(str).str.replace(r'\.0$', '', regex=True)
        df_screen["Posição Anterior"] = df_screen["Posição Anterior"].astype(str).str.replace(r'\.0$', '', regex=True)
        df_screen["Share %"] = df_screen["Share %"].astype(str)

        def safe_fmt_share(val):
            if val == "": return ""
            try: return f"{float(val):.1%}"
            except: return str(val)

        def safe_fmt_int_dash(val):
            if val == "": return ""
            try:
                v = float(val)
                if v > 100000 or v <= 0: return "-"
                return f"{int(v)}"
            except: return str(val)
        
        def highlight_var(val):
            if isinstance(val, (float, int)):
                if val > 0: return 'color: #16a34a; font-weight: bold'
                if val < 0: return 'color: #dc2626; font-weight: bold'
            return ""

        st.markdown("### Resultado Comparativo")

        styler = df_screen.style\
            .format({
                "Inserções (Atual)": "{:,.0f}",
                "Inserções (Anterior)": "{:,.0f}",
                "Var %": "{:+.1%}",
                "Share %": safe_fmt_share,
                "Posição Anterior": safe_fmt_int_dash
            })\
            .map(highlight_var, subset=["Var %"])\
            .apply(lambda x: ["background-color: #f0f2f6; font-weight: bold" if x["Anunciante"] == "TOTAL GERAL" else "" for i in x], axis=1)
        
        styler = styler.set_properties(**{'text-align': 'center'})

        st.dataframe(
            styler,
            width="stretch",
            height=600,
            hide_index=True,
            column_config={
                "Ranking": st.column_config.TextColumn("Ranking", width="small"),
                "Posição Anterior": st.column_config.TextColumn("Posição Ant.", width="small"),
                "Anunciante": st.column_config.TextColumn("Anunciante", width="large"),
                "Var %": st.column_config.TextColumn("Var %", help="Variação em relação ao período anterior")
            }
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # --- DETALHAMENTO ---
        with st.expander("Fonte de Dados Completa (Detalhamento)", expanded=False):
            df_full_detail = pd.concat([df_atual, df_ref]).drop_duplicates()
            
            rename_map = {
                "Praca": "Praça", "Anuncio": "Anúncio", "Duracao": "Duração",
                "Emissora": "Veículo", "Volume de Insercoes": "Inserções", 
                "Tipo": "Tipo de Veiculação", "DayPart": "DayPart"
            }
            
            cols_originais = ["Data_Dt", "Anunciante", "Anuncio", "Duracao", "Praca", "Emissora", "Tipo", "DayPart", "Volume de Insercoes"]
            cols_existentes = [c for c in cols_originais if c in df_full_detail.columns]
            
            # DF Numérico Original (Exportação)
            df_exib_detalhe = df_full_detail[cols_existentes].rename(columns=rename_map)
            
            if "Data_Dt" in df_exib_detalhe.columns:
                df_exib_detalhe["Data"] = df_exib_detalhe["Data_Dt"].dt.strftime("%d/%m/%Y")
                df_exib_detalhe = df_exib_detalhe.drop(columns=["Data_Dt"])
                cols = ["Data"] + [c for c in df_exib_detalhe.columns if c != "Data"]
                df_exib_detalhe = df_exib_detalhe[cols]

            df_exib_detalhe.sort_values(by=["Anunciante", "Data"], inplace=True)

            # --- DF PARA VISUALIZAÇÃO (Com Total e String) ---
            df_exib_view = df_exib_detalhe.copy()

            if not df_exib_view.empty and "Inserções" in df_exib_view.columns:
                total_ins = df_exib_view["Inserções"].sum()
                
                # Linha de Total com Espaços
                row_total = {col: " " for col in df_exib_view.columns}
                row_total["Anunciante"] = "TOTAL GERAL"
                row_total["Inserções"] = total_ins
                
                # Append
                df_exib_view = pd.concat([df_exib_view, pd.DataFrame([row_total])], ignore_index=True)
                
                # CONVERSÃO PARA TEXTO (Evita erro do PyArrow)
                df_exib_view = df_exib_view.astype(str)

            st.dataframe(df_exib_view, width="stretch", hide_index=True)

        st.markdown("---")

        # ==================== EXPORTAÇÃO COM POP-UP ====================
        st.markdown("<br>", unsafe_allow_html=True)
        c_vazio1, c_vazio2, c_btn, c_vazio3, c_vazio4 = st.columns([1, 1, 1, 1, 1])
        with c_btn:
             if st.button("Exportar Excel", type="secondary", use_container_width=True):
                st.session_state.show_perf_export = True

        # --- DEFINIÇÃO DO DIALOG ---
        if st.session_state.get("show_perf_export", False):
            @st.dialog("Exportação")
            def export_dialog_performance():
                st.write("Gerando arquivo Excel...")

                # Prepara dados
                tipos_str = ", ".join(sel_tipos) if sel_tipos else "Todos"
                anunciantes_str = ", ".join(sel_anunciante) if sel_anunciante else "Todos"

                filters_info = {
                    "Período Atual": f"{dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}",
                    "Período Comparativo": f"{ref_ini.strftime('%d/%m/%Y')} a {ref_fim.strftime('%d/%m/%Y')}",
                    "Praça": sel_praca,
                    "Veículo": sel_veiculo,
                    "Anunciantes Filtro": anunciantes_str,
                    "Tipo de Veiculação": tipos_str
                }

                dfs_dict = {
                    'ranking': df_export_rank,
                    'detail': df_exib_detalhe
                }

                with st.spinner("Processando dados..."):
                    excel_buffer = generate_performance_index_excel(dfs_dict, filters_info)

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
                    file_name=f"Performance_Index_{sel_praca}_{datetime.now().strftime('%d%m')}.xlsx",
                    mime="application/vnd.ms-excel",
                    type="primary",
                    use_container_width=True,
                    on_click=lambda: st.session_state.update(show_perf_export=False)
                )

            export_dialog_performance()
        
        st.markdown(f"<div style='text-align:center;color:#666;font-size:0.8rem;margin-top:5px;'>Última atualização da base de dados: {data_atualizacao}</div>", unsafe_allow_html=True)