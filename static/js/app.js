/* Lexara AI */

/* ═══════════════════════════════════════════════════════════════
   PARTICLE CANVAS — floating dots with connecting lines
   Purple (#8B5CF6) and Cyan (#22D3EE) palette
   ═══════════════════════════════════════════════════════════════ */
(function initParticles() {
  const canvas = document.getElementById("particleCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const COLORS = ["#8B5CF6", "#22D3EE", "#A78BFA", "#67E8F9"];
  const COUNT  = 55;
  const MAX_DIST = 130;
  let W, H, particles = [], raf;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function rand(min, max) { return Math.random() * (max - min) + min; }

  function createParticle() {
    return {
      x:  rand(0, W),
      y:  rand(0, H),
      vx: rand(-0.35, 0.35),
      vy: rand(-0.35, 0.35),
      r:  rand(1.2, 2.8),
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      alpha: rand(0.3, 0.7),
    };
  }

  function init() {
    resize();
    particles = Array.from({ length: COUNT }, createParticle);
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    // Draw connecting lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MAX_DIST) {
          const opacity = (1 - dist / MAX_DIST) * 0.18;
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          // Blend between the two particle colors
          const grad = ctx.createLinearGradient(
            particles[i].x, particles[i].y,
            particles[j].x, particles[j].y
          );
          grad.addColorStop(0, particles[i].color);
          grad.addColorStop(1, particles[j].color);
          ctx.strokeStyle = grad;
          ctx.globalAlpha = opacity;
          ctx.lineWidth = 0.8;
          ctx.stroke();
        }
      }
    }

    // Draw dots
    particles.forEach(p => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.globalAlpha = p.alpha;
      ctx.fill();
    });

    ctx.globalAlpha = 1;
  }

  function update() {
    particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      // Wrap around edges
      if (p.x < -10) p.x = W + 10;
      if (p.x > W + 10) p.x = -10;
      if (p.y < -10) p.y = H + 10;
      if (p.y > H + 10) p.y = -10;
    });
  }

  function loop() {
    update();
    draw();
    raf = requestAnimationFrame(loop);
  }

  window.addEventListener("resize", () => {
    resize();
    // Redistribute particles on resize
    particles.forEach(p => {
      if (p.x > W) p.x = rand(0, W);
      if (p.y > H) p.y = rand(0, H);
    });
  });

  init();
  loop();
})();

/* ═══════════════════════════════════════════════════════════════ */

marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try { return hljs.highlight(code, {language: lang}).value; } catch(e) {}
    }
    return hljs.highlightAuto(code).value;
  }
});

let currentUser=null,currentChatId=null,docsLoaded=false,isStreaming=false;
let selectedFiles=[],allDocuments=[],selectedDocId=null;

const chatWin=document.getElementById("chatWindow"),qInput=document.getElementById("questionInput"),askBtn=document.getElementById("askBtn");
const sDot=document.getElementById("statusDot"),sTxt=document.getElementById("statusText"),chatTitle=document.getElementById("chatTitle");
const chatHist=document.getElementById("chatHistory"),dropZone=document.getElementById("dropZone"),fileInput=document.getElementById("fileInput");
const fileList=document.getElementById("fileList"),uploadBtn=document.getElementById("uploadBtn"),upLoader=document.getElementById("uploadLoader");
const upBtnTxt=document.getElementById("uploadBtnText"),upStatus=document.getElementById("uploadStatus");
const docsCard=document.getElementById("docsCard"),docListSB=document.getElementById("docListSidebar"),chunkInfo=document.getElementById("chunkInfo");
const smartCard=document.getElementById("smartCard"),smartOut=document.getElementById("smartOutput");

(async()=>{
  try {
    await loadUser();
    // Purge stale vectors FIRST, then load everything else
    try { await api('/api/purge-stale-vectors', {method:'POST'}); } catch(e) {}
    await Promise.all([loadChats(), loadDocuments()]);
    setupResize();
  } catch(e) {
    console.error('Init error:', e);
  }
})();

async function loadUser(){
  try{
    const r = await api("/api/auth/me");
    if(!r.ok){ location.href="/login"; return; }
    const d = await r.json();
    currentUser = d.user;
    const name = currentUser.name || "User";
    document.getElementById("userName").textContent  = name;
    document.getElementById("userEmail").textContent = currentUser.email || "";
    document.getElementById("userAvatar").textContent = name[0].toUpperCase();
  } catch(e) {
    console.error("loadUser failed:", e);
    location.href="/login";
  }
}
function api(url,opts={}){return fetch(url,{credentials:"include",...opts});}
function setStatus(s,t){sDot.className="sdot "+s;sTxt.textContent=t;}
function switchView(v){
  document.querySelectorAll(".view").forEach(el=>el.classList.add("hidden"));
  document.querySelectorAll(".sb-item").forEach(el=>el.classList.remove("active"));
  document.getElementById("view-"+v).classList.remove("hidden");
  document.querySelector(`[data-view="${v}"]`).classList.add("active");
  if(v==="analytics")loadAnalytics();
  if(v==="documents")renderDocGrid();
  if(v==="workspaces")loadWorkspaces();
  if(v==="activity")loadActivity();
}

async function loadChats(){
  const r=await api("/api/chats");const d=await r.json();
  const chats = d.chats||[];
  renderHistory(chats);
  if(chats.length>0) await openChat(chats[0].id,chats[0].title);
  else showWelcome(); // don't auto-create a chat, just show welcome screen
}
function renderHistory(chats){
  chatHist.innerHTML="";
  chats.forEach(c=>{
    const div=document.createElement("div");
    div.className="shi"+(c.id===currentChatId?" active":"");
    div.dataset.id=c.id;

    const title=document.createElement("span");
    title.className="shi-title";
    title.title=c.title;
    title.textContent=c.title;

    const del=document.createElement("button");
    del.className="shi-del";
    del.textContent="✕";
    del.title="Delete chat";
    del.type="button";
    del.style.cssText="pointer-events:all;position:relative;z-index:10;";
    del.onclick = async function(e){
      e.stopImmediatePropagation();
      e.preventDefault();
      del.textContent="…";
      try{
        const r = await api(`/api/chats/${c.id}`,{method:"DELETE"});
        if(!r.ok) throw new Error("Failed");
        div.style.opacity="0";
        div.style.transform="translateX(-10px)";
        div.style.transition="all .2s";
        setTimeout(()=>{
          div.remove();
          if(currentChatId===c.id){
            chatWin.innerHTML="";
            chatTitle.textContent="New Chat";
            currentChatId=null;
            showWelcome();
          }
        }, 200);
      }catch{
        del.textContent="✕";
        toast("Failed to delete chat","error");
      }
    };

    div.appendChild(title);
    div.appendChild(del);
    div.addEventListener("click",()=>openChat(c.id,c.title));
    chatHist.appendChild(div);
  });
}
async function openChat(id,title){
  currentChatId=id;chatTitle.textContent=title;chatWin.innerHTML="";
  document.querySelectorAll(".shi").forEach(el=>el.classList.toggle("active",parseInt(el.dataset.id)===id));
  const r=await api(`/api/chats/${id}/messages`);const d=await r.json();const msgs=d.messages||[];
  if(!msgs.length)showWelcome();
  else{msgs.forEach(m=>{if(m.role==="user")addUserMsg(m.content,false);else addBotAnswer(m.content,m.sources?JSON.parse(m.sources):[],false);});scrollWin();}
}
async function newChat(){
  const r=await api("/api/chats",{method:"POST"});const d=await r.json();
  currentChatId=d.chat.id;
  chatTitle.textContent="New Chat";
  chatWin.innerHTML="";
  showWelcome();
  // Refresh sidebar list without re-opening anything
  const cr=await api("/api/chats");const cd=await cr.json();
  renderHistory(cd.chats||[]);
}
document.getElementById("newChatBtn").addEventListener("click",newChat);

function showWelcome(){
  const div=document.createElement("div");div.className="welcome";div.id="welcomeDyn";
  div.innerHTML=`<div class="welcome-mark">🧠</div><h2>How can I help you today?</h2><p>Upload your documents and ask me anything. I'll find the most relevant information and give you accurate, cited answers.</p>`;
  chatWin.appendChild(div);
}
async function loadSuggestions(){
  try{
    const r=await api("/api/suggest");
    const d=await r.json();
    const g=document.getElementById("sugGridDyn");
    if(!g||!d.questions||!d.questions.length) return;
    g.innerHTML=d.questions.slice(0,4).map(q=>`<button class="sug-chip" onclick="askSug('${esc(q)}')">${esc(q)}</button>`).join("");
  }catch{}
}
function askSug(q){qInput.value=q;sendQ();}

async function loadDocuments(){
  const r=await api("/api/documents");const d=await r.json();allDocuments=d.documents||[];
  renderDocSB();renderDocGrid();docsLoaded=allDocuments.length>0;
  askBtn.disabled=false; // always allow sending — backend will explain if no docs
  if(docsLoaded)setStatus("active","Documents loaded");
}
function renderDocSB(){
  if(!allDocuments.length){docsCard.style.display="none";smartCard.style.display="none";return;}
  docsCard.style.display="flex";smartCard.style.display="flex";
  const total=allDocuments.reduce((s,d)=>s+d.chunks,0);
  docListSB.innerHTML=allDocuments.map(d=>`<li class="kb-item ${selectedDocId===d.id?'selected':''}" onclick="selDoc(${d.id})"><span class="kb-icon">📄</span><span class="kb-name" title="${esc(d.orig_name)}">${esc(d.orig_name)}</span><span class="kb-pages">${d.pages}p</span></li>`).join("");
  chunkInfo.textContent=`${total} chunks · ${allDocuments.length} files`;
}
function selDoc(id){selectedDocId=selectedDocId===id?null:id;renderDocSB();}
function renderDocGrid(){
  const g=document.getElementById("docGrid");if(!g)return;
  let docs = allDocuments;
  if(typeof filterFolderId !== 'undefined' && filterFolderId !== null){
    docs = docs.filter(d => d.folder_id === filterFolderId);
  }
  if(!docs.length){g.innerHTML=`<div class="empty-state"><div>📂</div><p>${(typeof filterFolderId!=='undefined'&&filterFolderId)?'No documents in this folder.':'No documents yet. Upload your first file.'}</p></div>`;return;}
  g.innerHTML=docs.map(d=>`<div class="doc-card">
    <div style="display:flex;align-items:flex-start;justify-content:space-between">
      <div class="doc-card-icon">${d.file_type==="pdf"?"📕":d.file_type==="docx"?"📘":"📄"}</div>
      ${(d.version||1)>1?`<span class="version-badge">v${d.version}</span>`:''}
    </div>
    <div class="doc-card-name" title="${esc(d.orig_name)}">${esc(d.orig_name)}</div>
    <div class="doc-card-meta">
      <span class="doc-badge">${d.file_type.toUpperCase()}</span>
      <span class="doc-badge">${d.pages}p</span>
      <span class="doc-badge">${d.chunks} chunks</span>
      <span class="doc-badge">${fmtSize(d.file_size)}</span>
    </div>
    <div class="doc-card-actions">
      <button class="doc-act" onclick="previewDoc(${d.id},'${esc(d.orig_name)}',${d.version||1})">👁 Preview</button>
      <button class="doc-act" onclick="sumDoc(${d.id},'${esc(d.orig_name)}')">📋 Summary</button>
      <button class="doc-act" onclick="topDoc(${d.id},'${esc(d.orig_name)}')">🏷️ Topics</button>
      <button class="doc-act del" onclick="delDoc(${d.id})">🗑 Delete</button>
    </div>
  </div>`).join("");
}
function fmtSize(b){if(b<1024)return b+"B";if(b<1048576)return(b/1024).toFixed(0)+"KB";return(b/1048576).toFixed(1)+"MB";}
async function delDoc(id){if(!confirm("Delete this document?"))return;await api(`/api/documents/${id}`,{method:"DELETE"});await loadDocuments();}

dropZone.addEventListener("click",()=>fileInput.click());
dropZone.addEventListener("dragover",e=>{e.preventDefault();dropZone.classList.add("drag-over");});
["dragleave","dragend"].forEach(ev=>dropZone.addEventListener(ev,()=>dropZone.classList.remove("drag-over")));
dropZone.addEventListener("drop",e=>{e.preventDefault();dropZone.classList.remove("drag-over");addFiles([...e.dataTransfer.files]);});
fileInput.addEventListener("change",()=>{addFiles([...fileInput.files]);fileInput.value="";});
function addFiles(files){[".pdf",".docx",".txt",".md"].forEach(ext=>files.filter(f=>f.name.toLowerCase().endsWith(ext)).forEach(f=>{if(!selectedFiles.find(s=>s.name===f.name))selectedFiles.push(f);}));renderFiles();}
function renderFiles(){
  fileList.innerHTML="";
  selectedFiles.forEach(f=>{const li=document.createElement("li");li.className="file-item";li.innerHTML=`<span class="file-item-icon">📄</span><span class="file-item-name" title="${f.name}">${f.name}</span><span class="file-item-size">${(f.size/1024).toFixed(0)}KB</span><button class="file-remove">✕</button>`;li.querySelector(".file-remove").addEventListener("click",()=>{selectedFiles=selectedFiles.filter(s=>s.name!==f.name);renderFiles();});fileList.appendChild(li);});
  uploadBtn.disabled=selectedFiles.length===0;
}
// Old uploadBtn listener removed — replaced by bulk progress version below
function showUpAlert(msg,type){upStatus.textContent=msg;upStatus.className="up-alert "+type;upStatus.classList.remove("hidden");}

document.getElementById("suggestBtn").addEventListener("click",async()=>{const id=selectedDocId||(allDocuments[0]&&allDocuments[0].id);if(!id)return showSmart("Select a document first.");showSmart("⏳ Generating...");const r=await api(`/api/documents/${id}/questions`);const d=await r.json();if(d.questions)showSmart(d.questions.map((q,i)=>`${i+1}. ${q}`).join("\n"));});
document.getElementById("summarizeBtn").addEventListener("click",async()=>{const id=selectedDocId||(allDocuments[0]&&allDocuments[0].id);if(!id)return showSmart("Select a document first.");const doc=allDocuments.find(d=>d.id===id);showSmart("⏳ Summarizing...");const r=await api(`/api/documents/${id}/summarize`,{method:"POST"});const d=await r.json();if(d.summary)openModal(`Summary: ${doc?.orig_name}`,d.summary);});
document.getElementById("topicsBtn").addEventListener("click",async()=>{const id=selectedDocId||(allDocuments[0]&&allDocuments[0].id);if(!id)return showSmart("Select a document first.");const doc=allDocuments.find(d=>d.id===id);showSmart("⏳ Extracting...");const r=await api(`/api/documents/${id}/topics`);const d=await r.json();if(d.topics)openModal(`Topics: ${doc?.orig_name}`,d.topics);});
function showSmart(t){smartOut.textContent=t;smartOut.classList.remove("hidden");}
async function sumDoc(id,name){openModal(`Summary: ${name}`,"⏳ Generating...");const r=await api(`/api/documents/${id}/summarize`,{method:"POST"});const d=await r.json();if(d.summary)document.getElementById("modalBody").innerHTML=marked.parse(d.summary);}
async function topDoc(id,name){openModal(`Topics: ${name}`,"⏳ Extracting...");const r=await api(`/api/documents/${id}/topics`);const d=await r.json();if(d.topics)document.getElementById("modalBody").innerHTML=marked.parse(d.topics);}
function openModal(title,content){document.getElementById("modalTitle").textContent=title;document.getElementById("modalBody").innerHTML=marked.parse(content);document.getElementById("modalOverlay").classList.remove("hidden");}
function closeModal(){document.getElementById("modalOverlay").classList.add("hidden");}
document.getElementById("modalOverlay").addEventListener("click",e=>{if(e.target===document.getElementById("modalOverlay"))closeModal();});

function setupResize(){qInput.addEventListener("input",()=>{qInput.style.height="auto";qInput.style.height=Math.min(qInput.scrollHeight,120)+"px";});}
askBtn.addEventListener("click",()=>{ if(isStreaming) stopStreaming(); else sendQ(); });
qInput.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&!isStreaming){e.preventDefault();sendQ();}});

// ── Stop streaming ─────────────────────────────────────────────────
let streamAbort = null;

function stopStreaming() {
  if(streamAbort) { streamAbort.abort(); streamAbort = null; }
}

function _setAskBtnStop() {
  askBtn.disabled = false;
  askBtn.title = "Stop generating";
  askBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>`;
  askBtn.classList.add("stop-mode");
}

function _setAskBtnSend() {
  askBtn.disabled = false;
  askBtn.title = "Send";
  askBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M22 2L11 13" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  askBtn.classList.remove("stop-mode");
}

async function sendQ(){
  const q=qInput.value.trim();if(!q||isStreaming)return;
  // Auto-create chat if none exists
  if(!currentChatId){
    const r=await api("/api/chats",{method:"POST"});const d=await r.json();
    currentChatId=d.chat.id;chatTitle.textContent="New Chat";
    const cr=await api("/api/chats");const cd=await cr.json();renderHistory(cd.chats||[]);
  }
  const ws=document.getElementById("welcomeDyn");if(ws)ws.remove();
  addUserMsg(q);qInput.value="";qInput.style.height="auto";
  isStreaming=true;
  _setAskBtnStop();
  setStatus("loading","Thinking...");
  const{cEl,sEl,confEl,fuEl}=makeBotBubble();let raw="";
  const cur=document.createElement("span");cur.className="cursor";cEl.appendChild(cur);
  streamAbort = new AbortController();
  try{
    const r=await fetch(`/api/chats/${currentChatId}/ask`,{method:"POST",headers:{"Content-Type":"application/json"},credentials:"include",body:JSON.stringify({question:q}),signal:streamAbort.signal});
    if(!r.ok){const e=await r.json();throw new Error(e.error||`Error ${r.status}`);}
    const reader=r.body.getReader();const dec=new TextDecoder();let buf="";
    while(true){const{done,value}=await reader.read();if(done)break;buf+=dec.decode(value,{stream:true});const lines=buf.split("\n");buf=lines.pop();
      for(const line of lines){if(!line.startsWith("data: "))continue;let p;try{p=JSON.parse(line.slice(6));}catch{continue;}
        if(p.type==="sources"){/* sources hidden */}
        else if(p.type==="confidence"){/* confidence hidden */}
        else if(p.type==="token"){raw+=p.text;cur.remove();const clean=raw.replace(/\(Source:[^)]+\)/g,'').replace(/\[Source:[^\]]+\]/g,'').replace(/\(Source:[^)]+,\s*p\.\d+\)/g,'');cEl.innerHTML=marked.parse(clean);addCopyBtns(cEl);hljs.highlightAll();cEl.appendChild(cur);scrollWin();}
        else if(p.type==="followups"){/* follow-ups hidden */}
        else if(p.type==="done"){cur.remove();const clean=raw.replace(/\(Source:[^)]+\)/g,'').replace(/\[Source:[^\]]+\]/g,'').replace(/\(Source:[^)]+,\s*p\.\d+\)/g,'');cEl.innerHTML=marked.parse(clean);addCopyBtns(cEl);hljs.highlightAll();scrollWin();setStatus("active","Documents loaded");const cr=await api("/api/chats");const cd=await cr.json();renderHistory(cd.chats||[]);}
        else if(p.type==="error"){cur.remove();cEl.innerHTML=`<span style="color:#991b1b">❌ ${esc(p.text)}</span>`;setStatus("error","Error");}
      }
    }
  }catch(e){
    cur.remove();
    if(e.name==="AbortError"){
      // User stopped — show what was generated so far
      if(raw){cEl.innerHTML=marked.parse(raw);addCopyBtns(cEl);renderConfidence(confEl,parseFloat(cEl.dataset.confidence||0));}
      else{cEl.innerHTML=`<span style="color:var(--text3)">⏹ Stopped.</span>`;}
      setStatus("active","Stopped");
    } else {
      cEl.innerHTML=`<span style="color:#991b1b">❌ ${e.message==="Failed to fetch"?"Server unreachable":esc(e.message)}</span>`;
      setStatus("error","Error");
    }
  }
  finally{isStreaming=false;streamAbort=null;_setAskBtnSend();}
}

function addUserMsg(text,scroll=true){const r=document.createElement("div");r.className="msg-row user";r.innerHTML=`<div class="msg-av">👤</div><div class="msg-bub">${esc(text)}</div>`;chatWin.appendChild(r);if(scroll)scrollWin();}
function addBotAnswer(text,sources=[],scroll=true){const clean=text.replace(/\(Source:[^)]+\)/g,'').replace(/\[Source:[^\]]+\]/g,'');const r=document.createElement("div");r.className="msg-row bot";const b=document.createElement("div");b.className="msg-bub";const c=document.createElement("div");c.className="md-content";c.innerHTML=marked.parse(clean);addCopyBtns(c);hljs.highlightAll();b.appendChild(c);r.innerHTML=`<div class="msg-av">🧠</div>`;r.appendChild(b);chatWin.appendChild(r);if(scroll)scrollWin();}
function makeBotBubble(){const r=document.createElement("div");r.className="msg-row bot";const b=document.createElement("div");b.className="msg-bub";const cEl=document.createElement("div");cEl.className="md-content";const sEl=document.createElement("div");const confEl=document.createElement("div");const fuEl=document.createElement("div");b.appendChild(cEl);b.appendChild(sEl);b.appendChild(confEl);b.appendChild(fuEl);r.innerHTML=`<div class="msg-av">🧠</div>`;r.appendChild(b);chatWin.appendChild(r);scrollWin();return{cEl,sEl,confEl,fuEl};}
function renderSrcs(el,sources){if(!sources||!sources.length)return;el.innerHTML=`<div class="src-block"><div class="src-title">📚 Sources</div>${sources.map(s=>`<span class="src-tag">📄 ${esc(s.file)} · p.${s.page}</span>`).join("")}</div>`;}
function addCopyBtns(el){el.querySelectorAll("pre").forEach(pre=>{if(pre.querySelector(".copy-btn"))return;const btn=document.createElement("button");btn.className="copy-btn";btn.textContent="Copy";btn.addEventListener("click",()=>{navigator.clipboard.writeText(pre.querySelector("code")?.textContent||"");btn.textContent="Copied!";setTimeout(()=>btn.textContent="Copy",2000);});pre.appendChild(btn);});}
async function loadAnalytics(){const r=await api("/api/analytics");const d=await r.json();document.getElementById("statDocs").textContent=d.docs??0;document.getElementById("statChats").textContent=d.chats??0;document.getElementById("statQueries").textContent=d.queries??0;document.getElementById("statChunks").textContent=d.chunks??0;}
async function logout(){await api("/api/auth/logout",{method:"POST"});location.href="/login";}
function scrollWin(){chatWin.scrollTop=chatWin.scrollHeight;}
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}

// ── Theme toggle ───────────────────────────────────────────────────
function toggleTheme(){
  const isDark = document.documentElement.classList.toggle("dark");
  _applyThemeUI(isDark);
  localStorage.setItem("theme", isDark ? "dark" : "light");
}

function _applyThemeUI(isDark){
  const icon  = document.getElementById("themeIcon");
  const label = document.getElementById("themeLabel");
  if(icon)  icon.textContent  = isDark ? "🌙" : "☀️";
  if(label) label.textContent = isDark ? "Dark mode" : "Light mode";
  syncThemeToggle();
}

// Apply saved theme on load — default to dark
(function(){
  const saved = localStorage.getItem("theme");
  const isDark = saved !== "light"; // dark unless explicitly set to light
  document.documentElement.classList.toggle("dark", isDark);
  // Run after DOM is ready so elements exist
  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", () => _applyThemeUI(isDark));
  } else {
    _applyThemeUI(isDark);
  }
})();

// ── Profile / Settings Popup ───────────────────────────────────────
function openProfile(){
  const popup = document.getElementById("profilePopup");
  const backdrop = document.getElementById("ppBackdrop");
  // Fill in current user data
  if(currentUser){
    document.getElementById("ppAvatar").textContent  = currentUser.name[0].toUpperCase();
    document.getElementById("ppName").textContent    = currentUser.name;
    document.getElementById("ppEmail").textContent   = currentUser.email;
    document.getElementById("ppNameInput").value     = currentUser.name;
    document.getElementById("ppEmailInput").value    = currentUser.email;
  }
  syncThemeToggle();
  popup.classList.remove("hidden");
  backdrop.classList.remove("hidden");
  checkEmailVerification();
}

function closeProfile(){
  document.getElementById("profilePopup").classList.add("hidden");
  document.getElementById("ppBackdrop").classList.add("hidden");
  // Clear password fields
  ["ppOldPwd","ppNewPwd","ppConfirmPwd"].forEach(id => document.getElementById(id).value = "");
  document.getElementById("ppAlert").classList.add("hidden");
}

function ppTab(tab){
  document.querySelectorAll(".pp-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".pp-body").forEach(b => b.classList.add("hidden"));
  event.target.classList.add("active");
  document.getElementById("pp" + tab.charAt(0).toUpperCase() + tab.slice(1)).classList.remove("hidden");
}

function syncThemeToggle(){
  const isDark = document.documentElement.classList.contains("dark");
  // Profile popup toggle
  const ppToggle = document.getElementById("ppThemeToggle");
  if(ppToggle) ppToggle.classList.toggle("active", isDark);
  // Sidebar toggle track
  const track = document.querySelector(".tt-track");
  if(track) track.classList.toggle("dark-active", isDark);
}

function showPpAlert(msg, type){
  const el = document.getElementById("ppAlert");
  el.textContent = msg;
  el.className = "pp-alert " + type;
}

async function saveProfile(){
  const name    = document.getElementById("ppNameInput").value.trim();
  const oldPwd  = document.getElementById("ppOldPwd").value;
  const newPwd  = document.getElementById("ppNewPwd").value;
  const confirm = document.getElementById("ppConfirmPwd").value;

  if(!name){ showPpAlert("Name cannot be empty.", "error"); return; }
  if(newPwd && newPwd.length < 6){ showPpAlert("New password must be at least 6 characters.", "error"); return; }
  if(newPwd && newPwd !== confirm){ showPpAlert("Passwords do not match.", "error"); return; }
  if(newPwd && !oldPwd){ showPpAlert("Please enter your current password.", "error"); return; }

  const btn = document.querySelector(".pp-save-btn");
  btn.textContent = "Saving..."; btn.disabled = true;

  try{
    const payload = { name };
    if(newPwd) { payload.old_password = oldPwd; payload.new_password = newPwd; }

    const r = await api("/api/auth/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    if(!r.ok) throw new Error(d.error || "Update failed");

    // Update UI
    currentUser.name = name;
    document.getElementById("userName").textContent  = name;
    document.getElementById("userAvatar").textContent = name[0].toUpperCase();
    document.getElementById("ppAvatar").textContent  = name[0].toUpperCase();
    document.getElementById("ppName").textContent    = name;
    ["ppOldPwd","ppNewPwd","ppConfirmPwd"].forEach(id => document.getElementById(id).value = "");
    showPpAlert("Profile updated successfully!", "success");
  } catch(e){
    showPpAlert(e.message, "error");
  } finally {
    btn.textContent = "Save Changes"; btn.disabled = false;
  }
}

async function dangerClear(){
  if(!confirm("This will permanently delete all your documents and embeddings. Continue?")) return;
  await api("/api/clear-all", { method: "POST" });
  await loadDocuments();
  closeProfile();
}

async function deleteAccount(){
  const confirmed = confirm(
    "⚠️ Delete your account?\n\nThis will permanently remove your account, all documents, chats, and data. This CANNOT be undone."
  );
  if (!confirmed) return;
  // Second confirmation
  const reconfirmed = confirm("Are you absolutely sure? Your account will be gone forever.");
  if (!reconfirmed) return;
  const r = await api("/api/auth/delete-account", { method: "POST" });
  if (r.ok) {
    location.href = "/login";
  } else {
    const d = await r.json();
    toast(d.error || "Failed to delete account", "error");
  }
}

// ── Toast notifications ────────────────────────────────────────────
function toast(msg, type="info", duration=3500){
  const icons = {success:"✅", error:"❌", info:"ℹ️", warning:"⚠️"};
  const c = document.getElementById("toastContainer");
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.innerHTML = `<span class="toast-icon">${icons[type]||"ℹ️"}</span><span class="toast-msg">${msg}</span><button class="toast-close" onclick="this.parentElement.remove()">✕</button>`;
  c.appendChild(t);
  setTimeout(()=>{ t.style.animation="toastIn .25s ease reverse"; setTimeout(()=>t.remove(), 250); }, duration);
}

// ── Search chats ───────────────────────────────────────────────────
let searchTimer = null;
async function searchChats(q){
  const box = document.getElementById("searchResults");
  if(!q.trim()){ box.classList.add("hidden"); return; }
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async()=>{
    const r = await api(`/api/search?q=${encodeURIComponent(q)}`);
    const d = await r.json();
    if(!d.results.length){ box.innerHTML=`<div class="sr-item"><span class="sr-text" style="color:var(--ink4)">No results found</span></div>`; }
    else{ box.innerHTML = d.results.map(r=>`<div class="sr-item" onclick="openChat(${r.chat_id},'${esc(r.chat_title)}');document.getElementById('searchInput').value='';document.getElementById('searchResults').classList.add('hidden')"><div class="sr-chat">${esc(r.chat_title)}</div><div class="sr-text">${esc(r.content.slice(0,80))}…</div></div>`).join(""); }
    box.classList.remove("hidden");
  }, 300);
}

// ── URL / YouTube ingestion ────────────────────────────────────────
async function ingestUrl(){
  const input = document.getElementById("ingestUrl");
  const url = input.value.trim();
  if(!url){ toast("Please enter a URL", "warning"); return; }
  const isYT = url.includes("youtube.com") || url.includes("youtu.be");
  const endpoint = isYT ? "/api/ingest/youtube" : "/api/ingest/url";
  toast(`⏳ Ingesting ${isYT ? "YouTube transcript" : "webpage"}…`, "info", 8000);
  try{
    const r = await api(endpoint, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({url}) });
    const d = await r.json();
    if(!r.ok) throw new Error(d.error);
    input.value = "";
    await loadDocuments();
    toast(`✅ ${d.message}`, "success");
  }catch(e){ toast(e.message, "error"); }
}

// ── Export chat as PDF ─────────────────────────────────────────────
async function exportChat(){
  if(!currentChatId){ toast("No chat to export", "warning"); return; }
  toast("Generating PDF\u2026", "info", 2000);
  try {
    const r = await api('/api/chats/' + currentChatId + '/export');
    if(!r.ok){ toast("Export failed", "error"); return; }
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    const title = (document.getElementById("chatTitle")?.textContent || "chat").replace(/[^a-z0-9]/gi,'_').slice(0,40);
    a.href     = url;
    a.download = title + '.pdf';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast("PDF downloaded", "success");
  } catch(e) {
    toast("Export failed: " + e.message, "error");
  }
}

// ── Message feedback ───────────────────────────────────────────────
async function sendFeedback(msgId, rating, btn){
  try{
    await api(`/api/messages/${msgId}/feedback`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({rating}) });
    btn.closest(".msg-actions").querySelectorAll(".msg-act-btn").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    toast(rating===1 ? "Thanks for the feedback! 👍" : "Thanks, we'll improve! 👎", "success");
  }catch(e){ toast("Failed to save feedback", "error"); }
}

// ── Keyboard shortcuts ─────────────────────────────────────────────
document.addEventListener("keydown", e=>{
  if((e.ctrlKey||e.metaKey) && e.key==="k"){ e.preventDefault(); document.getElementById("searchInput").focus(); }
  if((e.ctrlKey||e.metaKey) && e.key==="n"){ e.preventDefault(); newChat(); }
  if((e.ctrlKey||e.metaKey) && e.key==="e"){ e.preventDefault(); exportChat(); }
  if(e.key==="Escape"){
    closeModal();
    document.getElementById("searchResults").classList.add("hidden");
    closeProfile();
  }
});

// ── Onboarding ─────────────────────────────────────────────────────
function closeOnboarding(){
  document.getElementById("onboardingModal").classList.add("hidden");
  localStorage.setItem("onboarded","1");
}
function checkOnboarding(){
  if(!localStorage.getItem("onboarded")){
    setTimeout(()=>document.getElementById("onboardingModal").classList.remove("hidden"), 800);
  }
}

// ── Override addBotAnswer to include feedback buttons ─────────────
const _origAddBotAnswer = addBotAnswer;
function addBotAnswer(text, sources=[], scroll=true, msgId=null){
  const clean = text.replace(/\(Source:[^)]+\)/g,'').replace(/\[Source:[^\]]+\]/g,'');
  const row = document.createElement("div"); row.className="msg-row bot";
  const b = document.createElement("div"); b.className="msg-bub";
  const c = document.createElement("div"); c.className="md-content"; c.innerHTML=marked.parse(clean); addCopyBtns(c); hljs.highlightAll();
  // Action buttons (no sources, confidence, or follow-ups)
  const acts = document.createElement("div"); acts.className="msg-actions";
  acts.innerHTML=`
    <button class="msg-act-btn" onclick="navigator.clipboard.writeText(this.closest('.msg-bub').querySelector('.md-content').innerText);toast('Copied!','success')" title="Copy answer">📋 Copy</button>
    ${msgId ? `<button class="msg-act-btn" onclick="sendFeedback(${msgId},1,this)" title="Good answer">👍</button><button class="msg-act-btn" onclick="sendFeedback(${msgId},-1,this)" title="Bad answer">👎</button>` : ""}
  `;
  b.appendChild(c); b.appendChild(acts);
  row.innerHTML=`<div class="msg-av">🧠</div>`; row.appendChild(b);
  chatWin.appendChild(row); if(scroll) scrollWin();
}

// Call onboarding check after user loads
const _origLoadUser = loadUser;
loadUser = async function(){
  await _origLoadUser();
  checkOnboarding();
};



// ── About modal ────────────────────────────────────────────────────
function openAbout(){
  document.getElementById("aboutModal").classList.remove("hidden");
}
function closeAbout(){
  document.getElementById("aboutModal").classList.add("hidden");
}
document.getElementById("aboutModal").addEventListener("click", e => {
  if(e.target === document.getElementById("aboutModal")) closeAbout();
});
// Esc key closes about modal too
document.addEventListener("keydown", e => {
  if(e.key === "Escape") closeAbout();
}, true);

// ── Confidence score renderer ──────────────────────────────────────
function renderConfidence(el, score) {
  if (!score || score <= 0) return;
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? '#22d3ee' : pct >= 40 ? '#f59e0b' : '#ef4444';
  const label = pct >= 70 ? 'High' : pct >= 40 ? 'Medium' : 'Low';
  el.innerHTML = `
    <div class="conf-bar-wrap">
      <span class="conf-label">Confidence</span>
      <div class="conf-bar"><div class="conf-fill" style="width:${pct}%;background:${color}"></div></div>
      <span class="conf-pct" style="color:${color}">${pct}% ${label}</span>
    </div>`;
}

// ── Follow-up suggestions renderer ────────────────────────────────
function renderFollowups(el, questions) {
  if (!questions || !questions.length) return;
  el.innerHTML = `<div class="followup-wrap">
    <div class="followup-title">💡 Follow-up questions</div>
    <div class="followup-chips">
      ${questions.map(q => `<button class="followup-chip" onclick="askSug('${esc(q)}')">${esc(q)}</button>`).join('')}
    </div>
  </div>`;
}

// ── Drag-to-folder ─────────────────────────────────────────────────
function dragDoc(e, docId) { e.dataTransfer.setData('docId', docId); }

// ── Bulk upload with per-file progress ────────────────────────────
uploadBtn.addEventListener("click", async () => {
  if (!selectedFiles.length) return;
  uploadBtn.disabled = true;
  upBtnTxt.textContent = "Processing...";
  upLoader.classList.remove("hidden");
  uploadBtn.querySelector(".bp-icon").classList.add("hidden");
  setStatus("loading", "Processing...");

  // Show bulk progress UI
  const wrap = document.getElementById('bulkProgressWrap');
  const list = document.getElementById('bulkProgressList');
  wrap.classList.remove('hidden');
  list.innerHTML = selectedFiles.map((f, i) =>
    `<div class="bp-row" id="bpr-${i}">
      <span class="bp-fname">${esc(f.name)}</span>
      <div class="bp-bar-wrap"><div class="bp-bar" id="bpb-${i}" style="width:0%"></div></div>
      <span class="bp-status" id="bps-${i}">Waiting…</span>
    </div>`
  ).join('');

  const results = [];
  for (let i = 0; i < selectedFiles.length; i++) {
    const f = selectedFiles[i];
    document.getElementById(`bps-${i}`).textContent = 'Uploading…';
    document.getElementById(`bpb-${i}`).style.width = '30%';

    const fd = new FormData();
    fd.append('files', f);
    if (filterFolderId) fd.append('folder_id', filterFolderId);

    try {
      const r = await api('/api/documents/upload', {method: 'POST', body: fd});
      const d = await r.json();
      document.getElementById(`bpb-${i}`).style.width = '100%';
      if (d.results && d.results[0] && !d.results[0].error) {
        document.getElementById(`bps-${i}`).textContent = `✅ ${d.results[0].chunks} chunks`;
        document.getElementById(`bpb-${i}`).style.background = '#22d3ee';
        results.push(d.results[0]);
      } else {
        document.getElementById(`bps-${i}`).textContent = `❌ ${d.results?.[0]?.error || 'Failed'}`;
        document.getElementById(`bpb-${i}`).style.background = '#ef4444';
      }
    } catch (e) {
      document.getElementById(`bps-${i}`).textContent = '❌ Error';
      document.getElementById(`bpb-${i}`).style.background = '#ef4444';
    }
  }

  selectedFiles = [];
  renderFiles();
  await loadDocuments();
  setStatus('active', 'Documents loaded');
  setTimeout(() => wrap.classList.add('hidden'), 3000);
  uploadBtn.disabled = false;
  upBtnTxt.textContent = 'Process Files';
  upLoader.classList.add('hidden');
  uploadBtn.querySelector('.bp-icon').classList.remove('hidden');
  toast(`Processed ${results.length} file(s)`, 'success');
}, {once: false});

// Remove the old uploadBtn listener (it was added before, we override here)
// The new one above replaces it via the re-declaration

// ── Document preview ───────────────────────────────────────────────
let previewDocId = null;

async function showVersions() {
  if (!previewDocId) return;
  const r = await api(`/api/documents/${previewDocId}/versions`);
  const d = await r.json();
  const versions = d.versions || [];
  openModal('Version History', versions.map((v, i) =>
    `**v${v.version}** — ${v.pages} pages, ${v.chunks} chunks — ${new Date(v.created_at).toLocaleDateString()}`
  ).join('\n\n'));
}

// ── Document comparison ────────────────────────────────────────────
function openCompareModal() {
  const selA = document.getElementById('cmpDocA');
  const selB = document.getElementById('cmpDocB');
  const opts = allDocuments.map(d => `<option value="${esc(d.orig_name)}">${esc(d.orig_name)}</option>`).join('');
  selA.innerHTML = opts;
  selB.innerHTML = opts;
  if (allDocuments.length > 1) selB.selectedIndex = 1;
  document.getElementById('compareModal').classList.remove('hidden');
}

async function runComparison() {
  const docA  = document.getElementById('cmpDocA').value;
  const docB  = document.getElementById('cmpDocB').value;
  const topic = document.getElementById('cmpTopic').value.trim() || 'general content';
  if (docA === docB) return toast('Select two different documents', 'warning');
  document.getElementById('compareModal').classList.add('hidden');
  openModal(`Comparing: ${docA} vs ${docB}`, '⏳ Analyzing documents…');
  const r = await api('/api/documents/compare', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({doc_a: docA, doc_b: docB, topic})
  });
  const d = await r.json();
  if (d.comparison) document.getElementById('modalBody').innerHTML = marked.parse(d.comparison);
  else document.getElementById('modalBody').textContent = d.error || 'Failed';
}

// ── Full-text document content search ─────────────────────────────
let docSearchTimer = null;
function searchDocContent(q) {
  const box = document.getElementById('docSearchResults');
  if (!q.trim()) { box.classList.add('hidden'); return; }
  clearTimeout(docSearchTimer);
  docSearchTimer = setTimeout(async () => {
    const r = await api(`/api/documents/search?q=${encodeURIComponent(q)}`);
    const d = await r.json();
    if (!d.results || !d.results.length) {
      box.innerHTML = '<div class="dsr-item"><span style="color:var(--text3)">No matches found in document content</span></div>';
    } else {
      box.innerHTML = d.results.map(r =>
        `<div class="dsr-item">
          <div class="dsr-name">📄 ${esc(r.orig_name)}</div>
          <div class="dsr-snippet">${r.snippet || ''}</div>
        </div>`
      ).join('');
    }
    box.classList.remove('hidden');
  }, 350);
}

// ── Document Preview ───────────────────────────────────────────────
function previewDoc(id, name, version) {
  previewDocId = id;
  const modal   = document.getElementById('previewModal');
  const frame   = document.getElementById('previewFrame');
  const loading = document.getElementById('previewLoading');
  const fallback= document.getElementById('previewFallback');
  const badge   = document.getElementById('previewVersionBadge');
  const dlLink  = document.getElementById('previewDownload');

  // Reset state
  frame.classList.add('hidden');
  fallback.classList.add('hidden');
  loading.classList.remove('hidden');
  frame.src = 'about:blank';

  document.getElementById('previewTitle').textContent = name;

  if (version > 1) {
    badge.textContent = `v${version}`;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }

  modal.classList.remove('hidden');

  const ext = name.split('.').pop().toLowerCase();
  const previewUrl = `/api/documents/${id}/preview`;

  if (ext === 'pdf') {
    // Embed PDF directly in iframe
    frame.onload = () => {
      loading.classList.add('hidden');
      frame.classList.remove('hidden');
    };
    frame.onerror = () => {
      loading.classList.add('hidden');
      frame.classList.add('hidden');
      fallback.classList.remove('hidden');
      dlLink.href = previewUrl;
    };
    frame.src = previewUrl;
  } else if (['txt', 'md'].includes(ext)) {
    // Fetch text and render in iframe as plain text
    fetch(previewUrl, {credentials: 'include'})
      .then(r => {
        if (!r.ok) throw new Error('Not found');
        return r.text();
      })
      .then(text => {
        loading.classList.add('hidden');
        const blob = new Blob([`<pre style="font-family:monospace;padding:1rem;white-space:pre-wrap;word-break:break-word;background:#0f172a;color:#f8fafc;min-height:100vh;margin:0">${text.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</pre>`], {type: 'text/html'});
        frame.src = URL.createObjectURL(blob);
        frame.classList.remove('hidden');
      })
      .catch(() => {
        loading.classList.add('hidden');
        fallback.classList.remove('hidden');
        dlLink.href = previewUrl;
      });
  } else {
    // Unsupported type — show download fallback
    loading.classList.add('hidden');
    fallback.classList.remove('hidden');
    dlLink.href = previewUrl;
  }
}

function closePreview() {
  const modal = document.getElementById('previewModal');
  const frame = document.getElementById('previewFrame');
  modal.classList.add('hidden');
  frame.src = 'about:blank'; // stop loading / free memory
}

// Close on backdrop click
document.getElementById('previewModal').addEventListener('click', e => {
  if (e.target === document.getElementById('previewModal')) closePreview();
});

// ── Folders ────────────────────────────────────────────────────────
let allFolders = [];
let selectedFolderColor = '#8b5cf6';
let filterFolderId = null;

async function loadFolders() {
  try {
    const r = await api('/api/folders');
    const d = await r.json();
    allFolders = d.folders || [];
    renderFoldersRow();
  } catch(e) { /* folders not critical */ }
}

function renderFoldersRow() {
  const row = document.getElementById('foldersRow');
  if (!row) return;
  row.innerHTML = `
    <div class="folder-chip ${filterFolderId === null ? 'active' : ''}" onclick="filterByFolder(null)">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
      All
    </div>
    ${allFolders.map(f => `
      <div class="folder-chip ${filterFolderId === f.id ? 'active' : ''}" style="--fc:${f.color}" onclick="filterByFolder(${f.id})">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
        ${esc(f.name)}
        <button class="folder-del" onclick="event.stopPropagation();deleteFolder(${f.id})">✕</button>
      </div>`).join('')}`;
}

function filterByFolder(id) {
  filterFolderId = id;
  renderFoldersRow();
  renderDocGrid();
}

function openNewFolderModal() {
  selectedFolderColor = '#8b5cf6';
  document.getElementById('newFolderName').value = '';
  // Reset color selection
  document.querySelectorAll('#folderColors .fc').forEach(el => el.classList.remove('selected'));
  const first = document.querySelector('#folderColors .fc[data-color="#8b5cf6"]');
  if (first) first.classList.add('selected');
  document.getElementById('newFolderModal').classList.remove('hidden');
  setTimeout(() => document.getElementById('newFolderName').focus(), 100);
}

function selectFolderColor(el) {
  document.querySelectorAll('#folderColors .fc').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  selectedFolderColor = el.dataset.color;
}

async function createFolder() {
  const name = document.getElementById('newFolderName').value.trim();
  if (!name) {
    toast('Enter a folder name', 'warning');
    document.getElementById('newFolderName').focus();
    return;
  }
  const btn = document.querySelector('#newFolderModal .pp-save-btn');
  btn.textContent = 'Creating…';
  btn.disabled = true;
  try {
    const r = await api('/api/folders', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name, color: selectedFolderColor })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Failed');
    document.getElementById('newFolderModal').classList.add('hidden');
    await loadFolders();
    toast(`Folder "${name}" created`, 'success');
  } catch(e) {
    toast(e.message, 'error');
  } finally {
    btn.textContent = 'Create Folder';
    btn.disabled = false;
  }
}

async function deleteFolder(id) {
  if (!confirm('Delete this folder? Documents will be unassigned.')) return;
  await api(`/api/folders/${id}`, { method: 'DELETE' });
  if (filterFolderId === id) filterFolderId = null;
  await loadFolders();
  renderDocGrid();
  toast('Folder deleted', 'info');
}

// Hook loadFolders into loadDocuments
const _baseLoadDocuments = loadDocuments;
loadDocuments = async function() {
  await _baseLoadDocuments();
  await loadFolders();
};

// Allow Enter key in folder name input
document.addEventListener('DOMContentLoaded', () => {
  const inp = document.getElementById('newFolderName');
  if (inp) inp.addEventListener('keydown', e => { if (e.key === 'Enter') createFolder(); });
});

// ════════════════════════════════════════════════════════════════
// FEATURE: VOICE INPUT (Web Speech 

// ══════════════════════════════════════════════════════════════════
// FEATURE: VOICE INPUT + TEXT-TO-SPEECH
// ══════════════════════════════════════════════════════════════════

let voiceRecognition = null;
let isListening = false;
let ttsEnabled = true;

function toggleVoice() {
  if (isListening) { stopVoice(); return; }
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { toast('Voice input not supported in this browser', 'warning'); return; }

  voiceRecognition = new SpeechRecognition();
  voiceRecognition.continuous = false;
  voiceRecognition.interimResults = true;
  voiceRecognition.lang = navigator.language || 'en-US';

  voiceRecognition.onstart = () => {
    isListening = true;
    const btn = document.getElementById('voiceBtn');
    btn.classList.add('listening');
    btn.title = 'Listening… click to stop';
    setStatus('loading', 'Listening…');
  };

  voiceRecognition.onresult = (e) => {
    const transcript = Array.from(e.results).map(r => r[0].transcript).join('');
    qInput.value = transcript;
    qInput.style.height = 'auto';
    qInput.style.height = Math.min(qInput.scrollHeight, 120) + 'px';
  };

  voiceRecognition.onend = () => {
    isListening = false;
    const btn = document.getElementById('voiceBtn');
    btn.classList.remove('listening');
    btn.title = 'Voice input';
    setStatus('active', 'Ready');
    if (qInput.value.trim()) sendQ();
  };

  voiceRecognition.onerror = (e) => {
    isListening = false;
    document.getElementById('voiceBtn').classList.remove('listening');
    if (e.error !== 'aborted') toast('Voice error: ' + e.error, 'error');
    setStatus('active', 'Ready');
  };

  voiceRecognition.start();
}

function stopVoice() {
  if (voiceRecognition) { voiceRecognition.stop(); voiceRecognition = null; }
}

function speakText(text) {
  if (!ttsEnabled || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  // Strip markdown for cleaner speech
  const clean = text.replace(/[#*`_~\[\]()>]/g, '').replace(/\n+/g, ' ').trim();
  const utt = new SpeechSynthesisUtterance(clean);
  utt.lang = navigator.language || 'en-US';
  utt.rate = 1.0;
  window.speechSynthesis.speak(utt);
}

// ══════════════════════════════════════════════════════════════════
// FEATURE: SAVED PROMPTS LIBRARY
// ══════════════════════════════════════════════════════════════════

let savedPrompts = [];

async function loadSavedPrompts() {
  try {
    const r = await api('/api/prompts');
    const d = await r.json();
    savedPrompts = d.prompts || [];
  } catch(e) {}
}

async function openPromptsPanel() {
  await loadSavedPrompts();
  renderPromptsModal();
  document.getElementById('promptsModal').classList.remove('hidden');
}

function renderPromptsModal() {
  const list = document.getElementById('promptsList');
  if (!savedPrompts.length) {
    list.innerHTML = '<p style="color:var(--text3);font-size:.8rem;text-align:center;padding:1rem">No saved prompts yet. Save a question to reuse it quickly.</p>';
    return;
  }
  list.innerHTML = savedPrompts.map(p => `
    <div class="prompt-item">
      <div class="prompt-item-content" onclick="usePrompt('${esc(p.prompt)}')">
        <div class="prompt-item-title">${esc(p.title)}</div>
        <div class="prompt-item-text">${esc(p.prompt.slice(0, 80))}${p.prompt.length > 80 ? '…' : ''}</div>
      </div>
      <button class="prompt-del" onclick="deletePrompt(${p.id})">✕</button>
    </div>`).join('');
}

function usePrompt(text) {
  qInput.value = text;
  qInput.style.height = 'auto';
  qInput.style.height = Math.min(qInput.scrollHeight, 120) + 'px';
  document.getElementById('promptsModal').classList.add('hidden');
  qInput.focus();
}

async function saveCurrentPrompt() {
  const titleInput = document.getElementById('promptTitleInput');
  const textInput  = document.getElementById('promptTextInput');
  // Use modal textarea if filled, otherwise fall back to chat input
  const text  = (textInput && textInput.value.trim()) || qInput.value.trim();
  const title = (titleInput && titleInput.value.trim()) || text.slice(0, 40);
  if (!text)  { toast('Enter a prompt text to save', 'warning'); return; }
  if (!title) { toast('Enter a title for this prompt', 'warning'); return; }
  const r = await api('/api/prompts', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title, prompt: text})
  });
  const d = await r.json();
  if (r.ok) {
    savedPrompts.unshift(d.prompt);
    if (titleInput) titleInput.value = '';
    if (textInput)  textInput.value  = '';
    renderPromptsModal();
    toast('Prompt saved!', 'success');
  } else {
    toast(d.error || 'Failed to save prompt', 'error');
  }
}

async function deletePrompt(id) {
  await api(`/api/prompts/${id}`, {method: 'DELETE'});
  savedPrompts = savedPrompts.filter(p => p.id !== id);
  renderPromptsModal();
  toast('Prompt deleted', 'info');
}

// ══════════════════════════════════════════════════════════════════
// FEATURE: CHAT SHARING
// ══════════════════════════════════════════════════════════════════

async function shareChat() {
  if (!currentChatId) { toast('No chat to share', 'warning'); return; }
  const r = await api(`/api/chats/${currentChatId}/share`, {method: 'POST'});
  const d = await r.json();
  if (!r.ok) { toast(d.error || 'Failed to share', 'error'); return; }

  document.getElementById('shareUrlInput').value = window.location.origin + d.url;
  document.getElementById('shareModal').classList.remove('hidden');
}

function copyShareUrl() {
  const url = document.getElementById('shareUrlInput').value;
  navigator.clipboard.writeText(url).then(() => toast('Link copied!', 'success'));
}

// ══════════════════════════════════════════════════════════════════
// FEATURE: CHAT BRANCHING
// ══════════════════════════════════════════════════════════════════

async function branchChat(msgId) {
  if (!currentChatId) return;
  const r = await api(`/api/chats/${currentChatId}/branch`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({from_message_id: msgId})
  });
  const d = await r.json();
  if (!r.ok) { toast(d.error || 'Branch failed', 'error'); return; }

  toast('Branch created! Opening…', 'success');
  // Refresh chat list and open the new branch
  const cr = await api('/api/chats');
  const cd = await cr.json();
  renderHistory(cd.chats || []);
  await openChat(d.chat.id, d.chat.title);
}

// ══════════════════════════════════════════════════════════════════
// FEATURE: ANSWER REGENERATION
// ══════════════════════════════════════════════════════════════════

async function regenerateMsg(msgId, bubbleEl) {
  if (!currentChatId || isStreaming) return;
  isStreaming = true;
  _setAskBtnStop();
  setStatus('loading', 'Regenerating…');

  // Clear the bubble content
  bubbleEl.innerHTML = '';
  const cEl = document.createElement('div');
  cEl.className = 'md-content';
  const cur = document.createElement('span');
  cur.className = 'cursor';
  cEl.appendChild(cur);
  bubbleEl.appendChild(cEl);

  streamAbort = new AbortController();
  let raw = '';

  try {
    const r = await fetch(`/api/chats/${currentChatId}/regenerate`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'include',
      body: JSON.stringify({message_id: msgId}),
      signal: streamAbort.signal
    });
    if (!r.ok) throw new Error('Regeneration failed');

    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      const lines = buf.split('\n'); buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let p; try { p = JSON.parse(line.slice(6)); } catch { continue; }
        if (p.type === 'token') {
          raw += p.text;
          cur.remove();
          cEl.innerHTML = marked.parse(raw);
          addCopyBtns(cEl);
          cEl.appendChild(cur);
          scrollWin();
        } else if (p.type === 'done') {
          cur.remove();
          cEl.innerHTML = marked.parse(raw);
          addCopyBtns(cEl);
          scrollWin();
          setStatus('active', 'Ready');
        }
      }
    }
  } catch(e) {
    cur.remove();
    if (e.name !== 'AbortError') {
      cEl.innerHTML = `<span style="color:#991b1b">❌ Regeneration failed</span>`;
    }
  } finally {
    isStreaming = false;
    streamAbort = null;
    _setAskBtnSend();
  }
}

// ══════════════════════════════════════════════════════════════════
// FEATURE: MULTI-LANGUAGE (auto-detect via browser)
// ══════════════════════════════════════════════════════════════════

function detectLang() {
  return navigator.language || navigator.userLanguage || 'en';
}

// ══════════════════════════════════════════════════════════════════
// OVERRIDE addBotAnswer to include regen + branch + speak buttons
// ══════════════════════════════════════════════════════════════════

const __origAddBotAnswer = addBotAnswer;
function addBotAnswer(text, sources=[], scroll=true, msgId=null) {
  const row = document.createElement('div'); row.className = 'msg-row bot';
  const b   = document.createElement('div'); b.className = 'msg-bub';
  const c   = document.createElement('div'); c.className = 'md-content';
  c.innerHTML = marked.parse(text); addCopyBtns(c);
  const s = document.createElement('div'); renderSrcs(s, sources);

  const acts = document.createElement('div'); acts.className = 'msg-actions';
  acts.innerHTML = `
    <button class="msg-act-btn" onclick="navigator.clipboard.writeText(this.closest('.msg-bub').querySelector('.md-content').innerText);toast('Copied!','success')" title="Copy">📋 Copy</button>
    <button class="msg-act-btn" onclick="speakText(this.closest('.msg-bub').querySelector('.md-content').innerText)" title="Read aloud">🔊 Speak</button>
    ${msgId ? `
    <button class="msg-act-btn" onclick="regenerateMsg(${msgId}, this.closest('.msg-bub'))" title="Regenerate">🔄 Retry</button>
    <button class="msg-act-btn" onclick="branchChat(${msgId})" title="Branch from here">🌿 Branch</button>
    <button class="msg-act-btn" onclick="sendFeedback(${msgId},1,this)" title="Good">👍</button>
    <button class="msg-act-btn" onclick="sendFeedback(${msgId},-1,this)" title="Bad">👎</button>` : ''}
  `;

  b.appendChild(c); b.appendChild(s); b.appendChild(acts);
  row.innerHTML = `<div class="msg-av">🧠</div>`;
  row.appendChild(b);
  chatWin.appendChild(row);
  if (scroll) scrollWin();
}

// ── Wire up share button in topbar ─────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Load saved prompts on init
  loadSavedPrompts();

  // Close modals on backdrop click
  ['promptsModal', 'shareModal'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', e => { if (e.target === el) el.classList.add('hidden'); });
  });

  // Save prompt shortcut: Ctrl+S in input
  qInput.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveCurrentPrompt(); }
  });
});

function closePromptsPanel() {
  document.getElementById('promptsModal').classList.add('hidden');
}

// ══════════════════════════════════════════════════════════════════
// SECURITY: EMAIL VERIFICATION, 2FA, SESSIONS
// ══════════════════════════════════════════════════════════════════

// ── Email verification banner ──────────────────────────────────────
function checkEmailVerification() {
  if (!currentUser) return;
  if (currentUser.email_verified === false) {
    const banner = document.createElement('div');
    banner.id = 'verifyBanner';
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:linear-gradient(90deg,#f59e0b,#d97706);color:#fff;padding:.5rem 1rem;font-size:.8rem;display:flex;align-items:center;justify-content:center;gap:.75rem';
    banner.innerHTML = `⚠️ Please verify your email address. <button onclick="resendVerification()" style="background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.4);color:#fff;padding:.2rem .6rem;border-radius:5px;cursor:pointer;font-size:.75rem">Resend Email</button> <button onclick="this.parentElement.remove()" style="background:none;border:none;color:#fff;cursor:pointer;margin-left:.5rem;font-size:1rem">✕</button>`;
    document.body.prepend(banner);
  }
  // Show verified badge in profile
  const desc = document.getElementById('emailVerifiedDesc');
  const btn  = document.getElementById('resendVerifyBtn');
  if (desc) {
    if (currentUser.email_verified) {
      desc.textContent = '✅ Verified';
      desc.style.color = 'var(--cyan)';
    } else {
      desc.textContent = '⚠️ Not verified — check your inbox';
      desc.style.color = '#f59e0b';
      if (btn) btn.style.display = 'block';
    }
  }
}

async function resendVerification() {
  const r = await api('/api/auth/resend-verification', {method: 'POST'});
  const d = await r.json();
  toast(d.message || 'Verification email sent', 'success');
}

// ── 2FA ────────────────────────────────────────────────────────────
let twoFaSecret = '';

async function toggle2FA() {
  const user = await (await api('/api/auth/me')).json();
  if (user.user?.totp_enabled) {
    // Show disable flow
    document.getElementById('twoFaSetup').classList.add('hidden');
    document.getElementById('twoFaDisable').classList.remove('hidden');
    document.getElementById('twoFaBtn').textContent = 'Disable 2FA';
    document.getElementById('twoFaBtn').style.background = '#dc2626';
  } else {
    // Setup flow
    document.getElementById('twoFaDisable').classList.add('hidden');
    const r = await api('/api/auth/2fa/setup', {method: 'POST'});
    const d = await r.json();
    if (!r.ok) { showSecAlert(d.error, 'error'); return; }
    twoFaSecret = d.secret;
    document.getElementById('twoFaQR').src = d.qr;
    document.getElementById('twoFaSetup').classList.remove('hidden');
    document.getElementById('twoFaBtn').textContent = 'Cancel';
    document.getElementById('twoFaBtn').onclick = () => {
      document.getElementById('twoFaSetup').classList.add('hidden');
      document.getElementById('twoFaBtn').textContent = 'Enable 2FA';
      document.getElementById('twoFaBtn').onclick = toggle2FA;
    };
  }
}

async function confirm2FA() {
  const code = document.getElementById('twoFaCode').value.trim();
  if (!code) return;
  const r = await api('/api/auth/2fa/verify', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({code})
  });
  const d = await r.json();
  if (r.ok) {
    showSecAlert('2FA enabled successfully!', 'success');
    document.getElementById('twoFaSetup').classList.add('hidden');
    document.getElementById('twoFaBtn').textContent = 'Disable 2FA';
    document.getElementById('twoFaBtn').style.background = '#dc2626';
    document.getElementById('twoFaBtn').onclick = toggle2FA;
    toast('2FA is now active 🔐', 'success');
  } else {
    showSecAlert(d.error || 'Invalid code', 'error');
  }
}

async function do2FADisable() {
  const code = document.getElementById('twoFaDisableCode').value.trim();
  if (!code) return;
  const r = await api('/api/auth/2fa/disable', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({code})
  });
  const d = await r.json();
  if (r.ok) {
    showSecAlert('2FA disabled', 'success');
    document.getElementById('twoFaDisable').classList.add('hidden');
    document.getElementById('twoFaBtn').textContent = 'Enable 2FA';
    document.getElementById('twoFaBtn').style.background = 'var(--purple)';
    document.getElementById('twoFaBtn').onclick = toggle2FA;
    toast('2FA disabled', 'info');
  } else {
    showSecAlert(d.error || 'Invalid code', 'error');
  }
}

function showSecAlert(msg, type) {
  const el = document.getElementById('secAlert');
  if (!el) return;
  el.textContent = msg;
  el.className = 'pp-alert ' + type;
}

// ── Session management ─────────────────────────────────────────────
async function loadSessions() {
  const r = await api('/api/auth/sessions');
  const d = await r.json();
  const list = document.getElementById('sessionsList');
  if (!list) return;
  const sessions = d.sessions || [];
  if (!sessions.length) {
    list.innerHTML = '<p style="color:var(--text3);font-size:.78rem">No active sessions found.</p>';
    return;
  }
  list.innerHTML = sessions.map(s => `
    <div class="session-item">
      <div class="session-info">
        <div class="session-device">${esc(s.device_info.slice(0, 60) || 'Unknown device')}</div>
        <div class="session-meta">${esc(s.ip_address || 'Unknown IP')} · Last seen ${new Date(s.last_seen).toLocaleString()}</div>
      </div>
      <button class="pp-danger-btn" style="font-size:.68rem" onclick="revokeSession(${s.id})">Revoke</button>
    </div>`).join('');
}

async function revokeSession(id) {
  await api(`/api/auth/sessions/${id}`, {method: 'DELETE'});
  toast('Session revoked', 'info');
  loadSessions();
}

async function revokeAllSessions() {
  if (!confirm('Revoke all other sessions? You will stay logged in on this device.')) return;
  await api('/api/auth/sessions/revoke-all', {method: 'POST'});
  toast('All other sessions revoked', 'success');
  loadSessions();
}

// ── Override ppTab to load sessions/security on open ──────────────
const _origPpTab = ppTab;
function ppTab(tab) {
  document.querySelectorAll('.pp-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.pp-body').forEach(b => b.classList.add('hidden'));
  event.target.classList.add('active');
  const bodyId = 'pp' + tab.charAt(0).toUpperCase() + tab.slice(1);
  const body = document.getElementById(bodyId);
  if (body) body.classList.remove('hidden');
  if (tab === 'sessions') loadSessions();
  if (tab === 'security') checkEmailVerification();
}

// ── Check verification on load ─────────────────────────────────────
const _origLoadUserFinal = loadUser;
loadUser = async function() {
  await _origLoadUserFinal();
  if (currentUser) checkEmailVerification();
};


// ══════════════════════════════════════════════════════════════════
// WORKSPACES
// ══════════════════════════════════════════════════════════════════

let allWorkspaces = [];
let currentWsId = null;

async function loadWorkspaces() {
  const r = await api('/api/workspaces');
  const d = await r.json();
  allWorkspaces = d.workspaces || [];
  renderWsGrid();
}

function renderWsGrid() {
  const g = document.getElementById('wsGrid');
  if (!g) return;
  if (!allWorkspaces.length) {
    g.innerHTML = `<div class="ws-empty">No workspaces yet.<br>Create one to collaborate with your team.</div>`;
    return;
  }
  g.innerHTML = allWorkspaces.map(ws => `
    <div class="ws-card" onclick="openWsDetail(${ws.id},'${esc(ws.name)}')">
      <div class="ws-card-name">🏢 ${esc(ws.name)}</div>
      ${ws.description ? `<div class="ws-card-desc">${esc(ws.description)}</div>` : ''}
      <div class="ws-card-meta">
        <span class="ws-role-badge ${ws.my_role}">${ws.my_role}</span>
        <span style="font-size:.7rem;color:var(--text3)">${ws.owner_name}</span>
      </div>
      <div class="ws-card-footer">
        <span style="font-size:.7rem;color:var(--text3)">${ws.created_at ? ws.created_at.slice(0,10) : ''}</span>
        ${ws.my_role === 'owner' ? `<button class="ws-del-btn" onclick="event.stopPropagation();deleteWorkspace(${ws.id})">🗑 Delete</button>` : ''}
      </div>
    </div>
  `).join('');
}

function openNewWorkspaceModal() {
  document.getElementById('wsNameInput').value = '';
  document.getElementById('wsDescInput').value = '';
  document.getElementById('newWsModal').classList.remove('hidden');
}

async function createWorkspace() {
  const name = document.getElementById('wsNameInput').value.trim();
  const desc = document.getElementById('wsDescInput').value.trim();
  if (!name) { toast('Name required', 'warning'); return; }
  const r = await api('/api/workspaces', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, description: desc})
  });
  const d = await r.json();
  if (!r.ok) { toast(d.error || 'Failed', 'error'); return; }
  document.getElementById('newWsModal').classList.add('hidden');
  toast('Workspace created', 'success');
  await loadWorkspaces();
}

async function deleteWorkspace(id) {
  if (!confirm('Delete this workspace? This cannot be undone.')) return;
  await api(`/api/workspaces/${id}`, {method: 'DELETE'});
  toast('Workspace deleted', 'success');
  await loadWorkspaces();
}

async function openWsDetail(id, name) {
  currentWsId = id;
  document.getElementById('wsGrid').classList.add('hidden');
  const detail = document.getElementById('wsDetail');
  detail.classList.remove('hidden');
  document.getElementById('wsDetailName').textContent = name;

  // Determine role
  const ws = allWorkspaces.find(w => w.id === id);
  const role = ws ? ws.my_role : 'viewer';
  const roleBadge = document.getElementById('wsDetailRole');
  roleBadge.textContent = role;
  roleBadge.className = `ws-role-badge ${role}`;

  const canEdit   = ['owner','admin','editor'].includes(role);
  const canManage = ['owner','admin'].includes(role);

  document.getElementById('wsInviteBtn').style.display  = canManage ? '' : 'none';
  document.getElementById('wsEditBtn').style.display    = canManage ? '' : 'none';
  document.getElementById('wsDocActions').style.display = canEdit   ? 'flex' : 'none';

  await Promise.all([loadWsDocs(id), loadWsMembers(id)]);

  if (canEdit) {
    const sel = document.getElementById('wsDocSelect');
    sel.innerHTML = allDocuments.map(d => `<option value="${d.id}">${esc(d.orig_name)}</option>`).join('');
  }
}

function openEditWsModal() {
  const ws = allWorkspaces.find(w => w.id === currentWsId);
  if (!ws) return;
  document.getElementById('editWsNameInput').value = ws.name;
  document.getElementById('editWsDescInput').value = ws.description || '';
  document.getElementById('editWsModal').classList.remove('hidden');
}

async function saveEditWorkspace() {
  const name = document.getElementById('editWsNameInput').value.trim();
  const desc = document.getElementById('editWsDescInput').value.trim();
  if (!name) { toast('Name required', 'warning'); return; }
  const r = await api(`/api/workspaces/${currentWsId}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, description: desc})
  });
  const d = await r.json();
  if (!r.ok) { toast(d.error || 'Failed', 'error'); return; }
  document.getElementById('editWsModal').classList.add('hidden');
  document.getElementById('wsDetailName').textContent = name;
  toast('Workspace updated', 'success');
  await loadWorkspaces();
}

function closeWsDetail() {
  currentWsId = null;
  document.getElementById('wsDetail').classList.add('hidden');
  document.getElementById('wsGrid').classList.remove('hidden');
}

async function loadWsDocs(id) {
  const r = await api(`/api/workspaces/${id}/documents`);
  const d = await r.json();
  const list = document.getElementById('wsDocList');
  const docs = d.documents || [];
  if (!docs.length) { list.innerHTML = '<div style="font-size:.78rem;color:var(--text3)">No documents yet.</div>'; return; }
  list.innerHTML = docs.map(doc => `
    <div class="ws-doc-item">
      <span>📄</span>
      <span title="${esc(doc.orig_name)}">${esc(doc.orig_name)}</span>
      <span style="font-size:.68rem;color:var(--text3)">${doc.uploaded_by_name}</span>
      <button class="ws-doc-remove" onclick="removeWsDoc(${doc.id})">✕</button>
    </div>
  `).join('');
}

async function addDocToWs() {
  const docId = parseInt(document.getElementById('wsDocSelect').value);
  if (!docId || !currentWsId) return;
  const r = await api(`/api/workspaces/${currentWsId}/documents`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({doc_id: docId})
  });
  if (!r.ok) { const d = await r.json(); toast(d.error || 'Failed', 'error'); return; }
  toast('Document added to workspace', 'success');
  await loadWsDocs(currentWsId);
}

async function removeWsDoc(docId) {
  await api(`/api/workspaces/${currentWsId}/documents/${docId}`, {method: 'DELETE'});
  await loadWsDocs(currentWsId);
}

async function loadWsMembers(id) {
  const r = await api(`/api/workspaces/${id}/members`);
  const d = await r.json();
  const list = document.getElementById('wsMemberList');
  const members = d.members || [];
  const ws = allWorkspaces.find(w => w.id === id);
  const myRole = ws ? ws.my_role : 'viewer';
  const canManage = ['owner','admin'].includes(myRole);

  if (!members.length) {
    list.innerHTML = '<div style="font-size:.78rem;color:var(--text3)">No members yet. Invite someone to get started.</div>';
    return;
  }

  list.innerHTML = members.map(m => `
    <div class="ws-member-item">
      <div class="ws-member-av">${(m.user_name||m.email)[0].toUpperCase()}</div>
      <div class="ws-member-info">
        <div class="ws-member-name">${esc(m.user_name || '—')}
          ${m.status === 'pending' ? '<span style="font-size:.65rem;color:#f59e0b;margin-left:.3rem">⏳ pending</span>' : ''}
        </div>
        <div class="ws-member-email">${esc(m.email)}</div>
      </div>
      ${canManage
        ? `<select class="cmp-input" style="font-size:.75rem;padding:.2rem .4rem;width:90px"
             onchange="updateMemberRole(${m.id}, this.value)">
             <option value="viewer"  ${m.role==='viewer'  ? 'selected':''}>Viewer</option>
             <option value="editor"  ${m.role==='editor'  ? 'selected':''}>Editor</option>
             <option value="admin"   ${m.role==='admin'   ? 'selected':''}>Admin</option>
           </select>`
        : `<span class="ws-role-badge ${m.role}">${m.role}</span>`
      }
      ${canManage ? `<button class="ws-member-remove" title="Remove member" onclick="removeWsMember(${m.id})">✕</button>` : ''}
    </div>
  `).join('');
}

async function updateMemberRole(memberId, role) {
  const r = await api(`/api/workspaces/${currentWsId}/members/${memberId}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({role})
  });
  if (!r.ok) {
    const d = await r.json();
    toast(d.error || 'Failed to update role', 'error');
    await loadWsMembers(currentWsId); // revert UI
    return;
  }
  toast('Role updated', 'success');
}

function openInviteModal() {
  document.getElementById('inviteEmail').value = '';
  document.getElementById('inviteModal').classList.remove('hidden');
}

async function inviteMember() {
  const email = document.getElementById('inviteEmail').value.trim().toLowerCase();
  const role  = document.getElementById('inviteRole').value;
  if (!email) { toast('Email required', 'warning'); return; }
  const r = await api(`/api/workspaces/${currentWsId}/members`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email, role})
  });
  const d = await r.json();
  if (!r.ok) { toast(d.error || 'Failed', 'error'); return; }
  document.getElementById('inviteModal').classList.add('hidden');
  document.getElementById('inviteEmail').value = '';
  toast(`Invitation sent to ${email}`, 'success');
  // Refresh both the workspace list (roles) and member list
  await loadWorkspaces();
  await loadWsMembers(currentWsId);
}

async function removeWsMember(memberId) {
  if (!confirm('Remove this member from the workspace?')) return;
  const r = await api(`/api/workspaces/${currentWsId}/members/${memberId}`, {method: 'DELETE'});
  if (!r.ok) {
    const d = await r.json();
    toast(d.error || 'Failed to remove member', 'error');
    return;
  }
  toast('Member removed', 'info');
  await loadWsMembers(currentWsId);
}


// ══════════════════════════════════════════════════════════════════
// ACTIVITY FEED
// ══════════════════════════════════════════════════════════════════

const ACTION_LABELS = {
  uploaded_document: ['📤', 'uploaded'],
  deleted_document:  ['🗑', 'deleted'],
  created_workspace: ['🏢', 'created workspace'],
  deleted_workspace: ['❌', 'deleted workspace'],
  invited_member:    ['👋', 'invited'],
  added_document:    ['➕', 'added document to workspace'],
};

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso)) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff/60) + 'm ago';
  if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
  return Math.floor(diff/86400) + 'd ago';
}

async function loadActivity() {
  const r = await api('/api/activity');
  const d = await r.json();
  const feed = document.getElementById('activityFeed');
  if (!feed) return;
  const items = d.activity || [];
  if (!items.length) {
    feed.innerHTML = '<div class="act-empty">No activity yet. Start uploading documents and chatting!</div>';
    return;
  }
  feed.innerHTML = items.map(item => {
    const [icon, verb] = ACTION_LABELS[item.action] || ['⚡', item.action];
    return `
      <div class="act-item">
        <div class="act-icon">${icon}</div>
        <div class="act-av">${(item.user_name||'?')[0].toUpperCase()}</div>
        <div class="act-body">
          <div class="act-text"><strong>${esc(item.user_name||'Someone')}</strong> ${verb}${item.target_name ? ` <strong>${esc(item.target_name)}</strong>` : ''}</div>
          <div class="act-time">${timeAgo(item.created_at)}</div>
        </div>
      </div>
    `;
  }).join('');
}


// ══════════════════════════════════════════════════════════════════
// COMMENTS ON ANSWERS
// ══════════════════════════════════════════════════════════════════

async function toggleComments(msgId, btn) {
  const section = document.getElementById(`comments-${msgId}`);
  if (!section) return;
  const isHidden = section.classList.contains('hidden');
  if (isHidden) {
    section.classList.remove('hidden');
    btn.textContent = '💬 Hide comments';
    await loadComments(msgId);
  } else {
    section.classList.add('hidden');
    btn.textContent = '💬 Comments';
  }
}

async function loadComments(msgId) {
  const r = await api(`/api/messages/${msgId}/comments`);
  const d = await r.json();
  const list = document.getElementById(`comment-list-${msgId}`);
  if (!list) return;
  const comments = d.comments || [];
  if (!comments.length) {
    list.innerHTML = '<div style="font-size:.72rem;color:var(--text3);padding:.2rem 0">No comments yet.</div>';
    return;
  }
  list.innerHTML = comments.map(c => `
    <div class="comment-item" id="comment-${c.id}">
      <div class="comment-av">${(c.user_name||'?')[0].toUpperCase()}</div>
      <div class="comment-body">
        <div class="comment-author">${esc(c.user_name||'User')}
          ${currentUser && c.user_id === currentUser.id ? `<button class="comment-del" onclick="deleteComment(${c.id},${msgId})">✕</button>` : ''}
        </div>
        <div class="comment-text">${esc(c.content)}</div>
        <div class="comment-time">${timeAgo(c.created_at)}</div>
      </div>
    </div>
  `).join('');
}

async function submitComment(msgId) {
  const input = document.getElementById(`comment-input-${msgId}`);
  const content = input.value.trim();
  if (!content) return;
  const r = await api(`/api/messages/${msgId}/comments`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({content})
  });
  if (!r.ok) { toast('Failed to post comment', 'error'); return; }
  input.value = '';
  await loadComments(msgId);
}

async function deleteComment(commentId, msgId) {
  await api(`/api/comments/${commentId}`, {method: 'DELETE'});
  await loadComments(msgId);
}

// Inject comment section into bot messages
function addCommentSection(bubbleEl, msgId) {
  if (!msgId) return;
  const section = document.createElement('div');
  section.className = 'comments-section';
  section.innerHTML = `
    <button class="comments-toggle" onclick="toggleComments(${msgId}, this)">💬 Comments</button>
    <div class="comments-list hidden" id="comments-${msgId}">
      <div id="comment-list-${msgId}"></div>
      <div class="comment-input-row">
        <input class="comment-input" id="comment-input-${msgId}" placeholder="Add a comment…" onkeydown="if(event.key==='Enter')submitComment(${msgId})"/>
        <button class="comment-submit" onclick="submitComment(${msgId})">Post</button>
      </div>
    </div>
  `;
  bubbleEl.appendChild(section);
}


// ══════════════════════════════════════════════════════════════════
// @MENTION DOC SCOPING
// ══════════════════════════════════════════════════════════════════

let mentionDoc = null;  // currently scoped document name
let mentionActive = false;
let mentionQuery = '';
let mentionStart = 0;

const mentionDropdown = document.getElementById('mentionDropdown');

qInput.addEventListener('input', handleMentionInput);
qInput.addEventListener('keydown', handleMentionKeydown);

function handleMentionInput(e) {
  const val = qInput.value;
  const pos = qInput.selectionStart;
  // Find @ before cursor
  const before = val.slice(0, pos);
  const atIdx = before.lastIndexOf('@');
  if (atIdx !== -1 && (atIdx === 0 || /\s/.test(before[atIdx-1]))) {
    mentionQuery = before.slice(atIdx + 1).toLowerCase();
    mentionStart = atIdx;
    mentionActive = true;
    showMentionDropdown(mentionQuery);
  } else {
    hideMentionDropdown();
  }
}

function showMentionDropdown(query) {
  const matches = allDocuments.filter(d => d.orig_name.toLowerCase().includes(query));
  if (!matches.length) { hideMentionDropdown(); return; }
  mentionDropdown.innerHTML = matches.slice(0, 6).map((d, i) => `
    <div class="mention-item" data-name="${esc(d.orig_name)}" onclick="selectMention('${esc(d.orig_name)}')">
      <span class="mention-item-icon">📄</span>
      <span class="mention-item-name">${esc(d.orig_name)}</span>
      <span class="mention-item-pages">${d.pages}p</span>
    </div>
  `).join('');
  mentionDropdown.classList.remove('hidden');
}

function hideMentionDropdown() {
  mentionActive = false;
  mentionDropdown.classList.add('hidden');
}

function selectMention(docName) {
  // Replace @query with the doc name chip (stored as mentionDoc)
  const val = qInput.value;
  const before = val.slice(0, mentionStart);
  const after = val.slice(qInput.selectionStart);
  qInput.value = before + after;
  mentionDoc = docName;
  hideMentionDropdown();
  // Show scope chip above input
  renderMentionChip(docName);
  qInput.focus();
}

function renderMentionChip(name) {
  let chip = document.getElementById('mentionChip');
  if (!chip) {
    chip = document.createElement('div');
    chip.id = 'mentionChip';
    chip.style.cssText = 'padding:.3rem 1rem .1rem;font-size:.75rem;color:var(--text2)';
    document.querySelector('.chat-foot').insertBefore(chip, document.querySelector('.chat-input-box'));
  }
  chip.innerHTML = `<span class="mention-scope-chip">📄 ${esc(name)} <button onclick="clearMention()">✕</button></span> Scoped to this document`;
}

function clearMention() {
  mentionDoc = null;
  const chip = document.getElementById('mentionChip');
  if (chip) chip.remove();
}

function handleMentionKeydown(e) {
  if (!mentionActive) return;
  if (e.key === 'Escape') { hideMentionDropdown(); e.preventDefault(); }
}

// Patch sendQ to pass mention_doc
const _origSendQ = sendQ;
sendQ = async function() {
  // Temporarily patch the ask body to include mention_doc
  window._currentMentionDoc = mentionDoc;
  await _origSendQ();
};

// Patch the fetch in the ask SSE call — we intercept via a wrapper
// The actual injection happens in the ask route body builder
const _origApi = api;
// Override the ask endpoint body to include mention_doc
const _origFetch = window.fetch;
window.fetch = function(url, opts) {
  if (typeof url === 'string' && url.includes('/ask') && opts && opts.body && window._currentMentionDoc) {
    try {
      const body = JSON.parse(opts.body);
      if (body && typeof body === 'object') {
        body.mention_doc = window._currentMentionDoc;
        opts = {...opts, body: JSON.stringify(body)};
      }
    } catch(e) { /* ignore parse errors */ }
  }
  return _origFetch.call(this, url, opts);
};


// ══════════════════════════════════════════════════════════════════
// ENHANCED ANALYTICS
// ══════════════════════════════════════════════════════════════════

async function loadAnalyticsExtended() {
  const r = await api('/api/analytics/extended');
  if (!r.ok) return;
  const d = await r.json();

  // Update stat cards
  document.getElementById('statDocs').textContent    = d.docs;
  document.getElementById('statChats').textContent   = d.chats;
  document.getElementById('statQueries').textContent = d.queries;
  document.getElementById('statChunks').textContent  = d.chunks;

  const ext = document.getElementById('analyticsExt');
  if (!ext) return;

  // Build daily queries bar chart
  const daily = d.daily_queries || [];
  const maxCnt = Math.max(...daily.map(x => x.cnt), 1);
  const bars = daily.length ? daily.map(x => {
    const h = Math.round((x.cnt / maxCnt) * 70);
    const label = x.day ? x.day.slice(5) : '';
    return `<div class="bar-col"><div class="bar-fill" style="height:${h}px" title="${x.cnt} queries"></div><div class="bar-label">${label}</div></div>`;
  }).join('') : '<div style="color:var(--text3);font-size:.8rem">No data yet</div>';

  // Top docs
  const topDocs = (d.top_docs || []).map(doc => `
    <div class="top-doc-item">
      <span class="top-doc-name" title="${esc(doc.orig_name)}">${esc(doc.orig_name)}</span>
      <span class="top-doc-chunks">${doc.chunks} chunks</span>
    </div>
  `).join('') || '<div style="color:var(--text3);font-size:.8rem">No documents yet</div>';

  // Feedback
  const pos = d.feedback?.['1'] || 0;
  const neg = d.feedback?.['-1'] || 0;
  const total = pos + neg;
  const pct = total ? Math.round((pos/total)*100) : 0;

  ext.innerHTML = `
    <div class="analytics-row">
      <div class="analytics-card">
        <div class="analytics-card-title">📊 Queries (last 7 days)</div>
        <div class="bar-chart">${bars}</div>
      </div>
      <div class="analytics-card">
        <div class="analytics-card-title">📄 Top Documents by Size</div>
        ${topDocs}
      </div>
    </div>
    <div class="analytics-row">
      <div class="analytics-card">
        <div class="analytics-card-title">👍 Answer Feedback</div>
        ${total ? `
          <div class="feedback-row">
            <div class="fb-stat pos">👍 ${pos} helpful</div>
            <div class="fb-stat neg">👎 ${neg} not helpful</div>
          </div>
          <div style="margin-top:.6rem;background:var(--border);border-radius:999px;height:6px;overflow:hidden">
            <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,#34d399,#10b981);border-radius:999px;transition:width .5s"></div>
          </div>
          <div style="font-size:.72rem;color:var(--text3);margin-top:.3rem">${pct}% positive</div>
        ` : '<div style="color:var(--text3);font-size:.8rem">No feedback yet</div>'}
      </div>
      <div class="analytics-card">
        <div class="analytics-card-title">📈 Overview</div>
        <div style="display:flex;flex-direction:column;gap:.4rem;margin-top:.2rem">
          <div style="display:flex;justify-content:space-between;font-size:.82rem"><span style="color:var(--text2)">Total pages indexed</span><strong>${d.pages}</strong></div>
          <div style="display:flex;justify-content:space-between;font-size:.82rem"><span style="color:var(--text2)">Avg chunks/doc</span><strong>${d.docs ? Math.round(d.chunks/d.docs) : 0}</strong></div>
          <div style="display:flex;justify-content:space-between;font-size:.82rem"><span style="color:var(--text2)">Avg queries/chat</span><strong>${d.chats ? Math.round(d.queries/d.chats) : 0}</strong></div>
        </div>
      </div>
    </div>
  `;
}


// ══════════════════════════════════════════════════════════════════
// PATCH switchView to load new views + sync mobile bottom nav
// ══════════════════════════════════════════════════════════════════

const _origSwitchView = switchView;
switchView = function(v) {
  _origSwitchView(v);
  if (v === 'workspaces') { loadWorkspaces(); closeWsDetail(); }
  if (v === 'activity')   { loadActivity(); }
  if (v === 'analytics')  { loadAnalyticsExtended(); }
  // Sync mobile bottom nav
  if (isMobile()) {
    const btn = document.querySelector(`.mob-nav-btn[data-view="${v}"]`);
    mobNavActive(btn || null);
  }
};

// ══════════════════════════════════════════════════════════════════
// PATCH addBotAnswer to inject comment section
// ══════════════════════════════════════════════════════════════════

const _origAddBotAnswerComments = addBotAnswer;
addBotAnswer = function(text, sources, scroll, msgId) {
  _origAddBotAnswerComments(text, sources, scroll, msgId);
  if (msgId) {
    // Find the last bot bubble and add comments
    const rows = chatWin.querySelectorAll('.msg-row.bot');
    const lastRow = rows[rows.length - 1];
    if (lastRow) {
      const bub = lastRow.querySelector('.msg-bub');
      if (bub) addCommentSection(bub, msgId);
    }
  }
};


// ══════════════════════════════════════════════════════════════════
// FULL ANALYTICS DASHBOARD
// ══════════════════════════════════════════════════════════════════

async function loadAnalyticsFull() {
  const container = document.getElementById('analyticsFull');
  if (!container) return;
  container.innerHTML = '<div style="padding:1rem 1.5rem;color:var(--text3);font-size:.82rem">Loading analytics…</div>';

  try {
    const r = await api('/api/analytics/full');
    if (!r.ok) { container.innerHTML = ''; return; }
    const d = await r.json();
    renderAnalyticsFull(container, d);
  } catch(e) {
    container.innerHTML = '';
  }
}

function renderAnalyticsFull(container, d) {
  const daily30 = d.daily_30 || [];
  const topics  = d.topics   || [];
  const heatmap = d.heatmap  || [];
  const quality = d.quality_trend || [];
  const topRefs = d.top_by_refs   || [];

  // ── 30-day bar chart ──────────────────────────────────────────
  const max30 = Math.max(...daily30.map(x => x.cnt), 1);
  const bars30 = daily30.length
    ? daily30.map(x => {
        const h = Math.max(2, Math.round((x.cnt / max30) * 90));
        const lbl = x.day ? x.day.slice(5) : '';
        return `<div class="bar-col-30">
          <div class="bar-fill-30" style="height:${h}px" title="${lbl}: ${x.cnt} queries"></div>
          <div class="bar-label-30">${lbl}</div>
        </div>`;
      }).join('')
    : '<div style="color:var(--text3);font-size:.8rem;padding:.5rem">No queries yet</div>';

  // ── Topic cloud ───────────────────────────────────────────────
  const maxTopic = Math.max(...topics.map(t => t.count), 1);
  const TOPIC_COLORS = [
    ['rgba(139,92,246,.2)','rgba(139,92,246,.5)','var(--purple-l)'],
    ['rgba(34,211,238,.15)','rgba(34,211,238,.4)','var(--cyan)'],
    ['rgba(16,185,129,.15)','rgba(16,185,129,.4)','#34d399'],
    ['rgba(245,158,11,.15)','rgba(245,158,11,.4)','#fbbf24'],
  ];
  const topicHtml = topics.length
    ? topics.map((t, i) => {
        const size = 0.68 + (t.count / maxTopic) * 0.45;
        const [bg, border, color] = TOPIC_COLORS[i % TOPIC_COLORS.length];
        return `<span class="topic-chip" style="font-size:${size.toFixed(2)}rem;background:${bg};border-color:${border};color:${color}" title="${t.count} occurrences">${esc(t.word)}</span>`;
      }).join('')
    : '<span style="color:var(--text3);font-size:.8rem">Ask some questions to see topics</span>';

  // ── Page heatmap ──────────────────────────────────────────────
  const maxHeat = Math.max(...heatmap.map(h => h.count), 1);
  const heatHtml = heatmap.length
    ? heatmap.map(h => {
        const pct = Math.round((h.count / maxHeat) * 100);
        return `<div class="heatmap-item">
          <div class="heatmap-label" title="${esc(h.key)}">${esc(h.key)}</div>
          <div class="heatmap-bar-wrap"><div class="heatmap-bar" style="width:${pct}%"></div></div>
          <div class="heatmap-count">${h.count}</div>
        </div>`;
      }).join('')
    : '<div style="color:var(--text3);font-size:.8rem">No citations yet — ask questions about your documents</div>';

  // ── Quality trend ─────────────────────────────────────────────
  const maxQ = Math.max(...quality.map(q => (q.pos||0) + (q.neg||0)), 1);
  const qualHtml = quality.length
    ? quality.map(q => {
        const total = (q.pos||0) + (q.neg||0);
        const posH = Math.max(1, Math.round(((q.pos||0) / maxQ) * 70));
        const negH = Math.max(1, Math.round(((q.neg||0) / maxQ) * 70));
        const lbl = q.day ? q.day.slice(5) : '';
        return `<div class="quality-col" title="${lbl}: 👍${q.pos||0} 👎${q.neg||0}">
          <div class="quality-pos" style="height:${posH}px"></div>
          <div class="quality-neg" style="height:${negH}px"></div>
          <div class="quality-label">${lbl}</div>
        </div>`;
      }).join('')
    : '<div style="color:var(--text3);font-size:.8rem">No feedback yet</div>';

  // ── Top docs by reference ─────────────────────────────────────
  const refHtml = topRefs.length
    ? topRefs.map((doc, i) => `
        <div class="ref-doc-item">
          <div class="ref-doc-rank">#${i+1}</div>
          <div class="ref-doc-name" title="${esc(doc.orig_name)}">${esc(doc.orig_name)}</div>
          <div class="ref-doc-count">${doc.ref_count} refs</div>
        </div>`)
      .join('')
    : '<div style="color:var(--text3);font-size:.8rem">No documents yet</div>';

  container.innerHTML = `
    <div class="analytics-row">
      <div class="analytics-card" style="grid-column:1/-1">
        <div class="analytics-card-title">📊 Queries per Day — Last 30 Days</div>
        <div class="bar-chart-30">${bars30}</div>
      </div>
    </div>

    <div class="analytics-row">
      <div class="analytics-card">
        <div class="analytics-card-title">🔥 Most-Asked Topics</div>
        <div class="topic-cloud">${topicHtml}</div>
      </div>
      <div class="analytics-card">
        <div class="analytics-card-title">📄 Top Documents by Reference</div>
        <div>${refHtml}</div>
      </div>
    </div>

    <div class="analytics-row">
      <div class="analytics-card" style="grid-column:1/-1">
        <div class="analytics-card-title">🗺️ Document Coverage Heatmap — Most-Cited Pages</div>
        <div class="heatmap-list">${heatHtml}</div>
      </div>
    </div>

    <div class="analytics-row">
      <div class="analytics-card" style="grid-column:1/-1">
        <div class="analytics-card-title">👍 Answer Quality Trend — Last 30 Days <span style="font-size:.65rem;color:var(--text3);font-weight:400;margin-left:.5rem">green = helpful · red = not helpful</span></div>
        <div class="quality-chart">${qualHtml}</div>
      </div>
    </div>
  `;
}

function exportAnalyticsCSV() {
  window.location.href = '/api/analytics/export.csv';
}

// Patch the existing switchView analytics loader to also call loadAnalyticsFull
const _switchViewAnalyticsPatch = switchView;
switchView = function(v) {
  _switchViewAnalyticsPatch(v);
  if (v === 'analytics') loadAnalyticsFull();
};


// ══════════════════════════════════════════════════════════════════
// BILLING / TIER UI
// ══════════════════════════════════════════════════════════════════

const TIER_COLORS = { free: '#64748b', pro: '#8b5cf6', enterprise: '#22d3ee' };
const TIER_DESCS  = {
  free:       '5 docs · 20 queries/day · 1 workspace',
  pro:        '50 docs · 200 queries/day · 10 workspaces · API access',
  enterprise: 'Unlimited · API access · White-label · Priority support',
};
const TIER_PRICES = { free: 'Free', pro: '₹999/mo', enterprise: 'Contact us' };

async function loadBillingTab() {
  const r = await api('/api/billing/tier');
  if (!r.ok) return;
  const d = await r.json();
  const { tier, limits, usage } = d;

  // Current plan card
  document.getElementById('tierName').textContent = tier.charAt(0).toUpperCase() + tier.slice(1) + ' Plan';
  document.getElementById('tierDesc').textContent = TIER_DESCS[tier] || '';
  document.getElementById('tierBadgeWrap').innerHTML =
    `<span style="background:${TIER_COLORS[tier]}22;color:${TIER_COLORS[tier]};border:1px solid ${TIER_COLORS[tier]}44;padding:.2rem .65rem;border-radius:999px;font-size:.72rem;font-weight:700;text-transform:uppercase">${tier}</span>`;

  // Usage bars
  const qPct = Math.min(100, Math.round((usage.queries_today / limits.queries_per_day) * 100));
  const dPct = Math.min(100, Math.round((usage.docs / limits.docs) * 100));
  document.getElementById('tierUsage').innerHTML = `
    <div style="font-size:.75rem;color:var(--text2)">Queries today: <strong>${usage.queries_today} / ${limits.queries_per_day}</strong></div>
    <div style="background:var(--border);border-radius:999px;height:5px;overflow:hidden">
      <div style="height:100%;width:${qPct}%;background:${qPct>80?'#f87171':'var(--purple)'};border-radius:999px;transition:width .4s"></div>
    </div>
    <div style="font-size:.75rem;color:var(--text2);margin-top:.25rem">Documents: <strong>${usage.docs} / ${limits.docs}</strong></div>
    <div style="background:var(--border);border-radius:999px;height:5px;overflow:hidden">
      <div style="height:100%;width:${dPct}%;background:${dPct>80?'#f87171':'var(--cyan)'};border-radius:999px;transition:width .4s"></div>
    </div>
  `;

  // Upgrade options
  const opts = Object.entries(d.all_tiers).filter(([t]) => t !== tier);
  document.getElementById('tierOptions').innerHTML = opts.map(([t, lim]) => `
    <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.85rem;display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="font-size:.85rem;font-weight:600;color:${TIER_COLORS[t]}">${t.charAt(0).toUpperCase()+t.slice(1)}</div>
        <div style="font-size:.72rem;color:var(--text3);margin-top:.15rem">${TIER_DESCS[t]}</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:.85rem;font-weight:700;color:var(--text)">${TIER_PRICES[t]}</div>
        <button onclick="requestUpgrade('${t}')" style="margin-top:.3rem;background:${TIER_COLORS[t]};color:#fff;border:none;border-radius:6px;padding:.25rem .65rem;font-size:.72rem;cursor:pointer;font-family:inherit">Upgrade</button>
      </div>
    </div>
  `).join('');
}

async function requestUpgrade(tier) {
  const r = await api('/api/billing/upgrade', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tier})
  });
  const d = await r.json();
  toast(d.message, 'info', 5000);
}

// Patch ppTab to load billing/apikeys on open
const _origPpTabBilling = ppTab;
ppTab = function(tab) {
  _origPpTabBilling.call(this, tab);
  if (tab === 'billing') loadBillingTab();
  if (tab === 'apikeys') loadApiKeys();
  if (tab === 'sessions') loadSessions();
};


// ══════════════════════════════════════════════════════════════════
// API KEYS UI
// ══════════════════════════════════════════════════════════════════

async function loadApiKeys() {
  const r = await api('/api/keys');
  if (!r.ok) {
    document.getElementById('apiKeysList').innerHTML =
      '<div style="font-size:.75rem;color:var(--text3)">API keys require Pro or Enterprise plan.</div>';
    return;
  }
  const d = await r.json();
  const keys = d.keys || [];
  const list = document.getElementById('apiKeysList');
  if (!keys.length) {
    list.innerHTML = '<div style="font-size:.75rem;color:var(--text3)">No API keys yet.</div>';
    return;
  }
  list.innerHTML = keys.map(k => `
    <div style="display:flex;align-items:center;gap:.5rem;padding:.45rem .65rem;background:rgba(30,41,59,.6);border:1px solid var(--border);border-radius:8px">
      <div style="flex:1;min-width:0">
        <div style="font-size:.78rem;font-weight:500">${esc(k.label)}</div>
        <div style="font-size:.68rem;color:var(--text3)"><code>${esc(k.key_prefix)}…</code> · Created ${k.created_at ? k.created_at.slice(0,10) : '—'} · Last used: ${k.last_used ? k.last_used.slice(0,10) : 'Never'}</div>
      </div>
      <button onclick="deleteApiKey(${k.id})" style="background:none;border:none;color:var(--text3);cursor:pointer;font-size:.75rem;padding:.2rem .4rem;border-radius:4px;transition:all .15s" onmouseover="this.style.color='#ef4444'" onmouseout="this.style.color='var(--text3)'">✕</button>
    </div>
  `).join('');
}

async function createApiKey() {
  const label = document.getElementById('newKeyLabel').value.trim() || 'Default';
  const r = await api('/api/keys', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({label})
  });
  const d = await r.json();
  if (!r.ok) { toast(d.error || 'Failed', 'error'); return; }
  document.getElementById('newKeyValue').textContent = d.key.raw_key;
  document.getElementById('newKeyDisplay').classList.remove('hidden');
  document.getElementById('newKeyLabel').value = '';
  await loadApiKeys();
}

async function deleteApiKey(keyId) {
  if (!confirm('Delete this API key? Any apps using it will stop working.')) return;
  await api(`/api/keys/${keyId}`, {method: 'DELETE'});
  document.getElementById('newKeyDisplay').classList.add('hidden');
  await loadApiKeys();
}


// ══════════════════════════════════════════════════════════════════
// TIER LIMIT TOAST — show friendly message when limit hit
// ══════════════════════════════════════════════════════════════════

// Cache tier info so we don't hit the API on every send
let _tierCache = null;
let _tierCacheTime = 0;

async function getTierCached() {
  if (_tierCache && Date.now() - _tierCacheTime < 60000) return _tierCache;
  try {
    const r = await api('/api/billing/tier');
    if (r.ok) { _tierCache = await r.json(); _tierCacheTime = Date.now(); }
  } catch(e) {}
  return _tierCache;
}

const _origSendQTier = sendQ;
sendQ = async function() {
  try {
    const d = await getTierCached();
    if (d) {
      const { tier, limits, usage } = d;
      if (usage.queries_today >= limits.queries_per_day) {
        toast(`Daily limit reached (${limits.queries_per_day} queries on ${tier} plan). Open Profile → Plan to upgrade.`, 'warning', 6000);
        return;
      }
    }
  } catch(e) { /* non-blocking */ }
  await _origSendQTier();
  // Invalidate cache after sending so next check is fresh
  _tierCache = null;
};

// ══════════════════════════════════════════════════════════════════
// MOBILE RESPONSIVENESS
// ══════════════════════════════════════════════════════════════════

const MOB_BREAKPOINT = 768;
function isMobile() { return window.innerWidth <= MOB_BREAKPOINT; }

function toggleMobSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.getElementById('mobOverlay');
  const isOpen  = sidebar.classList.toggle('mob-open');
  document.querySelector('.chat-aside')?.classList.remove('mob-open');
  overlay.classList.toggle('active', isOpen);
}

function closeMobSidebar() {
  document.querySelector('.sidebar')?.classList.remove('mob-open');
  document.querySelector('.chat-aside')?.classList.remove('mob-open');
  document.getElementById('mobOverlay')?.classList.remove('active');
}

function toggleMobAside() {
  const aside   = document.querySelector('.chat-aside');
  const overlay = document.getElementById('mobOverlay');
  if (!aside) return;
  const isOpen = aside.classList.toggle('mob-open');
  document.querySelector('.sidebar')?.classList.remove('mob-open');
  overlay.classList.toggle('active', isOpen);
}

function mobNavActive(btn) {
  document.querySelectorAll('.mob-nav-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  closeMobSidebar();
}

// Close panels when sidebar nav item or chat is clicked
document.querySelectorAll('.sb-item').forEach(el => {
  el.addEventListener('click', () => { if (isMobile()) closeMobSidebar(); });
});
document.querySelectorAll('.shi').forEach(el => {
  el.addEventListener('click', () => { if (isMobile()) closeMobSidebar(); });
});

