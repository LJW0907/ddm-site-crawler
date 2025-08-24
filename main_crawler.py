import sys
import json
import os
import boto3
from datetime import datetime
from crawlers import warak_crawling


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

    # 2. 추후 다른 사이트 추가
    # results['other_site'] = other_crawler.crawl()

    # 통합 결과 저장
    with open("all_programs.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # S3 업로드
    if "GITHUB_ACTIONS" in os.environ:
        s3 = boto3.client("s3")
        s3.upload_file(
            "all_programs.json",
            "test-dondaemoon-school-20250822",
            "dynamic_programs/all_programs.json",
        )


if __name__ == "__main__":
    main()
