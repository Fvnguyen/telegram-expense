import pickle
import redis
data = pickle.loads('migrate')
r = redis.from_url(os.environ.get("REDIS_URL"))
pdb = pickle.dumps(data)
r.set(user_id,pdb)