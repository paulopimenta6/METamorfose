#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul 29 01:59:54 2021

@author: phpimenta
"""
import os
import os.path
import time
import pygrib
from controla_env import controla_dirs_MET

dir_save=controla_dirs_MET()

class leitura_dados_gribs_AUT:

    def __init__(self):

        self.data_horario=time.localtime()
        self.ano=self.data_horario.tm_year
        self.mes=self.data_horario.tm_mon
        self.dia=self.data_horario.tm_mday
        self.hora=self.data_horario.tm_hour
        self.minuto=self.data_horario.tm_min

        self.prev_ana=["00", "06", "12", "18"]
        self.obj_lista_grib=[]
        self.lista_dir=[]
        self.lista_grib=[]

        print("ano: " + str(self.ano))
        print("mes: " + str(self.mes))
        print("dia: " + str(self.dia))
        print("hora: " + str(self.hora))
        print("minuto: " + str(self.minuto))

        if int(self.dia)<10:
            self.dia="0"+str(self.dia)
        if int(self.mes)<10:
            self.mes="0"+str(self.mes)

        self.var_data_dir=str(self.ano)+str(self.mes)+str(self.dia)
        print("data correspondente dos GRIBS do dia: " + self.var_data_dir)

    def limpa_lista_obj_gribs(self):
        self.obj_lista_grib=[]

    def _seleciona_ciclo(self):
        # Ciclos GFS em hora local, com intervalo semiaberto [ciclo, proximo).
        hora_int = int(self.hora)
        if not 0 <= hora_int < 24:
            raise ValueError("hora fora dos ciclos GFS: " + str(self.hora))
        ciclo = max(c for c in (0, 6, 12, 18) if c <= hora_int)
        return "%02d" % ciclo

    def imprime_lista_obj_gribs_AUT(self):
        self.limpa_lista_obj_gribs()
        self.lista_dir = []
        self.lista_grib = []
        ###Entrando no diretorio Grib
        self.dir_grib_completo=dir_save.imprime_dirGrib()
        ###Mostrando diretorio
        print("Diretorio de armazenamento dos GRIBS: " + self.dir_grib_completo)

        caminho_dia = os.path.join(self.dir_grib_completo, self.var_data_dir)
        if not os.path.isdir(caminho_dia):
            print("diretorio dos GRIBS do dia nao encontrado: " + caminho_dia)
            raise FileNotFoundError("diretorio dos GRIBS do dia nao encontrado: " + caminho_dia)

        ciclo = self._seleciona_ciclo()
        caminho_ciclo = os.path.join(caminho_dia, ciclo)
        print("entrou no diretorio dos GRIBS correspondentes do dia: " + caminho_dia)
        print("ciclo GFS selecionado para a hora local " + str(self.hora) + ": " + ciclo)

        if not os.path.isdir(caminho_ciclo):
            raise FileNotFoundError(
                "ciclo GFS selecionado nao existe: " + caminho_ciclo
            )

        try:
            for p in self.prev_ana:
                candidatos = [
                    ("GRIB de 0.25 grau", "gfs.t" + ciclo + "z.pgrb2.0p25.f0" + p),
                    ("GRIB de 0.50 grau", "gfs.t" + ciclo + "z.pgrb2.0p50.f0" + p),
                    ("GRIB de 1.00 grau", "gfs.t" + ciclo + "z.pgrb2.1p00.f0" + p),
                    (
                        "GRIB de 1.00 grau legado",
                        "gfs" + str(self.ano) + str(self.mes) + str(self.dia)
                        + ciclo + "00_000.grb",
                    ),
                ]
                aberto = False
                for descricao, nome in candidatos:
                    caminho = os.path.join(caminho_ciclo, nome)
                    print("# =============================================================================")
                    print(descricao)
                    try:
                        self.obj_lista_grib.append(pygrib.open(caminho))
                        print("# =============================================================================")
                        aberto = True
                        break
                    except OSError:
                        print("arquivo de " + descricao + " nao foi encontrado...")
                if not aberto:
                    raise FileNotFoundError("nenhum arquivo GRIB encontrado para a previsao f0" + p)

        except BaseException:
            for source in self.obj_lista_grib:
                source.close()
            self.obj_lista_grib = []
            raise

        if len(self.obj_lista_grib)>0:
            print(self.obj_lista_grib)
        print(len(self.obj_lista_grib))
        return self.obj_lista_grib

class leitura_dados_gribs_MAN:

    def __init__(self, ano, mes, dia, ana, prev):
        self.ano=ano
        self.mes=mes
        self.dia=dia
        self.ana=ana
        self.prev=prev
        self.obj_grib=None

        print("ano: " + self.ano)
        print("mes: " + self.mes)
        print("dia: " + self.dia)
        print("Analise: " + self.ana)
        print("Previsao: " + self.prev)

        self.var_data_dir=str(self.ano)+str(self.mes)+str(self.dia)
        print("data correspondente dos GRIBS do dia: " + self.var_data_dir)

    def imprime_obj_grib_MAN(self):
        base = os.path.join(dir_save.imprime_dirGrib(), self.var_data_dir, self.ana)
        names = ["gfs.t" + self.ana + "z.pgrb2." + res + ".f0" + self.prev
                 for res in ("0p25", "0p50", "1p00")]
        names.append("gfs" + self.var_data_dir + self.ana + "00_000.grb")
        for name in names:
            try:
                self.obj_grib = pygrib.open(os.path.join(base, name))
                return self.obj_grib
            except OSError:
                continue
        raise FileNotFoundError("GRIB manual nao encontrado em " + base)
