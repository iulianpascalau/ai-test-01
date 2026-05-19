import os
import json
import logging
import asyncio
from openai import AsyncOpenAI
import config

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configure logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_backend.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("orchestrator")

try:
    import subprocess
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_tag = subprocess.check_output(
        ["git", "describe", "--tags", "--always"], 
        stderr=subprocess.STDOUT, 
        text=True, 
        cwd=root_dir
    ).strip()
    logger.info(f"========== Agentic Workspace Backend Started | Version: {git_tag} ==========")
except Exception as e:
    logger.info(f"========== Agentic Workspace Backend Started | Version: Unknown (Error: {e}) ==========")

LITELLM_BASE_URL = config.LITELLM_BASE_URL
LITELLM_API_KEY = config.LITELLM_API_KEY
MODEL_NAME = config.MODEL_NAME

client = AsyncOpenAI(
    base_url=LITELLM_BASE_URL,
    api_key=LITELLM_API_KEY
)

def get_system_prompt(tools=None):
    """Reads AGENTS.md and all directives to construct the system prompt."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Read AGENTS.md
    agents_path = os.path.join(base_dir, "AGENTS.md")
    if os.path.exists(agents_path):
        with open(agents_path, "r") as f:
            system_prompt = f.read() + "\n\n"
    else:
        system_prompt = "You are an agent operating within a 3-layer architecture.\n\n"

    # Read Directives
    system_prompt += "### Available Directives\n"
    directives_dir = os.path.join(base_dir, "directives")
    if os.path.exists(directives_dir):
        for filename in os.listdir(directives_dir):
            if filename.endswith(".md"):
                with open(os.path.join(directives_dir, filename), "r") as f:
                    system_prompt += f"--- {filename} ---\n{f.read()}\n\n"
    
    if tools:
        tool_names = [t["function"]["name"] for t in tools]
        system_prompt += (
            "CRITICAL INSTRUCTION:\n"
            f"You have access to the following function tools: {', '.join(tool_names)}. "
            "The directives above may mention running python scripts, bash commands, or MCP tools directly, "
            "BUT you must map those instructions to one of the provided function tools. "
            "DO NOT attempt to write bash commands, run python manually, or return placeholder text. "
            "If a provided tool matches the intent of the directive, JUST CALL THE TOOL."
        )
    return system_prompt

async def process_command(user_command: str):
    """Sends the command to the LLM and orchestrates multi-turn execution."""
    logger.info(f"Received user command: {user_command}")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. MCP Server Setup for Dynamic Tools
    env = os.environ.copy()
    env["npm_config_yes"] = "true"
    env["npm_config_loglevel"] = "error"
    env["npm_config_update_notifier"] = "false"
    
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@cavort-it-systems/clickup-mcp"],
        env=env
    )
    
    async def run_agent_loop():
        logger.info("Initializing MCP connection for tool discovery...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Discover MCP tools
                mcp_tools_resp = await session.list_tools()
                
                # Base custom tools
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "execute_send_email",
                            "description": "Sends an onboarding email to a client. (Automatically creates CRM task as well)",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string"}
                                },
                                "required": ["email"]
                            }
                        }
                    }
                ]
                
                # Map external MCP tools to OpenAI format
                for tool in mcp_tools_resp.tools:
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema
                        }
                    })
                
                system_prompt = get_system_prompt(tools)
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_command}
                ]
                
                MAX_TURNS = 7
                for turn in range(MAX_TURNS):
                    logger.info(f"Agent Loop Turn {turn + 1}: Sending prompt to LLM...")
                    response = await client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=messages,
                        tools=tools,
                        tool_choice="auto"
                    )
                    
                    msg = response.choices[0].message
                    
                    # Convert OpenAI Message object to a safe dict for appending
                    msg_dict = {"role": "assistant"}
                    if msg.content:
                        msg_dict["content"] = msg.content
                    if msg.tool_calls:
                        msg_dict["tool_calls"] = []
                        for tc in msg.tool_calls:
                            msg_dict["tool_calls"].append({
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            })
                    messages.append(msg_dict)
                    
                    if not msg.tool_calls:
                        logger.info("No tool calls detected. Returning final response to user.")
                        if msg.content and "execute_function_name_placeholder" in msg.content:
                            return {"status": "error", "message": "The LLM model leaked a tool placeholder."}
                        return {
                            "status": "success",
                            "message": msg.content or "Done."
                        }
                        
                    # Handle Tool Calls
                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.function.name
                        args_str = tool_call.function.arguments
                        logger.info(f"Executing tool: {tool_name} with args: {args_str}")
                        
                        try:
                            args = json.loads(args_str)
                        except Exception:
                            args = {}
                            
                        if tool_name == "execute_send_email":
                            email = args.get("email")
                            script_path = os.path.join(base_dir, "execution", "send_email.py")
                            template_path = os.path.join(base_dir, "directives", "templates", "onboarding.txt")
                            
                            import sys
                            python_exe = sys.executable
                            execution_command = f"{python_exe} {script_path} --to {email} --subject \"Welcome!\" --template {template_path}"
                            
                            process = await asyncio.create_subprocess_shell(
                                execution_command,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            stdout, stderr = await process.communicate()
                            
                            if process.returncode == 0:
                                # Chain the old clickup_mcp.py script to maintain original atomic flow
                                mcp_script_path = os.path.join(base_dir, "execution", "clickup_mcp.py")
                                mcp_command = f"{python_exe} {mcp_script_path} --email {email}"
                                mcp_process = await asyncio.create_subprocess_shell(
                                    mcp_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                                )
                                mcp_stdout, mcp_stderr = await mcp_process.communicate()
                                
                                if mcp_process.returncode == 0:
                                    res_content = "Email sent and CRM task created successfully."
                                else:
                                    res_content = f"Email sent, but ClickUp task failed: {mcp_stderr.decode('utf-8')}"
                            else:
                                res_content = f"Email script failed: {stderr.decode('utf-8')}"
                            
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_name,
                                "content": res_content
                            })
                        else:
                            # Dynamically forward any other tool directly to the running MCP Server!
                            try:
                                result = await session.call_tool(tool_name, args)
                                content_str = "\n".join([c.text for c in result.content if hasattr(c, 'text')])
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": tool_name,
                                    "content": content_str
                                })
                                logger.info(f"MCP Tool returned successfully.")
                            except Exception as e:
                                logger.error(f"MCP Tool Error: {str(e)}")
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": tool_name,
                                    "content": f"MCP Tool Error: {str(e)}"
                                })
                                
                return {
                    "status": "success",
                    "message": "Max tool turns reached. Final response: " + (msg.content or "None")
                }
                
    try:
        # Prevent the whole request from hanging if MCP stalls
        return await asyncio.wait_for(run_agent_loop(), timeout=180.0)
    except asyncio.TimeoutError:
        return {"status": "error", "message": "The orchestrator timed out during execution."}
    except Exception as e:
        logger.error(f"Error during orchestrator process_command: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"Server Error: {str(e)}"}
