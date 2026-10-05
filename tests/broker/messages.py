"""Small valid messages for the broker tests."""

from datetime import datetime, timezone

from vda5050.models import Factsheet, InstantActions, Order, State, Visualization

MANUFACTURER = "TestMan"
SERIAL = "r1"


def header(n: int = 0, serial: str = SERIAL) -> dict:
    return {"headerId": n, "timestamp": datetime.now(timezone.utc), "version": "2.1.0",
            "manufacturer": MANUFACTURER, "serialNumber": serial}


def make_order(n: int, serial: str = SERIAL) -> Order:
    return Order.model_validate({
        **header(n, serial), "orderId": f"o{n}", "orderUpdateId": 0,
        "nodes": [{"nodeId": "n1", "sequenceId": 0, "released": True, "actions": [],
                   "nodePosition": {"x": 1.0, "y": 2.0, "mapId": "map"}}],
        "edges": [],
    })


def make_instant(n: int, serial: str = SERIAL) -> InstantActions:
    return InstantActions.model_validate({
        **header(n, serial),
        "actions": [{"actionType": "startPause", "actionId": f"a{n}", "blockingType": "HARD"}],
    })


def make_state(n: int = 0, **header_fields) -> State:
    return State.model_validate({
        **header(n), **header_fields,
        "orderId": "", "orderUpdateId": 0, "lastNodeId": "", "lastNodeSequenceId": 0,
        "nodeStates": [], "edgeStates": [], "driving": False, "actionStates": [],
        "batteryState": {"batteryCharge": 50.0, "charging": False},
        "operatingMode": "AUTOMATIC", "errors": [],
        "safetyState": {"eStop": "NONE", "fieldViolation": False},
    })


FACTSHEET_BODY = {
    "typeSpecification": {
        "seriesName": "S1", "agvKinematic": "DIFF", "agvClass": "CARRIER", "maxLoadMass": 1.0,
        "localizationTypes": ["NATURAL"], "navigationTypes": ["AUTONOMOUS"],
    },
    "physicalParameters": {
        "speedMin": 0.1, "speedMax": 1.0, "accelerationMax": 0.5, "decelerationMax": 0.5,
        "heightMax": 0.5, "width": 0.5, "length": 1.0,
    },
    "protocolLimits": {
        "maxStringLens": {}, "maxArrayLens": {},
        "timing": {"minOrderInterval": 1.0, "minStateInterval": 0.5},
    },
    "protocolFeatures": {"optionalParameters": [], "agvActions": []},
    "agvGeometry": {},
    "loadSpecification": {},
}


def make_factsheet(n: int = 0) -> Factsheet:
    return Factsheet.model_validate({**header(n), **FACTSHEET_BODY})


def make_visualization() -> Visualization:
    return Visualization.model_validate({
        **header(),
        "agvPosition": {"x": 1.0, "y": 2.0, "theta": 0.0, "mapId": "map",
                        "positionInitialized": True},
    })
