from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_has_no_activation_or_private_update_flow() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    forbidden = [
        "check_activation",
        "license_manager",
        "public.pem",
        "NebulaLab-Updates",
        "UpdateManager",
        "run_desktop.py",
    ]
    for token in forbidden:
        assert token not in app


def test_private_packaging_and_license_files_are_absent() -> None:
    forbidden_paths = [
        "build_dist.py",
        "run_desktop.py",
        "installer.iss",
        "ChineseSimplified.isl",
        "assets/public.pem",
        "modules/license_manager.py",
        "modules/updater.py",
    ]
    for relative_path in forbidden_paths:
        assert not (ROOT / relative_path).exists(), f"{relative_path} should not ship in Classic"


def test_core_modules_import_without_streamlit_side_effects() -> None:
    import modules

    assert "init_session_state" in modules.__all__
    assert "AIAnalyzer" not in modules.__all__
