# PC で学習を回す（自己対戦学習 ＋ デッキ自動探索 QD）

CPU だけで回せます（**GPU 不要**）。前提は `docs/LOCAL_VIZ.md` と同じ（**Linux/Windows x64**、
`cg` は mac ネイティブ非対応 → mac は WSL2/Docker）。`numpy` は価値ネット学習にのみ必要。

```bash
cd repo/pokemon-tcg-ai-battle
pip install numpy        # 価値ネット/サロゲート学習用（QD のデッキ探索だけなら不要）
```

---

## 1. デッキ自動探索（MAP-Elites / Quality-Diversity）

「多様なニッチごとに最強デッキ」を進化させ、メタ再発見＋**新デッキ/新カードの発掘**を行う。
各ニッチに champion を残すので **勝率主義で1つに収束せず、弱カードも埋もれない**。

```bash
# 本番（MCTSがデッキを操作して評価。質は高いが遅い）
python -m discovery.run_qd --generations 300 --out runs/qd1

# 続きから（毎世代チェックポイント、いつでも再開可）
python -m discovery.run_qd --generations 300 --out runs/qd1 --resume

# 高速スモーク（ランダム操作・少試合。動作確認用）
python -m discovery.run_qd --generations 50 --pilot random --n-games 2 --out runs/smoke
```

**主なオプション**: `--generations N` 世代数 / `--pilot mcts|random` 操作AI / `--n-games` 1評価の試合数 /
`--k-opp` 相手フィールドの数（archive から PFSP 的にサンプル＋シード） / `--resume`。

**出力（`--out` 配下）**:
- `archive.json` … MAP-Elites アーカイブ（再開に使用）
- `summary.json` … 被覆数・最良適応度・**発見した新カード一覧**・上位ニッチ
- `best_deck.csv` … 現時点の最強デッキ（60枚）

**仕組み**: ニッチ＝行動記述子 BC（#Pokémon・#Energy・#ex〔単/多プライズ〕）。
変異＝合法なカード入替（語彙からの活用＋たまに全カードから探索）。
適応度＝候補デッキを MCTS で操作し、アーカイブの多様な相手に対する勝率。

### 発見したデッキを使う / 観戦する
```bash
cp runs/qd1/best_deck.csv sample_submission/deck.csv   # 発見デッキに差し替え
python3 tools/validate_deck.py                          # 合法性チェック
python3 tools/record_game.py game_replay.html 0        # 観戦HTML（ブラウザで開く）
bash tools/make_submission.sh                          # 提出物を作る
```

---

## 2. 価値ネット（エージェント）の学習

自己対戦データから value net を学習し、MCTS の葉評価を強化する（`agent/mcts` の `value_fn`）。

```bash
python3 - <<'PY'
from selfplay.learner import collect_dataset, train_value
buf = collect_dataset(500, seed=0)          # 自己対戦データ（agent= を MCTS にすると質↑/速度↓）
net, m = train_value(buf, epochs=50)        # CPU・数秒〜
print(m); net.save_json('value.json')       # 重み保存（val_mse < baseline なら学習成立）
PY
```

並列で自己対戦データを増やす: `python3 -m selfplay.actor`（プロセス分離・worker 再生成）。

---

## 3. スケール/運用のヒント
- 速度は **MCTS の `max_sims`/`deadline` と `--n-games`** で調整（質↔速度）。
- 長時間運用は `--resume` で安全に再開（毎世代チェックポイント）。
- 多コア活用の**並列 QD 評価**は今後追加予定（現状は serial。`selfplay/actor` のプロセス分離方式を流用）。
- 強さの最終判断は**本番ラダー A/B**（ローカル勝率は代理指標。`docs/PLAN_v1.1.md` 方針）。

## 4. ロードマップ（Phase D）
- **D1（実装済）**: QD でデッキ発見（archive/変異/評価/CLI/再開）。
- D2: カード埋め込み（card2vec）＋シナジー誘導変異＝**コンボ学習**。
- D3: デッキ⇄エージェント**共進化**（PFSP 相手分布）。
- D4: 深層サロゲート（DSA-ME）で評価コスト削減＋並列化。
