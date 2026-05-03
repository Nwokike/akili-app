"""AI service — agentic orchestrator with retry, streaming, and modality translation."""

import asyncio
import base64
import json
import random
import re

import httpx

from core.constants import API_GATEWAY, AITaskType
from services.tools import AKILI_TOOLS, get_current_time, read_page, search_web


def get_dynamic_system_prompt(user_name="Student", education_level="unknown") -> str:
    """Injects real-world time and strict anti-hallucination rules dynamically."""
    current_time = get_current_time()
    
    return f"""You are Akili, an expert AI tutor. 

[CONTEXT]
Student: {user_name}
Level: {education_level}
Current System Time: {current_time}

[STRICT TOOL USAGE PROTOCOL]
1. FOR ANY FACTUAL, HISTORICAL, OR CURRICULUM QUESTIONS: You MUST use the `search_web` tool FIRST.
2. ALWAYS include the year and educational level in your search queries (e.g., "History JSS3 curriculum Nigeria 2026").
3. After searching, if the results are summarized or truncated, use the `read_page` tool on the most relevant URLs to "fetch" the full content.
4. DO NOT GUESS OR HALLUCINATE. If tools provide no information, explicitly state: "I'm sorry, but I couldn't find verified syllabus information for this topic. Could you please provide more details or rephrase?"
5. SOURCES: You must cite your sources at the end of every response that used search.

[OUTPUT FORMAT]
- Use beautiful Markdown with bold headings.
- Use LaTeX for math ($...$ for inline, $$...$$ for blocks).
- Keep it encouraging but academically rigorous."""


class AIService:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=120.0)

    async def _post_with_backoff(self, payload: dict) -> dict:
        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                resp = await self._client.post(f"{API_GATEWAY}/chat", json=payload)
                if resp.status_code in [429, 500, 502, 503, 504]:
                    raise httpx.HTTPStatusError("Server Overloaded", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json()

            except (httpx.HTTPStatusError, httpx.RequestError):
                if attempt == max_retries - 1:
                    return {"error": f"Network overloaded after {max_retries} attempts. Please try again."}

                delay = min(30.0, (base_delay ** attempt) + random.uniform(0.5, 2.0))
                print(f"[AI] Network busy. Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

    async def _stream_with_backoff(self, payload: dict):
        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                async with self._client.stream("POST", f"{API_GATEWAY}/chat", json=payload) as response:
                    if response.status_code in [429, 500, 502, 503, 504]:
                        raise httpx.HTTPStatusError("Server Overloaded", request=response.request, response=response)
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                yield delta
                            except json.JSONDecodeError:
                                continue
                    return # Success, exit retry loop

            except (httpx.HTTPStatusError, httpx.RequestError):
                if attempt == max_retries - 1:
                    yield {"error": f"Network overloaded after {max_retries} attempts. Please try again."}
                    return

                delay = min(30.0, (base_delay ** attempt) + random.uniform(0.5, 2.0))
                await asyncio.sleep(delay)



    async def analyze_image(self, media_data: bytes, mime_type: str) -> str:
        b64_image = base64.b64encode(media_data).decode("utf-8")
        payload = {
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": "You are Akili Eye. Transcribe every word, math formula, and describe every diagram in this image in extreme detail."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}
                    }
                ]
            }],
            "task_type": AITaskType.VISION,
            "temperature": 0.2,
            "max_tokens": 2048
        }
        resp = await self._post_with_backoff(payload)
        if "error" in resp:
            raise Exception(resp["error"])
        return resp.get("choices", [{}])[0].get("message", {}).get("content", "[Image analysis failed]")

    async def transcribe_audio(self, media_data: bytes, mime_type: str) -> str:
        b64_audio = base64.b64encode(media_data).decode("utf-8")
        payload = {
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe this audio precisely."},
                    {
                        "type": "input_audio",
                        "input_audio": {"data": b64_audio, "format": mime_type.split("/")[-1]}
                    }
                ]
            }],
            "task_type": AITaskType.AUDIO,
            "temperature": 0.1,
            "max_tokens": 1024
        }
        resp = await self._post_with_backoff(payload)
        if "error" in resp:
            raise Exception(resp["error"])
        return resp.get("choices", [{}])[0].get("message", {}).get("content", "[Audio transcription failed]")




    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str = None, 
        task_type: str = AITaskType.TEXT,
        media: dict = None,
        on_status=None,
    ):

        def _status(msg):
            if on_status:
                on_status(msg)
            print(f"[AI Status] {msg}")

        # 1. Handle Modality Translation FIRST
        if media:
            try:
                last_msg = messages[-1]
                original_text = last_msg.get("content", "").strip()
                
                if media["type"] == "audio":
                    _status("👂 Akili Ear is listening...")
                    transcript = await self.transcribe_audio(media["data"], media["mime"])
                    last_msg["content"] = f"{original_text}\n\n[Voice Note Transcription]: {transcript}".strip()
                    
                elif media["type"] == "image":
                    _status("👁️ Akili Eye is scanning the image...")
                    description = await self.analyze_image(media["data"], media["mime"])
                    last_msg["content"] = f"{original_text}\n\n[Extracted Image Context]: {description}".strip()
            except Exception as e:
                yield f"\n\n⚠️ Failed to process media: {str(e)}"
                return

        # 2. Inject Dynamic System Prompt
        if not system_prompt:
            system_prompt = get_dynamic_system_prompt()

        current_messages = [{"role": "system", "content": system_prompt}] + list(messages)
        
        _status("🧠 Thinking...")

        MAX_TOOL_ITERATIONS = 4
        
        for _iteration in range(MAX_TOOL_ITERATIONS):
            payload = {
                "messages": current_messages,
                "max_tokens": 4096,
                "temperature": 0.6,
                "task_type": task_type,
                "stream": True,  # noqa: E501
                "tools": AKILI_TOOLS,
                "tool_choice": "auto"
            }

            is_tool_call = False
            tool_calls_buffer = {}
            content_yielded = False

            async for delta in self._stream_with_backoff(payload):
                if "error" in delta:
                    yield f"\n\n⚠️ {delta['error']}"
                    return

                if "content" in delta and delta["content"]:
                    if not content_yielded:
                        if not is_tool_call:
                            _status("🧠 Synthesizing...")
                        content_yielded = True
                    yield delta["content"]

                if "tool_calls" in delta:
                    is_tool_call = True
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.get("id"), 
                                "name": tc.get("function", {}).get("name", ""), 
                                "arguments": ""
                            }
                        if "function" in tc and "arguments" in tc["function"]:
                            tool_calls_buffer[idx]["arguments"] += tc["function"]["arguments"]

            if not is_tool_call:
                break 


            assistant_message = {"role": "assistant", "content": None, "tool_calls": []}
            
            for _, tc in tool_calls_buffer.items():
                assistant_message["tool_calls"].append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]}
                })
            current_messages.append(assistant_message)

            for _, tc in tool_calls_buffer.items():
                func_name = tc["name"]
                call_id = tc["id"]
                args_str = tc["arguments"]

                try:
                    args = json.loads(args_str)
                except (json.JSONDecodeError, TypeError):
                    args = {}

                result_content = ""
                

                if func_name == "search_web":
                    query = args.get("query", "")
                    _status(f"🔍 Searching web for: {query}...")
                    res = await search_web(query)
                    result_content = str(res)
                    print(f"[AI] Tool Result (search_web): {len(res)} results received.")
                    
                elif func_name == "read_page":
                    url = args.get("url", "")
                    _status(f"📖 Reading source: {url[:30]}...")
                    res = await read_page(url)
                    result_content = str(res)
                    print(f"[AI] Tool Result (read_page): {len(result_content)} chars received.")
                    
                else:
                    result_content = f"Error: Unknown tool {func_name}"
                    print(f"[AI] ❌ Unknown tool: {func_name}")

                if not result_content or "error" in result_content.lower() or "no results found" in result_content.lower():
                    print("[AI] ⚠️ Tool returned no relevant info. Triggering failsafe.")
                    result_content = "TOOL RESULT: No relevant information found. CRITICAL: You must inform the user you couldn't find verified info."

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": func_name,
                    "content": result_content
                })

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = None,
        task_type: str = AITaskType.TEXT,
        media: dict = None,
        on_status=None,
        **kwargs
    ) -> dict:

        def _status(msg):
            if on_status:
                on_status(msg)
            print(f"[AI Status] {msg}")

        # 1. Handle Modality Translation
        if media:
            try:
                last_msg = messages[-1]
                original_text = last_msg.get("content", "").strip()
                if media["type"] == "audio":
                    _status("👂 Akili Ear is listening...")
                    transcript = await self.transcribe_audio(media["data"], media["mime"])
                    last_msg["content"] = f"{original_text}\n\n[Voice Note Transcription]: {transcript}".strip()
                elif media["type"] == "image":
                    _status("👁️ Akili Eye is scanning...")
                    description = await self.analyze_image(media["data"], media["mime"])
                    last_msg["content"] = f"{original_text}\n\n[Extracted Image Context]: {description}".strip()
            except Exception as e:
                return {"role": "assistant", "content": f"⚠️ Media error: {str(e)}", "_error": True}

        # 2. Inject Dynamic System Prompt
        if not system_prompt:
            system_prompt = get_dynamic_system_prompt()

        current_messages = [{"role": "system", "content": system_prompt}] + list(messages)
        
        if "search_query" in kwargs:
            current_messages.append({"role": "user", "content": f"[Background Research Hint]: {kwargs['search_query']}"})

        _status("🧠 Thinking...")

        MAX_TOOL_ITERATIONS = 4
        final_content = ""
        model_used = "unknown"

        for iteration in range(MAX_TOOL_ITERATIONS):
            payload = {
                "messages": current_messages,  # noqa: E501
                "max_tokens": 4096,
                "temperature": 0.3 if iteration > 0 else 0.6,
                "task_type": task_type,
                "stream": False,
                "tools": AKILI_TOOLS,
                "tool_choice": "auto"
            }

            if iteration > 0:
                await asyncio.sleep(1.5)

            resp = await self._post_with_backoff(payload)
            if "error" in resp:
                return {"role": "assistant", "content": f"⚠️ {resp['error']}", "_error": True}

            choice = resp.get("choices", [{}])[0]
            message = choice.get("message", {})  # noqa: E501
            model_used = resp.get("_model_used", "unknown")
            
            if not message.get("tool_calls"):
                final_content = message.get("content", "")
                break


            current_messages.append(message)
            
            for tc in message.get("tool_calls", []):
                func_name = tc["function"]["name"]
                call_id = tc["id"]
                args_str = tc["function"]["arguments"]
                
                try:
                    args = json.loads(args_str)
                except (json.JSONDecodeError, TypeError):
                    args = {}

                if func_name == "search_web":
                    query = args.get("query", "")
                    _status(f"🔍 Searching: {query}...")
                    res = await search_web(query)
                    result_content = str(res)
                elif func_name == "read_page":
                    url = args.get("url", "")
                    _status(f"📖 Reading: {url[:30]}...")
                    res = await read_page(url)
                    result_content = str(res)
                else:
                    result_content = "Error: Unknown tool"

                if not result_content or "error" in result_content.lower() or "no results" in result_content.lower():
                    result_content = "No relevant info found."

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": func_name,
                    "content": result_content
                })

        return {
            "role": "assistant",
            "content": _strip_thinking(final_content),
            "_model": model_used,
        }

    async def close(self):
        await self._client.aclose()


def _strip_thinking(text: str) -> str:
    if not text:
        return text
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if "<think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1].strip()
        if cleaned.startswith("<think>"):
            cleaned = ""
    cleaned = re.sub(r"<tool_call>.*?</tool_call>", "", cleaned, flags=re.DOTALL).strip()
    return cleaned or text


ai_service = AIService()