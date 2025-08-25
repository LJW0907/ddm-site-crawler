# main_crawler.py

import json
from datetime import datetime
from crawlers.warak_crawler import crawl_warak_programs
from crawlers.ddm_edu_crawler import DDMEducationCrawler
from crawlers.ddm_news_crawler import crawl_ddm_news
from crawlers.ddm_reserve_crawler import DDMReserveCrawler
import boto3
import os


def upload_to_s3(data, key, bucket_name="test-dondaemoon-school-20250822"):
    """S3에 데이터 업로드"""
    s3_client = boto3.client("s3")

    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"✅ S3 업로드 성공: {key}")
        return True
    except Exception as e:
        print(f"❌ S3 업로드 실패 ({key}): {e}")
        return False


def main():
    """모든 크롤러 실행 및 S3 업로드"""
    print("\n" + "=" * 60)
    print("   동대문구 교육정보 통합 크롤링 시작")
    print("   시작 시간:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    results = {}

    # 1. 와락 프로그램 크롤링
    print("\n[1/4] 와락센터 프로그램 크롤링...")
    try:
        warak_data = crawl_warak_programs()
        results["warak"] = {
            "count": len(warak_data) if warak_data else 0,
            "status": "success",
        }

        # 빈 데이터여도 업로드
        upload_data = {
            "data": warak_data if warak_data else [],
            "count": len(warak_data) if warak_data else 0,
            "updated_at": datetime.now().isoformat(),
        }
        upload_to_s3(upload_data, "dynamic_programs/warak_programs.json")

    except Exception as e:
        print(f"❌ 와락 크롤링 실패: {e}")
        results["warak"] = {"status": "failed", "error": str(e)}
        # 실패해도 빈 파일 업로드
        upload_data = {
            "data": [],
            "count": 0,
            "updated_at": datetime.now().isoformat(),
            "error": str(e),
        }
        upload_to_s3(upload_data, "dynamic_programs/warak_programs.json")

    # 2. 교육지원센터 크롤링
    print("\n[2/4] 교육지원센터 크롤링...")
    try:
        edu_crawler = DDMEducationCrawler()
        ddm_edu_data = edu_crawler.crawl_all()

        # 각 카테고리별 개수 계산
        edu_count = 0
        for key, value in ddm_edu_data.items():
            if isinstance(value, list):
                edu_count += len(value)

        results["ddm_edu"] = {
            "count": edu_count,
            "status": "success",
        }

        # 빈 데이터여도 업로드
        upload_data = {
            "data": ddm_edu_data if ddm_edu_data else {},
            "updated_at": datetime.now().isoformat(),
        }
        upload_to_s3(upload_data, "dynamic_programs/ddm_edu_programs.json")

    except Exception as e:
        print(f"❌ 교육지원센터 크롤링 실패: {e}")
        results["ddm_edu"] = {"status": "failed", "error": str(e)}
        # 실패해도 빈 파일 업로드
        upload_data = {
            "data": {},
            "updated_at": datetime.now().isoformat(),
            "error": str(e),
        }
        upload_to_s3(upload_data, "dynamic_programs/ddm_edu_programs.json")

    # 3. 교육소식 크롤링
    print("\n[3/4] 동대문구청 교육소식 크롤링...")
    try:
        ddm_news_data = crawl_ddm_news()
        results["ddm_news"] = {
            "count": len(ddm_news_data) if ddm_news_data else 0,
            "status": "success",
        }

        # 빈 데이터여도 업로드
        upload_data = {
            "data": ddm_news_data if ddm_news_data else [],
            "count": len(ddm_news_data) if ddm_news_data else 0,
            "updated_at": datetime.now().isoformat(),
        }
        upload_to_s3(upload_data, "dynamic_programs/ddm_news.json")

    except Exception as e:
        print(f"❌ 교육소식 크롤링 실패: {e}")
        results["ddm_news"] = {"status": "failed", "error": str(e)}
        # 실패해도 빈 파일 업로드
        upload_data = {
            "data": [],
            "count": 0,
            "updated_at": datetime.now().isoformat(),
            "error": str(e),
        }
        upload_to_s3(upload_data, "dynamic_programs/ddm_news.json")

    # 4. 예약포털 크롤링
    print("\n[4/4] 동대문구 예약포털 크롤링...")
    try:
        reserve_crawler = DDMReserveCrawler()
        ddm_reserve_data = reserve_crawler.crawl_all()
        results["ddm_reserve"] = {
            "count": len(ddm_reserve_data) if ddm_reserve_data else 0,
            "status": "success",
        }

        # 빈 데이터여도 업로드
        upload_data = {
            "data": ddm_reserve_data if ddm_reserve_data else [],
            "count": len(ddm_reserve_data) if ddm_reserve_data else 0,
            "updated_at": datetime.now().isoformat(),
        }
        upload_to_s3(upload_data, "dynamic_programs/ddm_reserve.json")

    except Exception as e:
        print(f"❌ 예약포털 크롤링 실패: {e}")
        results["ddm_reserve"] = {"status": "failed", "error": str(e)}
        # 실패해도 빈 파일 업로드
        upload_data = {
            "data": [],
            "count": 0,
            "updated_at": datetime.now().isoformat(),
            "error": str(e),
        }
        upload_to_s3(upload_data, "dynamic_programs/ddm_reserve.json")

    # 최종 결과 출력
    print("\n" + "=" * 60)
    print("   크롤링 완료 요약")
    print("=" * 60)
    total_count = 0
    for name, result in results.items():
        if result["status"] == "success":
            count = result.get("count", 0)
            total_count += count
            if count > 0:
                print(f"✅ {name}: {count}개")
            else:
                print(f"⚠️ {name}: 데이터 없음 (0개)")
        else:
            print(f"❌ {name}: 실패 - {result.get('error', 'Unknown error')}")

    print(f"\n총 {total_count}개 데이터 수집 완료")
    print("완료 시간:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 로컬 요약 파일 저장
    summary = {
        "results": results,
        "total_count": total_count,
        "completed_at": datetime.now().isoformat(),
    }
    with open("crawl_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return results


if __name__ == "__main__":
    main()
