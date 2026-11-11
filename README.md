# 대성에너지 공동주택 지도

Streamlit + PyDeck 공동주택 지도 (난방방식·공급승인연도·고시지역·업종 필터)

## 폴더 구조
```
app.py                 지도 앱 (data/output 만 읽음)
update_data.py         데이터 갱신 실행 파일
pipeline/
  config.py            경로·컬럼 설정
  clean.py             원본 정제 · 단지 단위 집계 · 시군구 보정
  geocode.py           SGIS 지오코딩 (좌표캐시에 없는 신규 단지만)
  gosi.py              고시지역 판정
data/
  raw/공동주택현황.csv   고객지원시스템 원본 (매번 덮어쓰기)
  ref/고시지역.geojson
  cache/좌표캐시.csv     지오코딩 누적 결과 (지우지 말 것)
  output/공동주택_지도.csv  앱 입력
  output/지오코딩실패.csv   좌표 못 찾은 행 확인용
```

## 데이터 갱신
1. 고객지원시스템에서 받은 CSV를 `data/raw/공동주택현황.csv` 로 덮어쓰기
2. (최초 1회) `.env.example` → `.env` 복사 후 SGIS 키 입력
3. `python update_data.py`
4. `streamlit run app.py` 로 확인 → 커밋·푸시

- 공급승인일자 컬럼(`공급승인일자`/`공급승인일`)이 원본에 있으면 자동 반영 (YYYYMMDD, YYYY-MM-DD 등)
- 원본은 공급승인일자별로 행이 나뉨 → 단지별 세대수 합산, 대표 공급승인일자는 세대수가 가장 많은 행의 날짜
- 1983-01-01 은 전산화 이전 공급분 일괄등록일 → 앱에서 "1983 일괄등록"으로 따로 표시
- 좌표 못 찾은 단지는 지도에서 빠지고 `지오코딩실패.csv` 에 남음
