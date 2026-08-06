$ErrorActionPreference = 'Stop'
$TaskName = 'CGV-Yongsan-IMAX-Watcher'
$ScriptPath = Join-Path $PSScriptRoot 'cgv_imax_watcher.py'
$ConfigPath = Join-Path $PSScriptRoot 'config.json'
if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "감시기 파일을 찾을 수 없습니다: $ScriptPath"
}

$Python = Get-Command py.exe -ErrorAction SilentlyContinue
$PythonArgs = @('-3', $ScriptPath)
$ScheduledArgs = '-3 "{0}"' -f $ScriptPath
if (-not $Python) {
    $Python = Get-Command python.exe -ErrorAction SilentlyContinue
    $PythonArgs = @($ScriptPath)
    $ScheduledArgs = '"{0}"' -f $ScriptPath
}
if (-not $Python) {
    throw 'Python 3을 찾지 못했습니다. Python 3 설치 후 다시 실행하세요.'
}

$Config = Get-Content -Raw -Encoding UTF8 -LiteralPath $ConfigPath | ConvertFrom-Json
$Now = Get-Date
$Start = $Now.AddHours(1)
$Start = Get-Date -Year $Start.Year -Month $Start.Month -Day $Start.Day -Hour $Start.Hour -Minute 0 -Second 0
$EndExclusive = ([datetime]::ParseExact($Config.end_date, 'yyyy-MM-dd', $null)).AddDays(1)
if ($Start -ge $EndExclusive) {
    throw "감시 종료일($($Config.end_date))이 이미 지났습니다."
}

$Duration = $EndExclusive - $Start
$Trigger = New-ScheduledTaskTrigger -Once -At $Start -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration $Duration
$Action = New-ScheduledTaskAction -Execute $Python.Source -Argument $ScheduledArgs -WorkingDirectory $PSScriptRoot
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description 'CGV 용산아이파크몰 IMAX 2026-08-18~23 예매 오픈 감시' -Force | Out-Null

Write-Host "설치 완료: $TaskName"
Write-Host '검사 시간: 하루 24시간, 매시간 (2026-08-23까지)'
Write-Host 'PC가 켜져 있고 현재 Windows 사용자가 로그인되어 있어야 알림이 표시됩니다.'
& $Python.Source @PythonArgs --force --dry-run
if ($LASTEXITCODE -ne 0) {
    Write-Warning "시험 조회 실패. watcher.log를 확인하세요. 종료 코드: $LASTEXITCODE"
} else {
    Write-Host '시험 조회 완료. watcher.log에서 결과를 확인할 수 있습니다.'
}

