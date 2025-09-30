from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, confloat, conint

from .base import Action, ActionParameter, VDA5050Message, BlockingType, ControlPoint, Trajectory


class NodePosition(BaseModel):
    x: float = Field(
        ...,
        description='X-position on the map in reference to the map coordinate system. Precision is up to the specific implementation.',
    )
    y: float = Field(
        ...,
        description='Y-position on the map in reference to the map coordinate system. Precision is up to the specific implementation.',
    )
    theta: Optional[confloat(ge=-3.14159265359, le=3.14159265359)] = Field(
        None,
        description='Absolute orientation of the AGV on the node. \nOptional: vehicle can plan the path by itself.\nIf defined, the AGV has to assume the theta angle on this node. If previous edge disallows rotation, the AGV must rotate on the node. If following edge has a differing orientation defined but disallows rotation, the AGV is to rotate on the node to the edges desired rotation before entering the edge.',
    )
    allowedDeviationXY: Optional[confloat(ge=0.0)] = Field(
        None,
        description='Indicates how exact an AGV has to drive over a node in order for it to count as traversed.\nIf = 0: no deviation is allowed (no deviation means within the normal tolerance of the AGV manufacturer).\nIf > 0: allowed deviation-radius in meters. If the AGV passes a node within the deviation-radius, the node is considered to have been traversed.',
    )
    allowedDeviationTheta: Optional[confloat(ge=0.0, le=3.141592654)] = Field(
        None,
        description='Indicates how big the deviation of theta angle can be. \nThe lowest acceptable angle is theta - allowedDeviationTheta and the highest acceptable angle is theta + allowedDeviationTheta.',
    )
    mapId: str = Field(
        ...,
        description='Unique identification of the map in which the position is referenced.\nEach map has the same origin of coordinates. When an AGV uses an elevator, e.g., leading from a departure floor to a target floor, it will disappear off the map of the departure floor and spawn in the related lift node on the map of the target floor.',
    )
    mapDescription: Optional[str] = Field(
        None, description='Additional information on the map.'
    )




class CorridorRefPoint(Enum):
    KINEMATICCENTER = 'KINEMATICCENTER'
    CONTOUR = 'CONTOUR'


class Corridor(BaseModel):
    leftWidth: confloat(ge=0.0) = Field(
        ...,
        description='Defines the width of the corridor in meters to the left related to the trajectory of the vehicle.',
    )
    rightWidth: confloat(ge=0.0) = Field(
        ...,
        description='Defines the width of the corridor in meters to the right related to the trajectory of the vehicle.',
    )
    corridorRefPoint: Optional[CorridorRefPoint] = Field(
        None,
        description='Defines whether the boundaries are valid for the kinematic center or the contour of the vehicle.',
    )




class Node(BaseModel):
    nodeId: str = Field(
        ...,
        description='Unique node identification',
        examples=['pumpenhaus_1', 'MONTAGE'],
    )
    sequenceId: conint(ge=0) = Field(
        ...,
        description='Number to track the sequence of nodes and edges in an order and to simplify order updates.\nThe main purpose is to distinguish between a node which is passed more than once within one orderId. The variable sequenceId runs across all nodes and edges of the same order and is reset when a new orderId is issued.',
    )
    nodeDescription: Optional[str] = Field(
        None, description='Additional information on the node.'
    )
    released: bool = Field(
        ...,
        description='True indicates that the node is part of the base. False indicates that the node is part of the horizon.',
    )
    nodePosition: Optional[NodePosition] = Field(
        None,
        description='Defines the position on a map in world coordinates. Each floor has its own map. All maps must use the same project specific global origin. \nOptional for vehicle-types that do not require the node position (e.g., line-guided vehicles).',
    )
    actions: List[Action] = Field(
        ...,
        description='Array of actions to be executed on a node. Empty array, if no actions required.',
    )


class Edge(BaseModel):
    edgeId: str = Field(..., description='Unique edge identification')
    sequenceId: conint(ge=0) = Field(
        ...,
        description='Number to track the sequence of nodes and edges in an order and to simplify order updates. The variable sequenceId runs across all nodes and edges of the same order and is reset when a new orderId is issued.',
    )
    edgeDescription: Optional[str] = Field(
        None, description='Additional information on the edge.'
    )
    released: bool = Field(
        ...,
        description='True indicates that the edge is part of the base. False indicates that the edge is part of the horizon.',
    )
    startNodeId: str = Field(..., description='The nodeId of the start node.')
    endNodeId: str = Field(..., description='The nodeId of the end node.')
    maxSpeed: Optional[float] = Field(
        None,
        description='Permitted maximum speed on the edge in m/s. Speed is defined by the fastest measurement of the vehicle.',
    )
    maxHeight: Optional[float] = Field(
        None,
        description='Permitted maximum height of the vehicle, including the load, on edge in meters.',
    )
    minHeight: Optional[float] = Field(
        None,
        description='Permitted minimal height of the load handling device on the edge in meters',
    )
    orientation: Optional[confloat(ge=-3.14159265359, le=3.14159265359)] = Field(
        None,
        description='Orientation of the AGV on the edge. The value orientationType defines if it has to be interpreted relative to the global project specific map coordinate system or tangential to the edge. In case of interpreted tangential to the edge 0.0 = forwards and PI = backwards. Example: orientation Pi/2 rad will lead to a rotation of 90 degrees. \nIf AGV starts in different orientation, rotate the vehicle on the edge to the desired orientation if rotationAllowed is set to True. If rotationAllowed is False, rotate before entering the edge. If that is not possible, reject the order. \nIf no trajectory is defined, apply the rotation to the direct path between the two connecting nodes of the edge. If a trajectory is defined for the edge, apply the orientation to the trajectory.',
    )
    orientationType: Optional[str] = Field(
        None,
        description='Enum {GLOBAL, TANGENTIAL}: \n"GLOBAL"- relative to the global project specific map coordinate system; \n"TANGENTIAL"- tangential to the edge. \nIf not defined, the default value is "TANGENTIAL".',
    )
    direction: Optional[str] = Field(
        None,
        description='Sets direction at junctions for line-guided or wire-guided vehicles, to be defined initially (vehicle-individual).',
    )
    rotationAllowed: Optional[bool] = Field(
        None,
        description='True: rotation is allowed on the edge. False: rotation is not allowed on the edge. \nOptional: No limit, if not set.',
    )
    maxRotationSpeed: Optional[float] = Field(
        None,
        description='Maximum rotation speed in rad/s. \nOptional: No limit, if not set.',
    )
    length: Optional[float] = Field(
        None,
        description='Distance of the path from startNode to endNode in meters. \nOptional: This value is used by line-guided AGVs to decrease their speed before reaching a stop position.',
    )
    trajectory: Optional[Trajectory] = Field(
        None,
        description='Trajectory JSON-object for this edge as a NURBS. Defines the curve, on which the AGV should move between startNode and endNode. \nOptional: Can be omitted, if AGV cannot process trajectories or if AGV plans its own trajectory.',
    )
    corridor: Optional[Corridor] = Field(
        None,
        description='Definition of boundaries in which a vehicle can deviate from its trajectory, e. g. to avoid obstacles.',
    )
    actions: List[Action] = Field(
        ..., description='Array of action objects with detailed information.'
    )


class OrderMessage(VDA5050Message):
    orderId: str = Field(
        ...,
        description='Order Identification. This is to be used to identify multiple order messages that belong to the same order.',
    )
    orderUpdateId: conint(ge=0) = Field(
        ...,
        description='orderUpdate identification. Is unique per orderId. If an order update is rejected, this field is to be passed in the rejection message.',
    )
    zoneSetId: Optional[str] = Field(
        None,
        description='Unique identifier of the zone set that the AGV has to use for navigation or that was used by MC for planning.\nOptional: Some MC systems do not use zones. Some AGVs do not understand zones. Do not add to message if no zones are used.',
    )
    nodes: List[Node] = Field(
        ...,
        description='Array of nodes objects to be traversed for fulfilling the order. One node is enough for a valid order. Leave edge list empty for that case.',
    )
    edges: List[Edge] = Field(
        ...,
        description='Directional connection between two nodes. Array of edge objects to be traversed for fulfilling the order. One node is enough for a valid order. Leave edge list empty for that case.',
    )
