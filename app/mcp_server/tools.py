# 실제 도구 함수들이 정의되는 곳입니다.

def calculate_sum(a: int, b: int) -> int:
    """두 숫자의 합을 계산하여 반환합니다."""
    print(f"[Tool Log] Calculating {a} + {b}")
    return a + b

def get_system_status() -> str:
    """현재 시스템의 상태 문자열을 반환합니다."""
    return "SYSTEM_NORMAL_OPERATION"