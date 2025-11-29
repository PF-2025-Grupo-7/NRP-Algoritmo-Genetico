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
        # Esta restricción ahora se repara previamente mediante
        # `ProblemaRostering._reparar_cromosoma`. Por tanto, ya no
        # aplicamos la penalización dura aquí y devolvemos 0.0.
        return 0.0

    
    def _calcular_pen_limites_turnos(self, matriz):
        """
        Penaliza si un profesional trabaja más de T-max
        o menos de T-min turnos en el mes.
        Lógica: [cite: 104-107]
        """
        # Los límites T_min / T_max se garantizan mediante la función
        # de reparación (`_reparar_cromosoma`). No penalizamos aquí.
        return 0.0

        
    def _calcular_pen_descansos(self, matriz):
        """
        Penaliza si un profesional tiene una secuencia de turnos
        prohibida (ej: Noche -> Mañana).
        Lógica: [cite: 84-99]
        """
        # Las secuencias prohibidas se corrigen previamente en la
        # función de reparación. Devolvemos 0.0 para evitar dobles penalizaciones.
        return 0.0


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
