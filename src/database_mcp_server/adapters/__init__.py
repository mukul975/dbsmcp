"""
Database adapters for different database systems
"""

from .base_adapter import BaseAdapter, QueryResult
from .mysql_adapter import MySQLAdapter
from .postgresql_adapter import PostgreSQLAdapter
from .mongodb_adapter import MongoDBAdapter
from .sqlite_adapter import SQLiteAdapter
from .redis_adapter import RedisAdapter

__all__ = [
    'BaseAdapter',
    'QueryResult',
    'MySQLAdapter',
    'PostgreSQLAdapter',
    'MongoDBAdapter',
    'SQLiteAdapter',
    'RedisAdapter'
]
