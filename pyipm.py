import theano
import theano.tensor as T
import numpy as np
from theano.tensor.nlinalg import pinv
from theano.tensor.nlinalg import diag
from theano.tensor.nlinalg import eigh
from theano.tensor.slinalg import eigvalsh

class IPM:
    """Solve nonlinear, nonconvex minimization problems using an interior point method.


       Detailed Description:
         This solver uses a line search primal-dual interior-point method to solve
         problems of the form

           min f(x)   subject to {ce(x) = 0} and {ci(x) >= 0}
            x

         where f(x) is a continuously differentiable function of the weights x,
         {ce(x) = 0} is the set of M equality constraints, and {ci(x) <= 0} is the
         set of N inequality constraints. The solver finds a solution to an
         'unconstrained' transformation of the problem by forming the Lagrangian
         augmented by a barrier term with coefficient mu when N > 0:

           L(x,s,lda) = f - ce.dot(lda[:M]) - (ci-s).dot(lda[M:]) - mu*sum(log(s))

         where s >= 0 are the slack variables (only used when N > 0) that transform
         the inequality constraints into equality constraints and lda are the
         Lagrange multipliers where lda[M:] >= 0. The optimization completes when
         the first-order Karush-Kuhn-Tucker (KKT) conditions are satisfied to the
         desired precision.

         For more details on this algorithm, see the line search interior-point
         algorithm in chapter 19 of 'Numerical optimization' by Nocedal & Wright
         (2006) and 'Representations of quasi-newton matrices and their use in
         limited memory methods' by Byrd, Nocedal, and Schnabel.


       Dependencies:
           Required:
             numpy
             scipy
             theano
           Optional:
             Intel MKL, OpenBlas, ATLAS, or BLAS/LAPACK
             Nvidia's CUDA or OpenCL
               for more details on support for GPU software, see the theano
               documentation.


       Examples:
           For example usage of this solver class, see the problem definitions in
           the main function at the bottom of this file, pyipm.py. Each of these
           example problems can be run from the command line using argv input. For
           example, if one wants to run example problem 3, enter this command into
           the terminal from the directory that contains pyipm.py

               python pyipm.py 3

           and the solver will print the solution to screen. There are 10 example
           problems that are called by numbers on the range 1 through 10.


       Class Variables:
           x0 (numpy array): weight initialization (size D).
           x_dev (theano matrix): symbolic weight variables.
           f (theano expression): objective function.
               [Args] x_dev
               [Returns] symbolic scalar
           df (theano expression, OPTIONAL): gradient of the objective function
                 with respect to (wrt) x_dev.
               [Args] x_dev
               [Default] df is assigned through automatic symbolic differentiation
                 of f wrt x_dev
               [Returns] symbolic array (size D)
           d2f (theano expression, OPTIONAL): hessian of the objective function wrt
                 x_dev.
               [Args] x_dev
               [Default] d2f is assigned through automatic symbolic differentiation
                 of f wrt x_dev
               [Returns] symbolic array (size DxD) 
           ce (theano expression, OPTIONAL): symbolic expression for the equality
                 constraints as a function of x_dev. This is required if dce or
                 d2ce is not None.
               [Args] x_dev
               [Default] None
               [Returns] symbolic array (size M)
           dce (theano expression, OPTIONAL): symbolic expression for the Jacobian
                 of the equality constraints wrt x_dev.
               [Args] x_dev
               [Default] if ce is not None, then dce is assigned through automatic
                 symbolic differentiation of ce wrt x_dev; otherwise None.
               [Returns] symbolic array (size DxM)
           d2ce (theano expression, OPTIONAL): symbolic expression for the Hessian
                 of the equality constraints wrt x_dev.
               [Args] x_dev, lambda_dev
               [Default] if ce is not None, then d2ce is assigned through automatic
                 symbolic differentiation of ce wrt x_dev; otherwise None.
               [Returns] symbolic array (size DxD)
           ci (theano expression, OPTIONAL): symbolic expression for the
                 inequality constraints as a function of x_dev. Required if dci or
                 d2ci are not None.
               [Args] x_dev
               [Default] None
               [Returns] symbolic array (size N)
           dci (theano expression, OPTIONAL): symbolic expression for the Jacobian 
                 of the inequality constraints wrt x_dev.
               [Args] x_dev
               [Default] if ci is not None, then dci is assigned through automatic
                 symbolic differentiation of ci wrt x_dev; otherwise None
               [Returns] symbolic array (size DxN)
           d2ci (theano expression, OPTIONAL): symbolic expression for the Hessian
                 of the inequality constraints wrt x_dev.
               [Args] x_dev, lambda_dev
               [Default] if ci is not None, then d2ci is assigned through autormatic
                 symbolic differentiation of ci wrt x_dev; otherwise None
               [Returns] symbolic array (size DxD)
           lda0 (numpy array, OPTIONAL): Lagrange multiplier initialization (size
                 M+N). For equality constraints, lda0 may take on any sign while for
                 inequality constraints all elements of lda0 must be >=0.
               [Default] if ce or ci is not None, then lda0 is initialized using (if
                 ce is not None), dci (if ci is not None), and df all evaluated at
                 x0 and the Moore-Penrose pseudoinverse; otherwise None
           lambda_dev (theano expression, OPTIONAL) symbolic Lagrange multipliers.
           s0 (numpy array, OPTIONAL): slack variables initialization (size N).
                 These are only set when inequality constraints are in use.
               [Default] if ci is not None, then s0 is set to the larger of ci
                 evaluated at x0 or Ktol; otherwise None
           mu (float, OPTIONAL): barrier parameter (scalar>0).
               [Default] 0.2
           nu (float, OPTIONAL): merit function barrier parameter (scalar>0).
               [Default] 10.0
           rho (float, OPTIONAL): multiplicative factor for testing progress
                 towards feasibility (scalar in (0,1)).
               [Default] 0.25.
           tau (float, OPTIONAL): fraction to the boundary parameter (scalar in
                 (0,1)).
               [Default] 0.995
           eta (float, OPTIONAL): Armijo rule parameter (Wolfe conditions) (scalar in
                 (0,1)).
               [Default] 1.0E-4
           beta (float, OPTIONAL): power factor used in Hessian regularization to
                 combat ill-conditioning. This is only relevant if ce or ci is not
                 None.
               [Default] 0.4
           miter (int, OPTIONAL): number of 'inner' iterations where mu and nu are
                 held constant.
               [Default] 50
           niter (int, OPTIONAL): number of 'outer' iterations where mu and nu are
                 adjusted.
               [Default] 20
           Xtol (float, OPTIONAL): weight precision tolerance.
               [Default] np.finfo(np.float32).eps (32-bit float machine precision)
           Ktol (float, OPTIONAL): precision tolerance on the first order Karush-
                 Kuhn-Tucker (KKT) conditions.
               [Default] 1.0E-4
           lbfgs (integer, OPTIONAL): solve using the L-BFGS approximation of the
                 Hessian; can also set to False to use the exact Hessian.
               [Default] False
           lbfgs_zeta (float, OPTIONAL): initialize the scaling of the initial Hessian
                 approximation with respect to the weights. The approximation is
                 lbfgs_zeta multiplied by the identity matrix.
               [Default] 1.0
           float_dtype (dtype, OPTIONAL): set the universal precision of all float
                 variables.
               [Default] np.float32 (32-bit floats)
               [NOTE] since this code was written with GPU computing in mind, 32-bit
                 precision is chosen as the default despite the fact that 64-bit
                 precision is usually more reliable for Hessian-based methods. This
                 is because, at present, most GPUs do not support 64-bit precision.
                 If one is planning to use CPUs instead, 64-bit precision is
                 recommended.
           verbosity (integer, OPTIONAL): screen output level from -1 to 3 where -1
                 is no feedback and 3 is maximum feedback.
               [Default] 1


       Class Functions:
           validate_and_compile(nvar=None, neq=None, nineq=None): validate input,
                 form expressions for the Lagrangian and its gradient and Hessian,
                 form expressions for weight and Lagrange multiplier initialization,
                 define device variables, and compile symbolic expressions.
               [Args] nvar (optional), neq (optional), nineq (optional)
                 * nvar (int, scalar) must be set to the number of weights if x0 is
                   uninitialized
                 * neq (int, scalar) must be set to the number of equality constraints
                   if x0 is unintialized, M
                 * nineq (int, scalar) must be set to the number of inequality
                   constraints if x0 is uninitialized, N (scalar)
               [NOTE] If the user runs validate_and_compile on an instance of the
                 solver object and then intends to reuse the solver object after
                 changing the symbolic theano expressions defined in the Class 
                 Variables section, validate_and_compile will need to be rerun to
                 compile any modified/new expressions.
           solve(x0=None, s0=None, lda0=None): run the interior point solver.
               [Args] x0 (optional), s0 (optional), lda0 (optional)
                 * x0 (numpy array, size D) can be used to initialize the weights if
                   they are not already initialized or to reinitialize the weights
                 * s0 (numpy array, size N) gives the user control over initialization
                   of the slack variables, if desired (size N)
                 * lda0 (numpy array, size M+N) gives the user control over
                   initialization of the Lagrange multipliers, if desired
               [Returns] (x, s, lda, fval, kkt)
                 * x (numpy array, size D) are the weights at the solution
                 * s (numpy array, size N) are the slack variables at the solution
                 * lda (numpy array, size M+N) are the Lagrange multipliers at the
                   solution
                 * fval (float, scalar) is f evaluated at x
                 * kkt (list) is a list of the first-order KKT conditions solved at x
                   (see class function KKT for details)
               [NOTE] If the solver is used more than once, it will likely be
                 necessary to reinitialize mu and nu since they are left in their
                 final state after the solver is used.
           KKT(x, s, lda): calculate the first-order KKT conditions.
               [Args] x, s, lda
                 * x (numpy array, size D) are the weights
                 * s (numpy array, size N) are the slack variables
                 * lda (numpy array, size M+N) are the Lagrange multipliers
               [Returns] [kkt1, kkt2, kkt3, kkt4]
                 * kkt1 (numpy array, size D) is the gradient of the Lagrangian barrier
                   problem at x, s, and lda
                 * kkt2 (numpy array, size N) is the gradient of the dual barrier
                   problem at x, s, and lda; if there are no inequality constraints,
                   then kkt2=0
                 * kkt3 (numpy array, size M) is the equality constraint satisfaction
                   (i.e. solve ce at x); if there are no equality constraints, then
                   kkt3=0
                 * kkt4 (numpy array, size N) is the inequality constraint 
                   satisfaction (i.e. solve ci at x); if there are inequality
                   constraints, then kkt=0
               [NOTE] All arguments are required. If s and/or lda are irrelevant to
                 the user's problem, set those variables to a 0 dimensional numpy
                 array.

            TO Do: Translate numpy functions into theano functions


    """

    def __init__(self, x0=None, x_dev=None, f=None, df=None, d2f=None, ce=None, dce=None, d2ce=None, ci=None, dci=None, d2ci=None,
            lda0=None, lambda_dev=None, s0=None, mu=0.2, nu=10.0, rho=0.1, tau=0.995, eta=1.0E-4, beta=0.4,
            miter=20, niter=10, Xtol=None, Ktol=1.0E-4, lbfgs=False, lbfgs_zeta=None, float_dtype=np.float32,
            verbosity=1):

        self.x0 = x0
        self.x_dev = x_dev
        self.lda0 = lda0
        self.lambda_dev = lambda_dev
        self.s0 = s0

        self.f = f
        self.df = df
        self.d2f = d2f
        self.ce = ce
        self.dce = dce
        self.d2ce = d2ce
        self.ci = ci
        self.dci = dci
        self.d2ci = d2ci

        self.eps = np.finfo(float_dtype).eps

        self.mu = mu
        self.nu = nu
        self.rho = rho
        self.tau = tau
        self.eta = eta
        self.beta = beta
        self.miter = miter
        self.niter = niter
        if Xtol:
            self.Xtol = Xtol
        else:
            self.Xtol = self.eps
        self.Ktol = Ktol

        self.reg_coef = float_dtype(np.sqrt(self.eps))

        self.lbfgs = lbfgs
        if self.lbfgs and lbfgs_zeta is None:
            self.lbfgs_zeta = float_dtype(1.0)
        self.lbfgs_fail_max = lbfgs

        self.verbosity = verbosity
        self.float_dtype = float_dtype

        self.delta0 = self.reg_coef

        self.compiled = False

    def check_precompile(self, func):
        return isinstance(func, theano.compile.function_module.Function)

    def validate_and_compile(self, nvar=None, neq=None, nineq=None):
        """Validate some of the input variables and compile the objective function,
           the gradient, and the Hessian with constraints.

        """

        assert self.x_dev is not None
        assert self.f is not None

        # get number of variables and constraints
        if nvar is not None:
            self.nvar = nvar
        if neq is not None:
            self.neq = neq
        else:
            self.neq = None
        if nineq is not None:
            self.nineq = nineq
        else:
            self.nineq = None

        if self.ce is not None and self.neq is None:
            CE = theano.function(
                inputs = [self.x_dev],
                outputs = self.ce,
            )

            c = CE(self.x0)
            self.neq = c.size
        elif neq is None:
            self.neq = 0
        else:
            self.neq = neq

        if self.ci is not None and self.nineq is None:
            CI = theano.function(
                inputs = [self.x_dev],
                outputs = self.ci,
            )

            c = CI(self.x0)
            self.nineq = c.size
        elif nineq is None:
            self.nineq = 0
        else:
            self.nineq = nineq

        # declare device variables
        if self.lambda_dev is None:
            self.lambda_dev = T.vector('lamda_dev')
        self.s_dev = T.vector('s_dev')
        self.M_dev = T.matrix('M_dev')
        self.b_dev = T.matrix('b_dev')
        self.dz_dev = T.vector('dz_dev')

        self.mu_dev = theano.shared(self.float_dtype(self.mu), name="mu_dev")
        self.nu_dev = theano.shared(self.float_dtype(self.nu), name="nu_dev")

        # construct expression for the constraint Jacobians and primal problem
        if self.nineq:
            Sigma = diag(self.lambda_dev[self.neq:] / (self.s_dev + self.eps))
            if self.dci is None:
                dci = theano.gradient.jacobian(self.ci, wrt=self.x_dev).reshape((self.nineq, self.nvar)).T
            else:
                dci = self.dci

        if self.neq:
            if self.dce is None:
                dce = theano.gradient.jacobian(self.ce, wrt=self.x_dev).reshape((self.neq, self.nvar)).T
            else:
                dce = self.dce

        # construct expression of all constraints
        if self.neq or self.nineq:
            con = T.zeros((self.neq+self.nineq,))
            if self.neq:
                con = T.set_subtensor(con[:self.neq], self.ce)
            if self.nineq:
                con = T.set_subtensor(con[self.neq:], self.ci-self.s_dev)

        # construct expression for the full constraint Jacobian
        if self.neq or self.nineq:
            jaco = T.zeros((self.nvar+self.nineq, self.neq+self.nineq))
            if self.neq:
                jaco = T.set_subtensor(jaco[:self.nvar,:self.neq], dce)
            if self.nineq:
                jaco = T.set_subtensor(jaco[:self.nvar,self.neq:], dci)
                jaco = T.set_subtensor(jaco[self.nvar:,self.neq:], -T.eye(self.nineq))

        if not self.lbfgs:
            # construct expression for the Hessian of the Lagrangian (assumes Lagrange multipliers included in d2ce/d2ci expresssions
            if self.d2f is None:
                d2L = theano.gradient.hessian(cost=self.f, wrt=self.x_dev)
            else:
                d2L = self.d2f
            if self.neq:
                if self.d2ce is None:
                    d2L -= theano.gradient.hessian(cost=T.sum(self.ce*self.lambda_dev[:self.neq]), wrt=self.x_dev)
                else:
                    d2L -= self.d2ce
            if self.nineq:
                if self.d2ci is None:
                    d2L -= theano.gradient.hessian(cost=T.sum(self.ci*self.lambda_dev[self.neq:]), wrt=self.x_dev)
                else:
                    d2L -= self.d2ci

            # construct expression for the symmetric Hessian matrix
            hess = T.zeros((self.nvar+2*self.nineq+self.neq, self.nvar+2*self.nineq+self.neq))
            hess = T.set_subtensor(hess[:self.nvar,:self.nvar], T.triu(d2L))
            if self.neq:
                hess = T.set_subtensor(hess[:self.nvar,(self.nvar+self.nineq):(self.nvar+self.nineq+self.neq)], dce)
            if self.nineq:
                hess = T.set_subtensor(hess[:self.nvar,(self.nvar+self.nineq+self.neq):], dci)
                hess = T.set_subtensor(hess[self.nvar:(self.nvar+self.nineq),self.nvar:(self.nvar+self.nineq)], T.triu(Sigma))
                hess = T.set_subtensor(hess[self.nvar:(self.nvar+self.nineq),(self.nvar+self.nineq+self.neq):], -T.eye(self.nineq))
            hess = T.triu(hess) + T.triu(hess).T
            hess = hess - T.diag(T.diagonal(hess)/2.0)

        # construct expression for the gradient, merit function, and merit function gradient
        grad = T.zeros((self.nvar+2*self.nineq+self.neq,))
        phi = self.f
        if self.df is None:
            dphi = T.dot(T.grad(self.f, self.x_dev), self.dz_dev[:self.nvar])
        else:
            dphi = T.dot(self.df, self.dz_dev[:self.nvar])
        if self.neq and self.nineq:
            if self.df is None:
                grad = T.set_subtensor(grad[:self.nvar], T.grad(self.f, self.x_dev) - T.dot(dce, self.lambda_dev[:self.neq]) - T.dot(dci, self.lambda_dev[self.neq:]))
            else:
                grad = T.set_subtensor(grad[:self.nvar], self.df - T.dot(dce, self.lambda_dev[:self.neq]) - T.dot(dci, self.lambda_dev[self.neq:]))
            dphi -= self.nu_dev*T.sum(T.abs_(self.ce)) + self.nu_dev*T.sum(T.abs_(self.ci-self.s_dev))
            init_lambda = T.dot(pinv(T.concatenate((dce, dci), axis=1)).reshape((self.neq+self.nineq, self.nvar)), T.grad(self.f, self.x_dev).reshape((self.nvar,1))).reshape((self.neq+self.nineq,))
        elif self.neq:
            if self.df is None:
                grad = T.set_subtensor(grad[:self.nvar], T.grad(self.f, self.x_dev) - T.dot(dce, self.lambda_dev))
            else:
                grad = T.set_subtensor(grad[:self.nvar], self.df - T.dot(dce, self.lambda_dev))
            dphi -= self.nu_dev*T.sum(T.abs_(self.ce))
            init_lambda = T.dot(pinv(dce).reshape((self.neq, self.nvar)), T.grad(self.f, self.x_dev).reshape((self.nvar,1))).reshape((self.neq,))
        elif self.nineq:
            if self.df is None:
                grad = T.set_subtensor(grad[:self.nvar], T.grad(self.f, self.x_dev) - T.dot(dci, self.lambda_dev))
            else:
                grad = T.set_subtensor(grad[:self.nvar], self.df - T.dot(dci, self.lambda_dev))
            dphi -= self.nu_dev*T.sum(T.abs_(self.ci-self.s_dev))
            init_lambda = T.dot(pinv(dci).reshape((self.nineq, self.nvar)), T.grad(self.f, self.x_dev).reshape((self.nvar,1))).reshape((self.nineq,))
        else:
            if self.df is None:
                grad = T.set_subtensor(grad[:self.nvar], T.grad(self.f, self.x_dev))
            else:
                grad = T.set_subtensor(grad[:self.nvar], self.df)

        if self.nineq:
            phi -= self.mu_dev*T.sum(T.log(self.s_dev))
            phi += self.nu_dev*T.sum(T.abs_(self.ci - self.s_dev))
            dphi -= T.dot(self.mu_dev/(self.s_dev+self.eps), self.dz_dev[self.nvar:])
            grad = T.set_subtensor(grad[self.nvar:(self.nvar+self.nineq)], self.lambda_dev[self.neq:]-self.mu_dev/(self.s_dev+self.eps))
            grad = T.set_subtensor(grad[(self.nvar+self.nineq+self.neq):], self.ci-self.s_dev)
            init_slack = T.max(T.concatenate([self.ci.reshape((self.nineq,1)), self.Ktol*T.ones((self.nineq, 1))], axis=1), axis=1)
        
        if self.neq:
            phi += self.nu_dev*T.sum(T.abs_(self.ce))
            grad = T.set_subtensor(grad[(self.nvar+self.nineq):(self.nvar+self.nineq+self.neq)], self.ce)

        # construct expression for gradient of f( + the barrier function)
        barrier_cost_grad = T.zeros((self.nvar+self.nineq,))
        if self.df is None:
            barrier_cost_grad = T.set_subtensor(barrier_cost_grad[:self.nvar], T.grad(self.f, self.x_dev))
        else:
            barrier_cost_grad = T.set_subtensor(barrier_cost_grad[:self.nvar], self.df)
        if self.nineq:
            barrier_cost_grad = T.set_subtensor(barrier_cost_grad[self.nvar:], -self.mu_dev/(self.s_dev+self.eps))

        # construct expression for general linear system solve
        #gen_solve = T.slinalg.solve(self.M_dev, self.b_dev)

        # construct expression for symmetric linear system solve
        sym_solve = T.slinalg.Solve(A_structure='symmetric')
        sym_solve = sym_solve(self.M_dev, self.b_dev)

 
        # compile expressions into device functions
        self.cost = theano.function(
            inputs=[self.x_dev],
            outputs=self.f,
        )

        self.barrier_cost_grad = theano.function(
            inputs=[self.x_dev, self.s_dev],
            outputs=barrier_cost_grad,
            on_unused_input='ignore',
        )

        self.grad = theano.function(
            inputs=[self.x_dev, self.s_dev, self.lambda_dev],
            outputs=grad,
            on_unused_input='ignore',
        )

        if not self.lbfgs:
            self.hess = theano.function(
                inputs=[self.x_dev, self.s_dev, self.lambda_dev],
                outputs=hess,
                on_unused_input='ignore',
            )

        self.phi = theano.function(
            inputs=[self.x_dev, self.s_dev],
            outputs=phi,
            on_unused_input='ignore',
        )

        self.dphi = theano.function(
            inputs=[self.x_dev, self.s_dev, self.dz_dev],
            outputs=dphi,
            on_unused_input='ignore',
        )

        self.eigh = theano.function(
            inputs=[self.M_dev],
            outputs=eigvalsh(self.M_dev, T.eye(self.M_dev.shape[0])),
        )

        self.sym_solve = theano.function(
            inputs=[self.M_dev, self.b_dev],
            outputs=sym_solve,
        )

        #self.gen_solve = theano.function(
        #    inputs=[self.M_dev, self.b_dev],
        #    outputs=gen_solve,
        #)

        if self.neq or self.nineq:
            self.init_lambda = theano.function(
                inputs=[self.x_dev],
                outputs=init_lambda,
            )

            self.con = theano.function(
                inputs=[self.x_dev, self.s_dev],
                outputs=con,
                on_unused_input='ignore',
            )

            self.jaco = theano.function(
                inputs=[self.x_dev],
                outputs=jaco,
                on_unused_input='ignore',
            )

        if self.nineq:
            self.init_slack = theano.function(
                inputs=[self.x_dev],
                outputs=init_slack,
            )

        self.compiled = True

    def KKT(self, x, s, lda):
        """Calculate the first-order Karush-Kuhn-Tucker conditions. Irrelevant
           conditions are set to zero.

        """

        kkts = self.grad(x, s, lda)

        if self.neq and self.nineq:
            kkt1 = kkts[:self.nvar]
            kkt2 = kkts[self.nvar:(self.nvar+self.nineq)]*s
            kkt3 = kkts[(self.nvar+self.nineq):(self.nvar+self.nineq+self.neq)]
            kkt4 = kkts[(self.nvar+self.nineq+self.neq):]
        elif self.neq:
            kkt1 = kkts[:self.nvar]
            kkt2 = self.float_dtype(0.0)
            kkt3 = kkts[(self.nvar+self.nineq):(self.nvar+self.nineq+self.neq)]
            kkt4 = self.float_dtype(0.0)
        elif self.nineq:
            kkt1 = kkts[:self.nvar]
            kkt2 = kkts[self.nvar:(self.nvar+self.nineq)]*s
            kkt3 = self.float_dtype(0.0)
            kkt4 = kkts[(self.nvar+self.nineq+self.neq):]
        else:
            kkt1 = kkts[:self.nvar]
            kkt2 = self.float_dtype(0.0)
            kkt3 = self.float_dtype(0.0)
            kkt4 = self.float_dtype(0.0)

        return [kkt1, kkt2, kkt3, kkt4]

    def lbfgs_init(self):
        """Initialize storage arrays for L-BFGS algorithm.

        """
        
        # initialize diagonal constant and storage arrays
        zeta = self.float_dtype(self.lbfgs_zeta)
        S = np.array([], dtype=self.float_dtype).reshape((self.nvar, 0))
        Y = np.array([], dtype=self.float_dtype).reshape((self.nvar, 0))
        SS = np.array([], dtype=self.float_dtype).reshape((0, 0))
        L = np.array([], dtype=self.float_dtype).reshape((0, 0))
        D = np.array([], dtype=self.float_dtype).reshape((0, 0))
        lbfgs_fail = 0

        return (zeta, S, Y, SS, L, D, lbfgs_fail)

    def lbfgs_dir(self, x, s, lda, g, zeta, S, Y, SS, L, D):
        """Calculate the descent direction for the L-BFGS algorithm.

        """

        # get the current number of L-BFGS updates
        m_lbfgs = S.shape[1]

        # calculate the step direction
        if self.neq or self.nineq:
            reduce = False
            B = self.jaco(x)
            if B.shape[0] == B.shape[1]:
                # B is a square matrix
                w = self.eigh(B)
                rcond = np.min(np.abs(w))/np.max(np.abs(w))
                if rcond > self.eps:
                    # B is invertible, reduce problem
                    reduce = True

            # set-up approximate second-derivative to the Lagrangian (diagonal matrix)
            Adiag = zeta*np.ones((self.nvar,1), dtype=self.float_dtype)
            if self.nineq:
                # append Sigma
                Sigma = (lda[self.neq:]/(s + self.eps)).reshape((self.nineq,1))
                Adiag = np.concatenate([Adiag, Sigma], axis=0)

            if reduce:
                # calculate initial inverse Hessian multiplied by the negative gradient
                v01 = self.sym_solve(B, g[:self.nvar+self.nineq].reshape((self.neq+self.nineq,1)))
                v02 = self.sym_solve(B.T, g[self.nvar+self.nineq:].reshape((self.neq+self.nineq,1)))
                v03 = -Adiag*self.sym_solve(B, v02)
                Zg = np.concatenate([v02, v01 + v03], axis=0)

                if m_lbfgs > 0:
                    # set-up quantities to calculate the direction caused by updates to the approximate Hessian
                    W = np.concatenate([zeta*S, Y], axis=1)
                    if self.nineq:
                        W = np.concatenate([W, np.zeros((self.nineq, 2*m_lbfgs), dtype=self.float_dtype)], axis=0)                    
                    invB_W = self.sym_solve(B, W)

                    M0 = np.concatenate([zeta*SS, L], axis=1)
                    M1 = np.concatenate([L.T, -D], axis=1)
                    Minv = np.concatenate([M0, M1], axis=0)

                    # calculate intermediate
                    v10 = np.dot(W.T, Zg[:self.nvar+self.nineq])
                    v11 = -self.sym_solve(Minv, v10)

                    X10 = np.concatenate([np.zeros((self.nvar+self.nineq, 2*m_lbfgs), dtype=self.float_dtype), invB_W], axis=0)
                    XZg = np.dot(X10, v11)

                    # combine two terms to get direction
                    dz = Zg-XZg
                else:
                    # storage arrays empty, set direction to "guess"
                    dz = Zg

            else:
                # set-up quantities for multiplication of the initial inverse Hessian by the negative gradient
                BT_invA = np.copy(B.T)
                BT_invA[:,:self.nvar] /= zeta
                if self.nineq:
                    # multiply by Sigma inverse
                    BT_invA[self.neq:,self.nvar:] = -np.diag(s/(lda[self.neq:] + self.eps))
                BT_invA_B = np.dot(BT_invA, B)
                if self.neq:
                    # check if equality constraints Jacobian product is ill-conditioned
                    w = self.eigh(BT_invA_B[:self.neq,:self.neq])
                    rcond = np.min(np.abs(w))/np.max(np.abs(w))
                    if rcond <= self.eps:
                        # equality constraints Jacobian product is ill-conditioned; adding small diagonal offset
                        BT_invA_B[:self.neq,:self.neq] += self.reg_coef*self.eta*(self.mu_host ** beta)*np.eye(self.neq, dtype=self.float_dtype)
                # calculate initial inverse Hessian multiplied by the negative gradient
                v00 = np.dot(BT_invA, g[:self.nvar+self.nineq].reshape((self.nvar+self.nineq,1)))
                v01 = self.sym_solve(BT_invA_B, v00)
                v02 = g[:self.nvar+self.nineq].reshape((self.nvar+self.nineq,1))/Adiag - np.dot(BT_invA.T, v01)
                v03 = -self.sym_solve(BT_invA_B, g[self.nvar+self.nineq:].reshape((self.neq+self.nineq,1)))
                v04 = -np.dot(BT_invA.T, v03)
                Zg = np.concatenate([v02 + v04, v01 + v03], axis=0)

                if m_lbfgs > 0:
                    # set-up quantities to calculate the direction caused by updates to the approximate Hessian
                    W = np.concatenate([zeta*S, Y], axis=1)
                    if self.nineq:
                        W = np.concatenate([W, np.zeros((self.nineq, 2*m_lbfgs), dtype=self.float_dtype)], axis=0)
                    BT_gmaW = np.dot(B.T, W)/zeta
                    X00 = -self.sym_solve(BT_invA_B, BT_gmaW)
                    X01 = W/zeta + np.dot(BT_invA.T, X00)
                    X02 = np.dot(W.T, X01)
                
                    M0 = np.concatenate([zeta*SS, L], axis=1)
                    M1 = np.concatenate([L.T, -D], axis=1)
                    Minv = np.concatenate([M0, M1], axis=0)

                    # calculate intermediate
                    v10 = np.dot(W.T, Zg[:self.nvar+self.nineq])
                    v11 = self.sym_solve(X02 - Minv, v10)

                    X10 = np.concatenate([X01, -X00], axis=0)
                    XZg = np.dot(X10, v11)

                    # combine two terms to get direction
                    dz = Zg-XZg
                else:
                    # storage arrays empty, set direction to "guess"
                    dz = Zg

                # inefficient prototype for testing
                #H = np.zeros((self.nvar+2*self.nineq+self.neq, self.nvar+2*self.nineq+self.neq))
                #H[:self.nvar,:self.nvar] = zeta*np.eye(self.nvar)
                #if self.nineq:
                #    Sigma = (lda[self.neq:]/(s+self.eps)).reshape((self.nineq,))
                #    H[self.nvar:self.nvar+self.nineq, self.nvar:self.nvar+self.nineq] = np.diag(lda[self.neq:]/(s+self.eps))
                #H[self.nvar+self.nineq:, :self.nvar+self.nineq] = B.T
                #H[:self.nvar+self.nineq, self.nvar+self.nineq:] = B
                #
                #Zg_new = self.sym_solve(H, g.reshape((g.size,1)))
                #
                #if m_lbfgs > 0:
                #    M0 = np.concatenate([zeta*SS, L], axis=1)
                #    M1 = np.concatenate([L.T, -D], axis=1)
                #    Minv = np.concatenate([M0, M1], axis=0)
                #    W = np.concatenate([zeta*S, Y], axis=1)
                #    H[:self.nvar, :self.nvar] = H[:self.nvar, :self.nvar] - np.dot(W, self.sym_solve(Minv, W.T.reshape((W.size/self.nvar, self.nvar))))
                # 
                #dz = self.sym_solve(H, g.reshape((g.size,1)))
        else:
            # SS and L translate to YY and R
            Hg = zeta*g.reshape((self.nvar,1))

            if m_lbfgs:
                W = np.concatenate([S, zeta*Y], axis=1)
                WT_g = np.dot(W.T, g)
                B = -self.sym_solve(L, WT_g[:m_lbfgs].reshape((m_lbfgs,1)))
                A = -self.sym_solve(L.T, np.dot(D + zeta*SS, B)) - self.sym_solve(L.T, WT_g[m_lbfgs:].reshape((m_lbfgs,1)))
                Hg_update = np.dot(W, np.concatenate([A, B], axis=0))
                dz = Hg + Hg_update
            else:
                dz = Hg

            # inefficient prototype for testing
            #H = 1.0/zeta*np.eye(self.nvar)
            #
            #SStrue = np.dot(S.T, S)
            #Ltrue = np.tril(np.dot(S.T, Y), -1)
            #
            #if S.size > 0:
            #    M0 = np.concatenate([1.0/zeta*SStrue, Ltrue], axis=1)
            #    M1 = np.concatenate([Ltrue.T, -D], axis=1)
            #    Minv = np.concatenate([M0, M1], axis=0)
            #    W = np.concatenate([1.0/zeta*S, Y], axis=1)
            #    H -= np.dot(W, self.sym_solve(Minv, W.T.reshape((W.size/self.nvar, self.nvar))))
            #
            #dz = self.sym_solve(H, g.reshape((g.size,1)))

        return dz.reshape((dz.size,))

    def lbfgs_curv_perturb(self, dx, dg):
        """Perturb the curvature of the L-BFGS update when
           np.dot(dg, dx) <= 0.0 to maintain positive definiteness
           of the Hessian approximation.

        """

        if np.dot(dg, dx) <= 0.0:
            idx = np.argmin(dg * dx)
            while np.dot(dg, dx) < -np.sqrt(self.eps) and dg[idx]*dx[idx] < -np.sqrt(self.eps):
                dg[idx] *= 0.5
        if np.dot(dg, dx) < np.sqrt(self.eps) and (self.neq or self.nineq):
            dc_new = self.jaco(x_new)
            dc_old = self.jaco(x_old)
            dcc = np.dot(dc_old, g_old[self.nvar+self.nineq:]) - np.dot(dc_new, g_new[self.nvar+self.nineq:])
            self.delta = self.delta0
            dg_new = np.copy(dg)
            inp = np.dot(dg_new, dx)
            while inp < np.sqrt(self.eps) and np.linalg.norm(dg_new) > np.sqrt(self.eps) and not np.isinf(inp):
                dg_new = np.copy(dg)
                mask = np.where(dg_new*dx < np.sqrt(self.eps))
                dg_new[mask] = dg[mask] + self.delta*np.sign(dx[mask])*np.abs(dcc[mask])
                self.delta *= 2.0
                inp = np.dot(dg_new, dx)
            dg = np.copy(dg_new)

    def lbfgs_update(self, x_old, x_new, g_old, g_new, zeta, S, Y, SS, L, D, lbfgs_fail):
        """Update stored arrays for the next L-BFGS interation

        """

        dx = x_new-x_old
        dg = g_old[:self.nvar]-g_new[:self.nvar]
        # curvature perturbation (not used)
        # dg = self.lbfgs_curv_perturb(dx, dg)
        # calculate updated zeta
        if self.neq or self.nineq:
            zeta_new = np.dot(dg, dx)/(np.dot(dx, dx)+self.eps)
        else:
            zeta_new = np.dot(dg, dx)/(np.dot(dg, dg)+self.eps)
        if np.dot(dx, dg) > np.sqrt(self.eps) and zeta_new > np.sqrt(self.eps):
            zeta = zeta_new
            if S.shape[1] > self.lbfgs:
                # if S and Y exceed memory limit, remove oldest displacements
                S[:,:-1] = S[:,1:]
                Y[:,:-1] = Y[:,1:]
                SS[:-1,:-1] = SS[1:,1:]
                L[:-1,:-1] = L[1:,1:]
                D[:-1,:-1] = D[1:,1:]
            else:
                # otherwise, expand arrays
                lsize = S.shape[1]+1       
                S = np.concatenate([S, np.zeros((self.nvar, 1), dtype=self.float_dtype)], axis=1)
                Y = np.concatenate([Y, np.zeros((self.nvar, 1), dtype=self.float_dtype)], axis=1)
                SS = np.concatenate([SS, np.zeros((1, lsize-1), dtype=self.float_dtype)], axis=0)
                SS = np.concatenate([SS, np.zeros((lsize, 1), dtype=self.float_dtype)], axis=1)
                L = np.concatenate([L, np.zeros((1, lsize-1), dtype=self.float_dtype)], axis=0)
                L = np.concatenate([L, np.zeros((lsize, 1), dtype=self.float_dtype)], axis=1)
                D = np.concatenate([D, np.zeros((1, lsize-1), dtype=self.float_dtype)], axis=0)
                D = np.concatenate([D, np.zeros((lsize, 1), dtype=self.float_dtype)], axis=1)

            S[:,-1] = dx
            Y[:,-1] = dg

            if self.neq or self.nineq:
                SS_update = np.dot(S.T, dx.reshape((self.nvar,1)))
            else:
                # this is YY_update
                SS_update = np.dot(Y.T, dg.reshape((self.nvar,1)))

            # update storage arrays (this is YY for unconstrained)
            SS[:,-1] = SS_update.reshape((SS_update.size,))
            SS[-1,:] = SS_update.reshape((SS_update.size,))
            lsize = SS.shape[1]
            SS = SS.reshape((lsize,lsize))

            if self.neq or self.nineq:
                L_update = np.dot(dx.reshape((1, self.nvar)), Y)
                L[-1,:] = L_update
                L[-1,-1] = self.float_dtype(0.0)
            else:
                # this is R_update and R
                L_update = np.dot(S.T, dg.reshape((self.nvar, 1))).reshape((S.shape[1],))
                L[:,-1] = L_update
            L = L.reshape((lsize,lsize))            

            D_update = np.dot(dx, dg)
            D[-1,-1] = D_update
            D = D.reshape((lsize,lsize))

            lbfgs_fail = 0
        else:
            lbfgs_fail += 1

        if lbfgs_fail > self.lbfgs_fail_max and S.shape[1] > 0:
            if self.verbosity > 2:
                print "Max failures reached, resetting storage arrays."
            zeta, S, Y, SS, L, D, lbfgs_fail = self.lbfgs_init()

        return (zeta, S, Y, SS, L, D, lbfgs_fail)

    def reghess(self, Hc):
        """Regularize the Hessian to avoid ill-conditioning and to escape saddle
           points.

        """

        w = self.eigh(Hc)
        rcond = np.min(np.abs(w))/np.max(np.abs(w))

        if rcond <= self.eps or (self.neq + self.nineq) != np.sum(w < -self.eps):
            if rcond <= self.eps and self.neq:
                ind1 = self.nvar+self.nineq
                ind2 = ind1+self.neq
                Hc[ind1:ind2, ind1:ind2] -= self.reg_coef*self.eta*(self.mu_host ** self.beta)*np.eye(self.neq)
            if self.delta == 0.0:
                self.delta = self.delta0
            else:
                self.delta = np.max([self.delta/2, self.delta0])
            Hc[:self.nvar, :self.nvar] += self.delta*np.eye(self.nvar)
            w = self.eigh(Hc)
            while (self.neq + self.nineq) != np.sum(w < -self.eps):
                Hc[:self.nvar, :self.nvar] -= self.delta*np.eye(self.nvar)
                self.delta *= 10.0
                Hc[:self.nvar, :self.nvar] += self.delta*np.eye(self.nvar)
                w = self.eigh(Hc)

        return Hc

    def step(self, x, dx):
        """Golden section search used to determine the maximum
           step length for slack variables and Lagrange multipliers
           using the fraction to the boundary rule.

        """

        GOLD = (np.sqrt(5)+1.0)/2.0

        a = 0.0
        b = 1.0
        if np.all(x + b*dx >= (1.0-self.tau)*x):
            return b
        else:
            c = b - (b - a)/GOLD
            d = a + (b - a)/GOLD
            while np.abs(b - a) > GOLD*self.Xtol:
                if np.any(x + d*dx < (1.0-self.tau)*x):
                    b = np.copy(d)
                else:
                    a = np.copy(d)
                if c > a:
                    if np.any(x + c*dx < (1.0-self.tau)*x):
                        b = np.copy(c)
                    else:
                        a = np.copy(c)
        
                c = b - (b - a)/GOLD
                d = a + (b - a)/GOLD
            
            return a
    
    def search(self, x0, s0, lda0, dz, alpha_smax, alpha_lmax):
        """Backtracking line search to find a solution that leads
           to a smaller value of the Lagrangian within the confines
           of the maximum step length for the slack variables and
           Lagrange multipliers found using class function 'step'.

        """

        dx = dz[:self.nvar]
        if self.nineq:
            ds = dz[self.nvar:(self.nvar+self.nineq)]

        if self.neq or self.nineq:
            dl = dz[(self.nvar+self.nineq):]
        else:
            dl = self.float_dtype(0.0)
            alpha_lmax = self.float_dtype(0.0)

        x = np.copy(x0)
        s = np.copy(s0)
        phi0 = self.phi(x0, s0)
        dphi0 = self.dphi(x0, s0, dz[:self.nvar+self.nineq])
        correction = False
        if self.nineq:
            if self.phi(x0 + alpha_smax*dx, s0 + alpha_smax*ds) > phi0 + alpha_smax*self.eta*dphi0:
                # second-order correction
                c_old = self.con(x0, s0)
                c_new = self.con(x0+alpha_smax*dx, s0+alpha_smax*ds)
                if np.sum(np.abs(c_new)) > np.sum(np.abs(c_old)):
                    # infeasibility has increased, attempt to correct
                    A = self.jaco(x0).T
                    try:
                        # calculate a feasibility restoration direction
                        dz_p = -self.sym_solve(A, c_new.reshape((self.nvar+self.nineq,1))).reshape((self.nvar+self.nineq,))
                    except:
                        # if the Jacobian is not invertible, find the minimum norm solution instead
                        dz_p = -np.linalg.lstsq(A, c_new)[0]
                    if self.phi(x0 + alpha_smax*dx + dz_p[:self.nvar], s0 + alpha_smax*ds + dz_p[self.nvar:]) <= phi0 + alpha_smax*self.eta*dphi0:
                        alpha_corr = self.step(s0, alpha_smax*ds + dz_p[self.nvar:])
                        if self.phi(x0 + alpha_corr*(alpha_smax*dx + dz_p[:self.nvar]), s0 + alpha_corr*(alpha_smax*ds + dz_p[self.nvar:])) <= phi0 + alpha_corr*self.eta*self.dphi(x0, s0, alpha_smax*np.concatenate([dx, ds], axis=0) + dz_p):
                            if self.verbosity > 2:
                                print "Second-order feasibility correction accepted"
                            # correction accepted
                            correction = True
                if not correction:
                    # infeasibility has not increased, no correction necessary
                    alpha_smax *= self.tau
                    alpha_lmax *= self.tau
                    while self.phi(x0 + alpha_smax*dx, s0 + alpha_smax*ds) > phi0 + alpha_smax*self.eta*dphi0:
                        alpha_smax *= self.tau
                        alpha_lmax *= self.tau
            if correction:
                s = s0 + alpha_corr*(alpha_smax*ds + dz_p[self.nvar:])
            else:
                s = s0 + alpha_smax*ds
        else:
            if self.phi(x0 + alpha_smax*dx, s0) > phi0 + alpha_smax*self.eta*dphi0:
                # second-order correction
                if self.neq:
                    c_old = self.con(x0, s0)
                    c_new = self.con(x0+alpha_smax*dx, s0)
                    if np.sum(np.abs(c_new)) > np.sum(np.abs(c_old)):
                        # infeasibility has increased, attempt to correct
                        A = self.jaco(x0).T
                        try:
                            # calculate a feasibility restoration direction
                            dz_p = -self.sym_solve(A, c_new.reshape((self.nvar,self.nineq,1))).reshape((self.nvar+self.nineq,))
                        except:
                            # if the Jacobian is not invertible, find the minimum norm solution instead
                            dz_p = -np.linalg.lstsq(A, c_new)[0]
                        if self.phi(x0 + alpha_smax*dx + dz_p, s0) <= phi0 + alpha_smax*self.eta*dphi0:
                            # correction accepted
                            if self.verbosity > 2:
                                print "Second-order feasibility correction accepted"
                            alpha_corr = self.float_dtype(1.0)
                            correction = True
                if not correction:
                    # infeasibility has not increased, no correction necessary
                    alpha_smax *= self.tau
                    alpha_lmax *= self.tau
                    while self.phi(x0 + alpha_smax*dx, s0) > phi0 + alpha_smax*self.eta*dphi0:
                        alpha_smax *= self.tau
                        alpha_lmax *= self.tau
        if correction:
            x = x0 + alpha_corr*(alpha_smax*dx + dz_p[:self.nvar])
        else:
            x = x0 + alpha_smax*dx
        if self.neq or self.nineq:
            lda = lda0 + alpha_lmax*dl
        else:
            lda = np.copy(lda0)

        return (x, s, lda)


    def solve(self, x0=None, s0=None, lda0=None, force_recompile=False):
        """Main solver function that initiates, controls the iteraions, and
         performs the primary operations of the line search primal-dual
         interior point method.

        """

        if x0 is not None:
            self.x0 = x0
        if s0 is not None:
            self.s0 = s0
        if lda0 is not None:
            self.lda0 = lda0

        assert (self.x0 is not None) and (self.x0.size > 0)
        assert self.x0.size == self.x0.shape[0]
        self.nvar = self.x0.size
        self.x0 = self.float_dtype(self.x0)

        if not self.compiled or force_recompile:
            self.validate_and_compile()

        x = self.x0
        if self.nineq:
            if self.s0 is None:
                s = self.init_slack(x)
            else:
                s = self.s0.astype(self.float_dtype)
            self.mu_host = self.mu
        else:
            s = np.array([]).astype(self.float_dtype)
            self.mu_host = self.Ktol
            self.mu_dev.set_value(self.float_dtype(self.mu_host))

        if self.neq or self.nineq:
            self.nu_host = self.nu
            self.nu_dev.set_value(self.float_dtype(self.nu_host))
            if self.lda0 is None:
                lda = self.init_lambda(x)
                if self.nineq and self.neq:
                    lda_ineq = lda[self.neq:]
                    lda_ineq[lda_ineq < self.float_dtype(0.0)] = self.float_dtype(self.Ktol)
                    lda[self.neq:] = lda_ineq
                elif self.nineq:
                    lda[lda < self.float_dtype(0.0)] = self.float_dtype(self.Ktol)
            else:
                lda = self.lda0.astype(self.float_dtype)
        else:
            lda = np.array([]).astype(self.float_dtype)

        self.delta = self.float_dtype(0.0)

        kkt = self.KKT(x, s, lda)

        if self.lbfgs:
            zeta, S, Y, SS, L, D, lbfgs_fail = self.lbfgs_init()
            x_old = np.copy(x)
            g = -self.grad(x, s, lda)

        if self.verbosity > 0:
            if self.lbfgs:
                print "Searching for a feasible local minimizer using L-BFGS to approximate the Hessian."
            else:
                print "Searching for a feasible local minimizer using the exact Hessian."

        iter_count = 0

        for outer in range(self.niter):

            if np.linalg.norm(kkt[0]) <= self.Ktol and np.linalg.norm(kkt[1]) <= self.Ktol and np.linalg.norm(kkt[2]) <= self.Ktol and np.linalg.norm(kkt[3]) <= self.Ktol:
                break

            if self.verbosity > 0 and (self.neq or self.nineq):
                print "OUTER ITERATION " + str(outer+1)

            for inner in range(self.miter):

                muTol = np.max([self.Ktol, self.mu_host])
                if np.linalg.norm(kkt[0]) <= muTol and np.linalg.norm(kkt[1]) <= muTol and np.linalg.norm(kkt[2]) <= muTol and np.linalg.norm(kkt[3]) <= muTol:
                    break

                if self.verbosity > 0:
                    
                    if self.neq or self.nineq:
                        msg = "* INNER ITERATION " + str(inner+1)
                    else:
                        msg = "ITERATION " + str(iter_count+1)
                    if self.verbosity > 1:
                        msg += ", f(x) = " + str(self.cost(x))
                    if self.verbosity > 2:
                        msg += ", |dL/dx| = " + str(np.linalg.norm(kkt[0])) + ", |dL/ds| = " + str(np.linalg.norm(kkt[1]))
                        msg += ", |ce| = " + str(np.linalg.norm(kkt[2])) + ", |ci-s| = " + str(np.linalg.norm(kkt[3]))
                    print msg

                if self.lbfgs:
                    if inner > 0 or outer > 0:
                        g_old = -self.grad(x_old, s, lda)
                        g_new = -self.grad(x, s, lda)
                        zeta, S, Y, SS, L, D, lbfgs_fail = self.lbfgs_update(x_old, x, g_old, g_new, zeta, S, Y, SS, L, D, lbfgs_fail)
                        x_old = np.copy(x)
                        g = np.copy(g_new)
                    dz = self.lbfgs_dir(x, s, lda, g, zeta, S, Y, SS, L, D)
                else:
                    g = -self.grad(x, s, lda)
                    Hc = self.reghess(self.hess(x, s, lda))
                    dz = self.sym_solve(Hc, g.reshape((g.size,1))).reshape((g.size,))

                if self.neq or self.nineq:
                    dz[self.nvar+self.nineq:] = -dz[self.nvar+self.nineq:]

                if self.neq or self.nineq:
                    nu_thres = np.dot(self.barrier_cost_grad(x, s), dz[:self.nvar+self.nineq])/(1-self.rho)/np.sum(np.abs(self.con(x, s)))
                    if self.nu_host < nu_thres:
                        self.nu_host = self.float_dtype(nu_thres)
                        self.nu_dev.set_value(self.nu_host)

                if self.nineq:
                    alpha_smax = self.step(s, dz[self.nvar:(self.nvar+self.nineq)])
                    alpha_lmax = self.step(lda[self.neq:], dz[(self.nvar+self.nineq+self.neq):])
                    x, s, lda = self.search(x, s, lda, dz, self.float_dtype(alpha_smax), self.float_dtype(alpha_lmax))
                else:
                    x, s, lda = self.search(x, s, lda, dz, self.float_dtype(1.0), self.float_dtype(1.0))

                #print self.cost(x)
                #print x
                #print s
                #print lda
                #print str(np.linalg.norm(kkt[0])) + " " + str(np.linalg.norm(kkt[2]))

                kkt = self.KKT(x, s, lda)

                iter_count += 1

                if inner >= self.miter-1:
                    if self.verbosity > 0 and (self.neq or self.nineq):
                        print "MAXIMUM INNER ITERATIONS EXCEEDED"

            if outer >= self.niter-1:
                if self.verbosity > 0:
                    if self.neq or self.nineq:
                        print "MAXIMUM OUTER ITERATIONS EXCEEDED"
                    else:
                        print "MAXIMUM ITERATIONS EXCEEDED"
                break

            if self.nineq:
                xi = self.nineq*np.min(s*lda[self.neq:])/(np.dot(s, lda[self.neq:])+self.eps)
                self.mu_host = 0.1*np.min([0.05*(1.0-xi)/(xi+self.eps), 2.0]) ** 3 * np.dot(s, lda[self.neq:])/self.nineq               
                if self.float_dtype(self.mu_host) < self.float_dtype(0.0):
                    self.mu_host = 0.0
                self.mu_host = self.float_dtype(self.mu_host)
                self.mu_dev.set_value(self.mu_host)

        self.x = x
        self.s = s
        self.lda = lda
        self.kkt = kkt
        self.fval = self.cost(x)

        if self.verbosity >= 0 and np.linalg.norm(kkt[0]) <= self.Ktol and np.linalg.norm(kkt[1]) <= self.Ktol and np.linalg.norm(kkt[2]) <= self.Ktol and np.linalg.norm(kkt[3]) <= self.Ktol:
            msg = "Converged "
        elif self.verbosity >= 0:
            msg = "Maximum iterations reached "
            outer = self.niter
            inner = 0

        if self.verbosity >= 0:
            if self.neq or self.nineq:
                if outer > 1:
                    msg += "after " + str(outer-1) + " outer "
                    if outer > 2:
                        msg += "iterations "
                    else:
                        msg += "iteration "
                    msg += "and "
                else:
                    msg += "after "
                msg += str(inner) + " inner "
                if inner > 1:
                    msg += "iterations "
                else:
                    msg += "iteration "
                msg += "(" + str(iter_count) + " total)."
            else:
                msg += "after " + str(iter_count)
                if iter_count > 1:
                    msg += " iterations."
                else:
                    msg += " iteration."
            print msg
            if self.verbosity > 1:
                msg = "FINAL: f(x) = " + str(self.cost(x))
                if self.verbosity > 2:
                    msg += ", |dL/dx| = " + str(np.linalg.norm(kkt[0])) + ", |dL/ds| = " + str(np.linalg.norm(kkt[1]))
                    msg += ", |ce| = " + str(np.linalg.norm(kkt[2])) + ", |ci-s| = " + str(np.linalg.norm(kkt[3]))
                print msg

        return (self.x, self.s, self.lda, self.fval, self.kkt)



def main():
    import sys
    import os

    prob = int(sys.argv[1])
    float_dtype = os.environ.get('THEANO_FLAGS')
    if float_dtype is not None:
        try:
            float_dtype = float_dtype.split('floatX=')[1]
        except IndexError:
            raise Exception("Error: attribute 'floatX' not defined in 'THEANO_FLAGS' environment variable.")
        float_dtype = float_dtype.split(',')[0]
    else:
        raise Exception("Error: 'THEANO_FLAGS' environment variable is unset.")
        exit()

    if float_dtype.strip() == "float32":
        float_dtype = np.float32
    else:
        float_dtype = np.float64

    lbfgs = 4
    x_dev = T.vector('x_dev')
    verbosity = 1

    if prob == 1:
        print "minimize f(x,y) = x**2 - 4*x + y^2 - y - x*y"
        print ""
        x0 = np.random.randn(2).astype(float_dtype)

        f = x_dev[0]**2 - 4*x_dev[0] + x_dev[1]**2 - x_dev[1] - x_dev[0]*x_dev[1]

        p = IPM(x0=x0, x_dev=x_dev, f=f, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        print ""
        print "Ground truth: [x, y] = [" + str(float_dtype(3.0)) + ", " + str(float_dtype(2.0)) + "]"
        print "Solver solution: [x, y] = [" + str(x[0]) + ", " + str(x[1]) + "]"
        print "f(x,y) = " + str(fval)
    elif prob == 2:
        print "Find the global minimum of the 2D Rosenbrock function."
        print "minimize f(x,y) = 100*(y-x**2)**2 + (1-x)**2"
        print ""
        x0 = np.random.randn(2).astype(float_dtype)
        
        f = 100*(x_dev[1]-x_dev[0]**2)**2 + (1-x_dev[0])**2

        p = IPM(x0=x0, x_dev=x_dev, f=f, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        print ""
        print "Ground truth: [x, y] = [" + str(float_dtype(1.0)) + ", " + str(float_dtype(1.0)) + "]"
        print "Solver solution: [x, y] = [" + str(x[0]) + ", " + str(x[1]) + "]"
        print "f(x,y) = " + str(fval)
    elif prob == 3:
        print "maximize f(x,y) = x+y subject to x**2 + y**2 = 1"
        print ""
        x0 = np.random.randn(2).astype(float_dtype)

        f = -T.sum(x_dev)
        ce = T.sum(x_dev ** 2)-1.0

        p = IPM(x0=x0, x_dev=x_dev, f=f, ce=ce, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        print ""
        print "Ground truth: [x, y] = [" + str(float_dtype(np.sqrt(2.0)/2.0)) + ", " + str(float_dtype(np.sqrt(2.0)/2.0)) + "]"
        print "Solver solution: [x, y] = [" + str(x[0]) + ", " + str(x[1]) + "]"
        print "Lagrange multiplier: lda = " + str(lda)
        print "f(x,y) = " + str(-fval)
    elif prob == 4:
        print "maximize f(x,y) = (x**2)*y subject to x**2 + y**2 = 3"
        print ""
        x0 = np.random.randn(2).astype(float_dtype)

        f = -(x_dev[0]**2)*x_dev[1]
        ce = T.sum(x_dev ** 2) - 3.0

        p = IPM(x0=x0, x_dev=x_dev, f=f, ce=ce, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        print ""
        print "Ground truth: global max. @ [x, y] = [" + str(float_dtype(np.sqrt(2.0))) + ", " + str(float_dtype(1.0)) + "] or [" + str(-float_dtype(np.sqrt(2.0))) + ", " + str(float_dtype(1.0)) + "], local max @ [x_gt, y_gt] = [0.0, " + str(-float_dtype(np.sqrt(3))) + "]"
        print "Solver solution: [x, y] = [" + str(x[0]) + ", " + str(x[1]) + "]"
        print "Lagrange multiplier: lda = " + str(lda)
        print "f(x,y) = " + str(-fval)
    elif prob == 5:
        print "minimize f(x,y) = x**2 + 2*y**2 + 2*x + 8*y subject to -x-2*y+10 <= 0, x >= 0, y >= 0"
        print ""
        x0 = np.random.randn(2).astype(float_dtype)

        f = x_dev[0]**2 + 2.0*x_dev[1]**2 + 2.0*x_dev[0] + 8.0*x_dev[1]
        ci = T.zeros((3,))
        ci = T.set_subtensor(ci[0], x_dev[0]+2.0*x_dev[1]-10.0)
        ci = T.set_subtensor(ci[1], x_dev[0])
        ci = T.set_subtensor(ci[2], x_dev[1])

        p = IPM(x0=x0, x_dev=x_dev, f=f, ci=ci, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        print ""
        print "Ground truth: [x, y] = [" + str(float_dtype(4.0)) + ", " +  str(float_dtype(3.0)) + "]"
        print "Solver solution: [x, y] = [" + str(x[0]) + ", " + str(x[1]) + "]"
        print "Slack variables: s = [" + str(-s[0]) + ", " + str(s[1]) + ", " + str(s[2]) + "]"
        print "Lagrange multipliers: lda = [" + str(-lda[0]) + ", " + str(lda[1]) + ", " + str(lda[2]) + "]"
        print "f(x,y) = " + str(fval)
    elif prob == 6:
        print "Find the maximum entropy distribution of a six-sided die:"
        print "maximize f(x) = -sum(x*log(x)) subject to sum(x) = 1 and x >= 0 (x.size=6)"
        print ""
        x0 = np.random.rand(6).astype(float_dtype)
        x0 = x0/np.sum(x0)

        f = T.sum(x_dev*T.log(x_dev + np.finfo(float_dtype).eps))
        ce = T.sum(x_dev) - 1.0
        ci = 1.0*x_dev

        p = IPM(x0=x0, x_dev=x_dev, f=f, ce=ce, ci=ci, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        gt = str(float_dtype(1.0/6.0))
        print ""
        print "Ground truth: x = [" + gt + ", " + gt + ", " + gt + ", " + gt + ", " + gt + ", " + gt + "]"
        print "Solver solution: x = [" + str(x[0]) + ", " + str(x[1]) + ", " + str(x[2]) + ", " + str(x[3]) + ", " + str(x[4]) + ", " + str(x[5]) + "]"
        print "Slack variables: s = [" + str(s[0]) + ", " + str(s[1]) + ", " + str(s[2]) + ", " + str(s[3]) + ", " + str(s[4]) + ", " + str(s[5]) + "]"
        print "Lagrange multipliers: lda = [" + str(lda[0]) + ", " + str(lda[1]) + ", " + str(lda[2]) + ", " + str(lda[3]) + ", " + str(lda[4]) + ", " + str(lda[5]) + ", " + str(lda[6]) + "]"
        print "f(x) = " + str(-fval)
    elif prob == 7:
        print "maximize f(x,y,z) = x*y*z subject to x+y+z = 1, x >= 0, y >= 0, z >= 0"
        print ""
        x0 = np.random.randn(3).astype(float_dtype)

        f = -x_dev[0]*x_dev[1]*x_dev[2]
        ce = T.sum(x_dev) - 1.0
        ci = 1.0*x_dev

        p = IPM(x0=x0, x_dev=x_dev, f=f, ce=ce, ci=ci, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        print ""
        print "Ground truth: [x, y, z] = [" + str(float_dtype(1.0/3.0)) + ", " + str(float_dtype(1.0/3.0)) + ", " + str(float_dtype(1.0/3.0)) + "]"
        print "Solver solution: [x, y, z] = [" + str(x[0]) + ", " + str(x[1]) + ", " + str(x[2]) + "]"
        print "Slack variables: s = [" + str(s[0]) + ", " + str(s[1]) + ", " + str(s[2]) + "]"
        print "Lagrange multipliers: lda = [" + str(lda[0]) + ", " + str(lda[1]) + ", " + str(lda[2]) + ", " + str(lda[3]) + "]"
        print "f(x,y,z) = " + str(-fval)
    elif prob == 8:
        print "minimize f(x,y,z) = 4*x-2*z subject to 2*x-y-z = 2, x**2 + y**2 = 1" 
        print ""
        x0 = np.random.randn(3).astype(float_dtype)

        f = 4.0*x_dev[1] - 2.0*x_dev[2]
        ce = T.zeros((2,))
        ce = T.set_subtensor(ce[0], 2.0*x_dev[0]-x_dev[1]-x_dev[2]-2.0)
        ce = T.set_subtensor(ce[1], x_dev[0]**2+x_dev[1]**2-1.0)

        p = IPM(x0=x0, x_dev=x_dev, f=f, ce=ce, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        print ""
        print "Ground truth: [x, y, z] = [" + str(float_dtype(2.0/np.sqrt(13.0))) + ", " + str(-float_dtype(3.0/np.sqrt(13.0))) + ", " + str(float_dtype(-2.0+7.0/np.sqrt(13.0))) + "]"
        print "Solver solution: [x, y, z] = [" + str(x[0]) + ", " + str(x[1]) + ", " + str(x[2]) + "]"
        print "Lagrange multipliers: lda = [" + str(lda[0]) + ", " + str(lda[1]) + "]"
        print "f(x,y,z) = " + str(fval)
    elif prob == 9:
        print "minimize f(x,y) = (x-2)**2 + 2*(y-1)**2 subject to x+4*y <= 3, x >= y"
        print ""
        x0 = np.random.randn(2).astype(float_dtype)

        f = (x_dev[0]-2.0)**2 + 2.0*(x_dev[1]-1.0)**2
        ci = T.zeros(2)
        ci = T.set_subtensor(ci[0], -x_dev[0]-4.0*x_dev[1]+3.0)
        ci = T.set_subtensor(ci[1], x_dev[0]-x_dev[1])

        p = IPM(x0=x0, x_dev=x_dev, f=f, ci=ci, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        print ""
        print "Ground truth: [x, y] = [" + str(float_dtype(5.0/3.0)) + ", " + str(float_dtype(1.0/3.0)) + "]"
        print "Solver solution: [x, y] = [" + str(x[0]) + ", " + str(x[1]) + "]"
        print "Slack variables: s = [" + str(-s[0]) + ", " + str(s[1]) + "]"
        print "Lagrange multipliers: lda = [" + str(-lda[0]) + ", " + str(lda[1]) + "]"
        print "f(x,y) = " + str(fval)
    elif prob == 10:
        print "minimize f(x,y,z) = (x-1)**2 + 2*(y+2)**2 + 3*(z+3)**2 subject to z-y-x = 1, z-x**2 >= 0"
        print ""
        x0 = np.random.randn(3).astype(float_dtype)

        f = (x_dev[0]-1.0)**2 + 2.0*(x_dev[1]+2.0)**2 + 3.0*(x_dev[2]+3.0)**2
        ce = x_dev[2] - x_dev[1] - x_dev[0] - 1.0
        ci = x_dev[2] - x_dev[0]**2

        p = IPM(x0=x0, x_dev=x_dev, f=f, ce=ce, ci=ci, lbfgs=lbfgs, float_dtype=float_dtype, verbosity=verbosity)
        x, s, lda, fval, kkt = p.solve()

        print ""
        print "Ground truth: [x, y, z] = [0.12288, -1.1078, 0.015100]"
        print "Solver solution: [x, y, z] = [" + str(x[0]) + ", " + str(x[1]) + ", " + str(x[2]) + "]"
        print "Slack variable: s = " + str(s)
        print "Lagrange multipliers: lda = [" + str(lda[0]) + ", " + str(lda[1]) + "]"
        print "f(x,y) = " + str(fval)

    print "Karush-Kuhn-Tucker conditions (up to a sign):"
    print kkt

if __name__ == '__main__':
    main()

