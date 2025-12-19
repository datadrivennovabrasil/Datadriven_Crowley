# utils/export_crowley.py
import pandas as pd
import io
import xlsxwriter

def _save_tab(writer, df, name, include_index=True):
    """Função auxiliar para salvar abas com formatação padrão."""
    if df is not None and not df.empty:
        safe_name = name[:31]  # Limite do Excel
        workbook = writer.book
        fmt_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
        fmt_left = workbook.add_format({'align': 'left', 'valign': 'vcenter'})
        
        df.to_excel(writer, sheet_name=safe_name, index=include_index)
        worksheet = writer.sheets[safe_name]
        
        # Formatação básica
        if include_index:
            worksheet.set_column('A:A', 40, fmt_left) # Index column
            worksheet.set_column('B:Z', 15, fmt_center)
        else:
            # Tenta adivinhar colunas de texto vs numero
            for idx, col_name in enumerate(df.columns):
                if col_name in ["Anunciante", "Anúncio", "Tipo de Veiculação", "Veículo", "Praça"]:
                    worksheet.set_column(idx, idx, 35, fmt_left)
                else:
                    worksheet.set_column(idx, idx, 15, fmt_center)

def generate_campaign_flow_excel(dfs_dict, filters_info):
    """Gera Excel para Campaign Flow"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # 1. ABA FILTROS
        pd.DataFrame({
            "Parâmetro": list(filters_info.keys()),
            "Valor": list(filters_info.values())
        }).to_excel(writer, sheet_name='Filtros', index=False)
        writer.sheets['Filtros'].set_column('A:B', 40)

        # 2. DADOS
        _save_tab(writer, dfs_dict.get('exclusivos'), 'Exclusivos')
        _save_tab(writer, dfs_dict.get('comp_vol'), 'Comp. (Volume)')
        _save_tab(writer, dfs_dict.get('comp_share'), 'Comp. (Share)')
        _save_tab(writer, dfs_dict.get('ausentes_vol'), 'Ausentes (Volume)')
        _save_tab(writer, dfs_dict.get('ausentes_share'), 'Ausentes (Share)')
        _save_tab(writer, dfs_dict.get('detalhe'), 'Detalhamento', include_index=False)

    output.seek(0)
    return output

def generate_opportunity_radar_excel(dfs_dict, filters_info):
    """Gera Excel para Opportunity Radar"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # 1. ABA FILTROS
        pd.DataFrame({
            "Parâmetro": list(filters_info.keys()),
            "Valor": list(filters_info.values())
        }).to_excel(writer, sheet_name='Filtros', index=False)
        writer.sheets['Filtros'].set_column('A:B', 40)

        # 2. VISÃO GERAL (PIVOT)
        _save_tab(writer, dfs_dict.get('overview'), 'Visão Geral', include_index=True)

        # 3. DETALHAMENTO
        _save_tab(writer, dfs_dict.get('detail'), 'Detalhamento', include_index=False)

    output.seek(0)
    return output

def generate_presence_map_excel(dfs_dict, filters_info):
    """Gera Excel para Presence Map"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        fmt_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
        fmt_left = workbook.add_format({'align': 'left', 'valign': 'vcenter'})

        # 1. FILTROS
        pd.DataFrame({
            "Parâmetro": list(filters_info.keys()),
            "Valor": list(filters_info.values())
        }).to_excel(writer, sheet_name='Filtros', index=False)
        writer.sheets['Filtros'].set_column('A:B', 40)
        
        # 2. MAPA PRESENCE
        df_map = dfs_dict.get('map')
        if df_map is not None and not df_map.empty:
            df_map.to_excel(writer, sheet_name='Presence Map', index=False)
            ws_mapa = writer.sheets['Presence Map']
            
            has_tipo = "Tipo de Veiculação" in df_map.columns
            if not has_tipo:
                ws_mapa.set_column('A:A', 40, fmt_left)
                ws_mapa.set_column('B:Z', 8, fmt_center)
            else:
                ws_mapa.set_column('A:A', 40, fmt_left)   
                ws_mapa.set_column('B:B', 20, fmt_center) 
                ws_mapa.set_column('C:Z', 8, fmt_center)

        # 3. DETALHAMENTO
        df_det = dfs_dict.get('detail')
        if df_det is not None and not df_det.empty:
            df_det.to_excel(writer, sheet_name='Detalhamento', index=False)
            ws_det = writer.sheets['Detalhamento']
            for idx, col in enumerate(df_det.columns):
                width = 35 if col in ["Anunciante", "Anúncio", "Tipo de Veiculação"] else 15
                align = fmt_left if col in ["Anunciante", "Anúncio"] else fmt_center
                ws_det.set_column(idx, idx, width, align)

    output.seek(0)
    return output

def generate_performance_index_excel(dfs_dict, filters_info):
    """Gera Excel para Performance Index"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        fmt_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
        fmt_left = workbook.add_format({'align': 'left', 'valign': 'vcenter'})

        # 1. FILTROS
        pd.DataFrame({
            "Parâmetro": list(filters_info.keys()),
            "Valor": list(filters_info.values())
        }).to_excel(writer, sheet_name='Filtros', index=False)
        writer.sheets['Filtros'].set_column('A:A', 30)
        writer.sheets['Filtros'].set_column('B:B', 50)

        # 2. RANKING
        df_rank = dfs_dict.get('ranking')
        if df_rank is not None and not df_rank.empty:
            df_rank.to_excel(writer, sheet_name='Ranking', index=False)
            ws_rank = writer.sheets['Ranking']
            ws_rank.set_column('A:B', 10, fmt_center)
            ws_rank.set_column('C:C', 40, fmt_left)
            ws_rank.set_column('D:G', 15, fmt_center)

        # 3. DETALHAMENTO
        df_det = dfs_dict.get('detail')
        if df_det is not None and not df_det.empty:
            df_det.to_excel(writer, sheet_name='Detalhamento', index=False)
            ws_det = writer.sheets['Detalhamento']
            for idx, col in enumerate(df_det.columns):
                width = 35 if col in ["Anunciante", "Anúncio", "Tipo de Veiculação"] else 15
                align = fmt_left if col in ["Anunciante", "Anúncio"] else fmt_center
                ws_det.set_column(idx, idx, width, align)

    output.seek(0)
    return output