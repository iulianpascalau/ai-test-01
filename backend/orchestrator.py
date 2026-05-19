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
            "CRITICAL INSTRUCTION FOR TOOL CALLING:\n"
            f"You have access to the following function tools: {', '.join(tool_names)}. "
            "When the user asks you to perform an action or fetch data, YOU MUST USE A TOOL. "
            "Do not output raw JSON or code blocks in your text response. Use the native tool calling format. "
            "If you need to fetch ClickUp data, use the clickup tools. "
            "If a provided tool matches the intent of the user, JUST CALL THE TOOL natively."
        )
    return system_prompt

async def process_command(user_command: str):
    """Sends the command to the LLM and orchestrates multi-turn execution."""
    logger.info(f"Received user command: {user_command}")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
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
    
    system_prompt = get_system_prompt(tools)
    system_prompt += (
        "\n\nCRITICAL INSTRUCTION FOR FETCHING DATA:\n"
        "If you need to fetch data from ClickUp or execute custom logic, DO NOT try to use a JSON tool call. "
        "Instead, WRITE A PYTHON SCRIPT in a standard markdown block starting with ```python\n. "
        "The system will automatically execute your script and feed the output back to you so you can read it. "
        "You can access the ClickUp API token via os.environ.get('CLICKUP_API_TOKEN'). "
        "Always use print() to output the data you want to read."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_command}
    ]
    
    async def run_agent_loop():
        MAX_TURNS = 5
        for turn in range(MAX_TURNS):
            logger.info(f"Agent Loop Turn {turn + 1}: Sending prompt to LLM...")
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            msg = response.choices[0].message
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
                # Check if the LLM wrote a python script instead
                import re
                if msg.content and "```python" in msg.content:
                    logger.info("Python code block detected in response. Executing script...")
                    code_match = re.search(r"```python\n(.*?)\n```", msg.content, re.DOTALL)
                    if code_match:
                        code = code_match.group(1)
                        script_path = os.path.join(base_dir, "execution", "agent_temp_script.py")
                        
                        with open(script_path, "w") as f:
                            f.write(code)
                        
                        import sys
                        python_exe = sys.executable
                        process = await asyncio.create_subprocess_shell(
                            f"{python_exe} {script_path}",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            cwd=base_dir
                        )
                        stdout, stderr = await process.communicate()
                        
                        res_content = f"[System: Python Script Execution Results]\nStdout:\n{stdout.decode('utf-8')}\nStderr:\n{stderr.decode('utf-8')}"
                        logger.info(f"Script executed. Feeding output back to LLM. Stdout length: {len(stdout)}")
                        messages.append({"role": "user", "content": res_content})
                        continue # Continue the loop so the LLM can read the output!
                
                # If no python block and no tool calls, it's the final answer
                logger.info("No tool calls or python scripts detected. Returning final response to user.")
                if msg.content and "execute_function_name_placeholder" in msg.content:
                    return {"status": "error", "message": "The LLM model leaked a tool placeholder."}
                return {
                    "status": "success",
                    "message": msg.content or "Done."
                }
                
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                args_str = tool_call.function.arguments
                logger.info(f"Executing tool: {tool_name}")
                
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
                        execution_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
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
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": "Error: Unknown tool."
                    })
                        
        return {
            "status": "success",
            "message": "Max tool turns reached. Final response: " + (msg.content or "None")
        }
        
    try:
        return await asyncio.wait_for(run_agent_loop(), timeout=180.0)
    except asyncio.TimeoutError:
        return {"status": "error", "message": "The orchestrator timed out during execution."}
    except Exception as e:
        logger.error(f"Error during orchestrator process_command: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"Server Error: {str(e)}"}
