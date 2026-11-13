/* HERO TV - Movie Roulette, the movie-guessing game. Loaded by index.html after app.js; styles are in roulette.css.
   It talks to /api/roulette/... and to the TV page through window.HEROTV (enter, leave, watch, toast). */
(()=>{"use strict";
const $=(s,r)=>(r||document).querySelector(s),$$=(s,r)=>[...(r||document).querySelectorAll(s)];
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e};
const HT=()=>window.HEROTV||{};
const say=t=>{const h=HT();if(h.toast)h.toast(t)};
async function call(path,body){const r=await fetch("/api/roulette/"+path,body===undefined?undefined:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
 let j=null;try{j=await r.json()}catch(e){}
 if(!r.ok)throw new Error(j&&j.error?j.error:"HERO TV did not answer. Is its window still open?");return j}
const hms=s=>{s=Math.max(0,Math.round(s||0));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return(h?h+":"+String(m).padStart(2,"0"):m)+":"+String(x).padStart(2,"0")};
const plural=(n,w)=>n+" "+w+(n===1?"":"s");

let box=null,open=false,scr="",H=null,S=null,G=null,busy=false,menu=null,draft=null,catCtx=null,back=[];
let sig="",tickT=0,clock={left:null,running:false,at:0,limit:0},sideSel=null,rebind=null,sentUp="",padT=0,padPrev={},lastTick=-1;

/* ---------------------------------------------------------------- sound (made here, no files) */
let ac=null;
function tone(freq,dur,type,vol,when){if(!S||!S.sounds)return;try{ac=ac||new(window.AudioContext||window.webkitAudioContext)();if(ac.state==="suspended")ac.resume();
 const o=ac.createOscillator(),g=ac.createGain(),t=ac.currentTime+(when||0);o.type=type||"sine";o.frequency.value=freq;g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(vol||.12,t+.015);g.gain.exponentialRampToValueAtTime(.0001,t+dur);
 o.connect(g).connect(ac.destination);o.start(t);o.stop(t+dur+.05)}catch(e){}}
const sfx={tick:()=>tone(880,.07,"square",.05),right:()=>{tone(523,.14,"triangle",.14);tone(659,.14,"triangle",.14,.12);tone(784,.3,"triangle",.16,.24)},
 wrong:()=>{tone(196,.22,"sawtooth",.1);tone(147,.34,"sawtooth",.1,.16)},reveal:()=>{tone(392,.12,"triangle",.1);tone(523,.25,"triangle",.12,.1)},
 hint:()=>tone(660,.16,"sine",.1),spin:()=>{for(let i=0;i<9;i++)tone(300+i*55,.06,"square",.04,i*.08)},up:()=>{tone(440,.16,"square",.08);tone(330,.3,"square",.08,.15)},
 win:()=>{[523,659,784,1047,784,1047].forEach((f,i)=>tone(f,i===5?.6:.16,"triangle",.16,i*.15))},move:()=>tone(520,.03,"sine",.03)};

/* ---------------------------------------------------------------- frame and small parts */
function ensure(){if(box)return;box=el("div");box.id="rl";box.setAttribute("role","application");box.setAttribute("aria-label","Movie Roulette");document.body.append(box);
 box.addEventListener("click",e=>{const b=e.target.closest&&e.target.closest("button");if(b&&!b.disabled&&box.contains(b)&&(!menu||menu.contains(b)))b.focus({preventScroll:true})})}
function clear(cls){box.className="on "+(cls||"");box.textContent="";if(S&&!S.animations)box.classList.add("still");return box}
function btn(text,fn,cls,key){const b=el("button","rb "+(cls||""));b.type="button";b.append(el("span",0,text));if(key)b.append(el("kbd",0,keyName(key)));b.onclick=async e=>{e.preventDefault();if(busy)return;try{await fn(b)}catch(x){say(String(x.message||x))}};return b}
const keyName=k=>k===" "?"Space":k.length===1?k.toUpperCase():k.replace("Arrow","");
function head(title,sub){const h=el("header","rl-head");const l=el("div");l.append(el("small",0,"MOVIE ROULETTE"),el("h1",0,title));h.append(l);if(sub)h.append(el("p",0,sub));return h}
function foot(pairs){const f=el("footer","rl-foot");for(const[a,b]of pairs){f.append(el("kbd",0,a),el("span",0,b))}return f}
function focusFirst(sel){const t=sel&&$(sel,box)||$(".rb.go",box)||$("button:not(:disabled),input",box);if(t)t.focus({preventScroll:true})}
async function go(name,arg,keep){if(!keep&&scr&&scr!==name&&scr!=="game")back.push(scr);
 /* a screen that redraws itself (a player added, a category deleted) keeps the highlight where it was */
 let at=null;if(name===scr){const a=document.activeElement,row=a&&a.closest&&a.closest(".rl-row,section,.rl-bar,.rl-catbar");
  if(row&&box.contains(a)){const lab=$("label,h3",row);at={lab:lab?lab.textContent:"",cls:row.className,i:$$("button,input",row).indexOf(a)}}}
 scr=name;menu=null;rebind=null;await SCREENS[name](arg);
 if(at&&scr===name){const rows=$$(".rl-row,section,.rl-bar,.rl-catbar",box).filter(r=>r.className===at.cls),row=rows.find(r=>{const l=$("label,h3",r);return(l?l.textContent:"")===at.lab})||rows[0];
  if(row){const f=$$("button:not(:disabled),input",row);const t=f[Math.min(at.i,f.length-1)];if(t)t.focus({preventScroll:true})}}}
function goBack(){const b=back.pop();if(b==="__game"){scr="game";sig="";return drawGame(true)}if(b)go(b,undefined,true);else go("landing",undefined,true)}
function choice(label,opts,cur,set,note){const row=el("div","rl-row");row.append(el("label",0,label));const g=el("div","seg");
 for(const[v,t]of opts){const b=btn(t,()=>{set(v);$$("button",g).forEach(x=>x.classList.toggle("on",x===b))},"opt"+(String(v)===String(cur)?" on":""));b.dataset.v=v;g.append(b)}
 row.append(g);if(note)row.append(el("small",0,note));return row}
function stepper(label,val,min,max,step,set,fmt){const row=el("div","rl-row");row.append(el("label",0,label));const g=el("div","seg"),out=el("b","num",(fmt||String)(val));let v=val;
 const ch=d=>{v=Math.max(min,Math.min(max,v+d*step));out.textContent=(fmt||String)(v);set(v)};g.append(btn("−",()=>ch(-1),"opt sq"),out,btn("+",()=>ch(1),"opt sq"));row.append(g);return row}

/* ---------------------------------------------------------------- landing */
async function loadHome(){H=await call("home");S=H.settings;return H}
const SCREENS={
async landing(){let err="";try{await loadHome()}catch(e){err=String(e.message||e)}
 const b=clear("landing");const hero=el("div","rl-hero");hero.append(el("div","rl-wheel"),el("small",0,(HT().name||"HERO TV").toUpperCase()+" PRESENTS"),el("h1",0,"MOVIE ROULETTE"),
  el("p",0,err||(!H.films?"There are no films in your library yet. Add some movies to HERO TV, then come back.":!H.tools?"The video tools (ffmpeg) are missing. Settings > Tools > Install video tools, then come back."
   :`A moment from one of your ${plural(H.films,"film")} appears. Name the film before the clock runs out.`)));
 const m=el("nav","rl-menu");const can=!err&&H.films>0&&H.tools,a=H&&H.active;
 if(a)m.append(btn("Continue game",()=>resume(),"big go"));
 const pn=btn("Play now",()=>start({}),"big"+(a?"":" go"));pn.disabled=!can;m.append(pn);
 const q=btn("Quick game",()=>{draft=null;go("setup",false)},"big");q.disabled=!can;m.append(q);
 const c=btn("Create game",()=>{draft=null;go("setup",true)},"big");c.disabled=!can;m.append(c);
 const row=el("div","rl-sub");row.append(btn("Categories",()=>{catCtx={keys:S.categories.slice(),logic:S.logic,save:true};go("cats")}),btn("Game settings",()=>go("settings")),
  btn("History",()=>go("history")),btn("How to play",()=>go("how")),btn("Back to "+(HT().name||"HERO TV"),()=>close()));
 hero.append(m,row);if(a&&can){const sm=el("p","rl-note",`A game is waiting: round ${Math.min(a.played+1,a.rounds)} of ${a.rounds}, ${a.board.map(s=>s.name+" "+s.points).join(" · ")}`);hero.append(sm)}
 b.append(hero,foot([["↑ ↓ ← →","move"],["Enter","choose"],["Esc","back to "+(HT().name||"HERO TV")]]));back=[];focusFirst()},

/* ---------------------------------------------------------------- quick game / create game */
async setup(full){if(!S)await loadHome();const D=draft=draft||{full:!!full,mode:S.mode,rounds:S.rounds,difficulty:S.difficulty,timer:S.timer,hints:S.hints,scene:S.scene,show:S.show,answers:S.answers,phones:S.phones,
  categories:S.categories.slice(),logic:S.logic,players:(S.players.length?S.players:[{name:"Player 1"}]).map(p=>({...p})),teams:(S.teams.length?S.teams:[{name:"Team 1"},{name:"Team 2"}]).map(t=>({...t}))};
 if(full!==undefined&&full!==null)D.full=!!full;
 const b=clear("form");b.append(head(D.full?"Create game":"Quick game",D.full?"Set it up the way you like. Everything here is remembered for next time.":"Who is playing, how many rounds, and go."));
 const f=el("div","rl-form");
 f.append(choice("Game",Object.entries(H.modes),D.mode,v=>{D.mode=v;if(v!=="solo"&&D.players.length<2)D.players.push({name:"Player "+(D.players.length+1)});go("setup",null,true)},
  {solo:"One player against the clock.",turns:"Players take it in turns to guess.",teams:"Teams take turns. Anyone on the team can answer.",party:"Everyone shouts. The host says who got it."}[D.mode]));
 if(D.mode==="teams"){const tr=el("div","rl-row");tr.append(el("label",0,"Teams"));const g=el("div","names");
   D.teams.forEach((t,i)=>{const inp=el("input");inp.value=t.name;inp.maxLength=24;inp.placeholder="Team "+(i+1);inp.oninput=()=>{t.name=inp.value};g.append(inp)});
   if(D.teams.length<6)g.append(btn("+ Team",()=>{D.teams.push({name:"Team "+(D.teams.length+1)});go("setup",null,true)},"opt"));
   if(D.teams.length>2)g.append(btn("− Team",()=>{D.teams.pop();D.players.forEach(p=>{if(p.team>D.teams.length)delete p.team});go("setup",null,true)},"opt"));tr.append(g);f.append(tr)}
 if(D.mode!=="solo"||D.full){const pr=el("div","rl-row");pr.append(el("label",0,D.mode==="solo"?"Player":"Players"));const g=el("div","names");
   const list=D.mode==="solo"?D.players.slice(0,1):D.players;
   list.forEach((p,i)=>{const w=el("span","nm"),inp=el("input");inp.value=p.name;inp.maxLength=24;inp.placeholder="Player "+(i+1);inp.oninput=()=>{p.name=inp.value};w.append(inp);
    if(D.mode==="teams"){const tb=btn(D.teams[(p.team||(i%D.teams.length)+1)-1].name||"Team",()=>{p.team=((p.team||(i%D.teams.length)+1)%D.teams.length)+1;tb.firstChild.textContent=D.teams[p.team-1].name||"Team "+p.team},"opt tm");p.team=p.team||(i%D.teams.length)+1;w.append(tb)}
    g.append(w)});
   if(D.mode!=="solo"){if(D.players.length<12)g.append(btn("+ Player",()=>{D.players.push({name:"Player "+(D.players.length+1)});go("setup",null,true)},"opt"));
    if(D.players.length>(D.mode==="teams"?0:2))g.append(btn("− Player",()=>{D.players.pop();go("setup",null,true)},"opt"))}
   pr.append(g);if(D.mode==="teams")pr.append(el("small",0,"Press a player's team to move them. Names are optional."));f.append(pr)}
 f.append(choice("Rounds",[[5,"5"],[10,"10"],[15,"15"],[20,"20"]],D.rounds,v=>{D.rounds=+v}));
 f.append(choice("Difficulty",Object.entries(H.difficulties).map(([k,v])=>[k,v.name]),D.difficulty,v=>{D.difficulty=v;note.textContent=diffNote(v)}));
 const note=el("small","rl-diff",diffNote(D.difficulty));f.lastChild.append(note);
 const cr=el("div","rl-row");cr.append(el("label",0,"Films"));const cg=el("div","seg"),cn=el("b","num","...");
 cg.append(cn,btn("Choose categories",()=>{catCtx={keys:D.categories.slice(),logic:D.logic,done:(k,l)=>{D.categories=k;D.logic=l}};go("cats")},"opt"));
 if(D.categories.length)cg.append(btn("All films",()=>{D.categories=[];go("setup",null,true)},"opt"));cr.append(cg);f.append(cr);
 call("count?logic="+D.logic+"&keys="+encodeURIComponent(D.categories.join("|"))).then(j=>{cn.textContent=D.categories.length?`${j.count} of ${plural(j.total,"film")}`:`All ${plural(j.total,"film")}`;if(!j.count)startB.disabled=true}).catch(()=>{cn.textContent=""});
 f.append(choice("Answers",[["both","Typed or said out loud"],["choice","Multiple choice"],["typed","Typed only"],["host","Said out loud, host decides"]],D.answers,v=>{D.answers=v},"Multiple choice shows four titles to pick from."));
 if(D.mode!=="solo")f.append(choice("Phones",[[1,"Players can join on their phones"],[0,"TV only"]],D.phones?1:0,v=>{D.phones=!!+v},H.lan?"The TV shows a code. Phones on your WiFi open the address and type it.":"To use phones, first switch on Settings > Other devices in HERO TV, then come back."));
 if(D.full){
  f.append(choice("Time to guess",[["auto","From difficulty"],[15,"15 s"],[30,"30 s"],[45,"45 s"],[60,"60 s"],[0,"No limit"]],D.timer,v=>{D.timer=v==="auto"?v:+v}));
  f.append(choice("Hints",[[1,"On"],[0,"Off"]],D.hints?1:0,v=>{D.hints=!!+v}));
  f.append(choice("The moment",[["random","Chosen at random"],["choose","The guesser picks where"]],D.scene,v=>{D.scene=v}));
  f.append(choice("Show",[["still","A still picture"],["clip","A short clip, then the picture"]],D.show,v=>{D.show=v}))}
 b.append(f);const bar=el("div","rl-bar");const startB=btn("Start the game",()=>start(payload(D)),"big go");
 bar.append(startB,btn(D.full?"Fewer choices":"More choices",()=>go("setup",!D.full,true)),btn("Back",()=>{draft=null;goBack()}));b.append(bar,foot([["↑ ↓ ← →","move"],["Enter","choose"],["Esc","back"]]));
 focusFirst(".rl-bar .go")},

/* ---------------------------------------------------------------- categories */
async cats(){const C=catCtx;let d;const b=clear("form cats");b.append(head("Categories",C.save?"Films for a new game come from these. Choose none for every film.":"Choose what this game draws from. Choose none for every film."));
 try{d=await call("categories")}catch(e){b.append(el("p","rl-empty",String(e.message||e)),btn("Back",()=>goBack(),"go"));return focusFirst()}
 const top=el("div","rl-catbar"),cnt=el("b","num",""),lg=el("div","seg");
 const count=()=>call("count?logic="+C.logic+"&keys="+encodeURIComponent(C.keys.join("|"))).then(j=>{cnt.textContent=C.keys.length?`${plural(j.count,"film")} can come up`:`All ${plural(j.total,"film")} can come up`;cnt.classList.toggle("bad",!j.count)}).catch(()=>{});
 for(const[v,t]of[["any","In any of them"],["all","In all of them"]]){const x=btn(t,()=>{C.logic=v;$$("button",lg).forEach(y=>y.classList.toggle("on",y===x));count()},"opt"+(C.logic===v?" on":""));lg.append(x)}
 top.append(cnt,lg);b.append(top);const wrap=el("div","rl-cats");
 const chip=it=>{const x=btn(it.name,()=>{const i=C.keys.indexOf(it.key);if(i>=0)C.keys.splice(i,1);else C.keys.push(it.key);x.classList.toggle("on",i<0);count()},"chip"+(C.keys.includes(it.key)?" on":""));x.append(el("i",0,String(it.count)));return x};
 if(d.custom.length){const sec=el("section");sec.append(el("h3",0,"Your categories"));const g=el("div","chips");
   for(const c of d.custom){const w=el("span","mine");w.append(chip(c),btn("Rename",()=>nameBox("New name for "+c.name,c.name,async n=>{await call("categories",{op:"rename",id:c.id,name:n});go("cats",null,true)}),"tiny"),
     btn("Delete",async()=>{await call("categories",{op:"delete",id:c.id});C.keys=C.keys.filter(k=>k!==c.key);say("Deleted "+c.name);go("cats",null,true)},"tiny"));g.append(w)}sec.append(g);wrap.append(sec)}
 for(const grp of d.groups){const sec=el("section");sec.append(el("h3",0,grp.title));const g=el("div","chips");const many=grp.items.length>24;
   grp.items.slice(0,many?24:999).forEach(it=>g.append(chip(it)));
   if(many){const more=btn(`Show all ${grp.items.length}`,()=>{more.remove();grp.items.slice(24).forEach(it=>g.append(chip(it)))},"tiny");g.append(more)}sec.append(g);wrap.append(sec)}
 if(!d.groups.length)wrap.append(el("p","rl-empty",d.total?"Your films have no details from TMDB yet, so there are no categories. Add a free TMDB key in Settings > Cover art.":"There are no films in your library yet."));
 b.append(wrap);const bar=el("div","rl-bar");
 bar.append(btn("Done",async()=>{if(C.save){S=(await call("settings",{categories:C.keys,logic:C.logic})).settings}else C.done(C.keys,C.logic);goBack()},"big go"),
  btn("Save as my category",()=>{const own=C.keys.filter(k=>!k.startsWith("custom:"));if(!own.length)return say("Choose one or more categories first.");nameBox("Name this category","",async n=>{const r=await call("categories",{op:"create",name:n,keys:own,logic:C.logic});C.keys=["custom:"+r.id];go("cats",null,true)})}),
  btn("Clear",()=>{C.keys=[];go("cats",null,true)}));b.append(bar,foot([["↑ ↓ ← →","move"],["Enter","choose"],["Esc","back without changing"]]));count();focusFirst(".rl-bar .go")},

/* ---------------------------------------------------------------- settings */
async settings(){if(!S)await loadHome();const b=clear("form");b.append(head("Game settings","These are the starting choices for every new game. Changes are saved straight away."));
 const set=async p=>{try{S=(await call("settings",p)).settings}catch(e){say(String(e.message||e));go("settings",null,true)}};const f=el("div","rl-form scroll");
 const sec=t=>f.append(el("h3",0,t));
 sec("The game");
 f.append(choice("Usual game",Object.entries(H.modes),S.mode,v=>set({mode:v})));
 f.append(choice("Rounds",[[5,"5"],[10,"10"],[15,"15"],[20,"20"]],S.rounds,v=>set({rounds:+v})));
 f.append(choice("Difficulty",Object.entries(H.difficulties).map(([k,v])=>[k,v.name]),S.difficulty,v=>set({difficulty:v}),"Easy shows clearer moments from the middle of the film and gives more time. Expert shows a close-up and one hint."));
 f.append(choice("Time to guess",[["auto","From difficulty"],[15,"15 s"],[30,"30 s"],[45,"45 s"],[60,"60 s"],[0,"No limit"]],S.timer,v=>set({timer:v==="auto"?v:+v})));
 f.append(choice("When time runs out",[["reveal","Show the answer"],["last","One last answer first"]],S.after_time,v=>set({after_time:v})));
 f.append(choice("Same film again",[["days30","Not for 30 days"],["game","Not in the same game"],["none","Allowed when films run out"]],S.repeat,v=>set({repeat:v})));
 sec("The picture");
 f.append(choice("The moment",[["random","Chosen at random"],["choose","The guesser picks where"]],S.scene,v=>set({scene:v}),"Opening logos and end credits are left out either way."));
 f.append(choice("Show",[["still","A still picture"],["clip","A short clip, then the picture"]],S.show,v=>set({show:v}),"Clips need a film this screen can play; others show the picture."));
 f.append(stepper("Clip length",S.clip_seconds,5,60,5,v=>set({clip_seconds:v}),v=>v+" s"));
 f.append(choice("Picture effect",[["auto","From difficulty"],["none","None"],["blur","Blurred, clears slowly"],["zoom","Close-up, pulls back"]],S.effect,v=>set({effect:v})));
 sec("Answers and hints");
 f.append(choice("Answers",[["both","Typed or said out loud"],["choice","Multiple choice"],["typed","Typed only"],["host","Said out loud, host decides"]],S.answers,v=>set({answers:v})));
 f.append(choice("Phones",[[1,"Players can join on their phones"],[0,"TV only"]],S.phones?1:0,v=>set({phones:!!+v}),H.lan?"":"Needs Settings > Other devices switched on in HERO TV."));
 f.append(choice("Small spelling mistakes",[[1,"Still count"],[0,"Must be exact"]],S.spelling?1:0,v=>set({spelling:!!+v})));
 f.append(choice("Hints",[[1,"On"],[0,"Off"]],S.hints?1:0,v=>set({hints:!!+v})));
 { const row=el("div","rl-row");row.append(el("label",0,"Kinds of hint"));const g=el("div","seg");const names={decade:"Decade",genre:"Genre",frame:"Another picture",actor:"An actor",words:"Words in the title",director:"Director",letter:"First letter",franchise:"Film series"};
   for(const k of H.hint_kinds){const x=btn(names[k],()=>{const on=!S.hint_kinds.includes(k);x.classList.toggle("on",on);set({hint_kinds:on?[...S.hint_kinds,k]:S.hint_kinds.filter(y=>y!==k)})},"opt"+(S.hint_kinds.includes(k)?" on":""));g.append(x)}
   row.append(g,el("small",0,"Given in this order, mildest first."));f.append(row)}
 sec("Points");
 ["No hints","After one hint","After two hints","After three hints"].forEach((t,i)=>f.append(stepper(t,S.points[i],0,1000,5,v=>{const p=S.points.slice();p[i]=v;set({points:p})})));
 f.append(choice("Speed bonus",[[1,"On"],[0,"Off"]],S.speed_bonus?1:0,v=>set({speed_bonus:!!+v}),"Extra points for a fast answer, shrinking as the clock runs down."));
 f.append(stepper("Biggest speed bonus",S.speed_max,0,500,5,v=>set({speed_max:v})));
 f.append(stepper("Points lost for a wrong answer",S.wrong_penalty,0,500,5,v=>set({wrong_penalty:v})));
 sec("Sound and screen");
 f.append(choice("Sound effects",[[1,"On"],[0,"Off"]],S.sounds?1:0,v=>set({sounds:!!+v})));
 f.append(choice("Animations",[[1,"On"],[0,"Off"]],S.animations?1:0,v=>set({animations:!!+v}).then(()=>box.classList.toggle("still",!S.animations))));
 f.append(choice("Fill the whole screen while playing",[[1,"Yes"],[0,"No"]],S.fullscreen?1:0,v=>set({fullscreen:!!+v})));
 sec("Keys during a game");
 { const names={timer:"Start or pause the clock",reveal:"Reveal the answer",next:"Next round",hint:"Show a hint",correct:"Mark correct",wrong:"Mark wrong",skip:"Skip this film"};
   for(const a of Object.keys(H.actions)){const row=el("div","rl-row");row.append(el("label",0,names[a]));const g=el("div","seg");const kb=btn(keyName(S.keys[a]),()=>{rebind={a,b:kb};kb.firstChild.textContent="Press a key...";kb.classList.add("on")},"opt key");g.append(kb);row.append(g);f.append(row)}
   const row=el("div","rl-row");row.append(el("label",0,""));const g=el("div","seg");g.append(btn("Put the keys back",async()=>{await set({keys:H.actions});go("settings",null,true)},"opt"));row.append(g,el("small",0,"Enter always sends a typed answer and Esc always opens the pause menu. A game controller works too: A chooses, B goes back, X reveals, Y gives a hint."));f.append(row)}
 b.append(f);const bar=el("div","rl-bar");bar.append(btn("Done",()=>goBack(),"big go"));b.append(bar,foot([["↑ ↓ ← →","move"],["Enter","change"],["Esc","back"]]));focusFirst(".rl-form button")},

/* ---------------------------------------------------------------- how to play, history */
async how(){if(!S)await loadHome();const b=clear("form");b.append(head("How to play"));const o=el("ol","rl-how");const K=S.keys,k=a=>keyName(K[a]);
 for(const[t,s]of[["A moment appears","A random film from your library, at a random moment. No title, no clues."],["Name the film","Type it and press Enter, or just say it out loud. Small spelling mistakes are fine."],
  ["Stuck? Take a hint",`Press ${k("hint")}. Each hint is worth less: 100 points with none, then 75, 50 and 25.`],["See the answer",`Press ${k("reveal")} to reveal. If someone said it, press their number to give them the points.`],
  ["Next round",`Press ${k("next")}. Most points after the last round wins.`]]){const li=el("li");li.append(el("b",0,t),el("span",0,s));o.append(li)}
 const keys=el("div","rl-keys");for(const[a,t]of[[k("timer"),"start or pause the clock"],["Enter","send a typed answer"],[k("hint"),"hint"],[k("reveal"),"reveal"],[k("correct")+" / "+k("wrong"),"mark an answer said out loud"],["1 - 9","who is answering"],[k("skip"),"skip a film nobody knows"],[k("next"),"next round"],["Esc","pause menu"]]){keys.append(el("kbd",0,a),el("span",0,t))}
 b.append(o,keys);const bar=el("div","rl-bar");bar.append(btn("Got it",()=>goBack(),"big go"));b.append(bar);focusFirst()},
async history(id){const b=clear("form");let d;
 try{d=id?await call("history/"+id):await call("history")}catch(e){b.append(head("History"),el("p","rl-empty",String(e.message||e)));const bar=el("div","rl-bar");bar.append(btn("Back",()=>goBack(),"big go"));b.append(bar);return focusFirst()}
 const when=t=>new Date(t*1e3).toLocaleDateString([],{weekday:"short",month:"short",day:"numeric"});
 if(id){b.append(head("Game on "+when(d.created),`${H.modes[d.mode]||""} · ${plural(d.played,"round")} · ${d.winners.length?"Won by "+d.winners.join(" and "):d.status==="abandoned"?"Not finished":"No winner"}`));
  const t=el("div","rl-table");d.rounds_list.filter(r=>r.status!=="skipped"||r.title).forEach(r=>{const row=el("div","tr"+(r.status==="skipped"?" dim":""));row.append(el("span",0,r.status==="skipped"?"–":String(r.number)),el("b",0,r.title+(r.year?" ("+r.year+")":"")),el("span",0,"at "+hms(r.at)),el("span",0,r.status==="skipped"?"skipped":r.winner?r.winner+" +"+r.points:"nobody"));t.append(row)});
  b.append(scoreList(d.board),t)}
 else{b.append(head("History","Every game you have played."));const t=el("div","rl-table");
  if(!d.games.length)t.append(el("p","rl-empty","No games yet. Play one and it shows up here."));
  for(const g of d.games){const row=btn("",()=>go("history",g.id),"tr");row.textContent="";row.append(el("span",0,when(g.created)),el("b",0,g.winners.length?g.winners.join(" and ")+" won":g.status==="abandoned"?"Not finished":"No winner"),
    el("span",0,(H&&H.modes[g.mode]||g.mode)+" · "+plural(g.played,"round")),el("span",0,g.board.map(s=>s.name+" "+s.points).join(" · ")));t.append(row)}b.append(t)}
 const bar=el("div","rl-bar");bar.append(btn("Back",()=>goBack(),"big go"));b.append(bar,foot([["↑ ↓","move"],["Enter","open"],["Esc","back"]]));focusFirst(id?"":".rl-table button")},
game(){drawGame(true)}};
function diffNote(k){const d=H.difficulties[k];return `${d.timer} seconds, ${d.hints===1?"1 hint":d.hints+" hints"}`+({easy:" · clearer moments",normal:"",hard:" · any moment, plainer pictures",expert:" · a close-up that slowly pulls back"}[k]||"")}
function payload(D){const p={mode:D.mode,rounds:D.rounds,difficulty:D.difficulty,answers:D.answers,phones:!!D.phones,lobby:true,categories:D.categories,logic:D.logic,players:D.players.filter(x=>x.name.trim()).map(x=>D.mode==="teams"?{name:x.name,team:x.team}:{name:x.name}),teams:D.teams.filter(x=>x.name.trim())};
 if(D.full)Object.assign(p,{timer:D.timer,hints:D.hints,scene:D.scene,show:D.show});return p}
function nameBox(title,val,done){const m=el("div","rl-modal");const c=el("div","card");const inp=el("input");inp.value=val||"";inp.maxLength=40;c.append(el("h3",0,title),inp);const bar=el("div","rl-bar");
 const ok=btn("Save",async()=>{const n=inp.value.trim();if(!n)return say("Type a name first.");m.remove();menu=null;await done(n)},"go");{const x=btn("Cancel",()=>{m.remove();menu=null;focusFirst()});x.dataset.esc=1;bar.append(ok,x)}c.append(bar);m.append(c);box.append(m);menu=m;
 setTimeout(()=>{inp.focus();inp.select()},0)}
function scoreList(board,winners){const s=el("div","rl-final");board.forEach(x=>{const r=el("div","sc"+(winners&&x.rank===1&&x.points>0?" win":""));r.style.setProperty("--c",x.color||"#ffcf1f");
  r.append(el("i",0,(x.tied?"=":"")+x.rank),el("b",0,x.name),el("span",0,x.players&&x.players.length?x.players.join(", "):plural(x.correct,"film")),el("em",0,String(x.points)));s.append(r)});return s}

/* ---------------------------------------------------------------- starting, resuming, leaving */
async function start(body){if(busy)return;busy=true;spin("Shuffling your films...");try{const j=await call("new",body);G=j.game;sideSel=null;sig="";inLobby=!G.round;if(S.fullscreen&&!document.fullscreenElement&&document.documentElement.requestFullscreen)document.documentElement.requestFullscreen().catch(()=>{});scr="game";drawGame(true)}
 catch(e){say(String(e.message||e));go(scr==="setup"?"setup":"landing",null,true)}finally{busy=false}}
async function resume(){try{const j=await call("game");if(!j.game)return go("landing",null,true);G=j.game;sig="";sideSel=null;scr="game";inLobby=!G.round&&!G.played&&!!G.join;if(!G.round&&G.status==="active"&&!inLobby)return act("next");drawGame(true)}catch(e){say(String(e.message||e))}}
function spin(text){const b=clear("spin");const w=el("div","rl-spin");w.append(el("div","rl-wheel big"),el("h2",0,text));b.append(w);sfx.spin()}
async function act(op,extra,quiet){if(busy||!G)return;busy=true;const slow=op==="next"||op==="time";let spinT=0;
 if(slow)spinT=setTimeout(()=>{if(op==="next")spin(G.played>=G.rounds?"Counting the points...":"Picking a film...")},op==="next"?0:400);
 try{const j=await call("act",Object.assign({game:G.id,op},extra||{}));const was=G;G=j.game;clearTimeout(spinT);
  if(op==="guess"||op==="choose"){const v=j.verdict;if(v==="correct")sfx.right();else if(v==="close"){sfx.hint();flash("Close! Be more exact.","warn")}else{sfx.wrong();flash("Not that one.","bad")}}
  else if(op==="correct")sfx.right();else if(op==="wrong"){sfx.wrong();flash("Not that one.","bad")}else if(op==="hint")sfx.hint();else if(op==="reveal"||op==="skip")sfx.reveal();
  if(G.status!=="active"&&was.status==="active"&&G.winners)sfx.win();
  seenGuesses=G.round?G.round.guesses.length:0;
  drawGame(slow||G.status!=="active");return j}
 catch(e){clearTimeout(spinT);if(!quiet)say(String(e.message||e));if(slow){try{G=(await call("game?id="+G.id)).game||G}catch(x){}drawGame(true)}}
 finally{busy=false;if(queued){const k=queued;queued="";setTimeout(()=>onKey({key:k,preventDefault(){},stopPropagation(){}}),0)}}}
function close(){if(!open)return;open=false;clearInterval(tickT);cancelAnimationFrame(padT);stopClip();if(document.fullscreenElement&&S&&S.fullscreen&&document.exitFullscreen)document.exitFullscreen().catch(()=>{});
 if(G&&G.status==="active"&&G.round&&G.round.timer.running)call("act",{game:G.id,op:"timer",do:"pause"}).catch(()=>{});
 box.className="";box.textContent="";scr="";const h=HT();if(h.leave)h.leave()}
function watch(item){const h=HT();open=false;clearInterval(tickT);cancelAnimationFrame(padT);stopClip();box.className="";box.textContent="";scr="";if(h.leave)h.leave(item)}

/* ---------------------------------------------------------------- the game screen */
function flash(text,cls){const f=$(".rl-flash",box);if(!f)return;f.textContent=text;f.className="rl-flash on "+(cls||"");clearTimeout(flash.t);flash.t=setTimeout(()=>{f.className="rl-flash"},1800)}
const sideOf=id=>G.sides.find(s=>s.id===id);
function answering(){const r=G.round;if(G.sides.length===1)return G.sides[0].id;return sideSel||(r&&r.turn)||null}
let fxAt=0,fxTok="";
function setClock(r){const t=r&&r.timer;clock={left:t?t.left:null,running:!!(t&&t.running),at:performance.now(),limit:t?t.limit:0};lastTick=-1;if(r&&r.token!==fxTok){fxTok=r.token;fxAt=performance.now()}}
const clockLeft=()=>clock.left==null?null:clock.running?Math.max(0,clock.left-(performance.now()-clock.at)/1e3):clock.left;
let clipV=null,clipT=0;
function stopClip(){clearTimeout(clipT);if(clipV){try{clipV.pause();clipV.removeAttribute("src");clipV.load()}catch(e){}clipV=null}}
function playClip(stage,r,after){stopClip();if(!r.clip)return after&&after();const v=el("video","rl-clip");v.playsInline=true;v.preload="auto";clipV=v;const done=()=>{if(clipV===v){stopClip();v.remove();stage.classList.remove("clip");if(after)after()}};
 v.addEventListener("loadedmetadata",()=>{try{v.currentTime=r.clip.start}catch(e){done()}});v.addEventListener("seeked",()=>{v.play().catch(done);clipT=setTimeout(done,r.clip.seconds*1e3)},{once:true});v.addEventListener("error",done);
 v.src=r.clip.src;stage.classList.add("clip");stage.append(v)}
function drawGame(force){if(!open||scr!=="game"||!G)return;
 if(G.status!=="active")return drawFinal();
 const r=G.round;if(!r&&inLobby&&G.join)return drawLobby();
 if(!r){busy=false;return act("next")}
 const s=[r.token,r.status,r.hints.length,r.frames.length,r.win.side||0,G.sides.map(x=>x.name).join(","),(r.out||[]).join(",")].join("|");
 if(!force&&(s===sig||menu)){setClock(r);paintBoard();paintTimer();return}   /* nothing new to draw (and never pull a menu out from under you) */
 const fa=document.activeElement,keepK=fa&&fa.tagName==="BUTTON"&&box.contains(fa)&&fa.dataset.k||"";
 sig=s;menu=null;stopClip();const b=clear("game "+r.status+(r.effect!=="none"?" fx-"+r.effect:""));const shown=r.status==="revealed"||r.status==="skipped";
 /* top: title, round, category, clock */
 const top=el("div","g-top");const tl=el("div","g-id");tl.append(el("small",0,"MOVIE ROULETTE"),el("b",0,`Round ${r.number} of ${G.rounds}`));
 const nc=G.config.categories.length,mid=el("div","g-cat",!nc?"All films":nc===1?"1 category":nc+" categories");
 if(G.join&&G.join.on){const jc=el("i","code","Join: "+G.join.code);mid.append(jc)}
 mid.append(el("i",0,G.difficulty.name));
 const tm=el("div","g-timer");tm.append(el("b"),el("span"));top.append(tl,mid,tm);b.append(top);
 /* centre: the picture */
 const stage=el("div","g-stage");const fr=el("div","g-frame");
 if(r.status==="pick"){fr.append(pickUI(r))}
 else{const img=new Image();img.alt="";img.className="g-img";img.decoding="async";const which=r.frames[shownFrame(r)]||r.frames[0];img.src=which;
  img.onerror=()=>{fr.classList.add("nopic");fr.append(el("p",0,"The picture could not be shown. Skip this film."))};
  {let h=0;for(const ch of r.token)h=(h*31+ch.charCodeAt(0))>>>0;img.style.transformOrigin=`${20+h%61}% ${25+(h>>8)%51}%`}
  const begin=()=>{if(G&&G.round&&G.round.token===r.token&&G.round.status==="guess"&&r.timer.limit&&!r.timer.running&&r.timer.left===r.timer.limit&&!clock.running&&!menu)act("timer",{do:"start"},true)};
  const clip=r.status==="guess"&&r.clip&&!clipSeen.has(r.token);
  img.onload=()=>{if(!clip)begin()};
  fr.append(img);if(r.frames.length>1&&!shown){const sw=el("div","g-pics");r.frames.forEach((f,i)=>{const t=btn(i?"Picture "+(i+1):"First picture",()=>{frameSel=i;sig="";drawGame(true)},"tiny"+(i===shownFrame(r)?" on":""));sw.append(t)});fr.append(sw)}
  if(clip){clipSeen.add(r.token);playClip(fr,r,begin)}}
 stage.append(fr);
 if(r.hints.length&&!shown){const hb=el("div","g-hints");r.hints.forEach((h,i)=>{const c=el("div","hint",h);c.prepend(el("i",0,"HINT "+(i+1)));hb.append(c)});stage.append(hb)}
 if(shown)stage.append(answerCard(r));
 stage.append(el("div","rl-flash"));b.append(stage);
 /* bottom: scores and controls */
 const bot=el("div","g-bot");bot.append(el("div","g-board"));const ctl=el("div","g-ctl");const K=S.keys;
 const typed=G.config.answers!=="host",host=G.config.answers!=="typed";
 if(r.status==="guess"||r.status==="timeup"){
  const who=answering(),ws=who&&sideOf(who);
  const line=el("div","g-who");
  if(r.status==="timeup")line.append(el("b","up","Time is up! One last answer."));
  else if(G.sides.length>1)line.append(el("b",0,ws?(G.config.mode==="party"?ws.name+" is answering":ws.name+(r.turn===who?"'s turn":" is answering")):"Who knows it? Press their number."));
  else line.append(el("b",0,ws.name+", what film is this?"));
  line.append(el("span",0,r.would_score?`Worth ${r.would_score} points`:""));ctl.append(line);
  const row=el("div","g-row");
  if(r.choices){row.className="g-row g-choices";const outMe=who&&(r.out||[]).includes(who);
   r.choices.forEach((t,i)=>{const cb=btn(t,()=>pickChoice(i),"pick",["a","b","c","d"][i]);cb.disabled=!!outMe;row.append(cb)})}
  else if(typed){const inp=el("input","g-in");inp.placeholder="Type the film's name";inp.autocomplete="off";inp.spellcheck=false;inp.maxLength=120;inp.value=draftGuess;inp.oninput=()=>{draftGuess=inp.value};row.append(inp,btn("Guess",()=>sendGuess(),"go"))}
  if(host&&G.sides.length>1&&!r.choices){row.append(kb("correct",btn("Correct",()=>mark(true),"ok",K.correct)),kb("wrong",btn("Wrong",()=>mark(false),"no",K.wrong)))}
  ctl.append(row);const row2=el("div","g-row small");
  if(r.timer.limit&&r.status==="guess"){const cb=btn(r.timer.running?"Pause":"Start clock",()=>act("timer",{do:clock.running?"pause":"resume"}),"",K.timer);cb.dataset.act="clock";row2.append(kb("timer",cb))}
  if(G.difficulty.hints>0){const hb=btn(r.hints_left?`Hint (${r.hints_left} left)`:"No hints left",()=>act("hint"),"",K.hint);hb.disabled=!r.hints_left;row2.append(kb("hint",hb))}
  row2.append(kb("reveal",btn("Reveal answer",()=>act("reveal"),"",K.reveal)),kb("skip",btn("Skip film",()=>act("skip"),"",K.skip)));ctl.append(row2)}
 else if(r.status==="pick"){ctl.append(el("div","g-who"));$(".g-who",ctl).append(el("b",0,(sideOf(r.turn||0)||G.sides[0]).name+(G.config.mode==="party"?"":", ")+"choose where in the film to look"),el("span",0,"You will not see it until you choose."))}
 else{const line=el("div","g-who");const w=r.win.side&&sideOf(r.win.side);
  if(r.status==="skipped")line.append(el("b",0,"Skipped. This one does not count."));
  else if(w)line.append(el("b","won",`${w.name} got it: +${r.win.points}`),el("span",0,r.win.speed?`${r.win.base} + ${r.win.speed} for speed`:r.win.hints?plural(r.win.hints,"hint")+" used":"No hints used"));
  else line.append(el("b",0,G.sides.length>1?"Did someone get it? Press their number.":"Nobody got this one."),el("span",0,""));
  ctl.append(line);const row=el("div","g-row");
  row.append(btn(G.last_round&&r.status!=="skipped"?"See who won":"Next round",()=>{draftGuess="";frameSel=0;sideSel=null;return act("next")},"go",K.next));
  if(r.status==="revealed"&&!w&&G.sides.length===1)row.append(btn("I got it",()=>act("correct",{side:G.sides[0].id}),"ok",K.correct));
  if(w)row.append(btn("Undo",()=>act("undo")));
  if(r.answer&&r.answer.item)row.append(btn("Watch this film",()=>confirmBox("Leave the game and watch "+r.answer.title+"?","The game is kept. Choose Continue game to come back to it.","Watch it",()=>watch(r.answer.item))));
  ctl.append(row)}
 bot.append(ctl);b.append(bot,foot(gameHints(r)));setClock(r);paintBoard();paintTimer();
 const live=r.status==="guess"||r.status==="timeup",kept=live&&keepK&&$(`.g-ctl [data-k="${keepK}"]:not(:disabled)`,box)||live&&keepK&&$(".g-ctl .small button:not(:disabled)",box);
 if(kept)kept.focus({preventScroll:true});   /* you had moved to the buttons: stay there, so the letter keys keep working */
 else focusFirst(live&&r.choices?".g-choices button:not(:disabled), .g-ctl .small button":live&&typed&&(G.sides.length===1||answering())?".g-in":r.status==="pick"?".g-pick .go":".g-ctl .go, .g-ctl .ok, .g-ctl button");
 if(shown&&force)box.classList.add("justshown")}
let queued="",draftGuess="",frameSel=0;const clipSeen=new Set(),kb=(k,b)=>{b.dataset.k=k;return b};
const shownFrame=r=>Math.min(frameSel,r.frames.length-1);
function gameHints(r){const K=S.keys,k=a=>keyName(K[a]);if(r.status==="pick")return[["← →","move"],["Enter","choose"],["Esc","pause"]];
 if(r.status==="guess"||r.status==="timeup"){const h=[];if(r.choices)h.push(["A - D","pick a title"]);else if(G.config.answers!=="host")h.push(["Enter","send your answer"],["Tab","buttons"]);if(G.sides.length>1)h.push(["1 - "+Math.min(9,G.sides.length),"who is answering"]);h.push([k("hint"),"hint"],[k("reveal"),"reveal"],["Esc","pause"]);return h}
 const h=[[k("next"),"next round"]];if(G.sides.length>1&&r.status==="revealed")h.push(["1 - "+Math.min(9,G.sides.length),"who got it"]);h.push(["Esc","pause"]);return h}
function paintBoard(){const bd=$(".g-board",box);if(!bd)return;bd.textContent="";const r=G.round,cur=r&&(r.status==="guess"||r.status==="timeup"||r.status==="pick")?answering():null;
 const order=G.sides.map(s=>G.board.find(x=>x.id===s.id));
 order.forEach((x,i)=>{const c=btn("",()=>{if(!G.round)return;if(G.round.status==="revealed"&&!G.round.win.side)return act("correct",{side:x.id});sideSel=x.id;sig="";drawGame(true)},"side"+(cur===x.id?" cur":"")+(r&&(r.out||[]).includes(x.id)&&r.status!=="revealed"?" out":"")+(r&&r.win.side===x.id?" got":"")+(x.rank===1&&x.points>0?" lead":""));
  c.textContent="";c.style.setProperty("--c",x.color);c.append(el("i",0,String(i+1)),el("b",0,x.name),el("em",0,String(x.points)));if(x.players&&x.players.length)c.title=x.players.join(", ");c.tabIndex=-1;bd.append(c)})}
function paintTimer(){const tm=$(".g-timer",box);if(!tm||!G||!G.round)return;const r=G.round,left=clockLeft(),b=tm.firstChild,sp=tm.lastChild;
 if(r.status==="revealed"||r.status==="skipped"||r.status==="pick"||left==null){tm.className="g-timer off";const open2=left==null&&(r.status==="guess"||r.status==="timeup");b.textContent=open2?"∞":"";sp.textContent=open2?"no time limit":"";fx(open2?Math.min(1,(performance.now()-fxAt)/3e4):1);return}
 const sec=Math.ceil(left);b.textContent=String(sec);sp.textContent=clock.running?"seconds":r.status==="timeup"?"time is up":"paused";
 tm.className="g-timer"+(clock.running?"":" paused")+(sec<=5?" low":"");{const cb=$("[data-act=clock] span",box);if(cb)cb.textContent=clock.running?"Pause":"Start clock"}tm.style.setProperty("--p",clock.limit?String(left/clock.limit):"1");
 fx(clock.limit?1-left/clock.limit:1);
 if(clock.running&&sec<=5&&sec>0&&sec!==lastTick){lastTick=sec;sfx.tick()}
 if(clock.running&&left<=0&&sentUp!==r.token){sentUp=r.token;sfx.up();busy=false;act("timer",{do:"up"},true)}}
function fx(p){const img=$(".g-img",box);if(!img||!G.round)return;const e=G.round.effect,shown=G.round.status==="revealed"||G.round.status==="skipped";p=shown?1:Math.max(0,Math.min(1,p));
 if(e==="blur")img.style.filter=p>=1?"":`blur(${((1-p)*2.6).toFixed(2)}vh)`;   /* fully clear only when the time is up */
 else if(e==="zoom"){const z=shown?1:3.2-1.8*p;img.style.transform=z<=1.01?"":`scale(${z.toFixed(3)})`}}   /* a close-up that pulls back, never all the way until the reveal */
function pickUI(r){const p=r.pick,w=el("div","g-pick");let val=Math.round((p.min+p.max)/2);const out=el("b","num",hms(val)),rg=el("input");rg.type="range";rg.min=Math.ceil(p.min);rg.max=Math.floor(p.max);rg.step=5;rg.value=val;
 rg.oninput=()=>{val=+rg.value;out.textContent=hms(val)};const scale=el("div","scale");scale.append(el("span",0,hms(p.min)),el("span",0,"the film is "+hms(p.runtime)+" long"),el("span",0,hms(p.max)));
 const bar=el("div","rl-bar");bar.append(btn("Show this moment",()=>act("time",{seconds:val}),"big go"),btn("Surprise me",()=>act("time",{}),"big"),btn("Skip film",()=>act("skip")));
 w.append(el("h2",0,"Where in the film?"),out,rg,scale,bar);return w}
function answerCard(r){const a=r.answer,c=el("div","g-answer");const p=el("div","a-post");if(a.media_id){const im=new Image();im.alt="";im.src="/poster/"+a.media_id;im.onerror=()=>{im.remove();p.classList.add("none")};p.append(im)}else p.classList.add("none");
 const t=el("div","txt");t.append(el("small",0,r.status==="skipped"?"IT WAS":"THE FILM IS"),el("h2",0,a.title));
 t.append(el("div","meta",[a.year,a.minutes?a.minutes+" min":"",a.rating?"★ "+Number(a.rating).toFixed(1):"",(a.genres||[]).join(", ")].filter(Boolean).join(" · ")));
 if(a.directors&&a.directors.length)t.append(el("div","who","Directed by "+a.directors.join(" and ")));
 if(a.cast&&a.cast.length)t.append(el("div","who","With "+a.cast.join(", ")));
 if(a.tagline)t.append(el("p",0,"“"+a.tagline.replace(/^["“]|["”]$/g,"")+"”"));
 t.append(el("div","at","This moment is "+hms(a.at)+" into the film."));c.append(p,t);return c}
function sendGuess(){const inp=$(".g-in",box);const text=(inp?inp.value:draftGuess).trim();if(!text)return say("Type the film's name first.");
 const who=answering();if(!who)return say("Press a player's number first, so the points go to the right person.");draftGuess="";if(inp)inp.value="";return act("guess",{text,side:who})}
function pickChoice(i){const who=answering();if(!who)return say("Press a player's number first, so the points go to the right person.");if((G.round.out||[]).includes(who))return say(sideOf(who).name+" is out until the next film.");return act("choose",{choice:i,side:who})}
function mark(ok){const who=answering();if(!who)return say("Press a player's number first.");return act(ok?"correct":"wrong",{side:who})}
function drawFinal(){stopClip();sig="";const b=clear("final");const w=G.winners||[],tie=w.length>1;
 const hero=el("div","rl-hero");hero.append(el("small",0,w.length?(tie?"IT'S A TIE":"THE WINNER IS"):"GAME OVER"));
 hero.append(el("h1",0,w.length?w.map(x=>x.name).join(" & "):G.played?"Nobody scored":"No rounds played"));
 if(w.length)hero.append(el("p",0,`${w[0].points} points · ${plural(w[0].correct,"film")} named`+(G.sides.length===1?` out of ${G.played}`:"")));
 if(G.note)hero.append(el("p","rl-note",G.note));
 hero.append(scoreList(G.board,true));const bar=el("div","rl-bar");
 bar.append(btn("Play again",()=>{const c=Object.assign({},G.config);delete c.note;delete c.code;c.lobby=true;return start(c)},"big go"),btn("New game",()=>{draft=null;back=[];go("setup",true)},"big"),btn("See the rounds",()=>{back=["landing"];scr="";go("history",G.id)}),btn("Back to "+(HT().name||"HERO TV"),()=>close()));
 hero.append(bar);b.append(hero);if(w.length&&S.animations)confetti(b);focusFirst()}
function confetti(b){const c=el("div","rl-confetti");const cols=["#ffcf1f","#ff5d73","#4cc9f0","#7bd389","#c77dff","#ff9f1c"];for(let i=0;i<70;i++){const p=el("i");p.style.cssText=`left:${Math.random()*100}%;background:${cols[i%cols.length]};animation-delay:${(Math.random()*2.5).toFixed(2)}s;animation-duration:${(3+Math.random()*3).toFixed(2)}s;transform:rotate(${Math.random()*360}deg)`;c.append(p)}b.append(c)}

/* ---------------------------------------------------------------- phones: the lobby, the join card, and keeping up with them */
let inLobby=false,pollT=0,seenGuesses=0;
function joinCard(j){const w=el("div","rl-join");
 if(!j.on||!j.url){w.append(el("p",0,"Phones cannot join yet. In HERO TV, open Settings > Other devices and switch it on, then start a new game."));return w}
 const q=el("div","qr");q.innerHTML=j.qr||"";const t=el("div","how");
 t.append(el("small",0,"ON YOUR PHONE"),el("p",0,"Point the camera at the square. Or open"),el("b","url",j.url.replace(/^http:\/\//,"")),el("p",0,"and type this code:"),el("b","code",j.code),el("small",0,"The phone must be on the same WiFi as this PC."));
 w.append(q,t);return w}
function drawLobby(){sig="lobby";stopClip();const b=clear("form lobby");b.append(head("Who is playing?","Players can join on their phones now, or later from the pause menu. Players without a phone can still shout their answers."));
 const wrap=el("div","rl-lobby");wrap.append(joinCard(G.join));const list=el("div","who");list.append(el("h3",0,"Players"));
 const phones=new Set(G.join.players.map(p=>p.side));for(const s of G.sides){const r=el("div","sc");r.style.setProperty("--c",s.color);r.append(el("b",0,s.name),el("span",0,(s.players&&s.players.length?s.players.join(", ")+" · ":"")+(phones.has(s.id)?"phone joined":"on the TV")));list.append(r)}
 wrap.append(list);b.append(wrap);const bar=el("div","rl-bar");bar.append(btn("Start the game",()=>{inLobby=false;return act("next")},"big go"),btn("Leave",()=>close()));b.append(bar,foot([["Enter","start"],["Esc","leave (the game is kept)"]]));focusFirst()}
function joinBox(){const m=el("div","rl-modal"),c=el("div","card wide");c.append(el("h3",0,"Add a phone"),joinCard(G.join));const bar=el("div","rl-bar");const ok=btn("Done",()=>{m.remove();menu=null;sig="";drawGame(true)},"go");ok.dataset.esc=1;bar.append(ok);c.append(bar);m.append(c);box.append(m);menu=m;ok.focus()}
async function pollGame(){if(!open||scr!=="game"||!G||G.status!=="active"||!G.join||!G.join.on||busy)return;let j;try{j=await call("game?id="+G.id)}catch(e){return}
 if(busy||!j.game||!open||scr!=="game")return;const was=G;G=j.game;const r=G.round,n=r?r.guesses.length:0,same=r&&was.round&&was.round.token===r.token;
 if(same&&n>seenGuesses){const g=r.guesses[n-1],s=sideOf(g.side);if(g.verdict==="wrong"){sfx.wrong();flash((s?s.name+": ":"")+"not that one","bad")}else if(g.verdict==="close")flash((s?s.name+": ":"")+"close!","warn")}
 if(same&&r.win.side&&!was.round.win.side)sfx.right();
 if(same&&r.status==="revealed"&&was.round.status!=="revealed"&&!r.win.side)sfx.reveal();
 seenGuesses=n;if(G.status!=="active"&&G.winners)sfx.win();
 if(inLobby&&!G.round){if(JSON.stringify(G.sides)+G.join.players.length!==JSON.stringify(was.sides)+(was.join?was.join.players.length:0))drawLobby();return}
 drawGame(false)}

/* ---------------------------------------------------------------- pause menu and small dialogs */
let wasRunning=false;
function pauseMenu(){if(menu)return;const r0=G.round;wasRunning=clock.running||!!(r0&&r0.status==="guess"&&r0.timer.limit&&r0.timer.left===r0.timer.limit);if(wasRunning){clock.left=clockLeft();clock.running=false;call("act",{game:G.id,op:"timer",do:"pause"}).then(j=>{G=j.game}).catch(()=>{})}
 const m=el("div","rl-modal"),c=el("div","card");c.append(el("h3",0,"Paused"),el("p",0,`Round ${G.round?G.round.number:G.played} of ${G.rounds}`));const col=el("div","col");
 const done=()=>{m.remove();menu=null};
 const co=btn("Carry on",async()=>{done();sig="";drawGame(true);if(wasRunning&&G.round&&G.round.status==="guess")await act("timer",{do:"resume"})},"go");co.dataset.esc=1;
 col.append(co,
  btn("Change the scores",()=>{done();scoreMenu()}),...(G.join?[btn("Add a phone",()=>{done();joinBox()})]:[]),btn("How to play",()=>{done();back=["__game"];go("how",null,true)}),
  btn("End the game now",()=>{done();confirmBox("End the game now?","The scores so far decide the winner.","End the game",()=>act("finish"))}),
  btn("Leave and come back later",()=>{done();close()}));c.append(col);m.append(c);box.append(m);menu=m;$("button",col).focus()}
function scoreMenu(){const m=el("div","rl-modal"),c=el("div","card wide");c.append(el("h3",0,"Change the scores"),el("p",0,"For a mistake, or a bonus you want to give."));const col=el("div","col");
 const draw=()=>{col.textContent="";for(const s of G.sides){const x=G.board.find(y=>y.id===s.id),row=el("div","adj");row.append(el("b",0,s.name),el("em",0,String(x.points)));
   for(const d of[-25,-5,5,25])row.append(btn((d>0?"+":"−")+Math.abs(d),async()=>{const j=await call("act",{game:G.id,op:"adjust",side:s.id,points:d,nonce:Date.now()+"-"+Math.random().toString(36).slice(2)});G=j.game;draw();paintBoard()},"opt"));col.append(row)}
  const dn=btn("Done",()=>{m.remove();menu=null;sig="";drawGame(true)},"go");dn.dataset.esc=1;col.append(dn);dn.focus()};
 c.append(col);m.append(c);box.append(m);menu=m;draw()}
function confirmBox(title,text,yes,fn){const m=el("div","rl-modal"),c=el("div","card");c.append(el("h3",0,title),el("p",0,text));const bar=el("div","rl-bar");
 const no=btn("No, stay",()=>{m.remove();menu=null;focusFirst(".g-ctl .go")},"go");no.dataset.esc=1;
 bar.append(no,btn(yes,()=>{m.remove();menu=null;return fn()}));c.append(bar);m.append(c);box.append(m);menu=m;$("button",bar).focus()}

/* ---------------------------------------------------------------- keys, arrows and controllers */
function focusables(){const root=menu||box;return $$("button:not(:disabled):not([tabindex='-1']),input,select",root).filter(e=>e.offsetParent!==null)}
function move(dir){const list=focusables();if(!list.length)return;const a=document.activeElement;if(!a||!list.includes(a)){list[0].focus();return}
 const r=a.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height/2;let best=null,bs=1e9;
 for(const e of list){if(e===a)continue;const q=e.getBoundingClientRect(),x=q.left+q.width/2,y=q.top+q.height/2,dx=x-cx,dy=y-cy;
  let along,across;if(dir==="ArrowRight"){along=dx;across=Math.abs(dy)}else if(dir==="ArrowLeft"){along=-dx;across=Math.abs(dy)}else if(dir==="ArrowDown"){along=dy;across=Math.abs(dx)}else{along=-dy;across=Math.abs(dx)}
  const horiz=dir==="ArrowLeft"||dir==="ArrowRight";if(along<=2)continue;if(horiz&&across>Math.max(r.height,q.height)*.7)continue;
  const sc=along+across*(horiz?4:2.2);if(sc<bs){bs=sc;best=e}}
 if(best){best.focus({preventScroll:true});best.scrollIntoView({block:"nearest",behavior:S&&S.animations?"smooth":"auto"});sfx.move()}}
function onKey(e){if(!open)return;if(e.ctrlKey||e.metaKey||e.altKey)return;const k=e.key,a=document.activeElement,inField=a&&a.tagName==="INPUT"&&a.type!=="range",inRange=a&&a.tagName==="INPUT"&&a.type==="range";
 e.stopPropagation();
 if(rebind){e.preventDefault();const{a:name,b}=rebind;rebind=null;if(k==="Escape"){go("settings",null,true);return}if(["Enter","Tab","Shift","Control","Alt","Meta"].includes(k)||/^[0-9]$/.test(k)||k.startsWith("Arrow")){say("That key is already used. Pick another.");go("settings",null,true);return}
  const keys=Object.assign({},S.keys);keys[name]=k.length===1?k.toLowerCase():k;call("settings",{keys}).then(j=>{S=j.settings}).catch(x=>say(String(x.message||x))).finally(()=>go("settings",null,true));return}
 if(k==="F11")return;
 if(k==="Escape"||(k==="Backspace"&&!inField)){e.preventDefault();
  if(menu){const c=$("[data-esc]",menu);if(c)c.click();return}
  if(inField&&k==="Escape"&&scr==="game"){a.blur();return pauseMenu()}
  if(scr==="game")return G&&G.status==="active"&&!(inLobby&&!G.round)?pauseMenu():close();
  if(scr==="landing")return close();
  if(scr==="setup")draft=null;return goBack()}
 if(busy){if(k!=="Tab"){e.preventDefault();if(!inField&&scr==="game")queued=k}return}   /* a key pressed while HERO TV is answering is done right after */
 if(k.startsWith("Arrow")){if(inField&&(k==="ArrowLeft"||k==="ArrowRight"))return;if(inRange&&(k==="ArrowLeft"||k==="ArrowRight"))return;e.preventDefault();return move(k)}
 if(k==="Enter"){if(inField&&menu){e.preventDefault();const g=$(".go",menu);if(g)g.click();return}if(inField&&a.classList.contains("g-in")){e.preventDefault();return sendGuess()}if(inRange){e.preventDefault();const g=$(".g-pick .go",box);if(g)g.click()}return}
 if(k==="Tab"){if(scr==="game"&&inField){e.preventDefault();const t=$(".g-ctl .small button:not(:disabled)",box)||$(".g-ctl button",box);if(t)t.focus()}return}
 if(scr!=="game"||menu||!G||G.status!=="active"||!G.round)return;
 if(inField)return;                                             /* typing an answer: letters are letters */
 const r=G.round,K=S.keys,key=k.length===1?k.toLowerCase():k,live=r.status==="guess"||r.status==="timeup";
 if(/^[1-9]$/.test(k)&&G.sides.length>1){const s=G.sides[+k-1];if(!s)return;e.preventDefault();if(r.status==="revealed"&&!r.win.side)return act("correct",{side:s.id});if(live){sideSel=s.id;sig="";drawGame(true)}return}
 if(live&&r.choices&&"abcd".includes(key)&&key.length===1){const i="abcd".indexOf(key);if(i<r.choices.length){e.preventDefault();return pickChoice(i)}}
 const hit=Object.keys(K).find(a2=>K[a2]===key);if(!hit)return;e.preventDefault();
 if(hit==="timer"&&r.status==="guess"&&r.timer.limit)return act("timer",{do:clock.running?"pause":"resume"});
 if(hit==="hint"&&live&&r.hints_left)return act("hint");
 if(hit==="reveal"&&(live||r.status==="pick"))return act("reveal");
 if(hit==="skip"&&(live||r.status==="pick"))return act("skip");
 if(hit==="correct"){if(live&&G.config.answers!=="typed"&&G.sides.length>1)return mark(true);if(r.status==="revealed"&&!r.win.side&&G.sides.length===1)return act("correct",{side:G.sides[0].id})}
 if(hit==="wrong"&&live&&G.config.answers!=="typed"&&G.sides.length>1)return mark(false);
 if(hit==="next"&&(r.status==="revealed"||r.status==="skipped")){draftGuess="";frameSel=0;sideSel=null;return act("next")}}
addEventListener("keydown",onKey,true);
/* a game controller: the d-pad or stick moves, A chooses, B goes back, X reveals, Y gives a hint, Start is the clock */
function pad(){if(!open)return;padT=requestAnimationFrame(pad);const gp=(navigator.getGamepads?[...navigator.getGamepads()]:[]).find(Boolean);if(!gp)return;
 const B=i=>!!(gp.buttons[i]&&gp.buttons[i].pressed),ax=gp.axes||[],now={up:B(12)||ax[1]<-.6,down:B(13)||ax[1]>.6,left:B(14)||ax[0]<-.6,right:B(15)||ax[0]>.6,a:B(0),b:B(1),x:B(2),y:B(3),start:B(9),rb:B(5)};
 const fire=k=>{const a=document.activeElement;if(k==="Enter"&&a&&a.tagName==="BUTTON")return a.click();onKey({key:k,preventDefault(){},stopPropagation(){}})};
 const map={up:"ArrowUp",down:"ArrowDown",left:"ArrowLeft",right:"ArrowRight",a:"Enter",b:"Escape",x:S?S.keys.reveal:"r",y:S?S.keys.hint:"h",start:S?S.keys.timer:" ",rb:S?S.keys.next:"n"};
 for(const k in now){if(now[k]&&!padPrev[k]){const a=document.activeElement;if(a&&a.tagName==="INPUT"&&a.type!=="range"&&["x","y","start","rb"].includes(k))a.blur();fire(map[k])}}padPrev=now}

/* ---------------------------------------------------------------- open */
async function openGame(){const h=HT();if(h.remote&&h.remote())return say("Movie Roulette is played on the TV itself.");ensure();if(open)return;open=true;if(h.enter)h.enter();back=[];clearInterval(tickT);tickT=setInterval(()=>{if(open&&scr==="game"&&!menu)paintTimer()},100);clearInterval(pollT);pollT=setInterval(pollGame,1000);padT=requestAnimationFrame(pad);
 clear("landing");await SCREENS.landing();scr="landing"}
window.Roulette={open:openGame,close,isOpen:()=>open};
})();
