# -*- coding: utf-8 -*-
"""꿀곳간 유튜브 쇼츠 업로드 — 릴스 폴더의 reel.mp4 를 유튜브 @kkulgotgan 에 올린다.

- 릴스와 같은 폴더를 그대로 쓴다. reels/<폴더>/ 또는 published-reels/<폴더>/ 에서 찾는다.
- 제목: yt_title.txt 가 있으면 그것, 없으면 caption.txt 첫 줄 (100자 제한)
- 설명: yt_description.txt 가 있으면 그것, 없으면 caption.txt 전체 + #Shorts
- 올리고 나면 폴더에 youtube.txt(영상 주소)를 남긴다. 이게 있으면 다시 안 올린다(재실행 중복 방지).
- 세로 영상 3분 이하는 유튜브가 알아서 쇼츠로 분류한다.
- 구글 심사를 안 받은 API 프로젝트로 올린 영상은 유튜브가 '비공개'로 잠근다.
  그때는 스튜디오에서 직접 공개로 바꾸면 된다.
"""

import os
import json
import pathlib
import urllib.parse
import urllib.request
import urllib.error

ROOT = pathlib.Path(__file__).parent
SEARCH = [ROOT / "reels", ROOT / "published-reels"]
PRIVACY = os.environ.get("YT_PRIVACY", "").strip() or "public"


def http(url, data=None, headers=None, method=None):
    """요청을 보내고 (본문, 헤더)를 돌려준다. 실패하면 응답 본문을 그대로 보여주고 멈춘다."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.read().decode("utf-8", "replace"), r.headers
    except urllib.error.HTTPError as e:
        raise SystemExit(
            "[API 실패] %s\nHTTP %s\n%s" % (url.split("?")[0], e.code, e.read().decode("utf-8", "replace"))
        )


def access_token():
    """리프레시 토큰으로 1시간짜리 액세스 토큰을 받는다."""
    body = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    text, _ = http("https://oauth2.googleapis.com/token", data=body, method="POST")
    return json.loads(text)["access_token"]


def find_folder(target):
    for base in SEARCH:
        if not base.is_dir():
            continue
        if (base / target).is_dir():
            return base / target
        cand = sorted(d for d in base.iterdir() if d.is_dir() and d.name.startswith(target))
        if cand:
            return cand[0]
    raise SystemExit("폴더가 없습니다: reels/ · published-reels/ 아래 %s" % target)


def read(p):
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def main():
    target = os.environ.get("TARGET_FOLDER", "").strip()
    if not target:
        raise SystemExit("올릴 폴더 이름을 지정해야 합니다 (예: 2026-10-06 청년미래적금).")
    folder = find_folder(target)
    print("업로드 대상: %s/" % folder.relative_to(ROOT).as_posix())

    done = folder / "youtube.txt"
    if done.exists():
        raise SystemExit("이미 유튜브에 올린 폴더입니다: %s\n다시 올리려면 youtube.txt 를 지우고 실행하세요." % read(done))

    video = folder / "reel.mp4"
    if not video.exists():
        raise SystemExit("reel.mp4 가 없습니다.")

    caption = read(folder / "caption.txt")
    title = read(folder / "yt_title.txt") or (caption.splitlines()[0] if caption else folder.name)
    title = title[:100]
    desc = read(folder / "yt_description.txt") or caption
    if "#shorts" not in desc.lower():
        desc = (desc + "\n\n#Shorts").strip()

    meta = {
        "snippet": {
            "title": title,
            "description": desc[:5000],
            "categoryId": "26",  # 노하우/스타일
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": PRIVACY,
            "selfDeclaredMadeForKids": False,
            # AI 나레이션·AI 배경 이미지를 쓰므로 '변경·합성 콘텐츠'로 고지한다
            "containsSyntheticMedia": True,
        },
    }
    print("제목:", title)

    token = access_token()
    data = video.read_bytes()

    # 1) 업로드 세션 열기
    _, h = http(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(meta).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(len(data)),
        },
        method="POST",
    )
    session = h["Location"]

    # 2) 영상 올리기 (20MB 안팎이라 한 번에 보낸다)
    print("영상 업로드 중... (%.1f MB)" % (len(data) / 1e6))
    text, _ = http(session, data=data, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "video/mp4",
    }, method="PUT")
    res = json.loads(text)
    vid = res["id"]
    got = res.get("status", {}).get("privacyStatus")
    url = "https://www.youtube.com/shorts/%s" % vid
    print("업로드 완료:", url, "(공개 상태: %s)" % got)
    if got != PRIVACY:
        print("※ 유튜브가 공개 상태를 '%s'로 바꿨습니다. 심사 전 API 프로젝트라 그렇습니다." % got)
        print("  스튜디오 > 콘텐츠에서 직접 '공개'로 바꿔 주세요.")

    done.write_text(url + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
