#!/usr/bin/env python3
"""
Script para testar especificamente as notificações do canal admin.
"""

import os
import sys
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

def test_admin_notifications():
    """Testa as notificações do canal admin."""
    
    print("🧪 TESTANDO NOTIFICAÇÕES DO CANAL ADMIN")
    print("=" * 50)
    
    try:
        from discord_bot import DiscordBotAutoChannels
        
        # Inicializar o bot
        bot = DiscordBotAutoChannels()
        
        # Obter o ID do canal admin
        admin_channel_id = bot.report_system.config.get_discord_admin_channel_id()
        print(f"📋 Canal Admin ID: {admin_channel_id}")
        
        if not admin_channel_id:
            print("❌ Canal admin não configurado no .env")
            return
        
        # Verificar se o canal admin está na lista de canais ativos
        channels = bot.get_channels_from_spreadsheet()
        admin_channel_clean = ''.join(c for c in admin_channel_id if c.isdigit())
        
        if admin_channel_clean in channels:
            print(f"✅ Canal admin encontrado na lista de canais ativos")
            print(f"   Nome: {channels[admin_channel_clean]['project_name']}")
        else:
            print(f"❌ Canal admin NÃO encontrado na lista de canais ativos")
            print(f"   Procurado: {admin_channel_clean}")
            print(f"   Canais disponíveis: {list(channels.keys())[:5]}...")
        
        # Testar validação do canal admin
        print(f"\n🔍 Validando canal admin: {admin_channel_clean}")
        validation = bot.validate_channel_for_reports(admin_channel_clean)
        
        if validation['valid']:
            print(f"✅ Canal admin é válido para relatórios")
        else:
            print(f"❌ Canal admin não é válido: {validation['reason']}")
            print(f"   Mensagem: {validation['message'][:100]}...")
        
        # Testar comando !notificar
        print(f"\n🔍 Testando comando !notificar no canal admin")
        try:
            bot.process_command(admin_channel_clean, "!notificar")
            print("✅ Comando !notificar executado com sucesso")
        except Exception as e:
            print(f"❌ Erro ao executar !notificar: {e}")
        
        # Testar comando !controle
        print(f"\n🔍 Testando comando !controle no canal admin")
        try:
            bot.process_command(admin_channel_clean, "!controle")
            print("✅ Comando !controle executado com sucesso")
        except Exception as e:
            print(f"❌ Erro ao executar !controle: {e}")
        
        # Verificar se o bot consegue enviar mensagens para o canal admin
        print(f"\n🔍 Testando envio de mensagem para o canal admin")
        try:
            result = bot.send_message(admin_channel_clean, "🧪 Teste de conectividade - Bot funcionando!")
            if result:
                print("✅ Mensagem enviada com sucesso para o canal admin")
            else:
                print("❌ Falha ao enviar mensagem para o canal admin")
        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")
        
        print("\n✅ Testes concluídos!")
        
    except Exception as e:
        print(f"❌ Erro durante os testes: {e}")
        import traceback
        traceback.print_exc()

def test_specific_channel_notifications(channel_id):
    """Testa notificações em um canal específico."""
    
    print(f"🧪 TESTANDO NOTIFICAÇÕES NO CANAL: {channel_id}")
    print("=" * 50)
    
    try:
        from discord_bot import DiscordBotAutoChannels
        
        # Inicializar o bot
        bot = DiscordBotAutoChannels()
        
        # Verificar se o canal está na lista
        channels = bot.get_channels_from_spreadsheet()
        
        if channel_id in channels:
            print(f"✅ Canal encontrado na lista de canais ativos")
            print(f"   Nome: {channels[channel_id]['project_name']}")
        else:
            print(f"❌ Canal NÃO encontrado na lista de canais ativos")
            return
        
        # Testar validação
        validation = bot.validate_channel_for_reports(channel_id)
        
        if validation['valid']:
            print(f"✅ Canal é válido para relatórios")
        else:
            print(f"❌ Canal não é válido: {validation['reason']}")
            print(f"   Mensagem: {validation['message']}")
            return
        
        # Testar comando !relatorio
        print(f"\n🔍 Testando comando !relatorio")
        try:
            bot.process_command(channel_id, "!relatorio")
            print("✅ Comando !relatorio executado com sucesso")
        except Exception as e:
            print(f"❌ Erro ao executar !relatorio: {e}")
        
        # Testar envio de mensagem
        print(f"\n🔍 Testando envio de mensagem")
        try:
            result = bot.send_message(channel_id, "🧪 Teste de conectividade - Bot funcionando!")
            if result:
                print("✅ Mensagem enviada com sucesso")
            else:
                print("❌ Falha ao enviar mensagem")
        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")
        
        print("\n✅ Testes concluídos!")
        
    except Exception as e:
        print(f"❌ Erro durante os testes: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Função principal."""
    if len(sys.argv) == 1:
        # Teste do canal admin
        test_admin_notifications()
    elif len(sys.argv) == 2:
        # Teste de canal específico
        channel_id = sys.argv[1]
        test_specific_channel_notifications(channel_id)
    else:
        print("Uso:")
        print("  python test_admin_notifications.py                    # Teste do canal admin")
        print("  python test_admin_notifications.py <canal_id>        # Teste de canal específico")
        print("Exemplo:")
        print("  python test_admin_notifications.py 1383090628379934851")

if __name__ == "__main__":
    main() 