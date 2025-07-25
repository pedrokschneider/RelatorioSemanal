#!/usr/bin/env python3
"""
Script para testar a validação de canais do bot Discord.
"""

import os
import sys
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

def test_channel_validation():
    """Testa a validação de canais."""
    
    print("🧪 TESTANDO VALIDAÇÃO DE CANAIS")
    print("=" * 50)
    
    try:
        from discord_bot import DiscordBotAutoChannels
        
        # Inicializar o bot
        bot = DiscordBotAutoChannels()
        
        # Obter canais ativos
        active_channels = bot.get_channels_from_spreadsheet()
        print(f"📊 Canais ativos encontrados: {len(active_channels)}")
        
        # Testar validação de canais ativos
        print("\n✅ Testando canais ATIVOS:")
        for channel_id, info in list(active_channels.items())[:3]:  # Testar apenas os primeiros 3
            print(f"\n🔍 Testando canal: {channel_id} ({info['project_name']})")
            validation = bot.validate_channel_for_reports(channel_id)
            
            if validation['valid']:
                print(f"   ✅ VÁLIDO - Projeto: {validation['project_name']}")
            else:
                print(f"   ❌ INVÁLIDO - Motivo: {validation['reason']}")
                print(f"   📝 Mensagem: {validation['message'][:100]}...")
        
        # Testar validação de canais inexistentes
        print("\n❌ Testando canais INEXISTENTES:")
        fake_channels = [
            "999999999999999999",  # Canal fake
            "111111111111111111",  # Outro canal fake
            "000000000000000000"   # Canal zero
        ]
        
        for fake_channel in fake_channels:
            print(f"\n🔍 Testando canal fake: {fake_channel}")
            validation = bot.validate_channel_for_reports(fake_channel)
            
            if validation['valid']:
                print(f"   ⚠️  VÁLIDO (inesperado) - Projeto: {validation['project_name']}")
            else:
                print(f"   ✅ INVÁLIDO (esperado) - Motivo: {validation['reason']}")
                print(f"   📝 Mensagem: {validation['message'][:100]}...")
        
        # Testar comando !topico
        print("\n📋 Testando comando !topico:")
        for channel_id, info in list(active_channels.items())[:2]:  # Testar apenas os primeiros 2
            print(f"\n🔍 Testando !topico para: {channel_id} ({info['project_name']})")
            thread_info = bot.get_correct_thread_info(channel_id)
            
            if thread_info:
                print(f"   ✅ Tópico encontrado: {thread_info[:100]}...")
            else:
                print(f"   ❌ Tópico não encontrado")
        
        # Testar lista de canais ativos
        print("\n📋 Testando lista de canais ativos:")
        channels_list = bot._get_active_channels_list()
        print(f"   📝 Lista: {channels_list[:200]}...")
        
        print("\n✅ Testes concluídos com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro durante os testes: {e}")
        import traceback
        traceback.print_exc()

def test_specific_channel(channel_id):
    """Testa um canal específico."""
    
    print(f"🧪 TESTANDO CANAL ESPECÍFICO: {channel_id}")
    print("=" * 50)
    
    try:
        from discord_bot import DiscordBotAutoChannels
        
        # Inicializar o bot
        bot = DiscordBotAutoChannels()
        
        # Testar validação
        print(f"\n🔍 Validando canal: {channel_id}")
        validation = bot.validate_channel_for_reports(channel_id)
        
        print(f"Resultado da validação:")
        print(f"  Válido: {validation['valid']}")
        print(f"  Motivo: {validation.get('reason', 'N/A')}")
        
        if validation['valid']:
            print(f"  Projeto: {validation['project_name']}")
            print(f"  ID Construflow: {validation['project_id']}")
        else:
            print(f"  Mensagem: {validation['message']}")
        
        # Testar comando !topico
        print(f"\n🔍 Testando !topico para: {channel_id}")
        thread_info = bot.get_correct_thread_info(channel_id)
        
        if thread_info:
            print(f"Tópico encontrado: {thread_info}")
        else:
            print("Tópico não encontrado")
        
        print("\n✅ Teste concluído!")
        
    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Função principal."""
    if len(sys.argv) == 1:
        # Teste geral
        test_channel_validation()
    elif len(sys.argv) == 2:
        # Teste de canal específico
        channel_id = sys.argv[1]
        test_specific_channel(channel_id)
    else:
        print("Uso:")
        print("  python test_channel_validation.py                    # Teste geral")
        print("  python test_channel_validation.py <canal_id>        # Teste de canal específico")
        print("Exemplo:")
        print("  python test_channel_validation.py 1290649572372123678")

if __name__ == "__main__":
    main() 