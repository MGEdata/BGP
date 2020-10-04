from sklearn.base import BaseEstimator, TransformerMixin, MultiOutputMixin
from sklearn.metrics import check_scoring

from bgp import flow
from bgp.base import SymbolSet
from bgp.calculation.scores import calculate_y_unpack
from bgp.calculation.translate import general_expr
from bgp.flow import MutilMutateLoop


class SymbolLearning(BaseEstimator, MultiOutputMixin, TransformerMixin):
    """One simplify API for flow.\n
    The detailed functions should turn to the loop of bgp.flow.\n
    The SymbolLearning is time costing and are not suit for GridSearchCV, the cross_validate are builtin """

    def __str__(self):
        return str(self.loop)

    def __init__(self, loop, *args, **kwargs):
        """
        Parameters
        ----------
        pset:SymbolSet
            the feature x and traget y and others should have been added.
        loop: str,None
            bgp.flow.BaseLoop
            [“BaseLoop”,”MutilMutateLoop“,“OnePointMutateLoop”, ”DimForceLoop“...]
        pop:int
            number of popolation
        gen:int
            number of generation
        mutate_prob:float
            probability of mutate
        mate_prob:float
            probability of mate(crossover)
        initial_max:int
            max initial size of expression when first producing.
        initial_min : None,int
            max initial size of expression when first producing.
        max_value:int
            max size of expression
        hall:int,>=1
            number of HallOfFame(elite) to maintain
        re_hall:None or int>=2
            Notes: only vaild when hall
            number of HallOfFame to add to next generation.
        re_Tree: int
            number of new features to add to next generation.
            0 is false to add.
        personal_map:bool or "auto"
            "auto" is using premap and with auto refresh the premap with individual.\n
            True is just using constant premap.\n
            False is just use the prob of terminals.
        scoring: list of Callbale, default is [sklearn.metrics.r2_score,]
            See Also sklearn.metrics
        score_pen: tuple of  1, -1 or float but 0.
            >0 : max problem, best is positive, worse -np.inf
            <0 : min problem, best is negative, worse np.inf
            Notes:
            if multiply score method, the scores must be turn to same dimension in preprocessing
            or weight by score_pen. Because the all the selection are stand on the mean(w_i*score_i)
            Examples: [r2_score] is [1],
        cv:sklearn.model_selection._split._BaseKFold,int
            the shuffler must be False,
            default=1 means no cv
        filter_warning:bool
            filter warning or not
        add_coef:bool
            add coef in expression or not.
        inter_add：bool
            add intercept constant or not
        inner_add:bool
            add inner coeffcients or not
        out_add:bool
            add out coeffcients or not
        flat_add:bool
            add flat coeffcients or not
        n_jobs:int
            default 1, advise 6
        batch_size:int
            default 40, depend of machine
        random_state:int
            None,int
        cal_dim:bool
            excape the dim calculation
        dim_type:Dim or None or list of Dim
            "coef": af(x)+b. a,b have dimension,f(x) is not dnan. \n
            "integer": af(x)+b. f(x) is interger dimension. \n
            [Dim1,Dim2]: f(x) in list. \n
            Dim: f(x) ~= Dim. (see fuzzy) \n
            Dim: f(x) == Dim. \n
            None: f(x) == pset.y_dim
        fuzzy:bool
            choose the dim with same base with dim_type,such as m,m^2,m^3.
        stats:dict
            details of logbook to show. \n
            Map:\n
            values
                = {"max": np.max, "mean": np.mean, "min": np.mean, "std": np.std, "sum": np.sum}
            keys
                = {\n
                   "fitness": just see fitness[0], \n
                   "fitness_dim_max": max problem, see fitness with demand dim,\n
                   "fitness_dim_min": min problem, see fitness with demand dim,\n
                   "dim_is_target": demand dim,\n
                   "coef":  dim is true, coef have dim, \n
                   "integer":  dim is integer, \n
                   ...
                   }
            if stats is None, default is :\n
                stats = {"fitness_dim_max": ("max",), "dim_is_target": ("sum",)}   for cal_dim=True
                stats = {"fitness": ("max",)}                                      for cal_dim=False
            if self-definition, the key is func to get attribute of each ind./n
            Examples:
                def func(ind):\n
                    return ind.fitness[0]
                stats = {func: ("mean",), "dim_is_target": ("sum",)}
        verbose:bool
            print verbose logbook or not
        tq:bool
            print progress bar or not
        store:bool or path
            bool or path
        stop_condition:callable
            stop condition on the best ind of hall, which return bool,the true means stop loop.
            Examples:
                def func(ind):\n
                    c = ind.fitness.values[0]>=0.90
                    return c
        details:bool
            return expr and predi_y or not.
        """
        self.args = args
        self.kwargs = kwargs
        if loop is None:
            loop = MutilMutateLoop
        if isinstance(loop, str):
            loop = getattr(flow, loop)

        self.loop = loop

    def fit(self, X=None, y=None, c=None, x_group=None, x_dim=1, y_dim=1, c_dim=1, x_prob=None,
            c_prob=None, pset=None, power_categories=(2, 3, 0.5), categories=("Add", "Mul", "Sub", "Div"),
            warm_start=False, new_gen=None):
        """

        If need more self-definition, use one defined SymbolSet object to pset.\n
        Examples:
            pset = SymbolSet()\n
            pset.add_features_and_constants(...)\n
            pset.add_operations(...)\n
            ...\n
            ...SymbolLearning().fit(pset=pset)\n

        Parameters
        ----------
        X:np.ndarray

        y:np.ndarray

        c:list of float, None

        x_dim: 1 or list of Dim
            the same size wih x.shape[1], default 1 is dless for all x
        y_dim: 1,Dim
            dim of y
        c_dim: 1,list of Dim
            the same size wih c.shape, default 1 is dless for all c

        x_prob: None,list of float
            the same size wih x.shape[1]
        c_prob: None,list of float
            the same size wih c
        x_group:list of list
            Group of x.\n
            See Also pset.add_features_and_constants
        power_categories: Sized,tuple, None
            Examples:(0.5,2,3)
        categories: tuple of str
            map table:
                    {"Add": sympy.Add, 'Sub': Sub, 'Mul': sympy.Mul, 'Div': Div}

                    {"sin": sympy.sin, 'cos': sympy.cos, 'exp': sympy.exp, 'ln': sympy.ln,

                    {'Abs': sympy.Abs, "Neg": functools.partial(sympy.Mul, -1.0),

                    "Rec": functools.partial(sympy.Pow, e=-1.0)}

                    Others:  \n
                    "Rem":  f(x)=1-x,if x true \n
                    "Self":  f(x)=x,if x true \n

        pset:SymbolSet
            See Also SymbolSet
        warm_start: bool
            warm start or not.
            Note:
                If you offer pset in advance by user, please check carefully the feature numbers,especially when use "re_Tree.
                because the new fatures are add.
            Reference:
                CalculatePrecisionSet.update_with_X_y
        new_gen: None,int
            warm_start generation.

        """
        # try to find pest form args,kwargs
        psets = [i for i in self.args if isinstance(i, SymbolSet)]
        if len(psets) > 0:
            self.args.remove(psets[0])
        if "pset" in self.kwargs:
            psets.append(self.kwargs["pset"])
            del self.kwargs["pset"]

        if pset is None:
            if len(psets) > 0:
                pset = psets[0]

        if pset is None:
            # one simple pset are generate with no dimension calculation, But just with x_group.\n

            if X is not None and y is not None:
                pset = SymbolSet()
                pset.add_features_and_constants(X, y, c, x_dim=x_dim, y_dim=y_dim, c_dim=c_dim, x_prob=x_prob,
                                                c_prob=c_prob, x_group=x_group, feature_name=None)
                pset.add_operations(power_categories=power_categories,
                                    categories=categories)

            elif hasattr(self.loop, "gen"):
                pass
            else:
                raise ValueError("The pset should be defined or the X and Y should be offered.")
        ####################################

        if warm_start:
            assert hasattr(self.loop, "gen"), "Before the warm_start, Need fit at least one time"
            if X is not None and y is not None:
                self.loop.cpset.update_with_X_y(X, y)
            elif pset:
                # the warm_start are not compacting with "re_Tree"
                self.loop.cpset.update(pset)
            else:
                raise ValueError("The pset should be defined or the X and Y should be offered.")

            self.loop.re_fresh_by_name()

            hall = self.loop.run(warm_start=True, new_gen=new_gen)
        else:
            if hasattr(self.loop, "gen"):
                loops = self.loop.__class__
                self.loop = loops(pset, *self.args, **self.kwargs)
            else:
                self.loop = self.loop(pset, *self.args, **self.kwargs)

            hall = self.loop.run()

        self.best_one = hall.items[0]
        try:
            expr = general_expr(self.best_one.coef_expr, self.loop.cpset)
            self.expr_type = "single"
        except (RecursionError, RuntimeWarning):
            expr = self.best_one.coef_expr
            self.expr_type = "group"

        self.expr = expr
        self.y_dim = self.best_one.y_dim
        self.fitness = self.best_one.fitness.values[0]

    def _predict_by_single(self, X):

        terminals = self.loop.cpset.init_free_symbol
        indexs = [int(i.name.replace("x", "")) for i in terminals if "x" in i.name]
        X = [xi for xi in X.T]
        X = [X[indexi] for indexi in indexs]

        c = []
        for i in self.loop.cpset.data_x_dict.keys():
            if "c" in i:
                c.append(self.loop.cpset.data_x_dict[i])
        X_and_c = X + c
        pre_y = calculate_y_unpack(self.expr, X_and_c, terminals)
        return pre_y

    def _predict_by_group(self, X):
        from copy import deepcopy
        cpset_new = deepcopy(self.loop.cpset)
        se = cpset_new.replace(X)

        res = se.calculate_score(self.expr)
        score, expr01, pre_y = res
        return pre_y

    def predict(self, X):
        if self.expr_type == "group":
            return self._predict_by_group(X)
        else:
            return self._predict_by_single(X)

    def score(self, X, y, scoring):

        scoring = check_scoring(self, scoring=scoring)

        if not isinstance(scoring, (list, tuple)):
            scoring = [scoring, ]
        try:
            sc_all = []
            for si in scoring:
                sc = si(self, X, y)
                sc_all.append(sc)

        except (ValueError, RuntimeWarning):

            sc_all = None

        return sc_all

    def cv_result(self, refit=True):
        if self.loop.cpset.cv != 1:
            self.loop.cpset.refit = refit
            return self.loop.cpset.calculate_cv_score(self.best_one.expr)
        else:
            return None


if __name__ == "__main__":
    # data
    from sklearn.datasets import load_boston

    data = load_boston()
    x = data["data"]
    y = data["target"]
    c = [6, 3, 4]

    sl = SymbolLearning(loop=None, pop=50, gen=3, cal_dim=False, re_hall=2, add_coef=True, cv=1, random_state=2,
                        re_Tree=1, details=True,
                        store=r"/data/home/wangchangxin"
                        )
    sl.fit(x, y, c=c, x_group=[[1, 3], [0, 2], [4, 7]])
    sl.fit(x, y, c=c, x_group=[[1, 3], [0, 2], [4, 7]], warm_start=True)
    # score = sl.score(x, y, "r2")
    # print(sl.expr)
