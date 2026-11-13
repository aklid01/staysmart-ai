import re
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route

from staysmart.app.routes import register_routes
from staysmart.config import Settings

ROOT = Path(__file__).resolve().parents[1]

ENV_SETTINGS = {
    "HOTEL_PROVIDER": "hotel_provider",
    "STAYSMART_DATASET_PATH": "dataset_path",
    "STAYSMART_LOG_LEVEL": "log_level",
    "STAYSMART_CURRENCY": "currency",
    "STAYSMART_WINDOW_DAYS": "window_days",
    "STAYSMART_HTTP_HOST": "http_host",
    "STAYSMART_HTTP_PORT": "http_port",
    "STAYSMART_CORS_ORIGINS": "cors_origins",
    "STAYSMART_RAG_CORPUS_PATH": "rag_corpus_path",
    "STAYSMART_RAG_INDEX_PATH": "rag_index_path",
    "STAYSMART_RAG_MODEL": "rag_model",
    "LLM_BASE_URL": "llm_base_url",
    "LLM_API_KEY": "llm_api_key",
    "LLM_MODEL": "llm_model",
}

README_MODULES = [
    "src/staysmart/app/__main__.py",
    "src/staysmart/mcp_server/__main__.py",
    "src/staysmart/rag/__main__.py",
    "scripts/demo_provider.py",
    "scripts/demo_mcp.py",
    "scripts/demo_api.py",
    "scripts/demo_rag.py",
    "scripts/demo_agent.py",
    "frontend/package.json",
]


def test_every_registered_route_is_documented_in_api_md():
    app = Starlette()
    register_routes(app)
    api_md = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")

    for route in app.routes:
        if isinstance(route, Route):
            assert f"`{route.path}`" in api_md, f"route {route.path} missing from docs/API.md"


def test_every_env_backed_setting_exists_and_is_documented():
    settings = Settings.from_env(env={})
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for env_var, attribute in ENV_SETTINGS.items():
        assert hasattr(settings, attribute), f"Settings.{attribute} missing for {env_var}"
        assert env_var in env_example, f"{env_var} missing from .env.example"
        assert env_var in readme, f"{env_var} missing from the README configuration table"


def test_readme_quickstart_references_existing_modules():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for relative in README_MODULES:
        assert (ROOT / relative).exists(), f"{relative} referenced by README does not exist"

    for command in [
        "uv run python -m staysmart.mcp_server",
        "uv run python -m staysmart.app",
        "uv run python -m staysmart.rag ingest",
        "npm run dev",
        "uv run pytest",
    ]:
        assert command in readme, f"README quickstart missing: {command}"


def test_architecture_status_table_lists_all_phases_implemented():
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for phase in range(0, 8):
        assert re.search(rf"\| {phase} \|", architecture), f"phase {phase} row missing"
    assert "Not yet implemented |" not in architecture
