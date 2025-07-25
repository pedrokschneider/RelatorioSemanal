import os
import sys
import subprocess
import logging
import requests
import json
from datetime import datetime
import time
from dotenv import load_dotenv
import pythoncom
import win32serviceutil
import win32service
import win32event
import servicemanager

# Importar nossa nova classe ReportQueue
from report_queue import ReportQueue

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

class DiscordBotService(win32serviceutil.ServiceFramework):
    _svc_name_ = "DiscordBotService"
    _svc_display_name_ = "Discord Bot Service"
    _svc_description_ = "Serviço do Bot Discord para Relatórios Semanais"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.bot = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        try:
            self.bot = DiscordBotAutoChannels()
            channels = self.bot.get_channels_from_spreadsheet()
            
            if not channels:
                logger.error("Nenhum canal encontrado na planilha")
                return
                
            channel_ids = list(channels.keys())
            self.bot.start_real_monitoring(channel_ids)
            
        except Exception as e:
            logger.error(f"Erro fatal no serviço: {e}", exc_info=True)

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
            
            # Inicializar o sistema de filas com 2 workers por padrão
            from report_queue import ReportQueue  # Importação explícita
            self.queue_system = ReportQueue(self, max_workers=2)
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
                
                # Limpar o canal_id (remover caracteres não numéricos)
                channel_id_clean = ''.join(c for c in channel_id if c.isdigit())
                
                if channel_id_clean:
                    channels_dict[channel_id_clean] = {
                        'project_id': project_id,
                        'project_name': project_name
                    }
            
            logger.info(f"Encontrados {len(channels_dict)} canais ativos na planilha")
            
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
            # Comando para gerar relatório
            if command == "!relatorio":
                logger.info(f"Processando comando !relatorio para canal {channel_id}")
                
                # Verificar se a fila está inicializada corretamente
                if not hasattr(self, 'queue_system') or not self.queue_system:
                    logger.error("Sistema de filas não inicializado corretamente")
                    self.send_message(channel_id, "❌ Erro interno: Sistema de filas não inicializado. Contate o administrador.")
                    return False

                # Adicionar à fila em vez de processar diretamente
                try:
                    self.queue_system.add_report_request(channel_id)
                    logger.info(f"Relatório para canal {channel_id} adicionado à fila com sucesso")
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
                    # Enviar notificação para o próprio canal
                    success = self.report_system.send_weekly_reports_notification(channel_id)
                    
                    if success:
                        logger.info(f"Notificação de relatórios enviada para canal {channel_id}")
                        return True
                    else:
                        self.send_message(channel_id, "❌ Falha ao enviar notificação de relatórios")
                        return False
                        
                except Exception as e:
                    logger.error(f"Erro ao enviar notificação: {e}", exc_info=True)
                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(e)}")
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
            
            # Comando para enviar notificação (alias para !notificar)
            elif command == "!notification":
                logger.info(f"Processando comando !notification para canal {channel_id}")
                
                try:
                    # Enviar notificação para o próprio canal
                    success = self.report_system.send_weekly_reports_notification(channel_id)
                    
                    if success:
                        self.send_message(channel_id, "✅ Notificação enviada para o canal ADM!")
                        logger.info(f"Notificação de relatórios enviada para canal {channel_id}")
                        return True
                    else:
                        self.send_message(channel_id, "❌ Falha ao enviar notificação de relatórios")
                        return False
                        
                except Exception as e:
                    logger.error(f"Erro ao enviar notificação: {e}", exc_info=True)
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
        elif "ERROR" in stderr:
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
        logger.info(f"Iniciando monitoramento de {len(channels_to_monitor)} canais Discord")
        
        # Dicionário para armazenar o ID da última mensagem processada por canal
        last_message_ids = {}
        
        # Inicializar com a última mensagem de cada canal
        for channel_id in channels_to_monitor:
            try:
                messages = self.get_channel_messages(channel_id, limit=1)
                if messages and len(messages) > 0:
                    last_message_ids[channel_id] = messages[0]['id']
                    project_name = self.get_project_name(channel_id)
                    logger.info(f"Canal {project_name} inicializado")
                else:
                    logger.warning(f"Não foi possível obter mensagens iniciais do canal {channel_id}")
                    last_message_ids[channel_id] = "0"  # ID fictício para inicialização
            except Exception as e:
                logger.error(f"Erro ao inicializar canal {channel_id}: {e}")
                last_message_ids[channel_id] = "0"  # ID fictício em caso de erro
        
        logger.info("Bot inicializado e monitorando!")
        
        # Contadores para controle de verificação
        error_counters = {channel_id: 0 for channel_id in channels_to_monitor}
        channel_check_interval = {channel_id: 0 for channel_id in channels_to_monitor}
        next_check_time = {channel_id: 0 for channel_id in channels_to_monitor}
        
        # Inicializar timestamp de início
        start_time = time.time()
        heartbeat_interval = 30  # Intervalo para heartbeat em segundos
        last_heartbeat = start_time
        
        # Loop principal de monitoramento
        try:
            while True:
                current_time = time.time()
                
                # Heartbeat periódico para mostrar que o bot está vivo
                if current_time - last_heartbeat >= heartbeat_interval:
                    uptime_seconds = int(current_time - start_time)
                    hours, remainder = divmod(uptime_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    logger.info(f"Bot ativo há {hours:02d}:{minutes:02d}:{seconds:02d} | Monitorando {len(channels_to_monitor)} canais")
                    last_heartbeat = current_time
                
                # Verificar canais que estão na hora de serem verificados
                for channel_id in channels_to_monitor:
                    if current_time < next_check_time.get(channel_id, 0):
                        continue
                    
                    current_interval = max(polling_interval, channel_check_interval.get(channel_id, polling_interval))
                    next_check_time[channel_id] = current_time + current_interval
                    
                    try:
                        messages = self.get_channel_messages(channel_id, limit=5)
                        
                        if messages:
                            error_counters[channel_id] = 0
                            if channel_check_interval[channel_id] > polling_interval:
                                channel_check_interval[channel_id] = max(polling_interval, channel_check_interval[channel_id] * 0.8)
                        else:
                            error_counters[channel_id] += 1
                            continue
                        
                        for message in messages:
                            if channel_id in last_message_ids and message['id'] <= last_message_ids[channel_id]:
                                continue
                                
                            last_message_ids[channel_id] = message['id']
                            
                            if message.get('author', {}).get('bot', False):
                                continue
                                
                            content = message.get('content', '').strip().lower()
                            if content in ['!relatorio', '!fila', '!status', '!controle', '!notificar', '!notificar_coordenadores', '!notification']:
                                project_name = self.get_project_name(channel_id)
                                logger.info(f"Comando {content} recebido para {project_name}")
                                logger.info(f"De: {message.get('author', {}).get('username', 'Desconhecido')}")
                                logger.info(f"Em: {message.get('timestamp', 'tempo desconhecido')}")
                                
                                try:
                                    self.process_command(channel_id, content)
                                    time.sleep(1)
                                except Exception as cmd_error:
                                    logger.error(f"Erro ao processar comando {content}: {cmd_error}", exc_info=True)
                                    self.send_message(channel_id, f"❌ Erro ao processar comando: {str(cmd_error)}")
                        
                    except Exception as e:
                        error_counters[channel_id] += 1
                        if error_counters[channel_id] % 5 == 1:
                            logger.error(f"Erro ao verificar canal {channel_id} (erro #{error_counters[channel_id]}): {e}")
                        max_interval = 300
                        channel_check_interval[channel_id] = min(max_interval, polling_interval * (2 ** min(5, error_counters[channel_id])))
                
                time.sleep(0.5)
                    
        except KeyboardInterrupt:
            logger.info("Monitoramento interrompido pelo usuário")
        except Exception as e:
            logger.error(f"Erro durante o monitoramento: {e}", exc_info=True)
            time.sleep(10)
            return self.start_real_monitoring(channels_to_monitor, polling_interval)

def main():
    """Função principal."""
    if len(sys.argv) == 1:
        try:
            # Se executado diretamente (não como serviço)
            pythoncom.CoInitialize()
            bot = DiscordBotAutoChannels()
            channels = bot.get_channels_from_spreadsheet()
            
            if not channels:
                logger.error("Nenhum canal encontrado na planilha")
                return 1
                
            channel_ids = list(channels.keys())
            bot.start_real_monitoring(channel_ids)
            
        except Exception as e:
            logger.error(f"Erro fatal: {e}", exc_info=True)
            return 1
    else:
        # Se executado como serviço
        try:
            if len(sys.argv) > 1:
                if sys.argv[1] == 'install':
                    # Forçar remoção do serviço se existir
                    try:
                        win32serviceutil.RemoveService(DiscordBotService._svc_name_)
                        logger.info("Serviço antigo removido com sucesso")
                    except Exception as e:
                        logger.warning(f"Não foi possível remover serviço antigo: {e}")
                    
                    # Instalar novo serviço
                    win32serviceutil.InstallService(
                        DiscordBotService._svc_name_,
                        DiscordBotService._svc_display_name_,
                        DiscordBotService._svc_description_
                    )
                    print("Serviço instalado com sucesso!")
                    return 0
                elif sys.argv[1] == 'remove':
                    try:
                        win32serviceutil.RemoveService(DiscordBotService._svc_name_)
                        print("Serviço removido com sucesso!")
                    except Exception as e:
                        print(f"Erro ao remover serviço: {e}")
                    return 0
                
            win32serviceutil.HandleCommandLine(DiscordBotService)
            
        except Exception as e:
            logger.error(f"Erro ao manipular serviço: {e}", exc_info=True)
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())