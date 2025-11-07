import numpy as np

class PenalizacionesDurasMixin:
    """
    Mixin que contiene los métodos de cálculo para
    TODAS las restricciones duras del problema.
    """

    def _calcular_pen_disponibilidad(self, matriz):
        """
        Penaliza si a un profesional se le asigna un turno
        en un día que marcó como NO disponible.
        Lógica: [cite: 100-103]
        """
        
        # Comparamos la matriz de disponibilidad (False = No disponible)
        # con la matriz de asignación (Turno != 0 significa que trabaja)
        trabaja_indisponible = (self.matriz_disponibilidad == False) & (matriz != 0)
        
        # Contamos cuántas violaciones ocurrieron
        num_violaciones = np.sum(trabaja_indisponible)
        
        return num_violaciones * self.PENALIZACION_DURA

    
    def _calcular_pen_limites_turnos(self, matriz):
        """
        Penaliza si un profesional trabaja más de T-max
        o menos de T-min turnos en el mes.
        Lógica: [cite: 104-107]
        """
        penalizacion = 0.0
        
        for p in range(self.num_profesionales):
            # Contamos los días que trabaja (cualquier turno > 0) [cite: 107]
            turnos_trabajados = np.count_nonzero(matriz[p, :])
            
            # Obtenemos los límites para este profesional
            # (Asumimos que esta info está en info_profesionales)
            t_min = self.info_profesionales[p]['t_min']
            t_max = self.info_profesionales[p]['t_max']

            if not (t_min <= turnos_trabajados <= t_max):
                penalizacion += self.PENALIZACION_DURA
                
        return penalizacion

        
    def _calcular_pen_descansos(self, matriz):
        """
        Penaliza si un profesional tiene una secuencia de turnos
        prohibida (ej: Noche -> Mañana).
        Lógica: [cite: 84-99]
        """
        penalizacion = 0.0
        
        # Iteramos por cada profesional
        for p in range(self.num_profesionales):
            # Iteramos por cada día, menos el último
            for d in range(self.num_dias - 1):
                turno_actual = matriz[p, d]
                turno_siguiente = matriz[p, d+1]
                
                # Creamos la tupla de secuencia
                secuencia = (turno_actual, turno_siguiente)
                
                # Verificamos si está en el set de secuencias prohibidas
                # (Asumimos que 'self.secuencias_prohibidas' se carga en __init__)
                if secuencia in self.secuencias_prohibidas:
                    penalizacion += self.PENALIZACION_DURA
                    
        return penalizacion


    def _calcular_pen_cobertura(self, matriz):
        """
        Penaliza si un turno no tiene la cobertura mínima
        requerida para un nivel de habilidad.
        Lógica: [cite: 73-83]
        """
        penalizacion = 0.0
        
        # Iteramos por cada día del mes
        for d in range(self.num_dias):
            # Iteramos por cada turno (ej: 1=Mañana, 2=Tarde, 3=Noche)
            # (Asumimos 'self.turnos_a_cubrir' = [1, 2, 3])
            for s in self.turnos_a_cubrir:
                
                # Iteramos por cada habilidad (ej: 'junior', 'senior')
                # (Asumimos 'self.skills_a_cubrir' = ['junior', 'senior'])
                for k in self.skills_a_cubrir:
                    
                    # 1. Cuánto se REQUIERE
                    requerido = self.requerimientos_cobertura[d][s][k]
                    
                    # Si no se requiere nadie, continuamos
                    if requerido == 0:
                        continue
                        
                    # 2. Cuánto se ASIGNÓ
                    asignado = 0
                    for p in range(self.num_profesionales):
                        
                        # Verificamos si el profesional 'p' está en este turno 's'
                        esta_en_turno = (matriz[p, d] == s)
                        
                        # Verificamos si tiene la habilidad 'k'
                        tiene_habilidad = (self.info_profesionales[p]['skill'] == k)
                        
                        if esta_en_turno and tiene_habilidad:
                            asignado += 1
                            
                    # 3. Comparamos y penalizamos el déficit
                    if asignado < requerido:
                        faltantes = requerido - asignado
                        # Penalizamos por CADA profesional que falta
                        penalizacion += (faltantes * self.PENALIZACION_DURA)
                        
        return penalizacion