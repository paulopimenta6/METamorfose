"""Configuração de caminhos independente do diretório corrente."""
import os
from pathlib import Path
import time

class controla_dirs_MET:
    def __init__(self):
        self.data_horario = time.localtime()
        self.ano, self.mes, self.dia, self.hora, self.minuto = self.data_horario[:5]
        self.var_data_dir = "%04d%02d%02d" % (self.ano, self.mes, self.dia)
        config = Path(os.environ.get("MET_PATH_CONF", Path(__file__).resolve().parents[1] / "environment/path.conf"))
        self.dict_dirs = {}
        for line in config.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                path = Path(value.strip()).expanduser()
                if not path.is_absolute():
                    path = config.resolve().parent / path
                self.dict_dirs[key.strip()] = str(path.resolve())
        required = {"dir_gribs", "dir_mapas", "dir_matrizes", "dir_matrizes_predi", "dir_matrizes_bluesky"}
        if not required <= self.dict_dirs.keys():
            raise ValueError("path.conf incompleto: " + str(required - self.dict_dirs.keys()))

    def hora_dirs(self):
        return "%02d" % (self.hora // 6 * 6)

    def imprime_dirGrib(self):
        return self.dict_dirs["dir_gribs"]

    def _output(self, key):
        path = Path(self.dict_dirs[key]) / self.var_data_dir / self.hora_dirs()
        path.mkdir(parents=True, exist_ok=True)
        return str(path) + os.sep

    def imprime_dirMapas(self):
        return self._output("dir_mapas")

    def imprime_dirMatrizes(self):
        return self._output("dir_matrizes")

    def imprime_dirMatrizesPredi(self):
        return self._output("dir_matrizes_predi")

    def imprime_dirMatrizesBluesky(self):
        return self._output("dir_matrizes_bluesky")
