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

    if "CLICKUP_API_TOKEN" not in os.environ:
        sys.stderr.write("Error: CLICKUP_API_TOKEN is not set in the .env file. Please configure it first.\n")
        sys.exit(1)

    print("Spawning ClickUp MCP Server via npx...")
    env = os.environ.copy()
    env["npm_config_yes"] = "true"
    env["npm_config_loglevel"] = "error"
    env["npm_config_update_notifier"] = "false"
    
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@cavort-it-systems/clickup-mcp"],
        env=env
    )

    async def run_mcp():
        sys.stderr.write("Starting stdio_client...\n")
        async with stdio_client(server_params) as (read, write):
            sys.stderr.write("Client initialized. Creating session...\n")
            async with ClientSession(read, write) as session:
                sys.stderr.write("Initializing session handshake...\n")
                await session.initialize()
                
                sys.stderr.write(f"Calling MCP tool 'clickup_create_task' for {args.email}...\n")
                result = await session.call_tool("clickup_create_task", {
                    "list_id": "901218146714",
                    "name": args.email,
                    "status": "intake"
                })
                
                print(f"Success! ClickUp task created: {result}")

    try:
        # Prevent the script from hanging forever if npx gets stuck
        await asyncio.wait_for(run_mcp(), timeout=45.0)
    except asyncio.TimeoutError:
        sys.stderr.write("Failed: The MCP server timed out after 45 seconds (npx might be stuck or installing). Please try again.\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Failed to create ClickUp task via MCP: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
