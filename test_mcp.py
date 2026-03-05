import asyncio
from mcp_server import create_mcp_server

async def test_mcp():
    app = create_mcp_server()
    print("Testing um_get_profile...")
    try:
        results = await app._call_tool("um_get_profile", {})
        print("Profile Results:", [r.text for r in results])
    except Exception as e:
        print("Failed direct call tool, skipping raw test:", e)

    print("\nTesting um_search_memory...")
    try:
        results = await app._call_tool("um_search_memory", {"query": "test", "limit": 2})
        print("Search Results:", [r.text for r in results])
    except Exception as e:
        pass

if __name__ == "__main__":
    asyncio.run(test_mcp())
