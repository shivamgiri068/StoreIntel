from shapely.geometry import Point, Polygon
from app.config import ZONES

class ZoneManager:
    def __init__(self):
        self.zones = {}
        for name, data in ZONES.items():
            self.zones[name] = {
                "type": data["type"],
                "polygon": Polygon(data["polygon"]),
                "points": data["polygon"]
            }

    def get_zone_at_point(self, x, y) -> tuple[str, str]:
        """
        Returns (zone_name, zone_type) if point is inside any zone.
        Otherwise returns (None, None).
        """
        point = Point(x, y)
        for name, zone_data in self.zones.items():
            if zone_data["polygon"].contains(point):
                return name, zone_data["type"]
        return None, None

    def get_all_zones(self):
        return self.zones
