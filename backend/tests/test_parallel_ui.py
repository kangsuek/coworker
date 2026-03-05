import asyncio
import time
import subprocess
import os
import signal
from playwright.async_api import async_playwright

async def wait_for_port(port, timeout=30):
    """특정 포트가 열릴 때까지 대기."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            await asyncio.sleep(1)
    return False

async def run_test():
    print("서버 기동 시작...")
    
    # 1. 백엔드 실행
    backend_proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=".",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    
    # 2. 프론트엔드 실행
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", "5173"],
        cwd="../frontend",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    try:
        print("서버 준비 대기 중 (8000, 5173)...")
        if not await wait_for_port(8000) or not await wait_for_port(5173):
            print("서버 기동 실패: 포트 대기 시간 초과")
            return

        print("서버 준비 완료! Playwright 테스트 시작...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto("http://127.0.0.1:5173", timeout=30000)
            
            # 1. LLM 설정 변경 (Gemini CLI + Gemini3 flash)
            print("LLM 설정 변경 중: Gemini CLI / Gemini3 flash")
            # 첫 번째 select (Provider) 선택
            await page.select_option('select:nth-of-type(1)', value='gemini-cli')
            # 두 번째 select (Model) 선택 - Provider 변경 시 옵션이 바뀌므로 잠시 대기
            await asyncio.sleep(0.5)
            await page.select_option('select:nth-of-type(2)', value='gemini-3-flash-preview')
            
            input_selector = 'input[placeholder="메시지를 입력하세요..."]'
            await page.wait_for_selector(input_selector)
            
            # 2. 질문 입력
            test_query = "(팀모드) 1.개기월식일어나는 현상을 조사 하세요. 2. 대한민국에서 개기월식이 언제 일어날지 알려 주세요. 3. 두 내용을 종합하여 간단한 교육 제도를 만드세요."
            await page.fill(input_selector, test_query)
            await page.press(input_selector, "Enter")
            print(f"질문 전송: {test_query}")

            # 병렬 노출 검증
            found_parallel = False
            start_time = time.time()
            print("에이전트 노출 상태 확인 중...")
            while time.time() - start_time < 30:
                # 현재 화면의 모든 텍스트 가져오기
                content = await page.content()
                
                # 디버깅: Researcher 라는 단어가 포함된 줄 모두 출력
                if "Researcher" in content:
                    import re
                    researchers = re.findall(r'Researcher-\d+', content)
                    if researchers:
                        print(f"발견된 에이전트: {set(researchers)}")
                    
                    if "Researcher-1" in content and "Researcher-2" in content:
                        print(">>> [검증 성공] Researcher-1과 Researcher-2가 동시에 화면에 표시되었습니다!")
                        found_parallel = True
                        break
                
                await asyncio.sleep(1)

            if not found_parallel:
                print(">>> [검증 실패] 두 에이전트가 동시에 나타나지 않았습니다.")
                # 현재 페이지의 전체 텍스트 덤프 (일부만)
                text_content = await page.evaluate("() => document.body.innerText")
                print(f"현재 페이지 텍스트 요약: {text_content[:500]}...")

            # 스트리밍 확인
            print("스트리밍 및 완료 상태 대기...")
            try:
                await page.wait_for_selector('text="done"', timeout=60000)
                print(">>> [최종 확인] 모든 프로세스가 정상 완료되었습니다.")
            except Exception:
                print(">>> [최종 확인 실패] 완료 상태(done)를 포착하지 못했습니다.")

            await browser.close()

    finally:
        print("서버 종료 중...")
        os.killpg(os.getpgid(backend_proc.pid), signal.SIGTERM)
        os.killpg(os.getpgid(frontend_proc.pid), signal.SIGTERM)
        print("테스트 종료.")

if __name__ == "__main__":
    asyncio.run(run_test())
