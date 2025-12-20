import numpy as np

class PenalizacionesBlandasMixin:
    """
    Mixin que contiene los métodos de cálculo para
    las restricciones blandas del problema.

    """

    

    def _calcular_score_equidad(self, horas_trabajadas_por_prof, tolerancia, detallar=False):
        if self.num_profesionales == 0:
            return (0.0, [], 0, 0, 0) if detallar else 0.0

        h_avg = np.mean(horas_trabajadas_por_prof)
        h_min = h_avg - tolerancia
        h_max = h_avg + tolerancia

        if h_avg == 0:
            return (0.0, [1.0]*self.num_profesionales, 0, 0, 0) if detallar else 0.0

        x_points = [h_min, h_avg, h_max]
        y_points = [0.0,   1.0,   0.0]

        scores = np.interp(horas_trabajadas_por_prof, x_points, y_points)
        penalizacion_equidad = 1.0 - np.mean(scores)
        
        if detallar:
            return penalizacion_equidad, scores, h_avg, h_min, h_max
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


    def _calcular_pen_pdl(self, matriz, detallar=False):
        """
        Penaliza si a un profesional se le asigna un turno
        en un día que marcó como "Prefiere Día Libre" (PDL).
        
        """
        
        # Dónde se pidió libre? (Preferencia == -1)
        prefiere_libre = (self.matriz_preferencias == -1)
        # Dónde se asignó trabajo? (Asignación != 0)
        trabaja_asignado = (matriz != 0)
        violaciones_mask = prefiere_libre & trabaja_asignado
        
        if detallar:
            coords = np.argwhere(violaciones_mask) # Devuelve lista de [profesional, dia]
            incidentes = [{"profesional_id": int(p), "dia": int(d)} for p, d in coords]
            return float(len(incidentes)), incidentes
        
        return float(np.sum(violaciones_mask))


    def _calcular_pen_pte(self, matriz, detallar=False):
        """
        Penaliza si un profesional pidió un turno específico (PTE)
        y no se le asignó.
       
        """
        penalizacion = 0.0
        incidentes = []
        alpha = self.pesos_fitness.get('alpha_pte', 0.5) 
        
        for p in range(self.num_profesionales):
            for d in range(self.num_dias):
                pref = self.matriz_preferencias[p, d]
                asign = matriz[p, d]
                if pref > 0:
                    if asign != 0 and asign != pref:
                        penalizacion += 1.0
                        if detallar: incidentes.append({"profesional_id": p, "dia": d, "tipo": "turno_incorrecto", "pedido": int(pref), "asignado": int(asign)})
                    elif asign == 0:
                        penalizacion += alpha
                        if detallar: incidentes.append({"profesional_id": p, "dia": d, "tipo": "no_asignado", "pedido": int(pref)})
                        
        return (penalizacion, incidentes) if detallar else penalizacion