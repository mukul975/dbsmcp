"""
SQLite adapter for database operations
"""

from typing import Dict, List, Any, Optional
import aiosqlite
import os
import time
from .base_adapter import BaseAdapter, QueryResult

class SQLiteAdapter(BaseAdapter):
    """SQLite Adapter Implementation"""
    
    async def connect(self) -> None:
        """Connect to SQLite database"""
        connection_params = self._parse_connection_string(self.connection_string)
        database_path = connection_params['database']
        
        # Create directory if it doesn't exist and path has a directory
        db_dir = os.path.dirname(database_path)
        if db_dir and db_dir != '':
            os.makedirs(db_dir, exist_ok=True)
        
        self.connection = await aiosqlite.connect(database_path)
        self.connection.row_factory = aiosqlite.Row
    
    async def disconnect(self) -> None:
        """Disconnect from SQLite database"""
        if self.connection:
            await self.connection.close()
    
    async def execute_query(self, query: str, parameters: Optional[List[Any]] = None, explain: bool = False) -> QueryResult:
        """Execute a SQLite query"""
        start_time = time.time()
        
        try:
            sanitized_query = self._sanitize_query(query)
            
            async with self.connection.execute(sanitized_query, parameters or []) as cursor:
                data = await cursor.fetchall()
                columns = [description[0] for description in cursor.description] if cursor.description else []
                rows_affected = cursor.rowcount
                
                # Convert Row objects to dictionaries
                data_dict = [dict(row) for row in data]
                
                explain_plan = None
                if explain:
                    explain_query = f"EXPLAIN QUERY PLAN {sanitized_query}"
                    async with self.connection.execute(explain_query, parameters or []) as explain_cursor:
                        explain_data = await explain_cursor.fetchall()
                        explain_plan = [dict(row) for row in explain_data]
                
                execution_time = self._measure_execution_time(start_time)
                self._log_query(query, parameters, execution_time)
                
                return QueryResult(
                    data=data_dict,
                    columns=columns,
                    rows_affected=rows_affected,
                    execution_time=execution_time,
                    explain_plan=explain_plan
                )
        except Exception as e:
            execution_time = self._measure_execution_time(start_time)
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=execution_time,
                error=self._format_error(e)
            )

    async def add_column(self, table_name: str, column_definition: Dict[str, Any]) -> Optional[QueryResult]:
        """Add a column to an SQLite table"""
        column_name = column_definition['name']
        column_type = column_definition['type']
        nullable_clause = "" if column_definition.get('nullable', True) else "NOT NULL"
        default_clause = f"DEFAULT {column_definition['default']}" if 'default' in column_definition else ""
        column_clause = f"{column_name} {column_type} {nullable_clause} {default_clause}"
        query = f"ALTER TABLE {table_name} ADD COLUMN {column_clause}"
        return await self.execute_query(query)

    async def list_tables(self) -> List[str]:
        """List all tables in the SQLite database"""
        query = "SELECT name FROM sqlite_master WHERE type='table'"
        result = await self.execute_query(query)
        return [row['name'] for row in result.data] if result.data else []

    async def describe_table(self, table_name: str) -> Dict[str, Any]:
        """Describe the structure of an SQLite table"""
        query = f"PRAGMA table_info({table_name})"
        result = await self.execute_query(query)
        return {'columns': result.data} if result.data else {'error': 'Table not found or no columns'}
    
    async def create_table(self, table_name: str, columns: List[Dict[str, Any]], constraints: List[Dict[str, Any]] = None) -> Optional[QueryResult]:
        """Create a table in SQLite"""
        columns_clause = self._build_columns_clause(columns)
        constraints_clause = self._build_constraints_clause(constraints)
        
        query = f"CREATE TABLE {table_name} ({columns_clause}{constraints_clause})"
        return await self.execute_query(query)
    
    async def drop_table(self, table_name: str, cascade: bool = False) -> Optional[QueryResult]:
        """Drop a table in SQLite"""
        query = f"DROP TABLE {table_name}"
        return await self.execute_query(query)
    
    async def alter_table(self, table_name: str, alterations: List[Dict[str, Any]]) -> Optional[QueryResult]:
        """Alter table structure in SQLite"""
        # SQLite has limited ALTER TABLE support
        results = []
        for alteration in alterations:
            alter_type = alteration.get('type', '').upper()
            
            if alter_type == 'ADD_COLUMN':
                column_def = f"{alteration['column_name']} {alteration['column_type']}"
                if alteration.get('nullable', True) is False:
                    column_def += " NOT NULL"
                if alteration.get('default'):
                    column_def += f" DEFAULT {alteration['default']}"
                    
                query = f"ALTER TABLE {table_name} ADD COLUMN {column_def}"
                result = await self.execute_query(query)
                results.append(result)
            elif alter_type == 'RENAME_TABLE':
                query = f"ALTER TABLE {table_name} RENAME TO {alteration['new_name']}"
                result = await self.execute_query(query)
                results.append(result)
            else:
                # For other alterations, SQLite requires recreating the table
                return QueryResult(
                    data=[],
                    columns=[],
                    rows_affected=0,
                    execution_time=0.0,
                    error=f"ALTER TABLE {alter_type} not supported in SQLite"
                )
        
        return results[0] if results else None
    
    async def create_index(self, table_name: str, index_name: str, columns: List[str], unique: bool = False) -> Optional[QueryResult]:
        """Create an index in SQLite"""
        unique_clause = "UNIQUE " if unique else ""
        columns_clause = ", ".join(columns)
        
        query = f"CREATE {unique_clause}INDEX {index_name} ON {table_name} ({columns_clause})"
        return await self.execute_query(query)
    
    async def drop_index(self, index_name: str, table_name: Optional[str] = None) -> Optional[QueryResult]:
        """Drop an index in SQLite"""
        query = f"DROP INDEX {index_name}"
        return await self.execute_query(query)
    
    async def insert_data(self, table_name: str, data: List[Dict[str, Any]], on_conflict: str = "error") -> Optional[QueryResult]:
        """Insert data into SQLite table"""
        if not data:
            return None
            
        columns = list(data[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        columns_clause = ", ".join(columns)
        
        conflict_clause = ""
        if on_conflict == "ignore":
            conflict_clause = " OR IGNORE"
        elif on_conflict == "replace":
            conflict_clause = " OR REPLACE"
        
        query = f"INSERT{conflict_clause} INTO {table_name} ({columns_clause}) VALUES ({placeholders})"
        
        # Execute multiple inserts in a transaction
        start_time = time.time()
        try:
            async with self.connection.cursor() as cursor:
                for row in data:
                    values = [row[col] for col in columns]
                    await cursor.execute(query, values)
                
                await self.connection.commit()
                
                execution_time = self._measure_execution_time(start_time)
                
                return QueryResult(
                    data=[],
                    columns=[],
                    rows_affected=len(data),
                    execution_time=execution_time
                )
        except Exception as e:
            execution_time = self._measure_execution_time(start_time)
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=execution_time,
                error=self._format_error(e)
            )
    
    async def update_data(self, table_name: str, data: Dict[str, Any], where: Dict[str, Any]) -> Optional[QueryResult]:
        """Update data in SQLite table"""
        set_clause = self._build_set_clause(data)
        where_clause = self._build_where_clause(where)
        
        query = f"UPDATE {table_name} SET {set_clause}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        return await self.execute_query(query)
    
    async def delete_data(self, table_name: str, where: Dict[str, Any]) -> Optional[QueryResult]:
        """Delete data from SQLite table"""
        where_clause = self._build_where_clause(where)
        
        query = f"DELETE FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        return await self.execute_query(query)
    
    async def backup_database(self, backup_path: str, compression: str = "gzip", include_data: bool = True) -> Optional[QueryResult]:
        """Create a SQLite backup"""
        start_time = time.time()
        
        try:
            # SQLite backup using .backup() method
            connection_params = self._parse_connection_string(self.connection_string)
            source_path = connection_params['database']
            
            # Create backup directory if needed
            backup_dir = os.path.dirname(backup_path)
            if backup_dir and backup_dir != '':
                os.makedirs(backup_dir, exist_ok=True)
            
            # Simple file copy for SQLite
            import shutil
            shutil.copy2(source_path, backup_path)
            
            execution_time = self._measure_execution_time(start_time)
            
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=1,
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = self._measure_execution_time(start_time)
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=execution_time,
                error=self._format_error(e)
            )
    
    async def restore_database(self, backup_path: str, overwrite: bool = False) -> Optional[QueryResult]:
        """Restore SQLite from backup"""
        start_time = time.time()
        
        try:
            connection_params = self._parse_connection_string(self.connection_string)
            target_path = connection_params['database']
            
            if not overwrite and os.path.exists(target_path):
                raise Exception("Database already exists and overwrite is False")
            
            # Close current connection
            await self.disconnect()
            
            # Copy backup to target location
            import shutil
            shutil.copy2(backup_path, target_path)
            
            # Reconnect
            await self.connect()
            
            execution_time = self._measure_execution_time(start_time)
            
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=1,
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = self._measure_execution_time(start_time)
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=execution_time,
                error=self._format_error(e)
            )
    
    async def get_schema_info(self) -> Dict[str, Any]:
        """Get schema information for SQLite"""
        try:
            # Get table information
            tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
            tables_result = await self.execute_query(tables_query)
            
            schema_info = {
                'tables': [],
                'total_tables': len(tables_result.data)
            }
            
            for table_row in tables_result.data:
                table_name = table_row['name']
                
                # Get column information
                columns_query = f"PRAGMA table_info({table_name})"
                columns_result = await self.execute_query(columns_query)
                
                # Get index information
                indexes_query = f"PRAGMA index_list({table_name})"
                indexes_result = await self.execute_query(indexes_query)
                
                schema_info['tables'].append({
                    'name': table_name,
                    'columns': columns_result.data,
                    'indexes': indexes_result.data
                })
            
            return schema_info
        except Exception as e:
            return {'error': self._format_error(e)}
    
    async def analyze_performance(self, query: Optional[str] = None, include_execution_plan: bool = True) -> Dict[str, Any]:
        """Analyze SQLite performance"""
        try:
            analysis = {}
            
            # Database statistics
            stats_query = "PRAGMA database_list"
            stats_result = await self.execute_query(stats_query)
            analysis['database_info'] = stats_result.data
            
            # Cache statistics
            cache_query = "PRAGMA cache_size"
            cache_result = await self.execute_query(cache_query)
            analysis['cache_size'] = cache_result.data
            
            # Page size
            page_query = "PRAGMA page_size"
            page_result = await self.execute_query(page_query)
            analysis['page_size'] = page_result.data
            
            if query and include_execution_plan:
                explain_result = await self.execute_query(query, explain=True)
                analysis['execution_plan'] = explain_result.explain_plan
            
            return analysis
        except Exception as e:
            return {'error': self._format_error(e)}
    
    async def migrate_schema(self, migration_script: str, dry_run: bool = True) -> Optional[QueryResult]:
        """Migrate SQLite schema"""
        if dry_run:
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=0.0,
                error="Dry run mode - migration would be executed"
            )
        
        # Execute migration script
        return await self.execute_query(migration_script)
    
    async def create_user(self, username: str, password: str, permissions: List[str]) -> Optional[QueryResult]:
        """Create a database user (SQLite doesn't support users)"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite doesn't support user management"
        )
    
    async def grant_permissions(self, username: str, permissions: List[str], table_name: Optional[str] = None) -> Optional[QueryResult]:
        """Grant permissions to a user (SQLite doesn't support permissions)"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite doesn't support permission management"
        )
    
    async def health_check(self) -> bool:
        """Check SQLite health"""
        try:
            result = await self.execute_query("SELECT 1")
            return result.error is None
        except:
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        connection_params = self._parse_connection_string(self.connection_string)
        return {
            'host': 'localhost',
            'port': 0,
            'database': connection_params['database'],
            'username': 'sqlite'
        }
    
    async def connect_database(self, database_type: str, connection_string: str, connection_name: Optional[str] = None) -> Dict[str, Any]:
        """Connect to a database with specified parameters"""
        try:
            if database_type.lower() != 'sqlite':
                return {'error': f'Database type {database_type} not supported by SQLite adapter'}
            
            old_connection_string = self.connection_string
            self.connection_string = connection_string
            
            # Disconnect from current database if connected
            if self.connection:
                await self.disconnect()
            
            # Connect to new database
            await self.connect()
            
            return {
                'success': True,
                'connection_name': connection_name or 'default',
                'database_type': database_type,
                'connection_string': connection_string
            }
        except Exception as e:
            return {'error': self._format_error(e)}
    
    async def drop_column(self, table_name: str, column_name: str) -> Optional[QueryResult]:
        """Drop a column from a table (SQLite doesn't support this directly)"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite doesn't support dropping columns directly. Use ALTER TABLE with table recreation."
        )
    
    async def modify_column(self, table_name: str, column_name: str, new_definition: Dict[str, Any]) -> Optional[QueryResult]:
        """Modify a column definition (SQLite doesn't support this directly)"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite doesn't support modifying columns directly. Use ALTER TABLE with table recreation."
        )
    
    async def filter_data(self, table_name: str, conditions: Dict[str, Any], limit: Optional[int] = None) -> QueryResult:
        """Filter data within a table"""
        where_clause = self._build_where_clause(conditions)
        query = f"SELECT * FROM {table_name}"
        
        if where_clause:
            query += f" WHERE {where_clause}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return await self.execute_query(query)
    
    async def aggregate_data(self, table_name: str, aggregations: List[Dict[str, Any]], group_by: Optional[List[str]] = None) -> QueryResult:
        """Perform aggregation operations"""
        select_parts = []
        
        for agg in aggregations:
            func = agg.get('function', '').upper()
            column = agg.get('column', '*')
            alias = agg.get('alias', f"{func.lower()}_{column}")
            
            if func in ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX']:
                select_parts.append(f"{func}({column}) AS {alias}")
        
        if group_by:
            select_parts.extend(group_by)
        
        query = f"SELECT {', '.join(select_parts)} FROM {table_name}"
        
        if group_by:
            query += f" GROUP BY {', '.join(group_by)}"
        
        return await self.execute_query(query)
    
    async def join_tables(self, join_config: Dict[str, Any]) -> QueryResult:
        """Join multiple tables"""
        try:
            tables = join_config.get('tables', [])
            if len(tables) < 2:
                return QueryResult(
                    data=[],
                    columns=[],
                    rows_affected=0,
                    execution_time=0.0,
                    error="At least 2 tables required for join"
                )
            
            # Build JOIN query
            query_parts = [f"SELECT * FROM {tables[0]['name']}"]
            
            for i in range(1, len(tables)):
                table = tables[i]
                join_type = table.get('join_type', 'INNER').upper()
                on_condition = table.get('on_condition', '')
                
                query_parts.append(f"{join_type} JOIN {table['name']} ON {on_condition}")
            
            query = " ".join(query_parts)
            return await self.execute_query(query)
        except Exception as e:
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=0.0,
                error=self._format_error(e)
            )
    
    async def revoke_permissions(self, username: str, permissions: List[str], table_name: Optional[str] = None) -> Optional[QueryResult]:
        """Revoke permissions from a user (SQLite doesn't support permissions)"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite doesn't support permission management"
        )
    
    async def drop_user(self, username: str) -> Optional[QueryResult]:
        """Drop a database user (SQLite doesn't support users)"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite doesn't support user management"
        )
    
    async def explain_query(self, query: str) -> Dict[str, Any]:
        """Explain query execution plan"""
        try:
            explain_query = f"EXPLAIN QUERY PLAN {query}"
            result = await self.execute_query(explain_query)
            return {
                'execution_plan': result.data,
                'query': query
            }
        except Exception as e:
            return {'error': self._format_error(e)}
    
    async def migrate_table(self, source_table: str, target_table: str, mapping: Optional[Dict[str, str]] = None) -> Optional[QueryResult]:
        """Migrate data from one table to another"""
        try:
            if mapping:
                # Map columns
                source_cols = list(mapping.keys())
                target_cols = list(mapping.values())
                query = f"INSERT INTO {target_table} ({', '.join(target_cols)}) SELECT {', '.join(source_cols)} FROM {source_table}"
            else:
                # Direct copy
                query = f"INSERT INTO {target_table} SELECT * FROM {source_table}"
            
            return await self.execute_query(query)
        except Exception as e:
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=0.0,
                error=self._format_error(e)
            )
    
    async def sync_schema(self, target_schema: Dict[str, Any]) -> Optional[QueryResult]:
        """Sync schema with target definition"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="Schema sync not implemented for SQLite"
        )
    
    async def schedule_task(self, task_name: str, schedule: str, query: str) -> Optional[QueryResult]:
        """Schedule a recurring task (SQLite doesn't support scheduling)"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite doesn't support task scheduling"
        )
    
    async def log_query(self, query: str, execution_time: float, result_count: int) -> None:
        """Log query execution"""
        self._log_query(query, None, execution_time)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get database status and health information"""
        try:
            status = {
                'connected': self.connection is not None,
                'database_type': 'sqlite',
                'health': await self.health_check()
            }
            
            if self.connection:
                # Get database file info
                connection_params = self._parse_connection_string(self.connection_string)
                db_path = connection_params['database']
                
                if os.path.exists(db_path):
                    file_size = os.path.getsize(db_path)
                    status['database_size'] = file_size
                    status['database_path'] = db_path
            
            return status
        except Exception as e:
            return {'error': self._format_error(e)}
    
    async def create_database(self, database_name: str) -> Optional[QueryResult]:
        """Create a new database (SQLite creates on connection)"""
        try:
            # For SQLite, creating a database is just connecting to a new file
            new_db_path = f"{database_name}.db"
            temp_connection = await aiosqlite.connect(new_db_path)
            await temp_connection.close()
            
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=1,
                execution_time=0.0
            )
        except Exception as e:
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=0.0,
                error=self._format_error(e)
            )
    
    async def drop_database(self, database_name: str) -> Optional[QueryResult]:
        """Drop a database (delete SQLite file)"""
        try:
            db_path = f"{database_name}.db"
            if os.path.exists(db_path):
                os.remove(db_path)
                return QueryResult(
                    data=[],
                    columns=[],
                    rows_affected=1,
                    execution_time=0.0
                )
            else:
                return QueryResult(
                    data=[],
                    columns=[],
                    rows_affected=0,
                    execution_time=0.0,
                    error="Database file not found"
                )
        except Exception as e:
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=0.0,
                error=self._format_error(e)
            )
    
    async def rename_table(self, old_name: str, new_name: str) -> Optional[QueryResult]:
        """Rename a table"""
        query = f"ALTER TABLE {old_name} RENAME TO {new_name}"
        return await self.execute_query(query)
    
    async def select_data(self, table_name: str, filters: Dict[str, Any], projection: Optional[List[str]] = None) -> QueryResult:
        """Fetch data using filters and projections"""
        columns = ", ".join(projection) if projection else "*"
        query = f"SELECT {columns} FROM {table_name}"
        
        where_clause = self._build_where_clause(filters)
        if where_clause:
            query += f" WHERE {where_clause}"
        
        return await self.execute_query(query)
    
    async def truncate_table(self, table_name: str) -> Optional[QueryResult]:
        """Deletes all rows without dropping table"""
        query = f"DELETE FROM {table_name}"
        return await self.execute_query(query)
    
    async def vacuum_table(self, table_name: str, full: bool = False) -> Optional[QueryResult]:
        """Cleans up bloat and dead rows"""
        if full:
            query = "VACUUM"
        else:
            query = f"VACUUM {table_name}" if table_name else "VACUUM"
        return await self.execute_query(query)
    
    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query and return execution plan with performance insights"""
        try:
            explain_query = f"EXPLAIN QUERY PLAN {query}"
            result = await self.execute_query(explain_query)
            
            # Get basic statistics
            stats = {
                'execution_plan': result.data,
                'query': query,
                'plan_steps': len(result.data)
            }
            
            return stats
        except Exception as e:
            return {'error': self._format_error(e)}
    
    async def optimize_query(self, query: str) -> Dict[str, Any]:
        """Automatically rewrite query for optimal performance"""
        # SQLite doesn't have built-in query optimization hints
        # Return basic analysis instead
        return await self.analyze_query(query)
    
    async def get_connection_string(self) -> str:
        """Return current database connection string"""
        return self.connection_string
    
    async def monitor_health(self) -> Dict[str, Any]:
        """Monitor DB CPU, memory, storage, active connections"""
        try:
            health_info = {
                'status': 'healthy' if await self.health_check() else 'unhealthy',
                'database_type': 'sqlite',
                'connection_status': 'connected' if self.connection else 'disconnected'
            }
            
            # Get file size if connected
            if self.connection:
                connection_params = self._parse_connection_string(self.connection_string)
                db_path = connection_params['database']
                
                if os.path.exists(db_path):
                    file_size = os.path.getsize(db_path)
                    health_info['database_size_bytes'] = file_size
                    health_info['database_path'] = db_path
            
            return health_info
        except Exception as e:
            return {'error': self._format_error(e)}
    
    async def monitor_queries(self) -> Dict[str, Any]:
        """Track running and slow queries"""
        # SQLite doesn't have built-in query monitoring
        return {
            'running_queries': [],
            'slow_queries': [],
            'message': 'SQLite doesn\'t support query monitoring'
        }
    
    async def log_queries(self, enable: bool = True) -> Dict[str, Any]:
        """Record all queries and execution times"""
        # This would be handled by the base class logging
        return {
            'query_logging': enable,
            'message': 'Query logging controlled by configuration'
        }
    
    async def check_disk_usage(self) -> Dict[str, Any]:
        """Returns size of DB, tables, indexes, logs"""
        try:
            connection_params = self._parse_connection_string(self.connection_string)
            db_path = connection_params['database']
            
            if not os.path.exists(db_path):
                return {'error': 'Database file not found'}
            
            file_size = os.path.getsize(db_path)
            
            # Get page count and size
            page_count_result = await self.execute_query("PRAGMA page_count")
            page_size_result = await self.execute_query("PRAGMA page_size")
            
            return {
                'database_size_bytes': file_size,
                'database_path': db_path,
                'page_count': page_count_result.data[0] if page_count_result.data else 0,
                'page_size': page_size_result.data[0] if page_size_result.data else 0
            }
        except Exception as e:
            return {'error': self._format_error(e)}
    
    async def check_memory_usage(self) -> Dict[str, Any]:
        """Returns buffer/cache/memory info"""
        try:
            # Get cache size
            cache_size_result = await self.execute_query("PRAGMA cache_size")
            
            return {
                'cache_size': cache_size_result.data[0] if cache_size_result.data else 0,
                'message': 'SQLite uses minimal memory monitoring'
            }
        except Exception as e:
            return {'error': self._format_error(e)}
    
    async def update_statistics(self, table_name: Optional[str] = None) -> Optional[QueryResult]:
        """Refreshes DB statistics for query planner"""
        if table_name:
            query = f"ANALYZE {table_name}"
        else:
            query = "ANALYZE"
        
        return await self.execute_query(query)
    
    async def rebuild_index(self, index_name: str, table_name: str) -> Optional[QueryResult]:
        """Rebuilds fragmented indexes"""
        query = f"REINDEX {index_name}"
        return await self.execute_query(query)
    
    async def run_health_check(self) -> Dict[str, Any]:
        """Runs full DB diagnostics and performance tests"""
        try:
            health_report = {
                'database_type': 'sqlite',
                'connection_status': 'connected' if self.connection else 'disconnected',
                'health_checks': {}
            }
            
            # Basic connectivity test
            health_report['health_checks']['connectivity'] = await self.health_check()
            
            # Check if database file exists
            connection_params = self._parse_connection_string(self.connection_string)
            db_path = connection_params['database']
            health_report['health_checks']['file_exists'] = os.path.exists(db_path)
            
            if health_report['health_checks']['file_exists']:
                # Check file permissions
                health_report['health_checks']['readable'] = os.access(db_path, os.R_OK)
                health_report['health_checks']['writable'] = os.access(db_path, os.W_OK)
                
                # Check integrity
                try:
                    integrity_result = await self.execute_query("PRAGMA integrity_check")
                    health_report['health_checks']['integrity'] = integrity_result.data[0] if integrity_result.data else 'unknown'
                except:
                    health_report['health_checks']['integrity'] = 'failed'
            
            return health_report
        except Exception as e:
            return {'error': self._format_error(e)}
    
    # Methods that don't apply to SQLite but need to be implemented
    async def setup_database(self, database_config: Dict[str, Any]) -> Optional[QueryResult]:
        """Deploy a new database instance with configuration"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="Database setup not applicable to SQLite"
        )
    
    async def init_cluster(self, cluster_config: Dict[str, Any]) -> Optional[QueryResult]:
        """Set up a cluster with replication or sharding support"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="Clustering not supported by SQLite"
        )
    
    async def set_user_privileges(self, username: str, privileges: List[str], resource: Optional[str] = None) -> Optional[QueryResult]:
        """Grant or revoke permissions to users"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite doesn't support user privileges"
        )
    
    async def enable_ssl(self, ssl_config: Dict[str, Any]) -> Optional[QueryResult]:
        """Configure SSL/TLS encryption"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite doesn't support SSL configuration"
        )
    
    async def define_constraint(self, table_name: str, constraint_definition: Dict[str, Any]) -> Optional[QueryResult]:
        """Add constraints like PRIMARY KEY, UNIQUE, FOREIGN KEY"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="SQLite constraints must be defined during table creation"
        )
    
    async def recommend_index(self, table_name: str, query_patterns: List[str]) -> Dict[str, Any]:
        """Analyze and recommend index strategies"""
        # Simple recommendation based on query patterns
        recommendations = []
        
        for pattern in query_patterns:
            if 'WHERE' in pattern.upper():
                # Suggest indexes on WHERE clause columns
                recommendations.append({
                    'type': 'index',
                    'reason': 'WHERE clause optimization',
                    'pattern': pattern
                })
        
        return {
            'table_name': table_name,
            'recommendations': recommendations,
            'message': 'Basic index recommendations for SQLite'
        }
    
    async def shard_table(self, table_name: str, shard_config: Dict[str, Any]) -> Optional[QueryResult]:
        """Distribute table/collection across shards"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="Sharding not supported by SQLite"
        )
    
    async def partition_table(self, table_name: str, partition_config: Dict[str, Any]) -> Optional[QueryResult]:
        """Partition large table for performance"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="Table partitioning not supported by SQLite"
        )
    
    async def migrate_data(self, source_config: Dict[str, Any], target_config: Dict[str, Any], migration_options: Dict[str, Any]) -> Optional[QueryResult]:
        """Migrate data between different DB types or environments"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="Cross-database migration not implemented for SQLite"
        )
    
    async def convert_schema(self, source_schema: Dict[str, Any], target_db_type: str) -> Dict[str, Any]:
        """Convert schema from one DB type to another"""
        return {
            'error': 'Schema conversion not implemented for SQLite',
            'source_schema': source_schema,
            'target_db_type': target_db_type
        }
    
    async def import_data(self, table_name: str, data_source: str, import_options: Dict[str, Any]) -> Optional[QueryResult]:
        """Import data from CSV, JSON, or dump files"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="Data import not implemented for SQLite adapter"
        )
    
    async def export_data(self, table_name: str, export_format: str, export_options: Dict[str, Any]) -> Dict[str, Any]:
        """Export data to formats like CSV, JSON, SQL"""
        return {
            'error': 'Data export not implemented for SQLite adapter',
            'table_name': table_name,
            'export_format': export_format
        }
    
    async def schedule_backup(self, backup_schedule: str, backup_config: Dict[str, Any]) -> Optional[QueryResult]:
        """Schedule recurring backups"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="Backup scheduling not supported by SQLite"
        )
    
    async def clone_database(self, source_db: str, target_db: str, clone_options: Dict[str, Any]) -> Optional[QueryResult]:
        """Clone database into staging/sandbox environment"""
        try:
            # Simple file copy for SQLite
            import shutil
            shutil.copy2(source_db, target_db)
            
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=1,
                execution_time=0.0
            )
        except Exception as e:
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=0.0,
                error=self._format_error(e)
            )
    
    async def mask_data(self, table_name: str, masking_rules: Dict[str, Any]) -> Optional[QueryResult]:
        """Anonymize sensitive data for test environments"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="Data masking not implemented for SQLite adapter"
        )

    # All missing abstract methods
    async def add_shard(self, shard_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Sharding not supported by SQLite")

    async def apply_migration_script(self, migration_script: str, dry_run: bool = True) -> Optional[QueryResult]:
        return await self.migrate_schema(migration_script, dry_run)

    async def archive_old_data(self, table_name: str, cutoff_date: str, archive_table: str) -> Optional[QueryResult]:
        query = f"INSERT INTO {archive_table} SELECT * FROM {table_name} WHERE date_column < '{cutoff_date}'"
        return await self.execute_query(query)

    async def assign_role(self, username: str, role_name: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Roles not supported by SQLite")

    async def audit_login_activity(self, time_window: str = '24h') -> List[Dict[str, Any]]:
        return [{'message': 'Login activity audit not supported by SQLite'}]

    async def check_replication_status(self) -> Dict[str, Any]:
        return {'error': 'Replication not supported by SQLite'}

    async def compact_storage(self, collection_name: Optional[str] = None) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Storage compaction not applicable to SQLite")

    async def compare_schemas(self, source_schema: Dict[str, Any], target_schema: Dict[str, Any]) -> Dict[str, Any]:
        return {'error': 'Schema comparison not implemented for SQLite'}

    async def create_function(self, function_name: str, parameters: List[Dict[str, Any]], return_type: str, body: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Functions not supported by SQLite")

    async def create_procedure(self, procedure_name: str, parameters: List[Dict[str, Any]], body: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Procedures not supported by SQLite")

    async def create_trigger(self, trigger_name: str, table_name: str, event: str, timing: str, action: str) -> Optional[QueryResult]:
        query = f"CREATE TRIGGER {trigger_name} {timing} {event} ON {table_name} FOR EACH ROW {action}"
        return await self.execute_query(query)

    async def create_view(self, view_name: str, query: str, materialized: bool = False) -> Optional[QueryResult]:
        create_query = f"CREATE VIEW {view_name} AS {query}"
        return await self.execute_query(create_query)

    async def defragment_table(self, table_name: str) -> Optional[QueryResult]:
        return await self.vacuum_table(table_name)

    async def detect_anomalies(self, time_window: str = '24h') -> List[Dict[str, Any]]:
        return [{'message': 'Anomaly detection not implemented for SQLite'}]

    async def drop_function(self, function_name: str, cascade: bool = False) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Functions not supported by SQLite")

    async def drop_procedure(self, procedure_name: str, cascade: bool = False) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Procedures not supported by SQLite")

    async def drop_trigger(self, trigger_name: str, table_name: Optional[str] = None) -> Optional[QueryResult]:
        query = f"DROP TRIGGER {trigger_name}"
        return await self.execute_query(query)

    async def drop_view(self, view_name: str, cascade: bool = False) -> Optional[QueryResult]:
        query = f"DROP VIEW {view_name}"
        return await self.execute_query(query)

    async def enable_audit_log(self, audit_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Audit logging not supported by SQLite")

    async def enable_event_scheduler(self, enabled: bool = True) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Event scheduler not supported by SQLite")

    async def enable_firewall(self, firewall_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Firewall not supported by SQLite")

    async def enable_replication(self, replication_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Replication not supported by SQLite")

    async def enable_tls_auth(self, tls_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="TLS auth not supported by SQLite")

    async def force_disconnect_user(self, username: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="User disconnection not supported by SQLite")

    async def generate_er_diagram(self, output_format: str = 'png') -> Dict[str, Any]:
        return {'error': 'ER diagram generation not implemented for SQLite'}

    async def generate_migration_script(self, target_schema: Dict[str, Any]) -> Dict[str, Any]:
        return {'error': 'Migration script generation not implemented for SQLite'}

    async def generate_schema_doc(self, output_format: str = 'markdown') -> Dict[str, Any]:
        return {'error': 'Schema documentation generation not implemented for SQLite'}

    async def generate_seed_data(self, table_name: str, row_count: int, seed_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Seed data generation not implemented for SQLite")

    async def list_roles(self) -> List[Dict[str, Any]]:
        return [{'message': 'Roles not supported by SQLite'}]

    async def list_users(self) -> List[Dict[str, Any]]:
        return [{'message': 'Users not supported by SQLite'}]

    async def log_schema_changes(self, enable: bool = True) -> Dict[str, Any]:
        return {'error': 'Schema change logging not implemented for SQLite'}

    async def pause_replication(self, channel_name: Optional[str] = None) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Replication not supported by SQLite")

    async def purge_binary_logs(self, before_date: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Binary logs not supported by SQLite")

    async def rebalance_shards(self, rebalance_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Sharding not supported by SQLite")

    async def refresh_materialized_view(self, view_name: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Materialized views not supported by SQLite")

    async def remove_shard(self, shard_name: str, safe_mode: bool = True) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Sharding not supported by SQLite")

    async def reset_password(self, username: str, new_password: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Password reset not supported by SQLite")

    async def restart_database(self) -> Dict[str, Any]:
        return {'error': 'Database restart not applicable to SQLite'}

    async def resume_replication(self, channel_name: Optional[str] = None) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Replication not supported by SQLite")

    async def revoke_role(self, username: str, role_name: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Roles not supported by SQLite")

    async def rotate_logs(self, log_type: str = 'all') -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Log rotation not applicable to SQLite")

    async def schedule_sql_job(self, job_name: str, sql_command: str, schedule: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="SQL job scheduling not supported by SQLite")

    async def setup_connection_pooling(self, pool_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Connection pooling not implemented for SQLite")

    async def setup_sharding(self, sharding_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Sharding not supported by SQLite")

    async def track_locks(self) -> List[Dict[str, Any]]:
        return [{'message': 'Lock tracking not implemented for SQLite'}]

    async def track_session(self) -> List[Dict[str, Any]]:
        return [{'message': 'Session tracking not implemented for SQLite'}]
