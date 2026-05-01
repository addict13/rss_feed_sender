# 📰 RSS 뉴스 다이제스트 자동화

RSS 피드를 수집하고, Claude AI로 기사 전문을 분석·요약한 뒤, 매일 이메일로 발송하는 자동화 시스템입니다.

---

## 📁 파일 구조

```
.
├── rss_analyzer.py                        # 메인 스크립트
├── requirements.txt                       # Python 의존성
├── .github/
│   └── workflows/
│       └── daily-digest.yml               # GitHub Actions 워크플로우
└── README.md
```

---

## ⚡ 빠른 시작

### 1단계 · GitHub 저장소 생성

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/<YourName>/<repo-name>.git
git push -u origin main
```

### 2단계 · GitHub Secrets 등록

저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 이름        | 값 예시                          | 설명                        |
|--------------------|----------------------------------|-----------------------------|
| `ANTHROPIC_API_KEY`| `sk-ant-...`                     | Anthropic API 키            |
| `SMTP_HOST`        | `smtp.gmail.com`                 | SMTP 서버 호스트            |
| `SMTP_PORT`        | `587`                            | SMTP 포트 (TLS)             |
| `SMTP_USER`        | `yourname@gmail.com`             | 발신 Gmail 주소             |
| `SMTP_PASSWORD`    | `xxxx xxxx xxxx xxxx`            | Gmail **앱 비밀번호** ★     |
| `TO_EMAIL`         | `receiver@example.com`           | 수신자 이메일               |

> ★ **Gmail 앱 비밀번호 만들기**  
> Google 계정 → 보안 → 2단계 인증 활성화 →  
> [앱 비밀번호](https://myaccount.google.com/apppasswords) → 앱: `메일`, 기기: `기타` → 생성

---

### 3단계 · RSS 피드 추가

`rss_analyzer.py` 상단 `RSS_FEEDS` 리스트를 수정합니다:

```python
RSS_FEEDS = [
    {"name": "내 블로그",    "url": "https://myblog.com/rss"},
    {"name": "Reuters Tech", "url": "https://feeds.reuters.com/reuters/technologyNews"},
    {"name": "연합뉴스",     "url": "https://www.yna.co.kr/rss/news.xml"},
    # 원하는 만큼 추가하세요
]
```

---

## ⏰ 발송 스케줄

기본값: **매일 오전 8시 KST** (`cron: "0 23 * * *"` = UTC 23:00)

변경하려면 `.github/workflows/daily-digest.yml`의 cron 값을 수정하세요.

| 원하는 시간 (KST) | cron 값           |
|------------------|-------------------|
| 오전 7시         | `0 22 * * *`      |
| 오전 8시         | `0 23 * * *`      |
| 오전 9시         | `0 0 * * *`       |
| 오후 6시         | `0 9 * * *`       |

---

## 🧪 수동 테스트

GitHub 저장소 → **Actions → Daily RSS Digest → Run workflow**

`dry_run: true`로 실행하면 이메일 발송 없이 로그만 확인할 수 있습니다.  
생성된 HTML은 **Artifacts**에서 다운로드해 브라우저로 미리보기 가능합니다.

---

## ⚙️ 주요 설정값

`rss_analyzer.py` 상단에서 조정:

| 변수                  | 기본값 | 설명                               |
|-----------------------|--------|------------------------------------|
| `MAX_ARTICLES_PER_FEED` | `3`  | 피드당 가져올 최신 기사 수         |
| `MAX_CONTENT_CHARS`   | `6000` | Claude에게 전달할 본문 최대 글자 수 |
| `HOURS_LOOKBACK`      | `25`   | 최근 N시간 이내 기사만 포함        |

---

## 🛠 로컬 실행

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-..."
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="yourname@gmail.com"
export SMTP_PASSWORD="앱비밀번호"
export TO_EMAIL="receiver@example.com"

python rss_analyzer.py
```

---

## 📧 이메일 예시

- 각 기사마다 **핵심 요약**, **주요 포인트**, **중요도**, **한 줄 인사이트** 제공  
- 피드별로 섹션 분리  
- 원문 링크 포함  
- 모바일 친화적 HTML 디자인
