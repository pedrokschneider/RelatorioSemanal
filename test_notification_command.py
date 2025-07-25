#!/usr/bin/env python3
"""
Script para testar o comando !notification do bot Discord.
"""

import os
import sys
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

def test_notification_command():
    """Testa o comando !notification."""
    
    print("🧪 Testando comando !notification...")
    
    try:
        # Importar o bot (usar o arquivo .pyw que é o que está rodando)
        import sys
        import importlib.util
        
        # Carregar o arquivo .pyw diretamente
        spec = importlib.util.spec_from_file_location("discord_bot_pyw", "discord_bot.pyw")
        discord_bot_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(discord_bot_module)
        
        DiscordBotAutoChannels = discord_bot_module.DiscordBotAutoChannels
        
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
        
        # Testar o comando !notification
        print("🔍 Processando comando !notification...")
        success = bot.process_command(test_channel_id, "!notification")
        
        if success:
            print("✅ Comando !notification processado com sucesso!")
            return True
        else:
            print("❌ Falha ao processar comando !notification")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar comando: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_other_commands():
    """Testa outros comandos relacionados."""
    
    print("\n🧪 Testando outros comandos...")
    
    try:
        # Importar diretamente do arquivo .pyw
        import importlib.util
        
        # Carregar o arquivo .pyw diretamente
        spec = importlib.util.spec_from_file_location("discord_bot_pyw", "discord_bot.pyw")
        discord_bot_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(discord_bot_module)
        
        DiscordBotAutoChannels = discord_bot_module.DiscordBotAutoChannels
        
        bot = DiscordBotAutoChannels()
        channels = bot.get_channels_from_spreadsheet()
        
        if not channels:
            print("❌ Nenhum canal encontrado na planilha")
            return False
        
        test_channel_id = list(channels.keys())[0]
        
        # Testar comando !controle
        print("🔍 Testando comando !controle...")
        success_controle = bot.process_command(test_channel_id, "!controle")
        print(f"✅ Comando !controle: {'Sucesso' if success_controle else 'Falha'}")
        
        # Testar comando !notificar
        print("🔍 Testando comando !notificar...")
        success_notificar = bot.process_command(test_channel_id, "!notificar")
        print(f"✅ Comando !notificar: {'Sucesso' if success_notificar else 'Falha'}")
        
        # Testar comando !notificar_coordenadores
        print("🔍 Testando comando !notificar_coordenadores...")
        success_coord = bot.process_command(test_channel_id, "!notificar_coordenadores")
        print(f"✅ Comando !notificar_coordenadores: {'Sucesso' if success_coord else 'Falha'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao testar outros comandos: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal."""
    print("🚀 Iniciando testes do comando !notification")
    print("=" * 50)
    
    # Testar comando principal
    success1 = test_notification_command()
    
    # Testar outros comandos
    success2 = test_other_commands()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("🎉 Todos os testes passaram!")
        print("✅ O comando !notification está funcionando corretamente")
    else:
        print("⚠️ Alguns testes falharam")
        print("❌ Verifique os logs para mais detalhes")
    
    return 0 if (success1 and success2) else 1

if __name__ == "__main__":
    sys.exit(main()) 