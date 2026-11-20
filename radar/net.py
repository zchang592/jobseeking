"""Low-frequency, bounded fetches of public documents on explicitly configured hosts."""

from functools import lru_cache
import ipaddress
import json
import os
import socket
import threading
import time
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from .settings import ROOT

CATALOG = json.loads((ROOT / "data/sources.json").read_text())
KNOWN_HOSTS = {
    host for s in CATALOG for host in [urlsplit(s["url"]).hostname, *s.get("hosts", [])]
}
UA = "MusicJobRadar"
MAX_BYTES = 10 * 1024 * 1024


class FetchError(Exception):
    pass


@lru_cache(maxsize=512)
def addresses(host, port, five_minute_bucket):
    for attempt in range(2):
        try:
            return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            if exc.errno != socket.EAI_AGAIN or attempt:
                raise
            time.sleep(1)


def public_url(url, hosts=None):
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        valid = (
            p.scheme in ("https", "http")
            and p.port in (None, 80, 443)
            and not p.username
            and not p.password
        )
        if (
            not valid
            or not host
            or "." not in host
            or host.endswith((".internal", ".local", ".localhost"))
            or "%" in host
        ):
            raise FetchError("仅支持公开 HTTP(S) 网站的标准端口")
        if hosts is not None and host not in hosts:
            raise FetchError("域名不在该来源的监控范围")
        try:
            ips = addresses(host, p.port or 443, int(time.monotonic() // 300))
        except socket.gaierror:
            # Managed HTTP proxies resolve the built-in school domains at the egress gateway.
            # A user-supplied hostname always requires positive public DNS verification.
            if host in KNOWN_HOSTS and (
                os.getenv(p.scheme + "_proxy") or os.getenv(p.scheme.upper() + "_PROXY")
            ):
                return urldefrag(url.strip())[0]
            raise
        if not ips or any(not ipaddress.ip_address(i[4][0]).is_global for i in ips):
            raise FetchError("地址未解析为公网地址")
        return urldefrag(url.strip())[0]
    except (OSError, ValueError) as exc:
        raise FetchError("域名或网址无效，无法解析公网地址") from exc


class Web:
    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": UA + "/1.0 (public recruitment monitor)"}, timeout=12
        )
        self.rules = {}
        self.next_request = {}
        self.lock = threading.Lock()

    def close(self):
        self.client.close()

    def _request(self, url, wait, headers=None, limit=MAX_BYTES):
        host = urlsplit(url).hostname
        with self.lock:
            when = max(time.monotonic(), self.next_request.get(host, 0))
            self.next_request[host] = when + max(1.5, wait)
        time.sleep(max(0, when - time.monotonic()))
        try:
            with self.client.stream("GET", url, headers=headers) as r:
                if r.is_redirect or r.status_code != 200:
                    return r.status_code, r.headers, b""
                content = bytearray()
                for chunk in r.iter_bytes(chunk_size=65536):
                    content.extend(chunk)
                    if len(content) > limit:
                        raise FetchError("文件超出采集大小上限")
                return 200, r.headers, bytes(content)
        except httpx.HTTPError as exc:
            raise FetchError(f"连接失败：{type(exc).__name__}") from exc

    def _policy(self, url, hosts):
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self.rules:
            rule = RobotFileParser()
            robots = origin + "/robots.txt"
            for _ in range(4):
                code, headers, body = self._request(robots, 1.5, limit=512000)
                if code in (301, 302, 303, 307, 308):
                    robots = public_url(
                        urljoin(robots, headers.get("location", "")), hosts
                    )
                    continue
                break
            if code in (404, 410):
                rule.parse([])
            elif code == 200 and b"<html" not in body[:500].lower():
                rule.parse(body.decode("utf-8-sig", "replace").splitlines())
            else:
                raise FetchError(f"robots.txt 无法核实（HTTP {code}），暂停访问")
            self.rules[origin] = rule
        rule = self.rules[origin]
        if not rule.can_fetch(UA, url):
            raise FetchError("robots.txt 禁止自动访问")
        delay = rule.crawl_delay(UA) or 0
        rate = rule.request_rate(UA)
        if rate:
            delay = max(delay, rate.seconds / rate.requests)
        if delay > 120:
            raise FetchError("站点要求较长请求间隔，待人工核实")
        return delay

    def get(self, url, hosts, headers=None):
        for _ in range(5):
            url = public_url(url, hosts)
            delay = self._policy(url, hosts)
            code, hdrs, data = self._request(url, delay, headers)
            if code in (301, 302, 303, 307, 308):
                url = urljoin(url, hdrs.get("location", ""))
                continue
            if code not in (200, 304):
                raise FetchError(f"HTTP {code}，未取得公开内容")
            return url, hdrs, data
        raise FetchError("重定向次数超过上限")
