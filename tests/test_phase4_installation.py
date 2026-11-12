"""Regressões de instalação: preflight, preservação e scripts operacionais."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reprocessamento"))
import acceptance_check as check
import release_phase4 as release
import setup_production_env as setup


def inventory(root: Path) -> dict:
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def sources(tmp_path):
    candidate = tmp_path / "candidate"
    for name in ("code/environment", "code/bash", "products/mapasGrib",
                 "products/matrizGrib/predi", "products/matrizGrib/bluesky"):
        (candidate / name).mkdir(parents=True)
    (candidate / "code/environment/path.conf").write_text("dir_gribs=/original\n")
    (candidate / "code/foo.py").write_text("# codigo candidato\n")
    (candidate / "products/matrizGrib/temp.csv").write_bytes(b"lat,lon,temp\r\n0,0,20\r\n")
    (candidate / "validation.json").write_text(json.dumps({"status": "ok", "failures": []}))
    (candidate / "release.json").write_text(json.dumps({
        "files": release.inventory(candidate),
        "validation_sha256": release.digest(candidate / "validation.json"),
    }))
    samples = tmp_path / "samples"
    samples.mkdir()
    sample = samples / "20221215-00-f000.grb2"
    sample.write_bytes(b"GRIB" + b"0" * 20 + b"7777")
    (samples / "manifest.json").write_text(json.dumps({"samples": [{
        "date": "20221215", "cycle": "00", "forecast": 0,
        "path": "/caminho-antigo/20221215-00-f000.grb2", "sha256": release.digest(sample),
    }], "errors": []}))
    root = tmp_path / "ambiente com espacos"
    args = ["--root", str(root), "--candidate", str(candidate), "--samples", str(samples)]
    return root, candidate, samples, args


def test_fresh_install_from_relocated_samples(sources):
    root, candidate, samples, args = sources
    assert setup.main(args) == 0
    report = check.check_environment(root, check_dependencies=False)
    assert report["status"] == "ok", report["failures"]
    assert report["deployment"] == "candidate-only"
    assert report["acceptance"] == "pending"
    assert (root / "app/foo.py").read_bytes() == (candidate / "code/foo.py").read_bytes()
    assert (root / "gribs/20221215/00/gfs.t00z.pgrb2.0p25.f000").read_bytes() == (samples / "20221215-00-f000.grb2").read_bytes()
    for script in (root / "bin").glob("*.sh"):
        subprocess.run(["bash", "-n", str(script)], check=True)


@pytest.mark.parametrize("defect", ["missing", "hash", "signature", "date", "duplicate", "errors", "release", "acceptance"])
def test_invalid_sources_cannot_destroy_existing_environment(sources, defect):
    root, candidate, samples, args = sources
    setup.main(args)
    (root / "app/user-note.txt").write_text("preservar")
    manifest = json.loads((samples / "manifest.json").read_text())
    item = manifest["samples"][0]
    sample = samples / "20221215-00-f000.grb2"
    if defect == "missing":
        sample.unlink()
    elif defect == "hash":
        sample.write_bytes(b"GRIBalterado7777")
    elif defect == "signature":
        sample.write_bytes(b"erro de download")
        item["sha256"] = release.digest(sample)
    elif defect == "date":
        item["date"] = "../../fora"
    elif defect == "duplicate":
        manifest["samples"].append(item.copy())
    elif defect == "errors":
        manifest["errors"] = ["download incompleto"]
    elif defect == "release":
        (candidate / "code/foo.py").write_text("alterado")
    else:
        path = root / "acceptance/acceptance.json"
        acceptance = json.loads(path.read_text())
        acceptance["release_sha256"] = "0" * 64
        path.write_text(json.dumps(acceptance))
    (samples / "manifest.json").write_text(json.dumps(manifest))
    before = inventory(root)
    with pytest.raises(SystemExit, match="erro:"):
        setup.main(args + ["--force"])
    assert inventory(root) == before


def test_destination_cannot_contain_sources(sources):
    root, candidate, samples, args = sources
    before = inventory(candidate.parent)
    with pytest.raises(SystemExit, match="sobrepor"):
        setup.main(args + ["--root", str(candidate.parent), "--force"])
    assert inventory(candidate.parent) == before


def test_update_tools_preserves_data_code_configuration_and_acceptance(sources):
    root, candidate, samples, args = sources
    setup.main(args)
    # Até edições locais ficam preservadas: atualizar ferramentas não reinstala produtos.
    (root / "app/foo.py").write_text("edicao local\n")
    (root / "logs/previous.log").write_text("historico")
    snapshots = {name: inventory(root / name) for name in (
        "app", "gribs", "matrizGrib", "mapasGrib", "environment", "acceptance", "evidence", "logs")}
    (root / "tools/acceptance_check.py").write_text("antigo")
    assert setup.main(["--root", str(root), "--update-tools", "--candidate", "/inexistente", "--samples", "/inexistente"]) == 0
    for name, before in snapshots.items():
        assert inventory(root / name) == before
    assert (root / "tools/acceptance_check.py").read_bytes() == (ROOT / "reprocessamento/acceptance_check.py").read_bytes()
    assert (root / "docs/16-manual-de-aceitacao.md").is_file()
    # A edição não é escondida pelo update-tools.
    assert check.check_environment(root, check_dependencies=False)["status"] == "failed"


def test_update_requires_existing_environment(tmp_path):
    root = tmp_path / "missing"
    with pytest.raises(SystemExit, match="ambiente incompleto"):
        setup.main(["--root", str(root), "--update-tools"])
    assert not root.exists()


@pytest.mark.parametrize("failure", [None, "checker", "generator"])
def test_generated_script_propagates_errors_and_tests_candidate(sources, failure):
    root, candidate, samples, args = sources
    setup.main(args)
    # Simula apenas as fronteiras dos subprocessos; geração GRIB real é validada à parte.
    (root / "tools/acceptance_check.py").write_text(
        'import os, sys\nprint("checagem", sys.argv[1])\nsys.exit(6 if os.getenv("FAIL_CHECKER") else 0)\n')
    (root / "app/bash/reqs_MAN_MET.sh").write_text(
        '#!/bin/bash\necho "gerador candidato executado"\nexit "${FAIL_GENERATOR:-0}"\n')
    active = root / "releases/other/code"
    (active / "bash").mkdir(parents=True)
    (active / "bash/reqs_MAN_MET.sh").write_text('exit 99\n')
    (root / "current").symlink_to(active.parent)
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
    if failure:
        env["FAIL_" + failure.upper()] = "7"
    command = [str(root / "bin/testar_bluesky.sh")]
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    if failure:
        assert result.returncode == (6 if failure == "checker" else 7)
        assert "Teste tecnico concluido" not in result.stdout
        if failure == "checker":
            assert "gerador candidato executado" not in result.stdout
    else:
        assert result.returncode == 0, result.stderr
        assert "gerador candidato executado" in result.stdout
        assert "Teste tecnico concluido" in result.stdout
        subprocess.run(command, env=env, capture_output=True, check=True)
        assert len(list((root / "aceitacao-manual").iterdir())) == 2
        assert len(list((root / "logs").glob("*.log"))) == 2
    assert json.loads((root / "acceptance/acceptance.json").read_text())["approved"] is False


def test_test_all_stops_at_first_failure(sources):
    root, _, _, args = sources
    setup.main(args)
    (root / "bin/testar_bluesky.sh").write_text('#!/bin/bash\nexit 17\n')
    for name in ("preditor", "planilhas"):
        (root / f"bin/testar_{name}.sh").write_text('#!/bin/bash\ntouch "$(dirname "$0")/unexpected"\n')
    result = subprocess.run([str(root / "bin/testar_todos.sh")])
    assert result.returncode == 17
    assert not (root / "bin/unexpected").exists()
