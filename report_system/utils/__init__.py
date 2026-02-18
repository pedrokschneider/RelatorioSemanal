"""
Pacote de utilitários para o sistema.
"""

from .logging_config import setup_logging, get_logger


def extract_discord_channel_id(discord_id: str) -> str:
    """
    Extrai o ID do canal Discord de uma URL ou ID raw.

    Suporta formatos:
    - URL: https://discordapp.com/channels/SERVER_ID/CHANNEL_ID → CHANNEL_ID
    - URL: https://discord.com/channels/SERVER_ID/CHANNEL_ID → CHANNEL_ID
    - Raw: 1310674177665007668 → 1310674177665007668

    Args:
        discord_id: ID do canal ou URL do Discord

    Returns:
        ID numérico do canal (apenas dígitos)
    """
    if not discord_id:
        return ""

    discord_id = str(discord_id).strip()

    # Se contém barra, é uma URL - extrair o último segmento numérico
    if '/' in discord_id:
        parts = discord_id.rstrip('/').split('/')
        for part in reversed(parts):
            cleaned = ''.join(c for c in part if c.isdigit())
            if cleaned:
                return cleaned

    # Raw number - extrair apenas dígitos
    return ''.join(c for c in discord_id if c.isdigit())


__all__ = ['setup_logging', 'get_logger', 'extract_discord_channel_id']
