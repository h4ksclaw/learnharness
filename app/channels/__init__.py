"""Base channel adapter — all adapters inherit from this.

The flow is:
1. Adapters listen for incoming messages on their platform (IRC, Telegram, Discord).
2. Incoming messages are forwarded to the LearnHarness API (/v1/chat/completions).
3. The response is sent back on the platform.
4. Adapters also poll /v1/outbound for proactive messages the agent wants to send.
"""
