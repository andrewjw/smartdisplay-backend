import time
from typing import Dict, Tuple

from prometheus_api_client import PrometheusConnect  # type:ignore


def get_current_weather_last_update() -> float:
    prom = PrometheusConnect(url="http://192.168.1.207:9090")

    last_message = _get_weather_metric(prom, "last_message")

    return time.time() - last_message


def get_current_weather() -> Dict[str, float | str]:
    prom = PrometheusConnect(url="http://192.168.1.207:9090")

    pressure, pressure_change, pressure_text = get_pressure(prom)

    return {
        "temperature": _get_weather_metric(prom, "temperature"),
        "humidity": _get_weather_metric(prom, "humidity"),
        "lux": _get_weather_metric(prom, "light_lux"),
        "uv": _get_weather_metric(prom, "uvi"),
        "gust": _get_weather_metric(prom, "wind_max_m"),
        "wind": _get_weather_metric(prom, "wind_avg_m"),
        "winddir": get_wind_dir(prom),
        "rain_24h": _get_weather_query(prom, "increase(prom433_rain[24h])"),
        "rain_1h": _get_weather_query(prom, "increase(prom433_rain[1h])"),
        "pressure": pressure,
        "pressure_change": pressure_change,
        "pressure_text": pressure_text
    }


def get_pressure(prom: PrometheusConnect) -> Tuple[float, str, str]:
    data = prom.get_current_metric_value(metric_name="bge_pressure")

    pressure = float(data[0]["value"][1])

    change = _get_weather_query(prom,
                                "bge_pressure - (bge_pressure offset 2h)")

    if pressure < 965:
        text = "Stormy"
    elif pressure < 985:
        text = "Rainy"
    elif pressure < 1015:
        text = "Changeable"
    elif pressure < 1035:
        text = "Fair"
    else:
        text = "Very Dry"

    if change > 0.5:
        return pressure, "increasing", text
    elif change < -0.5:
        return pressure, "decreasing", text
    else:
        return pressure, "level", text


def get_wind_dir(prom: PrometheusConnect) -> str:
    direction = _get_weather_query(prom,
                                   "avg_over_time(prom433_wind_dir_deg[15m])")

    if direction < 22.5:
        return "N"
    if direction < 22.5 + 45:
        return "NE"
    if direction < 90 + 22.5:
        return "E"
    if direction < 90 + 45 + 22.5:
        return "SE"
    if direction < 180 + 22.5:
        return "S"
    if direction < 180 + 45 + 22.5:
        return "SW"
    if direction < 270 + 22.5:
        return "W"
    if direction < 270 + 45 + 22.5:
        return "NW"
    return "N"


def _get_weather_metric(prom: PrometheusConnect, metric: str) -> float:
    data = prom.get_current_metric_value(metric_name='prom433_' + metric,
                                         label_config={"model":
                                                       "Fineoffset-WS90"})

    return float(data[0]["value"][1])


def _get_weather_query(prom: PrometheusConnect, query: str) -> float:
    data = prom.custom_query(query)

    return float(data[0]["value"][1])


if __name__ == "__main__":
    print(get_current_weather_last_update())
    print(get_current_weather())
