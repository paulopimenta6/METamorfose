#!/usr/bin/env python3
"""Verifica o ambiente de produção e o aceite da Fase 4.

Subcomandos:
  environment  layout, hashes da release e contagens de produtos;
  bluesky      contrato das matrizes consumidas pelo BlueSky;
  preditor     contrato das matrizes consumidas pelo preditor;
  planilhas    contrato das matrizes escalares usadas nas planilhas;
  acceptance   estado do aceite (``--require-approved`` para promoção);
  register     registra o log de um teste como evidência;
  sign         assina o aceite depois das três evidências.

O verificador não substitui a execução dos aplicativos externos. Ele confere
os contratos dos arquivos, o vínculo com o SHA-256 exato da release e a
existência das evidências registradas.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

CONSUMERS = ("BlueSky", "preditor", "planilhas")
GRIB_NAME = re.compile(r"^gfs\.t\d{2}z\.pgrb2\.0p25\.f\d{3}$")
N_LEVEL = re.compile(r"_N(\d+)_")

BLUESKY_HEADERS = {
    ("lat", "lon", "hMET", "angMET", "vento_resultante"): "AUT",
    ("lat", "lon", "hMET<feet>", "angMET<grau>", "vento_resultante<knot>"): "MAN",
}
PREDITOR_HEADERS = {
    ("lat", "lon", "vento U", "vento V", "temp"): "AUT",
    ("lat", "lon", "vento U", "vento V", "temperatura K"): "MAN",
}
SCALAR_LIMITS = {
    # nome historico: (minimo, maximo, unidade)
    "temp": (-100.0, 70.0, "C"),
    "temps": (-100.0, 90.0, "C"),
    "nuvem": (0.0, 100.0, "%"),
    "ps": (500.0, 1100.0, "hPa"),
    "prnm": (500.0, 1100.0, "hPa"),
    "umidadeRel": (0.0, 100.0, "%"),
    "chuvaNaoConvec": (0.0, 10000.0, "mm"),
    "chuvaConvec": (0.0, 10000.0, "mm"),
}
HEIGHT_LEVELS = (20, 30, 40, 50, 80)
REQUIRED_SCRIPTS = (
    "ativar.sh",
    "verificar.sh",
    "status.sh",
    "promover.sh",
    "rollback.sh",
    "assinar.sh",
    "registrar_evidencia.sh",
    "testar_bluesky.sh",
    "testar_preditor.sh",
    "testar_planilhas.sh",
)
REQUIRED_DIRS = (
    "app",
    "gribs",
    "mapasGrib",
    "matrizGrib",
    "matrizGrib/predi",
    "matrizGrib/bluesky",
    "environment",
    "acceptance/evidence/BlueSky",
    "acceptance/evidence/preditor",
    "acceptance/evidence/planilhas",
    "evidence/release/candidate",
    "evidence/samples",
    "logs",
    "run/locks",
    "backups",
    "aceitacao-manual",
    "bin",
)


class CheckError(ValueError):
    """Erro de contrato que deve ser mostrado sem traceback."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CheckError("arquivo ausente: %s" % path) from exc
    except json.JSONDecodeError as exc:
        raise CheckError("JSON invalido em %s: %s" % (path, exc)) from exc


def write_json_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp-%d" % (path.name, os.getpid()))
    try:
        temporary.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def iso_datetime(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("data/hora ausente")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed


def resolve_root(value):
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise CheckError("raiz do ambiente nao encontrada: %s" % root)
    return root


def default_root():
    return os.environ.get("MET_PROD_ROOT") or str(Path.home() / "MET" / "servidor_MET")


def load_acceptance(root):
    path = Path(root) / "acceptance" / "acceptance.json"
    data = read_json(path)
    if not isinstance(data, dict):
        raise CheckError("acceptance.json deve ser um objeto")
    return data


def installed_release_hash(root):
    release = Path(root) / "evidence" / "release" / "candidate" / "release.json"
    if not release.is_file():
        raise CheckError("release.json ausente em %s" % release)
    return sha256_file(release)


def read_path_conf(path):
    values = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise CheckError("linha invalida em %s: %r" % (path, line))
        key, value = line.split("=", 1)
        item = Path(value.strip()).expanduser()
        if not item.is_absolute():
            item = Path(path).resolve().parent / item
        values[key.strip()] = item.resolve()
    return values


def read_matrix(path):
    """Le um CSV de produto e devolve (header, linhas, bytes)."""
    raw = Path(path).read_bytes()
    if not raw:
        raise CheckError("arquivo vazio")
    if raw.count(b"\n") != raw.count(b"\r\n"):
        raise CheckError("fim de linha fora do contrato CRLF")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckError("conteudo nao e UTF-8: %s" % exc) from exc
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise CheckError("CSV sem linhas")
    return tuple(rows[0]), rows[1:], raw


def numeric_rows(rows, width):
    parsed = []
    for index, row in enumerate(rows, start=2):
        if len(row) != width:
            raise CheckError(
                "linha %d com %d colunas; esperado %d" % (index, len(row), width)
            )
        try:
            values = [float(item) for item in row]
        except ValueError as exc:
            raise CheckError("linha %d nao numerica: %s" % (index, exc)) from exc
        if not all(math.isfinite(item) for item in values):
            raise CheckError("linha %d com valor nao finito" % index)
        parsed.append(values)
    if not parsed:
        raise CheckError("CSV sem dados")
    return parsed


def validate_grid(data, issues):
    coordinates = [(row[0], row[1]) for row in data]
    for lat, lon in coordinates:
        if not -90.0 <= lat <= 90.0:
            issues.append("latitude fora de [-90, 90]: %s" % lat)
            break
    for lat, lon in coordinates:
        if not -180.0 <= lon <= 180.0:
            issues.append("longitude fora de [-180, 180]: %s" % lon)
            break
    for previous, current in zip(coordinates, coordinates[1:]):
        if current <= previous:
            issues.append("coordenadas fora da ordem crescente em lat/lon")
            break
    latitudes = {row[0] for row in coordinates}
    longitudes = {row[1] for row in coordinates}
    if len(latitudes) * len(longitudes) != len(coordinates):
        issues.append("grade nao retangular ou coordenada repetida")
    return latitudes, longitudes


def bluesky_height_issue(path, data):
    match = N_LEVEL.search(Path(path).name)
    if not match:
        return None
    level = int(match.group(1))
    expected = (
        level * 3.28084
        if level in HEIGHT_LEVELS
        else (1.0 - (level / 1013.25) ** 0.190284) * 145366.45
    )
    tolerance = 0.01 if level in HEIGHT_LEVELS else 0.5
    for row in data:
        if abs(row[2] - expected) > tolerance:
            return "hMET %.6f difere do nivel %d hPa (esperado %.6f)" % (
                row[2],
                level,
                expected,
            )
    return None


def validate_matrix(path, kind):
    """Valida um arquivo e devolve o resultado daquele arquivo."""
    result = {"path": str(path), "variant": None, "rows": 0, "failures": []}
    try:
        header, rows, raw = read_matrix(path)
        if kind == "bluesky":
            variant = BLUESKY_HEADERS.get(header)
            width = 5
        elif kind == "preditor":
            variant = PREDITOR_HEADERS.get(header)
            width = 5
        else:
            if len(header) != 3 or header[0] != "lat" or header[1] != "lon":
                raise CheckError("header escalar invalido: %r" % (header,))
            variable = header[2]
            if variable not in SCALAR_LIMITS:
                raise CheckError("variavel escalar desconhecida: %r" % variable)
            variant = "comum"
            width = 3
        if variant is None:
            raise CheckError("header nao reconhecido para %s: %r" % (kind, header))
        data = numeric_rows(rows, width)
        result.update(variant=variant, rows=len(data), bytes=len(raw), header=list(header))
        issues = []
        validate_grid(data, issues)
        if kind == "bluesky":
            for row in data:
                if not 0.0 <= row[3] < 360.0:
                    issues.append("angMET fora de [0, 360): %s" % row[3])
                    break
            for row in data:
                if row[4] < 0.0 or row[4] > 200.0:
                    issues.append("vento_resultante fora de [0, 200] kt: %s" % row[4])
                    break
            height_issue = bluesky_height_issue(path, data)
            if height_issue:
                issues.append(height_issue)
        elif kind == "preditor":
            for row in data:
                if not -150.0 <= row[2] <= 150.0 or not -150.0 <= row[3] <= 150.0:
                    issues.append("vento U/V fora de [-150, 150] m/s")
                    break
            for row in data:
                if not 150.0 <= row[4] <= 350.0:
                    issues.append("temperatura fora de [150, 350] K: %s" % row[4])
                    break
        else:
            variable = header[2]
            low, high, unit = SCALAR_LIMITS[variable]
            for row in data:
                if not low <= row[2] <= high:
                    issues.append(
                        "%s fora de [%s, %s] %s: %s"
                        % (variable, low, high, unit, row[2])
                    )
                    break
            if "_" + variable + "_" not in Path(path).name:
                issues.append("nome do arquivo nao contem a variavel %r" % variable)
        result["failures"] = issues
        result["lat_range"] = [min(row[0] for row in data), max(row[0] for row in data)]
        result["lon_range"] = [min(row[1] for row in data), max(row[1] for row in data)]
    except (CheckError, OSError) as exc:
        result["failures"] = [str(exc)]
    return result


def classify(path):
    name = Path(path).name
    if "matriz_lat_lon_alt_angMET_VentoResult" in name or "matriz_vento_bluesky" in name:
        return "bluesky"
    if "Vento_UVT_Predi" in name or "matriz_vento_predi" in name:
        return "preditor"
    if "matriz_vento" in name or "matriz_lat_lon" in name:
        return None
    if name.startswith("GFS_"):
        return "planilhas"
    return None


def products_in(base, kind, family_directory=False):
    base = Path(base)
    if not base.is_dir():
        return []
    result = []
    for path in sorted(base.rglob("*.csv")):
        if family_directory or classify(path) == kind:
            result.append(path)
    return result


def check_products(root, kind, directories):
    root = Path(root)
    sources = []
    failures = []
    total_files = 0
    total_rows = 0
    variants = {}
    for directory, family_directory in directories:
        files = products_in(directory, kind, family_directory)
        source = {
            "path": str(directory),
            "files": len(files),
            "rows": 0,
            "variants": {},
            "failures": [],
        }
        if not files:
            source["failures"].append("nenhum produto encontrado")
        for path in files:
            outcome = validate_matrix(path, kind)
            total_files += 1
            total_rows += outcome["rows"]
            source["rows"] += outcome["rows"]
            if outcome["variant"]:
                variants[outcome["variant"]] = variants.get(outcome["variant"], 0) + 1
                source["variants"][outcome["variant"]] = (
                    source["variants"].get(outcome["variant"], 0) + 1
                )
            for issue in outcome["failures"]:
                message = "%s: %s" % (path, issue)
                failures.append(message)
                source["failures"].append(message)
        sources.append(source)
    report = {
        "kind": kind,
        "status": "ok" if not failures and total_files else "failed",
        "files": total_files,
        "rows": total_rows,
        "variants": variants,
        "sources": sources,
        "failures": failures,
        "checked_at_utc": utc_now(),
    }
    return report


def check_environment(root, check_dependencies=True):
    root = Path(root)
    failures = []
    report = {
        "root": str(root),
        "release_sha256": None,
        "acceptance": None,
        "gribs": 0,
        "csv": 0,
        "png": 0,
        "checked_files": 0,
        "failures": failures,
        "checked_at_utc": utc_now(),
    }

    def failure(message):
        failures.append(message)

    for relative in REQUIRED_DIRS:
        if not (root / relative).is_dir():
            failure("diretorio ausente: %s" % relative)
    for relative in ("LEIA-ME.md", "environment/path.conf", "acceptance/acceptance.json"):
        if not (root / relative).is_file():
            failure("arquivo ausente: %s" % relative)
    for name in REQUIRED_SCRIPTS:
        script = root / "bin" / name
        if not script.is_file():
            failure("script ausente: bin/%s" % name)
        elif not os.access(script, os.X_OK):
            failure("script sem permissao de execucao: bin/%s" % name)

    try:
        config = read_path_conf(root / "environment" / "path.conf")
        expected = {
            "dir_gribs": root / "gribs",
            "dir_mapas": root / "mapasGrib",
            "dir_matrizes": root / "matrizGrib",
            "dir_matrizes_predi": root / "matrizGrib" / "predi",
            "dir_matrizes_bluesky": root / "matrizGrib" / "bluesky",
        }
        for key, value in expected.items():
            if key not in config:
                failure("path.conf sem %s" % key)
            elif config[key] != value.resolve():
                failure(
                    "path.conf %s aponta para %s; esperado %s"
                    % (key, config[key], value.resolve())
                )
    except (CheckError, OSError) as exc:
        failure("path.conf invalido: %s" % exc)

    try:
        acceptance = load_acceptance(root)
        report["acceptance"] = "approved" if acceptance.get("approved") is True else "pending"
        report["release_sha256"] = acceptance.get("release_sha256")
    except (CheckError, OSError) as exc:
        failure(str(exc))
        acceptance = {}

    release_hash = None
    candidate = root / "evidence" / "release" / "candidate"
    try:
        release_hash = installed_release_hash(root)
        report["release_sha256"] = release_hash
        if acceptance and acceptance.get("release_sha256") != release_hash:
            failure(
                "acceptance.release_sha256 nao corresponde a release instalada "
                "(%s != %s)" % (acceptance.get("release_sha256"), release_hash)
            )
        release = read_json(candidate / "release.json")
        if release.get("validation_sha256") != sha256_file(candidate / "validation.json"):
            failure("validation.json nao corresponde a release.json")
        files = release.get("files")
        if not isinstance(files, dict) or not files:
            failure("release.json sem inventario de arquivos")
            files = {}
        for relative, expected_hash in files.items():
            if relative == "code/environment/path.conf":
                # Este arquivo e reescrito para apontar para a raiz local.
                report["path_conf_overridden"] = True
                continue
            if relative.startswith("code/"):
                target = root / "app" / relative[len("code/"):]
            elif relative.startswith("products/"):
                target = root / relative[len("products/"):]
            else:
                target = candidate / relative
            if not target.is_file():
                failure("arquivo da release ausente: %s" % relative)
                continue
            report["checked_files"] += 1
            if sha256_file(target) != expected_hash:
                failure("hash divergente: %s" % relative)
        expected_csv = sum(
            1 for item in files if item.startswith("products/") and item.endswith(".csv")
        )
        expected_png = sum(
            1 for item in files if item.startswith("products/") and item.endswith(".png")
        )
        actual_csv = len(list((root / "matrizGrib").rglob("*.csv")))
        actual_png = len(list((root / "mapasGrib").rglob("*.png")))
        report["csv"] = actual_csv
        report["png"] = actual_png
        if actual_csv != expected_csv:
            failure("matrizGrib tem %d CSVs; release tem %d" % (actual_csv, expected_csv))
        if actual_png != expected_png:
            failure("mapasGrib tem %d PNGs; release tem %d" % (actual_png, expected_png))
    except (CheckError, OSError) as exc:
        failure(str(exc))

    try:
        manifest = read_json(root / "evidence" / "samples" / "manifest.json")
        samples = manifest.get("samples") if isinstance(manifest, dict) else None
        if not isinstance(samples, list) or not samples:
            failure("manifesto de GRIBs ausente ou vazio")
            samples = []
        expected_gribs = set()
        for sample in samples:
            date = str(sample.get("date", ""))
            cycle = str(sample.get("cycle", "")).zfill(2)
            forecast = int(sample.get("forecast", 0))
            relative = (
                Path("gribs") / date / cycle
                / ("gfs.t%sz.pgrb2.0p25.f%03d" % (cycle, forecast))
            )
            expected_gribs.add(relative)
            target = root / relative
            if not target.is_file():
                failure("GRIB ausente: %s" % relative)
                continue
            if target.read_bytes()[:4] != b"GRIB":
                failure("GRIB invalido: %s" % relative)
            expected_hash = sample.get("sha256")
            if expected_hash and sha256_file(target) != expected_hash:
                failure("hash do GRIB divergente: %s" % relative)
        report["gribs"] = len(expected_gribs)
        actual_gribs = {
            path.relative_to(root)
            for path in (root / "gribs").rglob("*")
            if path.is_file() and GRIB_NAME.match(path.name)
        }
        if actual_gribs != expected_gribs:
            failure(
                "conjunto de GRIBs diverge do manifesto (%d instalados, %d esperados)"
                % (len(actual_gribs), len(expected_gribs))
            )
    except (CheckError, OSError, TypeError, ValueError) as exc:
        failure("manifesto de GRIBs invalido: %s" % exc)

    if check_dependencies:
        for module in ("numpy", "pygrib", "matplotlib"):
            try:
                if importlib.util.find_spec(module) is None:
                    failure("modulo Python ausente: %s" % module)
            except (ImportError, AttributeError):
                failure("modulo Python ausente: %s" % module)
        try:
            if importlib.util.find_spec("mpl_toolkits.basemap") is None:
                failure("modulo Python ausente: mpl_toolkits.basemap")
        except (ImportError, AttributeError):
            failure("modulo Python ausente: mpl_toolkits.basemap")

    current = root / "current"
    if current.exists():
        try:
            target = current.resolve()
            releases = (root / "releases").resolve()
            if not target.is_relative_to(releases):
                failure("current aponta para fora de releases/")
            elif release_hash and sha256_file(target / "release.json") != release_hash:
                failure("current nao corresponde a release aceita")
        except (OSError, CheckError) as exc:
            failure("current invalido: %s" % exc)

    report["status"] = "ok" if not failures else "failed"
    return report


def resolve_evidence(root, consumer, entry):
    if isinstance(entry, str):
        value = entry
        expected_hash = None
    elif isinstance(entry, dict):
        value = entry.get("path")
        expected_hash = entry.get("sha256")
    else:
        return None, "evidencia deve ser caminho ou objeto com path"
    if not isinstance(value, str) or not value.strip():
        return None, "evidencia sem path"
    path = Path(value).expanduser()
    candidates = [path] if path.is_absolute() else [Path(root) / path]
    if not path.is_absolute():
        candidates += [
            Path(root) / "acceptance" / path,
            Path(root) / "acceptance" / "evidence" / consumer / path,
        ]
    for candidate in candidates:
        if candidate.is_file():
            if candidate.stat().st_size == 0:
                return None, "evidencia vazia: %s" % candidate
            if expected_hash:
                if not isinstance(expected_hash, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", expected_hash
                ):
                    return None, "sha256 invalido na evidencia"
                if sha256_file(candidate) != expected_hash:
                    return None, "hash da evidencia diverge: %s" % candidate
            return candidate.resolve(), None
    return None, "evidencia nao encontrada: %s" % value


def check_acceptance(root, require_approved=False, require_evidence=False):
    root = Path(root)
    failures = []
    state = "pending"
    data = {}
    report = {
        "root": str(root),
        "state": state,
        "release_sha256": None,
        "approved_by": None,
        "accepted_at_utc": None,
        "evidence": {},
        "failures": failures,
        "pending": False,
        "checked_at_utc": utc_now(),
    }
    try:
        data = load_acceptance(root)
        actual_hash = installed_release_hash(root)
        report["release_sha256"] = actual_hash
        if data.get("release_sha256") != actual_hash:
            failures.append(
                "release_sha256 do aceite nao corresponde a release instalada"
            )
        approved = data.get("approved")
        if not isinstance(approved, bool):
            failures.append("campo approved deve ser booleano")
            approved = False
        state = "approved" if approved else "pending"
        report["state"] = state
        report["approved_by"] = data.get("approved_by")
        report["accepted_at_utc"] = data.get("accepted_at_utc")
        consumers = data.get("consumers")
        if not isinstance(consumers, list) or set(consumers) != set(CONSUMERS):
            failures.append(
                "consumers deve ser exatamente %s" % (list(CONSUMERS),)
            )
        evidence = data.get("evidence")
        if not isinstance(evidence, dict):
            failures.append("campo evidence deve ser um objeto")
            evidence = {}
        for consumer in CONSUMERS:
            entry = evidence.get(consumer)
            if entry is None:
                if approved or require_evidence:
                    failures.append("evidencia ausente para %s" % consumer)
                report["evidence"][consumer] = None
                continue
            path, error = resolve_evidence(root, consumer, entry)
            if error:
                failures.append("%s: %s" % (consumer, error))
                report["evidence"][consumer] = None
            else:
                report["evidence"][consumer] = str(path)
        if approved:
            if not isinstance(data.get("approved_by"), str) or not data["approved_by"].strip():
                failures.append("approved_by ausente")
            try:
                iso_datetime(data.get("accepted_at_utc"))
            except (ValueError, TypeError) as exc:
                failures.append("accepted_at_utc invalido: %s" % exc)
        if require_approved and not approved:
            report["pending"] = True
            failures.append("aceite pendente; execute os tres consumidores e assine")
    except (CheckError, OSError) as exc:
        failures.append(str(exc))
    report["status"] = "ok" if not failures else "failed"
    return report


def register_evidence(root, consumer, source, notes):
    root = Path(root)
    if consumer not in CONSUMERS:
        raise CheckError("consumidor invalido: %s" % consumer)
    data = load_acceptance(root)
    if data.get("approved") is True:
        raise CheckError("aceite ja aprovado; edite acceptance.json manualmente para trocar evidencias")
    source = Path(source).expanduser().resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise CheckError("evidencia invalida: %s" % source)
    destination_dir = root / "acceptance" / "evidence" / consumer
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = destination_dir / ("%s-%s" % (stamp, source.name))
    counter = 1
    while destination.exists():
        destination = destination_dir / ("%s-%d-%s" % (stamp, counter, source.name))
        counter += 1
    shutil.copy2(source, destination)
    entry = {
        "path": destination.relative_to(root).as_posix(),
        "sha256": sha256_file(destination),
        "notes": notes or "",
        "registered_at_utc": utc_now(),
    }
    evidence = data.setdefault("evidence", {})
    if not isinstance(evidence, dict):
        raise CheckError("campo evidence deve ser um objeto")
    evidence[consumer] = entry
    write_json_atomic(root / "acceptance" / "acceptance.json", data)
    return {"consumer": consumer, "evidence": entry}


def sign_acceptance(root, approved_by):
    root = Path(root)
    name = (approved_by or "").strip()
    if not name:
        raise CheckError("approved_by nao pode ser vazio")
    report = check_acceptance(root, require_evidence=True)
    if report["failures"]:
        raise CheckError(
            "aceite nao pode ser assinado:\n- " + "\n- ".join(report["failures"])
        )
    data = load_acceptance(root)
    if data.get("approved") is True:
        return {"state": "already-approved", "approved_by": data.get("approved_by")}
    data["approved"] = True
    data["approved_by"] = name
    data["accepted_at_utc"] = utc_now()
    data["note"] = "Aceite registrado apos execucao dos tres consumidores."
    write_json_atomic(root / "acceptance" / "acceptance.json", data)
    return {
        "state": "approved",
        "approved_by": name,
        "accepted_at_utc": data["accepted_at_utc"],
        "release_sha256": data["release_sha256"],
    }


def print_report(report, as_json, limit):
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    for key in ("kind", "state", "root", "release_sha256", "acceptance"):
        if key in report and report[key] is not None:
            print("%s: %s" % (key, report[key]))
    if "gribs" in report:
        print("gribs: %s" % report["gribs"])
    if "csv" in report:
        print("csv: %s" % report["csv"])
    if "png" in report:
        print("png: %s" % report["png"])
    if "checked_files" in report:
        print("arquivos verificados: %s" % report["checked_files"])
    if "files" in report:
        print("arquivos: %s" % report["files"])
        print("linhas: %s" % report["rows"])
        if report.get("variants"):
            print(
                "variantes: "
                + ", ".join("%s=%s" % item for item in sorted(report["variants"].items()))
            )
    for source in report.get("sources", []):
        print(
            "  %s: %s arquivos, %s linhas%s"
            % (
                source["path"],
                source["files"],
                source["rows"],
                (", " + ", ".join("%s=%s" % item for item in sorted(source["variants"].items())))
                if source.get("variants")
                else "",
            )
        )
    failures = report.get("failures", [])
    if failures:
        print("falhas: %s" % len(failures))
        for message in failures[:limit]:
            print("  - %s" % message)
        if len(failures) > limit:
            print("  ... mais %d falhas" % (len(failures) - limit))
    else:
        print("falhas: 0")
    print("status: %s" % report.get("status", "ok"))


def consumer_directories(root, kind, extra):
    directories = []
    if extra:
        directories.append((Path(extra).expanduser().resolve(), False))
    else:
        if kind == "bluesky":
            directories.append((root / "matrizGrib" / "bluesky", True))
        elif kind == "preditor":
            directories.append((root / "matrizGrib" / "predi", True))
        else:
            directories.append((root / "matrizGrib", False))
    return directories


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(sub):
        sub.add_argument(
            "--root",
            default=default_root(),
            help="raiz do ambiente (padrao: MET_PROD_ROOT ou ~/MET/servidor_mt)",
        )
        sub.add_argument("--json", action="store_true", help="saida em JSON")

    environment = subparsers.add_parser("environment", help="confere o ambiente")
    common(environment)

    for name, help_text in (
        ("bluesky", "valida matrizes do BlueSky"),
        ("preditor", "valida matrizes do preditor"),
        ("planilhas", "valida matrizes escalares"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        common(sub)
        sub.add_argument("--dir", help="diretorio extra (por exemplo, saida MAN)")
        sub.add_argument(
            "--limit", type=int, default=5, help="maximo de falhas exibidas"
        )

    acceptance = subparsers.add_parser("acceptance", help="confere o aceite")
    common(acceptance)
    acceptance.add_argument(
        "--require-approved",
        action="store_true",
        help="falha com codigo 2 enquanto o aceite estiver pendente",
    )
    acceptance.add_argument(
        "--limit", type=int, default=5, help="maximo de falhas exibidas"
    )

    register = subparsers.add_parser("register", help="registra uma evidencia")
    common(register)
    register.add_argument("--consumer", required=True, choices=CONSUMERS)
    register.add_argument("--path", required=True, help="arquivo de evidencia")
    register.add_argument("--notes", default="", help="observacao")

    sign = subparsers.add_parser("sign", help="assina o aceite")
    common(sign)
    sign.add_argument("--by", required=True, help="responsavel pelo aceite")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        root = resolve_root(args.root)
        if args.command == "environment":
            report = check_environment(root)
            print_report(report, args.json, 20)
            return 0 if report["status"] == "ok" else 1
        if args.command in ("bluesky", "preditor", "planilhas"):
            kind = {"bluesky": "bluesky", "preditor": "preditor", "planilhas": "planilhas"}[
                args.command
            ]
            report = check_products(
                root, kind, consumer_directories(root, kind, args.dir)
            )
            print_report(report, args.json, args.limit)
            return 0 if report["status"] == "ok" else 1
        if args.command == "acceptance":
            report = check_acceptance(
                root, require_approved=args.require_approved
            )
            print_report(report, args.json, args.limit)
            if report["status"] == "ok":
                return 0
            return 2 if report.get("pending") else 1
        if args.command == "register":
            result = register_evidence(root, args.consumer, args.path, args.notes)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(
                    "evidencia registrada: %s (%s)"
                    % (result["evidence"]["path"], args.consumer)
                )
            return 0
        if args.command == "sign":
            result = sign_acceptance(root, args.by)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(
                    "aceite %s: %s (%s)"
                    % (result["state"], result.get("approved_by"), result.get("accepted_at_utc"))
                )
            return 0
    except CheckError as exc:
        print("erro: %s" % exc, file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
