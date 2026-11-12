"""The security boundary for open-ended HTML, owned by the server.

The CSP is injected into every piece of generated HTML before it leaves the
agent -- including HTML that travels inside streamed tool-call arguments --
and the sandbox token list is sent to the page, which applies it verbatim.
"""
SANDBOX = "allow-scripts"
CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
       "img-src data:; base-uri 'none'; form-action 'none'")


def sandboxed(html: str) -> str:
    meta = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
    return html.replace("<head>", "<head>" + meta, 1) if "<head>" in html else meta + html
