"""K-apt(국토교통부 공동주택 기본정보) 사용승인일 연결.

- 단지코드·단지명이 당사와 달라서 주소로 매칭: 도로명주소 → 지번 → 지번 본번
  (같은 주소 후보가 여럿이면 세대수가 가장 가까운 단지)
- 조회 결과는 data/cache/kapt_*.csv 에 누적 → 다음 갱신부터는 새 단지만 조회
- API 키: .env 의 DATA_GO_KR_KEY (공공데이터포털 '일반 인증키(Decoding)')
  필요 API 활용신청: 공동주택 단지 목록제공 서비스 / 공동주택 기본 정보제공 서비스

단독 실행(조회만, 이어받기):  python -m pipeline.kapt [제한초]
"""
import os
import re
import sys
import time

import pandas as pd
import requests

from . import config
from .geocode import _load_env

BASE = "https://apis.data.go.kr/1613000/"
LIST_FILE = config.DATA / "cache" / "kapt_목록.csv"
INFO_FILE = config.DATA / "cache" / "kapt_기본정보.csv"
AREAS = [("getSidoAptList4", {"sidoCode": "27"})] + \
        [("getSigunguAptList4", {"sigunguCode": c}) for c in ("47290", "47830", "47850")]  # 경산·고령·칠곡
INFO_COLS = ["kaptCode", "kaptName", "kaptUsedate", "codeHeatNm", "kaptdaCnt", "kaptDongCnt",
             "doroJuso", "kaptAddr", "kaptTel"]


# ── API ──────────────────────────────────────────────────────
class QuotaExceeded(Exception):
    pass


def _get(path, key, tries=8, **params):
    """공공데이터 게이트웨이가 간헐적으로 HTTP_ERROR(04)를 줘서 재시도.
    재시도도 일일 호출 한도에 포함되므로 횟수는 적게. 한도 초과(22)면 즉시 중단."""
    for i in range(tries):
        try:
            txt = requests.get(BASE + path, params={"serviceKey": key, **params}, timeout=20).text
            if "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS" in txt:
                raise QuotaExceeded
            return __import__("json").loads(txt)["response"]["body"]
        except QuotaExceeded:
            raise
        except Exception:
            time.sleep(1 + i)
    return None


def _key():
    _load_env()
    return os.getenv("DATA_GO_KR_KEY")


def fetch(limit_sec=None) -> int:
    """목록 + 기본정보 수집(이어받기). 남은 건수 반환."""
    key = _key()
    if not key:
        print("   ⚠️ .env에 DATA_GO_KR_KEY 없음 → K-apt 조회 건너뜀 (캐시만 사용)")
        return -1
    t0 = time.time()
    if not LIST_FILE.exists():
        rows = []
        for op, p in AREAS:
            pg = 1
            while True:
                b = _get("AptListService4/" + op, key, pageNo=pg, numOfRows=300, **p)
                if b is None:
                    raise RuntimeError("K-apt 목록 조회 실패 — 잠시 후 다시 실행")
                rows += b.get("items") or []
                if pg * 300 >= int(b["totalCount"]):
                    break
                pg += 1
        LIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).drop_duplicates("kaptCode").to_csv(LIST_FILE, index=False, encoding="utf-8-sig")
    lst = pd.read_csv(LIST_FILE, dtype=str)
    done = load_info()
    todo = [c for c in lst["kaptCode"] if c not in set(done["kaptCode"])]
    print(f"   K-apt 단지 {len(lst):,} | 기본정보 캐시 {len(done):,} | 조회할 것 {len(todo):,}")
    new = []
    for i, c in enumerate(todo, 1):
        if limit_sec and time.time() - t0 > limit_sec:
            break
        try:
            b = _get("AptBasisInfoServiceV5/getAphusBassInfoV5", key, kaptCode=c)
        except QuotaExceeded:
            print("   ⚠️ 오늘 API 호출 한도 초과 → 내일 다시 실행하면 이어서 조회")
            break
        it = (b or {}).get("item") or {}
        if it.get("kaptName"):
            new.append({k: it.get(k) for k in INFO_COLS})
        if i % 100 == 0:
            print(f"   {i}/{len(todo)}", flush=True)
            _save(done, new)
    _save(done, new)
    left = len(todo) - len(new)
    print(f"   이번 조회 {len(new):,} | 남음 {left:,}")
    return left


def load_info() -> pd.DataFrame:
    if not INFO_FILE.exists():
        return pd.DataFrame(columns=INFO_COLS)
    return pd.read_csv(INFO_FILE, dtype=str)[INFO_COLS].dropna(subset=["kaptName"])


def _save(done, new):
    if new:
        pd.concat([done, pd.DataFrame(new)], ignore_index=True).drop_duplicates("kaptCode", keep="last") \
          .to_csv(INFO_FILE, index=False, encoding="utf-8-sig")


# ── 주소 정규화 ───────────────────────────────────────────────
def _road(s):
    """'대구광역시 달서구 월성로 77 (…)' → '달서구|월성로|77'"""
    if not isinstance(s, str):
        return None
    s = re.sub(r"^(대구광역시|경상북도)\s*", "", s.strip())
    m = re.match(r"(\S+[시군구])\s+(?:\S+[읍면]\s+)?(\S+?(?:로|길))\s*(\d+(?:-\d+)?)", s)
    return f"{m.group(1)}|{m.group(2)}|{m.group(3)}" if m else None


def _jibun_ours(s):
    """'달서구 구마로36길 20 (본동 247)' / '남구 봉덕동 350' → '본동|247'"""
    if not isinstance(s, str):
        return None
    m = re.search(r"\((\S+?[동가리])\s+(산?\s?\d+(?:-\d+)?)", s) or \
        re.search(r"(\S+?[동가리])\s+(산?\s?\d+(?:-\d+)?)", s)
    return f"{m.group(1)}|{m.group(2).replace(' ', '')}" if m else None


def _jibun_kapt(s):
    """'대구광역시 중구 대봉동 590-395 단지명' → '대봉동|590-395'"""
    if not isinstance(s, str):
        return None
    m = re.search(r"\s(\S+?[동가리])\s+(산?\s?\d+(?:-\d+)?)", s)
    return f"{m.group(1)}|{m.group(2).replace(' ', '')}" if m else None


# ── 매칭 ─────────────────────────────────────────────────────
OUT_COLS = {"사용승인일": "kaptUsedate", "K-apt단지명": "kaptName", "K-apt난방방식": "codeHeatNm",
            "K-apt세대수": "kaptdaCnt", "동수": "kaptDongCnt", "관리사무소전화": "kaptTel"}


def _tel(v):
    if not isinstance(v, str) or not v.strip():
        return None
    d = re.sub(r"\D", "", v.split(".")[0])
    d = d if d.startswith("0") else "0" + d
    return f"{d[:3]}-{d[3:-4]}-{d[-4:]}" if len(d) >= 9 else d


def _norm_name(s):
    s = re.sub(r"\(.*?\)|아파트|apt|APT|[\s_\-·,.]", "", str(s)).lower()
    return s.replace("엘에이치", "lh").replace("이편한", "e편한").replace("제", "")


def _plausible(n_ours, n_kapt, name_ours, name_kapt, strict=False) -> bool:
    """주소가 같아도 다른 건물(빌라 등)일 수 있어 검증: 세대수 비율 0.5~2배 또는 단지명 유사.
    strict(지번 본번만 같은 경우): 둘 다 만족해야 인정."""
    from difflib import SequenceMatcher
    sim_ok = SequenceMatcher(None, _norm_name(name_ours), _norm_name(name_kapt)).ratio() >= 0.6
    n_ok = bool(n_kapt and n_kapt > 0 and 0.5 <= n_ours / n_kapt <= 2)
    return (sim_ok and n_ok) if strict else (sim_ok or n_ok)


def attach_kapt(df: pd.DataFrame) -> pd.DataFrame:
    """단지 단위 df(도로명주소·주소·세대수·용도) 에 K-apt 컬럼 추가. 공동주택만 매칭."""
    k = load_info()
    for c in list(OUT_COLS) + ["K-apt매칭"]:
        df[c] = None
    if k.empty:
        print("   ⚠️ K-apt 캐시 없음 → 사용승인일 빈 값")
        return df
    k = k.assign(r=k.doroJuso.map(_road), j=k.kaptAddr.map(_jibun_kapt))
    k["jb"] = k.j.str.split("-").str[0]
    k["n"] = pd.to_numeric(k.kaptdaCnt, errors="coerce")
    idx = {c: k.dropna(subset=[c]).groupby(c) for c in ("r", "j", "jb")}

    addr = df["주소"] if "주소" in df.columns else df["도로명주소"]
    keys = pd.DataFrame({"r": df["도로명주소"].map(_road), "j": addr.map(_jibun_ours)})
    keys["jb"] = keys.j.str.split("-").str[0]
    target = df["용도"].eq("공동주택") if "용도" in df.columns else pd.Series(True, index=df.index)

    for i in df.index[target]:
        n_ours, name = df.at[i, "세대수"], df.at[i, "아파트명"]
        for col, label in (("r", "도로명주소"), ("j", "지번"), ("jb", "지번본번")):
            v = keys.at[i, col]
            if pd.isna(v) or v not in idx[col].groups:
                continue
            h = idx[col].get_group(v)
            h = h.iloc[(h.n - n_ours).abs().argsort()]
            hit = next((x for _, x in h.iterrows() if _plausible(n_ours, x.n, name, x.kaptName, strict=(col == "jb"))), None)
            if hit is None:
                continue
            for out, src in OUT_COLS.items():
                df.at[i, out] = hit[src]
            df.at[i, "K-apt매칭"] = label + (f"(후보{len(h)})" if len(h) > 1 else "")
            break

    df["사용승인일"] = pd.to_datetime(df["사용승인일"].astype(str).str[:8], format="%Y%m%d", errors="coerce")
    df["관리사무소전화"] = df["관리사무소전화"].map(_tel)
    for c in ("K-apt세대수", "동수"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    n_apt, n_hit = int(target.sum()), int(df["K-apt매칭"].notna().sum())
    print(f"   K-apt 매칭 {n_hit:,} / 공동주택 {n_apt:,} 단지")
    return df


if __name__ == "__main__":
    fetch(float(sys.argv[1]) if len(sys.argv) > 1 else None)
