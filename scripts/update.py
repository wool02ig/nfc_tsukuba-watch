#!/usr/bin/env python3
"""Collect public RSS/Atom feeds for NFC TSUKUBA WATCH."""
import hashlib
import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'tsukuba.json'
JST = timezone(timedelta(hours=9))
NOW = datetime.now(timezone.utc)
MAX_ARTICLES = 500
MAX_AGE_DAYS = 90
HEADERS = {'User-Agent': 'NFC-Tsukuba-Watch/1.0 (public RSS reader; contact via repository)', 'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*'}

SEARCHES = [
    ('つくば市 ニュース', '地域ニュース'),
    ('つくば市 新店舗 開店 閉店', '店舗・グルメ'),
    ('つくば市 再開発 建設 商業施設', '開発・建設'),
    ('つくば市 イベント 祭り 週末', 'イベント'),
    ('つくば市 交通 つくばエクスプレス 道路', '交通・生活'),
    ('つくば市 防災 災害 警報', '防災・安全'),
    ('つくば市 研究学園 みどりの 万博記念公園 陣場', '地域ニュース'),
]
SOURCES = [{'name': 'つくば市公式', 'url': 'https://www.city.tsukuba.lg.jp/cgi-bin/feed.php', 'type': 'official', 'defaultCategory': '行政・市政'}]
for term, category in SEARCHES:
    SOURCES.append({'name': f'ニュース検索：{term}', 'url': f'https://news.google.com/rss/search?q={quote(term)}&hl=ja&gl=JP&ceid=JP:ja', 'type': 'news', 'defaultCategory': category})

CATEGORIES = [
    ('防災・安全', ['避難', '地震', '防災', '警報', '災害', '洪水', '不審者', '停電', '火災', '台風']),
    ('開発・建設', ['再開発', '建設', '造成', '区画整理', '開発計画', '工事', '都市計画', '商業施設', '新駅']),
    ('店舗・グルメ', ['開店', '閉店', 'オープン', '新店舗', '出店', '飲食店', 'カフェ', 'スーパー', 'レストラン', 'ラーメン', 'グルメ']),
    ('交通・生活', ['交通規制', '通行止め', '鉄道', 'つくばエクスプレス', 'バス', '道路', '渋滞', '運休', 'TX', '上下水道']),
    ('イベント', ['イベント', '祭り', 'フェス', '展覧会', 'マルシェ', '開催', '講演会', '体験会', '募集', '企画展']),
    ('行政・市政', ['市議会', '条例', '市役所', '市政', '公募', '補助金', '入札', '市長', '予算']),
]
AREAS = [
    ('研究学園', ['研究学園', '学園の森', '学園南']),
    ('みどりの', ['みどりの', 'みどりの中央', 'みどりの南', '谷田部']),
    ('万博記念公園', ['万博記念公園', '島名', '香取台']),
    ('陣場', ['陣場']),
    ('つくば駅周辺', ['つくば駅', '吾妻', '竹園', '中央公園', 'つくばセンター']),
    ('筑波山', ['筑波山', '筑波山神社', 'つつじヶ丘']),
    ('大穂・豊里', ['大穂', '豊里', '筑穂']),
    ('桜・テクノパーク', ['テクノパーク桜', '桜地区', '天久保']),
]

def plain(value):
    value = re.sub(r'<[^>]*>', ' ', value or '')
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()

def canonical(url):
    parts = urlsplit(url.strip())
    if parts.scheme not in ('https', 'http') or not parts.netloc:
        return ''
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not k.startswith('utm_') and k not in ('fbclid', 'gclid')])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/') or '/', query, ''))

def parse_date(entry):
    for field in ('published_parsed', 'updated_parsed'):
        value = entry.get(field)
        if value:
            try:
                from calendar import timegm
                return datetime.fromtimestamp(timegm(value), tz=timezone.utc)
            except (ValueError, TypeError, OverflowError):
                pass
    return None

def classify(text, fallback):
    for category, words in CATEGORIES:
        if any(word.lower() in text.lower() for word in words):
            return category
    return fallback

def identify_areas(text):
    return [area for area, words in AREAS if any(w.lower() in text.lower() for w in words)]

def load_previous():
    try:
        return json.loads(OUT.read_text(encoding='utf-8')).get('articles', [])
    except (OSError, ValueError):
        return []

def collect():
    existing = load_previous()
    found = {}
    status = []
    for source in SOURCES:
        try:
            response = requests.get(source['url'], headers=HEADERS, timeout=22)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            if not feed.entries and feed.bozo:
                raise ValueError(str(feed.bozo_exception))
            count = 0
            for entry in feed.entries[:100]:
                title = plain(entry.get('title', ''))[:220]
                url = canonical(entry.get('link', ''))
                if not title or not url:
                    continue
                published = parse_date(entry)
                if published and (published > NOW + timedelta(days=2) or published < NOW - timedelta(days=MAX_AGE_DAYS)):
                    continue
                summary = plain(entry.get('summary', entry.get('description', '')))[:340]
                text = title + ' ' + summary
                # The municipal feed is intrinsically local; news searches can have false matches.
                if source['type'] == 'news' and not any(k in text.lower() for k in ('つくば', '筑波', 'tsukuba', '研究学園', 'みどりの', '陣場')):
                    continue
                key = hashlib.sha256(url.encode('utf-8')).hexdigest()[:20]
                article = {
                    'id': key,
                    'title': title,
                    'url': url,
                    'summary': summary,
                    'category': classify(text, source['defaultCategory']),
                    'areas': identify_areas(text),
                    'source': plain(entry.get('source', {}).get('title', '')) or source['name'],
                    'sourceType': source['type'],
                    'publishedAt': published.isoformat() if published else None,
                    'firstSeenAt': NOW.isoformat(),
                }
                found[key] = article
                count += 1
            status.append({'source': source['name'], 'ok': True, 'count': count})
            logging.info('%s: %d articles', source['name'], count)
        except (requests.RequestException, ValueError, Exception) as exc:
            logging.warning('Failed %s: %s', source['name'], exc)
            status.append({'source': source['name'], 'ok': False, 'count': 0, 'error': str(exc)[:120]})
    for item in existing:
        if not isinstance(item, dict) or not item.get('id'):
            continue
        if item['id'] in found:
            found[item['id']]['firstSeenAt'] = item.get('firstSeenAt') or NOW.isoformat()
        else:
            found[item['id']] = item
    limit = NOW - timedelta(days=MAX_AGE_DAYS)
    articles = []
    for item in found.values():
        try:
            d = datetime.fromisoformat(item.get('publishedAt') or item.get('firstSeenAt'))
            if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
            if d < limit: continue
            articles.append(item)
        except (ValueError, TypeError):
            continue
    articles.sort(key=lambda a: a.get('publishedAt') or a.get('firstSeenAt') or '', reverse=True)
    if not any(s['ok'] for s in status) and existing:
        logging.error('All sources unavailable; preserving existing data.')
        return 1
    output = {'version': 1, 'updatedAt': NOW.isoformat(), 'articleCount': min(len(articles), MAX_ARTICLES), 'sources': status, 'articles': articles[:MAX_ARTICLES]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    logging.info('Saved %d articles', output['articleCount'])
    return 0

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    raise SystemExit(collect())
