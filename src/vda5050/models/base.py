from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, confloat, conint


class BaseMessage(BaseModel):
    """
    Base message class containing common header fields for all VDA5050 message types.
    
    This abstract base class provides the standard header structure that appears in all
    VDA5050 protocol messages. All message types inherit from this class to ensure
    consistency across the protocol.
    
    The header contains essential metadata for message identification, timing, and
    protocol versioning that is required for proper message routing and processing.
    
    Used by all VDA5050 message types:
    - Connection: AGV connection status messages
    - Factsheet: AGV capability and configuration messages  
    - InstantActions: Immediate action execution messages
    - Order: Planned mission and navigation messages
    - State: Current AGV status and state messages
    - Visualization: Real-time position and velocity messages
    
    Attributes:
        headerId: Unique message identifier within the topic, incremented per message
        timestamp: ISO8601 formatted timestamp of message creation
        version: VDA5050 protocol version in semver format (Major.Minor.Patch)
        manufacturer: Name of the AGV manufacturer
        serialNumber: Unique identifier of the specific AGV instance
    """
    headerId: int = Field(
        ...,
        description='Header ID of the message. The headerId is defined per topic and incremented by 1 with each sent (but not necessarily received) message.',
    )
    timestamp: datetime = Field(
        ...,
        description='Timestamp in ISO8601 format (YYYY-MM-DDTHH:mm:ss.ssZ).',
        examples=['1991-03-11T11:40:03.12Z'],
    )
    version: str = Field(
        ...,
        description='Version of the protocol [Major].[Minor].[Patch]',
        examples=['1.3.2'],
    )
    manufacturer: str = Field(..., description='Manufacturer of the AGV.')
    serialNumber: str = Field(..., description='Serial number of the AGV.')
    
    def to_mqtt_payload(self) -> str:
        """
        Convert the message to a JSON payload for MQTT.
        """
        return self.model_dump_json(exclude_none=True)
    
    @classmethod
    def from_mqtt_payload(cls, payload: str):
        """
        Create a message from a JSON payload received from MQTT.
        """
        return cls.model_validate_json(payload)


class BlockingType(Enum):
    """
    Enum defining the blocking behavior of an action during execution.
    
    This determines whether an action can be executed in parallel with other actions
    or if it requires exclusive execution. Used in both Order and InstantActions messages.
    
    Values:
        NONE: Action can happen in parallel with others, including movement
        SOFT: Action can happen simultaneously with others, but not while moving
        HARD: No other actions can be performed while this action is running
    """
    NONE = 'NONE'
    SOFT = 'SOFT'
    HARD = 'HARD'


class ActionParameter(BaseModel):
    """
    Parameter object for actions, containing key-value pairs.
    
    This class represents individual parameters that can be passed to an action
    to customize its behavior. Used in both Order and InstantActions messages.
    
    Attributes:
        key: The parameter name/identifier
        value: The parameter value (can be various types: string, number, boolean, array, object)
    """
    key: str = Field(
        ...,
        description='The key of the action parameter.',
        examples=['duration', 'direction', 'signal'],
    )
    value: Union[List[Any], bool, float, str, Dict[str, Any]] = Field(
        ...,
        description='The value of the action parameter',
        examples=[103.2, 'left', True, ['arrays', 'are', 'also', 'valid']],
    )


class Action(BaseModel):
    """
    Represents an action that the AGV can perform.
    
    This is the core action definition used in both Order messages (for planned actions
    on nodes/edges) and InstantActions messages (for immediate execution). Each action
    has a unique ID for tracking and can contain multiple parameters.
    
    Attributes:
        actionType: Identifies the function/type of the action (e.g., 'pick', 'drop', 'customAction')
        actionId: Unique identifier for tracking this specific action instance
        actionDescription: Optional human-readable description
        blockingType: Determines execution behavior relative to other actions
        actionParameters: Optional list of parameters to customize the action
    """
    actionType: str = Field(
        ...,
        description='Name of action as described in the first column of "Actions and Parameters". Identifies the function of the action.',
    )
    actionId: str = Field(
        ...,
        description='Unique ID to identify the action and map them to the actionState in the state. Suggestion: Use UUIDs.',
    )
    actionDescription: Optional[str] = Field(
        None, description='Additional information on the action.'
    )
    blockingType: BlockingType = Field(
        ...,
        description='Regulates if the action is allowed to be executed during movement and/or parallel to other actions.\nnone: action can happen in parallel with others, including movement.\nsoft: action can happen simultaneously with others, but not while moving.\nhard: no other actions can be performed while this action is running.',
    )
    actionParameters: Optional[List[ActionParameter]] = Field(
        None,
        description='Array of actionParameter-objects for the indicated action e. g. deviceId, loadId, external Triggers.',
    )


class ControlPoint(BaseModel):
    """
    Control point for NURBS trajectory definition.
    
    Represents a single control point in a NURBS (Non-Uniform Rational B-Spline) curve
    that defines the trajectory path for AGV movement. Used in both Order messages
    (for planned trajectories) and State messages (for executed trajectories).
    
    Attributes:
        x: X coordinate in the world coordinate system (meters)
        y: Y coordinate in the world coordinate system (meters)
        weight: Weight factor influencing the curve shape (default: 1.0)
    """
    x: float = Field(
        ..., description='X coordinate described in the world coordinate system.'
    )
    y: float = Field(
        ..., description='Y coordinate described in the world coordinate system.'
    )
    weight: Optional[confloat(ge=0.0)] = Field(
        None,
        description='The weight, with which this control point pulls on the curve. When not defined, the default will be 1.0.',
    )


class Trajectory(BaseModel):
    """
    NURBS trajectory definition for AGV path planning.
    
    Defines a smooth curved path using Non-Uniform Rational B-Splines (NURBS)
    for precise AGV movement between nodes. This provides more natural and
    efficient paths compared to straight-line segments.
    
    Used in both Order messages (for planned trajectories on edges) and State
    messages (for actual executed trajectory segments).
    
    Attributes:
        degree: Number of control points that influence any given point on the curve
        knotVector: Parameter values determining how control points affect the curve
        controlPoints: List of control points defining the curve shape and path
    """
    degree: conint(ge=1) = Field(
        ...,
        description='Defines the number of control points that influence any given point on the curve. Increasing the degree increases continuity. If not defined, the default value is 1.',
    )
    knotVector: List[confloat(ge=0.0, le=1.0)] = Field(
        ...,
        description='Sequence of parameter values that determines where and how the control points affect the NURBS curve. knotVector has size of number of control points + degree + 1.',
    )
    controlPoints: List[ControlPoint] = Field(
        ...,
        description='List of JSON controlPoint objects defining the control points of the NURBS, which includes the beginning and end point.',
    )


class AgvPosition(BaseModel):
    """
    AGV position information in world coordinates.
    
    Represents the current or planned position of the AGV on a map using world coordinates.
    Used in both State messages (for current position reporting) and Visualization messages
    (for real-time position display).
    
    Attributes:
        x: X coordinate in the world coordinate system (meters)
        y: Y coordinate in the world coordinate system (meters)
        theta: Orientation angle in radians
        mapId: Unique identifier of the map containing this position
        mapDescription: Optional description of the map
        positionInitialized: Whether the position has been properly initialized
        localizationScore: Quality of localization (0.0-1.0, optional)
        deviationRange: Position uncertainty range in meters (optional)
    """
    x: float
    y: float
    theta: float
    mapId: str
    mapDescription: Optional[str] = None
    positionInitialized: bool = Field(
        ...,
        description='True: position is initialized. False: position is not initizalized.',
    )
    localizationScore: Optional[confloat(ge=0.0, le=1.0)] = Field(
        None,
        description='Describes the quality of the localization and therefore, can be used, e.g., by SLAM-AGV to describe how accurate the current position information is.\n0.0: position unknown\n1.0: position known\nOptional for vehicles that cannot estimate their localization score.\nOnly for logging and visualization purposes',
    )
    deviationRange: Optional[float] = Field(
        None,
        description='Value for position deviation range in meters. Optional for vehicles that cannot estimate their deviation, e.g., grid-based localization. Only for logging and visualization purposes.',
    )


class Velocity(BaseModel):
    """
    AGV velocity in vehicle coordinate system.
    
    Represents the current velocity of the AGV in its own coordinate system.
    Used in both State messages (for velocity reporting) and Visualization messages
    (for real-time velocity display).
    
    Attributes:
        vx: Velocity in the AGV's x direction (m/s)
        vy: Velocity in the AGV's y direction (m/s)
        omega: Angular velocity around the AGV's z axis (rad/s)
    """
    vx: Optional[float] = Field(
        None, description='The AVGs velocity in its x direction'
    )
    vy: Optional[float] = Field(
        None, description='The AVGs velocity in its y direction'
    )
    omega: Optional[float] = Field(
        None, description='The AVGs turning speed around its z axis.'
    )


class BoundingBoxReference(BaseModel):
    """
    Reference point for load bounding box in AGV coordinate system.
    
    Defines the reference point for positioning a load's bounding box relative to the AGV.
    The reference point is always the center of the bounding box bottom surface (at height = 0)
    and is described in coordinates of the AGV coordinate system.
    
    Used in both State messages (for current load positioning) and Factsheet messages
    (for load capability specification).
    
    Attributes:
        x: X coordinate of the reference point in AGV coordinate system (meters)
        y: Y coordinate of the reference point in AGV coordinate system (meters)
        z: Z coordinate of the reference point in AGV coordinate system (meters)
        theta: Optional orientation of the load's bounding box (radians)
    """
    x: float
    y: float
    z: float
    theta: Optional[float] = Field(
        None,
        description='Orientation of the loads bounding box. Important for tugger, trains, etc.',
    )


class LoadDimensions(BaseModel):
    """
    Dimensions of a load's bounding box.
    
    Specifies the physical dimensions of a load that the AGV can carry.
    Used in both State messages (for current load reporting) and Factsheet messages
    (for load capability specification).
    
    Attributes:
        length: Absolute length of the load's bounding box (meters)
        width: Absolute width of the load's bounding box (meters)
        height: Optional absolute height of the load's bounding box (meters)
    """
    length: float = Field(
        ..., description='Absolute length of the loads bounding box in meter.'
    )
    width: float = Field(
        ..., description='Absolute width of the loads bounding box in meter.'
    )
    height: Optional[float] = Field(
        None,
        description='Absolute height of the loads bounding box in meter.\nOptional:\nSet value only if known.',
    )
