from datetime import datetime
import re
from typing import Dict, List, Optional, Set

from nredarwin.webservice import DarwinLdbSession, StationBoard  # type: ignore

DARWIN = DarwinLdbSession(
    wsdl="https://lite.realtime.nationalrail.co.uk/"
    + "OpenLDBWS/wsdl.aspx?ver=2021-11-01"
)

NORTH_STATIONS = set([
    "Welwyn Garden City",
    "Royston",
    "Stevenage",
    "Cambridge",
    "Peterborough",
    "Letchworth Garden City"
])

SOUTH_STATIONS = set(
    [
        "Hatfield",
        "Welwyn Green",
        "Brookmans Park",
        "Potters Bar",
        "Hadley Wood",
        "New Barnet",
        "Oakleigh Park",
        "New Southgate",
        "Alexandra Palace",
        "Harringay",
        "Hornsey",
        "Finsbury Park",
        "London Kings Cross",
        "Old Street",
        "Moorgate",
        "Sevenoaks",
    ]
)

HTML_RE = re.compile(r"<[^>]+?>")


class BoardCache:
    def __init__(self, departures: bool, stations: Set[str]) -> None:
        self.departures = departures
        self.last_update: Optional[datetime] = None
        self.board: List[Dict[str, str | bool]] = []
        self.stations = stations

    def get(self) -> StationBoard:
        if self.last_update is None \
           or (datetime.utcnow() - self.last_update).total_seconds() > 300:
            board = DARWIN.get_station_board(
                                    crs='WGC',
                                    include_departures=self.departures,
                                    include_arrivals=not self.departures)
            self.last_update = datetime.utcnow()

            self.board = []
            for train in board.train_services:
                if train.destination_text in self.stations:
                    continue
                details = DARWIN.get_service_details(train.service_id)
                self.board.append({
                    "destination": train.origin_text,
                    "platform": train.platform,
                    "scheduled": train.sta,
                    "eta": train.eta,
                    "is_late": _is_late(train.sta, train.eta),
                    "message": details.disruption_reason or details.overdue_message
                })
        return self.board


DEPARTURE_BOARD = BoardCache(True, SOUTH_STATIONS)
ARRIVALS_BOARD = BoardCache(False, NORTH_STATIONS)


def get_trains_to_london() -> List[Dict[str, str | bool]]:
    return DEPARTURE_BOARD.get()


def get_trains_from_london() -> List[Dict[str, str | bool]]:
    return ARRIVALS_BOARD.get()


TRAINS_MESSAGE: Optional[str] = None
TRAINS_MESSAGE_LAST_UPDATE: Optional[datetime] = None

def get_trains_message() -> Optional[str]:
    global TRAINS_MESSAGE, TRAINS_MESSAGE_LAST_UPDATE
    msg = None
    if TRAINS_MESSAGE_LAST_UPDATE is None \
       or (datetime.utcnow() - TRAINS_MESSAGE_LAST_UPDATE).total_seconds() > 300:
        TRAINS_MESSAGE_LAST_UPDATE = datetime.utcnow()
        TRAINS_MESSAGE = " ".join(DEPARTURE_BOARD.get().nrcc_messages)
        
    msg = HTML_RE.sub("", TRAINS_MESSAGE)
    msg = msg.replace("\n", " ")
    while "  " in msg:
        msg = msg.replace("  ", " ")
    msg = msg.replace(" More details can be found in Latest Travel News.", "")
    msg = msg.replace(
        " Latest information can be found in Status and Disruptions.", "")
    msg = msg.replace(" Please speak to station staff for further assistance.", "")
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
