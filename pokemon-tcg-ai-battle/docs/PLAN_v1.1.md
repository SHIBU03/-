# ポケカ AI バトル「仮想空間」開発計画 v1.1（実装前・計画のみ）

> 本書は添付の計画書 **v1.0**（`1d8442c9-...md`）と調査レポートを土台に、
> 1) リポジトリ実機調査で判明した **クラッシュ原因**、
> 2) **公式プログラムの有無監査**、
> 3) 各スプリント末の **Playwright MCP によるデバッグ・ゲート**
> を組み込んで更新した版です。**この段階ではコード実装は行いません。**
>
> 版: v1.1 / 更新日: 2026-06-20 / 対象: cabt エンジン（Matsuo Institute 製）

---

## 0. エグゼクティブサマリ（先に結論）

- **クラッシュの主因は「ネイティブ資源（`Battle.battle_ptr`）のライフサイクル管理ミス」**。
  `cg/game.py` の `battle_finish()` は **解放後に `battle_ptr` を `None` に戻さない**。
  さらにネイティブ側（`libcg.so`）は **NULL/解放済みポインタを一切ガードしない**。
  → finish 後の操作・二重 finish で **SIGABRT(134)/SIGSEGV(139)** が出る（実機で再現済み）。
- もう一つの主因候補は **`kaggle_environments` 未インストール**。公式の `make("cabt")` で走らせると
  `ModuleNotFoundError` で即停止する（実機で確認）。
- **公式スターターキット本体（エンジン＋サンプル＋カードデータ）はリポジトリに揃っている**。
  ただし **`kaggle_environments`（cabt ランナー）と版固定ファイルは無い**＝自分で用意が必要。
- **対策の核**は「全ネイティブ呼び出しを **安全ラッパー**（`alive` フラグ＋例外握り＋必ず finish）で包む」こと。
  これは v1.0 が言う「無クラッシュ土台（Foundation first）」そのもの。
- **Playwright MCP デバッグは「各スプリントの完了ゲート（Definition of Done）」として常設**する。
  ただし Playwright は**ブラウザ自動化ツール**であり、cabt シムはヘッドレス。
  → **軽量 Web ビジュアライザを用意し、それを Playwright で動かして目視＋自動検証**する構成にする（§5・§6）。

---

## 1. 調査で判明した事実：なぜクラッシュするか（証拠つき）

リポジトリ `pokemon-tcg-ai-battle/sample_submission` を実機で動かして切り分けた結果。

### 1.1 正常に動くもの（クラッシュではない）

| 検証 | 結果 |
|---|---|
| `import cg.api`（`libcg.so` ロード＋`GameInitialize`） | OK（カード 1267 種ロード） |
| Game API で 1 ゲーム自己対戦（ランダム agent） | OK（21 手で決着） |
| **100 ゲーム連続自己対戦** | OK（例外 0 件 / p0:41, p1:59） |
| Search API（`search_begin/step/end/release`） | OK |
| `deck.csv`（60 枚・整数パース） | OK |

→ **エンジン本体・サンプル agent・Game/Search API は単体では健全**。アーキ（x86_64）・依存（libstdc++ 等）も解決済み。

### 1.2 ハードクラッシュを再現したパターン（ここが原因）

| # | 操作 | 結果 | 終了コード | 根本原因 |
|---|---|---|---|---|
| B1 | `battle_finish()` の **後に** `battle_select([0])` | `std::out_of_range` で Abort | **134** | 解放済みポインタ参照（use-after-free） |
| B2 | `battle_finish()` を **2 回** | `free(): invalid pointer` で Abort | **134** | 二重 free（double-free） |
| D1 | finish 後に `battle_ptr=None` にして `battle_select` | **Segmentation fault** | **139** | ネイティブが NULL ポインタを deref |
| C3 | `from kaggle_environments import make; make("cabt")` | `ModuleNotFoundError` | 1 | パッケージ未インストール |

補足:
- B3（`battle_finish` を呼ばず `battle_start` を 3 連発）はクラッシュしないが、
  `Battle.battle_ptr` は**クラス変数（シングルトン）**なので前のポインタが上書き＝**ネイティブメモリのリーク**
  （調査レポートの「libcg.so メモリリーク」と整合）。
- `cg/game.py` の該当行（`grep` 済み）:
  - `battle_finish()` は `lib.BattleFinish(Battle.battle_ptr)` のみで **`battle_ptr` を戻さない**。
  - `battle_select` / `visualize_data` / `_get_battle_data` は無条件で `Battle.battle_ptr` を使う。

### 1.3 「あなたが実行してクラッシュした」最有力シナリオ

実行コマンドの実物は未確認のため断定はしませんが、リポジトリにランナーが無いことから次の 2 つが濃厚です。

1. **公式ランナーで走らせた** → `kaggle_environments` 未導入で `ModuleNotFoundError`（=「動かない」）。
2. **自己対戦ループを書いた／回した** → ループの境界で finish 後に select、または再ループ前に二重 finish
   が起きて **SIGABRT/Segfault**。シングルトン `battle_ptr` 設計なので、ループ・並列・例外時に踏みやすい。

> 正確な特定が必要なら、**実行したコマンド or スタックトレース**を共有してください。上記のどれかに一致するはずです。

### 1.4 だから対策はこうなる（v1.0 の「無クラッシュ土台」を具体化）

- **安全ラッパー `env/game_api.py`** を必ず噛ませる:
  - `alive` フラグを持ち、`battle_start` 成功で `True`、`battle_finish` で **`battle_ptr=None`＋`alive=False`**。
  - `select/visualize/get_data` は `alive` でなければ呼ばない（クリーンな Python 例外）。
  - `battle_finish` は **冪等**（二度呼んでも無害）。`__del__`/`finally`/context manager で**必ず一度だけ**呼ぶ。
- **1 プロセス 1 ロード**を厳守。長時間ループは **プロセス再生成**でネイティブリークを断つ。
- agent 全体を `try/except` で包み `_legal_fallback` を返す（v1.0 §4.6）。
- 並列自己対戦は**プロセス分離**（シングルトン `battle_ptr`/`agent_ptr` の共有事故を防ぐ）。

---

## 2. リポジトリ監査：公式プログラムは入っているか

> 質問「kaggle 公式で取得できるプログラムは SHIBU03/- に入っている？無ければ言って」への回答。

### 2.1 入っているもの（= 公式スターターキット相当は揃っている）✅

```
pokemon-tcg-ai-battle/
├── JP_Card_Data.csv          # カードDB（日本語, 2102行）
├── EN_Card_Data.csv          # カードDB（英語, 2102行）
└── sample_submission/
    ├── main.py               # サンプル agent（obs_dict -> list[int]）
    ├── deck.csv              # サンプルデッキ（60枚・検証OK）
    └── cg/                   # cabt エンジン本体
        ├── libcg.so          # ネイティブ（Linux, x86_64）
        ├── cg.dll            # ネイティブ（Windows, x86_64）
        ├── api.py            # Observation/Select/Option/Search API 等（642行）
        ├── game.py           # battle_start/select/finish/visualize
        ├── sim.py            # ctypes バインディング＋Battle シングルトン
        ├── utils.py          # dict→dataclass 変換
        └── __init__.py       # 空
```

- `api.py` の API 仕様は調査レポート／v1.0 の記述と**完全一致**（SelectType 11 種、SelectContext 49 種、
  Search API の引数順、`search_begin_input` など）。一次情報として信頼できる。

### 2.2 入っていない／不足しているもの ❌（要・自前調達）

| 不足物 | 影響 | 対応（Phase 0 で実施） |
|---|---|---|
| `kaggle_environments`（cabt 環境登録含む） | 公式 `make("cabt")+env.run` が動かない＝**本番同等の最終検証ができない** | `pip install kaggle-environments==1.30.1`、cabt 環境の入手・登録方法を公式 docs で確認 |
| 版固定ファイル（`requirements.lock` 等） | 再現性なし | `kaggle-environments==1.30.1` 等をロック |
| 提出パッケージ作成スクリプト | 提出フロー未整備 | `tools/make_submission.sh`（`tar -czvf submission.tar.gz *`） |
| 自己対戦／探索／評価のコード一式 | これから作る対象 | Phase 1〜3 |
| 競技公式 README / ルール文書 | 仕様変動の追従先が手元に無い | docs にリンク・要点を控える |

> ⚠️ `make("cabt")` は標準 `kaggle_environments` には含まれない**競技専用環境**の可能性が高い。
> pip だけで入るか、競技ページからの環境取得が要るかは**Phase 0 で要確認**（取得不能なら当面 Game API で代替）。

---

## 3. 全体方針（v1.0 を踏襲し、優先順位だけ更新）

v1.0 の 5 層（環境／自己対戦／エージェント／リーグ／評価）と Phase 0–3 ロードマップは**そのまま採用**。
v1.1 での強調点は次の 3 つ。

1. **安全ラッパーを“最初の成果物”にする**（§1 の実機クラッシュが理由）。土台が無いと何を作っても落ちる。
2. **`kaggle_environments` 経路の確保**を Phase 0 のタスクに明示（最終検証の生命線）。
3. **各スプリント末に Playwright MCP デバッグ・ゲートを必須化**（§4・§5・§6）。ゲート通過まで次へ進まない。

---

## 4. スプリント運用ルール（Playwright デバッグ・ゲートの定義）

### 4.1 スプリントの回し方

各 Phase を 1〜複数スプリントに分割。**各スプリントは必ず「実装 → Playwright MCP デバッグ・ゲート → 合否判定」**で閉じる。
ゲートを通らない限り次スプリントに進まない（v1.0「完了の閾値を満たすまで進まない」を手続き化）。

### 4.2 各スプリント末の「Playwright MCP デバッグ・ゲート」共通手順

> 目的: **AI（Claude）自身が仮想空間を“動かして・見て・壊れていないか確かめる”**。
> バグが出たら **その場で Claude が自己修正**して再実行（ユーザー指示）。

1. **起動**: `submission/main.py` ではなく、スプリント成果を載せた **Web ビジュアライザ**（§6）をローカル起動。
2. **接続**: Claude を **Playwright MCP server に接続**し、ブラウザでビジュアライザを開く。
3. **実走**: Playwright で「対戦開始 / 1 手送り / N ゲーム自動実行 / シード変更」を操作し、
   盤面のスクリーンショットと DOM/コンソールログを取得。
4. **自動検証（合否チェックリスト）**: 下記「DoD チェック」を全項目確認。
5. **自己修正ループ**: 失敗・例外・見た目の異常があれば Claude が原因を特定 → 修正 → 2 へ戻り再実行。
6. **記録**: スクショ・ログ・結果を `docs/sprint_reports/` に残し、合否を判定。

### 4.3 スプリント共通 DoD（Definition of Done）チェック

- [ ] **無クラッシュ**: 指定ゲーム数を完走（SIGABRT/Segfault/未捕捉例外ゼロ）。
- [ ] **資源解放**: 各ゲームで `battle_finish`／各探索で `search_release/search_end` が呼ばれている（リークなし）。
- [ ] **合法手のみ**: 返す選択が `minCount≤len≤maxCount`・範囲内・重複なし。
- [ ] **時間予算**: 1 手・1 試合の消費時間がログされ、安全圏（試合 10 分の余裕内）。
- [ ] **目視妥当性**: ビジュアライザ上で盤面遷移が破綻していない（場・手札・サイド・勝敗表示）。
- [ ] **スプリント固有閾値**: 各 Phase の「✅完了の閾値」（§5）を満たす。

---

## 5. スプリント計画（Phase 0–3 ＋ 各末尾の Playwright ゲート）

> 期間は目安。各スプリントは §4.2 のゲートで閉じる。

### Sprint 0A — クラッシュ恒久対策＋安全土台（最優先・数日）
- 成果物: `env/game_api.py`（安全ラッパー：`alive`/冪等 finish/NULL ガード/context manager）、
  `agent/safety.py`（`normalize_selection`/`_legal_fallback`/全体 try-except）。
- 既存サンプルを安全ラッパー経由に置換し、§1.2 の B1/B2/D1 が**再発しない**ことを回帰テスト化。
- **Playwright ゲート**: ビジュアライザで 100 ゲーム自動実行 → クラッシュ 0・リーク 0 を目視＋ログ確認。
- ✅閾値: 旧クラッシュ全消滅、100 ゲーム完走。

### Sprint 0B — 公式ランナー確保＋提出パイプライン（数日）
- 成果物: `kaggle-environments==1.30.1` 導入、`make("cabt")` 可否の確認（不可なら代替策を明記）、
  `requirements.lock`、`tools/make_submission.sh`、Phase 0 の単純強デッキ（例: Iono's Bellibolt ex 系）。
- **Playwright ゲート**: ビジュアライザから「本番同等ランナー（あれば）」と「Game API」両経路で 1 戦ずつ実行・目視。
- ✅閾値: 無クラッシュでローカル完走、（可能なら）`make("cabt")` で 1 戦成立、提出物が tar 化できる。

### Sprint 1 — 高速自己対戦基盤（1–2 週）
- 成果物: `selfplay/actor.py`（プロセス分離並列）、`selfplay/replay_buffer.py`、`model/features.py`、`eval/cabt_eval.py`。
- スループット計測＋長時間ループのプロセス再生成。
- **Playwright ゲート**: ビジュアライザに「並列ワーカー稼働状況・毎秒対戦数・メモリ推移」パネルを出し、
  Playwright で一定時間走らせて**メモリ非増加（リークなし）**と**毎秒 N 対戦**を確認。
- ✅閾値（v1.0）: 1 コアで毎秒 N 対戦の安定動作、メモリリークなし。

### Sprint 2 — 決定化探索（PIMC→ISMCTS）（2–3 週）
- 成果物: `agent/determinize.py`、`agent/mcts.py`、`agent/time_budget.py`。
- `search_begin` を前向きモデルにした PIMC、ensemble 集約、時間予算打ち切り。
- **Playwright ゲート**: ビジュアライザで「探索 agent vs ルール土台」を可視対戦させ、
  1 手の探索時間・visit 分布・打ち切り発生を目視。勝ち越しと時間安全圏を確認。
- ✅閾値（v1.0）: ルール土台に明確勝ち越し＋平均手番消費が予算の 50%未満。

### Sprint 3 — 学習＋リーグ/PFSP（3 週〜）
- 成果物: `selfplay/learner.py`、`model/network.py`、`selfplay/model_pool.py`、`league/league.py`、`league/pfsp.py`。
- 軽量 policy/value NN（visit 分布・最終勝敗）、oracle guiding、main/exploiter＋PFSP。
- **Playwright ゲート**: ビジュアライザに「学習曲線・Elo・リーグ相性表」ダッシュボードを出し、
  Playwright で世代別 agent の自動対戦を回して**強さの単調改善**と無クラッシュを確認。
- ✅閾値（v1.0）: 本番ラダー A/B で μ が有意上昇（ローカルは代理指標）。

---

## 6. Playwright MCP × 仮想空間ビジュアライザ 連携設計

### 6.1 なぜ「ビジュアライザ」が要るのか（重要な前提）

- **Playwright はブラウザ（Chromium 等）を自動操作するツール**。一方 **cabt シムはヘッドレスな Python/ctypes**で、
  そのままでは Playwright が「操作する画面」が存在しない。
- そこで **薄い Web ビジュアライザ**（ローカル HTTP サーバ）を用意し、これを Playwright で動かす:
  - バックエンド: 安全ラッパー経由で対戦を進め、`visualize_data()`／obs を JSON で配信。
  - フロント: 盤面（場・ベンチ・手札・サイド・スタジアム・状態異常）、ログ、時間/メモリ計測、
    操作ボタン（開始 / 1 手送り / N ゲーム自動 / シード / agent 切替）。
- これにより Claude は **「実際に動かす（クリック）→ 見る（スクショ/DOM）→ 異常を検知 → 自己修正」** が回せる。
  card game のデバッグは“盤面を見られる”ことの価値が大きい。

### 6.2 接続手順（実装時に行う。今は計画のみ）

1. **MCP 設定追加**（プロジェクト `.mcp.json`）:
   ```jsonc
   { "mcpServers": {
       "playwright": { "command": "npx", "args": ["-y", "@playwright/mcp@latest"] }
   } }
   ```
2. **ブラウザ導入**: `npx playwright install chromium`（※ネットワークポリシー許可が前提）。
3. ビジュアライザをローカル起動（例: `127.0.0.1:8000`）。
4. Claude を再起動して Playwright MCP ツールを認識させ、§4.2 の手順でゲート実行。

### 6.3 この環境での実現可能性と注意（実機確認済み）

| 項目 | 現状 | 含意 |
|---|---|---|
| `node`/`npx` | v22 / 10.9 あり | `@playwright/mcp` の起動は可能 |
| Chromium | **システムに無し** | `playwright install chromium` が必要（要ネットワーク許可） |
| Playwright MCP ツール | **未接続**（`mcp__playwright__*` 無し） | `.mcp.json` 追加＋再起動が必要 |
| 実行環境 | リモート/Web のコンテナ | ブラウザ常駐や GUI は制約され得る。**ヘッドレス**前提で設計 |

- **フォールバック（ブラウザが入れられない場合）**:
  - (a) ビジュアライザを**ヘッドレス＋スクショ API** にして画像だけ取得し Claude が確認。
  - (b) Web 不可なら `visualize_data()` の**テキスト盤面ダンプ**＋数値メトリクスで自動検証（目視は画像、判定はログ）。
  - (c) ブラウザ必須の目視はローカルのデスクトップ版 Claude Code 側で実施。
- いずれにせよ **DoD の自動判定（§4.3）はテキスト/JSON ログで成立**させ、Playwright 目視は“追加の安心”と位置づける。

### 6.4 成果物（Phase 0 で着手予定・今は未実装）
- `viz/server.py`（対戦進行 API＋静的配信）、`viz/index.html`（盤面 UI）、
- `tools/run_viz.sh`、`.mcp.json`、`docs/sprint_reports/`（ゲート結果置き場）。

---

## 7. リスクと留意点（v1.0 §6 に追補）

- **ネイティブ・ライフサイクルが最大の地雷**: シングルトン `battle_ptr`/`agent_ptr` 設計のため、
  並列・例外・ループ境界で use-after-free/double-free を踏みやすい。**安全ラッパー必須・プロセス分離推奨**。
- **`make("cabt")` の入手性が不確実**: pip だけで揃わない可能性。Phase 0 で可否を確定し、
  ダメなら最終検証は Game API＋本番提出（ラダー）で代替する運用に切替。
- **Playwright は“仮想空間そのもの”ではない**: あくまで**ビジュアライザを介した目視/操作の手段**。
  仮想空間の本体（自己対戦・探索・学習）は Python 側。Playwright が無くても開発は進む設計にしておく
  （Playwright ゲートは品質保証レイヤ）。
- **リモート環境制約**: ブラウザ/GUI/ネットワークがポリシー依存。ヘッドレス・フォールバックを常に用意。
- v1.0 の留意点（API 仕様変動、ローカルは本番順位を誤予測、超人手法は大規模計算前提）は**そのまま有効**。

---

## 8. 次にやること（このタスクの締め）

- 本書は **計画のみ**。コード実装は未着手（ユーザー指示「まだ実装しなくて大丈夫」）。
- 着手順は **Sprint 0A（クラッシュ恒久対策＋安全土台）→ 0B（公式ランナー＋提出）** から。
- 実装フェーズに入る合図をもらったら、Sprint 0A から開始し、各スプリント末に §4.2 の Playwright ゲートを回す。

*（本書は v1.0 と調査レポートを上位資料とし、実機調査の事実で補強したもの。最新 cabt docs とローカル挙動で常に再検証する。）*
