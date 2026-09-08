# main.py
# 초보자용 KOBIS 일별 박스오피스 앱
#
# 필요한 것:
# 1. Streamlit Cloud의 Secrets에 KOBIS_KEY를 등록해야 합니다.
# 2. API 키는 코드에 직접 쓰지 않습니다.
#
# Secrets 예시:
# KOBIS_KEY = "발급받은_API_키"

import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일별 박스오피스")


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 계산하기
# --------------------------------------------------
# Streamlit Cloud 서버의 시간이 한국 시간이 아닐 수 있으므로
# 서버의 현재 시간을 그대로 사용하지 않고 한국 시간(KST)을 사용합니다.

KST = ZoneInfo("Asia/Seoul")

now_korea = datetime.now(KST)
yesterday = now_korea.date() - timedelta(days=1)

# KOBIS가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여 줄 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 3. KOBIS API 주소
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# --------------------------------------------------
# 4. Secrets에서 API 인증키 가져오기
# --------------------------------------------------
# API 키를 코드에 직접 적지 않습니다.
# Streamlit Cloud의 Secrets에 KOBIS_KEY를 저장해 두세요.

try:
    KOBIS_KEY = st.secrets["KOBIS_KEY"]
except Exception:
    st.error(
        "🔑 KOBIS API 인증키를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 **Settings → Secrets**에서 "
        "`KOBIS_KEY`가 등록되어 있는지 확인해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 5. KOBIS API 호출 함수
# --------------------------------------------------
# 같은 날짜를 다시 조회하면 1시간 동안 저장해 둔 결과를 사용합니다.
# 따라서 페이지를 다시 실행해도 API를 매번 호출하지 않습니다.

@st.cache_data(ttl=3600)
def get_box_office(api_key, date_string):
    """KOBIS에서 해당 날짜의 일별 박스오피스를 가져옵니다."""

    params = {
        "key": api_key,
        "targetDt": date_string,
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 상태 코드가 200이 아니면 오류로 처리합니다.
        response.raise_for_status()

        # JSON으로 변환합니다.
        data = response.json()

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": (
                "⏱️ KOBIS API 응답 시간이 너무 깁니다.\n\n"
                "인터넷 연결 상태나 KOBIS 서버 상태를 확인한 뒤 "
                "잠시 후 다시 시도해 주세요."
            ),
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "🌐 KOBIS API 요청에 실패했습니다.\n\n"
                "인터넷 연결, KOBIS API 주소, KOBIS 서버 상태를 "
                "확인해 주세요.\n\n"
                f"오류 내용: {e}"
            ),
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "📦 KOBIS에서 정상적인 JSON 응답을 받지 못했습니다.\n\n"
                "KOBIS API 서버의 응답 상태를 확인해 주세요."
            ),
        }

    # --------------------------------------------------
    # 6. 인증키 오류 확인
    # --------------------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 이 경우 faultInfo가 응답에 들어옵니다.

    if "faultInfo" in data:
        fault = data["faultInfo"]

        fault_code = fault.get("errorCode", "알 수 없음")
        fault_message = fault.get(
            "message",
            "KOBIS API에서 오류가 발생했습니다.",
        )

        return {
            "success": False,
            "message": (
                "🔑 KOBIS API 인증에 실패했습니다.\n\n"
                "다음을 확인해 주세요.\n"
                "1. Streamlit Cloud의 Secrets에 `KOBIS_KEY`가 있는지\n"
                "2. 인증키를 정확하게 입력했는지\n"
                "3. 인증키가 유효한지\n\n"
                f"오류 코드: {fault_code}\n\n"
                f"오류 메시지: {fault_message}"
            ),
        }

    # --------------------------------------------------
    # 7. 예상한 응답 구조인지 확인
    # --------------------------------------------------

    box_office_result = data.get("boxOfficeResult")

    if not box_office_result:
        return {
            "success": False,
            "message": (
                "📦 KOBIS 응답에서 `boxOfficeResult`를 찾지 못했습니다.\n\n"
                "KOBIS API 응답 형식이 정상인지 확인해 주세요."
            ),
        }

    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "message": (
                f"📭 {date_string[:4]}년 {date_string[4:6]}월 "
                f"{date_string[6:]}일의 영화 목록이 없습니다.\n\n"
                "아직 해당 날짜의 박스오피스가 집계되지 않았거나 "
                "KOBIS에서 데이터를 제공하지 않는 날짜일 수 있습니다.\n\n"
                "조회 날짜와 KOBIS 서비스 상태를 확인해 주세요."
            ),
        }

    # --------------------------------------------------
    # 8. 숫자 데이터를 실제 숫자로 변환
    # --------------------------------------------------
    # KOBIS API에서는 rank, audiCnt, audiAcc, scrnCnt 등이
    # 문자열로 오기 때문에 숫자로 바꿉니다.

    movies = []

    for movie in movie_list:
        try:
            movie_data = {
                "순위": int(movie.get("rank", 0)),
                "영화명": movie.get("movieNm", ""),
                "개봉일": movie.get("openDt", ""),
                "관객수": int(movie.get("audiCnt", 0)),
                "누적관객": int(movie.get("audiAcc", 0)),
                "스크린수": int(movie.get("scrnCnt", 0)),
            }

            movies.append(movie_data)

        except (ValueError, TypeError):
            # 숫자로 변환할 수 없는 영화 데이터가 있으면
            # 해당 데이터는 건너뜁니다.
            continue

    if not movies:
        return {
            "success": False,
            "message": (
                "⚠️ 영화 데이터는 받았지만 숫자 데이터를 정상적으로 "
                "변환하지 못했습니다.\n\n"
                "KOBIS API 응답 내용을 확인해 주세요."
            ),
        }

    return {
        "success": True,
        "movies": movies,
    }


# --------------------------------------------------
# 9. API 호출
# --------------------------------------------------

result = get_box_office(KOBIS_KEY, target_date)


# --------------------------------------------------
# 10. 오류가 발생했으면 안내하고 종료
# --------------------------------------------------

if not result.get("success", False):
    st.warning(result["message"])
    st.stop()


movies = result["movies"]


# --------------------------------------------------
# 11. 조회 날짜 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")


# --------------------------------------------------
# 12. 1위 영화 지표 카드
# --------------------------------------------------

first_movie = movies[0]

st.markdown(f"### 🏆 1위: {first_movie['영화명']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="오늘의 관객수",
        value=f"{first_movie['관객수']:,}명",
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['누적관객']:,}명",
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['스크린수']:,}개",
    )


# --------------------------------------------------
# 13. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬합니다.
top5 = sorted(
    movies,
    key=lambda movie: movie["관객수"],
    reverse=True,
)[:5]

# Streamlit의 bar_chart에 사용할 데이터 형태를 만듭니다.
chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top5
}

st.bar_chart(chart_data)


# --------------------------------------------------
# 14. 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎞️ 전체 순위")

# 표에 표시할 데이터입니다.
table_data = []

for movie in movies:
    table_data.append(
        {
            "순위": movie["순위"],
            "영화명": movie["영화명"],
            "개봉일": movie["개봉일"],
            "관객수": movie["관객수"],
            "누적관객": movie["누적관객"],
            "스크린수": movie["스크린수"],
        }
    )

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d위",
        ),
        "영화명": st.column_config.TextColumn(
            "영화명",
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%,d명",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%,d명",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%,d개",
        ),
    },
)


# --------------------------------------------------
# 15. 데이터 출처 안내
# --------------------------------------------------

st.caption(
    "※ 데이터 출처: 영화진흥위원회(KOBIS) 일별 박스오피스 API"
)
st.caption(
    "※ 같은 날짜의 API 결과는 약 1시간 동안 캐시됩니다."
)
