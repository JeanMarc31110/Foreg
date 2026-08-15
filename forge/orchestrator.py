from __future__ import annotations

import os
import re
import zipfile
from datetime import datetime
from pathlib import Path

from agents import Agent, Runner, WebSearchTool
from .schemas import AgentBlueprint, AuditReport

BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "generated_agents"
MODEL = os.getenv("FORGE_MODEL", "gpt-5.6-sol")

WINDOWS_RELEASE_STANDARD = """STANDARD FEWURA WINDOWS OBLIGATOIRE POUR TOUT AGENT DESTINE A UN UTILISATEUR WINDOWS :
- un agent client ne doit pas etre livre sous forme de simples scripts .bat ;
- produire un EXE Windows et un Setup Inno Setup ou un package MSIX adapte ;
- les donnees modifiables doivent etre stockees hors de Program Files, typiquement sous LOCALAPPDATA ;
- tester le vrai EXE compile sur Windows ;
- construire le Setup seulement si le test du vrai EXE reussit ;
- installer ensuite le Setup dans un environnement Windows propre et tester l'application installee ;
- signer l'EXE applicatif et le Setup avec une identite FEWURA publiquement reconnue ;
- verifier Authenticode et bloquer toute release client si la signature n'est pas valide ;
- ne jamais demander au client de desactiver Defender, SmartScreen ou Smart App Control ;
- les builds non signes sont des builds internes QA uniquement, jamais des releases client ;
- pour une exigence d'absence de SmartScreen des la distribution, privilegier une distribution MSIX via Microsoft Store lorsque le produit s'y prete ;
- aucun secret, certificat prive ou mot de passe de signature ne doit etre committe dans Git.
"""


def _safe_slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "agent"


researcher = Agent(
    name="FORGE Researcher",
    model=MODEL,
    instructions=(
        "Tu es l'analyste métier et documentaire de FORGE. "
        "Identifie les connaissances, contraintes, risques et sources officielles nécessaires. "
        "Utilise la recherche web si une information actuelle, réglementaire ou technique doit être vérifiée. "
        "N'invente jamais une règle juridique, une norme ou une API."
    ),
    tools=[WebSearchTool()],
)

architect = Agent(
    name="FORGE Architect",
    model=MODEL,
    instructions=(
        "Tu conçois des agents IA professionnels et réellement exploitables. "
        "Transforme la demande et la recherche en architecture structurée : mission, outils, "
        "sous-agents, permissions, workflows, tests et critères de réussite. "
        "Toute action financière, destructive, irréversible ou de diffusion massive doit demander "
        "une validation humaine. Le slug doit être compatible Windows.\n\n"
        + WINDOWS_RELEASE_STANDARD +
        "\nLe blueprint doit inclure les tests et critères de release nécessaires pour respecter ce standard."
    ),
    output_type=AgentBlueprint,
)

auditor = Agent(
    name="FORGE Auditor",
    model=MODEL,
    instructions=(
        "Tu audites sévèrement un blueprint d'agent. Cherche les hallucinations possibles, "
        "permissions excessives, outils manquants, tests faibles, ambiguïtés métier et risques "
        "d'automatisation. Donne un score sur 100 et une version améliorée des instructions si nécessaire.\n\n"
        + WINDOWS_RELEASE_STANDARD +
        "\nPour un agent Windows destiné à des clients, refuse le statut livrable si le blueprint ne prévoit pas "
        "test du vrai EXE, test après installation, signature Authenticode de l'EXE et du Setup, vérification "
        "de signature et blocage de release lorsque la signature manque."
    ),
    output_type=AuditReport,
)


async def build_blueprint(user_request: str, autonomy_level: int = 2):
    research_result = await Runner.run(
        researcher,
        "Mission demandée :\n" + user_request +
        "\n\nProduis une note de recherche concise et exploitable pour l'architecte."
    )
    research_text = str(research_result.final_output)

    architect_input = (
        "DEMANDE UTILISATEUR\n" + user_request +
        f"\n\nNIVEAU D'AUTONOMIE SOUHAITÉ\n{autonomy_level}/4" +
        "\n\nNOTE DE RECHERCHE\n" + research_text +
        "\n\nCrée le blueprint complet de l'agent."
    )
    architecture_result = await Runner.run(architect, architect_input)
    blueprint: AgentBlueprint = architecture_result.final_output
    blueprint.autonomy_level = autonomy_level
    blueprint.slug = _safe_slug(blueprint.slug or blueprint.name)

    audit_result = await Runner.run(
        auditor, "BLUEPRINT À AUDITER :\n" + blueprint.model_dump_json(indent=2)
    )
    audit: AuditReport = audit_result.final_output

    if audit.score < 90 and audit.improved_system_instructions.strip():
        blueprint.system_instructions = audit.improved_system_instructions.strip()

    return blueprint, audit, research_text


def generated_agent_source(blueprint: AgentBlueprint) -> str:
    tool_comments = "\n".join(
        f"# - {t.name}: {t.purpose} | validation_humaine={t.approval_required}"
        for t in blueprint.tools
    ) or "# Aucun outil métier externe déclaré."

    return (
        "from agents import Agent, Runner\n"
        "import asyncio\n"
        "import os\n\n"
        "# Outils prévus par FORGE :\n"
        + tool_comments + "\n\n"
        + "SYSTEM_INSTRUCTIONS = " + repr(blueprint.system_instructions) + "\n\n"
        + "agent = Agent(\n"
        + f"    name={blueprint.name!r},\n"
        + "    model=os.getenv('AGENT_MODEL', os.getenv('FORGE_MODEL', 'gpt-5.6-sol')),\n"
        + "    instructions=SYSTEM_INSTRUCTIONS,\n"
        + ")\n\n"
        + "async def ask(message: str) -> str:\n"
        + "    result = await Runner.run(agent, message)\n"
        + "    return str(result.final_output)\n\n"
        + "async def main():\n"
        + f"    print('\\n{blueprint.name} - v{blueprint.version}')\n"
        + "    print(\"Tapez 'quit' pour quitter.\\n\")\n"
        + "    while True:\n"
        + "        message = input('Vous > ').strip()\n"
        + "        if message.lower() in {'quit', 'exit', 'q'}:\n"
        + "            break\n"
        + "        if not message:\n"
        + "            continue\n"
        + "        try:\n"
        + "            answer = await ask(message)\n"
        + "            print('\\nAgent >', answer, '\\n')\n"
        + "        except Exception as exc:\n"
        + "            print('\\nErreur :', exc, '\\n')\n\n"
        + "if __name__ == '__main__':\n"
        + "    asyncio.run(main())\n"
    )


def generated_readme(blueprint: AgentBlueprint, audit: AuditReport) -> str:
    tools = "\n".join(
        f"- {t.name}: {t.purpose}" + (" [VALIDATION HUMAINE]" if t.approval_required else "")
        for t in blueprint.tools
    ) or "- Aucun outil supplémentaire."
    subs = "\n".join(f"- {s.name}: {s.mission}" for s in blueprint.subagents) or "- Aucun."
    tests = "\n".join(f"- {t.name}: {t.expected_behavior}" for t in blueprint.tests) or "- Aucun."
    return f"""# {blueprint.name}

Version : {blueprint.version}

## Mission
{blueprint.purpose}

## Autonomie
Niveau {blueprint.autonomy_level}/4.

## Outils prévus
{tools}

## Sous-agents prévus
{subs}

## Tests métier
{tests}

## Audit FORGE
Score : {audit.score}/100
Verdict : {audit.verdict}

## Développement local
1. Exécuter install.bat.
2. Ajouter la clé OpenAI dans .env.
3. Exécuter start.bat.

## Release client Windows
Les scripts BAT sont réservés au développement local. Une release client doit respecter `WINDOWS_RELEASE_STANDARD.md` et ne peut être publiée que lorsque le vrai EXE, le Setup, l'installation réelle et les signatures Authenticode ont été validés.

## Important
Cette V1 générée fournit le noyau agentique et le cahier des charges des outils.
Les intégrations métier réelles (ERP, CRM, banque, messagerie, etc.) nécessitent
leurs API et identifiants. Les actions sensibles doivent rester soumises à validation humaine.
"""


def materialize_agent(blueprint: AgentBlueprint, audit: AuditReport, research_text: str):
    GENERATED_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{blueprint.slug}_{stamp}"
    agent_dir = GENERATED_DIR / folder_name
    agent_dir.mkdir(parents=True, exist_ok=True)

    (agent_dir / "agent.py").write_text(generated_agent_source(blueprint), encoding="utf-8")
    (agent_dir / "manifest.json").write_text(blueprint.model_dump_json(indent=2), encoding="utf-8")
    (agent_dir / "audit.json").write_text(audit.model_dump_json(indent=2), encoding="utf-8")
    (agent_dir / "research.md").write_text("# Note de recherche FORGE\n\n" + research_text, encoding="utf-8")
    (agent_dir / "README.md").write_text(generated_readme(blueprint, audit), encoding="utf-8")
    (agent_dir / "WINDOWS_RELEASE_STANDARD.md").write_text(
        "# Standard FEWURA Windows\n\n" + WINDOWS_RELEASE_STANDARD +
        "\n## Secrets de signature\nLes identifiants de signature doivent etre fournis uniquement par le gestionnaire de secrets CI/CD. Ils ne doivent jamais etre places dans le code source ou le ZIP.\n",
        encoding="utf-8"
    )
    (agent_dir / "requirements.txt").write_text("openai-agents>=0.7.0\npython-dotenv>=1.0.1\n", encoding="utf-8")
    (agent_dir / ".env.example").write_text(
        "OPENAI_API_KEY=sk-votre-cle-api\nAGENT_MODEL=gpt-5.6-sol\n", encoding="utf-8"
    )
    (agent_dir / "install.bat").write_text(
        '@echo off\ncd /d "%~dp0"\npy -3 -m venv .venv\n'
        'call .venv\\Scripts\\activate.bat\npython -m pip install --upgrade pip\n'
        'pip install -r requirements.txt\nif not exist ".env" copy ".env.example" ".env" >nul\n'
        'echo Installation de developpement terminee. Configurez .env puis lancez start.bat\npause\n',
        encoding="utf-8"
    )
    (agent_dir / "start.bat").write_text(
        '@echo off\ncd /d "%~dp0"\ncall .venv\\Scripts\\activate.bat\npython agent.py\npause\n',
        encoding="utf-8"
    )

    zip_path = GENERATED_DIR / f"{folder_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in agent_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(agent_dir.parent))

    return {"folder": folder_name, "zip": zip_path.name, "zip_path": str(zip_path)}
