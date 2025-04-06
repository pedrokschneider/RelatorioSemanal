"""
Módulo de configuração de logging corrigido.
"""

import logging
import os
import sys
from datetime import datetime

def setup_logging(log_level=logging.INFO, verbose_init=False):
    """
    Configura o sistema de logging com níveis específicos por módulo.
    
    Args:
        log_level: Nível de log padrão
        verbose_init: Se deve mostrar logs verbosos de inicialização
    
    Returns:
        Logger configurado
    """
    # Criar diretório de logs se não existir
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Gerar nome de arquivo baseado na data
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_filename = os.path.join(log_dir, f"report_system_{today_str}.log")
    
    # Formato básico para logs
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                 datefmt='%Y-%m-%d %H:%M:%S')
    
    # Handler para arquivo - usar UTF-8 explicitamente
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Configurar handler para console com UTF-8
    # Em Windows, a saída do console pode ter problemas com UTF-8
    if sys.platform == 'win32':
        # No Windows, precisamos configurar a codificação do console
        import codecs
        try:
            # Tentar configurar a saída para UTF-8
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except AttributeError:
            # Para versões mais antigas do Python que não têm reconfigure
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

    # Handler para console - tratar caracteres especiais
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(formatter)        
   
    # Configurar logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Limpar handlers existentes
    while root_logger.handlers:
        root_logger.removeHandler(root_logger.handlers[0])
    
    # Adicionar handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Ajustar níveis de log específicos para diferentes componentes
    if not verbose_init:
        # Reduzir verbosidade de módulos específicos durante inicialização
        logging.getLogger("report_system.config").setLevel(logging.WARNING)
        logging.getLogger("report_system.discord_notification").setLevel(logging.WARNING)
        logging.getLogger("report_system.storage.google_drive").setLevel(logging.WARNING)
        logging.getLogger("DiscordBot").setLevel(logging.INFO)  # Manter INFO para o bot principal
        logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)
    
    # Criar e retornar o logger principal
    logger = logging.getLogger("ReportSystem")
    logger.info(f"Logging configurado em {log_filename}")
    
    return logger

# Função de compatibilidade para código existente que ainda utiliza get_logger
def get_logger():
    """
    Função de compatibilidade que chama setup_logging para código existente.
    """
    return setup_logging()