from datetime import datetime
import re
from typing import Dict, List, Optional

from nredarwin.webservice import DarwinLdbSession, StationBoard  # type:ignore

DARWIN = DarwinLdbSession(
    wsdl="https://lite.realtime.nationalrail.co.uk/"
         + "OpenLDBWS/wsdl.aspx?ver=2021-11-01")

NORTH_STATIONS = set([
    "Royston",
    "Stevenage",
    "Cambridge",
    "Peterborough",
    "Letchworth Garden City"
])

SOUTH_STATIONS = set([
    "Hatfield", "Welwyn Green", "Brookmans Park",
    "Potters Bar", "Hadley Wood", "New Barnet",
    "Oakleigh Park", "New Southgate", "Alexandra Palace",
    "Harringay", "Hornsey", "Finsbury Park", "London Kings Cross",
    "Old Street", "Moorgate", "Sevenoaks"
])

HTML_RE = re.compile(r"<[^>]+?>")


class BoardCache:
    def __init__(self, departures: bool) -> None:
        self.departures = departures
        self.last_update: Optional[datetime] = None
        self.board: Optional[StationBoard] = None

    def get(self) -> StationBoard:
        if self.last_update is None \
           or (datetime.utcnow() - self.last_update).total_seconds() > 300:
            self.board = DARWIN.get_station_board(
                                    crs='WGC',
                                    include_departures=self.departures,
                                    include_arrivals=not self.departures)
            self.last_update = datetime.utcnow()
        return self.board


DEPARTURE_BOARD = BoardCache(True)
ARRIVALS_BOARD = BoardCache(False)


def get_trains_to_london() -> List[Dict[str, str | bool]]:
    board = DEPARTURE_BOARD.get()

    r: List[Dict[str, str | bool]] = []

    for train in board.train_services:
        if train.destination_text in NORTH_STATIONS:
            continue
        r.append({
            "destination": train.destination_text,
            "platform": train.platform,
            "scheduled": train.std,
            "eta": train.etd,
            "is_late": _is_late(train.std, train.etd)
        })

    return r


def get_trains_from_london() -> List[Dict[str, str | bool]]:
    board = ARRIVALS_BOARD.get()

    r: List[Dict[str, str | bool]] = []

    for train in board.train_services:
        if train.destination_text in SOUTH_STATIONS:
            continue
        details = DARWIN.get_service_details(train.service_id)
        r.append({
            "destination": train.origin_text,
            "platform": train.platform,
            "scheduled": train.sta,
            "eta": train.eta,
            "is_late": _is_late(train.sta, train.eta),
            "message": details.disruption_reason or details.overdue_message
        })

    return r


def get_trains_message() -> Optional[str]:
    msg = " ".join(DEPARTURE_BOARD.get().nrcc_messages)

    msg = HTML_RE.sub("", msg)
    msg = msg.replace("\n", " ")
    while "  " in msg:
        msg = msg.replace("  ", " ")
    msg = msg.replace(" More details can be found in Latest Travel News.", "")
    msg = msg.replace(" Latest information can be found in Status and Disruptions.", "")
    return msg.strip()


def _is_late(scheduled: str, estimated: str) -> bool:
    if estimated == "On time" or scheduled is None or estimated is None:
        return False
    if estimated in ("Cancelled", "Delayed"):
        return True
    shour, sminute = int(scheduled.split(":")[0]), int(scheduled.split(":")[1])
    ehour, eminute = int(estimated.split(":")[0]), int(estimated.split(":")[1])

    return (ehour > shour) or (eminute > sminute)


if __name__ == "__main__":
    print(get_trains_message())
    print()
    print(get_trains_to_london())
    print()
    print(get_trains_from_london())
