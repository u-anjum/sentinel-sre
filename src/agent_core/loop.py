import asyncio
import json
import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_core.prompts import SYSTEM_PROMPT
from agent_core.sandbox import DiagnosticSandbox
from agent_core.schemas import IncidentReport

load_dotenv()

READ_ONLY_MCP_TOOLS = {"inspect_db_health", "fetch_logs_to_sandbox"}


def _build_tool_declarations(mcp_tools) -> list[types.Tool]:
    declarations: list[types.FunctionDeclaration] = []

    for tool in mcp_tools:
        if tool.name not in READ_ONLY_MCP_TOOLS:
            continue
        declarations.append(
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or "",
                parameters_json_schema=tool.input_schema,
            )
        )

    declarations.append(
        types.FunctionDeclaration(
            name="run_diagnostic_python",
            description="Run Python code inside the isolated E2B sandbox to analyze /home/user/logs.jsonl.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python script to execute in the sandbox."}
                },
                "required": ["code"],
            },
        )
    )

    return [types.Tool(function_declarations=declarations)]


async def run_triage(alert_payload: dict, max_steps: int = 10) -> IncidentReport:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    sandbox = DiagnosticSandbox()

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["src/mcp_servers/telemetry_server/server.py"],
        env=os.environ.copy(),
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_resp = await session.list_tools()
                gemini_tools = _build_tool_declarations(tools_resp.tools)

                initial_msg = (
                    f"INCOMING ALERT:\n{json.dumps(alert_payload, indent=2)}\n\n"
                    f"ACTIVE SANDBOX ID: {sandbox.sandbox_id}"
                )
                contents: list[types.Content] = [
                    types.Content(role="user", parts=[types.Part.from_text(text=initial_msg)])
                ]

                logs_fetched = False

                for step in range(1, max_steps + 1):
                    print(f"[LOOP] Step {step}/{max_steps} -> querying Gemini...")
                    response = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            tools=gemini_tools,
                            temperature=0.1,
                        ),
                    )

                    candidate_content = response.candidates[0].content
                    contents.append(candidate_content)

                    if not response.function_calls:
                        print("[LOOP] Diagnosis complete. Enforcing structured IncidentReport schema...")
                        final_resp = client.models.generate_content(
                            model="gemini-3.8-flash",
                            contents=contents + [
                                types.Content(
                                    role="user",
                                    parts=[types.Part.from_text(text="Emit the final IncidentReport JSON.")],
                                )
                            ],
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=IncidentReport,
                                temperature=0.0,
                            ),
                        )
                        return IncidentReport.model_validate_json(final_resp.text)

                    tool_response_parts: list[types.Part] = []
                    for call in response.function_calls:
                        args = dict(call.args) if call.args else {}
                        print(f"  [TOOL] {call.name}({args})")

                        if call.name == "run_diagnostic_python" and not logs_fetched:
                            result = {
                                "error": "No logs loaded in sandbox yet. Call fetch_logs_to_sandbox(sandbox_id=...) first."
                            }
                        elif call.name == "run_diagnostic_python":
                            result = sandbox.run_python(args["code"])
                        elif call.name in READ_ONLY_MCP_TOOLS:
                            mcp_result = await session.call_tool(call.name, arguments=args)
                            if call.name == "fetch_logs_to_sandbox":
                                logs_fetched = True
                            result = {"output": [c.text for c in mcp_result.content if hasattr(c, "text")]}
                        else:
                            result = {"error": f"Tool '{call.name}' is blocked during read-only triage."}

                        print(f"    -> {str(result)[:250]}")
                        tool_response_parts.append(
                            types.Part.from_function_response(name=call.name, response=result)
                        )

                    contents.append(types.Content(role="user", parts=tool_response_parts))

                raise RuntimeError(f"Agent exceeded max_steps={max_steps} without producing a diagnosis.")
    finally:
        sandbox.close()


if __name__ == "__main__":
    sample_alert = {
        "alert_name": "HighOrderFailureRate",
        "service": "target-api",
        "symptom": "POST /orders returning 500 errors and lock timeout exceptions",
    }
    report = asyncio.run(run_triage(sample_alert))
    print("\n=== FINAL STRUCTURED REPORT ===")
    print(report.model_dump_json(indent=2))