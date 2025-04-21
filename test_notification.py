import os
import sys
from dotenv import load_dotenv

# Adicione o caminho do diretório atual ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Adicione o caminho do report_system ao PYTHONPATH 
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Importe depois de configurar o path
from report_system.discord_notification import DiscordNotificationManager
from report_system.config import ConfigManager

def main():
    """Teste de envio de notificação para o canal configurado."""
    # Carregar variáveis de ambiente
    load_dotenv()
    
    print("Iniciando teste de notificação Discord...")
    
    # Criar o gerenciador de configuração
    config = ConfigManager()
    
    # Criar o gerenciador de notificações do Discord
    discord = DiscordNotificationManager(config)
    
    # Obter o ID do canal de administração
    admin_channel_id = os.getenv("DISCORD_ADMIN_CHANNEL_ID", "")
    
    if not admin_channel_id:
        print("⚠️ Erro: ID do canal de administração não configurado!")
        return 1
    
    print(f"Enviando notificação para o canal {admin_channel_id}...")
    
    # Enviar mensagem de teste
    message = "### 🧪 Teste de Notificação\n\nEste é um teste do sistema de notificação. Se você está vendo esta mensagem, o sistema está funcionando corretamente! 👍"
    
    success = discord.send_notification(
        channel_id=admin_channel_id,
        message=message
    )
    
    if success:
        print("✅ Notificação enviada com sucesso!")
    else:
        print("❌ Falha ao enviar notificação!")
    
    # Tentar através do método send_admin_notification
    print("Testando método send_admin_notification...")
    
    admin_message = "### 🧪 Teste de Notificação (Admin)\n\nEste é um teste do método send_admin_notification. Se você está vendo esta mensagem, o sistema está pronto para enviar resumos de execução! 👍"
    
    admin_success = discord.send_admin_notification(admin_message)
    
    if admin_success:
        print("✅ Notificação admin enviada com sucesso!")
    else:
        print("❌ Falha ao enviar notificação admin!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 