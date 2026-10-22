"""Klien tiruan untuk pengembangan alur tanpa model. HANYA untuk tes, bukan evaluasi atau demo."""


class MockLlmClient:
    def __init__(self, fixed_sql: list[str]):
        self.fixed_sql = fixed_sql

    def generate(self, prompt: str, n: int, system: str | None = None) -> list[str]:
        return (self.fixed_sql * n)[:n]
