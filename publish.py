# -*- coding: utf-8 -*-
"""꿀곳간 자동 발행 — queue/<오늘날짜>/ 폴더를 캐러셀로 인스타에 올린다."""

import os
import sys
import json
import time
import datetime
import pathlib
import urllib.parse
import urllib.request
import urllib.error

GRAPH = os.environ.get("GRAPH_VERSION", "https://graph.instagram.com/v23.0")
TOKEN = os.environ["META_TOKEN"]
IG_ID = os.environ["IG_USER_ID"]
REPO = os.environ["GITHUB_REPOSITORY"]
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")

ROOT = pathlib.Path(__file__).parent
QUEUE = ROOT / "queue"
DONE = ROOT / "published"
KST = datetime.timezone(datetime.timedelta(hours=9))
IMG_EXT = {".png", ".jpg", ".jpeg"}
MAX_ITEMS = 10


def api(path, params=None, post=False):
    """그래프 API 호출. 실패하면 응답 본문을 그대로 보여주고 멈춘다."""
    params = dict(params or {})
    params["access_token"] = TOKEN
    url = "%s/%s" % (GRAPH, path)
    try:
        if post:
            req = urllib.request.Request(
                url, data=urllib.parse.urlencode(params).encode(), method="POST"
            )
        else:
            req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params))
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(
            "[API 실패] %s\nHTTP %s\n%s" % (path, e.code, e.read().decode("utf-8", "replace"))
        )


def raw_url(p):
    """메타 서버가 이미지를 가져갈 공개 주소."""
    rel = urllib.parse.quote(p.relative_to(ROOT).as_posix())
    return "https://raw.githubusercontent.com/%s/%s/%s" % (REPO, BRANCH, rel)


def wait_ready(cid, label):
    """메타가 이미지를 다 받아갈 때까지 기다린다."""
    for _ in range(30):
        st = api(cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise SystemExit("[%s] 이미지 처리 실패: %s" % (label, st))
        time.sleep(5)
    raise SystemExit("[%s] 2분 넘게 준비 안 됨 — 중단합니다." % label)


def main():
    today = datetime.datetime.now(KST).strftime("%Y-%m-%d")
    # 수동 실행 시 특정 폴더를 지정하면 그걸 올린다(즉시발행). 없으면 오늘 날짜.
    target = os.environ.get("TARGET_FOLDER", "").strip()
    name = target if target else today
    folder = QUEUE / name

    if not folder.is_dir():
        print("올릴 폴더가 없습니다: queue/%s/ (지정: %r, 오늘: %s)" % (name, target, today))
        return
    print("발행 대상 폴더: %s" % name)

    cap_file = folder / "caption.txt"
    caption = cap_file.read_text(encoding="utf-8").strip() if cap_file.exists() else ""

    images = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMG_EXT)
    if not images:
        raise SystemExit("%s 에 이미지가 없습니다." % folder)
    if len(images) > MAX_ITEMS:
        print("이미지 %d장 → 캐러셀 한도 때문에 앞 %d장만 씁니다." % (len(images), MAX_ITEMS))
        images = images[:MAX_ITEMS]

    print("오늘 게시: %s (이미지 %d장)" % (today, len(images)))

    if len(images) == 1:
        # 캐러셀은 2장 이상이어야 하므로 단일 이미지로 올린다
        c = api(IG_ID + "/media", {"image_url": raw_url(images[0]), "caption": caption}, post=True)
        wait_ready(c["id"], "단일 이미지")
        creation_id = c["id"]
    else:
        children = []
        for i, p in enumerate(images, 1):
            c = api(
                IG_ID + "/media",
                {"image_url": raw_url(p), "is_carousel_item": "true"},
                post=True,
            )
            wait_ready(c["id"], "%d번째 장" % i)
            children.append(c["id"])
            print("  %d/%d 준비됨" % (i, len(images)))

        car = api(
            IG_ID + "/media",
            {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption},
            post=True,
        )
        wait_ready(car["id"], "캐러셀")
        creation_id = car["id"]

    res = api(IG_ID + "/media_publish", {"creation_id": creation_id}, post=True)
    print("게시 완료:", res)

    DONE.mkdir(exist_ok=True)
    dest = DONE / today
    n = 2
    while dest.exists():  # 같은 날 두 번 올리면 이름이 겹친다
        dest = DONE / ("%s-%d" % (today, n))
        n += 1
    folder.rename(dest)
    print("queue → %s 로 옮겼습니다." % dest.name)


if __name__ == "__main__":
    main()
