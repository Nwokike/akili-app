"""AI service — httpx client for CF Worker. Tools run locally before calling AI."""

import base64
import json
import re

import httpx

from core.constants import API_GATEWAY


SYSTEM_PROMPT = """You are Akili, a friendly and knowledgeable AI tutor. You help students learn effectively.

Rules:
- Be encouraging and patient
- Explain concepts clearly with examples
- Format responses with clear structure (headings, bullet points)
- For math/science, show step-by-step solutions
- Keep responses focused and educational"""


class AIService:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=90.0)

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = SYSTEM_PROMPT,
        search_query: str | None = None,
        on_status=None,
    ) -> dict:
        """Send chat to CF Worker. Optionally searches web first for context.

        Args:
            messages: Chat history
            system_prompt: System instructions
            search_query: If set, searches web FIRST and adds results to context
            on_status: Optional callback(str) for live status updates
        """
        def _status(msg):
            if on_status:
                on_status(msg)
            print(f"[AI] {msg}")

        # Prepend system message
        full_messages = [{"role": "system", "content": system_prompt}]

        # If search requested, do it first and inject as context
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
            else:
                _status("⚠️ Search returned no results, proceeding without")

        for msg in messages:
            full_messages.append(msg)

        _status("🧠 Thinking...")

        payload = {
            "messages": full_messages,
            "max_tokens": 4096,
            "temperature": 0.7,
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
