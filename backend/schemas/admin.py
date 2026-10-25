from typing import List, Optional

from schemas.common import Out


class IssueRow(Out):
    """A full issues-table row (every column passes through)."""
    id: str
    status: str
    category: Optional[str] = None
    building: Optional[str] = None
    priority: Optional[float] = None
    severity: Optional[int] = None


class Location(Out):
    building: str
    issues: List[IssueRow]


class CategoryGroup(Out):
    category: Optional[str] = None
    count: int
    locations: List[Location]


class FlaggedReport(Out):
    id: str
    image_path: Optional[str] = None
    ai_description: Optional[str] = None
    building: Optional[str] = None
    created_at: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    name: Optional[str] = None
    cusat_id: Optional[str] = None
    gps_flag: Optional[str] = None


class GroupedOut(Out):
    groups: List[CategoryGroup]
    top: List[IssueRow]
    flagged: List[FlaggedReport]


class HeatPoint(Out):
    id: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    priority: Optional[float] = None
    category: Optional[str] = None
    threat_level: Optional[str] = None
    status: str
    weight: float


class HeatmapOut(Out):
    points: List[HeatPoint]


class FixResult(Out):
    """Gemma's audit of a repair photo."""
    passed: bool
    same_location_verified: Optional[bool] = None
    resolved: Optional[bool] = None
    is_screen_or_reused: Optional[bool] = None
    reason: Optional[str] = None


class MarkFakeResult(Out):
    marked_fake: bool
    reason: Optional[str] = None
    same_location_verified: Optional[bool] = None
    problem_present: Optional[bool] = None
    is_screen_or_reused: Optional[bool] = None
