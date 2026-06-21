"""Record one cabt game and emit a self-contained HTML replay.

Plays a game (default: MCTS player0 vs random player1) through the crash-proof
BattleSession, capturing a board snapshot at every decision, and writes a single
standalone HTML file (frames embedded) that plays back the battle in any browser
-- no server, no Playwright/Chromium needed.

Usage: python3 tools/record_game.py [out.html] [seed]
"""
import json
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for p in (_REPO, os.path.join(_REPO, "sample_submission")):
    if p not in sys.path:
        sys.path.insert(0, p)

import logging
logging.disable(logging.CRITICAL)

from env.game_api import BattleSession, read_deck, random_agent  # noqa: E402
from agent.mcts import make_mcts_agent                           # noqa: E402
from cg.api import all_card_data                                 # noqa: E402

CARD_NAME = {c.cardId: c.name for c in all_card_data()}


def _poke(p):
    if not p:
        return None
    return {"name": CARD_NAME.get(p.get("id"), str(p.get("id"))),
            "hp": p.get("hp"), "maxHp": p.get("maxHp"),
            "energy": len(p.get("energies") or [])}


def _player(ps):
    active = ps.get("active") or []
    return {
        "active": _poke(active[0]) if active else None,
        "bench": [_poke(b) for b in (ps.get("bench") or [])],
        "hand": ps.get("handCount", len(ps.get("hand") or []) if ps.get("hand") else 0),
        "prize": len(ps.get("prize") or []),
        "deck": ps.get("deckCount"),
        "discard": len(ps.get("discard") or []),
        "status": [k for k in ("poisoned", "burned", "asleep", "paralyzed", "confused") if ps.get(k)],
    }


def _log_str(lg):
    t = lg.get("type")
    cid = lg.get("cardId")
    name = CARD_NAME.get(cid) if cid else None
    parts = [f"type{t}"]
    if name:
        parts.append(name)
    if lg.get("attackId") is not None:
        parts.append(f"atk{lg['attackId']}")
    return " ".join(parts)


def record(out_path, seed=0, names=("MCTS", "random")):
    random.seed(seed)
    a0 = make_mcts_agent(deadline_s=0.12, max_sims=48, seed=seed)
    a1 = random_agent
    deck = read_deck()
    frames = []
    with BattleSession() as s:
        s.start(deck, deck)
        steps = 0
        while s.result == -1 and steps < 20000:
            obs = s.obs
            cur = obs.get("current") or {}
            players = cur.get("players") or [{}, {}]
            yi = cur.get("yourIndex", 0)
            sel = obs.get("select") or {}
            action = (a0 if yi == 0 else a1)(obs)
            frames.append({
                "step": steps, "turn": cur.get("turn"), "toMove": yi,
                "selCtx": sel.get("context"), "nOpt": len(sel.get("option") or []),
                "action": action,
                "players": [_player(players[0]), _player(players[1])],
                "logs": [_log_str(l) for l in (obs.get("logs") or [])[:8]],
            })
            s.select(action)
            steps += 1
        result = s.result
    meta = {"result": result, "p0": names[0], "p1": names[1], "seed": seed, "frames": len(frames)}
    html = _TEMPLATE.replace("__META__", json.dumps(meta)).replace("__FRAMES__", json.dumps(frames))
    with open(out_path, "w") as f:
        f.write(html)
    print(f"wrote {out_path}  ({len(frames)} frames, result={result} -> "
          f"{'p0/'+names[0] if result==0 else 'p1/'+names[1] if result==1 else 'draw'})")
    return out_path


_TEMPLATE = r"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>ポケカ 対局リプレイ</title><style>
body{font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6;margin:16px}
h1{font-size:19px} .sub{font-size:12px;color:#8aa}
.ctrl{display:flex;gap:8px;align-items:center;margin:10px 0;flex-wrap:wrap}
button{background:#2a3550;color:#fff;border:1px solid #44557a;border-radius:6px;padding:6px 12px;cursor:pointer}
button:hover{background:#38456a}
input[type=range]{width:340px}
.player{background:#161a22;border:1px solid #333;border-radius:8px;padding:10px;margin:6px 0}
.win{border-color:#3a7}.row{font-size:13px;padding:2px 0;color:#cdd}
h3{margin:0 0 4px;font-size:13px;color:#fc9}.mid{text-align:center;color:#ccc;font-size:13px;padding:4px}
.act{color:#6cf}.pre{white-space:pre-wrap;font-size:12px;color:#9ab;background:#11141b;border-radius:6px;padding:8px;max-height:160px;overflow:auto}
.badge{display:inline-block;background:#333;border-radius:4px;padding:0 6px;margin-left:6px;font-size:11px}
</style></head><body>
<h1>ポケカ AI 対局リプレイ <span class="sub" id="meta"></span></h1>
<div class="ctrl">
  <button id="first">⏮</button><button id="prev">◀ Prev</button>
  <button id="play">▶ Play</button><button id="next">Next ▶</button><button id="last">⏭</button>
  <input type="range" id="seek" min="0" value="0"><span id="counter"></span>
  <label>速度<select id="speed"><option value="700">slow</option><option value="350" selected>normal</option><option value="120">fast</option></select></label>
</div>
<div id="result" class="mid"></div>
<div class="player" id="p1box"><h3>Player 1 <span id="p1tag"></span></h3>
  <div class="row" id="p1a"></div><div class="row" id="p1b"></div><div class="row" id="p1i"></div></div>
<div class="mid" id="turn"></div>
<div class="player" id="p0box"><h3>Player 0 <span id="p0tag"></span></h3>
  <div class="row" id="p0a"></div><div class="row" id="p0b"></div><div class="row" id="p0i"></div></div>
<div class="mid act" id="action"></div>
<div class="pre" id="logs"></div>
<script>
const META=__META__, FRAMES=__FRAMES__;
let i=0, timer=null;
const $=id=>document.getElementById(id);
$('meta').textContent=`p0=${META.p0} vs p1=${META.p1} | seed ${META.seed} | ${META.frames} frames`;
$('seek').max=FRAMES.length-1;
$('p0tag').textContent='('+META.p0+')'; $('p1tag').textContent='('+META.p1+')';
function poke(p){return p?`${p.name} HP ${p.hp}/${p.maxHp} ⚡${p.energy}`:'(none)';}
function render(){
 const f=FRAMES[i];
 $('counter').textContent=`${i+1}/${FRAMES.length}`; $('seek').value=i;
 $('turn').textContent=`turn ${f.turn} ｜ to move: Player ${f.toMove}`;
 for(const x of [0,1]){const p=f.players[x];
  $('p'+x+'a').textContent='active: '+poke(p.active)+(p.status.length?'  ['+p.status.join(',')+']':'');
  $('p'+x+'b').textContent='bench: '+(p.bench.length?p.bench.map(poke).join(' | '):'-');
  $('p'+x+'i').innerHTML=`hand ${p.hand} ｜ prize ${p.prize} ｜ deck ${p.deck} ｜ discard ${p.discard}`;}
 $('p0box').className='player'+(f.toMove===0?' win':''); $('p1box').className='player'+(f.toMove===1?' win':'');
 $('action').textContent=`Player ${f.toMove} action → option ${JSON.stringify(f.action)}  (ctx ${f.selCtx}, ${f.nOpt} options)`;
 $('logs').textContent=(f.logs||[]).join('\n');
 const r=META.result; $('result').innerHTML = (i===FRAMES.length-1)?
   `<b>RESULT: ${r===0?'Player 0 ('+META.p0+') WINS':r===1?'Player 1 ('+META.p1+') WINS':'DRAW'}</b>`:'';
}
function step(d){i=Math.max(0,Math.min(FRAMES.length-1,i+d));render();}
$('next').onclick=()=>step(1);$('prev').onclick=()=>step(-1);
$('first').onclick=()=>{i=0;render()};$('last').onclick=()=>{i=FRAMES.length-1;render()};
$('seek').oninput=e=>{i=+e.target.value;render()};
$('play').onclick=function(){ if(timer){clearInterval(timer);timer=null;this.textContent='▶ Play';return;}
 this.textContent='⏸ Pause'; const sp=+$('speed').value;
 timer=setInterval(()=>{ if(i>=FRAMES.length-1){clearInterval(timer);timer=null;$('play').textContent='▶ Play';return;} step(1); }, sp); };
render();
</script></body></html>"""


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_REPO, "game_replay.html")
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    record(out, seed)
