import numpy as np
import random

def init_population(pop_size, num_profesionales, num_dias, max_turno_val, seed=None):
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)
    pop = []
    for _ in range(pop_size):
        indiv = np.random.randint(0, max_turno_val + 1, size=(num_profesionales * num_dias,))
        pop.append(indiv.astype(int))
    return pop


def diversity(pop):
    # count unique vectors
    seen = set()
    for ind in pop:
        seen.add(ind.tobytes())
    return len(seen)


def population_stats(fitnesses):
    import numpy as _np
    arr = _np.array(fitnesses)
    return float(arr.min()), float(arr.mean()), float(arr.std())
