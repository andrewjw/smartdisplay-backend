from typing import Dict

from prometheus_api_client import PrometheusConnect  # type:ignore


def get_air_quality() -> Dict[str, float | str]:
    prom = PrometheusConnect(url="http://192.168.1.207:9090")

    co2 = _get_query(prom, "avg_over_time(bge_co2[5m])")
    voc = _get_query(prom, "avg_over_time(bge_voc[5m])")
    pm25 = _get_query(prom,
                       "avg_over_time(bge_airqual_standard{psize=\"2.5\"}[10m])")

    if co2 < 500:
        co2_level = "Great"
    elif co2 < 600:
        co2_level = "Good"
    elif co2 < 800:
        co2_level = "Ok"
    elif co2 < 1000:
        co2_level = "Bad"
    else:
        co2_level = "Very Bad"

    if voc < 221:
        voc_level = "Great"
    elif voc < 661:
        voc_level = "Good"
    elif voc < 1431:
        voc_level = "Ok"
    elif voc < 2201:
        voc_level = "Bad"
    else:
        voc_level = "Very Bad"

    if pm25 < 9.1:
        pm25_level = "Great"
    elif pm25 < 35.5:
        pm25_level = "Good"
    elif pm25 < 55.5:
        pm25_level = "Ok"
    elif pm25 < 125.5:
        pm25_level = "Bad"
    else:
        pm25_level = "Very Bad"

    return {
        "co2": co2,
        "co2_level": co2_level,
        "voc": voc,
        "voc_level": voc_level,
        "pm25": pm25,
        "pm25_level": pm25_level
    }


def _get_query(prom: PrometheusConnect, query: str) -> float:
    data = prom.custom_query(query)

    return float(data[0]["value"][1])


if __name__ == "__main__":
    print(get_water_gas())
