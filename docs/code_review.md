# Sprint 3 코드 리뷰 (Code Review)

## 3. 개선 제안 (Optional)
- **에러 로깅 (Logging)**: `reader.py`의 `process_message` 예외 처리 블록에 `logging` 모듈을 이용한 에러 로깅을 추가하면, 향후 실제 운영 단계나 Team 모드 개발 시 디버깅에 큰 도움이 될 수 있습니다.
- **페이징 (Pagination)**: 현재 `GET /api/sessions`가 모든 세션을 반환하고 있습니다. 추후 데이터가 많아질 것을 대비해 `limit`/`offset` 등의 페이징 처리나 무한 스크롤(Cursor 기반) 준비를 고민해 볼 수 있습니다.
