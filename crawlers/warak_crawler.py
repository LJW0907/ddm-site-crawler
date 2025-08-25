# crawlers/warak_crawler.py
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
import boto3
import os


def is_program_valid(title, test_mode=False, prev_month=None):
    """
    프로그램의 유효성을 판단합니다.

    와락 특징: 신청일 내림차순 정렬
    - 월이 갑자기 커지면 작년 데이터

    테스트 모드: 3개월 전까지의 프로그램도 포함
    일반 모드: 미래 프로그램만 포함
    """
    try:
        # M/D 형식 날짜 찾기
        matches = re.findall(r"(\d{1,2})/(\d{1,2})", title)

        if not matches:
            return True, None  # 날짜 없으면 포함, 월 정보 없음

        # 첫 번째 날짜만 확인 (주로 시작일)
        month = int(matches[0][0])
        day = int(matches[0][1])

        today = datetime.now().date()
        current_year = today.year

        # 내림차순 정렬 체크: 이전 월보다 크면 작년
        if prev_month is not None and month > prev_month:
            current_year -= 1

        try:
            program_date = datetime(current_year, month, day).date()
        except ValueError:
            return True, month  # 날짜 변환 실패시 포함

        # 테스트 모드: 3개월 전까지 OK
        if test_mode:
            threshold = today - relativedelta(months=3)
            return program_date >= threshold, month
        else:
            # 일반 모드: 오늘 이후만 OK
            return program_date >= today, month

    except Exception:
        return True, None


def crawl_warak_programs():
    """와락 센터 프로그램 크롤링"""
    target_url = "https://www.ddmwarak.com/book-online?category=44962198-7cc6-4efd-83be-39d4dd7f08d8"

    # GitHub Actions 환경 체크
    if os.environ.get("GITHUB_ACTIONS"):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        driver = webdriver.Chrome(options=options)
    else:
        # 로컬 환경용 설정
        from webdriver_manager.chrome import ChromeDriverManager

        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(service=service, options=options)

    programs = []

    try:
        print("페이지 로딩 중...")
        driver.get(target_url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.sVaQi4G")))

        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")

        program_items = soup.find_all("li", class_="sWsUGva")
        print(f"발견된 프로그램 수: {len(program_items)}개")

        today = datetime.now().date()

        for item in program_items:
            button_tag = item.find("span", class_="sqQSaw2")
            status_text = button_tag.text.strip() if button_tag else ""

            # 예약/신청 가능한 것만
            if "예약" in status_text or "신청" in status_text:
                title_tag = item.find("h2", class_="sK8oMUK")
                title = title_tag.text.strip() if title_tag else "제목 없음"

                # 날짜 추출 및 필터링
                date_match = re.search(r"(\d{1,2})/(\d{1,2})", title)
                if date_match:
                    month = int(date_match.group(1))
                    day = int(date_match.group(2))
                    year = today.year

                    try:
                        program_date = datetime(year, month, day).date()
                        # 미래 날짜만
                        if program_date < today:
                            continue
                        date_str = program_date.strftime("%Y-%m-%d")
                    except ValueError:
                        date_str = None
                else:
                    date_str = None

                tag_line_tag = item.find("p", class_="sYCZueN")
                duration_tag = item.find("p", class_="s__8v7Zit")
                link_tag = item.find("a", class_="sk3GcZh")

                programs.append(
                    {
                        "title": title,
                        "status": status_text if status_text else "상태 미상",
                        "duration": (
                            duration_tag.text.strip()
                            if duration_tag
                            else "시간 정보 없음"
                        ),
                        "tags": tag_line_tag.text.strip() if tag_line_tag else "",
                        "link": (
                            link_tag["href"]
                            if link_tag and link_tag.has_attr("href")
                            else ""
                        ),
                        "date": date_str,
                        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

        print(f"수집된 프로그램: {len(programs)}개")

    except Exception as e:
        print(f"오류 발생: {str(e)}")
        print("페이지 로딩 중 시간 초과 또는 오류 발생")
    finally:
        driver.quit()

    return programs


# 테스트 실행 코드 - main 함수 안이 아닌 __main__ 부분
if __name__ == "__main__":
    programs = crawl_warak_programs()

    print("\n" + "=" * 30)
    print("      크롤링 결과")
    print("=" * 30)
    print(f"수집된 프로그램 수: {len(programs)}개")

    # 결과 파일 저장
    output_filename = "warak_programs.json"  # _test 제거
    result = {
        "data": programs,
        "count": len(programs),
        "updated": datetime.now().isoformat(),
        # "test_mode": 제거
    }

    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 결과가 '{output_filename}' 파일에 저장되었습니다.")

    # 샘플 출력
    if programs:
        print("\n샘플 (최대 3개):")
        for i, program in enumerate(programs[:3]):
            print(f"\n{i+1}. {program['title']}")
            print(f"   상태: {program['status']}")
            print(f"   날짜: {program.get('date', '날짜 정보 없음')}")
            print(f"   시간: {program['duration']}")
