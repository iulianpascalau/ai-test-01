import os
import json
from openai import AsyncOpenAI
import config

LITELLM_BASE_URL = config.LITELLM_BASE_URL
LITELLM_API_KEY = config.LITELLM_API_KEY
MODEL_NAME = config.MODEL_NAME

client = AsyncOpenAI(
    base_url=LITELLM_BASE_URL,
    api_key=LITELLM_API_KEY
)

def get_system_prompt():
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
    
    return system_prompt

async def process_command(user_command: str):
    """Sends the command to the LLM and orchestrates execution."""
    system_prompt = get_system_prompt()
    
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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_command}
    ]

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message

        # Handle tool calls if the LLM decides to execute something
        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            if tool_call.function.name == "execute_send_email":
                args = json.loads(tool_call.function.arguments)
                email = args.get("email")
                
                # In production, this would trigger subprocess.Popen to run the script
                # and stream logs back to the frontend.
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                script_path = os.path.join(base_dir, "execution", "send_email.py")
                template_path = os.path.join(base_dir, "directives", "templates", "onboarding.txt")
                
                execution_command = f"python {script_path} --to {email} --subject \"Welcome!\" --template {template_path}"
                
                return {
                    "status": "executing",
                    "message": f"Orchestrating tool: {tool_call.function.name}",
                    "details": f"Spawning execution process for {email}...",
                    "command_staged": execution_command
                }
        
        # If no tool was called, return the text response
        return {
            "status": "success",
            "message": response_message.content
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
