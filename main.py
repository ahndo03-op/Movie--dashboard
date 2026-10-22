import datetime
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 및 제목 표시
# ==========================================
st.set_page_config(
    page_title="일별 박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 조회")
st.caption("영화진흥위원회(KOBIS) API 기반 일별 박스오피스 현황")

# ==========================================
# 2. 날짜 선택 (한국 표준시 KST 기준, 최대 '어제'까지)
# ==========================================
# 배포 서버 시계와 무관하게 한국 시간(Asia/Seoul) 기준으로 어제 날짜 계산
kst = ZoneInfo("Asia/Seoul")
today_kst = datetime.datetime.now(kst).date()
max_allowed_date = today_kst - datetime.timedelta(days=1)

# 달력(date_input)으로 조회하고 싶은 날짜 선택 (기본값: 어제, 선택 가능 최대 날짜: 어제)
selected_date = st.date_input(
    label="📅 조회할 날짜를 선택하세요 (오늘 날짜는 아직 집계 전입니다)",
    value=max_allowed_date,
    max_value=max_allowed_date,
    help="최대 어제 날짜까지 선택할 수 있습니다."
)

# API 요청용 날짜 형식 (YYYYMMDD) 및 화면 표시용 형식 설정
target_date_str = selected_date.strftime("%Y%m%d")
display_date_str = selected_date.strftime("%Y년 %m월 %d일")

st.markdown(f"**선택한 기준일:** `{display_date_str}`")

# ==========================================
# 3. API 키 불러오기 (Secrets 사용)
# ==========================================
if "KOBIS_KEY" not in st.secrets:
    st.error("🔒 **인증키가 설정되지 않았습니다.**")
    st.info(
        "Streamlit Cloud의 **Secrets** 항목 또는 로컬 환경의 `.streamlit/secrets.toml` 파일에\n"
        "`KOBIS_KEY = '발급받은_키'` 형태로 등록되어 있는지 확인해 주세요."
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# ==========================================
# 4. KOBIS API 데이터 요청
# ==========================================
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_date_str
}

try:
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
except Exception as e:
    st.error("⚠️ **API 서버와 통신하는 중 오류가 발생했습니다.**")
    st.write(f"상세 오류 내용: `{e}`")
    st.info("네트워크 상태를 확인하시거나 잠시 후 다시 시도해 주세요.")
    st.stop()

# ==========================================
# 5. API 응답 에러 및 예외 처리
# ==========================================
# 5-1. 인증키 오류 등으로 인한 faultInfo 처리
if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 에러")
    st.error("❌ **API 인증키 오류 또는 서비스 에러가 발생했습니다.**")
    st.warning(f"서버 응답 메시지: `{fault_msg}`")
    st.info(
        "**확인 조치 사항:**\n"
        "1. KOBIS 개발자 센터에서 발급받은 API Key가 정확하게 입력되었는지 확인하세요.\n"
        "2. Streamlit Cloud Secrets에 `KOBIS_KEY` 이름으로 등록되어 있는지 확인하세요."
    )
    st.stop()

# 5-2. 박스오피스 데이터가 비어 있는 경우 처리
box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("📭 **그날은 아직 집계 전입니다.**")
    st.info(
        "**확인 조치 사항:**\n"
        "1. KOBIS API 집계 시스템 반영 전이거나 데이터가 아직 작성되지 않은 날짜일 수 있습니다.\n"
        "2. 다른 과거 날짜를 선택하여 다시 조회해 주세요."
    )
    st.stop()

# ==========================================
# 6. 데이터 전처리 및 가공
# ==========================================
df = pd.DataFrame(daily_list)

# API 응답의 숫자 값이 문자열 형태이므로 정수형(int)으로 변환
numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 6-1. 순위 증감(rankInten) 표시 가공 함수
# 양수: 🔺 (빨간 위 화살표) / 음수: 🔹 (파란 아래 화살표) / 0: -
def format_rank_inten(val):
    if val > 0:
        return f"🔺 {val}"
    elif val < 0:
        return f"🔹 {abs(val)}"
    else:
        return "-"

df["순위변화"] = df["rankInten"].apply(format_rank_inten)

# 6-2. 누적관객수 100만 명 이상 영화명에 트로피(🏆) 이모지 추가
def format_movie_title(row):
    title = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"🏆 {title}"
    return title

df["표시_영화명"] = df.apply(format_movie_title, axis=1)

# ==========================================
# 7. 1위 영화 지표 카드 (Metric Card) 3장 표시
# ==========================================
top_movie = df.iloc[0]

st.divider()
st.subheader(f"🥇 1위 영화: {top_movie['표시_영화명']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="당일 관객수",
        value=f"{top_movie['audiCnt']:,} 명"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{top_movie['audiAcc']:,} 명"
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{top_movie['scrnCnt']:,} 개"
    )

# ==========================================
# 8. 관객수 상위 5편 막대그래프 표시
# ==========================================
st.divider()
st.subheader("📊 관객수 상위 5개 영화")

top_5_df = df.head(5).copy()
chart_df = top_5_df.set_index("movieNm")[["audiCnt"]]
chart_df.columns = ["관객수(명)"]

st.bar_chart(chart_df)

# ==========================================
# 9. 박스오피스 전체 순위 표(Table) 출력
# ==========================================
st.divider()
st.subheader("📋 전체 박스오피스 순위 표")

# 표에 표시할 컬럼 선택 및 한글 컬럼명 설정
display_df = df[["rank", "순위변화", "표시_영화명", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "전날대비", "영화명", "개봉일", "관객수", "누적관객수", "스크린수"]

st.dataframe(
    display_df,
    column_config={
        "관객수": st.column_config.NumberColumn(format="%d명"),
        "누적관객수": st.column_config.NumberColumn(format="%d명"),
        "스크린수": st.column_config.NumberColumn(format="%d개"),
    },
    use_container_width=True,
    hide_index=True
)
