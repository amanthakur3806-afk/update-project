# Video Processing MCP Server

This file contains a production-ready Python example implementing an MCP server with background tasks using **FastMCP**. It registers the native `TasksExtension` and uses a guard pattern to handle multi-round-trip data collection (`input_required` state) securely.

## 1. Installation

Install FastMCP with the native tasks dependencies:

```bash
pip install "fastmcp[tasks]"
```

## 2. Server Implementation Code

Save the following code as `server.py`:

```python
import asyncio
from fastmcp import FastMCP
from fastmcp_tasks import TasksExtension
from fastmcp.shared.results import InputRequiredResult

# Initialize FastMCP Server
mcp = FastMCP("VideoProcessingServer")

# Register the standard protocol tasks extension
mcp.add_extension(TasksExtension())

@mcp.tool(task=True)
async def render_video(video_id: str, quality: str = "1080p", confirm: bool = False) -> str:
    """
    Simulates a long-running video rendering job.
    Demonstrates working state and mid-flight input requirements.
    """
    # 1. Check for mid-flight confirmation (Guard Pattern)
    if not confirm:
        # Pauses the task and transitions status to 'input_required'
        return InputRequiredResult(
            message=f"Rendering {video_id} in {quality} can take up to 5 minutes. Proceed?",
            fields={"confirm": "boolean"}
        )

    # 2. Simulate heavy async background processing ('working' state)
    print(f"Starting render for {video_id}...")
    for percent in range(0, 101, 25):
        await asyncio.sleep(2)  # Simulating long rendering iterations
        print(f"Task progress: {percent}% complete")

    # 3. Terminal State ('completed')
    return f"Successfully rendered video {video_id} in {quality}!"

if __name__ == "__main__":
    # Run server via Standard I/O transport channel
    mcp.run(transport="stdio")
```

## 3. Protocol Architecture

* **Durable Task Handle:** When an AI client triggers `render_video`, the server doesn't freeze the connection. It sends back an immediate JSON-RPC task ID.
* **`input_required` Phase:** Because `confirm` is initially false, the task transitions to `input_required`. The client polls via `tasks/get`, sees the prompt, collects your confirmation, and submits it back using `tasks/update`.
* **`working` & `completed` Phase:** Once confirmed, the background task resumes processing in a separate runtime loop (`working`) before writing out the terminal message (`completed`).
