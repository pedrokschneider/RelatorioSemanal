"""
Gerenciador de operações com Google Docs e Gmail.
"""

import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from googleapiclient.discovery import build

from ..config import ConfigManager

logger = logging.getLogger("ReportSystem")

class GoogleDocsManager:
    """Gerencia operações com Google Docs e Gmail."""
    
    def __init__(self, config: ConfigManager):
        """
        Inicializa o gerenciador do Google Docs.
        
        Args:
            config: Instância do ConfigManager
        """
        self.config = config
        self.credentials = config.get_google_creds()
        self.docs_service = self._get_docs_service()
        self.gmail_service = self._get_gmail_service()
    
    def _get_docs_service(self):
        """Cria e retorna o serviço do Google Docs."""
        if not self.credentials:
            return None
        
        try:
            from googleapiclient.discovery import build
            return build('docs', 'v1', credentials=self.credentials)
        except Exception as e:
            logger.error(f"Erro ao criar serviço do Docs: {e}")
            return None
        """Cria e retorna o serviço do Gmail."""
        if not self.credentials:
            return None
        
        try:
            from googleapiclient.discovery import build
            return build('gmail', 'v1', credentials=self.credentials)
        except Exception as e:
            logger.error(f"Erro ao criar serviço do Gmail: {e}")
            return None
    
    def create_google_doc(self, title: str, content: str, parent_folder_id: Optional[str] = None) -> Optional[str]:
        # Código existente...
        
        # Criar documento vazio
        doc = self.docs_service.documents().create(body={'title': title}).execute()
        document_id = doc.get('documentId')
        
        # Processar links markdown antes de inserir
        import re
        
        # Inserir conteúdo no documento
        if document_id:
            # Encontrar links markdown no formato [texto](url)
            markdown_links = re.findall(r'\[(.*?)\]\((.*?)\)', content)
            
            # Substituir links por texto simples temporariamente
            processed_content = content
            for i, (link_text, url) in enumerate(markdown_links):
                # Substituir o link por um marcador único
                marker = f"{{LINK_{i}}}"
                processed_content = processed_content.replace(f"[{link_text}]({url})", marker)
            
            # Inserir o texto com marcadores
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': 1
                        },
                        'text': processed_content
                    }
                }
            ]
            
            # Executar a inserção de texto
            self.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()
            
            # Obter o documento para encontrar as posições dos marcadores
            doc = self.docs_service.documents().get(documentId=document_id).execute()
            content_text = doc.get('body', {}).get('content', [])
            
            # Substituir os marcadores por links reais
            link_requests = []
            for i, (link_text, url) in enumerate(markdown_links):
                marker = f"{{LINK_{i}}}"
                
                # Encontrar o marcador no documento
                start_index = None
                end_index = None
                
                for item in content_text:
                    if 'paragraph' in item:
                        for element in item.get('paragraph', {}).get('elements', []):
                            if 'textRun' in element:
                                text = element.get('textRun', {}).get('content', '')
                                if marker in text:
                                    element_start = element.get('startIndex', 0)
                                    marker_start = text.index(marker)
                                    start_index = element_start + marker_start
                                    end_index = start_index + len(marker)
                                    break
                    if start_index is not None:
                        break
                
                if start_index is not None and end_index is not None:
                    # Adicionar solicitação para substituir o marcador pelo texto do link
                    link_requests.append({
                        'replaceText': {
                            'text': link_text,
                            'startIndex': start_index,
                            'endIndex': end_index
                        }
                    })
                    
                    # Adicionar solicitação para aplicar o link
                    link_requests.append({
                        'updateTextStyle': {
                            'range': {
                                'startIndex': start_index,
                                'endIndex': start_index + len(link_text)
                            },
                            'textStyle': {
                                'link': {
                                    'url': url
                                }
                            },
                            'fields': 'link'
                        }
                    })
            
            # Executar as solicitações de links
            if link_requests:
                self.docs_service.documents().batchUpdate(
                    documentId=document_id,
                    body={'requests': link_requests}
                ).execute()
            
            return document_id
        
        return None
        """
        Obtém o ID de um template do Gmail procurando por uma label específica.
        
        Args:
            template_label: Nome da label que identifica o template
            
        Returns:
            ID do template ou None se não encontrado
        """
        if not self.gmail_service:
            logger.error("Serviço do Gmail não disponível")
            return None
            
        try:
            # Buscar ID da label
            labels = self.gmail_service.users().labels().list(userId='me').execute()
            label_id = None
            
            for label in labels.get('labels', []):
                if label['name'].lower() == template_label.lower():
                    label_id = label['id']
                    break
            
            if not label_id:
                logger.error(f"Label para template '{template_label}' não encontrada")
                return None
            
            # Buscar mensagens com essa label
            response = self.gmail_service.users().messages().list(
                userId='me',
                labelIds=[label_id],
                maxResults=1
            ).execute()
            
            messages = response.get('messages', [])
            
            if not messages:
                logger.error(f"Nenhuma mensagem encontrada com a label '{template_label}'")
                return None
            
            # Pegar o primeiro template encontrado
            template_id = messages[0]['id']
            logger.info(f"Template encontrado com ID: {template_id}")
            
            return template_id
            
        except Exception as e:
            logger.error(f"Erro ao buscar template do Gmail: {e}")
            return None
