"""
Node Group Model
Represents a logical group of WireGuard nodes for organization and load balancing
"""
from datetime import datetime


class NodeGroup:
    def __init__(self, tableData):
        self.id = tableData.get("id")
        self.name = tableData.get("name")
        self.description = tableData.get("description")
        self.region = tableData.get("region")
        self.priority = tableData.get("priority", 0)
        self.created_at = tableData.get("created_at")
        self.updated_at = tableData.get("updated_at")

    def toJson(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "region": self.region,
            "priority": self.priority,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __repr__(self):
        return str(self.toJson())
