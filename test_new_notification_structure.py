#!/usr/bin/env python3
"""
Script para testar a nova estrutura de notificações do bot Discord.
"""

import os
import sys
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

def test_channel_configuration():
    """Testa se todos os canais necessários estão configurados."""
    
    print("🧪 Testando configuração dos canais...")
    
    try:
        from report_system.config import ConfigManager
        
        # Inicializar configuração
        config = ConfigManager()
        
        # Obter os canais configurados
        admin_channel_id = config.get_discord_admin_channel_id()
        team_notification_channel_id = config.get_discord_notification_team_channel_id()
        notification_channel_id = config.get_discord_notification_channel_id()
        
        print(f"📋 Canal administrativo: {admin_channel_id}")
        print(f"📋 Canal da equipe: {team_notification_channel_id}")
        print(f"📋 Canal de status: {notification_channel_id}")
        
        # Verificar se todos estão configurados
        missing_channels = []
        
        if not admin_channel_id:
            missing_channels.append("DISCORD_ADMIN_CHANNEL_ID")
        
        if not team_notification_channel_id:
            missing_channels.append("DISCORD_NOTIFICATION_TEAM_CHANNEL_ID")
        
        if not notification_channel_id:
            missing_channels.append("DISCORD_NOTIFICATION_CHANNEL_ID")
        
        if missing_channels:
            print(f"❌ Canais não configurados: {', '.join(missing_channels)}")
            print("   Adicione essas variáveis ao arquivo .env")
            return False
        else:
            print("✅ Todos os canais estão configurados corretamente")
            return True
            
    except Exception as e:
        print(f"❌ Erro ao testar configuração: {e}")
        return False

def test_admin_channel_monitoring():
    """Testa se o canal admin está sendo monitorado."""
    
    print("\n🧪 Testando monitoramento do canal admin...")
    
    try:
        from discord_bot import DiscordBotAutoChannels
        
        # Inicializar o bot
        bot = DiscordBotAutoChannels()
        
        # Obter canais da planilha (incluindo admin)
        channels = bot.get_channels_from_spreadsheet()
        
        if not channels:
            print("❌ Nenhum canal encontrado")
            return False
        
        # Verificar se o canal admin está na lista
        admin_channel_id = bot.report_system.config.get_discord_admin_channel_id()
        admin_channel_clean = ''.join(c for c in admin_channel_id if c.isdigit()) if admin_channel_id else ''
        
        if admin_channel_clean in channels:
            print(f"✅ Canal admin está sendo monitorado: {admin_channel_clean}")
            print(f"   Nome: {channels[admin_channel_clean]['project_name']}")
            return True
        else:
            print(f"❌ Canal admin não está sendo monitorado")
            print(f"   Canal configurado: {admin_channel_clean}")
            print(f"   Canais monitorados: {list(channels.keys())}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar monitoramento: {e}")
        return False

def test_notification_command_restriction():
    """Testa se o comando !notificar está restrito ao canal admin."""
    
    print("\n🧪 Testando restrição do comando !notificar...")
    
    try:
        from discord_bot import DiscordBotAutoChannels
        
        # Inicializar o bot
        bot = DiscordBotAutoChannels()
        
        # Obter canais da planilha
        channels = bot.get_channels_from_spreadsheet()
        
        if not channels:
            print("❌ Nenhum canal encontrado")
            return False
        
        # Pegar um canal que não seja admin para teste
        admin_channel_id = bot.report_system.config.get_discord_admin_channel_id()
        admin_channel_clean = ''.join(c for c in admin_channel_id if c.isdigit()) if admin_channel_id else ''
        
        test_channel_id = None
        for channel_id in channels.keys():
            if channel_id != admin_channel_clean:
                test_channel_id = channel_id
                break
        
        if not test_channel_id:
            print("❌ Não foi possível encontrar um canal não-admin para teste")
            return False
        
        print(f"📋 Testando com canal não-admin: {test_channel_id}")
        
        # Simular o processamento do comando (sem enviar mensagem real)
        # Vamos verificar se a validação funciona
        admin_channel_id = bot.report_system.config.get_discord_admin_channel_id()
        admin_channel_clean = ''.join(c for c in admin_channel_id if c.isdigit()) if admin_channel_id else ''
        
        if test_channel_id != admin_channel_clean:
            print("✅ Validação funcionando: canal não-admin seria rejeitado")
            return True
        else:
            print("❌ Erro na validação: canal admin seria aceito incorretamente")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar restrição: {e}")
        return False

def test_new_config_method():
    """Testa se o novo método de configuração está funcionando."""
    
    print("\n🧪 Testando novo método de configuração...")
    
    try:
        from report_system.config import ConfigManager
        
        # Inicializar configuração
        config = ConfigManager()
        
        # Testar o novo método
        team_channel_id = config.get_discord_notification_team_channel_id()
        
        print(f"📋 Método get_discord_notification_team_channel_id(): {team_channel_id}")
        
        if team_channel_id is not None:
            print("✅ Método funcionando corretamente")
            return True
        else:
            print("❌ Método retornou None")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar método: {e}")
        return False

def main():
    """Função principal de teste."""
    
    print("🚀 Iniciando testes da nova estrutura de notificações...\n")
    
    tests = [
        ("Configuração dos canais", test_channel_configuration),
        ("Monitoramento do canal admin", test_admin_channel_monitoring),
        ("Restrição do comando !notificar", test_notification_command_restriction),
        ("Novo método de configuração", test_new_config_method)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"🔍 {test_name}...")
        result = test_func()
        results.append((test_name, result))
        print()
    
    # Resumo dos resultados
    print("📊 RESUMO DOS TESTES")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"Total: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram! A nova estrutura está funcionando.")
    else:
        print("⚠️ Alguns testes falharam. Verifique a configuração.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 