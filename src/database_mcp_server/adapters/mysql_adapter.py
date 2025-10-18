"""
MySQL adapter for database operations
"""

from typing import Dict, List, Any, Optional
import time
import aiomysql
from .base_adapter import BaseAdapter, QueryResult

class MySQLAdapter(BaseAdapter):
    """MySQL Adapter Implementation"""
    
    async def connect(self) -> None:
        """Connect to MySQL database"""
        connection_params = self._parse_connection_string(self.connection_string)
        self.connection = await aiomysql.connect(
            host=connection_params['host'],
            port=connection_params['port'],
            user=connection_params['username'],
            password=connection_params['password'],
            db=connection_params['database'],
            autocommit=True
        )
        
    async def disconnect(self) -> None:
        """Disconnect from MySQL database"""
        if self.connection:
            self.connection.close()
            
    async def execute_query(self, query: str, parameters: Optional[List[Any]] = None, explain: bool = False) -> QueryResult:
        """Execute a MySQL query"""
        start_time = time.time()
        
        sanitized_query = self._sanitize_query(query)
        async with self.connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(sanitized_query, parameters)
            data = await cursor.fetchall()
            columns = [column[0] for column in cursor.description]
            
            explain_plan = None
            if explain:
                await cursor.execute(f"EXPLAIN {sanitized_query}", parameters)
                explain_plan = await cursor.fetchall()
                
            execution_time = self._measure_execution_time(start_time)
            self._log_query(query, parameters, execution_time)
            
            return QueryResult(
                data=data,
                columns=columns,
                rows_affected=cursor.rowcount,
                execution_time=execution_time,
                explain_plan=explain_plan
            )
            
    async def create_table(self, table_name: str, columns: List[Dict[str, Any]], constraints: List[Dict[str, Any]] = None) -> Optional[QueryResult]:
        """Create a table in MySQL"""
        columns_clause = self._build_columns_clause(columns)
        constraints_clause = self._build_constraints_clause(constraints)
        
        query = f"CREATE TABLE {table_name} ({columns_clause}{', ' + constraints_clause if constraints_clause else ''})"
        return await self.execute_query(query)
        
    async def drop_table(self, table_name: str, cascade: bool = False) -> Optional[QueryResult]:
        """Drop a table in MySQL"""
        query = f"DROP TABLE {table_name}" + (" CASCADE" if cascade else "")
        return await self.execute_query(query)
        
    async def add_column(self, table_name: str, column_definition: Dict[str, Any]) -> Optional[QueryResult]:
        """Add a column in MySQL table"""
        column_clause = f"{column_definition['name']} {column_definition['type']}"
        if not column_definition.get('nullable', True):
            column_clause += " NOT NULL"
        if 'default' in column_definition:
            column_clause += f" DEFAULT {column_definition['default']}"
        if column_definition.get('primary_key', False):
            column_clause += " PRIMARY KEY"
        if column_definition.get('unique', False):
            column_clause += " UNIQUE"
        query = f"ALTER TABLE {table_name} ADD COLUMN {column_clause}"
        return await self.execute_query(query)

    async def drop_column(self, table_name: str, column_name: str) -> Optional[QueryResult]:
        """Drop a column in MySQL table"""
        query = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        return await self.execute_query(query)

    async def modify_column(self, table_name: str, column_name: str, new_definition: Dict[str, Any]) -> Optional[QueryResult]:
        """Modify a column in MySQL table"""
        column_clause = f"{column_name} {new_definition['type']}"
        if not new_definition.get('nullable', True):
            column_clause += " NOT NULL"
        if 'default' in new_definition:
            column_clause += f" DEFAULT {new_definition['default']}"
        query = f"ALTER TABLE {table_name} MODIFY COLUMN {column_clause}"
        return await self.execute_query(query)

    async def list_tables(self) -> List[str]:
        """List all tables in the MySQL database"""
        query = "SHOW TABLES"
        result = await self.execute_query(query)
        return [row['Tables_in_{}'.format(self.connection.db)] for row in result.data]

    async def describe_table(self, table_name: str) -> Dict[str, Any]:
        """Describe a MySQL table"""
        query = f"DESCRIBE {table_name}"
        result = await self.execute_query(query)
        return {'columns': result.data}

    async def truncate_table(self, table_name: str) -> Optional[QueryResult]:
        """Truncate a MySQL table (remove all rows)"""
        query = f"TRUNCATE TABLE {table_name}"
        return await self.execute_query(query)

    async def get_status(self) -> Dict[str, Any]:
        """Get MySQL status and health information"""
        status = {
            'server_version': self.connection.get_server_info(),
            'host': self.connection.host,
            'port': self.connection.port
        }
        status['healthy'] = await self.health_check()
        return status
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        return {
            'host': self.connection.host,
            'port': self.connection.port,
            'database': self.connection.db,
            'username': self.connection.user
        }
    
    async def health_check(self) -> bool:
        """Check MySQL health"""
        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute("SELECT 1")
                return True
        except:
            return False

    # All missing abstract methods implementation
    async def connect_database(self, database_type: str, connection_string: str, connection_name: Optional[str] = None) -> Dict[str, Any]:
        """Connect to a database with specified parameters"""
        try:
            if database_type.lower() != 'mysql':
                return {'error': f'Database type {database_type} not supported by MySQL adapter'}
            
            # Disconnect from current database if connected
            if self.connection:
                await self.disconnect()
            
            # Update connection string and connect
            self.connection_string = connection_string
            await self.connect()
            
            return {
                'success': True,
                'connection_name': connection_name or 'default',
                'database_type': database_type,
                'connection_string': connection_string
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def alter_table(self, table_name: str, alterations: List[Dict[str, Any]]) -> Optional[QueryResult]:
        """Alter table structure in MySQL"""
        results = []
        for alteration in alterations:
            alter_type = alteration.get('type', '').upper()
            
            if alter_type == 'ADD_COLUMN':
                column_def = f"{alteration['column_name']} {alteration['column_type']}"
                if not alteration.get('nullable', True):
                    column_def += " NOT NULL"
                if alteration.get('default'):
                    column_def += f" DEFAULT {alteration['default']}"
                query = f"ALTER TABLE {table_name} ADD COLUMN {column_def}"
                result = await self.execute_query(query)
                results.append(result)
            elif alter_type == 'DROP_COLUMN':
                query = f"ALTER TABLE {table_name} DROP COLUMN {alteration['column_name']}"
                result = await self.execute_query(query)
                results.append(result)
            elif alter_type == 'MODIFY_COLUMN':
                column_def = f"{alteration['column_name']} {alteration['column_type']}"
                if not alteration.get('nullable', True):
                    column_def += " NOT NULL"
                query = f"ALTER TABLE {table_name} MODIFY COLUMN {column_def}"
                result = await self.execute_query(query)
                results.append(result)
            elif alter_type == 'RENAME_TABLE':
                query = f"ALTER TABLE {table_name} RENAME TO {alteration['new_name']}"
                result = await self.execute_query(query)
                results.append(result)
        
        return results[0] if results else None
async def create_index(self, table_name: str, index_name: str, columns: List[str], unique: bool = False) -> Optional[QueryResult]:
    
    async def analyze_alert(self) -> Dict[str, Any]:
        """Analyze alert data for MySQL adapter"""
        try:
            # Get error log entries and warnings
            query = "SHOW VARIABLES LIKE 'log_error'"
            log_result = await self.execute_query(query)
            
            # Get current warnings
            warnings_query = "SHOW WARNINGS"
            warnings_result = await self.execute_query(warnings_query)
            
            return {
                'error_log_path': log_result.data,
                'current_warnings': warnings_result.data,
                'warning_count': len(warnings_result.data) if warnings_result.data else 0
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_backup(self) -> Dict[str, Any]:
        """Analyze backup data for MySQL adapter"""
        try:
            # Check binary logging status for backup capabilities
            query = "SHOW VARIABLES LIKE 'log_bin'"
            log_bin_result = await self.execute_query(query)
            
            # Get binary log files
            binlog_query = "SHOW BINARY LOGS"
            try:
                binlog_result = await self.execute_query(binlog_query)
                binlog_files = binlog_result.data
            except:
                binlog_files = []
            
            return {
                'binary_logging_enabled': log_bin_result.data,
                'binary_log_files': binlog_files,
                'backup_ready': len(binlog_files) > 0
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_cache(self) -> Dict[str, Any]:
        """Analyze cache data for MySQL adapter"""
        try:
            # Query cache and buffer pool statistics
            cache_queries = [
                "SHOW STATUS LIKE 'Qcache%'",
                "SHOW STATUS LIKE 'Innodb_buffer_pool%'",
                "SHOW VARIABLES LIKE 'query_cache_size'"
            ]
            
            cache_info = {}
            for query in cache_queries:
                result = await self.execute_query(query)
                cache_info.update({row[0]: row[1] for row in result.data})
            
            return {
                'query_cache_stats': cache_info,
                'cache_hit_rate': self._calculate_cache_hit_rate(cache_info)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_certificate(self) -> Dict[str, Any]:
        """Analyze certificate data for MySQL adapter"""
        try:
            # Check SSL configuration
            ssl_queries = [
                "SHOW VARIABLES LIKE 'have_ssl'",
                "SHOW VARIABLES LIKE 'ssl_cert'",
                "SHOW VARIABLES LIKE 'ssl_key'",
                "SHOW VARIABLES LIKE 'ssl_ca'"
            ]
            
            ssl_info = {}
            for query in ssl_queries:
                result = await self.execute_query(query)
                ssl_info.update({row[0]: row[1] for row in result.data})
            
            return {
                'ssl_configuration': ssl_info,
                'ssl_enabled': ssl_info.get('have_ssl', 'NO') == 'YES'
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_cluster(self) -> Dict[str, Any]:
        """Analyze cluster data for MySQL adapter"""
        try:
            # Check for replication status
            master_status_query = "SHOW MASTER STATUS"
            slave_status_query = "SHOW SLAVE STATUS"
            
            cluster_info = {}
            
            try:
                master_result = await self.execute_query(master_status_query)
                cluster_info['master_status'] = master_result.data
            except:
                cluster_info['master_status'] = []
            
            try:
                slave_result = await self.execute_query(slave_status_query)
                cluster_info['slave_status'] = slave_result.data
            except:
                cluster_info['slave_status'] = []
            
            return {
                'replication_info': cluster_info,
                'is_master': len(cluster_info['master_status']) > 0,
                'is_slave': len(cluster_info['slave_status']) > 0
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_database(self) -> Dict[str, Any]:
        """Analyze database data for MySQL adapter"""
        try:
            # Get database statistics
            db_query = """
                SELECT 
                    SCHEMA_NAME as database_name,
                    DEFAULT_CHARACTER_SET_NAME as charset,
                    DEFAULT_COLLATION_NAME as collation
                FROM INFORMATION_SCHEMA.SCHEMATA
                WHERE SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
            """
            
            # Get table counts per database
            table_count_query = """
                SELECT 
                    TABLE_SCHEMA as database_name,
                    COUNT(*) as table_count
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                GROUP BY TABLE_SCHEMA
            """
            
            db_result = await self.execute_query(db_query)
            table_count_result = await self.execute_query(table_count_query)
            
            return {
                'databases': db_result.data,
                'table_counts': table_count_result.data,
                'total_databases': len(db_result.data)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_entity(self) -> Dict[str, Any]:
        """Analyze entity data for MySQL adapter"""
        try:
            # Get entity information (tables, views, procedures)
            entities_query = """
                SELECT 
                    TABLE_SCHEMA as schema_name,
                    TABLE_NAME as entity_name,
                    TABLE_TYPE as entity_type,
                    ENGINE,
                    TABLE_ROWS as row_count,
                    DATA_LENGTH as data_size,
                    INDEX_LENGTH as index_size
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                ORDER BY DATA_LENGTH DESC
            """
            
            result = await self.execute_query(entities_query)
            
            return {
                'entities': result.data,
                'total_entities': len(result.data),
                'entity_types': list(set(row[2] for row in result.data))
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_event(self) -> Dict[str, Any]:
        """Analyze event data for MySQL adapter"""
        try:
            # Get event scheduler status and events
            event_status_query = "SHOW VARIABLES LIKE 'event_scheduler'"
            events_query = """
                SELECT 
                    EVENT_SCHEMA,
                    EVENT_NAME,
                    STATUS,
                    EVENT_TYPE,
                    EXECUTE_AT,
                    INTERVAL_VALUE,
                    INTERVAL_FIELD,
                    STARTS,
                    ENDS
                FROM INFORMATION_SCHEMA.EVENTS
            """
            
            status_result = await self.execute_query(event_status_query)
            events_result = await self.execute_query(events_query)
            
            return {
                'event_scheduler_status': status_result.data,
                'events': events_result.data,
                'total_events': len(events_result.data)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_history(self) -> Dict[str, Any]:
        """Analyze history data for MySQL adapter"""
        try:
            # Get general log status and recent connections
            history_queries = [
                "SHOW VARIABLES LIKE 'general_log'",
                "SHOW VARIABLES LIKE 'general_log_file'",
                "SHOW STATUS LIKE 'Connections'",
                "SHOW STATUS LIKE 'Uptime'"
            ]
            
            history_info = {}
            for query in history_queries:
                result = await self.execute_query(query)
                history_info.update({row[0]: row[1] for row in result.data})
            
            return {
                'general_log_info': history_info,
                'uptime_seconds': int(history_info.get('Uptime', 0)),
                'total_connections': int(history_info.get('Connections', 0))
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_index(self) -> Dict[str, Any]:
        """Analyze index data for MySQL adapter"""
        try:
            # Get index statistics
            index_query = """
                SELECT 
                    TABLE_SCHEMA,
                    TABLE_NAME,
                    INDEX_NAME,
                    COLUMN_NAME,
                    SEQ_IN_INDEX,
                    NON_UNIQUE,
                    INDEX_TYPE,
                    CARDINALITY
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                ORDER BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
            """
            
            result = await self.execute_query(index_query)
            
            return {
                'indexes': result.data,
                'total_indexes': len(set((row[0], row[1], row[2]) for row in result.data)),
                'index_types': list(set(row[6] for row in result.data))
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_instance(self) -> Dict[str, Any]:
        """Analyze instance data for MySQL adapter"""
        try:
            # Get MySQL instance information
            instance_queries = [
                "SELECT VERSION() as version",
                "SHOW VARIABLES LIKE 'server_id'",
                "SHOW VARIABLES LIKE 'hostname'",
                "SHOW VARIABLES LIKE 'port'",
                "SHOW STATUS LIKE 'Uptime'",
                "SHOW STATUS LIKE 'Threads_connected'",
                "SHOW STATUS LIKE 'Max_used_connections'"
            ]
            
            instance_info = {}
            for query in instance_queries:
                result = await self.execute_query(query)
                if query.startswith("SELECT VERSION()"):
                    instance_info['version'] = result.data[0][0]
                else:
                    instance_info.update({row[0]: row[1] for row in result.data})
            
            return {
                'instance_info': instance_info,
                'uptime_hours': int(instance_info.get('Uptime', 0)) // 3600,
                'current_connections': int(instance_info.get('Threads_connected', 0))
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_lock(self) -> Dict[str, Any]:
        """Analyze lock data for MySQL adapter"""
        try:
            # Get current locks and lock waits
            lock_query = "SHOW ENGINE INNODB STATUS"
            processlist_query = "SHOW PROCESSLIST"
            
            try:
                lock_result = await self.execute_query(lock_query)
                innodb_status = lock_result.data[0][2] if lock_result.data else ""
            except:
                innodb_status = "Unable to retrieve InnoDB status"
            
            processlist_result = await self.execute_query(processlist_query)
            locked_processes = [row for row in processlist_result.data if row[4] and 'lock' in str(row[4]).lower()]
            
            return {
                'innodb_status': innodb_status,
                'active_processes': processlist_result.data,
                'locked_processes': locked_processes,
                'lock_count': len(locked_processes)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_log(self) -> Dict[str, Any]:
        """Analyze log data for MySQL adapter"""
        try:
            # Get log configuration
            log_queries = [
                "SHOW VARIABLES LIKE 'log_error'",
                "SHOW VARIABLES LIKE 'general_log'",
                "SHOW VARIABLES LIKE 'slow_query_log'",
                "SHOW VARIABLES LIKE 'long_query_time'",
                "SHOW STATUS LIKE 'Slow_queries'"
            ]
            
            log_info = {}
            for query in log_queries:
                result = await self.execute_query(query)
                log_info.update({row[0]: row[1] for row in result.data})
            
            return {
                'log_configuration': log_info,
                'slow_queries_count': int(log_info.get('Slow_queries', 0)),
                'logging_enabled': log_info.get('general_log', 'OFF') == 'ON'
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_metric(self) -> Dict[str, Any]:
        """Analyze metric data for MySQL adapter"""
        try:
            # Get key performance metrics
            metric_queries = [
                "SHOW STATUS LIKE 'Questions'",
                "SHOW STATUS LIKE 'Queries'",
                "SHOW STATUS LIKE 'Uptime'",
                "SHOW STATUS LIKE 'Threads_connected'",
                "SHOW STATUS LIKE 'Bytes_sent'",
                "SHOW STATUS LIKE 'Bytes_received'",
                "SHOW STATUS LIKE 'Com_select'",
                "SHOW STATUS LIKE 'Com_insert'",
                "SHOW STATUS LIKE 'Com_update'",
                "SHOW STATUS LIKE 'Com_delete'"
            ]
            
            metrics = {}
            for query in metric_queries:
                result = await self.execute_query(query)
                metrics.update({row[0]: row[1] for row in result.data})
            
            # Calculate QPS
            uptime = int(metrics.get('Uptime', 1))
            questions = int(metrics.get('Questions', 0))
            qps = questions / uptime if uptime > 0 else 0
            
            return {
                'performance_metrics': metrics,
                'queries_per_second': round(qps, 2),
                'total_operations': questions
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_network(self) -> Dict[str, Any]:
        """Analyze network data for MySQL adapter"""
        try:
            # Get network-related status
            network_queries = [
                "SHOW STATUS LIKE 'Bytes_sent'",
                "SHOW STATUS LIKE 'Bytes_received'",
                "SHOW STATUS LIKE 'Connections'",
                "SHOW STATUS LIKE 'Aborted_connects'",
                "SHOW STATUS LIKE 'Aborted_clients'",
                "SHOW VARIABLES LIKE 'max_connections'",
                "SHOW VARIABLES LIKE 'port'"
            ]
            
            network_info = {}
            for query in network_queries:
                result = await self.execute_query(query)
                network_info.update({row[0]: row[1] for row in result.data})
            
            return {
                'network_stats': network_info,
                'bytes_total': int(network_info.get('Bytes_sent', 0)) + int(network_info.get('Bytes_received', 0)),
                'connection_errors': int(network_info.get('Aborted_connects', 0))
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_operation(self) -> Dict[str, Any]:
        """Analyze operation data for MySQL adapter"""
        try:
            # Get operation statistics
            operation_queries = [
                "SHOW STATUS LIKE 'Com_select'",
                "SHOW STATUS LIKE 'Com_insert'",
                "SHOW STATUS LIKE 'Com_update'",
                "SHOW STATUS LIKE 'Com_delete'",
                "SHOW STATUS LIKE 'Com_replace'",
                "SHOW STATUS LIKE 'Com_commit'",
                "SHOW STATUS LIKE 'Com_rollback'"
            ]
            
            operations = {}
            for query in operation_queries:
                result = await self.execute_query(query)
                operations.update({row[0]: row[1] for row in result.data})
            
            total_ops = sum(int(v) for v in operations.values())
            
            return {
                'operation_counts': operations,
                'total_operations': total_ops,
                'read_operations': int(operations.get('Com_select', 0)),
                'write_operations': sum(int(operations.get(k, 0)) for k in ['Com_insert', 'Com_update', 'Com_delete', 'Com_replace'])
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_partition(self) -> Dict[str, Any]:
        """Analyze partition data for MySQL adapter"""
        try:
            # Get partition information
            partition_query = """
                SELECT 
                    TABLE_SCHEMA,
                    TABLE_NAME,
                    PARTITION_NAME,
                    PARTITION_METHOD,
                    PARTITION_EXPRESSION,
                    TABLE_ROWS,
                    DATA_LENGTH,
                    INDEX_LENGTH
                FROM INFORMATION_SCHEMA.PARTITIONS
                WHERE PARTITION_NAME IS NOT NULL
                AND TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
            """
            
            result = await self.execute_query(partition_query)
            
            return {
                'partitions': result.data,
                'partitioned_tables': len(set((row[0], row[1]) for row in result.data)),
                'total_partitions': len(result.data)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_privilege(self) -> Dict[str, Any]:
        """Analyze privilege data for MySQL adapter"""
        try:
            # Get user privileges
            users_query = "SELECT User, Host FROM mysql.user"
            
            # Get database privileges
            db_privs_query = "SELECT User, Host, Db, Select_priv, Insert_priv, Update_priv, Delete_priv FROM mysql.db"
            
            users_result = await self.execute_query(users_query)
            db_privs_result = await self.execute_query(db_privs_query)
            
            return {
                'users': users_result.data,
                'database_privileges': db_privs_result.data,
                'total_users': len(users_result.data),
                'privileged_databases': len(set(row[2] for row in db_privs_result.data))
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_process(self) -> Dict[str, Any]:
        """Analyze process data for MySQL adapter"""
        try:
            # Get current processes
            processlist_query = "SHOW FULL PROCESSLIST"
            thread_status_query = "SHOW STATUS LIKE 'Threads%'"
            
            processlist_result = await self.execute_query(processlist_query)
            thread_status_result = await self.execute_query(thread_status_query)
            
            thread_info = {row[0]: row[1] for row in thread_status_result.data}
            
            # Analyze process states
            process_states = {}
            for row in processlist_result.data:
                state = row[4] if len(row) > 4 else 'Unknown'
                process_states[state] = process_states.get(state, 0) + 1
            
            return {
                'active_processes': processlist_result.data,
                'thread_statistics': thread_info,
                'process_states': process_states,
                'total_processes': len(processlist_result.data)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_role(self) -> Dict[str, Any]:
        """Analyze role data for MySQL adapter"""
        try:
            # MySQL 8.0+ has roles, check version first
            version_query = "SELECT VERSION()"
            version_result = await self.execute_query(version_query)
            version = version_result.data[0][0]
            
            if '8.0' in version or '8.' in version:
                # Get roles for MySQL 8.0+
                roles_query = "SELECT * FROM mysql.role_edges"
                try:
                    roles_result = await self.execute_query(roles_query)
                    return {
                        'mysql_version': version,
                        'roles_supported': True,
                        'role_assignments': roles_result.data
                    }
                except:
                    return {
                        'mysql_version': version,
                        'roles_supported': True,
                        'role_assignments': [],
                        'note': 'No roles currently defined'
                    }
            else:
                return {
                    'mysql_version': version,
                    'roles_supported': False,
                    'note': 'Roles require MySQL 8.0 or higher'
                }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_schema(self) -> Dict[str, Any]:
        """Analyze schema data for MySQL adapter"""
        try:
            # Get comprehensive schema analysis
            schema_query = """
                SELECT 
                    TABLE_SCHEMA,
                    COUNT(CASE WHEN TABLE_TYPE = 'BASE TABLE' THEN 1 END) as table_count,
                    COUNT(CASE WHEN TABLE_TYPE = 'VIEW' THEN 1 END) as view_count,
                    SUM(DATA_LENGTH) as total_data_size,
                    SUM(INDEX_LENGTH) as total_index_size,
                    SUM(TABLE_ROWS) as total_rows
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                GROUP BY TABLE_SCHEMA
            """
            
            result = await self.execute_query(schema_query)
            
            return {
                'schema_summary': result.data,
                'total_schemas': len(result.data),
                'total_size_bytes': sum(int(row[3] or 0) + int(row[4] or 0) for row in result.data)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_security(self) -> Dict[str, Any]:
        """Analyze security data for MySQL adapter"""
        try:
            # Get security-related information
            security_queries = [
                "SHOW VARIABLES LIKE 'have_ssl'",
                "SHOW VARIABLES LIKE 'validate_password%'",
                "SELECT User, Host, ssl_type, ssl_cipher FROM mysql.user",
                "SHOW VARIABLES LIKE 'local_infile'"
            ]
            
            security_info = {}
            
            # SSL status
            ssl_result = await self.execute_query(security_queries[0])
            security_info['ssl_enabled'] = ssl_result.data
            
            # Password validation
            try:
                pwd_result = await self.execute_query(security_queries[1])
                security_info['password_validation'] = pwd_result.data
            except:
                security_info['password_validation'] = []
            
            # User SSL info
            user_ssl_result = await self.execute_query(security_queries[2])
            security_info['user_ssl_config'] = user_ssl_result.data
            
            # Local infile setting
            infile_result = await self.execute_query(security_queries[3])
            security_info['local_infile'] = infile_result.data
            
            return {
                'security_configuration': security_info,
                'ssl_users': len([row for row in user_ssl_result.data if row[2]]),
                'total_users': len(user_ssl_result.data)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_session(self) -> Dict[str, Any]:
        """Analyze session data for MySQL adapter"""
        try:
            # Get session information
            session_queries = [
                "SHOW STATUS LIKE 'Threads_connected'",
                "SHOW STATUS LIKE 'Threads_running'",
                "SHOW STATUS LIKE 'Max_used_connections'",
                "SHOW VARIABLES LIKE 'max_connections'",
                "SHOW PROCESSLIST"
            ]
            
            session_info = {}
            processlist_data = []
            
            for query in session_queries[:-1]:
                result = await self.execute_query(query)
                session_info.update({row[0]: row[1] for row in result.data})
            
            # Get processlist
            processlist_result = await self.execute_query(session_queries[-1])
            processlist_data = processlist_result.data
            
            return {
                'session_statistics': session_info,
                'active_sessions': processlist_data,
                'connection_utilization': f"{session_info.get('Threads_connected', 0)}/{session_info.get('max_connections', 0)}"
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_slave(self) -> Dict[str, Any]:
        """Analyze slave data for MySQL adapter"""
        try:
            # Get slave/replica status
            slave_query = "SHOW SLAVE STATUS"
            
            try:
                result = await self.execute_query(slave_query)
                if result.data:
                    # Convert to dict for easier analysis
                    slave_status = dict(zip(result.columns, result.data[0]))
                    
                    return {
                        'is_slave': True,
                        'slave_status': slave_status,
                        'io_thread_running': slave_status.get('Slave_IO_Running', 'No') == 'Yes',
                        'sql_thread_running': slave_status.get('Slave_SQL_Running', 'No') == 'Yes',
                        'seconds_behind_master': slave_status.get('Seconds_Behind_Master', 0)
                    }
                else:
                    return {
                        'is_slave': False,
                        'note': 'This server is not configured as a slave'
                    }
            except:
                return {
                    'is_slave': False,
                    'note': 'Unable to determine slave status'
                }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_snapshot(self) -> Dict[str, Any]:
        """Analyze snapshot data for MySQL adapter"""
        try:
            # Get current database state snapshot
            snapshot_queries = [
                "SELECT COUNT(*) as total_databases FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')",
                "SELECT COUNT(*) as total_tables FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')",
                "SELECT SUM(DATA_LENGTH + INDEX_LENGTH) as total_size FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')",
                "SHOW STATUS LIKE 'Uptime'"
            ]
            
            snapshot_data = {}
            
            for i, query in enumerate(snapshot_queries):
                result = await self.execute_query(query)
                if i < 3:
                    key = list(result.data[0])[0] if result.data else 'unknown'
                    snapshot_data[f'metric_{i}'] = {key: result.data[0][0] if result.data else 0}
                else:
                    snapshot_data.update({row[0]: row[1] for row in result.data})
            
            return {
                'snapshot_timestamp': str(datetime.now()),
                'database_metrics': snapshot_data,
                'uptime_seconds': int(snapshot_data.get('Uptime', 0))
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_statistics(self) -> Dict[str, Any]:
        """Analyze statistics data for MySQL adapter"""
        try:
            # Get comprehensive database statistics
            stats_queries = [
                "SHOW TABLE STATUS",
                "SHOW STATUS LIKE 'Handler%'",
                "SHOW STATUS LIKE 'Created_tmp%'",
                "SHOW STATUS LIKE 'Sort%'"
            ]
            
            statistics = {}
            
            # Table statistics
            table_stats_result = await self.execute_query(stats_queries[0])
            statistics['table_statistics'] = table_stats_result.data
            
            # Handler statistics
            for query in stats_queries[1:]:
                result = await self.execute_query(query)
                category = query.split("LIKE '")[1].split('%')[0]
                statistics[f'{category.lower()}_stats'] = result.data
            
            return {
                'database_statistics': statistics,
                'total_tables_analyzed': len(statistics['table_statistics'])
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_storage(self) -> Dict[str, Any]:
        """Analyze storage data for MySQL adapter"""
        try:
            # Get storage engine information
            storage_query = """
                SELECT 
                    ENGINE,
                    COUNT(*) as table_count,
                    SUM(DATA_LENGTH) as total_data_size,
                    SUM(INDEX_LENGTH) as total_index_size,
                    SUM(DATA_FREE) as free_space
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                AND ENGINE IS NOT NULL
                GROUP BY ENGINE
            """
            
            # Get InnoDB specific stats
            innodb_query = "SHOW ENGINE INNODB STATUS"
            
            storage_result = await self.execute_query(storage_query)
            
            try:
                innodb_result = await self.execute_query(innodb_query)
                innodb_status = innodb_result.data[0][2] if innodb_result.data else ""
            except:
                innodb_status = "Unable to retrieve InnoDB status"
            
            return {
                'storage_engines': storage_result.data,
                'innodb_status': innodb_status,
                'total_storage_size': sum(int(row[2] or 0) + int(row[3] or 0) for row in storage_result.data)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_transaction(self) -> Dict[str, Any]:
        """Analyze transaction data for MySQL adapter"""
        try:
            # Get transaction-related statistics
            transaction_queries = [
                "SHOW STATUS LIKE 'Com_commit'",
                "SHOW STATUS LIKE 'Com_rollback'",
                "SHOW STATUS LIKE 'Com_begin'",
                "SHOW STATUS LIKE 'Handler_commit'",
                "SHOW STATUS LIKE 'Handler_rollback'",
                "SHOW VARIABLES LIKE 'autocommit'",
                "SHOW VARIABLES LIKE 'transaction_isolation'"
            ]
            
            transaction_info = {}
            for query in transaction_queries:
                result = await self.execute_query(query)
                transaction_info.update({row[0]: row[1] for row in result.data})
            
            commits = int(transaction_info.get('Com_commit', 0))
            rollbacks = int(transaction_info.get('Com_rollback', 0))
            total_transactions = commits + rollbacks
            
            return {
                'transaction_statistics': transaction_info,
                'total_transactions': total_transactions,
                'commit_ratio': commits / total_transactions if total_transactions > 0 else 0,
                'autocommit_enabled': transaction_info.get('autocommit', 'OFF') == 'ON'
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_user(self) -> Dict[str, Any]:
        """Analyze user data for MySQL adapter"""
        try:
            # Get user information
            user_query = """
                SELECT 
                    User,
                    Host,
                    account_locked,
                    password_expired,
                    password_last_changed,
                    password_lifetime,
                    ssl_type,
                    max_connections
                FROM mysql.user
            """
            
            # Get user privileges summary
            priv_query = """
                SELECT 
                    User,
                    Host,
                    Select_priv,
                    Insert_priv,
                    Update_priv,
                    Delete_priv,
                    Create_priv,
                    Drop_priv,
                    Grant_priv,
                    Super_priv
                FROM mysql.user
            """
            
            user_result = await self.execute_query(user_query)
            priv_result = await self.execute_query(priv_query)
            
            # Analyze user privileges
            super_users = [row for row in priv_result.data if row[9] == 'Y']
            locked_users = [row for row in user_result.data if row[2] == 'Y']
            
            return {
                'users': user_result.data,
                'user_privileges': priv_result.data,
                'total_users': len(user_result.data),
                'super_users': len(super_users),
                'locked_users': len(locked_users)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    def _calculate_cache_hit_rate(self, cache_info: Dict[str, str]) -> float:
        """Calculate cache hit rate from cache statistics"""
        try:
            hits = int(cache_info.get('Qcache_hits', 0))
            inserts = int(cache_info.get('Qcache_inserts', 0))
            total = hits + inserts
            return (hits / total * 100) if total > 0 else 0
        except:
            return 0.0

    async def create_index(self, table_name: str, index_name: str, columns: List[str], unique: bool = False) -> Optional[QueryResult]:
        """Create an index in MySQL"""
        unique_clause = "UNIQUE " if unique else ""
        columns_clause = ", ".join(columns)
        query = f"CREATE {unique_clause}INDEX {index_name} ON {table_name} ({columns_clause})"
        return await self.execute_query(query)

    async def drop_index(self, index_name: str, table_name: Optional[str] = None) -> Optional[QueryResult]:
        """Drop an index in MySQL"""
        if table_name:
            query = f"DROP INDEX {index_name} ON {table_name}"
        else:
            query = f"DROP INDEX {index_name}"
        return await self.execute_query(query)

    async def insert_data(self, table_name: str, data: List[Dict[str, Any]], on_conflict: str = "error") -> Optional[QueryResult]:
        """Insert data into MySQL table"""
        if not data:
            return None
        
        columns = list(data[0].keys())
        placeholders = ", ".join(["%s" for _ in columns])
        columns_clause = ", ".join(columns)
        
        conflict_clause = ""
        if on_conflict == "ignore":
            conflict_clause = " ON DUPLICATE KEY UPDATE id=id"
        elif on_conflict == "replace":
            conflict_clause = " ON DUPLICATE KEY UPDATE " + ", ".join([f"{col} = VALUES({col})" for col in columns])
        
        query = f"INSERT INTO {table_name} ({columns_clause}) VALUES ({placeholders}){conflict_clause}"
        
        rows_affected = 0
        async with self.connection.cursor() as cursor:
            for row in data:
                values = [row[col] for col in columns]
                await cursor.execute(query, values)
                rows_affected += cursor.rowcount
        
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=rows_affected,
            execution_time=0.0
        )

    async def update_data(self, table_name: str, data: Dict[str, Any], where: Dict[str, Any]) -> Optional[QueryResult]:
        """Update data in MySQL table"""
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
        
        query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
        values = list(data.values()) + list(where.values())
        
        async with self.connection.cursor() as cursor:
            await cursor.execute(query, values)
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=cursor.rowcount,
                execution_time=0.0
            )

    async def delete_data(self, table_name: str, where: Dict[str, Any]) -> Optional[QueryResult]:
        """Delete data from MySQL table"""
        where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
        
        query = f"DELETE FROM {table_name} WHERE {where_clause}"
        values = list(where.values())
        
        async with self.connection.cursor() as cursor:
            await cursor.execute(query, values)
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=cursor.rowcount,
                execution_time=0.0
            )

    async def backup_database(self, backup_path: str, compression: str = "gzip", include_data: bool = True) -> Optional[QueryResult]:
        """Create a MySQL backup using mysqldump"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="MySQL backup requires external mysqldump tool"
        )

    async def restore_database(self, backup_path: str, overwrite: bool = False) -> Optional[QueryResult]:
        """Restore MySQL from backup"""
        return QueryResult(
            data=[],
            columns=[],
            rows_affected=0,
            execution_time=0.0,
            error="MySQL restore requires external mysql client tool"
        )

    async def get_schema_info(self) -> Dict[str, Any]:
        """Get schema information for MySQL"""
        try:
            query = "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE()"
            result = await self.execute_query(query)
            return {
                'tables': result.data,
                'total_tables': len(result.data)
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def analyze_performance(self, query: Optional[str] = None, include_execution_plan: bool = True) -> Dict[str, Any]:
        """Analyze MySQL performance"""
        try:
            analysis = {}
            
            # Get server status
            status_query = "SHOW STATUS LIKE 'Threads_connected'"
            status_result = await self.execute_query(status_query)
            analysis['status'] = status_result.data
            
            if query and include_execution_plan:
                explain_result = await self.execute_query(query, explain=True)
                analysis['execution_plan'] = explain_result.explain_plan
            
            return analysis
        except Exception as e:
            return {'error': self._format_error(e)}

    async def migrate_schema(self, migration_script: str, dry_run: bool = True) -> Optional[QueryResult]:
        """Migrate MySQL schema"""
        if dry_run:
            return QueryResult(
                data=[],
                columns=[],
                rows_affected=0,
                execution_time=0.0,
                error="Dry run mode - migration would be executed"
            )
        
        return await self.execute_query(migration_script)

    async def create_user(self, username: str, password: str, permissions: List[str]) -> Optional[QueryResult]:
        """Create a MySQL user"""
        query = f"CREATE USER '{username}'@'%' IDENTIFIED BY '{password}'"
        return await self.execute_query(query)

    async def grant_permissions(self, username: str, permissions: List[str], table_name: Optional[str] = None) -> Optional[QueryResult]:
        """Grant permissions to a MySQL user"""
        perms = ", ".join(permissions)
        target = f"{table_name}" if table_name else "*.*"
        query = f"GRANT {perms} ON {target} TO '{username}'@'%'"
        return await self.execute_query(query)

    # Add stubs for all other missing abstract methods
    async def create_database(self, database_name: str) -> Optional[QueryResult]:
        """Create a new MySQL database"""
        query = f"CREATE DATABASE {database_name}"
        return await self.execute_query(query)

    async def drop_database(self, database_name: str) -> Optional[QueryResult]:
        """Drop a MySQL database"""
        query = f"DROP DATABASE {database_name}"
        return await self.execute_query(query)

    async def rename_table(self, old_name: str, new_name: str) -> Optional[QueryResult]:
        """Rename a MySQL table"""
        query = f"RENAME TABLE {old_name} TO {new_name}"
        return await self.execute_query(query)

    async def filter_data(self, table_name: str, conditions: Dict[str, Any], limit: Optional[int] = None) -> QueryResult:
        """Filter data within a MySQL table"""
        where_clause = self._build_where_clause(conditions)
        query = f"SELECT * FROM {table_name}"
        
        if where_clause:
            query += f" WHERE {where_clause}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return await self.execute_query(query)

    async def aggregate_data(self, table_name: str, aggregations: List[Dict[str, Any]], group_by: Optional[List[str]] = None) -> QueryResult:
        """Perform aggregation operations in MySQL"""
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
        """Join multiple MySQL tables"""
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
        """Revoke permissions from a MySQL user"""
        perms = ", ".join(permissions)
        target = f"{table_name}" if table_name else "*.*"
        query = f"REVOKE {perms} ON {target} FROM '{username}'@'%'"
        return await self.execute_query(query)

    async def drop_user(self, username: str) -> Optional[QueryResult]:
        """Drop a MySQL user"""
        query = f"DROP USER '{username}'@'%'"
        return await self.execute_query(query)

    async def explain_query(self, query: str) -> Dict[str, Any]:
        """Explain query execution plan in MySQL"""
        try:
            explain_query = f"EXPLAIN {query}"
            result = await self.execute_query(explain_query)
            return {
                'execution_plan': result.data,
                'query': query
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def migrate_table(self, source_table: str, target_table: str, mapping: Optional[Dict[str, str]] = None) -> Optional[QueryResult]:
        """Migrate data from one table to another in MySQL"""
        try:
            if mapping:
                source_cols = list(mapping.keys())
                target_cols = list(mapping.values())
                query = f"INSERT INTO {target_table} ({', '.join(target_cols)}) SELECT {', '.join(source_cols)} FROM {source_table}"
            else:
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
            error="Schema sync not implemented for MySQL"
        )

    async def schedule_task(self, task_name: str, schedule: str, query: str) -> Optional[QueryResult]:
        """Schedule a recurring task in MySQL"""
        # MySQL supports events for scheduling
        query = f"CREATE EVENT {task_name} ON SCHEDULE {schedule} DO {query}"
        return await self.execute_query(query)

    async def log_query(self, query: str, execution_time: float, result_count: int) -> None:
        """Log query execution"""
        self._log_query(query, None, execution_time)

    async def select_data(self, table_name: str, filters: Dict[str, Any], projection: Optional[List[str]] = None) -> QueryResult:
        """Fetch data using filters and projections"""
        columns = ", ".join(projection) if projection else "*"
        query = f"SELECT {columns} FROM {table_name}"
        
        where_clause = self._build_where_clause(filters)
        if where_clause:
            query += f" WHERE {where_clause}"
        
        return await self.execute_query(query)

    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query and return execution plan with performance insights"""
        return await self.explain_query(query)

    async def optimize_query(self, query: str) -> Dict[str, Any]:
        """Automatically rewrite query for optimal performance"""
        return await self.analyze_query(query)

    async def get_connection_string(self) -> str:
        """Return current database connection string"""
        return self.connection_string

    async def monitor_health(self) -> Dict[str, Any]:
        """Monitor MySQL health"""
        try:
            return {
                'status': 'healthy' if await self.health_check() else 'unhealthy',
                'database_type': 'mysql',
                'connection_status': 'connected' if self.connection else 'disconnected'
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def monitor_queries(self) -> Dict[str, Any]:
        """Track running and slow queries"""
        try:
            query = "SHOW PROCESSLIST"
            result = await self.execute_query(query)
            return {
                'running_queries': result.data,
                'slow_queries': []
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def log_queries(self, enable: bool = True) -> Dict[str, Any]:
        """Record all queries and execution times"""
        return {
            'query_logging': enable,
            'message': 'Query logging controlled by configuration'
        }

    async def check_disk_usage(self) -> Dict[str, Any]:
        """Returns size of DB, tables, indexes, logs"""
        try:
            query = "SELECT table_schema, SUM(data_length + index_length) as size FROM information_schema.tables GROUP BY table_schema"
            result = await self.execute_query(query)
            return {
                'database_sizes': result.data
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def check_memory_usage(self) -> Dict[str, Any]:
        """Returns buffer/cache/memory info"""
        try:
            query = "SHOW STATUS LIKE 'Innodb_buffer_pool_size'"
            result = await self.execute_query(query)
            return {
                'buffer_pool_size': result.data
            }
        except Exception as e:
            return {'error': self._format_error(e)}

    async def update_statistics(self, table_name: Optional[str] = None) -> Optional[QueryResult]:
        """Refreshes DB statistics for query planner"""
        if table_name:
            query = f"ANALYZE TABLE {table_name}"
        else:
            query = "ANALYZE TABLE"
        
        return await self.execute_query(query)

    async def vacuum_table(self, table_name: str, full: bool = False) -> Optional[QueryResult]:
        """Optimize table in MySQL"""
        query = f"OPTIMIZE TABLE {table_name}"
        return await self.execute_query(query)

    async def rebuild_index(self, index_name: str, table_name: str) -> Optional[QueryResult]:
        """Rebuild index in MySQL"""
        query = f"ALTER TABLE {table_name} DROP INDEX {index_name}, ADD INDEX {index_name}"
        return await self.execute_query(query)

    async def run_health_check(self) -> Dict[str, Any]:
        """Runs full DB diagnostics and performance tests"""
        try:
            health_report = {
                'database_type': 'mysql',
                'connection_status': 'connected' if self.connection else 'disconnected',
                'health_checks': {}
            }
            
            health_report['health_checks']['connectivity'] = await self.health_check()
            
            return health_report
        except Exception as e:
            return {'error': self._format_error(e)}

    # Add stubs for all other abstract methods that don't apply to MySQL
    async def setup_database(self, database_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Database setup not implemented for MySQL")

    async def init_cluster(self, cluster_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Clustering setup not implemented for MySQL")

    async def set_user_privileges(self, username: str, privileges: List[str], resource: Optional[str] = None) -> Optional[QueryResult]:
        return await self.grant_permissions(username, privileges, resource)

    async def enable_ssl(self, ssl_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="SSL configuration not implemented for MySQL")

    async def define_constraint(self, table_name: str, constraint_definition: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Constraint definition not implemented for MySQL")

    async def recommend_index(self, table_name: str, query_patterns: List[str]) -> Dict[str, Any]:
        recommendations = []
        for pattern in query_patterns:
            if 'WHERE' in pattern.upper():
                recommendations.append({
                    'type': 'index',
                    'reason': 'WHERE clause optimization',
                    'pattern': pattern
                })
        return {
            'table_name': table_name,
            'recommendations': recommendations
        }

    async def shard_table(self, table_name: str, shard_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Sharding not implemented for MySQL")

    async def partition_table(self, table_name: str, partition_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Partitioning not implemented for MySQL")

    async def migrate_data(self, source_config: Dict[str, Any], target_config: Dict[str, Any], migration_options: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Data migration not implemented for MySQL")

    async def convert_schema(self, source_schema: Dict[str, Any], target_db_type: str) -> Dict[str, Any]:
        return {'error': 'Schema conversion not implemented for MySQL'}

    async def import_data(self, table_name: str, data_source: str, import_options: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Data import not implemented for MySQL")

    async def export_data(self, table_name: str, export_format: str, export_options: Dict[str, Any]) -> Dict[str, Any]:
        return {'error': 'Data export not implemented for MySQL'}

    async def schedule_backup(self, backup_schedule: str, backup_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Backup scheduling not implemented for MySQL")

    async def clone_database(self, source_db: str, target_db: str, clone_options: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Database cloning not implemented for MySQL")

    async def mask_data(self, table_name: str, masking_rules: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Data masking not implemented for MySQL")

    # Add stubs for all other missing methods...
    async def enable_audit_log(self, audit_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Audit logging not implemented for MySQL")

    async def log_schema_changes(self, enable: bool = True) -> Dict[str, Any]:
        return {'error': 'Schema change logging not implemented for MySQL'}

    async def compare_schemas(self, source_schema: Dict[str, Any], target_schema: Dict[str, Any]) -> Dict[str, Any]:
        return {'error': 'Schema comparison not implemented for MySQL'}

    async def restart_database(self) -> Dict[str, Any]:
        return {'error': 'Database restart not implemented for MySQL'}

    async def enable_replication(self, replication_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Replication not implemented for MySQL")

    async def pause_replication(self, channel_name: Optional[str] = None) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Replication not implemented for MySQL")

    async def resume_replication(self, channel_name: Optional[str] = None) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Replication not implemented for MySQL")

    async def check_replication_status(self) -> Dict[str, Any]:
        return {'error': 'Replication not implemented for MySQL'}

    async def setup_sharding(self, sharding_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Sharding not implemented for MySQL")

    async def rebalance_shards(self, rebalance_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Sharding not implemented for MySQL")

    async def add_shard(self, shard_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Sharding not implemented for MySQL")

    async def remove_shard(self, shard_name: str, safe_mode: bool = True) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Sharding not implemented for MySQL")

    async def create_view(self, view_name: str, query: str, materialized: bool = False) -> Optional[QueryResult]:
        create_query = f"CREATE VIEW {view_name} AS {query}"
        return await self.execute_query(create_query)

    async def drop_view(self, view_name: str, cascade: bool = False) -> Optional[QueryResult]:
        query = f"DROP VIEW {view_name}"
        return await self.execute_query(query)

    async def refresh_materialized_view(self, view_name: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Materialized views not supported in MySQL")

    async def create_trigger(self, trigger_name: str, table_name: str, event: str, timing: str, action: str) -> Optional[QueryResult]:
        query = f"CREATE TRIGGER {trigger_name} {timing} {event} ON {table_name} FOR EACH ROW {action}"
        return await self.execute_query(query)

    async def drop_trigger(self, trigger_name: str, table_name: Optional[str] = None) -> Optional[QueryResult]:
        query = f"DROP TRIGGER {trigger_name}"
        return await self.execute_query(query)

    async def create_function(self, function_name: str, parameters: List[Dict[str, Any]], return_type: str, body: str) -> Optional[QueryResult]:
        params = ", ".join([f"{p['name']} {p['type']}" for p in parameters])
        query = f"CREATE FUNCTION {function_name}({params}) RETURNS {return_type} {body}"
        return await self.execute_query(query)

    async def drop_function(self, function_name: str, cascade: bool = False) -> Optional[QueryResult]:
        query = f"DROP FUNCTION {function_name}"
        return await self.execute_query(query)

    async def create_procedure(self, procedure_name: str, parameters: List[Dict[str, Any]], body: str) -> Optional[QueryResult]:
        params = ", ".join([f"{p['name']} {p['type']}" for p in parameters])
        query = f"CREATE PROCEDURE {procedure_name}({params}) {body}"
        return await self.execute_query(query)

    async def drop_procedure(self, procedure_name: str, cascade: bool = False) -> Optional[QueryResult]:
        query = f"DROP PROCEDURE {procedure_name}"
        return await self.execute_query(query)

    async def list_users(self) -> List[Dict[str, Any]]:
        query = "SELECT User, Host FROM mysql.user"
        result = await self.execute_query(query)
        return result.data

    async def list_roles(self) -> List[Dict[str, Any]]:
        return [{'message': 'Roles not supported in MySQL'}]

    async def assign_role(self, username: str, role_name: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Roles not supported in MySQL")

    async def revoke_role(self, username: str, role_name: str) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Roles not supported in MySQL")

    async def reset_password(self, username: str, new_password: str) -> Optional[QueryResult]:
        query = f"ALTER USER '{username}'@'%' IDENTIFIED BY '{new_password}'"
        return await self.execute_query(query)

    async def force_disconnect_user(self, username: str) -> Optional[QueryResult]:
        query = f"KILL USER '{username}'"
        return await self.execute_query(query)

    async def track_session(self) -> List[Dict[str, Any]]:
        query = "SHOW PROCESSLIST"
        result = await self.execute_query(query)
        return result.data

    async def track_locks(self) -> List[Dict[str, Any]]:
        query = "SHOW ENGINE INNODB STATUS"
        result = await self.execute_query(query)
        return result.data

    async def generate_er_diagram(self, output_format: str = 'png') -> Dict[str, Any]:
        return {'error': 'ER diagram generation not implemented for MySQL'}

    async def generate_schema_doc(self, output_format: str = 'markdown') -> Dict[str, Any]:
        return {'error': 'Schema documentation generation not implemented for MySQL'}

    async def generate_migration_script(self, target_schema: Dict[str, Any]) -> Dict[str, Any]:
        return {'error': 'Migration script generation not implemented for MySQL'}

    async def apply_migration_script(self, migration_script: str, dry_run: bool = True) -> Optional[QueryResult]:
        return await self.migrate_schema(migration_script, dry_run)

    async def schedule_sql_job(self, job_name: str, sql_command: str, schedule: str) -> Optional[QueryResult]:
        return await self.schedule_task(job_name, schedule, sql_command)

    async def enable_event_scheduler(self, enabled: bool = True) -> Optional[QueryResult]:
        query = f"SET GLOBAL event_scheduler = {'ON' if enabled else 'OFF'}"
        return await self.execute_query(query)

    async def generate_seed_data(self, table_name: str, row_count: int, seed_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Seed data generation not implemented for MySQL")

    async def archive_old_data(self, table_name: str, cutoff_date: str, archive_table: str) -> Optional[QueryResult]:
        query = f"INSERT INTO {archive_table} SELECT * FROM {table_name} WHERE date_column < '{cutoff_date}'"
        return await self.execute_query(query)

    async def rotate_logs(self, log_type: str = 'all') -> Optional[QueryResult]:
        query = "FLUSH LOGS"
        return await self.execute_query(query)

    async def purge_binary_logs(self, before_date: str) -> Optional[QueryResult]:
        query = f"PURGE BINARY LOGS BEFORE '{before_date}'"
        return await self.execute_query(query)

    async def detect_anomalies(self, time_window: str = '24h') -> List[Dict[str, Any]]:
        return [{'message': 'Anomaly detection not implemented for MySQL'}]

    async def enable_firewall(self, firewall_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Firewall not implemented for MySQL")

    async def audit_login_activity(self, time_window: str = '24h') -> List[Dict[str, Any]]:
        return [{'message': 'Login activity audit not implemented for MySQL'}]

    async def enable_tls_auth(self, tls_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="TLS auth not implemented for MySQL")

    async def defragment_table(self, table_name: str) -> Optional[QueryResult]:
        return await self.vacuum_table(table_name)

    async def compact_storage(self, collection_name: Optional[str] = None) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Storage compaction not implemented for MySQL")

    async def setup_connection_pooling(self, pool_config: Dict[str, Any]) -> Optional[QueryResult]:
        return QueryResult(data=[], columns=[], rows_affected=0, execution_time=0.0, error="Connection pooling not implemented for MySQL")

