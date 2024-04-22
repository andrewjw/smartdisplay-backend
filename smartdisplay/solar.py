import time
from typing import Dict, Tuple

from prometheus_api_client import PrometheusConnect  # type:ignore

IMPORT_QUERY = """
increase(glowprom_import_cumulative_Wh{type="electric"}[24h])
- on () increase(teslamate_home_kwh_total[24h]) * 1000
"""

CAR_QUERY = "increase(teslamate_home_kwh_total[24h]) * 1000"


def get_current_solar() -> Dict[str, float | str]:
    prom = PrometheusConnect(url="http://192.168.1.207:9090")

    return {
        "house": _get_query(prom, IMPORT_QUERY),
        "car": _get_query(prom, CAR_QUERY),
        "pv_power": _get_metric(prom, "foxess_pvPower"),
        "battery": _get_metric(prom, "foxess_SoC"),
        "current_power": _get_metric(prom, "glowprom_power_W"),
        "battery_change":
            _get_query(prom,
                       "foxess_batChargePower - foxess_batDischargePower")
    }


def _get_metric(prom: PrometheusConnect, metric: str) -> float:
    data = prom.get_current_metric_value(metric_name=metric)

    return float(data[0]["value"][1])


def _get_query(prom: PrometheusConnect, query: str) -> float:
    data = prom.custom_query(query)

    return float(data[0]["value"][1])


if __name__ == "__main__":
    print(get_current_solar())
