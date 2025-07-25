#!/usr/bin/env python3
"""
Script para enviar mensagens diretas aos coordenadores com relatórios pendentes.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SendCoordinatorNotifications")

def send_coordinator_notifications():
    """Envia mensagens diretas aos coordenadores."""
    
    print("📨 ENVIANDO MENSAGENS AOS COORDENADORES")
    print("=" * 60)
    
    try:
        from report_system.config import ConfigManager
        from report_system.weekly_report_control import WeeklyReportController
        
        # Inicializar configuração
        config = ConfigManager()
        
        # Inicializar controlador
        controller = WeeklyReportController(config)
        
        # Verificar status dos relatórios
        print("\n📊 Verificando status dos relatórios...")
        status_list = controller.get_weekly_report_status()
        
        missing_reports = controller.get_missing_reports_by_coordinator()
        
        if not missing_reports:
            print("✅ Todos os relatórios foram gerados!")
            return True
        
        print(f"⚠️ {len(missing_reports)} coordenadores com relatórios pendentes")
        
        # Enviar notificações diretas
        print(f"\n🚀 Enviando mensagens diretas aos coordenadores...")
        success = controller.send_direct_notifications_to_coordinators()
        
        if success:
            print("✅ Mensagens enviadas com sucesso!")
        else:
            print("❌ Falha ao enviar algumas mensagens")
        
        return success
        
    except Exception as e:
        logger.error(f"Erro ao enviar mensagens: {e}")
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    send_coordinator_notifications() 