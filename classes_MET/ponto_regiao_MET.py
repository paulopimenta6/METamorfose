import math

class met_ponto_regiao:
    def __init__(self, longitude, latitude):
        self.longitude, self.latitude = float(longitude), float(latitude)
        if not math.isfinite(self.longitude) or not -180 <= self.longitude <= 180:
            raise ValueError("longitude fora de -180..180")
        if not math.isfinite(self.latitude) or not -90 <= self.latitude <= 90:
            raise ValueError("latitude fora de -90..90")
        self.lonlat = []

    def limpa_longitude_latitude(self):
        self.lonlat = []
        return self.lonlat

    def verifica_longitude(self):
        return max(-180, self.longitude - 5), min(180, self.longitude + 5)

    def verifica_latitude(self):
        center = min(85, max(-85, self.latitude))
        return center - 5, center + 5

    def imprime_longitude_latitude(self):
        self.lonlat = [self.verifica_longitude(), self.verifica_latitude()]
        return self.lonlat
