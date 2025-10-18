#!/usr/bin/env python3
import asyncio
from src.database_mcp_server.server import DatabaseMCPServer

async def test_server():
    server = DatabaseMCPServer()
    await server.database_manager.initialize()
    
    tools = await server.list_tools()
    print(f"Total tools: {len(tools)}")
    print("Sample tools:", [t.name for t in tools[:10]])
    
    # Test specific tools that were mentioned in the error
    test_tools = [
        'add_column', 'add_shard', 'aggregate_data', 'analyze_query', 
        'natural_language_query', 'create_table', 'backup_database'
    ]
    
    for tool_name in test_tools:
        tool_found = any(t.name == tool_name for t in tools)
        print(f"Tool '{tool_name}': {'✅ Found' if tool_found else '❌ Missing'}")

if __name__ == "__main__":
    asyncio.run(test_server())
