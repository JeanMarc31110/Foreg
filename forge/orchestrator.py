from __future__ import annotations

import os
import re
import zipfile
from datetime import datetime
from pathlib import Path

from agents import Agent, Runner, WebSearchTool
from .schemas import AgentBlueprint, AuditReport
from .windows_release import write_windows_release_files

BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "generated_agents"
MODEL = os.getenv("FORGE_MODEL", "gpt-5.6-sol")

WINDOWS_RELEASE_STANDARD = """STANDARD FEWURA WINDOWS OBLIGATOIRE POUR TOUT AGENT DESTINE A UN UTILISATEUR WINDOWS :
- un agent client ne doit pas etre livre sous forme de simples scripts .bat ;
- produire un EXE Windows autonome et un Setup Inno Setup ou un package MSIX adapte ;
- le PC client ne doit pas avoir besoin de Python, pip ou du code source ;
- les donnees modifiables doivent etre stockees hors de Program Files, typiquement sous LOCALAPPDATA ;
- aucun agent ne peut etre qualifie de livrable si son audit FORGE est inferieur a 90/100 ou contient encore une correction critique ;
- chaque agent doit posseder des tests automatises, dont au moins un test critique ;
- executer tous les tests source et metier dans un etat propre et exiger zero echec avant compilation ;
- tester le vrai EXE compile sur Windows ;
- construire le Setup seulement si les tests source, metier et EXE reussissent ;
- signer l'EXE applicatif avant de construire le Setup ;
- signer ensuite le Setup avec une identite FEWURA publiquement reconnue ;
- verifier Authenticode de l'EXE et du Setup ;
- installer le Setup signe dans un environnement Windows propre et tester l'application reellement installee ;
- tester aussi la desinstallation et verifier qu'aucun executable installe ne reste en place ;
- bloquer toute release client si build, test, installation, desinstallation ou signature echoue ;
- ne jamais publier ou etiqueter TESTED un artefact issu d'une chaine partiellement rouge ;
- ne jamais demander au client de desactiver Defender, SmartScreen ou Smart App Control ;
- les builds non signes sont des builds internes QA uniquement, jamais des releases client ;
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
        + WINDOWS_RELEASE_STANDARD
        + "\nLe blueprint doit inclure plusieurs tests concrets, dont au moins un test critique, et les critères de release nécessaires pour respecter ce standard."
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
        + WINDOWS_RELEASE_STANDARD
        + "\nPour un agent Windows destiné à des clients, refuse le statut livrable si le blueprint ne prévoit pas "
        "des tests métier exécutables, le test du vrai EXE, la signature Authenticode de l'EXE et du Setup, "
        "le test après installation, la désinstallation, la vérification de signature et le blocage de release "
        "lorsque l'une de ces étapes manque ou échoue. Toute correction critique restante interdit la livraison."
    ),
    output_type=AuditReport,
)


async def build_blueprint(user_request: str, autonomy_level: int = 2):
    research_result = await Runner.run(
        researcher,
        "Mission demandée :\n" + user_request
        + "\n\nProduis une note de recherche concise et exploitable pour l'architecte.",
    )
    research_text = str(research_result.final_output)

    architect_input = (
        "DEMANDE UTILISATEUR\n" + user_request
        + f"\n\nNIVEAU D'AUTONOMIE SOUHAITÉ\n{autonomy_level}/4"
        + "\n\nNOTE DE RECHERCHE\n" + research_text
        + "\n\nCrée le blueprint complet de l'agent."
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
        "import json\n"
        "import os\n"
        "import sys\n\n"
        "# Outils prévus par FORGE :\n"
        + tool_comments + "\n\n"
        + "SYSTEM_INSTRUCTIONS = " + repr(blueprint.system_instructions) + "\n\n"
        + "agent = Agent(\n"
        + f"    name={blueprint.name!r},\n"
        + "    model=os.getenv('AGENT_MODEL', os.getenv('FORGE_MODEL', 'gpt-5.6-sol')),\n"
        + "    instructions=SYSTEM_INSTRUCTIONS,\n"
        + ")\n\n"
        + "def self_test() -> int:\n"
        + "    checks = {\n"
        + "        'python_runtime': True,\n"
        + "        'agent_name': bool(agent.name),\n"
        + "        'instructions': bool(SYSTEM_INSTRUCTIONS.strip()),\n"
        + "    }\n"
        + "    print(json.dumps({'self_test': checks, 'ok': all(checks.values())}, ensure_ascii=False))\n"
        + "    return 0 if all(checks.values()) else 2\n\n"
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
        + "    if '--self-test' in sys.argv:\n"
        + "        raise SystemExit(self_test())\n"
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
2. Ajouter la clé OpenAI dans .env si l'agent en a réellement besoin.
3. Exécuter start.bat.

## Release client Windows
Exécuter `build_release.bat` sur une machine Windows de build correctement équipée. La chaîne part d'un environnement propre, exécute tous les tests, effectue le self-test source, produit et teste le vrai EXE, signe l'EXE, construit et signe le Setup, installe ce Setup dans un répertoire propre, teste l'application installée, teste la désinstallation et génère `release/release-manifest.json` avec le SHA-256.

La release est bloquée si une seule étape échoue. Le PC client n'a besoin ni de Python, ni de pip, ni des scripts de développement.

Seul un manifeste portant `VALIDATED_FOR_REMOTE_WINDOWS_INSTALL` autorise une livraison à un ordinateur distant.

Voir `RELEASE_WINDOWS.md` et `WINDOWS_RELEASE_STANDARD.md`.

## Important
Les intégrations métier réelles (ERP, CRM, banque, messagerie, etc.) nécessitent leurs API et identifiants lorsqu'elles en dépendent réellement. Les actions sensibles doivent rester soumises à validation humaine.
"""


def _generated_release_contract_test(blueprint: AgentBlueprint) -> str:
    return f'''import json\nfrom pathlib import Path\n\nfrom agent import self_test, agent, SYSTEM_INSTRUCTIONS\n\n\ndef test_agent_self_test():\n    assert self_test() == 0\n\n\ndef test_agent_identity_and_instructions():\n    assert agent.name == {blueprint.name!r}\n    assert SYSTEM_INSTRUCTIONS.strip()\n\n\ndef test_blueprint_contains_release_tests():\n    manifest = json.loads((Path(__file__).resolve().parents[1] / "manifest.json").read_text(encoding="utf-8"))\n    tests = manifest.get("tests", [])\n    assert tests, "FORGE interdit une release sans tests declares"\n    assert any(bool(t.get("critical")) for t in tests), "Au moins un test critique est obligatoire"\n    assert all(str(t.get("expected_behavior", "")).strip() for t in tests)\n'''


def materialize_agent(blueprint: AgentBlueprint, audit: AuditReport, research_text: str):
    if audit.score < 90:
        raise ValueError(f"FORGE bloque la matérialisation : audit insuffisant ({audit.score}/100).")
    if audit.critical_fixes:
        raise ValueError("FORGE bloque la matérialisation : corrections critiques restantes : " + "; ".join(audit.critical_fixes))
    if not blueprint.tests:
        raise ValueError("FORGE bloque la matérialisation : aucun test métier défini.")
    if not any(test.critical for test in blueprint.tests):
        raise ValueError("FORGE bloque la matérialisation : au moins un test critique est obligatoire.")

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
        "# Standard FEWURA Windows\n\n" + WINDOWS_RELEASE_STANDARD
        + "\n## Secrets de signature\nLes identifiants de signature doivent etre fournis uniquement par le gestionnaire de secrets CI/CD. Ils ne doivent jamais etre places dans le code source ou le ZIP.\n",
        encoding="utf-8",
    )
    tests_dir = agent_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_release_contract.py").write_text(
        _generated_release_contract_test(blueprint), encoding="utf-8"
    )
    (agent_dir / "requirements.txt").write_text(
        "openai-agents>=0.7.0\npython-dotenv>=1.0.1\n", encoding="utf-8"
    )
    (agent_dir / ".env.example").write_text(
        "OPENAI_API_KEY=sk-votre-cle-api\nAGENT_MODEL=gpt-5.6-sol\n", encoding="utf-8"
    )
    (agent_dir / "install.bat").write_text(
        '@echo off\ncd /d "%~dp0"\npy -3 -m venv .venv\n'
        'call .venv\\Scripts\\activate.bat\npython -m pip install --upgrade pip\n'
        'pip install -r requirements.txt\nif not exist ".env" copy ".env.example" ".env" >nul\n'
        'echo Installation de developpement terminee. Configurez .env si necessaire puis lancez start.bat\npause\n',
        encoding="utf-8",
    )
    (agent_dir / "start.bat").write_text(
        '@echo off\ncd /d "%~dp0"\ncall .venv\\Scripts\\activate.bat\npython agent.py\npause\n',
        encoding="utf-8",
    )

    write_windows_release_files(
        agent_dir=agent_dir,
        app_name=blueprint.name,
        slug=blueprint.slug,
        version=blueprint.version,
    )

    zip_path = GENERATED_DIR / f"{folder_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in agent_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(agent_dir.parent))

    return {"folder": folder_name, "zip": zip_path.name, "zip_path": str(zip_path)}
