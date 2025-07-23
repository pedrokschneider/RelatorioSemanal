"""
Manipulador de comandos do Discord para o sistema de relatórios.
Usa processamento otimizado de cache por projeto.
"""

import os
import logging
import time
from typing import Optional, Tuple

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
    
    def _process_report_command(self, channel_id: str, project_id: str) -> bool:
        """
        Processa o comando para gerar relatório.
        
        Args:
            channel_id: ID do canal do Discord
            project_id: ID do projeto
            
        Returns:
            True se o comando foi processado com sucesso, False caso contrário
        """
        if not self.report_system:
            logger.error("Sistema de relatórios não disponível")
            self.discord.send_notification(
                channel_id,
                "❌ Erro: Sistema de relatórios não disponível."
            )
            return False
        
        # Atualizar cache do projeto primeiro de forma otimizada
        success = self._update_project_cache(channel_id, project_id)
        
        if not success:
            self.discord.send_notification(
                channel_id,
                f"⚠️ Atenção: Não foi possível atualizar o cache para o projeto {project_id}. " +
                "Continuando com os dados existentes."
            )
        
        # Gerar relatório
        try:
            result = self.report_system.run_for_project(project_id)
            success, file_path, drive_id = result
            
            if success:
                # Mensagem de sucesso
                if drive_id:
                    doc_url = f"https://docs.google.com/document/d/{drive_id}/edit"
                    
                    # Tentar obter pasta do projeto
                    project_folder_id = None
                    try:
                        # Obter nome do projeto
                        project_name = self.report_system.processor.construflow.get_projects()[
                            self.report_system.processor.construflow.get_projects()['id'] == project_id
                        ]['name'].values[0]
                        
                        project_folder_id = self.report_system.gdrive.get_project_folder(
                            project_id, 
                            project_name
                        )
                    except Exception as e:
                        logger.warning(f"Erro ao obter pasta do projeto: {e}")
                        project_name = "Projeto"
                    
                    # Usar o formato de mensagem padrão do sistema
                    folder_url = f"https://drive.google.com/drive/folders/{project_folder_id}" if project_folder_id else None
                    
                    # Usar a função de formatação do sistema principal
                    final_message = self.report_system._format_final_success_message(project_name, doc_url, folder_url)
                    
                    # Enviar a mensagem formatada
                    self.discord.send_notification(
                        channel_id,
                        final_message
                    )
                else:
                    self.discord.send_notification(
                        channel_id,
                        f"✅ Relatório gerado localmente com sucesso, mas não foi possível enviá-lo ao Google Drive."
                    )
                return True
            else:
                self.discord.send_notification(
                    channel_id,
                    f"❌ Ocorreu um erro ao gerar o relatório para o projeto {project_id}. Antes de entrar em contato com o suporte, verifique se as colunas **STATUS** e **DISCIPLINA** do cronograma do SmartSheet não possuem dados vazios."
                )
                return False
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            self.discord.send_notification(
                channel_id,
                f"❌ Ocorreu um erro ao gerar o relatório. Antes de entrar em contato com o suporte, verifique se as colunas **STATUS** e **DISCIPLINA** do cronograma do SmartSheet não possuem dados vazios."
            )
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
            True se a atualização foi bem-sucedida, False caso contrário
        """
        try:
            # Verificar se o sistema de relatórios está disponível
            if not self.report_system:
                logger.error("Sistema de relatórios não disponível")
                return False
            
            # Verificar se o cache manager foi inicializado
            if not self.cache_manager:
                logger.error("Cache manager não inicializado")
                return False
            
            # Atualizar dados do Construflow
            logger.info(f"Atualizando dados de issues do Construflow para projeto {project_id}")
            construflow = self.report_system.processor.construflow
            
            # Obter issues do projeto
            issues_df = construflow.get_project_issues(project_id, force_refresh=True)
            logger.info(f"Cache de issues atualizado para projeto {project_id}: {len(issues_df)} issues")
            
            # Salvar issues no novo sistema de cache
            if not issues_df.empty:
                self.cache_manager.save_construflow_data('issues', issues_df.to_dict('records'))
            
            # Buscar ID do Smartsheet para este projeto
            smartsheet_id = self.report_system.get_project_smartsheet_id(project_id)
            
            if smartsheet_id:
                # Atualizar dados do Smartsheet
                logger.info(f"Atualizando dados do Smartsheet para projeto {project_id} (ID: {smartsheet_id})")
                try:
                    sheet_data = self.report_system.processor.smartsheet.get_sheet(
                        smartsheet_id, 
                        force_refresh=True
                    )
                    if sheet_data:
                        logger.info(f"Cache do Smartsheet atualizado para projeto {project_id}")
                        
                        # Salvar dados do Smartsheet usando o novo método
                        self.cache_manager.save_smartsheet_data(
                            smartsheet_id, 
                            project_id, 
                            sheet_data
                        )
                except Exception as e:
                    logger.error(f"Erro ao atualizar Smartsheet para {project_id}: {e}")
            
            logger.info(f"Atualização de cache para projeto {project_id} concluída")
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar cache para projeto {project_id}: {e}")
            return False