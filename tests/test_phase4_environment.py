"""Testes do verificador de ambiente e do aceite da Fase 4."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reprocessamento"))
import acceptance_check as check
import release_phase4 as release_tools
import setup_production_env as setup


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(path, header, rows, newline="\r\n"):
    text = newline.join([",".join(header)] + [",".join(map(str, row)) for row in rows])
    text += newline
    Path(path).write_bytes(text.encode("utf-8"))


BLUESKY_AUT = (
    "lat",
    "lon",
    "hMET",
    "angMET",
    "vento_resultante",
)
BLUESKY_MAN = (
    "lat",
    "lon",
    "hMET<feet>",
    "angMET<grau>",
    "vento_resultante<knot>",
)
PREDITOR_AUT = ("lat", "lon", "vento U", "vento V", "temp")
PREDITOR_MAN = ("lat", "lon", "vento U", "vento V", "temperatura K")
GRID = [(-1.0, -1.0), (-1.0, 0.0), (0.0, -1.0), (0.0, 0.0)]
H200 = (1.0 - (200.0 / 1013.25) ** 0.190284) * 145366.45


def bluesky_product(path, header=BLUESKY_AUT, name_hint="N200"):
    height = H200 if name_hint == "N200" else 20 * 3.28084
    write_csv(
        path,
        header,
        [
            [lat, lon, height, angle, speed]
            for (lat, lon), angle, speed in zip(GRID, (0, 90, 180, 359), (1, 2, 3, 4))
        ],
    )
    return path


def preditor_product(path, header=PREDITOR_AUT, temperature=300.0):
    write_csv(
        path,
        header,
        [[lat, lon, -5.0, 3.0, temperature] for lat, lon in GRID],
    )
    return path


def test_bluesky_accepts_aut_and_man_headers(tmp_path):
    base = tmp_path / "saida"
    base.mkdir()
    bluesky_product(
        base / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_RJ_N200_00_20221215_00.csv"
    )
    bluesky_product(
        base / "matriz_vento_bluesky_LonMin:-1_N20_00_20221215_00.csv",
        header=BLUESKY_MAN,
        name_hint="N20",
    )
    report = check.check_products(tmp_path, "bluesky", [(base, True)])
    assert report["status"] == "ok"
    assert report["files"] == 2
    assert report["variants"] == {"AUT": 1, "MAN": 1}


def test_bluesky_rejects_angle_outside_range(tmp_path):
    base = tmp_path / "saida"
    base.mkdir()
    path = base / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_RJ_N200_00_20221215_00.csv"
    write_csv(
        path,
        BLUESKY_AUT,
        [
            [lat, lon, H200, 360.0, 1.0]
            for lat, lon in GRID
        ],
    )
    report = check.check_products(tmp_path, "bluesky", [(base, True)])
    assert report["status"] == "failed"
    assert "angMET fora de [0, 360)" in " ".join(report["failures"])


def test_bluesky_rejects_height_from_wrong_level(tmp_path):
    base = tmp_path / "saida"
    base.mkdir()
    path = base / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_RJ_N200_00_20221215_00.csv"
    write_csv(path, BLUESKY_AUT, [[lat, lon, 65.6, 0.0, 1.0] for lat, lon in GRID])
    report = check.check_products(tmp_path, "bluesky", [(base, True)])
    assert report["status"] == "failed"
    assert "hMET" in " ".join(report["failures"])


def test_rejects_lf_only_and_unsorted_coordinates(tmp_path):
    base = tmp_path / "saida"
    base.mkdir()
    lf = base / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_RJ_N200_00_20221215_00.csv"
    write_csv(lf, BLUESKY_AUT, [[lat, lon, H200, 0.0, 1.0] for lat, lon in GRID], newline="\n")
    report = check.check_products(tmp_path, "bluesky", [(base, True)])
    assert report["status"] == "failed"
    assert "CRLF" in " ".join(report["failures"])

    write_csv(lf, BLUESKY_AUT, [[lat, lon, H200, 0.0, 1.0] for lat, lon in reversed(GRID)])
    report = check.check_products(tmp_path, "bluesky", [(base, True)])
    assert report["status"] == "failed"
    assert "ordem crescente" in " ".join(report["failures"])


def test_preditor_accepts_aut_and_man_and_rejects_kelvin(tmp_path):
    base = tmp_path / "saida"
    base.mkdir()
    preditor_product(
        base / "GFS_0.25_matriz_lat_lon_Vento_UVT_Predi_RJ_N20_00_20221215_00.csv"
    )
    preditor_product(
        base / "matriz_vento_predi_LonMin:-1_N20_00_20221215_00.csv",
        header=PREDITOR_MAN,
    )
    report = check.check_products(tmp_path, "preditor", [(base, True)])
    assert report["status"] == "ok"
    assert report["variants"] == {"AUT": 1, "MAN": 1}

    preditor_product(
        base / "GFS_0.25_matriz_lat_lon_Vento_UVT_Predi_RJ_N20_00_20221215_00.csv",
        temperature=400.0,
    )
    report = check.check_products(tmp_path, "preditor", [(base, True)])
    assert report["status"] == "failed"
    assert "temperatura" in " ".join(report["failures"])


def test_planilhas_validates_scalars_and_skips_wind(tmp_path):
    base = tmp_path / "saida"
    base.mkdir()
    write_csv(base / "GFS_0.25_AM_N850_temp_00_20221215_00.csv", ("lat", "lon", "temp"), [[lat, lon, 20.0] for lat, lon in GRID])
    write_csv(base / "GFS_0.25_AM_N700_nuvem_00_20221215_00.csv", ("lat", "lon", "nuvem"), [[lat, lon, 50.0] for lat, lon in GRID])
    bluesky_product(base / "GFS_0.25_matriz_lat_lon_alt_angMET_VentoResult_RJ_N200_00_20221215_00.csv")
    report = check.check_products(tmp_path, "planilhas", [(base, False)])
    assert report["status"] == "ok"
    assert report["files"] == 2


def test_planilhas_rejects_out_of_range_value(tmp_path):
    base = tmp_path / "saida"
    base.mkdir()
    write_csv(base / "GFS_0.25_AM_N700_nuvem_00_20221215_00.csv", ("lat", "lon", "nuvem"), [[lat, lon, 150.0] for lat, lon in GRID])
    report = check.check_products(tmp_path, "planilhas", [(base, False)])
    assert report["status"] == "failed"
    assert "nuvem" in " ".join(report["failures"])


def make_environment(tmp_path):
    root = tmp_path / "servidor_MET"
    for relative in check.REQUIRED_DIRS:
        (root / relative).mkdir(parents=True, exist_ok=True)
    (root / "LEIA-ME.md").write_text("ambiente de teste", encoding="utf-8")
    config = (
        f"dir_gribs={root / 'gribs'}\n"
        f"dir_mapas={root / 'mapasGrib'}\n"
        f"dir_matrizes={root / 'matrizGrib'}\n"
        f"dir_matrizes_predi={root / 'matrizGrib' / 'predi'}\n"
        f"dir_matrizes_bluesky={root / 'matrizGrib' / 'bluesky'}\n"
    )
    (root / "environment" / "path.conf").write_text(config, encoding="utf-8")
    for name in check.REQUIRED_SCRIPTS:
        script = root / "bin" / name
        script.write_text("#!/bin/bash\n", encoding="utf-8")
        script.chmod(0o755)
    for name in ("acceptance_check.py", "release_phase4.py"):
        shutil.copy2(ROOT / "reprocessamento" / name, root / "tools" / name)

    (root / "app" / "foo.py").write_text("codigo\n", encoding="utf-8")
    write_csv(root / "matrizGrib" / "x.csv", ("lat", "lon", "temp"), [[0, 0, 20.0]])
    (root / "mapasGrib").mkdir(exist_ok=True)

    candidate = root / "evidence" / "release" / "candidate"
    candidate.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "app", candidate / "code")
    shutil.copytree(root / "matrizGrib", candidate / "products" / "matrizGrib")
    (candidate / "validation.json").write_text(
        json.dumps({"status": "ok", "failures": []}), encoding="utf-8"
    )
    release = {
        "validation_sha256": sha(candidate / "validation.json"),
        "files": {
            "code/foo.py": sha(root / "app" / "foo.py"),
            "products/matrizGrib/x.csv": sha(root / "matrizGrib" / "x.csv"),
            "validation.json": sha(candidate / "validation.json"),
        },
    }
    (candidate / "release.json").write_text(json.dumps(release), encoding="utf-8")
    release_hash = sha(candidate / "release.json")

    grib = root / "gribs" / "20221215" / "00" / "gfs.t00z.pgrb2.0p25.f000"
    grib.parent.mkdir(parents=True, exist_ok=True)
    grib.write_bytes(b"GRIB" + b"0" * 12)
    manifest = {
        "samples": [
            {
                "date": "20221215",
                "cycle": "00",
                "forecast": 0,
                "sha256": sha(grib),
            }
        ]
    }
    (root / "evidence" / "samples" / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    acceptance = {
        "release_sha256": release_hash,
        "approved": False,
        "consumers": list(check.CONSUMERS),
        "evidence": {consumer: None for consumer in check.CONSUMERS},
        "approved_by": None,
        "accepted_at_utc": None,
        "note": "pendente",
    }
    (root / "acceptance" / "acceptance.json").write_text(
        json.dumps(acceptance), encoding="utf-8"
    )
    return root


def test_environment_checks_hashes_and_counts(tmp_path):
    root = make_environment(tmp_path)
    report = check.check_environment(root, check_dependencies=False)
    assert report["status"] == "ok", report["failures"]
    assert report["gribs"] == 1
    assert report["csv"] == 1
    assert report["png"] == 0
    assert report["checked_files"] == 3


def test_environment_detects_changed_product(tmp_path):
    root = make_environment(tmp_path)
    (root / "matrizGrib" / "x.csv").write_text("alterado", encoding="utf-8")
    report = check.check_environment(root, check_dependencies=False)
    assert report["status"] == "failed"
    assert any("hash divergente" in item for item in report["failures"])


def test_environment_ignores_local_path_conf_hash(tmp_path):
    root = make_environment(tmp_path)
    (root / "app" / "environment").mkdir()
    (root / "app" / "environment" / "path.conf").write_text(
        "dir_gribs=/caminho/local\n", encoding="utf-8"
    )
    release_path = root / "evidence" / "release" / "candidate" / "release.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    original_config = release_path.parent / "code/environment/path.conf"
    original_config.parent.mkdir()
    original_config.write_text("dir_gribs=/origem/gribs\n", encoding="utf-8")
    release["files"]["code/environment/path.conf"] = sha(original_config)
    release_path.write_text(json.dumps(release), encoding="utf-8")

    acceptance_path = root / "acceptance" / "acceptance.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    acceptance["release_sha256"] = sha(release_path)
    acceptance_path.write_text(json.dumps(acceptance), encoding="utf-8")

    report = check.check_environment(root, check_dependencies=False)
    assert report["status"] == "ok", report["failures"]
    assert report["path_conf_overridden"] is True


def test_environment_detects_missing_grib(tmp_path):
    root = make_environment(tmp_path)
    (root / "gribs" / "20221215" / "00" / "gfs.t00z.pgrb2.0p25.f000").unlink()
    report = check.check_environment(root, check_dependencies=False)
    assert report["status"] == "failed"
    assert any("GRIB ausente" in item for item in report["failures"])


def test_pending_acceptance_requires_approved_for_promotion(tmp_path):
    root = make_environment(tmp_path)
    report = check.check_acceptance(root, require_approved=True)
    assert report["state"] == "pending"
    assert report["pending"] is True
    assert report["status"] == "failed"


def test_register_sign_and_tamper_evidence(tmp_path):
    root = make_environment(tmp_path)
    source = tmp_path / "evidencia.log"
    source.write_text("teste externo concluido\n", encoding="utf-8")
    for consumer in check.CONSUMERS:
        check.register_evidence(root, consumer, source, "teste " + consumer)
    report = check.check_acceptance(root)
    assert report["status"] == "ok", report["failures"]
    assert report["state"] == "pending"
    report = check.check_acceptance(root, require_approved=True)
    assert report["status"] == "failed"
    assert report["pending"] is True

    result = check.sign_acceptance(root, "Responsavel")
    assert result["state"] == "approved"
    report = check.check_acceptance(root, require_approved=True)
    assert report["status"] == "ok"
    assert report["state"] == "approved"
    assert report["approved_by"] == "Responsavel"

    data = json.loads((root / "acceptance" / "acceptance.json").read_text())
    evidence = root / data["evidence"]["BlueSky"]["path"]
    evidence.write_text("adulterado", encoding="utf-8")
    report = check.check_acceptance(root, require_approved=True)
    assert report["status"] == "failed"
    assert any("hash da evidencia" in item for item in report["failures"])


def test_sign_requires_three_evidences(tmp_path):
    root = make_environment(tmp_path)
    with pytest.raises(check.CheckError, match="evidencia ausente"):
        check.sign_acceptance(root, "Responsavel")


def test_acceptance_hash_must_match_installed_release(tmp_path):
    root = make_environment(tmp_path)
    data = json.loads((root / "acceptance" / "acceptance.json").read_text())
    data["release_sha256"] = "0" * 64
    (root / "acceptance" / "acceptance.json").write_text(json.dumps(data))
    report = check.check_acceptance(root)
    assert report["status"] == "failed"
    assert any("release_sha256" in item for item in report["failures"])


def test_cli_returns_two_for_pending_acceptance(tmp_path, capsys):
    root = make_environment(tmp_path)
    code = check.main(["acceptance", "--root", str(root), "--require-approved"])
    assert code == 2
    assert "pendente" in capsys.readouterr().out


def test_candidate_copy_is_verified_even_when_app_is_intact(tmp_path):
    root = make_environment(tmp_path)
    (root / "evidence/release/candidate/code/foo.py").write_text("alterado")
    report = check.check_environment(root, check_dependencies=False)
    assert report["status"] == "failed"
    assert any("inventario/hash" in failure for failure in report["failures"])


def test_active_release_promotion_and_rollback_are_checked_independently(tmp_path):
    root = make_environment(tmp_path)
    candidate = root / "evidence/release/candidate"
    older = tmp_path / "older"
    shutil.copytree(candidate, older)
    (older / "code/foo.py").write_text("versao anterior\n")
    manifest = json.loads((older / "release.json").read_text())
    manifest["files"] = release_tools.inventory(older)
    (older / "release.json").write_text(json.dumps(manifest))
    original_acceptance = (root / "acceptance/acceptance.json").read_bytes()

    release_tools.promote(older, root, rehearsal=True)
    release_tools.promote(candidate, root, rehearsal=True)
    report = check.check_environment(root, check_dependencies=False)
    assert report["status"] == "ok", report["failures"]
    assert report["deployment"] == "candidate-active"
    assert report["active_release_sha256"] == sha(candidate / "release.json")

    setup.install_scripts(root)
    result = subprocess.run(
        ["bash", "-c", 'source "$1/bin/ativar.sh"; test "$PYTHONDONTWRITEBYTECODE" = 1; echo "$MET_ACTIVE_CODE"',
         "bash", str(root)], text=True, capture_output=True, check=True)
    assert str((root / "current/code").resolve()) in result.stdout

    release_tools.rollback(root)
    report = check.check_environment(root, check_dependencies=False)
    assert report["status"] == "ok", report["failures"]
    assert report["deployment"] == "other-release-active"
    assert report["active_release_sha256"] == sha(older / "release.json")
    assert report["release_sha256"] == sha(candidate / "release.json")
    assert check.check_acceptance(root)["state"] == "pending"
    assert (root / "acceptance/acceptance.json").read_bytes() == original_acceptance

    (root / "current/code/foo.py").write_text("adulterado")
    assert check.check_environment(root, check_dependencies=False)["status"] == "failed"
    assert check.check_acceptance(root)["status"] == "failed"


@pytest.mark.parametrize("kind", ["broken", "outside", "directory"])
def test_invalid_current_is_not_silently_ignored(tmp_path, kind):
    root = make_environment(tmp_path)
    current = root / "current"
    if kind == "directory":
        current.mkdir()
    elif kind == "outside":
        current.symlink_to(root / "evidence/release/candidate", target_is_directory=True)
    else:
        current.symlink_to("releases/missing", target_is_directory=True)
    report = check.check_environment(root, check_dependencies=False)
    assert report["status"] == "failed"
    assert any("current" in failure for failure in report["failures"])
    if kind != "outside":
        setup.install_scripts(root)
        result = subprocess.run(["bash", "-c", 'source "$1/bin/ativar.sh"', "bash", str(root)])
        assert result.returncode != 0


def test_register_rejects_wrong_release_without_copying_evidence(tmp_path):
    root = make_environment(tmp_path)
    path = root / "acceptance/acceptance.json"
    data = json.loads(path.read_text())
    data["release_sha256"] = "0" * 64
    path.write_text(json.dumps(data))
    source = tmp_path / "result.log"
    source.write_text("resultado de teste sintetico")
    before = path.read_bytes()
    with pytest.raises(check.CheckError, match="release_sha256"):
        check.register_evidence(root, "BlueSky", source, "teste")
    assert path.read_bytes() == before
    assert not list((root / "acceptance/evidence/BlueSky").iterdir())


def test_cli_require_evidence_checks_all_consumers_without_signing(tmp_path, capsys):
    root = make_environment(tmp_path)
    command = ["acceptance", "--root", str(root), "--require-evidence", "--json"]
    assert check.main(command) == 1
    report = json.loads(capsys.readouterr().out)
    assert len(report["failures"]) == 3
    evidence = tmp_path / "synthetic.log"
    evidence.write_text("teste sintetico")
    for consumer in check.CONSUMERS:
        check.register_evidence(root, consumer, evidence, "regressao")
    assert check.main(command) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["state"] == "pending"
    assert not report["failures"]
