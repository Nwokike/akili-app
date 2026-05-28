"""AI service — agentic orchestrator with retry, streaming, and modality translation."""

import asyncio
import base64
import json
import logging
import random
import re

import httpx

from core.constants import API_GATEWAY, AITaskType, GATEWAY_SECRET, USER_AGENT
from core.state import state
from services.tools import AKILI_TOOLS, get_current_time, read_page, search_web

logger = logging.getLogger(__name__)

# Auth headers required by kiri-gateway security gate
COMMON_HEADERS = {
    "Authorization": f"Bearer {GATEWAY_SECRET}",
    "User-Agent": USER_AGENT,
}


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
        logger.info("Initializing AIService...")
        self._client = httpx.AsyncClient(
            headers=COMMON_HEADERS,
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30,
            ),
        )

    async def _post_with_backoff(self, payload: dict) -> dict:
        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                resp = await self._client.post(f"{API_GATEWAY}/chat", json=payload)
                if resp.status_code != 200:
                    try:
                        error_detail = resp.json()
                        logger.warning("AI Error (Attempt %d): %s", attempt + 1, json.dumps(error_detail))
                    except Exception:
                        logger.warning("AI Error Raw (Attempt %d): %s", attempt + 1, resp.text[:300])
                    resp.raise_for_status()

                return resp.json()

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning("AI Attempt %d Failed: %s", attempt + 1, e)
                if attempt == max_retries - 1:
                    return {"error": f"Network overloaded after {max_retries} attempts. {str(e)}"}

                delay = min(30.0, (base_delay**attempt) + random.uniform(0.5, 2.0))
                logger.info("Retrying in %.1fs...", delay)
                await asyncio.sleep(delay)

    async def _stream_with_backoff(self, payload: dict):
        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries):
            print(f"\n[DEBUG] Requesting {API_GATEWAY}/chat (Attempt {attempt + 1})", flush=True)
            try:
                async with self._client.stream("POST", f"{API_GATEWAY}/chat", json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        try:
                            error_detail = json.loads(body)
                            print(
                                f"\n[AI Stream Error Detail - Attempt {attempt + 1}] {json.dumps(error_detail, indent=2)}",
                                flush=True,
                            )
                        except Exception:
                            print(f"\n[AI Stream Error Raw - Attempt {attempt + 1}] {body.decode()}", flush=True)

                        await asyncio.sleep(0.5)
                        response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})

                                # YIELD BOTH CONTENT AND REASONING
                                yield {
                                    "content": delta.get("content", ""),
                                    "reasoning": delta.get("reasoning_content", ""),
                                }
                            except json.JSONDecodeError:
                                continue
                    return  # Success, exit retry loop

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                print(f"[AI Stream Attempt {attempt + 1} Failed] {str(e)}", flush=True)
                if attempt == max_retries - 1:
                    yield {"error": f"Network overloaded. {str(e)}"}
                    return

                delay = min(30.0, (base_delay**attempt) + random.uniform(0.5, 2.0))
                await asyncio.sleep(delay)

    async def analyze_image(self, media_data: bytes, mime_type: str) -> str:
        b64_image = base64.b64encode(media_data).decode("utf-8")
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "You are Akili Eye. Transcribe every word, math formula, and describe every diagram in this image in extreme detail.",
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
                    ],
                }
            ],
            "task_type": AITaskType.VISION,
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        resp = await self._post_with_backoff(payload)
        if "error" in resp:
            raise Exception(resp["error"])
        return resp.get("choices", [{}])[0].get("message", {}).get("content", "[Image analysis failed]")

    async def transcribe_audio(self, media_data: bytes, mime_type: str) -> str:
        """Send audio to Whisper via gateway for transcription."""
        files = {"file": ("audio.wav", media_data, mime_type)}
        data = {
            "task_type": AITaskType.AUDIO,
            "temperature": "0.1",
        }

        try:
            resp = await self._client.post(
                f"{API_GATEWAY}/chat",
                files=files,
                data=data,
                headers=COMMON_HEADERS,
                timeout=30.0,
            )

            if resp.status_code != 200:
                logger.error("Whisper HTTP %d: %s", resp.status_code, resp.text[:200])
                resp.raise_for_status()

            data_resp = resp.json()

            # Whisper returns {"text": "..."}, chat completions return choices[]
            transcript = data_resp.get("text", "")
            if not transcript:
                transcript = (
                    data_resp.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

            if transcript:
                logger.info("Transcribed %d bytes audio → '%s'", len(media_data), transcript[:80])
                return transcript

            return "[Transcription returned empty result]"

        except Exception as e:
            logger.error("Audio transcription failed: %s", e)
            return f"[Transcription failed: {e}]"

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

        # 2. Inject Dynamic System Prompt (MERGED WITH CUSTOM)
        base_prompt = get_dynamic_system_prompt(user_name=state.user_name or "Student", education_level=state.education_level or "Grade 10")
        full_system_prompt = f"{base_prompt}\n\n[TASK INSTRUCTIONS]:\n{system_prompt}" if system_prompt else base_prompt

        print(f"[AI] Injecting Student Context (User: {state.user_name}, Level: {state.education_level})", flush=True)

        current_messages = [{"role": "system", "content": full_system_prompt}] + list(messages)

        _status("🧠 Thinking...")
        print("\n[AI] >>> Starting Agentic Loop (Streaming)", flush=True)

        MAX_TOOL_ITERATIONS = 25

        for iteration in range(MAX_TOOL_ITERATIONS):
            print(f"[AI] Iteration {iteration + 1}/{MAX_TOOL_ITERATIONS}...", flush=True)
            payload = {
                "messages": current_messages,
                "max_tokens": 4096,
                "temperature": 0.6,
                "task_type": task_type,
                "stream": True,
                "tools": AKILI_TOOLS,
                "tool_choice": "auto",
            }

            is_tool_call = False
            tool_calls_buffer = {}
            content_yielded = False

            async for delta in self._stream_with_backoff(payload):
                if "error" in delta:
                    yield f"\n\n⚠️ {delta['error']}"
                    return

                # Display reasoning in real-time
                if delta.get("reasoning"):
                    yield f"💭 *{delta['reasoning']}*"

                if delta.get("content") and delta["content"]:
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
                                "arguments": "",
                            }
                        if "function" in tc and "arguments" in tc["function"]:
                            tool_calls_buffer[idx]["arguments"] += tc["function"]["arguments"]

            if not is_tool_call:
                print("[AI] <<< Loop Finished (No more tools requested).", flush=True)
                break

            # Process Tool Calls
            assistant_message = {"role": "assistant", "content": None, "tool_calls": []}

            for _, tc in tool_calls_buffer.items():
                print(f"[AI Tool Call] {tc['name']}({tc['arguments']})", flush=True)
                assistant_message["tool_calls"].append({"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}})
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
                    _status(f"🔍 Searching: {query}...")
                    res = await search_web(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_web: {len(res)} items. Snippet: {result_content[:150]}...", flush=True)

                elif func_name == "read_page":
                    url = args.get("url", "")
                    _status(f"📖 Reading: {url[:30]}...")
                    res = await read_page(url)
                    result_content = str(res)
                    print(
                        f"[AI Tool Result] read_page: {len(result_content)} chars. Snippet: {result_content[:300]}...",
                        flush=True,
                    )

                else:
                    result_content = f"Error: Unknown tool {func_name}"

                current_messages.append({"role": "tool", "tool_call_id": call_id, "name": func_name, "content": result_content})
        else:
            print("[AI Warning] Loop reached MAX_TOOL_ITERATIONS. Stopping research.", flush=True)
            yield "\n\n⚠️ Research limit reached. The answer may be incomplete."

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = None,
        task_type: str = AITaskType.TEXT,
        media: dict = None,
        use_tools: bool = True,
        on_status=None,
        **kwargs,
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

        # 2. Inject Dynamic System Prompt (MERGED WITH CUSTOM)
        base_prompt = get_dynamic_system_prompt(user_name=state.user_name or "Student", education_level=state.education_level or "Grade 10")
        full_system_prompt = f"{base_prompt}\n\n[TASK INSTRUCTIONS]:\n{system_prompt}" if system_prompt else base_prompt

        print(f"[AI] Injecting Student Context (User: {state.user_name}, Level: {state.education_level})", flush=True)

        current_messages = [{"role": "system", "content": full_system_prompt}] + list(messages)

        if "search_query" in kwargs:
            current_messages.append({"role": "user", "content": f"[Background Research Hint]: {kwargs['search_query']}"})

        _status("🧠 Thinking...")
        print("\n[AI] >>> Starting Agentic Loop (Deep Research Mode)", flush=True)

        MAX_TOOL_ITERATIONS = 25
        final_content = ""
        model_used = "unknown"

        search_count = 0
        read_count = 0

        for iteration in range(MAX_TOOL_ITERATIONS):
            print(f"[AI] Iteration {iteration + 1}/{MAX_TOOL_ITERATIONS}...", flush=True)

            # FAILSAFE: If searching too much without reading, force a read.
            if search_count >= 5 and read_count == 0:
                print("[AI Failsafe] Too many searches. Forcing a 'READ' hint.", flush=True)
                current_messages.append(
                    {
                        "role": "user",
                        "content": "CRITICAL: You are stuck in a search loop. The snippets are insufficient. You MUST use 'read_page' on a relevant URL now to get the full curriculum.",
                    }
                )
                search_count = 0  # Reset failsafe

            payload = {
                "messages": current_messages,
                "max_tokens": 4096,
                "temperature": 0.3 if iteration > 0 else 0.6,
                "task_type": task_type,
                "stream": False,
            }
            if use_tools:
                payload["tools"] = AKILI_TOOLS
                payload["tool_choice"] = "auto"

            if iteration > 0:
                await asyncio.sleep(1.0)

            resp = await self._post_with_backoff(payload)
            if "error" in resp:
                return {"role": "assistant", "content": f"⚠️ {resp['error']}", "_error": True}

            choice = resp.get("choices", [{}])[0]
            message = choice.get("message", {})
            model_used = resp.get("_model_used", "unknown")

            if not message.get("tool_calls"):
                print("[AI] <<< Loop Finished (Final Answer Generated).", flush=True)
                reasoning = message.get("reasoning_content", "")
                content = message.get("content", "")

                final_content = f"💭 *{reasoning}*\n\n{content}" if reasoning else content

                print(f"\n[AI RAW CONTENT] {final_content[:500]}...", flush=True)
                break

            # Handle Tool Calls
            current_messages.append(message)

            for tc in message.get("tool_calls", []):
                func_name = tc["function"]["name"]
                call_id = tc["id"]
                args_str = tc["function"]["arguments"]

                print(f"[AI Tool Call] {func_name}({args_str})", flush=True)

                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {}

                if func_name == "search_web":
                    search_count += 1
                    query = args.get("query", "")
                    _status(f"🔍 Searching: {query}...")
                    res = await search_web(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_web: {len(res)} items. Snippet: {result_content[:150]}...", flush=True)
                elif func_name == "read_page":
                    read_count += 1
                    url = args.get("url", "")
                    _status(f"📖 Reading: {url[:30]}...")
                    res = await read_page(url)
                    result_content = str(res)
                    print(
                        f"[AI Tool Result] read_page: {len(result_content)} chars. Snippet: {result_content[:300]}...",
                        flush=True,
                    )
                else:
                    result_content = "Error: Unknown tool"

                current_messages.append({"role": "tool", "tool_call_id": call_id, "name": func_name, "content": result_content})
        else:
            print("[AI Warning] Loop reached MAX_TOOL_ITERATIONS.", flush=True)
            final_content = "⚠️ Research limit reached. Result may be incomplete."

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
