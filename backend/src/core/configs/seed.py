from pathlib import Path

from pydantic import BaseModel


class SeedSettings(BaseModel):
    PATH: Path = Path("../seed/companies.json")
