# -*- coding: utf-8 -*-
"""토큰 자동 갱신 — 인스타 토큰을 새로 받아 깃허브 시크릿에 덮어쓴다.

인스타 토큰은 60일이면 만료되고, 만료되면 에러도 없이 그냥 안 올라간다.
매주 돌려서 항상 60일 가까이 남은 상태로 유지한다.
"""

import os
import json
import base64
import urllib.parse
import urllib.request
import urllib.error

from nacl import encoding, public

TOKEN = os.environ["META_TOKEN"]
PAT = os.environ["GH_PAT"]
REPO = os.environ["GITHUB_REPOSITORY"]


def gh(path, method="GET", body=None):
    req = urllib.request.Request(
        "https://api.github.com/repos/%s/%s" % (REPO, path),
        data=json.dumps(body).encode() if body else None,
        method=method,
        headers={
            "Authorization": "Bearer %s" % PAT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(
            "[깃허브 API 실패] %s\nHTTP %s\n%s"
            % (path, e.code, e.read().decode("utf-8", "replace"))
        )


def main():
    # 1) 인스타 토큰 갱신
    url = "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode(
        {"grant_type": "ig_refresh_token", "access_token": TOKEN}
    )
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(
            "[토큰 갱신 실패] HTTP %s\n%s\n"
            "이미 만료됐다면 메타 개발자 콘솔에서 토큰을 새로 발급받아야 합니다."
            % (e.code, e.read().decode("utf-8", "replace"))
        )

    new_token = data["access_token"]
    print("토큰 갱신됨. 남은 유효기간: 약 %.0f일" % (data.get("expires_in", 0) / 86400))

    # 2) 깃허브 시크릿에 덮어쓰기 (libsodium 봉인 암호화 필요)
    key = gh("actions/secrets/public-key")
    sealed = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder))
    encrypted = base64.b64encode(sealed.encrypt(new_token.encode())).decode()

    gh(
        "actions/secrets/META_TOKEN",
        "PUT",
        {"encrypted_value": encrypted, "key_id": key["key_id"]},
    )
    print("META_TOKEN 시크릿 갱신 완료.")


if __name__ == "__main__":
    main()
