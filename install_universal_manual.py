#!/usr/bin/env python3
"""
Script de instalação manual para o serviço universal.
"""

import os
import sys
import subprocess
import win32serviceutil
import win32service
import win32event
import servicemanager
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ManualInstaller")

class DiscordBotUniversalService(win32serviceutil.ServiceFramework):
    _svc_name_ = "DiscordReportBotUniversal"
    _svc_display_name_ = "Discord Report Bot Universal"
    _svc_description_ = "Bot Discord Universal para Relatórios Semanais"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.is_alive = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.is_alive = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        # Obter o caminho completo do script principal
        main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discord_bot_universal.pyw")
        
        logger.info(f"Executando script: {main_script}")
        
        while self.is_alive:
            try:
                # Executar o script principal
                process = subprocess.Popen([sys.executable, main_script])
                process.wait()  # Aguarda o processo terminar
                
                # Se o processo terminou, espera um pouco antes de reiniciar
                import time
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Erro durante execução do serviço: {e}")
                import time
                time.sleep(60)

def install_service():
    """Instala o serviço manualmente."""
    try:
        print("🔧 INSTALANDO SERVIÇO UNIVERSAL MANUALMENTE")
        print("=" * 50)
        
        # Verificar se o arquivo existe
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discord_bot_universal.pyw")
        if not os.path.exists(script_path):
            print(f"❌ Arquivo não encontrado: {script_path}")
            return False
        
        print(f"✅ Arquivo encontrado: {script_path}")
        
        # Instalar o serviço
        win32serviceutil.InstallService(
            DiscordBotUniversalService._svc_name_,
            DiscordBotUniversalService._svc_display_name_,
            DiscordBotUniversalService._svc_description_,
            startType=win32service.SERVICE_AUTO_START
        )
        print("✅ Serviço instalado com sucesso!")
        
        # Tentar iniciar o serviço
        try:
            win32serviceutil.StartService(DiscordBotUniversalService._svc_name_)
            print("✅ Serviço iniciado com sucesso!")
        except Exception as e:
            print(f"⚠️  Serviço instalado mas não foi possível iniciar automaticamente: {e}")
            print("   Você pode iniciar manualmente com: sc start DiscordReportBotUniversal")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao instalar serviço: {e}")
        return False

def uninstall_service():
    """Desinstala o serviço."""
    try:
        print("🗑️  DESINSTALANDO SERVIÇO")
        print("=" * 50)
        
        # Parar o serviço se estiver rodando
        try:
            win32serviceutil.StopService(DiscordBotUniversalService._svc_name_)
            print("✅ Serviço parado")
        except:
            pass
        
        # Remover o serviço
        win32serviceutil.RemoveService(DiscordBotUniversalService._svc_name_)
        print("✅ Serviço desinstalado com sucesso!")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao desinstalar serviço: {e}")
        return False

def check_service():
    """Verifica o status do serviço."""
    try:
        print("🔍 VERIFICANDO STATUS DO SERVIÇO")
        print("=" * 50)
        
        status = win32serviceutil.QueryServiceStatus(DiscordBotUniversalService._svc_name_)
        print(f"✅ Serviço encontrado")
        print(f"   Status: {status[1]}")
        print(f"   Nome: {DiscordBotUniversalService._svc_name_}")
        
        return True
        
    except Exception as e:
        print(f"❌ Serviço não encontrado: {e}")
        return False

def main():
    """Função principal."""
    if len(sys.argv) == 1:
        print("🤖 INSTALADOR MANUAL DO BOT UNIVERSAL")
        print("=" * 50)
        print()
        print("Opções:")
        print("1. Instalar serviço")
        print("2. Desinstalar serviço")
        print("3. Verificar status")
        print("4. Executar como serviço")
        print()
        
        choice = input("Escolha uma opção (1-4): ").strip()
        
        if choice == "1":
            install_service()
        elif choice == "2":
            uninstall_service()
        elif choice == "3":
            check_service()
        elif choice == "4":
            win32serviceutil.HandleCommandLine(DiscordBotUniversalService)
        else:
            print("❌ Opção inválida")
    else:
        # Execução como serviço
        win32serviceutil.HandleCommandLine(DiscordBotUniversalService)

if __name__ == "__main__":
    main() 