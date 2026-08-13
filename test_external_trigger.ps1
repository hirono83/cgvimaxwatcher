[CmdletBinding()]
param(
    [string]$Token = $env:CGV_GITHUB_ACTIONS_TOKEN
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Token)) {
    throw 'CGV_GITHUB_ACTIONS_TOKEN 환경 변수에 GitHub fine-grained PAT를 설정하세요.'
}

$Uri = 'https://api.github.com/repos/hirono83/cgvimaxwatcher/actions/workflows/cgv-imax-watcher.yml/dispatches'
$Headers = @{
    Accept                 = 'application/vnd.github+json'
    Authorization          = "Bearer $Token"
    'X-GitHub-Api-Version' = '2026-03-10'
}
$Body = @{
    ref = 'main'
    inputs = @{
        force             = $false
        test_notification = $false
        trigger_source    = 'local-test'
    }
} | ConvertTo-Json -Depth 3

$Response = Invoke-WebRequest `
    -Uri $Uri `
    -Method Post `
    -Headers $Headers `
    -ContentType 'application/json' `
    -Body $Body

Write-Host "GitHub Actions 호출 성공: HTTP $([int]$Response.StatusCode)"
if ($Response.Content) {
    $Result = $Response.Content | ConvertFrom-Json
    if ($Result.html_url) {
        Write-Host "실행 확인: $($Result.html_url)"
    }
}

Write-Host '보안을 위해 현재 PowerShell 세션의 토큰을 삭제하세요:'
Write-Host 'Remove-Item Env:CGV_GITHUB_ACTIONS_TOKEN'
