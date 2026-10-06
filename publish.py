# -*- coding: utf-8 -*-
"""꿀곳간 자동 발행 — 업로드대기/<오늘날짜>/ 폴더를 캐러셀로 인스타에 올린다."""

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
QUEUE = ROOT / "업로드대기"
DONE = ROOT / "업로드완료"
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


def pick_folder(today, target):
    """업로드대기 안에서 올릴 폴더를 고른다.
    폴더 이름은 `2026-10-13` 처럼 날짜만이어도, `2026-10-13 도라에몽명대사` 처럼 날짜 뒤에 내용이 붙어 있어도 된다.
    - target(수동/예약 지정)이 있으면 그 이름과 같거나 그 이름으로 시작하는 폴더
    - 없으면 오늘 날짜로 시작하는 폴더(여러 개면 이름순 첫 번째)
    """
    dirs = sorted((d for d in QUEUE.iterdir() if d.is_dir()), key=lambda d: d.name) if QUEUE.is_dir() else []
    if target:
        exact = QUEUE / target
        if exact.is_dir():
            return exact
        cand = [d for d in dirs if d.name.startswith(target)]
        return cand[0] if cand else exact
    cand = [d for d in dirs if d.name == today or d.name.startswith(today + " ") or d.name.startswith(today + "-")]
    return cand[0] if cand else QUEUE / today


def main():
    today = datetime.datetime.now(KST).strftime("%Y-%m-%d")
    # 수동 실행 시 특정 폴더를 지정하면 그걸 올린다(즉시발행). 없으면 오늘 날짜.
    target = os.environ.get("TARGET_FOLDER", "").strip()
    folder = pick_folder(today, target)
    name = folder.name

    if not folder.is_dir():
        print("올릴 폴더가 없습니다: 업로드대기/%s/ (지정: %r, 오늘: %s)" % (name, target, today))
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

    # 첫 댓글(comment.txt)이 있으면 달아서 해시태그·질문으로 노출·댓글 참여를 늘린다. 실패해도 발행은 성공으로 둔다.
    cm_file = folder / "comment.txt"
    if cm_file.exists() and res.get("id"):
        cm = cm_file.read_text(encoding="utf-8").strip()
        if cm:
            try:
                api(res["id"] + "/comments", {"message": cm}, post=True)
                print("첫 댓글 등록 완료")
            except SystemExit as e:
                print("첫 댓글 등록 실패(발행은 정상):", str(e)[:300])

    DONE.mkdir(exist_ok=True)
    # 같은 날 여러 번 올리면 -1, -2, -3 ... 으로 번호를 붙인다(하루 한 번이면 날짜만).
    first = DONE / today
    if first.exists():
        first.rename(DONE / (today + "-1"))
    if (DONE / (today + "-1")).exists():
        n = 2
        while (DONE / ("%s-%d" % (today, n))).exists():
            n += 1
        dest = DONE / ("%s-%d" % (today, n))
    else:
        dest = first
    folder.rename(dest)
    print("업로드대기 → %s 로 옮겼습니다." % dest.name)


if __name__ == "__main__":
    main()
