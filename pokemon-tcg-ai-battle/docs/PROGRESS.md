# 作業進捗・再開ガイド（PROGRESS / RESUME）

> このファイルは「トークンが切れても作業を途中から再開できる」ためのもの。
> **各コミットの直後にこのファイルを更新する**。再開時はまずこのファイルを読むこと。

最終更新: 2026-06-20 / 作業ブランチ: `claude/nifty-albattani-4mgg7m`
**現在地**: Sprint 0A 完了（テスト 6/6 PASS）。次は Sprint 0B（公式ランナー＋提出パイプライン）。

---

## 0. ゴール

ポケカ AI Battle Challenge（cabt エンジン）優勝のための **自己対戦・学習基盤（仮想空間）** を作る。
設計は `docs/PLAN_v1.2.md`（Sprint 0A/0B 詳細）・`docs/PLAN_v1.1.md`（全体）に従う。

---

## 1. 再開のしかた（途中から続ける手順）

```bash
# 1) 最新を取得
cd <repo>
git fetch origin claude/nifty-albattani-4mgg7m
git checkout claude/nifty-albattani-4mgg7m
git pull origin claude/nifty-albattani-4mgg7m

# 2) この進捗ファイルを読む（次にやる項目＝最初の [ ] 未チェック）
sed -n '1,200p' pokemon-tcg-ai-battle/docs/PROGRESS.md

# 3) 現状が壊れていないか検証（Sprint 0A 完了後はこれが通るはず）
cd pokemon-tcg-ai-battle
python3 tests/test_lifecycle.py        # 全 PASS で exit 0

# 4) 次の未チェック項目から実装を続ける
```

- **方針**: 1 タスクごとに実装 → テスト → `git commit` → `git push -u origin claude/nifty-albattani-4mgg7m` → 本ファイルの該当項目を `[x]` に更新。
- コミットメッセージ末尾には Co-Authored-By / Claude-Session トレーラを付ける。
- push が 403 等で失敗したら時間をおいて再試行（プロキシ過渡状態のことがある）。

---

## 2. 進捗チェックリスト

### Sprint 0A — クラッシュ恒久対策＋安全土台 ✅ 完了
- [x] `env/game_api.py`: `BattleSession`（alive ガード・冪等 finish・1プロセス1セッション）＋ self-play ヘルパ
- [x] `sample_submission/agent/safety.py`: `normalize_selection` / `legal_fallback` / `safe_agent`
- [x] `sample_submission/main.py`: `safe_agent` でラップ＋堅牢な deck 読込
- [x] `tests/test_lifecycle.py`: B1/B2/D1 回帰 ＋ 200ゲーム自己対戦 ＋ fuzz ＋ メモリリーク検査
- [x] テスト全 PASS（6/6・クラッシュ 0・リーク 0）
- [x] コミット＆プッシュ

### Sprint 0B — 公式ランナー確保＋提出パイプライン
- [ ] `kaggle-environments==1.30.1` 導入試行 ＋ `make("cabt")` 可否確認（不可なら代替明記）
- [ ] `requirements.lock`
- [ ] `tools/validate_deck.py`（60枚・cardId存在・4枚制限・ACE SPEC）
- [ ] `tools/make_submission.sh`（main.py+deck.csv+agent/+cg/ を tar）
- [ ] 提出スモークテスト（展開→1ゲーム完走）
- [ ] コミット＆プッシュ

### 可視化インフラ（0A/0B 共通）
- [ ] `viz/server.py`（start/step/auto/metrics）
- [ ] `viz/index.html` + `app.js` + `style.css`（盤面・操作・計測）
- [ ] `tools/run_viz.sh`
- [ ] `.mcp.json`（Playwright MCP）
- [ ] Playwright MCP 接続 ＋ chromium 導入（ネットワークポリシー許可が前提）
- [ ] スプリント末ゲート（Auto 100、クラッシュ0/リーク0 を確認）
- [ ] コミット＆プッシュ

### Sprint 1〜3
- [ ] 未着手（`docs/PLAN_v1.2.md` §6 / `PLAN_v1.1.md` を参照）

---

## 3. よく使うコマンド

```bash
cd pokemon-tcg-ai-battle
python3 tests/test_lifecycle.py     # 0A 回帰テスト
bash tools/run_viz.sh               # 可視化サーバ（実装後）
bash tools/make_submission.sh       # 提出物作成（実装後）
```

## 4. 既知の事実（再掲）
- クラッシュ根因: `cg/game.py:battle_finish()` が `Battle.battle_ptr` を戻さず、ネイティブが NULL/解放済みを無防備に参照 → use-after-free/double-free/segfault。対策＝`BattleSession` で alive ガード。
- `kaggle_environments` 未導入。`make("cabt")` は競技専用環境で pip だけでは入らない可能性。
- 並列はプロセス分離必須（`battle_ptr`/`agent_ptr` はプロセス共有シングルトン）。
