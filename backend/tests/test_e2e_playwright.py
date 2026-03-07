import pytest
from playwright.async_api import Page, expect

# 프론트엔드 URL (Vite 기본값)
BASE_URL = "http://localhost:5173"


@pytest.mark.asyncio
async def test_team_mode_parallel_execution_ui(page: Page):
    """Team 모드 실행 시 UI에서 병렬 에이전트와 스트리밍이 정상 작동하는지 확인."""

    # 1. 페이지 접속
    await page.goto(BASE_URL)

    # 페이지 제목 또는 특정 텍스트가 나타날 때까지 대기 (로딩 확인)
    await expect(page.get_by_placeholder("메시지를 입력하세요...")).to_be_visible()

    # 2. Team 모드 메시지 입력 및 전송
    # 규칙 기반 분류를 트리거하기 위해 (팀모드) 헤더와 번호 목록 사용
    test_message = "(팀모드) 다음 작업을 수행해줘: 1. 첫 번째 분석 수행 2. 두 번째 코드 작성"
    await page.get_by_placeholder("메시지를 입력하세요...").fill(test_message)
    await page.get_by_role("button", name="전송").click()

    # 3. 사용자 메시지가 화면에 나타났는지 확인
    await expect(page.get_by_text("다음 작업을 수행해줘")).to_be_visible()

    # 4. 에이전트 채널 확인 (오른쪽 패널)
    # 병렬로 두 에이전트가 생성되어야 함
    # Researcher-1, Coder-2 등의 텍스트가 나타나는지 확인
    await expect(page.get_by_text("Researcher-1")).to_be_visible(timeout=10000)
    await expect(page.get_by_text("Coder-2")).to_be_visible(timeout=10000)

    # 5. 스트리밍 상태 확인
    # 'working' 상태 배지가 나타나는지 확인
    await expect(page.get_by_text("working")).to_be_visible()

    # 6. 최종 답변 완료 대기 (최대 60초)
    # 답변이 완료되면 'done' 상태로 변하고 결과 텍스트가 표시됨
    await expect(page.get_by_text("done")).to_be_visible(timeout=60000)

    # 7. 취소 버튼 테스트 (별도 테스트로 분리 가능하나 흐름상 포함)
    # 신규 메시지 전송 후 즉시 취소 클릭
    await page.get_by_placeholder("메시지를 입력하세요...").fill("취소 테스트용 메시지")
    await page.get_by_role("button", name="전송").click()

    cancel_btn = page.get_by_role("button", name="취소 ✕")
    await expect(cancel_btn).to_be_visible()
    await cancel_btn.click()

    # 취소됨 메시지가 나타나는지 확인
    await expect(page.get_by_text("취소되었습니다")).to_be_visible(timeout=10000)


if __name__ == "__main__":
    # 수동 실행 시 가이드
    print("이 테스트를 실행하려면 백엔드(8000)와 프론트엔드(5173)가 모두 실행 중이어야 합니다.")
