"""AI service — agentic orchestrator with retry, streaming, and modality translation."""

import asyncio
import base64
import json
import logging
import random
import re

import httpx

from core.constants import API_GATEWAY, GATEWAY_SECRET, USER_AGENT, AITaskType
from core.state import state
from services.tools import (
    AKILI_TOOLS,
    get_current_time,
    read_page,
    search_books,
    search_images,
    search_news,
    search_videos,
    search_web,
)

logger = logging.getLogger(__name__)

# Auth headers required by kiri-gateway security gate
COMMON_HEADERS = {
    "Authorization": f"Bearer {GATEWAY_SECRET}",
    "User-Agent": USER_AGENT,
}


def get_dynamic_system_prompt(user_name="Student", education_level="unknown") -> str:
    """Injects real-world time and strict anti-hallucination rules dynamically."""
    current_time = get_current_time()
    from datetime import datetime

    year = datetime.now().year

    return f"""You are Akili, an expert AI tutor.

⚠️ TODAY'S DATE: {current_time}
⚠️ CURRENT YEAR: {year}

[CONTEXT]
Student: {user_name}
Level: {education_level}

[STRICT TOOL USAGE PROTOCOL]
1. FOR ANY FACTUAL, HISTORICAL, OR CURRICULUM QUESTIONS: You MUST use the `search_web` tool FIRST.
2. ALWAYS include the current year ({year}) and educational level in your search queries (e.g., "History JSS3 curriculum Nigeria {year}").
3. After searching, if the results are summarized or truncated, use the `read_page` tool on the most relevant URLs to "fetch" the full content.
4. DO NOT GUESS OR HALLUCINATE. If tools provide no information, explicitly state: "I'm sorry, but I couldn't find verified syllabus information for this topic. Could you please provide more details or rephrase?"
5. SOURCES: You must cite your sources at the end of every response that used search.
6. NEVER use outdated years in search queries. The current year is {year}.

[OUTPUT FORMAT]
- Use beautiful Markdown with bold headings.
- FORMULA RENDERING: Do NOT use LaTeX syntax (like $, $$, \\frac, \\sqrt, etc.) for scientific/mathematical equations.
  Instead, format all equations and formulas using standard Unicode characters, bold/italic text, and sub/superscripts
  (e.g., use 'H₂O', 'x²', '±', '√', 'π', and italics for variables) so they render beautifully and natively in standard markdown.
- Keep it encouraging but academically rigorous."""


class AIService:
    def __init__(self):
        logger.info("Initializing AIService...")

    async def _post_with_backoff(self, payload: dict) -> dict:
        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(
                    headers=COMMON_HEADERS,
                    timeout=httpx.Timeout(120.0, connect=10.0),
                ) as client:
                    resp = await client.post(f"{API_GATEWAY}/chat", json=payload)
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
                async with (
                    httpx.AsyncClient(
                        headers=COMMON_HEADERS,
                        timeout=httpx.Timeout(120.0, connect=10.0),
                    ) as client,
                    client.stream("POST", f"{API_GATEWAY}/chat", json=payload) as response,
                ):
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

                    line_count = 0
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)

                                # Detect stream-level errors (rate limit, etc.)
                                if "error" in chunk:
                                    error_msg = chunk["error"]
                                    if isinstance(error_msg, dict):
                                        error_msg = error_msg.get("message", str(error_msg))
                                    print(f"[AI Stream Error] {error_msg}", flush=True)
                                    yield {"error": str(error_msg)}
                                    return

                                choice = chunk.get("choices", [{}])[0]
                                delta = choice.get("delta", {})
                                finish_reason = choice.get("finish_reason")

                                if finish_reason and finish_reason != "stop":
                                    print(f"[AI Stream] finish_reason={finish_reason}", flush=True)

                                # YIELD CONTENT, REASONING, AND TOOL CALLS
                                result = {
                                    "content": delta.get("content") or "",
                                    "reasoning": delta.get("reasoning_content") or "",
                                }
                                if "tool_calls" in delta:
                                    result["tool_calls"] = delta["tool_calls"]
                                yield result
                                line_count += 1
                            except json.JSONDecodeError:
                                continue

                    if line_count == 0:
                        print("[AI Stream Warning] Stream returned 0 data chunks", flush=True)
                    return  # Success, exit retry loop

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                print(f"[AI Stream Attempt {attempt + 1} Failed] {str(e)}", flush=True)
                if attempt == max_retries - 1:
                    yield {"error": f"Network overloaded. {str(e)}"}
                    return

                delay = min(30.0, (base_delay**attempt) + random.uniform(0.5, 2.0))
                await asyncio.sleep(delay)

    async def analyze_image(self, media_data: bytes, mime_type: str) -> str:
        """Meticulous image analysis — captures every detail for accurate evaluation."""
        b64_image = base64.b64encode(media_data).decode("utf-8")
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "You are Akili Eye — a meticulous academic document reader.\n\n"
                                "TRANSCRIBE this image with EXTREME precision. Capture:\n"
                                "1. EVERY word exactly as written — preserve spelling (including errors)\n"
                                "2. ALL punctuation marks exactly as they appear (commas, periods, apostrophes)\n"
                                "3. The EXACT ordering of content (paragraphs, numbered lists, bullet points)\n"
                                "4. Letter/essay FORMAT if present (date, address, salutation, body, closing, signature)\n"
                                "5. ALL mathematical formulas, equations, chemical symbols, diagrams\n"
                                "6. Handwriting QUALITY observations (legibility, neatness, crossed-out words)\n"
                                "7. Any drawings, diagrams, or tables — describe their structure and labels\n"
                                "8. Margin notes, corrections, or annotations\n\n"
                                "OUTPUT FORMAT:\n"
                                "[TRANSCRIPTION]\n(exact text as written)\n\n"
                                "[OBSERVATIONS]\n(handwriting quality, formatting style, any notable issues)\n\n"
                                "Be forensically precise. Every detail matters for grading."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
                    ],
                }
            ],
            "task_type": AITaskType.VISION,
            "temperature": 0.1,
            "max_tokens": 3000,
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
            async with httpx.AsyncClient(
                headers=COMMON_HEADERS,
                timeout=httpx.Timeout(30.0),
            ) as client:
                resp = await client.post(
                    f"{API_GATEWAY}/chat",
                    files=files,
                    data=data,
                )

            if resp.status_code != 200:
                logger.error("Whisper HTTP %d: %s", resp.status_code, resp.text[:200])
                resp.raise_for_status()

            data_resp = resp.json()

            # Whisper returns {"text": "..."}, chat completions return choices[]
            transcript = data_resp.get("text", "")
            if not transcript:
                transcript = data_resp.get("choices", [{}])[0].get("message", {}).get("content", "")

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

        total_chars = sum(len(str(m.get("content", ""))) for m in current_messages)
        print(f"[AI] {len(current_messages)} messages, ~{total_chars} chars total", flush=True)

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

                elif func_name == "search_images":
                    query = args.get("query", "")
                    _status(f"🖼️ Finding Images: {query}...")
                    res = await search_images(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_images: {len(res)} items.", flush=True)

                elif func_name == "search_news":
                    query = args.get("query", "")
                    _status(f"📰 Finding News: {query}...")
                    res = await search_news(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_news: {len(res)} items.", flush=True)

                elif func_name == "search_videos":
                    query = args.get("query", "")
                    _status(f"🎬 Finding Videos: {query}...")
                    res = await search_videos(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_videos: {len(res)} items.", flush=True)

                elif func_name == "search_books":
                    query = args.get("query", "")
                    _status(f"📚 Finding Books: {query}...")
                    res = await search_books(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_books: {len(res)} items.", flush=True)

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
                elif func_name == "search_images":
                    query = args.get("query", "")
                    _status(f"🖼️ Finding Images: {query}...")
                    res = await search_images(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_images: {len(res)} items.", flush=True)
                elif func_name == "search_news":
                    query = args.get("query", "")
                    _status(f"📰 Finding News: {query}...")
                    res = await search_news(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_news: {len(res)} items.", flush=True)
                elif func_name == "search_videos":
                    query = args.get("query", "")
                    _status(f"🎬 Finding Videos: {query}...")
                    res = await search_videos(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_videos: {len(res)} items.", flush=True)
                elif func_name == "search_books":
                    query = args.get("query", "")
                    _status(f"📚 Finding Books: {query}...")
                    res = await search_books(query)
                    result_content = str(res)
                    print(f"[AI Tool Result] search_books: {len(res)} items.", flush=True)
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

    async def chat_with_healing(
        self,
        messages: list[dict],
        validation_func,
        system_prompt: str = None,
        task_type: str = AITaskType.TEXT,
        media: dict = None,
        use_tools: bool = True,
        on_status=None,
        max_healing_attempts: int = 2,
        **kwargs,
    ) -> dict:
        """Call AI and automatically self-heal if the validation_func returns None."""
        current_messages = list(messages)

        # First attempt
        resp = await self.chat(messages=current_messages, system_prompt=system_prompt, task_type=task_type, media=media, use_tools=use_tools, on_status=on_status, **kwargs)
        if resp.get("_error"):
            return resp

        raw_content = resp.get("content", "")
        try:
            parsed = validation_func(raw_content)
        except Exception as e:
            logger.warning("Validation exception: %s", e)
            parsed = None

        if parsed is not None:
            resp["parsed"] = parsed
            return resp

        # Self-healing loop
        for attempt in range(max_healing_attempts):
            if on_status:
                on_status(f"⚠️ Format invalid. Attempting AI self-healing ({attempt + 1}/{max_healing_attempts})...")
            print(f"[AI Self-Healing] Attempt {attempt + 1}/{max_healing_attempts} for prompt: {messages[-1]['content'][:80]}...", flush=True)

            # Construct a clear, precise correction turn
            healing_messages = current_messages + [
                {"role": "assistant", "content": raw_content},
                {
                    "role": "user",
                    "content": (
                        "CRITICAL: The previous output could not be parsed successfully.\n"
                        "Please regenerate it and return ONLY the exact, valid output structure requested.\n"
                        "Do not include any thinking tags (<think>), markdown fences, preamble, introduction, "
                        "or extra text. Ensure all quotes, brackets, and commas are perfectly formatted."
                    ),
                },
            ]

            # Call AI again - disable tools to keep it focused on formatting
            resp = await self.chat(messages=healing_messages, system_prompt=system_prompt, task_type=task_type, media=None, use_tools=False, on_status=on_status, **kwargs)
            if resp.get("_error"):
                return resp

            raw_content = resp.get("content", "")
            try:
                parsed = validation_func(raw_content)
            except Exception as e:
                logger.warning("Validation exception: %s", e)
                parsed = None

            if parsed is not None:
                resp["parsed"] = parsed
                if on_status:
                    on_status("✅ Self-healing succeeded!")
                return resp

        # If we reach here, self-healing exhausted
        if on_status:
            on_status("❌ Self-healing exhausted. Displaying fallback.")
        return resp

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
