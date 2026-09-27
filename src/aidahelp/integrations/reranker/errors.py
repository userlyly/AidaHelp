"""精排服务异常。"""


class RerankerError(Exception):
    pass


class RerankerNotConfiguredError(RerankerError):
    pass


class RerankerUpstreamError(RerankerError):
    pass
