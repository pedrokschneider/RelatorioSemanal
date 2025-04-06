"""
Gerenciador de operações com Google Drive.
"""

import os
import logging
import pandas as pd
import time
from typing import Dict, List, Optional, Any, Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from ..config import ConfigManager

logger = logging.getLogger("ReportSystem")

class GoogleDriveManager:
    """Gerencia operações com Google Drive."""
    
    def __init__(self, config: ConfigManager):
        """
        Inicializa o gerenciador do Google Drive.
        
        Args:
            config: Instância do ConfigManager
        """
        self.config = config
        self.credentials = config.get_google_creds()
        self.drive_service = self._get_drive_service()
        self.sheets_service = self._get_sheets_service()
        self.project_folders_cache = {}  # Cache para IDs de pasta de projetos
    
    def _get_drive_service(self):
        """
        Cria e retorna o serviço do Google Drive.
        
        Returns:
            Serviço do Google Drive ou None se falhar
        """
        if not self.credentials:
            logger.error("Credenciais do Google não disponíveis")
            return None
        
        try:
            return build('drive', 'v3', credentials=self.credentials)
        except Exception as e:
            logger.error(f"Erro ao criar serviço do Drive: {e}")
            return None
    
    def _get_sheets_service(self):
        """
        Cria e retorna o serviço do Google Sheets.
        
        Returns:
            Serviço do Google Sheets ou None se falhar
        """
        if not self.credentials:
            logger.error("Credenciais do Google não disponíveis")
            return None
        
        try:
            return build('sheets', 'v4', credentials=self.credentials)
        except Exception as e:
            logger.error(f"Erro ao criar serviço do Sheets: {e}")
            return None
    
    def read_sheet(self, spreadsheet_id: str, range_name: str = 'A1:Z1000', 
                 header: bool = True) -> pd.DataFrame:
        """
        Lê dados de uma planilha Google.
        
        Args:
            spreadsheet_id: ID da planilha
            range_name: Intervalo a ser lido
            header: Se True, usa a primeira linha como cabeçalho
            
        Returns:
            DataFrame com dados da planilha
        """
        if not self.sheets_service:
            logger.error("Serviço do Sheets não disponível")
            return pd.DataFrame()
        
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, 
                range=range_name,
                valueRenderOption='UNFORMATTED_VALUE'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                logger.warning(f"Planilha {spreadsheet_id} vazia ou inacessível")
                return pd.DataFrame()
            
            # Criar DataFrame
            if header:
                if len(values) > 1:
                    df = pd.DataFrame(values[1:], columns=values[0])
                else:
                    df = pd.DataFrame(columns=values[0])
            else:
                df = pd.DataFrame(values)
            
            return df
            
        except Exception as e:
            logger.error(f"Erro ao ler planilha {spreadsheet_id}: {e}")
            return pd.DataFrame()
    
    def create_folder(self, name: str, parent_id: Optional[str] = None, 
                     max_retries: int = 3) -> Optional[str]:
        """
        Cria uma pasta no Google Drive com retry automático.
        
        Args:
            name: Nome da pasta
            parent_id: ID da pasta pai
            max_retries: Número máximo de tentativas
            
        Returns:
            ID da pasta criada ou None em caso de erro
        """
        if not self.drive_service:
            logger.error("Serviço do Drive não disponível")
            return None
        
        for attempt in range(max_retries):
            try:
                file_metadata = {
                    'name': name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                
                if parent_id:
                    file_metadata['parents'] = [parent_id]
                
                # Adicionar suporte a Drives Compartilhados
                folder = self.drive_service.files().create(
                    body=file_metadata, 
                    fields='id,name',
                    supportsAllDrives=True
                ).execute()
                
                folder_id = folder.get('id')
                logger.info(f"Pasta '{name}' criada com ID: {folder_id}")
                return folder_id
                
            except HttpError as e:
                # Tentar novamente apenas para erros específicos
                if e.resp.status in [429, 500, 502, 503, 504]:
                    logger.warning(f"Falha temporária ao criar pasta '{name}' (tentativa {attempt+1}/{max_retries}): {e}")
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    logger.error(f"Erro permanente ao criar pasta '{name}': {e}")
                    return None
                    
            except Exception as e:
                logger.error(f"Erro ao criar pasta '{name}': {e}")
                time.sleep(2 ** attempt)  # Backoff exponencial
                
        logger.error(f"Todas as {max_retries} tentativas falharam ao criar pasta '{name}'")
        return None
    
    def upload_file(self, file_path: str, name: Optional[str] = None, 
                   parent_id: Optional[str] = None, max_retries: int = 3) -> Optional[str]:
        """
        Faz upload de um arquivo para o Google Drive com retry automático.
        
        Args:
            file_path: Caminho local do arquivo
            name: Nome do arquivo no Drive (opcional)
            parent_id: ID da pasta pai (opcional)
            max_retries: Número máximo de tentativas
            
        Returns:
            ID do arquivo enviado ou None em caso de erro
        """
        if not self.drive_service:
            logger.error("Serviço do Drive não disponível")
            return None
        
        if not os.path.exists(file_path):
            logger.error(f"Arquivo não encontrado: {file_path}")
            return None
            
        file_name = name or os.path.basename(file_path)
        
        for attempt in range(max_retries):
            try:
                file_metadata = {'name': file_name}
                if parent_id:
                    file_metadata['parents'] = [parent_id]
                
                # Determinar o tipo MIME
                mime_type = self._get_mime_type(file_path)
                
                media = MediaFileUpload(
                    file_path,
                    mimetype=mime_type,
                    resumable=True
                )
                
                # Adicionar suporte a Drives Compartilhados
                file = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,name,webViewLink',
                    supportsAllDrives=True
                ).execute()
                
                file_id = file.get('id')
                logger.info(f"Arquivo '{file_name}' enviado com ID: {file_id}")
                return file_id
                
            except HttpError as e:
                # Tentar novamente apenas para erros específicos
                if e.resp.status in [429, 500, 502, 503, 504]:
                    logger.warning(f"Falha temporária ao enviar arquivo '{file_name}' (tentativa {attempt+1}/{max_retries}): {e}")
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    logger.error(f"Erro permanente ao enviar arquivo '{file_name}': {e}")
                    return None
                    
            except Exception as e:
                logger.error(f"Erro ao enviar arquivo '{file_name}': {e}")
                time.sleep(2 ** attempt)  # Backoff exponencial
                
        logger.error(f"Todas as {max_retries} tentativas falharam ao enviar arquivo '{file_name}'")
        return None
    
    def _get_mime_type(self, file_path: str) -> str:
        """
        Determina o tipo MIME de um arquivo pelo nome.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Tipo MIME do arquivo
        """
        # Mapeamento básico de extensões para tipos MIME
        mime_map = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.csv': 'text/csv',
            '.json': 'application/json',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }
        
        ext = os.path.splitext(file_path)[1].lower()
        return mime_map.get(ext, 'application/octet-stream')  # Tipo genérico como fallback
        
    def find_or_create_folder_path(self, folder_path: List[str], 
                                  parent_id: Optional[str] = None) -> Optional[str]:
        """
        Encontra ou cria uma hierarquia de pastas no Google Drive.
        
        Args:
            folder_path: Lista com nomes das pastas na hierarquia
            parent_id: ID da pasta pai inicial
            
        Returns:
            ID da pasta mais interna da hierarquia ou None em caso de erro
        """
        if not folder_path:
            return parent_id
            
        current_parent_id = parent_id
        
        for folder_name in folder_path:
            folder_id = self._find_folder(folder_name, current_parent_id)
            
            if not folder_id:
                folder_id = self.create_folder(folder_name, current_parent_id)
                
            if not folder_id:
                logger.error(f"Erro ao criar/encontrar pasta {folder_name}")
                return None
                
            current_parent_id = folder_id
            
        return current_parent_id
    
    def _find_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Encontra uma pasta no Google Drive pelo nome.
        
        Args:
            name: Nome da pasta
            parent_id: ID da pasta pai
            
        Returns:
            ID da pasta encontrada ou None se não encontrada
        """
        if not self.drive_service:
            logger.error("Serviço do Drive não disponível")
            return None
            
        try:
            # Construir query
            query = f"mimeType='application/vnd.google-apps.folder' and name='{name}' and trashed=false"
            
            if parent_id:
                query += f" and '{parent_id}' in parents"
                
            response = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            files = response.get('files', [])
            
            if files:
                logger.debug(f"Pasta '{name}' encontrada com ID: {files[0]['id']}")
                return files[0]['id']
            else:
                logger.debug(f"Pasta '{name}' não encontrada")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao buscar pasta '{name}': {e}")
            return None
    
    def load_project_config_from_sheet(self) -> pd.DataFrame:
        """
        Carrega a configuração de projetos da planilha Google Sheets.
        
        Returns:
            DataFrame com configurações de projetos
        """
        if not self.sheets_service or not self.config.projects_sheet_id:
            logger.warning("Serviço do Sheets não disponível ou ID da planilha não configurado")
            return pd.DataFrame()
        
        try:
            # Carregar planilha de configuração de projetos
            df = self.read_sheet(
                spreadsheet_id=self.config.projects_sheet_id,
                range_name=f"{self.config.projects_sheet_name}!A1:Z1000"
            )
            
            if df.empty:
                logger.warning("Planilha de configuração de projetos vazia")
                return pd.DataFrame()
            
            # Garantir que o ID do Construflow seja string
            if 'ID_Construflow' in df.columns:
                df['ID_Construflow'] = df['ID_Construflow'].astype(str)
            
            logger.info(f"Carregados {len(df)} projetos da planilha de configuração")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao carregar planilha de configuração de projetos: {e}")
            return pd.DataFrame()
    
    def get_project_folder(self, project_id, project_name):
        """
        Obtém ou cria uma pasta do Drive para um projeto.
        
        Args:
            project_id: ID do projeto
            project_name: Nome do projeto
            
        Returns:
            ID da pasta ou None
        """
        try:
            logger.info(f"Buscando pasta do Drive para projeto {project_id} ({project_name})")
            
            # 1. Primeiro, tentar encontrar na planilha de configuração
            projects_df = self.load_project_config_from_sheet()
            
            if not projects_df.empty and 'ID_Construflow' in projects_df.columns and 'ID_Pasta_Drive' in projects_df.columns:
                # Converter para string para comparação segura
                projects_df['ID_Construflow'] = projects_df['ID_Construflow'].astype(str)
                project_row = projects_df[projects_df['ID_Construflow'] == str(project_id)]
                
                if not project_row.empty and pd.notna(project_row['ID_Pasta_Drive'].iloc[0]):
                    folder_id = str(project_row['ID_Pasta_Drive'].iloc[0])
                    logger.info(f"ID da pasta encontrado na planilha: {folder_id}")
                    return folder_id
            
            # 2. Se não encontrar na planilha, tentar buscar pelo nome do projeto
            drive_service = self._get_drive_service()
            if not drive_service:
                logger.error("Serviço do Google Drive não disponível")
                return None
            
            # Sanitizar o nome para evitar problemas na consulta
            safe_name = project_name.replace("'", "\\'")
            
            # Buscar pasta pelo nome
            query = f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            
            try:
                response = drive_service.files().list(
                    q=query,
                    spaces='drive',
                    fields='files(id, name)',
                    pageSize=10
                ).execute()
                
                folders = response.get('files', [])
                if folders:
                    folder_id = folders[0]['id']
                    logger.info(f"Pasta encontrada pelo nome: {folders[0]['name']} (ID: {folder_id})")
                    return folder_id
            except Exception as search_error:
                logger.error(f"Erro ao buscar pasta pelo nome: {search_error}")
            
            # 3. Se não encontrar, criar uma nova pasta
            logger.info(f"Pasta não encontrada. Criando nova pasta para o projeto {project_name}")
            
            # Determinar pasta pai
            parent_id = self.report_base_folder_id
            if not parent_id:
                # Se não tiver ID de pasta base, usar raiz
                parent_id = 'root'
                logger.warning("ID da pasta base não configurado, usando pasta raiz")
            
            try:
                folder_metadata = {
                    'name': project_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parent_id]
                }
                
                # Criar pasta com suporte a drives compartilhados
                folder = drive_service.files().create(
                    body=folder_metadata,
                    fields='id',
                    supportsAllDrives=True
                ).execute()
                
                folder_id = folder.get('id')
                logger.info(f"Nova pasta criada com ID: {folder_id}")
                
                return folder_id
            except Exception as create_error:
                logger.error(f"Erro ao criar pasta: {create_error}")
                
                # Em caso de falha ao criar, tentar usar um ID de pasta padrão
                fallback_folder = self.config.get_env_var('DEFAULT_FOLDER_ID')
                if fallback_folder:
                    logger.info(f"Usando pasta padrão como fallback: {fallback_folder}")
                    return fallback_folder
                
                return None
                
        except Exception as e:
            logger.error(f"Erro ao obter/criar pasta para o projeto {project_id}: {e}")
            return None
    
    def list_all_drive_folders(self) -> List[Dict[str, str]]:
        """
        Lista todas as pastas disponíveis no Google Drive.
        Útil para debug e para identificar os IDs das pastas.
        
        Returns:
            Lista de dicionários com 'id' e 'name' das pastas
        """
        if not self.drive_service:
            logger.error("Serviço do Drive não disponível")
            return []
        
        try:
            # Buscar todas as pastas
            query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
            result = []
            page_token = None
            
            while True:
                response = self.drive_service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, parents)',
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                
                folders = response.get('files', [])
                result.extend(folders)
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            # Ordenar pastas por nome para facilitar a leitura
            result.sort(key=lambda x: x.get('name', '').lower())
            
            logger.info(f"Encontradas {len(result)} pastas no Drive")
            return result
        except Exception as e:
            logger.error(f"Erro ao listar pastas do Drive: {e}")
            return []

    def find_folders_containing(self, name_part: str) -> List[Dict[str, str]]:
        """
        Encontra pastas que contenham uma parte específica no nome.
        
        Args:
            name_part: Parte do nome a ser buscada
            
        Returns:
            Lista de dicionários com 'id' e 'name' das pastas encontradas
        """
        if not self.drive_service:
            logger.error("Serviço do Drive não disponível")
            return []
        
        try:
            # Buscar pastas que contenham a parte do nome
            query = f"mimeType='application/vnd.google-apps.folder' and name contains '{name_part}' and trashed=false"
            
            response = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, parents)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            folders = response.get('files', [])
            
            # Ordenar pastas por nome
            folders.sort(key=lambda x: x.get('name', '').lower())
            
            logger.info(f"Encontradas {len(folders)} pastas contendo '{name_part}'")
            return folders
        except Exception as e:
            logger.error(f"Erro ao buscar pastas contendo '{name_part}': {e}")
            return []