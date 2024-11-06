from typing import Dict

from prometheus_api_client import PrometheusConnect  # type:ignore


def get_water_gas() -> Dict[str, float | str]:
    prom = PrometheusConnect(url="http://192.168.1.207:9090")

    return {
        "water_day": _get_query(prom, "increase(watermeter_count[24h])"),
        "water_cost": _get_query(prom, "increase(watercost_total[24h])"),
        "gas_day":
            _get_query(prom,
                       "increase(glowprom_import_cumulativevol_m3[24h])"),
        "gas_cost": _get_query(prom,
                               "increase(octopus_cost{type=\"gas\"}[24h])"),
    }


def _get_query(prom: PrometheusConnect, query: str) -> float:
    data = prom.custom_query(query)

    return float(data[0]["value"][1])


if __name__ == "__main__":
    print(get_water_gas())
