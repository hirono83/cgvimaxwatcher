$ErrorActionPreference = 'Stop'
$TaskName = 'CGV-Yongsan-IMAX-Watcher'
$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "작업 스케줄러에서 제거했습니다: $TaskName"
} else {
    Write-Host "설치된 작업이 없습니다: $TaskName"
}
