# -*- coding: utf-8 -*-
"""生成通用字幕剪辑台（单文件 HTML，数据/声波/参考图全部内嵌）。"""
import json
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>__TITLE__ · 字幕剪辑台</title>
<style>
  * { box-sizing: border-box; } html, body { height: 100%; }
  body { font-family: "Microsoft YaHei", sans-serif; margin: 0; background: #14161c;
         color: #e8eaf0; display: flex; flex-direction: column; overflow: hidden; }
  header { background: #1b1e27; padding: 8px 14px; border-bottom: 2px solid #2c3040; }
  h1 { font-size: 17px; margin: 0; color: #ffd740; display: inline; }
  .hint { font-size: 12px; color: #9aa2b5; margin-left: 14px; }
  .bar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 8px; }
  .bar select, .bar input, .bar button { font-size: 13px; padding: 3px 8px; border-radius: 4px;
      border: 1px solid #3a4054; background: #232838; color: #e8eaf0; }
  .bar button { cursor: pointer; }
  .bar button.primary { background: #2f6fed; border-color: #2f6fed; color: #fff; font-weight: bold; }
  .chip { font-size: 12px; padding: 2px 10px; border-radius: 12px; cursor: pointer;
          border: 1px solid #3a4054; user-select: none; }
  .chip.on { background: #2f6fed; border-color: #2f6fed; color: #fff; }
  .stat { font-size: 13px; color: #7fe08a; margin-left: auto; } .stat.warn { color: #ffb74d; }
  #stripWrap { position: relative; height: 54px; background: #101218;
               border-bottom: 1px solid #2c3040; cursor: crosshair; }
  #strip { width: 100%; height: 100%; display: block; }
  #stripWrap .cursor { position: absolute; top: 0; bottom: 0; width: 2px;
                       background: #ff5252; pointer-events: none; }
  #mainRow { flex: 1; display: flex; min-height: 0; }
  #tableWrap { flex: 1; overflow: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th { position: sticky; top: 0; background: #1b1e27; color: #8fa0c9; padding: 6px 4px;
       border-bottom: 2px solid #2c3040; text-align: left; z-index: 2; }
  td { padding: 3px 4px; border-bottom: 1px solid #232838; vertical-align: middle; }
  tr.r-keep td { background: rgba(70,160,90,.10); }
  tr.r-highlight td { background: rgba(240,180,60,.12); }
  tr.r-slow td { background: rgba(70,140,240,.12); }
  tr.playing td { outline: 2px solid #ff5252; outline-offset: -2px; }
  td input, td select { font-size: 13px; background: #232838; color: #e8eaf0;
      border: 1px solid #333a4e; border-radius: 3px; padding: 3px 5px; }
  td input.txt { width: 100%; min-width: 190px; } td input.hz { width: 110px; }
  .playBtn { cursor: pointer; color: #7fe08a; font-size: 15px; width: 22px;
             display: inline-block; text-align: center; }
  #side { width: 400px; border-left: 2px solid #2c3040; background: #171a22;
          display: flex; flex-direction: column; overflow-y: auto; padding: 10px; }
  #video { width: 100%; background: #000; border-radius: 6px; }
  .vbtns { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
  .vbtns button { font-size: 13px; padding: 4px 10px; border-radius: 4px; cursor: pointer;
      border: 1px solid #3a4054; background: #232838; color: #e8eaf0; }
  .vbtns button.on { background: #2f6fed; color: #fff; }
  #nowLine { font-size: 14px; margin-top: 8px; min-height: 40px; line-height: 1.5; }
  .panel { background: #1b1e27; border: 1px solid #2c3040; border-radius: 8px;
           padding: 10px 12px; margin-top: 10px; font-size: 13px; }
  .panel h3 { margin: 0 0 8px; font-size: 14px; color: #ffd740; }
  .panel label { display: block; margin: 6px 0; }
  .panel input[type="range"] { width: 140px; vertical-align: middle; }
  #gridWrap { position: relative; width: 100%; }
  #gridImg { width: 100%; display: block; cursor: crosshair; border: 1px solid #3a4054; }
  .mk { position: absolute; pointer-events: none; }
  .del { color: #ff6b6b; cursor: pointer; margin-left: 6px; }
  .sw { display: inline-block; width: 12px; height: 12px; border-radius: 50%;
        vertical-align: middle; margin-right: 4px; }
  .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
           background: #2f6fed; color: #fff; padding: 8px 18px; border-radius: 6px;
           font-size: 14px; display: none; z-index: 30; }
</style>
</head>
<body>
<header>
  <h1 contenteditable id="projTitle">__TITLE__</h1><span class="hint">点行首 ▶ 预览 · 空格 播放 · ↑↓ 选行 · K 保留/略过 · Ctrl+Z 撤销</span>
  <div class="bar">
    <button class="primary" onclick="exportDecisions()">⬇ 导出决策</button>
    <label style="font-size:13px;cursor:pointer;">导入 <input type="file" accept=".json"
        style="display:none" onchange="importDecisions(this)"></label>
    <button onclick="undo()">↩ 撤销</button>
    <span class="chip on" data-f="全部" onclick="setFilter(this)">全部</span>
    <span class="chip" data-f="仅保留" onclick="setFilter(this)">仅保留</span>
    <span class="chip" data-f="仅略过" onclick="setFilter(this)">仅略过</span>
    <span class="chip" data-f="仅重点" onclick="setFilter(this)">仅重点</span>
    <select id="filterEvent" onchange="render()"></select>
    <input id="search" placeholder="搜台词/人名" oninput="render()" style="width:110px">
    <select id="batchAction">
      <option value="keep">完整保留</option><option value="skip">快速略过</option>
      <option value="highlight">重点突出</option><option value="slow">慢放突出</option>
    </select>
    <button onclick="batchApply()">批量应用</button>
    <span class="stat" id="stat"></span>
  </div>
</header>
<div id="stripWrap"><canvas id="strip"></canvas><div class="cursor" id="cursor"></div></div>
<div id="mainRow">
  <div id="tableWrap"><table>
    <thead><tr><th></th><th>#</th><th>时间</th><th>人物</th><th>台词（可改）</th>
      <th>事件</th><th>剪辑方式</th><th>花字</th><th>样式</th><th>音效</th><th>字幕</th></tr></thead>
    <tbody id="tb"></tbody>
  </table></div>
  <div id="side">
    <video id="video" controls preload="metadata">
      <source src="__PROXY__" type="video/mp4">
      <source src="__VIDEO__" type="video/mp4">
    </video>
    <div class="vbtns">
      <button onclick="vid.play()">▶</button><button onclick="vid.pause()">⏸</button>
      <button id="btnFollow" class="on" onclick="toggleFollow()">跟随:开</button>
      <button id="btnCutMode" onclick="toggleCutMode()">成片模式:关</button>
    </div>
    <div id="nowLine">（点表格行或时间轴预览）</div>
    <div class="panel"><h3>成片参数</h3>
      <label>片名 <input id="setTitle" style="width:150px" onchange="setSetting('片名', this.value)"></label>
      <label>前后缓冲 <input type="range" id="setBuf" min="0.1" max="1" step="0.05"
        oninput="setSetting('缓冲', +this.value)"><span id="bufV"></span>s</label>
      <label>拼接间隔 <input type="range" id="setGap" min="0.3" max="3" step="0.1"
        oninput="setSetting('拼接间隔', +this.value)"><span id="gapV"></span>s</label>
      <label><input type="checkbox" id="setSub" onchange="setSetting('字幕', this.checked)"> 字幕</label>
      <label><input type="checkbox" id="setPrefix" onchange="setSetting('人名前缀', this.checked)"> 字幕带人名前缀</label>
      <label><input type="checkbox" id="setSfx" onchange="setSetting('音效', this.checked)"> 音效（安全叮/中毒咚）</label>
      <label><input type="checkbox" id="setHz" onchange="setSetting('花字', this.checked)"> 花字</label>
      <label><input type="checkbox" id="setSlow" onchange="setSetting('慢放', this.checked)"> 慢放</label>
    </div>
    <div class="panel"><h3>人物与标记</h3>
      <div>名字 <input id="newName" style="width:90px" placeholder="如：小明">
        <button onclick="addPlayer()">＋ 添加人物</button></div>
      <div style="margin:6px 0">操作：选人 → 在下方参考图上<b>点头顶</b>放人名条，<b>点物品</b>放归属环</div>
      <div>选中：<select id="selPlayer" onchange="renderMarkers()"></select>
        <button onclick="mode='tag'" id="mTag">放人名条</button>
        <button onclick="mode='ring'" id="mRing">放归属环</button></div>
      <div id="gridWrap"><img id="gridImg" src="data:image/jpeg;base64,__REF__" onclick="placeMarker(event)"></div>
      <div id="mkList"></div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const LOUD = __LOUD__;
const EVENTS = ["对话","规则","高潮","安全","中毒","结尾"];
const ACTIONS = [["keep","完整保留"],["skip","快速略过"],["highlight","重点突出"],["slow","慢放突出"]];
const STYLES = [["gold","金"],["red","红"],["blue","蓝"]];
const SFXS = [["","无"],["ding","叮(安全)"],["dun","咚(中毒)"]];
const PALETTE = ["#40C4FF","#69F0AE","#FFD740","#FF4081","#B388FF","#FF7043",
                 "#00BCD4","#8BC34A","#FF9800","#E91E63","#7C4DFF","#795548"];
const DUR = LOUD.length ? LOUD[LOUD.length-1][0]+1 : 655;
DATA.settings = Object.assign({缓冲:.35,拼接间隔:1.2,字幕:true,音效:true,花字:true,
                               慢放:true,人名前缀:false,片名:DATA.title}, DATA.settings||{});
DATA.players = DATA.players || []; DATA.markers = DATA.markers || [];
let curFilter="全部", follow=true, cutMode=false, stopAt=null, mode="tag";
let undoStack=[]; let whoList=null;
const vid=document.getElementById("video");
const LS="subcut_editor_"+(DATA.title||"x");

function snapshot(){ undoStack.push(JSON.stringify({lines:DATA.lines,players:DATA.players,
  markers:DATA.markers,settings:DATA.settings})); if(undoStack.length>60) undoStack.shift(); }
function undo(){ if(!undoStack.length){toast("没有可撤销的操作");return;}
  const d=JSON.parse(undoStack.pop());
  DATA.lines=d.lines; DATA.players=d.players; DATA.markers=d.markers; DATA.settings=d.settings;
  syncUI(); render(); renderMarkers(); toast("已撤销"); }
(function(){ const saved=localStorage.getItem(LS);
  if(saved){ try{ const d=JSON.parse(saved);
    if(d.lines && confirm("检测到上次未导出的编辑，恢复吗？\\n（取消则使用初始数据）")){
      DATA.lines=d.lines; DATA.players=d.players||[]; DATA.markers=d.markers||[];
      DATA.settings=Object.assign(DATA.settings,d.settings||{}); } }catch(e){} } })();
function save(){ localStorage.setItem(LS, JSON.stringify({lines:DATA.lines,
  players:DATA.players, markers:DATA.markers, settings:DATA.settings, savedAt:Date.now()})); }

function keptWindows(){ const B=DATA.settings.缓冲,G=DATA.settings.拼接间隔;
  const iv=DATA.lines.filter(l=>l.action!=="skip")
    .map(l=>[Math.max(0,l.start-B),l.end+B]).sort((a,b)=>a[0]-b[0]);
  const out=[]; for(const [a,b] of iv){ if(out.length&&a-out[out.length-1][1]<=G)
    out[out.length-1][1]=Math.max(out[out.length-1][1],b); else out.push([a,b]); }
  return out.filter(([a,b])=>b-a>=.5); }
function estDur(){ let s=keptWindows().reduce((t,[a,b])=>t+(b-a),0);
  for(const l of DATA.lines) if(l.action==="slow") s+=(l.end-l.start); return s; }
function fmt(s){ const m=Math.floor(s/60),r=Math.round(s%60); return m+":"+String(r).padStart(2,"0"); }

const strip=document.getElementById("strip");
function drawStrip(){ const w=strip.clientWidth,h=strip.clientHeight;
  strip.width=w*devicePixelRatio; strip.height=h*devicePixelRatio;
  const c=strip.getContext("2d"); c.scale(devicePixelRatio,devicePixelRatio);
  c.fillStyle="#101218"; c.fillRect(0,0,w,h); const mid=h/2, x=t=>t/DUR*w;
  c.fillStyle="#5b6b94";
  for(const [t,db] of LOUD){ const v=Math.max(0,Math.min(1,(db+55)/50));
    const bh=v*(h/2-4); c.fillRect(x(t),mid-bh,Math.max(1,w/DUR),bh*2); }
  c.fillStyle="rgba(90,200,120,.30)";
  for(const [a,b] of keptWindows()) c.fillRect(x(a),0,x(b)-x(a),h);
  for(const l of DATA.lines){ if(l.action==="highlight"){c.fillStyle="#ffd740";
      c.fillRect(x(l.start),0,Math.max(2,x(l.end)-x(l.start)),4);}
    if(l.action==="slow"){c.fillStyle="#40a9ff";
      c.fillRect(x(l.start),h-4,Math.max(2,x(l.end)-x(l.start)),4);} }
  c.fillStyle="#8fa0c9"; c.font="10px sans-serif";
  for(let m=0;m<=DUR/60;m++) c.fillText(m+":00",x(m*60)+2,h-2); }
document.getElementById("stripWrap").addEventListener("click",e=>{
  const r=e.currentTarget.getBoundingClientRect();
  seek((e.clientX-r.left)/r.width*DUR); });
new ResizeObserver(drawStrip).observe(strip);
function seek(t){ vid.currentTime=Math.max(0,Math.min(DUR-.1,t)); vid.play(); stopAt=null; }
function toggleCutMode(){ cutMode=!cutMode; const b=document.getElementById("btnCutMode");
  b.textContent="成片模式:"+(cutMode?"开":"关"); b.classList.toggle("on",cutMode);
  toast(cutMode?"成片模式：自动跳过被剪部分（慢放不模拟）":"完整播放"); }
function toggleFollow(){ follow=!follow; const b=document.getElementById("btnFollow");
  b.textContent="跟随:"+(follow?"开":"关"); b.classList.toggle("on",follow); }

function whoOptions(sel){ const names=[...new Set(["?",...DATA.players.map(p=>p.名字)])];
  return names.map(w=>`<option ${w===sel?"selected":""}>${w}</option>`).join(""); }
function visibleLines(){ const fe=document.getElementById("filterEvent").value;
  const q=document.getElementById("search").value.trim();
  return DATA.lines.filter(l=>{
    if(curFilter==="仅保留"&&l.action==="skip") return false;
    if(curFilter==="仅略过"&&l.action!=="skip") return false;
    if(curFilter==="仅重点"&&!(l.action==="highlight"||l.action==="slow")) return false;
    if(fe&&l.event!==fe) return false;
    if(q&&!(l.text.includes(q)||(l.who||"").includes(q))) return false; return true; }); }

function render(){ const tb=document.getElementById("tb"); const vis=new Set(visibleLines().map(l=>l.id));
  tb.innerHTML="";
  for(const l of DATA.lines){ if(!vis.has(l.id)) continue;
    const tr=document.createElement("tr"); tr.className="r-"+l.action; tr.dataset.id=l.id;
    const act=ACTIONS.map(([v,n])=>`<option value="${v}" ${v===l.action?"selected":""}>${n}</option>`).join("");
    const ev=EVENTS.map(e=>`<option ${e===l.event?"selected":""}>${e}</option>`).join("");
    const st=STYLES.map(([v,n])=>`<option value="${v}" ${v===(l.style||"gold")?"selected":""}>${n}</option>`).join("");
    const fx=SFXS.map(([v,n])=>`<option value="${v}" ${v===(l.sfx||"")?"selected":""}>${n}</option>`).join("");
    tr.innerHTML=`<td class="playBtn" onclick="seek(${l.start})">▶</td>
      <td>${l.no}</td><td>${l.start.toFixed(1)}<br>${l.end.toFixed(1)}</td>
      <td><select onchange="setLine(${l.id},'who',this.value)">${whoOptions(l.who)}</select></td>
      <td><input class="txt" value="${l.text.replace(/"/g,"&quot;")}" onchange="setLine(${l.id},'text',this.value)"></td>
      <td><select onchange="setLine(${l.id},'event',this.value)">${ev}</select></td>
      <td><select onchange="setLine(${l.id},'action',this.value)">${act}</select></td>
      <td><input class="hz" value="${(l.huazi||"").replace(/"/g,"&quot;")}" onchange="setLine(${l.id},'huazi',this.value)"></td>
      <td><select onchange="setLine(${l.id},'style',this.value)">${st}</select></td>
      <td><select onchange="setLine(${l.id},'sfx',this.value)">${fx}</select></td>
      <td style="text-align:center"><input type="checkbox" ${l.subShow!==false?"checked":""} onchange="setLine(${l.id},'subShow',this.checked)"></td>`;
    tr.addEventListener("click",e=>{ if(e.target.tagName==="INPUT"||e.target.tagName==="SELECT") return;
      seek(l.start); stopAt=l.end+.4; });
    tb.appendChild(tr); }
  const kept=DATA.lines.filter(l=>l.action!=="skip").length, est=estDur();
  const st=document.getElementById("stat");
  st.textContent=`全片 ${DATA.lines.length} 句 · 保留 ${kept} · 预计成片 ≈ ${fmt(est)}`;
  st.className="stat"+(est>240?" warn":"");
  drawStrip(); save(); }

function setLine(id,key,val){ snapshot();
  const l=DATA.lines.find(x=>x.id===id); l[key]=val;
  if(key==="action"&&(val==="highlight"||val==="slow")&&!l.huazi){
    l.huazi=l.event==="中毒"?"中毒了？":l.event==="安全"?"安全！":"重点！";
    l.sfx=l.sfx||(l.event==="安全"?"ding":l.event==="中毒"?"dun":""); }
  render(); }
function batchApply(){ const a=document.getElementById("batchAction").value;
  if(!confirm(`把筛选出的 ${visibleLines().length} 行设为「${ACTIONS.find(x=>x[0]===a)[1]}」？`)) return;
  snapshot(); for(const l of visibleLines()){ l.action=a;
    if((a==="highlight"||a==="slow")&&!l.huazi)
      l.huazi=l.event==="中毒"?"中毒了？":l.event==="安全"?"安全！":"重点！"; }
  render(); toast("批量应用完成"); }
function setFilter(chip){ document.querySelectorAll(".chip").forEach(c=>c.classList.remove("on"));
  chip.classList.add("on"); curFilter=chip.dataset.f; render(); }
function setSetting(k,v){ snapshot(); DATA.settings[k]=v; if(k==="片名") DATA.title=v; syncUI(); render(); }
function syncUI(){ const s=DATA.settings;
  document.getElementById("setBuf").value=s.缓冲; document.getElementById("bufV").textContent=(+s.缓冲).toFixed(2);
  document.getElementById("setGap").value=s.拼接间隔; document.getElementById("gapV").textContent=(+s.拼接间隔).toFixed(1);
  document.getElementById("setSub").checked=!!s.字幕; document.getElementById("setSfx").checked=!!s.音效;
  document.getElementById("setHz").checked=!!s.花字; document.getElementById("setSlow").checked=!!s.慢放;
  document.getElementById("setPrefix").checked=!!s.人名前缀;
  document.getElementById("setTitle").value=s.片名||DATA.title;
  document.getElementById("projTitle").textContent=s.片名||DATA.title;
  const fe=document.getElementById("filterEvent");
  if(!fe.options.length){ fe.insertAdjacentHTML("beforeend",'<option value="">全部事件</option>');
    for(const e of EVENTS) fe.insertAdjacentHTML("beforeend",`<option>${e}</option>`); } }

/* ---- 人物与标记 ---- */
function addPlayer(){ const n=document.getElementById("newName").value.trim();
  if(!n){toast("先输入名字");return;} if(DATA.players.find(p=>p.名字===n)){toast("重名");return;}
  snapshot(); const color=PALETTE[DATA.players.length%PALETTE.length];
  DATA.players.push({名字:n,颜色:color,tagX:null,tagY:null});
  document.getElementById("newName").value=""; renderMarkers(); render(); save(); }
function playerSel(){ const sel=document.getElementById("selPlayer");
  const cur=sel.value; sel.innerHTML="";
  if(!DATA.players.length) sel.insertAdjacentHTML("beforeend",'<option value="">（先添加人物）</option>');
  for(const p of DATA.players)
    sel.insertAdjacentHTML("beforeend",`<option value="${p.名字}" ${p.名字===cur?"selected":""}>${p.名字}</option>`);
  document.getElementById("mTag").classList.toggle("on",mode==="tag");
  document.getElementById("mRing").classList.toggle("on",mode==="ring"); }
function placeMarker(ev){ const name=document.getElementById("selPlayer").value;
  if(!name){toast("先添加并选择人物");return;}
  const img=ev.currentTarget, r=img.getBoundingClientRect();
  const W=img.naturalWidth, H=img.naturalHeight;
  const x=Math.round((ev.clientX-r.left)/r.width*W), y=Math.round((ev.clientY-r.top)/r.height*H);
  snapshot(); const p=DATA.players.find(p=>p.名字===name);
  if(mode==="tag"){ p.tagX=x; p.tagY=y; toast(`${name} 的人名条 → (${x},${y})`); }
  else { const m=DATA.markers.find(m=>m.名字===name&&m.kind==="ring");
    if(m){m.x=x;m.y=y;} else DATA.markers.push({kind:"ring",名字:name,颜色:p.颜色,x,y,出现:0});
    toast(`${name} 的归属环 → (${x},${y})（出现时间可在下方改）`); }
  renderMarkers(); save(); }
function renderMarkers(){ playerSel();
  const img=document.getElementById("gridImg"), wrap=document.getElementById("gridWrap");
  wrap.querySelectorAll(".mk").forEach(e=>e.remove());
  const draw=(x,y,el)=>{ const sx=img.clientWidth/img.naturalWidth, sy=img.clientHeight/img.naturalHeight;
    el.style.left=x*sx+"px"; el.style.top=y*sy+"px"; wrap.appendChild(el); };
  for(const p of DATA.players){ if(p.tagX==null) continue;
    const d=document.createElement("div"); d.className="mk";
    d.style.cssText=`transform:translate(-50%,-50%);padding:1px 7px;border-radius:10px;
      background:rgba(20,20,28,.75);border:2px solid ${p.颜色};color:#fff;font-size:12px;white-space:nowrap;`;
    d.textContent=p.名字; draw(p.tagX,p.tagY,d); }
  for(const m of DATA.markers){ if(m.kind!=="ring") continue;
    const d=document.createElement("div"); d.className="mk";
    d.style.cssText=`transform:translate(-50%,-50%);width:40px;height:40px;border:4px solid ${m.颜色};
      border-radius:50%;box-shadow:0 0 4px #000;`;
    draw(m.x,m.y,d); }
  const list=document.getElementById("mkList"); list.innerHTML="";
  for(const p of DATA.players){
    const div=document.createElement("div");
    div.innerHTML=`<span class="sw" style="background:${p.颜色}"></span><b>${p.名字}</b>
      人名条X<input type="number" value="${p.tagX??''}" onchange="setTag('${p.名字}','tagX',this.value)">
      Y<input type="number" value="${p.tagY??''}" onchange="setTag('${p.名字}','tagY',this.value)">
      <span class="del" onclick="delPlayer('${p.名字}')">✕删人</span>`;
    list.appendChild(div); }
  for(const m of DATA.markers){ if(m.kind!=="ring") continue;
    const div=document.createElement("div");
    div.innerHTML=`<span class="sw" style="background:${m.颜色}"></span><b>${m.名字}</b>的环
      X<input type="number" value="${m.x}" onchange="setRing('${m.名字}','x',this.value)">
      Y<input type="number" value="${m.y}" onchange="setRing('${m.名字}','y',this.value)">
      出现(源秒)<input type="number" value="${m.出现||0}" style="width:64px"
        onchange="setRing('${m.名字}','出现',this.value)">
      <span class="del" onclick="delRing('${m.名字}')">✕</span>`;
    list.appendChild(div); } }
function setTag(n,k,v){ const p=DATA.players.find(p=>p.名字===n);
  p[k]=v===""?null:+v; renderMarkers(); save(); }
function setRing(n,k,v){ const m=DATA.markers.find(m=>m.名字===n&&m.kind==="ring");
  m[k]=+v; renderMarkers(); save(); }
function delRing(n){ snapshot(); DATA.markers=DATA.markers.filter(m=>!(m.名字===n&&m.kind==="ring"));
  renderMarkers(); save(); }
function delPlayer(n){ snapshot(); DATA.players=DATA.players.filter(p=>p.名字!==n);
  DATA.markers=DATA.markers.filter(m=>m.名字!==n); renderMarkers(); render(); save(); }

vid.addEventListener("timeupdate",()=>{ const t=vid.currentTime;
  document.getElementById("cursor").style.left=(t/DUR*100)+"%";
  if(cutMode&&!vid.paused){ const wins=keptWindows();
    if(!wins.some(([a,b])=>t>=a-.05&&t<=b)){ const nxt=wins.find(([a])=>a>t);
      if(nxt) vid.currentTime=nxt[0]; else vid.pause(); } }
  if(stopAt!=null&&t>=stopAt){ vid.pause(); stopAt=null; }
  const active=DATA.lines.find(l=>t>=l.start&&t<l.end);
  if(active){ document.getElementById("nowLine").innerHTML=
      `<b style="color:#ffd740">#${active.no} ${active.who}</b> ${active.text}
       <span style="color:#9aa2b5">（${active.event}）</span>`;
    if(follow){ const row=document.querySelector(`tr[data-id="${active.id}"]`);
      if(row) row.scrollIntoView({block:"nearest"}); } }
  document.querySelectorAll("tr.playing").forEach(r=>r.classList.remove("playing"));
  if(active){ const row=document.querySelector(`tr[data-id="${active.id}"]`);
    if(row) row.classList.add("playing"); } });
document.addEventListener("keydown",e=>{
  if(["INPUT","SELECT","TEXTAREA"].includes(e.target.tagName)) return;
  if(e.code==="Space"){ e.preventDefault(); vid.paused?vid.play():vid.pause(); }
  else if(e.key==="ArrowLeft") vid.currentTime=Math.max(0,vid.currentTime-2);
  else if(e.key==="ArrowRight") vid.currentTime+=2;
  else if(e.key==="ArrowUp"||e.key==="ArrowDown"){ e.preventDefault();
    const vis=visibleLines(); if(!vis.length) return;
    let idx=vis.findIndex(l=>l.id===(curRowId||vis[0].id));
    idx=e.key==="ArrowDown"?Math.min(vis.length-1,idx+1):Math.max(0,idx-1);
    seek(vis[idx].start); stopAt=vis[idx].end+.4; }
  else if(e.key==="k"||e.key==="K"){ const row=document.querySelector("tr.playing");
    if(row){ const l=DATA.lines.find(x=>x.id==+row.dataset.id);
      setRow(l, l.action==="skip"?"keep":"skip"); } }
  else if(e.ctrlKey&&e.key==="z"){ e.preventDefault(); undo(); } });
let curRowId=null; vid.addEventListener("timeupdate",()=>{
  const t=vid.currentTime; const a=DATA.lines.find(l=>t>=l.start&&t<l.end);
  curRowId=a?a.id:curRowId; });
function setRow(l,action){ snapshot(); l.action=action; render(); }

async function exportDecisions(){ DATA.title=DATA.settings.片名||DATA.title;
  const json=JSON.stringify({version:1,title:DATA.title,settings:DATA.settings,
      players:DATA.players,markers:DATA.markers,lines:DATA.lines},null,1);
  if(window.showSaveFilePicker){ try{
      const h=await showSaveFilePicker({suggestedName:"witch_decisions.json",
        types:[{description:"JSON",accept:{"application/json":[".json"]}}]});
      const w=await h.createWritable(); await w.write(json); await w.close();
      toast("已保存；接着运行 cut.py build 即可出片"); return;
    }catch(e){ if(e.name==="AbortError") return; } }
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([json],{type:"application/json"}));
  a.download="witch_decisions.json"; a.click(); toast("已下载 witch_decisions.json"); }
function importDecisions(input){ const f=input.files[0], rd=new FileReader();
  rd.onload=()=>{ try{ const d=JSON.parse(rd.result);
      DATA.lines=d.lines; DATA.players=d.players||[]; DATA.markers=d.markers||[];
      DATA.settings=Object.assign(DATA.settings,d.settings||{});
      syncUI(); render(); renderMarkers(); save(); toast("已导入"); }
    catch(e){ toast("文件解析失败"); } }; rd.readAsText(f); }
let toastTimer; function toast(m){ const t=document.getElementById("toast");
  t.textContent=m; t.style.display="block"; clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>t.style.display="none",2600); }

syncUI(); renderMarkers(); render();
window.addEventListener("resize",()=>{ drawStrip(); renderMarkers(); });
</script>
</body>
</html>
"""


def generate(data: dict, ref_b64: str, loud: list, proxy_name: str,
             video_name: str):
    html = (TEMPLATE
            .replace("__TITLE__", data.get("title", "我的视频"))
            .replace("__PROXY__", proxy_name)
            .replace("__VIDEO__", video_name)
            .replace("__REF__", ref_b64)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__LOUD__", json.dumps(loud)))
    Path("剪辑台.html").write_text(html, encoding="utf-8")
