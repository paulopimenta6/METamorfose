#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 22 06:02:44 2021

@author: paulopimenta
"""
from runtime_MET import close_sources
from leitura_dados_grib_MET import leitura_dados_gribs_AUT, leitura_dados_gribs_MAN

# =============================================================================
# Inicio da classe
# =============================================================================
class processamento_dados_met_AUT:

    VARIAVEIS = (
        "ps", "prnm", "temp", "temps", "nuvem", "chuvaNaoConvec", "chuvaConvec",
        "umidadeRel", "u", "v", "uSupe", "vSupe",
    )

    def __init__(self, varMET, nivel=None):

        self.varMET=varMET
        self.nivel=nivel
        self.dict_var_met={"ps": ["Surface pressure", "surface"],
                            "prnm": ["Pressure reduced to MSL", "meanSea"],
                            "temp": ["Temperature", "isobaricInhPa"],
                            "temps": ["Temperature", "surface"],
                            "nuvem": ["Total Cloud Cover", "isobaricInhPa"],
                            "chuvaNaoConvec": ["Total Precipitation", "surface"],
                            "chuvaConvec": ["Convective precipitation (water)", "surface"],
                            "umidadeRel": ["Relative humidity", "isobaricInhPa"],
                            "u": ["U component of wind", "isobaricInhPa"],
                            "v": ["V component of wind", "isobaricInhPa"],
                            "uSupe": ["U component of wind", "heightAboveGround"],
                            "vSupe": ["V component of wind", "heightAboveGround"]}

        if varMET not in self.dict_var_met:
            raise ValueError(self._mensagem_variavel_desconhecida(varMET))

        self.varMET_dict=self.dict_var_met[varMET][0]
        self.tipo_nivel_dict=self.dict_var_met[varMET][1]
        self._valida_nivel(varMET, self.tipo_nivel_dict, self.nivel)

        print(self.varMET_dict, self.tipo_nivel_dict)

        self.obj_GRIBS=leitura_dados_gribs_AUT().imprime_lista_obj_gribs_AUT()

    @classmethod
    def _mensagem_variavel_desconhecida(cls, varMET):
        if varMET == "chuva":
            return "variável 'chuva' não existe; use 'chuvaConvec' ou 'chuvaNaoConvec'"
        return (
            "variável desconhecida: %s; use uma de: %s"
            % (varMET, ", ".join(cls.VARIAVEIS))
        )

    @staticmethod
    def _mensagem_nivel_incompativel(varMET, tipo_nivel_dict, nivel):
        if varMET == "umidadeRel":
            return "umidadeRel não possui campo em superfície; use -n <hPa> (por exemplo, -n 850)"
        if tipo_nivel_dict == "heightAboveGround":
            return "%s usa altura acima do solo; use -n <altura em metros>" % varMET
        if tipo_nivel_dict in ("surface", "meanSea"):
            return "%s é variável de superfície; use -ns" % varMET
        return "%s não possui campo em superfície; use -n <hPa>" % varMET

    @classmethod
    def _valida_nivel(cls, varMET, tipo_nivel_dict, nivel):
        if nivel == "surface" and tipo_nivel_dict not in ("surface", "meanSea"):
            raise ValueError(cls._mensagem_nivel_incompativel(varMET, tipo_nivel_dict, nivel))
        if tipo_nivel_dict in ("surface", "meanSea") and nivel not in (None, "surface"):
            raise ValueError(
                "%s é variável de superfície; use -ns (nível recebido: %s)"
                % (varMET, nivel)
            )

# =============================================================================
# Aqui recebera os objetos de leitura do GRIB
# Uma lista de objetos sera adquirida, serao 4 objetos referente aos arquivos GRIBs...
# ...de 00 06 12 18 horas. Lembrando que as propriedades de um vale para todos, desde que...
# ...sejam da mesma variavel MET
# =============================================================================

# =============================================================================
# Verificacao de nivel
# =============================================================================

    def _seleciona_niveis(self, tipo):
        if self.tipo_nivel_dict != tipo:
            raise ValueError("seletor de nivel incompativel: " + self.varMET)
        try:
            requested = float(self.nivel)
        except (ValueError, TypeError) as exc:
            raise ValueError("nivel numerico obrigatorio") from exc
        if tipo == "isobaricInhPa" and not 150 <= requested <= 1000:
            raise ValueError("nivel fora de 150..1000 hPa")
        result = []
        for source in self.obj_GRIBS:
            messages = source.select(name=self.varMET_dict, typeOfLevel=tipo)
            levels = sorted({m.level for m in messages if tipo != "isobaricInhPa" or 150 <= m.level <= 1000})
            if not levels:
                raise ValueError("nenhum nivel GFS disponivel")
            level = min(levels, key=lambda n: (abs(n - requested), -n))
            if result and result[0].level != level:
                raise ValueError("niveis divergentes entre previsoes")
            result.append(source.select(name=self.varMET_dict, typeOfLevel=tipo, level=level)[0])
        if not result:
            raise ValueError("nenhum GRIB disponivel")
        return result

    @close_sources
    def define_lista_var_com_nivel_pressao(self):
        return self._seleciona_niveis("isobaricInhPa")

    @close_sources
    def define_lista_var_com_altitude(self):
        return self._seleciona_niveis("heightAboveGround")

    @close_sources
    def define_lista_var_com_nivel_superficie(self):
        if self.tipo_nivel_dict not in ("surface", "meanSea"):
            raise ValueError(
                self._mensagem_nivel_incompativel(
                    self.varMET, self.tipo_nivel_dict, "surface"
                )
            )
        #self.lista_var_met=[]
        lista_var_com_nivel=[]

        for self.grb in self.obj_GRIBS:
            if self.tipo_nivel_dict=="surface" or self.tipo_nivel_dict=="meanSea":
                #var_met=self.grb.select(name=self.varMET_dict, typeOfLevel=self.tipo_nivel_dict)
                try:
                    var_met=self.grb.select(name=self.varMET_dict, typeOfLevel=self.tipo_nivel_dict)[0]
                #except ValueError:
                except ValueError:
                    if self.varMET not in ("chuvaConvec", "chuvaNaoConvec"):
                        raise
                    print("Nao ha chuva para Analise: ")
                    print(self.grb)
                else:
                    nivel_escolhido=var_met.level
                    lista_var_com_nivel.append(self.grb.select(name=self.varMET_dict, typeOfLevel=self.tipo_nivel_dict, level=nivel_escolhido)[0])

        return lista_var_com_nivel

    def imprime_nivel(self):
        print("No interior da funcao imprime_nivel")
        print("tamanho do vetor de objetos de Gribs: %d" %(len(self.obj_GRIBS)))
        print(self.define_lista_var_com_nivel_pressao())

class processamento_dados_met_MAN:
    def __init__(self, varMET, ano, mes, dia, ana, prev, nivel):

        self.varMET=varMET
        self.ano=ano
        self.mes=mes
        self.dia=dia
        self.ana=ana
        self.prev=prev
        self.nivel=nivel
        self.dict_var_met={"ps": ["Surface pressure", "surface"],
                            "prnm": ["Pressure reduced to MSL", "meanSea"],
                            "temp": ["Temperature", "isobaricInhPa"],
                            "temps": ["Temperature", "surface"],
                            "nuvem": ["Total Cloud Cover", "isobaricInhPa"],
                            "chuvaNaoConvec": ["Total Precipitation", "surface"],
                            "chuvaConvec": ["Convective precipitation (water)", "surface"],
                            "umidadeRel": ["Relative humidity", "isobaricInhPa"],
                            "u": ["U component of wind", "isobaricInhPa"],
                            "v": ["V component of wind", "isobaricInhPa"],
                            "uSupe": ["U component of wind", "heightAboveGround"],
                            "vSupe": ["V component of wind", "heightAboveGround"]}

        if varMET not in self.dict_var_met:
            raise ValueError(processamento_dados_met_AUT._mensagem_variavel_desconhecida(varMET))

        self.varMET_dict=self.dict_var_met[varMET][0]
        self.tipo_nivel_dict=self.dict_var_met[varMET][1]
        processamento_dados_met_AUT._valida_nivel(varMET, self.tipo_nivel_dict, self.nivel)
        self.obj_GRIB=leitura_dados_gribs_MAN(self.ano, self.mes, self.dia, self.ana, self.prev).imprime_obj_grib_MAN() #passar ano, mes, dia, ana, prev

    @close_sources
    def define_var_com_nivel_ou_superficie(self):
        if type(self.nivel)!=str:
            print("tem mais de um nivel")
            if self.tipo_nivel_dict in ("surface", "meanSea"):
                raise ValueError(
                    "%s é variável de superfície; use -ns" % self.varMET
                )
            self.var_met_com_nivel=self.obj_GRIB.select(name=self.varMET_dict, typeOfLevel=self.tipo_nivel_dict, level=self.nivel)[0]
        else:
            print("tem somente o nivel de superficie")
            if self.tipo_nivel_dict=="surface" or self.tipo_nivel_dict=="meanSea":
                self.var_met_com_nivel_superficie=self.obj_GRIB.select(name=self.varMET_dict, typeOfLevel=self.tipo_nivel_dict)
                print("tipo de nivel: " + self.tipo_nivel_dict)
                nivel_escolhido=self.var_met_com_nivel_superficie[0].level
                self.var_met_com_nivel=self.obj_GRIB.select(name=self.varMET_dict, typeOfLevel=self.tipo_nivel_dict, level=nivel_escolhido)[0]
            else:
                raise ValueError(
                    processamento_dados_met_AUT._mensagem_nivel_incompativel(
                        self.varMET, self.tipo_nivel_dict, self.nivel
                    )
                )

        print("# =============================================================================")
        print("#conseguiu processar o dado")
        print(self.var_met_com_nivel)
        print("# =============================================================================")
        return self.var_met_com_nivel

    @close_sources
    def define_var_com_nivel(self):
        if self.tipo_nivel_dict in ("surface", "meanSea"):
            raise ValueError("%s é variável de superfície; use -ns" % self.varMET)
        if type(self.nivel)!=str:
            print("tem mais de um nivel")
            self.var_met_com_nivel=self.obj_GRIB.select(name=self.varMET_dict, typeOfLevel=self.tipo_nivel_dict, level=self.nivel)[0]

        print(self.var_met_com_nivel)
        return self.var_met_com_nivel

    @close_sources
    def define_var_com_nivel_superficie(self):
        if self.tipo_nivel_dict not in ("surface", "meanSea"):
            raise ValueError(
                processamento_dados_met_AUT._mensagem_nivel_incompativel(
                    self.varMET, self.tipo_nivel_dict, "surface"
                )
            )
        self.var_met_com_nivel_superficie=self.obj_GRIB.select(name=self.varMET_dict, typeOfLevel=self.tipo_nivel_dict)
        print("tipo de nivel: " + self.tipo_nivel_dict)
        nivel_escolhido=self.var_met_com_nivel_superficie[0].level
        self.var_com_nivel=self.obj_GRIB.select(name=self.varMET_dict, typeOfLevel=self.tipo_nivel_dict, level=nivel_escolhido)[0]

        print(self.var_com_nivel)
        return self.var_com_nivel
