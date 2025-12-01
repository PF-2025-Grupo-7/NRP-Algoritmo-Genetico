import random
import numpy as np

def reparar_cromosoma(matriz, problem):
    matriz_reparada = matriz.copy()

    # Paso de Limpieza
    for p in range(problem.num_profesionales):
        skill = problem.info_profesionales[p]['skill']
        for d in range(problem.num_dias):
            turno = int(matriz_reparada[p, d])
            if turno == 0:
                continue
            if not bool(problem.matriz_disponibilidad[p, d]):
                matriz_reparada[p, d] = 0
                continue
            try:
                requerido = problem.requerimientos_cobertura[d][turno].get(skill, 0)
            except Exception:
                requerido = 0
            if requerido == 0:
                matriz_reparada[p, d] = 0

    # Secuencias prohibidas
    for p in range(problem.num_profesionales):
        for d in range(problem.num_dias - 1):
            sec = (int(matriz_reparada[p, d]), int(matriz_reparada[p, d+1]))
            if sec in problem.secuencias_prohibidas:
                matriz_reparada[p, d+1] = 0

    # Podado sobre-asignacion
    for d in range(problem.num_dias):
        for turno in problem.turnos_a_cubrir:
            for skill in problem.skills_a_cubrir:
                try:
                    requerido = problem.requerimientos_cobertura[d][turno].get(skill, 0)
                except:
                    requerido = 0
                asignados = []
                for p in range(problem.num_profesionales):
                    if int(matriz_reparada[p, d]) == turno and problem.info_profesionales[p]['skill'] == skill:
                        asignados.append(p)
                sobrantes = len(asignados) - requerido
                if sobrantes > 0:
                    random.shuffle(asignados)
                    for _ in range(sobrantes):
                        p_elim = asignados.pop()
                        matriz_reparada[p_elim, d] = 0

    # Contadores
    assigned_counts = {}
    prof_counts = [0] * problem.num_profesionales
    dificiles_counts = [0] * problem.num_profesionales

    for d in range(problem.num_dias):
        assigned_counts[d] = {}
        for turno in problem.turnos_a_cubrir:
            assigned_counts[d][turno] = {}
            for k in problem.skills_a_cubrir:
                assigned = 0
                for p in range(problem.num_profesionales):
                    if int(matriz_reparada[p, d]) == turno and problem.info_profesionales[p]['skill'] == k:
                        assigned += 1
                assigned_counts[d][turno][k] = assigned

    # Iniciar conteos
    for p in range(problem.num_profesionales):
        for d in range(problem.num_dias):
            turno = int(matriz_reparada[p, d])
            if turno > 0:
                prof_counts[p] += 1
                es_finde = d in problem.dias_no_habiles
                es_noche = turno in problem.turnos_noche
                if es_finde or es_noche:
                    dificiles_counts[p] += 1

    # Recortar por t_max
    for p in range(problem.num_profesionales):
        t_max = problem.info_profesionales[p]['t_max']
        skill = problem.info_profesionales[p]['skill']
        if prof_counts[p] <= t_max:
            continue
        trabajados = [d for d in range(problem.num_dias) if int(matriz_reparada[p, d]) != 0]
        random.shuffle(trabajados)
        eliminar = prof_counts[p] - t_max
        for d_elim in trabajados:
            if eliminar <= 0:
                break
            turno_elim = int(matriz_reparada[p, d_elim])
            es_finde = d_elim in problem.dias_no_habiles
            es_noche = turno_elim in problem.turnos_noche
            if es_finde or es_noche:
                dificiles_counts[p] -= 1
            matriz_reparada[p, d_elim] = 0
            try:
                assigned_counts[d_elim][turno_elim][skill] = max(0, assigned_counts[d_elim][turno_elim][skill] - 1)
            except:
                pass
            prof_counts[p] -= 1
            eliminar -= 1

    # Cubrir deficit
    for d in range(problem.num_dias):
        for turno in problem.turnos_a_cubrir:
            es_finde = d in problem.dias_no_habiles
            es_noche = turno in problem.turnos_noche
            turno_es_dificil = es_finde or es_noche
            for skill in problem.skills_a_cubrir:
                try:
                    requerido = problem.requerimientos_cobertura[d][turno].get(skill, 0)
                except:
                    requerido = 0
                asignado = assigned_counts[d][turno].get(skill, 0)
                deficit = requerido - asignado
                while deficit > 0:
                    candidatos = []
                    for p in range(problem.num_profesionales):
                        if problem.info_profesionales[p]['skill'] != skill:
                            continue
                        if int(matriz_reparada[p, d]) != 0:
                            continue
                        if not bool(problem.matriz_disponibilidad[p, d]):
                            continue
                        if prof_counts[p] >= problem.info_profesionales[p]['t_max']:
                            continue
                        prev_turno = int(matriz_reparada[p, d-1]) if d-1 >= 0 else 0
                        next_turno = int(matriz_reparada[p, d+1]) if d+1 < problem.num_dias else 0
                        if (prev_turno, turno) in problem.secuencias_prohibidas:
                            continue
                        if (turno, next_turno) in problem.secuencias_prohibidas:
                            continue
                        candidatos.append(p)
                    if not candidatos:
                        break
                    def puntaje_candidato(p_idx):
                        viola_pdl = 1 if problem.matriz_preferencias[p_idx, d] == -1 else 0
                        pref = problem.matriz_preferencias[p_idx, d]
                        viola_pte = 1 if (pref > 0 and pref != turno) else 0
                        if turno_es_dificil:
                            return (viola_pdl, viola_pte, dificiles_counts[p_idx], prof_counts[p_idx], random.random())
                        else:
                            return (viola_pdl, viola_pte, prof_counts[p_idx], dificiles_counts[p_idx], random.random())
                    candidatos.sort(key=puntaje_candidato)
                    elegido_p = candidatos[0]
                    matriz_reparada[elegido_p, d] = turno
                    prof_counts[elegido_p] += 1
                    if turno_es_dificil:
                        dificiles_counts[elegido_p] += 1
                    assigned_counts[d][turno][skill] = assigned_counts[d][turno].get(skill, 0) + 1
                    deficit -= 1

    # Rellenar hasta t_min
    for p in range(problem.num_profesionales):
        if prof_counts[p] >= problem.info_profesionales[p]['t_min']:
            continue
        dias_libres = [d for d in range(problem.num_dias) if matriz_reparada[p, d] == 0 and bool(problem.matriz_disponibilidad[p, d])]
        random.shuffle(dias_libres)
        skill = problem.info_profesionales[p]['skill']
        for d_cand in dias_libres:
            if prof_counts[p] >= problem.info_profesionales[p]['t_min']:
                break
            posibles = problem.turnos_a_cubrir[:]
            random.shuffle(posibles)
            for turno in posibles:
                prev_turno = int(matriz_reparada[p, d_cand-1]) if d_cand-1 >= 0 else 0
                next_turno = int(matriz_reparada[p, d_cand+1]) if d_cand+1 < problem.num_dias else 0
                if (prev_turno, turno) in problem.secuencias_prohibidas:
                    continue
                if (turno, next_turno) in problem.secuencias_prohibidas:
                    continue
                matriz_reparada[p, d_cand] = turno
                prof_counts[p] += 1
                break

    return matriz_reparada
