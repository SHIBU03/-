# Sprint 2 ゲート結果（決定化探索 PIMC）

日付: 2026-06-21 / ブランチ: `claude/nifty-albattani-4mgg7m`

## 自動判定（DoD）— PASS ✅

| 検証 | コマンド | 結果 |
|---|---|---|
| 決定化・前向きモデル・PIMC | `python3 tests/test_search.py` | **4/4 PASS** |
| 強さ（対 random, dev） | evaluate 16ゲーム | **A_winrate 0.81**（13-3） |
| 強さ（対 random, 公式env） | env.run 8ゲーム | **mcts 6 - random 2** |
| 手番時間 | 計測 | max ~93ms（予算 600s/試合に対し十分安全） |
| 本番 env で search 動作 | STATS | sims=548, **sb_ok=548, sb_err=0** |
| 回帰（lifecycle/selfplay） | 両テスト | 6/6・5/5 PASS |
| 提出（MCTS同梱）スモーク | `tools/smoke_submission.py` | SMOKE PASS |
| 可視化ゲート（Auto100, random） | `tools/viz_gate.py` | PASS（crashes=0, leak無, max_move 0.1ms） |

## 設計
- 単一選択（minCount==maxCount==1＝全 MAIN 手番）に対し、決定化×UCB1 のフラットMC。
  各シミュ: `search_begin` で決定化ワールド構築 → ルート option 適用 → ランダムロールアウト
  （depth≤24）→ ヒューリスティック評価（prize差＋HP＋ベンチ）→ UCB1 でバックプロップ。
  多選択/複雑コンテキストは base(random) にフォールバック。
- **バンドル安全**: `sample_submission/agent/`（base/determinize/time_budget/mcts/safety）に集約。
  `cg/` と agent パッケージのみ依存（dev専用 `env` に非依存）。提出 tar に同梱。
- **重要発見**: 提出 agent が同梱 cg で `search_begin` を呼んでも、公式 env が渡す
  `search_begin_input` をそのまま受理（sb_err=0）。ラダー上でも探索が機能する。
- 時間: `use_global_budget=True`＋デッキ選択フェーズで `reset_global(600)`。手番 soft deadline。

## 既知の注意
- 公式 env では「対戦＝env の cg / 探索＝同梱 cg」と二系統だが互換動作を確認（sb_err=0）。
  ただしワールド動力学の完全一致は未保証 → 強さは env 実測（6-2）で確認済み。
- 強さ評価はローカル代理。最終判断は本番ラダー A/B（PLAN 方針）。

## 次（Sprint 3）
軽量 value/policy NN を replay から学習し、探索の事前確率/葉評価を置換。リーグ＋PFSP。
