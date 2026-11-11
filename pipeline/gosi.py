"""고시지역 판정 (좌표가 고시지역 폴리곤 안에 있는지)."""
import json

import pandas as pd
from shapely.geometry import Point, shape
from shapely.prepared import prep

from . import config


def attach_gosi(df: pd.DataFrame) -> pd.DataFrame:
    gj = json.loads(config.GOSI_GEOJSON.read_text(encoding="utf-8"))
    polys = [(f["properties"]["Name"], prep(shape(f["geometry"]))) for f in gj["features"]]

    def find(lon, lat):
        if pd.isna(lon) or pd.isna(lat):
            return None
        pt = Point(lon, lat)
        return next((name for name, g in polys if g.contains(pt)), None)

    df["고시지역명"] = [find(x, y) for x, y in zip(df["경도"], df["위도"])]
    df["고시여부"] = df["고시지역명"].notna().map({True: "예", False: "아니오"})
    return df
