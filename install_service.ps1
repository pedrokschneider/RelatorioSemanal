# Script para instalar o serviço do Discord Bot
$ErrorActionPreference = "Stop"

# Configurações
$serviceName = "Discord Report Bot"
$displayName = "Bot Discord para Relatórios Semanais"
$description = "Bot Discord para Relatórios Semanais"
$pythonPath = "C:\Users\Otus - TI\AppData\Local\Programs\Python\Python313\python.exe"
$scriptPath = "C:\GitHub\RelatorioSemanal\discord_bot.py"
$nssmPath = "C:\GitHub\RelatorioSemanal\nssm\nssm.exe"
$workingDir = "C:\GitHub\RelatorioSemanal"
$logPath = "C:\GitHub\RelatorioSemanal\logs\service.log"

# Verificar se o NSSM existe
if (-not (Test-Path $nssmPath)) {
    Write-Host "Erro: NSSM não encontrado em $nssmPath"
    Write-Host "Por favor, certifique-se que a pasta nssm existe no diretório do projeto"
    exit 1
}

# Verificar se o Python existe
if (-not (Test-Path $pythonPath)) {
    Write-Host "Erro: Python não encontrado em $pythonPath"
    exit 1
}

# Verificar se o script existe
if (-not (Test-Path $scriptPath)) {
    Write-Host "Erro: Script não encontrado em $scriptPath"
    exit 1
}

# Verificar se as dependências estão instaladas
Write-Host "Verificando dependências..."
& $pythonPath -c "import discord; import pandas; import numpy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando dependências..."
    & $pythonPath -m pip install --only-binary :all: discord.py pandas numpy
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Erro ao instalar dependências"
        exit 1
    }
}

# Criar diretório de logs se não existir
$logDir = Split-Path $logPath -Parent
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

# Remover serviço existente
Write-Host "Removendo serviço existente (se existir)..."
& $nssmPath stop "$serviceName" 2>$null
& $nssmPath remove "$serviceName" confirm 2>$null
Start-Sleep -Seconds 2

# Criar o serviço usando NSSM
Write-Host "Instalando novo serviço..."
Write-Host "Comando: $pythonPath $scriptPath --service"

# Instalar o serviço
& $nssmPath install "$serviceName" "$pythonPath" "`"$scriptPath`" --service"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Erro ao criar serviço usando NSSM"
    exit 1
}

# Configurar o serviço
& $nssmPath set "$serviceName" Description "$description"
& $nssmPath set "$serviceName" DisplayName "$displayName"
& $nssmPath set "$serviceName" AppDirectory "$workingDir"
& $nssmPath set "$serviceName" AppStdout "$logPath"
& $nssmPath set "$serviceName" AppStderr "$logPath"
& $nssmPath set "$serviceName" AppRotateFiles 1
& $nssmPath set "$serviceName" AppRotateOnline 1
& $nssmPath set "$serviceName" AppRotateSeconds 86400
& $nssmPath set "$serviceName" Start SERVICE_AUTO_START

# Iniciar o serviço
Write-Host "Iniciando serviço..."
& $nssmPath start "$serviceName"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Erro ao iniciar serviço"
    Write-Host "Verifique o log em: $logPath"
    exit 1
}

Write-Host "Serviço instalado e iniciado com sucesso!"
Write-Host "Nome do serviço: $serviceName"
Write-Host "Status: $(Get-Service -Name "$serviceName" | Select-Object -ExpandProperty Status)"

# Exibir informações úteis
Write-Host "`nInformações úteis:"
Write-Host "- Logs do serviço: $logPath"
Write-Host "- Logs do bot: C:\GitHub\RelatorioSemanal\logs\"
Write-Host "- Para reiniciar o serviço: nssm restart `"$serviceName`""
Write-Host "- Para parar o serviço: nssm stop `"$serviceName`""
Write-Host "- Para ver o status: nssm status `"$serviceName`""
Write-Host "- Para ver os logs em tempo real: Get-Content $logPath -Wait" 