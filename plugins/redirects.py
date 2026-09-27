from datasette import hookimpl


def _https_and_hsts(app):
    """Behind Fly's edge the app sees plain HTTP; the original scheme arrives in
    X-Forwarded-Proto. Redirect http → https (301, one canonical scheme for
    crawlers) and send HSTS on every https response."""
    async def wrapped(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        proto = headers.get("x-forwarded-proto", "")
        host = headers.get("host", "")
        if proto == "http" and host and not host.startswith(("localhost", "127.0.0.1")):
            qs = scope.get("query_string", b"").decode("latin-1")
            location = f"https://{host}{scope.get('path', '/')}" + (f"?{qs}" if qs else "")
            await send({"type": "http.response.start", "status": 301,
                        "headers": [(b"location", location.encode("latin-1")),
                                    (b"content-length", b"0")]})
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_with_hsts(message):
            if message["type"] == "http.response.start" and proto == "https":
                message = dict(message)
                message["headers"] = list(message.get("headers", [])) + [
                    (b"strict-transport-security", b"max-age=31536000; includeSubDomains")]
            await send(message)

        return await app(scope, receive, send_with_hsts)
    return wrapped


@hookimpl
def asgi_wrapper(datasette):
    return _https_and_hsts


@hookimpl
def register_routes():
    return ()
