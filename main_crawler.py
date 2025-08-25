# main_crawler.py
import sys
import json
import os
import boto3
from datetime import datetime
from crawlers import warak_crawler
from crawlers.ddm_edu_crawler import DDMEducationCrawler


def main():
    # 테스트 모드 확인 (set CRAWLER_TEST_MODE=true or false)
    test_mode = os.environ.get("CRAWLER_TEST_MODE", "false").lower() == "true"

    if test_mode:
        print("\n" + "=" * 60)
        print("          전체 크롤러 실행 - 테스트 모드")
        print("          (3개월 범위 데이터 수집)")
        print("=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print("          전체 크롤러 실행 - 일반 모드")
        print("=" * 60 + "\n")

    results = {}

    # 1. 와락 크롤링
    print("\n[1/2] 와락 센터 크롤링 시작...")
    print("-" * 40)
    try:
        warak_data = warak_crawler.crawl_warak_programs()
        results["warak"] = {
            "data": warak_data,
            "count": len(warak_data),
            "updated": datetime.now().isoformat(),
            "test_mode": test_mode,
        }
        print(f"✅ 와락 크롤링 완료: {len(warak_data)}개 프로그램")
    except Exception as e:
        results["warak"] = {"error": str(e), "test_mode": test_mode}
        print(f"❌ 와락 크롤링 실패: {str(e)}")

    # 2. 동대문구 교육지원센터 크롤링
    print("\n[2/2] 교육지원센터 크롤링 시작...")
    print("-" * 40)
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
            "test_mode": test_mode,
        }

        print(f"✅ 교육지원센터 크롤링 완료:")
        for category, count in summary.items():
            print(f"   - {category}: {count}개")

    except Exception as e:
        results["ddm_edu"] = {"error": str(e), "test_mode": test_mode}
        print(f"❌ 교육지원센터 크롤링 실패: {str(e)}")

    # 3. 개별 파일로 저장
    print("\n" + "=" * 60)
    print("          결과 저장")
    print("=" * 60)

    for site_name, site_data in results.items():
        if test_mode:
            filename = f"{site_name}_programs_test.json"
        else:
            filename = f"{site_name}_programs.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(site_data, f, ensure_ascii=False, indent=2)
        print(f"📁 {filename} 저장 완료")

        # S3 업로드 (GitHub Actions 환경에서만)
        if "GITHUB_ACTIONS" in os.environ:
            try:
                s3 = boto3.client("s3")
                s3_key = f"dynamic_programs/{filename}"
                s3.upload_file(filename, "test-dondaemoon-school-20250822", s3_key)
                print(f"☁️  S3 업로드 완료: {s3_key}")
            except Exception as e:
                print(f"⚠️  S3 업로드 실패: {str(e)}")

    # 4. 최종 요약
    print("\n" + "=" * 60)
    print("          크롤링 완료 요약")
    print("=" * 60)

    total_count = 0
    for site_name, site_data in results.items():
        if "error" not in site_data:
            if site_name == "warak":
                count = site_data.get("count", 0)
                print(f"• {site_name}: {count}개 프로그램")
                total_count += count
            elif site_name == "ddm_edu":
                summary = site_data.get("summary", {})
                site_total = sum(summary.values())
                print(f"• {site_name}: {site_total}개 항목")
                for category, count in summary.items():
                    print(f"  - {category}: {count}개")
                total_count += site_total
        else:
            print(f"• {site_name}: 오류 발생")

    print(f"\n총 {total_count}개 항목 수집")

    if test_mode:
        print("\n⚠️  테스트 모드로 실행됨 (3개월 범위 데이터)")

    print("=" * 60)


if __name__ == "__main__":
    main()
