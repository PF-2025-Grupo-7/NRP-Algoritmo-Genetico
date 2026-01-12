import numpy as np

class PenalizacionesDurasMixin:
    """
    Mixin que contiene los métodos de cálculo para
    las restricciones duras del problema.

    """

    def _calcular_pen_disponibilidad(self, matriz):
        """
        Penaliza si a un profesional se le asigna un turno
        en un día que marcó como NO disponible.

        """
        # Esta restricción se repara. Por tanto, ya no
        # aplicamos la penalización dura aquí y devolvemos 0.0.
        return 0.0

    
    def _calcular_pen_limites_turnos(self, matriz):
        """
        Penaliza si un profesional trabaja más de T-max
        o menos de T-min turnos en el mes.

        """
        # Los límites T_min / T_max se garantizan mediante la función
        # de reparación. No penalizamos aquí.
        return 0.0

        
    def _calcular_pen_descansos(self, matriz):
        """
        Penaliza si un profesional tiene una secuencia de turnos
        prohibida (ej: Noche -> Mañana).

        """
        # Las secuencias prohibidas se corrigen en la
        # función de reparación. Devolvemos 0.0.
        return 0.0


    def _calcular_pen_cobertura(self, matriz, detallar=False):
        """
        Penaliza si un turno no tiene la cobertura mínima
        requerida para un nivel de habilidad.

        """
        penalizacion = 0.0
        incidentes = []
        
        # Iteramos por cada día del mes
        for d in range(self.num_dias):
            # Iteramos por cada turno
            for s in self.turnos_a_cubrir:
                # Iteramos por cada habilidad
                for k in self.skills_a_cubrir:
                    
                    # Cuánto se REQUIERE
                    requerido = self.requerimientos_cobertura[d][s][k]
                    # Si no se requiere nadie, continuamos
                    if requerido == 0:
                        continue
                        
                    # Cuánto se ASIGNÓ
                    asignado = 0
                    for p in range(self.num_profesionales):
                        
                        # Verificamos si el profesional 'p' está en este turno 's'
                        esta_en_turno = (matriz[p, d] == s)
                        # Verificamos si tiene la habilidad 'k'
                        tiene_habilidad = (self.info_profesionales[p]['skill'] == k)
                        
                        if esta_en_turno and tiene_habilidad:
                            asignado += 1
                            
                    # Comparamos y penalizamos el déficit
                    if asignado < requerido:
                        faltantes = requerido - asignado
                        # MULTIPLICADOR NUCLEAR: 100.000 puntos por cada turno descubierto
                        penalizacion += (faltantes * 100000.0)
                        if detallar:
                            incidentes.append({
                                "dia": d,
                                "turno": s,
                                "skill": k,
                                "requerido": requerido,
                                "asignado": asignado,
                                "faltantes": faltantes
                        })
                        
        return (penalizacion, incidentes) if detallar else penalizacion
