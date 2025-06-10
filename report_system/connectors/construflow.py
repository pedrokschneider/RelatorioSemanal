"""
Conector para a API do Construflow.
"""

import os
import pickle
import time
import logging
import pandas as pd
from typing import Dict, List

from .base import APIConnector
from ..config import ConfigManager

logger = logging.getLogger("ReportSystem")

class ConstruflowConnector(APIConnector):
    """Conector para a API do Construflow."""
    
    def __init__(self, config: ConfigManager):
        """Inicializa o conector do Construflow."""
        super().__init__(config)
        self.base_url = config.construflow_api_base
        self.api_key = config.construflow_api_key
        self.api_secret = config.construflow_api_secret
        self.auth = (self.api_key, self.api_secret)
        self.cache_dir = os.path.join(config.cache_dir, "construflow")
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_data(self, endpoint: str, template_version: str = '9.0.0', 
                 use_cache: bool = True, force_refresh: bool = False) -> List[Dict]:
        """
        Obtém dados da API do Construflow com suporte a cache.
        
        Args:
            endpoint: Endpoint da API (ex: 'projects', 'issues')
            template_version: Versão do template
            use_cache: Se deve usar cache
            force_refresh: Se deve forçar atualização do cache
            
        Returns:
            Lista de dicionários com dados
        """
        cache_file = os.path.join(self.cache_dir, f"{endpoint}_cache.pkl")
        
        # Verificar cache
        if use_cache and os.path.exists(cache_file) and not force_refresh:
            cache_time = os.path.getmtime(cache_file)
            cache_age = time.time() - cache_time
            
            # Cache válido por 24 horas (86400 segundos)
            if cache_age < 86400:
                try:
                    with open(cache_file, 'rb') as f:
                        logger.info(f"Usando cache para {endpoint}")
                        return pickle.load(f)
                except Exception as e:
                    logger.warning(f"Erro ao carregar cache para {endpoint}: {e}")
        
        # Buscar dados da API
        logger.info(f"Buscando dados da API para {endpoint}")
        data = self._fetch_all_pages(endpoint, template_version)
        
        # Salvar em cache
        if use_cache:
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(data, f)
                logger.info(f"Cache atualizado para {endpoint}")
            except Exception as e:
                logger.warning(f"Erro ao salvar cache para {endpoint}: {e}")
        
        return data
    
    def _fetch_all_pages(self, endpoint: str, template_version: str) -> List[Dict]:
        """
        Busca todas as páginas de um endpoint com paginação.
        
        Args:
            endpoint: Endpoint da API
            template_version: Versão do template
            
        Returns:
            Lista combinada de todos os dados
        """
        connector_version = "3.0.0"
        after = 0
        all_data = []
        
        while True:
            # Parâmetros da requisição
            include_header = "true" if after == 0 else "false"
            
            # Construir URL
            url = (
                f"{self.base_url}/data-lake/{endpoint}?"
                f"templateVersion={template_version}"
                f"&connectorVersion={connector_version}"
                f"&page[size]=1000"
                f"&page[after]={after}"
                f"&page[include_header]={include_header}"
            )
            
            # Fazer requisição
            response = self._make_request("GET", url, auth=self.auth)
            data = response.json()
            
            if not isinstance(data, dict) or 'data' not in data:
                logger.error(f"Estrutura de resposta inesperada: {data}")
                break
            
            # Adicionar dados
            page_data = data.get('data', [])
            
            # Se não for a primeira página, remover cabeçalho duplicado
            if all_data and page_data:
                page_data = page_data[1:]
            
            all_data.extend(page_data)
            
            # Verificar se há mais páginas
            if not data.get('meta', {}).get('has_more', False):
                break
            
            # Obter cursor para próxima página
            after = data['meta'].get('after_cursor')
            if after is None:
                logger.error("Cursor de paginação ausente na resposta")
                break
        
        return all_data
    
    def get_projects(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Obtém lista de projetos.
        
        Args:
            force_refresh: Se deve forçar atualização do cache
            
        Returns:
            DataFrame com projetos
        """
        projects = self.get_data("projects", force_refresh=force_refresh)
        df = pd.DataFrame(projects)
        
        # Garantir que a coluna ID seja string
        if 'id' in df.columns:
            df['id'] = df['id'].astype(str)
        
        return df
    
    def get_issues(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Obtém issues.
        
        Args:
            force_refresh: Se deve forçar atualização do cache
            
        Returns:
            DataFrame com issues
        """
        issues = self.get_data("issues", force_refresh=force_refresh)
        df = pd.DataFrame(issues)
        
        # Converter ProjectID para string
        if 'projectId' in df.columns:
            df['projectId'] = df['projectId'].astype(str).str.strip()
        
        return df
    
    def get_disciplines(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Obtém disciplinas.
        
        Args:
            force_refresh: Se deve forçar atualização do cache
            
        Returns:
            DataFrame com disciplinas
        """
        disciplines = self.get_data("disciplines", force_refresh=force_refresh)
        df = pd.DataFrame(disciplines)
        
        # Garantir que ID seja string
        if 'id' in df.columns:
            df['id'] = df['id'].astype(str)
        
        return df
    
    def get_issue_disciplines(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Obtém relação entre issues e disciplinas.
        
        Args:
            force_refresh: Se deve forçar atualização do cache
            
        Returns:
            DataFrame com relações
        """
        issue_disciplines = self.get_data("issues-disciplines", force_refresh=force_refresh)
        df = pd.DataFrame(issue_disciplines)
        
        # Garantir tipos consistentes
        if 'issueId' in df.columns:
            df['issueId'] = df['issueId'].astype(str)
        if 'disciplineId' in df.columns:
            df['disciplineId'] = df['disciplineId'].astype(str)
        
        return df
    
    def get_project_issues(self, project_id: str) -> pd.DataFrame:
        """
        Obtém issues filtradas por projeto.
        
        Args:
            project_id: ID do projeto
            
        Returns:
            DataFrame com issues do projeto
        """
        # Garantir que project_id seja string
        project_id = str(project_id).strip()
        
        # Obter dados
        df_issues = self.get_issues()
        df_disciplines = self.get_disciplines()
        df_issue_disciplines = self.get_issue_disciplines()
        
        # Filtrar por projeto
        df_filtered = df_issues[df_issues['projectId'] == project_id]
        
        if df_filtered.empty:
            logger.warning(f"Nenhuma issue encontrada para o projeto {project_id}")
            return pd.DataFrame()
        
        # Mesclar com disciplinas
        # Primeiro mesclar issue_disciplines com disciplines
        df_issue_disciplines['disciplineId'] = df_issue_disciplines['disciplineId'].astype(str)
        df_disciplines['id'] = df_disciplines['id'].astype(str)
        
        df_merged_disciplines = df_issue_disciplines.merge(
            df_disciplines,
            left_on='disciplineId',
            right_on='id',
            how='left'
        )
        
        # Depois mesclar com as issues
        df_filtered = df_filtered.copy()
        df_filtered['id'] = df_filtered['id'].astype(str)
        df_merged_disciplines['issueId'] = df_merged_disciplines['issueId'].astype(str)
        
        df_result = df_filtered.merge(
            df_merged_disciplines,
            left_on='id',
            right_on='issueId',
            how='left'
        )
        
        # Limpar colunas duplicadas
        if 'issueId' in df_result.columns:
            df_result.drop(columns=['issueId'], inplace=True)
        if 'id_y' in df_result.columns:
            df_result.drop(columns=['id_y'], inplace=True)
        if 'id_x' in df_result.columns:
            df_result.rename(columns={'id_x': 'id'}, inplace=True)
        
        return df_result