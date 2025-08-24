import sys
import json
import os
import boto3
from datetime import datetime
from crawlers import warak_crawler  # 이름 변경


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

    # 각 사이트별로 개별 파일 저장
    for site_name, site_data in results.items():
        filename = f"{site_name}_programs.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(site_data, f, ensure_ascii=False, indent=2)

        # S3에도 개별 업로드
        if "GITHUB_ACTIONS" in os.environ:
            s3 = boto3.client("s3")
            s3.upload_file(
                filename,
                "test-dondaemoon-school-20250822",
                f"dynamic_programs/{filename}",  # warak_programs.json으로 저장됨
            )
            print(f"{filename} S3 업로드 완료")


if __name__ == "__main__":
    main()
