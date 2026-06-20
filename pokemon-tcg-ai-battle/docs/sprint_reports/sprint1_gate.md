# Sprint 1 ゲート結果（高速自己対戦基盤）

日付: 2026-06-20 / ブランチ: `claude/nifty-albattani-4mgg7m`

## 自動判定（DoD）— PASS ✅

| 検証 | コマンド | 結果 |
|---|---|---|
| 特徴量・バッファ・収集・並列・評価 | `python3 tests/test_selfplay.py` | **5/5 PASS** |
| 回帰（0A ライフサイクル） | `python3 tests/test_lifecycle.py` | 6/6 PASS |

### スループット / 安定性
```
単コア collect_game:     ~113 games/sec（featurize 込み）
並列 parallel_selfplay:  40ゲーム/4worker, crashes=0, finished=40, ~124 games/sec
  （spawn 起動オーバヘッド込み。長時間ほど線形に伸びる）
samples 収集:            40ゲームで 1724 サンプル
メモリ:                  worker は maxtasksperchild=1 で再生成しネイティブリークを抑止
```

- DoD「1コアで毎秒N対戦の安定動作・リークなし」を満たす（113 games/sec、crashes 0）。
- 報酬 z は手番プレイヤー視点で ±1/0（`result_to_z`）。policy ターゲットは暫定で
  「選択した先頭 index」（Sprint 2 で visit-count 分布 π に置換）。

## 成果物
- `model/features.py`（FEATURE_DIM=37: global9 + 自分14 + 相手14）
- `selfplay/replay_buffer.py`（npz 保存/読込、ring capacity）
- `selfplay/actor.py`（`collect_game` / `parallel_selfplay` spawn 並列）
- `eval/cabt_eval.py`（席交代の勝率評価）

## 次（Sprint 2）
`search_begin` を前向きモデルにした決定化 MCTS（PIMC→ISMCTS）＋時間予算マネージャ。
土台ルールに勝ち越し＋手番消費が予算内、を閾値とする。
