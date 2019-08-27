import redis
r = redis.from_url(os.environ.get("REDIS_URL"))
for key in r.scan_iter():
       print key