"""
Sistema simples de notificação de progresso para o Discord.
Versão compatível com Windows.
Salve este arquivo como report_system/utils/progress_reporter.py
"""

import time
import sys
import logging
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger("ReportSystem")

class ProgressReporter:
    """
    Classe simplificada para enviar atualizações de progresso no Discord.
    Compatível com Windows e Unix.
    """
    
    def __init__(self, channel_id: str, project_name: str, send_message_func: Callable, quiet_mode=False):
        """
        Inicializa o reporter de progresso.
        
        Args:
            channel_id: ID do canal do Discord
            project_name: Nome do projeto
            send_message_func: Função para enviar mensagens (deve aceitar channel_id e message)
        """
        self.channel_id = channel_id
        self.project_name = project_name
        self.send_message = send_message_func
        self.start_time = None
        self.stages = []
        self.quiet_mode = quiet_mode
        # Lista das etapas típicas do processo para calcular o progresso
        self.all_expected_stages = [
            "Atualização de cache", 
            "Processamento de dados", 
            "Geração de relatório", 
            "Upload do relatório", 
            "Criação de documento", 
            "Finalização"
        ]
    
    def start(self, initial_message: Optional[str] = None):
        """
        Inicia o relatório com mensagem inicial opcional.
        
        Args:
            initial_message: Mensagem inicial para enviar
        """
        self.start_time = datetime.now()
        
        # Enviar mensagem inicial ultra-concisa
        if not initial_message:
            # Usar versão sem emoji no Windows
            if sys.platform == 'win32':
                initial_message = f"{self.project_name}: Iniciando..."
            else:
                initial_message = f"🔄 {self.project_name}: Iniciando..."
        
        self.send_message(self.channel_id, initial_message)
    
    def update(self, stage: str, details: Optional[str] = None):
        """
        Envia uma atualização de progresso.
        
        Args:
            stage: Nome do estágio atual
            details: Detalhes adicionais (opcional)
        """
        # No modo silencioso, apenas registrar no log sem enviar mensagens
        if self.quiet_mode:
            return

        # Adicionar estágio à lista se ainda não estiver lá
        if stage not in self.stages:
            self.stages.append(stage)
        
        # Tempo decorrido
        elapsed = datetime.now() - self.start_time
        minutes, seconds = divmod(elapsed.total_seconds(), 60)
        
        # Calcular progresso atual
        stage_short = self._get_short_stage_name(stage)
        current_stage_index = self.all_expected_stages.index(stage) if stage in self.all_expected_stages else 0
        total_stages = len(self.all_expected_stages)
        progress = f"{current_stage_index+1}/{total_stages}"
        
        # Obter emoji para o estágio
        emoji = self._get_stage_emoji(stage)

        # Mensagem melhorada
        message = f"{emoji} **{self.project_name}**: {stage} {progress} ({int(minutes)}:{int(seconds):02d})"
        
        if details:
            message += f"\n{details}"
        
        self.send_message(self.channel_id, message)
    
    def _get_stage_emoji(self, stage):
        """Retorna um emoji apropriado para o estágio atual"""
        mapping = {
            "Atualização de cache": "🔄",
            "Processamento de dados": "🔍",
            "Geração de relatório": "📝",
            "Upload do relatório": "📤",
            "Criação de documento": "📋",
            "Finalização": "✅"
        }
        return mapping.get(stage, "⏳")


    def _get_short_stage_name(self, stage):
        """Retorna uma versão abreviada do nome da etapa"""
        mapping = {
            "Atualização de cache": "Cache",
            "Processamento de dados": "Proc",
            "Geração de relatório": "Rel",
            "Upload do relatório": "Upload",
            "Criação de documento": "Doc",
            "Finalização": "Fin"
        }
        return mapping.get(stage, stage)
    
    def complete(self, success: bool = True, final_message: Optional[str] = None, doc_url: Optional[str] = None):
        """
        Finaliza o relatório com mensagem final.
        
        Args:
            success: Indica se o processo foi concluído com sucesso
            final_message: Mensagem final personalizada (opcional)
            doc_url: URL do documento gerado (opcional)
        """
        # Tempo total
        total_time = datetime.now() - self.start_time
        minutes, seconds = divmod(total_time.total_seconds(), 60)
        time_str = f"{int(minutes)}:{int(seconds):02d}"
        
        # Mensagem padrão se não for fornecida
        if not final_message:
            if success:
                emoji = "✅"
                final_message = f"{emoji} **{self.project_name}: Relatório concluído!**\n\nTempo de processamento: {time_str}"
                
                if doc_url:
                    final_message += f"\n\n📄 [Abrir Relatório]({doc_url})"
            else:
                emoji = "❌"
                final_message = f"{emoji} **{self.project_name}: Erro ao gerar relatório**\n\nTempo de processamento: {time_str}\n\nAntes de entrar em contato com o suporte, verifique se as colunas **STATUS** e **DISCIPLINA** do cronograma do SmartSheet não possuem dados vazios."
    
        self.send_message(self.channel_id, final_message)