# crawlers/ddm_news_crawler.py

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
import os


def crawl_ddm_news():
    """동대문구청 교육소식 게시판 크롤링"""
    BASE_URL = "https://www.ddm.go.kr/www/"
    URL_TEMPLATE = "https://www.ddm.go.kr/www/selectBbsNttList.do?key=575&bbsNo=38&searchCtgry=%ea%b5%90%ec%9c%a1&pageIndex={page}"

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

    # 크롤링 범위 설정: 지난달 1일
    today = datetime.now().date()
    first_day_of_current_month = today.replace(day=1)
    threshold_date = first_day_of_current_month - relativedelta(months=1)

    print("\n" + "=" * 50)
    print("   [동대문구청 교육소식] 크롤링 시작")
    print(f"   데이터 수집 범위: {threshold_date} 이후 게시물")
    print("=" * 50 + "\n")

    results = []
    page_index = 1
    stop_crawling = False
    consecutive_errors = 0

    try:
        while not stop_crawling and consecutive_errors < 3:
            target_url = URL_TEMPLATE.format(page=page_index)
            print(f"페이지 {page_index} 로딩 중...")

            try:
                driver.get(target_url)

                # tbody가 로드될 때까지 최대 10초 대기
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "tbody.text_center")
                    )
                )

                html = driver.page_source
                soup = BeautifulSoup(html, "lxml")

                notice_list = soup.select("tbody.text_center tr")

                if not notice_list:
                    print("게시물이 더 이상 없습니다. 크롤링을 종료합니다.")
                    break

                page_items = 0
                for notice in notice_list:
                    # 공지사항(img alt="공지")은 건너뛰기
                    if notice.find("img", alt="공지"):
                        continue

                    cells = notice.find_all("td")

                    # 테이블 구조 확인: 번호(0), 제목(1), 담당부서(2), 작성일(3), 첨부(4)
                    if len(cells) < 4:
                        continue

                    try:
                        # 날짜 추출 및 검증 - 수정된 부분
                        date_cell = cells[3]
                        date_text = date_cell.text.strip()

                        # "작성일" 텍스트 제거 및 공백 정리
                        date_text = date_text.replace("작성일", "").strip()
                        # 여러 줄 공백 제거
                        date_text = re.sub(r"\s+", " ", date_text).strip()

                        # 날짜 형식 매칭 (YYYY-MM-DD)
                        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
                        if not date_match:
                            print(f"날짜 형식 인식 실패: {repr(date_text)}")
                            continue

                        date_str = date_match.group(1)
                        post_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                        # 날짜가 기준일 이전이면 크롤링 중단
                        if post_date < threshold_date:
                            stop_crawling = True
                            print(
                                f"기준일({threshold_date}) 이전 게시물 발견. 크롤링 중단."
                            )
                            break

                        # 제목 및 URL 추출
                        title_cell = cells[1]
                        title_tag = title_cell.find("a")
                        if not title_tag:
                            continue

                        title = title_tag.text.strip()

                        # onclick 속성에서 nttNo 추출하여 실제 URL 생성
                        onclick = title_tag.get("onclick", "")
                        href = title_tag.get("href", "")

                        if onclick and "selectBbsNttView" in onclick:
                            # onclick에서 파라미터 추출
                            ntt_no_match = re.search(
                                r'nttNo["\s]*[:=]["\s]*(\d+)', onclick
                            )
                            if ntt_no_match:
                                ntt_no = ntt_no_match.group(1)
                                absolute_url = f"https://www.ddm.go.kr/www/selectBbsNttView.do?key=575&bbsNo=38&nttNo={ntt_no}"
                            else:
                                # onclick 파싱 실패시 기본 처리
                                absolute_url = (
                                    BASE_URL + "selectBbsNttList.do?key=575&bbsNo=38"
                                )
                        elif href and href != "#" and href != "javascript:void(0);":
                            # href가 유효한 경우
                            if href.startswith("http"):
                                absolute_url = href
                            else:
                                absolute_url = BASE_URL + href.lstrip("/")
                        else:
                            # URL 추출 실패
                            print(f"URL 추출 실패: {title}")
                            absolute_url = (
                                BASE_URL + "selectBbsNttList.do?key=575&bbsNo=38"
                            )

                        # 담당부서 추출
                        dept_cell = cells[2]
                        department = dept_cell.text.strip()

                        # 첨부파일 여부 확인
                        has_attachment = False
                        if len(cells) > 4:
                            attachment_cell = cells[4]
                            if (
                                attachment_cell.find("img")
                                or "첨부" in attachment_cell.text
                            ):
                                has_attachment = True

                        results.append(
                            {
                                "title": title,
                                "date": date_str,
                                "department": department,
                                "url": absolute_url,
                                "has_attachment": has_attachment,
                                "type": "교육소식",
                                "source": "동대문구청",
                                "crawled_at": datetime.now().isoformat(),
                            }
                        )
                        page_items += 1

                    except Exception as e:
                        print(f"항목 처리 중 오류: {e}")
                        continue

                print(f"  - 페이지 {page_index}: {page_items}개 항목 수집")

                if not stop_crawling and page_items > 0:
                    page_index += 1
                    consecutive_errors = 0
                    time.sleep(1)  # 페이지 간 1초 대기
                elif page_items == 0:
                    # 빈 페이지인 경우 종료
                    print("더 이상 게시물이 없습니다.")
                    break

            except Exception as e:
                print(f"페이지 {page_index} 처리 중 오류: {e}")
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    print("연속 오류 발생으로 크롤링 중단")
                    break
                time.sleep(2)  # 오류 발생시 2초 대기

    except Exception as e:
        print(f"크롤러 실행 중 치명적 오류: {e}")
    finally:
        driver.quit()

    print(f"\n총 {len(results)}개의 교육소식을 수집했습니다.")
    return results


# 테스트용 실행
if __name__ == "__main__":
    crawled_data = crawl_ddm_news()

    output_filename = "ddm_news_test.json"
    result = {
        "data": crawled_data,
        "count": len(crawled_data),
        "updated_at": datetime.now().isoformat(),
        "crawl_info": {
            "source": "동대문구청 교육소식",
            "url": "https://www.ddm.go.kr/www/selectBbsNttList.do?key=575&bbsNo=38&searchCtgry=교육",
        },
    }

    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 결과가 '{output_filename}' 파일에 저장되었습니다.")

    # 샘플 출력
    if crawled_data:
        print("\n📋 수집된 데이터 샘플 (최대 5개):")
        print("-" * 50)
        for i, item in enumerate(crawled_data[:5], 1):
            print(f"\n[{i}] {item['title']}")
            print(f"    날짜: {item['date']}")
            print(f"    부서: {item['department']}")
            print(f"    첨부: {'있음' if item.get('has_attachment') else '없음'}")
            print(f"    URL: {item['url'][:60]}...")
