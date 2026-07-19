"""
Kimi Web Search Agent
An intelligent search agent based on the Kimi API, capable of understanding user questions, retrieving information via search engines, and summarizing answers.
"""

import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from openai.types.chat.chat_completion import Choice
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _reasoning_safe_temperature(model, requested=1.0):
    """Reasoning models (Kimi K3, GPT-5, ...) only accept temperature=1.
    Return 1 for those; otherwise the requested value so non-reasoning
    providers (Doubao, DeepSeek, older Moonshot) are unchanged."""
    m = str(model or "").lower().replace("/", "-")
    return 1 if ("kimi-k3" in m or "gpt-5" in m) else requested


# Step types and display labels for ReAct trajectory (Thought → Action → Observation → Final Answer)
STEP_LABELS = {
    "thought": ("💭", "Thought"),
    "action": ("🔧", "Action"),
    "observation": ("👀", "Observation"),
    "answer": ("✅", "Final Answer"),
}


def format_trace_step(step: Dict[str, Any], max_len: int = 500) -> str:
    """Render a ReAct trajectory step into a single line of readable text.

    This is exactly the "trajectory" emphasized in this chapter—user messages, model thoughts, tool calls,
    and tool results are clearly separated, making the ReAct loop of "Think→Do→See" clear at a glance.
    """
    icon, label = STEP_LABELS.get(step["type"], ("•", step["type"]))
    prefix = f"{icon} [{step.get('iteration', '-')}] {label}"

    if step["type"] == "action":
        args = json.dumps(step.get("args", {}), ensure_ascii=False)
        return f"{prefix}: Call tool {step.get('tool')}   Parameters={args}"

    content = str(step.get("content", "")).strip()
    if len(content) > max_len:
        content = content[:max_len] + f"… (omitted {len(content) - max_len} characters)"
    return f"{prefix}: {content}"


def search_impl(arguments: Dict[str, Any]) -> Any:
    """
    When using the search tool provided by Moonshot AI, you just need to return the arguments as they are,
    without any additional processing logic.
 
    But if you want to use other models and keep the internet search functionality, you just need to modify 
    the implementation here (for example, calling search and fetching web page content), the function signature 
    remains the same and still works.
 
    This ensures maximum compatibility, allowing you to switch between different models without making 
    destructive changes to the code.
    """
    return arguments


class WebSearchAgent:
    """
    Web Search Agent - Using Kimi API's built-in search tool
    
    According to official documentation: https://platform.moonshot.ai/docs/guide/use-web-search
    Kimi provides the built-in $web_search tool
    """
    
    def __init__(self, api_key: str = None, base_url: str = "https://api.moonshot.cn/v1",
                 model: str = "kimi-k3", verbose: bool = False):
        """
        Initialize Agent

        Args:
            api_key: Kimi API key (if not provided, get from environment variable)
            base_url: API base URL
            model: Model name to use (default kimi-k3)
            verbose: Whether to print ReAct trajectory in real time (Thought/Action/Observation)
        """
        # Prefer the passed api_key, otherwise get from environment variable
        # Moonshot as primary, OpenRouter as general fallback (enabled when MOONSHOT_API_KEY is missing)
        from config import resolve_llm_backend
        primary_key = api_key or os.environ.get("MOONSHOT_API_KEY") or os.environ.get("KIMI_API_KEY")
        resolved_key, resolved_base_url, model, self.using_openrouter = \
            resolve_llm_backend(primary_key, base_url, model)
        if self.using_openrouter:
            logger.info(
                f"MOONSHOT_API_KEY not set, falling back to OpenRouter (model: {model}）。"
                "Note: Moonshot's built-in $web_search tool is not available on OpenRouter,"
                "in this mode the model will answer based solely on its own knowledge, without real-time web search."
            )

        self.client = OpenAI(
            api_key=resolved_key,
            base_url=resolved_base_url
        )
        self.model = model
        self.verbose = verbose
        self.conversation_history = []
        # ReAct trajectory: record each step's Thought/Action/Observation in order for display and debugging
        self.trace: List[Dict[str, Any]] = []
        self.temperature = 0.6
        # Reasoning model (Kimi K3) needs sufficient output budget to avoid truncation of final answer
        self.max_tokens = 4096

    def _emit(self, step: Dict[str, Any]):
        """Record a ReAct trajectory step and print it in real time when verbose mode is on."""
        self.trace.append(step)
        if self.verbose:
            print(format_trace_step(step))
        
    def _get_tools(self) -> List[Dict[str, Any]]:
        """
        Define available tools
        According to Kimi documentation, $web_search is a built-in tool (only supported by Moonshot).
        When falling back via OpenRouter, this built-in tool is unavailable; return an empty list to avoid 400 errors,
        and the model will answer based solely on its own knowledge.
        """
        if getattr(self, "using_openrouter", False):
            return []
        return [
            {
                "type": "builtin_function",
                "function": {
                    "name": "$web_search",
                }
            }
        ]
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt
        """
        return f"""You are Kimi, an intelligent search assistant.

Please follow these steps:
1. Analyze the user's question and identify key information needs
2. Use the $web_search tool to search for relevant information
3. If more information is needed, you can call the search tool multiple times
4. Synthesize all information to generate an accurate and comprehensive answer

Note:
- Use precise keywords when searching
- Prioritize the latest and most authoritative information
- The answer should be well-structured and evidence-based
"""
    
    def _chat(self, messages: List[Dict[str, Any]]) -> Choice:
        """
        Call Kimi API for conversation
        
        Args:
            messages: List of messages
            
        Returns:
            API response Choice object
        """
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=_reasoning_safe_temperature(self.model, self.temperature),
            # Kimi K3 is a reasoning model that first produces a long reasoning_content; the final answer needs
            # sufficient output budget (Moonshot requires max_tokens>=2048), otherwise the answer may be truncated to empty.
            max_tokens=self.max_tokens,
        )
        tools = self._get_tools()
        if tools:  # When falling back via OpenRouter, there is no built-in search tool; omit the tools parameter
            kwargs["tools"] = tools
        completion = self.client.chat.completions.create(**kwargs)
        return completion.choices[0]

    def search_and_answer(self, user_question: str, max_iterations: int = 5) -> str:
        """
        Execute search and generate answer
        
        Args:
            user_question: User question
            max_iterations: Maximum search iterations (to prevent infinite loops)
            
        Returns:
            Final answer
        """
        #  Build system prompt
        system_prompt = self._get_system_prompt()
        
        #  Reset conversation history and add new system prompt
        self.conversation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ]
        #  Reset ReAct trajectory
        self.trace = []
        logger.info("Start calling Kimi search tool...")

        try:
            finish_reason = None
            iteration = 0
            
            #  Loop until final answer is obtained or max iterations reached
            while (finish_reason is None or finish_reason == "tool_calls") and iteration < max_iterations:
                iteration += 1
                logger.info(f"Iteration {iteration}/{max_iterations}")
                
                #  Call Kimi API
                choice = self._chat(self.conversation_history)
                finish_reason = choice.finish_reason
                
                #  Capture model's thinking process (reasoning models like Kimi K3 expose thinking mode via reasoning_content)
                reasoning = getattr(choice.message, "reasoning_content", None)
                if reasoning:
                    self._emit({"iteration": iteration, "type": "thought", "content": reasoning})

                if finish_reason == "tool_calls":
                    #  Handle tool calls
                    logger.info(f"Model requests to call {len(choice.message.tool_calls)}  tools")

                    #  Add assistant message (including tool calls) to history.
                    #  Note: The message must be reconstructed as a plain dict, not directly using the SDK-returned
                    #  pydantic message object — the latter carries extra fields like reasoning_content / refusal
                    #  which, when sent back to Moonshot, trigger a "tokenization failed" 400 error.
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": choice.message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in choice.message.tool_calls
                        ],
                    })

                    #  Execute each tool call
                    for tool_call in choice.message.tool_calls:
                        tool_call_name = tool_call.function.name
                        tool_call_arguments = json.loads(tool_call.function.arguments)

                        logger.info(f"Execute tool: {tool_call_name}, parameters: {tool_call_arguments}")
                        #  Action: record a tool call
                        self._emit({"iteration": iteration, "type": "action",
                                    "tool": tool_call_name, "args": tool_call_arguments})

                        if tool_call_name == "$web_search":
                            #  Call search implementation
                            tool_result = search_impl(tool_call_arguments)
                        else:
                            tool_result = f"Error: unable to find tool by name '{tool_call_name}'"

                        tool_content = json.dumps(tool_result, ensure_ascii=False)
                        #  Observation: record tool return result
                        self._emit({"iteration": iteration, "type": "observation",
                                    "tool": tool_call_name, "content": tool_content})
                        #  Build tool response message and add to history
                        self.conversation_history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call_name,
                            "content": tool_content
                        })
                else:
                    #  Obtain final answer
                    if choice.message.content:
                        answer = choice.message.content
                        logger.info("Successfully generated answer")
                        self._emit({"iteration": iteration, "type": "answer", "content": answer})

                        #  Add final answer to history
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": answer
                        })

                        return answer
            
            #  If max iterations reached without completion
            if iteration >= max_iterations:
                logger.warning(f"Reached max iterations {max_iterations}")
                return "Sorry, the search process exceeded the maximum number of iterations. Please try again later."
            
            return "Sorry, I cannot obtain enough information to answer your question."
                
        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return f"Error during search: {str(e)}"
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get conversation history"""
        return self.conversation_history

    def get_trace(self) -> List[Dict[str, Any]]:
        """Get the ReAct trace (Thought/Action/Observation/Final Answer) of the last search_and_answer"""
        return self.trace
    
    def set_temperature(self, temperature: float):
        """
        Set temperature parameter
        
        Args:
            temperature: Temperature value (0.0 - 2.0)
        """
        if 0.0 <= temperature <= 2.0:
            self.temperature = temperature
            logger.info(f"Temperature set to: {temperature}")
        else:
            logger.warning(f"Invalid temperature value: {temperature}, should be between 0.0 and 2.0")


def run_offline_demo(question: str = "What is Moonshot AI's Context Caching technology?",
                     verbose: bool = True) -> Dict[str, Any]:
    """Offline demonstration of the ReAct loop — no API key or internet required.

    This function **does not call real search** but replays a "sample trace" to visually show the
    “Think→Act→Observe→Think→Act→Observe” loop described in this chapter: the model first thinks, then calls the $web_search action, observes the result,
    continues thinking, and finally synthesizes an answer. The trace content is only a teaching example and does not represent real search results.

    Returns:
        A dictionary containing question / trace / answer.
    """
    trace: List[Dict[str, Any]] = [
        {"iteration": 1, "type": "thought",
         "content": "The user wants to know about Context Caching. This is a Moonshot feature. I need to search for official documentation first to confirm its definition and purpose."},
        {"iteration": 1, "type": "action", "tool": "$web_search",
         "args": {"query": "What is Moonshot AI Context Caching"}},
        {"iteration": 1, "type": "observation", "tool": "$web_search",
         "content": "(Sample result) Context Caching is a context caching mechanism: it caches repeated prefixes"
                    "(such as long system prompts, documents) on the server side, and subsequent requests that hit the cache can reuse them,"
                    "thereby reducing redundant computation and costs."},
        {"iteration": 2, "type": "thought",
         "content": "The general definition is known, but use cases are still missing. Search again for its typical applications to answer more comprehensively."},
        {"iteration": 2, "type": "action", "tool": "$web_search",
         "args": {"query": "Context Caching use cases billing"}},
        {"iteration": 2, "type": "observation", "tool": "$web_search",
         "content": "(Sample result) Commonly seen in multi-turn conversations, repeated Q&A on long documents, fixed system prompts, etc.;"
                    "tokens that hit the cache are usually billed at a lower price and can significantly reduce time-to-first-token latency."},
        {"iteration": 3, "type": "answer",
         "content": "Context Caching is a mechanism provided by Moonshot AI: it caches repeated"
                    "context prefixes on the server side, and subsequent requests reuse the cached content, thereby reducing redundant computation, lowering costs,"
                    "and speeding up responses. It is especially suitable for scenarios like long system prompts, repeated Q&A on long documents, and multi-turn conversations."
                    "(This paragraph is from an offline sample trace, not real search results.)"},
    ]

    if verbose:
        for step in trace:
            print(format_trace_step(step))

    answer = next(s["content"] for s in trace if s["type"] == "answer")
    return {"question": question, "trace": trace, "answer": answer}


# Standalone example
def main():
    """
    Standalone example demonstrating basic usage
    """
    # Set API key (ensure environment variable MOONSHOT_API_KEY is set)
    agent = WebSearchAgent()
    
    # Example question
    test_question = "Please search for Moonshot AI Context Caching technology and tell me what it is."
    
    print(f"Question: {test_question}")
    print("-" * 60)
    print("Searching...")
    
    # Get answer
    answer = agent.search_and_answer(test_question)
    
    print("\nAnswer:")
    print("-" * 60)
    print(answer)


if __name__ == '__main__':
    main()