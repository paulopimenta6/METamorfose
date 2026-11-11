"""Operações de produto: escrita atômica, exclusão mútua e recursos."""
import contextlib
import functools
import hashlib
import inspect
import logging
import os
from pathlib import Path
import tempfile
import fcntl
import numpy as np

LOG = logging.getLogger("metamorfose")
if not LOG.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.addHandler(handler)
LOG.setLevel(logging.INFO)

@contextlib.contextmanager
def atomic_path(path):
    path = Path(path).expanduser().absolute()
    if not path.parent.is_dir():
        raise FileNotFoundError("diretorio de saida inexistente: " + str(path.parent))
    # O lock permanece no disco: remover seu inode permitiria dois locks distintos.
    lock_dir = Path(os.environ.get("MET_LOCK_DIR", Path(tempfile.gettempdir()) / ("metamorfose-%d" % os.getuid())))
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_name = hashlib.sha256(str(path.resolve()).encode()).hexdigest() + ".lock"
    with open(lock_dir / lock_name, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        fd, name = tempfile.mkstemp(prefix="." + path.stem + ".", suffix=path.suffix, dir=path.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            yield temporary
            with open(temporary, "rb") as stream:
                os.fsync(stream.fileno())
            os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
            os.replace(temporary, path)
            LOG.info("produto=%s bytes=%d", path, path.stat().st_size)
        finally:
            temporary.unlink(missing_ok=True)

@contextlib.contextmanager
def atomic_text(path, mode="w", **kwargs):
    if mode != "w":
        raise ValueError("produtos exigem sobrescrita atomica")
    with atomic_path(path) as temporary:
        with open(temporary, mode, **kwargs) as stream:
            yield stream

def save_figure(*args, **kwargs):
    import matplotlib.pyplot as plt
    with atomic_path(args[0]) as temporary:
        plt.savefig(temporary, *args[1:], **kwargs)

def product_operation(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        import matplotlib.pyplot as plt
        before = set(plt.get_fignums())
        bound = inspect.signature(function).bind(*args, **kwargs).arguments
        for key in ("regiao", "regNome"):
            value = str(bound.get(key, ""))
            if "/" in value or "\\" in value or ".." in value:
                raise ValueError("nome de regiao invalido")
        try:
            with plt.rc_context():
                result = function(*args, **kwargs)
            LOG.info("operacao=%s status=ok", function.__qualname__)
            return result
        except Exception:
            LOG.exception("operacao=%s status=erro", function.__qualname__)
            raise
        finally:
            for number in set(plt.get_fignums()) - before:
                plt.close(number)
    return wrapped

def validate_wind(*groups):
    lists = [g if isinstance(g, (list, tuple)) else [g] for g in groups]
    if not lists[0] or any(len(g) != len(lists[0]) for g in lists):
        raise ValueError("componentes de vento incompletos")
    for messages in zip(*lists):
        first = messages[0]
        lat, lon = first.latlons()
        for index, message in enumerate(messages[1:], 1):
            for key in ("dataDate", "dataTime", "forecastTime", "iDirectionIncrementInDegrees"):
                if getattr(first, key, None) != getattr(message, key, None):
                    raise ValueError("componentes de vento divergentes: " + key)
            if index == 1 and (first.level != message.level or first.typeOfLevel != message.typeOfLevel):
                raise ValueError("niveis U/V divergentes")
            if index > 1 and message.typeOfLevel != "surface" and first.level != message.level:
                raise ValueError("nivel de temperatura divergente")
            other_lat, other_lon = message.latlons()
            if lat.shape != other_lat.shape or not np.array_equal(lat, other_lat) or not np.array_equal(lon, other_lon):
                raise ValueError("grades de vento divergentes")

def close_sources(function):
    @functools.wraps(function)
    def wrapped(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        finally:
            sources = getattr(self, "obj_GRIBS", [getattr(self, "obj_GRIB", None)])
            for source in sources:
                if source is not None:
                    source.close()
    return wrapped
