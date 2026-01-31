"""
Módulo para controle de relatórios semanais.
Verifica quais projetos deveriam gerar relatórios e notifica coordenadores que não geraram.
"""

import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class WeeklyReportStatus:
    """Status de um relatório semanal."""
    project_name: str
    coordinator_name: str
    coordinator_discord_id: str
    should_generate: bool
    was_generated: bool
    week_number: str
    week_text: str

class WeeklyReportController:
    """Controlador de relatórios semanais."""
    
    def __init__(self, config_manager):
        """
        Inicializa o controlador.
        
        Args:
            config_manager: Gerenciador de configuração
        """
        self.config = config_manager
        self.gdrive = None

        # IDs das planilhas (obtidos via configuração)
        self.control_sheet_id = self.config.get_weekly_report_control_sheet_id()
        self.base_sheet_id = self.config.get_weekly_report_base_sheet_id()

        # Inicializar Google Drive
        self._initialize_google_drive()
    
    def _initialize_google_drive(self):
        """Inicializa o conector do Google Drive."""
        try:
            from report_system.storage.google_drive import GoogleDriveManager
            self.gdrive = GoogleDriveManager(self.config)
            logger.info("Google Drive inicializado para controle de relatórios")
        except Exception as e:
            logger.error(f"Erro ao inicializar Google Drive: {e}")
            self.gdrive = None
    
    def get_current_week_info(self) -> Tuple[str, str]:
        """
        Obtém informações da semana atual.
        
        Returns:
            Tupla com (número da semana, texto da semana)
        """
        today = datetime.now()
        
        # Calcular número da semana (semana do ano)
        week_number = str(today.isocalendar()[1])
        
        # Calcular início e fim da semana (segunda a domingo)
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        sunday = monday + timedelta(days=6)
        
        # Formatar texto da semana
        week_text = f"Semana {monday.strftime('%d/%m')} - {sunday.strftime('%d/%m')}"
        
        logger.info(f"Semana atual: {week_number} - {week_text}")
        return week_number, week_text
    
    def load_control_sheet(self) -> pd.DataFrame:
        """
        Carrega a planilha de controle de relatórios.
        
        Returns:
            DataFrame com dados da planilha de controle
        """
        try:
            if not self.gdrive:
                logger.error("Google Drive não inicializado")
                return pd.DataFrame()
            
            # Carregar apenas as colunas A:D da aba "Base" para evitar colunas duplicadas
            control_df = self.gdrive.read_sheet(
                spreadsheet_id=self.control_sheet_id,
                range_name="Base!A:D"
            )
            
            if control_df.empty:
                logger.warning("Planilha de controle vazia")
                return pd.DataFrame()
            
            # Renomear colunas para facilitar o uso
            control_df.columns = ['Semana', 'Txt_Semana', 'Projeto', 'Coordenador']
            
            logger.info(f"Planilha de controle carregada: {len(control_df)} registros")
            return control_df
            
        except Exception as e:
            logger.error(f"Erro ao carregar planilha de controle: {e}")
            return pd.DataFrame()
    
    def load_base_sheet(self) -> pd.DataFrame:
        """
        Carrega a planilha base com informações dos projetos.
        
        Returns:
            DataFrame com dados da planilha base
        """
        try:
            if not self.gdrive:
                logger.error("Google Drive não inicializado")
                return pd.DataFrame()
            
            # Carregar aba "Port - Links" da planilha base
            # Colunas: Projeto - PR (B), Coordenador (users) (E), relatoriosemanal_status (J), coordenador_discord_id (U)
            base_df = self.gdrive.read_sheet(
                spreadsheet_id=self.base_sheet_id,
                range_name="Port - Links!A:Z"  # Carregar todas as colunas para facilitar
            )
            
            if base_df.empty:
                logger.warning("Planilha base vazia")
                return pd.DataFrame()
            
            # Verificar se as colunas necessárias existem
            required_columns = ['Projeto - PR', 'Coordenador (users)', 'relatoriosemanal_status', 'coordenador_discord_id']
            available_columns = list(base_df.columns)
            
            logger.info(f"Colunas disponíveis: {available_columns}")
            
            # Selecionar apenas as colunas necessárias
            selected_columns = []
            for col in required_columns:
                if col in available_columns:
                    selected_columns.append(col)
                else:
                    logger.warning(f"Coluna '{col}' não encontrada na planilha")
            
            if len(selected_columns) < 2:
                logger.error("Colunas insuficientes encontradas na planilha")
                return pd.DataFrame()
            
            # Filtrar apenas as colunas necessárias
            base_df = base_df[selected_columns]
            
            # Renomear colunas para facilitar o uso
            column_mapping = {
                'Projeto - PR': 'Projeto',
                'Coordenador (users)': 'Coordenador',
                'relatoriosemanal_status': 'Relatorio_Semanal',
                'coordenador_discord_id': 'Discord_ID'
            }
            
            base_df = base_df.rename(columns=column_mapping)
            
            logger.info(f"Planilha base carregada: {len(base_df)} registros")
            logger.info(f"Colunas finais: {list(base_df.columns)}")
            
            return base_df
            
        except Exception as e:
            logger.error(f"Erro ao carregar planilha base: {e}")
            return pd.DataFrame()
    
    def get_weekly_report_status(self) -> List[WeeklyReportStatus]:
        """
        Obtém o status dos relatórios da semana atual.
        
        Returns:
            Lista com status dos relatórios
        """
        try:
            # Obter informações da semana atual
            current_week, current_week_text = self.get_current_week_info()
            
            # Carregar planilhas
            control_df = self.load_control_sheet()
            base_df = self.load_base_sheet()
            
            if control_df.empty or base_df.empty:
                logger.error("Não foi possível carregar as planilhas")
                return []
            
            # Filtrar registros da semana atual na planilha de controle
            # Converter current_week para inteiro para comparação correta
            week_control = control_df[control_df['Semana'] == int(current_week)]
            
            logger.info(f"Registros da semana atual ({current_week}): {len(week_control)}")
            
            # Debug: mostrar alguns registros da semana atual
            if not week_control.empty:
                logger.info("Exemplos de registros da semana atual:")
                for i, (_, row) in enumerate(week_control.head(3).iterrows()):
                    logger.info(f"  {i+1}. Projeto: {row.get('Projeto', 'N/A')} | Coordenador: {row.get('Coordenador', 'N/A')}")
            else:
                logger.warning(f"Nenhum registro encontrado para semana {current_week}")
                # Debug: mostrar todas as semanas disponíveis
                if 'Semana' in control_df.columns:
                    semanas_disponiveis = control_df['Semana'].unique()
                    logger.info(f"Semanas disponíveis na planilha: {list(semanas_disponiveis)}")
            
            # Criar lista de status
            status_list = []
            
            # Para cada projeto na planilha base
            for _, base_row in base_df.iterrows():
                project_name = base_row['Projeto']
                coordinator_name = base_row['Coordenador']
                coordinator_discord_id = base_row.get('Discord_ID', '')
                should_generate = base_row.get('Relatorio_Semanal', '').lower() == 'sim'
                
                # Verificar se foi gerado na semana atual - MELHORAR A BUSCA
                was_generated = False
                if not week_control.empty:
                    # Buscar por projeto E coordenador
                    matching_rows = week_control[
                        (week_control['Projeto'].str.contains(project_name, case=False, na=False)) | 
                        (week_control['Projeto'] == project_name)
                    ]
                    
                    # Se encontrou pelo projeto, verificar se o coordenador também bate
                    if not matching_rows.empty:
                        for _, control_row in matching_rows.iterrows():
                            control_coordinator = control_row.get('Coordenador', '')
                            if (control_coordinator.lower() == coordinator_name.lower() or 
                                coordinator_name.lower() in control_coordinator.lower() or
                                control_coordinator.lower() in coordinator_name.lower()):
                                was_generated = True
                                logger.debug(f"✅ Relatório encontrado: {project_name} - {coordinator_name}")
                                break
                
                status = WeeklyReportStatus(
                    project_name=project_name,
                    coordinator_name=coordinator_name,
                    coordinator_discord_id=str(coordinator_discord_id),
                    should_generate=should_generate,
                    was_generated=was_generated,
                    week_number=current_week,
                    week_text=current_week_text
                )
                
                status_list.append(status)
            
            # Debug: mostrar estatísticas
            total_should_generate = sum(1 for s in status_list if s.should_generate)
            total_was_generated = sum(1 for s in status_list if s.was_generated)
            total_missing = sum(1 for s in status_list if s.should_generate and not s.was_generated)
            
            logger.info(f"Status de relatórios processado: {len(status_list)} projetos")
            logger.info(f"Devem gerar: {total_should_generate} | Já gerados: {total_was_generated} | Em falta: {total_missing}")
            
            return status_list
            
        except Exception as e:
            logger.error(f"Erro ao obter status dos relatórios: {e}")
            return []
    
    def get_missing_reports_by_coordinator(self) -> Dict[str, List[str]]:
        """
        Obtém projetos com relatórios em falta, agrupados por coordenador.
        
        Returns:
            Dicionário com {coordenador: [lista_de_projetos]}
        """
        status_list = self.get_weekly_report_status()
        
        missing_reports = {}
        
        for status in status_list:
            if status.should_generate and not status.was_generated:
                coordinator = status.coordinator_name
                if coordinator not in missing_reports:
                    missing_reports[coordinator] = []
                missing_reports[coordinator].append(status.project_name)
        
        logger.info(f"Relatórios em falta: {len(missing_reports)} coordenadores")
        return missing_reports
    
    def generate_missing_reports_message(self, channel_id: str = None) -> str:
        """
        Gera mensagem para notificar coordenadores sobre relatórios em falta.
        
        Args:
            channel_id: ID do canal para enviar a mensagem (opcional)
            
        Returns:
            Mensagem formatada
        """
        missing_reports = self.get_missing_reports_by_coordinator()
        
        if not missing_reports:
            return "✅ Todos os relatórios da semana foram gerados!"
        
        current_week, current_week_text = self.get_current_week_info()
        
        message = f"⚠️ **RELATÓRIOS EM FALTA - {current_week_text}**\n\n"
        message += "👥 **Coordenadores com relatórios pendentes:**\n\n"
        
        for coordinator, projects in missing_reports.items():
            # Buscar o Discord ID do coordenador
            coordinator_discord_id = ""
            status_list = self.get_weekly_report_status()
            for status in status_list:
                if status.coordinator_name == coordinator:
                    coordinator_discord_id = status.coordinator_discord_id
                    break
            
            # Formatar a mensagem com marcação do Discord
            if coordinator_discord_id and coordinator_discord_id.strip():
                message += f"<@{coordinator_discord_id}> - {len(projects)} projeto(s)\n"
            else:
                message += f"**{coordinator}** (Discord ID não configurado) - {len(projects)} projeto(s)\n"
            
            # Listar os projetos
            for project in projects:
                message += f"  • {project}\n"
            message += "\n"
        
        message += "📋 **Total:** " + str(sum(len(projects) for projects in missing_reports.values())) + " relatórios pendentes"
        
        return message
    
    def send_missing_reports_notification(self, channel_id: str) -> bool:
        """
        Envia notificação sobre relatórios em falta para um canal específico.
        
        Args:
            channel_id: ID do canal do Discord
            
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        try:
            if not self.gdrive:
                logger.error("Google Drive não inicializado")
                return False
            
            # Gerar mensagem
            message = self.generate_missing_reports_message()
            
            # Enviar via Discord
            from report_system.discord_notification import DiscordNotificationManager
            discord = DiscordNotificationManager(self.config)
            
            success = discord.send_notification(channel_id, message)
            
            if success:
                logger.info(f"Notificação de relatórios em falta enviada para canal {channel_id}")
            else:
                logger.error(f"Falha ao enviar notificação para canal {channel_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {e}")
            return False
    
    def send_direct_notifications_to_coordinators(self, admin_channel_id: str = None) -> bool:
        """
        Envia notificações diretas para coordenadores que não geraram relatórios.
        
        Args:
            admin_channel_id: ID do canal admin para logs (opcional)
            
        Returns:
            True se pelo menos uma notificação foi enviada com sucesso
        """
        try:
            status_list = self.get_weekly_report_status()
            missing_coordinators = {}
            
            # Agrupar coordenadores com relatórios em falta
            for status in status_list:
                if status.should_generate and not status.was_generated:
                    if status.coordinator_discord_id and status.coordinator_discord_id != 'nan':
                        if status.coordinator_discord_id not in missing_coordinators:
                            missing_coordinators[status.coordinator_discord_id] = []
                        missing_coordinators[status.coordinator_discord_id].append(status.project_name)
            
            if not missing_coordinators:
                logger.info("Nenhum coordenador com relatórios em falta")
                return True
            
            # Enviar notificações diretas
            from report_system.discord_notification import DiscordNotificationManager
            discord = DiscordNotificationManager(self.config)
            
            current_week, current_week_text = self.get_current_week_info()
            success_count = 0
            
            for coordinator_id, projects in missing_coordinators.items():
                try:
                    message = f"⚠️ **RELATÓRIO SEMANAL PENDENTE**\n\n"
                    message += f"Olá! Você ainda não gerou o relatório da **{current_week_text}**.\n\n"
                    message += "**Projetos pendentes:**\n"
                    for project in projects:
                        message += f"• {project}\n"
                    message += "\nUse o comando `!relatorio` no canal do projeto para gerar."
                    
                    success = discord.send_direct_message(coordinator_id, message)
                    if success:
                        success_count += 1
                        logger.info(f"Notificação enviada para coordenador {coordinator_id}")
                    else:
                        logger.warning(f"Falha ao enviar notificação para coordenador {coordinator_id}")
                        
                except Exception as e:
                    logger.error(f"Erro ao enviar notificação para coordenador {coordinator_id}: {e}")
            
            # Log no canal admin se fornecido
            if admin_channel_id:
                admin_message = f"📊 **CONTROLE DE RELATÓRIOS - {current_week_text}**\n\n"
                admin_message += f"Notificações enviadas: {success_count}/{len(missing_coordinators)} coordenadores"
                discord.send_notification(admin_channel_id, admin_message)
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificações diretas: {e}")
            return False
    
    def send_weekly_report_notification(self) -> bool:
        """
        Envia notificação semanal para o canal configurado no .env.
        
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        try:
            # Pegar o canal do .env
            channel_id = self.config.get_discord_notification_channel_id()
            
            if not channel_id:
                logger.error("DISCORD_NOTIFICATION_CHANNEL_ID não configurado no .env")
                return False
            
            return self.send_missing_reports_notification(channel_id)
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação semanal: {e}")
            return False