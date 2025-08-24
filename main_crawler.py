import sys
import json
import os
import boto3
from datetime import datetime
from crawlers import warak_crawler
from crawlers.ddm_edu_crawler import DDMEducationCrawler


def main():
    results = {}

    # 1. 와락 크롤링
    try:
        warak_data = warak_crawler.crawl_warak_programs()
        results["warak"] = {
            "data": warak_data,
            "count": len(warak_data),
            "updated": datetime.now().isoformat(),
        }
    except Exception as e:
        results["warak"] = {"error": str(e)}

    # 2. 동대문구 교육지원센터 크롤링
    try:
        ddm_edu_crawler = DDMEducationCrawler()
        ddm_edu_data = ddm_edu_crawler.crawl_all()

        # 카테고리별 개수 집계
        summary = {}
        for key, value in ddm_edu_data.items():
            if isinstance(value, list):
                summary[key] = len(value)

        results["ddm_edu"] = {
            "data": ddm_edu_data,
            "summary": summary,
            "updated": ddm_edu_data.get("updated_at", datetime.now().isoformat()),
        }
    except Exception as e:
        results["ddm_edu"] = {"error": str(e)}

    # 3. 개별 파일로 저장
    for site_name, site_data in results.items():
        filename = f"{site_name}_programs.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(site_data, f, ensure_ascii=False, indent=2)

        # S3 업로드
        if "GITHUB_ACTIONS" in os.environ:
            s3 = boto3.client("s3")
            s3.upload_file(
                filename,
                "test-dondaemoon-school-20250822",
                f"dynamic_programs/{filename}",
            )
            print(f"{filename} S3 업로드 완료")


if __name__ == "__main__":
    main()
