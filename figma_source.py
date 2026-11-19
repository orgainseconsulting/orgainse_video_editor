"""Import the selected frame of an authorized Figma design as a cached PNG."""

import json
import os
import re
import urllib.request
from urllib.parse import parse_qs, quote, urlencode, urlsplit


def frame_ref(url):
    parts = urlsplit(url)
    if parts.hostname not in ("www.figma.com", "figma.com"):
        return None
    match = re.match(r"^/(?:design|file|proto)/([a-zA-Z0-9]+)(?:/|$)", parts.path)
    node = parse_qs(parts.query).get("node-id", [""])[0].replace("-", ":")
    if not match or not re.fullmatch(r"\d+:\d+", node):
        raise ValueError(
            "Choose a specific Figma frame and copy its link with node-id, or supply its exported PNG."
        )
    return match[1], node


def fetch_frame(ref, path):
    token = os.environ.get("FIGMA_TOKEN")
    if not token:
        raise ValueError(
            "For a private Figma frame, set FIGMA_TOKEN before launching the studio or attach a local PNG export."
        )
    key, node = ref
    endpoint = (
        "https://api.figma.com/v1/images/"
        + quote(key)
        + "?"
        + urlencode({"ids": node, "format": "png", "scale": "1.5"})
    )

    class NoTokenRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            raise ValueError("Figma API returned an unexpected redirect.")

    req = urllib.request.Request(endpoint, headers={"X-Figma-Token": token})
    with urllib.request.build_opener(NoTokenRedirect).open(req, timeout=45) as response:
        rendered = json.load(response).get("images", {}).get(node)
    if not rendered or urlsplit(rendered).scheme != "https":
        raise ValueError("Figma did not return an image for the selected frame.")
    # The signed asset URL needs its own request without the Figma access token.
    with urllib.request.urlopen(rendered, timeout=60) as response, path.open("wb") as out:
        signature = response.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Figma frame did not return a PNG.")
        out.write(signature)
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    return path
