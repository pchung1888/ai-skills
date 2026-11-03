/* personal-htsw walk page behavior. The page reads fine without this script:
   links, chart, glossary popovers and check-yourself boxes are plain HTML.
   This adds theme, you-are-here, seen marks, progress, comments, Respond,
   present mode and anime.js motion. ASCII only. */
(function(){
  "use strict";
  var D=document,root=D.documentElement,CFG=window.WALK||{steps:[],key:"walk"};
  var KEY=CFG.key||"walk";
  function $(s,c){return (c||D).querySelector(s)}
  function $$(s,c){return Array.prototype.slice.call((c||D).querySelectorAll(s))}
  function load(k,d){try{var v=localStorage.getItem(KEY+":"+k);return v?JSON.parse(v):d}catch(e){return d}}
  function save(k,v){try{localStorage.setItem(KEY+":"+k,JSON.stringify(v))}catch(e){}}
  var reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  var A=(!reduce&&window.anime&&window.anime.animate)?window.anime:null;

  /* Theme picker: Auto / Light / Dark. */
  var tb=$$(".pill button[data-t]");
  function setT(t){if(t==="auto")root.removeAttribute("data-theme");else root.setAttribute("data-theme",t);
    tb.forEach(function(b){b.setAttribute("aria-pressed",b.getAttribute("data-t")===t?"true":"false")});save("theme",t)}
  setT(load("theme","auto"));tb.forEach(function(b){b.addEventListener("click",function(){setT(b.getAttribute("data-t"))})});

  var STEPS=CFG.steps||[],secs=$$("main section.sec"),stepIds=STEPS.map(function(s){return s[0]});

  /* Seen marks: a step counts as opened once its section was on screen or linked to. */
  var DWELL_MS=4000; /* how long a section stays on screen before it counts as read */
  var seen=load("seen",{}),manual={}; /* manual: steps the reader unchecked in this page load; dwell skips them */
  var progI=$(".prog i"),whereB=$(".where");
  function paint(){
    $$("a.st, nav.mf .mini a").forEach(function(a){var id=(a.getAttribute("href")||"").slice(1);a.classList.toggle("seen",!!seen[id])});
    var n=stepIds.filter(function(id){return seen[id]}).length;
    if(progI)progI.style.width=(STEPS.length?Math.round(100*n/STEPS.length):0)+"%";
    if(whereB)whereB.setAttribute("data-seen",n);
    $$("nav.mf .seen-tog").forEach(function(b){var id=b.getAttribute("data-step"),on=!!seen[id];
      b.setAttribute("aria-pressed",on?"true":"false");b.setAttribute("aria-label","Mark step "+(stepIds.indexOf(id)+1)+(on?" as not read":" as read"))});
  }
  function markSeen(id,auto){if(stepIds.indexOf(id)<0)return;if(auto){if(manual[id])return}else delete manual[id];if(seen[id])return;seen[id]=1;save("seen",seen);paint()}
  function setSeen(id,on){if(on){seen[id]=1;delete manual[id]}else{delete seen[id];manual[id]=1}save("seen",seen);paint()}
  $$("nav.mf .seen-tog").forEach(function(b){b.addEventListener("click",function(){var id=b.getAttribute("data-step");setSeen(id,!seen[id])})});
  /* Reset progress: first click asks, second click within 4 s clears only the seen marks. */
  var rst=$("#reset-prog"),rstT=0;
  function rstBack(){clearTimeout(rstT);rstT=0;if(rst)rst.textContent="Reset progress"}
  if(rst)rst.addEventListener("click",function(){
    if(!rstT){rst.textContent="Click again to reset";rstT=setTimeout(rstBack,4000);return}
    rstBack();try{localStorage.removeItem(KEY+":seen")}catch(e){}seen={};manual={};paint()});
  paint();
  function fromHash(){var h=location.hash.slice(1);if(h)markSeen(h,false)}
  window.addEventListener("hashchange",fromHash);fromHash();

  /* You are here: yellow on the menu entry and chart box of the section on screen. */
  var navLinks=$$("nav.mf a"),boxes=$$("a.st"),curId="";
  function setCur(id){if(id===curId)return;curId=id;
    navLinks.forEach(function(a){a.classList.toggle("cur",a.getAttribute("href")==="#"+id)});
    boxes.forEach(function(a){a.classList.toggle("cur",a.getAttribute("href")==="#"+id)});
    var k=stepIds.indexOf(id);
    if(whereB){if(k>=0)whereB.innerHTML='<span class="wf">Step <b>'+(k+1)+"</b> of "+STEPS.length+'</span><span class="wc"><b>'+(k+1)+"</b>/"+STEPS.length+"</span>";else{var hh=$("#"+id+" h2");whereB.innerHTML="";var wf=D.createElement("span");wf.className="wf";wf.textContent=hh?(hh.getAttribute("data-name")||hh.textContent):"";whereB.appendChild(wf)}}
    var on=$("nav.mf a.cur");if(on&&window.innerWidth>860){var nv=$("nav.mf"),r=on.offsetTop;
      if(r<nv.scrollTop+40||r>nv.scrollTop+nv.clientHeight-60)nv.scrollTo({top:r-nv.clientHeight/2,behavior:reduce?"auto":"smooth"})}
    if(A&&on)an(on,{scale:[1.06,1],duration:420,ease:"outBack(2)"});
  }
  var dwell={};
  if("IntersectionObserver" in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){var id=e.target.id;
      if(e.isIntersecting){setCur(id);dwell[id]=setTimeout(function(){markSeen(id,true)},DWELL_MS)}
      else clearTimeout(dwell[id])})},{rootMargin:"-30% 0px -60% 0px"});
    secs.forEach(function(s){io.observe(s)});
  }

  /* One click handler for Back links, chart boxes and (in present mode) every in-page link.
     It never blocks the browser: modified clicks and chart boxes keep their normal jump. */
  function pulse(b){if(!A)return;var bx=b.querySelector(".bx");
    if(bx)an(bx,{strokeWidth:[6,1.5],duration:900,ease:"outQuad"});else an(b,{scale:[1.04,1],duration:500,ease:"outQuad"})}
  D.addEventListener("click",function(e){
    if(e.defaultPrevented||e.button||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;
    var a=e.target.closest&&e.target.closest("a[href]");if(!a)return;
    var href=a.getAttribute("href")||"",back=a.getAttribute("data-back");
    if(back){e.preventDefault();goTo("box-"+back,true);return}
    if(a.classList.contains("st"))pulse(a);
    if(href.charAt(0)==="#"&&href.length>1&&D.body.classList.contains("presenting")&&D.getElementById(href.slice(1))){e.preventDefault();goTo(href.slice(1))}
  });

  /* Comments: per section, kept in this browser until Respond copies them out. */
  var C=load("comments",{});
  secs.forEach(function(s){
    var d=D.createElement("div");d.className="cm";
    d.innerHTML='<button type="button" class="cbtn" aria-expanded="false">+ Comment</button><div class="cedit" hidden><div class="btns"><button type="button" class="csave">Save comment</button><button type="button" class="sec cdel">Delete</button></div></div><div class="csaved"></div>';
    var tx=D.createElement("textarea");tx.setAttribute("data-s",s.id);tx.setAttribute("aria-label","Comment on this section");$(".cedit",d).insertBefore(tx,$(".btns",d));
    var w=$(".walk",s);if(w)s.insertBefore(d,w);else s.appendChild(d);
    var ed=$(".cedit",d),ta=$("textarea",d),sv=$(".csaved",d),bt=$(".cbtn",d),navs=$$('nav.mf a[href="#'+s.id+'"]');
    function show(){var t=C[s.id]||"";ta.value=t;sv.textContent=t?"Saved comment: "+t:"";navs.forEach(function(a){a.classList.toggle("has-c",!!t)})}
    bt.addEventListener("click",function(){ed.hidden=!ed.hidden;bt.setAttribute("aria-expanded",String(!ed.hidden));if(!ed.hidden)ta.focus()});
    $(".csave",d).addEventListener("click",function(){var t=ta.value.trim();if(t)C[s.id]=t;else delete C[s.id];save("comments",C);show();ed.hidden=true;bt.setAttribute("aria-expanded","false");
      if(A)an(sv,{opacity:[0,1],translateY:[6,0],duration:400})});
    $(".cdel",d).addEventListener("click",function(){delete C[s.id];save("comments",C);show();ed.hidden=true});
    show();
  });

  /* Answer sheet: answered count, Other boxes, Respond. */
  var form=$("#qform"),qs=$$("fieldset.q"),qc=$(".qcount");
  function count(){var n=0;qs.forEach(function(q){var r=$("input[type=radio]:checked",q),o=$("input.other-in, input.free",q);
      var ok=r?(r.value!=="other"||(o&&o.value.trim())):(o&&o.value.trim());q.classList.toggle("answered",!!ok);if(ok)n++});
    if(qc)qc.textContent=n+" of "+qs.length+" answered"}
  qs.forEach(function(q){$$("input[type=radio]",q).forEach(function(r){r.addEventListener("change",function(){
      var o=$("input.other-in",q);if(o){o.hidden=r.value!=="other";if(!o.hidden)o.focus()}count()})});
    $$("input[type=text]",q).forEach(function(t){t.addEventListener("input",count)})});
  count();
  var out=$("#out"),st=$("#status"),rb=$("#respond");
  if(rb)rb.addEventListener("click",function(){
    var L=[CFG.respondTitle||D.title,"Date: "+new Date().toLocaleDateString("en-US",{timeZone:"America/New_York"}),""];
    qs.forEach(function(q,i){
      var title=q.getAttribute("data-title"),ask=q.getAttribute("data-ask"),a,r=$("input[type=radio]:checked",q),o=$("input.other-in, input.free",q);
      var ov=o?o.value.trim():"";
      if($("input[type=radio]",q)){a=!r?"(no answer)":r.value==="other"?"Other: "+(ov||"(no answer)"):r.getAttribute("data-text")}
      else a=ov||"(no answer)";
      var n=$("input.note",q),nv=n?n.value.trim():"";
      L.push((i+1)+". "+title+" - "+ask);L.push("   Answer: "+a);if(nv)L.push("   Note: "+nv);L.push("");
    });
    var nc=0;L.push("Comments by section");
    secs.forEach(function(s){if(C[s.id]){nc++;var h=$("h2",s);L.push("- "+(h?h.getAttribute("data-name")||h.textContent:s.id)+": "+C[s.id])}});
    if(!nc)L.push("(no comments saved)");
    var unsaved=$$(".cm textarea").some(function(t){return t.value.trim()!==(C[t.getAttribute("data-s")]||"")});
    out.value=L.join("\n");
    var tail=" "+nc+" saved comment(s) included."+(unsaved?" Warning: some comment text is typed but not saved.":"");
    function done(msg){st.textContent=msg+tail;if(A){an(rb,{scale:[1,1.12,1],duration:500,ease:"outBack(3)"});burst(rb)}}
    function fallback(){out.select();var ok=false;try{ok=D.execCommand("copy")}catch(e){}
      st.textContent=(ok?"Copied to clipboard.":"Copy failed: select the text below and copy it.")+tail;if(ok&&A)burst(rb)}
    if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(out.value).then(function(){done("Copied to clipboard.")},fallback);
    else fallback();
  });
  var cl=$("#clear");if(cl)cl.addEventListener("click",function(){form.reset();out.value="";st.textContent="";$$("input.other-in").forEach(function(x){x.hidden=true});count()});
  function burst(el){if(!A)return;var r=el.getBoundingClientRect(),i,dots=[];
    for(i=0;i<14;i++){var p=D.createElement("i");p.style.cssText="position:fixed;z-index:60;width:8px;height:8px;border-radius:99px;pointer-events:none;left:"+(r.left+r.width/2)+"px;top:"+(r.top+r.height/2)+"px;background:"+(i%2?"var(--hi)":"var(--ok)");D.body.appendChild(p);dots.push(p)}
    an(dots,{translateX:function(){return A.utils.random(-90,90)},translateY:function(){return A.utils.random(-80,30)},opacity:[1,0],scale:[1,.3],duration:800,ease:"outExpo",onComplete:function(){dots.forEach(function(p){p.remove()})}})}

  /* Present mode: one section at a time, arrow keys or the dots to move. */
  var pb=$("#present"),order=secs.filter(function(s){return !s.classList.contains("ref-sec")}),pi=0,dotsBox=$(".pdots");
  var pcount=null;
  if(dotsBox){
    var pv=D.createElement("button");pv.type="button";pv.className="pnav";pv.textContent="Prev";pv.setAttribute("aria-label","Previous section");pv.addEventListener("click",function(){go(pi-1)});dotsBox.appendChild(pv);
    pcount=D.createElement("span");pcount.className="pcount";dotsBox.appendChild(pcount);
    var nx=D.createElement("button");nx.type="button";nx.className="pnav";nx.textContent="Next";nx.setAttribute("aria-label","Next section");nx.addEventListener("click",function(){go(pi+1)});dotsBox.appendChild(nx);
    order.forEach(function(s,i){var b=D.createElement("button");b.type="button";b.className="pd";b.setAttribute("aria-label","Go to "+(($("h2",s)||{}).textContent||s.id));b.addEventListener("click",function(){go(i)});dotsBox.insertBefore(b,pcount)})}
  function go(i){pi=Math.max(0,Math.min(order.length-1,i));order.forEach(function(s,j){s.classList.toggle("on",j===pi)});
    $$(".pd",dotsBox).forEach(function(b,j){b.classList.toggle("on",j===pi)});if(pcount)pcount.textContent=(pi+1)+"/"+order.length;
    order[pi].classList.remove("rv");
    history.replaceState(null,"","#"+order[pi].id);setCur(order[pi].id);markSeen(order[pi].id);window.scrollTo(0,0);
    if(A)an(order[pi],{opacity:[0,1],translateY:[24,0],duration:450,ease:"outExpo"});
    var hd=$("h2",order[pi]);if(hd){hd.setAttribute("tabindex","-1");try{hd.focus({preventScroll:true})}catch(x){}}}
  function present(on){D.body.classList.toggle("presenting",on);if(pb)pb.setAttribute("aria-pressed",String(on));
    if(on){var h=location.hash.slice(1),k=0;order.forEach(function(s,j){if(s.id===h)k=j});go(k)}
    else{order.forEach(function(s){s.classList.remove("on");s.style.opacity="";s.style.transform=""});var c=D.getElementById(curId);if(c)c.scrollIntoView()}}
  if(pb)pb.addEventListener("click",function(){present(!D.body.classList.contains("presenting"))});
  /* goTo: the one navigation function. In present mode it shows the section that holds the
     target (a section, a question like q3, or a chart box), then scrolls to and focuses it. */
  function shown(e){return !!e&&e.getClientRects().length>0}
  function goTo(id,fromBack){
    var el=D.getElementById(id),m=/^box-(.+)$/.exec(id);if(!el&&m)el=D.getElementById("pbox-"+m[1]);if(!el)return;
    var sec=el.closest("main section.sec");
    if(D.body.classList.contains("presenting")){
      var k=sec?order.indexOf(sec):-1;
      if(k>=0)go(k);else present(false)}
    if(m&&!shown(el)){var alt=D.getElementById(el.id==="box-"+m[1]?"pbox-"+m[1]:"box-"+m[1]);if(shown(alt))el=alt}
    var box=!!m;
    el.scrollIntoView({behavior:reduce?"auto":"smooth",block:box?"center":"start"});
    if(fromBack||D.body.classList.contains("presenting"))history.replaceState(null,"",fromBack?"#flow":"#"+id);
    if(!/^(A|BUTTON|INPUT|TEXTAREA|SELECT)$/.test(el.tagName)&&!el.hasAttribute("tabindex"))el.setAttribute("tabindex","-1");
    try{el.focus({preventScroll:true})}catch(x){}
    if(box)setTimeout(function(){pulse(el)},450);
  }
  window.addEventListener("hashchange",function(){if(D.body.classList.contains("presenting")){var h=location.hash.slice(1);if(h)goTo(h)}});
  D.addEventListener("keydown",function(e){
    if(e.ctrlKey||e.metaKey||e.altKey)return;
    var tg=(e.target||{}).tagName||"";
    if(/INPUT|TEXTAREA|SELECT/.test(tg)||(e.target&&e.target.isContentEditable))return;
    var p=D.body.classList.contains("presenting"),own=/^(BUTTON|A|SUMMARY)$/.test(tg);
    if(p&&(e.key==="ArrowRight"||e.key==="PageDown"||(e.key===" "&&!own))){e.preventDefault();go(pi+1)}
    else if(p&&(e.key==="ArrowLeft"||e.key==="PageUp")){e.preventDefault();go(pi-1)}
    else if(p&&e.key==="Escape")present(false);
    else if(!p&&!own&&(e.key==="n"||e.key==="p")){
      var list=["intro","flow"].concat(stepIds,["answers"]),k=curId?list.indexOf(curId):-1;if(curId&&k<0)k=list.length;
      var t=list[e.key==="n"?k+1:k-1];if(t){e.preventDefault();setCur(t);location.hash=t}}
  });
  if(/[?&]present=1/.test(location.search))present(true);

  /* Glossary terms open on tap, click, Enter or Space. One is open at a time. A click elsewhere or Escape closes it. */
  function closeTerms(){var o=D.querySelectorAll(".term.open");for(var i=0;i<o.length;i++)o[i].classList.remove("open")}
  function hvGo(e){var l=e.target&&e.target.closest?e.target.closest(".hv-link"):null;if(l&&l.getAttribute("data-go")){e.preventDefault();var g=l.getAttribute("data-go");if(location.hash===g){var t=D.getElementById(g.slice(1));if(t)t.scrollIntoView()}else location.hash=g}}
  D.addEventListener("click",hvGo);
  D.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" ")hvGo(e)});
  D.addEventListener("click",function(e){
    var t=e.target&&e.target.closest?e.target.closest(".term"):null;
    var was=t&&t.classList.contains("open");closeTerms();
    if(t&&!was)t.classList.add("open")});
  D.addEventListener("keydown",function(e){
    if(e.key==="Escape")closeTerms();
    else if((e.key==="Enter"||e.key===" ")&&e.target&&e.target.classList&&e.target.classList.contains("term")){e.preventDefault();e.target.click()}});

  /* Motion with anime.js. Off when reduced motion is on, anime.js did not load or IntersectionObserver is missing.
     Hidden-before-animation states are CSS rules under .motion, so removing that class shows everything.
     Any motion error calls bail(), which removes the class and clears the inline styles motion set. */
  if(A&&!("IntersectionObserver" in window))A=null;
  if(!A)return;
  var HID=".rv, .hv-in, .hm-n, .hm-dec, .hm-out, .hm-cap, #flow svg .st, #flow svg .oc";
  var anims=new WeakMap(),revealed=new WeakSet(),split=null,ro=null;
  function clear(el){el.style.opacity="";el.style.transform=""}
  /* dashKeep and dashBack: remember and restore a hero path's own stroke-dasharray and stroke-dashoffset (a dashed path stays dashed). */
  var dashKeep=new WeakMap();
  function dashBack(p){var k=dashKeep.get(p)||["",""];p.style.strokeDasharray=k[0];p.style.strokeDashoffset=k[1]}
  function bail(){
    A=null;root.classList.remove("motion");
    $$(HID).forEach(function(el){el.classList.remove("rv");clear(el)});
    try{if(split)split.revert()}catch(e){}
    var h1b=$(".hero h1");if(h1b)$$("*",h1b).forEach(clear);
    var hr0=$(".hm-reveal");if(hr0){hr0.style.strokeDasharray="";hr0.style.strokeDashoffset=""}
    $$(".hv-draw").forEach(function(p){dashBack(p)});
  }
  /* an: animate that turns any anime.js error into bail(). Also serves the you-are-here, pulse and burst calls. */
  function an(t,p){if(!A)return null;try{return A.animate(t,p)}catch(e){bail();return null}}
  /* show: reveal one section now, no animation. */
  function show(el){if(!el)return;var a=anims.get(el);if(a)try{a.pause()}catch(e){}
    el.classList.remove("rv");clear(el);revealed.add(el);if(ro)ro.unobserve(el)}
  function reveal(id){var el=id&&D.getElementById(id);if(el)show(el.closest("main section.sec"))}
  D.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("a[href^='#']");if(a)reveal((a.getAttribute("href")||"").slice(1))},true);
  window.addEventListener("hashchange",function(){reveal(location.hash.slice(1))});
  /* Fallback: 1.5 s after load, anything still hidden and on screen is shown. */
  function rescue(){$$(HID).forEach(function(el){if(anims.has(el))return;var r=el.getBoundingClientRect();
    if(r.bottom>0&&r.top<innerHeight&&parseFloat(getComputedStyle(el).opacity)<.5){el.classList.remove("rv");el.style.opacity="1";el.style.transform="none"}})}
  if(D.readyState==="complete")setTimeout(rescue,1500);else window.addEventListener("load",function(){setTimeout(rescue,1500)});
  try{
    root.classList.add("motion");
    var st2=A.stagger;
    // Hero: every text is readable within 500 ms. The title rises word by word, then the rest follows.
    var h1=$(".hero h1");
    if(h1&&A.splitText){try{split=A.splitText(h1,{words:{wrap:"clip"}});A.animate(split.words,{y:["110%","0%"],duration:500,delay:st2(40),ease:"outExpo"})}catch(e){}}
    A.animate(".hero .rv",{opacity:[0,1],translateY:[12,0],duration:400,delay:st2(40),ease:"outExpo"});
    // Hero map (decoration, may finish later): dots and labels rise, then the dashed path draws once.
    var hm=$(".hero-map");
    if(hm&&hm.classList.contains("hero-vis")){
      // Hero picture (carries the idea): shapes marked hv-in rise in with a 40 ms stagger (total 500 ms at most); labels stay visible. Paths marked hv-draw draw once in 900 ms.
      var hin=$$(".hv-in",hm);
      if(hin.length&&hm.offsetParent!==null)A.animate(hin,{opacity:[0,1],translateY:[8,0],duration:300,delay:st2(Math.min(40,200/Math.max(hin.length-1,1))),ease:"outExpo",onComplete:function(){hin.forEach(clear)}});
      $$(".hv-draw",hm).forEach(function(p){if(!p.getTotalLength)return;var l=p.getTotalLength();dashKeep.set(p,[p.style.strokeDasharray,p.style.strokeDashoffset]);p.style.strokeDasharray=l;p.style.strokeDashoffset=l;
        A.animate(p,{strokeDashoffset:[l,0],duration:900,ease:"inOutSine",onComplete:function(){dashBack(p)}})})
    }else if(hm&&hm.offsetParent!==null){
      A.animate($$(".hm-n, .hm-dec, .hm-out, .hm-cap",hm),{opacity:[0,1],translateY:[8,0],duration:350,delay:st2(40,{start:150}),ease:"outExpo"});
      var hr=$(".hm-reveal",hm);
      if(hr&&hr.getTotalLength){var hl=hr.getTotalLength();hr.style.strokeDasharray=hl;hr.style.strokeDashoffset=hl;
        A.animate(hr,{strokeDashoffset:[hl,0],duration:900,delay:300,ease:"inOutSine"})}
    }
    // Sections reveal once as they enter the screen: one fade per section, nothing inside it.
    ro=new IntersectionObserver(function(es){es.forEach(function(e){var t=e.target;if(!e.isIntersecting||revealed.has(t))return;
      revealed.add(t);ro.unobserve(t);
      var a=an(t,{opacity:[0,1],translateY:[10,0],duration:380,ease:"outQuad",onComplete:function(){t.classList.remove("rv");clear(t)}});
      if(a)anims.set(t,a);else show(t)})},{rootMargin:"0px"});
    // The hash may name a section, a question, a chart box or any element inside a section: the section that holds it is the target.
    var hs=location.hash.slice(1),he=hs&&D.getElementById(hs),hsec=he&&he.closest("main section.sec");
    $$("main section.sec").forEach(function(s){if(s.id==="flow")return;
      if(s.getBoundingClientRect().bottom<0||s===hsec)return; // already above the screen, or the link target: no animation
      s.classList.add("rv");ro.observe(s)});
    // The chart draws in about 500 ms. A box starts by its index, an arrow follows its source box,
    // the decision diamond follows its incoming arrow, and the outcomes come together last.
    var chart=$("#flow svg");
    if(chart){
      var cio=new IntersectionObserver(function(es){if(!es[0].isIntersecting)return;cio.disconnect();
        try{
          var all=$$(".st",chart),dia=null,flowB=[];
          all.forEach(function(g){if($("polygon",g))dia=g;else flowB.push(g)});
          var gap=Math.min(30,120/Math.max(flowB.length-1,1)),bs=function(i){return i*gap};
          A.animate(flowB,{opacity:[0,1],translateY:[8,0],duration:200,delay:function(_,i){return bs(i)},ease:"outQuad"});
          var edges=$$(".flow-edge:not(.al-edge)",chart),dl=[],dd=[],lastIn=0,k;
          edges.forEach(function(el){var f=el.getAttribute("data-from"),d;
            if(f==="d"){d=null}else d=bs(+f||0)+60;dl.push(d);
            if(el.getAttribute("data-to")==="d")lastIn=Math.max(lastIn,d)});
          var diaAt=lastIn+100,outAt=diaAt+100;
          dl=dl.map(function(d,j){dd.push(d===null?120:220);return d===null?outAt:d});
          var dr=A.svg.createDrawable(edges);
          A.animate(dr,{draw:["0 0","0 1"],duration:function(_,i){return dd[i]},delay:function(_,i){return dl[i]},ease:"inOutQuad"});
          if(dia)A.animate(dia,{opacity:[0,1],translateY:[8,0],duration:140,delay:diaAt,ease:"outQuad"});
          A.animate($$(".oc",chart),{opacity:[0,1],translateY:[8,0],duration:120,delay:outAt,ease:"outQuad"});
        }catch(x){bail()}
      },{threshold:.15});
      cio.observe(chart);
    }
    // Menu entries slide in from the left on load.
    A.animate("nav.mf .mini li",{opacity:[0,1],translateX:[-12,0],duration:420,delay:st2(30,{start:300}),ease:"outQuad"});
  }catch(err){bail()}
})();
