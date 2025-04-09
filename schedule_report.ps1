# Configuração da tarefa agendada
$taskName = "RelatorioSemanal"
$taskDescription = "Executa o relatório semanal toda sexta-feira às 15:00"
$scriptPath = "C:\GitHub\RelatorioSemanal\run_report.bat"
$startTime = "15:00"

# Criar a ação
$action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory "C:\GitHub\RelatorioSemanal"

# Criar o trigger (toda sexta-feira às 15:00)
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At $startTime

# Configurar as configurações
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -RestartInterval (New-TimeSpan -Minutes 1) -RestartCount 3

# Registrar a tarefa
Register-ScheduledTask -TaskName $taskName -Description $taskDescription -Action $action -Trigger $trigger -Settings $settings -Force

Write-Host "Tarefa agendada criada com sucesso!"
Write-Host "Nome: $taskName"
Write-Host "Execução: Toda sexta-feira às $startTime" 