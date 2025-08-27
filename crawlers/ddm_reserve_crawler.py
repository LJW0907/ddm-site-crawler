# crawlers/ddm_reserve_crawler.py

import time
from bs4 import BeautifulSoup
from datetime import datetime
import json
from urllib.parse import urljoin

# --- Selenium 관련 라이브러리 추가 ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


class DDMReserveCrawler:
    """동대문구 예약포털 크롤러 (전체프로그램 & 온라인접수 통합)"""

    def __init__(self):
        """크롤러 초기화. requests 세션 대신 헤더 정보만 유지"""
        self.base_url = "https://www.ddm.go.kr"
        # Selenium에서도 User-Agent는 중요하므로 헤더 정보는 유지합니다.
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        }
        # requests.Session 관련 코드는 제거합니다.
        # self.session = requests.Session()
        # self.session.headers.update(self.headers)

    def _get_soup(self, url, params=None):
        """
        [수정된 부분]
        Selenium을 사용해 BeautifulSoup 객체를 반환하는 헬퍼 함수.
        실제 브라우저를 구동하여 자바스크립트 렌더링과 봇 차단을 우회합니다.
        """
        driver = None  # driver 변수 초기화
        try:
            # Chrome 옵션 설정
            options = Options()
            options.add_argument("--headless")  # 브라우저 창을 띄우지 않는 옵션
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(
                f"user-agent={self.headers['User-Agent']}"
            )  # User-Agent 설정

            # ChromeDriver 자동 설치 및 서비스 실행
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)

            # 페이지 접속
            driver.get(url)

            # 페이지의 모든 콘텐츠(자바스크립트 포함)가 로드될 때까지 잠시 대기
            time.sleep(3)

            # 렌더링된 페이지의 HTML 소스를 가져옴
            html = driver.page_source

            # BeautifulSoup 객체로 변환하여 반환
            return BeautifulSoup(html, "lxml")

        except Exception as e:
            print(f"Error fetching {url} with Selenium: {e}")
            return None
        finally:
            # 드라이버가 성공적으로 생성되었을 경우에만 종료
            if driver:
                driver.quit()

    # ==================================================================
    # 아래의 파싱 및 실행 로직은 기존 코드와 동일합니다. (수정 없음)
    # ==================================================================

    def _parse_programs(self, soup, status):
        """'전체프로그램' 페이지의 목록을 파싱"""
        programs = []
        rows = soup.select("div.program.lecture tbody.text_center tr")

        if not rows:
            print(f"     -> 전체프로그램 {status}: 데이터 없음")
            return programs

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 8:
                continue

            title_tag = cells[1].find("a")
            status_tag = cells[7].find("a")

            date_cell_text = cells[3].get_text(separator="|").strip()
            date_parts = [p.strip() for p in date_cell_text.split("|") if p.strip()]

            application_period = date_parts[0] if date_parts else ""
            education_period = date_parts[1] if len(date_parts) > 1 else ""

            detail_url = ""
            if title_tag and "href" in title_tag.attrs:
                detail_url = urljoin(self.base_url, title_tag["href"])
            elif status_tag and "onclick" in status_tag.attrs:
                onclick = status_tag["onclick"]
                if "location.href" in onclick:
                    url_match = onclick.split("'")[1] if "'" in onclick else ""
                    if url_match:
                        detail_url = urljoin(self.base_url, url_match)

            program = {
                "title": title_tag.text.strip() if title_tag else "제목 없음",
                "location": cells[2].text.strip(),
                "application_period": application_period,
                "education_period": education_period,
                "education_time": cells[4].get_text(separator=" ", strip=True),
                "selection_method": cells[5].text.strip(),
                "capacity_status": cells[6].get_text(separator=" ", strip=True),
                "status": status,
                "button_text": status_tag.text.strip() if status_tag else "",
                "url": detail_url,
                "type": "전체프로그램",
                "source": "동대문구 예약포털",
                "crawled_at": datetime.now().isoformat(),
            }
            programs.append(program)

        print(f"     -> 전체프로그램 {status}: {len(programs)}개")
        return programs

    def _parse_online_receptions(self, soup, status):
        """'온라인접수' 페이지의 목록을 파싱"""
        receptions = []
        rows = soup.select("div.online_accept.list tbody.text_center tr")

        if not rows:
            print(f"     -> 온라인접수 {status}: 데이터 없음")
            return receptions

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 8:
                continue

            title_tag = cells[1].find("a")
            status_tag = cells[7].find("a")

            detail_url = ""
            if title_tag and "href" in title_tag.attrs:
                detail_url = urljoin(self.base_url, title_tag["href"])
            elif status_tag and "onclick" in status_tag.attrs:
                onclick = status_tag["onclick"]
                if "location.href" in onclick:
                    url_match = onclick.split("'")[1] if "'" in onclick else ""
                    if url_match:
                        detail_url = urljoin(self.base_url, url_match)

            reception = {
                "title": title_tag.text.strip() if title_tag else "제목 없음",
                "department": cells[2].text.strip(),
                "application_period": cells[3].get_text(separator="~", strip=True),
                "selection_method": cells[4].text.strip(),
                "capacity_status": cells[5]
                .get_text(separator="/", strip=True)
                .replace("\n", ""),
                "fee": cells[6].text.strip(),
                "status": status,
                "button_text": status_tag.text.strip() if status_tag else "",
                "url": detail_url,
                "type": "온라인접수",
                "source": "동대문구 예약포털",
                "crawled_at": datetime.now().isoformat(),
            }
            receptions.append(reception)

        print(f"     -> 온라인접수 {status}: {len(receptions)}개")
        return receptions

    def crawl_all(self):
        """모든 예약/접수 프로그램을 크롤링"""
        print("\n" + "=" * 50)
        print("   [동대문구 예약포털] 크롤링 시작")
        print("=" * 50 + "\n")

        all_results = []

        program_urls = {
            "접수예정": "https://www.ddm.go.kr/reserve/selectDongdaemunUserCourseList.do?searchEduInstSe=&key=1529&searchEdcKey=&searchEdcRealm=&searchTime=%EC%A0%91%EC%88%98%EA%B8%B0%EA%B0%84&timeBgnde=&timeEndde=&receptionStts=TBCCPT&searchCnd=SJ&searchKrwd=",
            "접수중": "https://www.ddm.go.kr/reserve/selectDongdaemunUserCourseList.do?searchEduInstSe=&key=1529&searchEdcKey=&searchEdcRealm=&searchTime=%EC%A0%91%EC%88%98%EA%B8%B0%EA%B0%84&timeBgnde=&timeEndde=&receptionStts=ACCPT&searchCnd=SJ&searchKrwd=",
        }

        print("1. [전체프로그램] 크롤링")
        for status, url in program_urls.items():
            print(f"   - {status} 페이지 로딩...")
            soup = self._get_soup(url)
            if soup:
                programs = self._parse_programs(soup, status)
                all_results.extend(programs)
            # Selenium은 자체적으로 로딩 시간이 있으므로 time.sleep()을 줄이거나 제거해도 됩니다.
            # time.sleep(1)

        reception_urls = {
            "접수예정": "https://www.ddm.go.kr/reserve/selectUserOnlineReceptionList.do?key=3133&searchCnd=TBCCPT",
            "접수중": "https://www.ddm.go.kr/reserve/selectUserOnlineReceptionList.do?key=3133&searchCnd=ACCPT",
        }

        print("\n2. [온라인접수] 크롤링")
        for status, url in reception_urls.items():
            print(f"   - {status} 페이지 로딩...")
            soup = self._get_soup(url)
            if soup:
                receptions = self._parse_online_receptions(soup, status)
                all_results.extend(receptions)
            # time.sleep(1)

        print(f"\n총 {len(all_results)}개의 예약/접수 정보를 수집했습니다.")
        return all_results


# --- 테스트 실행 코드 ---
if __name__ == "__main__":
    crawler = DDMReserveCrawler()
    crawled_data = crawler.crawl_all()

    output_filename = "ddm_reserve_test.json"
    result = {
        "data": crawled_data,
        "count": len(crawled_data),
        "updated_at": datetime.now().isoformat(),
        "crawl_info": {
            "source": "동대문구 예약포털",
            "categories": ["전체프로그램", "온라인접수"],
            "status": ["접수예정", "접수중"],
        },
    }

    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 결과가 '{output_filename}' 파일에 저장되었습니다.")

    if crawled_data:
        print("\n📋 수집된 데이터 샘플 (최대 5개):")
        print("-" * 50)
        for i, item in enumerate(crawled_data[:5], 1):
            print(f"\n[{i}] {item['title']}")
            print(f"    유형: {item['type']}")
            print(f"    상태: {item['status']}")
            if "application_period" in item:
                print(f"    접수기간: {item['application_period']}")
            if "department" in item:
                print(f"    담당부서: {item['department']}")
