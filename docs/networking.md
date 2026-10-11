# External network and transient state policy

FazTestBot routes maintained idempotent HTTP integrations through
`core.http_client.AsyncHttpClient`. Integrations must not create ad-hoc
`aiohttp.ClientSession` objects or put tokens in URL strings.

## HTTP boundary

The shared client provides:

- separate connect, read, and total timeouts;
- bounded exponential retry for transient failures and a capped `Retry-After`;
- a maximum response size before JSON or text parsing;
- redirects disabled unless a future integration explicitly proves they are required;
- typed `APIError` failures with safe user-facing messages;
- retry events containing service and error metadata, but no URL or query parameters.

Callers pass query data via `params`. API keys and tokens must never be interpolated
into endpoints or included in exception messages, logs, or Telegram responses.
Provider payloads are untrusted: validate their type and expected fields before use.

The URL Shortener and IP Lookup clients use this boundary. The Steam integration is
intentionally deferred until the newer Steam implementation from `master` is safely
reconciled into `develop`; the two branches currently have divergent histories.

## Interaction state

`core.state.TransientStateStore` is the bounded in-memory store for module workflows.
It uses a sliding TTL, an entry limit, and a re-entrant lock. New or migrated handlers
must key state by both Telegram actor and chat:

```python
module.set_interaction_state(call.from_user.id, call.message.chat.id, "step", "input")
```

The legacy `set_user_state` helpers remain temporarily compatible with private chats,
where actor and chat identifiers are equal. Do not use them in new code. Admin
snapshots expose only the pruned number of active scopes, never their keys or values.
