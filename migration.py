# import pickle
# import redis
# import os
# infile = open('migrate','rb')
# data = pickle.load(infile)
# infile.close()
# r = redis.from_url(os.environ.get("REDIS_URL"))
# pdb = pickle.dumps(data)
# r.set('961108390',pdb)