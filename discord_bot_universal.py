#!/usr/bin/env python3
"""
Bot Discord Universal - Escuta todos os canais e tópicos do servidor.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
log_dir = os.path.join(os.getcwd(), "logs")
os.makedirs(log_dir, exist_ok=True)

today_str = datetime.now().strftime("%Y-%m-%d")
bot_log_file = os.path.join(log_dir, f"discord_bot_universal_{today_str}.log")

bot_logger = logging.getLogger("DiscordBotUniversal")
bot_logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(bot_log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
bot_logger.addHandler(file_handler)

logger = bot_logger

try:
    import discord
    from discord.ext import commands
except ImportError:
    logger.error("Discord.py não está instalado. Execute: pip install discord.py")
    sys.exit(1)

class DiscordBotUniversal:
    """Bot Discord que escuta todos os canais e tópicos."""
    
    def __init__(self):
        """Inicializa o bot universal."""
        logger.info("Inicializando bot Discord Universal 🤖")
        
        try:
            # Importar sistema de relatórios
            from report_system.main import WeeklyReportSystem
            from report_system.discord_notification import DiscordNotificationManager
            from report_queue import ReportQueue
            
            # Inicializar sistema de relatórios
            self.report_system = WeeklyReportSystem(verbose_init=False)
            logger.info("Sistema de relatórios inicializado com sucesso")
            
            # Obter gerenciador de Discord
            self.discord_manager = self.report_system.discord
            if not self.discord_manager:
                logger.info("Criando gerenciador de Discord próprio")
                self.discord_manager = DiscordNotificationManager(self.report_system.config)
            
            # Token do Discord
            self.token = self.discord_manager.discord_token if hasattr(self.discord_manager, 'discord_token') else os.getenv('DISCORD_TOKEN', '')
            
            if not self.token:
                logger.error("Token do Discord não configurado")
                raise ValueError("DISCORD_TOKEN não encontrado")
            
            # Configurar bot Discord
            intents = discord.Intents.default()
            intents.message_content = True
            intents.guilds = True
            intents.guild_messages = True
            
            self.bot = commands.Bot(command_prefix='!', intents=intents)
            
            # Sistema de filas
            self.queue_system = ReportQueue(self, max_workers=2)
            logger.info("Sistema de filas inicializado com sucesso")
            
            # Armazenar informações dos canais/projetos
            self.channels_info = {}
            self.load_channels_info()
            
            # Configurar comandos
            self.setup_commands()
            
            logger.info("Bot Universal inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar bot universal: {e}", exc_info=True)
            raise
    
    def load_channels_info(self):
        """Carrega informações dos canais da planilha."""
        try:
            self.channels_info = self.get_channels_from_spreadsheet()
            logger.info(f"Carregados {len(self.channels_info)} canais da planilha")
        except Exception as e:
            logger.error(f"Erro ao carregar canais: {e}")
            self.channels_info = {}
    
    def get_channels_from_spreadsheet(self):
        """Obtém canais da planilha de configuração."""
        try:
            projects_df = self.report_system._load_project_config()
            
            if projects_df is None or projects_df.empty:
                logger.error("Planilha de configuração vazia ou inacessível")
                return {}
            
            if 'discord_id' not in projects_df.columns:
                logger.error(f"Coluna 'discord_id' não encontrada")
                return {}
            
            # Filtrar projetos ativos
            if 'relatoriosemanal_status' in projects_df.columns:
                active_projects = projects_df[projects_df['relatoriosemanal_status'].str.lower() == 'sim']
            else:
                active_projects = projects_df
            
            # Filtrar projetos com discord_id
            projects_with_channel = active_projects[active_projects['discord_id'].notna()]
            
            channels_dict = {}
            for _, row in projects_with_channel.iterrows():
                channel_id = str(row['discord_id']).strip()
                project_id = str(row.get('construflow_id', '')).strip()
                project_name = str(row.get('Projeto - PR', 'Projeto sem nome')).strip()
                
                channel_id_clean = ''.join(c for c in channel_id if c.isdigit())
                
                if channel_id_clean:
                    channels_dict[channel_id_clean] = {
                        'project_id': project_id,
                        'project_name': project_name
                    }
            
            # Adicionar canal admin
            admin_channel_id = self.report_system.config.get_discord_admin_channel_id()
            if admin_channel_id:
                admin_channel_clean = ''.join(c for c in admin_channel_id if c.isdigit())
                if admin_channel_clean:
                    channels_dict[admin_channel_clean] = {
                        'project_id': 'ADMIN',
                        'project_name': 'Canal Administrativo'
                    }
            
            return channels_dict
            
        except Exception as e:
            logger.error(f"Erro ao obter canais da planilha: {e}")
            return {}
    
    def setup_commands(self):
        """Configura os comandos do bot."""
        
        @self.bot.event
        async def on_ready():
            """Evento quando o bot está pronto."""
            logger.info(f"Bot Universal conectado como {self.bot.user}")
            logger.info(f"Servidores conectados: {len(self.bot.guilds)}")
            
            # Listar servidores
            for guild in self.bot.guilds:
                logger.info(f"Servidor: {guild.name} (ID: {guild.id})")
                logger.info(f"  Canais: {len(guild.channels)}")
                logger.info(f"  Tópicos: {len(guild.threads)}")
        
        @self.bot.event
        async def on_message(message):
            """Evento quando uma mensagem é recebida."""
            # Ignorar mensagens do próprio bot
            if message.author == self.bot.user:
                return
            
            # Processar comandos
            await self.bot.process_commands(message)
        
        @self.bot.command(name='relatorio')
        async def relatorio(ctx):
            """Comando para gerar relatório semanal."""
            channel_id = str(ctx.channel.id)
            
            # Verificar se é um canal configurado
            if channel_id in self.channels_info:
                project_info = self.channels_info[channel_id]
                project_name = project_info['project_name']
                
                # Validar canal
                validation = self.validate_channel_for_reports(channel_id)
                
                if validation['valid']:
                    # Adicionar à fila
                    await ctx.send(f"📋 **Relatório Solicitado**\n\n"
                                 f"**Projeto:** {project_name}\n"
                                 f"**Canal:** {ctx.channel.mention}\n"
                                 f"**Status:** Adicionado à fila de processamento\n\n"
                                 f"⏳ Aguarde o processamento...")
                    
                    # Processar relatório
                    try:
                        self.process_report_command(channel_id, "!relatorio")
                        await ctx.send(f"✅ **Relatório Processado**\n\n"
                                     f"**Projeto:** {project_name}\n"
                                     f"**Status:** Relatório gerado com sucesso!")
                    except Exception as e:
                        await ctx.send(f"❌ **Erro ao Processar**\n\n"
                                     f"**Projeto:** {project_name}\n"
                                     f"**Erro:** {str(e)}")
                else:
                    await ctx.send(validation['message'])
            else:
                # Canal não configurado
                await ctx.send(self.get_channel_not_configured_message(channel_id))
        
        @self.bot.command(name='fila')
        async def fila(ctx):
            """Comando para ver status da fila."""
            channel_id = str(ctx.channel.id)
            
            if channel_id in self.channels_info:
                status_text = self.queue_system.show_queue_status()
                await ctx.send(f"📊 **Status da Fila**\n\n{status_text}")
            else:
                await ctx.send("❌ Este comando só funciona em canais configurados para relatórios.")
        
        @self.bot.command(name='status')
        async def status(ctx):
            """Alias para o comando fila."""
            await fila(ctx)
        
        @self.bot.command(name='controle')
        async def controle(ctx):
            """Comando para verificar controle de relatórios."""
            channel_id = str(ctx.channel.id)
            
            if channel_id in self.channels_info:
                try:
                    self.process_report_command(channel_id, "!controle")
                    await ctx.send("✅ Controle de relatórios verificado!")
                except Exception as e:
                    await ctx.send(f"❌ Erro ao verificar controle: {str(e)}")
            else:
                await ctx.send("❌ Este comando só funciona em canais configurados para relatórios.")
        
        @self.bot.command(name='notificar')
        async def notificar(ctx):
            """Comando para enviar notificação de relatórios em falta."""
            channel_id = str(ctx.channel.id)
            
            # Verificar se é o canal admin
            admin_channel_id = self.report_system.config.get_discord_admin_channel_id()
            admin_channel_clean = ''.join(c for c in admin_channel_id if c.isdigit()) if admin_channel_id else None
            
            if channel_id == admin_channel_clean:
                try:
                    self.process_report_command(channel_id, "!notificar")
                    await ctx.send("✅ Notificação de relatórios em falta enviada!")
                except Exception as e:
                    await ctx.send(f"❌ Erro ao enviar notificação: {str(e)}")
            else:
                await ctx.send("❌ Este comando só funciona no canal administrativo.")
        
        @self.bot.command(name='notificar_coordenadores')
        async def notificar_coordenadores(ctx):
            """Comando para enviar notificações diretas aos coordenadores."""
            channel_id = str(ctx.channel.id)
            
            # Verificar se é o canal admin
            admin_channel_id = self.report_system.config.get_discord_admin_channel_id()
            admin_channel_clean = ''.join(c for c in admin_channel_id if c.isdigit()) if admin_channel_id else None
            
            if channel_id == admin_channel_clean:
                try:
                    self.process_report_command(channel_id, "!notificar_coordenadores")
                    await ctx.send("✅ Notificações diretas enviadas aos coordenadores!")
                except Exception as e:
                    await ctx.send(f"❌ Erro ao enviar notificações: {str(e)}")
            else:
                await ctx.send("❌ Este comando só funciona no canal administrativo.")
        
        @self.bot.command(name='topico')
        async def topico(ctx):
            """Comando para encontrar tópico correto."""
            channel_id = str(ctx.channel.id)
            
            if channel_id in self.channels_info:
                thread_info = self.get_correct_thread_info(channel_id)
                if thread_info:
                    await ctx.send(thread_info)
                else:
                    await ctx.send("❌ Tópico não encontrado para este projeto.")
            else:
                await ctx.send("❌ Este comando só funciona em canais configurados para relatórios.")
        
        @self.bot.command(name='canais')
        async def canais(ctx):
            """Comando para listar canais ativos."""
            channels_list = self._get_active_channels_list()
            await ctx.send(f"📋 **Canais Ativos para Relatórios**\n\n{channels_list}")
        
        @self.bot.command(name='ajuda')
        async def ajuda(ctx):
            """Comando de ajuda."""
            help_text = """
🤖 **Bot de Relatórios Semanais - Ajuda**

**Comandos Disponíveis:**

📋 **!relatorio** - Gerar relatório semanal
📊 **!fila** ou **!status** - Ver status da fila de processamento
🔍 **!controle** - Verificar controle de relatórios semanais
📢 **!notificar** - Enviar notificação de relatórios em falta (só admin)
👥 **!notificar_coordenadores** - Enviar notificações diretas (só admin)
📋 **!topico** - Encontrar tópico correto do projeto
📋 **!canais** - Listar canais ativos para relatórios
❓ **!ajuda** - Mostrar esta mensagem de ajuda

**Observações:**
• O bot funciona em **todos os canais e tópicos** do servidor
• Comandos de relatório só funcionam em canais configurados
• Comandos administrativos só funcionam no canal admin
• Use **!canais** para ver quais projetos estão ativos
"""
            await ctx.send(help_text)
    
    def validate_channel_for_reports(self, channel_id):
        """Valida se um canal está configurado para relatórios."""
        try:
            if channel_id not in self.channels_info:
                return {
                    'valid': False,
                    'reason': 'not_configured',
                    'message': self.get_channel_not_configured_message(channel_id)
                }
            
            project_info = self.channels_info[channel_id]
            project_name = project_info['project_name']
            
            # Carregar planilha para validação completa
            projects_df = self.report_system._load_project_config()
            
            if projects_df is None or projects_df.empty:
                return {
                    'valid': False,
                    'reason': 'spreadsheet_error',
                    'message': "❌ Erro ao carregar planilha de configuração"
                }
            
            # Buscar projeto na planilha
            project_row = projects_df[projects_df['discord_id'].astype(str).str.contains(channel_id, na=False)]
            
            if project_row.empty:
                return {
                    'valid': False,
                    'reason': 'not_found',
                    'message': f"❌ Projeto não encontrado na planilha"
                }
            
            row = project_row.iloc[0]
            
            # Verificar se está ativo
            if 'relatoriosemanal_status' in projects_df.columns:
                status = str(row.get('relatoriosemanal_status', '')).strip().lower()
                if status != 'sim':
                    return {
                        'valid': False,
                        'reason': 'disabled',
                        'message': f"❌ **Relatórios Desativados**\n\n"
                                 f"O projeto **{project_name}** está com relatórios semanais desativados.\n\n"
                                 f"**Status atual:** {status.upper()}\n\n"
                                 f"**Para reativar:**\n"
                                 f"📧 Entre em contato com o time de Dados e Tecnologia\n"
                                 f"📋 Solicite a reativação do projeto: {project_name}"
                    }
            
            # Verificar se tem ID do Construflow
            construflow_id = str(row.get('construflow_id', '')).strip()
            if not construflow_id:
                return {
                    'valid': False,
                    'reason': 'incomplete',
                    'message': f"❌ **Projeto Incompleto**\n\n"
                             f"O projeto **{project_name}** não possui ID do Construflow configurado.\n\n"
                             f"**Para completar o cadastro:**\n"
                             f"📧 Entre em contato com o time de Dados e Tecnologia\n"
                             f"📋 Solicite a configuração do ID Construflow para: {project_name}"
                }
            
            return {
                'valid': True,
                'project_name': project_name,
                'project_id': construflow_id
            }
            
        except Exception as e:
            logger.error(f"Erro na validação do canal {channel_id}: {e}")
            return {
                'valid': False,
                'reason': 'error',
                'message': f"❌ Erro na validação: {str(e)}"
            }
    
    def get_channel_not_configured_message(self, channel_id):
        """Retorna mensagem para canal não configurado."""
        channels_list = self._get_active_channels_list()
        
        return f"""❌ **Canal Não Configurado**

Este canal não está configurado para gerar relatórios semanais.

**Para solicitar o cadastro:**
📧 Entre em contato com o time de Dados e Tecnologia
📋 Informe o nome do projeto e o ID do canal: `{channel_id}`

**Canais ativos disponíveis:**
{channels_list}"""
    
    def _get_active_channels_list(self):
        """Retorna lista formatada de canais ativos."""
        if not self.channels_info:
            return "Nenhum canal configurado"
        
        channels_list = []
        for channel_id, info in self.channels_info.items():
            project_name = info['project_name']
            channels_list.append(f"• **{project_name}** (Canal: `{channel_id}`)")
        
        return "\n".join(channels_list[:10])  # Limitar a 10 canais
    
    def get_correct_thread_info(self, channel_id):
        """Retorna informação sobre o tópico correto."""
        if channel_id not in self.channels_info:
            return None
        
        project_info = self.channels_info[channel_id]
        project_name = project_info['project_name']
        
        return f"""📋 **Tópico Correto:**

Para o projeto **{project_name}**, use o comando `!relatorio` no tópico dedicado:
<#{channel_id}>

**Observação:** Este comando funciona em qualquer canal, mas o relatório será gerado para o projeto correto."""
    
    def process_report_command(self, channel_id, command):
        """Processa comandos de relatório."""
        try:
            # Importar função de processamento do bot original
            from discord_bot import DiscordBotAutoChannels
            temp_bot = DiscordBotAutoChannels()
            temp_bot.channels_info = self.channels_info
            temp_bot.report_system = self.report_system
            temp_bot.queue_system = self.queue_system
            
            return temp_bot.process_command(channel_id, command)
        except Exception as e:
            logger.error(f"Erro ao processar comando {command}: {e}")
            raise
    
    async def start(self):
        """Inicia o bot."""
        try:
            logger.info("Iniciando bot Universal...")
            await self.bot.start(self.token)
        except Exception as e:
            logger.error(f"Erro ao iniciar bot: {e}")
            raise

def main():
    """Função principal."""
    try:
        bot = DiscordBotUniversal()
        
        # Executar o bot
        asyncio.run(bot.start())
        
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 