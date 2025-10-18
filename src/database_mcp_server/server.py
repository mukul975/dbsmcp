#!/usr/bin/env python3
"""
Database MCP Server - Main server implementation
"""

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .core.config import Config
from .core.database_manager import DatabaseManager
from .core.intent_parser import IntentParser
from .core.audit_logger import AuditLogger
from .core.security_manager import SecurityManager
from .core.query_optimizer import QueryOptimizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseMCPServer:
    """Main Database MCP Server class"""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize the server with configuration"""
        self.config = Config(config_file)
        self.database_manager = DatabaseManager(self.config)
        self.intent_parser = IntentParser(self.config)
        self.audit_logger = AuditLogger(self.config)
        self.security_manager = SecurityManager(self.config)
        self.query_optimizer = QueryOptimizer(self.config)
        
        # Initialize MCP server
        self.server = Server(
            name=self.config.server.name,
            version=self.config.server.version
        )
        
        # Register handlers
        self._register_handlers()
        
    def _register_handlers(self):
        """Register all MCP handlers"""
        # Resources
        self.server.list_resources()(self.list_resources)
        self.server.read_resource()(self.read_resource)
        
        # Tools
        self.server.list_tools()(self.list_tools)
        self.server.call_tool()(self.call_tool)
        
        # Prompts
        self.server.list_prompts()(self.list_prompts)
        self.server.get_prompt()(self.get_prompt)
        
    async def list_resources(self) -> List[types.Resource]:
        """List available database resources"""
        resources = []
        
        # Database connections
        for db_name, db_config in self.config.databases.items():
            if db_config.enabled:
                resources.append(types.Resource(
                    uri=f"database://{db_name}",
                    name=f"{db_name.title()} Database",
                    description=f"Connection to {db_name} database",
                    mimeType="application/json"
                ))
        
        # Schema information
        for db_name in self.database_manager.get_active_databases():
            resources.append(types.Resource(
                uri=f"schema://{db_name}",
                name=f"{db_name.title()} Schema",
                description=f"Schema information for {db_name}",
                mimeType="application/json"
            ))
            
        return resources
        
    async def read_resource(self, uri: str) -> str:
        """Read a specific resource"""
        try:
            if uri.startswith("database://"):
                db_name = uri.replace("database://", "")
                connection_info = await self.database_manager.get_connection_info(db_name)
                return str(connection_info)
                
            elif uri.startswith("schema://"):
                db_name = uri.replace("schema://", "")
                schema_info = await self.database_manager.get_schema_info(db_name)
                return str(schema_info)
                
            else:
                raise ValueError(f"Unknown resource URI: {uri}")
                
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            raise
            
    async def list_tools(self) -> List[types.Tool]:
        """List available database tools"""
        tools = [
            # Connection management
            types.Tool(
                name="connect_database",
                description="Connect to a database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_type": {"type": "string", "enum": ["mysql", "postgresql", "mongodb", "sqlite", "redis"]},
                        "connection_string": {"type": "string"},
                        "connection_name": {"type": "string"}
                    },
                    "required": ["database_type", "connection_string"]
                }
            ),
            
            # Query execution
            types.Tool(
                name="execute_query",
                description="Execute a database query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "query": {"type": "string"},
                        "parameters": {"type": "array", "items": {"type": "string"}},
                        "explain": {"type": "boolean", "default": False}
                    },
                    "required": ["database_name", "query"]
                }
            ),
            
            # Schema operations
            types.Tool(
                name="create_table",
                description="Create a new table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "table_name": {"type": "string"},
                        "columns": {"type": "array", "items": {"type": "object"}},
                        "constraints": {"type": "array", "items": {"type": "object"}}
                    },
                    "required": ["database_name", "table_name", "columns"]
                }
            ),
            
            types.Tool(
                name="drop_table",
                description="Drop an existing table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "table_name": {"type": "string"},
                        "cascade": {"type": "boolean", "default": False}
                    },
                    "required": ["database_name", "table_name"]
                }
            ),
            
            types.Tool(
                name="alter_table",
                description="Alter table structure",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "table_name": {"type": "string"},
                        "alterations": {"type": "array", "items": {"type": "object"}}
                    },
                    "required": ["database_name", "table_name", "alterations"]
                }
            ),
            
            # Index management
            types.Tool(
                name="create_index",
                description="Create a database index",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "table_name": {"type": "string"},
                        "index_name": {"type": "string"},
                        "columns": {"type": "array", "items": {"type": "string"}},
                        "unique": {"type": "boolean", "default": False}
                    },
                    "required": ["database_name", "table_name", "index_name", "columns"]
                }
            ),
            
            types.Tool(
                name="drop_index",
                description="Drop a database index",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "index_name": {"type": "string"},
                        "table_name": {"type": "string"}
                    },
                    "required": ["database_name", "index_name"]
                }
            ),
            
            # Data operations
            types.Tool(
                name="insert_data",
                description="Insert data into a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "table_name": {"type": "string"},
                        "data": {"type": "array", "items": {"type": "object"}},
                        "on_conflict": {"type": "string", "enum": ["ignore", "update", "error"]}
                    },
                    "required": ["database_name", "table_name", "data"]
                }
            ),
            
            types.Tool(
                name="update_data",
                description="Update existing data",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "table_name": {"type": "string"},
                        "data": {"type": "object"},
                        "where": {"type": "object"}
                    },
                    "required": ["database_name", "table_name", "data", "where"]
                }
            ),
            
            types.Tool(
                name="delete_data",
                description="Delete data from a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "table_name": {"type": "string"},
                        "where": {"type": "object"}
                    },
                    "required": ["database_name", "table_name", "where"]
                }
            ),
            
            # Backup and restore
            types.Tool(
                name="backup_database",
                description="Create a database backup",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "backup_path": {"type": "string"},
                        "compression": {"type": "string", "enum": ["none", "gzip", "bzip2"]},
                        "include_data": {"type": "boolean", "default": True}
                    },
                    "required": ["database_name"]
                }
            ),
            
            types.Tool(
                name="restore_database",
                description="Restore a database from backup",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "backup_path": {"type": "string"},
                        "overwrite": {"type": "boolean", "default": False}
                    },
                    "required": ["database_name", "backup_path"]
                }
            ),
            
            # Performance and monitoring
            types.Tool(
                name="analyze_performance",
                description="Analyze database performance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "query": {"type": "string"},
                        "include_execution_plan": {"type": "boolean", "default": True}
                    },
                    "required": ["database_name"]
                }
            ),
            
            types.Tool(
                name="optimize_query",
                description="Get query optimization suggestions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "query": {"type": "string"}
                    },
                    "required": ["database_name", "query"]
                }
            ),
            
            # Natural language processing
            types.Tool(
                name="natural_language_query",
                description="Execute natural language query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "natural_query": {"type": "string"},
                        "table_context": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["database_name", "natural_query"]
                }
            ),
            
            # Migration
            types.Tool(
                name="migrate_schema",
                description="Migrate database schema",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "migration_script": {"type": "string"},
                        "dry_run": {"type": "boolean", "default": True}
                    },
                    "required": ["database_name", "migration_script"]
                }
            ),
            
            # User management
            types.Tool(
                name="create_user",
                description="Create a database user",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                        "permissions": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["database_name", "username", "password"]
                }
            ),
            
            types.Tool(
                name="grant_permissions",
                description="Grant permissions to a user",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"},
                        "username": {"type": "string"},
                        "permissions": {"type": "array", "items": {"type": "string"}},
                        "table_name": {"type": "string"}
                    },
                    "required": ["database_name", "username", "permissions"]
                }
            ),
            
            # Additional connection management
            types.Tool(
                name="disconnect",
                description="Disconnect from the database",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="create_database",
                description="Create a new database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"}
                    },
                    "required": ["database_name"]
                }
            ),
            
            types.Tool(
                name="drop_database",
                description="Drop a database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_name": {"type": "string"}
                    },
                    "required": ["database_name"]
                }
            ),
            
            # Additional schema operations
            types.Tool(
                name="rename_table",
                description="Rename a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "old_name": {"type": "string"},
                        "new_name": {"type": "string"}
                    },
                    "required": ["old_name", "new_name"]
                }
            ),
            
            types.Tool(
                name="add_column",
                description="Add a new column to a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column_definition": {"type": "object"}
                    },
                    "required": ["table_name", "column_definition"]
                }
            ),
            
            types.Tool(
                name="drop_column",
                description="Drop a column from a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column_name": {"type": "string"}
                    },
                    "required": ["table_name", "column_name"]
                }
            ),
            
            types.Tool(
                name="modify_column",
                description="Modify a column definition",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column_name": {"type": "string"},
                        "new_definition": {"type": "object"}
                    },
                    "required": ["table_name", "column_name", "new_definition"]
                }
            ),
            
            # Query operations
            types.Tool(
                name="filter_data",
                description="Filter data within a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "conditions": {"type": "object"},
                        "limit": {"type": "integer"}
                    },
                    "required": ["table_name", "conditions"]
                }
            ),
            
            types.Tool(
                name="aggregate_data",
                description="Aggregate data (COUNT, SUM, AVG, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "aggregations": {"type": "array", "items": {"type": "object"}},
                        "group_by": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["table_name", "aggregations"]
                }
            ),
            
            types.Tool(
                name="join_tables",
                description="Join multiple tables",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "join_config": {"type": "object"}
                    },
                    "required": ["join_config"]
                }
            ),
            
            # Additional user management
            types.Tool(
                name="revoke_permissions",
                description="Revoke user permissions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "permissions": {"type": "array", "items": {"type": "string"}},
                        "table_name": {"type": "string"}
                    },
                    "required": ["username", "permissions"]
                }
            ),
            
            types.Tool(
                name="drop_user",
                description="Drop a database user",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"}
                    },
                    "required": ["username"]
                }
            ),
            
            # Metadata operations
            types.Tool(
                name="list_tables",
                description="List all tables in the database",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="describe_table",
                description="Describe table structure",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"}
                    },
                    "required": ["table_name"]
                }
            ),
            
            types.Tool(
                name="explain_query",
                description="Explain query execution plan",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            ),
            
            # Data movement operations
            types.Tool(
                name="migrate_table",
                description="Migrate data between tables",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_table": {"type": "string"},
                        "target_table": {"type": "string"},
                        "mapping": {"type": "object"}
                    },
                    "required": ["source_table", "target_table"]
                }
            ),
            
            types.Tool(
                name="sync_schema",
                description="Synchronize schema with target definition",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target_schema": {"type": "object"}
                    },
                    "required": ["target_schema"]
                }
            ),
            
            # Automation operations
            types.Tool(
                name="schedule_task",
                description="Schedule a recurring task",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_name": {"type": "string"},
                        "schedule": {"type": "string"},
                        "query": {"type": "string"}
                    },
                    "required": ["task_name", "schedule", "query"]
                }
            ),
            
            # Monitoring operations
            types.Tool(
                name="log_query",
                description="Log query execution",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "execution_time": {"type": "number"},
                        "result_count": {"type": "integer"}
                    },
                    "required": ["query", "execution_time", "result_count"]
                }
            ),
            
            types.Tool(
                name="get_status",
                description="Get database status and health information",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            # Additional comprehensive commands
            types.Tool(
                name="setup_database",
                description="Deploy a new database instance with configuration",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database_config": {"type": "object"}
                    },
                    "required": ["database_config"]
                }
            ),
            
            types.Tool(
                name="init_cluster",
                description="Set up a cluster with replication or sharding support",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cluster_config": {"type": "object"}
                    },
                    "required": ["cluster_config"]
                }
            ),
            
            types.Tool(
                name="set_user_privileges",
                description="Grant or revoke permissions to users",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "privileges": {"type": "array", "items": {"type": "string"}},
                        "resource": {"type": "string"}
                    },
                    "required": ["username", "privileges"]
                }
            ),
            
            types.Tool(
                name="enable_ssl",
                description="Configure SSL/TLS encryption",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ssl_config": {"type": "object"}
                    },
                    "required": ["ssl_config"]
                }
            ),
            
            types.Tool(
                name="define_constraint",
                description="Add constraints like PRIMARY KEY, UNIQUE, FOREIGN KEY",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "constraint_definition": {"type": "object"}
                    },
                    "required": ["table_name", "constraint_definition"]
                }
            ),
            
            types.Tool(
                name="recommend_index",
                description="Analyze and recommend index strategies",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "query_patterns": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["table_name", "query_patterns"]
                }
            ),
            
            types.Tool(
                name="shard_table",
                description="Distribute table/collection across shards",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "shard_config": {"type": "object"}
                    },
                    "required": ["table_name", "shard_config"]
                }
            ),
            
            types.Tool(
                name="partition_table",
                description="Partition large table for performance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "partition_config": {"type": "object"}
                    },
                    "required": ["table_name", "partition_config"]
                }
            ),
            
            types.Tool(
                name="analyze_query",
                description="Analyze query and return execution plan with performance insights",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            ),
            
            types.Tool(
                name="optimize_query",
                description="Automatically rewrite query for optimal performance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            ),
            
            types.Tool(
                name="select_data",
                description="Fetch data using filters and projections",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "filters": {"type": "object"},
                        "projection": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["table_name", "filters"]
                }
            ),
            
            types.Tool(
                name="migrate_data",
                description="Migrate data between different DB types or environments",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_config": {"type": "object"},
                        "target_config": {"type": "object"},
                        "migration_options": {"type": "object"}
                    },
                    "required": ["source_config", "target_config", "migration_options"]
                }
            ),
            
            types.Tool(
                name="convert_schema",
                description="Convert schema from one DB type to another",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_schema": {"type": "object"},
                        "target_db_type": {"type": "string"}
                    },
                    "required": ["source_schema", "target_db_type"]
                }
            ),
            
            types.Tool(
                name="import_data",
                description="Import data from CSV, JSON, or dump files",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "data_source": {"type": "string"},
                        "import_options": {"type": "object"}
                    },
                    "required": ["table_name", "data_source", "import_options"]
                }
            ),
            
            types.Tool(
                name="export_data",
                description="Export data to formats like CSV, JSON, SQL",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "export_format": {"type": "string"},
                        "export_options": {"type": "object"}
                    },
                    "required": ["table_name", "export_format", "export_options"]
                }
            ),
            
            types.Tool(
                name="schedule_backup",
                description="Schedule recurring backups",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "backup_schedule": {"type": "string"},
                        "backup_config": {"type": "object"}
                    },
                    "required": ["backup_schedule", "backup_config"]
                }
            ),
            
            types.Tool(
                name="clone_database",
                description="Clone database into staging/sandbox environment",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_db": {"type": "string"},
                        "target_db": {"type": "string"},
                        "clone_options": {"type": "object"}
                    },
                    "required": ["source_db", "target_db", "clone_options"]
                }
            ),
            
            types.Tool(
                name="mask_data",
                description="Anonymize sensitive data for test environments",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "masking_rules": {"type": "object"}
                    },
                    "required": ["table_name", "masking_rules"]
                }
            ),
            
            types.Tool(
                name="monitor_health",
                description="Monitor DB CPU, memory, storage, active connections",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="monitor_queries",
                description="Track running and slow queries",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="log_queries",
                description="Record all queries and execution times",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "enable": {"type": "boolean", "default": True}
                    },
                    "required": []
                }
            ),
            
            types.Tool(
                name="enable_audit_log",
                description="Enable audit logging for DDL/DML changes",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "audit_config": {"type": "object"}
                    },
                    "required": ["audit_config"]
                }
            ),
            
            types.Tool(
                name="log_schema_changes",
                description="Track all changes to tables, columns, and constraints",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "enable": {"type": "boolean", "default": True}
                    },
                    "required": []
                }
            ),
            
            types.Tool(
                name="compare_schemas",
                description="Compare schema differences across environments",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_schema": {"type": "object"},
                        "target_schema": {"type": "object"}
                    },
                    "required": ["source_schema", "target_schema"]
                }
            ),
            
            types.Tool(
                name="restart_database",
                description="Restart the database engine",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="get_connection_string",
                description="Return current database connection string",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            # Advanced Replication Commands
            types.Tool(
                name="enable_replication",
                description="Sets up master-slave or primary-replica replication",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "replication_config": {"type": "object"}
                    },
                    "required": ["replication_config"]
                }
            ),
            
            types.Tool(
                name="pause_replication",
                description="Pauses an active replication channel",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "channel_name": {"type": "string"}
                    },
                    "required": []
                }
            ),
            
            types.Tool(
                name="resume_replication",
                description="Resumes replication after pause or failure",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "channel_name": {"type": "string"}
                    },
                    "required": []
                }
            ),
            
            types.Tool(
                name="check_replication_status",
                description="Checks replication lag and health",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            # Advanced Sharding Commands
            types.Tool(
                name="setup_sharding",
                description="Initializes and distributes data across shards",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sharding_config": {"type": "object"}
                    },
                    "required": ["sharding_config"]
                }
            ),
            
            types.Tool(
                name="rebalance_shards",
                description="Rebalances data between existing shards",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "rebalance_config": {"type": "object"}
                    },
                    "required": ["rebalance_config"]
                }
            ),
            
            types.Tool(
                name="add_shard",
                description="Adds a new shard node to the cluster",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "shard_config": {"type": "object"}
                    },
                    "required": ["shard_config"]
                }
            ),
            
            types.Tool(
                name="remove_shard",
                description="Removes a shard from cluster safely",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "shard_name": {"type": "string"},
                        "safe_mode": {"type": "boolean", "default": True}
                    },
                    "required": ["shard_name"]
                }
            ),
            
            # Views and Materialized Views
            types.Tool(
                name="create_view",
                description="Creates a virtual view from query result",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "view_name": {"type": "string"},
                        "query": {"type": "string"},
                        "materialized": {"type": "boolean", "default": False}
                    },
                    "required": ["view_name", "query"]
                }
            ),
            
            types.Tool(
                name="drop_view",
                description="Drops an existing view from the schema",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "view_name": {"type": "string"},
                        "cascade": {"type": "boolean", "default": False}
                    },
                    "required": ["view_name"]
                }
            ),
            
            types.Tool(
                name="refresh_materialized_view",
                description="Refreshes a materialized view with latest data",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "view_name": {"type": "string"}
                    },
                    "required": ["view_name"]
                }
            ),
            
            # Triggers
            types.Tool(
                name="create_trigger",
                description="Creates a trigger on insert/update/delete",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trigger_name": {"type": "string"},
                        "table_name": {"type": "string"},
                        "event": {"type": "string"},
                        "timing": {"type": "string"},
                        "action": {"type": "string"}
                    },
                    "required": ["trigger_name", "table_name", "event", "timing", "action"]
                }
            ),
            
            types.Tool(
                name="drop_trigger",
                description="Drops an existing trigger",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trigger_name": {"type": "string"},
                        "table_name": {"type": "string"}
                    },
                    "required": ["trigger_name"]
                }
            ),
            
            # Functions and Procedures
            types.Tool(
                name="create_function",
                description="Creates a stored function or UDF",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "function_name": {"type": "string"},
                        "parameters": {"type": "array", "items": {"type": "object"}},
                        "return_type": {"type": "string"},
                        "body": {"type": "string"}
                    },
                    "required": ["function_name", "parameters", "return_type", "body"]
                }
            ),
            
            types.Tool(
                name="drop_function",
                description="Drops a stored function",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "function_name": {"type": "string"},
                        "cascade": {"type": "boolean", "default": False}
                    },
                    "required": ["function_name"]
                }
            ),
            
            types.Tool(
                name="create_procedure",
                description="Creates a stored procedure for repeatable logic",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "procedure_name": {"type": "string"},
                        "parameters": {"type": "array", "items": {"type": "object"}},
                        "body": {"type": "string"}
                    },
                    "required": ["procedure_name", "parameters", "body"]
                }
            ),
            
            types.Tool(
                name="drop_procedure",
                description="Drops a stored procedure",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "procedure_name": {"type": "string"},
                        "cascade": {"type": "boolean", "default": False}
                    },
                    "required": ["procedure_name"]
                }
            ),
            
            # Advanced User Management
            types.Tool(
                name="list_users",
                description="Lists all users in the database",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="list_roles",
                description="Lists all defined roles and permissions",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="assign_role",
                description="Assigns an existing role to a user",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "role_name": {"type": "string"}
                    },
                    "required": ["username", "role_name"]
                }
            ),
            
            types.Tool(
                name="revoke_role",
                description="Removes a role from a user",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "role_name": {"type": "string"}
                    },
                    "required": ["username", "role_name"]
                }
            ),
            
            types.Tool(
                name="reset_password",
                description="Resets password for any user",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "new_password": {"type": "string"}
                    },
                    "required": ["username", "new_password"]
                }
            ),
            
            types.Tool(
                name="force_disconnect_user",
                description="Kills active session or connection",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"}
                    },
                    "required": ["username"]
                }
            ),
            
            # Session and Lock Monitoring
            types.Tool(
                name="track_session",
                description="Tracks live user sessions or connections",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="track_locks",
                description="Shows locked resources or waiting queries",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            # Documentation Generation
            types.Tool(
                name="generate_er_diagram",
                description="Auto-generates Entity-Relationship diagram",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "output_format": {"type": "string", "default": "png"}
                    },
                    "required": []
                }
            ),
            
            types.Tool(
                name="generate_schema_doc",
                description="Creates schema documentation in markdown or HTML",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "output_format": {"type": "string", "default": "markdown"}
                    },
                    "required": []
                }
            ),
            
            # Migration and DevOps
            types.Tool(
                name="generate_migration_script",
                description="Generates diff script for schema versioning",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target_schema": {"type": "object"}
                    },
                    "required": ["target_schema"]
                }
            ),
            
            types.Tool(
                name="apply_migration_script",
                description="Applies SQL diff or change script to environment",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "migration_script": {"type": "string"},
                        "dry_run": {"type": "boolean", "default": True}
                    },
                    "required": ["migration_script"]
                }
            ),
            
            # Job Scheduling
            types.Tool(
                name="schedule_sql_job",
                description="Schedules and runs SQL jobs at intervals",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_name": {"type": "string"},
                        "sql_command": {"type": "string"},
                        "schedule": {"type": "string"}
                    },
                    "required": ["job_name", "sql_command", "schedule"]
                }
            ),
            
            types.Tool(
                name="enable_event_scheduler",
                description="Enables internal scheduler for jobs",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean", "default": True}
                    },
                    "required": []
                }
            ),
            
            # Testing and Data Generation
            types.Tool(
                name="generate_seed_data",
                description="Generates fake/test data for any table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "row_count": {"type": "integer"},
                        "seed_config": {"type": "object"}
                    },
                    "required": ["table_name", "row_count", "seed_config"]
                }
            ),
            
            types.Tool(
                name="truncate_table",
                description="Deletes all rows without dropping table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"}
                    },
                    "required": ["table_name"]
                }
            ),
            
            types.Tool(
                name="archive_old_data",
                description="Moves data older than X date to archive",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "cutoff_date": {"type": "string"},
                        "archive_table": {"type": "string"}
                    },
                    "required": ["table_name", "cutoff_date", "archive_table"]
                }
            ),
            
            # Maintenance
            types.Tool(
                name="rotate_logs",
                description="Archives or deletes old query logs",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "log_type": {"type": "string", "default": "all"}
                    },
                    "required": []
                }
            ),
            
            types.Tool(
                name="purge_binary_logs",
                description="Deletes old binlogs to free disk",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "before_date": {"type": "string"}
                    },
                    "required": ["before_date"]
                }
            ),
            
            # Resource Monitoring
            types.Tool(
                name="check_disk_usage",
                description="Returns size of DB, tables, indexes, logs",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="check_memory_usage",
                description="Returns buffer/cache/memory info",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            # Security
            types.Tool(
                name="detect_anomalies",
                description="Flags suspicious queries or access patterns",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "time_window": {"type": "string", "default": "24h"}
                    },
                    "required": []
                }
            ),
            
            types.Tool(
                name="enable_firewall",
                description="Enables IP-level database firewall (if supported)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "firewall_config": {"type": "object"}
                    },
                    "required": ["firewall_config"]
                }
            ),
            
            types.Tool(
                name="audit_login_activity",
                description="Tracks login attempts with timestamp/IP",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "time_window": {"type": "string", "default": "24h"}
                    },
                    "required": []
                }
            ),
            
            types.Tool(
                name="enable_tls_auth",
                description="Forces client cert/TLS auth instead of password",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tls_config": {"type": "object"}
                    },
                    "required": ["tls_config"]
                }
            ),
            
            # Optimization
            types.Tool(
                name="update_statistics",
                description="Refreshes DB statistics for query planner",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"}
                    },
                    "required": []
                }
            ),
            
            types.Tool(
                name="vacuum_table",
                description="Cleans up bloat and dead rows",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "full": {"type": "boolean", "default": False}
                    },
                    "required": ["table_name"]
                }
            ),
            
            types.Tool(
                name="rebuild_index",
                description="Rebuilds fragmented indexes",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "index_name": {"type": "string"},
                        "table_name": {"type": "string"}
                    },
                    "required": ["index_name", "table_name"]
                }
            ),
            
            types.Tool(
                name="defragment_table",
                description="Compacts and reorders physical table layout",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"}
                    },
                    "required": ["table_name"]
                }
            ),
            
            types.Tool(
                name="compact_storage",
                description="Compacts document storage to save space",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "collection_name": {"type": "string"}
                    },
                    "required": []
                }
            ),
            
            # Health and Setup
            types.Tool(
                name="run_health_check",
                description="Runs full DB diagnostics and performance tests",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            types.Tool(
                name="setup_connection_pooling",
                description="Configures pooling (e.g., PgBouncer, ProxySQL)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pool_config": {"type": "object"}
                    },
                    "required": ["pool_config"]
                }
            )
        ,

            # Additional Missing Tools
            types.Tool(
                name="backup_table",
                description="Backups the table in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_user",
                description="Backups the user in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_role",
                description="Backups the role in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_index",
                description="Backups the index in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_view",
                description="Backups the view in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_function",
                description="Backups the function in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_trigger",
                description="Backups the trigger in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_schema",
                description="Backups the schema in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_replica",
                description="Backups the replica in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_shard",
                description="Backups the shard in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_cluster",
                description="Backups the cluster in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_backup",
                description="Backups the backup in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_query",
                description="Backups the query in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_session",
                description="Backups the session in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_job",
                description="Backups the job in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_plan",
                description="Backups the plan in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_cache",
                description="Backups the cache in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_connection",
                description="Backups the connection in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_policy",
                description="Backups the policy in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_constraint",
                description="Backups the constraint in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_snapshot",
                description="Backups the snapshot in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_column",
                description="Backups the column in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_mask",
                description="Backups the mask in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_log",
                description="Backups the log in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_metric",
                description="Backups the metric in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_alert",
                description="Backups the alert in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_firewall",
                description="Backups the firewall in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_certificate",
                description="Backups the certificate in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="backup_plan_baseline",
                description="Backups the plan baseline in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_table",
                description="Restores the table in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_user",
                description="Restores the user in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_role",
                description="Restores the role in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_index",
                description="Restores the index in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_view",
                description="Restores the view in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_function",
                description="Restores the function in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_trigger",
                description="Restores the trigger in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_schema",
                description="Restores the schema in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_replica",
                description="Restores the replica in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_shard",
                description="Restores the shard in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_cluster",
                description="Restores the cluster in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_backup",
                description="Restores the backup in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_query",
                description="Restores the query in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_session",
                description="Restores the session in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_job",
                description="Restores the job in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_plan",
                description="Restores the plan in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_cache",
                description="Restores the cache in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_connection",
                description="Restores the connection in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_policy",
                description="Restores the policy in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_constraint",
                description="Restores the constraint in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_snapshot",
                description="Restores the snapshot in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_column",
                description="Restores the column in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_mask",
                description="Restores the mask in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_log",
                description="Restores the log in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_metric",
                description="Restores the metric in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_alert",
                description="Restores the alert in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_firewall",
                description="Restores the firewall in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_certificate",
                description="Restores the certificate in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="restore_plan_baseline",
                description="Restores the plan baseline in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_table",
                description="Replicates the table in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_user",
                description="Replicates the user in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_role",
                description="Replicates the role in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_index",
                description="Replicates the index in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_view",
                description="Replicates the view in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_function",
                description="Replicates the function in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_trigger",
                description="Replicates the trigger in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_schema",
                description="Replicates the schema in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_replica",
                description="Replicates the replica in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_shard",
                description="Replicates the shard in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_cluster",
                description="Replicates the cluster in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_backup",
                description="Replicates the backup in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_query",
                description="Replicates the query in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_session",
                description="Replicates the session in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_job",
                description="Replicates the job in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_plan",
                description="Replicates the plan in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_cache",
                description="Replicates the cache in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_connection",
                description="Replicates the connection in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_policy",
                description="Replicates the policy in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_constraint",
                description="Replicates the constraint in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_snapshot",
                description="Replicates the snapshot in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_column",
                description="Replicates the column in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_mask",
                description="Replicates the mask in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_log",
                description="Replicates the log in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_metric",
                description="Replicates the metric in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_alert",
                description="Replicates the alert in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_firewall",
                description="Replicates the firewall in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_certificate",
                description="Replicates the certificate in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="replicate_plan_baseline",
                description="Replicates the plan baseline in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_table",
                description="Configures the table in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_user",
                description="Configures the user in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_role",
                description="Configures the role in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_index",
                description="Configures the index in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_view",
                description="Configures the view in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_function",
                description="Configures the function in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_trigger",
                description="Configures the trigger in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_schema",
                description="Configures the schema in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_replica",
                description="Configures the replica in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_shard",
                description="Configures the shard in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_cluster",
                description="Configures the cluster in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_backup",
                description="Configures the backup in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_query",
                description="Configures the query in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_session",
                description="Configures the session in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_job",
                description="Configures the job in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_plan",
                description="Configures the plan in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_cache",
                description="Configures the cache in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_connection",
                description="Configures the connection in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_policy",
                description="Configures the policy in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_constraint",
                description="Configures the constraint in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_snapshot",
                description="Configures the snapshot in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_column",
                description="Configures the column in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_mask",
                description="Configures the mask in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_log",
                description="Configures the log in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_metric",
                description="Configures the metric in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_alert",
                description="Configures the alert in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_firewall",
                description="Configures the firewall in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_certificate",
                description="Configures the certificate in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="configure_plan_baseline",
                description="Configures the plan baseline in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_table",
                description="Resets the table in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_user",
                description="Resets the user in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_role",
                description="Resets the role in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_index",
                description="Resets the index in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_view",
                description="Resets the view in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_function",
                description="Resets the function in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_trigger",
                description="Resets the trigger in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_schema",
                description="Resets the schema in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_replica",
                description="Resets the replica in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_shard",
                description="Resets the shard in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_cluster",
                description="Resets the cluster in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_backup",
                description="Resets the backup in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_query",
                description="Resets the query in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_session",
                description="Resets the session in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_job",
                description="Resets the job in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_plan",
                description="Resets the plan in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_cache",
                description="Resets the cache in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_connection",
                description="Resets the connection in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_policy",
                description="Resets the policy in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_constraint",
                description="Resets the constraint in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_snapshot",
                description="Resets the snapshot in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_column",
                description="Resets the column in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_mask",
                description="Resets the mask in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_log",
                description="Resets the log in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_metric",
                description="Resets the metric in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_alert",
                description="Resets the alert in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_firewall",
                description="Resets the firewall in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_certificate",
                description="Resets the certificate in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="reset_plan_baseline",
                description="Resets the plan baseline in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_table",
                description="Rotates the table in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_user",
                description="Rotates the user in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_role",
                description="Rotates the role in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_index",
                description="Rotates the index in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_view",
                description="Rotates the view in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_function",
                description="Rotates the function in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_trigger",
                description="Rotates the trigger in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_schema",
                description="Rotates the schema in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_replica",
                description="Rotates the replica in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_shard",
                description="Rotates the shard in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_cluster",
                description="Rotates the cluster in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_backup",
                description="Rotates the backup in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_query",
                description="Rotates the query in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_session",
                description="Rotates the session in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_job",
                description="Rotates the job in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_plan",
                description="Rotates the plan in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_cache",
                description="Rotates the cache in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_connection",
                description="Rotates the connection in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_policy",
                description="Rotates the policy in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_constraint",
                description="Rotates the constraint in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_snapshot",
                description="Rotates the snapshot in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_column",
                description="Rotates the column in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_mask",
                description="Rotates the mask in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_log",
                description="Rotates the log in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_metric",
                description="Rotates the metric in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_alert",
                description="Rotates the alert in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_firewall",
                description="Rotates the firewall in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_certificate",
                description="Rotates the certificate in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="rotate_plan_baseline",
                description="Rotates the plan baseline in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_user",
                description="Schedules the user in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_role",
                description="Schedules the role in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_index",
                description="Schedules the index in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_view",
                description="Schedules the view in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_function",
                description="Schedules the function in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_trigger",
                description="Schedules the trigger in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_schema",
                description="Schedules the schema in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_replica",
                description="Schedules the replica in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_shard",
                description="Schedules the shard in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_cluster",
                description="Schedules the cluster in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_session",
                description="Schedules the session in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_job",
                description="Schedules the job in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_plan",
                description="Schedules the plan in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_cache",
                description="Schedules the cache in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_connection",
                description="Schedules the connection in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_policy",
                description="Schedules the policy in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_constraint",
                description="Schedules the constraint in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_snapshot",
                description="Schedules the snapshot in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_column",
                description="Schedules the column in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_mask",
                description="Schedules the mask in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_log",
                description="Schedules the log in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_metric",
                description="Schedules the metric in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_alert",
                description="Schedules the alert in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_firewall",
                description="Schedules the firewall in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_certificate",
                description="Schedules the certificate in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_plan_baseline",
                description="Schedules the plan baseline in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_user",
                description="Optimizes the user in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_role",
                description="Optimizes the role in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_index",
                description="Optimizes the index in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_view",
                description="Optimizes the view in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_function",
                description="Optimizes the function in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_trigger",
                description="Optimizes the trigger in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_schema",
                description="Optimizes the schema in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_replica",
                description="Optimizes the replica in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_shard",
                description="Optimizes the shard in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_cluster",
                description="Optimizes the cluster in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_backup",
                description="Optimizes the backup in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_session",
                description="Optimizes the session in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_job",
                description="Optimizes the job in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_plan",
                description="Optimizes the plan in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_cache",
                description="Optimizes the cache in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_connection",
                description="Optimizes the connection in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_policy",
                description="Optimizes the policy in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_constraint",
                description="Optimizes the constraint in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_snapshot",
                description="Optimizes the snapshot in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_column",
                description="Optimizes the column in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_mask",
                description="Optimizes the mask in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_log",
                description="Optimizes the log in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_metric",
                description="Optimizes the metric in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_alert",
                description="Optimizes the alert in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_firewall",
                description="Optimizes the firewall in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_certificate",
                description="Optimizes the certificate in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_plan_baseline",
                description="Optimizes the plan baseline in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_user",
                description="Analyzes the user in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_role",
                description="Analyzes the role in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_index",
                description="Analyzes the index in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_view",
                description="Analyzes the view in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_function",
                description="Analyzes the function in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_trigger",
                description="Analyzes the trigger in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_schema",
                description="Analyzes the schema in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_replica",
                description="Analyzes the replica in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_shard",
                description="Analyzes the shard in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_cluster",
                description="Analyzes the cluster in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_backup",
                description="Analyzes the backup in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_session",
                description="Analyzes the session in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_job",
                description="Analyzes the job in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_plan",
                description="Analyzes the plan in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_cache",
                description="Analyzes the cache in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_connection",
                description="Analyzes the connection in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_policy",
                description="Analyzes the policy in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_constraint",
                description="Analyzes the constraint in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_snapshot",
                description="Analyzes the snapshot in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_column",
                description="Analyzes the column in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_mask",
                description="Analyzes the mask in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_log",
                description="Analyzes the log in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_metric",
                description="Analyzes the metric in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_alert",
                description="Analyzes the alert in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_firewall",
                description="Analyzes the firewall in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_certificate",
                description="Analyzes the certificate in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_plan_baseline",
                description="Analyzes the plan baseline in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_user",
                description="Migrates the user in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_role",
                description="Migrates the role in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_index",
                description="Migrates the index in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_view",
                description="Migrates the view in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_function",
                description="Migrates the function in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_trigger",
                description="Migrates the trigger in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_replica",
                description="Migrates the replica in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_shard",
                description="Migrates the shard in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_cluster",
                description="Migrates the cluster in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_backup",
                description="Migrates the backup in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_query",
                description="Migrates the query in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_session",
                description="Migrates the session in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_job",
                description="Migrates the job in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_plan",
                description="Migrates the plan in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_cache",
                description="Migrates the cache in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_connection",
                description="Migrates the connection in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_policy",
                description="Migrates the policy in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_constraint",
                description="Migrates the constraint in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_snapshot",
                description="Migrates the snapshot in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_column",
                description="Migrates the column in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_mask",
                description="Migrates the mask in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_log",
                description="Migrates the log in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_metric",
                description="Migrates the metric in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_alert",
                description="Migrates the alert in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_firewall",
                description="Migrates the firewall in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_certificate",
                description="Migrates the certificate in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_plan_baseline",
                description="Migrates the plan baseline in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),

            # Extended Context-Specific Tools
            types.Tool(
                name="create_database",
                description="Creates the database in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_table",
                description="Creates the table in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_user",
                description="Creates the user in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_role",
                description="Creates the role in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_index",
                description="Creates the index in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_schema",
                description="Creates the schema in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_replica",
                description="Creates the replica in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_shard",
                description="Creates the shard in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_cluster",
                description="Creates the cluster in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_backup",
                description="Creates the backup in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_query",
                description="Creates the query in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_session",
                description="Creates the session in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_job",
                description="Creates the job in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_plan",
                description="Creates the plan in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_cache",
                description="Creates the cache in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_connection",
                description="Creates the connection in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_policy",
                description="Creates the policy in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_constraint",
                description="Creates the constraint in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_snapshot",
                description="Creates the snapshot in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_column",
                description="Creates the column in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_mask",
                description="Creates the mask in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_log",
                description="Creates the log in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_metric",
                description="Creates the metric in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_alert",
                description="Creates the alert in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_firewall",
                description="Creates the firewall in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_certificate",
                description="Creates the certificate in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="create_plan_baseline",
                description="Creates the plan baseline in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_database",
                description="Deletes the database in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_table",
                description="Deletes the table in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_user",
                description="Deletes the user in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_role",
                description="Deletes the role in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_index",
                description="Deletes the index in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_view",
                description="Deletes the view in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_function",
                description="Deletes the function in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_trigger",
                description="Deletes the trigger in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_schema",
                description="Deletes the schema in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_replica",
                description="Deletes the replica in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_shard",
                description="Deletes the shard in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_cluster",
                description="Deletes the cluster in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_backup",
                description="Deletes the backup in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_query",
                description="Deletes the query in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_session",
                description="Deletes the session in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_job",
                description="Deletes the job in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_plan",
                description="Deletes the plan in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_cache",
                description="Deletes the cache in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_connection",
                description="Deletes the connection in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_policy",
                description="Deletes the policy in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_constraint",
                description="Deletes the constraint in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_snapshot",
                description="Deletes the snapshot in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_column",
                description="Deletes the column in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_mask",
                description="Deletes the mask in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_log",
                description="Deletes the log in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_metric",
                description="Deletes the metric in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_alert",
                description="Deletes the alert in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_firewall",
                description="Deletes the firewall in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_certificate",
                description="Deletes the certificate in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="delete_plan_baseline",
                description="Deletes the plan baseline in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_database",
                description="Updates the database in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_table",
                description="Updates the table in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_user",
                description="Updates the user in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_role",
                description="Updates the role in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_index",
                description="Updates the index in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_view",
                description="Updates the view in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_function",
                description="Updates the function in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_trigger",
                description="Updates the trigger in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_schema",
                description="Updates the schema in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_replica",
                description="Updates the replica in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_shard",
                description="Updates the shard in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_cluster",
                description="Updates the cluster in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_backup",
                description="Updates the backup in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_query",
                description="Updates the query in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_session",
                description="Updates the session in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_job",
                description="Updates the job in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_plan",
                description="Updates the plan in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_cache",
                description="Updates the cache in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_connection",
                description="Updates the connection in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_policy",
                description="Updates the policy in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_constraint",
                description="Updates the constraint in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_snapshot",
                description="Updates the snapshot in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_column",
                description="Updates the column in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_mask",
                description="Updates the mask in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_log",
                description="Updates the log in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_metric",
                description="Updates the metric in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_alert",
                description="Updates the alert in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_firewall",
                description="Updates the firewall in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_certificate",
                description="Updates the certificate in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="update_plan_baseline",
                description="Updates the plan baseline in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_database",
                description="Enables the database in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_table",
                description="Enables the table in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_user",
                description="Enables the user in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_role",
                description="Enables the role in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_index",
                description="Enables the index in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_view",
                description="Enables the view in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_function",
                description="Enables the function in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_trigger",
                description="Enables the trigger in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_schema",
                description="Enables the schema in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_replica",
                description="Enables the replica in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_shard",
                description="Enables the shard in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_cluster",
                description="Enables the cluster in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_backup",
                description="Enables the backup in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_query",
                description="Enables the query in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_session",
                description="Enables the session in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_job",
                description="Enables the job in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_plan",
                description="Enables the plan in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_cache",
                description="Enables the cache in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_connection",
                description="Enables the connection in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_policy",
                description="Enables the policy in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_constraint",
                description="Enables the constraint in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_snapshot",
                description="Enables the snapshot in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_column",
                description="Enables the column in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_mask",
                description="Enables the mask in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_log",
                description="Enables the log in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_metric",
                description="Enables the metric in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_alert",
                description="Enables the alert in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_firewall",
                description="Enables the firewall in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_certificate",
                description="Enables the certificate in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="enable_plan_baseline",
                description="Enables the plan baseline in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_database",
                description="Disables the database in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_table",
                description="Disables the table in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_user",
                description="Disables the user in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_role",
                description="Disables the role in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_index",
                description="Disables the index in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_view",
                description="Disables the view in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_function",
                description="Disables the function in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_trigger",
                description="Disables the trigger in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_schema",
                description="Disables the schema in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_replica",
                description="Disables the replica in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_shard",
                description="Disables the shard in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_cluster",
                description="Disables the cluster in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_backup",
                description="Disables the backup in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_query",
                description="Disables the query in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_session",
                description="Disables the session in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_job",
                description="Disables the job in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_plan",
                description="Disables the plan in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_cache",
                description="Disables the cache in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_connection",
                description="Disables the connection in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_policy",
                description="Disables the policy in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_constraint",
                description="Disables the constraint in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_snapshot",
                description="Disables the snapshot in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_column",
                description="Disables the column in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_mask",
                description="Disables the mask in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_log",
                description="Disables the log in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_metric",
                description="Disables the metric in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_alert",
                description="Disables the alert in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_firewall",
                description="Disables the firewall in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_certificate",
                description="Disables the certificate in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="disable_plan_baseline",
                description="Disables the plan baseline in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_database",
                description="Lists the database in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_table",
                description="Lists the table in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_user",
                description="Lists the user in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_role",
                description="Lists the role in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_index",
                description="Lists the index in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_view",
                description="Lists the view in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_function",
                description="Lists the function in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_trigger",
                description="Lists the trigger in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_schema",
                description="Lists the schema in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_replica",
                description="Lists the replica in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_shard",
                description="Lists the shard in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_cluster",
                description="Lists the cluster in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_backup",
                description="Lists the backup in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_query",
                description="Lists the query in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_session",
                description="Lists the session in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_job",
                description="Lists the job in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_plan",
                description="Lists the plan in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_cache",
                description="Lists the cache in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_connection",
                description="Lists the connection in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_policy",
                description="Lists the policy in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_constraint",
                description="Lists the constraint in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_snapshot",
                description="Lists the snapshot in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_column",
                description="Lists the column in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_mask",
                description="Lists the mask in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_log",
                description="Lists the log in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_metric",
                description="Lists the metric in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_alert",
                description="Lists the alert in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_firewall",
                description="Lists the firewall in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_certificate",
                description="Lists the certificate in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="list_plan_baseline",
                description="Lists the plan baseline in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_database",
                description="Monitors the database in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_table",
                description="Monitors the table in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_user",
                description="Monitors the user in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the user'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_role",
                description="Monitors the role in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the role'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_index",
                description="Monitors the index in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the index'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_view",
                description="Monitors the view in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the view'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_function",
                description="Monitors the function in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the function'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_trigger",
                description="Monitors the trigger in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the trigger'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_schema",
                description="Monitors the schema in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_replica",
                description="Monitors the replica in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the replica'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_shard",
                description="Monitors the shard in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the shard'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_cluster",
                description="Monitors the cluster in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cluster'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_backup",
                description="Monitors the backup in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_query",
                description="Monitors the query in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_session",
                description="Monitors the session in the observability context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the session'}, 'observability_config': {'type': 'object', 'description': 'Observability configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_job",
                description="Monitors the job in the optimization context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the job'}, 'optimization_config': {'type': 'object', 'description': 'Optimization configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_plan",
                description="Monitors the plan in the automation context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan'}, 'automation_config': {'type': 'object', 'description': 'Automation configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_cache",
                description="Monitors the cache in the maintenance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the cache'}, 'maintenance_config': {'type': 'object', 'description': 'Maintenance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_connection",
                description="Monitors the connection in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the connection'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_policy",
                description="Monitors the policy in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the policy'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_constraint",
                description="Monitors the constraint in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the constraint'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_snapshot",
                description="Monitors the snapshot in the performance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the snapshot'}, 'performance_config': {'type': 'object', 'description': 'Performance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_column",
                description="Monitors the column in the backup context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the column'}, 'backup_config': {'type': 'object', 'description': 'Backup configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_mask",
                description="Monitors the mask in the monitoring context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the mask'}, 'monitoring_config': {'type': 'object', 'description': 'Monitoring configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_log",
                description="Monitors the log in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the log'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_metric",
                description="Monitors the metric in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the metric'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_alert",
                description="Monitors the alert in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the alert'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_firewall",
                description="Monitors the firewall in the sharding context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the firewall'}, 'sharding_config': {'type': 'object', 'description': 'Sharding configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_certificate",
                description="Monitors the certificate in the compliance context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the certificate'}, 'compliance_config': {'type': 'object', 'description': 'Compliance configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="monitor_plan_baseline",
                description="Monitors the plan baseline in the ai/ml context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the plan_baseline'}, 'ai_ml_config': {'type': 'object', 'description': 'AI/ML configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_database",
                description="Schedules the database in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_table",
                description="Schedules the table in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_backup",
                description="Schedules the backup in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the backup'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="schedule_query",
                description="Schedules the query in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_database",
                description="Optimizes the database in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_table",
                description="Optimizes the table in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="optimize_query",
                description="Optimizes the query in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_database",
                description="Analyzes the database in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_table",
                description="Analyzes the table in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="analyze_query",
                description="Analyzes the query in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_database",
                description="Migrates the database in the provisioning context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'provisioning_config': {'type': 'object', 'description': 'Provisioning configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_table",
                description="Migrates the table in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="migrate_schema",
                description="Migrates the schema in the replication context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'replication_config': {'type': 'object', 'description': 'Replication configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="audit_database",
                description="Audits the database in the audit context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'audit_config': {'type': 'object', 'description': 'Audit configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="audit_table",
                description="Audits the table in the devops context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'devops_config': {'type': 'object', 'description': 'DevOps configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="audit_query",
                description="Audits the query in the security context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the query'}, 'security_config': {'type': 'object', 'description': 'Security configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="setup_database",
                description="Sets up the database in the testing context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the database'}, 'testing_config': {'type': 'object', 'description': 'Testing configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="setup_table",
                description="Sets up the table in the data migration context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the table'}, 'data_migration_config': {'type': 'object', 'description': 'Data Migration configuration options'}},
                    "required": ["name"]
                }
            ),
            types.Tool(
                name="setup_schema",
                description="Sets up the schema in the schema context",
                inputSchema={
                    "type": "object",
                    "properties": {'name': {'type': 'string', 'description': 'Name of the schema'}, 'schema_config': {'type': 'object', 'description': 'Schema configuration options'}},
                    "required": ["name"]
                }
            ),
        ]
        
        return tools
        
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        """Handle tool calls"""
        try:
            # Log the tool call for audit
            await self.audit_logger.log_tool_call(name, arguments)
            
            # Security check
            if not await self.security_manager.validate_tool_call(name, arguments):
                raise ValueError("Security validation failed")
                
            # Route to appropriate handler
            if name == "connect_database":
                result = await self.database_manager.connect_database(
                    arguments["database_type"],
                    arguments["connection_string"],
                    arguments.get("connection_name")
                )
                
            elif name == "execute_query":
                result = await self.database_manager.execute_query(
                    arguments["database_name"],
                    arguments["query"],
                    arguments.get("parameters"),
                    arguments.get("explain", False)
                )
                
            elif name == "create_table":
                result = await self.database_manager.create_table(
                    arguments["database_name"],
                    arguments["table_name"],
                    arguments["columns"],
                    arguments.get("constraints", [])
                )
                
            elif name == "natural_language_query":
                # Parse natural language to SQL/NoSQL
                parsed_query = await self.intent_parser.parse_natural_language(
                    arguments["natural_query"],
                    arguments["database_name"],
                    arguments.get("table_context", [])
                )
                
                # Execute the parsed query
                result = await self.database_manager.execute_query(
                    arguments["database_name"],
                    parsed_query.query,
                    parsed_query.parameters
                )
                
            elif name == "optimize_query":
                result = await self.query_optimizer.optimize_query(
                    arguments["database_name"],
                    arguments["query"]
                )
                
            elif name == "backup_database":
                result = await self.database_manager.backup_database(
                    arguments["database_name"],
                    arguments.get("backup_path"),
                    arguments.get("compression", "gzip"),
                    arguments.get("include_data", True)
                )

            elif name == "disconnect":
                result = await self.database_manager._disconnect_all()

            elif name == "create_database":
                result = await self.database_manager._create_database(arguments["database_name"])

            elif name == "drop_database":
                result = await self.database_manager._drop_database(arguments["database_name"])

            elif name == "rename_table":
                result = await self.database_manager._rename_table(arguments["old_name"], arguments["new_name"])

            elif name == "add_column":
                result = await self.database_manager._add_column(arguments["table_name"], arguments["column_definition"])

            elif name == "drop_column":
                result = await self.database_manager._drop_column(arguments["table_name"], arguments["column_name"])

            elif name == "modify_column":
                result = await self.database_manager._modify_column(arguments["table_name"], arguments["column_name"], arguments["new_definition"])

            elif name == "filter_data":
                result = await self.database_manager._filter_data(arguments["table_name"], arguments["conditions"], arguments.get("limit"))

            elif name == "aggregate_data":
                result = await self.database_manager._aggregate_data(arguments["table_name"], arguments["aggregations"], arguments.get("group_by"))

            elif name == "join_tables":
                result = await self.database_manager._join_tables(arguments["join_config"])

            elif name == "revoke_permissions":
                result = await self.database_manager._revoke_permissions(arguments["username"], arguments["permissions"], arguments.get("table_name"))

            elif name == "drop_user":
                result = await self.database_manager._drop_user(arguments["username"])

            elif name == "list_tables":
                result = await self.database_manager._list_tables()

            elif name == "describe_table":
                result = await self.database_manager._describe_table(arguments["table_name"])

            elif name == "explain_query":
                result = await self.database_manager._explain_query(arguments["query"])

            elif name == "migrate_table":
                result = await self.database_manager._migrate_table(arguments["source_table"], arguments["target_table"], arguments.get("mapping"))

            elif name == "sync_schema":
                result = await self.database_manager._sync_schema(arguments["target_schema"])

            elif name == "schedule_task":
                result = await self.database_manager._schedule_task(arguments["task_name"], arguments["schedule"], arguments["query"])

            elif name == "log_query":
                result = await self.database_manager._log_query(arguments["query"], arguments["execution_time"], arguments["result_count"])

            elif name == "get_status":
                result = await self.database_manager._get_status()

            # Missing handlers for comprehensive database commands
            elif name == "setup_database":
                result = await self.database_manager._setup_database(arguments["database_config"])

            elif name == "init_cluster":
                result = await self.database_manager._init_cluster(arguments["cluster_config"])

            elif name == "create_user":
                result = await self.database_manager._create_user(arguments["database_name"], arguments["username"], arguments["password"], arguments.get("permissions", []))

            elif name == "set_user_privileges":
                result = await self.database_manager._set_user_privileges(arguments["username"], arguments["privileges"], arguments.get("resource"))

            elif name == "enable_ssl":
                result = await self.database_manager._enable_ssl(arguments["ssl_config"])

            elif name == "define_constraint":
                result = await self.database_manager._define_constraint(arguments["table_name"], arguments["constraint_definition"])

            elif name == "create_index":
                result = await self.database_manager.create_index(arguments["database_name"], arguments["table_name"], arguments["index_name"], arguments["columns"], arguments.get("unique", False))

            elif name == "recommend_index":
                result = await self.database_manager._recommend_index(arguments["table_name"], arguments["query_patterns"])

            elif name == "shard_table":
                result = await self.database_manager._shard_table(arguments["table_name"], arguments["shard_config"])

            elif name == "partition_table":
                result = await self.database_manager._partition_table(arguments["table_name"], arguments["partition_config"])

            elif name == "analyze_query":
                result = await self.database_manager._analyze_query(arguments["query"])

            elif name == "insert_data":
                result = await self.database_manager._insert_data(arguments["database_name"], arguments["table_name"], arguments["data"], arguments.get("on_conflict", "error"))

            elif name == "update_data":
                result = await self.database_manager._update_data(arguments["database_name"], arguments["table_name"], arguments["data"], arguments["where"])

            elif name == "delete_data":
                result = await self.database_manager._delete_data(arguments["database_name"], arguments["table_name"], arguments["where"])

            elif name == "select_data":
                result = await self.database_manager._select_data(arguments["table_name"], arguments["filters"], arguments.get("projection"))

            elif name == "migrate_data":
                result = await self.database_manager._migrate_data(arguments["source_config"], arguments["target_config"], arguments["migration_options"])

            elif name == "convert_schema":
                result = await self.database_manager._convert_schema(arguments["source_schema"], arguments["target_db_type"])

            elif name == "import_data":
                result = await self.database_manager._import_data(arguments["table_name"], arguments["data_source"], arguments["import_options"])

            elif name == "export_data":
                result = await self.database_manager._export_data(arguments["table_name"], arguments["export_format"], arguments["export_options"])

            elif name == "restore_database":
                result = await self.database_manager._restore_database(arguments["database_name"], arguments["backup_path"], arguments.get("overwrite", False))

            elif name == "schedule_backup":
                result = await self.database_manager._schedule_backup(arguments["backup_schedule"], arguments["backup_config"])

            elif name == "clone_database":
                result = await self.database_manager._clone_database(arguments["source_db"], arguments["target_db"], arguments["clone_options"])

            elif name == "mask_data":
                result = await self.database_manager._mask_data(arguments["table_name"], arguments["masking_rules"])

            elif name == "monitor_health":
                result = await self.database_manager._monitor_health()

            elif name == "monitor_queries":
                result = await self.database_manager._monitor_queries()

            elif name == "log_queries":
                result = await self.database_manager._log_queries(arguments.get("enable", True))

            elif name == "enable_audit_log":
                result = await self.database_manager._enable_audit_log(arguments["audit_config"])

            elif name == "log_schema_changes":
                result = await self.database_manager._log_schema_changes(arguments.get("enable", True))

            elif name == "compare_schemas":
                result = await self.database_manager._compare_schemas(arguments["source_schema"], arguments["target_schema"])

            elif name == "drop_table":
                result = await self.database_manager.drop_table(arguments["database_name"], arguments["table_name"], arguments.get("cascade", False))

            elif name == "restart_database":
                result = await self.database_manager._restart_database()

            elif name == "get_connection_string":
                result = await self.database_manager._get_connection_string()

            elif name == "connect_database":
                result = await self.database_manager.connect_database(arguments["database_type"], arguments["connection_string"], arguments.get("connection_name"))

            # Advanced replication handlers
            elif name == "enable_replication":
                result = await self.database_manager._enable_replication(arguments["replication_config"])

            elif name == "pause_replication":
                result = await self.database_manager._pause_replication(arguments.get("channel_name"))

            elif name == "resume_replication":
                result = await self.database_manager._resume_replication(arguments.get("channel_name"))

            elif name == "check_replication_status":
                result = await self.database_manager._check_replication_status()

            # Advanced sharding handlers
            elif name == "setup_sharding":
                result = await self.database_manager._setup_sharding(arguments["sharding_config"])

            elif name == "rebalance_shards":
                result = await self.database_manager._rebalance_shards(arguments["rebalance_config"])

            elif name == "add_shard":
                result = await self.database_manager._add_shard(arguments["shard_config"])

            elif name == "remove_shard":
                result = await self.database_manager._remove_shard(arguments["shard_name"], arguments.get("safe_mode", True))

            # Views and materialized views handlers
            elif name == "create_view":
                result = await self.database_manager._create_view(arguments["view_name"], arguments["query"], arguments.get("materialized", False))

            elif name == "drop_view":
                result = await self.database_manager._drop_view(arguments["view_name"], arguments.get("cascade", False))

            elif name == "refresh_materialized_view":
                result = await self.database_manager._refresh_materialized_view(arguments["view_name"])

            # Triggers handlers
            elif name == "create_trigger":
                result = await self.database_manager._create_trigger(arguments["trigger_name"], arguments["table_name"], arguments["event"], arguments["timing"], arguments["action"])

            elif name == "drop_trigger":
                result = await self.database_manager._drop_trigger(arguments["trigger_name"], arguments.get("table_name"))

            # Functions and procedures handlers
            elif name == "create_function":
                result = await self.database_manager._create_function(arguments["function_name"], arguments["parameters"], arguments["return_type"], arguments["body"])

            elif name == "drop_function":
                result = await self.database_manager._drop_function(arguments["function_name"], arguments.get("cascade", False))

            elif name == "create_procedure":
                result = await self.database_manager._create_procedure(arguments["procedure_name"], arguments["parameters"], arguments["body"])

            elif name == "drop_procedure":
                result = await self.database_manager._drop_procedure(arguments["procedure_name"], arguments.get("cascade", False))

            # Advanced user management handlers
            elif name == "list_users":
                result = await self.database_manager._list_users()

            elif name == "list_roles":
                result = await self.database_manager._list_roles()

            elif name == "assign_role":
                result = await self.database_manager._assign_role(arguments["username"], arguments["role_name"])

            elif name == "revoke_role":
                result = await self.database_manager._revoke_role(arguments["username"], arguments["role_name"])

            elif name == "reset_password":
                result = await self.database_manager._reset_password(arguments["username"], arguments["new_password"])

            elif name == "force_disconnect_user":
                result = await self.database_manager._force_disconnect_user(arguments["username"])

            # Session and lock monitoring handlers
            elif name == "track_session":
                result = await self.database_manager._track_session()

            elif name == "track_locks":
                result = await self.database_manager._track_locks()

            # Documentation generation handlers
            elif name == "generate_er_diagram":
                result = await self.database_manager._generate_er_diagram(arguments.get("output_format", "png"))

            elif name == "generate_schema_doc":
                result = await self.database_manager._generate_schema_doc(arguments.get("output_format", "markdown"))

            # Migration and DevOps handlers
            elif name == "generate_migration_script":
                result = await self.database_manager._generate_migration_script(arguments["target_schema"])

            elif name == "apply_migration_script":
                result = await self.database_manager._apply_migration_script(arguments["migration_script"], arguments.get("dry_run", True))

            # Job scheduling handlers
            elif name == "schedule_sql_job":
                result = await self.database_manager._schedule_sql_job(arguments["job_name"], arguments["sql_command"], arguments["schedule"])

            elif name == "enable_event_scheduler":
                result = await self.database_manager._enable_event_scheduler(arguments.get("enabled", True))

            # Testing and data generation handlers
            elif name == "generate_seed_data":
                result = await self.database_manager._generate_seed_data(arguments["table_name"], arguments["row_count"], arguments["seed_config"])

            elif name == "truncate_table":
                result = await self.database_manager._truncate_table(arguments["table_name"])

            elif name == "archive_old_data":
                result = await self.database_manager._archive_old_data(arguments["table_name"], arguments["cutoff_date"], arguments["archive_table"])

            # Maintenance handlers
            elif name == "rotate_logs":
                result = await self.database_manager._rotate_logs(arguments.get("log_type", "all"))

            elif name == "purge_binary_logs":
                result = await self.database_manager._purge_binary_logs(arguments["before_date"])

            # Resource monitoring handlers
            elif name == "check_disk_usage":
                result = await self.database_manager._check_disk_usage()

            elif name == "check_memory_usage":
                result = await self.database_manager._check_memory_usage()

            # Security handlers
            elif name == "detect_anomalies":
                result = await self.database_manager._detect_anomalies(arguments.get("time_window", "24h"))

            elif name == "enable_firewall":
                result = await self.database_manager._enable_firewall(arguments["firewall_config"])

            elif name == "audit_login_activity":
                result = await self.database_manager._audit_login_activity(arguments.get("time_window", "24h"))

            elif name == "enable_tls_auth":
                result = await self.database_manager._enable_tls_auth(arguments["tls_config"])

            # Optimization handlers
            elif name == "update_statistics":
                result = await self.database_manager._update_statistics(arguments.get("table_name"))

            elif name == "vacuum_table":
                result = await self.database_manager._vacuum_table(arguments["table_name"], arguments.get("full", False))

            elif name == "rebuild_index":
                result = await self.database_manager._rebuild_index(arguments["index_name"], arguments["table_name"])

            elif name == "defragment_table":
                result = await self.database_manager._defragment_table(arguments["table_name"])

            elif name == "compact_storage":
                result = await self.database_manager._compact_storage(arguments.get("collection_name"))

            # Health and setup handlers
            elif name == "run_health_check":
                result = await self.database_manager._run_health_check()

            elif name == "setup_connection_pooling":
                result = await self.database_manager._setup_connection_pooling(arguments["pool_config"])

            # Additional Missing Tool Handlers
            elif name == "backup_table":
                result = await self.database_manager._backup_table(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "backup_user":
                result = await self.database_manager._backup_user(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "backup_role":
                result = await self.database_manager._backup_role(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "backup_index":
                result = await self.database_manager._backup_index(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "backup_view":
                result = await self.database_manager._backup_view(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "backup_function":
                result = await self.database_manager._backup_function(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "backup_trigger":
                result = await self.database_manager._backup_trigger(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "backup_schema":
                result = await self.database_manager._backup_schema(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "backup_replica":
                result = await self.database_manager._backup_replica(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "backup_shard":
                result = await self.database_manager._backup_shard(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "backup_cluster":
                result = await self.database_manager._backup_cluster(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "backup_backup":
                result = await self.database_manager._backup_backup(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "backup_query":
                result = await self.database_manager._backup_query(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "backup_session":
                result = await self.database_manager._backup_session(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "backup_job":
                result = await self.database_manager._backup_job(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "backup_plan":
                result = await self.database_manager._backup_plan(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "backup_cache":
                result = await self.database_manager._backup_cache(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "backup_connection":
                result = await self.database_manager._backup_connection(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "backup_policy":
                result = await self.database_manager._backup_policy(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "backup_constraint":
                result = await self.database_manager._backup_constraint(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "backup_snapshot":
                result = await self.database_manager._backup_snapshot(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "backup_column":
                result = await self.database_manager._backup_column(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "backup_mask":
                result = await self.database_manager._backup_mask(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "backup_log":
                result = await self.database_manager._backup_log(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "backup_metric":
                result = await self.database_manager._backup_metric(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "backup_alert":
                result = await self.database_manager._backup_alert(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "backup_firewall":
                result = await self.database_manager._backup_firewall(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "backup_certificate":
                result = await self.database_manager._backup_certificate(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "backup_plan_baseline":
                result = await self.database_manager._backup_plan_baseline(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "restore_table":
                result = await self.database_manager._restore_table(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "restore_user":
                result = await self.database_manager._restore_user(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "restore_role":
                result = await self.database_manager._restore_role(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "restore_index":
                result = await self.database_manager._restore_index(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "restore_view":
                result = await self.database_manager._restore_view(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "restore_function":
                result = await self.database_manager._restore_function(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "restore_trigger":
                result = await self.database_manager._restore_trigger(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "restore_schema":
                result = await self.database_manager._restore_schema(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "restore_replica":
                result = await self.database_manager._restore_replica(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "restore_shard":
                result = await self.database_manager._restore_shard(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "restore_cluster":
                result = await self.database_manager._restore_cluster(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "restore_backup":
                result = await self.database_manager._restore_backup(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "restore_query":
                result = await self.database_manager._restore_query(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "restore_session":
                result = await self.database_manager._restore_session(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "restore_job":
                result = await self.database_manager._restore_job(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "restore_plan":
                result = await self.database_manager._restore_plan(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "restore_cache":
                result = await self.database_manager._restore_cache(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "restore_connection":
                result = await self.database_manager._restore_connection(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "restore_policy":
                result = await self.database_manager._restore_policy(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "restore_constraint":
                result = await self.database_manager._restore_constraint(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "restore_snapshot":
                result = await self.database_manager._restore_snapshot(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "restore_column":
                result = await self.database_manager._restore_column(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "restore_mask":
                result = await self.database_manager._restore_mask(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "restore_log":
                result = await self.database_manager._restore_log(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "restore_metric":
                result = await self.database_manager._restore_metric(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "restore_alert":
                result = await self.database_manager._restore_alert(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "restore_firewall":
                result = await self.database_manager._restore_firewall(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "restore_certificate":
                result = await self.database_manager._restore_certificate(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "restore_plan_baseline":
                result = await self.database_manager._restore_plan_baseline(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "replicate_table":
                result = await self.database_manager._replicate_table(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "replicate_user":
                result = await self.database_manager._replicate_user(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "replicate_role":
                result = await self.database_manager._replicate_role(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "replicate_index":
                result = await self.database_manager._replicate_index(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "replicate_view":
                result = await self.database_manager._replicate_view(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "replicate_function":
                result = await self.database_manager._replicate_function(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "replicate_trigger":
                result = await self.database_manager._replicate_trigger(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "replicate_schema":
                result = await self.database_manager._replicate_schema(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "replicate_replica":
                result = await self.database_manager._replicate_replica(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "replicate_shard":
                result = await self.database_manager._replicate_shard(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "replicate_cluster":
                result = await self.database_manager._replicate_cluster(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "replicate_backup":
                result = await self.database_manager._replicate_backup(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "replicate_query":
                result = await self.database_manager._replicate_query(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "replicate_session":
                result = await self.database_manager._replicate_session(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "replicate_job":
                result = await self.database_manager._replicate_job(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "replicate_plan":
                result = await self.database_manager._replicate_plan(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "replicate_cache":
                result = await self.database_manager._replicate_cache(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "replicate_connection":
                result = await self.database_manager._replicate_connection(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "replicate_policy":
                result = await self.database_manager._replicate_policy(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "replicate_constraint":
                result = await self.database_manager._replicate_constraint(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "replicate_snapshot":
                result = await self.database_manager._replicate_snapshot(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "replicate_column":
                result = await self.database_manager._replicate_column(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "replicate_mask":
                result = await self.database_manager._replicate_mask(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "replicate_log":
                result = await self.database_manager._replicate_log(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "replicate_metric":
                result = await self.database_manager._replicate_metric(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "replicate_alert":
                result = await self.database_manager._replicate_alert(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "replicate_firewall":
                result = await self.database_manager._replicate_firewall(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "replicate_certificate":
                result = await self.database_manager._replicate_certificate(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "replicate_plan_baseline":
                result = await self.database_manager._replicate_plan_baseline(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "configure_table":
                result = await self.database_manager._configure_table(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "configure_user":
                result = await self.database_manager._configure_user(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "configure_role":
                result = await self.database_manager._configure_role(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "configure_index":
                result = await self.database_manager._configure_index(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "configure_view":
                result = await self.database_manager._configure_view(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "configure_function":
                result = await self.database_manager._configure_function(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "configure_trigger":
                result = await self.database_manager._configure_trigger(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "configure_schema":
                result = await self.database_manager._configure_schema(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "configure_replica":
                result = await self.database_manager._configure_replica(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "configure_shard":
                result = await self.database_manager._configure_shard(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "configure_cluster":
                result = await self.database_manager._configure_cluster(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "configure_backup":
                result = await self.database_manager._configure_backup(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "configure_query":
                result = await self.database_manager._configure_query(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "configure_session":
                result = await self.database_manager._configure_session(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "configure_job":
                result = await self.database_manager._configure_job(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "configure_plan":
                result = await self.database_manager._configure_plan(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "configure_cache":
                result = await self.database_manager._configure_cache(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "configure_connection":
                result = await self.database_manager._configure_connection(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "configure_policy":
                result = await self.database_manager._configure_policy(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "configure_constraint":
                result = await self.database_manager._configure_constraint(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "configure_snapshot":
                result = await self.database_manager._configure_snapshot(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "configure_column":
                result = await self.database_manager._configure_column(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "configure_mask":
                result = await self.database_manager._configure_mask(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "configure_log":
                result = await self.database_manager._configure_log(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "configure_metric":
                result = await self.database_manager._configure_metric(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "configure_alert":
                result = await self.database_manager._configure_alert(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "configure_firewall":
                result = await self.database_manager._configure_firewall(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "configure_certificate":
                result = await self.database_manager._configure_certificate(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "configure_plan_baseline":
                result = await self.database_manager._configure_plan_baseline(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "reset_table":
                result = await self.database_manager._reset_table(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "reset_user":
                result = await self.database_manager._reset_user(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "reset_role":
                result = await self.database_manager._reset_role(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "reset_index":
                result = await self.database_manager._reset_index(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "reset_view":
                result = await self.database_manager._reset_view(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "reset_function":
                result = await self.database_manager._reset_function(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "reset_trigger":
                result = await self.database_manager._reset_trigger(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "reset_schema":
                result = await self.database_manager._reset_schema(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "reset_replica":
                result = await self.database_manager._reset_replica(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "reset_shard":
                result = await self.database_manager._reset_shard(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "reset_cluster":
                result = await self.database_manager._reset_cluster(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "reset_backup":
                result = await self.database_manager._reset_backup(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "reset_query":
                result = await self.database_manager._reset_query(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "reset_session":
                result = await self.database_manager._reset_session(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "reset_job":
                result = await self.database_manager._reset_job(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "reset_plan":
                result = await self.database_manager._reset_plan(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "reset_cache":
                result = await self.database_manager._reset_cache(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "reset_connection":
                result = await self.database_manager._reset_connection(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "reset_policy":
                result = await self.database_manager._reset_policy(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "reset_constraint":
                result = await self.database_manager._reset_constraint(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "reset_snapshot":
                result = await self.database_manager._reset_snapshot(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "reset_column":
                result = await self.database_manager._reset_column(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "reset_mask":
                result = await self.database_manager._reset_mask(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "reset_log":
                result = await self.database_manager._reset_log(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "reset_metric":
                result = await self.database_manager._reset_metric(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "reset_alert":
                result = await self.database_manager._reset_alert(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "reset_firewall":
                result = await self.database_manager._reset_firewall(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "reset_certificate":
                result = await self.database_manager._reset_certificate(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "reset_plan_baseline":
                result = await self.database_manager._reset_plan_baseline(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "rotate_table":
                result = await self.database_manager._rotate_table(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "rotate_user":
                result = await self.database_manager._rotate_user(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "rotate_role":
                result = await self.database_manager._rotate_role(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "rotate_index":
                result = await self.database_manager._rotate_index(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "rotate_view":
                result = await self.database_manager._rotate_view(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "rotate_function":
                result = await self.database_manager._rotate_function(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "rotate_trigger":
                result = await self.database_manager._rotate_trigger(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "rotate_schema":
                result = await self.database_manager._rotate_schema(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "rotate_replica":
                result = await self.database_manager._rotate_replica(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "rotate_shard":
                result = await self.database_manager._rotate_shard(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "rotate_cluster":
                result = await self.database_manager._rotate_cluster(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "rotate_backup":
                result = await self.database_manager._rotate_backup(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "rotate_query":
                result = await self.database_manager._rotate_query(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "rotate_session":
                result = await self.database_manager._rotate_session(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "rotate_job":
                result = await self.database_manager._rotate_job(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "rotate_plan":
                result = await self.database_manager._rotate_plan(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "rotate_cache":
                result = await self.database_manager._rotate_cache(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "rotate_connection":
                result = await self.database_manager._rotate_connection(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "rotate_policy":
                result = await self.database_manager._rotate_policy(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "rotate_constraint":
                result = await self.database_manager._rotate_constraint(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "rotate_snapshot":
                result = await self.database_manager._rotate_snapshot(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "rotate_column":
                result = await self.database_manager._rotate_column(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "rotate_mask":
                result = await self.database_manager._rotate_mask(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "rotate_log":
                result = await self.database_manager._rotate_log(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "rotate_metric":
                result = await self.database_manager._rotate_metric(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "rotate_alert":
                result = await self.database_manager._rotate_alert(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "rotate_firewall":
                result = await self.database_manager._rotate_firewall(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "rotate_certificate":
                result = await self.database_manager._rotate_certificate(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "rotate_plan_baseline":
                result = await self.database_manager._rotate_plan_baseline(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "schedule_user":
                result = await self.database_manager._schedule_user(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "schedule_role":
                result = await self.database_manager._schedule_role(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "schedule_index":
                result = await self.database_manager._schedule_index(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "schedule_view":
                result = await self.database_manager._schedule_view(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "schedule_function":
                result = await self.database_manager._schedule_function(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "schedule_trigger":
                result = await self.database_manager._schedule_trigger(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "schedule_schema":
                result = await self.database_manager._schedule_schema(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "schedule_replica":
                result = await self.database_manager._schedule_replica(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "schedule_shard":
                result = await self.database_manager._schedule_shard(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "schedule_cluster":
                result = await self.database_manager._schedule_cluster(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "schedule_session":
                result = await self.database_manager._schedule_session(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "schedule_job":
                result = await self.database_manager._schedule_job(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "schedule_plan":
                result = await self.database_manager._schedule_plan(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "schedule_cache":
                result = await self.database_manager._schedule_cache(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "schedule_connection":
                result = await self.database_manager._schedule_connection(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "schedule_policy":
                result = await self.database_manager._schedule_policy(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "schedule_constraint":
                result = await self.database_manager._schedule_constraint(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "schedule_snapshot":
                result = await self.database_manager._schedule_snapshot(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "schedule_column":
                result = await self.database_manager._schedule_column(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "schedule_mask":
                result = await self.database_manager._schedule_mask(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "schedule_log":
                result = await self.database_manager._schedule_log(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "schedule_metric":
                result = await self.database_manager._schedule_metric(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "schedule_alert":
                result = await self.database_manager._schedule_alert(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "schedule_firewall":
                result = await self.database_manager._schedule_firewall(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "schedule_certificate":
                result = await self.database_manager._schedule_certificate(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "schedule_plan_baseline":
                result = await self.database_manager._schedule_plan_baseline(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "optimize_user":
                result = await self.database_manager._optimize_user(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "optimize_role":
                result = await self.database_manager._optimize_role(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "optimize_index":
                result = await self.database_manager._optimize_index(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "optimize_view":
                result = await self.database_manager._optimize_view(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "optimize_function":
                result = await self.database_manager._optimize_function(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "optimize_trigger":
                result = await self.database_manager._optimize_trigger(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "optimize_schema":
                result = await self.database_manager._optimize_schema(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "optimize_replica":
                result = await self.database_manager._optimize_replica(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "optimize_shard":
                result = await self.database_manager._optimize_shard(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "optimize_cluster":
                result = await self.database_manager._optimize_cluster(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "optimize_backup":
                result = await self.database_manager._optimize_backup(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "optimize_session":
                result = await self.database_manager._optimize_session(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "optimize_job":
                result = await self.database_manager._optimize_job(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "optimize_plan":
                result = await self.database_manager._optimize_plan(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "optimize_cache":
                result = await self.database_manager._optimize_cache(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "optimize_connection":
                result = await self.database_manager._optimize_connection(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "optimize_policy":
                result = await self.database_manager._optimize_policy(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "optimize_constraint":
                result = await self.database_manager._optimize_constraint(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "optimize_snapshot":
                result = await self.database_manager._optimize_snapshot(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "optimize_column":
                result = await self.database_manager._optimize_column(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "optimize_mask":
                result = await self.database_manager._optimize_mask(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "optimize_log":
                result = await self.database_manager._optimize_log(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "optimize_metric":
                result = await self.database_manager._optimize_metric(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "optimize_alert":
                result = await self.database_manager._optimize_alert(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "optimize_firewall":
                result = await self.database_manager._optimize_firewall(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "optimize_certificate":
                result = await self.database_manager._optimize_certificate(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "optimize_plan_baseline":
                result = await self.database_manager._optimize_plan_baseline(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "analyze_user":
                result = await self.database_manager._analyze_user(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "analyze_role":
                result = await self.database_manager._analyze_role(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "analyze_index":
                result = await self.database_manager._analyze_index(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "analyze_view":
                result = await self.database_manager._analyze_view(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "analyze_function":
                result = await self.database_manager._analyze_function(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "analyze_trigger":
                result = await self.database_manager._analyze_trigger(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "analyze_schema":
                result = await self.database_manager._analyze_schema(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "analyze_replica":
                result = await self.database_manager._analyze_replica(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "analyze_shard":
                result = await self.database_manager._analyze_shard(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "analyze_cluster":
                result = await self.database_manager._analyze_cluster(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "analyze_backup":
                result = await self.database_manager._analyze_backup(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "analyze_session":
                result = await self.database_manager._analyze_session(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "analyze_job":
                result = await self.database_manager._analyze_job(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "analyze_plan":
                result = await self.database_manager._analyze_plan(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "analyze_cache":
                result = await self.database_manager._analyze_cache(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "analyze_connection":
                result = await self.database_manager._analyze_connection(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "analyze_policy":
                result = await self.database_manager._analyze_policy(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "analyze_constraint":
                result = await self.database_manager._analyze_constraint(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "analyze_snapshot":
                result = await self.database_manager._analyze_snapshot(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "analyze_column":
                result = await self.database_manager._analyze_column(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "analyze_mask":
                result = await self.database_manager._analyze_mask(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "analyze_log":
                result = await self.database_manager._analyze_log(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "analyze_metric":
                result = await self.database_manager._analyze_metric(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "analyze_alert":
                result = await self.database_manager._analyze_alert(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "analyze_firewall":
                result = await self.database_manager._analyze_firewall(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "analyze_certificate":
                result = await self.database_manager._analyze_certificate(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "analyze_plan_baseline":
                result = await self.database_manager._analyze_plan_baseline(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "migrate_user":
                result = await self.database_manager._migrate_user(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "migrate_role":
                result = await self.database_manager._migrate_role(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "migrate_index":
                result = await self.database_manager._migrate_index(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "migrate_view":
                result = await self.database_manager._migrate_view(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "migrate_function":
                result = await self.database_manager._migrate_function(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "migrate_trigger":
                result = await self.database_manager._migrate_trigger(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "migrate_replica":
                result = await self.database_manager._migrate_replica(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "migrate_shard":
                result = await self.database_manager._migrate_shard(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "migrate_cluster":
                result = await self.database_manager._migrate_cluster(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "migrate_backup":
                result = await self.database_manager._migrate_backup(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "migrate_query":
                result = await self.database_manager._migrate_query(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "migrate_session":
                result = await self.database_manager._migrate_session(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "migrate_job":
                result = await self.database_manager._migrate_job(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "migrate_plan":
                result = await self.database_manager._migrate_plan(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "migrate_cache":
                result = await self.database_manager._migrate_cache(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "migrate_connection":
                result = await self.database_manager._migrate_connection(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "migrate_policy":
                result = await self.database_manager._migrate_policy(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "migrate_constraint":
                result = await self.database_manager._migrate_constraint(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "migrate_snapshot":
                result = await self.database_manager._migrate_snapshot(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "migrate_column":
                result = await self.database_manager._migrate_column(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "migrate_mask":
                result = await self.database_manager._migrate_mask(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "migrate_log":
                result = await self.database_manager._migrate_log(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "migrate_metric":
                result = await self.database_manager._migrate_metric(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "migrate_alert":
                result = await self.database_manager._migrate_alert(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "migrate_firewall":
                result = await self.database_manager._migrate_firewall(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "migrate_certificate":
                result = await self.database_manager._migrate_certificate(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "migrate_plan_baseline":
                result = await self.database_manager._migrate_plan_baseline(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )

            # Extended Context-Specific Tool Handlers
            elif name == "create_database":
                result = await self.database_manager._create_database(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "create_table":
                result = await self.database_manager._create_table(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "create_user":
                result = await self.database_manager._create_user(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "create_role":
                result = await self.database_manager._create_role(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "create_index":
                result = await self.database_manager._create_index(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "create_schema":
                result = await self.database_manager._create_schema(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "create_replica":
                result = await self.database_manager._create_replica(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "create_shard":
                result = await self.database_manager._create_shard(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "create_cluster":
                result = await self.database_manager._create_cluster(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "create_backup":
                result = await self.database_manager._create_backup(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "create_query":
                result = await self.database_manager._create_query(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "create_session":
                result = await self.database_manager._create_session(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "create_job":
                result = await self.database_manager._create_job(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "create_plan":
                result = await self.database_manager._create_plan(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "create_cache":
                result = await self.database_manager._create_cache(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "create_connection":
                result = await self.database_manager._create_connection(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "create_policy":
                result = await self.database_manager._create_policy(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "create_constraint":
                result = await self.database_manager._create_constraint(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "create_snapshot":
                result = await self.database_manager._create_snapshot(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "create_column":
                result = await self.database_manager._create_column(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "create_mask":
                result = await self.database_manager._create_mask(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "create_log":
                result = await self.database_manager._create_log(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "create_metric":
                result = await self.database_manager._create_metric(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "create_alert":
                result = await self.database_manager._create_alert(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "create_firewall":
                result = await self.database_manager._create_firewall(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "create_certificate":
                result = await self.database_manager._create_certificate(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "create_plan_baseline":
                result = await self.database_manager._create_plan_baseline(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "delete_database":
                result = await self.database_manager._delete_database(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "delete_table":
                result = await self.database_manager._delete_table(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "delete_user":
                result = await self.database_manager._delete_user(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "delete_role":
                result = await self.database_manager._delete_role(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "delete_index":
                result = await self.database_manager._delete_index(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "delete_view":
                result = await self.database_manager._delete_view(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "delete_function":
                result = await self.database_manager._delete_function(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "delete_trigger":
                result = await self.database_manager._delete_trigger(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "delete_schema":
                result = await self.database_manager._delete_schema(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "delete_replica":
                result = await self.database_manager._delete_replica(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "delete_shard":
                result = await self.database_manager._delete_shard(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "delete_cluster":
                result = await self.database_manager._delete_cluster(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "delete_backup":
                result = await self.database_manager._delete_backup(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "delete_query":
                result = await self.database_manager._delete_query(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "delete_session":
                result = await self.database_manager._delete_session(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "delete_job":
                result = await self.database_manager._delete_job(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "delete_plan":
                result = await self.database_manager._delete_plan(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "delete_cache":
                result = await self.database_manager._delete_cache(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "delete_connection":
                result = await self.database_manager._delete_connection(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "delete_policy":
                result = await self.database_manager._delete_policy(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "delete_constraint":
                result = await self.database_manager._delete_constraint(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "delete_snapshot":
                result = await self.database_manager._delete_snapshot(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "delete_column":
                result = await self.database_manager._delete_column(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "delete_mask":
                result = await self.database_manager._delete_mask(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "delete_log":
                result = await self.database_manager._delete_log(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "delete_metric":
                result = await self.database_manager._delete_metric(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "delete_alert":
                result = await self.database_manager._delete_alert(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "delete_firewall":
                result = await self.database_manager._delete_firewall(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "delete_certificate":
                result = await self.database_manager._delete_certificate(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "delete_plan_baseline":
                result = await self.database_manager._delete_plan_baseline(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "update_database":
                result = await self.database_manager._update_database(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "update_table":
                result = await self.database_manager._update_table(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "update_user":
                result = await self.database_manager._update_user(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "update_role":
                result = await self.database_manager._update_role(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "update_index":
                result = await self.database_manager._update_index(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "update_view":
                result = await self.database_manager._update_view(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "update_function":
                result = await self.database_manager._update_function(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "update_trigger":
                result = await self.database_manager._update_trigger(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "update_schema":
                result = await self.database_manager._update_schema(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "update_replica":
                result = await self.database_manager._update_replica(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "update_shard":
                result = await self.database_manager._update_shard(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "update_cluster":
                result = await self.database_manager._update_cluster(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "update_backup":
                result = await self.database_manager._update_backup(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "update_query":
                result = await self.database_manager._update_query(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "update_session":
                result = await self.database_manager._update_session(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "update_job":
                result = await self.database_manager._update_job(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "update_plan":
                result = await self.database_manager._update_plan(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "update_cache":
                result = await self.database_manager._update_cache(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "update_connection":
                result = await self.database_manager._update_connection(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "update_policy":
                result = await self.database_manager._update_policy(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "update_constraint":
                result = await self.database_manager._update_constraint(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "update_snapshot":
                result = await self.database_manager._update_snapshot(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "update_column":
                result = await self.database_manager._update_column(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "update_mask":
                result = await self.database_manager._update_mask(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "update_log":
                result = await self.database_manager._update_log(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "update_metric":
                result = await self.database_manager._update_metric(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "update_alert":
                result = await self.database_manager._update_alert(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "update_firewall":
                result = await self.database_manager._update_firewall(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "update_certificate":
                result = await self.database_manager._update_certificate(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "update_plan_baseline":
                result = await self.database_manager._update_plan_baseline(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "enable_database":
                result = await self.database_manager._enable_database(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "enable_table":
                result = await self.database_manager._enable_table(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "enable_user":
                result = await self.database_manager._enable_user(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "enable_role":
                result = await self.database_manager._enable_role(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "enable_index":
                result = await self.database_manager._enable_index(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "enable_view":
                result = await self.database_manager._enable_view(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "enable_function":
                result = await self.database_manager._enable_function(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "enable_trigger":
                result = await self.database_manager._enable_trigger(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "enable_schema":
                result = await self.database_manager._enable_schema(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "enable_replica":
                result = await self.database_manager._enable_replica(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "enable_shard":
                result = await self.database_manager._enable_shard(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "enable_cluster":
                result = await self.database_manager._enable_cluster(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "enable_backup":
                result = await self.database_manager._enable_backup(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "enable_query":
                result = await self.database_manager._enable_query(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "enable_session":
                result = await self.database_manager._enable_session(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "enable_job":
                result = await self.database_manager._enable_job(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "enable_plan":
                result = await self.database_manager._enable_plan(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "enable_cache":
                result = await self.database_manager._enable_cache(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "enable_connection":
                result = await self.database_manager._enable_connection(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "enable_policy":
                result = await self.database_manager._enable_policy(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "enable_constraint":
                result = await self.database_manager._enable_constraint(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "enable_snapshot":
                result = await self.database_manager._enable_snapshot(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "enable_column":
                result = await self.database_manager._enable_column(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "enable_mask":
                result = await self.database_manager._enable_mask(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "enable_log":
                result = await self.database_manager._enable_log(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "enable_metric":
                result = await self.database_manager._enable_metric(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "enable_alert":
                result = await self.database_manager._enable_alert(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "enable_firewall":
                result = await self.database_manager._enable_firewall(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "enable_certificate":
                result = await self.database_manager._enable_certificate(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "enable_plan_baseline":
                result = await self.database_manager._enable_plan_baseline(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "disable_database":
                result = await self.database_manager._disable_database(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "disable_table":
                result = await self.database_manager._disable_table(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "disable_user":
                result = await self.database_manager._disable_user(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "disable_role":
                result = await self.database_manager._disable_role(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "disable_index":
                result = await self.database_manager._disable_index(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "disable_view":
                result = await self.database_manager._disable_view(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "disable_function":
                result = await self.database_manager._disable_function(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "disable_trigger":
                result = await self.database_manager._disable_trigger(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "disable_schema":
                result = await self.database_manager._disable_schema(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "disable_replica":
                result = await self.database_manager._disable_replica(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "disable_shard":
                result = await self.database_manager._disable_shard(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "disable_cluster":
                result = await self.database_manager._disable_cluster(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "disable_backup":
                result = await self.database_manager._disable_backup(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "disable_query":
                result = await self.database_manager._disable_query(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "disable_session":
                result = await self.database_manager._disable_session(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "disable_job":
                result = await self.database_manager._disable_job(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "disable_plan":
                result = await self.database_manager._disable_plan(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "disable_cache":
                result = await self.database_manager._disable_cache(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "disable_connection":
                result = await self.database_manager._disable_connection(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "disable_policy":
                result = await self.database_manager._disable_policy(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "disable_constraint":
                result = await self.database_manager._disable_constraint(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "disable_snapshot":
                result = await self.database_manager._disable_snapshot(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "disable_column":
                result = await self.database_manager._disable_column(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "disable_mask":
                result = await self.database_manager._disable_mask(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "disable_log":
                result = await self.database_manager._disable_log(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "disable_metric":
                result = await self.database_manager._disable_metric(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "disable_alert":
                result = await self.database_manager._disable_alert(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "disable_firewall":
                result = await self.database_manager._disable_firewall(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "disable_certificate":
                result = await self.database_manager._disable_certificate(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "disable_plan_baseline":
                result = await self.database_manager._disable_plan_baseline(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "list_database":
                result = await self.database_manager._list_database(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "list_table":
                result = await self.database_manager._list_table(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "list_user":
                result = await self.database_manager._list_user(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "list_role":
                result = await self.database_manager._list_role(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "list_index":
                result = await self.database_manager._list_index(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "list_view":
                result = await self.database_manager._list_view(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "list_function":
                result = await self.database_manager._list_function(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "list_trigger":
                result = await self.database_manager._list_trigger(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "list_schema":
                result = await self.database_manager._list_schema(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "list_replica":
                result = await self.database_manager._list_replica(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "list_shard":
                result = await self.database_manager._list_shard(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "list_cluster":
                result = await self.database_manager._list_cluster(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "list_backup":
                result = await self.database_manager._list_backup(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "list_query":
                result = await self.database_manager._list_query(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "list_session":
                result = await self.database_manager._list_session(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "list_job":
                result = await self.database_manager._list_job(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "list_plan":
                result = await self.database_manager._list_plan(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "list_cache":
                result = await self.database_manager._list_cache(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "list_connection":
                result = await self.database_manager._list_connection(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "list_policy":
                result = await self.database_manager._list_policy(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "list_constraint":
                result = await self.database_manager._list_constraint(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "list_snapshot":
                result = await self.database_manager._list_snapshot(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "list_column":
                result = await self.database_manager._list_column(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "list_mask":
                result = await self.database_manager._list_mask(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "list_log":
                result = await self.database_manager._list_log(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "list_metric":
                result = await self.database_manager._list_metric(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "list_alert":
                result = await self.database_manager._list_alert(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "list_firewall":
                result = await self.database_manager._list_firewall(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "list_certificate":
                result = await self.database_manager._list_certificate(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "list_plan_baseline":
                result = await self.database_manager._list_plan_baseline(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "monitor_database":
                result = await self.database_manager._monitor_database(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "monitor_table":
                result = await self.database_manager._monitor_table(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "monitor_user":
                result = await self.database_manager._monitor_user(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "monitor_role":
                result = await self.database_manager._monitor_role(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "monitor_index":
                result = await self.database_manager._monitor_index(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "monitor_view":
                result = await self.database_manager._monitor_view(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "monitor_function":
                result = await self.database_manager._monitor_function(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "monitor_trigger":
                result = await self.database_manager._monitor_trigger(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "monitor_schema":
                result = await self.database_manager._monitor_schema(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "monitor_replica":
                result = await self.database_manager._monitor_replica(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "monitor_shard":
                result = await self.database_manager._monitor_shard(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "monitor_cluster":
                result = await self.database_manager._monitor_cluster(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "monitor_backup":
                result = await self.database_manager._monitor_backup(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "monitor_query":
                result = await self.database_manager._monitor_query(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "monitor_session":
                result = await self.database_manager._monitor_session(
                    arguments["name"],
                    arguments.get("observability_config", {})
                )
            elif name == "monitor_job":
                result = await self.database_manager._monitor_job(
                    arguments["name"],
                    arguments.get("optimization_config", {})
                )
            elif name == "monitor_plan":
                result = await self.database_manager._monitor_plan(
                    arguments["name"],
                    arguments.get("automation_config", {})
                )
            elif name == "monitor_cache":
                result = await self.database_manager._monitor_cache(
                    arguments["name"],
                    arguments.get("maintenance_config", {})
                )
            elif name == "monitor_connection":
                result = await self.database_manager._monitor_connection(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "monitor_policy":
                result = await self.database_manager._monitor_policy(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "monitor_constraint":
                result = await self.database_manager._monitor_constraint(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            elif name == "monitor_snapshot":
                result = await self.database_manager._monitor_snapshot(
                    arguments["name"],
                    arguments.get("performance_config", {})
                )
            elif name == "monitor_column":
                result = await self.database_manager._monitor_column(
                    arguments["name"],
                    arguments.get("backup_config", {})
                )
            elif name == "monitor_mask":
                result = await self.database_manager._monitor_mask(
                    arguments["name"],
                    arguments.get("monitoring_config", {})
                )
            elif name == "monitor_log":
                result = await self.database_manager._monitor_log(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "monitor_metric":
                result = await self.database_manager._monitor_metric(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "monitor_alert":
                result = await self.database_manager._monitor_alert(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "monitor_firewall":
                result = await self.database_manager._monitor_firewall(
                    arguments["name"],
                    arguments.get("sharding_config", {})
                )
            elif name == "monitor_certificate":
                result = await self.database_manager._monitor_certificate(
                    arguments["name"],
                    arguments.get("compliance_config", {})
                )
            elif name == "monitor_plan_baseline":
                result = await self.database_manager._monitor_plan_baseline(
                    arguments["name"],
                    arguments.get("ai_ml_config", {})
                )
            elif name == "schedule_database":
                result = await self.database_manager._schedule_database(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "schedule_table":
                result = await self.database_manager._schedule_table(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "schedule_backup":
                result = await self.database_manager._schedule_backup(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "schedule_query":
                result = await self.database_manager._schedule_query(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "optimize_database":
                result = await self.database_manager._optimize_database(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "optimize_table":
                result = await self.database_manager._optimize_table(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "optimize_query":
                result = await self.database_manager._optimize_query(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "analyze_database":
                result = await self.database_manager._analyze_database(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "analyze_table":
                result = await self.database_manager._analyze_table(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "analyze_query":
                result = await self.database_manager._analyze_query(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "migrate_database":
                result = await self.database_manager._migrate_database(
                    arguments["name"],
                    arguments.get("provisioning_config", {})
                )
            elif name == "migrate_table":
                result = await self.database_manager._migrate_table(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "migrate_schema":
                result = await self.database_manager._migrate_schema(
                    arguments["name"],
                    arguments.get("replication_config", {})
                )
            elif name == "audit_database":
                result = await self.database_manager._audit_database(
                    arguments["name"],
                    arguments.get("audit_config", {})
                )
            elif name == "audit_table":
                result = await self.database_manager._audit_table(
                    arguments["name"],
                    arguments.get("devops_config", {})
                )
            elif name == "audit_query":
                result = await self.database_manager._audit_query(
                    arguments["name"],
                    arguments.get("security_config", {})
                )
            elif name == "setup_database":
                result = await self.database_manager._setup_database(
                    arguments["name"],
                    arguments.get("testing_config", {})
                )
            elif name == "setup_table":
                result = await self.database_manager._setup_table(
                    arguments["name"],
                    arguments.get("data_migration_config", {})
                )
            elif name == "setup_schema":
                result = await self.database_manager._setup_schema(
                    arguments["name"],
                    arguments.get("schema_config", {})
                )
            
            # Missing handlers
            elif name == "alter_table":
                result = await self.database_manager.alter_table(
                    arguments["database_name"],
                    arguments["table_name"],
                    arguments["alterations"]
                )
            
            elif name == "analyze_performance":
                result = await self.database_manager.analyze_performance(
                    arguments["database_name"],
                    arguments.get("query"),
                    arguments.get("include_execution_plan", True)
                )
            
            elif name == "drop_index":
                result = await self.database_manager.drop_index(
                    arguments["database_name"],
                    arguments["index_name"],
                    arguments.get("table_name")
                )
            
            elif name == "grant_permissions":
                result = await self.database_manager.grant_permissions(
                    arguments["database_name"],
                    arguments["username"],
                    arguments["permissions"],
                    arguments.get("table_name")
                )

            else:
                # Route to database manager for other operations
                result = await self.database_manager.handle_tool_call(name, arguments)
                
            return [types.TextContent(
                type="text",
                text=str(result)
            )]
            
        except Exception as e:
            logger.error(f"Error handling tool call {name}: {e}")
            await self.audit_logger.log_error(name, arguments, str(e))
            raise
            
    async def list_prompts(self) -> List[types.Prompt]:
        """List available prompts"""
        return [
            types.Prompt(
                name="database_design",
                description="Help design database schema",
                arguments=[
                    types.PromptArgument(
                        name="requirements",
                        description="Database requirements",
                        required=True
                    )
                ]
            ),
            types.Prompt(
                name="query_optimization",
                description="Optimize database queries",
                arguments=[
                    types.PromptArgument(
                        name="query",
                        description="Query to optimize",
                        required=True
                    ),
                    types.PromptArgument(
                        name="database_type",
                        description="Database type",
                        required=True
                    )
                ]
            ),
            types.Prompt(
                name="migration_planning",
                description="Plan database migration",
                arguments=[
                    types.PromptArgument(
                        name="source_schema",
                        description="Source schema",
                        required=True
                    ),
                    types.PromptArgument(
                        name="target_schema",
                        description="Target schema",
                        required=True
                    )
                ]
            )
        ]
        
    async def get_prompt(self, name: str, arguments: Dict[str, str]) -> types.GetPromptResult:
        """Get a specific prompt"""
        if name == "database_design":
            return types.GetPromptResult(
                description="Database design assistant",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"Help me design a database schema for: {arguments['requirements']}"
                        )
                    )
                ]
            )
            
        elif name == "query_optimization":
            return types.GetPromptResult(
                description="Query optimization assistant",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"Optimize this {arguments['database_type']} query: {arguments['query']}"
                        )
                    )
                ]
            )
            
        elif name == "migration_planning":
            return types.GetPromptResult(
                description="Migration planning assistant",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"Plan migration from {arguments['source_schema']} to {arguments['target_schema']}"
                        )
                    )
                ]
            )
            
        else:
            raise ValueError(f"Unknown prompt: {name}")

async def main():
    """Main server entry point"""
    config_file = os.getenv("DATABASE_CONFIG_FILE", "config/database.yaml")
    
    # Initialize server
    server = DatabaseMCPServer(config_file)
    
    # Initialize database manager
    await server.database_manager.initialize()
    
    # Start server
    async with stdio_server() as (read_stream, write_stream):
        await server.server.run(
            read_stream,
            write_stream,
            server.server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
