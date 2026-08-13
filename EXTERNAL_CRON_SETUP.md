# cron-job.org 외부 5분 실행 설정

GitHub의 예약 `schedule` 이벤트 대신 cron-job.org가 GitHub Actions API를 5분마다 호출합니다. 텔레그램 토큰과 채팅 ID는 기존 GitHub Actions Secrets에 그대로 두며, cron-job.org에는 이 저장소의 Actions 실행 권한만 가진 제한 토큰을 등록합니다.

## 1. GitHub fine-grained PAT 만들기

GitHub에서 Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token으로 이동합니다.

- Token name: `cgvimaxwatcher-cron`
- Expiration: 감시 종료일 직후로 설정
- Resource owner: `hirono83`
- Repository access: `Only select repositories` → `cgvimaxwatcher`
- Repository permissions: `Actions` → `Read and write`
- 나머지 권한: 기본값 유지

생성 직후 표시되는 토큰을 복사합니다. 토큰을 저장소 파일, 이슈, 채팅에 넣지 마세요.

## 2. 로컬에서 API 호출 시험

PowerShell의 현재 세션에만 토큰을 설정하고 시험 스크립트를 실행합니다.

```powershell
$env:CGV_GITHUB_ACTIONS_TOKEN = '<fine-grained PAT>'
.\test_external_trigger.ps1
Remove-Item Env:CGV_GITHUB_ACTIONS_TOKEN
```

GitHub Actions 목록에 `CGV Odyssey IMAX check · local-test` 실행이 생기면 정상입니다.

## 3. cron-job.org 작업 만들기

cron-job.org에 로그인한 뒤 Cronjobs → Create cronjob에서 다음 값을 등록합니다.

### 기본 설정

- Title: `CGV Odyssey IMAX Watcher`
- URL: `https://api.github.com/repos/hirono83/cgvimaxwatcher/actions/workflows/cgv-imax-watcher.yml/dispatches`
- Schedule: 매 5분
- Enabled: 켬

### Advanced 설정

- Request method: `POST`
- Request timeout: 30초
- Request headers:

```text
Accept: application/vnd.github+json
Authorization: Bearer <fine-grained PAT>
X-GitHub-Api-Version: 2026-03-10
Content-Type: application/json
```

- Request body:

```json
{
  "ref": "main",
  "inputs": {
    "force": false,
    "test_notification": false,
    "trigger_source": "cron-job.org"
  }
}
```

응답 저장 기능은 끄고, 실패 알림은 켜는 것을 권장합니다. 작업을 한 번 수동 실행해 HTTP 성공 응답을 확인합니다.

## 4. 정상 동작 확인

- cron-job.org History: 5분마다 HTTP 성공
- GitHub Actions: `CGV Odyssey IMAX check · cron-job.org` 실행 생성
- GitHub Actions의 `Check CGV schedule`: 날짜별 오디세이 IMAX 회차 수 출력
- 새 회차 발견 시: 텔레그램 알림 후 `state.json` 자동 커밋

외부 호출은 GitHub에서 `workflow_dispatch` 이벤트로 표시되는 것이 정상입니다.

## 보안 및 중지

- 토큰이 노출되면 즉시 GitHub에서 폐기하고 새로 발급합니다.
- 감시가 끝나면 cron-job.org 작업을 비활성화하고 PAT를 폐기합니다.
- cron-job.org 계정에는 2단계 인증을 사용하는 것을 권장합니다.

## 문제 해결

- HTTP 401: 토큰이 잘못됐거나 만료됨
- HTTP 403: fine-grained PAT의 Actions 권한이 Read-only이거나 저장소가 선택되지 않음
- HTTP 404: URL의 저장소 또는 워크플로 파일명이 잘못됨
- HTTP 422: 요청 본문, `ref`, 입력 이름 중 하나가 워크플로와 일치하지 않음
