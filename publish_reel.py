# -*- coding: utf-8 -*-
"""꿀곳간 릴스 발행 — reels/<폴더>/ 의 reel.mp4 + cover.jpg + caption.txt 를 릴스로 올린다.

- 캐러셀 자동발행(publish.py)과 완전히 분리. 수동 실행(publish-reel 워크플로)으로만 돈다.
- 인스타 음악 라이브러리 곡은 API로 붙일 수 없다. 영상에 들어 있는 소리(나레이션·효과음)만 나간다.
"""

import os
import time
import pathlib

from publish import api, raw_url, ROOT, IG_ID

REELS = ROOT / "reels"
DONE = ROOT / "published-reels"


def wait_video(cid):
    """영상 처리는 이미지보다 오래 걸린다. 최대 10분 기다린다."""
    for i in range(120):
        st = api(cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise SystemExit("영상 처리 실패: %s" % st)
        if i % 6 == 0:
            print("  영상 처리 중... (%s)" % code)
        time.sleep(5)
    raise SystemExit("10분 넘게 영상 처리가 안 끝남 — 중단합니다.")


def main():
    target = os.environ.get("TARGET_FOLDER", "").strip()
    if not target:
        raise SystemExit("올릴 릴스 폴더 이름을 지정해야 합니다 (예: 2026-10-06 청년미래적금).")
    folder = REELS / target
    if not folder.is_dir():
        cand = sorted(d for d in REELS.iterdir() if d.is_dir() and d.name.startswith(target))
        if not cand:
            raise SystemExit("폴더가 없습니다: reels/%s/" % target)
        folder = cand[0]
    print("발행 대상: reels/%s/" % folder.name)

    video = folder / "reel.mp4"
    if not video.exists():
        raise SystemExit("reel.mp4 가 없습니다.")
    cover = folder / "cover.jpg"
    cap_file = folder / "caption.txt"
    caption = cap_file.read_text(encoding="utf-8").strip() if cap_file.exists() else ""

    params = {
        "media_type": "REELS",
        "video_url": raw_url(video),
        "caption": caption,
        "share_to_feed": "true",
    }
    if cover.exists():
        params["cover_url"] = raw_url(cover)

    c = api(IG_ID + "/media", params, post=True)
    print("컨테이너 생성:", c.get("id"))
    wait_video(c["id"])

    res = api(IG_ID + "/media_publish", {"creation_id": c["id"]}, post=True)
    print("게시 완료:", res)

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
    dest = DONE / folder.name
    n = 2
    while dest.exists():
        dest = DONE / ("%s-%d" % (folder.name, n))
        n += 1
    folder.rename(dest)
    print("reels → %s 로 옮겼습니다." % dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
