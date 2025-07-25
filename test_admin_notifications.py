#!/usr/bin/env python3
"""
Script para testar as mensagens de controle no canal ADM.
"""

import os
import sys
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

def test_admin_channel_config():
    """Testa se o canal ADM está configurado."""
    
    print("🧪 Testando configuração do canal ADM...")
    
    try:
        from report_system.config import ConfigManager
        
        # Inicializar configuração
        config = ConfigManager()
        
        # Obter o canal ADM configurado
        admin_channel_id = config.get_discord_admin_channel_id()
        
        print(f"📋 Canal ADM configurado: {admin_channel_id}")
        
        if admin_channel_id:
            print("✅ Canal ADM encontrado no .env")
            return admin_channel_id
        else:
            print("❌ Canal ADM não configurado no .env")
            print("   Verifique se a variável DISCORD_ADMIN_CHANNEL_ID está definida")
            return None
            
    except Exception as e:
        print(f"❌ Erro ao testar configuração: {e}")
        return None

def test_notification_channels():
    """Testa se os canais de notificação estão configurados."""
    
    print("\n🧪 Testando configuração dos canais de notificação...")
    
    try:
        from report_system.config import ConfigManager
        
        # Inicializar configuração
        config = ConfigManager()
        
        # Obter os canais configurados
        notification_channel_id = config.get_discord_notification_channel_id()
        admin_channel_id = config.get_discord_admin_channel_id()
        
        print(f"📋 Canal de notificação: {notification_channel_id}")
        print(f"📋 Canal ADM: {admin_channel_id}")
        
        if notification_channel_id and admin_channel_id:
            print("✅ Ambos os canais estão configurados")
            return True
        else:
            print("❌ Um ou ambos os canais não estão configurados")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar configuração: {e}")
        return False

def test_admin_message_sending():
    """Testa o envio de mensagens para o canal ADM."""
    
    print("\n🧪 Testando envio de mensagens para o canal ADM...")
    
    try:
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
        
        # Obter o canal ADM
        admin_channel_id = bot.report_system.config.get_discord_admin_channel_id()
        
        if not admin_channel_id:
            print("❌ Canal ADM não configurado")
            return False
        
        # Testar envio de mensagem de controle
        print("🔍 Enviando mensagem de teste para o canal ADM...")
        
        test_message = f"🧪 **TESTE DE MENSAGEM DE CONTROLE**\n\n"
        test_message += f"**Projeto:** {test_project_name}\n"
        test_message += f"**Canal de origem:** <#{test_channel_id}>\n"
        test_message += f"**Canal ADM:** <#{admin_channel_id}>\n"
        test_message += f"**Status:** Teste de funcionalidade"
        
        success = bot.send_message(admin_channel_id, test_message)
        
        if success:
            print("✅ Mensagem de teste enviada com sucesso para o canal ADM!")
            return True
        else:
            print("❌ Falha ao enviar mensagem de teste")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar envio de mensagens: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal."""
    print("🚀 Testando mensagens de controle no canal ADM")
    print("=" * 50)
    
    # Testar configuração do canal ADM
    admin_channel = test_admin_channel_config()
    
    if not admin_channel:
        print("\n❌ Canal ADM não configurado. Verifique o arquivo .env")
        return 1
    
    # Testar configuração dos canais
    channels_ok = test_notification_channels()
    
    if not channels_ok:
        print("\n❌ Configuração de canais incompleta")
        return 1
    
    # Testar envio de mensagens
    success = test_admin_message_sending()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Testes de mensagens de controle passaram!")
        print("✅ O sistema está configurado para enviar mensagens de controle no canal ADM")
        print("\n📋 Resumo do que foi implementado:")
        print("   • Mensagem de início quando o comando é executado")
        print("   • Mensagem de sucesso quando a notificação é enviada")
        print("   • Mensagem de erro se algo der errado")
        print("   • Informações detalhadas sobre projeto, canais e status")
    else:
        print("⚠️ Alguns testes falharam")
        print("❌ Verifique os logs para mais detalhes")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 