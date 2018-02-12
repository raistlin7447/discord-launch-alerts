import redis

db = redis.StrictRedis(host='localhost', charset="utf-8", decode_responses=True)  # TODO: Make DB configurable in local_config
LAUNCH_MONITORS_KEY = "launch-monitors"


