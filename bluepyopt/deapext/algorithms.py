"""Optimisation class"""

"""
Copyright (c) 2016, EPFL/Blue Brain Project

 This file is part of BluePyOpt <https://github.com/BlueBrain/BluePyOpt>

 This library is free software; you can redistribute it and/or modify it under
 the terms of the GNU Lesser General Public License version 3.0 as published
 by the Free Software Foundation.

 This library is distributed in the hope that it will be useful, but WITHOUT
 ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
 details.

 You should have received a copy of the GNU Lesser General Public License
 along with this library; if not, write to the Free Software Foundation, Inc.,
 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

# pylint: disable=R0914, R0912


import random
import logging
import os
import shutil

import deap.algorithms
import deap.tools
import pickle

from .stoppingCriteria import MaxNGen
from . import utils

logger = logging.getLogger(__name__)


def _evaluate_invalid_fitness(toolbox, population):
    """Evaluate the individuals with an invalid fitness

    Returns the count of individuals with invalid fitness
    """
    invalid_ind = [ind for ind in population if not ind.fitness.valid]
    fitnesses = toolbox.map(toolbox.evaluate, invalid_ind)
    for ind, fit in zip(invalid_ind, fitnesses):
        ind.fitness.values = fit

    return len(invalid_ind)


def _get_offspring(parents, toolbox, cxpb, mutpb):
    """return the offsprint, use toolbox.variate if possible"""
    if hasattr(toolbox, "variate"):
        return toolbox.variate(parents, toolbox, cxpb, mutpb)
    return deap.algorithms.varAnd(parents, toolbox, cxpb, mutpb)


def _check_stopping_criteria(criteria, params):
    for c in criteria:
        c.check(params)
        if c.criteria_met:
            logger.info("Run stopped because of stopping criteria: " + c.name)
            return True
    else:
        return False


def eaAlphaMuPlusLambdaCheckpoint(
    population,
    toolbox,
    mu,
    cxpb,
    mutpb,
    ngen,
    stats=None,
    halloffame=None,
    cp_frequency=1,
    cp_filename=None,
    continue_cp=False,
):
    r"""This is the :math:`(~\alpha,\mu~,~\lambda)` evolutionary algorithm

    Args:
        population(list of deap Individuals)
        toolbox(deap Toolbox)
        mu(int): Total parent population size of EA
        cxpb(float): Crossover probability
        mutpb(float): Mutation probability
        ngen(int): Total number of generation to run
        stats(deap.tools.Statistics): generation of statistics
        halloffame(deap.tools.HallOfFame): hall of fame
        cp_frequency(int): generations between checkpoints
        cp_filename(string): path to checkpoint filename
        continue_cp(bool): whether to continue
    """

    if cp_filename:
        cp_filename_tmp = str(cp_filename) + ".tmp"

    if continue_cp:
        # A file name has been given, then load the data from the file
        cp = pickle.load(open(cp_filename, "rb"))
        population = cp["population"]
        parents = cp["parents"]
        start_gen = cp["generation"]
        halloffame = cp["halloffame"]
        logbook = cp["logbook"]
        history = cp["history"]
        random.setstate(cp["rndstate"])
    else:
        # Start a new evolution
        start_gen = 1
        parents = population[:]
        logbook = deap.tools.Logbook()
        logbook.header = ["gen", "nevals"] + (stats.fields if stats else [])
        history = deap.tools.History()

        # TODO this first loop should be not be repeated !
        invalid_count = _evaluate_invalid_fitness(toolbox, population)
        utils.update_history_and_hof(halloffame, history, population)
        utils.record_stats(
            stats, logbook, start_gen, population, invalid_count
        )

    stopping_criteria = [MaxNGen(ngen)]

    # Begin the generational process
    gen = start_gen + 1
    stopping_params = {"gen": gen}
    while not (_check_stopping_criteria(stopping_criteria, stopping_params)):
        offspring = _get_offspring(parents, toolbox, cxpb, mutpb)

        population = parents + offspring

        invalid_count = _evaluate_invalid_fitness(toolbox, offspring)
        utils.update_history_and_hof(halloffame, history, population)
        utils.record_stats(stats, logbook, gen, population, invalid_count)

        # Select the next generation parents
        parents = toolbox.select(population, mu)

        logger.info(logbook.stream)

        if cp_filename and cp_frequency and gen % cp_frequency == 0:
            cp = dict(
                population=population,
                generation=gen,
                parents=parents,
                halloffame=halloffame,
                history=history,
                logbook=logbook,
                rndstate=random.getstate(),
            )
            pickle.dump(cp, open(cp_filename_tmp, "wb"))
            if os.path.isfile(cp_filename_tmp):
                shutil.copy(cp_filename_tmp, cp_filename)
                logger.debug("Wrote checkpoint to %s", cp_filename)

        gen += 1
        stopping_params["gen"] = gen

    return population, halloffame, logbook, history
