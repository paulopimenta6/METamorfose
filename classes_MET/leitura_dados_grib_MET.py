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
            return self.obj_lista_grib

        ciclo = self._seleciona_ciclo()
        caminho_ciclo = os.path.join(caminho_dia, ciclo)
        print("entrou no diretorio dos GRIBS correspondentes do dia: " + caminho_dia)
        print("ciclo GFS selecionado para a hora local " + str(self.hora) + ": " + ciclo)

        if not os.path.isdir(caminho_ciclo):
            raise FileNotFoundError(
                "ciclo GFS selecionado nao existe: " + caminho_ciclo
            )

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
                print("nenhum arquivo GRIB encontrado para a previsao f0" + p)

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
        lista_dir=[]
        lista_grib=[]
        ###Entrando no diretorio Grib
        self.dir_grib_completo=dir_save.imprime_dirGrib()
        os.chdir(self.dir_grib_completo)
        ###Mostrando diretorio
        print("diretorio de armazenamento dos GRIBS: " + self.dir_grib_completo)

        ###Verificando os arquivos e diretorios
        for elementos in os.listdir("."):
            if os.path.isdir(elementos):
                lista_dir.append(elementos)
            else:
                lista_grib.append(elementos)

        print("lista de diretorios: ")
        print(lista_dir)
        print("lista de arquivos no interior do diretorio de diretorios de GRIBS: ") 
        print(lista_grib)


        ###verificando a existencia do diretorio
        if os.path.exists(self.var_data_dir):
            os.chdir(self.var_data_dir)    
            print("entrou no diretorio dos GRIBS correspondentes do dia: " + self.var_data_dir)
            print(os.listdir("."))
            
            if os.path.exists(self.ana):
                os.chdir(self.ana)
                print("entrou no diretorio: " + os.getcwd())
                print("Analise desejada: " + str(self.ana))
                print(os.listdir("."))
                #if os.path.exists("gfs.t" + self.ana + "z.pgrb2.0p25.f0" + self.prev):
                    #print("gfs.t" + self.ana + "z.pgrb2.0p25.f0" + self.prev)                       
                    #self.obj_grib=(pygrib.open("gfs.t" + self.ana + "z.pgrb2.0p25.f0" + self.prev))
                try:
                    print("# =============================================================================")
                    print("GRIB de 0.25 grau")
                    self.obj_grib=(pygrib.open("gfs.t" + self.ana + "z.pgrb2.0p25.f0" + self.prev))
                    print("# =============================================================================")
                except OSError:
                    try:
                        print("# =============================================================================")
                        print("arquivo de GRIB de 0.25 grau nao foi encontrado...")
                        print("GRIB de 0.50 grau")
                        self.obj_grib=(pygrib.open("gfs.t" + self.ana + "z.pgrb2.0p50.f0" + self.prev))
                        print("# =============================================================================")
                    except OSError:
                        try:
                            print("# =============================================================================")
                            print("arquivo de GRIB de 0.50 grau nao foi encontrado...")
                            print("GRIB de 1.00 grau")
                            self.obj_grib=(pygrib.open("gfs.t" + self.ana + "z.pgrb2.1p00.f0" + self.prev))
                            print("# =============================================================================")
                        except OSError:
                            try:
                                print("# =============================================================================")
                                print("arquivo de GRIB de 1.00 grau nao foi encontrado...")
                                print("GRIB de 1.00 grau do Lab MASTER")
                                self.obj_grib=(pygrib.open("gfs" + self.ano + self.mes + self.dia + self.ana + "00_000.grb"))
                                print("# =============================================================================")
                            except OSError:
                                print("# =============================================================================")
                                print("arquivo de GRIB de 1.00 grau do laboratorio MASTER nao foi encontrado")
                                print("# =============================================================================")                  
       
        print("# =============================================================================")
        print("entregando o objeto de GRIB de analise: %s e previsao: %s" %(self.ana,self.prev))
        print(self.obj_grib)
        print("# =============================================================================")
        return self.obj_grib