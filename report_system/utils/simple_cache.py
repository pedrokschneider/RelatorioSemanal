"""
Gerenciador de Cache Simplificado - Thread-safe com cache híbrido
Usa JSON para dados simples (List[Dict]) e Pickle para DataFrames.
"""

import os
import json
import pickle
import logging
import threading
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Optional

# Configurar logger
logger = logging.getLogger("ReportSystem")


class SimpleCacheManager:
    """Gerenciador de cache thread-safe com suporte a JSON e Pickle."""

    def __init__(self, base_cache_dir="cache"):
        """
        Inicializa o gerenciador de cache.

        Args:
            base_cache_dir: Diretório base para os arquivos de cache
        """
        self.base_cache_dir = base_cache_dir
        self._lock = threading.RLock()  # Lock recursivo para thread safety

        # Criar estrutura de diretórios
        os.makedirs(base_cache_dir, exist_ok=True)

        # Subdiretórios para diferentes tipos de dados
        self.construflow_dir = os.path.join(base_cache_dir, "construflow")
        os.makedirs(self.construflow_dir, exist_ok=True)

        self.smartsheet_dir = os.path.join(base_cache_dir, "smartsheet")
        os.makedirs(self.smartsheet_dir, exist_ok=True)

        # Log de configuração
        logger.info(f"SimpleCacheManager inicializado em {base_cache_dir}")

    def _is_dataframe(self, data: Any) -> bool:
        """Verifica se os dados são um DataFrame do Pandas."""
        return isinstance(data, pd.DataFrame)

    def _get_file_path(self, filename: str, data_type: str = None, use_json: bool = False) -> str:
        """
        Determina o caminho do arquivo de cache.

        Args:
            filename: Nome do arquivo (sem extensão)
            data_type: Tipo de dados ('construflow' ou 'smartsheet')
            use_json: Se True, usa extensão .json, senão .pkl
        """
        ext = ".json" if use_json else ".pkl"

        if data_type == 'construflow':
            return os.path.join(self.construflow_dir, f"{filename}{ext}")
        elif data_type == 'smartsheet':
            return os.path.join(self.smartsheet_dir, f"{filename}{ext}")
        else:
            return os.path.join(self.base_cache_dir, f"{filename}{ext}")

    # === MÉTODOS GENÉRICOS ===

    def save_data(self, filename: str, data: Any, data_type: str = None) -> bool:
        """
        Salva dados no cache de forma thread-safe.
        Usa JSON para List[Dict] e Pickle para DataFrames.

        Args:
            filename: Nome do arquivo (sem extensão)
            data: Dados a serem salvos
            data_type: Tipo de dados ('construflow' ou 'smartsheet'), opcional

        Returns:
            True se salvo com sucesso, False caso contrário
        """
        with self._lock:
            try:
                # Determinar formato baseado no tipo de dado
                is_df = self._is_dataframe(data)
                use_json = not is_df and isinstance(data, (list, dict))

                file_path = self._get_file_path(filename, data_type, use_json)

                # Criar diretório pai se não existir
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                if use_json:
                    # Salvar como JSON (mais seguro para List[Dict])
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
                    logger.debug(f"Dados salvos como JSON em {file_path}")
                else:
                    # Salvar como Pickle (necessário para DataFrames)
                    with open(file_path, 'wb') as f:
                        pickle.dump(data, f)
                    logger.debug(f"Dados salvos como Pickle em {file_path}")

                logger.info(f"Cache atualizado: {filename}")
                return True
            except Exception as e:
                logger.error(f"Erro ao salvar dados em {filename}: {e}")
                return False

    def load_data(self, filename: str, data_type: str = None) -> Optional[Any]:
        """
        Carrega dados do cache de forma thread-safe.
        Tenta JSON primeiro, depois Pickle.

        Args:
            filename: Nome do arquivo (sem extensão)
            data_type: Tipo de dados ('construflow' ou 'smartsheet'), opcional

        Returns:
            Dados carregados ou None se não existir ou ocorrer erro
        """
        with self._lock:
            try:
                # Tentar carregar JSON primeiro (mais seguro)
                json_path = self._get_file_path(filename, data_type, use_json=True)
                pkl_path = self._get_file_path(filename, data_type, use_json=False)

                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    logger.debug(f"Dados carregados de JSON: {json_path}")
                    return data
                elif os.path.exists(pkl_path):
                    with open(pkl_path, 'rb') as f:
                        data = pickle.load(f)
                    logger.debug(f"Dados carregados de Pickle: {pkl_path}")
                    return data
                else:
                    logger.debug(f"Cache não encontrado para {filename}")
                    return None
            except Exception as e:
                logger.error(f"Erro ao carregar dados de {filename}: {e}")
                return None

    def is_cache_valid(self, filename: str, max_age_hours: int = 24, data_type: str = None) -> bool:
        """
        Verifica se o cache está válido (não é muito antigo).

        Args:
            filename: Nome do arquivo (sem extensão)
            max_age_hours: Idade máxima em horas
            data_type: Tipo de dados ('construflow' ou 'smartsheet'), opcional

        Returns:
            True se o cache estiver válido, False caso contrário
        """
        with self._lock:
            try:
                # Verificar ambos os formatos
                json_path = self._get_file_path(filename, data_type, use_json=True)
                pkl_path = self._get_file_path(filename, data_type, use_json=False)

                file_path = None
                if os.path.exists(json_path):
                    file_path = json_path
                elif os.path.exists(pkl_path):
                    file_path = pkl_path

                if not file_path:
                    return False

                # Verificar idade do arquivo
                file_time = os.path.getmtime(file_path)
                file_age_hours = (datetime.now().timestamp() - file_time) / 3600

                return file_age_hours < max_age_hours
            except Exception as e:
                logger.error(f"Erro ao verificar validade do cache para {filename}: {e}")
                return False

    # === MÉTODOS ESPECÍFICOS PARA CONSTRUFLOW ===

    def save_construflow_data(self, endpoint: str, data: List[Dict]) -> bool:
        """
        Salva dados do Construflow no cache.

        Args:
            endpoint: Nome do endpoint (projects, issues, etc.)
            data: Dados a serem salvos

        Returns:
            True se salvo com sucesso, False caso contrário
        """
        return self.save_data(endpoint, data, 'construflow')

    def load_construflow_data(self, endpoint: str) -> Optional[List[Dict]]:
        """
        Carrega dados do Construflow do cache.

        Args:
            endpoint: Nome do endpoint (projects, issues, etc.)

        Returns:
            Dados carregados ou None se não existir ou ocorrer erro
        """
        return self.load_data(endpoint, 'construflow')

    def get_project_issues(self, project_id: str) -> List[Dict]:
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

    def save_smartsheet_data(self, sheet_id: str, project_id: str, data: Any) -> bool:
        """
        Salva dados do Smartsheet no cache, associando ao projeto.

        Args:
            sheet_id: ID da planilha Smartsheet
            project_id: ID do projeto associado
            data: Dados a serem salvos

        Returns:
            True se salvo com sucesso, False caso contrário
        """
        with self._lock:
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

    def load_smartsheet_data(self, sheet_id: str) -> Optional[Any]:
        """
        Carrega dados do Smartsheet do cache.

        Args:
            sheet_id: ID da planilha Smartsheet

        Returns:
            Dados carregados ou None se não existir ou ocorrer erro
        """
        file_name = f"sheet_{sheet_id}"
        return self.load_data(file_name, 'smartsheet')

    def get_smartsheet_by_project(self, project_id: str) -> Optional[Any]:
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

    def _update_smartsheet_index(self, sheet_id: str, project_id: str) -> None:
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

    def clear_cache(self, data_type: str = None) -> bool:
        """
        Limpa o cache para um tipo de dados ou todo o cache.

        Args:
            data_type: Tipo de dados ('construflow' ou 'smartsheet'), opcional

        Returns:
            True se limpo com sucesso, False caso contrário
        """
        with self._lock:
            try:
                def clear_directory(dir_path: str) -> None:
                    for file in os.listdir(dir_path):
                        if file.endswith(('.pkl', '.json')):
                            os.remove(os.path.join(dir_path, file))

                if data_type == 'construflow':
                    clear_directory(self.construflow_dir)
                    logger.info("Cache do Construflow limpo com sucesso")
                elif data_type == 'smartsheet':
                    clear_directory(self.smartsheet_dir)
                    logger.info("Cache do Smartsheet limpo com sucesso")
                else:
                    for dir_path in [self.construflow_dir, self.smartsheet_dir, self.base_cache_dir]:
                        if os.path.isdir(dir_path):
                            clear_directory(dir_path)
                    logger.info("Cache completo limpo com sucesso")
                return True
            except Exception as e:
                logger.error(f"Erro ao limpar cache: {e}")
                return False

    def get_cache_status(self) -> pd.DataFrame:
        """
        Obtém status do cache.

        Returns:
            DataFrame com informações sobre os arquivos de cache
        """
        with self._lock:
            try:
                status_data = []

                def scan_directory(dir_path: str, data_type: str) -> None:
                    if not os.path.isdir(dir_path):
                        return
                    for file in os.listdir(dir_path):
                        if file.endswith(('.pkl', '.json')) and os.path.isfile(os.path.join(dir_path, file)):
                            file_path = os.path.join(dir_path, file)
                            mtime = os.path.getmtime(file_path)
                            size = os.path.getsize(file_path) / 1024  # KB

                            status_data.append({
                                'file_name': file,
                                'data_type': data_type,
                                'format': 'json' if file.endswith('.json') else 'pickle',
                                'last_modified': datetime.fromtimestamp(mtime),
                                'age_hours': (datetime.now().timestamp() - mtime) / 3600,
                                'size_kb': size
                            })

                # Verificar todos os diretórios
                scan_directory(self.construflow_dir, 'construflow')
                scan_directory(self.smartsheet_dir, 'smartsheet')
                scan_directory(self.base_cache_dir, 'other')

                return pd.DataFrame(status_data)
            except Exception as e:
                logger.error(f"Erro ao obter status do cache: {e}")
                return pd.DataFrame()
