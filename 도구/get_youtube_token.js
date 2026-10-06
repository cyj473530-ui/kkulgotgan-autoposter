// 꿀곳간 유튜브 리프레시 토큰 받기 — 처음 한 번만 내 컴퓨터에서 실행한다.
//
// 1) 구글 클라우드에서 받은 OAuth 클라이언트(데스크톱 앱) JSON 을
//    유튜브인증/client_secret.json 으로 저장 (이 폴더는 깃에 안 올라감)
// 2) node 도구/get_youtube_token.js
// 3) 브라우저가 열리면 @kkulgotgan 채널 계정(cyj473530@gmail.com)으로 허용
// 4) 유튜브인증/github_secrets.txt 에 시크릿 3개가 저장됨 → 깃허브 Secrets 에 직접 붙여넣기
//
// 값은 화면에 출력하지 않는다. 채팅에도 붙이지 말 것.

const fs = require("fs");
const path = require("path");
const http = require("http");
const https = require("https");
const { exec } = require("child_process");

const DIR = path.join(__dirname, "..", "유튜브인증");
const raw = JSON.parse(fs.readFileSync(path.join(DIR, "client_secret.json"), "utf8"));
const c = raw.installed || raw.web;
const SCOPE = "https://www.googleapis.com/auth/youtube.upload";

function post(url, form) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams(form).toString();
    const req = https.request(url, { method: "POST", headers: {
      "Content-Type": "application/x-www-form-urlencoded", "Content-Length": Buffer.byteLength(body) } },
      (res) => { let d = ""; res.on("data", (x) => (d += x)); res.on("end", () => resolve(JSON.parse(d))); });
    req.on("error", reject);
    req.end(body);
  });
}

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, "http://127.0.0.1");
  const code = u.searchParams.get("code");
  if (!code) { res.end("코드가 없습니다: " + (u.searchParams.get("error") || "")); return; }
  const redirect = "http://127.0.0.1:" + server.address().port;
  const tok = await post("https://oauth2.googleapis.com/token", {
    code, client_id: c.client_id, client_secret: c.client_secret,
    redirect_uri: redirect, grant_type: "authorization_code",
  });
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  if (!tok.refresh_token) {
    res.end("실패: 리프레시 토큰이 안 왔습니다. 터미널을 확인하세요.");
    console.error("실패:", tok.error, tok.error_description || "");
  } else {
    fs.writeFileSync(path.join(DIR, "github_secrets.txt"),
      "YT_CLIENT_ID\n" + c.client_id + "\n\nYT_CLIENT_SECRET\n" + c.client_secret +
      "\n\nYT_REFRESH_TOKEN\n" + tok.refresh_token + "\n", "utf8");
    res.end("완료! 이 창은 닫아도 됩니다.");
    console.log("완료 → 유튜브인증/github_secrets.txt 저장됨 (값은 출력하지 않음)");
  }
  server.close();
});

server.listen(0, "127.0.0.1", () => {
  const redirect = "http://127.0.0.1:" + server.address().port;
  const auth = "https://accounts.google.com/o/oauth2/v2/auth?" + new URLSearchParams({
    client_id: c.client_id, redirect_uri: redirect, response_type: "code",
    scope: SCOPE, access_type: "offline", prompt: "consent",
  });
  console.log("브라우저에서 구글 로그인 → 허용을 눌러 주세요.");
  exec('start "" "' + auth + '"');
});
