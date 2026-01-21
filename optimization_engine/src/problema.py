import numpy as np
import traceback
import json
from .penalizaciones.duras import PenalizacionesDurasMixin
from .penalizaciones.blandas import PenalizacionesBlandasMixin
from .repair import reparar_cromosoma

class ProblemaGAPropio(PenalizacionesDurasMixin, PenalizacionesBlandasMixin):
    """Representa la instancia del problema de planificación de guardias (NRP)."""

    PENALIZACION_DURA = 10_000_000 

    def __init__(self,
                 num_profesionales,
                 num_dias,
                 max_turno_val,
                 info_profesionales,
                 matriz_preferencias,
                 matriz_disponibilidad,
                 requerimientos_cobertura,
                 pesos_fitness,
                 secuencias_prohibidas,
                 turnos_a_cubrir,
                 skills_a_cubrir,
                 duracion_turnos,
                 tolerancia_equidad_general,
                 tolerancia_equidad_dificil,
                 dias_no_habiles,
                 turnos_noche,
                 reglas_cobertura=None, 
                 **kwargs 
                 ):
        
        print("🔧 INICIALIZANDO ProblemaGAPropio (Versión DIAGNÓSTICO)...")

        self.num_profesionales = num_profesionales
        self.num_dias = num_dias
        self.max_turno_val = max_turno_val
        self.info_profesionales = info_profesionales
        
        # --- FIX SKILLS CACHE ---
        self.cache_skills = []
        try:
            if isinstance(info_profesionales, dict):
                for i in range(num_profesionales):
                    p_data = info_profesionales.get(i, {})
                    skill = p_data.get('skill', 'junior') if isinstance(p_data, dict) else 'junior'
                    self.cache_skills.append(skill.strip().lower())
            else:
                for p in info_profesionales:
                    skill = p.get('skill', 'junior') if isinstance(p, dict) else 'junior'
                    self.cache_skills.append(skill.strip().lower())
        except:
            self.cache_skills = ['junior'] * num_profesionales

        self.matriz_preferencias = np.array(matriz_preferencias)
        self.matriz_disponibilidad = np.array(matriz_disponibilidad)
        self.pesos_fitness = pesos_fitness
        self.turnos_a_cubrir = turnos_a_cubrir 
        self.skills_a_cubrir = skills_a_cubrir
        self.tolerancia_equidad_general = tolerancia_equidad_general
        self.tolerancia_equidad_dificil = tolerancia_equidad_dificil
        self.dias_no_habiles = set(dias_no_habiles)
        self.turnos_noche = set(turnos_noche)
        self.reglas_cobertura = reglas_cobertura

        # 1. BLINDAJE DURACIÓN
        self.duracion_turnos = {}
        if isinstance(duracion_turnos, dict):
            for k, v in duracion_turnos.items():
                try:
                    val = float(v)
                    self.duracion_turnos[int(k)] = val
                    self.duracion_turnos[str(int(k))] = val
                except ValueError: continue
        
        # 2. BLINDAJE SECUENCIAS
        self.secuencias_prohibidas = set()
        for seq in secuencias_prohibidas:
            if isinstance(seq, (list, tuple)) and len(seq) == 2:
                self.secuencias_prohibidas.add((int(seq[0]), int(seq[1])))
            elif isinstance(seq, dict): 
                try:
                    self.secuencias_prohibidas.add((int(seq['turno_previo']), int(seq['turno_siguiente'])))
                except: pass

        # 3. PROCESAR REQUERIMIENTOS (CON DEBUG TRAP)
        self.requerimientos_cobertura = []
        for d in range(num_dias):
            try: dia_data_sucio = requerimientos_cobertura[d]
            except (IndexError, KeyError): dia_data_sucio = {}

            dia_data_limpio = {}
            # Normalización agresiva
            if isinstance(dia_data_sucio, dict):
                for t_key, skills_dict in dia_data_sucio.items():
                    try:
                        t_id_int = int(t_key)
                        if isinstance(skills_dict, dict):
                            skills_limpio = {k.lower(): v for k, v in skills_dict.items()}
                            dia_data_limpio[t_id_int] = skills_limpio
                            dia_data_limpio[str(t_id_int)] = skills_limpio
                    except: continue
            
            # RELLENAR HUECOS INMEDIATO
            skills_template = {s.lower(): 0 for s in self.skills_a_cubrir}
            for turno_id in self.turnos_a_cubrir:
                turno_int = int(turno_id)
                if turno_int not in dia_data_limpio:
                    dia_data_limpio[turno_int] = skills_template.copy()
                    dia_data_limpio[str(turno_int)] = skills_template.copy()
            
            self.requerimientos_cobertura.append(dia_data_limpio)

    def _calcular_pen_cobertura(self, matriz, detallar=False):
        penalizacion = 0.0
        faltantes_total = 0

        for d in range(self.num_dias):
            demanda_dia = self.requerimientos_cobertura[d]
            
            for t_id in self.turnos_a_cubrir:
                t_int = int(t_id)
                reqs = demanda_dia.get(t_int)
                if not reqs: reqs = demanda_dia.get(str(t_int), {'junior': 0, 'senior': 0})
                
                req_jun = reqs.get('junior', 0)
                req_sen = reqs.get('senior', 0)

                if req_jun == 0 and req_sen == 0: continue

                cub_jun = 0
                cub_sen = 0
                
                for p in range(self.num_profesionales):
                    if int(matriz[p, d]) == t_int:
                        skill = self.cache_skills[p]
                        if skill == 'senior': cub_sen += 1
                        else: cub_jun += 1
                
                falta = max(0, req_jun - cub_jun) + max(0, req_sen - cub_sen)
                if falta > 0:
                    penalizacion += falta * self.PENALIZACION_DURA
                    faltantes_total += falta

        if detallar: return penalizacion, faltantes_total
        return penalizacion

    def fitness(self, solution_vector):
        try:
            matriz = solution_vector.reshape(self.num_profesionales, self.num_dias)
            matriz_reparada = self._reparar_cromosoma(matriz)
            
            penalizacion = 0.0
            
            try: penalizacion += self._calcular_pen_cobertura(matriz_reparada)
            except Exception as e: raise ValueError(f"Fallo Cobertura: {e}")

            try: penalizacion += self._calcular_pen_disponibilidad(matriz_reparada)
            except: pass 
            try: penalizacion += self._calcular_pen_descansos(matriz_reparada)
            except: pass
            try: penalizacion += self._calcular_pen_limites_turnos(matriz_reparada)
            except: pass
            
            pen_eq = self._calcular_pen_equidad_general(matriz_reparada)
            pen_dif = self._calcular_pen_equidad_dificiles(matriz_reparada)
            pen_pdl = self._calcular_pen_pdl(matriz_reparada)
            pen_pte = self._calcular_pen_pte(matriz_reparada)
            
            total = (penalizacion + 
                     (self.pesos_fitness['eq'] * pen_eq) + 
                     (self.pesos_fitness['dif'] * pen_dif) + 
                     (self.pesos_fitness['pdl'] * pen_pdl) + 
                     (self.pesos_fitness['pte'] * pen_pte))
            
            return float(total)

        except Exception as e:
            print(f"💥 CRASH EN FITNESS: {e}")
            traceback.print_exc()
            raise e 

    def _reparar_cromosoma(self, matriz):
        return reparar_cromosoma(matriz, self)
    
    def evaluar_detallado(self, solution_vector):
        matriz = solution_vector.reshape(self.num_profesionales, self.num_dias)
        matriz_reparada = self._reparar_cromosoma(matriz)
        
        pen_cob, inc_cob = self._calcular_pen_cobertura(matriz_reparada, detallar=True)
        pen_pdl, inc_pdl = self._calcular_pen_pdl(matriz_reparada, detallar=True)
        pen_pte, inc_pte = self._calcular_pen_pte(matriz_reparada, detallar=True)
        
        horas_gen = self._obtener_horas_por_profesional(matriz_reparada, tipo="general")
        _, scores, h_avg, h_min, h_max = self._calcular_score_equidad(
            horas_gen, self.tolerancia_equidad_general, detallar=True
        )
        
        outliers = []
        for p, s in enumerate(scores):
            if s < 1.0:
                outliers.append({
                    "profesional_id": p,
                    "horas": float(horas_gen[p]),
                    "estado": "sobrecarga" if horas_gen[p] > h_avg else "subcarga",
                    "puntos_fuera_del_ideal": round(abs(horas_gen[p] - h_avg), 2)
                })

        return {
            "status": "success",
            "metricas": {
                "fitness_total": self.fitness(solution_vector),
                "cobertura_cumplida": pen_cob == 0
            },
            "violaciones_duras": { "deficit_cobertura": inc_cob },
            "violaciones_blandas": {
                "preferencia_libre_incumplida": inc_pdl,
                "preferencia_turno_incumplida": inc_pte,
                "desbalance_equidad": outliers
            },
            "datos_equidad": {
                "promedio_objetivo": float(h_avg),
                "rango_ideal": [float(h_min), float(h_max)],
                "horas_por_profesional": horas_gen.tolist()
            }
        }

    def _obtener_horas_por_profesional(self, matriz, tipo="general"):
        horas = np.zeros(self.num_profesionales)
        for p in range(self.num_profesionales):
            for d in range(self.num_dias):
                turno = int(matriz[p, d])
                if turno > 0:
                    duracion = self.duracion_turnos.get(turno)
                    if duracion is None:
                         duracion = self.duracion_turnos.get(str(turno), 0)
                    if tipo == "dificil":
                        es_finde_o_feriado = (d in self.dias_no_habiles)
                        es_turno_noche = (turno in self.turnos_noche)
                        if es_finde_o_feriado or es_turno_noche: horas[p] += duracion
                    else: horas[p] += duracion
        return horas