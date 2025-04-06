"""
Script para simular comandos do Discord e testar a funcionalidade de atualização de cache.
Versão corrigida para evitar problemas de importação circular.
"""

import os
import sys
import time
import logging
import argparse
import importlib.util
from datetime import datetime

# Adicionar o diretório pai ao path para poder importar os módulos
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)
sys.path.insert(0, os.path.join(project_dir, "report_system"))


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("DiscordTest")



def simulate_discord_command(command, channel_id, project_id=None, config_path=".env"):
    """
    Simula um comando recebido pelo Discord e verifica a resposta.
    
    Args:
        command: Comando a ser simulado (ex: 'relatorio', 'atualizar', 'status')
        channel_id: ID do canal do Discord
        project_id: ID do projeto (opcional)
        config_path: Caminho para o arquivo de configuração
    
    Returns:
        Resultado da execução do comando
    """
    try:
        # Importamos o sistema diretamente para evitar problemas de importação circular
        from main import WeeklyReportSystem
        import pandas as pd
        
        logger.info("=" * 50)
        logger.info(f"SIMULANDO COMANDO DISCORD: {command}")
        logger.info(f"Canal: {channel_id}, Projeto: {project_id or 'Auto-detectar'}")
        logger.info("=" * 50)
        
        # Iniciar sistema
        logger.info("Inicializando sistema...")
        start_time = time.time()
        system = WeeklyReportSystem(config_path)
        init_time = time.time() - start_time
        logger.info(f"Sistema inicializado em {init_time:.2f} segundos")
        
        # Executar comando
        logger.info(f"Processando comando '{command}'...")
        command_start = time.time()
        
        # Registrar estado inicial do cache
        initial_status = system.cache_manager.get_cache_status()
        if project_id:
            project_cache_before = initial_status[initial_status['cache_key'].str.contains(str(project_id))]
            logger.info(f"Entradas de cache para projeto antes: {len(project_cache_before)}")
        
        # Processar o comando
        result = system.process_discord_command(channel_id, command, project_id)
        command_time = time.time() - command_start
        
        # Registrar estado final do cache
        final_status = system.cache_manager.get_cache_status()
        if project_id:
            project_cache_after = final_status[final_status['cache_key'].str.contains(str(project_id))]
            logger.info(f"Entradas de cache para projeto depois: {len(project_cache_after)}")
            
            # Identificar atualizações
            updated_entries = []
            for idx, row in project_cache_after.iterrows():
                cache_key = row['cache_key']
                # Verificar se existia antes ou é nova
                if cache_key in project_cache_before['cache_key'].values:
                    # Obter hora da atualização anterior
                    old_rows = project_cache_before[project_cache_before['cache_key'] == cache_key]
                    if not old_rows.empty:
                        old_row = old_rows.iloc[0]
                        if pd.to_datetime(row['last_update']) > pd.to_datetime(old_row['last_update']):
                            updated_entries.append(f"{cache_key} (atualizado)")
                else:
                    updated_entries.append(f"{cache_key} (novo)")
            
            if updated_entries:
                logger.info("Entradas de cache atualizadas:")
                for entry in updated_entries:
                    logger.info(f"- {entry}")
        
        # Relatório final
        logger.info("=" * 50)
        logger.info(f"RESULTADO DO COMANDO DISCORD")
        logger.info(f"Comando: {command}")
        logger.info(f"Sucesso: {'Sim' if result else 'Não'}")
        logger.info(f"Tempo de execução: {command_time:.2f} segundos")
        logger.info("=" * 50)
        
        return {
            "command": command,
            "success": result,
            "time": command_time,
            "project_id": project_id,
            "channel_id": channel_id
        }
    except Exception as e:
        logger.error(f"Erro ao simular comando Discord: {e}")
        return {"error": str(e)}

def main():
    """Função principal para execução do teste."""
    parser = argparse.ArgumentParser(description='Teste de Comandos do Discord')
    parser.add_argument('--command', type=str, required=True, choices=['relatorio', 'report', 'atualizar', 'update', 'status'], 
                        help='Comando a ser simulado')
    parser.add_argument('--channel', type=str, required=True, help='ID do canal do Discord')
    parser.add_argument('--project', type=str, help='ID do projeto (opcional)')
    parser.add_argument('--config', type=str, default=".env", help='Caminho para arquivo de configuração')
    
    args = parser.parse_args()
    
    # Executar simulação
    simulate_discord_command(args.command, args.channel, args.project, args.config)

if __name__ == "__main__":
    main()