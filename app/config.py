"""Configurações lidas de variáveis de ambiente"""
import os
import secrets

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./food_rescue.db")

        # Se SECRET_KEY não for definida, gera uma aleatória (os tokens deixam de valer ao reiniciar).
        self.secret_key = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
        self.jwt_algorithm = "HS256"
        self.access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
        self.password_iterations = int(os.getenv("PASSWORD_ITERATIONS", "200000"))

        self.admin_email = os.getenv("ADMIN_EMAIL")
        self.admin_password = os.getenv("ADMIN_PASSWORD")

        self.webhook_secret = os.getenv("WEBHOOK_SECRET", "")
        self.webhook_timeout = float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "3"))

        # Regra de compatibilidade (peso da capacidade; o da distância é o complemento)
        self.max_distance_km = float(os.getenv("MAX_DISTANCE_KM", "30"))
        self.weight_capacity = float(os.getenv("WEIGHT_CAPACITY", "0.6"))

        # Estimativa para as métricas de impacto: 1 refeição ≈ 0,5 kg
        self.kg_per_meal = 0.5


settings = Settings()
