#!/usr/bin/env python3
import sys
import subprocess
import shlex
import re
import os

# Deterministic Blocklist of dangerous command patterns
DANGEROUS_COMMANDS = {
    "rm": [r"-r", r"-f", r"\*"], # Block recursive/force removes
    "sudo": [],                  # Block any privilege escalation
    "su": [],                    # Block user switching
    "chmod": [r"777", r"-R"],    # Block giving full permissions or recursive changes
    "chown": [r"-R"],            # Block recursive ownership changes
    "mkfs": [],                  # Block formatting
    "dd": [],                    # Block disk cloning/overwriting
    "mv": [r"/dev", r"/etc"],    # Prevent moving system files
}

DANGEROUS_PATTERNS = [
    r">\s*/dev/",                # Block redirection to devices
    r">\s*/etc/",                # Block redirection to system configs
    r":\(\)\{ :\|:& \};:",       # Block fork bombs
]

def is_safe(command_str):
    """
    Parses and checks if the shell command is safe to execute.
    """
    # 1. Check raw patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command_str):
            print(f"BLOCKED: Command matches dangerous pattern '{pattern}'")
            return False
            
    # 2. Tokenize and check specific commands
    try:
        tokens = shlex.split(command_str)
    except ValueError:
        # If shlex fails (e.g. unclosed quotes), block it to be safe
        print("BLOCKED: Could not parse command properly.")
        return False

    for i, token in enumerate(tokens):
        base_cmd = os.path.basename(token) if token else ""
        if base_cmd in DANGEROUS_COMMANDS:
            blocked_args = DANGEROUS_COMMANDS[base_cmd]
            # If no specific args are needed to block, block the whole command (e.g. 'sudo')
            if not blocked_args:
                print(f"BLOCKED: Command '{base_cmd}' is completely forbidden.")
                return False
                
            # Check following tokens for forbidden arguments
            for subsequent_token in tokens[i+1:]:
                # If we hit another command (e.g., after a pipe), stop checking args for this command
                if subsequent_token in ["|", "&&", "||", ";"]:
                    break
                for arg_pattern in blocked_args:
                    if re.search(arg_pattern, subsequent_token):
                        print(f"BLOCKED: Command '{base_cmd}' used with forbidden argument matching '{arg_pattern}'")
                        return False

    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python safe_runner.py '<shell_command>'")
        sys.exit(1)
        
    command_str = sys.argv[1]
    
    if not is_safe(command_str):
        print("\n--- EXECUTION ABORTED DUE TO SAFETY GUARDRAILS ---")
        sys.exit(1)
        
    print(f"Command '{command_str}' passed safety checks. Executing...")
    
    try:
        # We run with shell=True to allow pipes, but we've sanitized it.
        result = subprocess.run(command_str, shell=True, text=True, capture_output=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
            
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
