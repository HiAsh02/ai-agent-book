import asyncio
import logging
import os
import sys
import traceback
from typing import Union

from browser_use import Agent, BrowserSession
from browser_use.llm import ChatOpenAI
from dotenv import load_dotenv
from fastmcp.server.server import FastMCP
from mcp.types import TextContent
from pydantic import Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

mcp = FastMCP("browseruse-server")

extended_browser_system_prompt = """

# Efficiency Guide
0. If the user query contains a clear URL, access it directly
1. Use specific search queries containing key terms of the task
2. Avoid being distracted by irrelevant information
3. If blocked by a paywall, try using archive.org or similar alternatives
4. Record each important finding clearly and concisely
5. Precisely extract necessary information with minimal browsing steps.

## Output Rules
1. If the task requires finding relevant content, return a summary of the relevant content
2. If the task requires querying related downloads, try to find downloadable links and return them (e.g., downloadable links on GitHub are typically: https://raw.githubusercontent.com/; for Hugging Face, find the raw tag address on the corresponding file page). The download link should be the most matching address based on the task. Example:
Example 1:
```json
{
  "url": "https://"
}
```
"""


@mcp.tool(
    description="""Use browser to visit a web page, extract content,
    and optionally download files/images, ...

    Returns a dict with execution trace, answer (extracted content),
    and downloaded file/image paths."""
)
async def complete_browser_task(
    task: str = Field(
        ...,
        description=(
            "Task-related description"
        ),
    )
)-> Union[str, TextContent]:
    browser_session = BrowserSession(
        # headless=True,  # Key parameter: set to True to enable headless mode
        headless=False,  # Key parameter: set to True to enable headless mode
    )
    try:
        load_dotenv()
        model = os.environ['LLM_MODEL_NAME']
        base_url = os.environ['LLM_BASE_URL']
        api_key = os.environ['LLM_API_KEY']
        if not model or not base_url or not api_key:
            logging.warning(f"Query failed: LLM_MODEL_NAME, LLM_BASE_URL, LLM_API_KEY parameters incomplete")
            return None
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=float(0.1),
        )
        agent = Agent(
            task=task,
            llm=llm,
            extend_system_message=extended_browser_system_prompt,
            browser_session=browser_session
        )
        final_result = ""
        result = await agent.run()
        logging.info(f"complete_browser_task result: {result}")
        if result and result.history[-1] and result.history[-1].result and result.history[-1].result[0]:
            final_result = result.history[-1].result[0].extracted_content

        return final_result
    except BaseException as e:
        logging.warning(f"complete_browser_task error: {e}")
        return None
    except Exception:
        logging.warning(f"complete_browser_task error: {traceback.format_exc()}")
        return None


if __name__ == "__main__":
    load_dotenv(override=True)
    logging.info("Starting browseruse-server MCP server!")
    mcp.run(transport="stdio")

