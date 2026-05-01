#!/usr/bin/env python3
"""
RSS Feed Analyzer & Digest Emailer
- RSS 피드에서 기사를 수집하고 Claude AI로 분석/요약
- 결과를 HTML 이메일로 발송
"""

import os
import re
import smtplib
import feedparser
import requests
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ── 설정 ──────────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    # 원하는 RSS 피드 URL을 여기에 추가하세요
    {"name": "Hani news", "url": "http://www.hani.co.kr/rss/culture/"},
    #{"name": "Hacker News", "url": "https://news.ycombinator.com/rss"},
    #{"name": "TechCrunch",  "url": "https://techcrunch.com/feed/"},
    # {"name": "내 피드",   "url": "https://example.com/rss"},
]

# 피드당 가져올 최신 기사 수
MAX_ARTICLES_PER_FEED = 3

# 기사 본문 최대 글자 수 (Claude에게 전달)
MAX_CONTENT_CHARS = 6000

# 발송 기준: 최근 N시간 내 기사만 포함
HOURS_LOOKBACK = 25  # 약간의 여유를 두어 누락 방지


# ── 기사 수집 ─────────────────────────────────────────────────────────────────

def fetch_article_content(url: str) -> str:
    """기사 URL에서 본문 텍스트를 추출합니다."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; RSSDigestBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "iframe", "ads", "advertisement"]):
            tag.decompose()

        # 본문 후보 선택 (article > main > body 순)
        for selector in ["article", "main", '[role="main"]', ".post-content",
                          ".article-body", ".entry-content", "body"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator="\n", strip=True)
                # 연속 빈줄 정리
                text = re.sub(r"\n{3,}", "\n\n", text)
                return text[:MAX_CONTENT_CHARS]

        return soup.get_text(separator="\n", strip=True)[:MAX_CONTENT_CHARS]
    except Exception as e:
        return f"[본문 수집 실패: {e}]"


def parse_feed(feed_info: dict) -> list[dict]:
    """RSS 피드를 파싱하여 최신 기사 목록을 반환합니다."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_LOOKBACK)
    parsed = feedparser.parse(feed_info["url"])
    articles = []

    for entry in parsed.entries[:MAX_ARTICLES_PER_FEED * 2]:  # 여유 있게 가져옴
        # 발행 시간 파싱
        published = None
        for attr in ("published_parsed", "updated_parsed"):
            if hasattr(entry, attr) and getattr(entry, attr):
                import time
                published = datetime.fromtimestamp(
                    time.mktime(getattr(entry, attr)), tz=timezone.utc
                )
                break

        # 시간 필터 (발행 시간 없으면 포함)
        if published and published < cutoff:
            continue

        articles.append({
            "title":     getattr(entry, "title", "제목 없음"),
            "url":       getattr(entry, "link",  ""),
            "summary":   getattr(entry, "summary", ""),
            "published": published.strftime("%Y-%m-%d %H:%M UTC") if published else "날짜 불명",
            "feed_name": feed_info["name"],
        })

        if len(articles) >= MAX_ARTICLES_PER_FEED:
            break

    return articles


# ── 기사 포맷 ─────────────────────────────────────────────────────────────────

def analyze_article(article: dict) -> dict:
    """RSS 피드 요약 및 본문 미리보기를 포맷합니다."""
    print(f"  📖 수집 중: {article['title'][:60]}...")
    content = fetch_article_content(article["url"])

    rss_summary = article.get("summary", "").strip()
    if rss_summary:
        soup = BeautifulSoup(rss_summary, "html.parser")
        rss_summary = soup.get_text(separator=" ", strip=True)

    parts = []
    if rss_summary:
        parts.append(f"## 피드 요약\n{rss_summary[:600]}")
    if content and not content.startswith("[본문 수집 실패"):
        parts.append(f"## 본문 미리보기\n{content[:800]}")

    analysis = "\n\n".join(parts) if parts else "내용을 가져올 수 없습니다."

    return {**article, "analysis": analysis, "content_preview": content[:300]}


# ── 이메일 HTML 생성 ──────────────────────────────────────────────────────────

def build_html_email(analyzed_articles: list[dict], date_str: str) -> str:
    """분석 결과를 HTML 이메일로 포맷합니다."""

    def format_analysis(text: str) -> str:
        """마크다운 스타일 텍스트를 HTML로 변환."""
        lines = text.strip().split("\n")
        html_lines = []
        in_list = False
        for line in lines:
            if line.startswith("## "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f'<h3 style="color:#1a1a2e;margin:16px 0 8px;font-size:14px;">{line[3:]}</h3>')
            elif line.startswith("- "):
                if not in_list:
                    html_lines.append('<ul style="margin:4px 0 8px 20px;padding:0;">')
                    in_list = True
                html_lines.append(f'<li style="margin-bottom:4px;">{line[2:]}</li>')
            else:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                if line.strip():
                    html_lines.append(f'<p style="margin:4px 0;">{line}</p>')
        if in_list:
            html_lines.append("</ul>")
        return "\n".join(html_lines)

    # 피드별 그룹핑
    feeds: dict[str, list] = {}
    for art in analyzed_articles:
        feeds.setdefault(art["feed_name"], []).append(art)

    articles_html = ""
    for feed_name, arts in feeds.items():
        articles_html += f"""
        <div style="margin-bottom:8px;">
          <h2 style="font-size:18px;color:#16213e;border-bottom:2px solid #e94560;
                     padding-bottom:8px;margin:32px 0 16px;">{feed_name}</h2>
        """
        for i, art in enumerate(arts):
            importance_color = {"높음": "#e94560", "중간": "#f5a623", "낮음": "#4caf50"}.get(
                "높음" if "높음" in art["analysis"] else
                "중간" if "중간" in art["analysis"] else "낮음", "#888"
            )
            articles_html += f"""
          <div style="background:#fff;border-radius:12px;padding:24px;
                      margin-bottom:20px;border:1px solid #eee;
                      box-shadow:0 2px 8px rgba(0,0,0,0.06);">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
              <h3 style="margin:0 0 8px;font-size:17px;line-height:1.4;color:#1a1a2e;flex:1;">
                <a href="{art['url']}" style="color:#1a1a2e;text-decoration:none;"
                   target="_blank">{art['title']}</a>
              </h3>
            </div>
            <div style="font-size:12px;color:#888;margin-bottom:16px;">
              📅 {art['published']} &nbsp;|&nbsp;
              <a href="{art['url']}" style="color:#e94560;text-decoration:none;" target="_blank">원문 보기 →</a>
            </div>
            <div style="font-size:14px;color:#333;line-height:1.7;">
              {format_analysis(art['analysis'])}
            </div>
          </div>
            """
        articles_html += "</div>"

    total = len(analyzed_articles)
    feed_count = len(feeds)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>RSS 뉴스 다이제스트 - {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Apple SD Gothic Neo',
             -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:680px;margin:0 auto;padding:20px;">

    <!-- 헤더 -->
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
                border-radius:16px;padding:36px 32px;margin-bottom:24px;color:#fff;">
      <div style="font-size:11px;letter-spacing:3px;text-transform:uppercase;
                  color:#e94560;margin-bottom:12px;">DAILY DIGEST</div>
      <h1 style="margin:0 0 8px;font-size:28px;font-weight:700;">📰 오늘의 뉴스 분석</h1>
      <p style="margin:0;color:#a0aec0;font-size:14px;">{date_str} &nbsp;|&nbsp;
         {feed_count}개 피드 &nbsp;|&nbsp; {total}개 기사</p>
    </div>

    <!-- 기사 목록 -->
    {articles_html}

    <!-- 푸터 -->
    <div style="text-align:center;padding:24px;color:#aaa;font-size:12px;">
      <p style="margin:0;">📡 RSS 뉴스 다이제스트</p>
      <p style="margin:4px 0 0;">자동 생성 · {date_str}</p>
    </div>

  </div>
</body>
</html>"""


# ── 이메일 발송 ───────────────────────────────────────────────────────────────

def send_email(html_body: str, date_str: str):
    """Gmail SMTP를 통해 이메일을 발송합니다."""
    smtp_host     = os.environ["SMTP_HOST"]          # smtp.gmail.com
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user     = os.environ["SMTP_USER"]          # your@gmail.com
    smtp_password = os.environ["SMTP_PASSWORD"]      # Gmail App Password
    to_email      = os.environ["TO_EMAIL"]           # 수신자 이메일
    from_name     = os.environ.get("FROM_NAME", "RSS Digest Bot")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📰 오늘의 뉴스 다이제스트 - {date_str}"
    msg["From"]    = f"{from_name} <{smtp_user}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_string())

    print(f"✅ 이메일 발송 완료 → {to_email}")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    date_str = datetime.now(timezone.utc).strftime("%Y년 %m월 %d일")
    print(f"\n🚀 RSS 다이제스트 시작 ({date_str})\n")

    all_articles = []
    for feed in RSS_FEEDS:
        print(f"📡 피드 수집: {feed['name']}")
        articles = parse_feed(feed)
        print(f"   {len(articles)}개 기사 발견")
        all_articles.extend(articles)

    if not all_articles:
        print("⚠️  수집된 기사가 없습니다. 종료합니다.")
        return

    print(f"\n📄 총 {len(all_articles)}개 기사 처리 시작...\n")
    analyzed = [analyze_article(art) for art in all_articles]

    html = build_html_email(analyzed, date_str)

    # HTML 파일로도 저장 (디버깅용)
    with open("digest_preview.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("💾 digest_preview.html 저장 완료")

    send_email(html, date_str)


if __name__ == "__main__":
    main()
