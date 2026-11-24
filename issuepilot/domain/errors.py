"""도메인 오류."""


class ClassificationFailed(Exception):
    """분류기가 유효한 결과를 내지 못했다. 메시지에는 이슈 내용을 넣지 않는다."""
