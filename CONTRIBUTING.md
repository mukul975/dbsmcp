# Contributing to Database MCP Server

We love your input! We want to make contributing to Database MCP Server as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Development Process

We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

## Pull Requests

Pull requests are the best way to propose changes to the codebase. We actively welcome your pull requests:

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Development Setup

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/database-mcp-server.git
cd database-mcp-server
```

2. **Create a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install development dependencies:**
```bash
pip install -r requirements-dev.txt
```

4. **Install pre-commit hooks:**
```bash
pre-commit install
```

5. **Run tests to ensure everything works:**
```bash
python -m pytest
```

## Code Style

We use several tools to maintain code quality:

- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking
- **pytest** for testing

Run all checks:
```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type check
mypy src/

# Run tests
pytest
```

## Testing

We use pytest for testing. Please ensure:

1. **Write tests** for new functionality
2. **Update tests** when modifying existing code
3. **Ensure all tests pass** before submitting PR
4. **Aim for high test coverage** (>90%)

Run tests:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_mysql.py

# Run tests matching pattern
pytest -k "test_connection"
```

## Database Adapter Development

When adding support for a new database:

1. **Create adapter class** in `src/database_mcp_server/adapters/`
2. **Inherit from BaseAdapter** and implement all abstract methods
3. **Add configuration** in `config/database.yaml.example`
4. **Write comprehensive tests** in `tests/`
5. **Update documentation** in README.md

Example adapter structure:
```python
from .base_adapter import BaseAdapter, QueryResult

class NewDatabaseAdapter(BaseAdapter):
    async def connect(self) -> None:
        # Implementation
        pass
    
    async def execute_query(self, query: str, parameters=None) -> QueryResult:
        # Implementation
        pass
    
    # ... implement all other abstract methods
```

## Adding New Tools

When adding new MCP tools:

1. **Add tool definition** in `server.py`
2. **Implement handler** in the `call_tool` method
3. **Add business logic** in `DatabaseManager`
4. **Write tests** for the new tool
5. **Update documentation**

Tool definition example:
```python
types.Tool(
    name="new_tool",
    description="Description of what the tool does",
    inputSchema={
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
            "param2": {"type": "integer"}
        },
        "required": ["param1"]
    }
)
```

## Documentation

- **Docstrings**: All public methods must have comprehensive docstrings
- **Type hints**: Use type hints for all function parameters and return values
- **Comments**: Add comments for complex logic
- **README**: Update README.md for new features
- **Examples**: Provide usage examples for new functionality

## Commit Messages

Use clear and meaningful commit messages:

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **test**: Adding missing tests or correcting existing tests
- **chore**: Changes to the build process or auxiliary tools

Examples:
```
feat: add PostgreSQL connection pooling support
fix: resolve MySQL adapter timeout issue
docs: update installation instructions
test: add integration tests for MongoDB adapter
```

## Issue Reporting

When reporting issues, please include:

1. **Clear description** of the problem
2. **Steps to reproduce** the issue
3. **Expected behavior** vs actual behavior
4. **Environment details** (OS, Python version, database versions)
5. **Error messages** and stack traces
6. **Minimal code example** if applicable

## Feature Requests

For feature requests, please:

1. **Check existing issues** to avoid duplicates
2. **Provide clear use case** and motivation
3. **Describe proposed solution** if you have one
4. **Consider implementation complexity**
5. **Be open to discussion** and alternative approaches

## Code Review Process

All submissions require review. We use GitHub pull requests for this purpose:

1. **Automated checks** must pass (tests, linting, etc.)
2. **At least one maintainer** must approve
3. **Address feedback** promptly and professionally
4. **Keep PRs focused** - one feature/fix per PR
5. **Update documentation** as needed

## Security

If you discover a security vulnerability, please:

1. **Do NOT** open a public issue
2. **Email** security@example.com with details
3. **Allow time** for us to address the issue
4. **Follow responsible disclosure** practices

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to:

- **Open an issue** for questions about contributing
- **Join discussions** in GitHub Discussions
- **Contact maintainers** directly if needed

Thank you for contributing to Database MCP Server! 🎉