"""
Configuration management for Database MCP Server
"""

import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ServerConfig:
    """Server configuration"""
    name: str = "database-mcp-server"
    version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    port: int = 8080

@dataclass
class SecurityConfig:
    """Security configuration"""
    encryption_key: Optional[str] = None
    credential_store_path: str = "~/.dbmcp/credentials"
    audit_log_path: str = "logs/audit.log"
    enable_sql_injection_protection: bool = True
    enable_query_logging: bool = True

@dataclass
class ConnectionPoolConfig:
    """Connection pool configuration"""
    default_pool_size: int = 10
    max_pool_size: int = 50
    pool_timeout: int = 30
    pool_recycle: int = 3600

@dataclass
class DatabaseConfig:
    """Individual database configuration"""
    enabled: bool = True
    default_connection: Dict[str, Any] = field(default_factory=dict)
    pool_size: int = 10
    connect_timeout: int = 30

@dataclass
class NLPConfig:
    """Natural Language Processing configuration"""
    enabled: bool = True
    model: str = "en_core_web_sm"
    confidence_threshold: float = 0.7
    max_query_length: int = 1000

@dataclass
class QueryOptimizationConfig:
    """Query optimization configuration"""
    enabled: bool = True
    explain_plans: bool = True
    suggest_indexes: bool = True
    detect_slow_queries: bool = True
    slow_query_threshold: int = 1000

@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    enabled: bool = True
    prometheus_endpoint: str = "/metrics"
    health_check_endpoint: str = "/health"
    collect_query_metrics: bool = True
    collect_connection_metrics: bool = True

@dataclass
class BackupConfig:
    """Backup configuration"""
    enabled: bool = True
    default_backup_path: str = "backups/"
    compression: str = "gzip"
    retention_days: int = 30

@dataclass
class MigrationConfig:
    """Migration configuration"""
    enabled: bool = True
    migration_table: str = "_schema_migrations"
    auto_migrate: bool = False
    backup_before_migrate: bool = True

@dataclass
class RateLimitingConfig:
    """Rate limiting configuration"""
    enabled: bool = True
    requests_per_minute: int = 100
    requests_per_hour: int = 1000
    burst_limit: int = 10

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "json"
    file_path: str = "logs/database-mcp.log"
    max_file_size: str = "100MB"
    backup_count: int = 5

@dataclass
class FeaturesConfig:
    """Features configuration"""
    schema_introspection: bool = True
    query_caching: bool = True
    connection_testing: bool = True
    data_masking: bool = True
    query_validation: bool = True
    performance_analytics: bool = True

class Config:
    """Main configuration class"""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration"""
        self.config_file = config_file or self._get_default_config_file()
        self.config_data = self._load_config()
        
        # Initialize configuration sections
        self.server = self._create_server_config()
        self.security = self._create_security_config()
        self.connection_pools = self._create_connection_pool_config()
        self.databases = self._create_database_configs()
        self.nlp = self._create_nlp_config()
        self.query_optimization = self._create_query_optimization_config()
        self.monitoring = self._create_monitoring_config()
        self.backup = self._create_backup_config()
        self.migration = self._create_migration_config()
        self.rate_limiting = self._create_rate_limiting_config()
        self.logging = self._create_logging_config()
        self.features = self._create_features_config()
        
    def _get_default_config_file(self) -> str:
        """Get default configuration file path"""
        config_file = os.getenv("DATABASE_CONFIG_FILE")
        if config_file and os.path.exists(config_file):
            return config_file
            
        # Try common locations
        locations = [
            "config/database.yaml",
            "database.yaml",
            os.path.expanduser("~/.dbmcp/config.yaml")
        ]
        
        for location in locations:
            if os.path.exists(location):
                return location
                
        # Return default location
        return "config/database.yaml"
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if not os.path.exists(self.config_file):
            # Create default configuration if file doesn't exist
            return self._create_default_config()
            
        try:
            with open(self.config_file, 'r') as f:
                config_data = yaml.safe_load(f)
                
            # Expand environment variables
            config_data = self._expand_environment_variables(config_data)
            return config_data
            
        except Exception as e:
            raise ValueError(f"Error loading configuration from {self.config_file}: {e}")
            
    def _expand_environment_variables(self, obj: Any) -> Any:
        """Recursively expand environment variables in configuration"""
        if isinstance(obj, dict):
            return {k: self._expand_environment_variables(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_environment_variables(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]
            return os.getenv(env_var, obj)
        else:
            return obj
            
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        return {
            "server": {
                "name": "database-mcp-server",
                "version": "1.0.0",
                "debug": False,
                "log_level": "INFO",
                "port": 8080
            },
            "security": {
                "encryption_key": None,
                "credential_store_path": "~/.dbmcp/credentials",
                "audit_log_path": "logs/audit.log",
                "enable_sql_injection_protection": True,
                "enable_query_logging": True
            },
            "connection_pools": {
                "default_pool_size": 10,
                "max_pool_size": 50,
                "pool_timeout": 30,
                "pool_recycle": 3600
            },
            "databases": {
                "sqlite": {
                    "enabled": True,
                    "default_connection": {
                        "database": "test.db"
                    },
                    "pool_size": 5
                }
            },
            "nlp": {
                "enabled": True,
                "model": "en_core_web_sm",
                "confidence_threshold": 0.7,
                "max_query_length": 1000
            },
            "query_optimization": {
                "enabled": True,
                "explain_plans": True,
                "suggest_indexes": True,
                "detect_slow_queries": True,
                "slow_query_threshold": 1000
            },
            "monitoring": {
                "enabled": True,
                "prometheus_endpoint": "/metrics",
                "health_check_endpoint": "/health",
                "collect_query_metrics": True,
                "collect_connection_metrics": True
            },
            "backup": {
                "enabled": True,
                "default_backup_path": "backups/",
                "compression": "gzip",
                "retention_days": 30
            },
            "migration": {
                "enabled": True,
                "migration_table": "_schema_migrations",
                "auto_migrate": False,
                "backup_before_migrate": True
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 100,
                "requests_per_hour": 1000,
                "burst_limit": 10
            },
            "logging": {
                "level": "INFO",
                "format": "json",
                "file_path": "logs/database-mcp.log",
                "max_file_size": "100MB",
                "backup_count": 5
            },
            "features": {
                "schema_introspection": True,
                "query_caching": True,
                "connection_testing": True,
                "data_masking": True,
                "query_validation": True,
                "performance_analytics": True
            }
        }
        
    def _create_server_config(self) -> ServerConfig:
        """Create server configuration"""
        server_data = self.config_data.get("server", {})
        return ServerConfig(
            name=server_data.get("name", "database-mcp-server"),
            version=server_data.get("version", "1.0.0"),
            debug=server_data.get("debug", False),
            log_level=server_data.get("log_level", "INFO"),
            port=server_data.get("port", 8080)
        )
        
    def _create_security_config(self) -> SecurityConfig:
        """Create security configuration"""
        security_data = self.config_data.get("security", {})
        return SecurityConfig(
            encryption_key=security_data.get("encryption_key"),
            credential_store_path=security_data.get("credential_store_path", "~/.dbmcp/credentials"),
            audit_log_path=security_data.get("audit_log_path", "logs/audit.log"),
            enable_sql_injection_protection=security_data.get("enable_sql_injection_protection", True),
            enable_query_logging=security_data.get("enable_query_logging", True)
        )
        
    def _create_connection_pool_config(self) -> ConnectionPoolConfig:
        """Create connection pool configuration"""
        pool_data = self.config_data.get("connection_pools", {})
        return ConnectionPoolConfig(
            default_pool_size=pool_data.get("default_pool_size", 10),
            max_pool_size=pool_data.get("max_pool_size", 50),
            pool_timeout=pool_data.get("pool_timeout", 30),
            pool_recycle=pool_data.get("pool_recycle", 3600)
        )
        
    def _create_database_configs(self) -> Dict[str, DatabaseConfig]:
        """Create database configurations"""
        databases_data = self.config_data.get("databases", {})
        configs = {}
        
        for db_name, db_data in databases_data.items():
            configs[db_name] = DatabaseConfig(
                enabled=db_data.get("enabled", True),
                default_connection=db_data.get("default_connection", {}),
                pool_size=db_data.get("pool_size", 10),
                connect_timeout=db_data.get("connect_timeout", 30)
            )
            
        return configs
        
    def _create_nlp_config(self) -> NLPConfig:
        """Create NLP configuration"""
        nlp_data = self.config_data.get("nlp", {})
        return NLPConfig(
            enabled=nlp_data.get("enabled", True),
            model=nlp_data.get("model", "en_core_web_sm"),
            confidence_threshold=nlp_data.get("confidence_threshold", 0.7),
            max_query_length=nlp_data.get("max_query_length", 1000)
        )
        
    def _create_query_optimization_config(self) -> QueryOptimizationConfig:
        """Create query optimization configuration"""
        opt_data = self.config_data.get("query_optimization", {})
        return QueryOptimizationConfig(
            enabled=opt_data.get("enabled", True),
            explain_plans=opt_data.get("explain_plans", True),
            suggest_indexes=opt_data.get("suggest_indexes", True),
            detect_slow_queries=opt_data.get("detect_slow_queries", True),
            slow_query_threshold=opt_data.get("slow_query_threshold", 1000)
        )
        
    def _create_monitoring_config(self) -> MonitoringConfig:
        """Create monitoring configuration"""
        mon_data = self.config_data.get("monitoring", {})
        return MonitoringConfig(
            enabled=mon_data.get("enabled", True),
            prometheus_endpoint=mon_data.get("prometheus_endpoint", "/metrics"),
            health_check_endpoint=mon_data.get("health_check_endpoint", "/health"),
            collect_query_metrics=mon_data.get("collect_query_metrics", True),
            collect_connection_metrics=mon_data.get("collect_connection_metrics", True)
        )
        
    def _create_backup_config(self) -> BackupConfig:
        """Create backup configuration"""
        backup_data = self.config_data.get("backup", {})
        return BackupConfig(
            enabled=backup_data.get("enabled", True),
            default_backup_path=backup_data.get("default_backup_path", "backups/"),
            compression=backup_data.get("compression", "gzip"),
            retention_days=backup_data.get("retention_days", 30)
        )
        
    def _create_migration_config(self) -> MigrationConfig:
        """Create migration configuration"""
        migration_data = self.config_data.get("migration", {})
        return MigrationConfig(
            enabled=migration_data.get("enabled", True),
            migration_table=migration_data.get("migration_table", "_schema_migrations"),
            auto_migrate=migration_data.get("auto_migrate", False),
            backup_before_migrate=migration_data.get("backup_before_migrate", True)
        )
        
    def _create_rate_limiting_config(self) -> RateLimitingConfig:
        """Create rate limiting configuration"""
        rate_data = self.config_data.get("rate_limiting", {})
        return RateLimitingConfig(
            enabled=rate_data.get("enabled", True),
            requests_per_minute=rate_data.get("requests_per_minute", 100),
            requests_per_hour=rate_data.get("requests_per_hour", 1000),
            burst_limit=rate_data.get("burst_limit", 10)
        )
        
    def _create_logging_config(self) -> LoggingConfig:
        """Create logging configuration"""
        log_data = self.config_data.get("logging", {})
        return LoggingConfig(
            level=log_data.get("level", "INFO"),
            format=log_data.get("format", "json"),
            file_path=log_data.get("file_path", "logs/database-mcp.log"),
            max_file_size=log_data.get("max_file_size", "100MB"),
            backup_count=log_data.get("backup_count", 5)
        )
        
    def _create_features_config(self) -> FeaturesConfig:
        """Create features configuration"""
        features_data = self.config_data.get("features", {})
        return FeaturesConfig(
            schema_introspection=features_data.get("schema_introspection", True),
            query_caching=features_data.get("query_caching", True),
            connection_testing=features_data.get("connection_testing", True),
            data_masking=features_data.get("data_masking", True),
            query_validation=features_data.get("query_validation", True),
            performance_analytics=features_data.get("performance_analytics", True)
        )
        
    def get_database_config(self, database_name: str) -> Optional[DatabaseConfig]:
        """Get configuration for a specific database"""
        return self.databases.get(database_name)
        
    def is_database_enabled(self, database_name: str) -> bool:
        """Check if a database is enabled"""
        config = self.get_database_config(database_name)
        return config is not None and config.enabled
        
    def save_config(self, config_file: Optional[str] = None) -> None:
        """Save current configuration to file"""
        output_file = config_file or self.config_file
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Write configuration
        with open(output_file, 'w') as f:
            yaml.dump(self.config_data, f, default_flow_style=False, indent=2)
