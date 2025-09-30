from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, confloat, conint

from .base import BaseMessage, BoundingBoxReference, BlockingType, LoadDimensions


class AgvKinematic(Enum):
    DIFF = 'DIFF'
    OMNI = 'OMNI'
    THREEWHEEL = 'THREEWHEEL'


class AgvClass(Enum):
    FORKLIFT = 'FORKLIFT'
    CONVEYOR = 'CONVEYOR'
    TUGGER = 'TUGGER'
    CARRIER = 'CARRIER'


class LocalizationType(Enum):
    NATURAL = 'NATURAL'
    REFLECTOR = 'REFLECTOR'
    RFID = 'RFID'
    DMC = 'DMC'
    SPOT = 'SPOT'
    GRID = 'GRID'


class NavigationType(Enum):
    PHYSICAL_LINE_GUIDED = 'PHYSICAL_LINE_GUIDED'
    VIRTUAL_LINE_GUIDED = 'VIRTUAL_LINE_GUIDED'
    AUTONOMOUS = 'AUTONOMOUS'


class TypeSpecification(BaseModel):
    seriesName: str = Field(
        ...,
        description='Free text generalized series name as specified by manufacturer',
    )
    seriesDescription: Optional[str] = Field(
        None, description='Free text human readable description of the AGV type series'
    )
    agvKinematic: AgvKinematic = Field(
        ..., description='simplified description of AGV kinematics-type.'
    )
    agvClass: AgvClass = Field(..., description='Simplified description of AGV class.')
    maxLoadMass: confloat(ge=0.0) = Field(..., description='maximum loadable mass')
    localizationTypes: List[LocalizationType] = Field(
        ..., description='simplified description of localization type'
    )
    navigationTypes: List[NavigationType] = Field(
        ...,
        description='List of path planning types supported by the AGV, sorted by priority',
    )


class PhysicalParameters(BaseModel):
    speedMin: float = Field(
        ..., description='minimal controlled continuous speed of the AGV'
    )
    speedMax: float = Field(..., description='maximum speed of the AGV')
    accelerationMax: float = Field(
        ..., description='maximum acceleration with maximum load'
    )
    decelerationMax: float = Field(
        ..., description='maximum deceleration with maximum load'
    )
    heightMin: Optional[float] = Field(None, description='minimum height of AGV')
    heightMax: float = Field(..., description='maximum height of AGV')
    width: float = Field(..., description='width of AGV')
    length: float = Field(..., description='length of AGV')


class MaxStringLens(BaseModel):
    msgLen: Optional[int] = Field(None, description='maximum MQTT Message length')
    topicSerialLen: Optional[int] = Field(
        None,
        description='maximum length of serial-number part in MQTT-topics. Affected Parameters: order.serialNumber, instantActions.serialNumber, state.SerialNumber, visualization.serialNumber, connection.serialNumber',
    )
    topicElemLen: Optional[int] = Field(
        None,
        description='maximum length of all other parts in MQTT-topics. Affected parameters: order.timestamp, order.version, order.manufacturer, instantActions.timestamp, instantActions.version, instantActions.manufacturer, state.timestamp, state.version, state.manufacturer, visualization.timestamp, visualization.version, visualization.manufacturer, connection.timestamp, connection.version, connection.manufacturer',
    )
    idLen: Optional[int] = Field(
        None,
        description='maximum length of ID-Strings. Affected parameters: order.orderId, order.zoneSetId, node.nodeId, nodePosition.mapId, action.actionId, edge.edgeId, edge.startNodeId, edge.endNodeId',
    )
    idNumericalOnly: Optional[bool] = Field(
        None, description='If true ID-strings need to contain numerical values only'
    )
    enumLen: Optional[int] = Field(
        None,
        description='maximum length of ENUM- and Key-Strings. Affected parameters: action.actionType, action.blockingType, edge.direction, actionParameter.key, state.operatingMode, load.loadPosition, load.loadType, actionState.actionStatus, error.errorType, error.errorLevel, errorReference.referenceKey, info.infoType, info.infoLevel, safetyState.eStop, connection.connectionState',
    )
    loadIdLen: Optional[int] = Field(
        None, description='maximum length of loadId Strings'
    )


class MaxArrayLens(BaseModel):
    order_nodes: Optional[int] = Field(
        None,
        alias='order.nodes',
        description='maximum number of nodes per order processable by the AGV',
    )
    order_edges: Optional[int] = Field(
        None,
        alias='order.edges',
        description='maximum number of edges per order processable by the AGV',
    )
    node_actions: Optional[int] = Field(
        None,
        alias='node.actions',
        description='maximum number of actions per node processable by the AGV',
    )
    edge_actions: Optional[int] = Field(
        None,
        alias='edge.actions',
        description='maximum number of actions per edge processable by the AGV',
    )
    actions_actionsParameters: Optional[int] = Field(
        None,
        alias='actions.actionsParameters',
        description='maximum number of parameters per action processable by the AGV',
    )
    instantActions: Optional[int] = Field(
        None,
        description='maximum number of instant actions per message processable by the AGV',
    )
    trajectory_knotVector: Optional[int] = Field(
        None,
        alias='trajectory.knotVector',
        description='maximum number of knots per trajectory processable by the AGV',
    )
    trajectory_controlPoints: Optional[int] = Field(
        None,
        alias='trajectory.controlPoints',
        description='maximum number of control points per trajectory processable by the AGV',
    )
    state_nodeStates: Optional[int] = Field(
        None,
        alias='state.nodeStates',
        description='maximum number of nodeStates sent by the AGV, maximum number of nodes in base of AGV',
    )
    state_edgeStates: Optional[int] = Field(
        None,
        alias='state.edgeStates',
        description='maximum number of edgeStates sent by the AGV, maximum number of edges in base of AGV',
    )
    state_loads: Optional[int] = Field(
        None,
        alias='state.loads',
        description='maximum number of load-objects sent by the AGV',
    )
    state_actionStates: Optional[int] = Field(
        None,
        alias='state.actionStates',
        description='maximum number of actionStates sent by the AGV',
    )
    state_errors: Optional[int] = Field(
        None,
        alias='state.errors',
        description='maximum number of errors sent by the AGV in one state-message',
    )
    state_information: Optional[int] = Field(
        None,
        alias='state.information',
        description='maximum number of information objects sent by the AGV in one state-message',
    )
    error_errorReferences: Optional[int] = Field(
        None,
        alias='error.errorReferences',
        description='maximum number of error references sent by the AGV for each error',
    )
    information_infoReferences: Optional[int] = Field(
        None,
        alias='information.infoReferences',
        description='maximum number of info references sent by the AGV for each information',
    )


class Timing(BaseModel):
    minOrderInterval: float = Field(
        ..., description='minimum interval sending order messages to the AGV'
    )
    minStateInterval: float = Field(
        ..., description='minimum interval for sending state-messages'
    )
    defaultStateInterval: Optional[float] = Field(
        None,
        description='default interval for sending state-messages if not defined, the default value from the main document is used',
    )
    visualizationInterval: Optional[float] = Field(
        None, description='default interval for sending messages on visualization topic'
    )


class ProtocolLimits(BaseModel):
    maxStringLens: MaxStringLens = Field(..., description='maximum lengths of strings')
    maxArrayLens: MaxArrayLens = Field(..., description='maximum lengths of arrays')
    timing: Timing = Field(..., description='timing information')


class Support(Enum):
    SUPPORTED = 'SUPPORTED'
    REQUIRED = 'REQUIRED'


class OptionalParameter(BaseModel):
    parameter: str = Field(
        ...,
        description='full name of optional parameter, e.g. “order.nodes.nodePosition.allowedDeviationTheta”',
    )
    support: Support = Field(
        ...,
        description='type of support for the optional parameter, the following values are possible: SUPPORTED: optional parameter is supported like specified. REQUIRED: optional parameter is required for proper AGV-operation.',
    )
    description: Optional[str] = Field(
        None,
        description='free text. Description of optional parameter. E.g. Reason, why the optional parameter ‚direction‘ is necessary for this AGV-type and which values it can contain. The parameter ‘nodeMarker’ must contain unsigned interger-numbers only. Nurbs-Support is limited to straight lines and circle segments.',
    )


class ActionScope(Enum):
    INSTANT = 'INSTANT'
    NODE = 'NODE'
    EDGE = 'EDGE'


class ValueDataType(Enum):
    BOOL = 'BOOL'
    NUMBER = 'NUMBER'
    INTEGER = 'INTEGER'
    FLOAT = 'FLOAT'
    STRING = 'STRING'
    OBJECT = 'OBJECT'
    ARRAY = 'ARRAY'


class ActionParameter(BaseModel):
    key: str = Field(..., description='key-String for Parameter')
    valueDataType: ValueDataType = Field(
        ...,
        description='data type of Value, possible data types are: BOOL, NUMBER, INTEGER, FLOAT, STRING, OBJECT, ARRAY',
    )
    description: Optional[str] = Field(
        None, description='free text: description of the parameter'
    )
    isOptional: Optional[bool] = Field(None, description='True: optional parameter')




class AgvAction(BaseModel):
    actionType: str = Field(
        ..., description='unique actionType corresponding to action.actionType'
    )
    actionDescription: Optional[str] = Field(
        None, description='free text: description of the action'
    )
    actionScopes: List[ActionScope] = Field(
        ...,
        description='list of allowed scopes for using this action-type. INSTANT: usable as instantAction, NODE: usable on nodes, EDGE: usable on edges.',
    )
    actionParameters: Optional[List[ActionParameter]] = Field(
        None,
        description='list of parameters. if not defined, the action has no parameters',
    )
    resultDescription: Optional[str] = Field(
        None, description='free text: description of the resultDescription'
    )
    blockingTypes: Optional[List[BlockingType]] = Field(
        None, description='Array of possible blocking types for defined action.'
    )


class ProtocolFeatures(BaseModel):
    optionalParameters: List[OptionalParameter] = Field(
        ...,
        description='list of supported and/or required optional parameters. Optional parameters, that are not listed here, are assumed to be not supported by the AGV.',
    )
    agvActions: List[AgvAction] = Field(
        ...,
        description='list of all actions with parameters supported by this AGV. This includes standard actions specified in VDA5050 and manufacturer-specific actions',
    )


class Type(Enum):
    DRIVE = 'DRIVE'
    CASTER = 'CASTER'
    FIXED = 'FIXED'
    MECANUM = 'MECANUM'


class Position(BaseModel):
    x: float = Field(..., description='[m] x-position in AGV-coordinate system')
    y: float = Field(..., description='y-position in AGV-coordinate system')
    theta: Optional[float] = Field(
        None,
        description='orientation of wheel in AGV-coordinate system Necessary for fixed wheels',
    )


class WheelDefinition(BaseModel):
    type: Type = Field(..., description='wheel type. DRIVE, CASTER, FIXED, MECANUM')
    isActiveDriven: bool = Field(
        ..., description='True: wheel is actively driven (de: angetrieben)'
    )
    isActiveSteered: bool = Field(
        ..., description='True: wheel is actively steered (de: aktiv gelenkt)'
    )
    position: Position
    diameter: float = Field(..., description='nominal diameter of wheel')
    width: float = Field(..., description='nominal width of wheel')
    centerDisplacement: Optional[float] = Field(
        None,
        description='nominal displacement of the wheel’s center to the rotation point (necessary for caster wheels). If the parameter is not defined, it is assumed to be 0',
    )
    constraints: Optional[str] = Field(
        None,
        description='free text: can be used by the manufacturer to define constraints',
    )


class PolygonPoint(BaseModel):
    x: float = Field(..., description='x-position of polygon-point')
    y: float = Field(..., description=' y-position of polygon-point')


class Envelopes2dItem(BaseModel):
    set: str = Field(..., description='name of the envelope curve set')
    polygonPoints: List[PolygonPoint] = Field(
        ...,
        description='envelope curve as a x/y-polygon polygon is assumed as closed and must be non-self-intersecting',
    )
    description: Optional[str] = Field(
        None, description='free text: description of envelope curve set'
    )


class Envelopes3dItem(BaseModel):
    set: str = Field(..., description='name of the envelope curve set')
    format: str = Field(..., description='format of data e.g. DXF')
    data: Optional[Dict[str, Any]] = Field(
        None, description='3D-envelope curve data, format specified in ‚format‘'
    )
    url: Optional[str] = Field(
        None,
        description='protocol and url-definition for downloading the 3D-envelope curve data e.g. ftp://xxx.yyy.com/ac4dgvhoif5tghji',
    )
    description: Optional[str] = Field(
        None, description='free text: description of envelope curve set'
    )


class AgvGeometry(BaseModel):
    wheelDefinitions: Optional[List[WheelDefinition]] = Field(
        None, description='list of wheels, containing wheel-arrangement and geometry'
    )
    envelopes2d: Optional[List[Envelopes2dItem]] = None
    envelopes3d: Optional[List[Envelopes3dItem]] = Field(
        None, description='list of AGV-envelope curves in 3D (german: „Hüllkurven“)'
    )




class LoadSet(BaseModel):
    setName: str = Field(
        ..., description='Unique name of the load set, e.g. DEFAULT, SET1, ...'
    )
    loadType: str = Field(..., description='type of load e.g. EPAL, XLT1200, ….')
    loadPositions: Optional[List[str]] = Field(
        None,
        description='list of load positions btw. load handling devices, this load-set is valid for. If this parameter does not exist or is empty, this load-set is valid for all load handling devices on this AGV.',
    )
    boundingBoxReference: Optional[BoundingBoxReference] = Field(
        None,
        description='bounding box reference as defined in parameter loads[] in state-message',
    )
    loadDimensions: Optional[LoadDimensions] = None
    maxWeight: Optional[float] = Field(None, description='maximum weight of loadtype')
    minLoadhandlingHeight: Optional[float] = Field(
        None,
        description='minimum allowed height for handling of this load-type and –weight. References to boundingBoxReference',
    )
    maxLoadhandlingHeight: Optional[float] = Field(
        None,
        description='maximum allowed height for handling of this load-type and –weight. references to boundingBoxReference',
    )
    minLoadhandlingDepth: Optional[float] = Field(
        None,
        description='minimum allowed depth for this load-type and –weight. references to boundingBoxReference',
    )
    maxLoadhandlingDepth: Optional[float] = Field(
        None,
        description='maximum allowed depth for this load-type and –weight. references to boundingBoxReference',
    )
    minLoadhandlingTilt: Optional[float] = Field(
        None, description='minimum allowed tilt for this load-type and –weight'
    )
    maxLoadhandlingTilt: Optional[float] = Field(
        None, description='maximum allowed tilt for this load-type and –weight'
    )
    agvSpeedLimit: Optional[float] = Field(
        None, description='maximum allowed speed for this load-type and –weight'
    )
    agvAccelerationLimit: Optional[float] = Field(
        None, description='maximum allowed acceleration for this load-type and –weight'
    )
    agvDecelerationLimit: Optional[float] = Field(
        None, description='maximum allowed deceleration for this load-type and –weight'
    )
    pickTime: Optional[float] = Field(
        None, description='approx. time for picking up the load'
    )
    dropTime: Optional[float] = Field(
        None, description='approx. time for dropping the load'
    )
    description: Optional[str] = Field(
        None, description='free text description of the load handling set'
    )


class LoadSpecification(BaseModel):
    loadPositions: Optional[List[str]] = Field(
        None,
        description='list of load positions / load handling devices. This lists contains the valid values for the parameter “state.loads[].loadPosition” and for the action parameter “lhd” of the actions pick and drop. If this list doesn’t exist or is empty, the AGV has no load handling device.',
    )
    loadSets: Optional[List[LoadSet]] = Field(
        None, description='list of load-sets that can be handled by the AGV'
    )


class Version(BaseModel):
    key: str = Field(
        ...,
        description='The key of the version.',
        examples=['softwareVersion', 'cameraVersion', 'plcSoftChecksum'],
    )
    value: str = Field(
        ...,
        description='The value of the action parameter.',
        examples=['v1.03.2', '0620NL51805A0', '0x4297F30C'],
    )


class Network(BaseModel):
    dnsServers: Optional[List[str]] = Field(
        None, description='List of DNS servers used by the vehicle.'
    )
    localIpAddress: Optional[str] = Field(
        None,
        description='A priori assigned IP address of the vehicle used to communicate with the MQTT broker. Note that this IP address should not be modified/changed during operations.',
    )
    ntpServers: Optional[List[str]] = Field(
        None, description='List of NTP servers used by the vehicle.'
    )
    netmask: Optional[str] = Field(None, description='Network subnet mask.')
    defaultGateway: Optional[str] = Field(
        None, description='Default gateway used by the vehicle.'
    )


class VehicleConfig(BaseModel):
    versions: Optional[List[Version]] = Field(
        None,
        description='Array containing various hardware and software versions running on the vehicle.',
    )
    network: Optional[Network] = None


class AgvFactsheet(BaseMessage):
    typeSpecification: TypeSpecification = Field(
        ...,
        description='These parameters generally specify the class and the capabilities of the AGV',
    )
    physicalParameters: PhysicalParameters = Field(
        ...,
        description='These parameters specify the basic physical properties of the AGV',
    )
    protocolLimits: ProtocolLimits = Field(
        ...,
        description='This JSON-object describes the protocol limitations of the AGV. If a parameter is not defined or set to zero then there is no explicit limit for this parameter.',
    )
    protocolFeatures: ProtocolFeatures = Field(
        ..., description='Supported features of VDA5050 protocol'
    )
    agvGeometry: AgvGeometry = Field(
        ..., description='Detailed definition of AGV geometry'
    )
    loadSpecification: LoadSpecification = Field(
        ..., description='Abstract specification of load capabilities'
    )
    vehicleConfig: Optional[VehicleConfig] = None
