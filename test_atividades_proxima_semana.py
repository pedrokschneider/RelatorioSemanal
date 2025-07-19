#!/usr/bin/env python3
"""
Script de teste para verificar se as atividades da próxima semana estão sendo identificadas corretamente.
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_system.config import ConfigManager
from report_system.generators.report_generator import SimpleReportGenerator, parse_data_flex

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_parse_data_flex():
    """Testa a função parse_data_flex com diferentes formatos de data."""
    print("=== Testando parse_data_flex ===")
    
    test_dates = [
        "25/12/2024",
        "25/12/24", 
        "2024-12-25",
        "25/12",
        "2024-12-25 10:30:00",
        "25/12/2024 10:30:00",
        "2024-12-25T10:30:00",
        "2024-12-25T10:30:00.123456",
        "2024-12-25T10:30:00.123456Z",
        "2024-12-25T10:30:00Z",
        "invalid_date",
        "",
        None
    ]
    
    for date_str in test_dates:
        result = parse_data_flex(date_str)
        if result:
            print(f"✓ '{date_str}' -> {result.strftime('%d/%m/%Y')}")
        else:
            print(f"✗ '{date_str}' -> None")

def test_intervalo_datas():
    """Testa o cálculo do intervalo de datas para atividades da próxima semana."""
    print("\n=== Testando cálculo de intervalo de datas ===")
    
    hoje = datetime.now()
    weekday = hoje.weekday()
    
    print(f"Hoje: {hoje.strftime('%d/%m/%Y')} (dia da semana: {weekday})")
    
    if weekday < 4:  # Antes de sexta-feira
        segunda_atual = (hoje - timedelta(days=hoje.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        domingo_proxima = segunda_atual + timedelta(days=13)
        intervalo_inicio = segunda_atual
        intervalo_fim = domingo_proxima
        print(f"Relatório antes de sexta-feira")
    else:
        dias_ate_segunda = (7 - hoje.weekday()) % 7 or 7
        proxima_segunda = (hoje + timedelta(days=dias_ate_segunda)).replace(hour=0, minute=0, second=0, microsecond=0)
        proximo_domingo = proxima_segunda + timedelta(days=6)
        intervalo_inicio = proxima_segunda
        intervalo_fim = proximo_domingo
        print(f"Relatório após sexta-feira")
    
    print(f"Intervalo: {intervalo_inicio.strftime('%d/%m/%Y')} a {intervalo_fim.strftime('%d/%m/%Y')}")
    
    # Testar algumas datas
    test_dates = [
        datetime.now() + timedelta(days=1),   # Amanhã
        datetime.now() + timedelta(days=7),   # Próxima semana
        datetime.now() + timedelta(days=14),  # Em 2 semanas
        datetime.now() - timedelta(days=1),   # Ontem
    ]
    
    for test_date in test_dates:
        if intervalo_inicio <= test_date <= intervalo_fim:
            print(f"✓ {test_date.strftime('%d/%m/%Y')} está no intervalo")
        else:
            print(f"✗ {test_date.strftime('%d/%m/%Y')} está fora do intervalo")

def test_dados_exemplo():
    """Testa com dados de exemplo para simular o processamento real."""
    print("\n=== Testando com dados de exemplo ===")
    
    # Dados de exemplo baseados no Smartsheet
    dados_exemplo = {
        'project_id': '123',
        'project_name': 'Projeto Teste',
        'smartsheet_data': [
            {
                'Nome da Tarefa': 'Tarefa que inicia amanhã',
                'Data Inicio': (datetime.now() + timedelta(days=1)).strftime('%d/%m/%Y'),
                'Data Término': (datetime.now() + timedelta(days=5)).strftime('%d/%m/%Y'),
                'Disciplina': 'Arquitetura',
                'Status': 'Em andamento'
            },
            {
                'Nome da Tarefa': 'Tarefa que inicia na próxima semana',
                'Data Inicio': (datetime.now() + timedelta(days=8)).strftime('%d/%m/%Y'),
                'Data Término': (datetime.now() + timedelta(days=12)).strftime('%d/%m/%Y'),
                'Disciplina': 'Estrutural',
                'Status': 'Planejado'
            },
            {
                'Nome da Tarefa': 'Tarefa que já iniciou',
                'Data Inicio': (datetime.now() - timedelta(days=5)).strftime('%d/%m/%Y'),
                'Data Término': (datetime.now() + timedelta(days=2)).strftime('%d/%m/%Y'),
                'Disciplina': 'Elétrica',
                'Status': 'Em andamento'
            },
            {
                'Nome da Tarefa': 'Tarefa sem data de início',
                'Data Término': (datetime.now() + timedelta(days=10)).strftime('%d/%m/%Y'),
                'Disciplina': 'Hidráulica',
                'Status': 'Planejado'
            }
        ]
    }
    
    # Criar instância do gerador
    config = ConfigManager()
    generator = SimpleReportGenerator(config)
    
    # Gerar seção de atividades da próxima semana
    resultado = generator._gerar_atividades_iniciadas_proxima_semana(dados_exemplo)
    
    print("Resultado da geração:")
    print(resultado)

if __name__ == "__main__":
    print("Teste de Atividades da Próxima Semana")
    print("=" * 50)
    
    try:
        test_parse_data_flex()
        test_intervalo_datas()
        test_dados_exemplo()
        
        print("\n" + "=" * 50)
        print("Testes concluídos!")
        
    except Exception as e:
        print(f"Erro durante os testes: {e}")
        import traceback
        traceback.print_exc() 