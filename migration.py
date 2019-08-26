import pickle
import redis
infile = open('migrate','rb')
data = pickle.load(infile)
infile.close()
r = redis.from_url(os.environ.get("REDIS_URL"))
pdb = pickle.dumps(data)
r.set(user_id,pdb)