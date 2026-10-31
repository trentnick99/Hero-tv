/* HERO TV - the TV page. Loaded by index.html; styles are in app.css. */
(()=>{"use strict";
const $=s=>document.querySelector(s),v=$("#v"),root=document.documentElement;
let seq=0,cfg={tz:null},off=0,chans=[],allChans=[],emptyIds=new Set(),ci=0,slot=null,nextSlot=null,vod=null,layer="",numBuf="",osdT,numT,errs=[],lastPos=0,stall=0,nopic=0,prevCi=-1,started=false;
/* channels with nothing on them stay hidden until a video arrives (the Free Movies tile still finds its channel) */
let theme={name:"HERO TV",color:"#ffcf1f",tagline:"What do you want to watch?"};
const setChans=list=>{allChans=list;emptyIds=new Set(list.filter(c=>c.empty).map(c=>c.id));const shown=list.filter(c=>!c.empty);chans=shown.length?shown:list};
const nowS=()=>Date.now()/1e3+off,api=async(p,o)=>{const r=await fetch(p,o);if(!r.ok)throw new Error(p+" "+r.status);return r.json()};
const post=(p,b)=>fetch(p,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b),keepalive:true}).catch(()=>{});
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e};
const T=s=>new Intl.DateTimeFormat([],{hour:"numeric",minute:"2-digit",timeZone:cfg.tz||undefined}).format(s*1e3);
const label=s=>{if(!s)return"";if(!s.series)return s.title;const ep=`${s.series} ${s.season?"S"+s.season:""}E${s.episode}`,t=/^Episode \d+$/.test(s.title)?"":s.title;return t?ep+" · "+t:ep};
const mins=s=>Math.max(0,Math.round(s/60));
const hms=s=>{s=Math.max(0,Math.floor(s||0));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return(h?h+":"+String(m).padStart(2,"0"):m)+":"+String(x).padStart(2,"0")};
function show(id,on){$(id).classList.toggle("on",on)}
function msg(t,s){$("#m-t").textContent=t;$("#m-s").textContent=s||"";show("#msg",!!t&&layer!=="settings")}   /* never cover the Settings screen: it has buttons and fields to click */

/* ---- channel colors: every channel owns one accent; text color is picked for contrast ---- */
function onColor(hex){const m=/^#?([0-9a-f]{6})$/i.exec(hex||"");if(!m)return"#0b0d16";const n=parseInt(m[1],16),f=c=>{c/=255;return c<=.03928?c/12.92:Math.pow((c+.055)/1.055,2.4)};
 const L=.2126*f(n>>16)+.7152*f(n>>8&255)+.0722*f(n&255);return L>.3?"#0b0d16":"#ffffff"}
function paint(node,color){const c=/^#[0-9a-f]{6}$/i.test(color||"")?color:"#ffcf1f";node.style.setProperty("--accent",c);node.style.setProperty("--on",onColor(c))}
let REMOTE=false,MK="";   /* REMOTE = this is a phone/laptop on the home WiFi (watch-only); MK = its media key */
const withK=u=>REMOTE&&MK?u+(u.includes("?")?"&":"?")+"k="+encodeURIComponent(MK):u;
const COARSE=matchMedia("(pointer:coarse)").matches;
const thumb=(id,lazy)=>{const i=el("img");i.alt="";i.decoding="async";if(lazy)i.loading="lazy";i.src=withK("/thumb/"+id);i.onerror=()=>i.remove();return i};
/* one line-icon set (24x24, drawn with the station color) instead of emoji, which look different on every PC */
const ICONS={live:'<rect x="2.5" y="5.5" width="19" height="12.5" rx="2"/><path d="M8.5 21h7M12 18v3M8.5 2.5 12 5.5l3.5-3"/>',
 resume:'<circle cx="12" cy="12" r="9"/><path d="M10 8.6v6.8l5.6-3.4z"/>',
 new:'<path d="M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9zM18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
 ticket:'<path d="M3.5 7h17v3a2 2 0 0 0 0 4v3h-17v-3a2 2 0 0 0 0-4z"/><path d="M14 7.5v9" stroke-dasharray="1.6 1.8"/>',
 guide:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M3 14.5h18M9 9v11"/>',
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="M20.5 20.5 15.3 15.3"/>',
 star:'<path d="M12 3.6l2.6 5.3 5.8.9-4.2 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.2-4.1 5.8-.9z"/>',
 gift:'<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M5 12v8.5h14V12M12 8v12.5M12 8C10.5 4.5 6.5 4.5 7 7c.3 1.3 3 1 5 1 2 0 4.7.3 5-1 .5-2.5-3.5-2.5-5 1"/>',
 weather:'<path d="M7 19h10a4 4 0 0 0 .6-8 5.5 5.5 0 0 0-10.4 1.6A3.2 3.2 0 0 0 7 19z"/><path d="M5 3.5v1.6M1.8 7.6h1.6M2.6 4.6l1.1 1.1"/>',
 moon:'<path d="M20 14.6A8.2 8.2 0 0 1 9.4 4a8.2 8.2 0 1 0 10.6 10.6z"/>',
 text:'<path d="M2.5 19 7.5 5.5 12.5 19M4.4 14h6.2M14.5 19l3-8 3 8M15.6 16.2h3.8"/>',
 list:'<path d="M9.5 6.5h11M9.5 12h11M9.5 17.5h11M3.5 6.5l1.3 1.3L7.3 5.3M3.5 12l1.3 1.3L7.3 10.8M3.5 17.5l1.3 1.3 2.5-2.5"/>',
 gear:'<circle cx="12" cy="12" r="3.2"/><path d="M12 2.8l1.7 2.2 2.7-.7.5 2.8 2.4 1.5-1.2 2.5 1.2 2.5-2.4 1.5-.5 2.8-2.7-.7L12 21.2l-1.7-2.2-2.7.7-.5-2.8-2.4-1.5L5.9 12 4.7 9.5l2.4-1.5.5-2.8 2.7.7z"/>',
 help:'<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.6 2.3c-.7.4-1.2 1-1.2 1.8v.6M12 17.3v.1"/>'};
function iconEl(name,cls){const w=el("span",cls||"ic");w.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]||ICONS.help}</svg>`;return w}
const tile=t=>{let h=0;for(const ch of t||"")h=(h*31+ch.charCodeAt(0))%360;return`linear-gradient(135deg,hsl(${h} 34% 22%),hsl(${(h+50)%360} 40% 11%))`};
function hints(box,pairs){box.textContent="";const k=el("div","kbd");for(const[a,b]of pairs){k.append(el("b",0,a),el("span",0,b))}box.append(k)}

/* ---- playback ---- */
function osd(keep){const c=chans[ci];if(!c)return;const wx=c.kind==="weather"&&!vod;if(!slot&&!vod&&!wx)return;const s=vod||slot;
 $("#osd").classList.toggle("vod",!!vod);$("#o-num").textContent=vod?"VOD":c.number;
 $("#o-title").textContent=wx?"Local weather":label(s);
 $("#o-sub").textContent=wx?c.name+", live forecast and alerts":vod?(vod.startOver?"Start over":"On demand")+([vod.franchise,vod.year].filter(Boolean).length?", "+[vod.franchise,vod.year].filter(Boolean).join(", "):""):`${c.name}${s.block?" · "+s.block:""}, ${T(s.start)} to ${T(s.end)}, ${mins(s.end-nowS())} min left`;
 osdHints(wx?"":vod?"":nextSlot?(nextSlot.card?`Next at ${T(nextSlot.end)}: ${nextSlot.next_title}`:`Next at ${T(nextSlot.start)}: ${label(nextSlot)}`):"",
  wx?[]:vod?[["← →","skip 10 s / 30 s"],["0-9","jump"],["Space","pause"],["C","subtitles"],...(vod.series?[["J","intro ends here"],["E","credits start here"]]:[]),["Esc","back to TV"]]:slot?[["R","start over"],["C","subtitles"],["H","home menu"],["S","sleep timer"],["F3","rename"]]:[]);
 $("#o-clock").textContent=T(nowS())+(sleepLeft()?"   ·   Sleep in "+sleepLeft():"");show("#osd",true);clearTimeout(osdT);if(!(vod&&(v.paused||keep)))osdT=setTimeout(()=>show("#osd",false),5e3);bar()}
function osdHints(text,pairs){const nx=$("#o-next");nx.textContent="";if(text)nx.append(el("span",0,text));
 if(pairs.length){const k=el("span","kbd");for(const[a,b]of pairs)k.append(el("b",0,a),el("span",0,b));nx.append(k)}}
function bar(){const s=vod||slot;$("#o-barwrap").style.visibility=s?"visible":"hidden";$("#o-cur").textContent=$("#o-dur").textContent="";if(!s)return;
 const dur=vod?(v.duration||s.runtime_s):(s.end-s.start),pos=vod?v.currentTime:(nowS()-s.start),f=Math.min(1,Math.max(0,pos/dur));
 $("#o-bar").style.width=f*100+"%";$("#o-knob").style.left=f*100+"%";$("#o-cur").textContent=vod?hms(pos):T(s.start);$("#o-dur").textContent=vod?hms(dur):T(s.end)}
/* on-demand seeking: keys, and click/drag on the bar */
function seekTo(t){if(!vod||!isFinite(v.duration))return;v.currentTime=Math.max(0,Math.min(v.duration-1,t));osd(true)}
const seekBy=d=>seekTo(v.currentTime+d);
{const wb=$("#o-barwrap"),hv=$("#o-hover");let scrub=false;const frac=e=>{const r=wb.getBoundingClientRect();return Math.min(1,Math.max(0,(e.clientX-r.left)/r.width))};
 wb.addEventListener("pointerdown",e=>{if(!vod||!isFinite(v.duration))return;scrub=true;wb.setPointerCapture(e.pointerId);seekTo(frac(e)*v.duration)});
 wb.addEventListener("pointermove",e=>{if(!vod||!isFinite(v.duration))return;const f=frac(e);hv.textContent=hms(f*v.duration);hv.style.left=f*100+"%";hv.style.display="block";if(scrub)seekTo(f*v.duration)});
 wb.addEventListener("pointerup",()=>{scrub=false});wb.addEventListener("pointerleave",()=>{if(!scrub)hv.style.display="none"})}
v.addEventListener("pause",()=>{if(vod)osd(true)});v.addEventListener("play",()=>{if(vod)osd()});
function startOver(){if(!slot||vod||slot.card)return;startVod({id:slot.media_id,title:slot.title,series:slot.series,season:slot.season,episode:slot.episode,
 franchise:slot.franchise,year:slot.year,runtime_s:slot.runtime_s,position:0,completed:0,startOver:true})}
async function sync(){const a=Date.now(),j=await api("/api/now");off=j.now-(a+Date.now())/2e3;cfg=j}
async function tune(i){if(sleeping)return;if(!chans.length){msg("No channels have anything to show yet","Put videos in your media folder, or open Settings (O) and check the library.");return}const my=++seq;vod=null;const ni=(i+chans.length)%chans.length;if(started&&ni!==ci)prevCi=ci;started=true;tunedAt=nowS();ci=ni;localStorage.setItem("ch",chans[ci].id);savePrefs();msg("");paint(root,chans[ci].color);
 const wx=chans[ci].kind==="weather";show("#wx",wx);show("#upcard",false);clearTimeout(cardT);clearTimeout(cutT);document.body.classList.toggle("novideo",wx);
 if(wx){slot=nextSlot=null;v.pause();v.removeAttribute("src");v.load();loadWx();return osd()}
 let j;try{j=await api(`/api/channel/${chans[ci].id}/now`)}catch(e){return msg("Can't reach HERO TV","Make sure the HERO TV window is still open. Trying again."),setTimeout(()=>tune(ci),3e3)}
 if(my!==seq)return; /* a newer tune() superseded this one */
 slot=j.slot;nextSlot=j.next;if(!slot){v.removeAttribute("src");v.load();v.classList.remove("dim");osd();return chans[ci].id==="free"?msg("No free movies yet","Press O for Settings, then Tools > Free movies > Download."):msg("Nothing is scheduled on "+chans[ci].name,"Drag videos onto this window, or put them in this channel's folder. They appear by themselves.")}
 if(slot.card)return upCard(my);
 play(withK(`/media/${slot.media_id}`),()=>Math.min(nowS()-slot.start+(slot.seek||0),(v.duration||1e9)-.5));loadSubs(slot.media_id);osd();
 if(slot.cut)cutT=setTimeout(()=>{if(my===seq&&!vod)tune(ci)},Math.max(0,(slot.end-nowS())*1e3)+80)}   /* a break (or a time slot) starts before the video ends */
/* the channel logo in the corner: always, now and then (when a show starts, after changing channel, and briefly
   every five minutes), or off - Settings > Appearance */
let tunedAt=0;
function updateBug(){const b=$("#bug"),c=chans[ci],m=theme.logo||"sometimes";
 const live=c&&slot&&!vod&&!slot.card&&c.kind!=="weather"&&layer===""&&!sleeping;
 const t=nowS(),on=live&&m!=="off"&&(m==="always"||t-tunedAt<12||(slot&&t-slot.start<15&&t-slot.start>=0)||t%300<10);
 if(on&&c){$("#bug-n").textContent=c.number;$("#bug-t").textContent=c.name;paint(b,c.color)}b.classList.toggle("on",!!on)}
setInterval(updateBug,1000);
/* "Up next" card: fills the minute or two before a show that starts at a clean time (no video) */
let cardT=0,cutT=0;
function upCard(my){const c=chans[ci],box=$("#upcard");v.pause();v.removeAttribute("src");v.load();clearSub();document.body.classList.add("novideo");
 box.textContent="";const img=el("img");img.alt="";img.src=withK(`/thumb/${slot.media_id}`);img.onerror=()=>img.remove();
 const t=el("div","uc-t");t.append(el("small",0,"UP NEXT ON "+c.name.toUpperCase()),el("h2",0,slot.next_title||""),el("div","uc-at",`at ${T(slot.end)}`));
 if(slot.plot)t.append(el("p",0,slot.plot));const left=el("div","uc-left");t.append(left);box.append(img,t);show("#upcard",true);
 const tick=()=>{if(my!==seq||!slot||!slot.card)return;const s=Math.max(0,slot.end-nowS());left.textContent=`Starts in ${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,"0")}`;
  if(s<=0)return tune(ci);cardT=setTimeout(tick,1e3)};tick();osd()}
/* ---- comfort: even volume, night mode, screensaver, TV edge margin, look (Settings > Appearance) ---- */
let actx=null,gainN=null,compN=null,gainFor="";
function comfortOf(){return theme.comfort||{level:true,night:{active:false},screensaver:true,safe_margin:0,theme:"classic"}}
function audioChain(){if(gainN)return true;try{if(!actx)actx=new (window.AudioContext||window.webkitAudioContext)()}catch(e){return false}
 if(actx.state!=="running"){actx.resume().catch(()=>{});return false}   /* never route the sound through a stopped player */
 try{const src=actx.createMediaElementSource(v);gainN=actx.createGain();compN=actx.createDynamicsCompressor();src.connect(gainN);gainN.connect(compN);compN.connect(actx.destination);nightSound();return true}catch(e){return false}}
function nightSound(){if(!compN)return;const on=comfortOf().night.active;   /* at night loud bangs are evened out too */
 compN.threshold.value=on?-30:0;compN.ratio.value=on?4:1;compN.knee.value=on?12:0;compN.attack.value=.01;compN.release.value=.3}
async function evenVolume(url){const m=/\/media\/(\d+)/.exec(url||"");if(!m)return;const id=m[1];gainFor=id;
 if(!comfortOf().level){if(gainN)gainN.gain.value=1;return}
 let g=0;try{const j=await api("/api/gain/"+id);if(gainFor!==id)return;g=j.gain_db||0}catch(e){return}
 if(!audioChain()&&!(g<0))return;                          /* turning down also works without the sound chain */
 if(gainN){gainN.gain.setTargetAtTime(Math.pow(10,g/20),actx.currentTime,.4);v.volume=Math.min(1,v.volume||1)}
 else v.volume=Math.max(.05,Math.min(1,Math.pow(10,g/20)))}
function applyComfort(){const c=comfortOf();document.body.classList.toggle("night",!!c.night.active);document.body.dataset.theme=c.theme||"classic";
 document.documentElement.style.setProperty("--safe",(c.safe_margin||0)+"");document.body.classList.toggle("safe",(c.safe_margin||0)>0);nightSound()}
setInterval(()=>{loadTheme()},300000);                         /* night mode starts and ends by itself */
/* screensaver: when on-demand video is paused, or a menu is left open, for a few minutes (live TV never) */
let lastInput=Date.now(),saverT=0,saverPics=[];
for(const ev of["keydown","mousemove","mousedown","touchstart","wheel"])addEventListener(ev,e=>{lastInput=Date.now();if($("#saver").classList.contains("on")){show("#saver",false);clearInterval(saverT);if(ev==="keydown"){e.preventDefault();e.stopImmediatePropagation()}}},true);
async function saverOn(){const box=$("#saver");if(box.classList.contains("on"))return;
 if(!saverPics.length){try{const j=await api("/api/library?limit=80");saverPics=(j.items||[]).map(x=>x.id)}catch(e){}}
 if(!saverPics.length)return;box.textContent="";const clock=el("div","sv-clock");box.append(clock);show("#saver",true);
 const next=()=>{const id=saverPics[Math.floor(Math.random()*saverPics.length)],img=el("img");img.alt="";img.src=withK(`/thumb/${id}`);
  img.style.setProperty("--x",(Math.random()*6-3)+"%");img.style.setProperty("--y",(Math.random()*6-3)+"%");img.onload=()=>{img.classList.add("in");
  const old=[...box.querySelectorAll("img")].slice(0,-1);setTimeout(()=>old.forEach(o=>o.remove()),2500)};box.insertBefore(img,clock);clock.textContent=T(nowS())};
 next();clearInterval(saverT);saverT=setInterval(next,9000)}
setInterval(()=>{if(!comfortOf().screensaver||sleeping)return;const idle=(Date.now()-lastInput)/1e3;
 const paused=vod&&v.paused&&idle>=180,menu=layer!==""&&layer!=="rename"&&idle>=300,blank=!vod&&!slot&&chans.length&&chans[ci]&&chans[ci].kind!=="weather"&&idle>=300;
 if(paused||menu||blank)saverOn()},5000);
/* subtitles: files next to the video, or text subtitles inside it (C cycles off / each track) */
let subs=[],subI=-1,subPref="",subMid=0,subPics=0;
function clearSub(){for(const t of v.querySelectorAll("track"))t.remove();subI=-1}
async function loadSubs(id){subMid=id;subs=[];subPics=0;clearSub();
 try{const j=await api("/api/subs/"+id);if(subMid!==id)return;subs=j.tracks||[];subPics=j.picture_only||0}catch(e){return}
 if(subPref){const i=subPref==="*"?(subs.length?0:-1):subs.findIndex(t=>t.language===subPref);if(i>=0)setSub(i,true)}}
function setSub(i,quiet){clearSub();subI=i;
 if(i>=0){const t=subs[i],tr=document.createElement("track");tr.kind="subtitles";tr.label=t.label;tr.src=withK(`/sub/${subMid}/${t.key}.vtt`);tr.default=true;v.append(tr);tr.track.mode="showing"}
 if(!quiet)toast(i>=0?"Subtitles: "+subs[i].label:"Subtitles off")}
function cycleSub(){
 if(!subs.length)return toast(subPics?"This video's subtitles are pictures (Blu-ray style) that a browser cannot show. Use a .srt file instead.":"No subtitles for this video. Put a .srt file next to it with the same name.");
 const n=subI+1>=subs.length?-1:subI+1;setSub(n);subPref=n>=0?(subs[n].language||"*"):"";post("/api/prefs",{subs:subPref})}
function play(url,startFn){clearSub();v.classList.add("dim");v.src=url;evenVolume(url);v.onloadedmetadata=()=>{v.currentTime=Math.max(0,startFn());v.play().catch(e=>{if(e&&e.name==="NotAllowedError")show("#tapgo",true)})};v.onplaying=()=>v.classList.remove("dim")}
async function startVod(it){vod=it;slot=null;closeAll();show("#wx",false);show("#upcard",false);clearTimeout(cardT);document.body.classList.remove("novideo");layer="";msg("");const p=it.completed?0:it.position;
 it.skip=null;if(it.series){try{it.skip=await api("/api/skip?series="+encodeURIComponent(it.series)+"&media_id="+it.id)}catch(e){}if(vod!==it)return}
 play(withK(`/media/${it.id}`),()=>{const d=v.duration||0;if(p>10&&p<d-10)return p;
  const sk=it.skip;if(sk&&sk.intro>0&&sk.intro<d*.5){toast("Skipped the intro. Press ← to go back.");return sk.intro}return 0});loadSubs(it.id);osd()}
v.addEventListener("ended",()=>{if(vod){post("/api/progress",{media_id:vod.id,position:0,completed:true});if(sleepAfter)return goToSleep();if(vod.series)return nextEpisode(vod);return tune(ci)}
 setTimeout(()=>tune(ci),Math.max(0,(slot?slot.end-nowS():0)*1e3)+80)});
v.addEventListener("error",async()=>{const id=vod?vod.id:slot&&slot.media_id;if(!id)return;
 if(REMOTE)return msg("This video can't play on this device yet","Usually a .mkv file. On the PC: Settings > Tools > Make iPhone-friendly copies. Change channel to keep watching.");
 errs=errs.filter(t=>Date.now()-t<3e4);errs.push(Date.now());
 await post("/api/report-error",{media_id:id,reason:v.error&&v.error.message});
 if(errs.length>=5){msg("Playback keeps failing","This video may be in a format the TV cannot play. Settings > Tools > Videos that are skipped can fix it. Trying again in 10 seconds.");errs=[];return setTimeout(()=>tune(ci),1e4)}
 setTimeout(()=>tune(ci),1500)});
setInterval(()=>{ // 1 Hz: sleep timer, slot rollover, drift correction, stall watchdog, progress
 sleepCheck();if(sleeping)return;
 if(vod&&vod.skip&&vod.skip.outro>0&&!vod.credDone&&v.duration&&v.currentTime>30&&v.duration-v.currentTime<=vod.skip.outro){vod.credDone=true;toast("Skipped the credits");v.dispatchEvent(new Event("ended"))}
 /* found by HERO TV itself (when you have not set the show's points with J / E): this episode's own intro and credits */
 const fd=vod&&vod.skip&&vod.skip.found;
 if(fd&&!(vod.skip.intro>0)&&fd.intro_end>0&&!vod.introDone&&v.currentTime>=fd.intro_start-.3&&v.currentTime<fd.intro_end-2){vod.introDone=true;toast("Skipped the intro. Press ← to go back.");v.currentTime=fd.intro_end}
 if(fd&&!(vod.skip.outro>0)&&fd.credits>0&&!vod.credDone&&v.currentTime>=fd.credits&&v.duration&&v.duration-v.currentTime>5){vod.credDone=true;toast("Skipped the credits");v.dispatchEvent(new Event("ended"))}
 upNext();
 if(slot&&!vod&&nowS()>=slot.end)tune(ci);
 if(slot&&!vod&&!v.paused&&v.readyState>2){const e=nowS()-slot.start;if(Math.abs(v.currentTime-e)>4&&e<v.duration-1)v.currentTime=e}
 if(v.src&&!v.paused&&v.currentTime===lastPos){if(++stall>20){stall=0;tune(ci)}}else stall=0;lastPos=v.currentTime;
 /* sound but no picture = a video format this browser cannot show: report it, say so, move on */
 if(v.src&&!v.paused&&v.readyState>=2&&v.currentTime>3&&v.videoWidth===0){if(++nopic>=3){nopic=0;const id=vod?vod.id:slot&&slot.media_id;
   if(id){post("/api/report-error",{media_id:id,reason:"no-picture"});msg("This video has sound but no picture","Its video format cannot be shown here, so it is skipped. Settings > Tools > Videos that are skipped can fix it.");setTimeout(()=>{msg("");tune(ci)},5e3)}}}else nopic=0;
 if(layer===""&&$("#osd").classList.contains("on"))bar()},1e3);
setInterval(()=>{const id=vod?vod.id:slot&&slot.media_id;if(id&&v.currentTime>5)post("/api/progress",{media_id:id,position:v.currentTime,completed:v.duration&&v.currentTime>v.duration*.95})},1e4);
setInterval(()=>sync().catch(()=>{}),3e5);
const NEED_API=19;   /* must match API_LEVEL in herotv/config.py */
let libV=null,toastT;
function toast(t){const e=$("#toast");e.textContent=t;e.classList.add("on");clearTimeout(toastT);toastT=setTimeout(()=>e.classList.remove("on"),5000)}
async function libChanged(note){try{const cur=chans[ci]&&chans[ci].id;setChans((await api("/api/channels")).channels);const i=chans.findIndex(c=>c.id===cur);if(i>=0)ci=i;
  if(layer==="guide"){await loadGuide();drawGuide()}else if(layer==="lib"){const keep=li;await search();li=Math.min(keep,items.length-1);drawList()}
  toast("Library updated"+(note&&note!=="updated"?": "+note:""))}catch(e){}}
let errSent=0;function sendErr(msg,where){if(REMOTE||Date.now()-errSent<2000)return;errSent=Date.now();try{fetch("/api/client-error",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({msg:String(msg).slice(0,400),where:String(where||"").slice(0,80)})}).catch(()=>{})}catch(e){}}
addEventListener("error",e=>sendErr(e.message,(e.filename||"").split("/").pop()+":"+e.lineno));
addEventListener("unhandledrejection",e=>sendErr("promise: "+((e.reason&&(e.reason.message||e.reason))||""),"async"));
let bootV=null;const beat=()=>fetch("/api/hb").then(r=>r.json()).then(j=>{if(j.v){if(bootV===null)bootV=j.v;else if(j.v!==bootV){bootV=j.v;return location.reload()}}
 if(libV===null)libV=j.lib;else if(j.lib!==libV){libV=j.lib;libChanged(j.note)}}).catch(()=>{});beat();setInterval(beat,1e4);
/* what you actually watch live is remembered (30 s at a time): channels then pass over finished shows, and pick up where you left off */
setInterval(()=>{if(slot&&!vod&&!v.paused&&v.readyState>=3&&document.visibilityState==="visible")post("/api/seen",{media_id:slot.media_id,secs:30})},3e4);
let prT;const savePrefs=()=>{if(!chans[ci])return;clearTimeout(prT);prT=setTimeout(()=>post("/api/prefs",{channel:chans[ci].number,volume:v.volume,muted:v.muted}),1500)};
v.addEventListener("volumechange",savePrefs);   /* lets a windowless (quiet) start shut down when this window closes */

/* ---- sleep timer, up-next card, bigger text ---- */
const SLEEP_STEPS=[0,30,60,90,120,"end"];let sleepI=0,sleepMs=0,sleepAfter=false,sleeping=false,sleepWarned=false;
function sleepLeft(){const s=SLEEP_STEPS[sleepI];return s==="end"?"end of show":sleepMs?Math.max(1,Math.ceil((sleepMs-Date.now())/6e4))+" min":""}
function cycleSleep(){sleepI=(sleepI+1)%SLEEP_STEPS.length;const s=SLEEP_STEPS[sleepI];sleepMs=typeof s==="number"&&s?Date.now()+s*6e4:0;sleepAfter=s==="end";sleepWarned=false;
 toast(s===0?"Sleep timer off":s==="end"?"Sleep timer: TV will pause when this show ends":`Sleep timer: TV will pause in ${s} minutes`);if(layer==="home")drawHome();else if(layer==="")osd(true)}
function sleepCheck(){if(sleeping)return;
 if(sleepMs){const left=sleepMs-Date.now();if(left<=0)return goToSleep();if(left<=6e4&&!sleepWarned){sleepWarned=true;toast("Sleep timer: pausing in 1 minute. Press S to change it.")}}
 if(sleepAfter&&!vod&&slot&&nowS()>=slot.end-1)goToSleep()}
function goToSleep(){sleeping=true;sleepMs=0;sleepAfter=false;sleepI=0;v.pause();msg("Sleep timer finished","Press any key to keep watching.")}
function wake(){sleeping=false;msg("");if(vod&&!v.ended)v.play().catch(()=>{});else tune(ci)}
function upNext(){const u=$("#upnext"),left=slot?slot.end-nowS():0;
 if(vod||!slot||!nextSlot||slot.card||nextSlot.card||left<=0||left>75||layer!==""||sleeping){u.classList.remove("on");u.dataset.k="";return}
 const k=nextSlot.media_id+":"+nextSlot.start;
 if(u.dataset.k!==k){u.dataset.k=k;const pic=$("#un-pic");pic.textContent="";pic.append(thumb(nextSlot.media_id));$("#un-t").textContent=label(nextSlot);$("#un-s").textContent=`${chans[ci].number} ${chans[ci].name}, ${T(nextSlot.start)}${nextSlot.block?" · "+nextSlot.block:""}`}
 $("#un-h").textContent="UP NEXT IN "+hms(left);u.classList.add("on")}
function setBig(on,save){document.body.classList.toggle("big",!!on);if(save){post("/api/prefs",{bigtext:!!on});toast(on?"Bigger text on":"Bigger text off")}if(layer==="guide")drawGuide();else if(layer==="lib")drawList();else if(layer==="home")drawHome()}

/* ---- skip intro / skip credits (on-demand playback; live TV keeps its schedule) ---- */
function markSkip(kind,clear){if(!vod||!vod.series||!isFinite(v.duration))return;const sk=vod.skip||(vod.skip={intro:0,outro:0});
 const val=clear?0:kind==="intro"?v.currentTime:Math.max(0,v.duration-v.currentTime);
 if(kind==="outro")vod.credDone=true;sk[kind]=val;post("/api/skip",{series:vod.series,[kind]:val});
 toast(clear?`${kind==="intro"?"Intro":"Credits"} skipping turned off for ${vod.series}`:kind==="intro"?`Saved. Every ${vod.series} episode will skip ahead to here.`:`Saved. ${vod.series} will skip its credits from here.`)}

/* ---- home menu and help ---- */
let hi=0,homeData={};
async function openHome(){layer="home";hi=0;show("#settings",false);show("#info",false);sDirty=false;show("#check",false);show("#guide",false);show("#lib",false);show("#help",false);show("#osd",false);show("#home",true);drawHome();await loadHome();if(layer==="home")drawHome()}
async function loadHome(){const d={};
 try{const j=await api("/api/library?view=continue&limit=1");d.cont=j.items[0]||null;d.counts=j.counts||{}}catch(e){}
 try{const n=Math.floor(nowS()),j=await api(`/api/guide?from=${n}&hours=24`);let best=null;
  for(const c of j.channels)for(const s of c.slots)if(s.block&&s.block!=="Filler"&&s.end>n&&(!best||s.start<best.s.start))best={c,s};d.special=best}catch(e){}
 try{const j=await api("/api/library?view=recent&limit=1");d.recent=j.items[0]||null;d.recentN=j.counts&&j.counts.recent||0}catch(e){}
 try{d.help=await api("/api/help")}catch(e){}
 try{d.check=(await api("/api/checklist")).lists}catch(e){}
 if(!REMOTE)try{d.setup=await api("/api/setup")}catch(e){}
 homeData=d}
const dayWord=t=>(new Date(t*1e3).toDateString()===new Date(nowS()*1e3).toDateString()?"today ":"tomorrow ")+T(t);
function homeTiles(){const d=homeData,c=chans[ci],free=allChans.find(x=>x.id==="free"),wxc=chans.find(x=>x.kind==="weather"),list=[];
 const tuneTo=i=>{closeAll();tune(i)};
 const sp=d.setup;
 list.push({ic:"live",wide:1,t:"Live TV",s:c?`${c.number} ${c.name}${slot?": "+label(slot):""}`:"",img:slot&&slot.media_id,go:()=>closeAll()});
 if(sp&&!sp.done&&!REMOTE){const nx=sp.steps.find(x=>!x.done),n=sp.steps.filter(x=>x.done).length;
  list.push({ic:"gear",t:"Finish setting up",s:`${n} of ${sp.steps.length} done. Next: ${nx.text}`,go:()=>{closeAll();openSettings("tools").then(()=>sJump(nx.cat,nx.card))}})}
 list.push(d.cont?{ic:"resume",t:"Continue watching",s:`${label(d.cont)}, ${hms(d.cont.position)} in`,img:d.cont.id,go:()=>startVod(d.cont)}
  :{ic:"resume",t:"Continue watching",s:"Nothing started yet. Pick something from the library.",dim:1,go:()=>{closeAll();openLib()}});
 if(d.recent)list.push({ic:"new",t:"New in your library",s:`${d.recentN} new: ${label(d.recent)}${d.recentN>1?" and more":""}`,img:d.recent.id,go:()=>{closeAll();openLib("recent")}});
 if(d.special){const x=d.special,on=x.s.start<=nowS();list.push({ic:"ticket",t:x.s.block,s:`${on?"On now":"Starts "+dayWord(x.s.start)}, channel ${x.c.number}`,img:x.s.media_id,go:()=>tuneTo(chans.findIndex(k=>k.id===x.c.id))})}
 list.push({ic:"guide",t:"TV guide",s:"See what is on every channel",go:()=>{closeAll();openGuide()}});
 list.push({ic:"search",t:"Library and search",s:"Find any movie or show",go:()=>{closeAll();openLib()}});
 const fv=d.counts&&d.counts.favorites||0;list.push({ic:"star",t:"Favorites",s:fv?`${fv} saved`:"Press F2 on any video to save it here",dim:!fv,go:()=>{closeAll();openLib("favorites")}});
 if(free){const n=d.help?d.help.free:null;list.push({ic:"gift",t:"Free movies",s:n===0?"None yet: Settings > Tools":n?`${n} free ${n===1?"title":"titles"} to watch`:"Free public-domain movies",go:()=>{const i=chans.indexOf(free);if(i<0){toast("No free movies yet. Settings > Tools > Free movies.");return}tuneTo(i)}})}
 if(wxc)list.push({ic:"weather",t:"Weather",s:"Forecast and alerts",go:()=>tuneTo(chans.indexOf(wxc))});
 list.push({ic:"moon",t:"Sleep timer",s:sleepLeft()?"Pauses in "+sleepLeft()+". Select to change":"Off. Pick 30 to 120 minutes",stay:1,go:cycleSleep});
 const big=document.body.classList.contains("big");list.push({ic:"text",t:"Bigger text",s:big?"On. Select to turn off":"Off. Select to make text bigger",stay:1,go:()=>setBig(!big,true)});
 if(d.check){const miss=d.check.filter(l=>!l.ideas).reduce((a,l)=>a+l.missing,0);list.push({ic:"list",t:"Checklist",s:miss?`${miss} titles still to find`:"Everything on your lists is here",go:()=>openCheck()})}
 if(!REMOTE)list.push({ic:"gear",t:"Settings",s:"Look, channels, phone, backup",go:()=>openSettings()});
 list.push({ic:"help",t:"Help",s:d.help&&d.help.problem_count?`${d.help.problem_count} video(s) need attention`:"Keys, and fixes for common problems",go:()=>openHelp("home")});
 return list}
function drawHome(){const box=$("#tiles"),L=homeTiles();box.textContent="";paint($("#home"),theme.color);hi=Math.max(0,Math.min(hi,L.length-1));
 $("#h-clock").textContent=dayStr();$("#h-hello").textContent=theme.tagline;$("#home h2").textContent=theme.name;
 hints($("#h-hints"),[["← → ↑ ↓","choose"],["Enter","open"],["Esc","back to TV"],["?","help"]]);
 L.forEach((t,i)=>{const n=el("div","tl"+(i===hi?" sel":"")+(t.dim?" dim":"")+(t.wide?" wide":"")+(t.img?" has-img":""));if(t.img)n.append(thumb(t.img));
  n.append(iconEl(t.ic));if(t.wide&&slot&&!wxOn())n.append(el("i","onnow","On now"));n.append(el("b",0,t.t),el("small",0,t.s));
  n.onclick=()=>{hi=i;t.go();if(t.stay)drawHome()};box.append(n)});
 homeList=L}
let homeList=[];
function homeKey(e){const k=e.key,cols=getComputedStyle($("#tiles")).gridTemplateColumns.split(" ").length||4;
 if(k==="Escape"||k==="Backspace"||k==="h"||k==="H"||k==="Home"){e.preventDefault();return closeAll()}
 if(k==="?"||k==="F1"){e.preventDefault();return openHelp("home")}
 if(k==="s"||k==="S"){return cycleSleep()}
 if(k==="t"||k==="T"){return setBig(!document.body.classList.contains("big"),true)}
 const mv=d=>{e.preventDefault();hi=Math.max(0,Math.min(homeList.length-1,hi+d));drawHome()};
 if(k==="ArrowRight")mv(1);else if(k==="ArrowLeft")mv(-1);
 else if(k==="ArrowDown"||k==="ArrowUp"){e.preventDefault();const ts=[...$("#tiles").children],r0=ts[hi]&&ts[hi].getBoundingClientRect();if(!r0)return;
  const cx=r0.left+r0.width/2;let best=-1,bd=1e9;
  ts.forEach((n,i)=>{if(i===hi)return;const r=n.getBoundingClientRect();if(!inDir(r0,r,k))return;     /* the nearest tile in the row above/below */
   const dy=Math.abs(r.top+r.height/2-r0.top-r0.height/2),dx=overlapX(r0,r)?Math.abs(r.left+r.width/2-cx)*.1:Math.abs(r.left+r.width/2-cx),d=dy*4+dx;if(d<bd){bd=d;best=i}});
  if(best>=0){hi=best;drawHome()}}
 else if(k==="Enter"){e.preventDefault();const t=homeList[hi];if(t){t.go();if(t.stay)drawHome()}}}
let ck={data:null,i:0};
async function openCheck(){layer="check";show("#settings",false);show("#home",false);show("#help",false);show("#check",true);paint($("#check"),theme.color);
 hints($("#ck-hints"),[["← →","change list"],["↑ ↓","scroll"],["Esc","back"]]);ck.i=0;ck.data=null;drawCheck();
 try{const j=await api("/api/checklist");ck.data=j.lists;ck.err=j.error||""}catch(e){}drawCheck()}
function drawCheck(){const tabs=$("#ck-tabs"),body=$("#ck-body"),sum=$("#ck-sum");tabs.textContent=body.textContent=sum.textContent="";
 if(!ck.data){body.append(el("div","empty","Loading your lists..."));return}
 if(!ck.data.length){body.append(el("div","empty",ck.err||"There are no lists to show."));return}
 ck.data.forEach((l,i)=>tabs.append(el("span",i===ck.i?"on":"",l.name)));
 const l=ck.data[ck.i];if(!l)return;$("#ck-sub").textContent=l.channel?"on channel "+l.channel:"";
 const total=l.have+l.missing,f=total?l.have/total:0;
 sum.append(el("span",0,l.kind==="series"?`${l.have} episodes in your library`:`You have ${l.have} of ${total}${l.ideas?" (ideas, not a full set)":""}`));
 if(l.kind!=="series"){const bar=el("i"),fill=el("b");fill.style.width=f*100+"%";bar.append(fill);sum.append(bar)}
 for(const it of l.items){const r=el("div","ck "+(l.kind==="series"?(it.done||!it.total?"have":"miss"):it.soon?"soon":it.have?"have":"miss"));
  const d=el("div");
  if(l.kind==="series"){r.append(el("i",0,it.done||!it.total?"✓":"○"));d.append(el("span",0,it.total?`${it.label}: ${it.have} of ${it.total}`:`${it.label}: ${it.have} episode${it.have===1?"":"s"}`));
   if(it.missing_eps&&it.missing_eps.length)d.append(el("small",0,"Missing episode "+it.missing_eps.join(", ")))}
  else{r.append(el("i",0,it.soon?"⏳":it.have?"✓":"○"));d.append(el("span",0,it.label));if(it.soon)d.append(el("small",0,"Not out yet, "+it.date));else if(it.have&&!it.playable)d.append(el("small",0,"Have it, but it is being skipped (see Help)"))}
  r.append(d);body.append(r)}
 if(l.kind==="series"&&!l.items.length)body.append(el("div","empty","Nothing yet. Put episodes named like  Show S01E01.mkv  in its folder."))}
function checkKey(e){const k=e.key;
 if(k==="Escape"||k==="Backspace"){e.preventDefault();return openHome()}
 if(!ck.data)return;
 if(k==="ArrowRight"){e.preventDefault();ck.i=(ck.i+1)%ck.data.length;$("#ck-body").scrollTop=0;drawCheck()}
 else if(k==="ArrowLeft"){e.preventDefault();ck.i=(ck.i-1+ck.data.length)%ck.data.length;$("#ck-body").scrollTop=0;drawCheck()}
 else if(k==="ArrowDown"){e.preventDefault();$("#ck-body").scrollBy(0,innerHeight*.25)}
 else if(k==="ArrowUp"){e.preventDefault();$("#ck-body").scrollBy(0,-innerHeight*.25)}}
let helpBack="";
async function openHelp(back){helpBack=back||"";layer="help";show("#settings",false);show("#home",false);show("#guide",false);show("#lib",false);show("#osd",false);show("#help",true);hints($("#hp-hints"),[["Esc","back"]]);paint($("#help"),theme.color);
 let h=null;try{h=await api("/api/help")}catch(e){}drawHelp(h)}
function drawHelp(h){const L=$("#hp-l"),R=$("#hp-r");L.textContent=R.textContent="";
 const row=(good,text,sub)=>{const r=el("div","st "+(good?"good":"bad"));r.append(el("i",0,good?"✓":"!"));const d=el("div");d.append(el("span",0,text));if(sub)d.append(el("small",0,sub));r.append(d);L.append(r)};
 L.append(el("h3",0,"Is anything wrong?"));
 if(!h)row(false,"HERO TV is not running on this PC right now.","Click the HERO TV icon to start it again, then press F5 here.");
 else{row(h.playable>0,h.playable?`${h.playable} videos are ready to play.`:"No videos are ready to play yet.",h.playable?"":"Drag videos onto this window, or get free ones in Settings > Tools.");
  row(h.ffmpeg,h.ffmpeg?"Video tools (ffmpeg) are installed.":"Video tools (ffmpeg) were not found.",h.ffmpeg?"":"Settings > Tools > Install video tools.");
  if(h.problem_count){row(false,`${h.problem_count} video(s) are being skipped:`,"");for(const p of h.problems)row(false,p.title,p.why+" "+p.fix);if(h.problem_count>h.problems.length)row(false,"...and more.","Settings > Tools lists them all, with a Fix button.")}
  else row(true,"Every video in your library can play.","");
  if(h.hidden_channels&&h.hidden_channels.length)row(true,`${h.hidden_channels.length} channel(s) are hidden until they have something to show: ${h.hidden_channels.join(", ")}`,"Put a video in that channel's folder, or drop it in the Inbox, and the channel appears by itself.");
  if(h.inbox_waiting)row(false,`${h.inbox_waiting} video(s) are waiting in the Inbox folder.`,"HERO TV files them by itself once they have finished copying. Ones it cannot place wait for you in Settings > Tools > Inbox - pick a channel (or make a new one) there.");
  row(true,"Your videos are in: "+h.media_dir,"Settings > Media library > Open media folder.")}
 R.append(el("h3",0,"Keys"));const t=el("table");
 for(const[a,b]of[["↑ ↓","Change channel"],["0-9","Type a channel number"],["Backspace","Previous channel"],["Esc or H","Home menu"],["G","TV guide"],["L","Library and search"],["R","Start this show over"],["F2","Add or remove favorite"],["D (F8 in Library)","Details: picture, plot, cast, rating"],["O","Settings"],["Right-click","Menu for the video under the pointer"],["F3 / F4","Rename video / show"],["C","Subtitles: off / each language"],["S","Sleep timer"],["T","Bigger text"],["← →","Volume (skip, when watching on demand)"],["M","Mute"],["F","Fullscreen"],["J / E","On demand: mark where the intro ends / credits start"],["R (in the guide)","Remind me when that show starts"],["M (in Details)","Move a video to another channel"],["? or F1","This help"]]){const r=el("tr");const k=el("td"),b1=el("b",0,a);k.append(b1);r.append(k,el("td",0,b));t.append(r)}
 R.append(t);
 L.append(el("h3",0,"Where to find things"));const w=el("table");w.className="where";
 for(const[a,b]of[["Settings > Channels > a channel","Play order, start times (with shorts and Up next), breaks inside shows, time slots"],
   ["Settings > Appearance","Look, channel logo, subtitles, even volume, night mode, screensaver, TV edge margin"],
   ["Settings > Tools","Skip intros and credits, Inbox, free movies and cartoons, fixing videos that are skipped"],
   ["Settings > Other devices","Phones, Roku TVs, always on, live TV in other apps (Plex, Jellyfin, IPTV)"],
   ["Settings > Backup and about","Updates, backup, problem report, quit HERO TV"]]){const r=el("tr");r.append(el("td",0,a),el("td",0,b));w.append(r)}
 L.append(w)}

/* ---- guide ---- */
let g={t0:0,t:0,row:0,data:[]};const WIN=3*3600;
let remSet=new Set();
async function loadGuide(){const j=await api(`/api/guide?from=${g.t0}&hours=3`);g.data=j.channels.filter(c=>chans.some(x=>x.id===c.id));
 try{const r=await api("/api/reminders");remSet=new Set(r.reminders.map(x=>x.channel+":"+x.start))}catch(e){}}
const inSlot=(c,t)=>c.slots.find(s=>s.start<=t&&t<s.end);
const dayStr=()=>new Intl.DateTimeFormat([],{weekday:"short",month:"short",day:"numeric",timeZone:cfg.tz||undefined}).format(nowS()*1e3)+"   "+T(nowS());
function placePreview(on){if(!on){v.style.cssText="";document.body.classList.remove("gopen");return}
 const c=chans[ci]||{};$("#pv-l").textContent=c.kind==="weather"?`${c.number}  ${c.name}  ·  live`:`${c.number||""}  ${c.name||""}`;
 document.body.classList.add("gopen");const r=$("#pv").getBoundingClientRect();Object.assign(v.style,{left:r.left+"px",top:r.top+"px",width:r.width+"px",height:r.height+"px",right:"auto",bottom:"auto"})}
function drawGuide(){const grid=$("#grid");grid.textContent="";const left=innerWidth*(innerWidth<=1000?.22:.17),pxs=(grid.clientWidth-left)/WIN; /* channel column width matches the CSS */
 const h=el("div","hdr");h.append(el("div","ch day",dayStr()));const tr=el("div","track");for(let t=g.t0;t<g.t0+WIN;t+=1800){const k=el("div","tick",T(t));k.style.left=(t-g.t0)*pxs+"px";tr.append(k)}h.append(tr);
 const rows=el("div");rows.id="rows";grid.append(h,rows);
 g.data.forEach((c,r)=>{const row=el("div","row2"+(r===g.row?" cur":"")),ch=el("div","ch");paint(row,c.color);ch.append(el("span","plate",c.number),el("span",0,c.name));ch.style.cursor="pointer";ch.onclick=()=>{closeAll();tune(r)};const track=el("div","track");
  if(c.kind==="weather"){const b_=el("div","blk wxb");b_.style.left="0px";b_.style.width=(WIN*pxs-4)+"px";b_.append(el("b",0,"Local weather  ·  live"),el("small",0,"Current conditions, 7-day forecast and alerts"));if(r===g.row)b_.classList.add("sel");track.append(b_)}
  else for(const s of c.slots){const a=Math.max(s.start,g.t0),b=Math.min(s.end,g.t0+WIN),b_=el("div","blk");b_.style.left=(a-g.t0)*pxs+"px";b_.style.width=Math.max(2,(b-a)*pxs-4)+"px";
   const on=s.start<=nowS()&&nowS()<s.end;b_.append(thumb(s.media_id),el("b",0,label(s)),el("small",0,`${T(s.start)} to ${T(s.end)}`));
   if(remSet.has(c.id+":"+s.start)){b_.classList.add("rem");b_.append(el("span","rbadge","Reminder"))}
   if(on){const p=el("i");p.style.width=Math.min(100,(nowS()-s.start)/(s.end-s.start)*100)+"%";b_.append(p)}
   if(r===g.row&&s.start<=g.t&&g.t<s.end)b_.classList.add("sel");b_.dataset.r=r;b_.dataset.t=s.start;b_.onclick=()=>{if(COARSE&&g.row===r&&s.start<=g.t&&g.t<s.end){closeAll();return tune(r)}g.row=r;g.t=s.start;drawGuide()};b_.ondblclick=()=>{closeAll();tune(r)};track.append(b_)}
  if(!c.slots.length&&c.kind!=="weather")track.append(el("div","none","No programming"));
  row.append(ch,track);rows.append(row)});
 {const rh=rows.firstChild&&rows.firstChild.offsetHeight;if(rh){rows.style.flex="none";rows.style.height=Math.max(1,Math.floor((grid.getBoundingClientRect().bottom-rows.getBoundingClientRect().top)/rh))*rh+"px"}   /* whole rows only, never a half-cut one */
  const cur=rows.children[g.row];if(cur)cur.scrollIntoView({block:"nearest"})}
 const nl=el("div");nl.id="nowline";const x=(nowS()-g.t0)*pxs;if(x>=0&&x<=WIN*pxs){nl.style.left=left+x+"px";grid.append(nl)}
 const c=g.data[g.row]||{slots:[]},s=inSlot(c,g.t),root=$("#detail");root.textContent="";paint(root,c.color);
 const still=s&&c.kind!=="weather"&&s.media_id?withK(`/thumb/${s.media_id}`):"";
 const live=g.row===ci&&s&&s.start<=nowS()&&nowS()<s.end;      /* the live preview already shows it */
 const pic=live?"":still;root.classList.toggle("withpic",!!pic);
 $("#guide").style.setProperty("--bd",still?`url("${still}")`:"none");
 if(pic){const p=el("div","pic"),im=el("img");im.alt="";im.src=pic;im.onerror=()=>{p.remove();root.classList.remove("withpic")};p.append(im);root.append(p)}
 const d=pic?el("div","txt"):root;if(pic)root.append(d);
 const chn=el("div","chn");chn.append(el("span","plate",c.number),el("span",0,c.name));d.append(chn);
 if(c.kind==="weather"){d.append(el("h3",0,"Local weather"),el("p","meta","Live, around the clock"),el("p",0,"Current conditions, the hourly and 7-day forecast, and live weather alerts. Press Enter to watch."))}
 else if(s){d.append(el("h3",0,s.card?"Up next: "+(s.next_title||""):label(s)),el("p","meta",`${T(s.start)} to ${T(s.end)}, ${mins(s.end-s.start)} min`+(s.start<=nowS()&&nowS()<s.end?", on now":"")+([s.franchise,s.year].filter(Boolean).length?"   ·   "+[s.franchise,s.year].filter(Boolean).join(", "):"")+(s.block?"   ·   "+s.block:"")));if(s.plot)d.append(el("p",0,s.plot))}
 else d.append(el("p",0,"Nothing is scheduled here."))}
async function openGuide(){show("#settings",false);show("#info",false);const n=nowS();g.t0=Math.floor(n/1800)*1800;g.t=n;g.row=ci;layer="guide";await loadGuide();hints($("#g-hints"),[["↑ ↓","channel"],["← →","time"],["Enter","watch"],["R","remind me"],["G","close"],["L","library"],["F3","rename"]]);
 const nt=el("span",0,"Showtimes are generated on this PC from your own videos. They are not real TV listings.");$("#g-hints").append(nt);nt.style.marginLeft="auto";
 show("#guide",true);show("#osd",false);drawGuide();placePreview(true)}
setInterval(()=>{if(layer==="guide"){const d=$(".hdr .day");if(d)d.textContent=dayStr()}},15e3);
async function guideKey(k){const c=g.data[g.row],s=inSlot(c,g.t);
 if((k==="r"||k==="R")&&s&&c&&c.kind!=="weather"){const key=c.id+":"+s.start,had=remSet.has(key);
  if(!had&&s.start<=nowS())return toast("That is on now - press Enter to watch it.");
  try{await pj("/api/reminders",{op:had?"remove":"add",channel:c.id,start:s.start});had?remSet.delete(key):remSet.add(key);toast(had?"Reminder removed.":`Reminder set: ${label(s)} at ${T(s.start)} on ${c.number} ${c.name}.`)}
  catch(e){toast(String(e.message||e).replace(/^Error: /,""))}return drawGuide()}
 if(k==="ArrowUp")g.row=Math.max(0,g.row-1);else if(k==="ArrowDown")g.row=Math.min(g.data.length-1,g.row+1);
 else if(k==="ArrowLeft"&&s){const nt=s.start-1;if(nt<Math.floor(nowS()/1800)*1800-3600)return;g.t=nt;if(nt<g.t0){g.t0-=3600;await loadGuide()}}
 else if(k==="ArrowRight"&&s){g.t=s.end;if(g.t>=g.t0+WIN){g.t0+=3600;await loadGuide()}}
 else if(k==="Enter"){closeAll();return tune(g.row)}
 drawGuide()}

/* ---- library: grid of screengrabs ---- */
let items=[],li=0,qT,cols=4,view="all",counts={continue:0,favorites:0,recent:0};const VIEWS=[["all","All"],["recent","New"],["continue","Continue watching"],["favorites","Favorites"]];
const colCount=()=>innerWidth>1700?6:innerWidth>1400?5:innerWidth>1150?4:innerWidth>700?3:2;
async function search(){const j=await api("/api/library?view="+view+"&q="+encodeURIComponent($("#q").value));items=j.items;counts=j.counts||counts;li=0;drawList()}
function drawList(){const L=$("#list");L.textContent="";L.style.flex="";L.style.height="";cols=colCount();L.style.setProperty("--cols",cols);paint(L.parentNode,chans[ci]&&chans[ci].color);
 const tb=$("#l-tabs");tb.textContent="";for(const[k,n]of VIEWS){const sp=el("span",k===view?"on":"",n+(k==="all"?"":" "+counts[k]));sp.onclick=()=>{view=k;saveView();search()};tb.append(sp)}
 const q=$("#q").value.trim();$("#l-count").textContent=items.length?`${items.length} ${items.length===1?"video":"videos"}`:"";
 if(!items.length){const e=el("div","empty");if(q){e.append(el("b",0,`Nothing matches "${q}".`),el("br"),document.createTextNode("Try a title, a series or a channel name."))}
  else if(view==="continue")e.append(el("b",0,"Nothing in progress."),el("br"),document.createTextNode("Videos you start from the library show up here so you can pick up where you left off."));
  else if(view==="favorites")e.append(el("b",0,"No favorites yet."),el("br"),document.createTextNode("Highlight a video and press F2 to add it."));
  else{e.append(el("b",0,"No videos yet."),el("br"),document.createTextNode("Drag movies or shows onto this window to add them."))}L.append(e);return}
 items.forEach((it,k)=>{const c=el("div","card"+(k===li?" sel":"")),pic=el("div","pic");pic.style.background=tile(it.title);pic.append(thumb(it.id,true));
  const resume=it.position>10&&!it.completed;if(resume&&it.runtime_s){const p=el("i");p.style.width=Math.min(100,it.position/it.runtime_s*100)+"%";pic.append(p)}
  pic.append(el("em",0,mins(it.runtime_s)+" min"));if(it.favorite)pic.append(el("u",0,"★"));
  const meta=[it.franchise,it.year].filter(Boolean).join(", ")+(resume?(it.franchise||it.year?", ":"")+"resume at "+mins(it.position)+" min":"");
  c.append(pic,el("b",0,label(it)),el("small",0,meta||" "));c.onclick=()=>{if(COARSE&&li===k)return startVod(it);li=k;drawList()};c.ondblclick=()=>startVod(it);L.append(c)});
 const f=L.firstElementChild;if(f&&f.classList.contains("card")){const second=L.children[cols],step=second?second.offsetTop-f.offsetTop:f.offsetHeight;
  if(step>0){L.style.flex="none";L.style.height=Math.max(1,Math.floor((L.parentNode.clientHeight-L.offsetTop-$("#l-hints").offsetHeight-16)/step))*step+"px"}}   /* whole rows only */
 const sel=L.querySelector(".card.sel");if(sel)sel.scrollIntoView({block:"nearest"})}
function saveView(){try{localStorage.setItem("herotv.libView",view)}catch(e){}}
function savedView(){try{const v=localStorage.getItem("herotv.libView");return VIEWS.some(x=>x[0]===v)?v:"all"}catch(e){return"all"}}
async function openLib(v0){layer="lib";show("#settings",false);show("#info",false);view=v0||savedView();show("#home",false);show("#help",false);hints($("#l-hints"),[["← → ↑ ↓","browse"],["Enter","play"],["Tab","switch list"],["F2","favorite"],["F8","details"],["F3 / F4","rename"],["Esc","back"]]);show("#lib",true);show("#osd",false);$("#q").value="";await search();$("#q").focus()}
function closeAll(){layer="";show("#guide",false);show("#lib",false);show("#home",false);show("#help",false);show("#check",false);show("#info",false);show("#settings",false);$("#q").blur();placePreview(false)}
$("#q").addEventListener("input",()=>{clearTimeout(qT);qT=setTimeout(search,200)});
addEventListener("resize",()=>{if(layer==="lib")drawList();if(layer==="guide"){drawGuide();placePreview(true)}});

/* ---- weather channel + live alert crawl ---- */
const WMO={0:["Clear","☀️","🌙"],1:["Mostly clear","🌤️","🌙"],2:["Partly cloudy","⛅","☁️"],3:["Cloudy","☁️"],45:["Fog","🌫️"],48:["Freezing fog","🌫️"],
 51:["Light drizzle","🌦️"],53:["Drizzle","🌦️"],55:["Heavy drizzle","🌧️"],56:["Freezing drizzle","🌧️"],57:["Freezing drizzle","🌧️"],61:["Light rain","🌦️"],63:["Rain","🌧️"],
 65:["Heavy rain","🌧️"],66:["Freezing rain","🌧️"],67:["Freezing rain","🌧️"],71:["Light snow","🌨️"],73:["Snow","🌨️"],75:["Heavy snow","❄️"],77:["Snow grains","🌨️"],
 80:["Showers","🌦️"],81:["Showers","🌧️"],82:["Heavy showers","⛈️"],85:["Snow showers","🌨️"],86:["Heavy snow showers","❄️"],95:["Thunderstorms","⛈️"],96:["Storms with hail","⛈️"],99:["Storms with hail","⛈️"]};
const wmo=(c,day=true)=>{const w=WMO[c]||["",""];return[w[0],!day&&w[2]?w[2]:w[1]]};
const compass=d=>d==null?"":["N","NE","E","SE","S","SW","W","NW"][Math.round(d/45)%8];
const whenStr=iso=>{const t=Date.parse(iso);if(!t)return"";return new Date(t).toDateString()===new Date().toDateString()?T(t/1e3)
 :new Intl.DateTimeFormat([],{weekday:"short",hour:"numeric",minute:"2-digit",timeZone:cfg.tz||undefined}).format(t)};
let wxT;async function loadWx(){clearTimeout(wxT);wxT=setTimeout(()=>{if(chans[ci]&&chans[ci].kind==="weather")loadWx()},3e5);
 let w;try{w=await api("/api/weather")}catch(e){w={configured:true,error:"HERO TV not reachable"}}
 if(chans[ci]&&chans[ci].kind==="weather")drawWx(w);if(w.alerts)applyAlerts(w.alerts)}
function drawWx(w){const box=$("#wx");box.textContent="";paint(box,chans[ci]&&chans[ci].color);
 const head=el("div","wtop");head.append(el("h2",0,w.location||"Weather"),el("span","wclock",T(nowS())));box.append(head);
 if(!w.configured){box.append(el("div","wmsg","No town set yet. Press O for Settings > Weather and type your town."));return}
 if(!w.current){box.append(el("div","wmsg","The weather is not available right now (is the internet connected?). HERO TV will try again in a few minutes."));return}
 const u=w.units||{temp:"°",wind:""},c=w.current,[txt,ic]=wmo(c.code,c.is_day),now=el("div","wnow"),info=el("div");
 now.append(el("div","ic",ic),el("div","t",(c.temp??"–")+u.temp));info.append(el("div","c",txt));
 info.append(el("div","d",`Feels like ${c.feels??"–"}${u.temp}   ·   Wind ${c.wind??"–"} ${u.wind} ${compass(c.wind_dir)}   ·   Humidity ${c.humidity??"–"}%`));
 const td=(w.daily||[])[0];if(td)info.append(el("div","d",`Today: high ${td.hi}${u.temp}, low ${td.lo}${u.temp}`+(td.pop!=null?`, ${td.pop}% chance of rain`:"")));
 now.append(info);box.append(now);
 const al=el("div","walerts");if(w.alerts&&w.alerts.length){for(const a of w.alerts.slice(0,3)){const d=el("div","a "+(a.severity||"unknown").toLowerCase());
   d.append(el("b",0,a.event+(a.ends?"  until "+whenStr(a.ends):"")),el("span",0,a.headline&&a.headline!==a.event?a.headline:a.area));al.append(d)}
   if(w.alerts.length>3)al.append(el("div","ok",`+ ${w.alerts.length-3} more alert(s)`))}
 else al.append(el("div","ok",w.alerts_supported?"No active weather alerts for your area.":"Live alerts are only available for US locations."));box.append(al);
 const o=w.utc_offset||0,fmt=(t,f)=>new Intl.DateTimeFormat([],{...f,timeZone:"UTC"}).format((t+o)*1e3);
 const hrs=el("div","whours");for(const h of (w.hourly||[]).slice(0,10)){const x=el("div");x.append(el("small",0,fmt(h.t,{hour:"numeric"})),el("div","i",wmo(h.code,h.is_day)[1]),el("b",0,(h.temp??"–")+"°"),el("small",0,h.pop?h.pop+"%":" "));hrs.append(x)}box.append(hrs);
 const days=el("div","wdays");(w.daily||[]).forEach((d,k)=>{const x=el("div");x.append(el("small",0,k===0?"Today":fmt(d.t,{weekday:"short"})),el("div","i",wmo(d.code)[1]),el("b",0,`${d.hi??"–"}° / ${d.lo??"–"}°`),el("small",0,d.pop?d.pop+"% rain":" "));days.append(x)});box.append(days);
 box.append(el("div","wfoot",(w.stale?"Showing the last forecast received - the internet seems to be down.   ":"")+"Forecast: Open-Meteo"+(w.alerts_supported?"   ·   Alerts: US National Weather Service":"")+"   ·   updated "+T(w.updated)))}
setInterval(()=>{const c=$("#wx .wclock");if(c)c.textContent=T(nowS())},15e3);
let crawlKey="";function applyAlerts(list){const hot=(list||[]).filter(a=>a.crawl),c=$("#crawl");if(!hot.length){c.classList.remove("on");document.body.classList.remove("alerting");crawlKey="";if(layer==="guide")placePreview(true);return}
 const text=hot.map(a=>`${a.event.toUpperCase()}${a.ends?" until "+whenStr(a.ends):""}  -  ${a.area||a.headline}`).join("          ●          ");
 if(text!==crawlKey){crawlKey=text;const sp=$("#crawl span");sp.textContent=text;sp.style.setProperty("--dur",Math.max(20,text.length*.2)+"s")}const was=c.classList.contains("on");c.classList.add("on");document.body.classList.add("alerting");if(!was&&layer==="guide"){drawGuide();placePreview(true)}}
async function pollAlerts(){try{const j=await api("/api/weather/alerts");if(j.configured)applyAlerts(j.alerts)}catch(e){}}
setInterval(pollAlerts,12e4);

/* ---- rename (F3 = this video, F4 = the whole show) ---- */
let renCtx=null;
let infoCtx=null;
async function openInfo(){const t=renameTarget();if(!t)return;infoCtx={back:layer,t};layer="info";
 for(const id of ["#guide","#lib","#home","#help","#check","#osd"])show(id,false);placePreview(false);$("#q").blur();show("#info",true);paint($("#info"),theme.color);
 $("#in-t").textContent=t.title||"";$("#in-m").textContent=$("#in-tag").textContent=$("#in-plot").textContent=$("#in-cast").textContent=$("#in-note").textContent="";
 $("#in-bg").style.backgroundImage=`url(${withK("/thumb/"+t.id)})`;
 const pic=$("#in-pic");pic.textContent="";pic.style.background=`center/cover no-repeat url(${withK("/thumb/"+t.id)}), ${tile(t.title)}`;pic.classList.add("wide");pic.classList.remove("noimg");
 {const probe=new Image();probe.onerror=()=>{if(infoCtx&&infoCtx.t===t){pic.classList.add("noimg");pic.append(el("span","pic-t",t.series||t.title||""))}};probe.src=withK("/thumb/"+t.id)}
 const btns=$("#in-btns");btns.textContent="";
 if(infoCtx.back==="lib")btns.append(sBtn("Play",()=>closeInfo(true),"pri"));btns.append(sBtn("Back",()=>closeInfo(false)));
 let d=null;try{d=await api("/api/info/"+t.id)}catch(e){}
 if(layer!=="info"||!d)return;
 $("#in-t").textContent=d.title||t.title;
 $("#in-m").textContent=[d.year,d.runtime_min?d.runtime_min+" min":"",d.rating?"★ "+d.rating.toFixed(1):"",(d.genres||[]).join(", ")].filter(Boolean).join("  ·  ");
 $("#in-tag").textContent=d.tagline||"";$("#in-plot").textContent=d.plot||"";
 $("#in-cast").textContent=(d.cast||[]).length?"Starring "+d.cast.join(", "):"";
 if(d.poster){$("#in-bg").style.backgroundImage=`url(${withK(`/poster/${t.id}`)})`;pic.style.background=`center/cover no-repeat url(${withK(`/poster/${t.id}?v=${Date.now()%1e6}`)}), ${tile(t.title)}`;pic.classList.remove("wide","noimg");pic.textContent=""}
 $("#in-note").textContent=d.plot?"":d.has_key?(d.searched?"No description was found for this title online.":"Looking this up in the background... check again in a minute."):"No description yet. Add a free TMDB key in Settings > Cover art to get posters, plots, cast and ratings.";
 moveUI(t,d);
 $("#in-cr").textContent=d.source==="TMDB"?"Cover art and descriptions: TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.":"";
 hints($("#in-hints"),[["Enter",infoCtx.back==="lib"?"play":"back"],...(REMOTE?[]:[["M","move to another channel"]]),["Esc","back"]])}
/* ---- wrong channel? move a film (or a whole show) and remember it ---- */
function moveUI(t,d){const old=$("#in-on");if(old)old.remove();const om=$("#in-miss");if(om&&!d.missingAsked)om.remove();const old2=$("#in-move");if(old2)old2.remove();
 const on=el("div");on.id="in-on";on.textContent=(d.on||[]).length?"On: "+d.on.join(", "):"Not on a channel yet";$("#in-m").after(on);
 if(t.series&&d.has_key&&!d.missingAsked){d.missingAsked=true;api("/api/missing/"+t.id).then(m=>{if(!m.known||!infoCtx||infoCtx.t!==t)return;const x=el("div");x.id="in-miss";
  x.textContent=m.missing?`You have ${m.aired-m.missing} of ${m.aired} aired episodes - missing ${m.text}`:`You have all ${m.aired} aired episodes`;const o=$("#in-miss");if(o)o.remove();$("#in-on").after(x)}).catch(()=>{})}
 if(REMOTE||!(d.channels||[]).length)return;
 $("#in-btns").append(sBtn("Move to another channel",()=>openMove()));infoCtx.move={t,d}}
function openMove(){if(!infoCtx||!infoCtx.move||$("#in-move"))return;const {t,d}=infoCtx.move;
 const box=el("div","tcard");box.id="in-move";const show=t.series&&d.episodes>1;
 box.append(el("h4",0,"Where does it belong?"),el("small",0,(show?`Moves all ${d.episodes} episodes of ${t.series}. `:"")+"Pick one or more channels, then Save. It leaves the channels you untick."));
 const pick=new Set(d.on_ids||[]),row=el("div","picks");
 for(const c of d.channels){const b=sBtn(c.name,()=>{pick.has(c.id)?pick.delete(c.id):pick.add(c.id);b.classList.toggle("on",pick.has(c.id));b.setAttribute("aria-pressed",pick.has(c.id))});b.classList.toggle("on",pick.has(c.id));b.setAttribute("aria-pressed",pick.has(c.id));row.append(b)}
 const rl=el("label","lb"),rc=el("input");rc.type="checkbox";rc.checked=true;rl.append(rc,show?" Remember: new episodes of this show go here too":" Remember: other copies of this title go here too");
 const bar=el("div","sbar"),note=el("small");
 const save=sBtn("Save",async()=>{if(!pick.size){note.textContent="Pick at least one channel.";return}save.disabled=true;note.textContent="Moving...";
  try{await pj("/api/job",{name:"move",media_id:t.id,channels:[...pick],remember:rc.checked});await waitJob(note);if(infoCtx&&infoCtx.t===t){box.remove();const dd=await api("/api/info/"+t.id);moveUI(t,dd)}}
  catch(e){note.textContent=String(e.message||e).replace(/^Error: /,"");save.disabled=false}},"pri");
 bar.append(save,sBtn("Cancel",()=>{box.remove();const b=$("#in-btns button:last-child");if(b)b.focus()}));box.append(row,rl,bar,note);
 $("#in-btns").after(box);const f=row.querySelector("button.on")||row.querySelector("button");if(f)f.focus()}
async function waitJob(note){for(let i=0;i<400;i++){await new Promise(r=>setTimeout(r,700));const j=(await api("/api/job")).job;if(!j||j.state!=="running"){
 const ok=j&&j.state==="done";const t=ok?(j.lines.filter(x=>x.includes("[ OK ]")).pop()||"Done.").replace("[ OK ]","").trim():"That did not work: "+((j&&j.lines.slice(-1)[0])||"");if(note)note.textContent=t;toast(t);if(!ok)throw new Error(t);return j}}}
function closeInfo(play){const c=infoCtx;infoCtx=null;show("#info",false);layer=c?c.back:"";
 if(layer==="lib"){show("#lib",true);$("#q").focus();if(play&&items[li])return startVod(items[li])}
 else if(layer==="guide"){show("#guide",true);drawGuide();placePreview(true)}else{layer="";show("#osd",false)}}
function renameTarget(){if(layer==="lib")return items[li]&&{id:items[li].id,title:items[li].title,series:items[li].series};
 if(layer==="guide"){const s=g.data[g.row]&&inSlot(g.data[g.row],g.t);return s&&{id:s.media_id,title:s.title,series:s.series}}
 if(vod)return{id:vod.id,title:vod.title,series:vod.series};
 if(slot&&!wxOn())return{id:slot.media_id,title:slot.title,series:slot.series};return null}
const wxOn=()=>{const c=chans[ci];return c&&c.kind==="weather"};
function openRename(kind){const t=renameTarget();if(!t)return;if(kind==="series"&&!t.series)return flashRen("This video is not part of a show, so use F3 to rename just this one.");
 renCtx={t,kind,back:layer};layer="rename";const cur=kind==="series"?t.series:t.title;
 $("#ren-h").textContent=kind==="series"?"Rename the whole show":"Rename this video";
 $("#ren-was").textContent="Now: "+cur;
 $("#ren-s").textContent=kind==="series"?`Changes the show name on every episode of "${t.series}". Empty = back to the folder name. Enter saves, Esc cancels.`:"A short, clean name. Empty = back to the name from the file. Enter saves, Esc cancels.";
 $("#ren-s").classList.remove("err");const i=$("#ren-in");i.value=cur;show("#ren",true);i.focus();i.select()}
function flashRen(text){renCtx={t:null,back:layer};layer="rename";$("#ren-h").textContent="Can't rename the show";$("#ren-was").textContent="";$("#ren-s").textContent=text;$("#ren-s").classList.remove("err");show("#ren",true);setTimeout(()=>{if(renCtx&&!renCtx.t)closeRen()},2600)}
function closeRen(){const b=renCtx&&renCtx.back;show("#ren",false);renCtx=null;layer=b||"";$("#ren-in").blur();if(layer==="lib")$("#q").focus()}
async function saveRen(){if(!renCtx||!renCtx.t)return;const{t,kind}=renCtx,val=$("#ren-in").value.trim();
 try{const r=await fetch("/api/rename",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({media_id:t.id,[kind]:val})}),j=await r.json();
  if(!r.ok){$("#ren-s").textContent=j.error||"Could not rename.";$("#ren-s").classList.add("err");return}
  const back=renCtx.back;closeRen();
  const fix=x=>{if(x&&(x.media_id===t.id||x.id===t.id)){x.title=j.title;x.series=j.series}else if(kind==="series"&&x&&x.series===t.series&&(x.media_id||x.id)){x.series=j.series}};
  fix(slot);fix(nextSlot);fix(vod);
  if(back==="lib"){const keep=li;await search();li=Math.min(keep,items.length-1);drawList()}
  else if(back==="guide"){await loadGuide();drawGuide()}
  else osd(true)}
 catch(e){$("#ren-s").textContent="Could not reach HERO TV.";$("#ren-s").classList.add("err")}}
$("#ren-in").addEventListener("keydown",e=>{e.stopPropagation();if(e.key==="Enter"){e.preventDefault();saveRen()}else if(e.key==="Escape"){e.preventDefault();closeRen()}});

/* ---- reminders that are due: "Starting now on ... - Enter to watch" ---- */
const remShown=new Set();let remDue=null;
const remOpen=()=>$("#remind")&&$("#remind").classList.contains("on");
function remClose(){const r=$("#remind");if(r)r.classList.remove("on");remDue=null}
function remWatch(){const d=remDue;remClose();if(!d)return;const i=chans.findIndex(c=>c.id===d.channel);if(i<0)return toast("That channel is not on the TV right now.");
 if(layer!=="")closeAll();vod=null;tune(i)}
async function remPoll(){try{const r=await api("/api/reminders");for(const d of r.due){const k=d.channel+":"+d.start;if(remShown.has(k))continue;
  if(!vod&&chans[ci]&&chans[ci].id===d.channel)continue;                 /* already watching it (asks again if you switch away) */
  remShown.add(k);
  let box=$("#remind");if(!box){box=el("div");box.id="remind";box.setAttribute("role","alertdialog");document.body.append(box)}
  box.textContent="";paint(box,theme.color);const late=r.now>d.start;
  box.append(el("small",0,late?"YOUR REMINDER - IT HAS STARTED":"YOUR REMINDER - STARTING NOW"),el("b",0,d.title),el("span",0,`${d.number??""} ${d.channel_name} at ${T(d.start)}`));
  const row=el("div","sbar"),w=sBtn("Watch (Enter)",remWatch,"pri"),x=sBtn("Not now (Esc)",remClose);row.append(w,x);box.append(row);
  remDue=d;box.classList.add("on");clearTimeout(box._t);box._t=setTimeout(remClose,120000);return}}catch(e){}}
setInterval(remPoll,20000);setTimeout(remPoll,6000);
/* ---- keys (keyboard / HDMI-CEC remote) ---- */
addEventListener("keydown",e=>{const k=e.key;
 if(layer==="rename"||e.ctrlKey||e.metaKey||e.altKey)return;
 if(remOpen()&&(k==="Enter"||k==="Escape")&&!(document.activeElement&&/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName))){e.preventDefault();e.stopPropagation();return k==="Enter"?remWatch():remClose()}
 if(sleeping){e.preventDefault();return wake()}
 if(neOpen()){if(k==="Enter"||k===" "){e.preventDefault();nePlay()}else if(k==="Escape"||k==="Backspace"){e.preventDefault();neStop()}return}
 if(newsOpen()){const a=document.activeElement,inPick=$("#news").dataset.kind==="lineup"&&a&&a.closest&&a.closest("#nw-l");
  if($("#news").dataset.kind==="lineup"&&k.startsWith("Arrow")){e.preventDefault();spatialMove(k,$("#news"),true);return}
  if(inPick&&(k==="Enter"||k===" "))return;                       /* the focused channel button toggles itself */
  if(k==="Enter"||k==="Escape"||k===" "){e.preventDefault();closeNews()}return}
 if(ctxIsOpen())return ctxKey(e);
 if(layer==="settings")return settingsKey(e);
 if(layer==="info"){const a=document.activeElement,inside=!!(a&&a.closest&&a.closest("#info")&&/^(BUTTON|INPUT|SELECT)$/.test(a.tagName));
  if(k==="Escape"||(k==="Backspace"&&!inside)||((k==="d"||k==="D")&&!inside)){e.preventDefault();const mv=$("#in-move");if(mv){mv.remove();const b=$("#in-btns button:last-child");if(b)b.focus()}else closeInfo(false)}
  else if((k==="m"||k==="M")&&!REMOTE){e.preventDefault();openMove()}
  else if(k.startsWith("Arrow")&&!arrowOwnedByField(a,k)){e.preventDefault();spatialMove(k,$("#info"),true)}
  else if(k==="Enter"&&!inside){e.preventDefault();closeInfo(true)}return}
 if((k==="d"||k==="D")&&(layer==="guide"||layer===""||vod)&&!(layer==="lib")){e.preventDefault();return openInfo()}
 if(layer==="home")return homeKey(e);
 if(layer==="check")return checkKey(e);
 if(layer==="help"){if(k==="Escape"||k==="Backspace"||k==="?"||k==="F1"||k==="h"||k==="H"){e.preventDefault();return helpBack==="home"?openHome():closeAll()}return}
 if((k==="F3"||k==="F4")&&(layer==="lib"||layer==="guide"||layer===""||vod)){e.preventDefault();return openRename(k==="F4"?"series":"title")}
 if(layer==="lib"){const mv=d=>{li=Math.max(0,Math.min(items.length-1,li+d));drawList();e.preventDefault()};
  if(k==="Tab"){e.preventDefault();view=VIEWS[(VIEWS.findIndex(x=>x[0]===view)+1)%VIEWS.length][0];saveView();search();return}
  if(k==="F2"&&items[li]){e.preventDefault();const it=items[li],on=!it.favorite;it.favorite=on?1:0;post("/api/favorite",{media_id:it.id,on});counts.favorites+=on?1:-1;
   if(view==="favorites"&&!on){items.splice(li,1);li=Math.min(li,items.length-1)}drawList();return}
  if(k==="F8"&&items[li]){e.preventDefault();return openInfo()}
  if(k==="Escape"||k==="Backspace"&&!$("#q").value)closeAll();else if(k==="ArrowDown")mv(cols);else if(k==="ArrowUp")mv(-cols);
  else if(k==="ArrowRight")mv(1);else if(k==="ArrowLeft")mv(-1);else if(k==="Enter"&&items[li])startVod(items[li]);return}
 if(layer==="guide"){if(k==="Escape"||k==="g"||k==="G")closeAll();else if(k.startsWith("Arrow")||k==="Enter"||k==="r"||k==="R"){e.preventDefault();guideKey(k)}return}
 if(layer===""){
  if(k==="h"||k==="H"||k==="Home"||k==="BrowserHome"){e.preventDefault();return openHome()}
  if(k==="?"||k==="F1"){e.preventDefault();return openHelp("")}
  if(k==="s"||k==="S")return cycleSleep();
  if(k==="o"||k==="O"){e.preventDefault();return openSettings()}
  if(k==="c"||k==="C")return cycleSub();
  if(k==="t"||k==="T")return setBig(!document.body.classList.contains("big"),true);
  if(vod){const lk=k.toLowerCase();
   if(lk==="j"){e.preventDefault();return markSkip("intro",e.shiftKey)}
   if(lk==="e"){e.preventDefault();return markSkip("outro",e.shiftKey)}
   if(lk==="n"&&vod.skip&&vod.skip.intro>v.currentTime)return seekTo(vod.skip.intro)}
  else if(k==="Escape"){e.preventDefault();return openHome()}}
 if(vod){const jump={ArrowLeft:-10,ArrowRight:30,PageDown:-300,PageUp:300,MediaRewind:-30,MediaFastForward:30};   /* on-demand controls */
  if(k in jump){e.preventDefault();return seekBy(jump[k])}
  if(/^\d$/.test(k)&&isFinite(v.duration))return seekTo(v.duration*+k/10);
  if(k==="ArrowUp"||k==="ArrowDown"){e.preventDefault();v.volume=Math.min(1,Math.max(0,v.volume+(k==="ArrowUp"?.1:-.1)));return osd(true)}
  if(k===" "||k==="MediaPlayPause"||k==="k"||k==="K"){e.preventDefault();v.paused?v.play():v.pause();return}
  if(k==="Escape"||k==="Backspace"){e.preventDefault();return tune(ci)}}
 if(/^\d$/.test(k)){numBuf+=k;$("#tune").textContent=numBuf;paint($("#tune"),(chans.find(c=>String(c.number)===numBuf)||chans[ci]||{}).color);show("#tune",true);clearTimeout(numT);numT=setTimeout(()=>{const i=chans.findIndex(c=>c.number==numBuf);numBuf="";show("#tune",false);if(i>=0)tune(i)},1500);return}
 switch(k){case"ArrowUp":case"PageUp":case"ChannelUp":tune(ci+1);break;case"ArrowDown":case"PageDown":case"ChannelDown":tune(ci-1);break;
  case"g":case"G":case"Enter":openGuide();break;case"l":case"L":case"/":e.preventDefault();openLib();break;case"i":case"I":osd();break;
  case"m":case"M":v.muted=!v.muted;msg(v.muted?"Muted":"");setTimeout(()=>msg(""),900);break;case"f":case"F":document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen().catch(()=>{});break;
  case"ArrowLeft":v.volume=Math.max(0,v.volume-.1);break;case"ArrowRight":v.volume=Math.min(1,v.volume+.1);break;
  case"r":case"R":startOver();break;case"Backspace":if(prevCi>=0){e.preventDefault();tune(prevCi)}break}});
/* ---- settings ---- */
async function pj(path,body){const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});let j={};try{j=await r.json()}catch(e){}
 if(!r.ok)throw new Error(j.error||"That did not work.");return j}
async function loadTheme(){try{theme=Object.assign(theme,await api("/api/theme"));document.title=theme.name;document.documentElement.style.setProperty("--brand",theme.color);applyCues(theme.subs);applyComfort()}catch(e){}}
function applyCues(st){st=st||{};const b=document.body.classList;b.toggle("cue-l",st.size==="large");b.toggle("cue-xl",st.size==="xl");b.toggle("cue-none",st.bg==="none");b.toggle("cue-yellow",st.color==="yellow")}
const SW=["#ffcf1f","#ff3b3b","#3d6bff","#3ddc84","#b06bff","#ff8c00","#ff2e88","#1fd1b4"];
const SCATS=[["look","Appearance"],["chan","Channels"],["lib","Media library"],["weather","Weather"],["art","Cover art"],["tools","Tools"],["devices","Other devices"],["about","Backup and about"]];
let chList=null,chSel=null,chShorts=0,chChoices={folders:[],series:[]};let sCat="look",sData=null,sDirty=false,sLeave=false;
function sMsg(t,cls){const m=$("#st-msg");if(m){m.textContent=t||"";m.className="smsg"+(cls?" "+cls:"")}}
function sField(label,help,input,row){const f=el("div","sf"+(row?" row":""));if(label)f.append(el("label",0,label));if(input)f.append(input);if(help)f.append(el("small",0,help));return f}
function sBtn(text,fn,cls){const b=el("button","sbtn"+(cls?" "+cls:""),text);b.type="button";b.onclick=fn;return b}
function sInput(val,type,ph){const i=el("input");i.type=type||"text";i.value=val||"";if(ph)i.placeholder=ph;i.autocomplete="off";i.spellcheck=false;i.addEventListener("input",()=>{sDirty=true;sLeave=false});return i}
async function sSave(changes,okText,after){sMsg("Saving...");try{const r=await pj("/api/settings",changes);sDirty=false;sLeave=false;
  sData=await api("/api/settings");if(after)await after();sMsg(okText+(r&&r.restart?" Restart HERO TV for this to take effect.":""),"ok")}
 catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}}
async function sAct(name,btn){const old=btn.textContent;btn.disabled=true;btn.textContent="Working...";
 try{const r=await pj("/api/action",{name});sMsg(r.message||"Done.","ok")}catch(e){sMsg(String(e.message||e),"err")}btn.disabled=false;btn.textContent=old}
async function openSettings(cat){if(REMOTE)return toast("Settings are on the PC.");atData=null;if(cat)sCat=cat;layer="settings";sDirty=false;sLeave=false;chList=null;chSel=null;tData=null;
 for(const id of ["#guide","#lib","#home","#help","#check","#info","#osd","#msg"])show(id,false);placePreview(false);show("#settings",true);paint($("#settings"),theme.color);
 hints($("#st-hints"),[["↑ ↓ ← →","move"],["Enter","choose"],["Esc","back"]]);
 try{sData=await api("/api/settings")}catch(e){sData=null}drawSettings()}
function drawSettings(){const nav=$("#st-nav"),main=$("#st-main");jumped=false;
 {const a=document.activeElement;if(a&&main.contains(a)){const all=[...main.querySelectorAll(FOCUSABLE)];sKeep={cat:sCat,i:all.indexOf(a),text:a.textContent,type:a.type,top:main.scrollTop}}
  else if(sKeep&&(sKeep.cat!==sCat||(a&&a!==document.body)))sKeep=null}       /* a "Loading..." redraw in between keeps your place */
 nav.textContent=main.textContent="";
 for(const[k,n]of SCATS){const b=el("button",k===sCat?"on":"",n);b.type="button";b.setAttribute("role","tab");b.onclick=()=>sGo(k);b.dataset.k=k;nav.append(b)}
 if(!sData){main.append(el("div","empty","Settings could not be loaded. Make sure HERO TV is still running."));return}
 const d=sData,msg=el("div","smsg");msg.id="st-msg";
 if(!REMOTE&&sCat==="look"){const ab=el("div");ab.id="st-attn";main.append(ab);drawAttn()}
 if(sCat==="look"){main.append(el("h3",0,"Appearance"));
  const name=sInput(d.station.name),tag=sInput(d.station.tagline);let col=d.station.color;
  const sw=el("div","sw");const pick=c=>{col=c;sDirty=true;sLeave=false;[...sw.children].forEach(b=>b.classList.toggle("on",b.dataset.c.toLowerCase()===c.toLowerCase()));hex.value=c};
  const hex=sInput(col,"text","#ffcf1f");hex.size=9;hex.addEventListener("input",()=>{if(/^#[0-9a-fA-F]{6}$/.test(hex.value))pick(hex.value)});
  for(const c of SW){const b=el("button",c.toLowerCase()===col.toLowerCase()?"on":"");b.type="button";b.dataset.c=c;b.style.background=c;b.title=c;b.setAttribute("aria-label","Color "+c);b.onclick=()=>pick(c);sw.append(b)}
  main.append(sField("Station name","Shown on the home screen and the browser tab.",name),sField("Greeting","The line under the name.",tag),
   sField("Main color","Pick one, or type a code like #ff3b3b.",sw),sField("",null,hex,true));
  main.append(el("div","sbar")),main.lastChild.append(sBtn("Save",()=>sSave({station:{name:name.value,tagline:tag.value,color:col}},"Saved.",async()=>{await loadTheme();paint($("#settings"),theme.color);drawSettings()}),"pri"),
   sBtn("Restore the default look",()=>{if(!main.dataset.sure){main.dataset.sure=1;sMsg("Press the button again to restore the standard name, greeting and color.","err");return}
    delete main.dataset.sure;sSave({reset_station:true},"Default look restored.",async()=>{await loadTheme();drawSettings()})},"warn"));main.append(msg);
  main.append(el("h3",0,"Viewing"),sField("","These change straight away, no Save needed.",null));
  const big=el("input");big.type="checkbox";big.checked=document.body.classList.contains("big");big.onchange=()=>setBig(big.checked,true);
  const bl=el("label","lb");bl.append(big," Bigger text");bl.style.display="flex";bl.style.gap="1vw";main.append(sField("",'Makes every screen easier to read from the couch. Same as pressing T.',bl));
  const wnd=el("input");wnd.type="checkbox";wnd.checked=!!d.windowed;wnd.onchange=()=>sSave({windowed:wnd.checked},wnd.checked?"HERO TV will open in a normal window from now on.":"HERO TV will open full screen from now on.");
  const wl=el("label","lb");wl.append(wnd," Open in a window instead of full screen");wl.style.display="flex";wl.style.gap="1vw";main.append(sField("","Takes effect the next time you start HERO TV. F still switches full screen on and off.",wl));
  { const st=Object.assign({size:"normal",bg:"box",color:"white"},d.subs_style),row=el("div","sbar");
    const pick=(opts,key)=>{const sel=el("select");for(const[v,t]of opts){const o=el("option",0,t);o.value=v;if(st[key]===v)o.selected=true;sel.append(o)}
     sel.onchange=()=>{st[key]=sel.value;applyCues(st);sSave({subs_style:st},"Subtitle style saved.",async()=>{await loadTheme()})};sel.dataset.k=key;return sel};
    row.append(pick([["normal","Normal size"],["large","Large"],["xl","Extra large"]],"size"),pick([["box","On a dark box"],["none","Outline only"]],"bg"),pick([["white","White"],["yellow","Yellow"]],"color"));
    row.id="cue-style";main.append(sField("Subtitles","How subtitles look on the TV and on paired phones. Press C while watching to turn them on.",row))}
  { const lg=el("select");for(const[v,t]of[["sometimes","Now and then (when a show starts, and briefly every 5 minutes)"],["always","Always"],["off","Off"]]){const o=el("option",0,t);o.value=v;if((d.logo||"sometimes")===v)o.selected=true;lg.append(o)}
    lg.onchange=()=>sSave({logo:lg.value},"Channel logo saved.",async()=>{await loadTheme()});
    main.append(sField("Channel logo","The channel's number and name in the corner of the picture, like a TV network's logo. Also on the Roku app.",lg))}
  { const th=el("select");for(const[v,t]of[["classic","Classic dark"],["black","Pure black (best on OLED TVs)"],["retro","Retro cable (blue, like a 90s cable box)"]]){const o=el("option",0,t);o.value=v;if(((d.comfort||{}).theme||"classic")===v)o.selected=true;th.append(o)}
    th.onchange=()=>sSave({theme:th.value},"Look saved.",async()=>{await loadTheme()});main.append(sField("Look","The colors of the menus and the guide, here and in the Roku app.",th))}
  { const cf=Object.assign({level:true,screensaver:true,safe_margin:0,night:{on:false,from:"22:00",to:"07:00"}},d.comfort);
    const box=(key,text,on,save)=>{const i=el("input");i.type="checkbox";i.checked=on;const l=el("label","lb");l.append(i," "+text);l.style.display="flex";l.style.gap="1vw";i.onchange=()=>save(i.checked);return l};
    main.append(sField("Even volume","Quiet videos are turned up and loud ones down, so films, shorts and episodes all play at about the same volume (each video is measured once, in the background). On the TV screen and phones; Roku TVs have their own 'volume leveling' in the TV's sound settings.",
     box("level","Even out the volume between videos",cf.level,on=>sSave({level_volume:on},"Saved.",async()=>{await loadTheme()}))));
    const tsel=v=>{const i=el("select");for(let q=0;q<48;q++){const h=Math.floor(q/2),mm=q%2?"30":"00",val=String(h).padStart(2,"0")+":"+mm;const o=el("option",0,`${h%12||12}:${mm} ${h<12?"AM":"PM"}`);o.value=val;if(val===v)o.selected=true;i.append(o)}return i};
    const nf=tsel(cf.night.from),nt=tsel(cf.night.to),nrow=el("div","sbar");
    const nsave=on=>sSave({night:{on,from:nf.value,to:nt.value}},"Night mode saved.",async()=>{await loadTheme()});
    const nb=box("night","Night mode",cf.night.on,on=>nsave(on));nf.onchange=nt.onchange=()=>nsave(nb.querySelector("input").checked);
    nrow.append(nb,el("span",0,"from"),nf,el("span",0,"to"),nt);
    main.append(sField("Night mode","Between these times menus are dimmer and warmer, everything plays a little quieter and loud bangs are evened out.",nrow));
    main.append(sField("Screensaver","When an on-demand video is paused for 3 minutes, or a menu is left open for 5, pictures from your library drift across the screen (kind to OLED TVs). Any key brings you back. Never during live TV.",
     box("saver","Screensaver",cf.screensaver,on=>sSave({screensaver:on},"Saved.",async()=>{await loadTheme()}))));
    const sm=el("select");for(const[v,t]of[[0,"None"],[2.5,"Small"],[5,"Large"]]){const o=el("option",0,t);o.value=v;if(Number(cf.safe_margin)===v)o.selected=true;sm.append(o)}
    sm.onchange=()=>sSave({safe_margin:Number(sm.value)},"Saved.",async()=>{await loadTheme()});
    main.append(sField("TV edge margin","If your TV cuts off the edges of menus, move everything in a little. The picture itself is not changed.",sm))}
}
 else if(sCat==="chan"){drawChannelsCfg(main,msg)}
 else if(sCat==="tools"){drawTools(main,msg)}
 else if(sCat==="devices"){drawDevices(main,msg)}
 else if(sCat==="lib"){main.append(el("h3",0,"Media library"));
  const dir=sInput(d.media_dir);dir.style.width="50vw";
  main.append(sField("Media folder","Where your videos live. Changing it needs HERO TV to be restarted. Type the full path, for example D:\\Movies.",dir));
  const ai=el("input");ai.type="checkbox";ai.checked=d.auto_inbox;const al=el("label","lb");al.append(ai," File new videos in the Inbox automatically");al.style.display="flex";al.style.gap="1vw";ai.onchange=()=>{sDirty=true;sLeave=false};
  main.append(sField("",'While HERO TV is open, videos dropped into the Inbox folder are put on the right channel by their title.',al));
  const bar=el("div","sbar");bar.append(sBtn("Save",()=>{const c={auto_inbox:ai.checked};if(dir.value.trim()!==d.media_dir)c.media_dir=dir.value;sSave(c,"Saved.")},"pri"));
  const b1=sBtn("Check library now",()=>sAct("rescan",b1)),b2=sBtn("Open media folder",()=>sAct("open-media",b2)),b3=sBtn("Open Inbox",()=>sAct("open-inbox",b3));bar.append(b1,b2,b3);main.append(bar,msg)}
 else if(sCat==="weather"){main.append(el("h3",0,"Weather"));
  const w=sInput("","text","City name or postcode");w.style.width="30vw";
  main.append(sField("Current location",d.weather||"Not set yet - the Weather channel needs one.",null),sField("New location","Looked up online once. Example: Chicago, or 60601.",w));
  main.append(el("div","sbar"));main.lastChild.append(sBtn("Save",()=>sSave({weather:w.value},w.value.trim()?"Weather location saved.":"Weather location cleared.",()=>drawSettings()),"pri"));main.append(msg)}
 else if(sCat==="art"){main.append(el("h3",0,"Cover art and descriptions"));
  const k=sInput("","password","Paste your TMDB key");k.style.width="40vw";
  main.append(sField("Status",d.art.has_key?"A key is saved ("+d.art.key_hint+"). Press D on any video to see its poster, story, cast and rating.":"No key yet, so only your own pictures and the video screengrabs are shown.",null),
   sField(d.art.has_key?"Replace the key":"TMDB key","Free: make an account at themoviedb.org, then Settings > API > request a personal key. Only each title and year are sent to TMDB.",k));
  const bar=el("div","sbar");bar.append(sBtn("Save key",()=>sSave({tmdb_key:k.value},"Key saved. Pictures fill in over the next few minutes.",()=>drawSettings()),"pri"));
  if(d.art.has_key)bar.append(sBtn("Remove key",()=>{if(!main.dataset.sure){main.dataset.sure=1;sMsg("Press again to remove the key. Posters already downloaded stay.","err");return}delete main.dataset.sure;sSave({tmdb_key:""},"Key removed.",()=>drawSettings())},"warn"));
  main.append(bar,msg,el("small",0,"This product uses the TMDB API but is not endorsed or certified by TMDB."))}
 else{main.append(el("h3",0,"Updates"));const ub=el("div","tcard");ub.id="upd";main.append(ub);drawUpdate(ub,d);
  main.append(el("h3",0,"Something not right?"));
  {const c=tCard("Report a problem","Makes one report with what is needed to find the problem: version, settings (keys hidden), library counts, errors on this screen and the last lines of the log. Copy it and paste it into your chat with Claude. HERO TV does not send it anywhere.");
   const note=el("textarea");note.placeholder="What happened? (for example: on Home, pressing Up moves sideways)";note.rows=3;note.style.width="100%";
   const out=el("textarea");out.readOnly=true;out.rows=8;out.style.cssText="width:100%;display:none;font-family:ui-monospace,Consolas,monospace;font-size:1.5vh";
   const bar=el("div","sbar"),info=el("small");
   const mk=sBtn("Make a report",async()=>{mk.disabled=true;info.textContent="Making the report...";try{const r=await pj("/api/report",{note:note.value,page:`${layer||"tv"}/${sCat} ${innerWidth}x${innerHeight} ${navigator.userAgent}`});
     out.value=r.text;out.style.display="";cp.style.display="";info.textContent=r.file?"Saved as "+r.file+" - now press Copy and paste it into the chat.":"Press Copy and paste it into the chat."}catch(e){info.textContent=String(e.message||e)}mk.disabled=false},"pri");
   const cp=sBtn("Copy",async()=>{try{await navigator.clipboard.writeText(out.value);toast("Report copied - paste it into the chat (Ctrl+V).")}catch(e){out.focus();out.select();document.execCommand&&document.execCommand("copy");toast("Report selected and copied.")}});cp.style.display="none";
   const of=sBtn("Open reports folder",()=>sAct("open-reports",of));
   bar.append(mk,cp,of);c.append(note,bar,info,out);main.append(c)}
  {const c=tCard("Quit HERO TV","Turns HERO TV off completely on this PC - also when it runs in the background for the Roku app and phones. Click the HERO TV icon to start it again.");
   const b=sBtn("Quit HERO TV",async()=>{if(!c.dataset.sure){c.dataset.sure=1;b.textContent="Press again to quit";return}try{await pj("/api/quit",{});document.body.textContent="";const m=el("div","quitmsg","HERO TV is off. Click the HERO TV icon to start it again.");document.body.append(m)}catch(e){sMsg("Could not quit.","err")}},"warn");
   const r=el("div","sbar");r.append(b);c.append(r);main.append(c)}
  main.append(el("h3",0,"Backup"));
  const bar=el("div","sbar"),b1=sBtn("Back up my settings now",()=>sAct("backup",b1),"pri"),b2=sBtn("Open backups folder",()=>sAct("open-backups",b2)),b3=sBtn("Open log folder",()=>sAct("open-logs",b3));bar.append(b1,b2,b3);
  main.append(sField("","A backup keeps your favorites, resume points, channel settings and look - not the videos themselves.",null),bar,msg);
  const ab=el("input");ab.type="checkbox";ab.checked=d.auto_backup!==false;ab.onchange=()=>sSave({auto_backup:ab.checked},ab.checked?"Weekly backups on.":"Weekly backups off.",()=>drawSettings());
  const abl=el("label","lb");abl.append(ab," Back up automatically every week (keeps the last 8)");abl.style.display="flex";abl.style.gap="1vw";
  main.append(sField("",d.last_backup?"Last backup: "+new Date(d.last_backup.when*1e3).toLocaleString():"No backup yet.",abl));
  const a=d.about,kv=el("div","kv");for(const[x,y]of[["HERO TV version",a.version+" (build "+a.api+")"],["Video tools (ffmpeg)",a.ffmpeg&&a.ffprobe?"installed":"MISSING - Settings > Tools > Install video tools"],["Settings file",a.settings_file],["Log file",a.log_file],["Channel files",a.config_dir]])kv.append(el("span",0,x),el("span",0,y));
  main.append(el("h3",0,"About"),kv)}
 if(sKeep&&sKeep.cat===sCat&&!jumped){const all=[...main.querySelectorAll(FOCUSABLE)].filter(x=>x.getClientRects().length);     /* keep your place after a redraw */
  const t=all.find(x=>x.textContent===sKeep.text&&sKeep.text)||all[Math.min(sKeep.i,all.length-1)];if(t){main.scrollTop=sKeep.top;t.focus({preventScroll:true});sKeep=null;return}
  if(!all.length)return}                                                          /* still loading: try again on the next draw */
 sKeep=null;const sel=nav.querySelector(".on");if(sel&&(document.activeElement===document.body||!document.activeElement))sel.focus()}
let sKeep=null;
/* ---- one-press updates ---- */
let updT=null;
async function drawUpdate(box,d,u){box.textContent="";if(!u){box.append(el("small",0,"Checking..."));try{u=await api("/api/update")}catch(e){box.textContent="";box.append(el("small",0,"Could not ask about updates."));return}}
 if(!box.isConnected)return;box.textContent="";
 const busy=u.phase==="downloading"||u.phase==="installing";
 if(u.available){box.append(el("h4",0,`HERO TV ${u.latest} is ready to install`),el("small",0,`You have ${u.current}. Your videos, favorites, resume points and settings stay as they are.`));
  if(u.notes.length){const ul=el("ul","unotes");for(const n of u.notes)ul.append(el("li",0,n));box.append(ul)}}
 else box.append(el("h4",0,`You have the newest HERO TV (${u.current})`),el("small",0,u.checked?"Last checked "+new Date(u.checked*1e3).toLocaleString()+".":"Not checked yet."));
 if(u.error)box.append(el("small","err",u.error));
 const bar=el("div","sbar");
 if(busy){const pct=u.total?Math.min(100,Math.round(u.done*100/u.total)):0;box.append(el("b",0,u.phase==="downloading"?`Downloading... ${pct}%`:"Installing - HERO TV closes for a moment and starts again by itself. This screen comes back on its own."));
  clearTimeout(updT);updT=setTimeout(()=>{if(layer==="settings"&&sCat==="about")api("/api/update").then(x=>drawUpdate(box,d,x)).catch(()=>{})},1000)}
 else{if(u.available&&u.can_install){const b=sBtn("Install now",async()=>{b.disabled=true;try{drawUpdate(box,d,await pj("/api/update",{op:"install"}))}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err");b.disabled=false}},"pri");bar.append(b)}
  if(u.available&&!u.can_install)box.append(el("small",0,"This copy runs from Python source: update it with Update-HERO-TV.bat."));
  const c=sBtn("Check now",async()=>{c.disabled=true;box.append(el("small",0,"Asking GitHub..."));try{drawUpdate(box,d,await pj("/api/update",{op:"check"}))}catch(e){c.disabled=false}});bar.append(c);
  if(u.page){const g=sBtn("Release page",()=>window.open(u.page,"_blank"));bar.append(g)}}
 box.append(bar);
 const au=el("input");au.type="checkbox";au.checked=u.auto!==false;au.onchange=()=>sSave({auto_update:au.checked},au.checked?"HERO TV will look for updates by itself.":"Automatic update checks are off.");
 const l=el("label","lb");l.append(au," Look for updates by itself (every few hours) and tell me when one is ready");l.style.display="flex";l.style.gap="1vw";box.append(l)}
async function updateNudge(){if(REMOTE)return;try{const u=await api("/api/update");if(u.last_error)toast(u.last_error);else if(u.available&&u.can_install){let seen="";try{seen=localStorage.getItem("updSeen")||""}catch(e){}
 if(seen!==u.latest){toast(`HERO TV ${u.latest} is ready - Settings (O) > Backup and about > Install now`);try{localStorage.setItem("updSeen",u.latest)}catch(e){}}}}catch(e){}}
setTimeout(updateNudge,30e3);setInterval(updateNudge,3*3600e3);

/* ---- Tools: the jobs the .bat files used to do, run in the background ---- */
let tData=null,jobT=null,jobSeen=0;
function jobPoll(){clearTimeout(jobT);if(layer!=="settings")return;api("/api/job").then(j=>{drawJob(j.job);if(j.job&&j.job.state==="running")jobT=setTimeout(jobPoll,1500);
 else if(j.job&&j.job.id!==jobSeen){jobSeen=j.job.id;toast(j.job.title+(j.job.state==="done"?": finished.":": did not finish - see Settings > Tools."));atData=null;if(sCat==="tools"){tData=null;drawSettings()}}}).catch(()=>{})}
const JOB_WHY=[[/cannot read this file as a video|not a video file/i,"This file cannot be read as a video - it may be damaged, or not a video."],
 [/came out shorter/i,"The fixed copy came out shorter than the original, so the original was kept. Nothing was changed."],
 [/ffmpeg could not/i,"The video tool (ffmpeg) could not convert this one."],
 [/ffmpeg is missing|ffprobe not found|needs ffmpeg/i,"The video tools are missing. Settings > Tools > This PC > Install video tools puts them in."],
 [/not enough free space/i,"There is not enough free space on this drive."],
 [/already exists|already in /i,"A file with this name is already there, so this one was skipped."],
 [/no longer there/i,"The file is no longer there."],
 [/already being fixed/i,"Something else is already fixing this file."]];
function jobSummary(lines){const out=[];let name="";
 for(const raw of lines){const t=raw.trim();if(!t)continue;
  if(!/^\s/.test(raw)&&!/^\[/.test(t)){name=t;continue}
  const m=t.match(/^\[(FAIL|skip)\]\s*(.*)$/i);if(!m)continue;
  let why=m[2];for(const[re,txt]of JOB_WHY)if(re.test(why)){why=txt;break}
  out.push({name,fail:m[1].toUpperCase()==="FAIL",why})}
 return out}
let lastJob=null,jobFull=false;
function drawJob(j){const b=$("#jobbox");if(!b)return;b.textContent="";if(!j){b.style.display="none";return}b.style.display="";
 b.append(el("b",0,(j.state==="running"?"Working: ":j.state==="done"?"Finished: ":"Did not finish: ")+j.title));
 const sum=j.state==="running"?[]:jobSummary(j.lines);
 if(sum.length){const l=el("div","jsum");const bad=sum.filter(x=>x.fail).length;
  l.append(el("small",0,bad?`${bad} thing(s) did not work, ${sum.length-bad} skipped.`:`${sum.length} skipped.`));
  for(const x of sum.slice(0,12))l.append(el("small",x.fail?"jbad":"",(x.name?x.name+": ":"")+x.why));
  if(sum.length>12)l.append(el("small",0,`...and ${sum.length-12} more - see the full log.`));b.append(l);
  const row=el("div","sbar");if(lastJob&&lastJob.name===j.name){const r=sBtn("Try again",()=>runJob(lastJob));row.append(r)}
  const tg=sBtn(jobFull?"Hide the full log":"Show the full log",()=>{jobFull=!jobFull;drawJob(j)});row.append(tg);b.append(row)}
 if(!sum.length||jobFull||j.state==="running"){const pre=el("pre",0,j.lines.slice(-25).join("\n")||"Starting...");b.append(pre);pre.scrollTop=pre.scrollHeight}
 if(j.state==="running")b.append(el("small",0,"You can keep watching TV - this carries on in the background. Closing HERO TV stops it (run it again later to continue)."))}
async function runJob(body,btn){if(btn)btn.disabled=true;sMsg("");lastJob=body;jobFull=false;try{const r=await pj("/api/job",body);drawJob(r.job);jobPoll()}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}if(btn)btn.disabled=false}
function tCard(title,help){const c=el("div","tcard");c.append(el("h4",0,title));if(help)c.append(el("small",0,help));return c}
const gb=n=>n>=1e9?(n/1e9).toFixed(1)+" GB":Math.round(n/1e6)+" MB";
/* intros and credits that HERO TV finds by itself (Settings > Tools) */
let nData=null;
function introsCard(){const c=tCard("Skip intros and credits by themselves","HERO TV listens to the episodes of each show and finds the theme song and the credits they have in common. Watching on demand (PC, phones, Roku), the intro is skipped (← goes back) and the credits go straight on to the next episode. Points you set yourself with J and E always win.");
 if(!nData){c.append(el("small",0,"Loading..."));api("/api/intros").then(j=>{nData=j;if(layer==="settings"&&sCat==="tools")drawSettings()}).catch(()=>{});return c}
 const d=nData;c.append(el("small",0,`Checked ${d.checked} of ${d.episodes} episodes - found intros or credits in ${d.found}.`+(d.running?" Checking now...":"")));
 const cb=el("input");cb.type="checkbox";cb.checked=d.on;const l=el("label","lb");l.append(cb," Check new episodes in the background (a few at a time, at low priority)");l.style.display="flex";l.style.gap="1vw";
 cb.onchange=async()=>{try{nData=await pj("/api/intros",{auto:cb.checked});toast("Saved.")}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}};
 const go=sBtn("Check everything now",async()=>{try{nData=await pj("/api/intros",{op:"now"});sMsg("Checking in the background - this page shows the progress when you come back.","ok");drawSettings()}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}});
 const bar=el("div","sbar");bar.append(go);c.append(l,bar);return c}
/* ready-to-play copies of videos this TV screen cannot play as they are (Settings > Tools) */
let wT=null;
function wBar(p){const b=el("div","pbar"+(p==null?" ind":""));const i=el("i");if(p!=null)i.style.width=p+"%";b.append(i);return b}
function workCard(){const c=tCard("New videos: how far along","Videos that arrive in the Inbox are checked, fixed if needed (picture, then sound) and sorted onto their channels. Ready-to-play copies show here too. Nothing is deleted.");
 const body=el("div","wbody");body.id="wbody";c.append(body);body.append(el("small",0,"Loading..."));workPoll();return c}
function drawWork(j){const b=$("#wbody");if(!b)return;b.textContent="";const act=j.active||[];
 const inb=act.filter(t=>t.kind==="inbox"),cp=act.filter(t=>t.kind==="copy");
 if(inb.length){const bt=j.batch||{};if(bt.total>1)b.append(el("small",0,`Inbox pass: ${Math.min(bt.done+1,bt.total)} of ${bt.total} videos`));
  for(const t of inb){const r=el("div","wrow");r.append(el("b",0,t.name),el("small",0,t.stage+(t.pct!=null?` - ${t.pct}%`:"")),wBar(t.pct));b.append(r)}}
 const w=j.inbox||{};if(w.waiting>(inb.length)){b.append(el("small",0,`Waiting in the Inbox: ${w.waiting-inb.length} (a new file is given about a minute to finish copying first)`));
  const ul=el("div","wlist");for(const n of(w.names||[]).slice(0,8))ul.append(el("small",0,"- "+n));if((w.names||[]).length>8||w.waiting-inb.length>8)ul.append(el("small",0,"...and more"));b.append(ul)}
 const cs=j.copies||{};
 for(const t of act.filter(t=>t.kind==="scan")){const r=el("div","wrow");r.append(el("b",0,"Library: checking for changes"),el("small",0,t.stage),wBar(t.pct));b.append(r)}
 if(cp.length){for(const t of cp){const r=el("div","wrow");r.append(el("b",0,"Copy: "+t.name),el("small",0,t.stage+(t.pct!=null?` - ${t.pct}%`:"")),wBar(t.pct));b.append(r)}}
 if(cs.need)b.append(el("small",0,`Ready-to-play copies: ${cs.ready} of ${cs.need} done`),wBar(Math.round(100*cs.ready/cs.need)));
 if(!act.length&&!w.waiting)b.append(el("small",0,"Nothing new is being processed right now."));
 const rc=(j.recent||[]).slice(0,6);if(rc.length){b.append(el("small",0,"Recently:"));for(const r of rc)b.append(el("small",0,`- ${r.name}: ${r.result}`))}}
function workPoll(){clearTimeout(wT);if(layer!=="settings"||sCat!=="tools")return;
 api("/api/work").then(j=>{drawWork(j);wT=setTimeout(workPoll,(j.active||[]).length?1500:4000)}).catch(()=>{wT=setTimeout(workPoll,6000)})}
let pData=null;
function prepCard(){const c=tCard("Videos in other formats (ready-to-play copies)","Some movies (Dolby or DTS sound, H.265 inside an .mkv file) cannot be played by this TV screen as they are. HERO TV makes a hidden copy of each one by itself, in the background, and adds it to the channels when it is ready. Your own files are never changed or moved. A Roku plays the originals directly.");
 if(!pData){c.append(el("small",0,"Loading..."));api("/api/prepare").then(j=>{pData=j;if(layer==="settings"&&sCat==="tools")drawSettings()}).catch(()=>{});return c}
 const d=pData;
 c.append(el("small",0,d.need?`${d.ready} of ${d.need} copies ready`+(d.bytes?` - ${gb(d.bytes)} used`:"")+(d.working?` - making: ${d.working}`:"")+(d.failed?` - ${d.failed} could not be made`:""):"No video needs a copy right now."));
 if(d.convert)c.append(el("small",0,`${d.convert} more need a real conversion (10-bit or unusual picture): see "Videos that are skipped" below.`));
 const cb=el("input");cb.type="checkbox";cb.checked=d.on;const l=el("label","lb");l.append(cb," Make copies automatically (one at a time, at low priority)");l.style.display="flex";l.style.gap="1vw";
 const run=async(body,msg)=>{try{pData=await pj("/api/prepare",body);if(msg)sMsg(msg,"ok");tData=null;drawSettings()}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}};
 cb.onchange=()=>run({auto:cb.checked},"Saved.");
 const lim=el("select");for(const g of[0,50,100,200,500,1000]){const o=el("option",0,g?`Stop making new copies after ${g} GB`:"No limit on how much space copies use");o.value=g;if(g===d.cap_gb)o.selected=true;lim.append(o)}
 if(d.cap_gb&&![50,100,200,500,1000].includes(d.cap_gb)){const o=el("option",0,`Stop making new copies after ${d.cap_gb} GB`);o.value=d.cap_gb;o.selected=true;lim.append(o)}
 lim.onchange=()=>run({cap:+lim.value},"Saved. Copies that already exist are never removed because of this limit.");
 const LANGS=[["eng","English"],["spa","Spanish"],["fre","French"],["ger","German"],["jpn","Japanese"],["ita","Italian"],["por","Portuguese"],["kor","Korean"],["chi","Chinese"],["rus","Russian"],["","Off - play each video's own default sound"]];
 const lg=el("select");for(const[k,n]of LANGS){const o=el("option",0,k?"Preferred sound language: "+n:n);o.value=k;if((d.lang||"")===k)o.selected=true;lg.append(o)}
 lg.onchange=()=>run({lang:lg.value},"Saved. Videos with that language as a second sound track get a copy that plays it; your own files are not changed.");
 if(d.lang&&d.lang_need)c.append(el("small",0,`${d.lang_ready} of ${d.lang_need} videos that have a ${(LANGS.find(x=>x[0]===d.lang)||[0,d.lang])[1]} sound track as a second choice now play it`+(d.lang_ready<d.lang_need?" (copies are being made in the background)":"")+"."));
 if(d.blocked)c.append(el("small",0,"The space limit is reached, so no new copies are being made. Raise the limit to carry on - nothing is deleted."));
 const bar=el("div","sbar");bar.append(lg,lim);
 if(d.failed)bar.append(sBtn("Try the failed ones again",()=>run({op:"retry"},"Trying again in the background.")));
 if(d.ready){const b=sBtn("Delete all copies",()=>{if(!c.dataset.sure){c.dataset.sure=1;b.textContent="Press again to delete them";return}run({op:"clear"},"Copies deleted. Your own videos were not touched.")});bar.append(b)}
 c.append(l,bar);return c}
let atData=null;
function drawAttn(){const b=$("#st-attn");if(!b)return;b.textContent="";
 if(!atData){api("/api/attention").then(j=>{atData=j;drawAttn()}).catch(()=>{atData={items:[]}});return}
 const it=atData.items||[];b.className=it.length?"attn":"";if(!it.length)return;b.append(el("b",0,it.length>1?"Needs a look":"Needs a look: "));
 for(const x of it){const r=el("div","arow");r.append(el("span",0,x.text),sBtn("Open",()=>sJump(x.cat,x.card)));b.append(r)}}
let jumpCard="",jumped=false;
function sJump(cat,card){jumpCard=card||"";if(cat==="tools"&&card){const g=TGROUPS.find(g=>g[2].includes(card));if(g)tOpen[g[0]]=true;tSave()}atData=null;sGo(cat)}
/* ---- Tools: the cards are folded into a few sections so the page is short; open or close one with Enter ---- */
const TGROUPS=[["now","Right now",["New videos: how far along","Inbox","Videos not on any channel","Videos that are skipped"]],
 ["add","Add videos",["Free movies","Bring in a folder or USB drive"]],
 ["fmt","Formats and copies",["Videos in other formats (ready-to-play copies)","H.265 (HEVC) videos","iPhone-friendly copies"]],
 ["tidy","Tidy and check",["Skip intros and credits by themselves","Sound language","Missing episodes","The same video twice","Free up space","This PC"]]];
let tOpen={now:true};try{const o=JSON.parse(localStorage.getItem("herotv.toolsOpen")||"null");if(o&&typeof o==="object")tOpen=o}catch(e){}
function tSave(){try{localStorage.setItem("herotv.toolsOpen",JSON.stringify(tOpen))}catch(e){}}
function groupTools(main){const cards=[...main.children].filter(x=>x.classList.contains("tcard")),last=TGROUPS[TGROUPS.length-1];
 const by={};for(const g of TGROUPS)by[g[0]]=[];for(const c of cards){const t=c.firstChild.textContent;(by[(TGROUPS.find(g=>g[2].includes(t))||last)[0]]).push(c);c.remove()}
 for(const[k,name]of TGROUPS){const list=by[k];if(!list.length)continue;const open=!!tOpen[k];
  const h=el("button","tgroup"+(open?" open":""),name+"  ("+list.length+")");h.type="button";h.dataset.g=k;h.setAttribute("aria-expanded",open?"true":"false");
  h.onclick=()=>{tOpen[k]=!open;tSave();drawSettings();const n=$('#st-main [data-g="'+k+'"]');if(n)n.focus({preventScroll:true})};main.append(h);
  if(open){const body=el("div","tgbody");for(const c of list)body.append(c);main.append(body)}}
 if(jumpCard){const c=[...main.querySelectorAll(".tcard")].find(x=>x.firstChild.textContent===jumpCard);jumpCard="";
  if(c){c.scrollIntoView({block:"start"});const f=c.querySelector(FOCUSABLE);if(f){f.focus({preventScroll:true});jumped=true}}}}
function drawTools(main,msg){drawToolsRaw(main,msg);if(tData)groupTools(main)}
function drawToolsRaw(main,msg){main.append(el("h3",0,"Tools"));const jb=el("div");jb.id="jobbox";jb.style.display="none";main.append(jb,msg);
 if(!tData){main.append(el("div","empty","Loading..."));api("/api/tools").then(j=>{tData=j;if(layer==="settings"&&sCat==="tools")drawSettings()}).catch(()=>{});return}
 drawJob(tData.job);if(tData.job&&tData.job.state==="running")jobPoll();
 const t=tData;
 main.append(workCard());
 main.append(introsCard());
 main.append(prepCard());
 { const c=tCard("Free movies","Public-domain films and cartoons from the Internet Archive, saved into your Free Movies folder.");const box=el("div","chk"),cbs=[];
   t.free_sources.forEach((n,i)=>{const l=el("label"),cb=el("input");cb.type="checkbox";cb.checked=true;cbs.push(cb);l.append(cb,n);box.append(l)});
   const cnt=el("select");for(const n of[1,3,5,10]){const o=el("option",0,n+" from each list");o.value=n;if(n===3)o.selected=true;cnt.append(o)}
   const b=sBtn("Download",()=>runJob({name:"free",count:+cnt.value,lists:cbs.map((x,i)=>x.checked?i:-1).filter(i=>i>=0)},b),"pri");
   const row=el("div","sbar");row.append(cnt,b);c.append(box,row);main.append(c)}
 { const c=tCard("Bring in a folder or USB drive","Copies every video from it into your Inbox (your originals stay where they are) and files them onto channels.");
   const p=sInput("","text","For example  E:\\  or  D:\\Movies");p.style.width="34vw";const b=sBtn("Bring them in",()=>runJob({name:"import",path:p.value},b),"pri");
   const row=el("div","sbar");row.append(p,b);c.append(row);main.append(c)}
 { const c=tCard("Inbox",t.inbox_waiting?`${t.inbox_waiting} video(s) waiting in the Inbox. HERO TV could not tell where these belong - pick a channel for each and it is filed right away.`:"The Inbox is empty.");const b=sBtn("Sort the Inbox now",()=>runJob({name:"sort"},b));
   const row=el("div","sbar");row.append(b);c.append(row);
   for(const f of (t.inbox_files||[])){const r=el("div","ibx"),txt=el("div","ibt");txt.append(el("b",0,f.group>1?`${f.pack} (${f.group} videos)`:f.title));if(f.about)txt.append(el("small",0,f.about));
    const sel=el("select");sel.append(el("option",0,"Choose a channel..."));sel.options[0].value="";for(const ch of t.move_channels||[]){const o=el("option",0,ch.name+((f.suggest||[]).includes(ch.id)?"  (suggested)":""));o.value=ch.id;if((f.suggest||[]).includes(ch.id))o.selected=true;sel.append(o)}
    {const o=el("option",0,f.group>1?`+ New channel for these ${f.group} videos...`:"+ New channel for this...");o.value="__new";sel.append(o)}
    const nm=el("input");nm.type="text";nm.value=f.pack||f.title;nm.placeholder="Channel name";nm.autocomplete="off";nm.style.width="18vw";nm.style.display="none";nm.maxLength=40;
    sel.addEventListener("change",()=>{nm.style.display=sel.value==="__new"?"":"none";go.textContent=sel.value==="__new"?"Make the channel":"Put it here";if(sel.value==="__new")nm.focus()});
    if(f.group>1)txt.append(el("small",0,"They move together, onto the channel you pick."));
    const rl=el("label","lb"),rc=el("input");rc.type="checkbox";rc.checked=true;rl.append(rc," Remember");rl.title="Next time a video with this title (or a new episode of this show) arrives, it goes here by itself.";
    const go=sBtn("Put it here",()=>{if(!sel.value)return sMsg("Choose a channel for "+f.title+" first.","err");
     if(sel.value==="__new"){if(!nm.value.trim())return sMsg("Give the new channel a name.","err");return runJob({name:"newchan",file:f.file,channel_name:nm.value.trim(),remember:rc.checked},go)}
     runJob({name:"place",file:f.file,channels:[sel.value],remember:rc.checked},go)},"pri");
    const ctl=el("div","sbar");ctl.append(sel,nm,rl,go);r.append(txt,ctl);c.append(r)}
   {const listed=(t.inbox_files||[]).reduce((a,f)=>a+(f.group||1),0);if(listed&&t.inbox_waiting>listed)c.append(el("small",0,`...and ${t.inbox_waiting-listed} more - they appear here as these are filed.`))}
   const first=main.querySelector(".tcard");if((t.inbox_files||[]).length&&first)main.insertBefore(c,first);else main.append(c)}
 { const u=t.unsorted||[];if(u.length){const c=tCard("Videos not on any channel",`${u.length}${u.length>=200?"+":""} video(s) are in your library but no channel shows them - usually because they are loose in the media folder or in a folder no channel uses. Sort them puts them through the Inbox: each is filed by its title, and any HERO TV cannot place shows up in the Inbox list above with a channel picker.`);
   const byF={};for(const v of u)byF[v.folder]=(byF[v.folder]||0)+1;
   c.append(el("small",0,Object.entries(byF).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([f,n])=>`${f}: ${n}`).join("   ")));
   const b=sBtn("Sort them",()=>runJob({name:"unsorted"},b),"pri");const row=el("div","sbar");row.append(b);c.append(row);
   main.append(c)}}
 { const c=tCard("Videos that are skipped",t.skipped.length?"These cannot play in the TV yet. Fixing makes a copy that plays (keeps the original); a picture problem can take 15-40 minutes for a movie.":"Every video can play.");
   if(t.skipped.length>1){const b=sBtn(`Fix all ${t.skipped.length}`,()=>runJob({name:"fixall"},b),"pri");const row=el("div","sbar");row.append(b,el("small",0,"Sound-only fixes go first and take seconds each; ones that need the picture converted take longer."));c.append(row)}
   for(const v of t.skipped.slice(0,12)){const row=el("div","sbar"),b=sBtn("Fix",()=>runJob({name:"fix",media_id:v.id},b));row.append(b,el("span",0,v.title+" - "+v.why));c.append(row)}
   if(t.skipped.length>12)c.append(el("small",0,`...and ${t.skipped.length-12} more. Fix these first, then come back.`));main.append(c)}
 main.append(capsCard(t));
 { const c=tCard("Sound language","For a video with more than one language: choose which one it plays.");const q=sInput("","text","Type part of the title");q.style.width="30vw";const res=el("div","pickl");
   let qt;q.addEventListener("input",()=>{clearTimeout(qt);qt=setTimeout(async()=>{res.textContent="";if(q.value.trim().length<2)return;
    const j=await api("/api/library?view=all&q="+encodeURIComponent(q.value.trim()));for(const it of j.items.slice(0,6)){const b=sBtn(label(it),async()=>{res.textContent="";res.append(el("small",0,"Reading its sound tracks..."));
     const a=await api("/api/audio/"+it.id);res.textContent="";if(a.tracks.length<2){res.append(el("small",0,"This video has only one sound track - nothing to choose."));return}
     for(const tr of a.tracks){const tb=sBtn((tr.language||tr.lang||"Unknown")+(tr.title?" - "+tr.title:"")+(tr.n===a.playing?"  (plays now)":""),()=>runJob({name:"audio",media_id:it.id,track:tr.n},tb));if(tr.n===a.playing)tb.disabled=true;res.append(tb)}});res.append(b)}},350)});
   c.append(q,res);main.append(c)}
 { const c=tCard("Missing episodes",t.shows?`Checks each of your ${t.shows} show(s) against TMDB's episode lists and tells you which aired episodes you do not have. A show's Details screen shows this too.`:"No shows in your library yet.");
   if(t.shows){const b=sBtn("Check my shows",()=>runJob({name:"missing"},b),"pri");const row=el("div","sbar");row.append(b);c.append(row)}main.append(c)}
 { const d=t.duplicates||[],c=tCard("The same video twice",d.length?`${d.length} film(s) or episode(s) are here more than once - ${gb(d.reduce((a,g)=>a+g.extra,0))} of extra copies. The best copy is marked keep; Set aside moves another one into the hidden .originals folder (Free space deletes it for good).`:"No video is in your library twice.");
   for(const g of d.slice(0,8)){const r=el("div","ibx");r.append(el("b",0,g.name));
    for(const cp of g.copies){const row=el("div","sbar"),txt=el("small",0,`${cp.folder} / ${cp.file}  -  ${gb(cp.size)}${cp.plays?"":"  -  does not play here"}`);
     if(cp.keep){row.append(el("span","keep","Keep"),txt)}else{const b=sBtn("Set aside",()=>runJob({name:"aside",media_id:cp.id},b));row.append(b,txt)}r.append(row)}c.append(r)}
   if(d.length>8)c.append(el("small",0,`...and ${d.length-8} more. Set these aside first, then come back.`));main.append(c)}
 { const c=tCard("iPhone-friendly copies",t.not_phone?`${t.not_phone} video(s) cannot play on an iPhone as they are (usually .mkv files). This makes .mp4 copies that play on phones, the PC and over AirPlay - normally quick, because the picture is copied, not re-encoded. Originals are kept, and so are resume points and favorites.`:"Every video can play on an iPhone.");
   if(t.not_phone){const b=sBtn("Make iPhone-friendly copies",()=>runJob({name:"phone"},b),"pri");const row=el("div","sbar");row.append(b);c.append(row)}main.append(c)}
 { const c=tCard("Free up space",t.originals_bytes?`Original copies kept after fixing or shrinking videos use ${gb(t.originals_bytes)}. Delete them once you are happy with the new versions. This is permanent.`:"No original copies are being kept.");
   if(t.originals_bytes){const b=sBtn("Delete the originals",()=>{if(!c.dataset.sure){c.dataset.sure=1;sMsg(`Press again to permanently delete ${gb(t.originals_bytes)} of original copies.`,"err");return}delete c.dataset.sure;runJob({name:"clean"},b)},"warn");const row=el("div","sbar");row.append(b);c.append(row)}main.append(c)}
 { const c=tCard("This PC",t.ffmpeg?"Video tools (ffmpeg) are installed.":"Video tools (ffmpeg) are missing: needed to read, fix and convert videos.");const row=el("div","sbar");
   if(!t.ffmpeg){const b=sBtn("Install video tools",()=>runJob({name:"ffmpeg"},b),"pri");row.append(b)}
   const b2=sBtn("Check setup",()=>runJob({name:"check"},b2));row.append(b2);
   if(t.windows){const b3=sBtn("Make a desktop shortcut",()=>runJob({name:"shortcut"},b3));row.append(b3)}c.append(row);main.append(c)}}
/* ---- H.265 / Dolby sound: test once what this PC's TV window can really show, so those videos are not skipped ---- */
function capClip(name){return new Promise(res=>{const t=document.createElement("video");t.muted=true;t.playsInline=true;t.preload="auto";
 t.style.cssText="position:fixed;left:-9999px;width:16px;height:16px;opacity:0";let done=false;
 const fin=ok=>{if(done)return;done=true;clearTimeout(tm);try{t.pause();t.removeAttribute("src");t.load()}catch(e){}t.remove();res(ok)};
 const tm=setTimeout(()=>fin(false),6000);t.onerror=()=>fin(false);
 const seen=()=>fin(t.videoWidth>0);if(t.requestVideoFrameCallback)t.requestVideoFrameCallback(seen);else t.addEventListener("timeupdate",()=>{if(t.currentTime>0.2)seen()});
 document.body.append(t);t.src="/api/captest/"+name;t.play().catch(()=>{})})}
function capType(ty){try{return !!(window.MediaSource&&MediaSource.isTypeSupported(ty))}catch(e){return false}}
async function capTest(force){if(REMOTE)return null;let cur={};try{cur=await api("/api/caps")}catch(e){return null}
 if(!force&&cur.checked&&Date.now()/1000-cur.checked<7*86400)return cur;
 const r={hevc:await capClip("hevc8.mp4")};r.hevc10=r.hevc?await capClip("hevc10.mp4"):false;r.hevc_mkv=r.hevc?await capClip("hevc8.mkv"):false;
 r.ac3=capType('audio/mp4; codecs="ac-3"');r.eac3=capType('audio/mp4; codecs="ec-3"');
 try{const j=await api("/api/caps",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(r)});
  if(!cur.checked&&j.hevc&&j.hevc_videos)toast(`Good news: this PC can show H.265 videos, so ${j.hevc_videos} of them are being added back to your channels.`);return j}catch(e){return null}}
function capsCard(t){const k=t.caps||{},n=t.hevc_videos||0,c=tCard("H.265 (HEVC) videos",
  !k.checked?"Not tested yet - HERO TV checks once whether this PC can show H.265 videos.":
  (k.hevc?"This PC can show H.265 videos"+(k.hevc10?" (10-bit ones too)":" (but not 10-bit ones - Fix converts those)")+(k.hevc_mkv?"":"; .mkv ones are repackaged by Fix in seconds")+".":
   "This PC cannot show H.265 videos yet"+(n?` (you have ${n})`:"")+". Install Microsoft's \"HEVC Video Extensions\" from the Microsoft Store (or \"HEVC Video Extensions from Device Manufacturer\", which is free on many PCs), restart HERO TV, then press Test again. Or press Fix on each one.")+
  " Dolby (AC-3) sound is always converted to AAC on the way in - quick, only the sound.");
 const row=el("div","sbar"),lb=k.checked?"Test again":"Test now",b=sBtn(lb,async()=>{b.disabled=true;b.textContent="Testing...";const j=await capTest(true);b.disabled=false;b.textContent="Test again";
  if(j){sMsg(j.hevc?"H.265 works on this PC. Videos are being checked again - give it a minute.":"H.265 still does not play here.",j.hevc?"ok":"err");tData=null;drawSettings()}});
 row.append(b);if(t.encoder)row.append(el("small",0,"Fix converts with the "+t.encoder+"."));c.append(row);return c}
/* ---- always on: start with Windows, keep running without the TV window (Roku app and phones need it) ---- */
let aData=null;
function alwaysCard(){const c=tCard("Always on","So your Roku TV and phones always find HERO TV: it can start by itself when you sign in to Windows and keep running quietly when the TV window is closed. Clicking the HERO TV icon still opens the TV.");
 if(!aData){c.append(el("small",0,"Loading..."));api("/api/alwayson").then(j=>{aData=j;if(layer==="settings"&&sCat==="devices")drawSettings()}).catch(()=>{});return c}
 const mk=(key,text,on,dis)=>{const i=el("input");i.type="checkbox";i.checked=on;i.disabled=!!dis;const l=el("label","lb");l.append(i," "+text);l.style.display="flex";l.style.gap="1vw";
  i.onchange=async()=>{i.disabled=true;try{aData=await pj("/api/alwayson",{[key]:i.checked});toast("Saved.")}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err");i.checked=!i.checked}i.disabled=false;drawSettings()};return l};
 if(aData.windows)c.append(mk("startup","Start HERO TV when I sign in to Windows (in the background, no window)",aData.startup));
 c.append(mk("background","Keep HERO TV running when the TV window is closed",aData.background,aData.startup));
 c.append(mk("stay_awake","Keep this PC awake so the TVs always find it (the screen can still switch off)",aData.stay_awake));
 c.append(el("small",0,aData.startup?"Starting with Windows also keeps it running. To stop it: Settings > Backup and about > Quit HERO TV.":"If it ever stops with an error while running in the background, it starts itself again."));
 return c}
/* ---- live TV in other apps: M3U + XMLTV guide + HDHomeRun look-alike (own warned switch, off by default) ---- */
let iData=null;
function iptvCard(){const c=tCard("Live TV in other apps","Your channels as live TV in Plex, Jellyfin, Emby, Channels and IPTV apps (TiviMate, IPTV Smarters, VLC...) on Fire TV, Apple TV, Android TV, phones and smart TVs - with the TV guide. Each channel is one live stream that follows your schedule.");
 if(!iData){c.append(el("small",0,"Loading..."));api("/api/iptv").then(j=>{iData=j;if(layer==="settings"&&sCat==="devices")drawSettings()}).catch(()=>{});return c}
 const d=iData,err=t=>sMsg(String(t.message||t).replace(/^Error: /,""),"err");
 if(!d.ffmpeg)c.append(el("small","err","This needs ffmpeg (Settings > Tools shows how to get it)."));
 if(!d.on){c.append(el("small","err","Warning: when this is on, any app or device on your home network that knows the address can watch your channels (watch-only - nothing can be changed). There is no pairing, like the TV media server. Only switch it on at home, on a network you trust."));
  const b=sBtn("Switch on live TV for other apps",async()=>{if(!b.dataset.sure){b.dataset.sure=1;b.textContent="Press again to switch it on";return}
   try{iData=await pj("/api/iptv",{on:true});sMsg("Live TV for other apps is on.","ok");drawSettings()}catch(e){err(e)}},"warn");
  if(!d.lan)c.append(el("small",0,"Switch on 'Let other devices watch' above first."));c.append(b);return c}
 const row=(label,val)=>{const r=el("div","ibx");r.append(el("b",0,label));const t=el("code",0,val||"(this PC has no network address right now)");t.style.userSelect="all";r.append(t);return r};
 c.append(row("Channel list (M3U) for IPTV apps",d.m3u),row("TV guide (XMLTV)",d.xmltv),row("Tuner address for Plex / Jellyfin / Emby (HDHomeRun)",d.hdhr));
 c.append(el("small",0,"Short addresses, easy to type with a remote. If an app wants a private address instead: "+(d.m3u_long||"")+" and "+(d.xmltv_long||"")));
 const ol=el("ol","rsteps");for(const t of["Plex: Settings > Live TV & DVR > Set up Plex DVR > 'Don't see your HDHomeRun device? Enter its network address manually' > type the tuner address. For the guide choose 'Have an XMLTV guide on your server?' and paste the guide address.","Jellyfin / Emby: Dashboard > Live TV > add a Tuner (HDHomeRun, the tuner address) and a TV guide provider (XMLTV, the guide address).","IPTV apps (TiviMate, IPTV Smarters, VLC...): add a playlist by URL with the channel list address; most find the guide by themselves (else paste the guide address)."])ol.append(el("li",0,t));c.append(ol);
 const bar=el("div","sbar");
 bar.append(sBtn("New addresses (old ones stop working)",async()=>{try{iData=await pj("/api/iptv",{on:true,new_key:true});sMsg("New addresses made - put them into your apps again.","ok");drawSettings()}catch(e){err(e)}}),
  sBtn("Switch off",async()=>{try{iData=await pj("/api/iptv",{on:false});sMsg("Live TV for other apps is off.","ok");drawSettings()}catch(e){err(e)}},"warn"));
 c.append(bar,el("small",0,"Works while this PC is on with HERO TV running. Videos are sent as they are when the format allows and converted on the fly otherwise (that uses more of the PC)."));return c}
/* ---- the HERO TV app on a Roku TV: found and installed from here, nothing to type on the TV ---- */
let rData=null,rFound=null,rPick="";
function rokuCard(){const c=tCard("HERO TV on your Roku TVs","Puts a real HERO TV app on each Roku TV in the house: open it with the Roku remote and flip through your channels like cable - Up/Down changes channel, OK opens the TV guide, Left opens everything on demand. Every TV can watch its own channel. This PC does the work, so it must be on with HERO TV open.");
 if(!rData){c.append(el("small",0,"Loading..."));api("/api/roku").then(j=>{rData=j;if(layer==="settings"&&sCat==="devices")drawSettings()}).catch(()=>{});return c}
 const r=rData,err=t=>sMsg(String(t.message||t).replace(/^Error: /,""),"err");
 if(!r.app_files){c.append(el("small","err","The Roku app files are missing from this HERO TV folder. Reinstall HERO TV."));return c}
 for(const tv of r.tvs){const row=el("div","ibx"),t=el("div","ibt");t.append(el("b",0,`${tv.name} (${tv.ip})`),el("small",0,`HERO TV app ${tv.installed||"?"}`+(tv.needs_update?` - will be updated by itself (${tv.needs_update}) the next time the TV is on, or press Update now.`:" - kept up to date by itself.")));
  const bar=el("div","sbar"),up=sBtn("Update now",async()=>{up.disabled=true;sMsg(`Sending the app to ${tv.name}...`);try{const j=await pj("/api/roku",{op:"install",ip:tv.ip,name:tv.name});rData=j;dData=null;sMsg(`Done - ${tv.name}: ${j.done.result}.`,"ok");drawSettings()}catch(e){err(e);up.disabled=false}});
  const rm=sBtn("Remove",async()=>{if(!row.dataset.sure){row.dataset.sure=1;rm.textContent="Press again to remove";return}try{rData=await pj("/api/roku",{op:"forget",ip:tv.ip});dData=null;sMsg(`Removed ${tv.name}. The app stays on that TV but can no longer watch until you install it again.`,"ok");drawSettings()}catch(e){err(e)}},"warn");
  bar.append(up,rm);row.append(t,bar);c.append(row)}
 const add=el("div","ibx");add.append(el("b",0,r.tvs.length?"Add another Roku TV":"Set up a Roku TV"));
 const ol=el("ol","rsteps");for(const t of["On that TV's remote press: Home 3 times, Up 2 times, then Right, Left, Right, Left, Right.","On the screen that opens, choose Enable installer and restart, agree, and pick a password (write it down). The TV restarts.","Back here: press Find my Roku TVs, choose the TV, type that password and press Install on the TV."])ol.append(el("li",0,t));add.append(ol);
 const row=el("div","sbar");
 const find=sBtn("Find my Roku TVs",async()=>{find.disabled=true;sMsg("Looking for Roku TVs on your network...");try{const j=await pj("/api/roku",{op:"find"});rData=j;rFound=j.found;const fresh=rFound.filter(x=>!r.tvs.some(t=>t.ip===x.ip));if(fresh.length===1)rPick=fresh[0].ip;sMsg(rFound.length?"":"No Roku TV answered. Is it on? You can also type its address (TV: Settings > Network > About).",rFound.length?"ok":"err");drawSettings()}catch(e){err(e);find.disabled=false}},r.tvs.length?"":"pri");row.append(find);add.append(row);
 if(rFound&&rFound.length){const box=el("div","picks");for(const t of rFound){const set=r.tvs.some(x=>x.ip===t.ip);const b=sBtn(`${t.name}${t.model?" - "+t.model:""} (${t.ip})${set?" - already set up":t.dev===false?" - developer mode is OFF":""}`,()=>{rPick=t.ip;drawSettings()});b.classList.toggle("on",rPick===t.ip);box.append(b)}add.append(box)}
 const ip=el("input");ip.type="text";ip.placeholder="TV address, e.g. 192.168.12.40";ip.value=rPick||"";ip.autocomplete="off";ip.style.width="18vw";
 const pw=el("input");pw.type="password";pw.placeholder="developer password from that TV";pw.autocomplete="off";pw.style.width="18vw";
 const form=el("div","sbar");form.append(ip,pw);
 const go=sBtn("Install on the TV",async()=>{go.disabled=true;sMsg("Building the app and sending it to the TV (about 10 seconds)...");
  try{const a=ip.value.trim(),j=await pj("/api/roku",{op:"install",ip:a,password:pw.value,name:(rFound||[]).find(x=>x.ip===a)?.name||""});
   rData=j;dData=null;rPick="";sMsg(`Done - the HERO TV app is ${j.done.result} on the TV`+(j.done.started?" and starting now.":". Open it from the TV's home screen (it is called HERO TV)."),"ok");drawSettings()}
  catch(e){err(e);go.disabled=false}},"pri");form.append(go);add.append(form);c.append(add);
 c.append(el("small",0,"Each TV's password is remembered on this PC so HERO TV can update its app by itself. Each TV gets its own watch-only key (listed under Paired devices)."));
 return c}
/* ---- Other devices: watch on a phone/laptop on the home WiFi (paired, watch-only) ---- */
let dData=null,devT=null;
async function devOp(body,btn){if(btn)btn.disabled=true;sMsg("");try{dData=await pj("/api/devices",body);drawSettings()}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}if(btn)btn.disabled=false}
function devPoll(){clearTimeout(devT);if(layer!=="settings"||sCat!=="devices")return;
 api("/api/devices").then(j=>{const before=dData;dData=j;const paired=before&&before.pairing&&!j.pairing&&j.devices.length>before.devices.length;
  if(paired)toast("Paired: "+j.devices[j.devices.length-1].name);if(paired||!before||!!before.pairing!==!!j.pairing||before.devices.length!==j.devices.length)drawSettings();
  else{const c=$("#pair-left");if(c&&j.pairing)c.textContent=Math.ceil(j.pairing.seconds_left/60)+" min left"}
  if(j.pairing)devT=setTimeout(devPoll,2000)}).catch(()=>{})}
function drawDevices(main,msg){main.append(el("h3",0,"Other devices"));
 if(!dData){main.append(el("div","empty","Loading..."));api("/api/devices").then(j=>{dData=j;if(layer==="settings"&&sCat==="devices")drawSettings()}).catch(()=>{});return}
 const d=dData;
 { const c=tCard("Watch on your phone or another computer","Lets devices on your home WiFi watch HERO TV after you pair them once. Paired devices can watch, browse and resume, but cannot change settings, channels or files. Off until you switch it on.");
   const on=el("input");on.type="checkbox";on.checked=d.enabled;const l=el("label","lb");l.append(on," Let other devices on my home WiFi watch");l.style.display="flex";l.style.gap="1vw";
   on.onchange=()=>devOp({op:on.checked?"enable":"disable"});c.append(l);
   if(d.enabled)c.append(el("small",0,"The first time, Windows may ask whether HERO TV may use the network: choose Allow (private networks only)."));
   main.append(c)}
 main.append(alwaysCard());
 main.append(rokuCard());
 main.append(iptvCard());
 if(d.enabled){
  { const c=tCard("Phone can't connect?","Checks this PC for the usual reasons (Windows Firewall, a network marked Public, a VPN) and fixes what it can. Ethernet on the PC and WiFi on the phone is fine - they only need the same router.");
    const ck=d.check,row=el("div","sbar"),b=sBtn("Check the connection",()=>devOp({op:"check"},b),ck?"":"pri");row.append(b);
    if(ck){if(!ck.problems.length)c.append(el("b",0,ck.windows?"Everything looks right on this PC.":"Nothing wrong found (the firewall check only works on Windows)."),
       el("small",0,"Still no luck? Then it is usually the network, not this PC: the phone and the PC must be on the same router. On the iPhone, Settings > Wi-Fi > (i) shows its IP address - its first three numbers must match the address above"+(d.addresses[0]?` (${d.addresses[0].replace(/^https?:\/\//,"").split(".").slice(0,3).join(".")}.x)`:"")+". If they differ, the PC is behind a second router: plug the PC into the main router, put the phone on the second router's WiFi, or set the second router to Access Point / Bridge mode. Guest WiFi and 'AP / client isolation' also block it."));
     for(const p of ck.problems){const x=el("div","ibx");x.append(el("b",0,p.title),el("small",0,p.text));c.append(x)}
     if(ck.problems.some(p=>p.fixable)){const f=sBtn("Fix it",async()=>{f.disabled=true;try{dData=await pj("/api/devices",{op:"fix-network"});sMsg("Windows will ask for permission - choose Yes. Checking again in a few seconds...","ok");
       setTimeout(()=>devOp({op:"check"}),7000)}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err");f.disabled=false}},"pri");row.prepend(f)}}
    c.append(row);main.append(c)}
  { const c=tCard("On the phone, open this address",d.addresses.length?"Type it into Safari or Chrome while the phone is on the same WiFi as this PC."+(d.addresses.length>1?" If the first one does not open, try the others.":""):"This PC does not seem to be on a home network right now.");
    for(const a of d.addresses){const b=el("b",0,a);b.style.fontSize="calc(3vh*var(--tx))";b.style.userSelect="all";c.append(b)}
    if(d.qr){const q=el("div");q.id="phone-qr";q.innerHTML=d.qr;q.style.cssText="display:inline-block;align-self:flex-start;line-height:0;background:#fff;padding:8px;border-radius:8px";   /* whole pixels per square: sharp for cameras */c.append(el("small",0,"Or open the iPhone's Camera and point it at this code, then tap the link that appears:"),q)}
    main.append(c)}
  { const c=tCard("Pair a device",d.pairing?"Type this code on the phone. It works once, for 10 minutes.":"Each phone or computer needs pairing once.");
    if(d.pairing){const code=el("b",0,d.pairing.code.replace(/(\d{3})(\d{3})/,"$1 $2"));code.style.cssText="font-size:calc(6vh*var(--tx));letter-spacing:.2em;color:var(--accent)";
     const left=el("small",0,Math.ceil(d.pairing.seconds_left/60)+" min left");left.id="pair-left";c.append(code,left);const row=el("div","sbar");row.append(sBtn("Cancel",()=>devOp({op:"cancel"})));c.append(row);devPoll()}
    else{const row=el("div","sbar"),b=sBtn("Pair a device",()=>devOp({op:"pair"},b),"pri");row.append(b);c.append(row)}main.append(c)}
  { const c=tCard("Paired devices",d.devices.length?"":"None yet.");
    for(const x of d.devices){const row=el("div","sbar"),seen=x.last_seen?new Date(x.last_seen*1e3).toLocaleString():"never";row.append(el("span",0,`${x.name} - last used ${seen}`));
     const b=sBtn("Remove",()=>{if(!row.dataset.sure){row.dataset.sure=1;b.textContent="Press again to remove";return}devOp({op:"remove",id:x.id},b)},"warn");row.append(b);c.append(row)}
    if(d.devices.length>1){const row=el("div","sbar"),b=sBtn("Remove all",()=>{if(!c.dataset.sure){c.dataset.sure=1;b.textContent="Press again to remove every device";return}devOp({op:"remove-all"},b)},"warn");row.append(b);c.append(row)}
    main.append(c)}
  main.append(tCard("Watching on the TV","On the iPhone, start a video, tap the AirPlay icon and pick your TV (on a Roku TV, AirPlay must be on: Settings > Apple AirPlay and HomeKit). Or mirror this PC: press Windows key + K and pick the TV."))}
 { const x=d.dlna||{},c=tCard("Browse your library on the TV itself","For TVs with a media player app (Roku Media Player, VLC, the 'Media' app of many smart TVs): your folders, shows and new arrivals appear there, and play straight on the TV. Watch-only: nothing can be changed through it.");
   const w=el("small",0,"Important: this standard has no pairing. While it is on, ANY device on your WiFi can see and play your videos. Leave it off on shared or public networks.");w.style.color="var(--accent)";c.append(w);
   const row=el("div","sbar");
   if(x.enabled){row.append(el("b",0,"On"));const off=sBtn("Turn off",()=>devOp({op:"dlna-off"},off));off.id="dlna-btn";row.append(off)}
   else{const go=sBtn("Turn on TV media player browsing",()=>{if(!c.dataset.sure){c.dataset.sure=1;go.textContent="Press again to confirm: anyone on my WiFi may watch";sMsg("Press again to confirm. Every device on your WiFi will be able to watch your videos.","err");return}delete c.dataset.sure;devOp({op:"dlna-on"},go)},"pri");go.id="dlna-btn";row.append(go)}
   c.append(row);
   if(x.enabled)c.append(el("small",0,`On the Roku: open the Roku Media Player channel (free in the Roku Channel Store) and choose "${x.name}". If Windows asks about network access, choose Allow for private networks.`+(x.running?"":" (Not running right now - see the message above.)")));
   main.append(c)}
 main.append(msg)}
function chBack(){chSel=null;sDirty=false;sLeave=false;drawSettings();$("#st-main").scrollTop=0}
async function chSaved(r,text){chList=r.channels;sDirty=false;sLeave=false;try{libV=(await fetch("/api/hb").then(x=>x.json())).lib}catch(e){}libChanged("channels updated");sMsg(text+(r.note?" "+r.note:""),"ok")}
async function chPost(body,okText,backToList){sMsg("Saving...");try{const r=await pj("/api/channels-config",body);await chSaved(r,okText);if(backToList){chSel=null;drawSettings();sMsg(okText+(r.note?" "+r.note:""),"ok")}}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}}
function drawChannelsCfg(main,msg){main.append(el("h3",0,"Channels"));
 if(!chList){main.append(el("div","empty","Loading channels..."));api("/api/channels-config").then(j=>{chList=j.channels;chShorts=j.shorts||0;chChoices=j.slot_choices||chChoices;if(layer==="settings"&&sCat==="chan")drawSettings()}).catch(()=>{main.textContent="";main.append(el("div","empty","Channels could not be loaded."))});return}
 if(chSel===null){main.append(el("small",0,"Click a channel to rename it, change its color, folder or keywords. Changes show up in the guide straight away."));
  { const sm=el("input");sm.type="checkbox";sm.checked=sData&&sData.smart_sort!==false;
    sm.onchange=async()=>{try{await pj("/api/settings",{smart_sort:sm.checked});sData=await api("/api/settings");chList=null;drawSettings();toast(sm.checked?"Smart sorting on":"Smart sorting off")}catch(e){sMsg(String(e.message||e),"err")}};
    const l=el("label","lb");l.append(sm," Smart sorting");l.style.display="flex";l.style.gap="1vw";
    const hasKey=sData&&sData.art&&sData.art.has_key;
    main.append(sField("",hasKey?"New videos are filed by what they really are - studio, genre and film series from TMDB - so a non-Marvel film with a Marvel-sounding name stays out of the Marvel channels. Keywords are used when a title is unknown.":"Needs a free TMDB key (Settings > Cover art). Until then new videos are filed by the keywords in their names.",l))}
  { const sc=el("input");sc.type="checkbox";sc.checked=sData&&sData.seasonal!==false;
    sc.onchange=async()=>{try{await pj("/api/settings",{seasonal:sc.checked});sData=await api("/api/settings");toast(sc.checked?"Seasonal specials on":"Seasonal specials off")}catch(e){sMsg(String(e.message||e),"err")}};
    const l=el("label","lb");l.append(sc," Seasonal specials");l.style.display="flex";l.style.gap="1vw";
    const list=(sData&&sData.seasonal_list||[]).map(x=>`${x.name} (${x.dates.replace("..", " to ")}, ${x.from}-${x.to})`).join("; ");
    main.append(sField("",(list?list+". ":"")+"Extra programming on Hero Marathon at certain times of year. If you have nothing that fits, the channel plays as usual.",l))}
  { const dp=el("input");dp.type="checkbox";dp.checked=sData&&sData.dayparts!==false;
    dp.onchange=async()=>{try{await pj("/api/settings",{dayparts:dp.checked});sData=await api("/api/settings");toast(dp.checked?"Time-of-day programming on":"Time-of-day programming off")}catch(e){sMsg(String(e.message||e),"err")}};
    const l=el("label","lb");l.append(dp," Time-of-day programming");l.style.display="flex";l.style.gap="1vw";
    const list=(sData&&sData.dayparts_list||[]).map(x=>`${x.name} (${x.days}, ${x.from}-${x.to})`).join("; ");
    main.append(sField("",(list?list+". ":"")+"Hero Marathon follows the clock like real TV. If you have nothing that fits a time slot, it plays as usual.",l))}
  {const bar=el("div","sbar");bar.append(sBtn("Choose your channels...",()=>openLineup(false)));main.append(sField("","Switch whole channels on or off - nothing is deleted, and you can switch them back any time.",bar))}
  for(const c of chList){const b=el("button","chrow"+(c.off?" off":""));b.type="button";const dot=el("i");dot.style.background=c.color;b.append(dot,el("b",0,String(c.number)),el("span",0,c.name+(c.off?"  (off)":"")),el("small",0,c.summary));b.onclick=()=>{chSel=c.id;drawSettings();$("#st-main").scrollTop=0};main.append(b)}
  const bar=el("div","sbar");bar.append(sBtn("Add a channel",()=>{chSel="new";drawSettings()},"pri"));main.append(bar,msg);return}
 const isNew=chSel==="new",c=isNew?{id:"",number:"",name:"",color:"#ffcf1f",mode:"sequential",description:"",kind:"tv",folder:"",keywords:[],shared_keywords:0,special:false,summary:""}:chList.find(x=>x.id===chSel);
 if(!c){chSel=null;return drawChannelsCfg(main,msg)}
 main.firstChild.textContent=isNew?"New channel":"Edit channel: "+c.name;
 const name=sInput(c.name),num=sInput(c.number,"text",isNew?"automatic":"");num.size=6;let col=c.color;
 const sw=el("div","sw"),hex=sInput(col,"text","#ffcf1f");hex.size=9;
 const pick=x=>{col=x;sDirty=true;sLeave=false;[...sw.children].forEach(b=>b.classList.toggle("on",b.dataset.c.toLowerCase()===x.toLowerCase()));hex.value=x};
 hex.addEventListener("input",()=>{if(/^#[0-9a-fA-F]{6}$/.test(hex.value))pick(hex.value)});
 for(const x of SW){const b=el("button",x.toLowerCase()===col.toLowerCase()?"on":"");b.type="button";b.dataset.c=x;b.style.background=x;b.title=x;b.setAttribute("aria-label","Color "+x);b.onclick=()=>pick(x);sw.append(b)}
 main.append(sField("Channel name","Shown in the guide and when you change channel.",name),sField("Channel number","The number you type to tune it. Each channel needs its own.",num),sField("Color",null,sw),sField("",null,hex,true));
 let mode=null;if(c.kind!=="weather"){mode=el("select");for(const[v,t]of[["sequential","In order (episodes and movies one after another)"],["mixed","Mixed shows, each in order (shows take turns, episodes stay in order)"],["balanced","Mixed shows, fair share (like Mixed, and a big show no longer crowds out small ones)"],["shuffle","Shuffled (everything in a random order)"]]){const o=el("option",0,t);o.value=v;if(v===c.mode)o.selected=true;mode.append(o)}mode.onchange=()=>{sDirty=true;sLeave=false};main.append(sField("Play order",null,mode))}
 let starts=null,brk=null;if(c.kind!=="weather"){starts=el("select");for(const[v,t]of[[0,"Any time (one show straight after the other)"],[15,"On the quarter hour (:00, :15, :30, :45)"],[30,"On the half hour (:00 and :30)"],[60,"On the hour"]]){const o=el("option",0,t);o.value=v;if(v===(c.starts||0))o.selected=true;starts.append(o)}starts.onchange=()=>{sDirty=true;sLeave=false};
  main.append(sField("Start times",`Like real TV: shows start at clean times, and the gap before them is filled with whole short cartoons from your Shorts folder (put them in a folder called Shorts in your media folder - Tools > Free movies > Superhero-era cartoons gets some free ones) and an "Up next" card for the last minute or two. You have ${chShorts} short${chShorts===1?"":"s"} right now`+(chShorts<10?" - with few or none, the gaps are mostly the Up next card, so quarter hours work best.":"."),starts));
  brk=el("input");brk.type="checkbox";brk.checked=!!c.breaks;brk.onchange=()=>{sDirty=true;sLeave=false};const bl=el("label","lb");bl.append(brk," Breaks inside shows");bl.style.display="flex";bl.style.gap="1vw";
  main.append(sField("","With clean start times on: part of the time before the next show becomes a break of shorts in the middle of each show (two in shows of 50 minutes or more), at a chapter mark of the video when there is one nearby. The guide still lists the show as one.",bl))}
 if(!isNew&&c.kind!=="weather"&&c.kind!=="foryou")main.append(slotsField(c));
 let folder=null,words=null,desc=null;
 if(c.kind!=="weather"){
  if(!isNew)main.append(sField(c.off?"This channel is off":"On or off",c.off?"It is hidden from the guide and nothing new is filed onto it. Your videos are untouched.":"Switching it off hides it from the guide and stops new videos being filed onto it. Nothing is deleted.",
   sBtn(c.off?"Switch it back on":"Switch this channel off",()=>chPost({op:"switch",id:c.id,off:!c.off},c.off?"Switched back on.":"Switched off.",true))));
  if(isNew||c.folder){folder=sInput(isNew?"":c.folder,"text",isNew?"same as the name":"");folder.style.width="30vw";main.append(sField("Folder","Videos in this folder (inside your media folder) play on this channel."+(isNew?" It is created for you.":" Renaming it does not move videos already in the old folder."),folder))}
  else main.append(sField("What it shows",c.summary+" - these special rules are kept as they are. They can be changed in config\\channels.json.",null));
  words=el("textarea");words.value=c.keywords.join("\n");words.placeholder="one per line, for example:\niron man\navengers";words.addEventListener("input",()=>{sDirty=true;sLeave=false});
  if(c.smart&&c.smart.length)main.append(sField("Smart sorting",`With a TMDB key, this channel automatically gets: ${c.smart.join("; ")}. The keywords below are then only used for titles TMDB does not know.`,null));
  main.append(sField("Keywords","When new videos arrive in the Inbox (or you press Sort the Inbox now in Tools), a file whose name contains one of these words goes on this channel. One per line."+(c.shared_keywords?` ${c.shared_keywords} more keywords are shared with other channels and are not shown here.`:""),words))}
 desc=sInput(c.description);desc.style.width="50vw";main.append(sField("Description","One line shown in the guide.",desc));
 const bar=el("div","sbar"),payload=()=>{const b={name:name.value,color:col,description:desc.value};if(num.value.trim()!=="")b.number=num.value.trim();if(mode)b.mode=mode.value;if(starts)b.starts=Number(starts.value);if(brk)b.breaks=brk.checked;if(folder&&(isNew||folder.value.trim()))b.folder=folder.value;if(words)b.keywords=words.value;return b};
 bar.append(sBtn(isNew?"Create channel":"Save",()=>isNew?chPost(Object.assign({op:"add"},payload()),"Channel created.",true):chPost(Object.assign({op:"save",id:c.id},payload()),"Saved."),"pri"),sBtn("Back to the list",()=>{if(sDirty&&!sLeave){sLeave=true;toast("You have unsaved changes. Choose again to discard them, or press Save.");return}chBack()}));
 if(!isNew)bar.append(sBtn("Delete this channel",()=>{if(!bar.dataset.sure){bar.dataset.sure=1;sMsg("Press Delete again to remove this channel from the guide. Your videos are not touched.","err");return}chPost({op:"delete",id:c.id},"Channel deleted.",true)},"warn"));
 main.append(bar,msg)}
/* time slots: "Spider-Man cartoons on Saturday mornings" - blocks in channels.json, made here */
function slotsField(c){const box=el("div","slots"),ORD={sequential:"in order",mixed:"mixed shows, in order",balanced:"fair share",shuffle:"shuffled"};
 const post=async(body,ok)=>{sMsg("Saving...");try{const r=await pj("/api/channels-config",body);await chSaved(r,ok);drawSettings();sMsg(ok+(r.note?" "+r.note:""),"ok")}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}};
 for(const b of c.blocks||[]){const row=el("div","sbar");const t12=x=>{const[h,mm]=String(x).split(":").map(Number);return isNaN(h)?x:`${h%12||12}:${String(mm).padStart(2,"0")} ${h<12?"AM":"PM"}`};row.append(el("span",0,`${b.days} ${t12(b.from)} to ${t12(b.to)}: ${b.what}${b.mode?" ("+(ORD[b.mode]||b.mode)+")":""}${b.dates?" - only "+b.dates:""}`),
  sBtn("Remove",()=>post({op:"remove_block",id:c.id,name:b.name},"Time slot removed."),"warn"));box.append(row)}
 if(!(c.blocks||[]).length)box.append(el("small",0,"None yet."));
 const days=el("select");for(const[v,t]of[["daily","Every day"],["weekdays","Weekdays"],["weekends","Weekends"],["mon","Mondays"],["tue","Tuesdays"],["wed","Wednesdays"],["thu","Thursdays"],["fri","Fridays"],["sat","Saturdays"],["sun","Sundays"]]){const o=el("option",0,t);o.value=v;days.append(o)}
 const tm=v=>{const i=el("select");for(let q=0;q<96;q++){const h=Math.floor(q/4),mm=String(q%4*15).padStart(2,"0"),val=String(h).padStart(2,"0")+":"+mm;
   const o=el("option",0,`${h%12||12}:${mm} ${h<12?"AM":"PM"}`);o.value=val;if(val===v)o.selected=true;i.append(o)}return i},a=tm("08:00"),z=tm("11:00");
 const what=el("select");const grp=(label,list,key)=>{if(!list.length)return;const g=document.createElement("optgroup");g.label=label;for(const x of list){const o=el("option",0,x);o.value=key+"\t"+x;g.append(o)}what.append(g)};
 grp("Folders",chChoices.folders||[],"folder");grp("Shows",chChoices.series||[],"series");
 const ord=el("select");for(const[v,t]of[["shuffle","Shuffled"],["mixed","Mixed shows, each in order"],["sequential","In order"],["balanced","Mixed shows, fair share"]]){const o=el("option",0,t);o.value=v;ord.append(o)}
 const add=sBtn("Add time slot",()=>{const[k,x]=(what.value||"\t").split("\t");if(!x)return sMsg("Choose what plays in the time slot.","err");
  post({op:"add_block",id:c.id,days:days.value,from:a.value,to:z.value,mode:ord.value,what:{[k]:x}},"Time slot added.")});
 const form=el("div","sbar");form.append(days,a,el("span",0,"to"),z,what,ord,add);box.append(form);
 return sField("Time slots","Like real TV: during these hours this channel plays only what you pick - for example cartoons on Saturday mornings. Outside them it plays as usual. A slot can run past midnight (22:00 to 02:00).",box)}
function sGo(k){if(sDirty&&!sLeave){sLeave=true;toast("You have unsaved changes. Choose again to discard them, or press Save.");return}sDirty=false;sLeave=false;sCat=k;chSel=null;if(k==="chan")chList=null;if(k==="tools"){tData=null;nData=null;pData=null}if(k==="devices"){dData=null;rData=null;rFound=null;aData=null;iData=null}drawSettings();$("#st-main").scrollTop=0}
/* is box q in direction k from box r? Compared by halves, so tiles a few pixels out of line still count as one row */
function inDir(r,q,k){if(k==="ArrowDown")return q.top>=r.top+r.height*.5&&q.top+q.height/2>r.top+r.height/2;
 if(k==="ArrowUp")return q.bottom<=r.bottom-r.height*.5&&q.top+q.height/2<r.top+r.height/2;
 if(k==="ArrowRight")return q.left>=r.left+r.width*.5;return q.right<=r.right-r.width*.5}
const sameRow=(r,q)=>q.top<r.bottom-Math.min(r.height,q.height)*.5&&q.bottom>r.top+Math.min(r.height,q.height)*.5;
const overlapX=(r,q)=>q.left<r.right&&q.right>r.left;
/* ---- arrow keys move between buttons and boxes by where they are on screen (TV-remote style) ---- */
const FOCUSABLE='button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),a[href]';
function arrowOwnedByField(a,k){if(!a)return false;const t=a.tagName,typ=(a.type||"").toLowerCase();
 if(t==="TEXTAREA")return true;                                          /* moving the cursor in a text box */
 if(t==="INPUT"&&!["checkbox","radio","button","submit","color","range"].includes(typ))return k==="ArrowLeft"||k==="ArrowRight";
 if(t==="INPUT"&&typ==="range")return k==="ArrowLeft"||k==="ArrowRight";
 if(t==="SELECT")return k==="ArrowLeft"||k==="ArrowRight";            /* left/right change the choice, up/down leave it */
 return false}
function spatialMove(k,root,wrap){const a=document.activeElement;
 const all=[...root.querySelectorAll(FOCUSABLE)].filter(x=>x.getClientRects().length&&getComputedStyle(x).visibility!=="hidden");
 if(!all.length)return false;
 if(!a||a===document.body||!root.contains(a)){all[0].focus();all[0].scrollIntoView({block:"nearest"});return true}
 const r=a.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height/2;let best=null,bd=Infinity;
 for(const n of all){if(n===a)continue;const q=n.getBoundingClientRect(),qx=q.left+q.width/2,qy=q.top+q.height/2;let along,across;
  if(!inDir(r,q,k))continue;
  if(k==="ArrowDown"||k==="ArrowUp"){along=Math.abs(qy-cy);across=overlapX(r,q)?0:Math.abs(qx-cx)}
  else{if(!sameRow(r,q))continue;along=Math.abs(qx-cx);across=Math.abs(qy-cy)}                  /* left/right: only along the same row */
  if(along<=0)continue;const d=along+across*2;if(d<bd){bd=d;best=n}}
 if(!best&&wrap&&(k==="ArrowRight"||k==="ArrowLeft")){const i=all.indexOf(a);best=all[i+(k==="ArrowRight"?1:-1)]||null}   /* end of a row: on to the next one */
 if(!best)return false;best.focus({preventScroll:true});best.scrollIntoView({block:"nearest",inline:"nearest"});return true}
function settingsKey(e){const k=e.key;
 if(k==="Escape"){e.preventDefault();if(sDirty&&!sLeave){sLeave=true;return toast("You have unsaved changes. Press Esc again to leave without saving.")}if(sCat==="chan"&&chSel!==null)return chBack();return openHome()}
 if(!k.startsWith("Arrow"))return;const a=document.activeElement,inNav=!!(a&&a.closest&&a.closest("#st-nav"));
 if(inNav&&(k==="ArrowUp"||k==="ArrowDown")){e.preventDefault();const ks=SCATS.map(x=>x[0]),i=ks.indexOf(sCat),n=ks[(i+(k==="ArrowDown"?1:-1)+ks.length)%ks.length];sGo(n);const b=$("#st-nav .on");if(b)b.focus();return}
 if(inNav&&k==="ArrowRight"){e.preventDefault();const f=[...$("#st-main").querySelectorAll(FOCUSABLE)].find(x=>x.getClientRects().length);if(f){f.focus({preventScroll:true});f.scrollIntoView({block:"nearest"})}return}
 if(inNav&&k==="ArrowLeft"){e.preventDefault();return}
 if(arrowOwnedByField(a,k))return;
 e.preventDefault();if(!spatialMove(k,$("#st-main"))&&k==="ArrowLeft"){const b=$("#st-nav .on");if(b)b.focus()}}
/* ---- on-screen buttons for the mouse + right-click menus ---- */
let mbarT;function mbarInit(){const b=$("#mbar");if(b.dataset.ok)return;b.dataset.ok=1;
 for(const[t,fn]of[...(COARSE?[["Ch ▲",()=>tune(ci+1)],["Ch ▼",()=>tune(ci-1)]]:[]),["Home",()=>openHome()],["Guide",()=>openGuide()],["Library",()=>openLib()],["Details",()=>openInfo()],...(REMOTE?[]:[["Settings",()=>openSettings()]]),["Full screen",()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen().catch(()=>{})]]){const x=el("button",0,t);x.type="button";x.onclick=fn;b.append(x)}}
function mbarShow(){if(layer!==""){show("#mbar",false);return}mbarInit();paint($("#mbar"),theme.color);show("#mbar",true);clearTimeout(mbarT);mbarT=setTimeout(()=>show("#mbar",false),3000)}
let ctxI=0,ctxL=[];
function ctxOpen(x,y,list){ctxL=list;ctxI=0;const m=$("#ctx");m.textContent="";paint(m,theme.color);list.forEach((it,i)=>{const d=el("div",i===0?"sel":"",it.t);d.setAttribute("role","menuitem");d.onmouseenter=()=>{ctxI=i;ctxDraw()};d.onclick=()=>{ctxClose();it.fn()};m.append(d)});
 show("#ctx",true);m.style.left=Math.min(x,innerWidth-m.offsetWidth-8)+"px";m.style.top=Math.min(y,innerHeight-m.offsetHeight-8)+"px"}
function ctxDraw(){[...$("#ctx").children].forEach((d,i)=>d.classList.toggle("sel",i===ctxI))}
function ctxClose(){show("#ctx",false);ctxL=[]}
const ctxIsOpen=()=>$("#ctx").classList.contains("on");
function ctxKey(e){const k=e.key;e.preventDefault();e.stopPropagation();
 if(k==="Escape"||k==="ContextMenu")ctxClose();else if(k==="ArrowDown"){ctxI=(ctxI+1)%ctxL.length;ctxDraw()}else if(k==="ArrowUp"){ctxI=(ctxI-1+ctxL.length)%ctxL.length;ctxDraw()}
 else if(k==="Enter"){const it=ctxL[ctxI];ctxClose();if(it)it.fn()}}
function toggleFav(){const it=items[li];if(!it)return;const on=!it.favorite;it.favorite=on?1:0;post("/api/favorite",{media_id:it.id,on});counts.favorites+=on?1:-1;
 if(view==="favorites"&&!on){items.splice(li,1);li=Math.min(li,items.length-1)}drawList()}
addEventListener("contextmenu",e=>{
 const card=e.target.closest&&e.target.closest("#list .card");
 if(layer==="lib"&&card){e.preventDefault();li=[...card.parentNode.children].indexOf(card);drawList();const it=items[li];if(!it)return;
  return ctxOpen(e.clientX,e.clientY,[{t:"Play",fn:()=>startVod(it)},{t:"Details (picture, plot, cast)",fn:()=>openInfo()},{t:it.favorite?"Remove from favorites":"Add to favorites",fn:toggleFav},{t:"Rename this video",fn:()=>openRename("title")},it.series?{t:"Rename the show",fn:()=>openRename("series")}:null].filter(Boolean))}
 const blk=e.target.closest&&e.target.closest("#grid .blk");
 if(layer==="guide"&&blk&&blk.dataset.r!==undefined){e.preventDefault();g.row=+blk.dataset.r;g.t=+blk.dataset.t;drawGuide();
  return ctxOpen(e.clientX,e.clientY,[{t:"Watch this channel",fn:()=>{closeAll();tune(g.row)}},{t:"Details (picture, plot, cast)",fn:()=>openInfo()},{t:"Rename this video",fn:()=>openRename("title")}])}
 if(layer===""&&!e.target.closest("input,textarea")){e.preventDefault();const t=renameTarget();
  ctxOpen(e.clientX,e.clientY,[{t:"Home menu",fn:()=>openHome()},{t:"TV guide",fn:()=>openGuide()},{t:"Library and search",fn:()=>openLib()},t?{t:"Details about this video",fn:()=>openInfo()}:null,{t:"Settings",fn:()=>openSettings()}].filter(Boolean))}});
addEventListener("mousedown",e=>{if(ctxIsOpen()&&!e.target.closest("#ctx"))ctxClose()});
/* ---- on demand: the next episode starts by itself after a short countdown ---- */
let neT=null,neItem=null;
async function nextEpisode(cur){let n=null;try{n=(await api("/api/next/"+cur.id)).next}catch(e){}
 if(!n||vod!==cur)return tune(ci);
 neItem=n;let left=10;paint($("#nextep"),theme.color);$("#ne-t").textContent=label(n);const tick=()=>{$("#ne-c").textContent=`Starts in ${left} s`;if(left--<=0)nePlay()};
 show("#nextep",true);tick();clearInterval(neT);neT=setInterval(tick,1e3)}
function neClose(){clearInterval(neT);neT=null;show("#nextep",false)}
function nePlay(){const n=neItem;neClose();if(n)startVod(n)}
function neStop(){neClose();neItem=null;tune(ci)}
$("#ne-go").onclick=nePlay;$("#ne-no").onclick=neStop;
const neOpen=()=>$("#nextep").classList.contains("on");
/* ---- what's new after an update (shown once) ---- */
async function showNews(){if(REMOTE)return;
 try{const w=await api("/api/welcome");if(w.show)return showWelcome(w)}catch(e){}try{const j=await api("/api/whatsnew");if(!j.notes||!j.notes.length)return;paint($("#news"),theme.color);
 $("#nw-ok").textContent="OK";$("#news").dataset.kind="news";$("#nw-h").textContent="What's new in "+theme.name+" "+j.version;const ul=$("#nw-l");ul.textContent="";for(const n of j.notes)for(const l of n.lines)ul.append(el("li",0,l));
 show("#news",true);$("#nw-ok").focus()}catch(e){}}
function closeNews(){const k=$("#news").dataset.kind;if(k==="lineup")return saveLineup();
 if(k==="welcome"){post("/api/welcome",{});$("#news").dataset.kind="";return openLineup(true)}
 show("#news",false);post("/api/whatsnew",{});$("#news").dataset.kind=""}
/* ---- "Your channels": pick the lineup (first start, and Settings > Channels) ---- */
let lineupOff=null,lineupWas="";
async function openLineup(first){let j;try{j=await api("/api/lineup")}catch(e){show("#news",false);return}
 const nw=$("#news");nw.dataset.kind="lineup";nw.dataset.first=first?"1":"";paint(nw,theme.color);$("#nw-h").textContent="Pick your channels";
 const ul=$("#nw-l");ul.textContent="";lineupOff=new Set();
 ul.append(el("li","lnote",(first?"Everything is on. ":"")+"Tap a channel to switch it off or on. Channels only show once you have videos for them, and nothing is ever deleted - change this any time in Settings > Channels."));
 for(const g of j.groups){const li=el("li","lgrp");li.append(el("b",0,g.name));const row=el("div","picks");
  for(const c of g.channels){if(!c.on)lineupOff.add(c.id);const b=sBtn(c.name,()=>{lineupOff.has(c.id)?lineupOff.delete(c.id):lineupOff.add(c.id);mark()});b.title=c.description||"";
   const mark=()=>{const on=!lineupOff.has(c.id);b.classList.toggle("on",on);b.setAttribute("aria-pressed",on)};mark();row.append(b)}
  li.append(row);ul.append(li)}
 lineupWas=[...lineupOff].sort().join();$("#nw-ok").textContent="Done";show("#news",true);const f=ul.querySelector("button");(f||$("#nw-ok")).focus()}
async function saveLineup(){const nw=$("#news");if([...lineupOff].sort().join()===lineupWas){show("#news",false);nw.dataset.kind="";return}try{const r=await pj("/api/channels-config",{op:"lineup",off:[...lineupOff]});chList=null;
  toast(r.note||"Saved.");show("#news",false);nw.dataset.kind="";libChanged("channels updated");if(layer==="settings")drawSettings()}
 catch(e){toast(String(e.message||e).replace(/^Error: /,""))}}
function showWelcome(w){const nw=$("#news");nw.dataset.kind="welcome";paint(nw,theme.color);$("#nw-h").textContent="Welcome to "+theme.name;const ul=$("#nw-l");ul.textContent="";
 for(const l of[w.media?`${w.media} video(s) found so far - they are already on your channels.`:"No videos yet: drag movies or shows onto this window, or put them in the Inbox folder.",
  "Press H (or Esc) for the Home menu, G for the TV guide, L for the library.",
  "Press O for Settings: name your station, pick its color, add free movies, posters and more.",
  "Want it on your phone too? Settings > Other devices."])ul.append(el("li",0,l));
 $("#nw-ok").textContent="Let's watch";show("#news",true);$("#nw-ok").focus()}
$("#nw-ok").onclick=closeNews;
setTimeout(showNews,2500);   /* once, after the theme has loaded */
const newsOpen=()=>$("#news").classList.contains("on");
$("#tapgo").onclick=()=>{show("#tapgo",false);v.muted=false;v.play().catch(()=>{})};
$("#xclose").onclick=()=>dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}));
document.body.classList.toggle("coarse",COARSE);
addEventListener("touchstart",()=>{if(layer==="")mbarShow()},{passive:true});
setInterval(()=>{document.body.classList.toggle("inlayer",layer!=="");if(layer!=="")show("#mbar",false)},300);
/* ---- drag videos onto the window to add them (they land in the Inbox folder) ---- */
const VEXT=/\.(mp4|m4v|mkv|webm|mov|avi|wmv|flv|ts|m2ts|mts|mpg|mpeg|divx|ogv|3gp|srt|vtt)$/i;let dragN=0,upBusy=false;
const hasFiles=e=>e.dataTransfer&&[...(e.dataTransfer.types||[])].includes("Files");
addEventListener("dragenter",e=>{if(!hasFiles(e))return;e.preventDefault();dragN++;show("#dropz",true)});
addEventListener("dragover",e=>{if(hasFiles(e))e.preventDefault()});
addEventListener("dragleave",e=>{if(!hasFiles(e))return;if(--dragN<=0){dragN=0;show("#dropz",false)}});
async function entryFiles(en,out){if(en.isFile)await new Promise(r=>en.file(f=>{out.push(f);r()},r));
 else if(en.isDirectory){const rd=en.createReader();for(;;){const part=await new Promise(r=>rd.readEntries(r,()=>r([])));if(!part.length)break;for(const x of part)await entryFiles(x,out)}}}
addEventListener("drop",async e=>{if(!hasFiles(e))return;e.preventDefault();dragN=0;show("#dropz",false);if(REMOTE)return toast("Add videos on the PC.");
 const files=[];const ents=[...(e.dataTransfer.items||[])].map(it=>it.webkitGetAsEntry&&it.webkitGetAsEntry()).filter(Boolean);   /* read everything before the first await: the browser empties the drop afterwards */
 const plain=[...e.dataTransfer.files];
 for(const en of ents)await entryFiles(en,files);
 if(!files.length)files.push(...plain);
 const ok=files.filter(f=>VEXT.test(f.name));if(!ok.length)return toast("Those are not videos HERO TV can use (mp4, mkv, avi...).");
 if(upBusy)return toast("Still adding the last ones. Drop these again in a moment.");
 upBusy=true;let done=0,bad=0;
 try{const tok=(await api("/api/upload-token")).token;
  for(const f of ok){toast(`Adding ${done+1} of ${ok.length}: ${f.name}`);
   try{const r=await fetch("/api/upload?name="+encodeURIComponent(f.name)+"&token="+encodeURIComponent(tok),{method:"POST",headers:{"Content-Type":"application/octet-stream","X-HeroTV-Upload":"1"},body:f});
    if(r.ok)done++;else{bad++;let m="";try{m=(await r.json()).error}catch(x){}toast(f.name+": "+(m||"could not be added"))}}catch(x){bad++}}}
 catch(x){bad=ok.length}
 upBusy=false;toast(done?`${done} video${done===1?"":"s"} added to your Inbox. HERO TV will file ${done===1?"it":"them"} in about a minute.${bad?` (${bad} failed)`:""}`:"Nothing could be added.")});
/* the mouse pointer only shows while it is being used */
let curT;addEventListener("mousemove",()=>{mbarShow();if(vod&&layer==="")osd();document.body.classList.remove("hide-cursor");clearTimeout(curT);curT=setTimeout(()=>document.body.classList.add("hide-cursor"),3e3)});
(async()=>{try{const dv=await api("/api/device");REMOTE=!!dv.remote;MK=dv.mk||"";document.body.classList.toggle("remote",REMOTE)}catch(e){}
 try{await sync();setChans((await api("/api/channels")).channels)}catch(e){return msg("Can't reach HERO TV","Make sure the HERO TV window is still open, then press F5.")}
 try{const h=await api("/api/health");if(h.api!==NEED_API)toast(h.frozen?"This HERO TV program is older than its files. Settings > Backup and about > Check now, then Install now, puts the matching version in place (or run the latest HERO TV Setup).":"HERO TV is an older version than this page. Close it completely and start it again to get the newest features.")}catch(e){}
 try{theme=Object.assign(theme,await api("/api/theme"));document.title=theme.name;root.style.setProperty("--brand",theme.color);applyCues(theme.subs);applyComfort()}catch(e){}
 let pf={};try{pf=await api("/api/prefs")}catch(e){}
 if(typeof pf.volume==="number")v.volume=pf.volume;if("muted" in pf)v.muted=!!pf.muted;if(pf.bigtext)setBig(true,false);if(typeof pf.subs==="string")subPref=pf.subs;
 let i=pf.channel!=null?chans.findIndex(c=>c.number===pf.channel):-1;if(i<0)i=chans.findIndex(c=>c.id===localStorage.getItem("ch"));tune(i<0?0:i);pollAlerts();setTimeout(()=>capTest(false),8000);
 try{if(!localStorage.getItem("homeHint")){localStorage.setItem("homeHint","1");setTimeout(()=>toast("Tip: press H for the home menu, or ? for help"),6000)}}catch(e){}})();
})();
