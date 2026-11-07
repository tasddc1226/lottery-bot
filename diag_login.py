# 임시 진단 스크립트 (커밋 후 제거 예정) - 비밀값은 출력하지 않음
import os, re, auth
from HttpClient import HttpClientSingleton
a = auth.AuthController(); c = HttpClientSingleton.get_instance()
orig_post = c.post
def post(url, headers=None, data=None):
    r = orig_post(url, headers=headers, data=data)
    if "securityLoginCheck" in url:
        t = r.text
        print("[diag] login POST", r.status_code, r.url, "history:", [(h.status_code, h.headers.get('Location')) for h in r.history])
        print("[diag] set-cookie names:", [k.name for k in r.cookies])
        for pat in [r"const\s+errorMessage\s*=\s*'([^']*)'", r"const\s+errorCode\s*=\s*'([^']*)'", r"<title>([^<]*)</title>"]:
            m = re.search(pat, t); print("[diag]", pat[:25], "=>", m.group(1) if m else None)
        import hashlib
        anon = open(os.environ.get("ANON_HTML","/dev/null")).read() if os.environ.get("ANON_HTML") else ""
        lines = t.splitlines()
        for i,l in enumerate(lines):
            if re.search(r"다음에|나중에|Late|Expry|expry|연장|sendHttpJson\(|action=|\.do[\"']", l) and "gnb" not in l and "law.go" not in l:
                print(f"[diag] L{i}: {l.strip()[:220]}")
        print("[diag] has logout link:", "securityLogout" in t, "| has loginForm:", 'id="loginForm"' in t)
    return r
c.post = post
a.login(os.environ["USERNAME"], os.environ["PASSWORD"])
print("[diag] session cookies:", [(k.name, k.domain, k.path) for k in c.session.cookies])
for u in ["https://www.dhlottery.co.kr/mypage/home", "https://www.dhlottery.co.kr/main"]:
    r = c.session.get(u, headers=a._REQ_HEADERS, timeout=30)
    print("[diag] GET", u, "->", r.status_code, r.url, "logout link:", "securityLogout" in r.text, "loginForm:", 'id="loginForm"' in r.text)
h = dict(a._REQ_HEADERS); h.update({"X-Requested-With":"XMLHttpRequest","Accept":"application/json","AJAX":"true","requestMenuUri":"/mypage/home","Referer":"https://www.dhlottery.co.kr/mypage/home"})
r = c.session.get("https://www.dhlottery.co.kr/mypage/selectUserMndp.do", headers=h, timeout=30)
print("[diag] selectUserMndp ->", r.status_code, r.text[:200].replace("\n"," "))
# JSESSIONID 오버라이드 제거 후 재시도
for k in list(c.session.cookies):
    if k.name == "JSESSIONID": c.session.cookies.clear(k.domain, k.path, k.name)
r = c.session.get("https://www.dhlottery.co.kr/mypage/selectUserMndp.do", headers=h, timeout=30)
print("[diag] selectUserMndp (no JSESSIONID) ->", r.status_code, r.text[:200].replace("\n"," "))
