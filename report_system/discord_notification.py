"""
Gerenciador de notificações do Discord usando a API REST direta.
"""

import logging
import requests
import json
import os
import time
from typing import Optional, Dict, Any, List, Tuple, Union

logger = logging.getLogger(__name__)

class DiscordNotificationManager:
    """Gerencia o envio de notificações para canais do Discord via API REST."""
    
    def __init__(self, config_manager=None):
        """
        Inicializa o gerenciador de notificações do Discord.
        
        Args:
            config_manager: Gerenciador de configuração (opcional)
        """
        logger.info("Inicializando DiscordNotificationManager")
        self.config = config_manager
        
        # Obter o token do Discord
        self.discord_token = self._get_discord_token()
        
        if not self.discord_token:
            logger.warning("Token do Discord não configurado. As notificações não funcionarão.")
    
    def _get_discord_token(self) -> str:
        """
        Obtém o token do Discord das variáveis de ambiente ou configuração.
        
        Returns:
            Token do Discord ou string vazia
        """
        token = ""
        
        # Tentar obter do ConfigManager se disponível
        if self.config:
            try:
                # Tentar diferentes métodos de acesso à configuração
                if hasattr(self.config, 'get_env_var') and callable(getattr(self.config, 'get_env_var')):
                    token = self.config.get_env_var("DISCORD_TOKEN", "")
                elif hasattr(self.config, 'get') and callable(getattr(self.config, 'get')):
                    token = self.config.get("DISCORD_TOKEN", "")
                elif hasattr(self.config, 'DISCORD_TOKEN'):
                    token = self.config.DISCORD_TOKEN
                elif hasattr(self.config, '__getitem__') and callable(getattr(self.config, '__getitem__')):
                    try:
                        token = self.config["DISCORD_TOKEN"]
                    except (KeyError, TypeError):
                        pass
            except Exception as e:
                logger.error(f"Erro ao obter token do Discord do ConfigManager: {e}")
        
        # Se não conseguiu ou não tem ConfigManager, tenta variáveis de ambiente
        if not token:
            token = os.getenv("DISCORD_TOKEN", "")
            
        # Tentar também DISCORD_BOT_TOKEN
        if not token:
            token = os.getenv("DISCORD_BOT_TOKEN", "")
            
        # Verificar se é webhook URL e extrair o token se for
        if not token and self.config and hasattr(self.config, 'discord_webhook_url'):
            webhook_url = self.config.discord_webhook_url
            if webhook_url and '/api/webhooks/' in webhook_url:
                try:
                    # Formato webhook: https://discord.com/api/webhooks/ID/TOKEN
                    token = webhook_url.split('/')[-1]
                    logger.info("Token extraído de webhook URL")
                except Exception:
                    pass
                
        # Remover possíveis aspas e espaços
        if token:
            token = token.strip().strip('"\'')
        
        # Não logar o token completo por segurança
        if token:
            # Mascarar o token nos logs
            masked_token = token[:5] + '*' * 15 if len(token) > 5 else '*' * len(token)
            logger.info(f"Token do Discord obtido: {masked_token}")
        
        return token
    
    def _validate_channel_id(self, channel_id: str) -> str:
        """
        Valida e limpa o ID do canal.
        
        Args:
            channel_id: ID do canal a ser validado
            
        Returns:
            ID do canal limpo (apenas dígitos)
        """
        if not channel_id:
            return ""
            
        # Extrair apenas os dígitos
        clean_id = ''.join(c for c in channel_id if c.isdigit())
        
        # Verificar se houve alteração
        if clean_id != channel_id:
            logger.info(f"ID do canal foi limpo: '{channel_id}' -> '{clean_id}'")
            
        return clean_id
    
    def _format_token(self, token: str) -> str:
        """
        Formata o token conforme necessário para a API do Discord.
        
        Args:
            token: Token original
            
        Returns:
            Token formatado
        """
        if not token:
            return ""
        
        # Se o token já tem um prefixo, não adicione outro
        # Os prefixos válidos são: "Bot ", "Bearer "
        if token.startswith(("Bot ", "Bearer ")):
            return token
            
        # IMPORTANTE: Verificar se é um token de bot (geralmente começa com MT, MT0, NjU, etc.)
        # ou um token de webhook (que não precisa de prefixo)
        # ou um token de OAuth2 (que usa Bearer)
        
        # Verificar características típicas de um token de bot
        if any(token.startswith(prefix) for prefix in ["MT", "NT", "MT0", "NjU", "ODg"]):
            logger.debug("Token detectado como token de bot")
            return f"Bot {token}"
        elif token.startswith(("ghp_", "gho_")):
            logger.debug("Token detectado como token OAuth2 GitHub")
            return f"Bearer {token}"
        else:
            # Para webhooks e tokens de usuário
            logger.debug("Token tratado como token genérico (possivelmente webhook)")
            return token
    
    def _split_long_message(self, message: str, max_length: int = 4000) -> List[str]:
        """
        Divide uma mensagem longa em partes menores que o limite do Discord.
        
        Args:
            message: Mensagem original
            max_length: Tamanho máximo de cada parte (default: 4000)
            
        Returns:
            Lista de partes da mensagem
        """
        if len(message) <= max_length:
            return [message]
            
        parts = []
        current_part = ""
        
        # Dividir por linhas para manter a formatação
        lines = message.split('\n')
        
        for line in lines:
            # Se a linha atual + a próxima linha exceder o limite
            if len(current_part) + len(line) + 1 > max_length:
                if current_part:
                    parts.append(current_part.strip())
                current_part = line
            else:
                if current_part:
                    current_part += '\n' + line
                else:
                    current_part = line
        
        # Adicionar a última parte se houver
        if current_part:
            parts.append(current_part.strip())
            
        return parts

    def send_notification(self, channel_id: str, message: str, embeds: Optional[List[Dict[str, Any]]] = None, 
                   max_retries: int = 3, retry_delay: float = 2.0, return_message_id: bool = False) -> Union[bool, str]:
        """
        Envia uma notificação para um canal do Discord.
        
        Args:
            channel_id: ID do canal
            message: Mensagem a ser enviada
            embeds: Lista de embeds (opcional)
            max_retries: Número máximo de tentativas
            retry_delay: Delay entre tentativas em segundos (default: 2.0)
            return_message_id: Se True, retorna o ID da mensagem em vez de bool
            
        Returns:
            True se enviado com sucesso, False caso contrário
            Se return_message_id=True, retorna o ID da mensagem ou False
        """
        if not self.discord_token:
            logger.error("Token do Discord não configurado")
            return False
            
        channel_id = self._validate_channel_id(channel_id)
        if not channel_id:
            logger.error("ID do canal inválido")
            return False
            
        # Dividir mensagem longa em partes
        message_parts = self._split_long_message(message)
        
        last_message_id = None
        success = True
        
        for i, part in enumerate(message_parts):
            # Adicionar indicador de parte se houver mais de uma
            if len(message_parts) > 1:
                part = f"Parte {i+1}/{len(message_parts)}:\n{part}"
                
            # Usar embeds apenas na última parte
            current_embeds = embeds if i == len(message_parts) - 1 else None
            
            # Aumentar o delay entre partes de uma mensagem longa
            current_retry_delay = retry_delay * (1.5 ** i)  # Backoff exponencial entre partes
            
            result = self._send_single_notification(
                channel_id, part, current_embeds,
                max_retries, current_retry_delay, return_message_id
            )
            
            if not result:
                success = False
                break
                
            if return_message_id:
                last_message_id = result
                
            # Aguardar entre partes da mensagem
            if i < len(message_parts) - 1:  # Não esperar após a última parte
                wait_time = 3.0 * (1.5 ** i)  # Aumenta o tempo de espera entre partes
                logger.info(f"Aguardando {wait_time:.1f} segundos antes de enviar a próxima parte...")
                time.sleep(wait_time)
                
        return last_message_id if return_message_id else success

    def _send_single_notification(self, channel_id: str, message: str, embeds: Optional[List[Dict[str, Any]]] = None,
                           max_retries: int = 3, retry_delay: float = 2.0, return_message_id: bool = False) -> Union[bool, str]:
        """
        Envia uma única parte de uma notificação.
        """
        headers = {
            "Authorization": f"Bot {self.discord_token}",
            "Content-Type": "application/json"
        }
        
        payload = {"content": message}
        if embeds:
            payload["embeds"] = embeds
            
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        
        for attempt in range(max_retries):
            try:
                # Aumentar o delay entre tentativas
                current_delay = retry_delay * (2 ** attempt)  # Backoff exponencial
                if attempt > 0:
                    logger.info(f"Tentativa {attempt + 1}/{max_retries}. Aguardando {current_delay:.1f} segundos...")
                    time.sleep(current_delay)
                
                response = requests.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    if return_message_id:
                        return response.json()["id"]
                    return True
                    
                elif response.status_code == 401:
                    logger.error(f"Token inválido (401 Unauthorized). Resposta: {response.text}")
                    return False
                    
                elif response.status_code == 429:  # Rate limit
                    retry_after = float(response.headers.get('Retry-After', current_delay))
                    logger.warning(f"Rate limit atingido. Aguardando {retry_after:.1f} segundos...")
                    time.sleep(retry_after)
                    continue
                    
                else:
                    logger.error(f"Erro ao enviar notificação. Status: {response.status_code}, Resposta: {response.text}")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return False
                        
            except Exception as e:
                logger.error(f"Erro ao enviar notificação: {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    return False
                    
        return False
    
    def _send_webhook_notification(self, webhook_url: str, message: str, 
                                embeds: Optional[List[Dict[str, Any]]] = None,
                                max_retries: int = 3, retry_delay: float = 1.0, 
                                return_message_id: bool = False) -> Union[bool, str]:
        """
        Envia uma notificação usando um webhook do Discord.
        
        Args:
            webhook_url: URL do webhook do Discord ou ID do webhook
            message: Mensagem a ser enviada
            embeds: Lista de embeds para incluir na mensagem (opcional)
            max_retries: Número máximo de tentativas em caso de falha
            retry_delay: Tempo de espera entre tentativas (em segundos)
            return_message_id: Se True, retorna o ID da mensagem em vez de um booleano
            
        Returns:
            True/ID da mensagem se enviado com sucesso, False/None caso contrário
        """
        # Determinar a URL completa do webhook
        if not webhook_url.startswith(('https://', 'http://')):
            # Se for apenas o ID, usar o token armazenado para construir a URL
            if self.discord_token:
                webhook_url = f"https://discord.com/api/webhooks/{webhook_url}/{self.discord_token}"
            else:
                logger.error("Token não disponível para construir URL do webhook")
                return False if not return_message_id else None
                
        # Payload
        payload = {
            "content": message
        }
        
        # Adicionar embeds se fornecidos
        if embeds:
            payload["embeds"] = embeds
        
        # Headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # Tentativas com backoff exponencial
        for attempt in range(max_retries):
            try:
                logger.info(f"Enviando mensagem para webhook (tentativa {attempt+1}/{max_retries})")
                
                response = requests.post(
                    webhook_url,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=10  # 10 segundos de timeout
                )
                
                if response.status_code in [200, 201, 204]:
                    logger.info(f"Notificação webhook enviada com sucesso. Status: {response.status_code}")
                    
                    # Se precisamos retornar o ID da mensagem
                    if return_message_id:
                        try:
                            message_data = response.json()
                            return message_data.get('id')
                        except Exception as e:
                            logger.error(f"Erro ao extrair ID da mensagem do webhook: {e}")
                            return None
                    
                    return True
                
                # Tratamento especial para rate limiting
                if response.status_code == 429:
                    try:
                        retry_info = response.json()
                        retry_after = retry_info.get('retry_after', retry_delay)
                        global_rate_limit = retry_info.get('global', False)
                        
                        if global_rate_limit:
                            logger.warning(f"Rate limit GLOBAL atingido no webhook. Aguardando {retry_after} segundos...")
                        else:
                            logger.warning(f"Rate limit atingido no webhook. Aguardando {retry_after} segundos...")
                        
                        # Adicionamos 1s de margem para garantir
                        time.sleep(retry_after + 1)
                    except Exception as e:
                        # Se não conseguimos extrair o retry_after, usamos o valor padrão
                        logger.warning(f"Erro ao extrair retry_after: {e}. Usando valor padrão de {retry_delay}s.")
                        time.sleep(retry_delay * (2 ** attempt))  # Backoff exponencial
                    continue
                
                logger.error(f"Erro ao enviar notificação webhook. Status: {response.status_code}, Resposta: {response.text}")
                
                # Se for um erro permanente, não faz sentido tentar novamente
                if response.status_code in [400, 401, 403, 404]:
                    return False if not return_message_id else None
                
                # Backoff exponencial para outras falhas
                delay = retry_delay * (2 ** attempt)
                logger.info(f"Aguardando {delay:.2f} segundos antes da próxima tentativa")
                time.sleep(delay)
                
            except requests.RequestException as e:
                logger.error(f"Erro de requisição HTTP ao webhook: {str(e)}")
                
                # Backoff exponencial
                delay = retry_delay * (2 ** attempt)
                logger.info(f"Aguardando {delay:.2f} segundos antes da próxima tentativa")
                time.sleep(delay)
        
        logger.error(f"Todas as {max_retries} tentativas falharam para webhook")
        return False if not return_message_id else None
    
    def update_message(self, channel_id: str, message_id: str, new_content: str,
                       embeds: Optional[List[Dict[str, Any]]] = None,
                       max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """
        Atualiza o conteúdo de uma mensagem existente.
        
        Args:
            channel_id: ID do canal
            message_id: ID da mensagem a ser atualizada
            new_content: Novo conteúdo da mensagem
            embeds: Lista de embeds para incluir na mensagem (opcional)
            max_retries: Número máximo de tentativas em caso de falha
            retry_delay: Tempo de espera entre tentativas (em segundos)
            
        Returns:
            True se atualizado com sucesso, False caso contrário
        """
        if not self.discord_token:
            logger.error("Token do Discord não configurado. Impossível atualizar mensagem.")
            return False
        
        if not message_id:
            logger.error("ID da mensagem não fornecido para atualização")
            return False
        
        # Limpar ID do canal
        clean_channel_id = self._validate_channel_id(channel_id)
        
        if not clean_channel_id:
            logger.error(f"ID do canal inválido: {channel_id}")
            return False
        
        # Tentar todas as variações possíveis do token
        token_variations = [
            self.discord_token,
            f"Bot {self.discord_token}",
            self.discord_token.replace("Bot ", "")
        ]
        
        # Payload
        payload = {
            "content": new_content
        }
        
        # Adicionar embeds se fornecidos
        if embeds:
            payload["embeds"] = embeds
        
        # Não podemos atualizar mensagens webhook, então verificamos se é um canal normal
        is_webhook = '/api/webhooks/' in clean_channel_id or clean_channel_id.startswith(('https://', 'http://'))
        
        if is_webhook:
            logger.error("Não é possível atualizar mensagens de webhook. Enviando nova mensagem.")
            return self.send_notification(channel_id, new_content, embeds)
        
        # Tentar todas as variações de token e retry
        for attempt in range(max_retries * len(token_variations)):
            token_index = attempt % len(token_variations)
            current_token = token_variations[token_index]
            
            try:
                # URL da API para atualizar mensagens
                url = f"https://discord.com/api/v9/channels/{clean_channel_id}/messages/{message_id}"
                
                # Headers
                headers = {
                    "Authorization": current_token,
                    "Content-Type": "application/json"
                }
                
                logger.info(f"Atualizando mensagem {message_id} no canal Discord {clean_channel_id}")
                
                response = requests.patch(
                    url,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=10  # 10 segundos de timeout
                )
                
                if response.status_code in [200, 201, 204]:
                    logger.info(f"Mensagem atualizada com sucesso. Status: {response.status_code}")
                    return True
                
                # Tratamento especial para rate limiting
                if response.status_code == 429:
                    try:
                        retry_info = response.json()
                        retry_after = retry_info.get('retry_after', retry_delay)
                        global_rate_limit = retry_info.get('global', False)
                        
                        if global_rate_limit:
                            logger.warning(f"Rate limit GLOBAL atingido ao atualizar mensagem. Aguardando {retry_after} segundos...")
                        else:
                            logger.warning(f"Rate limit atingido ao atualizar mensagem no canal {clean_channel_id}. Aguardando {retry_after} segundos...")
                        
                        # Adicionamos 1s de margem para garantir
                        time.sleep(retry_after + 1)
                    except Exception as e:
                        # Se não conseguimos extrair o retry_after, usamos o valor padrão
                        logger.warning(f"Erro ao extrair retry_after: {e}. Usando valor padrão de {retry_delay}s.")
                        time.sleep(retry_delay * (2 ** (attempt // len(token_variations))))  # Backoff exponencial
                    continue
                
                # Verificar se o problema é com o token
                if response.status_code == 401:
                    logger.error(f"Token inválido (401 Unauthorized). Resposta: {response.text}")
                    # A próxima iteração usará um formato de token diferente
                elif response.status_code == 404:
                    logger.error(f"Mensagem {message_id} não encontrada no canal {clean_channel_id}")
                    return False  # Não adianta tentar mais, mensagem não existe
                else:
                    logger.error(f"Erro ao atualizar mensagem. Status: {response.status_code}, Resposta: {response.text}")
                
                # Aguardar antes de tentar novamente
                if (attempt + 1) % len(token_variations) != 0:  # Se não é o último formato de token
                    continue  # Não aguardar, tentar próximo formato imediatamente
                
                # Backoff exponencial
                delay = retry_delay * (2 ** (attempt // len(token_variations)))
                logger.info(f"Aguardando {delay:.2f} segundos antes da próxima tentativa")
                time.sleep(delay)
                
            except requests.RequestException as e:
                logger.error(f"Erro de requisição HTTP: {str(e)}")
                
                # Backoff exponencial
                delay = retry_delay * (2 ** (attempt // len(token_variations)))
                logger.info(f"Aguardando {delay:.2f} segundos antes da próxima tentativa")
                time.sleep(delay)
        
        logger.error(f"Todas as {max_retries * len(token_variations)} tentativas de atualização falharam")
        return False
    
    def send_report_notification(self, project_id: str, project_name: str, channel_id: str,
                               doc_id: Optional[str] = None, folder_id: Optional[str] = None) -> bool:
        """
        Envia uma notificação formatada sobre relatório semanal.
        
        Args:
            project_id: ID do projeto
            project_name: Nome do projeto
            channel_id: ID do canal do Discord
            doc_id: ID do documento no Google Drive (opcional)
            folder_id: ID da pasta no Google Drive (opcional)
            
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not channel_id:
            logger.error(f"ID do canal não fornecido para projeto {project_id}")
            return False
        
        try:
            # Limpar o ID do canal
            clean_channel_id = self._validate_channel_id(channel_id)
            
            if not clean_channel_id:
                logger.error(f"ID do canal inválido após limpeza: '{channel_id}'")
                return False
            
            # Construir URLs se IDs forem fornecidos
            doc_url = None
            if doc_id:
                doc_url = f"https://drive.google.com/file/d/{doc_id}/view"
            
            folder_url = None
            if folder_id:
                folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
            
            # Construir a mensagem básica
            message = f"🔔🤖🔔 Relatório Semanal do {project_name} concluído com sucesso!✅\n Já disponivel na pasta do Drive: "
            
            # Adicionar links conforme disponibilidade
            if doc_url:
                message += f"\n    📄 Link para o relatório: {doc_url}"
            
            if folder_url:
                message += f"\n    📁 Link para a pasta do projeto: {folder_url}"
            
            # Adicionar timestamp
            current_time = time.strftime("%d/%m/%Y %H:%M")
            message += f"\n\n⏰ Gerado em: {current_time}"
            
            # Enviar a mensagem
            return self.send_notification(channel_id=clean_channel_id, message=message)
            
        except Exception as e:
            logger.error(f"Erro em send_report_notification para projeto {project_id}: {str(e)}")
            return False
    
    def send_direct_message(self, user_id: str, message: str, embeds: Optional[List[Dict[str, Any]]] = None,
                      max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """
        Envia uma mensagem direta para um usuário específico do Discord.
        
        Args:
            user_id: ID do usuário do Discord
            message: Mensagem a ser enviada
            embeds: Lista de embeds para incluir na mensagem (opcional)
            max_retries: Número máximo de tentativas em caso de falha
            retry_delay: Tempo de espera entre tentativas (em segundos)
            
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not self.discord_token:
            logger.error("Token do Discord não configurado. Impossível enviar mensagem direta.")
            return False
        
        # Limpar ID do usuário
        clean_user_id = self._validate_channel_id(user_id)  # Podemos reutilizar este método
        
        if not clean_user_id:
            logger.error(f"ID do usuário inválido: {user_id}")
            return False
        
        logger.info(f"Tentando enviar mensagem direta para o usuário {clean_user_id}")
        
        # Precisamos primeiro criar um canal DM com o usuário
        create_dm_url = "https://discord.com/api/v9/users/@me/channels"
        
        # Headers com o token formatado
        headers = {
            "Authorization": self._format_token(self.discord_token),
            "Content-Type": "application/json"
        }
        
        # Payload para criar o canal DM
        create_dm_payload = {
            "recipient_id": clean_user_id
        }
        
        # Tentar criar o canal DM
        try:
            create_dm_response = requests.post(
                create_dm_url,
                data=json.dumps(create_dm_payload),
                headers=headers,
                timeout=10
            )
            
            if create_dm_response.status_code not in [200, 201]:
                logger.error(f"Falha ao criar canal DM. Status: {create_dm_response.status_code}")
                if create_dm_response.status_code == 401:
                    logger.error("Token não autorizado para criar DMs. O token precisa ser de um bot com intents adequadas.")
                return False
            
            # Extrair o ID do canal DM da resposta
            dm_data = create_dm_response.json()
            dm_channel_id = dm_data.get('id')
            
            if not dm_channel_id:
                logger.error("Não foi possível obter o ID do canal DM")
                return False
            
            # Agora enviamos a mensagem para o canal DM
            return self.send_notification(
                channel_id=dm_channel_id,
                message=message,
                embeds=embeds,
                max_retries=max_retries,
                retry_delay=retry_delay
            )
            
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem direta: {e}")
            return False
    
    def send_admin_notification(self, message: str, embeds: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Envia uma notificação para o administrador usando o canal de administração configurado.
        
        Args:
            message: Mensagem a ser enviada
            embeds: Lista de embeds para incluir na mensagem (opcional)
            
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        # Primeiro tenta usar o canal de administração
        admin_channel_id = ""
        
        if self.config:
            try:
                if hasattr(self.config, 'get_env_var') and callable(getattr(self.config, 'get_env_var')):
                    admin_channel_id = self.config.get_env_var("DISCORD_ADMIN_CHANNEL_ID", "")
            except Exception:
                pass
        
        if not admin_channel_id or admin_channel_id == "COLOQUE_AQUI_O_ID_DO_CANAL":
            admin_channel_id = os.getenv("DISCORD_ADMIN_CHANNEL_ID", "")
        
        # Usar o canal se estiver configurado
        if admin_channel_id and admin_channel_id != "COLOQUE_AQUI_O_ID_DO_CANAL":
            logger.info(f"Enviando notificação para o canal de administração {admin_channel_id}")
            return self.send_notification(
                channel_id=admin_channel_id,
                message=message,
                embeds=embeds
            )
            
        # Caso contrário, tenta usar DM como fallback (menos provável de funcionar)
        # Obter o ID do administrador do Discord
        admin_id = ""
        
        if self.config:
            try:
                if hasattr(self.config, 'get_env_var') and callable(getattr(self.config, 'get_env_var')):
                    admin_id = self.config.get_env_var("DISCORD_ADMIN_USER_ID", "")
            except Exception:
                pass
        
        if not admin_id:
            admin_id = os.getenv("DISCORD_ADMIN_USER_ID", "")
        
        if not admin_id or admin_id == "SEU_ID_AQUI":
            logger.warning("Nem o canal nem o ID do administrador foram configurados corretamente. Impossível enviar notificação.")
            return False
        
        logger.info(f"Tentando enviar DM para o usuário {admin_id} (pode falhar se o token não tiver permissões adequadas)")
        return self.send_direct_message(
            user_id=admin_id,
            message=message,
            embeds=embeds
        )