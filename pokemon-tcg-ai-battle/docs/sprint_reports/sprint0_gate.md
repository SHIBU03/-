# Sprint 0 デバッグ・ゲート結果（0A + 0B + 可視化）

日付: 2026-06-20 / ブランチ: `claude/nifty-albattani-4mgg7m`

## 自動判定（DoD）— すべて PASS ✅

| 検証 | コマンド | 結果 |
|---|---|---|
| ライフサイクル回帰（B1/B2/D1） | `python3 tests/test_lifecycle.py` | **6/6 PASS**（SIGABRT/Segfault 0） |
| 200ゲーム自己対戦＋リーク | （同上に内包） | error 0 / RSS 安定 |
| デッキ妥当性 | `python3 tools/validate_deck.py` | VALID（60枚） |
| 提出パッケージ | `bash tools/make_submission.sh` | tar 構成 OK |
| 提出スモーク（自己完結1ゲーム） | `python3 tools/smoke_submission.py` | SMOKE PASS（108手） |
| 公式ランナー | `python3 -m env.kaggle_runner` | env.run 完走（done=True） |
| **可視化ゲート（Auto 100）** | `python3 tools/viz_gate.py 100` | **GATE PASS** |

### 可視化ゲート メトリクス（Auto 100ゲーム）
```
crashes=0  finished=100/100  p0/p1/draw=50/50/0
rss_start=28.9MB -> rss_now=30.4MB (growth=1.5MB, no leak)
max_move_ms=0.7  total_moves=5501  elapsed=1.7s
```

### 盤面スナップショット（テキスト・フォールバック / `/api/state`）
turn=2, yourIndex=0, result=-1（進行中）。カード名解決つきで描画確認:
- P1 active: Snover#722 HP90/90 ⚡1 / hand5 prize6 deck46
- P0 active: Snover#722 HP90/90 ⚡0, bench[Snover#722] / hand6 prize6 deck46

→ ビジュアライザの盤面・手札・サイド・デッキ・状態異常の描画が正常。

## Playwright MCP ブラウザ目視 — 接続済み・ブラウザ取得のみ環境制約

切り分け結果（後日セッションで実機確認）:
- **Playwright MCP は Claude に接続済み**（`mcp__playwright__*` ツール利用可）。`.mcp.json` が読込まれた。
- `mcp__playwright__browser_navigate("http://127.0.0.1:8022")` を実行 →
  エラー `Browser "chrome-for-testing" is not installed`。
- ブラウザ導入を再試行（`npx @playwright/mcp install-browser chrome-for-testing` /
  `npx playwright install chromium`）→ いずれも **egress 403**:
  `Host not in allowlist: cdn.playwright.dev`。
- 結論: **唯一の不足はブラウザ・バイナリのダウンロード**（MCP 接続・サーバ・操作系は揃っている）。
  計画 §5.3 で想定したリスクそのもの。

### ブラウザ目視を有効化する手順（次回 or ローカル）
1. ネットワークegress設定で `cdn.playwright.dev`（と `*.playwright.dev`）を許可、
   または **ローカルのデスクトップ版 Claude Code** で実施。
2. `npx playwright install chromium` でブラウザ導入。
3. Claude セッションを再起動して `.mcp.json` の playwright MCP を読込。
4. `bash tools/run_viz.sh` で起動 → Playwright MCP で `http://127.0.0.1:8000` を開き、
   Start/Step/Auto を操作してスクショ。判定は本書「自動判定」と同じ DoD。

## 結論
仮想空間（自己対戦＋安全土台＋公式ランナー＋可視化）は**無クラッシュ・無リークで動作**し、
DoD の自動判定をすべて満たす。Playwright のブラウザ目視のみ環境制約で保留（フォールバックの
HTTP自動ゲートで代替済み）。
