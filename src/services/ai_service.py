"""AI service — httpx client for CF Worker. Tools run locally before calling AI."""

import base64
import json
import re

import httpx

from core.constants import API_GATEWAY, AITaskType

SYSTEM_PROMPT = """You are Akili, a friendly and knowledgeable AI tutor. You help students learn effectively.

Rules:
- Be encouraging and patient
- Explain concepts clearly with examples
- Format responses with clear structure (headings, bullet points)
- For math/science, show step-by-step solutions
- Keep responses focused and educational"""


class AIService:
    def __init__(self):
        # We increase timeout slightly just in case the final fallback is used
        self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = SYSTEM_PROMPT,
        search_query: str | None = None,
        task_type: str = AITaskType.GENERAL,
        on_status=None,
    ) -> dict:
        """Send chat to CF Worker. Returns full JSON response.
        
        Args:
            messages: Chat history
            system_prompt: System instructions
            search_query: If set, searches web FIRST and adds results to context
            task_type: AITaskType enum to route to the correct model array
            on_status: Optional callback(str) for live status updates
        """
        def _status(msg):
            if on_status:
                on_status(msg)
            print(f"[AI] {msg}")

        full_messages = [{"role": "system", "content": system_prompt}]

        if search_query:
            _status(f"🔍 Searching: {search_query[:60]}...")
            from services.tools import web_search
            results = web_search(search_query, max_results=10)

            if results and not any("error" in r for r in results):
                context = "## Web Search Results\n\n"
                for i, r in enumerate(results, 1):
                    context += f"{i}. **{r['title']}**\n   {r['url']}\n   {r['snippet']}\n\n"

                full_messages.append({
                    "role": "user",
                    "content": f"Here are relevant web search results for context:\n\n{context}\n\nUse these to inform your response.",
                })
                full_messages.append({
                    "role": "assistant",
                    "content": "I've reviewed the search results. I'll use this information in my response.",
                })
                _status(f"📚 Found {len(results)} sources")
            else:
                _status("⚠️ Search returned no results, proceeding without")

        for msg in messages:
            full_messages.append(msg)

        _status("🧠 Thinking...")

        payload = {
            "messages": full_messages,
            "max_tokens": 4096,
            "temperature": 0.7,
            "task_type": task_type,
            "stream": False,
        }

        try:
            resp = await self._client.post(
                f"{API_GATEWAY}/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            print(f"[AI] HTTP error: {e.response.status_code}")
            return {
                "role": "assistant",
                "content": f"⚠️ AI service error ({e.response.status_code}). Please try again.",
                "_error": True,
            }
        except Exception as e:
            print(f"[AI] Connection error: {e}")
            return {
                "role": "assistant",
                "content": "⚠️ Connection error. Check your internet and try again.",
                "_error": True,
            }

        if "error" in data:
            return {
                "role": "assistant",
                "content": f"⚠️ Gateway Error: {data.get('error')}",
                "_error": True,
            }

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        model_used = data.get("_model_used", "unknown")

        content = message.get("content", "")
        content = _strip_thinking(content)

        _status(f"✅ Response from {model_used.split('/')[-1]}")

        return {
            "role": "assistant",
            "content": content,
            "_model": model_used,
        }

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str = SYSTEM_PROMPT,
        search_query: str | None = None,
        task_type: str = AITaskType.GENERAL,
        on_status=None,
    ):
        """Generator that yields chunks of text for real-time UI updates."""
        def _status(msg):
            if on_status:
                on_status(msg)
            print(f"[AI Stream] {msg}")

        full_messages = [{"role": "system", "content": system_prompt}]

        if search_query:
            _status(f"🔍 Searching: {search_query[:60]}...")
            from services.tools import web_search
            results = web_search(search_query, max_results=5)

            if results and not any("error" in r for r in results):
                context = "## Web Search Results\n\n"
                for i, r in enumerate(results, 1):
                    context += f"{i}. **{r['title']}**\n   {r['url']}\n   {r['snippet']}\n\n"

                full_messages.append({
                    "role": "user",
                    "content": f"Here are relevant web search results for context:\n\n{context}\n\nUse these to inform your response.",
                })
                full_messages.append({
                    "role": "assistant",
                    "content": "I've reviewed the search results. I'll use this information in my response.",
                })
                _status(f"📚 Found {len(results)} sources")

        for msg in messages:
            full_messages.append(msg)

        _status("🧠 Thinking...")

        payload = {
            "messages": full_messages,
            "max_tokens": 4096,
            "temperature": 0.7,
            "task_type": task_type,
            "stream": True,
        }

        try:
            async with self._client.stream(
                "POST", 
                f"{API_GATEWAY}/chat", 
                json=payload
            ) as response:
                response.raise_for_status()
                
                # Yield incoming text chunks
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"[AI Stream Error] {e}")
            yield "\n\n⚠️ Connection lost. Please try asking again."

    def make_image_part(self, image_bytes: bytes, mime: str = "image/jpeg") -> dict:
        """Create image part for multimodal message."""
        b64 = base64.b64encode(image_bytes).decode()
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        }

    def make_audio_part(self, audio_bytes: bytes, mime: str = "audio/wav") -> dict:
        """Create audio part for multimodal message."""
        b64 = base64.b64encode(audio_bytes).decode()
        return {
            "type": "input_audio",
            "input_audio": {"data": b64, "format": mime.split("/")[-1]},
        }

    async def close(self):
        await self._client.aclose()


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from AI response."""
    if not text:
        return text
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Handle unclosed <think> tag
    if "<think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1].strip()
        if cleaned.startswith("<think>"):
            cleaned = ""
    # Also strip any <tool_call> XML the model might hallucinate
    cleaned = re.sub(r"<tool_call>.*?</tool_call>", "", cleaned, flags=re.DOTALL).strip()
    cleaned = re.sub(r"<function=.*?</function>", "", cleaned, flags=re.DOTALL).strip()
    return cleaned or text


ai_service = AIService()