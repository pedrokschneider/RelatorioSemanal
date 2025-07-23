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
    
    def add_report_request(self, channel_id):
        """
        Adiciona uma solicitação de relatório à fila.
        
        Args:
            channel_id: ID do canal que solicitou o relatório
            
        Returns:
            int: Posição na fila (0 significa processamento imediato)
        """
        logger.info(f"Tentando adicionar relatório para canal {channel_id} à fila")

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
                'status': 'queued'
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
                self.send_message_with_rate_limit(channel_id, message)
                
                logger.info(f"Worker {worker_id} iniciando relatório para {project_name} (canal {channel_id})")
                
                # Executar o processo de geração de relatório - CORREÇÃO: Não passar project_name como argumento
                success = self._generate_report(channel_id, worker_id)
                
                # Marcar como concluído na fila
                self.report_queue.task_done()
                
                if not success:
                    # Enviar mensagem de erro se o processo falhou
                    error_message = f"❌ Ocorreu um erro ao gerar o relatório para {project_name}. Antes de entrar em contato com o suporte, verifique se as colunas **STATUS** e **DISCIPLINA** do cronograma do SmartSheet não possuem dados vazios."
                    self.send_message_with_rate_limit(channel_id, error_message)
                
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
    
    def _generate_report(self, channel_id, worker_id):
        """
        Gera um relatório para o canal específico, com monitoramento em tempo real.
        
        Args:
            channel_id: ID do canal
            worker_id: ID do worker processando esta solicitação
            
        Returns:
            bool: True se o relatório foi gerado com sucesso, False caso contrário
        """
        # Obter o nome do projeto para mensagens
        project_name = self.discord_bot.get_project_name(channel_id)
        
        # Executar o script run.py com o parâmetro --channel
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py")
        
        logger.info(f"Worker {worker_id} executando relatório para {project_name} (canal {channel_id})")
        
        try:
            # Executar o processo redirecionando saída para capturar o URL
            cmd = [sys.executable, script_path, "--channel", channel_id, "--quiet"]
            
            # Imprimir comando que será executado
            logger.info(f"Executando: {' '.join(cmd)}")
            
            # Processo com saída capturada para obter URL
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Verificar resultado
            if result.returncode == 0:
                # Procurar URL do documento na saída
                doc_url = None
                for line in result.stdout.split('\n'):
                    if "docs.google.com/document" in line:
                        doc_url = line.strip()
                        break
                
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
                else:
                    # Mensagem de sucesso simplificada se não encontrarmos o URL
                    message = f"✅ **Relatório de {project_name} gerado com sucesso!**"
                    self.send_message_with_rate_limit(channel_id, message)
                return True
            else:
                # Mensagem de erro
                message = f"❌ **Erro ao gerar relatório para {project_name}**\n\nAntes de entrar em contato com o suporte, verifique se as colunas **STATUS** e **DISCIPLINA** do cronograma do SmartSheet não possuem dados vazios."
                self.send_message_with_rate_limit(channel_id, message)
                return False
                
        except Exception as e:
            logger.error(f"Erro ao executar script: {e}")
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