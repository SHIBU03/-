# ポケカ AI バトル「仮想空間」開発計画 v1.2（Sprint 0A+0B 詳細化版・実装前）

> 上位資料: 計画書 **v1.0**（着想・全体ロードマップ）、**v1.1**（`docs/PLAN_v1.1.md`：クラッシュ診断・公式監査・Playwrightゲート導入）。
> 本 v1.2 は v1.1 を土台に、ユーザー決定を反映して **可視化方針を確定**し、**Sprint 0A・0B を実装可能な粒度まで詳細化**したもの。
> **この段階ではコード実装は行わない**（Sprint 1〜3 は v1.1 の粒度を維持）。
>
> 版: v1.2 / 更新日: 2026-06-20 / 対象: cabt エンジン（Matsuo Institute 製）

---

## 0. v1.2 で確定した事項

ユーザー決定:
1. **可視化方針 = Web ビジュアライザ ＋ Playwright MCP**
   盤面 UI をローカル Web で作り、Playwright MCP でブラウザを開いて AI（Claude）が目視・操作・スクショし、各スプリント末にデバッグする。
2. **詳細化範囲 = Sprint 0A ＋ 0B**（安全土台＋公式ランナー/提出パイプライン）。Sprint 1〜3 は v1.1 の粒度のまま。

実機調査で確定した前提（v1.1 §1 の要約）:
- クラッシュ主因は **ネイティブ資源 `Battle.battle_ptr` のライフサイクル管理ミス**。
- `kaggle_environments` 未導入で公式 `make("cabt")` は起動不可。
- スターターキット本体（エンジン `cg/`・サンプル・カードDB）は揃っている。

---

## 1. クラッシュ原因（実機で確定した証拠）

| # | 操作 | 結果 | 終了コード | 原因 |
|---|---|---|---|---|
| B1 | `battle_finish()` の後に `battle_select()` | `std::out_of_range` で Abort | 134 | use-after-free |
| B2 | `battle_finish()` を 2 回 | `free(): invalid pointer` で Abort | 134 | double-free |
| D1 | finish 後に `battle_ptr=None` にして `select` | Segmentation fault | 139 | NULL deref（ネイティブが無防備） |
| C3 | `from kaggle_environments import make; make("cabt")` | `ModuleNotFoundError` | 1 | パッケージ未導入 |

**根本原因**: `cg/game.py:battle_finish()`（45行）が `Battle.battle_ptr` を `None` に戻さない。
`battle_select`（60行）/`visualize_data`（75行）/`_get_battle_data`（13行）は無条件で `Battle.battle_ptr`
（`cg/sim.py` 67–69 行のクラス変数＝プロセス共有シングルトン）を使う。ネイティブ側は NULL/解放済みポインタを
一切ガードしない。→ **ライフサイクル管理は Python 側の責務**。

**健全な部分（再利用可）**: Game API 単体・Search API・サンプル agent は 100 ゲーム自己対戦で無クラッシュを確認済み。

---

## 2. 確定した設計方針

1. **全ネイティブ呼び出しを安全ラッパーで包む**。`alive` フラグで「終了後は二度とネイティブを呼ばない」を保証
   （`battle_ptr=None` にしても segfault するため、**呼び出し自体を抑止**する）。
2. **submission 側 と dev 側 で対策を分離**:
   - **submission**（ラダーで動く agent）: `agent(obs_dict)` を try/except で包み、必ず合法手（`legal_fallback`）を返す。
     B1/B2 は起きない（`battle_*` を呼ぶのは Kaggle ハーネス側）。守るべきは「例外で落ちない・常に合法手」。
   - **dev**（自己対戦ハーネス）: 自己対戦ループが `battle_start/select/finish` を呼ぶ → ここで B1/B2/D1 が起きる
     → `BattleSession` で根絶。
3. **1 プロセス 1 ライブセッション**。`Battle.battle_ptr`/`agent_ptr` はプロセス共有シングルトンのため、
   並列は必ずプロセス分離（Sprint 1）。長時間ループはプロセス再生成でネイティブリークを断つ。
4. **可視化 = Web ビジュアライザ**。dev の `BattleSession` 経由で対戦を進め、`visualize_data()`/obs を JSON 配信。
   Playwright MCP がブラウザで開いて目視・操作・スクショ。各スプリント末の **デバッグ・ゲート** で使用。

### 2.1 ディレクトリ方針（実リポジトリ構造に合わせる）

```
pokemon-tcg-ai-battle/
├── sample_submission/          # 提出物（tar に入る）。自己完結を維持
│   ├── main.py                 # agent(obs_dict)。safe_agent でラップ
│   ├── deck.csv
│   ├── agent/                  # ← 新規。提出に同梱（safety, 後に rule_based/mcts）
│   │   ├── __init__.py
│   │   └── safety.py
│   └── cg/                     # 既存エンジン（変更しない）
├── env/                        # ← 新規 dev 専用（提出に入れない）
│   ├── __init__.py
│   └── game_api.py             # BattleSession 安全ラッパー
├── viz/                        # ← 新規 dev 専用（可視化）
│   ├── server.py
│   └── index.html / app.js / style.css
├── tools/
│   ├── make_submission.sh
│   ├── validate_deck.py
│   └── run_viz.sh
├── tests/
│   └── test_lifecycle.py
├── docs/
│   ├── PLAN_v1.1.md            # 既存
│   ├── PLAN_v1.2.md            # 本書
│   └── sprint_reports/         # ゲート結果（スクショ/ログ）
├── requirements.lock           # kaggle-environments==1.30.1 等
└── .mcp.json                   # Playwright MCP 設定
```

---

## 3. Sprint 0A — クラッシュ恒久対策＋安全土台（詳細）

**目的**: B1/B2/D1 を再発不能にし、submission がラダーで決してクラッシュしない土台を作る。

### 3.1 タスク

1. **`env/game_api.py`: `BattleSession`（安全ラッパー）**
   - `start(deck0, deck1)`: 既に alive なら `RuntimeError`。`cg.game.battle_start` を呼び、obs が None なら
     `StartData`（errorPlayer/errorType）を例外化。成功で `alive=True`。
   - `select(list)`: `alive` 検査 → false なら `RuntimeError`（ネイティブ未呼出）。`cg.game.battle_select` をラップ。
   - `visualize()`: `alive` 検査つき `cg.game.visualize_data`。
   - `finish()`: **冪等**。一度だけ `cg.game.battle_finish` を呼び、直後に `Battle.battle_ptr=None`＋`alive=False`＋`_finished=True`。
   - `__enter__/__exit__`/`__del__`: 必ず一度 finish。`with BattleSession() as s:` で使う。
   - 再利用元: `cg.game.battle_start/battle_select/battle_finish/visualize_data`、`cg.sim.Battle`、`cg.api.to_observation_class`。
2. **`sample_submission/agent/safety.py`**
   - `normalize_selection(sel, minCount, maxCount, n_options)`: 範囲内・重複なし・`minCount≤len≤maxCount` に矯正。
   - `legal_fallback(select_data)`: 確実な合法手（例: 先頭から `minCount` 個、または `list(range(maxCount))`）。
   - `safe_agent(fn)`: `agent` を try/except で包み、例外時は `legal_fallback`。デッキ選択フェーズ（`select is None`）は
     60 枚デッキ返却に委譲。
   - 再利用元: `sample_submission/main.py:read_deck_csv`、`cg.api.to_observation_class`。
3. **`sample_submission/main.py`**: `agent` を `safe_agent` でラップ。現行ランダムは最小ベースラインとして温存
   （強いルールは Phase 0 続きで追加）。
4. **`tests/test_lifecycle.py`（回帰テスト）**
   - B1（finish 後 select）→ `RuntimeError`、かつ **プロセスが Abort しない**（subprocess の exit code が 134/139 でないことを assert）。
   - B2（二重 finish）→ 例外なし・クラッシュなし。
   - start 二重 → `RuntimeError`。
   - 200 ゲーム自己対戦（`BattleSession`＋`safe_agent`）→ クラッシュ 0・各ゲーム finish 呼出・未捕捉例外 0。
   - メモリ: N ゲーム後 RSS が単調増加でない（閾値内）。

### 3.2 受入基準（DoD）

- [ ] B1/B2/D1 が **クリーンな Python 例外**になり、SIGABRT/Segfault が出ない（subprocess exit code で検証）。
- [ ] 200 ゲーム自己対戦完走、クラッシュ 0・リーク 0（finish 計数一致）。
- [ ] submission の `agent` が想定外入力でも必ず合法手を返す（fuzz テスト）。
- [ ] **Playwright デバッグ・ゲート通過**（§5）。

---

## 4. Sprint 0B — 公式ランナー確保＋提出パイプライン（詳細）

**目的**: 本番同等検証の経路を確保（不可なら代替を確定）し、再現性と提出を整備。

### 4.1 タスク

1. **`kaggle_environments` 確保**: `pip install kaggle-environments==1.30.1` を試行し、`make("cabt")` の可否を確認。
   - cabt は競技専用環境のため pip だけで登録されない可能性大 → 登録方法（競技配布物/環境ファイル）を公式 docs で調査。
   - 取得不能なら **最終検証 = Game API ＋ 本番ラダー提出** にフォールバックする旨を明記。
   - `env/kaggle_runner.py`（取得できた場合のみ）: `make("cabt")+env.run` ラッパー。
2. **`requirements.lock`**: `kaggle-environments==1.30.1` 等を固定。
3. **`tools/validate_deck.py`**: 60 枚・存在する `cardId`・同名 4 枚制限（基本エネ除く）・ACE SPEC ≤1 を検査。
   - 再利用元: `cg.api.all_card_data`、`JP_Card_Data.csv`/`EN_Card_Data.csv`。
4. **`tools/make_submission.sh`**: `main.py`＋`deck.csv`＋`agent/`＋`cg/` を top-level に `tar -czvf submission.tar.gz *`。
   事前に `validate_deck.py` を実行。
5. **提出スモークテスト**: tar を temp 展開 → `deck.csv` パス（`/kaggle_simulations/agent/`）解決 →
   `BattleSession`＋packaged agent で 1 ゲーム完走確認。
6. **Phase 0 デッキ**: 既存 `deck.csv` の妥当性検証。必要なら単純強デッキ（例: Iono's Bellibolt ex 系）へ
   差し替え検討（採否の最終判断は本番ラダー A/B）。

### 4.2 受入基準（DoD）

- [ ] 版固定で再現可能。
- [ ] `make_submission.sh` が正しい top-level 構成の tar を生成、`validate_deck.py` 合格。
- [ ] `make("cabt")` が使えれば `env.run` で 1 ゲーム完走。使えなければ **ギャップを文書化＋Game API 代替を確認**。
- [ ] 展開後の packaged agent が 1 ゲーム完走。
- [ ] **Playwright デバッグ・ゲート通過**（§5）。

---

## 5. Web ビジュアライザ ＋ Playwright MCP（0A/0B 共通インフラ）

### 5.1 構成

- **`viz/server.py`**: 依存最小（標準ライブラリ `http.server`）。エンドポイント:
  - `GET /` → `index.html`
  - `POST /api/start {decks, seed}` → `BattleSession.start`、obs＋`visualize()` 返却
  - `POST /api/step {action}` → `select`、obs＋viz
  - `POST /api/auto {n_games, seed, agent}` → N ゲーム実行、結果＋メトリクス（1 手時間/RSS/完走数/クラッシュ数）
  - `GET /api/metrics` → 計測値
- **`viz/index.html` + `app.js` + `style.css`**: 盤面（active/bench/hand/prize/discard/stadium/状態異常）、ログ、
  勝敗、turn、操作（Start/Step/Auto N/Seed/agent 切替）、計測パネル。
- **`tools/run_viz.sh`**: サーバ起動（`127.0.0.1:8000`）。
- **`.mcp.json`**: `{"mcpServers":{"playwright":{"command":"npx","args":["-y","@playwright/mcp@latest"]}}}`。
- **ブラウザ**: `npx playwright install chromium`（**ネットワークポリシー許可が前提**）。

### 5.2 各スプリント末「Playwright デバッグ・ゲート」手順

1. `tools/run_viz.sh` でビジュアライザ起動。
2. Claude を Playwright MCP に接続、`browser_navigate` で `http://127.0.0.1:8000`。
3. 「Auto 100」操作 → `browser_snapshot`/スクショ、コンソール/DOM 取得。
4. 計測パネル確認: クラッシュ 0／完走数一致／メモリ安定／最大手番時間が予算内。
5. 異常時は **Claude が自己修正 → 再起動 → 再実行**。
6. スクショ・ログ・合否を `docs/sprint_reports/` に保存。

### 5.3 実現可能性（実機確認済み）と注意

- `node v22`/`npx` あり → `@playwright/mcp` 起動可。**chromium 未導入・Playwright MCP 未接続**
  （`.mcp.json` 追加＋`playwright install` が必要）。
- リモート/ヘッドレス環境。**フォールバック**: (a) ヘッドレス＋スクショ API で画像のみ取得、
  (b) Web 不可なら `visualize_data()` テキスト盤面＋メトリクスで自動判定。
  **DoD の自動判定はテキスト/JSON ログで成立**させ、Playwright 目視は“追加の安心”と位置づける。

---

## 6. Sprint 1〜3（v1.1 の粒度を維持・参考）

| Sprint | 主成果 | ✅完了の閾値 | スプリント末ゲート |
|---|---|---|---|
| **1** 高速自己対戦基盤 | `selfplay/actor.py`（プロセス分離並列）、`replay_buffer`、`model/features.py`、`eval/cabt_eval.py` | 1 コアで毎秒 N 対戦・リークなし | ビジュアライザで「毎秒対戦数・メモリ推移」を可視化し非増加を確認 |
| **2** 決定化探索 | `agent/determinize.py`、`agent/mcts.py`（PIMC→ISMCTS）、`agent/time_budget.py` | ルール土台に明確勝ち越し＋手番消費が予算 50%未満 | 探索 agent vs 土台を可視対戦、探索時間/visit/打ち切りを目視 |
| **3** 学習＋リーグ | `selfplay/learner.py`、`model/network.py`、`league/`＋`pfsp` | 本番ラダー A/B で μ 有意上昇 | 学習曲線/Elo/相性表ダッシュボードを Playwright で確認 |

詳細は v1.1 §5 を参照。

---

## 7. リスクと留意点

- **ネイティブ・ライフサイクルが最大の地雷**: シングルトン `battle_ptr`/`agent_ptr` のため、並列・例外・ループ境界で
  use-after-free/double-free を踏みやすい。**安全ラッパー必須・プロセス分離推奨**。
- **`make("cabt")` 入手不確実**: pip だけで揃わない可能性。0B で可否を確定し、不可なら Game API＋ラダー提出で代替。
- **Playwright のブラウザ導入がネットワークポリシーで不可の場合**: §5.3 のヘッドレス/テキスト・フォールバックに切替。
- v1.0/v1.1 の留意点（API 仕様変動、ローカルは本番順位を誤予測、超人手法は大規模計算前提）は引き続き有効。

---

## 8. 次のアクション

- 本書は **計画のみ**。Sprint のコード実装は未着手。
- 実装の合図をもらったら **Sprint 0A（安全土台）→ 0B（公式ランナー＋提出）** の順で着手し、各末尾で §5.2 の
  Playwright デバッグ・ゲートを回す。

*（本書は v1.0/v1.1 と調査レポートを上位資料とし、実機調査の事実で補強したもの。最新 cabt docs とローカル挙動で常に再検証する。）*
