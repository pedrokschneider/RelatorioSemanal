"""
Gerenciador de Cache Simplificado - Tudo em um arquivo
Salve como simple_cache.py na pasta report_system/utils/
"""

import os
import pickle
import logging
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Optional

# Configurar logger
logger = logging.getLogger("ReportSystem")

class SimpleCacheManager:
    """Gerenciador de cache simples usando arquivos pickle."""
    
    def __init__(self, base_cache_dir="cache"):
        """
        Inicializa o gerenciador de cache.
        
        Args:
            base_cache_dir: Diretório base para os arquivos de cache
        """
        self.base_cache_dir = base_cache_dir
        
        # Criar estrutura de diretórios
        os.makedirs(base_cache_dir, exist_ok=True)
        
        # Subdiretórios para diferentes tipos de dados
        self.construflow_dir = os.path.join(base_cache_dir, "construflow")
        os.makedirs(self.construflow_dir, exist_ok=True)
        
        self.smartsheet_dir = os.path.join(base_cache_dir, "smartsheet")
        os.makedirs(self.smartsheet_dir, exist_ok=True)
        
        # Log de configuração
        logger.info(f"SimpleCacheManager inicializado em {base_cache_dir}")
    
    # === MÉTODOS GENÉRICOS ===
    
    def save_data(self, filename: str, data: Any, data_type: str = None):
        """
        Salva dados em um arquivo pickle no cache.
        
        Args:
            filename: Nome do arquivo (sem extensão)
            data: Dados a serem salvos
            data_type: Tipo de dados ('construflow' ou 'smartsheet'), opcional
        
        Returns:
            True se salvo com sucesso, False caso contrário
        """
        try:
            # Determinar diretório com base no tipo de dados
            if data_type == 'construflow':
                file_path = os.path.join(self.construflow_dir, f"{filename}.pkl")
            elif data_type == 'smartsheet':
                file_path = os.path.join(self.smartsheet_dir, f"{filename}.pkl")
            else:
                file_path = os.path.join(self.base_cache_dir, f"{filename}.pkl")
            
            # Criar diretório pai se não existir
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Salvar dados usando pickle
            with open(file_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"Dados salvos com sucesso em {file_path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar dados em {filename}: {e}")
            return False
    
    def load_data(self, filename: str, data_type: str = None):
        """
        Carrega dados de um arquivo pickle do cache.
        
        Args:
            filename: Nome do arquivo (sem extensão)
            data_type: Tipo de dados ('construflow' ou 'smartsheet'), opcional
        
        Returns:
            Dados carregados ou None se não existir ou ocorrer erro
        """
        try:
            # Determinar caminho com base no tipo de dados
            if data_type == 'construflow':
                file_path = os.path.join(self.construflow_dir, f"{filename}.pkl")
            elif data_type == 'smartsheet':
                file_path = os.path.join(self.smartsheet_dir, f"{filename}.pkl")
            else:
                file_path = os.path.join(self.base_cache_dir, f"{filename}.pkl")
            
            # Verificar se o arquivo existe
            if not os.path.exists(file_path):
                logger.warning(f"Arquivo {file_path} não encontrado")
                return None
            
            # Carregar dados
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
            
            logger.info(f"Dados carregados com sucesso de {file_path}")
            return data
        except Exception as e:
            logger.error(f"Erro ao carregar dados de {filename}: {e}")
            return None
    
    def is_cache_valid(self, filename: str, max_age_hours: int = 24, data_type: str = None):
        """
        Verifica se o cache está válido (não é muito antigo).
        
        Args:
            filename: Nome do arquivo (sem extensão)
            max_age_hours: Idade máxima em horas
            data_type: Tipo de dados ('construflow' ou 'smartsheet'), opcional
        
        Returns:
            True se o cache estiver válido, False caso contrário
        """
        try:
            # Determinar caminho com base no tipo de dados
            if data_type == 'construflow':
                file_path = os.path.join(self.construflow_dir, f"{filename}.pkl")
            elif data_type == 'smartsheet':
                file_path = os.path.join(self.smartsheet_dir, f"{filename}.pkl")
            else:
                file_path = os.path.join(self.base_cache_dir, f"{filename}.pkl")
            
            # Verificar se o arquivo existe
            if not os.path.exists(file_path):
                return False
            
            # Verificar idade do arquivo
            file_time = os.path.getmtime(file_path)
            file_age_hours = (datetime.now().timestamp() - file_time) / 3600
            
            return file_age_hours < max_age_hours
        except Exception as e:
            logger.error(f"Erro ao verificar validade do cache para {filename}: {e}")
            return False
    
    # === MÉTODOS ESPECÍFICOS PARA CONSTRUFLOW ===
    
    def save_construflow_data(self, endpoint: str, data: List[Dict]):
        """
        Salva dados do Construflow no cache.
        
        Args:
            endpoint: Nome do endpoint (projects, issues, etc.)
            data: Dados a serem salvos
        
        Returns:
            True se salvo com sucesso, False caso contrário
        """
        return self.save_data(endpoint, data, 'construflow')
    
    def load_construflow_data(self, endpoint: str):
        """
        Carrega dados do Construflow do cache.
        
        Args:
            endpoint: Nome do endpoint (projects, issues, etc.)
        
        Returns:
            Dados carregados ou None se não existir ou ocorrer erro
        """
        return self.load_data(endpoint, 'construflow')
    
    def get_project_issues(self, project_id: str):
        """
        Obtém issues de um projeto específico do cache.
        
        Args:
            project_id: ID do projeto
        
        Returns:
            Lista de issues ou lista vazia
        """
        issues = self.load_construflow_data('issues')
        if not issues:
            return []
        
        # Filtrar issues do projeto
        return [issue for issue in issues if str(issue.get('projectId', '')) == str(project_id)]
    
    # === MÉTODOS ESPECÍFICOS PARA SMARTSHEET ===
    
    def save_smartsheet_data(self, sheet_id: str, project_id: str, data: Any):
        """
        Salva dados do Smartsheet no cache, associando ao projeto.
        
        Args:
            sheet_id: ID da planilha Smartsheet
            project_id: ID do projeto associado
            data: Dados a serem salvos
        
        Returns:
            True se salvo com sucesso, False caso contrário
        """
        try:
            # Adicionar IDs aos dados
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        item['sheet_id'] = str(sheet_id)
                        item['project_id'] = str(project_id)
            elif isinstance(data, dict):
                data['sheet_id'] = str(sheet_id)
                data['project_id'] = str(project_id)
            
            # Salvar dados
            file_name = f"sheet_{sheet_id}"
            result = self.save_data(file_name, data, 'smartsheet')
            
            # Atualizar índice central para rastreamento
            self._update_smartsheet_index(sheet_id, project_id)
            
            return result
        except Exception as e:
            logger.error(f"Erro ao salvar dados do Smartsheet {sheet_id}: {e}")
            return False
    
    def load_smartsheet_data(self, sheet_id: str):
        """
        Carrega dados do Smartsheet do cache.
        
        Args:
            sheet_id: ID da planilha Smartsheet
        
        Returns:
            Dados carregados ou None se não existir ou ocorrer erro
        """
        file_name = f"sheet_{sheet_id}"
        return self.load_data(file_name, 'smartsheet')
    
    def get_smartsheet_by_project(self, project_id: str):
        """
        Obtém dados do Smartsheet para um projeto específico.
        
        Args:
            project_id: ID do projeto
        
        Returns:
            Dados do Smartsheet ou None
        """
        # Carregar índice de Smartsheets
        index = self.load_data('smartsheet_index')
        if not index or not isinstance(index, dict):
            return None
        
        # Verificar se existe Smartsheet para o projeto
        sheet_id = index.get(str(project_id))
        if not sheet_id:
            return None
        
        # Carregar dados do Smartsheet
        return self.load_smartsheet_data(sheet_id)
    
    def _update_smartsheet_index(self, sheet_id: str, project_id: str):
        """
        Atualiza o índice de Smartsheets.
        
        Args:
            sheet_id: ID da planilha Smartsheet
            project_id: ID do projeto associado
        """
        try:
            # Carregar índice existente
            index = self.load_data('smartsheet_index') or {}
            
            # Atualizar índice
            index[str(project_id)] = str(sheet_id)
            
            # Salvar índice atualizado
            self.save_data('smartsheet_index', index)
        except Exception as e:
            logger.error(f"Erro ao atualizar índice de Smartsheets: {e}")
    
    # === MÉTODOS DE UTILIDADE ===
    
    def clear_cache(self, data_type: str = None):
        """
        Limpa o cache para um tipo de dados ou todo o cache.
        
        Args:
            data_type: Tipo de dados ('construflow' ou 'smartsheet'), opcional
        
        Returns:
            True se limpo com sucesso, False caso contrário
        """
        try:
            if data_type == 'construflow':
                # Limpar apenas cache do Construflow
                for file in os.listdir(self.construflow_dir):
                    if file.endswith('.pkl'):
                        os.remove(os.path.join(self.construflow_dir, file))
                logger.info("Cache do Construflow limpo com sucesso")
            elif data_type == 'smartsheet':
                # Limpar apenas cache do Smartsheet
                for file in os.listdir(self.smartsheet_dir):
                    if file.endswith('.pkl'):
                        os.remove(os.path.join(self.smartsheet_dir, file))
                logger.info("Cache do Smartsheet limpo com sucesso")
            else:
                # Limpar todo o cache
                for dir_path in [self.construflow_dir, self.smartsheet_dir, self.base_cache_dir]:
                    for file in os.listdir(dir_path):
                        if file.endswith('.pkl'):
                            os.remove(os.path.join(dir_path, file))
                logger.info("Cache completo limpo com sucesso")
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            return False
    
    def get_cache_status(self):
        """
        Obtém status do cache.
        
        Returns:
            DataFrame com informações sobre os arquivos de cache
        """
        try:
            status_data = []
            
            # Verificar arquivos do Construflow
            for file in os.listdir(self.construflow_dir):
                if file.endswith('.pkl'):
                    file_path = os.path.join(self.construflow_dir, file)
                    mtime = os.path.getmtime(file_path)
                    size = os.path.getsize(file_path) / 1024  # KB
                    
                    status_data.append({
                        'file_name': file,
                        'data_type': 'construflow',
                        'last_modified': datetime.fromtimestamp(mtime),
                        'age_hours': (datetime.now().timestamp() - mtime) / 3600,
                        'size_kb': size
                    })
            
            # Verificar arquivos do Smartsheet
            for file in os.listdir(self.smartsheet_dir):
                if file.endswith('.pkl'):
                    file_path = os.path.join(self.smartsheet_dir, file)
                    mtime = os.path.getmtime(file_path)
                    size = os.path.getsize(file_path) / 1024  # KB
                    
                    status_data.append({
                        'file_name': file,
                        'data_type': 'smartsheet',
                        'last_modified': datetime.fromtimestamp(mtime),
                        'age_hours': (datetime.now().timestamp() - mtime) / 3600,
                        'size_kb': size
                    })
            
            # Verificar arquivos na raiz do cache
            for file in os.listdir(self.base_cache_dir):
                if file.endswith('.pkl') and os.path.isfile(os.path.join(self.base_cache_dir, file)):
                    file_path = os.path.join(self.base_cache_dir, file)
                    mtime = os.path.getmtime(file_path)
                    size = os.path.getsize(file_path) / 1024  # KB
                    
                    status_data.append({
                        'file_name': file,
                        'data_type': 'other',
                        'last_modified': datetime.fromtimestamp(mtime),
                        'age_hours': (datetime.now().timestamp() - mtime) / 3600,
                        'size_kb': size
                    })
            
            return pd.DataFrame(status_data)
        except Exception as e:
            logger.error(f"Erro ao obter status do cache: {e}")
            return pd.DataFrame()