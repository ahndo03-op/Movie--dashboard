import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 및 제목 표시
# ==========================================
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) API 기반 일별 박스오피스 현황")

# ==========================================
# 2. 날짜 계산 (한국 표준시 KST 기준)
# ==========================================
# 배포 서버(Streamlit Cloud 등)의 시각 기준이 해외(UTC)일 수 있으므로
# 명시적으로 한국 시간대(Asia/Seoul)를 적용하여 '어제' 날짜를 구합니다.
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
yesterday = now_kst - datetime.timedelta(days=1)

# API 요청용 날짜 형식 (YYYYMMDD)
target_date_str = yesterday.strftime("%Y%m%d")
# 화면 표시용 날짜 형식 (YYYY년 MM월 DD일)
display_date_str = yesterday.strftime("%Y년 %m월 %d일")

st.markdown(f"**기준일:** `{display_date_str}`")

# ==========================================
# 3. API 키 불러오기 (Secrets 사용)
# ==========================================
# Streamlit Secrets(비밀 금고)에 KOBIS_KEY가 없으면 사용자에게 설정 안내 메시지를 출력합니다.
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
# 5-1. 인증키 오류 등으로 인한 faultInfo 처리 (KOBIS API는 상태 코드 200으로 오류 응답 전달)
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

# 5-2. 박스오피스 데이터 구조 검증
box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("📭 **어제 날짜의 박스오피스 데이터가 비어 있거나 존재하지 않습니다.**")
    st.info(
        "**확인 조치 사항:**\n"
        "1. KOBIS API 서비스 점검 시간인지 확인해 주세요.\n"
        "2. 집계 시스템의 문제일 수 있으니 잠시 후 다시 조회해 주세요."
    )
    st.stop()

# ==========================================
# 6. 데이터 전처리 (문자열 -> 숫자 변환)
# ==========================================
df = pd.DataFrame(daily_list)

# API 응답의 숫자 값이 문자열 형태이므로 정수형(int)으로 변환합니다.
numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# ==========================================
# 7. 1위 영화 지표 카드 (Metric Card) 3장 표시
# ==========================================
top_movie = df.iloc[0]

st.divider()
st.subheader(f"🥇 1위 영화: {top_movie['movieNm']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
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
# 차트 가독성을 위해 영화명을 인덱스로 지정하고 관객수 컬럼만 선택
chart_df = top_5_df.set_index("movieNm")[["audiCnt"]]
chart_df.columns = ["관객수(명)"]

st.bar_chart(chart_df)

# ==========================================
# 9. 박스오피스 전체 순위 표(Table) 출력
# ==========================================
st.divider()
st.subheader("📋 전체 박스오피스 순위 표")

# 화면에 보여줄 열을 선택하고 한글 이름으로 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객수", "스크린수"]

# 데이터프레임을 깔끔하게 출력 (숫자 세자리마다 쉼표 처리)
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
