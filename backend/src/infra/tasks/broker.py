import taskiq_fastapi
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisStreamBroker

from core.configs import settings

broker = RedisStreamBroker(
    url=settings.redis.url,
    queue_name=settings.redis.QUEUE_NAME,
)

scheduler = TaskiqScheduler(broker, sources=[LabelScheduleSource(broker)])

taskiq_fastapi.init(broker, "app:create_worker_app")
