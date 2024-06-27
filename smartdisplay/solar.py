import time
from typing import Dict, Tuple

from prometheus_api_client import PrometheusConnect  # type:ignore

IMPORT_QUERY = """
increase(glowprom_import_cumulative_Wh{type="electric"}[24h])
- on () increase(teslamate_home_kwh_total[24h]) * 1000
- on () increase(octopus_export[24h])
"""

CAR_QUERY = "increase(teslamate_home_kwh_total[24h]) * 1000"

HOUSE_COST = """
increase(octopus_cost{type="electric"}[24h])
- on () delta(teslamate_home_cost_total[24h])
- on () increase(octopus_feed_in{type="electric"}[24h])
"""

CAR_COST = "delta(teslamate_home_cost_total[24h])"


def is_solar_valid() -> bool:
    prom = PrometheusConnect(url="http://192.168.1.207:9090")

    try:
        _get_metric(prom, "foxess_pvPower")
    except IndexError:
        return False
    return True


def get_current_solar() -> Dict[str, float | str]:
    prom = PrometheusConnect(url="http://192.168.1.207:9090")

    return {
        "house_wh": _get_query(prom, IMPORT_QUERY),
        "car_wh": _get_query(prom, CAR_QUERY),
        "house_cost": _get_query(prom, HOUSE_COST),
        "car_cost": _get_query(prom, CAR_COST),
        "pv_power": _get_metric(prom, "foxess_pvPower"),
        "battery": _get_metric(prom, "foxess_SoC"),
        "house_load": _get_metric(prom, "foxess_loadsPower"),
        "current_power": _get_metric(prom, "glowprom_power_W"),
        "battery_change":
            _get_query(prom,
                       "foxess_batChargePower - foxess_batDischargePower")
            * 1000
    }


def _get_metric(prom: PrometheusConnect, metric: str) -> float:
    data = prom.get_current_metric_value(metric_name=metric)

    return float(data[0]["value"][1])


def _get_query(prom: PrometheusConnect, query: str) -> float:
    data = prom.custom_query(query)

    return float(data[0]["value"][1])


if __name__ == "__main__":
    print(get_current_solar())
