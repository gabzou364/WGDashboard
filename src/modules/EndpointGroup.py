"""
EndpointGroup Model
Represents a Mode A (Cluster/Single domain) endpoint configuration (Phase 8)
"""
from datetime import datetime


class EndpointGroup:
    def __init__(self, tableData):
        self.id = tableData.get("id")
        self.config_name = tableData.get("config_name")
        self.domain = tableData.get("domain")
        self.port = tableData.get("port")
        self.cloudflare_zone_id = tableData.get("cloudflare_zone_id")
        self.cloudflare_record_name = tableData.get("cloudflare_record_name")
        self.ttl = tableData.get("ttl", 60)
        self.proxied = tableData.get("proxied", False)
        self.auto_migrate = tableData.get("auto_migrate", True)
        self.publish_only_healthy = tableData.get("publish_only_healthy", True)
        self.min_nodes = tableData.get("min_nodes", 1)
        self.created_at = tableData.get("created_at")
        self.updated_at = tableData.get("updated_at")

    def toJson(self):
        return {
            "id": self.id,
            "config_name": self.config_name,
            "domain": self.domain,
            "port": self.port,
            "cloudflare_zone_id": self.cloudflare_zone_id,
            "cloudflare_record_name": self.cloudflare_record_name,
            "ttl": self.ttl,
            "proxied": self.proxied,
            "auto_migrate": self.auto_migrate,
            "publish_only_healthy": self.publish_only_healthy,
            "min_nodes": self.min_nodes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __repr__(self):
        return str(self.toJson())
