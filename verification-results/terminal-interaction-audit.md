# Terminal interaction audit

Commit under test: `5f0f694`  
Online deployment run: `30552316701` (success)  
Online URL: `http://101.32.190.42/`

The real online Workbench now mounts xterm after the asynchronously loaded exercise appears. DOM evidence showed `.pw-xterm` with a real xterm terminal and `Terminal input`; the online run displayed compile/startup messages and exit code 0. The deployed WebSocket endpoint also completed the HTTP 101 upgrade.

Python `gigasecond` was used for the online smoke test, but it is a function-only exercise without top-level input, so it cannot prove the requested `Tom`/`18` multi-step interaction. C, C++, Java, Ctrl+C, EOF, stderr ordering, and a hidden adapter remain unverified and are explicitly not marked passed.

Screenshot: `verification-screenshots/terminal-online-pty-mounted.png`
