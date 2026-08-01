from collections import Counter
from threading import Lock

from fastapi.responses import PlainTextResponse

_lock = Lock()
_counters: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()
_gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
_observations: dict[
    tuple[str, tuple[tuple[str, str], ...]],
    tuple[int, float],
] = {}


def increment_metric(name: str, **labels: str | int) -> None:
    normalized = tuple(sorted((key, str(value)) for key, value in labels.items()))
    with _lock:
        _counters[(name, normalized)] += 1


def set_metric_gauge(name: str, value: float | int, **labels: str | int) -> None:
    normalized = tuple(sorted((key, str(label)) for key, label in labels.items()))
    with _lock:
        _gauges[(name, normalized)] = float(value)


def observe_metric(name: str, value: float, **labels: str | int) -> None:
    normalized = tuple(sorted((key, str(label)) for key, label in labels.items()))
    metric_key = (name, normalized)
    with _lock:
        count, total = _observations.get(metric_key, (0, 0.0))
        _observations[metric_key] = (count + 1, total + value)


def _labels_text(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    rendered = ",".join(
        f'{key}="{value.replace(chr(34), chr(92) + chr(34))}"' for key, value in labels
    )
    return f"{{{rendered}}}"


def render_metrics() -> PlainTextResponse:
    lines = [
        "# HELP caspra_process_info Caspra API process marker",
        "# TYPE caspra_process_info gauge",
        "caspra_process_info 1",
    ]
    with _lock:
        counters = list(_counters.items())
        gauges = list(_gauges.items())
        observations = list(_observations.items())
    declared: set[str] = set()
    for (name, labels), value in sorted(counters):
        metric_name = f"caspra_{name}"
        if metric_name not in declared:
            lines.append(f"# TYPE {metric_name} counter")
            declared.add(metric_name)
        lines.append(f"{metric_name}{_labels_text(labels)} {value}")
    for (name, labels), value in sorted(gauges):
        metric_name = f"caspra_{name}"
        if metric_name not in declared:
            lines.append(f"# TYPE {metric_name} gauge")
            declared.add(metric_name)
        lines.append(f"{metric_name}{_labels_text(labels)} {value}")
    for (name, labels), (count, total) in sorted(observations):
        metric_name = f"caspra_{name}"
        if metric_name not in declared:
            lines.append(f"# TYPE {metric_name} summary")
            declared.add(metric_name)
        label_text = _labels_text(labels)
        lines.append(f"{metric_name}_count{label_text} {count}")
        lines.append(f"{metric_name}_sum{label_text} {total}")
    return PlainTextResponse("\n".join(lines) + "\n")
