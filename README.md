# PyCorsProxy

A simple Python CORS proxy with SQLite caching.

## Features

- Proxies HTTP requests to bypass CORS restrictions
- SQLite caching with 1 hour TTL
- Automatic cache hit/miss detection

## Installation

No dependencies required - uses Python standard library only.

## Usage

Start the server:

```bash
python server.py --host 0.0.0.0 --port 5000 --log proxy.log
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--host` | Host to bind to | `0.0.0.0` |
| `--port` | Port to bind to | `5000` |
| `--log` | Log file path (auto-rotates at 10MB) | none |

Make a proxy request:

```
GET http://localhost:5000/proxy?url=https://example.com/api/data
```

## Response Headers

- `X-Cache: HIT` - Response served from cache
- `X-Cache: MISS` - Response fetched from origin
- `Access-Control-Allow-Origin: *` - CORS enabled

## Requirements

- Python 3.x

## License

BSD 3-Clause License. See [LICENSE](LICENSE) file for details.

## AI Disclosure & Responsibility

Note: Approximately 95% of this codebase was generated using MiniMax M2.5.

While the logic has been prompted and organized by a human maintainer, it may contain patterns, bugs, or inefficiencies unique to large language models. This project is provided "as-is" for educational purposes. Users are encouraged to conduct their own security and performance audits before using this code in a production environment.
