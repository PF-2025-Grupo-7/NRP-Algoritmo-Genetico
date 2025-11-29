import numpy as np

class PenalizacionesDurasMixin:
    def _calcular_pen_disponibilidad(self, matriz):
        # penaliza asignaciones en días no disponibles
        penal = 0.0
        for p in range(self.num_profesionales):
            for d in range(self.num_dias):
                if matriz[p, d] != 0 and not bool(self.matriz_disponibilidad[p, d]):
                    penal += 1.0
        return penal

    def _calcular_pen_limites_turnos(self, matriz):
        penal = 0.0
        for p in range(self.num_profesionales):
            trabajados = int((matriz[p] > 0).sum())
            if trabajados > self.info_profesionales[p]['t_max']:
                penal += (trabajados - self.info_profesionales[p]['t_max']) * 1.0
            if trabajados < self.info_profesionales[p]['t_min']:
                penal += (self.info_profesionales[p]['t_min'] - trabajados) * 1.0
        return penal

    def _calcular_pen_descansos(self, matriz):
        penal = 0.0
        for p in range(self.num_profesionales):
            for d in range(self.num_dias - 1):
                if (int(matriz[p,d]), int(matriz[p,d+1])) in self.secuencias_prohibidas:
                    penal += 1.0
        return penal

    def _calcular_pen_cobertura(self, matriz):
        penalizacion = 0.0
        for d in range(self.num_dias):
            for s in self.turnos_a_cubrir:
                for k in self.skills_a_cubrir:
                    requerido = self.requerimientos_cobertura[d][s].get(k, 0)
                    if requerido == 0:
                        continue
                    asignado = 0
                    for p in range(self.num_profesionales):
                        if int(matriz[p, d]) == s and self.info_profesionales[p]['skill'] == k:
                            asignado += 1
                    if asignado < requerido:
                        penalizacion += (requerido - asignado) * 10.0
        return penalizacion