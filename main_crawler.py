import sys
import json
import os
import boto3
from datetime import datetime
from crawlers import warak_crawling  # 올바른 import


def main():
    results = {}

    # 1. 와락 크롤링
    try:
        warak_data = warak_crawling.crawl_warak_programs()  # 함수명 수정
        results["warak"] = {
            "data": warak_data,
            "count": len(warak_data),
            "updated": datetime.now().isoformat(),
        }
    except Exception as e:
        results["warak"] = {"error": str(e)}

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
        print("S3 업로드 완료")


if __name__ == "__main__":
    main()
