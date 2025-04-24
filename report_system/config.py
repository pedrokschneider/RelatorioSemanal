"""
Módulo de configuração para o sistema de relatórios.
"""

import os
import json
import logging
import requests
from typing import Any, Dict, Optional, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from google.oauth2 import service_account

logger = logging.getLogger("ReportSystem")

class ConfigManager:
    """Gerencia configurações do sistema de relatórios."""
    
    def __init__(self, env_path: str = ".env"):
        """
        Inicializa o gerenciador de configuração.
        
        Args:
            env_path: Caminho para o arquivo .env
        """
        # Carregar variáveis de ambiente
        self._load_env(env_path)
        
        # Diretório para cache
        self.cache_dir = self.get_env_var("CACHE_DIR", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Diretório para logs
        self.logs_dir = self.get_env_var("LOGS_DIR", "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Configurações API
        self.smartsheet_token = self.get_env_var("SMARTSHEET_TOKEN")
        self.smartsheet_base_url = self.get_env_var("SMARTSHEET_BASE_URL", "https://api.smartsheet.com/2.0/sheets/")
        
        self.construflow_api_base = self.get_env_var("CONSTRUFLOW_API_BASE_URL")
        self.construflow_api_key = self.get_env_var("CONSTRUFLOW_API_KEY")
        self.construflow_api_secret = self.get_env_var("CONSTRUFLOW_API_SECRET")
        
        # Configurações Google
        self.google_credentials_path = self.get_env_var("GOOGLE_CREDENTIALS_PATH")
        self.template_folder_id = self.get_env_var("TEMPLATE_FOLDER_ID")
        self.report_base_folder_id = self.get_env_var("REPORT_BASE_FOLDER_ID")
        
        # Google Sheets para configuração de projetos
        self.projects_sheet_id = self.get_env_var("PROJECTS_SHEET_ID")
        self.projects_sheet_name = self.get_env_var("PROJECTS_SHEET_NAME", "Projetos")
        
        # API key do Google Sheets (opcional)
        self.sheet_api_key = self.get_env_var("sheet_api_key")
        
        # Caminho para templates de prompt
        self.prompt_template_path = self.get_env_var("PROMPT_TEMPLATE_PATH", "templates/prompt_template.txt")
        
        # Configurações de Discord
        self.discord_token = self.get_env_var("DISCORD_TOKEN")
        self.discord_webhook_url = self.get_env_var("DISCORD_WEBHOOK_URL")
    
    def _load_env(self, env_path: str):
        """
        Carrega variáveis de ambiente do arquivo .env e valida existência.
        
        Args:
            env_path: Caminho para o arquivo .env
        """
        if not os.path.exists(env_path):
            logger.warning(f"Arquivo .env não encontrado em '{env_path}'. Usando variáveis de ambiente existentes.")
            return
            
        load_dotenv(env_path)
        logger.info(f"Variáveis de ambiente carregadas de '{env_path}'")
    
    def get_env_var(self, var_name: str, default: Any = None, required: bool = False) -> Any:
        """
        Obtém uma variável de ambiente com valor padrão.
        
        Args:
            var_name: Nome da variável
            default: Valor padrão se a variável não existir
            required: Se True, sempre loga avisos; se False, só loga em modo DEBUG
            
        Returns:
            Valor da variável ou o padrão
        """
        value = os.getenv(var_name, default)
        
        # Para variáveis sensíveis, não logar o valor completo
        sensitive_vars = ["TOKEN", "KEY", "SECRET", "PASSWORD", "CREDENTIALS"]
        is_sensitive = any(s in var_name for s in sensitive_vars)
        
        if value is not None and value != default:
            if is_sensitive and isinstance(value, str) and len(value) > 8:
                masked_value = value[:4] + '*' * (len(value) - 8) + value[-4:]
                logger.debug(f"Variável {var_name} carregada: {masked_value}")
            else:
                logger.debug(f"Variável {var_name} carregada")
        else:
            if default is not None:
                logger.debug(f"Variável {var_name} não encontrada, usando padrão")
            elif required:
                # Só logar como WARNING se a variável for realmente necessária
                logger.warning(f"Variável {var_name} não encontrada e sem valor padrão")
            else:
                # Para variáveis opcionais, usar o nível DEBUG
                logger.debug(f"Variável {var_name} não encontrada e sem valor padrão")
        
        return value
    
    def load_json_file(self, file_path: str, default: Any = None) -> Any:
        """
        Carrega um arquivo JSON se existir, caso contrário retorna o valor padrão.
        
        Args:
            file_path: Caminho para o arquivo JSON
            default: Valor padrão se o arquivo não existir ou for inválido
            
        Returns:
            Dados do arquivo JSON ou valor padrão
        """
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Arquivo JSON não encontrado: {file_path}")
                return default if default is not None else {}
                
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Não foi possível carregar {file_path}: {e}")
            return default if default is not None else {}
    
    def save_json_file(self, data: Any, file_path: str, indent: int = 2) -> bool:
        """
        Salva dados em um arquivo JSON.
        
        Args:
            data: Dados a serem salvos
            file_path: Caminho para o arquivo JSON
            indent: Indentação para formatação do JSON
            
        Returns:
            True se o arquivo foi salvo com sucesso, False caso contrário
        """
        try:
            # Criar diretório se não existir
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
                
            logger.info(f"Arquivo JSON salvo em {file_path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo JSON {file_path}: {e}")
            return False
    
    def get_http_session(self) -> requests.Session:
        """
        Cria e retorna uma sessão HTTP com retry configurado.
        
        Returns:
            Sessão HTTP configurada
        """
        session = requests.Session()
        
        # Configurar retry com backoff exponencial
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def get_google_creds(self):
        """
        Retorna as credenciais do Google.
        
        Returns:
            Objeto de credenciais do Google ou None se não encontrado
        """
        if not self.google_credentials_path:
            logger.warning("Caminho para credenciais do Google não configurado")
            return None
            
        if not os.path.exists(self.google_credentials_path):
            logger.error(f"Arquivo de credenciais do Google não encontrado: {self.google_credentials_path}")
            return None
        
        try:
            return service_account.Credentials.from_service_account_file(
                self.google_credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/spreadsheets'
                ]
            )
        except Exception as e:
            logger.error(f"Erro ao carregar credenciais do Google: {e}")
            return None
    
    def validate_required_config(self) -> Dict[str, bool]:
        """
        Valida se as configurações obrigatórias estão presentes.
        
        Returns:
            Dicionário com status de cada configuração obrigatória
        """
        required_configs = {
            'CONSTRUFLOW_API_KEY': bool(self.construflow_api_key),
            'CONSTRUFLOW_API_SECRET': bool(self.construflow_api_secret),
            'CONSTRUFLOW_API_BASE_URL': bool(self.construflow_api_base),
            'GOOGLE_CREDENTIALS_PATH': os.path.exists(self.google_credentials_path) if self.google_credentials_path else False,
            'PROJECTS_SHEET_ID': bool(self.projects_sheet_id),
            'PROMPT_TEMPLATE_PATH': os.path.exists(self.prompt_template_path) if self.prompt_template_path else False
        }
        
        # Verificar valores obrigatórios
        validity_status = {
            'all_valid': all(required_configs.values()),
            'configs': required_configs
        }
        
        if not validity_status['all_valid']:
            missing_configs = [key for key, valid in required_configs.items() if not valid]
            logger.warning(f"Configurações obrigatórias ausentes: {', '.join(missing_configs)}")
        
        return validity_status
    
    def get_template_content(self, template_name: Optional[str] = None) -> str:
        """
        Obtém o conteúdo do template de relatório.
        
        Args:
            template_name: Nome do template (se None, usa o padrão)
            
        Returns:
            Conteúdo do template ou string vazia se não encontrado
        """
        template_path = template_name or self.prompt_template_path
        
        if not template_path:
            logger.warning("Caminho para template não configurado")
            return ""
            
        try:
            if not os.path.exists(template_path):
                logger.error(f"Arquivo de template não encontrado: {template_path}")
                return ""
                
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            return content
        except Exception as e:
            logger.error(f"Erro ao ler template {template_path}: {e}")
            return ""