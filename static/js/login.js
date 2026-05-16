/* Lexara AI — Login JS */

function switchTab(tab){
  const track = document.getElementById("tabTrack");
  document.getElementById("tabLogin").classList.toggle("active", tab==="login");
  document.getElementById("tabSignup").classList.toggle("active", tab==="signup");
  document.getElementById("loginForm").classList.toggle("hidden", tab!=="login");
  document.getElementById("signupForm").classList.toggle("hidden", tab!=="signup");
  track.classList.toggle("right", tab==="signup");
  hideAlert();
}

function showAlert(msg, type="error"){
  const box=document.getElementById("alertBox");
  document.getElementById("alertIcon").textContent = type==="error" ? "⚠️" : "✅";
  document.getElementById("alertMsg").textContent = msg;
  box.className = "alert-box " + type;
}
function hideAlert(){ document.getElementById("alertBox").classList.add("hidden"); }

function togglePwd(id, btn){
  const input=document.getElementById(id);
  const show = input.type==="password";
  input.type = show ? "text" : "password";
  btn.querySelector(".eye-icon").style.opacity = show ? ".45" : "1";
}

function checkStrength(pwd){
  const segs=["seg1","seg2","seg3","seg4"].map(id=>document.getElementById(id));
  const txt=document.getElementById("strengthTxt");
  if(!pwd){ segs.forEach(s=>s.style.background=""); txt.textContent=""; return; }
  let score=0;
  if(pwd.length>=8) score++;
  if(/[A-Z]/.test(pwd)) score++;
  if(/[0-9]/.test(pwd)) score++;
  if(/[^A-Za-z0-9]/.test(pwd)) score++;
  const colors=["#ef4444","#f59e0b","#3b82f6","#10b981"];
  const labels=["Weak","Fair","Good","Strong"];
  const col = colors[score-1]||"#ef4444";
  segs.forEach((s,i)=>{ s.style.background = i<score ? col : ""; });
  txt.textContent = labels[score-1]||"";
  txt.style.color = col;
}

function checkConfirm(){
  const pwd=document.getElementById("signupPwd").value;
  const val=document.getElementById("signupConfirm").value;
  const icon=document.getElementById("matchIcon");
  const wrap=document.getElementById("confirmWrap");
  if(!val){ icon.textContent=""; wrap.className="field-input"; return; }
  if(val===pwd){ icon.textContent="✅"; wrap.className="field-input success"; }
  else { icon.textContent="❌"; wrap.className="field-input error"; }
}

function showForgot(e){
  e.preventDefault();
  const email = document.getElementById("loginEmail")?.value?.trim() || "";
  const modal = document.getElementById("forgotModal");
  if (modal) {
    document.getElementById("forgotEmail").value = email;
    modal.classList.remove("hidden");
  }
}

async function submitForgot(e) {
  e.preventDefault();
  const email = document.getElementById("forgotEmail").value.trim().toLowerCase();
  if (!email) { showForgotAlert("Please enter your email address.", "error"); return; }
  const btn = document.getElementById("forgotBtn");
  btn.disabled = true; btn.textContent = "Sending…";
  try {
    const r = await fetch("/api/auth/forgot-password", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({email})
    });
    const d = await r.json();
    showForgotAlert("If that email exists, a reset link has been sent. Check your inbox.", "success");
    btn.textContent = "Sent ✓";
  } catch(err) {
    showForgotAlert("Something went wrong. Please try again.", "error");
    btn.disabled = false; btn.textContent = "Send Reset Link";
  }
}

function showForgotAlert(msg, type) {
  const el = document.getElementById("forgotAlert");
  if (!el) return;
  el.textContent = msg;
  el.className = "forgot-alert " + type;
  el.style.display = "block";
}

function closeForgot() {
  const modal = document.getElementById("forgotModal");
  if (modal) modal.classList.add("hidden");
  const el = document.getElementById("forgotAlert");
  if (el) el.style.display = "none";
  const btn = document.getElementById("forgotBtn");
  if (btn) { btn.disabled = false; btn.textContent = "Send Reset Link"; }
}
function oauthMsg(){ showAlert("OAuth login coming soon. Use email & password for now."); }

function setLoading(form, loading){
  const btn=document.getElementById(form+"Btn");
  const label=document.getElementById(form+"Label");
  const arrow=document.getElementById(form+"Arrow");
  const spin=document.getElementById(form+"Spin");
  btn.disabled=loading;
  label.textContent=loading ? (form==="login"?"Signing in…":"Creating account…") : (form==="login"?"Sign In":"Create Free Account");
  arrow.classList.toggle("hidden", loading);
  spin.classList.toggle("hidden", !loading);
}

async function handleLogin(e){
  e.preventDefault(); hideAlert();
  const email=document.getElementById("loginEmail").value.trim();
  const pwd=document.getElementById("loginPwd").value;
  if(!email||!pwd){ showAlert("Please fill in all fields."); return; }
  setLoading("login", true);
  try{
    const r=await fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password:pwd})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.error||"Login failed");
    showAlert("Signed in! Redirecting…","success");
    const next = new URLSearchParams(window.location.search).get("next");
    setTimeout(()=>window.location.href = next || "/", 600);
  }catch(err){ showAlert(err.message); setLoading("login",false); }
}

async function handleSignup(e){
  e.preventDefault(); hideAlert();
  const first=document.getElementById("signupFirst").value.trim();
  const last=document.getElementById("signupLast").value.trim();
  const email=document.getElementById("signupEmail").value.trim();
  const pwd=document.getElementById("signupPwd").value;
  const confirm=document.getElementById("signupConfirm").value;
  const agreed=document.getElementById("agreeTerms").checked;
  if(!first||!last||!email||!pwd){ showAlert("Please fill in all required fields."); return; }
  if(pwd!==confirm){ showAlert("Passwords do not match."); return; }
  if(pwd.length<6){ showAlert("Password must be at least 6 characters."); return; }
  if(!agreed){ showAlert("Please agree to the Terms of Service."); return; }
  setLoading("signup",true);
  try{
    const r=await fetch("/api/auth/signup",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:`${first} ${last}`,email,password:pwd})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.error||"Signup failed");
    showAlert("Account created! Redirecting…","success");
    const next = new URLSearchParams(window.location.search).get("next");
    setTimeout(()=>window.location.href = next || "/", 800);
  }catch(err){ showAlert(err.message); setLoading("signup",false); }
}

// Input focus micro-animation
document.querySelectorAll(".field-input input").forEach(input=>{
  input.addEventListener("focus",()=>input.closest(".field-input").style.transform="scale(1.005)");
  input.addEventListener("blur",()=>input.closest(".field-input").style.transform="");
});

