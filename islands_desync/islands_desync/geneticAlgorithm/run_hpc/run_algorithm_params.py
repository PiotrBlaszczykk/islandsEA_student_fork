import dataclasses


@dataclasses.dataclass
class RunAlgorithmParams:
    island_count: int
    number_of_emigrants: int
    migration_interval: int
    dda: str
    tta: str
    series_number: int
    topology: str
    strategy: str
    strategy2: str
    torus_rows: int | None = None
    torus_columns: int | None = None
    actor_startup_timeout: float = 300.0
