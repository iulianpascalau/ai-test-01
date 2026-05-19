import os
import json
import logging
from openai import AsyncOpenAI
import config

# Configure logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_backend.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("orchestrator")

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
    """Sends the command to the LLM and orchestrates execution."""
    logger.info(f"Received user command: {user_command}")
    
    # Define the tools (Execution layer scripts)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_send_email",
                "description": "Sends an onboarding email to a client and adds them to ClickUp.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email": {
                            "type": "string",
                            "description": "The email address of the client to onboard."
                        }
                    },
                    "required": ["email"]
                }
            }
        }
    ]

    system_prompt = get_system_prompt(tools)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_command}
    ]

    try:
        logger.info("Sending prompt to LLM...")
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        logger.info(f"Received LLM response. Tool calls: {bool(response_message.tool_calls)}")

        # Handle tool calls if the LLM decides to execute something
        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            if tool_call.function.name == "execute_send_email":
                args = json.loads(tool_call.function.arguments)
                email = args.get("email")
                
                logger.info(f"Executing tool: {tool_call.function.name} for email: {email}")
                
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                script_path = os.path.join(base_dir, "execution", "send_email.py")
                template_path = os.path.join(base_dir, "directives", "templates", "onboarding.txt")
                
                import sys
                python_exe = sys.executable
                execution_command = f"{python_exe} {script_path} --to {email} --subject \"Welcome!\" --template {template_path}"
                
                import asyncio
                logger.info(f"Spawning shell: {execution_command}")
                
                # Execute the script asynchronously
                process = await asyncio.create_subprocess_shell(
                    execution_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    logger.info("Script executed successfully.")
                    return {
                        "status": "success",
                        "message": f"Successfully executed onboarding for {email}!",
                        "details": stdout.decode('utf-8').strip(),
                        "command_staged": execution_command
                    }
                else:
                    logger.error(f"Script failed with code {process.returncode}: {stderr.decode('utf-8')}")
                    return {
                        "status": "error",
                        "message": f"Execution failed for {email}.",
                        "details": stderr.decode('utf-8').strip()
                    }
        
        content = response_message.content or ""
        
        # Fallback for LiteLLM tool leaking bug
        if "execute_function_name_placeholder" in content:
            logger.warning("LiteLLM tool placeholder leaked into content.")
            return {
                "status": "error",
                "message": "The LLM model failed to trigger the internal tool correctly. Please try again."
            }

        # If no tool was called, return the text response
        logger.info("No tool called. Returning raw text response.")
        return {
            "status": "success",
            "message": content
        }

    except Exception as e:
        logger.error(f"Error during orchestrator process_command: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }
