# crawlers/ddm_edu_crawler.py
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
from dateutil.relativedelta import relativedelta
import os


class DDMEducationCrawler:
    """동대문구 교육지원센터 규칙별 맞춤 크롤러"""

    def __init__(self):
        self.base_url = "https://www.ddm.go.kr"
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.today = datetime.now().date()
        # 미래 이벤트만 수집
        self.date_threshold = self.today

    def _is_future_event(self, date_string):
        """미래 이벤트만 필터링"""
        # YYYY-MM-DD 형식
        dates_found_ymd = re.findall(r"(\d{4})-(\d{2})-(\d{2})", date_string)
        if dates_found_ymd:
            try:
                last_date_str = "-".join(dates_found_ymd[-1])
                event_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
                return event_date >= self.today
            except ValueError:
                return True

        # 한글 날짜 형식: "7월 29일(화), 7월 31일(목)" 처리
        korean_dates = re.findall(r"(\d{1,2})월\s*(\d{1,2})일", date_string)
        if korean_dates:
            try:
                month, day = map(int, korean_dates[-1])
                event_date = datetime(self.today.year, month, day).date()

                # 날짜가 과거이고 12월이면 작년일 가능성
                if event_date < self.today and month >= 11:
                    event_date = datetime(self.today.year - 1, month, day).date()
                # 날짜가 미래이고 1-2월이면 내년일 가능성
                elif event_date > self.today and month <= 2:
                    if self.today.month >= 7:
                        event_date = datetime(self.today.year + 1, month, day).date()

                return event_date >= self.today
            except ValueError:
                return True

        # M/D 형식 (예: 8/13)
        dates_found_md = re.findall(r"(\d{1,2})/(\d{1,2})", date_string)
        if dates_found_md:
            try:
                month, day = map(int, dates_found_md[-1])
                event_date = datetime(self.today.year, month, day).date()
                return event_date >= self.today
            except ValueError:
                return True

        return True  # 날짜 정보가 없으면 포함

    def _crawl_sorted_board(self, params, parser_func, content_type):
        """날짜 순으로 정렬된 게시판을 크롤링"""
        print(f"-> '{content_type}' (정렬) 크롤링 시작...")

        items = []
        page = 1
        max_pages = 5

        while page <= max_pages:
            params["pageIndex"] = page
            url = f"{self.base_url}{params.pop('url_path', '/jinhak/selectBbsNttList.do')}"
            try:
                response = requests.get(url, params=params, headers=self.headers)
                soup = BeautifulSoup(response.content, "lxml")
                rows = soup.select("table.p-table tbody tr")

                if not rows:
                    break

                stop_for_this_board = False
                for row in rows:
                    item, is_valid_date = parser_func(row, content_type)
                    if not item:
                        continue
                    if not is_valid_date:
                        stop_for_this_board = True
                        break
                    else:
                        items.append(item)

                if stop_for_this_board:
                    break
                if not soup.select_one("strong.active + a.p-page__link"):
                    break
                page += 1
            except Exception as e:
                print(f"Error in _crawl_sorted_board for {content_type}: {e}")
                break

        print(f"   -> {len(items)}개 항목 수집 완료")
        return items

    def _crawl_unsorted_board(self, params, parser_func, content_type):
        """정렬되지 않은 게시판은 전부 크롤링 후 날짜 필터링"""
        print(f"-> '{content_type}' (미정렬) 크롤링 시작...")

        all_items = []
        page = 1
        max_pages = 5

        while page <= max_pages:
            params["pageIndex"] = page
            url = f"{self.base_url}/jinhak/selectBbsNttList.do"
            try:
                response = requests.get(url, params=params, headers=self.headers)
                soup = BeautifulSoup(response.content, "lxml")
                rows = soup.select("table.p-table tbody tr")

                if not rows:
                    break

                for row in rows:
                    item, _ = parser_func(row, content_type)
                    if item:
                        all_items.append(item)

                if not soup.select_one("strong.active + a.p-page__link"):
                    break
                page += 1
            except Exception as e:
                print(f"Error in _crawl_unsorted_board for {content_type}: {e}")
                break

        # 날짜 필터링
        filtered_items = [
            item for item in all_items if self._is_future_event(item.get("date", ""))
        ]

        print(f"   -> {len(filtered_items)}개 항목 수집 완료 (전체: {len(all_items)})")
        return filtered_items

    def _crawl_notices(self, params, parser_func, content_type):
        """공지사항은 작성일 기준으로 크롤링"""
        print(f"-> '{content_type}' (공지) 크롤링 시작...")

        months_ago = self.today - relativedelta(months=2)
        start_date = months_ago.replace(day=1)
        items = []
        page = 1
        max_pages = 5

        while page <= max_pages:
            params["pageIndex"] = page
            url = f"{self.base_url}/jinhak/selectBbsNttList.do"
            try:
                response = requests.get(url, params=params, headers=self.headers)
                soup = BeautifulSoup(response.content, "lxml")
                rows = soup.select("table.p-table tbody tr")
                if not rows:
                    break

                stop_for_this_board = False
                for row in rows:
                    item, post_date_str = parser_func(row, content_type)
                    if not item:
                        continue

                    post_date = datetime.strptime(post_date_str, "%Y-%m-%d").date()
                    if post_date < start_date:
                        stop_for_this_board = True
                        break
                    else:
                        items.append(item)

                if stop_for_this_board:
                    break
                if not soup.select_one("strong.active + a.p-page__link"):
                    break
                page += 1
            except Exception as e:
                print(f"Error in _crawl_notices for {content_type}: {e}")
                break

        print(f"   -> {len(items)}개 항목 수집 완료")
        return items

    def _parse_board_row(self, row, content_type):
        cols = row.find_all("td")
        if len(cols) != 7:
            return None, None
        event_date_str = cols[2].text.strip()
        is_valid = self._is_future_event(event_date_str)

        apply_button = cols[6].find("a")
        title_tag = cols[1].find("a")
        item = {
            "title": title_tag.text.strip() if title_tag else cols[1].text.strip(),
            "date": event_date_str,
            "target": cols[4].text.strip(),
            "location": cols[5].text.strip(),
            "status": apply_button.text.strip() if apply_button else "마감",
            "url": self.base_url
            + (
                apply_button["href"]
                if apply_button and apply_button.has_attr("href")
                else title_tag.get("href", "")
            ),
            "type": content_type,
        }
        return item, is_valid

    def _parse_expo_row(self, row, content_type):
        cols = row.find_all("td")
        if len(cols) != 5:
            return None, None
        registration_period_str = cols[3].text.strip()
        is_valid = self._is_future_event(registration_period_str)

        apply_button = cols[4].find("a")
        title_tag = cols[1].find("a")
        item = {
            "title": title_tag.text.strip() if title_tag else cols[1].text.strip(),
            "event_period": cols[2].text.strip(),
            "registration_period": registration_period_str,
            "status": apply_button.text.strip() if apply_button else "마감",
            "url": self.base_url
            + (
                apply_button["href"]
                if apply_button and apply_button.has_attr("href")
                else title_tag.get("href", "")
            ),
            "type": content_type,
        }
        return item, is_valid

    def _parse_notice_row(self, row, content_type):
        cols = row.find_all("td")
        if len(cols) != 5:
            return None, None
        title_tag = cols[1].find("a")
        date_str = cols[3].text.strip()
        item = {
            "title": title_tag.text.strip() if title_tag else cols[1].text.strip(),
            "date": date_str,
            "url": self.base_url + (title_tag.get("href", "") if title_tag else ""),
            "type": content_type,
        }
        return item, date_str


def crawl_all(self):
    """모든 섹션을 규칙에 맞게 크롤링"""
    results = {
        "notices": self._crawl_notices(
            {"bbsNo": "175", "key": "3646"}, self._parse_notice_row, "공지사항"
        ),
        "expo_university": self._crawl_sorted_board(
            {
                "key": "3634",
                "expoTypeNo": "7",
                "url_path": "/jinhak/selectUserExpoList.do",
            },
            self._parse_expo_row,
            "대입수시박람회",
        ),
        "camps": self._crawl_sorted_board(
            {"bbsNo": "332", "key": "3622"}, self._parse_board_row, "방학캠프"
        ),
        "parent_programs": self._crawl_sorted_board(
            {"bbsNo": "333", "key": "3623"}, self._parse_board_row, "학부모역량강화"
        ),
        "expo_college": self._crawl_sorted_board(
            {
                "key": "3635",
                "expoTypeNo": "2",
                "url_path": "/jinhak/selectUserExpoList.do",
            },
            self._parse_expo_row,
            "전문대학정보박람회",
        ),
        "expo_highschool": self._crawl_sorted_board(
            {
                "key": "3636",
                "expoTypeNo": "1",
                "url_path": "/jinhak/selectUserExpoList.do",
            },
            self._parse_expo_row,
            "고교입학박람회",
        ),
        "parent_lectures": self._crawl_unsorted_board(
            {"bbsNo": "345", "key": "3632"}, self._parse_board_row, "학부모진학교실"
        ),
    }
    results["updated_at"] = datetime.now().isoformat()
    # self.test_mode 제거!
    # results["test_mode"] = self.test_mode  ← 이 줄 삭제
    return results


# --- 테스트 실행 코드 ---
if __name__ == "__main__":
    crawler = DDMEducationCrawler()
    all_crawled_data = crawler.crawl_all()

    print("\n" + "=" * 30)
    print("      크롤링 결과 요약")
    print("=" * 30)
    for category, data in all_crawled_data.items():
        if isinstance(data, list):
            print(f"- {category}: {len(data)}개")
    print("=" * 30)

    output_filename = "ddm_education_center_all.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(all_crawled_data, f, ensure_ascii=False, indent=4)

    print(f"\n✅ 전체 결과가 '{output_filename}' 파일에 저장되었습니다.")
