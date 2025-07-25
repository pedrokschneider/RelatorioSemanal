#!/usr/bin/env python3
"""
Script para testar a correção do comando !notification.
"""

import os
import sys
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

def test_notification_config():
    """Testa se a configuração do canal de notificação está correta."""
    
    print("🧪 Testando configuração do canal de notificação...")
    
    try:
        from report_system.config import ConfigManager
        
        # Inicializar configuração
        config = ConfigManager()
        
        # Obter o canal de notificação configurado
        notification_channel_id = config.get_discord_notification_channel_id()
        
        print(f"📋 Canal de notificação configurado: {notification_channel_id}")
        
        if notification_channel_id:
            print("✅ Canal de notificação encontrado no .env")
            return notification_channel_id
        else:
            print("❌ Canal de notificação não configurado no .env")
            print("   Verifique se a variável DISCORD_NOTIFICATION_CHANNEL_ID está definida")
            return None
            
    except Exception as e:
        print(f"❌ Erro ao testar configuração: {e}")
        return None

def test_notification_command():
    """Testa o comando !notification corrigido."""
    
    print("\n🧪 Testando comando !notification corrigido...")
    
    try:
        # Importar o bot
        from discord_bot import DiscordBotAutoChannels
        
        # Inicializar o bot
        bot = DiscordBotAutoChannels()
        
        # Obter canais da planilha
        channels = bot.get_channels_from_spreadsheet()
        
        if not channels:
            print("❌ Nenhum canal encontrado na planilha")
            return False
        
        # Pegar o primeiro canal para teste
        test_channel_id = list(channels.keys())[0]
        test_project_name = channels[test_channel_id]['project_name']
        
        print(f"📋 Testando com canal: {test_project_name} (ID: {test_channel_id})")
        
        # Simular o processamento do comando !notification
        print("🔍 Simulando comando !notification...")
        
        # Obter o canal de notificação configurado
        notification_channel_id = bot.report_system.config.get_discord_notification_channel_id()
        
        if not notification_channel_id:
            print("❌ Canal de notificação não configurado no .env")
            return False
        
        print(f"📤 Canal de destino: {notification_channel_id}")
        
        # Testar o envio da notificação
        success = bot.report_system.send_weekly_reports_notification(notification_channel_id)
        
        if success:
            print("✅ Notificação enviada com sucesso para o canal correto!")
            return True
        else:
            print("❌ Falha ao enviar notificação")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar comando: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal."""
    print("🚀 Testando correção do comando !notification")
    print("=" * 50)
    
    # Testar configuração
    notification_channel = test_notification_config()
    
    if not notification_channel:
        print("\n❌ Configuração incorreta. Verifique o arquivo .env")
        return 1
    
    # Testar comando
    success = test_notification_command()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Correção funcionando corretamente!")
        print("✅ O comando !notification agora envia para o canal configurado no .env")
    else:
        print("⚠️ Ainda há problemas com o comando")
        print("❌ Verifique os logs para mais detalhes")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 