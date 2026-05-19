import asyncio
import argparse
import sys
import os
from dotenv import load_dotenv

# Load env before importing mcp to ensure CLICKUP_API_KEY is available
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    parser = argparse.ArgumentParser(description="Create a ClickUp task via MCP")
    parser.add_argument('--email', required=True, help="Email address of the client (Task Name)")
    args = parser.parse_args()

    if "CLICKUP_API_KEY" not in os.environ:
        sys.stderr.write("Error: CLICKUP_API_KEY is not set in the .env file. Please configure it first.\n")
        sys.exit(1)

    print("Spawning ClickUp MCP Server via npx...")
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-clickup"],
        env=os.environ.copy()
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                print(f"Calling MCP tool 'clickup_create_task' for {args.email}...")
                result = await session.call_tool("clickup_create_task", {
                    "list_id": "901218146714",
                    "name": args.email,
                    "status": "intake"
                })
                
                print(f"Success! ClickUp task created: {result}")
    except Exception as e:
        sys.stderr.write(f"Failed to create ClickUp task via MCP: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
