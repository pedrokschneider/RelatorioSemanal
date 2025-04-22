"""
Manipulador de comandos do Discord para o sistema de relatórios.
Usa processamento otimizado de cache por projeto.
"""

import os
import logging
import time
from typing import Optional, Tuple
import re
import pandas as pd
from concurrent.futures import Future
import threading
import traceback
from queue import Queue

from report_system.config import ConfigManager
from report_system.utils.simple_cache import SimpleCacheManager
from report_system.discord_notification import DiscordNotificationManager

logger = logging.getLogger("ReportSystem")

class DiscordCommandHandler:
    """Manipulador de comandos do Discord para o sistema de relatórios."""
    
    def __init__(self, config: ConfigManager, weekly_report_system=None):
        """
        Inicializa o manipulador de comandos.
        
        Args:
            config: Instância do ConfigManager
            weekly_report_system: Instância do WeeklyReportSystem (opcional)
        """
        self.config = config
        self.report_system = weekly_report_system
        self.discord = DiscordNotificationManager(config)
        
        # Flag para indicar se devemos usar cache no Google Drive
        self.use_drive_cache = config.get_env_var("USE_DRIVE_CACHE", "false").lower() == "true"
        
        # Inicializar cache manager
        try:
            self.cache_manager = SimpleCacheManager(self.config.cache_dir)
        except Exception as e:
            logger.error(f"Erro ao inicializar SimpleCacheManager: {e}")
            self.cache_manager = None
            self.use_drive_cache = False
    
    def process_command(self, channel_id: str, command: str, 
                       project_id: Optional[str] = None) -> bool:
        """
        Processa um comando recebido via Discord.
        
        Args:
            channel_id: ID do canal do Discord
            command: Comando recebido
            project_id: ID do projeto (opcional, se não fornecido, tenta obter do canal)
            
        Returns:
            True se o comando foi processado com sucesso, False caso contrário
        """
        # Normalizar o comando
        command = command.strip().lower()
        
        # Caso não tenha project_id, tentar obter do canal
        if not project_id and self.report_system:
            try:
                project_id = self.report_system.get_project_by_discord_channel(channel_id)
                if project_id:
                    logger.info(f"ID do projeto obtido do canal Discord: {project_id}")
            except Exception as e:
                logger.error(f"Erro ao obter ID do projeto do canal: {e}")
        
        # Se ainda não temos project_id, não podemos continuar
        if not project_id:
            self.discord.send_notification(
                channel_id,
                "❌ Erro: Não foi possível identificar o projeto associado a este canal. " +
                "Por favor, especifique o ID do projeto."
            )
            return False
        
        # Processar comandos conhecidos
        if command in ["relatorio", "relatório", "report"]:
            return self._process_report_command(channel_id, project_id)
        elif command in ["atualizar", "update", "refresh"]:
            return self._process_update_command(channel_id, project_id)
        elif command in ["status", "cache"]:
            return self._process_status_command(channel_id, project_id)
        else:
            # Comando desconhecido
            self.discord.send_notification(
                channel_id,
                f"❓ Comando não reconhecido: `{command}`\n" +
                "Comandos disponíveis: `relatorio`, `atualizar`, `status`"
            )
            return False
    
    def _process_report_command(self, ctx, no_wait=False):
        """
        Processa um comando de relatório.
        
        Args:
            ctx: Contexto do comando
            no_wait: Se True, não aguarda o processamento da fila
            
        Returns:
            True se o comando foi processado com sucesso, False caso contrário
        """
        if not self.report_system.is_available():
            logger.error("Sistema de relatórios não está disponível")
            return False
            
        try:
            # Carregar a configuração do projeto
            projects_df = self.report_system._load_project_config(force_refresh=True)
            if projects_df is None or projects_df.empty:
                logger.error("Não foi possível carregar a configuração dos projetos")
                return False
                
            # Verificar e corrigir colunas para compatibilidade
            has_old_columns = 'Canal_Discord' in projects_df.columns
            has_new_columns = 'discord_id' in projects_df.columns
            
            # Situação problemática: Temos nomes novos nos métodos mas nomes antigos na planilha
            if has_old_columns and not has_new_columns:
                logger.warning("Detectada incompatibilidade de colunas no _process_report_command")
                
                # Criar cópias das colunas antigas com nomes novos para compatibilidade
                column_map = {
                    'ID_Construflow': 'construflow_id',
                    'ID_Smartsheet': 'smartsheet_id',
                    'Nome_Projeto': 'Projeto - PR',
                    'Canal_Discord': 'discord_id',
                    'Tipo_Discord': 'discord_tipo',
                    'ID_Pasta_Drive': 'pastaemails_id',
                    'Disciplinas_Cliente': 'construflow_disciplinasclientes',
                    'Ativo': 'relatoriosemanal_status'
                }
                
                # Adicionar colunas novas com dados das antigas para compatibilidade
                for old_col, new_col in column_map.items():
                    if old_col in projects_df.columns and new_col not in projects_df.columns:
                        projects_df[new_col] = projects_df[old_col]
                        logger.info(f"Adicionada coluna {new_col} como cópia de {old_col} para compatibilidade no _process_report_command")
                
                # Substituir o DataFrame no sistema
                self.report_system.project_config_df = projects_df
            
            # Obter o ID do canal
            channel_id = str(ctx.channel.id)
            author = f"{ctx.author.name}#{ctx.author.discriminator}"
            
            # Enfileirar o relatório
            future = self.enqueue_report(channel_id, author, no_wait=no_wait)
            
            if not future and not no_wait:
                logger.error(f"Não foi possível enfileirar o relatório para o canal {channel_id}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar comando de relatório: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _process_update_command(self, channel_id: str, project_id: str) -> bool:
        """
        Processa o comando para atualizar cache.
        
        Args:
            channel_id: ID do canal do Discord
            project_id: ID do projeto
            
        Returns:
            True se o comando foi processado com sucesso, False caso contrário
        """
        # Enviar mensagem inicial
        #message_id = self.discord.send_notification(
        #    channel_id,
        #    f"🔄 Iniciando atualização de cache para o projeto {project_id}...",
        #    return_message_id=True
        #)
        
        # Atualizar cache
        start_time = time.time()
        success = self._update_project_cache(channel_id, project_id)
        elapsed_time = time.time() - start_time
        
        # Formatar tempo decorrido
        if elapsed_time < 60:
            time_str = f"{elapsed_time:.1f} segundos"
        else:
            time_str = f"{elapsed_time/60:.1f} minutos"
        
        # Atualizar mensagem com status
        if success:
            self.discord.update_message(
                channel_id,
                #message_id,
                f"✅ Cache atualizado com sucesso para o projeto {project_id}! (tempo: {time_str})"
            )
            return True
        else:
            self.discord.update_message(
                channel_id,
                #message_id,
                f"❌ Erro ao atualizar cache para o projeto {project_id}. (tempo: {time_str})"
            )
            return False
    
    def _process_status_command(self, channel_id: str, project_id: str) -> bool:
        """
        Processa o comando para verificar status do cache.
        
        Args:
            channel_id: ID do canal do Discord
            project_id: ID do projeto
            
        Returns:
            True se o comando foi processado com sucesso, False caso contrário
        """
        try:
            # Verificar se o cache manager foi inicializado
            if not self.cache_manager:
                self.discord.send_notification(
                    channel_id,
                    "❌ Erro: Sistema de cache não inicializado."
                )
                return False
            
            # Obter status do cache
            status_df = self.cache_manager.get_cache_status()
            
            # Filtrar apenas entradas relacionadas ao projeto
            project_cache = status_df[status_df['file_name'].str.contains(str(project_id))]
            
            if project_cache.empty:
                self.discord.send_notification(
                    channel_id,
                    f"ℹ️ Nenhum cache encontrado para o projeto {project_id}."
                )
                return True
            
            # Formatar mensagem com status
            valid_count = len(project_cache[project_cache['age_hours'] < 24])
            total_count = len(project_cache)
            
            # Calcular idade média do cache
            avg_age_hours = project_cache['age_hours'].mean()
            if avg_age_hours < 1:
                age_str = f"{avg_age_hours*60:.0f} minutos"
            elif avg_age_hours < 24:
                age_str = f"{avg_age_hours:.1f} horas"
            else:
                age_str = f"{avg_age_hours/24:.1f} dias"
            
            message = f"📊 **Status de Cache - Projeto {project_id}**\n"
            message += f"- Arquivos de cache válidos: {valid_count}/{total_count}\n"
            message += f"- Idade média: {age_str}\n"
            
            # Adicionar detalhes dos arquivos mais desatualizados
            project_cache_sorted = project_cache.sort_values('age_hours', ascending=False)
            if not project_cache_sorted.empty:
                message += "\n**Arquivos de cache:**\n"
                for _, row in project_cache_sorted.head(3).iterrows():
                    file_name = row['file_name']
                    age = row['age_hours']
                    
                    if age < 24:
                        age_str = f"{age:.1f} horas"
                    else:
                        age_str = f"{age/24:.1f} dias"
                    
                    message += f"- {file_name}: {age_str}\n"
            
            self.discord.send_notification(channel_id, message)
            return True
        except Exception as e:
            logger.error(f"Erro ao obter status do cache: {e}")
            self.discord.send_notification(
                channel_id,
                f"❌ Erro ao obter status do cache: {str(e)}"
            )
            return False
    
    def _update_project_cache(self, channel_id: str, project_id: str) -> bool:
        """
        Atualiza o cache para um projeto específico.
        
        Args:
            channel_id: ID do canal do Discord
            project_id: ID do projeto
            
        Returns:
            True se o cache foi atualizado com sucesso, False caso contrário
        """
        if not self.report_system:
            logger.error("Sistema de relatórios não disponível")
            return False
        
        try:
            # Verificar compatibilidade de colunas na planilha
            projects_df = self.report_system._load_project_config(force_refresh=True)
            if projects_df is not None and not projects_df.empty:
                # Verificar e corrigir colunas para compatibilidade
                has_old_columns = 'ID_Construflow' in projects_df.columns
                has_new_columns = 'construflow_id' in projects_df.columns
                
                # Situação problemática: Temos nomes novos nos métodos mas nomes antigos na planilha
                if has_old_columns and not has_new_columns:
                    logger.warning("Detectada incompatibilidade de colunas na atualização de cache")
                    
                    # Criar cópias das colunas antigas com nomes novos para compatibilidade
                    column_map = {
                        'ID_Construflow': 'construflow_id',
                        'ID_Smartsheet': 'smartsheet_id',
                        'Nome_Projeto': 'Projeto - PR',
                        'Canal_Discord': 'discord_id',
                        'Tipo_Discord': 'discord_tipo',
                        'ID_Pasta_Drive': 'pastaemails_id',
                        'Disciplinas_Cliente': 'construflow_disciplinasclientes',
                        'Ativo': 'relatoriosemanal_status'
                    }
                    
                    # Adicionar colunas novas com dados das antigas para compatibilidade
                    for old_col, new_col in column_map.items():
                        if old_col in projects_df.columns and new_col not in projects_df.columns:
                            projects_df[new_col] = projects_df[old_col]
                            logger.info(f"Adicionada coluna {new_col} como cópia de {old_col} para compatibilidade no cache")
                    
                    # Substituir o DataFrame no sistema
                    self.report_system.project_config_df = projects_df
            
            # Atualizar o cache para o projeto específico
            start_time = time.time()
            message = f"🔄 Atualizando cache para o projeto {project_id}..."
            
            # Atualizar cache usando o método do sistema
            result = self.report_system._update_project_cache(project_id)
            
            elapsed_time = time.time() - start_time
            
            # Formatar o tempo decorrido
            if elapsed_time < 60:
                time_str = f"{elapsed_time:.1f} segundos"
            else:
                minutes = int(elapsed_time // 60)
                seconds = int(elapsed_time % 60)
                time_str = f"{minutes} minutos e {seconds} segundos"
            
            # Enviar mensagem de conclusão
            if result:
                logger.info(f"Cache atualizado para projeto {project_id} em {time_str}")
                return True
            else:
                logger.error(f"Falha ao atualizar cache para projeto {project_id}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao atualizar cache: {e}")
            return False

    def enqueue_report(self, channel_id, author, no_wait=False):
        """
        Adiciona uma solicitação de relatório à fila para processamento assíncrono.
        
        Args:
            channel_id: ID do canal Discord
            author: Autor da solicitação
            no_wait: Se True, não aguarda o processamento da fila
            
        Returns:
            Future se no_wait=False, None caso contrário
        """
        try:
            # Limpar o ID do canal (remover caracteres não numéricos)
            clean_channel_id = re.sub(r'\D', '', str(channel_id))
            channel_id = clean_channel_id if clean_channel_id else channel_id
            
            # Carregar a configuração do projeto
            projects_df = self.report_system._load_project_config(force_refresh=True)
            if projects_df is None or projects_df.empty:
                logger.error("Não foi possível carregar a configuração dos projetos")
                return None
                
            # Verificar e corrigir colunas para compatibilidade
            has_old_columns = 'Canal_Discord' in projects_df.columns
            has_new_columns = 'discord_id' in projects_df.columns
            
            # Situação problemática: Temos nomes novos nos métodos mas nomes antigos na planilha
            if has_old_columns and not has_new_columns:
                logger.warning("Detectada incompatibilidade de colunas no enqueue_report")
                
                # Criar cópias das colunas antigas com nomes novos para compatibilidade
                column_map = {
                    'ID_Construflow': 'construflow_id',
                    'ID_Smartsheet': 'smartsheet_id',
                    'Nome_Projeto': 'Projeto - PR',
                    'Canal_Discord': 'discord_id',
                    'Tipo_Discord': 'discord_tipo',
                    'ID_Pasta_Drive': 'pastaemails_id',
                    'Disciplinas_Cliente': 'construflow_disciplinasclientes',
                    'Ativo': 'relatoriosemanal_status'
                }
                
                # Adicionar colunas novas com dados das antigas para compatibilidade
                for old_col, new_col in column_map.items():
                    if old_col in projects_df.columns and new_col not in projects_df.columns:
                        projects_df[new_col] = projects_df[old_col]
                        logger.info(f"Adicionada coluna {new_col} como cópia de {old_col} para compatibilidade no enqueue_report")
                
                # Substituir o DataFrame no sistema
                self.report_system.project_config_df = projects_df
                
            # Filtrar projetos com o ID do canal correspondente
            projects = projects_df[projects_df['discord_id'] == str(channel_id)]
            
            if projects.empty:
                logger.error(f"Nenhum projeto encontrado para o canal {channel_id}")
                return None
                
            # Obter o primeiro projeto correspondente
            project = projects.iloc[0]
            
            # Criar opções de relatório
            report_options = {
                'author': author,
                'channel_id': channel_id,
                'project_id': project['construflow_id'] if 'construflow_id' in project and not pd.isna(project['construflow_id']) else None,
                'project_name': project['Projeto - PR'] if 'Projeto - PR' in project and not pd.isna(project['Projeto - PR']) else None,
            }
            
            # Adicionar à fila
            if no_wait:
                self.report_queue.put(report_options)
                return None
            else:
                future = Future()
                self.report_queue.put((report_options, future))
                return future
                
        except Exception as e:
            logger.error(f"Erro ao enfileirar relatório para o canal {channel_id}: {e}")
            logger.error(traceback.format_exc())
            return None