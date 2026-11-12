#!/usr/bin/env python3
"""Monta um ambiente de produção local para os testes de aceitação.

O ambiente contém o código da release candidata, os GRIBs históricos da
campanha, os produtos validados e uma configuração independente do repositório.
A promoção oficial continua sendo feita por ``release_phase4.py`` somente
depois do aceite real dos consumidores.

O ambiente criado não é uma promoção: ``production_promoted`` e
``external_consumers_validated`` permanecem falsos até o aceite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path.home() / "MET" / "servidor_MET"
DEFAULT_CANDIDATE = ROOT / "reprocessamento" / "releases" / "phase4-candidate"
DEFAULT_SAMPLES = ROOT / "reprocessamento" / "phase4-data"
CONSUMERS = ("BlueSky", "preditor", "planilhas")


def validate_installation(root: Path, candidate: Path, samples: Path | None) -> str:
    """Confere todas as fontes antes de substituir qualquer arquivo instalado."""
    import release_phase4

    try:
        release_phase4.verify(candidate)
        release_hash = sha256(candidate / "release.json")
        acceptance_path = root / "acceptance" / "acceptance.json"
        if acceptance_path.exists():
            acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
            if acceptance.get("release_sha256") != release_hash:
                fail("o ambiente pertence a outra release; use --root com um novo diretorio")
        if samples is not None:
            for source in (ROOT, candidate, samples):
                if root.is_relative_to(source) or source.is_relative_to(root):
                    fail("destino e fontes da instalacao nao podem se sobrepor")
            for relative in ("code", "code/environment", "products/matrizGrib", "products/mapasGrib"):
                if not (candidate / relative).is_dir():
                    fail(f"diretorio ausente na candidata: {relative}")
            manifest = json.loads((samples / "manifest.json").read_text(encoding="utf-8"))
            if not isinstance(manifest.get("samples"), list) or not manifest["samples"] or manifest.get("errors"):
                fail("manifesto de amostras vazio ou com erros; conclua o download primeiro")
            identities = set()
            for item in manifest["samples"]:
                date, cycle, forecast = item["date"], item["cycle"], item["forecast"]
                if not isinstance(date, str) or not re.fullmatch(r"\d{8}", date):
                    fail("data invalida no manifesto de amostras")
                datetime.strptime(date, "%Y%m%d")
                if cycle not in ("00", "06", "12", "18") or type(forecast) is not int or forecast not in (0, 6, 12, 18):
                    fail("ciclo/previsao invalido no manifesto de amostras")
                identity = (date, cycle, forecast)
                if identity in identities:
                    fail("amostra duplicada no manifesto")
                identities.add(identity)
                source = sample_source(samples, item)
                if sha256(source) != item["sha256"]:
                    fail(f"hash da amostra divergente: {source}")
                with source.open("rb") as stream:
                    if stream.read(4) != b"GRIB":
                        fail(f"amostra nao e GRIB: {source}")
        return release_hash
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        fail(f"fontes invalidas; ambiente preservado: {exc}")


def sample_source(samples: Path, item: dict) -> Path:
    source = Path(item["path"])
    if not source.is_file():
        source = samples / f"{item['date']}-{item['cycle']}-f{item['forecast']:03d}.grb2"
    return source


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message):
    raise SystemExit("erro: " + message)


def copy_tree(source, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def reset_directory(path):
    path = Path(path)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def write_if_missing(path, content, mode=0o644):
    path = Path(path)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    return True


def prepare_root(root, force):
    if root.exists():
        if not root.is_dir():
            fail(f"{root} não é um diretório")
        markers = [root / "app", root / "gribs", root / "matrizGrib"]
        if any(marker.exists() for marker in markers) and not force:
            fail(
                f"ambiente já existe em {root}; use --force para reinstalar "
                "(aceite e evidências são preservados)"
            )

    for relative in (
        "app",
        "gribs",
        "mapasGrib",
        "matrizGrib/predi",
        "matrizGrib/bluesky",
        "environment",
        "acceptance/evidence/BlueSky",
        "acceptance/evidence/preditor",
        "acceptance/evidence/planilhas",
        "evidence/release",
        "evidence/samples",
        "logs",
        "run/locks",
        "backups",
        "aceitacao-manual",
        "bin",
        "tools",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)


def install_code(candidate, root):
    reset_directory(root / "app")
    copy_tree(candidate / "code", root / "app")


def install_tools(root: Path, release_hash: str) -> None:
    """Atualiza somente os utilitários e manuais do ambiente."""
    (root / "tools").mkdir(exist_ok=True)
    for name in ("acceptance_check.py", "release_phase4.py"):
        shutil.copy2(ROOT / "reprocessamento" / name, root / "tools" / name)
    (root / "docs").mkdir(exist_ok=True)
    for document in (ROOT / "docs").glob("*.md"):
        if not document.name.startswith("session-"):
            shutil.copy2(document, root / "docs" / document.name)
    shutil.copy2(ROOT / "README.md", root / "README.md")
    (root / "tests").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "tests" / "README.md", root / "tests" / "README.md")
    install_scripts(root)
    install_readme(root, release_hash)


def write_config(root):
    config = (
        f"dir_gribs={root / 'gribs'}\n"
        f"dir_mapas={root / 'mapasGrib'}\n"
        f"dir_matrizes={root / 'matrizGrib'}\n"
        f"dir_matrizes_predi={root / 'matrizGrib' / 'predi'}\n"
        f"dir_matrizes_bluesky={root / 'matrizGrib' / 'bluesky'}\n"
    )
    for path in (root / "environment" / "path.conf",
                 root / "app" / "environment" / "path.conf"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config, encoding="utf-8")


def install_gribs(samples, root):
    manifest_path = samples / "manifest.json"
    if not manifest_path.is_file():
        fail(f"manifesto de amostras ausente: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples_list = manifest.get("samples", [])
    if not samples_list:
        fail("manifesto de amostras vazio")
    reset_directory(root / "gribs")

    installed = []
    for item in samples_list:
        date = str(item["date"])
        cycle = str(item["cycle"]).zfill(2)
        forecast = int(item["forecast"])
        source = sample_source(samples, item)
        if not source.is_file():
            fail(f"amostra ausente: {source}")

        destination = (
            root / "gribs" / date / cycle
            / f"gfs.t{cycle}z.pgrb2.0p25.f{forecast:03d}"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        installed.append(destination.relative_to(root).as_posix())

        index = source.with_suffix(".idx")
        if index.is_file():
            shutil.copy2(index, destination.parent / (destination.name + ".idx"))
        metadata = source.with_suffix(".json")
        if metadata.is_file():
            shutil.copy2(
                metadata,
                root / "evidence" / "samples"
                / f"{date}-{cycle}-f{forecast:03d}.json",
            )
    shutil.copy2(manifest_path, root / "evidence" / "samples" / "manifest.json")
    return installed


def install_products(candidate, root):
    for family in ("matrizGrib", "mapasGrib"):
        destination = root / family
        reset_directory(destination)
        copy_tree(candidate / "products" / family, destination)


def install_release(candidate, root, release_hash):
    reset_directory(root / "evidence" / "release" / "candidate")
    copy_tree(candidate, root / "evidence" / "release" / "candidate")
    shutil.copy2(candidate / "release.json", root / "evidence" / "release" / "release.json")
    shutil.copy2(candidate / "validation.json", root / "evidence" / "release" / "validation.json")
    (root / "evidence" / "release" / "SHA256SUMS").write_text(
        f"{release_hash}  release.json\n"
        f"{sha256(candidate / 'validation.json')}  validation.json\n",
        encoding="utf-8",
    )


def install_acceptance(root, release_hash):
    acceptance = {
        "release_sha256": release_hash,
        "approved": False,
        "consumers": list(CONSUMERS),
        "evidence": {consumer: None for consumer in CONSUMERS},
        "approved_by": None,
        "accepted_at_utc": None,
        "note": (
            "Preencher somente apos validar esta release nos consumidores reais. "
            "Este arquivo nao constitui aceite."
        ),
    }
    write_if_missing(
        root / "acceptance" / "acceptance.json",
        json.dumps(acceptance, indent=2, ensure_ascii=False) + "\n",
    )


def sample_test_script(consumer: str, kind: str, variable: str, level: int,
                       reference: str, filename: str) -> str:
    return f'''#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"
CHECKER="$ROOT/tools/acceptance_check.py"
source "$ROOT/bin/ativar.sh" >/dev/null
# O aceite testa sempre o codigo da candidata, inclusive apos um rollback.
TEST_CODE="$ROOT/app"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$ROOT/aceitacao-manual" "$ROOT/logs"
OUT="$(mktemp -d "$ROOT/aceitacao-manual/{kind}-$STAMP-XXXXXX")"
LOG="$ROOT/logs/$(basename "$OUT").log"
{{
  echo "teste tecnico: {consumer}"
  echo "release: $(sha256sum "$ROOT/evidence/release/candidate/release.json" | cut -d' ' -f1)"
  echo "codigo em teste: $TEST_CODE"
  echo "data UTC: $STAMP"
  echo "== 1. Integridade do ambiente e produtos da candidata =="
  python3 -B "$CHECKER" environment --root "$ROOT"
  python3 -B "$CHECKER" {kind} --root "$ROOT"
  echo "== 2. Geracao MAN real (15/12/2022, ciclo 00, f000, {level} hPa) =="
  bash "$TEST_CODE/bash/reqs_MAN_MET.sh" -v {variable} -nhpa {level} \\
      -lonmin -51.75 -lonmax -41.5 -latmin -28.25 -latmax -17.75 \\
      -datetime 202212150000 -out "$OUT"
  echo "== 3. Contrato da saida MAN =="
  python3 -B "$CHECKER" {kind} --root "$ROOT" --dir "$OUT"
  echo "CSV gerado para {consumer}:"
  find "$OUT" -maxdepth 1 -type f -name '{filename}' -print
  echo "Saida MAN: $OUT"
  echo "Amostras da release: $ROOT/matrizGrib/{reference}20221215/00/"
  echo "Teste tecnico concluido. Revise os resultados conforme o manual de aceitacao."
}} 2>&1 | tee "$LOG"
echo "Log local: $LOG"
'''


def install_scripts(root):
    ativar = """#!/bin/bash
# Ativa o ambiente no shell atual.
# Uso: source "$ROOT/bin/ativar.sh"
MET_PROD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export MET_PROD_ROOT
if [ -e "$MET_PROD_ROOT/current" ] || [ -L "$MET_PROD_ROOT/current" ]; then
    if [ ! -L "$MET_PROD_ROOT/current" ] || [ ! -d "$MET_PROD_ROOT/current/code" ]; then
        echo "erro: current invalido; execute bin/verificar.sh" >&2
        unset MET_ACTIVE_CODE
        return 1
    fi
    MET_ACTIVE_CODE="$(cd "$MET_PROD_ROOT/current/code" && pwd -P)"
else
    MET_ACTIVE_CODE="$MET_PROD_ROOT/app"
fi
export MET_ACTIVE_CODE
export MET_PATH_CONF="$MET_PROD_ROOT/environment/path.conf"
export MET_LOCK_DIR="$MET_PROD_ROOT/run/locks"
export PYTHONDONTWRITEBYTECODE=1
export MPLBACKEND=Agg
export PATH="$MET_ACTIVE_CODE/bash:$MET_PROD_ROOT/bin:$PATH"
echo "Ambiente MET ativado: $MET_PROD_ROOT"
echo "Codigo ativo: $MET_ACTIVE_CODE"
echo "MET_PATH_CONF=$MET_PATH_CONF"
echo "MET_LOCK_DIR=$MET_LOCK_DIR"
"""

    verificar = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKER="$ROOT/tools/acceptance_check.py"
python3 -B "$CHECKER" environment --root "$ROOT"
python3 -B "$CHECKER" bluesky --root "$ROOT"
python3 -B "$CHECKER" preditor --root "$ROOT"
python3 -B "$CHECKER" planilhas --root "$ROOT"
python3 -B "$CHECKER" acceptance --root "$ROOT"
"""

    status = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B "$ROOT/tools/acceptance_check.py" acceptance --root "$ROOT"
"""

    promover = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACCEPTANCE="$ROOT/acceptance/acceptance.json"
CANDIDATE="$ROOT/evidence/release/candidate"
CHECKER="$ROOT/tools/acceptance_check.py"

python3 -B "$CHECKER" environment --root "$ROOT"
python3 -B "$CHECKER" acceptance --root "$ROOT" --require-approved
mkdir -p "$ROOT/backups"
BACKUP="$ROOT/backups/pre-promocao-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
tar -czf "$BACKUP" -C "$ROOT" environment acceptance app matrizGrib mapasGrib
echo "backup: $BACKUP"
python3 -B "$ROOT/tools/release_phase4.py" promote "$CANDIDATE" \\
    --target "$ROOT" --acceptance "$ACCEPTANCE"
echo "release promovida; codigo ativo: $ROOT/current/code"
echo "para ativar no shell: source $ROOT/bin/ativar.sh"
"""

    rollback = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B "$ROOT/tools/release_phase4.py" rollback --target "$ROOT"
echo "rollback concluido; codigo ativo: $ROOT/current/code"
"""

    assinar = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -lt 1 ]; then
    echo "uso: $0 \\"Nome do responsavel\\"" >&2
    exit 64
fi
python3 -B "$ROOT/tools/acceptance_check.py" sign \\
    --root "$ROOT" --by "$*"
"""

    registrar = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -lt 2 ]; then
    echo "uso: $0 BlueSky|preditor|planilhas ARQUIVO [NOTA]" >&2
    exit 64
fi
python3 -B "$ROOT/tools/acceptance_check.py" register \\
    --root "$ROOT" --consumer "$1" --path "$2" --notes "${3:-}"
"""

    testar_todos = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for family in bluesky preditor planilhas; do
    "$ROOT/bin/testar_${family}.sh"
done
echo "Os tres testes tecnicos passaram. Logs em $ROOT/logs"
"""

    scripts = {
        "ativar.sh": ativar,
        "verificar.sh": verificar,
        "status.sh": status,
        "promover.sh": promover,
        "rollback.sh": rollback,
        "assinar.sh": assinar,
        "registrar_evidencia.sh": registrar,
        "testar_bluesky.sh": sample_test_script(
            "BlueSky", "bluesky", "wind", 200, "bluesky/", "matriz_vento_bluesky_*.csv"),
        "testar_preditor.sh": sample_test_script(
            "preditor", "preditor", "wind", 500, "predi/", "matriz_vento_predi_*.csv"),
        "testar_planilhas.sh": sample_test_script(
            "planilhas", "planilhas", "temp", 850, "", "GFS_*_temp_*.csv"),
        "testar_todos.sh": testar_todos,
    }
    for name, content in scripts.items():
        path = root / "bin" / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)


def install_readme(root, release_hash):
    content = f"""# Ambiente MET — como executar

Este ambiente contém uma candidata para os testes de aceitação da Fase 4.
O aceite registra a conferência real de BlueSky, preditor e planilhas.

- Raiz: `{root}`
- Release: `{release_hash}`
- Código em teste: `{root / 'app'}`
- Produtos validados: `{root / 'matrizGrib'}` e `{root / 'mapasGrib'}`
- GRIBs históricos: `{root / 'gribs'}`
- Estado do aceite: `{root / 'acceptance' / 'acceptance.json'}`

## 1. Ativar

Abra um terminal Bash. Ative primeiro a `.venv` do repositório (ou seu ambiente
Conda com as dependências instaladas). Depois execute:

```bash
source "{root / 'bin' / 'ativar.sh'}"
```

## 2. Conferir a instalação

```bash
"{root / 'bin' / 'verificar.sh'}"
```

Esperado: `falhas: 0`, `status: ok`. `state: pending` é normal antes do aceite.

## 3. Gerar amostras reais

```bash
"{root / 'bin' / 'testar_todos.sh'}"
```

Esperado: `Os tres testes tecnicos passaram`. Os CSVs e PNGs ficam em
`aceitacao-manual/`; os logs em `logs/`. Cada teste usa o código candidato em
`app/` e mostra o caminho exato do CSV da família correspondente.

BlueSky é o código do autor; a rotina MAN de geração é executada pelo teste.
Confira os resultados nos três usos reais conforme o manual abaixo.

## 4. Conferir e aceitar

Siga [o manual de aceitação](docs/16-manual-de-aceitacao.md) para registrar as
evidências, assinar e promover. O log técnico sozinho não registra aceite.

## Manuais locais

- [Execução e solução de problemas](docs/15-manual-testes-de-execucao.md)
- [Aceitação e promoção](docs/16-manual-de-aceitacao.md)
- [Referência e atualização das ferramentas](docs/14-ambiente-de-producao-e-aceitacao.md)

Para consultar o estado atual:

```bash
"{root / 'bin' / 'status.sh'}"
```
"""
    (root / "LEIA-ME.md").write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help=f"diretório do ambiente (padrão: {DEFAULT_ROOT})")
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE,
                        help="release candidata validada")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES,
                        help="diretório das amostras GFS da campanha")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--force", action="store_true",
                      help="reinstala a mesma release; preserva aceite e evidências")
    mode.add_argument("--update-tools", action="store_true",
                      help="atualiza tools/, bin/ e manuais do ambiente existente")
    args = parser.parse_args(argv)

    root = args.root.expanduser().resolve()
    candidate = args.candidate.expanduser().resolve()
    samples = args.samples.expanduser().resolve()

    sys.path.insert(0, str(ROOT / "reprocessamento"))
    if args.update_tools:
        for relative in ("app", "bin", "environment/path.conf", "acceptance/acceptance.json"):
            if not (root / relative).exists():
                fail(f"ambiente incompleto: {relative}; conclua a instalacao primeiro")
        candidate = root / "evidence" / "release" / "candidate"
        release_hash = validate_installation(root, candidate, None)
        install_tools(root, release_hash)
        print(f"Ferramentas e manuais atualizados em {root}")
        print(f"Release preservada: {release_hash}")
        return 0

    release_hash = validate_installation(root, candidate, samples)

    prepare_root(root, args.force)
    install_code(candidate, root)
    write_config(root)
    gribs = install_gribs(samples, root)
    install_products(candidate, root)
    install_release(candidate, root, release_hash)
    install_acceptance(root, release_hash)
    install_tools(root, release_hash)

    report = {
        "root": str(root),
        "release_sha256": release_hash,
        "gribs": len(gribs),
        "csv": len(list((root / "matrizGrib").rglob("*.csv"))),
        "png": len(list((root / "mapasGrib").rglob("*.png"))),
        "acceptance": str(root / "acceptance" / "acceptance.json"),
        "approved": json.loads(
            (root / "acceptance" / "acceptance.json").read_text(encoding="utf-8")
        ).get("approved") is True,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("\nAtive com: source %s/bin/ativar.sh" % root)
    print("Verifique com: %s/bin/verificar.sh" % root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
