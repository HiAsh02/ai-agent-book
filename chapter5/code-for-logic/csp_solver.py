"""
Offline Constraint Solver: Translates the structured representation of the "Knights and Knaves" puzzle into a Constraint Satisfaction Problem (CSP),
solved using the python-constraint library—this is the deterministic reference implementation for the "code solving" path that Experiment 5-2 aims to demonstrate.

It does not rely on any LLM / network and can run completely offline, so it is used both by build_puzzles.py to verify that a puzzle has a unique solution,
and by demo.py's solver mode to provide a constraint-solving baseline (theoretically 100% correct).

【Structured Statement DSL】Each statement is represented by a JSON-serializable list, with node forms as follows
(True=knight/truth-teller, False=knave/liar):

    ["is",   target, "knight"|"knave"]   # target is a knight / knave
    ["same",  a, b]                       # a and b are the same type
    ["diff",  a, b]                       # a and b are different types
    ["count", "knight"|"knave", op, k]    # the number of that role among all satisfies op k, op ∈ {">=","<=","=="}
    ["and",  s1, s2]                       # conjunction
    ["or",   s1, s2]                       # disjunction
    ["not",  s1]                           # negation

Key modeling rule: For each speaker X, add a 【biconditional constraint】 `t[X] == eval_stmt(X's statement)`—
X is a knight if and only if his statement is true. Never treat the statement itself as a hard constraint.
"""
from constraint import Problem

_OPS = {">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b}


def eval_stmt(node, t):
    """Evaluate the semantic truth value of a statement under an assignment t(name->bool, True=knight)."""
    tag = node[0]
    if tag == "is":
        _, target, role = node
        return t[target] if role == "knight" else (not t[target])
    if tag == "same":
        return t[node[1]] == t[node[2]]
    if tag == "diff":
        return t[node[1]] != t[node[2]]
    if tag == "count":
        _, role, op, k = node
        want = (role == "knight")
        cnt = sum(1 for v in t.values() if v == want)
        return _OPS[op](cnt, k)
    if tag == "and":
        return eval_stmt(node[1], t) and eval_stmt(node[2], t)
    if tag == "or":
        return eval_stmt(node[1], t) or eval_stmt(node[2], t)
    if tag == "not":
        return not eval_stmt(node[1], t)
    raise ValueError(f"Unknown statement node: {node!r}")


def solve(names, structs):
    """Solve using python-constraint, returning a list of all assignments (dict name->bool) that satisfy the constraints.

    names   : list of resident names
    structs : dict name -> structured DSL of that resident's statement
    """
    problem = Problem()
    for n in names:
        problem.addVariable(n, [True, False])

    # Add a biconditional constraint for each speaker: t[X] == (X's statement is true)
    for speaker in names:
        stmt = structs[speaker]

        def make_constraint(speaker=speaker, stmt=stmt):
            def constraint(*values):
                t = dict(zip(names, values))
                return t[speaker] == eval_stmt(stmt, t)
            return constraint

        problem.addConstraint(make_constraint(), names)

    return problem.getSolutions()


def solve_labeled(names, structs):
    """Solve and convert boolean solutions to {name: 'knight'/'knave'}. Return list of solutions (usually unique)."""
    out = []
    for sol in solve(names, structs):
        out.append({n: ("knight" if sol[n] else "knave") for n in names})
    return out


def render_nl(node):
    """Render a structured statement into a Chinese puzzle description (for use with randomly generated puzzles)."""
    tag = node[0]
    if tag == "is":
        role = "knight" if node[2] == "knight" else "knave"
        return f"{node[1]} is {role}。"
    if tag == "same":
        return f"{node[1]} and {node[2]} are the same type."
    if tag == "diff":
        return f"{node[1]} and {node[2]} are different types."
    if tag == "count":
        role = "knight" if node[1] == "knight" else "knave"
        word = {">=": "at least", "<=": "at most", "==": "exactly"}[node[2]]
        return f"Among us, {word} there are {node[3]} {role}。"
    if tag == "and":
        return f"{render_nl(node[1])[:-1]}, and {render_nl(node[2])}"
    if tag == "or":
        return f"{render_nl(node[1])[:-1]}, or {render_nl(node[2])}"
    if tag == "not":
        return f"The following statement is false: {render_nl(node[1])}"
    raise ValueError(f"Unknown statement node: {node!r}")


if __name__ == "__main__":
    # Self-test: kk01 — A says "B is a knave", B says "Neither of us is a knight"
    names = ["A", "B"]
    structs = {
        "A": ["is", "B", "knave"],
        "B": ["and", ["is", "A", "knave"], ["is", "B", "knave"]],
    }
    print("Solution:", solve_labeled(names, structs))
