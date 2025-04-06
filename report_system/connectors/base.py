"""
Classe base para conectores de API.
"""

import time
import requests
import logging
from report_system.config import ConfigManager

logger = logging.getLogger("ReportSystem")

class APIConnector:
    """Classe base para conexões com APIs."""
    
    def __init__(self, config: ConfigManager):
        """
        Inicializa o conector de API.
        
        Args:
            config: Instância do ConfigManager
        """
        self.config = config
        self.session = config.get_http_session()
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Faz uma requisição HTTP com retry automático.
        
        Args:
            method: Método HTTP (GET, POST, etc.)
            url: URL da requisição
            **kwargs: Argumentos adicionais para requests
            
        Returns:
            Objeto Response
        """
        start_time = time.time()
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição {method} {url}: {e}")
            raise
        finally:
            logger.debug(f"Requisição {method} {url} levou {time.time() - start_time:.2f}s")
