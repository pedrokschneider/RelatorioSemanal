#!/usr/bin/env python3
"""
Script para migrar do bot original para o bot universal.
"""

import os
import sys
import subprocess
import win32serviceutil
import win32service
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def check_service_status():
    """Verifica o status do serviço atual."""
    print("🔍 VERIFICANDO STATUS DO SERVIÇO ATUAL")
    print("=" * 50)
    
    try:
        # Verificar se o serviço original existe
        try:
            win32serviceutil.QueryService("DiscordReportBot")
            print("✅ Serviço original (DiscordReportBot) encontrado")
            original_exists = True
        except:
            print("❌ Serviço original (DiscordReportBot) não encontrado")
            original_exists = False
        
        # Verificar se o serviço universal existe
        try:
            win32serviceutil.QueryService("DiscordReportBotUniversal")
            print("✅ Serviço universal (DiscordReportBotUniversal) encontrado")
            universal_exists = True
        except:
            print("❌ Serviço universal (DiscordReportBotUniversal) não encontrado")
            universal_exists = False
        
        return original_exists, universal_exists
        
    except Exception as e:
        print(f"❌ Erro ao verificar serviços: {e}")
        return False, False

def stop_original_service():
    """Para o serviço original."""
    print("\n⏹️  PARANDO SERVIÇO ORIGINAL")
    print("=" * 50)
    
    try:
        win32serviceutil.StopService("DiscordReportBot")
        print("✅ Serviço original parado com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao parar serviço original: {e}")
        return False

def uninstall_original_service():
    """Desinstala o serviço original."""
    print("\n🗑️  DESINSTALANDO SERVIÇO ORIGINAL")
    print("=" * 50)
    
    try:
        win32serviceutil.RemoveService("DiscordReportBot")
        print("✅ Serviço original desinstalado com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao desinstalar serviço original: {e}")
        return False

def install_universal_service():
    """Instala o serviço universal."""
    print("\n🚀 INSTALANDO SERVIÇO UNIVERSAL")
    print("=" * 50)
    
    try:
        # Executar o script de instalação
        result = subprocess.run([sys.executable, "install_service_final.py"], 
                              capture_output=True, text=True, check=True)
        print("✅ Serviço universal instalado com sucesso")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao instalar serviço universal: {e}")
        print(f"   Saída: {e.stdout}")
        print(f"   Erro: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

def start_universal_service():
    """Inicia o serviço universal."""
    print("\n▶️  INICIANDO SERVIÇO UNIVERSAL")
    print("=" * 50)
    
    try:
        win32serviceutil.StartService("DiscordReportBotUniversal")
        print("✅ Serviço universal iniciado com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao iniciar serviço universal: {e}")
        return False

def test_universal_bot():
    """Testa o bot universal."""
    print("\n🧪 TESTANDO BOT UNIVERSAL")
    print("=" * 50)
    
    try:
        result = subprocess.run([sys.executable, "test_universal_bot.py"], 
                              capture_output=True, text=True, check=True)
        print("✅ Teste do bot universal executado com sucesso")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro no teste do bot universal: {e}")
        print(f"   Saída: {e.stdout}")
        print(f"   Erro: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado no teste: {e}")
        return False

def show_migration_menu():
    """Mostra o menu de migração."""
    print("🤖 MIGRAÇÃO PARA BOT UNIVERSAL")
    print("=" * 50)
    print()
    print("Este script irá migrar do bot original para o bot universal.")
    print()
    print("O que será feito:")
    print("1. ✅ Verificar status dos serviços")
    print("2. ⏹️  Parar serviço original")
    print("3. 🗑️  Desinstalar serviço original")
    print("4. 🚀 Instalar serviço universal")
    print("5. ▶️  Iniciar serviço universal")
    print("6. 🧪 Testar bot universal")
    print()
    print("⚠️  ATENÇÃO: O bot original será parado durante a migração!")
    print()

def main():
    """Função principal."""
    show_migration_menu()
    
    # Verificar se o usuário quer continuar
    response = input("Deseja continuar com a migração? (s/n): ").lower().strip()
    if response != 's':
        print("❌ Migração cancelada pelo usuário")
        return
    
    print("\n" + "=" * 50)
    print("🚀 INICIANDO MIGRAÇÃO")
    print("=" * 50)
    
    # 1. Verificar status
    original_exists, universal_exists = check_service_status()
    
    if not original_exists:
        print("\n⚠️  Serviço original não encontrado. Pulando para instalação do universal.")
    else:
        # 2. Parar serviço original
        if not stop_original_service():
            print("\n❌ Falha ao parar serviço original. Migração interrompida.")
            return
        
        # 3. Desinstalar serviço original
        if not uninstall_original_service():
            print("\n❌ Falha ao desinstalar serviço original. Migração interrompida.")
            return
    
    # 4. Instalar serviço universal
    if not install_universal_service():
        print("\n❌ Falha ao instalar serviço universal. Migração interrompida.")
        return
    
    # 5. Iniciar serviço universal
    if not start_universal_service():
        print("\n❌ Falha ao iniciar serviço universal. Migração interrompida.")
        return
    
    # 6. Testar bot universal
    if not test_universal_bot():
        print("\n⚠️  Teste do bot universal falhou, mas o serviço foi instalado.")
    
    print("\n" + "=" * 50)
    print("🎉 MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 50)
    print()
    print("✅ O bot universal foi instalado e está rodando")
    print("✅ O bot agora escuta TODOS os canais e tópicos")
    print("✅ Comandos funcionam em qualquer lugar com validação inteligente")
    print()
    print("📋 Para verificar o status do serviço:")
    print("   sc query DiscordReportBotUniversal")
    print()
    print("📋 Para parar o serviço:")
    print("   sc stop DiscordReportBotUniversal")
    print()
    print("📋 Para iniciar o serviço:")
    print("   sc start DiscordReportBotUniversal")
    print()
    print("📋 Para desinstalar o serviço:")
    print("   sc delete DiscordReportBotUniversal")
    print()
    print("🔍 Logs do bot universal:")
    print("   logs/discord_bot_universal_YYYY-MM-DD.log")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Migração interrompida pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro fatal durante migração: {e}")
        import traceback
        traceback.print_exc() 