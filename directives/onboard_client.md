# Onboard Client Directive

**Goal:** Send an automated onboarding email to a new client that introduces the company, provides background information, and includes a kickoff call calendar link. Then, automatically add the client to the ClickUp CRM List with the status set to Intake.

**Inputs:**
- Client email address (provided by user in the prompt)

**Prerequisites:**
- `COMPANY_NAME` and `CALENDAR_LINK` must be set in the `.env` file.
- `credentials.json` must be populated with valid Google OAuth credentials (Desktop App) for the Gmail API.
- ClickUp MCP Server must be running and connected via `mcp_config.json`.
- Python dependencies installed: `google-api-python-client google-auth-httplib2 google-auth-oauthlib python-dotenv`

**Tools to Use:**
- `execution/send_email.py`: General Python script utilizing the Gmail API to send emails.
- `directives/templates/onboarding.txt`: Template file containing the email body.
- **ClickUp MCP (`mcp_clickup_clickup_create_task`)**: To add the client to the CRM.

**Execution Steps:**
1. Check if `COMPANY_NAME` and `CALENDAR_LINK` are in `.env`. If not, ask the user to provide them or add them.
2. Check if `credentials.json` is empty. If it is `{}` or empty, prompt the user to configure Gmail API.
3. If prerequisites are met, run the email script: 
   `python execution/send_email.py --to <client_email> --subject "Welcome to $COMPANY_NAME! Let's Kickoff" --template directives/templates/onboarding.txt`
4. Confirm the email was sent successfully based on the script's stdout.
5. **Add Client to ClickUp CRM:**
   - Use the `mcp_clickup_clickup_create_task` tool.
   - Set `list_id` to `"901218146714"` (This is the Team Space -> CRM -> List).
   - Set `name` to the client's email address (e.g., `<client_email>`).
   - Set `status` to `"intake"`.
6. Confirm to the user that both the email was sent and the ClickUp task was created successfully.

**Outputs:**
- Confirmation that the onboarding email was sent to the client.
- A newly created task in the ClickUp CRM List.

**Edge Cases:**
- **Missing Credentials:** Script will exit if `credentials.json` is empty or invalid.
- **ClickUp API Error:** Inform the user if the MCP tool fails to create the task.
