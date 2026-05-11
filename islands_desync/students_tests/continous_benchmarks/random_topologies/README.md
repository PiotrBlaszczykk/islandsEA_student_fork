# Deterministic Random Topologies

This directory contains the random-topology experiment track. The topologies
are random only at generation time. Runtime reads frozen adjacency lists from
JSON, which keeps HPC runs reproducible.

Generate graphs and matrix from outer `islands_desync/`:

```bash
python3 students_tests/continous_benchmarks/random_topologies/generate_random_topologies.py
```

From the repository root, prefix the path with `islands_desync/`.

Generated graph files live in:

```text
students_tests/continous_benchmarks/random_topologies/graphs/
```

The generated matrix is:

```text
students_tests/continous_benchmarks/random_topologies/benchmark_matrix_random_topologies.csv
```

Current topology variants:

```text
rt_er_d4_s1       connected Erdos-Renyi, expected degree about 4
rt_er_d8_s1       connected Erdos-Renyi, expected degree about 8
rt_ws_k4_p010_s1  Watts-Strogatz, k=4, beta=0.10
```

Current matrix:

```text
3 objective functions x 3 random topologies x 4 migrant strategies x 3 island counts x 3 repeats = 324 jobs
```

Island counts are `48`, `96`, and `144`. Do not mix this matrix with the
fixed-topology full matrix; run it as a separate batch, preferably on a
separate cluster/workspace.
