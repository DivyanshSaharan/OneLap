"""Offline packaging contracts; not a substitute for actually building the image."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def content(name):
    return (ROOT / name).read_text("utf-8")


def test_runtime_is_single_non_root_service_with_signal_and_health_handling():
    docker = content("Dockerfile")
    assert "FROM node:22-alpine AS frontend" in docker
    assert "COPY --from=frontend /build/dist ./dist" in docker
    assert "USER onelap" in docker
    assert "HEALTHCHECK" in docker and "/health" in docker
    assert "exec uvicorn" in docker
    assert "${PORT:-10000}" in docker
    assert "--workers 1 --no-proxy-headers" in docker
    assert "COPY . " not in docker


def test_adapter_binding_files_are_in_image_but_private_receipt_is_not():
    docker = content("Dockerfile")
    assert "COPY backend/onelap ./backend/onelap" in docker
    assert "COPY datasets/onelap-sft-v1.manifest.json" in docker
    assert "onelap-checkpoint-receipt.json" not in docker
    assert "onelap-checkpoint-receipt.json" in content(".dockerignore").splitlines()


@pytest.mark.parametrize("excluded", [".env", ".env.*", ".data", ".git", ".secrets"])
def test_build_context_excludes_private_state(excluded):
    assert excluded in content(".dockerignore").splitlines()


def test_compose_is_loopback_only_and_uses_separate_private_configuration():
    compose = content("compose.yaml")
    assert "127.0.0.1:4178:10000" in compose
    assert "${ONELAP_DOCKER_ENV_FILE:-.env.docker}" in compose
    assert "required: true" in compose
    assert "http://localhost:4178" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose and "- ALL" in compose
    assert "init: true" in compose
    assert "volumes:" not in compose


@pytest.mark.parametrize(
    "gate",
    [
        "ONELAP_HOSTED_REQUESTS_ENABLED",
        "ONELAP_DATA_SHARING_APPROVED",
        "ONELAP_REFLECTION_SHARING_APPROVED",
        "ONELAP_ATLAS_BUDGET_APPROVED",
        "ONELAP_JOURNAL_ENABLED",
        "ONELAP_ATLAS_SHARING_APPROVED",
        "ONELAP_TRACING_ENABLED",
        "ONELAP_TRACE_SHARING_APPROVED",
    ],
)
def test_compose_cannot_activate_paid_or_sharing_gates_from_env_file(gate):
    assert f"{gate}: 'false'" in content("compose.yaml")
    assert f"key: {gate}\n        value: 'false'" in content("render.yaml")


def test_render_exposes_private_runtime_settings_without_secret_values():
    blueprint = content("render.yaml")
    for key in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "MONGODB_URI", "TINKER_API_KEY"]:
        assert f"key: {key}\n        sync: false" in blueprint
    assert "ONELAP_CHECKPOINT_RECEIPT" in blueprint
    assert "ONELAP_CHECKPOINT_RECEIPT_SHA256" in blueprint
    assert "autoDeployTrigger: off" in blueprint
    assert "healthCheckPath: /health" in blueprint
    assert "value: atlas" in blueprint
    assert "key: ONELAP_MODEL_TARGET\n        value: adapter" in blueprint
    assert "key: ONELAP_CHECKPOINT_APPROVED\n        value: 'true'" in blueprint
    assert "value: /etc/secrets/onelap-checkpoint-receipt.json" in blueprint


def test_compose_keeps_its_diagnostic_base_separate_from_approved_deployment_adapter():
    compose = content("compose.yaml")
    assert "ONELAP_MODEL_TARGET: base" in compose
    assert "ONELAP_CHECKPOINT_APPROVED: 'false'" in compose


def test_only_placeholder_docker_env_example_is_publishable():
    sample = content(".env.docker.example")
    for key in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "MONGODB_URI"]:
        assert f"{key}=\n" in sample
    assert "!.env.docker.example" in content(".gitignore")
    assert ".env.*" in content(".gitignore")
