"""Allow running seed as: python -m app.db"""
from app.db.seed import main
import asyncio

asyncio.run(main())
