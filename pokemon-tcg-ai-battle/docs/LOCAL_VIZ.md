# ローカルで対戦をライブ観戦する（Playwright MCP × Webビジュアライザ）

クラウド版ではブラウザ・バイナリの取得が egress で不可のため、**ローカルのデスクトップ版
Claude Code** で実ブラウザ＋Playwright MCP を使って対戦を観戦する手順。

---

## 0. 前提（重要）

- **OS は Linux x64 または Windows x64**。同梱エンジンは `sample_submission/cg/libcg.so`(Linux x64)
  と `cg.dll`(Windows x64) のみで、**macOS / ARM ビルドは無い**。
  - macOS の人は **WSL2 / Linux VM / Docker（x86_64）** で実行するか、生成済みの観戦用 HTML
    （`game_replay.html`、`tools/record_game.py` で再生成可）をそのままブラウザで開く。
- 必要: `python3.11+`、`node`/`npx`（Playwright MCP 用）、デスクトップ版 Claude Code。
- viz サーバ自体は **Python 標準ライブラリ＋同梱 cg のみ**で動く（numpy 不要。numpy はテスト/学習用）。

---

## 1. クローンしてブランチへ

```bash
git clone <この repo の URL> repo
cd repo                                   # リポジトリ直下（.mcp.json がある場所）
git checkout claude/nifty-albattani-4mgg7m
```

> `.mcp.json`（Playwright MCP 設定）は**リポジトリ直下**にある。Claude Code はこの
> ディレクトリで起動すると自動で読み込む。

## 2. ビジュアライザを起動

別ターミナルで:

```bash
cd repo/pokemon-tcg-ai-battle
bash tools/run_viz.sh            # → http://127.0.0.1:8000  (ポート変更: bash tools/run_viz.sh 9000)
```

ブラウザで直接 `http://127.0.0.1:8000` を開けば、その場で
**Start / Step / Auto-step / Auto N games** を手動操作して観戦できる（Playwright 不要）。

## 3. Playwright MCP を使う（Claude に操作させる）

1. リポジトリ直下で **デスクトップ版 Claude Code を起動**（`.mcp.json` が読まれ playwright MCP が接続）。
2. 初回のみブラウザ導入:
   ```bash
   npx playwright install chromium
   ```
3. **見えるウィンドウで観たい場合**は `.mcp.json` の playwright 引数から `--headless` を外す:
   ```json
   { "mcpServers": { "playwright": {
       "command": "npx",
       "args": ["-y", "@playwright/mcp@latest", "--browser", "chromium"]
   } } }
   ```
   （既定は headless。その場合は Claude がスクショを取って見せる。）変更後は Claude を再起動。
4. Claude にこう頼む:
   > 「Playwright MCP で http://127.0.0.1:8000 を開いて、Start を押して Auto-step で対戦を進め、
   > 盤面のスクリーンショットを撮って」
   - 使うツール: `browser_navigate` → `browser_click`（Start / Auto-step）→ `browser_take_screenshot` / `browser_snapshot`。
   - 「Auto N games」を押すと N 戦のメトリクス（crashes/finished/勝敗/手番時間/メモリ）が出る。

## 4. 健全性チェック（ブラウザ無しの自動ゲート）

```bash
cd repo/pokemon-tcg-ai-battle
python3 tools/viz_gate.py 50          # サーバへ HTTP。crashes=0 / finished=50 なら GATE PASS
```

## 5. ブラウザを使わずに観戦用 HTML を作る（代替）

```bash
cd repo/pokemon-tcg-ai-battle
python3 tools/record_game.py game_replay.html 0      # 任意の seed
# 出力された game_replay.html をブラウザで開く（▶Play / Prev / Next）
```

---

## トラブルシュート

- **`Browser ... is not installed`**: `npx playwright install chromium` を実行（ローカル回線なら通る）。
- **`ModuleNotFoundError: cg` 等**: `repo/pokemon-tcg-ai-battle` で `tools/run_viz.sh` を起動しているか確認
  （サーバが `sample_submission` を import パスに追加する）。
- **macOS で `libcg` ロード失敗**: 前提どおり mac ネイティブ非対応。WSL2/Linux/Docker を使う。
- **MCP が見えない**: Claude Code を**リポジトリ直下**（`.mcp.json` のある場所）で起動し直す。
- **強い AI 同士を観たい**: `tools/record_game.py` を編集して `a1 = make_mcts_agent(...)` にする、
  または viz の agent セレクタで `main`（=MCTS）を選ぶ。

## 参考
- ビジュアライザ実装: `viz/server.py`, `viz/index.html`, `viz/app.js`
- 観戦用録画: `tools/record_game.py`
- 自動ゲート: `tools/viz_gate.py`
- 進捗・再開: `docs/PROGRESS.md`
