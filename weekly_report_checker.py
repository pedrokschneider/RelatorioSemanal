#!/usr/bin/env python3
"""
Script para verificar e notificar relatórios semanais em falta.
Pode ser executado manualmente ou agendado.
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/weekly_check_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("WeeklyReportChecker")

def check_weekly_reports(notification_channel: str = None, admin_channel: str = None, send_direct: bool = False):
    """
    Verifica relatórios semanais e envia notificações.
    
    Args:
        notification_channel: ID do canal para enviar notificação geral
        admin_channel: ID do canal admin para logs
        send_direct: Se deve enviar notificações diretas aos coordenadores
    """
    try:
        from report_system.main import WeeklyReportSystem
        
        logger.info("🔍 Iniciando verificação de relatórios semanais")
        
        # Inicializar sistema
        system = WeeklyReportSystem(verbose_init=False)
        
        # Verificar status dos relatórios
        status = system.check_weekly_reports_status()
        
        if "error" in status:
            logger.error(f"Erro ao verificar relatórios: {status['error']}")
            return False
        
        logger.info(f"📊 Status dos relatórios da semana {status['week_text']}:")
        logger.info(f"  Total de projetos: {status['total_projects']}")
        logger.info(f"  Devem gerar: {status['should_generate']}")
        logger.info(f"  Já gerados: {status['was_generated']}")
        logger.info(f"  Em falta: {status['missing_reports']}")
        
        # Se não há relatórios em falta, não precisa notificar
        if status['missing_reports'] == 0:
            logger.info("✅ Todos os relatórios foram gerados!")
            return True
        
        # Enviar notificação para canal específico se fornecido
        if notification_channel:
            logger.info(f"📤 Enviando notificação para canal {notification_channel}")
            success = system.send_weekly_reports_notification(notification_channel)
            if success:
                logger.info("✅ Notificação enviada com sucesso!")
            else:
                logger.error("❌ Falha ao enviar notificação")
        
        # Enviar notificações diretas se solicitado
        if send_direct:
            logger.info("📤 Enviando notificações diretas aos coordenadores")
            success = system.send_direct_notifications_to_coordinators(admin_channel)
            if success:
                logger.info("✅ Notificações diretas enviadas com sucesso!")
            else:
                logger.error("❌ Falha ao enviar notificações diretas")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro durante verificação de relatórios: {e}", exc_info=True)
        return False

def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Verificador de relatórios semanais")
    parser.add_argument("--notification-channel", help="ID do canal para notificação geral")
    parser.add_argument("--admin-channel", help="ID do canal admin para logs")
    parser.add_argument("--send-direct", action="store_true", help="Enviar notificações diretas aos coordenadores")
    parser.add_argument("--test", action="store_true", help="Modo teste - apenas verificar status")
    
    args = parser.parse_args()
    
    # Criar diretório de logs se não existir
    os.makedirs("logs", exist_ok=True)
    
    logger.info("🚀 Iniciando verificador de relatórios semanais")
    
    if args.test:
        # Modo teste - apenas verificar status
        logger.info("🧪 Modo teste ativado")
        try:
            from report_system.main import WeeklyReportSystem
            system = WeeklyReportSystem(verbose_init=False)
            status = system.check_weekly_reports_status()
            
            print(f"\n📊 STATUS DOS RELATÓRIOS - {status['week_text']}")
            print(f"📋 Total de projetos: {status['total_projects']}")
            print(f"✅ Devem gerar: {status['should_generate']}")
            print(f"📝 Já gerados: {status['was_generated']}")
            print(f"⚠️ Em falta: {status['missing_reports']}")
            
            if status['missing_reports'] > 0:
                print(f"\n👥 Coordenadores com relatórios pendentes:")
                for coordinator, projects in status['missing_by_coordinator'].items():
                    print(f"  • {coordinator}: {len(projects)} projetos")
            
            return 0
            
        except Exception as e:
            logger.error(f"Erro no modo teste: {e}")
            return 1
    
    # Executar verificação
    success = check_weekly_reports(
        notification_channel=args.notification_channel,
        admin_channel=args.admin_channel,
        send_direct=args.send_direct
    )
    
    if success:
        logger.info("✅ Verificação concluída com sucesso")
        return 0
    else:
        logger.error("❌ Falha na verificação")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 