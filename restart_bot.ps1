# Script para reiniciar o bot Discord
# Execute este script como Administrador

Write-Host "🔄 Reiniciando Bot Discord..." -ForegroundColor Cyan

$serviceName = "Discord Report Bot"

# Verificar se o serviço existe
$service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue

if (-not $service) {
    Write-Host "❌ Serviço '$serviceName' não encontrado!" -ForegroundColor Red
    exit 1
}

Write-Host "📊 Status atual: $($service.Status)" -ForegroundColor Yellow

# Parar o serviço
Write-Host "⏹️  Parando serviço..." -ForegroundColor Yellow
try {
    Stop-Service -Name $serviceName -Force -ErrorAction Stop
    Start-Sleep -Seconds 3
    Write-Host "✅ Serviço parado com sucesso" -ForegroundColor Green
} catch {
    Write-Host "❌ Erro ao parar serviço: $_" -ForegroundColor Red
    Write-Host "💡 Tente executar como Administrador" -ForegroundColor Yellow
    exit 1
}

# Iniciar o serviço
Write-Host "▶️  Iniciando serviço..." -ForegroundColor Yellow
try {
    Start-Service -Name $serviceName -ErrorAction Stop
    Start-Sleep -Seconds 3
    Write-Host "✅ Serviço iniciado com sucesso" -ForegroundColor Green
} catch {
    Write-Host "❌ Erro ao iniciar serviço: $_" -ForegroundColor Red
    exit 1
}

# Verificar status final
$finalStatus = Get-Service -Name $serviceName
Write-Host "`n📊 Status final: $($finalStatus.Status)" -ForegroundColor $(if ($finalStatus.Status -eq 'Running') { 'Green' } else { 'Red' })

if ($finalStatus.Status -eq 'Running') {
    Write-Host "`n✅ Bot reiniciado com sucesso!" -ForegroundColor Green
    Write-Host "📋 Logs disponíveis em: logs\discord_bot_$(Get-Date -Format 'yyyy-MM-dd').log" -ForegroundColor Cyan
    Write-Host "📋 Logs do serviço: logs\service.log" -ForegroundColor Cyan
} else {
    Write-Host "`n❌ Bot não está rodando. Verifique os logs." -ForegroundColor Red
}










