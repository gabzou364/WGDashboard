"""
AuditLog Model
Represents an audit log entry for tracking important system changes (Phase 8)
"""
from datetime import datetime


class AuditLog:
    def __init__(self, tableData):
        self.id = tableData.get("id")
        self.timestamp = tableData.get("timestamp")
        self.action = tableData.get("action")
        self.entity_type = tableData.get("entity_type")
        self.entity_id = tableData.get("entity_id")
        self.details = tableData.get("details")
        self.user = tableData.get("user")

    def toJson(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": self.details,
            "user": self.user,
        }

    def __repr__(self):
        return str(self.toJson())
