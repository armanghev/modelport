# Python

Python clients can call ModelPort directly over HTTP or point compatible SDKs at the proxy base URL.

## Simple `requests` Example

```python

response = requests.post(
    "https://127.0.0.1:13243/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {os.environ['MODELPORT_TOKEN']}",
        "Content-Type": "application/json",
    },
    json={
        "model": "openai/gpt-4.1",
        "messages": [{"role": "user", "content": "Hello from ModelPort."}],
    },
    timeout=60,
)

response.raise_for_status()
print(response.json())
```

## Anthropic-Style Example

```python

response = requests.post(
    "https://127.0.0.1:13243/v1/messages",
    headers={
        "Authorization": f"Bearer {os.environ['MODELPORT_TOKEN']}",
        "Content-Type": "application/json",
    },
    json={
        "model": "models/gemini-2.5-flash",
        "max_tokens": 128,
        "messages": [{"role": "user", "content": "Hello from ModelPort."}],
    },
    timeout=60,
)

response.raise_for_status()
print(response.json())
```
