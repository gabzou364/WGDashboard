"""
Node Groups Management
Handles CRUD operations for node groups in multi-node architecture
"""
import uuid
from datetime import datetime
from typing import List, Optional, Tuple, Any
import sqlalchemy
from sqlalchemy import func, select

try:
    from flask import current_app
    _has_flask = True
except ImportError:
    _has_flask = False

try:
    from .NodeGroup import NodeGroup
except ImportError:
    from NodeGroup import NodeGroup


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


class NodeGroupsManager:
    """Manager for node group operations"""
    
    def __init__(self, DashboardConfig):
        self.DashboardConfig = DashboardConfig
        self.engine = DashboardConfig.engine
        self.nodeGroupsTable = DashboardConfig.nodeGroupsTable
    
    def getAllGroups(self) -> List[NodeGroup]:
        """Get all node groups from database"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(self.nodeGroupsTable.select()).mappings().fetchall()
                groups = []
                for row in result:
                    groups.append(NodeGroup(dict(row)))
                return groups
        except Exception as e:
            _log_error(f"Error getting all node groups: {e}")
            return []
    
    def getGroupById(self, group_id: str) -> Optional[NodeGroup]:
        """Get node group by ID"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.nodeGroupsTable.select().where(self.nodeGroupsTable.c.id == group_id)
                ).mappings().fetchone()
                if result:
                    return NodeGroup(dict(result))
                return None
        except Exception as e:
            _log_error(f"Error getting node group {group_id}: {e}")
            return None
    
    def getGroupByName(self, name: str) -> Optional[NodeGroup]:
        """Get node group by name"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.nodeGroupsTable.select().where(self.nodeGroupsTable.c.name == name)
                ).mappings().fetchone()
                if result:
                    return NodeGroup(dict(result))
                return None
        except Exception as e:
            _log_error(f"Error getting node group by name {name}: {e}")
            return None
    
    def createGroup(self, name: str, description: Optional[str] = None,
                   region: Optional[str] = None, priority: int = 0) -> Tuple[bool, str, Optional[NodeGroup]]:
        """
        Create a new node group
        
        Args:
            name: Group name (unique)
            description: Optional description
            region: Optional region identifier
            priority: Group priority (higher = preferred)
        
        Returns:
            Tuple of (success: bool, message: str, group: NodeGroup or None)
        """
        try:
            # Check if group with same name exists
            existing = self.getGroupByName(name)
            if existing:
                return False, f"Group with name '{name}' already exists", None
            
            group_id = str(uuid.uuid4())
            
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodeGroupsTable.insert().values(
                        id=group_id,
                        name=name,
                        description=description,
                        region=region,
                        priority=priority
                    )
                )
            
            group = self.getGroupById(group_id)
            _log_info(f"Created node group: {name} (ID: {group_id})")
            return True, "Node group created successfully", group
            
        except Exception as e:
            _log_error(f"Error creating node group: {e}")
            return False, f"Failed to create node group: {str(e)}", None
    
    def updateGroup(self, group_id: str, name: Optional[str] = None,
                   description: Optional[str] = None, region: Optional[str] = None,
                   priority: Optional[int] = None) -> Tuple[bool, str]:
        """
        Update node group
        
        Args:
            group_id: Group ID to update
            name: Optional new name
            description: Optional new description
            region: Optional new region
            priority: Optional new priority
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            group = self.getGroupById(group_id)
            if not group:
                return False, "Node group not found"
            
            # Build update dict with only provided values
            update_values = {}
            if name is not None:
                # Check if new name conflicts with existing group
                existing = self.getGroupByName(name)
                if existing and existing.id != group_id:
                    return False, f"Group with name '{name}' already exists"
                update_values['name'] = name
            if description is not None:
                update_values['description'] = description
            if region is not None:
                update_values['region'] = region
            if priority is not None:
                update_values['priority'] = priority
            
            if not update_values:
                return False, "No fields to update"
            
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodeGroupsTable.update()
                    .where(self.nodeGroupsTable.c.id == group_id)
                    .values(**update_values)
                )
            
            _log_info(f"Updated node group: {group_id}")
            return True, "Node group updated successfully"
            
        except Exception as e:
            _log_error(f"Error updating node group {group_id}: {e}")
            return False, f"Failed to update node group: {str(e)}"
    
    def deleteGroup(self, group_id: str, unassign_nodes: bool = True) -> Tuple[bool, str]:
        """
        Delete node group
        
        Args:
            group_id: Group ID to delete
            unassign_nodes: If True, unassign nodes from this group (set group_id to NULL)
                          If False, fail if group has nodes assigned
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            group = self.getGroupById(group_id)
            if not group:
                return False, "Node group not found"
            
            # Check if any nodes are assigned to this group
            nodesTable = self.DashboardConfig.nodesTable
            with self.engine.connect() as conn:
                nodes_count = conn.execute(
                    select(func.count()).select_from(nodesTable)
                    .where(nodesTable.c.group_id == group_id)
                ).scalar()
            
            if nodes_count > 0:
                if not unassign_nodes:
                    return False, f"Cannot delete group: {nodes_count} nodes are assigned to it"
                
                # Unassign nodes
                with self.engine.begin() as conn:
                    conn.execute(
                        nodesTable.update()
                        .where(nodesTable.c.group_id == group_id)
                        .values(group_id=None)
                    )
                _log_info(f"Unassigned {nodes_count} nodes from group {group_id}")
            
            # Delete group
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodeGroupsTable.delete().where(self.nodeGroupsTable.c.id == group_id)
                )
            
            _log_info(f"Deleted node group: {group_id}")
            return True, "Node group deleted successfully"
            
        except Exception as e:
            _log_error(f"Error deleting node group {group_id}: {e}")
            return False, f"Failed to delete node group: {str(e)}"
    
    def getNodesInGroup(self, group_id: str) -> List:
        """
        Get all nodes in a specific group
        
        Returns:
            List of node IDs in the group
        """
        try:
            nodesTable = self.DashboardConfig.nodesTable
            with self.engine.connect() as conn:
                result = conn.execute(
                    nodesTable.select().where(nodesTable.c.group_id == group_id)
                ).mappings().fetchall()
                return [dict(row) for row in result]
        except Exception as e:
            _log_error(f"Error getting nodes in group {group_id}: {e}")
            return []
    
    def assignNodeToGroup(self, node_id: str, group_id: Optional[str]) -> Tuple[bool, str]:
        """
        Assign a node to a group (or unassign if group_id is None)
        
        Args:
            node_id: Node ID to assign
            group_id: Group ID to assign to (or None to unassign)
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate group exists if not None
            if group_id is not None:
                group = self.getGroupById(group_id)
                if not group:
                    return False, "Node group not found"
            
            nodesTable = self.DashboardConfig.nodesTable
            with self.engine.begin() as conn:
                conn.execute(
                    nodesTable.update()
                    .where(nodesTable.c.id == node_id)
                    .values(group_id=group_id)
                )
            
            if group_id:
                _log_info(f"Assigned node {node_id} to group {group_id}")
                return True, "Node assigned to group successfully"
            else:
                _log_info(f"Unassigned node {node_id} from group")
                return True, "Node unassigned from group successfully"
            
        except Exception as e:
            _log_error(f"Error assigning node {node_id} to group: {e}")
            return False, f"Failed to assign node to group: {str(e)}"
