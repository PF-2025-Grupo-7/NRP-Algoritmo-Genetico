import numpy as np

class PenalizacionesBlandasMixin:
    """
    Mixin que contiene los métodos de cálculo para
    las restricciones blandas del problema.

    """

    def _calcular_score_equidad(self, horas_trabajadas_por_prof, tolerancia):
        """
        Calcula la penalización de equidad basada en la
        función triangular difusa.
        
        Recibe un array de horas (general o difíciles) y 
        devuelve la penalización (0.0 = mejor, 1.0 = peor).

        """
        
        # Si no hay profesionales, no hay penalización
        if self.num_profesionales == 0:
            return 0.0

        # 1. Calcular H_avg, H_min, H_max
        h_avg = np.mean(horas_trabajadas_por_prof)
        h_min = h_avg - tolerancia
        h_max = h_avg + tolerancia

        # Si H_avg es 0, la equidad es perfecta
        if h_avg == 0:
            return 0.0

        # 2. Definir los puntos de la función triangular
        # (x_points = horas, y_points = score)
        x_points = [h_min, h_avg, h_max]
        y_points = [0.0,   1.0,   0.0]

        # 3. Calcular el score(h_p) para cada profesional
        # Los valores fuera de [h_min, h_max] se clipean a 0.0.
        scores = np.interp(horas_trabajadas_por_prof, x_points, y_points)

        # 4. Calcular la penalización final
        # Pen_eq = 1 - (promedio de scores)
        penalizacion_equidad = 1.0 - np.mean(scores)
        
        return penalizacion_equidad


    def _calcular_pen_equidad_general(self, matriz):
        """
        Calcula la penalización de equidad general basada en
        el total de horas trabajadas por cada profesional.

        """
        horas_por_profesional = np.zeros(self.num_profesionales)
        
        for p in range(self.num_profesionales):
            total_horas_p = 0.0
            for d in range(self.num_dias):
                turno = int(matriz[p, d]) 
                if turno > 0:
                    total_horas_p += self.duracion_turnos.get(turno, 0)
            
            horas_por_profesional[p] = total_horas_p
        
        return self._calcular_score_equidad(
            horas_por_profesional, 
            self.tolerancia_equidad_general
        )


    def _calcular_pen_equidad_dificiles(self, matriz):
        """
        Calcula la penalización de equidad de turnos difíciles
        (noches, fines de semana, feriados).
        
        """
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

        return self._calcular_score_equidad(
            horas_dificiles_por_prof, 
            self.tolerancia_equidad_dificil
        )


    def _calcular_pen_pdl(self, matriz):
        """
        Penaliza si a un profesional se le asigna un turno
        en un día que marcó como "Prefiere Día Libre" (PDL).
        
        """
        
        # Dónde se pidió libre? (Preferencia == -1)
        prefiere_libre = (self.matriz_preferencias == -1)
        # Dónde se asignó trabajo? (Asignación != 0)
        trabaja_asignado = (matriz != 0)
        
        # La violación ocurre donde ambas son True
        num_violaciones = np.sum(prefiere_libre & trabaja_asignado)
        
        return float(num_violaciones)


    def _calcular_pen_pte(self, matriz):
        """
        Penaliza si un profesional pidió un turno específico (PTE)
        y no se le asignó.
       
        """
        penalizacion = 0.0
        
        alpha = self.pesos_fitness.get('alpha_pte', 0.5) 
        
        for p in range(self.num_profesionales):
            for d in range(self.num_dias):
                
                pref = self.matriz_preferencias[p, d]
                asign = matriz[p, d]
                
                # Si la preferencia es > 0 (pidió turno s)
                if pref > 0:
                    # Violación Mayor: trabaja, pero en un turno incorrecto
                    if asign != 0 and asign != pref:
                        penalizacion += 1.0
                    # Violación Parcial: se le dio libre en vez del turno
                    elif asign == 0:
                        penalizacion += alpha
                        
        return penalizacion