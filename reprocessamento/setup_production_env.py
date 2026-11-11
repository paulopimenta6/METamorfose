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
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path.home() / "MET" / "servidor_MET"
DEFAULT_CANDIDATE = ROOT / "reprocessamento" / "releases" / "phase4-candidate"
DEFAULT_SAMPLES = ROOT / "reprocessamento" / "phase4-data"
CONSUMERS = ("BlueSky", "preditor", "planilhas")


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
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)


def install_code(candidate, root):
    reset_directory(root / "app")
    copy_tree(candidate / "code", root / "app")
    checker = ROOT / "reprocessamento" / "acceptance_check.py"
    if not checker.is_file():
        fail(f"verificador ausente: {checker}")
    shutil.copy2(checker, root / "app" / "reprocessamento" / "acceptance_check.py")


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
        source = Path(item["path"])
        if not source.is_file():
            source = samples / f"{date}-{cycle}-f{forecast:03d}.grb2"
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


def install_scripts(root):
    ativar = """#!/bin/bash
# Ativa o ambiente no shell atual.
# Uso: source "$ROOT/bin/ativar.sh"
MET_PROD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export MET_PROD_ROOT
if [ -d "$MET_PROD_ROOT/current/code" ]; then
    MET_ACTIVE_CODE="$(cd "$MET_PROD_ROOT/current/code" && pwd -P)"
else
    MET_ACTIVE_CODE="$MET_PROD_ROOT/app"
fi
export MET_ACTIVE_CODE
export MET_PATH_CONF="$MET_PROD_ROOT/environment/path.conf"
export MET_LOCK_DIR="$MET_PROD_ROOT/run/locks"
export PATH="$MET_ACTIVE_CODE/bash:$MET_PROD_ROOT/bin:$PATH"
echo "Ambiente MET ativado: $MET_PROD_ROOT"
echo "Codigo ativo: $MET_ACTIVE_CODE"
echo "MET_PATH_CONF=$MET_PATH_CONF"
echo "MET_LOCK_DIR=$MET_LOCK_DIR"
"""

    verificar = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKER="$ROOT/app/reprocessamento/acceptance_check.py"
python3 "$CHECKER" environment --root "$ROOT"
python3 "$CHECKER" bluesky --root "$ROOT"
python3 "$CHECKER" preditor --root "$ROOT"
python3 "$CHECKER" planilhas --root "$ROOT"
python3 "$CHECKER" acceptance --root "$ROOT"
"""

    status = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/app/reprocessamento/acceptance_check.py" acceptance --root "$ROOT"
"""

    promover = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACCEPTANCE="$ROOT/acceptance/acceptance.json"
CANDIDATE="$ROOT/evidence/release/candidate"
CHECKER="$ROOT/app/reprocessamento/acceptance_check.py"

python3 "$CHECKER" acceptance --root "$ROOT" --require-approved
mkdir -p "$ROOT/backups"
BACKUP="$ROOT/backups/pre-promocao-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
tar -czf "$BACKUP" -C "$ROOT" environment acceptance app matrizGrib mapasGrib
echo "backup: $BACKUP"
python3 "$ROOT/app/reprocessamento/release_phase4.py" promote "$CANDIDATE" \\
    --target "$ROOT" --acceptance "$ACCEPTANCE"
echo "release promovida; codigo ativo: $ROOT/current/code"
echo "para ativar no shell: source $ROOT/bin/ativar.sh"
"""

    rollback = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/app/reprocessamento/release_phase4.py" rollback --target "$ROOT"
echo "rollback concluido; codigo ativo: $ROOT/current/code"
"""

    assinar = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -lt 1 ]; then
    echo "uso: $0 \\"Nome do responsavel\\"" >&2
    exit 64
fi
python3 "$ROOT/app/reprocessamento/acceptance_check.py" sign \\
    --root "$ROOT" --by "$*"
"""

    registrar = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -lt 2 ]; then
    echo "uso: $0 BlueSky|preditor|planilhas ARQUIVO [NOTA]" >&2
    exit 64
fi
python3 "$ROOT/app/reprocessamento/acceptance_check.py" register \\
    --root "$ROOT" --consumer "$1" --path "$2" --notes "${3:-}"
"""

    testar_bluesky = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKER="$ROOT/app/reprocessamento/acceptance_check.py"
source "$ROOT/bin/ativar.sh" >/dev/null
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/aceitacao-manual/bluesky-$STAMP"
LOG="$ROOT/logs/bluesky-$STAMP.log"
mkdir -p "$OUT" "$(dirname "$LOG")"
{
  echo "teste: BlueSky"
  echo "release: $(sha256sum "$ROOT/evidence/release/candidate/release.json" | cut -d' ' -f1)"
  echo "codigo ativo: $MET_ACTIVE_CODE"
  echo "data UTC: $STAMP"
  echo
  echo "== 1. Produtos da release (abrir estes no BlueSky) =="
  python3 "$CHECKER" bluesky --root "$ROOT"
  echo
  echo "== 2. Geracao manual com GRIB real (f000, 200 hPa) =="
  bash "$MET_ACTIVE_CODE/bash/reqs_MAN_MET.sh" -v wind -nhpa 200 \\
      -lonmin -51.75 -lonmax -41.5 -latmin -28.25 -latmax -17.75 \\
      -datetime 202212150000 -out "$OUT"
  echo
  echo "== 3. Contrato da saida manual =="
  python3 "$CHECKER" bluesky --root "$ROOT" --dir "$OUT"
} 2>&1 | tee "$LOG"
echo "Log local: $LOG"
echo "Amostra da release: $ROOT/matrizGrib/bluesky/20221215/00/"
echo "Depois de executar o BlueSky, registre a evidencia do consumidor:"
echo "  $ROOT/bin/registrar_evidencia.sh BlueSky ARQUIVO \"teste no BlueSky\""
"""

    testar_preditor = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKER="$ROOT/app/reprocessamento/acceptance_check.py"
source "$ROOT/bin/ativar.sh" >/dev/null
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/aceitacao-manual/preditor-$STAMP"
LOG="$ROOT/logs/preditor-$STAMP.log"
mkdir -p "$OUT" "$(dirname "$LOG")"
{
  echo "teste: preditor"
  echo "release: $(sha256sum "$ROOT/evidence/release/candidate/release.json" | cut -d' ' -f1)"
  echo "codigo ativo: $MET_ACTIVE_CODE"
  echo "data UTC: $STAMP"
  echo
  echo "== 1. Produtos da release (abrir estes no preditor) =="
  python3 "$CHECKER" preditor --root "$ROOT"
  echo
  echo "== 2. Geracao manual com GRIB real (f000, 500 hPa) =="
  bash "$MET_ACTIVE_CODE/bash/reqs_MAN_MET.sh" -v wind -nhpa 500 \\
      -lonmin -51.75 -lonmax -41.5 -latmin -28.25 -latmax -17.75 \\
      -datetime 202212150000 -out "$OUT"
  echo
  echo "== 3. Contrato da saida manual =="
  python3 "$CHECKER" preditor --root "$ROOT" --dir "$OUT"
} 2>&1 | tee "$LOG"
echo "Log local: $LOG"
echo "Amostra da release: $ROOT/matrizGrib/predi/20221215/00/"
echo "Depois de executar o preditor, registre a evidencia do consumidor:"
echo "  $ROOT/bin/registrar_evidencia.sh preditor ARQUIVO \"teste no preditor\""
"""

    testar_planilhas = """#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKER="$ROOT/app/reprocessamento/acceptance_check.py"
source "$ROOT/bin/ativar.sh" >/dev/null
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/aceitacao-manual/planilhas-$STAMP"
LOG="$ROOT/logs/planilhas-$STAMP.log"
mkdir -p "$OUT" "$(dirname "$LOG")"
{
  echo "teste: planilhas"
  echo "release: $(sha256sum "$ROOT/evidence/release/candidate/release.json" | cut -d' ' -f1)"
  echo "codigo ativo: $MET_ACTIVE_CODE"
  echo "data UTC: $STAMP"
  echo
  echo "== 1. Produtos da release (abrir estes nas planilhas) =="
  python3 "$CHECKER" planilhas --root "$ROOT"
  echo
  echo "== 2. Geracao manual com GRIB real (f000, 850 hPa) =="
  bash "$MET_ACTIVE_CODE/bash/reqs_MAN_MET.sh" -v temp -nhpa 850 \\
      -lonmin -51.75 -lonmax -41.5 -latmin -28.25 -latmax -17.75 \\
      -datetime 202212150000 -out "$OUT"
  echo
  echo "== 3. Contrato da saida manual =="
  python3 "$CHECKER" planilhas --root "$ROOT" --dir "$OUT"
} 2>&1 | tee "$LOG"
echo "Log local: $LOG"
echo "Amostra da release: $ROOT/matrizGrib/20221215/00/"
echo "Depois de executar as planilhas, registre a evidencia do consumidor:"
echo "  $ROOT/bin/registrar_evidencia.sh planilhas ARQUIVO \"teste nas planilhas\""
"""

    scripts = {
        "ativar.sh": ativar,
        "verificar.sh": verificar,
        "status.sh": status,
        "promover.sh": promover,
        "rollback.sh": rollback,
        "assinar.sh": assinar,
        "registrar_evidencia.sh": registrar,
        "testar_bluesky.sh": testar_bluesky,
        "testar_preditor.sh": testar_preditor,
        "testar_planilhas.sh": testar_planilhas,
    }
    for name, content in scripts.items():
        path = root / "bin" / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)


def install_readme(root, release_hash):
    content = f"""# Ambiente de produção local — servidor_MET

Este ambiente foi montado para os testes de aceitação da Fase 4. Ele **não**
representa uma promoção: a release só é promovida depois do aceite dos três
consumidores (BlueSky, preditor e planilhas).

- Raiz: `{root}`
- Release: `{release_hash}`
- Código em teste: `{root / 'app'}`
- Produtos validados: `{root / 'matrizGrib'}` e `{root / 'mapasGrib'}`
- GRIBs históricos: `{root / 'gribs'}`
- Aceite pendente: `{root / 'acceptance' / 'acceptance.json'}`

## Ativação

```bash
source "{root / 'bin' / 'ativar.sh'}"
```

## Roteiro

```bash
"{root / 'bin' / 'verificar.sh'}"          # ambiente, contratos e aceite
"{root / 'bin' / 'testar_bluesky.sh'}"     # release + MAN 200 hPa, grava log local
"{root / 'bin' / 'testar_preditor.sh'}"    # release + MAN 500 hPa, grava log local
"{root / 'bin' / 'testar_planilhas.sh'}"   # release + MAN 850 hPa, grava log local
"{root / 'bin' / 'status.sh'}"             # mostra o estado do aceite
"{root / 'bin' / 'assinar.sh'}" "Seu Nome" # assina depois das três evidências
"{root / 'bin' / 'promover.sh'}"           # backup + promoção com aceite
```

Cada script `testar_*` valida os produtos da release e gera uma amostra nova a
partir de um GRIB real. Ele grava o log em `logs/`, mas **não** registra a
evidência: o teste nos aplicativos externos (BlueSky, preditor e planilhas)
continua sendo manual. Abra os arquivos indicados no log, execute o consumidor
e registre a evidência com `bin/registrar_evidencia.sh`.

## Roteiro completo

Consulte `docs/14-ambiente-de-producao-e-aceitacao.md` no repositório
`servidor_MET`/`METamorfose`.
"""
    (root / "LEIA-ME.md").write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help=f"diretório do ambiente (padrão: {DEFAULT_ROOT})")
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE,
                        help="release candidata validada")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES,
                        help="diretório das amostras GFS da campanha")
    parser.add_argument("--force", action="store_true",
                        help="reinstala código/produtos; preserva aceite e evidências")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    candidate = args.candidate.expanduser().resolve()
    samples = args.samples.expanduser().resolve()

    if not (candidate / "release.json").is_file():
        fail(f"release candidata inválida: {candidate}")
    if not (candidate / "validation.json").is_file():
        fail(f"relatório de validação ausente: {candidate / 'validation.json'}")

    sys.path.insert(0, str(ROOT / "reprocessamento"))
    import release_phase4

    release_phase4.verify(candidate)
    release_hash = sha256(candidate / "release.json")

    prepare_root(root, args.force)
    install_code(candidate, root)
    write_config(root)
    gribs = install_gribs(samples, root)
    install_products(candidate, root)
    install_release(candidate, root, release_hash)
    install_acceptance(root, release_hash)
    install_scripts(root)
    install_readme(root, release_hash)

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
