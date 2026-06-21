# Sprint 3 ゲート結果（学習＋リーグ・コア）

日付: 2026-06-21 / ブランチ: `claude/nifty-albattani-4mgg7m`

## 自動判定（DoD・ローカル代理）— PASS ✅

| 検証 | コマンド | 結果 |
|---|---|---|
| ValueNet 学習・NN誘導MCTS・PFSP・pool | `python3 tests/test_learn.py` | **5/5 PASS** |
| 全回帰（lifecycle/selfplay/search/learn） | 4ファイル | **20/20 PASS** |
| 提出バンドル（numpy非依存・スモーク） | make_submission + smoke | PASS（bundle-safe） |

### 学習が効いている証拠（self-play 40 ゲーム → ValueNet）
```
n=1696 samples
epoch0_mse=0.922 -> epochN_mse=0.720   (訓練で損失低下)
val_mse=0.818  <  val_baseline_mse=0.998   (平均予測より ~18% 改善 = 学習成立)
```
- value ターゲット z = 手番プレイヤー視点の最終勝敗（±1/0）。AlphaZero の価値学習骨格。

## 成果物
- `model/network.py`: numpy MLP ValueNet（37→64→1, tanh, 手書き誤差逆伝播, JSON 保存）。
- `model/features.py`: dict/dataclass 両対応に refactor、`featurize_search_obs`（MCTS 葉用）。
- `selfplay/learner.py`: `collect_dataset`→`train_value`→`make_value_fn`。
- `agent/mcts.py`: `value_fn` 引数で葉評価を NN に差し替え可（既定ヒューリスティック＝バンドル安全）。
- `league/pfsp.py`・`league/league.py`: PFSP 重み付けと ModelPool（autocurriculum 雛形）。

## スコープと今後
- 本スプリントは **価値学習ループ ＋ NN誘導MCTS 接続 ＋ リーグ/PFSP 雛形** を確立（コア）。
- 今後: NN の pure-python 化で submission にも value-guided を載せる／policy head（visit-π, PUCT）／
  リーグ自己対戦の本格運用／**本番ラダー A/B でμ採否**（最終判断は本番、PLAN 方針）。
- 強さの最終評価はローカル代理に留まる点に注意（PLAN の「本番が真実」）。

## 仮想空間の到達点（Sprint 0–3）
環境層（安全 Game/Search API ラッパー）→ 自己対戦層（並列アクター＋replay）→ エージェント層
（決定化探索 PIMC）→ 学習層（value net）→ リーグ層（PFSP 雛形）＋ 評価層（head-to-head）＋
可視化（Web＋自動ゲート）。**無クラッシュ・無リーク**で一貫動作。
