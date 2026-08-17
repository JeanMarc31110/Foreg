from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from .orchestrator import build_blueprint, materialize_agent, GENERATED_DIR

app = FastAPI(title="AURELIA FORGE", version="1.0.0")

class BuildRequest(BaseModel):
    request: str = Field(min_length=10)
    autonomy_level: int = Field(default=2, ge=0, le=4)
    download_url: str = ""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML

@app.get("/api/health")
async def health():
    return {"status": "ok", "name": "AURELIA FORGE", "version": "1.0.0"}

@app.post("/api/build")
async def build(payload: BuildRequest):
    try:
        blueprint, audit, research = await build_blueprint(payload.request, payload.autonomy_level)
        package = materialize_agent(blueprint, audit, research, payload.download_url)
        return {
            "ok": True,
            "blueprint": blueprint.model_dump(),
            "audit": audit.model_dump(),
            "package": {
                "folder": package["folder"],
                "zip": package["zip"],
                "download_url": f"/download/{package['zip']}",
                "code_audit": package["code_audit"],
                "installation": {
                    "deployment_mode": blueprint.deployment_mode,
                    "link_install_enabled": blueprint.link_install_enabled,
                    "download_url": blueprint.download_url or payload.download_url,
                    "publication": "BLOCKED_UNTIL_VALIDATED",
                },
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/download/{filename}")
async def download(filename: str):
    if "/" in filename or "\\" in filename or not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")
    path = GENERATED_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    return FileResponse(path, filename=filename, media_type="application/zip")

HTML = """
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURELIA FORGE</title>
<style>
:root{--bg:#090b10;--panel:#121722;--muted:#8e99aa;--line:#283041;--text:#f4f7fb;--accent:#d5b86a;--ok:#83d6a3;--bad:#ff8c8c}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% 0,#1b2230,#090b10 46%);color:var(--text);font-family:Segoe UI,Arial,sans-serif}
.wrap{max-width:1100px;margin:auto;padding:42px 24px 70px}.brand{font-size:14px;letter-spacing:.28em;color:var(--accent);font-weight:700}
h1{font-size:48px;margin:9px 0 8px}.sub{color:var(--muted);font-size:18px;max-width:800px;line-height:1.55}
.panel{background:rgba(18,23,34,.92);border:1px solid var(--line);border-radius:18px;padding:24px;margin-top:28px}
textarea{width:100%;min-height:170px;resize:vertical;background:#0c1018;border:1px solid var(--line);border-radius:12px;color:white;padding:16px;font-size:16px}
.row{display:flex;gap:18px;align-items:center;margin-top:18px;flex-wrap:wrap}select,button{border-radius:10px;padding:12px 16px;font-size:15px}
select{background:#0c1018;color:white;border:1px solid var(--line)}button{border:0;background:var(--accent);color:#15120a;font-weight:800;cursor:pointer}
button:disabled{opacity:.45}.stage{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:22px}
.stage div{font-size:12px;text-align:center;padding:10px 4px;border:1px solid var(--line);border-radius:8px;color:var(--muted)}
.stage .active{color:#fff;border-color:var(--accent)}.stage .done{color:var(--ok)}#result{display:none}.score{font-size:44px;font-weight:800}
.meta{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:#0c1018;border:1px solid var(--line);border-radius:12px;padding:16px}.card h3{margin-top:0}
pre{white-space:pre-wrap;word-break:break-word;color:#c8d0dd}a.dl{display:inline-block;text-decoration:none;background:var(--accent);color:#15120a;padding:12px 18px;border-radius:10px;font-weight:800;margin-top:10px}
.err{color:var(--bad);white-space:pre-wrap}@media(max-width:750px){h1{font-size:36px}.stage{grid-template-columns:1fr 1fr}.meta{grid-template-columns:1fr}}
</style></head>
<body><div class="wrap">
<div class="brand">FEWURA · AGENT FACTORY</div><h1>AURELIA FORGE</h1>
<div class="sub">Décrivez un métier, un problème ou une équipe à automatiser. FORGE recherche, conçoit, audite puis génère un agent spécialisé installable.</div>
<div class="panel">
<textarea id="request" placeholder="Exemple : Crée un agent qui automatise la réception, le contrôle et le classement des factures fournisseurs d'une PME française."></textarea>
<div class="row"><label>Autonomie <select id="autonomy">
<option value="0">0 — Conseil uniquement</option><option value="1">1 — Prépare les actions</option>
<option value="2" selected>2 — Agit après validation</option><option value="3">3 — Autonomie encadrée</option>
<option value="4">4 — Autonomie maximale</option></select></label>
<label>URL Setup HTTPS (optionnelle) <input id="downloadUrl" type="url" placeholder="https://downloads.example.com/agent-Setup.exe" style="min-width:320px;background:#0c1018;color:white;border:1px solid var(--line);border-radius:10px;padding:12px"></label>
<button id="build" onclick="buildAgent()">CRÉER L'AGENT</button></div>
<div class="stage"><div id="s1">RECHERCHE</div><div id="s2">ARCHITECTURE</div><div id="s3">AUDIT</div><div id="s4">CORRECTION</div><div id="s5">PACKAGE</div></div>
<div id="error" class="err" style="margin-top:16px"></div></div>
<div class="panel" id="result"><div class="meta"><div class="card"><h3 id="agentName"></h3><div id="purpose"></div><p>Autonomie : <b id="autoOut"></b>/4</p></div>
<div class="card"><h3>Audit FORGE</h3><div class="score"><span id="score"></span>/100</div><div id="verdict"></div></div></div>
<div class="card" style="margin-top:16px"><h3>Architecture</h3><pre id="architecture"></pre></div>
<a class="dl" id="download">TÉLÉCHARGER L'AGENT (.ZIP)</a></div></div>
<script>
function stage(n){for(let i=1;i<=5;i++){const el=document.getElementById('s'+i);el.className=i<n?'done':(i===n?'active':'')}}
async function buildAgent(){
const request=document.getElementById('request').value.trim();if(request.length<10){document.getElementById('error').textContent="Décrivez plus précisément l'agent.";return}
const btn=document.getElementById('build');btn.disabled=true;document.getElementById('error').textContent='';document.getElementById('result').style.display='none';stage(1);
let ticker=1;const interval=setInterval(()=>{ticker=Math.min(4,ticker+1);stage(ticker)},4500);
try{const res=await fetch('/api/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request,autonomy_level:parseInt(document.getElementById('autonomy').value),download_url:document.getElementById('downloadUrl').value.trim()})});
const data=await res.json();if(!res.ok)throw new Error(data.detail||'Erreur inconnue');clearInterval(interval);stage(5);
setTimeout(()=>{for(let i=1;i<=5;i++)document.getElementById('s'+i).className='done'},250);
document.getElementById('agentName').textContent=data.blueprint.name+' v'+data.blueprint.version;document.getElementById('purpose').textContent=data.blueprint.purpose;
document.getElementById('autoOut').textContent=data.blueprint.autonomy_level;document.getElementById('score').textContent=data.audit.score;document.getElementById('verdict').textContent=data.audit.verdict;
document.getElementById('architecture').textContent=JSON.stringify({tools:data.blueprint.tools,subagents:data.blueprint.subagents,workflows:data.blueprint.workflows,success_criteria:data.blueprint.success_criteria},null,2);
document.getElementById('download').href=data.package.download_url;document.getElementById('result').style.display='block'}
catch(e){clearInterval(interval);document.getElementById('error').textContent='Erreur : '+e.message}finally{btn.disabled=false}}
</script></body></html>
"""

