# CGV 용산 IMAX 예매 오픈 알리미

CGV 용산아이파크몰 IMAX관의 2026년 8월 18일~23일 상영 회차를 한국시간 기준 매시간 1분에 하루 24시간 확인합니다. 새 회차를 처음 발견하면 텔레그램으로 알리고, 추가 회차가 없으면 변동사항 없음 메시지를 보냅니다. 중복 알림 상태는 state.json에 자동 저장합니다.

## GitHub Actions로 실행하기

### 1. 텔레그램 봇 준비

1. 텔레그램에서 @BotFather와 대화해 /newbot으로 봇을 만듭니다.
2. 받은 봇 토큰을 보관합니다.
3. 생성한 봇과 대화를 열고 아무 메시지나 하나 보냅니다.
4. 브라우저에서 아래 주소를 열어 chat 객체의 id 값을 확인합니다.

    https://api.telegram.org/bot<봇토큰>/getUpdates

토큰과 채팅 ID는 저장소 파일이나 채팅에 공개하지 마세요.

### 2. GitHub 저장소 만들기

1. GitHub에서 새 저장소를 만듭니다. 토큰 보호를 위해 Private 저장소를 권장합니다.
2. 이 폴더의 내용 전체를 저장소 최상위에 올립니다.
3. .github/workflows/cgv-imax-watcher.yml 파일이 정확한 위치에 있는지 확인합니다.

Git 명령을 사용하는 경우:

    git init
    git add .
    git commit -m "Add CGV IMAX watcher"
    git branch -M main
    git remote add origin <저장소 URL>
    git push -u origin main

### 3. GitHub Secrets 등록

저장소의 Settings → Secrets and variables → Actions → New repository secret에서 다음 두 개를 등록합니다.

- TELEGRAM_BOT_TOKEN: BotFather가 발급한 토큰
- TELEGRAM_CHAT_ID: getUpdates에서 확인한 채팅 ID

### 4. 권한 및 시험 실행

1. 저장소의 Actions 탭을 열고 워크플로 실행을 허용합니다.
2. Settings → Actions → General → Workflow permissions에서 Read and write permissions를 선택합니다. 조직 정책이 YAML의 contents: write 권한을 허용한다면 이 설정은 이미 충족될 수 있습니다.
3. Actions → CGV Yongsan IMAX Watcher → Run workflow를 엽니다.
4. test_notification을 체크하고 실행해 텔레그램 시험 메시지를 확인합니다.
5. 다시 실행할 때 test_notification을 해제하면 CGV의 6개 날짜를 실제 조회합니다.

CGV 조회 실행 시 현재 예매가 열려 있다면 실제 텔레그램 알림이 전송되고 state.json이 자동 커밋됩니다. 아직 열리지 않았다면 알림 없이 정상 종료합니다.

## 자동 실행 일정

- 한국시간 매시간 1분(00:01, 01:01, …, 23:01)
- GitHub Actions 혼잡이 많은 정각을 피해 매시 1분에 실행
- 2026년 8월 23일이 지나면 프로그램이 조회하지 않고 종료
- Actions 화면에서 Run workflow로 수동 실행 가능

예약 작업은 기본 브랜치에 워크플로 파일이 있어야 동작합니다. 공개 저장소는 60일간 활동이 없으면 예약 워크플로가 비활성화될 수 있습니다.

## 로컬 실행

Windows 로컬 작업 스케줄러 방식도 계속 사용할 수 있습니다.

    powershell -ExecutionPolicy Bypass -File .\install_task.ps1

직접 시험:

    python cgv_imax_watcher.py --force --dry-run

자동 작업 삭제:

    powershell -ExecutionPolicy Bypass -File .\uninstall_task.ps1

## 파일

- cgv_imax_watcher.py: CGV 조회 및 알림 본체
- .github/workflows/cgv-imax-watcher.yml: GitHub Actions 예약 실행
- config.json: 극장, 날짜, 시간 설정
- state.json: 알림 후 자동 생성되는 중복 방지 상태
- test_watcher.py: 파서 단위 테스트

CGV가 공개 시간표의 구조나 접근 정책을 변경하면 실행이 실패할 수 있습니다. 실패 여부는 GitHub Actions 실행 기록에서 확인할 수 있습니다.
