"""
Módulo de sistema de fila para processamento de relatórios.
Este arquivo deve ser salvo como report_queue.py no mesmo diretório que o bot do Discord.
Versão corrigida com timeout e melhor tratamento de erros, compatível com Windows.
"""

import os
import sys
import subprocess
import logging
import threading
import queue
import time
import platform
from datetime import datetime

# Configurar encoding padrão para UTF-8
if sys.platform == "win32":
    import locale
    # Tentar configurar locale para UTF-8 no Windows
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
        except locale.Error:
            pass  # Usar configuração padrão se não conseguir

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DiscordBotQueue")

class ReportQueue:
    """Sistema de fila para processar solicitações de relatórios."""
    
    def __init__(self, discord_bot, max_workers=2, notification_delay=2):
        """
        Inicializa o sistema de fila.
        
        Args:
            discord_bot: Instância do bot DiscordBotAutoChannels
            max_workers: Número máximo de workers para processar relatórios simultaneamente
            notification_delay: Tempo em segundos a aguardar entre mensagens do Discord (para evitar rate limiting)
        """
        self.discord_bot = discord_bot
        self.max_workers = max_workers
        self.notification_delay = notification_delay
        self.report_queue = queue.Queue()
        self.active_reports = {}  # Dicionário para rastrear relatórios sendo processados
        self.lock = threading.Lock()  # Lock para acesso seguro a active_reports
        self.worker_status = {}  # Status de cada worker
        self.process_timeout = 600  # Timeout para processos (10 minutos)
        self.last_message_time = 0  # Timestamp da última mensagem enviada
        
        # Iniciar threads de worker
        self.workers = []
        for i in range(max_workers):
            worker = threading.Thread(target=self._process_queue, args=(i,), daemon=True)
            worker.start()
            self.workers.append(worker)
            self.worker_status[i] = "idle"
            
        logger.info(f"Sistema de fila iniciado com {max_workers} workers")
    
    def add_report_request(self, channel_id, hide_dashboard=False, schedule_days=None):
        """
        Adiciona uma solicitação de relatório à fila.
        
        Args:
            channel_id: ID do canal que solicitou o relatório
            hide_dashboard: Se True, não exibe o botão do Dashboard no relatório
            schedule_days: Número de dias para o cronograma (None = padrão de 15 dias)
            
        Returns:
            int: Posição na fila (0 significa processamento imediato)
        """
        logger.info(f"Tentando adicionar relatório para canal {channel_id} à fila (sem-dashboard={hide_dashboard}, schedule_days={schedule_days})")

        with self.lock:
            # Verificar se já existe um relatório em processamento para este canal
            if channel_id in self.active_reports:
                logger.info(f"Já existe uma solicitação de relatório em processamento para o canal {channel_id}")
                
                # Obter informações sobre a solicitação atual
                report_info = self.active_reports[channel_id]
                started_at = report_info.get('started_at', 'tempo desconhecido')
                
                # Verificar se o processo está preso por muito tempo (mais de 15 minutos)
                if isinstance(started_at, datetime):
                    elapsed_seconds = (datetime.now() - started_at).total_seconds()
                    
                    # Se estiver preso há mais de 15 minutos, cancelar e permitir nova solicitação
                    if elapsed_seconds > 900:  # 15 minutos
                        logger.warning(f"Relatório para canal {channel_id} está preso há {int(elapsed_seconds//60)} minutos. Cancelando.")
                        
                        # Tentar matar o processo se ele existir
                        if 'process' in report_info and report_info['process']:
                            try:
                                if hasattr(report_info['process'], 'terminate'):
                                    report_info['process'].terminate()
                                    time.sleep(1)
                                    if report_info['process'].poll() is None:
                                        # Forçar término se ainda estiver rodando
                                        if hasattr(report_info['process'], 'kill'):
                                            report_info['process'].kill()
                            except Exception as e:
                                logger.error(f"Erro ao terminar processo: {e}")
                        
                        # Remover da lista de ativos
                        del self.active_reports[channel_id]
                        
                        # Notificar usuário sobre o timeout
                        project_name = self.discord_bot.get_project_name(channel_id)
                        message = (
                            f"⚠️ **Tempo Limite Excedido**\n\n"
                            f"O relatório anterior para **{project_name}** excedeu o tempo limite de 15 minutos e foi cancelado.\n"
                            f"🔄 Iniciando novo processamento..."
                        )
                        self.send_message_with_rate_limit(channel_id, message)
                    else:
                        # Calcular tempo decorrido para exibição
                        elapsed = f" (em processamento há {int(elapsed_seconds//60)} min e {int(elapsed_seconds%60)} seg)"
                        
                        # Enviar mensagem de status
                        project_name = self.discord_bot.get_project_name(channel_id)
                        message = (
                            f"⏳ **Processamento em Andamento**\n\n"
                            f"Já existe um relatório para **{project_name}** em processamento{elapsed}.\n"
                            f"Por favor, aguarde a conclusão ou verifique o status usando `!status`."
                        )
                        self.send_message_with_rate_limit(channel_id, message)
                        return -1  # Código especial indicando que já existe processamento
                else:
                    # Enviar mensagem de status
                    project_name = self.discord_bot.get_project_name(channel_id)
                    message = f"⏳ Já existe um relatório para {project_name} em processamento. Por favor, aguarde."
                    self.send_message_with_rate_limit(channel_id, message)
                    return -1  # Código especial indicando que já existe processamento
            
            # Verificar quantos itens já estão na fila
            queue_size = self.report_queue.qsize()
            
            # Adicionar à fila
            request_info = {
                'channel_id': channel_id,
                'requested_at': datetime.now(),
                'status': 'queued',
                'hide_dashboard': hide_dashboard,
                'schedule_days': schedule_days
            }
            
            self.report_queue.put(request_info)
            
            # Verificar se será processado imediatamente ou aguardará na fila
            position = queue_size
            
            # Enviar mensagem adequada sobre a posição na fila
            project_name = self.discord_bot.get_project_name(channel_id)
            if position == 0 and sum(1 for r in self.active_reports.values() if r['status'] == 'processing') < self.max_workers:
                message = (
                    f"🤖**Iniciando geração do relatório para {project_name}**.\n"
                    f"⏳Este processo pode levar alguns minutos. Você será notificado quando estiver concluído."
                )
            else:
                message = (
                    f"🔢Relatório para **{project_name}** adicionado à fila de processamento.\n"
                    f"Posição atual: **{position+1}** na fila de espera.\n\n"
                    f"Você será notificado quando o processamento começar."
                )
            
            self.send_message_with_rate_limit(channel_id, message)
            
            return position
    
    def _process_queue(self, worker_id):
        """
        Função executada por cada worker para processar itens da fila.
        
        Args:
            worker_id: ID do worker para logs
        """
        logger.debug(f"Worker {worker_id} iniciado")
        
        while True:
            try:
                # Atualizar status do worker
                self.worker_status[worker_id] = "waiting for task"
                
                # Obter próximo item da fila (com timeout para responder a sinais de interrupção)
                try:
                    request = self.report_queue.get(timeout=5)
                except queue.Empty:
                    # Timeout, continuar loop
                    time.sleep(0.5)
                    continue
                
                channel_id = request['channel_id']
                hide_dashboard = request.get('hide_dashboard', False)
                schedule_days = request.get('schedule_days', None)
                
                # Obter nome do projeto logo no início para melhorar os logs
                project_name = self.discord_bot.get_project_name(channel_id)
                
                # Atualizar status com nome do projeto
                self.worker_status[worker_id] = f"processing {project_name} (channel {channel_id})"
                
                # Atualizar informações
                with self.lock:
                    request['status'] = 'processing'
                    request['started_at'] = datetime.now()
                    request['worker_id'] = worker_id
                    request['project_name'] = project_name  # Armazenar nome do projeto
                    self.active_reports[channel_id] = request
                
                # Notificar que está começando o processamento
                message = f"🔄 Iniciando geração do relatório para {project_name}. Isso pode levar alguns minutos..."
                if schedule_days:
                    message += f"\n📅 Cronograma configurado para **{schedule_days} dias**."
                self.send_message_with_rate_limit(channel_id, message)
                
                logger.info(f"Worker {worker_id} iniciando relatório para {project_name} (canal {channel_id}, sem-dashboard={hide_dashboard}, schedule_days={schedule_days})")
                
                # Executar o processo de geração de relatório - CORREÇÃO: Não passar project_name como argumento
                success = self._generate_report(channel_id, worker_id, hide_dashboard=hide_dashboard, schedule_days=schedule_days)
                
                # Marcar como concluído na fila
                self.report_queue.task_done()
                
                if not success:
                    # Enviar mensagem de erro detalhada para o canal do projeto
                    error_message = f"❌ **Erro ao gerar relatório para {project_name}**\n\nAntes de entrar em contato com o suporte, verifique se as colunas **STATUS** e **DISCIPLINA** do cronograma do SmartSheet não possuem dados vazios."
                    self.send_message_with_rate_limit(channel_id, error_message)
                    
                    # Enviar notificação adicional para o canal admin/notificação
                    try:
                        from report_system.main import WeeklyReportSystem
                        system = WeeklyReportSystem()
                        notification_channel_id = system.config.get_discord_notification_channel_id()
                        
                        if notification_channel_id:
                            admin_error_message = f"🚨 **ERRO NO RELATÓRIO - {project_name}**\n\n"
                            admin_error_message += f"**Canal:** <#{channel_id}>\n"
                            admin_error_message += f"**Projeto:** {project_name}\n"
                            admin_error_message += f"**Status:** Falha na geração\n"
                            admin_error_message += f"**Motivo:** Erro durante o processamento do relatório\n"
                            admin_error_message += f"**Ação:** Verificar logs e configurações"
                            
                            system.discord.send_notification(notification_channel_id, admin_error_message)
                            logger.info(f"Notificação de erro enviada para canal admin {notification_channel_id}")
                    except Exception as e:
                        logger.error(f"Erro ao enviar notificação admin: {e}")
                
                # Marcar como concluído
                with self.lock:
                    if channel_id in self.active_reports:
                        del self.active_reports[channel_id]
                
                # Atualizar status do worker
                self.worker_status[worker_id] = "idle"
                
            except Exception as e:
                logger.error(f"Erro no worker {worker_id}: {e}", exc_info=True)
                # Atualizar status para refletir o erro
                self.worker_status[worker_id] = f"error: {str(e)[:50]}"
                time.sleep(1) 
    
    def _generate_report(self, channel_id, worker_id, hide_dashboard=False, schedule_days=None):
        """
        Gera um relatório para o canal específico, com monitoramento em tempo real.
        
        Args:
            channel_id: ID do canal
            worker_id: ID do worker processando esta solicitação
            hide_dashboard: Se True, não exibe o botão do Dashboard no relatório
            schedule_days: Número de dias para o cronograma (None = padrão de 15 dias)
            
        Returns:
            bool: True se o relatório foi gerado com sucesso, False caso contrário
        """
        # Obter o nome do projeto para mensagens
        project_name = self.discord_bot.get_project_name(channel_id)
        
        # Executar o script run.py com o parâmetro --channel
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py")
        
        logger.info(f"Worker {worker_id} executando relatório para {project_name} (canal {channel_id}, sem-dashboard={hide_dashboard}, schedule_days={schedule_days})")
        
        try:
            # Executar o processo redirecionando saída para capturar o URL
            # Permitir notificações automáticas para erros (serão enviadas para canal admin/notificação)
            cmd = [sys.executable, script_path, "--channel", channel_id, "--quiet"]
            if hide_dashboard:
                cmd.append("--hide-dashboard")
            if schedule_days:
                cmd.extend(["--schedule-days", str(schedule_days)])
            
            # Imprimir comando que será executado
            logger.info(f"Executando: {' '.join(cmd)}")
            
            # Processo com saída capturada para obter URL
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # Verificar resultado
            logger.info(f"Resultado do subprocess: returncode={result.returncode}, stdout_length={len(result.stdout) if result.stdout else 0}, stderr_length={len(result.stderr) if result.stderr else 0}")
            
            if result.returncode == 0:
                # Procurar URL do documento na saída (pode ser Google Docs ou Google Drive)
                doc_url = None
                if result.stdout:
                    logger.info(f"Procurando URL na saída: {repr(result.stdout[:500])}...")
                    for line in result.stdout.split('\n'):
                        # Procurar por links do Google Docs ou Google Drive
                        if "docs.google.com/document" in line or "drive.google.com/file" in line:
                            doc_url = line.strip()
                            logger.info(f"URL encontrado: {doc_url}")
                            break
                else:
                    logger.warning("stdout está vazio, não foi possível encontrar URL")
                
                # Importamos aqui para evitar importação circular
                from report_system.main import WeeklyReportSystem
                system = WeeklyReportSystem()
                
                # Se temos um URL do documento, formatar a mensagem completa
                if doc_url:
                    # Tentar obter o ID do projeto a partir do canal
                    project_id = system.get_project_by_discord_channel(channel_id)
                    
                    # Tentar obter a pasta do projeto
                    folder_url = None
                    if project_id:
                        try:
                            project_folder_id = system.gdrive.get_project_folder(project_id, project_name)
                            if project_folder_id:
                                folder_url = f"https://drive.google.com/drive/folders/{project_folder_id}"
                        except Exception as e:
                            logger.warning(f"Erro ao obter pasta do projeto: {e}")
                    
                    # Usar o formato de mensagem padrão
                    message = [
                        "🎉 Relatório Semanal Concluído!",
                        "",
                        f"📋 Projeto: {project_name}",
                        "",
                        f"📄 [Abrir Relatório]({doc_url})"
                    ]
                    
                    if folder_url:
                        message.append(f"📁 [Abrir Pasta do Projeto]({folder_url})")
                    
                    message.extend([
                        "",
                        "✅ O relatório foi gerado com sucesso e está pronto para ser compartilhado.",
                        "🔄 Para gerar um novo relatório, use o comando !relatorio neste canal."
                    ])
                    
                    formatted_message = "\n".join(message)
                    self.send_message_with_rate_limit(channel_id, formatted_message)
                    logger.info(f"Relatório gerado com sucesso para {project_name} com URL: {doc_url}")
                    return True
                else:
                    # Se não encontramos o URL, considerar como falha
                    logger.error(f"Relatório não gerado com sucesso para {project_name}: URL não encontrado na saída")
                    # Mensagem simples para o canal do projeto
                    error_message = f"❌ **Erro ao gerar relatório para {project_name}**\n\nO relatório foi processado mas não foi possível obter o link do documento. Isso pode indicar um problema na criação do Google Doc ou nas permissões do Google Drive."
                    self.send_message_with_rate_limit(channel_id, error_message)
                    
                    # Enviar notificação adicional para o canal admin/notificação
                    try:
                        from report_system.main import WeeklyReportSystem
                        system = WeeklyReportSystem()
                        notification_channel_id = system.config.get_discord_notification_channel_id()
                        
                        if notification_channel_id:
                            admin_error_message = f"🚨 **ERRO NO RELATÓRIO - {project_name}**\n\n"
                            admin_error_message += f"**Canal:** <#{channel_id}>\n"
                            admin_error_message += f"**Projeto:** {project_name}\n"
                            admin_error_message += f"**Status:** Documento não criado\n"
                            admin_error_message += f"**Motivo:** Documento não foi criado no Google Docs - URL não encontrado na saída\n"
                            admin_error_message += f"**Ação:** Verificar permissões do Google Drive e configurações"
                            
                            system.discord.send_notification(notification_channel_id, admin_error_message)
                            logger.info(f"Notificação de erro enviada para canal admin {notification_channel_id}")
                    except Exception as e:
                        logger.error(f"Erro ao enviar notificação admin: {e}")
                    
                    return False
            else:
                # Mensagem de erro com mais detalhes
                error_details = ""
                if result.stderr:
                    error_details = f"\n\n**Detalhes do erro:**\n{result.stderr[:500]}"
                
                # Determinar o motivo do erro baseado no returncode e stderr (apenas para canal admin)
                error_reason = self._determine_error_reason(result.returncode, result.stderr)
                
                # Mensagem simples para o canal do projeto
                message = f"❌ **Erro ao gerar relatório para {project_name}**\n\nAntes de entrar em contato com o suporte, verifique se as colunas **STATUS** e **DISCIPLINA** do cronograma do SmartSheet não possuem dados vazios."
                
                self.send_message_with_rate_limit(channel_id, message)
                logger.error(f"Subprocess falhou com returncode {result.returncode}. stderr: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao executar script: {e}")
            logger.error(f"Detalhes do erro: stdout={getattr(result, 'stdout', 'N/A')}, stderr={getattr(result, 'stderr', 'N/A')}")
            self.send_message_with_rate_limit(channel_id, f"❌ **Erro ao gerar relatório**\n\nAntes de entrar em contato com o suporte, verifique se as colunas **STATUS** e **DISCIPLINA** do cronograma do SmartSheet não possuem dados vazios.")
            return False
    
    def _read_pipe_windows_compatible(self, pipe):
        """
        Lê uma linha do pipe do processo de forma compatível com Windows.
        Não usa select.select() que causa problemas no Windows.
        
        Args:
            pipe: Pipe do processo (stdout ou stderr)
            
        Returns:
            str: Linha lida ou None se não houver dados
        """
        # Método não bloqueante para ler pipe
        # Verifica se há dados disponíveis sem bloquear
        import io
        
        if pipe.closed:
            return None
            
        # Em Python 3, os pipes têm o método readline() não bloqueante
        # quando criados com bufsize=1 (line buffered)
        line = pipe.readline()
        if line:
            return line.strip()
        return None
    
    def get_queue_status(self):
        """
        Retorna o status atual da fila.
        
        Returns:
            dict: Dicionário com informações sobre a fila
        """
        with self.lock:
            active_reports_info = {}
            for channel_id, info in self.active_reports.items():
                # Criar cópia das informações para não modificar o original
                report_info = dict(info)
                
                # Adicionar nome do projeto
                project_name = self.discord_bot.get_project_name(channel_id)
                report_info['project_name'] = project_name
                
                # Calcular tempo decorrido
                if 'started_at' in report_info and isinstance(report_info['started_at'], datetime):
                    elapsed_seconds = (datetime.now() - report_info['started_at']).total_seconds()
                    report_info['elapsed_seconds'] = elapsed_seconds
                    report_info['elapsed_formatted'] = f"{int(elapsed_seconds//60)} min e {int(elapsed_seconds%60)} seg"
                
                # Remover referência ao processo para serialização
                if 'process' in report_info:
                    del report_info['process']
                
                active_reports_info[channel_id] = report_info
            
            return {
                'queue_size': self.report_queue.qsize(),
                'active_reports': active_reports_info,
                'max_workers': self.max_workers,
                'workers_running': len([w for w in self.workers if w.is_alive()]),
                'worker_status': self.worker_status
            }
    
    def show_queue_status(self, channel_id=None):
        """
        Envia uma mensagem com o status atual da fila.
        
        Args:
            channel_id: ID do canal para enviar a mensagem (opcional)
            
        Returns:
            str: Mensagem de status
        """
        status = self.get_queue_status()
        
        # Construir mensagem de status
        message = "📊 **Status do Sistema de Relatórios**\n\n"
        
        # Informações sobre workers
        active_workers = status['workers_running']
        total_workers = status['max_workers']
        worker_emoji = "✅" if active_workers == total_workers else "⚠️"
        message.append(f"{worker_emoji} **Workers:** {active_workers}/{total_workers} ativos")
        
        # Informações sobre a fila
        queue_size = status['queue_size']
        queue_emoji = "✅" if queue_size == 0 else "📋"
        message.append(f"{queue_emoji} **Fila:** {queue_size} relatório(s) aguardando")
        message.append("")


        # Informações sobre workers
        active_workers = status['workers_running']
        total_workers = status['max_workers']
        worker_emoji = "✅" if active_workers == total_workers else "⚠️"
        message.append(f"{worker_emoji} **Workers:** {active_workers}/{total_workers} ativos")

        # Informações sobre a fila
        queue_size = status['queue_size']
        queue_emoji = "✅" if queue_size == 0 else "📋"
        message.append(f"{queue_emoji} **Fila:** {queue_size} relatório(s) aguardando")
        message.append("")
        
        # Informações sobre workers e seu status atual
        message.append("**Status dos Workers:**")
        for worker_id, worker_status in status['worker_status'].items():
            # Escolher emoji baseado no status
            if "idle" in worker_status:
                emoji = "💤"
            elif "processing" in worker_status:
                emoji = "⚙️"
            elif "waiting" in worker_status:
                emoji = "⏳"
            elif "error" in worker_status:
                emoji = "⚠️"
            else:
                emoji = "ℹ️"
                
            message.append(f"{emoji} Worker {worker_id}: {worker_status}")
        
        message.append("")    
            

        # Informações sobre relatórios em processamento
        if status['active_reports']:
            message.append("**Relatórios em processamento:**")
            for ch_id, info in status['active_reports'].items():
                project_name = info.get('project_name', 'Projeto desconhecido')
                worker = info.get('worker_id', '?')
                elapsed = info.get('elapsed_formatted', 'tempo desconhecido')
                message.append(f"⚙️ **{project_name}** - Worker {worker} - Em processamento há {elapsed}")
        else:
            message.append("🔍 Nenhum relatório em processamento no momento.")
        
         # Enviar para o canal específico se fornecido
        formatted_message = "\n".join(message)
        if channel_id:
            self.send_message_with_rate_limit(channel_id, formatted_message)
        
        return formatted_message

    def _determine_error_reason(self, returncode, stderr):
        """
        Determina o motivo do erro baseado no returncode e stderr.
        
        Args:
            returncode: Código de retorno do subprocess
            stderr: Saída de erro do subprocess
            
        Returns:
            str: Descrição do motivo do erro
        """
        stderr_lower = stderr.lower() if stderr else ""
        
        # Verificar erros específicos baseados no conteúdo do stderr
        if "smartsheet" in stderr_lower and ("token" in stderr_lower or "auth" in stderr_lower):
            return "Erro de autenticação no SmartSheet - Token inválido ou expirado"
        elif "google" in stderr_lower and ("auth" in stderr_lower or "credentials" in stderr_lower):
            return "Erro de autenticação no Google - Credenciais inválidas ou expiradas"
        elif "construflow" in stderr_lower and ("api" in stderr_lower or "connection" in stderr_lower):
            return "Erro de conexão com a API do ConstruFlow"
        elif "permission" in stderr_lower or "access" in stderr_lower:
            return "Erro de permissão - Acesso negado aos recursos necessários"
        elif "timeout" in stderr_lower or "connection" in stderr_lower:
            return "Erro de timeout ou conexão - Serviço indisponível temporariamente"
        elif "data" in stderr_lower and ("empty" in stderr_lower or "missing" in stderr_lower):
            return "Dados insuficientes - Colunas obrigatórias vazias no SmartSheet"
        elif "file" in stderr_lower and ("not found" in stderr_lower or "missing" in stderr_lower):
            return "Arquivo não encontrado - Template ou configuração ausente"
        elif "memory" in stderr_lower or "out of memory" in stderr_lower:
            return "Erro de memória - Sistema sobrecarregado"
        elif returncode == 1:
            return "Erro geral de execução - Verificar logs para detalhes"
        elif returncode == 2:
            return "Erro de configuração - Verificar arquivos de configuração"
        elif returncode == 126:
            return "Erro de permissão - Script não pode ser executado"
        elif returncode == 127:
            return "Comando não encontrado - Python ou dependências não disponíveis"
        else:
            return f"Erro desconhecido (código {returncode}) - Verificar logs para detalhes"
    
    def send_message_with_rate_limit(self, channel_id, content):
        """
        Envia uma mensagem respeitando limites de rate do Discord.
        
        Args:
            channel_id: ID do canal
            content: Conteúdo da mensagem
            
        Returns:
            str: ID da mensagem se enviado com sucesso, None caso contrário
        """
        # Verificar se precisamos aguardar antes de enviar a próxima mensagem
        current_time = time.time()
        time_since_last = current_time - self.last_message_time
        
        if time_since_last < self.notification_delay and self.last_message_time > 0:
            # Calcular tempo a aguardar
            wait_time = self.notification_delay - time_since_last
            logger.debug(f"Aguardando {wait_time:.2f}s antes de enviar próxima mensagem para evitar rate limit")
            time.sleep(wait_time)
        
        # Enviar a mensagem
        result = self.discord_bot.send_message(channel_id, content)
        
        # Atualizar timestamp
        self.last_message_time = time.time()
        
        return result