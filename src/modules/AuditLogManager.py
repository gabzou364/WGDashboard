"""
Audit Log Manager
Handles audit logging for important system changes (Phase 8)
"""
import json
from datetime import datetime
from typing import List, Optional, Tuple
import sqlalchemy as db

try:
    from flask import current_app
    _has_flask = True
except ImportError:
    _has_flask = False

try:
    from .AuditLog import AuditLog
except ImportError:
    from AuditLog import AuditLog


def _log_info(msg):
    """Helper to log info messages"""
    if _has_flask:
        try:
            current_app.logger.info(msg)
        except (RuntimeError, NameError):
            pass


def _log_error(msg, exc=None):
    """Helper to log error messages"""
    if _has_flask:
        try:
            if exc:
                current_app.logger.error(msg, exc)
            else:
                current_app.logger.error(msg)
        except (RuntimeError, NameError):
            pass


class AuditLogManager:
    """Manager for audit log operations"""
    
    def __init__(self, DashboardConfig):
        self.DashboardConfig = DashboardConfig
        self.engine = DashboardConfig.engine
        self.auditLogTable = DashboardConfig.auditLogTable
    
    def log(self, action: str, entity_type: str, entity_id: str = None, 
            details: str = None, user: str = None) -> Tuple[bool, str]:
        """
        Create an audit log entry
        
        Args:
            action: Action performed (e.g., "node_added", "peer_migrated", "dns_updated")
            entity_type: Type of entity (e.g., "config_node", "peer", "dns_record")
            entity_id: ID of the entity
            details: Additional details in JSON format
            user: User who performed the action
            
        Returns:
            Tuple of (success, message)
        """
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    self.auditLogTable.insert().values(
                        action=action,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        details=details,
                        user=user
                    )
                )
            
            _log_info(f"Audit log: {action} on {entity_type} {entity_id}")
            return True, "Audit log created"
        
        except Exception as e:
            _log_error(f"Error creating audit log: {e}")
            return False, str(e)
    
    def get_logs(self, entity_type: str = None, entity_id: str = None, 
                action: str = None, limit: int = 100, offset: int = 0) -> List[AuditLog]:
        """
        Query audit logs with filters
        
        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            action: Filter by action
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of AuditLog objects
        """
        try:
            with self.engine.connect() as conn:
                query = self.auditLogTable.select()
                
                # Apply filters
                filters = []
                if entity_type:
                    filters.append(self.auditLogTable.c.entity_type == entity_type)
                if entity_id:
                    filters.append(self.auditLogTable.c.entity_id == entity_id)
                if action:
                    filters.append(self.auditLogTable.c.action == action)
                
                if filters:
                    query = query.where(db.and_(*filters))
                
                # Order by timestamp descending
                query = query.order_by(self.auditLogTable.c.timestamp.desc())
                
                # Apply pagination
                query = query.limit(limit).offset(offset)
                
                result = conn.execute(query).mappings().fetchall()
                
                return [AuditLog(dict(row)) for row in result]
        
        except Exception as e:
            _log_error(f"Error querying audit logs: {e}")
            return []
