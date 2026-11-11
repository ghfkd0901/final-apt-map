"""SGIS 지오코딩 + 좌표캐시.

캐시에 없는 단지(아파트코드+아파트명)만 API를 호출하고, 결과를 캐시에 누적합니다.
API 키는 .env 또는 환경변수 SGIS_SERVICE_ID / SGIS_SECRET_KEY 에서 읽습니다.
"""
import os
import time

import pandas as pd
import requests

from . import config
from .clean import normalize_code, read_csv

CACHE_COLS = config.KEY + ["도로명주소", "위도", "경도", "읍면동명"]
BASE = "https://sgisapi.mods.go.kr/OpenAPI3"


# ── 캐시 ─────────────────────────────────────────────────────
def load_cache() -> pd.DataFrame:
    if not config.COORD_CACHE.exists():
        return pd.DataFrame(columns=CACHE_COLS)
    c = read_csv(config.COORD_CACHE, dtype={"아파트코드": str})
    c["아파트코드"] = normalize_code(c["아파트코드"])
    return c[CACHE_COLS]


def save_cache(cache: pd.DataFrame):
    config.COORD_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache.drop_duplicates(config.KEY, keep="last").to_csv(
        config.COORD_CACHE, index=False, encoding="utf-8-sig")


# ── SGIS API ─────────────────────────────────────────────────
def _load_env():
    env = config.ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _token() -> str:
    _load_env()
    sid, sec = os.getenv("SGIS_SERVICE_ID"), os.getenv("SGIS_SECRET_KEY")
    if not sid or not sec:
        raise RuntimeError(".env에 SGIS_SERVICE_ID / SGIS_SECRET_KEY 를 넣어주세요 (.env.example 참고)")
    data = requests.get(f"{BASE}/auth/authentication.json",
                        params={"consumer_key": sid, "consumer_secret": sec}, timeout=10).json()
    if data.get("errCd") != 0:
        raise RuntimeError(f"SGIS 토큰 발급 실패: {data}")
    return data["result"]["accessToken"]


def _geocode_one(addr: str, token: str):
    from pyproj import Transformer
    tf = _geocode_one.tf = getattr(_geocode_one, "tf", None) or \
        Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    data = requests.get(f"{BASE}/addr/geocode.json",
                        params={"accessToken": token, "address": addr,
                                "pagenum": 0, "resultcount": 1}, timeout=10).json()
    rd = (data.get("result") or {}).get("resultdata") or []
    if data.get("errCd") != 0 or not rd:
        return None
    lon, lat = tf.transform(float(rd[0]["x"]), float(rd[0]["y"]))
    return {"위도": round(lat, 7), "경도": round(lon, 7), "읍면동명": rd[0].get("adm_nm")}


def geocode_new(todo: pd.DataFrame, delay=0.15, retries=3) -> pd.DataFrame:
    """todo: KEY + 도로명주소. 성공한 행만 반환."""
    token, out = _token(), []
    for i, r in enumerate(todo.itertuples(index=False), 1):
        res = None
        for _ in range(retries):
            try:
                res = _geocode_one(r.도로명주소, token)
                break
            except Exception:
                time.sleep(2)
                token = _token()
        if res:
            out.append({"아파트코드": r.아파트코드, "아파트명": r.아파트명,
                        "도로명주소": r.도로명주소, **res})
        else:
            print(f"   ❌ {r.아파트명} | {r.도로명주소}")
        if i % 50 == 0:
            print(f"   {i}/{len(todo)}")
        time.sleep(delay)
    return pd.DataFrame(out, columns=CACHE_COLS)


# ── 메인 ─────────────────────────────────────────────────────
def attach_coords(df: pd.DataFrame) -> pd.DataFrame:
    cache = load_cache()
    todo = (df[config.KEY + ["도로명주소"]]
            .drop_duplicates(config.KEY)
            .merge(cache[config.KEY], on=config.KEY, how="left", indicator=True)
            .query("_merge == 'left_only'").drop(columns="_merge"))

    print(f"   좌표캐시 {len(cache):,}건 | 신규 단지 {len(todo):,}건")
    if len(todo):
        try:
            new = geocode_new(todo)
        except RuntimeError as e:
            print(f"   ⚠️ 지오코딩 건너뜀: {e}")
            new = pd.DataFrame(columns=CACHE_COLS)
        cache = pd.concat([cache, new], ignore_index=True)
        save_cache(cache)
        print(f"   지오코딩 성공 {len(new):,} / {len(todo):,}")

    df = df.merge(cache.drop(columns="도로명주소").drop_duplicates(config.KEY),
                  on=config.KEY, how="left")

    fails = df[df["위도"].isna()]
    fails.to_csv(config.GEOCODE_FAILS, index=False, encoding="utf-8-sig")
    if len(fails):
        print(f"   ⚠️ 좌표 없음 {len(fails):,}행 → {config.GEOCODE_FAILS.name}")
    return df
