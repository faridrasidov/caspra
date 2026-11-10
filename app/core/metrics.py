from threading import Lock

from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

_registry = CollectorRegistry()
_lock = Lock()
_metrics = {}
Gauge("caspra_process_info", "Caspra process marker", registry=_registry).set(1)


def _metric(kind, name, labels):
    keys = tuple(sorted(labels))
    key = (kind, name, keys)
    with _lock:
        metric = _metrics.get(key)
        if metric is None:
            metric = kind(f"caspra_{name}", name.replace("_", " "), keys, registry=_registry)
            _metrics[key] = metric
    return metric.labels(**{key: str(value) for key, value in labels.items()}) if keys else metric


def increment_metric(name: str, **labels: str | int) -> None:
    _metric(Counter, name, labels).inc()


def set_metric_gauge(name: str, value: float | int, **labels: str | int) -> None:
    _metric(Gauge, name, labels).set(value)


def observe_metric(name: str, value: float, **labels: str | int) -> None:
    _metric(Histogram, name, labels).observe(value)


def render_metrics() -> Response:
    return Response(generate_latest(_registry), headers={"Content-Type": CONTENT_TYPE_LATEST})
