# 꿀곳간 오토포스터

[@kkulgotgan](https://www.instagram.com/kkulgotgan/) 자동 발행.
`queue/`에 날짜 폴더를 쌓아두면 **화·금 18:07(KST)에 컴퓨터가 꺼져 있어도** 올라간다.

## 구조

```
queue/2026-09-29/  →  publish.py  →  Instagram API  →  게시
                                          ↓
                                    published/2026-09-29/
```

## 시크릿 3개 (Settings → Secrets and variables → Actions)

| 이름 | 값 |
|---|---|
| `META_TOKEN` | 메타 개발자 콘솔에서 발급한 인스타 토큰 |
| `IG_USER_ID` | `17841467752540190` |
| `GH_PAT` | 토큰 자동갱신용 깃허브 PAT (Secrets 쓰기 권한) |

## 워크플로우 2개

- **publish** — 화·금 18:07 게시. 정각은 깃허브 예약이 밀려서 07분에 둠
- **refresh-token** — 매주 일요일 토큰 갱신. 안 하면 60일 뒤 조용히 죽는다

## 유튜브 쇼츠 ([@kkulgotgan](https://www.youtube.com/@kkulgotgan))

- **publish-short** — 수동 실행. 입력 `folder`에 릴스 폴더 이름(예: `2026-10-06 청년미래적금`)
- 릴스 폴더(`reels/` 또는 `published-reels/`)의 `reel.mp4`를 그대로 올린다. 영상을 따로 둘 필요 없음
- 제목 `yt_title.txt`, 설명 `yt_description.txt` (없으면 `caption.txt` 사용)
- 올리면 폴더에 `youtube.txt`(영상 주소)가 생긴다. **이게 있으면 다시 안 올라감** → 재실행해도 중복 없음
- 시크릿 3개 추가: `YT_CLIENT_ID` `YT_CLIENT_SECRET` `YT_REFRESH_TOKEN` (`tools/get_youtube_token.js`로 발급)
- 구글 심사 전에는 업로드 영상이 **비공개로 잠김** → 스튜디오에서 직접 공개 전환

## 확인하는 법

`Actions` 탭 → 초록 체크(성공) / 빨간 X(실패). X를 누르면 어디서 멈췄는지 로그가 다 보인다.

## 주의

- 저장소는 **Public**이어야 한다. 메타 서버가 이미지를 직접 가지러 오기 때문
- **60일간 아무 커밋도 없으면 깃허브가 예약 실행을 꺼버린다.** 한 달에 한 번 큐를 채우면 자동으로 살아있음
- Actions에서 수동 재실행(Re-run)하면 **같은 글이 또 올라간다**
