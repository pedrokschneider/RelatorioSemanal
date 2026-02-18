"""
Classe principal do sistema de relatórios semanais com cache otimizado.
"""

import os
import argparse
import logging
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from tqdm import tqdm
import sys
import requests
import json
from googleapiclient.discovery import build
import googleapiclient.errors


# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from report_system.config import ConfigManager
from report_system.processors.data_processor import DataProcessor
from report_system.generators import SimpleReportGenerator
from report_system.generators.html_report_generator import HTMLReportGenerator
from report_system.storage import GoogleDriveManager
from report_system.utils.logging_config import setup_logging
from report_system.utils.simple_cache import SimpleCacheManager
from report_system.utils import extract_discord_channel_id

# Sistema de mensagens de erro padronizadas
try:
    from report_system.utils.error_messages import (
        ErrorMessages, ErrorCategory, classify_error, get_error_response
    )
    ERROR_MESSAGES_AVAILABLE = True
except ImportError:
    ERROR_MESSAGES_AVAILABLE = False
from report_system.discord_handler import DiscordCommandHandler

# Configurar logging
logger = setup_logging()

class WeeklyReportSystem:
    """Sistema principal para geração de relatórios semanais."""
    
    def __init__(self, env_path: str = ".env", verbose_init: bool = True):
        """
        Inicializa o sistema de relatórios semanais.
        
        Args:
            env_path: Caminho para o arquivo .env
            verbose_init: Se deve mostrar logs detalhados durante inicialização
        """
        if verbose_init:
            logger.info("🚀 Inicializando Sistema de Relatórios Semanais")
        
        # Inicializar configuração
        self.config = ConfigManager(env_path)
        
        # Inicializar componentes
        self._initialize_connectors(verbose_init)
        self._initialize_managers(verbose_init)
        self._initialize_processor_and_generator(verbose_init)
        self.discord = self._initialize_discord_manager()
        
        # Inicializar controlador de relatórios semanais
        self._initialize_weekly_control()
        
        # Cache para configuração de projetos
        self.project_config_df = None
        
        if verbose_init:
            logger.info("✅ Sistema de Relatórios Semanais inicializado com sucesso")
    
    def _initialize_weekly_control(self):
        """Inicializa o controlador de relatórios semanais."""
        try:
            from report_system.weekly_report_control import WeeklyReportController
            self.weekly_controller = WeeklyReportController(self.config)
            logger.info("Controlador de relatórios semanais inicializado")
        except Exception as e:
            logger.warning(f"Não foi possível inicializar controlador de relatórios semanais: {e}")
            self.weekly_controller = None
    
    def _initialize_connectors(self, verbose_init: bool = True):
        """Inicializa os conectores de dados."""
        try:
            # Tentar usar GraphQL como principal
            try:
                from .connectors.construflow_graphql import ConstruflowGraphQLConnector
                self.construflow = ConstruflowGraphQLConnector(self.config)
                if verbose_init:
                    logger.info("✅ Conector GraphQL do Construflow inicializado")
            except ImportError as e:
                logger.warning(f"Conector GraphQL não disponível: {e}")
                # Fallback para REST
                from .connectors.construflow import ConstruflowConnector
                self.construflow = ConstruflowConnector(self.config)
                if verbose_init:
                    logger.info("✅ Conector REST do Construflow inicializado (fallback)")
            
            # Smartsheet
            from .connectors.smartsheet import SmartsheetConnector
            self.smartsheet = SmartsheetConnector(self.config)
            if verbose_init:
                logger.info("✅ Conector do Smartsheet inicializado")
                
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar conectores: {e}")
            raise

    def _initialize_managers(self, verbose_init: bool = True):
        """Inicializa os gerenciadores de cache e notificação."""
        try:
            # Inicializar o gerenciador de cache simplificado
            try:
                from report_system.utils.simple_cache import SimpleCacheManager
                self.cache_manager = SimpleCacheManager(self.config.cache_dir)
                if verbose_init:
                    logger.info("✅ Gerenciador de Cache inicializado")
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar Gerenciador de Cache: {e}")
                # Se falhar, criar diretório básico de cache
                cache_dir = os.path.join(os.getcwd(), "cache")
                os.makedirs(cache_dir, exist_ok=True)
                
                # Atribuir None e registrar erro
                self.cache_manager = None
                logger.error("Sistema de cache não disponível")
            
            # Inicializar o GoogleDriveManager
            self.gdrive = GoogleDriveManager(self.config)
            if verbose_init:
                logger.info("✅ GoogleDriveManager inicializado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar gerenciadores: {e}")
            raise

    def _initialize_processor_and_generator(self, verbose_init: bool = True):
        """Inicializa o processador de dados e o gerador de relatórios."""
        try:
            # Inicializar processador de dados com o conector GraphQL
            self.processor = DataProcessor(self.config, self.construflow)
            if verbose_init:
                logger.info("✅ DataProcessor inicializado com conector GraphQL")
            
            # Inicializar gerador de relatórios
            self.generator = SimpleReportGenerator(self.config)
            if verbose_init:
                logger.info("✅ SimpleReportGenerator inicializado")
            
            # Inicializar gerador de relatórios HTML
            self.html_generator = HTMLReportGenerator(self.config)
            if verbose_init:
                logger.info("✅ HTMLReportGenerator inicializado")
                
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar processador e gerador: {e}")
            raise

    def _initialize_discord_manager(self):
        """Inicializa o gerenciador de Discord com melhor tratamento de erros."""
        try:
            from report_system.discord_notification import DiscordNotificationManager
            discord_manager = DiscordNotificationManager(self.config)
            
            # Verificar se tem token configurado
            if hasattr(discord_manager, 'discord_token') and discord_manager.discord_token:
                logger.info("Gerenciador de Discord inicializado com sucesso")
                return discord_manager
            else:
                logger.warning("Gerenciador de Discord inicializado mas sem token configurado")
                return None
        except Exception as e:
            logger.warning(f"Não foi possível inicializar o gerenciador de Discord: {str(e)}")
            return None
    
    def process_discord_command(self, channel_id: str, command: str, project_id: str = None) -> bool:
        """
        Processa um comando recebido pelo Discord.
        
        Args:
            channel_id: ID do canal do Discord
            command: Comando a ser processado
            project_id: ID do projeto (opcional)
            
        Returns:
            True se o comando foi processado com sucesso, False caso contrário
        """
        if not hasattr(self, 'discord_handler'):
            self.discord_handler = DiscordCommandHandler(self.config, self)
        
        return self.discord_handler.process_command(channel_id, command, project_id)
    
    def _load_project_config(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Carrega a configuração de projetos da planilha.
        
        Args:
            force_refresh: Se deve forçar atualização
            
        Returns:
            DataFrame com configuração dos projetos
        """
        if self.project_config_df is None or force_refresh:
            self.project_config_df = self.gdrive.load_project_config_from_sheet()
        
        return self.project_config_df

    def _extract_column_value(self, project_row: pd.DataFrame, column_name: str) -> Optional[str]:
        """
        Extrai valor de uma coluna do DataFrame de forma segura.

        Args:
            project_row: DataFrame com dados do projeto
            column_name: Nome da coluna

        Returns:
            Valor da coluna ou None se ausente/inválido
        """
        if column_name not in project_row.columns:
            return None

        value = project_row[column_name].values[0]
        if pd.notna(value):
            value_str = str(value).strip()
            if value_str.lower() not in ['nan', 'none', 'null', '']:
                return value_str
        return None

    def _download_project_image(self, image_url: str, project_id: str, project_name: str) -> Optional[str]:
        """
        Baixa a imagem do projeto do Google Drive.

        Args:
            image_url: URL da imagem
            project_id: ID do projeto
            project_name: Nome do projeto

        Returns:
            Imagem em base64 ou None se falhar
        """
        if not hasattr(self, 'gdrive') or not self.gdrive:
            return None

        try:
            logger.info(f"📷 Processando imagem do projeto {project_id} ({project_name})")
            logger.info(f"   URL da imagem de capa: {image_url[:150]}...")

            file_id = self.gdrive.extract_file_id_from_url(image_url)
            if not file_id:
                self._log_file_id_extraction_error(image_url)
                return None

            logger.info(f"   🔑 File ID extraído: {file_id}")
            logger.info(f"   📥 Tentando baixar imagem do projeto...")

            project_image_base64 = self.gdrive.download_file_as_base64(file_id)
            if project_image_base64:
                logger.info(f"   ✅ Imagem do projeto carregada com sucesso (tamanho: {len(project_image_base64)} caracteres)")
                return project_image_base64

            self._log_image_download_error(file_id, image_url)
            return None

        except Exception as img_error:
            logger.error(f"❌ Erro ao processar imagem do projeto: {img_error}")
            logger.error(f"   URL da imagem: {image_url[:150] if image_url else 'N/A'}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return None

    def _log_file_id_extraction_error(self, image_url: str):
        """Log de erro ao extrair File ID da URL."""
        logger.warning(f"   ⚠️ Não foi possível extrair o File ID da URL.")
        logger.warning(f"      URL fornecida: {image_url[:150]}")
        logger.warning(f"      Verifique se a URL está no formato correto do Google Drive.")
        logger.warning(f"      Formatos suportados:")
        logger.warning(f"      - https://drive.google.com/file/d/FILE_ID/view")
        logger.warning(f"      - https://drive.google.com/open?id=FILE_ID")
        logger.warning(f"      - https://drive.google.com/uc?id=FILE_ID")
        logger.warning(f"      - FILE_ID (apenas o ID)")

    def _log_image_download_error(self, file_id: str, image_url: str):
        """Log de erro ao baixar imagem."""
        logger.warning(f"   ⚠️ Não foi possível baixar a imagem do projeto.")
        logger.warning(f"      Verifique se o arquivo existe no Google Drive e se as credenciais têm permissão para acessá-lo.")
        logger.warning(f"      File ID: {file_id}")
        logger.warning(f"      URL original: {image_url[:150]}")
        logger.warning(f"      Possíveis causas:")
        logger.warning(f"      1. O arquivo foi deletado ou movido")
        logger.warning(f"      2. O arquivo não está compartilhado com a conta de serviço")
        logger.warning(f"      3. O formato da URL não é reconhecido")

    def get_project_smartsheet_id(self, project_id: str) -> Optional[str]:
        """
        Obtém o ID do Smartsheet para um projeto.
        
        Args:
            project_id: ID do projeto
            
        Returns:
            ID do Smartsheet ou None
        """
        projects_df = self._load_project_config()
        
        if projects_df.empty:
            logger.warning(f"Falha ao obter ID Smartsheet para projeto {project_id}: Planilha de configuração vazia")
            return None
        
        if 'construflow_id' not in projects_df.columns:
            logger.warning(f"Falha ao obter ID Smartsheet para projeto {project_id}: Coluna 'construflow_id' não encontrada")
            logger.debug(f"Colunas disponíveis: {', '.join(projects_df.columns)}")
            return None
        
        if 'smartsheet_id' not in projects_df.columns:
            logger.warning(f"Falha ao obter ID Smartsheet para projeto {project_id}: Coluna 'smartsheet_id' não encontrada")
            logger.debug(f"Colunas disponíveis: {', '.join(projects_df.columns)}")
            return None
        
        # Garantir que o construflow_id é tratado como string para comparação
        projects_df['construflow_id'] = projects_df['construflow_id'].astype(str)
        
        # Filtrar projeto
        project_row = projects_df[projects_df['construflow_id'] == str(project_id)]
        
        if project_row.empty:
            logger.warning(f"Falha ao obter ID Smartsheet para projeto {project_id}: Projeto não encontrado na planilha")
            logger.debug(f"Total de projetos na planilha: {len(projects_df)}")
            return None
        
        if pd.isna(project_row['smartsheet_id'].values[0]):
            logger.warning(f"Falha ao obter ID Smartsheet para projeto {project_id}: Valor ausente na planilha")
            return None
        
        smartsheet_id = str(project_row['smartsheet_id'].values[0])
        logger.info(f"ID Smartsheet obtido para projeto {project_id}: {smartsheet_id}")
        return smartsheet_id
    
    def get_active_projects(self) -> List[Dict[str, Any]]:
        """
        Obtém a lista de projetos ativos da planilha.
        
        Returns:
            Lista de dicionários com dados dos projetos ativos
        """
        projects_df = self._load_project_config()
        
        if projects_df.empty:
            logger.warning("Planilha de configuração vazia ou inacessível")
            return []
        
        # Converter IDs para string
        projects_df['construflow_id'] = projects_df['construflow_id'].astype(str)
        
        # Verificar se temos a coluna relatoriosemanal_status
        if 'relatoriosemanal_status' in projects_df.columns:
            active_projects = projects_df[projects_df['relatoriosemanal_status'].str.lower() == 'sim']
        else:
            # Se não tiver coluna relatoriosemanal_status, considerar todos os projetos
            active_projects = projects_df
        
        logger.info(f"Total de projetos ativos: {len(active_projects)}")
        
        # Converter para lista de dicionários
        projects_list = []
        for _, row in active_projects.iterrows():
            try:
                project_dict = {
                    'id': str(row['construflow_id']),
                    'name': row.get('Projeto - PR', 'Projeto sem nome'), 
                    'smartsheet_id': str(row.get('smartsheet_id', '')),
                }
                
                # Adicionar disciplinas do cliente se disponível 
                if 'construflow_disciplinasclientes' in row and pd.notna(row['construflow_disciplinasclientes']):
                    disciplines_str = str(row['construflow_disciplinasclientes'])
                    if disciplines_str:
                        # Suportar tanto vírgula quanto ponto e vírgula como separadores
                        if ';' in disciplines_str:
                            disciplines = [d.strip() for d in disciplines_str.split(';') if d.strip()]
                        else:
                            disciplines = [d.strip() for d in disciplines_str.split(',') if d.strip()]
                        project_dict['disciplinas_cliente'] = disciplines
                
                # Adicionar nome_cliente se disponível
                if 'nome_cliente' in row and pd.notna(row['nome_cliente']):
                    project_dict['nome_cliente'] = row['nome_cliente']
                
                projects_list.append(project_dict)
            except Exception as e:
                logger.error(f"Erro ao processar projeto na linha {_}: {e}")
        
        return projects_list
        
    def get_client_names(self, project_id: str) -> List[str]:
        """
        Obtém os nomes do cliente para um projeto específico.
        
        Args:
            project_id: ID do projeto
            
        Returns:
            Lista de nomes do cliente
        """
        projects = self.get_active_projects()
        for project in projects:
            if project['id'] == project_id:
                nome_cliente = project.get('nome_cliente', [])
                if isinstance(nome_cliente, list):
                    return nome_cliente
                elif isinstance(nome_cliente, str):
                    return [nome_cliente]
                else:
                    return []
        return []
    
    def get_client_disciplines(self, project_id: str) -> List[str]:
        """
        Obtém as disciplinas sob responsabilidade do cliente para um projeto específico.
        
        Args:
            project_id: ID do projeto
            
        Returns:
            Lista de disciplinas do cliente
        """
        projects = self.get_active_projects()
        
        for project in projects:
            if project['id'] == project_id:
                return project.get('disciplinas_cliente', [])
        
        return []
    
    def get_project_by_discord_channel(self, channel_id: str) -> Optional[str]:
        """
        Busca o ID do projeto associado a um canal do Discord.
        
        Args:
            channel_id: ID do canal Discord
            
        Returns:
            ID do projeto ou None se não encontrado
        """
        projects_df = self._load_project_config()
        
        if projects_df.empty or 'discord_id' not in projects_df.columns:
            logger.warning("Planilha não contém coluna discord_id")
            return None
        
        # Limpar IDs para comparação (suporta URLs e IDs raw)
        channel_id_clean = extract_discord_channel_id(channel_id)

        # Verificar cada linha
        for _, row in projects_df.iterrows():
            if 'discord_id' in row and pd.notna(row['discord_id']):
                row_channel_clean = extract_discord_channel_id(str(row['discord_id']))

                if row_channel_clean == channel_id_clean:
                    if 'construflow_id' in row and pd.notna(row['construflow_id']):
                        logger.info(f"Canal {channel_id} mapeado para projeto construflow_id={row['construflow_id']}")
                        return str(row['construflow_id'])
        
        return None
    
    def get_project_by_code(self, project_code: str) -> Optional[str]:
        """
        Busca o ID do projeto (construflow_id) pelo código do projeto.
        
        Args:
            project_code: Código do projeto (ex: PRC_CREFAZ)
            
        Returns:
            ID do projeto (construflow_id) ou None se não encontrado
        """
        projects_df = self._load_project_config()
        
        if projects_df.empty:
            logger.warning("Planilha de configuração vazia")
            return None
        
        # Verificar colunas disponíveis
        available_columns = list(projects_df.columns)
        logger.debug(f"Colunas disponíveis na planilha: {', '.join(available_columns)}")
        
        # Tentar diferentes nomes de coluna para código do projeto
        code_column = None
        possible_code_columns = ['Código Projeto', 'codigo_projeto', 'project_code_norm', 'Código', 'codigo']
        
        for col in possible_code_columns:
            if col in projects_df.columns:
                code_column = col
                break
        
        if not code_column:
            logger.warning(f"Coluna de código do projeto não encontrada. Colunas disponíveis: {', '.join(available_columns)}")
            # Tentar buscar em todas as colunas de texto
            logger.info("Tentando buscar em todas as colunas de texto...")
            for col in projects_df.columns:
                if projects_df[col].dtype == 'object':  # Coluna de texto
                    matches = projects_df[projects_df[col].astype(str).str.upper().str.contains(project_code.upper(), na=False)]
                    if not matches.empty:
                        logger.info(f"Encontrado '{project_code}' na coluna '{col}'")
                        if 'construflow_id' in matches.columns:
                            construflow_id = matches['construflow_id'].values[0]
                            if pd.notna(construflow_id):
                                logger.info(f"Projeto '{project_code}' encontrado na coluna '{col}': construflow_id={construflow_id}")
                                return str(construflow_id)
            return None
        
        if 'construflow_id' not in projects_df.columns:
            logger.warning("Planilha não contém coluna 'construflow_id'")
            return None
        
        # Buscar projeto pelo código (case-insensitive)
        project_code_upper = project_code.upper()
        project_row = projects_df[projects_df[code_column].astype(str).str.upper() == project_code_upper]
        
        if project_row.empty:
            # Tentar busca parcial (contém)
            project_row = projects_df[projects_df[code_column].astype(str).str.upper().str.contains(project_code_upper, na=False)]
        
        # Se ainda não encontrou, tentar buscar pelo nome do projeto
        if project_row.empty and 'Projeto - PR' in projects_df.columns:
            logger.info(f"Tentando buscar '{project_code}' pelo nome do projeto...")
            project_row = projects_df[projects_df['Projeto - PR'].astype(str).str.upper().str.contains(project_code_upper, na=False)]
            if not project_row.empty:
                logger.info(f"Encontrado '{project_code}' no nome do projeto")
        
        # Se ainda não encontrou, tentar buscar em todas as colunas de texto
        if project_row.empty:
            logger.info(f"Tentando buscar '{project_code}' em todas as colunas de texto...")
            for col in projects_df.columns:
                if projects_df[col].dtype == 'object':  # Coluna de texto
                    matches = projects_df[projects_df[col].astype(str).str.upper().str.contains(project_code_upper, na=False)]
                    if not matches.empty:
                        logger.info(f"Encontrado '{project_code}' na coluna '{col}'")
                        project_row = matches
                        break
            
            if project_row.empty:
                # Listar alguns códigos disponíveis para ajudar no debug
                if len(projects_df) > 0:
                    sample_codes = projects_df[code_column].dropna().head(10).tolist()
                    logger.warning(f"Projeto com código '{project_code}' não encontrado na planilha")
                    logger.info(f"Alguns códigos disponíveis (primeiros 10): {sample_codes}")
                return None
        
        construflow_id = project_row['construflow_id'].values[0]
        
        if pd.isna(construflow_id):
            logger.warning(f"Projeto '{project_code}' encontrado mas sem construflow_id")
            return None
        
        logger.info(f"Projeto '{project_code}' encontrado: construflow_id={construflow_id}")
        return str(construflow_id)

    def filter_client_issues(self, df_issues: pd.DataFrame, project_id: str) -> pd.DataFrame:
        """
        Filtra issues do Construflow relacionadas às disciplinas do cliente.
        
        Args:
            df_issues: DataFrame com todas as issues do projeto
            project_id: ID do projeto
            
        Returns:
            DataFrame com issues filtradas pelas disciplinas do cliente
        """
        import re
        import unicodedata
        
        def normalize_text(text):
            """Normaliza texto removendo acentos, espaços extras e convertendo para lowercase."""
            if not text or pd.isna(text):
                return ""
            # Converter para string e remover espaços extras
            text = str(text).strip()
            # Normalizar unicode (NFD = decomposed form)
            text = unicodedata.normalize('NFD', text)
            # Remover acentos
            text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
            # Converter para lowercase e remover espaços múltiplos
            text = re.sub(r'\s+', ' ', text.lower().strip())
            return text
        
        # Obter disciplinas relacionadas ao cliente
        disciplinas_cliente = self.get_client_disciplines(project_id)
        
        if not disciplinas_cliente or 'name' not in df_issues.columns:
            logger.warning(f"Não foi possível filtrar issues para o cliente. Disciplinas: {disciplinas_cliente}")
            return df_issues
        
        # Normalizar disciplinas do cliente (remover acentos, espaços, case-insensitive)
        disciplinas_cliente_normalized = [normalize_text(d) for d in disciplinas_cliente if d and str(d).strip()]
        logger.info(f"Filtrando por disciplinas do cliente (originais): {disciplinas_cliente}")
        logger.info(f"Filtrando por disciplinas do cliente (normalizadas): {disciplinas_cliente_normalized}")
        
        # Verificar quais disciplinas únicas existem nas issues
        if not df_issues.empty and 'name' in df_issues.columns:
            disciplinas_issues = df_issues['name'].dropna().unique()
            disciplinas_issues_normalized = [normalize_text(d) for d in disciplinas_issues]
            logger.info(f"Disciplinas encontradas nas issues (originais): {list(disciplinas_issues)}")
            logger.info(f"Disciplinas encontradas nas issues (normalizadas): {disciplinas_issues_normalized}")
        
        # Filtrar pelas disciplinas do cliente (comparação normalizada com correspondência parcial)
        if df_issues['name'].dtype == 'object':
            # Normalizar nomes das issues para comparação
            df_issues_normalized = df_issues['name'].astype(str).apply(normalize_text)
            
            # Primeiro tentar correspondência exata
            mask = df_issues_normalized.isin(disciplinas_cliente_normalized)
            
            # Se não encontrou correspondência exata, tentar correspondência parcial (contém)
            if not mask.any() and disciplinas_cliente_normalized:
                logger.info(f"Tentando correspondência parcial para disciplinas do cliente...")
                # Criar máscara para cada disciplina do cliente
                partial_masks = []
                for disc_cliente in disciplinas_cliente_normalized:
                    if disc_cliente:  # Ignorar strings vazias
                        partial_mask = df_issues_normalized.str.contains(disc_cliente, case=False, na=False, regex=False)
                        partial_masks.append(partial_mask)
                        if partial_mask.any():
                            logger.info(f"  ✅ Encontrada correspondência parcial: '{disc_cliente}' em {partial_mask.sum()} issues")
                
                # Combinar todas as máscaras parciais
                if partial_masks:
                    mask = pd.concat(partial_masks, axis=1).any(axis=1)
        else:
            mask = df_issues['name'].isin(disciplinas_cliente)
        
        filtered_df = df_issues[mask]
        
        logger.info(f"Filtradas {len(filtered_df)} issues de cliente de um total de {len(df_issues)}")
        if len(filtered_df) == 0 and len(df_issues) > 0:
            logger.warning(f"⚠️ NENHUMA ISSUE FILTRADA! Verifique se os nomes das disciplinas na planilha correspondem aos nomes no Construflow")
            logger.warning(f"   Disciplinas configuradas: {disciplinas_cliente}")
            if 'name' in df_issues.columns:
                disciplinas_disponiveis = df_issues['name'].dropna().unique().tolist()
                logger.warning(f"   Disciplinas disponíveis nas issues: {disciplinas_disponiveis}")
        
        return filtered_df
    
    def get_project_discord_channel(self, project_id: str) -> Optional[str]:
        """
        Obtém o ID do canal do Discord para um projeto específico.
        
        Args:
            project_id: ID do projeto
            
        Returns:
            ID do canal do Discord ou None se não encontrado
        """
        projects_df = self._load_project_config()
        
        if projects_df.empty or 'construflow_id' not in projects_df.columns:
            logger.warning("Planilha de configuração não contém as colunas necessárias")
            return None
        
        # Verificar se a coluna discord_id existe
        if 'discord_id' not in projects_df.columns:
            logger.warning("Coluna discord_id não encontrada na planilha")
            return None
        
        # Filtrar projeto
        project_row = projects_df[projects_df['construflow_id'] == project_id]
        
        if project_row.empty or pd.isna(project_row['discord_id'].values[0]):
            logger.warning(f"Canal Discord não encontrado para projeto {project_id}")
            return None
        
        channel_id = project_row['discord_id'].values[0]
        logger.info(f"ID do canal Discord obtido: {channel_id}")
        return str(channel_id)
    
    def send_discord_notification(self, channel_id: str, message: str, max_retries: int = 3) -> bool:
        """
        Envia uma notificação do Discord com retry automático.
        
        Args:
            channel_id: ID do canal do Discord
            message: Mensagem a enviar
            max_retries: Número máximo de tentativas
        
        Returns:
            True se a notificação foi enviada com sucesso, False caso contrário
        """
        # Verificar se notificações estão desativadas
        if hasattr(self, 'disable_notifications') and self.disable_notifications:
            logger.info(f"Notificações desativadas. Mensagem para canal {channel_id} não enviada.")
            return False
        
        if not self.discord:
            logger.error("Gerenciador de Discord não inicializado")
            return False
            
        for attempt in range(max_retries):
            try:
                # Tenta sem e com o prefixo "Bot " alternadamente
                if attempt % 2 == 1 and self.discord.discord_token and not self.discord.discord_token.startswith("Bot "):
                    # Temporariamente adiciona o prefixo "Bot " ao token
                    original_token = self.discord.discord_token
                    self.discord.discord_token = f"Bot {original_token}"
                    result = self.discord.send_notification(channel_id, message)
                    self.discord.discord_token = original_token  # Restaura o token original
                else:
                    result = self.discord.send_notification(channel_id, message)
                
                if result:
                    logger.info(f"Notificação enviada para canal {channel_id} com sucesso")
                    return True
                else:
                    logger.warning(f"Tentativa {attempt+1}/{max_retries} falhou")
                    time.sleep(1 * (attempt + 1))  # Backoff exponencial
                    
            except Exception as e:
                logger.error(f"Erro ao enviar notificação: {str(e)}")
                time.sleep(1 * (attempt + 1))
        
        logger.error(f"Todas as {max_retries} tentativas falharam ao enviar notificação")
        return False
    
    def _update_project_cache(self, project_id: str) -> bool:
        """
        Atualiza o cache para um projeto específico usando queries GraphQL otimizadas.
        Atualiza apenas o projeto solicitado, sem atualizar todos os projetos ativos.
        Também atualiza o cache do SmartSheet para garantir dados mais recentes.
        
        Args:
            project_id: ID do projeto
        
        Returns:
            True se a atualização foi bem-sucedida, False caso contrário
        """
        try:
            logger.info(f"🚀 Atualizando cache otimizado apenas para o projeto {project_id} via GraphQL consolidado")
            
            # Verificar se o cache manager está disponível
            if not self.cache_manager:
                logger.error("Cache manager não inicializado")
                return False
            
            cache = self.cache_manager
            
            # Usar apenas o conector GraphQL otimizado para o projeto solicitado
            if hasattr(self.processor.construflow, 'get_project_data_optimized'):
                logger.info("🎯 Usando query consolidada GraphQL para otimização máxima (apenas 1 projeto)")
                consolidated_data = self.processor.construflow.get_project_data_optimized(project_id)
                
                if consolidated_data:
                    if 'projects' in consolidated_data and hasattr(cache, 'save_construflow_data'):
                        projects_data = consolidated_data['projects'].to_dict('records')
                        cache.save_construflow_data("projects", projects_data)
                        logger.info(f"✅ {len(projects_data)} projetos salvos via GraphQL consolidado")
                    if 'disciplines' in consolidated_data and hasattr(cache, 'save_construflow_data'):
                        disciplines_data = consolidated_data['disciplines'].to_dict('records')
                        cache.save_construflow_data("disciplines", disciplines_data)
                        logger.info(f"✅ {len(disciplines_data)} disciplinas salvas via GraphQL consolidado")
                    if 'issues' in consolidated_data and hasattr(cache, 'save_construflow_data'):
                        issues_data = consolidated_data['issues'].to_dict('records')
                        cache.save_construflow_data("issues", issues_data)
                        logger.info(f"✅ {len(issues_data)} issues salvas via GraphQL consolidado")
                        try:
                            project_issues = consolidated_data['issues'][consolidated_data['issues']['projectId'] == str(project_id)]
                            logger.info(f"🎯 {len(project_issues)} issues específicas do projeto {project_id} obtidas via GraphQL")
                        except Exception as e:
                            logger.warning(f"Erro ao analisar issues para o projeto {project_id}: {e}")
                    if 'issue_disciplines' in consolidated_data and hasattr(cache, 'save_construflow_data'):
                        issue_disciplines_data = consolidated_data['issue_disciplines'].to_dict('records')
                        cache.save_construflow_data("issues-disciplines", issue_disciplines_data)
                        logger.info(f"✅ {len(issue_disciplines_data)} relacionamentos issue-discipline salvos via GraphQL consolidado")
                    
                    # Atualizar também o cache do SmartSheet para garantir dados mais recentes
                    smartsheet_id = self.get_project_smartsheet_id(project_id)
                    if smartsheet_id:
                        logger.info(f"Atualizando cache do SmartSheet {smartsheet_id} para projeto {project_id}")
                        try:
                            sheet_data = self.processor.smartsheet.get_sheet(smartsheet_id, force_refresh=True)
                            if sheet_data and hasattr(cache, 'save_smartsheet_data'):
                                cache.save_smartsheet_data(smartsheet_id, project_id, sheet_data)
                                logger.info(f"✅ Cache do SmartSheet atualizado para projeto {project_id}")
                        except Exception as e:
                            logger.warning(f"Erro ao atualizar cache do SmartSheet para projeto {project_id}: {e}")
                    
                    logger.info(f"🚀 Cache otimizado concluído para projeto {project_id} - 1 query GraphQL")
                    return True
                else:
                    logger.warning("Query consolidada GraphQL retornou dados vazios para o projeto solicitado")
            else:
                logger.error("Conector GraphQL otimizado não disponível. Não foi possível atualizar apenas o projeto solicitado.")
                return False
        except Exception as e:
            logger.error(f"Erro ao atualizar cache do projeto {project_id}: {e}")
            return False

    def _format_final_success_message(self, project_name, doc_url, folder_url=None):
        """
        Formata uma mensagem de sucesso atraente para envio via Discord.
        
        Args:
            project_name: Nome do projeto
            doc_url: URL do documento gerado
            folder_url: URL da pasta do projeto (opcional)
            
        Returns:
            Mensagem formatada
        """
        message = [
            f"🎉 **Relatório Semanal Concluído!**",
            f"",
            f"📋 **Projeto:** {project_name}",
            f"",
            f"📄 [Abrir Relatório]({doc_url})"
        ]
        
        if folder_url:
            message.append(f"📁 [Abrir Pasta do Projeto]({folder_url})")
        
        message.extend([
            "",
            "✅ O relatório foi gerado com sucesso e está pronto para ser compartilhado.",
            "🔄 Para gerar um novo relatório, use o comando `!relatorio` neste canal."
        ])
        
        return "\n".join(message)

    def log_execution_to_sheet(self, project_id, project_name, status, message, doc_url=None):
        """
        Registra um log de execução na planilha do Google Sheets via API.
        """
        import logging
        logging.debug(f"Início do log_execution_to_sheet para {project_id} ({project_name}) com status={status}")
        logging.info(f"Chamando log_execution_to_sheet para {project_id} ({project_name})")
        try:
            from googleapiclient.discovery import build
            from datetime import datetime
            LOG_SHEET_ID = self.config.get_weekly_report_control_sheet_id()
            LOG_SHEET_NAME = 'Log'  # ou 'Sheet1', conforme sua planilha
            creds = self.config.get_google_creds()
            if not creds:
                logging.error("Credenciais do Google não disponíveis para log de execução.")
                return False
            sheets_service = build('sheets', 'v4', credentials=creds)
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            row = [now, str(project_id), str(project_name), status, message, doc_url or ""]
            range_ = f"{LOG_SHEET_NAME}!A1"
            body = {"values": [row]}
            sheets_service.spreadsheets().values().append(
                spreadsheetId=LOG_SHEET_ID,
                range=range_,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            logging.info(f"Log registrado na planilha para projeto {project_id} ({status})")
            return True
        except Exception as e:
            logging.error(f"Erro ao registrar log de execução na planilha: {e}")
            return False

    def run_for_project(self, project_id, quiet_mode=False, skip_cache_update=False, skip_notifications=False, hide_dashboard=False, schedule_days=None, reference_date=None, since_date=None) -> Tuple[bool, str, Optional[str]]:
        """
        Executa o processo completo para um projeto, atualizando o cache primeiro.
        
        Args:
            project_id: ID do projeto
            quiet_mode: Se deve operar em modo silencioso
            skip_cache_update: Se True, pula a atualização do cache (use quando já foi atualizado)
            skip_notifications: Se True, não envia notificações para o Discord
            hide_dashboard: Se True, não exibe o botão do Dashboard no relatório HTML
            schedule_days: Número de dias para o cronograma (None = padrão de 15 dias)
            
        Returns:
            Tupla com (sucesso, caminho_arquivo, id_drive)
        """
        self.quiet_mode = quiet_mode
        status = None
        mensagem = None
        doc_url = None
        try:
            # Verificar se o projeto está ativo (mas permitir forçar execução se necessário)
            projects_df = self._load_project_config()
            if 'relatoriosemanal_status' in projects_df.columns:
                project_row = projects_df[projects_df['construflow_id'].astype(str) == str(project_id)]
                if not project_row.empty and 'relatoriosemanal_status' in project_row.columns:
                    ativo = str(project_row['relatoriosemanal_status'].values[0]).lower()
                    if ativo != 'sim':
                        logger.warning(f"Projeto {project_id} não está ativo (relatoriosemanal_status={ativo}). Pulando.")
                        # Se estiver em modo quiet ou forçado, ainda assim executar
                        if not quiet_mode:
                            return False, "", None
                        else:
                            logger.info(f"Executando mesmo com status '{ativo}' (modo forçado)")

            # Obter canal Discord e nome do projeto
            discord_channel_id = self.get_project_discord_channel(project_id)
            project_name = "Projeto"  # Valor padrão
            codigo_projeto = None
            
            # Obter nome mais amigável do projeto e Código Projeto se possível
            projects_df = self._load_project_config()
            if not projects_df.empty and 'construflow_id' in projects_df.columns:
                project_row = projects_df[projects_df['construflow_id'] == project_id]
                if not project_row.empty:
                    if 'Projeto - PR' in project_row.columns:
                        project_name = project_row['Projeto - PR'].values[0]
                    if 'Código Projeto' in project_row.columns:
                        codigo_projeto = project_row['Código Projeto'].values[0]
            
            # Inicializar reporter de progresso somente se NÃO estiver em modo silencioso
            progress_reporter = None
            if discord_channel_id and not quiet_mode:
                try:
                    from report_system.utils.progress_reporter import ProgressReporter
                    progress_reporter = ProgressReporter(
                        channel_id=discord_channel_id,
                        project_name=project_name,
                        send_message_func=self.send_discord_notification
                    )
                    progress_reporter.start()
                except ImportError:
                    logger.warning("Módulo progress_reporter não encontrado. Continuando sem atualizações de progresso.")
            
            try:
                # Buscar o ID do Smartsheet para este projeto (independente de atualização de cache)
                smartsheet_id = self.get_project_smartsheet_id(project_id)
                
                if not skip_cache_update:
                    # Verificar se o cache é recente antes de atualizar (otimização de performance)
                    cache_valid = False
                    if self.cache_manager:
                        # Verificar se o cache de issues é válido (menos de 1 hora)
                        cache_valid = self.cache_manager.is_cache_valid("issues", max_age_hours=1, data_type='construflow')
                        if cache_valid:
                            logger.info(f"✅ Cache válido encontrado para o projeto {project_id} (menos de 1 hora). Usando cache existente.")
                        else:
                            logger.info(f"⏳ Cache expirado ou não encontrado para o projeto {project_id}. Atualizando...")
                    
                    if not cache_valid:
                        # Atualizar o cache para este projeto específico apenas se necessário
                        logger.info(f"Atualizando cache para o projeto {project_id} antes de gerar relatório")
        
                        if progress_reporter:
                            progress_reporter.update("Atualização de cache", "Obtendo dados mais recentes...")      
                        self._update_project_cache(project_id)
                    else:
                        if progress_reporter:
                            progress_reporter.update("Carregando dados", "Usando cache recente...")
                else:
                    logger.info(f"Pulando atualização de cache para o projeto {project_id} (já atualizado)")
                
                if progress_reporter:
                    progress_reporter.update("Processamento de dados", "Analisando informações do projeto...")
                    
                # Verificar se temos um ID de Smartsheet válido
                if not smartsheet_id:
                    logger.warning(f"ID do Smartsheet não encontrado para o projeto {project_id}. Alguns dados podem estar incompletos.")
                    smartsheet_id = None  # Garantir que é None e não outro valor que represente "falso"
                
                # Chamar process_project_data com proteção adicional
                project_data = None
                try:
                    project_data = self.processor.process_project_data(project_id, smartsheet_id, reference_date=reference_date, since_date=since_date)
                except Exception as e:
                    logger.error(f"Erro ao processar dados do projeto {project_id}: {e}")
                    
                    # Se o erro foi causado por dados do Smartsheet, tentar novamente sem usar Smartsheet
                    if smartsheet_id is not None:
                        logger.info(f"Tentando processar projeto {project_id} novamente sem usar dados do Smartsheet")
                        try:
                            project_data = self.processor.process_project_data(project_id, None, reference_date=reference_date, since_date=since_date)
                        except Exception as e2:
                            logger.error(f"Erro ao processar projeto {project_id} sem Smartsheet: {e2}")
                            project_data = None
                    else:
                        # Se já estamos tentando sem Smartsheet, manter project_data como None
                        project_data = None
                
                # Validar project_data antes de continuar
                if not project_data or not isinstance(project_data, dict) or not project_data.get('project_name'):
                    logger.error(f"Projeto {project_id} não encontrado ou sem dados")
                    
                    # Verificar se é falta de dados do Construflow especificamente
                    construflow_data_missing = False
                    if isinstance(project_data, dict):
                        construflow_data = project_data.get('construflow_data')
                        if construflow_data is None:
                            construflow_data_missing = True
                            logger.warning(f"Projeto {project_id} não tem dados do Construflow")
                    
                    # Notificar no Discord sobre falta de dados do Construflow
                    if not skip_notifications and construflow_data_missing:
                        try:
                            self._check_and_notify_no_issues(project_data, project_id, project_name)
                        except Exception as notify_error:
                            logger.error(f"Erro ao enviar notificação sobre falta de dados do Construflow: {notify_error}")
                    
                    if progress_reporter:
                        if ERROR_MESSAGES_AVAILABLE:
                            detail = "os dados do cronograma" if construflow_data_missing else None
                            error_msg = ErrorMessages.get_user_message(
                                category=ErrorCategory.NOT_FOUND,
                                project_name=project_name,
                                details=detail
                            )
                        else:
                            error_msg = f"❌ **Erro:** Não foi possível encontrar dados para o projeto {project_name}."
                            if construflow_data_missing:
                                error_msg += "\n\n⚠️ **Dados do cronograma não disponíveis.**"
                        progress_reporter.complete(
                            success=False,
                            final_message=error_msg
                        )
                    # Log de falha
                    self.log_execution_to_sheet(
                        project_id=codigo_projeto or project_id,
                        project_name=project_name,
                        status="Falha",
                        message="Não foi possível encontrar dados para o projeto." + (" Dados do Construflow não disponíveis." if construflow_data_missing else ""),
                        doc_url=None
                    )
                    return False, "", None
                
                # Atualizar o nome do projeto se necessário
                if project_name == "Projeto" and project_data.get('project_name'):
                    project_name = project_data['project_name']
                
                # Gerar relatório
                if progress_reporter:
                    progress_reporter.update("Geração de relatório", "Criando conteúdo do relatório...")
                
                # Validar project_data antes de gerar relatório
                if not project_data or not isinstance(project_data, dict):
                    logger.error(f"project_data é inválido antes de gerar relatório para projeto {project_id}")
                    raise ValueError(f"Dados do projeto {project_id} são inválidos")
                
                # Gerar relatório HTML primeiro
                if progress_reporter:
                    progress_reporter.update("Geração de relatório HTML", "Criando relatórios HTML para e-mail...")
                
                # Obter URLs do cronograma, relatório de disciplinas e imagem da planilha
                # IMPORTANTE: Forçar refresh para garantir URLs e imagem atualizadas
                email_url_gant = None
                email_url_disciplina = None
                project_image_base64 = None
                try:
                    projects_df = self._load_project_config(force_refresh=True)
                    if not projects_df.empty and 'construflow_id' in projects_df.columns:
                        project_row = projects_df[projects_df['construflow_id'].astype(str) == str(project_id)]
                        if not project_row.empty:
                            email_url_gant = self._extract_column_value(project_row, 'email_url_gant')
                            email_url_disciplina = self._extract_column_value(project_row, 'email_url_disciplina')
                            image_url = self._extract_column_value(project_row, 'email_url_capa')

                            if image_url:
                                project_image_base64 = self._download_project_image(image_url, project_id, project_name)
                except Exception as e:
                    logger.warning(f"Erro ao obter URLs e imagem do projeto: {e}")
                
                # Gerar e salvar relatórios HTML
                html_paths = self.html_generator.save_reports(
                    data=project_data,
                    project_name=project_data['project_name'],
                    project_id=project_id,
                    project_image_base64=project_image_base64,
                    email_url_gant=email_url_gant,
                    email_url_disciplina=email_url_disciplina,
                    show_dashboard_button=not hide_dashboard,
                    schedule_days=schedule_days
                )
                
                logger.info(f"Relatórios HTML gerados: {html_paths}")

                # Verificar se o relatório do cliente foi gerado (obrigatório)
                if not html_paths or not html_paths.get('client'):
                    logger.error(f"Erro ao gerar relatório do CLIENTE para projeto {project_id}")

                    if ERROR_MESSAGES_AVAILABLE:
                        error_message = ErrorMessages.get_user_message(
                            category=ErrorCategory.SYSTEM,
                            project_name=project_name,
                            details="Falha ao criar o documento do relatório"
                        )
                    else:
                        error_message = f"❌ **Erro:** Falha ao gerar o relatório do cliente para {project_name}."

                    if progress_reporter:
                        progress_reporter.complete(success=False, final_message=error_message)
                    elif discord_channel_id and not skip_notifications:
                        self.send_discord_notification(discord_channel_id, error_message)

                    self.log_execution_to_sheet(
                        project_id=codigo_projeto or project_id,
                        project_name=project_name,
                        status="Falha",
                        message="Falha ao gerar o relatório do cliente.",
                        doc_url=None
                    )
                    return False, "", None

                # Verificar se o relatório da equipe foi gerado (opcional, apenas aviso)
                if not html_paths.get('team'):
                    logger.warning(f"⚠️ Relatório da EQUIPE não foi gerado para projeto {project_id} ({project_name})")
                    if discord_channel_id and not skip_notifications:
                        if ERROR_MESSAGES_AVAILABLE:
                            warning_message = ErrorMessages.partial_success_message(
                                project_name=project_name,
                                generated="do Cliente",
                                failed="da Equipe",
                                reason="Dados insuficientes para gerar o relatório da equipe"
                            )
                        else:
                            warning_message = f"⚠️ **Aviso:** Relatório da equipe não foi gerado para {project_name}."
                        self.send_discord_notification(discord_channel_id, warning_message)
                
                # Verificar se o projeto tem apontamentos e notificar se não tiver
                if not skip_notifications:
                    self._check_and_notify_no_issues(project_data, project_id, project_name)
                
                # Usar o caminho do relatório do cliente como file_path principal
                file_path = html_paths.get('client', '')
                
                # Obter a pasta específica do projeto a partir da planilha de configuração
                if progress_reporter:
                    progress_reporter.update("Upload dos relatórios", "Enviando relatórios HTML para o Google Drive...")
                    
                project_folder_id = self.gdrive.get_project_folder(
                    project_id, 
                    project_data['project_name']
                )
                
                # Fazer upload dos arquivos HTML para o Google Drive em paralelo
                uploaded_files = {}
                client_file_id = None  # Inicializar variável
                if project_folder_id:
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    
                    # Funções para upload em paralelo
                    def upload_client_report():
                        """Upload do relatório do cliente."""
                        if html_paths.get('client'):
                            try:
                                result = self.gdrive.upload_file(
                                    file_path=html_paths['client'],
                                    name=f"Email_cliente_{project_data['project_name']}_{today_str}.html",
                                    parent_id=project_folder_id
                                )
                                return ('client', result)
                            except Exception as e:
                                logger.error(f"Erro ao enviar relatório do cliente para o Drive: {e}")
                                return ('client', None)
                        return ('client', None)
                    
                    def upload_team_report():
                        """Upload do relatório da equipe."""
                        if html_paths.get('team'):
                            try:
                                result = self.gdrive.upload_file(
                                    file_path=html_paths['team'],
                                    name=f"Email_time_{project_data['project_name']}_{today_str}.html",
                                    parent_id=project_folder_id
                                )
                                return ('team', result)
                            except Exception as e:
                                logger.error(f"Erro ao enviar relatório da equipe para o Drive: {e}")
                                return ('team', None)
                        return ('team', None)
                    
                    # Executar uploads SEQUENCIALMENTE para evitar race conditions
                    logger.info("🚀 Iniciando upload dos relatórios para o Google Drive...")

                    # Upload do relatório do cliente primeiro
                    if html_paths.get('client'):
                        logger.info(f"📤 Enviando relatório do CLIENTE: {html_paths['client']}")
                        try:
                            report_type, result = upload_client_report()
                            if result:
                                if isinstance(result, dict):
                                    uploaded_files['client'] = result.get('webViewLink', f"https://drive.google.com/file/d/{result.get('id')}/view")
                                    client_file_id = result.get('id')
                                else:
                                    uploaded_files['client'] = f"https://drive.google.com/file/d/{result}/view"
                                    client_file_id = result
                                logger.info(f"✅ Relatório do CLIENTE enviado para o Drive: {client_file_id}")
                            else:
                                logger.error(f"❌ Upload do relatório do CLIENTE retornou None/vazio")
                        except Exception as e:
                            logger.error(f"❌ Erro ao fazer upload do relatório do CLIENTE: {e}", exc_info=True)
                    else:
                        logger.warning(f"⚠️ Caminho do relatório do cliente não encontrado em html_paths")

                    # Upload do relatório da equipe
                    if html_paths.get('team'):
                        logger.info(f"📤 Enviando relatório da EQUIPE: {html_paths['team']}")
                        try:
                            report_type, result = upload_team_report()
                            if result:
                                if isinstance(result, dict):
                                    uploaded_files['team'] = result.get('webViewLink', f"https://drive.google.com/file/d/{result.get('id')}/view")
                                    team_file_id = result.get('id')
                                else:
                                    uploaded_files['team'] = f"https://drive.google.com/file/d/{result}/view"
                                    team_file_id = result
                                logger.info(f"✅ Relatório da EQUIPE enviado para o Drive: {team_file_id}")
                            else:
                                logger.error(f"❌ Upload do relatório da EQUIPE retornou None/vazio")
                        except Exception as e:
                            logger.error(f"❌ Erro ao fazer upload do relatório da EQUIPE: {e}", exc_info=True)
                    else:
                        logger.warning(f"⚠️ Caminho do relatório da equipe não encontrado em html_paths")
                else:
                    logger.warning(f"ID da pasta do Drive não encontrado para projeto {project_id}")
                
                # Preparar mensagem final - formato limpo e conciso
                folder_url = f"https://drive.google.com/drive/folders/{project_folder_id}" if project_folder_id else None

                if folder_url:
                    final_message = f"✅ **Relatório de {project_name} gerado com sucesso!**\n\n📁 [Abrir Pasta do Projeto]({folder_url})"
                else:
                    # Fallback caso não tenha pasta (raro)
                    final_message = f"✅ **Relatório de {project_name} gerado com sucesso!**"
                    if uploaded_files.get('client'):
                        final_message += f"\n\n📄 [Abrir Relatório]({uploaded_files['client']})"
                
                # Enviar notificação
                if progress_reporter:
                    progress_reporter.complete(success=True, final_message=final_message)
                elif discord_channel_id and not skip_notifications:
                    self.send_discord_notification(discord_channel_id, final_message)
                
                # Log de sucesso
                self.log_execution_to_sheet(
                    project_id=codigo_projeto or project_id,
                    project_name=project_name,
                    status="Sucesso",
                    message="Relatórios HTML gerados e enviados para o Google Drive com sucesso.",
                    doc_url=uploaded_files.get('client') if uploaded_files else None
                )
                
                # Retornar o link completo do arquivo HTML do cliente no terceiro elemento
                # para que o report_queue possa capturar o URL
                drive_file_url = None
                if uploaded_files.get('client'):
                    # Usar o link completo do arquivo no Drive
                    drive_file_url = uploaded_files['client']
                elif client_file_id:
                    # Se não temos o link completo mas temos o ID, construir o link
                    drive_file_url = f"https://drive.google.com/file/d/{client_file_id}/view"
                
                return True, file_path, drive_file_url
                    
            except Exception as e:
                logger.error(f"Erro ao processar projeto {project_id}: {str(e)}", exc_info=True)

                if progress_reporter:
                    if ERROR_MESSAGES_AVAILABLE:
                        error_category = classify_error(e)
                        error_message = ErrorMessages.get_user_message(
                            category=error_category,
                            project_name=project_name
                        )
                    else:
                        error_message = f"❌ **Erro ao gerar relatório para {project_name}**\n\nOcorreu um erro inesperado. Por favor, tente novamente em alguns minutos."

                    progress_reporter.complete(success=False, final_message=error_message)

                # Log de falha
                self.log_execution_to_sheet(
                    project_id=codigo_projeto or project_id,
                    project_name=project_name,
                    status="Falha",
                    message=f"Erro ao gerar relatório: {str(e)[:200]}",
                    doc_url=None
                )

                return False, "", None
        except Exception as e:
            logger.error(f"Erro ao processar projeto {project_id}: {str(e)}", exc_info=True)

            if progress_reporter:
                if ERROR_MESSAGES_AVAILABLE:
                    error_category = classify_error(e)
                    error_message = ErrorMessages.get_user_message(
                        category=error_category,
                        project_name=project_name if 'project_name' in locals() else str(project_id)
                    )
                else:
                    error_message = f"❌ **Erro ao gerar relatório**\n\nOcorreu um erro inesperado. Por favor, tente novamente."

                progress_reporter.complete(success=False, final_message=error_message)

            # Log de falha
            self.log_execution_to_sheet(
                project_id=codigo_projeto or project_id,
                project_name=project_name if 'project_name' in locals() else str(project_id),
                status="Falha",
                message=f"Erro ao gerar relatório: {str(e)[:200]}",
                doc_url=None
            )

            return False, "", None
        finally:
            import logging
            logging.debug(f"Entrou no finally do run_for_project para {project_id}")
            if status is not None:
                logging.debug(f"Chamando log_execution_to_sheet no finally para {project_id} com status={status}")
                self.log_execution_to_sheet(
                    project_id=codigo_projeto or project_id,
                    project_name=project_name if 'project_name' in locals() else str(project_id),
                    status=status,
                    message=mensagem,
                    doc_url=doc_url
                )
            else:
                logging.debug(f"status é None no finally do run_for_project para {project_id}")

    def create_google_doc_with_links(self, docs_service, drive_service, title, project_data, parent_folder_id=None):
        """
        Cria um documento Google Docs com links funcionais para os apontamentos.
        
        Versão simplificada que processa apenas os links de apontamentos no formato #XXXX,
        sem tentar formatar os cabeçalhos Markdown.
        
        Args:
            docs_service: Serviço Google Docs
            drive_service: Serviço Google Drive
            title: Título do documento
            project_data: Dados do projeto
            parent_folder_id: ID da pasta onde salvar o documento (opcional)
            
        Returns:
            ID do documento criado no Google Docs
        """
        # 1. Criar documento vazio
        doc_body = {'title': title}

        # Função auxiliar para fazer requisições com retry e backoff
        def execute_with_retry(request, max_retries=5):
            for retry in range(max_retries):
                try:
                    return request.execute()
                except googleapiclient.errors.HttpError as e:
                    if e.resp.status == 429 or e.resp.status in [500, 503]:  
                        wait_time = 60  # Wait for 1 minute
                        logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry.")
                        time.sleep(wait_time)
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error executing request: {e}")
                    raise

            raise Exception(f"Failed after {max_retries} attempts")

        # Criar documento com retry
        try:
            doc = execute_with_retry(docs_service.documents().create(body=doc_body))
            document_id = doc.get('documentId')
        except Exception as e:
            logger.error(f"Erro ao criar documento: {e}")
            return None
        
        # 2. Mover para a pasta correta, se especificada
        if parent_folder_id:
            try:
                drive_service.files().update(
                    fileId=document_id,
                    addParents=parent_folder_id,
                    fields='id, parents',
                    supportsAllDrives=True
                ).execute()
            except Exception as e:
                logger.warning(f"Erro ao mover documento para pasta: {e}")
        
        # 3. Gerar relatório com os links já construídos corretamente
        original_report = self.generator.generate_report(project_data)
        
        # 4. Extrair os links do formato markdown e substituir por texto simples com os mesmos links
        import re
        
        # Função para substituir os links em formato markdown por texto simples
        def replace_markdown_links(text):
            """Substitui links no formato [#XXXX](URL) por #XXXX sem mostrar a URL"""
            
            def replace_func(match):
                link_text = match.group(1)
                url = match.group(2)
                # Armazenar o par código-URL para processamento posterior
                if link_text.startswith('#'):
                    code = link_text[1:]  # Remover o '#' para obter apenas o número
                    links_info.append({
                        'code': code,
                        'url': url
                    })
                return link_text  # Retornar apenas o texto do link, sem a URL
                
            links_info = []
            # Substituir todos os links markdown [texto](url) por apenas o texto
            modified_text = re.sub(r'\[(.*?)\]\((.*?)\)', replace_func, text)
            
            return modified_text, links_info
        
        # Processar o relatório para remover as URLs visíveis
        clean_report, links_info = replace_markdown_links(original_report)
        
        # 5. Inserir o texto limpo no documento
        try:
            execute_with_retry(
                docs_service.documents().batchUpdate(
                    documentId=document_id,
                    body={
                        'requests': [{
                            'insertText': {
                                'location': {'index': 1},
                                'text': clean_report
                            }
                        }]
                    }
                )
            )
        except Exception as e:
            logger.error(f"Erro ao inserir texto no documento: {e}")
            return document_id  # Retornar o ID mesmo assim, para que o usuário possa acessar o documento incompleto
        
        # 6. Obter o documento para encontrar as posições dos códigos
        try:
            search_response = execute_with_retry(
                docs_service.documents().get(documentId=document_id)
            )
            content = search_response.get('body', {}).get('content', [])
        except Exception as e:
            logger.error(f"Erro ao obter conteúdo do documento: {e}")
            return document_id
        
        # 7. Criar solicitações para adicionar links
        link_requests = []
        
        # Processar cada código de apontamento
        for link_info in links_info:
            code = link_info['code']
            url = link_info['url']
            search_text = f"#{code}"
            
            # Procurar todas as ocorrências do código no documento
            for item in content:
                if 'paragraph' in item:
                    paragraph = item.get('paragraph', {})
                    elements = paragraph.get('elements', [])
                    
                    for element in elements:
                        text_run = element.get('textRun', {})
                        content_text = text_run.get('content', '')
                        
                        if search_text in content_text:
                            # Encontrar a posição exata do código no texto
                            local_start = content_text.find(search_text)
                            start_index = element.get('startIndex', 0) + local_start
                            end_index = start_index + len(search_text)
                            
                            # Aplicar negrito ao código do apontamento
                            link_requests.append({
                                'updateTextStyle': {
                                    'range': {
                                        'startIndex': start_index,
                                        'endIndex': end_index
                                    },
                                    'textStyle': {
                                        'bold': True
                                    },
                                    'fields': 'bold'
                                }
                            })
                            
                            # Adicionar o link usando a URL
                            link_requests.append({
                                'updateTextStyle': {
                                    'range': {
                                        'startIndex': start_index,
                                        'endIndex': end_index
                                    },
                                    'textStyle': {
                                        'link': {'url': url}
                                    },
                                    'fields': 'link'
                                }
                            })
        
        # 8. Aplicar os links em lotes
        if link_requests:
            batch_size = 20  # Limitar o tamanho dos lotes para evitar erros
            for i in range(0, len(link_requests), batch_size):
                batch = link_requests[i:i+batch_size]
                
                try:
                    execute_with_retry(
                        docs_service.documents().batchUpdate(
                            documentId=document_id,
                            body={'requests': batch}
                        )
                    )
                    # Adicionar uma pausa entre lotes
                    if i + batch_size < len(link_requests):
                        time.sleep(1)  # Pausa de 1 segundo entre lotes
                except Exception as e:
                    logger.error(f"Erro ao processar lote de links {i//batch_size + 1}: {e}")
                    # Continuar com o próximo lote mesmo em caso de erro
        
        logger.info(f"Documento criado com sucesso: {document_id}")
        return document_id

    def update_all_cache(self, projects):
        """
        Atualiza o cache para todos os projetos de uma vez usando queries GraphQL otimizadas.
        Versão ultra-otimizada que usa queries paralelas por projeto em vez de carregar todas as issues.
        
        Args:
            projects: Lista de dicionários com dados dos projetos
        
        Returns:
            True se a atualização foi bem-sucedida, False caso contrário
        """
        logger.info(f"🚀 Iniciando atualização centralizada ULTRA-OTIMIZADA para {len(projects)} projetos via GraphQL")
        
        try:
            # Registrar a hora da última atualização
            self.last_cache_update = datetime.now()
            
            # Salvar em um arquivo para persistir entre execuções
            cache_timestamp_file = os.path.join(self.config.cache_dir, "last_update.txt")
            with open(cache_timestamp_file, 'w') as f:
                f.write(self.last_cache_update.isoformat())

            # Verificar se estamos usando o conector GraphQL otimizado
            if hasattr(self.processor.construflow, 'get_multiple_projects_data_optimized'):
                logger.info("🎯 Usando queries paralelas GraphQL para otimização máxima")
                
                # Extrair IDs dos projetos
                project_ids = [str(project['id']) for project in projects if 'id' in project]
                
                if project_ids:
                    logger.info(f"🎯 Processando {len(project_ids)} projetos com queries paralelas")
                    
                    # Obter dados usando queries paralelas otimizadas
                    consolidated_data = self.processor.construflow.get_multiple_projects_data_optimized(project_ids)
                    
                    if consolidated_data:
                        # Salvar cada tipo de dados no cache
                        if 'projects' in consolidated_data and hasattr(self.cache_manager, 'save_construflow_data'):
                            projects_data = consolidated_data['projects'].to_dict('records')
                            self.cache_manager.save_construflow_data("projects", projects_data)
                            logger.info(f"✅ {len(projects_data)} projetos salvos via queries paralelas")
                        
                        if 'disciplines' in consolidated_data and hasattr(self.cache_manager, 'save_construflow_data'):
                            disciplines_data = consolidated_data['disciplines'].to_dict('records')
                            self.cache_manager.save_construflow_data("disciplines", disciplines_data)
                            logger.info(f"✅ {len(disciplines_data)} disciplinas salvas via GraphQL")
                        
                        if 'issues' in consolidated_data and hasattr(self.cache_manager, 'save_construflow_data'):
                            issues_data = consolidated_data['issues'].to_dict('records')
                            self.cache_manager.save_construflow_data("issues", issues_data)
                            logger.info(f"🎯 {len(issues_data)} issues de {len(project_ids)} projetos salvas via queries paralelas")
                        
                        if 'issue_disciplines' in consolidated_data and hasattr(self.cache_manager, 'save_construflow_data'):
                            issue_disciplines_data = consolidated_data['issue_disciplines'].to_dict('records')
                            self.cache_manager.save_construflow_data("issues-disciplines", issue_disciplines_data)
                            logger.info(f"✅ {len(issue_disciplines_data)} relacionamentos issue-discipline salvos")
                        
                        logger.info(f"🚀 Cache ULTRA-OTIMIZADO concluído: queries paralelas vs carregar todas as issues")
                        return True
                    else:
                        logger.warning("Queries paralelas retornaram dados vazios, tentando método consolidado")
                else:
                    logger.warning("Nenhum ID de projeto encontrado, tentando método consolidado")
            
            # Fallback para método consolidado
            if hasattr(self.processor.construflow, 'get_all_data_optimized'):
                logger.info("🎯 Usando query consolidada GraphQL como fallback")
                
                # Obter todos os dados em uma única query GraphQL
                consolidated_data = self.processor.construflow.get_all_data_optimized()
                
                if consolidated_data:
                    # Salvar cada tipo de dados no cache
                    if 'projects' in consolidated_data and hasattr(self.cache_manager, 'save_construflow_data'):
                        projects_data = consolidated_data['projects'].to_dict('records')
                        self.cache_manager.save_construflow_data("projects", projects_data)
                        logger.info(f"✅ {len(projects_data)} projetos salvos via GraphQL consolidado")
                    
                    if 'disciplines' in consolidated_data and hasattr(self.cache_manager, 'save_construflow_data'):
                        disciplines_data = consolidated_data['disciplines'].to_dict('records')
                        self.cache_manager.save_construflow_data("disciplines", disciplines_data)
                        logger.info(f"✅ {len(disciplines_data)} disciplinas salvas via GraphQL consolidado")
                    
                    if 'issues' in consolidated_data and hasattr(self.cache_manager, 'save_construflow_data'):
                        issues_data = consolidated_data['issues'].to_dict('records')
                        self.cache_manager.save_construflow_data("issues", issues_data)
                        logger.info(f"✅ {len(issues_data)} issues salvas via GraphQL consolidado")
                    
                    if 'issue_disciplines' in consolidated_data and hasattr(self.cache_manager, 'save_construflow_data'):
                        issue_disciplines_data = consolidated_data['issue_disciplines'].to_dict('records')
                        self.cache_manager.save_construflow_data("issues-disciplines", issue_disciplines_data)
                        logger.info(f"✅ {len(issue_disciplines_data)} relacionamentos issue-discipline salvos via GraphQL consolidado")
                    
                    logger.info(f"🚀 Cache centralizado otimizado concluído - 1 query GraphQL vs 4+ REST")
                    return True
                else:
                    logger.warning("Query consolidada GraphQL retornou dados vazios, tentando método tradicional")
            else:
                logger.info("Conector GraphQL otimizado não disponível, usando método tradicional")
            
            # Fallback para método tradicional
            logger.info(f"Iniciando atualização centralizada de cache para {len(projects)} projetos")
            
            # Atualizar projetos
            projects_data = self.processor.construflow.get_data("projects", force_refresh=True, use_cache=False)
            if projects_data and hasattr(self.cache_manager, 'save_construflow_data'):
                self.cache_manager.save_construflow_data("projects", projects_data)
                logger.info(f"Cache de projetos atualizado com {len(projects_data)} registros")
            
            # Atualizar issues (todas de uma vez)
            issues_data = self.processor.construflow.get_data("issues", force_refresh=True, use_cache=False)
            if issues_data and hasattr(self.cache_manager, 'save_construflow_data'):
                self.cache_manager.save_construflow_data("issues", issues_data)
                logger.info(f"Cache de issues atualizado com {len(issues_data)} registros")
            
            # Atualizar disciplinas
            disciplines_data = self.processor.construflow.get_data("disciplines", force_refresh=True, use_cache=False)
            if disciplines_data and hasattr(self.cache_manager, 'save_construflow_data'):
                self.cache_manager.save_construflow_data("disciplines", disciplines_data)
                logger.info(f"Cache de disciplines atualizado com {len(disciplines_data)} registros")
            
            # Atualizar issues-disciplines
            issue_disciplines_data = self.processor.construflow.get_data("issues-disciplines", force_refresh=True, use_cache=False)
            if issue_disciplines_data and hasattr(self.cache_manager, 'save_construflow_data'):
                self.cache_manager.save_construflow_data("issues-disciplines", issue_disciplines_data)
                logger.info(f"Cache de issues-disciplines atualizado com {len(issue_disciplines_data)} registros")
            
            # 2. Agora, atualizar os Smartsheets específicos de cada projeto
            logger.info("Atualizando Smartsheets específicos de cada projeto")
            for project in projects:
                project_id = project['id']
                smartsheet_id = self.get_project_smartsheet_id(project_id)
                
                if smartsheet_id:
                    logger.info(f"Atualizando Smartsheet {smartsheet_id} para projeto {project_id}")
                    try:
                        sheet_data = self.processor.smartsheet.get_sheet(smartsheet_id, force_refresh=True)
                        if sheet_data and hasattr(self.cache_manager, 'save_smartsheet_data'):
                            self.cache_manager.save_smartsheet_data(smartsheet_id, project_id, sheet_data)
                            logger.info(f"Cache do Smartsheet {smartsheet_id} atualizado para projeto {project_id}")
                    except Exception as e:
                        logger.error(f"Erro ao atualizar Smartsheet para projeto {project_id}: {e}")
                else:
                    logger.warning(f"ID do Smartsheet não encontrado para projeto {project_id}")
            
            logger.info("Atualização centralizada de cache concluída com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro na atualização centralizada de cache: {e}", exc_info=True)
            return False

    def was_cache_recently_updated(self, minutes=10):
        """
        Verifica se o cache foi atualizado nos últimos X minutos.
        
        Args:
            minutes: Número de minutos para considerar como "recente"
            
        Returns:
            True se o cache foi atualizado recentemente, False caso contrário
        """
        try:
            # Verificar se temos o atributo last_cache_update
            if hasattr(self, 'last_cache_update'):
                last_update = self.last_cache_update
            else:
                # Tentar ler do arquivo
                cache_timestamp_file = os.path.join(self.config.cache_dir, "last_update.txt")
                if os.path.exists(cache_timestamp_file):
                    with open(cache_timestamp_file, 'r') as f:
                        last_update_str = f.read().strip()
                        last_update = datetime.fromisoformat(last_update_str)
                else:
                    # Se não houver arquivo, considerar que nunca foi atualizado
                    return False
            
            # Calcular tempo decorrido desde a última atualização
            elapsed = datetime.now() - last_update
            elapsed_minutes = elapsed.total_seconds() / 60
            
            return elapsed_minutes < minutes
        except Exception as e:
            logger.warning(f"Erro ao verificar última atualização de cache: {e}")
            return False

    def run_scheduled(self, force: bool = False, quiet_mode: bool = False, skip_notifications: bool = False, notification_delay: int = 0):
        """
        Executa o processamento se for sexta-feira ou se forçado.
        
        Args:
            force: Se deve forçar a execução independente do dia
            quiet_mode: Se deve operar em modo silencioso
            skip_notifications: Se True, não envia notificações para o Discord
            notification_delay: Tempo em segundos a aguardar entre notificações do Discord (para evitar rate limiting)
            
        Returns:
            Dicionário com resultados por projeto
        """
        if force or self.check_if_friday():
            logger.info("Iniciando processamento agendado")
            self.quiet_mode = quiet_mode
            
            # Obter projetos ativos da planilha
            projects_df = self._load_project_config()
            
            # Filtrar projetos ativos (igual ao que o bot faz)
            if 'relatoriosemanal_status' in projects_df.columns:
                active_projects_df = projects_df[projects_df['relatoriosemanal_status'].str.lower() == 'sim']
                logger.info(f"Filtrando {len(active_projects_df)} projetos ativos de {len(projects_df)} projetos totais")
            else:
                # Se não tiver coluna relatoriosemanal_status, considerar todos os projetos
                active_projects_df = projects_df
                logger.info(f"Coluna 'relatoriosemanal_status' não encontrada. Considerando todos os {len(projects_df)} projetos.")
            
            # Obter lista de projetos ativos com os dados completos
            projects = self.get_active_projects()
            
            if not projects:
                logger.warning("Nenhum projeto ativo encontrado na planilha de configuração")
                return {}
            
            # Logar detalhes sobre os projetos ativos
            logger.info(f"Iniciando processamento para {len(projects)} projetos ativos")
            for i, project in enumerate(projects):
                logger.info(f"Projeto {i+1}: {project['id']} - {project['name']}")
            
            # Verificar se o cache foi atualizado recentemente
            if self.was_cache_recently_updated(minutes=10):
                # Perguntar ao usuário se deseja atualizar o cache novamente
                print("\nO cache foi atualizado nos últimos 10 minutos.")
                update_cache = input("Deseja atualizar o cache novamente? (s/N): ").lower().strip() == 's'
                
                if not update_cache:
                    logger.info("Pulando atualização de cache por escolha do usuário")
                else:
                    # Primeira etapa: atualizar cache de forma centralizada
                    self.update_all_cache(projects)

            # Resultados
            results = {}
            
            # Definir flag para indicar que estamos em run_scheduled
            # Isso evita duplicação de notificações
            self._in_scheduled_run = True
            
            try:
                # Segunda etapa: processar cada projeto usando cache atualizado
                for i, project in enumerate(projects):
                    project_id = project['id']
                    logger.info(f"Processando projeto: {project['name']} (ID: {project_id}) - {i+1} de {len(projects)}")
                    
                    # Processar o projeto sem enviar notificações
                    results[project_id] = self.run_for_project(
                        project_id, 
                        quiet_mode=True, 
                        skip_cache_update=True, 
                        skip_notifications=True  # Evitar notificações duplicadas
                    )
                    
                    # Se configurado para enviar notificações no final, fazemos isso com delay
                    if not skip_notifications and results[project_id][0]:  # Se teve sucesso
                        try:
                            # Obter detalhes do projeto para notificação
                            project_name = project['name']
                            discord_channel_id = self.get_project_discord_channel(project_id)
                            doc_id = results[project_id][2]
                            
                            if discord_channel_id and doc_id:
                                # Tentar obter folder_id
                                try:
                                    project_folder_id = self.gdrive.get_project_folder(project_id, project_name)
                                except:
                                    project_folder_id = None
                                
                                # Construir URLs
                                doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
                                folder_url = f"https://drive.google.com/drive/folders/{project_folder_id}" if project_folder_id else None
                                
                                # Formatar mensagem final
                                final_message = self._format_final_success_message(project_name, doc_url, folder_url)
                                
                                # Enviar notificação
                                logger.info(f"Enviando notificação para canal {discord_channel_id} (projeto {project_id})")
                                self.send_discord_notification(discord_channel_id, final_message)
                                
                                # Aguardar para evitar rate limiting
                                if notification_delay > 0 and i < len(projects) - 1:  # Não aguardar após o último
                                    logger.info(f"Aguardando {notification_delay}s antes da próxima notificação (evitar rate limit)")
                                    time.sleep(notification_delay)
                        except Exception as e:
                            logger.error(f"Erro ao enviar notificação para projeto {project_id}: {e}")
                
                # Resumo
                success_count = sum(1 for result in results.values() if result[0])
                logger.info(f"Processamento concluído: {success_count}/{len(projects)} projetos com sucesso")
                
                # Limpar a flag
                self._in_scheduled_run = False
                
                return results
            except Exception as e:
                # Garantir que a flag seja limpa mesmo em caso de erro
                self._in_scheduled_run = False
                logger.error(f"Erro em run_scheduled: {e}")
                raise
        else:
            logger.info("Hoje não é sexta-feira. O processamento agendado não será executado.")
            return {}
    
    def check_if_friday(self) -> bool:
        """Verifica se hoje é sexta-feira."""
        return datetime.now().weekday() == 4  # 0 é segunda, 4 é sexta
    
    def get_cache_status(self):
        """Obtém o status do cache."""
        try:
            return self.cache.get_cache_status()
        except Exception as e:
            logger.error(f"Erro ao obter status do cache: {e}")
            return {}
    
    def check_weekly_reports_status(self) -> Dict:
        """
        Verifica o status dos relatórios da semana atual.
        
        Returns:
            Dicionário com informações sobre relatórios em falta
        """
        try:
            if not self.weekly_controller:
                logger.warning("Controlador de relatórios semanais não inicializado")
                return {"error": "Controlador não inicializado"}
            
            status_list = self.weekly_controller.get_weekly_report_status()
            missing_reports = self.weekly_controller.get_missing_reports_by_coordinator()
            
            current_week, current_week_text = self.weekly_controller.get_current_week_info()
            
            return {
                "week_number": current_week,
                "week_text": current_week_text,
                "total_projects": len(status_list),
                "should_generate": len([s for s in status_list if s.should_generate]),
                "was_generated": len([s for s in status_list if s.was_generated]),
                "missing_reports": len([s for s in status_list if s.should_generate and not s.was_generated]),
                "missing_by_coordinator": missing_reports,
                "status_list": status_list
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar status dos relatórios: {e}")
            return {"error": str(e)}
    
    def send_weekly_reports_notification(self, channel_id: str) -> bool:
        """
        Envia notificação sobre relatórios em falta para um canal específico.
        
        Args:
            channel_id: ID do canal do Discord
            
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        try:
            if not self.weekly_controller:
                logger.warning("Controlador de relatórios semanais não inicializado")
                return False
            
            return self.weekly_controller.send_missing_reports_notification(channel_id)
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de relatórios: {e}")
            return False
    
    def send_direct_notifications_to_coordinators(self, admin_channel_id: str = None) -> bool:
        """
        Envia notificações diretas para coordenadores que não geraram relatórios.
        
        Args:
            admin_channel_id: ID do canal admin para logs (opcional)
            
        Returns:
            True se pelo menos uma notificação foi enviada com sucesso
        """
        try:
            if not self.weekly_controller:
                logger.warning("Controlador de relatórios semanais não inicializado")
                return False
            
            return self.weekly_controller.send_direct_notifications_to_coordinators(admin_channel_id)
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificações diretas: {e}")
            return False
    
    def _check_and_notify_no_issues(self, project_data: Dict[str, Any], project_id: str, project_name: str) -> None:
        """
        Verifica se o projeto tem apontamentos e notifica no Discord se não tiver.
        
        Args:
            project_data: Dados processados do projeto
            project_id: ID do projeto
            project_name: Nome do projeto
        """
        try:
            # Validar project_data
            if not project_data or not isinstance(project_data, dict):
                logger.warning(f"project_data inválido em _check_and_notify_no_issues para projeto {project_id}")
                return
            
            # Verificar se há dados do Construflow
            construflow_data = project_data.get('construflow_data')
            if not construflow_data:
                logger.warning(f"Projeto {project_id} ({project_name}) não tem dados do Construflow - enviando notificação")
                
                # Obter canal do Discord para este projeto
                discord_channel_id = self.get_project_discord_channel(project_id)
                
                if discord_channel_id:
                    # Formatar mensagem de notificação sobre falta de dados do Construflow
                    today_str = datetime.now().strftime("%d/%m/%Y")
                    notification_message = (
                        f"⚠️ **Atenção - Dados do Construflow Indisponíveis**\n\n"
                        f"📋 **Projeto:** {project_name}\n"
                        f"📅 **Data:** {today_str}\n\n"
                        f"❌ **Problema:** Não foi possível obter dados do Construflow para este projeto.\n\n"
                        f"**Possíveis causas:**\n"
                        f"• Problemas de conexão com a API do Construflow\n"
                        f"• Projeto não encontrado no Construflow\n"
                        f"• Permissões insuficientes para acessar os dados\n\n"
                        f"Por favor, verifique a configuração do projeto e tente novamente."
                    )
                    
                    # Enviar notificação
                    logger.info(f"Enviando notificação sobre falta de dados do Construflow para canal {discord_channel_id}")
                    self.send_discord_notification(discord_channel_id, notification_message)
                else:
                    logger.warning(f"Canal do Discord não encontrado para projeto {project_id} - não foi possível notificar sobre falta de dados do Construflow")
                
                return
            
            # Verificar se há apontamentos ativos
            active_issues = construflow_data.get('active_issues', [])
            if not active_issues:
                logger.info(f"Projeto {project_id} ({project_name}) não tem apontamentos ativos")
                
                # Obter canal do Discord para este projeto
                discord_channel_id = self.get_project_discord_channel(project_id)
                
                if discord_channel_id:
                    # Formatar mensagem de notificação
                    today_str = datetime.now().strftime("%d/%m/%Y")
                    notification_message = (
                        f"📋 **Relatório Semanal - {project_name}**\n\n"
                        f"ℹ️ **Status:** Relatório gerado com sucesso\n"
                        f"📅 **Data:** {today_str}\n"
                        f"⚠️ **Observação:** Este projeto não possui apontamentos pendentes no Construflow\n\n"
                        f"O relatório foi gerado normalmente, mas as seções de apontamentos estão vazias."
                    )
                    
                    # Enviar notificação
                    logger.info(f"Enviando notificação sobre falta de apontamentos para canal {discord_channel_id}")
                    self.send_discord_notification(discord_channel_id, notification_message)
                else:
                    logger.warning(f"Canal do Discord não encontrado para projeto {project_id}")
            else:
                logger.info(f"Projeto {project_id} ({project_name}) tem {len(active_issues)} apontamentos ativos")
                
        except Exception as e:
            logger.error(f"Erro ao verificar apontamentos do projeto {project_id}: {e}")

    def send_hourly_notification(self, message: str) -> bool:
        """
        Envia uma notificação para o canal de notificações por hora configurado.
        
        Args:
            message: Mensagem a ser enviada
            
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        try:
            if not self.discord:
                logger.warning("Gerenciador de Discord não inicializado")
                return False
            
            return self.discord.send_hourly_notification(message)
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação por hora: {e}")
            return False

# Funções de utilidade para execução
def is_running_in_colab():
    """Verifica se o código está sendo executado no Google Colab."""
    try:
        import importlib.util
        colab_spec = importlib.util.find_spec("google.colab")
        return colab_spec is not None
    except ImportError:
        return False

def setup_for_colab():
    """Configura o ambiente para execução no Google Colab."""
    # Verificar se estamos no ambiente Colab
    if not is_running_in_colab():
        print("Não estamos no Google Colab, executando localmente")
        return ".env"  # Path padrão local
    
    # Se chegou aqui, estamos no Colab - importa apenas se estiver no Colab
    from google.colab import drive
    try:
        drive.mount('/content/drive')
        
        # Configurar path para o arquivo .env
        env_path = '/content/drive/MyDrive/report_system/.env'
        
        # Verificar se o arquivo existe
        if not os.path.exists(env_path):
            print(f"Arquivo .env não encontrado em {env_path}")
            print("Por favor, crie o arquivo .env na pasta /content/drive/MyDrive/report_system/")
            return None
        
        return env_path
        
    except Exception as e:
        print(f"Erro ao configurar Google Drive no Colab: {e}")
        return None


# Execução principal
if __name__ == "__main__":
    # Detectar ambiente (Colab ou local)
    env_path = setup_for_colab()
    
    if not env_path:
        print("Configuração inicial falhou. Encerrando.")
        exit(1)
    
    # Parâmetro para forçar execução mesmo que não seja sexta
    parser = argparse.ArgumentParser(description='Sistema de Relatórios Semanais')
    parser.add_argument('--force', action='store_true', help='Forçar execução independente do dia')
    parser.add_argument('--project', type=str, help='ID do projeto específico para executar')
    parser.add_argument('--check-cache', action='store_true', help='Verificar status do cache')
    parser.add_argument('--update-cache', action='store_true', help='Forçar atualização de todo o cache')
    parser.add_argument('--no-notifications', action='store_true', help='Desativar notificações do Discord')
    args = parser.parse_args()
    
    # Criar e executar o sistema
    system = WeeklyReportSystem(env_path, disable_notifications=args.no_notifications)
    
    # Verificar se é para mostrar o status do cache
    if args.check_cache:
        # Verificar se estamos usando o sistema de 5 arquivos
        if hasattr(system.cache_manager, 'files'):
            print("\n=== STATUS DO SISTEMA DE 5 ARQUIVOS ===")
            
            # Verificar cada arquivo
            for data_type, file_path in system.cache_manager.files.items():
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # tamanho em MB
                    modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    # Tentar obter contagem de registros
                    try:
                        df = pd.read_parquet(file_path)
                        record_count = len(df)
                    except Exception as e:
                        record_count = f"Erro: {e}"
                    
                    print(f"\n{data_type.upper()}:")
                    print(f"  Arquivo: {os.path.basename(file_path)}")
                    print(f"  Tamanho: {file_size:.2f} MB")
                    print(f"  Atualizado: {modified}")
                    print(f"  Registros: {record_count}")
                else:
                    print(f"\n{data_type.upper()}:")
                    print(f"  Arquivo não encontrado: {os.path.basename(file_path)}")
        else:
            # Listar arquivos no diretório de cache
            cache_dir = system.config.cache_dir
            print(f"\n=== ARQUIVOS NO DIRETÓRIO DE CACHE ({cache_dir}) ===")
            if os.path.exists(cache_dir):
                files = os.listdir(cache_dir)
                for file in files:
                    file_path = os.path.join(cache_dir, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path) / (1024 * 1024)  # tamanho em MB
                        print(f"  - {file}: {file_size:.2f} MB")
                
                # Verificar subdiretório construflow
                construflow_dir = os.path.join(cache_dir, "construflow")
                if os.path.exists(construflow_dir):
                    print(f"\n=== ARQUIVOS NO DIRETÓRIO {construflow_dir} ===")
                    files = os.listdir(construflow_dir)
                    for file in files:
                        file_path = os.path.join(construflow_dir, file)
                        if os.path.isfile(file_path):
                            file_size = os.path.getsize(file_path) / (1024 * 1024)  # tamanho em MB
                            print(f"  - {file}: {file_size:.2f} MB")
            else:
                print(f"Diretório {cache_dir} não encontrado")
        
        # Verificar status do cache antigo se disponível
        cache_status = system.get_cache_status()
        if not isinstance(cache_status, pd.DataFrame) or cache_status.empty:
            print("\nInformações detalhadas do cache não disponíveis")
        else:
            print("\n=== STATUS DO CACHE ANTIGO ===")
            print(f"Total de entradas: {len(cache_status)}")
            
            # Agrupar por fonte e status de validade se as colunas estiverem presentes
            if 'source' in cache_status.columns and 'is_valid' in cache_status.columns:
                source_stats = cache_status.groupby(['source', 'is_valid']).size().unstack(fill_value=0)
                print("\nStatus por fonte:")
                print(source_stats)
                
                # Mostrar entradas mais antigas
                if 'last_update' in cache_status.columns:
                    print("\nEntradas mais antigas:")
                    oldest = cache_status.sort_values('last_update').head(5)
                    for _, row in oldest.iterrows():
                        if 'age_hours' in row:
                            age_hours = row['age_hours']
                            age_days = age_hours / 24
                            print(f"- {row['cache_key']} ({row['source']}): {age_days:.1f} dias ({row['last_update']})")
        
        exit(0)
    
    # Verificar se é para atualizar o cache
    if args.update_cache:
        print("Forçando atualização de todo o cache...")
        
        # Verificar se estamos usando o sistema de 5 arquivos
        using_five_files = hasattr(system.cache_manager, 'files')
        
        if using_five_files:
            print("Atualizando arquivos do sistema de 5 arquivos...")
            # Chamar o método de atualização de cache com um projeto qualquer
            # Isso forçará atualização de todos os 5 arquivos
            active_projects = system.get_active_projects()
            if active_projects:
                first_project = active_projects[0]['id']
                print(f"Usando o projeto {first_project} para iniciar atualização completa...")
                system._update_project_cache(first_project)
                print("\nAtualização de cache concluída!")
            else:
                print("Nenhum projeto ativo encontrado para atualizar o cache")
        else:
            # Usar método antigo
            # Atualizar dados do Construflow
            construflow = system.processor.construflow
            print("Atualizando projetos...")
            projects_df = construflow.get_projects(force_refresh=True)
            print(f"Cache de projetos atualizado: {len(projects_df)} projetos")
            
            print("Atualizando issues...")
            issues_df = construflow.get_issues(force_refresh=True)
            print(f"Cache de issues atualizado: {len(issues_df)} issues")
            
            # Tentar atualizar dados do Smartsheet para projetos ativos
            projects = system.get_active_projects()
            print(f"\nAtualizando Smartsheets para {len(projects)} projetos ativos...")
            for project in projects:
                if project.get('smartsheet_id'):
                    print(f"Atualizando Smartsheet para {project['name']}...")
                    try:
                        sheet_data = system.processor.smartsheet.get_sheet(
                            project['smartsheet_id'], 
                            force_refresh=True
                        )
                        if sheet_data:
                            print(f"Smartsheet atualizado para {project['name']}")
                    except Exception as e:
                        print(f"Erro ao atualizar Smartsheet para {project['name']}: {e}")
        
        print("\nAtualização de cache concluída!")
        exit(0)
    
    # Executar o sistema
    if args.project:
        # Executar apenas para um projeto específico
        project_id = args.project
        print(f"Executando apenas para o projeto {project_id}")
        result = system.run_for_project(project_id)
        
        status = "✅ Sucesso" if result[0] else "❌ Falha"
        print(f"Projeto {project_id}: {status}")
        if result[0]:
            print(f"  - Arquivo local: {result[1]}")
            if result[2]:
                print(f"  - ID no Drive: {result[2]}")
    else:
        # Executar para todos os projetos ativos
        results = system.run_scheduled(force=args.force)
        
        # Exibir resultados
        for project_id, (success, file_path, drive_id) in results.items():
            status = "✅ Sucesso" if success else "❌ Falha"
            print(f"Projeto {project_id}: {status}")
            if success:
                print(f"  - Arquivo local: {file_path}")
                if drive_id:
                    print(f"  - ID no Drive: {drive_id}")