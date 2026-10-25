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

/* ---- channel colours: every channel owns one accent; text colour is picked for contrast ---- */
function onColor(hex){const m=/^#?([0-9a-f]{6})$/i.exec(hex||"");if(!m)return"#0b0d16";const n=parseInt(m[1],16),f=c=>{c/=255;return c<=.03928?c/12.92:Math.pow((c+.055)/1.055,2.4)};
 const L=.2126*f(n>>16)+.7152*f(n>>8&255)+.0722*f(n&255);return L>.3?"#0b0d16":"#ffffff"}
function paint(node,color){const c=/^#[0-9a-f]{6}$/i.test(color||"")?color:"#ffcf1f";node.style.setProperty("--accent",c);node.style.setProperty("--on",onColor(c))}
let REMOTE=false,MK="";   /* REMOTE = this is a phone/laptop on the home WiFi (watch-only); MK = its media key */
const withK=u=>REMOTE&&MK?u+(u.includes("?")?"&":"?")+"k="+encodeURIComponent(MK):u;
const COARSE=matchMedia("(pointer:coarse)").matches;
const thumb=(id,lazy)=>{const i=el("img");i.alt="";i.decoding="async";if(lazy)i.loading="lazy";i.src=withK("/thumb/"+id);i.onerror=()=>i.remove();return i};
const tile=t=>{let h=0;for(const ch of t||"")h=(h*31+ch.charCodeAt(0))%360;return`linear-gradient(135deg,hsl(${h} 34% 22%),hsl(${(h+50)%360} 40% 11%))`};
function hints(box,pairs){box.textContent="";const k=el("div","kbd");for(const[a,b]of pairs){k.append(el("b",0,a),el("span",0,b))}box.append(k)}

/* ---- playback ---- */
function osd(keep){const c=chans[ci];if(!c)return;const wx=c.kind==="weather"&&!vod;if(!slot&&!vod&&!wx)return;const s=vod||slot;
 $("#osd").classList.toggle("vod",!!vod);$("#o-num").textContent=vod?"VOD":c.number;
 $("#o-title").textContent=wx?"Local weather":label(s);
 $("#o-sub").textContent=wx?c.name+", live forecast and alerts":vod?(vod.startOver?"Start over":"On demand")+([vod.franchise,vod.year].filter(Boolean).length?", "+[vod.franchise,vod.year].filter(Boolean).join(", "):""):`${c.name}${s.block?" · "+s.block:""}, ${T(s.start)} to ${T(s.end)}, ${mins(s.end-nowS())} min left`;
 osdHints(wx?"":vod?"":nextSlot?`Next at ${T(nextSlot.start)}: ${label(nextSlot)}`:"",
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
function startOver(){if(!slot||vod)return;startVod({id:slot.media_id,title:slot.title,series:slot.series,season:slot.season,episode:slot.episode,
 franchise:slot.franchise,year:slot.year,runtime_s:slot.runtime_s,position:0,completed:0,startOver:true})}
async function sync(){const a=Date.now(),j=await api("/api/now");off=j.now-(a+Date.now())/2e3;cfg=j}
async function tune(i){if(sleeping)return;if(!chans.length){msg("No channels have anything to show yet","Put videos in your media folder, or open Settings (O) and check the library.");return}const my=++seq;vod=null;const ni=(i+chans.length)%chans.length;if(started&&ni!==ci)prevCi=ci;started=true;ci=ni;localStorage.setItem("ch",chans[ci].id);savePrefs();msg("");paint(root,chans[ci].color);
 const wx=chans[ci].kind==="weather";show("#wx",wx);document.body.classList.toggle("novideo",wx);
 if(wx){slot=nextSlot=null;v.pause();v.removeAttribute("src");v.load();loadWx();return osd()}
 let j;try{j=await api(`/api/channel/${chans[ci].id}/now`)}catch(e){return msg("Can't reach HERO TV","Make sure the HERO TV window is still open. Trying again."),setTimeout(()=>tune(ci),3e3)}
 if(my!==seq)return; /* a newer tune() superseded this one */
 slot=j.slot;nextSlot=j.next;if(!slot){v.removeAttribute("src");v.load();v.classList.remove("dim");osd();return chans[ci].id==="free"?msg("No free movies yet","Double-click Get-Free-Movies.bat to download some, then press F5."):msg("Nothing is scheduled on "+chans[ci].name,"Add videos to this channel with Add-Movies.bat or Sort-Movies.bat, then press F5.")}
 play(withK(`/media/${slot.media_id}`),()=>Math.min(nowS()-slot.start,(v.duration||1e9)-.5));loadSubs(slot.media_id);osd()}
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
function play(url,startFn){clearSub();v.classList.add("dim");v.src=url;v.onloadedmetadata=()=>{v.currentTime=Math.max(0,startFn());v.play().catch(e=>{if(e&&e.name==="NotAllowedError")show("#tapgo",true)})};v.onplaying=()=>v.classList.remove("dim")}
async function startVod(it){vod=it;slot=null;closeAll();show("#wx",false);document.body.classList.remove("novideo");layer="";msg("");const p=it.completed?0:it.position;
 it.skip=null;if(it.series){try{it.skip=await api("/api/skip?series="+encodeURIComponent(it.series))}catch(e){}if(vod!==it)return}
 play(withK(`/media/${it.id}`),()=>{const d=v.duration||0;if(p>10&&p<d-10)return p;
  const sk=it.skip;if(sk&&sk.intro>0&&sk.intro<d*.5){toast("Skipped the intro. Press ← to go back.");return sk.intro}return 0});loadSubs(it.id);osd()}
v.addEventListener("ended",()=>{if(vod){post("/api/progress",{media_id:vod.id,position:0,completed:true});if(sleepAfter)return goToSleep();if(vod.series)return nextEpisode(vod);return tune(ci)}
 setTimeout(()=>tune(ci),Math.max(0,(slot?slot.end-nowS():0)*1e3)+80)});
v.addEventListener("error",async()=>{const id=vod?vod.id:slot&&slot.media_id;if(!id)return;
 if(REMOTE)return msg("This video can't play on this device yet","Usually a .mkv file. On the PC: Settings > Tools > Make iPhone-friendly copies. Change channel to keep watching.");
 errs=errs.filter(t=>Date.now()-t<3e4);errs.push(Date.now());
 await post("/api/report-error",{media_id:id,reason:v.error&&v.error.message});
 if(errs.length>=5){msg("Playback keeps failing","This video may be in a format browsers can't play. Drag it onto Convert-Video.bat. Trying again in 10 seconds.");errs=[];return setTimeout(()=>tune(ci),1e4)}
 setTimeout(()=>tune(ci),1500)});
setInterval(()=>{ // 1 Hz: sleep timer, slot rollover, drift correction, stall watchdog, progress
 sleepCheck();if(sleeping)return;
 if(vod&&vod.skip&&vod.skip.outro>0&&!vod.credDone&&v.duration&&v.currentTime>30&&v.duration-v.currentTime<=vod.skip.outro){vod.credDone=true;toast("Skipped the credits");v.dispatchEvent(new Event("ended"))}
 upNext();
 if(slot&&!vod&&nowS()>=slot.end)tune(ci);
 if(slot&&!vod&&!v.paused&&v.readyState>2){const e=nowS()-slot.start;if(Math.abs(v.currentTime-e)>4&&e<v.duration-1)v.currentTime=e}
 if(v.src&&!v.paused&&v.currentTime===lastPos){if(++stall>20){stall=0;tune(ci)}}else stall=0;lastPos=v.currentTime;
 /* sound but no picture = a video format this browser cannot show: report it, say so, move on */
 if(v.src&&!v.paused&&v.readyState>=2&&v.currentTime>3&&v.videoWidth===0){if(++nopic>=3){nopic=0;const id=vod?vod.id:slot&&slot.media_id;
   if(id){post("/api/report-error",{media_id:id,reason:"no-picture"});msg("This video has sound but no picture","Its video format cannot be shown here. It is being skipped. To fix it, drag the file onto Convert-Video.bat.");setTimeout(()=>{msg("");tune(ci)},5e3)}}}else nopic=0;
 if(layer===""&&$("#osd").classList.contains("on"))bar()},1e3);
setInterval(()=>{const id=vod?vod.id:slot&&slot.media_id;if(id&&v.currentTime>5)post("/api/progress",{media_id:id,position:v.currentTime,completed:v.duration&&v.currentTime>v.duration*.95})},1e4);
setInterval(()=>sync().catch(()=>{}),3e5);
const NEED_API=15;   /* must match API_LEVEL in herotv/config.py */
let libV=null,toastT;
function toast(t){const e=$("#toast");e.textContent=t;e.classList.add("on");clearTimeout(toastT);toastT=setTimeout(()=>e.classList.remove("on"),5000)}
async function libChanged(note){try{const cur=chans[ci]&&chans[ci].id;setChans((await api("/api/channels")).channels);const i=chans.findIndex(c=>c.id===cur);if(i>=0)ci=i;
  if(layer==="guide"){await loadGuide();drawGuide()}else if(layer==="lib"){const keep=li;await search();li=Math.min(keep,items.length-1);drawList()}
  toast("Library updated"+(note&&note!=="updated"?": "+note:""))}catch(e){}}
const beat=()=>fetch("/api/hb").then(r=>r.json()).then(j=>{if(libV===null)libV=j.lib;else if(j.lib!==libV){libV=j.lib;libChanged(j.note)}}).catch(()=>{});beat();setInterval(beat,1e4);
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
 if(vod||!slot||!nextSlot||left<=0||left>75||layer!==""||sleeping){u.classList.remove("on");u.dataset.k="";return}
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
 homeData=d}
const dayWord=t=>(new Date(t*1e3).toDateString()===new Date(nowS()*1e3).toDateString()?"today ":"tomorrow ")+T(t);
function homeTiles(){const d=homeData,c=chans[ci],free=allChans.find(x=>x.id==="free"),wxc=chans.find(x=>x.kind==="weather"),list=[];
 const tuneTo=i=>{closeAll();tune(i)};
 list.push({ic:"📺",t:"Live TV",s:c?`${c.number} ${c.name}${slot?": "+label(slot):""}`:"",img:slot&&slot.media_id,go:()=>closeAll()});
 list.push(d.cont?{ic:"⏯️",t:"Continue watching",s:`${label(d.cont)}, ${hms(d.cont.position)} in`,img:d.cont.id,go:()=>startVod(d.cont)}
  :{ic:"⏯️",t:"Continue watching",s:"Nothing started yet. Pick something from the library.",dim:1,go:()=>{closeAll();openLib()}});
 if(d.recent)list.push({ic:"🆕",t:"New in your library",s:`${d.recentN} new: ${label(d.recent)}${d.recentN>1?" and more":""}`,img:d.recent.id,go:()=>{closeAll();openLib("recent")}});
 if(d.special){const x=d.special,on=x.s.start<=nowS();list.push({ic:"🍿",t:x.s.block,s:`${on?"On now":"Starts "+dayWord(x.s.start)} · ${x.c.number} ${x.c.name}`,img:x.s.media_id,go:()=>tuneTo(chans.findIndex(k=>k.id===x.c.id))})}
 list.push({ic:"🗓️",t:"TV guide",s:"See what is on every channel",go:()=>{closeAll();openGuide()}});
 list.push({ic:"🔍",t:"Library and search",s:"Find any movie or show and play it now",go:()=>{closeAll();openLib()}});
 const fv=d.counts&&d.counts.favorites||0;list.push({ic:"⭐",t:"Favorites",s:fv?`${fv} saved`:"Press F2 on any video to save it here",dim:!fv,go:()=>{closeAll();openLib("favorites")}});
 if(free){const n=d.help?d.help.free:null;list.push({ic:"🎁",t:"Free movies",s:n===0?"None yet. Double-click Get-Free-Movies.bat":n?`${n} free ${n===1?"title":"titles"} to watch`:"Free public-domain movies",go:()=>{const i=chans.indexOf(free);if(i<0){toast("No free movies yet. Double-click Get-Free-Movies.bat.");return}tuneTo(i)}})}
 if(wxc)list.push({ic:"⛅",t:"Weather",s:"Forecast and alerts",go:()=>tuneTo(chans.indexOf(wxc))});
 list.push({ic:"😴",t:"Sleep timer",s:sleepLeft()?"Pauses in "+sleepLeft()+". Select to change":"Off. Select to set 30, 60, 90 or 120 minutes",stay:1,go:cycleSleep});
 const big=document.body.classList.contains("big");list.push({ic:"🔠",t:"Bigger text",s:big?"On. Select to turn off":"Off. Select to make text bigger",stay:1,go:()=>setBig(!big,true)});
 if(d.check){const miss=d.check.filter(l=>!l.ideas).reduce((a,l)=>a+l.missing,0);list.push({ic:"📝",t:"Checklist",s:miss?`${miss} titles still to find`:"Everything on your lists is here",go:()=>openCheck()})}
 if(!REMOTE)list.push({ic:"⚙️",t:"Settings",s:"Look, library, weather, cover art, backup",go:()=>openSettings()});
 list.push({ic:"❓",t:"Help",s:d.help&&d.help.problem_count?`${d.help.problem_count} video(s) need attention`:"Keys, and what to do if something looks wrong",go:()=>openHelp("home")});
 return list}
function drawHome(){const box=$("#tiles"),L=homeTiles();box.textContent="";paint($("#home"),theme.color);hi=Math.max(0,Math.min(hi,L.length-1));
 $("#h-clock").textContent=dayStr();$("#h-hello").textContent=theme.tagline;$("#home h2").textContent=theme.name;
 hints($("#h-hints"),[["← → ↑ ↓","choose"],["Enter","open"],["Esc","back to TV"],["?","help"]]);
 L.forEach((t,i)=>{const n=el("div","tl"+(i===hi?" sel":"")+(t.dim?" dim":""));if(t.img)n.append(thumb(t.img));n.append(el("span","ic",t.ic),el("b",0,t.t),el("small",0,t.s));n.onclick=()=>{hi=i;t.go();if(t.stay)drawHome()};box.append(n)});
 homeList=L}
let homeList=[];
function homeKey(e){const k=e.key,cols=getComputedStyle($("#tiles")).gridTemplateColumns.split(" ").length||4;
 if(k==="Escape"||k==="Backspace"||k==="h"||k==="H"||k==="Home"){e.preventDefault();return closeAll()}
 if(k==="?"||k==="F1"){e.preventDefault();return openHelp("home")}
 if(k==="s"||k==="S"){return cycleSleep()}
 if(k==="t"||k==="T"){return setBig(!document.body.classList.contains("big"),true)}
 const mv=d=>{e.preventDefault();hi=Math.max(0,Math.min(homeList.length-1,hi+d));drawHome()};
 if(k==="ArrowRight")mv(1);else if(k==="ArrowLeft")mv(-1);else if(k==="ArrowDown")mv(cols);else if(k==="ArrowUp")mv(-cols);
 else if(k==="Enter"){e.preventDefault();const t=homeList[hi];if(t){t.go();if(t.stay)drawHome()}}}
let ck={data:null,i:0};
async function openCheck(){layer="check";show("#settings",false);show("#home",false);show("#help",false);show("#check",true);paint($("#check"),theme.color);
 hints($("#ck-hints"),[["← →","change list"],["↑ ↓","scroll"],["Esc","back"]]);ck.i=0;ck.data=null;drawCheck();
 try{ck.data=(await api("/api/checklist")).lists}catch(e){}drawCheck()}
function drawCheck(){const tabs=$("#ck-tabs"),body=$("#ck-body"),sum=$("#ck-sum");tabs.textContent=body.textContent=sum.textContent="";
 if(!ck.data){body.append(el("div","empty","Loading your lists..."));return}
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
 if(!h)row(false,"HERO TV cannot reach its own server.","Make sure the black HERO TV window is still open, then press F5.");
 else{row(h.playable>0,h.playable?`${h.playable} videos are ready to play.`:"No videos are ready to play yet.",h.playable?"":"Put videos in your media folder (Open-Media-Folder.bat), or run Get-Free-Movies.bat for free ones.");
  row(h.ffmpeg,h.ffmpeg?"Video tools (ffmpeg) are installed.":"Video tools (ffmpeg) were not found.",h.ffmpeg?"":"Double-click Check-Setup.bat. It can install them for you.");
  if(h.problem_count){row(false,`${h.problem_count} video(s) are being skipped:`,"");for(const p of h.problems)row(false,p.title,p.why+" "+p.fix);if(h.problem_count>h.problems.length)row(false,"...and more.","Run Why-Isnt-It-Showing.bat for the full list.")}
  else row(true,"Every video in your library can play.","");
  if(h.hidden_channels&&h.hidden_channels.length)row(true,`${h.hidden_channels.length} channel(s) are hidden until they have something to show: ${h.hidden_channels.join(", ")}`,"Put a video in that channel's folder (or in Inbox, then run Sort-Movies.bat) and the channel appears by itself.");
  if(h.inbox_waiting)row(false,`${h.inbox_waiting} video(s) are waiting in the Inbox folder.`,"HERO TV files them by title by itself once they have finished copying. Ones it cannot place stay there: use Add-Movies.bat to choose their channel.");
  row(true,"Your videos are in: "+h.media_dir,"Open-Media-Folder.bat opens it.")}
 R.append(el("h3",0,"Keys"));const t=el("table");
 for(const[a,b]of[["↑ ↓","Change channel"],["0-9","Type a channel number"],["Backspace","Previous channel"],["Esc or H","Home menu"],["G","TV guide"],["L","Library and search"],["R","Start this show over"],["F2","Add or remove favorite"],["D (F8 in Library)","Details: picture, plot, cast, rating"],["O","Settings"],["Right-click","Menu for the video under the pointer"],["F3 / F4","Rename video / show"],["C","Subtitles: off / each language"],["S","Sleep timer"],["T","Bigger text"],["← →","Volume (skip, when watching on demand)"],["M","Mute"],["F","Fullscreen"],["J / E","On demand: mark where the intro ends / credits start"]]){const r=el("tr");const k=el("td"),b1=el("b",0,a);k.append(b1);r.append(k,el("td",0,b));t.append(r)}
 R.append(t)}

/* ---- guide ---- */
let g={t0:0,t:0,row:0,data:[]};const WIN=3*3600;
async function loadGuide(){const j=await api(`/api/guide?from=${g.t0}&hours=3`);g.data=j.channels.filter(c=>chans.some(x=>x.id===c.id))}
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
   if(on){const p=el("i");p.style.width=Math.min(100,(nowS()-s.start)/(s.end-s.start)*100)+"%";b_.append(p)}
   if(r===g.row&&s.start<=g.t&&g.t<s.end)b_.classList.add("sel");b_.dataset.r=r;b_.dataset.t=s.start;b_.onclick=()=>{if(COARSE&&g.row===r&&s.start<=g.t&&g.t<s.end){closeAll();return tune(r)}g.row=r;g.t=s.start;drawGuide()};b_.ondblclick=()=>{closeAll();tune(r)};track.append(b_)}
  if(!c.slots.length&&c.kind!=="weather")track.append(el("div","none","No programming"));
  row.append(ch,track);rows.append(row)});
 {const rh=rows.firstChild&&rows.firstChild.offsetHeight;if(rh){rows.style.flex="none";rows.style.height=Math.max(1,Math.floor((grid.getBoundingClientRect().bottom-rows.getBoundingClientRect().top)/rh))*rh+"px"}   /* whole rows only, never a half-cut one */
  const cur=rows.children[g.row];if(cur)cur.scrollIntoView({block:"nearest"})}
 const nl=el("div");nl.id="nowline";const x=(nowS()-g.t0)*pxs;if(x>=0&&x<=WIN*pxs){nl.style.left=left+x+"px";grid.append(nl)}
 const c=g.data[g.row]||{slots:[]},s=inSlot(c,g.t),d=$("#detail");d.textContent="";paint(d,c.color);
 const chn=el("div","chn");chn.append(el("span","plate",c.number),el("span",0,c.name));d.append(chn);
 if(c.kind==="weather"){d.append(el("h3",0,"Local weather"),el("p","meta","Live, around the clock"),el("p",0,"Current conditions, the hourly and 7-day forecast, and live weather alerts. Press Enter to watch."))}
 else if(s){d.append(el("h3",0,label(s)),el("p","meta",`${T(s.start)} to ${T(s.end)}, ${mins(s.end-s.start)} min`+(s.start<=nowS()&&nowS()<s.end?", on now":"")+([s.franchise,s.year].filter(Boolean).length?"   ·   "+[s.franchise,s.year].filter(Boolean).join(", "):"")+(s.block?"   ·   "+s.block:"")));if(s.plot)d.append(el("p",0,s.plot))}
 else d.append(el("p",0,"Nothing is scheduled here."))}
async function openGuide(){show("#settings",false);show("#info",false);const n=nowS();g.t0=Math.floor(n/1800)*1800;g.t=n;g.row=ci;layer="guide";await loadGuide();hints($("#g-hints"),[["↑ ↓","channel"],["← →","time"],["Enter","watch"],["G","close"],["L","library"],["F3","rename"]]);
 const nt=el("span",0,"Showtimes are generated on this PC from your own videos. They are not real TV listings.");$("#g-hints").append(nt);nt.style.marginLeft="auto";
 show("#guide",true);show("#osd",false);drawGuide();placePreview(true)}
setInterval(()=>{if(layer==="guide"){const d=$(".hdr .day");if(d)d.textContent=dayStr()}},15e3);
async function guideKey(k){const c=g.data[g.row],s=inSlot(c,g.t);
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
 const tb=$("#l-tabs");tb.textContent="";for(const[k,n]of VIEWS){const sp=el("span",k===view?"on":"",n+(k==="all"?"":" "+counts[k]));sp.onclick=()=>{view=k;search()};tb.append(sp)}
 const q=$("#q").value.trim();$("#l-count").textContent=items.length?`${items.length} ${items.length===1?"video":"videos"}`:"";
 if(!items.length){const e=el("div","empty");if(q){e.append(el("b",0,`Nothing matches "${q}".`),el("br"),document.createTextNode("Try a title, a series or a channel name."))}
  else if(view==="continue")e.append(el("b",0,"Nothing in progress."),el("br"),document.createTextNode("Videos you start from the library show up here so you can pick up where you left off."));
  else if(view==="favorites")e.append(el("b",0,"No favorites yet."),el("br"),document.createTextNode("Highlight a video and press F2 to add it."));
  else{e.append(el("b",0,"No videos yet."),el("br"),document.createTextNode("Add movies with Add-Movies.bat or Sort-Movies.bat, then press F5."))}L.append(e);return}
 items.forEach((it,k)=>{const c=el("div","card"+(k===li?" sel":"")),pic=el("div","pic");pic.style.background=tile(it.title);pic.append(thumb(it.id,true));
  const resume=it.position>10&&!it.completed;if(resume&&it.runtime_s){const p=el("i");p.style.width=Math.min(100,it.position/it.runtime_s*100)+"%";pic.append(p)}
  pic.append(el("em",0,mins(it.runtime_s)+" min"));if(it.favorite)pic.append(el("u",0,"★"));
  const meta=[it.franchise,it.year].filter(Boolean).join(", ")+(resume?(it.franchise||it.year?", ":"")+"resume at "+mins(it.position)+" min":"");
  c.append(pic,el("b",0,label(it)),el("small",0,meta||" "));c.onclick=()=>{if(COARSE&&li===k)return startVod(it);li=k;drawList()};c.ondblclick=()=>startVod(it);L.append(c)});
 const f=L.firstElementChild;if(f&&f.classList.contains("card")){const second=L.children[cols],step=second?second.offsetTop-f.offsetTop:f.offsetHeight;
  if(step>0){L.style.flex="none";L.style.height=Math.max(1,Math.floor((L.parentNode.clientHeight-L.offsetTop-$("#l-hints").offsetHeight-16)/step))*step+"px"}}   /* whole rows only */
 const sel=L.querySelector(".card.sel");if(sel)sel.scrollIntoView({block:"nearest"})}
async function openLib(v0){layer="lib";show("#settings",false);show("#info",false);view=v0||"all";show("#home",false);show("#help",false);hints($("#l-hints"),[["← → ↑ ↓","browse"],["Enter","play, resumes where you left off"],["Tab","all / continue / favorites"],["F2","favorite"],["F8","details"],["F3","rename"],["F4","rename show"],["Esc","back"]]);show("#lib",true);show("#osd",false);$("#q").value="";await search();$("#q").focus()}
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
 if(!w.configured){box.append(el("div","wmsg","No town set yet. Double-click Set-Weather-Location.bat in the HERO TV folder, then press F5."));return}
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
 const pic=$("#in-pic");pic.style.backgroundImage=`url(/thumb/${t.id})`;pic.classList.add("wide");
 let d=null;try{d=await api("/api/info/"+t.id)}catch(e){}
 if(layer!=="info"||!d)return;
 $("#in-t").textContent=d.title||t.title;
 $("#in-m").textContent=[d.year,d.runtime_min?d.runtime_min+" min":"",d.rating?"★ "+d.rating.toFixed(1):"",(d.genres||[]).join(", ")].filter(Boolean).join("  ·  ");
 $("#in-tag").textContent=d.tagline||"";$("#in-plot").textContent=d.plot||"";
 $("#in-cast").textContent=(d.cast||[]).length?"Starring "+d.cast.join(", "):"";
 if(d.poster){pic.style.backgroundImage=`url(${withK(`/poster/${t.id}?v=${Date.now()%1e6}`)})`;pic.classList.remove("wide")}
 $("#in-note").textContent=d.plot?"":d.has_key?(d.searched?"No description was found for this title online.":"Looking this up in the background... check again in a minute."):"No description yet. Run Set-Poster-Key.bat once (free) to get posters, plots, cast and ratings.";
 $("#in-cr").textContent=d.source==="TMDB"?"Cover art and descriptions: TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.":"";
 hints($("#in-hints"),[["Enter",infoCtx.back==="lib"?"play":"back"],["Esc","back"]])}
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

/* ---- keys (keyboard / HDMI-CEC remote) ---- */
addEventListener("keydown",e=>{const k=e.key;
 if(layer==="rename"||e.ctrlKey||e.metaKey||e.altKey)return;
 if(sleeping){e.preventDefault();return wake()}
 if(neOpen()){if(k==="Enter"||k===" "){e.preventDefault();nePlay()}else if(k==="Escape"||k==="Backspace"){e.preventDefault();neStop()}return}
 if(newsOpen()){if(k==="Enter"||k==="Escape"||k===" "){e.preventDefault();closeNews()}return}
 if(ctxIsOpen())return ctxKey(e);
 if(layer==="settings")return settingsKey(e);
 if(layer==="info"){if(k==="Escape"||k==="Backspace"||k==="d"||k==="D"){e.preventDefault();closeInfo(false)}else if(k==="Enter"){e.preventDefault();closeInfo(true)}return}
 if((k==="d"||k==="D")&&(layer==="guide"||layer===""||vod)&&!(layer==="lib")){e.preventDefault();return openInfo()}
 if(layer==="home")return homeKey(e);
 if(layer==="check")return checkKey(e);
 if(layer==="help"){if(k==="Escape"||k==="Backspace"||k==="?"||k==="F1"||k==="h"||k==="H"){e.preventDefault();return helpBack==="home"?openHome():closeAll()}return}
 if((k==="F3"||k==="F4")&&(layer==="lib"||layer==="guide"||layer===""||vod)){e.preventDefault();return openRename(k==="F4"?"series":"title")}
 if(layer==="lib"){const mv=d=>{li=Math.max(0,Math.min(items.length-1,li+d));drawList();e.preventDefault()};
  if(k==="Tab"){e.preventDefault();view=VIEWS[(VIEWS.findIndex(x=>x[0]===view)+1)%VIEWS.length][0];search();return}
  if(k==="F2"&&items[li]){e.preventDefault();const it=items[li],on=!it.favorite;it.favorite=on?1:0;post("/api/favorite",{media_id:it.id,on});counts.favorites+=on?1:-1;
   if(view==="favorites"&&!on){items.splice(li,1);li=Math.min(li,items.length-1)}drawList();return}
  if(k==="F8"&&items[li]){e.preventDefault();return openInfo()}
  if(k==="Escape"||k==="Backspace"&&!$("#q").value)closeAll();else if(k==="ArrowDown")mv(cols);else if(k==="ArrowUp")mv(-cols);
  else if(k==="ArrowRight")mv(1);else if(k==="ArrowLeft")mv(-1);else if(k==="Enter"&&items[li])startVod(items[li]);return}
 if(layer==="guide"){if(k==="Escape"||k==="g"||k==="G")closeAll();else if(k.startsWith("Arrow")||k==="Enter"){e.preventDefault();guideKey(k)}return}
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
async function loadTheme(){try{theme=Object.assign(theme,await api("/api/theme"));document.title=theme.name;document.documentElement.style.setProperty("--brand",theme.color);applyCues(theme.subs)}catch(e){}}
function applyCues(st){st=st||{};const b=document.body.classList;b.toggle("cue-l",st.size==="large");b.toggle("cue-xl",st.size==="xl");b.toggle("cue-none",st.bg==="none");b.toggle("cue-yellow",st.color==="yellow")}
const SW=["#ffcf1f","#ff3b3b","#3d6bff","#3ddc84","#b06bff","#ff8c00","#ff2e88","#1fd1b4"];
const SCATS=[["look","Appearance"],["chan","Channels"],["lib","Media library"],["weather","Weather"],["art","Cover art"],["tools","Tools"],["devices","Other devices"],["about","Backup and about"]];
let chList=null,chSel=null;let sCat="look",sData=null,sDirty=false,sLeave=false;
function sMsg(t,cls){const m=$("#st-msg");if(m){m.textContent=t||"";m.className="smsg"+(cls?" "+cls:"")}}
function sField(label,help,input,row){const f=el("div","sf"+(row?" row":""));if(label)f.append(el("label",0,label));if(input)f.append(input);if(help)f.append(el("small",0,help));return f}
function sBtn(text,fn,cls){const b=el("button","sbtn"+(cls?" "+cls:""),text);b.type="button";b.onclick=fn;return b}
function sInput(val,type,ph){const i=el("input");i.type=type||"text";i.value=val||"";if(ph)i.placeholder=ph;i.autocomplete="off";i.spellcheck=false;i.addEventListener("input",()=>{sDirty=true;sLeave=false});return i}
async function sSave(changes,okText,after){sMsg("Saving...");try{const r=await pj("/api/settings",changes);sDirty=false;sLeave=false;
  sData=await api("/api/settings");if(after)await after();sMsg(okText+(r&&r.restart?" Restart HERO TV for this to take effect.":""),"ok")}
 catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}}
async function sAct(name,btn){const old=btn.textContent;btn.disabled=true;btn.textContent="Working...";
 try{const r=await pj("/api/action",{name});sMsg(r.message||"Done.","ok")}catch(e){sMsg(String(e.message||e),"err")}btn.disabled=false;btn.textContent=old}
async function openSettings(cat){if(REMOTE)return toast("Settings are on the PC.");if(cat)sCat=cat;layer="settings";sDirty=false;sLeave=false;chList=null;chSel=null;tData=null;
 for(const id of ["#guide","#lib","#home","#help","#check","#info","#osd","#msg"])show(id,false);placePreview(false);show("#settings",true);paint($("#settings"),theme.color);
 hints($("#st-hints"),[["Tab","next control"],["← →","change section"],["Esc","back"]]);
 try{sData=await api("/api/settings")}catch(e){sData=null}drawSettings()}
function drawSettings(){const nav=$("#st-nav"),main=$("#st-main");nav.textContent=main.textContent="";
 for(const[k,n]of SCATS){const b=el("button",k===sCat?"on":"",n);b.type="button";b.setAttribute("role","tab");b.onclick=()=>sGo(k);b.dataset.k=k;nav.append(b)}
 if(!sData){main.append(el("div","empty","Settings could not be loaded. Make sure HERO TV is still running."));return}
 const d=sData,msg=el("div","smsg");msg.id="st-msg";
 if(sCat==="look"){main.append(el("h3",0,"Appearance"));
  const name=sInput(d.station.name),tag=sInput(d.station.tagline);let col=d.station.color;
  const sw=el("div","sw");const pick=c=>{col=c;sDirty=true;sLeave=false;[...sw.children].forEach(b=>b.classList.toggle("on",b.dataset.c.toLowerCase()===c.toLowerCase()));hex.value=c};
  const hex=sInput(col,"text","#ffcf1f");hex.size=9;hex.addEventListener("input",()=>{if(/^#[0-9a-fA-F]{6}$/.test(hex.value))pick(hex.value)});
  for(const c of SW){const b=el("button",c.toLowerCase()===col.toLowerCase()?"on":"");b.type="button";b.dataset.c=c;b.style.background=c;b.title=c;b.setAttribute("aria-label","Colour "+c);b.onclick=()=>pick(c);sw.append(b)}
  main.append(sField("Station name","Shown on the home screen and the browser tab.",name),sField("Greeting","The line under the name.",tag),
   sField("Main colour","Pick one, or type a code like #ff3b3b.",sw),sField("",null,hex,true));
  const big=el("input");big.type="checkbox";big.checked=document.body.classList.contains("big");big.onchange=()=>setBig(big.checked,true);
  const bl=el("label","lb");bl.append(big," Bigger text");bl.style.display="flex";bl.style.gap="1vw";main.append(sField("",'Makes every screen easier to read from the couch. Same as pressing T.',bl));
  const wnd=el("input");wnd.type="checkbox";wnd.checked=!!d.windowed;wnd.onchange=()=>sSave({windowed:wnd.checked},wnd.checked?"HERO TV will open in a normal window from now on.":"HERO TV will open full screen from now on.");
  const wl=el("label","lb");wl.append(wnd," Open in a window instead of full screen");wl.style.display="flex";wl.style.gap="1vw";main.append(sField("","Takes effect the next time you start HERO TV. F still switches full screen on and off.",wl));
  { const st=Object.assign({size:"normal",bg:"box",color:"white"},d.subs_style),row=el("div","sbar");
    const pick=(opts,key)=>{const sel=el("select");for(const[v,t]of opts){const o=el("option",0,t);o.value=v;if(st[key]===v)o.selected=true;sel.append(o)}
     sel.onchange=()=>{st[key]=sel.value;applyCues(st);sSave({subs_style:st},"Subtitle style saved.",async()=>{await loadTheme()})};sel.dataset.k=key;return sel};
    row.append(pick([["normal","Normal size"],["large","Large"],["xl","Extra large"]],"size"),pick([["box","On a dark box"],["none","Outline only"]],"bg"),pick([["white","White"],["yellow","Yellow"]],"color"));
    row.id="cue-style";main.append(sField("Subtitles","How subtitles look on the TV and on paired phones. Press C while watching to turn them on.",row))}
  main.append(el("div","sbar")),main.lastChild.append(sBtn("Save",()=>sSave({station:{name:name.value,tagline:tag.value,color:col}},"Saved.",async()=>{await loadTheme();paint($("#settings"),theme.color);drawSettings()}),"pri"),
   sBtn("Restore the default look",()=>{if(!main.dataset.sure){main.dataset.sure=1;sMsg("Press the button again to restore the standard name, greeting and colour.","err");return}
    delete main.dataset.sure;sSave({reset_station:true},"Default look restored.",async()=>{await loadTheme();drawSettings()})},"warn"));main.append(msg)}
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
 else{main.append(el("h3",0,"Backup and about"));
  const bar=el("div","sbar"),b1=sBtn("Back up my settings now",()=>sAct("backup",b1),"pri"),b2=sBtn("Open backups folder",()=>sAct("open-backups",b2)),b3=sBtn("Open log folder",()=>sAct("open-logs",b3));bar.append(b1,b2,b3);
  main.append(sField("","A backup keeps your favorites, resume points, channel settings and look - not the videos themselves.",null),bar,msg);
  const ab=el("input");ab.type="checkbox";ab.checked=d.auto_backup!==false;ab.onchange=()=>sSave({auto_backup:ab.checked},ab.checked?"Weekly backups on.":"Weekly backups off.",()=>drawSettings());
  const abl=el("label","lb");abl.append(ab," Back up automatically every week (keeps the last 8)");abl.style.display="flex";abl.style.gap="1vw";
  main.append(sField("",d.last_backup?"Last backup: "+new Date(d.last_backup.when*1e3).toLocaleString():"No backup yet.",abl));
  const a=d.about,kv=el("div","kv");for(const[x,y]of[["HERO TV version",a.version+" (build "+a.api+")"],["Video tools (ffmpeg)",a.ffmpeg&&a.ffprobe?"installed":"MISSING - run Check-Setup.bat"],["Settings file",a.settings_file],["Log file",a.log_file],["Channel files",a.config_dir]])kv.append(el("span",0,x),el("span",0,y));
  main.append(el("h3",0,"About"),kv)}
 const sel=nav.querySelector(".on");if(sel&&document.activeElement===document.body)sel.focus()}
/* ---- Tools: the jobs the .bat files used to do, run in the background ---- */
let tData=null,jobT=null,jobSeen=0;
function jobPoll(){clearTimeout(jobT);if(layer!=="settings")return;api("/api/job").then(j=>{drawJob(j.job);if(j.job&&j.job.state==="running")jobT=setTimeout(jobPoll,1500);
 else if(j.job&&j.job.id!==jobSeen){jobSeen=j.job.id;toast(j.job.title+(j.job.state==="done"?": finished.":": did not finish - see Settings > Tools."));if(sCat==="tools"){tData=null;drawSettings()}}}).catch(()=>{})}
function drawJob(j){const b=$("#jobbox");if(!b)return;b.textContent="";if(!j){b.style.display="none";return}b.style.display="";
 b.append(el("b",0,(j.state==="running"?"Working: ":j.state==="done"?"Finished: ":"Did not finish: ")+j.title));const pre=el("pre",0,j.lines.slice(-25).join("\n")||"Starting...");b.append(pre);pre.scrollTop=pre.scrollHeight;
 if(j.state==="running")b.append(el("small",0,"You can keep watching TV - this carries on in the background. Closing HERO TV stops it (run it again later to continue)."))}
async function runJob(body,btn){if(btn)btn.disabled=true;sMsg("");try{const r=await pj("/api/job",body);drawJob(r.job);jobPoll()}catch(e){sMsg(String(e.message||e).replace(/^Error: /,""),"err")}if(btn)btn.disabled=false}
function tCard(title,help){const c=el("div","tcard");c.append(el("h4",0,title));if(help)c.append(el("small",0,help));return c}
const gb=n=>n>=1e9?(n/1e9).toFixed(1)+" GB":Math.round(n/1e6)+" MB";
function drawTools(main,msg){main.append(el("h3",0,"Tools"));const jb=el("div");jb.id="jobbox";jb.style.display="none";main.append(jb,msg);
 if(!tData){main.append(el("div","empty","Loading..."));api("/api/tools").then(j=>{tData=j;if(layer==="settings"&&sCat==="tools")drawSettings()}).catch(()=>{});return}
 drawJob(tData.job);if(tData.job&&tData.job.state==="running")jobPoll();
 const t=tData;
 { const c=tCard("Free movies","Public-domain films and cartoons from the Internet Archive, saved into your Free Movies folder.");const box=el("div","chk"),cbs=[];
   t.free_sources.forEach((n,i)=>{const l=el("label"),cb=el("input");cb.type="checkbox";cb.checked=true;cbs.push(cb);l.append(cb,n);box.append(l)});
   const cnt=el("select");for(const n of[1,3,5,10]){const o=el("option",0,n+" from each list");o.value=n;if(n===3)o.selected=true;cnt.append(o)}
   const b=sBtn("Download",()=>runJob({name:"free",count:+cnt.value,lists:cbs.map((x,i)=>x.checked?i:-1).filter(i=>i>=0)},b),"pri");
   const row=el("div","sbar");row.append(cnt,b);c.append(box,row);main.append(c)}
 { const c=tCard("Bring in a folder or USB drive","Copies every video from it into your Inbox (your originals stay where they are) and files them onto channels.");
   const p=sInput("","text","For example  E:\\  or  D:\\Movies");p.style.width="34vw";const b=sBtn("Bring them in",()=>runJob({name:"import",path:p.value},b),"pri");
   const row=el("div","sbar");row.append(p,b);c.append(row);main.append(c)}
 { const c=tCard("Inbox",t.inbox_waiting?`${t.inbox_waiting} video(s) waiting in the Inbox.`:"The Inbox is empty.");const b=sBtn("Sort the Inbox now",()=>runJob({name:"sort"},b));
   const row=el("div","sbar");row.append(b);c.append(row);main.append(c)}
 { const c=tCard("Videos that are skipped",t.skipped.length?"These cannot play in the TV yet. Fixing makes a copy that plays (keeps the original); a picture problem can take 15-40 minutes for a movie.":"Every video can play.");
   for(const v of t.skipped.slice(0,12)){const row=el("div","sbar"),b=sBtn("Fix",()=>runJob({name:"fix",media_id:v.id},b));row.append(b,el("span",0,v.title+" - "+v.why));c.append(row)}
   if(t.skipped.length>12)c.append(el("small",0,`...and ${t.skipped.length-12} more. Fix these first, then come back.`));main.append(c)}
 { const c=tCard("Sound language","For a video with more than one language: choose which one it plays.");const q=sInput("","text","Type part of the title");q.style.width="30vw";const res=el("div","pickl");
   let qt;q.addEventListener("input",()=>{clearTimeout(qt);qt=setTimeout(async()=>{res.textContent="";if(q.value.trim().length<2)return;
    const j=await api("/api/library?view=all&q="+encodeURIComponent(q.value.trim()));for(const it of j.items.slice(0,6)){const b=sBtn(label(it),async()=>{res.textContent="";res.append(el("small",0,"Reading its sound tracks..."));
     const a=await api("/api/audio/"+it.id);res.textContent="";if(a.tracks.length<2){res.append(el("small",0,"This video has only one sound track - nothing to choose."));return}
     for(const tr of a.tracks){const tb=sBtn((tr.language||tr.lang||"Unknown")+(tr.title?" - "+tr.title:"")+(tr.n===a.playing?"  (plays now)":""),()=>runJob({name:"audio",media_id:it.id,track:tr.n},tb));if(tr.n===a.playing)tb.disabled=true;res.append(tb)}});res.append(b)}},350)});
   c.append(q,res);main.append(c)}
 { const c=tCard("iPhone-friendly copies",t.not_phone?`${t.not_phone} video(s) cannot play on an iPhone as they are (usually .mkv files). This makes .mp4 copies that play on phones, the PC and over AirPlay - normally quick, because the picture is copied, not re-encoded. Originals are kept, and so are resume points and favorites.`:"Every video can play on an iPhone.");
   if(t.not_phone){const b=sBtn("Make iPhone-friendly copies",()=>runJob({name:"phone"},b),"pri");const row=el("div","sbar");row.append(b);c.append(row)}main.append(c)}
 { const c=tCard("Free up space",t.originals_bytes?`Original copies kept after fixing or shrinking videos use ${gb(t.originals_bytes)}. Delete them once you are happy with the new versions. This is permanent.`:"No original copies are being kept.");
   if(t.originals_bytes){const b=sBtn("Delete the originals",()=>{if(!c.dataset.sure){c.dataset.sure=1;sMsg(`Press again to permanently delete ${gb(t.originals_bytes)} of original copies.`,"err");return}delete c.dataset.sure;runJob({name:"clean"},b)},"warn");const row=el("div","sbar");row.append(b);c.append(row)}main.append(c)}
 { const c=tCard("This PC",t.ffmpeg?"Video tools (ffmpeg) are installed.":"Video tools (ffmpeg) are missing: needed to read, fix and convert videos.");const row=el("div","sbar");
   if(!t.ffmpeg){const b=sBtn("Install video tools",()=>runJob({name:"ffmpeg"},b),"pri");row.append(b)}
   const b2=sBtn("Check setup",()=>runJob({name:"check"},b2));row.append(b2);
   if(t.windows){const b3=sBtn("Make a desktop shortcut",()=>runJob({name:"shortcut"},b3));row.append(b3)}c.append(row);main.append(c)}}
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
 if(d.enabled){
  { const c=tCard("On the phone, open this address",d.addresses.length?"Type it into Safari or Chrome while the phone is on the same WiFi as this PC.":"This PC does not seem to be on a home network right now.");
    for(const a of d.addresses){const b=el("b",0,a);b.style.fontSize="calc(3vh*var(--tx))";b.style.userSelect="all";c.append(b)}
    if(d.qr){const q=el("div");q.id="phone-qr";q.innerHTML=d.qr;q.style.cssText="width:22vh;height:22vh;background:#fff;padding:1vh;border-radius:1vh";
     q.firstChild.setAttribute("width","100%");q.firstChild.setAttribute("height","100%");c.append(el("small",0,"Or open the iPhone's Camera and point it at this code, then tap the link that appears:"),q)}
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
 if(!chList){main.append(el("div","empty","Loading channels..."));api("/api/channels-config").then(j=>{chList=j.channels;if(layer==="settings"&&sCat==="chan")drawSettings()}).catch(()=>{main.textContent="";main.append(el("div","empty","Channels could not be loaded."))});return}
 if(chSel===null){main.append(el("small",0,"Click a channel to rename it, change its colour, folder or keywords. Changes show up in the guide straight away."));
  { const sc=el("input");sc.type="checkbox";sc.checked=sData&&sData.seasonal!==false;
    sc.onchange=async()=>{try{await pj("/api/settings",{seasonal:sc.checked});sData=await api("/api/settings");toast(sc.checked?"Seasonal specials on":"Seasonal specials off")}catch(e){sMsg(String(e.message||e),"err")}};
    const l=el("label","lb");l.append(sc," Seasonal specials");l.style.display="flex";l.style.gap="1vw";
    const list=(sData&&sData.seasonal_list||[]).map(x=>`${x.name} (${x.dates.replace("..", " to ")}, ${x.from}-${x.to})`).join("; ");
    main.append(sField("",(list?list+". ":"")+"Extra programming on Hero Marathon at certain times of year. If you have nothing that fits, the channel plays as usual.",l))}
  for(const c of chList){const b=el("button","chrow");b.type="button";const dot=el("i");dot.style.background=c.color;b.append(dot,el("b",0,String(c.number)),el("span",0,c.name),el("small",0,c.summary));b.onclick=()=>{chSel=c.id;drawSettings();$("#st-main").scrollTop=0};main.append(b)}
  const bar=el("div","sbar");bar.append(sBtn("Add a channel",()=>{chSel="new";drawSettings()},"pri"));main.append(bar,msg);return}
 const isNew=chSel==="new",c=isNew?{id:"",number:"",name:"",color:"#ffcf1f",mode:"sequential",description:"",kind:"tv",folder:"",keywords:[],shared_keywords:0,special:false,summary:""}:chList.find(x=>x.id===chSel);
 if(!c){chSel=null;return drawChannelsCfg(main,msg)}
 main.firstChild.textContent=isNew?"New channel":"Edit channel: "+c.name;
 const name=sInput(c.name),num=sInput(c.number,"text",isNew?"automatic":"");num.size=6;let col=c.color;
 const sw=el("div","sw"),hex=sInput(col,"text","#ffcf1f");hex.size=9;
 const pick=x=>{col=x;sDirty=true;sLeave=false;[...sw.children].forEach(b=>b.classList.toggle("on",b.dataset.c.toLowerCase()===x.toLowerCase()));hex.value=x};
 hex.addEventListener("input",()=>{if(/^#[0-9a-fA-F]{6}$/.test(hex.value))pick(hex.value)});
 for(const x of SW){const b=el("button",x.toLowerCase()===col.toLowerCase()?"on":"");b.type="button";b.dataset.c=x;b.style.background=x;b.title=x;b.setAttribute("aria-label","Colour "+x);b.onclick=()=>pick(x);sw.append(b)}
 main.append(sField("Channel name","Shown in the guide and when you change channel.",name),sField("Channel number","The number you type to tune it. Each channel needs its own.",num),sField("Colour",null,sw),sField("",null,hex,true));
 let mode=null;if(c.kind!=="weather"){mode=el("select");for(const[v,t]of[["sequential","In order (episodes and movies one after another)"],["shuffle","Shuffled (a different order each time)"]]){const o=el("option",0,t);o.value=v;if(v===c.mode)o.selected=true;mode.append(o)}mode.onchange=()=>{sDirty=true;sLeave=false};main.append(sField("Play order",null,mode))}
 let folder=null,words=null,desc=null;
 if(c.kind!=="weather"){
  if(isNew||c.folder){folder=sInput(isNew?"":c.folder,"text",isNew?"same as the name":"");folder.style.width="30vw";main.append(sField("Folder","Videos in this folder (inside your media folder) play on this channel."+(isNew?" It is created for you.":" Renaming it does not move videos already in the old folder."),folder))}
  else main.append(sField("What it shows",c.summary+" - these special rules are kept as they are. They can be changed in config\\channels.json.",null));
  words=el("textarea");words.value=c.keywords.join("\n");words.placeholder="one per line, for example:\niron man\navengers";words.addEventListener("input",()=>{sDirty=true;sLeave=false});
  main.append(sField("Keywords","When new videos arrive in the Inbox (or you use Sort-Movies), a file whose name contains one of these words goes on this channel. One per line."+(c.shared_keywords?` ${c.shared_keywords} more keywords are shared with other channels and are not shown here.`:""),words))}
 desc=sInput(c.description);desc.style.width="50vw";main.append(sField("Description","One line shown in the guide.",desc));
 const bar=el("div","sbar"),payload=()=>{const b={name:name.value,color:col,description:desc.value};if(num.value.trim()!=="")b.number=num.value.trim();if(mode)b.mode=mode.value;if(folder&&(isNew||folder.value.trim()))b.folder=folder.value;if(words)b.keywords=words.value;return b};
 bar.append(sBtn(isNew?"Create channel":"Save",()=>isNew?chPost(Object.assign({op:"add"},payload()),"Channel created.",true):chPost(Object.assign({op:"save",id:c.id},payload()),"Saved."),"pri"),sBtn("Back to the list",()=>{if(sDirty&&!sLeave){sLeave=true;toast("You have unsaved changes. Choose again to discard them, or press Save.");return}chBack()}));
 if(!isNew)bar.append(sBtn("Delete this channel",()=>{if(!bar.dataset.sure){bar.dataset.sure=1;sMsg("Press Delete again to remove this channel from the guide. Your videos are not touched.","err");return}chPost({op:"delete",id:c.id},"Channel deleted.",true)},"warn"));
 main.append(bar,msg)}
function sGo(k){if(sDirty&&!sLeave){sLeave=true;toast("You have unsaved changes. Choose again to discard them, or press Save.");return}sDirty=false;sLeave=false;sCat=k;chSel=null;if(k==="chan")chList=null;if(k==="tools")tData=null;if(k==="devices")dData=null;drawSettings();$("#st-main").scrollTop=0}
function closeSettings(){show("#settings",false);layer="";sDirty=false;sLeave=false}
function settingsKey(e){const k=e.key;
 if(k==="Escape"){e.preventDefault();if(sDirty&&!sLeave){sLeave=true;return toast("You have unsaved changes. Press Esc again to leave without saving.")}if(sCat==="chan"&&chSel!==null)return chBack();return openHome()}
 if((k==="ArrowRight"||k==="ArrowLeft")&&document.activeElement&&document.activeElement.closest&&document.activeElement.closest("#st-nav")){e.preventDefault();const ks=SCATS.map(x=>x[0]),i=ks.indexOf(sCat),n=ks[(i+(k==="ArrowRight"?1:-1)+ks.length)%ks.length];sGo(n);const b=$("#st-nav .on");if(b)b.focus()}}
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
function closeNews(){show("#news",false);if($("#news").dataset.kind==="welcome")post("/api/welcome",{});else post("/api/whatsnew",{});$("#news").dataset.kind=""}
function showWelcome(w){const nw=$("#news");nw.dataset.kind="welcome";paint(nw,theme.color);$("#nw-h").textContent="Welcome to "+theme.name;const ul=$("#nw-l");ul.textContent="";
 for(const l of[w.media?`${w.media} video(s) found so far - they are already on your channels.`:"No videos yet: drag movies or shows onto this window, or put them in the Inbox folder.",
  "Press H (or Esc) for the Home menu, G for the TV guide, L for the library.",
  "Press O for Settings: name your station, pick its colour, add free movies, posters and more.",
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
 try{const h=await api("/api/health");if(h.api!==NEED_API)toast(h.frozen?"The HERO TV application is older than its files. Close it, then double-click Build-App.bat in the HERO TV folder (a few minutes) to bring it up to date.":"HERO TV is an older version than this page. Close it completely and start it again to get the newest features.")}catch(e){}
 try{theme=Object.assign(theme,await api("/api/theme"));document.title=theme.name;root.style.setProperty("--brand",theme.color);applyCues(theme.subs)}catch(e){}
 let pf={};try{pf=await api("/api/prefs")}catch(e){}
 if(typeof pf.volume==="number")v.volume=pf.volume;if("muted" in pf)v.muted=!!pf.muted;if(pf.bigtext)setBig(true,false);if(typeof pf.subs==="string")subPref=pf.subs;
 let i=pf.channel!=null?chans.findIndex(c=>c.number===pf.channel):-1;if(i<0)i=chans.findIndex(c=>c.id===localStorage.getItem("ch"));tune(i<0?0:i);pollAlerts();
 try{if(!localStorage.getItem("homeHint")){localStorage.setItem("homeHint","1");setTimeout(()=>toast("Tip: press H for the home menu, or ? for help"),6000)}}catch(e){}})();
})();
