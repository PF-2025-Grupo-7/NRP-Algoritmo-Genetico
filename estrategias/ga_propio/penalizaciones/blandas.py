import numpy as np

class PenalizacionesBlandasMixin:
    def _calcular_score_equidad(self, horas_trabajadas_por_prof, tolerancia):
        if self.num_profesionales == 0:
            return 0.0
        h_avg = np.mean(horas_trabajadas_por_prof)
        h_min = h_avg - tolerancia
        h_max = h_avg + tolerancia
        if h_avg == 0:
            return 0.0
        x_points = [h_min, h_avg, h_max]
        y_points = [0.0, 1.0, 0.0]
        scores = np.interp(horas_trabajadas_por_prof, x_points, y_points)
        penalizacion_equidad = 1.0 - np.mean(scores)
        return penalizacion_equidad

    def _calcular_pen_equidad_general(self, matriz):
        horas_por_profesional = np.zeros(self.num_profesionales)
        for p in range(self.num_profesionales):
            total_horas_p = 0.0
            for d in range(self.num_dias):
                turno = int(matriz[p, d])
                if turno > 0:
                    total_horas_p += self.duracion_turnos.get(turno, 0)
            horas_por_profesional[p] = total_horas_p
        return self._calcular_score_equidad(horas_por_profesional, self.tolerancia_equidad_general)

    def _calcular_pen_equidad_dificiles(self, matriz):
        horas_dificiles_por_prof = np.zeros(self.num_profesionales)
        for p in range(self.num_profesionales):
            total_horas_dificiles = 0.0
            for d in range(self.num_dias):
                turno = int(matriz[p, d])
                if turno > 0:
                    es_finde_o_feriado = (d in self.dias_no_habiles)
                    es_turno_noche = (turno in self.turnos_noche)
                    if es_finde_o_feriado or es_turno_noche:
                        total_horas_dificiles += self.duracion_turnos.get(turno, 0)
            horas_dificiles_por_prof[p] = total_horas_dificiles
        return self._calcular_score_equidad(horas_dificiles_por_prof, self.tolerancia_equidad_dificil)

    def _calcular_pen_pdl(self, matriz):
        prefiere_libre = (self.matriz_preferencias == -1)
        trabaja_asignado = (matriz != 0)
        num_violaciones = np.sum(prefiere_libre & trabaja_asignado)
        return float(num_violaciones)

    def _calcular_pen_pte(self, matriz):
        penalizacion = 0.0
        alpha = self.pesos_fitness.get('alpha_pte', 0.5)
        for p in range(self.num_profesionales):
            for d in range(self.num_dias):
                pref = self.matriz_preferencias[p, d]
                asign = matriz[p, d]
                if pref > 0:
                    if asign != 0 and asign != pref:
                        penalizacion += 1.0
                    elif asign == 0:
                        penalizacion += alpha
        return penalizacion