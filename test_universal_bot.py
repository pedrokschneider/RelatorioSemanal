#!/usr/bin/env python3
"""
Script para testar o bot universal.
"""

import os
import sys
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

def test_universal_bot():
    """Testa o bot universal."""
    
    print("🧪 TESTANDO BOT UNIVERSAL")
    print("=" * 50)
    
    try:
        from discord_bot_universal import DiscordBotUniversal
        
        # Inicializar o bot
        print("🔧 Inicializando bot universal...")
        bot = DiscordBotUniversal()
        
        print("✅ Bot universal inicializado com sucesso!")
        
        # Verificar configurações
        print(f"\n📋 Configurações:")
        print(f"   Token configurado: {'✅' if bot.token else '❌'}")
        print(f"   Canais carregados: {len(bot.channels_info)}")
        print(f"   Sistema de relatórios: {'✅' if bot.report_system else '❌'}")
        print(f"   Sistema de filas: {'✅' if bot.queue_system else '❌'}")
        
        # Listar alguns canais
        print(f"\n📋 Canais configurados (primeiros 5):")
        for i, (channel_id, info) in enumerate(list(bot.channels_info.items())[:5]):
            print(f"   {i+1}. {info['project_name']} (ID: {channel_id})")
        
        # Testar validação de canais
        print(f"\n🔍 Testando validação de canais:")
        
        # Testar canal válido
        if bot.channels_info:
            test_channel = list(bot.channels_info.keys())[0]
            validation = bot.validate_channel_for_reports(test_channel)
            print(f"   Canal válido ({test_channel}): {'✅' if validation['valid'] else '❌'}")
        
        # Testar canal inválido
        fake_channel = "999999999999999999"
        validation = bot.validate_channel_for_reports(fake_channel)
        print(f"   Canal inválido ({fake_channel}): {'✅' if validation['valid'] else '❌'} (esperado)")
        
        # Testar mensagens
        print(f"\n📝 Testando mensagens:")
        channels_list = bot._get_active_channels_list()
        print(f"   Lista de canais: {len(channels_list.split(chr(10)))} linhas")
        
        # Testar mensagem de canal não configurado
        not_configured_msg = bot.get_channel_not_configured_message(fake_channel)
        print(f"   Mensagem canal não configurado: {len(not_configured_msg)} caracteres")
        
        print("\n✅ Testes concluídos com sucesso!")
        print("\n🚀 Para iniciar o bot universal, execute:")
        print("   python discord_bot_universal.py")
        
    except Exception as e:
        print(f"❌ Erro durante os testes: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Função principal."""
    test_universal_bot()

if __name__ == "__main__":
    main() 