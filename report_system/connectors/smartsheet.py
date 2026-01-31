"""
Conector para a API do Smartsheet - Versão simplificada usando .pkl
Salve como smartsheet.py na pasta report_system/connectors/
"""

import os
import pickle
import time
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Configurar logger
logger = logging.getLogger("ReportSystem")

class SmartsheetConnector:
    """Conector simplificado para a API do Smartsheet."""
    
    def __init__(self, config):
        """Inicializa o conector do Smartsheet."""
        self.config = config
        
        # Configurações da API
        self.base_url = config.get_env_var("SMARTSHEET_BASE_URL", "https://api.smartsheet.com/2.0/sheets/")
        self.token = config.get_env_var("SMARTSHEET_TOKEN")
        
        # Headers para autenticação
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }
        
        # Diretório de cache
        self.cache_dir = os.path.join(os.getcwd(), "cache", "smartsheet")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        logger.info("SmartsheetConnector inicializado")
    
    def get_sheet(self, sheet_id: str, use_cache: bool = True, 
                 force_refresh: bool = False) -> Dict:
        """
        Obtém os dados de uma planilha do Smartsheet com suporte a cache.
        """
        cache_file = os.path.join(self.cache_dir, f"sheet_{sheet_id}.pkl")
        
        # Verificar cache
        if use_cache and os.path.exists(cache_file) and not force_refresh:
            cache_time = os.path.getmtime(cache_file)
            cache_age = time.time() - cache_time
            
            # Cache válido por 24 horas (configurável)
            if cache_age < self.config.get_cache_duration_default():
                try:
                    with open(cache_file, 'rb') as f:
                        logger.info(f"Usando cache para Smartsheet {sheet_id}")
                        return pickle.load(f)
                except Exception as e:
                    logger.warning(f"Erro ao carregar cache para Smartsheet {sheet_id}: {e}")
        
        # Buscar dados da API
        logger.info(f"Buscando dados da API para Smartsheet {sheet_id}")
        url = f"{self.base_url}{sheet_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Converter para formato mais fácil de usar
            processed_data = self._process_sheet_data(data)
            
            # Salvar em cache
            if use_cache:
                try:
                    with open(cache_file, 'wb') as f:
                        pickle.dump(processed_data, f)
                    logger.info(f"Cache atualizado para Smartsheet {sheet_id}")
                except Exception as e:
                    logger.warning(f"Erro ao salvar cache para Smartsheet {sheet_id}: {e}")
            
            return processed_data
        except Exception as e:
            logger.error(f"Erro ao obter dados do Smartsheet {sheet_id}: {e}")
            return None
    
    def _process_sheet_data(self, sheet_data: Dict) -> List[Dict]:
        """
        Processa os dados brutos da API do Smartsheet para um formato mais amigável.
        """
        if 'columns' not in sheet_data or 'rows' not in sheet_data:
            logger.error(f"Formato inválido de dados do Smartsheet")
            return []
        
        # Mapear IDs de colunas para títulos
        column_map = {col['id']: col['title'] for col in sheet_data['columns']}
        
        # Processar linhas
        rows_data = []
        for row in sheet_data['rows']:
            row_dict = {}
            for cell in row.get('cells', []):
                col_id = cell.get('columnId')
                if col_id in column_map:
                    row_dict[column_map[col_id]] = cell.get('value')
            rows_data.append(row_dict)
        
        return rows_data
    
    def get_recent_tasks(self, sheet_id: str, weeks_range: float = None, 
                        use_cache: bool = True, force_refresh: bool = False) -> pd.DataFrame:
        """
        Obtém tarefas recentes de uma planilha Smartsheet.
        Inclui tarefas que iniciam OU terminam no período especificado.
        Por padrão, usa 60 dias (aproximadamente 8.5 semanas) para garantir que tarefas futuras sejam carregadas.
        """
        # Se weeks_range não for especificado, usar padrão de 60 dias (~8.5 semanas)
        if weeks_range is None:
            weeks_range = 60 / 7  # 60 dias em semanas
        
        sheet_data = self.get_sheet(sheet_id, use_cache=use_cache, force_refresh=force_refresh)
        df = pd.DataFrame(sheet_data)
        if df.empty:
            return df
        
        # Converter colunas de data
        if 'Data Término' in df.columns:
            df['Data Término'] = pd.to_datetime(df['Data Término'], errors='coerce')
        if 'Data Inicio' in df.columns:
            df['Data Inicio'] = pd.to_datetime(df['Data Inicio'], errors='coerce')
        
        # Definir intervalo de tempo
        today = datetime.today()
        last_week = today - timedelta(weeks=weeks_range)
        next_week = today + timedelta(weeks=weeks_range)
        
        # Filtrar por data de início OU data de término no período
        # Criar máscaras para cada condição
        mask_inicio = df['Data Inicio'].between(last_week, next_week) if 'Data Inicio' in df.columns else False
        mask_termino = df['Data Término'].between(last_week, next_week) if 'Data Término' in df.columns else False
        
        # Combinar as máscaras (OU lógico)
        filtered_df = df[mask_inicio | mask_termino]
        
        # Filtrar por Level 5 (apenas tarefas de nível 5)
        if 'Level' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Level'] == 5]
        
        # Retornar todas as colunas disponíveis
        return filtered_df