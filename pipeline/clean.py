"""원본 로드·정제."""
import pandas as pd

from . import config


def read_csv(path, **kw) -> pd.DataFrame:
    """utf-8-sig → cp949 순으로 시도."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"인코딩을 알 수 없음: {path}")


def normalize_code(s: pd.Series) -> pd.Series:
    """아파트코드 → 6자리 문자열 ('60130.0', '060130' → '060130')."""
    num = pd.to_numeric(s, errors="coerce")
    return num.astype("Int64").astype(str).str.zfill(6).where(num.notna())


def parse_date(s: pd.Series) -> pd.Series:
    """'20240731', '2024-07-31', '2024.07.31' 등 → datetime."""
    txt = s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    digits = txt.str.replace(r"[^0-9]", "", regex=True)
    return pd.to_datetime(digits.where(digits.str.len() == 8), format="%Y%m%d", errors="coerce")


def addr_to_sgg(addr):
    if pd.isna(addr) or not str(addr).strip():
        return None
    toks = str(addr).split()
    if toks[0].endswith(("특별시", "광역시", "특별자치시", "특별자치도", "도")):
        toks = toks[1:]
    return toks[0] if toks else None


def load_raw() -> pd.DataFrame:
    df = read_csv(config.RAW_FILE, dtype=str)
    df = df.drop(columns=[c for c in df.columns
                          if c in config.DROP_COLS or c.startswith("Unnamed")])

    need = ["아파트명", "아파트코드", "세대수", "주소", "난방구분"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise RuntimeError(f"원본에 필요한 컬럼 없음: {missing}\n현재 컬럼: {df.columns.tolist()}")

    if "서비스센터" in df.columns and "고객센터" not in df.columns:   # 예전 컬럼명
        df = df.rename(columns={"서비스센터": "고객센터"})

    df["아파트명"] = df["아파트명"].str.strip()
    df["아파트코드"] = normalize_code(df["아파트코드"])
    df = df[df["아파트코드"].notna()]          # 맨 끝 '합계' 행 등 제거
    df["세대수"] = pd.to_numeric(df["세대수"].str.replace(",", ""), errors="coerce").fillna(0).astype(int)
    df["도로명주소"] = df["주소"].str.split("(").str[0].str.strip()

    # 공급승인일자
    col = next((c for c in config.APPROVAL_COL_CANDIDATES if c in df.columns), None)
    if col:
        df["공급승인일자"] = parse_date(df[col])
        if col != "공급승인일자":
            df = df.drop(columns=[col])
        print(f"   공급승인일자: '{col}' 사용 → {df['공급승인일자'].notna().sum():,}/{len(df):,}행 파싱")
    else:
        df["공급승인일자"] = pd.NaT
        print("   ⚠️ 공급승인일자 컬럼 없음 → 빈 값으로 진행")

    return df


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """같은 단지(코드·이름·주소·난방·용도·고객센터)의 여러 행 → 1행, 세대수 합산.

    원본은 공급승인일자별로 행이 나뉨 (예: 46세대 1983-01-01 + 1세대 1999-04-28).
    대표 공급승인일자 = 세대수가 가장 많은 행의 날짜 (같으면 이른 날짜).
    """
    keys = ["아파트명", "아파트코드", "도로명주소", "난방구분", "용도", "고객센터"]
    keys = [k for k in keys if k in df.columns]
    df = df.sort_values(["세대수", "공급승인일자"], ascending=[False, True])
    agg = {c: "first" for c in df.columns if c not in keys}
    agg["세대수"] = "sum"
    return df.groupby(keys, as_index=False, dropna=False).agg(agg)


def add_region(df: pd.DataFrame) -> pd.DataFrame:
    """시군구·시도를 도로명주소 기준으로 채움 (지오코딩 결과보다 신뢰도 높음)."""
    df["시군구명"] = df["도로명주소"].apply(addr_to_sgg)
    df["시도명"] = df["시군구명"].map(
        lambda s: None if s is None else ("경상북도" if s in config.GYEONGBUK_SGG else "대구광역시"))
    return df
