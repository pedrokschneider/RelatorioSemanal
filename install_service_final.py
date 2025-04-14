import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import os
import logging
import time
import subprocess

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ServiceInstaller")

class DiscordBotService(win32serviceutil.ServiceFramework):
    _svc_name_ = "DiscordReportBot"
    _svc_display_name_ = "Discord Report Bot"
    _svc_description_ = "Bot Discord para Relatórios Semanais"

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
        main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discord_bot.pyw")
        
        while self.is_alive:
            try:
                # Executar o script principal
                process = subprocess.Popen([sys.executable, main_script])
                process.wait()  # Aguarda o processo terminar
                
                # Se o processo terminou, espera um pouco antes de reiniciar
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Erro durante execução do serviço: {e}")
                time.sleep(60)

def install_service():
    try:
        # Instalar o serviço
        win32serviceutil.InstallService(
            DiscordBotService._svc_name_,
            DiscordBotService._svc_display_name_,
            DiscordBotService._svc_description_,
            startType=win32service.SERVICE_AUTO_START
        )
        logger.info("Serviço instalado com sucesso!")
        
        # Iniciar o serviço
        win32serviceutil.StartService(DiscordBotService._svc_name_)
        logger.info("Serviço iniciado com sucesso!")
        
        return True
    except Exception as e:
        logger.error(f"Erro ao instalar serviço: {e}")
        return False

if __name__ == '__main__':
    if install_service():
        print("Serviço instalado e iniciado com sucesso!")
    else:
        print("Falha ao instalar o serviço. Verifique os logs para mais detalhes.") 