# utils/loaders.py
import os
import gc
import time
import pandas as pd
import streamlit as st
import pyarrow.parquet as pq
import pyarrow as pa
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURAÇÃO ---
DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

PATH_CROWLEY = os.path.join(DATA_FOLDER, "crowley.parquet")

# --- AUTH DRIVE ---
def get_drive_service():
    if "gcp_service_account" not in st.secrets or "drive_files" not in st.secrets:
        st.error("❌ Erro: Secrets não configurados.")
        return None
    try:
        service_account_info = dict(st.secrets["gcp_service_account"])
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Erro Auth Drive: {e}")
        return None

# --- ROTINA DESTRUTIVA (LIMPEZA) ---
def nuke_and_prepare(files_list):
    """
    Remove arquivos e limpa memória agressivamente ANTES do download.
    """
    gc.collect()
    for f in files_list:
        if os.path.exists(f):
            try: os.remove(f)
            except Exception: pass
    time.sleep(1)
    gc.collect()

# --- DOWNLOADER ---
def download_file(service, file_id, dest_path):
    try:
        with open(dest_path, "wb") as f:
            request = service.files().get_media(fileId=file_id)
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        return True
    except Exception:
        return False

# ==========================================
# LOADER CROWLEY
# ==========================================

@st.cache_resource(ttl=3600, show_spinner="Atualizando Base Crowley...")
def load_crowley_base():
    # 1. Limpeza Prévia
    nuke_and_prepare([PATH_CROWLEY])
    
    service = get_drive_service()
    if not service: return None, "Erro Conexão"

    # Pega ID do arquivo no secrets
    file_id = st.secrets["drive_files"]["crowley_parquet"]
    
    # 2. Download
    if not download_file(service, file_id, PATH_CROWLEY):
        return None, "Erro Download"

    # 3. Leitura Otimizada (Self Destruct)
    try:
        gc.collect()
        # Lê usando memory map
        arrow_table = pq.read_table(PATH_CROWLEY, memory_map=True)
        # Converte para Pandas limpando o PyArrow da memória
        df = arrow_table.to_pandas(self_destruct=True, split_blocks=True)
        
        del arrow_table
        gc.collect()
        
        # 4. Otimização de Tipos (Redução de RAM)
        cat_cols = ["Praca", "Emissora", "Anunciante", "Anuncio", "Tipo", "DayPart"]
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].astype("category")

        num_cols = ["Volume de Insercoes", "Duracao"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype("int32")

        # Tratamento de Data
        ultima = "N/A"
        if "Data" in df.columns:
            df["Data_Dt"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
            try:
                m = df["Data_Dt"].max()
                if pd.notna(m): ultima = m.strftime("%d/%m/%Y")
            except: pass
            
            # Remove coluna original de texto para economizar memória
            df.drop(columns=["Data"], inplace=True) 

        # Se não achou data na coluna, tenta data do arquivo
        if ultima == "N/A" and os.path.exists(PATH_CROWLEY):
             ts = os.path.getmtime(PATH_CROWLEY)
             ultima = datetime.fromtimestamp(ts).strftime("%d/%m/%Y")

        return df, ultima

    except Exception:
        if os.path.exists(PATH_CROWLEY): os.remove(PATH_CROWLEY)
        return None, "Erro Leitura"