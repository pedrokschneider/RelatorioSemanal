from report_system.main import WeeklyReportSystem

if __name__ == "__main__":
    system = WeeklyReportSystem()
    resultado = system.log_execution_to_sheet(
        project_id="TESTE",
        project_name="Teste Manual",
        status="Teste",
        message="Teste de log manual",
        doc_url="https://exemplo.com"
    )
    print("Resultado do log:", resultado) 