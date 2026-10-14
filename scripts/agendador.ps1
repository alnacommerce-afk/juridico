<#
 Agendador do monitoramento diario (Windows Task Scheduler), 08:00 no fuso do Windows.
 Uso:  powershell -File scripts\agendador.ps1 -Acao instalar|status|remover|testar
 O Windows deve estar com fuso "Brasilia" (UTC-03:00); `testar` verifica isso.
#>
param([Parameter(Mandatory=$true)][ValidateSet('instalar','status','remover','testar')][string]$Acao,
      [string]$Hora = '08:00')
$ErrorActionPreference = 'Stop'
$Nome = 'JURIDICO-ALNA-Monitoramento-Diario'
$Raiz = Split-Path -Parent $PSScriptRoot
# sys.executable evita o alias da Microsoft Store (WindowsApps), que falha sob o Agendador de Tarefas
$Py = $null
try { $Py = (& python -c "import sys;print(sys.executable)").Trim() } catch {}
$Script = Join-Path $Raiz 'scripts\monitor.py'

switch ($Acao) {
 'testar' {
   if (-not $Py) { throw 'python nao encontrado no PATH' }
   $tz = (Get-TimeZone).BaseUtcOffset.TotalHours
   "Python: $Py"; "Script: $Script (existe: $(Test-Path $Script))"
   "Fuso do Windows: $((Get-TimeZone).Id) (UTC$tz) - esperado -3"
   if ($tz -ne -3) { Write-Warning 'Fuso diferente de Brasilia: 08:00 sera no horario LOCAL do Windows.' }
   & $Py $Script status
 }
 'instalar' {
   if (-not $Py) { throw 'python nao encontrado no PATH' }
   $a = New-ScheduledTaskAction -Execute $Py -Argument "`"$Script`" run" -WorkingDirectory $Raiz
   $t = New-ScheduledTaskTrigger -Daily -At $Hora
   $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
   Register-ScheduledTask -TaskName $Nome -Action $a -Trigger $t -Settings $s -Description 'JURIDICO ALNA - consulta diaria' -Force | Out-Null
   "Tarefa '$Nome' instalada para $Hora diariamente (StartWhenAvailable: roda ao ligar o PC se perdeu o horario)."
 }
 'status' {
   $x = Get-ScheduledTask -TaskName $Nome -ErrorAction SilentlyContinue
   if (-not $x) { 'NAO INSTALADA'; exit 0 }
   $i = Get-ScheduledTaskInfo -TaskName $Nome
   "Estado: $($x.State) | Ultima execucao: $($i.LastRunTime) | Resultado: $($i.LastTaskResult) | Proxima: $($i.NextRunTime)"
   & $Py $Script status
 }
 'remover' { Unregister-ScheduledTask -TaskName $Nome -Confirm:$false; "Tarefa removida." }
}
