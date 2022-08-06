import json
from urllib.parse import urlparse

import requests
from flask import Flask, Response, request

app = Flask(__name__)

JSON_CTYPE = "application/json"


INVALID_REQ = Response(
    json.dumps({"error": "Invalid Request"}), status=400, content_type=JSON_CTYPE
)

INVALID_FWD = Response(
    json.dumps({"error": "Invalid url"}), status=400, content_type=JSON_CTYPE
)


ALLOWED_SCHEMES = ("http", "https")


_REMOVE_HEADERS = (
    "x-forwarded-host",
    "x-forwarded-for",
    "host",
    "accept-encoding",
    "x-real-ip",
    "x-vercel-deployment-url",
    "x-vercel-id",
    "x-vercel-forwarded-for",
    "x-vercel-trace",
)

_SET_HEADERS = ("origin",)


def val_or_none(val):
    return val or None


def nice_try(fn):
    def run(*k, **kw):
        try:
            return fn(*k, **kw)
        except:
            return INVALID_REQ

    return run


def remove_headers(send_headers: dict):

    for i in _REMOVE_HEADERS:
        if i in send_headers:
            send_headers.pop(i)


def append_headers(send_headers: dict, url):
    for i in _SET_HEADERS:
        new_header = request.headers.get(i)
        if new_header is not None:
            send_headers[i] = new_header
    send_headers["x-orig-url"] = url


def lower_dict(d):
    return {k.lower(): v for k, v in dict(d).items()}


@app.route("/", methods=["get", "post", "patch", "put", "delete"])
@app.route("/api/", methods=["get", "post", "patch", "put", "delete"])
@nice_try
def catch_all():
    url = request.args.get("fwd")
    if url is None:
        return INVALID_FWD
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return INVALID_FWD
    method = request.method.lower()

    func = getattr(requests, method, None)

    if func is None:
        return INVALID_REQ

    send_data = val_or_none(request.data)
    send_headers = lower_dict(request.headers)

    remove_headers(send_headers)
    append_headers(send_headers, url)

    req = func(url, data=send_data, headers=send_headers, stream=True)

    req: requests.Response

    response_headers = lower_dict(req.headers)

    for x in ("content-length", "content-encoding"):
        if x in response_headers:
            response_headers.pop(x)

    iterator = req.iter_content(chunk_size=1025 * 512)

    # initial_chunk = next(iterator) or b""

    def generate_resp():

        for f in iterator:
            if f:
                yield f
            else:
                break

    return Response(generate_resp(), headers=response_headers, status=req.status_code)


@app.after_request
def respond_headers(resp):
    resp.headers["access-control-allow-origin"] = request.headers.get("origin", "*")
    resp.headers["access-control-allow-credentials"] = "true"
    resp.headers["access-control-allow-headers"] = request.headers.get(
        "access-control-request-headers", "*"
    )
    return resp


if __name__ == "__main__":
    app.run(debug=True)
