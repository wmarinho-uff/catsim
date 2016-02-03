"""Module containing functions relevant to the process of simulating the
application of adaptive tests. Most of this module is based on the work of
[Bar10]_.

.. [Bar10] BARRADA, Juan Ramón et al. A method for the comparison of item
   selection rules in computerized adaptive testing. Applied Psychological
   Measurement, v. 34, n. 6, p. 438-452, 2010."""

import math
import numpy as np
from sklearn.metrics import mean_squared_error
from scipy.optimize import differential_evolution, fmin


class Simulator:

    def __init__(self):
        self.existent_methods = ['max_info', 'item_info', 'cluster_info', 'weighted_info']
        self.cluster_dependent_methods = ['item_info', 'cluster_info', 'weighted_info']

    def simulate(items, clusters=None, examinees=1, n_itens=20,
                 r_max=1, method='item_info', optimization='fmin',
                 r_control='passive'):
        """CAT simulation and validation method proposed by [Bar10]_.

        :param items: an n x 3 matrix containing item parameters
        :type items: numpy.ndarray
        :param clusters: a list containing item cluster memberships
        :type clusters: list
        :param n_itens: the number of items an examinee will answer during the
                        adaptive test
        :type n_itens: int
        :param r_max: maximum exposure rate for items
        :type r_max: float
        :param method: one of the available methods for cluster selection. Given
                       the estimated theta value at each step:

                           ``max_info``: ignores cluster selection altogether and
                           selects the item with maximum information to be applied
                           at each step. This is the traditional item selection
                           method used by CATs, prioritizing precision over item
                           exposure;

                           ``item_info``: selects the cluster which has the item
                           with maximum information;

                           ``cluster_info``: selects the cluster whose items sum of
                           information is maximum;

                           ``weighted_info``: selects the cluster whose weighted
                           sum of information is maximum. The weighted equals the
                           number of items in the cluster;

        :type method: string
        :param optimization: the optimization to be used in order to estimate the
                             :math:`\\hat{\\theta}` values. `hill` for a hill-climbing
                             algorithm; `binary` for a binary search algorithm;
                             `fmin` for scipy's function minimization method;
                             `DE` for scipy's differential evolution. With their default
                             parameters, the first method takes roughly 35 function
                             evaluations to converge; the second takes 40 function
                             evaluations; and the last, between 80 and 100 function
                             evaluations. The default method is `fmin`, due to its speed.
        :type optimization: string
        :param r_control: if `passive` and all items :math:`i` in the selected
                          cluster have :math:`r_i > r^{max}`, applies the item with
                          maximum information; if `aggressive`, applies the item
                          with smallest :math:`r` value.
        :type r_control: string
        :return: a list containing two dictionaries. The first contains the global
                 results of the simulation process.
                    *Qtd. Itens*: number of items in the test;

                    *RMSE*: root mean squared error of the estimations;

                    *Overlap*: overlap rate;

                    *r_max*: maximum exposure rate.

                **localResults**: Individual results for each simulated examinee.
                    *Theta*: true theta value of the individual;

                    *Est. theta*: estimated theta value of the individual;

                    *Id. Itens*: a list containing the id. of the items used
                    during the test, in the order they were used;

                    *r*: exposure rate of the items in the bank, after the
                    simulations

        :rtype: list
        """

        if r_max > 1:
            raise ValueError(
                'r_max must be greater than 0 and lesser or equal to 1')
        if items.shape[1] != 3:
            raise ValueError('item matrix has the incorrect number of parameters')
        if n_itens < 1:
            raise ValueError('Number of items must be positive.')
        if items.shape[0] < n_itens:
            raise ValueError('There are not enough items in the item matrix.')
        if method not in self.existent_methods:
            raise ValueError(
                'Invalid method, select one from' + str(self.existent_methods) + '.')
        if method in self.cluster_dependent_methods and clusters is None:
            raise ValueError(
                'Method {0} cannot be used when clusters is None'.format(method))
        if optimization not in ['hill', 'binary', 'fmin', 'DE']:
            raise ValueError('Optimization method not supported')
        if r_control not in ['passive', 'aggressive']:
            raise ValueError('Exposure control method not supported')

        # true thetas extracted from a normal distribution
        true_thetas = np.random.normal(0, 1, examinees)
        min_difficulty = np.min(items[:, 1])
        max_difficulty = np.max(items[:, 1])

        # adds a column for each item's exposure rate and their cluster membership
        items = np.append(items, np.zeros([items.shape[0], 1]), axis=1)

        if clusters is None:
            clusters = np.zeros(items.shape[0])

        items = np.append(
            items, np.array(clusters).reshape(clusters.shape[0], 1), axis=1).astype(np.float64)

        localResults = []
        est_thetas = []

        current_examinee = 0
        total_tries = 0
        for true_theta in true_thetas:
            current_examinee += 1
            est_theta = float('inf')

            while abs(est_theta - true_theta) > .5:
                total_tries += 1
                # estimated theta value
                est_theta = np.random.uniform(-5, 5)

                # keeps indexes of items that were already administered for this
                # examinee
                administered_items = []
                response_vector = []

                for q in range(n_itens):
                    if method == 'max_info':
                        
                        # get the indexes of all items that have not yet been
                        # administered, calculate their information value and pick the
                        # one with maximum information
                        valid_indexes = np.array(
                            list(set(range(items.shape[0])) - set(administered_items)))

                        inf_values = [inf(est_theta, i[0], i[1], i[2])
                                      for i in items[valid_indexes]]

                        valid_indexes = [
                            index for (inf_value, index) in sorted(zip(inf_values, valid_indexes), reverse=True)]

                        selected_item = valid_indexes[0]
                    else:
                        selected_cluster = None
                        # this part of the code selects the cluster from which the item at
                        # the current point of the test will be chosen
                        if method == 'item_info':
                            # finds the item in the matrix which maximizes the
                            # information, given the current estimated theta value
                            max_inf = 0
                            for counter, i in enumerate(items):
                                if inf(est_theta, i[0], i[1], i[2]) > max_inf:
                                    # gets the indexes of all the items in the same cluster
                                    # as the current selected item that have not been
                                    # administered
                                    valid_indexes = np.array(list(set(np.nonzero(
                                        items[:, 4] == i[4])[0]) - set(administered_items)))

                                    # checks if at least one item from this cluster has not
                                    # been adminitered to this examinee yet
                                    if len(valid_indexes) > 0:
                                        selected_cluster = i[4]
                                        max_inf = inf(est_theta, i[0], i[1], i[2])

                        elif method in ['cluster_info', 'weighted_info']:
                            # calculates the cluster information, depending on the method
                            # selected
                            if method == 'cluster_info':
                                cluster_infos = sum_cluster_infos(
                                    est_theta, items, clusters)
                            elif method == 'weighted_info':
                                cluster_infos = weighted_cluster_infos(
                                    est_theta, items, clusters)

                            # sorts clusters descending by their information values
                            # this type of sorting was seem on
                            # http://stackoverflow.com/a/6618543
                            sorted_clusters = np.array(
                                [cluster for (inf_value, cluster) in
                                 sorted(zip(cluster_infos, set(clusters)), reverse=True)], dtype=float)

                            # walks through the sorted clusters in order
                            for i in range(len(sorted_clusters)):
                                valid_indexes = np.nonzero(
                                    items[:, 4] == sorted_clusters[i])[0]

                                # checks if at least one item from this cluster has not
                                # been adminitered to this examinee yet
                                if set(valid_indexes).intersection(administered_items) != set(valid_indexes):
                                    selected_cluster = sorted_clusters[i]
                                    break
                                    # the for loop ends with the cluster that has a) the maximum
                                    # information possible and b) at least one item that has not
                                    # yet been administered

                        assert (selected_cluster is not None)

                        # in this part, an item is chosen from the cluster that was
                        # selected above
                        selected_item = None

                        # gets the indexes and information values from the items in the
                        # selected cluster that have not been administered
                        valid_indexes = np.array(list(set(np.nonzero(
                            items[:, 4] == selected_cluster)[0]) - set(administered_items)))

                        # gets the indexes and information values from the items in the
                        # selected cluster with r < rmax that have not been
                        # administered
                        valid_indexes_low_r = np.array(list(set(np.nonzero(
                            (items[:, 4] == selected_cluster) & (items[:, 3] < r_max))[0]) - set(administered_items)))

                        if len(valid_indexes_low_r) > 0:
                            # sort both items and their indexes by their information
                            # value
                            inf_values = [inf(est_theta, i[0], i[1], i[2])
                                          for i in items[valid_indexes_low_r]]
                            valid_indexes_low_r = [
                                index for (inf_value, index) in sorted(zip(inf_values, valid_indexes_low_r), reverse=True)]

                            selected_item = valid_indexes_low_r[0]

                        # if all items in the selected cluster have exceed their r values,
                        # select the one with smallest r, regardless of information
                        else:
                            if r_control == 'passive':
                                inf_values = [inf(est_theta, i[0], i[1], i[2])
                                              for i in items[valid_indexes]]
                                valid_indexes = [
                                    index for (inf_value, index) in sorted(zip(inf_values, valid_indexes), reverse=True)]
                            elif r_control == 'aggressive':
                                valid_indexes = [
                                    index for (r, index) in sorted(zip(items[valid_indexes,
                                                                             3], valid_indexes))]

                            selected_item = valid_indexes[0]

                    if selected_item is None:
                        print('selected_cluster = ' + str(selected_cluster))
                        print('inf_values = ' + str(inf_values))
                        print('valid_indexes_low_r = ' + str(valid_indexes_low_r))
                        print('valid_indexes = ' + str(valid_indexes))
                        print('administered_items = ' + str(administered_items))

                    assert (selected_item is not None)

                    # simulates the examinee's response via the three-parameter
                    # logistic function
                    response = tpm(
                        true_theta,
                        items[selected_item][0],
                        items[selected_item][1],
                        items[selected_item][2]) >= np.random.uniform()

                    response_vector.append(response)
                    # adds the administered item to the pool of administered items
                    administered_items.append(selected_item)

                    # update the exposure value for this item
                    # items[selected_item, 3] = (
                    #     (items[selected_item, 3] * examinees) + 1) / examinees

                    # reestimation of the examinee's proficiency: if the response
                    # vector contains only success or errors, Dodd's method is used
                    # to reestimate the proficiency
                    if all(response_vector[0] == response for response in response_vector):
                        est_theta = dodd(est_theta, items, response)
                    # else, a maximum likelihood approach is used
                    else:
                        if optimization == 'hill':
                            est_theta = hill_climbing_ml(
                                response_vector, items[administered_items])
                        elif optimization == 'binary':
                            est_theta = binary_search_ml(
                                response_vector, items[administered_items])
                        elif optimization == 'fmin':
                            est_theta = fmin(negativelogLik, est_theta, (response_vector, items[administered_items]))
                        elif optimization == 'DE':
                            est_theta = differential_evolution(
                                negativelogLik, bounds=[
                                    [min_difficulty * 2, max_difficulty * 2]],
                                args=(response_vector, items[administered_items])).x[0]

                            # if abs(est_theta - true_theta) > 1:
                            #     print('....', true_theta, est_theta)

            # items[:, 3] /= examinees

            # print(true_theta, est_theta)

            # update the exposure value for this item
            items[administered_items, 3] = (
                (items[administered_items, 3] * examinees) + 1) / examinees
            est_thetas.append(est_theta)

        # save the results for this examinee simulation
        localResults.append({'Theta': true_theta,
                             'Est. Theta': est_theta,
                             'Id. Itens': administered_items,
                             'r': items[:, 3]})

        # end true_theta loop

        print(examinees, total_tries)

        return {'Nº de grupos': len(set(clusters)),
                'Qtd. Itens': n_itens,
                'RMSE': rmse(true_thetas, est_thetas),
                'Overlap': overlap_rate(items, n_itens),
                'r_max': r_max}, localResults

    def dodd(theta, items, correct):
        """Method proposed by [Dod90]_ for the reestimation of
        :math:`\\hat{\\theta}` when the response vector is composed entirely of 1s
        or 0s

        .. math::

            \\hat{\\theta}_{t+1} = \\left\\lbrace \\begin{array}{ll}
            \\hat{\\theta}_t+\\frac{b_{max}-\\hat{\\theta_t}}{2} & \\text{if } X_t = 1 \\\\
            \\hat{\\theta}_t-\\frac{\\hat{\\theta}_t-b_{min}}{2} & \\text{if }  X_t = 0
            \\end{array} \\right\\rbrace

        :param theta: the initial profficiency level
        :param items: a numpy array containing the parameters of the items in the
                      database. This is necessary to capture the maximum and minimum
                      difficulty levels necessary for the method.
        :param correct: a boolean value informing whether or not the examinee
                        correctly answered the current item.

        .. [Dod90] Dodd, B. G. (1990). The Effect of Item Selection Procedure and
           Stepsize on Computerized Adaptive Attitude Measurement Using the Rating
           Scale Model. Applied Psychological Measurement, 14(4), 355–366.
           http://doi.org/10.1177/014662169001400403
        """
        b = items[:, 1]
        b_max = max(b)
        b_min = min(b)

        dodd = theta + \
            ((b_max - theta) / 2) if correct else theta - ((theta - b_min) / 2)

        return (dodd)

    def rmse(actual, predicted):
        """Root mean squared error:

        .. math:: RMSE = \\sqrt{\\frac{\\sum_{i=1}^{N} (\\hat{\\theta}_i - \\theta_{i})^2}{N}}

        :param actual: a list or 1-D numpy array containing the true profficiency
                       values
        :param predicted: a list or 1-D numpy array containing the estimated
                          profficiency values
        """
        if len(actual) != len(predicted):
            raise ValueError('actuala nd predicted need to be the same size')

        # se = 0
        # for i in range(len(actual)):
        #     se += (predicted[i] - actual[i])**2

        # mse = se / len(actual)

        # rmse = np.sqrt(mse)

        # return rmse
        return mean_squared_error(actual, predicted) ** .5

    def overlap_rate(items, testSize):
        """Test overlap rate:

        .. math:: T=\\frac{N}{Q}S_{r}^2 + \\frac{Q}{N}

        :param items: a numpy array containing, in the 4th column, the number of
                      times each item was used in the tests.
        :param testSize: an integer informing the number of items in a test.
        """

        bankSize = items.shape[0]
        varR = np.var(items[:, 3])

        T = (bankSize / testSize) * varR + (testSize / bankSize)

        return T

    def sum_cluster_infos(theta, items, clusters):
        """Returns the sum of item informations, separated by cluster"""
        cluster_infos = np.zeros((len(set(clusters))))

        for cluster in set(clusters):
            cluster_indexes = np.nonzero(clusters == cluster)[0]

            for item in items[cluster_indexes]:
                cluster_infos[cluster] = cluster_infos[
                    cluster] + inf(theta, item[0], item[1], item[2])

        return cluster_infos

    def weighted_cluster_infos(theta, items, clusters):
        """Returns the weighted sum of item informations, separated by cluster.
           The weight is the number of items in each cluster."""
        cluster_infos = sum_cluster_infos(theta, items, clusters)
        count = np.bincount(clusters)

        for i in range(len(cluster_infos)):
            cluster_infos[i] = cluster_infos[i] / count[i]

        return cluster_infos

    def generateItemBank(items, itemtype='3PL', corr=0.5):
        """Generate a synthetic item bank whose parameters approximately follow
        real-world parameters, as proposed by [Bar10]_.

        Item parameters are extracted from the following probability distributions:

        * discrimination: :math:`N(1.2,0.25)`

        * difficulty: :math:`N(0,1)`

        * pseudo-guessing: :math:`N(0.25,0.02)`

        :param items: how many items are to be generated
        :type items: int
        :param itemtype: either ``1PL``, ``2PL`` or ``3PL`` for the one-, two- or
                         three-parameter logistic model
        :type itemtype: string
        :param corr: the correlation between item discrimination and difficulty. If
                     ``itemtype == '1PL'``, it is ignored.
        :type corr: float
        :return: an ``itens x 3`` numerical matrix containing item parameters
        :rtype: numpy.ndarray
        """

        valid_itemtypes = ['1PL', '2PL', '3PL']

        if itemtype not in valid_itemtypes:
            raise ValueError('Item type not in ' + str(valid_itemtypes))

        means = [0, 1.2]
        stds = [1, 0.25]
        covs = [[stds[0] ** 2, stds[0] * stds[1] * corr],
                [stds[0] * stds[1] * corr, stds[1] ** 2]]

        b, a = np.random.multivariate_normal(means, covs, items).T

        if itemtype not in ['2PL', '3PL']:
            a = np.ones((500))
        if itemtype == '3PL':
            c = np.random.normal(.25, .02, items)
        else:
            c = np.zeros((500))
        return np.array([a, b, c]).T

    def tpm(theta, a, b, c):
        @staticmethod
        """Item Response Theory three-parameter logistic function:

        .. math:: P(X_i = 1| \\theta) = c_i + \\frac{1-c_i}{1+ e^{Da_i(\\theta-b_i)}}

        :param theta: the individual's proficiency value. This parameter value has
                      no boundary, but if a distribution of the form :math:`N(0, 1)` was
                      used to estimate the parameters, then :math:`-4 \\leq \\theta \\leq
                      4`.

        :param a: the discrimination parameter of the item, usually a positive
                  value in which :math:`0.8 \\leq a \\leq 2.5`.

        :param b: the item difficulty parameter. This parameter value has no
                  boundary, but if a distribution of the form :math:`N(0, 1)` was used to
                  estimate the parameters, then :math:`-4 \\leq b \\leq 4`.

        :param c: the item pseudo-guessing parameter. Being a probability,
            :math:`0\\leq c \\leq 1`, but items considered good usually have
            :math:`c \\leq 0.2`.
        """
        try:
            return c + ((1 - c) / (1 + math.exp(-a * (theta - b))))
        except OverflowError:
            print('----ERROR HAPPENED WITH THESE VALUES: ' +
                  format([theta, a, b, c]))
            raise

    def logLik(est_theta, response_vector, administered_items):
        @staticmethod
        """Calculates the log-likelihood of an estimated proficiency, given a
        response vector and the parameters of the answered items.

        .. math:: L(X_{Ij} | \\theta_j, a_I, b_I, c_I) = \\prod_{i=1} ^ I P_{ij}(\\theta)^{X_{ij}} Q_{ij}(\\theta)^{1-X_{ij}}

        For computational reasons, it is common to use the log-likelihood in
        maximization/minimization problems, transforming the product of
        probabilities in a sum of probabilities:

        .. math:: \\log L(X_{Ij} | \\theta_j, , a_I, b_I, c_I) = \\sum_{i=1} ^ I \\left\\lbrace x_{ij} \\log P_{ij}(\\theta)+ (1 - x_{ij}) \\log Q_{ij}(\\theta) \\right\\rbrace

        :param est_theta: estimated profficiency value
        :param response_vector: a binary list containing the response vector
        :param administered_items: a numpy array containing the parameters of the answered items
        """
        # inspired in the example found in
        # http://stats.stackexchange.com/questions/66199/maximum-likelihood-curve-
        # model-fitting-in-python
        # try:
        if len(response_vector) != administered_items.shape[0]:
            raise ValueError(
                'Response vector and administered items must have the number of items')
        LL = 0

        for i in range(len(response_vector)):
            prob = tpm(est_theta, administered_items[i][
                0], administered_items[i][1], administered_items[i][2])

            LL += (response_vector[i] * math.log(prob)) + \
                  ((1 - response_vector[i]) * math.log(1 - prob))
        return LL
        # except OverflowError:
        #     print('Deu pau com esses valores: \n' + str(est_theta) + '\n' +
        #           str([prob, math.log10(prob)]) + '\n' + str(response_vector))
        #     raise

    def negativelogLik(est_theta, *args):
        @staticmethod
        """Function used by :py:mod:`scipy.optimize` functions to find the estimated
        proficiency that maximizes the likelihood of a given response vector

        :param est_theta: estimated profficiency value
        :type est_theta: float
        :param args: a list containing the response vector and the array of
                     administered items, just like :py:func:`logLik`
        :type args: list
        :return: the estimated proficiency that maximizes the likelihood function
        """
        return -logLik(est_theta, args[0], args[1])

    def hill_climbing_ml(response_vector, administered_items, precision=6, verbose=False):
        @staticmethod
        """Uses a hill-climbing algorithm to find and returns the theta value
        that maximizes the likelihood function, given a response vector and a
        matrix with the administered items parameters.

        :param response_vector: a binary list containing the response vector
        :param administered_items: a numpy array containing the parameters of the
                                   answered items
        :param precision: number of decimal points of precision
        :param verbose: verbosity level of the maximization method
        """

        if set(response_vector) == 1:
            return float('inf')
        elif set(response_vector) == 0:
            return float('-inf')

        lbound = min(administered_items[:, 1])
        ubound = max(administered_items[:, 1])
        best_theta = -float('inf')
        max_ll = -float('inf')

        iters = 0

        for i in range(10):
            intervals = np.linspace(lbound, ubound, 10)
            if verbose:
                print('Bounds: ' + str(lbound) + ' ' + str(ubound))
                print('Interval size: ' + str(intervals[1] - intervals[0]))

            for ii in intervals:
                iters += 1
                ll = logLik(ii, response_vector, administered_items)
                if ll > max_ll:
                    max_ll = ll

                    if verbose:
                        print('Iteration: {0}, Theta: {1}, LL: {2}'.format(iters, ii, ll))

                    if abs(best_theta - ii) < float('1e-' + str(precision)):
                        return ii

                    best_theta = ii

                else:
                    lbound = best_theta - (intervals[1] - intervals[0])
                    ubound = ii
                    break

        return best_theta

    def binary_search_ml(response_vector, administered_items, precision=35, verbose=False):
        @staticmethod
        """Uses a binary search algorithm to find and returns the theta value
        that maximizes the likelihood function, given a response vector and a
        matrix with the administered items parameters.

        :param response_vector: a binary list containing the response vector
        :param administered_items: a numpy array containing the parameters of the
                                   answered items
        :param precision: number of decimal points of precision
        :param verbose: verbosity level of the maximization method
        """

        if set(response_vector) == 1:
            return float('inf')
        elif set(response_vector) == 0:
            return float('-inf')

        lbound = min(administered_items[:, 1])
        ubound = max(administered_items[:, 1])
        best_theta = -float('inf')
        iters = 0

        while True:
            iters += 1
            if verbose:
                print('Bounds: ' + str(lbound) + ' ' + str(ubound))
                print('Iteration: {0}, Theta: {1}, LL: {2}'.format(iters, best_theta,
                                                                   logLik(best_theta, response_vector, administered_items)))

            if logLik(ubound, response_vector, administered_items) > logLik(lbound, response_vector, administered_items):

                if abs(best_theta - ubound) < float('1e-' + str(precision)):
                    return ubound

                best_theta = ubound
                lbound += (ubound - lbound) / 2
            else:

                if abs(best_theta - lbound) < float('1e-' + str(precision)):
                    return lbound

                best_theta = lbound
                ubound -= (ubound - lbound) / 2

    def inf(theta, a, b, c):
        @staticmethod
        """Item Response Theory three-parameter information function

        .. math:: I(\\theta) = a^2\\frac{(P(\\theta)-c)^2}{(1-c)^2}.\\frac{(1-P(\\theta))}{P(\\theta)}

        :param theta: the individual's proficiency value. This parameter value has
                      no boundary, but if a distribution of the form
                      :math:`N(0, 1)` was used to estimate the parameters, then
                      :math:`-4 \\leq \\theta \\leq 4`.

        :param a: the discrimination parameter of the item, usually a positive
                  value in which :math:`0.8 \\leq a \\leq 2.5`.

        :param b: the item difficulty parameter. This parameter value has no
                  boundary, but if a distribution of the form :math:`N(0, 1)` was
                  used to estimate the parameters, then :math:`-4 \\leq b \\leq 4`.

        :param c: the item pseudo-guessing parameter. Being a probability,
            :math:`0\\leq c \\leq 1`, but items considered good usually have
            :math:`c \\leq 0.2`.
        """
        ml3 = tpm(theta, a, b, c)
        return math.pow(a, 2) * (math.pow(ml3 - c, 2) /
                                 math.pow(1 - c, 2)) * (1 - ml3) / ml3