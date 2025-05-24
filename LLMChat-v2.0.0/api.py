import aiohttp
import json
import openai
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

async def fetch_models_async(provider, api_key, url=None, headers=None, known_models=None):
    """Fetch models for a provider asynchronously with retry."""
    if not api_key:
        return []
    try:
        if known_models:
            return sorted(known_models)
        async with aiohttp.ClientSession() as session:
            headers = headers or {"Authorization": f"Bearer {api_key}"}
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
                models = data.get("data", data.get("models", []))
                return sorted([model.get("id", model.get("name", "")) for model in models])
    except Exception as e:
        print(f"Error fetching {provider} models: {e}")
        return []

async def fetch_all_models(config):
    """Fetch models from all providers concurrently."""
    model_groups = {
        'OpenAI': [], 'OpenRouter': [], 'XAI': [], 'Anthropic': [], 'HuggingFace': [],
        'Google': [], 'Perplexity': [], 'Together': [], 'Groq': [], 'Pi': [],
        'Mistral': [], 'DeepSeek': []
    }
    tasks = [
        (fetch_models_async("OpenAI", config["openai_api_key"], "https://api.openai.com/v1/models"), "OpenAI"),
        (fetch_models_async("OpenRouter", config["openrouter_api_key"], "https://openrouter.ai/api/v1/models"), "OpenRouter"),
        (fetch_models_async("XAI", config["xai_api_key"], "https://api.x.ai/v1/models"), "XAI"),
        (fetch_models_async("Anthropic", config["anthropic_api_key"], known_models=["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]), "Anthropic"),
        (fetch_models_async("HuggingFace", config["huggingface_api_key"], "https://api-inference.huggingface.co/models"), "HuggingFace"),
        (fetch_models_async("Google", config["google_api_key"], f"https://generativelanguage.googleapis.com/v1beta/models?key={config['google_api_key']}"), "Google"),
        (fetch_models_async("Perplexity", config["perplexity_api_key"], known_models=["llama-3-sonar-large-32k-online", "llama-3-sonar-small-32k-online"]), "Perplexity"),
        (fetch_models_async("Together", config["together_api_key"], "https://api.together.ai/models"), "Together"),
        (fetch_models_async("Groq", config["groq_api_key"], "https://api.groq.com/openai/v1/models"), "Groq"),
        (fetch_models_async("Pi", config["pi_api_key"], known_models=["xAI-Pi"]), "Pi"),
        (fetch_models_async("Mistral", config["mistral_api_key"], "https://api.mixtral.ai/v1/models"), "Mistral"),
        (fetch_models_async("DeepSeek", config["deepseek_api_key"], "https://api.deepseek.com/v1/models"), "DeepSeek")
    ]
    results = await asyncio.gather(*(task[0] for task in tasks), return_exceptions=True)
    for (task, provider), result in zip(tasks, results):
        if not isinstance(result, Exception):
            model_groups[provider] = result
    return model_groups

async def process_ai_response(app, selected_model_full, messages, config):
    """Process AI response with streaming and cost/token tracking."""
    if not selected_model_full or "No models" in selected_model_full:
        app.add_log_message("Error: No model selected.", "error")
        return
    try:
        provider, model_id = selected_model_full.split(": ", 1)
    except ValueError:
        app.add_log_message(f"Error: Invalid model format '{selected_model_full}'.", "error")
        return

    api_key = config.get(f"{provider.lower()}_api_key")
    if not api_key:
        app.add_log_message(f"Error: {provider} API key not set.", "error")
        return

    client_config = {}
    base_url = None
    headers = {"Content-Type": "application/json"}
    if provider == "OpenAI":
        client_config = {"api_key": api_key}
    elif provider == "OpenRouter":
        client_config = {"api_key": api_key, "base_url": "https://openrouter.ai/api/v1"}
    elif provider == "XAI":
        client_config = {"api_key": api_key, "base_url": "https://api.x.ai/v1"}
    elif provider == "Anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        base_url = "https://api.anthropic.com/v1/messages"
    elif provider == "HuggingFace":
        headers["Authorization"] = f"Bearer {api_key}"
        base_url = f"https://api-inference.huggingface.co/models/{model_id}"
    elif provider == "Google":
        base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    elif provider == "Perplexity":
        headers["Authorization"] = f"Bearer {api_key}"
        base_url = "https://api.perplexity.ai/chat/completions"
    elif provider == "Together":
        headers["Authorization"] = f"Bearer {api_key}"
        base_url = "https://api.together.ai/v1/chat/completions"
    elif provider == "Groq":
        client_config = {"api_key": api_key, "base_url": "https://api.groq.com/openai/v1"}
    elif provider == "Pi":
        headers["Authorization"] = f"Bearer {api_key}"
        base_url = "https://api.pi.ai/v1/chat/completions"
    elif provider == "Mistral":
        headers["Authorization"] = f"Bearer {api_key}"
        base_url = "https://api.mixtral.ai/v1/chat/completions"
    elif provider == "DeepSeek":
        headers["Authorization"] = f"Bearer {api_key}"
        base_url = "https://api.deepseek.com/v1/chat/completions"
    else:
        app.add_log_message(f"Error: Unknown provider '{provider}'.", "error")
        return

    try:
        if provider in ["OpenAI", "OpenRouter", "XAI", "Groq"]:
            client = openai.OpenAI(**client_config)
            response_stream = client.chat.completions.create(
                model=model_id, messages=messages,
                temperature=app.temperature_var.get(), max_tokens=app.max_tokens_var.get(),
                presence_penalty=app.presence_penalty_var.get(), frequency_penalty=app.frequency_penalty_var.get(),
                top_p=app.top_p_var.get(), stream=True
            )
            full_response = ""
            message_frame = None
            label = None
            tokens = 0
            for chunk in response_stream:
                text = chunk.choices[0].delta.content or ""
                if text:
                    full_response += text
                    tokens += 1  # Approximate token count
                    if not message_frame:
                        message_frame, label = app.create_message_frame("assistant", "")
                    app.debounce_stream_update(full_response, message_frame, label)
            cost = estimate_cost(provider, model_id, tokens)  # Simplified cost estimation
        else:
            data = {
                "model": model_id,
                "messages": messages,
                "max_tokens": app.max_tokens_var.get(),
                "temperature": app.temperature_var.get(),
                "top_p": app.top_p_var.get(),
                "stream": True if provider in ["Perplexity", "Together", "Pi", "Mistral", "DeepSeek"] else False
            }
            if provider == "Anthropic":
                response = requests.post(base_url, headers=headers, json=data)
                response.raise_for_status()
                full_response = response.json()["content"][0]["text"]
                tokens = len(full_response.split())  # Approximate
            elif provider == "HuggingFace":
                data["inputs"] = "\n".join([msg["content"] for msg in messages])
                response = requests.post(base_url, headers=headers, json=data)
                response.raise_for_status()
                full_response = response.json()[0]["generated_text"]
                tokens = len(full_response.split())
            elif provider == "Google":
                data = {
                    "contents": [{"parts": [{"text": msg["content"]} for msg in messages]}],
                    "generationConfig": {
                        "maxOutputTokens": app.max_tokens_var.get(),
                        "temperature": app.temperature_var.get(),
                        "topP": app.top_p_var.get()
                    }
                }
                response = requests.post(base_url, headers=headers, json=data)
                response.raise_for_status()
                full_response = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                tokens = len(full_response.split())
            else:
                response = requests.post(base_url, headers=headers, json=data, stream=True)
                response.raise_for_status()
                full_response = ""
                message_frame = None
                label = None
                tokens = 0
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data:"):
                            data = json.loads(decoded_line[5:])
                            if "choices" in data and data["choices"]:
                                text = data["choices"][0].get("delta", {}).get("content", "") or ""
                                if text:
                                    full_response += text
                                    tokens += 1
                                    if not message_frame:
                                        message_frame, label = app.create_message_frame("assistant", "")
                                    app.debounce_stream_update(full_response, message_frame, label)
            cost = estimate_cost(provider, model_id, tokens)

        if full_response.strip() and app.current_conversation_id:
            app.conversation_log.append({"role": "assistant", "content": full_response})
            await db.add_message_to_db(app.current_conversation_id, "assistant", full_response, tokens=tokens, cost=cost)
            app.add_log_message(f"Tokens: {tokens}, Estimated Cost: ${cost:.4f}", "system")
            if app.tts_provider.get() != "None":
                app.play_message(full_response)
    except Exception as e:
        app.add_log_message(f"API Error ({provider} {model_id}): {str(e)}", "error")

def estimate_cost(provider, model_id, tokens):
    """Estimate API cost based on provider and model (simplified)."""
    # Placeholder pricing (update with actual rates)
    pricing = {
        "OpenAI": {"gpt-4": 0.03 / 1000, "gpt-3.5-turbo": 0.0015 / 1000},
        "XAI": {"grok": 0.01 / 1000},
        # Add other providers
    }
    rate = pricing.get(provider, {}).get(model_id, 0.01 / 1000)
    return tokens * rate