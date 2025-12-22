"""
ConfigNode Model
Represents the assignment of a node to a WireGuard configuration (Phase 8)
"""
from datetime import datetime


class ConfigNode:
    def __init__(self, tableData):
        self.id = tableData.get("id")
        self.config_name = tableData.get("config_name")
        self.node_id = tableData.get("node_id")
        self.is_healthy = tableData.get("is_healthy", True)
        self.created_at = tableData.get("created_at")
        self.updated_at = tableData.get("updated_at")

    def toJson(self):
        return {
            "id": self.id,
            "config_name": self.config_name,
            "node_id": self.node_id,
            "is_healthy": self.is_healthy,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __repr__(self):
        return str(self.toJson())
