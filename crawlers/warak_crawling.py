import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from datetime import datetime
import json
import boto3
import os


# --- ★★★ 핵심 변경점: 여러 날짜를 모두 확인하도록 함수 강화 ★★★ ---
def is_program_in_future(title):
    """
    프로그램 제목에서 'M/D' 형식의 날짜를 '모두' 찾아,
    그 중 하나라도 미래의 날짜가 있으면 True를 반환합니다.
    """
    try:
        # 정규표현식으로 제목에 있는 '월/일' 패턴을 모두 찾습니다.
        # findall은 모든 결과를 리스트로 반환합니다. ex: [('8', '12'), ('8', '13')]
        matches = re.findall(r"(\d{1,2})/(\d{1,2})", title)

        if not matches:
            return True  # 날짜 정보가 없으면 일단 유효하다고 판단

        today = datetime.now().date()

        # 찾은 모든 날짜를 순회합니다.
        for month_str, day_str in matches:
            month = int(month_str)
            day = int(day_str)

            program_date = datetime(today.year, month, day).date()

            # 찾은 날짜 중 단 하나라도 오늘보다 미래라면,
            # 이 프로그램은 유효하므로 즉시 True를 반환하고 함수를 종료합니다.
            if program_date > today:
                return True

        # for 루프가 모두 끝날 때까지 True가 반환되지 않았다면,
        # 모든 날짜가 과거라는 의미이므로 최종적으로 False를 반환합니다.
        return False

    except ValueError:
        return True  # 날짜 변환 중 오류가 나면 일단 포함시킵니다.


def crawl_warak_programs():
    target_url = "https://www.ddmwarak.com/book-online?category=44962198-7cc6-4efd-83be-39d4dd7f08d8"

    # GitHub Actions 환경 체크
    if os.environ.get("GITHUB_ACTIONS"):
        # GitHub Actions용 설정
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        driver = webdriver.Chrome(options=options)  # Service 없이
    else:
        # 로컬 환경용 설정
        from webdriver_manager.chrome import ChromeDriverManager

        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(service=service, options=options)

    programs = []

    try:
        driver.get(target_url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.sVaQi4G")))

        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")

        program_items = soup.find_all("li", class_="sWsUGva")

        for item in program_items:
            button_tag = item.find("span", class_="sqQSaw2")
            status_text = button_tag.text.strip() if button_tag else ""

            if "예약" in status_text or "신청" in status_text:
                title_tag = item.find("h2", class_="sK8oMUK")
                title = title_tag.text.strip() if title_tag else "제목 없음"

                if is_program_in_future(title):
                    tag_line_tag = item.find("p", class_="sYCZueN")
                    duration_tag = item.find("p", class_="s__8v7Zit")
                    link_tag = item.find("a", class_="sk3GcZh")

                    tags = tag_line_tag.text.strip() if tag_line_tag else ""
                    duration = (
                        duration_tag.text.strip() if duration_tag else "시간 정보 없음"
                    )
                    link = (
                        link_tag["href"]
                        if link_tag and link_tag.has_attr("href")
                        else ""
                    )

                    programs.append(
                        {
                            "title": title,
                            "status": status_text,
                            "duration": duration,
                            "tags": tags,
                            "link": link,
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

    except Exception as e:
        print(
            "페이지 로딩 중 시간 초과 또는 오류 발생. 모집 중인 프로그램이 없거나 페이지 구조가 변경되었을 수 있습니다."
        )
    finally:
        driver.quit()

    return programs


# --- 실행 부분 ---
if __name__ == "__main__":
    print("동대문 와락 사이트에서 '미래 & 모집중'인 프로그램 정보를 크롤링합니다...")
    available_programs = crawl_warak_programs()

    if available_programs:
        print(
            f"✅ 성공! 총 {len(available_programs)}개의 유효한 프로그램을 찾았습니다."
        )

        # JSON 파일 저장
        with open("warak_programs.json", "w", encoding="utf-8") as f:
            json.dump(available_programs, f, ensure_ascii=False, indent=4)

        # S3 업로드 (GitHub Actions 환경에서만)
        if os.environ.get("GITHUB_ACTIONS"):
            s3 = boto3.client("s3")
            s3.upload_file(
                "warak_programs.json",
                "test-dondaemoon-school-20250822",
                "dynamic_programs/warak_programs.json",
            )
            print("S3 업로드 완료")
    else:
        print("❌ 현재 신청 가능한 미래의 프로그램이 없습니다.")
