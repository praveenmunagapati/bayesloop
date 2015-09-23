#!/usr/bin/env python
"""
This file introduces the transition models that can be used by the Study class for data analysis. A transition model
here referes to a stochastic or deterministic model that describes how the parameter values of a given time series
model change from one time step to another. The transition model can thus be compared to the state transition matrix
of Hidden Markov models. However, instead of explicitely stating transition probabilities for all possible states, a
transformation is defined that alters the distribution of the model parameters in one time step according to the
transition model. This altered distribution is subsequently used as a prior distribution in the next time step.
"""

import numpy as np
from scipy.ndimage.filters import gaussian_filter
from scipy.ndimage.interpolation import shift
from collections import OrderedDict


class Static:
    """
    Static transition model. This trivial model assumes no change of parameter values over time.
    """
    def __init__(self):
        self.latticeConstant = None
        self.hyperParameters = {}

    def __str__(self):
        return 'Static/constant parameter values'

    def computeForwardPrior(self, posterior, t):
        """
        Compute new prior from old posterior (moving forwards in time).

        Parameters:
            posterior - Parameter distribution (numpy array shaped according to grid size) from current time step
            t - integer time step

        Returns:
            Prior parameter distribution for subsequent time step (numpy array shaped according to grid size)
        """
        return posterior.copy()

    def computeBackwardPrior(self, posterior, t):
        return self.computeForwardPrior(posterior, t - 1)


class GaussianRandomWalk:
    """
    Gaussian random walk model. This model assumes that parameter changes are Gaussian-distributed. The standard
    deviation can be set individually for each model parameter.

    Parameters (on initialization):
        sigma - Float or list of floats defining the standard deviation of the Gaussian random walk for each parameter
    """
    def __init__(self, sigma=None):
        self.latticeConstant = None
        self.hyperParameters = OrderedDict([('sigma', sigma)])

    def __str__(self):
        return 'Gaussian random walk'

    def computeForwardPrior(self, posterior, t):
        """
        Compute new prior from old posterior (moving forwards in time).

        Parameters:
            posterior - Parameter distribution (numpy array shaped according to grid size) from current time step
            t - integer time step

        Returns:
            Prior parameter distribution for subsequent time step (numpy array shaped according to grid size)
        """
        newPrior = posterior.copy()

        normedSigma = []
        if type(self.hyperParameters['sigma']) is not list:
            for c in self.latticeConstant:
                normedSigma.append(self.hyperParameters['sigma'] / c)
        else:
            for i, c in enumerate(self.latticeConstant):
                normedSigma.append(self.hyperParameters['sigma'][i] / c)


        newPrior = gaussian_filter(newPrior, normedSigma)

        return newPrior

    def computeBackwardPrior(self, posterior, t):
        return self.computeForwardPrior(posterior, t - 1)


class ChangePoint:
    """
    Change-point model. Parameter values are allowed to change only at a single point in time, right after a specified
    time step (Hyper-parameter tChange). Note that a uniform parameter distribution is used at this time step to
    achieve this "reset" of parameter values.

    Parameters (on initialization):
        tChange - Integer value of the time step of the change point
    """
    def __init__(self, tChange=None):
        self.latticeConstant = None
        self.hyperParameters = OrderedDict([('tChange', tChange)])

    def __str__(self):
        return 'Change-point model'

    def computeForwardPrior(self, posterior, t):
        """
        Compute new prior from old posterior (moving forwards in time).

        Parameters:
            posterior - Parameter distribution (numpy array shaped according to grid size) from current time step
            t - integer time step

        Returns:
            Prior parameter distribution for subsequent time step (numpy array shaped according to grid size)
        """
        if t == self.hyperParameters['tChange']:
            return np.ones_like(posterior) / np.sum(np.ones_like(posterior))  # return flat distribution
        else:
            return posterior.copy()

    def computeBackwardPrior(self, posterior, t):
        return self.computeForwardPrior(posterior, t - 1)


class RegimeSwitch:
    """
    Regime-switching model. In case the number of change-points in a given data set is unknown, the regime-switching
    model may help to identify potential abrupt changes in parameter values. At each time step, all parameter values
    within the set boundaries are assigned a minimal probability of being realized in the next time step, effectively
    allowing abrupt parameter changes at every time step.

    Parameters (on initialization):
        log10pMin - Minimal probability (on a log10 scale) that is assigned to every parameter value
    """
    def __init__(self, log10pMin=None):
        self.latticeConstant = None
        self.hyperParameters = OrderedDict([('log10pMin', log10pMin)])

    def __str__(self):
        return 'Regime-switching model'

    def computeForwardPrior(self, posterior, t):
        """
        Compute new prior from old posterior (moving forwards in time).

        Parameters:
            posterior - Parameter distribution (numpy array shaped according to grid size) from current time step
            t - integer time step

        Returns:
            Prior parameter distribution for subsequent time step (numpy array shaped according to grid size)
        """
        newPrior = posterior.copy()
        newPrior[newPrior < 10**self.hyperParameters['log10pMin']] = 10**self.hyperParameters['log10pMin']

        # transformation above violates proper normalization; re-normalization needed
        newPrior /= np.sum(newPrior)

        return newPrior

    def computeBackwardPrior(self, posterior, t):
        return self.computeForwardPrior(posterior, t - 1)

class Linear:
    """
    Linear deterministic model. This model assumes a constant change of parameter values, resulting in a linear
    parameter evolution. Note that this model is entirely deterministic, as the slope for all parameters has to be
    entered by the user. However, the slope can be optimized by maximizing the model evidence.

    Parameters (on initialization):
        slope - Float or list of floats defining the change in parameter value for each time step for all parameters
    """
    def __init__(self, slope=None):
        self.latticeConstant = None
        self.hyperParameters = OrderedDict([('slope', slope)])

    def __str__(self):
        return 'Linear deterministic model'

    def computeForwardPrior(self, posterior, t):
        """
        Compute new prior from old posterior (moving forwards in time).

        Parameters:
            posterior - Parameter distribution (numpy array shaped according to grid size) from current time step
            t - integer time step

        Returns:
            Prior parameter distribution for subsequent time step (numpy array shaped according to grid size)
        """
        # slope has to be adjusted based on grid size
        normedSlope = []
        if type(self.hyperParameters['slope']) is not list:
            for c in self.latticeConstant:
                normedSlope.append(self.hyperParameters['slope'] / c)
        else:
            for i, c in enumerate(self.latticeConstant):
                normedSlope.append(self.hyperParameters['slope'][i] / c)

        newPrior = posterior.copy()

        # shift interpolated version of distribution according to slope
        shift(newPrior, normedSlope, output=newPrior, order=3, mode='nearest')

        # transformation above may violate proper normalization; re-normalization needed
        newPrior /= np.sum(newPrior)

        return newPrior

    def computeBackwardPrior(self, posterior, t):
        # slope has to be adjusted based on grid size
        normedSlope = []
        if type(self.hyperParameters['slope']) is not list:
            for c in self.latticeConstant:
                normedSlope.append(self.hyperParameters['slope'] / c)
        else:
            for i, c in enumerate(self.latticeConstant):
                normedSlope.append(self.hyperParameters['slope'][i] / c)

        newPrior = posterior.copy()

        # shift interpolated version of distribution according to negative (!) slope
        shift(newPrior, -np.array(normedSlope), output=newPrior, order=3, mode='nearest')

        # transformation above may violate proper normalization; re-normalization needed
        newPrior /= np.sum(newPrior)

        return newPrior


class CombinedTransitionModel:
    """
    Combined transition model. This class allows to combine different transition models to be able to explore more
    complex parameter dynamics. All sub-models are passed to this class as arguments on initialization. Note that a
    different order of the sub-models can result in different parameter dynamics.

    Parameters (on initialization):
        args - Sequence of transition models
    """
    def __init__(self, *args):
        self.latticeConstant = None
        self.models = args

    def __str__(self):
        return 'Combined transition model'

    def computeForwardPrior(self, posterior, t):
        """
        Compute new prior from old posterior (moving forwards in time).

        Parameters:
            posterior - Parameter distribution (numpy array shaped according to grid size) from current time step
            t - integer time step

        Returns:
            Prior parameter distribution for subsequent time step (numpy array shaped according to grid size)
        """
        newPrior = posterior.copy()

        for m in self.models:
            m.latticeConstant = self.latticeConstant  # latticeConstant needs to be propagated to sub-models
            newPrior = m.computeForwardPrior(newPrior, t)

        return newPrior

    def computeBackwardPrior(self, posterior, t):
        newPrior = posterior.copy()

        for m in self.models:
            m.latticeConstant = self.latticeConstant
            newPrior = m.computeBackwardPrior(newPrior, t)

        return newPrior


class SerialTransitionModel:
    """
    Serial transition model. To model fundamental changes in parameter dynamics, different transition models can be
    serially coupled. Depending on the time step, a corresponding sub-model is chosen to compute the new prior
    distribution from the posterior distribution.

    Parameters (on initialization):
        args - Sequence of transition models and integer time steps for structural breaks
               (for n models, n-1 time steps have to be provided)

    Usage example:
        K = bl.transitionModels.SerialTransitionModel(bl.transitionModels.Static(),
                                                      50,
                                                      bl.transitionModels.RegimeSwitch(log10pMin=-7),
                                                      100,
                                                      bl.transitionModels.GaussianRandomWalk(sigma=0.2))

        In this example, parameters are assumed to be constant until time step 50, followed by a regime-switching-
        process until time step 100. Finally, we assume Gaussian parameter fluctuations until the last time step. Note
        that models and time steps do not necessarily have to be passed in an alternating way.
    """
    def __init__(self, *args):
        self.latticeConstant = None

        # determine time steps of structural breaks and corresponding models
        self.breakTimes = [t for t in args if isinstance(t, int)]
        self.models = [m for m in args if not isinstance(m, int)]

        # check: break times have to be passed in monotonically increasing order
        if not all(x < y for x, y in zip(self.breakTimes, self.breakTimes[1:])):
            print '! Time steps for structural breaks ave to be passed in monotonically increasing order.'

        # check: n models require n-1 break times
        if not (len(self.models)-1 == len(self.breakTimes)):
            print '! Wrong number of structural breaks/models. For n models, n-1 structural breaks are required.'

    def __str__(self):
        return 'Serial transition model'

    def computeForwardPrior(self, posterior, t):
        """
        Compute new prior from old posterior (moving forwards in time).

        Parameters:
            posterior - Parameter distribution (numpy array shaped according to grid size) from current time step
            t - integer time step

        Returns:
            Prior parameter distribution for subsequent time step (numpy array shaped according to grid size)
        """
        # the index of the model to choose at time t is given by the number of break times <= t
        modelIndex = np.sum(np.array(self.breakTimes) <= t)

        newPrior = posterior.copy()
        self.models[modelIndex].latticeConstant = self.latticeConstant  # latticeConstant needs to be propagated
        newPrior = self.models[modelIndex].computeForwardPrior(newPrior, t)
        return newPrior

    def computeBackwardPrior(self, posterior, t):
        # the index of the model to choose at time t is given by the number of break times <= t
        modelIndex = np.sum(np.array(self.breakTimes) <= t-1)

        newPrior = posterior.copy()
        self.models[modelIndex].latticeConstant = self.latticeConstant  # latticeConstant needs to be propagated
        newPrior = self.models[modelIndex].computeBackwardPrior(newPrior, t)
        return newPrior