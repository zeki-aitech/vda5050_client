from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, confloat

from .base import AgvPosition, VDA5050Message, BoundingBoxReference, ControlPoint, LoadDimensions, Trajectory, Velocity


class MapStatus(Enum):
    ENABLED = 'ENABLED'
    DISABLED = 'DISABLED'


class Map(BaseModel):
    mapId: str = Field(
        ...,
        description="ID of the map describing a defined area of the vehicle's workspace.",
    )
    mapVersion: str = Field(..., description='Version of the map.')
    mapDescription: Optional[str] = Field(
        None, description='Additional information on the map.'
    )
    mapStatus: MapStatus = Field(
        ...,
        description='Information on the status of the map indicating, if a map version is currently used on the vehicle. ENABLED: Indicates this map is currently active / used on the AGV. At most one map with the same mapId can have its status set to ENABLED.<br>DISABLED: Indicates this map version is currently not enabled on the AGV and thus could be enabled or deleted by request.',
    )


class OperatingMode(Enum):
    AUTOMATIC = 'AUTOMATIC'
    SEMIAUTOMATIC = 'SEMIAUTOMATIC'
    MANUAL = 'MANUAL'
    SERVICE = 'SERVICE'
    TEACHIN = 'TEACHIN'


class NodePosition(BaseModel):
    x: float
    y: float
    theta: Optional[float] = None
    mapId: str


class NodeState(BaseModel):
    nodeId: str = Field(..., description='Unique node identification')
    sequenceId: int = Field(
        ..., description='sequenceId to discern multiple nodes with same nodeId.'
    )
    nodeDescription: Optional[str] = Field(
        None, description='Additional information on the node.'
    )
    released: bool = Field(
        ...,
        description='True: indicates that the node is part of the base. False: indicates that the node is part of the horizon.',
    )
    nodePosition: Optional[NodePosition] = Field(
        None,
        description='Node position. The object is defined in chapter 5.4 Topic: Order (from master control to AGV).\nOptional:Master control has this information. Can be sent additionally, e.g., for debugging purposes. ',
    )




class EdgeState(BaseModel):
    edgeId: str = Field(..., description='Unique edge identification')
    sequenceId: int = Field(..., description='sequenceId of the edge.')
    edgeDescription: Optional[str] = Field(
        None, description='Additional information on the edge.'
    )
    released: bool = Field(
        ...,
        description='True indicates that the edge is part of the base. False indicates that the edge is part of the horizon.',
    )
    trajectory: Optional[Trajectory] = Field(
        None,
        description='The trajectory is to be communicated as a NURBS and is defined in chapter 6.7 Implementation of the Order message.\nTrajectory segments reach from the point, where the AGV starts to enter the edge to the point where it reports that the next node was traversed. ',
    )






class Load(BaseModel):
    loadId: Optional[str] = Field(
        None,
        description='Unique identification number of the load (e.g., barcode or RFID). Empty field, if the AGV can identify the load, but did not identify the load yet. Optional, if the AGV cannot identify the load.',
    )
    loadType: Optional[str] = Field(None, description='Type of load.')
    loadPosition: Optional[str] = Field(
        None,
        description='Indicates, which load handling/carrying unit of the AGV is used, e.g., in case the AGV has multiple spots/positions to carry loads. Optional for vehicles with only one loadPosition.',
        examples=['front', 'back', 'positionC1'],
    )
    boundingBoxReference: Optional[BoundingBoxReference] = Field(
        None,
        description='Point of reference for the location of the bounding box. The point of reference is always the center of the bounding box bottom surface (at height = 0) and is described in coordinates of the AGV coordinate system.',
    )
    loadDimensions: Optional[LoadDimensions] = Field(
        None, description='Dimensions of the loads bounding box in meters.'
    )
    weight: Optional[confloat(ge=0.0)] = Field(
        None, description='Absolute weight of the load measured in kg.'
    )


class ActionStatus(Enum):
    WAITING = 'WAITING'
    INITIALIZING = 'INITIALIZING'
    RUNNING = 'RUNNING'
    PAUSED = 'PAUSED'
    FINISHED = 'FINISHED'
    FAILED = 'FAILED'


class ActionState(BaseModel):
    actionId: str = Field(
        ..., description='Unique actionId', examples=['blink_123jdaimoim234']
    )
    actionType: Optional[str] = Field(
        None,
        description='actionType of the action.\nOptional: Only for informational or visualization purposes. Order knows the type.',
    )
    actionDescription: Optional[str] = Field(
        None, description='Additional information on the current action.'
    )
    actionStatus: ActionStatus = Field(
        ...,
        description='WAITING: waiting for the trigger (passing the mode, entering the edge) PAUSED: paused by instantAction or external trigger FAILED: action could not be performed.',
    )
    resultDescription: Optional[str] = Field(
        None,
        description='Description of the result, e.g., the result of a RFID-read. Errors will be transmitted in errors.',
    )


class BatteryState(BaseModel):
    batteryCharge: float = Field(
        ...,
        description='State of Charge in %:\nIf AGV only provides values for good or bad battery levels, these will be indicated as 20% (bad) and 80% (good).',
    )
    batteryVoltage: Optional[float] = Field(None, description='Battery voltage')
    batteryHealth: Optional[confloat(ge=0.0, le=100.0)] = Field(
        None, description='State of health in percent.'
    )
    charging: bool = Field(
        ...,
        description='True: charging in progress. False: AGV is currently not charging.',
    )
    reach: Optional[confloat(ge=0.0)] = Field(
        None, description='Estimated reach with current State of Charge in meter.'
    )


class ErrorReference(BaseModel):
    referenceKey: str = Field(
        ...,
        description='Specifies the type of reference used (e.g. nodeId, edgeId, orderId, actionId, etc.).',
    )
    referenceValue: str = Field(
        ...,
        description='The value that belongs to the reference key. For example, the id of the node where the error occurred.',
    )


class ErrorLevel(Enum):
    WARNING = 'WARNING'
    FATAL = 'FATAL'


class Error(BaseModel):
    errorType: str = Field(..., description='Type/name of error.')
    errorReferences: Optional[List[ErrorReference]] = None
    errorDescription: Optional[str] = Field(
        None,
        description='Verbose description providing details and possible causes of the error.',
    )
    errorHint: Optional[str] = Field(
        None, description='Hint on how to approach or solve the reported error.'
    )
    errorLevel: ErrorLevel = Field(
        ...,
        description='WARNING: AGV is ready to start (e.g., maintenance cycle expiration warning). FATAL: AGV is not in running condition, user intervention required (e.g., laser scanner is contaminated).',
    )


class InfoReference(BaseModel):
    referenceKey: str = Field(
        ...,
        description='References the type of reference (e.g., headerId, orderId, actionId, etc.).',
    )
    referenceValue: str = Field(
        ..., description='References the value, which belongs to the reference key.'
    )


class InfoLevel(Enum):
    INFO = 'INFO'
    DEBUG = 'DEBUG'


class Information(BaseModel):
    infoType: str = Field(..., description='Type/name of information.')
    infoReferences: Optional[List[InfoReference]] = None
    infoDescription: Optional[str] = Field(None, description='Info of description.')
    infoLevel: InfoLevel = Field(
        ..., description='DEBUG: used for debugging. INFO: used for visualization.'
    )


class EStop(Enum):
    AUTOACK = 'AUTOACK'
    MANUAL = 'MANUAL'
    REMOTE = 'REMOTE'
    NONE = 'NONE'


class SafetyState(BaseModel):
    eStop: EStop = Field(
        ...,
        description='Acknowledge-Type of eStop: AUTOACK: auto-acknowledgeable e-stop is activated, e.g., by bumper or protective field. MANUAL: e-stop hast to be acknowledged manually at the vehicle. REMOTE: facility e-stop has to be acknowledged remotely. NONE: no e-stop activated.',
    )
    fieldViolation: bool = Field(
        ...,
        description='Protective field violation. True: field is violated. False: field is not violated.',
    )


class State(VDA5050Message):
    maps: Optional[List[Map]] = Field(
        None,
        description='Array of map-objects that are currently stored on the vehicle.',
    )
    orderId: str = Field(
        ...,
        description='Unique order identification of the current order or the previous finished order. The orderId is kept until a new order is received. Empty string ("") if no previous orderId is available. ',
    )
    orderUpdateId: int = Field(
        ...,
        description='Order Update Identification to identify that an order update has been accepted by the AGV. "0" if no previous orderUpdateId is available.',
    )
    zoneSetId: Optional[str] = Field(
        None,
        description='Unique ID of the zone set that the AGV currently uses for path planning. Must be the same as the one used in the order, otherwise the AGV is to reject the order.\nOptional: If the AGV does not use zones, this field can be omitted.',
    )
    lastNodeId: str = Field(
        ...,
        description='nodeID of last reached node or, if AGV is currently on a node, current node (e.g., "node7"). Empty string ("") if no lastNodeId is available.',
    )
    lastNodeSequenceId: int = Field(
        ...,
        description='sequenceId of the last reached node or, if the AGV is currently on a node, sequenceId of current node. "0" if no lastNodeSequenceId is available. ',
    )
    driving: bool = Field(
        ...,
        description='True: indicates that the AGV is driving and/or rotating. Other movements of the AGV (e.g., lift movements) are not included here.\nFalse: indicates that the AGV is neither driving nor rotating ',
    )
    paused: Optional[bool] = Field(
        None,
        description='True: AGV is currently in a paused state, either because of the push of a physical button on the AGV or because of an instantAction. The AGV can resume the order.\nFalse: The AGV is currently not in a paused state.',
    )
    newBaseRequest: Optional[bool] = Field(
        None,
        description='True: AGV is almost at the end of the base and will reduce speed if no new base is transmitted. Trigger for master control to send new base\nFalse: no base update required.',
    )
    distanceSinceLastNode: Optional[float] = Field(
        None,
        description='Used by line guided vehicles to indicate the distance it has been driving past the "lastNodeId".\nDistance is in meters.',
    )
    operatingMode: OperatingMode = Field(
        ..., description='Current operating mode of the AGV.'
    )
    nodeStates: List[NodeState] = Field(
        ...,
        description='Array of nodeState-Objects, that need to be traversed for fulfilling the order. Empty list if idle.',
    )
    edgeStates: List[EdgeState] = Field(
        ...,
        description='Array of edgeState-Objects, that need to be traversed for fulfilling the order, empty list if idle.',
    )
    agvPosition: Optional[AgvPosition] = Field(
        None,
        description='Defines the position on a map in world coordinates. Each floor has its own map.',
    )
    velocity: Optional[Velocity] = Field(
        None, description='The AGVs velocity in vehicle coordinates'
    )
    loads: Optional[List[Load]] = Field(
        None,
        description='Loads, that are currently handled by the AGV. Optional: If AGV cannot determine load state, leave the array out of the state. If the AGV can determine the load state, but the array is empty, the AGV is considered unloaded.',
    )
    actionStates: List[ActionState] = Field(
        ...,
        description='Contains a list of the current actions and the actions which are yet to be finished. This may include actions from previous nodes that are still in progress\nWhen an action is completed, an updated state message is published with actionStatus set to finished and if applicable with the corresponding resultDescription. The actionStates are kept until a new order is received.',
    )
    batteryState: BatteryState = Field(
        ..., description='Contains all battery-related information.'
    )
    errors: List[Error] = Field(
        ...,
        description='Array of error-objects. All active errors of the AGV should be in the list. An empty array indicates that the AGV has no active errors.',
    )
    information: Optional[List[Information]] = Field(
        None,
        description='Array of info-objects. An empty array indicates, that the AGV has no information. This should only be used for visualization or debugging – it must not be used for logic in master control.',
    )
    safetyState: SafetyState = Field(
        ..., description='Contains all safety-related information.'
    )
