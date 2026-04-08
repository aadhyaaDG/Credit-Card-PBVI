import uuid


def generate_run_id() -> str:
    """
    Generate a unique run identifier for one pipeline invocation.
    Call once at pipeline startup and pass to all loaders and dbt invocations.
    """
    return f"run_{uuid.uuid4()}"
