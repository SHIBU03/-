# 作業進捗・再開ガイド（PROGRESS / RESUME）

> このファイルは「トークンが切れても作業を途中から再開できる」ためのもの。
> **各コミットの直後にこのファイルを更新する**。再開時はまずこのファイルを読むこと。

最終更新: 2026-06-20 / 作業ブランチ: `claude/nifty-albattani-4mgg7m`
**現在地**: Sprint 0〜3 すべて完了（仮想空間の5層が一通り動作）。テスト 20/20 PASS。
提出 agent=決定化探索（dev/本番env で search 動作、対 random ~81%）。value net は self-play から
学習（val_mse<baseline）し NN誘導MCTS に接続可。リーグ/PFSP 雛形あり。
Playwright ブラウザ目視のみ環境制約で保留（chromium egress 403）。
**次の発展**: NN のバンドル安全化（pure-python forward）＋ value-guided 提出、リーグ自己対戦の本格運用、
本番ラダー A/B（PLAN 方針）。

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

### Sprint 0B — 公式ランナー確保＋提出パイプライン ✅ 完了
- [x] `kaggle-environments==1.30.1` 導入（`--ignore-installed blinker`）。**`make("cabt")` は同梱で利用可**（別途 DL 不要）
- [x] `env/kaggle_runner.py`（make("cabt")+env.run ラッパー、1ゲーム完走確認）
- [x] `requirements.lock`
- [x] `tools/validate_deck.py`（60枚・cardId存在・4枚制限・ACE SPEC）→ 既存デッキ VALID
- [x] `tools/make_submission.sh`（main.py+deck.csv+agent/+cg/ を tar、`__pycache__` 除外）
- [x] `tools/smoke_submission.py`（展開→自己完結で1ゲーム完走）→ SMOKE PASS
- [x] コミット＆プッシュ

### 可視化インフラ（0A/0B 共通）✅ 完了（Playwright目視のみ保留）
- [x] `viz/server.py`（start/step/auto/metrics、BattleSession 経由）
- [x] `viz/index.html` + `app.js` + `style.css`（盤面・操作・計測パネル）
- [x] `tools/run_viz.sh` / `tools/viz_gate.py`（自動ゲート）
- [x] `.mcp.json`（Playwright MCP 設定、`@playwright/mcp` 起動確認済み）
- [~] Playwright MCP 接続 ＋ chromium 導入 → **保留**: chromium DL が egress 403
      （`cdn.playwright.dev` 非許可）＋ MCP は要セッション再起動。手順は sprint0_gate.md。
- [x] スプリント末ゲート（Auto 100、クラッシュ0/リーク0）→ HTTP自動ゲートで **PASS**
- [x] コミット＆プッシュ

### Sprint 1 — 高速自己対戦基盤 ✅ 完了
- [x] `model/features.py`: `featurize(obs)` → 固定長 float32（FEATURE_DIM=37）
- [x] `selfplay/replay_buffer.py`: ReplayBuffer（add/sample/save/load・z 算出）
- [x] `selfplay/actor.py`: `collect_game` ＋ `parallel_selfplay`（spawn 並列・worker 再生成）
- [x] `eval/cabt_eval.py`: 席交代の head-to-head 勝率評価
- [x] `tests/test_selfplay.py`: 5/5 PASS。並列40ゲーム crashes=0、単コア ~113 games/sec
- [x] コミット＆プッシュ

### Sprint 2 — 決定化探索（PIMC）✅ 完了
- [x] `sample_submission/agent/base.py`（バンドル安全な read_deck/random_agent、env非依存）
- [x] `sample_submission/agent/determinize.py`（hidden info を決定化、count 整合）
- [x] `sample_submission/agent/time_budget.py`（600s 予算・手番 soft deadline）
- [x] `sample_submission/agent/mcts.py`（UCB1 フラットMC×決定化、search_begin 前向きモデル）
- [x] `sample_submission/main.py`: 提出 agent を MCTS 化（safe_agent ＋ 予算リセット）
- [x] `tests/test_search.py`: 4/4 PASS（対 random 81%）。本番 env でも search 動作（sb_ok 全件）
- [x] バグ修正: repo直下 `agent/` 衝突を解消（`sample_submission/agent/` に集約）
- [x] コミット＆プッシュ

### Sprint 3 — 学習＋リーグ ✅ 完了（コア）
- [x] `model/network.py`（numpy MLP ValueNet：train/predict/save_json/load_json、手書きBP）
- [x] `model/features.py`：dict/dataclass 両対応に refactor ＋ `featurize_search_obs`
- [x] `selfplay/learner.py`（collect→train_value→make_value_fn）。self-play で val_mse<baseline 学習
- [x] `agent/mcts.py`：`value_fn` で葉評価を NN 置換可（既定はヒューリスティック＝バンドル安全）
- [x] `league/pfsp.py`＋`league/league.py`（PFSP 重み・ModelPool 雛形）
- [x] `tests/test_learn.py`: 5/5 PASS（ValueNet 学習・NN誘導MCTS合法・PFSP・pool）
- [x] コミット＆プッシュ

### 発展課題（今後）
- [ ] NN を pure-python forward に書き出し submission へ（value-guided 提出）
- [ ] policy ターゲット（visit-count π）収集 ＋ policy head（PUCT 化）
- [ ] リーグ自己対戦の本格運用（main/exploiter・定期リセット）
- [ ] 本番ラダー A/B（μ で採否、PLAN 方針）
- [ ] Playwright ブラウザ目視（egress 許可 or ローカルで）

---

## 2.5 対局を見る（ブラウザ不要・MCP代替）
- `python3 tools/record_game.py game_replay.html <seed>` → 実戦を録画した自己完結HTMLを生成。
  ブラウザで開くと1手ずつ/自動再生で対戦を観戦できる（Playwright MCP のブラウザ目視が
  egress 制約で不可なための代替。MCP 自体は接続済み）。

## 3. よく使うコマンド

```bash
cd pokemon-tcg-ai-battle
python3 tests/test_lifecycle.py     # 0A 回帰テスト
bash tools/run_viz.sh               # 可視化サーバ（実装後）
bash tools/make_submission.sh       # 提出物作成（実装後）
```

## 4. 既知の事実（再掲）
- クラッシュ根因: `cg/game.py:battle_finish()` が `Battle.battle_ptr` を戻さず、ネイティブが NULL/解放済みを無防備に参照 → use-after-free/double-free/segfault。対策＝`BattleSession` で alive ガード。
- `kaggle-environments==1.30.1` を導入すれば **`make("cabt")` は同梱で利用可**（要 `--ignore-installed blinker`）。cabt 環境はエージェントの最初の行動で 60 枚デッキを受け取り、報酬は win=1/lose=-1/draw=0、各プレイヤー 600 秒の overage。
- 並列はプロセス分離必須（`battle_ptr`/`agent_ptr` はプロセス共有シングルトン）。
