import os
import sys
import subprocess
import logging
import requests
import json
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv

# Importar nossa nova classe ReportQueue
from report_queue import ReportQueue
from report_system.utils import extract_discord_channel_id

# Configurar logging
# Criar diretório de logs se não existir
log_dir = os.path.join(os.getcwd(), "logs")
os.makedirs(log_dir, exist_ok=True)

# Criar arquivo de log específico para o bot
today_str = datetime.now().strftime("%Y-%m-%d")
bot_log_file = os.path.join(log_dir, f"discord_bot_{today_str}.log")

# Configurar logger do bot
bot_logger = logging.getLogger("DiscordBot")
bot_logger.setLevel(logging.DEBUG)  # Definir para DEBUG para capturar mais detalhes

# Criar handler para arquivo
file_handler = logging.FileHandler(bot_log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Adicionar handler ao logger
bot_logger.addHandler(file_handler)

# Continuar usando logger ao invés de bot_logger no resto do código para manter compatibilidade
logger = bot_logger

# Adicionar diretório ao path (mesma lógica do run.py)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

class DiscordBotAutoChannels:
    """Bot do Discord que obtém canais automaticamente da planilha de configuração."""
    
    def __init__(self):
        """Inicializa o bot com acesso ao sistema de relatórios."""
        logger.info("Inicializando bot Discord 🤖")
        
        try:
            # Importar aqui para evitar problemas de importação
            from report_system.main import WeeklyReportSystem
            from report_system.discord_notification import DiscordNotificationManager
            
            # Tente inicializar com uma flag para ignorar módulos problemáticos
            self.report_system = WeeklyReportSystem(verbose_init=False)
            
            logger.info("Sistema de relatórios inicializado com sucesso")
            
            # Obter o mesmo gerenciador de notificações que o sistema usa
            self.discord = self.report_system.discord
            
            if not self.discord:
                logger.warning("Gerenciador de Discord não inicializado no sistema de relatórios")
                logger.info("Criando um gerenciador de Discord próprio")
                self.discord = DiscordNotificationManager(self.report_system.config)
            
            # Token para API e endpoints
            self.token = self.discord.discord_token if hasattr(self.discord, 'discord_token') else os.getenv('DISCORD_TOKEN', '')
            self.api_endpoint = 'https://discord.com/api/v10'
            
            # Armazenar informações dos canais/projetos
            self.channels_info = {}
            
            # Lista de bots autorizados para executar comandos
            self.authorized_bots = self._load_authorized_bots()
            
            # Inicializar o sistema de filas com 3 workers por padrão (aumentado para melhor performance)
            from report_queue import ReportQueue  # Importação explícita
            self.queue_system = ReportQueue(self, max_workers=3)
            logger.info("Sistema de filas inicializado com sucesso")
            
            # Verificar se a inicialização foi bem sucedida
            if not hasattr(self, 'queue_system') or not self.queue_system:
                logger.error("Falha ao inicializar sistema de filas")
            else:
                logger.info("Sistema de filas inicializado com sucesso")


        except ImportError as e:
            logger.error(f"Erro de importação ao inicializar sistema de relatórios: {e}", exc_info=True)
            raise

        except Exception as e:
            logger.error(f"Erro ao inicializar o sistema de relatórios: {e}", exc_info=True)
            raise
        
    def get_channels_from_spreadsheet(self):
        """
        Obtém todos os canais Discord da planilha de configuração.
        
        Returns:
            dict: Dicionário com {canal_id: project_info}
        """
        try:
            # Carregar a planilha de configuração
            projects_df = self.report_system._load_project_config()
            
            if projects_df is None or projects_df.empty:
                logger.error("Planilha de configuração vazia ou inacessível")
                return {}
                
            # Verificar se as colunas necessárias existem
            if 'discord_id' not in projects_df.columns:
                logger.error(f"Coluna 'discord_id' não encontrada. Colunas disponíveis: {', '.join(projects_df.columns)}")
                return {}
                
            # Verificar se há coluna relatoriosemanal_status
            if 'relatoriosemanal_status' in projects_df.columns:
                # Filtrar apenas projetos ativos
                active_projects = projects_df[projects_df['relatoriosemanal_status'].str.lower() == 'sim']
                logger.debug(f"Filtrando projetos ativos: {len(active_projects)}/{len(projects_df)}")
            else:
                # Se não houver coluna relatoriosemanal_status, considerar todos
                active_projects = projects_df
                logger.debug(f"Coluna 'relatoriosemanal_status' não encontrada, considerando todos os {len(projects_df)} projetos")
            
            # Filtrar projetos com discord_id preenchido
            projects_with_channel = active_projects[active_projects['discord_id'].notna()]
            
            # Criar dicionário de canal -> informações do projeto
            channels_dict = {}
            
            for _, row in projects_with_channel.iterrows():
                channel_id = str(row['discord_id']).strip()
                project_id = str(row.get('construflow_id', '')).strip()
                project_name = str(row.get('Projeto - PR', 'Projeto sem nome')).strip()

                # Extrair channel ID (suporta URLs e IDs raw)
                channel_id_clean = extract_discord_channel_id(channel_id)
                
                if channel_id_clean:
                    channels_dict[channel_id_clean] = {
                        'project_id': project_id,
                        'project_name': project_name
                    }
            
            # Adicionar o canal admin à lista de canais monitorados
            admin_channel_id = self.report_system.config.get_discord_admin_channel_id()
            if admin_channel_id:
                admin_channel_clean = extract_discord_channel_id(admin_channel_id)
                if admin_channel_clean:
                    channels_dict[admin_channel_clean] = {
                        'project_id': 'ADMIN',
                        'project_name': 'Canal Administrativo'
                    }
                    logger.info(f"Canal admin adicionado à lista de monitoramento: {admin_channel_clean}")
            
            logger.info(f"Encontrados {len(channels_dict)} canais ativos na planilha (incluindo admin)")
            
            # Exibir os canais apenas em nível DEBUG
            for channel, info in channels_dict.items():
                logger.debug(f"Canal: {channel} -> Projeto: {info['project_name']} (ID: {info['project_id']})")
            
            # Armazenar para uso em outras funções
            self.channels_info = channels_dict
            
            return channels_dict
            
        except Exception as e:
            logger.error(f"Erro ao obter canais da planilha: {e}")
            return {}
    
    def get_project_name(self, channel_id):
        """
        Obtém o nome do projeto associado a um canal.
        
        Args:
            channel_id: ID do canal
            
        Returns:
            str: Nome do projeto ou "projeto" se não encontrado
        """
        if channel_id in self.channels_info:
            return self.channels_info[channel_id]['project_name']
        return "projeto"
    
    def validate_channel_for_reports(self, channel_id):
        """
        Valida se um canal está configurado corretamente para gerar relatórios.
        
        Args:
            channel_id: ID do canal
            
        Returns:
            dict: Dicionário com informações de validação
        """
        try:
            # Carregar a planilha de configuração
            projects_df = self.report_system._load_project_config()
            
            if projects_df is None or projects_df.empty:
                return {
                    'valid': False,
                    'reason': 'config_error',
                    'message': '❌ **Erro de Configuração**\n\nNão foi possível acessar a planilha de configuração. Contate o time de Dados e Tecnologia.'
                }
            
            # Verificar se as colunas necessárias existem
            if 'discord_id' not in projects_df.columns:
                return {
                    'valid': False,
                    'reason': 'config_error',
                    'message': '❌ **Erro de Configuração**\n\nColuna "discord_id" não encontrada na planilha. Contate o time de Dados e Tecnologia.'
                }
            
            # Buscar o projeto pelo canal
            channel_id_clean = extract_discord_channel_id(str(channel_id))

            # Procurar o projeto na planilha
            project_row = None
            for _, row in projects_df.iterrows():
                row_channel_clean = extract_discord_channel_id(str(row['discord_id']))

                if row_channel_clean == channel_id_clean:
                    project_row = row
                    break
            
            # Se não encontrou o projeto
            if project_row is None:
                return {
                    'valid': False,
                    'reason': 'not_configured',
                    'message': f'❌ **Canal Não Configurado**\n\nEste canal não está configurado para gerar relatórios semanais.\n\n**Para solicitar o cadastro:**\n📧 Entre em contato com o time de **Dados e Tecnologia**\n📋 Informe o nome do projeto e o ID do canal: `{channel_id}`\n\n**Canais ativos disponíveis:**\n{self._get_active_channels_list()}'
                }
            
            # Verificar se o projeto tem status ativo
            if 'relatoriosemanal_status' in projects_df.columns:
                status = str(project_row['relatoriosemanal_status']).strip().lower()
                if status != 'sim':
                    project_name = str(project_row.get('Projeto - PR', 'Projeto sem nome')).strip()
                    return {
                        'valid': False,
                        'reason': 'inactive',
                        'message': f'❌ **Relatórios Desativados**\n\nO projeto **{project_name}** está com relatórios semanais **desativados**.\n\n**Status atual:** {status.upper()}\n\n**Para reativar:**\n📧 Entre em contato com o time de **Dados e Tecnologia**\n📋 Solicite a reativação do projeto: **{project_name}**'
                    }
            
            # Verificar se o projeto tem ID do Construflow
            construflow_id = str(project_row.get('construflow_id', '')).strip()
            if not construflow_id:
                project_name = str(project_row.get('Projeto - PR', 'Projeto sem nome')).strip()
                return {
                    'valid': False,
                    'reason': 'no_construflow_id',
                    'message': f'❌ **Projeto Incompleto**\n\nO projeto **{project_name}** não possui ID do Construflow configurado.\n\n**Para completar o cadastro:**\n📧 Entre em contato com o time de **Dados e Tecnologia**\n📋 Solicite a configuração do ID Construflow para: **{project_name}**'
                }
            
            # Se chegou até aqui, o canal está válido
            project_name = str(project_row.get('Projeto - PR', 'Projeto sem nome')).strip()
            return {
                'valid': True,
                'project_id': construflow_id,
                'project_name': project_name,
                'message': None
            }
            
        except Exception as e:
            logger.error(f"Erro ao validar canal {channel_id}: {e}")
            return {
                'valid': False,
                'reason': 'validation_error',
                'message': f'❌ **Erro de Validação**\n\nOcorreu um erro ao validar este canal.\n\n**Erro:** {str(e)}\n\n**Para suporte:**\n📧 Entre em contato com o time de **Dados e Tecnologia**'
            }
    
    def _get_active_channels_list(self):
        """
        Obtém uma lista formatada dos canais ativos para orientação.
        
        Returns:
            str: Lista formatada dos canais ativos
        """
        try:
            active_channels = self.get_channels_from_spreadsheet()
            
            if not active_channels:
                return "Nenhum canal ativo encontrado."
            
            # Limitar a 10 canais para não poluir a mensagem
            channels_list = []
            for channel_id, info in list(active_channels.items())[:10]:
                project_name = info['project_name']
                channels_list.append(f"• **{project_name}** (Canal: `{channel_id}`)")
            
            if len(active_channels) > 10:
                channels_list.append(f"... e mais {len(active_channels) - 10} projetos")
            
            return "\n".join(channels_list)
            
        except Exception as e:
            logger.error(f"Erro ao obter lista de canais ativos: {e}")
            return "Erro ao carregar lista de canais ativos."
    
    def get_correct_thread_info(self, channel_id):
        """
        Obtém informações sobre o tópico correto para um projeto.
        
        Args:
            channel_id: ID do canal
            
        Returns:
            str: Informações sobre o tópico correto ou None se não encontrado
        """
        try:
            # Buscar o projeto na planilha
            projects_df = self.report_system._load_project_config()
            
            if projects_df is None or projects_df.empty:
                return None
            
            channel_id_clean = extract_discord_channel_id(str(channel_id))

            # Procurar o projeto na planilha
            for _, row in projects_df.iterrows():
                row_channel_clean = extract_discord_channel_id(str(row['discord_id']))

                if row_channel_clean == channel_id_clean:
                    project_name = str(row.get('Projeto - PR', 'Projeto sem nome')).strip()
                    return f"📋 **Tópico Correto:**\n\nPara o projeto **{project_name}**, use o comando `!relatorio` no tópico dedicado:\n<#{channel_id_clean}>"
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao obter informações do tópico correto: {e}")
            return None
    
    def get_formatted_token(self):
        """Obtém o token formatado para uso na API."""
        if not self.token:
            return ""
            
        # Se o token já tem um prefixo, não adicione outro
        if self.token.startswith(("Bot ", "Bearer ")):
            return self.token
            
        # Verificar características típicas de um token de bot
        if any(self.token.startswith(prefix) for prefix in ["MT", "NT", "MT0", "NjU", "ODg"]):
            return f"Bot {self.token}"
        else:
            return self.token
    
    def _get_bot_user_id(self):
        """
        Obtém o ID do usuário do nosso bot.
        
        Returns:
            str: ID do bot ou None se não conseguir obter
        """
        try:
            # Se já temos o ID armazenado, retornar
            if hasattr(self, '_bot_user_id') and self._bot_user_id:
                return self._bot_user_id
            
            # Fazer requisição para obter informações do bot
            url = f"{self.api_endpoint}/users/@me"
            headers = {"Authorization": self.get_formatted_token()}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                self._bot_user_id = bot_info.get('id')
                logger.info(f"ID do bot obtido: {self._bot_user_id}")
                return self._bot_user_id
            else:
                logger.error(f"Erro ao obter ID do bot: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao obter ID do bot: {e}")
            return None
    
    def _load_authorized_bots(self):
        """
        Carrega a lista de bots autorizados para executar comandos.
        
        Returns:
            list: Lista de nomes de bots autorizados
        """
        try:
            # Lista padrão de bots autorizados
            default_bots = ['n8n_bot', 'automatização de projetos']
            
            # Tentar carregar do arquivo .env
            authorized_bots_env = os.getenv('DISCORD_AUTHORIZED_BOTS', '')
            if authorized_bots_env:
                # Separar por vírgula e limpar espaços
                env_bots = [bot.strip() for bot in authorized_bots_env.split(',') if bot.strip()]
                logger.info(f"Bots autorizados carregados do .env: {env_bots}")
                return env_bots
            
            logger.info(f"Usando lista padrão de bots autorizados: {default_bots}")
            return default_bots
            
        except Exception as e:
            logger.error(f"Erro ao carregar bots autorizados: {e}")
            return ['n8n_bot', 'automatização de projetos']  # Fallback para lista padrão
    
    def _is_system_bot(self, username, message_author):
        """
        Verifica se um bot pertence ao sistema "Automatização de Projetos".
        
        Args:
            username: Nome do usuário do bot
            message_author: Dados completos do autor da mensagem
            
        Returns:
            bool: True se é um bot do sistema
        """
        try:
            # Padrões que indicam que é um bot do sistema "Automatização de Projetos"
            system_patterns = [
                'n8n_bot',
                'automatização de projetos',
                'automatizacao de projetos',
                'automatização',
                'automatizacao',
                'n8n',
                'workflow',
                'automation'
            ]
            
            username_lower = username.lower()
            
            # Verificar se o nome contém algum padrão do sistema
            for pattern in system_patterns:
                if pattern in username_lower:
                    logger.info(f"Bot do sistema detectado: {username} (padrão: {pattern})")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao verificar se é bot do sistema: {e}")
            return False
    
    def get_channel_messages(self, channel_id, limit=10, max_retries=3):
        """
        Obtém as mensagens mais recentes de um canal usando a API REST.
        
        Args:
            channel_id: ID do canal
            limit: Número máximo de mensagens para obter
            max_retries: Número máximo de tentativas em caso de erro
            
        Returns:
            list: Lista de mensagens ou lista vazia em caso de erro
        """
        url = f"{self.api_endpoint}/channels/{channel_id}/messages?limit={limit}"
        
        # Tentar com diferentes formatos de token
        headers_options = [
            {"Authorization": self.get_formatted_token(), "Content-Type": "application/json"},
            {"Authorization": self.token, "Content-Type": "application/json"},
            {"Authorization": f"Bot {self.token}", "Content-Type": "application/json"}
        ]
        
        retry_count = 0
        
        while retry_count < max_retries:
            for headers in headers_options:
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        return response.json()
                    
                    if response.status_code == 429:  # Rate limit
                        retry_after = int(response.headers.get('Retry-After', 5))
                        logger.warning(f"Taxa limite excedida para o canal {channel_id}. Aguardando {retry_after} segundos.")
                        time.sleep(retry_after + 1)  # Adiciona 1 segundo extra por segurança
                        break  # Tenta novamente com o mesmo cabeçalho
                        
                    if response.status_code in [502, 503, 504]:  # Erro de servidor Discord
                        retry_count += 1
                        wait_time = 2 ** retry_count  # Backoff exponencial
                        logger.warning(f"Erro de servidor Discord {response.status_code} para canal {channel_id}. Tentativa {retry_count}, aguardando {wait_time}s")
                        time.sleep(wait_time)
                        break  # Tenta novamente com o mesmo cabeçalho
                    
                    if response.status_code != 401:  # Se não for erro de autenticação, não tentar outro formato
                        logger.error(f"Erro ao obter mensagens do canal {channel_id}: {response.status_code}")
                        if response.status_code == 403:
                            logger.error("Sem permissão para ler mensagens neste canal")
                        return []
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout ao acessar API do Discord para o canal {channel_id}. Tentativa {retry_count+1}/{max_retries}")
                    retry_count += 1
                    time.sleep(2)
                    break  # Tenta novamente com o mesmo cabeçalho
                    
                except Exception as e:
                    logger.error(f"Erro ao fazer requisição para API: {e}")
                    retry_count += 1
                    time.sleep(2)
                    break  # Tenta novamente com o mesmo cabeçalho
        
        logger.error(f"Não foi possível obter mensagens do canal {channel_id} após {max_retries} tentativas")
        return []

    def send_message(self, channel_id, content, max_retries=3):
        """
        Envia uma mensagem para um canal específico.
        
        Args:
            channel_id: ID do canal
            content: Conteúdo da mensagem
            max_retries: Número máximo de tentativas em caso de erro
            
        Returns:
            str: ID da mensagem se enviado com sucesso, None caso contrário
        """
        if not self.discord:
            logger.error("Gerenciador de Discord não inicializado")
            return None
            
        retry_count = 0
        while retry_count < max_retries:
            try:
                # Usamos o parâmetro return_message_id para obter o ID da mensagem
                message_id = self.discord.send_notification(channel_id, content, return_message_id=True)
                return message_id
            except Exception as e:
                retry_count += 1
                wait_time = 2 ** retry_count  # Backoff exponencial
                
                logger.warning(f"Erro ao enviar mensagem para canal {channel_id} (tentativa {retry_count}/{max_retries}): {e}")
                
                if "429" in str(e):  # Rate limit error
                    logger.warning(f"Taxa limite excedida ao enviar mensagem. Aguardando {wait_time}s")
                elif "5" in str(e)[:1]:  # Erro 5xx (servidor)
                    logger.warning(f"Erro de servidor ao enviar mensagem. Aguardando {wait_time}s")
                
                if retry_count < max_retries:
                    time.sleep(wait_time)
                else:
                    logger.error(f"Desistindo após {max_retries} tentativas de enviar mensagem para canal {channel_id}")
                    return None
        
        return None  
    
    def send_message_with_command(self, channel_id, content, command_to_execute=None):
        """
        Envia uma mensagem que pode conter um comando que o próprio bot executará.
        
        Args:
            channel_id: ID do canal
            content: Conteúdo da mensagem
            command_to_execute: Comando opcional para incluir na mensagem
            
        Returns:
            str: ID da mensagem se enviado com sucesso, None caso contrário
        """
        if not self.discord:
            logger.error("Gerenciador de Discord não inicializado")
            return None
        
        # Se um comando foi especificado, adicionar à mensagem
        if command_to_execute:
            content += f"\n\n{command_to_execute}"
        
        try:
            message_id = self.discord.send_notification(channel_id, content, return_message_id=True)
            logger.info(f"Mensagem com comando enviada para canal {channel_id}: {command_to_execute}")
            return message_id
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem com comando: {e}")
            return None

    def update_message(self, channel_id, message_id, new_content):
        """
        Atualiza o conteúdo de uma mensagem existente.
        
        Args:
            channel_id: ID do canal
            message_id: ID da mensagem a ser atualizada
            new_content: Novo conteúdo da mensagem
            
        Returns:
            bool: True se atualizado com sucesso, False caso contrário
        """
        if not self.discord:
            logger.error("Gerenciador de Discord não inicializado")
            return False
            
        if not message_id:
            logger.error(f"ID de mensagem não fornecido para atualização no canal {channel_id}")
            return False
            
        try:
            return self.discord.update_message(channel_id, message_id, new_content)
        except Exception as e:
            logger.error(f"Erro ao atualizar mensagem {message_id} no canal {channel_id}: {e}")
            return False
    
    def process_command(self, channel_id, command):
        """
        Processa um comando recebido em um canal.
        
        Args:
            channel_id: ID do canal onde o comando foi recebido
            command: Comando recebido
            
        Returns:
            bool: True se o comando foi processado, False caso contrário
        """
        command = command.strip().lower()
        
        try:
            # Comando para gerar relatório de semana específica (ex: !relatorio-semana 16/12/2024)
            if command.startswith("!relatorio-semana"):
                from datetime import datetime
                parts = command.split()
                reference_date = None
                hide_dashboard = "sem-dashboard" in parts or "sem_dashboard" in parts
                
                # Tentar extrair data do comando
                for part in parts:
                    # Formato: DD/MM/YYYY ou DD-MM-YYYY
                    if '/' in part or '-' in part:
                        try:
                            if '/' in part:
                                reference_date = datetime.strptime(part, "%d/%m/%Y")
                            elif '-' in part:
                                reference_date = datetime.strptime(part, "%d-%m-%Y")
                            break
                        except ValueError:
                            pass
                
                if not reference_date:
                    self.send_message(channel_id, "❌ **Formato inválido!**\n\nUse: `!relatorio-semana DD/MM/YYYY`\nExemplo: `!relatorio-semana 16/12/2024`")
                    return True
                
                logger.info(f"Processando comando !relatorio-semana para canal {channel_id} (data={reference_date.strftime('%d/%m/%Y')}, sem-dashboard={hide_dashboard})")
                
                # Validar se o canal está configurado corretamente
                validation = self.validate_channel_for_reports(channel_id)
                
                if not validation['valid']:
                    self.send_message(channel_id, validation['message'])
                    logger.info(f"Canal {channel_id} não validado: {validation['reason']}")
                    return True
                
                # Verificar se a fila está inicializada corretamente
                if not hasattr(self, 'queue_system') or not self.queue_system:
                    logger.error("Sistema de filas não inicializado corretamente")
                    self.send_message(channel_id, "❌ Erro interno: Sistema de filas não inicializado. Contate o administrador.")
                    return False

                # Adicionar à fila com data de referência
                try:
                    self.queue_system.add_report_request(channel_id, hide_dashboard=hide_dashboard, reference_date=reference_date)
                    logger.info(f"Relatório para semana específica adicionado à fila: {reference_date.strftime('%d/%m/%Y')}")
                    self.send_message(channel_id, f"✅ Relatório para a semana de **{reference_date.strftime('%d/%m/%Y')}** adicionado à fila.")
                    return True
                
                except Exception as e:
                    logger.error(f"Erro ao adicionar relatório à fila: {e}", exc_info=True)
                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(e)}")
                    return False
            
            # Comando para gerar relatório da última semana antes das férias
            elif command == "!relatorio-ultima-semana":
                from datetime import datetime, timedelta
                
                # Calcular a última semana antes das férias (última semana antes do Natal)
                today = datetime.now()
                current_year = today.year
                
                # Natal é 25/12
                christmas = datetime(current_year, 12, 25)
                
                # Se já passou do Natal, usar o Natal do ano atual
                # Se ainda não chegou no Natal, usar o Natal do ano anterior
                if today > christmas:
                    # Já passou do Natal, usar a semana antes do Natal deste ano
                    reference_date = christmas - timedelta(days=7)
                else:
                    # Ainda não chegou no Natal, usar a semana antes do Natal do ano anterior
                    reference_date = datetime(current_year - 1, 12, 25) - timedelta(days=7)
                
                # Ajustar para a segunda-feira daquela semana
                days_since_monday = reference_date.weekday()
                reference_date = reference_date - timedelta(days=days_since_monday)
                
                logger.info(f"Processando comando !relatorio-ultima-semana para canal {channel_id} (data calculada={reference_date.strftime('%d/%m/%Y')})")
                
                # Validar se o canal está configurado corretamente
                validation = self.validate_channel_for_reports(channel_id)
                
                if not validation['valid']:
                    self.send_message(channel_id, validation['message'])
                    logger.info(f"Canal {channel_id} não validado: {validation['reason']}")
                    return True
                
                # Verificar se a fila está inicializada corretamente
                if not hasattr(self, 'queue_system') or not self.queue_system:
                    logger.error("Sistema de filas não inicializado corretamente")
                    self.send_message(channel_id, "❌ Erro interno: Sistema de filas não inicializado. Contate o administrador.")
                    return False

                # Adicionar à fila com data de referência
                try:
                    self.queue_system.add_report_request(channel_id, hide_dashboard=False, reference_date=reference_date)
                    logger.info(f"Relatório da última semana antes das férias adicionado à fila: {reference_date.strftime('%d/%m/%Y')}")
                    self.send_message(channel_id, f"✅ Relatório da **última semana antes das férias** ({reference_date.strftime('%d/%m/%Y')}) adicionado à fila.")
                    return True
                
                except Exception as e:
                    logger.error(f"Erro ao adicionar relatório à fila: {e}", exc_info=True)
                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(e)}")
                    return False
            
            # Comando para gerar relatório (com suporte a parâmetros)
            elif command.startswith("!relatorio"):
                # Extrair parâmetros do comando
                parts = command.split()
                hide_dashboard = "sem-dashboard" in parts or "sem_dashboard" in parts
                
                # Extrair parâmetro de dias (ex: !relatorio 30dias ou !relatorio dias=30)
                schedule_days = None
                since_date = None
                
                # Verificar se há parâmetro "desde dia X" ou "desde X"
                desde_index = None
                for i, part in enumerate(parts):
                    if part.lower() == "desde":
                        desde_index = i
                        break
                
                if desde_index is not None and desde_index + 1 < len(parts):
                    # Pode ser "desde dia DD/MM/YYYY" ou "desde DD/MM/YYYY"
                    date_part = parts[desde_index + 1]
                    if date_part.lower() == "dia" and desde_index + 2 < len(parts):
                        date_part = parts[desde_index + 2]
                    
                    # Tentar parsear a data
                    from datetime import datetime
                    try:
                        # Formato DD/MM/YYYY
                        since_date = datetime.strptime(date_part, "%d/%m/%Y")
                    except ValueError:
                        try:
                            # Formato DD-MM-YYYY
                            since_date = datetime.strptime(date_part, "%d-%m-%Y")
                        except ValueError:
                            logger.warning(f"Formato de data inválido após 'desde': {date_part}")
                            self.send_message(channel_id, f"❌ **Formato de data inválido!**\n\nUse: `!relatorio desde dia DD/MM/YYYY`\nExemplo: `!relatorio desde dia 15/01/2024`")
                            return False
                
                for part in parts:
                    # Formato: 30dias, 30d, 15dias, etc
                    if part.endswith('dias') or part.endswith('d'):
                        try:
                            # Remover 'dias' ou 'd' e converter para int
                            num_str = part.rstrip('dias').rstrip('d')
                            schedule_days = int(num_str)
                            if schedule_days <= 0:
                                schedule_days = None
                            break
                        except ValueError:
                            pass
                    # Formato: dias=30
                    elif '=' in part and part.startswith('dias'):
                        try:
                            schedule_days = int(part.split('=')[1])
                            if schedule_days <= 0:
                                schedule_days = None
                            break
                        except (ValueError, IndexError):
                            pass

                # Se schedule_days foi informado mas since_date não, derivar since_date
                if schedule_days and not since_date:
                    since_date = datetime.now() - timedelta(days=schedule_days)
                
                logger.info(f"Processando comando !relatorio para canal {channel_id} (sem-dashboard={hide_dashboard}, schedule_days={schedule_days}, since_date={since_date.strftime('%d/%m/%Y') if since_date else None})")
                
                # Validar se o canal está configurado corretamente
                validation = self.validate_channel_for_reports(channel_id)
                
                if not validation['valid']:
                    # Enviar mensagem de orientação
                    self.send_message(channel_id, validation['message'])
                    logger.info(f"Canal {channel_id} não validado: {validation['reason']}")
                    return True  # Retorna True pois processamos o comando (mesmo que com erro)
                
                # Verificar se a fila está inicializada corretamente
                if not hasattr(self, 'queue_system') or not self.queue_system:
                    logger.error("Sistema de filas não inicializado corretamente")
                    self.send_message(channel_id, "❌ Erro interno: Sistema de filas não inicializado. Contate o administrador.")
                    return False

                # Adicionar à fila em vez de processar diretamente
                try:
                    self.queue_system.add_report_request(channel_id, hide_dashboard=hide_dashboard, schedule_days=schedule_days, since_date=since_date)
                    if since_date:
                        logger.info(f"Relatório para canal {channel_id} adicionado à fila com sucesso (sem-dashboard={hide_dashboard}, schedule_days={schedule_days}, since_date={since_date.strftime('%d/%m/%Y')})")
                        self.send_message(channel_id, f"✅ Relatório adicionado à fila. Atividades concluídas desde **{since_date.strftime('%d/%m/%Y')}** até hoje.")
                    elif schedule_days:
                        logger.info(f"Relatório para canal {channel_id} adicionado à fila com sucesso (sem-dashboard={hide_dashboard}, schedule_days={schedule_days})")
                        self.send_message(channel_id, f"✅ Relatório adicionado à fila com cronograma de **{schedule_days} dias**.")
                    else:
                        logger.info(f"Relatório para canal {channel_id} adicionado à fila com sucesso (sem-dashboard={hide_dashboard})")
                    return True
                
                except Exception as e:
                    logger.error(f"Erro ao adicionar relatório à fila: {e}", exc_info=True)
                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(e)}")
                    return False
                
            # Comando para verificar status da fila
            elif command in ["!fila", "!status"]:
                logger.info(f"Processando comando de status para canal {channel_id}")

                # Verificar se a fila está inicializada corretamente
                if not hasattr(self, 'queue_system') or not self.queue_system:
                    logger.error("Sistema de filas não inicializado corretamente")
                    self.send_message(channel_id, "❌ Erro interno: Sistema de filas não inicializado. Contate o administrador.")
                    return False
                    
                try:
                    self.queue_system.show_queue_status(channel_id)
                    logger.info(f"Status da fila exibido para canal {channel_id}")
                    return True
                
                except Exception as e:
                    logger.error(f"Erro ao exibir status da fila: {e}", exc_info=True)
                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(e)}")
                    return False
            
            # Comando para verificar relatórios semanais
            elif command == "!controle":
                logger.info(f"Processando comando !controle para canal {channel_id}")
                
                try:
                    # Verificar status dos relatórios
                    status = self.report_system.check_weekly_reports_status()
                    
                    if "error" in status:
                        self.send_message(channel_id, f"❌ Erro ao verificar relatórios: {status['error']}")
                        return False
                    
                    # Gerar mensagem de status
                    message = f"📊 **CONTROLE DE RELATÓRIOS - {status['week_text']}**\n\n"
                    message += f"📋 **Total de projetos:** {status['total_projects']}\n"
                    message += f"✅ **Devem gerar:** {status['should_generate']}\n"
                    message += f"📝 **Já gerados:** {status['was_generated']}\n"
                    message += f"⚠️ **Em falta:** {status['missing_reports']}\n\n"
                    
                    if status['missing_reports'] > 0:
                        message += "**Coordenadores com relatórios pendentes:**\n"
                        for coordinator, projects in status['missing_by_coordinator'].items():
                            message += f"👤 **{coordinator}:** {len(projects)} projetos\n"
                            for project in projects[:3]:  # Mostrar apenas os primeiros 3
                                message += f"  • {project}\n"
                            if len(projects) > 3:
                                message += f"  ... e mais {len(projects) - 3} projetos\n"
                            message += "\n"
                    else:
                        message += "✅ **Todos os relatórios foram gerados!**"
                    
                    self.send_message(channel_id, message)
                    logger.info(f"Status de relatórios exibido para canal {channel_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Erro ao verificar relatórios: {e}", exc_info=True)
                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(e)}")
                    return False
            
            # Comando para enviar notificação de relatórios em falta
            elif command == "!notificar":
                logger.info(f"Processando comando !notificar para canal {channel_id}")
                
                try:
                    # Verificar se o comando está sendo executado no canal admin
                    admin_channel_id = self.report_system.config.get_discord_admin_channel_id()
                    admin_channel_clean = extract_discord_channel_id(admin_channel_id) if admin_channel_id else ''
                    
                    if channel_id != admin_channel_clean:
                        self.send_message(channel_id, "❌ **COMANDO RESTRITO**\n\nO comando `!notificar` só pode ser executado no canal administrativo.")
                        logger.warning(f"Tentativa de executar !notificar em canal não autorizado: {channel_id}")
                        return False
                    
                    # Obter o canal de notificação da equipe
                    team_notification_channel_id = self.report_system.config.get_discord_notification_team_channel_id()
                    
                    if not team_notification_channel_id:
                        self.send_message(channel_id, "❌ Canal de notificação da equipe não configurado no .env (DISCORD_NOTIFICATION_TEAM_CHANNEL_ID)")
                        logger.error("DISCORD_NOTIFICATION_TEAM_CHANNEL_ID não configurado no .env")
                        return False
                    
                    # Obter o canal de notificação para mensagens de sucesso/erro
                    notification_channel_id = self.report_system.config.get_discord_notification_channel_id()
                    
                    if not notification_channel_id:
                        self.send_message(channel_id, "❌ Canal de notificação não configurado no .env (DISCORD_NOTIFICATION_CHANNEL_ID)")
                        logger.error("DISCORD_NOTIFICATION_CHANNEL_ID não configurado no .env")
                        return False
                    
                    # Enviar mensagem de início no canal admin
                    admin_message = f"🚀 **INICIANDO NOTIFICAÇÃO DE RELATÓRIOS**\n\n"
                    admin_message += f"**Canal de origem:** <#{channel_id}>\n"
                    admin_message += f"**Canal da equipe:** <#{team_notification_channel_id}>\n"
                    admin_message += f"**Canal de status:** <#{notification_channel_id}>\n"
                    admin_message += f"**Comando:** `!notificar`\n"
                    admin_message += f"**Status:** Processando..."
                    
                    self.send_message(channel_id, admin_message)
                    logger.info(f"Mensagem de controle enviada para canal admin {channel_id}")
                    
                    # Enviar notificação para o canal da equipe
                    success = self.report_system.send_weekly_reports_notification(team_notification_channel_id)
                    
                    if success:
                        # Mensagem de sucesso no canal de notificação
                        success_message = f"✅ **NOTIFICAÇÃO ENVIADA COM SUCESSO**\n\n"
                        success_message += f"A notificação de relatórios em falta foi enviada para a equipe.\n"
                        success_message += f"**Canal da equipe:** <#{team_notification_channel_id}>\n"
                        success_message += f"**Status:** Concluído com sucesso"
                        
                        self.send_message(notification_channel_id, success_message)
                        
                        # Mensagem de confirmação no canal admin
                        confirm_message = f"✅ **NOTIFICAÇÃO CONCLUÍDA**\n\n"
                        confirm_message += f"**Canal de origem:** <#{channel_id}>\n"
                        confirm_message += f"**Canal da equipe:** <#{team_notification_channel_id}>\n"
                        confirm_message += f"**Canal de status:** <#{notification_channel_id}>\n"
                        confirm_message += f"**Status:** Sucesso"
                        
                        self.send_message(channel_id, confirm_message)
                        
                        logger.info(f"Notificação de relatórios enviada para canal da equipe {team_notification_channel_id}")
                        return True
                    else:
                        # Mensagem de erro no canal de notificação
                        error_message = f"❌ **FALHA NA NOTIFICAÇÃO**\n\n"
                        error_message += f"Falha ao enviar notificação de relatórios em falta para a equipe.\n"
                        error_message += f"**Canal da equipe:** <#{team_notification_channel_id}>\n"
                        error_message += f"**Status:** Falha"
                        
                        self.send_message(notification_channel_id, error_message)
                        
                        # Mensagem de erro no canal admin
                        admin_error_message = f"❌ **FALHA NA NOTIFICAÇÃO**\n\n"
                        admin_error_message += f"**Canal de origem:** <#{channel_id}>\n"
                        admin_error_message += f"**Canal da equipe:** <#{team_notification_channel_id}>\n"
                        admin_error_message += f"**Canal de status:** <#{notification_channel_id}>\n"
                        admin_error_message += f"**Status:** Falha"
                        
                        self.send_message(channel_id, admin_error_message)
                        
                        return False
                        
                except Exception as e:
                    logger.error(f"Erro ao enviar notificação: {e}", exc_info=True)
                    
                    # Mensagem de erro no canal de notificação
                    notification_channel_id = self.report_system.config.get_discord_notification_channel_id()
                    if notification_channel_id:
                        error_message = f"❌ **ERRO NA NOTIFICAÇÃO**\n\n"
                        error_message += f"Ocorreu um erro ao enviar notificação de relatórios em falta.\n"
                        error_message += f"**Erro:** {str(e)}\n"
                        error_message += f"**Status:** Erro"
                        
                        self.send_message(notification_channel_id, error_message)
                    
                    # Mensagem de erro no canal admin
                    admin_error_message = f"❌ **ERRO NA NOTIFICAÇÃO**\n\n"
                    admin_error_message += f"**Canal de origem:** <#{channel_id}>\n"
                    admin_error_message += f"**Erro:** {str(e)}\n"
                    admin_error_message += f"**Status:** Erro"
                    
                    self.send_message(channel_id, admin_error_message)
                    
                    return False
            
            # Comando para enviar notificações diretas aos coordenadores
            elif command == "!notificar_coordenadores":
                logger.info(f"Processando comando !notificar_coordenadores para canal {channel_id}")
                
                try:
                    # Enviar notificações diretas (usando o canal atual como admin)
                    success = self.report_system.send_direct_notifications_to_coordinators(channel_id)
                    
                    if success:
                        self.send_message(channel_id, "✅ Notificações diretas enviadas aos coordenadores!")
                        logger.info(f"Notificações diretas enviadas via canal {channel_id}")
                        return True
                    else:
                        self.send_message(channel_id, "❌ Falha ao enviar notificações diretas")
                        return False
                        
                except Exception as e:
                    logger.error(f"Erro ao enviar notificações diretas: {e}", exc_info=True)
                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(e)}")
                    return False
            
            # Comando para encontrar tópico correto
            elif command == "!topico":
                logger.info(f"Processando comando !topico para canal {channel_id}")
                
                try:
                    # Buscar informações sobre o tópico correto
                    thread_info = self.get_correct_thread_info(channel_id)
                    
                    if thread_info:
                        self.send_message(channel_id, thread_info)
                    else:
                        # Se não encontrou o projeto, mostrar orientação geral
                        message = "❓ **Tópico Não Encontrado**\n\n"
                        message += "Este canal não está configurado para relatórios semanais.\n\n"
                        message += "**Canais ativos disponíveis:**\n"
                        message += self._get_active_channels_list()
                        message += "\n\n**Para solicitar cadastro:**\n"
                        message += "📧 Entre em contato com o time de **Dados e Tecnologia**"
                        
                        self.send_message(channel_id, message)
                    
                    logger.info(f"Informações de tópico exibidas para canal {channel_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Erro ao buscar informações de tópico: {e}", exc_info=True)
                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(e)}")
                    return False
            
            # Comando para listar canais ativos
            elif command == "!canais":
                logger.info(f"Processando comando !canais para canal {channel_id}")
                
                try:
                    active_channels = self.get_channels_from_spreadsheet()
                    
                    if not active_channels:
                        self.send_message(channel_id, "❌ Nenhum canal ativo encontrado na configuração.")
                        return True
                    
                    message = "📋 **CANAIS ATIVOS PARA RELATÓRIOS**\n\n"
                    message += "Lista de projetos com relatórios semanais ativos:\n\n"
                    
                    # Mostrar até 15 canais para não poluir muito
                    for i, (channel_id_list, info) in enumerate(list(active_channels.items())[:15], 1):
                        project_name = info['project_name']
                        message += f"{i}. **{project_name}**\n   Canal: <#{channel_id_list}>\n\n"
                    
                    if len(active_channels) > 15:
                        message += f"... e mais {len(active_channels) - 15} projetos\n\n"
                    
                    message += "💡 **Dica:** Use `!topico` para encontrar o tópico correto do seu projeto."
                    
                    self.send_message(channel_id, message)
                    logger.info(f"Lista de canais exibida para canal {channel_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Erro ao listar canais: {e}", exc_info=True)
                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(e)}")
                    return False
            
            # Comando não reconhecido
            else:
                logger.info(f"Comando não reconhecido: {command}")
                return False
            
        except Exception as e:
            logger.error(f"Erro não capturado ao processar comando '{command}': {e}", exc_info=True)
            self.send_message(channel_id, f"❌ Erro inesperado ao processar comando. Verifique os logs.")
            return False

    def _get_friendly_error_message(self, stderr):
        """
        Extrai uma mensagem de erro amigável a partir da saída de erro.
        
        Args:
            stderr: Saída de erro do processo
            
        Returns:
            str: Mensagem de erro amigável
        """
        # Procurar por mensagens de erro específicas
        if "Não foi possível encontrar projeto para o canal" in stderr:
            return "Não foi possível encontrar um projeto associado a este canal na planilha de configuração."
        elif "Projeto não encontrado ou sem dados" in stderr:
            return "O projeto foi encontrado, mas não possui dados suficientes para gerar o relatório."
        elif "Credenciais do Google não disponíveis" in stderr:
            return "Problema com as credenciais do Google. Verifique a configuração."
        elif stderr and "ERROR" in stderr:
            # Tentar extrair apenas a linha com ERROR mais relevante
            error_lines = [line for line in stderr.split('\n') if "ERROR" in line]
            if error_lines:
                # Extrair apenas a mensagem do erro, não o timestamp e o logger
                parts = error_lines[-1].split(" - ERROR - ")
                if len(parts) > 1:
                    return parts[1]
        
        # Mensagem genérica se não encontrarmos nada específico
        return "Ocorreu um erro durante o processamento. Verifique os logs para mais detalhes."
    
    def start_real_monitoring(self, channels_to_monitor, polling_interval=5):
        """
        Inicia o monitoramento real dos canais do Discord usando polling.
        
        Args:
            channels_to_monitor: Lista de IDs de canais para monitorar
            polling_interval: Intervalo em segundos entre verificações
        """
        print(f"Iniciando monitoramento REAL de {len(channels_to_monitor)} canais Discord.")
        print("O bot vai verificar cada canal a cada", polling_interval, "segundos.")
        print("Pressione Ctrl+C para interromper o monitoramento.")
        
        # Mostrar os projetos que estão sendo monitorados
        print("\nProjetos monitorados:")
        for channel_id in channels_to_monitor:
            project_name = self.get_project_name(channel_id)
            print(f"• {project_name} (Canal: {channel_id})")
        
        # Dicionário para armazenar o ID da última mensagem processada por canal
        last_message_ids = {}
        
        # Inicializar com a última mensagem de cada canal
        print("\nObtendo mensagens recentes de cada canal para referência...")
        for channel_id in channels_to_monitor:
            try:
                messages = self.get_channel_messages(channel_id, limit=1)
                if messages and len(messages) > 0:
                    last_message_ids[channel_id] = messages[0]['id']
                    project_name = self.get_project_name(channel_id)
                    print(f"• {project_name} inicializado")
                else:
                    print(f"Não foi possível obter mensagens iniciais do canal {channel_id}")
                    last_message_ids[channel_id] = "0"  # ID fictício para inicialização
            except Exception as e:
                print(f"Erro ao inicializar canal {channel_id}: {e}")
                last_message_ids[channel_id] = "0"  # ID fictício em caso de erro
        
        print("\n✅ Bot inicializado e monitorando!")
        print("Aguardando comandos:")
        print("• !relatorio - Gerar relatório semanal")
        print("• !relatorio-semana DD/MM/YYYY - Gerar relatório para semana específica")
        print("• !relatorio-ultima-semana - Gerar relatório da última semana antes das férias")
        print("• !fila / !status - Verificar status da fila")
        print("• !controle - Verificar controle de relatórios")
        print("• !notificar - Enviar notificação de relatórios em falta (só no canal admin)")
        print("• !notificar_coordenadores - Enviar notificações diretas")
        print("• !topico - Encontrar tópico correto do projeto")
        print("• !canais - Listar canais ativos para relatórios")
        print("\n")
        
        # Contadores para controle de verificação
        error_counters = {channel_id: 0 for channel_id in channels_to_monitor}
        channel_check_interval = {channel_id: 0 for channel_id in channels_to_monitor}  # Intervalo dinamicamente ajustado por canal
        next_check_time = {channel_id: 0 for channel_id in channels_to_monitor}  # Timestamp da próxima verificação
        
        # Inicializar timestamp de início
        start_time = time.time()
        heartbeat_interval = 30  # Intervalo para heartbeat em segundos
        last_heartbeat = start_time

        # Configuração para reload automático de canais (detectar novos projetos)
        channel_reload_interval = 600  # Recarregar canais a cada 10 minutos (600 segundos)
        last_channel_reload = start_time
        
        # Loop principal de monitoramento
        try:
            while True:
                current_time = time.time()
                
                # Heartbeat periódico para mostrar que o bot está vivo
                if current_time - last_heartbeat >= heartbeat_interval:
                    # Calcular tempo total de atividade em horas:minutos:segundos
                    uptime_seconds = int(current_time - start_time)
                    hours, remainder = divmod(uptime_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    # Indicador visual de que o bot está vivo
                    status_symbol = "." if (uptime_seconds // 30) % 2 == 0 else ":"
                    sys.stdout.write(f"\r{status_symbol} Uptime: {hours:02d}:{minutes:02d}:{seconds:02d} | Monitorando {len(channels_to_monitor)} canais")
                    sys.stdout.flush()
                    
                    last_heartbeat = current_time

                # Reload automático de canais a cada 10 minutos (detectar novos projetos)
                if current_time - last_channel_reload >= channel_reload_interval:
                    try:
                        new_channels = self.get_channels_from_spreadsheet()
                        new_channel_ids = set(new_channels.keys())
                        current_channel_ids = set(channels_to_monitor)

                        # Verificar se há novos canais
                        added_channels = new_channel_ids - current_channel_ids
                        removed_channels = current_channel_ids - new_channel_ids

                        if added_channels or removed_channels:
                            # Atualizar lista de canais
                            channels_to_monitor = list(new_channel_ids)

                            # Inicializar novos canais
                            for channel_id in added_channels:
                                project_name = new_channels[channel_id].get('project_name', 'Desconhecido')
                                print(f"\n🆕 Novo canal detectado: {project_name} (ID: {channel_id})")
                                logger.info(f"Novo canal adicionado ao monitoramento: {project_name} (ID: {channel_id})")

                                # Inicializar tracking para novo canal
                                error_counters[channel_id] = 0
                                channel_check_interval[channel_id] = 0
                                next_check_time[channel_id] = 0

                                # Obter última mensagem do novo canal
                                try:
                                    messages = self.get_channel_messages(channel_id, limit=1)
                                    if messages and len(messages) > 0:
                                        last_message_ids[channel_id] = messages[0]['id']
                                    else:
                                        last_message_ids[channel_id] = "0"
                                except Exception:
                                    last_message_ids[channel_id] = "0"

                            # Limpar canais removidos
                            for channel_id in removed_channels:
                                print(f"\n🗑️ Canal removido do monitoramento: {channel_id}")
                                logger.info(f"Canal removido do monitoramento: {channel_id}")
                                # Limpar dados do canal removido
                                error_counters.pop(channel_id, None)
                                channel_check_interval.pop(channel_id, None)
                                next_check_time.pop(channel_id, None)
                                last_message_ids.pop(channel_id, None)

                            print(f"\n✅ Lista de canais atualizada: {len(channels_to_monitor)} canais monitorados")
                        else:
                            logger.debug("Reload de canais: nenhuma alteração detectada")
                    except Exception as e:
                        logger.warning(f"Erro ao recarregar canais: {e}")

                    last_channel_reload = current_time

                # Verificar canais que estão na hora de serem verificados
                for channel_id in channels_to_monitor:
                    # Verificar se é hora de verificar este canal
                    if current_time < next_check_time.get(channel_id, 0):
                        continue
                    
                    # Definir o próximo horário de verificação com base no intervalo atual
                    current_interval = max(polling_interval, channel_check_interval.get(channel_id, polling_interval))
                    next_check_time[channel_id] = current_time + current_interval
                    
                    try:
                        # Obter mensagens recentes do canal
                        messages = self.get_channel_messages(channel_id, limit=5)
                        
                        # Se tiver sucesso, redefinir contador de erros e normalizar intervalo
                        if messages:
                            error_counters[channel_id] = 0
                            # Gradualmente voltar ao intervalo normal após sucesso
                            if channel_check_interval[channel_id] > polling_interval:
                                channel_check_interval[channel_id] = max(polling_interval, channel_check_interval[channel_id] * 0.8)
                            
                            # Log de debug: verificar se há mensagens novas
                            new_messages_count = sum(1 for msg in messages if channel_id not in last_message_ids or msg['id'] > last_message_ids.get(channel_id, 0))
                            if new_messages_count > 0:
                                logger.debug(f"Canal {channel_id}: {new_messages_count} mensagens novas de {len(messages)} total")
                        else:
                            # Incrementar contador de erros e ajustar intervalo
                            error_counters[channel_id] += 1
                            if error_counters[channel_id] % 10 == 1:  # Log a cada 10 tentativas falhas
                                logger.warning(f"Não foi possível obter mensagens do canal {channel_id} (tentativa {error_counters[channel_id]})")
                            continue  # Pular este canal se não conseguir mensagens
                        
                        # Processar as mensagens em ordem cronológica inversa (mais recentes primeiro)
                        for message in messages:
                            # Pular se for uma mensagem antiga que já processamos
                            if channel_id in last_message_ids and message['id'] <= last_message_ids[channel_id]:
                                continue
                                
                            # Atualizar o ID da última mensagem processada
                            last_message_ids[channel_id] = message['id']
                            
                            # Verificar se é uma mensagem de bot
                            message_author = message.get('author', {})
                            is_bot_message = message_author.get('bot', False)
                            author_username = message_author.get('username', '')
                            
                            # Log de debug para mensagens que contêm comandos
                            message_content = message.get('content', '').strip()
                            if message_content and ('!relatorio' in message_content.lower() or any(cmd in message_content.lower() for cmd in ['!fila', '!status', '!controle'])):
                                logger.debug(f"Mensagem detectada no canal {channel_id}: autor={author_username}, bot={is_bot_message}, conteúdo={message_content[:50]}")
                            
                            # Se for mensagem de bot, verificar se é autorizada
                            if is_bot_message:
                                # Obter o ID do nosso bot para comparação
                                bot_user_id = self._get_bot_user_id()
                                
                                # Verificar se é nosso próprio bot
                                is_own_bot = bot_user_id and message_author.get('id') == bot_user_id
                                
                                # Verificar se é um bot autorizado
                                is_authorized_bot = author_username.lower() in [bot.lower() for bot in self.authorized_bots]
                                
                                # Verificar se é um bot do sistema "Automatização de Projetos"
                                is_system_bot = self._is_system_bot(author_username, message_author)
                                
                                # Se não é nosso bot, nem autorizado, nem do sistema, pular
                                if not is_own_bot and not is_authorized_bot and not is_system_bot:
                                    continue
                                
                                # Se é um bot autorizado, verificar se contém comandos conhecidos
                                content = message.get('content', '').strip().lower()
                                
                                # Lista de comandos que bots autorizados podem executar
                                allowed_bot_commands = ['!notificar', '!notificar_coordenadores', '!controle']
                                
                                # Verificar se a mensagem contém algum comando permitido
                                detected_command = None
                                for cmd in allowed_bot_commands:
                                    if cmd in content:
                                        detected_command = cmd
                                        break
                                
                                if detected_command:
                                    project_name = self.get_project_name(channel_id)
                                    
                                    # Determinar o tipo de bot
                                    if is_own_bot:
                                        bot_type = "próprio bot"
                                    elif is_system_bot:
                                        bot_type = f"bot do sistema ({author_username})"
                                    else:
                                        bot_type = f"bot autorizado ({author_username})"
                                    
                                    print(f"\n\n🤖 Bot detectou comando {detected_command} de {bot_type} para {project_name}!")
                                    print(f"Conteúdo: {message.get('content', '').strip()}")
                                    
                                    # Processar o comando detectado
                                    try:
                                        self.process_command(channel_id, detected_command)
                                        time.sleep(1)
                                    except Exception as cmd_error:
                                        logger.error(f"Erro ao processar comando {detected_command} de {bot_type}: {cmd_error}", exc_info=True)
                                        self.send_message(channel_id, f"❌ Erro ao processar comando: {str(cmd_error)}")
                                continue
                                
                            # Verificar se é um dos comandos que conhecemos (apenas para mensagens de usuários, não bots)
                            content = message.get('content', '').strip().lower()
                            if content.startswith('!relatorio') or content == '!relatorio-ultima-semana' or content in ['!fila', '!status', '!controle', '!notificar', '!notificar_coordenadores', '!topico', '!canais']:
                                project_name = self.get_project_name(channel_id)
                                author_username = message.get('author', {}).get('username', 'Desconhecido')
                                logger.info(f"📣 Comando {content} recebido para {project_name} de {author_username} no canal {channel_id}")
                                print(f"\n\n📣 Comando {content} recebido para {project_name}!")
                                print(f"De: {author_username}")
                                print(f"Em: {message.get('timestamp', 'tempo desconhecido')}")
                                
                                # Processar o comando
                                try:
                                    self.process_command(channel_id, content)
                                    # Pequena pausa após processar comando para evitar sobrecarga
                                    time.sleep(1)
                                except Exception as cmd_error:
                                    logger.error(f"Erro ao processar comando {content} para canal {channel_id}: {cmd_error}", exc_info=True)
                                    # Notificar o erro no Discord
                                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(cmd_error)}")
                        
                    except Exception as e:
                        # Incrementar contador de erros
                        error_counters[channel_id] += 1
                        
                        # Log com menos frequência para evitar spam
                        if error_counters[channel_id] % 5 == 1:  # Log a cada 5 erros
                            logger.error(f"Erro ao verificar canal {channel_id} (erro #{error_counters[channel_id]}): {e}")
                        
                        # Aumentar intervalo exponencialmente até um limite para canais com problemas
                        # Máximo de 5 minutos (300 segundos)
                        max_interval = 300
                        channel_check_interval[channel_id] = min(max_interval, polling_interval * (2 ** min(5, error_counters[channel_id])))
                
                # Pequena pausa para evitar consumo excessivo de CPU
                time.sleep(0.5)
                    
        except KeyboardInterrupt:
            print("\n\nMonitoramento interrompido pelo usuário.")
        except Exception as e:
            print(f"\n\nErro durante o monitoramento: {e}")
            logger.error(f"Erro durante o monitoramento: {e}", exc_info=True)
            
            # Tentar reiniciar monitoramento após erro grave
            print("Tentando reiniciar monitoramento em 10 segundos...")
            time.sleep(10)
            return self.start_real_monitoring(channels_to_monitor, polling_interval)
    
    def simulate_command(self):
        """Menu principal do bot."""
        # Obter os canais da planilha
        channels = self.get_channels_from_spreadsheet()
        
        if not channels:
            print("❌ Nenhum canal encontrado na planilha. Verifique a configuração.")
            return
            
        # Extrair apenas os IDs dos canais
        channel_ids = list(channels.keys())
            
        # Exibir os canais disponíveis
        print("\n=== PROJETOS DISPONÍVEIS ===")
        for i, (channel, info) in enumerate(channels.items(), 1):
            print(f"{i}. {info['project_name']} (Canal: {channel})")
        
        # Menu de opções - Agora com opções de fila
        while True:
            print("\n=== MENU ===")
            print("1. Enviar mensagem de teste para um projeto")
            print("2. Simular comando !relatorio para um projeto")
            print("3. Iniciar monitoramento REAL de projetos")
            print("4. Configurar número de workers da fila (atual:", self.queue_system.max_workers, ")")
            print("5. Ver status da fila")
            print("6. Verificar controle de relatórios semanais")
            print("7. Enviar notificação de relatórios em falta (só no canal admin)")
            print("8. Enviar notificações diretas aos coordenadores")
            print("9. Testar envio de mensagem com comando automático")
            print("10. Gerenciar bots autorizados")
            print("0. Sair")
            
            try:
                choice = input("Escolha uma opção: ")
                
                if choice == "0":
                    print("Encerrando...")
                    break
                    
                elif choice == "1":
                    # Selecionar canal
                    channel_num = int(input(f"Selecione o número do projeto (1-{len(channels)}): "))
                    if 1 <= channel_num <= len(channels):
                        channel_id = list(channels.keys())[channel_num-1]
                        project_info = list(channels.values())[channel_num-1]
                        message = input("Digite a mensagem: ")
                        
                        result = self.send_message(channel_id, message)
                        if result:
                            print(f"✅ Mensagem enviada para {project_info['project_name']}")
                        else:
                            print(f"❌ Falha ao enviar mensagem para {project_info['project_name']}")
                    else:
                        print("Número de projeto inválido")
                
                elif choice == "2":
                    # Selecionar canal
                    channel_num = int(input(f"Selecione o número do projeto (1-{len(channels)}): "))
                    if 1 <= channel_num <= len(channels):
                        channel_id = list(channels.keys())[channel_num-1]
                        project_info = list(channels.values())[channel_num-1]
                        
                        print(f"Simulando comando !relatorio para {project_info['project_name']}")
                        self.process_command(channel_id, "!relatorio")
                    else:
                        print("Número de projeto inválido")
                
                elif choice == "3":
                    # Iniciar monitoramento real dos canais
                    # Perguntar quais canais monitorar
                    monitor_all = input("Monitorar todos os projetos? (s/n): ").lower() == "s"
                    
                    if monitor_all:
                        self.start_real_monitoring(channel_ids)
                    else:
                        # Permitir seleção de canais específicos
                        print("Selecione os projetos a monitorar (separados por vírgula, ex: 1,3,5):")
                        for i, (channel, info) in enumerate(channels.items(), 1):
                            print(f"{i}. {info['project_name']}")
                            
                        selections = input("Projetos: ")
                        try:
                            if selections is None:
                                print("Nenhuma seleção fornecida")
                                continue
                            selected_indices = [int(i.strip()) for i in selections.split(",") if i.strip().isdigit()]
                            selected_channels = [list(channels.keys())[i-1] for i in selected_indices if 1 <= i <= len(channels)]
                            
                            if selected_channels:
                                self.start_real_monitoring(selected_channels)
                            else:
                                print("Nenhum projeto válido selecionado")
                        except Exception as e:
                            print(f"Erro ao selecionar projetos: {e}")
                
                elif choice == "4":
                    # Configurar número de workers
                    try:
                        workers = int(input("Digite o número de workers para processar relatórios simultaneamente (1-10): "))
                        if 1 <= workers <= 10:
                            # Criar nova instância do sistema de filas com o número desejado de workers
                            self.queue_system = ReportQueue(self, max_workers=workers)
                            print(f"✅ Sistema de filas reconfigurado com {workers} workers")
                        else:
                            print("Número de workers deve estar entre 1 e 10")
                    except ValueError:
                        print("Por favor, digite um número válido")
                
                elif choice == "5":
                    # Ver status da fila
                    status_text = self.queue_system.show_queue_status()
                    print("\n" + status_text)
                    
                elif choice == "6":
                    # Verificar controle de relatórios semanais
                    try:
                        self.process_command(channel_id, "!controle") # Assuming channel_id is available or pass a dummy
                    except Exception as e:
                        print(f"Erro ao verificar controle de relatórios: {e}")
                        logger.error(f"Erro ao verificar controle de relatórios: {e}", exc_info=True)
                
                elif choice == "7":
                    # Enviar notificação de relatórios em falta
                    try:
                        self.process_command(channel_id, "!notificar") # Assuming channel_id is available or pass a dummy
                    except Exception as e:
                        print(f"Erro ao enviar notificação de relatórios: {e}")
                        logger.error(f"Erro ao enviar notificação de relatórios: {e}", exc_info=True)
                
                elif choice == "8":
                    # Enviar notificações diretas aos coordenadores
                    try:
                        self.process_command(channel_id, "!notificar_coordenadores") # Assuming channel_id is available or pass a dummy
                    except Exception as e:
                        print(f"Erro ao enviar notificações diretas: {e}")
                        logger.error(f"Erro ao enviar notificações diretas: {e}", exc_info=True)
                
                elif choice == "9":
                    # Testar envio de mensagem com comando automático
                    try:
                        # Selecionar canal
                        channel_num = int(input(f"Selecione o número do projeto (1-{len(channels)}): "))
                        if 1 <= channel_num <= len(channels):
                            channel_id = list(channels.keys())[channel_num-1]
                            project_info = list(channels.values())[channel_num-1]
                            
                            print("\nComandos disponíveis para teste:")
                            print("1. !notificar")
                            print("2. !notificar_coordenadores")
                            print("3. !controle")
                            
                            cmd_choice = input("Escolha o comando (1-3): ")
                            commands = {"1": "!notificar", "2": "!notificar_coordenadores", "3": "!controle"}
                            
                            if cmd_choice in commands:
                                command = commands[cmd_choice]
                                message_content = f"🤖 **TESTE DE COMANDO AUTOMÁTICO**\n\n"
                                message_content += f"Esta é uma mensagem de teste para o projeto **{project_info['project_name']}**.\n"
                                message_content += f"O bot deve detectar e executar o comando automaticamente."
                                
                                result = self.send_message_with_command(channel_id, message_content, command)
                                if result:
                                    print(f"✅ Mensagem com comando {command} enviada para {project_info['project_name']}")
                                    print("O bot deve detectar e executar o comando automaticamente.")
                                else:
                                    print(f"❌ Falha ao enviar mensagem para {project_info['project_name']}")
                            else:
                                print("Comando inválido")
                        else:
                            print("Número de projeto inválido")
                    except ValueError:
                        print("Por favor, digite um número válido")
                    except Exception as e:
                        print(f"Erro ao testar comando automático: {e}")
                        logger.error(f"Erro ao testar comando automático: {e}", exc_info=True)
                
                elif choice == "10":
                    # Gerenciar bots autorizados
                    try:
                        print(f"\n=== BOTS AUTORIZADOS ===")
                        print(f"Bots atualmente autorizados: {', '.join(self.authorized_bots)}")
                        print("\nOpções:")
                        print("1. Adicionar bot autorizado")
                        print("2. Remover bot autorizado")
                        print("3. Listar bots autorizados")
                        print("4. Voltar ao menu principal")
                        
                        bot_choice = input("Escolha uma opção: ")
                        
                        if bot_choice == "1":
                            new_bot = input("Digite o nome do bot para autorizar: ").strip()
                            if new_bot and new_bot.lower() not in [bot.lower() for bot in self.authorized_bots]:
                                self.authorized_bots.append(new_bot)
                                print(f"✅ Bot '{new_bot}' adicionado à lista de autorizados")
                                logger.info(f"Bot '{new_bot}' adicionado à lista de autorizados")
                            elif new_bot.lower() in [bot.lower() for bot in self.authorized_bots]:
                                print(f"❌ Bot '{new_bot}' já está na lista de autorizados")
                            else:
                                print("❌ Nome do bot não pode estar vazio")
                        
                        elif bot_choice == "2":
                            if self.authorized_bots:
                                print("Bots autorizados:")
                                for i, bot in enumerate(self.authorized_bots, 1):
                                    print(f"{i}. {bot}")
                                
                                try:
                                    bot_index = int(input("Digite o número do bot para remover: ")) - 1
                                    if 0 <= bot_index < len(self.authorized_bots):
                                        removed_bot = self.authorized_bots.pop(bot_index)
                                        print(f"✅ Bot '{removed_bot}' removido da lista de autorizados")
                                        logger.info(f"Bot '{removed_bot}' removido da lista de autorizados")
                                    else:
                                        print("❌ Número inválido")
                                except ValueError:
                                    print("❌ Por favor, digite um número válido")
                            else:
                                print("❌ Nenhum bot autorizado para remover")
                        
                        elif bot_choice == "3":
                            print(f"\n=== LISTA DE BOTS AUTORIZADOS ===")
                            if self.authorized_bots:
                                for i, bot in enumerate(self.authorized_bots, 1):
                                    print(f"{i}. {bot}")
                            else:
                                print("Nenhum bot autorizado")
                        
                        elif bot_choice == "4":
                            continue
                        
                        else:
                            print("❌ Opção inválida")
                            
                    except Exception as e:
                        print(f"Erro ao gerenciar bots autorizados: {e}")
                        logger.error(f"Erro ao gerenciar bots autorizados: {e}", exc_info=True)
                
                else:
                    print("Opção inválida")
                    
            except ValueError:
                print("Por favor, digite um número válido")
            except KeyboardInterrupt:
                print("\nOperação cancelada pelo usuário")
                break
            except Exception as e:
                print(f"Erro: {e}")

import discord
from discord.ext import commands
from report_system.config import ConfigManager
from report_system.weekly_report_control import WeeklyReportController

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.command(name='notification')
async def notification(ctx):
    config = ConfigManager()
    controller = WeeklyReportController(config)
    admin_channel_id = config.get_discord_admin_channel_id()
    # Se quiser enviar no canal onde o comando foi chamado, use ctx.channel.id
    if admin_channel_id:
        controller.send_missing_reports_notification(admin_channel_id)
        await ctx.send("✅ Notificação enviada para o canal ADM!")
    else:
        await ctx.send("❌ Canal ADM não configurado no .env")

def main():
    """Função principal."""
    try:
        # Inicializar o bot
        bot = DiscordBotAutoChannels()
        
        # Verificar se está rodando como serviço (sem interação)
        if len(sys.argv) > 1 and sys.argv[1] == "--service":
            # Modo serviço: iniciar monitoramento automaticamente
            logger.info("Iniciando bot em modo serviço (monitoramento automático)")
            
            # Obter canais da planilha
            channels = bot.get_channels_from_spreadsheet()
            if not channels:
                logger.error("Nenhum canal encontrado na planilha")
                return 1
            
            # Extrair IDs dos canais
            channel_ids = list(channels.keys())
            
            # Iniciar monitoramento de todos os canais
            logger.info(f"Iniciando monitoramento de {len(channel_ids)} canais")
            bot.start_real_monitoring(channel_ids)
        else:
            # Modo interativo: executar menu
            bot.simulate_command()
        
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())