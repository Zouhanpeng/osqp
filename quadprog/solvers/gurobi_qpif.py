# GUROBI interface to solve QP problems
import numpy as np
from quadprog.results import quadprogResults
import gurobipy as grb
import quadprog.problem as qp


class GUROBI(object):
    """
    An interface for the Gurobi QP solver.
    """

    # Map of Gurobi status to CVXPY status.
    STATUS_MAP = {2: qp.OPTIMAL,
                  3: qp.INFEASIBLE,
                  5: qp.UNBOUNDED,
                  4: qp.SOLVER_ERROR,
                  6: qp.SOLVER_ERROR,
                  7: qp.SOLVER_ERROR,
                  8: qp.SOLVER_ERROR,
                  # TODO could be anything.
                  # means time expired.
                  9: qp.OPTIMAL_INACCURATE,
                  10: qp.SOLVER_ERROR,
                  11: qp.SOLVER_ERROR,
                  12: qp.SOLVER_ERROR,
                  13: qp.SOLVER_ERROR}

    def solve(self, p):

        # Convert Matrices in CSR format
        p.Aeq = p.Aeq.tocsr()
        p.Aineq = p.Aineq.tocsr()

        # Convert Q matrix to COO format
        p.Q = p.Q.tocoo()

        # Get problem dimensions
        nx = p.Q.shape[0]
        neq = p.Aeq.shape[0]
        nineq = p.Aineq.shape[0]

        # Create a new model
        m = grb.Model("qp")

        # Add variables
        for i in range(nx):
            m.addVar(lb=p.lb[i], ub=p.ub[i], obj=p.c[i])
        m.update()
        x = m.getVars()

        # Add equality constraints: iterate over the rows of Aeq
        # adding each row into the model
        for i in range(neq):
            start = p.Aeq.indptr[i]
            end = p.Aeq.indptr[i+1]
            variables = [x[j] for j in p.Aeq.indices[start:end]]  # Get nnz
            coeff = p.Aeq.data[start:end]
            expr = grb.LinExpr(coeff, variables)
            m.addConstr(lhs=expr, sense=grb.GRB.EQUAL, rhs=p.beq[i])

        # Add inequality constraints: iterate over the rows of Aeq
        # adding each row into the model
        for i in range(nineq):
            start = p.Aineq.indptr[i]
            end = p.Aineq.indptr[i+1]
            variables = [x[j] for j in p.Aineq.indices[start:end]]  # Get nnz
            coeff = p.Aineq.data[start:end]
            expr = grb.LinExpr(coeff, variables)
            m.addConstr(lhs=expr, sense=grb.GRB.LESS_EQUAL, rhs=p.bineq[i])

        # Set quadratic cost
        obj = grb.QuadExpr()
        for i in range(p.Q.nnz):
            obj += p.Q.data[i]*x[p.Q.row[i]]*x[p.Q.col[i]]
        m.setObjective(obj)

        # Update model
        m.update()

        # Solve
        m.optimize()


        # Return results
        # Get objective value
        objval = m.objVal
        # Get status
        status = self.STATUS_MAP.get(m.Status, qp.SOLVER_ERROR)
        # Get solution
        sol = np.array([x[i].X for i in range(nx)])

        # Get dual variables
        constrs = m.getConstrs()
        sol_dual_eq = np.array([constrs[i].Pi for i in range(neq)])
        sol_dual_ineq = np.array([constrs[i+neq].Pi for i in range(nineq)])
        RCx = [x[i].RC for i in range(nx)]  # Get reduced costs
        for i in range(nx):
            if RCx[i] >= 1e-07:
                sol_dual_lb = RCx[i]
                sol_dual_ub = 0.0
            else:
                sol_dual_lb = 0.0
                sol_dual_ub = -RCx[i]

        # Get computation time
        cputime = m.Runtime

        return quadprogResults(status, objval, sol, sol_dual_eq,
                               sol_dual_ineq, sol_dual_lb, sol_dual_ub, cputime)