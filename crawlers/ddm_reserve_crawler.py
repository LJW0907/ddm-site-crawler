# crawlers/ddm_reserve_crawler.py

import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
from urllib.parse import urljoin


class DDMReserveCrawler:
    """동대문구 예약포털 크롤러 (전체프로그램 & 온라인접수 통합)"""

    def __init__(self):
        self.base_url = "https://www.ddm.go.kr"
        # 실제 브라우저와 유사한 헤더 정보 추가
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _get_soup(self, url, params=None):
        """requests를 사용해 BeautifulSoup 객체를 반환하는 헬퍼 함수"""
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            response.encoding = "utf-8"  # 한글 인코딩 명시
            return BeautifulSoup(response.content, "lxml")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

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

            # 접수/교육 기간을 두 줄로 된 <p> 태그에서 추출
            date_cell_text = cells[3].get_text(separator="|").strip()
            date_parts = [p.strip() for p in date_cell_text.split("|") if p.strip()]

            application_period = date_parts[0] if date_parts else ""
            education_period = date_parts[1] if len(date_parts) > 1 else ""

            # 신청하기 버튼의 onclick에서 상세 URL 파라미터 추출
            detail_url = ""
            if title_tag and "href" in title_tag.attrs:
                detail_url = urljoin(self.base_url, title_tag["href"])
            elif status_tag and "onclick" in status_tag.attrs:
                # onclick에서 URL 파라미터 추출 시도
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
                "status": status,  # 접수예정/접수중 명시
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

            # 신청하기 버튼의 onclick에서 상세 URL 파라미터 추출
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
                "status": status,  # 접수예정/접수중 명시
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

        # 1. 전체프로그램 크롤링 (접수예정, 접수중) - URL 파라미터 추가
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
            time.sleep(1)  # 서버 부하 방지

        # 2. 온라인접수 크롤링 (접수예정, 접수중)
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
            time.sleep(1)  # 서버 부하 방지

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

    # 샘플 출력
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
