from typing import Dict

from prometheus_api_client import PrometheusConnect  # type:ignore

ROOMS = [
    "lounge",
    "kitchen",
    "mainbedroom",
    "alexbedroom",
    "harrietbedroom",
    "office"
]


def get_house_temperature() -> Dict[str, float]:
    prom = PrometheusConnect(url="http://192.168.1.207:9090")

    labels = {"model": "Fineoffset-WS90"}
    outside = prom.get_current_metric_value(metric_name='prom433_temperature',
                                            label_config=labels)

    data = {}

    for room in ROOMS:
        try:
            data[room] = _get_room_temperature(prom, room)
        except IndexError:
            pass

    try:
        data["outside"] = float(outside[0]["value"][1])
    except IndexError:
        pass

    return data


def _get_room_temperature(prom: PrometheusConnect, room: str) -> float:
    data = prom.get_current_metric_value(metric_name='prom433_temperature',
                                         label_config={"room": room})
    return float(data[0]["value"][1])


if __name__ == "__main__":
    print(get_house_temperature())
