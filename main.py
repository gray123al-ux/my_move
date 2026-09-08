```python
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="영화 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 영화 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 일별 박스오피스")


# --------------------------------------------------
# 한국 시간 기준 날짜 설정
# --------------------------------------------------
# Streamlit Cloud 서버가 해외에 있어도
# Asia/Seoul 시간대를 사용하면 한국 시간을 기준으로 계산됩니다.
KST = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(KST).date()
yesterday = today_kst - timedelta(days=1)


# --------------------------------------------------
# 날짜 선택
# --------------------------------------------------
# 가장 늦은 날짜는 어제입니다.
selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday
)

# KOBIS API가 요구하는 yyyymmdd 형식으로 변환
target_date = selected_date.strftime("%Y%m%d")


# --------------------------------------------------
# KOBIS API에서 박스오피스 데이터를 가져오는 함수
# --------------------------------------------------
# 같은 날짜를 다시 조회하면 최대 1시간 동안
# 저장된 결과를 사용합니다.
@st.cache_data(ttl=3600)
def get_daily_boxoffice(target_dt):
    """
    KOBIS 일별 박스오피스 API를 호출합니다.

    Parameters
    ----------
    target_dt : str
        조회 날짜 (yyyymmdd)

    Returns
    -------
    tuple
        (영화 목록, 오류 메시지)
    """

    # Streamlit Cloud의 Secrets에서 인증키를 읽습니다.
    # 코드 안에 인증키를 직접 작성하지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]

    except KeyError:
        return None, (
            "인증키를 찾을 수 없습니다. "
            "Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지 확인하세요."
        )

    # KOBIS 일별 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    # API에 전달할 값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # API 요청
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있으면 예외 발생
        response.raise_for_status()

        # JSON 데이터로 변환
        data = response.json()

    except requests.exceptions.Timeout:
        return None, (
            "KOBIS 서버의 응답 시간이 너무 오래 걸렸습니다. "
            "잠시 후 다시 시도해 보세요."
        )

    except requests.exceptions.RequestException as e:
        return None, (
            "KOBIS API 요청에 실패했습니다.\n\n"
            "인터넷 연결 또는 KOBIS API 서버 상태를 확인하세요.\n\n"
            f"오류 내용: {e}"
        )

    except ValueError:
        return None, (
            "KOBIS API 응답을 JSON 형식으로 읽을 수 없습니다. "
            "API 서버 응답을 확인해 보세요."
        )

    # --------------------------------------------------
    # KOBIS API는 인증키 오류 등이 있어도
    # HTTP 상태 코드 200과 함께 faultInfo를 보낼 수 있습니다.
    # --------------------------------------------------
    if "faultInfo" in data:

        fault = data["faultInfo"]

        # 오류 메시지가 있는 경우 가져오기
        message = (
            fault.get("message")
            or fault.get("resultMsg")
            or str(fault)
        )

        return None, (
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            f"오류 내용: {message}\n\n"
            "인증키(KOBIS_KEY)가 올바른지, "
            "API 사용 권한이 정상인지 확인하세요."
        )

    # boxOfficeResult 확인
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return None, (
            "응답에 boxOfficeResult 데이터가 없습니다. "
            "KOBIS API 응답 형식을 확인해 보세요."
        )

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있으면 빈 목록을 그대로 반환합니다.
    # 화면에서 '그날은 아직 집계 전입니다'라고 표시합니다.
    return movie_list, None


# --------------------------------------------------
# 데이터 조회
# --------------------------------------------------
with st.spinner("박스오피스 데이터를 불러오는 중입니다..."):
    movie_list, error_message = get_daily_boxoffice(target_date)


# --------------------------------------------------
# API 요청 오류가 발생한 경우
# --------------------------------------------------
if error_message:

    st.error("⚠️ 박스오피스 데이터를 불러오지 못했습니다.")

    st.markdown(error_message)

    st.info(
        "💡 확인할 사항\n\n"
        "- Streamlit Cloud Secrets에 `KOBIS_KEY`가 등록되어 있는지 확인하세요.\n"
        "- 인증키가 올바른지 확인하세요.\n"
        "- 인터넷 연결과 KOBIS API 서버 상태를 확인하세요."
    )

    # 아래 코드를 실행하지 않고 종료
    st.stop()


# --------------------------------------------------
# 영화 목록이 비어 있는 경우
# --------------------------------------------------
if not movie_list:

    st.warning("📭 그날은 아직 집계 전입니다.")

    st.info(
        "선택한 날짜의 박스오피스 데이터가 아직 제공되지 않았습니다.\n\n"
        "조금 뒤 다시 확인하거나 다른 날짜를 선택해 보세요."
    )

    st.stop()


# --------------------------------------------------
# pandas DataFrame으로 변환
# --------------------------------------------------
df = pd.DataFrame(movie_list)


# --------------------------------------------------
# 숫자 데이터 변환
# --------------------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 정렬과 그래프를 위해 실제 숫자로 변환합니다.
numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in numeric_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0).astype(int)


# --------------------------------------------------
# 순위 기준으로 정렬
# --------------------------------------------------
df = df.sort_values("rank")


# --------------------------------------------------
# 순위 변화 표시 만들기
# --------------------------------------------------
def make_rank_change(rank_inten):
    """
    전날 대비 순위 변화를 표시합니다.

    양수 : 순위 상승 → 🔺 빨간색 느낌의 위 화살표
    음수 : 순위 하락 → 🔽 파란색 느낌의 아래 화살표
    0    : 변화 없음 → -
    """

    if rank_inten > 0:
        return f"🔺 +{rank_inten}"

    elif rank_inten < 0:
        return f"🔽 {rank_inten}"

    else:
        return "-"


# 순위 변화 열 추가
df["rankChange"] = df["rankInten"].apply(make_rank_change)


# --------------------------------------------------
# 누적관객 100만 명 이상 영화 표시
# --------------------------------------------------
def make_movie_name(movie_name, audi_acc):
    """
    누적관객이 100만 명을 넘으면
    영화명 옆에 트로피를 붙입니다.
    """

    if audi_acc > 1_000_000:
        return f"{movie_name} 🏆"

    return movie_name


# 화면에 표시할 영화명 만들기
df["movieDisplay"] = df.apply(
    lambda row: make_movie_name(
        row["movieNm"],
        row["audiAcc"]
    ),
    axis=1
)


# --------------------------------------------------
# 선택한 날짜 표시
# --------------------------------------------------
display_date = selected_date.strftime("%Y년 %m월 %d일")

st.subheader(f"📅 {display_date} 박스오피스")


# --------------------------------------------------
# 1위 영화 정보
# --------------------------------------------------
first_movie = df.iloc[0]

st.markdown("## 🥇 1위 영화")

# 100만 명 이상이면 트로피가 붙은 영화명 사용
st.subheader(f"🎥 {first_movie['movieDisplay']}")


# --------------------------------------------------
# 지표 카드 3개
# --------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "👥 그날 관객수",
        f"{first_movie['audiCnt']:,}명"
    )

with col2:
    st.metric(
        "🎟️ 누적 관객수",
        f"{first_movie['audiAcc']:,}명"
    )

with col3:
    st.metric(
        "🎬 스크린수",
        f"{first_movie['scrnCnt']:,}개"
    )


st.divider()


# --------------------------------------------------
# 전체 박스오피스 표
# --------------------------------------------------
st.markdown("## 📋 전체 순위")


# 화면에 보여 줄 열 선택
display_df = df[
    [
        "rank",
        "rankChange",
        "movieDisplay",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# 열 이름을 한국어로 변경
display_df.columns = [
    "순위",
    "순위 변화",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# --------------------------------------------------
# 숫자를 보기 좋게 쉼표 형식으로 변경
# --------------------------------------------------
for column in [
    "관객수",
    "누적관객",
    "스크린수"
]:

    display_df[column] = display_df[column].map(
        lambda x: f"{x:,}"
    )


# 표 출력
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 관객수 상위 5편 막대그래프
# --------------------------------------------------
st.markdown("## 📊 관객수 상위 5편")


# 관객수 기준으로 내림차순 정렬
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
)


# 그래프에 사용할 데이터
chart_data = top5.set_index(
    "movieDisplay"
)["audiCnt"]


# 막대그래프 출력
st.bar_chart(chart_data)


# --------------------------------------------------
# 안내
# --------------------------------------------------
st.caption(
    "🔺 순위 상승 | "
    "🔽 순위 하락 | "
    "🏆 누적관객 100만 명 초과"
)


# --------------------------------------------------
# 하단 정보
# --------------------------------------------------
st.caption(
    f"조회 날짜: {target_date} | "
    "데이터 출처: KOBIS 영화관입장권통합전산망"
)
```
