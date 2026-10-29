# NFC TSUKUBA WATCH v1.0

つくば市の行政・ニュース・店舗・開発・イベント・交通・防災情報を公開RSSから集約する、静的なGitHub Pagesサイト。

## セットアップ

1. GitHubに新しい公開リポジトリ（例：`nfc-tsukuba-watch`）を作成する。
2. このフォルダの**中身すべて**（隠しフォルダ `.github` と `.nojekyll` も）をリポジトリのルートにアップロードする。
3. リポジトリの **Settings → Pages → Build and deployment → Deploy from a branch → main / (root)** を選択して保存する。
4. **Actions → Update TSUKUBA WATCH → Run workflow** を手動実行する（初回は記事0件）。
5. Actionsが成功すると `data/tsukuba.json` が更新され、Pages上の記事が表示される。
6. 自動更新は日本時間 **00:17 / 06:17 / 12:17 / 18:17** の計4回。GitHub側の混雑等で予定時刻から遅れる場合がある。

## ファイル構成

- `index.html`: 単一ファイルのレスポンシブUI。記事表示、検索、カテゴリ・地区別フィルター、既読（ブラウザ内localStorage）、リンク。
- `scripts/update.py`: 公開RSS/Atomを取得し分類、重複排除、過去記事を保持、最大500件・90日保存。
- `requirements.txt`: Python依存ライブラリ。
- `.github/workflows/update-tsukuba.yml`: 定期・手動収集と自動コミット。
- `data/tsukuba.json`: 配信データ。初期は空。
- `.nojekyll`: Pages用。

## ソースと制約

- つくば市公式RSS: `https://www.city.tsukuba.lg.jp/cgi-bin/feed.php`
- Google ニュース検索RSS: ニュース / 店舗 / 開発 / イベント / 交通 / 防災 / 地区別。
- X / Instagram の投稿本文は自動収集しない。検索リンクのみ。APIキーを使う拡張は別途実装する。
- ニュース検索RSSは非公式のAPI仕様に依存しており、取得不能になる場合がある。
- 記事本文は転載せず、短い概要と元記事リンクを表示。
- 地区・カテゴリ判定はキーワードベースで誤判定の可能性がある。
- 同じ話題でも異なる記事URLなら個別掲載される（URL単位での重複排除）。
- 記事をクリックするとブラウザごとの既読に保存する。他端末とは同期しない。
- Google News側のRSSリンクはGoogle News経由で開かれる場合がある。

## 手元で収集を試す

```bash
python -m pip install -r requirements.txt
python scripts/update.py
python -m http.server 8000
```

`http://localhost:8000` を開く。単にindex.htmlを直接ダブルクリックする場合、ブラウザの制約でJSONの取得が失敗する場合がある。

## 監視と変更

`SEARCHES`（`scripts/update.py`）で検索キーワードとフォールバックカテゴリを変更可能。失敗した情報源はページの DATA STATUS に表示される。

## セキュリティ

外部HTMLを画面に流し込まず `textContent` により表示。GitHub Actionsはリポジトリのcontents書き込み権限のみ。外部APIキー不要。運用時はリポジトリのActions権限/ブランチ保護を適宜確認。
