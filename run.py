import os
import io
import sys
import logging
import argparse
import time
from datetime import datetime
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# Configurar logging básico (será substituído pelo setup_logging depois)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ReportSystemRunner")

# Adicione o caminho do diretório atual ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importe diretamente do arquivo, não através do pacote
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))
from report_system.utils.logging_config import setup_logging

# Agora substitua com a configuração avançada
logger = setup_logging()

# Importar a classe principal depois de configurar o logging
from report_system.main import WeeklyReportSystem

def main():
    """Função principal para executar o sistema de relatórios."""
    # Carregar "variáveis de ambiente do arquivo .env
    load_dotenv()
    
    logger.info("Inicializando o sistema de relatórios")
    
    # Configurar argumentos da linha de comando
    parser = argparse.ArgumentParser(description='Sistema de Relatórios Semanais')
    parser.add_argument('--force', action='store_true', help='Forçar execução independente do dia')
    parser.add_argument('--project', type=str, help='ID do projeto específico para executar')
    parser.add_argument('--channel', type=str, help='ID do canal Discord para identificar o projeto')
    parser.add_argument('--check-only', action='store_true', help='Apenas verificar configurações sem executar')
    parser.add_argument('--quiet', action='store_true', help='Modo silencioso - apenas notificações finais')
    parser.add_argument('--no-notifications', action='store_true', help='Não enviar notificações para o Discord')
    parser.add_argument('--no-admin-notification', action='store_true', help='Não enviar notificação de resumo para o administrador')
    parser.add_argument('--hide-dashboard', action='store_true', help='Não exibir o botão do Dashboard de Indicadores no relatório')
    args = parser.parse_args()
    
    try:
        # Inicializar o sistema
        system = WeeklyReportSystem()
    
        # Configurar modo silencioso se solicitado
        if args.quiet:
            system.quiet_mode = True
        else:
            system.quiet_mode = False
            
        # Desativar notificações Discord se solicitado
        if args.no_notifications:
            system.disable_notifications = True
        
        # Verificar se o discord foi inicializado
        if not hasattr(system, 'discord') or not system.discord:
            logger.error("O gerenciador de Discord não foi inicializado corretamente!")
        else:
            # Verificar se o token está configurado
            token_status = "configurado" if hasattr(system.discord, 'discord_token') and system.discord.discord_token else "NÃO configurado"
            logger.info(f"Token do Discord: {token_status}")
        
        # Verificar coluna de Discord
        try:
            logger.info("Verificando informações do Discord na planilha...")
            
            # Carregar a planilha
            project_df = system._load_project_config()
            
            if project_df is None or project_df.empty:
                logger.error("Planilha de configuração vazia!")
            else:
                # Verificar se a coluna existe
                if 'discord_id' in project_df.columns:
                    logger.info("✅ Coluna discord_id encontrada na planilha")
                    
                    # Contar quantos projetos têm valor nessa coluna
                    projetos_com_canal = project_df['discord_id'].notna().sum()
                    total_projetos = len(project_df)
                    
                    logger.info(f"Projetos com canal Discord: {projetos_com_canal}/{total_projetos}")
                    
                    # Verificar projetos ativos
                    if 'relatoriosemanal_status' in project_df.columns:
                        projetos_ativos = project_df[project_df['relatoriosemanal_status'].str.lower() == 'sim']
                        projetos_ativos_com_canal = projetos_ativos['discord_id'].notna().sum()
                        total_ativos = len(projetos_ativos)
                        
                        logger.info(f"Projetos ATIVOS com canal Discord: {projetos_ativos_com_canal}/{total_ativos}")
                else:
                    logger.error("❌ Coluna discord_id NÃO encontrada na planilha!")
                    logger.info(f"Colunas disponíveis: {', '.join(project_df.columns)}")
        except Exception as e:
            logger.error(f"Erro ao verificar colunas: {e}")
            
        # Se for apenas verificação, não executar o sistema
        if args.check_only:
            logger.info("Verificação de configurações concluída")
            return
        
        # Determinar o projeto a ser executado
        project_id = None
        
        # Se recebeu um canal, buscar o projeto correspondente
        if args.channel:
            logger.info(f"Buscando projeto associado ao canal Discord {args.channel}")
            project_id = system.get_project_by_discord_channel(args.channel)
            if not project_id:
                logger.error(f"Não foi possível encontrar projeto para o canal {args.channel}")
                return 1
            logger.info(f"Encontrado projeto {project_id} para o canal {args.channel}")
        elif args.project:
            project_id = args.project
        
        # Executar o sistema
        if project_id:
            logger.info(f"Executando apenas para o projeto {project_id} (sem-dashboard={args.hide_dashboard})")
            result = system.run_for_project(project_id, quiet_mode=True, skip_notifications=args.no_notifications, hide_dashboard=args.hide_dashboard) 
            status = "Sucesso" if result[0] else "Falha"
            mensagem = "Relatório gerado com sucesso" if result[0] else (result[3] if len(result) > 3 and result[3] else "Falha ao gerar relatório")
            doc_url = f"https://docs.google.com/document/d/{result[2]}/edit" if result[2] else None
            # Buscar nome do projeto e Código Projeto
            project_name = "Projeto desconhecido"
            codigo_projeto = project_id
            try:
                project_df = system._load_project_config()
                if 'construflow_id' in project_df.columns and 'Projeto - PR' in project_df.columns and 'Código Projeto' in project_df.columns:
                    project_row = project_df[project_df['construflow_id'].astype(str) == str(project_id)]
                    if not project_row.empty:
                        project_name = project_row['Projeto - PR'].iloc[0]
                        codigo_projeto = project_row['Código Projeto'].iloc[0]
            except Exception:
                pass
            # Chamada explícita do log na planilha
            system.log_execution_to_sheet(
                project_id=codigo_projeto,
                project_name=project_name,
                status=status,
                message=mensagem,
                doc_url=doc_url
            )
            status_str = "✅ Sucesso" if result[0] else "❌ Falha"
            drive_file_id = result[2]
            logger.info(f"Projeto {project_id}: {status_str}")
            if result[0]:
                logger.info(f"  - Arquivo local: {result[1]}")
                if drive_file_id:
                    # Se já for um link completo, usar diretamente; senão construir o link
                    if drive_file_id.startswith('http'):
                        doc_url = drive_file_id
                    else:
                        # Construir link do Google Drive
                        doc_url = f"https://drive.google.com/file/d/{drive_file_id}/view"
                    logger.info(f"  - Link do relatório: {doc_url}")
                    print(doc_url)
            # Enviar mensagem para o canal de notificação se solicitado
            if not args.no_admin_notification and hasattr(system, 'discord') and system.discord:
                if result[0]:
                    message = f"✅ Projeto {project_name} gerado com sucesso!"
                else:
                    message = f"❌ Projeto {project_name} falhou: {mensagem}"
                
                # Tentar enviar para o canal de notificação primeiro
                notification_channel_id = system.config.get_discord_notification_channel_id()
                if notification_channel_id:
                    system.discord.send_notification(notification_channel_id, message)
                else:
                    # Fallback para o canal admin
                    system.discord.send_admin_notification(message)
        else:
            results = system.run_scheduled(force=args.force, quiet_mode=True, skip_notifications=args.no_notifications, notification_delay=2)
            for project_id, (success, file_path, drive_id, *rest) in results.items():
                status = "✅ Sucesso" if success else "❌ Falha"
                logger.info(f"Projeto {project_id}: {status}")
                project_name = "Projeto desconhecido"
                motivo_falha = rest[0] if not success and len(rest) > 0 and rest[0] else "Falha ao gerar relatório"
                try:
                    project_df = system._load_project_config()
                    if 'construflow_id' in project_df.columns and 'Projeto - PR' in project_df.columns:
                        project_row = project_df[project_df['construflow_id'].astype(str) == str(project_id)]
                        if not project_row.empty:
                            project_name = project_row['Projeto - PR'].iloc[0]
                except Exception:
                    pass
                if not args.no_admin_notification and hasattr(system, 'discord') and system.discord:
                    if success:
                        msg = f"✅ Projeto {project_name} gerado com sucesso!"
                    else:
                        msg = f"❌ Projeto {project_name} falhou: {motivo_falha}"
                    
                    # Tentar enviar para o canal de notificação primeiro
                    notification_channel_id = system.config.get_discord_notification_channel_id()
                    if notification_channel_id:
                        system.discord.send_notification(notification_channel_id, msg)
                    else:
                        # Fallback para o canal admin
                        system.discord.send_admin_notification(msg)
        logger.info("=== Fim do processamento ===")
    except Exception as e:
        logger.error(f"Erro não tratado: {e}", exc_info=True)
        try:
            if not args.no_admin_notification and 'system' in locals() and hasattr(system, 'discord') and system.discord:
                error_message = f"### ❌ ERRO NA EXECUÇÃO DO SISTEMA\n\n"
                error_message += f"**Erro:** {str(e)}\n\n"
                error_message += "Verifique os logs para mais detalhes."
                
                # Tentar enviar para o canal de notificação primeiro
                notification_channel_id = system.config.get_discord_notification_channel_id()
                if notification_channel_id:
                    system.discord.send_notification(notification_channel_id, error_message)
                else:
                    # Fallback para o canal admin
                    system.discord.send_admin_notification(error_message)
        except Exception as notify_error:
            logger.error(f"Falha ao enviar notificação de erro: {notify_error}")
        return 1
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Execução interrompida pelo usuário")
        sys.exit(130)  # 130 é o código padrão para interrupção por SIGINT
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
        sys.exit(1)