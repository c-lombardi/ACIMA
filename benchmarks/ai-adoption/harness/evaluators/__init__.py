"""Independent evaluation.

Two stages, deliberately separate from the executing agent: deterministic checks over captured
evidence, and a ground-truth comparison using the scenario's independently established evidence.
Neither stage is allowed to infer success from the agent's own claims.
"""
