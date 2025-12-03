"""
Gerenciador de operações com Google Drive.
"""

import os
import logging
import pandas as pd
import time
import re
import io
import base64
from typing import Dict, List, Optional, Any, Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from ..config import ConfigManager

# Configurar logger primeiro
logger = logging.getLogger("ReportSystem")

# Tentar importar Pillow para processamento de imagens
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Pillow não está instalado. Processamento de imagens não estará disponível.")

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
                    # Pegar os cabeçalhos da primeira linha
                    headers = values[0]
                    
                    # Preparar os dados normalizando o número de colunas
                    data = []
                    for row in values[1:]:
                        # Se a linha tiver menos colunas que o cabeçalho, preencher com None
                        if len(row) < len(headers):
                            row_padded = row + [None] * (len(headers) - len(row))
                            data.append(row_padded)
                        # Se a linha tiver mais colunas que o cabeçalho, truncar
                        elif len(row) > len(headers):
                            logger.warning(f"Linha com mais colunas ({len(row)}) que o cabeçalho ({len(headers)}). Truncando dados.")
                            data.append(row[:len(headers)])
                        else:
                            data.append(row)
                    
                    # Criar o DataFrame com os dados normalizados
                    df = pd.DataFrame(data, columns=headers)
                else:
                    df = pd.DataFrame(columns=values[0])
            else:
                # Se não estiver usando a primeira linha como cabeçalho,
                # normalizar o número de colunas para a linha mais longa
                max_cols = max(len(row) for row in values)
                data = []
                for row in values:
                    if len(row) < max_cols:
                        data.append(row + [None] * (max_cols - len(row)))
                    else:
                        data.append(row)
                df = pd.DataFrame(data)
            
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
                web_view_link = file.get('webViewLink')
                logger.info(f"Arquivo '{file_name}' enviado com ID: {file_id}")
                
                # Retornar dicionário com id e webViewLink para arquivos HTML
                if mime_type == 'text/html' and web_view_link:
                    return {'id': file_id, 'webViewLink': web_view_link}
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
            '.html': 'text/html',
            '.htm': 'text/html',
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
    
    def extract_file_id_from_url(self, url: str) -> Optional[str]:
        """
        Extrai o ID do arquivo de um link do Google Drive.
        
        Suporta vários formatos:
        - https://drive.google.com/file/d/FILE_ID/view
        - https://drive.google.com/open?id=FILE_ID
        - https://docs.google.com/document/d/FILE_ID/edit
        - FILE_ID (se já for apenas o ID)
        
        Args:
            url: URL do Google Drive ou ID do arquivo
            
        Returns:
            ID do arquivo ou None se não encontrar
        """
        if not url or pd.isna(url):
            return None
        
        url = str(url).strip()
        
        # Se já for apenas um ID (sem caracteres especiais de URL)
        if re.match(r'^[a-zA-Z0-9_-]+$', url):
            return url
        
        # Padrões comuns de URLs do Google Drive
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',  # /file/d/FILE_ID
            r'[?&]id=([a-zA-Z0-9_-]+)',   # ?id=FILE_ID ou &id=FILE_ID
            r'/d/([a-zA-Z0-9_-]+)',        # /d/FILE_ID
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        logger.warning(f"Não foi possível extrair ID do arquivo da URL: {url}")
        return None

    def download_file_as_base64(self, file_id: str, 
                                max_width: int = 400, 
                                max_height: int = 400,
                                quality: int = 85) -> Optional[str]:
        """
        Baixa um arquivo do Google Drive, redimensiona e retorna como base64.
        
        Args:
            file_id: ID do arquivo no Google Drive (ou URL completa)
            max_width: Largura máxima da imagem (padrão: 400px)
            max_height: Altura máxima da imagem (padrão: 400px)
            quality: Qualidade JPEG (1-100, padrão: 85)
            
        Returns:
            String base64 da imagem processada ou None se falhar
        """
        if not self.drive_service:
            logger.error("Serviço do Google Drive não disponível")
            return None
        
        # Se for uma URL, extrair o ID
        if file_id.startswith('http'):
            file_id = self.extract_file_id_from_url(file_id)
            if not file_id:
                return None
        
        try:
            # Baixar o arquivo
            request = self.drive_service.files().get_media(fileId=file_id)
            file_content = request.execute()
            
            # Processar a imagem apenas se Pillow estiver disponível
            if PIL_AVAILABLE:
                try:
                    # Abrir a imagem
                    image = Image.open(io.BytesIO(file_content))
                    
                    # Converter para RGB se necessário (para JPEG)
                    if image.mode in ('RGBA', 'LA', 'P'):
                        # Criar fundo branco para imagens com transparência
                        rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                        if image.mode == 'P':
                            image = image.convert('RGBA')
                        rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                        image = rgb_image
                    elif image.mode != 'RGB':
                        image = image.convert('RGB')
                    
                    # Redimensionar mantendo proporção
                    image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                    
                    # Salvar em buffer como JPEG
                    output_buffer = io.BytesIO()
                    image.save(output_buffer, format='JPEG', quality=quality, optimize=True)
                    output_buffer.seek(0)
                    
                    # Converter para base64
                    base64_content = base64.b64encode(output_buffer.read()).decode('utf-8')
                    
                    # Retornar no formato data URI
                    return f"data:image/jpeg;base64,{base64_content}"
                    
                except Exception as img_error:
                    logger.error(f"Erro ao processar imagem {file_id}: {img_error}")
                    # Se não for uma imagem, tentar retornar o arquivo original
                    base64_content = base64.b64encode(file_content).decode('utf-8')
                    
                    # Determinar o tipo MIME
                    file_metadata = self.drive_service.files().get(
                        fileId=file_id,
                        fields='mimeType'
                    ).execute()
                    
                    mime_type = file_metadata.get('mimeType', 'application/octet-stream')
                    return f"data:{mime_type};base64,{base64_content}"
            else:
                # Se Pillow não estiver disponível, retornar o arquivo original
                logger.warning("Pillow não disponível, retornando imagem sem processamento")
                base64_content = base64.b64encode(file_content).decode('utf-8')
                
                # Determinar o tipo MIME
                file_metadata = self.drive_service.files().get(
                    fileId=file_id,
                    fields='mimeType'
                ).execute()
                
                mime_type = file_metadata.get('mimeType', 'application/octet-stream')
                return f"data:{mime_type};base64,{base64_content}"
            
        except HttpError as e:
            logger.error(f"Erro ao baixar arquivo {file_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro ao processar arquivo {file_id}: {e}")
            return None
        
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
            # Range estendido para incluir colunas AD, AE, AF (email_url_capa, email_url_gant, email_url_disciplina)
            df = self.read_sheet(
                spreadsheet_id=self.config.projects_sheet_id,
                range_name=f"{self.config.projects_sheet_name}!A1:AF1000"
            )
            
            if df.empty:
                logger.warning("Planilha de configuração de projetos vazia")
                return pd.DataFrame()
            
            # Garantir que o ID do Construflow seja string
            if 'construflow_id' in df.columns:
                df['construflow_id'] = df['construflow_id'].astype(str)
            
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
            
            if not projects_df.empty and 'construflow_id' in projects_df.columns and 'pastaemails_id' in projects_df.columns:
                # Converter para string para comparação segura
                projects_df['construflow_id'] = projects_df['construflow_id'].astype(str)
                project_row = projects_df[projects_df['construflow_id'] == str(project_id)]
                
                if not project_row.empty and pd.notna(project_row['pastaemails_id'].iloc[0]):
                    folder_id = str(project_row['pastaemails_id'].iloc[0])
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

    def create_google_doc(self, file_path: str, folder_id: str = None) -> str:
        """
        Cria um documento Google Docs a partir de um arquivo local.
        
        Args:
            file_path: Caminho para o arquivo local
            folder_id: ID da pasta do Google Drive (opcional)
            
        Returns:
            ID do documento criado ou None se falhar
        """
        try:
            # Verificar se o arquivo existe
            if not os.path.exists(file_path):
                logger.error(f"Arquivo não encontrado: {file_path}")
                return None
            
            # Ler o conteúdo do arquivo para criar o documento diretamente
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Inicializar serviço do Google Docs
            docs_service = self._get_docs_service()
            if not docs_service:
                logger.error("Não foi possível conectar ao Google Docs")
                return None
            
            # Obter o nome do arquivo sem extensão
            file_name = os.path.basename(file_path)
            file_name_without_ext = os.path.splitext(file_name)[0]
            
            # Criar um documento vazio
            logger.info(f"Criando documento Google Docs: {file_name_without_ext}")
            doc = docs_service.documents().create(body={'title': file_name_without_ext}).execute()
            doc_id = doc.get('documentId')
            
            if not doc_id:
                logger.error("Falha ao criar documento vazio no Google Docs")
                return None
            
            # Pré-processamento do conteúdo para melhorar a formatação
            import re
            
            # Melhorias no pré-processamento para tratamento dos símbolos Markdown
            logger.info("Pré-processando conteúdo para garantir formatação adequada...")
            
            # Identificar e armazenar links para restauração posterior
            links = []
            def store_link(match):
                link_text = match.group(1)
                link_url = match.group(2)
                links.append((link_text, link_url))
                # Retornar apenas o texto com um marcador especial
                return f"__LINK_{len(links)-1}__"
            
            # Substituir links por marcadores temporários
            content = re.sub(r'\[(.*?)\]\((.*?)\)', store_link, content)
            
            # Identificar cabeçalhos
            headers_level1 = []
            headers_level2 = []
            
            def store_header1(match):
                header_text = match.group(1).strip()
                headers_level1.append(header_text)
                # Retornar apenas o texto com um marcador especial
                return f"__H1_{len(headers_level1)-1}__\n"
                
            def store_header2(match):
                header_text = match.group(1).strip()
                headers_level2.append(header_text)
                # Retornar apenas o texto com um marcador especial
                return f"__H2_{len(headers_level2)-1}__\n"
            
            # Substituir cabeçalhos por marcadores temporários
            content = re.sub(r'^#\s+(.*?)$', store_header1, content, flags=re.MULTILINE)
            content = re.sub(r'^##\s+(.*?)$', store_header2, content, flags=re.MULTILINE)
            
            # Identificar itens de lista
            list_items = []
            def store_list_item(match):
                indentation = match.group(1)
                item_text = match.group(2).strip()
                list_items.append((indentation, item_text))
                # Retornar um marcador temporário
                return f"{indentation}__LIST_{len(list_items)-1}__\n"
            
            # Substituir itens de lista por marcadores temporários
            content = re.sub(r'^(\s*)[-*]\s+(.*?)$', store_list_item, content, flags=re.MULTILINE)
            
            # Identificar negrito
            bold_texts = []
            def store_bold(match):
                bold_text = match.group(1)
                bold_texts.append(bold_text)
                # Retornar apenas o texto com um marcador especial
                return f"__BOLD_{len(bold_texts)-1}__"
            
            # Substituir textos em negrito por marcadores temporários
            content = re.sub(r'\*\*(.*?)\*\*', store_bold, content)
            
            # Agora restaurar os elementos com formatação adequada
            
            # Restaurar cabeçalhos
            for i, header in enumerate(headers_level1):
                content = content.replace(f"__H1_{i}__", header)
            
            for i, header in enumerate(headers_level2):
                content = content.replace(f"__H2_{i}__", header)
            
            # Restaurar itens de lista
            for i, (indent, item) in enumerate(list_items):
                content = content.replace(f"{indent}__LIST_{i}__", f"{indent}{item}")
            
            # Restaurar textos em negrito
            for i, bold in enumerate(bold_texts):
                content = content.replace(f"__BOLD_{i}__", bold)
            
            # Restaurar links
            for i, (text, url) in enumerate(links):
                content = content.replace(f"__LINK_{i}__", text)
            
            # Garantir que cabeçalhos tenham espaço após # e ##
            content = re.sub(r'#([^#\s])', r'# \1', content)  # Corrigir #Título para # Título
            content = re.sub(r'##([^#\s])', r'## \1', content)  # Corrigir ##Título para ## Título
            
            # Garantir que listas tenham espaço após marcadores
            content = re.sub(r'^-([^\s])', r'- \1', content, flags=re.MULTILINE)
            content = re.sub(r'^\*([^\s])', r'* \1', content, flags=re.MULTILINE)
            
            # Adicionar espaços em branco após parágrafos para melhor separação
            content = re.sub(r'([^\n])\n([^#\s-*\n])', r'\1\n\n\2', content)
            
            # Garantir que links estejam formatados corretamente [texto](url)
            # Não altera links já corretos, mas pode corrigir alguns problemas comuns
            content = re.sub(r'\[(.*?)\]\s+\((.*?)\)', r'[\1](\2)', content)
            
            # Inserir conteúdo no documento
            logger.info("Inserindo conteúdo no documento...")
            
            # Preparar as solicitações para inserir texto e aplicar formatação
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': 1
                        },
                        'text': content
                    }
                }
            ]
            
            # Executar a inserção do texto
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
            
            # Aplicar formatação avançada após inserir o conteúdo
            self._format_simple_doc(docs_service, doc_id)
            
            # Configurar propriedades do documento para melhor visualização
            requests = [
                {
                    'updateDocumentStyle': {
                        'documentStyle': {
                            'marginTop': {'magnitude': 36, 'unit': 'PT'},
                            'marginBottom': {'magnitude': 36, 'unit': 'PT'},
                            'marginLeft': {'magnitude': 36, 'unit': 'PT'},
                            'marginRight': {'magnitude': 36, 'unit': 'PT'},
                            'pageSize': {
                                'width': {'magnitude': 612, 'unit': 'PT'},
                                'height': {'magnitude': 792, 'unit': 'PT'}
                            }
                        },
                        'fields': 'marginTop,marginBottom,marginLeft,marginRight,pageSize'
                    }
                }
            ]
            
            # Aplicar configurações de página
            try:
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()
                logger.info("Propriedades do documento configuradas com sucesso")
            except Exception as e:
                logger.error(f"Erro ao configurar propriedades do documento: {e}")
            
            # Se folder_id for fornecido, mover o documento para a pasta
            if folder_id:
                drive_service = self._get_drive_service()
                if drive_service:
                    try:
                        # Obter as pastas atuais do arquivo
                        file = drive_service.files().get(
                            fileId=doc_id, 
                            fields='parents'
                        ).execute()
                        
                        # Remover das pastas atuais e adicionar à nova pasta
                        previous_parents = ",".join(file.get('parents', []))
                        
                        # Mover para a nova pasta
                        drive_service.files().update(
                            fileId=doc_id,
                            addParents=folder_id,
                            removeParents=previous_parents,
                            fields='id, parents'
                        ).execute()
                        
                        logger.info(f"Documento movido para a pasta: {folder_id}")
                    except Exception as e:
                        logger.error(f"Erro ao mover documento para a pasta: {e}")
            
            logger.info(f"Documento criado com sucesso: {doc_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Erro ao criar documento no Google Drive: {e}", exc_info=True)
            return None
    
    def _format_simple_doc(self, docs_service, doc_id):
        """
        Aplica formatação avançada ao documento Google Docs, tratando Markdown.
        
        Args:
            docs_service: Serviço Google Docs
            doc_id: ID do documento
            
        Returns:
            True se sucesso, False se falhar
        """
        try:
            logger.info(f"Iniciando formatação avançada do documento {doc_id}...")
            
            # Obter o conteúdo do documento
            document = docs_service.documents().get(documentId=doc_id).execute()
            
            # Lista para armazenar as requisições de formatação
            requests = []
            
            # Iterar sobre o conteúdo do documento
            for content in document.get('body', {}).get('content', []):
                if 'paragraph' in content:
                    paragraph = content.get('paragraph', {})
                    elements = paragraph.get('elements', [])
                    
                    if not elements:
                        continue
                    
                    # Obter o texto do parágrafo
                    text = ''
                    for element in elements:
                        if 'textRun' in element:
                            text_run = element.get('textRun', {})
                            text += text_run.get('content', '')
                    
                    # Verificar se é um título (começa com # ou ##)
                    text = text.strip()
                    start_index = content.get('startIndex', 0)
                    end_index = content.get('endIndex', 0)
                    
                    # Formatação para cabeçalhos de nível 1 (# Título)
                    if text.startswith('# '):
                        # Remover os marcadores Markdown dos cabeçalhos
                        clean_text = text[2:].strip()
                        
                        # Atualizar o texto para remover os marcadores
                        requests.append({
                            'deleteContentRange': {
                                'range': {
                                    'startIndex': start_index,
                                    'endIndex': end_index
                                }
                            }
                        })
                        
                        requests.append({
                            'insertText': {
                                'location': {
                                    'index': start_index
                                },
                                'text': clean_text
                            }
                        })
                        
                        # Aplicar estilo de cabeçalho
                        requests.append({
                            'updateParagraphStyle': {
                                'range': {
                                    'startIndex': start_index,
                                    'endIndex': start_index + len(clean_text)
                                },
                                'paragraphStyle': {
                                    'namedStyleType': 'HEADING_1',
                                    'alignment': 'CENTER'
                                },
                                'fields': 'namedStyleType,alignment'
                            }
                        })
                        
                        # Aplicar formatação de texto para o cabeçalho
                        requests.append({
                            'updateTextStyle': {
                                'range': {
                                    'startIndex': start_index,
                                    'endIndex': start_index + len(clean_text)
                                },
                                'textStyle': {
                                    'bold': True,
                                    'fontSize': {
                                        'magnitude': 16,
                                        'unit': 'PT'
                                    }
                                },
                                'fields': 'bold,fontSize'
                            }
                        })
                        
                    # Formatação para cabeçalhos de nível 2 (## Título)
                    elif text.startswith('## '):
                        # Remover os marcadores Markdown dos cabeçalhos
                        clean_text = text[3:].strip()
                        
                        # Atualizar o texto para remover os marcadores
                        requests.append({
                            'deleteContentRange': {
                                'range': {
                                    'startIndex': start_index,
                                    'endIndex': end_index
                                }
                            }
                        })
                        
                        requests.append({
                            'insertText': {
                                'location': {
                                    'index': start_index
                                },
                                'text': clean_text
                            }
                        })
                        
                        # Aplicar estilo de cabeçalho
                        requests.append({
                            'updateParagraphStyle': {
                                'range': {
                                    'startIndex': start_index,
                                    'endIndex': start_index + len(clean_text)
                                },
                                'paragraphStyle': {
                                    'namedStyleType': 'HEADING_2'
                                },
                                'fields': 'namedStyleType'
                            }
                        })
                        
                        # Aplicar formatação de texto para o cabeçalho
                        requests.append({
                            'updateTextStyle': {
                                'range': {
                                    'startIndex': start_index,
                                    'endIndex': start_index + len(clean_text)
                                },
                                'textStyle': {
                                    'bold': True,
                                    'fontSize': {
                                        'magnitude': 14,
                                        'unit': 'PT'
                                    }
                                },
                                'fields': 'bold,fontSize'
                            }
                        })
                    
                    # Formatação para listas com marcadores (linhas que começam com - ou *)
                    elif text.lstrip().startswith(('-', '*')) and len(text.lstrip()) > 2:
                        # Remover o marcador de lista do texto
                        indentation = len(text) - len(text.lstrip())
                        prefix = text[:indentation]
                        marker = text[indentation]
                        rest_text = text[indentation + 1:].strip()
                        clean_text = prefix + rest_text
                        
                        # Atualizar o texto para remover os marcadores
                        requests.append({
                            'deleteContentRange': {
                                'range': {
                                    'startIndex': start_index,
                                    'endIndex': end_index
                                }
                            }
                        })
                        
                        requests.append({
                            'insertText': {
                                'location': {
                                    'index': start_index
                                },
                                'text': clean_text
                            }
                        })
                        
                        # Aplicar estilo de lista com marcadores
                        requests.append({
                            'createParagraphBullets': {
                                'range': {
                                    'startIndex': start_index,
                                    'endIndex': start_index + len(clean_text)
                                },
                                'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                            }
                        })
                        
                    # Formatação para tabelas básicas (linhas que começam com |)
                    elif text.startswith('|') and text.endswith('|') and '|' in text[1:-1]:
                        # Deixar a formatação de tabela como está por enquanto
                        # O processamento de tabelas é mais complexo e pode exigir
                        # um tratamento especial de várias linhas consecutivas
                        pass
                        
                    # Formatação para texto em negrito (**texto**)
                    bold_matches = list(re.finditer(r'\*\*(.*?)\*\*', text))
                    
                    if bold_matches:
                        # Se temos marcadores de negrito, precisamos remover e aplicar formatação
                        # Começamos de trás para frente para não afetar os índices
                        offset = 0
                        for match in reversed(bold_matches):
                            bold_text = match.group(1)  # O texto entre **
                            full_match = match.group(0)  # O texto completo com **
                            
                            match_start = start_index + match.start()
                            match_end = start_index + match.end()
                            
                            # Remover os marcadores de negrito
                            requests.append({
                                'deleteContentRange': {
                                    'range': {
                                        'startIndex': match_start,
                                        'endIndex': match_end
                                    }
                                }
                            })
                            
                            # Inserir apenas o texto sem os marcadores
                            requests.append({
                                'insertText': {
                                    'location': {
                                        'index': match_start
                                    },
                                    'text': bold_text
                                }
                            })
                            
                            # Aplicar formatação em negrito
                            requests.append({
                                'updateTextStyle': {
                                    'range': {
                                        'startIndex': match_start,
                                        'endIndex': match_start + len(bold_text)
                                    },
                                    'textStyle': {
                                        'bold': True
                                    },
                                    'fields': 'bold'
                                }
                            })
                            
                            # Atualizar o final do parágrafo para refletir a remoção dos marcadores
                            end_index -= (len(full_match) - len(bold_text))
                    
                    # Formatação para seções especiais (emojis de prioridade)
                    if "🔴" in text or "🟠" in text or "🟢" in text or "⚪" in text:
                        # Destacar linhas com emojis (geralmente títulos de seção)
                        requests.append({
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
                    
                    # Formatação para links no formato [texto](url)
                    # Esta é uma abordagem melhorada para remover completamente a sintaxe Markdown
                    link_pattern = re.finditer(r'\[(.*?)\]\((.*?)\)', text)
                    link_matches = list(link_pattern)
                    
                    if link_matches:
                        # Se temos links, precisamos processá-los de trás para frente
                        # para não afetar os índices
                        for match in reversed(link_matches):
                            full_match = match.group(0)
                            link_text = match.group(1)
                            link_url = match.group(2)
                            
                            link_start = start_index + match.start()
                            link_end = start_index + match.end()
                            
                            # 1. Remover o texto do link na formatação Markdown
                            requests.append({
                                'deleteContentRange': {
                                    'range': {
                                        'startIndex': link_start,
                                        'endIndex': link_end
                                    }
                                }
                            })
                            
                            # 2. Inserir apenas o texto do link
                            requests.append({
                                'insertText': {
                                    'location': {
                                        'index': link_start
                                    },
                                    'text': link_text
                                }
                            })
                            
                            # 3. Adicionar o link ao texto
                            requests.append({
                                'updateTextStyle': {
                                    'range': {
                                        'startIndex': link_start,
                                        'endIndex': link_start + len(link_text)
                                    },
                                    'textStyle': {
                                        'link': {
                                            'url': link_url
                                        }
                                    },
                                    'fields': 'link'
                                }
                            })
                            
                            # Atualizar o final do parágrafo para refletir a remoção dos marcadores
                            end_index -= (len(full_match) - len(link_text))
            
            # Aplicar as formatações
            if requests:
                # Dividir em blocos menores para evitar erro de tamanho máximo da requisição
                max_batch_size = 100  # Número máximo de operações por lote
                for i in range(0, len(requests), max_batch_size):
                    batch = requests[i:i + max_batch_size]
                    logger.info(f"Aplicando lote de {len(batch)} formatações...")
                    try:
                        docs_service.documents().batchUpdate(
                            documentId=doc_id,
                            body={'requests': batch}
                        ).execute()
                    except Exception as e:
                        logger.error(f"Erro ao aplicar lote de formatações: {e}")
                
                logger.info("Formatação aplicada com sucesso")
                return True
            else:
                logger.info("Nenhuma formatação para aplicar")
                return True
            
        except Exception as e:
            logger.error(f"Erro na formatação do documento: {e}")
            return False

    def _get_docs_service(self):
        """
        Inicializa e retorna o serviço Google Docs.
        
        Returns:
            Serviço Google Docs ou None se falhar
        """
        try:
            # Usar as credenciais já inicializadas no construtor
            if not self.credentials:
                logger.error("Credenciais do Google não disponíveis")
                return None
            
            return build('docs', 'v1', credentials=self.credentials)
        except Exception as e:
            logger.error(f"Erro ao inicializar serviço Google Docs: {e}")
            return None