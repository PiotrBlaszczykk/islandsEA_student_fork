#!/usr/bin/env python3
import argparse
import ast
import json
import math
import random
import re
from collections import defaultdict, deque
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
except ModuleNotFoundError:
    plt = None
    LineCollection = None


SCRIPT_DIR = Path(__file__).resolve().parent
ISLANDS_ROOT = SCRIPT_DIR.parents[1]
TOPOLOGY_DIR = ISLANDS_ROOT / "islands_desync" / "islands" / "topologies"

HARDCODED_TOPOLOGY_FILES = {
    "er1": "ER1Topology.py",
    "er2": "ER2Topology.py",
    "er3": "ER3Topology.py",
    "er4": "ER4Topology.py",
    "ws3": "WS3Topology.py",
    "ws4": "WS4Topology.py",
}


def parse_result_file(path):
    if not path:
        return {}, {}

    result_path = Path(path)
    if not result_path.exists():
        raise FileNotFoundError(result_path)

    values = {}
    meta = {}
    number_re = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    island_re = re.compile(rf"^\s*(\d+)\s+({number_re})\s*$")

    for raw_line in result_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        match = island_re.match(line)
        if match:
            values[int(match.group(1))] = float(match.group(2))
            continue

        if "MIGRANT SELECTION STRATEGY" in line:
            meta["migrant_selection_strategy"] = line.split()[3]
        elif "MIGRANT ACCEPTATION STRATEGY" in line:
            meta["migrant_acceptation_strategy"] = line.replace("-", " ").split()[-1]
        elif "TOPOLOGY" in line:
            parts = line.replace("-", " ").split()
            if parts:
                meta["topology"] = parts[0]
        elif line.startswith("Average result"):
            meta["average_result"] = _last_float(line)
        elif line.startswith("Best result"):
            meta["best_result"] = _last_float(line)
        elif line.startswith("Winner island"):
            winner = re.search(r"Winner island:\s*(\d+)", line)
            if winner:
                meta["winner_island"] = int(winner.group(1))

    return values, meta


def _last_float(text):
    matches = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", text)
    return float(matches[-1]) if matches else None


def load_hardcoded_topology(name):
    file_name = HARDCODED_TOPOLOGY_FILES.get(name)
    if file_name is None:
        raise ValueError(f"Topology '{name}' is not available as a hardcoded map")

    source_path = TOPOLOGY_DIR / file_name
    tree = ast.parse(source_path.read_text(encoding="utf-8", errors="replace"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "topol":
                    data = ast.literal_eval(node.value)
                    return {int(k): [int(v) for v in vals] for k, vals in data.items()}

    raise ValueError(f"No 'topol = {{...}}' assignment found in {source_path}")


def build_adjacency(topology, island_count, torus_width=12):
    topology = topology.lower()

    if topology == "ring":
        if island_count == 1:
            return {0: []}
        if island_count == 2:
            return {0: [1], 1: [0]}
        return {i: [i, (i + 1) % island_count] for i in range(island_count)}

    if topology == "complete":
        return {
            i: [j for j in range(island_count) if j != i]
            for i in range(island_count)
        }

    if topology == "torus":
        if island_count % torus_width != 0:
            raise ValueError(
                f"Torus requires island_count divisible by {torus_width}; got {island_count}"
            )
        result = {}
        for i in range(island_count):
            row = i // torus_width
            top = (i - torus_width) % island_count
            right = ((i + 1) % torus_width) + torus_width * row
            bottom = (i + torus_width) % island_count
            left = (i - 1) % torus_width + torus_width * row
            result[i] = [top, right, bottom, left]
        return result

    if topology in HARDCODED_TOPOLOGY_FILES:
        result = load_hardcoded_topology(topology)
        expected = max(result.keys()) + 1
        if island_count != expected:
            raise ValueError(
                f"Topology {topology} is hardcoded for {expected} islands; got {island_count}"
            )
        return result

    raise ValueError(
        f"Unsupported topology '{topology}'. Use ring, torus, complete, er1-er4, ws3, ws4."
    )


def circular_positions(n):
    return {
        i: (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
        for i in range(n)
    }


def torus_positions(n, width=12):
    return {i: (i % width, -(i // width)) for i in range(n)}


def force_positions(adjacency, n, seed=7, iterations=180):
    rng = random.Random(seed)
    positions = {
        i: (
            math.cos(2 * math.pi * i / n) + rng.uniform(-0.05, 0.05),
            math.sin(2 * math.pi * i / n) + rng.uniform(-0.05, 0.05),
        )
        for i in range(n)
    }
    undirected_edges = {
        tuple(sorted((src, dst)))
        for src, values in adjacency.items()
        for dst in values
        if src != dst
    }

    area = 4.0
    k = math.sqrt(area / max(n, 1))
    temperature = 0.12

    for _ in range(iterations):
        disp = {i: [0.0, 0.0] for i in range(n)}

        for i in range(n):
            xi, yi = positions[i]
            for j in range(i + 1, n):
                xj, yj = positions[j]
                dx = xi - xj
                dy = yi - yj
                dist = math.hypot(dx, dy) + 1e-9
                force = (k * k) / dist
                fx = dx / dist * force
                fy = dy / dist * force
                disp[i][0] += fx
                disp[i][1] += fy
                disp[j][0] -= fx
                disp[j][1] -= fy

        for src, dst in undirected_edges:
            xs, ys = positions[src]
            xd, yd = positions[dst]
            dx = xs - xd
            dy = ys - yd
            dist = math.hypot(dx, dy) + 1e-9
            force = (dist * dist) / k
            fx = dx / dist * force
            fy = dy / dist * force
            disp[src][0] -= fx
            disp[src][1] -= fy
            disp[dst][0] += fx
            disp[dst][1] += fy

        for i in range(n):
            dx, dy = disp[i]
            length = math.hypot(dx, dy) + 1e-9
            step = min(length, temperature)
            x, y = positions[i]
            positions[i] = (x + dx / length * step, y + dy / length * step)

        temperature *= 0.985

    return positions


def compute_metrics(adjacency, n, fitness=None):
    out_degree = {i: len(adjacency.get(i, [])) for i in range(n)}
    in_degree = {i: 0 for i in range(n)}
    self_loops = 0
    edge_count = 0

    undirected = {i: set() for i in range(n)}
    for src, values in adjacency.items():
        for dst in values:
            edge_count += 1
            if src == dst:
                self_loops += 1
            if 0 <= dst < n:
                in_degree[dst] += 1
                if src != dst:
                    undirected[src].add(dst)
                    undirected[dst].add(src)

    components = []
    visited = set()
    for node in range(n):
        if node in visited:
            continue
        queue = deque([node])
        visited.add(node)
        component = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in undirected[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(component)

    total_degree = {i: in_degree[i] + out_degree[i] for i in range(n)}
    metrics = {
        "island_count": n,
        "edge_count_directed": edge_count,
        "self_loops": self_loops,
        "density_directed_no_self": (
            (edge_count - self_loops) / (n * (n - 1)) if n > 1 else 0
        ),
        "min_out_degree": min(out_degree.values()) if out_degree else 0,
        "max_out_degree": max(out_degree.values()) if out_degree else 0,
        "avg_out_degree": sum(out_degree.values()) / n if n else 0,
        "min_in_degree": min(in_degree.values()) if in_degree else 0,
        "max_in_degree": max(in_degree.values()) if in_degree else 0,
        "avg_in_degree": sum(in_degree.values()) / n if n else 0,
        "weak_component_count": len(components),
        "weak_component_sizes": sorted((len(c) for c in components), reverse=True),
        "zero_in_degree_nodes": [i for i, degree in in_degree.items() if degree == 0],
        "zero_out_degree_nodes": [i for i, degree in out_degree.items() if degree == 0],
        "out_degree_by_node": out_degree,
        "in_degree_by_node": in_degree,
        "total_degree_by_node": total_degree,
    }

    if fitness:
        ordered = sorted(fitness.items(), key=lambda item: item[1])
        metrics["best_nodes"] = ordered[:10]
        metrics["worst_nodes"] = ordered[-10:]

    return metrics


def draw_topology(adjacency, topology, island_count, output_path, fitness=None, title=None):
    if plt is None:
        return draw_topology_svg(adjacency, topology, island_count, output_path, fitness, title)

    if topology == "torus":
        positions = torus_positions(island_count)
    elif topology in ("ring", "complete") or island_count <= 24:
        positions = circular_positions(island_count)
    else:
        positions = force_positions(adjacency, island_count)

    edge_segments = []
    for src, values in adjacency.items():
        for dst in values:
            if src == dst or dst not in positions:
                continue
            edge_segments.append([positions[src], positions[dst]])

    fig_width = 10 if island_count <= 50 else 12
    fig_height = 8 if topology != "torus" else max(5, island_count // 24 + 4)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    if edge_segments:
        collection = LineCollection(
            edge_segments,
            colors="#7f8794",
            linewidths=0.45 if island_count > 50 else 0.8,
            alpha=0.25 if island_count > 50 else 0.45,
            zorder=1,
        )
        ax.add_collection(collection)

    xs = [positions[i][0] for i in range(island_count)]
    ys = [positions[i][1] for i in range(island_count)]

    if fitness:
        node_values = [fitness.get(i, float("nan")) for i in range(island_count)]
        scatter = ax.scatter(
            xs,
            ys,
            c=node_values,
            cmap="RdYlGn_r",
            s=58 if island_count <= 50 else 34,
            edgecolors="#1f2937",
            linewidths=0.35,
            zorder=3,
        )
        cbar = fig.colorbar(scatter, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("final fitness (lower is better)")

        worst = sorted(fitness.items(), key=lambda item: item[1], reverse=True)[:8]
        for node, value in worst:
            if node in positions:
                ax.text(
                    positions[node][0],
                    positions[node][1],
                    str(node),
                    fontsize=7,
                    ha="center",
                    va="center",
                    color="#111827",
                    zorder=4,
                )
    else:
        total_degree = defaultdict(int)
        for src, values in adjacency.items():
            total_degree[src] += len(values)
            for dst in values:
                total_degree[dst] += 1
        node_values = [total_degree[i] for i in range(island_count)]
        scatter = ax.scatter(
            xs,
            ys,
            c=node_values,
            cmap="Blues",
            s=58 if island_count <= 50 else 34,
            edgecolors="#1f2937",
            linewidths=0.35,
            zorder=3,
        )
        cbar = fig.colorbar(scatter, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("in + out degree")

    if island_count <= 24:
        for node, (x_pos, y_pos) in positions.items():
            ax.text(x_pos, y_pos, str(node), fontsize=8, ha="center", va="center")

    ax.set_title(title or f"{topology} topology ({island_count} islands)")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.margins(0.08)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=170)
    plt.close(fig)
    return output


def draw_topology_svg(adjacency, topology, island_count, output_path, fitness=None, title=None):
    if topology == "torus":
        positions = torus_positions(island_count)
    elif topology in ("ring", "complete") or island_count <= 24:
        positions = circular_positions(island_count)
    else:
        positions = force_positions(adjacency, island_count)

    output = Path(output_path)
    if output.suffix.lower() != ".svg":
        output = output.with_suffix(".svg")

    width = 1100
    height = 850 if topology != "torus" else max(620, 420 + island_count * 2)
    margin = 55

    xs = [pos[0] for pos in positions.values()]
    ys = [pos[1] for pos in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    def project(node):
        x, y = positions[node]
        sx = margin + (x - min_x) / span_x * (width - 2 * margin)
        sy = margin + (y - min_y) / span_y * (height - 2 * margin)
        return sx, sy

    def color_for(value, values, by_fitness):
        if not values:
            return "#3b82f6"
        lo = min(values)
        hi = max(values)
        ratio = 0.5 if hi == lo else (value - lo) / (hi - lo)
        ratio = max(0.0, min(1.0, ratio))
        if by_fitness:
            # lower objective is better: green -> yellow -> red
            if ratio < 0.5:
                local = ratio / 0.5
                return _rgb_interp((34, 197, 94), (250, 204, 21), local)
            return _rgb_interp((250, 204, 21), (239, 68, 68), (ratio - 0.5) / 0.5)
        return _rgb_interp((191, 219, 254), (30, 64, 175), ratio)

    if fitness:
        node_values = {i: fitness.get(i, 0.0) for i in range(island_count)}
        color_values = list(node_values.values())
    else:
        degree = defaultdict(int)
        for src, values in adjacency.items():
            degree[src] += len(values)
            for dst in values:
                degree[dst] += 1
        node_values = {i: degree[i] for i in range(island_count)}
        color_values = list(node_values.values())

    radius = 7 if island_count <= 50 else 5
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="28" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="20" fill="#111827">'
        f'{_xml_escape(title or f"{topology} topology ({island_count} islands)")}</text>',
    ]

    for src, values in adjacency.items():
        if src not in positions:
            continue
        x1, y1 = project(src)
        for dst in values:
            if dst == src or dst not in positions:
                continue
            x2, y2 = project(dst)
            lines.append(
                f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                'stroke="#7f8794" stroke-width="0.7" stroke-opacity="0.32"/>'
            )

    worst_nodes = set()
    if fitness:
        worst_nodes = {
            node for node, _ in sorted(fitness.items(), key=lambda item: item[1], reverse=True)[:8]
        }

    for node in range(island_count):
        x, y = project(node)
        fill = color_for(node_values[node], color_values, bool(fitness))
        lines.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" '
            f'fill="{fill}" stroke="#1f2937" stroke-width="0.7"/>'
        )
        if island_count <= 24 or node in worst_nodes:
            lines.append(
                f'<text x="{x:.2f}" y="{y + 3:.2f}" text-anchor="middle" '
                'font-family="Arial, sans-serif" font-size="8" fill="#111827">'
                f'{node}</text>'
            )

    legend = "final fitness: green better, red worse" if fitness else "node color: total degree"
    lines.append(
        f'<text x="{margin}" y="{height - 18}" font-family="Arial, sans-serif" '
        f'font-size="13" fill="#374151">{_xml_escape(legend)}</text>'
    )
    lines.append("</svg>")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def _rgb_interp(left, right, ratio):
    values = [
        round(left[index] + (right[index] - left[index]) * ratio)
        for index in range(3)
    ]
    return "#" + "".join(f"{value:02x}" for value in values)


def _xml_escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main():
    parser = argparse.ArgumentParser(description="Plot island topology graphs.")
    parser.add_argument("--topology", required=True, help="ring, torus, complete, er1-er4, ws3, ws4")
    parser.add_argument("--islands", required=True, type=int, help="Number of islands")
    parser.add_argument("--result", help="Optional ___RESULT.txt path for fitness coloring")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--metrics-output", help="Optional JSON metrics output path")
    parser.add_argument("--torus-width", type=int, default=12)
    args = parser.parse_args()

    topology = args.topology.lower()
    adjacency = build_adjacency(topology, args.islands, torus_width=args.torus_width)
    fitness, result_meta = parse_result_file(args.result) if args.result else ({}, {})
    metrics = compute_metrics(adjacency, args.islands, fitness=fitness)
    metrics["topology"] = topology
    metrics["result_meta"] = result_meta

    title = f"{topology} topology ({args.islands} islands)"
    if fitness:
        title += " colored by final fitness"
    actual_output = draw_topology(adjacency, topology, args.islands, args.output, fitness=fitness, title=title)

    if args.metrics_output:
        metrics_path = Path(args.metrics_output)
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"Saved topology plot: {actual_output}")
    if args.metrics_output:
        print(f"Saved topology metrics: {args.metrics_output}")


if __name__ == "__main__":
    main()
