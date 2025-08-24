# crawlers/ddm_edu_crawler.py
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
from dateutil.relativedelta import relativedelta


class DDMEducationCrawler:
    """동대문구 교육지원센터 규칙별 맞춤 크롤러"""

    def __init__(self):
        self.base_url = "https://www.ddm.go.kr"
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.today = datetime.now().date()

    def _is_future_event(self, date_string):
        """'YYYY-MM-DD' 또는 'M월 D일' 등 다양한 날짜 형식을 분석해,
        기간의 종료일이 오늘이거나 미래인 경우 True를 반환"""
        dates_found_ymd = re.findall(r"(\d{4})-(\d{2})-(\d{2})", date_string)
        if dates_found_ymd:
            try:
                last_date_str = "-".join(dates_found_ymd[-1])
                event_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
                return event_date >= self.today
            except ValueError:
                return True

        dates_found_md = re.findall(r"(\d{1,2})월 (\d{1,2})일", date_string)
        if dates_found_md:
            try:
                month, day = map(int, dates_found_md[-1])
                event_date = datetime(self.today.year, month, day).date()
                return event_date >= self.today
            except ValueError:
                return True
        return True

    def _crawl_sorted_board(self, params, parser_func, content_type):
        """날짜 순으로 정렬된 게시판을 크롤링하고, 날짜가 지나면 중단"""
        print(f"-> '{content_type}' (정렬) 크롤링 시작...")
        items = []
        page = 1
        while True:
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
                    items.append(item)

                if stop_for_this_board:
                    break
                if not soup.select_one("strong.active + a.p-page__link"):
                    break
                page += 1
            except Exception as e:
                print(f"Error in _crawl_sorted_board for {content_type}: {e}")
                break
        return items

    def _crawl_unsorted_board(self, params, parser_func, content_type):
        """정렬되지 않은 게시판은 전부 크롤링 후 날짜 필터링"""
        print(f"-> '{content_type}' (미정렬) 크롤링 시작...")
        all_items = []
        page = 1
        while True:
            params["pageIndex"] = page
            url = f"{self.base_url}/jinhak/selectBbsNttList.do"
            try:
                response = requests.get(url, params=params, headers=self.headers)
                soup = BeautifulSoup(response.content, "lxml")
                rows = soup.select("table.p-table tbody tr")

                if not rows:
                    break

                for row in rows:
                    item, _ = parser_func(row, content_type)  # is_valid_date는 무시
                    if item:
                        all_items.append(item)

                if not soup.select_one("strong.active + a.p-page__link"):
                    break
                page += 1
            except Exception as e:
                print(f"Error in _crawl_unsorted_board for {content_type}: {e}")
                break

        # 모든 페이지를 다 읽은 후, 날짜가 지난 항목을 걸러냄
        return [
            item for item in all_items if self._is_future_event(item.get("date", ""))
        ]

    def _crawl_notices(self, params, parser_func, content_type):
        """공지사항은 작성일 기준으로 2달 전까지 크롤링"""
        print(f"-> '{content_type}' (공지) 크롤링 시작...")
        two_months_ago = self.today - relativedelta(months=2)
        start_date = two_months_ago.replace(day=1)
        items = []
        page = 1
        while True:
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
                    items.append(item)

                if stop_for_this_board:
                    break
                if not soup.select_one("strong.active + a.p-page__link"):
                    break
                page += 1
            except Exception as e:
                print(f"Error in _crawl_notices for {content_type}: {e}")
                break
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
        is_valid = self._is_period_valid(registration_period_str)

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
